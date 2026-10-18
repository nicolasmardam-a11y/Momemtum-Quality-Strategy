# Family G: public-information and cross-market lead-lag (as of 2026-10-17)

Status: IN PROGRESS. Pre-registration below was written at 2026-10-17 ~22:55 UTC, before any lead-lag
result was computed. Market discovery and the rules read (section 1) came first. A 1.5-minute collector smoke test also ran first, but only to check that the plumbing works. No price comparison was run.

## 0. Pre-registration (written before results; not to be changed)

### 0.1 Crypto: hypotheses, signal and fair-value model

Universe: Polymarket BTC and ETH `Up or Down` markets (5m, 15m, 4h: Chainlink BTC/USD **TWAP-60s** stream;
hourly: Binance BTC/USDT 1h candle) and hourly `above-K` markets (Binance 1h close). Rules: see section 1.

Fair value (fixed before results):
* Binance-resolved (hourly up/down, hourly above-K): `P = Phi( ln(S_t/K) / (sigma*sqrt(tau)) )`, zero drift.
  S_t = Binance mid (live) or 1m close (historical). K = 1h candle open (up/down) or the strike (above-K). tau = seconds to candle close.
* Chainlink-TWAP-resolved (5m/15m/4h): K = Gamma `eventMetadata.priceToBeat`. The final value is the 60-s average
  over [T-60, T]. For t <= T-60: mean S_t, variance `sigma^2 * ((T-60-t) + 60/3)`. Inside the last 60 s, the
  realised partial average gets weight w and the remainder variance is `(1-w)^2 * sigma^2 * (T-t)/3`.
  S_t = Chainlink BTC/USD spot from RTDS (live). Historically there is no Chainlink history, so the proxy is
  Coinbase BTC-USD 1m with a per-market basis = priceToBeat / Coinbase price at the start minute.
* sigma: live uses the stdev of 10-s log returns of the reference source over the trailing 30 min. Historical uses
  1-min log returns over the trailing 60 min. Both are scaled to per-second.

Signals:
* H1 (lag): Polymarket mid moves after spot. Historical: the coefficient on lagged spot-implied fair-value changes in
  regressions of 1-min Polymarket price changes (`prices-history` fidelity=1, a trade/mid series, **not executable**).
  Live: event study of spot moves >= 3 sigma_10s within 10 s, with the Polymarket mid response measured at +0.5/1/2/5/10/30 s.
* H2 (executable mispricing): `edge_up = fair - ask_up - fee(ask_up)`, `edge_down = (1-fair) - ask_down - fee(ask_down)`,
  fee = 0.07 * p * (1-p) per share (market `feeSchedule`: crypto_fees_v2, rate 0.07, exponent 1, takerOnly).
  A signal fires when edge >= **0.02** per share **and** the depth at the best ask is >= the market `orderMinSize` (5 shares).
  An **episode** is a maximal run of consecutive 1-s snapshots with the signal true for one (market, side). Runs separated by
  less than 2 s are merged. Episodes are counted as distinct events, not as snapshots.
* Entry rule (simulated): buy at the best ask seen **1.0 s after** the signal first fires (a retail latency budget: network plus
  150 ms `itode` delay plus decision). Use that ask only if it still gives edge >= 0 net of fee. Size = min(ask depth, size cap).
* Exit rule: hold to resolution (payout 1/0 from the resolved market). Also report the mark-to-mid at +5 s, +30 s and +60 s.

Rejection criteria (pre-registered):
* **R1 (persistence):** reject for a retail trader if the median episode lasts < 2 s, or if < 25% of episodes survive to the
  1-s delayed entry (edge >= 0 at t+1 s).
* **R2 (P&L):** no demonstrated edge if the delayed-entry hold-to-resolution P&L per share has mean <= 0, or a 95% CI
  (bootstrap by market) that includes 0. Same for the +30 s markout net of the entry fee and the half-spread exit.
* **R3 (model check):** if the fair model's log-loss on outcomes is not better than the Polymarket mid's at the same timestamps,
  then "mispricing" is model error and H2 is rejected regardless of R2.
* **R4 (lag size):** H1 is economically rejected if the predictable 1-min move implied by the historical lag coefficient,
  at the median, is smaller than half the median spread plus the taker fee at that price.
* **R5 (sample):** fewer than 20 distinct episodes means "inconclusive data", not edge.

### 0.2 Cross-venue (Kalshi vs Polymarket)

* A cross-venue arb counts only if (i) the rules match (same event, same resolution source, same cut-off time), or the mismatch
  is explicitly bounded, and (ii) `ask_YES(venue A) + ask_NO(venue B) + fees_A + fees_B < 1 - 0.01`, using executable asks with
  >= $100 of depth on both legs.
