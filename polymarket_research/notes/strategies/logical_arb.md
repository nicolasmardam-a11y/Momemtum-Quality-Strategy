# Family C: cross-market logical arbitrage (as of 2026-10-17)

Status: COMPLETE for this round (two live windows, 2026-10-17 15:23-16:15 and 21:37-22:36 UTC). The
pre-registration in section 0 was written ~15:10 UTC, before any order-book data was pulled or any edge was
computed. It is reproduced unchanged. Section 0b adds clarifications made later; it does not change any rule.

**Bottom line.** The classic two-leg relations (date ladders, threshold ladders, nested futures, duplicates,
crypto cross-event ladders, sports score grids) show **no demonstrated edge**. The few TRUE-dominance violations
are sub-threshold or tiny ($0.7-1.6 of depth-limited profit per window), and most of the rest are NEAR or
CORRELATED. One sub-family does pass every pre-registered test: **k-of-n count constraints across separate
(non neg-risk) Yes/No markets** ("at most k of these n can resolve Yes", so buying NO on all n pays >= n-k).
Oscars 2027 Best Actor nominations (19 listed actors, at most 5 nominations) and the CFP national-title-game set
(50 teams, 2 play) were profitable after fees at executable prices in **every** snapshot of both windows,
6.5 h apart. They hold about **$520 of depth-limited net profit on about $15k of capital, 3.4-3.6% over
~95-100 days (~12-14%/yr simple)**. Verdict: `promising_test_further`, with a thin R4 margin. **[corrected by auditor 2026-10-18: audited verdict `marginal`. The R4 10%/yr clause fails in window 1 (9.4%/yr capital-weighted, not shown in section 6). It passes in window 2 (11.6%) and in an auditor window on 2026-10-18 06:19-06:47 UTC (12.1%, but on only $9.9k and $314, down from $18.3k and $546). Pooled, it is 10.75%. See Audit.]** It is a
capacity-limited standing stock, not a demonstrated recurring flow, and it is never risk-free: 19-50 separate
oracle resolutions, rule-change risk and execution leg risk all remain.

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

## 0b. Clarifications added after pre-registration (no rule changed)

- **k-of-n count sets** (added 21:40 UTC, before their books were evaluated) are the pre-registered
  "mutually exclusive / exhaustive set of separate markets" relation generalised. If at most k of n separate
  Yes/No markets can resolve Yes, then NO on all n pays >= n-k in every state (`ALL_NO`), so it is an arbitrage
  iff the depth-walked cost plus fees is < n-k. If exactly k must resolve Yes and the list is complete, YES on all n
  pays k (`ALL_YES`); a cancellation that resolves everything No pays 0, so `ALL_YES` is NEAR at best and is
  only evaluated for complete league lists. Same cost model, the same R1-R5, equal shares on every leg.
- **R4 "profit per hour of observation"**: a standing opportunity is counted once (median depth-limited
  profit across its snapshots) and divided by the hours observed. A standing stock seen in two windows is
  still one stock: it is not evidence of a recurring flow, and section 6 says so.
