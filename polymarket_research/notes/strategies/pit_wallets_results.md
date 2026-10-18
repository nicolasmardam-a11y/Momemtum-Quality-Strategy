# PIT wallet-following: stage 2 results (follower simulation, benchmarks, inference)

- Written 2026-10-18, about 05:15-05:35 UTC. As-of date of the project: 2026-10-17.
- Inputs: stage-1 build (`pit_wallets_build.md`) and the pre-registration (`pit_wallets_preregistration.md`,
  sections 7-11 and addenda A10-A12).
- Scripts: `analyses/pit_wallets/12_signals.py` .. `20_prereg_secondary.py`, with shared helpers in `evalib.py`.
- Result tables: `data/derived/pit_wallets/results/`.
- Labels: **VERIFIED** = computed from the data here or checked against a primary source; **PLAUSIBLE** = consistent
  with the evidence but not directly verified; **UNSUPPORTED** = no evidence.

> **Stage-4 audit (2026-10-18, [corrected by auditor]).** The confirmatory numbers were re-computed from the raw signal
> and print tables with the auditor's own code (`a01_recompute_stage2.py`, no `evalib` import): ROI, fills and event
> counts match to 1e-16 for all 90 (type, screen, split) cells, and the ipw estimator matches within 0.02 point in
> 30 of 31 test cells (0.6 point in F2 S4_politics, 22 events). Three
> corrections, none of which changes a verdict: (1) CL entries were priced from prints that include the cluster's own
> fresh wallets (sections 1-2 below); (2) the +0.01 "tick" is 10 ticks above 0.96 (section 0, item 1); (3) the
> current-fee stress uses the category table, which overstates some markets' fees (section 2). Wallet-clustered CIs
> were added (section 4). Final, audited conclusions: `pit_wallets_FINAL.md`.

## 0. Bottom line

1. **The trader's rule does not survive as a follower strategy.** The rule is to follow wallets with exactly 5 bets
   in the previous 12 months, all won (S1).
   - On the held-out TEST period (selection dates 2025-07..2025-12), at the pre-registered model, a follower loses
     money: **net ROI -7.1%** per dollar staked, 95% event-clustered CI [-10.6%, -3.7%], 3,882 filled signals in
     1,542 events. The model buys the first other-wallet taker print 2 minutes after the wallet's first fill, plus 1
     tick, and holds to resolution.
   - Validation was -4.5% and train -6.1%. Every split is negative with a CI below zero. **VERIFIED.**
   - The reason is visible in the data. S1 wallets buy near-certain favourites: the median own entry price is 0.987.
     They also have no edge of their own in the evaluation window, at -2.3 points per decision (payout minus their own
     first-fill price). The extra tick then costs about 1.1% per trade. [corrected by auditor: +0.01 is ten ticks
     for prices above 0.96, where the tick is 0.001, and 64% of S1's filled entries are above 0.96. With a
     tick-aware +0.001 / +0.01, S1 is -6.6% [-10.4%, -2.7%]; with no slippage at all, -6.0% [-9.5%, -1.8%]. Across
     the three slippage conventions x two fee regimes x drop / ipw (186 test variants, `a01_slippage_sens.parquet`)
     no confirmatory hypothesis has a CI above zero.]
2. **All 28 pre-registered hypotheses are rejected.** The family is 9 screens x {new decision, large bet, returning
   wallet} plus the fresh-wallet cluster signal.
   - 27 of 28 have negative test ROI. None beats both benchmark B1 (random eligible wallets) and B2 (price/category-
     matched market prints) after Holm; every Holm-adjusted p = 1.00.
   - The best point estimates are not robust: large-bet S4-sports (+3.0%, CI [-4.0%, +11.3%], P&L concentrated, and
     -4.4% on validation) and the cluster signal (-0.7%, CI [-6.2%, +5.4%]). **VERIFIED.**
3. **Better screens did not produce a follower edge either.**
   - The "skill" screens (S3, S4) and the naive top-1% P&L screen (S5) do pick wallets whose OWN entries had positive
     edge in the evaluation window: +0.6 to +7.6 probability points.
   - At the follower's price 2 minutes later that edge is gone: -0.2 to +0.2 points. Test ROI is -1.8% (S5) to
     -7.8% (S3), and it is still negative at a 5-second delay. **VERIFIED.**
   - The information is in the price before a follower can act. The wallets' prices are not available to a follower.
4. **A trap in the execution proxy, found and quantified.** If a signal is "filled" only when other wallets' taker
   prints follow it, the fill depends on what the market does next.
   - For $500-$10,000 fills, winners fill up to 3x as often as losers. That makes even RANDOM wallets look profitable:
     B1 shows +5.6% to +15.7% on the test split.
   - Outcome-neutral estimators remove this. Under both, every P screen is negative at every size. Portfolio
     simulations show the same (section 8). **VERIFIED.**
   - Any copy-trading backtest that drops "unfilled" signals this way will show spurious profits. **PLAUSIBLE**, as a
     general statement.
5. **Exploratory grid.** It covers 10,200 variants: signal type x screen x delay x size x slippage x fee x exit.
   - In the outcome-neutral estimators no variant survives Holm or the reality check in the test split (section 7).
     Under ipw, 1 of 8,526 testable variants has a CI above zero.
   - With the pre-registered drop-unfilled rule, 84 variants pass Holm. All are P signals at VWAP sizes of $500 or
     more, i.e. fill-selection artefacts: 208 B1 random-wallet variants also have CIs above zero.
6. **Verdict: no demonstrated edge** for following PIT-selected Polymarket wallets with public on-chain data at
   realistic delays. This covers the trader's 5-for-5 rule and the better screens. **VERIFIED** for this data
   (pre-V2 exchange, 2024-2025). Not tested: 2026 Protocol V2, live order books, maker execution.

Test-split summary at the pre-registered model (first print >= 2 min after the signal + 0.01, $100, hold, historical fee 0):

| signal | train ROI | val ROI | TEST ROI [95% event CI] | test ROI ipw / adv | test filled / events | mean follower px | hit rate |
|---|---|---|---|---|---|---|---|
| P S1 | -6.1% | -4.5% | -7.1% [-10.6%, -3.7%] | -6.9% / -9.4% | 3,882 / 1,542 | 0.86 | 0.84 |
| P S1m | -5.8% | -4.7% | -7.4% [-11.6%, -3.7%] | -7.3% / -9.9% | 4,374 / 1,355 | 0.86 | 0.84 |
| P S2 | -4.0% | -1.6% | -3.2% [-4.5%, -2.0%] | -3.6% / -5.3% | 6,205 / 2,147 | 0.92 | 0.92 |
| P S3 | -5.4% | -4.1% | -7.8% [-11.1%, -4.4%] | -8.5% / -16.9% | 5,760 / 5,269 | 0.53 | 0.52 |
| P S4_sports | -5.0% | -6.9% | -4.9% [-8.4%, -1.1%] | -5.9% / -21.0% | 5,637 / 3,669 | 0.52 | 0.52 |
| P S4_politics | -2.7% | -2.4% | -6.0% [-13.4%, +2.8%] | -9.7% / -30.1% | 4,652 / 1,116 | 0.53 | 0.54 |
| P S4_crypto | -27.1% | -1.6% | -5.1% [-8.5%, -1.3%] | -6.1% / -9.6% | 6,141 / 5,436 | 0.54 | 0.54 |
| P S4_other | +2.8% | -11.8% | -2.9% [-12.0%, +7.4%] | -8.8% / -42.6% | 2,255 / 1,024 | 0.52 | 0.53 |
| P S5 | -5.7% | -1.3% | -1.8% [-5.1%, +1.5%] | -2.5% / -9.0% | 6,045 / 5,517 | 0.55 | 0.55 |
| F1 S4_sports | -5.0% | -4.4% | +3.0% [-4.0%, +11.3%] | +1.5% / -3.8% | 1,402 / 1,214 | 0.61 | 0.62 |
| CL CL | -6.7% | -10.4% | -0.7% [-6.2%, +5.4%] | -0.5% / -4.3% | 295 / 183 | 0.76 | 0.78 |
| P B1_random_eligible | -7.1% | -3.1% | -4.7% [-7.5%, -1.8%] | -6.4% / -13.1% | 5,777 / 4,555 | 0.60 | 0.60 |

