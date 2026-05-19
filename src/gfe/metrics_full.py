"""Full performance metric suite + acceptance gate evaluation."""
from __future__ import annotations

import numpy as np
import pandas as pd


def annualize_return(daily: pd.Series, periods: int = 252) -> float:
    if len(daily) == 0:
        return float("nan")
    total = (1 + daily).prod()
    years = len(daily) / periods
    if years <= 0 or total <= 0:
        return float("nan")
    return total ** (1 / years) - 1


def annualize_vol(daily: pd.Series, periods: int = 252) -> float:
    if len(daily) < 2:
        return float("nan")
    return float(daily.std(ddof=0) * np.sqrt(periods))


def sharpe(daily: pd.Series, rf_annual: float = 0.0, periods: int = 252) -> float:
    if len(daily) < 30:
        return float("nan")
    rf_daily = rf_annual / periods
    excess = daily - rf_daily
    vol = excess.std(ddof=0)
    if vol <= 0:
        return float("nan")
    return float(excess.mean() / vol * np.sqrt(periods))


def sortino(daily: pd.Series, rf_annual: float = 0.0, periods: int = 252) -> float:
    if len(daily) < 30:
        return float("nan")
    rf_daily = rf_annual / periods
    excess = daily - rf_daily
    down = excess.where(excess < 0, 0.0)
    dvol = down.std(ddof=0)
    if dvol <= 0:
        return float("nan")
    return float(excess.mean() / dvol * np.sqrt(periods))


def max_drawdown(daily: pd.Series) -> float:
    if len(daily) < 2:
        return float("nan")
    cum = (1 + daily).cumprod()
    peak = cum.cummax()
    dd = (cum / peak) - 1.0
    return float(dd.min())


def drawdown_series(daily: pd.Series) -> pd.Series:
    cum = (1 + daily).cumprod()
    peak = cum.cummax()
    return (cum / peak) - 1.0


def calmar(daily: pd.Series, periods: int = 252) -> float:
    mdd = max_drawdown(daily)
    cagr = annualize_return(daily, periods)
    if mdd is None or mdd == 0 or np.isnan(mdd):
        return float("nan")
    return float(cagr / abs(mdd))


def skewness(daily: pd.Series) -> float:
    if len(daily) < 30:
        return float("nan")
    return float(daily.skew())


def kurtosis_metric(daily: pd.Series) -> float:
    if len(daily) < 30:
        return float("nan")
    return float(daily.kurt())


def drawdown_duration_days(daily: pd.Series) -> int:
    """Longest underwater stretch in calendar days."""
    if daily.empty:
        return 0
    cum = (1 + daily).cumprod()
    peak = cum.cummax()
    underwater = cum < peak
    if not underwater.any():
        return 0
    # Find longest run
    groups = (underwater != underwater.shift()).cumsum()
    runs = underwater.groupby(groups).agg(["sum", "first"])
    runs = runs[runs["first"] == True]
    if runs.empty:
        return 0
    return int(runs["sum"].max())


def rolling_sharpe(daily: pd.Series, window_days: int = 252) -> pd.Series:
    excess = daily
    rs = excess.rolling(window_days).apply(
        lambda x: x.mean() / x.std(ddof=0) * np.sqrt(252) if x.std(ddof=0) > 0 else np.nan
    )
    return rs


def rolling_metric_summary(daily: pd.Series, window_years: int = 3) -> dict:
    rs = rolling_sharpe(daily, window_years * 252)
    valid = rs.dropna()
    if len(valid) == 0:
        return {"pct_3y_positive": float("nan"), "min_3y_sharpe": float("nan"),
                "median_3y_sharpe": float("nan")}
    return {
        "pct_3y_positive": float((valid > 0).mean()),
        "min_3y_sharpe": float(valid.min()),
        "median_3y_sharpe": float(valid.median()),
    }


def metrics_dict(daily: pd.Series, label: str = "", periods: int = 252) -> dict:
    if daily.empty:
        return {"label": label, "n_days": 0}
    return {
        "label": label,
        "n_days": int(len(daily)),
        "start": str(daily.index[0].date()),
        "end": str(daily.index[-1].date()),
        "cagr": annualize_return(daily, periods),
        "vol": annualize_vol(daily, periods),
        "sharpe": sharpe(daily, periods=periods),
        "sortino": sortino(daily, periods=periods),
        "max_dd": max_drawdown(daily),
        "calmar": calmar(daily, periods=periods),
        "skew": skewness(daily),
        "kurt": kurtosis_metric(daily),
        "dd_duration_days": drawdown_duration_days(daily),
        **rolling_metric_summary(daily, 3),
    }


# ------------- subperiod analysis -------------
SUBPERIODS: dict[str, tuple[str, str]] = {
    "2011_euro": ("2011-04-01", "2012-06-30"),
    "2015_16_china": ("2015-08-01", "2016-02-29"),
    "2018_q4": ("2018-10-01", "2018-12-31"),
    "2020_covid": ("2020-02-01", "2020-04-30"),
    "2022_rate_shock": ("2022-01-01", "2022-12-31"),
    "2023_2026_recent": ("2023-01-01", "2026-05-13"),
}


def subperiod_metrics(daily: pd.Series) -> pd.DataFrame:
    rows = []
    for name, (s, e) in SUBPERIODS.items():
        win = daily.loc[s:e]
        if win.empty:
            continue
        rows.append({"period": name, **metrics_dict(win, label=name)})
    return pd.DataFrame(rows)


