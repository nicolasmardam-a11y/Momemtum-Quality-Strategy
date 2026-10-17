# WALLETS: mintblade, GRIMDRIP, endlessFate, consolidated after adversarial review (as of 2026-10-17)

This note consolidates and supersedes, where they conflict: `mintblade.md`, `grimdrip_endlessfate.md`, `linkage.md` and `copyability.md`. Corrections in those files are marked **[corrected by reviewer]**.

Reviewer scripts: `analyses/wallets/review_01_pnl.py` … `review_05_mirrored_orders.py`. Outputs: `data/derived/review_*.parquet`.

Labels:
- **VERIFIED**: checked in primary data by the reviewer or by a reproduced computation.
- **PLAUSIBLE**: consistent with the evidence but not proven.
- **UNSUPPORTED**: no evidence, or contradicted.

Nothing here infers anyone's real-world identity, and performance is not treated as evidence of private information.

## 0. Bottom line

1. **Only mintblade passes a screen, and only on the weakest counting rule** (VERIFIED).
   - It is 5 of 5 *markets*, but those markets cover only 3 distinct events: a $4.81 MLB test ticket, one Saudi Arabia–Uruguay bet split over three nested markets, and one Iran–New Zealand bet.
   - Per event it fails both screens, and with any minimum stake of $100 or more it also fails.
   - GRIMDRIP (2 markets, 1 event) and endlessFate (9 markets, 7 events, 3 losses) fail every rule.
2. **Under credible linked-wallet scenarios everything fails** (VERIFIED arithmetic; linkage PLAUSIBLE to strong).
   - The funds evidence links all three wallets, so the evidence-consistent grouping is all three together: 13 markets (10 won), 10 events (7 made money). That fails both screens.
   - The only grouping that passes, mintblade + GRIMDRIP without endlessFate, is not supported by the evidence (§3).
3. **P&L is real and reconciles** (VERIFIED, re-derived from raw /v2 data). Realised P&L:
   - mintblade **+$9,109,605**
   - GRIMDRIP **+$7,507,246**
   - endlessFate **+$7,249,106**

   Fees match `/v2/user-stats` to the cent. Unrealised P&L is $0 everywhere. Deposits and withdrawals are not profit.
4. **The records are statistically ordinary given the market's own prices** (VERIFIED computation; the null model is an assumption). Under a zero-edge null, P(P&L ≥ observed) is:
   - mintblade 0.113
   - GRIMDRIP 0.288
   - endlessFate 0.168
   - all three 0.028, which is heavily selection-biased

   The profits come from three large, roughly even-money bets that won (two of them draws) and one 0.24 draw bet.
5. **No signal is demonstrably copyable** (VERIFIED for the point-in-time result).
   - Applied point-in-time, the user's screens would have selected **none** of these wallets before any of their 21 entry signals. A screen-following trader would have copied zero trades.
   - Copying with hindsight would have matched the wallets' returns. Most of that is one drawn match. The only non-luck component, about +1.5c of closing-line value for fast copies, comes from front-running the wallets' own price impact.
   - All three wallets have been dormant since June 2026 (last trades 06-16, 06-18 and 06-18; VERIFIED live).
6. **Linkage.** There is no shared key and no direct transfer between the wallets (VERIFIED).
   - The withdrawal proceeds of all three end in the same two Etherscan-tagged *Binance Deposit* addresses (VERIFIED on-chain and against the tags). That is strong probabilistic evidence of a common financial destination.
   - New, VERIFIED: endlessFate and two other cluster accounts (LEEEROYJENKINS, FlickRaw) signed **identical orders within 0.4–2.1 s**. That is direct evidence of common control of those accounts' orders.
   - mintblade and GRIMDRIP have no trading-level link to anyone.

## 1. What is verified about each address and profile (VERIFIED live 2026-10-17: Gamma `/public-profile`, `/v2/user-stats`, Data API row `name`, on-chain)

