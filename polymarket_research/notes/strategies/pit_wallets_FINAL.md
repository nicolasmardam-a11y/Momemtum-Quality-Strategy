# Point-in-time wallet following on Polymarket: final audited conclusions

- Stage 4 of 4 (adversarial audit), written 2026-10-18. Project as-of date: 2026-10-17.
- What it covers:
  - stage 1, the build: `pit_wallets_build.md`;
  - stage 2, the pre-V2 follower test for 2024-2025: `pit_wallets_results.md`;
  - stage 3, the 2026 V2 holdout: `pit_wallets_v2_holdout.md`;
  - the pre-registration: `pit_wallets_preregistration.md`. It is unchanged; only the pointer addendum AUD-A1 was added.
- Audit scripts: `analyses/pit_wallets/a01_*.py` .. `a07_*.py`. Audit outputs: `data/derived/pit_wallets/audit/`.
  Corrections in the stage notes are marked **[corrected by auditor]**.
- Labels:
  - **VERIFIED**: computed or re-computed from the data, or checked against a primary source;
  - **PLAUSIBLE**: consistent with the evidence but not directly verified;
  - **UNSUPPORTED**: no evidence.

## 0. Answer for the trader

**Do not copy-trade wallets picked by "5 bets in the last 12 months, all won".** A follower who copies their new bets
at prices available after detection loses money. The pre-V2 test period gives -7.1% per dollar staked, 95% CI
[-10.6%, -3.7%]. Train and validation are negative too, and the 2026 holdout gives -3.2%. That rule also loses to
random wallets and to random entries at the same prices. **VERIFIED.**

**The rule finds people who bought near-certain favourites, not forecasters (VERIFIED).**
- Look at random eligible wallets that had exactly 5 resolved bets. 27% of them won all 5, and their own entry
  prices predict 24-30%.
- The median S1 wallet paid 0.98 per share. It would have gone 5 for 5 with probability >= 0.91 by luck alone.
- Its total profit on those five wins was $0.43.

**None of the seven better-designed alternatives works either.** They are:
- (b) >= 5 bets, no loss;
- (c) a skill z-score;
- (d) category specialists;
- (e) large bets;
- (f) wallets returning after inactivity;
- (g) clusters of brand-new wallets;
- (h) top-1% trailing P&L.

All 28 pre-registered hypotheses are rejected, and the four screens re-tested on 2026 data are rejected again. The
skill and P&L screens do pick wallets whose own entries have positive edge. That edge is already in the price by the
time a follower can act, even 5 seconds later.

**What we found is "no demonstrated edge", which is not the same as "proven impossible".** Residual uncertainty is in
section 6. The most promising untested variant would need a fresh pre-registration and live data, not more tuning
here.

## 1. Verdicts by strategy

**Model.**
- **Primary (pre-registered).** Buy the first taker BUY print by another wallet at or after detection (t + 2 min,
  within 60 min), pay that price + 0.01 (capped at 0.999), stake $100, hold to resolution.
- **Data.**
  - The TEST split uses selection dates 2025-07..2025-12, with each date's following month as its evaluation window.
  - The 2026 holdout uses one selection date, 2026-06-01, with signals from 2026-06 to 2026-09.
- **Fees.**
  - fee 0 = the on-chain fee field in force: zero from 2025-04, negligible before.
  - current = today's taker schedule. Stage 2 used the category table; stage 3 used each market's own feeSchedule.
- **Estimators.** Results are reported three ways because, under the print-based fill rule, whether a signal fills
  depends on its outcome:
  - *drop*: the pre-registered rule; unfilled signals are dropped;
  - *ipw*: the outcome-neutral "always filled" estimate;
  - *adv*: the adverse-fill bound.

