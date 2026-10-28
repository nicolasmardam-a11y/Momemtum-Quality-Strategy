"""Strategy backtests on out-of-sample predictions (development folds + validation).

    python scripts/run_backtests.py

Uses only walk-forward predictions written by run_research.py. The holdout
is not touched. Configuration selection follows config/go_no_go.yaml.
"""
from __future__ import annotations

import logging
import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from hkrd import pipeline as P  # noqa: E402
from hkrd import plots  # noqa: E402
from hkrd import strategies as S  # noqa: E402
from hkrd import validation as V  # noqa: E402
from hkrd.config import load_config  # noqa: E402
from hkrd.runners import build_market, paper_short_table, run_a, run_bc  # noqa: E402

log = logging.getLogger("backtests")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cfg = load_config()
    gng = yaml.safe_load(open(cfg.root / "config" / "go_no_go.yaml"))
    out = cfg.path("outputs_dir") / "backtests"
    out.mkdir(parents=True, exist_ok=True)
    figs = cfg.path("outputs_dir") / "figures"
    inp = P.load_inputs(cfg)
    df = pd.read_parquet(cfg.path("store_dir") / "dataset.parquet")
    preds = pd.read_parquet(cfg.path("store_dir") / "oos_predictions.parquet")
    mkt = build_market(cfg, inp, df)
    periods = {"development_oos": (pd.Timestamp("2016-05-03"), pd.Timestamp(cfg["sample"]["development"][1])),
               "validation": tuple(map(pd.Timestamp, cfg["sample"]["validation"]))}

    # ------------------------------------------------------------- Strategy A
    grid = gng["selection_rule"]["strategy_a_grid"]
    sigs = {m: S.alert_signals(preds, df, m) for m in grid["model"] + ["C_lightgbm"]}
    sigs["naive_ret20_100pct"] = S.naive_signals(df, *periods["development_oos"]).pipe(
        lambda a: pd.concat([a, S.naive_signals(df, *periods["validation"])]))
    n_d = len(sigs["D_two_stage"])
    sigs["random_candidates"] = pd.concat([S.random_signals(df, lo, hi, max(n_d // 2, 1), seed=k)
                                           for k, (lo, hi) in enumerate(periods.values())])
    rows = []
    for name, sig in sigs.items():
        for hold, stop in product(grid["hold_days"], grid["stop_loss"]):
            for per, (lo, hi) in periods.items():
                st, _ = run_a(mkt, sig, lo, hi, cfg, hold, stop)
                rows.append({"signal": name, "hold_days": hold, "stop_loss": stop, "period": per, **st})
                log.info("A %s h=%d s=%.1f %s trades=%s mean=%.4f", name, hold, stop, per,
                         st["n_trades"], st.get("mean_net_ret", np.nan))
    A = pd.DataFrame(rows)
    A.to_csv(out / "strategy_a_grid.csv", index=False)

    # selection per the pre-registered rule
    v = A[(A["period"] == "validation") & A["signal"].isin(grid["model"])
          & (A["n_trades"] >= gng["selection_rule"]["min_validation_trades"])]
    sel = None
    if len(v):
        best = v.sort_values(["mean_net_ret", "hold_days", "stop_loss"], ascending=[False, True, True]).iloc[0]
        sel = {"model": best["signal"], "hold_days": int(best["hold_days"]), "stop_loss": float(best["stop_loss"])}
    else:
        # nothing meets the trade-count floor: still carry the primary model so the
        # holdout records an honest failure instead of silently skipping it
        sel = {"model": "D_two_stage", "hold_days": 10, "stop_loss": 0.3, "note": "no config met min trades"}
    P.save_json(sel, out / "strategy_a_selected.json")
    log.info("selected: %s", sel)

    # stress tests and capacity for the selected configuration, dev + validation together
    lo_all, hi_all = periods["development_oos"][0], periods["validation"][1]
    sig = sigs[sel["model"]]
    stress = []
    scen = ([{"label": "base"}] + [{"label": f"participation_{p}", "participation": p} for p in (0.01, 0.05)]
            + [{"label": f"spread_x{m}", "spread_mult": m} for m in (2.0, 3.0)]
            + [{"label": f"borrow_x{m}", "fee_mult": m} for m in (2.0, 4.0)]
            + [{"label": f"delay_{d}", "delay_days": d} for d in (1, 2)]
            + [{"label": f"nav_{int(n / 1e6)}m", "nav": n} for n in (10e6, 200e6)]
            + [{"label": "combined_severe", "spread_mult": 2.0, "fee_mult": 2.0, "delay_days": 1,
                "participation": 0.01}])
    for sc in scen:
        kw = {k: v for k, v in sc.items() if k != "label"}
        st, res = run_a(mkt, sig, lo_all, hi_all, cfg, sel["hold_days"], sel["stop_loss"], **kw)
        tr = res["trades"]
        if len(tr):
            bs = V.event_bootstrap(tr["net_ret"], tr["code"])
            conc = V.concentration(tr["net_pnl"], tr["code"])
            st.update({"boot_ci05": bs["ci_05"], "boot_ci95": bs["ci_95"], **conc})
        stress.append({"scenario": sc["label"], **st})
        if sc["label"] == "base":
            tr.to_csv(out / "strategy_a_selected_trades.csv", index=False)
            res["failures"].to_csv(out / "strategy_a_selected_failures.csv", index=False)
            plots.equity_curves({"Strategy A (selected), fixed capital": res["daily"]["ret"]},
                                figs / "strategy_a_equity.png", "Strategy A net P&L on HK$50m, dev OOS + validation")
    pd.DataFrame(stress).to_csv(out / "strategy_a_stress.csv", index=False)

    paper, _ = paper_short_table(df, mkt, sig, lo_all, hi_all)
    paper.to_csv(out / "strategy_a_paper_vs_tradable.csv")
    log.info("paper:\n%s", paper)

    # ----------------------------------------------------- Strategies B and C
    res_b, res_c = run_bc(cfg, inp, mkt, preds, pd.Timestamp("2016-01-01"), periods["validation"][1],
                          figs, "oos_2016_2024H1")
    P.save_json(res_b, out / "strategy_b.json")
    P.save_json(res_c, out / "strategy_c.json")
    log.info("B: %s", res_b)
    log.info("C: %s", res_c)


if __name__ == "__main__":
    main()
