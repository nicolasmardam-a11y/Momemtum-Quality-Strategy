"""Development + validation research run (the holdout stays locked).

    python scripts/run_research.py events     # event DB, sensitivity grid, figures
    python scripts/run_research.py dataset    # causal features + labels -> parquet
    python scripts/run_research.py models     # walk-forward folds + validation
    python scripts/run_research.py all
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from hkrd import pipeline as P  # noqa: E402
from hkrd import plots  # noqa: E402
from hkrd import validation as V  # noqa: E402
from hkrd.config import load_config  # noqa: E402

log = logging.getLogger("research")


def flag_sfc_cases(ev: pd.DataFrame, sfc: pd.DataFrame) -> pd.DataFrame:
    """Mark episodes in stocks named in SFC actions. `sfc_period_overlap` also
    requires the episode to overlap the alleged manipulation period. Neither
    flag is proof: codes are recycled and statistical matches are not findings."""
    ev["sfc_code_match"] = ev["code"].isin(sfc["code"])
    ov = np.zeros(len(ev), dtype=bool)
    for r in sfc.dropna(subset=["alleged_period_start"]).itertuples():
        ov |= ((ev["code"] == r.code) & (ev["run_start_date"] <= r.alleged_period_end)
               & (ev["trough_date"] >= r.alleged_period_start)).to_numpy()
    ev["sfc_period_overlap"] = ov
    return ev


def step_events(cfg, inp, w, sh, out: Path):
    ev, grid = P.build_event_db(cfg, inp, w, sh)
    ev = flag_sfc_cases(ev, pd.read_csv(cfg.path("reference_dir") / "sfc_cases.csv",
                                        parse_dates=["alleged_period_start", "alleged_period_end"]))
    ev.to_csv(out / "event_db.csv", index=False)
    grid.to_csv(out / "sensitivity_grid.csv", index=False)
    figs = cfg.path("outputs_dir") / "figures"
    figs.mkdir(exist_ok=True)
    plots.events_by_year(ev, figs / "events_by_year.png")
    p = cfg["events"]["primary"]
    plots.sensitivity_heatmap(grid, figs / "sensitivity_heatmap.png", p["post_window"], p["drawdown"])
    a = ev[ev["category"] == "A_ramp_dump"]
    # representative cases: spread across years, liquid enough to matter
    rep = (a[a["mean_value_run_hkd"] >= 2e6].sort_values("peak_date")
           .groupby(a["peak_date"].dt.year).head(1).head(6))
    plots.event_gallery(rep, w["close"], w["value"], figs / "cases_category_A.png",
                        "Category A: run-up on abnormal value, then >= 40% collapse within 20 days")
    for cat, fn in (("B_sustained", "cases_category_B.png"), ("C_volatile", "cases_category_C.png")):
        g = ev[(ev["category"] == cat) & (ev["mean_value_run_hkd"] >= 2e6)]
        plots.event_gallery(g.sample(min(3, len(g)), random_state=1) if len(g) else g, w["close"],
                            w["value"], figs / fn, f"Category {cat}")
    sfc_ev = ev[ev["sfc_period_overlap"]]
    if len(sfc_ev):
        plots.event_gallery(sfc_ev.head(6), w["close"], w["value"], figs / "cases_sfc.png",
                            "Episodes in stocks named in SFC ramp-and-dump actions (pattern match, not proof)")
    summary = {
        "n_episodes": int(len(ev)), "n_stocks": int(ev["code"].nunique()),
        "by_category": ev["category"].value_counts().to_dict(),
        "A_by_board": a["board"].value_counts().to_dict(),
        "A_shortable_at_peak": int(a["shortable_at_peak"].sum()),
        "A_peak_since_2016_05": int((a["peak_date"] >= "2016-05-03").sum()),
        "A_median_run_return": float(a["run_return"].median()),
        "A_median_drawdown": float(a["max_drawdown_post"].median()),
        "A_median_mean_value_run_hkd": float(a["mean_value_run_hkd"].median()),
        "A_with_mean_value_ge_5m": int((a["mean_value_run_hkd"] >= 5e6).sum()),
        "A_median_decline_remaining_at_first_signal": float(a["decline_remaining_at_signal"].median()),
    }
    P.save_json(summary, out / "event_summary.json")
    log.info("events: %s", summary)
    return ev


def step_dataset(cfg, inp, w, ev, out: Path):
    df = P.build_dataset(cfg, inp, w, ev)
    df.to_parquet(cfg.path("store_dir") / "dataset.parquet", index=False)
    base = {}
    for pop, g in (("all", df), ("candidate", df[df["candidate"]])):
        base[pop] = {t: float(g[t].mean()) for t in P.TARGETS_ALL}
        base[pop]["n_rows"] = int(len(g))
    P.save_json(base, out / "base_rates.json")
    log.info("dataset rows=%d candidates=%d base=%s", len(df), int(df["candidate"].sum()), base)
    return df


def step_models(cfg, df, ev, out: Path):
    dates = pd.DatetimeIndex(sorted(df["date"].unique()))
    folds = V.walk_forward_folds(dates, cfg["sample"])
    preds, metas = [], []
    for f in folds:
        p, m = P.fit_predict_fold(cfg, df, f)
        preds.append(p)
        metas.append(m)
    preds = pd.concat(preds, ignore_index=True)
    preds.to_parquet(cfg.path("store_dir") / "oos_predictions.parquet", index=False)
    P.save_json(metas, out / "fold_meta.json")
    met = P.evaluate_predictions(df, preds)
    met.to_csv(out / "metrics_by_fold.csv", index=False)
    # pooled out-of-sample (development folds) and validation
    preds["block"] = np.where(preds["fold"] == "validation", "validation", "development_oos")
    pooled = P.evaluate_predictions(df, preds.assign(fold=preds["block"]))
    pooled.to_csv(out / "metrics_pooled.csv", index=False)
    ew = P.early_warning_table(ev, preds, df)
    ew.to_csv(out / "early_warning.csv", index=False)
    if len(ew):
        s = ew.groupby("model").agg(events=("event_id", "size"), alerted=("alerted", "mean"),
                                    before_or_at_peak=("before_or_at_peak", "mean"),
                                    median_remaining_decline=("remaining_decline", "median"),
                                    median_ret_to_trough=("ret_alert_close_to_trough", "median"))
        s.to_csv(out / "early_warning_summary.csv")
        log.info("early warning:\n%s", s)
    # calibration on pooled development OOS, candidate population
    M = preds.merge(df[["date", "code", "candidate", "dd20_40"]], on=["date", "code"])
    M = M[M["candidate"] & (M["block"] == "development_oos")]
    tabs = {}
    for model, tgt in P.prediction_columns(preds):
        if tgt == "dd20_40":
            tabs[model] = V.calibration_table(M["dd20_40"].to_numpy(), M[P.pcol(model, tgt)].to_numpy(), 10)
    pd.concat(tabs, names=["model"]).to_csv(out / "calibration_candidates.csv")
    plots.calibration_plot(tabs, cfg.path("outputs_dir") / "figures" / "calibration_candidates.png",
                           "Calibration, candidate rows, dev OOS (dd20_40)")
    # conditional outcome table by predicted-risk decile (Model D, candidates)
    col = P.pcol("D_two_stage", "dd20_40")
    M = M.merge(df[["date", "code", "fwd_ret_1", "fwd_ret_5", "fwd_ret_20", "fwd_min_ret_20",
                    "fwd_max_ret_20", "days_to_dd20", "fwd_ret_open_20"]], on=["date", "code"])
    M["decile"] = pd.qcut(M[col].rank(method="first"), 10, labels=False)
    dec = M.groupby("decile").agg(n=("dd20_40", "size"), p_mean=(col, "mean"), crash40=("dd20_40", "mean"),
                                  fwd_ret_1=("fwd_ret_1", "mean"), fwd_ret_5=("fwd_ret_5", "mean"),
                                  fwd_ret_20=("fwd_ret_20", "mean"),
                                  fwd_ret_open_20_median=("fwd_ret_open_20", "median"),
                                  max_adverse_20=("fwd_max_ret_20", "mean"),
                                  median_days_to_dd20=("days_to_dd20", "median"))
    dec.to_csv(out / "decile_outcomes_model_D_candidates.csv")
    log.info("deciles:\n%s", dec)
    return preds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["events", "dataset", "models", "all"])
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cfg = load_config()
    out = cfg.path("outputs_dir") / "research"
    out.mkdir(parents=True, exist_ok=True)
    if args.step in ("events", "dataset", "all"):
        inp = P.load_inputs(cfg)
        w = P.wide_frames(inp["panel"])
        sh = P.shortable_wide(inp["ds"], w["close"].index, w["close"].columns)
    if args.step in ("events", "all"):
        ev = step_events(cfg, inp, w, sh, out)
    else:
        ev = pd.read_csv(out / "event_db.csv", parse_dates=["run_start_date", "first_signal_date",
                                                            "last_signal_date", "peak_date", "trough_date"])
    if args.step in ("dataset", "all"):
        df = step_dataset(cfg, inp, w, ev, out)
        del w, inp
    if args.step in ("models", "all"):
        if args.step == "models":
            df = pd.read_parquet(cfg.path("store_dir") / "dataset.parquet")
        step_models(cfg, df, ev, out)


if __name__ == "__main__":
    main()
