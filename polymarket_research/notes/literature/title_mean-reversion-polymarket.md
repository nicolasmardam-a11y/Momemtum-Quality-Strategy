# Reference check: "Exploiting Mean-Reversion in Decentralized Prediction Markets: Evidence from Polymarket Binary Contracts"

As of 2026-10-17. Status labels: **VERIFIED** (I read it in the primary source or checked it in data myself),
**PLAUSIBLE** (consistent with the evidence but not directly verified), **UNSUPPORTED**.

## Bottom line

1. **The exact title exists (VERIFIED).** It is a Quantpedia "own-research" piece, not a peer-reviewed paper.
   It appeared first as a Quantpedia blog post on **17 April 2026** credited to **Cyril Dujava**. It was then
   deposited on SSRN as a preprint, **DOI 10.2139/ssrn.6726362**, with authors **Radovan Vojtko and Cyril Dujava**
   (both Quantpedia, Bratislava). The Crossref record was created on 2026-05-06.
2. **What it is:** a backtest on **three hand-picked "No" contracts** that all resolved No:
   - Jesus returns in 2025
   - China invades Taiwan in 2025
   - US confirms aliens in 2025

   The rule is: buy at a new X-day low, hold Y days. It runs a 12-cell in-sample grid, with **no out-of-sample test,
   no significance test, and a cost model of 0 or 10 bps per side**.
3. **I reproduced it (VERIFIED, my own data work).**
   - **Data:** the authors' "internal API" data matches the public **CLOB `/prices-history` series at 10-minute
     fidelity**, which is a midpoint/trade series and not executable. Observation counts are identical for Jesus
     (41,218) and China (48,554).
   - **Results:** when entry happens one 10-minute bar after the signal, on the uncleaned series, the China tables
     reproduce to about 0.05 pp CAR, the Alien strategy tables to 0.5 pp or better, and Jesus to about 0.2 pp. The one
     exception is the Alien buy-and-hold CAR (8.63% reported vs 11.57% mine), which I cannot explain.
4. **Problems I found when reproducing it:**
   - **The China and Alien benchmark is distorted by one data point.** The buy-and-hold drawdowns (−24.29%, −21.94%)
     and volatilities (49%, 44%) equal exactly the effect of **one 10-minute print at 2025-12-27 01:10 UTC**, which was
     not buyable. The paper says such outliers were forward-filled, but its reported figures match the uncleaned series.
     So the "strategy Sharpe ≈ 2 vs benchmark ≈ 0.2–0.3" comparison is mostly an artefact.
   - **The "spread" measure is not a bid-ask spread.** It is the 4-hour high–low range of the price series.
   - **Real trading costs were about 5–6× the assumed 10 bps.** The China mid sat on a half-cent (x.xx5) value in 90%
     of bars below 0.96, which points to a 1-cent quoted spread. Taker fills were a median **0.57%** away from the
     prevailing mid. With 0.5% per side, most variants lose money, and all of them trail buy-and-hold.
5. **There is a real reversal effect, but it is small and was chosen with hindsight.** In-sample, entries at new lows
   beat random entries with the same holding period (placebo p < 0.03 in all 9 cases I tested). The effect is
   0.1–1.5% per trade before costs, which is about the size of one spread crossing. It was measured on three contracts
   chosen *because* they resolved No. **Nothing here shows an edge you could have identified in advance at
   executable prices.**

## 1. Existence and metadata