| | strategy | signal (screen) | test net ROI, fee 0 [95% event CI] | current fee: drop / ipw / adv | best delay, current fee (drop) | vs benchmarks (test) | 2026 holdout (M1, current fee) | rejection status |
|---|---|---|---|---|---|---|---|---|
| (a) | exactly 5 resolved bets, all won (trader's idea) | P S1 | **-7.1%** [-10.6, -3.7]; 1,542 events | -7.8% / -7.6% / -10.1% | -8% at 5 s (-8% to -10% at every delay) | below B1 (-4.7%), B2 (-2.8%) and matched random entries (-3.1%; difference -4.0 pts [-7.7, -0.4]) | -3.2% [-7.9, +0.5], 90 events; corrected members only -2.6% [-7.2, +1.0] | **REJECTED**: criteria 1, 2, 5; holdout also criterion 3 (< 100 events). Made-money variant S1m: -7.4%, rejected |
| (b) | >= 5 resolved bets, no loss | P S2 | **-3.2%** [-4.5, -2.0] | -3.6% / -4.0% / -5.7% | -3% at 5 s | above B1 (p 0.15), below B2 (-1.7%) and matched (-1.3 pts [-2.5, -0.3]) | -0.6% [-3.4, +2.2]; ipw +0.3% [-0.4, +1.0]; vs random entry +0.7 pts (p 0.34) | **REJECTED**: 1, 2, 5 |
| (c) | skill (shrunken edge z >= 2, >= 10 bets) | P S3 | **-7.8%** [-11.1, -4.4] | -10.8% / -11.3% / -19.6% | -10% at 5 s | equal to matched entries (-0.6 pts [-4.0, +3.1]); own entry edge +1.2 pts, follower edge -0.2 | -3.8% [-12.2, +6.1] (audit rule; note said -4.5%) | **REJECTED**: 1, 2, 5 |
| (d) | category specialist (S3 rule within one category) | P S4 sports / politics / crypto / other | -4.9% / -6.0% / -5.1% / -2.9%; CIs [-8.4, -1.1] / [-13.4, +2.8] / [-8.5, -1.3] / [-12.0, +7.4] | -7.2 / -7.8 / -8.2 / -5.2% (drop); ipw -8 to -12% | sports -3% (5 s), other -2% (10-60 min), politics and crypto -8% | politics and other beat matched random entries (+8.8 [+1.4, +17.2], +13.4 [+4.3, +23.7] pts) but lose money; own edge +0.6 to +7.6 pts, follower edge -0.1 to +0.2 | not tested | **REJECTED**: 1, 2, 5 (all four) |
| (e) | large bet (10-min buys >= 5x own median; known at t0 + 10 min) | F1, best = S4_sports | best **+3.0%** [-4.0, +11.3]; others -0.2% to -16.5% | S4_sports +1.1% / -0.1% / -5.6% | S4_sports -1% at 5 s, +1% at 2 min | S4_sports beats B1 (-2.7%) and matched (-4.3%) by +5.7 to +7.3 pts, not significant after Holm | not tested | **REJECTED**: S4_sports fails 1, 2, 4 (top 1% of signals = 273% of P&L), 5 (validation -4.4%, train -5.0%); all other F1 fail 1, 2 |
| (f) | returning after >= 60 days inactive | F2 (all screens) | -2.2% (S1) to -16.2% (S5); S4 -9% to -100% | S1 -2.7%, S1m -5.5%, S5 -18.2%, others -10% to -100% | none positive | B1 F2 -7.2% | not tested | **REJECTED**: all fail 1, 2; 3 cells < 100 events (inconclusive) |
| (g) | clustered new wallets (>= 3 fresh wallets, >= $20k, 60 min) | CL | **-0.7%** [-6.2, +5.4]; without the cluster's own prints -0.8% [-6.6, +5.8] | -2.0% / -1.8% / -5.5% | -1% at 5 s | above B1 (-4.7%, p 0.12), B2 (-3.1%, p 0.21) | not tested | **REJECTED**: 1, 2, 5 (validation -10.4%; -15.2% without self-prints) |
| (h) | naive profitable (top 1% trailing P&L) | P S5 | **-1.8%** [-5.1, +1.5] | -4.6% / -4.9% / -11.5% | -4% at 5 s; -12% at the hourly poll | beats matched random entries (+3.5 pts [+0.2, +6.9]) and B1 (p 0.10, unadjusted) but loses money; own edge +1.5 pts, follower 0.0 | -4.0% [-9.8, +2.1] | **REJECTED**: 1, 2, 5 |
| | benchmarks | B1 random eligible wallets | -4.7% [-7.5, -1.8] | -7.0% / -8.6% / -15.2% | | zero (no trade); T-bill accrual 0.0-0.3% per signal | B1 -9.2% | |

**Notes on the table.**
- **Rejection criteria** (pre-registration section 11):
  1. ROI <= 0, or the CI includes 0;
  2. does not beat both B1 and B2 after Holm correction over 28 hypotheses (every Holm p = 1.00);
  3. fewer than 100 events;
  4. fragile (top 1% of signals or a single event carries more than 50% of P&L);
  5. not positive on validation.
- **Status of each verdict.** All verdicts are VERIFIED for this data and this execution proxy. The auditor's own code
  reproduces every number. The 2026 column uses the audit's stricter fill rule (section 2.3).
- **Delays.** Results by delay, at 5 s, 30 s, 2 min, 10 min, 15 min, 60 min and an hourly poll, are in section 4.

## 2. Audit findings

### 2.1 Look-ahead and survivorship

**Trailing record (stage 1).** No look-ahead found. **VERIFIED.**
- **Code review of the server SQL (`04_screens.py`).**
  - A decision counts only if `cnt AND p >= 0 AND r > 0 AND r < D`, where r is Gamma closedTime.
  - The trailing window is t0 in [D - 12 months, D).
  - The features n_win and med_usd use only episodes that ended before D.
  - The event-level made-money flag (S1m) counts only tokens first traded before D, and requires each of them to be
    resolved before D.
- **Fills after D.** Per-token totals do include fills up to 2026-01-01, but for a decision resolved before D any later
  fill would be a post-resolution fill. Those are rare: 0.0065% of tokens have a fill more than 1 hour after closedTime.
- **Independent re-derivation (`a03`).** This was a fresh hash sample at TEST dates, coded by the auditor and using
  Data API fills cut at D:
  - 25 of 25 S1 memberships were reproduced;
  - 14 of 14 negative controls were correctly not S1 (8 wallets with 5 bets and 4 wins, 6 with 6 bets and 6 wins);
  - every counted market's UMA resolution record (`/v2/resolutions`, a second source) is also before D.
  - Stage 1's own audit had already reproduced 39 of 39 memberships across S1, S1m, S2 and S3.
- **Resolution time.** closedTime was never earlier than the UMA record in a 432-market sample (stage 1). Using it
  delays counting; it never advances it.

**Universe and survivorship (stages 1-2).** No survivorship issue found. **VERIFIED.**
- The universe is every wallet in `orders_filled`, processed in 256 hash buckets with no activity filter. A wallet does
  not need to exist later to be included.
- Market metadata covers 99.98% of fill volume. The lookup used every traded token, with closed=true and then open, and
  no end-date filter.
- The evaluation samples (md5 rank) and the pricing samples (md5 hash) do not depend on outcomes.
- No future volume is used anywhere in the screens.

**Stage-3 market table: an error. [corrected by auditor]**
- The 2026 market table came from the shared universe, filtered to endDate < 2026-10-16. That filter drops markets
  that resolved early but carry a later endDate.
- A Gamma lookup (`a05`) found:
  - 1,309 such markets resolved cleanly before D;
  - 575 more resolved inside the evaluation window.
- **Effect on screens.** 23 of the 55 stage-3 S1 members were misclassified: they had one or two more resolved bets, so
  not exactly 5. The corrected S1 has 43 wallets.
  - On the 32 correctly classified members the holdout result is -2.6% [-7.2%, +1.0%] (85 events), against -3.2% for
    all 55. The verdict is unchanged.
  - S2 loses 19 and gains 15 of its 1,031 members; S3 loses 4 and gains 5 of 126.
- **Effect on the evaluation window.** Some signals should have been evaluable but were left out: S2 705, B1 222, S5 75,
  S3 51, S1 2. For S2 the effect is about 0.1 point (PLAUSIBLE).
- **Stage 3 also used final volume.**
  - The candidate-pool strata use the final volume of markets that had already closed before D. That is
    point-in-time.
  - The benchmark markets are drawn in proportion to final evaluation-window volume. That is look-ahead in a
    benchmark, not in a strategy. Its only effect is to tilt the random-entry benchmark toward liquid markets.

### 2.2 Fill accounting

All five checks pass. **VERIFIED.**
- **One row per order.** Each `OrderFilled` row is one order's fill, and the owner is the `maker` column, so maker and
  taker legs are not double-counted. This was checked 28 of 28 against the Data API in stage 1.
- **Side, NegRisk and decimals.**
  - Side comes from `maker_asset_id = '0'`, which marks a BUY.
  - NegRisk fills have the same row shape as other fills, and every row carries its owner's own price, including in
    MINT and MERGE matches.
  - Amounts use 6 decimals.
- **No contract owners (new check, one CryptoHouse query).** No exchange, NegRisk-adapter or CTF contract ever appears
  as a fill owner, so contract rows cannot pollute the "other wallets'" prints.
- **Data API v2 rows.** Rows are consistent with CryptoHouse (stage-1 audit, `a03`), and `outcome_index` matches the
  Gamma token order on 6,930 rows (stage 3).
- **Remaining approximation.** Made-money P&L is fill-based. It is approximate for NegRisk conversions, splits and
  transfers; about 8% of S3/S5 member rows are flagged "unreliable". This affects only the S1m screen, which treats
  unreliable as "not made money", the conservative choice.

### 2.3 Follower execution

**Invariants (VERIFIED, `a01`).** Across 236,947 signals:
- the follower's print is never before detection: 0 negative gaps at all 7 delays;
- signal time equals t0 for P and F2 signals and t0 + 600 s for F1 (whose size test is only knowable then): 0
  violations;
- every decision lies in its evaluation window: 0 violations;
- payout and t_res in the signal table equal the token metadata: 0 mismatches.

**The followed wallet's own prices are not used.** Its fills are excluded from the follower's prints by wallet, and
its same-transaction fills by time (detection is at least 5 s later).

**One exception: the cluster signal (CL). [corrected by auditor]**
- CL used prints of the cluster's own fresh wallets, in breach of pre-registration sections 7 and 12.
- At 2 minutes, 41% of CL first prints were such buys.
- Re-priced without any fresh wallet whose first decision is on that token (`a04`): test -0.8% (was -0.7%),
  validation -15.2% (was -10.4%). The verdict is unchanged.

**No midpoint or `/prices-history` price is treated as executable.** Entries are prints that actually traded. With no
historical order book, the proxy cannot show depth (PLAUSIBLE proxy). Stage 2 cross-checked it against the Data API
tape: fill status matched 25 of 25 and price within half a cent in 17 of 18.

**Unfilled signals are not ignored.**
- A signal counts as filled only if prints follow it, and that depends on the outcome (VERIFIED).
- The pre-registered *drop* rule is therefore biased: upward for large VWAP sizes, slightly downward for first-print
  fills.
- Every verdict also holds under *ipw* and *adv*. The auditor's own ipw implementation matches stage 2's to within
  0.02 point in 30 of 31 test cells.

**Prints after resolution. [corrected by auditor]**
- Stage 2 never fills at or after t_res.
- Stage 3 required only detection before t_res. That let 18 signals fill on a print at or after t_res.
- With the stricter rule: S3 -3.8% (was -4.5%), S5 -4.0% (was -4.1%), B1 -9.2% (was -9.4%).

**Slippage convention. [corrected by auditor]**
- The pre-registered +0.01 "tick" is ten ticks above 0.96, where the tick is 0.001. 64-76% of S1/S1m/S2 entries are
  above 0.96.
- A tick-aware rule (+0.001 above 0.96 and below 0.04, +0.01 between) and a no-slippage rule were run as post-hoc
  checks:
  - S1 is -6.6% [-10.4%, -2.7%] tick-aware and -6.0% [-9.5%, -1.8%] with no slippage.
  - Across 186 test variants (all signal sets x 3 slippage conventions x 2 fees x drop / ipw), **no confirmatory
    hypothesis has a CI above zero.**
- The best case is F1 S4_sports with no slippage, fee 0 and ipw: +4.6% [-0.4%, +9.6%]. It is negative on train and
  validation under every convention.

**Latency.** The first print can come minutes after detection: the median gap is 6-718 s by screen. ROI by gap bucket
shows no pattern of fast fills being profitable. For example, S1 entries filled within 10 s return -14.6% (`a01` /
inline check, PLAUSIBLE reading). At the 5-second delay every P screen is still negative.

### 2.4 Fees

**Historical fees (VERIFIED).** The on-chain fee field is zero on every fill from 2025-04 onward and negligible before.
Fee 0 is therefore the correct historical case.

**Current fees in the prospective case: applied.** **VERIFIED.**
- **Stage 2** used a category table: crypto 0.07, sports 0.05, politics 0.04, other 0.05. The fee per dollar staked
  is rate x (1 - p), which matches `fee = shares x rate x p(1 - p)`.
  - [corrected by auditor] The table slightly overstates today's per-market fees for some markets: `sports_fees_v2` at
    0.03, fee-free geopolitics, and finance and tech at 0.04.
- **Stage 3** applied each market's own feeSchedule.
  - Every evaluated market has exponent 1, so the formula `rate x (p(1-p))^exp / p` per dollar is correct there. It
    would overstate fees by 1/p for the legacy exponent-2 markets, but none was evaluated.
  - On-chain charges for `sports_fees_v2` were 0.05 in parts of July 2026 against 0.03 on Gamma, a slight
    understatement.

**Neither fee issue can change a verdict.** Every hypothesis already fails at fee 0. Any taker rebate is 3-50% of the
fee, so a rebated result lies between the fee-0 and current-fee columns.

### 2.5 Dependence, test-period integrity, multiple testing

**Clustering. VERIFIED.**
- Confidence intervals are clustered by underlying event, with sports games merged across Gamma sub-events (A6).
  Calendar-week CIs are also reported.
- The auditor added **wallet-clustered CIs**, because many signals come from a few bot wallets. Examples: P S1
  [-9.5%, -4.6%], P S5 [-5.5%, +2.3%], F1 S4_sports [-4.1%, +11.7%], 2026 S1 [-10.6%, -0.3%]. No verdict changes.

**Test-period integrity.**
- The pre-registration (15:12Z) and addendum A10 (23:27Z) are timestamped before any follower price was pulled
  (`13_follower_prices.py`, last modified 23:28Z) (PLAUSIBLE: the timestamps are self-reported but consistent with
  file times).
- The auditor rebuilt the 28 confirmatory numbers from the pre-registered definitions and got the published values.
  So whatever iterations happened, the confirmatory results are the pre-registered computation (VERIFIED).
- After the confirmatory results were seen, the 10,200-variant grid and addenda A11 and A12 were run on the same test
  split. The 2024-25 test split is therefore spent for any further hypothesis.
- The 2026 holdout protocol was written before any post-2026-06-01 data was pulled. It is a clean replication for
  S1, S2, S3 and S5 only.

**Multiple testing. VERIFIED** by code review and reproduction.
- Holm over the 28 confirmatory hypotheses, each with p = max(p vs B1, p vs B2). Every Holm-adjusted p = 1.00.
- The exploratory grid applied Holm and a White reality check over 8,526 testable variants. Under ipw and adv, 0
  variants survive.
- The auditor's 186 sensitivity variants are post hoc and exploratory, and none has a CI above zero.

### 2.6 Economic sense and base rate of the 5-for-5 screen

All figures from `a02` (VERIFIED, trailing data only).

**Base rate.**
- S1 holds 1.1-4.4% of eligible wallets at each date (median 3.0%), about 10-12k wallets a month in 2025-H2.
- 10-20% of eligible wallets have exactly 5 resolved bets.

**Luck null.** Take the 1% random sample of eligible wallets (B1) at test dates. Among those with exactly 5 resolved
bets:
- 26.9% won all 5;
- their entry prices imply 23.5-30.1% under fair pricing (lower bound 1 - sum(1 - p_i), upper bound mean(p)^5).

Validation dates: 27.4% against 23.7-31.3%. Train: 14.4% against 11.0-18.8%. So **the 5-for-5 record carries no excess
skill over its price-implied base rate.** Random eligible wallets overall win 65.2% of bets against 66.3% implied, a
mean edge of -1.05 points.

**What S1 members look like** (test dates, 66,109 member rows):
- median implied entry price 0.982;
- 85% at 0.90 or above;
- probability of going 5 for 5 by luck alone: median >= 0.91;
- median trailing P&L $0.43, on a median $89 of resolved stake;
- 20.6% won all 5 but made <= $0 (outcome-won is not made-money);
- membership turns over by about half each month (stage 1).

**Forward.** In the following month their own entries have edge -2.3 points, and the follower's -2.2 points. In a
logistic regression of the outcome on the follower's price, the S1 coefficient is negative (-0.33, one-sided p for > 0
of 0.99). The screen picks low-sample, near-certain-favourite buyers. It is mostly luck, as far as luck is involved at
all: the wins are what the prices predicted.

