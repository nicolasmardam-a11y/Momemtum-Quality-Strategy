"""Chronological validation with purging, embargo and event grouping, plus
class-imbalance-aware metrics and event-level bootstrap.

Holdout discipline: `split_masks` never returns holdout rows unless
`unlock_holdout=True`, and scripts only pass that flag when the
pre-registered criteria file hash matches (see scripts/run_holdout.py).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


@dataclass(frozen=True)
class Fold:
    name: str
    train_end: pd.Timestamp     # last label-complete training date (after purge)
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def trading_day_offset(dates: pd.DatetimeIndex, d: pd.Timestamp, k: int) -> pd.Timestamp:
    i = dates.searchsorted(d)
    return dates[int(np.clip(i + k, 0, len(dates) - 1))]


def walk_forward_folds(dates: pd.DatetimeIndex, sample: dict) -> list[Fold]:
    """Expanding-window yearly folds in the development period, then the
    validation block. Training rows are purged `embargo_days` trading days
    before each test start so no training label window overlaps the test.
    """
    emb = sample["embargo_days"]
    dev_end = pd.Timestamp(sample["development"][1])
    folds = []
    for y in range(sample["first_test_year"], dev_end.year + 1):
        ts, te = pd.Timestamp(f"{y}-01-01"), min(pd.Timestamp(f"{y}-12-31"), dev_end)
        folds.append(Fold(f"wf_{y}", trading_day_offset(dates, ts, -emb - 1), ts, te))
    vs, ve = map(pd.Timestamp, sample["validation"])
    folds.append(Fold("validation", trading_day_offset(dates, vs, -emb - 1), vs, ve))
    return folds


def holdout_fold(dates: pd.DatetimeIndex, sample: dict) -> Fold:
    hs, he = map(pd.Timestamp, sample["holdout"])
    return Fold("holdout", trading_day_offset(dates, hs, -sample["embargo_days"] - 1), hs, he)


def split_masks(row_dates: pd.Series, fold: Fold, groups: pd.Series | None = None,
                unlock_holdout: bool = False, holdout_start: pd.Timestamp | None = None):
    """Train/test boolean masks for a fold.

    Event grouping: rows sharing a group id (ramp episode) are assigned to the
    side of the group's first date; a group that starts in training but
    continues into the test window is removed from training entirely.
    """
    d = pd.to_datetime(row_dates)
    if fold.name == "holdout" and not unlock_holdout:
        raise PermissionError("holdout is locked; run scripts/run_holdout.py after pre-registration")
    train = d <= fold.train_end
    test = (d >= fold.test_start) & (d <= fold.test_end)
    if holdout_start is not None and fold.name != "holdout":
        test &= d < holdout_start
    if groups is not None:
        g = groups.where(groups.notna())
        g_last = d.groupby(g).transform("max")
        straddle = g.notna() & (g_last > fold.train_end)
        train &= ~straddle
    return train.to_numpy(), test.to_numpy()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
def classification_report(y: np.ndarray, p: np.ndarray, top_fracs=(0.001, 0.01, 0.05)) -> dict:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    ok = ~np.isnan(y) & ~np.isnan(p)
    y, p = y[ok], p[ok]
    out = {"n": int(len(y)), "positives": int(y.sum()), "base_rate": float(y.mean()) if len(y) else np.nan}
    if len(y) == 0 or y.sum() == 0 or y.sum() == len(y):
        return out
    out["pr_auc"] = float(average_precision_score(y, p))
    out["pr_auc_lift"] = out["pr_auc"] / out["base_rate"]
    out["roc_auc"] = float(roc_auc_score(y, p))
    out["brier"] = float(brier_score_loss(y, np.clip(p, 0, 1)))
    out["brier_baseline"] = float(brier_score_loss(y, np.full_like(y, y.mean())))
    order = np.argsort(-p, kind="stable")
    for f in top_fracs:
        k = max(int(round(f * len(y))), 1)
        sel = y[order[:k]]
        out[f"precision_top_{f:g}"] = float(sel.mean())
        out[f"recall_top_{f:g}"] = float(sel.sum() / y.sum())
        thr = p[order[k - 1]]
        neg = y == 0
        out[f"fpr_top_{f:g}"] = float(((p >= thr) & neg).sum() / max(neg.sum(), 1))
    return out


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = 10) -> pd.DataFrame:
    df = pd.DataFrame({"y": y, "p": p}).dropna()
    df["bin"] = pd.qcut(df["p"].rank(method="first"), bins, labels=False)
    return df.groupby("bin").agg(n=("y", "size"), mean_pred=("p", "mean"), observed=("y", "mean"))


def random_alert_baseline(y: np.ndarray, frac: float, n_draws: int = 1000, seed: int = 0) -> dict:
    """Precision of randomly chosen alerts: the base rate, with its spread."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y, dtype=float)
    y = y[~np.isnan(y)]
    k = max(int(round(frac * len(y))), 1)
    prec = np.array([y[rng.choice(len(y), k, replace=False)].mean() for _ in range(n_draws)])
    return {"mean": float(prec.mean()), "p95": float(np.quantile(prec, 0.95))}


def event_bootstrap(values: pd.Series, groups: pd.Series, stat=np.mean, n: int = 2000,
                    seed: int = 0) -> dict:
    """Resample whole events (groups) with replacement; CI of `stat` on values."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({"v": values.to_numpy(), "g": groups.to_numpy()}).dropna()
    if df.empty:
        return {"n_groups": 0}
    per = df.groupby("g")["v"].apply(np.asarray)
    arrs = per.to_list()
    k = len(arrs)
    draws = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, k, k)
        draws[i] = stat(np.concatenate([arrs[j] for j in idx]))
    return {"n_groups": k, "point": float(stat(df["v"].to_numpy())),
            "ci_05": float(np.quantile(draws, 0.05)), "ci_95": float(np.quantile(draws, 0.95)),
            "p_le_0": float((draws <= 0).mean())}


def concentration(pnl: pd.Series, by: pd.Series, top: int = 5) -> dict:
    """Share of total profit coming from the top-N groups (stocks or events)."""
    g = pnl.groupby(by).sum().sort_values(ascending=False)
    total = g.sum()
    return {"total": float(total), f"top{top}_share": float(g.head(top).sum() / total) if total > 0 else np.nan,
            "pnl_ex_top": float(g.iloc[top:].sum()), "n_groups": int(len(g))}