| Field | Value | Status |
|---|---|---|
| Exact title | Exploiting Mean-Reversion in Decentralized Prediction Markets: Evidence from Polymarket Binary Contracts | VERIFIED (blog HTML; Crossref; OpenAlex) |
| Authors | Blog: Cyril Dujava ("Quant Analyst, Quantpedia"). SSRN/Crossref: Radovan Vojtko (first), Cyril Dujava (corresponding per OpenAlex). Affiliation: Quantpedia, Dulovo namestie 14, Bratislava, Slovakia | VERIFIED (blog footer; Crossref 10.2139/ssrn.6726362; OpenAlex W7160440502) |
| First posted | Quantpedia blog dated "17.April 2026". Figure uploads sit in `/app/uploads/2026/03/`, so the work was drafted in March 2026 | VERIFIED |
| SSRN version | SSRN abstract 6726362; Crossref deposit/created 2026-05-06T18:32Z; type "posted-content / preprint"; abstract identical to the blog's first paragraph | VERIFIED (metadata). The SSRN page and PDF return 403 from this sandbox, so I could not compare the PDF with the blog or see the SSRN "date written" / revision dates |
| Latest version | Nothing later than the SSRN deposit was found. Crossref shows one DOI and no relations | PLAUSIBLE |
| Status | Practitioner research note / SSRN preprint. Not peer-reviewed, no journal or conference | VERIFIED (Crossref subtype "preprint"; OpenAlex is_published=false) |
| Primary URL | https://quantpedia.com/exploiting-mean-reversion-in-decentralized-prediction-markets-evidence-from-polymarket-binary-contracts/ | VERIFIED |
| Other URLs | https://doi.org/10.2139/ssrn.6726362 ; https://www.ssrn.com/abstract=6726362 ; https://quantpedia.com/?p=44922 | VERIFIED (the SSRN URL is the Crossref resource link, 403 here) |
| arXiv | None. Title, author and abstract-phrase searches returned 0 hits. The arXiv "Dujava" hits are unrelated physics papers | VERIFIED |
| Code / data repository | None linked. The blog says the data was "exported in flat CSV" by Quantpedia's dev team. No GitHub link found | VERIFIED (none in page) |

**Full text read:** yes, the complete Quantpedia blog HTML: Sections 1–6, Tables 1–9 and the reference list.
I could not read the SSRN PDF (403).

## 2. Content of the paper (from the blog full text; section and table numbers are the paper's)

- **Research question (Sec. 1):** the paper explicitly does *not* try to identify mispriced contracts. It asks
  whether, *conditional on already knowing a contract is undervalued*, "averaging-down (reversal)" entries add
  risk-adjusted return. This conditioning is the paper's own framing, and it builds hindsight into the test.
- **Mechanism (Sec. 1, 2.2):** prices temporarily move away from equilibrium because of "sentiment shocks, liquidity
  imbalances, or information asymmetry". Binary settlement gives the price an anchor. The paper does not test this
  mechanism.
- **Data (Sec. 3.1, Table 1):**
  - Source: 10-minute prices "obtained via Polymarket's internal APIs".
  - Jesus: 2025-03-20 → 2026-01-01, 41,218 observations.
  - China: 2025-01-29 → 2026-01-01, 48,554 observations.
  - Alien: 2024-12-31 → 2026-01-01, 52,597 observations.
  - Coverage: three markets, all "No" side, all "will X happen in 2025" contracts that resolved No.
    There is no category sample.
- **Preprocessing (Sec. 3.2):** "outliers ... toward the end of 2025 (November period)" were forward-filled.
- **Strategy (Sec. 3.3):**
  - Long when price ≤ X-day rolling minimum, hold exactly Y days, no overlapping positions, full reinvestment.
  - X ∈ {5,10,20}, Y ∈ {1,2,3,5}, giving 12 variants per contract.
  - The grid is evaluated in-sample, and the "optimal" parameters are picked from the same data.
- **Costs (Sec. 3.4):**
  - "Zero-spread" scenario = passive limit orders, treated as an upper bound.
  - 10 bps per trade (0.2% round trip), described as covering "aggressive market-order execution".
  - Spread "estimation" = 4-hour rolling (high − low)/low of the price series (Table 9).
- **Metrics (Sec. 3.5):**
  - CAR, annualised vol, Sharpe at a 0% risk-free rate (it is CAR/vol: 5.98/5.86 = 1.02), MaxDD, Calmar.
  - Idle cash earns 0%.