## 1. What was run, and deviations

- **Followed set.** Fixed at each selection date D (first of the month, 2024-01..2025-12) from the stage-1 screens.
  - S1: 5 resolved decisions, all won.
  - S1m: 5 resolved and event-complete decisions, all made money.
  - S2: >=5 decisions and no outcome loss.
  - S3: shrunken-edge skill z >= 2 with >= 10 decisions.
  - S4_<cat>: S3 within one category.
  - S5: top 1% of trailing P&L.
  - B1: a 1% random sample of wallets with >= 5 resolved decisions.
  - Only data timestamped before D is used, and a decision counts toward a record only if its market resolved before
    D (stage 1, VERIFIED by a 39/39 audit).
- **Signals** (A10). Signal time is the wallet's first fill.
  - **P**: each new decision (entry episode) in the month after D.
  - **F1**: pre-registered "large bet", 10-minute buys >= 5x the wallet's own median. Signal time t0 + 10 min,
    because only then is it knowable.
  - **F1b**: exploratory large bet, first-second $ >= 5x median, known at t0.
  - **F2**: returning after >= 60 days with no active day.
  - **ADD**: every add-on buy (fill-second) of the fill-export sub-sample.
  - **CL**: fresh-wallet cluster, >= 3 brand-new wallets buying the same token for >= $20k within 60 minutes.
- **Pricing sample.** The CryptoHouse quota is 120 queries/hour, so pricing uses a hash sample (A10), not outcomes:
  - per (split, screen, type), at most 8,000 P, 2,000 F1 and 2,000 ADD signals;
  - F2 and CL in full;
  - 242,431 distinct (token, time, wallet) rows priced.
  - Sample rates are in `sig_sample_counts.parquet`. Within a cell all signals have equal weight.
- **Signals priced.** Underlying events: train 5,443, validation 9,269, test 26,566.
  - 15 signals were dropped for a missing resolution time.
  - Signals detected after the resolution-known time count as unfilled. 1,541 of these are F1 signals in 15-minute
    crypto markets that resolved inside the 10-minute knowability lag.
- **Deviations and post-hoc steps.** All are logged as dated addenda, and none changes a pre-registered rule.
  - A10 was written before any follower price was computed.
  - **A11** (outcome-dependent fills) and **A12** (estimator repair, Holm family) are **post hoc**. They were written
    after the confirmatory test results were seen and serve only as robustness checks. The 28 confirmatory verdicts
    come from the pre-registered rule.
  - The every-fill (ADD) export is capped at 1,000 buys per wallet-month (A9, stage 1).
- **CryptoHouse use in stage 2.** About 85 queries:
  - follower prints 50;
  - benchmark prints 27, including 13 that returned nothing because of a month-start bug, fixed and re-run;
  - followed-wallet sells 3;
  - exit prints 2.
- **Other sources.** 25 Data API `/v2/trades` calls (spot check) and one FRED download.

## 2. Execution proxy, fees, T-bill

- **Follower entry** (historical order books do not exist).
  - The follower buys the same token from taker BUY prints by other wallets. A taker BUY print is an `orders_filled`
    row whose `taker` is an exchange contract and whose order paid collateral. Price = collateral / shares.
  - Detection delays: 5 s, 30 s, 2 min, 10 min, 15 min, 60 min, and an hourly poll (next full UTC hour).
  - Models:
    - `fp` (pre-registered): the first print within 60 minutes of detection, + 0.01;
    - `vX` (stage-2 brief): the VWAP of prints in [detection, +30 min) accumulated to $X, for X = $100, $500,
      $2,500 or $10,000; otherwise unfilled.
  - Sensitivities add 0.5 and 1 cent of slippage. Prices are capped at 0.999.
  - **Taker prints show prices that traded, not the book.** The follower would compete with these takers for the same
    asks. For large sizes the VWAP may understate cost (no depth information) or overstate it (it buys over 30
    minutes while the price moves). This is an exploratory proxy.
  - [corrected by auditor] For CL signals no wallet was excluded (A10, "cluster signals: no exclusion"), although
    pre-registration sections 7 and 12 say prices paid by the followed wallets are never used. At the 2-minute delay
    41% of CL first prints were buys by the cluster's own fresh wallets. Re-priced without any fresh wallet whose
    first decision is on that token (`a04_cluster_selfprints.py`, one CryptoHouse query): test -0.8% [-6.6%, +5.8%]
    (282 filled, 180 events) instead of -0.7%; validation -15.2% instead of -10.4%; train -7.5%. Verdict unchanged.
- **Spot check (VERIFIED).** 25 hash-chosen P signals in small markets were re-derived independently from the Data API
  taker tape (`/v2/trades?condition=`).
  - Fill status agreed 25/25; the time from detection to the first print was identical 18/18.
  - The price agreed within 0.5 cent in 17/18. The one difference was two prints in the same second, ordered
    differently (0.71 vs 0.67).
  - Script `16_spotcheck_follower.py`, output `spotcheck_follower.parquet`.
- **Fees.**
  - (a) Regime in force: the on-chain `fee` field of `orders_filled` is zero on every fill from 2025-04 to the end of
    the data (2026-01-05). In 2024 it is non-zero on 5-1,889 fills per quarter, out of 0.36M-48M (<= 0.02%), so the
    historical fee is taken as 0 (`fee_field_by_quarter.parquet`, **VERIFIED**).
  - (b) Prospective case: the current taker schedule fee = shares x rate x p(1-p), with rate 0.07 crypto, 0.05
    sports, 0.04 politics and 0.05 other (`pmr.fees`, CONTEXT.md). This costs a buyer rate x (1 - p) per dollar
    staked. The exit variant also pays the fee on the sale.
    [corrected by auditor: the category table overstates today's per-market fee for sports markets on
    `sports_fees_v2` (0.03), fee-free geopolitics markets inside "politics", and finance/tech/mentions markets
    (0.04) inside "other" (0.05), so this stress case is slightly pessimistic. It cannot hide an edge: every
    hypothesis already fails at fee 0, and any taker rebate (at most 50% of the fee) lies between the two cases.]
