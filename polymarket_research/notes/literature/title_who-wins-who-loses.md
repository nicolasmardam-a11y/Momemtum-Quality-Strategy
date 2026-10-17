# Reference check: "Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket"

As of 2026-10-17. Author of note: research agent (literature verification).
Labels: **VERIFIED** = I read it in a primary source myself; **PLAUSIBLE** = consistent with the evidence but not
directly checked; **UNSUPPORTED** = no evidence found.

## Verdict

- **The paper exists under this exact title. VERIFIED.** Capitalisation differs by venue: SSRN/Crossref and the authors'
  pages write "Who Wins and Who Loses **In** Prediction Markets?"; the CEPR listing and the PDF title page write "in".
- The supplied reference gave only a title, so there is nothing else in it to be wrong. Two points matter for anyone
  citing it:
  1. It is a **working paper**: SSRN and CEPR Discussion Paper DP21615. I found no journal acceptance or publication
     as of 2026-10-17 (UNSUPPORTED that it has been published).
  2. **The headline numbers changed between versions.** The early version (about March/April 2026) said "top 1% capture
     84% of gains" on 1.4M users, 70M trades and $20B of volume. The June 12, 2026 version says "top 1% **of users with
     positive PnL** capture 76.5% of profits" on 2.48M users, 588M trades and $67.1B. A citation to "84%" refers to the
     superseded draft. Both figures are VERIFIED, in the sources listed below.

## Metadata

| Field | Value | Status |
|---|---|---|
| Exact title | Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket | VERIFIED (PDF title page; CEPR/RePEc; Crossref) |
| Authors | Pat Akey (ESSEC Business School, CEPR, ECGI); Vincent Grégoire (HEC Montréal); Nicolas Harvie (Rotman, University of Toronto); Charles Martineau (Rotman and UTSC, University of Toronto) | VERIFIED (title page of June 12, 2026 version) |
| DOI | 10.2139/ssrn.6443103 (SSRN abstract 6443103) | VERIFIED (Crossref API) |
| First posted | Crossref DOI record created 2026-04-07T20:38Z. CXO Advisory (a lead only) calls it a "March 2026" paper. I could not read SSRN's own "posted" date (HTTP 403) | VERIFIED (Crossref date); PLAUSIBLE (March 2026 date-written) |
| Latest version seen | Dated June 12, 2026 on the title page. Crossref metadata redeposited 2026-06-12T21:05Z with the new abstract. CEPR DP21615 is dated June 2026 (EconPapers) | VERIFIED |
| Later versions | None found after June 12, 2026. Grégoire's homepage still shows the *old* (84%) abstract as of 2026-10-17 | VERIFIED (absence = my search only) |
| Status/venue | SSRN working paper; CEPR Discussion Paper No. 21615 (RePEc:cpr:ceprdp:21615). JEL on the paper: G12, G14, G15, D47, D82 | VERIFIED |
| Primary URL | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6443103 | VERIFIED via author pages and Crossref (page itself 403 from sandbox) |
| Other URLs | https://cepr.org/publications/dp21615 ; https://ideas.repec.org/p/cpr/ceprdp/21615.html ; https://econpapers.repec.org/RePEc:cpr:ceprdp:21615 ; data: https://huggingface.co/datasets/vgregoire/polymarket-users ; data docs: https://www.vincentgregoire.com/polymarket-users-data | VERIFIED |
| Seminars | Aarhus (2026-04-30), HEC Paris (2026-06-04), and others listed in the acknowledgements | PLAUSIBLE (from search snippets plus the acknowledgements) |
| Citations | Crossref is-referenced-by-count = 2 (2026-09-26 index). arXiv papers citing it: 2606.04217, 2609.12878, 2609.28965, 2610.13593 | VERIFIED (grep of those PDFs) |

### How I read the full text

- SSRN and CEPR return 403 from this sandbox, both to curl and to WebFetch. The full **June 12, 2026 version** (main text
  plus a 158-page Internet Appendix) was readable as HTML text on an **unofficial mirror** (dokumen.pub). Its
  title page, author block, acknowledgements, data link and numbers match the CEPR, RePEc and Crossref abstracts, so I
  treat it as the authentic June version. It is still a third-party copy, not the publisher's file.
- **Gap:** the mirror dropped all text between a `<` and the next `>`, because "PnL < 0" was parsed as an HTML tag. As a result
  **Section 6.2 (spread decomposition and maker/taker persistence), parts of Section 6.1, and the bodies of Tables 4–6
  are partly missing.** I took the numbers for those parts from the Introduction, the Conclusion, the table captions and
  the surviving table cells. Everything else (Sections 1–5, 7, 8 and Appendices A–D, I, K, L) I read in full.