- **Key reported numbers:**
  - **B&H benchmark (Table 2):** Jesus +5.98% CAR, Sharpe 1.02, MDD −2.37%. China +12.69%, 0.26, −24.29%.
    Alien +8.63%, 0.20, −21.94%.
  - **Jesus at 0 cost (Table 3):** all 12 variants beat B&H on Sharpe. Best is X5_Y1 at +7.95% CAR, Sharpe 2.97.
  - **Jesus at 10 bps (Table 4):** only X20_Y5 is positive (+0.10%). X5_Y1 falls to −7.83%.
  - **China (Tables 5/6):** X5_Y1 +30.98% at 0 cost and −0.08% at 10 bps. X20_Y5 +22.57% (Sharpe 2.34) at 0 cost
    and +18.91% (Sharpe 1.96) at 10 bps.
  - **Alien (Tables 7/8):** X5_Y2 +33.33% at 0 cost. X10_Y5 +22.09% (Sharpe 1.23) at 10 bps.
  - **"Spread" percentiles (Table 9):** median 0.00% / 0.00% / 0.05%; 99.9th percentile 0.63% / 2.21% / 12.42%.
  - **Conclusions (Sec. 6):**
    - Results are extremely sensitive to costs.
    - X=20, Y=5 is "consistently" among the best.
    - Passive execution is "essential".
    - Diversify across "ideally up to 100" contracts.
- **Evidence type:** in-sample simulated trading on one historical path per contract. No live trading, no
  out-of-sample period, no standard errors.
- **Dependence:** not addressed. Each contract is analysed alone and nothing is pooled. Sharpe comes from serially
  dependent intraday returns.
- **Execution realism:** no order-book depth, queue position, partial fills, adverse selection, latency model or
  position size. No platform fees (correct for these 2025 markets, see below). Capital lock-up is not discussed
  beyond annualising returns.

## 3. Independent reproduction (my work, read-only public data)

Scripts:
- `analyses/literature_checks/quantpedia_mr_fetch.py` fetches Gamma metadata and CLOB `/prices-history`
  at fidelity=10. The endpoint refuses windows longer than about 15 days, so it fetches 14-day chunks.
- `quantpedia_mr_replicate.py` runs the rule as described.
- `quantpedia_mr_trades.py` fetches the Data API `/v2/trades` taker tape with wallet fields dropped.
- `quantpedia_mr_diagnostics.py` runs cost sensitivity, the drift control and the placebo.

Outputs are in `data/derived/literature_checks/` (`qp_mr_*.parquet`, `qp_mr_replication.csv`, `qp_mr_diagnostics.csv`).
Raw responses with fetch times are under `data/raw/` (pmr provenance).

### 3.1 Market facts (Gamma, VERIFIED 2026-10-17)

| Contract | Gamma market id | Start | Resolved | Gamma volume | `feesEnabled` | `holdingRewardsEnabled` | tick (final) |
|---|---|---|---|---|---|---|---|
| Jesus | 529315 | 2025-03-20 22:05Z | No (`outcomePrices` ["0","1"]) | $3.27M | false | false | 0.001 |
| China | 520630 | 2025-01-29 00:13Z | No | $12.36M | false | false | 0.001 |
| Alien | 516925 | 2024-12-31 18:51Z | No | $8.39M | false | false | 0.001 |

The start dates match Table 1 exactly. The "0 fees" assumption was correct for these 2025 markets (VERIFIED from the
Gamma field). Under today's schedule, a similar market with fees enabled would charge `rate × p(1−p)` per share.
At a 0.05 rate and p = 0.92 that is about 0.37 cents per share, or 0.4% of notional per taker fill. Geopolitics
markets are currently at rate 0. Which category these three markets would fall into today is not verified.

### 3.2 Data source identified (VERIFIED by count match; that the authors used this endpoint is PLAUSIBLE, very strong)

CLOB `/prices-history?fidelity=10` returns:
- **41,218** points for Jesus (paper 41,218).
- **48,554** for China (paper 48,554).
- 52,621 for Alien (paper 52,597, a difference consistent with a slightly earlier cut-off).

Per CONTEXT.md this series is a trade/mid series and not an executable bid/ask series.

### 3.3 Reproduction quality (VERIFIED)

The match uses vol computed from 10-minute returns × √(365·144), entry one bar after the signal, and the raw
series. Paper value, then my value:

| Item | Paper | Mine |
|---|---|---|
| China B&H CAR / vol / MDD | 12.69 / 49.19 / −24.29 | 12.65 / 49.21 / −24.29 |
| China X5_Y1, 0 cost | 30.98 / 19.64 / Sh 1.58 / −13.55 | 30.97 / 19.65 / 1.58 / −13.55 |
| China X20_Y5, 0 cost | 22.57 / 9.65 / 2.34 / −3.42 | 22.55 / 9.66 / 2.33 / −3.42 |
| China X20_Y5, 10 bps | 18.91 / 9.67 / 1.96 / −3.99 | 18.88 / 9.67 / 1.95 / −3.99 |
| China X5_Y1, 10 bps | −0.08 / 19.76 / −0.00 / −20.95 | −0.13 / 19.72 / −0.01 / −20.95 |
| Alien X5_Y2, 0 cost | 33.33 / 19.41 / 1.72 / −11.54 | 32.89 / 19.41 / 1.69 / −11.54 |
| Alien X10_Y5, 10 bps | 22.09 / 17.97 / 1.23 / −11.14 | 22.19 / 17.97 / 1.23 / −11.14 |
| Jesus B&H | 5.98 / 5.86 / 1.02 / −2.37 | 5.99 / 6.00 / 1.00 / −2.37 |
| Jesus X5_Y1, 0 cost / 10 bps | 7.95 / −7.83 | 8.11 / −7.73 |

Remaining mismatches:
- **Alien B&H CAR:** the paper has 8.63% and I get 11.57%. Their Alien vol and MDD match mine, so only their B&H
  entry price differs. The cause is unexplained.
- **Jesus vol:** small differences, probably small data-snapshot differences.

Executing on the signal bar itself (no lag) gives much higher China returns (X5_Y1 about 41% on cleaned data),
so the paper's one-bar lag is the more conservative choice. That is to its credit.

### 3.4 Problems that only show up in the data (VERIFIED unless noted)

1. **The benchmark comes from one non-executable print.**
   - The China No series reads 0.9985 → **0.756** → 0.9985, and Alien reads → **0.779** →, both at
     **2025-12-27 01:10 UTC**.
   - That one bar alone produces the paper's B&H MDD (−24.29%, −21.94%). It also inflates the B&H vol 1.6–1.9×:
     forward-filling the bar cuts China vol from 49.2% to 25.8% and Alien from 44.4% to 27.2%.
   - The public taker tape shows a real flash dislocation at that moment:
     - 01:07:37: someone sold 2,512.91 No at **0.0109**.
     - 01:10:39: a sale of 31 No at 0.525.
   - But every taker *buy* of China No between 01:09 and 01:13 printed at **0.986–0.990**. A buyer could not get 0.756.
   - So the paper's statement that outliers were forward-filled (Sec. 3.2) is inconsistent with its own Table 2
     numbers. The strategy-versus-benchmark Sharpe gap for China and Alien is inflated by this artefact. The strategy
     is out of the market on that day and gets almost nothing from the spike, because it enters one bar later at about 0.9985.
2. **Table 9 "spread" is not a spread.** (high−low)/low of a 4-hour window of a 10-minute mid series measures price
   movement, not the quoted bid-ask spread. A 0.00% median means the mid did not move, not that trading was free.
   The paper's claim that Table 9 "validate[s] our 10 bps friction assumption" does not follow (VERIFIED from the
   method description).
3. **Real crossing cost is about 5–6× the assumption.**
   - When the China mid was below 0.96, **90.1%** of 10-minute values ended in x.xx5. That is the signature of a
     1-cent-tick book with a 1-cent spread (PLAUSIBLE inference). Above 0.96 the tick was 0.001.
   - Taker trades on the No leg (Yes trades converted to No terms) sat a **median 0.565%** (notional-weighted
     0.86%) away from the prevailing 10-minute value when China was below 0.96. That covers 8,095 trades, and 98%
     were ≥ 0.5 cents away.
   - Alien below 0.96: median 0.05%, notional-weighted 0.67% (mixed tick regimes).
   - Jesus (above 0.96): median 0.05%, notional-weighted 0.18%.
   - These are noisy, because the "mid" can be up to 10 minutes stale (PLAUSIBLE magnitude).
