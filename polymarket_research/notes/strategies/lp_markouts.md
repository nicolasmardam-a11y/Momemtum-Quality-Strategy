# Family D — selective liquidity provision (historical part): taker markouts and maker P&L

Status: COMPLETE (historical part). As-of 2026-10-17 (written 2026-10-18). Verdict: MARGINAL, no demonstrated trading edge in the current fee regime. **[corrected by auditor] Audited verdict: NO DEMONSTRATED EDGE** (see the Audit section at the end). Author: research agent (read-only public data; no orders, no wallet).
Companion: `notes/strategies/lp_rewards_live.md` (live part: websocket books, queue-aware fill simulation, rewards). This file
uses only the historical taker tapes, the minute price series and today's books from the stage-2 panel (`panel.md`).

## 0. Pre-registration (written 2026-10-18 05:11 UTC, BEFORE any markout or maker-P&L number was computed)

Nothing in this section may be changed after results are seen. Deviations go in section 8.
Before writing it I looked only at schemas and coverage. Facts: tapes have one row per transaction; minute stamps are not
on the minute; 1,499 of 1,603 tape markets have a minute series covering at most 72 h; `clobRewards_json` is `[]` on closed
markets; `fee_rate` is blank for 55% of tape markets. I computed no price change, spread or P&L.

### 0.1 Questions
- Q1. What adverse selection does a passive maker face on Polymarket? That is, the signed post-trade move of the reference price
  in the taker's direction at 10 s, 1 m, 5 m, 1 h, 24 h and at resolution. Cuts: category, price bucket, time to resolution,
  trade size, sports game clock (pre-match vs in-play), recent volatility and order-flow imbalance.
- Q2. Is maker P&L per filled share positive once adverse selection is netted? Maker P&L = realised spread, i.e. effective
  half-spread minus markout. Is it positive in any filter cell chosen ex ante on train and validation? Trading P&L is kept separate
  from maker rebates and liquidity rewards.
- Q3. What forward data is needed to settle what history cannot, namely fill probability and queue position?

### 0.2 Data and units
- Tapes: `data/derived/tapes/tape_*.parquet`, 5.66M taker rows from 1,603 markets: 1,503 liquid plus 100 null-volume audit
  markets. Split is the market's split from `tape_selection.parquet`, set by resolution date: TEST 2026-01-01..2026-10-15,
  validation 2025-07-01..2025-12-31, train earlier.
- Taker event = one tape row (one row per transaction, VERIFIED). Fields: traded token index i, taker direction d (+1 BUY,
  −1 SELL), price P (traded token), shares q.
- Token-0 terms: p0 = P if i = 0, else 1 − P; d0 = d if i = 0, else −d. Books are mirrored (panel, VERIFIED).
- The maker on the other side is short the traded token at P when d = +1 and long it when d = −1.

### 0.3 Reference prices (two, fixed in advance)
- **M (primary for h ≥ 1 m):** the CLOB `/prices-history` fidelity-1 series of token 0 (`price_series_m1.parquet`). It is a
  midpoint, or last trade when the spread is above 10c (panel, PLAUSIBLE). It covers at most the 72 h before resolution.
  - Pre-trade M(t−) = last stamp strictly before t. Post-trade M(t+h) = last stamp ≤ t+h.
  - Missing if M(t−) is more than 120 s old, or if no stamp exists after t and on or before t+h, unless t+h is past resolution.
- **R (print mid; only reference at 10 s, robustness elsewhere, covers the full market life):** in token-0 terms,
  R(τ) = (last ask-side print + last bid-side print)/2, using prints at or before τ. Ask-side means d0 = +1, bid-side d0 = −1.
  - Pre-trade R(t−) uses prints strictly before t. Post-trade R(t+h) uses prints ≤ t+h and therefore includes the trade itself.
  - Missing if either side's last print is older than max(600 s, h), or the bid-side proxy exceeds the ask-side proxy (crossed).
- **At resolution and past it:** if t+h ≥ closedTime, the reference is the payout Y (1 if token i won, else 0). Markets with
  unknown winner are dropped from resolution metrics. The resolution horizon uses Y only, so it is reference-free.

### 0.4 Metrics, per taker event, in traded-token price units (0.01 = 1c per share)
- Effective half-spread `eff = d·(P − ref(t−))`.
- Markout `mo_h = d·(ref(t+h) − ref(t−))`. Positive means the price kept moving in the taker's direction, which is adverse
  for the maker.
- Realised spread, the maker's trading P&L per share marked at h: `rs_h = d·(P − ref(t+h)) = eff − mo_h`.
- To resolution: `rs_res = d·(P − Y)`.
- Prospective maker rebate per filled share: `reb = rebateRate × rate × P(1−P)`. Rate and rebateRate come from the market's
  current Gamma `feeSchedule` (fields `fee_rate`, `fee_rebate_rate`) where present, else the `pmr.fees` category table
  (TAKER_RATE, MAKER_REBATE_SHARE).
  - This is the current schedule applied to all splits, a prospective "as if today" view. It is exact only if every fill in
    the market paid that rate. It is discretionary and temporary, so it is reported separately and never netted silently.
