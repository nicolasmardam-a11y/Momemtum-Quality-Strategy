# Literature sweep: microstructure, mean reversion, lead–lag, near-expiry and logical arbitrage

As of 2026-10-17. Author: research agent (literature sweep). Labels: **VERIFIED** = I read it in the primary source
myself; **PLAUSIBLE** = consistent with the evidence but not directly checked; **UNSUPPORTED** = no evidence found.
"Sibling note" = another file in `notes/literature/` or `notes/strategies/`; I say when I rely on one instead of my
own reading. No paper, number or quote below comes from memory. Where I saw only an abstract, I say so.

Scope:

- market making and adverse selection in prediction-market and binary limit order books, including Polymarket
  liquidity rewards (family D);
- overreaction and mean reversion after large price moves, separating in-play news from liquidity shocks (F);
- lead–lag between prediction markets and other price sources: polls, bookmakers, Kalshi vs Polymarket, crypto spot vs
  short-horizon crypto markets (G);
- near-expiry convergence and returns on "high-probability" contracts (H);
- logical and combinatorial arbitrage across linked contracts (C, with B where it overlaps).

Classic theory is included only where it makes a testable prediction.

Overlap with sibling notes. These papers are covered in depth elsewhere, and I only cross-reference them here:

| Paper | Sibling note |
|---|---|
| Bartlett & O'Hara (Kalshi adverse selection, VPIN) | `sweep_informed-trading-following.md` §3.1 |
| Angelini & De Angelis 2026 (Kalshi NBA underreaction) | `sweep_informed-trading-following.md` §3.6 |
| Croxson & Reade 2014 (Betfair goals) | `sweep_informed-trading-following.md` §3.7 |
| Bürgi, Deng & Whelan; Becker (Kalshi makers vs takers) | `sweep_flb-calibration.md` §§3.1–3.2 |
| Zitzewitz 2026 (PredictIt limits to arbitrage) | `sweep_flb-calibration.md` §3.4 |
| Gebele, Mutzel & Matthes 2026 (executable arbitrage) | `sweep_polymarket-empirical.md` §3.2 |
| Saguillo et al. 2025 | `title_probabilistic-forest.md` |
| Cheng, Yang & Zou 2026 (NBA arbitrage) | `sweep_polymarket-empirical.md` §3.4 |
| Dai, Jia & Yu 2026 (settlement manipulation) | `sweep_polymarket-empirical.md` §3.6 |
| Dubach (two papers) | `sweep_polymarket-empirical.md` §§3.8–3.9 |
| Vojtko & Dujava (mean reversion) | `title_mean-reversion-polymarket.md` |
| The project's own live logical-arbitrage scan | `strategies/logical_arb.md` |

---

## 1. Bottom line for a retail trader

1. **Market making (D): makers earn at settlement, not from the spread, and they lose in informative periods.**
   - **Who earns.** On a 24-hour sample of Polymarket's BTC 5-minute markets, persistent makers took **91.4%** of their
     profit at resolution and 8.6% from round trips. Profit came almost entirely from *buying* the under-priced side
     (VERIFIED, Zang et al. App. B.1, Tables 1–2).
   - **When makers lose.** In TradeSports data, limit orders that filled during clustered in-play trading lost
     **more than 1%** to expiry. Before the event they earned **about 1%**, after the 0.4% commission (VERIFIED,
     Tetlock 2008 §V.A, Table V).
   - **The direct test.** A pre-registered test on Kalshi and Polymarket MLB and Fed markets reports that makers who
     avoid the fee realise **−7.39¢ per contract**, "because fills arrive only when they are losing" (abstract only,
     Moulinier 2026).
   - **Rewards are real but concentrated.** About **$9.3M** of Polymarket liquidity rewards was paid from 2023-11-25
     to 2025-07-24. The top five addresses took about 22% (VERIFIED, Singh 2025 §5.2). Today's configured median is
     about $3/day per market (sibling `notes/platform/fees_incentives.md`).
   - **Prediction for our LP markout study:** markouts are positive pre-event and negative in-play and near the close.
     Rewards must cover the in-play adverse-selection loss.
2. **Volatility is predictable from contract structure. Use it to size quotes, not as a directional signal.**
   - On 6.75M out-of-sample Kalshi contract-hours, next-hour variance is well described by p(1−p)/τ (time left) plus a
     Glosten–Milgrom spread×volume term. This beats GARCH by **15%** on interval score (VERIFIED, Xi et al. §§1, 4,
     Table 3).
   - **Volatility rises 22.6× from the longest to the shortest time-to-resolution bin** (Table 2).
   - In sports, **4.1% of hours carry 47.8% of volume**, in jump-like moves (§5). A maker must pull quotes around game
     events.
3. **Mean reversion after big moves (F) is conditional, the evidence conflicts, and it is rarely tradable after the
   spread.**
   - **News moves mostly stick.** Deep Betfair markets price goals "swiftly and fully" (Croxson & Reade, sibling).
   - **Betfair after the first goal.** Prices stay mispriced for up to about 5 minutes. Gross ROIs of 11–70% appear
     only in regions estimated in-sample, before Betfair's commission of up to 5% (VERIFIED, Angelini, De Angelis &
     Singleton 2022, Table 4).
   - **Surprise goals: two papers disagree.** Angelini et al. find the market *under*-reacts to a surprise (a longshot
     scores). Choi & Hui (2014) report *over*-reaction to highly surprising goals (abstract only).
   - **Political shocks** gave one reversal and one continuation, so n = 3 events tells us nothing general (VERIFIED,
     Tsang & Yang Table 8).
   - **Uninformed pressure reverses; informed in-play flow continues.**
     - In TradeSports, limit orders profit before the event, when flow is uninformed. During clustered in-play trading,
       copying the previous market order's direction earns a significant positive return (VERIFIED, Tetlock 2008
       §V.A).
     - In UFC, aggressive flow predicts *reversal*, but by less than the fees (abstract only, Adamczewski 2026).
   - **Practical rule to test:** fade moves only when they are not news-driven, and only as a maker.
4. **Lead–lag (G): the crypto lag is sub-second, and cross-venue "arbitrage" is mostly a measurement artefact.**
   - **Crypto.** Polymarket BTC 15-minute quotes follow ≥5 bp Binance moves after a median **347 ms**. Out of sample, a
     43-feature model *underperforms* the Polymarket mid. Simulated trading nets **−0.116 units per trade** (VERIFIED,
     Young 2026 §§5.2, 6, 10).
   - **Kalshi vs Polymarket.**
     - One paper reports **2–4%** "execution-aware" deviations, but it uses mid-quotes plus *assumed* spreads and fees
       (VERIFIED, Gebele & Matthes 2026 §5.4, App. I).
     - Moulinier's pre-registered test on executable one-minute quotes finds **no fee-clearing edge**. Deliberate
       mistiming inflates the apparent edge from 7% to 24–41% of minutes (abstract only).
   - **Historic venues did have real gaps.** Intrade vs Betfair in 2012 gave executed arbitrage of **6.38% over 3
     months** on $3,686, net of transaction costs (VERIFIED, Rothschild & Pennock 2014 §2.1). Bookmaker vs Betfair
     arbitrage appeared in **19.2% of matches** (VERIFIED, Franck et al. 2013). Both depended on segmentation and
     counterparty or account risk.
5. **Near-expiry favourites (H) earn little and carry tail risk.**
   - **BTC 5-minute.** The upper boundary is calibrated: average price **0.982** against a **98.4%** win rate. The
     lower boundary is over-priced: **0.024** against **1.4%** (VERIFIED, Zang et al. App. B.1).
     - That leaves about 0.2¢ gross per share for a buyer at 98¢.
     - The Crypto taker fee at p = 0.98 is 0.07 × 0.98 × 0.02 ≈ **0.14¢** per share (my calculation from CONTEXT.md
       fees; PLAUSIBLE). Net is close to zero.
     - Under a final-seconds Binance push, a [0.90, 1.00) favourite flips **34.2%** of the time (sibling, Dai et al.).
   - **Late comebacks.** Page (2012) reports that traders over-estimate a losing side's late comeback, so favourites
     are cheap at the very end (abstract only).
6. **Logical and combinatorial arbitrage (C) is real but small. It is paid for capital lock-up and resolution risk.**
   - **Polymarket multi-outcome sets.** Buying every YES leg costs *more* than $1, and the excess rises by **+0.06 per
     log(n)**. 96% of that is per-leg markup on cheap legs (VERIFIED, Zang et al. App. B.2, Table 5).
   - **Same-age drift above par.** Compared at the same age, the books' mid prices drift above $1. The drift is widest
     at 7–30 days to resolution (+0.081 per log n), where correcting it ties up capital longest (Table 6).
   - **Order-book replay.** Guaranteed profit after spreads and fees is **2.2% of committed capital** (abstract only,
     Zhai & Shi 2026).
   - **Our own scan agrees.** k-of-n constraints gave 3.4–3.6% over about 95–100 days (sibling
     `strategies/logical_arb.md`).
   - **Historic venues were far worse.** Intrade's NH-primary second-place set could be sold for **$1.082**, and minutes
     later bought for **$0.591** (VERIFIED, Rothschild & Pennock §2.2). PredictIt sets stayed above $1 for 271–433
     days in 2016 because of its 10% profit fee and $850 cap (VERIFIED, Stershic & Gujral 2020 §4.4).

## 2. Papers selected (ranked by usefulness to this project)

