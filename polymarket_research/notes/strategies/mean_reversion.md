# Family F: mean reversion after large price moves / liquidity shocks

As-of 2026-10-17. Builds on `universe.md` (stage 1) and `panel.md` (stage 2: tapes, minute series, cost model).
Scripts: `analyses/mean_reversion/`. Derived data: `data/derived/mr_*.parquet`.

## 0. Pre-registration (written 2026-10-17T23:21Z, before any shock outcome was computed)

Nothing below was changed after outcomes were seen, except where section 7 declares it.

### 0.1 Data and universe
- **Primary universe:** the 1,503 `liquid` tape markets (`tapes/`, taker-only `/v2/trades`). The 100 null-volume audit markets
  are excluded. These markets were selected on full-life volume (look-ahead), so the primary design adds a point-in-time
  activity screen (0.2) and reports the selection caveat.
- Prints are converted to token-0 terms: `p0 = price` if `outcome_index == 0`, else `1 - price` (books are mirrored, VERIFIED in panel.md).
- **Secondary universe:** the 8,000-market minute series (`price_series_m1`, 72 h before `ref_ts`), shocks detected on the
  display price. That series is a mid/last-trade display price, **not executable**; results there are cost-adjusted descriptive only.
- Splits by **detection time**: train < 2025-07-01, validation 2025-07-01..2025-12-31, TEST 2026-01-01..2026-10-15.

### 0.2 Shock definition (computed at print i, time t, using only prints at or before t)
- `anchor_last` = p0 of the last print at or before t-300 s; `anchor_med` = median p0 of prints in [t-2100 s, t-300 s].
- Shock if `p0_i - anchor_last` and `p0_i - anchor_med` have the same sign and both have absolute value >= theta,
  theta in {5c, **10c**, 15c}. Detection time `t_det` = time of the first such print. Direction s = sign.
- Adequate prior activity (all at t-300 s): >= 3 prints in [t-2100, t-300]; >= 20 prints in the prior 24 h; cumulative taker
  notional >= $5,000 (about $10k of `volumeNum`, since taker notional is about half of `volumeNum`, panel.md 4).
- Dedup: after a detection, the same market cannot trigger again (same theta) for 3,600 s.
- **Final-hour exclusion, ex ante (primary):** `t_det <= endDate - 1 h` (scheduled clock). **Look-ahead version
  (sensitivity only, the literal task wording):** `t_det <= min(endDate, closedTime) - 1 h`.
- Price band (primary): post-shock `p0_i` in [0.05, 0.95]. Shocks outside it are reported separately.

### 0.3 Trade (reversal side)
- s = +1 -> buy token 1 (sell token 0); s = -1 -> buy token 0. Reversal-token price `q`.
- **Entry:** the first print with timestamp >= t_det + delay, delay in {30 s, **120 s**, 900 s}, and no later than delay + 1,800 s
  and before `min(endDate, closedTime)`; otherwise no trade (counted).
- **Exit:** the first print at or after entry + h, h in {15 m, **1 h**, 6 h, 24 h}, before the market closes; else the resolution
  payout. Also "res": hold to resolution (payout y0 or 1-y0; 0.5 for 50-50).
- **Costs:** half-spread `hs` = max(historical effective half-spread median for split x price bucket x TTR (panel 5.3, falling back
  to coarser levels), live-book `vol10k` median half-spread for category x price bucket (L1 if n >= 20, else L3),
  shock-time local half-spread median by split x price bucket). The shock-time local half-spread is measured on the tape:
  median ask-type minus median bid-type reversal-token prints within +-60 s of the entry print, halved. Paid on entry and on exit
  (not at resolution). Sensitivity: 2 x hs.
- **Fees (prospective, current schedule):** per-market `feeSchedule` if its `feeType` is a current-generation schedule
  (`sports_fees_v3`, `crypto_fees_v2`, `weather_fees`, `finance_prices_fees`, `sports_fees_nfl_cfb_oct26`, `culture_fees`,
  `mentions_fees`, `politics_fees`, `tech_fees`, `economics_fees`, `general_fees`, `zero_fees`), else the `pmr.fees.TAKER_RATE`
  category table. fee/share = rate x p x (1-p) at the fill price, on entry and on a pre-resolution exit. No taker rebate assumed.
  Also reported: gross (prints only, no hs, no fee) and as-traded fees (TEST only).
