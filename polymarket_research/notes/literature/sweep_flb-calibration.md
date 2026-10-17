# Literature sweep: favorite–longshot bias (FLB) and calibration across betting and prediction markets

As of 2026-10-17. Author: research agent (literature sweep). Labels: **VERIFIED** = I read it in the primary source
myself; **PLAUSIBLE** = consistent with the evidence but not directly checked; **UNSUPPORTED** = no evidence found.
"Sibling note" = another file in this folder; I say when I rely on one instead of my own reading.

Scope: FLB and calibration evidence that could transfer to Polymarket. That means classic racetrack and betting
theory, Intrade, IEM, PredictIt, Betfair, Kalshi and Polymarket. Four questions throughout:

1. Does the bias survive fees and spreads?
2. Does it vary with time to expiry?
3. Does it vary with liquidity and category?
4. Who earns it, makers or takers?

Related notes: Polymarket-specific papers are covered in depth in `title_flb-polymarket.md` (Cardozo &
Rivero-Wildemauwe), `title_who-wins-who-loses.md` (Akey et al.) and `sweep_polymarket-empirical.md`. I re-checked the
Cardozo & Rivero-Wildemauwe tables I cite below against the arXiv PDF myself.

---

## 1. Bottom line

1. **The FLB is not universal.** It depends on market design.

   | Venue | Finding |
   |---|---|
   | Racetracks and bookmakers | Strong FLB |
   | Intrade long-horizon political markets | Strong FLB |
   | PredictIt 2016–22 | Strong FLB |
   | Kalshi | Present, mostly in the tails |
   | Betfair pre-play soccer | Absent (VERIFIED, Whelan 2025, Table 2) |
   | IEM | Absent, even reversed (VERIFIED, Berg & Rietz 2019) |
   | PredictIt after the 2025 relaunch | Absent (VERIFIED, Zitzewitz 2026, Table 11) |
   | Polymarket | Small, and its sign depends on how contracts are grouped |

   Where the FLB is large, a binding friction usually explains it:
   - track take (Snowberg & Wolfers; Ottaviani & Sørensen §8);
   - position limits plus a profit fee (PredictIt);
   - no interest paid on long-dated collateral (Page & Clemen);
   - bookmaker market power (Shin).

   Where arbitrage is cheap, the bias is small:
   - IEM had $1 complete slates and no fees;
   - Betfair charges a low commission and has no position limits.

   Polymarket has split/merge at $1 and no position limits, so the large historical FLB magnitudes should not be
   expected there. This last point is PLAUSIBLE: it is my inference from the cross-venue pattern.

2. **On the venue most like Polymarket (a CLOB with p(1−p) taker fees, i.e. Kalshi), the FLB is real, but most of the
   money moves through the spread, not through mispriced longshots.**
   - Becker's SSRN abstract attributes about three-quarters of taker losses to "execution within price-direction
     cells". Selection across price levels, "the longshot bias proper, contributes essentially nothing" (VERIFIED,
     Crossref abstract of SSRN 7217640).
   - Bürgi, Deng & Whelan: Kalshi takers average −31.46% and makers −11.99% per contract-observation, both including
     fees (VERIFIED, §5).

3. **Survival after fees and spreads.**
   - **Buying longshots never survives.** They lose before fees on every venue that has an FLB, and fees make it worse.
   - **Buying favorites as a taker usually does not survive.** On Polymarket, equal-child-market returns on favorites
     (p ≥ 0.90) are **+0.277% before fees** for all buyers (VERIFIED, Cardozo & R-W Table 6A). They are **−0.46% before
     fees for buyers who accept a seller's offer** (Table 9B/16A).
   - **My calculation, from the CONTEXT.md fee formula.** The current taker fee as a share of cost is rate × (1−p):
     - at p = 0.95: 0.35% (Crypto), 0.25% (Sports), 0.20% (Politics);
     - at p = 0.90: 0.70%, 0.50% and 0.40%.
   - A one-cent spread adds about 0.53% to a 0.95 purchase if you cross half of it.
   - **Taker favorite-buying therefore needs a pre-fee edge of roughly 0.6–1.2% per dollar.** No published Polymarket
     estimate reaches that level robustly (PLAUSIBLE).
   - **Maker-side favorite buying is the only version with positive pre-fee evidence:**
     - Polymarket: +0.641% [0.607, 0.675] equal-child, Cardozo & R-W Table 16A;
     - Kalshi: +1.9% after commission for makers buying at ≥ 50¢, with a 33% SD (Bürgi et al. §5–6).
   - Betfair points to a different lesson.
     - In pre-play soccer, Makers' best returns come when they *lay* strong favorites, i.e. hold the longshot side
       against takers who back favorites (Whelan Fig. 15, §7.1).
     - So on an unbiased exchange the edge is "be the maker", whichever side you take, not "buy favorites".
   - These maker returns are measured on filled orders only. Every author who discusses it flags adverse selection and
     fill risk (Whelan §8; Becker "Limitations").

4. **Time to expiry matters, in two different ways.**
   - **Long horizons (weeks to months): longshots are overpriced.**
     - Intrade: the FLB is much stronger beyond 100 days (VERIFIED, Page & Clemen §4.2.4, Table 2).
     - Kalshi: calibration slopes rise at 1w–1mo+ in Politics and Sports (VERIFIED, Le Table 4). Le reports the same
       pattern on Polymarket (§5, Fig. 2).
     - Page & Clemen's mechanism is that **collateral earns nothing**, so favorite buyers stay away. In their
       out-of-sample test the profit disappears at a 15–25% discount rate.
     - PredictIt is the exception: the bias did *not* shrink as elections approached (VERIFIED, Zitzewitz Table 8).
   - **The last minutes of in-play sports: longshots are overpriced again.** Three sources agree:
     - Page (2012) on Intrade; abstract only.
     - Betfair: by 105 minutes, takers in the bottom probability decile lose about 70%, makers on longshots almost as
       much, and takers backing strong favorites earn "small but statistically significant" profits (VERIFIED,
       Whelan 2025 §7.3).
     - Kalshi, last 10 minutes: contracts at 10–40¢ "resolve favorably almost never" (VERIFIED, Moshrefi 2026 §IV).
       That study does no game-level clustering.
   - **Weather is the opposite.** On Polymarket, *favorites* are overpriced 1–12 h before the daily peak (VERIFIED,
     Qiu & Qiu Table III), and Kalshi short-horizon weather slopes are below 1 (Le Table 4).
   - **Near-resolution behaviour is category-specific.** It cannot be assumed from the classic FLB.

5. **Liquidity has an inconsistent effect.**

   | Study | Venue | Effect of volume or liquidity |
   |---|---|---|
   | Bürgi et al., Table 6 | Kalshi | Only the lowest-volume quintile is worse |
   | Page & Clemen, Table 2 col. 4 | Intrade | No effect |
   | Kagan & Baiocchi (abstract only) | Kalshi | Calibration improves with more volume and traders |
   | Zitzewitz §IV | PredictIt | Mispricing is **worse** in high-volume markets, because capped arbitrageurs are swamped |
   | Becker | Kalshi | The maker–taker transfer appeared only after volume brought in professional makers |
   | Whelan, Figures 16–17 | Betfair | Wider spreads mean bigger taker *and* maker losses on longshots |

6. **Category matters more than the aggregate.**
   - **Politics shows the most FLB-like compression in every venue that reports it:**
     - Intrade: Page & Clemen Fig. 5;
     - PredictIt: elections 1.946, investigations 1.912 (Zitzewitz Table 7);
     - Kalshi: politics ECE 0.117, about 5–15× other domains (Le Table 6). Political underconfidence replicates on
       Polymarket, with a mean slope of 1.45.
     - The exception is Kalshi politics in Bürgi et al. (ψ = 0.022, not significant; Table 8).
   - **Finance is nearly efficient on Kalshi:** the maker–taker gap is 0.17 pp (Becker).
   - **Sports favorites on Polymarket earn −0.230% (equal child)**, a reverse FLB (Cardozo & R-W Table 8, from the
     sibling note).

