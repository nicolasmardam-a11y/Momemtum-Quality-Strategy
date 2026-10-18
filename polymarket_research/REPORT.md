# Polymarket for a retail trader: what is testably profitable after costs?

**As-of:** research date 2026-10-17; live data pulled 2026-10-17 15:00 UTC to 2026-10-18 07:00 UTC.
**Scope:** public, read-only data only. No wallet was connected, no order was placed, no data was bought,
nothing was deployed. Labels: **VERIFIED** (checked in the primary source or the data), **PLAUSIBLE**
(consistent with the evidence, not checked directly), **UNSUPPORTED**.
**Evidence base:** every number below comes from a notes file under `notes/` (paths given). The strategy tests
were pre-registered and then audited adversarially; the wallet case studies, platform notes and literature synthesis
were reviewed adversarially but not pre-registered. Code is under `analyses/`, the shared read-only client under
`pmr/`, the alert system under `alerts/`.

---

## Bottom line

**Nothing tested here justifies risking money yet.** Two strategies are *marginal* and capacity-limited,
and deserve a cheap forward paper test. Everything else, including the wallet-following idea that motivated
the project, was rejected or showed no demonstrated edge at executable prices after the current fees.

**Test first (paper / read-only):**
1. **k-of-n "all-NO" count-set baskets** (cross-market logical arbitrage). This is the only family with genuine
   payoff dominance after per-leg fees and a verified rules check. Example: the 19 separate "nominated for Best
   Actor?" markets, of which at most 5 can resolve Yes. Buying NO on all 19 pays at least 14 per set. That
   basket was profitable after fees in 34 of 34 snapshots over 15.4 h. **But** the total standing profit across
   all verified baskets shrank from $527 to $314 while we watched (Best Actor alone: $481–483, then $237).
   Capital-weighted, the verified baskets return 9.4–12.1%/yr (10.75% pooled) on capital locked to January 2027,
   against a pre-registered 10% hurdle. Capacity is about $10k. Verdict: **marginal**.
2. **Buying favourites priced ≥ 0.95 seven days before the scheduled end (kick-off for sports), in small size.** Such favourites lost only
   0.54× as often as their prices implied (95% CI 0.36–0.78), so the bias is real. After the audit, the
   expected net is about **+0.5% per ~8-day hold**, it is fragile to one loss, and it fades above about
   $500 per market. Verdict: **marginal**.
3. **A maker-side version of (2), and selective quoting.** This is the only family the 2026 fee design
   structurally favours: makers pay 0 and receive rebates, while takers pay `rate × p(1−p)`. It is unproven:
   historical markouts are economically nil, and a short live sample (114 market-hours) was weakly negative. It needs forward
   order-book collection before any verdict. Verdict: **no demonstrated edge; research only**.

**Reject or deprioritise:**
- **Your screen, "5 bets in 12 months, all 5 won", is rejected.** Run point-in-time on 2024–25 on-chain data, a
  follower loses **−7.1%** per $ staked on the held-out period (95% CI −10.6% to −3.7%; 1,542 events). The
  screen mostly selects people buying ~0.98 favourites. All 28 pre-registered hypotheses (9 screens × 3 signal
  types, plus a cluster signal) were rejected, including skill-based, category-specialist, large-bet,
  returning-wallet and clustered-new-wallet signals.
  Skilled wallets' edge exists at *their* prices but is gone at the price a follower gets two minutes later.
  A 2026 holdout on Protocol V2 data replicates this (S1 −3.2%; no screen beats matched random entries).
- **mintblade is not a copyable signal.** Its "5-for-5" counts markets, not events: it is really 3 decisions
  (one a $4.81 test ticket). Run point-in-time, your screen would have copied **zero** of its trades. It has
  not traded since 16 June 2026.
- **Hourly monitoring is too slow** for every signal type observed.
- **Binary YES+NO arbitrage is structurally impossible.** The two books are one mirrored book.
- **Multi-outcome (neg-risk) complete-set arbitrage:** 0 of 436 re-checked group-rounds were profitable after
  per-leg fees.
- **Crypto spot→Polymarket lead–lag:** −4.1¢ per trade held to resolution (95% CI −11.3 to +2.9) and −2.6¢ at a
  30 s markout (significant). Competition is sub-second.
- **Taker mean reversion after shocks:** about +7.9% per $ gross, but less than costs.
- **Near-resolution ≥ 0.99:** no demonstrated edge.
- **Buying favourites at 0.80–0.95 one day before the end (rule E1):** rejected (−6.5% net in liquid markets;
  −0.6% to −3.4% in unscreened markets). Buying ≤ 10¢ longshots also loses heavily.
- **Cross-venue Kalshi:** inconclusive, and blocked by access rules and data terms for most people.

---

## 1. Platform facts that drive every result (verified 2026-10-17)

