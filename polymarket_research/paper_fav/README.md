# paper_fav: automated paper trader for "favourites ≥ 0.95 at T−7d"

Automates the forward test of the only marginal directional strategy in `REPORT.md` (rule E2 in
`notes/strategies/flb_near_resolution.md`). **It is read-only.** It needs no wallet, no keys and no account,
and nothing in it can place an order. Every "trade" is a paper position priced from the real order book.

## What one run does (`python -m paper_fav.run all`)

1. **Scan.** It lists open binary markets from Gamma and computes each market's decision time
   D = anchor − 7 days, where the anchor is `gameStartTime` (sports) or else `endDate`. It then decides each
   market **once**, while now is inside [D, D + 3 h]:
   - **favourite:** the side whose fresh CLOB book midpoint is ≥ 0.95;
   - **paper fill:** walk that side's real asks for the stake ($20 by default), charging the market's own
     `feeSchedule` fee on each level;
   - **record:** a paper position if the all-in cost per share is ≤ 0.999 (the tested rule). The book
     snapshot is stored with it as provenance;
   - otherwise the reason is recorded (`no_favourite`, `infeasible`, `not_tradable`).

   Markets first seen after their window are recorded as `missed` and never traded, so an outage cannot
   create look-ahead. Markets created after D are `unlisted`, because the backtest could not have priced them
   either. If a book fetch fails, the market stays undecided and is retried next run while still in its window.
2. **Resolve.** It settles open positions from Gamma once their markets close. 50-50 pays 0.5, and disputes
   are flagged.
3. **Score.** It applies the kill rule and sends notices: one per new paper signal, a daily scorecard and a
   KILL alert. Each notice is sent once (deduplicated in SQLite).

## Run it

```bash
cd polymarket_research
python -m paper_fav.run all --dry-run                  # one run, console output only
python -m paper_fav.run report                         # print the scorecard
python -m pytest paper_fav/tests -q                    # 18 offline tests
```

**Schedule it hourly** on any always-on machine. Nothing is set up here; this is how you would do it:

```cron
5 * * * *  cd /path/to/polymarket_research && /usr/bin/python3 -m paper_fav.run all >> data/derived/paper_fav/cron.log 2>&1
```

- **Duration.** A run takes about 5–6 minutes, mostly waiting on polite rate limits. It pages about 70k
  Gamma markets, because sports `endDate` can be days after kick-off, and fetches fresh books for the
  ~4k markets that are due.
- **Missed runs.** With a 3 h decision window, an hourly schedule tolerates two missed runs without losing
  signals.
- **Notifications.** Console and `data/derived/paper_fav/notices.ndjson` by default. For Telegram or email,
  set `telegram: true` / `email: true` in a copy of `config.example.yaml`, and the same environment variables
  as `alerts/` (`PM_ALERT_TELEGRAM_BOT`, `PM_ALERT_TELEGRAM_CHAT`, or `PM_ALERT_SMTP_*`). Credentials are read
  only from the environment.

## Reading the scorecard

| Subset | Meaning |
|---|---|
| `all` | The rule exactly as pre-registered |
| `core` | **Liquid** (volume ≥ $10k or book liquidity ≥ $5k) **and tight** (spread ≤ 2¢). This is the version comparable to the backtest's positive liquid sample. **Judge the strategy on this one.** |
| `wide_or_thin` | Everything else. The first live run found mids of 0.95–0.96 on 6–7¢ spreads, so fills paid ~3¢ over mid against ~0.7¢ assumed in the backtest. Expect this subset to fail. |
| `exact_score` | Soccer exact-score markets. They appeared only in the 2026 test period, so they are tracked separately. |

- **k** is realised losses ÷ price-implied losses, where implied = Σ(1 − fill price) and a 50-50 counts as
  half a loss. The backtest estimate was **0.54 [0.36, 0.78]**; break-even after costs was **~0.79** in liquid
  markets.
- **Kill rule.** Proposed by the audit, post hoc, and fixed here before any outcome was seen: stop if
  losses > 0.75 × implied once implied ≥ 5. Status `collecting` until then, then `passing` or `killed`.
- **Slippage flag** (my addition). It fires if the median fill pays > 0.5¢ over the book midpoint after
  ≥ 30 signals.
- **Sample size.** About 23 implied losses (~1,200 core trades) are needed to separate k = 0.54 from
  break-even with reasonable confidence. The FLB note asks for at least 3 months.

## Data and files

| Path | Holds |
|---|---|
| `data/derived/paper_fav/paper_fav.sqlite` | `decisions` (every market decided once, with status), `signals` (paper positions, book snapshot, fill, fee, slippage, capacity at $100/$500/$2.5k, resolution), `runs` (each run's counts and errors), `notices` |
| `client.py` | Thin HTTP client; raises `DataError` so a failed run is never mistaken for "no signals" (exit code 2 plus a DATA PROBLEM notice) |
| `rules.py` | Pure rule logic |
| `scan.py`, `resolve.py`, `stats.py`, `run.py` | Scan, settlement, kill rule and scorecard, CLI |

## Not done here (by design)

- **No live orders.** Automating execution would need a funded Polymarket wallet, signing keys and CLOB API
  credentials, and you must confirm you may trade on Polymarket from your jurisdiction (`REPORT.md` §1).
  It should be considered only if `core` reaches `passing` with enough data, and only with your explicit
  approval.
- **No maker variant.** Resting bids instead of paying the ask needs queue-aware fill modelling from recorded
  books (`REPORT.md` D3).
