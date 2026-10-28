# Deliverable 6: Execution-aware backtests

Code: `src/hkrd/backtest.py`, `src/hkrd/strategies.py`, `src/hkrd/runners.py`.
Run: `python scripts/run_backtests.py` (development + validation), then
`python scripts/run_holdout.py` (once).

**Periods.**
- Development OOS: Strategy A 2016-05-03 to 2022-12-31 (the first archived
  short-selling list is 2016-05-03); Strategies B/C 2016-01 to 2024-06.
- Validation: 2023-01 to 2024-06.
- Holdout: 2024-07-01 to 2026-10-27. Every signal comes from a model
  trained only on data before its test window.

## Engine: what is modelled

| Constraint | Implementation |
|---|---|
| Signal timing | Close of t; earliest execution is the t+1 opening auction. Stress: +1 and +2 days of delay |
| Short-sale eligibility | HKEX designated list **in force on the fill date** (631 archived lists). No list = not shortable |
| Tick rule | Shorts are filled in the continuous session at a VWAP proxy (O+H+L+C)/4, not at the auction; fills are halved on down days |
| Borrow | Locate failure: 2% / 15% / 50% for large / mid / small ADV tiers; fees 1% / 5% / 20% a year accrued by calendar day; recall probability 0.5% a day. **Assumptions, not data**; stressed at 2x and 4x |
| Liquidity | Fill <= participation x min(ADV20 known at t, that day's value). Partial fills carry over; entries expire after 3 days |
| Board lots | Whole lots only (current lot sizes: pilot limitation) |
| Ticks | HKEX spread table in force on the date (2025 and 2026 reductions included), applied to the *traded* price, with rounding against the trader |
| Spread and impact | Half-spread = max(half a tick, Abdi-Ranaldo / 2) x stress multiplier; impact = sigma20 x sqrt(fill / day value) |
| Statutory costs | Stamp duty 0.10% / 0.13% (2021-08 to 2023-11) / 0.10% on **both** sides; trading fee, SFC levy, AFRC levy, settlement fee, brokerage 8 bp (min HK$50) |
| Suspensions | No fill on zero-volume days. Exits wait; positions are marked at the last price, so the gap is paid on resumption |
| Stops | Evaluated on the close, executed at the next open. Gaps through the stop are paid in full |
| Sizing | 2% of NAV per name, gross <= 50%, <= 25 names; NAV HK$50m base, HK$10m and HK$200m tested |

Portfolio strategies (B, C) use a weight engine:
- monthly equal-weight rebalances;
- targets take effect from close t+1, one extra day of lag;
- stocks that do not trade cannot be changed, so suspensions trap exits;
- cost per unit of turnover is explicit costs plus the half-spread.

An independent recomputation of the equal-weight investable universe gave
−4.8%/yr gross, against the engine's −6.1%/yr net for 2016 to 2024H1.

## Strategy A: short suspected ramps

**Opportunity funnel** (selected configuration, dev + validation, 2016-05 to 2024-06):

| Step | Count |
|---|---|
| Alert stock-days | 6,017 |
| Distinct stock-month opportunities | 2,328 |
| Not on the designated list | 2,087 (90%) |
| Locate failed (assumed) | 42 |
| No liquidity | 6 |
| **Executed trades** | **195 (8% of opportunities), about 24 a year** |
| Average gross capital deployed on a HK$50m book | **HK$1.06m (2.1%)** |

**Pre-registered grid** (3 models x 3 holding periods x 2 stops, plus
naive and random baselines). Development OOS mean net return per trade:

| Signal | Range across hold/stop settings |
|---|---|
| A rules | −8.3% to −7.3% |
| B HMM | −6.7% to +3.7% |
| C LightGBM | −13.3% to −5.3% |
| D two-stage | −8.0% to −2.8% |
| Naive (20-day run >= 100%) | −8.4% to −7.2% |
| Random candidates | −8.0% to −6.3% |

Only 2 of 36 model configurations are positive in development. In
validation only Model A produced >= 20 trades, so the pre-registered rule
selected **A rules, 20-day hold, 30% stop**: mean −2.0% on 28 validation
trades.

**Stress tests, selected configuration** (dev + validation, 2016-05 to 2024-06):

| Scenario | Trades | Mean net per trade | 90% event-bootstrap CI | Sharpe |
|---|---|---|---|---|
| Base (2% ADV, HK$50m) | 195 | **−6.8%** | [−9.6%, −3.8%] | −1.02 |
| 1% ADV | 192 | −7.5% | [−10.4%, −4.5%] | −0.99 |
| 5% ADV | 197 | −6.4% | [−9.1%, −3.4%] | −0.88 |
| Spreads x2 | 206 | −10.7% | [−13.8%, −7.5%] | −1.49 |
| Spreads x3 | 207 | −14.1% | [−17.5%, −10.6%] | −2.01 |
| Borrow x2 | 195 | −7.2% | [−10.0%, −4.3%] | −1.05 |
| Borrow x4 | 195 | −8.1% | [−10.9%, −5.3%] | −1.11 |
| +1 day delay | 198 | −5.9% | [−8.9%, −2.9%] | −0.92 |
| +2 days delay | 197 | −4.7% | [−7.6%, −1.8%] | −0.65 |
| Combined severe | 194 | −9.6% | [−12.7%, −6.6%] | −1.38 |

Explicit costs average 0.44% per round trip and borrow 0.45%. **The loss
is in the gross price path**, not in costs: −6.4% mean gross. Designated
names that alert keep rising on average. 30% stops, triggered on the close
and executed at the next open, realise around −55% on the worst squeezes.

**Statistical vs. executable (frictionless paper shorts from the t+1 open):**

| Period | Alerts | Mean 20d short return | Median |
|---|---|---|---|
| Dev+val, all alerts | 6,017 | **−0.4%** | +5.7% |
| Dev+val, designated only | 569 | **−1.1%** | +3.9% |
| Holdout, all alerts | 2,660 | −5.5% | +4.6% |
| Holdout, designated only | 273 | +5.6% | +6.1% |

The median short wins; the mean short does not. Squeezes in the stocks
that keep ramping cancel the collapses. The designated subset flips sign
between periods: noise around zero.

**Holdout (selected configuration):**
- 107 trades in 95 stocks; mean net −0.8%, median +2.1%, win rate 58%,
  payoff ratio 0.67.
- Bootstrap CI [−4.0%, +2.6%]; Sharpe 0.10.
- Total +HK$0.85m, but the top 5 stocks are 195% of it; excluding them,
  −HK$0.81m.
- Average capital deployed: HK$2.3m.
- Stress means: spread x2 −4.7%, borrow x2 −1.2%, +1 day −1.9%.
- **Fails 8 of 10 pre-registered criteria → NO-GO.**

## Strategy B: early-warning liquidation on a long book

**Base book:** top-50 HK names by 120-day momentum (skipping 5 days) among
investable stocks (ADV20 >= HK$5m, traded price >= HK$0.50), equal weight,
monthly. **Overlay:** sell a holding the day after a crash alert and do not
re-buy for 20 days; the cash waits for the next rebalance.

| Period | Variant | Ann. return | Vol | Sharpe | Max DD | Avg. exposure |
|---|---|---|---|---|---|---|
| Dev+val 2016 to 2024H1 | Momentum top-50 | −11.7% | 25.1% | −0.37 | −79.6% | 0.99 |
| | + exit on C alerts | **−9.5%** | 20.3% | −0.39 | **−71.6%** | 0.82 |
| | + exit on D alerts | −11.4% | 23.2% | −0.41 | −75.4% | 0.93 |
| Holdout 2024H2 to 2026 | Momentum top-50 | −7.4% | 34.0% | −0.05 | −39.9% | 0.96 |
| | + exit on C alerts | **−3.5%** | 26.3% | 0.00 | **−29.7%** | 0.71 |
| | + exit on D alerts | **−0.5%** | 29.4% | **0.13** | −30.2% | 0.81 |

**Pre-registered verdict, holdout: GO for both variants.** Both clear
"Sharpe +0.10 or max-drawdown reduction >= 20%, with <= 1%/yr return
cost". *But note:*
- Block-bootstrap p-values against the base book are 0.42 (C) and 0.23
  (D). The pre-registration for B did not require significance, which in
  hindsight is a weakness of my own criteria.
- In development the C overlay improved return by 2.2%/yr and drawdown by
  10%, but not Sharpe. The D overlay did nothing.
- **The base book loses money in every period.** HK small/mid-cap price
  momentum without a quality screen has been a poor strategy in this
  sample, even with survivorship bias in its favour.

**Post-hoc placebo test** (`scripts/robustness.py`, not part of the
verdict). Random exits matched to the same number of new exit events per
day, 20 seeds:

| Period | Overlay | Real ann. return | Placebo mean | Placebos beating real on return / Sharpe / max DD |
|---|---|---|---|---|
| Dev+val | C alerts | −9.5% | −12.3% | 0% / 5% / 0% |
| Dev+val | D alerts | −11.4% | −11.7% | 35% / 75% / 0% |
| Holdout | C alerts | −3.5% | −6.1% | 15% / 30% / 0% |
| Holdout | D alerts | −0.5% | −8.5% | 0% / 0% / 0% |

The C-alert overlay beats random exits in both periods, so the benefit is
not just lower exposure. The D-alert overlay beats them only in the holdout.

## Strategy C: cross-sectional crash-risk ranking

Investable universe (about 490 names in dev, about 620 in holdout), ranked
monthly by Model C's probability.

| Period | Portfolio | Ann. return | Sharpe | Max DD |
|---|---|---|---|---|
| Dev+val | Equal-weight investable | −6.1% | −0.20 | −61% |
| | Excluding the top-risk decile | −4.9% | −0.15 | −61% |
| | **Top-risk decile only** | **−32.1%** | −1.12 | −96% |
| | Long low-risk / short designated top-risk (50/50) | −10.6% | −0.99 | −65% |
| Holdout | Equal-weight investable | +3.2% | 0.26 | −33% |
| | Excluding the top-risk decile | +4.9% | 0.32 | −31% |
| | **Top-risk decile only** | **−27.4%** | −0.57 | −67% |
| | Long low-risk minus 2800.HK | −9.5% | −0.79 | −26% |
| | Long low-risk / short designated top-risk (50/50) | −5.0% | −0.28 | −20% |

- **Top-decile return by year** (`outputs/robustness/`): negative in 11 of
  12 calendar-year segments (2024 is split between dev and holdout); only
  2020 is positive. Equal-weight returns ranged from −24% to +26% over the
  same years.
- 2016 to 2024: −26%, −30%, −42%, −35%, +15%, −8%, −33%, −55%, −36%.
- Holdout: −10% (2024H2), −6% (2025), −44% (2026 YTD).
- Block-bootstrap p-value for the top decile underperforming: < 0.01 in
  both periods.

**Pre-registered verdict: NO-GO, statistically interesting but not
tradable.**
- Excluding the top decile adds only +1.2%/yr (dev) and +1.7%/yr (holdout);
  the Sharpe gain is +0.05 / +0.07 against the +0.10 bar, p = 0.06 / 0.14.
- The decile that collapses holds about 10% of an equal-weight book.
- The obvious monetisation, shorting it, fails: the shortable part of the
  top decile does not fall. Long/short loses 10.6%/yr (dev) and 5.0%/yr
  (holdout).

## Strategy D: go long the ramps (added after the holdout; exploratory)

*Added at the user's request after the holdout had been opened. The holdout
therefore cannot validate it; only development OOS and validation data are
used. It is not part of the pre-registered verdict.*
Script: `scripts/strategy_d_long_ramps.py`.
Output: `outputs/post_holdout/strategy_d_long_ramps.csv`.

**Idea.** The run-up names that do not crash keep rising (mean worst move
against a short is +26% in 20 days), so buy them, preferably the ones the
model rates low crash risk.

**Design.**
- Universe: candidate (run-up state) stock-days, split by Model D's
  out-of-sample crash probability, ranked within each walk-forward fold.
- Buy at the t+1 open with the same engine as Strategy A (ticks, lots,
  participation caps, HKEX costs, suspensions).
- Hold 20 trading days; 30% stop on the close, executed at the next open.
- HK$50m NAV, 2% per name.

| Group | Period | Paper mean (t+1 open to t+20) | Paper median | Trades | Net per trade, estimated spread | 90% CI | Net, tick-only spread (optimistic) | 90% CI | Win rate |
|---|---|---|---|---|---|---|---|---|---|
| Low risk (bottom 30%) | dev 2016-22 | +2.6% | −2.9% | 845 | **−7.8%** | [−9.4%, −6.4%] | **−5.1%** | [−6.7%, −3.6%] | 29% |
| Low risk | val 2023-24H1 | −2.0% | −6.4% | 264 | −7.7% | [−11.1%, −3.8%] | −4.8% | [−8.8%, −0.6%] | 27% |
| All run-ups | dev | +0.5% | −5.2% | 914 | −9.0% | [−10.3%, −7.6%] | −5.8% | [−7.3%, −4.1%] | 29% |
| All run-ups | val | −1.3% | −7.3% | 260 | −10.8% | [−13.7%, −7.8%] | −8.5% | [−11.4%, −5.4%] | 24% |
| High risk (top 30%) | dev | −1.2% | −8.3% | 676 | −11.1% | [−13.9%, −7.9%] | −9.3% | [−11.9%, −6.4%] | 27% |
| High risk | val | −1.2% | −7.8% | 271 | −10.1% | [−14.7%, −5.4%] | −8.0% | [−13.0%, −2.9%] | 30% |

At 5% ADV participation the results are similar (−8% to −12%).

**Where the money goes** (low-risk group, dev, estimated spread):
- the paper mean is +2.6%;
- the engine's gross result is −6.4%, after spread and impact on entry and
  exit, tick rounding on penny stocks, stops that gap through, and fills
  concentrated on liquid days;
- explicit costs take a further 1.4%, higher than for shorts because the
  HK$50 minimum brokerage bites on small tickets;
- net: −7.8%.

With the optimistic tick-only spread, net is still −5.1%.

**Result.** Buying run-ups loses money in every group, period, spread
assumption and participation level. The crash-risk model does order the
outcomes correctly: low risk loses least, high risk most. But even the
best group cannot overcome the trading cost of illiquid, volatile, low-priced
stocks, whose typical (median) path from entry is already negative.
**Verdict: no.** Ramp stocks lose money in both directions once
implementation is honest. The only usable edge is avoiding them (B, C).

## Capacity

Strategy A deploys HK$0.3m (NAV HK$10m) to HK$2.4m (NAV HK$200m) on
average. Deployment is constrained by the number of designated and
borrowable opportunities, not by NAV. Its realistic capacity, even if it
were profitable, is a few million HK dollars of gross exposure. Strategies
B and C are overlays on an existing long book. Their capacity is the book's
capacity in the ADV >= HK$5m universe, cut by the 20-30 alerted names a
month that must be exited.
