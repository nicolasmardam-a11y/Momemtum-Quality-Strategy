# Price panel, trade tapes and spread model (stage 2 data build)

As-of 2026-10-17. Builds on `notes/strategies/universe.md` (stage 1). Family: data. Verdict: n/a (data build).

**Summary.**
- **Sample:** 8,000 binary markets with lifetime volume >= $10k, stratified by category x quarter (TEST 4,999, validation 1,500,
  train 1,501), with population weights and leakage clusters.
- **Panel:** a long-format price panel (133k rows) at T-30d..T-15m before `min(endDate, closedTime)`, before the scheduled endDate,
  and before gameStartTime, built from 28.6M CLOB `/prices-history` points (0 errors).
- **Tapes:** taker tapes for the 1,503 most liquid sampled markets: 5.66M trades, 0 errors, 1 market truncated at the 100-page cap.
- **Costs:** a live-book spread/depth model (1,292 volume-screened plus 2,384 unscreened open markets, 3 snapshots) and a historical
  effective-spread model from the tapes.
- **Checks:** 6 of 7 pre-registered checks pass. Check 2 fails as specified, for a structural reason: short-lived markets did not
  exist at T-1d.
- **Two warnings for every downstream test:**
  1. The full-life volume screen is a material look-ahead in TEST. Only 52% of the most liquid TEST markets had $10k of volume by
     T-1d.
  2. `res` horizons are look-ahead for the 19-23% of markets that closed early. Decide on `sched` or `game` horizons.

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
`data/raw/clob/live/20261017/`. All pulls ran on 2026-10-17 between 22:38 and 23:14 UTC. Errors: 0 of 22,476 price requests and
0 of 6,435 tape pages. **VERIFIED.**

## 2. Sample design

**Eligible population.** Universe markets (stage 1) with `n_outcomes == 2`, `enableOrderBook`, a `token_id_0`, Gamma `volumeNum >= $10,000`
and resolution `winner` or `split_50_50`: 447,936 markets. 50-50 splits are kept and flagged (`clean_resolution = False`,
`y0 = 0.5`; 18 in the sample), so the sample is not conditioned on how the market resolved. The 12 `unresolved_nonterminal` markets have no
payout and are dropped. Neg-risk constituents (2,981 in the sample) are their own binary contracts, and each carries `event_id`,
`negRiskMarketID` (via the universe) and `cluster_id`.

**What the sample conditions on.** Everything except two items is known at listing.
- **The volume screen uses full-life `volumeNum`.** This is a look-ahead: a market qualifies because of volume it had not yet
  traded at the decision time. Section 4.1 measures the size of the effect.
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
  - `game`: gameStartTime -60m and -15m, for the 2,589 markets with a gameStartTime: 1,786 of the 1,995 sports markets, plus
    weather 485, culture 133, finance 110 and others, where Gamma uses the field as an event start. A game horizon after the
    fetched series end is null (`after_series_end`, 202 rows where endDate falls before the game). Game horizons come from the
    minute series in 94% of priced rows. Median time since the last price change: 0.23 h at G-15m.
- Columns: `price, obs_ts, staleness_s` (= horizon - obs_ts), `src` (m1/h60), `last_change_ts`/`last_change_age_s` (time since the
  series value last changed; `change_censored` when the value never changed inside the fetched window). Market keys are included:
  `token_id_0, y0, event_id, cluster_id, cluster_week, split, category, structure, sample_weight, clean_resolution, early_close`.
- Tape markets also get: `last_trade_ts`/`last_trade_age_s`, `last_trade_p0` (in token-0 terms), `tape_notional_before`,
  `volnum_at_h_est` and `vol_screen_at_h` (section 4.1).
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
- Rows by split: TEST 3,592,268, validation 749,102, train 1,322,502. Trades run from 2023-12-01 to 2026-10-15.
- Median `volumeNum` of tape markets: TEST $236k, validation $402k, train $619k.
- The `/v2/trades` condition window is a fixed three years back. That reaches 2023-10, which covers the whole universe (CONTEXT.md /
  data_infrastructure.md).

