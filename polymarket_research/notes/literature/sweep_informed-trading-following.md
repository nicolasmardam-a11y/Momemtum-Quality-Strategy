# Literature sweep: informed trading, skill persistence, copy trading and detection latency

As of 2026-10-17. Author: research agent (literature sweep). Labels:

- **VERIFIED**: I read it in the primary source myself. I say which version I read when it differs from the
  published one.
- **PLAUSIBLE**: consistent with the evidence but not directly checked. This includes numbers I saw only in an
  abstract, in a search snippet, or in another paper's summary.
- **UNSUPPORTED**: I found no evidence for it.

Scope:

- Whether observable trader behaviour predicts outcomes, and whether followers can profit after costs and
  latency.
- Informed and insider trading in betting exchanges and prediction markets.
- Skill persistence, and luck versus skill under multiple testing.
- Copy and social trading, and following disclosed trades (13F, copycat funds, on-chain "smart money").
- How fast prices absorb information and large informed trades.
- The 2025–2026 US legal position on insider trading in event contracts.

Relation to sibling notes. `sweep_polymarket-empirical.md` already covers Mitts & Ofir, Akey et al., Della Vedova
("Execution, not Information") and Gómez-Cram et al. at abstract level. I do not repeat that. I add the parts of
Gómez-Cram et al. and Mitts & Ofir that two other papers report from their full texts. This file also feeds the
pre-registered test in `notes/strategies/pit_wallets_preregistration.md` ("follow wallets that won five of five").

## 1. Bottom line for a retail trader

None of the papers I read shows a wallet-following or copy-trading rule that you could pick in advance, execute at
real prices after fees and latency, and see survive a time-ordered out-of-sample test in a prediction market. The
literature supports four narrower conclusions.

1. **Informed trading in prediction markets is real, measurable and concentrated in specific contract types.**
   - On Kalshi, markets on a single company or person show a larger and almost entirely permanent price impact
     than broad markets (Kyle's λ in log-odds, t = 10.88). See Bartlett & O'Hara, Table 2; VERIFIED.
   - When order flow in single-name markets is one-sided, its direction predicts settlement. In the top-VPIN
     quintile, buckets with YES-directed flow settle YES 35.9% of the time and buckets with NO-directed flow 22.0%
     (t = 12.44). VERIFIED.
   - On Polymarket, Gómez-Cram et al. classify about 3% of accounts as "skilled". Their likely-insider set is
     967 of about 1.72M accounts, with about 0.2% of volume and 1.3% of profits, and insider activity appears in
     about 6% of markets. PLAUSIBLE: I saw these only through Macey & Enriques's page-cited summary, not the paper.
2. **The traders you would most want to copy are the ones you cannot identify in advance.**
   - Suspected insiders are mostly one-shot accounts: created days before the event and dormant after resolution
     (Gómez-Cram et al., via Macey & Enriques and Nechepurenko; PLAUSIBLE).
   - So no track record exists to select on. Track-record tests such as sign randomisation exclude these accounts
     by design (Nechepurenko 2605.02287 §3; VERIFIED that the paper says so).
   - Mitts & Ofir's broad anomaly pool beats price-implied winning odds by only **0.69 pp** (74.35% implied
     against 75.03% observed). Only the top score tiers make money. PLAUSIBLE: reported by Macey & Enriques from
     the full text.
3. **Skill persistence exists, but followers keep little of it.**
   - Coval, Hirshleifer & Shumway: copying the next-day trades of previously successful retail investors earns
     about **5 bp a day** in a long-short portfolio, before costs (t about 2). Trades are known from the
     day after; this is not a real-time follow. VERIFIED, 2005 working paper §D.
   - Barber, Lee, Liu & Odean: among roughly 360,000 Taiwanese day traders a year, only the top roughly 1,000
     (**under 1%**) predictably earn positive returns net of fees in the next year. VERIFIED, 2011 working paper.
   - Gómez-Cram et al.: 44% of "skilled" Polymarket accounts stay skilled on a *random* split of events. That is a
     cross-sectional split, not a time split, so it does not show copyability (PLAUSIBLE, via Nechepurenko).
   - Copycat mutual funds that buy disclosed holdings match the underlying funds only **after** the funds'
     expenses. Before expenses they trail by 42 bp over six months (VERIFIED, NBER w8653).
