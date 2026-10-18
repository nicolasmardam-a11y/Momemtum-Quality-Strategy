# PIT wallet-following: stage 3, 2026 recent-regime holdout (Data API v2)

- Stage 3 of 4. Started 2026-10-18T05:00Z. As-of date of the project: 2026-10-17.
- Pre-registered rules (`pit_wallets_preregistration.md`) are unchanged. This note adds a stage-3 protocol
  (section 1), written before any evaluation-window (2026-06-01 onwards) trade, price or outcome was pulled.
- Scripts: `analyses/pit_wallets/v2_*.py` and `v2common.py`. Data: `data/derived/pit_wallets/v2/`.

## 0. Result in brief

**Verdict: no demonstrated edge in the 2026 regime.** S1, S2, S3 and S5 are all rejected under pre-registration
section 11. This replicates stage 2 (pre-2026 test, historical fees: S1 -7.1%, S2 -3.2%, S3 -7.8%, S5 -1.8%).

**Primary model.**
- A follower buys the first other-wallet taker BUY print >= 2 minutes after the wallet's first fill, + 1 tick, $100,
  with the market's current fee, and holds to resolution.
- Net ROI on the 2026-06..09 decisions of wallets screened on 2026-06-01 (VERIFIED, event-clustered 95% CI):

