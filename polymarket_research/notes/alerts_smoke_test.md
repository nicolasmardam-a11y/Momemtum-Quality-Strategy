# Live smoke test of the read-only alert system (`alerts/`), 2026-10-18

> **Nothing has been deployed. Monitoring is NOT active.** Every run below was a foreground
> process started by hand with `--dry-run` and stopped by `--max-cycles` (no process is left running:
> `ps aux | grep alerts.run` finds nothing). Only the **console** and **file** notifiers were used.
> No Telegram or email message was sent; no `PM_ALERT_*`, Telegram or SMTP variable was set (checked with `env`).
> All data is public and read-only. No keys, no wallet connection, no orders, no copying.

Run 05:38–06:07 UTC on 2026-10-18 from the research sandbox (one IP, unknown region). Databases, logs
and the alert file are in `data/derived/alerts_smoke/` (git-ignored). Scripts: `analyses/alerts_smoke/`.

## 0. Verdicts

| Check | Result | Verdict |
|---|---|---|
| Test suite at start (resume check) | `python -m pytest alerts/tests -q`: **106 passed** | OK |
| 1. History of mintblade, GRIMDRIP, endlessFate rebuilt | fills 732 / 672 / 480 = notes' TRADE + REDEEM counts; per-market fills, shares, notional, fees, VWAP, first/last fill **identical** to `notes/wallets/` tables (16 markets) | **PASS** |
| 1b. Re-run is idempotent | 1,884 rows re-read, 0 new fills, 0 new alerts | **PASS** |
| 2. 16 min of running on 3 busy wallets (3 chunks, 35 cycles, 05:41–06:03 UTC) | 35/35 cycles all polls OK; 72 bet alerts + 2 ALERT CAP notices delivered | **PASS** |
| 2. Detection lag (fill seen − block timestamp), steady state | n = 602 fills: p50 **16.3 s**, p90 **28.7 s**, max **34.9 s** | as designed (30 s ± 5 s polling) |
| 2. Duplicates | **0** duplicate deliveries (148 = 74 alerts × 2 channels, each sent once, 0 POSSIBLE DUPLICATE); 0 duplicate fills | **PASS** |
| 2. DATA PROBLEM events | 1: `/v2/positions` 400 for a **Combo** id (enrichment only; auto-resolved, not notified) | real issue, **fixed (S1)** |
| 3. 5-min outage, restart, independent `/v2/trades` pull | outage window 329 rows: **329 stored, 0 missing**; whole window 3,763 rows: 0 missing, 0 extra; same 4 min later | **PASS** |
| Tests after the fix | **108 passed**, pyflakes clean; the new test fails without the fix | OK |

## 1. Resume check (interrupted attempt)

- `alerts/`: git shows the round-2 review files (`instance.py`, `logsafe.py`, `tests/test_review_round2.py` untracked, others modified).
  They match README §20. The suite passed (106) and pyflakes was clean, so no half-applied edit was found.
- `data/derived/alerts_smoke/` held an interrupted attempt from 05:33–05:34 UTC. Moved unchanged to
  `data/derived/alerts_smoke/interrupted_20261018T0533/`. **That attempt (and README §20.4) used `--backfill-hours 2000`,
  i.e. a window from 2026-07-26.** The candidates traded only from 2026-06-03 to 2026-07-08. So their "ok, no new trades" result did not
  exercise history reconstruction. Step 1 below does.

## 2. Step 1: history of the three candidate wallets

Config `data/derived/alerts_smoke/hist.yaml` is `alerts/config.example.yaml` with only the file and DB paths changed
(thresholds `min_usdc: 1000`, bootstrap alerts off).

```
python -m alerts.run --config data/derived/alerts_smoke/hist.yaml --once --dry-run --backfill-hours 8760   # exit 0, 3 s
poll mintblade: ok, 732 new fill(s) (rows=732 pages=2 from 2025-10-18 05:39:27Z, bootstrap)
poll GRIMDRIP: ok, 672 new fill(s) (rows=672 pages=2 from 2025-10-18 05:39:28Z, bootstrap)
poll endlessFate: ok, 480 new fill(s) (rows=480 pages=1 from 2025-10-18 05:39:28Z, bootstrap)
cycle done: 0 alert(s) created, 21 suppressed; deliveries {'sent': 0, ...}
# second identical run: rows=732/672/480, "ok, no new trades", 0 alerts created, exit 0
```

8,760 h reaches 2025-10-18, before all three profiles existed. The full history needs at least about 3,300 h,
which reaches back to mintblade's first fill on 2026-06-03. With the default `initial_backfill_hours: 24`, history is not rebuilt.