4. **Copying always carries an execution penalty. In liquid markets it absorbs most of the signal.**
   - Liquid Betfair soccer markets price goals within seconds and do not drift afterwards (Croxson & Reade;
     VERIFIED).
   - In thinner Kalshi NBA markets prices move only 0.64 for 1 at first. The remaining drift is predictable, but
     a strategy that buys at the ask and exits at the bid five minutes later has **negative mean returns
     (−0.0036 to −0.0120 in the table's units)**. Midpoint returns are positive (+0.0037 to +0.0087)
     (Angelini & De Angelis, Table 11; VERIFIED).
   - On a bonding curve, an immediate copier always overpays: the "imitation penalty" theorem. In memecoins,
     wallets whose own returns were +4% to +9% gave copiers −6% to −8% under three of the four baseline models
     (Luo et al. Fig. 8; VERIFIED in text, bar values read from the figure). The Polymarket order book is not a
     bonding curve, but walking a book that a large taker has just emptied is the same mechanism (PLAUSIBLE).
   - Large size is not information. Intrade's largest directional trader lost about $6.9M while apparently
     holding prices up on purpose (Rothschild & Sethi; VERIFIED).

**Legal position (VERIFIED in the primary documents):**

- The CFTC treats trading event contracts on misappropriated material nonpublic information as fraud under CEA
  §6(c)(1) and Rule 180.1. Separately, it applies the "Eddie Murphy" rule to misuse of government information.
  Its first such case (2026-04-23) was a Polymarket trader on the Maduro contract.
- CRS states that Rule 180.1 is not a parity-of-information rule.
- Kalshi's rules are broader than that. Polymarket US's rules follow the misappropriation theory, per Bartlett &
  O'Hara.
- No primary source I found addresses the liability of someone who copies a publicly visible on-chain trade
  (UNSUPPORTED either way). Per CONTEXT.md, we must not label any wallet an insider.

**Implication for the five-of-five screen (my calculation; PLAUSIBLE):**

- A calibrated bettor who only buys at p = 0.85 wins five of five with probability 0.85⁵ ≈ 0.44, and has zero
  expected edge.
- A "won all five" filter therefore mostly selects favourite buyers and lucky wallets.
- Any test must condition on entry prices (sign randomisation or a price-implied benchmark), control the false
  discovery rate across wallets, and use time-ordered selection.

## 2. Papers and documents selected (ranked by usefulness to this project)

| # | Item | Status / venue | Full text read? | Relevance | Families |
|---|---|---|---|---|---|
| 1 | Bartlett & O'Hara, "Adverse Selection in Prediction Markets: Evidence from Kalshi" | WP; SSRN 6615739; NBER conference PDF, version 2026-07-02 | **Yes**: main text and tables | core | A, D, H |
| 2 | Angelini & De Angelis, "When Do Markets Fully Process Public Information? Evidence from Real-Time Prediction Markets" | arXiv 2606.07811v1 (preprint) | **Yes**: main text and App. B | core | G, F, A |
| 3 | Rothschild & Sethi, "Trading Strategies and Market Microstructure: Evidence from a Prediction Market" | *Journal of Prediction Markets* 10(1), 2016 | **Yes**: Nov 2015 WP | core | A, D, B |
| 4 | Coval, Hirshleifer & Shumway, "Can Individual Investors Beat the Market?" | *RAPS* 11(3):552–579 (2021) | **Yes**: Sept 2005 WP, not the journal version | core | A |
| 5 | Barber, Lee, Liu & Odean, "The cross-section of speculator skill: Evidence from day trading" | *J. Financial Markets* 18:1–24 (2014) | **Yes**: May 2011 WP (intro and results) | core | A |
| 6 | Barras, Scaillet & Wermers, "False Discoveries in Mutual Fund Performance: Measuring Luck in Estimated Alphas" | *J. Finance* 65(1):179–216 (2010) | Partly: Nov 2005 WP | core (method) | A |
| 7 | Croxson & Reade, "Information and Efficiency: Goal Arrival in Soccer Betting" | *Economic Journal* 124(575):62–91 | Partly: Jan 2011 DP 11-01 | core | G, H |
| 8 | Luo, Feng, Xu & Liu, "Resisting Manipulative Bots in Meme Coin Copy Trading…" | arXiv 2601.08641v3 (preprint) | Partly: §§1–5, App. A.6 | core (copy-execution mechanism) | A |
| 9 | Gómez-Cram, Guo, Jensen & Kung, "Prediction Market Accuracy: Crowd Wisdom or Informed Minority?" | SSRN 6617059 (WP) | **No**: abstract plus two papers' summaries of the full text | core (unverified detail) | A, D |
| 10 | Apesteguia, Oechssler & Weidenholzer, "Copy Trading" | *Management Science* 66(12):5608–5622 (2020) | **Yes**: Sept 2019 accepted version | supporting | A |
| 11 | Brown, "Evidence of in-play insider trading on a UK betting exchange" | *Applied Economics* 44(9):1169–1175 (2012) | **Yes** (published version) | supporting | G, A |
| 12 | Smith, Paton & Vaughan Williams, "Market Efficiency in Person-to-Person Betting" (Shin z) | *Economica* 73(292):673–689 (2006) | Partly: postprint | supporting | A, E |
| 13 | Frank (Myers), Poterba, Shackelford & Shoven, "Copycat Funds…" | NBER w8653 (2001); *J. Law & Econ.* (2004) | Partly: NBER WP §4 | supporting | A |
| 14 | Macey & Enriques, "Different Markets, Different Regulatory Priorities: Insider Trading, Manipulation, and Corruption-Prone Event Contracts in Prediction Markets" | ECGI Law WP 955/2026; SSRN 7323118 | Partly: §§III.B–D, V–VI | core (legal) | other (legal) |
| 15 | CRS Legal Sidebar LSB11406, "Prediction Markets and Insider Trading Law" (J. B. Sykes) | Official (CRS), updated 2026-04-03 | **Yes** | core (legal) | other (legal) |
| 16 | CFTC Division of Enforcement, "Advisory on Enforcement Authority over Event Contracts" (Release 9185-26) | Official, 2026-02-25 | **Yes** | core (legal) | other (legal) |
| 17 | CFTC Release 9217-26, "CFTC Charges U.S. Service Member with Insider Trading in Nicolás Maduro-Related Event Contracts" | Official, 2026-04-23 | Release only (via WebFetch); complaint not read | core (legal) | other (legal) |
| 18 | CFTC NPRM, "Prediction Markets; Public Interest Determinations", 91 FR 35806, RIN 3038-AF65 | Official proposed rule, 2026-06-12 | Partly: the insider-trading passages | supporting (legal) | other (legal) |
| 19 | Della Vedova, "Detecting Informed Trading in Prediction Markets: An Orthogonality Test" | SSRN 6567238 (WP) | **No**: abstract only | supporting (unverified) | A |
| 20 | Oliphant, "The Return to Imitation: Evidence from Copy Trading on Polymarket" | SSRN 6670318 (WP) | **No**: abstract only | supporting (unverified) | A |

Families: A wallet-following, B complete-set arb, C logical arb, D liquidity provision, E favorite–longshot,
F mean reversion, G lead–lag, H near-resolution.

## 3. Paper-by-paper notes

### A. Informed trading in prediction markets and betting exchanges

#### 3.1 Bartlett & O'Hara (2026), "Adverse Selection in Prediction Markets: Evidence from Kalshi"

- **Metadata (VERIFIED):**
  - Robert Bartlett (Stanford Law and GSB); Maureen O'Hara (Cornell Johnson).
  - SSRN 6615739 (DOI 10.2139/ssrn.6615739; Crossref created 2026-04-21). I read the PDF at
    conference.nber.org/conf_papers/f243677.pdf, dated "This version: July 2, 2026 (first version: April 16, 2026)".
    Working paper, not peer-reviewed.
- **Data:**
  - Kalshi REST API: trades, markets and hourly candlesticks, July 2021 to 2026-03-11.
  - Analysis sample: 41.6M trades on 478,167 markets, split into 15,516 single-name and 462,651 broad-based
    markets (Table 1).
  - Every trade discloses the taker side. Quotes come only from hourly candles, available for about 7% of
    trades (35.6% of single-name trades).
- **Mechanism:**
  - Adverse selection is higher where information is concentrated (single company or person).
  - Makers survive anyway because takers overbuy YES, a "behavioural surplus": single-name markets settle YES
    30.9% of the time while takers buy YES in 60.2% of trades.
- **Key findings (VERIFIED):**
  - Kyle's λ in log-odds is higher for single-name markets (β = 0.0001, t = 10.88). The Glosten–Harris
    permanent component is significant (t = 7.46 and 9.58), so the impact is almost all permanent (Table 2).
  - Maker P&L per contract: +1.91¢ single-name, +0.82¢ broad-based. Maker win rate 63.4% against 53.9%. Average
    win 16.34¢, average loss −23.13¢ on single-name (Tables 5–6).
  - Trailing VPIN ($500 buckets, 20-bucket window, interior prices 30–70¢) predicts maker losses in single-name
    markets (OLS t = −2.42; logit z = 3.58) but not in broad-based ones (t = 0.56) (Table 10).
    - Top quintile in single-name markets: maker P&L −$12 per bucket and a 51.7% loss rate, against +$41 to +$46
      in Q1–Q4 (Table 9).
    - Direction of one-sided flow in the top quintile: YES-directed settles YES 35.9%, NO-directed 22.0%
      (t = 12.44). In broad-based markets the two rates are 50.0% and 50.2%.
  - One-sided strategies held to settlement on 14,988 single-name markets, gross of fees (Table 8):
    - Offer-only (selling YES): +$9.91M in total, but the per-market mean/SD is only 0.019.
    - Bid-only: −$5.32M.
  - Polymarket on-chain check (footnote 18): on 97,766 crypto price markets, makers carried 95% of gross volume
    to settlement in January–March 2026.
- **Costs and execution:**
  - Kalshi fees are ignored explicitly (§5.1 footnote: taker fees of 0.07–1.75¢ per contract, some maker fees
    from April 2025).
  - Hourly-candle midpoints are stale. The authors show the spread result depends on quote freshness (Table 4).
- **Dependence:** cross-sectional regressions use HC1 errors. VPIN regressions cluster by market. No
  calendar-time or event clustering, and many Kalshi markets come in correlated bracket families.
- **Tradable prospectively?** Partly.
  - VPIN is built only from information available at bucket t−1, so it is a real-time signal.
  - But the paper does not test a taker strategy that follows one-sided flow at ask prices after fees.
  - The YES-optimism means a follower must buy the side the flow points to at a price below its settlement
    rate. That is not shown.
  - The Polymarket analogue cannot use quotes (no historical book).
- **Replication needs:**
  - Polymarket version: taker-signed flow from `/v2/trades` (trade direction per Dubach, see sibling sweep).
  - Market classification into single-name and broad.
  - Executable-price backtest of "follow one-sided flow" at the next trade or current book, with current fees.
  - Event-clustered inference.

#### 3.2 Rothschild & Sethi (2016), "Trading Strategies and Market Microstructure: Evidence from a Prediction Market"

- **Metadata (VERIFIED):**
  - David M. Rothschild (Microsoft Research); Rajiv Sethi (Barnard/Columbia, SFI).
  - *The Journal of Prediction Markets* 10(1) (DOI 10.5750/jpm.v10i1.1179; Crossref issued 2016-09-20).
    SSRN 2322420 (2013).
  - I read the 2015-11-22 version (researchdmr.com PDF). The 2013 draft covered only the last two weeks.
- **Data:** every transaction in Intrade's 2012 presidential-winner market, 2010-11-16 to 2012-11-07. About
  287,000 trades, 12.9M contracts and 6,300 accounts, with account IDs and the aggressor side.
- **Key findings (VERIFIED):**
  - **87% of traders (32% of volume) never change direction.** The 40 arbitrageurs (median holding under 10
    minutes) are 1% of traders and 16% of volume. Only 6% of accounts and 15% of volume are "unbiased" traders
    willing to go either way (Table 2).
  - The largest directional account ("Trader B", 2.06M contracts) **lost $6,882,186** while holding up the
    Romney price. Its resting orders created a "firewall". The trader spent about $375,000 to hold prices
    during 90 minutes on election night. When the orders were pulled, prices converged to Betfair (§6,
    Table 1, Fig. 5).
  - The most profitable directional trader made $867,059. The authors call both bets "risky bets that could
    have gone either way" (§3.5).
- **Costs:** Intrade margin rules are modelled (cash equal to worst-case loss, with margin linking). Fees are
  not discussed.
- **Dependence:** n/a. This is a descriptive taxonomy of one market.
- **Tradable?** No strategy is tested. Lesson for following: the biggest and most persistent directional
  wallet was the worst one to copy, and its size was a manipulation signal, not an information signal.
- **Replication needs:** a Polymarket taxonomy (direction-switching, holding duration, aggression) on
  `/v2/trades?user=` histories. Measure the profitability of "unbiased" against "unidirectional" wallets out of
  sample.

#### 3.3 Gómez-Cram, Guo, Jensen & Kung (2026), "Prediction Market Accuracy: Crowd Wisdom or Informed Minority?"

- **Metadata (VERIFIED, Crossref):** SSRN 6617059 (created 2026-04-24). Not read: SSRN returns 403, I found no
  author-hosted PDF, and an NBER search found nothing.
- **What I can state:**
  - The abstract (VERIFIED) says that about 3% of accounts generate the bulk of price discovery and react to
    news as it arrives.
  - The rest (PLAUSIBLE) comes from two papers that read the full text:
    - **Nechepurenko (arXiv 2605.02287v2 §§1–3):**
      - Sample: 1.72M accounts, 210,322 markets and $13.76B, 2023–2025.
      - Method: sign randomisation of buy/sell direction **at the event level**, 10,000 draws, for accounts
        with at least 10 events.
      - Classification: p < 0.05 "skilled winners" (54,477, 3.14%); p > 0.95 "unskilled losers" (6.4%);
        "lucky winners" 29.0%; "unlucky losers" 61.4%; market makers 0.1%.
      - **44% of skilled accounts stay skilled on a randomly held-out set of events.**
      - Separately, a lifecycle heuristic flags 1,950 accounts as insiders.
    - **Macey & Enriques (§III.B):** "967 accounts out of roughly 1.72 million", 0.2% of volume, 1.3% of profits,
      insider activity in 6% of markets. Flagged accounts were created days before the event and went dormant
      after it.
- **Discrepancy:** 1,950 against 967 flagged insiders. These are probably different versions (the paper was
  revised 2026-04-25 and redeposited 2026-06-25 per the sibling note). Not resolved.
- **Multiple-testing observation (my reasoning; PLAUSIBLE):**
  - Under a global null of no skill, a per-account test at p < 0.05 flags about 5% of tested accounts by chance.
  - If 3.14% is a share of *tested* accounts, the right tail is no fuller than chance. The 44% persistence
    (against about 5% expected under the null) would then be the main evidence of skill.
  - The denominator is ambiguous in the summaries. 54,477 / 0.0314 ≈ 1.73M, the whole population, so the share
    among tested accounts is higher.
  - An FDR estimate in the style of Barras et al. (§3.7) is needed before anyone uses these flags.
- **Tradable?** Not shown. A random split of events is not a time split, the categories are pooled (sports 35%,
  politics 36% and crypto 19% of volume, per Nechepurenko quoting their Table A.2), and there is no
  latency-adjusted copy test.

#### 3.4 Brown (2012), "Evidence of in-play insider trading on a UK betting exchange"

- **Metadata (VERIFIED):** Alasdair Brown (SOAS at the time). *Applied Economics* 44(9):1169–1175, DOI
  10.1080/00036846.2010.537644, online 2011-02-15. I read the published PDF from the UEA repository.
- **Data:**
  - Betfair (Fracsoft) second-level quotes for **one match**, the 2008 Wimbledon men's final (36,752 seconds).
  - Four contracts.
  - High-information periods are the two tie-breaks (456 s and 816 s), dated from video.
- **Findings (VERIFIED):**
  - Back–lay spreads widen in tie-breaks. For Nadal-to-win the mean spread is 0.0098, against 0.0061 during
    play (Table 1).
  - In an OLS with lagged spread and depth, the tie-break dummy is positive and highly significant for all four
    contracts. Post-tie-break spreads fall (Table 2).
  - Interpretation: some bettors see the play before the TV picture. Betfair's 1–5 s in-play bet delay is
    "insufficient" or perceived to be.
- **Limits:** one match. The inference is indirect, from liquidity providers' behaviour. There are no
  trader-level data. The lagged dependent variable soaks up autocorrelation, but the errors are not robust.
- **Tradable?** Only for whoever has the faster feed. The paper argues the edge needs algorithmic, seconds-level
  execution. A follower who reacts to the courtsider's trade is on the wrong side of that latency.
- **Relevance:** Polymarket sports markets carry `secondsDelay` (CONTEXT.md), the same tool as Betfair's in-play
  delay.

#### 3.5 Smith, Paton & Vaughan Williams (2006), "Market Efficiency in Person-to-Person Betting" (Shin model)

- **Metadata (VERIFIED):** *Economica* 73(292):673–689, DOI 10.1111/j.1468-0335.2006.00518.x. I read the NTU
  postprint.
- **Data:** 700 UK horse races in 2002 (from 799; turnover filter of £2,000 on Betfair by 10:30). Mean bookmaker
  odds, best ("outlier") bookmaker odds and Betfair prices for the same races.
- **Findings (VERIFIED, Table 3):**
  - Shin's insider-share estimate z: 2.17% (mean bookmaker odds), 1.19% (best odds) and **0.90% (Betfair)**,
    all significant at 1%. Betfair is significantly lower (Table 8).
  - z falls from low-information to high-information race classes (Tables 4–7).
  - They quote Shin (1993) at z = 0.025 on 178 races.
- **Critiques (abstracts only; PLAUSIBLE):**
  - Marginson (2010, *Southern Economic Journal* 76(4), DOI 10.4284/sej.2010.76.4.932) argues that Shin's z
    assumes bookmakers. He finds "known loser" lay-side insider trading "potentially commonplace" on exchanges.
  - A search snippet says Coleman (2007, *Applied Financial Economics*, DOI 10.1080/09603100600675565) finds a
    similar z in the Tote market, where z should be zero. That suggests z measures more than insider trading.
    Not read.
- **Tradable?** No. These are market-level bias estimates.
- **Relevance:** small and contested. On exchanges, implied "insider" turnover is about 1%, so it says little
  about wallet-level signals.

### B. Detection latency: how fast prices absorb news and informed flow

#### 3.6 Angelini & De Angelis (2026), "When Do Markets Fully Process Public Information? Evidence from Real-Time Prediction Markets"

- **Metadata (VERIFIED):** Giovanni Angelini; Luca De Angelis (University of Bologna). arXiv:2606.07811v1
  (submitted 2026-06-05; dated 2026-06-09). Preprint.
- **Data:**
  - Kalshi NBA winner contracts, 2025-04-15 to 2026-05-25: 1,438 games, 2,876 contracts and 409,512
    contract-minutes.
  - Best bid and ask, volume and open interest each minute, merged with play-by-play (Table 1).
- **Method:** the benchmark win probability is estimated out of sample by five-fold cross-fitting at game level.
  Errors are clustered by game.
- **Findings (VERIFIED):**
  - A one-minute change in the benchmark probability moves the midpoint only about **0.64 for 1**. It is 0.509
    in clutch time (App. C, Table 12).
  - The gap predicts drift. A 10 pp gap predicts 2.0 pp (raw) and 4.6 pp (net of benchmark) at 5 minutes
    (Table 6).
  - Underreaction is worse when salient events happen in illiquid markets.
- **Executable test (VERIFIED, App. B Table 11):**
  - Rule: buy YES at the ask when the gap is positive, and exit at the bid after 5 minutes.
  - Result, in the table's units (the table does not state them; probably dollars per $1 contract):
    **−0.0092 to −0.0120** on all observations and −0.0036 to −0.0078 on high-quality quotes.
  - Gap thresholds run from 0 to 200 bp. Larger gaps give less negative results, but none turns positive.
  - Midpoint returns are positive (+0.0037 to +0.0087). The spread absorbs the predictability.
  - Fees are not mentioned. The executable test uses quotes only.
- **Tradable?** No, at the tested 1-minute frequency with spreads.
- **Relevance:** a follower's signal (a big trade or a news event) arrives with the same structure. Even
  predictable drift may be uneconomic once the follower crosses the spread.

#### 3.7 Croxson & Reade (2014), "Information and Efficiency: Goal Arrival in Soccer Betting"

- **Metadata (VERIFIED):** Karen Croxson (Oxford); J. James Reade. *Economic Journal* 124(575):62–91 (Crossref
  issued 2013-06-03). DOI 10.1111/ecoj.12033. I read Birmingham DP 11-01 (2011-01-21).
- **Data:** second-by-second Betfair order-book snapshots for **1,206 matches** (Premiership, Champions League,
  Euro 2008 and others), averaging over $6M matched per match.
- **Findings (VERIFIED, intro and §§3–4):**
  - On average a goal raises the scorer's win probability by 22 points.
  - 160 goals fall within five minutes of half-time, 53 of them in the final minute. Half-time prices do not
    drift after these goals: "prices update swiftly and fully".
  - The paper contrasts Gil & Levitt (2007): Intrade World Cup soccer had about 75 traders per game and drifted
    for 10–15 minutes after goals.
- **Lesson:** speed depends on liquidity. In deep exchange markets, public news is priced in seconds. In thin
  markets drift can persist, but see §3.6 on whether it pays.
- **Tradable?** No residual drift to trade in the deep market.

*Related, not read (PLAUSIBLE, from search snippets):* Rogers, Skinner & Zechman, "Run EDGAR Run: SEC
Dissemination in a High-Frequency World", *J. Accounting Research* 55(2):459–505 (2017), DOI
10.1111/1475-679x.12167.

- Paying SEC feed subscribers saw Form 4 insider filings before the public site. The mean posting lag was 40 s.
- Prices start reacting about 30 s *before* public posting.
- It is the canonical "followers of disclosed insider trades are seconds behind" result. I could not access the
  full text (SSRN only).

### C. Skill persistence and multiple testing

#### 3.8 Coval, Hirshleifer & Shumway, "Can Individual Investors Beat the Market?"

- **Metadata (VERIFIED):** *Review of Asset Pricing Studies* 11(3):552–579 (2021), DOI 10.1093/rapstu/raab017.
  I read the **September 2005 working paper** (HBS 04-025; SSRN 364000) from sites.uci.edu.
- **Data:** a US discount broker, January 1990 to November 1996: 115,856 accounts, of which 16,668 have at least
  25 trades.
- **Findings (VERIFIED, 2005 WP):**
  - The correlation of risk-adjusted performance across periods is about 10%. The top first-half decile beats
    the bottom by about 8% a year.
  - Real-time mimicking strategy (§D, Table 6):
    - Rank accounts using only past data; at least 25 trades; quintiles; at least 25 stocks a side.
    - Hold the stocks bought in the last 5 days, value-weighted, starting **the day after** the trade.
    - 4-factor alpha **5.1 bp a day** (significant at 5%, not at 1%). Daily formation gives 6.8 bp. It is
      gone at a one-month horizon.
    - With decile cut-offs, t = 1.74. Smallest third of CRSP stocks excluded.
  - The journal abstract (PLAUSIBLE, search snippet) gives about 6% a year for the top decile, smaller than the
    WP's 8%.
- **Costs:** none deducted from the strategy. The authors note that measuring returns from the day after
  removes same-day bid–ask effects.
- **Dependence:** daily long-short time-series alpha, so cross-sectional dependence is handled by the portfolio
  approach.
- **Tradable prospectively?** Marginal. It needs broker trade data in real time. About 5 bp a day before
  turnover costs on a high-turnover portfolio, in 1990s spreads.

#### 3.9 Barber, Lee, Liu & Odean (2014), "The cross-section of speculator skill: Evidence from day trading"

- **Metadata (VERIFIED):** *J. Financial Markets* 18:1–24 (March 2014), DOI 10.1016/j.finmar.2013.05.006. I read
  the **May 2011 WP** (Odean's site). The eScholarship copy of the published version returned 403.
- **Data:** every Taiwan Stock Exchange day trade, 1992–2006. About 360,000 day traders a year.
- **Findings (VERIFIED, 2011 WP):**
  - Sort on year-y returns and measure year y+1. The top 500 earn 49.5 bp a day gross and **28.1 bp net** on
    the day-trading portfolio. Prior-year losers earn −17.5 gross and −34.2 net.
  - "Only the 1,000 most profitable day traders (less than 1 percent…) go on to earn reliably positive abnormal
    returns net of trading costs."
  - About 15% earn positive net abnormal returns in a given year, "some… expected by sheer luck".
  - Top traders' combined portfolio: +2 bp a day net.
  - The published abstract (PLAUSIBLE, snippet) gives 37.9 and −28.9 bp.
- **Costs:** commissions plus the 30 bp transaction tax are included.
- **Tradable for a follower?** Not tested. Skilled day traders use aggressive orders (71%). Their edge is
  same-day and could not be copied from public data.

#### 3.10 Barras, Scaillet & Wermers (2010), "False Discoveries in Mutual Fund Performance: Measuring Luck in Estimated Alphas"

- **Metadata (VERIFIED):** *J. Finance* 65(1):179–216, DOI 10.1111/j.1540-6261.2009.01527.x. I read the November
  2005 WP (ULB CEB WP 05/014).
- **Method:** estimate π₀, the share of zero-alpha funds, from the p-value distribution (Storey 2002). Bootstrap
  the p-values. Report the FDR among significant funds in each tail.
- **Findings (VERIFIED, 2005 WP):**
  - About 20% of funds truly have negative alpha.
  - Only **1.9%** have truly positive alpha, concentrated in the extreme right tail.
  - Among the "best" funds the FDR is above 50% for the full universe. The 2010 journal numbers may differ;
    not checked.
- **Use here:** the template for any screen over 10⁵–10⁶ wallets. Report π₀, the FDR among selected wallets and
  the expected number of lucky selections, not just the count of "significant" wallets. Event-level
  dependence (one event, many wallets) needs a block or event-clustered bootstrap.

### D. Copy trading and following disclosed trades

#### 3.11 Apesteguia, Oechssler & Weidenholzer (2020), "Copy Trading"

- **Metadata (VERIFIED):** *Management Science* 66(12):5608–5622, DOI 10.1287/mnsc.2019.3508. I read the
  2019-09-17 accepted version (Essex repository).
- **Design:** laboratory experiment with 176 Heidelberg students (80 BASELINE, 48 INFO, 48 COPY).
  - Assets follow a binomial tree with tail risk.
  - INFO shows a ranking of prior subjects by realised payoff. COPY also allows one-click copying.
- **Findings (VERIFIED):**
  - In COPY, **35% copy, and 88% of copiers copy someone who chose the riskiest asset.** Non-copiers also shift
    to riskier assets.
  - More risk-averse subjects (from elicited lotteries) are *more* likely to copy.
  - Field description (May 2018 scrape): only 1.13–8.71% of ranked users are copied. The top 5% of leaders hold
    61.1% (ZuluTrade) to 92.8% (eToro) of copy relationships (§3).
- **Mechanism for us:** ranking by realised P&L selects lucky risk-takers. Copiers adopt their risk.
- **Tradable?** n/a (lab). Leaderboards such as Polymarket's `/v2/leaderboard` and `biggest-winners` are the
  same ranking.

#### 3.12 Luo, Feng, Xu & Liu (2026), "Resisting Manipulative Bots in Meme Coin Copy Trading: A Multi-Agent Approach with Chain-of-Thought Reasoning"

- **Metadata (VERIFIED):** UCL / NTU authors. arXiv:2601.08641v3 (v1 2026-01-13; v3 2026-02-05). CC-BY. Preprint.
- **Data:** wallet-level data on **6,000 pump.fun memecoins** (Solana, via Flipside). Temporal 70/15/15
  train/validation/test split.
- **Findings (VERIFIED in text):**
  - Copied "KOL" wallets often coordinate bundle, sniper and bump bots to manufacture apparent smart money and
    exit into copiers (§4).
  - **Theorem 2 (imitation penalty):** on the bonding curve, an immediate one-to-one copier overpays on every
    replicated buy, so the copier's return is strictly below the leader's.
  - On the test set, statistic-driven selectors (Lasso, NN, XGBoost) pick wallets with positive returns, but
    "copier returns remain negative". Only their LLM multi-agent system gives copiers a positive mean: about
    **+3%** against the leaders' +14%.
  - Bar values from Fig. 8 (PLAUSIBLE, read from the figure): leader/copier +9.2%/−5.8% (Lasso), +6.1%/−7.8%
    (NN), +4.2%/−8.3% (XGBoost).
- **Costs:** the 1% pump.fun fee and bonding-curve impact are modelled. The copier is assumed to execute right
  after the leader.
- **Caveats:** a single model family, a short sample, and the authors' own system as the winner. Treat +3% as
  in-sample to the research design.
- **Relevance:** the clearest formal statement that copying a visible wallet costs the copier the leader's
  price impact. On Polymarket the analogue is depth consumed by the leader's taker order, plus
  detection-to-fill latency.

#### 3.13 Frank (Myers), Poterba, Shackelford & Shoven, "Copycat Funds: Information Disclosure Regulation and the Returns to Active Management in the Mutual Fund Industry"

- **Metadata (VERIFIED):** NBER WP 8653 (December 2001; author listed as Mary Margaret Myers). Published in
  *J. Law & Economics* (2004), DOI 10.1086/422982, as Frank, Poterba, Shackelford & Shoven.
- **Design:** buy each actively managed fund's disclosed holdings at disclosure and hold for six months. Two
  samples of 1992–1999 equity funds: high-expense funds, and a broader set of 847 observations.
- **Findings (VERIFIED, §4):**
  - High-expense sample: before expenses the funds beat their copycats by **42 bp cumulative over six months**
    (significant). After the funds' expenses, copycats lead by 24 bp (not significant).
  - Tracking correlation falls from 0.98 to 0.96 over the six months.
- **Lesson:** disclosed positions keep only part of their value. Followers "win" mainly by not paying the
  leader's costs, not by capturing alpha.
- **Tradable?** Yes in principle, but the benchmark is the active fund, not the market.

### E. Legal and ethical limits (US, 2025–2026)

#### 3.14 CRS Legal Sidebar LSB11406, "Prediction Markets and Insider Trading Law" (Jay B. Sykes)

- **Read in full; VERIFIED.** Version 3, updated 2026-04-03.
- **Key points:**
  - CFTC Rule 180.1 (Dodd-Frank §753) is "modeled on" Rule 10b-5. It reaches **misappropriation** (breach of a
    duty to the source of the information).
  - The CFTC has said Rule 180.1 is not a parity-of-information regime. Trading on "lawfully obtained" material
    nonpublic information is not, by itself, a violation.
  - CEA §4c(a)(3)–(4) (the STOCK Act) bars federal officials from trading on nonpublic government information,
    and bars anyone from knowingly using information such officials impart.
  - Title 18 fraud is limited by *Blaszczak* (agency information is not "property") and *Chastain*
    (information must have commercial value to its owner).
  - It lists the 2026 bills: H.R. 7004, H.R. 8076, S. 4017, S. 4060, S. 4188, H.R. 7840, the BETS OFF Act and
    the STOP Corrupt Bets Act.
  - It notes the Polymarket "offshore exchange" Maduro and Iran episodes.
- **For a follower:** I found nothing on whether copying a publicly visible trade could expose the copier. Under
  the misappropriation framework there is no tip and no duty. This is my reading; UNSUPPORTED by any source.

#### 3.15 CFTC Enforcement Advisory (Release 9185-26, 2026-02-25)

- **Read in full; VERIFIED** (cftc.gov/media/13351).
- **The two Kalshi cases:**
  - A candidate traded on his own race: $2,246.36 penalty and a 5-year suspension.
  - A YouTube channel editor traded on unreleased video content: $20,397.58 and a 2-year suspension.
- **Theories:** the CFTC says both "potentially" violated §6(c)(1) and Rule 180.1(a)(1) and (3). For the
  candidate it uses a "scheme or artifice to defraud" theory, not misappropriation. CRS notes that this theory
  was left unexplained.
- It lists the other prohibited practices: wash and pre-arranged trading, disruptive trading, and manipulation.
- It states that DCMs must keep audit trails and run surveillance.

#### 3.16 CFTC Release 9217-26 (2026-04-23): *CFTC v. Van Dyke* (S.D.N.Y.)

- **Release read via WebFetch; VERIFIED. Complaint not read.**
- **Allegations:**
  - An active-duty US Army service member used classified information about the operation to capture Maduro.
  - From 2025-12-30 to 2026-01-02 he bought more than 436,000 "Yes" shares of "Maduro Out by January 31,
    2026?" on Polymarket, under the handle "Burdensome-Mix", for more than $404,000 profit.
- "**First time the CFTC has charged insider trading involving event contracts**", and the first use of the
  "Eddie Murphy Rule". A parallel SDNY criminal indictment was filed.
- The allegations are unproven.
- Consistency check (my arithmetic): 436,000 × (1 − 0.074) ≈ $404k matches the release. Mitts & Ofir, via
  Macey & Enriques, report $485,346 on $38,533 at risk. That probably includes linked accounts (PLAUSIBLE).

#### 3.17 CFTC NPRM, "Prediction Markets; Public Interest Determinations" (91 FR 35806, 2026-06-12)

- **Partly read (govinfo HTML); VERIFIED.**
- Proposed amendments to 17 CFR Part 40, RIN 3038-AF65. Comments were due 2026-07-27.
- Proposed listing factors include "particular risks of information leakage or exploitation of material
  non-public information by insiders". Mitigants include banning categories of likely insiders, surveillance and
  customer-ID policy.
- It cites the Van Dyke case as an example from an "unregistered platform".
- Status after the comment period: not checked.

#### 3.18 Macey & Enriques (2026), "Different Markets, Different Regulatory Priorities…"

- **Metadata (VERIFIED):** Jonathan R. Macey (Yale, ECGI); Luca Enriques (Bocconi, EBI, ECGI). ECGI Law Working
  Paper 955/2026, August 2026 (DOI 10.67929/ecgi-law-955-2026). SSRN 7323118. I read §§III.B–D and V–VI.
- **Argument:**
  - Informed trading improves the product, so prediction markets should **not** adopt a possession or parity
    rule.
  - Rule 180.1 should stay a misappropriation rule.
  - Exclude "corruption-prone event contracts" (outcomes an identifiable person can influence) at listing.
  - Remove information inequality as a stand-alone listing factor, which challenges the NPRM.
- **Evidence they cite:** Gómez-Cram et al.'s and Mitts & Ofir's figures (see §§3.3 and 1).
  - They note that insider bets on the Maduro contract "did not have a significant effect on the prices".
  - So a well-timed follower would not necessarily have paid much more, if the wallet had been identified in
    time (PLAUSIBLE).
- *Related, abstract only:* Turk, Holden & Haugh, "Optimal Insider Trading in Prediction Markets" (SSRN 7259584,
  2026-08-11). They argue that existing law gives "ample legal mechanisms" and that some room for inside
  information helps prices.

### F. Abstract-only Polymarket items in the main table

- **Della Vedova, "Detecting Informed Trading in Prediction Markets: An Orthogonality Test"** (SSRN 6567238,
  2026-04-20). Abstract (VERIFIED):
  - 222M resolved trades. Accuracy and execution quality are orthogonal for the uninformed but co-move for the
    informed.
  - Flags 6,032 of 450,048 wallets, worth about $150M.
  - Wallets are 10.5 pp more accurate in "sealed-ballot" markets.
  - Agreement with the behavioural heuristic: κ = 0.007 ("heuristics identify lucky traders").
  - The method, multiple-testing control and out-of-sample design are unknown.
- **Oliphant, "The Return to Imitation: Evidence from Copy Trading on Polymarket"** (SSRN 6670318, 2026-04-28).
  Abstract (VERIFIED): a follower's copy trades beat their own non-copy trades in the same market by 1.62 pp.
  - This is a within-follower comparison, not a benchmark against prices. It does not show that copying is
    profitable.

## 4. Implications for this project's wallet-following test

1. **Selection must condition on price.**
   - Use event-level sign randomisation (Gómez-Cram), a price-implied winning benchmark (Mitts & Ofir) or a
     Brier/log-score gain over the entry price.
   - Raw win counts reward favourite-buying (§1). Event-level randomisation matters because one event creates
     correlated wins across its markets.
2. **Control the false discovery rate across wallets** (Barras et al.).
   - Report π₀ and the expected number of lucky wallets among those selected.
   - With about 10⁵ eligible wallets, p < 0.05 alone gives about 5,000 false positives under the null.
3. **Time-ordered out-of-sample, not random event splits.** Selection may use only fills and resolutions
   timestamped before the decision (CONTEXT.md no-look-ahead rule).
4. **Model execution at follower latency.**
   - Enter at the first fills after the leader's fill plus a delay (for example 5 s, 30 s, 2 min, 10 min). Use
     the trade tape as a proxy, and say that it is not an executable price.
   - Add current taker fees, `fee = shares × rate × p(1−p)`.
   - Report the leader-minus-copier "imitation penalty" separately.
   - Bartlett & O'Hara and Angelini & De Angelis both show that the midpoint signal can vanish at the
     executable price.
5. **Segment by contract type.**
   - Informed flow concentrates in single-name, corporate and geopolitical markets (Bartlett & O'Hara; Mitts &
     Ofir channels).
   - In sports and crypto, skill means speed on public information, where a follower is structurally late
     (Brown; Croxson & Reade).
6. **Treat one-shot new accounts as uncopyable by construction.**
   - Treat them as a hazard (adverse selection against makers), not a signal.
   - Do not label them insiders.
7. **Watch for bait wallets.** Wallets whose visible history was built to attract copiers are documented in
   memecoins (Luo et al.) and suggested by Intrade Trader B. Check for coordinated wallet clusters before
   copying; Liu (SSRN 6678718, abstract) reports Sybil clusters of insider accounts on Polymarket.

## 5. Secondary leads (metadata VERIFIED via Crossref, arXiv or OpenAlex; content as stated)

| Item | ID | Why it matters | What I saw |
|---|---|---|---|
| Liu, S., "Wisdom of the Crowd or Wisdom of the Insider? Insider Trading on Prediction Markets" | SSRN 6678718 (2026-04-30) | Polymarket insiders, maker losses, Sybil clusters | Abstract only. Profits concentrate in insiders and market makers. Makers lose more per dollar in "compromised" markets. Insider accounts form Sybil clusters funnelling to one withdrawal address |
| Wang, M., "Smart Money on Polymarket: A Behavioral Anatomy of 273 Top Prediction-market Traders" | SSRN 6624899 (2026-07-29) | Smart-money archetypes | Abstract only. Built on third-party polydata.pro analytics, so selection is on fame. Median event-level win rate 93% against 58% trade-level. Pure bots earn the lowest median PnL. Weak design (no benchmark) |
| Félez-Viñas, Johnson & Putniņš, "Insider trading in cryptocurrency markets" | SSRN 4184367 | On-chain detection of pre-announcement wallets | Abstract only. The current Crossref abstract says insider trading in **28–48%** of listings and at least $30M. The 2022 press version said 10–25% and $1.5M (Coinbase, 146 listings). Versions differ |
| Rogers, Skinner & Zechman, "Run EDGAR Run" | *JAR* 2017, DOI 10.1111/1475-679x.12167 | Seconds-level disclosure latency | Search snippets only (see §3.7) |
| Nechepurenko, arXiv 2605.02287 / 2605.02286 / 2605.00493 | arXiv | Method comparison; Information Leakage Score; FFIC insider-case inventory and code at github.com/ForesightFlow | 2605.02287 partly read (the Gómez-Cram summary). 2605.02286 abstract: geopolitical deadline markets have a hazard half-life of 2.9 days; pre-event drift on the $269M Iran market is "mild". A single-author, self-citing series |
| Gemayel & Preda, *JEBO* 2018 (DOI 10.1016/j.jebo.2018.08.014); *EJF* 2017 (10.1080/1351847x.2017.1405832); *IRFA* 2021 (10.1016/j.irfa.2021.101847) | | Social-trading leaders: disposition effect, herding, crypto trader learning | Metadata only |
| Dorfleitner et al., "To follow or not to follow…", *QREF* 2018 | DOI 10.1016/j.qref.2018.04.009 | wikifolio leader returns | Metadata only. The Regensburg copy page is JavaScript-only |
| Röder & Walter, "What Drives Investment Flows into Social Trading Portfolios?", *J. Financial Research* 2019 | DOI 10.1111/jfir.12174 | Flow chasing on copy platforms | Abstract. Over 5,300 portfolios. Flows chase raw returns, not alpha, and only for top performers |
| Pelster & Hofmann, *JBF* 2018 | DOI 10.1016/j.jbankfin.2018.07.003 | eToro: being copied is linked to the disposition effect | Metadata; cited by Apesteguia et al. |
| Krafft, Zheng, Shmueli, Della Penna, Tenenbaum, Pentland, "Popularity and Performance: A Large-Scale Study" | arXiv 1406.7729 (CI 2014) | eToro copier dynamics | Read (4 pp.). Popularity amplifies the effect of recent performance on new copiers (p < 10⁻⁵). There are no copier-return results |
| Mellers et al., "Identifying and Cultivating Superforecasters…", *Perspectives on Psych. Sci.* 10(3):267–281 (2015) | DOI 10.1177/1745691615577794 | Persistence of forecasting skill (top 2% of forecasters placed on elite teams) | Not read (no open-access copy). Per the abstract, elite teams kept their accuracy rather than regressing to the mean (PLAUSIBLE) |
| Marginson (2010) *SEJ*; Coleman (2007) *AFE* | see §3.5 | Shin-model critiques | Abstract / snippet only |
| Mishory, SSRN 6439580; Gill, SSRN 6868059; Turk, Holden & Haugh, SSRN 7259584 | | Legal and theory views on prediction-market insider trading | Abstracts only. Gill's model has an interior optimal enforcement level |
| Gil & Levitt (2007), "Testing the efficiency of markets in the 2002 World Cup", *J. Prediction Markets* | | Intrade trader-level data; 10–15 min post-goal drift in a thin market | Only as summarised by Croxson & Reade |

## 6. Discrepancies

- **CONTEXT.md:** no contradictions found. Two additions:
  - Legal regimes differ by venue. The CFTC calls the international Polymarket site an "unregistered platform"
    in the NPRM. Polymarket US (QCX LLC) is a DCM whose rulebook follows the misappropriation theory, per
    Bartlett & O'Hara fn. 37 (not checked by me).
  - CONTEXT.md's Gamma `secondsDelay` field is the same remedy as Betfair's in-play bet delay discussed by
    Brown (2012).
- **Gómez-Cram et al. flagged-insider count:** 1,950 (Nechepurenko) against 967 (Macey & Enriques). Probably
  different versions; unresolved without the full text.
- **Maduro case profit:** CFTC says more than $404,000 on more than 436,000 shares. Mitts & Ofir (via Macey &
  Enriques) say $485,346 on $38,533 at risk. Probably account aggregation; unresolved.
- **Release-number typo in the NPRM:** one NPRM footnote gives the February advisory's URL as release
  "9158-26", and another gives "9185-26". 9185-26 is correct (VERIFIED on cftc.gov).
- **Working paper against journal numbers:**
  - CHS: 8% a year in the WP against about 6% in the RAPS abstract.
  - BLLO: 28.1 and −34.2 bp net in the 2011 WP against 37.9 and −28.9 in the published abstract.
  - BSW: 1.9% positive-alpha funds in the 2005 WP; the 2010 JF figure was not checked.
  - I report the versions I read.

## 7. Search log

1. Read CONTEXT.md, `sweep_polymarket-empirical.md` (sections on Gómez-Cram, Mitts & Ofir and secondary leads)
   and the head of `pit_wallets_preregistration.md`.
2. **arXiv API**, sorted by date:
   - Queries: `abs:"copy trading"` (3 hits, one relevant: 2601.08641), `abs:"social trading"`,
     `abs:"prediction market" AND abs:insider` (Nechepurenko series), `abs:"prediction market" AND abs:informed`
     (found 2606.07811), `abs:"betting exchange"`, `abs:betfair`, `abs:"insider trading" AND abs:crypto`,
     `abs:polymarket AND (skill OR persistence OR follow*)`.
   - `abs:"smart money" AND abs:crypto` returned 0 hits.
   - Downloaded and read 2606.07811, 2601.08641, 2605.02287 and 1406.7729.
3. **Crossref**: bibliographic searches for "insider trading prediction markets" (2025 onwards), copy-trading and
   social-trading performance, "Polymarket copy trading wallet following smart money", Shin-model papers,
   copycat funds and Run EDGAR Run.
   - Pulled abstracts for SSRN items (Liu, Turk et al., Macey & Enriques, Della Vedova, Mishory, Gill, Oliphant,
     Wang, Gómez-Cram, Félez-Viñas, Marginson).
   - Checked volume and page metadata for all journal items.
4. **OpenAlex**: open-access locations. These led to the BSW WP (ULB), the Apesteguia et al. accepted version
   (Essex), the BLLO eScholarship copy (403 to curl) and the copycat NBER WP.
5. **Primary PDFs obtained by curl:**
   - Rothschild & Sethi (researchdmr.com), Brown 2012 (UEA eprints), CHS 2005 WP (sites.uci.edu), BLLO 2011 WP
     (Haas).
   - CRS LSB11406 (congress.gov), the CFTC advisory PDF (cftc.gov/media/13351), the NPRM (govinfo HTML).
   - Bartlett & O'Hara (conference.nber.org), Croxson & Reade DP (repec.cal.bham.ac.uk via IDEAS), Smith et al.
     postprint (NTU), Macey & Enriques (ecgi.global), NBER w8653.
6. **WebFetch**: CFTC releases 9185-26 and 9217-26 (curl got only page chrome).
7. **Dead ends:**
   - SSRN (403 to curl and WebFetch). Federal Register website and API (IP blocked; used govinfo instead).
   - comments.cftc.gov (403; Mitts comment letter not read). Durham worktribe (403).
   - The eScholarship PDF of BLLO (403). The Regensburg repository (JavaScript).
8. **Expected but not found as primary text:**
   - Gómez-Cram et al., Della Vedova (both papers), Oliphant (no author page or PDF found by WebSearch), Liu,
     Félez-Viñas et al., Rogers et al., Mellers et al., Shin (1993; JSTOR only), Dorfleitner et al.
   - I found **no trader-level Betfair or bookmaker study of bettor skill persistence**. The closest are an
     online-poker persistence study (PLOS ONE 2014) and a sports-betting field experiment on beliefs; neither
     was read.
   - I found no rigorous field study of crypto-exchange copy trading (Binance, Bybit, Bitget lead traders); only
     exchange-sponsored surveys and blogs (leads only, not cited).
   - I found no eToro study measuring copier returns against a benchmark (Pan et al. 2012 and Liu et al. 2014
     are known only via Apesteguia et al.'s literature review).
9. Not done: no git commit; no paid sources.
