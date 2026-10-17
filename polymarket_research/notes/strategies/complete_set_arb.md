# Family B: within-market and complete-set arbitrage (live scan, 2026-10-17)

Status: IN PROGRESS. Section 1 (pre-registration) was written at ~15:15 UTC on 2026-10-17,
before any opportunity statistic was computed. Later sections are filled in after collection.

## 1. Pre-registration (written before results)

### 1.1 Opportunity definitions (all prices are executable CLOB book levels, never last trade or mid)

Notation: for a token, `askY(q)`/`bidY(q)` = walking the YES token's asks/bids for q shares;
fee per taker fill level = `size × rate × (p(1−p))^exponent` with `rate`/`exponent` from the
market's Gamma `feeSchedule` (fallback `pmr.fees` category table), charged in pUSD on top of a
buy and deducted from a sell (docs /trading/place-orders, /trading/fees). "Set size $X" = X complete sets (each worth $1 at
merge/convert/resolution), so $100 = 100 sets.

- **(a) binary buy-both + merge**: cost(Q) = Σ walk asks of both outcome tokens + fees; profit = Q − cost.
- **(b) binary split + sell-both**: profit = Σ walk bids of both tokens − fees − Q.
- **(c) neg-risk buy-all-YES, hold to resolution**: profit = Q − Σ_i walk askY_i − fees, over every
  tradable member of a negRiskMarketID group. Counted only if the outcome set is exhaustive:
  every non-tradable member is closed and already resolved NO, there are no unnamed placeholder
  members (active=false) and, for augmented neg-risk, the `negRiskOther` market is also bought.
- **(d) neg-risk split + convert + sell-all-YES**: split Q in one member, convert the NO into YES of
  every other member, sell YES in every member with bids. profit = Σ_i walk bidY_i(min(Q, depth_i)) − fees − Q.
- **(e) neg-risk buy-all-NO + convert**: buy Q NO in each of k tradable members, convert → (k−1)·Q pUSD
  (+ YES of the remaining members, valued at 0). profit = (k−1)Q − Σ walk askN_i − fees.
- Variants (c') split-all + sell-all-NO + hold YES set, and (e)/(d) mixtures are reported but not double
  counted when YES-bid and NO-ask books are the same liquidity (CLOB mirror; to be checked).
- Profit is reported at Q = 100 / 1,000 / 10,000 sets (NaN when the book cannot fill Q on every leg),
  and at the profit-maximising Q*.

### 1.2 Pre-registered artefact flags (a candidate carrying any flag is reported but not counted as capturable)

1. Any leg in a market with `acceptingOrders=false`, `closed=true`, `active=false`, or `enableOrderBook=false`.
2. Any leg's book crossed in itself (best bid ≥ best ask on one token) — matching-engine event / stale book.
3. Q* < the market's `min_order_size` (5 shares on almost all markets) on any leg, or max net profit < $0.50.
4. Any leg with `secondsDelay > 0` (sports delay; legging risk) or game already started (`gameStartTime` in the past) — flagged "legging risk", counted separately.
5. Any leg with `umaResolutionStatus` = proposed/disputed (prices pinned near 0/1 while a result is pending) — flagged "resolution pending".
6. Book timestamp older than 5 minutes on any leg at fetch time — flagged "possibly stale".
7. (c) only: non-exhaustive outcome set as defined above → excluded from (c) entirely.

### 1.3 Persistence rule

A candidate is identified by (negRiskMarketID or conditionId, type). It counts as **capturable by a
REST-polling retail trader** only if it is still present (net profit > 0 at ≥ min size) on at least one
re-fetch ≥ 30 s after first observation. Seen-once candidates are reported as "transient" (could be stale
data or already gone; capturable only by faster bots, if at all).

### 1.4 Rejection criteria for the family (applied to the full ~60–90 minute window)

- **R1 (no persistent edge)**: fewer than 3 distinct (event, type) candidates that are flag-free, net of fees,
  ≥ $1 net profit at an executable size, and persistent per 1.3 → verdict `no_demonstrated_edge`.
- **R2 (economically trivial)**: if candidates exist but the projected net profit for a $5k account is
  < $5/day (≈ 36%/yr would need ≥ $5/day on $5k; we require at least $5/day) after fees and an allowance for
  gas, or the annualised return on locked capital for hold-to-resolution (c) trades is < 10%/yr → `marginal` at best.
- **R3 (hold-to-resolution only)**: if every surviving candidate is type (c) (capital locked to resolution,
  exhaustiveness/resolution risk), the family is at best `marginal` regardless of R2.
- **R4 (artefacts)**: if > 80% of raw candidates carry an artefact flag or are transient, report that the raw
  signal is dominated by artefacts.
- Promotion to `promising_test_further` requires R1–R3 all passed.

### 1.5 Known limitations accepted in advance

- REST snapshots every ~5 min with 30–60 s rescans cannot observe sub-second opportunities; a measured zero is
  "none visible to a REST poller", not "none exist".
- Fills are simulated against displayed depth; queue position, hidden latency and other takers are not modelled,
  so all profits are upper bounds.
- Taker Rebate Program rebates (3%+ of fees at Bronze) are ignored (conservative).

<!-- RESULTS-START -->
