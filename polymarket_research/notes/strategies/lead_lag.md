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

<!-- SECTIONS 3-4 (live crypto) are inserted here -->

## 5. Cross-venue: Kalshi vs Polymarket (written 2026-10-18 ~05:10 UTC)

**Data-access decision (pre-registered in 0.2, unchanged):** no Kalshi market data (markets, orderbooks, candles, trades) was pulled.
The reasons are Kalshi's Developer Agreement (API use limited to a member's own trading; no storing or aggregating) and its Data Terms
(no systematic retrieval, no AI/ML use). See `notes/platform/geography_legal.md` §1, §4. **Verdict for both (a) arbitrage and (b) lead–lag:
`inconclusive_data` by construction.** What follows is what could be established without Kalshi data.

### 5.1 API and fee facts (Kalshi public documentation only)
* Public REST market-data endpoints (`/markets`, `/events`, `/series`, `/markets/{ticker}/orderbook`, candlesticks, trades) need **no
  authentication**. The OpenAPI pages declare `security: []`. The production base is `external-api.kalshi.com/trade-api/v2`, and the legacy
  `api.elections.kalshi.com` answered `/exchange/status` (geography_legal.md §4). The WebSocket needs authentication even for public channels. VERIFIED (docs).
  So an unauthenticated public API exists. **Using it is still not permitted for this project (above).**
* **Fee formula.** The series object has `fee_type` ∈ {`quadratic`, `quadratic_with_maker_fees`, `quadratic_with_combo_maker_fees`, `flat`} and a
  `fee_multiplier`. Docs: "quadratic is described by the General Trading Fees Table" in kalshi.com/docs/kalshi-fee-schedule.pdf. VERIFIED, docs.kalshi.com get-series.
  The General Trading Fees Table is **taker fee = roundup(0.07 × C × P × (1−P))**: 1.75 c per contract at P = 0.5 and 0.63 c at 0.1/0.9. Some series charge a
  **maker fee of roundup(0.0175 × C × P × (1−P))**, and S&P/Nasdaq series have their own multiplier. PLAUSIBLE-high: the schedule effective 2026-02-05 as indexed by
  search plus secondary sources. The live PDF returned **HTTP 429** to this sandbox.
* **Rounding.** Fees are computed per order and accumulate across its fills (`trade_fee = ceil_6dp(model_fee)`). Non-direct members' balances align to
  $0.01, so the rounding is a few tenths of a cent per small order. VERIFIED, docs.kalshi.com/getting_started/fee_rounding.md.
* So Kalshi's taker fee has the **same shape and rate as Polymarket's crypto fee (0.07·p(1−p))**. It is higher than Polymarket's politics (0.04) and
  economics (0.05) rates, which come from each market's `feeSchedule`.

### 5.2 Contract matching with rule checks (Polymarket side read live; Kalshi side from public CFTC filings)
| Underlying | Polymarket market (feeSchedule; executable top of book 2026-10-17 23:12 UTC) | Polymarket rule | Kalshi rule (source) | Match? |
|---|---|---|---|---|
| Oct 27–28 2026 FOMC, "no change" | `fed-decision-in-october-…` (economics_fees, rate 0.05). Bid 0.86 / ask 0.87, $1.66M of ask depth within 3 c | Change in the **upper bound** of the target range vs the pre-meeting level. Source: the FOMC statement. Non-25-bp moves round **up** to the next 25 bp bracket | "Will the Federal Reserve do <action> at <meeting>?" Underlying: FOMC decisions to change the target range. Source Agency: Federal Reserve System. Expiration at the first 2:05 PM ET after the decision. Later revisions ignored (CFTC 40.2 filing, 2023-04-05, `data/raw/lead_lag_docs/cftc_ptc040523303.pdf`) | **PLAUSIBLE match** on the main outcome. The bracket definitions for odd-size or inter-meeting moves were not compared, because the current KXFED market rules sit on kalshi.com (429) |
| 2026 House control (D) | `which-party-will-win-the-house-in-2026` (politics_fees, rate 0.04). Bid 0.90 / ask 0.91 | A majority of voting seats. Otherwise the party of the first elected Speaker. Runoffs count | Not read (kalshi.com 429; no CFTC filing located for the current contract) | **UNSUPPORTED** |
| 2026 Senate control (D) | `which-party-will-win-the-senate-in-2026` (politics_fees, 0.04). Bid 0.64 / ask 0.65 | Analogous chamber-control rule (VP tie-break wording not compared) | Not read | **UNSUPPORTED** |
| BTC hourly / daily strikes | Binance BTC/USDT 1h candle close (hourly) or the 12:00 ET 1m candle (daily) | (section 1) | Kalshi BTC contracts settle on CF Benchmarks' BRTI (USD) averages (PLAUSIBLE, not re-read) | **Mismatch by construction**: USDT vs USD (about +13 bp basis measured in section 1), a different index and different averaging windows. Basis risk at the strike, not an arb |