7. **Makers earn more than takers on every venue with role data:**
   - Kalshi: Bürgi et al.; Becker.
   - Betfair: Whelan; pre-play takers −2.5%, makers +0.6%.
   - Polymarket: Cardozo & R-W Table 16; Akey et al.
   - Intrade: Rothschild & Sethi's arbitrageurs and market makers.
   - The gap is largest for cheap contracts.
   - The maker premium is mostly **spread capture plus accommodation of YES-tilted taker flow**, not forecasting skill
     (Becker).

8. **No paper here shows a prospectively tradable FLB strategy at executable prices after current Polymarket fees.**
   The closest are:
   - Page & Clemen's out-of-sample Intrade split, which ignores fees and spreads;
   - Zitzewitz's PredictIt–Betfair cross-venue arbitrage, in a regime that no longer exists;
   - Qiu & Qiu's one-month Polymarket weather test (184 trades), which uses mean taker prices and ignores the order book.

   For this project:
   - family E (favorite–longshot) is at best a **maker-side, category-specific** hypothesis;
   - family H (near resolution) needs separate tests for **sports in-play** (fade late longshots) and **weather**
     (fade late favorites).
   - Both must be clustered by event and run on executable books.

---

## 2. Reference verification for the classic citations

| As supplied | Exact reference | Exists? | How I read it |
|---|---|---|---|
| Thaler & Ziemba 1988 | Thaler, R. H. & Ziemba, W. T., "Anomalies: Parimutuel Betting Markets: Racetracks and Lotteries", *Journal of Economic Perspectives* 2(2), 161–174, Spring 1988. DOI 10.1257/jep.2.2.161. Reprinted in *Efficiency of Racetrack Betting Markets* (World Scientific, 2008), pp. 255–268 | **Exact** (Crossref; AEA landing page) | **Full text not accessible.** AEA PDF returned 403 (Cloudflare), with no Wayback copy. Content taken from Ziemba's own 2020 revisit (SRC DP 103; published as *Annual Review of Financial Economics* 15:641–662, 2023, DOI 10.1146/annurev-financial-053122-021925), which I read, and from citing papers |
| Snowberg & Wolfers 2010 | Snowberg, E. & Wolfers, J., "Explaining the Favorite–Long Shot Bias: Is it Risk-Love or Misperceptions?", *Journal of Political Economy* 118(4), 723–746, Aug 2010. DOI 10.1086/655844. NBER WP 15923 (Apr 2010) is titled "…Favorite-Longshot Bias…" | **Exact**, but note the hyphenation: JPE uses "Favorite–Long Shot" | NBER WP full text read |
| Ottaviani & Sørensen | Ambiguous. (a) "The Favorite-Longshot Bias: An Overview of the Main Explanations", in Hausch & Ziemba (eds.), *Handbook of Sports and Lottery Markets*, Elsevier 2008, ch. 6, pp. 83–101, DOI 10.1016/B978-044450744-0.50009-3. (b) "Noise, Information, and the Favorite-Longshot Bias in Parimutuel Predictions", *AEJ: Microeconomics* 2(1), 58–85, Feb 2010, DOI 10.1257/mic.2.1.58 | Both exist (Crossref) | (a) full chapter read from a Bocconi-hosted PDF. (b) metadata only (AEA 403) |
| Shin's insider model | Shin, H. S. (1991), "Optimal Betting Odds Against Insider Traders", *Economic Journal* 101(408), 1179–1185, DOI 10.2307/2234434. Shin (1992), "Prices of State Contingent Claims with Insider Traders, and the Favourite-Longshot Bias", *EJ* 102(411), 426–435, DOI 10.2307/2234526. Shin (1993), "Measuring the Incidence of Insider Trading in a Market for State-Contingent Claims", *EJ* 103(420), 1141–1153, DOI 10.2307/2234240 | All three exist (Crossref; RePEc) | Abstracts only (RePEc); JSTOR is not accessible. The model is read via Ottaviani & Sørensen (2008) §7 |
| Page & Clemen 2013 | Page, L. & Clemen, R. T., "Do Prediction Markets Produce Well-Calibrated Probability Forecasts?", *Economic Journal* 123(568), 491–513, May 2013 (online 2012-12-17). DOI 10.1111/j.1468-0297.2012.02561.x | **Exact** | Full text read (author copy at Duke) |
| Rothschild & Sethi 2016 | Rothschild, D. M. & Sethi, R., "Trading Strategies and Market Microstructure: Evidence from a Prediction Market", *Journal of Prediction Markets* 10(1), 1–29, 2016. DOI 10.5750/jpm.v10i1.1179. SSRN 2322420 (2013 version) | **Exact** | Full text read (author WP dated 2015-11-22). Note: it is **not a calibration/FLB paper** |
| "2024–2026 working paper on Kalshi maker/taker returns" | (1) Bürgi, C., Deng, W. & Whelan, K., "Makers and Takers: The Economics of the Kalshi Prediction Market". Versions: CESifo WP 12122 (original Sept 2025, this version Jan 2026); SSRN 5502658; UCD WP 25/19; CEPR DP 20631; GWU Forecasting WP 2026-001. (2) Becker, J., "The Microstructure of Wealth Transfer in Prediction Markets", web paper 2026-01-18, SSRN 7217640 (Crossref record 2026-08-10) | Both exist | (1) CESifo PDF read in full. (2) web version read in full; SSRN abstract via Crossref |

---

## 3. Papers (ranked by usefulness to this project)

### 3.1 Bürgi, Deng & Whelan — "Makers and Takers: The Economics of the Kalshi Prediction Market" (core)

- **Metadata:** Constantin Bürgi, Wanying Deng, Karl Whelan (University College Dublin). CESifo Working Paper 12122:
  original version September 2025, this version January 2026.
  - https://www.ifo.de/DocDL/cesifo1_wp12122.pdf
  - SSRN 5502658; CEPR DP 20631.
  - No journal acceptance found (search 2026-10-17).
  - VERIFIED: CESifo PDF cover; Crossref.
- **Read:** full text (49 pp.; figures as images).
- **Mechanism (§4):**
  - Makers post offers to earn a required subjective return γ, net of a fee θp(1−p), but are slightly over-optimistic
    (δ).
  - Takers accept. Under the model, Taker loss rates rise steeply as price falls, and the fee bites hardest on cheap
    contracts.
  - The calibration that fits the data is γ ≈ 0.04, δ ≈ 0.005.
- **Data (§3.1):**
  - Kalshi API transaction data, 2021 to April 2025.
  - Filters: contracts with ≥ $1,000 total volume; final spread ≤ 20¢; markets open ≥ 24 h (hourly crypto/index
    markets excluded).
  - 12,403 events and 46,282 Yes contracts.
  - The last trade of each day, up to 10 days before close: 156,986 Yes prices, or 313,972 Yes+No prices.
  - Two-thirds of prices are < 10¢ or > 90¢ (Table 2).
  - Median contract volume is $8,982; mean trade $100, median trade $35.
- **Evidence type:** descriptive and in-sample (Mincer–Zarnowitz regressions plus a calibrated model). No trading
  simulation.
- **Costs:**
  - Post-fee return = (y − p − c)/(p + c), where c is the fee for 100 contracts rounded up (§3.3).
  - **The paper assumes both Maker and Taker pay 0.07p(1−p)** (§2.2, §2.3).
  - **Possible error (PLAUSIBLE):** the Kalshi public API on 2026-10-17 lists 14,992 of 15,187 series with
    `fee_type = "quadratic"` and only 159 with `"quadratic_with_maker_fees"` (VERIFIED, my API query). That suggests
    most markets charge makers nothing.
  - If so, Maker post-fee returns are understated. The API shows today's schedule, not the 2021–25 one.
  - Spreads are not modelled separately, because prices are actual trade prices.
