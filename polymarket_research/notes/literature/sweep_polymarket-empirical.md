# Literature sweep: Polymarket and crypto prediction-market empirical research, 2021–2026

As of 2026-10-17. Author: research agent (literature sweep). Labels: **VERIFIED** = I read it in the primary source
myself (or a sibling note in this folder read it in full, which I say); **PLAUSIBLE** = consistent with the evidence
but not directly checked; **UNSUPPORTED** = no evidence found.

Scope: arbitrage frequency and size, efficiency and calibration, who profits, wash trading and volume inflation,
informed-trading detection, liquidity provision and spreads, fee changes, resolution (UMA) disputes and manipulation.
Sibling notes already cover three papers in depth. I summarise them here and do not repeat their full analysis:
`title_who-wins-who-loses.md` (Akey et al.), `title_probabilistic-forest.md` (Saguillo et al.),
`title_flb-polymarket.md` (Cardozo & Rivero-Wildemauwe) and `title_mean-reversion-polymarket.md` (Vojtko & Dujava).

## 1. Bottom line for a retail trader

None of the papers below shows an edge that a retail trader could have identified in advance and executed at real
prices, after today's fees, with an out-of-sample test. The most useful results are about **where money goes** and
**which apparent edges are measurement errors**.

1. **Complete-set and neg-risk arbitrage are small, short-lived and competitive once measured at executable prices.**
   - Saguillo et al.'s "$40M realised" is a broad inference: fees ignored, 1-hour grouping, VWAP prices.
   - On the same resolution window, Gebele et al.'s mechanism-linked estimand gives **$291,424**. Across 2024 to early
     2026 they find $1.12M in total (VERIFIED, 2608.00666 §7).
   - Median converter profit fell from about $1 to about $0.08 per conversion by early 2026.
   - Order-book studies find single-market YES+NO arbitrage almost absent (7 episodes in 173 NBA games). Same-condition
     deviations are mostly API synchronisation artefacts.
   - Leg execution is also exposed to "ghost fills": matched orders that are deliberately cancelled before settlement,
     including attacks aimed at arbitrage bots.
2. **Combinatorial and logical arbitrage exists only in end-game sports states and at retail size.**
   - The median edge is about 1¢ per $1, and 76.9% of episodes are capped near 15 shares (2605.00864). The sample is
     fee-free, February to March 2026.
   - **My calculation (PLAUSIBLE):** under the current Sports taker rate of 0.05·p(1−p) per share, two legs near 0.5
     cost about 2.5¢ in fees, which wipes out the edge. Legs near 0.93/0.06 cost about 0.6¢.
3. **Liquidity provision is where the documented profits are, but no paper has a fill-level, fee-aware maker
   backtest.**
   - Akey et al. find that maker share is the strongest correlate of positive PnL.
   - Gómez-Cram et al. (abstract only) group "skilled + market makers" as under 3.5% of accounts taking over 30% of
     gains.
   - Dai, Jia & Yu find that BTC 5-minute market makers earned +$3.1M gross in normal cycles but lost in manipulated
     ones.
   - Dubach (2610.06412) measures a taker-signed realised spread of about 1.3¢ per share (share-weighted) at a
     5-minute horizon, before fees and rebates.
   - Inventory risk near resolution, adverse selection by informed and manipulative flow, and capital lock-up are all
     unmeasured at the fill level.
4. **Wallet-following has mixed in-sample support and no clean executable test.**
   - Skill concentration and some persistence are reported. Gómez-Cram et al. (abstract and press only): about 3% of
     accounts are skilled, and 44% persistence across a random split of events, which is not a time split.
   - Akey et al. find heavy dropout.
   - Two SSRN papers claim copy or expert-following returns (Oliphant +1.62 pp; Lei & Huang +335.66% replay). I could
     read only their abstracts, so both are UNSUPPORTED for decision purposes.
5. **Favorite–longshot effects are fragile to dependence and grouping.**
   - Cardozo & Rivero-Wildemauwe: the longshot loss flips sign under parent-event weighting.
   - Gruener (abstract): an apparent FLB in 5-minute crypto markets disappears under contract-clustered inference.
   - Reichenbach & Walther (Oct 2026 abstract): "no general market-level longshot bias".
   - Near-certain favourites in **BTC 5-minute** markets were reversed **34%** of the time in cycles with a settlement
     push on Binance, against 1% otherwise (2606.31675 Table 9). That is a tail a near-resolution favourite strategy
     must price.
6. **Wash trading and volume inflation make raw volume unreliable as a liquidity signal.**
   - About 24% of historical *share* volume is flagged by the network method, peaking near 60% in December 2024.
     Simple self-trade screens flag about 1–3%.
   - Naive OrderFilled sums overstate turnover by about 2.5× in the Trump market.
   - Any "volume" or "liquidity" filter in our universe construction should use depth, open interest or exchange-
     equivalent turnover, not reported volume.
7. **The 2026 fee regime changes everything measured before it.**
   - Most samples end before 2026-03-30, when fees went platform-wide.
   - Qin & Yang's staggered DiD links fee activation with wider effective spreads (Gibbs +0.008) and lower wash share.
     Pre-trends are acknowledged for several outcomes, and the authors call their own t-statistics "implausibly large".

## 2. Papers selected (ranked by usefulness to this project)