**Tape notional vs Gamma `volumeNum`.** Taker notional (sum of size x price) divided by `volumeNum`: median 0.501, IQR 0.41-0.56, p10
0.26, p90 0.62, about the same in every split. **PLAUSIBLE:** `volumeNum` counts both sides of each fill (maker plus taker), about
twice the taker notional.

### 4.1 How much the full-life volume screen looks ahead

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

No historical order book exists (CONTEXT.md). Two estimates are provided.
1. **Live books (5.1-5.2):** today's books applied to history. **This is an ASSUMPTION** and probably optimistic for 2024-25, when
   ticks were coarser, there were no rebates, and fewer market makers were active.
2. **Historical effective half-spread (5.3):** what takers actually paid relative to the panel series, in each split. Only valid for
   the small sizes takers actually traded.

### 5.1 Live-book method (`04_books.py`, `04b_resnap_books.py`, `06_spread_model.py`)

**Candidates.** Open markets from the Gamma open-market pull of 21:27 UTC (`la_markets_2026-10-17w2.parquet`, 303k markets) plus a
fresh Gamma pull of 25,000 open markets ending within 24 h (capped at 250 pages, so it is a subset).

**Two book universes.**
- `vol10k` (primary, comparable to the panel's volume screen): Gamma `volumeNum` to date >= $10k. That leaves 6,208 candidates and
  1,292 sampled.
- `allopen` (reference): no volume screen; 283,806 candidates, 2,384 sampled.

**Sampling.** Up to 45 random markets per category x time-to-resolution (TTR) cell.
- TTR = time to gameStartTime for sports (`in_play` once started), endDate otherwise (`past_end` once passed).
- Buckets are right-closed so panel horizons map one to one: T-15m and T-1h -> `<=1h`, T-6h -> `1-6h`, T-12h and T-1d -> `6-24h`,
  T-3d -> `1-3d`, T-7d -> `3-7d`, T-30d -> `7-30d`.

**Snapshots.** POST `/books` for `token_id_0`, taken three times on 2026-10-17:
- r1 at 22:54 UTC (`vol10k`) and 22:51 (`allopen`), metrics only;
- r2 at 22:58 and r3 at 23:14, with every price level stored.

The `token_id_1` book is the mirror of `token_id_0`'s (best bid = 1 - other best ask in 99-100% of 150 markets per universe;
**VERIFIED**). Each book is therefore used for both outcome sides, bucketed by **that side's own mid**, so buying a 2c long shot and
buying a 98c favourite land in different cells.

**Per side.** Half-spread, and for $500 / $2,500 / $10,000 the VWAP slippage from mid of a marketable buy (walking the asks) and
sell (walking the bids), the share of books that can fill the full size, and USD depth within 2c and 5c of mid. Slippage medians use
only books that fill the whole size.

**Stability.** r1 vs r2 half-spread for the same markets, 4-8 minutes apart: Spearman 0.98 (`vol10k`, n = 1,055; 84% unchanged) and 0.97
(`allopen`, n = 1,688; 78% unchanged).

**Coverage.** 1,055 two-sided `vol10k` markets per round, 1,694 `allopen`.
- `vol10k` is thin in short-TTR cells (`<=1h`: 48 markets at 35-65c, almost all sports; no crypto). Gamma `volumeNum` is blank for open
  short-horizon crypto and most sports markets, so the screen drops them.
- Geopolitics and mentions have only 2 `vol10k` markets each.
- Only 4 of 356 L0 cells (category x price x TTR) reach 20 markets. 47 of 98 L1 cells (category x price) and 26 of 83 L2 cells
  (price x TTR) do. Use the finest level with `n_markets_two_sided >= 20`, otherwise L3.
- r2 and r3 observations of the same market are pooled, so medians count each market up to twice.

### 5.2 Live-book results (`vol10k`, both rounds)

Costs are in price units (0.01 = 1c per share). Columns `buy $X` are the median slippage from mid for a buy of $X notional (fillable
books only). **VERIFIED** (computed from the stored books); applying them to history is an assumption.