| # | Paper | Status | Full text read? | Relevance | Families |
|---|---|---|---|---|---|
| 1 | Xi, Moallemi, Pai, Wang, "Volatility in Prediction Markets: A Structural Approach" | arXiv 2607.08199v3 (preprint) | Mostly (§§1–6; appendices skimmed) | core | D, H, F |
| 2 | Zang, Andrade, Nakajima, "Who Aggregates Information? Screening, Rent, and the Coexistence of CLOB and AMM Prediction Markets" | arXiv 2609.20017v1 | Intro and App. B in full; theory skimmed | core | D, C, B, E, H |
| 3 | Tetlock, "Liquidity and Prediction Market Efficiency" | SSRN 929916 (WP, May 2008) | Mostly (§§I–V) | core | D, E, F |
| 4 | Young, "OpenMarket: A Synchronized Polymarket–Binance Dataset for High-Frequency Prediction-Market Research" | arXiv 2607.26245v1; HF dataset | Yes | core | G |
| 5 | Moulinier, "Mistiming is not Arbitrage: A Pre-registered Falsification of Cross-Platform Prediction-market Arbitrage…" | SSRN 7175258 / 7170178 | **No, abstract only** | core (unverified detail) | G, D, E |
| 6 | Rothschild, Pennock, "The extent of price misalignment in prediction markets" | *Algorithmic Finance* 3(1–2):3–20, 2014 | Mostly (§§1–2.3) | core | G, C, B |
| 7 | Angelini, De Angelis, Singleton, "Informational efficiency and behaviour within in-play prediction markets" | *IJF* 38(1):282–299, 2022 | Mostly (accepted MS) | core | F, E, H |
| 8 | Gebele, Matthes, "Semantic Non-Fungibility and Violations of the Law of One Price in Prediction Markets" | arXiv 2601.01706v1 | Partly (§§3, 5, App. I) | supporting | G, C |
| 9 | Zhai, Shi, "Combinatorial Arbitrage in Prediction Markets" | SSRN 7587019 (2026-10) | **No, abstract only** | core (unverified detail) | C |
| 10 | Tsang, Yang, "Political Shocks and Price Discovery in Prediction Markets: Evidence from the 2024 U.S. Presidential Election" | arXiv 2603.03152v4 | Mostly (§§1–5) | supporting | F |
| 11 | Singh, "Market Making Mechanisms and Liquidity Dynamics in Blockchain-Based Prediction Markets" | TUM MSc thesis, 2025-09-03 | Mostly (Chs. 4–6) | supporting | D (rewards) |
| 12 | Franck, Verbeek, Nüesch, "Inter-market Arbitrage in Betting" | *Economica* 80(318):300–325, 2013 | Partly (intro, data, liquidity) | supporting | G |
| 13 | Portnaya, "Do Prediction Markets Match Option Prices? Bitcoin Threshold Evidence from Binance and Polymarket" | arXiv 2606.19517v1 | Yes | supporting | G |
| 14 | Feil, Nendel, "Optimal Market Making in Prediction Markets" | arXiv 2607.17991v1 | Model and numerics; proofs skipped | supporting (theory) | D, H |
| 15 | Adamczewski, "Integration Without Leadership: Cross-Venue Price Discovery in UFC Prediction Markets" | SSRN 7194218 | **No, abstract only** | supporting | G, F |
| 16 | Ng, Peng, Tao, Zhou, "Price Discovery and Trading in Modern Prediction Markets" | SSRN 5331995 (rev. 2026-04-27) | **No, abstract only** | supporting | G, A |
| 17 | Stershic, Gujral, "Arbitrage in Political Prediction Markets" | *J. Prediction Markets* 14(1):69–99, 2020 | Mostly | supporting | C, B |
| 18 | Kim et al., "LLM as a Risk Manager: LLM Semantic Filtering for Lead–Lag Trading in Prediction Markets" | arXiv 2602.07048v2 | Yes | peripheral | G, C |

Families: A wallet-following, B complete-set arbitrage, C logical arbitrage, D liquidity provision, E favourite–longshot,
F mean reversion, G lead–lag, H near-resolution.

---

## 3. Paper-by-paper notes

### 3.1 Xi, Moallemi, Pai, Wang (2026), "Volatility in Prediction Markets: A Structural Approach"

- **Metadata (VERIFIED, arXiv API and PDF):**
  - Weiye Xi, Ciamac C. Moallemi, Shouqiao Wang (Columbia); Mallesh Pai (Tempo Labs). Moallemi discloses advisory
    roles at Paradigm and Uniswap Labs.
  - arXiv:2607.08199 [q-fin.TR]: v1 2026-07-09, **v3 2026-10-13**. Preprint, no journal ref.
- **Mechanism:**
  - Conditional variance is h² = **p(1−p)/τ + K·ν(V)·s²/4**.
  - The first term is a Wright–Fisher "deadline-resolution" channel: remaining binary uncertainty is released at rate
    1/τ.
  - The second is a binary Glosten–Milgrom channel: the squared half-spread times the arrival of informed flow, proxied
    by volume. A GARCH multiplier handles residual clustering (§2, eq. 8).
- **Data:**
  - Kalshi contract-hours, **August 2021 to April 2026**.
  - End-of-hour mid-quote, quoted spread, hourly volume and time to resolution.
  - Contracts with fewer than 48 quoted hours are dropped. Multi-leg KXMVE markets are excluded because their quotes
    are placeholders at 0/1 (§3.1).
  - Out-of-sample panel: **6,753,373 contract-hours from 41,348 contracts**.
- **Evidence type:** **out-of-sample forecasting.** Monthly expanding windows give 56 test months (§3.3). Scoring uses
  a Winkler interval score, QLIKE, and QLIKE against two-scale realised variance. This is not a trading test.
- **Costs and execution:** not applicable; mid-quotes only. Using mids avoids bid–ask bounce.
- **Dependence:** paired bootstrap for model rankings. Contract-cluster bootstrap CIs in the stylised facts (Fig. 1).
- **Key findings (VERIFIED):**
  - **Ranking (Table 3).** GARCH × DR-AS (√V) is best: VW-IS-EQ 0.5913, calibrated 95% coverage 0.951. The
    one-parameter structural model beats plain GARCH(1,1) by **15%** on interval score and roughly doubles the per-hour
    likelihood (§1).
  - **Drivers (Table 2).** Max/min bin ratio of next-hour RMS move:
    - time to resolution **22.6×**;
    - category 8.0×; volume 7.5×; price 3.5×; spread 2.2×.
    - Volatility "rises sharply in the final hours" but is roughly flat beyond one day to resolution (§3.4).
  - **Sports are event-driven (§5).** Only **4.1%** of hours fall in the large-move tail, but they carry **47.8%** of
    Sports volume. Economics contracts behave closest to smooth deadline resolution.
  - **Portability.** Re-estimating per category *worsens* out-of-sample performance on most volume (§5).
- **Tradable prospectively?** It is not a return signal. It is a real-time risk input, built only from
  forecast-origin variables, for:
  - quote width and size (D);
  - position sizing near expiry (H);
  - telling a "big move" from expected deadline volatility before calling it an overreaction (F). An x-cent move at
    τ = 1 h is ordinary; the same move at τ = 30 days is not.
- **Testable predictions for Polymarket:**
  1. Absolute hourly mid changes scale with √(p(1−p)/τ).
  2. The spread×volume term adds explanatory power.
  3. Sports single-game markets have jump-dominated volume.
- **Replication needs:**
  - Polymarket has no historical book (CONTEXT.md). Needed instead:
    - our own hourly `/books` snapshots going forward, or the third-party PMXT archive named in the sibling note;
    - CLOB `/prices-history` for mids, which is a trade/mid series and not executable;
    - Gamma `endDate` and `gameStartTime` for τ.

### 3.2 Zang, Andrade, Nakajima (2026), "Who Aggregates Information? Screening, Rent, and the Coexistence of CLOB and AMM Prediction Markets"

- **Metadata (VERIFIED):**
  - Chengqi Zang (Gensyn AI; Univ. of Tokyo), Gabriel P. Andrade (Gensyn AI), Tomoyuki Nakajima (Univ. of Tokyo).
  - arXiv:2609.20017v1 [econ.GN], 2026-09-17. Preprint, "© 2026 Gensyn".
- **Mechanism (theory, §§3–5):**
  - A prediction-market share has no noise flow to finance classical Glosten–Milgrom market making.
  - A CLOB quote posted inside the "signal band" before news gets picked off. Viable makers quote outside it, screen
    informed traders out, and earn a **screening rent by carrying the under-priced side to settlement**. That rent is
    financed by state-contingent behavioural "tail demand".
  - With n ≥ 3 outcomes, separate binary books leave the level of implied beliefs indeterminate, and each leg carries
    its own committed markup.
- **Data:**
  1. **BTC 5-minute up/down, about 24 hours:** 738,393 trades, 275 markets, $10.38M notional, 15,134 wallets. The date
     is not stated. Makers and retail are classified by two-sidedness, round-trip frequency, inventory mean-reversion,
     holding horizon and clip size (App. B.1).
  2. **Multi-outcome reconstruction:** 16,036 validated events (n = 2–10; every sibling resolved and exactly one Yes)
     from the Polymarket record of 2022-11-11 to 2026-03-29. 9,988 events had every leg priced on both sides; 3,343,329
     rows (App. B.2).