| # | Paper | Status | Full text read? | Relevance | Families |
|---|---|---|---|---|---|
| 1 | Akey, Grégoire, Harvie, Martineau, "Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket" | SSRN 6443103 / CEPR DP21615 (WP) | Yes, by sibling note (mirror, some gaps) | core | A, D, E |
| 2 | Gebele, Mutzel, Matthes, "Executable Arbitrage and Market Efficiency in Prediction Markets" | arXiv 2608.00666v1 (preprint) | **Yes** (me) | core | B, C |
| 3 | Saguillo, Ghafouri, Kiffer, Suarez-Tangil, "Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets" | AFT 2025 (LIPIcs 354, peer-reviewed) | Yes, by sibling note | core | B, C |
| 4 | Cheng, Yang, Zou, "Arbitrage Analysis in Polymarket NBA Markets" | arXiv 2605.00864v1; SSRN 6624718 | **Yes** (me) | core | B, C, H |
| 5 | Sirolly, Ma, Kanoria, Sethi, "Network-Based Detection of Wash Trading" | SSRN 5714122 (WP, Jan 17 2026 rev.) | Yes, mostly (Jan 2026 version via third-party copy) | core | other (data hygiene), A |
| 6 | Dai, Jia, Yu, "Settlement Manipulation in Prediction Markets" | arXiv 2606.31675v1 | Mostly (intro, data, Sec. 6.4) | core | H, D, other |
| 7 | Shen, Jin, Wu, Wang, Chen, "The Ghosts of Polymarket: When Off-Chain Matches Meet On-Chain Reverts" | arXiv 2606.16852v2 | Partly (intro, RQ1–2, attack cases) | core (execution risk) | B, C, D |
| 8 | Dubach, "Measuring Trade Direction in a Prediction Market: Settlement Ground Truth and Trading-Cost Measurement on Polymarket" | arXiv 2610.06412v1 | Mostly (Secs. 1–6, App. D.1) | core | D, other |
| 9 | Dubach, "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book" | arXiv 2604.24366v2; SSRN 6658364 | **Yes** (me) | supporting (one key result is contradicted by #8) | D |
| 10 | Cardozo, Rivero-Wildemauwe, "The Favorite–Longshot Bias in Prediction Markets: Evidence from Polymarket" | arXiv 2609.12878v1 | Yes, by sibling note | core | E, A |
| 11 | Gómez-Cram, Guo, Jensen, Kung, "Prediction Market Accuracy: Crowd Wisdom or Informed Minority?" | SSRN 6617059 (WP) | **No, abstract plus author-institution summary only** | core (unverified detail) | A, D |
| 12 | Qin, Yang, "Polymarket-v1 Database" | arXiv 2606.04217v2; SSRN 6870538 | Partly (Secs. 1–3, 5) | supporting | other (fees, data) |
| 13 | Tsang, Yang, "The Anatomy of a Blockchain Prediction Market: Polymarket in the 2024 U.S. Presidential Election" | arXiv 2603.03136v3; SSRN 6336679 | Partly (abstract, intro, data, grep) | supporting | other (volume) |
| 14 | Young, "OpenMarket: A Synchronized Polymarket-Binance Dataset for High-Frequency Prediction-Market Research" | arXiv 2607.26245v1 | Partly | supporting | G |
| 15 | Mitts, Ofir, "From Iran to Taylor Swift: Informed Trading in Prediction Markets" | SSRN 6426778 / 7259741 (law WP) | **No, abstract plus authors' HLS Forum post** | supporting | A, other |
| 16 | Gebele, Matthes, "Semantic Non-Fungibility and Violations of the Law of One Price in Prediction Markets" | arXiv 2601.01706v1 | Partly | peripheral | C, G |
| 17 | Della Vedova, "Who Profits from Prediction Markets? Execution, not Information" | SSRN 6191618 | **No, abstract only** | supporting | A, D |
| 18 | Reichenbach, Walther, "When Can Prediction Market Prices Be Trusted? Price Informativeness, Calibration, and Bias on Polymarket" | SSRN 7552098 (2026-10-02) | **No, abstract only** | supporting | E, H |

Families: A wallet-following, B complete-set arb, C logical arb, D liquidity provision, E favorite–longshot,
F mean reversion, G lead–lag, H near-resolution.

## 3. Paper-by-paper notes

### 3.1 Akey, Grégoire, Harvie, Martineau (2026), "Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket"

- **Metadata (VERIFIED by sibling note):**
  - SSRN 6443103 (DOI 10.2139/ssrn.6443103, Crossref created 2026-04-07). The latest version seen is dated
    2026-06-12. CEPR DP21615.
  - Data: Hugging Face `vgregoire/polymarket-users` (v1.3).
- **Data:**
  - Goldsky subgraph OrderFilled, reconciled to one row per maker–taker pair.
  - 2022-11-11 to 2026-03-29; 2.48M wallets, 588.3M trades, $67.1B.
- **Mechanism:** a zero-sum transfer from liquidity takers, often long-shot buyers, to liquidity providers and a
  minority of better forecasters.
- **Key findings (from sibling note, Secs. 4–7):**
  - The top 1% of winners take 76.5% of gains, and about 69% of users lose.
  - A 1 SD rise in maker share raises Pr(PnL>0) by 9.0 pp.
  - Maker-heavy user-months are 6.6–11 pp more likely to have a positive next-month Sharpe-analogue.
  - Wash screen (counterparty HHI ≥ 0.5): 3.1% of volume.
  - The two CFTC-prosecuted insider wallets rank 115th and 307th.
- **Costs and execution:**
  - Mostly a pre-fee sample. Spread enters only as a 0.5¢ minimum half-tick.
  - No depth, latency, markouts or capital lock-up. Open positions are marked at last trade.
- **Dependence:** no clustering by event or calendar time. The skill mixture model treats repeated trades in one
  market as independent.
- **Tradable prospectively?** No. The results are ex post associations, and no copy or market-making test was run.
- **Replication needs:** see the sibling note. In short: rebuild maker and taker legs on chain; markouts; current fees,
  rebates and rewards; event-clustered inference; a point-in-time wallet selection test.

### 3.2 Gebele, Mutzel, Matthes (2026), "Executable Arbitrage and Market Efficiency in Prediction Markets"

- **Metadata (VERIFIED, arXiv API and PDF):**
  - Jonas Gebele, Timm Mutzel, Florian Matthes (TU Munich).
  - arXiv:2608.00666v1 [cs.CE], posted 2026-08-01, only one version. No journal ref.
  - https://arxiv.org/abs/2608.00666
- **Read:** full text, including Apps. A–G. Figures were read only through their captions and extracted text.
- **Mechanism:**
  - Distinguishes payoff-space no-arbitrage from protocol-executable no-arbitrage.
  - The NegRisk Adapter executes the NO→YES direction before settlement: a NO basket converts to collateral plus
    complementary YES.
  - The reverse YES→NO direction has no conversion path. It can be realised only by holding a complete basket to
    settlement, which locks up capital.
- **Data (§4.1), three non-overlapping panels:**
  1. FPMM era: 51 manually validated outcome sets, 235 markets, about 53k trades, with pool states rebuilt from Polygon
     RPC.
  2. CLOB transactions: 32,702 events and 259M trades for events listed to 2025-12-31.
     - Fills come from the HF `SII-WANGZJ/Polymarket_data` dataset.
     - Conversions, splits and merges come from Goldsky plus parsed logs, cross-checked on PolygonScan.
  3. Level-2 order books from the **pmxt archive**, hour-stratified, 2026-04-14 to 2026-05-19. Books are initialised
     from snapshots and replayed with incremental updates.
- **Evidence type:** descriptive measurement. Executable, depth-walked portfolio values in panel 3. Actor-level
  realised profits in panels 1 and 2. No forward-looking strategy test.
- **Costs and execution:**
  - Fee-adjusted edges, assuming taker execution on all legs (§4.2).
  - Gas is omitted because the relayer pays it.
  - Split-minted legs and residual YES are valued at midpoint-derived quotes: an assumed 1¢ spread at half-cent mids,
    2¢ at integer mids, and 0.1¢ near the extremes.
  - Conversion inputs must be acquired within 5 blocks; returned YES is tracked for 150 blocks.
  - Settlement baskets must be completed within 10 minutes, using FIFO accounting.
- **Dependence:** episodes are counted per event and direction, with no statistical inference. The FPMM and CLOB
  comparison is explicitly descriptive, not causal.
- **Key findings (VERIFIED):**
  - **CLOB order books (Fig. 2):** 2,098 positive fee-adjusted **YES-side** episodes against only 36 positive NO-side
    episodes. In the FPMM era the two sides were balanced.
  - **Durations (§5.2):** of 624 observed episodes, 366 span the whole observation window, so they last more than 50
    minutes. The median exact duration is **16.15 s for YES-side** (n=253) and 7.99 s for NO-side (n=5).
  - **Realised profit (§5.3):** about **1.118M USDC**, of which converter-enabled is 1.086M and settlement baskets are
    32,283.
    - CLOB: 5,923 profitable baskets, 28,644 USDC. The FPMM era adds 3,639 USDC.
  - **Exclusion:** one cluster of 75 conversions (3 addresses, 2025-12-12 22:07–22:14 UTC, 381,748 USDC) is left out
    as a likely related-party value transfer (App. D).
  - **Full-set NO→collateral conversions:** 205,531 USDC. Most of the profit comes from partial conversions plus
    management of the returned YES inventory.
  - **Trend:** median profit per conversion was about 1 USDC through July 2024, about 0.20 in late 2024–2025 and about
    0.08 by early 2026. That is consistent with rising competition.
  - **Restricted to Saguillo et al.'s 2024-04-01–2025-04-01 window:** these criteria give **$291,424**, against their
    ~$40M (§7).
  - **App. A:** in a 7-day replay of 308M WebSocket messages, the YES and NO books were exact mirrors apart from 20
    isolated API inconsistencies. Same-condition YES+NO "arbitrage" is therefore treated as a feed artefact and
    excluded.
- **Internal problems (VERIFIED in the PDF text):**
  - The v1 PDF drops the text after "%" in about 8 sentences, for example "approximately 40episodes", "366 (58.7first
    and final…" and "repeat actors form 70the profit". The affected shares (top-10 address share, maker-assisted share
    and others) cannot be read.
  - The 2,098 + 36 positive episodes in Fig. 2 do not reconcile with the "624 observed episodes" in §5.2. The paper
    does not explain the gap.
