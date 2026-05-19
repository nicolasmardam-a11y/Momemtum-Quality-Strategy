"""Walk-forward OOS validation for the 6-factor composite.

Modes:
- expanding: train window grows; test window fixed (annual or quarterly)
- rolling:   fixed train window (e.g. 5y); fixed test window

Per-fold:
1. Build pillar z-scores using ONLY data available up to train end
   (fundamentals: today's snapshot is used regardless — this is the
   acknowledged survivorship/look-ahead bias).
2. Build price-factor z-scores using prices up to train end.
3. Determine weight scheme:
   - "fixed": use a configured scheme name unchanged
   - "data_driven": pick the scheme that maximized in-train IC of next 3m returns
4. Rank universe, pick top-N, hold over the test window.
5. Stitch test-window daily returns to produce a continuous OOS curve.

The OOS curve is the deliverable for acceptance gates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from .factors_price import compute_price_factors
from .scoring_full import (PILLAR_METRICS, WEIGHT_SCHEMES,
                            compute_full_pillars, composite_with_weights,
                            apply_quality_floor)
from .utils import get_logger

log = get_logger("walk_forward")


@dataclass
class FoldResult:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    weight_scheme: str
    n_held: int
    top_tickers: list[str]
    daily_returns: pd.Series
    turnover: float = 0.0


@dataclass
class WalkForwardResult:
    folds: list[FoldResult] = field(default_factory=list)
    daily_returns: pd.Series = field(default_factory=pd.Series)
    weight_schemes_used: list[str] = field(default_factory=list)
    label: str = ""

    @property
    def equity_curve(self) -> pd.Series:
        return (1 + self.daily_returns).cumprod()


def generate_walk_forward_dates(start: pd.Timestamp, end: pd.Timestamp,
                                 train_years: int = 5,
                                 test_months: int = 12,
                                 mode: str = "rolling") -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    """Yield (train_start, train_end, test_start, test_end) tuples."""
    folds: list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]] = []
    cur_train_end = start + pd.DateOffset(years=train_years)
    while cur_train_end + pd.DateOffset(months=test_months) <= end:
        if mode == "rolling":
            ts = cur_train_end - pd.DateOffset(years=train_years)
        else:
            ts = start
        test_s = cur_train_end + pd.Timedelta(days=1)
        test_e = test_s + pd.DateOffset(months=test_months) - pd.Timedelta(days=1)
        if test_e > end:
            test_e = end
        folds.append((ts, cur_train_end, test_s, test_e))
        cur_train_end = test_e
    return folds


def _select_top_n(scores_df: pd.DataFrame, weights: dict[str, float],
                  neutrality: str, top_n: int, apply_floors: bool = True) -> pd.DataFrame:
    """Rank scores_df and return top_n with equal weights."""
    pillars = compute_full_pillars(scores_df, neutrality=neutrality)
    composite = composite_with_weights(pillars, weights)
    if apply_floors:
        composite = apply_quality_floor(scores_df, composite)
    composite = composite.dropna()
    if composite.empty:
        return pd.DataFrame(columns=["weight"])
    top = composite.sort_values(ascending=False).head(top_n)
    out = pd.DataFrame({"weight": np.ones(len(top)) / len(top)}, index=top.index)
    return out


def in_sample_ic(scores_df: pd.DataFrame, forward_rets: pd.Series,
                 weights: dict[str, float], neutrality: str) -> float:
    """Spearman IC between composite score and forward returns."""
    pillars = compute_full_pillars(scores_df, neutrality=neutrality)
    composite = composite_with_weights(pillars, weights).dropna()
    common = composite.index.intersection(forward_rets.index)
    if len(common) < 20:
        return np.nan
    return composite.loc[common].rank().corr(forward_rets.loc[common].rank())


def pick_best_scheme_by_ic(scores_df: pd.DataFrame, forward_rets: pd.Series,
                            neutrality: str) -> tuple[str, float]:
    """Across WEIGHT_SCHEMES, pick the one with highest in-train IC."""
    best_scheme, best_ic = "baseline", -np.inf
    for name, w in WEIGHT_SCHEMES.items():
        ic = in_sample_ic(scores_df, forward_rets, w, neutrality)
        if pd.notna(ic) and ic > best_ic:
            best_scheme = name
            best_ic = ic
    return best_scheme, best_ic


def run_walk_forward(
    fundamentals: pd.DataFrame,        # per-ticker fundamental snapshot
    prices_local_usd: pd.DataFrame,    # wide closes already USD-converted
    benchmark_prices: pd.Series,        # e.g. URTH closes
    start: pd.Timestamp,
    end: pd.Timestamp,
    top_n: int = 50,
    train_years: int = 5,
    test_months: int = 12,
    mode: str = "rolling",
    weight_scheme: str = "baseline",
    pick_data_driven: bool = False,
    neutrality: str = "sector_neutral",
    costs_bps_one_way: float = 10.0,
    apply_floors: bool = True,
    label: str = "",
) -> WalkForwardResult:
    """Run walk-forward OOS. For each fold:
       1. Compute price-factors at train_end (i.e. signal date)
       2. Merge with fundamentals
       3. Optionally pick weight scheme by in-train IC of next-3m returns
       4. Rank, take top_n equal-weighted
       5. Hold across test window, compute daily returns net of trading costs
    """
    folds_dates = generate_walk_forward_dates(start, end, train_years, test_months, mode)
    log.info("WF[%s]: %d folds from %s to %s", label, len(folds_dates), start.date(), end.date())

    fold_results: list[FoldResult] = []
    all_returns: list[pd.Series] = []
    prev_top: list[str] = []

    rets_daily = prices_local_usd.pct_change()

    for tr_s, tr_e, te_s, te_e in folds_dates:
        signal_date = pd.Timestamp(tr_e)
        # Compute price factors at signal_date
        price_factors = compute_price_factors(prices_local_usd, signal_date, benchmark_prices)
        # Join with fundamentals
        scores_df = fundamentals.copy()
        for col in price_factors.columns:
            scores_df[col] = price_factors[col]

        # Pick weight scheme
        chosen = weight_scheme
        if pick_data_driven:
            # Forward 3-month return ending at signal date (in-train, not in-test)
            look_start = signal_date - pd.DateOffset(months=3)
            try:
                ret_window = prices_local_usd.loc[look_start:signal_date]
                if len(ret_window) >= 30:
                    fwd_ret = (ret_window.iloc[-1] / ret_window.iloc[0]) - 1.0
                    chosen, _ic = pick_best_scheme_by_ic(scores_df, fwd_ret, neutrality)
            except Exception as e:
                log.warning("data-driven pick failed: %s", e)

        weights = WEIGHT_SCHEMES.get(chosen, WEIGHT_SCHEMES["baseline"])
        top_df = _select_top_n(scores_df, weights, neutrality, top_n, apply_floors)
        if top_df.empty:
            log.warning("WF[%s] fold %s-%s: no stocks selected", label, te_s.date(), te_e.date())
            continue

        # Build test-window returns
        test_rets = rets_daily.loc[te_s:te_e, top_df.index.intersection(rets_daily.columns)]
        # Apply equal weighting; drop columns with all NaN
        valid = test_rets.dropna(how="all", axis=1)
        if valid.shape[1] == 0:
            continue
        w = top_df["weight"].reindex(valid.columns).fillna(0)
        w = w / w.sum()
        daily_ret = valid.fillna(0).mul(w, axis=1).sum(axis=1)

        # Turnover cost on entry (assume we liquidate previous holdings + buy new)
        new = set(top_df.index)
        old = set(prev_top)
        if old:
            replaced = len(new ^ old) / max(1, len(new) + len(old))
            turnover = (len(new ^ old)) / (2 * len(new))  # one-side turnover
        else:
            turnover = 1.0  # initial buy is 100% turnover
        cost = turnover * 2 * costs_bps_one_way / 1e4  # round-trip
        # Apply cost on day 1 of test
        if len(daily_ret) > 0:
            first_idx = daily_ret.index[0]
            daily_ret.loc[first_idx] = daily_ret.loc[first_idx] - cost

        fold_results.append(FoldResult(
            train_start=tr_s, train_end=tr_e, test_start=te_s, test_end=te_e,
            weight_scheme=chosen, n_held=len(top_df), top_tickers=list(top_df.index),
            daily_returns=daily_ret, turnover=turnover,
        ))
        all_returns.append(daily_ret)
        prev_top = list(top_df.index)

    if not all_returns:
        return WalkForwardResult(folds=[], daily_returns=pd.Series(dtype=float),
                                  weight_schemes_used=[], label=label)
    stitched = pd.concat(all_returns).sort_index()
    stitched = stitched[~stitched.index.duplicated(keep="first")]
    return WalkForwardResult(
        folds=fold_results,
        daily_returns=stitched,
        weight_schemes_used=[f.weight_scheme for f in fold_results],
        label=label,
    )