## What the paper does

**Question:** who earns and who loses on Polymarket, at the wallet level, and does skill, liquidity provision or
insider trading explain the winners?

**Data (VERIFIED, Sec. 3, IA A):**
- Trades come from the **Goldsky Polymarket SubGraph**, which indexes on-chain `OrderFilled` events from the CTF Exchange
  and NegRisk exchange. Market metadata come from Gamma, the CLOB "simplified markets" winner flags, and the Data API
  (used only to validate PnL).
- Reconciliation, IA A.1: in a matched trade the event whose taker is the exchange contract gives the true taker. That
  taker-order event is dropped and the other events' taker field is rewritten, so each economic trade appears once, as
  one row per maker–taker pair.
- Sample: **2022-11-11 to 2026-03-29**. It ends because "Polymarket introduced trading fees on all markets on March 30,
  2026".
- Size: **2,480,104 wallets ("users"), 588.3M trades, $67.1B matched-notional volume, 614,883 markets with trades
  (729,133 in the metadata), 255,427 events with trades.**
- Categories: seven classifier categories (Sports, Crypto, Politics, Finance, Culture, Tech, Weather), from a four-stage
  tag, legacy-category, title-rule and manual cascade (IA A.4). Sports has 52% of markets and 37.9% of volume. Politics
  has 31.5% of volume from 29,926 markets. Crypto has 67% of trades (Table 2).

**PnL construction (VERIFIED, Sec. 3.2, IA A.3):**
- Daily mark-to-market at midnight UTC: PnL = Σ position × last trade price (or the settlement price) + net USDC from
  trades. Cash starts at zero.
- Not included: direct wallet-to-wallet transfers, external deposits and withdrawals, and gas.
- Validated against the Polymarket Data API on a stratified sample of 1,000 wallets, with a reported "perfect match".
- **Wallet = user.** Multiple wallets per person and off-platform hedges (for example Kalshi legs) are not observed.

**Methods:**
- Concentration curves.
- Calibration plots at 1 month, 2 weeks, 1 week and 1 day before resolution, with 10¢ bins.
- A per-user volume-weighted **excess hit rate** EHR = Σq(o−p)/Σq on resolved trades.
- A finite-mixture skill model adapted from Crane & Crotty (2020).
- Probits of 1{PnL>0} on behaviour (maker share, extreme-price share, log trades, log volume, category HHI,
  counterparty HHI, category dummies).
- Monthly PnL transition matrices (dollar buckets, plus Sharpe and Sortino analogues).
- Dropout and capital-growth regressions.
- A lower-bound spread decomposition.
- Wash-trading screens using counterparty HHI.
- A stylised simulation (IA K).
- A descriptive look at the top 100 wallets (Sec. 7, IA L).

## Key findings (June 12, 2026 version)

All VERIFIED in the mirror text unless marked.

1. **Concentration (Sec. 4.1, Fig. 3):**
   - 764,424 winners share $1.05B of gains. The top 0.1 / 1 / 5 / 25% of winners take **51.2 / 76.5 / 91.4 / 99.2%**.
   - The top 0.1 / 1 / 5 / 25% of losers bear 43.7 / 68.1 / 86.1 / 98.3% of losses.
   - About **69% of users end with a loss** (Table 3: 31.3% winners).
   - The top-1% share of gains was about 40–50% before the 2024 election and about 80% afterwards.
   - *Internal inconsistency:* the Figure 3 annotation says "N winners = 766,188, gains = $1.1B", while the text and
     Table 9 bucket counts sum to 764,424.
2. **Distribution (Sec. 3.3, Table 1):**
   - Median user: 28 trades, 10 markets, $2,343 of volume, PnL −$2. Mean PnL is $0.
   - Median share of trades at extreme prices (<10¢ or >90¢) is 58.3%. Median maker-volume share is 0%; the mean is 17.9%.
   - Median annualised PnL-to-volatility ratio is −1.03.
3. **Calibration (Sec. 3.4, Fig. 2, IA B.2):**
   - Aggregate prices sit close to the 45° line even one month before resolution, and tighten closer to it.
   - **Tech, Culture and Weather deviate even at the 1-day horizon.** The authors only say this "suggest[s]" mispricing.
     The results are figures only, with no tradable magnitude given.
4. **Forecast accuracy (Sec. 4.2, Fig. 4; IA C):**
   - Mean EHR is about −0.15 to −0.18 across the loss tail and about +0.20 for the most profitable bins. The sample mean
     is −0.021.
   - Mixture model (users with ≥20 resolved trades): **29.3% "skilled"** (π0 = 0.101, µ0 = −0.029; π1 = 0.899,
     µ1 = −0.002; Table C2).