- Liquidity rewards: closed markets carry no reward config, so they cannot be attributed historically. They are reported only as
  a separate order-of-magnitude line from the 2026-10-17 cross-section and `lp_rewards_live.md`.
- Committed capital per share for a maker who is flat beforehand: 1 − P when d = +1 (maker effectively buys the complement),
  P when d = −1.
  - Return on committed capital to resolution = Σ q·rs_res / Σ q·cap.
  - Holding period = closedTime − t. No annualisation.
- Weighting: **share-weighted means are primary** (P&L per filled share). Trade-weighted means and medians are secondary.

### 0.5 Conditioning variables (all computed from information strictly before t)
- Category: panel category. Price bucket: traded token P, panel buckets (<2c, 2-5c, 5-15c, 15-35c, 35-65c, 65-85c, 85-95c,
  95-98c, >98c).
- Time to resolution on the scheduled clock (endDate): past_end, ≤1h, 1-6h, 6-24h, 1-3d, 3-7d, 7-30d, >30d.
- Size, notional q·P: <$10, $10-100, $100-1k, $1k-10k, ≥$10k.
- Sports game clock (markets with gameStartTime): pre>24h, pre6-24h, pre1-6h, pre≤1h, inplay0-1h, inplay1-2h, inplay2-4h,
  inplay>4h.
- Recent volatility: |R(t−) − R(t−−3600 s)| in token-0 terms, both strictly before t. Buckets: <0.5c, 0.5-2c, 2-5c, ≥5c, NA.
- Imbalance: OI = Σ d0·q / Σ q over prints in [t−3600, t), requiring at least 3 prints. Alignment a = d0·OI.
  Buckets: with-flow-strong (a > 0.5), with-flow (0 < a ≤ 0.5), against (a ≤ 0), NA.
- Scheduled-release flag: economics or finance market whose question matches
  CPI|inflation|Fed|FOMC|interest rate|rate cut|rate hike|jobs|payroll|unemployment|GDP, with TTR ≤ 24 h.
- Fee era within TEST: trades before vs after 2026-03-30, when fees went to all categories.

### 0.6 Inference
- Cluster bootstrap with Poisson(1) weights on (a) `event_id` and (b) ISO week of the trade, 500 replications each.
- The reported 95% CI is the wider of the two. Contracts of one event share outcomes and news, so event clustering is mandatory.

### 0.7 Primary metrics and the filter-selection protocol
- **Primary trading metric:** `rs_5m` with reference M, share-weighted (turnover maker marked to mid after 5 minutes).
- **Co-primary:** `rs_res` (hold to resolution).
- Net maker P&L = trading metric + reb, with rewards on a separate line.
- **Candidate cells:**
  - every one-way cell of the section 0.5 variables;
  - two-way category × price bucket and category × TTR;
  - sports game clock × price bucket.
- **Selection** uses train and validation only. A cell is selected if, in BOTH train and validation separately:
  - share-weighted (rs_5m^M + reb) > 0;
  - its cluster-bootstrap 95% lower bound is > 0;
  - it has ≥ 30 events and ≥ 2,000 trades.
- **Evaluation:** the selected cells are evaluated once in TEST, each cell and their union. The number of candidate cells is
  reported.

### 0.8 Rejection criteria (pre-registered)
- **R1 (no edge).** Rejected if no selected cell has TEST share-weighted (rs_5m^M + reb) with a 95% lower bound above 0. If no
  cell is selected at all, also rejected.
- **R2 (incentive dependence).** A cell whose TEST rs_5m^M (no rebate) has a lower bound ≤ 0 but whose net is > 0 is labelled
  INCENTIVE-DEPENDENT. It is not counted as a trading edge.
- **R3 (reference artefact).** The TEST point estimate of rs_5m^R must have the same sign as rs_5m^M. Otherwise the cell is
  flagged reference-fragile and not counted.
- **R4 (inventory to resolution).** A cell whose TEST rs_res (no rebate) has a 95% upper bound below 0 is rejected for any
  strategy that may hold inventory to resolution.
- **R5 (back-of-queue haircut).** The TEST net P&L must stay > 0 when each trade is reweighted by the fill a new order at the
  back of the touch queue would get.
  - Fill weight = min(250, max(0, q − D)) shares, where D is the median best-level size, in shares, for that side's price bucket
    in today's `vol10k` books (r2 and r3 pooled). No cancellations ahead of us.
  - Otherwise the cell is QUEUE-FRAGILE and not deployable.
- **R6 (economic size).** The net must be ≥ 0.1c per share, in a TEST cell with ≥ 30 events and ≥ 10 distinct weeks. Otherwise
  it is too small or too thin to act on, given latency and API costs.
