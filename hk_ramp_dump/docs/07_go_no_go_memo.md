# Deliverable 8: GO / NO-GO investment research memo

**To:** Investment Committee
**Re:** Ramp-and-dump predictability in HKEX equities
**Date:** 2026-10-28
**Data:** daily OHLCV for 2,758 current HKEX listings (2012-01 to
2026-10-27) and 631 historical HKEX designated short-selling lists. Pilot
only: survivorship-biased (see section 6).

## 1. Decision

| Strategy | Pre-registered verdict (holdout 2024-07 to 2026-10) | Recommendation |
|---|---|---|
| A: short suspected ramps | **NO-GO** (fails 8 of 10 criteria) | Stop. Do not fund intraday or borrow data for this. |
| B: early-warning exits on a long book | **GO** (criteria met; not statistically significant) | Paper-trade only. **No capital** until a survivorship-free re-test and 12 months of live paper results. |
| C: crash-risk ranking / avoidance | **NO-GO: statistically interesting but not tradable** | Use as a **risk screen**, not a return source. |
| D: go long the ramps *(added after the holdout, exploratory, not pre-registered)* | **No** (−5% to −11% net per trade in every variant, dev and validation) | Do not pursue. |

**Prediction itself: passes.** Models C and D clear every pre-registered
statistical criterion on the untouched holdout. The rules model (A) and
the HMM (B) do not.

**Bottom line.** Ramp-and-dump collapses in Hong Kong are *statistically
identifiable* from daily data. The predictability sits almost entirely in
stocks that cannot be shorted, and the right-skewed survivors cancel the
crashes in the mean. It is a risk-management signal, not an alpha source.

## 2. The phenomenon is real and frequent

- 4,923 abnormal run-up episodes in 1,574 stocks; 1,434 followed by a
  >= 40% collapse within 20 days (category A), about 108 a year since 2016.
- Median category-A run-up +179%, then a median −51% within 20 days.
- The detector recovers the SFC-documented Wan Cheng (8291) episode. The
  price peaked 2021-04-21, two days before the end of the SFC's alleged
  manipulation period, and fell 89% by 2021-05-11.
- **Only 7.6% of category-A events since 2016-05 were on the HKEX
  designated short-selling list at the peak.** Designation requires
  roughly HK$3bn market capitalisation and >= 60% annual turnover. Ramp
  vehicles are small by construction. This mismatch is the central
  economic fact.

## 3. Prediction: identifiable, but not where the mandate expected

Population: stock-days already in a run-up (20-day return >= 50%, value
>= 3x baseline). Their base crash rate is 8%, about 7x the unconditional
rate.

| | PR-AUC lift over base rate | Top-decile precision vs. base |
|---|---|---|
| D two-stage, dev OOS 2016 to 2022 | 1.92 | 18.5% vs 7.8% |
| D two-stage, validation 2023 to 2024H1 | 2.20 | 24.0% vs 10.2% |
| **D two-stage, holdout 2024H2 to 2026** | **2.32** | **22.1% vs 8.0%** |
| C LightGBM, holdout | 2.35 | 21.3% vs 8.0% |
| A rules ("distribution checklist"), holdout | 1.05 | 9.6% vs 8.0% |

- Model D's lift is positive in all 9 test periods, ranging from 1.35 (2018)
  to 2.74 (2017).
- When it fires on a category-A event, the alert is early: at or before the
  peak in 91% of cases (dev) and 98% (holdout), with a median 70-80% of the
  collapse still ahead.
- **H1 as framed is refuted.** The "distribution phase" signs carry no
  measurable signal: upper wicks, failed highs, down-day selling, reversals
  on volume. What predicts collapse is the *size* of the ramp (60-day
  return, the largest one-day jump) and the stock's *illiquidity* (Amihud,
  spread, zero-volume days, low price). The models learn "the more extreme
  and illiquid the ramp, the likelier the crash", not the timing of
  distribution.

## 4. Why it does not convert into returns

1. **The mean is not the median.** In the top-risk decile, the median path
   from the next open falls 9.3% in 20 days, but the mean 20-day return is
   −0.5%. The names that do not crash keep ramping: mean maximum adverse
   move +26%. Frictionless paper shorts of all alerts earn −0.4% on
   average (dev+val).
2. **Shortability.** 90% of alert opportunities were not designated. Of
   the rest, the alerted designated names did *not* fall on average in
   development (paper −1.1% at 20 days). Executed shorts lost 6.8% per
   trade net (90% CI −9.6% to −3.8%, 195 trades). In the holdout:
   - mean −0.8% (CI −4.0% to +2.6%);
   - the top 5 stocks made 195% of total profit;
   - every stress scenario was negative.