5. **Determinants (Sec. 5, Table 4/5):**
   - A 1 SD rise in **maker-volume share raises Pr(PnL>0) by 9.0 pp**, the largest effect (4.5 pp among users with
     >1,000 trades).
   - Extreme-price share is about 0 once activity and category controls are added. It turns +12.8 pp among users with
     >1,000 trades, which the authors read as selection.
   - Counterparty HHI is −23.1 pp (>100 trades, col. 6) and −50.0 pp (>1,000 trades, col. 8).
   - The top 0.1% of earners are 47.3% maker versus 17.1% for the bottom 95%. They trade at extreme prices 28.2% versus
     56.4% of the time, and average 150,623 trades versus 223.
6. **Risk-adjusted (Sec. 5, Table 5 Panel B):**
   - Median annualised PnL/vol is 1.73 for the top 0.1%, against −1.15 for the bottom 95%.
   - The top group's mean monthly PnL is $54,586 and its max drawdown $35,216.
7. **Spread (Intro and Conclusion; Table 9; IA I):**
   - "Mean PnL (excl.)" removes "the minimum possible effective half-spread on each taker trade". The dataset card gives
     this as 0.005, half of a 1¢ tick.
   - Removing it would move **18.5% of losers to non-negative PnL**. It does not explain the worst losers.
   - Top winners are net spread earners: the top 0.1% of winners show a mean of $703,060 with the spread and $680,242
     without it, and are 49.3% maker. The bottom 20% of winners show $0.19 with and $0.49 without, and are 24.1% maker.
   - The text of Sec. 6.2 is partly missing from the mirror (see gap above).
8. **Persistence (Sec. 6.1, Tables 6–8, 10–11):**
   - Persistence is "modest", and **dropout is large**: 44% stop after one month, and up to 66% after six months,
     including 55% of the best performers (Sec. 1 lit. review).
   - One-month "No Trade" rates range from 36.5% (<−50k bucket) to 16.8% (>50k).
   - From the >50k bucket, conditional on trading, 33.4% stay in that bucket next month and 18.2% fall to <−50k (Table 6,
     cells partly garbled: PLAUSIBLE reading).
   - Maker-heavy user-months show a **+6.6 to +11 pp higher Pr(next-month Sharpe-analog > 0)** than taker-heavy ones
     (Table 11), on 1,185,170 maker-heavy versus 6,326,148 taker-heavy user-months.
9. **Top 100 (Sec. 7):**
   - The top 100 hold 27.7% of winners' profits. Many are pure liquidity providers.
   - 42 of them are concentrated in a few markets. Of those 42 wallets' gains, 81% come from sports across many leagues,
     15% from 2024 election markets, and 4% from other markets.
   - The two prosecuted insider wallets (CFTC v. Spagnuolo; CFTC v. Van Dyke) rank 115th and 307th, with about $0.93M and
     $0.41M, which is about 0.13% of winners' profits.
   - The authors conclude that insider trading is unlikely to be the dominant source of profits. This is
     interpretation, not proof.
10. **Robustness (IA D–F):**
    - The wash-trading screen (counterparty HHI ≥ 0.5, wallets with ≥100 trades) flags 7,241 wallets and 3.1% of volume.
      Concentration is essentially unchanged after excluding them (76.7% versus 76.5%).
    - Results hold on resolved-only and no-fee-only subsamples.
11. **Simulation (IA K):**
    - Wealth dispersion and luck produce some of the winner concentration. Matching the data takes skill, maker
      specialisation and overconfidence acting together.
    - The simulation does not reproduce the loss-side concentration. The authors call it "illustrative".

## Evaluation for a retail trader

**Economic mechanism:** the paper treats this as a zero-sum transfer from liquidity takers, who often trade long shots,
to liquidity providers and a minority of better forecasters. Spread capture is part of the transfer. The worst losses
reflect forecasting errors, not costs.

**Evidence type:**
- **Descriptive and in-sample.** No strategy is backtested and no trading simulation at executable prices is run.
- The persistence tables (month t bucket to month t+1 outcome) are the only forward-looking element, and they describe
  wallets' own PnL, not a copier's.

**Costs and execution:**
- Fees: mostly absent in the sample (no-fee robustness check). The sample ends 2026-03-29, before the all-market fee
  regime, Maker Rebates in their current form and the Taker Rebate Program (2026-05-28; see CONTEXT.md).