- **Cash benchmark (iv).** 3-month T-bill, FRED series DTB3 (secondary-market discount rate), downloaded 2026-10-18
  04:57 UTC to `data/raw/fred/DTB3.csv`.
  - Mean rate: 5.24% in 2024H1, 4.70% in 2024H2, 4.22% in 2025H1 and 3.92% in 2025H2.
  - It is accrued simple-interest over each signal's holding period, from entry to t_res.
  - Holding periods are short: the median for P signals is 0.01-5 days by screen. So the T-bill return per signal
    is only 0.0-0.3%, and it changes no conclusion.

## 3. The fill-selection trap (A11; VERIFIED; post-hoc diagnostic)

- Whether other wallets' taker BUY prints follow a signal depends on what happens next.
  - A token that is about to win attracts buyers.
  - A token near expiry that is clearly winning has no sellers below 0.99.
  - A collapsing token attracts lottery buyers.
- Test split, P signals, 2-minute delay. Fill rate among winners / losers:

| model | B1 random | S1 | S3 | S4_crypto | S5 |
|---|---|---|---|---|---|
| first print (fp) | 0.78 / 0.81 | 0.82 / 0.87 | 0.72 / 0.81 | 0.78 / 0.90 | 0.72 / 0.85 |
| VWAP $500 | 0.45 / 0.36 | 0.38 / 0.37 | 0.56 / 0.41 | 0.67 / 0.50 | 0.50 / 0.43 |
| VWAP $2,500 | 0.25 / 0.16 | 0.19 / 0.19 | 0.34 / 0.18 | 0.42 / 0.21 | 0.29 / 0.19 |
| VWAP $10,000 | 0.10 / 0.05 | 0.07 / 0.08 | 0.10 / 0.04 | 0.13 / 0.04 | 0.09 / 0.06 |

- Dropping unfilled signals therefore inflates large-size results and slightly deflates first-print results.
  - Test ROI at $2,500 with unfilled dropped: B1 +9.7%, S3 +11.6%, S4_crypto +14.1%, S5 +9.4%.
  - With the first-print model, those same signals give -5% to -8%.
  - On the subset that filled at $2,500, the first-print price returns +17% to +33%. The subset, not the price, makes
    the profit.
- Estimators used from here on (`evalib.est_vectors`):
  - **drop**: pre-registered, unfilled signals are excluded.
  - **ipw**: the "always filled" counterfactual. Every feasible loser loses its stake whatever its price. Winners are
    reweighted by the inverse fill rate within the followed wallet's own-price bucket, which is known at the signal.
  - **adv**: adverse-fill bound. Unfilled losers are filled and lose; unfilled winners are not filled.
  - For path simulations, **bal**: filled signals are thinned at random within (set x own-price bucket) so winners and
    losers have equal fill rates.
- The truth for a real follower is probably between ipw and adv (**PLAUSIBLE**). A marketable order almost always
  finds an ask on a losing token, but may not find one on a near-certain winner.

## 4. Confirmatory test (pre-registered model; sections 7-11)

The model: first other-wallet taker print >= 2 minutes after the signal, + 0.01; $100 per signal; hold to resolution;
historical fee 0. CIs: 95% percentile bootstrap, 2,000 resamples, clustered by underlying event; calendar-week CIs
are in `confirmatory.parquet`.

Test split (2025-07..2025-12 selection dates), all pre-registered hypotheses plus B1:

| type | screen | signals | fill | events | net ROI | 95% CI (event) | 95% CI (week) | B1 | p vs B1 | B2 | p vs B2 | Holm | ipw ROI | adv ROI | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P | S1 | 4,704 | 0.83 | 1,542 | -7.1% | [-10.6%, -3.7%] | [-10.5%, -2.1%] | -4.7% | 0.86 | -2.8% | 1.00 | 1.00 | -6.9% | -9.4% | rejected |
| P | S1m | 5,305 | 0.82 | 1,355 | -7.4% | [-11.6%, -3.7%] | [-11.5%, -2.4%] | -4.7% | 0.86 | -2.4% | 0.99 | 1.00 | -7.3% | -9.9% | rejected |
| P | S2 | 7,891 | 0.79 | 2,147 | -3.2% | [-4.5%, -2.0%] | [-4.3%, -2.2%] | -4.7% | 0.15 | -1.7% | 0.99 | 1.00 | -3.6% | -5.3% | rejected |
| P | S3 | 7,965 | 0.72 | 5,269 | -7.8% | [-11.1%, -4.4%] | [-11.1%, -3.9%] | -4.7% | 0.92 | -6.9% | 0.69 | 1.00 | -8.5% | -16.9% | rejected |
| P | S4_sports | 8,112 | 0.69 | 3,669 | -4.9% | [-8.4%, -1.1%] | [-7.5%, -1.5%] | -4.7% | 0.53 | -6.7% | 0.16 | 1.00 | -5.9% | -21.0% | rejected |
| P | S4_politics | 8,063 | 0.58 | 1,116 | -6.0% | [-13.4%, +2.8%] | [-14.1%, +2.7%] | -4.7% | 0.60 | -15.0% | 0.02 | 1.00 | -9.7% | -30.1% | rejected |
| P | S4_crypto | 7,885 | 0.78 | 5,436 | -5.1% | [-8.5%, -1.3%] | [-8.8%, -1.3%] | -4.7% | 0.56 | -5.8% | 0.35 | 1.00 | -6.1% | -9.6% | rejected |
| P | S4_other | 5,245 | 0.43 | 1,024 | -2.9% | [-12.0%, +7.4%] | [-14.3%, +11.0%] | -4.7% | 0.34 | -20.3% | 0.00 | 1.00 | -8.8% | -42.6% | rejected |
| P | S5 | 7,960 | 0.76 | 5,517 | -1.8% | [-5.1%, +1.5%] | [-5.1%, +1.0%] | -4.7% | 0.10 | -5.2% | 0.03 | 1.00 | -2.5% | -9.0% | rejected |
| P | B1_random_eligible | 8,077 | 0.72 | 4,555 | -4.7% | [-7.5%, -1.8%] | [-7.6%, -1.6%] |  |  |  |  |  | -6.4% | -13.1% | benchmark |
| F1 | S1 | 408 | 0.84 | 169 | -5.1% | [-10.3%, -0.9%] | [-9.6%, +0.7%] | -2.7% | 0.77 | -1.7% | 0.93 | 1.00 | -5.5% | -7.3% | rejected |
| F1 | S1m | 656 | 0.75 | 238 | -0.2% | [-4.1%, +3.9%] | [-3.6%, +3.6%] | -2.7% | 0.22 | -1.8% | 0.17 | 1.00 | -0.7% | -1.8% | rejected |
| F1 | S2 | 649 | 0.75 | 279 | -1.9% | [-5.7%, +2.4%] | [-4.4%, +0.9%] | -2.7% | 0.41 | -1.0% | 0.67 | 1.00 | -2.0% | -4.6% | rejected |
| F1 | S3 | 1,995 | 0.53 | 1,032 | -14.7% | [-20.6%, -8.4%] | [-18.9%, -9.0%] | -2.7% | 1.00 | -8.0% | 0.99 | 1.00 | -8.8% | -18.5% | rejected |
| F1 | S4_sports | 1,962 | 0.71 | 1,214 | +3.0% | [-4.0%, +11.3%] | [-2.2%, +8.5%] | -2.7% | 0.11 | -4.3% | 0.04 | 1.00 | +1.5% | -3.8% | rejected |
| F1 | S4_politics | 1,252 | 0.69 | 424 | -4.8% | [-10.8%, +1.5%] | [-10.1%, +0.4%] | -2.7% | 0.71 | -5.7% | 0.39 | 1.00 | -3.0% | -10.8% | rejected |
| F1 | S4_crypto | 1,950 | 0.47 | 890 | -16.5% | [-23.2%, -9.4%] | [-22.6%, -8.5%] | -2.7% | 1.00 | -10.0% | 0.98 | 1.00 | -11.0% | -19.8% | rejected |
| F1 | S4_other | 484 | 0.51 | 192 | -0.8% | [-11.7%, +11.7%] | [-13.5%, +12.5%] | -2.7% | 0.37 | -5.8% | 0.22 | 1.00 | +0.1% | -14.4% | rejected |
| F1 | S5 | 1,945 | 0.68 | 1,226 | -4.6% | [-10.5%, +2.2%] | [-9.0%, +0.1%] | -2.7% | 0.68 | -5.3% | 0.39 | 1.00 | -1.7% | -8.9% | rejected |
| F1 | B1_random_eligible | 2,009 | 0.69 | 1,206 | -2.7% | [-7.5%, +2.1%] | [-7.3%, +2.5%] |  |  |  |  |  | -1.7% | -5.7% | benchmark |
| F2 | S1 | 487 | 0.84 | 159 | -2.2% | [-9.7%, +4.6%] | [-9.5%, +4.4%] | -7.2% | 0.20 | -1.3% | 0.62 | 1.00 | -3.7% | -5.5% | rejected |
| F2 | S1m | 669 | 0.80 | 208 | -5.0% | [-10.5%, -0.7%] | [-9.9%, -1.1%] | -7.2% | 0.33 | -1.7% | 0.91 | 1.00 | -5.8% | -8.9% | rejected |
| F2 | S2 | 557 | 0.83 | 192 | -9.5% | [-15.4%, -4.6%] | [-13.4%, -5.7%] | -7.2% | 0.70 | -3.7% | 1.00 | 1.00 | -9.8% | -12.2% | rejected |
| F2 | S3 | 514 | 0.78 | 334 | -9.5% | [-19.7%, +0.3%] | [-22.6%, +3.1%] | -7.2% | 0.63 | -5.2% | 0.80 | 1.00 | -13.0% | -20.5% | rejected |
| F2 | S4_sports | 208 | 0.84 | 131 | -13.0% | [-31.2%, +5.4%] | [-34.1%, +8.4%] | -7.2% | 0.70 | -2.9% | 0.86 | 1.00 | -12.5% | -20.3% | rejected |
| F2 | S4_politics | 49 | 0.47 | 22 | -56.3% | [-92.3%, -7.2%] | [-100.0%, -6.2%] | -7.2% | 1.00 | -35.6% | 0.82 | 1.00 | -36.8% | -76.1% | rejected |
| F2 | S4_crypto | 142 | 0.65 | 93 | -8.8% | [-27.1%, +9.7%] | [-32.0%, +2.9%] | -7.2% | 0.54 | -4.6% | 0.67 | 1.00 | -16.0% | -25.6% | rejected |
| F2 | S4_other | 2 | 1.00 | 2 | -100.0% | [-100.0%, -100.0%] | [-100.0%, -100.0%] | -7.2% | 1.00 | -42.5% | 1.00 | 1.00 | -100.0% | -100.0% | rejected |
| F2 | S5 | 427 | 0.79 | 256 | -16.2% | [-25.8%, -6.5%] | [-23.8%, -10.5%] | -7.2% | 0.92 | -6.6% | 0.99 | 1.00 | -16.1% | -25.3% | rejected |
| F2 | B1_random_eligible | 545 | 0.80 | 270 | -7.2% | [-15.5%, +1.8%] | [-17.7%, +4.5%] |  |  |  |  |  | -12.0% | -16.3% | benchmark |
| CL | CL | 349 | 0.85 | 183 | -0.7% | [-6.2%, +5.4%] | [-5.4%, +3.7%] | -4.7% | 0.12 | -3.1% | 0.21 | 1.00 | -0.5% | -4.3% | rejected |