3. **Capacity.** Even ignoring losses, Strategy A deploys about
   HK$1-2.4m of gross exposure, independent of NAV. The binding
   constraint is borrowable opportunities, not capital.
4. **Costs are not the problem**, and that matters: lower commissions or
   better execution cannot rescue it. Round-trip explicit costs are about
   0.44%; the loss is in the gross price path.

**Going long the ramps fails too** (Strategy D, docs/05, tested after the
holdout on development and validation data only):
- buying run-up stocks for 20 days loses 7.8% to 11.1% per trade net;
- even with an optimistic minimum spread it loses 4.8% to 9.3%;
- that holds for the model's lowest-risk group as well.

The survivors' upside is a lottery-ticket mean (+2.6% for the low-risk
group) over a negative median (−2.9%). It does not cover the cost of
trading HK penny stocks. **Ramp stocks lose money from both sides; the
edge is avoiding them.**

## 5. What does work, modestly

- **The top crash-risk decile is a consistently terrible long.**
  - −32%/yr from 2016 to 2024H1 and −27%/yr in the holdout, net of costs;
  - negative in 11 of 12 calendar-year segments;
  - p < 0.01 in both periods.

  Any long book in HK small/mid caps should avoid it.
- For an equal-weight book that is worth only +1.2 to +1.7%/yr, because the
  decile is about 10% of names (Strategy C fails the +0.10 Sharpe bar).
- For a **momentum** book, which systematically buys ramps, the exit
  overlay matters more. Exiting on Model C alerts:
  - improved annual return by +2.2% (dev) and +3.9% (holdout);
  - cut maximum drawdown from −80% to −72% (dev) and from −40% to −30%
    (holdout);
  - beat random-exit placebos in both periods.

  This passes the pre-registered B criteria in the holdout. It is still
  **not statistically significant** (bootstrap p = 0.23 to 0.42), and the
  base momentum book lost money in every period.

**Relevance to the existing momentum-quality strategy:** the HK
small/mid-cap momentum top-50 lost 11.7%/yr (2016 to 2024H1) and 7.4%/yr
(holdout) in this pilot, with survivorship bias *in its favour*. If the
global book can hold HK small caps, the crash-risk score is a cheap,
low-regret exclusion filter. It is not a reason to add HK small-cap
exposure.

## 6. Biases and limits: direction and severity

| Issue | Direction | Severity |
|---|---|---|
| Current listings only (no delisted stocks) | Fewer events; the worst collapses (delisted after long suspension) are missing. Understates B/C benefits and the risk of a short being trapped in a suspended stock | **High.** Re-test on the Webb-site dump before any capital |
| No borrow history | Strategy A borrow is assumed. Real locates in designated small caps are probably worse | Medium. Cannot rescue A: it loses gross of borrow |
| Spreads estimated from daily OHLC | Real spreads in illiquid names are likely wider. Helps no strategy | Medium |
| Recycled stock codes / vendor errors | Partly handled by the quality mask (1,981 stock-days masked) | Medium |
| Current board lots used historically | Small effect on lot rounding | Low |
| Strategy B criteria had no significance test (my pre-registration gap) | B's GO is weaker than it reads | Noted; not changed after the fact |
| One pre-holdout code fix to the event definition (peak window), found by inspecting an SFC case; models re-run before the holdout | Affects event labels and grouping, not features or labels | Low; documented in git history |

## 7. Recommended next steps (ranked by value per cost)

1. **Load the Webb-site CC-BY dump.** It is free and survivorship-free, and
   adds issued shares and CCASS history. Re-run the identical pipeline:
   frozen code, frozen criteria, and the post-2024-07 period treated as
   already used. *Decision point:* if Strategy B or C loses its effect
   once delisted names are included, close the project.
2. **If B survives:** paper-trade the C-alert exit overlay for 12 months on
   whatever HK small/mid exposure the firm actually holds, using
   `scripts/daily_watchlist.py`. Promote to capital only if live alert
   precision stays above the random-alert 95th percentile and the overlay
   beats placebos.
3. **Test H3 and H5 cheaply.** Add HKEXnews headline flags (free; e.g.
   "unusual price/volume movement, board not aware of any reason") and
   CCASS concentration. They may sharpen the *illiquid* end of the
   ranking, which matters for avoidance, not shorting.
4. **Do not buy intraday or order-book data, or securities-lending data,
   for this programme.** The daily research found nothing that faster data
   could make shortable, so the US$10k-100k+ outlay has no expected
   payoff.

*All figures come from code in this repository run on the stated data.
None is illustrative. Simulated and research results only; not investment
advice.*
