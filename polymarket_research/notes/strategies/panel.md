# Price panel, trade tapes and spread model (stage 2 data build)

As-of 2026-10-17. Builds on `notes/strategies/universe.md` (stage 1). Family: data. Verdict: n/a (data build).

## 0. Pre-registered acceptance checks (written 2026-10-17 before any panel/tape/book result was computed)

Only one probe (`analyses/panel/00_probe.py`, 9 markets) was run before this section was written. It established that the CLOB
`/prices-history` series is forward-filled at the requested fidelity (one point per minute at fidelity=1, about one per hour at
fidelity=60) and that a point differs from the last trade by about half a tick, which suggests a midpoint series. No sample,
panel, tape or book statistic had been computed.

A check that fails is reported as FAIL with its consequence. It is not re-specified after the fact.

1. **Sample design.** Every category x quarter cell with at least one eligible market gets at least min(N_cell, 5) sampled markets.
   TEST (2026-01-01..2026-10-15) holds at least 55% of the sample.
2. **Price coverage.** At least 90% of sampled markets return a non-empty fidelity=60 series. At least 85% have a usable price
   (an observation at or before the horizon) at both T-1d and T-1h.
3. **No look-ahead in the panel.** In 100% of panel rows, `obs_ts <= horizon_ts`. Horizons that fall after the market's
   `closedTime` are null. Checked mechanically.
4. **Fidelity consistency.** Where the fidelity=60 and fidelity=1 windows overlap, the fidelity=60 point at time t equals the
   fidelity=1 point at the same minute within 0.5c in at least 90% of comparisons. If this fails, the fidelity=60 points are
   aggregates (not snapshots), and the panel uses fidelity=1 wherever it is available.
5. **Series vs tape alignment (look-ahead direction).** On tape markets, the median absolute gap between the series point at t and
   the last taker trade at or before t is no larger than the gap to the last trade at or before t+5 min. If this fails, the series
   may embed information from after t, and every horizon price must be lagged by one fidelity step.
6. **Tape completeness.** At least 95% of tape markets finish pagination without error and without hitting a page cap. The ratio of
   tape taker notional (sum of size x price) to Gamma `volumeNum` has an interquartile range inside [0.2, 5]. The ratio itself
   is reported, not assumed: what `volumeNum` measures is unverified.
7. **Spread model.** At least 800 sampled live books are two-sided (both a bid and an ask). Every cell reported in the headline
   table has at least 20 books, or the cell is collapsed into a coarser cell.

## 1. What was built

| file | rows | content |
|---|---|---|
| `data/derived/panel_sample.parquet` | 8,000 markets | sampled markets with stratum weights, payout of `token_id_0` (`y0`), `ref_ts`, `early_close`, `cluster_id`, `cluster_week` |
| `data/derived/price_panel.parquet` | 133,178 rows (long) | price at each horizon x reference type; see section 3 for the columns |
| `data/derived/price_series_h60.parquet` | 2,918,801 points | CLOB `/prices-history` fidelity=60 for `token_id_0`, at most the last 120 days before `ref_ts` |
| `data/derived/price_series_m1.parquet` | 25,664,433 points | fidelity=1 over `[ref_ts-72h, ref_ts]` |
| `data/derived/panel_fetch_log.parquet` | 22,476 requests | one row per request: window, number of points, error (none) |
| `data/derived/tape_selection.parquet` | 1,603 markets | 1,503 liquid tape markets + 100 null-volume audit markets |
| `data/derived/tapes/tape_NNN.parquet` (17 chunks, zstd) + `tapes/coverage.parquet` | 5,663,872 taker trades | `/v2/trades?condition=` default (taker-only) tapes |
| `data/derived/book_snapshots_2026-10-17_{vol10k,allopen}.parquet` | 1,292 / 2,384 markets | round-1 live books (token_id_0 metrics only) |
| `data/derived/book_levels_2026-10-17_{vol10k,allopen}_{r2,r3}.parquet` | | re-snapshots with every price level |
| `data/derived/book_sides_2026-10-17.parquet` | one row per book side and round | metrics for both outcome sides |
| `data/derived/spread_model.parquet` | | half-spread, slippage and depth by cell (section 5) |
| `data/derived/effective_spread_hist.parquet` | | historical effective half-spread paid by takers, from the tapes (section 5.3) |
| `analyses/panel/out/05_checks.json`, `06_spread_model.json`, `07_effective_spread.json` | | every number in the checks below |

