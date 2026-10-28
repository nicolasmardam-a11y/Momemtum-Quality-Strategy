"""Strategy D (post-holdout, exploratory): go LONG run-up stocks.

    python scripts/strategy_d_long_ramps.py

Question: since the run-up names that do not crash keep rising, can buying
them, especially the ones the model rates low crash risk, make money?

This idea was added AFTER the holdout was opened, so the holdout cannot
validate it. Only development OOS (2016-2022) and validation (2023-2024H1)
predictions are used. It is not part of the pre-registered verdict.

Design: candidate (run-up state) stock-days split into terciles of Model D's
out-of-sample crash probability, ranked within each walk-forward fold (no
look-ahead in the cut-offs beyond the fold itself). Buy at the t+1 open with
the same engine, costs, lots, ticks and participation caps as Strategy A;
hold 20 trading days, 30% stop on the close executed next open.

Spread scenarios: "estimated" uses max(half tick, Abdi-Ranaldo/2), as in all
other backtests. "tick_only" sets the estimated spread to zero, so only half
a tick is paid: an optimistic lower bound, because the Abdi-Ranaldo
estimator tends to overstate spreads in very volatile stocks.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from hkrd import pipeline as P  # noqa: E402
from hkrd import validation as V  # noqa: E402
from hkrd.backtest import EventBacktester, TradeRules, perf_stats, trade_stats  # noqa: E402
from hkrd.config import load_config  # noqa: E402
from hkrd.runners import build_market, exec_from_cfg, short_from_cfg  # noqa: E402

log = logging.getLogger("strategy_d")
PERIODS = {"development_oos": ("2016-01-01", "2022-12-31"), "validation": ("2023-01-01", "2024-06-30")}
GROUPS = {"low_risk_30pct": (0.0, 0.3), "all_candidates": (0.0, 1.0), "high_risk_30pct": (0.7, 1.0)}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cfg = load_config()
    inp = P.load_inputs(cfg)
    df = pd.read_parquet(cfg.path("store_dir") / "dataset.parquet",
                         columns=["date", "code", "candidate", "spread_ar_20", "fwd_ret_open_20"])
    preds = pd.read_parquet(cfg.path("store_dir") / "oos_predictions.parquet",
                            columns=["date", "code", "fold", "p__D_two_stage__dd20_40"])
    markets = {"estimated": build_market(cfg, inp, df),
               "tick_only": build_market(cfg, inp, df.assign(spread_ar_20=0.0))}
    M = preds.merge(df, on=["date", "code"])
    M = M[M["candidate"]].copy()
    M["risk_rank"] = M.groupby("fold")["p__D_two_stage__dd20_40"].rank(pct=True)

    rows = []
    for label, (lo_q, hi_q) in GROUPS.items():
        g = M[(M["risk_rank"] > lo_q) & (M["risk_rank"] <= hi_q)] if lo_q > 0 else M[M["risk_rank"] <= hi_q]
        for per, (lo, hi) in PERIODS.items():
            s = g[(g["date"] >= lo) & (g["date"] <= hi)]
            sig = s[["date", "code"]].assign(score=-s["p__D_two_stage__dd20_40"].to_numpy())
            for spread, part in (("estimated", 0.02), ("estimated", 0.05), ("tick_only", 0.02)):
                bt = EventBacktester(markets[spread], TradeRules(side="long", hold_days=20, stop_loss=0.30, nav=50e6),
                                     exec_from_cfg(cfg, participation=part), short_from_cfg(cfg), seed=0)
                res = bt.run(sig)
                tr = res["trades"]
                st = trade_stats(tr)
                bs = V.event_bootstrap(tr["net_ret"], tr["code"]) if len(tr) else {}
                d = res["daily"].loc[lo:hi]
                rows.append({
                    "signal": label, "period": per, "spread": spread, "participation": part,
                    "paper_mean_open_to_20d": s["fwd_ret_open_20"].mean(),
                    "paper_median_open_to_20d": s["fwd_ret_open_20"].median(),
                    "trades": st.get("n_trades", 0), "stocks": st.get("n_stocks", 0),
                    "mean_gross_ret": float((tr["gross_pnl"] / tr["notional"]).mean()) if len(tr) else None,
                    "mean_explicit_cost": float(((tr["entry_costs"] + tr["exit_costs"]) / tr["notional"]).mean())
                    if len(tr) else None,
                    "mean_net_ret": st.get("mean_net_ret"), "median_net_ret": st.get("median_net_ret"),
                    "boot_ci05": bs.get("ci_05"), "boot_ci95": bs.get("ci_95"),
                    "win_rate": st.get("win_rate"), "exit_reasons": st.get("exit_reasons"),
                    "sharpe": perf_stats(d["ret"]).get("sharpe"),
                    "avg_gross_deployed_hkd": float(d["gross_exposure"].mean()),
                })
                log.info("%s %s %s p=%.2f trades=%s mean_net=%s", label, per, spread, part, st.get("n_trades"),
                         st.get("mean_net_ret"))
    out = cfg.path("outputs_dir") / "post_holdout"
    out.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "strategy_d_long_ramps.csv", index=False)


if __name__ == "__main__":
    main()