- Return = net PnL per share / entry cost per share (return on committed capital, held until exit or settlement). No annualisation.

### 0.4 Features at detection time (tape, at or before t_det)
top-wallet share of shock-direction notional in (t_det-300, t_det]; largest-transaction share; distinct taker wallets;
trade count; sibling co-move (sibling minute series over [t_det-300, t_det], multi-market events only); game phase
(no game / pre-game > 1 h / last hour before start / in play = within 4 h after `gameStartTime`); round-time flag (minute 0-4 or
30-34); UTC time of day (0-8, 8-16, 16-24); prior volatility (std of 5-min p0 changes over the prior 24 h; terciles cut on
TRAIN shocks); post-shock price level (0.05-0.2, 0.2-0.8, 0.8-0.95 in p0 terms); category group (crypto, sports, other);
shock size.

Ex-ante subsets: **liquidity-like** = <= 2 distinct takers in the window and top-wallet notional share >= 0.7;
**news-like** = >= 5 distinct takers; **mixed** = the rest. Sibling co-move = any sibling's minute price moved >= 3c in
[t_det-300, t_det].

### 0.5 Primary tests (two, Bonferroni: 97.5% two-sided intervals)
- **P1:** theta 10c, delay 120 s, exit 1 h, all eligible shocks, current fees, TEST.
- **P2:** the same on the liquidity-like subset.
- Inference: mean net return per trade; cluster bootstrap on `cluster_id` and block bootstrap on the ISO week of `t_det`
  (2,000 resamples each); conclusions use the wider interval.

### 0.6 Rejection criteria (any one rejects "edge" for the cell)
- R1: TEST mean net return <= 0, or the lower bound of either 97.5% interval <= 0.
- R2: validation mean net return <= 0 (sign must replicate).
- R3: positive only with the look-ahead final-hour exclusion.
- R4: TEST mean <= 0 at 2 x hs.
- R5: removing the 5 clusters with the largest PnL makes the TEST mean <= 0.
- R6: fewer than 100 TEST trades or 30 TEST clusters -> "inconclusive", not "edge".
- R7: capacity: median reversal-side taker notional within 5 min after entry at <= entry + 1c below $250 -> not viable even for
  a $5k account.
- The 45-cell grid (3 theta x 3 delays x 5 exits) and the feature subsets are descriptive. A non-primary cell can at most earn
  "test further", and only if it passes R1-R5 with Bonferroni over 45 cells (99.9% intervals).

## 1. Verdict (2026-10-18)

**No demonstrated edge (VERIFIED for this sample and cost model).** Both pre-registered primary tests are rejected, and 0 of the
45 grid cells pass R1-R5 at 99.9%. The "liquidity shock" hypothesis, that single-wallet or single-transaction moves revert more,
is **not supported**. Those subsets do worse than multi-taker ("news-like") shocks, the opposite sign. Large moves do partly
revert. Most of that reversion (2.4-6c of a ~15c shock, measured from the detection print) happens before a 30 s taker entry.
Some of it is bid-ask bounce. After entry, the remaining 0.3-2.5c (gross, TEST) is not statistically different from zero, and it
is below the ~2-3c round-trip cost (half-spread both ways plus the current taker fee).

## 2. Pipeline and data
| step | script | output |
|---|---|---|
| detect shocks, features, raw outcomes on taker tapes | `01_detect.py` | `mr_shocks.parquet` (21,888 rows = shock x theta x variant), `mr_trades.parquet` |
| sibling co-move (CLOB `/prices-history` fidelity 1, <= 8 live siblings, points <= t_det) | `02_siblings.py` | `mr_siblings.parquet` (1,258 shocks; 1,256 with priced siblings) |
| costs, fees, returns, tests | `03_outcomes.py` | `mr_returns.parquet`, `out/03_results.json`, `out/03_tables.md`, `out/03b_reversal_profile_cents.csv` |
| secondary: 8,000-market minute display series | `04_minute_series.py` | `mr_m1_returns.parquet`, `out/04_results.json` |