- **Evidence type:** descriptive and in-sample. The App. B.2 sequence is described as pre-registered.
- **Costs and execution:**
  - Maker PnL is net of fees. "Takers pay 1.8%, makers pay nothing and get no rebate" (§1.1).
  - In B.2, prices are **last trades**, not quotes: the ask is the last taker-buy and the bid the last maker-buy. About
    8% of rows show ask < bid.
- **Dependence:**
  - B.1: market-level cluster bootstrap for the regime result.
  - B.2: one event, one vote, with HC3 errors. Robustness: event × date two-way clustering and Driscoll–Kraay errors.
- **Key findings (VERIFIED, App. B):**
  - **Who earns (Table 1).**
    - 407 persistent makers: **+$45.3K**.
    - 12,749 retail wallets: −$66.7K.
    - Total −$51.0K, which is the fee take.
    - Makers' share: **91.4% from resolution**, 8.6% from spread.
  - **Where (Table 2).** Buy side ≈ +$70K, against ≈ +$2.6K on the sell side.
    - Buying at 0.50–0.80: +$52.4K. Buying at 0.80–1.00: +$24.8K.
    - Makers' directional inventory resolves in their favour 56.8% of the time.
  - **Regime sign flip (Table 3).** Calibration gap (price minus win rate):

    | Band | Pooled | Trending | Flippy |
    |---|---|---|---|
    | Longshot [0.20, 0.40) | +0.043 | **+0.225** | −0.071 |
    | Favourite (0.60, 0.80] | −0.037 | −0.205 | +0.066 |

  - **Boundaries.**
    - Upper tail calibrated: 0.982 against 98.4%. Lower tail over-priced: 0.024 against 1.4%.
    - Table 4: [0, 0.05) +0.010; [0.95, 1.00) −0.002.
  - **Multi-outcome set premium (Table 5).** Coefficients on log n:

    | Term | Coefficient | SE / p |
    |---|---|---|
    | Set premium, β_ask | **+0.0595** | se 0.0056 |
    | Committed markup, β_HS | +0.0573 | se 0.0029 |
    | Book centre, β_mid | +0.0022 | p = 0.52 |

    - The NO-side replication gives +0.048.
    - Requiring the latest trade on every leg to be at least 100 shares drives the slope to zero.
    - A pure tick floor explains 4–44% of the markup slope.
  - **Same-age centre drift (Table 6).** β_mid by time to resolution: < 1 day +0.009; 1–7 days +0.051; **7–30 days
    +0.081**; > 30 days +0.060. With age held fixed, sums of mids sit above par.
- **Tradable prospectively?**
  - The regime split uses each market's *whole* price path, so it is **hindsight** and not tradable.
  - The maker facts describe a population, not a strategy, though they do show maker rent is real in BTC 5-minute
    markets.
  - The set-premium result says buy-all-YES is never cheap. A sell-side or NO-basket test needs executable bids, which
    the paper does not use.
- **Corrections and discrepancies:**
  - "Makers … get no rebate" conflicts with CONTEXT.md, which says Crypto maker rebates are 20% of taker fees as of
    2026-10-17. Both may be true at different dates, because the sample date is not given. **Unresolved.**
  - The arXiv abstract and App. B.1 say only "a major prediction-market CLOB platform". §1.1 names it as Polymarket's
    Bitcoin five-minute up/down claim, and App. B.2 says Polymarket explicitly.
- **Replication needs:**
  - `/v2/trades?condition=…&taker_only=false` for BTC 5-minute markets, plus a wallet maker/taker classifier (the
    paper's rules are qualitative).
  - For B.2: Gamma `negRisk` events and executable `/books` snapshots instead of last trades.

### 3.3 Tetlock (2008), "Liquidity and Prediction Market Efficiency"

- **Metadata (VERIFIED):** Paul C. Tetlock. The PDF notes he joins Columbia Business School as of July 2008 and
  thanks Columbia, Texas and Yale for support. SSRN 929916 (DOI 10.2139/ssrn.929916). I read the May 2008 version from
  a Columbia-hosted PDF. A working paper; I found no journal version.
- **Mechanism:**
  - "Naïve" limit-order traders do not adjust for time-varying adverse selection. They subsidise liquidity during
    informative periods, which slows price discovery.
  - Their passive orders also sit on the wrong side of the favourite–longshot bias (FLB): buying longshots and selling
    favourites.
- **Data (§III):**
  - TradeSports order-book and trade statistics, scraped about every 30 minutes, **2003-03-17 to 2006-10-23**.
  - Single-day sports (about 70%) and stock-index (about 25%) contracts.
  - Plus trade-by-trade archive data that flags the initiator.
  - Commission ≤ 0.4% of $10 per side; non-marketable limit orders free from 2004-11-09.
- **Evidence type:** descriptive and in-sample. Returns to expiration by price bin. IV regressions using cross-market
  liquidity as instruments. Performance of market vs limit orders.
- **Costs and execution:** quotes come from mids. The returns are compared with the 0.8% maximum round-trip commission.
- **Dependence:** clustered by **expiry day**, which covers repeated sampling and related same-day events (§IV.A). This
  is the right template for our sports and crypto tests.
- **Key findings (VERIFIED):**
  - **Liquidity does not improve calibration (§IV.A, Fig. 2).** The FLB is "virtually always positive" whatever the
    liquidity, and 5–6% in some liquid financial bins against spreads below 1%. Exogenous liquidity *lowers* resolution
    (IV, §IV.B, Table IV).
  - **Limit orders lose when information arrives (§V.A, Table V).** After a trade cluster during the event:
    - market-order traders earn more than +1% per day, value-weighted, which narrowly exceeds the 0.8% round trip;
    - limit orders lose more than 1%.
  - **Pre-event, the roles reverse.** Limit orders earn about **+1%**, still positive after fees. Market orders lose
    more than 1% after fees.
  - **Order-flow continuation (Table V, row 3).** Taking the side of the *previous* market order earns a significant
    positive equal-weighted return. Prices only partly adjust to the previous five initiations.
  - **Limit orders feed the FLB (Table VI).** In sports, purchases are 55.6% of trades in price quintile 2 and 43.7% in
    quintile 4. Executed limit orders buy over-priced longshots and sell under-priced favourites.
- **Tradable prospectively?**
  - The pre-event maker edge and the in-play follow-the-last-aggressor edge use only past information, so in principle
    they are prospective.
  - Both are at most about 1%, on a 2003–06 venue with a 0.8% round trip.
  - On Polymarket, sports taker fees are 0.05 × p(1−p) per share (CONTEXT.md). Sports markets can also carry an order
    delay (`secondsDelay`), which works against a follow-the-flow taker.
- **Testable predictions for Polymarket D/F:**
  1. Maker markouts are negative in-play and positive pre-event.
  2. Short-horizon continuation follows in-play aggressor flow.
  3. Makers are net long longshots.
- **Replication needs:**
  - Taker-signed `/v2/trades` with timestamps.
  - Gamma `gameStartTime` to split pre-event from in-play.
  - Expiry-day clustering.

### 3.4 Young (2026), "OpenMarket: A Synchronized Polymarket–Binance Dataset for High-Frequency Prediction-Market Research"

- **Metadata (VERIFIED):**
  - Gregory Young (CS, Univ. of Colorado Boulder). arXiv:2607.26245v1 [q-fin.TR], 2026-07-28.
  - Dataset `huggingface.co/datasets/gregyoung14/openmarket-btc-polymarket` returned HTTP 200 today (VERIFIED).
  - Code `github.com/gregyoung14/openmarket` (tag v0.5.2): GitHub returned 403 to this sandbox, so **not verified**.
- **Mechanism tested:** trading Polymarket's BTC 15-minute up/down markets on Binance BTC/USDT order flow (latency and
  lead–lag).
- **Data (§§4, 9):**
  - 727,098,247 deduplicated rows: 605.6M Polymarket ticks, 62.3M Binance trades, 2,936,031 explicit lead–lag pairs.
  - Event data on 54 Polymarket days between **2026-02-12 and 2026-05-15**, single collector vantage.
- **Evidence type:** walk-forward **out-of-sample** logistic model with Platt scaling over 43 features (559 windows,
  357,390 rows across 2,251 markets), plus simulated trading.
- **Costs and execution:** simulated with **1% fees and 0.5% slippage**.
  - Under CONTEXT.md, Crypto taker fees are 0.07 × p(1−p) per share. At p = 0.5 that is 1.75¢ per $1 share, or 3.5%
    of notional. The paper's 1% assumption is probably lenient (PLAUSIBLE; the paper does not say whether its 1% is of
    face or of notional).
- **Dependence:** market-block bootstrap (2,251 blocks). Random row splits are discouraged.
- **Key findings (VERIFIED):**
  - **Response latency (§5.2).** Polymarket UP best bid moves after ≥5 bp Binance moves in 1 s with a **median 347
    ms**: 4,272 of 15,148 moves matched within 2 s, on a single collector clock.
  - **Source-clock lag (§9.2).** Median 16 ms (p5/p95 −186/316 ms), with ±99 ms constant-offset ambiguity. It does not
    change across disagreement quintiles (16–19 ms; Spearman ρ ≈ 0 between |Δbps| and lag).
  - **Spreads (Table 3).** Top-of-book spreads are a median of **one tick (0.01)**; p95 0.02.
  - **Forecasting (§10.4, Table 2).** Pooled out-of-sample:

    | Model | AUC | Brier | ECE |
    |---|---|---|---|
    | Logistic model | 0.8377 | 0.165 | 0.026 |
    | **Naive Polymarket mid** | **0.8405** | **0.163** | **0.014** |

    The in-sample lift (+0.0014 AUC) "does not survive walk-forward evaluation".
  - **Trading.** Simulated positive-EV trading nets **−0.116 normalised payoff units per attempted trade**.
