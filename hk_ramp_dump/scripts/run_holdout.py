"""Open the final holdout ONCE and score it against the pre-registered criteria.

    python scripts/run_holdout.py

Refuses to run unless config/go_no_go.yaml is committed and unmodified, and
the Strategy A configuration has already been selected on validation data
(outputs/backtests/strategy_a_selected.json). Models are refitted on all
data up to the purged holdout start; nothing is tuned on the holdout.
"""
from __future__ import annotations

import hashlib
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import json  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from hkrd import pipeline as P  # noqa: E402
from hkrd import strategies as S  # noqa: E402
from hkrd import validation as V  # noqa: E402
from hkrd.config import load_config  # noqa: E402
from hkrd.runners import build_market, paper_short_table, run_a, run_bc  # noqa: E402

log = logging.getLogger("holdout")


def preregistration_check(root: Path) -> dict:
    f = root / "config" / "go_no_go.yaml"
    sha = hashlib.sha256(f.read_bytes()).hexdigest()
    rel = f.relative_to(root.parent).as_posix()
    dirty = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=root.parent).returncode != 0
    first = subprocess.run(["git", "log", "--diff-filter=A", "--format=%H %cI", "--", rel], cwd=root.parent,
                           capture_output=True, text=True).stdout.strip().splitlines()
    if dirty or not first:
        raise SystemExit("go_no_go.yaml must be committed and unmodified before opening the holdout")
    return {"sha256": sha, "first_commit": first[-1]}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cfg = load_config()
    prereg = preregistration_check(cfg.root)
    gng = yaml.safe_load(open(cfg.root / "config" / "go_no_go.yaml"))
    bdir = cfg.path("outputs_dir") / "backtests"
    sel = json.load(open(bdir / "strategy_a_selected.json"))
    out = cfg.path("outputs_dir") / "holdout"
    out.mkdir(parents=True, exist_ok=True)
    figs = cfg.path("outputs_dir") / "figures"

    df = pd.read_parquet(cfg.path("store_dir") / "dataset.parquet")
    ev = pd.read_csv(cfg.path("outputs_dir") / "research" / "event_db.csv",
                     parse_dates=["run_start_date", "first_signal_date", "last_signal_date", "peak_date", "trough_date"])
    dates = pd.DatetimeIndex(sorted(df["date"].unique()))
    hf = V.holdout_fold(dates, cfg["sample"])
    preds, meta = P.fit_predict_fold(cfg, df, hf, unlock_holdout=True)
    preds.to_parquet(cfg.path("store_dir") / "holdout_predictions.parquet", index=False)
    met = P.evaluate_predictions(df, preds)
    met.to_csv(out / "holdout_metrics.csv", index=False)
    ew = P.early_warning_table(ev, preds, df)
    ew.to_csv(out / "holdout_early_warning.csv", index=False)

    # ---------------- prediction criteria (candidate population, dd20_40)
    # go_no_go.yaml does not name the model, so each strategy is judged on the
    # model it actually trades: A -> the selected model; B -> the model whose
    # alerts drive each exit variant; C -> C_lightgbm (the ranking model).
    # Decided before the holdout was opened; all models are reported regardless.
    pc = gng["prediction"]

    def prediction_ok(model: str) -> dict:
        r = met[(met["model"] == model) & (met["target"] == "dd20_40") & (met["population"] == "candidate")].iloc[0]
        return {
            "positives": bool(r["positives"] >= pc["min_holdout_positives"]),
            "pr_auc_lift": bool(r.get("pr_auc_lift", 0) >= pc["pr_auc_lift_min"]),
            "precision_top10_lift": bool(r.get("precision_top_0.1", 0) / r["base_rate"] >= pc["precision_top10pct_lift_min"]),
            "brier": bool(r.get("brier", 1) < r.get("brier_baseline", 0)),
            "beats_random_p95": bool(r.get("precision_top_0.1", 0) > r.get("random_top_0.1_p95", 1)),
        }

    pred_ok = {m: prediction_ok(m) for m in ("A_rules", "B_regime_hmm", "C_lightgbm", "D_two_stage")}
    r = met[(met["model"] == sel["model"]) & (met["target"] == "dd20_40") & (met["population"] == "candidate")].iloc[0]

    # ---------------- Strategy A
    inp = P.load_inputs(cfg)
    mkt = build_market(cfg, inp, df)
    lo, hi = hf.test_start, hf.test_end
    sig = S.alert_signals(preds, df, sel["model"])
    c = gng["strategy_a_short"]
    base, res = run_a(mkt, sig, lo, hi, cfg, sel["hold_days"], sel["stop_loss"])
    tr = res["trades"]
    tr.to_csv(out / "holdout_strategy_a_trades.csv", index=False)
    res["failures"].to_csv(out / "holdout_strategy_a_failures.csv", index=False)
    bs = V.event_bootstrap(tr["net_ret"], tr["code"]) if len(tr) else {"ci_05": np.nan}
    conc = V.concentration(tr["net_pnl"], tr["code"]) if len(tr) else {"top5_share": np.nan, "pnl_ex_top": np.nan}
    stress = {}
    for s in c["stress_must_stay_positive"]:
        kw = {("fee_mult" if k == "borrow_mult" else k): v for k, v in s.items()}
        st, _ = run_a(mkt, sig, lo, hi, cfg, sel["hold_days"], sel["stop_loss"], **kw)
        stress[json.dumps(s)] = st.get("mean_net_ret", np.nan)
    grid = pd.read_csv(bdir / "strategy_a_grid.csv")
    g = grid[(grid["signal"] == sel["model"]) & (grid["hold_days"] == sel["hold_days"])
             & (grid["stop_loss"] == sel["stop_loss"])].set_index("period")["mean_net_ret"]
    a_ok = {
        "min_trades": bool(base["n_trades"] >= c["min_trades"]),
        "min_stocks": bool(base.get("n_stocks", 0) >= c["min_distinct_stocks"]),
        "mean_net_positive": bool(base.get("mean_net_ret", -1) > c["mean_net_return_per_trade_gt"]),
        "bootstrap_ci05_positive": bool(bs.get("ci_05", -1) > c["bootstrap_ci05_gt"]),
        "sharpe": bool(base.get("pf_sharpe", -9) >= c["sharpe_min"]),
        "concentration": bool(conc.get("top5_share", 1) <= c["top5_stock_profit_share_max"]
                              if np.isfinite(conc.get("top5_share", np.nan)) else False),
        "pnl_ex_top5_positive": bool(conc.get("pnl_ex_top", -1) > 0),
        "stress_positive": bool(all(np.isfinite(v) and v > 0 for v in stress.values())),
        "same_sign_dev_val": bool(g.get("development_oos", np.nan) > 0 and g.get("validation", np.nan) > 0),
        "deployed_capital": bool(base.get("avg_gross_deployed_hkd", 0) >= c["min_avg_gross_deployed_hkd"]),
    }
    paper, _ = paper_short_table(df, mkt, sig, lo, hi)
    paper.to_csv(out / "holdout_paper_vs_tradable.csv")

    # ---------------- Strategies B / C
    res_b, res_c = run_bc(cfg, inp, mkt, preds, lo, hi, figs, "holdout")
    cb, cc = gng["strategy_b_liquidation"], gng["strategy_c_ranking"]
    b0 = res_b["momentum_top50"]
    b_ok = {}
    for lab in ("exit_on_C_alert", "exit_on_D_alert"):
        b1 = res_b[lab]
        dd_red = 1 - b1.get("max_drawdown", 0) / b0["max_drawdown"] if b0.get("max_drawdown") else 0
        b_ok[lab] = bool((b1.get("sharpe", -9) - b0.get("sharpe", 0) >= cb["sharpe_improvement_min"]
                          or dd_red >= cb["or_max_drawdown_reduction_rel"])
                         and b0.get("ann_return", 0) - b1.get("ann_return", 0) <= cb["max_annual_return_cost"])
    c0, c1, c2 = res_c["ew_investable"], res_c["ex_top_decile_risk"], res_c["top_decile_risk"]
    c_ok = {"sharpe_improvement": bool(c1.get("sharpe", -9) - c0.get("sharpe", 0) >= cc["sharpe_improvement_min"]),
            "top_decile_underperforms": bool(c2.get("ann_return", 9) < c0.get("ann_return", -9)),
            "bootstrap_p": bool(res_c["ex_top_minus_ew_p"] <= cc["block_bootstrap_p_max"])}

    def verdict(stat_ok: bool, strat_ok: bool) -> str:
        return "GO" if stat_ok and strat_ok else ("NO_GO_STAT_ONLY" if stat_ok else "NO_GO")

    stat = {m: all(v.values()) for m, v in pred_ok.items()}
    b_models = {"exit_on_C_alert": "C_lightgbm", "exit_on_D_alert": "D_two_stage"}
    b_verdicts = {lab: verdict(stat[b_models[lab]], ok) for lab, ok in b_ok.items()}
    b_final = "GO" if "GO" in b_verdicts.values() else (
        "NO_GO_STAT_ONLY" if "NO_GO_STAT_ONLY" in b_verdicts.values() else "NO_GO")
    report = {
        "preregistration": prereg, "holdout": [str(lo.date()), str(hi.date())], "selected_strategy_a": sel,
        "prediction_metrics_selected_model": r.to_dict(), "prediction_criteria_by_model": pred_ok,
        "strategy_a": {"stats": base, "bootstrap": bs, "concentration": conc, "stress_mean_net_ret": stress,
                       "criteria": a_ok, "verdict": verdict(stat[sel["model"]], all(a_ok.values()))},
        "strategy_b": {"stats": res_b, "criteria": b_ok, "verdict_by_variant": b_verdicts, "verdict": b_final},
        "strategy_c": {"stats": res_c, "criteria": c_ok,
                       "verdict": verdict(stat["C_lightgbm"], all(c_ok.values()))},
        "fold_meta": meta,
    }
    P.save_json(report, out / "holdout_report.json")
    log.info("prediction criteria: %s", pred_ok)
    log.info("A: %s -> %s", a_ok, report["strategy_a"]["verdict"])
    log.info("B: %s -> %s", b_ok, report["strategy_b"]["verdict"])
    log.info("C: %s -> %s", c_ok, report["strategy_c"]["verdict"])


if __name__ == "__main__":
    main()