- Spreads: only as a minimum-tick lower bound (0.005 per taker fill).
- Not modelled: **depth, queue position, latency, partial fills, adverse selection or markouts, and capital lock-up.** On
  Hacker News a co-author (account "vcf") replied that they "haven't looked at the capital 'locked' in these markets".
  That is VERIFIED as a statement in the thread; that vcf is a co-author is PLAUSIBLE.
- Returns are in dollars, not on capital.
- Liquidity Rewards and maker rebate payouts are paid outside the exchange settlement flow. That probably puts them
  **outside** the trading-only PnL, which would understate maker profits (PLAUSIBLE, my inference from Sec. 3.2 fn 17 and
  IA A.3).

**Marking:**
- Open positions are valued at the **last trade price**, which is not an executable price (CONTEXT.md rule).
- A resolved-only variant is reported as a robustness check.

**Correlated observations:**
- The unit is the wallet. Calibration bootstraps (1,000 replications) appear to resample markets, with no clustering by
  event, even though there are 614,883 markets in 255,427 events.
- Probits use robust (not clustered) SEs. Transition-matrix tests are exact binomial tests treating user-months as
  independent. Only Table 8 clusters, and only by user. **None cluster by event or by calendar time**, although common
  shocks (election month, one sports match) hit many wallets at once.
- The mixture model's sampling error s_i assumes independent trades with variance p(1−p). For a wallet that trades
  the same market many times, outcomes are perfectly correlated, so s_i is understated and luck is pushed toward "skill".
  This is my assessment from eq. (3) (PLAUSIBLE, not tested).
- Cardozo & Rivero-Wildemauwe (arXiv 2609.12878, using this dataset) show why grouping matters. Longshots lose 6.3¢
  per dollar when child markets are equally weighted but **gain 4.1¢ when grouped by parent event** (VERIFIED, abstract).

**Prospective tradability:**
- **Not established.** Maker share, EHR and PnL are all measured over the same full sample with realised outcomes, so
  "be a maker" and "follow the top wallets" are ex post associations.
- The forward-looking evidence is weak. Persistence is modest, dropout is heavy, and no executable copy-trading or
  market-making test was run.
- The fee and rebate regime changed after the sample.
- The paper is useful for **direction** (taking liquidity on long shots is the losing side; passive liquidity is the
  winning side on average) and as a **free dataset**. It is not a validated strategy.

**Relevance to strategy families:**
- D_liquidity_provision: core, but untested at the fill level.
- E_favorite_longshot: losers trade extremes; the effect is second-order after controls.
- A_wallet_following: modest persistence and heavy attrition.
- H_near_resolution: calibration tightens toward resolution; Tech, Culture and Weather are less calibrated.

## What to replicate before risking money

1. Load HF dataset **v1.3** (`user_pnl_summary`, `trades`; 119 GB in total) and reproduce the headline concentration and
   the Table 9 spread decomposition. Note the changelog:
   - v1.1 fixed a phantom-settlement bug that had left aggregate PnL at +$114,798 instead of 0.
   - v1.2 withdrew the undocumented maker/taker PnL columns because they did not reconcile.
   - v1.3 fixed the `frac_longshot` and `frac_sureshot` columns.
2. Independently rebuild maker/taker attribution from on-chain fills: CryptoHouse `orders_filled` up to 2026-01-05, then
   Polygon RPC `eth_getLogs` or Data API v2 `/v2/trades?taker_only=false`. **The Goldsky subgraph the paper used is
   deprecated and stale since V2** (CONTEXT.md). Spot-check against `/v2/user-stats` and `/v2/user-pnl`.
3. Decompose maker PnL per fill into spread capture and **adverse selection** (markouts at 1 min, 1 h and resolution) by
   category, price bucket and time to resolution. Add Liquidity Rewards and maker rebates, and subtract taker fees
   under the **current** fee schedule (`feeSchedule` per market).
4. Measure capital lock-up and return on committed capital, not only dollar PnL.
5. Re-run inference clustered by event and by calendar week, and weight by parent event.
6. Run a prospective wallet-selection test: rank wallets only on data before month t, then simulate copying with
   realistic latency at **executable** prices. This requires live book capture, because there is no historical book
   endpoint.
7. Run an out-of-sample check on the post-2026-03-30 regime, when fees apply to all markets and the Taker Rebate Program
   exists.
8. Quantify the Tech, Culture and Weather calibration gaps with event-clustered CIs, at executable bid/ask rather than
   last trade, before treating them as edges.

## Related or confusable items (not the same paper)

- **Della Vedova (2026), "Who profits from prediction markets? Execution, not information"**: a working paper cited in
  Akey et al.'s references (VERIFIED as a citation). Its similar title invites confusion. I did not locate its full
  text, so its existence is PLAUSIBLE (it is cited by at least two papers).