- **Verdict mapping.**
  - Survives R1-R6: promising_test_further. Even then, the live queue-aware study (`lp_rewards_live.md`) must confirm it before
    any capital, because history cannot show fills.
  - Positive only via rebates: marginal / incentive-dependent.
  - Otherwise: no demonstrated edge.

### 0.9 Known limits accepted in advance
- **Fills.** Prints show where takers traded, not whether a given resting quote would have filled. Queue position, cancels and
  hidden competition are unobservable (section 6). Every historical maker number is the **aggregate maker side's** P&L, which is
  an upper bound for a late-arriving retail quote.
- **Selection.** The tape sample is the most liquid markets by full-life volume (look-ahead selection, panel section 4).
- **Fee regimes.** Pre-2026 trades had no fees, so the taker population differed. TEST spans several fee regimes.

---
*Everything below was written after the results were computed.*

## 1. Summary

**Units.** Cents per filled share, share-weighted. CI = the wider of event- and week-cluster bootstrap 95% intervals.
**Sample.** TEST = 3.59M taker trades, 942 markets, 870 events.

1. **Adverse selection eats almost the whole spread (VERIFIED on the tapes).**
   - TEST takers paid an effective half-spread of 0.70c against the minute mid.
   - The mid then moved in the taker's direction by 0.34c within 10 s (print reference), 0.48c by 1 min and 0.65c by 5 min.
   - The aggregate maker side's 5-minute realised spread is **+0.05c [-0.12, 0.22]**.
   - Held to resolution it is **+0.11c [-0.64, 0.80]**.
   - Train −0.01c [-0.22, 0.15]; validation +0.19c [0.10, 0.32].
2. **In the current all-category fee regime it is about zero or negative.**
   - From 2026-03-30 (1.88M trades): 5-minute realised spread −0.01c [-0.25, 0.22] with the minute series, −0.07c [-0.21, 0.06]
     with the print mid.
   - With the current maker rebate: +0.08c [-0.15, 0.31].
   - After the back-of-queue haircut: **−0.12c [-0.31, 0.04]**.
   - Before 2026-03-30 the same quantity was positive: +0.20c [0.02, 0.35], print mid +0.19c [0.11, 0.28].
   - Rebates are therefore, at best, what keeps the aggregate maker side flat today. The cause is PLAUSIBLE, not proven: taker fees
     priced out small noise flow, and rebates attracted more makers.
3. **Pre-registered protocol.** 321 candidate cells; 16 passed train and validation; 4 passed all six TEST rejection tests (R1-R6):
   sports × 7-30d, price >98c, TTR 7-30d, TTR ≤1h. Three more pass R1 only because of rebates and are labelled
   INCENTIVE-DEPENDENT: crypto, non-sports, and $10-100 trades.
4. **A disclosed artefact check removes most of the survivors.** These checks were added after the results (section 8).
   - **TTR 7-30d and sports × 7-30d.** The minute series covers only the 72 h before close, so in long-TTR cells its sample is entirely
     markets that closed early. That is selection on the future. With the full-life print mid the trading P&L is indistinguishable
     from zero: 0.03c [-0.13, 0.20] and 0.09c [-0.11, 0.40] in the current regime.
   - **TTR ≤1h.** Incentive-dependent in the current regime: trading +0.21c [-0.02, 0.50]. Queue-weighted fills lose
     −2.5c [-6.8, 0.5] per share if held to resolution.
   - **>98c.** Survives with a tiny positive realised spread, print mid +0.11c [0.05, 0.28] in the current regime, about one 0.1c tick.
     It is zero to resolution: 0.00c [-0.15, 0.18]. Rebate ≈ 0. Holding period median 20 days. Economically negligible.
5. **Rewards** cannot be attributed historically: closed markets carry no reward config. They are a separate, discretionary line
   (section 4.3).
6. **Verdict: MARGINAL.** **[corrected by auditor]** The audited verdict is **no demonstrated edge**.
   - Every survivor that is not an artefact is either incentive-dependent (TTR <= 1h) or about one tick per share and zero to
     resolution (>98c).
   - Neither is an economically demonstrated trading edge for a retail maker. See the Audit section.
   - There is no robust trading edge for passive liquidity provision in the current fee regime from the historical record.
   - Narrow conditions with lower adverse selection exist, all PLAUSIBLE and worth forward testing only with queue-aware simulation:
     non-crypto markets in the last hour before endDate, sports pre-match 1-6 h, low 1-hour volatility, and trades in the direction of
     recent flow.
   - Under the strict pre-registered mapping the four survivors would read "promising_test_further". I downgrade because of the artefact
     in point 4, which is a property of the pre-registered primary reference.

## 2. What was built (VERIFIED)