| screen | net ROI | 95% CI | filled / priced | events |
|---|---|---|---|---|
| **S1 (the trader's rule: 5 bets in 12 months, all won)** | **-3.2%** | [-7.7%, +0.5%] | 99 / 119 | 90 (< 100: also inconclusive by criterion 3) |
| S2 | -0.6% | [-3.4%, +2.3%] | 829 / 3,022 | 494 |
| S3 | -4.5% | [-12.9%, +5.0%] | 1,293 / 3,061 | 1,284 |
| S5 | -4.1% | [-10.0%, +1.8%] | 2,145 / 2,989 | 2,093 |
| B1 (random eligible wallets) | -9.4% | [-15.2%, -3.6%] | | |

- No screen beats the matched random-entry benchmark R (one-sided p 0.34-0.84). Every Holm-adjusted p = 1.00.
- **No delay saves it.** At 5 seconds: S1 -4.1%, S2 0.0%, S3 -11.0%, S5 -3.6%.
- **No outcome-neutral estimator saves it** (*ipw*, repaired as in stage-2 A12: S1 -3.1%, S2 +0.3% [-0.6%, +1.0%],
  S3 -4.6%, S5 -3.2%).
  - VWAP fills of $500-$2,500 look profitable under *drop*, B1 included (+1.5% to +11.3% at 2 min). That is the
    stage-2 fill-selection artefact again.
  - Under *ipw* these gains vanish, except S2's +0.7% (0.99+ favourites) and S3's +2.2% at $100.
  - Under *adv* every VWAP variant is negative.

**What S1 buys.**
- S1 wallets buy near-certain favourites: median own first-fill price 0.998, median first-second size $6.7.
- Their own trailing record was "won 5 of 5", but the median S1 wallet made $0.17 on it. Outcome-won is not
  made-money.

**World Cup.**
- Inside 2026 World Cup markets there are too few screened signals to say anything:
  - S1: 10 filled signals in 4 events;
  - S2: +9.4%, CI [-10.7%, +36.1%], 34 events;
  - S5: -12.8%, CI [-33.0%, +7.9%], 77 events.
- Over the whole tournament period (2026-06-11 .. 07-19), no screen has a CI above zero.
- The wallets the trader noticed (mintblade, GRIMDRIP) were created 2026-06-02, after the selection date, so no
  point-in-time screen could have picked them.

**Candidate-pool bias.**
- The pool over-samples active wallets, with inclusion probability 0.39-0.88 at the class medians. S1-type wallets are
  under-represented: 0.95% of eligible wallets (1.6% after IPW), against 2.9% in the 2025-H2 full population.
- Re-weighting to the frame population moves the primary ROI by -1.2 to +1.3 points and changes no verdict. The IPW
  estimates are noisy: Kish ESS is 417 of 5,786 eligible wallets, and only 9 for S1.


## 1. Stage-3 protocol (written 2026-10-18 ~05:10Z, before any post-2026-06-01 data was pulled)

Why a holdout: CryptoHouse fills stop at 2026-01-05. Protocol V2, pUSD, the 2026 fee schedule and the
2026 World Cup (2026-06-11 .. 2026-07-19) are only visible through the Data API v2.

**Data sources.**
- Market metadata, resolution and current fees come from the shared Gamma universe
  `data/derived/markets_resolved.parquet` (all closed markets with endDate < 2026-10-16, fetched 2026-10-17).
  A slim copy is in `v2/markets_2026.parquet` (`v2_00_markets.py`).
  - `t_res` = `closedTime`, else `umaEndDate`. "Clean" = binary market with payout {1, 0}.
  - category4: sports -> sports; crypto -> crypto; politics and geopolitics -> politics; everything else -> other.
  - Fees: `fee_rate_now` = feeSchedule rate if feesEnabled, else 0. `fee_exponent` comes from feeSchedule.
- Trades: `/v2/trades` with `condition` (market tapes; start/end are ignored, so whole tapes are walked) and with
  `user` (wallet histories, which honour start/end).
  - Rows have no maker/taker role, so `taker_only=false` returns all fills and `taker_only=true` returns taker fills only.
- Provenance (deviation from the pmr raw-storage convention, made because of disk space):
  - Each request is logged in `v2/provenance_log.tsv` with URL, params, UTC fetch time, status, row count and the
    sha1 of the raw body.
  - Only slim parsed rows are stored, as parquet.
- Underlying event key `ue` follows addendum A6:
  - a sports market whose event slug starts `<...>-YYYY-MM-DD` is keyed by that prefix;
  - every other market is keyed `s:<event_slug>`, both inside and outside the Gamma table.

**Step 1: candidate pool.**
- Frame: clean markets with t_res in [2026-01-15, 2026-06-01) (`v2_01_pool_sample.py`).
- Strata: category4 x volume tier (T1 < $10k, T2 $10k-$1M, T3 >= $1M).
- Draw: 60 / 80 / 40 markets per tier, the smallest md5('pool|condition_id') in each stratum. That is 720 markets
  in 655 underlying events.
- Each tape is pulled with `taker_only=false`, capped at 150 pages. Every wallet with any fill in a sampled
  market enters the pool.
- All of this is pre-2026-06-01 information: the markets resolved before D, so their fills are earlier.

**Step 2: wallet subset (selection uses only pool tapes, i.e. pre-D data).**
- Pool wallets are classed from their pool fills:
  - A: BUY fills in >= 2 underlying pool events, and the first-BUY token won in all of them;
  - B: >= 2 pool events, not all won;
  - C: exactly 1 pool event, won;
  - D: exactly 1 pool event, lost;
  - E: no BUY fill in the pool (sell-only or maker-sell fills).
- Each class is Bernoulli-sampled by u = md5('sub|wallet') < q_class. The rates are in section 3 and were set from
  class sizes and pull cost only.
  - The subset was grown twice, nested (same u, larger q). The decision used pre-D information only: pull cost, and
    the trailing screen counts of the first 1,280 wallets, which showed S1 to be rare.
- Wallet histories (`v2_04_wallets.py trail`):
  - [2025-06-01, 2026-06-01), capped at 20 pages (20,000 fills);
  - plus the newest 3,000 fills before 2025-06-01, used only to tell whether an event had been traded before.
- A wallet whose trailing window hits the cap is flagged "heavy" and excluded from the screens. This uses pre-D data
  only, and the count is reported.

**Step 3: decisions and screens at D = 2026-06-01** (same rules as pre-registration sections 4-6):
- decision = (wallet, ue); t0 = the first BUY in the ue; decision token = the largest-notional token bought in the
  t0 second;
- 6 h entry episode; net-buy >= 50%; dust < $1;
- trailing record = t0 in [2025-06-01, D), market clean and t_res < D, fills < D only;
- screens:
  - S1 = exactly 5 counted resolved decisions, all won;
  - S2 = >= 5, zero losses;
  - S3 = >= 10, shrunken mean edge > 0 and z >= 2 (k = 10);
  - S5 = top 1% of trailing decision-market P&L among eligible wallets (>= 5 counted resolved decisions). The cut is
    the IPW-weighted 99th percentile of the subset;
- B1 = eligible wallets, randomly sampled.

**Inclusion weights (sampling-bias quantification, step 3 of the brief).**
- A wallet enters the pool if any of its frame markets was drawn, so pool inclusion grows with activity:
  pi_pool = 1 - prod_s (1 - n_s/N_s)^(m_ws).
  - m_ws = number of frame markets of stratum s that the wallet traded, from its own history.
- Subset inclusion is q_class. The IPW weight is 1 / (pi_pool x q_class).
- Every result is reported both unweighted (what this sample shows) and IPW-weighted (an estimate for all wallets
  that traded any frame market). The difference measures the candidate-pool bias.
- Screen base rates are compared with the full-population stage-1 rates (CryptoHouse, 2025-12-01).

**Step 4: evaluation (decided before pulling any of it).**
- Eval wallets: all S1, S2, S3 and S5 members, plus a B1 sample of up to 600 eligible non-heavy wallets
  (smallest md5('b1|wallet')).
- Their fills in [2026-06-01, 2026-10-01) are pulled, capped at 30 pages.
- Signals = new decisions: the first BUY in a ue never traded before in the wallet's pulled history, with t0 in
  [2026-06-01, 2026-10-01).
  - The decision market must resolve cleanly with t_res < 2026-10-15.
  - Unclean or unresolved signals are counted and excluded.
- Follower entry comes from the market's taker tape (`taker_only=true`, capped at 200 pages): BUY prints of the
  decision token by wallets other than the followed wallet. Delays d = 5 s, 30 s, 2 min, 15 min, 60 min, and an
  hourly poll (the next full UTC hour after t0).
  - (M1, pre-registered model) first print at >= t0 + d within 60 min, + 0.01 slippage (capped at 0.999);
  - (M2) VWAP of prints in [t0 + d, + 30 min) accumulated to $100 / $500 / $2,500, + 0.01; otherwise unfilled.
- Payoff: hold to resolution.
- Fee: the market's current schedule, fee = shares x rate x (p(1 - p))^exponent, charged on entry. Taker rebates are
  ignored (a $100-per-signal follower is at best Bronze, 3%).
- Primary: net ROI per $ at M1, 2-min delay, $100 stake; 95% CI from an event-clustered bootstrap (2,000 resamples).
- Benchmarks:
  - B1 (random eligible wallets, same follower model);
  - R, random entry: taker BUY prints in the same category4 and ISO week, with |price - follower price| <= 0.05, in
    a different ue, at the print price + 0.01 and current fees;
  - FAV: taker BUY prints priced 0.70-0.95, same category4 and week.
  - Benchmark prints come from all pulled eval tapes plus benchmark markets that resolved 2026-06-01 .. 2026-10-15.
    These are drawn by Poisson PPS on Gamma volume, 40 expected per category4, capped at 200 pages.
- **Pricing sample (cost rule, outcome-blind, set 05:45Z before any eval data).**
  - Within each group (S1, S2, S3, S5, B1) a signal is priced if u = md5('px|wallet|ue') < min(1, 3,000 / n_group).
  - A signal is priced if any of its groups selects it. Within a group, every signal keeps the same inclusion rate,
    so group means need no reweighting.
- **Fill-selection estimators (adopted from stage-2 addendum A11 before any stage-3 eval data existed).** Whether a
  print follows a signal depends on how the market moves next, so "filled" is outcome-dependent. Every headline is
  therefore reported three ways:
  - *drop* (pre-registered): unfilled signals are dropped;
  - *ipw*: filled signals are weighted by 1 / fill rate of their class, where class = screen x outcome x the followed
    wallet's own first-second price bucket (<0.2, 0.2-0.5, 0.5-0.8, 0.8-0.95, >=0.95).
    - **Repaired after the first stage-3 run**, following stage-2 addendum A12, which appeared while this stage ran.
      The first version let loser classes with no fill drop out.
    - Now every feasible loser counts at the mean ROI of filled losers (-1 if none filled). Only winners are
      reweighted by bucket, and winners in unrepresented buckets are spread over the represented ones.
    - Tables show the repaired ipw. The first version (`ipw_roi` in `results_main.parquet`) differs materially only
      for S1 (-2.3% vs -3.1% at M1) and for large VWAP sizes.
    - *drop* remains the pre-registered estimator;
  - *adv*: adverse bound, where every feasible unfilled loser is assumed filled and loses its stake. Feasible means
    detection happens before t_res.
  - Verdicts use *drop*, as pre-registered. A claim also has to survive *adv* to be called robust.
- Rejection follows pre-registration section 11 (criteria 1-4; criterion 5 is replaced by "positive in the
  stage-2 test", which is taken from stage 2 and not re-tuned here).
  - Holm runs over {S1, S2, S3, S5}; per screen p = max(p vs B1, p vs R).
- World Cup:
  - reported separately for signals whose market is a 2026 FIFA World Cup market (event slug `fifwc-*`, or a soccer
    'world-cup' slug);
  - and for all signals with t0 in [2026-06-11, 2026-07-20).

## 2. Build: pool, subset and checks (VERIFIED unless marked)

**Pool tapes (`v2_02_tapes.py pool`).**
- 720 sampled markets took 5,039 requests and returned 4,611,531 fills (all fills, `taker_only=false`).
- 14 tapes were empty: 10 sports-T1 and 4 crypto-T1 markets.
- 1 tape hit the 150-page cap: `russia-x-ukraine-ceasefire-by-march-31-2026`, whose Gamma volume reads 0, so it was
  sampled as T1. Its fills before 2025-10-16 are missing.
- 297,144 distinct wallets are in the pool.
- Sampling fractions n_s/N_s run from 0.0002 (sports-T1 and crypto-T1, about 390k and 274k markets) to 0.185
  (crypto-T3, 216 markets).
- Wallet classes:
  - A = 49,016;
  - B = 54,589;
  - C = 123,257;
  - D = 69,321;
  - E = 961.
- Median pool wallet: 1 sampled market (p99 = 12).

**Subset.**
- The final rates were q_A = 0.0408, q_B = 0.0275, q_C = 0.0203, q_D = 0.0072 and q_E = 0.208, giving 6,784 wallets
  (A 1,984, B 1,518, C 2,588, D 497, E 197).
- The rates were raised twice, nested, from an initial 2,301 wallets:
  - first because the pull cost about 3.2 requests per wallet;
  - then for class C only, because S1 was 0.65% of eligible wallets in the first 1,280.

**Checks.**
- `outcome_index` of `/v2/trades` equals the Gamma outcome position. All 6,930 rows of 147 markets matched on
  token id (`v2_09_index_check.py`).
- Only 0.027% of pool fills come after `t_res`, in 110 markets, with a median of 53 s after `t_res`. So `closedTime`
  is a good "resolution known" time, with seconds of slack.

## 3. Screens at D = 2026-06-01 (trailing data only; VERIFIED counts from `v2_05_screens.py`, `v2_10_bias.py`)

**Trailing window.**
- 9,471,418 fills of the 6,784 subset wallets (21,042 requests).
- 2,354,541 decisions, of which 1,700,221 were counted and resolved.
- 149 wallets (2.2%) hit the 20,000-fill cap and were excluded as heavy. 5,786 wallets are eligible (>= 5 counted
  resolved decisions).

| screen | members | share of eligible, unweighted | share, IPW | full population 2025-06..12 (stage 1, CryptoHouse) | median resolved decisions | mean entry price | decisions that made money | median trailing P&L |
|---|---|---|---|---|---|---|---|---|
| S1 (5 bets, all won) | 55 | 0.95% | 1.60% | 2.86% | 5 | 0.973 | 76% | $0.17 |
| S2 (>= 5, no loss) | 1,031 | 17.8% | 16.4% | 18.2% | 14 | 0.980 | 85% | $1.37 |
| S3 (z >= 2) | 126 | 2.18% | 1.19% | 0.21% | 1,192 | 0.695 | 73% | $344 |
| S5 (top 1% P&L) | 91 | 1.57% | 1.00% (by construction) | 1.00% | 105 | 0.644 | 70% | $10,029 |

- The S5 cut is $4,482 under IPW (unweighted 99th percentile: $7,555). Stage 1's population cut was $3,300-5,268 in
  2025-H2.
- **Outcome-won is not made-money.** S1 wallets won all 5 bets, but only 76% of those decisions made money in their
  market. The median S1 wallet made **$0.17** in total on its five wins, because it bought favourites at 0.97 on
  average. The same profile as stage 1 (82% of S1 rows priced >= 0.90) appears in 2026.
- **The members the trader cares about could not have been selected.** `mintblade` and `GRIMDRIP` were created on
  2026-06-02, after D, so no point-in-time screen at D can contain them.
  - Even at a later date, mintblade's record is 5 markets in 3 underlying events (three markets on one match), so it
    never reaches 5 distinct events. Source: CONTEXT.md, VERIFIED there.

**Evaluation activity (fills 2026-06-01 .. 2026-09-30).**
- 1,118 of the 1,706 eval wallets traded in the window (2,218 requests; 2 wallets hit the 30-page cap).
- 209,383 new decisions: 206,542 evaluable, 2,498 on unclean markets, 343 unresolved by 2026-10-15.

| group | wallets | active Jun-Sep | median new decisions | evaluable signals | signal wallets | underlying events | World Cup signals | own first-second price (median) | priced (sample rate) |
|---|---|---|---|---|---|---|---|---|---|
| S1 | 55 | 53% | 1 | 119 | 29 | 109 | 13 | 0.998 | all |
| S2 | 1,031 | 63% | 1 | 24,885 | 652 | 5,501 | 2,577 | 0.999 | 12.1% |
| S3 | 126 | 63% | 52 | 111,118 | 80 | 70,008 | 774 | 0.900 | 2.7% |
| S5 | 91 | 69% | 8 | 21,704 | 63 | 19,125 | 934 | 0.550 | 13.8% |
| B1 | 600 | 62% | 3 | 69,685 | 370 | 44,659 | 2,398 | 0.750 | 4.3% |

- Category mix of evaluable signals:
  - S1: 57% other, 20% crypto;
  - S2: 67% sports;
  - S3: 85% crypto, mostly up/down bots;
  - S5: 66% crypto, 32% sports;
  - B1: 80% crypto.
- 11,636 signals are priced, in 9,877 markets (plus 135 benchmark markets, 110 of them new).

## 4. Follower results (VERIFIED from `v2_07_follower.py`, `v2_08_results.py`; tables in `v2/results_*.parquet`)

**Execution proxy.**
- Data: taker BUY prints (`taker_only=true` tape) of the decision token by other wallets.
  - 9,877 eval tapes: 21.1M taker fills, 26,927 requests, 1 tape capped. No priced signal fell in a truncated tape.
  - 135 benchmark tapes: 2.28M fills.
- **Fill rate at 2 minutes (M1).**
  - Overall: 47.8% of priced signals.
  - Fills depend on the outcome, in both directions:
    - S2: winners 27%, losers 92%. A 0.999 favourite stops trading once it is certain.
    - S5: winners 78%, losers 85%.
    - B1: winners 60%, losers 88%.
  - Hence the three estimators.

**Primary model (M1, 2-min delay, $100, + 0.01, current fees), unweighted (u) and pool-IPW (w).**

| group | wt | filled / priced | events | wallets | mean follower price | hit rate | net ROI (drop) | 95% CI | ipw | adv | ROI before fees | wallet's own price ROI* | vs R (p) | vs B1 (p) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1 | u | 99 / 119 | 90 | 25 | 0.975 | 0.960 | -3.2% | [-7.7%, +0.5%] | -3.1% | -4.2% | -3.1% | -2.9% | -3.0 pts (0.84) | 0.053 |
| S2 | u | 829 / 3,022 | 494 | 276 | 0.946 | 0.947 | -0.6% | [-3.4%, +2.3%] | +0.3% | -1.1% | -0.3% | -0.6% | +0.7 pts (0.34) | 0.007 |
| S3 | u | 1,293 / 3,061 | 1,284 | 69 | 0.608 | 0.596 | -4.5% | [-12.9%, +5.0%] | -4.6% | -14.3% | -2.1% | -1.1% | -1.3 pts (0.62) | 0.188 |
| S5 | u | 2,145 / 2,989 | 2,093 | 50 | 0.558 | 0.560 | -4.1% | [-10.0%, +1.8%] | -3.2% | -10.8% | -1.6% | +0.4% | -2.0 pts (0.77) | 0.107 |
| B1 | u | 1,614 / 3,081 | 1,570 | 157 | 0.566 | 0.559 | -9.4% | [-15.2%, -3.6%] | -6.1% | -14.4% | -6.6% | -1.8% | -6.6 pts (0.98) |  |
| S1 | w |  |  |  | 0.981 | 0.978 | -1.9% | [-6.1%, +0.3%] | -1.5% | -2.0% | -1.8% | -1.6% | -4.1 pts (0.63) | 0.051 |
| S2 | w |  |  |  | 0.962 | 0.958 | -0.9% | [-3.1%, +1.2%] | +0.1% | -1.7% | -0.7% | -0.7% | +0.7 pts (0.24) | 0.024 |
| S3 | w |  |  |  | 0.621 | 0.608 | -5.7% | [-13.6%, +2.6%] | -4.5% | -14.1% | -3.3% | -1.1% | -2.4 pts (0.72) | 0.275 |
| S5 | w |  |  |  | 0.591 | 0.582 | -4.7% | [-12.9%, +6.5%] | -1.9% | -9.4% | -2.2% | -3.2% | -2.0 pts (0.70) | 0.227 |
| B1 | w |  |  |  | 0.578 | 0.575 | -8.9% | [-16.0%, -1.5%] | -5.4% | -12.9% | -6.2% | -2.8% | -7.1 pts (0.96) |  |

\* The wallet's own first-second VWAP with the current taker fee. It is not available to a follower, and it overstates
fees for wallets that were makers.

- **Benchmarks.**
  - "vs R" is the paired difference from random taker entries in the same category and week at +-5 cents
    (pre-specified). Its p-value is one-sided (screen > R).
  - The exploratory +-1 cent version (R1) was added after a partial-data debug run showed that +-5 cents mis-matches
    0.99+ entries. It gives the same picture: S1 -3.2 pts, S2 +0.3, S3 -1.3, S5 -1.3.
  - The favourite rule (FAV, prints at 0.70-0.95, same category and week): S2 beats it by +4.9 pts (p < 0.001),
    because 0.70-0.95 favourites lost 6.0% on average in this window. No other screen does.
- **Outcome-won vs made-money.** For a hold-to-resolution follower the two coincide (a win at <= 0.999 plus fees still
  pays). The distinction bites in the followed wallets' trailing records (section 3).
- **Fees.** The current schedule costs 0.05-0.3 pts on 0.95+ favourites (S1, S2), and 2.4-2.8 pts on the mid-priced
  crypto and sports entries of S3, S5 and B1. Crypto has rate 0.07; World Cup markets carry `sports_fees_v2`
  at 0.03.
- **Concentration.** The top 5 wallets hold most filled signals: S1 75%, S2 22%, S3 44%, S5 76%, B1 58%. Within S1,
  25 wallets supply 99 filled signals.

**Rejection criteria (section 11), unweighted, *drop* estimator:**

| screen | (1) ROI > 0 and CI excludes 0 | (2) beats B1 and R after Holm | (3) >= 100 events | (4) fragility | (5) positive in stage-2 test | verdict |
|---|---|---|---|---|---|---|
| S1 | fail (-3.2%) | fail (Holm 1.00) | fail (90) | n/a (P&L < 0) | fail (-7.1%) | rejected; also inconclusive |
| S2 | fail (-0.6%) | fail (1.00) | pass (494) | n/a | fail (-3.2%) | rejected |
| S3 | fail (-4.5%) | fail (1.00) | pass | n/a | fail (-7.8%) | rejected |
| S5 | fail (-4.1%) | fail (1.00) | pass | n/a | fail (-1.8%) | rejected |

## 5. Delay decay and size (unweighted; `v2/results_delay.parquet`)

**M1 (first print + 1 tick).**

| group | estimator | 5 s | 30 s | 2 min | 15 min | 60 min | hourly poll |
|---|---|---|---|---|---|---|---|
| S1 | drop | -4.1% | -3.2% | -3.2% | -3.2% | -3.7% | -3.6% |
| S2 | drop | 0.0% | -0.5% | -0.6% | -0.9% | +1.7% | +0.6% |
| S3 | drop | -11.0% | -10.5% | -4.5% | -9.1% | -13.5% | -16.9% |
| S5 | drop | -3.6% | -3.3% | -4.1% | -2.3% | -3.9% | -8.0% |
| B1 | drop | -4.2% | -5.7% | -9.4% | +0.6% | +8.2% | +5.8% |
| S2 | ipw (repaired) | +0.3% | +0.2% | +0.3% | +0.2% | +0.5% | +0.4% |
| S5 | ipw (repaired) | -4.3% | -3.6% | -3.2% | -4.4% | -2.5% | -3.4% |
| B1 | adv | -5.9% | -8.0% | -14.4% | -12.6% | -6.9% | -10.1% |

- At 5 s, every 95% CI upper bound is <= +2.1%:
  - S1 [-8.9%, -0.2%];
  - S5 [-7.3%, -0.1%];
  - S3 [-14.4%, -7.1%].
- The later-delay positives (B1 +8.2% at 60 min, S2 +1.7%) come from fill selection:
  - few signals fill late (B1 351 of 3,081 at 60 min);
  - they vanish under *adv* (B1 -6.9%, S2 -0.6%).
- **VWAP to $2,500 (M2).**
  - Under *drop* it shows +0.3% to +21% for every group, B1 included: an artefact.
  - Under the repaired *ipw*: S1 -3.6%, S2 +0.7%, S3 -14.2%, S5 -12.6%, B1 -11.1% at 2 min.
  - The first ipw version gave S1 +0.7% here: the A12 flaw, where losers without a fill dropped out.
  - S2's +0.7% comes from 0.99+ favourites whose $2,500 fills are rare. Capacity: only 22% (S1) to 63% (S5) of
    filled signals had >= $1,000 of taker buys in the 30 min after detection.

## 6. World Cup (2026-06-11 .. 2026-07-19) split (M1, 2 min, unweighted; `v2/results_splits.parquet`)

| subset | group | filled | events | wallets | net ROI | 95% CI | ipw | adv | vs R |
|---|---|---|---|---|---|---|---|---|---|
| World Cup markets | S1 | 10 | 4 | 8 | +2.1% | [+0.3%, +7.6%] | +1.6% | +2.1% | +6.1 pts (p 0.000) |
| World Cup markets | S2 | 65 | 34 | 80 | +9.4% | [-10.7%, +36.1%] | +2.6% | +9.4% | +12.1 pts (p 0.143) |
| World Cup markets | S3 | 19 | 18 | 14 | +25.0% | [-36.1%, +109.0%] | +25.9% | +18.7% | +24.5 pts (p 0.217) |
| World Cup markets | S5 | 115 | 77 | 26 | -12.8% | [-33.0%, +7.9%] | -14.5% | -18.5% | -17.9 pts |
| World Cup markets | B1 | 79 | 57 | 49 | +22.0% | [-16.5%, +73.8%] | +9.8% | +10.8% | +25.6 pts (p 0.137) |
| tournament period, all markets | S1 | 40 | 34 | 19 | -0.9% | [-7.1%, +3.3%] | +0.1% | -0.9% | +2.8 pts (p 0.002) |
| tournament period, all markets | S2 | 276 | 173 | 164 | +2.5% | [-2.4%, +8.2%] | +1.2% | +2.5% | +5.3 pts (p 0.013) |
| tournament period, all markets | S3 | 543 | 535 | 60 | -12.6% | [-21.2%, -3.0%] | -9.1% | -20.2% | -7.6 pts |
| tournament period, all markets | S5 | 837 | 793 | 40 | -6.6% | [-16.1%, +5.3%] | -5.6% | -10.4% | -4.0 pts |
| tournament period, all markets | B1 | 926 | 891 | 125 | -8.4% | [-16.5%, +0.2%] | -5.2% | -12.3% | -5.1 pts |
| rest of window | S1 | 59 | 59 | 13 | -4.8% | [-11.5%, +0.4%] | -5.7% | -6.3% | -7.0 pts |
| rest of window | S2 | 553 | 333 | 211 | -2.1% | [-5.2%, +1.3%] | -0.3% | -2.8% | -1.7 pts |
| rest of window | S5 | 1,308 | 1,302 | 37 | -2.5% | [-9.2%, +4.8%] | -1.6% | -11.1% | -0.7 pts |

- World Cup market signals are few: 4-77 events per group. B1, the random-wallet benchmark, does as well as or
  better than every screen there. These are noise-level numbers (PLAUSIBLE reading: a handful of upsets decides
  them), not evidence of skill.
- The tournament-period S2 figure (+2.5%, p 0.014 vs R, unadjusted) is one of about 35 split cells. Its CI includes 0
  and it reverses to -2.1% outside the tournament. It is not an edge.
- The 2026 World Cup markets use `sports_fees_v2` (rate 0.03, exponent 1), VERIFIED in the Gamma universe.

## 7. How the candidate-pool sampling biases the result (`v2_10_bias.py`; VERIFIED numbers, PLAUSIBLE readings)

1. **Inclusion grows with activity.**
   - Medians by class:

     | class | pi_pool | frame markets traded | IPW weight |
     |---|---|---|---|
     | A | 0.84 | 46 | 29 |
     | B | 0.88 | 188 | 42 |
     | C | 0.43 | 16 | 114 |
     | D | 0.39 | 22 | 358 |
     | E | 0.47 | 33 | 10 |

   - A wallet that traded no frame market has pi = 0 and cannot appear at all.
   - So the pool is heavy in active and bot wallets:
     - 87% of eligible pool wallets have >= 10 resolved decisions (75% after IPW);
     - S3 members have a median of 1,192 resolved decisions;
     - S3 and B1 signals are 80-85% crypto.
2. **The screens' composition shifts.**
   - S1 is 0.95% of eligible wallets (IPW 1.60%), against 2.86% in the 2025-H2 full population (stage 1).
   - S3 is 2.18% (IPW 1.19%), against 0.21%.
   - S2 is 17.8% / 16.4%, against 18.2%.
   - IPW moves the rates toward the population, but S1 stays under-represented. Likely reason (PLAUSIBLE): S1 wallets
     make about 5 decisions a year, often outside the Jan 15 - May 31 resolution window, so many have pi = 0.
3. **Effect on the follower result: small relative to the CIs.**
   - Unweighted to IPW-weighted primary ROI: S1 -3.2% to -1.9%; S2 -0.6% to -0.9%; S3 -4.5% to -5.7%; S5 -4.1% to
     -4.7%; B1 -9.4% to -9.0%.
   - No verdict changes.
   - The IPW estimate is itself imprecise (Kish ESS 417 of 5,786 eligible; S1 8.7, S2 99, S3 18, S5 40).
4. **Other selection steps.**
   - Heavy-wallet exclusion: 149 wallets (2.2%) with > 20,000 fills in the trailing year.
   - 1 capped pool tape.
   - Pre-window history is capped at 3,000 fills. 9 non-heavy wallets hit the cap, so for them an event traded
     before their newest 3,000 pre-window fills could be mislabelled as new.
   - The pricing sample is a Bernoulli hash sample within each group, so it adds no bias.
   - S1 is too small to support a conclusion of its own (90 events, 25 signal wallets): the S1 verdict rests on
     "negative point estimate, consistent with stage 2", not on a tight interval.
5. **Survivorship and post-D information.**
   - Nothing after D was used to choose wallets.
   - 47% of S1 members made no new decision in June-September. That inactivity is part of the result, not a filter.

## 8. Limitations

- The execution proxy is other wallets' taker prints, not the book. There is no historical book, so this is the same
  proxy as stage 2.
  - The 5-second case assumes a follower sees the fill within 5 s of its block time. The Data API caches
    `/v2/trades` for up to 300 s (notes/platform/data_infrastructure.md), so 5 s is optimistic (PLAUSIBLE).
- Fees: the current feeSchedule is applied to every entry. Taker rebates (3-50% by tier) are ignored; a small
  follower would be at most Bronze.
  - The eval window straddles 2026-05-28 (Taker Rebate Program start) and possible schedule changes. The schedule
    in force at each trade was not reconstructed (UNSUPPORTED that it was constant).
- One selection date and a 4-month window. S1 has 90 events, so its power is low.
- Trades come from Data API v2, and the CryptoHouse fill rule was not re-verified for V2. The outcome-index mapping was
  verified on 6,930 rows, and the API is the platform's own record (VERIFIED for the fields used).
- The decision P&L uses fills only. Splits, merges and conversions in `/v2/activity` were not pulled: they were not
  needed for S1, S2, S3 or S5 and were left out for cost. So the "made money" shares in section 3 are approximate,
  with the same caveat as stage 1.

## 9. Files

- Scripts (`analyses/pit_wallets/`):
  - `v2common.py`: lean fetcher, provenance log, helpers;
  - `v2_00_markets.py`: slim market table;
  - `v2_01_pool_sample.py`: frame and stratified market sample;
  - `v2_02_tapes.py`: market tapes (pool, eval, bench);
  - `v2_03_subset.py`: pool classes and wallet subset;
  - `v2_04_wallets.py`: wallet histories (trail, eval);
  - `v2_05_screens.py`: decisions and screens at D;
  - `v2_06_eval.py`: eval signals, pricing sample, benchmark markets;
  - `v2_07_follower.py`: follower prices and payoffs;
  - `v2_08_results.py`: inference, delays, splits;
  - `v2_09_index_check.py`: outcome-index check;
  - `v2_10_bias.py`: sampling diagnostics.
- Data (`data/derived/pit_wallets/v2/`):
  - `markets_2026`, `pool_frame`, `pool_sample`;
  - `tapes_{pool,eval,bench}/` with status TSVs;
  - `pool_wallets`, `wallet_subset`;
  - `wallets_{trail,eval}/` with status TSVs;
  - `decisions_trail`, `screens_D`, `eval_wallets`, `eval_signals`, `eval_markets`, `bench_markets`, `follower`,
    `bench_prints`;
  - `results_{main,delay,splits}`, `results_text.txt`, `bias_text.txt`, `index_check`;
  - `provenance_log.tsv`: 57,751 requests, each with URL, params, UTC time, status, rows and body sha1.
- Total size about 1.2 GB.