| token price | markets | half-spread med | p75 | buy $500 | buy $2.5k | buy $10k | sell $500 | sell $2.5k | fillable buy $2.5k | fillable buy $10k | ask depth 2c $ | spread>10c |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| <2c | 213 | 0.0010 | 0.0045 | 0.0565 | 0.1895 | 0.4127 | 0.0026 | 0.0045 | 0.9569 | 0.8971 | 37.0000 | 0.0000 |
| 2-5c | 179 | 0.0068 | 0.0145 | 0.0839 | 0.2562 | 0.5360 | 0.0145 | 0.0149 | 0.9147 | 0.8147 | 27.0000 | 0.0000 |
| 5-15c | 213 | 0.0100 | 0.0200 | 0.0795 | 0.2431 | 0.4589 | 0.0184 | 0.0221 | 0.7415 | 0.6268 | 52.0000 | 0.0512 |
| 15-35c | 258 | 0.0100 | 0.0400 | 0.0495 | 0.1954 | 0.3604 | 0.0155 | 0.0190 | 0.7435 | 0.5666 | 69.0000 | 0.2266 |
| 35-65c | 221 | 0.0050 | 0.0300 | 0.0100 | 0.0108 | 0.0134 | 0.0050 | 0.0050 | 0.7683 | 0.6548 | 759.0000 | 0.2156 |
| 65-85c | 254 | 0.0100 | 0.0400 | 0.0175 | 0.0365 | 0.0751 | 0.0168 | 0.0253 | 0.7399 | 0.5181 | 209.0000 | 0.2298 |
| 85-95c | 211 | 0.0100 | 0.0200 | 0.0150 | 0.0258 | 0.0346 | 0.0143 | 0.0230 | 0.8108 | 0.5848 | 595.0000 | 0.0565 |
| 95-98c | 182 | 0.0070 | 0.0145 | 0.0117 | 0.0161 | 0.0195 | 0.0142 | 0.0251 | 0.8497 | 0.6561 | 1413.0000 | 0.0000 |
| >98c | 215 | 0.0010 | 0.0045 | 0.0020 | 0.0028 | 0.0045 | 0.0032 | 0.0073 | 0.7512 | 0.5474 | 11519.0000 | 0.0000 |
| ALL | 1055 | 0.0055 | 0.0150 | 0.0189 | 0.0376 | 0.0894 | 0.0100 | 0.0139 | 0.7990 | 0.6450 | 218.0000 | 0.1092 |

Half-spread by TTR x token price (median):

| half-spread median | <2c | 2-5c | 5-15c | 15-35c | 35-65c | 65-85c | 85-95c | 95-98c | >98c |
|---|---|---|---|---|---|---|---|---|---|
| <=1h |  |  | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0050 |  |  |
| 1-6h | 0.0025 | 0.0150 | 0.0242 | 0.0100 | 0.0050 | 0.0100 | 0.0242 | 0.0150 | 0.0025 |
| 6-24h | 0.0010 | 0.0100 | 0.0265 | 0.0050 | 0.0050 | 0.0050 | 0.0265 | 0.0100 | 0.0010 |
| 1-3d | 0.0005 | 0.0043 | 0.0100 | 0.1600 | 0.0050 | 0.1600 | 0.0100 | 0.0055 | 0.0005 |
| 3-7d | 0.0010 | 0.0070 | 0.0050 | 0.0100 | 0.0250 | 0.0060 | 0.0050 | 0.0070 | 0.0010 |
| 7-30d | 0.0015 | 0.0075 | 0.0050 | 0.0100 | 0.0155 | 0.0085 | 0.0050 | 0.0095 | 0.0018 |
| >30d | 0.0010 | 0.0060 | 0.0100 | 0.0100 | 0.0250 | 0.0100 | 0.0105 | 0.0065 | 0.0010 |
| in_play |  | 0.0057 | 0.0050 | 0.0300 | 0.0100 | 0.0300 | 0.0050 | 0.0058 |  |
| past_end | 0.0045 | 0.0200 | 0.0222 | 0.1115 | 0.3250 | 0.1115 | 0.0222 | 0.0200 | 0.0045 |

Slippage of a $2,500 buy by TTR x token price (median):

