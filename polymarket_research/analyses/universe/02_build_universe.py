"""Build data/derived/markets_resolved.parquet and events_resolved.parquet from the pulled chunks.

Run from polymarket_research/:  python analyses/universe/02_build_universe.py [stageA|stageB|events|all]
Inputs: data/raw/gamma_universe/markets/*.ndjson.gz, data/raw/gamma_universe/events/*.ndjson.gz,
        data/raw/gamma_universe/events_missing_by_id.json.gz (written by 01_pull_gamma.py)
Streaming: stage A parses each window in 100k-row parts (fixed Arrow schema) into
data/raw/gamma_universe/parts/; stage B de-duplicates by Gamma id, filters endDate to
[2024-01-01, 2026-10-16), adds event-level columns and writes the final parquet incrementally.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from categories import category_from_fee_type, category_from_rule  # noqa: E402

RAW = ROOT / "data" / "raw" / "gamma_universe"
PARTS = RAW / "parts"
DER = ROOT / "data" / "derived"
LO, HI = pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2026-10-16", tz="UTC")  # endDate in [LO, HI)
BATCH = 100_000

S, F, I, B, T = pa.string(), pa.float64(), pa.int64(), pa.bool_(), pa.timestamp("us", tz="UTC")
LS, LF = pa.list_(pa.string()), pa.list_(pa.float64())
SCHEMA_A = [
    ("id", S), ("condition_id", S), ("question_id", S), ("slug", S), ("question", S), ("groupItemTitle", S),
    ("groupItemThreshold", S), ("sportsMarketType", S), ("line", F),
    ("startDate", T), ("endDate", T), ("createdAt", T), ("closedTime", T), ("umaEndDate", T), ("gameStartTime", T),
    ("eventStartTime", T), ("updatedAt", T),
    ("umaResolutionStatus", S), ("umaResolutionStatuses", LS), ("n_proposed", I), ("n_disputed", I),
    ("has_disputed", B), ("multi_proposal", B), ("dispute_flag", B), ("automaticallyResolved", B),
    ("outcomes", LS), ("outcome_prices", LF), ("clob_token_ids", LS), ("token_id_0", S), ("token_id_1", S),
    ("n_outcomes", I), ("parse_ok", B), ("resolution", S), ("winner_idx", I), ("winner_outcome", S),
    ("negRisk", B), ("negRiskMarketID", S), ("negRiskRequestID", S), ("negRiskOther", B),
    ("volumeNum", F), ("volumeClob", F), ("volumeAmm", F), ("liquidityNum", F), ("liquidityClob", F),
    ("feesEnabled", B), ("feeType", S), ("feeSchedule", S), ("fee_rate", F), ("fee_exponent", F),
    ("fee_rebate_rate", F), ("fee_taker_only", B), ("makerBaseFee", F), ("takerBaseFee", F),
    ("secondsDelay", F), ("orderPriceMinTickSize", F), ("orderMinSize", F), ("rewardsMinSize", F),
    ("rewardsMaxSpread", F), ("holdingRewardsEnabled", B), ("clobRewards_json", S), ("restricted", B),
    ("version", S), ("enableOrderBook", B), ("active", B), ("archived", B), ("closed", B), ("resolvedBy", S),
    ("umaBond", F), ("umaReward", F), ("customLiveness", F), ("fallbackResolutionType", S),
    ("lastTradePrice", F), ("bestBid", F), ("bestAsk", F), ("spread", F), ("marketMakerAddress", S),
    ("fpmmLive", B), ("rfqEnabled", B), ("comboStatus", S), ("cyom", B),
    ("tags", LS), ("n_events", I), ("event_ids_all", LS),
    ("event_id", S), ("event_slug", S), ("event_title", S), ("event_ticker", S), ("event_negRisk", B),
    ("event_negRiskMarketID", S), ("event_enableNegRisk", B), ("event_negRiskAugmented", B),
    ("event_seriesSlug", S), ("series_slugs", LS), ("event_startDate", T), ("event_endDate", T),
    ("event_closedTime", T), ("event_version", S), ("event_cyom", B), ("event_closed", B),
    ("category_fee", S), ("category_rule", S), ("category", S), ("category_source", S),
    ("settle_lag_h", F), ("settle_lag_game_h", F), ("duration_h", F), ("end_quarter", S), ("split", S),
    ("src_window", S),
]
SCHEMA_B_EXTRA = [("event_n_markets_universe", I), ("structure", S), ("cluster_id", S), ("cluster_source", S),
                  ("cluster_week", S), ("n_proposal_rounds", I), ("dup_proposal_record", B), ("traded", B)]
# Sports games are split over several Gamma events that share the slug stem up to the ISO date
# (e.g. bra-cor1-cre-2026-07-23, ...-halftime-result, ...-more-markets, ...-player-props), so for sports
# the leakage cluster is that stem; otherwise the parent event, then negRiskMarketID, then the market.
GAME_STEM = r"^(.+?-\d{4}-\d{2}-\d{2})(?:-[a-z0-9-]+)?$"

RENAME = {"conditionId": "condition_id", "questionID": "question_id"}
EV_FIELDS = ["id", "slug", "title", "ticker", "negRisk", "negRiskMarketID", "enableNegRisk", "negRiskAugmented",
             "seriesSlug", "startDate", "endDate", "closedTime", "version", "cyom", "closed"]


def read_ndjson(path: Path):
    with gzip.open(path, "rt") as f:
        for line in f:
            yield json.loads(line)


def jl(v):
    if v is None:
        return None
    if isinstance(v, list):
        return v
    try:
        x = json.loads(v)
        return x if isinstance(x, list) else None
    except (TypeError, json.JSONDecodeError):
        return None


def ts(s) -> pd.Series:
    return pd.to_datetime(pd.Series(s), utc=True, format="mixed", errors="coerce")


def parse_resolution(prices) -> tuple[str, int | None]:
    """winner: exactly one payout == 1 and the rest 0; split_50_50: binary [0.5, 0.5]; else non-terminal."""
    if not prices:
        return "missing_prices", None
    try:
        p = [float(x) for x in prices]
    except (TypeError, ValueError):
        return "unparseable_prices", None
    if len(p) >= 2 and sum(1 for x in p if x == 1.0) == 1 and all(x in (0.0, 1.0) for x in p):
        return "winner", int(p.index(1.0))
    if len(p) == 2 and p[0] == 0.5 and p[1] == 0.5:
        return "split_50_50", None
    if all(x == 0.0 for x in p):
        return "all_zero", None
    return "unresolved_nonterminal", None


def uma_flags(sts) -> tuple[int, bool]:
    """(proposal rounds, consecutive duplicate 'proposed' records) from umaResolutionStatuses.

    From 2026-08 the status history of most markets reads ['proposed', 'proposed'] (0.3% of markets ending
    2026-07, 87% of those ending 2026-09) with no dispute and automatic resolution: a recording change,
    not a re-proposal. A proposal round is therefore a run of consecutive 'proposed' entries; a real
    second round needs an intervening status (in practice 'disputed')."""
    rounds, dup, prev = 0, False, None
    for x in sts if sts is not None else []:
        if x == "proposed":
            if prev == "proposed":
                dup = True
            else:
                rounds += 1
        prev = x
    return rounds, dup


def build_part(rows: list[dict], label: str) -> pa.Table:
    d = {}
    g = lambda k: [r.get(k) for r in rows]  # noqa: E731
    for k in ["id", "conditionId", "questionID", "slug", "question", "groupItemTitle", "groupItemThreshold",
              "sportsMarketType", "umaResolutionStatus", "negRiskMarketID", "negRiskRequestID", "feeType",
              "clobRewards_json", "version", "resolvedBy", "fallbackResolutionType", "marketMakerAddress", "comboStatus"]:
        d[RENAME.get(k, k)] = [None if v is None else str(v) for v in g(k)]
    for k in ["line", "volumeNum", "volumeClob", "volumeAmm", "liquidityNum", "liquidityClob", "makerBaseFee",
              "takerBaseFee", "secondsDelay", "orderPriceMinTickSize", "orderMinSize", "rewardsMinSize",
              "rewardsMaxSpread", "umaBond", "umaReward", "customLiveness", "lastTradePrice", "bestBid", "bestAsk", "spread"]:
        d[k] = pd.to_numeric(pd.Series(g(k), dtype=object), errors="coerce").astype(float).tolist()
    for k in ["automaticallyResolved", "negRisk", "negRiskOther", "feesEnabled", "holdingRewardsEnabled", "restricted",
              "enableOrderBook", "active", "archived", "closed", "fpmmLive", "rfqEnabled", "cyom"]:
        d[k] = [None if v is None else bool(v) for v in g(k)]
    d["negRisk"] = [bool(v) for v in d["negRisk"]]
    d["negRiskOther"] = [bool(v) for v in d["negRiskOther"]]
    for k in ["startDate", "endDate", "createdAt", "closedTime", "umaEndDate", "gameStartTime", "eventStartTime", "updatedAt"]:
        d[k] = ts(g(k))
    # outcomes / resolution
    outs = [jl(v) for v in g("outcomes")]
    prices = [jl(v) for v in g("outcomePrices")]
    toks = [jl(v) for v in g("clobTokenIds")]
    d["outcomes"] = [[str(x) for x in o] if o is not None else None for o in outs]
    d["clob_token_ids"] = [[str(x) for x in t] if t is not None else None for t in toks]
    fp = []
    for p in prices:
        try:
            fp.append([float(x) for x in p] if p is not None else None)
        except (TypeError, ValueError):
            fp.append(None)
    d["outcome_prices"] = fp
    d["token_id_0"] = [t[0] if t else None for t in d["clob_token_ids"]]
    d["token_id_1"] = [t[1] if t and len(t) > 1 else None for t in d["clob_token_ids"]]
    d["n_outcomes"] = [len(o) if o else 0 for o in outs]
    d["parse_ok"] = [bool(o) and p is not None and t is not None and len(o) == len(p) == len(t)
                     for o, p, t in zip(outs, fp, toks)]
    res = [parse_resolution(p) for p in prices]
    d["resolution"] = [r[0] for r in res]
    d["winner_idx"] = [r[1] for r in res]
    d["winner_outcome"] = [str(o[i]) if (o and i is not None and i < len(o)) else None for o, (_, i) in zip(outs, res)]
    # UMA
    sts = [[str(x) for x in (jl(v) or [])] for v in g("umaResolutionStatuses")]
    d["umaResolutionStatuses"] = sts
    d["n_proposed"] = [s.count("proposed") for s in sts]
    d["n_disputed"] = [s.count("disputed") for s in sts]
    d["has_disputed"] = [nd > 0 or u == "disputed" for nd, u in zip(d["n_disputed"], d["umaResolutionStatus"])]
    d["multi_proposal"] = [uma_flags(x)[0] > 1 for x in sts]
    d["dispute_flag"] = [a or b for a, b in zip(d["has_disputed"], d["multi_proposal"])]
    # fees
    fsl = []
    for v in g("feeSchedule"):
        if isinstance(v, str) and v.startswith("{"):
            v = json.loads(v)
        fsl.append(v if isinstance(v, dict) else None)
    d["feeSchedule"] = [json.dumps(x, sort_keys=True) if x else None for x in fsl]
    d["fee_rate"] = [float(x["rate"]) if x and x.get("rate") is not None else None for x in fsl]
    d["fee_exponent"] = [float(x["exponent"]) if x and x.get("exponent") is not None else None for x in fsl]
    d["fee_rebate_rate"] = [float(x["rebateRate"]) if x and x.get("rebateRate") is not None else None for x in fsl]
    d["fee_taker_only"] = [bool(x["takerOnly"]) if x and x.get("takerOnly") is not None else None for x in fsl]
    # tags / events
    d["tags"] = [sorted({t.get("slug") for t in json.loads(v or "[]") if t.get("slug")}) for v in g("tags_json")]
    evs = [json.loads(v or "[]") for v in g("events_json")]
    d["n_events"] = [len(e) for e in evs]
    d["event_ids_all"] = [[str(x.get("id")) for x in e] for e in evs]
    e0 = [e[0] if e else {} for e in evs]
    for k in EV_FIELDS:
        vals = [e.get(k) for e in e0]
        if k in ("startDate", "endDate", "closedTime"):
            d[f"event_{k}"] = ts(vals)
        elif k in ("negRisk", "enableNegRisk", "negRiskAugmented", "cyom", "closed"):
            d[f"event_{k}"] = [None if v is None else bool(v) for v in vals]
        else:
            d[f"event_{k}"] = [None if v is None else str(v) for v in vals]
    d["series_slugs"] = [[str(s) for s in (e.get("series_slugs") or []) if s] for e in e0]
    # categories
    d["category_fee"] = [category_from_fee_type(v) for v in d["feeType"]]
    d["category_rule"] = [category_from_rule(set(t) | set(), s, q, smt) for t, s, q, smt in
                          zip(d["tags"], d["slug"], d["question"], d["sportsMarketType"])]
    d["category"] = [a if a else b for a, b in zip(d["category_fee"], d["category_rule"])]
    d["category_source"] = ["feeType" if a else "rule" for a in d["category_fee"]]
    # timing
    end, start, closed, game = d["endDate"], d["startDate"], d["closedTime"], d["gameStartTime"]
    d["settle_lag_h"] = ((closed - end).dt.total_seconds() / 3600).tolist()
    d["settle_lag_game_h"] = ((closed - game).dt.total_seconds() / 3600).tolist()
    d["duration_h"] = ((end - start).dt.total_seconds() / 3600).tolist()
    d["end_quarter"] = [None if pd.isna(x) else f"{x.year}Q{(x.month - 1) // 3 + 1}" for x in end]
    d["split"] = [None if pd.isna(x) else ("train" if x < pd.Timestamp("2025-07-01", tz="UTC") else
                                           "validation" if x < pd.Timestamp("2026-01-01", tz="UTC") else "test") for x in end]
    d["src_window"] = [label] * len(rows)
    for k in list(d):
        if isinstance(d[k], pd.Series):
            d[k] = d[k].tolist() if not pd.api.types.is_datetime64_any_dtype(d[k]) else d[k]
    arrays = []
    for name, typ in SCHEMA_A:
        v = d[name]
        if isinstance(v, pd.Series):
            arrays.append(pa.array(v.dt.tz_convert("UTC").astype("datetime64[us, UTC]"), type=typ, from_pandas=True))
        else:
            if typ == F:
                v = [None if (x is None or (isinstance(x, float) and np.isnan(x))) else float(x) for x in v]
            arrays.append(pa.array(v, type=typ, from_pandas=True))
    return pa.Table.from_arrays(arrays, schema=pa.schema(SCHEMA_A))


def stage_a() -> None:
    PARTS.mkdir(parents=True, exist_ok=True)
    for p in sorted((RAW / "markets").glob("*.ndjson.gz")):
        label = p.name.split(".")[0]
        if (PARTS / f"{label}.done").exists():
            continue
        buf, k = [], 0
        for r in read_ndjson(p):
            buf.append(r)
            if len(buf) >= BATCH:
                pq.write_table(build_part(buf, label), PARTS / f"{label}_{k:03d}.parquet")
                buf, k = [], k + 1
        if buf:
            pq.write_table(build_part(buf, label), PARTS / f"{label}_{k:03d}.parquet")
            k += 1
        (PARTS / f"{label}.done").write_text(str(k))
        print("stageA", label, "parts", k, flush=True)


def stage_b() -> dict:
    files = sorted(PARTS.glob("*.parquet"))
    base = pd.concat([pq.read_table(f, columns=["id", "endDate", "event_id", "negRisk", "src_window"]).to_pandas()
                      for f in files], ignore_index=True)  # same order as the write loop below
    stats = {"raw_rows": int(len(base)), "rows_by_window": base["src_window"].value_counts().sort_index().to_dict()}
    dup = base["id"].duplicated(keep="first")
    stats["dup_ids_removed"] = int(dup.sum())
    stats["null_endDate"] = int(base["endDate"].isna().sum())
    inwin = base["endDate"].ge(LO) & base["endDate"].lt(HI)
    stats["outside_window_removed"] = int((~inwin & ~dup).sum())
    keep = ~dup & inwin
    kept = base[keep]
    ev_n = kept.groupby("event_id")["id"].size()
    stats["final_rows"] = int(keep.sum())
    keep_arr = keep.to_numpy()
    out_path = DER / "markets_resolved.parquet"
    schema = pa.schema(SCHEMA_A + SCHEMA_B_EXTRA)
    writer = pq.ParquetWriter(out_path, schema, compression="zstd")
    offset = 0
    for f in files:
        t = pq.read_table(f)
        n = t.num_rows
        mask = keep_arr[offset:offset + n]
        offset += n
        df = t.filter(pa.array(mask)).to_pandas()
        if not len(df):
            continue
        en = df["event_id"].map(ev_n)
        df["event_n_markets_universe"] = en.astype("Int64")
        df["structure"] = np.select([df["negRisk"].astype(bool), en.fillna(1).gt(1)],
                                    ["neg_risk", "binary_grouped"], "binary_standalone")
        uf = [uma_flags(x) for x in df["umaResolutionStatuses"]]
        df["n_proposal_rounds"] = [a for a, _ in uf]
        df["dup_proposal_record"] = [b for _, b in uf]
        df["multi_proposal"] = df["n_proposal_rounds"] > 1   # overrides stage-A raw count (> 1 'proposed')
        df["dispute_flag"] = df["has_disputed"].astype(bool) | df["multi_proposal"]
        # Trading proxy. Gamma volumeNum is NULL for 43% of markets, and NULL does not mean untraded: /v2/trades
        # samples (2026-10-17) found trades in 20/25 null-volume crypto and 22/25 null-volume non-sports
        # non-crypto markets, and in 25/25 null-volume markets that carry a lastTradePrice. Among markets with
        # both fields null, trades were found in 9/30 crypto, 1/30 sports, 0/30 other; volumeNum == 0: 0/30.
        df["traded"] = df["volumeNum"].fillna(0).gt(0) | df["lastTradePrice"].notna()
        stem = df["event_slug"].str.extract(GAME_STEM, expand=False)
        is_game = df["category"].eq("sports") & stem.notna()
        has_ev, has_nr = df["event_id"].notna(), df["negRiskMarketID"].notna()
        df["cluster_source"] = np.select([is_game, has_ev, has_nr], ["sports_game_stem", "event_id", "negRiskMarketID"],
                                         "condition_id")
        df["cluster_id"] = np.select([is_game, has_ev, has_nr],
                                     ["g:" + stem.fillna(""), "e:" + df["event_id"].fillna(""),
                                      "n:" + df["negRiskMarketID"].fillna("")], "c:" + df["condition_id"].fillna(""))
        iso = df["endDate"].dt.isocalendar()
        df["cluster_week"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
        writer.write_table(pa.Table.from_pandas(df, schema=schema, preserve_index=False))
    writer.close()
    print("markets_resolved rows", stats["final_rows"], flush=True)
    return stats


def events(stats: dict) -> dict:
    erows = []
    keep = ["id", "slug", "title", "ticker", "negRisk", "negRiskMarketID", "enableNegRisk", "negRiskAugmented",
            "negRiskFeeBips", "seriesSlug", "series_json", "tags_json", "startDate", "creationDate", "endDate",
            "closedTime", "createdAt", "closed", "active", "archived", "restricted", "volume", "liquidity",
            "openInterest", "commentCount", "automaticallyResolved", "cyom", "version"]
    for p in sorted((RAW / "events").glob("*.ndjson.gz")):
        erows += [{k: r.get(k) for k in keep} for r in read_ndjson(p)]
    mp = RAW / "events_missing_by_id.json.gz"
    n_missing_fetch = 0
    if mp.exists():
        with gzip.open(mp, "rt") as f:
            extra = json.load(f)["rows"]
        n_missing_fetch = len(extra)
        erows += [{k: r.get(k) for k in keep} for r in extra]
    ev = pd.DataFrame(erows)
    ev["id"] = ev["id"].astype(str)
    ev = ev.drop_duplicates("id")
    m = pd.read_parquet(DER / "markets_resolved.parquet",
                        columns=["id", "event_id", "volumeNum", "category", "endDate", "negRisk", "event_slug", "event_title"])
    used = set(m["event_id"].dropna())
    stats["events_pulled_total"] = int(len(ev))
    stats["events_referenced"] = len(used)
    stats["events_found"] = len(used & set(ev["id"]))
    stats["markets_with_event_found"] = int(m["event_id"].isin(set(ev["id"])).sum())
    stats["markets_without_event_id"] = int(m["event_id"].isna().sum())
    stats["events_missing_fetch_rows"] = n_missing_fetch
    ev = ev[ev["id"].isin(used)].copy()
    ev["tags"] = ev["tags_json"].map(lambda r: sorted({t.get("slug") for t in json.loads(r or "[]") if t.get("slug")}))
    ev["tag_labels"] = ev["tags_json"].map(lambda r: [str(t.get("label")) for t in json.loads(r or "[]")])
    ev = ev.drop(columns=["tags_json"])
    agg = m.groupby("event_id").agg(n_markets_universe=("id", "size"), volume_markets=("volumeNum", "sum"),
                                    first_end=("endDate", "min"), last_end=("endDate", "max"),
                                    n_neg_risk=("negRisk", "sum"))
    cm = m.groupby(["event_id", "category"]).size().reset_index(name="n").sort_values(["event_id", "n"], ascending=[True, False])
    agg["category_mode"] = cm.drop_duplicates("event_id").set_index("event_id")["category"]
    ev = ev.merge(agg, left_on="id", right_index=True, how="left")
    ev = ev.rename(columns={"id": "event_id", "slug": "event_slug", "title": "event_title"})
    for c in ["startDate", "creationDate", "endDate", "closedTime", "createdAt"]:
        ev[c] = ts(ev[c]).values
    for c in ["volume", "liquidity", "openInterest", "commentCount", "negRiskFeeBips"]:
        ev[c] = pd.to_numeric(ev[c], errors="coerce")
    for c in ["negRisk", "enableNegRisk", "negRiskAugmented", "closed", "active", "archived", "restricted",
              "automaticallyResolved", "cyom"]:
        ev[c] = ev[c].astype("boolean")
    for c in ["event_id", "event_slug", "event_title", "ticker", "negRiskMarketID", "seriesSlug", "series_json", "version"]:
        ev[c] = ev[c].map(lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)).astype("string")
    ev["n_markets_universe"] = ev["n_markets_universe"].astype("Int64")
    ev.to_parquet(DER / "events_resolved.parquet", index=False)
    print("events_resolved rows", len(ev), flush=True)
    return stats


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    sp = DER / "universe_build_stats.json"
    stats = json.loads(sp.read_text()) if sp.exists() else {}
    if what in ("stageA", "all"):
        stage_a()
    if what in ("stageB", "all"):
        stats.update(stage_b())
    if what in ("events", "all"):
        stats = events(stats)
    sp.write_text(json.dumps(stats, indent=1, default=str))
    print(json.dumps({k: v for k, v in stats.items() if k != "rows_by_window"}, indent=1, default=str))
