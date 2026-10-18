# Family D — selective liquidity provision (live part): rewards, queue, markouts

Status: COMPLETE (2026-10-18 ~06:10 UTC). As-of 2026-10-17/18. Verdict: NO DEMONSTRATED EDGE (R2 rejected, R3 failed). Author: research agent (read-only, public data only; no orders, no wallet, no auth).

## 0. Pre-registration (written 2026-10-17 ~23:05 UTC, BEFORE any live capture or reward/markout result was computed)

Nothing below this section may be changed after results are seen. Deviations, if any, are reported in section 9.

### 0.1 Questions
- Q1 Rewards: what daily liquidity reward would a hypothetical two-sided quote of $500 / $2,500 / $10,000 earn under the
  documented scoring function, given the competing qualifying depth visible in the public book?
- Q2 Trading P&L: for passive fills at the touch, does the spread captured exceed adverse selection (short-horizon markouts)?
- Q3 Combined: does a simple passive strategy with a conservative fill rule have positive net P&L, and how much of it is incentive-dependent?

### 0.2 Definitions fixed in advance
- Mid for markouts: (best bid + best ask)/2 from the websocket-reconstructed book of the YES token (unified book; the NO book is its mirror).
- Markout of a passive fill at horizon h (5 s, 30 s, 60 s, 300 s): for our bid filled at P, mo = mid(t+h) − P; for our ask filled at P,
  mo = P − mid(t+h). Spread capture = signed distance of fill price from mid at fill time; adverse selection = mid move against us
  from fill time to t+h. Reported per share and per $ of fill notional.
- Conservative fill rule (PRIMARY): a virtual order posted at time t0 joins the back of the queue at its price; queue ahead Q0 = displayed
  size at that price at t0. Queue ahead is reduced ONLY by trades printed at that price on that side (taker sells for our bid, taker buys for
  our ask). Cancellations never advance us. Our order fills only with the trade volume in excess of the queue ahead. A trade printed at a
  strictly worse price than ours (trade-through) fills us fully. Minimum resting time before a fill can count: 1 s after the post
  (latency proxy).
- Optimistic fill rule (SENSITIVITY only): cancellations at our price reduce queue ahead pro rata to their share of the queue
  (i.e. assume cancels are uniformly spread through the queue).
- Strategy sketch (fixed): every 60 s, for each market with mid in [0.10, 0.90] and a reward config, cancel and re-post one bid at the
  best bid and one ask at the best ask (join the touch; never improve the price), size = the reward min size or the capital allocation,
  whichever is larger, only if the price is within rewardsMaxSpread of the size-cutoff-adjusted mid. Inventory cap: when |inventory|
  exceeds 2x the quote size, only the reducing side is quoted. End-of-sample inventory is marked to the mid (not liquidated), and a
  separate "liquidation" line charges crossing the half-spread plus the market's taker fee.