| file | content |
|---|---|
| `analyses/lp_markouts/01_build_markouts.py` | per-taker-event references (M series, R print mid, payout) and conditioning variables; resumable per tape chunk |
| `data/derived/lp_markouts/mk_000..015.parquet` (146 MB) + `market_meta.parquet` | 5,664,362 taker events, 1,603 markets (tape_016 is empty) |
| `analyses/lp_markouts/02_analyze.py` | cell tables with event and week cluster bootstrap (500 Poisson reps each); pre-registered selection and TEST evaluation; back-of-queue weights |
| `data/derived/lp_markouts_cells.parquet` | all split × cell statistics (1-way, 2-way, fee era) |
| `analyses/lp_markouts/out/selection.json`, `union_test.parquet`, `tables.md`, `touch_depth.csv` | selection result, TEST evaluation, formatted tables, today's touch depth |
| `analyses/lp_markouts/03_tables.py` | markdown tables |
| `analyses/lp_markouts/04_robust.py` → `out/robust_cells.parquet`, `out/capacity.json` | survivors × fee era and × early-close flag; capacity (post hoc, section 8) |

**Coverage, as share of trades with a usable reference:**

| split | M (minute series) at 5 m | R (print mid) at 10 s | payout known |
|---|---|---|---|
| TEST | 52% | 63% | 95% |
| validation | 35% | 43% | 100% |
| train | 17% | 49% | 100% |

M exists only in the 72 h before close. Train and validation markets are longer-lived, so their M samples are smaller and later in life.
Events: 1,369 in total. Weeks: 151.

**How the costs were estimated.**
- The maker's fill price is the actual print, so no spread model is needed for the historical realised spread.
- Reference prices M and R are not executable. They are only marks.
- The spread model enters only through:
  - the back-of-queue haircut, which uses today's touch depth from the `vol10k` books (median 986 shares at 35-65c; 60-540 elsewhere;
    `out/touch_depth.csv`); and
  - the supplementary crossing-exit line: taker fee plus half a tick.

## 3. Adverse selection (Q1)

Same units as section 1 (cents per share, share-weighted). "eff" = effective half-spread vs M; "mo" = markout; rs = eff − mo; full
tables in `analyses/lp_markouts/out/tables.md`.

**By split:**

| split | trades | events | eff | mo 10 s (R) | mo 1 m | mo 5 m | mo 1 h | mo 24 h | rs 5 m [CI] | rs to resolution [CI] |
|---|---|---|---|---|---|---|---|---|---|---|
| train | 1.32M | 243 | 0.87 | 0.17 | 0.80 | 0.88 | 0.79 | 0.71 | −0.01 [−0.22, 0.15] | 0.39 [0.05, 0.84] |
| validation | 0.75M | 257 | 0.65 | 0.20 | 0.32 | 0.47 | 0.95 | 1.09 | 0.19 [0.10, 0.32] | −0.00 [−1.05, 0.98] |
| test | 3.59M | 870 | 0.70 | 0.34 | 0.48 | 0.65 | 0.36 | 0.40 | 0.05 [−0.12, 0.22] | 0.11 [−0.64, 0.80] |

**Reading the TEST cells (VERIFIED as computed; interpretation PLAUSIBLE).**
- **Category.** 5-minute realised spread, with rebate in parentheses:
  - crypto +0.08 [−0.21, 0.33] (rebate 0.32, so net 0.45 [0.14, 0.73]);
  - sports −0.04 [−0.32, 0.22];
  - politics +0.11 [0.05, 0.31];
  - weather +0.27 [0.09, 0.47];
  - mentions +0.98 [0.22, 1.43], but only 18 events;
  - tech −0.70 [−1.53, 0.10];
  - geopolitics +0.14 [−0.05, 0.27], with no rebate.
  - Markouts are largest in tech, weather and mentions (1.7-2.0c at 5 m).
- **Sports game clock.**
  - Pre-match ≤1h: +0.41 [0.26, 0.61]. Pre-match 1-6h: +0.27 [0.19, 0.35]. Pre-match 6-24h: +0.14 [0.00, 0.27].
  - In-play: 5-minute markouts of 1.3-1.8c and realised spreads of −0.20 to −0.70 (CIs span 0).
  - Pre-match >24h holds to resolution at −9.1c [−16.4, −0.7].
  - Makers are adversely selected in-play (latency; some sports markets have `secondsDelay`) and in long-dated pre-match inventory.
  - The pre-match 1-6h cell did not pass train and validation selection, so it is post hoc and PLAUSIBLE only.
- **Price.**
  - Realised spread ≈ 0 except 85-95c (+0.60 [0.03, 1.25]) and >98c (+0.31 [0.01, 0.94]).
  - To resolution, <2c pays makers +0.12c [0.04, 0.22]: makers selling long shots, consistent with the favourite-longshot bias, but
    tiny.
  - The M-based eff/mo split is biased at the extremes (eff −0.58c at <2c, +3.4c at 85-95c). There the series is a stale or
    last-trade display price, so use rs, which needs only the post-trade mark, or R.
