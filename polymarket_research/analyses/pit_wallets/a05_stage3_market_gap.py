"""Stage 4 (audit), step a05: stage-3 markets missing from the market table, and their effect on the 2026 screens.

Stage 3 took market metadata from data/derived/markets_resolved.parquet = closed markets with endDate < 2026-10-16.
A market that resolved before D = 2026-06-01 (or before the 2026-10-15 evaluation cut) but carries a LATER endDate
(e.g. "... by 2026-12-31?" markets that resolved early) is therefore missing; stage 3 treated decisions on it as open
(not resolved). This script looks up every missing condition of the eval wallets' counted trailing decisions and of the
evaluation signals in Gamma (/markets/keyset?condition_ids=..., closed=true, then without closed), classifies them, and
recomputes the count-based screens (S1, S2) and the S3 edge sum with the corrected resolution status.
Point-in-time rule as pre-registered: a decision counts as resolved at D only if the market is clean (payout {1, 0})
and closedTime < D. Output: audit/a05_missing_markets.parquet, audit/a05_screen_fix.parquet; summary on stdout.
Run from polymarket_research/:  python analyses/pit_wallets/a05_stage3_market_gap.py
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
V = OUT / "v2"
T_D, T_RESCUT = 1780272000, 1792022400  # 2026-06-01, 2026-10-15


def lookup(cids: list[str]) -> pd.DataFrame:
    rows = []
    for closed in ("true", None):
        todo = [c for c in cids if c not in {r["condition_id"] for r in rows}]
        for i in range(0, len(todo), 50):
            p = {"condition_ids": todo[i:i + 50], "limit": 100}
            if closed:
                p["closed"] = closed
            for x in api.gamma_markets(cache=bool(closed), **p):
                op = json.loads(x.get("outcomePrices") or "[]")
                rows.append(dict(condition_id=x.get("conditionId"), closed=bool(x.get("closed")),
                                 closedTime=x.get("closedTime"), endDate=x.get("endDate"),
                                 uma=x.get("umaResolutionStatus"), pay0=float(op[0]) if op else np.nan,
                                 pay1=float(op[1]) if len(op) > 1 else np.nan, n_out=len(op)))
    g = pd.DataFrame(rows).drop_duplicates("condition_id")
    g["t_res_s"] = pd.to_datetime(g.closedTime, utc=True, errors="coerce", format="mixed")
    g["t_res_s"] = g.t_res_s.map(lambda x: int(x.timestamp()) if pd.notna(x) else 0)
    g["clean"] = g.closed & (g.n_out == 2) & (((g.pay0 == 1) & (g.pay1 == 0)) | ((g.pay0 == 0) & (g.pay1 == 1)))
    return g


def main():
    mk = set(pd.read_parquet(V / "markets_2026.parquet", columns=["condition_id"]).condition_id)
    sc = pd.read_parquet(V / "screens_D.parquet")
    d = pd.read_parquet(V / "decisions_trail.parquet")
    e = pd.read_parquet(V / "eval_signals.parquet", columns=["wallet", "ue", "t0", "condition_id", "outcome_index",
                                                            "S1", "S2", "S3", "S5", "B1", "evaluable"])
    elig = set(sc.loc[sc.eligible | sc.S1 | sc.S2 | sc.S3 | sc.S5, "wallet"])
    sub = set(sc.wallet)
    dm = d[d.counted & ~d.condition_id.isin(mk) & d.wallet.isin(sub)]
    em = e[~e.condition_id.isin(mk)]
    cids = sorted(set(dm.condition_id) | set(em.condition_id))
    g = lookup(cids)
    g.to_parquet(OUT / "audit" / "a05_missing_markets.parquet", index=False)
    found = set(g.condition_id)
    g["cls"] = np.select([~g.closed, g.clean & (g.t_res_s < T_D), g.clean & (g.t_res_s < T_RESCUT), g.clean],
                         ["open", "resolved<D", "resolved D..10-15", "resolved>=10-15"], "closed_unclean")
    print("missing conditions looked up", len(cids), "found", len(found), g.cls.value_counts().to_dict())
    # ---- trailing decisions with corrected resolution
    x = dm.merge(g[["condition_id", "cls", "clean", "t_res_s", "pay0", "pay1"]], on="condition_id", how="left",
                 suffixes=("", "_g"))
    x = x[(x.cls == "resolved<D")].copy()
    x["pay"] = np.where(x.outcome_index == 0, x.pay0, x.pay1)
    x["won"] = x.pay == 1
    add = x.groupby("wallet").agg(add_res=("won", "size"), add_won=("won", "sum"), add_edge=("vwap", lambda v: 0.0))
    x["edge"] = x.pay - x.vwap
    add["add_edge"] = x.groupby("wallet").edge.sum()
    add["add_pv"] = x.assign(pv=x.vwap * (1 - x.vwap)).groupby("wallet").pv.sum()
    w = sc.merge(add, left_on="wallet", right_index=True, how="left").fillna({"add_res": 0, "add_won": 0, "add_edge": 0,
                                                                            "add_pv": 0})
    w["n_res2"] = w.n_res + w.add_res; w["n_won2"] = w.n_won + w.add_won
    ok = ~w.heavy
    w["S1_fix"] = ok & (w.n_res2 == 5) & (w.n_won2 == 5)
    w["S2_fix"] = ok & (w.n_res2 >= 5) & (w.n_won2 == w.n_res2)
    se2, pv2 = w.sum_edge + w.add_edge, w.sum_pv + w.add_pv
    w["S3_fix"] = ok & (w.n_res2 >= 10) & (se2 > 0) & (se2 / np.sqrt(pv2 + 2.5) >= 2)
    for s in ["S1", "S2", "S3"]:
        a, b = w[s].astype(bool), w[f"{s}_fix"]
        print(f"{s}: members {int(a.sum())} -> corrected {int(b.sum())}; kept {int((a & b).sum())}, "
              f"dropped {int((a & ~b).sum())}, new {int((~a & b).sum())} (new ones in eval set: "
              f"{int((~a & b & w.wallet.isin(set(e.wallet))).sum())})")
    w[["wallet", "n_res", "n_won", "add_res", "add_won", "S1", "S1_fix", "S2", "S2_fix", "S3", "S3_fix"]].to_parquet(
        OUT / "audit" / "a05_screen_fix.parquet", index=False)
    # ---- evaluation signals excluded because their market was missing
    y = em.merge(g[["condition_id", "cls", "t_res_s"]], on="condition_id", how="left")
    y["should_be_evaluable"] = y.cls.isin(["resolved<D", "resolved D..10-15"]) & (y.t_res_s > y.t0)
    for s in ["S1", "S2", "S3", "S5", "B1"]:
        z = y[y[s].fillna(False).astype(bool)]
        tot = int(e[s].fillna(False).astype(bool).sum())
        print(f"  eval {s}: missing-market signals {len(z)} of {tot}; should have been evaluable {int(z.should_be_evaluable.sum())}")


if __name__ == "__main__":
    main()
