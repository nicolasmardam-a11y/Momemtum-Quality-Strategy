"""Daily data refresh + overlay update. PAPER/READ-ONLY (no orders).

Keeps the FROZEN overlay model's INPUTS current (the model itself is
unchanged: 60d vol-target 10% x URTH/EEM 200d trend):

  1. Refresh URTH + EEM to today (yfinance) -> trend filter uses live data.
  2. Extend the strategy NAKED return series: for every trading day after
     the series' last date, append the equal-weight USD daily return of the
     current top-50 book constituents (the backtest's naked construction,
     pre-overlay -> no circularity with the exposure scalar). The trailing
     60d vol window therefore rolls forward on real recent market moves.
  3. Recompute + persist the overlay exposure; write a dated overlay report.

Idempotent: only appends dates not already present; safe to run repeatedly.
All consumers (paper bot, recommender, dashboard) already read
equity/full_pit_naked_returns.csv, so this single file is the source of truth.
"""
from __future__ import annotations
import json, sys, warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
import pandas as pd
from logger import get_logger
from config_loader import load_config
from overlay_engine import OverlayEngine

NAKED = ROOT / "equity/full_pit_naked_returns.csv"
NAKED_BACKUP = ROOT / "equity/full_pit_naked_returns.backtest_frozen.csv"
BENCH = ROOT / "data/prices/benchmarks_wide.parquet"
EEMP = ROOT / "data/prices/EEM.parquet"
FXH = ROOT / "data/fx/fx_history.parquet"
PORT = ROOT / "reports/production/current_portfolio_clean.csv"


def refresh_benchmarks(log):
    """Append latest URTH into benchmarks_wide and refresh EEM.parquet."""
    import yfinance as yf
    bench = pd.read_parquet(BENCH)
    if isinstance(bench.columns, pd.MultiIndex):
        bench.columns = bench.columns.get_level_values(0)
    bench.index = pd.to_datetime(bench.index)
    last = bench.index[-1]
    for sym in [c for c in bench.columns]:
        try:
            h = yf.Ticker(sym).history(period="3mo")
        except Exception:
            continue
        if h.empty:
            continue
        h.index = pd.to_datetime(h.index).tz_localize(None)
        new = h["Close"][h.index > last]
        for d, v in new.items():
            bench.loc[d, sym] = float(v)
    bench = bench.sort_index()
    bench.to_parquet(BENCH)

    eem = pd.read_parquet(EEMP)
    if isinstance(eem.columns, pd.MultiIndex):
        eem.columns = eem.columns.get_level_values(0)
    eem.index = pd.to_datetime(eem.index)
    h = yf.Ticker("EEM").history(period="3mo")
    h.index = pd.to_datetime(h.index).tz_localize(None)
    addn = h[h.index > eem.index[-1]]
    for d, row in addn.iterrows():
        for col in eem.columns:
            if col in h.columns:
                eem.loc[d, col] = float(row[col])
    eem.sort_index().to_parquet(EEMP)
    log.info("benchmarks refreshed: URTH/EEM -> %s",
             pd.read_parquet(BENCH).index.max())


def extend_naked_returns(log) -> int:
    """Append equal-weight USD daily naked returns of the current 50 book
    names for every date after the series end. Returns #days appended."""
    import yfinance as yf
    s = pd.read_csv(NAKED, parse_dates=[0], index_col=0)
    col = s.columns[0]
    last = s.index[-1]
    if not NAKED_BACKUP.exists():
        s.to_csv(NAKED_BACKUP)                # one-time frozen backtest backup
        log.info("backed up frozen backtest naked series -> %s", NAKED_BACKUP.name)

    tickers = pd.read_csv(PORT)["ticker"].tolist()
    px = yf.download(tickers, period="4mo", interval="1d",
                     progress=False, group_by="column")["Close"]
    if isinstance(px.columns, pd.MultiIndex):
        px.columns = px.columns.get_level_values(-1)
    px.index = pd.to_datetime(px.index).tz_localize(None)

    # FX: USD per 1 local unit (constant latest rate -> level cancels in
    # returns; equity moves dominate the 60d vol estimate).
    fx = pd.read_parquet(FXH).ffill().iloc[-1]
    sm = pd.read_csv(ROOT / "reports/production/security_master.csv").set_index("ticker")
    usd = pd.DataFrame(index=px.index)
    for t in tickers:
        if t not in px.columns:
            continue
        ccy = sm.loc[t, "currency"] if t in sm.index else "USD"
        rate = 1.0 if ccy == "USD" else float(fx.get(ccy, np.nan))
        if rate != rate or rate <= 0:
            rate = 1.0
        usd[t] = px[t] * rate
    rets = usd.pct_change()
    naked = rets.mean(axis=1, skipna=True)            # equal-weight
    new = naked[naked.index > last].dropna()
    appended = 0
    for d, v in new.items():
        s.loc[d, col] = float(v)
        appended += 1
    s.sort_index().to_csv(NAKED)
    log.info("naked series extended: +%d day(s) -> last %s (was %s)",
             appended, pd.read_csv(NAKED, parse_dates=[0], index_col=0).index[-1].date(),
             last.date())
    return appended


def main() -> int:
    date = datetime.now().strftime("%Y-%m-%d")
    log = get_logger(date)
    log.info("=== DAILY UPDATE start (%s) — refresh inputs + overlay ===", date)
    try:
        refresh_benchmarks(log)
    except Exception as e:
        log.error("benchmark refresh failed (continuing): %r", e)
    try:
        n = extend_naked_returns(log)
    except Exception as e:
        log.error("naked-series extension failed: %r", e)
        n = 0

    cfg = load_config(mode="signal_only")
    ov = OverlayEngine(cfg, log)
    r = ov.compute()
    ov.persist(r["exposure"], r["asof"])
    out = {
        "run_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "naked_days_appended": n,
        "overlay": {k: r[k] for k in
                    ("asof", "exposure", "vol_scalar", "trend_scalar",
                     "urth_above_sma", "eem_above_sma", "prior_exposure",
                     "exposure_change")},
    }
    rp = ROOT / "reports/daily" / f"{date}_overlay.json"
    rp.write_text(json.dumps(out, indent=2, default=str))
    log.info("OVERLAY updated: asof=%s exposure=%.4f (vol=%.3f trend=%.0f) "
             "URTH %s EEM %s | change=%s",
             r["asof"], r["exposure"], r["vol_scalar"], r["trend_scalar"],
             ">" if r["urth_above_sma"] else "<",
             ">" if r["eem_above_sma"] else "<", r["exposure_change"])
    log.info("=== DAILY UPDATE done -> %s ===", rp.name)
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