4. **Cost sensitivity** (cleaned series, one-bar lag; CAR %, Sharpe in brackets):

   | Contract, variant | 0 | 0.1%/side | 0.25%/side | 0.5%/side | 0.6%/side |
   |---|---|---|---|---|---|
   | Jesus X20_Y5 | 2.11 (0.77) | 0.30 | −2.36 | −6.64 | −8.30 |
   | China X5_Y1 | 31.33 (1.59) | 0.14 | −33.35 | −66.23 | −74.29 |
   | China X10_Y5 | 23.16 (1.66) | 16.66 | 7.54 | −6.14 | −11.12 |
   | China X20_Y5 | 22.48 (2.36) | 19.07 | 14.14 | **6.34 (0.64)** | 3.37 |
   | Alien X10_Y5 | 27.68 (1.54) | 21.70 | 13.23 | 0.38 | −4.35 |
   | Alien X20_Y5 | 18.79 (2.36) | 15.51 | 10.75 | 3.24 | 0.37 |

   At about 0.5% per side, which is close to the measured China taker cost, no variant beats simple buy-and-hold
   (China B&H 12.65%, Alien 11.57%). Buy-and-hold is itself only known to be profitable in hindsight.
5. **The reversal is real in-sample, but small.**
   - Mean signal-trade return is 0.10–1.46% before costs. The unconditional Y-day drift is 0.01–0.20%.
   - Against 500 random-entry placebos with the same number of non-overlapping Y-day trades, the share of placebos
     doing at least as well as the strategy is 0.000–0.030 across the 9 contract/parameter cases. So buying new lows
     did beat random timing on these three paths.
   - **The P&L is concentrated.** For China X20_Y5 (13 trades), removing the best 3 trades cuts the total return from
     20.6% to 6.9%.
   - The best trade, entered at the mid of 0.825 on 2025-04-07 09:50, was not executable at that mid. Taker buys printed
     at 0.84 at 09:41 and 09:56, which cuts that trade from +4.85% to about +3.0%.
6. **Hindsight selection (the decisive flaw, VERIFIED from Sec. 1 and Gamma outcomes).**
   - All three contracts were picked as "No" positions that resolved No, and the No price drifted from about 0.90 up
     to 0.999.
   - Buying dips in a security known to converge to $1 must make money in a backtest.
   - The authors state the conditioning openly ("conditional on identifying a contract that appears undervalued").
     A reader citing this as evidence of a *tradable* mean-reversion edge on Polymarket is therefore over-reading it.
   - Any contract that resolved Yes, such as a "nothing-happens" No that failed, would make dip-buying lose the
     whole stake.
7. **Correlated observations (VERIFIED for the shared timestamp, PLAUSIBLE for the common driver).**
   - The three series are not independent. All are year-end-2025 "nothing happens" No contracts, and China and Alien
     dislocated at the very same minute on 2025-12-27, which suggests a platform-wide liquidity event.
   - The effective sample is one regime and a few dozen independent trades.

### 3.5 Errors inside the paper (VERIFIED)

- **Sec. 6.2:** "Across all three contracts and both friction scenarios, strategies with X=20 and Y=5 consistently
  rank among the top performers on risk-adjusted metrics." In the paper's own Table 3 (Jesus, 0 cost), X20_Y5 is
  **11th of 12** by Sharpe (+0.68).
- **Sec. 5.6:** "2.6x improvement over buy-and-hold on a risk-adjusted basis" for Alien X10_Y5. 2.6× is the
  **CAR** ratio (22.09/8.52). The Sharpe ratio is about 6.5× (1.23/0.19).
- **Sec. 3.5:** says vol is the "standard deviation of daily returns". The reported B&H vol reproduces only with
  10-minute returns annualised by √(365·144). Daily returns give 2.7% (Jesus) and 12.0% (China), not 5.86% and 49.19%.
- **Sec. 5.3:** calls Y a "threshold". Y is the holding period.
- **Reference list:** gives the Clinton & Huang DOI as 10.31219/osf.io/d5yx2_v1, which returns 404 at doi.org and
  Crossref. The working DOI is **10.31235/osf.io/d5yx2_v1** (SocArXiv).
