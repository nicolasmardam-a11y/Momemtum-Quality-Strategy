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