- **Time to scheduled end.**
  - ≤1h: +0.19 [0.01, 0.39]. 6-24h: +0.17 [0.08, 0.30]. >30d: +0.17 [0.03, 0.37].
  - 1-6h: −0.18. 3-7d: −0.33. Neither is significant.
  - Past endDate (trades before close): the M reference is unusable (eff −7.9c).
- **Size.** 5-minute markouts rise with notional: $10-100 0.28c, $100-1k 1.03c, $1k-10k 1.15c. Realised spreads are near 0 for all sizes.
  The <$10 M-based numbers are distorted by the same display-price issue.
- **1-hour volatility before the trade.**
  - Markout 5 m: 0.23c (<0.5c vol), 0.69c (0.5-2c), 1.88c (≥5c).
  - Realised spread: +0.17 [0.10, 0.25] in calm markets vs −0.39 [−1.03, 0.14] in volatile ones.
  - Avoiding volatile markets is the most consistent filter, but it was not selected in train and validation.
- **Imbalance.**
  - Takers trading against the prior hour's net flow have 1-hour markouts of 1.95c and realised spread −0.32 [−0.89, 0.19].
  - Takers trading with strong flow: 1-hour markout −1.14c and realised spread +0.30 [0.07, 0.62].
  - Contrarian takers look informed; momentum-chasing takers do not. This is consistent with short-horizon reversion
    (see `mean_reversion.md`).
- **Scheduled releases** (economics/finance keyword markets ≤24h before end): 3,913 trades in 7 events. Too thin to conclude.

## 4. Maker P&L net of adverse selection (Q2)

### 4.1 Trading P&L vs incentives
- Trading P&L is the realised spread (cents/share). It is ≈ 0 for the aggregate maker side in TEST and in the current fee era (section 1).
- The **maker rebate** under the current schedule averages 0.07c/share over TEST trades:
  - 0.32c in crypto, 0.12c in sports and finance, 0.00c in geopolitics.
  - It is proportional to rate × P(1−P), so it vanishes at the extremes.
  - It is discretionary ("may change") and is reported separately.
- A maker that unwinds by **crossing** (taker fee + half tick) loses: TEST 5-minute net after crossing exit −0.56c, ≤1h −1.25c,
  crypto −1.58c. Unwinding must be passive.

### 4.2 Pre-registered selection and TEST evaluation

Flags R1..R6 are Y/n in the pre-registered order.

| cell | R1-R6 | net 5 m [lo] | trading rs 5 m [lo] | rs 5 m (R) | to resolution [hi] | net, queue-weighted | events / weeks |
|---|---|---|---|---|---|---|---|
| sports × 7-30d | YYYYYY | 0.34 [0.17] | 0.20 [0.02] | 0.06 | 1.53 [8.35] | 0.17 | 109 / 36 |
| pb >98c | YYYYYY | 0.32 [0.01] | 0.31 [0.01] | 0.07 | −0.02 [0.14] | 0.12 | 869 / 70 |
| TTR 7-30d | YYYYYY | 0.19 [0.10] | 0.14 [0.07] | 0.07 | 0.50 [1.21] | 0.20 | 297 / 45 |
| TTR ≤1h | YYYYYY | 0.51 [0.31] | 0.19 [0.01] | 0.17 | 1.27 [6.44] | 0.26 | 608 / 42 |
| crypto | YnnYYY | 0.45 [0.14] | 0.08 [−0.21] | −0.00 | 0.23 [0.87] | 0.25 | 273 / 41 |
| non-sports (game = none) | YnYYYY | 0.22 [0.11] | 0.09 [−0.01] | 0.10 | 0.34 [0.66] | 0.19 | 507 / 85 |
| size $10-100 | YnYYnY | 0.23 [0.10] | 0.07 [−0.05] | 0.10 | 0.03 [0.46] | −0.03 | 870 / 81 |
| 9 other selected cells | fail R1 | | | | | | |

- The union of the 16 selected cells covers essentially all TEST trades, so it is not informative: net 0.18 [0.00, 0.34], trading
  0.04 [−0.13, 0.21], queue-weighted 0.05 [−0.11, 0.20].

**Robustness of the survivors (post hoc, `04_robust.py`; current fee era = trades from 2026-03-30):**

| cell | trading rs 5 m (M) [CI] | rs 5 m (R) [CI] | net, queue-weighted [CI] | queue-weighted, to resolution [CI] |
|---|---|---|---|---|
| sports × 7-30d | 0.22 [0.01, 0.36] | 0.09 [−0.11, 0.40] | 0.17 [0.05, 0.44] | 2.80 [−1.38, 5.34] |
| >98c | 0.46 [0.05, 1.25] | 0.11 [0.05, 0.28] | 0.29 [0.02, 0.68] | 0.03 [−0.20, 0.45] |
| TTR 7-30d | 0.12 [0.05, 0.22] | 0.03 [−0.13, 0.20] | 0.15 [0.05, 0.22] | 0.14 [−0.55, 0.78] |
| TTR ≤1h | 0.21 [−0.02, 0.50] | 0.21 [−0.03, 0.40] | 0.09 [−0.57, 0.71] | −2.50 [−6.78, 0.52] |
| TTR ≤1h excluding crypto (post hoc) | 0.27 [0.15, 0.32] | 0.28 [0.16, 0.34] | 0.43 [0.28, 0.57] | −6.44 [−16.48, 1.00] |
| all TEST | −0.01 [−0.25, 0.22] | −0.07 [−0.21, 0.06] | −0.12 [−0.31, 0.04] | −0.42 [−1.59, 0.36] |

