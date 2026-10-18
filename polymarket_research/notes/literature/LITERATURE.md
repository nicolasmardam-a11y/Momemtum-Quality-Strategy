# Literature synthesis: can a retail trader earn positive expected returns on Polymarket after realistic costs?

As of 2026-10-17. Final-report literature section.

**Sources.** This synthesis uses only two inputs:
- the deduplicated paper entries and adversarial cross-check verdicts supplied to this step;
- the eight notes in this folder (`title_*.md`, `sweep_*.md`).

No paper outside that material is cited as evidence. Papers the notes mention only as leads appear under §4.3. They are
explicitly unverified.

**Labels.**

| Tag | Meaning |
|---|---|
| VERIFIED | Read in the primary source by a note author or the cross-checker |
| PLAUSIBLE | Consistent with the evidence but not directly checked |
| UNSUPPORTED | No evidence found |
| `[CC-confirmed]` | The adversarial cross-check found no material errors |
| `[CC-corrected]` | The cross-check corrected one or more fields; corrected values are used below |
| `[CC-unverifiable]` | Full text not accessible; abstract-level only |
| `[NCC]` | Relevance "peripheral", **not independently cross-checked** |

**Evidence-type tags.**

| Tag | Meaning |
|---|---|
| DESC | Descriptive measurement |
| IS | In-sample test or estimate |
| OOS | Out-of-sample or time-ordered test |
| SIM | Simulated trading |
| LIVE | Actual trading with real money |

**Platform facts** (fees, rebates, data access) come from `../../CONTEXT.md`, verified 2026-10-17.
- **Taker fee:** `shares × rate × p(1−p)`. Rates: Crypto 0.07; Sports 0.05; Politics, Finance, Mentions and Tech 0.04;
  most others 0.05; Geopolitics 0.
- **Makers** never pay fees. They receive maker rebates of 20% (Crypto), 15% (Sports) or 25% (others) of taker fees.
- **Taker Rebate Program:** 3–50% by tier, since 2026-05-28.
- **Liquidity Rewards** also exist.

Several of these numbers come from my own arithmetic on these rates. I mark that arithmetic as an extrapolation.

---

## 0. Decision-relevant summary

