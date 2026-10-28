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
| A ramp_dump | 1,434 | +179% | −51% | −61% | 6.0 | 6.3% |
| B sustained | 771 | +129% | −15% | −18% | 3.4 | 6.1% |
| C volatile | 2,667 | +133% | −28% | −40% | 4.4 | 6.8% |
| censored | 51 | | | | | |

- 1,574 distinct stocks had at least one episode. Category A runs at
  about 108 episodes per year since 2016.
- **Only 90 of 1,185 (7.6%) category-A events since the first archived
  designated-securities list (2016-05-03) were short-sellable at the
  peak.** 89 of those 90 had mean run-up value >= HK$5m/day.
- 766 A events had mean run-up traded value >= HK$5m/day and 362 had
  >= HK$20m/day. The rest are too thin to trade in size in any direction.
- At the first qualifying day, a median 73% of the eventual peak-to-trough
  decline is still ahead. The price is usually still rising, though, so a
  short at the first signal also bears the rest of the run-up (docs/04).
- 23% of A events started from a baseline with zero median traded value:
  dormant shells that suddenly trade.
- GEM is 21% of all episodes and 26% of A events.

**Survivorship caveat.** Codes delisted before 2026-10-28 are absent. Many
HK ramp targets are later suspended for 18+ months and delisted, so the
true A count, and especially the worst outcomes, is higher.

## Sensitivity

Share of episodes followed by a >= 40% drawdown within 20 days (value
multiple 5x), with episode count n:

| Run window | Run-up >= 50% | >= 80% | >= 150% |
|---|---|---|---|
| 5 days | 22% (6,680) | 35% (2,629) | 50% (670) |
| 10 days | 21% (8,295) | 32% (3,726) | 48% (1,063) |
| 20 days | 20% (9,411) | **29% (4,923)** | 42% (1,655) |

Primary definition (20d / +80% / 5x), varying what counts as the collapse:

| Collapse definition | A share | A count | Short-sellable A |
|---|---|---|---|
| >= 30% within 20d | 51% | 2,462 | 161 |
| >= 40% within 20d | 29% | 1,394 | 88 |
| >= 60% within 20d | 9% | 414 | 15 |
| >= 30% within 60d | 76% | 3,630 | 240 |
| >= 40% within 60d | 56% | 2,699 | 174 |
| >= 60% within 60d | 21% | 1,006 | 35 |

(The grid censors with the longest window, 60 days, so its A count, 1,394,
is slightly below the event database's 1,434.)

- Faster and larger run-ups collapse more often.
- The traded-value multiple barely matters once the run-up is large: 3x,
  5x and 10x give A shares of 28.8%, 29.1% and 30.1%.
- How often a "ramp-and-dump" occurs is mostly a definition choice. That is
  why the predictive work targets all three drawdown levels. Under every
  definition, short-sellable cases stay at 4-7% of the total.

Full grid: `outputs/research/sensitivity_grid.csv`; heat map:
`outputs/figures/sensitivity_heatmap.png`.

## Regulator-documented cases vs. statistical matches

`data/reference/sfc_cases.csv` holds hand-sourced SFC cases. The event
database flags `sfc_code_match` and `sfc_period_overlap`.

- **8291 (Wan Cheng Metal Packaging).** The SFC alleges manipulation from
  2020-12-22 to 2021-04-23. The detector finds two overlapping episodes
  under code 8291:
  - peak 2021-03-12 (C: +419% from 2021-01-11, then −9%);
  - peak **2021-04-21** (A: +206%, then **−89% by 2021-05-11**).

  The collapse starts two days before the end of the alleged period
  (`outputs/figures/cases_sfc.png`). Caveat: code 8291 now trades as "HK ENT
  INTL". Whether that is the same issuer renamed or a recycled code is not
  yet verified.
- The same code also shows A episodes in 2017 and 2018, which the SFC case
  does not cover. **A statistical match is not evidence of manipulation.**
  The database labels patterns, not misconduct.

## Figures

- `outputs/figures/events_by_year.png`: episodes per year by category,
  with clusters in 2015 (GEM mania), 2020-21 and 2024-26.
- `outputs/figures/cases_category_A.png`, `cases_category_B.png`,
  `cases_category_C.png`, `cases_sfc.png`: representative price and
  traded-value paths, marked with run start, first signal, peak and trough.
- `outputs/figures/sensitivity_heatmap.png`.