| | mintblade | GRIMDRIP | endlessFate |
|---|---|---|---|
| proxy wallet | 0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb | 0x3f87d51f27ba6e19ec52aaeebb68559a839c742c | 0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2 |
| profile name / pseudonym | mintblade / Golden-Reclamation | GRIMDRIP / Dismal-Volunteering-Graph | endlessFate / Mushy-Conspirator |
| `name` on every Data API activity row | 830 / 830 | 773 / 773 | 533 / 533 |
| createdAt (= user-stats join_date) | 2026-06-02 14:47:45Z | 2026-06-02 15:01:42Z | 2026-04-27 19:18:08Z |
| Gamma user id / taker tier / verified badge | 8422116 / 6 Obsidian / no | 8422276 / 4 Platinum / no | 7713278 / 6 Obsidian / no |
| wallet type | Polymarket V2 Deposit Wallet (ERC-1967 proxy); own owner EOA 0x8518…8542 | same type; owner 0xbd6e…7d83 | same type; owner 0xc108…abe1 (V2 wallet deployed 05-31) |
| all order signatures recover to own owner (linkage_11) | 721 / 721 | 667 / 667 | 474 / 474 |
| trades: first – last | 06-03 21:18:42 – **06-16 01:04:03** | 06-18 15:23:20 – 16:00:16 | 06-12 01:53:30 – 06-18 01:52:55 |
| last activity of any kind | 07-17 (rebate withdrawal) | 06-20 (withdrawal) | 07-17 (rebate withdrawal) |
| open positions / `/v2/value` today | 0 / $0 | 0 / $0 | 3 resolved losers held at 0 / $0 |

- Tier and `weightedVolume` look like stale snapshots of the last trading day. Their semantics are UNVERIFIED.
- endlessFate's profile predates its V2 wallet. The only legacy-proxy-looking contract that paid it, `0xfb1c…8b44` ($9,955 on 05-31, a 45-byte clone), has **no trades and no profile** in the Data API (VERIFIED). No earlier trading history was found.
- **CONTEXT.md correction:** mintblade's 727 trade rows end on **2026-06-16**, not 2026-07-08. The 07-09 date is the user-stats P&L snapshot.

## 2. P&L, fees and redemptions: independent re-derivation (VERIFIED; `review_01_pnl.py`, `review_pnl_wallets.parquet`, `review_pnl_markets.parquet`)

The re-derivation used raw `/v2/activity` (with `exclude_deposits_withdrawals=false`), `/v2/trades` (`taker_only` false and true), `/v2/positions`, `/v2/user-stats` and Gamma resolutions. No earlier derived file was used.

| | mintblade | GRIMDRIP | endlessFate |
|---|---|---|---|
| fills (taker / maker); all BUY, no sells, merges, splits or conversions | 727 (166 / 561) | 670 (93 / 577) | 474 (138 / 336) |
| distinct markets (= user-stats `trades`) | 5 | 2 | 9 |
| buy cost incl. fees | $8,650,317 | $6,096,723 | $13,843,427 |
| taker fees = Σ shares × 0.03 × p(1−p) (max row error 1.6e-5) | $127,397.56 | $94,911.90 | $160,131.17 |
| user-stats `fees_paid` | −$127,397.56 | −$94,911.90 | −$160,131.17 |
| redemptions | $17,759,922 | $13,603,969 | $21,092,533 |
| resolved losers, unredeemed (payout 0) | none | none | 3 markets, cost $2,076,629 |
| **realised market P&L** (payout value − cost) | **+$9,109,604.79** | **+$7,507,246.13** | **+$7,249,106.08** |
| user-stats `realized_market_pnl` | $9,110,689.71 (+$1,085) | $7,512,274.94 (+$5,029) | $7,249,616.01 (+$510) |
| naive sum over `positions?status=CLOSED` | $9,110,690 | $7,512,275 | **$9,326,180** (losers absent) |
| rebates and rewards (income, not trading P&L) | $28,790.49 (taker 27,877.90 + maker 912.59) | $538.70 | $65,515.07 |
| unrealised P&L | 0 | 0 | 0 (every market resolved) |
| peak capital (fill-by-fill, to closedTime) | $7,982,923 | $6,096,723 | $7,516,421 |

