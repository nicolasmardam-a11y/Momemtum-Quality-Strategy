# Reference check: "Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets"

As-of 2026-10-17. Task: check a reference cited in an earlier discussion, treating it as an unverified lead.

## Verdict

**The paper exists, and the supplied title is exact (VERIFIED).** The British spelling "Unravelling" (double l) matches arXiv and the LIPIcs version. The IMDEA Networks repository record spells it "Unraveling" (single l), which is only a spelling variant.

| Field | Value | Label |
|---|---|---|
| Exact title | Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets | VERIFIED |
| Authors (in order) | Oriol Saguillo (IMDEA Networks), Vahid Ghafouri (Oxford Internet Institute), Lucianna Kiffer (IMDEA Networks), Guillermo Suarez-Tangil (IMDEA Networks) | VERIFIED (PDF title page) |
| First posted | arXiv:2508.03474v1, 5 Aug 2025 14:06:50 UTC, cs.CR primary, q-fin.TR cross-list | VERIFIED (arXiv API and abs page) |
| Latest version | arXiv still shows only v1 when checked on 2026-10-17. No comments or journal-ref field. arXiv DOI 10.48550/arXiv.2508.03474 | VERIFIED |
| Published version | 7th Conference on Advances in Financial Technologies (AFT 2025), LIPIcs vol. 354, Article 27, pp. 27:1–27:24, DOI 10.4230/LIPIcs.AFT.2025.27, published 2025-10-06, CC-BY 4.0. Editors are Zeta Avarikioti and Nicolas Christin. The conference ran 8–10 Oct 2025 in Pittsburgh. The LIPIcs paper says the arXiv paper is the "Full Version" | VERIFIED (DROPS PDF and JSON-LD metadata, IMDEA DSpace record) |
| Peer review | Refereed conference paper (AFT). The arXiv v1 acknowledges "the anonymous AFT reviewers" | VERIFIED |
| Funding | Flashbots Research Proposal FRP-51 | VERIFIED |
| Primary URL | https://arxiv.org/abs/2508.03474 | |
| Other URLs | https://doi.org/10.4230/LIPIcs.AFT.2025.27, https://drops.dagstuhl.de/storage/00lipics/lipics-vol354-aft2025/LIPIcs.AFT.2025.27/LIPIcs.AFT.2025.27.pdf, https://hdl.handle.net/20.500.12761/1941, https://ideas.repec.org/p/arx/papers/2508.03474.html | |
| Code or data repository | **None found.** Neither the paper nor the LIPIcs record links to code or data. GitHub and web searches found nothing | VERIFIED (absent in text); repository searches PLAUSIBLE-negative |

**Full text read:** yes. I read all 36 pages of the arXiv v1 PDF, including appendices A–I, using pdftotext. Figures were only available as extracted axis text, so I report no values read off figure bars. I also read the 24-page LIPIcs version and diffed its numbers against arXiv. The main-text numbers are identical, and the LIPIcs version moves the appendices to the arXiv "full version".

## What the paper does

### Economic mechanism (VERIFIED, §3)
- A Polymarket "market" is a set of mutually exclusive, exhaustive "conditions" (NegRisk when there is more than one). Each condition is a binary YES/NO token pair.
- **Market Rebalancing Arbitrage** (Def. 3) covers two cases. Within one condition, YES+NO ≠ 1. Within a NegRisk market, Σ YES ≠ 1. Long means buying all legs when the sum is below 1. Short means buying all NOs, or splitting and selling the YESes, when the sum is above 1.
- **Combinatorial Arbitrage** (Defs. 2 and 4) applies to two logically dependent markets. It exists when subsets S ⊂ M1 and S′ ⊂ M2 must have equal resolution sums but their YES prices differ. Only YES-side strategies are considered.
- The authors stress that all of these are **non-atomic** on Polymarket's CLOB, so leg risk is always present (§3.2.1, footnote 11). They give no quantitative treatment of that risk.

### Data and sample (VERIFIED, §4)
- **Market metadata** came from the Polymarket CLOB API via `py-clob-client`. The end date is taken as the modal `end_date_iso` within a market ID.
- **On-chain data** came from Polygon via the Alchemy public node. The authors say they "query the transaction traces for the Polymarket Conditional Token Contract" (0x4D97…6045) for blocks from 1 Jan 2024 to 1 Apr 2025, keeping `OrderFilled`, `PositionSplit` and `PositionsMerge`.
- **Sample:** markets that **resolved between 1 Apr 2024 and 1 Apr 2025**. It covers 8,659 single-condition markets plus 1,578 NegRisk markets with 8,559 conditions, for 17,218 conditions in total. The arithmetic checks out.
- **Topics:** markets are assigned to Politics, Economy, Technology, Crypto, Twitter, Culture or Sports by cosine similarity of Linq-Embed-Mistral embeddings. On a 100-item hand-labelled sample this was 92% accurate (§4.1.1).
- **Trade records:** App. I.1 summarises 86,620,143 "bids" (executed fills), with a mean of $135.6 and a median of $8.29.