Pipeline (run from `polymarket_research/`, `PMR_RATE_SCALE=2`): `00_probe.py` -> `01_sample.py` -> `02_pull_prices.py` (resumable,
20 chunks of 400 markets) -> `03_pull_tapes.py select|pull` (resumable, 17 chunks of 100) -> `04_books.py 10000 vol10k` and
`04_books.py` (all open) -> `04b_resnap_books.py r2|r3` -> `05_build_panel.py` -> `06_spread_model.py` -> `07_effective_spread.py`.
All history requests are cached under `data/raw/{clob,data-api}/cache/` with URL, params and UTC fetch time; the live books are under
`data/raw/clob/live/20261017/`. All pulls ran on 2026-10-17 between 22:38 and 23:30 UTC. Errors: 0 of 22,476 price requests and
0 of 6,435 tape pages. **VERIFIED.**

## 2. Sample design

**Eligible population.** Universe markets (stage 1) with `n_outcomes == 2`, `enableOrderBook`, a `token_id_0`, Gamma `volumeNum >= $10,000`
and resolution `winner` or `split_50_50`: 447,936 markets. 50-50 splits are kept and flagged (`clean_resolution = False`,
`y0 = 0.5`; 18 in the sample), so the sample is not conditioned on how the market resolved. The 12 `unresolved_nonterminal` markets have no
payout and are dropped. Neg-risk constituents (2,981 in the sample) are their own binary contracts, and each carries `event_id`,
`negRiskMarketID` (via the universe) and `cluster_id`.

**What the sample conditions on.** Everything except two items is known at listing.
- **The volume screen uses full-life `volumeNum`.** This is a look-ahead: a market qualifies because of volume it had not yet
  traded at the decision time. Section 4.3 measures the size of the effect.
- **The resolution filter** drops only the 12 unresolved markets.

Blank `volumeNum` (43% of the universe, almost all 2026 sports and crypto) fails the screen. An audit of 100 random blank-volume
2026Q3 markets (`/v2/trades` tapes) found 5 with any trades and **0 with at least $10k of taker notional**, with a p99 of $820.
The screen therefore loses almost none of the markets it is meant to keep: by the rule of three, under 3% at 95% (**VERIFIED** on
that sample).

**Allocation.**
1. Split budgets: train 1,500, validation 1,500, TEST 5,000.
2. Within each split, a quarter's share is proportional to its calendar days inside the window. 2026Q4 covers only Oct 1-15, so it
   gets 260.
3. Within each quarter, categories get shares proportional to sqrt(N_cell), with a floor of min(N_cell, 5) and a cap of N_cell.
4. Within each cell, markets are drawn uniformly at random (seed 20261017).

`sample_weight = N_cell / n_cell` re-weights the sample to the eligible population. Weight medians: train 8.2, validation 31.7, TEST 77.8;
range 1.0-141. Sports and crypto are deliberately under-sampled relative to their counts: they are 57-90% of eligible markets per
quarter and highly repetitive.

| quarter | crypto | culture | economics | finance | geopolitics | mentions | other | politics | sports | tech | weather | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2024Q1 | 32 | 29 | 16 | 26 | 25 | 14 | 23 | 46 | 26 | 12 | 1 | 250 |
| 2024Q2 | 32 | 26 | 15 | 24 | 22 | 16 | 17 | 32 | 41 | 12 | 13 | 250 |
| 2024Q3 | 21 | 27 | 13 | 12 | 17 | 42 | 10 | 41 | 47 | 11 | 11 | 252 |
| 2024Q4 | 26 | 25 | 14 | 14 | 17 | 33 | 9 | 40 | 51 | 11 | 12 | 252 |
| 2025Q1 | 26 | 29 | 15 | 14 | 16 | 20 | 7 | 28 | 56 | 11 | 25 | 247 |
| 2025Q2 | 39 | 23 | 19 | 10 | 20 | 18 | 6 | 30 | 53 | 11 | 21 | 250 |
| 2025Q3 | 225 | 63 | 41 | 17 | 53 | 47 | 5 | 52 | 168 | 28 | 51 | 750 |
| 2025Q4 | 216 | 56 | 38 | 45 | 45 | 34 | 11 | 53 | 169 | 36 | 47 | 750 |
| 2026Q1 | 475 | 119 | 58 | 105 | 75 | 65 | 13 | 73 | 381 | 53 | 145 | 1562 |
| 2026Q2 | 459 | 100 | 42 | 86 | 64 | 44 | 21 | 79 | 416 | 48 | 221 | 1580 |
| 2026Q3 | 446 | 93 | 41 | 76 | 60 | 32 | 14 | 72 | 511 | 50 | 202 | 1597 |
| 2026Q4 | 61 | 17 | 9 | 15 | 13 | 7 | 8 | 18 | 76 | 11 | 25 | 260 |
| total | 2058 | 607 | 321 | 444 | 427 | 372 | 144 | 564 | 1995 | 294 | 774 | 8000 |