1. **No paper here demonstrates a strategy that meets all four tests a retail trader needs.** The strategy would have
   to be (a) selectable ex ante, (b) executed at executable prices, (c) net of the *current* (post-2026-03-30)
   Polymarket fee and rebate regime, and (d) out of sample.
   - The only real-money result is an Intrade/Betfair cross-venue trial in 2012: $3,686, +6.38% over 3 months
     ([RP14](https://doi.org/10.3233/AF-140031)). That venue regime no longer exists.
2. **Complete-set and NegRisk arbitrage (B) is not a retail opportunity.**
   - The "$40M" figure ([SAG25](https://arxiv.org/abs/2508.03474)) is a VWAP- and legged-fill inference that ignores
     fees. A mechanism-linked re-estimate for the same window finds **$291,424**
     ([GMM26](https://arxiv.org/abs/2608.00666)).
   - In 2026 order books, positive YES-side episodes last a median **16 s**. Same-condition YES+NO deviations are feed
     artefacts, because the two books are exact mirrors. Profit per conversion fell from about $1 to about **$0.08**.
3. **Logical and combinatorial arbitrage (C) is small and short-lived.**
   - Saguillo et al.'s combinatorial total is about $95k (0.24% of their headline).
   - In NBA markets the median edge is 101 bp, the median episode lasts 16 s, and the average executable size is
     about 15 shares, measured fee-free ([CYZ26](https://arxiv.org/abs/2605.00864)).
   - **Extrapolation:** at mid prices, today's sports taker fee is larger than that edge.
4. **Liquidity provision (D) is where profits accrue on every venue with role data.** But every maker return
   reported is conditional on fills, and no paper has a fill-level, fee- and rebate-aware Polymarket maker backtest.
   - Polymarket evidence: maker share is the strongest correlate of positive wallet PnL
     ([AKEY26](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6443103)). Persistent BTC 5-minute makers earn
     91.4% of their profit at resolution ([ZAN26](https://arxiv.org/abs/2609.20017)).
   - Makers lose in informative windows: in-play, high VPIN, settlement pushes.
5. **The favourite–longshot bias on Polymarket is small and depends on aggregation**
   ([CRW26](https://arxiv.org/abs/2609.12878)).
   - The abstract's "longshots lose 19.3¢ per $" is not significant, and the sign flips to +4.09% under
     parent-event weighting. There is no FLB in Sports.
   - The robust favourite premium (+0.28% to +0.83% pre-fee) is about the size of today's taker fee at 0.90–0.95.
     Taker favourite buys were −0.46% even before fees.
6. **Wallet-following (A): skill is concentrated and persists only modestly.**
   - There is no time-ordered, latency-adjusted, executable copy test on Polymarket.
   - Ex post "informed-trading" screens condition on outcomes.
   - The one Polymarket copy-trading result is a within-follower comparison, abstract only.
7. **Mean reversion (F):** the cited Polymarket paper is a hindsight-selected backtest on three contracts. Its assumed
   cost is about 5–6× too low ([VD26](https://doi.org/10.2139/ssrn.6726362)). Moves that carry news persist.
8. **Lead–lag (G):** Polymarket BTC 15-minute quotes lag Binance by a median **347 ms**. Out of sample, the
   Polymarket mid beats a 43-feature model, and simulated trading loses ([YOU26](https://arxiv.org/abs/2607.26245)).
   Cross-venue gaps largely disappear once quotes are synchronised (abstract-level,
   [MOU26](https://doi.org/10.2139/ssrn.7175258)).
9. **Near-resolution (H):** in BTC 5-minute markets the high-probability boundary is calibrated (0.982 price vs 98.4%
   wins). A final-seconds settlement push flips ≥0.90 favourites **34.2%** of the time
   ([DJY26](https://arxiv.org/abs/2606.31675)).
10. **Nearly every Polymarket sample ends before the 2026-03-30 fee regime.** No paper models per-market
    `feeSchedule`, maker rebates, the Taker Rebate Program and Liquidity Rewards together.

---

## 1. The four user-supplied titles

All four exist under the supplied titles. No supplied reference was unfindable.

| Supplied title | Exists? | Exact title / authors / date / status / link | What it actually finds | Correction to the supplied reference |
|---|---|---|---|---|
| "Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets" | **Yes, exact** (VERIFIED; the IMDEA repository spells it "Unraveling") | Oriol Saguillo, Vahid Ghafouri, Lucianna Kiffer, Guillermo Suarez-Tangil. arXiv:2508.03474v1, 2025-08-05 (still the only version). **Refereed**: AFT 2025, LIPIcs vol. 354, Art. 27, pp. 27:1–27:24, DOI 10.4230/LIPIcs.AFT.2025.27, published 2025-10-06. Pittsburgh, 8–10 Oct 2025, per the IMDEA record (not re-opened by the cross-checker). https://arxiv.org/abs/2508.03474 `[CC-corrected]` | DESC/IS on markets resolving 2024-04-01 to 2025-04-01: 17,218 conditions and 86,620,143 fills. Headline "realised" arbitrage **$39,587,585.02**: about $10.58M same-condition YES/NO, about $29.02M NegRisk within-market, and **about $95.2k combinatorial** (4 of 13 hand-validated 2024-election pairs). Prices are per-block trade VWAPs, carried forward up to 5,000 blocks (~2.5 h) and then **set to 0**. Fills per address within 950 blocks count as one opportunity. Fees, depth, latency, leg risk and lock-up are ignored. A mechanism-linked re-estimate for the same window is **$291,424** (GMM26). | It is a peer-reviewed conference paper, not just a preprint. The "$40M" is gross, inferred from legged fills, not risk-free, and almost entirely within-market (combinatorial is 0.24%). The abstract's "order book data" are executed fills. Internal inconsistencies: a 5¢ threshold in the text vs 2¢ in the captions; "5 cases" with 4 listed; Fig. 9 says "11 pairs" against 13 in the text. The headline does not reconcile: it is $9,630 below the single-condition + NegRisk sum ($39,597,215.48) and **$104,787 below the sum of all three components** ($39,692,372.19). The LLM validation ran on 128 NegRisk Politics markets, not "single markets". It names the Conditional Tokens contract as the `OrderFilled` emitter, which is wrong (VERIFIED from the exchange and CT contract ABIs, plus one decoded transaction). Reading the median ~$0.60 "profit per $" as a stale/zeroed-leg artefact is PLAUSIBLE. |
| "Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket" | **Yes, exact** (SSRN/Crossref capitalise "In") | Pat Akey (ESSEC), Vincent Grégoire (HEC Montréal), Nicolas Harvie and Charles Martineau (Toronto). SSRN 6443103 (DOI 10.2139/ssrn.6443103; Crossref created 2026-04-07) and CEPR DP21615. Latest version 2026-06-12. Working paper. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6443103 ; data https://huggingface.co/datasets/vgregoire/polymarket-users `[CC-confirmed]` | DESC/IS, wallet level, 2022-11-11 to 2026-03-29: 2,480,104 wallets, 588.3M trades, $67.1B. The top 1% of winners take **76.5%** of winners' gains, and about **69%** of wallets lose. A +1 SD maker-volume share raises Pr(PnL>0) by **9.0 pp**, the largest effect. Persistence is modest: 44% of wallets stop after one month. Maker-heavy user-months are 6.6–11 pp more likely to have a positive next-month Sharpe-analogue. Two wallets the paper describes as charged with MNPI trading rank 115th and 307th, about 0.13% of winners' profits (the case attribution was not verified by the cross-checker). Mostly pre-fee; open positions marked at last trade; no event or calendar clustering; no strategy test. | Working paper, not published. The superseded draft said "top 1% capture 84%" (1.4M users, $20B). The June version says 76.5% of *winners'* profits on 2.48M wallets. The full text was read only via an unofficial mirror, with some tables garbled. Abstract wording differs between Crossref and the PDF ("weakly" vs "modestly" persistent). |
| "The Favorite–Longshot Bias in Prediction Markets: Evidence from Polymarket" | **Yes, exact** (en dash on the PDF; hyphen in the arXiv metadata) | Marcos Cardozo, José Ignacio Rivero-Wildemauwe (Universidad Católica del Uruguay). arXiv:2609.12878v1, 2026-09-11 (only version), econ.GN, 51 pp. Preprint, not peer-reviewed. https://arxiv.org/abs/2609.12878 `[CC-corrected]` (minor) | DESC/IS on Akey et al.'s HF v1.3 data to 2026-03-29. Returns are pre-fee, held to resolution, with event-clustered CIs. **Equal weight per child market:** longshots (<10¢) −6.30% [−8.38, −4.22]; favourites (≥90¢) +0.277%. **Pooled:** longshots −19.35% [−46.99, +8.30], **not significant** (Webb p=0.184); favourites +0.83% [0.60, 1.07]. **Equal weight per parent event:** longshots **+4.09%** [1.29, 6.90]. A two-sided FLB holds only in Crypto and Politics; Sports has none. Takers lose at both tails (−31.17% and −0.460%); makers buying favourites earn +0.641%. The heaviest past longshot buyers earn −21.96% vs −20.33% for others. No strategy, no executable-price test, no out-of-sample period. | The abstract's "19.3¢ per dollar" is insignificant, and the sign reverses under event grouping. A web paraphrase that heavy longshot buyers "don't lose" is wrong. The experience-quintile range is −21.55% to **−44.13%** and is non-monotonic, not "−38.34% to −21.55%". The equal-child to equal-parent change is +10.39 pp in total. |
| "Exploiting Mean-Reversion in Decentralized Prediction Markets: Evidence from Polymarket Binary Contracts" | **Yes, exact** | Radovan Vojtko and Cyril Dujava (Quantpedia, Bratislava, per the blog footer and OpenAlex; Crossref lists no affiliation). First a Quantpedia blog post on 2026-04-17, credited to Dujava alone. Then SSRN 6726362 (DOI 10.2139/ssrn.6726362; Crossref 2026-05-06), preprint. https://quantpedia.com/exploiting-mean-reversion-in-decentralized-prediction-markets-evidence-from-polymarket-binary-contracts/ `[CC-corrected]` | IS SIM. Rule: buy at a new X-day low and hold Y days, over a 12-cell parameter grid. Applied to **3 hand-picked "No" contracts that all resolved No** (Jesus returns, China invades Taiwan, aliens confirmed; all "in 2025"). Data: 10-minute series that match public CLOB `/prices-history` counts, which are mid/trade prices and not executable. Costs: 0 or 10 bp per side. This project's reproduction: China taker fills sat a median **0.565%** from the mid, and at ~0.5% per side no variant beats buy-and-hold. The China and Alien buy-and-hold drawdowns rest on one non-buyable print (2025-12-27 01:10 UTC). In-sample reversal beats random-entry placebos, but is only 0.10–1.46% per trade before costs. | A practitioner preprint, not a peer-reviewed paper. It covers 3 contracts selected with hindsight, not Polymarket binaries in general. The text claims all 12 Jesus variants beat the buy-and-hold Sharpe (1.02), but its own Table 3 shows X20_Y5 (0.68) and X20_Y3 (0.65) below it: **10 of 12**. Its "spread" measure is a 4-hour high–low range, and its cost assumption is about 5–6× too low. It cites Clinton & Huang with the wrong DOI prefix (10.31219; correct 10.31235). It is not evidence of an executable after-cost edge. |

---

## 2. Findings by strategy family

Each family has the same layout:

- **Literature**: established findings, labelled, each with its cross-check tag.
- **Evidence type, fees and execution.**
- **Prospective tradability.**
- **Replicate before risking money.**
- **Our extrapolations**: my own reasoning, kept separate and labelled PLAUSIBLE.

### A. Wallet following and copy trading

**Literature**

| # | Finding | Source | Type | Cross-check |
|---|---|---|---|---|
| A1 | Gains are concentrated and most wallets lose. Top 1% of winners take 76.5%; about 69% of wallets lose; the top 100 hold 27.7% of winners' profits, many of them pure liquidity providers. | [AKEY26](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6443103) | DESC/IS | confirmed |
| A2 | Persistence is modest and attrition heavy: 44% of wallets stop after one month, up to 66% within six months. Maker-heavy user-months: +6.6 to +11 pp Pr(next-month Sharpe-analogue > 0). This is the wallets' own PnL, not a copier's. | AKEY26 | IS, forward-looking transition matrices | confirmed |
| A3 | "Around 3% of all accounts generate the bulk of price discovery" (abstract, VERIFIED). Secondary sources (PLAUSIBLE) add: 1.72M accounts; 44% of skilled accounts stay skilled on a *random* split of events, which is not a time split; likely insiders 967 accounts, 0.2% of volume, 1.3% of profits. A press claim of "12% overlap between top earners and skilled" is **UNSUPPORTED**. | [GC26](https://doi.org/10.2139/ssrn.6617059) | IS | unverifiable |
| A4 | An informed-trading screen flags >210,000 wallet-market pairs: 69.9% with positive realised profit and 75.0% holding the winner, **of resolved pairs**. About $143M realised, "$119M more than execution prices implied". The screen conditions on profitability and timing near resolution, both ex post. Via Macey & Enriques (PLAUSIBLE): the broad pool beats the price-implied win rate by only **0.69 pp** (74.35% vs 75.03%). | [MO26](https://doi.org/10.2139/ssrn.7259741); [ME26](https://www.ecgi.global/sites/default/files/2026-08/different-markets.pdf) | DESC | confirmed (abstract and authors' post) |
| A5 | "Execution, not information": retail picks winners 51.3% of the time yet loses $79M, while automated traders at coin-flip accuracy earn $133M. The venue is not named (PLAUSIBLY Polymarket). A companion paper flags 6,032 of 450,048 wallets (≈$150M); agreement with a behavioural heuristic is κ=0.007. | [DV26a](https://doi.org/10.2139/ssrn.6191618); [DV26b](https://doi.org/10.2139/ssrn.6567238) | unknown (abstract) | confirmed / unverifiable |
| A6 | Polymarket copy trades beat the same follower's own non-copy trades in the same market by 1.62 pp. There is no price benchmark, fee, latency or definition of a copy trade, so this does **not** show that copying is profitable. | [OLI26](https://doi.org/10.2139/ssrn.6670318) | unknown (abstract) | unverifiable |
| A7 | Classic base rates. **Taiwan day traders** (published version): fewer than 1% predictably earn positive net returns; the top 500 earn 61.3 bp/day gross and 37.9 bp net; ranking is on the prior-year Sharpe ratio of net returns. **US retail**: copying from the day after the trade earns about 5.1 bp/day 4-factor alpha before costs (significant at 5%, not 1%), gone at one month. **Mutual funds**: the 2005 WP finds 1.9% with truly positive alpha; the JF 2010 abstract says about 75% have zero alpha and almost no skilled funds remain by 2006. | [BLLO14](https://doi.org/10.1016/j.finmar.2013.05.006); [CHS21](https://doi.org/10.1093/rapstu/raab017); [BSW10](https://doi.org/10.1111/j.1540-6261.2009.01527.x) | OOS (BLLO, CHS); method (BSW) | all corrected |
| A8 | Copying disclosed holdings (copycat funds), high-expense sample: before the funds' expenses, copycats trail by 42 bp over six months. Broader sample (N=847): after expenses, copycats lead by 25 bp, which is significant (t=−2.49). Copycats are charged index-fund expenses. | [FPSS04](https://www.nber.org/system/files/working_papers/w8653/w8653.pdf) | SIM, OOS 6 months | corrected |
| A9 | Copiers pay an execution penalty. On a bonding curve an immediate copier strictly overpays (Theorem 2). Statistically selected memecoin leaders had positive returns, but their copiers lost about 6–8% (values read from a figure). The 1% fee is **not** visible in the copier model. | [LUO26](https://arxiv.org/abs/2601.08641) (WWW'26) | OOS SIM (temporal split) | corrected |
| A10 | Leaderboards select lucky risk-takers. In the lab, 35% of subjects copy, and 88% of copiers copy someone who chose the riskiest asset. In the field, the top 5% of leaders hold 61.1–92.8% of copy relationships. Copiers being more risk-averse is only weakly significant. | [AOW20](https://doi.org/10.1287/mnsc.2019.3508) | lab experiment (2017) + DESC | corrected |
| A11 | Size is not information. The largest directional Intrade account lost **$6,882,186** while holding a price "firewall". 87% of traders never switch direction. Arbitrageurs are 1% of traders and 16% of volume. | [RS16](https://doi.org/10.5750/jpm.v10i1.1179) | DESC | confirmed |
| A12 | Informed flow concentrates in single-name contracts (Kalshi). In the top-VPIN quintile of single-name markets, YES-directed flow settles YES 35.9% of the time vs 22.0% for NO-directed flow (t=12.44). In broad markets the rates are 50.0% vs 50.2%. The quintile breakpoints are formed in-sample. No taker follow-the-flow strategy is tested. | [BO26](https://conference.nber.org/conf_papers/f243677.pdf) | IS | corrected |
| A13 | Followers arrive too late in liquid markets. Deep Betfair markets price goals "swiftly and fully", and half-time round trips at the best quotes are unprofitable. In Kalshi NBA, the mid drifts predictably, but buying at the ask and selling at the bid five minutes later loses. Courtsiders widen Betfair spreads, and a follower is on the wrong side of that latency. | [CR14](https://doi.org/10.1111/ecoj.12033); [AD26](https://arxiv.org/abs/2606.07811); [BRO12](https://doi.org/10.1080/00036846.2010.537644) | DESC; IS with an executable-style test | corrected / confirmed / confirmed |
| A14 | Wash trading contaminates activity-based selection. 24.2% of historical *share* volume is flagged, with weekly peaks near 60% (Dec 2024); 14% of wallets have more than half their volume flagged. Akey et al.'s HHI screen flags 3.1% of volume. | [SIR25](https://doi.org/10.2139/ssrn.5714122); AKEY26 | DESC | confirmed |
| A15 | Heavy past longshot buyers are not differently skilled: −21.96% vs −20.33%. | CRW26 Table 10 | DESC | confirmed |

**Legal constraints** (VERIFIED in official documents; relevant to A).
- **First CFTC insider case on event contracts:** a service member's Polymarket trades on "Maduro Out by January 31,
  2026?", with more than 436,000 YES shares and more than $404,000 profit. These are allegations
  ([CFTC26b](https://www.cftc.gov/PressRoom/PressReleases/9217-26)). Speculation that a different figure in Mitts &
  Ofir reflects linked accounts is UNSUPPORTED.
- **Theories of liability:** the CFTC applies misappropriation and scheme-to-defraud theories under Rule 180.1. The two
  cases cited in its advisory were Kalshi's internal sanctions
  ([CFTC26a](https://www.cftc.gov/PressRoom/PressReleases/9185-26)).
- **No parity-of-information rule:** CRS says Rule 180.1 is not a parity-of-information rule
  ([CRS26](https://www.congress.gov/crs-product/LSB11406)).
- **Proposed listing factors:** the NPRM's proposed factors include insider-information risk
  ([CFTC26c](https://www.govinfo.gov/content/pkg/FR-2026-06-12/html/2026-11854.htm)).
- **Copiers:** no source addresses whether copying a public on-chain trade exposes the copier (UNSUPPORTED either way).
  Per CONTEXT.md, this project does not allege insider information from wallet data.

**Evidence type and costs.**
- Polymarket wallet studies are DESC/IS, pre-fee, marked at last trade, with no latency.
- The only time-ordered selection tests are in equities (BLLO14, CHS21) and memecoins (LUO26).
- There is no LIVE evidence.

**Prospective tradability:** not established for Polymarket.

**Replicate before risking money.**
1. Point-in-time ranking that uses only fills and resolutions before the decision.
2. A price-conditioned skill measure: event-level sign randomisation or a price-implied benchmark, not raw win counts.
3. False-discovery control across wallets, reporting π₀ and the expected number of lucky selections (BSW10 method).
4. Time-ordered out-of-sample evaluation.
5. Copy execution at a follower latency (seconds to minutes), at the tape or live book, with current taker fees.
   Report the leader-minus-copier imitation penalty.
6. Exclusion of wash clusters and Sybil clusters.
7. Segmentation by contract type.

**Our extrapolations (PLAUSIBLE, not in any paper).**
- A calibrated bettor who only buys at 0.85 wins five of five with probability 0.85⁵ ≈ 0.44 and has zero edge, so a
  "won 5 of 5" filter mostly selects favourite buyers.
- With about 10⁵ wallets, p < 0.05 alone yields about 5,000 false positives under the null.
- Suspected one-shot insider accounts have no track record to select on, which makes them uncopyable by construction.

### B. Within-market and complete-set arbitrage

**Literature**

| # | Finding | Source | Type | Cross-check |
|---|---|---|---|---|
| B1 | "Realised" arbitrage of $39.59M: ~$10.58M same-condition, ~$29.02M NegRisk, ~$95.2k combinatorial. Inferred from other wallets' fills, with VWAP prices that are carried forward and then zero-filled. Fees ignored. See §1 for the reconciliation gaps. | [SAG25](https://arxiv.org/abs/2508.03474) | DESC/IS | corrected |
| B2 | The NegRisk Adapter converts NO baskets into collateral plus YES. There is no reverse YES→NO conversion, so YES-side violations can only be realised by holding baskets to settlement. **Same window as SAG25: $291,424.** Total mechanism-linked profit about $1.118M ($1.086M converter-enabled, $32,283 settlement baskets), excluding an anomalous $381,748 cluster. Median profit per conversion fell ~$1 → ~$0.20 → **~$0.08** (early 2026). In the 2026 L2 replay: 2,098 positive YES-side vs 36 NO-side episodes; median exact durations **16.15 s** (253 YES) and 7.99 s (5 NO); 366 of 624 episodes span the sampling window. 308,416,666 WebSocket messages show **exactly mirrored YES/NO books** apart from 20 API glitches. Fee-adjusted, assuming taker execution throughout; gas omitted because the relayer pays it. | [GMM26](https://arxiv.org/abs/2608.00666) | DESC, depth-aware and fee-adjusted | confirmed |
| B3 | Polymarket NBA (fee-free at the time): 7 valid in-game single-market episodes in 3,042 markets, median 3.6 s, capped profit $210.19. 30 of 37 raw episodes were post-game artefacts. Median spreads: 392, 1,031 and 7,533 bp pre-game, in-game and post-game. The single-market episodes are PLAUSIBLY feed or projection artefacts (a crossed mirrored book). | [CYZ26](https://arxiv.org/abs/2605.00864) | DESC (top-of-book snapshots every 3.6–5.5 s) | confirmed |
| B4 | "Ghost fills": 2,037,304 reverted match transactions, 994,196 of them attributed to four attack vectors, including **hunting arbitrage bots** that are left holding partial baskets. Up to 24.3% of transactions reverted in peak hours. | [SHEN26](https://arxiv.org/abs/2606.16852) | DESC (security) | NCC |
| B5 | Buying every YES leg of a multi-outcome set costs more than $1. The premium rises by **+0.0595 per log n**, 96% of it from per-leg markup on cheap legs. Prices are last trades. With a ≥100-share floor on each leg the slope is +0.006 (n.s.), so in the paper's words it is "not an arbitrage executable at size". | [ZAN26](https://arxiv.org/abs/2609.20017) App. B.2 | DESC/IS | corrected |
| B6 | Large set violations occur where arbitrage is capped or taxed. **PredictIt:** bids summed to 110–125; after-fee arbitrage existed in 1.9% of markets at any time in 2019–22 ($850 cap, 10% profit fee). Sell-all mispricings above 20¢ lasted 271–433 days on PredictIt against 0 on the IEM (trade-price proxies; not shown executable). **IEM** (complete slates at $1, no fees): no FLB. **Intrade:** a NH-primary set sold for $1.082 and later bought for $0.591. Sums of asks sit further from $1 than sums of bids (153 vs 100 days). | [ZIT26](https://www.nber.org/papers/w35845); [SG20](https://doi.org/10.5750/jpm.v14i1.1796); [BR19](https://doi.org/10.1016/j.ijforecast.2018.03.004); [RP14](https://doi.org/10.3233/AF-140031) | DESC | corrected / corrected / corrected / confirmed |
| B7 | Naive `OrderFilled` sums overstate turnover: $958M naive vs $391M turnover in the Oct 2024 Trump market. | [TY26a](https://arxiv.org/abs/2603.03136) | DESC | NCC |

**Evidence type and costs.**
- Everything is DESC. GMM26's L2 replay (fee-adjusted, depth-walked) and CYZ26's snapshots are the only
  executable-price measurements.
- No paper models latency, queue position, partial fills, ghost-fill reverts or `secondsDelay`.
- There is no OOS and no LIVE evidence.

**Prospective tradability:** no for a retail entrant. Episodes last seconds, competition is visible in shrinking
per-conversion profits, and YES-side baskets lock capital until settlement.

**Replicate before risking money.**
1. Own sub-second WebSocket/L2 capture. The third-party pmxt/PMXT archive is an option; its terms are unchecked.
2. Decode NegRisk Adapter conversions plus split/merge in the same transaction.
3. Apply the per-market `feeSchedule`.
4. Run FOK/FAK latency and fill tests, and measure exposure to reverted legs.
5. Annualise the edge over the lock-up.
6. Account for placeholder and "other" outcomes and UMA dispute risk.
7. Test out of sample on post-V2 (2026-04-28 onward) markets.

**Our extrapolations (PLAUSIBLE).**
- A two-leg complete set bought as taker near p≈0.5 pays 2 × rate × 0.25 per set: **2.0–3.5¢** at rates 0.04–0.07.
  That is larger than most reported quote-level edges.
- A Bronze-tier taker rebate (3%) does not change the sign.
- Avoiding the fee by making one leg turns the trade into a legged, inventory-risk position. It is then no longer
  arbitrage.

### C. Cross-market logical and combinatorial arbitrage

**Literature**

| # | Finding | Source | Type | Cross-check |
|---|---|---|---|---|
| C1 | **2024 election:** 46,360 LLM-screened pairs → 1,576 flagged as dependent → 374 kept by the checker → **13 valid** after manual review (~97% false positives after the checker). **Non-election:** 2,267 pairs, 0 valid. Realised combinatorial profit about **$95.2k**, mostly in low-liquidity moments; the average maximum opportunity is about $100. | SAG25 | DESC | corrected |
| C2 | Moneyline vs spread (NBA, fee-free): 290 executable episodes (279 in-game), median 16 s, **median yield 101 bp**, capped profit $559.59 in total. 76.9% of episodes cannot absorb $100; the average executable size is **14.79 shares**. The "middle" double payout never occurred. | CYZ26 | DESC (L1) | confirmed |
| C3 | Abstract only: 1.9M logical relations over more than 255,000 contracts, with replayed "full-depth Polymarket order books" (source unknown). "**Among settled portfolios**", guaranteed profit after spreads and fees is 2.2% of committed capital, or 3.2% at resolution. No holding period is given. | [ZS26](https://doi.org/10.2139/ssrn.7587019) | SIM (claimed) | unverifiable |
| C4 | Cross-venue equivalents. About 6% of events are multi-listed; median deviations are 2–4% from parity, using mids plus assumed costs. A naive policy shows +1,218.66% over 800 days from 15 trades, which is not executable. The 2024 Polymarket–Kalshi gap (avg ~$0.03, up to $0.07) partly priced resolution-semantics differences. | [GM26](https://arxiv.org/abs/2601.01706) | DESC + naive IS | NCC |
| C5 | Linked contracts lose their bids during news. On Intrade, party < candidate violations appeared (buy Democratic Party at 0.491, sell Obama at 0.501). | RP14 | DESC | confirmed |
| C6 | Fee design and position caps, not information, sustained PredictIt linked-set violations. Maximum 170¢ per share (RNOM, Feb 2016). This conflicts with the paper's own "about zero after Dec 2015" statement. | SG20 | DESC (daily trade proxies) | corrected |
| C7 | Sums of mids drift above par at the same age. The drift is largest at 7–30 days to resolution (+0.081 per log n; Table 6; these are time-to-resolution buckets). | ZAN26 | DESC | corrected |
| C8 | Kalshi cross-game parlays vs the product of leg prices: median ratio 0.991 (2 legs) to 1.223 (10 legs); overall median **0.996**. Data from 29 Apr–13 May 2026 only, with legs at 30–240 min to expiry. | [MOS26](https://arxiv.org/abs/2607.14430) | DESC | corrected |
| C9 | LLM-filtered Granger lead–lag pairs on Kalshi Economics markets. Win rate 54.5% vs 51.4%; frictionless, no significance tests. | [KIM26](https://arxiv.org/abs/2602.07048) | OOS SIM (frictionless) | NCC |

**Evidence type and costs.**
- DESC, apart from ZS26's claimed replay, which could not be verified.
- CYZ26 is fee-free. No paper annualises over the lock-up, and none prices rule-equivalence or dispute risk.

**Prospective tradability:** not established. Edges are small and capital-locking. Pairs need manual validation of
rule text and resolution source.

**Replicate before risking money.**
1. Relation extraction with hand verification of rule text, resolution source and timing.
2. Synchronous executable quotes on every leg.
3. Per-leg fees.
4. Holding-period accounting.
5. UMA dispute and misresolution risk.
6. Ghost-fill exposure.

**Our extrapolations (PLAUSIBLE).**
- **Mid-price legs:** under the current sports rate 0.05·p(1−p), two legs near 0.5 cost about 2.5¢ in taker fees,
  against CYZ26's median edge of about 1¢. They are negative after fees.
- **End-game legs:** legs at 0.93/0.06 cost about 0.6¢. A fraction of the edge survives.
- **Project scan** (`../strategies/logical_arb.md`; project work, not literature): k-of-n constraints gave 3.4–3.6%
  over about 95–100 days. That is the same order as ZS26's abstract figure, or roughly 13% a year simple, before
  dispute risk.

### D. Liquidity provision (market making, rewards)

**Literature**

| # | Finding | Source | Type | Cross-check |
|---|---|---|---|---|
| D1 | Makers out-earn takers on every venue with role data. **Polymarket:** +1 SD maker share → +9.0 pp Pr(PnL>0) (AKEY26); maker favourite buys +0.641% vs taker −0.460% (equal-child, pre-fee; CRW26). **Kalshi:** Jan 2026 version, makers −9.64% vs takers −31.46%; makers buying ≥50¢ +2.6% (SD 33%) ([BDW25](https://www.ifo.de/DocDL/cesifo1_wp12122.pdf)). Takers −1.12% vs makers +1.12%, gross, with trade-level CIs; about three-quarters of taker losses come from "execution within price-direction cells" ([BEC26](https://jbecker.dev/research/prediction-market-microstructure)). **Betfair pre-play:** takers −2.5% vs makers +0.6% (t=11.8 for the difference). Maker returns by decile are **close to zero and insignificant** ([WHE25](https://mpra.ub.uni-muenchen.de/126351/)). | AKEY26, CRW26, BDW25, BEC26, WHE25 | DESC/IS | confirmed / confirmed (minor corr.) / corrected / confirmed / corrected |
| D2 | Where maker profit comes from. In Polymarket BTC 5-minute markets (~24 h, date not stated), 407 persistent makers made +$45.3K and retail lost −$66.7K. **91.4% of maker profit came at resolution** and 8.6% from the spread; buy side ≈ +$70K. Kalshi makers hold to settlement, cross-subsidised by YES-optimistic takers. On Polymarket crypto markets in Jan–Mar 2026, makers carried 95% of gross volume to settlement. | ZAN26 App. B.1; BO26 fn 18 | DESC | corrected / corrected |
| D3 | When makers lose. **TradeSports:** limit orders filled after in-play trade clusters lose more than 1%; pre-event they earn about +1% after fees, partly reflecting commission-free limit orders from 2004-11-09 ([TET08](https://doi.org/10.2139/ssrn.929916)). **Kalshi top-VPIN quintile:** −$12 per bucket and a 51.7% loss rate, vs +$36 to +$46 in Q1–Q4 (BO26). **BTC 5-minute market makers:** +$3.11M gross in normal cycles, −$0.62M in manipulated ones (DJY26). Abstract only: fee-avoiding makers realise −7.39¢ per contract, "because fills arrive only when they are losing" (MOU26). **Betfair:** wider spreads mean bigger losses for both sides, especially on longshots (WHE25). | TET08, BO26, DJY26, MOU26, WHE25 | IS / DESC | confirmed / corrected / confirmed / corrected (abstract) / corrected |
| D4 | Post-V2 costs. Taker effective spread **2.328¢** (equal-fill) and **2.033¢** (share-weighted) per share. These are *full-spread* quantities, so one-way cost is about half. The 5-minute realised spread is 6.486¢ / 1.344¢; impact flips sign with weighting. Fees are excluded, and the 12 days were selected purposively. 92.1–100% of prints match the taker leg; 53.5–73.8% of settlements are mints; the taker buy share is 80.6–85.6%. | [DUB26b](https://arxiv.org/abs/2610.06412) | DESC | confirmed |
| D5 | Direction-free facts: median quoted spread about 400 bp of mid at 0.4–0.6 and 1,300–1,800 bp below 0.10. Top of book holds 13.6% of top-10 depth. About 32 effective makers (HHI 0.031). Self-trade wash share median 0.97%. The paper's *signed* results (effective spread, SF5, Kyle's λ, "59% agreement") are PLAUSIBLY biased by its leg-pooling sign rule. | [DUB26a](https://arxiv.org/abs/2604.24366) | DESC | corrected |
| D6 | Liquidity Rewards: about **$9.3M** paid from 2023-11-25 to 2025-07-24. Peak week $242.4K; the top address received over $1.0M (10.9%); top five about 22%; 46,653 recipients. 69.7% of makers were profitable on *spread capture*, but that measure **excludes settlement P&L**. The thesis states the reward score rises with distance from mid; the official docs say it falls. | [SIN25](https://www.cs.cit.tum.de/fileadmin/w00cfj/sebis/_my_direct_uploads/20250903_Parshant_MA_Thesis.pdf) | DESC | confirmed (with corrections) |
| D7 | Ghost fills were used to farm $13,397.65 in liquidity rewards (1,567 addresses). | SHEN26 | DESC | NCC |
| D8 | Volatility structure (Kalshi). Next-hour variance ≈ p(1−p)/τ + K·ν(V)·s²/4. It beats GARCH by 15% on interval score. Time-to-resolution driver ratio 22.6×. In Sports, 4.1% of hours carry 47.8% of volume. | [XMPW26](https://arxiv.org/abs/2607.08199) | OOS forecasting (not trading) | confirmed |
| D9 | Theory. Spreads widen near settlement at p≈0.5. An inventory-aware quoting policy cuts PnL SD from 28.11 to 10.34 at a similar mean. The model has no adverse selection and uses illustrative parameters. | [FN26](https://arxiv.org/abs/2607.17991) | theory + SIM | confirmed |
| D10 | Fee activation is associated with a Gibbs spread +0.008. The authors call their own t-statistics "implausibly large" and report pre-trends. | [QY26](https://arxiv.org/abs/2606.04217) | DiD | NCC |

**Evidence type and costs.**
- DESC/IS throughout. XMPW26 is out-of-sample but is a forecasting paper, not a trading test.
- All maker returns are conditional on fills. No paper has a queue or fill-probability model.
- No paper combines per-market taker fees, maker rebates (20%, 15% or 25%), Liquidity Rewards and holding rewards.
- AKEY26 and CRW26 are mostly pre-fee. ZAN26 assumes no maker rebate, which conflicts with CONTEXT.md and may be a
  time-period difference (unresolved).

**Prospective tradability:** not established. It is the most supported family *directionally*. Its decisive unknown is
adverse selection of a new, uninformed maker's fills.

**Replicate before risking money.**
1. Fill-level maker markouts at 1 min, 1 h, pre-close and resolution, from `/v2/trades?taker_only=false` with correct
   taker-leg direction (DUB26b).
2. Pre-event vs in-play split using `gameStartTime`.
3. Add maker rebates, `/rewards/markets/*` reward income and holding rewards.
4. Live book capture for queue and fill-probability estimates.
5. Withdrawal rules around events and the final seconds of 5-minute crypto markets.
6. Capital-day returns.
7. Event or expiry-day clustered inference.
8. Post-V2 out-of-sample test.

**Our extrapolations (PLAUSIBLE).**
- The current regime structurally favours makers: zero maker fees plus rebates, against `rate·p(1−p)` for takers. This
  is the only family the 2026 fee changes help.
- The literature consistently implies that an uninformed new maker is adversely selected unless it withdraws around
  news.
- Use XMPW26-style variance to size quotes, not as a signal.

### E. Favourite–longshot bias (FLB)

**Literature**

| # | Finding | Source | Type | Cross-check |
|---|---|---|---|---|
| E1 | **Polymarket tails (Table 6).** Equal-child: longshots −6.30%, favourites +0.277%. Pooled: −19.35% (n.s.) and +0.83%. Equal-parent: +4.09% and +0.392%. Dropping the 1, 5 or 10 largest events moves the pooled longshot return to −15.8%, −14.5% and −10.6%. **Excluding endpoints:** pooled longshots −23.75% (significant), pooled favourites +1.729%, equal-child favourites +0.187%. **By category:** a two-sided FLB only in Crypto and Politics; none in Sports (favourites −0.230% equal-child); the Weather sign flips with weighting. **By role:** takers lose at both tails; makers buying favourites +0.641%. **Mechanism:** misperception fits the interior sign pattern, but tail probability errors are ≤0.53 pp. Large tail *returns* are tiny errors divided by an average price of about 1.17¢. Pre-fee and not annualised. | [CRW26](https://arxiv.org/abs/2609.12878) | DESC/IS, event-clustered CIs | confirmed / corrected |
| E2 | Independent sign pattern: mean (payout − price) per trade runs from −0.0023 (0–0.10) to +0.0098 (0.80–0.90) and +0.0056 (0.90–1.00). Trade-weighted, unclustered, pre-fee. | QY26 §3 | DESC | NCC |
| E3 | Abstract only: "no general market-level longshot bias". Low-probability outcomes are initially underpriced and reverse late; "default outcomes are persistently overpriced". The 2025 paper by the same authors exists, but none of its content was checked. | [RW26](https://doi.org/10.2139/ssrn.7552098); [RW25](https://doi.org/10.2139/ssrn.5910522) | unknown | confirmed (abstract) / NCC |
| E4 | Polymarket calibration slopes: Politics mean 1.45 (compression toward 50%), Sports 1.06, Crypto 1.06. Polymarket timestamps carry about 3 h of noise. The FLB sweep read the main text. | [LE26](https://arxiv.org/abs/2602.19520) | DESC | NCC |
| E5 | **Kalshi.** BDW25: contracts below 10¢ lose over 60%; above 70¢ they earn small, significant positive post-fee returns; the FLB holds at every horizon from 0 to 10 days; weaker in 2025 (ψ 0.021). BEC26: every bucket below 20¢ underperforms, but "the longshot bias proper contributes essentially nothing" to taker losses; most of the loss is execution. MOU26 (abstract only): the FLB premium is cancelled on both sides, by the half-spread for takers and adverse selection for makers. | BDW25, BEC26, MOU26 | DESC/IS | corrected / confirmed / corrected |
| E6 | **Venue design sets the magnitude.** **PredictIt** (capped, profit fee): logit slope 1.501 (yes/no), 1.946 for elections; no decline near elections. It **vanished** in 2025–26 (0.794) after the limit rose 4×. **Intrade:** a 0.20 price paid off 15.3%; the bias is stronger beyond 100 days; OOS +5.25% and +9.55%, erased at 15–25% discount rates, with 2.47% left at 10% (gross, transaction prices) ([PC13](https://doi.org/10.1111/j.1468-0297.2012.02561.x)). **IEM:** no FLB; longshots are *under*priced; a reverse FLB at intermediate horizons. **Betfair pre-play:** last traded prices are unbiased (MZ p=0.211), but taker returns still fall steeply for longshots. **Betfair** also has a lower Shin z (0.90%) than bookmakers ([SPV06](https://doi.org/10.1111/j.1468-0335.2006.00518.x)). **TradeSports:** the FLB is "virtually always positive" and liquidity does not remove it. | ZIT26, PC13, BR19, WHE25, SPV06, TET08 | DESC/IS (+ simple OOS in PC13) | corrected / confirmed / corrected / corrected / confirmed / confirmed |
| E7 | **Racetrack and theory.** Racetrack returns: about −61% at 100/1+ and −5.5% always backing favourites; no positive returns to extreme favourites. Misperception beats risk-love, with an 18.4% lower mean absolute *percentage* error on exactas ([SW10](https://doi.org/10.1086/655844)). The 1986-era favourite profit is gone in later data ([TZ88](https://doi.org/10.1257/jep.2.2.161), via Ziemba 2020). Theory taxonomy: Ali's heterogeneous-beliefs FLB **does** transfer to a CLOB; only the simultaneous-betting and timing mechanisms are parimutuel-specific ([OS08](https://doi.org/10.1016/B978-044450744-0.50009-3)). An uninformed bookmaker shades odds against longshots when facing insiders ([SHIN92](https://doi.org/10.2307/2234526), abstracts). | SW10, TZ88, OS08, SHIN92 | DESC / theory | corrected / confirmed / corrected / confirmed |
| E8 | Polymarket BTC threshold contracts priced **+5.6 pp** above options-implied probabilities (2023), with the largest gap at low probabilities. A 16-trade hedged proxy backtest gives p=0.053, and the pooled alpha CI includes zero. | [POR26](https://arxiv.org/abs/2606.19517) | DESC + IS SIM | confirmed |
| E9 | Exchange-authored Kalshi calibration paper (abstract only): Brier score about 0.08–0.09 at 3 months, about 0.02 at close. A Polymarket/Kalshi "Yes bias" paper (abstract only). | [KB26](https://doi.org/10.2139/ssrn.7355520); [DEL26](https://doi.org/10.2139/ssrn.6322678) | unknown | NCC |

**Evidence type and costs.**
- DESC/IS. The only OOS tests are PC13 (Intrade, gross) and QQ26 (one month; see H).
- CRW26 is pre-fee. BDW25 is post-fee, with only takers paying fees in the Jan 2026 version. WHE25 is post-commission.
- No paper uses Polymarket's current per-market schedule.

**Prospective tradability:** not established.
- Fading longshots depends on the aggregation sign.
- The favourite premium is about the size of the fee.
- The maker-side variant has no fill model.

**Replicate before risking money.**
1. Reproduce CRW26 Tables 6, 8 and 13 from HF v1.3, and check complementary-mint double counting.
2. Maker/taker × category × τ cells, with dollar-weighted P&L after the fee each trade would pay today.
3. Clustering by parent event, calendar day and common underlying (crypto asset, election).
4. Out of sample on post-2026-03-30 `/v2/trades`.
5. Live book capture of 0.90–0.98 quotes for depth and resting-bid fill rates.
6. The worst event loss per cell, plus UMA dispute risk.

**Our extrapolations (PLAUSIBLE).**
- **Taker cost per $** = rate × (1−p):
  - at 0.90: 0.40–0.70%;
  - at 0.95: 0.20–0.35%;
  - at 0.99: 0.04–0.07%.
- **Spread cost:** a 0.01 tick is about 1.05–1.1% of price at 0.90–0.95, so crossing half a 1¢ spread costs about 0.5%.
- **Implication:** taker favourite buying needs a pre-fee edge of roughly 0.6–1.2% per $. No published robust estimate
  reaches that.
- **Venue design:** Polymarket's split/merge at $1 and lack of position limits predict a small FLB. That is consistent
  with CRW26.

### F. Mean reversion and liquidity shocks

**Literature**

| # | Finding | Source | Type | Cross-check |
|---|---|---|---|---|
| F1 | The Quantpedia backtest: 3 hindsight-selected contracts; in-sample grid; 0–10 bp per side; mid prices. See §1 for the internal errors and reproduction. | [VD26](https://doi.org/10.2139/ssrn.6726362) | IS SIM | corrected |
| F2 | Per-market AR(1) on *daily closing-price changes* from 2024-09-01, pooled across IEM, Kalshi, PredictIt and Polymarket by market type (not split by venue). Mean ρ ranges from −0.233 to −0.644. 58.3% of 182 national presidential markets are significantly negative and 0% positive. Last-trade prices, so bid–ask bounce is possible. No trading or cost test. | [CH25](https://doi.org/10.31235/osf.io/d5yx2_v1) | DESC | corrected |
| F3 | Three 2024 political shocks. Debate: +0.04 at 30 min, +0.02 at 3 h (about half reversed). Assassination attempt: +0.05, then +0.10 (continued). Withdrawal: largely anticipated (0.70). A Glosten–Harris transitory component dominates after the debate and a permanent one after the assassination attempt. n=3. | [TY26b](https://arxiv.org/abs/2603.03152) | DESC event study | confirmed |
| F4 | **Uninformed vs informed flow.** Pre-event (uninformed flow), limit orders earn about +1%. In-play, copying the previous market order's direction earns a positive equal-weighted return (continuation). This is a hypothetical return, probably gross. | TET08 | IS | confirmed |
| F5 | Abstract only: in UFC, aggressive order flow predicts *reversal*, "with a magnitude well inside fees" (pre-registered). | [ADA26](https://doi.org/10.2139/ssrn.7194218) | unknown | unverifiable |
| F6 | Betfair EPL **traded** prices every 10 s (not back or lay quotes). After the first goal, the scorer's odds stay mispriced for up to about 5 min. Early favourite goals are overpriced; late longshot goals are underpriced. In-sample in-play ROIs are 10.7–70.4% gross of commission. Pre-match underpriced-favourite regions hold OOS in 2019/20 (gross 51.9% on 175 bets). | [ADS22](https://doi.org/10.1016/j.ijforecast.2021.05.012) | IS + OOS (pre-match) | corrected |
| F7 | Kalshi NBA prices move only 0.64 for 1 on public signals. The predictable mid drift does not survive buying at the ask and exiting at the bid. | AD26 | IS + executable-style test | confirmed |
| F8 | No post-goal drift in deep Betfair markets, and half-time round trips at the best quotes are unprofitable. The paper's statistical efficiency evidence is mixed. | CR14 | DESC + strategy test | corrected |
| F9 | "Reversals" here means changes in which outcome leads, across 79 markets. No P&L. | [SM26](https://arxiv.org/abs/2609.28965) | predictive classification | NCC |

**Evidence type and costs.**
- Mostly IS. The F evidence specific to Polymarket is one hindsight-selected backtest.
- No paper tests reversal at executable Polymarket prices after fees.

**Prospective tradability:** not established.
- Moves carrying news persist.
- Reversals of uninformed shocks are about one spread wide before fees.

**Replicate before risking money.**
1. An unselected universe defined by ex-ante filters, including contracts that resolved against the position.
2. Taker entry at the ask and exit at the bid, from the tape or a live book.
3. A maker variant with a fill model and post-fill markouts.
4. Out-of-sample parameter testing with multiple-testing correction.
5. Checks for one-bar prints.
6. Current fees.
7. Correlation across "nothing happens" contracts.
8. A news vs no-news classifier. There is no public news-timestamp source, which is a gap.

**Our extrapolations (PLAUSIBLE).**
- Normalise move size by √(p(1−p)/τ) (XMPW26) before calling a move an overreaction. That filter is untested.
- Fade only as a maker; a taker would need to clear more than one spread plus the fee.

### G. Public-information and cross-market lead–lag

**Literature**

| # | Finding | Source | Type | Cross-check |
|---|---|---|---|---|
| G1 | **Response latency:** the Polymarket BTC 15-minute UP best bid responds to ≥5 bp/1 s Binance moves after a **median 347 ms** (4,272 of 15,148 moves matched within 2 s). **Clock offset:** source-clock median 16 ms, with ±99 ms of offset ambiguity. **Forecasting:** walk-forward OOS logistic model AUC 0.8377 vs **naive Polymarket mid 0.8405**. **Trading:** simulated trading nets −0.116 normalised payoff units per attempted trade, using 1% fees plus 0.5% slippage, which is probably lenient against today's 0.07·p(1−p). | [YOU26](https://arxiv.org/abs/2607.26245) | OOS + SIM | confirmed |
| G2 | Abstract only. MLB moneylines plus the June 2026 Fed decision: the median cross-venue mid gap is 0.60¢ against a 2.00¢ Kalshi fee. Only **7.03%** of 20,915 aligned minutes clear the fee, with a median life of 1 minute. Deliberate mistiming inflates the edge (fast panel 7.03% → 23.8% at 7 min; slow panel 22.7% → 40.8% at 60 min). Pre-game: 0.00% of 2,617 minutes. Across nine pre-registered theses, no edge. The provenance of the Polymarket quote archive is unverified. | [MOU26](https://doi.org/10.2139/ssrn.7175258) | pre-registered (claimed) | corrected (abstract) |
| G3 | Abstract only. In UFC (281 fights) no venue leads, and gaps close within about 30 minutes. In the 2024 election, Polymarket led Kalshi and large-trade order imbalance predicted returns; this abstract gives no cost treatment. | ADA26; [NPTZ26](https://papers.ssrn.com/abstract=5331995) | unknown | unverifiable / unverifiable |
| G4 | **Historic real gaps.** **Intrade vs Betfair 2012** (actual trading): $3,686 for +6.38% over 3 months after transaction costs; the authors estimate $15–20k extractable over the final months. Intrade's lagged price strongly predicts Betfair's; Betfair's lags have small but significant coefficients. **Bookmakers vs Betfair:** arbitrage in 19.2% of matches, averaging 1.4%; bookmakers restrict winning accounts ([FVN13](https://doi.org/10.1111/ecca.12009)). | RP14; FVN13 | **LIVE** (RP14) + DESC | confirmed / confirmed |
| G5 | **News absorption.** Deep Betfair: immediate. Kalshi NBA: about 0.64 for 1 on impact, but not tradable after the spread. Betfair tennis courtsiding: spreads widen in tie-breaks, and the 1–5 s bet delay is insufficient or is perceived to be. | CR14; AD26; BRO12 | DESC/IS | corrected / confirmed / confirmed |
| G6 | A Binance → Chainlink → Polymarket settlement channel is exploited by final-seconds pushes. This is market manipulation and **excluded** as a strategy. The effect is largely absent in 15-minute contracts. | DJY26 | natural experiment + DESC | confirmed |
| G7 | Mid-based cross-venue deviations (2–4%) and the LLM lead–lag paper. | GM26; KIM26 | DESC / SIM | NCC |

**Evidence type and costs.**
- YOU26 is the only Polymarket OOS SIM. RP14 is the only LIVE result, on a defunct venue.
- Polymarket-side prices elsewhere are mids, trades or unverified archives.

**Prospective tradability:** no for a retail trader.
- The crypto lag is sub-second.
- Cross-venue gaps mostly vanish at synchronised executable quotes (abstract-level).
- Kalshi access raises a regulatory or geographic question outside the literature.

**Replicate before risking money.**
1. Quotes on both venues sampled within seconds of each other, with the edge measured at asks and bids, not mids.
2. A latency budget that includes taker order delays and sports `secondsDelay`.
3. A resolution-rule equivalence audit.
4. Both venues' current fees.

**Our extrapolations (PLAUSIBLE).**
- A retail stack (home internet, REST polling) is structurally slower than the ~350 ms quote response in YOU26.
- Information-speed strategies are therefore unavailable to a retail trader.

### H. Near-resolution convergence

**Literature**

| # | Finding | Source | Type | Cross-check |
|---|---|---|---|---|
| H1 | BTC 5-minute markets: the upper boundary is calibrated (average price 0.982 vs 98.4% wins). The lower boundary is overpriced (0.024 vs 1.4%). Last-trade prices. | ZAN26 App. B.1 | DESC | corrected |
| H2 | In the [0.90, 1.00) bin, a final-seconds Binance push against the favourite makes the underdog win **34.2%** of the time, against 1.0% in normal cycles. Manipulated cycles cluster overnight, at weekends and near the money. The 821 "manipulators" are selected on outcome. Crypto up/down resolution changed on 2026-08-07, per DUB26b, which may alter this. | DJY26 | DESC | confirmed |
| H3 | **Late in-play sports.** **Betfair:** by the 105-minute timestamp, bottom-decile takers lose about 70%. In the second half, takers on high-probability bets, including lays of longshots, earn small, significant profits. In-sample, CIs not stated as match-clustered, no bet-delay model. **Kalshi:** in the final 10 minutes, contracts at 10–40¢ "resolve favorably almost never". But time-to-expiry is measured to the *realised* game end (look-ahead), and there is no game clustering. | WHE25; MOS26 | IS / DESC | corrected / corrected |
| H4 | **Weather.** Favourites (0.75–0.95) are overpriced 1–12 h before the daily peak: about −0.10 at 6 h, and −11.2 pp in the 70–90% bin. In the July 2026 OOS test, Buy-NO in the favourite window gave 184 trades and a post-fee ROI of +50.71% (CI [1.76, 102.98]¢ per $). Prices are mean taker prices, with no depth or spread; the code is not public; the mechanism is only hedged by the authors. CRW26 instead finds Weather favourites ≥0.90 *under*priced (+0.502% equal-child; pooled +0.031% n.s.). The price bands, horizons and periods differ. | [QQ26](https://arxiv.org/abs/2610.13593); CRW26 | IS + 1-month OOS | confirmed |
| H5 | **Time to expiry.** Calibration tightens toward resolution, but Tech, Culture and Weather deviate even one day out (figure only; AKEY26). The FLB is stronger at long horizons because collateral earns nothing (PC13). The Kalshi FLB holds at every horizon from 0 to 10 days (BDW25). Abstract only: low-probability outcomes are initially underpriced and reverse late (RW26). Polymarket longshots in markets closing ≤1 day after purchase: pooled −10.86%, equal-child −13.14%, equal-parent −0.90% (CRW26 Table 14). The IEM shows prices above payoffs for $0.80–1.00 at 4- and 14-day horizons, and efficiency at 1–2 days (BR19). | AKEY26, PC13, BDW25, RW26, CRW26, BR19 | DESC/IS | mixed (see §3) |
| H6 | Volatility rises sharply in the final hours (Kalshi). Theory: spreads widen near settlement at p≈0.5. | XMPW26; FN26 | OOS forecasting; theory | confirmed |
| H7 | End-game extreme-price combinatorial episodes keep part of their edge (fee-free sample). | CYZ26 | DESC | confirmed |

**Evidence type and costs.**
- DESC/IS. QQ26 is the only post-fee Polymarket OOS test, on one month at non-executable prices.
- There is no executable-price study of 95–99¢ Polymarket contracts by time to resolution.

**Prospective tradability:** not established.
- The upper tail is about calibrated, which leaves the edge after fees near zero.
- Flip, dispute and misresolution tail risk is unpriced.

**Replicate before risking money.**
1. Price bucket × τ × category × role cells, dollar-weighted after today's fees, event-clustered, with the worst event
   loss reported.
2. Live depth at 0.95–0.99.
3. `umaResolutionStatus` dispute base rates.
4. Exclusion or stress test of 5-minute crypto against settlement pushes.
5. Game clock, not realised end, for sports.
6. `secondsDelay`.
7. Weather tested at executable asks across seasons.

**Our extrapolations (PLAUSIBLE).**
- At p=0.98 the Crypto taker fee is 0.07 × 0.98 × 0.02 ≈ 0.14¢ per share, against a ~0.2¢ gross calibration gap
  (H1). Net is about zero.
- At 0.95, one loss wipes out about 19 wins.

---

## 3. Per-paper reference list (with cross-check verdict)

Format: **Key**: authors (year). *Title*. Status, IDs, primary link. Read depth. **Cross-check** verdict and the
material corrections applied.

Read depth is the best reading achieved across the notes and the cross-check:
- **full**: the whole text, or essentially all of it;
- **partial**: named sections only;
- **abstract**: abstract or official summary only.

### 3.1 Polymarket arbitrage, execution and data

- **SAG25**: Saguillo, O.; Ghafouri, V.; Kiffer, L.; Suarez-Tangil, G. (2025). *Unravelling the Probabilistic Forest:
  Arbitrage in Prediction Markets*.
  - AFT 2025, LIPIcs 354, Art. 27, pp. 27:1–27:24, DOI 10.4230/LIPIcs.AFT.2025.27. arXiv:2508.03474v1 (2025-08-05).
    https://arxiv.org/abs/2508.03474
  - Read: full (arXiv and LIPIcs).
  - **Cross-check: corrected.** Reconciliation gaps (−$9,630 / −$104,787). The LLM test was on 128 NegRisk Politics
    markets. Fig. 9 says "11 pairs". Venue dates are per the IMDEA record. The wrong-emitter point holds (ABIs).
- **GMM26**: Gebele, J.; Mutzel, T.; Matthes, F. (2026). *Executable Arbitrage and Market Efficiency in Prediction
  Markets*.
  - arXiv:2608.00666v1 (2026-08-01), preprint. https://arxiv.org/abs/2608.00666
  - Read: full main text and App. A. Apps. B–G were not read by the entry author; the sweep reports reading them.
  - **Cross-check: confirmed.** Panel 1 is 51 FPMM-era hand-derived sets, not NegRisk. "$39.6M" is the summariser's
    sum of the paper's $10.6M + $29M. Midpoint imputation applies to split-minted positions. The empirical sweep
    flags that the v1 PDF drops the text after "%" in some sentences, and that 2,134 positive episodes are not
    reconciled with 624 timed episodes.
- **CYZ26**: Cheng, G.; Yang, J.; Zou, H. (2026). *Arbitrage Analysis in Polymarket NBA Markets*.
  - arXiv:2605.00864v1 (2026-04-22); SSRN 6624718 (Crossref order Yang, Cheng, Zou). https://arxiv.org/abs/2605.00864
  - Read: full.
  - **Cross-check: confirmed.** The single-market episodes are PLAUSIBLY artefacts. §3.1 misdescribes the data source
    as "Polygon blockchain". The title page is dated 2026-05-05.
- **SHEN26**: Shen, Y.; Jin, Y.; Wu, S.; Wang, Y.; Chen, J. (2026). *The Ghosts of Polymarket: When Off-Chain Matches
  Meet On-Chain Reverts*.
  - arXiv:2606.16852 (v1 2026-06-15; v2 2026-10-10). https://arxiv.org/abs/2606.16852
  - Read: abstract and related work (entry); the sweep read the intro, RQ1–2 and attack cases.
  - **NCC.**
- **TY26a**: Tsang, K. P.; Yang, Z. (2026). *The Anatomy of a Blockchain Prediction Market: Polymarket in the 2024
  U.S. Presidential Election*.
  - arXiv:2603.03136 (v3 2026-09-14); SSRN 6336679. https://arxiv.org/abs/2603.03136
  - Read: abstract (entry); the sweep read the intro and data.
  - **NCC.**
- **ZS26**: Zhai, D.; Shi, H. (2026). *Combinatorial Arbitrage in Prediction Markets*.
  - SSRN 7587019 (Crossref record 2026-10-10; posting date unconfirmed). https://doi.org/10.2139/ssrn.7587019
  - Read: abstract.
  - **Cross-check: unverifiable.** The 2.2% figure is "among settled portfolios".
- **GM26**: Gebele, J.; Matthes, F. (2026). *Semantic Non-Fungibility and Violations of the Law of One Price in
  Prediction Markets*.
  - arXiv:2601.01706v1 (2026-01-05). https://arxiv.org/abs/2601.01706
  - Read: partial.
  - **NCC.**
- **QY26**: Qin, B.; Yang, R. (2026). *Polymarket-v1 Database*.
  - arXiv:2606.04217v2 (2026-06-08); SSRN 6870538. https://arxiv.org/abs/2606.04217
  - Read: partial (§§1–3, 5).
  - **NCC.**
- **DUB26b**: Dubach, P. D. (2026). *Measuring Trade Direction in a Prediction Market: Settlement Ground Truth and
  Trading-Cost Measurement on Polymarket*.
  - arXiv:2610.06412v1 (2026-10-05); Zenodo 10.5281/zenodo.23164515. https://arxiv.org/abs/2610.06412
  - Read: partial (§§1–6, App. D.1).
  - **Cross-check: confirmed.** Spreads are full-spread quantities, so one-way cost is about half. Calling this the
    "best public estimate" is opinion. The 59% vs 0.942 contrast is not like-for-like; the buy-share conflict is real.
    Also lists the 2026-07-02 World Cup tick change.
- **DUB26a**: Dubach, P. D. (2026). *The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from
  the Polymarket Order Book*.
  - arXiv:2604.24366v2 (2026-05-14); SSRN 6658364. https://arxiv.org/abs/2604.24366
  - Read: full.
  - **Cross-check: corrected.** The buy/sell asymmetry conflict with DUB26b is VERIFIED. That the signed results
    (including SF5, Kyle's λ and the 59%) are biased is PLAUSIBLE. The direction-free facts stand.
- **YOU26**: Young, G. (2026). *OpenMarket: A Synchronized Polymarket–Binance Dataset for High-Frequency
  Prediction-Market Research*.
  - arXiv:2607.26245v1 (2026-07-28). Data: HF `gregyoung14/openmarket-btc-polymarket`. https://arxiv.org/abs/2607.26245
  - Read: full.
  - **Cross-check: confirmed.** The p5/p95 figures are in Fig. 5. The bootstrap was diagnostic only; the main safeguard
    is the walk-forward design. The fee-leniency point is PLAUSIBLE. The GitHub repo is unverified (403).

### 3.2 Polymarket wallets, profits, manipulation, informed trading

- **AKEY26**: Akey, P.; Grégoire, V.; Harvie, N.; Martineau, C. (2026). *Who Wins and Who Loses in Prediction Markets?
  Evidence from Polymarket*.
  - SSRN 6443103 (DOI 10.2139/ssrn.6443103); CEPR DP21615. Version 2026-06-12.
    https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6443103
  - Read: full, via an unofficial mirror (some tables garbled).
  - **Cross-check: confirmed** (both entries). The CFTC case attribution of the two wallets was not verified.
- **CRW26**: Cardozo, M.; Rivero-Wildemauwe, J. I. (2026). *The Favorite–Longshot Bias in Prediction Markets: Evidence
  from Polymarket*.
  - arXiv:2609.12878v1 (2026-09-11). https://arxiv.org/abs/2609.12878
  - Read: full (sibling note and cross-checker).
  - **Cross-check: confirmed / corrected.** Experience-quintile range −21.55% to −44.13%. Table 7 total +10.39 pp. The
    tick-plus-fee comparison applies at 0.90–0.95.
- **QQ26**: Qiu, S.; Qiu, H. (2026). *Time-Varying Favorite-Longshot Bias in Polymarket Weather Markets*.
  - arXiv:2610.13593v1 (2026-10-09). The arXiv comment claims IEEE ICDM 2026 Teen Track; the venue exists, acceptance
    is PLAUSIBLE. https://arxiv.org/abs/2610.13593
  - Read: full.
  - **Cross-check: confirmed.** The mechanism is the authors' hedged interpretation. The repo returns 404.
- **SIR25**: Sirolly, A.; Ma, H.; Kanoria, Y.; Sethi, R. (2025/2026). *Network-Based Detection of Wash Trading*.
  - SSRN 5714122 (DOI 10.2139/ssrn.5714122; revised 2026-01-17). https://doi.org/10.2139/ssrn.5714122
  - Read: partial, from third-party copies.
  - **Cross-check: confirmed.** ζ=0.001 is also needed for replication. Wallet counts are inconsistent (1.26M vs 1.33M).
    There is no headline dollar-volume share.
- **DJY26**: Dai, D.; Jia, R.; Yu, S. (2026). *Settlement Manipulation in Prediction Markets*.
  - arXiv:2606.31675v1 (2026-06-30). https://arxiv.org/abs/2606.31675
  - Read: partial.
  - **Cross-check: confirmed.** Manipulators are selected on outcome: +$7.41M at ≥10 cycles, +$6.33M at ≥20. The panels
    are cycle × 10 s bins. "Makers should withdraw" is an inference, not the paper's claim.
- **GC26**: Gómez-Cram, R.; Guo, Y.; Jensen, T. I.; Kung, H. (2026). *Prediction Market Accuracy: Crowd Wisdom or
  Informed Minority?*
  - SSRN 6617059 (Crossref 2026-04-24; redeposited 2026-06-25). https://doi.org/10.2139/ssrn.6617059
  - Read: abstract plus secondary summaries.
  - **Cross-check: unverifiable.** The "12% overlap" claim is UNSUPPORTED. The sample period is inconsistent across
    secondary sources.
- **MO26**: Mitts, J.; Ofir, M. (2026). *From Iran to Taylor Swift: Informed Trading in Prediction Markets*.
  - SSRN 6426778 (on or before 2026-03-25) and SSRN 7259741 (2026-08-11). https://doi.org/10.2139/ssrn.7259741
  - Read: abstracts plus the authors' HLS Forum post.
  - **Cross-check: confirmed.** Rates are "of resolved pairs"; v1 called 69.9% a "win rate". The Oct-2024 dating of the
    Iran strike in Nechepurenko's arXiv papers is VERIFIED as an error.
- **DV26a**: Della Vedova, J. (2026). *Who Profits from Prediction Markets? Execution, not Information*.
  - SSRN 6191618 (Crossref 2026-03-10). https://doi.org/10.2139/ssrn.6191618
  - Read: abstract.
  - **Cross-check: confirmed** (abstract). It may earlier have been titled "Picking winners and losing money". The
    platform is PLAUSIBLY Polymarket.
- **DV26b**: Della Vedova, J. (2026). *Detecting Informed Trading in Prediction Markets: An Orthogonality Test*.
  - SSRN 6567238 (Crossref 2026-04-20). https://doi.org/10.2139/ssrn.6567238
  - Read: abstract.
  - **Cross-check: unverifiable.** The venue is not named. The CBOE data are used for a dealer-market sign-flip test.
- **OLI26**: Oliphant, P. (2026). *The Return to Imitation: Evidence from Copy Trading on Polymarket*.
  - SSRN 6670318 (Crossref 2026-04-28). https://doi.org/10.2139/ssrn.6670318
  - Read: abstract.
  - **Cross-check: unverifiable.** Any claim of tradable copying is UNSUPPORTED.
- **ZAN26**: Zang, C.; Andrade, G. P.; Nakajima, T. (2026). *Who Aggregates Information? Screening, Rent, and the
  Coexistence of CLOB and AMM Prediction Markets*.
  - arXiv:2609.20017v1 (2026-09-17). https://arxiv.org/abs/2609.20017
  - Read: intro and App. B full; theory skimmed.
  - **Cross-check: corrected.** The size floor kills the *set-premium* slope, not the centre drift. Table 6 buckets are
    by time to resolution. The 56.8% figure is in the text. "Pre-registered" is weak. Flat fee rates conflict with
    CONTEXT.md. The set premium is not executable at size.
- **TY26b**: Tsang, K. P.; Yang, Z. (2026). *Political Shocks and Price Discovery in Prediction Markets: Evidence from
  the 2024 U.S. Presidential Election*.
  - arXiv:2603.03152v4 (2026-07-18). https://arxiv.org/abs/2603.03152
  - Read: full.
  - **Cross-check: confirmed.** The minted-share evidence is in Table 7 (0.66).
- **VD26**: Vojtko, R.; Dujava, C. (2026). *Exploiting Mean-Reversion in Decentralized Prediction Markets: Evidence
  from Polymarket Binary Contracts*.
  - Quantpedia blog 2026-04-17; SSRN 6726362. https://doi.org/10.2139/ssrn.6726362
  - Read: full (blog).
  - **Cross-check: corrected.** 10 of 12 variants beat buy-and-hold Sharpe, not 12. Crossref lists no affiliations.
- **SM26**: Sultan, O.; Morstatter, F. (2026). *The Conversation Turns First: Crowd Discussion and Price Reversals in
  Prediction Markets*.
  - arXiv:2609.28965v1 (2026-09-24). https://arxiv.org/abs/2609.28965
  - Read: abstract.
  - **NCC.**
- **RW25**: Reichenbach, F.; Walther, M. (2025). *Exploring Decentralized Prediction Markets: Accuracy, Skill, and Bias
  on Polymarket*.
  - SSRN 5910522 (Crossref 2025-12-13; revised 2026-05-24). https://doi.org/10.2139/ssrn.5910522
  - Read: none (existence only).
  - **NCC.**
- **RW26**: Reichenbach, F.; Walther, M. (2026). *When Can Prediction Market Prices Be Trusted? Price Informativeness,
  Calibration, and Bias on Polymarket*.
  - SSRN 7552098 (2026-10-02). https://doi.org/10.2139/ssrn.7552098
  - Read: abstract.
  - **Cross-check: confirmed** (abstract).
- **LE26**: Le, N. A. (2026). *Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics in Prediction Markets*.
  - arXiv:2602.19520 (v2 2026-08-04). https://arxiv.org/abs/2602.19520
  - Read: abstract (entry); main text (FLB sweep).
  - **NCC.**
- **SIN25**: Singh, P. (2025). *Market Making Mechanisms and Liquidity Dynamics in Blockchain-Based Prediction Markets*.
  - MSc thesis, TU Munich, 2025-09-03. Supervisor J. Gebele; advisor Prof. F. Matthes. Not peer-reviewed.
    https://www.cs.cit.tum.de/fileadmin/w00cfj/sebis/_my_direct_uploads/20250903_Parshant_MA_Thesis.pdf
  - Read: full.
  - **Cross-check: confirmed.** The $0.023 is a realised spread from opposing same-maker trades within 1 h. The thesis
    itself says rewards were "not overly concentrated". Its reward-formula statement is wrong.
- **POR26**: Portnaya, V. (2026). *Do Prediction Markets Match Option Prices? Bitcoin Threshold Evidence from Binance
  and Polymarket*.
  - arXiv:2606.19517v1 (2026-06-17). https://arxiv.org/abs/2606.19517
  - Read: full.
  - **Cross-check: confirmed.** Polymarket prices are the latest quote or trade. Polymarket costs are unspecified. The
    pooled alpha CI includes zero.

### 3.3 Kalshi, PredictIt, IEM, Intrade, Betfair, classic FLB, theory and multi-venue

- **BDW25**: Bürgi, C.; Deng, W.; Whelan, K. (2025/2026). *Makers and Takers: The Economics of the Kalshi Prediction
  Market*.
  - CESifo WP 12122; SSRN 5502658; CEPR DP 20631; GWU WP 2026-001; MPRA 126350. UCD WP 25/19 is unverified.
    https://www.ifo.de/DocDL/cesifo1_wp12122.pdf ; Jan 2026 author version at karlwhelan.com/Papers/Kalshi.pdf
  - Read: full (both versions, by the cross-checker).
  - **Cross-check: corrected.** In the Jan 2026 text only takers pay fees. Makers −9.64%, takers −31.46%. Makers buying
    ≥50¢ +2.6%. The γ/δ model is replaced by belief-sorting (β≈0.09, θ=0.6, σ≈0.107). The earlier "maker-fee error"
    claim is dropped.
- **BEC26**: Becker, J. (2026). *The Microstructure of Wealth Transfer in Prediction Markets*.
  - Web paper 2026-01-18; SSRN 7217640 (2026-08). https://jbecker.dev/research/prediction-market-microstructure
  - Read: full (web).
  - **Cross-check: confirmed.** The mirrored ±1.12% and the ratio-type "mispricing" are inconsistent with the stated
    formulas (PLAUSIBLE).
- **BO26**: Bartlett, R.; O'Hara, M. (2026). *Adverse Selection in Prediction Markets: Evidence from Kalshi*.
  - SSRN 6615739; version 2026-07-02. https://conference.nber.org/conf_papers/f243677.pdf
  - Read: full.
  - **Cross-check: corrected.** Q1–Q4 range is +$36 to +$46. λ β = 0.000114. VPIN quintile breakpoints are formed
    in-sample.
- **AD26**: Angelini, G.; De Angelis, L. (2026). *When Do Markets Fully Process Public Information? Evidence from
  Real-Time Prediction Markets*.
  - arXiv:2606.07811v1 (2026-06-05). https://arxiv.org/abs/2606.07811
  - Read: full.
  - **Cross-check: confirmed.** Fees are mentioned but not modelled.
- **XMPW26**: Xi, W.; Moallemi, C. C.; Pai, M.; Wang, S. (2026). *Volatility in Prediction Markets: A Structural
  Approach*.
  - arXiv:2607.08199v3 (2026-10-13). https://arxiv.org/abs/2607.08199
  - Read: full (mostly).
  - **Cross-check: confirmed.** The F tag is dropped (no return signal). Kalshi-only; transfer to Polymarket is untested.
- **MOS26**: Moshrefi, N. (2026). *Prices, Probabilities, and Parlays: Systematic Bias in Sports Prediction Markets*.
  - arXiv:2607.14430v1 (2026-07-15). https://arxiv.org/abs/2607.14430
  - Read: full.
  - **Cross-check: corrected.** Miscalibration is U-shaped. Parlays cover a 15-day window, with overall median 0.996.
    Time to expiry is measured to the realised end (look-ahead).
- **KB26**: Kagan, N.; Baiocchi, R. (Kalshi Research) (2026). *Calibration in Prediction Markets: Theory and Evidence*.
  - SSRN 7355520. https://doi.org/10.2139/ssrn.7355520
  - Read: abstract. Exchange-authored.
  - **NCC.**
- **DEL26**: Deleep, A.; Lee, J.; Bai, J.; Suresh, D.; Dhawan, H. (2026). *How Wise is the Crowd? Bias and Edge in
  Prediction Markets*.
  - SSRN 6322678. https://doi.org/10.2139/ssrn.6322678
  - Read: abstract.
  - **NCC.**
- **KIM26**: Kim, S.; Kim, M.; Kwon, J.; Kim, Y.; Kagan, N.; Lee, J. W.; Levy, O.; Lopez-Lira, A.; Lee, Y.; Choi, C.
  (2026). *LLM as a Risk Manager: LLM Semantic Filtering for Lead-Lag Trading in Prediction Markets*.
  - arXiv:2602.07048v2. https://arxiv.org/abs/2602.07048
  - Read: full.
  - **NCC.**
- **MOU26**: Moulinier, G. (2026). *Mistiming is not Arbitrage: A Pre-registered Falsification of Cross-Platform
  Prediction-market Arbitrage, and the Two-sided Cancellation of the Favourite-longshot Premium*.
  - SSRN 7175258 / 7170178 (2026-08-05). https://doi.org/10.2139/ssrn.7175258
  - Read: abstract.
  - **Cross-check: corrected** (abstract-level). The mistiming figures come from two different panels. The mean net
    edge turns positive only at about 1 h of mistiming. The archive provenance is unverified.
- **ADA26**: Adamczewski, M. (2026). *Integration Without Leadership: Cross-Venue Price Discovery in UFC Prediction
  Markets*.
  - SSRN 7194218. https://doi.org/10.2139/ssrn.7194218
  - Read: abstract.
  - **Cross-check: unverifiable.** The mechanism is the authors' suggestion.
- **NPTZ26**: Ng, H.; Peng, L.; Tao, Y.; Zhou, D. (2025/2026). *Price Discovery and Trading in Modern Prediction
  Markets*.
  - SSRN 5331995 (revised late April 2026). https://papers.ssrn.com/abstract=5331995
  - Read: abstract.
  - **Cross-check: unverifiable.** The abstract may be the 2025 version. There is no cost treatment. The A tag is a
    stretch.
- **ZIT26**: Zitzewitz, E. (2026). *Limits to Arbitrage and Prediction Market Efficiency: the Case of PredictIt*.
  - NBER WP 35845, DOI 10.3386/w35845. https://www.nber.org/papers/w35845
  - Read: full.
  - **Cross-check: corrected.** Quotes are near-minute (~57 per hour), not hourly. $45–90 is an example profit, not a
    cap. The 3+-outcome text factor 1.14 vs the table's 1.423 is inconsistent.
- **SG20**: Stershic, A.; Gujral, K. (2020). *Arbitrage in Political Prediction Markets*.
  - J. Prediction Markets 14(1):69–99, DOI 10.5750/jpm.v14i1.1796. https://doi.org/10.5750/jpm.v14i1.1796
  - Read: full.
  - **Cross-check: corrected.** Coverage is broader than first stated. "About zero after Dec 2015" conflicts with the
    170¢ maximum in Feb 2016. Quantpedia's "0.55 USD" is the −54.7¢ margin-linking coefficient. Not shown executable.
- **RP14**: Rothschild, D.; Pennock, D. M. (2014). *The extent of price misalignment in prediction markets*.
  - Algorithmic Finance 3(1–2):3–20, DOI 10.3233/AF-140031. https://researchdmr.com/files/PriceMisalignment.pdf
  - Read: full (mostly).
  - **Cross-check: confirmed.** Betfair's lags are small but significant. The authors' capacity estimate is
    $150–200/day net.
- **RS16**: Rothschild, D. M.; Sethi, R. (2016). *Trading Strategies and Market Microstructure: Evidence from a
  Prediction Market*.
  - J. Prediction Markets 10(1):1–29, DOI 10.5750/jpm.v10i1.1179.
    https://researchdmr.com/files/JournalofPredictionMarkets2016WP.pdf
  - Read: full (2015 WP).
  - **Cross-check: confirmed.**
- **TET08**: Tetlock, P. C. (2008). *Liquidity and Prediction Market Efficiency*.
  - SSRN 929916 (May 2008 version; first-posted date unverified). https://doi.org/10.2139/ssrn.929916
  - Read: full (mostly).
  - **Cross-check: confirmed.** IV effects in 4 of 6 regressions, mainly financial events. Market-order gains narrowly
    exceed the 0.8% round trip.
- **PC13**: Page, L.; Clemen, R. T. (2013). *Do Prediction Markets Produce Well-Calibrated Probability Forecasts?*
  - Economic Journal 123(568):491–513, DOI 10.1111/j.1468-0297.2012.02561.x.
    https://doi.org/10.1111/j.1468-0297.2012.02561.x
  - Read: full.
  - **Cross-check: confirmed.** Slope 1.25 is an analyst conversion of c=0.80. The strategies are long-short. 2.47%
    remains at a 10% discount rate.
- **BR19**: Berg, J. E.; Rietz, T. A. (2019). *Longshots, Overconfidence and Efficiency on the Iowa Electronic Market*.
  - IJF 35(1):271–287, DOI 10.1016/j.ijforecast.2018.03.004. WP: https://www.biz.uiowa.edu/faculty/trietz/papers/Longshots.pdf
  - Read: full (Feb 2018 WP).
  - **Cross-check: corrected.** The WP circulated by 2002. Student-only markets with a $500 cap.
- **WHE25**: Whelan, K. (2025). *Agreeing to Disagree: The Economics of Betting Exchanges*.
  - MPRA 126351 (2025-09-09). https://mpra.ub.uni-muenchen.de/126351/
  - Read: full.
  - **Cross-check: corrected.** "No FLB pre-play" is narrowed to unbiased last traded prices; taker longshot losses
    remain. Maker pre-play returns are insignificant. Totals: makers are positive from taker p>0.6.
- **ADS22**: Angelini, G.; De Angelis, L.; Singleton, C. (2022). *Informational efficiency and behaviour within
  in-play prediction markets*.
  - IJF 38(1):282–299, DOI 10.1016/j.ijforecast.2021.05.012. https://centaur.reading.ac.uk/98329/
  - Read: full (accepted MS).
  - **Cross-check: corrected.** The data are traded prices. An in-play OOS result is reported but not shown (fn 18).
    Table 3 nuances apply.
- **CR14**: Croxson, K.; Reade, J. J. (2014). *Information and Efficiency: Goal Arrival in Soccer Betting*.
  - Economic Journal 124(575):62–91, DOI 10.1111/ecoj.12033. DP: https://repec.cal.bham.ac.uk/pdf/11-01.pdf
  - Read: full (DP).
  - **Cross-check: corrected.** It does test half-time strategies at the best quotes, and both are unprofitable.
    Statistical efficiency is only "somewhat supported". The quoted significance wording is logically unusual, so I
    treat it as mixed.
- **FVN13**: Franck, E.; Verbeek, E.; Nüesch, S. (2013). *Inter-market Arbitrage in Betting*.
  - Economica 80(318):300–325, DOI 10.1111/ecca.12009. https://doi.org/10.1111/ecca.12009
  - Read: partial to full.
  - **Cross-check: confirmed.** The 2009 NCER precursor is VERIFIED. Volume at the specific odds: £125,270 vs £64,907.
- **BRO12**: Brown, A. (2012). *Evidence of in-play insider trading on a UK betting exchange*.
  - Applied Economics 44(9):1169–1175, DOI 10.1080/00036846.2010.537644. https://doi.org/10.1080/00036846.2010.537644
  - Read: full.
  - **Cross-check: confirmed.** The post-high-information dummy is significant for 2 of 4 contracts. The delay is
    "insufficient or perceived to be".
- **SPV06**: Smith, M. A.; Paton, D.; Vaughan Williams, L. (2006). *Market Efficiency in Person-to-Person Betting*.
  - Economica 73(292):673–689, DOI 10.1111/j.1468-0335.2006.00518.x. https://doi.org/10.1111/j.1468-0335.2006.00518.x
  - Read: full (postprint).
  - **Cross-check: confirmed.** The monotone class trend holds strictly only for Betfair.
- **SW10**: Snowberg, E.; Wolfers, J. (2010). *Explaining the Favorite–Long Shot Bias: Is it Risk-Love or
  Misperceptions?*
  - JPE 118(4):723–746, DOI 10.1086/655844; NBER WP 15923. https://doi.org/10.1086/655844
  - Read: full (NBER WP).
  - **Cross-check: corrected.** 18.4% is the reduction in mean absolute *percentage* error; absolute error falls about
    10%. There are no race fixed effects.
- **OS08**: Ottaviani, M.; Sørensen, P. N. (2008). *The Favorite-Longshot Bias: An Overview of the Main Explanations*.
  - In Hausch & Ziemba (eds.), Handbook of Sports and Lottery Markets, ch. 6, pp. 83–101, DOI
    10.1016/B978-044450744-0.50009-3. Companion AEJ: Micro 2(1):58–85 (2010).
    https://doi.org/10.1016/B978-044450744-0.50009-3
  - Read: full chapter.
  - **Cross-check: corrected.** Eight explanation sections. Ali's mechanism transfers to a CLOB. Fn 17: the FLB
    reappears when insiders are only partially informed.
- **SHIN92**: Shin, H. S. (1992). *Prices of State Contingent Claims with Insider Traders, and the Favourite-Longshot
  Bias*.
  - EJ 102(411):426–435, DOI 10.2307/2234526. Companions: EJ 1991 101(408):1179–1185, DOI 10.2307/2234434; EJ 1993
    103(420):1141–1153, DOI 10.2307/2234240. https://doi.org/10.2307/2234526
  - Read: abstracts.
  - **Cross-check: confirmed** (abstract level).
- **TZ88**: Thaler, R. H.; Ziemba, W. T. (1988). *Anomalies: Parimutuel Betting Markets: Racetracks and Lotteries*.
  - JEP 2(2):161–174, DOI 10.1257/jep.2.2.161. https://www.aeaweb.org/articles?id=10.1257/jep.2.2.161
  - Read: not accessible. Content via Ziemba (2020) SRC DP 103 / ARFE 2023 and via SW10.
  - **Cross-check: confirmed.** That TZ88 claimed favourite profits is VERIFIED via SW10's citation.
- **FN26**: Feil, D.; Nendel, M. (2026). *Optimal Market Making in Prediction Markets*.
  - arXiv:2607.17991v1 (2026-07-20). https://arxiv.org/abs/2607.17991
  - Read: full.
  - **Cross-check: confirmed.** The myopic benchmark has no inventory bound.
- **CH25**: Clinton, J. D.; Huang, T. (2025). *Prediction Markets? The Accuracy and Efficiency of $2.4 Billion in the
  2024 Presidential Election*.
  - SocArXiv/OSF, DOI 10.31235/osf.io/d5yx2_v1, dated 2025-12-01. https://doi.org/10.31235/osf.io/d5yx2_v1
  - Read: full (OSF).
  - **Cross-check: corrected.** First posted 2025-12-01; the February date is UNSUPPORTED. The $2.4B spans four venues;
    misattributing it to Polymarket alone is VERIFIED as an error. Per-market AR(1), pooled across venues.

### 3.4 Skill, copying, latency and legal

- **CHS21**: Coval, J. D.; Hirshleifer, D.; Shumway, T. (2021). *Can Individual Investors Beat the Market?*
  - RAPS 11(3):552–579, DOI 10.1093/rapstu/raab017. https://doi.org/10.1093/rapstu/raab017
  - Read: full (2005 WP).
  - **Cross-check: corrected.** The journal's ~6%/yr is the top decile's own return; the WP's 8% is top minus bottom,
    so they are not comparable. "Marginal" is the reviewer's judgement; the authors say mimicking is "almost certainly
    feasible".
- **BLLO14**: Barber, B. M.; Lee, Y.-T.; Liu, Y.-J.; Odean, T. (2014). *The cross-section of speculator skill:
  Evidence from day trading*.
  - J. Financial Markets 18:1–24, DOI 10.1016/j.finmar.2013.05.006. https://doi.org/10.1016/j.finmar.2013.05.006
  - Read: full (2011 WP).
  - **Cross-check: corrected.** Published figures: 61.3/37.9 and −11.5/−28.9 bp. Ranking is on the Sharpe ratio.
- **BSW10**: Barras, L.; Scaillet, O.; Wermers, R. (2010). *False Discoveries in Mutual Fund Performance: Measuring
  Luck in Estimated Alphas*.
  - JF 65(1):179–216, DOI 10.1111/j.1540-6261.2009.01527.x. https://doi.org/10.1111/j.1540-6261.2009.01527.x
  - Read: full (2005 WP).
  - **Cross-check: corrected.** WP 1.9%/19.6%; JF abstract about 75% zero-alpha. The 24.0%/0.6% split is PLAUSIBLE.
- **LUO26**: Luo, Y.; Feng, Y.; Xu, J.; Liu, Y. (2026). *Resisting Manipulative Bots in Meme Coin Copy Trading: A
  Multi-Agent Approach with Chain-of-Thought Reasoning*.
  - WWW'26; arXiv:2601.08641v3. https://arxiv.org/abs/2601.08641
  - Read: partial.
  - **Cross-check: corrected.** The sample period is not stated. The fee is not in the copier model. The bot findings
    are weaker than first summarised.
- **AOW20**: Apesteguia, J.; Oechssler, J.; Weidenholzer, S. (2020). *Copy Trading*.
  - Management Science 66(12):5608–5622, DOI 10.1287/mnsc.2019.3508. https://doi.org/10.1287/mnsc.2019.3508
  - Read: full (accepted version).
  - **Cross-check: corrected.** Experiment run in 2017. The risk-aversion effect is weak.
- **FPSS04**: Frank (Myers), M. M.; Poterba, J. M.; Shackelford, D. A.; Shoven, J. B. (2004). *Copycat Funds:
  Information Disclosure Regulation and the Returns to Active Management in the Mutual Fund Industry*.
  - J. Law & Econ. 47(2):515–541, DOI 10.1086/422982; NBER WP 8653.
    https://www.nber.org/system/files/working_papers/w8653/w8653.pdf
  - Read: full (WP).
  - **Cross-check: corrected.** In the broader sample the after-expense lead is significant. Copycats are charged index
    expenses.
- **ME26**: Macey, J. R.; Enriques, L. (2026). *Different Markets, Different Regulatory Priorities: Insider Trading,
  Manipulation, and Corruption-Prone Event Contracts in Prediction Markets*.
  - ECGI Law WP 955/2026; SSRN 7323118. https://www.ecgi.global/sites/default/files/2026-08/different-markets.pdf
  - Read: full.
  - **Cross-check: confirmed.** The cited Gómez-Cram and Mitts & Ofir numbers are second-hand. The "follower cost" point
    is an inference, not in the paper.
- **CRS26**: Sykes, J. B. (CRS) (2026). *Prediction Markets and Insider Trading Law*, Legal Sidebar LSB11406.
  - v4, updated 2026-04-03; first posted 2026-03-18. https://www.congress.gov/crs-product/LSB11406
  - Read: full.
  - **Cross-check: confirmed.** The latest version is v4.
- **CFTC26a**: CFTC Division of Enforcement (2026-02-25). *Advisory on Enforcement Authority over Event Contracts*,
  Release 9185-26.
  - https://www.cftc.gov/PressRoom/PressReleases/9185-26
  - Read: full.
  - **Cross-check: confirmed.** The two cases were Kalshi's internal sanctions. NPRM fn 241's URL typo reads 9158-26.
- **CFTC26b**: CFTC (2026-04-23). *CFTC Charges U.S. Service Member with Insider Trading in Nicolás Maduro-Related
  Event Contracts*, Release 9217-26.
  - https://www.cftc.gov/PressRoom/PressReleases/9217-26
  - Read: release only.
  - **Cross-check: confirmed.** The linked-account explanation is UNSUPPORTED.
- **CFTC26c**: CFTC (2026-06-12). *Prediction Markets; Public Interest Determinations*, NPRM, 91 FR 35806–35871, RIN
  3038-AF65.
  - https://www.govinfo.gov/content/pkg/FR-2026-06-12/html/2026-11854.htm
  - Read: partial.
  - **Cross-check: confirmed.** No final rule was found as of 2026-10-17 (PLAUSIBLE).

---

## 4. Gaps: what the literature does not establish for a retail trader in the 2026 fee regime

### 4.1 Substantive gaps

1. **No fee-era out-of-sample test of any strategy family.**
   - The large Polymarket panels end on 2026-03-29 (AKEY26, CRW26, ZAN26 B.2) or earlier (SAG25 to 2025-04-01, SIR25
     to 2025-10-12). QY26 runs to 2026-04-28 but covers only the pre-V2 exchange and is descriptive.
   - The only post-2026-03-30 quote studies are measurement work: GMM26's L2 panel for Apr–May 2026 and DUB26b's 12
     days. Neither tests a strategy.
2. **No paper prices the full current incentive stack.** That stack is:
   - the per-market `feeSchedule` (`rate·p(1−p)`, with category rates and Geopolitics at 0);
   - maker rebates (20%, 15% or 25%);
   - the Taker Rebate Program (tiered 3–50% on 30-day weighted volume, since 2026-05-28);
   - Liquidity Rewards, whose score falls quadratically with distance from the mid;
   - holding rewards.

   The net cost or benefit at retail size, where Bronze is the realistic tier, is unknown in the literature.
3. **No fill-level, queue-aware maker backtest on Polymarket marked to resolution.**
   - Every maker return in the literature is conditional on fills.
   - No paper measures whether a new, small LP's fills are adversely selected, or whether rewards plus rebates cover
     that cost.
4. **No time-ordered, latency-adjusted, executable copy-trading test on Polymarket.**
   - No paper estimates wallet skill with FDR control.
   - The most-cited skill paper (GC26) is not accessible beyond its abstract.
5. **No executable-price study of 95–99¢ contracts by time to resolution.**
   - No study links misresolution or dispute rates (UMA) to the economics of high-probability positions.
   - The project has only leads on dispute base rates (§4.3).
6. **Capital lock-up and return on committed capital are essentially unmeasured.**
   - AKEY26 did not look at it. CRW26 says committed collateral cannot be reconstructed.
   - PC13 shows that discounting can erase long-dated edges.
   - The yield on idle pUSD and on holding rewards is not studied.
7. **Execution risks a retail bot would face are unquantified at retail size:**
   - reverted ("ghost") fills;
   - `secondsDelay` on sports markets and crypto taker delays;
   - the 2026-07-24 change that stopped returning transaction hashes for FAK/FOK orders;
   - the 2026-08-07 change to crypto up/down resolution.
8. **Historical executable book data are not official.**
   - GMM26 and DUB26b rely on third-party archives (pmxt/PMXT), whose terms were not checked.
   - The order-book provenance in ZS26 and MOU26 is unknown.
   - Most other studies use trades, VWAPs or `/prices-history`, none of which are executable prices.
9. **Inference is weak across the board.**
   - Clustering by event or calendar time is rare. Correlated families (crypto up/down on one asset, linked election
     markets) are treated as independent.
   - Trade-level CIs (BEC26, MOS26) are far too narrow.
10. **Coverage is uneven by category.**
    - Sports has the largest volume share but shows no FLB.
    - Geopolitics (fee 0) and Mentions are barely studied.
    - Weather rests on one teen-track paper with one test month.
    - No literature exists on the new products (Combos, Perps) or on the Taker Rebate Program.
11. **Data plumbing after V2 is fragile.**
    - The Goldsky subgraph used by AKEY26, CRW26 and SIN25 is deprecated.
    - CryptoHouse is stale after 2026-01-05.
    - Trade-direction conventions conflict across papers (DUB26a vs DUB26b vs QY26).
12. **Legal and geographic questions are open.**
    - No source addresses the liability of copying a public on-chain trade.
    - Venue access differs between the international site, which the CFTC calls an "unregistered platform", and
      Polymarket US. That is outside the literature; see `../platform/geography_legal.md`.

### 4.2 Known inconsistencies to watch when citing

- **SAG25:** the headline does not equal its components.
- **GMM26 v1:** text is dropped after "%" in some sentences, and its episode counts are not reconciled (sweep).
- **DUB26a vs DUB26b:** the trade-direction findings conflict.
- **AKEY26:** the 84% vs 76.5% headline differs across versions.
- **BDW25:** the Sept 2025 and Jan 2026 versions differ materially.
- **BLLO14, BSW10 and CHS21:** working-paper and journal numbers differ.
- **ZAN26 vs CONTEXT.md:** ZAN26 assumes no maker rebate; CONTEXT.md gives a 20% Crypto rebate.
- **Fee activation dates differ across papers** (QY26, DUB26b, AKEY26, DJY26). Rely on per-market Gamma `feeSchedule`
  and `feesEnabled`, not on any paper's dates.

### 4.3 Leads (explicitly UNVERIFIED; not in the cross-checked set)

**Mentioned in the sweep notes, read at most at abstract level.**
- **UMA disputes:** Wang, G., Economics Letters 268 (2026) 113176, DOI 10.1016/j.econlet.2026.113176, metadata only.
  Nechepurenko, arXiv:2609.15368, abstract: 1,604 disputes among 159,447 proposals. Wen, Zhou & Huang,
  arXiv:2604.15674, LLM dispute arbitration.
- **Execution:** Chen, Long & Su, arXiv:2609.17902, ghost-filled orders.
- **FLB and calibration:** Gruener, SSRN 6863546 (the FLB in 5-minute crypto markets disappears under clustering).
  Page, Applied Economics 44(1):81–92 (2012), "Yogi Berra bias" near expiry. Lee, Lee & Lee, IRFA (2026) 105433,
  Kalshi/Polymarket crypto variance risk premium.
- **Makers vs takers:** Gupta, SSRN 6858200, Kalshi/Polymarket maker–taker returns.
- **Wallets and copying:** Lei & Huang, SSRN 7420398, a +335.66% "expert following" replay; an extraordinary claim.
  Liu, SSRN 6678718, Polymarket insider Sybil clusters. Wang, M., SSRN 6624899, 273 "smart money" traders.
- **Microstructure:** Agarwal, SSRN 7273479, a 6.63 s on-chain vs API lag in cricket. Malék, SSRN 7520438, Kalshi
  order-flow imbalance.
- **Costs:** Sun, SSRN 7453738, fees vs selection edge; assumes every buy is a taker trade.
- **Reversal:** Choi & Hui, JEBO 107:614–629 (2014), over-reaction to surprising goals, in conflict with ADS22.
- **Disclosure latency:** Gil & Levitt (2007), Intrade post-goal drift. Rogers, Skinner & Zechman, JAR 55(2) (2017),
  disclosure latency.
- **Industry:** Telonex (2026), sponsored-rewards case study; industry blog.

**Possibly missing methodological references.** These come from general knowledge, and their metadata has not been
checked in this project. Verify before citing.
- White (2000), "A Reality Check for Data Snooping", *Econometrica*.
- Harvey, Liu & Zhu (2016), "…and the Cross-Section of Expected Returns", *Review of Financial Studies*. Multiple
  testing for strategy and wallet search.
- Avellaneda & Stoikov (2008), "High-frequency trading in a limit order book", *Quantitative Finance*. The base model
  FN26 extends.
- Manski (2006), "Interpreting the predictions of prediction markets", *Economics Letters*. Cited by ZIT26 and PC13 as
  the source of the belief-heterogeneity bias logic.