| buy $2.5k slippage median | <2c | 2-5c | 5-15c | 15-35c | 35-65c | 65-85c | 85-95c | 95-98c | >98c |
|---|---|---|---|---|---|---|---|---|---|
| <=1h |  |  | 0.0103 | 0.0050 | 0.0050 | 0.0050 | 0.0050 |  |  |
| 1-6h | 0.1573 | 0.4043 | 0.4252 | 0.3955 | 0.0050 | 0.0378 | 0.0446 | 0.0236 | 0.0081 |
| 6-24h | 0.1744 | 0.3664 | 0.0102 | 0.0082 | 0.0050 | 0.0050 | 0.0050 | 0.0191 | 0.0038 |
| 1-3d | 0.1186 | 0.1398 | 0.1638 | 0.3728 | 0.0052 | 0.0248 | 0.0210 | 0.0113 | 0.0028 |
| 3-7d | 0.1981 | 0.2124 | 0.2532 | 0.1054 | 0.1099 | 0.0395 | 0.0402 | 0.0177 | 0.0025 |
| 7-30d | 0.1847 | 0.2025 | 0.0920 | 0.1026 | 0.0922 | 0.0500 | 0.0176 | 0.0166 | 0.0036 |
| >30d | 0.1997 | 0.3014 | 0.3207 | 0.2301 | 0.2653 | 0.0560 | 0.0318 | 0.0151 | 0.0025 |
| in_play |  | 0.1211 | 0.0213 | 0.2141 | 0.0289 | 0.0300 | 0.0149 | 0.0245 |  |
| past_end | 0.4956 | 0.5355 | 0.6099 | 0.3118 | 0.2465 | 0.0263 | 0.0364 | 0.0192 | 0.0057 |

Two-sided markets per cell:

| markets | <2c | 2-5c | 5-15c | 15-35c | 35-65c | 65-85c | 85-95c | 95-98c | >98c |
|---|---|---|---|---|---|---|---|---|---|
| <=1h |  |  | 2 | 5 | 48 | 5 | 2 |  |  |
| 1-6h | 8 | 4 | 3 | 6 | 28 | 6 | 3 | 4 | 8 |
| 6-24h | 6 | 6 | 7 | 12 | 31 | 12 | 7 | 6 | 6 |
| 1-3d | 24 | 13 | 14 | 21 | 19 | 21 | 14 | 12 | 24 |
| 3-7d | 13 | 11 | 13 | 12 | 18 | 11 | 14 | 11 | 14 |
| 7-30d | 70 | 54 | 73 | 68 | 43 | 67 | 72 | 54 | 70 |
| >30d | 77 | 78 | 84 | 114 | 32 | 112 | 82 | 82 | 78 |
| in_play |  | 2 | 4 | 8 | 25 | 8 | 4 | 2 |  |
| past_end | 15 | 11 | 15 | 15 | 9 | 15 | 15 | 11 | 15 |

$2,500 buy slippage by Gamma volume-to-date tier:

| buy $2.5k by volume tier | <2c | 2-5c | 5-15c | 15-35c | 35-65c | 65-85c | 85-95c | 95-98c | >98c |
|---|---|---|---|---|---|---|---|---|---|
| 100k-1M | 0.1023 | 0.1063 | 0.0939 | 0.0289 | 0.0050 | 0.0126 | 0.0146 | 0.0077 | 0.0016 |
| 10k-100k | 0.2637 | 0.3501 | 0.2943 | 0.2393 | 0.0126 | 0.0514 | 0.0307 | 0.0186 | 0.0048 |
| >=1M | 0.0156 | 0.0239 | 0.0115 | 0.0050 | 0.0049 | 0.0071 | 0.0050 | 0.0024 | 0.0007 |

**Reading.**
- Quoted half-spreads are small. The median is 0.5-1c at mid prices and 0.1c at the extremes; 75% of books are at or below 1.5c.
- Size is the binding cost.
  - Buying cheap tokens: $500 of a sub-15c token moves the VWAP 5.7-8.4c above mid. Ask depth within 2c of mid is a median $27-52.
  - Buying expensive tokens: $500 of a 95c+ token costs 0.2-1.2c.
  - $10k is fillable in only 52-90% of books.