- **Lock-up**: annualised returns use the expected resolution date named in the rules (e.g. Oscars nominations
  2027-01-21, Ballon d'Or ceremony 2026-10-26) when that date is earlier than Gamma `endDate`.

## 1. Data and method (VERIFIED: scripts and outputs listed in section 10)

| step | window 1 (earlier attempt, re-evaluated) | window 2 (this session) |
|---|---|---|
| Gamma pull of all open events (`01_pull_events`) | 15:06 UTC: 22,864 events, 318,605 open markets | 21:31 UTC: 22,704 events, 303,118 open markets |
| candidate relations (`02`, `02b`, `02c`) | 2,948,505 pairs (re-generated with fixed parser) | 2,714,272 pairs (incl. 5,990 new crypto cross-event pairs) |
| CLOB book snapshots (`03`), every 4 min | 13 snapshots 15:23:47-16:15:10, ~171k books, ~133 s each | 15 snapshots 21:37:48-22:33:48, 157-162k books, 86-139 s each |
| k-of-n sets (`06`, side collector `03b`) | from the main snapshots (all 19 Best Actor and 50 CFP legs were present) | 14 snapshots 21:44-22:36 (1,133 markets, 53 sets); Ballon d'Or top-k: 9 snapshots 22:03-22:35 (188 markets) |

Executable prices only: YES ladder = asks of the outcome-0 token; NO ladder = (1 - YES bid, size) from the same
book. Mirror books are VERIFIED in `notes/platform/mechanics.md` section 0. The two legs of a bundle are walked
jointly, best-first, while marginal cost (prices + per-leg taker fee `rate*(p(1-p))^exponent` from each
market's Gamma `feeSchedule`) is below the payoff bound. Up to 30 levels per side are kept. Each leg must reach
`orderMinSize` (5 shares). No rebates. A sensitivity re-prices legacy `sports_fees_v2` at 0.05 instead of 0.03
(`profit_sens`). Lock-up runs to the later leg's resolution. Opportunities are counted per distinct relation
(pair of markets) and per distinct set (Gamma event).

**Two parser bugs found and fixed before the final numbers (VERIFIED):**
1. The run1 relation file (15:2x UTC) had reversed date ladders, e.g. it priced YES("aliens by Oct 31") +
   NO("aliens before 2027"), which pays 0 if confirmation comes Nov 1-Dec 31. That produced a spurious
   "$4,540" top opportunity. The 16:07 regeneration had already fixed it, but run1 was never re-evaluated.
2. The year heuristic turned an expired-but-unresolved "AWS disrupted by September 30?" into 2027 and reversed
   that bundle too. Fix: `parse_date` now takes the year from the market's own rules text ("by September 30,
   2026, 11:59 PM ET"). Window 1 was re-evaluated with the fixed relations (`run1c`).
   After both fixes, no date-ladder relation is in the money in window 1. In window 2, one is, at 0.06%.

## 2. Candidate families (how relations were found)

- **Within-event ladders** (Gamma event + `groupItemTitle` parsing, non neg-risk): `lad_date` "X by d1" => "X by d2"
  (1,490 pairs); `lad_num` above/below thresholds (10,860); `lad_hit` reach/dip ladders with arrows (3,274).
- **Cross-event templates**: `xdate` (same question template, different deadline), `xeps` (EPS ladders), `dup`
  (identical normalised question text, rules text similarity >= 0.98 and identical numbers/dates; 8 pairs).
- **Nested futures** (`02b`, chains chosen by hand from event titles): champion => conference champion =>
  finalist => playoffs; top-k standings; Ballon d'Or winner => top 2 => top 3...; Oscars winner => nominee;
  presidential winner => nominee. 1,916 nested + 188 mutually-exclusive pairs, each tagged TRUE or NEAR a priori.
- **Crypto cross-event** (`02c`, new): all Binance <ASSET>/USDT 1-minute candles. above(K,t) => hit-up(K'<=K, window
  containing t); NOT above(K,t) => dip(K'>=K); price bucket [L,U) => above(K<L) / NOT above(K>=U) / hit / dip;
  weekly hit => monthly hit => yearly hit. 5,990 pairs, each requiring the same Binance pair in both legs' rules.
- **Sports score grids / accumulations** (`grid_*`, `acc_*`): moneyline/spread/total/exact-score covering pairs
  inside one game (~2.65M pairs, dominated by soccer exact-score combinations).
- **k-of-n count sets** (`06`, new): 30 sports sets (NFL 14 of 32 make the postseason, NBA 16 of 30, UCL top 8 /
  9th-24th / R16 / QF / SF / final, conference-round sets, EPL/LaLiga/Serie A 3 relegated, CFP 12-team field and
  title game) + 23 Oscars 2027 nomination categories + 7 Ballon d'Or top-k events. Found by screening non neg-risk
  events whose Gamma best bids sum above 1, then by manual review of which of those have a format-fixed k.
  Most bid-sum>1 events are **not** exclusive (multi-winner "say/mention" markets, nominations, daily strikes), so
  the screen alone proves nothing.

## 3. Rule verification (R3), top candidates

The written rules come from each market's Gamma `description` (pulled 21:31 UTC). External format facts are
labelled.

| relation / set | what the rules say (abridged) | class |
|---|---|---|
| **Oscars 2027 Best Actor nominations, ALL_NO on 19 listed actors** | each: Yes "if the listed actor is nominated for the 99th Academy Award for Best Actor"; No at the announcement (scheduled 2027-01-21) otherwise; No if no nominations by 2027-03-14. All 19 rules texts are identical apart from the name. Academy 99th rules, Rule Five section 6: "Not more than five nominations shall be made for each award, except for the Best Picture award, which shall have ten"; section 7: an ineligible nominee "shall not be replaced" (VERIFIED on a third-party mirror of the official PDF, centrodecine.go.cr; not fetched from oscars.org). **[corrected by auditor 2026-10-18: now VERIFIED on the official oscars.org PDF (`99th_oscars_complete_rules.pdf`, linked from oscars.org/rules, sha256 961ba49e…088e). Rule Five §6: "Not more than five nominations shall be made for each award, except for the Best Picture award, which shall have ten nominations." Rule Six §2: "The five acting achievements in each category receiving the highest number of votes shall become the nominations". Rule Five §7: an ineligible nominee "shall not be replaced". The Academy press release (press.oscars.org) confirms that one actor's multiple performances can each be nominated only "if those performances place in the top five votes", which can only lower the number of distinct Yes persons.]** The 2027 change letting one actor take two slots in a category (secondary press) only lowers the number of distinct Yes persons. | **TRUE DOMINANCE** per written rules (<= 5 of 19 Yes). Residual: 19 separate UMA resolutions; an Academy rule change before 2027-01-21. |
| Oscars Actress (26 listed), Supporting Actor (26) | same template and same cap | TRUE (sub-scale, see section 4) |
| Oscars Best Director (29 listed) | the list includes two co-directing duos as separate persons (Javier Calvo + Javier Ambrossi; Phil Lord + Christopher Miller); one nomination can make two listed names Yes | NOT an arbitrage at k=5. With k_max=7 the set is not in the money: Σbid 6.56 < 7. This is the classic **CORRELATED-looking-like-arb** trap. |
| **CFP national title game, ALL_NO on 50 listed teams** | each: Yes "if the listed team plays in the 2027 CFP National Championship Game ... A team counts as making the game if it is one of the two teams that competes in it"; canceled / not played by 2027-02-08 -> No. 50 identical rules texts, 50 distinct teams. | **TRUE DOMINANCE** (<= 2 of 50 Yes) |
| Ballon d'Or 2026 men's Top 2 (30 listed) | "If more than 2 players tie ... France Football's official top 2 list ... tied ... resolved alphabetically"; postponed after 2026-11-09 / canceled -> No | TRUE (exactly 2), but sub-threshold (0.06%) |
| Ballon d'Or 2026 men's Top 3 / Top 5 (19 listed each) | "officially finishes in the top 5 (positions 1 through 5) of the ... final ranking"; **no tie-break clause** (unlike Top 2 / Top 10) | **NEAR**: a tie at 3rd/5th could make k+1 Yes. Rough probability low (ranking is published without points), not quantified |
| LaLiga 2026-27 relegation, ALL_NO on 20 | "relegated ... through their final standing ..., via relegation playoff defeat, or by any other official league decision recognized by LaLiga" | **NEAR**: an administrative relegation without reprieving 18th place would make 4 Yes (precedent from memory, PLAUSIBLE: when Elche was relegated administratively in 2015, 18th-placed Eibar was reprieved, so it stayed at 3) |
| NBA WCF (15 West teams, 2 advance) | Yes if the team reaches the WCF; eliminated -> No early | TRUE (tiny) |
| Messi wins Ballon d'Or => Messi top 2 (pair) | winner market: no winner by 2026-12-31 -> "Other"; top-2 market: postponed after **2026-11-09** -> No | **NEAR**: fails if the ceremony slips into Nov 10-Dec 31 and Messi wins |
| CFP top-4 seed => makes CFP quarterfinals (pairs) | QF rules: "the four teams seeded 1-4 that received first-round byes ... count as reaching the quarterfinals"; QF not played by 2027-01-13 -> No. CFP kept the 12-team format for 2026-27 (official headline, collegefootballplayoff.com 2026-01-23, VERIFIED headline only) | **NEAR** (deadline mismatch) |
| CFP top-4 seed => makes CFP (pairs) | playoff market: "does not participate ... for any reason -> No" | NEAR |
| NFL divisional round => makes playoffs | playoff market voids if the playoffs begin after 2027-01-24; divisional market waits to 2027-02-28 | NEAR |
| Serie A top 4 => UCL qualification (Lazio, Atalanta) | UCL market counts the allocated place by league position, cup, UCL/UEL title | NEAR (UEFA exclusion/licensing) |
| EPL top 4 => top 5 (Man City) | identical final-standings rules, same tie and postponement clauses | TRUE |
| Stanley Cup champion => conference champion | format | TRUE (0.085%, sub-threshold) |
| The Rock wins presidency => wins Democratic nomination | presidency resolves to whoever wins; the nomination market is Democratic only | **CORRELATED BET** (he could win via another party or as an independent) |
| Anthropic "not IPO by 2027-12-31" in two bracket events | identical rules texts | TRUE duplicate, but 0.15-1.9% over a 440-day lock |
| FDV ladders, ByteDance NPM "hit (HIGH)" ladder, ETH vol-index dip ladder | identical rules texts apart from the threshold; same source and window | TRUE (all small) |
| Crypto cross-event (above vs hit/dip/buckets) | Binance BTC/USDT 1m candle: Close at 12:00 ET strictly above K; High >= K / Low <= K in the window; bucket ties go to the higher bracket (so bucket [L,U) => above(K) only for K < L) | TRUE by construction. Only 2 pairs were ever in the money (0.18%). |

## 4. Results

### 4.1 Two-leg relations (`la_final_relations_2026-10-17.parquet`)

| | window 1 | window 2 |
|---|---|---|
| distinct relations with cost < 1 at >= min size | 63 | 47 |
| persistent (>= 2 consecutive snapshots) | 54 | 43 |
| persistent TRUE/NEAR, pre-game/no-game, edge >= 0.5% (R5) | 17 (TRUE 5) | 12 (TRUE 2) |
| sum of median depth-limited profit, those relations | $11.86 (TRUE $1.55) | $6.91 (TRUE $0.68) |
| relations seen in both windows | 29 | |

The largest TRUE pairs: ByteDance NPM hit(HIGH) $1.0T NO + $900B YES, 49 shares, $0.69 (1.4%, 80-day lock);
ETH vol index dip 40/35, $0.10. The largest NEAR pairs are the CFP seed/quarterfinal pairs at $0.2-1.2 each.
In-play and stale-game grid hits (e.g. a soccer draw/O-U pair 3.3%) are stale books on finished games, not
opportunities (R2/R3). **Two-leg families: R1 passes only trivially (cents); they fail R4 by two orders of magnitude.
No demonstrated edge.**

### 4.2 k-of-n count sets (`la_cnt_summary_w{1,2,3}.parquet`)

Median over snapshots in which the set was in the money at >= 5 shares per leg; depth walked to the payoff bound.

| set (class) | window | in money / snapshots | median net profit | capital | edge | lock (days) | simple ann. |
|---|---|---|---|---|---|---|---|
| **Oscars Best Actor, NO x19, pays >= 14 (TRUE)** | 1 | 12/12 | $481 | $20.4k | 2.4% | 95 | 9.3% |
| | 2 | 14/14 | $483 | $13.8k | 3.6% | 95 | 13.6% |
| **CFP title game, NO x50, pays >= 48 (TRUE)** | 1 | 12/12 | $42 | $1.16k | 3.6% | 100 | 13.3% |
| | 2 | 14/14 | $40 | $1.16k | 3.4% | 100 | 12.6% |
| Oscars Best Actress, NO x26 (TRUE) | 2 | 13/14 | $17 | $2.36k | 0.71% | 95 | 2.7% |
| Oscars Supporting Actor, NO x26 (TRUE) | 2 | 8/14 | $5 | $0.83k | 0.60% | 95 | 2.3% |
| NBA WCF, NO x15 (TRUE) | 2 | 14/14 | $1.4 | $94 | 1.5% | 214 | 2.5% |
| Serie A relegation (rules not checked) / Ballon d'Or Top 2 (TRUE) | 2 / 3 | 9/14, 9/9 | $0.9 / $0.75 | $1.0k / $1.4k | 0.09% / 0.06% | | sub-threshold (R5) |
| Ballon d'Or men's Top 5, NO x19 (NEAR) | 3 | 9/9 | $40 | $4.5k | 0.90% | 9 | 36% |
| Ballon d'Or men's Top 3, NO x19 (NEAR) | 3 | 9/9 | $22 | $2.55k | 0.88% | 9 | 35% |
| LaLiga relegation, NO x20 (NEAR) | 1 / 2 | 12/12, 14/14 | $5 / $31 | $1.1k / $2.3k | 0.4% / 1.4% | 224 | 0.7% / 2.2% |
| NHL East 2nd round, NO x16 (TRUE) | 1 | 4/12 | $3.5 | $0.23k | 1.5% | 199 | 2.8% |

Every complete-league ALL_YES set and every other ALL_NO set (NFL/NBA/NHL/UCL/UEL/UECL stages, EPL relegation,
Oscars Picture/Director/craft categories, Ballon d'Or women's) was out of the money. Gaps to the payoff
ranged from +0.09 to +7 per set. For example, NBA "make playoffs" Σbid was 16.000 with k=16, and fees make it negative.
Market makers keep most count sets consistent to within fees. The two exceptions are long lists of names in
individually traded markets.

Best Actor depth at 21:44 UTC (VERIFIED, raw books): Σ best YES bids 5.679 across 19 actors. Top levels
include Malkovich 685 @0.87 then 2,055 @0.86, Gosling 2,193 @0.43 then 6,649 @0.42, Pattinson 200 @0.42 then
7,780 @0.41, and Damon 90 @0.929. Fees at 0.05 (`culture_fees`) cost about 0.125 per set at the top. The set
stayed in the money down to about 1,000 sets (window 2) and about 1,500 (window 1).

### 4.3 Longer persistence proxy (`08_history_proxy`, NOT executable: CLOB `/prices-history` trade/mid series)

- Best Actor: the sum of the 19 hourly prices has been 5.80-6.18 (median 5.92) since all 19 markets were listed (86 h),
  against k=5.
- CFP title game: the 50-market sum was 4.19-5.49 (median 4.52) for the full 30 days, against k=2.
Consistent with a long-lived structural overpricing of long-shot "Yes" across separate markets. Mid sums are
not tradable, so this is PLAUSIBLE support for persistence, not proof of executable edge before today.

## 5. Capital, lock-up, Combos

- Both legs (or all n legs) lock capital until their own resolution. There is no merge or convert across separate
  conditions. Non neg-risk events have no `convertPositions`, and the neg-risk convert in mechanics.md section 1.4
  does not apply. **Combos / collateral return do not help**: combos are RFQ-only for YES-side requesters, and
  collateral return decomposes offsetting *combo* positions for market makers (mechanics.md section 5.1). Neither
  can release CLOB legs early. VERIFIED from mechanics.md.
- Early release happens only through the rules. Oscars NO legs all resolve at the 2027-01-21 announcement
  ("immediately resolve to No"). Ballon d'Or legs resolve after the 2026-10-26 ceremony. NBA/NFL/NHL legs resolve
  early on elimination ("impossible ... resolve No"). The CFP title-game rules have **no** early clause, so
  assume a lock to ~2027-01-26. For pairs, the implied leg A often resolves first (e.g. a CFP seed on
  2026-12-06), returning part of the capital before leg B.
- An exit before resolution is possible only by selling the NO legs back at their bids, which costs the spread.
  The base case holds to resolution (about 2-3 h after the event for UMA markets; mechanics.md section 4.5).
- Return per day on committed capital: Best Actor 3.5%/95 d = 0.037%/day; CFP 3.4%/100 d = 0.034%/day; Ballon
  d'Or Top 5/3 (NEAR) ~0.1%/day for 9 days; two-leg TRUE pairs <= 0.02%/day except tiny short-dated ones.

## 6. Verdict against the pre-registered criteria

| criterion | two-leg relations | k-of-n sets (TRUE only) |
|---|---|---|
| R1 net edge > 0, TRUE/NEAR, >= 2 consecutive snapshots >= 4 min apart | yes, but cents | **yes**: Best Actor and CFP in 26/26 snapshots across both windows |
| R2 persistence | 43-54 persistent, mostly standing tiny edges | standing for >= 6.5 h live; mid-sum proxy says days to weeks |
| R3 rules | most of the in-money pairs are NEAR or CORRELATED; TRUE pairs are tiny | Best Actor and CFP TRUE per the written rules (section 3) |
| R4 >= $25/h observed **and** >= 10%/yr capital-weighted | fails ($0.7-1.6 TRUE per window) | about $546 of standing TRUE profit in a ~1 h window; capital-weighted simple return ~11.6%/yr on ~$18.2k **[corrected by auditor: that is window 2 only. Window 1 = 9.4%/yr on $21.8k (Best Actor 9.3%), which FAILS. Auditor window = 12.1%/yr on $9.9k. Pooled = 10.75%]** (Best Actor 13.6%, CFP 12.6%, Actress 2.7%, Supp. Actor 2.3%, WCF 2.5%) -> **passes, thinly**. Adding NEAR sets gives ~17%/yr. |
| R5 edge >= 0.5% | fails for almost all | Best Actor 3.6%, CFP 3.4% pass; Actress 0.71% and Supp. Actor 0.60% just pass |

**Verdict: `promising_test_further`**, for the k-of-n sub-family only. **[corrected by auditor 2026-10-18: `marginal`; R4 passes in 2 of 3 windows, see Audit]** Two-leg logical arbitrage:
`no_demonstrated_edge`. Caveats on the positive verdict: (a) the R4 annualised margin is 1.6 points, and 76% of
the capital is one set; (b) it is one standing stock (~$520 TRUE in total), seen twice, not a flow; (c) nothing
was executed, so fill quality, leg risk on 19-50 orders, and whether the bids survive the first leg are untested;
(d) resolution risk is spread over 19-69 separate UMA requests: one wrong Yes costs 1 per set, against an edge of
~0.5-1.6 per set (measured dispute rates: 0.035% overall, 0.6% non-sports; mechanics.md section 4.4).

## 7. Strategy card (k-of-n count-set arbitrage)

- **Signal**: for an event of separate (non neg-risk) Yes/No markets where a format or rule caps the number of Yes
  outcomes at k (nominee slots, finalists, relegation places, top-k ranks with an explicit tie-break), compute
  Σ_i (1 - bestYESbid_i) + Σ_i fee_i, walking each leg's bid ladder with equal shares. The signal fires when this
  is below n_listed - k (equivalently, Σ YES bids exceed k plus fees).
- **Entry**: buy NO on every listed leg in equal share counts (taker), largest-edge-per-share first, only while
  the marginal set cost is < n - k - 0.005*(n-k) (R5 buffer). Each leg needs >= 5 shares and a $1 notional.
  Re-read all books just before the first leg; abort if Σ bids fall back below k plus fees + buffer.
- **Exit**: hold to resolution (payoff >= n-k per set). Optional early unwind if the NO legs can be sold back
  at a total above the cost paid.
- **Data requirements**: Gamma event lists and rules text (to verify k, the tie-break clause, co-nominee
  structures, identical rules across legs); CLOB `/books` for all legs within ~1 s; per-market `feeSchedule`.
  Read-only for detection; a funded wallet would be needed to trade (out of scope here).
- **Holding period**: to the event (Oscars nominations ~95 days; CFP title game ~100 days; Ballon d'Or 9 days).
- **Why it might persist**: each market is quoted on its own. 17/19 Best Actor and 44/50 CFP markets carry
  liquidity rewards ($1-30/day, max spread 4.5-6.5c; `lp_rewards_current_2026-10-17.parquet`), which pays makers
  to rest bids in every market regardless of cross-market consistency (PLAUSIBLE). Taking the arb needs 19-50
  taker orders, months of locked capital for 3-4%, and a rules check per set. Long-shot Yes is generically
  over-bid. No neg-risk convert exists to recycle capital, so dedicated arbitrageurs are deterred.
- **Main reason it might fail**: it is a small, capacity-limited stock. Once one trader sells into the bids it is
  gone, and a recurrence rate has not been measured. Beyond that, a single wrong oracle resolution or an
  unexpected extra Yes (rule change, tie, administrative decision) can wipe out the edge, and the 10%/yr
  hurdle is cleared by only ~1.6 points. **[corrected by auditor: in window 1 it is missed by 0.6 points (9.4%/yr)]**

## 8. Capacity (`09_capacity`, median over snapshots, single opportunity, ignores competition and leg risk)

| account | deployable in TRUE sets | expected net (one pass) | notes |
|---|---|---|---|
| $5k | $5.0k (Best Actor alone) | ~$200 (4.0%) over ~95 days | the best levels give a higher edge at small size; ~15%/yr simple |
| $25k | ~$18.2k (Best Actor $13.8k + CFP $1.16k + Actress $2.36k + Supp. Actor $0.83k + WCF $0.09k) | ~$545 (3.0%) | adding NEAR sets (Ballon d'Or Top 5/3 $7.1k for 9 days, LaLiga $2.3k) gives ~+$94 |
| $100k | same ~$18-27k; the remaining ~$75k idle | ~$545-640 | capacity-bound: ~0.6% of the account |

Two-leg relations add at most ~$7-12 per window (overlapping legs), so they do not change capacity.

## 9. Things that looked like arbitrage but are not (worth keeping)

1. Reversed date ladders from parsing ("by Oct 31" vs "before 2027"), fixed (section 1).
2. Best Director: co-directing duos listed as separate persons (the Σbid 6.56 > 5 is mostly Los Javis counted twice).
3. Rock presidency vs Democratic nomination: a different party is a live failure state.
4. Ballon d'Or Top 3/Top 5: no tie-break clause; Top 2/Top 10 have one.
5. In-play and stale-game sports grid "edges" (books not yet cleared after a goal or the final whistle).
6. Oscars ALL_YES on incomplete lists (an unlisted film can be nominated); an early run showed false positives
   until ALL_YES was restricted to complete league lists.

## 10. Files

Scripts (`analyses/logical_arb/`): `01_pull_events.py` (now takes a tag), `02_relations.py` (date fix),
`02b_futures.py`, `02c_crypto_cross.py` (new), `03_snapshot_books.py` (slim relations + extra markets),
`03b_snapshot_cnt.py` (new side collector), `04_evaluate.py`, `05_summarize.py`, `06_count_sets.py` (new),
`07_combine.py` (new), `08_history_proxy.py` (new), `09_capacity.py` (new).
Derived (`data/derived/`): `la_markets_2026-10-17{,w2}.parquet`, `la_relations*_2026-10-17{,w2}.parquet`,
`la_books/` (28 snapshots), `la_books_cnt/` (14), `la_books_bdo/` (9), `la_opps_2026-10-17_run1c.parquet`,
`la_opps_2026-10-17w2_w2.parquet`, summaries `la_opps_summary_*`, `la_final_relations_2026-10-17.parquet`,
`la_cnt_opps_{w1,2026-10-17w2,bdo}.parquet`, `la_cnt_summary_w{1,2,3}.parquet`,
`la_capacity_2026-10-17w2_la_books_{cnt,bdo}.parquet`, `la_hist_proxy_{531533,801515}.parquet`; logs in `la_logs/`.
Superseded: `la_opps_2026-10-17_run1.parquet` and `run1b` (buggy relations; kept for provenance).
Raw responses: `data/raw/{gamma,clob}/live/20261017/` via `pmr.http`.

## Audit (adversarial review, 2026-10-18 ~06:15-06:50 UTC, auditor; read-only)

Scope: notes, `06_count_sets.py`, `03b_snapshot_cnt.py`, `04_evaluate.py` (price and fee handling), the count-set
summaries, the official Academy rules, and a fresh independent live re-check.
`analyses/audit_live/la_a01_countsets_live.py` is separate code. It re-pulls Gamma `/events/{id}` (membership,
acceptingOrders, negRisk, feeSchedule, min size, tick, rules text). It prices each NO leg on the **NO token's own
asks** and also via the 1−YES-bid mirror, enforces 5 shares and $1 per leg, and runs an independent equal-share
depth walk. 8 snapshots, 4 min apart, 06:19:36-06:47:36 UTC, about 8 h after window 2. Output:
`data/derived/audit_la/cnt_live_20261018T061936.parquet`, `legs_…`, `meta_…json`. Corrections in place are marked
**[corrected by auditor]**.

### What survived the attack (VERIFIED)
- **Rules, the critical point.** The 5-slot cap now comes from the official oscars.org PDF (Rule Five §6 and Rule Six §2,
  quoted in section 3; copy at `data/raw/audit_docs/99th_oscars_complete_rules_oscars.org_20261018.pdf`). The 2027
  multiple-performance rule only lowers the count of distinct Yes persons. The live Gamma rules texts of all 19 Best
  Actor legs and all 50 CFP legs reduce to **one identical template** once the name is masked (md5 check). None changed
  since window 2, and no market was added or removed. The 19 actor names and 50 team names are all distinct (no
  duo-style double counting as in Best Director). TRUE dominance per the written rules holds.
- **Executable prices.** NO-token asks equal 1 − YES bid on every leg in every snapshot (0 mismatches), and there are
  0 crossed books. The walk uses ask ladders only, never mid or last trade. `04_evaluate.py` also uses only ladders.
- **Fees.** Every leg's live `feeSchedule` is {rate 0.05, exponent 1, takerOnly}: `culture_fees` for the Oscars,
  `sports_fees_v3` for CFP, Ballon d'Or and LaLiga. This matches what the study charged. All legs have
  `acceptingOrders=True`, `negRisk=False`, `orderMinSize` 5, and `holdingRewardsEnabled=False` (no extra yield).
- **Persistence.** All four TRUE sets were in the money in **8/8** auditor snapshots. Best Actor and CFP have now been in the
  money in 34/34 snapshots across three windows spanning 15.4 h (12/12, 14/14, 8/8). That rules out a single-snapshot or stale artefact. Book timestamps are often 15 min to
  12 h old: these books change rarely, so legging risk over seconds is low (PLAUSIBLE).

| set (auditor window, median of 8) | Σ best YES bid vs k | net profit | capital | edge | simple ann. | vs window 2 |
|---|---|---|---|---|---|---|
| Oscars Best Actor, NO x19 (TRUE) | 5.652 vs 5 | **$237** | $6.34k | 3.7% | 14.4%/yr | $483 on $13.8k: depth halved (≈470 sets vs ≈1,000) |
| CFP title game, NO x50 (TRUE) | 3.581 vs 2 | $35 | $1.16k | 3.0% | 11.1%/yr | $40 |
| Oscars Supp. Actor, NO x26 (TRUE) | 5.541 vs 5 | $42 | $2.43k | 1.7% | 6.5%/yr | $5 |
| Oscars Best Actress, NO x26 (TRUE) | 5.230 vs 5 | $4.5 | $1.47k | 0.3%: sub-threshold (R5) | — | $17 |
| Ballon d'Or Top 5 / Top 3 (NEAR) | 5.26 / 3.23 | $48 / $41 | $4.5k / $4.4k | 1.1% / 0.9% | ~44-50%/yr (8 days) | $40 / $22 |

### What broke (corrected in place)
1. **R4 depends on the window.** The 10%/yr capital-weighted clause (TRUE sets with edge ≥ 0.5%) gives **9.4%/yr in
   window 1 (FAIL)**, 11.6% in window 2, and **12.1% in the auditor window**. Pooled, it is 10.75%. Section 6 showed
   only window 2. The return also depends on size: about 15%/yr at the top of book, about 9-14%/yr at the
   profit-maximising depth. The $25/h clause passes under any reading, since even $546 spread over the full 15.4 h
   is $35/h.
2. **The stock is shrinking.** Standing TRUE profit went $527 (W1) → $546 (W2) → **$314** (auditor window). The capital
   that clears R5 fell from $18-22k to $9.9k. Capacity for a $25k or $100k account is now about $10k deployable for
   about $300, once.
3. Minor: the "third-party mirror" caveat is resolved (official source now VERIFIED).

### Not re-checked
The two-leg relations (verdict `no_demonstrated_edge`, cents of profit) were not re-sampled live. That verdict
needs no live confirmation to stand.

**Audited conclusion: two-leg relations `no_demonstrated_edge` (unchanged). k-of-n count sets: a real, rule-verified,
persistent TRUE dominance, but economically `marginal`.** It clears the pre-registered 10%/yr hurdle in 2 of 3
windows, 10.75% pooled. It is a single ~$250-550 stock that is shrinking, with the capital locked about 95-100 days.
Risks remain: 19-50 separate UMA resolutions (one wrong Yes costs 1 per set against about 0.5 per set of edge), a
mid-season rule change, and leg risk across 19-50 taker orders. A forward test (weekly snapshots to 2027-01-21, plus
other award and playoff sets) is still the right next step. It is never risk-free.

## 11. Historical recurrence proxy for count sets (added 2026-10-18, post hoc; `10_count_set_history.py`)

Question: how often do k-of-n count sets like Best Actor arise? Method: every closed, non-neg-risk event with ≥ 5
"nominated / nomination" markets in the Gamma universe (32 events, 2024-05 to 2026-01). For each event, the hourly
CLOB `/prices-history` YES series of every listed market over the 60 days before resolution was summed and compared
with k. k is the official nominee count: VERIFIED for the Oscars acting, director, documentary, international and
animated categories and for Best Picture; ASSUMED for Casting, Grammys (8), Golden Globes (6) and Actor Awards (5).
Every assumed k is consistent with the realised number of Yes resolutions (yes ≤ k). The proxy profit per all-NO set is
Σ YES − k − 0.02 × n_legs. The cost allowance is calibrated on one live snapshot (Best Actor 2026-10-17: mid-sum 5.92,
bid-sum 5.68, fees ≈ 0.125). **Prices are trade/mid series, not executable**, and thin markets' series are often stale
last trades. Output: `analyses/logical_arb/out_10_count_set_history.csv`.

Findings (PLAUSIBLE, proxy):
- **Frequency.** 30 of 32 sets came in the 2025-26 award season: Grammys (Nov), Golden Globes (Dec), Actor Awards
  (Jan) and Oscars (Jan). The other 2 are the 2024 party-nominee sets (k = 1).
- **How many looked profitable.** 10 of 32 had a positive proxy profit for > 50% of their listed hours:
  - the 2024 Republican and Democratic nominee sets, median proxy return 1.2% and 1.6%;
  - Grammys Best New Artist (5.5%) and Album of the Year (10%);
  - Golden Globes Best Actor – Drama (11.4%);
  - five Actor Awards TV/ensemble sets (1.7-10.3%).
- **Those 10 are small.** All but the political sets had lifetime volume of $2k-$207k, so executable capacity was
  probably tens to a few hundred dollars per set (UNSUPPORTED: depth was not observed).
- **The liquid sets were about break-even.** For the 2026 Oscars categories (lifetime volume $0.6-1.9M), the median
  proxy profit was about 0 or negative: Best Actor −0.002 per set (positive 49% of hours), Director −0.02 (41%),
  Supporting Actor −0.13 (21%), Picture −0.60 (0.4%), Actress −0.79 (0%).
  - The current (2027) Best Actor set, with mid-sum 5.92 versus 5.40 a year earlier, is therefore unusually
    mispriced for a liquid category.
- **Implication.** Count-set opportunities recur seasonally, a few times a year and mostly in award season. Where
  depth exists, the edge has usually been near zero after costs. The sizeable live opportunity of 2026-10-17 looks
  like the exception, not a steady flow. Not tested here: sports count sets, other keyword families, and executable
  depth in past seasons.
