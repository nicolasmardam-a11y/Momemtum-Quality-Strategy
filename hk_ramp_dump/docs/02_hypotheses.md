# Deliverable 2: Five falsifiable hypotheses, ranked

Ranking = (probability the effect is statistically identifiable with daily
data) x (probability it can be monetised at realistic size). Each hypothesis
states what would refute it, and was written before any model was fitted.

All thresholds are hypotheses, evaluated out of sample with the purged
walk-forward in `src/hkrd/validation.py`. "Run-up state" = stage-1 filter:
20-day return >= +50% and 20-day mean traded value >= 3x its prior 120-day
median.

---

## H1: Distribution after a ramp predicts the collapse *(test first)*

**Claim.** Among stock-days in a run-up state, price and turnover patterns
visible at the close predict a >= 40% close-to-close drawdown within 20
trading days. The patterns: price >= 10% below the 20-day high, upper
wicks, value concentrated on down days, reversals on heavy volume, and
failed new highs. The prediction must come early: the first alert must leave
most of the decline ahead.

**Refuted if,** on pooled out-of-sample folds:
- PR-AUC is < 1.5x the run-up base rate, or precision in the top decile is
  not above the 95th percentile of random alerts; or
- the median share of the peak-to-trough decline still ahead at the first
  alert is < 50%. That would mean the model mostly confirms collapses
  already under way.

**Why first.** Every strategy depends on it, and it needs only daily
OHLCV, which we have. If H1 fails, nothing downstream is worth building.

## H2: Crash-risk avoidance improves a long small/mid-cap momentum book

**Claim.** Hong Kong momentum portfolios mechanically buy ramped stocks.
Two variants should raise net Sharpe by >= 0.10, or cut maximum drawdown by
>= 20%, at a cost of <= 1%/yr in return, with no shorting at all:
- exiting holdings when the model alerts (Strategy B);
- excluding the top crash-risk decile at rebalance (Strategy C).

**Refuted if** the improvement fails those bars out of sample, or the
block-bootstrap p-value of the daily return difference is > 0.10.

**Why second.** It is the only monetisation route that does not depend on
borrowing Hong Kong micro-caps. It also connects directly to the momentum
book this repository already runs.

## H3: "Unexplained" ramps collapse more often

**Claim.** Run-ups are more likely to end in category A when there is no
price-sensitive announcement during the run and the issuer publishes an
HKEX "unusual price and volume movements" clarification saying the board is
unaware of any reason. Free float and historical liquidity should also be
low. The collapse rate should be >= 1.5x that of run-ups with a dated
announcement (placing, acquisition, results, inside information).

**Refuted if** the collapse rate gap is < 1.5x with a bootstrap CI
spanning 1.0.

**Data needed.** HKEXnews headline categories with timestamps (free), plus
historical shares outstanding (Webb-site dump or Capital IQ). Not in the
pilot.

## H4: The shortable subset carries a negative drift that survives costs

**Claim.** For ramp alerts in stocks on the HKEX designated short-selling
list on the execution date, the short from the t+1 open has positive mean
net return after the following, with event-bootstrap 90% CI above zero:
- the stamp duty schedule, fees and spread;
- borrow at 1-20% a year;
- 2% ADV participation.

**Refuted if** the mean net return is <= 0, or the result depends on
fewer than five stocks for most of the P&L.

**Prior.** Weak. Designation requires market capitalisation of HK$3bn or
more and turnover/market-cap of 60% or more (HKEX criteria since 2016).
Classic ramp-and-dump vehicles are tiny, thinly traded and low-priced, so
they are rarely designated. The pilot event database confirms this (see
docs/01).

## H5: Ownership concentration predicts the dump

**Claim.** A rising share of issued shares held by the top-5 CCASS
participants during the run-up raises the collapse probability by >= 1.5x
at equal price/volume features. SFC ramp-and-dump cases repeatedly describe
shares parked with a few nominee brokers.

**Refuted if** adding CCASS concentration features does not raise OOS
PR-AUC by >= 10% relative over the H1 model.

**Data needed.** Daily CCASS participant holdings history. Webb-site
archived it from 2007; HKEX's own search only covers 12 months. Not in the
pilot.

---

## Order of work

1. **H1 on daily data** (this pilot). It is the go/no-go for the whole programme.
2. **H2** on the same predictions: zero extra data cost, and the most
   plausible route to money.
3. **H4** only as a capacity and feasibility check. Do not expect it to
   pass.
4. **H3 and H5** only if H1 shows real but modest signal and the Webb-site
   dump is loaded: they add information that daily prices cannot carry.