- **Gómez-Cram, Guo, Jensen & Kung (2026), "Prediction market accuracy: Crowd wisdom or informed minority?"**: cited by
  Akey et al. as closely related (VERIFIED as a citation; not read).
- **Reichenbach & Walther (2025), "Exploring decentralized prediction markets: Accuracy, skill, and bias on
  Polymarket"**: cited (VERIFIED as a citation; not read).
- **Becker (2025), Kalshi maker–taker wealth transfer (jbecker.dev)**: cited (VERIFIED as a citation; not read).
- **Cardozo & Rivero-Wildemauwe (2026), arXiv 2609.12878, "The Favorite–Longshot Bias in Prediction Markets: Evidence
  from Polymarket"**: a follow-on built on dataset v1.3, with event-clustered CIs. I read the abstract and Secs. 1–2 and
  part of 5. M. Cardozo is the person credited in the HF v1.3 changelog for finding the `frac_longshot` bug.

## Discrepancies with CONTEXT.md or within the sources

- The paper describes contracts as USDC-denominated. CONTEXT.md says collateral is now pUSD after the 2026 V2
  migration. The two are consistent if the sample (to 2026-03-29) predates or straddles the migration (PLAUSIBLE; I did
  not check the migration date).
- The paper says fees came in on "all markets" from 2026-03-30. CONTEXT.md lists Geopolitics at a 0 rate today. The
  "all" wording is loose or out of date.
- The paper (fn 12) dates the first fee-enabled markets to Feb–Mar 2026. The HF card describes the no-fee variant as
  "predat[ing] the Q4 2024 fee introduction". This inconsistency in the authors' own documentation is VERIFIED; which
  date is right I did not check.
- The Polymarket-v1 Database (arXiv 2606.04217) counts about 1.20B trades and $61B, against Akey et al.'s about 588M
  trades and $67B. Trade and volume totals depend on counting conventions, such as reconciled maker–taker pairs versus
  raw fill events.

## Search log

1. WebSearch for the exact title plus "Polymarket" found SSRN 6443103, CEPR DP21615, RePEc, the HN thread, press
   coverage (Washington Post, Yahoo) and mirrors (Scribd, Studocu, dokumen.pub).
2. arXiv API: `ti:"who wins" AND ti:prediction` returned only an unrelated 2020 paper. `all:polymarket` (100 newest)
   did not list the paper, so it is not on arXiv.
3. RePEc/IDEAS and EconPapers (WebFetch): metadata, CEPR DP21615, June 2026, JEL G12/G14. CEPR itself returned 403 to
   both curl and WebFetch.
4. SSRN abstract page: 403 to both curl and WebFetch.
5. Crossref `query.bibliographic` and `/works/10.2139/ssrn.6443103`: DOI created 2026-04-07, redeposited 2026-06-12 with
   the June abstract, 2 citations.
6. OpenAlex: daily budget exhausted (429-type error). I did not create a key, because that would need the user's email.
7. Author pages:
   - vincentgregoire.com: JSON-LD gives the old abstract (1.4M users, 70M trades, $20B, 2022–2025, 84%) and the HF link.
   - charlesmartineau.com and itsnh98.github.io: SSRN and HF links.
   - patakeyfinance.com: DNS failure.
8. Hugging Face dataset card plus API: created 2026-05-19, last modified 2026-07-06, v1.0–v1.3 changelog, 0.005
   half-spread, CC-BY 4.0. No code repository is linked; the card points to the docs page.
9. Full text: the dokumen.pub HTML text of the June 12, 2026 version, read via curl. Its PDF download sits behind a
   reCAPTCHA, which I did not attempt. Scribd (JS wall) and Studocu (wrong content) were dead ends.
10. WebSearch for later versions or a journal version: none found. Seminar pages (Aarhus 2026-04-30, HEC Paris
    2026-06-04) and the CXO Advisory post (2026-04-28, "March 2026" version, Nov 2022–Oct 2025 sample) were leads only.
11. Hacker News thread 48221877 (WebFetch): comments only. The author replied on capital lock-up and benchmarks.
    There was no substantive methodological rebuttal.
12. Citing works: downloaded 10 recent Polymarket arXiv PDFs and grepped for "Akey". Hits were 2606.04217, 2609.12878,
    2609.28965 and 2610.13593. Only 2609.12878 engages with the methods (wash-trading screen threshold, event grouping).
13. WebSearch for Della Vedova "Who profits from prediction markets": found only citations of it, not the paper.