### 2.7 List of corrections made

| note | what | effect |
|---|---|---|
| `pit_wallets_build.md` | Audit box. The S1 "favourite-buyer" prior upgraded from PLAUSIBLE to VERIFIED (luck null). The A2 "complete before D" claim qualified (rare fills after closedTime). | none |
| `pit_wallets_results.md` | CL priced with the cluster's own prints (sections 7 and 12 breached by A10); re-priced. | CL test -0.7% -> -0.8%; validation -10.4% -> -15.2% |
| `pit_wallets_results.md` | +0.01 is ten ticks above 0.96; tick-aware and no-slippage results added. | S1 -7.1% -> -6.6% / -6.0%; no CI above 0 anywhere |
| `pit_wallets_results.md` | The current-fee stress overstates some per-market fees (sports_fees_v2, geopolitics, finance/tech). | stress slightly pessimistic; no verdict effect |
| `pit_wallets_results.md` | Wallet-clustered CIs added. | none |
| `pit_wallets_v2_holdout.md` | Market table misses early-resolved long-dated markets: 23 of 55 S1 members misclassified; some signals not evaluated. | S1 on correct members -2.6% [-7.2, +1.0]; verdict unchanged |
| `pit_wallets_v2_holdout.md` | M1 filled on prints at or after t_res (18 signals). | S3 -4.5% -> -3.8%; S5 -4.1% -> -4.0%; B1 -9.4% -> -9.2% |
| `pit_wallets_preregistration.md` | Pointer addendum AUD-A1 only. No rule changed. | none |