Reconstructed BUY totals per market (from the `bets` table) against the notes:

| Wallet | Market → outcome | Fills | Shares | Notional $ | Fees $ | VWAP | First–last fill (UTC) | Matches notes |
|---|---|---|---|---|---|---|---|---|
| mintblade | Mets ML → Mets | 1 | 5 | 5 | 0 | 0.96 | 06-03 21:18:42 | yes (below $1k threshold) |
| mintblade | Uruguay win → No | 36 | 2,152,994 | 786,362 | 14,973 | 0.3652 | 06-15 21:54:45–22:00:01 | yes |
| mintblade | Spread URU −1.5 → Saudi | 11 | 1,053,072 | 659,999 | 7,390 | 0.6267 | 21:56:04–21:58:49 | yes |
| mintblade | Draw → Yes | 5 | 187,501 | 45,000 | 1,026 | 0.2400 | 21:57:52–21:59:21 | yes |
| mintblade | Iran win → No | 674 | 14,366,351 | 7,031,554 | 104,008 | 0.4894 | 06-16 00:17:22–01:04:03 | yes |
| GRIMDRIP | Czechia win → No | 650 | 9,925,592 | 4,941,811 | 72,278 | 0.4979 | 06-18 15:23:20–16:00:16 | yes |
| GRIMDRIP | Czechia–RSA draw → Yes | 20 | 3,678,377 | 1,060,000 | 22,633 | 0.2882 | 15:26:13–15:57:23 | yes |
| endlessFate | 9 markets (Korea, Bosnia, USA–PAR draw, Türkiye spread, Belgium, URU spread, KSA–URU draw, Uruguay, Colombia) | 17/10/50/10/2/9/15/9/352 | | | | | | **all 9 rows identical** (shares, notional, fees, VWAP, span) |

- Taker fills (fee embedded in `usdc_size`) are 166 / 93 / 138, equal to the notes' taker counts. Summed fees: mintblade $127,397.56, equal to `user-stats fees_paid`.
  The other fills are stored as `unknown`, not `maker`: the maker cross-check only runs when an alert is built, and bootstrap bets are suppressed.
  This is conservative and correct.
- 21 BUY bets: 15 `new_position` + 6 `addition`, because grouping splits a market's fills at gaps over 10 min. 13 REDEEM records.
  All are suppressed as "bootstrap baseline" (by design: history is never alerted). The $5 Mets ticket is `below_threshold`.
- Example stored record: `[suppressed] mintblade BUY No on Will IR Iran win on 2026-06-15?: $7,135,562.01 executed 2026-06-16 00:17:22Z`.
  $7,135,562 = notional $7,031,554 + fees $104,008.

## 3. Step 2: live run on wallets trading now

**Wallet choice** (`analyses/alerts_smoke/01_find_active.py`, global `/v2/trades?taker_only=false`, cache-busted, at 05:40 UTC).
The newest 5,000 rows covered only 138 s. I profiled seven busy wallets over the past hour with `/v2/activity` and picked three styles:

| Label | Address | Last hour (rows) | Style |
|---|---|---|---|
| GoalLineGhost | `0x0346afae2603313d2bbee96b628536c8cbe352a5` | 474 (384 TRADE, 90 REDEEM), ~$34k bought, 217 markets | sports |
| norm1e69 | `0x41e2e1ccf1e4940029af02259a31c6b89b9fa354` | 1,216 (1,171 TRADE), 40 markets | 5-/15-min crypto up/down |
| w38791873984189 | `0x0d2d845a6ff64e31e04a70afce8a573940767ff5` | 1,066 (655 TRADE, 315 REDEEM, 89 MERGE, 7 CONVERSION), 470 markets | tennis/sports, **Combos** |

Config `data/derived/alerts_smoke/active.yaml` = example config with these wallets, plus three changes: `min_usdc: 25` (global),
`initial_backfill_hours: 1` and smoke paths. Everything else is default: 30 s ± 5 s interval, 600 s overlap, cache-bust on, alert cap 30/wallet/hour.

```
python -m alerts.run --config data/derived/alerts_smoke/active.yaml --dry-run --max-cycles 13   # chunk A 05:41:38-05:47:54, exit 0
python -m alerts.run --config data/derived/alerts_smoke/active.yaml --dry-run --max-cycles 13   # chunk B 05:48:06-05:54:13, exit 0
#   ---- stopped 5 min 11 s (outage, step 3) ----
python -m alerts.run --config data/derived/alerts_smoke/active.yaml --dry-run --max-cycles 9    # chunk C 05:59:24-06:03:15, exit 0
python analyses/alerts_smoke/02_analyze_db.py <db> <ndjson> <stdouts> <run windows>             # lags, duplicates, health
```

