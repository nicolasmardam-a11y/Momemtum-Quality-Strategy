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

---
# RESULTS (written 2026-10-18 after the pre-registered analysis; section 0 above is unchanged)

Scripts: `01_wide_sample.py` (W draw), `02_pull_wide.py` (W prices), `03_build_entries.py` (decision-time entries),
`04_analyze.py` (pre-registered analysis), `05_posthoc.py` (post-hoc diagnostics, section 9). Outputs: `analyses/flb_near_res/out/
04_results.{md,json}`, `05_posthoc.md`. Derived data: `data/derived/flb_wide_sample.parquet`, `flb_wide_parts/` (W change points),
`flb_entries.parquet` (market x horizon), `flb_sides.parquet` (market x horizon x side, with costs and returns),
`flb_calibration_test.parquet`. All numbers are **VERIFIED** (computed from stored data) unless labelled otherwise. "net" = primary
cost (P: base half-spread; W: conservative half-spread) + CURRENT taker fee; returns are per $ committed, $1 per trade, population-weighted.

## 1. Data actually used
- **P** (stage-2 panel, full-life volume >= $10k): 8,000 markets. Priced at A-7d / A-1d / A-6h / A-1h: TEST 1,426 / 3,411 / 4,425 / 4,365
  of 4,999; validation 427 / 1,123 / 1,190 / 1,236 of 1,500; train 634 / 1,112 / 1,150 / 1,140 of 1,501.
- **W** (volume-free): 30,104 markets drawn (TEST 20,006, validation 6,001, train 4,097). 32.4k `/prices-history` requests (fidelity 5),
  0 errors, 37 empty. Priced TEST A-7d / A-1d / A-6h / A-1h: 4,280 / 12,471 / 16,941 / 16,854. Most nulls are markets that did not
  exist yet at the horizon (`before_series_start`, 44k rows) or had already closed (`post_close`, 10k).
- **Costs actually applied** (half-spread, price units):
  - base, by side-price bucket (A-7d / A-1d / A-6h; A-1h): 85-95c 1.0c, 1.5c; 95-98c 0.7c, 0.7c; >98c 0.1c, 0.25c; <2c 0.1c, 0.45c.
  - conservative (allopen L3): 85-95c 3.4c; 95-98c 1.85c; >98c 0.4c; 35-65c 19.5c.
  - Current fee at f = 0.98 is 0.05 x 0.98 x 0.02 = 0.1c per share. The fee is small at the extremes, so the half-spread is the
    dominant cost for favourites.
- T-bill: 3.87% p.a. = 0.0106% per day.

## 2. Family E: calibration (TEST unless stated)
- **The pre-registered FLB-presence test is met in only 1 of 8 sample x horizon cells: W at A-7d.**
  - Longshot sides <= 10c were priced 3.71c on average and won 1.13% (diff -2.58pp, cluster 95% CI [-3.43, -1.48]).
  - The mirror, the >= 90c sides, came in at +2.76pp [+1.59, +3.61].
  - At A-1d, A-6h and A-1h the W tails are calibrated to within 0.2pp (for example, A-1d <= 10c: -0.00pp [-0.72, +0.72]).
  - In P (liquid; full-life volume screen) the sign is reversed at A-1d and A-1h, but not significantly: <= 10c +1.0 to +1.2pp;
    >= 90c -1.2pp [-2.8, +0.4].
- **Period.** The FLB was clearer before 2026:
  - P at A-7d: <= 10c -1.6pp [-2.5, -0.5] in train and -1.8pp [-2.6, -1.0] in validation.
  - W at A-1d: -1.1pp in train and -1.2pp in validation (both CIs exclude 0).
  - In TEST, short-horizon FLB is gone. It survives only at 7 days in the unscreened universe (PLAUSIBLE: the bias has been competed
    away where turnover is fast).
- **Mid-range, P TEST, A-1d.** Sides priced 60-95c underperform by 4 to 7pp (70-80c: -7.4pp [-13.1, -1.8]). This holds across
  categories (sports -5pp, finance -14pp, mentions -12pp, weather -1pp) and also in P train+validation (-4.9pp). W TEST shows the
  opposite (+2.1pp). Section 9.1 shows this is largely a look-ahead selection effect of the full-life volume screen (PLAUSIBLE,
  strongly supported).
- **W uninformative prices.** At A-7d, W sides priced 40-50c realise -19.5pp and 50-60c +10.7pp. Thin, untraded markets display about
  0.5 and the "Yes" token usually loses. With a 19.5c conservative half-spread nothing here is tradable.