* Lead-lag between venues needs synchronised book time series from both venues. **Data-access constraint, decided before any
  data:** `notes/platform/geography_legal.md` says Kalshi's Developer Agreement (API access = acceptance; use limited to a member's own
  trading; no storing or aggregating) and its Data Terms (no systematic retrieval, no AI/ML use) bar this project from building a
  Kalshi dataset. It recommends limiting Kalshi to its public documentation. This study follows that. **No Kalshi market data is pulled.**
  Section 2 therefore reports rules, fee and eligibility comparisons and published evidence only. The cross-venue verdict is
  "inconclusive data" by construction, unless published evidence settles it.

### 0.3 Sports

No free real-time bookmaker-odds feed is available here. The Odds API needs a key, and other feeds are paid. The deliverable is a
forward-test design, not a result.

### 0.4 Sports mini forward test (added 2026-10-17 ~23:16 UTC, before any sports data was collected)

* Sources: the ESPN public scoreboard JSON (unofficial and free, polled every 4 s), the Polymarket sports WebSocket (free) and Polymarket
  CLOB books for the moneyline markets of in-play CFB and NHL games.
* Event: the first poll in which a team's ESPN score increases. t_E is the local receive time of that poll.
* Measure: the Polymarket mid of the scoring team's moneyline token. Pre-move window [t_E-60, t_E-1]; post window [t_E-1, t_E+30].
  Share of the move before ESPN = (mid(t_E-1) - mid(t_E-60)) / (mid(t_E+30) - mid(t_E-60)).
* **Rejection (ESPN as a leading signal):** reject if the median pre-detection share is >= 0.5, or if the median absolute
  post-detection move (t_E-1 to t_E+30) is <= the taker fee at that price plus half the spread. Fewer than 10 scoring events means inconclusive.
* Execution note: sports moneylines carry a 1 s `secondsDelay`. A taker order placed at t_E fills no earlier than t_E+1 s plus latency, and
  makers can cancel during the delay.

---

## 1. Crypto market rules and reference data (VERIFIED unless marked)

Source: Gamma `description`/`resolutionSource` for open markets on 2026-10-17 (`data/derived/lead_lag/crypto_rules_20261017T2243.json`, script
`analyses/lead_lag/01_rules.py`) and the predictions changelog (docs.polymarket.com/changelog/predictions.md).

| Family (slug) | Resolution rule | Price source | Strike | Tick | `itode` taker delay |
|---|---|---|---|---|---|
| 5m / 15m / 4h up/down (`btc-updown-5m-<ts>` etc.) | Up if the TWAP at the end of the window >= the TWAP at its start | **Chainlink BTC/USD TWAP-60s data stream** (data.chain.link/streams/btc-usd-twap-60s-streams) | `eventMetadata.priceToBeat`. **Gamma publishes it only after the window ends.** For an open window it is `None`. | 0.01 | 150 ms on 5m/15m (mechanics.md). None on 4h |
| Hourly up/down (`bitcoin-up-or-down-october-17-2026-6pm-et`) | Up if close >= open of the **Binance BTC/USDT 1H candle** | Binance BTCUSDT | Candle open | 0.001 | 150 ms (mechanics.md) |
| Hourly above-K (`bitcoin-above-81600-on-october-17-2026-8pm-et`) | Yes if the Binance BTC/USDT 1H candle **close > K** | Binance BTCUSDT | K in the title | 0.001 | none (mechanics.md) |
| Daily above-K (`bitcoin-above-74k-on-october-18-2026`) | Binance BTC/USDT **1m candle closing at 12:00 ET**: close > K | Binance BTCUSDT | K | 0.001 | none |

* Changelog: on 2026-08-07, crypto up/down markets moved to Chainlink TWAP. 5m markets used a 30-s window; 15m and 4h used 60 s. On **2026-08-14** the 5m markets
  moved to 60 s. "Both the price to beat and the final settlement price come from the applicable TWAP feed."
* **Checked live (L2/L3):** `priceToBeat` matches the mean of the public RTDS Chainlink BTC/USD *spot* values over the 60 s before the window start
  (see section 3: median |diff| in bp). It is further from the single spot value at the start. Outcomes matched `next window's priceToBeat >= this priceToBeat`
  on every market checked.
* Fees: every crypto market sampled has `feeType crypto_fees_v2`, `feeSchedule {rate 0.07, exponent 1, takerOnly true, rebateRate 0.2}`.
  The taker fee is 0.07·p·(1−p) per share, which is **1.75 c at p = 0.5** and 0.63 c at p = 0.1/0.9. LP rewards fields on these markets: `rewardsMinSize 50`, `rewardsMaxSpread 4.5`.
* Public reference feeds reachable from this sandbox without a key: RTDS `crypto_prices_chainlink` (Chainlink spot, ~1 value/s per symbol,
  received a median **1.4 s** after the Chainlink timestamp (p10 1.1 s, p90 1.7 s)); Binance `data-stream.binance.vision` (bookTicker, aggTrade) and
  `data-api.binance.vision` REST (klines, including **1s klines**); Coinbase Exchange WS/REST. `stream.binance.com` resets the connection (geo-block).
  The Chainlink **TWAP** stream itself (PolyBolt `price.crypto.twap`) needs CLOB API credentials (data_infrastructure.md), so it was not used.
