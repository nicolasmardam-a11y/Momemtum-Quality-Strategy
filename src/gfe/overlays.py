"""Risk overlays for the long-only equity composite.

Implemented:
- vol_target: scale daily exposure so realized portfolio vol matches a target
- trend_filter: on/off based on benchmark SMA (binary; same as defensive_rotation)
- trend_hysteresis: trend filter with off-on band to reduce whipsaws
- combo: take min(trend, vol_target_scaling); the more conservative wins

All operate on a stream of pre-cost daily returns + the daily exposure scalar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def vol_target_overlay(daily_rets: pd.Series, target_vol_annual: float = 0.10,
                       lookback_days: int = 60,
                       max_exposure: float = 1.0,
                       min_exposure: float = 0.0) -> pd.Series:
    """Compute daily exposure scalar to target target_vol_annual.

    exposure_t = min(target_vol / realized_vol_t-1, max_exposure)

    Returns a Series aligned to daily_rets.index.
    """
    realized_vol = daily_rets.rolling(lookback_days).std(ddof=0) * np.sqrt(252)
    realized_vol = realized_vol.shift(1)  # use yesterday's vol to size today
    exposure = (target_vol_annual / realized_vol).clip(lower=min_exposure, upper=max_exposure)
    return exposure.fillna(1.0)  # no signal yet -> full exposure


def trend_filter(benchmark_prices: pd.Series, sma_days: int = 200,
                  dates: pd.DatetimeIndex | None = None) -> pd.Series:
    """Return 1/0 series: 1 when benchmark > SMA(sma_days), else 0.

    Result shifted by 1 day to avoid look-ahead.
    """
    sma = benchmark_prices.rolling(sma_days).mean()
    sig = (benchmark_prices > sma).astype(float).shift(1).fillna(1.0)
    if dates is not None:
        sig = sig.reindex(dates).ffill().fillna(1.0)
    return sig


def trend_hysteresis(benchmark_prices: pd.Series, sma_days: int = 200,
                     on_band: float = 0.0, off_band: float = -0.03,
                     dates: pd.DatetimeIndex | None = None) -> pd.Series:
    """Hysteresis trend filter: only switch OFF when price < SMA*(1+off_band),
       only switch ON when price > SMA*(1+on_band). Default off_band=-3% means
       must drop 3% below SMA before exit.
    """
    sma = benchmark_prices.rolling(sma_days).mean()
    rel = benchmark_prices / sma - 1.0
    state = pd.Series(1.0, index=benchmark_prices.index)
    cur = 1.0
    for i in range(len(rel)):
        v = rel.iloc[i]
        if np.isnan(v):
            state.iloc[i] = 1.0
            continue
        if cur > 0.5 and v < off_band:
            cur = 0.0
        elif cur < 0.5 and v > on_band:
            cur = 1.0
        state.iloc[i] = cur
    state = state.shift(1).fillna(1.0)
    if dates is not None:
        state = state.reindex(dates).ffill().fillna(1.0)
    return state


def multi_asset_trend(prices_dict: dict[str, pd.Series], sma_days: int = 200,
                       n_required: int = 2, dates: pd.DatetimeIndex | None = None) -> pd.Series:
    """Multi-asset trend: OFF only when >= n_required of the assets are below SMA.

    prices_dict: e.g. {"URTH": urth, "EFA": efa, "EEM": eem, "HYG": hyg}
    """
    states = {}
    for name, p in prices_dict.items():
        sma = p.rolling(sma_days).mean()
        on = (p > sma).astype(float)
        states[name] = on
    df = pd.concat(states, axis=1)
    n_on = df.sum(axis=1, skipna=False)
    n_total = df.notna().sum(axis=1)
    # OFF when n_off >= n_required, equivalently when n_on <= n_total - n_required
    overlay = (n_on > (n_total - n_required)).astype(float).shift(1).fillna(1.0)
    if dates is not None:
        overlay = overlay.reindex(dates).ffill().fillna(1.0)
    return overlay


def apply_overlay_to_returns(raw_rets: pd.Series, exposure: pd.Series,
                              flip_cost_bps: float = 5.0) -> tuple[pd.Series, pd.Series]:
    """Multiply raw_rets by exposure each day; apply cost on |delta exposure|.

    flip_cost_bps: cost when exposure changes by 100% (full flip).
    Cost on a partial change of d% is (d/100) * flip_cost_bps.
    """
    exposure = exposure.reindex(raw_rets.index).ffill().fillna(1.0)
    overlayed = raw_rets * exposure
    flips = exposure.diff().abs().fillna(0)
    cost = flips * (flip_cost_bps / 1e4)
    return overlayed - cost, exposure


def vol_target_with_trend(raw_rets: pd.Series, benchmark_prices: pd.Series,
                            target_vol: float = 0.10,
                            sma_days: int = 200,
                            lookback_days: int = 60,
                            max_exposure: float = 1.0,
                            min_exposure: float = 0.0,
                            flip_cost_bps: float = 5.0) -> tuple[pd.Series, pd.Series]:
    """Combine: take min(trend filter, vol_target scaling).

    When trend off: exposure = 0 (full cash).
    When trend on:  exposure = min(target_vol / realized_vol, max_exposure).
    """
    vt = vol_target_overlay(raw_rets, target_vol_annual=target_vol,
                             lookback_days=lookback_days,
                             max_exposure=max_exposure, min_exposure=min_exposure)
    tr = trend_filter(benchmark_prices, sma_days=sma_days, dates=raw_rets.index)
    combined = vt * tr  # if trend off -> 0
    return apply_overlay_to_returns(raw_rets, combined, flip_cost_bps=flip_cost_bps)