- **Early-close artefact.** In both 7-30d cells, 100% of M-sample trades are in markets that closed more than a day before endDate.
  Trades in on-schedule markets have no M there at all. Early-close markets hold 186k of the cell's 673k trades for TTR 7-30d, and
  30k of 33k for sports × 7-30d. The print mid, which has no such
  selection, shows ≈ 0. **These two survivors are UNSUPPORTED as edges.**
- **TTR ≤1h.** The positive 5-minute mark comes with large losses if inventory is held to resolution. Large, back-of-queue-sized taker
  orders in the final hour are informed beyond 5 minutes, so a maker must be flat before resolution. A crossing exit costs more than the
  edge.
- **>98c.** Robust under both references in the current regime, but small, about 0.1c by the print mid.
  - A maker selling 99c tokens commits 1c per share. The mark-to-mid gain is 10% of committed capital.
  - The to-resolution P&L is 0, with tail risk of 99c per share.
  - The exit at >98c is realistically resolution, with a median 20-day hold. The 5-minute mark is not a realisable P&L there.
  - **PLAUSIBLE, economically negligible.**

### 4.3 Liquidity rewards (separate line; not attributable historically)
- Closed markets show `clobRewards_json = []`, so historical reward configs are unknown.
- Today (from `fees_incentives.md` §3.3) the pool is $190k-290k/day across ~14.5k markets: median $3/day per market, p90 $25.
- Rewards pay for qualifying resting size near mid, sampled each minute. They do not pay per fill, so they cannot be expressed per filled
  share from prints.
- A retail quoter's share depends on competing qualifying depth. This is measured live in `lp_rewards_live.md`.
- Rewards and rebates are discretionary and temporary. Seasonal programs (March Madness, Crypto TWAP August 2026) have ended.
  **No strategy here should be justified by them.**

## 5. Strategy specification (for forward testing only; not a recommendation to trade)

- **Signal.** Quote passively only where historical adverse selection is lowest. All PLAUSIBLE and post-hoc ranked:
  - non-crypto markets 0-60 min before scheduled end;
  - sports pre-match 1-6 h before gameStartTime;
  - 1-hour mid volatility < 2c;
  - optionally skew away from the side being hit against the recent flow.
- **Avoid:**
  - sports in-play (5-minute markouts 1.3-1.8c);
  - 1-hour volatility ≥ 5c;
  - tech and mentions;
  - the side opposed to contrarian prints;
  - long-dated sports pre-match inventory (−9c to resolution).
- **Entry.** Join the best bid and ask (never improve), at the reward min size or the allocation if larger. Enter only when the filter is
  on. Inventory cap 2× quote size, then quote only the reducing side.
- **Exit.**
  - Unwind passively with the opposite quote.
  - Cancel everything when the filter turns off: at gameStartTime, when volatility exceeds the threshold, and T−5 min before endDate.
  - Never hold inventory into resolution in ≤1h markets.
  - Cross only as an emergency (costs the fee plus half a tick, about 0.3-1.6c, more than the edge).
- **Holding period.** Target minutes, with inventory flat within ≤1 h. The >98c variant de facto holds to resolution (median 20 days),
  hence negligible return on capital.
- **Data requirements.**
  - Real-time L2 books via websocket, plus the trade stream.
  - Gamma `endDate`, `gameStartTime`, `secondsDelay`, `feeSchedule`, reward configs.
  - Own-order state, and a queue-position model (section 6).
- **Why it might persist.**
  - Makers are paid for inventory risk and for adverse selection that professional market makers avoid in thin markets.
  - Retail-size flow in small markets is below their threshold.
  - Rebates and rewards subsidise quoting.
- **Main reason it might fail.** Fill selection. A late-arriving retail quote at the back of the queue fills mainly against the large
  takers that sweep the touch, and those are the informed ones. In the current fee regime even the aggregate maker side, including
  queue-priority professionals, earns ≈ 0 after 5 minutes, and negative after the back-of-queue haircut.

**Capacity.** From `out/capacity.json`: current fee era, back-of-queue fills capped at 250 shares per taker trade, across the 601 most
liquid TEST tape markets.

| book | daily P&L |
|---|---|
| Quoting everything | −$92/day at 5 m (−$160/day trading, the rest rebate); −$980/day if held to resolution |
| ≤1h non-crypto | +$14/day at 5 m on ~$2k/day of fills, but −$233/day if held to resolution |
| >98c | +$26/day at 5 m; +$10/day to resolution |

