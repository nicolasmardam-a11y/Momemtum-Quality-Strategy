"""Causal daily features and forward labels.

Every feature at row (code, t) uses only open/high/low/close/volume on days
<= t, i.e. information available after the close of t. Execution is assumed
no earlier than the opening auction of t+1. Labels use days > t only.

Features are computed on wide (date x code) float32 frames for speed and
then stacked to long format.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .events import BASELINE_FLOOR_HKD
from .hkex import tick_size_array

FEATURE_GROUPS = {
    "price": ["ret_1", "ret_3", "ret_5", "ret_10", "ret_20", "ret_60", "accel_5", "dist_ma20",
              "dist_ma60", "dist_high20", "dist_high60", "days_since_high60", "gap_1",
              "intraday_1", "close_loc_1", "upper_wick_5", "close_strength_5",
              "vol_ratio_20_120", "excess_ret_20", "max_ret_1_in_20"],
    "liquidity": ["value_ratio_1", "value_ratio_5", "value_ratio_20", "value_z_120",
                  "value_trend_5_20", "value_per_abs_ret_5", "down_value_share_10",
                  "log_value_20", "zero_days_120", "amihud_60", "spread_ar_20",
                  "tick_rel", "log_price"],
    "distribution": ["failed_highs_10", "reversal_on_volume_5", "high_volume_near_high_10",
                     "drawdown_from_runpeak"],
}
FEATURES = [f for g in FEATURE_GROUPS.values() for f in g]


def _f32(x: pd.DataFrame) -> pd.DataFrame:
    return x.astype(np.float32)


def wide_features(o, h, l, c, v, market: pd.Series | None, base_win: int = 120,
                  raw_close: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Return {feature_name: wide frame}. Inputs are wide frames (date x code).

    `raw_close` is the price actually traded (adjusted x raw_factor); price-level
    features (tick size, log price) use it. Defaults to `c` when unavailable.
    """
    raw = c if raw_close is None else raw_close
    F: dict[str, pd.DataFrame] = {}
    lc = np.log(c)
    for w in (1, 3, 5, 10, 20, 60):
        F[f"ret_{w}"] = lc - lc.shift(w)
    F["accel_5"] = F["ret_5"] - F["ret_5"].shift(5)
    F["dist_ma20"] = c / c.rolling(20, min_periods=15).mean() - 1
    F["dist_ma60"] = c / c.rolling(60, min_periods=40).mean() - 1
    hi20 = h.rolling(20, min_periods=10).max()
    hi60 = h.rolling(60, min_periods=30).max()
    F["dist_high20"] = c / hi20 - 1
    F["dist_high60"] = c / hi60 - 1
    F["days_since_high60"] = _days_since_max(c, 60)
    F["gap_1"] = np.log(o / c.shift(1))
    F["intraday_1"] = np.log(c / o)
    rng = (h - l).where(h > l)
    F["close_loc_1"] = ((2 * c - h - l) / rng).fillna(0)
    F["upper_wick_5"] = ((h - np.maximum(o, c)) / rng).fillna(0).rolling(5, min_periods=3).mean()
    F["close_strength_5"] = F["close_loc_1"].rolling(5, min_periods=3).mean()
    r1 = F["ret_1"]
    F["vol_ratio_20_120"] = r1.rolling(20, min_periods=15).std() / r1.rolling(120, min_periods=60).std()
    F["max_ret_1_in_20"] = r1.rolling(20, min_periods=10).max()
    if market is not None:
        m = np.log(market.reindex(c.index).ffill())
        F["excess_ret_20"] = F["ret_20"].sub(m - m.shift(20), axis=0)
    else:
        F["excess_ret_20"] = F["ret_20"]

    vv = v.fillna(0)
    base = vv.shift(1).rolling(base_win, min_periods=base_win // 2).median().clip(lower=BASELINE_FLOOR_HKD)
    for w in (1, 5, 20):
        F[f"value_ratio_{w}"] = np.log1p(vv.rolling(w, min_periods=1).mean() / base)
    lv = np.log1p(vv)
    F["value_z_120"] = (lv - lv.shift(1).rolling(base_win, min_periods=60).mean()) / \
        lv.shift(1).rolling(base_win, min_periods=60).std()
    F["value_trend_5_20"] = np.log1p(vv.rolling(5).mean()) - np.log1p(vv.rolling(20).mean())
    F["value_per_abs_ret_5"] = F["value_ratio_5"] / (1 + 10 * F["ret_5"].abs())
    down = (r1 < 0).astype(float)
    F["down_value_share_10"] = (vv * down).rolling(10).sum() / vv.rolling(10).sum().replace(0, np.nan)
    F["log_value_20"] = np.log1p(vv.rolling(20, min_periods=10).mean())
    F["zero_days_120"] = (vv <= 0).astype(float).rolling(base_win, min_periods=60).mean()
    F["amihud_60"] = np.log1p((r1.abs() / vv.replace(0, np.nan) * 1e6).rolling(60, min_periods=20).median())
    F["spread_ar_20"] = _abdi_ranaldo(h, l, c, 20)
    F["log_price"] = np.log(raw)
    ticks = tick_size_array(raw.to_numpy().ravel(), np.repeat(raw.index.to_numpy(), raw.shape[1]))
    F["tick_rel"] = pd.DataFrame(ticks.reshape(raw.shape), index=raw.index, columns=raw.columns) / raw

    # Distribution-phase hypotheses
    prev_hi20 = h.shift(1).rolling(20, min_periods=10).max()
    near_high = (h >= 0.97 * prev_hi20)
    F["failed_highs_10"] = (near_high & (c < prev_hi20) & (c <= o)).astype(float).rolling(10).sum()
    vr1 = F["value_ratio_1"]
    F["reversal_on_volume_5"] = ((F["close_loc_1"] < -0.3) & (vr1 > np.log1p(3))).astype(float).rolling(5).sum()
    F["high_volume_near_high_10"] = (near_high & (vr1 > np.log1p(5))).astype(float).rolling(10).sum()
    F["drawdown_from_runpeak"] = c / c.rolling(20, min_periods=10).max() - 1
    return {k: _f32(x) for k, x in F.items()}


def _days_since_max(c: pd.DataFrame, w: int) -> pd.DataFrame:
    mx = c.rolling(w, min_periods=w // 2).max()
    out = pd.DataFrame(np.nan, index=c.index, columns=c.columns)
    for k in range(w):
        out = out.mask(out.isna() & (c.shift(k) >= mx), float(k))
    return out


def _abdi_ranaldo(h, l, c, w: int) -> pd.DataFrame:
    """Abdi & Ranaldo (2017) close-high-low effective spread estimator."""
    eta = (np.log(h) + np.log(l)) / 2
    # Original pairs (t, t+1); the causal version pairs (t-1, t) so row t uses days <= t.
    s2 = 4 * (np.log(c.shift(1)) - eta.shift(1)) * (np.log(c.shift(1)) - eta)
    return np.sqrt(s2.clip(lower=0).rolling(w, min_periods=w // 2).mean())


def forward_labels(c: pd.DataFrame, o: pd.DataFrame, horizons: list[int], dd_h: int,
                   dd_thresholds: list[float]) -> dict[str, pd.DataFrame]:
    """Labels measured from close t (prediction) and from open t+1 (trading)."""
    L: dict[str, pd.DataFrame] = {}
    for hz in horizons:
        L[f"fwd_ret_{hz}"] = c.shift(-hz) / c - 1
    # min close over t+1..t+dd_h relative to close t
    fut_min = c[::-1].rolling(dd_h, min_periods=1).min()[::-1].shift(-1)
    fut_max = c[::-1].rolling(dd_h, min_periods=1).max()[::-1].shift(-1)
    complete = c.shift(-dd_h).notna()
    mdd = (fut_min / c - 1).where(complete)
    L["fwd_min_ret_20"] = mdd
    L["fwd_max_ret_20"] = (fut_max / c - 1).where(complete)
    for th in dd_thresholds:
        L[f"dd20_{int(th * 100)}"] = (mdd <= -th).astype(float).where(complete)
    # trading-relevant: from the t+1 open
    o1 = o.shift(-1)
    L["fwd_ret_open_20"] = c.shift(-dd_h) / o1 - 1
    # days until a 20% decline from close t (censored at dd_h -> NaN)
    L["days_to_dd20"] = _days_to_threshold(c, 0.20, dd_h)
    return {k: _f32(x) for k, x in L.items()}


def _days_to_threshold(c: pd.DataFrame, th: float, h: int) -> pd.DataFrame:
    out = pd.DataFrame(np.nan, index=c.index, columns=c.columns)
    hit = pd.DataFrame(False, index=c.index, columns=c.columns)
    for k in range(1, h + 1):
        cond = (c.shift(-k) / c - 1 <= -th) & ~hit
        out = out.mask(cond, k)
        hit |= cond
    return out


def stack(frames: dict[str, pd.DataFrame], rows: pd.DataFrame | None = None) -> pd.DataFrame:
    """Stack wide frames into a long frame indexed by (date, code)."""
    cols = {}
    for k, f in frames.items():
        s = f.stack(future_stack=True)
        cols[k] = s
    df = pd.DataFrame(cols)
    df.index.names = ["date", "code"]
    if rows is not None:
        df = df.loc[df.index.intersection(rows.index)]
    return df