- **Expected net return per $ of buying each side** (TEST, current fee):
  - Longshots <= 10c: W -48% to -88%. P is noisy, from -54% to +7%, with every CI wide. Buying longshots never pays robustly.
  - The >= 90c side: W A-1d -1.65% [-2.38, -0.95], A-1h -1.55% [-2.19, -0.92], A-7d +0.80% [-0.43, +1.65]. P A-1d -1.81%, A-1h -1.91%.
- **Category and liquidity tables:** `04_results.md` sections "E2 tails by ...". The volume terciles use full-life volume (look-ahead)
  and are descriptive only. The decision-time activity split is in section 9.2.

## 3. Pre-registered rules: TEST (P = primary)

| rule | P n (clusters, weeks) | P gross | P net | P net 95% CI cluster / week | Bonf. lower (cl/wk) | P val net | W net (cons) | W net base [cl CI] | verdict |
|---|---|---|---|---|---|---|---|---|---|
| E1 fav [0.80,0.95] A-1d | 524 (510, 42) | -4.91% | **-6.50%** | [-11.45, -1.95] / [-12.24, -1.49] | -13.3 / -14.8 | -5.95% | -3.36% | -0.63% [-2.42, +1.08] | rejected |
| E1X (X = crypto, economics, mentions) | 56 (51, 21) | -7.52% | -9.21% | [-33.4, +10.3] | -44.9 | +0.50% | -2.22% | +0.68% | no_demonstrated_edge |
| E2 buy NO-equivalent vs longshot <= 0.05, A-7d | 394 (349, 40) | +1.44% | **+1.01%** | [+0.18, +1.62] / [-0.08, +1.77] | -0.22 / -0.50 | +0.55% | +1.13% | +1.94% [+1.58, +2.26] | **marginal** |
| H90_24h | 897 | -1.60% | -2.28% | [-4.48, -0.25] | -5.6 | +0.45% | -2.06% | -0.71% | rejected |
| H90_6h | 858 | -1.32% | -1.99% | [-4.31, +0.12] | -5.4 | -2.21% | -2.28% | -0.91% | no_demonstrated_edge |
| H90_1h | 699 | -2.60% | -3.60% | [-6.61, -1.00] | -7.8 | -1.27% | -2.19% | -1.07% [-2.14, -0.08] | rejected |
| H95_24h | 679 | -0.24% | -0.62% | [-2.15, +0.60] | -2.7 | -0.44% | -1.15% | -0.45% | no_demonstrated_edge |
| H95_6h | 669 | +0.35% | -0.03% | [-1.33, +0.90] | -2.0 | -1.34% | -1.37% | -0.66% | no_demonstrated_edge |
| H95_1h | 513 | -1.15% | -1.64% | [-4.24, +0.38] | -5.7 | +0.19% | -0.83% | -0.18% | no_demonstrated_edge |
| H98_24h | 473 | -0.78% | -0.92% | [-2.86, +0.49] | -4.1 | +0.43% | -0.17% | +0.12% | no_demonstrated_edge |
| H98_6h | 492 | +0.49% | +0.35% | [-0.15, +0.68] | -0.36 | +0.05% | -0.58% | -0.29% | no_demonstrated_edge (fails 7) |
| H98_1h | 357 | -0.89% | -1.17% | [-3.33, +0.44] | -4.6 | +0.42% | -0.12% | +0.03% | no_demonstrated_edge |
| H99_24h | 304 | -0.88% | -1.00% | [-2.81, +0.40] | -3.6 | +0.20% | +0.03% | +0.31% | no_demonstrated_edge |
| H99_6h | 357 (339, 42) | +0.40% | **+0.28%** | [+0.05, +0.41] / [+0.05, +0.40] | -0.05 / -0.05 | +0.18% | +0.22% | +0.51% [+0.45, +0.55] | **marginal** |
| H99_1h | 226 | +0.45% | +0.18% | [-0.17, +0.36] | -0.44 | -0.04% | +0.05% | +0.20% | no_demonstrated_edge |

- **No rule passes criterion 1** (the Bonferroni lower bound > 0 under both bootstraps).
  - E2 and H99_6h pass criteria 2 to 7. Criterion 8 is n/a (decision-time volume-screened subset: n = 81 and 71).
  - Both are therefore **marginal** under (a), and also under (b).
- **As-traded fees** (2026 per-market fee fields) give almost the same net as current fees: E2 +1.03%, H99_6h +0.29%. Fees are
  negligible at these prices.