- **Tradable prospectively?** **No** for a retail trader.
  - The lag is a few hundred milliseconds, and professional quoters arbitrage it.
  - The mid already beats a rich feature set.
  - The sibling platform note (`notes/platform/fees_incentives.md`, changelog rows) reports a crypto taker delay: 250
    → 50 ms on 2026-08-17, then 150 ms from 2026-09-04. CONTEXT.md does not mention it. The delay cuts both ways, but
    it does not open a retail window.
- **Replication needs:** none. The public HF corpus can be reused directly for G/H tests on BTC 15-minute markets
  (resolution labels included).

### 3.5 Moulinier (2026), "Mistiming is not Arbitrage: A Pre-registered Falsification of Cross-Platform Prediction-market Arbitrage, and the Two-sided Cancellation of the Favourite-longshot Premium" (abstract only)

- **Metadata (VERIFIED via Crossref):** Gaspard Moulinier. Two SSRN deposits created 2026-08-05: 10.2139/ssrn.7170178
  and 10.2139/ssrn.7175258, with slightly different capitalisation. **Full text not accessible**: SSRN returns 403,
  and no copy, preprint or repository was found by web search.
- **What the abstract claims (VERIFIED as the abstract's words; content UNVERIFIED):**
  - **Data.** Executable quotes: Kalshi one-minute bid/ask candles joined to "the full Polymarket CLOB archive". 855
    matched MLB moneylines and all four strikes of the June 2026 Fed decision.
  - **Divergence.** At true alignment the median cross-venue mid divergence is **0.60¢**, against a 2.00¢ Kalshi fee.
    Only **7.03% of 20,915 aligned minutes** carry a fee-clearing edge, with a median life of one minute.
    Pre-game minutes are profitable **0.00%** of the time (2,617 minutes).
  - **Mistiming.** Shifting one venue's quotes on purpose grows the apparent edge to 23.8% at 7 minutes and 40.8% at
    60 minutes.
  - **Both sides lose the FLB premium.** Takers pay a half-spread 5–7× the fee. Makers who avoid the fee realise
    **−7.39¢ per contract** (t = −13.6).
  - "Across nine pre-registered theses no fee- and spread-clearing edge survives"; the scripts are said to be
    reproducible.
- **Why it matters:** it is the only executable-quote, pre-registered cross-venue test found. It directly contradicts
  the 2–4% "execution-aware" deviations of Gebele & Matthes (§3.8), and it explains the gap by timestamp misalignment.
- **Replication needs:**
  - Kalshi public API candles (`api.elections.kalshi.com` is reachable per CONTEXT.md).
  - Our own Polymarket `/books` snapshots. The "full Polymarket CLOB archive" is presumably third party; UNSUPPORTED
    until the text is read.
  - Strict timestamp alignment.

### 3.6 Rothschild & Pennock (2014), "The extent of price misalignment in prediction markets"

- **Metadata (VERIFIED):**
  - David Rothschild, David M. Pennock (Microsoft Research NY).
  - *Algorithmic Finance* 3(1–2):3–20 (Crossref issued 2014-05-23), DOI 10.3233/AF-140031.
  - Read from researchdmr.com/files/PriceMisalignment.pdf, the journal version. An NBER 2012 conference draft also
    exists.
- **Mechanism:** identical contracts on segmented venues (currency, access, counterparty risk, fee structure). Hidden
  "shadow" liquidity. Human attention limits across linked contracts during news.
- **Data:** Intrade and Betfair 2012 US election and primary contracts. Ten contracts listed on both venues (§2.1).
  Order books captured every 2 minutes during the trial.
- **Evidence type:** **actual trading.** A randomised field trial over 8 days that bought matched arbitrage legs (§2.1).
  Descriptive otherwise; 12-hour lag regressions (Table 1).
- **Costs and execution:**
  - Explicit: Intrade $5/month; Betfair 2–5% commission on net winnings. They estimate about 3% typical and about 6%
    maximum all-in for a small trader, plus currency and counterparty risk.
  - Shadow liquidity: in 4 of 6 entries they bought inside the displayed ask, and depth refilled within minutes.
- **Dependence:** none modelled; the evidence is per contract.
- **Key findings (VERIFIED):**
  - **Cross-venue (§2.1).**
    - The Obama contracts were more than 5 pp apart on **64 of the last 85 days**. The gap peaked above 23 pp at 8:05
      PM ET on Election Day, and misalignment *grew* as Election Day approached.
    - The trial invested **$3,686 for a 6.38% return over 3 months, after transaction costs but before opportunity
      cost**.
    - Conservative estimate: $15–20k extractable over the last few months, against $1–5k visible in the books.
    - One trader supplied **35.0%** of all pro-Romney money on Intrade in the last two weeks and paid about a 20–25%
      premium over Betfair (non-profit-maximising).
  - **Within-exchange (§2.2).**
    - Intrade's NH-primary second-place set could be **sold for $1.082** in the days before the primary. Right after
      the polls closed, it could be **bought for $0.591**.
    - Party < candidate violations: buy Democratic Party to Win at 0.491 and sell Obama to Win at 0.501.
    - Less salient linked contracts lose their bids during news. Betfair finals markets lost all bids during the
      semifinal.
  - **Bounded rationality (§2.3).**
    - The sum of asks is further from $1 than the sum of bids: 153 vs 100 days; 92 of 159 in-game snapshots.
    - Intrade's 12-hour-lagged price helps predict Betfair's price but not the reverse (Table 1, 2,175 observations).
- **Tradable prospectively?** Yes then, and demonstrated with real money, but small. Capacity was a few thousand dollars
  net, the venues were segmented, and Intrade later froze accounts (§2.1 fn. 3).
- **Testable predictions for Polymarket:**
  1. Linked-contract violations cluster in moments of high information flow (C).
  2. Cross-venue gaps widen near resolution, when segmentation binds (G).
  3. Asks are systematically further from par than bids, so the sell-side basket is the better side (B/C).
- **Replication needs:** our own `/books` snapshots during news events. Polymarket neg-risk sets do let "sell all"
  happen through NO conversion (sibling Gebele et al.).

### 3.7 Angelini, De Angelis & Singleton (2022), "Informational efficiency and behaviour within in-play prediction markets"

- **Metadata (VERIFIED, Crossref and accepted manuscript):**
  - Giovanni Angelini, Luca De Angelis (Bologna); Carl Singleton (Reading).
  - *International Journal of Forecasting* 38(1):282–299, January 2022. DOI 10.1016/j.ijforecast.2021.05.012.
  - Read from the CentAUR accepted manuscript (May 2021).
- **Mechanism:** a Mincer–Zarnowitz-style efficiency framework applied pre-match and after the first goal, which is
  clean news. Biases: reverse FLB (a favourite bias), confirmation bias, under- or over-reaction.
- **Data (§III):**
  - **1,004 EPL matches, 2009-08-15 to 2014-05-11**, a within-season random subset of 1,900.
  - Betfair final-result odds every **10 seconds**, bought from a third party. The text does not say whether these are
    back, lay or traded prices (UNSUPPORTED either way).
  - Pre-match out-of-sample: 2019/20 EPL (380 matches).
- **Evidence type:** in-sample regressions and **in-sample** betting regions. Pre-match also has an **out-of-sample**
  season. The in-play out-of-sample result (last 100 matches) is only "available on request".
- **Costs and execution:** ROIs are **gross of Betfair commission** (up to 5%, 2% for many users; §III fn. 14). No
  depth or slippage.
- **Dependence:** matches are the unit. Goals within a match are filtered: later news before t+h is excluded.
- **Key findings (VERIFIED):**
  - **Pre-match: a reverse FLB (Table 2).**
    - Under-priced regions are home p ≤ 0.24 and away p ≤ 0.14.
    - Betting them gives gross ROI **40.05%** (183 home bets) and **56.41%** (195 away bets) in-sample.
    - **Out-of-sample 2019/20: 51.9%** on 175 bets at average decimal odds 10.3 (implied 9.8% against a realised
      17.7%).
  - **After the first goal (Table 3, Fig. 3).**
    - When the away team scores, home odds are efficient, and vice versa.
    - When a team scores, *its own* odds are mispriced: most strongly at 20 s and still significant at 5 minutes.
    - **An early goal by the favourite is over-priced** (over-confidence). **A goal by the longshot, especially late,
      is under-priced.**
  - **In-play betting regions (Table 4, in-sample, 882 matches).** Gross ROIs at h = 2, 5 and 30 ticks:
    - home team scoring: 35.27%, 10.74%, 11.97%;
    - away team scoring: 70.42%, 67.16%, 24.58%;
    - betting the over-priced regions loses.
- **Conflict with Choi & Hui (2014), whom the paper itself cites:** they report over-reaction to *highly surprising*
  goals; this paper finds under-reaction to surprise and over-reaction to expected news. Choi & Hui is abstract-only
  here (§5), so I cannot adjudicate.
- **Tradable prospectively?**
  - The pre-match favourite bias held out of sample (gross), which is notable. Small samples, though: about 175 bets
    a season.
  - The in-play regions are fitted in-sample on 10-second data without spreads or commission. Not shown tradable.
- **Replication on Polymarket sports:**
  - The `/v2/trades` tape for soccer markets, plus a goal-time feed (the Polymarket sports WebSocket; sibling platform
    notes).
  - Sports taker fees and `secondsDelay`.
  - Clustering by match.

### 3.8 Gebele & Matthes (2026), "Semantic Non-Fungibility and Violations of the Law of One Price in Prediction Markets"

- **Metadata (VERIFIED):** Jonas Gebele, Florian Matthes (TU Munich). arXiv:2601.01706v1 [cs.CE], 2026-01-05. No
  journal ref.
- **Mechanism:** economically equivalent claims on different venues are not fungible. Resolution semantics, cutoffs and
  oracles differ, and they cannot be netted. So arbitrage needs capital locked to resolution, and the Law of One Price
  fails "structurally".
- **Data:**
  - A human-validated alignment of **over 100,000 events across ten venues, 2018–2025**.
  - About **6% of events are listed on more than one venue concurrently**.
  - The price analysis covers 7 venues.
- **Evidence type:** descriptive, plus a naive in-sample "strategy".
- **Costs and execution:** "execution-aware" means **reported mid-quotes ± a standardised δ**, not actual quotes (§3.1;
  App. I Table 3).
  - Kalshi fee fixed at 1.5%; Polymarket fee 0%; spread $0.01.
  - Slippage "assumed negligible" (§5.5 fn. 7).
- **Dependence:** none.
- **Key findings (VERIFIED):**
  - Median deviations in even the most liquid constructions are **2–4%** from execution-adjusted parity. Maximum
    deviations must persist for at least an hour (Fig. 6).
  - Many pairs hold an "arbitrage" over nearly the whole overlap; others are absorbed by fees (Fig. 7).
  - A mechanical "enter the highest-yield equivalent arbitrage" policy returns **1,218.66% over 800 days across 15
    trades** (§5.4).
  - In the 2024 election, Polymarket YES vs Kalshi NO was a subset–superset pair, because Polymarket resolved on media
    calls and Kalshi on inauguration. Execution-adjusted spreads averaged about $0.03 and reached up to $0.07 (§5.5,
    Fig. 9).
- **Tradable prospectively?** Not shown.
  - The prices are mids with assumed costs.
  - Pairs are aligned with ex-post human validation.
  - The 15-trade compounding figure ignores capacity.
  - Moulinier (§3.5, abstract) finds no edge at executable quotes in MLB and Fed markets.
  - The paper's own case study shows the gap partly prices **resolution-semantics risk**, which is not riskless.
- **Replication needs:** the alignment dataset ("price data on request only"; App. G), plus executable quotes on both
  venues.

### 3.9 Zhai & Shi (2026), "Combinatorial Arbitrage in Prediction Markets" (abstract only)

- **Metadata (VERIFIED via Crossref):** Daojing Zhai, Hongjian Shi. SSRN 7587019, Crossref created 2026-10-10. **Full
  text not accessible** (SSRN 403; web search found no copy).
- **Abstract claims (content UNVERIFIED):**
  - Prices outside the convex hull of admissible payoff vectors admit arbitrage. Optimal portfolios are found by
    integer programming.
  - **1.9 million logical relations** are recovered over more than 255,000 contracts.
  - They "replay full-depth Polymarket order books" to simulate execution against resting orders.
  - **Guaranteed profit after spreads and fees = 2.2% of committed capital**; profit at resolution 3.2%.
  - Opportunities persist longer where relation discovery and execution cost more.
- **Assessment:** the magnitude agrees with the project's own k-of-n scan (3.4–3.6% over about 95–100 days) and with
  Gebele et al.'s small realised totals (sibling). "Committed capital" without a holding period cannot be annualised
  here. The source of the order-book history is unknown, since there is no official historical book.

### 3.10 Tsang & Yang (2026), "Political Shocks and Price Discovery in Prediction Markets: Evidence from the 2024 U.S. Presidential Election"

- **Metadata (VERIFIED):**
  - Kwok Ping Tsang (Virginia Tech), Zichao Yang (Zhongnan Univ. of Economics and Law).
  - arXiv:2603.03152 [econ.GN]: v1 2026-03-03, **v4 2026-07-18**, dated 2026-07-21.
- **Data (§2):**
  - NegRisk CTFExchange `OrderFilled` logs from Polygon RPC, **2024-01-05 to 2024-11-06**.
  - **3,654,974 matched trades, 232,469 addresses** in the Trump, Biden and Harris markets.
  - Platform, conversion and market-maker wallets are filtered: 2,176 + 355 + 91.
  - The initiator comes from the ledger. The tick rule agrees on 97% (Table A.2).
- **Evidence type:** event study of **three** shocks (debate, assassination attempt, withdrawal), at 5-minute bins
  with 30-minute and 3-hour horizons.
- **Costs and execution:** none.
- **Dependence:** trader-by-event fixed effects; errors clustered by trader-event.
- **Key findings (VERIFIED):**
  - **Price paths (Table 8).**

    | Shock | ΔTrump YES at 30 min | ΔTrump YES at 3 h | Path |
    |---|---|---|---|
    | Debate | +0.04 | +0.02 | about half reversed |
    | Assassination attempt | +0.05 | +0.10 | continued |
    | Withdrawal | −0.03 | −0.01 | Harris +0.14, Biden −0.07 |

  - **The withdrawal was largely priced in.** The Democratic-nominee market already put 0.70 on Biden being replaced
    (Table 9).
  - **Withdrawal flow (Table 6).** In the first 30 minutes, 94% of taker flow cut Trump exposure: 13 wallets sold
    $160,600 of YES and 16 bought $102,100 of NO. Most YES shares bought were newly minted.
  - **Persistence vs reversal (§5.4, Fig. 11).** A rolling Glosten–Harris decomposition (7-day trailing window) shows
    a larger *transitory* component after the debate and a *permanent* one after the assassination attempt.
- **Tradable prospectively?** No. With n = 3 there is no basis for a rule. The decomposition is computable in real
  time, which makes it a candidate *filter* for F (fade only when the transitory component dominates), but it is
  untested.
- **Replication needs:** `/v2/trades` with taker side for neg-risk sets, a rolling λ and Glosten–Harris estimate, and
  many more events.

### 3.11 Singh (2025), "Market Making Mechanisms and Liquidity Dynamics in Blockchain-Based Prediction Markets" (TUM MSc thesis)

- **Metadata (VERIFIED, PDF):**
  - Parshant Singh, Master's thesis in Informatics, TU Munich (sebis chair of Prof. Florian Matthes; advisor Jonas
    Gebele). Submitted **2025-09-03**.
  - https://www.cs.cit.tum.de/fileadmin/w00cfj/sebis/_my_direct_uploads/20250903_Parshant_MA_Thesis.pdf
  - AI-assistant use disclosed. Not peer-reviewed. Code: github.com/singhparshant/polymarketData (not checked).
