# Deliverable 7: Live monitoring design

`scripts/daily_watchlist.py` produces a daily risk-ranked watchlist. It is a
research monitor: it never connects to a broker or places orders.

## Schedule (Hong Kong time)

| Time | Step |
|---|---|
| 16:10 | Closing auction ends; the day's bars are final |
| 17:30 | `python scripts/daily_watchlist.py --refresh` refreshes prices, the HKEX securities list and the latest designated short-selling list |
| 17:35 | Features are computed on the close of t, using only data <= t |
| 17:36 | Models are scored; the watchlist is written to `outputs/watchlist/<date>.csv` and `latest.md` |
| next day 09:00 | Earliest action: pre-opening auction (exits), or the continuous session (any short, tick rule) |

Models are refitted monthly (`--retrain`, or automatically when the saved
models are over 30 days old). They use every label-complete row: the last
20 trading days have no complete label and are excluded.

## Watchlist fields

| Field | Meaning |
|---|---|
| code, name, board | Identity (Main Board / GEM) |
| timestamp | `YYYY-MM-DD 16:10 HKT (close)`: the information cut-off |
| close, ret_20, value_ratio_20 | Traded price, 20-day return, 20-day traded value / prior 120-day median |
| rule_score, warnings | Model A score and which distribution warnings fired: `off_high_10pct`, `upper_wicks`, `selling_on_down_days`, `reversal_on_volume`, `failed_new_highs` |
| p_D_two_stage_dd20_{20,30,40} | Two-stage model probability of a >= 20/30/40% close-to-close drop within 20 trading days |
| p_C_lightgbm_dd20_40 | Unconditional cross-sectional model, for ranking all stocks |
| designated_shortable | On the HKEX designated list in force today |
| adv20, board_lot, lot_value_hkd | Liquidity and minimum ticket |
| capacity_2pct_adv_hkd | Indicative daily trade size at 2% of ADV |
| est_round_trip_cost | 2 x (statutory and exchange fees + brokerage + half-spread), using tick and Abdi-Ranaldo spread |
| tradeability | `SHORTABLE` (designated, ADV >= HK$5m; **borrow not verified**), `NOT SHORTABLE: avoid/exit only`, `THIN`, `ILLIQUID` |
| model_trained_through | Last label-complete date in the training data |

Only stock-days in the stage-1 run-up state (20-day return >= 50% and value
ratio >= 3x) are listed, ranked by `p_D_two_stage_dd20_40`.

## Operational controls

1. **Data-freshness gate.** Refuse to publish if the latest bar date is not
   the expected trading day, or if more than 5% of codes are missing.
2. **Partial-bar guard.** Research runs stop at the configured end date.
   The monitor must run after 16:10 HKT, because a fetch during trading
   returns an intraday bar.
3. **Borrow check.** For any `SHORTABLE` name a human still needs a locate
   and fee quote from the prime broker before acting. Log the quote, so the
   borrow history the backtest lacks starts accumulating.
4. **Drift monitoring.** Track the alert precision of each week's alerts
   20 trading days later against the out-of-sample precision in
   `outputs/research/metrics_pooled.csv`. Investigate if the trailing
   3-month precision falls below the random-alert 95th percentile.
5. **Model-change control.** A model refit is versioned (pickle plus config
   hash). Changing thresholds, features or the label definition reopens
   validation; it is not a monitor change.

## Production gaps

- The pilot price source has no delisted names. In production, swap in the
  survivorship-free adapter (docs/01) before trusting any recalibration.
- Add HKEXnews headlines (H3) and CCASS concentration (H5) as watchlist
  annotations before using them as model features. Annotation first lets
  their value be judged out of sample.

## Sample output (2026-10-27 close)

`outputs/watchlist/2026-10-27.csv` and `latest.md`:
- 17 stocks were in the run-up state out of 1,994 that traded.
- The highest Model D crash probabilities (>= 40% within 20 days) were
  0.18 to 0.25, against an 8% base rate for run-up names.
- **None of the 17 was on the designated short-selling list.** Five had
  ADV >= HK$5m (avoid/exit only); the rest were thin or illiquid.

That single day restates the memo's central finding.