- **Cash-flow reconciliation** (withdrawals − deposits = P&L + income):
  - mintblade: residual $1.67.
  - GRIMDRIP: residual $1.46, and $1.00 pUSD is still in the wallet.
  - endlessFate: the API rows leave $1,599,997 unexplained. That is exactly the two non-refunded on-chain withdrawals that `/v2/activity` omits (VERIFIED on-chain in `grimdrip_endlessfate.md` §7; the reviewer did not re-scan the chain).
  - Redemptions equal the shares bought for every winner (no double counting).
- **API vs cash basis.** The API's realised P&L is higher by $1,085, $5,029 and $510. For GRIMDRIP, $5,000.32 of that is on the Czechia market.
  - The API position `avg_price` is below the fee-inclusive VWAP, while its fees match exactly.
  - Two explanations were tested and rejected: 2-decimal price rounding and duplicate fill rows.
  - The cause is UNVERIFIED. The cash figure is the one that reconciles with deposits, withdrawals and on-chain balances.
- **Fee rate.** The fee rate is **0.03** (`sports_fees_v2`) in all 13 markets, not the 0.05 sports default in CONTEXT.md.

## 3. Decisions, distinct events and the screens

**Event key.** The event key is the Gamma event slug with "-more-markets" stripped, because spreads live in the "More Markets" event of the same match. Nested legs on one match are one decision. This grouping was re-derived and confirmed, and it matches the reconstructions.

| wallet | event (final) | legs → side | cost | realised | made money |
|---|---|---|---|---|---|
| mintblade | NYM–SEA MLB 06-03 (7-1) | Mets ML, 5 sh @0.96 (min size, in play) | $4.81 | +$0.19 | yes |
| mintblade | KSA–URU 06-15 (1-1) | Uruguay-win No + Draw Yes + Spread Saudi +1.5 (nested) | $1,514,751 | +$1,878,816 | yes |
| mintblade | IRN–NZL 06-15 (2-2) | Iran-win No | $7,135,562 | +$7,230,789 | yes |
| GRIMDRIP | CZE–RSA 06-18 (1-1) | Czechia-win No + Draw Yes (nested) | $6,096,723 | +$7,507,246 | yes |
| endlessFate | KOR–CZE 06-11 (2-1) | Korea-win No | $859,535 | −$859,535 | no |
| endlessFate | CAN–BIH 06-12 (1-1) | Bosnia-win No (half-time) | $476,040 | +$346,401 | yes |
| endlessFate | USA–PAR 06-12 (4-1) | Draw Yes | $1,204,466 | −$1,204,466 | no |
| endlessFate | AUS–TUR 06-14 (2-0) | Spread Australia +1.5 | $363,242 | +$151,046 | yes |
| endlessFate | BEL–EGY 06-15 (1-1) | Belgium-win Yes | $12,627 | −$12,627 | no |
| endlessFate | KSA–URU 06-15 (1-1) | the same 3 legs and sides as mintblade | $3,411,095 | +$6,172,800 | yes |
| endlessFate | UZB–COL 06-17 (1-3) | Colombia-win Yes | $7,516,421 | +$2,655,487 | yes |

"Outcome won" and "made money" coincide at market level here because there were no exits. They differ at event level: KSA–URU legs make money on a Saudi win or a draw, but all three legs win only on a draw.

**Screens** (trailing 12 months; every decision falls in June 2026; `review_02_screens_null_capital.py`, `review_screens.parquet`). Each cell gives (i) "exactly 5, all successful" / (ii) "≥5, no losses".