- **Data (§§4.1, 5):**
  - AMM era: 2,643 FPMMs, October 2020 to November 2024, about 3,000 LPs.
  - CLOB: 3,100 markets, more than 1.2M matched orders, about 800 makers. The CLOB sample period is not stated.
  - Rewards: all transfers from distributor contract `0xc288…`, **2023-11-25 to 2025-07-24**.
  - Sources: Goldsky subgraphs and the PolygonScan API. CONTEXT.md notes the subgraph is now deprecated.
- **Evidence type:** descriptive.
- **Costs and execution:**
  - CLOB maker PnL is pure **spread capture**: any residual inventory is liquidated at the last execution price
    (§4.3.1).
  - This **excludes settlement PnL**, where adverse selection shows up: Zang et al. find 91.4% of maker profit comes
    at resolution.
  - Rewards cannot be attributed to markets (§4.3.2).
- **Key findings (VERIFIED):**
  - **Reward totals.** About **$9.3M** paid in total. Peak week **$242.4K** (Q4 2024). Top address over $1.0M; top
    five about 22% (10.9%, 3.1%, 2.9%, 2.7%, 2.3%). 46,653 recipient addresses (§5.2, Fig. 5.12).
  - **Spreads.** Same-maker opposite trades within 1 h imply an average spread of **$0.023** across about 59,000
    pairs, "within the typical reward-eligible range of 3 cents".
  - **Maker profitability.** 69.7% of makers and 76.1% of maker–market pairs are profitable on spread capture.
  - **AMM LPs.** Impermanent loss exceeds fees on average, across sizes. The best LPs exit before resolution.
- **Correction:** §5.3.3 says "rewards increase with the square of the distance from the mid-price". The official
  formula `S(v,s) = ((v−s)/v)²·b` (docs.polymarket.com/programs/liquidity-rewards, VERIFIED today) means the score
  **falls** quadratically with distance.
  - Today's docs also give: two-sided scoring with c = 3.0 and single-sided orders scoring only for mids in [0.10,
    0.90]; minute-level random sampling (1,440 samples per UTC day); a $1 minimum payout.
- **Tradable prospectively?** It establishes that rewards exist and are concentrated. It does **not** establish that
  quoting for rewards is profitable after adverse selection.
- **Replication needs:**
  - `/v2/activity?user=` REWARD rows per maker.
  - CLOB `/rewards/markets/*` configurations.
  - Markouts that include settlement.

### 3.12 Franck, Verbeek & Nüesch (2013), "Inter-market Arbitrage in Betting"

