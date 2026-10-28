"""Signal and portfolio construction for the three strategies.

A  short suspected ramps          -> order-level EventBacktester (backtest.py)
B  early-warning liquidation       -> long momentum book with an exit overlay
C  cross-sectional crash ranking   -> long book that drops the top-risk decile

Target-weight frames use NaN for "no instruction today" (hold drifted weight);
numbers are trade-to targets. Rebalance rows are full rows.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def month_end_dates(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(dates, index=dates)
    return pd.DatetimeIndex(s.groupby([dates.year, dates.month]).max().to_numpy())


# ---------------------------------------------------------------------------
# Strategy A
# ---------------------------------------------------------------------------
def alert_signals(preds: pd.DataFrame, df: pd.DataFrame, model: str, tgt: str = "dd20_40") -> pd.DataFrame:
    P = preds.merge(df[["date", "code", "candidate"]], on=["date", "code"])
    m = P[f"alert__{model}__{tgt}"] & P["candidate"]
    return P.loc[m, ["date", "code"]].assign(score=P.loc[m, f"p__{model}__{tgt}"].to_numpy())


def naive_signals(df: pd.DataFrame, lo, hi, ret_20_min: float = 1.0) -> pd.DataFrame:
    """Short anything up >= 100% in 20 days on abnormal value: the simple rule."""
    m = df["candidate"] & (df["ret_20"] >= np.log1p(ret_20_min)) & df["date"].between(lo, hi)
    return df.loc[m, ["date", "code"]].assign(score=df.loc[m, "ret_20"].to_numpy())


def random_signals(df: pd.DataFrame, lo, hi, n: int, seed: int = 0) -> pd.DataFrame:
    pool = df[df["candidate"] & df["date"].between(lo, hi)]
    if len(pool) == 0 or n == 0:
        return pd.DataFrame(columns=["date", "code", "score"])
    s = pool.sample(min(n, len(pool)), random_state=seed)
    return s[["date", "code"]].assign(score=np.random.default_rng(seed).random(len(s)))


# ---------------------------------------------------------------------------
# Strategies B and C
# ---------------------------------------------------------------------------
def investable(close: pd.DataFrame, adv: pd.DataFrame, min_adv: float, min_price: float) -> pd.DataFrame:
    return (adv >= min_adv) & (close >= min_price)


def momentum_members(close: pd.DataFrame, inv: pd.DataFrame, rebal: pd.DatetimeIndex,
                     top: int = 50, lookback: int = 120, skip: int = 5) -> dict:
    mom = np.log(close.shift(skip) / close.shift(lookback + skip))
    out = {}
    for d in rebal:
        s = mom.loc[d].where(inv.loc[d]).dropna()
        out[d] = list(s.nlargest(top).index)
    return out


def targets_from_members(members: dict, index: pd.DatetimeIndex, columns: pd.Index,
                         exits: pd.DataFrame | None = None, cooldown: int = 20) -> pd.DataFrame:
    """Equal-weight targets at each rebalance; optional exit overlay.

    exits: wide bool (date x code) alerts. An alerted holding is sold the
    next day and may not be re-bought for `cooldown` trading days; the cash is
    held until the next rebalance (no reallocation, which keeps the overlay's
    effect isolated).
    """
    T = pd.DataFrame(np.nan, index=index, columns=columns)
    block = pd.DataFrame(False, index=index, columns=columns)
    if exits is not None:
        e = exits.reindex(index=index, columns=columns).fillna(False).astype(bool)
        block = e.astype(float).rolling(cooldown, min_periods=1).max().astype(bool)
    held: set = set()
    rebal = set(members)
    for d in index:
        if d in rebal:
            names = [c for c in members[d] if not block.at[d, c]]
            row = pd.Series(0.0, index=columns)
            if names:
                row[names] = 1.0 / len(members[d])  # unfilled slots stay in cash
            T.loc[d] = row.to_numpy()
            held = set(names)
        elif exits is not None and held:
            hit = [c for c in held if e.at[d, c]]
            if hit:
                T.loc[d, hit] = 0.0
                held -= set(hit)
    return T


def risk_ranked_members(p: pd.DataFrame, inv: pd.DataFrame, rebal: pd.DatetimeIndex,
                        exclude_top: float = 0.10) -> tuple[dict, dict, dict]:
    """Members of: full universe, universe minus top-risk decile, top-risk decile."""
    full, low, high = {}, {}, {}
    for d in rebal:
        if d not in p.index:
            continue
        s = p.loc[d].where(inv.loc[d]).dropna()
        if len(s) < 20:
            continue
        cut = s.quantile(1 - exclude_top)
        full[d], low[d], high[d] = list(s.index), list(s[s < cut].index), list(s[s >= cut].index)
    return full, low, high


def avoided_loss_table(exits: pd.DataFrame, held_mask: pd.DataFrame, close: pd.DataFrame,
                       horizon: int = 20) -> pd.DataFrame:
    """For each alert on a held stock: realised return over the next `horizon`
    days from t+1 close (the conservative exit point). Negative = loss avoided,
    positive = opportunity cost of a false alert."""
    fwd = close.shift(-(horizon + 1)) / close.shift(-1) - 1
    e = exits.reindex_like(close).fillna(False).astype(bool) & held_mask.reindex_like(close).fillna(False)
    s = fwd.where(e).stack().dropna()
    return s.rename("fwd_ret").reset_index()


def block_bootstrap_p(diff: pd.Series, block: int = 20, n: int = 2000, seed: int = 0) -> float:
    """One-sided p-value that mean(diff) <= 0 using a circular block bootstrap."""
    x = diff.dropna().to_numpy()
    if len(x) < 2 * block:
        return np.nan
    rng = np.random.default_rng(seed)
    T = len(x)
    xc = x - x.mean()
    k = int(np.ceil(T / block))
    means = np.empty(n)
    for i in range(n):
        starts = rng.integers(0, T, k)
        idx = (starts[:, None] + np.arange(block)[None]).ravel()[:T] % T
        means[i] = xc[idx].mean()
    return float((means >= x.mean()).mean())