- **Dependence:** standard errors are clustered by event and by Yes contract. Regressions use Yes contracts only, to
  avoid double counting the No side (§3.4).
- **Key findings (VERIFIED):**
  - Contracts < 10¢ lose over 60%; contracts > 70¢ have small, significant positive post-fee returns (§3.3, Fig. 5).
  - Average return is −20% pre-fee and −22% post-fee. These are equal-weighted per price observation and dominated by
    cheap contracts.
  - MZ rejects unbiasedness in every subsample (Tables 4–9). Price slope ψ:
    - **volume quintiles:** Q1 0.045, Q5 0.032; only the lowest quintile stands out (Table 6);
    - **trade-size quintiles:** the largest-trade quintile has the *largest* ψ, 0.043 (Table 7);
    - **categories:** Crypto 0.058, Financials 0.032, Climate/Weather 0.031; Politics 0.022 and Entertainment 0.020
      are not significant (Table 8);
    - **2025:** 0.021*, weaker than earlier years (Table 9).
  - MAE falls as close approaches, with a sharp drop on the last day (Fig. 4). The FLB persists at every horizon from 0
    to 10 days (Table 5).
  - **Makers vs Takers (§5):**
    - average post-fee return: Makers −11.99%, Takers −31.46%;
    - Makers buying at ≥ 50¢: +2.6% pre-commission, +1.9% post, SD 33% (§6.2);
    - Makers are 43.5% of buyers at 1–10¢ and 56.5% at 90–99¢ (Table 10);
    - Makers also lose on ≤ 10¢ contracts, especially on the closing day ("Yogi Berra"-like; Figs. 12–13).
- **Prospectively tradable?**
  - Price buckets are known ex ante, but the sample takes one last-trade per contract-day. It is not volume-weighted and
    not a strategy.
  - Maker returns are conditional on fills.
  - Assessment: **not shown to be tradable.** The "+1.9% for makers on ≥ 50¢" figure is the only candidate, and it
    has huge variance and unknown fill rates.
- **Replication needs:**
  - Kalshi trade-level data with the taker side (public API).
  - The fee schedule by series and date.
  - Order-book snapshots to measure maker fill probability.
  - Re-weighting by dollars and by event.

### 3.2 Becker — "The Microstructure of Wealth Transfer in Prediction Markets" (core)

- **Metadata:** Jonathan Becker.
  - Web paper dated 2026-01-18: https://jbecker.dev/research/prediction-market-microstructure
  - Formal version: SSRN 7217640 (DOI 10.2139/ssrn.7217640; Crossref record created 2026-08-10).
  - Dataset and code: https://github.com/Jon-Becker/prediction-market-analysis (MIT; about 36 GiB compressed
    Kalshi+Polymarket parquet; repo existence VERIFIED via WebFetch).
  - Status: unrefereed. The author is a software developer, not an academic economist (PLAUSIBLE, from the site).
- **Read:** the web version in full (VERIFIED). The SSRN version: abstract only (Crossref).
- **Mechanism:**
  - Takers pay an "optimism tax": they prefer affirmative YES contracts, especially at longshot prices.
  - Makers accommodate that flow and capture the spread.
  - The SSRN abstract adds an exact decomposition: about 3/4 of taker losses come from execution within price-direction
    cells, the rest from directional tilt, and "the longshot bias proper contributes essentially nothing".
- **Data:**
  - Kalshi, June 2021 to 2025-11-25.
  - 72.1M trades, $18.26B, 7.68M markets.
  - Resolved markets only; markets with < $100 notional dropped.
  - Volume shares: Sports 72%, Politics 13%, Crypto 5%.
- **Evidence type:** descriptive, in-sample.
- **Costs:**
  - Returns are **gross of fees**: r = (100·o − p)/p.
  - Spreads cannot be observed historically; the author says so under Limitations.
- **Dependence:** **not addressed.** CIs are trade-level, so for example ±0.01 pp on the role means are far too narrow.
  There is no event clustering.
- **Key findings (VERIFIED, web text):**
  - **Calibration:** 5¢ contracts win 4.18% (mispricing −16.36%); 95¢ contracts win 95.83%. Every bucket < 20¢
    underperforms and every bucket > 80¢ outperforms.
  - **Role means:**
    - takers −1.12% [−1.13, −1.11], makers +1.12%;
    - at 1¢, taker win rate 0.43% against 1% implied;
    - takers are negative at 80 of 99 price levels.
  - **Category gaps (maker minus taker):**

    | Category | Gap (pp) |
    |---|---|
    | Finance | 0.17 |
    | Politics | 1.02 |
    | Sports | 2.23 |
    | Weather | 2.57 |
    | Crypto | 2.69 |
    | Entertainment | 4.79 |
    | Media | 7.28 |
    | World Events | 7.32 |

  - **Time:**
    - launch–2023: takers +2.0%, makers −2.0%;
    - the gap flipped by 5.3 pp around the 2024 election (pre −2.9 pp, post +2.5 pp);
    - the longshot share of taker volume was flat (4.8% vs 4.6%).
  - **YES/NO:**
    - at 1¢, YES EV is −41% and NO EV is +23%;
    - NO beats YES at 69 of 99 price levels;
    - dollar-weighted, YES −1.02% and NO +0.83%.
- **Internal issue (PLAUSIBLE):** the taker and maker means are exact mirror images (±1.12%). The stated per-position
  return formula cannot give that, because a 10¢ YES taker and a 90¢ NO maker have different denominators. The figure
  is more likely PnL per contract-dollar than return on capital. Treat the magnitudes as approximate.
- **Prospectively tradable?** Role is known ex ante, but maker returns are realised only on filled orders and are gross
  of fees. No fill model. **Not shown.**
- **Replication needs:**
  - The public dataset.
  - Event-clustered CIs.
  - Fee-aware returns.
  - An explicit return denominator.
  - A Polymarket version using on-chain taker legs (see `sweep_polymarket-empirical.md` §4 on trade direction).

### 3.3 Whelan — "Agreeing to Disagree: The Economics of Betting Exchanges" (core; Betfair)

- **Metadata:** Karl Whelan (UCD). MPRA Paper No. 126351, dated 2025-09-09, posted 2025-10-20.
  - https://mpra.ub.uni-muenchen.de/126351/1/MPRA_paper_126351.pdf
  - Working paper; no journal found.
- **Read:** full text (46 pp.).
- **Mechanism (§4–5):**
  - Traders disagree (cross-sectional SD σ ≈ 0.03 in the calibration) but are right on average.
  - Those with the strongest beliefs take, to guarantee execution. Those with moderate beliefs make. Those near the
    mean abstain.
  - The model predicts: Takers underperform; Taker losses grow non-linearly as win probability falls; Makers earn most
    on the far side of longshots.
  - A commission (τ = 0.02) and Betfair's tick ladder (Table 1) set spreads.
  - Multiple equilibria: thick markets with narrow spreads, thin markets with wide ones.
- **Data (§6):**
  - Betfair "Advanced" historical files for all soccer matches 2022–2024, with 1-second order-book messages.
  - 214,992 matches with pre-kickoff prices.
  - Maker/taker is inferred by matching trades to the prior best quotes, which is not possible for every trade.
