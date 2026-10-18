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