### Dependency detection (VERIFIED, §5)
- The LLM is DeepSeek-R1-Distill-Qwen-32B, asked to enumerate valid truth assignments (App. B prompt). Markets with more than 4 conditions are reduced to the top 4 by volume plus an "OR-of-the-rest" condition.
- **Single-market validation:** of 128 NegRisk Politics markets on 2024-11-05, 4 returned invalid JSON and 101 (81.45%, which is 101/124) passed all checks.
- **Non-US-election pairs:** 2,267 pairs checked. 2,033 were judged independent and 1 dependent (a hurricane-count pair), and that one did not meet the strict definition.
- **US-election pairs** (Politics, end date 2024-11-05): 46,360 pairs. 1,576 were flagged dependent, a subset-checker kept 374, and manual review kept **13 valid pairs** (11 NegRisk–NegRisk, 2 NegRisk–Single). So the combinatorial results rest on 13 hand-validated pairs, all from the 2024 US election.

### Opportunity detection (VERIFIED, §6)
- **Prices are not quotes.** They are block-level volume-weighted averages of executed fills for each token. The last price is carried forward for up to 5,000 blocks (about 2.5 h). **After that the price is set to 0.** Times when any token is above $0.95 are excluded. The text says only opportunities of at least $0.05 per dollar are kept (§6), but the Fig. 5, 6 and 14 captions refer to a 2-cent bound or cap (|1−VWAP sum| > 0.02). **This is an internal inconsistency.**
- **Within a single condition (YES vs NO):** 7,051 of 17.2k conditions show at least one opportunity (2,628 NegRisk, 4,423 single). All of them are long, and the median "profit per dollar" is about $0.60 (§6.1).
- **Within NegRisk markets:** 662 of 1,578 markets show at least one opportunity, about 100 per market on average. Both long and short occur, and the average maximum is about 40¢ per dollar (§6.2).
- **"Maximum profit" is not depth.** For a condition it is defined as price × "the total amount of tokens that exist". There is also a variant capped at $100.
- **Across markets:** within the 13 US-election pairs, pair 8 had no opportunities. Pairs 2, 1 and 4 had 72, 176 and 6,630 opportunities, and the median among the rest was 8. The authors note these occur "largely during lower liquidity moments", with an average maximum profit of about $100 (§6.3).

### "Realized" (exploited) arbitrage (VERIFIED, §7)
- **Method:** for each address, fills under $2 are dropped and fills within **950 blocks (about 1 h)** are grouped. Profit is the minimum token amount held across the legs minus the acquisition cost. Fees are explicitly ignored: "we do not take into account the fees because Polymarket currently does not charge per trade executed" (§7.1).
- **Single condition:** buying below $1 gave **$5,899,287.43** and selling above $1 gave **$4,682,074.77**, a subtotal of about $10.58M (§7.2). Fig. 10's caption says about 1% of the estimated US-election opportunities were exploited.
- **NegRisk within-market:** buy YES $11,092,286.31, sell YES $612,188.83, sell NO $4,264.33, buy NO $17,307,113.81, a subtotal of about $29.02M (§7.3).
- **Combinatorial (US-election pairs):** pair 2 $60,236.71, pair 4 $18,472.31, pair 1 $15,818.53, pair 3 $629.16, totalling **about $95.2k**. That is **about 0.24% of the headline**. The text says "evidence of value extraction in 5 cases" but lists only 4 values.
- **Headline:** **$39,587,585.02** "assuming an ε = $1 profit per trade" (§7.4). This does not exactly reconcile with the components. The components sum to $39,597,215.48 (a $9,630 gap), or $39,692,372 if the combinatorial amount is added. The paper does not explain the gap.
- **Top account:** $2,009,631.76 from 4,049 transactions (Table 1, top 10 by address prefix). The top 10 together account for about $8.18M.
- **Outlier:** one account (@Tutaaa91) bought both YES and NO at under $0.02 each, for a $58,983.36 single-trade "profit" (§7.2).

## Classification for trading purposes