**Leakage units.**
- The sample spans 7,115 events and 7,091 `cluster_id`s, with at most 12 markets per cluster. Clusters: TEST 4,554, validation 1,334,
  train 1,206.
- `cluster_week` (ISO week of endDate): TEST 42 weeks, validation 27, train 79. Bootstrap on clusters and on weeks.
- Structure: neg-risk 2,981, binary in a multi-market event 2,395, stand-alone binary 2,624.
- Fees enabled (as traded): 70.8% of TEST, 0.2% of validation, 0% of train.
- `early_close` (closedTime more than 1 h before endDate): 19-23% per split. This is mostly sports, where endDate is a deadline, plus
  "by date" markets that resolved early.

## 3. Price series and panel

**What the series is.** CLOB `/prices-history`, `market = token_id_0`, explicit `startTs`/`endTs`.
- Windows: fidelity=60 in 14-day windows (the endpoint rejects windows longer than about 15 days), capped at 120 days before `ref_ts`
  and at the market's start; fidelity=1 over the 72 h before `ref_ts`.
- `ref_ts = min(endDate, closedTime)`. If closedTime is missing (2 markets), endDate is used.
- Findings (**VERIFIED**):
  - The series is **forward-filled on a fixed grid**: one point per minute at fidelity=1, about one per hour at fidelity=60, with
    timestamps a few seconds past the minute or hour.
  - Fidelity-60 points are **snapshots of the minute series**, not aggregates: 409,692 of 409,692 overlapping points are exactly equal
    to the fidelity-1 value at the same minute.
  - Values sit about half a tick from the last trade. The median absolute gap to the last taker trade at or before t is 0.5c
    at every lag tested.
- Interpretation (**PLAUSIBLE**): this is the displayed price, the midpoint when the quoted spread is at most 10c and the last
  trade otherwise. The 10c rule is from Polymarket's UI documentation and is not re-verified here.
- **It is not executable.** Section 5 gives the costs to add.

**Panel construction (`price_panel.parquet`, long format).**
- The series used is fidelity-60 points before the 72 h window, then fidelity-1 points.
- For each horizon, the price is the **last observation with `obs_ts <= horizon_ts`**. Nothing after the horizon is used.
- Reference types:
  - `res`: horizons before `ref_ts` (T-30d, T-7d, T-3d, T-1d, T-12h, T-6h, T-1h, T-15m), as specified.
  - `sched`: the same horizons before the **scheduled endDate**. A horizon after closedTime is null (`post_close`).
  - `game`: gameStartTime -60m and -15m, for the 2,589 markets with a gameStartTime (1,995 sports plus others). A game horizon after
    the fetched series end is null (`after_series_end`, 186 rows where endDate falls before the game).
- Columns: `price, obs_ts, staleness_s` (= horizon - obs_ts), `src` (m1/h60), `last_change_ts`/`last_change_age_s` (time since the
  series value last changed; `change_censored` when the value never changed inside the fetched window). Market keys are included:
  `token_id_0, y0, event_id, cluster_id, cluster_week, split, category, structure, sample_weight, clean_resolution, early_close`.
- Tape markets also get: `last_trade_ts`/`last_trade_age_s`, `last_trade_p0` (in token-0 terms), `tape_notional_before`,
  `volnum_at_h_est` and `vol_screen_at_h` (section 4.3).
- **Look-ahead warning on `res`.** For early-closing markets (19-23%), `ref_ts = closedTime` is known only after the fact, and
  closing early is correlated with the outcome (a YES "by date" market closes when the event happens). Any rule that conditions on a
  `res` horizon is using information from the future. Strategy tests should decide on `sched` or `game` horizons, where the clock is
  known in advance, and treat `res` as descriptive.

**Coverage (`res`).** Share of markets with a price at each horizon:

| split | T-30d | T-7d | T-3d | T-1d | T-12h | T-6h | T-1h | T-15m |
|---|---|---|---|---|---|---|---|---|
| train | 0.257 | 0.506 | 0.724 | 0.884 | 0.941 | 0.952 | 0.967 | 0.968 |
| validation | 0.134 | 0.351 | 0.572 | 0.892 | 0.935 | 0.945 | 0.988 | 0.990 |
| test | 0.125 | 0.322 | 0.466 | 0.765 | 0.974 | 0.984 | 0.993 | 0.994 |
| *test, markets that existed at the horizon* | 0.961 | 0.991 | 0.993 | 0.992 | 0.999 | 0.999 | 0.999 | 0.999 |