## 3. Why copying fails even for wallets with real edge

These figures are for the test split, P signals, at the 2-minute delay (stage 2; VERIFIED, reproduced). Each pair is
the followed wallet's own edge at its own first-fill price, against the follower's edge at the next print. Edge =
payout minus price, in probability points.

| screen | own edge | follower edge |
|---|---|---|
| S3 | +1.2 | -0.2 |
| S4_sports | +2.1 | -0.1 |
| S4_politics | +4.7 | +0.2 |
| S4_other | +7.6 | +0.2 |
| S5 | +1.5 | 0.0 |
| S1 | -2.3 | -2.2 |
| B1 | -0.3 | 0.0 |

**The price moves before the follower can act.** The informative wallets do earn their edge. The market price absorbs it
within seconds to minutes, before a follower can trade at all, and a 5-second delay does not recover it.

**After the move, the follower is a random taker.** Their expected ROI is the market's taker return at that price
(about -2% to -20% by category and price; B2 cells), plus slippage and fees.

**The screens are only "less bad".** S4_politics, S4_other and S5 beat matched random entries by +3.5 to +13.4 points.
That happens only because the matched random entries lose heavily in those categories (the favourite-longshot loss of
takers). Net, the screens still lose money.

## 4. Delay decay under current fees (test split, first print + 0.01, hold, drop / ipw)

