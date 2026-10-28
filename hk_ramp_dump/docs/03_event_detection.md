# Deliverables 3 & 4: Event detection algorithm and event database

Code: `src/hkrd/events.py`. Run: `python scripts/run_research.py events`.
Output: `outputs/research/event_db.csv` (one row per episode),
`sensitivity_grid.csv`, `event_summary.json`, figures in `outputs/figures/`.

## Algorithm (daily data, fully reproducible)

Inputs: split-adjusted close, HK$ traded value, data-quality mask, and the
Hang Seng Index.

1. **Run-up day t.** Both conditions must hold:
   - `close_t / min(close_{t-L..t-1}) - 1 >= R`, in excess of the HSI's
     L-day return (floored at 0);
   - `mean(value_{t-L+1..t}) >= V x median(value_{t-L-120..t-L-1})`, with
     the baseline floored at HK$50k so dormant stocks do not divide by zero.

   Days within L+1 of a quality-masked print are excluded.
2. **Episode.** Run-up days less than 5 trading days apart merge.
   - `first_signal_date` is the first qualifying day: the earliest moment a
     causal rule could flag the episode.
   - The run start is the lowest close in the L-day window before it.
3. **Peak** is the highest close from the first qualifying day through L
   days after the last one. Prices often keep rising after turnover stops
   qualifying as abnormal; this was found by inspecting SFC case 8291.
   **Trough** is the lowest close in (peak, peak + W]. Both are hindsight
   quantities: they label the database and are never model inputs.
4. **Category:**
   - **A (ramp-and-dump pattern):** trough/peak - 1 <= -D.
   - **B (sustained repricing, price-path proxy):** max drawdown over the 60
     days after the peak is under 25%.
   - **C (volatile, no A-type collapse):** everything else.
   - **censored:** too little data after the peak.

Primary definition: L = 20, R = +80%, V = 5x, W = 20, D = 40%.

**Data-quality mask.** A one-day move within 3% (in logs) of a common
consolidation or split factor (2, 4, 5, 8, 10, 20, 25, 40, 50, 100), or any
|log return| > 2.5, is treated as a vendor adjustment error. It is masked
for ±2 days. In the pilot, 1,981 stock-days (about 400 incidents) were
masked. Without the mask, a missed 10-into-1 consolidation looks exactly
like a +900% ramp.

**What category B cannot do yet.** Separating genuine news-driven
repricing from manipulation needs timestamped announcements (HKEXnews). B
is defined by price path only. That is hypothesis H3, and it is not tested
in the pilot.

## Event database (pilot: 2,758 current listings, 2012-01 to 2026-10-27)

| Category | Episodes | Median run-up | Median max DD, 20d | Median DD, 60d | Median traded value in run (HK$m/day) | Designated short-sellable at peak |
|---|---|---|---|---|---|---|
| A ramp_dump | 1,265 | +171% | −51% | −60% | 5.3 | 6.0% |
| B sustained | 1,039 | +109% | −15% | −17% | 3.3 | 6.2% |
| C volatile | 2,582 | +124% | −28% | −40% | 4.4 | 6.7% |
| censored | 37 | | | | | |

- 1,574 distinct stocks had at least one episode. 1,265 category A episodes
  is about 98 per year since 2016.
- **Only 76 of 1,069 (7.1%) category-A events since the first archived DS
  list (2016-05-03) were on the designated short-selling list at the
  peak.** All 76 shortable A events across the sample had mean run-up value
  >= HK$5m/day.
- At the first qualifying day, a median 81% of the eventual peak-to-trough
  decline is still ahead. The price is usually still *rising*, though, so a
  short at the first signal also bears the rest of the run-up (see models).
- 24% of A events started from a baseline with zero median traded value:
  dormant shells that suddenly trade.
- GEM is 21% of all episodes and 26% of A events.

**Survivorship caveat.** Codes delisted before 2026-10-28 are absent. Many
HK ramp targets are later suspended for 18+ months and delisted, so the
true A count, and especially the worst outcomes, is higher.

## Sensitivity (post window 20d, drawdown 40%)

Share of episodes that become category A, with episode count n:

| Run window | Run-up >= 50% | >= 80% | >= 150% |
|---|---|---|---|
| 5 days, value x5 | 21% (6,680) | 32% (2,629) | 46% (670) |
| 10 days, value x5 | 19% (8,295) | 29% (3,726) | 44% (1,063) |
| 20 days, value x5 | 18% (9,411) | **26% (4,923)** | 39% (1,655) |

- Faster and larger run-ups collapse more often.
- The traded-value multiple barely matters once the run-up is large (3x
  vs 10x changes the A share by about 1 point).
- The A share swings from 7% (D = 60%) to 46% (D = 30%), and to 70% with a
  60-day window at D = 30%. "Ramp-and-dump" frequency is mostly a
  definition choice, so the predictive work targets all three drawdown
  levels.

Full grid: `outputs/research/sensitivity_grid.csv`; heat map:
`outputs/figures/sensitivity_heatmap.png`.

## Regulator-documented cases vs. statistical matches

`data/reference/sfc_cases.csv` holds hand-sourced SFC cases. The event
database flags `sfc_code_match` and `sfc_period_overlap`.

- **8291 (Wan Cheng Metal Packaging; SFC alleges manipulation 2020-12-22 to
  2021-04-23).** The detector finds episodes under code 8291 peaking
  2021-01-27 (C: +209%, then −28%) and 2021-04-01 (A: +150%, then −83%),
  both inside the alleged window. Caveat: code 8291 now trades as "HK ENT
  INTL". Whether that is the same issuer renamed or a recycled code is not
  yet verified.
- The same code also shows A episodes in 2017 and 2018, which the SFC case
  does not cover. **A statistical match is not evidence of manipulation.**
  The database labels patterns, not misconduct.

## Figures

- `outputs/figures/events_by_year.png`: episodes per year by category,
  with clear clusters in 2015 (GEM mania), 2020-21 and 2024-26.
- `outputs/figures/cases_category_A.png`, `cases_category_B.png`,
  `cases_category_C.png`, `cases_sfc.png`: representative price and
  traded-value paths, marked with run start, first signal, peak and trough.
- `outputs/figures/sensitivity_heatmap.png`.
