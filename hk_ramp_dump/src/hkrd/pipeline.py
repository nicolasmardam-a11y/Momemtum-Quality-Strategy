"""End-to-end research steps shared by the scripts.

    inputs -> event database -> feature/label dataset -> walk-forward models
           -> out-of-sample predictions -> strategy backtests

Each step writes its outputs under outputs/ so later steps (and the daily
monitor) can run independently.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from . import events as E
from . import features as F
from . import validation as V
from .config import Config
from .data import load_panel
from .models import GBMModel, RegimeModel, RulesModel, TwoStageModel, candidate_mask

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def load_inputs(cfg: Config, end: str | None = "holdout_end") -> dict:
    """Load the store. Research runs stop at the holdout end date so a partial
    intraday bar (fetched before the close) never enters the sample."""
    store = cfg.path("store_dir")
    panel = load_panel(store)
    if end == "holdout_end":
        panel = panel[panel["date"] <= pd.Timestamp(cfg["sample"]["holdout"][1])]
    elif end is not None:
        panel = panel[panel["date"] <= pd.Timestamp(end)]
    bench = pd.read_parquet(store / "benchmarks.parquet").set_index("date").sort_index()
    ds = pd.read_parquet(store / "ds_lists.parquet")
    uni = pd.read_csv(cfg.path("reference_dir") / "universe_current.csv")
    return {"panel": panel, "bench": bench, "ds": ds, "universe": uni}


def wide_frames(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    cols = ["open", "high", "low", "close", "value", "quality_mask", "raw_factor"]
    w = {c: panel.pivot(index="date", columns="code", values=c).sort_index() for c in cols}
    w["quality_mask"] = w["quality_mask"].fillna(False).astype(bool)
    w["raw_close"] = w["close"] * w["raw_factor"].fillna(1.0)
    w["traded"] = w["value"].fillna(0) > 0
    return w


def shortable_wide(ds: pd.DataFrame, dates: pd.DatetimeIndex, codes: pd.Index) -> pd.DataFrame:
    """Designated-list membership in force on each date (latest list <= date).
    False before the first archived list: unknown is treated as not shortable."""
    out = pd.DataFrame(False, index=dates, columns=codes)
    eff = sorted(ds["effective_date"].unique())
    for k, e in enumerate(eff):
        nxt = eff[k + 1] if k + 1 < len(eff) else pd.Timestamp("2100-01-01")
        rows = (dates >= e) & (dates < nxt)
        if not rows.any():
            continue
        mem = codes.isin(ds.loc[ds["effective_date"].eq(e), "code"])
        out.loc[rows, mem] = True
    return out


def market_series(bench: pd.DataFrame) -> pd.Series:
    return bench["^HSI"].dropna() if "^HSI" in bench else bench.iloc[:, 0].dropna()


# ---------------------------------------------------------------------------
# Step 1: event database
# ---------------------------------------------------------------------------
def build_event_db(cfg: Config, inp: dict, w: dict, sh: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    p = E.params_from_config(cfg["events"])
    mkt = market_series(inp["bench"])
    ev = E.detect_events(w["close"], w["value"], w["quality_mask"], mkt, p, sh)
    uni = inp["universe"].set_index("code")
    ev["name"] = ev["code"].map(uni["name"])
    ev["board"] = ev["code"].map(uni["board"])
    ev["board_lot_now"] = ev["code"].map(uni["board_lot"])
    grid = E.sensitivity_grid(w["close"], w["value"], w["quality_mask"], mkt, cfg["events"]["grid"], p, sh)
    return ev, grid


def episode_ids(ev: pd.DataFrame, dates: pd.DatetimeIndex, codes: pd.Index) -> pd.DataFrame:
    """Wide frame of episode ids covering [run_start, trough] for grouping."""
    g = pd.DataFrame(None, index=dates, columns=codes, dtype=object)
    for r in ev.itertuples():
        end = max(r.trough_date, r.last_signal_date)
        g.loc[r.run_start_date:end, r.code] = r.event_id
    return g


# ---------------------------------------------------------------------------
# Step 2: dataset
# ---------------------------------------------------------------------------
def build_dataset(cfg: Config, inp: dict, w: dict, ev: pd.DataFrame) -> pd.DataFrame:
    mkt = market_series(inp["bench"])
    feats = F.wide_features(w["open"], w["high"], w["low"], w["close"], w["value"], mkt,
                            cfg["features"]["baseline_window"], w["raw_close"])
    lab = F.forward_labels(w["close"], w["open"], cfg["labels"]["horizons"],
                           cfg["labels"]["drawdown_horizon"], cfg["labels"]["drawdown_thresholds"])
    c = w["close"]
    hist = c.notna().cumsum()
    m = w["quality_mask"].astype(float)
    mask_past = m.rolling(21, min_periods=1).max() > 0
    mask_future = m[::-1].rolling(21, min_periods=1).max()[::-1] > 0
    eligible = (c.notna() & w["traded"] & (hist >= cfg["universe"]["min_history_days"])
                & ~mask_past & ~mask_future)
    adv20 = w["value"].fillna(0).rolling(20, min_periods=10).mean()
    extra = {"adv20": adv20.astype(np.float32), "close": c.astype(np.float32),
             "raw_close": w["raw_close"].astype(np.float32)}
    keep = eligible.stack()
    keep = keep[keep].index
    frames = {**feats, **lab, **extra}
    df = pd.DataFrame({k: v.stack(future_stack=True).reindex(keep) for k, v in frames.items()})
    df.index.names = ["date", "code"]
    grp = episode_ids(ev, c.index, c.columns).stack().reindex(keep)
    df["episode_id"] = grp.to_numpy()
    df = df.reset_index().sort_values(["code", "date"]).reset_index(drop=True)
    df["candidate"] = candidate_mask(df, cfg["candidate_filter"]["ret_20_min"],
                                     cfg["candidate_filter"]["value_ratio_20_min"])
    return df


# ---------------------------------------------------------------------------
# Step 3: walk-forward models
# ---------------------------------------------------------------------------
TARGETS_ALL = ["dd20_20", "dd20_30", "dd20_40"]


def make_models(cfg: Config) -> dict:
    cf, mc = cfg["candidate_filter"], cfg["models"]
    seed = mc["random_seed"]
    return {
        "A_rules": lambda: RulesModel(cf["ret_20_min"], cf["value_ratio_20_min"]),
        "B_regime_hmm": lambda: RegimeModel(mc["hmm"]["n_states"], mc["hmm"]["n_iter"],
                                            mc["hmm"]["fit_sample_tickers"], seed),
        "C_lightgbm": lambda: GBMModel(mc["lightgbm"], mc["negative_subsample"], seed=seed),
        "D_two_stage": lambda: TwoStageModel(mc["lightgbm"], cf["ret_20_min"], cf["value_ratio_20_min"],
                                             seed=seed),
    }


def model_targets(name: str) -> list[str]:
    return TARGETS_ALL if name in ("C_lightgbm", "D_two_stage") else ["dd20_40"]


def pcol(model: str, tgt: str) -> str:
    return f"p__{model}__{tgt}"


def acol(model: str, tgt: str) -> str:
    return f"alert__{model}__{tgt}"


def fit_predict_fold(cfg: Config, df: pd.DataFrame, fold: V.Fold, unlock_holdout=False,
                     models: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    """Fit every model/target on the fold's training rows, predict its test rows.

    Returns a wide frame (one row per test stock-day) with p__/alert__ columns.
    Alert thresholds are the 90th percentile of each model's predictions on
    *training* candidate rows, so the test period never sets its own cut-off.
    """
    holdout_start = pd.Timestamp(cfg["sample"]["holdout"][0])
    tr, te = V.split_masks(df["date"], fold, df["episode_id"], unlock_holdout=unlock_holdout,
                           holdout_start=None if unlock_holdout else holdout_start)
    out = df.loc[te, ["date", "code"]].copy()
    out["fold"] = fold.name
    meta = {"fold": fold.name, "train_end": str(fold.train_end.date()), "n_train": int(tr.sum()),
            "n_test": int(te.sum()), "thresholds": {}, "importance": {}}
    cand = df["candidate"].to_numpy()
    for name, mk in make_models(cfg).items():
        if models and name not in models:
            continue
        for tgt in model_targets(name):
            y = df[tgt]
            trm = tr & y.notna().to_numpy()
            m = mk()
            m.fit(df.loc[trm], y[trm], df.loc[trm, "code"], df.loc[trm, "date"])
            if name == "B_regime_hmm":
                # HMM parameters come from training rows; the filter then runs
                # causally over all rows in date order (no smoothing).
                p_all = m.predict_proba(df, df["code"], df["date"])
                p_te, p_tr = p_all[te], p_all[tr & cand]
            else:
                p_te = m.predict_proba(df.loc[te])
                p_tr = m.predict_proba(df.loc[tr & cand]) if (tr & cand).any() else np.array([])
            thr = float(np.nanquantile(p_tr, 0.9)) if len(p_tr) else np.inf
            meta["thresholds"][f"{name}|{tgt}"] = thr
            if hasattr(m, "importance") and tgt == "dd20_40":
                meta["importance"][name] = m.importance().head(15).round(4).to_dict()
            out[pcol(name, tgt)] = p_te.astype(np.float32)
            out[acol(name, tgt)] = p_te >= thr
            log.info("%s %s %s done (thr=%.4f)", fold.name, name, tgt, thr)
    return out.reset_index(drop=True), meta


def prediction_columns(preds: pd.DataFrame) -> list[tuple[str, str]]:
    return [tuple(c.split("__")[1:]) for c in preds.columns if c.startswith("p__")]


def evaluate_predictions(df: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    """Per fold x model x target x population metrics, with random baselines."""
    P = preds.merge(df[["date", "code", "candidate", *TARGETS_ALL]], on=["date", "code"], how="left")
    rows = []
    for fold, g in P.groupby("fold"):
        for model, tgt in prediction_columns(preds):
            for pop, gg in (("all", g), ("candidate", g[g["candidate"]])):
                y, p = gg[tgt].to_numpy(), gg[pcol(model, tgt)].to_numpy()
                rep = V.classification_report(y, p, top_fracs=(0.01, 0.1))
                if rep.get("positives", 0) > 0 and len(y) > 50:
                    rb = V.random_alert_baseline(y, 0.1, n_draws=300)
                    rep["random_top_0.1_mean"], rep["random_top_0.1_p95"] = rb["mean"], rb["p95"]
                a = gg[acol(model, tgt)].to_numpy() & ~np.isnan(y)
                rep["alerts"] = int(a.sum())
                rep["alert_precision"] = float(np.nanmean(y[a])) if a.any() else np.nan
                rows.append({"fold": fold, "model": model, "target": tgt, "population": pop, **rep})
    return pd.DataFrame(rows)


def early_warning_table(ev: pd.DataFrame, preds: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """For each category-A event inside the tested window: did the model alert
    between run start and trough, was it before the peak, and how much of the
    eventual collapse was still ahead at the first alert?"""
    close = df.set_index(["code", "date"])["close"]
    lo, hi = preds["date"].min(), preds["date"].max()
    a_ev = ev[(ev["category"] == "A_ramp_dump") & (ev["run_start_date"] >= lo) & (ev["trough_date"] <= hi)]
    out = []
    for model, tgt in prediction_columns(preds):
        if tgt != "dd20_40":
            continue
        al = preds.loc[preds[acol(model, tgt)], ["code", "date"]]
        by_code = {c: g["date"].sort_values().to_numpy() for c, g in al.groupby("code")}
        for r in a_ev.itertuples():
            d = by_code.get(r.code, np.array([], dtype="datetime64[ns]"))
            win = d[(d >= np.datetime64(r.run_start_date)) & (d <= np.datetime64(r.trough_date))]
            rec = {"model": model, "event_id": r.event_id, "alerted": len(win) > 0}
            if len(win):
                a = pd.Timestamp(win[0])
                ca = float(close.get((r.code, a), np.nan))
                rec.update(first_alert=a, before_or_at_peak=a <= r.peak_date,
                           remaining_decline=float(np.clip((ca - r.trough_close) /
                                                           (r.peak_close - r.trough_close), 0, 1.5)),
                           ret_alert_close_to_trough=r.trough_close / ca - 1 if ca > 0 else np.nan)
            out.append(rec)
    return pd.DataFrame(out)


def save_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)