- **Evidence type:** descriptive, in-sample.
- **Costs:** returns are **post-commission** (2%). Spreads are embedded because roles are identified.
- **Dependence:** MZ standard errors clustered by match (200,622 clusters).
- **Key findings (VERIFIED):**
  - **Pre-play last traded prices are unbiased:** MZ F = 1.56, p = 0.211 on 601,866 bets (Table 2). There is **no FLB in
    Betfair pre-play soccer**.
  - **Pre-play 1X2** (902,568 bets, 152,102 matches): Takers −2.5%, Makers +0.6%, t = 11.8. The Maker SD is 198%, so
    mean-variance Kelly would stake only 0.5% of wealth (§7.1, fn. 10).
  - **Totals markets** (2,088,032 bets): Takers −2.2%, Makers +2.0%. Maker returns jump when the taker's win
    probability is > 0.9 (Fig. 15). In those trades the maker holds the longshot side against a taker who backs the
    favorite: a small stake at risk, so a small mispricing gives a large percentage return. This is not
    favorite-buying.
  - Taker losses rise steeply as probability falls (Fig. 14).
  - **Wider spreads mean larger losses for both sides, especially on longshots** (§7.2, Figs. 16–17).
  - **In-play:**
    - the FLB grows as the match goes on;
    - by the 105-minute timestamp (about the 87th minute), bottom-decile takers lose about 70%, and makers backing
      longshots lose almost as much;
    - takers backing strong favorites in the second half earn small, statistically significant profits (§7.3, Fig. 18).
  - **Caveat (§8):** maker returns cover only filled bets. Adverse selection may mean the profitable quotes don't
    fill. "Whether this approach can actually be turned into a practical trading strategy is left as an optional
    exercise."
- **Prospectively tradable?** The second-half favorite pattern is identifiable ex ante (match clock plus price) and was
  measured at taker prices after commission. But it is in-sample, from one sport and three seasons. **PLAUSIBLE
  candidate for H, not shown out of sample.**
- **Replication needs:**
  - Betfair historical data, which is commercial.
  - An out-of-sample season.
  - Clustering by match for the in-play results.
  - Equivalent Polymarket in-play sports tests (note `secondsDelay` on sports markets, per CONTEXT.md).

### 3.4 Zitzewitz — "Limits to Arbitrage and Prediction Market Efficiency: the Case of PredictIt" (core)

- **Metadata:** Eric Zitzewitz (Dartmouth). NBER Working Paper 35845, October 2026. DOI 10.3386/w35845.
  - https://www.nber.org/papers/w35845
  - The author discloses having traded on PredictIt.
- **Read:** full text (61 pp.). The NBER direct download was "Access denied" by curl, but the PDF arrived through
  WebFetch.
- **Mechanism:**
  - PredictIt capped downside risk at **$850 per contract** (2016–22), without netting across outcomes, and charged
    **10% of profits per contract**.
  - The cap lets longshot buyers take larger positions than favorite buyers. It also locks out traders who sell every
    outcome.
  - Short-aversion makes traders buy YES.
  - Result: overpricing (bids summing to > 100) plus an FLB (Manski 2006 / Ali 1977 logic).
- **Data (§III):**
  - Trade data from December 2015; hourly API quotes from 2019-06-08.
  - Main sample 2016–22, just over 5,000 markets.
  - Comparison samples: 2023–24 and the 2025–26 relaunch, when the limit was $3,400.
  - 191 markets matched to Betfair (Aug 2019 – Dec 2022).
- **Evidence type:** descriptive and in-sample calibration (logit on log-odds). Cross-venue price comparison.
- **Costs:**
  - Arbitrage conditions are derived after the 10% profit fee. Fees are roughly (100/9)(1−H), where H is the
    Herfindahl index of outcome probabilities (App. A).
  - Quote data restricted to 1-point spreads.
- **Dependence:** standard errors clustered by **event date** (e.g., all same-day elections). The author reports these
  are within 10–20% of market-clustered SEs.
- **Key findings (VERIFIED):**
  - **Overpricing:** the most active multi-outcome markets often had bids summing to 110–125. After-fee arbitrage
    existed in 1.9% of markets at any time in 2019–22 (§IV). Overpricing was more common in high-volume, many-outcome
    markets (Table 5B).
  - **Logit slopes (Table 6; > 1 = FLB):**
    - yes/no 1.501 (SE 0.138), 2-outcome 1.536, 3+ outcomes 1.423;
    - a 0.2 price pays off 13% (yes/no) or 11% (2-outcome);
    - for comparison, about 18% on Kalshi (Bürgi et al.), and Page & Clemen's slope was 1.25.
  - **By topic (Table 7):** elections 1.946, investigations 1.912, polling 1.332, "other" 1.029.
  - **By time to election (Table 8):** no decline as the election nears (1 day: 1.474; 16 weeks: 1.585 for 1–2-outcome
    markets).
  - **Against Betfair (Table 9):** PredictIt's FLB is 1.158× (binary) and 1.137× (multi) Betfair's. About 15% of
    matched observations allowed cross-venue arbitrage after fees (Table 10). The typical trade sold PredictIt
    longshots and bought PredictIt favorites.
  - **2025–26 (Table 11):** slope 0.794 (SE 0.230). **No FLB** once the limit rose 4× and volume fell about 10×.
- **Internal inconsistencies:**
  - The text says the yes/no and 2-outcome slopes imply 1.38 and 1.51; Table 6 shows 1.501 and 1.536.
  - The Table 11 note describes Betfair-on-PredictIt regressions, apparently copied from Table 9.
  - The Table 6 row label "Strong favorite (p < 0.5)" is probably meant to read "no strong favorite".
- **Prospectively tradable?**
  - Historically yes, for arbitrage that was visible at quotes, but capped at about $45–90 per market by the $850 limit.
  - The FLB itself is gone after 2025.
  - **Lesson for Polymarket:** the bias was a creature of arbitrage limits. Polymarket has no position limits, which
    predicts a smaller FLB (PLAUSIBLE).
- **Replication needs:** PredictIt API quotes, which are only partly public historically.

### 3.5 Cardozo & Rivero-Wildemauwe — "The Favorite–Longshot Bias in Prediction Markets: Evidence from Polymarket" (core)

- **Metadata:** arXiv:2609.12878 v1, 2026-09-11. Preprint. https://arxiv.org/abs/2609.12878
- **Read:** the sibling note `title_flb-polymarket.md` read all 51 pp. I re-read Tables 6, 9, 14 and 16 and §5.2 myself
  (VERIFIED).
- **Data:** Polymarket Users dataset v1.3 (Akey et al.), 2022-11-11 to 2026-03-29. 560.9M resolved purchases,
  $22.49B. Mostly pre-fee era.
- **Evidence type:** descriptive, in-sample. **Pre-fee**, hold to resolution, CIs clustered by parent event.
- **Key findings (VERIFIED):**
  - **Tails depend on aggregation (Table 6):**

    | Aggregation | Longshots (p < 0.10) | Favorites (p ≥ 0.90) |
    |---|---|---|
    | Equal child market | −6.30% [−8.38, −4.22] | +0.277% [0.242, 0.312] |
    | Pooled | −19.35% [−46.99, 8.30], **not significant** | +0.83% |
    | Equal parent event | **+4.09%** | +0.392% |

  - **By buyer role (Tables 9B and 16A, equal child):**

    | Role | Longshots | Favorites |
    |---|---|---|
    | Posted offer (maker) | −3.50% | **+0.641%** [0.607, 0.675] |
    | Accepted offer (taker) | −31.17% | **−0.460%** [−0.515, −0.405] |

    - Pooled, favorites earn +0.82% for makers and +0.88% for takers.
  - **Longshot losses are not shorter-horizon losses (Table 14).** Equal-child longshot returns are −13.14% for markets
    closing ≤ 1 day after purchase, but +2.39% for ≤ 30 days.
  - **Interim prices after posted-offer purchases are higher, not lower (§5.2):**
    - longshots: +3.92% at 5 minutes, +16.91% at 1 hour, +7.56% at 1 day;
    - favorites: +0.17% to +0.26%.
    - These are last-trade valuations, not executable.
- **Prospectively tradable?** **No evidence.** The favorite premium is +0.28% to +0.83% before fees. It is negative for
  takers in equal-child aggregation and smaller than today's taker fee plus half-spread at 0.90–0.95.
- **Replication needs:** see the sibling note §"What to replicate".

### 3.6 Page & Clemen — "Do Prediction Markets Produce Well-Calibrated Probability Forecasts?" (core)

- **Metadata:** *Economic Journal* 123(568), 491–513, May 2013. DOI 10.1111/j.1468-0297.2012.02561.x.
  - Author copy: https://people.duke.edu/~clemen/bio/Published%20Papers/45.PredictionMarkets-Page&Clemen-EJ-2013.pdf
