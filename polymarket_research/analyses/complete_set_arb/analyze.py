"""Summarise the complete-set arbitrage scans written by collect.py (no network access).

Run from polymarket_research/:  python -m analyses.complete_set_arb.analyze
Writes data/derived/complete_set_arb_events.parquet (one row per distinct candidate (id, type))
and data/derived/complete_set_arb_scan_summary.parquet (one row per full scan), and prints the tables
used in notes/strategies/complete_set_arb.md.
"""
from __future__ import annotations

import glob
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "derived" / "complete_set_arb"
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_colwidth", 70)

# Pre-registered artefact flags (section 1.2). "stale_gt5min" was pre-registered as "possibly stale"; the CLOB book
# `timestamp` turned out to be the last-change time of the book (REST data itself is fetched fresh), so results are
# reported both strictly (all flags) and relaxed (stale flag ignored).
PRE_FLAGS = {"not_tradable", "crossed_book", "seconds_delay", "game_started", "resolution_pending", "missing_book", "stale_gt5min"}
RELAXED_FLAGS = PRE_FLAGS - {"stale_gt5min"}


def load(pattern):
    fs = sorted(glob.glob(str(D / pattern)))
    out = []
    for f in fs:
        x = pd.read_parquet(f)
        m = re.search(r"(?:scan|cand)_(\d+)", Path(f).name)
        if m and "scan_id" not in x:
            x["scan_id"] = int(m.group(1))
        out.append(x)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def metric(row, key):
    m = json.loads(row["metrics"]) if isinstance(row["metrics"], str) else {}
    v = m.get(key)
    try:
        return float(v)
    except (TypeError, ValueError):
        return math.nan