- **Metadata (VERIFIED):** Egon Franck, Erwin Verbeek, Stephan Nüesch (Zurich). *Economica* 80(318):300–325, DOI
  10.1111/ecca.12009 (online 2012-12-17). Read from a Univ. of Fribourg copy of the published article.
- **Data:**
  - 10 bookmakers (football-data.co.uk odds, recorded Friday or Tuesday afternoon) matched to Betfair, **11,933
    matches in the top five leagues, 2004/05–2010/11**.
  - Betfair data are cross-sectional per traded odds (first and last taken, volume). The exchange quote is picked as
    the highest-volume odds that could have been live when the bookmaker odds were recorded.
- **Key findings (VERIFIED):**
  - 102 intra-bookmaker arbitrage opportunities.
  - **2,287 bookmaker-vs-exchange opportunities (19.2% of matches), average return 1.4%**. Bettors gain 1.6% on the
    bookmaker leg and lose 0.2% on the exchange hedge.
  - Arbitrage matches are *more* liquid on Betfair (£588,134 vs £378,266 pre-play). Requiring more than £10,000
    matched at the odds loses only 26.6% of opportunities.
  - Interpretation: bookmakers post "promotional" mispricing and later limit stakes or close accounts (§1).
- **Tradable prospectively?** Plausibly, but only for accounts that bookmakers do not restrict. Exchange odds are
  inferred, not time-stamped quotes.
- **Relevance:** the analogue is Polymarket sports against sportsbooks. The paper suggests bookmaker lines can be
  *stale*, not informative leaders. This is a test design for G, not evidence about Polymarket.

### 3.13 Portnaya (2026), "Do Prediction Markets Match Option Prices? Bitcoin Threshold Evidence from Binance and Polymarket"

- **Metadata (VERIFIED):** Victoria Portnaya (Kyiv School of Economics). arXiv:2606.19517v1 [q-fin.TR], 2026-06-17.
- **Data:**
  - Three mid-2023 Polymarket BTC threshold contracts (main: "BTC above $27,000 at end of September?").
  - Matched to Binance options with identical strike and expiry (EOHSummary hourly bid/ask).
  - Polymarket prices are the latest trade or hourly price at or before each hour, so **not executable**.
  - 214 hourly observations (main contract); 287 pooled.
- **Key findings (VERIFIED):**
  - **Wedge.** Mean gap **+5.6 pp** (t = 6.46; HAC CI [2.3, 8.9] pp); pooled **+6.3 pp**.
  - **Persistence.** AR(1) φ = 0.849, so the **half-life is 4.2 h**. The ADF test rejects a unit root (p = 0.004)
    (Table 2).
  - **Where the gap is largest.** At low implied probabilities and long maturities.
  - **Proxy backtest (Table 6).** Delta- and vega-hedged with options plus spot, rebalanced hourly. **16 trades**, net
    PnL 1.113 units, net α 0.067 (**p = 0.053**). Median hold 3.5 h.
  - **Other benchmarks.** Against Deribit the pooled gap is 11 pp (2,585 observations). Ethereum results are mixed.
- **Tradable prospectively?** The signal is ex ante, but the evidence is far too thin to act on: 16 trades, 2023, zero
  Polymarket fees then, trade prices. It is consistent with longshot over-pricing in crypto threshold markets (E).
- **Replication needs:** Deribit and Binance option quotes (Binance public data is reachable per CONTEXT.md), plus
  executable Polymarket asks.

### 3.14 Feil & Nendel (2026), "Optimal Market Making in Prediction Markets"

- **Metadata (VERIFIED):** Dominik Feil, Max Nendel. arXiv:2607.17991v1 [q-fin.TR, math.OC], 2026-07-20 (dated
  2026-07-21). NSERC-funded. No journal ref.
- **Model:**
  - An Avellaneda–Stoikov-type HJB for a binary claim. The price is a martingale (logistic transform of a latent
    belief diffusion); fills are Poisson in the quote distance.
  - Running penalty γq²ς² and terminal settlement penalty γ_T·q²·p(1−p).
  - **No adverse selection and no jumps**: fills are independent of the price process. Parameters are "illustrative,
    not calibrated" (§4.1).
- **Predictions (VERIFIED, Figs. 1–4):**
  - Spreads narrow over time as liquidity rises, but **widen near settlement for p near 0.5**.
  - Spreads are larger near 0.5 at any time.
  - Without inventory, skew is positive below 0.5 and negative above.
  - **Inventory risk vanishes as p → 0 or 1.**
- **Simulation (Table 2, 10,000 paths).** The inventory-aware policy keeps mean PnL (12.39 vs 12.47 for myopic) but
  cuts the standard deviation from 28.11 to 10.34 and 5% VaR from 32.41 to 4.20.
- **Use:** a baseline quoting rule. Its missing adverse-selection channel is the dominant empirical cost (§§3.2, 3.3,
  3.5). Pair it with Xi et al.'s variance forecast.

### 3.15 Adamczewski (2026), "Integration Without Leadership: Cross-Venue Price Discovery in UFC Prediction Markets" (abstract only)

- **Metadata (VERIFIED via Crossref):** Michał Adamczewski. SSRN 7194218, Crossref created 2026-07-29. **Full text not
  accessible**; web search found no copy or repository.
- **Abstract claims (content UNVERIFIED):**
  - **Data.** 281 UFC fights matched across Kalshi and Polymarket over fourteen months.
  - **No leader.** Same-bar co-movement is +0.103 at 5 minutes and +0.203 at 30 minutes. **No lead–lag correlation
    is distinguishable from zero at any horizon.**
  - **Jumps and gaps.** Large jumps propagate symmetrically. Inter-venue gaps close within about 30 minutes on liquid
    fights.
  - **Order flow.** A **pre-registered** test finds aggressive order flow predicts **reversal, with magnitude well
    inside fees**.
- **Relevance:** contradicts the election-based "Polymarket leads Kalshi" (Ng et al., §3.16) in the sports setting
  where volume actually is, and adds a liquidity-shock reversal result (F) that is not tradable after fees.

### 3.16 Ng, Peng, Tao & Zhou (2025/2026), "Price Discovery and Trading in Modern Prediction Markets" (abstract only)

- **Metadata (VERIFIED via Crossref and web search):**
  - Hunter Ng, Lin Peng, Yubo Tao, Dexin Zhou. SSRN 5331995 (Crossref created 2025-07-01). The SSRN page shows a
    revision dated 2026-04-27 and 62 pages.
  - **Full text not accessible.** Seminar pages (RUC, SZU, PKU, UM) carry only the abstract.
- **Abstract claims:**
  - Common contracts on Polymarket, Kalshi, PredictIt and Robinhood before the 2024 US election.
  - More liquid markets beat polls.
  - **Polymarket leads Kalshi**, especially when liquidity and activity are high, "implying economically meaningful
    arbitrage opportunities".
  - **Net order imbalance from large trades predicts subsequent returns**, and the venue with more directional
    large-trade flow leads.
- **Secondary:** Feil & Nendel (§1.1) cite it as showing market returns predict subsequent polls (PLAUSIBLE; not
  checked in the source).
- **Caveat:** one event, the most salient market ever. Adamczewski finds no leader in UFC; Moulinier finds no
  executable edge in MLB and Fed markets.

### 3.17 Stershic & Gujral (2020), "Arbitrage in Political Prediction Markets"

- **Metadata (VERIFIED):** Andrew Stershic (Duke, later Sandia), Kritee Gujral (UW). *Journal of Prediction Markets*
  14(1):69–99, DOI 10.5750/jpm.v14i1.1796. Open access (ubplj.org).
- **Data:** PredictIt 2016 (general, DNOM, RNOM) and 2020 (to 2020-01-10) markets; IEM 2016 nominations. **Daily**
  open, close, high and low trades.
- **Costs and execution:**
  - The bid is proxied as `max(0, min(close, high − tick))`. These are trades, not quotes (§4.1 fn. 2).
  - The 10% profit fee is included; the 5% withdrawal fee is not.
- **Key findings (VERIFIED):**
  - PredictIt sell-all mispricings above 20¢ lasted **271 days (DNOM), 391 (RNOM) and 433 (USPRES)**, against 0 days on
    IEM (§4.4).
  - The largest arbitrage was **170¢ per share** (RNOM, February 2016), about $1,445 at the $850 cap. The 2020 maximum
    was $85.
  - Margin-linking (October 2015) cut the sums sharply. After December 2015 the 10% profit fee left arbitrage profit
    at about zero (§4.1.1, Fig. 3).
  - Higher volume was associated with *worse* pricing (§4.2).
- **Status:** largely superseded by Zitzewitz (2026; sibling FLB note), who uses hourly API quotes from 2019. Kept as
  the clean demonstration that **fee design and position caps, not information, sustain linked-set violations**. The
  lesson for Polymarket: neg-risk conversion and the absence of caps should keep sums near par except on cheap legs and
  long horizons, as Zang et al. find.

### 3.18 Kim et al. (2026), "LLM as a Risk Manager: LLM Semantic Filtering for Lead–Lag Trading in Prediction Markets" (peripheral)

- **Metadata (VERIFIED):**
  - Sumin Kim, Minjae Kim, Jihoon Kwon, Yoon Kim, Nicole Kagan (Kalshi), Joo Won Lee, Oscar Levy, Alejandro
    Lopez-Lira, Yongjae Lee, Chanyeol Choi (LinqAlpha and others).
  - arXiv:2602.07048 [q-fin.RM]: v1 2026-02-04, v2 2026-02-27.