- **E2 literal** (the longshot is the "Yes" token): P TEST +0.86%, W +1.15%.
- **E2 by period:**
  - P: train +0.28%, validation +0.55%, TEST +1.01%.
  - W (conservative cost): train +0.44%, validation **-0.52%**, TEST +1.13%.
  - By category, P TEST losses fell in culture, economics and politics; W economics is -2.84% (3 losses in 76).
- **H99_6h by period:**
  - P: train +0.35% (0 losses), validation +0.18%, TEST +0.28%.
  - W: validation **-0.13%**, TEST +0.22%.
- **The H99 horizons are inconsistent**, which reads as noise around about +0.2%: 24h -1.00% (three A-1d weather losses), 6h +0.28%,
  1h +0.18%.
- **E1 X selection** on train+validation used >= 30 trades and net > 0: crypto 38 trades +0.15%, economics 31 +5.1%, mentions 35 +5.7%.
  In TEST: -9.2% on 56 trades.

## 4. Tail-loss exposure, correlation, lock-up (TEST)
- **Every rule's worst trade is -100%.** Loss rates:
  - E2: P 0.56%, W 0.27% (3 and 5 unweighted losses).
  - H99_6h: P 0.10%, W 0.03% (1 loss each).
  - E1: 16.5% against a price-implied 12%.
- **Worst loss per event** is -$1 per $1 stake for both marginal rules. Clusters are nearly all singletons (max 3-4 qualifying markets
  per event), so event concentration is low.
- **Correlation.**
  - Cluster design effect: 1.1 to 1.25 (P E2 1.25, H99_6h 1.11).
  - Entry-day design effect: larger. P E2 6.7, P H99_6h 5.9, W E2 2.8, W H99_6h 1.8. Same-day outcomes are correlated, which is why
    the week bootstrap is wider.
  - The one-way ICC point estimates (about 0.99 by cluster) are degenerate: most clusters have one member and winners have
    near-identical R. Use the design effects instead.
- **Lock-up and return per capital-day:**
  - E2: mean 8.2 days held (median 7.3). Return per capital-day +0.123% against T-bill 0.0106%. Excess over T-bill +0.92% per trade.
  - H99_6h: mean 1.40 days (median 0.66). +0.20% per capital-day. Excess +0.27% per trade.
  - Nothing is annualised. Treat these per-day figures as point estimates that one or a few losses would erase (section 9.3).
- **Rare-loss fragility** (`05_posthoc.md` section 3, unweighted):
  - **H99_6h:** break-even loss rate 0.37% (P). Observed P TEST 1/357; pooled over all splits 2/828 = 0.24% (Clopper-Pearson 95%
    upper bound 0.87%). One more loss among the 357 TEST trades takes the P mean to about 0.
  - **E2:** break-even loss rate 1.38-1.55%. Pooled P 9/902 = 1.00% (95% upper bound 1.89%); pooled W 16/1,487 = 1.08% (upper bound
    1.74%). About 4 more losses per 394 TEST trades erase the P mean.
  - With the upper bounds above break-even, the data cannot exclude zero or negative expectancy. The bootstrap CIs understate this,
    because they resample a handful of losses.

## 5. Family H extras: disputes, 50-50, settlement delay, worst cases (TEST, entries >= 0.90)

| sample, horizon | n | disputed | 50-50 | settle lag (closedTime - endDate) median / p90 / p99 | lag > 24h / > 72h / > 7d | days held mean (p90) | T-bill cost per trade |
|---|---|---|---|---|---|---|---|
| P A-1d | 897 | 0.26% | 0.00% | 7.1h / 46h / 798h | 10.8% / 2.6% / 1.5% | 1.86 (3.1) | 0.020% |
| P A-6h | 858 | 0.38% | 0.00% | 9.6h / 53h / 785h | 10.7% / 3.1% / 1.6% | 1.14 (2.8) | 0.012% |
| P A-1h | 699 | 0.05% | 0.00% | 11.2h / 60h / 822h | 11.0% / 2.8% / 1.6% | 0.93 (2.7) | 0.010% |
| W A-1d | 3,236 | 0.12% | 0.07% | 4.5h / 31h / 360h | 4.4% / 1.2% / 0.8% | 1.49 (2.3) | 0.016% |
| W A-6h / A-1h | 3,106 / 3,042 | 0.05% / 0.04% | 0.13% / 0.00% | 4.4h / 31h / 361h | 4.3% / 0.9% / 0.6% | 0.71 / 0.49 | <0.01% |

- **Opportunity cost.** The T-bill cost of the lock-up is 0.01-0.02% per trade. It is small against the 0.3-1% spreads, but it is
  of the same order as the H99 edge's uncertainty. Settlement tails matter more: 1.5% of liquid entries waited more than 7 days, and
  p99 was about 33 days.