- **Evidence type:** descriptive, in-sample historical measurement. There is no simulated strategy, no out-of-sample test, no statistical inference and no standard errors. The "realized" profits are the authors' inference from other people's on-chain fills, not from the authors' own trading (VERIFIED).
- **Fees:** ignored. That was accurate for most markets in 2024–25, but taker fees now apply (CONTEXT.md: `fee = shares × rate × p(1−p)`, rate 0.04–0.07 in most categories). A two-leg complete set near p≈0.5 now costs about rate × 0.5 per set, roughly 2–3.5¢. That is larger than the edge of most quote-level violations reported in later work (my calculation from CONTEXT.md, PLAUSIBLE).
- **Spreads:** not modelled. Trade VWAPs are used, and the authors say this *underestimates* margins (Fig. 5 caption). I think it can equally create spurious "opportunities" (see the critique below).
- **Depth:** not modelled. "Maximum profit" uses outstanding token supply, not resting liquidity. The $100-capped variant is the only size-aware measure.
- **Latency:** not modelled. The analysis has 1-block price granularity, a 5k-block carry-forward and a 950-block grouping window.
- **Capital lock-up:** not addressed. There is no time-to-resolution discounting.
- **Partial fills and leg risk:** only acknowledged qualitatively.
- **Gas:** not discussed.
- **Correlated observations:** no clustering or inference. Opportunities are counted per block and per condition. The aggregates take "the single most profitable opportunity" per condition or market to avoid summing overlapping opportunities. Conditions of the same NegRisk market are counted separately in the single-condition analysis. The combinatorial pairs overlap: one GOP-margin market is in pairs 1 and 2, and one balance-of-power market is in pairs 2 and 4 (§7.3), so pair-level profits are not independent. The sample is dominated by one event cluster, the 2024 US election.

### Prospective tradability: mostly hindsight (my assessment)

1. **The detection uses no executable quotes.** It combines trade VWAPs from different blocks, carried forward for up to 2.5 h. Once a token goes 5,000 blocks without trading, its price is set to **0**. A stale or zeroed NO price combined with a fresh YES price mechanically yields "YES+NO < 1". That plausibly explains a median single-condition "profit" of about $0.60 per dollar, which no live order book would display (PLAUSIBLE, strongly).
2. **Polymarket's YES and NO books are mirrors of one order book.** A YES bid at p *is* a NO ask at 1−p, and complementary buys or sells are crossed by split or merge. A resting YES ask plus NO ask below $1 therefore cannot persist. Gebele et al. (2026, App. A) replayed 308.4M WebSocket messages from 8–15 May 2026 and found the books to be exact mirrors apart from 20 isolated API inconsistencies (VERIFIED in that paper, which uses 2026 data, not 2024).
   - So the paper's $10.6M of single-condition "realized" profit is most plausibly **legged inventory**: an address that bought YES and later bought NO within an hour after the price moved, or a market maker whose fills on both sides net to a complete set.
   - That is a directional bet at the time of the first leg, or a market-making P&L. It is not riskless arbitrage identifiable ex ante (PLAUSIBLE).
3. **The "realized" metric ignores whether the position was held to resolution or unwound.** It also counts complete sets assembled from fills that were individually directional.
4. **Combinatorial opportunities need manual rule validation.** Only 13 of 46,360 LLM-screened pairs survived. Their realized value (about $95k) is negligible compared with the headline.

## Independent re-estimates and critiques (later literature)

- **Gebele, Mutzel & Matthes (TUM), "Executable Arbitrage and Market Efficiency in Prediction Markets", arXiv:2608.00666v1, 1 Aug 2026** (VERIFIED, main text and App. A read).
  - **On this paper (§7):** they restate its estimates as $10.6M same-condition and $29M NegRisk. They note its block-VWAP/5,000-block carry-forward and its 950-block grouping. They exclude same-condition rebalancing as non-executable on a unified book.
  - **Their re-estimate:** with mechanism-linked criteria over the **same 1 Apr 2024–1 Apr 2025 window**, they find **$291,424**, about **0.74%** of the $39.6M headline. The criteria are an Adapter conversion fed by inputs bought within 5 blocks, or a complete basket formed within 10 minutes.
  - **All their panels together:** about $1.118M, of which $1.086M is converter-enabled and $32k is settlement baskets. The panels are FPMM history plus CLOB fills for events listed through 31 Dec 2025.
  - **2026 quotes:** a depth-aware, fee-adjusted L2 replay (14 Apr–19 May 2026, pmxt archive) found 2,098 positive YES-side episodes and 36 NO-side. Median exact durations were 16.15 s (YES) and 7.99 s (NO).
  - **Overlapping addresses:** the address prefixes 0xd218…, 0x63d4… and 0x59ee… appear both in this paper's Table 1 and in Gebele et al.'s Fig. 4 list of top converter-profit addresses. This suggests the top "arbitrageurs" here are NegRisk-Adapter users (VERIFIED prefix match only; full addresses not compared).