- Liquidity tier matters more than category. Markets with lifetime volume of $1M or more have 0.1-2.4c slippage at $2.5k on every price
  bucket. The $10k-100k tier pays 24-35c on cheap tokens.
- In `allopen` (no volume screen), the median half-spread at 35-65c is 19.5c and 60% of books have spreads above 10c. Most open
  markets are empty placeholder books, which is why `vol10k` is the primary universe.

### 5.3 Historical effective half-spread (`07_effective_spread.py`, `effective_spread_hist.parquet`)

**Method.** 2,316,839 taker trades from 1,484 tape markets, in the 72 h before `ref_ts` where the minute series exists. For each
trade, the traded token's mid is the series value at the last minute at or before the trade (at most 60 s old). The effective
half-spread is (price - mid) for a taker BUY and (mid - price) for a SELL. Cells: split x category x price x TTR, and split x price x
notional size.

Median effective half-spread:

| eff_half_med | <2c | 2-5c | 5-15c | 15-35c | 35-65c | 65-85c | 85-95c | 95-98c | >98c |
|---|---|---|---|---|---|---|---|---|---|
| train | 0.0010 | 0.0025 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0020 | 0.0010 |
| validation | 0.0005 | 0.0026 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0015 | 0.0005 |
| test | 0.0005 | 0.0025 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0025 | 0.0005 |

Mean effective half-spread:

| eff_half_mean | <2c | 2-5c | 5-15c | 15-35c | 35-65c | 65-85c | 85-95c | 95-98c | >98c |
|---|---|---|---|---|---|---|---|---|---|
| train | 0.0015 | 0.0045 | 0.0081 | 0.0087 | 0.0120 | 0.0089 | 0.0081 | 0.0035 | 0.0011 |
| validation | 0.0018 | 0.0094 | 0.0122 | 0.0138 | 0.0124 | 0.0110 | 0.0075 | 0.0016 | 0.0010 |
| test | 0.0118 | 0.0210 | 0.0336 | 0.0270 | 0.0219 | 0.0099 | 0.0004 | -0.0021 | -0.0008 |

TEST median by TTR (sports `in_play` = after gameStartTime):

| TEST eff_half_med by TTR | <2c | 2-5c | 5-15c | 15-35c | 35-65c | 65-85c | 85-95c | 95-98c | >98c |
|---|---|---|---|---|---|---|---|---|---|
| <=1h | 0.0045 | 0.0050 | 0.0150 | 0.0150 | 0.0150 | 0.0150 | 0.0150 | 0.0050 | 0.0025 |
| 1-6h | 0.0005 | 0.0015 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0025 | 0.0005 |
| 6-24h | 0.0005 | 0.0025 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0020 | 0.0005 |
| 1-3d | 0.0005 | 0.0020 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0015 | 0.0005 |
| in_play | 0.0025 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0005 |

TEST median by category:

| TEST eff_half_med by category | <2c | 2-5c | 5-15c | 15-35c | 35-65c | 65-85c | 85-95c | 95-98c | >98c |
|---|---|---|---|---|---|---|---|---|---|
| crypto | 0.0024 | 0.0050 | 0.0150 | 0.0150 | 0.0150 | 0.0150 | 0.0150 | 0.0050 | 0.0010 |
| culture | 0.0005 | 0.0015 | 0.0045 | 0.0050 | 0.0050 | 0.0050 | 0.0040 | 0.0015 | 0.0005 |
| economics | 0.0005 | 0.0030 | 0.0050 | 0.0005 | 0.0050 | 0.0005 | 0.0083 | 0.0035 | 0.0005 |
| finance | 0.0010 | 0.0055 | 0.0050 | 0.0050 | 0.0100 | 0.0050 | 0.0050 | 0.0050 | 0.0005 |
| geopolitics | 0.0005 | 0.0020 | 0.0050 | 0.0100 | 0.0135 | 0.0090 | 0.0050 | 0.0010 | 0.0005 |
| mentions | 0.0005 | 0.0083 | 0.0150 | 0.0100 | 0.0150 | 0.0100 | 0.0100 | 0.0090 | 0.0025 |
| other | 0.0005 | 0.0040 | 0.0100 | 0.0100 | 0.0050 | 0.0150 | 0.0150 | 0.0100 | 0.0010 |
| politics | 0.0005 | 0.0035 | 0.0040 | 0.0100 | 0.0050 | 0.0100 | 0.0030 | 0.0025 | 0.0005 |
| sports | 0.0005 | 0.0010 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0050 | 0.0005 | 0.0005 |
| tech | 0.0005 | 0.0040 | 0.0115 | 0.0156 | 0.0113 | 0.0125 | 0.0100 | 0.0015 | 0.0005 |
| weather | 0.0024 | 0.0074 | 0.0100 | 0.0125 | 0.0105 | 0.0102 | 0.0100 | 0.0075 | 0.0010 |