- **Worst cases** (TEST losses at the highest entry price; full list in `04_results.md`):
  - weather: "Highest temperature in Madrid 17°C or below on May 7" (0.9955 at A-1d, P); Tel Aviv 32°C Oct 3 (0.9955); Kuala Lumpur
    29°C Jul 11 (0.993); San Francisco 70-71°F Jun 12 (0.9915 at A-1h, W);
  - economics: "US GDP growth Q4 2025 between 1.0% and 1.5%?" (0.9925 at A-6h, P; settled 546h after endDate);
  - geopolitics: "Han Duck Soo sentenced to at least 20 years?" (0.9925 at A-6h, W);
  - culture: "Khamenei 15-19 posts May 19-26" (0.992);
  - sports: several "Exact Score" markets at 0.98-0.99;
  - politics: "Abdul El-Sayed wins MI Senate Dem primary by < 5%" (0.986 at A-1h).
  - Pattern: losses concentrate in bucketed numeric markets (temperature, counts, GDP), where one unit decides the outcome, and in
    exact-score markets.
- **Look-ahead clock benchmark** (descriptive). On the realised-close clock (R-6h), P [0.95, 0.98) earns +2.4% net, against -0.8% on
  the scheduled clock. Knowing when a market will close is worth far more than any H rule earns, and it is not available ex ante.

## 6. Capacity (TEST; `04_results.md` capacity table and `05_posthoc.md` section 4)
- **Size-dependent net** (vol10k books: buy slippage at size + current fee), and the share of books that can fill:

  | rule | $500 | $2.5k | $10k | fillable $500 / $2.5k / $10k |
  |---|---|---|---|---|
  | E2 | +0.75% | +0.53% | +0.30% | 96% / 79% / 59% |
  | H99_6h | +0.19% | +0.11% | -0.06% | 94% / 75% / 55% |

- **Frequency** (P population = vol>=10k universe):
  - E2: about 29 qualifying markets per day, held 8.2 days, so about 237 concurrent positions. Trading all of them at $500 needs about
    $119k.
  - H99_6h: 35 per day, held 1.4 days, so about 49 concurrent. Trading all at $500 needs about $25k.
  - The W population adds 70 (E2) and 123 (H99_6h) per day, with thinner books where the conservative costs apply.
- **Accounts:**
  - **$5k:** fully deployable in either rule, at about $20 per E2 market or about $100 per H99_6h market. Size is not the
    constraint; the edge is.
  - **$25k:** E2 at about $105 per market across all qualifying markets; H99_6h at about $500.
  - **$100k:** E2 at about $420 per market (net about +0.7%); H99_6h would need about $2k per market, where the net is about +0.1%.
    That is roughly the ceiling for H99_6h.
  - These are capacity statements **conditional on an edge that is not demonstrated**.

## 7. Verdict
- **Family E/H verdict: marginal.** It is the best of 15 pre-registered rules: 2 marginal (E2, H99_6h), 3 rejected (E1, H90_24h,
  H90_1h) and 10 no demonstrated edge. No rule meets the promising criteria; criterion 1 (multiplicity-adjusted significance) fails
  for all.
- **E1 is rejected.** Buying liquid favourites priced 0.80-0.95 a day before resolution loses 6.5% net in P. The P figure is biased
  down by the volume screen (section 9.1). In the unscreened W it is still -0.6% (base) to -3.4% (conservative).
- **H at >= 0.90 or >= 0.95 loses after costs at every horizon.** The thin positive pockets (0.98-0.99 at 6h) are worth +0.2-0.3% per
  trade and are one or two losses from zero.
- **E2 is the most consistent positive cell, but not demonstrated.**
  - It is positive in 5 of 6 sample x split cells and in every decision-time activity tercile.
  - It survives in W markets whose final volume ended >= $10k.
  - Its expectancy rests on a loss rate (about 1%) within sampling error of break-even (about 1.4%).
  - PLAUSIBLE persistence reasons: lock-up aversion (8 days of capital for about 1%), a retail preference for longshots, and makers'
    reluctance to sell 98c contracts into low-turnover books.

## 8. Strategy card (best candidate: E2; H99_6h is the short-lock-up analogue)
- **Signal:** one side of a binary market trades >= 0.95 (the other side <= 0.05) 7 days before the scheduled end (sports: before
  `gameStartTime`).