- **Tradable prospectively?**
  - Some converter strategies were realised in real time, so they were tradable by the actors who ran them.
  - For a retail entrant the evidence argues against: there are few NO-side violations, they close in seconds, profits
    per conversion are shrinking, and the remaining YES-side violations need capital locked to settlement.
- **Replication needs:**
  - L2 book replay (pmxt archive, or our own live capture).
  - NegRisk Adapter `convertPositions` event decoding.
  - The current fee schedule per market.
  - A latency model.
  - Treatment of placeholder outcomes and of augmented neg-risk events.

### 3.3 Saguillo, Ghafouri, Kiffer, Suarez-Tangil (2025), "Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets"

- **Metadata (VERIFIED by sibling note):**
  - arXiv:2508.03474v1 (2025-08-05).
  - Peer-reviewed at AFT 2025: LIPIcs vol. 354, Art. 27, DOI 10.4230/LIPIcs.AFT.2025.27.
- **Data:** on-chain OrderFilled, split and merge events; markets resolved 2024-04-01 to 2025-04-01; 17,218 conditions;
  86.6M fills.
- **Findings:**
  - About **$39.59M** "realised" arbitrage: single-condition about $10.58M, NegRisk about $29.0M, combinatorial about
    $95k from 13 hand-validated election pairs.
  - The top account made about $2.0M.
- **Method caveats (sibling note):**
  - Opportunities use block-level VWAPs of executed fills, carried forward up to about 2.5 h. These are not quotes.
  - Realised profit groups each address's fills within a 950-block (about 1 h) window and ignores fees.
  - The text's threshold (5¢) conflicts with the figure captions (2¢).
  - The headline does not reconcile exactly with its components.
- **Dependence:** none modelled.
- **Tradable prospectively?** Not established. This is ex post realised extraction under broad inference. Gebele et al.
  find about 1/136 of it under mechanism-linked criteria on the same window.
- **Replication needs:** see the sibling note.

### 3.4 Cheng, Yang, Zou (2026), "Arbitrage Analysis in Polymarket NBA Markets"

- **Metadata (VERIFIED):**
  - Guang Cheng, Jiaxin Yang, Haoxuan Zou (UCLA).
  - arXiv:2605.00864v1 [q-fin.TR], posted 2026-04-22. Also SSRN 6624718 (Crossref created 2026-04-24; that record
    lists the author order Yang, Cheng, Zou).
  - https://arxiv.org/abs/2605.00864
- **Read:** full text, including Apps. A–B.
- **Data:**
  - CLOB `GET /book` polling: 75,088,497 snapshots across 173 NBA games, 2026-02-04 to 2026-03-04.
  - The polling cycle is 3.6–5.5 s per market. Only top of book (L1) is used.
- **Mechanism:** two strategies.
  1. Single-market: ask_A+ask_B<1, or bid_A+bid_B>1 via mint and sell.
  2. Moneyline–spread subset arbitrage: ask(ML_A)+ask(Sp_B)<1, with a "middle" double payout possible.
- **Evidence type:** descriptive measurement of executable top-of-book states. There is no realised-trade test and no
  live trading.
- **Costs and execution:**
  - **Zero fees assumed** (correct for NBA in the sample window, per the authors).
  - Gas ignored. A $10 minimum executable size and a $100 per-episode cap.
  - Mirrored-book double counting is de-duplicated.
  - Post-game states are excluded: 30 of 37 raw single-market episodes and 233 of 523 combinatorial episodes were
    post-game artefacts.
- **Dependence:** no inference. Episodes within a game are not independent.
- **Key findings (VERIFIED):**
  - **Single-market (§3.2, Tables 2–4):** 7 valid in-game episodes in 3,042 markets, with a median duration of 3.6 s.
    Capped profit totals $210.19, mostly from one blowout game; uncapped is $4,418.
    - Median quoted spreads: 392 bps pre-game, 1,031 bps in-game, 7,533 bps post-game.
  - **Combinatorial (§4.2, Tables 6–7):** 290 executable episodes, 279 of them in-game, with a median duration of 16 s.
    - Median yield **101 bps**. Aggregate capped profit $559.59; uncapped $2,032.75.
    - 76.9% of episodes cannot absorb $100. The average executable size is 14.79 shares.
    - The "middle" payout was never realised.
- **Tradable prospectively?**
  - Partly in principle: the edges are L1-executable at the snapshot.
  - But the median duration is about one polling cycle, there is latency against professional bots, and the sizes are
    tiny.
  - Under today's sports taker fee the mid-price episodes are negative after fees (my calculation, PLAUSIBLE; see §1).
- **Replication needs:**
  - Our own live `/book` or WebSocket capture with sub-second timestamps.
  - Current `feeSchedule`.
  - Fill-or-kill latency tests.
  - Treatment of `secondsDelay` on sports markets (CONTEXT.md). The paper does not mention order delays, which would
    add leg risk.

### 3.5 Sirolly, Ma, Kanoria, Sethi (2025/2026), "Network-Based Detection of Wash Trading"

- **Metadata:**
  - Allen Sirolly, Hongyao Ma, Yash Kanoria (Columbia Business School DRO); Rajiv Sethi (Barnard/Columbia, Santa Fe
    Institute).
  - SSRN 5714122, DOI 10.2139/ssrn.5714122: Crossref created 2025-11-17, redeposited 2026-01-17T21:45Z (VERIFIED,
    Crossref).
  - Versions read:
    - 2025-11-06 (80 pp.), from a gamblingharm.org copy.
    - **2026-01-17 (82 pp.)**, from a defirate.com copy. Its PDF ModDate is 2026-01-17T21:38Z, which matches the SSRN
      redeposit.
  - Both are third-party copies. The title pages and author blocks match. SSRN itself returns 403.
  - No journal or conference version was found.
- **Read:** the Jan 2026 version: intro, Secs. 3 (data), 6 (results) and 7 (discussion), and parts of the appendices.
  I did not read Sec. 5's algorithm proofs in detail.
- **Data:**
  - All Polymarket CLOB trades, 2022-11-21 to **2025-10-12**, via the Polygonscan API: 67.7M trades (82.7M in a
    line-by-line view), 1.33M wallets, 102,532 markets, 29.0B shares, $15.5B.
  - Direct USDC transfers and profile names (display names, created_at) are used for validation only.
- **Mechanism:**
  - Wash traders form near-closed clusters that repeatedly close positions and trade mostly with each other.
  - Motives: no KYC, no fees (in the sample), anticipated airdrop farming, and volume-ranked homepage placement.
- **Method:**
  - Each wallet starts with a score for its position-closing propensity. Scores are then iteratively averaged with
    counterparties' scores.
  - Algorithm 2 sets market-specific thresholds by minimising a spillover metric.