| signal | 5 s | 30 s | 2 min | 10 min | 15 min | 60 min | hourly poll |
|---|---|---|---|---|---|---|---|
| (a) P S1 | -8% / -8% | -8% / -8% | -8% / -8% | -9% / -8% | -9% / -8% | -10% / -9% | -9% / -8% |
| (b) P S2 | -3% / -4% | -3% / -4% | -4% / -4% | -4% / -5% | -3% / -4% | -4% / -5% | -3% / -4% |
| (c) P S3 | -10% / -10% | -10% / -11% | -11% / -11% | -12% / -13% | -11% / -11% | -17% / -14% | -17% / -15% |
| (d) P S4_sports | -3% / -3% | -7% / -8% | -7% / -8% | -8% / -9% | -8% / -9% | -9% / -12% | -7% / -9% |
| (d) P S4_politics | -9% / -12% | -8% / -12% | -8% / -11% | -9% / -13% | -10% / -13% | -13% / -16% | -12% / -14% |
| (d) P S4_crypto | -9% / -10% | -8% / -9% | -8% / -9% | -13% / -14% | -14% / -11% | -46% / -24% | -26% / -17% |
| (d) P S4_other | -6% / -11% | -5% / -10% | -5% / -11% | -2% / -10% | -2% / -9% | -2% / -14% | -3% / -11% |
| (e) F1 S4_sports | -1% / -2% | -1% / -2% | +1% / -0% | -3% / -3% | -3% / -4% | -4% / -2% | -3% / -3% |
| (e) F1 S5 | -7% / -5% | -8% / -6% | -7% / -3% | -5% / -3% | -6% / -3% | -6% / -3% | -10% / -2% |
| (f) F2 S1 | -3% / -5% | -2% / -5% | -3% / -4% | -3% / -5% | -5% / -6% | -6% / -5% | -6% / -6% |
| (f) F2 S5 | -18% / -19% | -18% / -18% | -18% / -18% | -18% / -18% | -20% / -19% | -18% / -20% | -17% / -17% |
| (g) CL | -1% / -1% | -2% / -2% | -2% / -2% | -1% / -2% | -3% / -2% | -3% / -2% | -3% / -3% |
| (h) P S5 | -4% / -4% | -4% / -4% | -5% / -5% | -7% / -6% | -7% / -6% | -9% / -8% | -12% / -8% |
| B1 random (P) | -7% / -8% | -7% / -8% | -7% / -9% | -8% / -10% | -8% / -10% | -13% / -11% | -12% / -11% |

