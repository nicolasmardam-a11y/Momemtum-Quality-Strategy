# Explicit data requirements

Every module consumes the canonical tables below. A new vendor needs one
adapter that emits these columns (see `src/hkrd/data.py`). Point-in-time
(PIT) means the value as known at the end of that date, never revised later.

| Table | Grain | Required columns | PIT? | Pilot source | Production source |
|---|---|---|---|---|---|
| `panel` | stock-day | code, date, open, high, low, close (split-adjusted), volume (adjusted), value (HK$), traded flag, raw_factor | prices: yes | Yahoo (current listings only) | Webb-site dump to 2025-04-30 + HKEX daily quotations / vendor after |
| `listing_history` | stock-listing | code, issuer id, board (Main/GEM), list date, delist date, delisting reason | yes | **missing** | Webb-site `stocklistings`, Capital IQ |
| `suspensions` | stock-interval | code, start, end, reason | yes | inferred (zero volume) | HKEX suspension reports / Webb-site |
| `corporate_actions` | event | code, ex-date, type (consolidation, split, rights, open offer, placing, bonus), ratio, price | yes | Yahoo splits only | Webb-site events, Capital IQ |
| `shares_outstanding` | stock-day/event | code, date, issued shares, free float estimate | yes | **missing** | Webb-site, Capital IQ, HKEX monthly returns |
| `board_lot` | stock-interval | code, effective date, lot size | yes | current lot only | HKEX securities list archive, Webb-site |
| `designated_short_list` | list-date | effective date, code, tick-rule exemption | yes | **HKEX archive, 631 lists, 2016-05-03 onward** | same, plus HKEX news releases before 2016 |
| `short_turnover` | stock-day | code, date, short-sell volume and value | yes | not loaded | HKEX daily short-selling turnover reports (free) |
| `short_positions` | stock-week | code, date, reportable short position | yes | not loaded | SFC aggregated reportable short positions (free, since 2012) |
| `borrow` | stock-day | code, date, lendable qty, utilisation, fee, locate success | yes | **none: stress assumptions** | prime broker history; S&P Global Securities Finance / DataLend; IBKR shortable-shares snapshots collected forward |
| `announcements` | filing | code, timestamp (HKT, to the minute), headline category, title | yes (timestamp) | not loaded | HKEXnews (free) |
| `ccass_holdings` | stock-participant-day | code, date, participant, shares | yes | not loaded | Webb-site archive (2007+), HKEX CCASS search (12-month window) |
| `fundamentals` | filing | code, period end, **filing date**, revenue, net income, equity, cash | as-filed | not loaded | Capital IQ PIT, Webb-site financial extracts |
| `benchmarks` | day | ^HSI, 2800.HK (hedge), HSCI small-cap if available | yes | Yahoo | vendor |
| `fees` | schedule | stamp duty, trading fee, SFC levy, AFRC levy, settlement fee, effective dates | yes | `src/hkrd/hkex.py` | HKEX fee schedule (verify settlement fee) |
| `ticks` | schedule | spread table with effective dates | yes | `src/hkrd/hkex.py` (2025/2026 reductions included) | HKEX |

## Timing conventions

- A daily signal uses data through the close of t: 16:00 continuous
  session, plus the closing auction to about 16:10 HKT since 2016.
- The earliest execution is the t+1 pre-opening auction (09:00 to 09:30).
  Short sales are modelled as continuous-session fills at a VWAP proxy,
  because the tick rule forbids selling below the best ask.
- Announcements count as known at t only if timestamped before 16:10 HKT
  on t. Evening filings (common in HK) belong to t+1.
- Fundamentals become usable on their filing date, never the period end.

## Known pilot gaps and the direction of each bias

| Gap | Effect |
|---|---|
| Delisted stocks missing (2012: ~1,190 codes in the panel against well over 1,400 actually listed) | Too few events. The worst collapses (delisted after long suspension) are absent. Strategy B/C benefits are understated; the risk of Strategy A being trapped short in a suspended stock is understated. |
| Recycled stock codes (HKEX reuses codes) | Yahoo may splice two issuers. Handled only through the quality mask; needs the listing history. |
| Current board lots applied historically | Lot-rounding costs are approximate. |
| No borrow history | Strategy A borrow costs and locate failures are assumptions (config `shorting`), stress-tested at 2x and 4x. |
| Spread estimated from daily OHLC (Abdi-Ranaldo), floored at half a tick | Real spreads in illiquid names are often wider; stress-tested at 2x and 3x. |
