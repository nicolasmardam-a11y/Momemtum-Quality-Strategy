# Deliverable 1: Feasibility assessment

*Status as of 2026-10-28. Every number below comes from data downloaded in
this project; nothing is illustrative. Pilot data are survivorship-biased
(current listings only). Read the numbers as a lower bound on event counts
and an upper bound on data quality.*

## 1. What was verified, not assumed

| Resource | Finding | How verified |
|---|---|---|
| **Norgate Data** | No evidence of HKEX coverage. Norgate's published history is ASX, then US exchanges. **Do not plan on it for Hong Kong.** Confirm with Norgate before cancelling the idea. | Vendor site search; no HK product found |
| **Capital IQ (PIT)** | Covers HKEX issuers, including delisted ones, with as-reported financials, shares outstanding and corporate actions. Bulk daily price export for ~4,000 historical HK codes depends on your licence (Xpressfeed vs. desktop). **Action: run a coverage query for 20 known delisted GEM codes before relying on it.** | Not testable from here (no credentials) |
| **HKEX designated short-selling lists** | **631 dated lists, 2016-05-03 to 2026-10-23, free CSV**. Lists before 2016-05 exist only as news releases of additions and deletions (2001 onward), which could be parsed if needed. | Downloaded: `scripts/fetch_pilot_data.py` |
| **HKEX List of Securities** | Free daily XLSX: 2,763 ordinary HKD shares (2,451 Main Board, 312 GEM) with board lot, short-sell eligibility, spread table. Current snapshot only. | Downloaded |
| **Yahoo Finance (yfinance)** | Free daily OHLCV from 2012 for **2,758 of 2,763 current listings**, with split/consolidation history. **No delisted stocks.** Prices are back-adjusted (a HK$0.04 stock in 2012 can show as HK$54), so the traded price must be rebuilt from split factors (done: `raw_factor`). | Downloaded: 6.97M stock-days |
| **Webb-site database** | Released under CC-BY 4.0 in 2025 by David Webb. Includes HK prices since 1994 **with delisted securities**, corporate actions, CCASS holdings (2007+), officers and other datasets. Prices cut off at **2025-04-30**. Distributed as database dumps (link on the Webb-site repository page; mirrors exist). | Release notes and mirror descriptions; the dump itself was not downloaded in this session |
| **SFC enforcement cases** | Public, but no machine-readable list with stock codes. Documented cases must be assembled by hand. The one fully sourced case, Wan Cheng Metal Packaging (8291, 2020-12 to 2021-04), **is delisted and therefore missing from the Yahoo pilot**: survivorship bias in action. | `data/reference/sfc_cases.csv` |

## 2. Vendor comparison (for a credible backtest)

Prices are indicative list ranges; obtain quotes. "Delisted" = survivorship-free history.

| Option | Daily OHLCV | Delisted | Shares / float history | Corp. actions | Intraday / book | Borrow | Indicative cost |
|---|---|---|---|---|---|---|---|
| yfinance (pilot) | yes, 2012+ | **no** | no | splits only | no | no | free (unofficial API, personal-use terms) |
| **Webb-site dump** | yes, 1994 to 2025-04 | **yes** | yes (issued shares) | yes | no | no | **free (CC-BY)**, plus work to load |
| HKEX free files | daily quotations (rolling window), short-sell turnover, DS lists | partly | monthly returns of equity issuers | announcements | no | no | free |
| SFC short positions | weekly aggregated reportable short positions by stock, 2012+ | yes | no | no | no | proxy for borrow use | free |
| Capital IQ / Compustat Global | yes | yes | yes, PIT | yes | no | no | already licensed (export limits apply) |
| EODHD / similar retail API | yes | partial, verify for HK | no | splits/dividends | some intraday | no | about US$20-100/month |
| Wind / iFinD / Choice | yes | yes | yes | yes | Level-1 intraday | no | roughly RMB 20-60k/yr |
| LSEG (Datastream / Tick History) | yes | yes | yes | yes | full tick and depth | no | tens of thousands of US$/yr |
| Bloomberg | yes | yes | yes | yes | intraday bars | some | about US$30k/yr per terminal |
| HKEX historical tick and order book (Data Marketplace) | n/a | yes | n/a | n/a | full | no | institutional pricing; quote needed |
| S&P Global Securities Finance / DataLend | n/a | n/a | n/a | n/a | n/a | **yes**: utilisation, fees | institutional; often five-figure US$ |
| IBKR shortable-shares snapshots | n/a | n/a | n/a | n/a | n/a | current availability and indicative fee, **no history** | free with an account; collect forward |