Each command was wrapped in `timeout -s TERM 520` as a guard; none hit it. Trimmed log:

```
cycle 1: 3/3 wallet polls ok, 0 new alert(s), 296 suppressed     # bootstrap baseline (1 h, 2,757 rows)
cycle 2: 3/3 wallet polls ok, 5 new alert(s), 0 suppressed
...
05:50:43 WARNING DATA PROBLEM data-api enrichment/invalid_request (x1): alert enrichment failed: invalid_request HTTP 400
         from data-api /v2/positions: invalid condition id: 0x037a734069bd6aa8e2d3876752879da2cd0000000000000000000000000000
...
cycle 13: 3/3 wallet polls ok, 2 new alert(s), 2 suppressed       # chunk B; suppressed = alert cap
```

Restart recovery between chunks A and B (a 12 s stop) also worked: B resumed from the stored watermark.

### 3.1 Alerts produced

| | Count |
|---|---|
| Bet alerts delivered (console + file) | **72** (40 new position, 32 addition). GoalLineGhost 22, norm1e69 20, w38791873984189 30 |
| ALERT CAP notices | 2 (w38791873984189 reached 30 alerts by 05:51:49; the second notice came at 06:00, see §6.3) |
| Suppressed bet records | 322 = 296 bootstrap baseline + 26 over the alert cap |
| Below threshold (< $25) / non-BUY bets recorded only | 212 / 712 (526 REDEEM, 106 MERGE, 72 SELL, 8 CONVERSION) |
| Spend per alerted bet | min $25.02, median $89.55, max $1,585.05 |
| Alert content | 72/72 maker/taker cross-checks complete ("every fill checked against the taker-only feed"); 0 outcome-label mismatches; 1 enrichment error (the Combo); 28 in-play |

### 3.2 Detection lag (detection time − execution timestamp)

The execution timestamp is the Data API `timestamp`, which is the **block time** (integer seconds, floored).
Block time is about 2.2 s after the CLOB match (`notes/platform/data_infrastructure.md` §3.3), so add about 2 s for lag from the match.
"Steady state" excludes fills executed within 40 s before a stop.

| Measure | n | min | p10 | p50 | p90 | p99 | max |
|---|---|---|---|---|---|---|---|
| Fill first stored − block ts, all wallets | 602 | 0.6 | 3.9 | **16.3** | **28.7** | 32.4 | 34.9 |
|  GoalLineGhost | 88 | 1.9 | 5.8 | 15.0 | 28.5 | 32.2 | 34.9 |
|  norm1e69 | 346 | 0.6 | 3.2 | 16.3 | 28.5 | 32.4 | 34.4 |
|  w38791873984189 | 168 | 1.5 | 4.1 | 16.7 | 29.6 | 31.6 | 32.9 |
| Alert: newest fill seen − its block ts | 54 | 1.2 | | 13.5 | 27.2 | | 31.4 |
| Alert: built − newest fill block ts (what a reader sees) | 54 | 2.9 | | **16.3** | **31.2** | | 37.3 |
| Enrichment time (built − detected) | 54 | 1.0 | | 2.2 | 4.6 | | 6.8 |

This matches README §14 ("block → alert median ≈ 20 s, p90 ≈ 35 s, worst ≈ 45 s") and is set by the 30 s poll phase.
That is roughly 8× slower than the public RTDS `activity` websocket: about 18 s versus a median 2.2 s from the match
(data_infrastructure.md §0). The fastest polled detections (0.6–2 s after the floored block second) are consistent with the
Data API ingestion delay measured there (busted `/v2/trades?user` poll: median lower bound 1.33 s, upper bound 3.56 s).

### 3.3 Duplicates

- **Deliveries: 0 duplicates.** 74 alerts × 2 channels = 148 deliveries, all `sent` once, `possible_duplicate` = 0.
  The file channel has 74 lines with 74 distinct `alert_id`s. Console headers: 72 `[NEW BET DETECTED]` + 2 `[ALERT CAP]`.
- **Fills: 0 duplicates.** 8 (tx, token, side, size, price, ts, type) keys occur more than once in the DB: equal-size maker fills in one transaction,
  and repeated MERGE rows. The independent pull shows the **same multiplicities**, so these are genuine repeats, not double inserts.
- 18 bets have two alert rows by design: a `bet:<id>:suppressed` baseline record and one delivered `bet:<id>` alert, made after live fills extended a baseline bet.
  Only one message was sent per bet.