def main():
    groups = load("scan_*_groups.parquet")
    binary = load("scan_*_binary.parquet")
    members = load("scan_*_members.parquet")
    cands = load("cand_*.parquet")
    print("full neg-risk scans:", groups.scan_id.nunique(), " binary scans:", binary.scan_id.nunique() if len(binary) else 0)
    print("first/last scan:", groups.fetched_at.min(), groups.fetched_at.max())

    # ---------------------------------------------------------------- per-scan summary
    g2 = groups[groups.n_trad >= 2].copy()
    summ = g2.groupby("scan_id").agg(
        groups=("nr_id", "size"), exhaustive=("exhaustive", "sum"),
        d_pos=("d_edge0", lambda s: int((s > 0).sum())), e_pos=("e_edge0", lambda s: int((s > 0).sum())),
        d_within_10bp=("d_edge0", lambda s: int((s > -0.001).sum())), d_within_50bp=("d_edge0", lambda s: int((s > -0.005).sum())),
        d_best=("d_edge0", "max"), e_best=("e_edge0", "max"),
    )
    cx = g2[g2.exhaustive]
    summ = summ.join(cx.groupby("scan_id").agg(c_exh_pos=("c_edge0", lambda s: int((s > 0).sum())),
                                               c_exh_best=("c_edge0", "max"),
                                               c_exh_pos_100=("c_p100", lambda s: int((s > 0).sum()))))
    summ = summ.join(g2[~g2.exhaustive].groupby("scan_id").agg(c_nonexh_pos=("c_edge0", lambda s: int((s > 0).sum()))))
    if len(binary):
        bs = binary.groupby("scan_id").agg(binaries=("market_id", "size"), a_pos=("a_edge0", lambda s: int((s > 0).sum())),
                                           b_pos=("b_edge0", lambda s: int((s > 0).sum())), a_best=("a_edge0", "max"),
                                           crossed=("crossed0", lambda s: int(s.sum())),
                                           mirror_false=("mirror", lambda s: int((s == False).sum())))  # noqa: E712
        summ = summ.join(bs)
    print("\nPer-scan summary (edge0 = top-of-book net edge per set after taker fees):")
    print(summ.round(4).to_string())
    summ.reset_index().to_parquet(ROOT / "data" / "derived" / "complete_set_arb_scan_summary.parquet", index=False)

    # mirror check (members)
    if len(members):
        top_mirror = (np.isclose(members.bbY, 1 - members.baN) | (members.bbY.isna() & members.baN.isna()))
        print(f"\nneg-risk member books: {len(members)} obs; full-depth mirror True {int((members.mirror == True).sum())}, "  # noqa: E712
              f"False {int((members.mirror == False).sum())}; top-of-book YES bid == 1 - NO ask: {top_mirror.mean():.4%}")  # noqa: E712

    # ---------------------------------------------------------------- gross (pre-fee) vs net: the fee band
    if len(members):
        gs = members.groupby(["scan_id", "nr_id"]).agg(sbid=("bbY", lambda x: x.fillna(0).sum()),
                                                       sask=("baY", lambda x: x.fillna(np.inf).sum())).reset_index()
        gs = gs.merge(groups[["scan_id", "nr_id", "exhaustive", "d_edge0", "c_edge0", "event_title"]], on=["scan_id", "nr_id"])
        fb = gs.groupby("scan_id").agg(
            gross_sumbid_gt1=("sbid", lambda s: int((s > 1 + 1e-9).sum())),
            net_d_pos=("d_edge0", lambda s: int((s > 0).sum())),
            gross_sumask_lt1_exh=("sask", lambda s: int((s[gs.loc[s.index, "exhaustive"]] < 1 - 1e-9).sum())),
            net_c_pos_exh=("c_edge0", lambda s: int((s[gs.loc[s.index, "exhaustive"]] > 0).sum())),
            max_gross_sumbid=("sbid", "max"))
        print("\nFee band: groups with a gross (pre-fee) top-of-book violation vs net-of-fee violations, per scan:")
        print(fb.round(4).to_string())
        gx = gs[gs.sbid > 1 + 1e-9]
        print(f"distinct groups ever gross sum(bidYES) > 1: {gx.nr_id.nunique()}; of which ever net (d) > 0: "
              f"{gx[gx.d_edge0 > 0].nr_id.nunique()}; median gross excess {np.median(gx.sbid - 1) if len(gx) else float('nan'):.4f}, "
              f"median net edge {gx.d_edge0.median() if len(gx) else float('nan'):.4f}")
        fb.reset_index().to_parquet(ROOT / "data" / "derived" / "complete_set_arb_feeband.parquet", index=False)

    # ---------------------------------------------------------------- near-miss distribution of (d)
    print("\n(d)/(e) top-of-book edge distribution over all group-scans (n_trad>=2):")
    print(g2.d_edge0.describe(percentiles=[.5, .9, .99, .999]).round(5).to_string())

    # ---------------------------------------------------------------- distinct candidate events
    if not len(cands):
        print("no candidates")
        return
    cands["exhaustive"] = cands["exhaustive"].fillna(False).astype(bool) if "exhaustive" in cands else False
    cands["flagset"] = cands["flags"].fillna("").map(lambda s: set(x for x in s.split("|") if x))
    cands["valid_type"] = (cands.type != "c") | cands.exhaustive
    cands["t"] = pd.to_datetime(cands.fetched_at, utc=True, format="ISO8601")
    for k in ("qstar", "p100", "p1000", "p10000", "edge0", "depth"):
        cands[f"m_{k}"] = [metric(r, f"{r['type']}_{k}") for _, r in cands.iterrows()]
    cands["pos"] = cands.pmax.fillna(0) > 0
    # a candidate observation counts as "sized" if Q* >= min order size on legs (5 on almost all markets) and pmax >= $0.50
    cands["min_size"] = [max([l.get("min_size") or 5 for l in json.loads(r)] or [5]) for r in cands.legs]
    cands["sized"] = cands.pos & (cands.m_qstar >= cands.min_size) & (cands.pmax >= 0.5)
    v = cands[cands.valid_type]
    rows = []
    for (kind, cid, ty), x in v.groupby(["kind", "id", "type"]):
        x = x.sort_values("t")
        px = x[x.pos]
        if not len(px):
            continue
        first, last = px.t.min(), px.t.max()
        # persistence: positive on a re-fetch >= 30 s after first positive observation
        persistent = bool(((px.t - first).dt.total_seconds() >= 30).any())
        # first time it was observed non-positive after first positive
        later = x[x.t > first]
        gone = later[~later.pos]
        t_gone = (gone.t.min() - first).total_seconds() if len(gone) else math.nan
        fl = set().union(*px.flagset) if len(px) else set()
        rows.append({
            "kind": kind, "id": cid, "type": ty, "title": x.title.iloc[0], "event_slug": x.event_slug.iloc[0],
            "n_obs": len(x), "n_pos": len(px), "n_full_pos": int((px.obs_kind == "full").sum()),
            "first_pos": first, "last_pos": last, "pos_span_s": (last - first).total_seconds(),
            "first_gone_after_s": t_gone, "persistent": persistent,
            "max_pmax": px.pmax.max(), "med_pmax": px.pmax.median(), "max_qstar": px.m_qstar.max(),
            "max_edge0": px.m_edge0.max(), "max_p100": px.m_p100.max(), "max_p1000": px.m_p1000.max(),
            "max_p10000": px.m_p10000.max(), "sized_any": bool(px.sized.any()),
            "flags": "|".join(sorted(fl)), "flag_free": len(fl & PRE_FLAGS) == 0,
            "flag_free_relaxed": len(fl & RELAXED_FLAGS) == 0,
            "exhaustive": bool(x.exhaustive.iloc[0]),
        })
    ev = pd.DataFrame(rows)
    ev.to_parquet(ROOT / "data" / "derived" / "complete_set_arb_events.parquet", index=False)
    print(f"\nraw candidate observations: {len(cands)} (valid-type {len(v)}); distinct valid candidates: {len(ev)}")
    print("non-exhaustive (c) observations with positive edge (excluded):", int((~cands.valid_type & cands.pos).sum()),
          "distinct:", cands[~cands.valid_type & cands.pos].id.nunique())
    print(ev.groupby(["kind", "type"]).agg(n=("id", "size"), persistent=("persistent", "sum"), sized=("sized_any", "sum"),
                                           flag_free=("flag_free", "sum"), sum_maxp=("max_pmax", "sum")).to_string())
    cols = ["type", "title", "n_obs", "n_pos", "n_full_pos", "pos_span_s", "first_gone_after_s", "persistent", "max_pmax",
            "max_qstar", "max_edge0", "max_p100", "max_p1000", "sized_any", "flags"]
    print(ev.sort_values("max_pmax", ascending=False)[cols].head(40).round(4).to_string())
    surv = ev[ev.persistent & ev.sized_any & ev.flag_free & (ev.max_pmax >= 1.0)]
    print(f"\nsurviving per pre-registration (persistent, sized, flag-free, >= $1): {len(surv)}")
    print(surv[cols].round(4).to_string())
    surv_r = ev[ev.persistent & ev.sized_any & ev.flag_free_relaxed & (ev.max_pmax >= 1.0)]
    print(f"surviving with the stale flag relaxed: {len(surv_r)}")
    print(surv_r[cols].round(4).to_string())

    # ---------------------------------------------------------------- persistence curve for candidates first seen in a full scan
    print("\nPersistence: share of full-scan candidates (pmax > $0.01) still positive at each rescan index:")
    fullpos = v[(v.obs_kind == "full") & (v.pmax > 0.01)][["scan_id", "id", "type"]].drop_duplicates()
    rs = v[v.obs_kind == "rescan"].copy()
    if len(rs):
        rs["k"] = rs.groupby(["scan_id", "id", "type"]).cumcount() + 1
        mm = fullpos.merge(rs[["scan_id", "id", "type", "k", "pos", "t"]], on=["scan_id", "id", "type"])
        print(mm.groupby("k").pos.agg(["mean", "size"]).to_string())