| scope | per market (won) | per market (made money) | per event (all legs won) | per event (made money) | market, stake ≥ $100 | event, stake ≥ $100 |
|---|---|---|---|---|---|---|
| mintblade | **PASS / PASS** (5/5) | **PASS / PASS** (5/5) | fail / fail (3/3) | fail / fail (3/3) | fail / fail (4/4) | fail / fail (2/2) |
| GRIMDRIP | fail / fail (2/2) | fail / fail | fail / fail (1/1) | fail / fail | fail / fail | fail / fail |
| endlessFate | fail / fail (6/9) | fail / fail (6/9) | fail / fail (4/7) | fail / fail (4/7) | fail / fail | fail / fail |
| mintblade + GRIMDRIP | fail / **PASS** (7/7) | fail / **PASS** | fail / fail (4/4) | fail / fail | fail / **PASS** (6/6) | fail / fail (3/3) |
| mintblade + endlessFate | fail / fail (8/11) | fail / fail | fail / fail (6/9) | fail / fail | fail / fail | fail / fail |
| GRIMDRIP + endlessFate | fail / fail (8/11) | fail / fail | fail / fail (5/8) | fail / fail | fail / fail | fail / fail |
| **all three (credible cluster)** | fail / fail (10/13) | fail / fail | fail / fail (7/10) | fail / fail | fail / fail (9/12) | fail / fail (6/9) |

**Notes on the screens:**
- **Trap.** `/v2/positions?status=CLOSED` lists only redeemed positions, so it shows endlessFate as 6 for 6 with no losses. Its 3 resolved losers were never redeemed (VERIFIED).
- **The (b) "pass" is not credible.** endlessFate is tied to mintblade by both Binance deposit addresses and by the shared match. That is at least as strong as GRIMDRIP's tie (one address). Any evidence-consistent grouping that contains mintblade and GRIMDRIP also contains endlessFate, and that grouping fails.
- **The extended book also fails.** It has 11 accounts with membership PLAUSIBLE, and endlessFate, LEEEROYJENKINS and FlickRaw are VERIFIED as order-coordinated. It fails by construction: FlickRaw (Netherlands Yes, Belgium Yes) and LEEEROYJENKINS (Belgium Yes) hold resolved losing markets. Its net is +$14.89M, with four accounts down a combined −$15.0M (`linkage.md` §4). A decision-level record for the whole book was not built.

## 4. Linkage (reviewed classification)

| link | class | exact evidence | what it does not show |
|---|---|---|---|
| shared owner or signer key (incl. delegated session signers) | **NONE** (VERIFIED) | 3 distinct owner EOAs. Every batch (49/58/40) and all 1,862 order signatures recover to the wallet's own owner. | Distinct keys do not imply distinct people. |
| direct transfers among the wallets or owners | **NONE** (VERIFIED) | 0 ERC-20 or ERC-1155 transfers on Polygon from 2026-04-20 | |
| shared bridge, relayer or hot-wallet funders | **WEAK / none** | All three are funded from Binance hot wallets and bridged by Relay (solver `0xf70d…`, depository `0x4cd0…`); 30 Polymarket relayers are shared. | Shared infrastructure. No link rests on it. |
| common destination A `0xb08b…317d` (all three) and B `0x3319…b072` (mintblade, endlessFate) | **STRONG PROBABILISTIC** for a common financial counterparty (facts VERIFIED; account semantics PLAUSIBLE) | Re-fetched 2026-10-17: Etherscan tag "Binance Deposit", funded by Binance: Deposit Funder 1, swept to Binance hot wallets. mintblade paid A directly ($8.0M). GRIMDRIP ($17.53M) and endlessFate ($6.35M) paid A through hops that hold only their own Relay deliveries. B was fresh on 06-18; endlessFate paid it at 14:11 and mintblade's hop at 15:37. | A received from 12 Polymarket wallets plus 9 one-use USDT EOAs, so it could be an intermediary's account (OTC desk, manager). Common beneficial ownership is PLAUSIBLE, not proven. |
| **identical orders across accounts** [reviewer, new] | **STRONG** for common control of orders (VERIFIED) | Belgium-win Yes: 6,313 sh @0.66 signed by endlessFate 18:50:06.183, LEEEROYJENKINS 06.577 and FlickRaw 07.738. Then 12,626 sh @0.66 signed 18:50:39.695, 40.502 and 41.742. Sizes are 1/3 and 2/3 of $12,500 (not round). All were signed before the first fill of each batch was mined (blocks 88,562,949–972). A search of all fills of the 5 accounts finds no other mirrors (`review_mirrored_orders.parquet`). | Only one match and two tickets. It involves neither mintblade nor GRIMDRIP. "One tool or signal group driving several owners' accounts" remains possible, but that is still a common controller of these orders. |
| KSA–URU same 3 legs (endlessFate → LEEEROYJENKINS → mintblade, 22–318 s hand-offs) | WEAK–MODERATE (VERIFIED facts) | 3 of 12 large 3-leg traders took this profile. mintblade came 6.3–47 min after endlessFate at worse prices. 0 shared transactions. Same-size matches are round-dollar ($10k) coincidences. | Public copying or a shared signal remain possible. |
| profile creation (mintblade–GRIMDRIP 13.9 min, GRIMDRIP–FlickRaw 8.6 min, endlessFate–LEEEROYJENKINS 9.9 min) | WEAK alone | 3 of 5,886 large-trader pairs were created within 14 min, and all 3 are in this cluster (selected baseline) | About 160 accounts are created platform-wide every 14 min. |
| mintblade and FlickRaw identical $4.80 Mets ticket | MODERATE | FlickRaw's order was signed 21:19:49, 67 s after mintblade's fill (VERIFIED) | It could be a public copy. Minimum-size tests are common. |