The full table for all 25 signal sets is in `audit/a07_tables.md`, and the grid with CIs is in `results/grid.parquet`.

**2026 holdout** (M1, current per-market fee, audit fill rule; drop estimator):

| screen | 5 s | 30 s | 2 min [event CI] | 15 min | 60 min | poll |
|---|---|---|---|---|---|---|
| S1 | -4.1% | -3.2% | -3.2% [-7.9, +0.5] | -3.2% | -3.7% | -3.6% |
| S2 | 0.0% | -0.5% | -0.6% [-3.4, +2.2] | -0.9% | +1.7% | +0.6% |
| S3 | -10.7% | -9.8% | -3.8% [-12.2, +6.1] | -9.1% | -13.5% | -16.5% |
| S5 | -3.6% | -3.1% | -4.0% [-9.8, +2.1] | -2.2% | -3.7% | -7.9% |
| B1 | -4.2% | -5.5% | -9.2% [-15.0, -2.9] | +0.6% | +8.2% | +6.3% |

The late-delay positives for B1 and S2 come from fill selection: few signals fill that late. Under *adv* they are
-6.9% and -0.6% (stage 3).

**World Cup subset.** It has 4-77 events per group, too few to support any conclusion, and B1 does as well as any
screen there. The trader's examples (mintblade, GRIMDRIP) were created 2026-06-02, after the selection date, so no
point-in-time screen could have picked them. mintblade's record is 5 markets in 3 underlying events.