### 5.3 Arbitrage hurdle (my calculation from the two fee formulas)
A two-venue lock needs `ask_YES(A) + ask_NO(B) + fee_A + fee_B < 0.99` (pre-registered 1 c margin). With one-tick spreads on both venues (two half-spreads = 1 c),
the **mid-price gap needed between venues** is:

| p | PM politics (0.04) + Kalshi | PM economics (0.05) + Kalshi |
|---|---|---|
| 0.10 / 0.90 | 3.0 c | 3.1 c |
| 0.30 / 0.70 | 4.3 c | 4.5 c |
| 0.50 | 4.75 c | 5.0 c |
| 0.865 (Fed "no change" today) | 3.3 c | 3.4 c |

The only executable-quote, pre-registered cross-venue study found (Moulinier 2026, SSRN, **abstract only**, see
`notes/literature/sweep_microstructure-leadlag.md` §3.5) reports a **median aligned divergence of 0.60 c** on MLB moneylines and Fed contracts. Only 7% of
aligned minutes clear the fees, with a median life of one minute and 0.00% pre-game. That is ~5–8× below the hurdle above. Non-price costs are not in the
hurdle: capital is locked on two venues until resolution (Fed: 10 days; House: at least 3 weeks, more if the result is contested), USD vs USDC funding
and withdrawal, and rule-mismatch tail risk (a lock that resolves YES on one venue and NO on the other loses ~100%).

### 5.4 Who leads? (published evidence only; content PLAUSIBLE, abstracts)
* Ng, Peng, Tao & Zhou (SSRN 5331995): **Polymarket led Kalshi** before the 2024 US election, more so when liquidity was high.
* Adamczewski (SSRN 7194218): 281 UFC fights. **No lead–lag distinguishable from zero** at any horizon, and gaps close within ~30 min.
* Moulinier: apparent edges grow from 7% to 24–41% of minutes when one venue's timestamps are shifted. Mistimed data creates "lead–lag" and "arb".
* So the evidence is mixed and depends on the event. Neither venue is shown to lead in the sports and macro markets a retail trader could use.

### 5.5 Who could even trade it (geography_legal.md)
Polymarket international excludes US persons. Kalshi excludes the UK, France, Poland, Singapore, Taiwan, Thailand, Australia, Canada, Russia and (reportedly) India.
The feasible pairs are **Kalshi ↔ Polymarket US for US persons** (outside the states that block either venue), or a small set of non-US persons eligible on both.
Using Kalshi prices only as a signal for Polymarket trading is outside the Developer Agreement's permitted use (PLAUSIBLE reading). The whole cross-venue
family is therefore **eligibility-limited before it is edge-limited**.

### 5.6 Forward test that would settle it (for an eligible Kalshi member trading their own account)
1. Pre-register the matched pairs with both venues' full rule texts. Drop any pair whose source, cut-off or edge-case rules differ unless the mismatch is bounded.
2. Record synchronised books from Kalshi (authenticated WS, own account) and the Polymarket CLOB WS. Use exchange timestamps plus local receive time, and NTP-check the clock.
   Record ≥ 4 weeks, so that several Fed/CPI releases and ≥ 200 sports games are covered.
3. Signal: the executable lock inequality with ≥ $100 of depth on both legs, persisting ≥ 2 consecutive 1-s snapshots. Lead–lag: Hasbrouck information
   shares / Hayashi–Yoshida cross-correlations on mid changes, using exchange timestamps only.
4. Reject if fewer than 20 distinct locks occur, if the median life is under your measured round-trip latency to both venues, or if P&L net of fees, funding
   costs and capital lock-up (at the T-bill rate) has a CI that includes 0.

## 6. Sports and other public information (written 2026-10-18 ~05:10 UTC)

### 6.1 Mini forward test S1 (pre-registered in 0.4): ESPN public scoreboard vs Polymarket moneylines
* Collection 2026-10-17 23:17–23:38 UTC (21 min; the collector was killed by the session interruption). Scripts: `sports_collect.py`. Raw frames are in
  `data/raw/lead_lag_live/20261017/{espn,clobS}_S1.tsv.gz`. Derived tables were rebuilt from raw with `07a_sports_rebuild.py`, and the analysis is `07_sports_analyze.py`
  (`data/derived/lead_lag/sports_S1_{espn,tob,events}.parquet`, `sports_S1_summary.json`).
* 26 moneyline markets (52 tokens), 30 ESPN games, of which 10 were in play. **9 ESPN scoring events, 6 matched to a Polymarket token** (5 NHL goals, 1 CFB point-after).
* Median pre-detection share of the move = **0.96** (n = 5 with a move ≥ 0.5 c). In 4 of 5 NHL goals, Polymarket had moved ~13 c **before** ESPN showed the score.
  Median |move| after detection (t_E−1 → t_E+30) = **0.75 c**, against a median hurdle (taker fee at the sports rate + half-spread) of **1.6 c**. Only 1 of 6 events cleared the hurdle.
