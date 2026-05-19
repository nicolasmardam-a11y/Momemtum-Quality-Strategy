# Global Equity Bot v2.5 — Daily Strategy Check (account-decoupled)

Minimal, self-contained bundle to **re-run the model and produce a daily
stats/performance snapshot** on a remote machine or a scheduled Claude agent.
**No broker. No orders. No live trading.** Public market data only (yfinance).

## What it does

`python scripts/daily_strategy_check.py` will, each run:

1. Refresh the risk-overlay inputs from public data (URTH/EEM + the 50-name
   book closes via yfinance) and recompute the exposure overlay — delegated
   to `scripts/daily_update.py`. Idempotent; extends the naked-return series
   forward by any new trading days.
2. Write a self-contained dashboard snapshot to
   `reports/dashboard/<YYYY-MM-DD>/` and mirror it to
   `reports/dashboard/latest/`:
   - `index.html` — full dashboard (opens with no server)
   - `snapshot.md` — git-diffable summary
   - `metrics.json` — machine-readable stats
   - plus the overlay JSON and the frozen 50-name book CSV

Stats produced: overlay exposure %, action band, vol scalar, URTH/EEM trend
state, validated metrics (overlay vs naked vs benchmarks: CAGR, vol, Sharpe,
Sortino, MaxDD, Calmar), annual returns, rolling 1y/3y Sharpe, geography &
sector mix, country PnL, crisis subperiods, and data-freshness markers.

## Run

```bash
pip install -r requirements.txt
python scripts/daily_strategy_check.py
```

Read `reports/dashboard/latest/metrics.json` for the headline stats, or open
`reports/dashboard/latest/index.html`.

## Requirements / caveats

- **Python ≥ 3.11**, deps in `requirements.txt`.
- **Internet required** for a *fresh* run (yfinance). Offline, it still emits
  a snapshot from the seeded data but flags `daily_update_rc != 0` (stale
  overlay) — treat that as a connectivity warning, not fresh stats.
- Fully **account-decoupled**: it never imports `ib_async`, never connects
  IBKR/any broker, never places/cancels orders. Safe to run anywhere.
- The 50-name stock book is **frozen** (quarterly reconstitution); the
  daily-varying part is the risk overlay. The routine refreshes the overlay
  and re-renders — it does **not** re-rank daily.

## Suggested scheduled-agent prompt

> In this repo, run `python scripts/daily_strategy_check.py` (research only —
> do NOT connect a broker or place orders). Then read
> `reports/dashboard/latest/metrics.json` and report: date, exposure %,
> action band, rolling Sharpe 1y/3y, validated metrics, data freshness, and
> `daily_update_rc` (flag prominently if non-zero = stale data). Keep it
> under ~200 words.

---

_Simulated / research. **Not investment advice. No live trading.** All
performance figures are hypothetical backtest/paper results._