### Recommendation: the cheapest scientifically defensible stack

1. **Webb-site dump** for 2012 to 2025-04: survivorship-free prices,
   delistings, suspensions, consolidations, issued shares and CCASS
   holdings. Cost: zero. One to three days of engineering for a
   `webbsite` adapter emitting the canonical `panel` schema
   (docs/data_requirements.md).
2. **Yahoo, or HKEX daily quotations,** for 2025-05 to date, the bridge
   period. Delistings in that window come from HKEX announcements. Before
   the bridge, the delisted-name gap is closed.
3. **HKEX DS lists** (already loaded), **HKEX short-selling turnover** and
   **SFC short positions**: free, and they are the only historical evidence
   of actual shorting.
4. **Capital IQ**, already licensed, for PIT fundamentals and to
   cross-check Webb-site shares outstanding.
5. **Borrow:** no affordable history exists. Start collecting prime-broker
   or IBKR availability and fee snapshots daily **now**. Until then, borrow
   is a stress assumption, and Strategy A results are an upper bound.

Total incremental data cost: **about zero**, plus engineering. Intraday or
order-book data (five to six figures in US$) is **not justified** unless the
daily research finds tradable signal (see section 4 and the memo).

## 3. Event and opportunity counts (pilot, current listings only)

From the pilot event database (docs/03) and backtests (docs/05):

| Quantity | Count |
|---|---|
| Abnormal run-up episodes (20d run >= 80%, value >= 5x), 2012 to 2026-10 | 4,923 in 1,574 stocks |
| Followed by a >= 40% drawdown within 20 days (category A) | 1,434, about 108 a year since 2016 |
| ... and short-sellable (designated list) at the peak, since 2016-05 | **90 of 1,185 (7.6%)** |
| ... with mean traded value >= HK$5m/day during the run | 766 (all years) |
| Stock-days in a run-up state (model population) | 84,126 of 5.19M eligible |
| Model alert opportunities, 2016-05 to 2024-06 (distinct stock-months) | 2,328 |
| ... executable as shorts after designation, locate and liquidity | **195 trades (8%), about 24 a year** |
| Average capital deployable short, HK$50m book | about HK$1m (HK$2.3m in holdout) |

The statistical sample is large enough to identify the phenomenon. The
**tradable** sample on the short side is small: about 24 trades a year and
low single-digit HK$ millions deployed. That alone caps Strategy A's
economic value, before any question of profitability.

## 4. Feasibility verdict on the premise

**The premise is only partly monetisable.**
- The event is common and predictable: out-of-sample precision is about 2x
  the conditional base rate, and the result replicates in the holdout.
- Short monetisation is structurally blocked. The HKEX designation criteria
  (about HK$3bn market capitalisation and >= 60% turnover ratio) exclude
  over 90% of the stocks where the effect lives. In the shortable minority
  the effect is weak or absent.
- The viable use is avoidance and exits in long books (Strategies B/C).
  That needs no borrow, intraday or order-book data.

**Cheapest defensible next step:** re-run the frozen pipeline on the free,
survivorship-free Webb-site dump (recommendation above). Do not buy
intraday, order-book or securities-lending data for this programme
(docs/07).