- **Method:**
  - Granger screen on daily log-odds across **554 Kalshi Economics markets (October 2021 to November 2025)**.
    Rolling 60-day train and 30-day test, 18 test windows; top 100 pairs, re-ranked by GPT-5-nano to the top 20.
  - Trade the follower one day after a leader move above a threshold θ; hold h days.
- **Results (Table 1).**

  | Ranking | Win rate | Average loss | Total PnL |
  |---|---|---|---|
  | Granger only | 51.4% | −$649 | $4,100 |
  | Granger + LLM | 54.5% | −$347 | $12,500 |

  - Positions are 100 contracts.
  - Same-event threshold pairs (Table 2) are logical relatives, so part of the "lead–lag" is C.
- **Costs:** **no fees, spreads or significance tests reported**. Daily "market-implied prices" are not defined as
  executable.
- **Assessment:** frictionless and small. It shows that statistically screened cross-market lead–lag is fragile. Not
  evidence of a tradable edge.

---

## 4. Cross-paper contradictions and measurement lessons

1. **Cross-venue edge depends on the price you measure.**

   | Measure | Result | Source |
   |---|---|---|
   | Mids plus assumed costs | 2–4% median | Gebele & Matthes |
   | One election, abstract | "Meaningful arbitrage" | Ng et al. |
   | Aligned executable one-minute quotes, abstract | 7% of minutes clear the fee; median life 1 min | Moulinier |
   | UFC, abstract | Gaps close within about 30 min; no leader | Adamczewski |

   Moulinier's mistiming sweep shows how 1–60 minutes of timestamp error manufactures edges (abstract). **Rule for
   our G tests:** quotes on both venues must be sampled within seconds of each other, and the edge measured at asks
   and bids, not mids.
2. **Mean reversion after shocks depends on whether the shock carried news.**
   - **Moves stick when they carry news:** Croxson & Reade (sibling); the assassination attempt in Tsang & Yang.
   - **Moves reverse when the flow is uninformed:** Tetlock's pre-event limit-order profits; the debate in Tsang &
     Yang; UFC aggressive flow in Adamczewski (abstract); the hand-picked Polymarket "No" contracts in the sibling
     Vojtko–Dujava reproduction.
   - **In-play informed flow continues:** Tetlock's lagged-initiator strategy.
   - **The surprise direction is contested:** Angelini et al. (under-reaction to surprise) vs Choi & Hui (over-reaction
     to big surprises; abstract only).
   - Every positive reversal result is at most about one spread wide before fees.
3. **"Makers win" has to be qualified.** It holds on average and at settlement:
   - Zang et al.: BTC 5-minute makers +$45.3K in 24 h;
   - Bartlett & O'Hara and Bürgi et al. (siblings);
   - Gupta (abstract: +0.83 pp on Kalshi).

   But makers lose in informative windows: Tetlock; Bartlett & O'Hara's top-quintile VPIN; Dai et al.'s manipulated
   cycles. In Moulinier's sports and Fed sample, fee-avoiding makers lose −7.39¢ per contract (abstract). A retail LP
   is a *new* maker with no information. The literature says its fills will be adversely selected unless it withdraws
   during news.
4. **Spread-only maker PnL is the wrong estimand.** Singh's inventory-flattening at the last trade (§3.11) leaves out
   settlement, which is where Zang et al. find 91% of maker profit and where adverse selection is realised. Our LP
   markout study must mark to resolution, and also at 1 min, 1 h and pre-close.
5. **Last-trade vs quote data.** Zang B.2, Stershic & Gujral, Portnaya and Kim et al. use trade prices. Only Young,
   Xi et al., Tetlock (mids), Rothschild & Pennock (books and real trades) and Moulinier (abstract) use quotes.
   CONTEXT.md's warning applies: `/prices-history` and last trades are not executable.
6. **Fees moved under every sample.**
   - Portnaya (2023) and Gebele & Matthes (2024 election) predate Polymarket fees.
   - Young assumes 1% while the live Crypto rate is 0.07·p(1−p) per share.
   - Zang et al.'s "no maker rebate" conflicts with CONTEXT.md's 20% Crypto maker rebate.
   - Use per-market Gamma `feeSchedule`.

## 5. What the literature implies for the project's tests (testable predictions)

| Family | Prediction to test on Polymarket | Source | Data we can get |
|---|---|---|---|
| D | Maker markouts are positive pre-event and negative in-play; the loss concentrates after trade clusters | Tetlock §V; Bartlett & O'Hara (sibling) | `/v2/trades` with `taker_only=false`; `gameStartTime` |
| D | Reward income per market is below the in-play adverse-selection cost except in markets with sponsored pools | Singh; docs; Telonex (lead) | REWARD activity rows; `/rewards/markets/*` |
| D/H | Next-hour absolute mid change ∝ √(p(1−p)/τ); sports volume concentrated in jump hours | Xi et al. | Our own hourly `/books` snapshots; CLOB `/prices-history` (mid series) |
| F | Large moves with concentrated single-wallet flow and no news revert; moves with news do not | Tetlock; Tsang & Yang; Adamczewski | `/v2/trades` with wallets; a news timestamp proxy (none public, so this is a gap) |
| G | Polymarket BTC up/down quotes lag Binance by hundreds of ms; no retail edge | Young | The OpenMarket HF corpus; Binance public data |
| G | Kalshi–Polymarket gaps at synchronous executable quotes rarely clear fees; mid-based gaps are inflated by mistiming | Moulinier; Gebele & Matthes | Kalshi public API plus our `/books` capture |
| H | 95–99¢ favourites are calibrated or slightly cheap, but net of fees and flip risk the edge is ≈ 0 | Zang B.1; Page (abstract); Dai et al. (sibling) | `/v2/trades`; resolutions |
| C | Set violations concentrate in large n, cheap legs, 7–30 days to resolution and news bursts; executable profit is about 2–4% of capital | Zang B.2; Zhai & Shi; Rothschild & Pennock | Gamma neg-risk events; `/books` |

## 6. Secondary leads (metadata VERIFIED via Crossref or arXiv; content as stated)

| Item | ID | Why it matters | What I saw |
|---|---|---|---|
| Choi, D. & Hui, S.K. (2014), "The role of surprise: Understanding overreaction and underreaction to unanticipated events using in-play soccer betting market", *JEBO* 107:614–629 | DOI 10.1016/j.jebo.2014.02.009; SSRN 2011564 / 1988974 | F; conflicts with Angelini et al. | Metadata via Crossref. **Not read**: the AUT working-paper PDF returned a Cloudflare challenge, and WebFetch got 403. The content comes from the search snippet and Angelini et al.'s summary: under-reaction in general, over-reaction to highly surprising goals |
| Page, L. (2012), "'It ain't over till it's over.' Yogi Berra bias on prediction markets", *Applied Economics* 44(1):81–92 | DOI 10.1080/00036846.2010.498578 | H | Abstract read (IDEAS): calibration "deteriorates very significantly in the last moments"; traders over-estimate the losing team's comeback. Stershic & Gujral's Table 1 lists the data as TradeSports 2006–07 (secondary). Full text: QUT eprints returned 403/503 |
| Lee, S., Lee, Y. & Lee, J. (2026), "Cryptocurrency prediction markets through the derivatives lens: Evidence from Kalshi and Polymarket", *IRFA* (November 2026) 105433 | DOI 10.1016/j.irfa.2026.105433; SSRN 6748186 | G, E (crypto) | Abstract only (SSRN record): 113,338 BTC and ETH contracts, September 2025 to February 2026. Positive VRP; Polymarket's is about 16× Kalshi's, attributed to its forward-start design anchoring prices near 0.50. Both venues "systematically underconfident". The only peer-reviewed item in this sweep's G set; ScienceDirect not accessible |
| Malék, A. (2026), "Order Flow Imbalance and Price Discovery on Prediction Markets: Evidence from Kalshi" | SSRN 7520438 | D, F | Abstract only: 143,297 snapshots over 13 days; OFI R² 0.29 for sports futures, 0.13 weather, 0.02 macro; standardised β = 0.45 |
| Agarwal, M. (2026), "Noise, Ghosts, and Adverse Selection: Market Microstructure in Decentralized Sports Prediction Markets" | SSRN 7273479 | D, G (sports latency) | Abstract only: 25 T20 cricket matches; a **6.63 s** gap between informed on-chain execution and public API registration; 58 "ghost orders" (a 116.4 ms flash-to-pull cycle) that vanish before wickets |
| Krause, D. (2026), "Same Bet, Different Markets…" | SSRN 6861841 | G | Abstract only: a single CLARITY Act market; 9 trades with a 100% win rate. Too small; treat as anecdote |
| Gupta, A. (2026), "Who Profits in Binary Prediction Markets? Maker-Taker Dynamics…on Kalshi" | SSRN 6858200 | D, E | Abstract only: 72.1M Kalshi trades plus 404.5M Polymarket trades. Maker +0.83 pp, rising 8.21 bp/month, no time-to-resolution decay (p = 0.88). Kalshi longshots over-priced, Polymarket favourites above 55% under-priced. The Kalshi totals match Becker's public dataset (sibling), so it is probably the same data (PLAUSIBLE) |
| Sultan, O. & Morstatter, F. (2026), "The Conversation Turns First…" | arXiv 2609.28965v1 | F (peripheral) | Read in part: 79 non-political markets chosen by lifetime contestedness (hindsight). Leader reversals are predicted mainly by market state; no PnL |
| Ibrahim, H. & Zaki, Y. (2026), "Price Dislocations, News Citations, and Epistemic Leverage on Polymarket" | arXiv 2609.06005v1 | F (liquidity shocks) | Read in part: 44,976 dislocations (≥5 pp with one-sided flow, 2024–25). About $0.7–1.0M needed to move a market 5 pp and get cited. **Does not study post-dislocation price reversal** |
| Liu, Thomas, Baer & Donovan (2026), "Adapting Pairs Trading to Gambling Markets…" | arXiv 2609.22639v1 | F, B (Betfair) | Read in part: Betfair 2020 and 2024 election odds; an OU model on the summed implied probability; 130 out-of-sample signals, mean synthetic return 1.86%, "frictionless descriptive quantities rather than executable" |
| Gu, Kagan, Sun, Wu & Xu (2026), "When do prophets profit in prediction markets?" | arXiv 2607.06166v3 | Execution of forecast edges on CLOBs | Read in part: "proper betting" under spreads; a 26-day live Kalshi pilot (+24.2% trimmed ROI). Not microstructure |
| Wheatcroft, E. (2020), "Profiting from overreaction in soccer betting odds", *JQAS* | DOI 10.1515/jqas-2019-0009 | F (across matches, bookmakers) | Abstract only: odds over-react to runs of results; a claimed sustained profit across 20 leagues × 12 seasons |
| Kroer, Dudík, Lahaie & Balakrishnan (2016), "Arbitrage-Free Combinatorial Market Making via Integer Programming" | arXiv 1606.02825 | C (method) | Abstract read: Frank–Wolfe Bregman projection with an IP oracle; NCAA 2010 (2^63 outcomes). A method for computing arbitrage-free prices, not a prediction |
| Telonex (2026-02-22), "How Sponsored Liquidity Rewards Rewired Polymarket's Jesus Market" | telonex.io/research/… | D (rewards) | **Industry blog, lead only.** About $70k of sponsored rewards; top-of-book depth 23.5×; cost to move 1¢ 7.8–12.7×; active makers 302 → 639. Single market, 3-day post window, no LP PnL. Data-vendor author |
| Rothschild & Sethi (2016); Croxson & Reade (2014); Bartlett & O'Hara (2026); Angelini & De Angelis (2026) | | D, F | See sibling `sweep_informed-trading-following.md` |

