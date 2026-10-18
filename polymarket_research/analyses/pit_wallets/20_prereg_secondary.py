"""Stage 2, step 20: pre-registered secondary metrics at the primary model ($100 per signal, first print at t + 2 min
+ 0.01, hold, historical fee): monthly P&L by resolution month, max drawdown of cumulative P&L (realised at t_res),
share of P&L from the top 1% of signals, made-money rate, and the delay decay of the hit/edge.
Run from polymarket_research/:  python analyses/pit_wallets/20_prereg_secondary.py
Output: data/derived/pit_wallets/results/prereg_secondary.parquet
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from evalib import B1, RES, SCREENS, load_signals, roi_hold  # noqa: E402

s, _ = load_signals()
ok, roi, raw, e, t_in = roi_hold(s, "fp", "120", 0.0, "hist")
s = s.assign(ok=ok, pnl=100 * roi)
rows = []
for (t, sc, sp), g in s[s.ok].groupby(["stype", "screen", "split"]):
    if t not in ("P", "F1", "F2", "CL"):
        continue
    g = g.sort_values("r")
    cum = g.pnl.cumsum().values
    peak = np.maximum.accumulate(np.concatenate([[0.0], cum]))[1:]
    mon = g.groupby(pd.to_datetime(g.r, unit="s", utc=True).dt.strftime("%Y-%m")).pnl.sum()
    rows.append(dict(stype=t, screen=sc, split=sp, n=len(g), pnl=g.pnl.sum(), max_dd_usd=float(np.max(peak - cum)),
                     months=len(mon), pos_months=int((mon > 0).sum()), worst_month=float(mon.min()),
                     best_month=float(mon.max())))
d = pd.DataFrame(rows)
d.to_parquet(RES / "prereg_secondary.parquet", index=False)
x = d[(d.split == "test") & (d.stype == "P")]
print(x.round(0).to_string(index=False))
print(d[(d.split == "test") & (d.stype != "P")][["stype", "screen", "n", "pnl", "max_dd_usd", "pos_months", "months"]].round(0).to_string(index=False))
