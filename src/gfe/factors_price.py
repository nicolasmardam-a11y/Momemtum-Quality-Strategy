"""Price-based factors for global equity ranking.

All factors take a wide DataFrame of daily adjusted closes (index=Date, cols=tickers)
and an evaluation date `asof`. They look BACK only — no future data used.

Factors:
- Momentum 12-1 (12m return excluding last month): mom_12_1
- Momentum 6m: mom_6m
- Momentum 3m: mom_3m
- Short-term reversal (1m return, neg sign): rev_1m
- Risk-adjusted momentum (12-1 / 12m vol): risk_adj_mom
- Distance to 52w high: dist_52w_high (negative = below high)
- Trend strength (price / SMA200 - 1): trend_sma200

- Realized vol 252d ann: vol_1y
- Realized vol 63d ann: vol_3m
- Downside semivol 252d ann: downvol_1y
- Max drawdown 252d: maxdd_1y
- Idiosyncratic vol (residual to MSCI World proxy URTH if provided, else market median): idio_vol
- Beta to URTH/SPY proxy (one of: URTH, SPY, ACWI): beta_market

Returned as a tidy DataFrame indexed by ticker for the given asof date.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .utils import get_logger

log = get_logger("factors_price")

TRADING_DAYS_YEAR = 252
TRADING_DAYS_MONTH = 21
TRADING_DAYS_QUARTER = 63
TRADING_DAYS_52W = 252


def _slice_window(prices: pd.DataFrame, asof: pd.Timestamp, lookback_days: int) -> pd.DataFrame:
    """Return prices[asof - lookback_days : asof] inclusive."""
    end = asof
    start_idx_pos = prices.index.searchsorted(end, side="right")
    if start_idx_pos == 0:
        return prices.iloc[:0]
    end_pos = start_idx_pos
    start_pos = max(0, end_pos - lookback_days - 1)
    return prices.iloc[start_pos:end_pos]


def _ret_window(prices: pd.DataFrame, asof: pd.Timestamp, lookback_days: int, skip_last: int = 0) -> pd.Series:
    """Total return over [asof - lookback_days - skip_last, asof - skip_last]."""
    win = _slice_window(prices, asof, lookback_days + skip_last + 1)
    if win.shape[0] < 2:
        return pd.Series(np.nan, index=prices.columns)
    if skip_last == 0:
        first = win.iloc[0]
        last = win.iloc[-1]
    else:
        first = win.iloc[0]
        if skip_last >= len(win):
            return pd.Series(np.nan, index=prices.columns)
        last = win.iloc[-(skip_last + 1)]
    ret = (last / first) - 1.0
    return ret


def compute_momentum_factors(prices: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Compute all price-momentum / trend factors for `asof`."""
    out = pd.DataFrame(index=prices.columns)
    # 12-1: 12m ret skipping last 1m
    out["mom_12_1"] = _ret_window(prices, asof, 12 * TRADING_DAYS_MONTH, skip_last=TRADING_DAYS_MONTH)
    out["mom_6m"] = _ret_window(prices, asof, 6 * TRADING_DAYS_MONTH)
    out["mom_3m"] = _ret_window(prices, asof, 3 * TRADING_DAYS_MONTH)
    out["rev_1m"] = _ret_window(prices, asof, TRADING_DAYS_MONTH) * -1.0  # higher = better (reversal of weak)

    # Risk-adjusted mom = mom_12_1 / annualized vol over 12m
    win_12 = _slice_window(prices, asof, 12 * TRADING_DAYS_MONTH)
    rets_12 = win_12.pct_change().dropna(how="all")
    vol_12 = rets_12.std(ddof=0) * np.sqrt(TRADING_DAYS_YEAR)
    out["risk_adj_mom"] = out["mom_12_1"] / vol_12.replace(0, np.nan)

    # Distance to 52w high (negative = below high)
    win_52 = _slice_window(prices, asof, TRADING_DAYS_52W)
    if not win_52.empty:
        latest = win_52.iloc[-1]
        hi = win_52.max()
        out["dist_52w_high"] = (latest / hi) - 1.0
    else:
        out["dist_52w_high"] = np.nan

    # Trend SMA200: price / SMA200 - 1
    win_200 = _slice_window(prices, asof, 200)
    if win_200.shape[0] >= 50:
        sma200 = win_200.mean()
        out["trend_sma200"] = (win_200.iloc[-1] / sma200) - 1.0
    else:
        out["trend_sma200"] = np.nan

    return out


def compute_risk_factors(prices: pd.DataFrame, asof: pd.Timestamp,
                         benchmark_prices: pd.Series | None = None) -> pd.DataFrame:
    """Realized vol, downside vol, max drawdown, beta, idio-vol."""
    out = pd.DataFrame(index=prices.columns)
    win_252 = _slice_window(prices, asof, TRADING_DAYS_YEAR)
    rets_252 = win_252.pct_change().dropna(how="all")
    if rets_252.empty:
        return out
    # 1y vol (annualized)
    out["vol_1y"] = rets_252.std(ddof=0) * np.sqrt(TRADING_DAYS_YEAR)
    # 3m vol
    rets_63 = win_252.iloc[-TRADING_DAYS_QUARTER:].pct_change().dropna(how="all") if len(win_252) >= TRADING_DAYS_QUARTER else rets_252
    out["vol_3m"] = rets_63.std(ddof=0) * np.sqrt(TRADING_DAYS_YEAR)
    # Downside vol 1y
    neg = rets_252.where(rets_252 < 0, 0.0)
    out["downvol_1y"] = neg.std(ddof=0) * np.sqrt(TRADING_DAYS_YEAR)

    # Max drawdown over 1y
    cum = (1 + rets_252).cumprod()
    peak = cum.cummax()
    dd = (cum / peak) - 1.0
    out["maxdd_1y"] = dd.min()

    # Beta to benchmark
    if benchmark_prices is not None:
        bench_win = benchmark_prices.reindex(win_252.index).ffill()
        bench_rets = bench_win.pct_change().dropna()
        common = rets_252.index.intersection(bench_rets.index)
        if len(common) >= 60:
            br = bench_rets.loc[common]
            br_var = br.var(ddof=0)
            if br_var > 0:
                # Covariance per ticker
                ar = rets_252.loc[common]
                cov = ar.apply(lambda x: x.cov(br, ddof=0))
                out["beta_market"] = cov / br_var
                # Idiosyncratic vol = residual std after removing beta*market
                residual = ar.subtract(out["beta_market"] * br, axis=0)
                out["idio_vol"] = residual.std(ddof=0) * np.sqrt(TRADING_DAYS_YEAR)
            else:
                out["beta_market"] = np.nan
                out["idio_vol"] = out["vol_1y"]
        else:
            out["beta_market"] = np.nan
            out["idio_vol"] = out["vol_1y"]
    else:
        out["beta_market"] = np.nan
        out["idio_vol"] = out["vol_1y"]

    return out


def compute_price_factors(prices: pd.DataFrame, asof: pd.Timestamp,
                          benchmark_prices: pd.Series | None = None) -> pd.DataFrame:
    """Convenience: momentum + risk factors merged for a given asof date."""
    mom = compute_momentum_factors(prices, asof)
    risk = compute_risk_factors(prices, asof, benchmark_prices)
    return mom.join(risk, how="outer")