## 5. Other exploratory results (no edge; not confirmatory)

- **First-second large bet (F1b, knowable at t0).** On test, S3, S5 and S4_politics are positive under current fees:
  +3.6% to +5.0% (drop) and +4.8% to +5.4% (ipw), with every CI including 0.
  - The same cells are negative on train (-6.7% to -8.9% drop, -6.8% to -7.2% ipw). On validation they are -8.4% to
    +1.3% (drop) and -6.2% to -1.2% (ipw). Holm p = 1.00.
  - Random wallets' large first bets also show +0.6% on test.
  - If anything deserves a new pre-registered test on live data, it is this one (PLAUSIBLE candidate only).
- **Every add-on buy (ADD).** Test ROI ranges from -25.7% (S1) to +0.8% (S3) under the drop rule. It is not an edge.
- **Exit when the followed wallet sells.** It changes ROI by -3 to +1.4 points and makes no screen positive.
- **Size and portfolio.**
  - VWAP fills of $500-$10,000 look profitable under *drop*, and random wallets show the same profits (fill-selection
    artefact, VERIFIED).
  - Under the outcome-neutral rules, every portfolio loses money on deployed capital, apart from +1-2% for S1 at $5k
    and S2 at $100k.
  - Capacity is a few hundred dollars per signal: a $500 order is a median 11-30% of the next 30 minutes' taker-buy
    volume.

