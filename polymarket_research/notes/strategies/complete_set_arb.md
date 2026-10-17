# Family B: within-market and complete-set arbitrage (live scan, 2026-10-17)

Status: COMPLETE (2026-10-17 ~23:00 UTC). Section 1 (pre-registration) was written at ~15:15 UTC on 2026-10-17,
before any opportunity statistic was computed, and has not been changed. Sections 2-10 hold the results of two
collection windows (15:17-16:21 UTC and 21:28-22:47 UTC).

**Verdict: no demonstrated edge.** No candidate passed the pre-registered filters in either window (R1 fails).
The one candidate that passes when the stale-book flag is relaxed is a hold-to-resolution (c) basket returning
under ~1%/yr (fails R2 and R3).

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

## 2. What was collected (VERIFIED: the raw responses are under data/raw/{gamma,clob,clob_ws,polygon}/live/20261017/)

| Item | Window 1 (15:17-16:21 UTC) | Window 2 (21:28-22:47 UTC) |
|---|---|---|
| Gamma universe (events keyset, closed=false, active=true), refreshed every 15 min | 421-425k markets | 415-417k markets |
| Full neg-risk scans (YES and NO books of every tradable member), every ~5 min | 13 scans, ~10,000 groups / ~212k books each | 16 scans, ~9,500 groups / ~204k books each |
| Full binary scans (both outcome tokens), every 2nd cycle | 7 scans x ~180k markets | 8 scans x ~167k markets |
| Candidate rescans (every 40 s until the next full scan) | 52 | 67 |
| Websocket (market channel, every update) on the ~600 near-miss groups (top-of-book within 2% of break-even) | runs 1-3, ~55 min, 656-881 groups / 4.8-7.9k YES assets | runs 4-6, 60 min, 607-633 groups / 5.1-5.5k YES assets |

In total: 29 full neg-risk scans (252,007 group-scans with at least 2 tradable members), 2,594,628 binary market-scans,
~115 min of websocket data, and 10 h of on-chain converts (blocks 95,687,670-95,711,670).

## 3. Results by opportunity type

### 3.1 Binary (a) buy-both + merge and (b) split + sell-both: zero, as expected from the book structure

- 0 of 2,594,628 binary market-scans had askYES + askNO < 1 or bidYES + bidNO > 1 at any size, before or after fees.
  The best (a) edge seen was -0.001, meaning askYES + askNO = 1.001: one tick of spread. **VERIFIED**.
- The reason is structural. YES and NO trade in one book: the YES bid at p is the NO ask at 1-p, and the engine matches
  BUY YES with BUY NO as a mint (and SELL with SELL as a merge). Top-of-book mirror (YES bid = 1 - NO ask) held on 99.989% of
  3.0M neg-risk member observations. Full-depth ladders matched on 98.8%. The small remainder is consistent with the
  book changing between the two reads; it was not studied further. **VERIFIED** (see notes/platform/mechanics.md §0, §2a-b).
- Crossed books on binary markets in REST snapshots: 0.

### 3.2 Neg-risk (d) split + sell-all-YES, and (e) buy-all-NO + convert (the only trades that recycle capital at once)

Because the books mirror each other, (d) and (e) are the same trade. The scanner's d and e numbers were identical in every row.

- Net of each leg's feeSchedule taker fee, groups with a positive top-of-book (d)/(e) edge per full scan: **0 or 1 out of
  about 9,500-10,000** (8 group-scans out of 252,007 in total). **VERIFIED**.
- Over both windows there were 5 distinct (d)/(e) candidates. None passed the pre-registered filters:
  - 3 were in-play soccer or weather markets (flags `game_started`, `seconds_delay`). They were seen once, gone by the next
    rescan 40-120 s later, and their maximum profit was $0.26-0.42 at Q* = 37-83 sets.
  - "#1 Spotify song in the US this week? (October 23)" stayed positive for 55 min, but only for **1 share** (edge 1.04%, $0.01).
    That is below the 5-share minimum, so it is unexecutable.
  - "Lowest temperature in Madrid on October 17?" was 2 shares and `game_started`.
- Distribution of the (d) top-of-book net edge over all group-scans: median -0.25, 99th percentile -0.00105,
  99.9th percentile -0.00071 (window 1) and -0.00105 (window 2). The book sits just outside the no-arbitrage band, by about one
  tick plus fees.

### 3.3 Neg-risk (c) buy-all-YES and hold to resolution