- **Read:** full text.
- **Mechanism (§2):**
  - Traders discount the future, and Intrade paid no interest (except on balances > $20k).
  - Buying a favorite ties up more capital per unit of edge than buying a longshot.
  - So favorite buyers drop out more as time to expiry grows, and prices compress toward 0.5.
  - Applying Ali's (1977) and Manski's (2006) logic over two periods turns this into an FLB that grows with horizon.
- **Data (§3):**
  - Intrade transactions on markets lasting > 1 month; markets started 2002-08-22 to 2007-02-06.
  - Raw: 1,883 markets, 512,828 trades. Final: 597 competitions, 1,787 markets, 512,612 transactions.
  - 1,064 sports, 302 political and 421 other markets.
  - Mean duration 205 days (27–649) (Table 1).
- **Evidence type:** in-sample calibration (local linear regression, plus a Lattimore et al. parametric pseudo-likelihood
  model), plus a simple **out-of-sample** split (§5).
- **Costs:** none. No fees, spreads or Intrade's charges. Time value is handled through discount rates.
- **Dependence:** strong. Clustered bootstrap over competitions (400 reps), drawing 10 random transactions per
  competition at each price point so large markets don't dominate.
- **Key findings (VERIFIED):**
  - **Overall:**
    - a 0.20 price → 15.3% frequency; a 0.80 price → 87.4% (§4.2.2);
    - prices near 0 and 1 are well calibrated, so the S-curve does not continue into the extreme tails;
    - parametric curvature c = 0.80, which equals slope 1.25 in Zitzewitz's convention (Table 2).
  - **Political markets:** 0.20 → 10.9%; 0.80 → 92.8% (§4.2.3).
  - **Time:** the bias is much stronger with > 100 days to expiry (Figs. 6–7). Time to expiration is significant in the
    PL model (Table 2 cols. 2–4).
  - **Volume** has no effect (Table 2 col. 4).
  - **Out-of-sample:**
    - fit on markets started 2002-08-22 to 2005-01-14; trade those started 2005-01-15 to 2007-02-06;
    - strategy A (buy/sell by the S-curve): **+5.25%**;
    - strategy B (buy > 0.5, sell < 0.5): **+9.55%**;
    - at a 10% discount rate, A falls to 2.47%;
    - a **15% rate eliminates A and a 25% rate eliminates B**.
- **Prospectively tradable?** The out-of-sample design is ex ante, but it trades at transaction prices with no fees,
  spreads or depth. The edge is consumed by capital cost over long horizons. **Weak.**
- **Relevance to Polymarket:**
  - Collateral is pUSD.
  - CONTEXT.md lists `holdingRewardsEnabled` on some markets. That is the analogue of "paying interest on committed
    balances", which Page & Clemen propose as the fix.
  - Long-dated Polymarket politics is where their mechanism should bite (PLAUSIBLE).

### 3.7 Le — "Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics in Prediction Markets" (core/supporting)

- **Metadata:** Nam Anh Le (National Economics University, Vietnam).
  - arXiv:2602.19520 [stat.AP]: v1 2026-02-23, v2 2026-08-04.
  - The repo README says it was "prepared for an IJF revision" (PLAUSIBLE that it is under review at IJF).
  - Code: https://github.com/namanhzz/prediction-market-calibration (MIT; existence VERIFIED). The data come from
    Becker's repo.
- **Read:** §1–6 and the data, fee and limitation passages in full. §7–8 (decomposition and Bayesian model) skimmed.
- **Mechanism:** descriptive. The paper does not test causes. Large political trades on Kalshi are associated with extra
  compression toward 50%.
- **Data:**
  - Kalshi: 64.7M trades, 210,608 binary contracts, 2021-07-01 to 2025-12-31.
  - Polymarket: 288.7M trades, 218,000 resolved contracts, from 2023-03-06.
  - Polymarket timestamps are derived from block numbers with about **3 h of noise** (§3.1).
  - Trades at 5–95¢ only; ≥ 10 trades per market; ≥ 200 trades per cell.
- **Evidence type:** descriptive, in-sample. The only "out-of-sample" figure (71.5%) is for explaining slope variance,
  not trading.
- **Costs:**
  - A Kalshi fee exposure is computed from the formula: about 1.2–1.3¢ per contract on average.
  - No maker/taker treatment. Polymarket costs ignored.
- **Dependence:** event- and market-clustered bootstraps. A Bayesian measurement-error model suggests about half the raw
  slope variation is noise.
- **Key findings (VERIFIED):**
  - **Kalshi slope by domain × horizon (Table 4; > 1 = FLB-like compression):**
    - Politics: 0.93–1.83, with 1.83 at 2d–1w and 1w–1mo;
    - Sports: 0.90–1.10 out to 48 h, then 1.74 beyond 1 month;
    - Weather: 0.69–0.97 within 48 h, i.e. over-extreme;
    - Crypto: about 1.0–1.36.
  - **Polymarket:** Politics mean slope 1.45, Sports 1.06, Crypto 1.06 (§5).
  - **Trade size:** Kalshi Politics, Large minus Single trades = +0.53 [0.29, 0.75]; event-clustered [0.12, 1.80]. Not
    robust on Polymarket (+0.21 [−0.31, 1.12] market-clustered) (Table 5, Table 12).
  - **ECE:** Politics 0.117, against 0.007–0.022 for other domains (Table 6).
- **Prospectively tradable?** Not tested. The political compression is the most consistent cross-venue regularity, but
  no executable-price or fee test was run.
- **Replication needs:** Becker's dataset; recompute on Polymarket with exact on-chain timestamps; event-clustered
  returns, not slopes.

### 3.8 Snowberg & Wolfers — "Explaining the Favorite–Long Shot Bias: Is it Risk-Love or Misperceptions?" (supporting; classic)

- **Metadata:** see §2. JPE 118(4) 723–746 (2010); NBER WP 15923.
- **Read:** NBER WP full text.
- **Mechanism:**
  - Both risk-love and probability misperception fit win-bet prices exactly.
  - They separate the two using compound bets (exacta, quinella, trifecta).
  - Misperception (a Prelec weighting with α ≈ 0.928) prices exotics much better, e.g. **18.4% lower MAE** for exactas
    (§4, Table 1).
- **Data:** all 6,403,712 US horse starts, 1992–2001. Also 2.725M Australian and 380k UK starts (§2).
- **Key findings (VERIFIED):**
  - Returns: about −61% at 100/1+; −23% betting at random; −5.5% always backing the favorite (Fig. 1).
  - The FLB is stable since 1949, and across parimutuel and bookmaker systems.
  - **No positive returns to extreme favorites** in any of their datasets, contradicting the Thaler & Ziemba
    suggestion (§2).
  - "Misperceptions are not large enough to generate profit opportunities for unbiased bettors" (§6).
- **Costs:** track take embedded in the odds.
- **Dependence:** race fixed effects in the exotic tests.
- **Tradable?** **No.** The authors themselves find no profitable simple strategy.
- **Transfer to Polymarket:** misperception predicts overpricing of tiny probabilities. On a CLOB, that shows up as
  YES longshot overpricing only if no one sells into it cheaply. Cheap selling is exactly what makers do (§3.2).

### 3.9 Moshrefi — "Prices, Probabilities, and Parlays: Systematic Bias in Sports Prediction Markets" (supporting)

- **Metadata:** Niusha Moshrefi (Princeton). arXiv:2607.14430 v1, 2026-07-15. Preprint.
- **Read:** full text (short paper).
- **Data:**
  - Kalshi NBA, MLB and NHL regular-season moneylines, early March to mid-May 2026.
  - About 23M trades: 13.0M NBA, 7.1M MLB, 2.8M NHL.
  - Prices **exclude fees**.