- Reward accounting: per minute, our share = our Q_min / (our Q_min + competitors' Q_min). Competitors' Q_min is not observable per maker,
  so it is bounded: optimistic = max(Q1, Q2)/3, central = the aggregate book treated as one maker, conservative = Q1 + Q2.
  Daily reward = total_daily_rate x mean share; reported separately from trading P&L, never netted silently.
- Maker rebates: estimated as rebateRate x fee-equivalent of our simulated fills (an upper bound: it assumes every fill in the market was
  fee-paying at the same rate). Reported separately.

### 0.3 Rejection criteria (pre-registered)
- R1 (rewards too small at retail size): a market is "reward-attractive" for a size only if the central estimate pays >= $2/day (twice the
  $1 minimum payout) AND >= 0.05% of quoted capital per day. If < 10% of the cross-section passes at $2,500, rewards are rejected as a
  stand-alone profit source at that size.
- R2 (adverse selection): if the pooled mean 60 s markout of conservative-rule fills at the touch is <= 0 (spread capture does not cover
  adverse selection), the trading-P&L leg is rejected ("no demonstrated edge" from spread capture).
- R3 (combined): the strategy sketch needs net P&L (spread capture + adverse selection + inventory MTM + central rewards) > 0 AND a
  market-block bootstrap 90% CI lower bound > 0. Otherwise the verdict is at best "no demonstrated edge". Because the sample is < 1 hour,
  a pass can at most earn "promising_test_further", never a stronger claim.
- R4 (too few fills): fewer than 30 conservative-rule fills in total => trading-P&L results are "inconclusive", not evidence either way.
- R5 (concentration): if > 50% of net P&L comes from one market or one 5-minute window, the result is "not robust".
- R6 (incentive dependence): if net P&L is positive only with rewards included, label "incentive-dependent" and cap the verdict at
  "marginal" (rewards are discretionary per-market allocations that change daily).
- R7 (dilution): if the $2,500 quote's central reward share in the median selected market is < 1%, rewards are "diluted".
- R8 (persistence): a market's reward allocation must be present in the reward snapshot at the start and at the end of the capture window;
  markets whose allocation disappears are flagged and excluded from the yield table.

(Sections 1-9 are filled in after collection.)

## 1. Program mechanics (docs read in full 2026-10-17; copies in `data/raw/docs_lp/`)

**Liquidity Rewards** ([/programs/liquidity-rewards](https://docs.polymarket.com/programs/liquidity-rewards.md)) — VERIFIED (docs)
- Resting limit orders are scored automatically; paid daily at midnight UTC to the maker address; **$1 minimum payout**.
- Per market: max qualifying spread `v` (cents, `rewardsMaxSpread`), min qualifying size (shares, `rewardsMinSize`), daily allocation.
- Order score `S(v,s) = ((v−s)/v)² · b`, `s` = distance from the **size-cutoff-adjusted midpoint**, `b` = in-game multiplier.
  The docs never define the size-cutoff adjustment precisely (UNSUPPORTED which variant is used); I test three variants (section 3).
- `Q_one` = S-weighted bids on m + asks on m′; `Q_two` = asks on m + bids on m′. `Q_min = max(min(Q1,Q2), max(Q1,Q2)/3)` when the
  mid is in [0.10, 0.90], else `min(Q1,Q2)` (two-sided required). Per-sample normalisation across makers, sampled once a minute at a
  random offset (≤1,440 samples per UTC day), then normalised again over the epoch × the market's daily allocation.
- Implications (my derivation, PLAUSIBLE): (i) `b` multiplies every order in a market-sample, so it cancels in the per-sample share;
  (ii) because each sample is normalised, the full daily allocation is split among whoever is scoring in the sampled minutes, so a
  market that is only open (or only quoted) for part of the day pays the whole pool to those present; (iii) the score is quadratic in
  distance, so a quote at 0.5¢ from mid with v = 4.5¢ scores 0.79/share, at 2¢ it scores 0.31/share.
- Docs inconsistency: the worked example's `Q_no` lists "bid on m @ 0.485", while equation 3 defines `Q_two` with *asks* on m.
- The **Crypto TWAP $1M** (August 2026) programme is marked ended.
- `/order-scoring?order_id=` (auth) says an order scores only if live on a rewards market, ≥ min size, within spread, and **"live for the
  required duration"** (duration not stated; the changelog quoted 3.5 s for March Madness, see platform notes).

**Maker Rebates** ([/programs/maker-rebates](https://docs.polymarket.com/programs/maker-rebates.md)) — VERIFIED (docs)
- Pool = rebate share × taker fees **in that market** (Crypto 20%, Sports 15%, others 25%, Geopolitics none; legacy `sports_fees_v2`
  keeps 25% per Gamma). Split pro rata to `fee_equivalent = C × feeRate × p × (1−p)` of your **filled** maker orders. Daily, $1 minimum.
  "At the sole discretion of Polymarket and may change." Only filled liquidity earns a rebate; resting quotes earn nothing.

**Market making guide** ([/trading/market-making](https://docs.polymarket.com/trading/market-making.md)) — VERIFIED (docs)
- GTC/GTD (+ post-only) for passive quotes; **orders cannot be edited in place** (cancel + replace = new queue position);
  batch submission; keep a local book from the market websocket; inventory via split/merge; GTD to expire before catalysts.
- Programs listed for MMs: Liquidity Rewards and Maker Rebates, "eligibility, calculations and payouts differ".

**Endpoints (live checks 2026-10-17 23:00 UTC)** — VERIFIED
- `GET clob/rewards/markets/current` public, 500/page: 14,331 markets with a config, `total_daily_rate` sum **$189,839/day**
  (vs $289,412/day across 14,608 markets at 15:09 UTC and $191,809 at 22:05 per the verifier; game-day props drop out).
- `GET clob/rewards/markets/multi` public (`page_size` ≤ 500, `order_by`, `min_volume_24hr`, …). It lists essentially **all** markets,
  including ones with an empty `rewards_config`; it adds tokens, `volume_24hr`, `spread` and `market_competitiveness`.
- Gamma `rewardsMinSize` / `rewardsMaxSpread` / `clobRewards` agree with the CLOB endpoint for the sampled markets (section 3).
- Market websocket `wss://ws-subscriptions-clob.polymarket.com/ws/market`: `book`, `price_change` (new aggregate size per level, plus
  `best_bid`/`best_ask`), `last_trade_price` (price, size, **taker side**, ms match time, tx hash), `tick_size_change`; with
  `custom_feature_enabled` also `best_bid_ask`, `new_market` (all new markets, not only subscribed ones), `market_resolved`.
- The AsyncAPI lists an undocumented subscription `level` (1/2/3). A 25 s probe on one market with level 1 and level 3 returned the
  **same event types and fields** (aggregated levels only, no order ids) — VERIFIED for that probe (`00_ws_level_probe.py`). The
  `price_change.hash` field ("hash of the order that caused this change") differs between the YES and NO rows of the same change, so it
  cannot be used to follow an order through the queue (VERIFIED in the capture). **There is no public per-order (L3) feed**, so queue
  position can only be modelled, not observed.
- `last_trade_price.fee_rate_bps` was `0` on every print captured, including fee-charging markets: do not use it for fees (use `feeSchedule`).

## 2. Data collected (VERIFIED: provenance on disk)
- **Reward configs** (`01_rewards_pull.py`): `rewards_t0` (2026-10-17 ~23:00 UTC), `rewards_t1` (10-18 04:56), `rewards_t2` (10-18 05:52).
  Platform `total_daily_rate` sum **$189.8k → $181.3k → $179.3k per day** (it was $289.4k at 10-17 15:09; game-day props drop out).
  Between t0 and t2 (~7 h): 1,001 of ~14.3k markets lost their config, 1,026 gained one, 20% changed rate, 5% changed min size / max spread.
- **Cross-section** (`02_select.py`, `04_xsec_snapshot.py`): 1,593 reward markets, stratum A = all 1,006 reward markets with 24 h volume ≥ $500,
  B = a seeded random 500 of the other ~13.2k, C = the 60 largest remaining allocations. YES books snapshotted at s0 (10-17 23:07),
  s1 (23:35) and **s2 (10-18 ~05:00, ~6 h later, added in this session)**.
- **Market websocket** (`03_capture.py`, read-only, `custom_feature_enabled`): w1 23 markets 31 min, w2 150 markets 28 min, w3 40 markets 21 min
  (all three cut at 23:38 UTC when the session was interrupted; planned 45–55 min) and **w4 = 20 markets × 55 min (10-18 04:57–05:52 UTC,
  0 reconnects, 71.5k frames), selected by the same rule from the fresh t1 snapshot** (`10_select_window.py`). Total 233 market-windows,
  114 market-hours; 4 politics / 4 sports / 2 each weather, culture, tech, crypto, economics / 1 zero-fee / 1 other in w4.
  REST `/books` every 60 s alongside each capture; WS-reconstructed touch agrees with REST in 91–98% of samples.
- Raw frames: `data/raw/clob_ws/live/20261017/lp_w{1,2,3}_*.jsonl.gz`, `data/raw/clob_ws/live/20261018/lp_w4_*.jsonl.gz` (~46 MB).

## 3. Rewards cross-section (Q1) — LIQUIDITY REWARDS ONLY (discretionary incentive, not trading P&L)
Method (`05_reward_xsec.py`, `lp.py`): our hypothetical two-sided quote joins the touch (YES bid at best bid, NO bid at 1 − best ask), size
N = max(rewardsMinSize, capital / (bb + 1 − ba)) shares; our Q_min vs competitors' Q_min from the visible aggregated book (central = book as one
maker; conservative = Q1 + Q2). Daily reward = total_daily_rate × share, assuming the snapshot persists all day. PLAUSIBLE, not VERIFIED:
per-maker queues are invisible, the size-cutoff mid is undefined in the docs (three variants give the same answer: R1 pass 0.659–0.667 at
$2,500), the "required duration" is unstated, and no payout was observed (no wallet).

| Capital per market | Median central reward/day | Median yield (bp of capital/day) | Median central share | R1 pass (≥ $2/day and ≥ 5 bp/day) |
|---|---|---|---|---|
| $500 | $1.85 | 37 | 40% | 48% |
| $2,500 | $4.20 | 16.8 | 77% | 66% (population-weighted 45%) |
| $10,000 | $4.95 | 4.9 | 93% | 48% |
(snapshot s2, all strata; s0/s1 are within a few %.)

- Rewards **saturate**: most allocations are small (median $3/day) and the visible qualifying depth is thin, so a $2,500 quote already takes
  ~77% of the median pool and quadrupling size adds little. Per stratum at $2,500 (s0): A (active) median $5.8/day, 23 bp/day, share 57%;
  B (long tail) $0.99/day, 4 bp/day; C (largest pools, ~$500/day) median share only **1.8%** (these are contested), median $8.4/day.
- By category at $2,500 (s0): **weather** median $31/day (126 bp/day, share 95%: daily temperature buckets with $100+/day pools and almost
  no qualifying depth) is the outlier; politics $3.1 (12 bp), sports $2.7 (11 bp), culture/economics/tech ~$5 (20–26 bp).
- Persistence: Spearman of per-market central reward s0 → s2 (6 h) = 0.82; 61% of markets pass R1 in all three snapshots vs 66.5% in the first.
- **Single-snapshot selection is badly biased.** Greedy "top-k by reward at s0", re-scored at s2 (0 if unscorable or config gone):

| Account | Per market × k | In-sample s0 $/day | Same markets at s2 $/day | s2 yield bp/day |
|---|---|---|---|---|
| $5k | $500 × 10 | 1,552 | 657 | 1,314 |
| $5k | $2,500 × 2 | 2,148 | **0** (sports games over) | 0 |
| $25k | $500 × 50 | 3,746 | 2,354 | 942 |
| $25k | $2,500 × 10 | 6,610 | 758 | 303 |
| $100k | $500 × 200 | 7,828 | 5,771 | 577 |
| $100k | $2,500 × 40 | 9,589 | 2,445 | 244 |
  These are **gross rewards on paper before any fill, adverse selection, inventory or competitor reaction**; the markets that make up the
  top are exactly the thin ones (weather, culture, game-day sports) where section 5 shows fills are toxic. They are not a P&L estimate.
- Pre-registered checks: **R1 not triggered** (45% ≥ 10% pass at $2,500; 43–46% when restricted to R8-persistent markets).
  **R7 not triggered** (median central share of a $2,500 quote in the selected websocket markets: 50% from the 60 s REST books, 42–52% from
  the snapshots). **R8**: all 20 w4 markets kept their allocation from start (t1) to end (t2) of the window, but 5 of 20 changed rate within
  those 55 min; for w1–w3, 8 of 213 markets had lost their allocation by t1 (5.3 h after the window; no end-of-window pull exists).
- Maker rebates (separate programme): only filled maker volume earns them; in the sim the upper bound (every fill fee-paying) is $38 against
  $9.8k of filled notional at $500 (section 5). Makers pay no fee (VERIFIED, platform notes).

## 4. Websocket microstructure (task step 3) — 551 prints, 233 market-windows, 114 market-hours
- **Arrival rates are low.** 4.8 prints per market-hour overall; 63% of market-windows had **no print at all**. Among markets with prints,
  median 4.3 prints/h (IQR 2.3–9.4) and $55/h notional (IQR $21–$290). Median print $9, p90 $161. w4 alone: 2.5 prints per market-hour,
  40% of markets with none.
- 87.7% of prints execute at the touch, 0.7% through it. Only **25 of 483 (5.2%) touch prints consumed the whole displayed best level**.
- **Queue depletion is cancellation-driven.** 12,213 decreases of displayed size at the best level (9.3 M shares): prints at that level within
  ±1.5 s explain only **3.4%** of the volume. The best level vanished 2,826 times; only **75 (2.7%)** of those had a print there.
  At observed touch trade rates, trades alone would take a median 4.6 h to clear the displayed touch queue (only 104 of 466 market-sides
  had any touch volume at all).
- **Unconditional maker markouts** (whoever was the maker on each print): +0.41c/share at 60 s (90% CI 0.25–0.57c; spread capture +0.60c,
  adverse selection −0.20c), similar at 5 s / 300 s. But **notional-weighted** it is −0.13c/share (−28 bp of notional): the top decile of
  prints by notional marks out at −0.02c vs +0.46c for the rest. Small prints pay the spread; large ones are informed.
- **Why touching a price is not a fill (VERIFIED in this sample):** while our virtual order rested, **423 prints hit our exact price on our
  side; only 11 (2.6%) were larger than the queue ahead of us** (plus 39 trade-throughs). Joining the back of a 245–320-share median
  time-weighted touch queue means almost every
  touch print is absorbed by earlier orders; displayed size mostly disappears by cancellation, which does not advance a back-of-queue order
  (front-of-queue makers cancel too, but you cannot tell where in the FIFO the cancels were, and there is **no public order-level feed**:
  the `level` subscription option gives the same aggregated levels, and `price_change.hash` cannot follow an order). Under the conservative
  rule **78% of our fills are trade-throughs**, i.e. we get filled mostly when the price moves through our level, the adverse case. Treating
  every touch print as a fill (or using last-trade prices) would overstate same-price fills ~40× (423 vs 11), total fill events ~9×,
  and would pick the benign fills.

## 5. Simulated passive strategy (Q2, Q3) — `08_sim.py`, `09_report.py`
Pre-registered sketch: every 60 s cancel and re-post at the touch (join, never improve), only if mid in [0.10, 0.90] and both quotes within
rewardsMaxSpread; inventory cap 2N; markouts on the YES mid. 218 quoted market-windows, 93.8 market-hours. All $ over the whole sample.

| $/market | Fill rule | Fills (mkts) | Spread capture | Adverse sel. 60 s | Inventory drift | **Trading MTM** (90% CI) | Liquidation (½ spread + taker fee) | **Rewards** central / conservative | Rebate UB | **net_r3 = MTM + central rewards** (90% CI) |
|---|---|---|---|---|---|---|---|---|---|---|
| 500 | conservative (PRIMARY) | 50 (29) | +2.6 | −148.2 | −54.2 | **−199.8** (−358, −62) | 319.3 | 81.4 / 48.4 | 38.2 | **−118.4** (−274, +12) |
| 2,500 | conservative | 50 (29) | +76.5 | −554.6 | −322.7 | **−800.8** (−1,415, −261) | 1,521.6 | 140.0 / 95.4 | 174.1 | **−660.9** (−1,256, −120) |
| 10,000 | conservative | 50 (29) | +298.3 | −2,216.5 | −1,283.9 | **−3,202.1** (−5,667, −1,012) | 6,073.3 | 214.0 / 153.0 | 695.2 | **−2,988.1** (−5,511, −860) |
| 500 | optimistic (cancels advance us pro rata) | 78 | −12.6 | −166.3 | −17.4 | −196.2 | 350.1 | 81.4 | 47.6 | −114.8 (−263, +13) |
| 500 | keep_queue (added) | 61 | +5.2 | −157.9 | −99.3 | −252.1 | 346.0 | 81.4 | 42.7 | −170.7 (−398, +9) |
| 500 | reactive (added: pull 1 s after our level empties) | 38 | +22.5 | −68.6 | −85.6 | −131.7 | 294.3 | 81.4* | 28.3 | −50.3 (−170, +51) |
| 500 | tt_capped (added post hoc: trade-through fills ≤ print size) | 78 | −8.1 | −51.4 | −36.1 | −95.5 | 150.1 | 81.4 | 15.7 | −14.1 (−83, +45) |
(* reactive rewards are slightly overstated: they are credited for the whole minute after a pull. CIs: market-block bootstrap.)

- Scale: at $500/market, trading MTM ≈ −$2.1 per market-hour vs central rewards ≈ +$0.87 per market-hour (gross reward yield ≈ 4%/day of
  quoted capital in this active sample, but the trading leg loses ≈ 2.5× that). Trading losses scale ~linearly with size, rewards
  sub-linearly ($81 → $140 → $214), so **bigger quotes are strictly worse**.
- By category ($500, conservative): sports −$110.6 MTM vs +$15.7 rewards (21 of 50 fills); weather −$41.7 vs +$29.3; politics −$4.3 vs
  +$6.0 (5 fills in 26.6 market-hours: deep queues, almost never filled, small reward share); culture +$15.0 vs +$19.5 (7 fills; small n).
  By window: net_r3 w1 −54, w2 −92, w3 +20.5, w4 (the fresh 55-min window) +7.0 on 6 fills, all negative after liquidation.
- **R2 (adverse selection): REJECTED.** 47 conservative fills with a 60 s horizon in 27 markets: markout **−0.63c/share (90% CI −1.44, −0.10)**
  = spread capture +0.05c + adverse selection −0.67c. Back-of-queue passive fills lose money at 60 s.
- **R3 (combined): FAILED** for every size and every fill rule: net_r3 < 0 and the CI lower bound < 0 (upper bound > 0 only at $500).
- **R4**: 50 conservative fills ≥ 30, so the result counts by the pre-registered rule, though it rests on 27 markets and < 2 hours per window.
- **R5**: top 5-minute window = 45% / 36% / 36% of |fill MTM| ($500 / $2,500 / $10,000); top market ≤ ~20% of |net|: below the 50% flag, but
  close at $500.
- **R6**: not reached (net is negative even with rewards). The only near-zero variants are post-hoc and still negative after liquidation.

## 6. Capacity ($5k / $25k / $100k)
- **Demonstrated net capacity: none** (no configuration with positive net P&L).
- Rewards-only on paper (section 3, re-scored 6 h later): $5k → ~$650/day if spread over 10 × $500 thin markets; $25k → ~$2.4k/day
  (50 × $500); $100k → ~$5.8k/day (200 × $500). These numbers are mostly weather / culture / long-tail pools with near-empty books; they
  assume no competitor reaction, persistent allocations (20% of rates change within 7 h) and, above all, ignore the fills, which section 5
  shows cost more than the rewards in the markets we could test. Concentrating size ($2,500–$10,000 per market) is worse on both counts:
  reward share saturates and losses scale with size. Practical retail capacity, if a positive variant were ever found, would be
  breadth-limited (many $250–$500 quotes, each ≥ rewardsMinSize) and operations-limited (hundreds of quotes requoted every few seconds).

## 7. Verdict and strategy specification
**Verdict: NO DEMONSTRATED EDGE.** Liquidity rewards are real money on paper (median 17 bp/day for a $2,500 quote, far above the R1 bar), but
in the captured sample the passive fills that come with them are adversely selected (−0.63c/share at 60 s) and inventory drifts against the
quoter, so net P&L (MTM + central rewards) is negative at every size under every fill rule tested. Very short sample (114 market-hours,
50 primary fills): this rejects the naive "join the touch and farm rewards" sketch, it does not prove that no LP strategy works.
- **Signal**: per-market reward yield = total_daily_rate × modelled Q_min share / quoted capital from the live book (central bound), with mid
  in [0.10, 0.90], touch within rewardsMaxSpread, allocation present in the latest `/rewards/markets/current` pull.
- **Entry**: post-only GTC bid at the best bid and NO bid at 1 − best ask (= YES ask), size max(rewardsMinSize, capital/(bb + 1 − ba)).
- **Exit**: cancel/re-post every 60 s (tested), or sooner on touch changes (reactive variant); inventory cap 2N, then quote only the reducing
  side; flatten (sell or merge YES+NO) before catalysts / game start / resolution and when the allocation is withdrawn.
- **Holding period**: quotes seconds to a minute; inventory minutes to hours; rewards sampled each minute, paid daily (≥ $1).
- **Data requirements**: market websocket (book, price_change, last_trade_price), 60 s REST books, reward configs at ≤ 15 min cadence,
  Gamma fee/reward params; for validation, own order fills and `/order-scoring` (authenticated, out of scope here).
- **Why it might persist**: the platform pays ~$180k/day to buy liquidity; many pools are small, numerous and short-lived (game-day,
  daily weather), which is operationally expensive for professional MMs to cover, and the rewards compensate exactly the risk they avoid.
- **Main reason it fails**: adverse selection plus queue position. A retail order joining the back of the queue is filled mainly when the
  price moves through it (78% of fills are trade-throughs); the subsidy (≈ $0.9 per market-hour at $500) is smaller than the losses
  (≈ $2.1 per market-hour). Secondary: discretionary allocations that change daily, dilution once others join, invisible queue position.

## 8. Forward data collection needed for a proper LP backtest
1. **Market websocket, continuous** for a fixed panel of ~100 reward markets stratified by category × pool size × competitiveness, plus
   rotating short-lived markets (game-day sports, daily weather), all events incl. `best_bid_ask`, `tick_size_change`, `market_resolved`,
   with local receive time; auto-reconnect and gap markers; a REST `/books` snapshot per market every 60 s to re-anchor and check gaps.
2. **Reward configs** (`/rewards/markets/current` and `/multi`) every 15 min and at each 00:00 UTC epoch; Gamma `feeSchedule`,
   `rewardsMinSize`, `rewardsMaxSpread`, `secondsDelay`, `gameStartTime`, `endDate` hourly; the public per-market raw-rewards endpoint
   (docs `get-raw-rewards-for-a-specific-market`) daily, to calibrate modelled shares against actual distributions where it is public.
3. **Fills with counterparties**: data-api trades and on-chain `OrderFilled` events (maker/taker addresses, order hashes) to measure maker
   concentration, who gets filled at the touch, and how often front-of-queue makers cancel; this is the only public proxy for queue position.
4. **A small authenticated pilot** (outside this read-only project): real post-only orders of the minimum size, logging order ids, `/order-scoring`
   status, actual fills vs the conservative model, and the next-day reward payout. Without it, fill and reward models stay PLAUSIBLE.
5. **Storage / cadence**: the captures ran at ~3,900 WS frames per market-hour ≈ 0.4 MB/market-hour gzipped JSONL, so 100 markets ≈ 1 GB/day
   ≈ 30 GB/month raw; convert daily to parquet (book deltas, TOB, trades) and keep raw for 7 days. REST books at 60 s ≈ 50 MB/day per 100 markets.
6. **Sample needed**: ≥ 4 weeks covering resolutions, news jumps, game starts and reward-epoch changes; ≥ 1,000 conservative fills in ≥ 100
   markets; inference by market-day block bootstrap; pre-register the same R1–R8.

## 9. Deviations from the pre-registration, fixes and caveats
- Windows w1–w3 were cut to 21–31 min by a session interruption (not a script error); a fresh 55-min w4 was added 5.3 h later by the same
  selection rule. Snapshot s2 and reward pulls t1/t2 were added. Rules in section 0 are unchanged.
- Sensitivity rules `keep_queue` and `reactive` were added after the pre-registration, and `tt_capped` after the w1–w3 results were seen.
  They are labelled; none changes the verdict.
- R8 for w1–w3 is checked against t1 (5.3 h after the window), which is stricter than "at the end of the window".
- **Bug fixed (2026-10-18):** w4 shares 14 markets with w1–w3. Keying fills and markouts by market alone double-counted their fills in the
  pooled run; now keyed by (window, market) in 07/08/09. The w1–w3-only results were unaffected (those windows are disjoint).
- Liquidation charges half the spread plus the taker fee on all end inventory, once per window. That is pessimistic for a strategy that
  keeps running, but inventory MTM (also negative) is shown separately. The rebate is an upper bound.
- Rewards use the visible aggregated book; hidden per-maker structure, the unknown sampling minute and the unknown "required duration"
  make the share PLAUSIBLE at best. Actual payouts were not observed.