## 6. What is not established (residual risk)

- **Execution realism.**
  - There is no historical order book. Entries are other wallets' later taker prints, and fills are outcome-dependent.
    The truth for a real taker follower probably lies between ipw and adv (PLAUSIBLE).
  - Maker or limit-order following was not tested (UNSUPPORTED either way).
- **Regime.** The 2024-25 evidence is pre-V2. The 2026 replication covers one selection date and four screens: S1 has
  85-90 events and 12-24 wallets, so its power is low. S4, F1, F2 and CL were not re-tested on 2026 data.
- **Identity.** One trader may run several wallets. Point-in-time screens per address cannot see this (UNSUPPORTED).
- **Information beyond fills.** Off-chain information about wallets, such as social media or known insiders, was not
  used. Nothing here alleges insider trading.
- **Spent data.** The 2024-25 test split has been used for the confirmatory test, a 10,200-variant grid and this audit.
  Any new idea, including F1b, needs fresh data after 2026-10-17 and a new pre-registration.

## 7. Reproduction (run from `polymarket_research/`)

| script | purpose | output (`data/derived/pit_wallets/audit/`) |
|---|---|---|
| `a01_recompute_stage2.py` | independent stage-2 recompute: invariants, event/wallet/week CIs, delays, slippage x fee x estimator | `a01_recompute`, `a01_delays`, `a01_slippage_sens` |
| `a02_base_rates.py` | S1 base rate and price-implied luck null | `a02_base_rates`, `a02_s1_profile` |
| `a03_pit_audit_s1.py` | Data API re-derivation of 25 S1 members + 14 controls at test dates; UMA resolution before D | `a03_pit_audit`, `a03_decisions` |
| `a04_cluster_selfprints.py` | CL re-priced without the cluster's own fresh wallets (1 CryptoHouse query) | `a04_cluster_prices`, `a04_cluster_eval` |
| `a05_stage3_market_gap.py` | Gamma lookup of stage-3 missing markets; corrected S1/S2/S3; S1 holdout on correct members | `a05_missing_markets`, `a05_screen_fix` |
| `a06_stage3_recompute.py` | independent stage-3 recompute: post-t_res prints, wallet CIs, slippage, ipw, delays | `a06_stage3` |
| `a07_final_tables.py` | tables in this note | `a07_tables.md` |

**Requests made by the audit.**
- CryptoHouse: 2 queries, the CL re-pricing and the contract-owner check.
- Data API: about 250 requests (39 wallet histories, about 200 resolution records).
- Gamma: about 170 requests.

No commit was made.