def ws_summary():
    """Websocket episodes: merge flickers of the same (group, type) separated by < 2 s into bursts."""
    eps = load("ws_episodes_*.parquet")
    if not len(eps):
        print("no websocket episodes")
        return
    groups = load("scan_*_groups.parquet")
    fl = groups.sort_values("scan_id").groupby("nr_id")["flags"].agg(lambda s: "|".join(sorted(set("|".join(s.fillna("")).split("|")) - {""})))
    eps["flags"] = eps.gid.map(fl).fillna("")
    eps["inplay"] = eps["flags"].str.contains("game_started") | eps["flags"].str.contains("seconds_delay")
    eps = eps.sort_values(["run", "gid", "type", "start_ms"])
    eps["still_open"] = eps.get("still_open", False)
    eps["still_open"] = eps["still_open"].fillna(False).astype(bool)
    bursts = []
    for (run, gid, ty), x in eps.groupby(["run", "gid", "type"]):
        cur = None
        for r in x.to_dict("records"):
            end = r["end_ms"] if r["end_ms"] == r["end_ms"] and r["end_ms"] is not None else None
            if cur and end is not None and cur["end_ms"] is not None and r["start_ms"] - cur["end_ms"] < 2000:
                cur["end_ms"] = end
                cur["n_flickers"] += 1
                cur["max_pmax"] = max(cur["max_pmax"], r["max_pmax"])
                cur["max_qstar"] = max(cur["max_qstar"], r["max_qstar"])
                cur["max_edge0"] = max(cur["max_edge0"], r["max_edge0"])
                cur["crossed"] = cur["crossed"] or r["crossed"]
                continue
            if cur:
                bursts.append(cur)
            cur = {"run": run, "gid": gid, "type": ty, "title": r["title"], "start_ms": r["start_ms"], "end_ms": end,
                   "n_flickers": 1, "max_pmax": r["max_pmax"], "max_qstar": r["max_qstar"], "max_edge0": r["max_edge0"],
                   "crossed": r["crossed"], "inplay": r["inplay"], "flags": r["flags"], "still_open": r["still_open"],
                   "n_legs": r["n_legs"]}
        if cur:
            bursts.append(cur)
    b = pd.DataFrame(bursts)
    b["dur_s"] = (b.end_ms - b.start_ms) / 1000
    b.to_parquet(ROOT / "data" / "derived" / "complete_set_arb_ws_bursts.parquet", index=False)
    print(f"\nWebsocket: {len(eps)} raw episodes -> {len(b)} bursts (flickers < 2 s apart merged); runs {sorted(eps.run.unique())}")
    print(b.groupby(["type", "inplay"]).agg(n=("gid", "size"), groups=("gid", "nunique"), med_dur=("dur_s", "median"),
                                            p90_dur=("dur_s", lambda s: s.quantile(.9)), max_dur=("dur_s", "max"),
                                            sized=("max_pmax", lambda s: int((s >= 0.5).sum())),
                                            sum_maxp=("max_pmax", "sum"), crossed=("crossed", "sum"),
                                            still_open=("still_open", "sum")).round(3).to_string())
    print(b.sort_values("max_pmax", ascending=False).head(25)[
        ["type", "title", "n_legs", "n_flickers", "dur_s", "max_edge0", "max_pmax", "max_qstar", "crossed", "inplay", "still_open", "flags"]].round(3).to_string())
    ni = b[~b.inplay]
    print(f"\nnon-in-play bursts: {len(ni)} (distinct groups {ni.gid.nunique()})")
    if len(ni):
        print(ni[["type", "title", "n_legs", "n_flickers", "dur_s", "max_edge0", "max_pmax", "max_qstar", "still_open", "flags"]].round(4).to_string())


if __name__ == "__main__":
    main()
    ws_summary()
