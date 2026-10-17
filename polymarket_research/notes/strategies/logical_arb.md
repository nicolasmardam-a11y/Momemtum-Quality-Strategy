# Family C: cross-market logical arbitrage (as of 2026-10-17)

Status: IN PROGRESS. The pre-registration section below was written before any order-book
data was pulled or any edge was computed (file created 2026-10-17 ~15:10 UTC).

## 0. Pre-registration (written before computing results)

### Relations tested
For contracts A, B with A => B per the question text (A can only be YES if B is YES):
buy YES_B + NO_A. Payoff in every state is >= 1 (1 if A&B, 2 if B and not A, 1 if neither).
For mutually exclusive A, B in separate markets: buy NO_A + NO_B (payoff >= 1).
For an exhaustive set of separate (non neg-risk) markets: buy every YES (payoff = 1).
For duplicates A == B: buy YES_A + NO_B (payoff = 1 if both resolve identically).

### Cost model (fixed in advance)
- Executable asks only, walking the full visible ask ladder of both legs jointly
  (CLOB `/books`, best-first). No midpoints, no last trades, no `outcomePrices`.
- Taker fee on every leg: `shares * rate * p * (1-p)` with `rate` from that market's Gamma
  `feeSchedule` (fallback: `pmr.fees` category table); exponent from `feeSchedule`.
- No maker legs, no rebates (Taker Rebate Program or maker rebates) counted in the base case;
  rebates are mentioned as an upside only.
- Minimum order: each leg >= `orderMinSize` shares and >= $1 notional.
- Gas: Polymarket relayer is gasless for users (to be confirmed in mechanics notes); assume $0
  but treat as UNSUPPORTED unless verified.

### Opportunity definition
An *opportunity* in a snapshot = a candidate relation whose depth-walked bundle has
marginal cost (sum of leg prices + per-share fees) < 1 for at least the minimum size.
Counted per distinct relation (pair of conditionIds); a family of relations within one Gamma
event / one underlying is also reported as one *distinct event*.

### Rejection criteria (pre-registered)
- **R1 (no edge):** if no relation classified TRUE DOMINANCE or NEAR-DOMINANCE has net
  (after-fee) edge > 0 at executable asks in >= 2 consecutive snapshots >= 4 min apart,
  verdict = "no demonstrated edge".
- **R2 (persistence):** an opportunity seen in only one snapshot is reported but not counted
  toward the edge (stale data / already taken).
- **R3 (rules):** any relation whose written rules (description, resolution source, deadline
  + timezone, early-resolution, 50-50, ties/postponements) do not guarantee the implication
  in every state is not an arbitrage; it is NEAR-DOMINANCE (fails only in a stated edge case)
  or CORRELATED BET. Only TRUE DOMINANCE counts toward the arbitrage verdict; NEAR is reported
  separately with the failure state's rough probability.
- **R4 (economic size):** reject as not worthwhile for a retail trader if, across all
  persistent TRUE/NEAR-DOMINANCE opportunities, the total depth-limited net profit available
  per hour of observation is < $25, OR the capital-weighted net return on committed capital
  annualised (simple, to the later resolution date) is < 10%/yr (T-bill-like hurdle plus a
  margin for resolution/oracle risk).
- **R5 (margin of safety):** opportunities with net edge < 0.5% of committed capital
  (< $0.005 per $1 payoff) are counted as "sub-threshold": they are within tick rounding,
  fee-rounding (5 dp) and book-staleness noise and are not counted toward a positive verdict.

Verdict mapping: R1 fails -> `no_demonstrated_edge`; persistent TRUE dominance but R4/R5 fail
-> `marginal`; persistent TRUE dominance passing R4 and R5 -> `promising_test_further`
(never "risk-free": oracle, smart-contract, and dispute risk always remain).