* **Verdict: inconclusive data (n = 6 < 10, the pre-registered minimum).** The direction is unambiguous, though. Both pre-registered rejection conditions would
  trigger (pre-share ≥ 0.5; post move ≤ hurdle). **A 4-s-polled free ESPN feed lags Polymarket.** It is a lagging, not a leading, signal (PLAUSIBLE; small sample).
* The Polymarket sports WebSocket (`sports-api.polymarket.com/ws`) delivered **0 frames** in S1. Its subscription protocol was not established, so "ESPN minus
  Polymarket-sports-feed" latency is unmeasured.
* Execution: sports moneylines carry `secondsDelay = 1` (all 6 matched markets). A taker order placed at t_E matches no earlier than ~t_E + 1 s plus latency,
  and makers can cancel during the delay. This removes most of the value of a feed that is a few seconds early.

### 6.2 Which public sources could lead Polymarket sports prices
| Source | Access / cost | Latency vs the field (typical) | Timestamp quality | Notes |
|---|---|---|---|---|
| Watching the broadcast / stream | Free-to-paid | Broadcast delay 5–30 s behind the field; streams worse | None (human) | Bettors at the venue or on low-latency feeds are ahead. That is "courtsiding" (banned by venues and some leagues) |
| ESPN site API (`site.api.espn.com`, unofficial) | Free, no key, unofficial (no ToS for automated use) | Seconds to tens of seconds; S1 showed it **behind** Polymarket | Poll receive time only; no event timestamp in the scoreboard | Used in S1 |
| League feeds: NHL `api-web.nhle.com`, MLB `statsapi.mlb.com`, NBA `cdn.nba.com` liveData (unofficial public endpoints) | Free, unofficial, terms vary | Usually seconds; play-by-play has event clock and wall-clock fields | Better (per-play `dateTime` in MLB/NHL) | The best free candidate for a forward test (UNSUPPORTED: not measured here) |
| Official data distributors (Sportradar, Genius Sports, Stats Perform) | Paid, enterprise contracts (typically thousands/month and up) | ~1–3 s from in-venue scouts | Good (per event) | The likely source for professional in-play bots |
| Bookmaker odds: The Odds API | Key required; free tier 500 **credits**/month | Live odds refreshed ~**every 40 s** (vendor page) | Poll time | Too slow and too small for in-play; usable for pre-game reference |
| Betfair Exchange API | Account + app key. The delayed key is free but delayed 1–60 or 1–180 s (docs conflict). Live key: one-off **£299** after KYC | Live stream ~sub-second | Exchange timestamps | Not available to US persons; jurisdiction-limited |
| Pinnacle | Public API closed to new users since 2025 (PLAUSIBLE) | — | — | The sharpest pre-game line historically |
| Paid odds aggregators (OpticOdds, OddsJam, SharpAPI, …) | Paid (hundreds to thousands/month) | Seconds | Vendor timestamps | Would be needed for a serious pre-game "sharp line leads Polymarket" test |

Sources for vendor terms: the-odds-api.com/sports-odds-data/update-intervals.html; betfair-developer-docs.atlassian.net (application keys). PLAUSIBLE: vendor
pages, not independently tested here.

### 6.3 Forward test that would be needed (not run here)
1. **Hypothesis A (in-play news):** a scoring event observed in a low-latency source moves the Polymarket moneyline after the source's timestamp by more than
   fee + half-spread + the 1-s `secondsDelay` drift. Data: a feed with per-event wall-clock timestamps (league play-by-play, or a paid official feed), the Polymarket CLOB WS
   (book + trades), and the ESPN poll as a control. Measure the source's latency against the exchange's first price move on ≥ 200 events per league. Reject if the median
   pre-source share is ≥ 0.5 or the post-source move net of fee + half-spread + delay drift is ≤ 0.
2. **Hypothesis B (pre-game sharp line):** a de-vigged sharp-book line (Pinnacle/Betfair/consensus) leads Polymarket pre-game prices. Data: odds snapshots every ≤ 10 s
   from a paid aggregator, plus Polymarket books. Test: does the gap (sharp fair − Polymarket executable) predict the Polymarket closing price and the outcome, net of fees?
   Bootstrap by game.
3. **Settlement differences to check per league:** Polymarket NHL/NBA moneylines include OT/shootout per their rules; some books grade "regulation" lines separately. Postponement
   and abandonment rules, and the void window, differ across venues. CFB/NFL markets carry their own feeSchedule (sports_fees v3 0.05; NFL/CFB 0.03 per platform notes;
   always read the market).
4. **Costs:** paid feed ($ hundreds–thousands/month) and a server near the Polymarket matching engine. The 1-s taker delay and maker cancellation during it mean a retail
   edge needs a *multi-second* information advantage, not a sub-second one.
