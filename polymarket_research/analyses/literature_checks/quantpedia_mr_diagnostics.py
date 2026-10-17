"""Diagnostics for the Vojtko & Dujava (2026) rolling-minimum backtest replication.

1. Cost sensitivity: clean series, 1-bar entry lag, per-side cost 0 / 0.1% / 0.25% / 0.5% / 0.6%.
2. Drift control: mean signal-trade return vs. the mean Y-day forward return of ALL bars
   (an entry at a random time), i.e. how much of the trade P&L is the No-side drift toward $1
   that is only known in hindsight because all three contracts resolved No.
3. Random-entry placebo: same number of non-overlapping Y-day trades at random times (500 draws).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from quantpedia_mr_replicate import load, clean, backtest, metrics  # noqa: E402

rng = np.random.default_rng(7)
rows = []
for name in ["jesus", "china", "alien"]:
    s = clean(load(name))
    t = s.index.values
    p = s.values
    for X, Y in [(5, 1), (10, 5), (20, 5)]:
        res = {"contract": name, "X": X, "Y": Y}
        for fee in [0.0, 0.001, 0.0025, 0.005, 0.006]:
            eq, tr = backtest(s, X, Y, fee, lag=1)
            m = metrics(eq)
            res[f"CAR_fee{fee*100:g}%"] = round(100 * m["CAR"], 2)
            res[f"Sharpe_fee{fee*100:g}%"] = round(m["Sharpe"], 2)
        eq, tr = backtest(s, X, Y, 0.0, lag=1)
        tr = pd.DataFrame(tr)
        j = np.searchsorted(t, t + np.timedelta64(Y, "D"))
        ok = j < len(p)
        fwd = p[j[ok]] / p[ok] - 1
        res["n_trades"] = len(tr)
        res["mean_trade_ret_%"] = round(100 * tr["ret"].mean(), 3)
        res["mean_all_bar_fwd_ret_%"] = round(100 * fwd.mean(), 3)
        res["share_trades_positive"] = round((tr["ret"] > 0).mean(), 2)
        days_in = ((tr["exit_time"] - tr["entry_time"]).dt.total_seconds().sum() / 86400)
        res["time_in_market"] = round(days_in / ((s.index[-1] - s.index[0]).total_seconds() / 86400), 2)
        # random-entry placebo with same count of non-overlapping Y-day trades
        n = len(tr)
        tot = []
        cand = np.where(ok)[0]
        for _ in range(500):
            starts = np.sort(rng.choice(cand, size=min(n * 3, len(cand)), replace=False))
            sel, last_exit = [], -1
            for i0 in starts:
                if i0 > last_exit:
                    sel.append(i0)
                    last_exit = j[i0]
                if len(sel) == n:
                    break
            r = p[j[sel]] / p[sel] - 1
            tot.append(np.prod(1 + r) - 1)
        strat_tot = np.prod(1 + tr["ret"].values) - 1
        res["strategy_total_ret_%"] = round(100 * strat_tot, 2)
        res["placebo_total_ret_median_%"] = round(100 * np.median(tot), 2)
        res["placebo_p_ge_strategy"] = round(float(np.mean(np.array(tot) >= strat_tot)), 3)
        rows.append(res)
out = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(out.T.to_string())
out.to_csv(Path(__file__).resolve().parents[2] / "data/derived/literature_checks/qp_mr_diagnostics.csv", index=False)