Primary-variant shock counts (theta 10c): train 504 / validation 347 / TEST 888 shocks. TEST covers 314 markets and 298 event
clusters; 5c: 2,270 TEST; 15c: 511 TEST. Entry within the 30-min window succeeded for 96-97% of shocks. The 1 h exit reached
resolution first for 2% of trades, the 24 h exit for 41-49%.

**Cost model actually used (TEST, P1 cell).** Median half-spread 1.0c, mean 0.82c. The binding component was the live-book vol10k
median for 57% of trades, the shock-time local tape spread for 42% and the historical effective spread for 1%. The mean current
taker fee rate is 0.038, about 0.74c per share at entry (geopolitics shocks are fee-free). The live-book component is today's books
applied to history (assumption, panel.md). The tape-local component is a direct estimate, PLAUSIBLE: it pairs ask- and bid-type
prints within +-60 s.

## 3. Pre-registered primary tests (theta 10c, delay 120 s, exit 1 h; return on committed capital per trade)
| test | split | n | clusters | gross | net | median net | hit | 97.5% interval (wider of cluster/week) |
|---|---|---|---|---|---|---|---|---|
| P1 all | train | 478 | 128 | +6.0% | -3.5% | -5.1% | 38% | [-10.6%, +5.2%] |
| P1 all | validation | 336 | 99 | +9.1% | -1.8% | -3.9% | 41% | [-12.4%, +10.8%] |
| P1 all | **TEST** | 869 | 297 | +7.9% | **-0.6%** | -3.3% | 44% | **[-7.3%, +6.3%]** |
| P2 liquidity-like | validation | 113 | 44 | +7.0% | -3.3% | -2.1% | 41% | [-14.0%, +4.4%] |
| P2 liquidity-like | **TEST** | 115 | 64 | +6.7% | **-1.9%** | -5.4% | 39% | **[-13.5%, +12.1%]** |

P1 TEST sensitivities: 2 x hs -4.9%; side-aware entry -0.9%; as-traded (historical) fees +0.8%; drop the top-5 PnL clusters
-5.1%; look-ahead final-hour exclusion -1.3%. In cents per share (equal shares): gross +1.22c [95%: -0.34, +2.69], net -1.57c.
- P1 rejected by R1, R2, R4, R5, R7 (R3 n/a, R6 not triggered). P2 rejected by R1, R2, R4, R5, R7.
- **R7 capacity:** the median reversal-side taker notional within 5 min of entry at <= entry + 1c is $50 (P1). It is $5 for
  liquidity-like shocks and $89 for news-like shocks. Only 29% of shocks see >= $250, 15% see >= $1k and 4% see >= $5k.

## 4. Grid and outcome profile (primary variant, TEST, net mean per trade)
- Short exits (15 m, 1 h, 6 h) are negative or near zero at every theta and delay. The 15 m exits are negative everywhere (-4%
  to -9%).
- The largest positive TEST cells are theta 10-15c with a 24 h or hold-to-resolution exit (+5% to +10% net). A few other cells
  (5c/24 h, 15c/6 h) are within +-1%. For example, 10c/120 s/res
  is +7.4% (99.9%: [-10.7%, +30.9%]) and 15c/120 s/res is +8.7%. Their medians are about 0 or -100% (lottery-like payoffs from
  cheap reversal tokens). Dropping the top-5 clusters turns all of them negative (R5), and train is negative for 10c (-4% to -8%).
  Validation is strongly positive at 15c (+18% to +63%), driven by a few low-price entries. **No cell passes R1-R5 at 99.9%.**
- Reversal profile (theta 10c, delay 30 s, cents of the reversal token, TEST / validation / train):
  - Average shock: 14.7 / 16.4 / 15.9c.
  - Move from the detection print to the 1 h exit: +3.0 / +5.5 / +6.2c.
  - Move from the entry print to the 1 h exit: +0.8 / +1.4 / +1.2c.
  - Net after costs: -2.0 / -2.2 / -2.2c.
  - With delay 120 s, 1.8c of reversion already happened between detection and entry (2.2c with delay 30 s).
  - In TEST, the 15 m gross reversion from entry is only +0.25c [95%: -0.86, +1.29].

## 5. Ex-ante feature subsets (theta 10c, delay 120 s; exit 1 h unless stated; net mean, TEST vs validation; 95% intervals all span 0 unless noted)
- **Regime.** Liquidity-like: TEST -1.9%, validation -3.3%. Mixed: -3.9% / -4.4%. News-like: +0.3% / +1.5%. Hold to resolution:
  liquidity-like -5.8%, news-like +10.8%. The hypothesis predicted the opposite ordering.
