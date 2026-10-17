"""Step 3: per-token market metadata for the PIT study + the external table uploaded to CryptoHouse.

Run from polymarket_research/:  python analyses/pit_wallets/03b_build_meta.py
Inputs: traded_assets.parquet (02), gamma_markets_traded.parquet + token_meta.parquet (03), ch_assets.parquet (03a).
Outputs (data/derived/pit_wallets/):
  market_meta.parquet  one row per traded market (condition) with event, category, payout class, t_res
  token_meta_pit.parquet one row per traded token with k (last 18 digits), cond/event indices, payout, t_res, cat
  meta_ext.tsv         external table "k c e p r cat" for 04/06
  meta_checks.json     coverage and cross-check numbers quoted in the build note
Rules (pre-registered, section 3):
  payout p = 1 / 0 only if the Gamma market is closed and outcomePrices are exactly 1/0 (tolerance 1e-3);
  otherwise p = -1 (excluded from win/loss records: 50-50, other splits, unresolved, missing).
  t_res = closedTime, else umaEndDate, else CryptoHouse assets.market_closed_date (>1970), else 0 (excluded).
  event = Gamma parent event id (events[0]); markets without one use their condition id as a pseudo-event;
  sports events sharing a "<...>-YYYY-MM-DD" slug prefix are merged into one underlying event (addendum A6).
  category from tag slugs (market tags), first match in order crypto, sports, politics, else other.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

OUT = ROOT / "data" / "derived" / "pit_wallets"

# Category slug lists, fixed from tag frequencies only (no performance data seen); see build note.
CRYPTO = {"crypto", "crypto-prices", "bitcoin", "ethereum", "solana", "xrp", "dogecoin", "up-or-down", "crypto-up-or-down",
          "15m", "hourly-crypto", "4h", "airdrops", "memecoins", "stablecoins", "token-launches", "pre-market"}
SPORTS = {"sports", "nba", "nfl", "mlb", "nhl", "soccer", "football", "basketball", "baseball", "hockey", "tennis", "golf",
          "ufc", "mma", "boxing", "f1", "formula-1", "cricket", "esports", "ncaa", "ncaab", "cbb", "cfb", "epl", "premier-league",
          "champions-league", "la-liga", "serie-a", "bundesliga", "ligue-1", "mls", "wnba", "olympics", "chess", "games",
          "counter-strike", "league-of-legends", "dota-2", "valorant", "rugby", "atp", "wta", "pga", "nascar", "cycling"}
POLITICS = {"politics", "elections", "us-politics", "us-election", "us-elections", "world-elections", "global-elections",
            "geopolitics", "trump", "trump-presidency", "biden", "congress", "senate", "house", "supreme-court", "primaries",
            "us-presidential-election", "world-politics", "foreign-policy", "ukraine", "israel", "middle-east", "china",
            "russia", "iran", "parliamentary-elections", "presidential-election", "mayoral-elections", "governor",
            "eu", "europe", "world", "world-affairs", "uptspt-politics", "potus", "tariffs", "trade-war", "courts",
            "court-cases", "2024-presidential-election", "deprec-us-election", "nyc-mayor", "mayor"}
CATS = ["sports", "politics", "crypto", "other"]
EPOCH = pd.Timestamp("1970-01-01", tz="UTC")


def category(slugs: str | None) -> str:
    s = set((slugs or "").split("|")) - {""}
    if s & CRYPTO:
        return "crypto"
    if s & SPORTS:
        return "sports"
    if s & POLITICS:
        return "politics"
    return "other"


def ts(v) -> int:
    if v is None or (isinstance(v, float) and np.isnan(v)) or v == "":
        return 0
    t = pd.to_datetime(v, utc=True, errors="coerce")
    return 0 if pd.isna(t) else int(t.timestamp())


def tsv(s: pd.Series) -> pd.Series:
    """Vectorised unix seconds (0 if missing/unparseable). Gamma mixes '2025-06-10 18:04:16+00' and ISO 'Z' forms."""
    t = pd.to_datetime(s, utc=True, errors="coerce", format="mixed")
    sec = (t - EPOCH) // pd.Timedelta("1s")
    return sec.where(t.notna(), 0).fillna(0).astype("int64")


def main():
    ta = pd.read_parquet(OUT / "traded_assets.parquet")
    mk = pd.read_parquet(OUT / "gamma_markets_traded.parquet")
    tm = pd.read_parquet(OUT / "token_meta.parquet")
    ca = pd.read_parquet(OUT / "ch_assets.parquet")
    checks = {}
    mk = mk.drop_duplicates("conditionId")
    mk["category"] = mk.tag_slugs.map(category)
    mk["t_closed"] = tsv(mk.closedTime)
    mk["t_uma"] = tsv(mk.umaEndDate)
    mk["event_key"] = mk.event_id.where(mk.event_id.notna() & (mk.event_id != "None"), "c:" + mk.conditionId)
    # underlying event: Gamma splits some sports games into several events ("<game>-more-markets", "-v2",
    # "-spreads-totals", cricket props ...). Sports events whose slug starts with "<...>-YYYY-MM-DD" are keyed by that
    # prefix so one game = one underlying event (pre-registration addendum A6). Everything else: Gamma event id.
    pre = mk.event_slug.fillna("").str.extract(r"^(.*?\d{4}-\d{2}-\d{2})")[0]
    mk["underlying_key"] = mk.event_key.where(~((mk.category == "sports") & pre.notna()), "g:" + pre.fillna(""))
    tm = tm.merge(mk[["id", "conditionId", "closed", "category", "t_closed", "t_uma", "event_key", "event_slug", "event_title",
                      "question", "umaResolutionStatus", "negRisk", "endDate", "underlying_key"]].rename(columns={"id": "market_id_g"}),
                  left_on="condition_id", right_on="conditionId", how="left")
    tm["payout_f"] = pd.to_numeric(tm.payout_raw, errors="coerce")
    clean_tok = tm.closed.fillna(False).astype(bool) & ((tm.payout_f - 1).abs() < 1e-3) | (tm.closed.fillna(False).astype(bool) & (tm.payout_f.abs() < 1e-3))
    tm["p_tok"] = np.where(clean_tok, np.where(tm.payout_f > 0.5, 1, 0), -1)
    # a market is clean only if all its tokens are clean and exactly one pays 1
    tm["_clean"] = (tm.p_tok >= 0).astype(int); tm["_win"] = (tm.p_tok == 1).astype(int)
    g = tm.groupby("condition_id").agg(n_tok=("token_id", "size"), n_clean=("_clean", "sum"), n_win=("_win", "sum"))
    g["market_clean"] = (g.n_clean == g.n_tok) & (g.n_win == 1)
    tm = tm.merge(g[["market_clean"]], left_on="condition_id", right_index=True, how="left")
    tm["p"] = np.where(tm.market_clean, tm.p_tok, -1)
    ca = ca.rename(columns={"token_id": "token_id_ch"})
    tm = tm.merge(ca, left_on="token_id", right_on="token_id_ch", how="left")
    tm["r"] = np.where(tm.t_closed > 0, tm.t_closed, np.where(tm.t_uma > 0, tm.t_uma,
                       np.where(tm.ch_closed_ts.fillna(0) > 0, tm.ch_closed_ts.fillna(0), 0))).astype("int64")
    tm["r_source"] = np.where(tm.t_closed > 0, "closedTime", np.where(tm.t_uma > 0, "umaEndDate",
                              np.where(tm.ch_closed_ts.fillna(0) > 0, "ch_assets", "none")))
    # attach traded stats
    ta["token_id"] = ta.token_id.astype(str)
    tok = ta.merge(tm, on="token_id", how="left")
    tok["has_meta"] = tok.condition_id.notna()
    tok["r"] = tok.r.fillna(0).astype("int64")
    tok["k"] = tok.token_id.str[-18:].astype("uint64")
    assert tok.k.is_unique, "18-digit key collision"
    # coverage numbers
    checks["traded_tokens"] = int(len(tok))
    checks["traded_tokens_with_gamma_meta"] = int(tok.has_meta.sum())
    checks["vol_legs_total"] = float(tok.vol_legs.sum())
    checks["vol_share_with_meta"] = float(tok.loc[tok.has_meta, "vol_legs"].sum() / tok.vol_legs.sum())
    checks["fills_share_with_meta"] = float(tok.loc[tok.has_meta, "n_fills"].sum() / tok.n_fills.sum())
    checks["vol_share_clean_payout"] = float(tok.loc[tok.p >= 0, "vol_legs"].sum() / tok.vol_legs.sum())
    checks["tokens_by_payout_class"] = tok.p.fillna(-9).astype(int).value_counts().to_dict()
    checks["r_source_counts"] = tok.r_source.fillna("no_meta").value_counts().to_dict()
    # fills after t_res (resolution-known time should not precede trading)
    tt = tok[(tok.p >= 0) & (tok.r > 0)].copy()
    lag = (tt.t_last - EPOCH) // pd.Timedelta("1s") - tt.r
    checks["clean_tokens"] = int(len(tt))
    checks["share_last_fill_after_tres_gt_1h"] = float((lag > 3600).mean())
    checks["share_last_fill_after_tres_gt_1d"] = float((lag > 86400).mean())
    checks["vol_share_last_fill_after_tres_gt_1d"] = float(tt.loc[lag > 86400, "vol_legs"].sum() / tt.vol_legs.sum())
    # cross-check vs CryptoHouse assets where both exist
    both = tok[tok.ch_outcome_price.notna() & (tok.p >= 0)]
    checks["xcheck_n"] = int(len(both))
    checks["xcheck_payout_agree"] = float(((both.ch_outcome_price - both.p).abs() < 1e-3).mean())
    d = (both.ch_closed_ts - both.r).abs()
    checks["xcheck_closed_abs_diff_le_1h"] = float((d <= 3600).mean())
    checks["xcheck_closed_abs_diff_le_1d"] = float((d <= 86400).mean())
    checks["xcheck_closed_median_diff_s"] = float((both.ch_closed_ts - both.r).median())
    # category
    tok["category"] = tok.category.fillna("other")
    checks["vol_share_by_category"] = (tok.groupby("category").vol_legs.sum() / tok.vol_legs.sum()).to_dict()
    # indices
    tok["c_idx"] = pd.factorize(tok.condition_id.fillna("none:" + tok.token_id))[0].astype("int64")
    tok["e_idx"] = pd.factorize(tok.underlying_key.fillna("none:" + tok.token_id))[0].astype("int64")
    checks["gamma_events_traded"] = int(tok.event_key.nunique())
    checks["underlying_events_traded"] = int(tok.underlying_key.nunique())
    tok["cat_idx"] = tok.category.map({c: i for i, c in enumerate(CATS)}).astype("int64")
    tok["p"] = tok.p.fillna(-1).astype("int64")
    keep = tok[tok.has_meta]
    ext = keep[["k", "c_idx", "e_idx", "p", "r", "cat_idx"]]
    with open(OUT / "meta_ext.tsv", "w") as fh:
        for r in ext.itertuples(index=False):
            fh.write(f"{r.k}\t{r.c_idx}\t{r.e_idx}\t{r.p}\t{r.r}\t{r.cat_idx}\n")
    cols = ["token_id", "k", "condition_id", "c_idx", "event_key", "underlying_key", "e_idx", "event_slug", "event_title", "question", "outcome",
            "outcome_index", "payout_raw", "p", "market_clean", "r", "r_source", "t_closed", "t_uma", "ch_closed_ts",
            "umaResolutionStatus", "negRisk", "endDate", "category", "cat_idx", "n_fills", "vol_legs", "t_first", "t_last", "has_meta"]
    out = tok[cols].copy()
    for c in ["event_slug", "event_title", "question", "outcome", "payout_raw", "umaResolutionStatus", "endDate", "event_key",
              "condition_id", "underlying_key"]:
        out[c] = out[c].astype("string")
    out["negRisk"] = out.negRisk.astype("boolean")
    out["market_clean"] = out.market_clean.astype("boolean")
    out.to_parquet(OUT / "token_meta_pit.parquet", index=False)
    mm = mk[["id", "conditionId", "question", "slug", "event_key", "underlying_key", "event_slug", "event_title", "category", "tag_slugs", "closed",
             "closedTime", "umaEndDate", "umaResolutionStatus", "outcomePrices", "negRisk", "endDate", "startDate", "feeType"]]
    mm.astype({c: "string" for c in mm.columns if mm[c].dtype == object}).to_parquet(OUT / "market_meta.parquet", index=False)
    (OUT / "meta_checks.json").write_text(json.dumps(checks, indent=1, default=str))
    print(json.dumps(checks, indent=1, default=str))


if __name__ == "__main__":
    main()