- The >98c book needs about $9k/day of new capital held a median of 20 days, so roughly $200-270k of inventory: about 0.004-0.01% per
  day.
- **By account size:**
  - **$5k:** flow-bound in the ≤1h cells (capital recycles within hours). At most a few $/day before latency and competition, and
    negative once resolution risk is counted. In the >98c cell, about $0.2-0.5/day.
  - **$25k:** no more flow in the ≤1h cells; >98c about $1-2.5/day.
  - **$100k:** about $4-10/day in >98c, i.e. ~1-4% a year, with fat-tailed resolution risk.
- The broader universe adds markets, but they are thinner (panel §5).
- **Capacity is effectively nil** after realistic costs, operating effort and the risk that incentives change.

## 6. Why fills and queue position cannot be inferred from prints (Q3), and the forward data needed

**What history cannot show (VERIFIED as a data limitation).**
- The tapes record only executed taker trades: one row per transaction, price and size, no maker order ids or queue state.
- No historical order book exists (panel §5).
- A print at our quoted price does not imply our order filled. Orders ahead of us at that price fill first (price-time priority).
  Unobservable cancellations can move us up. Hidden repricing by others can leave us alone at the touch exactly when informed flow
  arrives.
- Every number above is the **aggregate maker side's** P&L per filled share: an average over all resting orders, including makers with
  queue priority and faster cancels. It is an upper bound for a late, slow retail quote.