# ------------- regime analysis -------------
def split_by_regime(daily: pd.Series, benchmark_daily: pd.Series, sma_days: int = 200) -> dict:
    """Split into up-trend / down-trend based on benchmark SMA filter."""
    bench_eq = (1 + benchmark_daily).cumprod()
    sma = bench_eq.rolling(sma_days).mean()
    up_mask = bench_eq > sma
    common = daily.index.intersection(up_mask.index)
    up = daily.loc[common][up_mask.loc[common]]
    down = daily.loc[common][~up_mask.loc[common]]
    return {
        "up_regime": metrics_dict(up, "up_regime"),
        "down_regime": metrics_dict(down, "down_regime"),
        "pct_days_up": float(up_mask.loc[common].mean()) if len(common) > 0 else float("nan"),
    }


# ------------- concentration / attribution -------------
def stock_pnl_contribution(holdings_history: pd.DataFrame, prices_usd: pd.DataFrame) -> pd.DataFrame:
    """holdings_history: cols=[date, ticker, weight] (rebalance snapshots).
    Returns per-ticker pnl approx assuming weights held between rebalances."""
    if holdings_history.empty:
        return pd.DataFrame()
    holdings_history = holdings_history.sort_values("date")
    pnl_per_ticker: dict[str, float] = {}
    rebal_dates = sorted(holdings_history["date"].unique())
    for i, d0 in enumerate(rebal_dates):
        d1 = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else prices_usd.index[-1]
        snap = holdings_history[holdings_history["date"] == d0]
        for _, row in snap.iterrows():
            tk, w = row["ticker"], row["weight"]
            if tk not in prices_usd.columns:
                continue
            seg = prices_usd[tk].loc[d0:d1].dropna()
            if len(seg) < 2:
                continue
            ret = seg.iloc[-1] / seg.iloc[0] - 1
            pnl_per_ticker[tk] = pnl_per_ticker.get(tk, 0.0) + ret * w
    return pd.Series(pnl_per_ticker).sort_values(ascending=False).to_frame("pnl_contrib")


def concentration_stats(holdings_history: pd.DataFrame, prices_usd: pd.DataFrame,
                        universe_meta: pd.DataFrame) -> dict:
    """Top stock / country / sector contribution shares."""
    pnl_df = stock_pnl_contribution(holdings_history, prices_usd)
    if pnl_df.empty:
        return {"top10_stock_share": float("nan"), "top_country_share": float("nan"),
                "top_sector_share": float("nan"), "total_pnl": float("nan")}
    pos_pnl = pnl_df[pnl_df["pnl_contrib"] > 0]
    total = pos_pnl["pnl_contrib"].sum()
    if total <= 0:
        return {"top10_stock_share": float("nan"), "top_country_share": float("nan"),
                "top_sector_share": float("nan"), "total_pnl": float(total)}
    top10 = pos_pnl["pnl_contrib"].sort_values(ascending=False).head(10).sum() / total
    # Country / sector
    meta = universe_meta.set_index("ticker") if "ticker" in universe_meta.columns else universe_meta
    pnl_df = pnl_df.copy()
    pnl_df["country"] = meta["country"].reindex(pnl_df.index).fillna("Unknown")
    pnl_df["sector"] = meta["sector_hint"].reindex(pnl_df.index).fillna("Unknown")
    country_pnl = pnl_df.groupby("country")["pnl_contrib"].sum()
    sector_pnl = pnl_df.groupby("sector")["pnl_contrib"].sum()
    pos_c = country_pnl[country_pnl > 0]
    pos_s = sector_pnl[sector_pnl > 0]
    top_c = pos_c.max() / pos_c.sum() if pos_c.sum() > 0 else float("nan")
    top_s = pos_s.max() / pos_s.sum() if pos_s.sum() > 0 else float("nan")
    return {
        "top10_stock_share": float(top10),
        "top_country_share": float(top_c),
        "top_sector_share": float(top_s),
        "total_positive_pnl": float(total),
    }


# ------------- acceptance gates -------------
def evaluate_gates(metrics: dict, concentration: dict, gates: dict,
                    benchmark_metrics: dict | None = None) -> dict:
    """Return dict with per-gate pass/fail."""
    result = {}
    result["pass_sharpe"] = metrics.get("sharpe", -np.inf) >= gates.get("oos_sharpe_min", 0.0)
    result["pass_calmar"] = metrics.get("calmar", -np.inf) >= gates.get("oos_calmar_min", 0.0)
    mdd = abs(metrics.get("max_dd", -1.0))
    result["pass_mdd"] = mdd <= gates.get("max_dd_max", 1.0)
    result["pass_top10_stock"] = (
        pd.notna(concentration.get("top10_stock_share")) and
        concentration["top10_stock_share"] <= gates.get("top10_stock_profit_share_max", 1.0)
    )
    result["pass_top_country"] = (
        pd.notna(concentration.get("top_country_share")) and
        concentration["top_country_share"] <= gates.get("top_country_profit_share_max", 1.0)
    )
    result["pass_top_sector"] = (
        pd.notna(concentration.get("top_sector_share")) and
        concentration["top_sector_share"] <= gates.get("top_sector_profit_share_max", 1.0)
    )
    if benchmark_metrics is not None:
        result["pass_beat_bench_sharpe"] = metrics.get("sharpe", 0) > benchmark_metrics.get("sharpe", 0)
        result["pass_beat_bench_calmar"] = metrics.get("calmar", 0) > benchmark_metrics.get("calmar", 0)
    result["all_pass"] = all(v for k, v in result.items() if k.startswith("pass_"))
    return result
