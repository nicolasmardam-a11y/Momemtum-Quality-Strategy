"""Summarise opportunities across snapshots: persistence, size, timing flags, capital lock-up.

Run from polymarket_research/:  python -m analyses.logical_arb.05_summarize [date] [tag]
Input : data/derived/la_opps_<date>_<tag>.parquet
Output: data/derived/la_opps_summary_<date>_<tag>.parquet (one row per distinct relation) + printed tables
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-17"
TAG = sys.argv[2] if len(sys.argv) > 2 else "all"
pd.set_option("display.width", 280)
pd.set_option("display.max_colwidth", 70)

O = pd.read_parquet(ROOT / "data" / "derived" / f"la_opps_{DATE}_{TAG}.parquet")
snaps = sorted(O.snap_k.unique()) if len(O) else []
allk = pd.read_parquet(ROOT / "data" / "derived" / f"la_opps_{DATE}_{TAG}.parquet", columns=["snap_utc"]).snap_utc.unique()
O["snap_utc"] = pd.to_datetime(O.snap_utc, utc=True)
for leg in ("a", "b"):
    O[f"gst_{leg}"] = pd.to_datetime(O[f"gst_{leg}"], utc=True, errors="coerce", format="ISO8601")
    O[f"end_{leg}"] = pd.to_datetime(O[f"end_{leg}"], utc=True, errors="coerce", format="ISO8601")
gst = O[["gst_a", "gst_b"]].min(axis=1)
O["hrs_since_start"] = (O.snap_utc - gst).dt.total_seconds() / 3600
O["timing"] = np.select([O.hrs_since_start > 4, O.hrs_since_start >= 0], ["stale_game", "in_play"], "pre_game")
O.loc[gst.isna(), "timing"] = "no_game"
# capital lock: later of the two legs' end dates (sports: game start + 3h play + ~2h UMA liveness)
lock_end = O[["end_a", "end_b"]].max(axis=1)
lock_end = np.where(gst.notna(), gst + pd.Timedelta(hours=5), lock_end)
O["lock_days"] = np.maximum((pd.to_datetime(lock_end, utc=True) - O.snap_utc).dt.total_seconds() / 86400, 0.25)
O["edge_pct"] = O.profit / O.cost.replace(0, np.nan) * 100
O["ok_size"] = O.shares >= O.min_size
O["ret_per_day_pct"] = O.edge_pct / O.lock_days

order = {u: i for i, u in enumerate(sorted(pd.to_datetime(pd.Series(allk), utc=True).unique()))}
O["si"] = O.snap_utc.map(order)
nsnap = len(order)


def max_run(idx):
    s = sorted(set(idx))
    best = cur = 1
    for x, y in zip(s, s[1:]):
        cur = cur + 1 if y == x + 1 else 1
        best = max(best, cur)
    return best if s else 0


g = O[O.ok_size].groupby("rel_id")
S = g.agg(family=("family", "first"), note=("note", "first"), q_a=("q_a", "first"), out_a=("out_a", "first"),
          q_b=("q_b", "first"), out_b=("out_b", "first"), ev_a=("ev_a", "first"), ev_b=("ev_b", "first"),
          key=("key", "first"), timing=("timing", lambda x: ",".join(sorted(set(x)))),
          n_snaps=("si", "nunique"), first=("si", "min"), last=("si", "max"),
          med_cost=("top_cost", "median"), med_shares=("shares", "median"), med_profit=("profit", "median"),
          max_profit=("profit", "max"), med_profit_995=("profit_995", "median"), med_profit_sens=("profit_sens", "median"),
          med_edge_pct=("edge_pct", "median"), lock_days=("lock_days", "median"),
          ret_day=("ret_per_day_pct", "median"), cancel_payoff=("cancel_payoff", "first"),
          gap_s=("fetch_gap_s", "max"), smt_a=("smt_a", "first"), smt_b=("smt_b", "first"))
S["max_run"] = g.si.agg(max_run)
S["persistent"] = S.max_run >= 2
S.to_parquet(ROOT / "data" / "derived" / f"la_opps_summary_{DATE}_{TAG}.parquet")
print("snapshots in run:", nsnap, "| relation-snapshot rows:", len(O), "| with >= min size:", int(O.ok_size.sum()))
print("distinct relations:", len(S), "| persistent (>=2 consecutive):", int(S.persistent.sum()))
print("\nby family x timing (distinct relations; persistent; median edge %)")
print(S.groupby(["family", "timing"]).agg(n=("n_snaps", "size"), persistent=("persistent", "sum"),
                                         med_edge=("med_edge_pct", "median"),
                                         sum_med_profit=("med_profit", "sum")).to_string())
per_snap = O[O.ok_size].groupby(["si", "timing"]).agg(n=("rel_id", "nunique"), profit=("profit", "sum")).unstack(fill_value=0)
print("\nper snapshot (distinct relations, summed depth-limited profit $; relations overlap so sums overstate)")
print(per_snap.to_string())
cols = ["family", "timing", "q_a", "out_a", "q_b", "out_b", "n_snaps", "max_run", "med_cost", "med_shares",
        "med_profit", "med_profit_995", "med_profit_sens", "med_edge_pct", "lock_days", "ret_day", "cancel_payoff"]
print("\nTop persistent pre-game / non-game relations by median profit")
P = S[S.persistent & S.timing.isin(["pre_game", "no_game"])].sort_values("med_profit", ascending=False)
print(P[cols].head(60).to_string())