### 3.4 DATA PROBLEM events

One health event in 17 minutes: `data-api enrichment/invalid_request`. `/v2/positions?condition=<combo id>` answered 400. It was
recorded, resolved by the next good enrichment, and not notified (x1). No poll failure, no status lag, no stale wallet,
no quarantined row, no gap event.

### 3.5 Sample alert texts (trimmed)

```
[NEW BET DETECTED] addition to position | GoalLineGhost (0x0346…52a5)
INFORMATIONAL ONLY: no copy signal has been validated by this research. Not a trading recommendation.
Market: Will Fagiano Okayama win on 2026-10-18?
Event: Fagiano Okayama vs. Vissel Kōbe | Outcome: No | Side: BUY
Filled: 126.19 sh, avg 0.7000, spent $89.55 (2 fills; incl. fees eff. 0.7097)
Maker/taker: taker 116.20 / maker 9.99 / unknown 0.00 sh; wallet fees $1.22
Executed (UTC): 2026-10-18 05:41:30Z -> 2026-10-18 05:42:26Z
Detected (UTC): 2026-10-18 05:42:38Z | detection lag 12s | alert built 2026-10-18 05:42:42Z
Book now (2026-10-18 05:42:41Z): bid 0.640 / ask 0.720, spread 8.0c; ask depth <=1c $3,710.97 (5,142 sh), <=5c $11,759.20; ...
Price deterioration vs wallet avg: 2.00c (2.86%)
Follower taker fee at that price: 1.008c/sh (1.40% of notional; $1.40 on a $100.00 follow; rate 0.05 via feeSchedule)
Market state: closed=False accepting_orders=True in_play=True (gameStartTime has passed and the event has not ended); ...
Link: https://polymarket.com/event/jap-fag-vis-2026-10-18/jap-fag-vis-2026-10-18-fag
```

```
[NEW BET DETECTED] new position | w38791873984189 (0x0d2d…7ff5)          <- BEFORE the fix (S1)
Market: Guangzhou: Arthur Weber vs Dominik Palan AND Japan Women's Open, Qualification: Harriet Dart vs Aoi Ito
Event: n/a | Outcome: No | Side: BUY
Maker/taker: taker 0.00 / maker 51.50 / unknown 0.00 sh; wallet fees $0.00          <- unsupported "maker"
Book: unavailable (no order book (CLOB 404): market closed or not tradable)        <- misleading
Enrichment errors: positions (market): invalid_request HTTP 400 from data-api /v2/positions: invalid condition id: 0x037a…0000
```

```
Market: [COMBO: multi-leg RFQ position, not a single order-book market] Guangzhou: Omar Jasika vs Hiroki Moriya AND ...   <- AFTER the fix
Maker/taker: taker 0.00 / maker 0.00 / unknown 61.66 sh; wallet fees $0.00
Book: unavailable (combo (multi-leg RFQ position): no CLOB order book, Gamma market or /v2/positions entry exists for its id, ...)
```

## 4. Step 3: outage and restart

- Stopped after chunk B at **05:54:13Z**. Restarted at **05:59:24Z** (outage 5 min 11 s). The wallets kept trading.
- The first restart poll started from the stored watermark minus the 600 s overlap (`from 2026-10-18 05:43:41Z`). It returned
  78 / 162 / 91 new fills (331) in one page per wallet, and all polls were OK.
- **Independent check** (`analyses/alerts_smoke/03_compare_independent.py`). It ran a fresh full pull of `/v2/trades?user=…&taker_only=false&start&end`,
  which is a different endpoint from the poller's `/v2/activity`, cache-busted and paginated to the end. Non-trade rows came from a separate
  `/v2/activity?type=SPLIT,MERGE,REDEEM,CONVERSION` pull. The window ran from 04:41:41Z (start of the monitored window) to 06:02:43Z (final watermark).
  Rows were compared as multisets.

```
pulled 06:03:44
GoalLineGhost: independent rows=653 (trades 549, other 104), stored=653, missing=0, extra=0; outage window: independent=78 stored=78 missing=0
norm1e69: independent rows=1766 (trades 1702, other 64), stored=1766, missing=0, extra=0; outage window: independent=161 stored=161 missing=0
w38791873984189: independent rows=1344 (trades 872, other 472), stored=1344, missing=0, extra=0; outage window: independent=90 stored=90 missing=0
TOTAL missing=0 extra=0
pulled again 06:06:39 (late-ingestion check): identical
```

- **No fill was skipped**: 329 of 329 outage-window rows, 3,763 of 3,763 in the whole window. 0 extra.
  A pilot on the chunk A+B window had shown one "missing" row at 04:41:38Z. That row was 1 s before norm1e69's bootstrap start (04:41:39Z),
  so it was a window-edge artifact of the comparison, not a miss.
