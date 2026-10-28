# HKEX ramp-and-dump research

Can abnormal trading behaviour in Hong Kong equities predict the dump phase of
ramp-and-dump episodes, and can that be turned into positive net returns at
realistic size? This package covers the data, the detector, four competing
models, an execution-aware backtester and a pre-registered GO/NO-GO test.

**Research only. Never connects to a broker or places orders.**

**Verdict:** see [`docs/07_go_no_go_memo.md`](docs/07_go_no_go_memo.md).

## Deliverables

| # | Deliverable | Where |
|---|---|---|
| 1 | Feasibility, data audit, vendor costs | [`docs/01_feasibility.md`](docs/01_feasibility.md), [`docs/data_requirements.md`](docs/data_requirements.md) |
| 2 | Five ranked, falsifiable hypotheses | [`docs/02_hypotheses.md`](docs/02_hypotheses.md) |
| 3 | Daily event-detection algorithm | [`src/hkrd/events.py`](src/hkrd/events.py), [`docs/03_event_detection.md`](docs/03_event_detection.md) |
| 4 | Event database and case figures | `outputs/research/event_db.csv`, `outputs/figures/` |
| 5 | Predictive models with OOS metrics | [`src/hkrd/models.py`](src/hkrd/models.py), [`docs/04_models.md`](docs/04_models.md) |
| 6 | Execution-aware backtest (A/B/C) | [`src/hkrd/backtest.py`](src/hkrd/backtest.py), [`docs/05_backtests.md`](docs/05_backtests.md) |
| 7 | Live monitoring design and daily watchlist | [`docs/06_live_monitoring.md`](docs/06_live_monitoring.md), [`scripts/daily_watchlist.py`](scripts/daily_watchlist.py) |
| 8 | GO/NO-GO memo | [`docs/07_go_no_go_memo.md`](docs/07_go_no_go_memo.md) |

Pre-registered criteria: [`config/go_no_go.yaml`](config/go_no_go.yaml). It
was committed before any model or backtest result existed; check with
`git log -- hk_ramp_dump/config/go_no_go.yaml`.

## Run

```bash
cd hk_ramp_dump
pip install -r requirements.txt
python scripts/fetch_pilot_data.py           # ~15 min: HKEX lists, 631 short-sell lists, Yahoo prices
python scripts/run_research.py all           # events (~7 min), dataset (~4 min), walk-forward models (~15 min)
python scripts/run_backtests.py              # strategies A/B/C on OOS predictions (~3 min)
python scripts/run_holdout.py                # ONCE: refuses unless go_no_go.yaml is committed and unmodified
python scripts/daily_watchlist.py            # after 16:10 HKT: today's risk-ranked watchlist
python -m pytest -q tests                    # 34 unit and integration tests
```

Runs on a 4-core, 16 GB machine with no GPU (peak RAM about 6 GB).

## Layout

```
config/research.yaml      every threshold, sample split, cost and borrow assumption
config/go_no_go.yaml      pre-registered acceptance criteria and selection rule
src/hkrd/
  data.py                 vendor adapters -> canonical panel; quality mask; raw-price factor
  hkex.py                 dated tick tables, stamp duty/fees/levies, sessions, board lots
  events.py               ramp-and-dump episode detector, categories A/B/C, sensitivity grid
  features.py             causal features (price, liquidity, distribution) and forward labels
  models.py               A rules | B HMM (forward-filtered) | C LightGBM | D two-stage
  validation.py           purged walk-forward, embargo, event grouping, PR-AUC, bootstrap
  backtest.py             order-level engine (shorts) and weight-based engine (long books)
  strategies.py           signals and portfolio construction for strategies A, B, C
  pipeline.py, runners.py the steps used by the scripts
scripts/                  fetch, research, backtests, holdout, daily watchlist
tests/                    causality, purging, costs, ticks, suspensions, end-to-end smoke tests
data/reference/           current universe, SFC case list (small, committed)
outputs/                  event DB, metrics, backtests, figures (parquet stores are gitignored)
```

## Honesty notes

- The pilot uses Yahoo prices for **current listings only**. Delisted stocks
  are missing, a survivorship bias whose direction is discussed in every
  document. The survivorship-free route (Webb-site CC-BY dump) is specified
  in docs/01.
- No historical borrow data exists in the pilot. Borrow fees, locate
  failures and recalls are explicit assumptions, stress-tested at 2x and 4x.
- All reported figures are computed by the code in this repository on that
  data. No result is illustrative.