- **Intro:** attributes "over $2.4 billion in transaction volume" to Polymarket alone. Clinton & Huang's title and
  abstract describe more than $2 billion across *four* venues (IEM, Kalshi, PredictIt, Polymarket) in the final five
  weeks of the campaign (PLAUSIBLE misattribution; I read the abstract only).
- The Cordoba Otalora & Themistocleous reference (Future Internet 17(11):487, 2025, DOI 10.3390/fi17110487) resolves
  and matches (VERIFIED via Crossref).

## 4. Corrections to the reference as cited

- The title is exact and the work exists. It should be cited as **Vojtko, R. & Dujava, C. (2026), SSRN 6726362 /
  Quantpedia blog, 17 Apr 2026**, a practitioner preprint and not an academic journal article. The blog version
  credits Dujava alone.
- It studies **3 contracts**, not "Polymarket binary contracts" in general.
- Its own conclusion is that performance "degrades significantly" with aggressive execution. Citing it as evidence of
  a robust after-cost edge would misstate it.
- I do not know exactly what the earlier discussion claimed beyond the title. Any claim of an executable,
  prospectively identifiable mean-reversion edge is **UNSUPPORTED** by this source.

## 5. Later versions, comments, critiques

- No later version, published version, comment, replication or critique found. Searched: Crossref, OpenAlex
  (until its shared daily budget ran out), arXiv, web search, and Quantpedia's polymarket and prediction-markets tags.
- Two other Quantpedia posts, "Systematic Edges in Prediction Markets" (2025-11-27) and "How Wise is the Crowd in
  Prediction Markets" (2026-06-05), do not cite this piece (WebFetch summary).
- Crossref shows Vojtko & Dujava regularly post Quantpedia blog studies to SSRN (several 2026 SSRN DOIs), so the
  SSRN deposit is their normal practice and not a refereed upgrade.

## 6. What must be replicated before risking money (strategy family F, mean reversion)

1. **An unselected universe.** Every binary market meeting ex-ante filters (category, horizon, price band,
   liquidity), including markets that resolved against the position, with selection timestamped before entry.
2. **Executable prices.** Model a taker entry at the ask and exit at the bid, using order-book snapshots or the trade
   tape. Historical books are not available from Polymarket, so this needs forward collection or tape-based
   effective-spread models. Never use the `/prices-history` mid.
3. **A maker variant.** The paper's "passive" case needs a fill model: queue position, the share of resting bids at
   the low that actually fill, and markouts after fills, which capture adverse selection when someone dumps on news.
   The 2025-04-07 dip was a real 4.5k-share Yes buy, i.e. possibly informed flow.
4. **Out-of-sample discipline.** Fix X and Y on one period, then test on later markets. Report the number of
   independent trades, cluster by event and date, and correct for the 12 × contracts × cost-scenario grid.
5. **Data hygiene.** Detect one-bar prints and check them against the tape before using them in a benchmark or a
   signal.
6. **Current fees and incentives.** Apply today's taker fees (`rate × p(1−p)`) and maker rebates and liquidity
   rewards where `feesEnabled`, and account for capital lock-up (idle pUSD earns nothing).
7. **Tail risk.** A contract that resolves against you loses about 100% of the position. The "diversify across up to
   100 contracts" advice needs an explicit loss-given-wrong model, plus correlation across "nothing happens" contracts.

## 7. Related real papers surfaced by the search (leads only, abstract-level)

- **Clinton, J.D. & Huang, T. (2025)**, "Prediction Markets? The Accuracy and Efficiency of $2.4 Billion in the 2024
  Presidential Election", SocArXiv, DOI 10.31235/osf.io/d5yx2_v1 (IDEAS date 2025-02-02; Crossref record
  2025-12-01).
  - The abstract says "daily price changes were weakly correlated or negatively autocorrelated". This is the only
    empirical mean-reversion evidence the Quantpedia piece cites.
  - Abstract only; the OSF API returned 503.