Most missing early horizons are structural: the market did not exist yet. 1,455 of the 1,512 misses at T-1d are markets created less
than a day before `ref_ts`, mostly crypto up/down and sports. Among markets that existed at the horizon, 92.6-99.9% are priced in every
split. Coverage of `sched` is lower (T-1h 78%) because sports deadlines fall after the close. Both game horizons are 94% priced.

**Staleness.**
- Observation age: median 50 s (p99 59 s) on the minute series; median 3,582 s (p99 14,343 s) on the hourly series.
- Because the series is forward-filled, observation age says little. Time since the price last changed is more useful: median 0.8 h at
  T-15m, 1.1 h at T-1h, 0.76 h at T-1d, 3.0 h at T-7d. 6-10% of rows have not changed for more than a day.
- On tape markets, the median age of the last taker trade is 0.10 h at T-15m, 0.15 h at T-1h, 0.31 h at T-1d and 1.4 h at T-30d.
- The panel price is within 1c of the last trade in 81-88% of rows at T-1d and later, and in 73-77% at T-3d and earlier.
  **VERIFIED.**

## 4. Trade tapes

**Selection.**
- Within each split x category stratum of the sample, the top-k markets by `volumeNum`, with k proportional to the stratum's sample
  size (floor 5).
- Result: 1,503 markets (TEST 937, validation 283, train 283). By category: crypto 386, sports 374, weather 145, culture 114,
  politics 106, finance 84, geopolitics 80, mentions 70, economics 60, tech 55, other 29.
- These are the most liquid sampled markets, chosen by full-life volume (the same look-ahead as the screen). Do not treat them as
  representative of the sample.
- Plus the 100-market null-volume audit (section 2).

**Pull.**
- `/v2/trades?condition=<id>&limit=1000`, default `taker_only` (taker side only), keyset cursor, newest first, capped at 100 pages per
  market.
- Fields kept: `condition_id, token_id, outcome, outcome_index, side, price, size, timestamp` (block time), `proxy_wallet,
  transaction_hash`. Profile fields are dropped.

