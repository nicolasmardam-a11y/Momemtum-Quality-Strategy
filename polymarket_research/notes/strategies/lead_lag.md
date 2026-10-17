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