- **[auditor addition] Wallet-clustered 95% CIs** (`a01`; many signals come from a few bot wallets): P S1
  [-9.5%, -4.6%], P S2 [-4.4%, -2.1%], P S3 [-12.3%, -3.6%], P S5 [-5.5%, +2.3%], P S4_politics [-11.5%, -0.2%],
  F1 S4_sports [-4.1%, +11.7%], CL [-6.4%, +5.3%]. No verdict changes.
- **Benchmark columns.**
  - **B1** = the same signal type from random eligible wallets.
  - **B2** = mean ROI of all sampled taker BUY prints in the same month, category and price decile, with the same
    +0.01.
  - p-values are one-sided, centred event-bootstrap, for H1: signal > benchmark.
  - Holm runs over the 28 hypotheses, using p = max(p_B1, p_B2) (intersection-union).
- **Robustness.** Under ipw and adv every P screen is negative on test, and the ipw CI excludes zero for all but
  S4_other and S5. F1 S4_sports (ipw +1.5%, CI [-4.0%, +7.9%]) and CL (ipw -0.5%) stay inside noise.
- **Current fee schedule (prospective).** Every P screen loses another 0.4-3.1 points: S1 -7.8%, S3 -10.8%,
  S4_crypto -8.2%, S5 -4.6%. F1 S4_sports falls to +1.1% (CI upper +9.4%, lower bound negative).
- **Outcome-won vs made-money.** When holding to resolution, a follower makes money exactly when the outcome wins
  (entry < 1, fee 0). So the hit rate is the made-money rate: S1 0.84, S2 0.92, S3 0.52, S5 0.55 on test. A high hit
  rate at prices near 0.9-0.99 still loses money, because the follower pays 0.86-0.92 on average plus a tick.
- **Pre-registered secondary metrics** (test, P, $100 per signal; `prereg_secondary.parquet`).
  - Cumulative P&L is negative for every screen: S1 -$27.6k over 3,882 signals; S5 -$11.2k over 6,045.
  - Positive resolution-months: 1-7 of 7-15.
  - Max drawdown is about the whole P&L.
  - Capacity: the share of signals with >= $1,000 of taker-buy volume in the 60 minutes after detection is 0.15
    (S4_other) to 0.66 (S4_crypto).