- **Entry:** taker-buy the favourite side, i.e. the economic "buy NO" against the overpriced longshot, if the all-in cost (ask + fee)
  is <= 0.999 and below about 0.985. Size <= $500 per market. Diversify across many events and days. H99_6h is the same structure:
  side >= 0.99 at 6 hours.
- **Exit:** hold to resolution; redemption at `closedTime` (PLAUSIBLE: payout is available about at closedTime). No stop-loss: the
  books near resolution are too thin to exit a collapsing favourite.
- **Data:** Gamma `endDate` / `gameStartTime`, outcomes and fee fields; the CLOB best ask, or `/prices-history` plus a spread model,
  at T-7d (or T-6h). A live system would need the live book, because series prices are not executable.
- **Holding period:** E2 median 7.3 days (mean 8.2; p99 tail of more than 30 days via settlement delay); H99_6h median 0.66 days.
- **Why it might persist (PLAUSIBLE):** capital lock-up and tail-risk aversion, longshot preference, and low maker competition in
  thin long-dated books.
- **Main reason it might fail:** rare-event risk. The edge is +1.0% per trade against a break-even loss rate of about 1.4%, and the
  95% upper bound on the observed loss rate (1.7-1.9%) exceeds break-even. Bucketed numeric markets (weather, counts, macro prints)
  supply the 98-99c losers. Validation in W was negative.
- **Forward test needed:** paper-trade E2 and H99_6h on live asks (not mids) for 3+ months, logging every fill, loss and settlement
  delay.
  - Kill E2 if the cumulative loss rate exceeds 1.4% after 300 trades.
  - Kill H99_6h if it exceeds 0.35% after 500 trades.

## 9. Deviations, clarifications and post-hoc work (declared)
**Implementation clarifications (the pre-registration did not specify these):**
- The H1 effective-spread cell is used whenever it exists (no minimum n). A-7d has no H1 TTR cell, so it falls back to H3.
- The f <= 0.999 feasibility filter uses each sample's primary cost. The 2x variants are computed even if they exceed 0.999.
- E2 is implemented as "favourite side priced >= 0.95", which is identical to "longshot <= 0.05" by complement.
- Side prices are rounded to 4 dp. R_gross is undefined below m = 0.0005.
- Volume terciles are unweighted within sample x split.
- Calibration CIs use 2,000 bootstrap replicates (rules use 4,000).
- ICC is an unweighted one-way ANOVA.
- Verdict precedence: promising > rejected > marginal > NDE. Criterion 8 with n < 100 counts as n/a (not a failure).

**Bug fixes before the final run:** tape dtype cast; NaN guard on two-request markets; deterministic bootstrap seeds (crc32 instead of
Python's salted `hash`); `n_chg_24h` counted cumulatively across tokens when the series started less than 24h before the horizon
(fixed; the field is used only in 9.2). None affects a pre-registered statistic, and the verdicts were identical before and after
the reruns.

**Post-hoc diagnostics** (`05_posthoc.py`; NOT pre-registered; none changes a verdict):
1. **Look-ahead selection by full-life volume.** Within W TEST, E1-type favourites (0.80-0.95 at A-1d) realise **-9.1pp
   [-14.9, -3.8]** versus price when the market's final volume was >= $10k, +1.9pp at $1k-10k and +2.5pp [+0.5, +4.3] below $1k.
   Markets with upsets attract late volume. The `volumeNum >= $10k` screen used by P (and by the panel) therefore biases
   favourite-buying returns down, and low-volume subsets are biased up. PLAUSIBLE, strongly supported. It explains P's
   "reverse FLB" and means P is not a clean primary sample for favourite strategies. E2 is robust to it: W TEST at final volume
   >= $10k still gives +1.35% (base) / +0.58% (conservative). H99_6h is weaker there (+0.37% / +0.09%).
2. **Decision-time activity tercile** (price changes in the 24h before entry; no look-ahead).
   - E2 is positive in every tercile in both samples at base cost: P +0.95% / +1.59% / +0.55%; W +2.41% / +1.64% / +1.67%.
   - H99_6h is positive in every tercile (W about +0.5%; P +0.34% / +0.04% / +0.43%).
   - E1 is negative in every P tercile.
3. **Rare-loss fragility:** see section 4.
4. **Capacity scenarios:** see section 6.

**Not modelled:** maker execution (it would avoid the half-spread, but carries fill risk and adverse selection on favourites near
resolution); taker rebates; tick-size changes near the extremes. `orderPriceMinTickSize` is the post-resolution value, and a 0.01-tick
book cannot quote 0.995. Only token-0 series were pulled; token-1 prices are 1 - p0 (books mirrored, VERIFIED in panel.md).