- **Key findings (VERIFIED):**
  - Calibration is near-perfect mid-life and departs sharply near expiry.
  - **In the final 10 minutes** the curve becomes step-like: "contracts trading at 10–40 cents in the final ten minutes
    resolve favorably almost never". In the 0–10 minute bucket the power-law γ is 1.27–1.31 across leagues, and the
    Platt slope a is 1.62 (NBA), 2.05 (MLB) and 4.56 (NHL). Both equal 1 under perfect calibration (§IV.A).
  - **Cross-game parlays are overpriced against the product of their legs** (12,639 parlay trades, Table I):
    - median ratio 0.991 at 2 legs, 1.005 at 5, 1.066 at 8, 1.223 at 10;
    - overall mean 1.028.
- **Dependence: not handled.** There is no clustering by game, although every trade in a game's last 10 minutes shares
  one outcome. The effective sample is games (roughly thousands), not 23M trades. **The significance of the near-expiry
  result is unverified.**
- **Tradable?** Not tested. Fees, spreads and near-settlement liquidity are absent.
- **Relevance:** independent support for H (late in-play longshot overpricing), alongside Whelan (Betfair) and Page
  (2012, Intrade).

### 3.10 Berg & Rietz — "Longshots, Overconfidence and Efficiency on the Iowa Electronic Market" (supporting)

- **Metadata:** Joyce E. Berg, Thomas A. Rietz.
  - *International Journal of Forecasting* 35(1), 271–287, Jan 2019. DOI 10.1016/j.ijforecast.2018.03.004.
  - WP dated Feb 2018: https://www.biz.uiowa.edu/faculty/trietz/papers/Longshots.pdf
- **Read:** WP sections 1–4 and the strategy section.
- **Setting:**
  - IEM Microsoft Price Level and Computer Industry Returns markets: binary/winner-take-all, monthly 4–5 week markets
    over 5+ years.
  - Exact dates were not stated in the parts I read. A comparison with stock Sharpe ratios for 1996–2000 suggests that
    period (PLAUSIBLE).
  - **No fees; $500 account cap; complete slates buy/sell at $1** (§II.A–B).
- **Key findings (VERIFIED):**
  - **No longshot bias.**
  - In the lowest price quintile the average price is $0.0016 against a payoff frequency of 0.0135. Longshots are
    *under*priced (Table 2).
  - Prices are significantly above payoffs for $0.8–1.0 at the 4- and 14-day horizons.
  - Logit slopes are < 1 (overconfidence, a *reverse* FLB) at horizons ≥ 3 days, and efficient at 1–2 days (Fig. 2).
  - Buy-and-hold Sharpe ratios for ≤ $0.15 contracts are positive at intermediate horizons.
  - The dynamic strategy earns 0.31–1.2% per month, but it **uses in-sample logit estimates**. The authors say it "could
    not actually have been implemented".
- **Relevance:** the strongest evidence that cheap complete-set arbitrage and zero fees remove the FLB. Polymarket has
  split/merge at $1 (CONTEXT.md) but charges taker fees.

### 3.11 Qiu & Qiu — "Time-Varying Favorite-Longshot Bias in Polymarket Weather Markets" (supporting)

- **Metadata:** Shouchen Qiu (high-school student), Huaijun Qiu. arXiv:2610.13593 v1, 2026-10-09.
  - The arXiv comment claims acceptance at the IEEE ICDM 2026 Teen Research Symposium (PLAUSIBLE).
  - The linked GitHub repo is not public (sibling note).
- **Read:** full text (5 pp.).
- **Data:**
  - Polymarket daily max-temperature markets in 10 cities, 2025-12-05 to 2026-07-31.
  - 2,189 events, 21,697 buckets, 8,544,732 taker trades (Table I).
  - Chronological split: train to May, validate June, test July.
  - The price at horizon h is the **mean taker price in a ±0.5 h window**, which is not executable.
- **Key findings (VERIFIED, Table III; July test; $10 per trade; fee 0.05·r(1−r) per share; no depth, spread or
  slippage):**

  | Rule | Trades | NO win rate | Pre-fee ROI | Post-fee ROI |
  |---|---|---|---|---|
  | Buy NO on favorites, 1–12 h before peak | 184 | 20.7% | +54.96% | **+50.71%** (wide CI; event bootstrap) |
  | Buy NO on longshots, 30–48 h | 11,924 | 97.8% | −0.13% | −0.23% |

  - Favorite overpricing near the peak is about 10× larger than longshot overpricing.
- **Citation error:** the text attributes ref. [10] (Le 2026) to "Akey".
- **Tradable?** **One-month out-of-sample diagnostic at non-executable prices with 184 trades.** A lead for H in the
  Weather category, not evidence.

### 3.12 Dubach — "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book" (supporting; costs)

- **Metadata:** Philipp D. Dubach. arXiv:2604.24366 v2, 2026-05-14 [q-fin.TR].
  - Replication: https://github.com/philippdubach/polymarket-microstructure (MIT; existence VERIFIED).
  - Zenodo DOI 10.5281/zenodo.19811426.
- **Read:** abstract, §1, §3.5, §5.1–5.2 and the conclusion.
- **Data:**
  - The Polymarket public WebSocket book feed, 2026-02-21 to 2026-04-15: 30.3B events, 385,198 markets.
  - Joined to on-chain V1 `OrderFilled` events.
  - A pre-registered panel of 600 markets.
- **Key findings (VERIFIED):**
  - **"Longshot spread premium"** (SF1):
    - median spread about 400 bps of mid at mid 0.4–0.6;
    - 1,300–1,800 bps for markets with mid < 0.10;
    - the paper calls the latter "650–900 bps half-spread".
    - The text is ambiguous whether 400 bps is a half or a full spread.
  - Depth is spread across 10 levels; top of book holds a median 0.136 share (SF2).
  - Feed-inferred trade direction matches the chain only about 59% of the time.
- **Relevance:**
  - With a 1¢ tick, crossing at 0.05 costs about 10% of the purchase, while crossing at 0.95 costs about 0.5% (my
    arithmetic).
  - Combined with taker fees (rate × (1−p)), this makes longshot *buying* hopeless.
  - It makes favorite buying a question of whether a 0.3–0.8% edge beats about 0.7–1.2% of cost.
  - The sibling sweep (§3.8) reports Dubach's companion paper: a realised spread of about 1.3¢ per share.

### 3.13 Rothschild & Sethi — "Trading Strategies and Market Microstructure: Evidence from a Prediction Market" (supporting/peripheral)

- **Metadata:** see §2. Read the WP (2015-11-22) in full.
- **Data:**
  - Intrade 2012 presidential winner market, 2010-11-16 to 2012-11-07.
  - 6,300 accounts, about 300k trades, about 13M contracts.
  - Aggressor side and account IDs known.
- **Key findings (VERIFIED):**
  - **87% of traders are unidirectional**: they never switch side (32% of volume).
  - **Arbitrageurs** are 1% of traders and 16% of volume. They book small, near-riskless profits on tiny margin. Example:
    trader A, aggression 0.77, +$61,871 profit on $9,877 margin (Table 1).
  - **One trader (B) lost about $6.88M** holding Romney. Their bids formed a "firewall" that kept Intrade prices away
    from Betfair's.
  - The Intrade–Betfair gap persisted at **5–10 pp** despite Betfair's 2–5% commission.
  - The Intrade spread was "a penny or two per $10".
- **Costs and calibration:** profits are gross of Intrade fees. No calibration or FLB analysis.
- **Relevance:**
  - Wallet-level evidence that large biased traders can hold prices away from fair value for long periods (A, B and
    cross-venue relative value).
  - Liquidity-providing and arbitrage accounts are the consistent winners, as on Kalshi and Polymarket.

### 3.14 Ottaviani & Sørensen (2008 Handbook chapter; 2010 AEJ: Micro) (supporting; theory)

