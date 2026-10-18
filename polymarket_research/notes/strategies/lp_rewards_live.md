# Family D — selective liquidity provision (live part): rewards, queue, markouts

Status: IN PROGRESS. As-of 2026-10-17. Author: research agent (read-only, public data only; no orders, no wallet, no auth).

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