- **Key findings (VERIFIED, Sec. 6):**
  - **Algorithm 2 flags 24.2% of historical *share* volume.** Algorithm 1 at θ=0.99 flags 18.0%, and at θ=0.9 flags
    29.2%.
  - Peak: about **60% of weekly volume in Dec 2024**. Under 5% from June to late September 2025, then about 20% in the
    first week of October 2025.
  - By category: Sports 45% of all-time volume, Elections 17%, Politics 12%, Crypto 3%.
  - 14% of wallets have more than half their volume flagged. Fewer than 10% of markets have any flagged volume.
  - The three largest election markets have none flagged. The Nicolae Ciucă (Romania) market is 98.5% flagged: 326.5M
    shares but only $2.6M.
  - Wash trading concentrates in buy/sell trades at sub-cent prices and in markets with a high volume-to-open-interest
    ratio.
  - Validation: clusters linked by direct USDC transfers, up to tens of thousands of wallets, are mostly flagged.
- **Measurement caveat:**
  - The headline shares are **share-volume** fractions, not dollar volume. Sub-cent wash trades inflate share volume
    far more than dollar volume.
  - For dollar volume the paper gives only partial figures, e.g. the top-50 markets are 29.4% of share volume and
    23.0% of dollar volume.
- **Dependence:** not applicable (classification, not inference). There is no ground truth, so precision cannot be
  measured.
- **Tradable?** Not a strategy. It matters for (i) volume-based filters, (ii) wallet-following, since wash clusters can
  look like high-activity wallets, and (iii) maker-competition estimates.
- **Replication needs:**
  - Full trade graph with wallet pairs: CryptoHouse `orders_filled` to 2026-01-05, then RPC.
  - The algorithm parameters are given (c=0.005, θ bounds 0.8/0.99, Y=0.1). No public code was found.

### 3.6 Dai, Jia, Yu (2026), "Settlement Manipulation in Prediction Markets"

- **Metadata (VERIFIED):**
  - David Dai, Ruizhe Jia (Stanford MS&E); Shihao Yu (Singapore Management University).
  - arXiv:2606.31675v1 [q-fin.TR], posted 2026-06-30. The PDF says "Current version: July 1, 2026".
- **Read:** intro, related literature, institutional background, data (§6.2) and the manipulated-cycle analysis
  (§6.4.1–6.4.6). I skimmed the theory (§§4–5) and did not read the appendices.
- **Mechanism:** Kumar–Seppi cash-settlement manipulation.
  - A holder of a BTC 5-minute up/down binary pushes Binance spot in the final seconds.
  - The Chainlink Data Streams settlement price follows Binance.
  - The resolution flips, and Polymarket liquidity takers pay.
- **Data:**
  - Polymarket on-chain fills: over 60M on the BTC 5-minute contract alone.
  - Polymarket book snapshots for about the last 7 weeks.
  - Binance trades and 100 ms book snapshots.
  - Sample 2025-07-01 to 2026-04-08: pre-launch (P1), 15-minute and 4-hour contracts (P2), and the 5-minute contract
    live from 2026-02-12 (P3, 56 days).
- **Evidence type:** a natural experiment (the launch) plus a descriptive wallet-level PnL attribution. Not a strategy
  test.
- **Key findings (VERIFIED):**
  - **Manipulated cycles:** the top decile of PushIntensity (final 10 s Binance |net flow| over the cycle's median bin;
    threshold ≥ 16.11). That gives 1,613 of 16,073 cycles.
    - They are concentrated overnight (56% vs 40%) and at weekends (44% vs 27%).
    - 18.7% are near-the-money, against 4.4% of normal cycles (Table 8).
  - **Outcome flips (Table 9):** in the [0.90,1.00) favoured-confidence bin, a push against the favourite makes the
    underdog win **34.2%** of the time, against **1.0%** in normal cycles (304 opposite-direction cycles).
  - **PnL (Table 10, gross of fees):**
    - The 821 "manipulator" wallets (≥5 manipulated cycles, ≥$2,000 PnL) make +$8.22M in manipulated cycles and
      +$0.09M otherwise.
    - Retail loses −$7.61M in manipulated cycles and −$3.20M in normal ones.
    - The 227 market makers make +$3.11M in normal cycles and −$0.62M in manipulated ones.
  - **Fees (fn. 20):** 5-minute contracts were fee-enabled from launch, with a peak effective rate of about 1.56% at
    even odds, raised to about 1.80% at the end of March 2026.
  - **Remedy:** the effect is largely absent for 15-minute contracts.
- **Costs and execution:** PnL is **gross of exchange fees** (stated). Market makers flatten each cycle, so they bear
  no lock-up.
- **Dependence:** cycle-level OLS with hour fixed effects. Trader identification is ex post, based on profits, which
  the authors acknowledge.
- **Tradable prospectively?**
  - No for a retail trader. Manipulated cycles are identified from flow in the final 10 seconds, and executing the push
    would be market manipulation, which is excluded on legal and ethical grounds.
  - The *defensive* implications are actionable:
    1. Near-certain favourites in 5-minute crypto markets carry a 1-in-3 flip risk when a push occurs.
    2. Makers should withdraw near the money before the close, as the market makers here did.
- **Replication needs:**
  - Binance tick data (`data-api.binance.vision`).
  - Polymarket 5-minute fills (Data API v2 or RPC).
  - Chainlink resolution prints.
  - Check whether the 2026-08-07 change in crypto up/down resolution (per Dubach 2610.06412 App. D.1) altered the
    mechanism.

### 3.7 Shen, Jin, Wu, Wang, Chen (2026), "The Ghosts of Polymarket: When Off-Chain Matches Meet On-Chain Reverts"

- **Metadata (VERIFIED):**
  - Yiming Shen, Yuhan Jin, Shuohan Wu, Yanlin Wang, Jiachi Chen (Sun Yat-sen University, Zhejiang University).
  - arXiv:2606.16852 [cs.CR]: v1 2026-06-15, v2 2026-10-10.
  - Code: github.com/shenyimings/ghost-hunter.
- **Read:** abstract, intro, background, RQ1 summary, and the attack-case section (P1–P3). Not the full appendix.
- **Mechanism:**
  - Off-chain matches settle later on chain. Between match and settlement, a party can invalidate its order by bumping
    its nonce, draining its balance, revoking its allowance, or using an ERC-1155 receiver hook ("Proxy Trap").
  - The match then reverts: a "ghost fill".
- **Data:** reverted `matchOrders` transactions, 2025-08-15 to 2026-08-15.
- **Key findings (VERIFIED):**
  - 2,037,304 reverts involving 261,156 participants. The daily rate peaked at 8.5% of all settlements; hourly, it hit
    24.3% on May 4.
  - 994,196 reverts (48.8%) are attributed to deliberate attacks. Settlement of those orders would have locked in
    $103.7M of net losses for their owners (73¢ per $ of notional).
  - **Arbitrage-bot hunting (P2):**
    - Ten Sybil wallets post fake neg-risk arbitrage, then cancel by ghost fill.
    - The bot is left with a partial basket and dumps it into a pre-placed low bid.
    - Nonce Bump attacks over-index on NegRisk markets (23% of its reverts vs a 9.8% baseline).
  - **Liquidity-reward manipulation (P3):** $13,397.65 in liquidity rewards went to 1,567 attacker addresses.
  - Polymarket shipped partial mitigations, but "Ghost Fills persist" as of writing.
- **Companion:** Chen, Long, Su, "Ghost-Filled Orders: Detecting and Testing Atomicity Violations in Non-Custodial
  Prediction Markets", arXiv:2609.17902v1 (2026-09-15). It covers 1.8M reverted transactions, 2025-08-12 to
  2026-05-22. I read the abstract only.