- **Single transaction >= 70% of the shock-side notional:** TEST -5.5% (95%: [-10.5%, -0.8%], **reliably negative**), validation
  +0.2%. Shares below 70%: +1.5% / -3.6%.
- **Sibling co-move.** Siblings quiet: +4.6% / -5.0%. Siblings co-moved: -2.5% / +0.6%. No consistent sign.
- **Game phase.** In play (sports): +8.5% / +22.3%. Median -24%, interval spans 0, payoffs skewed. Post-game: -18.6% (95%:
  [-26%, -11%]).
- **Category.** Crypto is negative in both splits: -15.3% / -13.3%, with the TEST interval excluding 0. Sports: +9.8% / +18.8%.
- **Price level.** p0 0.2-0.8: +1.3% / -3.5%. Extremes are noisy.
- **Prior volatility.** High tercile: +2.1% / +6.9%. Low tercile: -2.0% / -8.4%.
- **Shock size.** >= 25c: +12.6% / +24.9%, but only n = 54 / 34. 15-25c to resolution: +20.5% [+0.6%, +41%] / +8.1%.
- **Round-time flag and time of day:** no consistent pattern.
- Leads for a new pre-registration, not results (multiple comparisons, about 60 subset cells): sports in play, very large shocks
  (>= 15-25c), and the high prior-volatility tercile. All three are positive in both validation and TEST but with intervals
  spanning 0. They also have the thinnest reversal-side flow.

## 6. Secondary universe (8,000 markets, 1-min display price, last 72 h only; NOT executable; descriptive)
TEST: 6,218 / 2,753 / 1,551 shocks (5/10/15c), with 1,299 / 990 / 763 clusters.
- **10c / 120 s / 1 h:** net TEST -1.7%, validation -1.0%, train -0.1%; -1.5c TEST.
- **Net TEST at 5c and 10c:** <= +1.6% in every cell, and the 99.9% intervals span 0 or lie below it.
- **Best cell, 15c / 60 s / 6 h:** TEST +4.7% (99.9%: [-4.3%, +15.3%]), +0.2c, drop-top-5 +0.7%.
- **Excluding the 1,503 tape markets:** the same picture.
- **Reversion from the detection point:** 3.0-5.7c for 10-15c shocks, against 0.1-2.6c gross after a 1-2 min entry.
- This **replicates the primary pattern** on a broader universe: fast reversion before entry, and no net edge after it.

## 6a. Strategy card
- **Signal:** a token's print is >= theta (10c) from both the last print >= 5 min earlier and the 5-35 min median. Requirements:
  adequate prior activity (>= 3 prints in the 30 min reference window, >= 20 prints in 24 h, >= $5k cumulative taker notional),
  at least 1 h before the scheduled end, and post-shock price within [0.05, 0.95].
- **Entry:** buy the reversal token at the first print >= 30 s / 2 min / 15 min after detection. Pay the half-spread and the
  current taker fee.
- **Exit:** a later print at +15 m / 1 h / 6 h / 24 h (pay the half-spread and fee), or hold to resolution.
- **Holding period:** 15 m to 1 day on the horizon clock. Hold to resolution: median 1.1 days, mean 8.3 days of lock-up.
- **Data:** a real-time trade feed (taker prints with wallet and transaction hash), sibling-market prices and Gamma metadata.
  A live book is needed to execute.
- **Why it might persist:** thin books and occasional forced or impatient takers create real transient dislocations. The
  detection print does sit 2-6c away from the later price.
- **Main reason it fails:** speed and costs. Faster liquidity providers and bots absorb the reversion within seconds, before a
  retail taker can act. The leftover drift (about 1c) is smaller than the ~2-3c round trip. The reversal side has a median of only
  $50 of fillable flow within 1c over 5 min.