- **Tsang, K.P. & Yang, Z.**, "Political Shocks and Price Discovery in Prediction Markets: Evidence from the 2024 U.S.
  Presidential Election", arXiv 2603.03152 (v1 2026-03-03, v4 2026-07-18).
  - The abstract says the debate-driven price increase "largely reverses" while the assassination-attempt repricing
    persists. Event-level evidence; abstract only.
- **Qin, B. & Yang, R.**, "Polymarket-v1 Database", arXiv 2606.04217 (v1 2026-06-02, v2 2026-06-08).
  - The abstract reports *positive* trade-direction autocorrelation that "violate[s] the mean-reversion assumption"
    of tick-rule classifiers. This concerns order flow, not price reversal. Abstract only.
- **Sultan, O. & Morstatter, F.**, "The Conversation Turns First: Crowd Discussion and Price Reversals in Prediction
  Markets", arXiv 2609.28965 (2026-09-24, cs.SI).
  - "Reversals" here means changes in the leading outcome, across 79 non-political Polymarket markets. It is not a
    trading backtest. Abstract only.

## Search log

- **arXiv API:**
  - Searches with 0 hits: `ti:"Exploiting Mean-Reversion"`, `ti:exploiting AND ti:reversion AND ti:prediction`,
    `au:Vojtko`, `abs:"Will Jesus Christ return"`.
  - `au:Dujava` returned 4 unrelated physics/IE papers.
  - `all:"mean reversion" AND all:"prediction market"` returned only 2606.04217.
  - `all:reversal AND all:"prediction market"` returned 8 hits, including 2609.28965 and 2603.03152.
  - `all:overreaction`, `all:momentum AND all:polymarket` and `all:"binary contracts" AND all:polymarket` returned
    nothing relevant.
  - `all:"decentralized prediction markets"` returned 10 hits, none on mean reversion.
  - `all:polymarket` (200 most recent) returned about 63 titles; I scanned them all and none matched.
- **WebSearch:** the exact title in quotes returned the Quantpedia pages (the post, `?p=44922`, tag pages, blog
  page 4). Other queries: "mean reversion Polymarket binary contracts paper"; "Cyril Dujava Polymarket mean reversion
  SSRN"; "ssrn 6726362 Vojtko Dujava" (no SSRN snippet); "Vojtko Dujava 2026 prediction markets Polymarket paper"
  (nothing); a Jesus/aliens/Taiwan rolling-minimum query (Quantpedia only, no critiques).
- **Crossref:**
  - `query.bibliographic=<title>` returned **10.2139/ssrn.6726362** (Vojtko, Dujava; created 2026-05-06).
  - `query.author=Dujava Vojtko` returned other Quantpedia SSRN deposits.
  - I also checked the cited DOIs (10.31219/... → 404; 10.31235/... → OK; 10.3390/fi17110487 → OK).
- **OpenAlex:**
  - `works/doi:10.2139/ssrn.6726362` gave W7160440502 with authors, affiliations and is_published=false.
  - Title and author searches then failed: the first had a malformed filter, and later calls hit the shared-IP daily
    budget ("Rate limit exceeded").
- **SSRN:** `papers.ssrn.com/sol3/papers.cfm?abstract_id=6726362`, `www.ssrn.com/abstract=6726362` and
  `Delivery.cfm` all returned **403** (WebFetch and curl).
- **IDEAS/RePEc:** the htsearch for the title returned nothing. The Clinton & Huang page was read for metadata and
  abstract.
- **OSF API** (`api.osf.io/v2/preprints/d5yx2_v1`): 503.
- **Quantpedia:**
  - The full blog HTML was read via curl. The WordPress REST API returned 403.
  - The polymarket tag lists 3 posts.
  - "Systematic Edges in Prediction Markets" and "How Wise is the Crowd in Prediction Markets" were summarised via
    WebFetch; neither cites this piece.
- **Data checks:** Gamma `/events/keyset?slug=…&closed=true`, CLOB `/prices-history` (fidelity 10, 14-day chunks;
  windows over about 15 days are rejected with "interval is too long"), and Data API `/v2/trades?condition=…`
  (taker tape: Jesus 10,706; China 28,850; Alien 36,597 rows).