- **Tradable?** Not a strategy. It is an **execution-risk input for B and C**. A multi-leg arbitrage can get one leg
  voided after the other legs fill. API fill reports must be confirmed on chain, as Dubach 2610.06412 also shows for
  reverted prints.
- **Replication needs:** use Polygon receipts to count reverts on our own candidate markets, and count our own
  simulated legs' exposure.

### 3.8 Dubach (2026), "Measuring Trade Direction in a Prediction Market: Settlement Ground Truth and Trading-Cost Measurement on Polymarket"

- **Metadata (VERIFIED):**
  - Philipp D. Dubach (independent, Zurich).
  - arXiv:2610.06412v1 [q-fin.TR, econ.EM], posted 2026-10-05.
  - Replication: doi:10.5281/zenodo.23164515.
- **Read:** Secs. 1–6.2, the results tables for 6.3–6.4, App. D.1 and the summary of App. D.3. Not every appendix
  table.
- **Data:**
  - PMXT third-party WebSocket archive, 171 days from 2026-02-21 to 2026-08-10. 17.0M asset-days on 3.08M assets.
  - On-chain OrderFilled, OrdersMatched and FeeCharged events for 12 selected days (two V1 days, ten V2 days).
- **Key findings (VERIFIED):**
  - **Prints and taker legs:** 92.1–100% of public `last_trade_price` prints match the **taker** leg of their own
    transaction. Side and token agree on all 24.5M matched pairs.
  - **Settlement routes (§6.2):** 53.5–73.8% of settlements are **mints**, 17.9–27.1% complementary matches.
    - Pooling maker and taker legs mislabels direction.
    - The taker buy share is 80.6–85.6%.
  - **Classifiers:** Lee–Ready balanced accuracy 0.942, tick test 0.768, BVC 0.670.
  - **Trading costs (Table 4, cents per share, 12-day equal-day means, fees excluded):**

    | Weighting | Taker effective spread | Realised spread (5 min) | Midpoint impact (5 min) |
    |---|---|---|---|
    | Equal-fill | 2.328 | 6.486 | −4.158 |
    | Share-volume | 2.033 | 1.344 | +0.689 |

  - The spread cross-section is bimodal: one mode at one to two ticks, another above 0.5. The daily median live-asset
    spread ranges from 0.020 to 0.090.
  - **App. D.1, dated venue changes:**
    - 2026-03-06: crypto taker fees and maker rebates extended to all new crypto markets.
    - 2026-03-30: "Fee Structure V2".
    - 2026-04-28: V2 migration, which wiped resting orders.
    - 2026-05-28: taker rebates.
    - 2026-07-02: World Cup tick changed to 0.0025.
    - 2026-07-10: **sports taker rate 0.03→0.05 and sports maker rebate 25%→15%**.
    - 2026-07-24: order endpoints stop returning transaction hashes for immediately matched FAK/FOK orders.
    - 2026-08-07: crypto up/down resolution changed.
- **Costs:** fees, rebates and inventory are explicitly excluded. Quotes are as received by the collector, not
  execution-time books.
- **Dependence:** the day is the summary unit. The 12 days were purposively selected, so no population inference is
  made.
- **Tradable?** No. This is measurement. For D_liquidity_provision it is the best public estimate of taker effective
  spread and short-horizon markouts on post-V2 Polymarket. It is neither fee-aware nor maker-attributed.
- **Replication needs:** the PMXT archive (third party), or our own WebSocket capture; V2 event ABIs (App. B); the
  current fee schedule; maker-side markouts.

### 3.9 Dubach (2026), "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book"

- **Metadata (VERIFIED):**
  - arXiv:2604.24366: v1 2026-04-27, v2 2026-05-14. Also SSRN 6658364 (2026-07-29).
  - Code: github.com/philippdubach/polymarket-microstructure, Zenodo 10.5281/zenodo.19811426.
- **Read:** full text.
- **Data:**
  - A 52-day WebSocket archive (2026-02-21 to 2026-04-15): 30.3B events across 385,198 markets.
  - 255.4M on-chain V1 OrderFilled events for 2026-02-28 to 2026-03-27.
  - A pre-registered 600-market panel: the top-100 by volume plus 500 random markets. 58% are crypto.
- **Findings (VERIFIED):**
  - **SF1:** median quoted spread about 400 bps of mid in the 0.4–0.6 deciles, rising to 1,300–1,800 bps below 0.10
    (Table 1).
  - **SF2:** depth is spread across ten levels, with the top of book holding a median 13.6% of top-10 depth.
  - **SF4:** median maker HHI 0.031, about 32 effective makers.
  - **SF7:** self-counterparty wash share, a lower bound, median 0.97%, p99 10.6%, max 22.2%.
  - **SF8:** no time-to-close effect on depth after controls.
  - **§7:** feed-inferred trade direction agrees with "on-chain ground truth" about 59% of the time.
- **Problem (VERIFIED contradiction; cause PLAUSIBLE):**
  - The paper signs on-chain trades with a rule applied to all OrderFilled legs: +1 when takerAssetId=0, −1 when
    makerAssetId=0 (§4.2).
  - In V1, the taker-order leg has the exchange in the taker field, and its makerAssetId=0 means the *taker bought*.
    Mints also make maker legs buyers of the complement.
  - The author's own companion paper (3.8) shows that pooling legs misstates direction. It finds taker buy shares of
    80.6–85.6%, whereas this paper reports a "60/40 seller/buyer asymmetry" (§7.4).
  - It also finds Lee–Ready balanced accuracy of 0.942 against hash-matched taker legs, where this paper reports a 59%
    agreement.
  - The periods differ (Feb–Mar vs Apr–Aug 2026). Even so, the 59% result and the sign-flip rates for effective spread
    and Kyle's λ in this paper are probably artefacts of an incorrect "ground truth".
  - The negative median effective half-spreads in Table 3 (Crypto −0.039) point the same way.
  - The **direction-free** facts SF1, SF2, SF4 and SF8 are unaffected.
- **Tradable?** No. Use SF1 and SF2 as quoted-spread and depth priors. Do not use its signed measures.

### 3.10 Cardozo & Rivero-Wildemauwe (2026), "The Favorite–Longshot Bias in Prediction Markets: Evidence from Polymarket"

- **Metadata (VERIFIED, arXiv API; sibling note read the full 51 pp.):**
  - arXiv:2609.12878v1 [econ.GN], posted 2026-09-11.
  - Universidad Católica del Uruguay.
  - Data: Akey et al. HF v1.3, ending 2026-03-29.
- **Findings (abstract VERIFIED by me; detail by sibling):**
  - Buys below 10¢ lose 19.3¢ per $. Event-clustered 95% CI [−46.99, +8.30]%, so **not significant**.
  - Buys at or above 90¢ earn +0.83¢.
  - Longshots lose 6.3¢ with equal child-market weights but **gain 4.1¢ with parent-event grouping**.
  - The pattern is absent in Sports.
  - Heavy past longshot buyers earn similar returns to others.
- **Costs:** pre-fee, held to resolution, transaction prices. No strategy test.
- **Dependence:** among the best in this literature (event-clustered CIs, wild bootstrap).
- **Tradable?** Not established. A favourite edge of about 0.8¢ is smaller than one tick plus today's fees at mid-range
  prices.

### 3.11 Gómez-Cram, Guo, Jensen, Kung (2026), "Prediction Market Accuracy: Crowd Wisdom or Informed Minority?"

