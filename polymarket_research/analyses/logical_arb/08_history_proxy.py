"""Persistence proxy for k-of-n sets: sum over listed markets of the CLOB /prices-history price (hourly), last N days.

Run from polymarket_research/:  python -m analyses.logical_arb.08_history_proxy <tag> <event_id> [<event_id> ...]
NOT executable prices: /prices-history is a trade/mid series, not bid/ask or depth (CONTEXT.md). A sum above k only
says the set looked over-priced at mid; the live, executable test is 06_count_sets on CLOB books.
Output: data/derived/la_hist_proxy_<event_id>.parquet (hour, n_with_price, sum_price)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

TAG, EIDS = sys.argv[1], sys.argv[2:]
DAYS = 30
M = pd.read_parquet(ROOT / "data" / "derived" / f"la_markets_{TAG}.parquet", columns=["id", "event_id", "clobTokenIds", "groupItemTitle"])
M["event_id"] = M.event_id.astype(str)
end = int(time.time())
start = end - DAYS * 86400
for eid in EIDS:
    g = M[M.event_id == eid]
    rows = []
    for r in g.itertuples():
        tok = json.loads(r.clobTokenIds)[0]
        h = []
        for s0 in range(start, end, 7 * 86400):  # the endpoint rejects long intervals ('interval is too long')
            h += api.prices_history(tok, s0, min(s0 + 7 * 86400, end), fidelity_min=60, cache=False)
        rows += [{"mid": str(r.id), "name": r.groupItemTitle, "t": x["t"], "p": x["p"]} for x in h]
    H = pd.DataFrame(rows)
    H["hour"] = pd.to_datetime(H.t, unit="s", utc=True).dt.floor("h")
    # forward-fill each market's last price on an hourly grid so a quiet market keeps its last value
    P = H.pivot_table(index="hour", columns="mid", values="p", aggfunc="last").sort_index().ffill()
    out = pd.DataFrame({"n_with_price": P.notna().sum(axis=1), "sum_price": P.sum(axis=1)})
    out.to_parquet(ROOT / "data" / "derived" / f"la_hist_proxy_{eid}.parquet")
    full = out[out.n_with_price == len(g)]
    d = full.resample("D").sum_price.median() if len(full) else pd.Series(dtype=float)
    print(eid, "markets", len(g), "hours", len(out), "hours with all markets priced", len(full),
          "| sum_price min/median/max", round(full.sum_price.min(), 3) if len(full) else None,
          round(full.sum_price.median(), 3) if len(full) else None, round(full.sum_price.max(), 3) if len(full) else None)
    print("   daily median sum:", " ".join(f"{i:%m-%d}:{v:.2f}" for i, v in d.dropna().items()))