- **Read:** the 2008 chapter in full (Bocconi PDF). The 2010 AEJ article: metadata only.
- **Taxonomy (VERIFIED, §1):** seven explanations.
  1. Misestimation of probabilities (Griffith).
  2. Market power of informed bettors (Isaacs).
  3. Risk or skewness preference (Weitzman).
  4. Heterogeneous beliefs under parimutuel pricing (Ali).
  5. An uninformed bookmaker against insiders (Shin).
  6. Limited arbitrage because of track take (Hurley & McDonough).
  7. Simultaneous last-minute betting by informed insiders (O&S).
- **Key point for transfer (VERIFIED, §7):**
  - In Shin's model, the FLB arises from monopoly bookmaking.
  - Under perfect competition the bias vanishes: m = q/(1−z), so m/q is constant.
  - Under limited arbitrage (§8), a positive take τ keeps rational money from fully correcting the longshot, giving
    m = p(1−τ).
- **Transfer to Polymarket:**
  - Mechanisms 4 and 7 are parimutuel-specific and do not apply to a CLOB.
  - Mechanism 5 applies only in modified form: makers face informed takers.
  - Mechanisms 1, 3 and 6 can transfer. Taker fees and spreads play the role of the take (PLAUSIBLE).

### 3.15 Shin (1991; 1992; 1993) (supporting; theory and measurement)

- **Read:** abstracts (RePEc) and the O&S exposition. Full texts are on JSTOR and not accessible.
- **Content (abstracts):**
  - **1991:** a bookmaker facing insiders optimally sets prices by a "square root rule". Odds understate favorites and
    exaggerate longshots.
  - **1992:** gives a necessary and sufficient condition for the favorite bias when bookmakers compete in prices
    against insiders.
  - **1993:** the spread, or overround, reflects the incidence of insider trading. That incidence is estimated from UK
    data. This is the source of the widely used "Shin z".
- **Transfer:** on a CLOB, the analogue is makers widening quotes on cheap contracts to protect against informed
  takers. That is consistent with Dubach's longshot spread premium and Whelan's wide-spread results, but not tested
  there (PLAUSIBLE).

### 3.16 Thaler & Ziemba (1988) and Ziemba's revisit (supporting; classic)

- **Read:**
  - The 1988 JEP article itself was **not accessible** (403).
  - I read Ziemba's 2020 SRC Discussion Paper 103, "Parimutuel betting markets: racetracks and lotteries revisited"
    (published 2023 in the *Annual Review of Financial Economics* 15:641–662).
- **Claims about the 1988 material (PLAUSIBLE; from Ziemba 2020, an original co-author):**
  - In 1986-era data there was "a small profit, about 3%" betting to win at odds of 3-10 or shorter.
  - 100-1 shots were "worth only about 13.7 cents per dollar bet".
  - Explanations offered: bragging rights, transaction costs, prospect-theory overweighting of small probabilities,
    mental accounting.
  - Ziemba (2020): "In the more recent data… the favorites are no longer underbet enough to turn a profit… However,
    investors can still short longshots on betting exchanges like Betfair and make a profit." That last claim is
    UNSUPPORTED here.
  - Snowberg & Wolfers (1992–2001 data) find no positive returns to extreme favorites (VERIFIED).

### 3.17 Kagan & Baiocchi — "Calibration in Prediction Markets: Theory and Evidence" (peripheral; abstract only)

- **Metadata:** Nicole Kagan, Rubens Baiocchi (Kalshi Research). SSRN 7355520, Crossref record 2026-08-28.
  - Also a PDF at kalshi.com/research, which returned 429 or an HTML challenge to me.
  - **The exchange itself is the author.**
- **Abstract claims (VERIFIED as claims):**
  - 2,243,741 resolved Kalshi markets, 11 categories, 2021 to mid-2026.
  - Brier score about 0.08–0.09 at 3 months, about 0.02 at close.
  - Naive accuracy 88.3% → 97.2%.
  - Calibration improves "near-monotonically" with volume and number of traders. Mentions is worse.
  - Anchoring to the true event time "de-biases" Elections and improves Sports.
- **Use:**
  - A counterweight to Bürgi, Becker and Le, but **not checked in full text**.
  - Brier and reliability diagrams near the 45° line are fully compatible with tail FLB returns. A 1¢ error on a 5¢
    contract is invisible in Brier but is a −20% return.

### 3.18 Deleep, Lee, Bai, Suresh & Dhawan — "How Wise is the Crowd? Bias and Edge in Prediction Markets" (peripheral; abstract only)

- **Metadata:** SSRN 6322678 (Crossref 2026-03-18). Zitzewitz cites it as a "UC-Berkeley mimeo".
- **Abstract claims (VERIFIED as claims):**
  - Polymarket and Kalshi tick-level order flow, wallet histories and comments.
  - The FLB is not present in every market.
  - Where it appears (Mention markets), it "may be a statistical artifact masking a pervasive 'Yes Bias'" once time to
    completion is controlled for.
  - Whales lose EV to small traders.
- **Use:** consistent with Becker's YES/NO asymmetry and with the time-to-expiry caveats. **Full text unread** (SSRN
  403).

**Pointers to Polymarket items covered elsewhere (not re-read by me):**
- Reichenbach & Walther (2026), SSRN 7552098 (abstract): "no general market-level longshot bias"; "default outcomes
  are persistently overpriced".
- Gruener, SSRN 6863546 (abstract): the FLB in 5-minute crypto markets disappears under contract-clustered inference.
- Akey et al. (CEPR DP 21615): maker share is the strongest correlate of positive PnL.
- See `sweep_polymarket-empirical.md` §3.18, §5 and `title_who-wins-who-loses.md`.

---

## 4. Cross-paper contradictions and measurement pitfalls

1. **Weighting flips signs.**
   - Equal-weighting price observations: Bürgi's −20% average makes cheap contracts dominate.
   - Dollar-pooling: Cardozo & R-W pooled −19.35% longshots.
   - Equal-event weighting: Cardozo & R-W +4.09%.
   - All three give different answers. A strategy's P&L is dollar-weighted *within the strategy's own selection rule*.
     Compute that, not a calibration statistic.