- **Metadata (VERIFIED, Crossref and OpenAlex):**
  - Roberto Gómez-Cram, Yunhan Guo, Howard Kung (London Business School); Theis Ingerslev Jensen (Yale).
  - SSRN 6617059, DOI 10.2139/ssrn.6617059. Crossref created 2026-04-24, redeposited 2026-06-25.
- **Read:** **abstract only** (Crossref). Plus Yale Insights' summary (author institution; treated as secondary) and
  press coverage (leads only). SSRN returned 403, and no author-hosted PDF was reachable.
- **Abstract (VERIFIED):** "around 3% of all accounts generate the bulk of price discovery". Their trades predict
  future prices and outcomes. The majority "funds" the minority.
- **Secondary detail (PLAUSIBLE, Yale Insights summary):**
  - 1.72M accounts, 98,906 events, 210,322 markets, $13.76B, over "two years".
  - Skill is classified by a sign-randomisation test with 10,000 draws.
  - Skilled traders plus market makers are under 3.5% of accounts and take over 30% of gains.
  - 44% of skilled accounts in one random half of events are also skilled in the other half.
  - Insiders are "sporadic" and "small".
  - Press adds that only 12% of top earners overlap with the skilled set (lead only).
- **Dependence and tradability:** unknown without the full text. A random split of events is **not** a time-ordered
  out-of-sample test, so it does not establish copyability.
- **Replication needs:** obtain the full text; re-run sign randomisation with event-clustered permutation; test
  time-ordered persistence and latency-adjusted copy returns.

### 3.12 Qin & Yang (2026), "Polymarket-v1 Database"

- **Metadata (VERIFIED):**
  - Boka Qin (WUSTL), Rui Yang (SWUPL); both associated with Time Seventeen.
  - arXiv:2606.04217: v1 2026-06-02, v2 2026-06-08. SSRN 6870538.
  - Data: huggingface.co/datasets/TimeSeventeen/Polymarket-v1.
- **Read:** Secs. 1–3, 4.1 and 5 (fee DiD). Partial.
- **Data:** the full V1 CTF Exchange OrderFilled tape, 2022-11-21 to 2026-04-28: 1.20B records, 1.30M markets, $61B
  nominal, with "ground-truth" aggressor labels.
- **Findings (VERIFIED):**
  - Tick rule 49.83% and BVC 50.51% accuracy against their labels.
  - **Concentration (Table 5):** the top 1% of maker addresses hold 84.1% of maker volume; the top 1% of takers hold
    69.7% of taker volume.
  - **Annual median Gibbs effective spread (Table 6):** 0.0149 (2022), 0.0072 (2024), 0.0067 (2025), 0.0078 (2026).
  - **Fee DiD (§5.3, Table 8):** fee activation by category (Crypto 2026-01, selected Sports 2026-02, others
    2026-03) is associated with:
    - Gibbs spread +0.00805;
    - Kyle's λ +0.00116;
    - True VPIN +0.0159;
    - wash share −0.000362.
- **Self-declared caveats:**
  - Pre-trends for VPIN and Amihud.
  - TWFE under staggered adoption.
  - "t-statistics … implausibly large … likely reflect under-estimated standard errors".
- **Discrepancies:**
  - Their fee-activation dates (crypto Jan 2026) differ from Dubach's (crypto extended 2026-03-06; platform-wide
    2026-03-30) and from Akey et al.'s (2026-03-30).
  - Their 1.20B "trades" vs Akey et al.'s 588M reflects counting conventions (raw fill events vs reconciled pairs).
  - Their "ground truth" labelling convention differs from Dubach's taker-leg target (see 3.8). Dubach could not
    reconcile the tick-rule accuracy gap.
- **Tradable?** No. A dataset plus descriptive and quasi-causal estimates. Useful as an independent on-chain archive up
  to the V2 cutover.

### 3.13 Tsang & Yang (2026), "The Anatomy of a Blockchain Prediction Market: Polymarket in the 2024 U.S. Presidential Election"

- **Metadata (VERIFIED):**
  - Kwok Ping Tsang (Virginia Tech), Zichao Yang (Zhongnan University of Economics and Law).
  - arXiv:2603.03136: v1 2026-03-03, v3 2026-09-14. SSRN 6336679.
  - Previously titled "The Anatomy of Polymarket: Evidence from the 2024 Presidential Election".
- **Read:** abstract, intro, data section and key passages (grep). Not the full text.
- **Data:** OrderFilled and OrdersMatched logs via public Polygon RPC for the Trump, Biden and Harris markets from
  2024-01-05: 5.09M fills, 2.35M matches. Extended to 249 election markets.
- **Findings (VERIFIED):**
  - Naive OrderFilled volume = exchange turnover + market activity.
  - October 2024 Trump market: $958M naive volume = $391M turnover + $567M activity.
  - Corrected Kyle's λ is 1.1–2.1× the naive estimate. Moving the October price 5 pp cost $9.1M, not $15.6M.
  - The median active market's naive volume is about 3× its turnover (range about 2–50×), largest in young, thin
    markets.
  - The whale's buying was about 15% of the October net inflow, and capital entered on both sides.
- **Tradable?** No. A measurement correction that matters for any liquidity or volume screen and for impact estimates.

### 3.14 Young (2026), "OpenMarket: A Synchronized Polymarket-Binance Dataset for High-Frequency Prediction-Market Research"

- **Metadata (VERIFIED):**
  - Gregory Young. arXiv:2607.26245v1 [q-fin.TR], posted 2026-07-28.
  - Data: HF `gregyoung14/openmarket-btc-polymarket`. Code: github.com/gregyoung14/openmarket (v0.5.2).
- **Read:** abstract, intro, and the model and spread sections (grep).
- **Data:** BTC 15-minute up/down markets on 54 Polymarket days and 57 Binance days, 2026-02-12 to 2026-05-15. 727M
  rows; 2.94M lead–lag pairs.
- **Findings (VERIFIED):**
  - A walk-forward logistic model with 43 features gives pooled out-of-sample AUC 0.8377, Brier 0.165 and ECE 0.026
    over 559 windows. The naive book-mid prior, scored on the same rows, does slightly better: AUC 0.8405, Brier 0.163,
    ECE 0.014. In the author's words, the in-sample "ranking lift … does not survive walk-forward evaluation".
  - Simulated trading with 1% fees and 0.5% slippage loses −0.116 normalised payoff units per trade.
  - Top-of-book spreads are usually one tick (median 0.01, p95 0.02).
  - Polymarket quotes respond to large Binance moves after a median 347 ms.