- Alerts for bets executed during the outage: 11 delivered after the restart, with detection lag 29–240 s (p50 59 s).
  Each shows its true lag (for example "detection lag 4.0 min"). 9 more were suppressed by the w38791873984189 alert cap.
  Outage fills were detected a median 144 s after their block time (max 312 s).

## 5. Issue found and fixed

**S1: Combo fills (`is_combo: true`) were enriched as ordinary markets.** Live facts (VERIFIED):

- Rows carry `is_combo: true`, a synthetic `condition_id` (34 hex digits, then zeros), a title "<market A> AND <market B>", and empty `slug`/`event_slug`.
- `/v2/positions?condition=` answers 400 "invalid condition id". CLOB `/book` answers 404. Gamma and `/v2/tokens?condition=` return nothing.
- 0 of the 6 combo TRADE rows are in the wallet's `taker_only=true` `/v2/trades` feed. 19 combo REDEEM rows also exist.

**Consequences before the fix.** Each combo bet raised a `/v2/positions` DATA PROBLEM health event. A structural property looked like a data outage.
The alert said "market closed or not tradable". The fee-free fill was labelled **maker**, an inference that does not hold for RFQ fills.

**Fix** (`alerts/enrich.py` `is_combo`, `Enricher._enrich_combo`; `alerts/render.py`). A combo bet now gets a facts-only enrichment with no lookups.
Roles stay as stored (fee-embedded = taker, unconfirmed; otherwise unknown). The Market line says `[COMBO: multi-leg RFQ position, …]`,
and the alert explains why book, fee, exposure and market state are unavailable.

**Tests.** `alerts/tests/test_smoke_findings.py` adds 2 tests. Without the fix, the combo test fails: maker 51.5 sh, "market closed", and 7 lookups.
Re-enriching all 8 real combo bets from the live DB (offline, with a source that fails on any network call) gave 0 errors, 0 lookups and 0 maker shares. 0 of 500 ordinary fills were misdetected.
Suite: **108 passed**, pyflakes clean. README §18/§20 updated.

## 6. Observations not changed (for the reviewer)

1. **Polling latency.** The steady-state p50 is 16 s and the worst case about 37 s. This is fine for informational alerts.
   It is far behind the leader for anything time-sensitive (RTDS about 2 s, CLOB WS print about 0 s; data_infrastructure.md §3.4).
2. **A short outage is not announced.** A 5-minute stop raises no gap event (`gap_horizon_hours: 6`) and no DELAYED line
   (that needs a lag above `max(300 s, 10 × interval)`). The outage shows only through the per-alert lag figure.
   An operator who wants to know about restarts would need a "monitor was down for X min" notice. This is a design choice, not a data loss.
3. **ALERT CAP notices are deduplicated per clock hour, while the cap is a rolling hour.** A wallet that stays over the cap gets one notice per clock hour (here 05:51 and 06:00). This is minor noise.
4. **Bootstrap fill roles.** Bootstrap fills stay `unknown` in the `fills` table (the cross-check runs only for alerts), so DB-level maker counts understate makers.
5. **Alerts for bets that began in the baseline** (18 here) report the whole bet, including the baseline fills ("first BUY run on this outcome seen by this monitor").
6. Combo REDEEM rows and MERGE/CONVERSION rows pass validation and are recorded. Nothing is quarantined.

## 7. Reproduce

```
cd polymarket_research
python -m pytest alerts/tests -q
python -m alerts.run --config data/derived/alerts_smoke/hist.yaml --once --dry-run --backfill-hours 8760
PYTHONPATH=. python analyses/alerts_smoke/01_find_active.py
python -m alerts.run --config data/derived/alerts_smoke/active.yaml --dry-run --max-cycles 13      # repeat in chunks; stop; wait; restart
python analyses/alerts_smoke/02_analyze_db.py data/derived/alerts_smoke/active.sqlite data/derived/alerts_smoke/active_alerts.ndjson \
       data/derived/alerts_smoke/chunkA_stdout.txt <start/end epoch pairs of the runs>
PYTHONPATH=. python analyses/alerts_smoke/03_compare_independent.py data/derived/alerts_smoke/active.sqlite <W0> <W1> <OUT0> <OUT1>
```

The wallets in step 2 are anonymous public accounts picked only because they were busy at 05:40 UTC.
Nothing here says anything about their skill or identity, and no copy signal is implied.
Again: **nothing has been deployed and monitoring is NOT active.**
