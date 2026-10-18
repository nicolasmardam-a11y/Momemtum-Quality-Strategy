# Family E (favourite-longshot bias) and Family H (near-resolution convergence)

As-of 2026-10-17. Builds on `universe.md` (stage 1) and `panel.md` (stage 2). Scripts: `analyses/flb_near_res/`.
Labels: **VERIFIED** (computed here from stored data), **PLAUSIBLE**, **UNSUPPORTED**.

## 0. Pre-registration (written 2026-10-17 BEFORE any outcome, return or calibration statistic was computed)

What I had looked at when writing this section: counts of priced markets and of markets with max(p, 1-p) >= 0.90/0.95/0.99
per clock x horizon x split in `price_panel.parquet`; eligible-population counts per split x category in the universe;
the cost-model tables in `spread_model.parquet` and `effective_spread_hist.parquet`; and the US Treasury average T-bill rate.
I had not looked at any payout, realised frequency or return. One probe of `/prices-history` (fidelity 5, 9- and 15-day
windows, one politics market) checked the pull is feasible. Nothing below is changed after results; deviations go in section 9.

### 0.1 Hypotheses
- **E (FLB):** at a fixed decision time before resolution, sides priced <= 10c win less often than their price and sides
  priced >= 90c win more often. After half-spread and the current taker fee, buying the favourite side, or buying the complement
  of a longshot (economically "buying NO", no naked shorting), earns a positive mean return per $ committed.
- **H (near-resolution convergence):** buying the side priced >= 0.90 / 0.95 / 0.98 / 0.99 at T-24h / T-6h / T-1h earns a
  positive net return, and a return per capital-day above the T-bill rate.
- **Null expectation** (from the verified literature note `title_flb-polymarket.md`): favourite tails earn about +0.3% to +0.8%
  per $ before fees on trade-weighted data. Takers lose at both tails, and sports shows no FLB. An edge of this size is about the
  same as the costs, so "no demonstrated edge" is the prior expectation.

### 0.2 Samples
- **P (panel, existing):** the 8,000-market stage-2 sample (binary, full-life `volumeNum` >= $10k, stratified, `sample_weight`
  to the eligible population). The volume screen is a look-ahead (panel.md 4.1). P is the **primary test sample** because its
  costs are credible (liquid markets).
- **W (wide, new, volume-free):** a stratified random sample of eligible markets with **no volume screen**. Eligible means binary,
  `enableOrderBook`, `traded` proxy, resolution winner or 50-50, and a `token_id_0`. P markets are excluded. Sizes: TEST 20,000,
  validation 6,000, train 4,000. Allocation within each split is proportional to sqrt(N_category), with a floor of min(N, 150)
  and a cap of N. Seed 20261018. Weight = N_cell / n_cell. Prices come from CLOB `/prices-history` for `token_id_0` at fidelity 5
  (5-minute grid) over [anchor - 7d - 2h, closedTime + 10 min], capped at 15 days. When closedTime is more than 15 days after the
  window start, a second request covers [closedTime - 26h, closedTime + 10 min]. W is the **replication / look-ahead check**.
- Splits by endDate: train < 2025-07-01 <= validation < 2026-01-01 <= TEST <= 2026-10-15. All headline results are TEST.

### 0.3 Decision clocks and horizons (known ex ante)
- Anchor A = `gameStartTime` for sports markets that have one, else `endDate` (the scheduled clock). The `res` clock
  (min(endDate, closedTime)) is reported only as a descriptive look-ahead comparison.
- E horizons: A-7d, A-1d, A-6h, A-1h. H horizons: A-24h (= A-1d), A-6h, A-1h. Secondary, sports only: in-play A+1h, A+2h.
  These are not in the primary test set.
- A horizon counts only if it is strictly before `closedTime` and a series point exists within one grid step plus slack
  (h60 points: 2 h; minute or 5-minute points: 15 min) at or before the horizon. Price = last series point with t <= horizon.
- The P series is the panel's own `price_series_m1` (last 72 h before ref_ts) and `price_series_h60` (earlier). The W series is
  the 5-minute grid.

### 0.4 Sides, buckets, payout
- Each market at a horizon gives two sides: token 0 at p and token 1 at 1-p. Books are mirrored (VERIFIED in panel.md). The
  token-1 series itself was not pulled.
- Calibration buckets (side price, cents): [0,2) [2,5) [5,10) [10,20) [20,30) [30,40) [40,50) [50,60) [60,70) [70,80)
  [80,90) [90,95) [95,98) [98,100].
- Payout per share: 1 if the side won, 0 if it lost, 0.5 for a 50-50 resolution.

### 0.5 Costs (per share, prospective)
- m = series price (midpoint or last-trade display price, **not executable**).
- Half-spread h:
  - **base** = max(TEST historical median effective half-spread at split=test x price bucket x TTR (`effective_spread_hist`
    H1, fallback H3), live-book `vol10k` median half-spread at price bucket x TTR (L2 if >= 20 two-sided markets, else L3)).
    TTR mapping: A-1h -> `<=1h`, A-6h -> `1-6h`, A-1d -> `6-24h`, A-7d -> `3-7d`, in-play -> `in_play`.
  - **conservative** = max(base, live-book `allopen` L3 median half-spread by price bucket), for unscreened markets.