**Coverage and pagination (VERIFIED).**
- Totals: 5,663,872 rows, 6,435 pages, 0 errors.
- Every walk ended naturally except one, which hit the 100-page cap: a $56.5M train geopolitics market ("Trump ends Ukraine war in
  first 90 days?"). Only its newest 100,000 trades are kept, so `truncated = True` and its volume-at-horizon is a lower bound.
- No empty pages with `has_more`, no out-of-order timestamps across pages, no exact duplicate rows.
- Tape length per market: median 2,013 (TEST), 1,464 (validation), 1,737 (train); max 76,440 below the cap.
- The `/v2/trades` condition window is a fixed three years back. That reaches 2023-10, which covers the whole universe (CONTEXT.md /
  data_infrastructure.md).

**Tape notional vs Gamma `volumeNum`.** Taker notional (sum of size x price) divided by `volumeNum`: median 0.501, IQR 0.41-0.56, p10
0.26, p90 0.62, about the same in every split. **PLAUSIBLE:** `volumeNum` counts both sides of each fill (maker plus taker), about
twice the taker notional.

### 4.3 How much the full-life volume screen looks ahead

For tape markets, `volnum_at_h_est = volumeNum x (tape notional at or before the horizon / total tape notional)`.
`vol_screen_at_h` = estimate >= $10k (for the one truncated market, a lower bound on what was available).

Share of these markets that would already have passed the $10k screen at the horizon (among markets priced at that horizon):
- T-1d: train 0.90, validation 0.65, TEST 0.52.
- T-1h: train 0.99, validation 0.85, TEST 0.72.

Counting markets that did not yet exist as fails, the T-1d shares are 0.87 / 0.62 / 0.41.

So in TEST, **about half of even the most liquid sampled markets had not yet reached $10k a day before resolution.** Short-lived 2026
crypto and sports markets do most of their trading in the final hours. The screen is a material look-ahead for TEST horizon studies.

Recommended handling:
- Run the main tests on the tape subsample with `vol_screen_at_h == True`, or use a volume-free design (all markets, cost-adjusted).
- Report the full-life-screen results only as a sensitivity check.

The flag exists only for the 1,503 tape markets. These are the most liquid, so their pass rates are an upper bound for the sample.
**VERIFIED** for the tape set.


## 5. Spread and cost model

SPREAD_SECTION_PLACEHOLDER

## 6. Acceptance checks (pre-registered in section 0)

| # | check | result | verdict |
|---|---|---|---|
| 1 | every category x quarter cell gets >= min(N, 5); TEST >= 55% | 0 violations in 132 cells; TEST 62.5% | **PASS** |
| 2 | >= 90% non-empty fidelity-60 series; >= 85% priced at both T-1d and T-1h (`res`) | 98.7% non-empty; **81.1%** priced at both | **FAIL** as specified |
| 3 | `obs_ts <= horizon_ts` in 100% of rows; horizons after closedTime null | 0 violations; 0 priced post-close rows | **PASS** |
| 4 | fidelity-60 point = fidelity-1 point at the same minute within 0.5c in >= 90% | 100% (exactly equal, n = 409,692) | **PASS**: fidelity-60 points are snapshots |
| 5 | median gap to the last trade at t <= the gap at t+5 min | 0.5c = 0.5c at every lag | **PASS, but uninformative** (see below) |
| 6 | >= 95% of tapes complete; IQR of tape notional / volumeNum inside [0.2, 5] | 99.93% complete (1 hit the cap); IQR 0.41-0.56 | **PASS** |
| 7 | >= 800 two-sided live books; headline cells n >= 20 or collapsed | CHECK7_PLACEHOLDER | CHECK7_VERDICT |

**Check 2.** The failure is structural, not a data gap. 1,455 of the 1,512 markets unpriced at T-1d did not exist a day before
`ref_ts` (short-lived crypto and sports). Among markets that existed at T-1d, 99.1% are priced at both T-1d and T-1h. Consequence:
a T-1d (or earlier) study covers a different, longer-lived population than a T-1h study. TEST loses 23.5% of its markets at T-1d and
68% at T-7d. Report horizon-specific sample sizes, and do not compare horizons as if the same markets were in each.

**Check 5.** The median is pinned at half a tick, so as written the check cannot detect a misalignment. A post-hoc comparison,
declared after seeing that result (**PLAUSIBLE**), separates the lags:
- Mean absolute gap by lag: 1.09c at -60 s, **1.00c at 0 s**, 1.18c at +60 s, 1.59c at +300 s. The series at t best matches trades
  at or before t.
- Of 520,225 minute-to-minute changes in the series, 35.6% had a taker trade in the preceding 60 s and 27.2% in the following 60 s.

Both results are consistent with a snapshot taken at t with no forward information. They do not prove it: quote changes without a
trade also move the series, and trades follow quote changes.

## 7. How to use this panel, and caveats

- **Entry prices.** The panel price is a midpoint or last-trade display price, **not executable**. Add a cost from section 5:
  either the historical effective half-spread for small orders (5.3), or the live-book slippage at the intended size (5.1-5.2,
  today's books, an assumption). Then apply fees. **Prospective**: `pmr.fees.TAKER_RATE[category] x p x (1-p)` per share (current
  schedule). **As traded**: the per-market `fee_rate`/`fee_exponent` in `panel_sample.parquet` (from Gamma `feeSchedule`, the
  current state of the market). Train and validation markets were fee-free.
- **Which reference clock.** Decide on `sched` or `game` horizons (known in advance). `res` horizons condition on the realised
  close time, which is look-ahead for the 19-23% of markets that closed early.
- **Volume screen.** Full-life `volumeNum` is a strong look-ahead for TEST short-horizon markets (4.3). Use `vol_screen_at_h`
  on the tape subsample, or a design that does not screen on volume.
- **Inference.** Cluster on `cluster_id` and block on `cluster_week`. TEST has 42 weeks. Weight with `sample_weight` to
  generalise to the eligible population, or report per category unweighted.
- **Capital lock-up.** A position opened at a horizon is locked until settlement: `closedTime` (+ the stage-1 settlement lag) for
  most markets; for sports, settlement is about 4 h after `gameStartTime`. Disputes extend it (stage 1, section 5).
- **Missing pieces.**
  - There is no historical order book: costs for history are either taker-realised (5.3) or today's books (5.1).
  - The series is only the first outcome token. The second token is its complement (`1 - p`) up to the spread, and books are
    mirrored (verified), but the second token's own series was not pulled.
  - Fidelity-1 data exists only for the last 72 h before `ref_ts`. Earlier horizons use hourly snapshots (staleness up to about 1 h,
    p99 4 h).
  - Tapes are taker-only. Maker fills (`taker_only=false`) were not pulled.
- **The tape subsample is not random.** It is the most liquid markets per stratum, chosen by full-life volume. Do not use it to
  estimate population averages without saying so.
