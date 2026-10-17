"""Capacity of the persistent k-of-n ALL_NO sets at $5k / $25k / $100k of committed capital - read-only, offline.

Run from polymarket_research/:  python -m analyses.logical_arb.09_capacity <tag> <books_dir> <event_id> [...]
Uses every snapshot in data/derived/<books_dir>/ ; per snapshot walks the joint NO ladders (1 - YES bid) of all
legs with equal shares, taker fees per leg from the market feeSchedule, and stops at the capital cap or when
the marginal set cost reaches the payoff bound (n_legs - k). Reports the median over snapshots.
This is a single-opportunity capacity: it assumes nobody else takes the bids first and ignores leg risk.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TAG, BOOKS, EIDS = sys.argv[1], sys.argv[2], sys.argv[3:]
K = {"531533": 5, "801515": 2, "904908": 3, "1188161": 5, "956300": 2, "904911": 3, "1188310": 5, "1188311": 5}
CAPS = [5_000, 25_000, 100_000]
M = pd.read_parquet(ROOT / "data" / "derived" / f"la_markets_{TAG}.parquet",
                    columns=["id", "event_id", "fee_rate", "fee_exponent", "feesEnabled", "acceptingOrders", "outcomes"])
M["id"], M["event_id"] = M.id.astype(str), M.event_id.astype(str)
M = M[M.acceptingOrders.eq(True) & M.outcomes.eq('["Yes", "No"]')]


def walk(lads, rates, expos, payoff, cap):
    pos, left = [0] * len(lads), [lad[0][1] for lad in lads]
    q = cost = 0.0
    while True:
        px = [lads[i][pos[i]][0] for i in range(len(lads))]
        mc = sum(p + r * (p * (1 - p)) ** e for p, r, e in zip(px, rates, expos))
        if mc >= payoff or cost >= cap:
            break
        take = min(min(left), (cap - cost) / mc)
        q, cost = q + take, cost + take * mc
        for i in range(len(lads)):
            left[i] -= take
            if left[i] <= 1e-9:
                pos[i] += 1
                if pos[i] >= len(lads[i]):
                    return q, cost
                left[i] = lads[i][pos[i]][1]
    return q, cost


rows = []
for sp in sorted(glob.glob(str(ROOT / "data" / "derived" / BOOKS / "snap_*.parquet"))):
    B = pd.read_parquet(sp, columns=["mid", "bids", "snap_utc"], filters=[("mid", "in", list(M[M.event_id.isin(EIDS)].id))])
    B = B.drop_duplicates("mid").set_index("mid")
    for eid in EIDS:
        g = M[(M.event_id == eid) & M.id.isin(B.index)]
        lads = [[(round(1 - p, 6), s) for p, s in json.loads(B.loc[i, "bids"])] for i in g.id]
        keep = [j for j, lad in enumerate(lads) if lad]
        if not keep:
            continue
        g = g.iloc[keep]
        lads = [lads[j] for j in keep]
        rates = np.where(g.feesEnabled == False, 0.0, g.fee_rate.fillna(0.05)).tolist()  # noqa: E712
        expos = g.fee_exponent.fillna(1.0).tolist()
        pay = len(lads) - K[eid]
        for cap in CAPS + [1e12]:
            q, cost = walk(lads, rates, expos, pay, cap)
            rows.append({"snap": B.snap_utc.iloc[0], "event_id": eid, "cap": cap, "sets": q, "capital": cost,
                         "profit": q * pay - cost})
R = pd.DataFrame(rows)
R.to_parquet(ROOT / "data" / "derived" / f"la_capacity_{TAG}_{BOOKS}.parquet", index=False)
S = R.groupby(["event_id", "cap"]).agg(snaps=("snap", "nunique"), med_capital=("capital", "median"),
                                       med_profit=("profit", "median"), min_profit=("profit", "min")).reset_index()
S["ret_pct"] = S.med_profit / S.med_capital * 100
print(S.to_string(index=False))