- **Cheng, Yang & Zou (UCLA), "Arbitrage Analysis in Polymarket NBA Markets", arXiv:2605.00864v1, 22 Apr 2026** (VERIFIED: abstract, intro and methods excerpts read, not the full text).
  - They describe this paper as using "executed trade data" and position their own CLOB `/book` snapshots as the methodological advance.
  - **Data:** 75.1M snapshots, 173 games, 4 Feb–4 Mar 2026.
  - **Single-market:** 7 executable in-game single-market episodes (median 3.6 s), with $210.19 of aggregate profit capped at $100 per episode.
  - **Combinatorial:** 290 episodes (median 101 bp), with 76.9% limited to an average of 14.8 shares.
  - They say their $10 liquidity floor is "consistent with the approach of Saguillo et al.", but Saguillo et al. filter fills under **$2**, so that is a small mis-citation in Cheng et al.
- **Shen et al., "The Ghosts of Polymarket", arXiv:2606.16852v2 (10 Oct 2026)** cites this paper only descriptively ("roughly $40M"). They document 2,037,304 reverted match transactions in which matched orders fail on-chain. Reverted fills do not emit `OrderFilled`, so trade-based studies see only settled fills, while live arbitrage legs can fail at settlement (VERIFIED abstract and related-work paragraph only).
- **Tsang & Yang, arXiv:2603.03136v3** does not cite this paper. It is relevant because naive aggregation of mint/burn-inside-trade fills overstates turnover (Trump market, Oct 2024: $391M turnover against $958M naive volume). Studies that sum `OrderFilled` "bids" without that decomposition overcount (VERIFIED abstract only).
- No erratum, published comment or arXiv v2 was found as of 2026-10-17.

## Other errors and inconsistencies in the paper
1. **Wrong emitting contract.** The paper says the Conditional Tokens contract (0x4D97…) emits `OrderFilled`. **That is wrong (VERIFIED).** I fetched the receipt of Polymarket fill tx 0x50eeb407…7b3d (Polygon block 63,913,208, 5 Nov 2024) via polygon.drpc.org and decoded it with my own keccak topic hashes:
   - `OrderFilled` ×2 and `OrdersMatched` ×1 were emitted by **0xC5d563A3…f80a (NegRisk CTF Exchange)**.
   - `PositionSplit`, `TransferSingle` and `TransferBatch` came from 0x4D97….
   - A replicator who filters logs by the CT address alone would get no fills. The text also mixes the names "OrdersMerged" and "PositionsMerge".
2. **Profit threshold:** the text says 5¢, while the figure captions say 2¢.
3. **Combinatorial pair counts:** "5 cases" are claimed but 4 values are listed. The checker kept "4 NegRisk–NegRisk" pairs, yet manual review then yields "11 NegRisk–NegRisk", which is impossible as written. §5.2 also cites "Definition 3" where the combinatorial definition is Definition 4.
4. **Headline total** does not reconcile with the itemised components (about $9.6k gap).
5. **The abstract's "on-chain historical order book data" is executed fills.** Polymarket's book is off-chain, and the paper itself uses `OrderFilled` events.

## Likely misreadings to watch for in the earlier discussion
- "$40M of arbitrage profit was available or earned risk-free." In fact it is an upper-bound-style inference from legged fills, gross of fees, leg risk and lock-up, with no resolution check. An executable-mechanism re-estimate for the same window is about $0.29M.
- "$40M from combinatorial or logical arbitrage." In fact combinatorial is about $95k. About $29M is NegRisk within-market rebalancing and about $10.6M is same-condition YES/NO.
- "Shows arbitrage is open to a retail trader." The paper simulates no trading. Later quote-level studies find edges lasting seconds, limited by depth, and now subject to taker fees.