**Reading.**
- Small taker trades paid a median of **half a tick** in every split: 0.5c at mid prices, 0.05-0.25c at the extremes. This agrees with
  the live-book quoted half-spreads.
- **Exception: the last hour in TEST, and crypto.** The median is 1.5c at mid prices. Means are larger (TEST 1.75c overall vs 0.66c train)
  and 29% of TEST trades show a *negative* effective spread. This is the signature of a series that is up to a minute stale in fast
  markets (5- and 15-minute crypto windows). In those markets the minute snapshot is not a reliable mid, so true costs are uncertain;
  use the medians or the live books.
- Selection: takers choose when to trade, so these are lower bounds for a strategy that must trade at a fixed horizon.

**Recommendation for backtests.**
- Small orders (under about $500): cost = max(historical median effective half-spread for split x price x TTR, live-book half-spread),
  plus fees.
- Larger orders: add the live-book slippage at that size from the `vol10k` model (or the volume tier, V1/V2), and state that it is
  today's book.
- Sensitivity: double the cost.


## 6. Acceptance checks (pre-registered in section 0)

| # | check | result | verdict |
|---|---|---|---|
| 1 | every category x quarter cell gets >= min(N, 5); TEST >= 55% | 0 violations in 132 cells; TEST 62.5% | **PASS** |
| 2 | >= 90% non-empty fidelity-60 series; >= 85% priced at both T-1d and T-1h (`res`) | 98.7% non-empty; **81.1%** priced at both | **FAIL** as specified |
| 3 | `obs_ts <= horizon_ts` in 100% of rows; horizons after closedTime null | 0 violations; 0 priced post-close rows | **PASS** |
| 4 | fidelity-60 point = fidelity-1 point at the same minute within 0.5c in >= 90% | 100% (exactly equal, n = 409,692) | **PASS**: fidelity-60 points are snapshots |
| 5 | median gap to the last trade at t <= the gap at t+5 min | 0.5c = 0.5c at every lag | **PASS, but uninformative** (see below) |
| 6 | >= 95% of tapes complete; IQR of tape notional / volumeNum inside [0.2, 5] | 99.93% complete (1 hit the cap); IQR 0.41-0.56 | **PASS** |
| 7 | >= 800 two-sided live books; headline cells n >= 20 or collapsed | 1,055 `vol10k` + 1,694 `allopen` two-sided markets per round; headline table (5.2) cells all have >= 179 markets; finer cells below 20 are flagged and collapsed by level | **PASS** (but L0 cells are mostly < 20: 4/356) |

**Changes made after seeing results (declared here, not pre-registered).**
1. The `vol10k` book universe was added after the first all-open snapshot showed that most open markets have empty placeholder books.
   That snapshot is kept as `allopen`.
2. Books are bucketed by each outcome side's own price, using the mirror. The first version bucketed by min(p, 1-p), which mixed
   cheap-token buys with expensive-token buys.
3. The historical effective-spread model (5.3) was added.
4. The mean-gap and change-event tests were added to check 5.
5. A `null_reason = after_series_end` rule was added for 202 game-horizon rows. Without it, those rows would have carried a price
   older than the horizon by more than one fidelity step.

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
- **Volume screen.** Full-life `volumeNum` is a strong look-ahead for TEST short-horizon markets (4.1). Use `vol_screen_at_h`
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