Correction to `linkage.md` §8: cluster peak capital is **$10.53M**, not $12.07M, and mintblade's peak is **$7.98M**, not $8.65M. The script counted each market's final cost from its first fill.

## 5. Timing against public information (VERIFIED from tapes, order structs and match reports; no identity or insider inference)

**Order times.** The signed V2 Order struct carries the order's creation `timestamp` (`review_03_order_times.py`). Taker orders were signed a median 2.5 s before their fill block (IQR 2.1–2.9 s), so fill times are good proxies for decision times.

| wallet / event | first order → last order signed (UTC) | kick-off: scheduled (inferred actual) | classification |
|---|---|---|---|
| mintblade NYM–SEA | fill 21:18:42 | first pitch 19:40 | **in play, after public news**: a 4-run 4th, price already 0.93–0.96, bought at 0.96 |
| mintblade KSA–URU | 21:54:42.8 → 21:59:59.2 | 22:00 (≈22:03:36, PLAUSIBLE) | pre-event, 9–4 min before the inferred kick-off |
| mintblade IRN–NZL | 00:17:19.0 → **01:04:00.2** | 01:00 (≈01:04, PLAUSIBLE) | pre-event for 93.5% of cost. Resting bids were signed at 01:01:13 and 01:01:52 and a taker order at 01:04:00, i.e. after the scheduled kick-off. That is at most the first seconds of play, before any goal (first goal 01:10:33). |
| GRIMDRIP CZE–RSA | 15:23:18.0 → **16:00:12.5** | 16:00 | pre-event. The resting 2M-share bid (signed 15:55:47) stopped at 16:00:01, then one taker order was signed 12.5 s after kick-off (≈$10k, in play, before the 6' goal). |
| endlessFate (7 matches) | first orders 3–69 min before kick-off; CAN–BIH at half-time | scheduled | 10 of 11 episodes pre-event. CAN–BIH was bought in play, about 36 min after Bosnia's public 21' goal, and the price then moved against it for about 30 min. |

- No fill followed a goal or card in any football entry. Every large later price move coincides with a publicly reported goal (VERIFIED, tape vs reports).
- Line-up release times were **not** verified for any match. The pre-event entries are consistent with trading after public line-ups (PLAUSIBLE), but no specific news item is tied to them.
- The wallets were the price-setters in their windows: 70–100% of taker flow, moving prices 0–4c. Performance is not evidence of private information, and none is claimed.

## 6. Luck versus skill (VERIFIED computation; null = entry VWAP is the true probability, matches independent, nested legs mapped to goal-margin states; `review_null.parquet`)

| scope | events | P(P&L ≥ observed) | P(P&L > 0) | null mean (= −fees) | null SD | P(all events made money) |
|---|---|---|---|---|---|---|
| mintblade | 3 | 0.113 | 0.489 | −$127k | $7.33M | 0.172 |
| mintblade ex Mets | 2 | 0.118 | 0.489 | −$127k | $7.33M | 0.179 |
| GRIMDRIP | 1 | 0.288 | 0.498 | −$95k | $6.16M | 0.498 |
| endlessFate | 7 | 0.168 | 0.458 | −$160k | $6.27M | 0.013 |
| mintblade + GRIMDRIP | 4 | 0.032 | 0.452 | −$222k | $9.57M | 0.085 |
| all three | 10 | 0.028 | 0.471 | −$382k | $11.92M | 0.003 |

- **Naive products overstate the evidence.** mintblade's naive product of 5 VWAPs is 0.026, against 0.113 when the legs are handled jointly.
- **Selection.** These wallets were found because they won. The same funds evidence ties them to accounts that lost $15.0M.
- **Base rate.** By CryptoHouse sampling, roughly 19,000 wallets a year go 5-for-5 by outcome (PLAUSIBLE order of magnitude).
- **Two real decisions** (mintblade) cannot estimate an edge: the 95% lower bound on the win rate is about 0.16.

## 7. Is any signal demonstrably copyable? No.

Exact evidence:
1. **Point-in-time selection: zero copyable trades** (VERIFIED, `review_pit_screen.parquet`). At each wallet's entries, using only markets resolved earlier, every screen and every counting rule fails:
   - GRIMDRIP: 0 prior decisions.
   - endlessFate: 0–8 prior markets, with up to 3 losses; −$1.57M realised before KSA–URU.
   - mintblade: only the Mets ticket.

   mintblade first passes (per market) at 06-16 03:22, after its last trade, and it never traded again.
2. **Ex post, with hindsight about which wallets to follow** (VERIFIED computation on print proxies; `copyability.md`):
   - A 5 s follower at $2,500 per market-episode earns **+$932 per $1,000** pooled, against the wallets' own +$906.
   - **Weighting each event equally gives +$332 per $1,000** (median +$397; 7 of 10 events positive). The equal-per-episode figure is inflated because one drawn match gets 9 of 21 signals and 43% of capital.
   - Excluding KSA–URU: +$217 per $1,000. endlessFate alone: −$264 per $1,000.
3. **The only non-luck component is closing-line value of about +1.3 to +1.5c** for copies within 2 min of the first fill. That is about +$13–17 per $1,000 after fees, and it comes from front-running the wallets' own subsequent buying. Copying every fill gives an EV of −$12 per $1,000; copying hourly gives −$22.
4. **Hourly monitoring is too slow.** Entries come 3–69 min before kick-offs on the hour. 7 of 19 pre-match signals would first be seen at the scheduled kick-off, and 10 of the 12 caught earlier depend on kick-offs that ran about 4 min late (PLAUSIBLE).
5. **Faster than any follower.** The cluster's own accounts signed identical orders within 0.4–2.1 s, before any of them was public (§4).
6. **Capacity and dormancy.** The wallets took 70–100% of taker flow. Other traders printed as little as $0.8k–$19k in some windows. There have been no trades since 2026-06-18.

**Checks on the copy test that held up:**
- It used the correct (ask) side of the tape.
- It is not driven by the wallet's own prints (ex_wallet changes results by ≤ $3 per $1,000).
- No copy was placed in a closed market.
- Fees are correct.

**Weaknesses:**
- There is no historical order book, so fills are print-based. The $2,500 fill spans a median of 51 s of later prints, and 6 hourly KSA–URU copies span the inferred kick-off.
- In-play pauses cannot be observed.
- The pooled sample treats one probable cluster as three sources.

## 8. What remains uncertain

- **Actual kick-off times** for KSA–URU (~22:03:36) and IRN–NZL (~01:04) are inferred from goal-driven tape jumps (PLAUSIBLE, ±1 min). This decides whether mintblade's last Iran order (signed 01:04:00) was seconds before or after the start.
- **Line-up publication times** were not verified for any match.
- **Account semantics.** Whether one Binance deposit address equals one beneficial owner (rather than an intermediary account) cannot be checked on-chain. Beneficial ownership is PLAUSIBLE only.
- **Extended book.** Its membership rests on the deposit-address evidence class (PLAUSIBLE), except endlessFate, LEEEROYJENKINS and FlickRaw, whose order coordination on Belgium is VERIFIED. LEEEROYJENKINS's funds link runs through an untagged, Kraken-swept address.
- **Coverage.** BNB Chain coverage is partial. Only the Relay route was followed off Polygon. GRIMDRIP's hop also sent $150 (07-02) to another Binance deposit address, `0x9Dea58…2f5E74`, which was not traced.
- **API gap.** The cause of the $510–$5,029 gap between the API's and the cash-basis realised P&L is unknown.
- **Base rate and null.** The 5-for-5 base rate uses pre-V2 CryptoHouse data (2025). The null treats entry prices as true probabilities and ignores selection.

## 9. Reviewer corrections (also marked in the source notes)

1. `linkage.md` §0 and §8:
   - Peak capital was overstated. mintblade is $7.98M (not $8.65M), scenario (b) $7.98M, and all three **$10.53M** (not $12.07M).
   - P&L / peak is 1.14 / 2.08 / 2.27.
   - The sum of the wallet peaks is $21.60M (not $22.3M).
2. `linkage.md` §8: scenario (b), the only linked "pass", is not an evidence-consistent grouping.
3. `linkage.md` §6–7, `grimdrip_endlessfate.md` §6, `mintblade.md` §9: new VERIFIED evidence of mirrored identical orders by endlessFate, LEEEROYJENKINS and FlickRaw.
4. `copyability.md` §0:
   - Wallet-selection look-ahead: there were zero point-in-time copyable signals.
   - The event-weighted ex-post return is +$332 per $1,000, not +$932.
   - Fill-proxy span caveat.
5. `grimdrip_endlessfate.md`:
   - The bottom-line closing-line value "0 to +5c" is −1 to +2.5c (or −0.5 to +4.5c on `/prices-history`).
   - GRIMDRIP's final order was signed 12.5 s after kick-off.
   - A point-in-time note was added to §10.
6. `mintblade.md`:
   - The Iran "No bid at 0.50" was five successive 500k-share bids, two of them signed after the scheduled kick-off.
   - P(P&L ≥ observed) is 0.111 (CLOB) or 0.113 (VWAP) once the Mets leg is required.
   - The null mean with VWAP probabilities is −$127k.
7. CONTEXT.md:
   - mintblade's trades end 06-16 (not 07-08).
   - The fee rate in these markets is 0.03.
   - The Mets position realised +$0.19.
   - publicnode does not serve historical receipts or logs.
   - Deposits and withdrawals appear only with `exclude_deposits_withdrawals=false`, and `/v2/activity` misses some on-chain withdrawals.

**Confirmed without change:**
- Every per-market fill count, cost, fee, redemption and realised P&L.
- The maker/taker inference (the taker rows are an exact subset; the fee formula is exact).
- Distinct-event grouping, all individual screen outcomes, and all null probabilities.
- The A/B tags, and the hops carrying only their own wallet's money.
- 0 shared transactions and 0 direct transfers.
- Copy-test side, sensitivities and dormancy.

## 10. Files

**Scripts** (`analyses/wallets/`):
- `review_01_pnl.py`: raw /v2 re-derivation
- `review_02_screens_null_capital.py`: screens, scenarios, exact null, fill-level capital
- `review_03_order_times.py`: V2 order timestamps from cached calldata
- `review_04_pit_screen.py`: point-in-time screen status
- `review_05_mirrored_orders.py`: cross-account identical orders

**Data** (`data/derived/`):
- `review_pnl_wallets.parquet`, `review_pnl_markets.parquet`
- `review_fills.parquet`, `review_pos_closed_*.parquet`
- `review_screens.parquet`, `review_null.parquet`, `review_capital.parquet`
- `review_order_times.parquet`, `review_pit_screen.parquet`, `review_mirrored_orders.parquet`

**Source notes:** `mintblade.md`, `grimdrip_endlessfate.md`, `linkage.md`, `copyability.md`.
