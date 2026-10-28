# Deliverable 5: Predictive models and out-of-sample metrics

Code: `src/hkrd/models.py`, `src/hkrd/validation.py`. Run:
`python scripts/run_research.py models`. Outputs: `outputs/research/`.

## Setup

**Target.** `dd20_40`: the minimum close over t+1..t+20 is at least 40%
below close t. Secondary targets are 20% and 30%. Labels are NaN when the
20-day window is incomplete, never 0.

**Populations.**
- *all*: 5.19M eligible stock-days. A day is eligible if it traded, has
  >= 140 days of history, and no quality-masked print within ±21 days.
- *candidate*: the stage-1 run-up state, 20-day return >= 50% and 20-day
  value ratio >= 3x. That is 84,126 stock-days (1.6%).

| Base rates | all | candidate |
|---|---|---|
| P(>= 20% drop in 20d) | 9.1% | 34.6% |
| P(>= 30% drop) | 3.0% | 17.3% |
| P(>= 40% drop) | 1.13% | 8.2% |

The run-up state alone raises the 40% crash rate about 7x. Every model
below must beat that conditional base rate, not the unconditional one.

**Features.** 37 causal features (`src/hkrd/features.py`, unit-tested by
perturbing future data):
- *price:* returns over 1/3/5/10/20/60 days; acceleration; distance from
  MA20/MA60 and from 20/60-day highs; days since the high; overnight gap;
  intraday return; close location and upper wicks; realised-vol regime;
  largest one-day jump; excess return vs HSI;
- *liquidity:* traded-value ratios and z-score; value trend; value per unit
  of price move; down-day value share; Amihud illiquidity; zero-volume
  days; Abdi-Ranaldo spread; tick size / *traded* price; log price;
- *distribution hypotheses:* failed new highs, reversals on volume, heavy
  volume near the high, drawdown from the run peak.

**Validation.**
- Expanding-window walk-forward: test years 2016 to 2022, then a validation
  block (2023-01 to 2024-06).
- Training rows are purged 21 trading days before each test start, which
  covers the 20-day label.
- Event grouping: a ramp episode that straddles the train/test boundary is
  removed from training.
- Alert thresholds are the 90th percentile of each model's scores on
  *training* candidates, never set on the test data.
- The holdout (2024-07 to 2026-10) is locked in code until
  `run_holdout.py` verifies the pre-registration commit.

**Models.**
- **A, rules.** Run-up state x (1 + count of five distribution warnings).
  Calibrated by empirical frequency per score level.
- **B, regime.** 3-state Gaussian HMM on (return, value ratio, close
  location), fitted on training data. Test-time state probabilities come
  from a causal forward filter run date by date: no smoothing. A logistic
  regression maps them to risk.
- **C, LightGBM, all stock-days.** Negatives subsampled at 10% and
  re-weighted.
- **D, two-stage.** Stage 1 is the run-up filter; stage 2 is LightGBM on
  candidates only.

## Results: candidate population, target dd20_40

Development OOS = pooled test years 2016 to 2022 (32,379 candidate rows,
2,512 crashes). Validation = 2023-01 to 2024-06 (8,030 rows, 819 crashes).

| Model | Period | Base rate | PR-AUC | PR-AUC lift | ROC-AUC | Precision, top 10% | Random top-10% p95 | Brier vs base-rate Brier |
|---|---|---|---|---|---|---|---|---|
| A rules | dev OOS | 7.8% | 0.077 | **0.99** | 0.50 | 7.8% | 8.5% | 0.0717 vs 0.0716 |
| B HMM | dev OOS | 7.8% | 0.081 | 1.05 | 0.52 | 5.6% | 8.5% | 0.0732 vs 0.0716 |
| C LightGBM | dev OOS | 7.8% | 0.151 | **1.94** | 0.69 | **17.8%** | 8.5% | 0.0706 vs 0.0716 |
| D two-stage | dev OOS | 7.8% | 0.149 | **1.92** | 0.70 | **18.5%** | 8.5% | 0.0714 vs 0.0716 |
| A rules | validation | 10.2% | 0.101 | 0.99 | 0.49 | 9.3% | 11.7% | 0.0922 vs 0.0916 |
| B HMM | validation | 10.2% | 0.142 | 1.39 | 0.61 | 15.2% | 11.7% | 0.0956 vs 0.0916 |
| C LightGBM | validation | 10.2% | 0.199 | 1.95 | 0.71 | 23.2% | 11.7% | 0.0879 vs 0.0916 |
| D two-stage | validation | 10.2% | 0.224 | **2.20** | 0.72 | **24.0%** | 11.7% | 0.0872 vs 0.0916 |