## 7. Discrepancies with CONTEXT.md and other notes

1. **Maker rebate.** Zang et al. say makers "get no rebate" in their BTC 5-minute sample (date not given). CONTEXT.md
   says Crypto maker rebates are 20% of taker fees today. Possibly time-dependent. **Unresolved.**
2. **Reward formula.** Singh's thesis says rewards *increase* with the square of the distance from the mid. The
   official docs (VERIFIED today) give `S = ((v−s)/v)²·b`, which *decreases* with distance. The thesis is wrong on
   this point. CONTEXT.md and the sibling platform note agree with the docs.
3. **Data sources.**
   - Singh's thesis relies on Goldsky subgraphs, which CONTEXT.md marks as deprecated since V2.
   - Zhai & Shi and Moulinier (abstracts) cite full-depth or "full" Polymarket order-book archives. CONTEXT.md says
     there is no *official* historical book. These must be third-party (e.g. the PMXT archive named in
     `sweep_polymarket-empirical.md`). PLAUSIBLE, not verified.
4. **Fee assumption.** Young's 1% simulated fee is lower than today's Crypto taker fee at mid prices: 0.07 × 0.25 =
   1.75¢ per share at p = 0.5 (CONTEXT.md). That makes his negative result conservative.
5. **No contradiction with CONTEXT.md platform facts** was found in Xi et al. (Kalshi only), Tsang & Yang (2024 USDC
   era, pre-V2) or Portnaya (2023, pre-fees).

## 8. Search log

1. **Context:** read CONTEXT.md and all sibling notes in `notes/literature/`, plus `strategies/logical_arb.md` and
   `platform/fees_incentives.md`. I took their verified citations as covered and did not re-read them.
2. **arXiv API**, sorted by submission date:
   - Polymarket and Kalshi sets:
     - `all:polymarket` returned 62; I scanned all titles.
     - `all:kalshi` returned 26.
   - Market making and adverse selection:
     - `abs:"prediction market" AND abs:"market making"`: 12. Surfaced Feil & Nendel, Xi et al., Zang et al.,
       ParlayMarket and Brahma et al. 2010.
     - `abs:"prediction market" AND (abs:"adverse selection" OR abs:"informed trader" OR abs:spread)`: 12.
     - `abs:"liquidity rewards" OR "liquidity incentives" OR "liquidity mining"`: 8, none about Polymarket rewards.
     - `abs:"binary option" AND (market making/order book)`: 1, irrelevant.
   - Mean reversion and betting exchanges:
     - `abs:"prediction markets" AND (overreaction OR "mean reversion" OR reversal OR momentum)`: 8.
     - `abs:"betting exchange"`: 8. Surfaced Liu et al. 2026 and agent-based models.
   - Lead–lag:
     - `abs:"prediction market" AND ("lead-lag" OR "price discovery")`: 10.
     - `abs:"prediction market" AND (binance OR bitcoin) AND (latency OR minute)`: 1 (Dai et al.).
   - Near expiry and linked contracts:
     - `… AND (expiry OR expiration OR "time to resolution")`: 5.
     - `abs:predictit`: 1 (Sethi et al. 2021).
     - Combinatorial: `abs:"combinatorial prediction market" OR "combinatorial market maker" OR (prediction market AND
       logical)`: 16. Surfaced Kroer et al. and Chen et al. 2008.
     - `abs:"event contracts"`: 6.
     - `ti:"election arbitrage"`: 0.
   - Downloaded 13 arXiv PDFs and converted them with pdftotext.
3. **Crossref:**
   - Bibliographic searches: "Polymarket liquidity rewards market making" (no relevant hit); "Kalshi Polymarket price
     discovery cross-venue" (surfaced Adamczewski, Lee et al., Malék, Nechepurenko's series); "Polymarket bitcoin up or
     down"; "price discovery and trading in modern prediction markets" (Ng et al.); "Polymarket liquidity provision";
     "prediction market maker inventory adverse selection"; "Kalshi Polymarket arbitrage cross-platform" (Moulinier,
     Krause, Gupta, Stanisljevic); "combinatorial arbitrage linked contracts" (Zhai & Shi, Zitzewitz).
   - Pulled abstracts by DOI for every SSRN item cited.
   - Confirmed DOIs: Angelini 2022, Rothschild & Pennock 2014, Franck 2013, Stershic & Gujral 2020, Tetlock (SSRN
     929916), Page 2012, Choi & Hui 2014.
4. **OpenAlex:** the shared-IP daily budget was exhausted ("Rate limit exceeded"). Dead end today.
5. **WebSearch and WebFetch:**
   - **Ng et al.:** only the SSRN page and seminar abstracts; no PDF.
   - **Adamczewski:** no copy, OSF registration or repository found.
   - **Moulinier:** no copy or repository found. A Quantpedia summary surfaced the JPM 2020 paper and SSRN 5086104.
   - **Zhai & Shi:** no copy found.
   - **Lee et al.:** no preprint; it surfaced the Mohanty & Krishnamachari arXiv paper (not used) and a Charles Univ.
     thesis on Polymarket crypto convergence (dspace.cuni.cz timed out twice).
   - **Choi & Hui:** the AUT PDF returned a Cloudflare challenge; WebFetch got 403.
   - **Angelini et al. 2022:** the Reading eprints host gave a 502; CentAUR worked.
   - **Rothschild & Pennock:** researchdmr.com PDF worked.
   - **Tetlock:** the AEA staging link returned HTML; the Columbia-hosted SSRN PDF worked.
   - **Page 2012:** abstract via IDEAS; QUT eprints returned 403 to curl and 503 to WebFetch.
   - **Franck et al. 2013:** Univ. of Fribourg PDF worked.
   - **Stershic & Gujral:** ubplj.org PDF worked.
   - **Polymarket rewards study:** found only the Singh TUM thesis (read) and the Telonex blog (lead).
   - **"High-probability contracts near resolution Polymarket":** only market pages and blogs, no study. Expected
     but **not found**: any primary paper on returns to 95–99¢ Polymarket contracts by time to resolution. The closest
     evidence is Zang et al.'s boundary calibration, Page (abstract) and Dai et al. (sibling).
6. **Official documents:** fetched docs.polymarket.com/programs/liquidity-rewards.md today (formula, c = 3.0, minute
   sampling, the ended crypto TWAP pools).
7. **Repository and dataset checks:** the OpenMarket HF dataset returned HTTP 200; the GitHub repo returned 403 to this
   sandbox (not verified). I did not attach any repository.
8. **Not cited from memory.** Expected classics I did not read and therefore do not cite as evidence:
   - Gil & Levitt (2007), mentioned only via Croxson & Reade (sibling);
   - Erikson & Wlezien (2008) and Berg, Nelson & Rietz (2008) on polls (named only as Feil & Nendel's references);
   - Hardiman, Richmond & Hutzler (2010) on Betfair anti-persistence (named only as Liu et al.'s citation);
   - Snowberg, Wolfers & Zitzewitz on election-night lead–lag (not searched further).