| Topic | Fact | Source |
|---|---|---|
| Taker fee | `fee = shares × rate × p × (1−p)`, takers only, rounded to 5 dp. Makers never pay. **The rate is set per market** (`feeSchedule` in Gamma), not by category. Today: most sports 0.05; NFL/college football (created from 2026-09-04) and legacy `sports_fees_v2` 0.03; politics/finance/tech/mentions 0.04; crypto 0.07; geopolitics markets mostly 0. 99.6% of 288,003 open markets charge fees. | `notes/platform/fees_incentives.md` (on-chain check of 20,740 fills) |
| Fee history | About ten changes in 2026: 15-min crypto (Jan 5), all categories (Mar 30), Protocol V2 / pUSD (Apr 28), crypto 0.072→0.070 (May, unannounced), all sports 0.03→0.05 (Jul 10–11), NFL/CFB 0.03 (Sep 4). **Backtests on 2024–25 data were effectively fee-free.** | same |
| Round-trip cost | At tier 0 with a 1¢ spread: buy at 0.30 and sell later at an unchanged mid costs 3.10¢ in sports (**10.3% of capital**) and 3.94¢ in crypto. Hold-to-resolution at 0.90 in sports costs 0.45¢ (0.5%). | same, §5 |
| Taker rebate | Live since 2026-05-28. 3% (Bronze) to 50% (Obsidian) **of fees paid**, by 30-day weighted volume. VERIFIED: mintblade's payout = 18% × that day's fees, to the cent. Obsidian halves the fee, not the spread. | same |
| Maker incentives | Maker rebates are 15–25% of taker fees in the same market. Liquidity rewards were $173k–289k/day across ~14.5k markets, **median about $3/day per market**, and allocations churn hourly. Holding rewards are paid on 339 markets; the stated rate conflicts (4.00% vs 3.25%). All discretionary. | same; `notes/strategies/lp_rewards_live.md` |
| Order book | YES and NO books are one mirrored book: BUY+BUY matches as a mint, SELL+SELL as a merge. Sports orders have a 1 s delay (3 s on ~533 markets) and cannot be cancelled during it. 5m/15m/1h crypto up/down markets have a 150 ms taker delay. | `notes/platform/mechanics.md` |
| Settlement | Match to chain ~2.3 s; auto-redeem ~12 s after resolution. Sports resolve a median ~4.2 h after kick-off; UMA disputes 0.08% of markets (5.1% of geopolitics markets ≥ $10k volume); 50-50 outcomes 0.56% of traded markets. Live UMA bonds $250–500 and a 15-min challenge window on ~89k markets differ from the docs. | `mechanics.md`, `notes/strategies/universe.md` |
| Data API | **v1 will be retired on 2026-10-24**; everything here uses v2. Identical-URL polls are CDN-cached up to 300 s (median 112 s stale); cache-busted polls see a trade ~4.6 s after its block. The public RTDS `activity` websocket sees all wallets' trades ~2.2 s after the match (no server-side wallet filter). **No historical order books** are published. | `notes/platform/data_infrastructure.md` |
| Historical data | Gamma: 4.15M closed markets 2024-01..2026-10. CryptoHouse SQL: 257.6M on-chain fills, **2022-11-21 to 2026-01-05 only** (pre-V2). Free third-party 1-min L2 archive (Feb–Aug 2026) has a **gap on 12–17 June 2026**, mintblade's window. | same; `universe.md` |
| Access | polymarket.com bars US, UK, France, Germany, Italy, Australia and Singapore, plus about 40 other jurisdictions including Taiwan, Thailand, Russia and Poland (ToS covers residence, location and citizenship; VPNs prohibited). Polymarket US (CFTC-regulated) is a separate book with different fees and no public trade tape. Kalshi's data terms may restrict systematic collection. **Your own eligibility must be confirmed before any trading.** | `notes/platform/geography_legal.md` |

---

## A. Ranked strategy table

Capacity is measured at executable prices today. "Locked" means capital is tied up until resolution.

| Rank | Family | Mechanism | Strength of evidence | Data availability | Execution difficulty | Capital intensity | Likely capacity | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | **C. k-of-n count sets** (all-NO baskets) | Separate markets are quoted independently, and liquidity rewards pay makers to rest YES bids in each one, so Σ YES bids can exceed the k slots that can pay | Live executable books, per-leg fees, official rules checked (Oscars Rule Five §6 on oscars.org), 34/34 snapshots over 15.4 h, audited | Public CLOB books + Gamma rules text | Medium: 19–50 taker legs, leg risk, 5-share minimums | High: locked ~95 days | ~$6–10k standing; one-off stock, recurrence unmeasured | **Marginal** → forward test |
| 2 | **E. Favourites ≥ 0.95 at T−7d** (= fading ≤ 5¢ longshots) | Long-dated favourites are underpriced (loss ratio 0.54×, VERIFIED); lock-up aversion and longshot preference are PLAUSIBLE causes | Pre-registered, 2026 TEST, audited; fragile (one loss flips the mean); only 25 losses pooled | Gamma + `/prices-history` + tapes; live asks for forward test | Low | Locked ~8 days | ~$500 per market; net ≈ 0 at $2.5k | **Marginal** → paper test |
| 3 | **D. Maker-side favourites / selective quoting** | Zero maker fee + rebates + rewards, against adverse selection and inventory | Literature: makers out-earn takers everywhere, but fill-conditional. Ours: historical realised spread ≈ 0.0–0.1¢/share; live 114 market-hours weakly negative (4 fills drive it) | **Needs forward book capture**; free 1-min L2 Feb–Aug 2026 exists | High: queue position, cancels, monitoring | Moderate | Unknown | **No demonstrated edge** → research |
| 4 | H. Near-resolution ≥ 0.99 (T−6h) | Lock-up aversion near settlement | Pre-registered, audited | Same as 2 | Low | Short lock | Tiny | No demonstrated edge |
| 5 | F. Taker mean reversion after ≥ 10¢ shocks | Order-flow pressure reverses | Pre-registered, 869 TEST trades, audited: gross +7.9%/$ but net −0.6% | Tapes | Medium | Short | n/a | No demonstrated edge |
| 6 | A. Wallet following (all screens) | "Informed" wallets lead prices | **Strong negative.** PIT on 2024–25 on-chain fills: 28 pre-registered hypotheses rejected; 0 of 8,526 testable exploratory variants survive under outcome-neutral estimators; 2026 V2 holdout also negative (S1 −3.2%, S2 −0.6%, S3 −3.8%, S5 −4.0%) | CryptoHouse (to 2026-01-05), Data API v2 | Medium–high (seconds matter) | Varies | n/a | **Rejected** |
| 7 | G. Lead–lag (crypto spot, Kalshi, sports) | Slow incorporation of public info | Crypto: −4.1¢/trade (CI −11.3 to +2.9), 30 s markout −2.6¢ [−3.8, −1.5]; Kalshi/sports inconclusive (no Kalshi data by design; 6 sports events) | Binance/Coinbase public; Kalshi terms risk | Very high (sub-second) | Short | n/a | No demonstrated edge |
| 8 | B. Complete-set (binary and neg-risk) | Sum of outcome prices ≠ 1 | Binary: 0 of 2.59M market-scans (structural). Neg-risk: 8 of 252k group-scans net-positive, 0 of 436 on re-check | Public books | High (legging, in-play flickers ~2 s) | Low if converted | $0/day demonstrated | No demonstrated edge |
| 9 | E. Short-dated favourites (E1: 0.80–0.95 at T−1d); buying longshots | Favourite/longshot mispricing at short horizons | Pre-registered, rejected: E1 −6.5% net (liquid), −0.6% to −3.4% unscreened; buying ≤ 10¢ longshots −48% to −88% | Same as 2 | Low | Locked | n/a | **Rejected** |