- **Evidence type:** **out-of-sample walk-forward with simulated trading: a null result.**
- **Tradable?** No (the author's own conclusion). The most honest lead–lag evidence available. The fee model (a flat 1%)
  differs from the actual p(1−p) schedule.

### 3.15 Mitts & Ofir (2026), "From Iran to Taylor Swift: Informed Trading in Prediction Markets"

- **Metadata (VERIFIED, Crossref):**
  - Joshua Mitts (Columbia Law), Moran Ofir (University of Haifa).
  - SSRN 6426778 (created 2026-04-06); revised SSRN 7259741 (2026-08-11).
  - Authors' summary on the Harvard Law School Forum on Corporate Governance, 2026-03-25.
- **Read:** **abstracts** (both versions) plus the authors' forum post. No full text (SSRN 403).
- **Findings (VERIFIED in abstract and post):**
  - The screen covers all Polymarket markets from Feb 2024 to Feb 2026 (forum post: over 93,000 markets, nearly 50,000
    wallets). It flags over 210,000 suspicious wallet-market pairs (post: 210,718) using five features: bet size
    across traders, bet size within a trader, profitability, pre-event timing and directional concentration.
  - Buy side only; positions of at least $500.
  - Flagged pairs have a 69.9% positive realised profit rate and hold the winner 75.0% of the time.
  - About $143M of realised profit, and "$119 million more than execution prices implied" (August version).
- **Problem:** the screen conditions on **profitability and proximity to resolution**, which are ex post. The flags
  therefore cannot be used as a prospective signal. Nechepurenko (arXiv 2605.00493) makes the same critique.
- **Dependence:** permutation test (">60 SD"). Clustering is unknown.
- **Tradable?** No. Following "insider-like" wallets after the fact would require identifying them in advance. Per
  CONTEXT.md we do not allege insider information from wallet data.

### 3.16 Gebele & Matthes (2026), "Semantic Non-Fungibility and Violations of the Law of One Price in Prediction Markets"

- **Metadata (VERIFIED):** arXiv:2601.01706v1 [cs.CE], posted 2026-01-05. TU Munich.
- **Read:** intro, model assumptions, results and App. I (partial).
- **Data:** over 100,000 events across ten venues, 2018–2025. Price deviations are analysed for 7 venues.
- **Findings (VERIFIED):**
  - About 6% of events are listed on more than one venue.
  - Median execution-aware deviations are 2–4% from parity.
  - The 2024 election spread between Polymarket and Kalshi averaged about $0.03, up to $0.07.
  - A mechanical "enter the highest-yield arbitrage and hold" simulation reports **+1,218.66% over 800 days from 15
    trades**.
- **Problem:**
  - Execution costs are *standardised assumptions* (e.g. a 1.5% fee and $0.01 spread for one CLOB venue; App. I,
    Table 3) applied to price time series. They are not order-book depth.
  - Resolution-semantics risk is assumed away: "dispute and appeal processes are assumed to terminate".
  - So the 1,218% figure is not executable evidence.
- **Tradable?** Not established. It is also cross-venue, and Kalshi access is a regulatory question for the user.

### 3.17 Della Vedova (2026), "Who Profits from Prediction Markets? Execution, not Information"

- **Metadata (VERIFIED, Crossref):**
  - Joshua Della Vedova. SSRN 6191618: created 2026-03-10, redeposited 2026-06-30.
  - Companion: "Detecting Informed Trading in Prediction Markets: An Orthogonality Test", SSRN 6567238.
- **Read:** **abstract only.**
- **Abstract claims:**
  - 222M trades. Retail picks winners 51.3% of the time yet loses $79M. Automated traders are at coin-flip accuracy yet
    earn $133M.
  - Forecasting and execution are nearly orthogonal. "Retail traders lose not because they are wrong, but because they
    are late."
  - The companion paper flags 6,032 of 450,048 wallets, extracting about $150M.
- **Platform:** the abstract does not name it. Cited alongside the Polymarket literature by Akey et al. and by Dai,
  Jia & Yu. **UNSUPPORTED** that it is Polymarket-only.
- **Tradable?** Unknown. It is consistent with a "be the patient maker, not the late taker" reading.

### 3.18 Reichenbach & Walther (2026), "When Can Prediction Market Prices Be Trusted? Price Informativeness, Calibration, and Bias on Polymarket"

- **Metadata (VERIFIED, Crossref):**
  - Felix Reichenbach (TU Berlin), Martin Walther (German International University).
  - SSRN 7552098, created **2026-10-02**.
  - An earlier paper by the same authors: "Exploring Decentralized Prediction Markets: Accuracy, Skill, and Bias on
    Polymarket", SSRN 5910522 (2025-12-13). No abstract is available.
- **Read:** **abstract only.**
- **Abstract claims:**
  - 1.5B trades across 779,000 markets.
  - Accuracy improves with maturity and activity. Weather is most precise; Mentions and Geopolitics are least precise.
  - **"no general market-level longshot bias"**: low-probability outcomes are initially underpriced, then reverse late.
    "Default outcomes are persistently overpriced."
  - Sports matches bookmakers' accuracy. Live trading produces temporary distortions.
- **Tradable?** Unknown. The "default outcomes overpriced" claim is a testable lead for E and H, and it needs
  event-clustered, executable-price testing.

## 4. Cross-paper contradictions and measurement lessons

1. **Arbitrage size depends on the estimand.**
   - For markets resolving 2024-04-01 to 2025-04-01: Saguillo et al. report about $39.6M; Gebele et al. report $291k.
   - Saguillo uses VWAP fills, 1-hour grouping and same-condition rebalancing, with fees ignored.
   - Gebele uses 5-block conversion links and 10-minute baskets, excludes same-condition cases, and adds fees.
   - Only order-book (L2) replays measure executability: Gebele panel 3 and Cheng et al.
2. **Wash-trading share depends on the method and the unit.**
   - Network method: 24.2% of share volume (Sirolly et al.).
   - Counterparty-HHI screen: 3.1% of volume (Akey et al.).
   - Direct self-trade lower bound: median 1% per market (Dubach 2604.24366).
   - Fee activation reduced the wash share (Qin & Yang). Sirolly et al. also find a lull from May to September 2025.
3. **Trade direction:** use the taker leg (the exchange-as-taker OrderFilled leg, or the V2 `side` field). Do not pool
   legs, because mints are 54–74% of settlements (Dubach 2610.06412). Dubach 2604.24366's signed results conflict with
   this.
4. **Volume:** naive OrderFilled sums double-count exchange and mix in issuance (Tsang & Yang). Akey et al. use
   reconciled pairs. Polymarket-v1 counts raw fill events. Totals are not comparable across papers.
5. **FLB inference:** results change sign under event grouping (Cardozo & Rivero-Wildemauwe). They disappear under
   clustering (Gruener, abstract). One large dataset reports no general FLB (Reichenbach & Walther, abstract).
6. **Fee timing is inconsistent across papers:**
   - Qin & Yang: Crypto Jan, Sports Feb, others Mar 2026.
   - Dubach: crypto extended 2026-03-06, Fee Structure V2 on 2026-03-30, sports rate 0.03→0.05 on 2026-07-10.
   - Akey et al.: "all markets" from 2026-03-30.
   - Dai, Jia & Yu: the 5-minute crypto contract fee-enabled from its 2026-02-12 launch.
   - These can all be true for different market subsets. The project should rely on per-market Gamma `feeSchedule`
     and `feesEnabled`, not on any paper's dates.

## 5. Secondary leads (metadata VERIFIED via Crossref or arXiv; content not checked unless stated)

| Item | ID | Why it matters | What I saw |
|---|---|---|---|
| Wang, G., "Do prediction markets price events or adjudication? Evidence from the disputed Polymarket markets", *Economics Letters* 268 (Oct 2026) 113176 | DOI 10.1016/j.econlet.2026.113176 | The only journal article on UMA-disputed markets | Metadata only. ScienceDirect 403; the Elsevier API returned 429. **Not read** |
| Nechepurenko, "Resolution Is Not Settlement, Part I", arXiv:2609.15368 (SSRN 7344079) | | UMA lifecycle base rates | Abstract read: 159,447 proposals, **1,604 disputes**, 159,133 settlements. Single author; a large self-citing series |
| Wen, Zhou, Huang, "Can LLMs Help Decentralized Dispute Arbitration?…", arXiv:2604.15674 | | UMA disputes | Abstract read: about $972M of volume in disputed events; LLMs agree with the UMA outcome 89.58% of the time but cannot predict disputes |
| Sun, "The Friction Ledger…", SSRN 7453738 (2026-09-14) | | Fees vs edge | Abstract only: across 439 settled markets, +0.143% gross selection vs 1.488% modelled fees. **Assumes every BUY fill is a taker**, which Dubach shows is wrong for mints. Disclosed AI drafting |
| Oliphant, "The Return to Imitation: Evidence from Copy Trading on Polymarket", SSRN 6670318 | | A_wallet_following | Abstract only: copy trades beat the follower's own trades by 1.62 pp |
| Lei & Huang, "Semantic Expert Following in Prediction Markets…", SSRN 7420398 | | A_wallet_following | Abstract only: a +335.66% replay on a 2,989-market snapshot; 85% of notional filled. Extraordinary claim, unverified |
| Gruener, "Are Short-Horizon Crypto Prediction Markets Calibrated?…", SSRN 6863546 | | E, dependence | Abstract only: 209,453 entries on 18,239 contracts; slope 1.012; FLB disappears under clustering |
| Kakhbod, Livdan, Maciel, Schuerhoff, "Financial Innovation and Speculative Expansion: Evidence from Polymarket", SSRN 7401198 | | New listings and positioning | Abstract only |
| Ng, Peng, Tao, Zhou, "Price Discovery and Trading in Modern Prediction Markets", SSRN 5331995 (rev. 2026) | | G_lead_lag (Polymarket leads Kalshi in 2024) | Abstract only. 2024 election only |
| Le, "Decomposing Crowd Wisdom…", arXiv:2602.19520 | | Calibration | Abstract only: political underconfidence replicates on Polymarket. Code on GitHub |
| Portnaya, "Do Prediction Markets Match Option Prices?…", arXiv:2606.19517 | | G and relative value vs options | Abstract only: a 5.6–6.3 pp gap, AR(1) half-life about 4 h, on 2023 BTC threshold markets; small n (287 hourly obs.) |
| Ibrahim & Zaki, "Price Dislocations, News Citations, and Epistemic Leverage on Polymarket", arXiv:2609.06005 | | Manipulation cost | Abstract only: about $0.7–1.0M to move a market 5 pp and get the move cited |
| Tsang & Yang, "Political Shocks and Price Discovery…", arXiv:2603.03152 | | Mean reversion after shocks | Abstract only: the debate repricing reversed, the assassination-attempt repricing persisted |
| Sultan & Morstatter, arXiv:2609.28965 | | F_mean_reversion | Abstract only: 79 markets; predictive associations, not trading |
| Zang, Andrade, Nakajima, arXiv:2609.20017 | | D theory | Abstract claims "makers profiting not from spread but from carrying an under-priced side to settlement". Theory with some evidence; not checked |
| Bürgi, Deng, Whelan, "Makers and Takers: The Economics of the Kalshi Prediction Market" (SSRN 5502658; CESifo WP 12122) | | Kalshi maker/taker benchmark | Not crypto. See the sibling FLB note |
| Vojtko & Dujava, mean reversion, SSRN 6726362 | | F | See sibling `title_mean-reversion-polymarket.md` (reproduced; not an executable edge) |
| ACDC, "Insider Risks in Polymarket Political Markets" (2026 PDF) | | Insider risk | A policy report, not peer-reviewed. Lead only; not read |

## 6. Discrepancies with CONTEXT.md

- CONTEXT.md gives Sports at 0.05 and the Sports maker rebate at 15%. Dubach (2610.06412 App. D.1) dates that change to
  **2026-07-10** (from 0.03 and 25%). Consistent.
- Dai, Jia & Yu give a peak effective 5-minute crypto fee of about 1.80% at even odds after end-March 2026. CONTEXT's
  Crypto rate of 0.07 gives 0.07×0.25 = 1.75¢ per share at p=0.5. Consistent, if their "rate" is per $1 face.
- Akey et al. and Tsang & Yang describe USDC collateral; CONTEXT says pUSD since V2. The samples predate V2 (2026-04-28,
  per Dubach), so there is no conflict.
- Gebele et al.'s L2 panel comes from the pmxt archive, and Dubach uses PMXT. This is a **third-party historical book
  archive** that CONTEXT.md does not mention ("No official historical order book endpoint"). It is consistent, since
  the archive is unofficial, but it is a possible data source to evaluate. Access terms and cost were not checked.
- Dubach (2610.06412): after 2026-07-24, order endpoints no longer return transaction hashes for immediately matched
  FAK/FOK orders. This is relevant to the read-only alert system only indirectly.

## 7. Search log

1. Read CONTEXT.md and the existing sibling notes (`title_*`). Took their verified citations as leads: 2606.04217,
   2609.28965, 2610.13593, 2608.00666, 2605.00864, 2606.16852, 2603.03136, SSRN 5910522 and 6870538.
2. **arXiv API**:
   - `all:polymarket`, sorted by date: 62 results, all listed.
   - `abs:"prediction market" AND abs:"wash trading"`: 0 results.
   - `… AND abs:insider` (6), `… kalshi` (21), `… UMA` (1), `… arbitrage` with blockchain or decentralized (5),
     `market makers`, `efficiency AND calibration`, `favorite-longshot`, `manipulation`, `wallets`, `informed trading`.
   - Downloaded 24 PDFs and converted them with pdftotext. Read the core ones in full or in part, as stated per paper.
3. **Crossref** title search for "polymarket" (200 rows) found about 50 SSRN and journal items from 2025–2026. Also ran
   Crossref bibliographic lookups for specific titles and pulled abstracts from Crossref, which carries SSRN abstracts
   for most of them.
4. **OpenAlex** worked today: author affiliations, no abstracts for SSRN items.
5. **SSRN**: `papers.cfm` and `Delivery.cfm` return 403 to curl. ScienceDirect returns 403 to WebFetch. The Elsevier
   text API returned 429.
6. **WebSearch**:
   - Sirolly et al.: found two third-party PDF copies (Nov 2025 and Jan 2026 versions) plus press. Read the Jan 2026
     version.
   - Mitts & Ofir: HLS Forum post fetched (the authors' own summary).
   - Gómez-Cram et al.: no full text found. Yale Insights summary fetched. Author homepages either returned 502 at the
     proxy (robertogomezcram.com) or did not list the paper (sites.google pages). howardkung.com returned 503 to
     WebFetch.
   - Ng et al.: only the SSRN page and seminar listings; no PDF.
   - Oliphant ("The Return to Imitation"): only copy-trading blogs; no paper text.
   - Wang (Economics Letters): only news on UMA disputes; no preprint found.
   - NBER: no Polymarket NBER working paper found. "Polymarket Institute" (Fortune, 2026-07-29) is a funding initiative,
     not research.
   - Conferences (ACM EC 2026, AFT 2026, FC 2026): no Polymarket-specific 2026 conference paper found. The only
     peer-reviewed venue among the core papers is AFT 2025 (Saguillo et al.). Wang appears in *Economics Letters*, and
     Lee, Lee & Lee in *IRFA* (2026; Kalshi and Polymarket crypto markets; not read).
7. **RePEc/IDEAS** htsearch returned no parsable results (JS page). Dead end.
8. **Expected but not found as primary text:**
   - Gómez-Cram et al., Mitts & Ofir, Della Vedova, Reichenbach & Walther, Ng et al., Oliphant, Lei & Huang and Wang
     exist (VERIFIED via Crossref), but their full texts were not accessible.
   - I did not cite their contents beyond abstracts and authors' own summaries.
