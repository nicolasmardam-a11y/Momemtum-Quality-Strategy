"""Approximate replication of the rolling-minimum "mean-reversion" backtest in
Vojtko & Dujava (2026) / Quantpedia blog 2026-04-17, on CLOB /prices-history 10-minute
series fetched by quantpedia_mr_fetch.py.

Rule as described in the source (Sec. 3.3): long when price <= X-day rolling minimum,
hold exactly Y days, exit, no overlap, full reinvestment. X in {5,10,20}, Y in {1,2,3,5}.
Costs: 0 or 0.1% per trade (0.2% round trip). Metrics follow the source: CAR, annualised
vol, Sharpe = CAR/vol (0% rf), MaxDD, Calmar = CAR/|MaxDD|. Vol is computed on 10-minute
equity returns annualised with 365*144 periods, which is the convention that reproduces
the source's buy-and-hold vol and drawdown figures (see notes).

Execution is at the observed series price at the signal bar and at the first bar >= Y days
later. This is the same optimistic assumption the source makes: the series is a trade/mid
price, not an executable bid/ask, so these are NOT executable-price results.

Variants:
  raw     : series as fetched (contains a one-bar print on 2025-12-27 01:10 UTC in China
            and Alien where No trades at 0.756 / 0.779 between bars at ~0.9985)
  clean   : bars whose |return| > 15% and that fully revert on the next bar are forward-filled
  raw_lag1: raw series, entry at the bar AFTER the signal bar (10-minute latency); this is the
            configuration that reproduces the source's Tables 3-8 (China/Alien to ~0.1 pp CAR)
  clean_lag1: clean series with the 1-bar entry lag
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "derived" / "literature_checks"
PER_YEAR = 365 * 144
CUTOFF = pd.Timestamp("2026-01-01", tz="UTC")


def load(name: str) -> pd.Series:
    s = pd.read_parquet(D / f"qp_mr_{name}_no_10min.parquet").set_index("time")["p"].astype(float)
    return s[s.index < CUTOFF]


def clean(s: pd.Series, thr: float = 0.15) -> pd.Series:
    r = s.pct_change()
    nxt = s.shift(-1) / s - 1
    bad = (r.abs() > thr) & (nxt.abs() > thr) & (np.sign(r) != np.sign(nxt))
    out = s.copy()
    out[bad] = np.nan
    return out.ffill()


def metrics(eq: pd.Series) -> dict:
    yrs = (eq.index[-1] - eq.index[0]).total_seconds() / (365.25 * 86400)
    car = (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1
    vol = eq.pct_change().dropna().std() * np.sqrt(PER_YEAR)
    mdd = (eq / eq.cummax() - 1).min()
    return {"CAR": car, "vol": vol, "Sharpe": car / vol if vol > 0 else np.nan, "MaxDD": mdd,
            "Calmar": car / abs(mdd) if mdd < 0 else np.nan}


def backtest(s: pd.Series, X: int, Y: int, fee: float = 0.0, lag: int = 0) -> tuple[pd.Series, list[dict]]:
    p = s.values
    t = s.index
    rmin = s.rolling(f"{X}D").min().values
    sig = p <= rmin + 1e-12
    # only allow signals once a full X-day lookback exists
    sig &= (t - t[0]) >= pd.Timedelta(days=X)
    eq = np.ones(len(p))
    cash = 1.0
    i = 0
    trades = []
    n = len(p)
    tv = t.values
    while i < n:
        if sig[i] and i + lag < n:
            e = i + lag
            exit_time = tv[e] + np.timedelta64(Y, "D")
            j = int(np.searchsorted(tv, exit_time, side="left"))
            if j >= n:
                j = n - 1
            entry = p[e]
            units = cash * (1 - fee) / entry
            eq[i:e + 1] = cash
            for k in range(e, j + 1):
                eq[k] = units * p[k]
            cash = units * p[j] * (1 - fee)
            eq[j] = cash
            trades.append({"entry_time": t[e], "entry": entry, "exit_time": t[j], "exit": p[j],
                           "ret": (p[j] / entry) * (1 - fee) ** 2 - 1})
            i = j + 1
            if i < n:
                eq[i:] = cash
        else:
            eq[i] = cash
            i += 1
    return pd.Series(eq, index=t), trades


def main() -> None:
    rows = []
    trade_rows = []
    for name in ["jesus", "china", "alien"]:
        raw = load(name)
        cl = clean(raw)
        for var, ser, lag in [("raw", raw, 0), ("raw_lag1", raw, 1), ("clean", cl, 0), ("clean_lag1", cl, 1)]:
            bh = metrics(ser)
            rows.append({"contract": name, "variant": var, "X": "B&H", "Y": "", "fee": 0.0, "n_trades": 1, **bh})
            for fee in [0.0, 0.001]:
                for X in [5, 10, 20]:
                    for Y in [1, 2, 3, 5]:
                        eq, tr = backtest(ser, X, Y, fee, lag)
                        m = metrics(eq)
                        top = max(tr, key=lambda d: d["ret"]) if tr else None
                        rows.append({"contract": name, "variant": var, "X": X, "Y": Y, "fee": fee,
                                     "n_trades": len(tr), "best_trade_ret": top["ret"] if top else np.nan,
                                     "best_trade_entry": top["entry_time"] if top else None, **m})
                        if var == "raw" and fee == 0.0:
                            for d in tr:
                                trade_rows.append({"contract": name, "X": X, "Y": Y, **d})
    res = pd.DataFrame(rows)
    res.to_csv(D / "qp_mr_replication.csv", index=False)
    pd.DataFrame(trade_rows).to_parquet(D / "qp_mr_trades_raw.parquet", index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 500)
    show = res.copy()
    for c in ["CAR", "vol", "MaxDD", "best_trade_ret"]:
        show[c] = (100 * show[c]).round(2)
    for c in ["Sharpe", "Calmar"]:
        show[c] = show[c].round(2)
    print(show.drop(columns=["best_trade_entry"]).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