- Raw positive (c) observations are dominated by **non-exhaustive outcome sets**: 5,290 of 5,768 raw positive candidate
  observations (91.7%), in 262 distinct groups. Most are augmented events whose placeholders cannot be traded, or events with
  an untradable or already-resolved member. These were excluded under rule 7. A scanner that does not apply this check
  reports hundreds of false "sum of YES < 1" signals. **VERIFIED**.
- The scanner's exhaustiveness test matched the on-chain question count for every group checked.
  `NegRiskAdapter.getQuestionCount` (eth_call) equalled the Gamma member count for all 13 exhaustive (c) candidate groups,
  all 263 non-exhaustive ones and a random 120 exhaustive groups. **VERIFIED**.
- Exhaustive (c) candidates that persisted (≥ 30 s), with annualised return = max profit / basket cost / years to endDate:

| Event | max net profit | Q* (sets) | top edge | endDate | annualised | flags |
|---|---|---|---|---|---|---|
| World Cup 2030: Location of Final (augmented; includes "Other / Unconfirmed by 2028") | $8.72 | 773 | 2.17% | none (≤ 2028 implied) | ≈0.6%/yr if it resolves in 2028 | stale_gt5min |
| OpenAI IPO Closing Market Cap | $0.91 | 230 | 1.72% | 2028-01-01 | 0.33%/yr | none |
| Who wins the Senate pending Hormuz Agreement by Oct 23? | $0.17 | 423 | 0.12% | 2026-11-04 | 0.9%/yr | none |
| Bitcoin vs. Gold vs. S&P 500 in 2026 | $0.13 | 59 | 0.22% | 2027-01-01 | 1.1%/yr | stale_gt5min |
| Mastercard Q3 cross-border growth | $0.11 | 20 | 0.54% | 2026-10-29 | 18%/yr on $20 | none |
| SB Energy IPO, Waymo cities, GitHub incident, Colombia CB, NJ turnout | $0.02-0.10 each | 0.3-82 | — | Oct 2026-Jan 2027 | — | Q* < 5 for three of them |

- The World Cup basket persisted for 7.5 h across both windows: it was positive in all 119 observations. It is flagged
  `stale_gt5min` because its book last changed more than 5 minutes before the fetch. That flag was pre-registered as
  "possibly stale". The CLOB `timestamp` turned out to be the book's last-change time, while the REST data itself is fetched
  fresh. So the opportunity is real but nobody touches it, because the money is locked for years.
- The World Cup basket is also an **augmented** event. New questions can still be added to it, and if a newly added question
  wins, "Other" resolves NO and the 5-leg basket pays 0. This risk is **PLAUSIBLE**. On-chain `getQuestionCount` = 5 today, so
  there are no placeholders now, but the operator can add questions.
- Websocket-only near-miss: "How many cities will Waymo operate in by December 31?" was positive for 562 s, at $4.88 for
  124 sets (edge 5.7%). REST polling saw only $0.06. It was a one-off, and the money would be held until 2027-01-01.

### 3.4 The fee band: gross violations are common, and fees remove them

Top-of-book (d)/(e) edge recomputed with taker fees scaled by f (`fee_sensitivity.py`; Taker Rebate Program rebates are paid daily
in arrears, so this is a profitability band, not an execution price):

| Fee level | distinct groups ever positive (both windows) | not in-play, no other flag | positive groups per scan | median edge |
|---|---|---|---|---|
| full fee (pre-registered) | 4 | 1 (Spotify, 1 share) | 0.28 | 0.56% |
| 3% rebate (Bronze) | 4 | 1 | 0.28 | 0.58% |
| 18% rebate | 7 | 3 | 0.45 | 0.09% |
| 50% rebate (Obsidian, $10M 30-day weighted volume) | 30 | 26 | 5.3 | 0.35% |
| no fee (gross / maker) | 103 | 94 | 35.2 | 0.50% |

**VERIFIED** (arithmetic on recorded book tops). Before fees, sum(bidYES) > 1 occurs in about 35 groups at any moment, by a median of
0.5%. After taker fees, the median net edge of those same groups is -1.56%. The violations persist because takers cannot profit
from them. They are the edge of a fee-wide no-arbitrage band, not free money.

### 3.5 Persistence and half-life

- REST: of the full-scan candidates with profit > $0.01, 89% (window 1, n = 37) and 97% (window 2, n = 69) were still positive at the
  next 40 s rescan. These are almost all the standing (c) baskets above. They do not decay, because nobody takes them.
- Every (d)/(e) candidate with real size was in-play sports and had disappeared by the next 40-120 s rescan.
- Websocket bursts (147 after merging flickers less than 2 s apart):