**Stability.** Model D's PR-AUC lift by test year was 2.25, 2.74, 1.35,
2.47, 1.86, 1.83 and 2.25 (2016 to 2022), then 2.20 in validation. It is
above 1 in every period; 2018 is the weak year. Model A is 0.93 to 1.10
every year: no signal.

**All stock-days (Model C).** ROC-AUC is 0.82 and PR-AUC lift 5.2 (dev) /
5.7 (validation). Most of that is the easy part, telling run-ups from
ordinary days. The candidate-population numbers are the honest ones.

**Calibration.** Model D's top decile predicts 29.6% on average; 18.5%
happen. The model ranks well but is over-confident at the top. Use it for
ranking, or recalibrate isotonically on a trailing window before reading
probabilities literally (`outputs/research/calibration_candidates.csv`,
`outputs/figures/calibration_candidates.png`).

## What the models actually learned

Model D, top features by gain (validation fold):

| Feature | Share |
|---|---|
| `ret_60` | 14% |
| `max_ret_1_in_20` | 10% |
| `vol_ratio_20_120` | 7% |
| `amihud_60` | 7% |
| `spread_ar_20` | 6% |
| `dist_ma60` | 5% |
| `zero_days_120` | 5% |
| `log_price` | 4% |

**What predicts a collapse is how extreme the ramp is (60-day run, the
largest single-day jump, volatility regime) and how illiquid the stock is
(Amihud, spread, zero-volume days, low price).** The "distribution phase"
signs from the mandate do not contribute measurably: upper wicks, failed
highs, down-day selling, reversals on volume. That is why the transparent
Model A, built entirely on those signs, has no lift. **H1 as framed (the
distribution pattern) is refuted. A weaker form holds: ramp magnitude plus
illiquidity predicts collapse.**

## Early warning vs. late confirmation

For category-A episodes inside the dev and validation test windows (724
episodes):

| Model | Alerted between run start and trough | First alert at or before peak | Median share of decline still ahead | Median return, alert close to trough |
|---|---|---|---|---|
| A rules | 43% | 76% | 59% | −41% |
| B HMM | 61% | 60% | 41% | −35% |
| C LightGBM | 62% | 76% | 53% | −42% |
| D two-stage | 49% | **91%** | **70%** | **−46%** |

Model D's alerts are genuinely early when they fire. They come at or before
the peak in 91% of cases, with a median 70% of the collapse still ahead.
But it catches under half of the episodes.

## Conditional outcomes by predicted risk (Model D, candidates, dev OOS)

| Decile | Mean p | Realised P(>= 40% drop) | Mean 20d return | Median return, t+1 open to t+20 close | Mean max adverse move (20d) | Median days to a 20% drop |
|---|---|---|---|---|---|---|
| 1 (low) | 0.7% | 1.7% | +2.4% | −2.3% | +15% | 11 |
| 5 | 3.6% | 5.4% | +0.7% | −4.9% | +19% | 9 |
| 9 | 14.5% | 14.0% | 0.0% | −7.8% | +24% | 7 |
| 10 (high) | 29.6% | 18.5% | **−0.5%** | −9.3% | **+26%** | 7 |

**This table is where prediction and profit part ways.** The top-risk
decile crashes at 2.2x the base rate, and its *median* path falls 9%. Yet
its *mean* 20-day return is only −0.5%. The names that do not crash keep
ramping, with a mean maximum adverse move of +26% in 20 days. A short book
earns the mean, not the median, so the right-skew of the survivors cancels
the crashes. See docs/05.

## Holdout (2024-07-01 to 2026-10-27, opened once)

Models were refitted on all data up to 2024-05-30 (purged) and scored on
1.03M holdout stock-days (25,248 candidate rows, 2,007 crashes).

| Model | Base rate | PR-AUC lift | ROC-AUC | Precision, top 10% | Random p95 | Brier vs base | Pre-registered prediction criteria |
|---|---|---|---|---|---|---|---|
| A rules | 7.9% | 1.05 | 0.51 | 9.6% | 8.8% | 0.0732 vs 0.0732 | **fail** |
| B HMM | 7.9% | 1.16 | 0.55 | 12.5% | 8.8% | 0.0750 vs 0.0732 | **fail** |
| C LightGBM | 7.9% | **2.35** | 0.71 | **21.3%** | 8.8% | 0.0707 vs 0.0732 | **pass** |
| D two-stage | 7.9% | **2.32** | 0.72 | **22.1%** | 8.8% | 0.0702 vs 0.0732 | **pass** |

Early warning in the holdout (454 category-A events):

| Model | Alerted | First alert at or before peak | Median share of decline still ahead |
|---|---|---|---|
| C LightGBM | 71% | 93% | 53% |
| D two-stage | 58% | 98% | 80% |

The statistical result replicates out of sample. Whether it can be
monetised is a separate question (docs/05, docs/07).
