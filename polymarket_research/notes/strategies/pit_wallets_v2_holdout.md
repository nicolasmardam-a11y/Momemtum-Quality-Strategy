# PIT wallet-following: stage 3, 2026 recent-regime holdout (Data API v2)

- Stage 3 of 4. Started 2026-10-18T05:00Z. As-of date of the project: 2026-10-17.
- Pre-registered rules (`pit_wallets_preregistration.md`) are unchanged. This note adds a stage-3 protocol
  (section 1), written before any evaluation-window (2026-06-01 onwards) trade, price or outcome was pulled.
- Scripts: `analyses/pit_wallets/v2_*.py` and `v2common.py`. Data: `data/derived/pit_wallets/v2/`.

__RESULT__

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
  class sizes only.
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
  - Benchmark prints come from all pulled eval tapes plus 300 benchmark markets that resolved
    2026-06-01 .. 2026-10-15. These are drawn PPS by volume within category4 (75 each), capped at 60 pages.
- **Fill-selection estimators (adopted from stage-2 addendum A11 before any stage-3 eval data existed).** Whether a
  print follows a signal depends on how the market moves next, so "filled" is outcome-dependent. Every headline is
  therefore reported three ways:
  - *drop* (pre-registered): unfilled signals are dropped;
  - *ipw*: filled signals are weighted by 1 / fill rate of their class, where class = screen x outcome x the followed
    wallet's own first-second price bucket (<0.2, 0.2-0.5, 0.5-0.8, 0.8-0.95, >=0.95);
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

__SECTIONS__