| Type | in-play | bursts | groups | median duration | p90 | ≥ $0.50 profit | crossed book |
|---|---|---|---|---|---|---|---|
| (c) | no | 37 | 9 | 28 s | 572 s | 9 | 0 |
| (c) | yes | 34 | 6 | 1.7 s | 10.8 s | 17 | 11 |
| (d)/(e) | no | 20 | 2 | 2.0 s | 33 s | 0 | 0 |
| (d)/(e) | yes | 56 | 16 | 2.2 s | 10.4 s | 22 | 16 |

  The in-play episodes last about 2 s, a third of them involve a crossed book, and they happen while the 1-3 s sports taker delay
  is active. In one in-play match (Boyacá Chicó vs Atlético Nacional) the (d) edge flickered 208 times with a median life of 54 ms
  and at most $0.008. **VERIFIED**.

### 3.6 Delayed-execution replay of the websocket stream (`replay_ws.py`; optimistic: no queue, no competing takers)

121 sized (≥ 5 shares) episode starts, 7 runs. One order per leg at the start-time best price. A leg fills only if the book still
offers that price after the stated latency (plus the market's `secondsDelay` in the "plus delay" scenarios). Legs that fill
when others do not are unwound at once at the opposite best price, paying taker fees both ways.

| Scenario | all legs filled | legged | captured profit | legging cost | net |
|---|---|---|---|---|---|
| 0.25 s, no sports delay | 64.5% | 34.7% | $47.63 | $61.56 | **-$13.93** |
| 0.25 s + secondsDelay | 48.8% | 47.1% | $41.83 | $77.17 | **-$35.34** |
| 1 s + secondsDelay | 38.8% | 60.3% | $39.43 | $89.53 | **-$50.10** |

- In the 0.25 s + delay scenario, the sports episodes (90 starts) lost $65.83 net. The non-sports episodes (31) made +$30.49, but
  +$32.08 of that is the same World Cup basket re-detected at the start of each of the 7 runs. It is one standing hold-to-resolution
  basket, not 7 trades. Without it, non-sports nets about -$1.6. **VERIFIED** (simulation on recorded data; the assumptions are
  optimistic, so real results would be worse).

### 3.7 Who already does "buy all NO + convert" on-chain (competition check)

- The NegRiskCtfCollateralAdapter's own `PositionsConverted(address,bytes32,uint256,uint256,uint256)` event names the user's wallet.
  The legacy adapter's event names the collateral adapter instead, so the earlier `onchain_converts.py` could not attribute converts.
  In 10 h there were 3,471 converts by 173 wallets. 361 of them were all-NO (k = n) converts, by **38 wallets** in 150 events,
  covering 36,398 sets and releasing 88,386 pUSD. The median size was 11 sets, and n = 3 (3-way soccer) in 98.5% of the
  converts that could be matched to trades. **VERIFIED** (on-chain logs).
- For the 6 largest all-NO converters, each convert was matched to the wallet's NO buys in the same event during the previous 60 min
  (Data API v2 activity):
  - The largest wallet (23.5k of the matched sets) had a **set-weighted gross edge of 1.84%/set**, and **0%** of its fills in those
    windows appear in its `taker_only=true` trades. That pattern fits a market maker filling passively on all three outcomes and
    converting the inventory. If it had paid taker fees, its edge would have been negative: about -$197 instead of +$432 over 6.7 h.
  - The second wallet appears 100% taker, at 1.1% gross edge per set over 2.5k sets. Taker fees would have turned its +$29 into -$19
    over 8.7 h.
  - **PLAUSIBLE**: the maker/taker split comes from the Data API `taker_only` filter, which has no explicit role field, and fees per fill
    are not in the rows.
- Reading: the "buy all NO + convert" volume that exists on-chain fits makers recycling inventory inside the fee band. It does not
  fit takers lifting arbitrage. That is a market-making strategy, with its own legging and adverse-selection risk. It is not the
  taker arbitrage tested here.

## 4. Pre-registered rejection criteria (section 1.4), applied to both windows

| Criterion | Result | Outcome |
|---|---|---|
| R1: ≥ 3 distinct flag-free, net-of-fee, ≥ $1, persistent candidates | **0** (strict), **1** with the stale flag relaxed (World Cup 2030 (c)) | **FAIL → no_demonstrated_edge** |
| R2: ≥ $5/day on $5k and ≥ 10%/yr on locked capital for (c) | The relaxed survivor is about $8.7 once, at about 0.6%/yr | FAIL |
| R3: every survivor is type (c) | yes (the only relaxed survivor is (c)) | at best marginal |
| R4: > 80% of raw candidates are artefacts or transient | 91.7% of raw positive observations are non-exhaustive (c). Of the 24 distinct valid candidates, 16 (67%) are flagged or transient | **raw signal dominated by artefacts** |

## 5. Exact sequences, collateral, legging, gas and recycling (for any future candidate)

**(e) buy all NO + convert (= (d)).** This is the only form that recycles capital at once.
1. Send k separate taker orders, one per tradable member: BUY NO q at askN_i (FOK or FAK). There is no atomic multi-leg order.
   - Collateral: Σ askN_i·q plus fees. For a 3-way event that is about (2 - edge)·q.
   - Minimum: 5 shares per leg, on the price tick grid.
2. Wait until all k fills settle on-chain: median 2.3 s, p90 2.9 s (mechanics §3.6).
3. Call `NegRiskCtfCollateralAdapter.convertPositions(marketId, indexSet with k bits, q)`. It returns (k-1)·q pUSD in the same
   block, plus YES on any members not in the set.
   - feeBips was 0 on the 60 markets sampled.
   - Gas: about 0.58M for 3 questions and about 2M for 9-15 questions, i.e. $0.02-0.50 at about 390 gwei and POL $0.093. It is
     gasless through the relayer for deposit/Safe wallets (mechanics §1.4).
   - Capital comes back about 5-10 s after the last fill, so turnover is limited by opportunity count, not capital.
4. Leg risk: if j < k legs fill, you hold a directional NO basket. Unwinding it costs the spread plus two taker fees. In the replay,
   that unwind cost alone exceeded the captured edge, and sports markets add a 1-3 s delay during which an order cannot be cancelled.

**(c) buy all YES, hold.**
- Send n taker BUY YES orders. The set must be the full on-chain question set (`getQuestionCount`), including Other in augmented events.
- Collateral is Σ askY_i·q, locked until resolution. The v1 adapter has no horizontal merge.
- Redemption is automatic (AutoRedeemer, about 12 s after resolution) and gasless.
- Risks: augmented events can add questions; 50-50 or disputed resolutions; capital is locked from months to years.

**(a)/(b)** would merge or split through `CtfCollateralAdapter` and recycle instantly, but they never occur in the visible book.

## 6. Capacity ($ per day, net of fees, at observed frequency)

| Account | Demonstrated (pre-registered) | Optimistic upper bound |
|---|---|---|
| $5k | **$0/day** | ≤ $0.15/day: capital-limited, since the (c) baskets return ≤ 1.1%/yr on locked capital |
| $25k | **$0/day** | ≤ $0.75/day |
| $100k | **$0/day** | ≤ $3/day. The opportunity limit is about $5/day (REST) to $20/day (websocket) of new (c) edge |

How the upper bound was built:
- **Assumption:** you take, once, every new flag-free persistent (c) basket that appeared between the windows (OpenAI IPO, Hormuz,
  SB Energy, Waymo, GitHub). Together they are about $1.3 by REST, or about $6 if the websocket-only Waymo burst is included,
  over about 6.5 h of elapsed time.
- **Cost:** those baskets tie up about $800 of capital until resolution (2-15 months), at annualised returns below 1.1% for every
  basket worth more than $0.11. That is about $3k/day of newly locked capital if the arrival rate held, so a $5k account is fully
  locked within about 2 days. The binding limit is the return on locked capital, which gives the bounds in the table.
- **(e) under realistic latency:** the in-play sports episodes are net negative in the replay. They also need a co-located bot, so they
  add nothing to the upper bound.
- **With rebates:** even at the top 50% taker-rebate tier, about 5 groups per scan clear the fee band, by a median of 0.35% on about
  11 shares. That is roughly $0.04 per opportunity, before the legging losses above.

## 7. Strategy card

- **Signal**:
  - (e)/(d): Σ_i bidYES_i (= Σ (1 - askNO_i)) minus Σ taker fees > 1 across every tradable member of a negRiskMarketID group.
  - (c): 1 minus Σ askYES_i minus fees > 0 on an exhaustive on-chain question set.
  - (a)/(b): binary sums. They never trigger.
- **Entry rule**:
  - On a full-group book snapshot (REST or websocket), enter when the depth-walked net profit is ≥ $1 at Q* ≥ 5 shares on every leg.
  - All members must be accepting orders, with no crossed book, no in-play or `secondsDelay`, and no proposed or disputed resolution.
  - Send all legs at once as FOK at the observed prices.
- **Exit rule**:
  - (e): convert as soon as all fills settle; the trade is finished then.
  - (c): hold to resolution and auto-redeem.
  - Partial fill: unwind the filled legs at once as a taker, or hold them as a directional position.
- **Data requirements**:
  - Full Gamma universe (about 415-425k markets) for neg-risk membership, Other, placeholders and feeSchedule.
  - Books for about 205k tokens every cycle, or a websocket on the near-miss set.
  - `getQuestionCount` for exhaustiveness.
  - About 75-80 s per full REST pass at about 27 req/s.
- **Holding period**: (e) about 5-10 s; (c) until resolution (weeks to years for the candidates seen).
- **Why it might persist**:
  - The taker fee `rate·p(1-p)` on every leg creates a no-arbitrage band of about 1-3% for 3-10-leg groups. Violations inside the band
    are common (about 35 groups at any time) and cannot be taken profitably by takers.
  - Standing (c) baskets persist because they lock capital for years at under 1%/yr.
- **Main reason it fails**:
  - Net of taker fees, there is almost nothing executable: 0 surviving candidates in about 2.5 h of scans across two windows.
  - What does appear is either an in-play sports flicker of about 2 s, where legging risk and the 1-3 s sports delay make the
    replayed P&L negative, or a hold-to-resolution basket with a tiny annualised return.
  - Makers who post NO bids on every outcome and convert already harvest the band (§3.7).

## 8. Deviations from the pre-registration and other caveats

- The `stale_gt5min` flag was pre-registered as "possibly stale". The CLOB `timestamp` is the book's last-change time, not the fetch
  time, so results are given both strictly and with that flag relaxed. The verdict is the same either way.
- Rescans ran every 40 s, inside the pre-registered 30-60 s range. Only about 2 rescans fit into the cycles that also ran a binary scan.
- Code changes made after the interruption are file naming and bookkeeping only. No rule changed:
  - collect.py: scan-id offset `CSA_SCAN_OFFSET=100` for window 2.
  - analyze.py: window filter (w1 / w2 / all).
  - replay_ws.py and ws_monitor.py: choose universe files by numeric version. The replay now uses the union of each window's
    universe snapshots, so window-1 matches that later closed are still replayed. The earlier parquet had been built from the last
    universe only.
- These are exploratory additions, not pre-registered and not used for the verdict: fee sensitivity, on-chain question counts,
  wallet attribution of converts.
- Limits:
  - A 5-minute REST poller with 40 s rescans, plus about 2 h of websocket data on about 600 groups, cannot see sub-100 ms events
    outside the monitored set. A zero means "none visible to a retail poller".
  - Two windows on one Saturday (European soccer in window 1, Latin American soccer in window 2) are a small sample. Weekday,
    election-night or major-match regimes may differ. **UNSUPPORTED** either way.
  - Displayed depth is treated as fully fillable, with no queue position or competing takers, so every profit figure is an upper bound.
  - Taker Rebate Program rebates are ignored in the verdict. §3.4 shows they do not change it.
- Nothing here is risk-free. Even a confirmed (e) still carries leg risk, settlement failure (`RETRYING`/`FAILED`), adapter pause
  gates and fee-schedule changes. (c) adds resolution risk (disputes, 50-50 outcomes, augmented-event redefinition).

## 9. Files

- Scripts in `analyses/complete_set_arb/`:
  - Core scanning and analysis: `csa.py`, `collect.py`, `analyze.py`.
  - Websocket monitoring and replay: `ws_monitor.py`, `ws_runs.sh`, `ws_runs_w2.sh`, `replay_ws.py`.
  - Extra checks: `fee_sensitivity.py`, `verify_exhaustive.py`, `onchain_converts.py`, `onchain_converts2.py`, `converter_wallets.py`.
- Per-scan data in `data/derived/complete_set_arb/`: `scan_*_{groups,members,binary}.parquet`, `cand_*.parquet`, `universe_v*.parquet`,
  `ws_episodes_run*.parquet`, `ws_samples_run*.parquet`, plus the logs `collect.log`, `collect_w2.log`, `ws.log`, `ws_w2.log`.
- Summaries in `data/derived/`:
  - Candidates, per-scan stats and fee bands: `complete_set_arb_events{,_w1,_w2}.parquet`,
    `complete_set_arb_scan_summary{,_w1,_w2}.parquet`, `complete_set_arb_feeband{,_w1,_w2}.parquet`.
  - Websocket: `complete_set_arb_ws_bursts{,_w1,_w2}.parquet`, `complete_set_arb_ws_replay.parquet`.
  - Extra checks: `complete_set_arb_fee_sensitivity_{w1,w2,all}.parquet`, `complete_set_arb_qcount.parquet`,
    `complete_set_arb_onchain_converts.parquet`, `complete_set_arb_converts_d1017.parquet`, `complete_set_arb_converter_edges_d1017.parquet`.