2. **Return vs probability error.** A +0.24 pp probability error on Polymarket longshots coexists with −6.30% returns
   (Cardozo & R-W §3.1). Brier and reliability results ("well calibrated", Kagan & Baiocchi; Becker's own note) cannot
   rule out large tail returns.
3. **Correlated observations.**
   - Trade-level CIs (Becker, Moshrefi) are far too narrow.
   - Clustering by event or event date (Bürgi; Page & Clemen; Zitzewitz; Cardozo & R-W; Le; Whelan) is the minimum.
   - Gruener (via the sibling sweep) reports that an FLB disappears under clustering.
4. **Maker returns are conditional on fills.** No paper simulates queue position or unfilled quotes. Whelan and Becker
   explicitly warn about adverse selection.
5. **Fee modelling errors.**
   - Bürgi charges makers the full taker fee; current Kalshi API data suggest most series have no maker fee.
   - Becker, Le, Cardozo & R-W and Moshrefi are pre-fee.
   - Only Whelan (Betfair commission), Zitzewitz (PredictIt arbitrage) and Qiu & Qiu (a simplified Polymarket fee) are
     post-fee.
   - None uses Polymarket's per-market `feeSchedule` or maker rebates.
6. **Venue design explains magnitudes.** The FLB is largest where arbitrage is capped (PredictIt; Intrade's long-dated,
   no-interest markets) and absent where it is cheap (IEM slates; Betfair). Results from one venue do not transfer
   numerically to another.
7. **Near-expiry direction differs by category.**
   - Sports in-play: longshots overpriced late (Whelan, Moshrefi, Page 2012).
   - Weather: favorites overpriced late (Qiu & Qiu; Le's weather slopes < 1).
   - IEM financial binaries: reverse FLB at intermediate horizons (Berg & Rietz).
8. **The citing literature disagrees on the facts.**
   - Zitzewitz cites Deleep et al. as finding "no evidence of a longshot bias in either Polymarket or Kalshi". Their
     abstract is narrower: absent in some markets, an artifact in others.
   - Zitzewitz cites Bürgi for "about 0.18 for outcomes priced at 0.2". I did not check Bürgi's Figure 3, which is an
     image.

## 5. What to replicate on Polymarket before risking money (E and H)

1. **Universe and data:**
   - Resolved markets with on-chain taker and maker legs: CryptoHouse `orders_filled` to 2026-01-05, then Data API
     `/v2/trades?taker_only=false`. Identify the taker leg per CONTEXT.md and the sibling sweep §4.
   - Per-market Gamma `feeSchedule` and `feesEnabled`.
   - `umaResolutionStatus` for dispute risk.
2. **Cells:** price bucket (≤ 0.05, 0.05–0.10, …, 0.90–0.95, ≥ 0.95) × time to resolution (< 1 h, 1–12 h, 12–48 h,
   2–7 d, 7–30 d, > 30 d) × category × role (maker or taker).
3. **Statistics:**
   - Dollar-weighted P&L per $ **after the fee the trade would pay today** (taker: rate·p(1−p) per share; maker: 0 plus
     the rebate share).
   - CIs clustered by parent event, plus leave-one-event-out.
   - Report the worst event loss in each cell.
4. **Time split:** fit cells before date T; evaluate after T. Include post-2026-03-30 fee-era data separately.
5. **Executability:**
   - Collect live `/book` snapshots for candidate cells. The candidates suggested by this literature:
     - maker bids on 0.90–0.97 favorites in Politics and Crypto with > 7 days to resolution;
     - late in-play sports favorites;
     - fading late weather favorites.
   - Measure depth, spread and maker fill rates prospectively. There is no historical book (CONTEXT.md). A third-party
     PMXT archive is mentioned in the sibling sweep; terms unchecked.
6. **Capital cost:** annualise using holding days. Page & Clemen show that a discount rate of 15–25% erases long-dated
   edges. Include any `holdingRewards`.
7. **Kill criteria:** if the post-fee, event-clustered, out-of-sample maker edge at 0.90–0.97 does not exceed fill-adjusted
   costs and the tail loss from wrong or disputed resolutions, drop family E.

## 6. Discrepancies with CONTEXT.md and other notes

- No conflict with CONTEXT.md platform facts.
- New fact for the project (VERIFIED 2026-10-17, Kalshi public API `/trade-api/v2/series?limit=1000`):
  - 15,187 series in total;
  - 14,992 `fee_type = "quadratic"`, 159 `"quadratic_with_maker_fees"`, plus small numbers with multiplier 0.5 or 0
    and 3 `"quadratic_with_combo_maker_fees"`;
  - examples: KXNBAGAME and KXFED have maker fees; KXHIGHNY and KXPRESPERSON do not.
  - Relevant to Kalshi–Polymarket comparisons and to Bürgi et al.'s fee assumption.
- `sweep_polymarket-empirical.md` lists Le (2602.19520) as "abstract only". I read the main text. Its abstract-level
  summary is consistent with what I found.

## 7. Search log

1. Read CONTEXT.md and the sibling notes (`title_flb-polymarket.md`, `title_who-wins-who-loses.md`,
   `sweep_polymarket-empirical.md`). Took their citations as leads.
2. **Crossref** (`query.bibliographic`) confirmed exact metadata for Thaler & Ziemba 1988; Snowberg & Wolfers
   (JPE + NBER + SSRN); Page & Clemen; Rothschild & Sethi; Shin 1991/1992/1993; Ottaviani & Sørensen 2008/2010;
   Gandhi & Serrano-Padial 2015 (RES 82(1):156–186); Smith, Paton & Vaughan Williams 2006 (Economica 73(292):673–689);
   Berg & Rietz 2019; Whelan 2023 (QF 23(11):1699–1712); Whelan 2024 Economica 91(361):188–209; Page 2012 (Applied
   Economics 44(1):81–92); Angelini, De Angelis & Singleton 2022 (IJF 38(1):282–299); Angelini & De Angelis 2019 (IJF
   35(2):712–721); Tetlock 2008 SSRN 929916; Green, Lee & Rothschild "The Favorite-Longshot Midas" SSRN 3271248;
   Moskowitz & Vasudevan "Betting Without Beta" SSRN 3845505. I also pulled Crossref records and abstracts for Becker
   SSRN 7217640, Kagan & Baiocchi SSRN 7355520 and Deleep et al. SSRN 6322678.
   - Crossref occasionally returned non-JSON (rate limit); retries succeeded.
3. **Full texts obtained:**
   - CESifo PDF (Bürgi et al.); NBER w15923 (Snowberg & Wolfers); Duke author copy (Page & Clemen);
   - researchdmr.com WP (Rothschild & Sethi); MPRA 126351 (Whelan, Betfair); Bocconi PDF (O&S 2008);
   - Iowa WP (Berg & Rietz); FMG/SRC DP 103 (Ziemba 2020); jbecker.dev (Becker web paper);
   - arXiv 2602.19520v2, 2607.14430, 2604.24366v2, 2609.12878, 2610.13593, 2607.06166;
   - NBER w35845: curl got "Access denied"; WebFetch retrieved the PDF binary, which I converted with pdftotext.
4. **arXiv API:** `abs:Kalshi` (25 recent), `all:"longshot" AND all:"prediction market"` (3),
   `abs:Polymarket AND abs:calibration`, `abs:"prediction market" AND abs:maker AND abs:taker`,
   `abs:Betfair AND abs:longshot` (0), `abs:PredictIt` (1, Sethi et al. 2021 on election forecasting; not FLB).
5. **WebSearch** surfaced: NBER w35845 (PredictIt); Whelan MPRA 126351 (via Becker's references); Kalshi Research
   calibration (Kagan & Baiocchi); Deleep et al. (via Zitzewitz's references and Quantpedia); the FC'26 DeFi talk by Fabi,
   Marfè, Ruffo & Schönleber (Polymarket BTC bets vs Deribit option-implied probabilities).
   - The FC'26 item is a 3-page abstract with no return numbers: tail events "persistently" overpriced, 255 bets,
     March 2024 – May 2025. A lead only.
6. **Dead ends:**
   - AEA PDFs for Thaler & Ziemba 1988 and O&S 2010 (Cloudflare 403; no Wayback snapshot).
   - JSTOR for Shin (page did not load).
   - QUT ePrints for Page (2012), "It ain't over till it's over" (empty response): abstract-level only via search
     snippets.
   - kalshi.com: the research PDF and fee-schedule PDF returned 429 or an HTML challenge, so I used the Kalshi public API
     instead.
   - SSRN (403) for Becker, Kagan & Baiocchi, Deleep et al. and Reichenbach & Walther.
   - Quantpedia (WAF 403 to curl; WebFetch worked, but only for a summary).
7. **Not pursued in depth:** they are less relevant to a CLOB, or their full text was inaccessible.
   - Ottaviani & Sørensen AEJ:Micro 2010 (parimutuel timing).
   - Gandhi & Serrano-Padial 2015 (parimutuel belief heterogeneity).
   - Moskowitz & Vasudevan (US sportsbook moneyline vs spread FLB).
   - Smith, Paton & Vaughan Williams 2006. Per its abstract, Betfair horse-racing odds show "significantly lower market
     biases" than bookmakers; RePEc abstract VERIFIED.
   - Tetlock 2004/2008 (TradeSports). Per Zitzewitz, an FLB "only in the most liquid sports prediction markets"; not read.
   - Gu, Kagan, Sun, Wu & Xu, arXiv 2607.06166: a proper-betting strategy with a Kalshi live pilot. Not FLB.
8. **Repository checks** (WebFetch):
   - Jon-Becker/prediction-market-analysis exists: MIT, about 3.9k stars, 36 GiB data.
   - namanhzz/prediction-market-calibration exists: MIT, code only.
   - philippdubach/polymarket-microstructure exists: MIT; the panel data are included, the raw archive is not.