- **Delay decay (B3, the wallet's own first-fill price; not achievable).** The wallet's own edge versus the follower's
  edge at 2 minutes, in points (test):
  - S3 +1.2 vs -0.2;
  - S4_sports +2.1 vs -0.1;
  - S4_politics +4.7 vs +0.2;
  - S4_other +7.6 vs +0.2;
  - S5 +1.5 vs 0.0;
  - S1 -2.3 vs -2.2.

  Mean ROI at the own price is much higher for low-price buyers (S4_other +122%, S4_politics +72%), because a few
  longshot fills paid 10-100x. That is the price a follower cannot get.

### Rejection criteria (section 11), test split

| criterion | hypotheses failing |
|---|---|
| 1. net ROI <= 0 or 95% CI includes 0 | 28 of 28 |
| 2. not better than B1 and B2 after Holm (p < 0.05) | 28 of 28 |
| 3. < 100 distinct events with filled signals | 3 (F2 S4_politics 22, F2 S4_crypto 93, F2 S4_other 2) |
| 4. > 50% of P&L from the top 1% of signals or one event (positive P&L only) | 1 of 1 positive (F1 S4_sports: top 1% = 273% of P&L, top event = 77%) |
| 5. validation net ROI not > 0 | 25 of 28 (only F1 S1, F1 S1m, F1 S4_other were positive on validation) |

- **Every one of the 28 hypotheses is rejected ("no demonstrated edge").** This covers S1-S5 and S4 x {P, F1, F2}
  and CL. **VERIFIED.**
- The trader's original rule (S1, P) fails criteria 1, 2 and 5.

## 5. Benchmarks for each signal (test, first-print model, 2-minute delay)

| signal | signal ROI | (i) matched random prints | signal - (i) [95% CI] | (ii) favourite 0.70-0.95 | signal - (ii) [95% CI] | B2 cell | (iv) T-bill over holding | median hold (days) | ipw signal - (i) |
|---|---|---|---|---|---|---|---|---|---|
| P S1 | -7.1% | -3.1% | -4.0% [-7.7%, -0.4%] | -1.6% | -5.5% [-9.4%, -1.8%] | -2.8% | +0.21% | 1.93 | -3.9% |
| P S1m | -7.4% | -2.4% | -5.0% [-9.1%, -1.5%] | -1.8% | -5.6% [-10.1%, -1.8%] | -2.4% | +0.16% | 2.11 | -5.0% |
| P S2 | -3.2% | -1.8% | -1.3% [-2.5%, -0.3%] | -1.2% | -2.0% [-3.5%, -0.5%] | -1.7% | +0.16% | 2.32 | -1.7% |
| P S3 | -7.8% | -7.2% | -0.6% [-4.0%, +3.1%] | -2.4% | -5.5% [-9.0%, -1.7%] | -6.9% | +0.01% | 0.07 | -1.8% |
| P S4_sports | -4.9% | -5.4% | +0.5% [-2.9%, +4.3%] | -2.6% | -2.2% [-5.6%, +1.5%] | -6.7% | +0.01% | 0.22 | -0.5% |
| P S4_politics | -6.0% | -14.8% | +8.8% [+1.4%, +17.2%] | +2.5% | -8.5% [-16.1%, -0.0%] | -15.0% | +0.26% | 5.00 | +5.0% |
| P S4_crypto | -5.1% | -6.2% | +1.1% [-2.4%, +5.0%] | -2.5% | -2.6% [-6.0%, +1.4%] | -5.8% | +0.00% | 0.01 | -0.4% |
| P S4_other | -2.9% | -16.2% | +13.4% [+4.3%, +23.7%] | +2.1% | -5.0% [-13.6%, +4.1%] | -20.3% | +0.13% | 1.05 | +8.1% |
| P S5 | -1.8% | -5.4% | +3.5% [+0.2%, +6.9%] | -2.2% | +0.3% [-2.9%, +3.6%] | -5.2% | +0.02% | 0.08 | +2.4% |
| P B1_random_eligible | -4.7% | -4.6% | -0.1% [-2.9%, +2.8%] | -2.0% | -2.7% [-5.5%, +0.1%] | -5.0% | +0.07% | 0.23 | -1.9% |
| F1 S4_sports | +3.0% | -4.3% | +7.3% [-0.2%, +16.4%] | -2.6% | +5.6% [-1.7%, +14.4%] | -4.3% | +0.01% | 0.21 | +5.3% |
| CL CL | -0.7% | -2.7% | +1.9% [-4.2%, +8.0%] | -1.6% | +0.9% [-5.4%, +7.2%] | -3.1% | +0.16% | 1.23 | +2.1% |

(iii) is the S5 row.

- **(i) Matched random entries.** Sampled taker BUY prints, about 12,000 a month: 297,072 clean prints in
  2024-01..2026-01. Each is matched on the same category, the same ISO week and a price within 0.05 of the follower
  price, from a different underlying event, with the same +0.01 slippage. Coverage is 100% of signals.
- **(ii) Favourite rule.** Buy prints priced 0.70-0.95 in the same category and week.
- **(iii) Naive profitable wallets.** S5 is in the table.
- **(iv) T-bill.**
- **Reading.**
  - The screens beat random takers only where random takers lose most: S4_politics, S4_other and S5 beat (i) by +8.8,
    +13.4 and +3.5 points, with CIs above zero. Those categories have a strong favourite-longshot loss for takers, so
    the screen's buys are "less bad" than average taker buys.
  - No screen beats cash or zero.
  - S1/S1m/S2 do worse than random entries and than the favourite rule: they buy the most expensive favourites.
  - These comparisons are not multiplicity-adjusted.

## 6. Does the wallet add information beyond the market price?

P signals at the first-print model. d edge = mean(payoff - follower price) minus the same for matched prints, in probability points, with a 95% event-clustered CI. Logit: outcome ~ logit(price) + signal indicator; event-clustered SE; one-sided p for b > 0.

| screen | train: d edge (pts) | train: logit b_signal (SE), p | val: d edge (pts) | val: logit b_signal (SE), p | test: d edge (pts) | test: logit b_signal (SE), p |
|---|---|---|---|---|---|---|
| S1 | -0.7 [-2.0, +0.4] | -0.11 (0.08), 0.91 | -0.5 [-1.4, +0.3] | -0.07 (0.10), 0.74 | -2.2 [-3.9, -0.8] | -0.33 (0.13), 0.99 |
| S1m | -0.5 [-1.8, +0.7] | -0.09 (0.09), 0.85 | -1.0 [-2.1, +0.1] | -0.19 (0.12), 0.93 | -2.2 [-4.2, -0.5] | -0.33 (0.16), 0.98 |
| S2 | -0.2 [-1.1, +0.6] | -0.04 (0.08), 0.71 | -0.5 [-1.2, +0.1] | -0.14 (0.10), 0.92 | -0.3 [-0.9, +0.3] | -0.07 (0.10), 0.75 |
| S3 | +0.4 [-0.8, +1.5] | +0.02 (0.05), 0.38 | -0.3 [-1.5, +1.0] | +0.00 (0.04), 0.46 | +0.2 [-0.9, +1.3] | +0.01 (0.04), 0.38 |
| S4_sports | +0.4 [-1.0, +1.7] | -0.03 (0.07), 0.67 | -0.6 [-1.8, +0.5] | -0.02 (0.04), 0.67 | +0.2 [-0.9, +1.4] | -0.01 (0.04), 0.60 |
| S4_politics | +0.8 [-1.2, +2.9] | +0.01 (0.09), 0.46 | +0.4 [-1.1, +2.0] | +0.02 (0.07), 0.36 | +1.1 [-0.1, +2.1] | +0.07 (0.07), 0.15 |
| S4_crypto | -3.2 [-10.2, +3.4] | -0.21 (0.24), 0.81 | +1.0 [-0.7, +2.7] | +0.05 (0.07), 0.24 | +0.2 [-0.8, +1.3] | +0.02 (0.04), 0.34 |
| S4_other | +0.5 [-8.6, +8.7] | +0.04 (0.37), 0.46 | +1.0 [-1.9, +4.3] | +0.07 (0.15), 0.32 | +2.2 [+0.4, +4.0] | +0.19 (0.11), 0.04 |
| S5 | +0.0 [-1.2, +1.2] | -0.02 (0.05), 0.63 | -0.8 [-1.9, +0.3] | -0.05 (0.04), 0.91 | +0.4 [-0.6, +1.5] | +0.02 (0.04), 0.31 |
| B1_random_eligible | -0.1 [-1.3, +1.2] | -0.03 (0.05), 0.73 | -0.3 [-1.2, +0.7] | -0.02 (0.04), 0.70 | +0.4 [-0.6, +1.5] | +0.03 (0.04), 0.20 |
| CL | -0.4 [-2.7, +1.8] | -0.34 (0.30), 0.87 | -0.6 [-3.7, +2.1] | -0.19 (0.33), 0.72 | +2.2 [-0.5, +5.2] | +0.16 (0.17), 0.18 |

- **Mean (payoff - follower price) for signals minus that of matched prints** (same category, week and +-5 cents).
  - Test: about 0 for every skill screen (-0.3 to +2.2 points).
  - It is significantly negative for S1/S1m: -2.2 points, CI [-3.9, -0.8].
- **Logistic regression** of the outcome on logit(price) plus a signal indicator, on signals and 3 matched prints
  per signal, with event-clustered SEs.
  - The signal coefficient is indistinguishable from 0 for all screens except S4_other on test: b = +0.19, SE 0.11,
    one-sided p = 0.04 unadjusted. It is not significant on validation (p = 0.32) or train (p = 0.46).
  - S1/S1m are negative on test: b = -0.33, one-sided p for b > 0 of 0.98-0.99.
  - Under ipw weights the edge differences are -2.2 to +2.3 points on test and -5.1 to +0.8 on train/validation
    (`dw_edge` in `bench_compare.parquet`).
- **Conclusion (VERIFIED).** Once a follower can see the trade, the market price already contains whatever the
  followed wallet knew. The one nominal exception, S4_other on test, does not replicate on validation and does not
  survive any multiplicity adjustment.

## 7. Exploratory grid and multiple testing

- **Variants.** 10,200 test-split variants per estimator: 46 signal sets (5 types x 9 screens + CL) x 7 delays x 5 entry models x 3 slippages x 2 fee regimes, plus exit-on-sell variants for P and F1b. 9,978 have at least one filled signal; 8,526 have >= 30 filled events (the multiple-testing family, A12). Each variant has an event-clustered Poisson bootstrap (1,000 draws, shared across variants).

| estimator | test variants ROI > 0 | B1 variants ROI > 0 | raw p < 0.05 | Holm p < 0.05 | best test variant (studentized) | reality-check p (studentized / raw) | best on validation -> its test ROI [CI] |
|---|---|---|---|---|---|---|---|
| drop | 44% | 74% | 576 | 84 | P S4_crypto d=30 v2500 slip=0.0 hist: +13.5% (2499 ev) | 0.001 / 0.451 | ADD S4_crypto d=5 v10000: val +25.6% -> test +17.0% [+7.4%, +25.8%] |
| ipw | 7% | 13% | 3 | 0 | F1b S3 d=120 v100 slip=0.0 hist exit: +10.4% (217 ev) | 1.000 / 0.986 | F1 S1m d=120 fp: val +9.0% -> test -0.7% [-4.2%, +2.4%] |
| adv | 0% | 0% | 0 | 0 | F1b S3 d=5 fp slip=0.0 hist: +15.4% (355 ev) | 1.000 / 0.806 | F1 S1m d=5 fp: val +7.4% -> test -1.8% [-6.2%, +2.0%] |

**Delay decay** (P, first-print model + 0.01, hold, historical fee, ipw, test): ROI by detection delay (seconds; poll = next full hour)

| screen | 5 | 30 | 120 | 600 | 900 | 3600 | poll |
|---|---|---|---|---|---|---|---|
| B1_random_eligible | -6.3% | -6.3% | -6.4% | -7.7% | -8.2% | -8.8% | -9.3% |
| S1 | -7.6% | -7.6% | -6.9% | -7.3% | -7.8% | -7.9% | -6.9% |
| S1m | -7.4% | -7.4% | -7.3% | -7.4% | -7.6% | -7.5% | -7.5% |
| S2 | -3.5% | -3.4% | -3.6% | -4.2% | -3.9% | -4.2% | -3.1% |
| S3 | -7.1% | -7.8% | -8.5% | -10.4% | -8.3% | -11.6% | -12.5% |
| S4_crypto | -6.8% | -6.6% | -6.1% | -11.3% | -8.0% | -20.5% | -13.6% |
| S4_other | -8.2% | -7.3% | -8.8% | -7.6% | -6.5% | -11.8% | -8.6% |
| S4_politics | -9.8% | -9.9% | -9.7% | -10.8% | -11.5% | -13.8% | -12.5% |
| S4_sports | -1.1% | -5.8% | -5.9% | -6.7% | -6.9% | -10.2% | -7.0% |
| S5 | -1.7% | -2.0% | -2.5% | -3.7% | -3.7% | -5.5% | -5.9% |

**Size** (P, 2-minute delay, no extra slippage, historical fee, test): ROI drop / ipw / adv

| screen | fp drop / ipw / adv | v100 drop / ipw / adv | v500 drop / ipw / adv | v2500 drop / ipw / adv | v10000 drop / ipw / adv |
|---|---|---|---|---|---|
| B1_random_eligible | -5% / -6% / -13% | +3% / -6% / -24% | +6% / -8% / -34% | +10% / -12% / -57% | +16% / -15% / -79% |
| S1 | -7% / -7% / -9% | -6% / -7% / -17% | -5% / -8% / -25% | -4% / -8% / -42% | -5% / -9% / -68% |
| S1m | -7% / -7% / -10% | -8% / -7% / -17% | -7% / -7% / -24% | -4% / -7% / -40% | -8% / -7% / -64% |
| S2 | -3% / -4% / -5% | -0% / -3% / -9% | -0% / -3% / -14% | +1% / -2% / -22% | +1% / -2% / -43% |
| S3 | -8% / -9% / -17% | +2% / -8% / -22% | +6% / -13% / -31% | +12% / -18% / -52% | +14% / -22% / -83% |
| S4_crypto | -5% / -6% / -10% | +2% / -7% / -13% | +7% / -13% / -21% | +14% / -18% / -43% | +17% / -23% / -78% |
| S4_other | -3% / -9% / -43% | +4% / -24% / -80% | +7% / -26% / -89% | +7% / -34% / -95% | +4% / -40% / -98% |
| S4_politics | -6% / -10% / -30% | +3% / -14% / -58% | +8% / -14% / -70% | +7% / -17% / -84% | +9% / -14% / -93% |
| S4_sports | -5% / -6% / -21% | +2% / -3% / -36% | +4% / -4% / -48% | +4% / -8% / -66% | +5% / -12% / -84% |
| S5 | -2% / -2% / -9% | +6% / -2% / -17% | +7% / -8% / -28% | +9% / -12% / -53% | +8% / -12% / -82% |

**Exit when the followed wallet sells** (P, first print, 2 min, ipw, test), ROI hold -> exit: B1_random_eligible -6.4% -> -6.8%, S1 -6.9% -> -5.5%, S1m -7.3% -> -5.9%, S2 -3.6% -> -3.3%, S3 -8.5% -> -8.9%, S4_crypto -6.1% -> -6.3%, S4_other -8.8% -> -11.5%, S4_politics -9.7% -> -9.7%, S4_sports -5.9% -> -6.1%, S5 -2.5% -> -2.9%

**Slippage / fee** (P, first print, 2 min, ipw, test), ROI at +0 / +0.5 / +1 cent extra; historical | current fee: B1_random_eligible -6.4% / -7.3% / -8.2% | -8.6% / -9.5% / -10.4%; S1 -6.9% / -7.3% / -7.6% | -7.6% / -8.0% / -8.3%; S1m -7.3% / -7.6% / -7.9% | -8.0% / -8.3% / -8.5%; S2 -3.6% / -3.8% / -4.0% | -4.0% / -4.2% / -4.4%; S3 -8.5% / -9.7% / -10.8% | -11.3% / -12.4% / -13.5%; S4_crypto -6.1% / -7.4% / -8.6% | -8.9% / -10.2% / -11.4%; S4_other -8.8% / -10.8% / -12.5% | -11.2% / -13.1% / -14.9%; S4_politics -9.7% / -11.7% / -13.3% | -11.5% / -13.4% / -15.0%; S4_sports -5.9% / -7.2% / -8.4% | -8.2% / -9.4% / -10.6%; S5 -2.5% / -3.6% / -4.7% | -4.9% / -6.1% / -7.1%

**Other exploratory signal types** (first print, 2 min, ipw): ROI by split

| signal | train | val | test |
|---|---|---|---|
| ADD S1 | +25.4% | -22.9% | -30.8% |
| ADD S1m | +12.1% | -3.0% | -37.0% |
| ADD S2 | -0.8% | -9.1% | -10.3% |
| ADD S3 | -21.6% | -8.9% | +4.8% |
| ADD S4_crypto | -30.5% | -14.8% | -7.7% |
| ADD S4_other | +42.9% | -5.9% | -25.0% |
| ADD S4_politics | -17.6% | -21.1% | -10.6% |
| ADD S4_sports | -11.2% | -8.2% | +0.6% |
| ADD S5 | -26.1% | -11.7% | -3.7% |
| F1b S1 | -11.2% | -0.8% | -5.0% |
| F1b S1m | -14.1% | +0.5% | -1.7% |
| F1b S2 | -3.3% | -1.2% | -2.1% |
| F1b S3 | -5.9% | -0.7% | +6.8% |
| F1b S4_crypto | -28.1% | -3.6% | +3.3% |
| F1b S4_other | -7.8% | +9.1% | -1.8% |
| F1b S4_politics | -5.8% | -0.3% | +5.9% |
| F1b S4_sports | -3.7% | -2.4% | -1.3% |
| F1b S5 | -5.6% | -4.9% | +6.1% |

**Reading (VERIFIED).**
- **drop.** 84 variants pass Holm on test, all of them P signals with VWAP fills of $500-$10,000. Their profits come
  from the fill rule (section 3): 208 of the 1,068 testable B1 random-wallet variants also have CIs above zero.
  - The drop reality check is "significant" (p = 0.001), with best variant P S4_crypto, 30 s, $2,500, +13.5%. In
    that variant winners fill 46% of the time and losers 23%.
  - The drop variant chosen on validation (ADD S4_crypto, 5 s, $10,000) scores +17% on test for the same reason:
    winners fill 17% of the time and losers 1.6%.
- **ipw.** 0 Holm survivors. 3 of 8,526 variants have a raw p < 0.05, far fewer than the ~430 expected under a global
  null of zero ROI, because almost all variants are negative.
  - Only 1 variant has a CI above zero: F1b S3, $100 VWAP, 2 min, exit when the wallet sells, +10.4% [+0.3%,
    +24.6%], 217 events. Its reality-check p is 1.00. That is what one lucky variant among thousands looks like.
  - The variant chosen on validation (F1 S1m, first print, 2 min: +9.0% on validation) gives -0.7% [-4.2%, +2.4%] on
    test.
- **adv.** No variant has ROI > 0 with a CI above zero; 0.5% of variants have ROI > 0.
- **Delay.** Shorter delays do not rescue any screen. At 5 seconds the ipw ROI is -1.1% (S4_sports) to -9.8%
  (S4_politics). Longer delays and hourly polling are worse, especially for 15-minute crypto markets: S4_crypto -20.5%
  at 60 min.
- **F1b (exploratory large first-second bets).** At the first-print model, ipw test ROI is positive for S3 (+6.8%),
  S5 (+6.1%), S4_politics (+5.9%) and S4_crypto (+3.3%). The same cells are negative in train and validation (-0.3%
  to -28%), and no F1b variant survives Holm or the reality check. This is not evidence of an edge. If anything, it
  is a candidate for a fresh pre-registered test on post-2025 data.
- **Exit when the followed wallet sells.** It changes ROI by -3 to +1.4 points and never turns a screen positive.
  It helps most for S1/S1m, which hold 0.99 favourites (about -6.9% -> -5.5%).
- **Slippage and fees.** Each extra half-cent costs about 0.2-2 points. The current fee schedule costs another 0.4-3
  points.

## 8. Portfolio accounting (test split, P signals)

- **Rules (A10).**
  - Accounts $5k / $25k / $100k. Stake 2% of the initial account: $100 / $500 / $2,000, at the 2-minute VWAP for
    $100 / $500 / $2,500.
  - At most 5% of the account per underlying event, at most 100% deployed.
  - Signals are taken in time order; a signal without free cash is skipped and counted.
  - Capital is locked until t_res.
  - Equity = cash + cost of open positions. There is no mark-to-market (no book), so drawdowns are realised at
    resolution.
  - The stream is the sampled signal stream. Sample rates by screen: 1.0 for S1/S1m/S2/S4_other, 0.75 S4_politics,
    0.36 B1, 0.09 S4_sports, 0.04 S5, 0.025 S4_crypto, 0.017 S3. So for the large screens the run means "follow a
    random 2-9% of the screen's signals".
  - Nothing is annualised: the window is 6 months, and capital stays locked for up to 244 days after it.

| screen | $5k drop / bal / adv: ROI on deployed | $25k drop / bal / adv: ROI on deployed | $25k return on committed: drop / bal | $25k max DD drop / bal | $25k trades taken (drop) | $25k skipped cash / event cap (drop) | $100k drop / bal / adv: ROI on deployed |
|---|---|---|---|---|---|---|---|
| S1 | +1% / +2% / -28% | +0% / -0% / -46% | +4% / -1% | 36% / 28% | 838 | 325 / 606 | -0% / -4% / -65% |
| S1m | -2% / -1% / -32% | -4% / -3% / -52% | -40% / -32% | 44% / 36% | 537 | 808 / 731 | -0% / -3% / -70% |
| S2 | -1% / -2% / -17% | +0% / -0% / -36% | +14% / -6% | 20% / 39% | 1,467 | 166 / 1,336 | +2% / +1% / -46% |
| S3 | +2% / -11% / -30% | +6% / -12% / -42% | +452% / -98% | 33% / 99% | 3,711 | 0 / 23 | +11% / -22% / -58% |
| S4_sports | +1% / -3% / -33% | +4% / -5% / -43% | +189% / -99% | 29% / 99% | 2,561 | 0 / 174 | +5% / -7% / -61% |
| S4_politics | -11% / -14% / -73% | +5% / -16% / -91% | +56% / -78% | 35% / 78% | 604 | 217 / 471 | +1% / -10% / -98% |
| S4_crypto | +2% / -13% / -15% | +7% / -22% / -28% | +592% / -99% | 27% / 99% | 4,396 | 0 / 50 | +14% / -29% / -52% |
| S4_other | +11% / -24% / -81% | +13% / -27% / -88% | +67% / -57% | 12% / 57% | 254 | 0 / 52 | +6% / -41% / -92% |
| S5 | +6% / -5% / -22% | +7% / -8% / -39% | +545% / -95% | 33% / 95% | 3,672 | 0 / 24 | +9% / -22% / -65% |
| B1_random_eligible | +3% / -1% / -36% | +6% / -2% / -53% | +321% / -66% | 25% / 73% | 2,859 | 0 / 170 | +10% / -6% / -73% |

Current fee schedule, bal rule, $25k, ROI on deployed: S1 -0.6%, S1m -2.9%, S2 -0.5%, S3 -17.3%, S4_sports -6.6%, S4_politics -14.5%, S4_crypto -25.0%, S4_other -28.9%, S5 -10.4%, B1_random_eligible -6.7%

- **Reading.**
  - Under the pre-registered fill logic (drop), the fast-turnover screens (S3, S4_crypto, S4_sports, S5) look
    profitable: +1% to +14% on deployed capital. So does B1, the random wallets: +6% on deployed, +321% of a $25k
    account. S3, S4_crypto and S5 reach +450-590% of a $25k account in 6 months, because 15-minute crypto markets
    recycle capital hundreds of times. S1/S1m/S2 are between -4% and +2% on deployed capital.
  - Once fills are made outcome-neutral (bal), every screen loses money on deployed capital except S1 at $5k (+2%)
    and S2 at $100k (+1%). The fast-turnover screens are ruined (-95% to -99% of the account) by compounding a 5-29%
    loss per trade over hundreds to thousands of trades.
  - Under adv every P-screen account loses 15-98% of deployed capital.
  - The +450% figures are therefore an artefact of the fill rule, not something a follower could earn. B1 earns
    them too.
- **Capital use and concentration** ($25k, drop rule).
  - Utilisation over the window: 2% (S4_crypto) to 100% (S4_politics, which reinvests gains).
  - Top-5-event share of absolute P&L: 1-32%.
  - Top wallet's share of stakes: 4-46%. S2 is dominated by one wallet (46%).
  - Category mix: S1/S2/S5/B1 signals are 54-74% crypto.
- **Capacity.**
  - The follower's $500 is a median 11-30% of all taker-buy volume on the token in the 30 minutes after detection.
  - In 31-57% of filled signals it is more than 25% of that volume.
  - At $2,500-$10,000 most signals cannot be filled from subsequent prints at all (section 3).
  - So capacity is a few hundred dollars per signal, even before the edge question. **VERIFIED** as a print-volume
    statement; book depth is UNSUPPORTED.

## 9. Final verdicts

| strategy | verdict | main reasons |
|---|---|---|
| Trader's idea: S1 (5 bets, 5 wins), new decisions | **rejected** | test ROI -7.1% [-10.6, -3.7]; worse than B1, B2 and the favourite rule; S1 wallets buy 0.99 favourites with negative own edge |
| S1m (5 bets, 5 made money) | **rejected** | -7.4% [-11.6, -3.7]; same mechanism |
| S2 (>= 5, no losses) | **rejected** | -3.2% [-4.5, -2.0] |
| S3 skill | **rejected** | -7.8%; own edge +1.2 pts gone at the follower price |
| S4 specialists (sports/politics/crypto/other) | **rejected** | -2.9% to -6.0%; CIs include or are below 0; no Holm survivor |
| S5 naive top-1% P&L | **rejected** | -1.8% [-5.1, +1.5]; not above B1 after Holm |
| F1 large bet (any screen) | **rejected** | best F1 S4_sports +3.0% [-4.0, +11.3], fragile (top 1% > 100% of P&L), validation -4.4% |
| F2 returning (any screen) | **rejected** | all negative; 3 cells inconclusive (< 100 events) |
| CL fresh-wallet cluster | **rejected** | -0.7% [-6.2, +5.4]; validation -10.4% |
| ADD every add-on buy, F1b, exit-on-sell, other delays/sizes (exploratory) | **no demonstrated edge** | section 7 |

## 10. Limitations

- **Proxy, not a book.**
  - No historical order book exists, so entries are priced from later taker prints of other wallets.
  - The fill-selection problem (section 3) means no single estimator is exact. The conclusion holds under all of
    them except the biased pre-registered drop rule at large sizes, where B1 random wallets "profit" by the same
    amount.
- **Pre-V2 only.** Fills end 2026-01-05. Protocol V2 (2026), fee changes and the taker-rebate programme (2026-05) are
  not in the data. The current-fee stress test shows fees would make results worse.
- **Hash samples.** Large screens are evaluated on hash samples: <= 1,000 wallets per date in stage 1, <= 8,000
  signals per split here. CIs reflect this sample, not the full population. Sampling is outcome-blind (VERIFIED by
  construction).
- **t_res.** t_res = Gamma closedTime, conservative (stage 1). Signals detected at or after t_res are unfilled.
- **Exit variant.** It uses the followed wallet's first sale after the follower's first print. Partial sales and
  NegRisk conversions are not modelled.
- **Not evaluated.** Maker (limit-order) following, cross-venue hedging, and wallets identified by off-chain
  information.

## 11. Files

- **Scripts** (`analyses/pit_wallets/`):
  - `12_signals.py`: signal table and pricing sample.
  - `13_follower_prices.py`: follower taker-BUY prints per delay and size (server side).
  - `14_bench_prints.py`: hash sample of taker BUY prints for B2, (i) and (ii).
  - `15_exit_prices.py`: followed-wallet sales and taker-SELL exit prints.
  - `16_spotcheck_follower.py`: Data API cross-check.
  - `evalib.py`: entry/exit/fee models, estimators, bootstrap, Holm.
  - `17_evaluate.py`: confirmatory family, benchmarks, information tests, grid, reality check.
  - `18_portfolio.py`: portfolio accounting.
  - `19_summary.py`, `20_prereg_secondary.py`, `21_note_tables.py`: summaries and this note's tables.
- **Derived data** (`data/derived/pit_wallets/`):
  - `sig_members.parquet`, `sig_pricing.parquet`, `sig_sample_counts.parquet`;
  - `follower_prices.parquet` (194,504 priced rows; rows without any print are unfilled at every delay);
  - `bench_prints.parquet` (299,025 prints), `bench_month_counts.parquet`;
  - `exit_sells.parquet`, `exit_prices.parquet`, `spotcheck_follower.parquet`;
  - `results/`: `confirmatory`, `criteria`, `bench_compare`, `grid` (199,800 rows), `grid_rc.json`, `portfolio`,
    `prereg_secondary`.
- **Raw.** `data/raw/fred/DTB3.csv`. CryptoHouse responses are cached under `data/raw/cryptohouse/`.
- **Deleted.** The per-chunk intermediate files (`follower_chunks/`, `bench_chunks/`, `exit_chunks/`) were removed
  after their merged parquet files were checked row-for-row: 194,504 and 299,025 rows. Re-running the pull scripts
  would hit the CryptoHouse cache.