* **Source basis (VERIFIED, live 15-min sample):** Binance BTCUSDT and ETHUSDT trade about **+13 bp** above Coinbase USD and Chainlink USD. Coinbase and Chainlink agree
  to within ~1 bp (p10–p90 −0.9 to +0.8 bp for BTC). The USDT premium matters for cross-venue matching (section 5).

## 2. Historical 1-minute test (7 days, 2026-10-10 22:00 to 2026-10-17 22:00 UTC)

Data: 1,680 resolved events, all found on Gamma: BTC and ETH × (672 15m + 168 1h). 841 Up / 839 Down. Median event volume is $10.2k (15m) and $14.0k (1h).
CLOB `/prices-history` fidelity=1 for the Up token gave 121,102 points. **This is a trade/mid series, not an executable price.** Spot came from Binance 1m and **1s** klines and
Coinbase 1m. Scripts: `02_hist_collect.py`, `02b_binance_1s.py`, `04_hist_analyze.py`, `04b_hist_r4_paper.py`. Outputs: `hist_summary.json`,
`hist_r4_paper.json`, `hist_panel_primary.parquet`.

**A data artefact first (VERIFIED):** `prices-history` points fall at irregular seconds (t mod 60 ≈ 20–24 s), not on minute boundaries. On the
pre-registered minute grid, the Polymarket value is the last point before the boundary, which is ~35–40 s stale. The grid regression therefore "finds" that
Polymarket follows the *previous* minute's fair-value change (coef 0.83, t = 90, 15m; 0.84, t = 56, 1h). It also finds the fair model beating Polymarket on
log-loss (15m 0.475 vs 0.489). **Both results are staleness artefacts, not lag.** The primary analysis below evaluates spot at the exact timestamps of the Polymarket
points (Binance 1s, no look-ahead).

Primary results (aligned):

| | 15m (Chainlink TWAP; Binance 1s proxy) | 1h (Binance candle) |
|---|---|---|
| Points / markets | 19,901 / 1,344 | 19,903 / 336 |
| Log-loss on outcomes: Polymarket vs fair model | **0.445 vs 0.456** (PM better) | **0.459 vs 0.460** (equal) |
| Logit of outcome on logit(PM) and logit(fair), market-clustered t | PM 0.73 (t 9.9), fair 0.38 (t 5.0) | PM 0.66 (t 2.5), fair 0.46 (t 1.7) |
| Response of ΔPM (between ~60-s samples) to the fair-value change in the window before the sample: last 0–5 s / 5–15 s / 15–30 s / 30–60 s / 60–120 s | −0.02 / 0.13 / 0.84 / 1.01 / 0.24 | −0.04 / 0.08 / 0.74 / 1.03 / 0.29 |
| Look-ahead check (fair change after the sample) | 0.01 | 0.00 |
| Predictive: next ΔPM on gap (fair − PM) and last-minute Δfair | gap 0.32 (t 18), Δfair 0.21 (t 18), R² 0.13 | gap 0.38 (t 16), Δfair 0.23 (t 17), R² 0.18 |
| Median abs predicted next-minute move | 2.1 c | 1.2 c |

Reading:
* The `prices-history` value at time t barely reflects spot moves in the last ~5–15 s (coefficients ≈ 0–0.13). It fully reflects moves 15–60 s earlier. This would
  look like a 10–15 s Polymarket lag. **The live books (section 4) show quotes react within a few hundred ms, so the 10–15 s is a lag inside the `prices-history` series**
  (sampling or publishing delay), not in the order book (PLAUSIBLE; the series construction is undocumented). The 60–120 s coefficient (0.24–0.29) has the same caveat.
  It may also reflect last-trade staleness.
* **R4 (pre-registered) rejects H1 economically.** The predictable move implied by the lagged coefficient has median **1.24 c (15m) / 0.70 c (1h)**. The median hurdle (half
  the 1-c live spread + taker fee at that price) is **1.79 c / 1.88 c**. Only 40% / 21% of observations clear it, and only before allowing for the staleness above.
* Calibration by time to expiry: the fair model is much worse than Polymarket in the last 3 minutes of 15m markets (log-loss 0.142 vs 0.089 in the last 60 s).
  That is the Chainlink TWAP-vs-Binance-proxy basis. Elsewhere the two are equal within ±0.01. **Polymarket's 1-minute prices contain the public spot information** at least as well as
  the model does.
* A non-executable "paper" test of H2 on these series (`04b`; buy the cheap side when |gap| − half-spread − fee >= 2 c, first signal per market,
  hold to resolution, entry at the stale series price) gives +2.7 c/share for 15m (bootstrap CI 0.1 to 5.2 c, n = 1,340). By time split it is
  **+5.3 c in the first 4 days and −0.8 c in the last 3 days**. For 1h it is +3.8 c (CI −1.5 to 9.4 c, n = 336). Entering at a price that is ~15 s stale, while the fair value uses spot up to t, is a
  look-ahead advantage, so these numbers are an **upper bound**, not evidence of edge. The live test is the binding one.
