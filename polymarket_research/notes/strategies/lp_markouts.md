# Family D — selective liquidity provision (historical part): taker markouts and maker P&L

Status: IN PROGRESS. As-of 2026-10-17 (written 2026-10-18). Author: research agent (read-only public data; no orders, no wallet).
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