- **Capacity (moot: no edge).**
  - $5k account ($100-250 per trade): at most 29% of shocks have >= $250 of reversal-side flow within 1c. Today's books add median
    slippage on a $500 buy of 1.0c (35-65c bucket), 1.8c (65-85c) and 5c (15-35c).
  - $25k account (~$500-1.25k per trade): 15% of shocks have >= $1k. A $2.5k buy slips 1.1-24c by price bucket.
  - $100k account (~$2.5-5k per trade): <= 4% of shocks have >= $5k. A $10k buy slips 1.3-46c and is fillable in 52-65% of books.
  - Frequency is ~21 TEST trades per week in the 1,503-market tape sample. The full universe would give more.
- **Persistence / failure labels:** fast liquidity provision absorbing the reversion is PLAUSIBLE (consistent with the reversal
  profile, not observed directly: maker fills were not pulled). That costs exceed the after-entry reversion is VERIFIED for this
  sample and cost model.

## 6b. Caveats
- The tape universe was selected on full-life volume (look-ahead, not representative). The point-in-time activity screen
  limits but does not remove this. The secondary universe covers only the final 72 h before resolution.
- Tapes are taker-only, and resting depth at entry is unknown. Costs combine today's books, the historical effective spread
  (a lower bound) and a tape-local estimate. The 2 x hs sensitivity is negative everywhere relevant.
- Hold-to-resolution means are dominated by a few cheap-token payoffs, so medians and drop-top-5 figures are the honest read.
- About 60 feature-subset cells and 45 grid cells were examined, so any positive subset is a hypothesis.
- The 30 s delay is optimistic for a retail taker, and the first print after the delay is not guaranteed to be fillable at that
  price. The side-aware sensitivity (-0.9%) partly addresses this.
- Sibling co-move uses a display series and ranks siblings by full-life volume. That is a look-ahead in which siblings are
  checked, not in the signal.

## 7. Declared implementation choices and deviations (written 2026-10-18 ~05:20Z)

7.1 Choices made while coding step 03, **before** its first run (no outcome seen):
- Cost lookup levels: historical effective half-spread uses H1 (split x price x TTR), else H3 (split x price), cells with
  >= 20 markets. TTR for the cost lookup is measured to `ref_ts` (the res clock). It is used only to price costs, never to select
  trades. TTR beyond 72 h has no H1 cell, so it falls back to H3. Price bucket = the traded (reversal) token's print price.
  The local tape half-spread is the median of `loc_hs` over distinct entry prints by split x price bucket (>= 20), else by split.
- Fee as-traded = the market's own Gamma `fee_rate` if `feesEnabled`, else 0 (the Gamma state at pull time, an approximation).
- Extra sensitivity (not pre-registered): **side-aware entry**. If the entry print was ask-type for the reversal token, fill at the
  print; otherwise pay 2 x hs. Exit keeps the symmetric hs.
- Feature cut points not fixed in 0.4: `single_tx` = top-transaction share >= 0.7; `absshock` buckets 5-10/10-15/15-25/>=25c;
  `sib` = sibling co-move flag, with "no_sib_data" for standalone markets.
- Bootstrap: ratio-of-sums mean per trade, multinomial resampling of clusters (cluster_id) or ISO weeks, 2,000 draws, seed 20261017.

7.2 Added **after** seeing the step-03 results (descriptive only, cannot change a verdict): the reversal profile in cents
(`out/03b_reversal_profile_cents.csv`), measured from the detection print and from the entry print.

7.3 Secondary universe specification (written before step 04 was run). Section 0.1 left it open.
- Series: `price_series_m1` (token 0, display price, 72 h before `ref_ts`), all 8,000 panel markets. The 1,503 tape markets are
  also reported separately.
- Shock at minute point t: `p(t) - p(last point <= t-300)` and `p(t) - median(p over [t-2100, t-300])` have the same sign and both
  are >= theta. Activity screen (point in time): >= 20 changes of the display price in (t-300-86400, t-300], and t >= series start +
  24 h. The final-hour exclusion, the [0.05, 0.95] band and the 1 h dedup are as in 0.2 (sched clock).
- Entry: display price at the first point >= t + delay, delay in {60, 120, 900} s. A 30 s delay is not possible at 1-min resolution.
  Exit: first point >= entry + h. If that is beyond the series end or the close, use the resolution payout. Also hold to resolution.
- Costs: hs = max(hist H1 -> H3, book L1 -> L3). There is no tape-local component. Current fees and gross as in 0.3.
  The display price is **not executable**. This universe is descriptive and cannot overturn the primary verdict.