- Primary cost: **base for P, conservative for W.** Both are reported for both samples. Sensitivity: 2x the half-spread.
- Fill price f = m + h. A trade with f > 0.999 is infeasible (no ask can exist) and is dropped from the rules.
- Fee:
  - **Current** (prospective, primary) = `pmr.fees.TAKER_RATE[category]` x f x (1-f) per share. Geopolitics is 0. This table equals
    the latest per-category `feeSchedule`.
  - **As-traded** = the per-market `fee_rate` x (f(1-f))^`fee_exponent`, or 0 where fees were off.
  - **Gross** = buy at m with no fee.
  - **Spread-only** = buy at f with no fee.
- Cost per share c = f + fee. Return per $ committed is R = payout / c - 1.
- Size: headline results are for small orders (< about $500), where the panel's recommendation is half-spread only. For
  capacity, add the `vol10k` L3 buy slippage at $500 / $2.5k / $10k and report the share of books that can fill.
- Not modelled: taker rebates (Bronze 3% of fees at $2k weighted volume, small) and maker execution (would avoid fee and spread but
  has fill risk and adverse selection). Both are stated, not credited.

### 0.6 Holding period and capital
- Entry at the horizon. Capital is released at Gamma `closedTime` (on-chain auto-redemption about 12 s later per mechanics.md;
  closedTime = payout availability is PLAUSIBLE). Days held d = (closedTime - entry) / 86400.
- Return on committed capital per day = sum(w R) / sum(w d), with $1 stakes.
- Opportunity cost: the US Treasury average interest rate on outstanding marketable T-bills, 3.87% p.a. at 2026-09-30 (fiscaldata
  API, fetched 2026-10-17), i.e. 0.0106% per day. Excess return per trade = R - 0.0387 x d / 365.
- **Nothing is annualised.** Per-day figures are compared with the per-day T-bill rate.

### 0.7 Pre-specified rules (the only primary tests; 15 in total)
- **E1:** buy the favourite side when its price is in [0.80, 0.95] at A-1d, all categories.
- **E1X:** E1 restricted to the categories in X. X is the set of categories where E1's net mean R (current fee, base cost, weighted)
  is > 0 with >= 30 trades in train + validation pooled. X is fixed before TEST is looked at; if X is empty, E1X is not run.
- **E2:** buy the complement of a longshot (the longshot side priced <= 0.05) at A-7d, all categories. The literal variant (the
  longshot is the token whose outcome is "Yes") is reported as secondary.
- **H grid (12 rules):** buy the side priced >= {0.90, 0.95, 0.98, 0.99} (and f <= 0.999) at A-24h / A-6h / A-1h, all
  categories. Disjoint bands and category splits are descriptive.
- One trade per market per rule (the favourite side). Every market that qualifies is traded with a $1 stake. Estimates are
  population-weighted (`sample_weight`, or the W weight), so they describe trading every qualifying market. Unweighted results are a
  robustness check.

### 0.8 Inference
- Two bootstraps, 4,000 replicates each, of the weighted mean of R:
  - by `cluster_id` (the event, the sports game stem or the neg-risk group);
  - by `cluster_week` (ISO week of endDate).
  For each rule, report the wider of the two 95% CIs.
- Multiplicity: over the 15 primary tests, "significant" means the one-sided Bonferroni bound (the 0.05/15 = 0.33% bootstrap
  quantile) excludes 0, under both bootstraps.
- Within-cluster and within-day correlation: one-way ANOVA intraclass correlation of R by `cluster_id` and by entry UTC date, plus
  the design effect.

### 0.9 Rejection criteria and verdict mapping (per rule; TEST unless stated)
A rule is **promising_test_further** only if ALL of the following hold:
1. In P, the TEST net mean R (current fee, base cost, weighted) has a Bonferroni lower bound > 0 under both bootstraps.
2. In P, the validation net mean R (current fee applied prospectively) has a point estimate > 0.
3. The net return per capital-day exceeds the T-bill rate per day (point estimate).
4. The point estimate stays > 0 at 2x half-spread.
5. The point estimate stays > 0 after dropping the 5 clusters that contribute the most PnL.
6. There are >= 200 TEST trades from >= 100 clusters and >= 20 weeks.
7. In W (volume-free), the TEST net mean R with base cost has a point estimate > 0.
8. In P, the point estimate is > 0 on the decision-time volume-screened tape subset (`vol_screen_at_h`), if n >= 100.

Verdict mapping:
- **rejected**: the P TEST net 95% CI upper bound is < 0 under the cluster bootstrap.
- **marginal**: not promising, but either (a) the P TEST net point estimate is > 0 with criteria 3-7 met, or (b) W TEST (base cost)
  has a 95% lower bound > 0 under both bootstraps.
- **no_demonstrated_edge**: otherwise.

The family verdict is the best rule verdict, reported together with the number of rules tried (15).
- **E calibration (descriptive):** FLB is "present at horizon h" if, in TEST, the pooled <= 10c side buckets have realised minus
  price < 0 with the 95% cluster CI excluding 0. With both sides included this is the mirror of the >= 90c statement.