---

## B. Verified academic evidence

Full synthesis: `notes/literature/LITERATURE.md`, 72 references. 62 were adversarially cross-checked (33 confirmed,
23 corrected, 6 unverifiable); about 10 peripheral entries were not.

### B.1 The four titles from the earlier discussion: all exist, but each was mis-characterised

| Supplied title | Exact reference (VERIFIED) | What it actually shows | Correction |
|---|---|---|---|
| "Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets" | Saguillo, Ghafouri, Kiffer, Suarez-Tangil. arXiv [2508.03474](https://arxiv.org/abs/2508.03474) (2025-08-05); **peer-reviewed** at AFT 2025, LIPIcs 354, art. 27 | Descriptive. "$39.6M realised arbitrage" (2024-04 to 2025-04): ~$10.6M same-condition, ~$29.0M neg-risk, only **~$95k combinatorial**. Inferred from fills priced by VWAPs carried forward 2.5 h and then set to 0; fees, depth and latency ignored | The $40M is not risk-free and not net. A mechanism-linked re-estimate for the same window finds **$291,424** ([Gebele et al. 2026, arXiv 2608.00666](https://arxiv.org/abs/2608.00666)). The headline does not reconcile with its own components. |
| "Who Wins and Who Loses in Prediction Markets? Evidence from Polymarket" | Akey, Grégoire, Harvie, Martineau. [SSRN 6443103](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6443103) / CEPR DP21615, working paper (version 2026-06-12) | Descriptive. 2.48M wallets to 2026-03-29: ~69% lose; top 1% of winners take 76.5%; maker share is the strongest correlate of profit; persistence modest, 44% stop after a month | Not published. "Top 1% capture 84%" is from a superseded draft. No strategy is tested. |
| "The Favorite–Longshot Bias in Prediction Markets: Evidence from Polymarket" | Cardozo, Rivero-Wildemauwe. arXiv [2609.12878](https://arxiv.org/abs/2609.12878) (2026-09-11), preprint | Pre-fee, to 2026-03-29. Longshots −6.3% (equal-weight markets) but **+4.1%** at event weighting; the headline "−19.3¢" is **not significant**; no FLB in Sports; favourites +0.28% to +0.83% | Unreviewed preprint. The bias is small, depends on aggregation, and is pre-fee. |
| "Exploiting Mean-Reversion in Decentralized Prediction Markets: Evidence from Polymarket Binary Contracts" | Vojtko, Dujava (Quantpedia). [Blog 2026-04-17](https://quantpedia.com/exploiting-mean-reversion-in-decentralized-prediction-markets-evidence-from-polymarket-binary-contracts/), SSRN 6726362, preprint | In-sample simulation on **3 hand-picked contracts that all resolved No**, at mid prices, with 0–10 bp costs | Practitioner preprint. Selection is in hindsight and the cost assumption is ~5–6× too low; our reproduction finds no variant beats buy-and-hold at realistic costs. |

### B.2 Established findings that matter most (literature; full table per family in `LITERATURE.md` §2)

- **No paper demonstrates a strategy that is selectable ex ante, executed at executable prices, net of the
  current fee regime, and out of sample.** The only real-money result is a 2012 Intrade/Betfair cross-venue
  trial: +6.38% over 3 months ([Rothschild & Pennock 2014](https://doi.org/10.3233/AF-140031)), on a venue
  pair that no longer exists.
- **Arbitrage (B, C):** in 2026 L2 data, positive neg-risk episodes last a median 16 s and profit per
  conversion fell from ~$1 to ~$0.08 ([GMM26](https://arxiv.org/abs/2608.00666)). NBA moneyline-vs-spread
  episodes: median edge 101 bp, 16 s, ~15 shares, fee-free ([CYZ26](https://arxiv.org/abs/2605.00864)).
- **Makers vs takers (D):** makers out-earn takers on Polymarket, Kalshi and Betfair (AKEY26;
  [BDW25](https://www.ifo.de/DocDL/cesifo1_wp12122.pdf); [WHE25](https://mpra.ub.uni-muenchen.de/126351/)).
  Every reported maker return is conditional on fills; no Polymarket fill-level maker backtest exists.
- **Lead–lag (G):** Polymarket BTC 15-minute quotes respond to Binance moves after a median **347 ms**; out of
  sample the Polymarket mid beats a 43-feature model, and simulated trading loses
  ([YOU26](https://arxiv.org/abs/2607.26245)).
- **Near-resolution (H):** BTC 5-minute markets are calibrated at the top (0.982 price vs 98.4% wins), and
  final-seconds settlement pushes flip ≥ 0.90 favourites 34% of the time in manipulated cycles
  ([DJY26](https://arxiv.org/abs/2606.31675)).
- **Wallet following (A):** there is no time-ordered, latency-adjusted copy test for Polymarket. In equities,
  under 1% of day traders predictably earn net profits ([BLLO14](https://doi.org/10.1016/j.finmar.2013.05.006));
  copiers of selected memecoin leaders lost ~6–8% ([LUO26](https://arxiv.org/abs/2601.08641)); leaderboards
  select lucky risk-takers ([AOW20](https://doi.org/10.1287/mnsc.2019.3508)). The first CFTC insider case on
  event contracts (a Polymarket "Maduro out" trader) is an allegation, not a selectable pattern
  ([CFTC](https://www.cftc.gov/PressRoom/PressReleases/9217-26)).

**My extrapolations (PLAUSIBLE, not in any paper):** at today's rates a taker favourite buyer needs a pre-fee
edge of roughly 0.6–1.2% per $ at 0.90–0.95, larger than any robust published estimate. A calibrated bettor
who only buys at 0.85 wins five of five 44% of the time with zero edge. The 2026 fee design helps only makers.

---

## C. Wallet-screen findings: mintblade and the possibly related wallets

Full detail: `notes/wallets/WALLETS.md` (consolidated and adversarially reviewed), plus `mintblade.md`,
`grimdrip_endlessfate.md`, `linkage.md` and `copyability.md`.

### C.1 What was verified

| Wallet (proxy address) | Profile (VERIFIED via Gamma `/public-profile` and Data API) | Activity | Markets / distinct events | Realised P&L (cash basis, reconciled on-chain) |
|---|---|---|---|---|
| `0x96cf…1acb` | **mintblade**, created 2026-06-02 14:47:45Z, user id 8422116 | 727 buys (166 taker / 561 maker), 5 redemptions; trades 2026-06-03 and 06-15/16 only | **5 markets / 3 events** | **+$9.11M** (+$28.8k rebates); fees $127k; peak capital $7.98M |
| `0x3f87…742c` | **GRIMDRIP**, created 14 min after mintblade, user id 8422276 | 670 fills, one match (Czechia–South Africa, 2026-06-18) | 2 / 1 | +$7.51M |
| `0x5e4c…dba2` | **endlessFate**, created 2026-04-27, user id 7713278 | 474 fills, 2026-06-12 to 06-18 | 9 / 7, **3 lost** | +$7.25M |

**mintblade's five markets are three decisions:**
1. A **$4.81 test ticket**: 5 shares of the Mets at 0.96, bought in-play after a 4-run inning. The "$0" P&L
   shown is +$0.19.
2. **Saudi Arabia–Uruguay**: one nested "Uruguay does not win" bet split across Uruguay-No, Saudi +1.5 and
   Draw. All three legs won only because the match was drawn (market-implied probability 0.236).
3. **Iran–New Zealand**: a $7.14M "Iran does not win" bet at ~0.49, an even-money call, which won on a 2–2 draw.

**Timing (no identity or insider inference is made):** both large bets were placed in the ~47 minutes before
kick-off, with prices flat before entry. No fill followed a goal or card; the match's first goal (New Zealand's)
came 6.5 min after the last fill. Decoded order timestamps show the final orders were signed around the inferred
kick-off (PLAUSIBLE, ±1 min). The wallet
was 72.6% of all taker volume in its Iran window and moved the price by 4¢.

### C.2 The screens

| Screen | mintblade | GRIMDRIP | endlessFate | All three as one entity |
|---|---|---|---|---|
| Exactly 5 resolved decisions, all won | Pass **only counting markets**; fail by events (3); fail with a $100 minimum stake | Fail (1 event) | Fail (3 losses) | Fail (13 markets, 10 won) |
| ≥ 5 resolved decisions, no observed losses | Same as above | Fail | Fail. **Trap:** its 3 losers were never redeemed, so `/positions?status=CLOSED` shows a spurious 6-for-6 | Fail |
| Luck: P(P&L ≥ observed) if each bet's true probability were its entry price | 0.11 | 0.29 | 0.17 | 0.028, heavily selection-biased |

**Why 5-for-5 is weak evidence.** It counts outcomes, not edge versus entry price, and nested legs inflate the
count. In 2025 on-chain data, 1–4% of eligible wallets (**~11,800 wallets** at 2025-12-01) passed "exactly
5, all won" at any time. On the audited test dates, 85% of their entries were at ≥ 0.90 and the median member's
trailing profit was **$0.43** ($0.56 across all dates); half dropped out the next month
(`notes/strategies/pit_wallets_build.md`, `pit_wallets_FINAL.md`). Searching that many wallets
guarantees thousands of perfect records by luck.

### C.3 Linkage (classified, not asserted)

- **No shared key and no direct transfer** (VERIFIED). All three are Polymarket V2 Deposit Wallets with distinct
  owner EOAs. All 1,862 order signatures recover to each wallet's own owner, and there were zero transfers
  between the wallets or owners.
- **Strong probabilistic link: a common financial counterparty** (VERIFIED flows). Withdrawals from all three
  reached the same Etherscan-tagged *Binance Deposit* address A on 2026-06-18, directly (mintblade) or via
  single-purpose hop addresses (GRIMDRIP, endlessFate); a second deposit address B received funds from mintblade
  and endlessFate. A deposit address identifies an exchange account, not a person; an intermediary serving several
  clients is not excluded.
- **Weak:** all deposits came from Binance hot wallets. That is meaningless on its own.
- **Extended cluster (PLAUSIBLE membership):** **LEEEROYJENKINS** (−$2.75M overall) and **FlickRaw**
  (−$4.87M) fit the same pattern. endlessFate, LEEEROYJENKINS and FlickRaw signed **identical non-round orders
  0.4–2.1 s apart, before any was mined** (VERIFIED). That shows coordinated control of those orders, not
  ownership. Selecting only the winners of such a group is exactly the selection bias the brief warned about.

### C.4 Could a follower have profited? (the question that matters)

- **Point-in-time: your screen copies 0 trades.** mintblade only qualified after its last market resolved, and
  never traded again.
- **With hindsight**, a follower 5 s to 2 min behind would have matched the wallets' returns, because pre-match
  prices barely moved: **+$332 per $1,000** with equal weight per event (the +$932 figure over-weights one
  match). That reproduces outcome luck. 87% of the profit is one drawn match, and the only non-luck component is
  ~1.5¢ of closing-line value from front-running the wallets' own buying.
- **Hourly monitoring:** World Cup kick-offs fall on the hour, so an hourly poll usually detects pre-match bets
  *at* kick-off. 82% of pre-match fills were first seen at or after it.
- **Exact book-based reconstruction is impossible:** no historical books exist, and the free archive misses
  12–17 June 2026. Follower prices are proxied from later taker prints, an upper bound for large sizes.

### C.5 The general point-in-time test (2024–25, then a 2026 holdout)

`notes/strategies/pit_wallets_results.md`, pre-registered, then audited (`pit_wallets_FINAL.md`).
- **Design.** Monthly selection dates 2024-01..2025-12, using only fills and resolutions before each date.
  Follower entry is the first other-wallet taker print ≥ 2 min after the signal (plus 0.01, which is ten ticks above 0.96),
  held to resolution. Benchmarks: random eligible wallets (B1), price- and category-matched prints (B2), a favourite
  rule, and T-bills. Inference is event-clustered, with Holm and reality-check adjustments.
- **TEST (selection dates 2025-07..12):** S1 "exactly 5, all won" **−7.1%** [−10.6, −3.7] at zero fee and
  −7.8% at current fees, and between −8% and −10% at every delay from 5 s to 60 min. S2 "≥ 5, no losses"
  −3.2% [−4.5, −2.0]; S3 skill −7.8%; S4 category specialists −2.9% to −6.0%; S5 top-1% P&L −1.8%
  [−5.1, +1.5]. Large-bet, returning-wallet and fresh-wallet-cluster signals were also rejected. All 28
  confirmatory hypotheses were rejected (Holm p = 1.00); the auditor's recompute matched all 90 cells, and 0 of
  186 slippage/fee/estimator variants has a CI above zero.
- **Why 5-for-5 fails (luck null).** Among random eligible wallets with exactly 5 resolved bets, 26.9% won all
  five, while their own entry prices implied 23.5–30.1%. There is no excess skill. The median S1 member bought
  at 0.98, would have won all five by luck with probability ≥ 0.91, and made $0.43 on the record.
- **Skill is real but already priced.** Skill-screened wallets' own entries had +0.6 to +7.6 points of edge.
  At the follower's price two minutes later it was −0.2 to +0.2 points, and still negative at a 5 s delay.
- **Methodology trap (important for any copy-trading backtest).** Counting a signal as "filled" only when later
  prints exist makes even random wallets look profitable (+5.6% to +15.7% at $500–$10k sizes), because whether
  a signal fills depends on what the market does next. Outcome-neutral estimators remove it.
- **2026 Protocol-V2 holdout** (`pit_wallets_v2_holdout.md`, audited in `pit_wallets_FINAL.md`). One selection
  date (2026-06-01), signals June–September 2026, current per-market fees, 2-minute model.
  - Results: S1 **−3.2%** [−7.9, +0.5], or −2.6% [−7.2, +1.0] after the audit fixed a market-table gap that had
    misclassified 23 of 55 members. S2 −0.6% [−3.4, +2.2]; S3 −3.8% (corrected); S5 −4.0%. Random wallets (B1)
    −9.2% (audited).
  - No screen beats random entries matched on category, week and price (Holm p = 1.00), and none turns
    positive at a 5 s delay (S2 0.0%).
  - S1 is low-power (85–90 events), so its verdict rests on a negative point estimate consistent with 2024–25.
  - World Cup signals are too few to conclude anything.
  - **mintblade and GRIMDRIP were created on 2026-06-02, after the selection date**, so no point-in-time screen
    could have selected them.
- **Audit corrections** (none changes a verdict):
  - the cluster signal used the cluster's own prints;
  - the 2026 market-table gap;
  - 18 fills at or after resolution;
  - the +0.01 slippage is ten ticks above 0.96 (tick-aware variants do not change any verdict).
- **Verdict: no demonstrated edge for any wallet-following family, at any delay, net of current fees, against
  every benchmark.** The 2024–25 test split is now spent: any new wallet idea needs fresh data after 2026-10-17.

---

## D. The three strongest research candidates

### D1. k-of-n count-set all-NO baskets (logical arbitrage)

- **Mechanism.** A set of n separate Yes/No markets whose rules allow at most k Yes outcomes: award nomination
  slots, finalists, relegation places, top-k with an explicit tie-break. Each is quoted on its own, and liquidity
  rewards pay makers to rest YES bids in every one regardless of cross-market consistency (PLAUSIBLE).
- **Signal.** Σᵢ(1 − bestYESbidᵢ) + Σᵢ feeᵢ < n − k, walking each leg's ladder with equal shares (equivalently
  Σ YES bids > k plus fees). Each NO token's ask equals 1 − its YES bid (mirror verified).
- **Rules gate (manual, per set).** The official rules must cap the Yes count in every state. Check ties,
  co-nominees, postponements and administrative decisions, identical rules text across legs, and no duplicate
  names. Example: Oscars Rule Five §6 ("not more than five nominations"), verified on the oscars.org PDF.
  Classify each set TRUE / NEAR / CORRELATED; trade only TRUE.
- **Entry.** Taker-buy NO on every leg in equal shares, best edge first. Only buy while marginal set cost is
  < (n − k) × 0.995, with ≥ 5 shares and $1 per leg. Re-read all books within ~1 s before the first leg and
  abort if the edge falls below fees plus buffer.
- **Exit.** Hold to resolution (payoff ≥ n − k per set); optionally unwind early if the NO legs can be sold for
  more than cost.
- **Holding period.** ~95 days (Oscars nominations 2027-01-21); ~100 days (College Football Playoff title game).
- **Benchmarks.** A T-bill over the same lock-up; the 10%/yr pre-registered hurdle.
- **Capacity today.** $5k: ~$200 once over ~95 days (pre-audit estimate). $25k or $100k: capacity-bound at ~$10k
  for ~$314 (down from $18.2k for $545 about 8 h earlier).
- **Why it might persist.** It needs 19–50 taker orders, months of lock-up for 3–4%, and a manual rules check.
  No neg-risk convert exists to recycle capital, which deters dedicated arbitrageurs.
- **Main reason it might fail.** It may be a one-off stock, not a flow. The other risks: one wrong Yes among
  19–50 UMA resolutions costs 1 per set against ~0.5 of edge; a rule change; and leg risk across many orders.
- **Kill criteria (my proposal; pre-declare before the forward test).**
  - Fewer than ~$500/month of new TRUE-set net profit at ≥ 10%/yr on locked capital across 8 weekly scans.
  - Or the median opportunity fails the R5 buffer (< 0.5% of committed capital).
  - Or any TRUE set is found to break on rules re-reading.
- **Data.** Gamma events/rules (free), CLOB `/books` (free), per-leg `feeSchedule`. Scripts:
  `analyses/logical_arb/`.

### D2. Long-dated favourites ≥ 0.95 at T−7d (rule "E2"), small size

- **Mechanism.** Realised losses were 0.54× the price-implied rate (95% CI 0.36–0.78; 25 losses pooled across
  splits; VERIFIED). Break-even after base costs is 0.79×. Lock-up aversion and retail longshot preference are
  the PLAUSIBLE causes. Economically this is the same trade as fading ≤ 5¢ longshots.
- **Signal / entry.** Seven days before the scheduled end (`gameStartTime` for sports), taker-buy the side priced
  ≥ 0.95 if ask + fee ≤ 0.999, at ≤ $500 per market, across many events and days. Report soccer exact-score
  markets and stale books (no price change in 24 h) separately.
- **Exit.** Hold to resolution; capital returns at `closedTime` (~8 days).
- **Benchmarks.** E1 (favourites 0.80–0.95 at T−1d, rejected), H90 at 24 h / 1 h (rejected), H99 at T−6h (no
  demonstrated edge), T-bills, random favourites.
- **Evidence (2026 TEST, audited).** +1.0% net at the pre-registered model, but +0.57% unweighted [−0.49,
  +1.34]. One extra loss gives −0.75%. Model-based central estimate ≈ +0.5% per trade.
- **Capacity.** ~+0.25% at $500 per market, ~0 at $2.5k, negative at $10k. Trading every qualifying liquid market
  at $500 each would need ~$119k, so at $5k / $25k / $100k you would size about $20 / $105 / $420 per market.
  Below ~$119k the thin edge and the number of markets bind, not book depth.
- **Why it might persist.** Thin maker competition in long-dated books, and capital-cost aversion.
- **Main reason it might fail.** Costs eat most of the bias, and every trade carries a −100% tail.
- **Kill criteria (proposed by the audit, post hoc; fix before the paper test starts).** Kill if realised losses
  exceed **0.75×** the price-implied losses (Σ(1 − fill price)) once that sum reaches 5. My addition: also kill
  if the median paid ask exceeds the series price by > 0.5¢. The FLB note asks for at least 3 months of paper
  trading.
- **Data.** Live asks and depth at decision time (free), outcomes, settlement delay. Scripts:
  `analyses/flb_near_res/`.

### D3. Maker-side favourites and selective quoting (research, not a strategy)

- **Hypothesis.** Rest bids at or just inside the best bid on the D2 favourites, and quote two-sided in
  reward-eligible markets far from kick-off. The aim is to capture the favourite underpricing **without** the
  taker fee and half-spread that consume D2, while avoiding informed fills.
- **Signal / entry.** At T−7d, a favourite trading 0.95–0.98 with spread ≥ 1 tick: post a GTC bid at best bid,
  ≤ $500. Cancel when `gameStartTime` − now < 2 h, when sibling markets in the event move > 2¢, or when a
  followed-wallet alert fires on the opposite side. Here wallet alerts serve as a *toxicity filter*, not a copy
  signal.
- **Exit.** Hold filled shares to resolution (rebates accrue daily).
- **Benchmarks.** D2 taker version; random-time bids in the same markets; queue-aware fill model.
- **Evidence so far.** Historical realised spread +0.0–0.1¢/share and about 0 held to resolution. The live
  conservative-fill simulation was −0.63¢/share quantity-weighted (−0.31¢ equal-weight, CI includes 0), with
  99% of the loss in 4 fills.
- **Why it might persist.** The fee design pays makers. Most reward allocations are small and thinly contested,
  although the largest pools (~$500/day) are contested (median share 1.8%).
- **Main reason it might fail.** Adverse selection: bids on favourites fill precisely when bad news arrives.
  Queue position is unobservable historically.
- **Kill criteria.** Kill if fill-weighted 1 h markout < −(half-spread + rebate) over ≥ 1,000 conservative
  simulated fills in ≥ 100 markets across ≥ 4 weeks (the bar set in `lp_rewards_live.md`), with ≥ 30 events per cell.
  Also kill if the realised loss ratio on filled favourites exceeds 0.79×, or if the edge depends on rewards
  (discretionary).
- **Data needed (forward).** Websocket market-channel capture (book + price_change + trades) for ≥ 100 markets
  over ≥ 4 weeks. Optionally the free `Joseph3222/polymarket-orderbook` 1-min L2 (Feb–Aug 2026, excluding
  12–17 June) for a historical first pass.

---

## E. Implementation sequence

Cheapest and most likely to reject first. Everything below is read-only until a trading decision is made
separately.

**Already done (this project).** Historical rejection tests for A, B, E, F, G and H; the PIT wallet study; live
scans for B, C, D and G; the alert system.

**Stage 1: immediately, public data, no forward collection needed.**
1. **D1 recurrence scan.** Run `analyses/logical_arb/` weekly (read-only) and log every TRUE/NEAR set, its depth
   and net edge. First decision on "stock or flow" after 8 weekly scans; keep logging to the 2027-01-21
   resolution. Cost: minutes per week.
2. **D2 paper log.** Each day, list markets with a side ≥ 0.95 at T−7d, record the executable ask, depth and
   fee, paper-fill, and track outcomes. Apply the kill rule continuously. Cost: one small daily job.
3. **Historical first pass for D3** on the free 1-min L2 archive (Feb–Aug 2026) for a sample of favourites.
   Estimate how often a resting best bid would plausibly have filled, and the markouts after those fills.

**Stage 2: needs forward collection (continuous process).**
4. **Order-book recorder.** Market-channel websocket for ≥ 100 markets (D2 candidates + reward-eligible), stored
   compactly with local timestamps. Prerequisite for any maker verdict (D3).
5. **Wallet signals, only if you still want them.** Record the RTDS `activity` firehose (~2 s latency), apply a
   pre-registered PIT skill screen, and log the executable book at detection + 2 s / 30 s / 2 min against
   matched random-print benchmarks. The 2024–25 evidence predicts rejection. Treat it as a test of whether 2026
   differs, and use wallet alerts mainly as a toxicity filter for D3.

**Stage 3: decision gates.** Consider a tiny live test only if a candidate passes its kill criteria
out-of-sample. That also requires confirming your eligibility to trade on the venue, and your explicit
approval. Nothing in this project places orders.

---

## F. Read-only bet-alert system (built and tested; not deployed)

Code and full design: `alerts/README.md`. 108 offline tests pass. A live read-only smoke test was run on
2026-10-18; its results are below.

**Architecture.**
`/v2/activity` poller (cursor walk, schema checks, CDN cache-bust) → SQLite (WAL) → grouping into bets → rules
→ enrichment (fresh CLOB book, fee, exposure, market state) → dispatcher thread → console / file / Telegram /
email. Credentials come from environment variables only and are redacted from logs. No keys, no wallet, no
orders.

**Minimal schema.**

| Table | Holds |
|---|---|
| `wallets` | address, label, cluster_id, cluster_confidence ∈ {confirmed, probable, weak, none}, note |
| `fills` | sha256(wallet, tx, asset, side, size, price, ts, type, occurrence) primary key, raw JSON, role, fee, first_seen_at |
| `bets` | grouped fills: same wallet, condition, outcome, side, ≤ 10-min gaps; new position / addition |
| `alerts` | UNIQUE dedupe_key, rendered text, payload |
| `deliveries` | per-channel state machine |
| `poll_state` | watermark advanced only after a complete walk |
| `health_events` | DATA PROBLEM episodes |

**Pseudocode.**
```
every 30 s ± jitter:
  check /v2/status lag → DATA PROBLEM if stale
  for each wallet:
    walk /v2/activity from (watermark − 600 s), ASC, all pages
    INSERT OR IGNORE fills
    on any failure: keep watermark, record health event (alert after 2 failures)
    on success:     watermark = server Date − max(30 s, lag)
  group new fills into bets
  for qualifying BUY bets:
    fetch fresh book / fee / exposure / market state
    label NEW BET DETECTED (always "no copy signal validated") or COPY-CANDIDATE (rules off by default)
    insert alert (unique per bet) and deliveries
  dispatcher: pending → sending → sent | retry | failed (at-least-once, marked [POSSIBLE DUPLICATE])
```

**Each alert carries:**
- wallet and cluster confidence; market, event and outcome (cross-checked against Gamma token ids);
- execution and detection timestamps with the lag;
- amount spent, shares and average price; maker/taker split;
- fresh bid/ask, spread and depth within 1¢ and 5¢; price deterioration since the fill;
- the follower's taker fee at the ask; the wallet's exposure to the market and the event;
- in-play status, accepting orders and `secondsDelay`; the link; the reason it qualified.

**Measured (2026-10-18, 3 active wallets, 16 min, console and file notifiers only):**
- detection lag after the block: p50 16 s, p90 29 s;
- 0 duplicate deliveries;
- a 5-minute simulated outage recovered with **no fills skipped** (checked against an independent full pull);
- rebuilding the three candidate wallets' histories reproduced the research notes exactly.

**What needs a continuously running service.**
- Any alert faster than the schedule: the loop process plus a persistent SQLite file, on a home machine or
  Raspberry Pi with systemd, or a small VPS (paid; not set up).
- A 5-minute cron gives ~2.5 min median latency; an hourly cron ~30 min, too slow for pre-match or in-play
  signals.
- The faster path is the public RTDS websocket (~2 s), which the README describes as an upgrade but which is not
  built.

**Status: nothing is deployed and no monitoring is active.** Telegram and email were tested only against
fakes.

---

## G. How the tests were run (data and backtest realism)

- **Point-in-time discipline.**
  - Rejection criteria were written to notes before results were computed and kept unchanged afterwards. The
    auditors verified this in git for the FLB, mean-reversion and LP-markout studies; for the PIT wallet study it
    is PLAUSIBLE (self-reported timestamps consistent with file times).
  - Selection used only data timestamped before the decision; resolutions counted only once resolved.
  - Splits were time-ordered: train < 2025-07, validation 2025-07..12, **TEST 2026-01-01..2026-10-15** for the
    market studies. PIT wallets: TEST = selection dates 2025-07..12, plus a 2026 Data-API holdout.
- **Dependence.** Bootstrap clustered by event (sports games across several Gamma events share one key) and by
  week or entry day; Holm and reality-check adjustments across the 28 hypotheses and the 8,526 testable exploratory variants.
- **Executable prices.**
  - Live studies walked depth on real books with each leg's own `feeSchedule`.
  - Historical studies used next taker prints plus a measured spread model, and were audited against actual
    first-buy prints. Midpoints were used only where labelled.
- **Fees.** Prospective results use the current fee schedule: each market's `feeSchedule` in the live scans and the
  2026 wallet holdout, and the current category table in the FLB and 2024–25 wallet studies. As-traded fees were
  checked on-chain.
  Results on 2024–25 data are optimistic because they were effectively fee-free.
- **Capital.** Returns are on committed capital to resolution, with lock-up and T-bill comparison. Short windows
  were not mechanically annualised; where an annual rate is quoted it is simple, over the stated lock-up.
- **Accounting.** Deposits, withdrawals and rebates are separated from trading P&L. Redemptions are not double
  counted. Wallet P&L was reconciled to on-chain flows within a few dollars.
- **Provenance.** Every raw API response is stored with URL, params, UTC fetch time and status under
  `data/raw/` (gitignored, ~15 GB); derived data is in `data/derived/`.

---

## H. What is missing, and how it changes the conclusions

| Missing | Effect |
|---|---|
| Historical order books (none official; free archive gap 12–17 June 2026) | Follower and maker fills are proxies. Wallet and LP conclusions are exploratory where noted; the PIT rejection holds under every estimator tried. |
| On-chain fill history after 2026-01-05 in a queryable form | The 2026 wallet holdout uses a sampled candidate pool (biased; quantified in its note). Free HF datasets (`SII-WANGZJ/Polymarket_data` to 2026-10-04) could extend it; they are not validated here. |
| Kalshi data (terms risk) and real-time bookmaker odds (paid) | Cross-venue and sports lead–lag are inconclusive, not rejected. |
| Recurrence of k-of-n sets | Unknown whether D1 is a flow or a one-off; this is the first experiment. |
| Your jurisdiction and eligibility | Every strategy is gated on it; cross-venue strategies are infeasible for most people. |

---

## First experiment (one concrete recommendation)

**Run a read-only, pre-registered forward scan of k-of-n count-set baskets (D1): weekly for 8 weeks to the first
decision, then on to the 2027-01-21 resolution. Put the favourite paper log (D2) on the same daily job for at least
3 months.**

- **What it measures.**
  - D1: each week, every TRUE set's executable net edge, depth and annualised return on lock-up, and whether new
    sets appear (recurrence).
  - D2: daily paper fills at real asks, and the realised loss ratio.
- **Kill rules (fixed now).**
  - D1 (my proposed threshold): reject if new TRUE-set profit is < $500/month at ≥ 10%/yr, or if any set fails a
    rules re-read.
  - D2: reject when realised losses exceed 0.75× price-implied losses after the implied sum reaches 5.
- **Why first.** It is the cheapest test of the only true-dominance candidate. It needs no funded wallet and no
  paid data, and it rejects quickly if the opportunity was a one-off stock.

The wallet-following idea is not the first experiment. The point-in-time evidence rejects it, and following
mintblade specifically is not possible because it has stopped trading.