## What must be replicated before risking money
1. **Rebuild the opportunity set from executable quotes,** meaning L2 books or a WebSocket recorder, not trade VWAPs or `/prices-history` (which per CONTEXT.md is not executable). Never set a missing price to 0 or carry it forward.
2. **Decode fills correctly.** Use `OrderFilled` from the CTF Exchange and NegRisk CTF Exchange, deduplicate maker and taker fills (CONTEXT.md OrderFilled semantics), and pair them with split, merge and NegRisk-Adapter conversion events in the same transaction.
3. **Apply the current per-market `feeSchedule`** (taker fee p(1−p) form) and rebates. Use maker versus taker execution realistically. Include `secondsDelay` on sports markets.
4. **Model non-atomic multi-leg execution:** latency (episodes last seconds), queue position, partial fills on each leg, and matched-but-reverted settlements (Ghost Fills).
5. **Model capital lock-up** until resolution, giving an annualised edge. Model resolution risk (UMA disputes, ambiguous rules such as the paper's FIDE example) and NegRisk placeholder or "other" outcomes.
6. **Test on post-V2 (2026) markets out of sample.** The paper's window is pre-fee, pre-V2, USDC-collateralised and dominated by the US election.
7. **Combinatorial pairs** need rule-text verification (identical resolution source and timing). LLM dependency flags had a false-positive rate of about 97% after the checker (374 → 13).
8. **Compare wallets against realised P&L.** Check the "realized" figures against wallets' actual resolved P&L (Data API v2 `user-pnl` and `positions`) for the top-listed addresses before treating them as arbitrage.

## Search log
- arXiv API `ti:"probabilistic forest"` returned exactly one hit, 2508.03474v1 (title, authors, abstract, cs.CR/q-fin.TR).
- arXiv abs page: submission history shows v1 only (5 Aug 2025, 9,604 KB) and the DataCite DOI. There are no comments or journal-ref fields.
- arXiv PDF v1 (36 pp.): downloaded and fully extracted with pdftotext (layout and plain).
- Crossref `query.bibliographic` and `query.title`: no Crossref record for the LIPIcs DOI among the top hits. Unrelated SSRN items surfaced ("Combinatorial Arbitrage in Prediction Markets", Zhai & Shi 2026; "Same Bet, Different Markets", Krause 2026; "Endogenous Limits to Arbitrage in Prediction Markets", Gill & John 2026). None of them is this paper, and none was read.
- OpenAlex: **dead end**, HTTP 429 daily budget exhausted ("Rate limit exceeded").
- WebSearch on the exact title: found arXiv, IMDEA Networks event pages, IDEAS/RePEc, EconPapers, IMDEA DSpace (hdl 20.500.12761/1941), alphaXiv and a Hugging Face papers mirror.
- WebSearch "AFT 2025 LIPIcs Saguillo …": found DROPS LIPIcs.AFT.2025.27. I downloaded the PDF (24 pp., created 2025-09-08) and the DROPS JSON-LD (datePublished 2025-10-06, pages 27:1–27:24, volume 354).
- IMDEA DSpace full record: conference object, AFT, 8–10 Oct 2025, Pittsburgh, refereed TRUE, status "inpress", title spelled "Unraveling".
- WebSearch for GitHub code or dataset: none found.
- WebSearch for follow-ups by the same authors: none found. A press lead, DL News, "Polymarket users lost millions of dollars to bot-like bettors over the past year", gives only a snippet. It is not verified and not used for any number.
- arXiv API `abs:polymarket AND abs:arbitrage`, `"combinatorial arbitrage" AND prediction`, `"market rebalancing arbitrage"` and `ti:"arbitrage in prediction markets"` surfaced 2608.00666, 2605.00864, 2606.16852, 2604.03888 (PolySwarm, not read) and 2606.19517 (not read). I grepped downloaded PDFs for citations: 2608.00666, 2605.00864 and 2606.16852 cite the paper, and 2603.03136 v3 does not.
- Polygon RPC: publicnode refused historical logs and receipts ("Archive requests require a personal token"). polygon-rpc.com returned 403 (tenant disabled), llamarpc gave a 502 tunnel error and 1rpc hit its usage limit. **polygon.drpc.org worked** for `eth_getTransactionReceipt`.
- The tx hash came from CryptoHouse `polymarket.orders_filled` (2024-11-05 12:00 UTC). The `transaction_hash` column is stored as raw bytes in FixedString(66), so it must be hex-encoded.
- Polymarket/ctf-exchange GitHub `ITrading.sol` confirms `event OrderFilled(bytes32 indexed orderHash, address indexed maker, address indexed taker, …)` is declared by the exchange, not by the CT contract.
- Scratch files (not part of the repo) are in `/tmp/claude-0/-home-user-Momemtum-Quality-Strategy/ae955eb9-57eb-588c-b2e8-f58244a974f1/scratchpad/pf/`: paper.txt, paper_plain.txt, lipics.txt, dl3/*.txt and scripts/keccak_logs.py.