- The back-of-queue haircut (fills only from the part of each taker order above today's median touch depth, capped at 250 shares) is a
  crude proxy. It uses today's depth, assumes no cancels ahead of us, and treats the print as executed at the touch.

**Forward data collection needed.** The companion study `lp_rewards_live.md` implements most of this.
1. **Market websocket per target market.** Full book snapshots plus every `price_change` delta and trade, with exchange timestamps.
   This reconstructs L2 at every event. The book is unified, so one token's book suffices.
2. **Own-order simulation (virtual orders).**
   - Post at the touch at time t0 with queue-ahead = displayed size at that price.
   - Advance the queue only on prints at that price and side (conservative). As a sensitivity, also advance pro rata on cancels.
   - A fill needs a 1 s minimum latency. Trade-throughs fill fully.
   - Track inventory, cancel and replace on the same cadence a retail bot could achieve.
3. **Markouts of the simulated fills** against the reconstructed book mid at 5 s, 30 s, 1 m, 5 m, at the cancel time and to resolution.
   These are compared with the historical aggregate-maker markouts here, to measure the queue-selection penalty directly.
4. **Incentive accounting.**
   - Rewards: minute-sampled Q_min share against competing qualifying depth (CLOB `/rewards/markets/current`).
   - Rebates: rebateRate × fee-equivalent of simulated fills.
   - Both kept on separate lines.
5. **Coverage.** At least 4 weeks spanning sports game days (pre-match vs in-play), crypto windows, and scheduled releases (CPI, FOMC).
   At least 30 events per cell. Randomised market selection, not liquidity-ranked.
6. **The only way to measure true queue priority** is posting real minimum-size orders. That is outside this read-only project; flag it
   for a separate, explicitly authorised paper/real test.

## 7. Caveats
- **Sample selection.** Tape markets are the most liquid by full-life volume, a look-ahead selection (panel §4). The bias direction for
  markouts is unknown.
- **The minute series (M)** is a display price: mid, or last trade when the spread is above 10c. It is up to 60 s stale and covers
  only the 72 h before close.
  - Its eff/mo decomposition is unreliable at extreme prices, past endDate and in 5-15-minute crypto. Use rs and the print mid R there.
  - **In long-TTR cells its sample is selected on an early close** (section 4.2).
- **R (print mid)** uses taker prints only, so a side's proxy can be up to 10 min old (max(600 s, h) after the trade). It includes the
  trade itself after t.
- **Horizons that pass closedTime** are marked to the payout. For trades in the final minutes, 5-minute marks partly mix in resolution
  outcomes.
- **Rebate and fees.** The rebate uses today's `feeSchedule`, or the category table for the 55% of tape markets with blank fee fields,
  applied prospectively to all splits. It is exact only if every fill in the market paid that rate. Historical takers mostly paid no
  fee before 2026.
- **Rewards** cannot be reconstructed historically.
- **Skew.** Share-weighted means are dominated by large trades. Medians are much lower: TEST median 5-minute realised spread 0.15c;
  median to resolution −0.30c. Many cells are heavy-tailed.
- **Multiple testing.** 321 candidate cells. The train→validation→test protocol controls it only partly. Post-hoc cells (sports
  pre-match 1-6 h, ≤1h ex-crypto, low volatility, with-flow) are PLAUSIBLE leads, not results.

## 8. Deviations from the pre-registration (declared)
1. **Staleness limits, set while coding before any result (clarifications).**
   - M post stamp must be within 180 s of t+h.
   - R lag for volatility uses a 3600 s age limit.
   - R pre-trade age limit is 600 s.
2. **Supplementary line (post hoc):** net after an exit by crossing (taker fee + half tick).
3. **Post-hoc robustness `04_robust.py`:**
   - survivors × fee era (current regime) and × early-close flag;
   - print-mid CIs for survivors;
   - a "≤1h excluding crypto" cell;
   - capacity under back-of-queue weights.
   - The early-close check revealed that the pre-registered primary reference (M) is selected on future early closes for long-TTR
     cells. I therefore did not apply the strict verdict mapping ("promising_test_further") and report MARGINAL.
4. **Bugs fixed before results were read:** a timestamp unit bug (pandas 3 microseconds) and a NaN book-JSON guard. No result-driven
   changes were made to definitions, buckets or thresholds.
5. **Provenance of the pre-registration (VERIFIED).** Another agent's commit `1686a92` (2026-10-18 05:16:27 UTC; not mine) captured this
   file's section 0, which is byte-identical to the current section 0. It also captured an intermediate `01_build_markouts.py`, before
   the timestamp fix. The first markout results were computed at about 05:24 UTC, so the commit is independent evidence that the
   pre-registration came first. I made no commits.

## Audit (independent adversarial review, 2026-10-18 ~06:05 UTC; auditor did not write sections 0-8)

Script: `analyses/audit/lp_a01_audit.py`, output `analyses/audit/out/lp_a01.json`. It is independent code that reads only
`lp_markouts/mk_*.parquet` and `market_meta.parquet`. Bootstraps use 1,000 reps and take the wider of the event and ISO-week intervals.
Units are cents per share, share-weighted.

**Audited verdict: no demonstrated edge (downgraded from MARGINAL).**

1. **Pre-registration (VERIFIED, git).** Lines 1-123 equal the `1686a92` version except the status line on line 3, which is outside
   section 0.
2. **Headline numbers re-run (VERIFIED).**

   | quantity | TEST | current fee era (from 2026-03-30) |
   |---|---|---|
   | effective half-spread vs M | 0.70c [0.60, 0.82] | |
   | 5-min markout | 0.65c | |
   | rs 5 m, M | +0.05c [-0.09, 0.20] | -0.01c [-0.21, 0.18] |
   | rs 5 m, R | +0.02c [-0.08, 0.10] | -0.07c [-0.19, 0.04] |
   | rs 5 m, M + rebate | | +0.08c [-0.11, 0.27] |
   | to resolution | +0.11c [-0.64, 0.84] | -0.22c [-1.25, 0.70] (-0.17c with rebate) |

   These match sections 1 and 4 within bootstrap noise.
3. **Look-ahead (VERIFIED; it confirms the author's own artefact finding).**
   - In TTR 7-30d, current era, 100% of the M-sample trades are in markets that closed more than 72 h before endDate. M exists only
     in the 72 h before `ref_ts`.
   - The print mid R, which has no such selection, gives +0.03c [-0.12, 0.20].
   - The two 7-30d survivors are artefacts.
4. **Survivors in the current era, re-run.**
   - **>98c:** R +0.115c [0.05, 0.26], significant but about one 0.1c tick per share; to resolution +0.004c [-0.15, 0.19].
   - **TTR <= 1h:** R +0.21c [-0.08, 0.46], not significant without the rebate; with the rebate +0.38c [0.09, 0.63].
5. **Time-ordering leakage (checked, immaterial).** TEST is assigned by market resolution date, so 1.8% of TEST trades (3.0% of
   shares) were executed before 2026-01-01, inside the validation calendar window. Restricting TEST to trade time 2026-01-01..10-15
   changes no headline figure by more than 0.01c. VERIFIED.
6. **Survivorship.** 7 of 1,603 tape markets have no winner index (50-50 or unknown) and drop out of the resolution metrics.
   Negligible. VERIFIED.
7. **Sign conventions (VERIFIED).**
   - eff = d·(P − ref(t−)) in traded-token terms.
   - rs = eff − markout. The maker's P&L is the negative of the taker's.
   - Cheap-token conversion is via to_tok.
   - The post-trade R includes the trade's own print by design. It is mechanical and documented, not look-ahead.
8. **Why the verdict changes.** A retail maker at the back of the queue cannot ensure round-trip fills, so the monetisable P&L
   includes inventory carried to resolution.
   - That is about 0 or negative in every survivor.
   - The only robust 5-minute effect (>98c) is about 0.1c per share, earns no rebate, and has a median 20-day hold.
   - It is worth about $4-10/day at $100k (section 6 capacity).
   - "Statistically detectable, economically nil" is no demonstrated edge, not "marginal".
   - Rebate-only cells are incentive-dependent by the pre-registered R2.
   - The pre-registered "promising" mapping is superseded by the declared artefact check, which this audit confirms.
9. **Not re-run.** The 321-cell selection itself and the queue-weight capacity numbers. They use today's touch depth: an assumption,
   not a measurement.
