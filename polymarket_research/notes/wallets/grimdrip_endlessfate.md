# GRIMDRIP and endlessFate: wallet reconstruction (as of 2026-10-17)

> Reviewed adversarially on 2026-10-17 (`analyses/wallets/review_0[1-5]_*.py`). Fills, fees, redemptions, realised P&L, screens, event grouping and null probabilities were re-derived independently from raw /v2 data and match to the cent. Corrections are marked [corrected by reviewer]. Consolidated view: `WALLETS.md`.

Wallets: **GRIMDRIP** `0x3f87d51f27ba6e19ec52aaeebb68559a839c742c`, **endlessFate** `0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2`.
Comparison wallet: **mintblade** `0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb`. Co-trader found in the tapes: **LEEEROYJENKINS**
`0x99aea8f9a64d0142b6b66a4b9d02a2211d45386f`.

Labels: **VERIFIED** = I inspected the primary data myself; **PLAUSIBLE** = consistent with the evidence but not directly verified;
**UNSUPPORTED** = no evidence or contradicted. Nothing here identifies any person, and nothing here shows insider information.

## Bottom line for a copy-trader

1. **Both wallets are one-tournament, one-sport, single-style accounts.** GRIMDRIP made **one decision**: one football match (Czechia v South Africa, 2026-06-18) placed across two nested markets. endlessFate made **7 match-level decisions across 9 markets** over 6 days. Both have **no fills before or after 12-18 June 2026**. (VERIFIED)
2. **Neither passes the user's screens.** GRIMDRIP has too few decisions (2 markets, 1 event). endlessFate has **3 resolved losses** (Korea win No, USA–Paraguay draw, Belgium win), totalling -$2.08M. (VERIFIED)
   - Trap: those losers were **never redeemed**, so they are missing from `/v2/positions?status=CLOSED`. A "closed positions" view therefore shows endlessFate as **6 for 6**.
3. **Profits are large but statistically ordinary given the market's own odds.**
   - Under the null that each bet wins with its entry price (zero edge), P&L at least as large as observed has probability **0.29 (GRIMDRIP)**, **0.17 (endlessFate)** and **0.11 (mintblade)**.
   - endlessFate won 4 of 7 matches; the null expectation is 3.84. (VERIFIED computation; the null model is stated below.)
4. **No leading-information signature in the price data.**
   - All entries but one were pre-match, in the last ~70 minutes before kick-off. The exception is endlessFate's Canada–Bosnia entry at half-time, after a public goal.
   - Prices barely moved after the entries. Closing-line value is about 0 to +5c [corrected by reviewer: the §5 table gives **−1 to +2.5c** (last trade by others before KO); with the `/prices-history` close (copyability.md) the range is −0.5 to +4.5c], and every large later move coincides with a publicly reported goal.
   - The wallets **were** most of the taker flow in their own windows (70-100%), so they set the price rather than front-ran it. (VERIFIED for the price/tape facts; "no leading information" is PLAUSIBLE, since absence of a signature is not proof.)
5. **Copying is not demonstrably profitable ex ante.**
   - Ex post, a follower lagging by 1-15 minutes would have matched the wallets' returns on these specific matches, because prices did not move pre-match.
   - That only replicates the outcomes, which are consistent with luck. Capacity is also tiny: the wallets themselves absorbed most of the available taker liquidity.
   - A style-identical co-trader (LEEEROYJENKINS) **lost $2.75M** on overlapping matches. (VERIFIED numbers; inference PLAUSIBLE)
6. **Data caveat.** `/v2/activity` (even with `exclude_deposits_withdrawals=false`) misses 5 of endlessFate's on-chain withdrawals and 3 relayer refunds.
   - Its cash flows only reconcile on-chain (section 7).
   - The trade, redemption and position data are complete: fees match to the cent, and redemptions match positions. (VERIFIED)

## 1. Profile verification (VERIFIED, Gamma `/public-profile`, Data API row `name`, `/v2/user-stats`)

| field | GRIMDRIP | endlessFate |
|---|---|---|
| proxyWallet (profile) | 0x3f87…742c | 0x5e4c…dba2 |
| name / pseudonym | GRIMDRIP / Dismal-Volunteering-Graph | endlessFate / Mushy-Conspirator |
| `name` on every Data API row (trades, activity, positions) | GRIMDRIP (670/670 trades, 773/773 activity) | endlessFate (474/474, 533/533) |
| createdAt | 2026-06-02T15:01:41.91Z | 2026-04-27T19:18:08.29Z |
| user-stats join_date | 1780412501 (= same instant) | 1777317488 (= same instant) |
| Gamma user id | 8422276 | 7713278 |
| taker tier / weightedVolume | 4 Platinum / 3,163,730.17 | 6 Obsidian / 1,857,402.35 |
| verifiedBadge / views | false / 24,090 | false / 26,737 |
| user-stats `trades` (= distinct markets) | 2 | 9 |

Note on tiers (VERIFIED arithmetic; semantics UNVERIFIED):
- Each profile's `weightedVolume` equals, to the dollar, the taker notional x (1 - price) of the wallet's **last trading day only**: GRIMDRIP's whole history, endlessFate's Colombia trade, mintblade's Iran trade.
- So the tier shown today looks like a stale snapshot, not a live 30-day figure.
- GRIMDRIP received **no taker rebate**: tier 0 at fill time, since this was its first-ever volume.

## 2. Full observable history (VERIFIED)

Scripts:
- `analyses/wallets/ge_pull_wallets.py` pulls everything. Raw responses are under `data/raw/data-api/`, with the fetch time recorded.
- Tidy outputs: `data/derived/ge_*.parquet`.

| item | GRIMDRIP | endlessFate | mintblade |
|---|---|---|---|
| `/v2/activity` default (exclude_deposits_withdrawals defaults to **true**) | 675 rows: 670 TRADE, 2 REDEEM, 2 REWARD, 1 MAKER_REBATE | 487: 474 TRADE, 6 REDEEM, 5 TAKER_REBATE, 1 MAKER_REBATE, 1 REWARD | 735 |
| `/v2/activity` with `exclude_deposits_withdrawals=false` | +60 DEPOSIT ($12,400,960), +38 WITHDRAWAL ($19,908,750) | +24 DEPOSIT ($5,699,999), +22 WITHDRAWAL ($11,414,623) | +58 / +37 |
| `type=TIP` (opt-in), `/v2/activity/combos`, `/v2/positions/combos` | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| SPLIT / MERGE / CONVERSION | 0 | 0 | 0 |
| `/v2/trades` taker_only=false / true | 670 / 93 | 474 / 138 | 727 / 166 |
| positions OPEN / REDEEMABLE / REDEEMABLE_LOST / MERGEABLE / CLOSED | 0/0/0/0/2 | 3/3/3/0/6 (the same 3 losers in OPEN, REDEEMABLE and REDEEMABLE_LOST) | 0/0/0/0/5 |
| `/v2/value` | 0 | 0 | 0 |
| on-chain pUSD balance now (Polygon `balanceOf`) | 1.00 | 0.00 | 0.00 |

- **Maker vs taker.** The taker-only rows are an exact subset of the taker_only=false rows: same tx hash, size and price, one row per tx.
  - So the remaining rows are maker fills. GRIMDRIP has 577 maker fills, but they are only 2.1% of its shares (median $10 each). endlessFate has 336 maker fills, all on Colombia: 2.6% of its shares, median $28.
  - **Check:** fees computed as `size x feeSchedule.rate (0.03) x p x (1-p)` on the inferred taker fills reproduce `/v2/positions.entry_fees_usdc` **to the cent on all 16 markets**. Activity `TRADE.usdc_size` minus `size x price` equals the same fee.
- **Fee rate.** These World Cup and MLB markets carry `feeType=sports_fees_v2` with `feeSchedule.rate=0.03`, `takerOnly=true`, `rebateRate=0.25`. That is lower than the 0.05 category default in CONTEXT.md; the per-market schedule is authoritative.
- **Deposits.** The rows that look like duplicate deposits (same tx, same amount) are distinct on-chain Transfer logs. I decoded every deposit and withdrawal receipt; the sums match the API exactly.

### P&L (cash basis = redemptions - buys - fees; there were no sells, merges or splits)

| | GRIMDRIP | endlessFate |
|---|---|---|
| buy notional | 6,001,811.25 | 13,683,295.81 |
| taker fees paid | 94,911.90 | 160,131.17 |
| redemptions | 13,603,969.28 | 21,092,532.74 |
| resolved losers held, unredeemed (payout 0) | none | 3 markets, cost 2,076,629 incl. fees |
| **realised market P&L** | **+7,507,246** | **+7,249,106** |
| rebates and rewards (wallet income, not trading P&L) | +538.70 | +65,515.07 (taker rebate 64,534.48) |
| unrealised P&L | 0 (nothing open) | 0 (all markets resolved; the 3 losers are worth 0) |
| API `user-stats.realized_market_pnl` | 7,512,274.94 (+$5,029 vs cash basis) | 7,249,616.01 (+$510) |

- API vs cash basis: the API is $5,029 higher for GRIMDRIP, almost all of it on the Czechia market, which is exactly $5,000.32 higher in `/v2/positions`. Cause UNVERIFIED (API cost-basis accounting).
- `/v2/positions` reports endlessFate's three resolved losers as `unrealized_pnl` -2,042,533. They are economically **realised** losses: resolved at 0, simply not redeemed.
- **Deposits are not profit.**
  - GRIMDRIP: withdrawals - deposits = 7,507,790 = realised P&L + income, within $5. The remaining $1.00 pUSD is still in the wallet. (VERIFIED reconciliation)
  - endlessFate: on API rows alone, deposits 5,699,999 + P&L 7,249,106 + income 65,515 - withdrawals 11,414,623 leaves **$1,600,000 unaccounted**, with an on-chain balance of 0 and no TIP or combo rows.
  - **Resolved on-chain (VERIFIED, section 7):** `/v2/activity` **omits 5 bridge withdrawals ($3,999,995)** made on 06-18 between 13:57 and 14:02 UTC. Three of them ($2,399,997) were sent straight back by the bridge relayer within 5 blocks and re-wrapped; the API also omits those refund legs.
  - The API's 06-18 "deposit" of $699,999 is likewise a relayer refund of a $699,999 withdrawal 4 blocks earlier. endlessFate's only external deposit was **$5.0M on 2026-05-31**.
  - On-chain: net bridged out 12,314,622 = 5,000,000 + 7,249,106 + 65,515, to within $1. The P&L is unaffected.

## 3. Market and event mapping (VERIFIED, Gamma `closed=true`, `ge_markets.parquet`, `ge_events.parquet`)

Common to all 13 markets: `umaResolutionStatus=resolved` (statuses list `["proposed"]`), `feeType=sports_fees_v2`, rate 0.03, tags [Sports, Games, Soccer, FIFA World Cup] (MLB for the Mets game).

| market | sportsMarketType | gameStartTime (UTC) | closedTime | result (outcomePrices) | negRisk | secondsDelay |
|---|---|---|---|---|---|---|
| Will Czechia win on 2026-06-18? | moneyline | 06-18 16:00 | 06-18 18:12:05 | No won (CZE 1-1 RSA) | true | 0 |
| Will Czechia vs. South Africa end in a draw? | moneyline | 06-18 16:00 | 06-18 18:17:17 | Yes won | true | 0 |
| Will Korea Republic win on 2026-06-11? | moneyline | 06-12 02:00 | 06-12 06:23:03 | Yes won (KOR 2-1 CZE) | true | 1 |
| Will Bosnia and Herzegovina win on 2026-06-12? | moneyline | 06-12 19:00 | 06-12 23:00:03 | No won (CAN 1-1 BIH) | true | 1 |
| Will United States vs. Paraguay end in a draw? | moneyline | 06-13 01:00 | 06-13 05:05:27 | No won (USA 4-1 PAR) | true | 1 |
| Spread: Türkiye (-1.5) | spreads | 06-14 04:00 | 06-14 06:28:30 | Australia won (AUS 2-0 TUR) | false | 0 |
| Will Belgium win on 2026-06-15? | moneyline | 06-15 19:00 | 06-16 01:53:27 | No won (BEL 1-1 EGY) | true | 0 |
| Spread: Uruguay (-1.5) | spreads | 06-15 22:00 | 06-16 00:35:48 | Saudi Arabia won (KSA 1-1 URY) | false | 0 |
| Will Saudi Arabia vs. Uruguay end in a draw? | moneyline | 06-15 22:00 | 06-16 02:06:57 | Yes won | true | 0 |
| Will Uruguay win on 2026-06-15? | moneyline | 06-15 22:00 | 06-16 02:06:57 | No won | true | 0 |
| Will Colombia win on 2026-06-17? | moneyline | 06-18 02:00 | 06-18 04:29:46 | Yes won (UZB 1-3 COL) | true | 0 |

Kick-off check: FIFA's post-match summary report gives Uzbekistan–Colombia as 20:00 local, Mexico City (= 02:00 UTC), matching Gamma. Socceroos.com.au gives AUS–TUR as 2026-06-14T04:00Z. The tape shows trading regime changes at about the scheduled times. Each match also has a "- More Markets" Gamma event: the spreads live there, and its match key is the base slug.

## 4. Decision tables (VERIFIED; `ge_dec_market.parquet`, `ge_dec_match.parquet`, `ge_dec_episode.parquet`, fills in `ge_fills.parquet`)

### (a) Per market (all BUYs, held to resolution; ROMC = realised P&L / (cost + fees))

| wallet | market -> outcome | fills (taker/maker) | first-last fill UTC | min to KO | shares | VWAP | notional $ | fees $ | won | realised P&L $ | ROMC | edge/sh |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GRIMDRIP | Will Czechia win on 2026-06-18? -> No | 650 (73/577) | 06-18 15:23:20-16:00:16 | -36.7 to +0.3 | 9,925,592 | 0.4979 | 4,941,811 | 72,278 | Y | 4,911,503 | 98% | +0.502 |
| GRIMDRIP | Will Czechia vs. South Africa end in a draw? -> Yes | 20 (20/0) | 06-18 15:26:13-15:57:23 | -33.8 to -2.6 | 3,678,377 | 0.2882 | 1,060,000 | 22,633 | Y | 2,595,743 | 240% | +0.712 |
| endlessFate | Will Korea Republic win on 2026-06-11? -> No | 17 (17/0) | 06-12 01:53:30-01:58:43 | -6.5 to -1.3 | 1,349,364 | 0.6300 | 850,099 | 9,436 | **N** | -859,535 | -100% | -0.630 |
| endlessFate | Will Bosnia and Herzegovina win on 2026-06-12? -> No | 10 (10/0) | 06-12 19:58:12-20:06:25 | **+58.2 to +66.4** | 822,441 | 0.5715 | 469,998 | 6,042 | Y | 346,401 | 73% | +0.429 |
| endlessFate | Will United States vs. Paraguay end in a draw? -> Yes | 50 (50/0) | 06-12 23:51:16-06-13 00:59:58 | -68.7 to -0.03 | 3,821,329 | 0.3088 | 1,179,998 | 24,468 | **N** | -1,204,466 | -100% | -0.309 |
| endlessFate | Spread: Türkiye (-1.5) -> Australia | 10 (10/0) | 06-14 03:56:58-03:59:27 | -3.0 to -0.6 | 514,288 | 0.7000 | 360,002 | 3,240 | Y | 151,046 | 42% | +0.300 |
| endlessFate | Will Belgium win on 2026-06-15? -> Yes | 2 (2/0) | 06-15 18:50:09-18:50:42 | -9.8 to -9.3 | 18,939 | 0.6600 | 12,500 | 127 | **N** | -12,627 | -100% | -0.660 |
| endlessFate | Spread: Uruguay (-1.5) -> Saudi Arabia | 9 (9/0) | 06-15 21:07:58-21:47:40 | -52.0 to -12.3 | 1,430,472 | 0.6082 | 869,999 | 10,218 | Y | 550,255 | 63% | +0.392 |
| endlessFate | Will Saudi Arabia vs. Uruguay end in a draw? -> Yes | 15 (15/0) | 06-15 21:09:07-21:47:19 | -50.9 to -12.7 | 3,526,515 | 0.2354 | 830,000 | 19,035 | Y | 2,677,480 | 315% | +0.765 |
| endlessFate | Will Uruguay win on 2026-06-15? -> No | 9 (9/0) | 06-15 21:19:51-21:48:27 | -40.1 to -11.6 | 4,626,909 | 0.3566 | 1,650,001 | 31,843 | Y | 2,945,065 | 175% | +0.643 |
| endlessFate | Will Colombia win on 2026-06-17? -> Yes | 352 (16/336) | 06-18 00:51:58-01:52:55 | -68.0 to -7.1 | 10,171,908 | 0.7335 | 7,460,699 | 55,722 | Y | 2,655,487 | 35% | +0.267 |

- Entry-implied probability = VWAP. Edge per share = payout - VWAP. Holding periods run 2.5-7.1 h from first fill to resolution.
- Most redemptions happened 10-40 s after the market's `closedTime`, for every wallet. That looks like an automated redeem, so same-second redemptions across wallets are not linking evidence. Exceptions: the GRIMDRIP draw (144 s), endlessFate Bosnia (2.1 h) and the mintblade Mets ticket (12 days).

### (b) Per distinct event (football match): net P&L by home-goal-margin state

| wallet | match (final) | markets | max capital $ | realised P&L $ | ROMC | net P&L by home margin {<=-2,-1,0,+1,>=+2} |
|---|---|---|---|---|---|---|
| GRIMDRIP | Czechia v South Africa (1-1) | 2 | 6,096,723 | +7,507,246 | 123% | +3.83M, +3.83M, **+7.51M**, -6.10M, -6.10M |
| endlessFate | Korea Rep. v Czechia (2-1) | 1 | 859,535 | -859,535 | -100% | +0.49M, +0.49M, +0.49M, **-0.86M**, -0.86M |
| endlessFate | Canada v Bosnia-H. (1-1) | 1 | 476,040 | +346,401 | 73% | -0.48M, -0.48M, **+0.35M**, +0.35M, +0.35M |
| endlessFate | USA v Paraguay (4-1) | 1 | 1,204,466 | -1,204,466 | -100% | -1.20M, -1.20M, +2.62M, -1.20M, **-1.20M** |
| endlessFate | Australia v Türkiye (2-0) | 1 | 363,242 | +151,046 | 42% | -0.36M, +0.15M, +0.15M, +0.15M, **+0.15M** |
| endlessFate | Belgium v Egypt (1-1) | 1 | 12,627 | -12,627 | -100% | -0.01M, -0.01M, **-0.01M**, +0.01M, +0.01M |
| endlessFate | Saudi Arabia v Uruguay (1-1) | 3 | 3,411,095 | +6,172,800 | 181% | -3.41M, -1.98M, **+6.17M**, +2.65M, +2.65M |
| endlessFate | Uzbekistan v Colombia (1-3) | 1 | 7,516,421 | +2,655,487 | 35% | **+2.66M**, +2.66M, -7.52M, -7.52M, -7.52M |

Economically overlapping legs:
- GRIMDRIP's two legs are nested: draw implies "Czechia does not win". The combined position is "Czechia does not win", with about 2/3 of the payoff riding on a draw.
- endlessFate's three KSA-URY legs (Uruguay No, Draw Yes, Saudi +1.5) are all "Uruguay does not win comfortably", again draw-heavy.
- Counted per event, endlessFate made **7 decisions: 4 won, 3 lost**.

### (c) Entry episodes (fills of one wallet on one match with gaps of 10 min or less)

| episode | UTC | min to KO | fills | notional $ | taker % | notional after KO $ | settled P&L $ | classification |
|---|---|---|---|---|---|---|---|---|
| GRIMDRIP CZE-RSA E1 | 06-18 15:23:20-16:00:16 | -36.7 to +0.3 | 670 | 6,001,811 | 98% | 10,095 (0.17%, within 16 s of scheduled KO) | +7,507,246 | pre-event |
| endlessFate KOR-CZE E1 | 06-12 01:53:30-01:58:43 | -6.5 to -1.3 | 17 | 850,099 | 100% | 0 | -859,535 | pre-event |
| endlessFate CAN-BIH E1 | 06-12 19:58:12-20:06:25 | +58.2 to +66.4 | 10 | 469,998 | 100% | 469,998 | +346,401 | **in-play-after-public-news** (half-time, Bosnia 1-0 up since 21') |
| endlessFate USA-PAR E1 | 06-12 23:51:16-06-13 00:06:00 | -68.7 to -54.0 | 6 | 120,000 | 100% | 0 | -122,520 | pre-event |
| endlessFate USA-PAR E2 | 06-13 00:28:12-00:59:58 | -31.8 to -0.03 | 44 | 1,059,998 | 100% | 0 | -1,081,946 | pre-event |
| endlessFate AUS-TUR E1 | 06-14 03:56:58-03:59:27 | -3.0 to -0.6 | 10 | 360,002 | 100% | 0 | +151,046 | pre-event |
| endlessFate BEL-EGY E1 | 06-15 18:50:09-18:50:42 | -9.8 to -9.3 | 2 | 12,500 | 100% | 0 | -12,627 | pre-event |
| endlessFate KSA-URY E1 | 06-15 21:07:58-21:20:24 | -52.0 to -39.6 | 7 | 700,000 | 100% | 0 | +1,408,154 | pre-event |
| endlessFate KSA-URY E2 | 06-15 21:34:07-21:48:27 | -25.9 to -11.6 | 26 | 2,649,999 | 100% | 0 | +4,764,647 | pre-event |
| endlessFate UZB-COL E1 | 06-18 00:51:58 | -68.0 | 1 | 400,000 | 100% | 0 | +159,900 | pre-event |
| endlessFate UZB-COL E2 | 06-18 01:08:49-01:52:55 | -51.2 to -7.1 | 351 | 7,060,699 | 93% | 0 | +2,495,587 | pre-event |

No episode is post-outcome-known; every fill precedes the first goal of its match except CAN-BIH (see section 5). (VERIFIED against the tape and public reports)

[corrected by reviewer] Order creation times from the signed V2 Order structs (`review_03_order_times.py`; VERIFIED) refine the GRIMDRIP kick-off fills. Its single resting bid (2,000,000 Czechia-No shares at 0.50, signed 15:55:47) filled 14% between 15:55:53 and **16:00:01** and then stopped. Its final taker order was **signed at 16:00:12.5**, after the scheduled kick-off, and filled at 16:00:16. So the last ~$10k was a new in-play order in the first seconds of the match, still before Czechia's 6' goal. endlessFate's Colombia maker fills came from one resting 3.2M-share bid at 0.74 signed 01:38:43 (21% filled by 01:52:55, KO 02:00).

Max capital (`ge_capital.parquet`):

| wallet | peak cost of unresolved positions | peak cumulative net cash outlay | realised P&L / peak open cost |
|---|---|---|---|
| GRIMDRIP | $6,096,723 | $6,096,723 | 123% |
| endlessFate | $7,516,421 (Colombia, 06-18) | $4,990,277 (winnings were recycled) | 96% |

endlessFate's daily `/v2/user-pnl` series was **-$1.72M** after its first three resolved matches (KOR-CZE, CAN-BIH, USA-PAR), and still -$1.57M on 06-15. The KSA-URY draw turned it positive.

## 5. Timing versus public information

Match timelines (public reports; minute-to-UTC mapping approximate, about +/-3 min):

| match | key events (UTC approximate) | sources |
|---|---|---|
| CZE 1-1 RSA (KO 16:00) | 6' Sadílek (CZE) about 16:06; 83' Mokoena pen (RSA) about 17:40 | beIN Sports "All the Goals", bundesliga.com report |
| KOR 2-1 CZE (KO 02:00) | 0-0 HT; 59' Krejčí; 67' Hwang; 80' Oh | ESPN report, Sky Sports, FIFA PMSR M02 |
| CAN 1-1 BIH (KO 19:00) | 21' Lukić (BIH), tape jump at **19:22**; HT lull in tape about 19:47-20:03; 78' Larin (CAN), tape jump at **20:39** | Flashscore report, NBC, bundesliga.com |
| USA 4-1 PAR (KO 01:00) | 7' OG, 31', 45+5', 73', 90+8' | bundesliga.com, Al Jazeera live blog |
| AUS 2-0 TUR (KO 04:00) | 27' Irankunda, about 76' Metcalfe | socceroos.com.au, The Analyst |
| BEL 1-1 EGY (KO 19:00) | 19/20' Ashour (EGY); 66' Hany OG | bundesliga.com, beIN Sports |
| KSA 1-1 URY (KO 22:00) | 41' Al-Amri (KSA); 80' Araujo (URY) | Sky Sports, The Analyst |
| UZB 1-3 COL (KO 02:00) | 41' Muñoz, 60' Fayzullaev, 65' Díaz, 90+9' Campaz | FIFA PMSR M24 (20:00 local KO), ekantipur |
| IRN 2-2 NZL (KO 01:00, mintblade) | 7' Just, 32' Rezaeian, 54' Just, 64' Mohebi | Flashscore, Gulf News |

- **Pre-event entries (10 of 11 episodes).**
  - All began 3-69 minutes before kick-off, and none started earlier than 69 minutes before.
  - Secondary sources say World Cup line-ups are published about 60-75 minutes before kick-off: a data-API vendor says 75, fantasy sites say "about an hour". I did not verify the exact release time per match.
  - So the entries are **consistent with trading after public line-ups** (PLAUSIBLE), but no specific news item is identified.
  - In the 1-min tape (`notes/wallets/figs/ge_price_paths.png`), no price jump precedes any entry in the hour before it.
- **CAN-BIH in-play entry.** The fills sit in the half-time break and the first minutes of the second half, about 35 minutes after Bosnia's public goal.
  - Bosnia-No was 0.56-0.57 for the 10 minutes before the entry.
  - After the entry the price drifted *against* endlessFate (0.58 to 0.41) for about 30 minutes, until Canada's 78' equaliser at about 20:39.
  - No sign of anticipating the equaliser.
- **Price path and impact** (`ge_episode_impact.parquet`; trade prices are not executable quotes):

| wallet / market | p before first fill | p at last fill | VWAP | last trade before KO (others) | CLV = close - VWAP | wallet share of taker $ in window | impact per $1M |
|---|---|---|---|---|---|---|---|
| GRIMDRIP Czechia No | 0.47 | 0.50 | 0.498 | 0.50 | +0.002 | 77% | +0.6c |
| GRIMDRIP Draw Yes | 0.28 | 0.2965 | 0.288 | 0.29 | +0.002 | 92% | +1.6c |
| endlessFate Colombia Yes (E2) | 0.72 | 0.75 | 0.735 | 0.76 | +0.025 | 90% | +0.4c |
| endlessFate KSA-URY Draw (E1/E2) | 0.22/0.23 | 0.23/0.24 | 0.228/0.240 | 0.24 | +0.012/0.000 | 86%/77% | 3.3c/1.9c |
| endlessFate Uruguay No (E2) | 0.34 | 0.35 | 0.358 | 0.37 | +0.012 | 84% | +0.6c |
| endlessFate Saudi +1.5 (E2) | 0.60 | 0.62 | 0.618 | 0.63 | +0.012 | 78% | +3.5c |
| endlessFate USA-PAR Draw (E2) | 0.30 | 0.30 | 0.310 | 0.30 | -0.010 | 98% | 0 |
| endlessFate Korea No | 0.63 | 0.63 | 0.630 | 0.64 | +0.010 | 94% | 0 |
| endlessFate Australia +1.5 | 0.69 | 0.70 | 0.700 | 0.69 | -0.010 | 99% | +2.8c |

- Average slippage versus the previous trade by others was 0-1c per share.
- CLOB `/prices-history` (fidelity 1 min, explicit startTs/endTs) agrees with the tape's last trade within 1c in 90% of minutes (median 0.5c; n = 2,766 minutes). The two sources tell the same story. (VERIFIED)
- About 90% of GRIMDRIP's taker shares (95% for endlessFate) were filled by makers **bidding the complementary outcome**, i.e. new complete sets were minted. The rest came from holders selling the same outcome.

## 6. Counterparties and cross-wallet overlap (VERIFIED, `ge_counterparties.parquet`, `ge_cotraders.parquet`)

- **No candidate traded against another candidate.** There are 0 shared transaction hashes among GRIMDRIP, endlessFate and mintblade across all 13 market tapes.
- **Counterparties.**
  - GRIMDRIP: 739 distinct counterparties. The top one, BreakTheBank `0xf031…`, supplied 20%; the top 5 supplied 57%.
  - endlessFate: 548 counterparties. The top one, `0x2c33…0563`, supplied 19%; the top 5 supplied 48%.
  - The large counterparties are the same handful of liquidity providers on all three wallets: `0x2c33…`, BreakTheBank, `0x709e…` ("0xd4aa…"), ferrariChampions2026, surfandturf, BoggsFromShawshank. That is expected for market makers quoting every World Cup match, and is **not** evidence of a link.
- **Overlap with mintblade.** The only shared event is **Saudi Arabia v Uruguay**: the same three markets, the **same outcomes**, all BUY.

| market | endlessFate | LEEEROYJENKINS (co-trader) | mintblade |
|---|---|---|---|
| Spread Uruguay -1.5 -> Saudi Arabia | 21:07:58-21:47:40, $870k @ 0.608 | 21:49:15-21:53:36 (95 s after eF's last), $870k @ 0.620 | 21:56:04-21:58:49 (148 s after LJ's last), $660k @ 0.627 |
| Draw -> Yes | 21:09:07-21:47:19, $830k @ 0.235 | 21:50:15-21:52:34 (176 s), $70k @ 0.240 | 21:57:52-21:59:21 (318 s), $45k @ 0.240 |
| Uruguay win -> No | 21:19:51-21:48:27, $1.65M @ 0.357 | 21:48:49-21:54:10 (**22 s**), $180k @ 0.360 | 21:54:45-22:00:01 (**35 s**), $786k @ 0.365 |

  - mintblade's first fills came 2,094-2,925 s after endlessFate's first fills and 378-633 s after endlessFate's last fills, each time at a worse VWAP.
- **LEEEROYJENKINS** (`0x99ae…386f`; profile verified: pseudonym Big-Throne, created 2026-04-27T19:28:01Z, user id 7713440, Obsidian).
  - It made the same kind of pre-match buys. On Australia +1.5 it bought 03:54:13-03:55:49, and endlessFate followed 69 s later. On Belgium Yes it bought $8.67M from 17:17 to 19:00 while endlessFate bought $12.5k at 18:50.
  - It **lost $2.75M overall**: Belgium Yes alone lost -$8.76M.
- **Profile-creation pattern.** endlessFate (19:18:08) and LEEEROYJENKINS (19:28:01) were created 10 minutes apart with user ids 162 apart. mintblade and GRIMDRIP were created 14 minutes apart with ids 160 apart. Both endlessFate and LEEEROYJENKINS deposited exactly $5.0M on 2026-05-31 within about an hour.
- **Withdrawal / deposit sequence on 2026-06-18 (UTC).**
  - endlessFate withdrew $11.35M per the API; on-chain it was $15.35M gross and $12.25M net of $3.10M relayer refunds, from 13:28 to 14:32.
  - mintblade withdrew $11.63M from 14:42 to 15:32.
  - GRIMDRIP deposited $7.22M from 14:48 to 15:28, began trading at 15:23, then deposited $2.30M from 15:54 to 16:00.
- **Assessment.**
  - Coordinated or related activity among these four accounts is **PLAUSIBLE**. Evidence: sequential hand-offs within 22-176 s on identical legs, paired account creations, a matching deposit day and amount, and adjacent withdraw/deposit windows.
  - [corrected by reviewer] **Mirrored orders, VERIFIED (`review_05_mirrored_orders.py`).** On Belgium-win Yes, endlessFate, LEEEROYJENKINS and FlickRaw each signed an order for exactly **6,313 shares at 0.66 ($4,166.58)** at 18:50:06.183, 18:50:06.577 and 18:50:07.738 UTC. Each then signed an order for exactly **12,626 shares at 0.66 ($8,333.16)** at 18:50:39.695, 18:50:40.502 and 18:50:41.742. These are not round-dollar sizes; they are 1/3 and 2/3 of $12,500. Every one of these orders was signed before the first fill of its batch was mined (blocks 88,562,949/950 and 88,562,971/972), so no follower using public data could have copied it. For endlessFate and LEEEROYJENKINS the coordination is therefore **VERIFIED** rather than PLAUSIBLE: one controller, or one automated instruction, drove three separately keyed accounts. It is still not proof of common beneficial ownership. A systematic search over all fills of the 5 accounts (same token, size and price within 5 s) finds no other mirrors, and none that involve mintblade or GRIMDRIP.
  - **Common ownership is UNSUPPORTED.** Each wallet uses its own deposit address (GRIMDRIP `0x6e39…d17d`, endlessFate `0x8599…8945`, mintblade `0xb4c3…3a41`, LEEEROY `0xb227…f69a`). All of them are funded through the same high-volume hot wallet `0xf70d…dbef` (nonce 3.26M), which is bridge/relayer infrastructure.
  - **Update 2026-10-17 (see `linkage.md`):** this verdict was reached before the Relay withdrawals were followed off Polygon. All three wallets' withdrawals end, directly or through one single-purpose hop, in two Etherscan-tagged *Binance Deposit* addresses: `0xb08b…317d` received from all three and `0x3319…b072` from mintblade and endlessFate. The link is now classed **STRONG PROBABILISTIC** (common destination account, not a shared key).
  - All withdrawals go to the same depository contract `0x4cd0…bc31`, which emits only an opaque bridge ID.
  - No withdrawal amount matches a GRIMDRIP deposit amount (round $499,999 / $999,999 out versus ~$250,066 chunks in).
  - Shared bridge infrastructure is not proof. Alternative explanations: copy-trading chains, a shared signal or tipster, or a group of independent accounts.

## 7. Funds-flow appendix (VERIFIED where stated)

Receipts for all 198 deposit/withdrawal transactions of the three wallets were decoded (`ge_fund_flows.parquet`, `ge_fund_sources.parquet`).
- **Deposit route:** USDC.e from the wallet's deposit address, then `CollateralOnramp.wrap`, then pUSD minted to the proxy wallet. Some deposits are direct USDC.e from `0xf70d…`.
- **Withdrawal route:** pUSD to `CollateralOfframp`, then USDC.e to the proxy, then to `0x4cd0…bc31`.
- **RPC limits:** publicnode refuses historical receipts and logs ("Archive requests require a personal token"). This **contradicts the CONTEXT.md note that publicnode eth_getLogs works**: it works only for recent blocks. The free public endpoints `polygon.drpc.org` (receipts) and `rpc-mainnet.matic.quiknode.pro` (receipts; eth_getLogs up to 10,000 blocks) work.
- **The $1.6M gap (endlessFate), resolved.**
  - Method: QuikNode `eth_getLogs` over blocks 87.65M-88.75M (`ge_scan_pusd_logs.py`, partial run, cached) and targeted windows (`ge_reconcile_endlessfate.py`, output `ge_endlessfate_reconciliation.parquet`).
  - All of endlessFate's pUSD outflows are explained:
    - $13.84M to the two exchange contracts (`0xe222…` neg-risk, `0xe111…` CTF) = buys + fees.
    - 25 unwraps on 06-18 (13:28-14:32) totalling **$15,349,105**: the 20 API-listed withdrawals ($11,349,110) plus **5 withdrawals missing from `/v2/activity` ($3,999,995** at blocks 88,724,044-88,724,222).
  - Three of the missing ones ($999,999, $899,999, $499,999) were matched within 5 blocks by USDC.e **from the bridge relayer `0xf70d…` back to endlessFate** (less ~$0.003 each), then re-wrapped in one tx (`0xdb46…0509`, $2,399,996.99). That looks like a bridge withdrawal routed back to Polygon or refunded; its purpose is UNVERIFIED.
  - The 2 non-refunded missing withdrawals ($999,999 + $599,999 = **$1,599,998**) are exactly the gap.
  - Lesson: the Data API activity feed is **not a complete cash-flow ledger**. Reconcile on-chain before treating deposit/withdrawal rows as complete.
- **Small pUSD transfers.** $9,955 into endlessFate (05-31) and $115 into LEEEROYJENKINS came from 45-byte minimal-proxy contracts with no Polymarket profile, which look like deposit forwarders. No link is implied.

## 8. The user's screens (trailing 12 months to 2026-10-17; `ge_screens.parquet`, `ge_null_pnl.parquet`)

| wallet | rule | resolved decisions | wins | losses | (i) exactly 5, all successful | (ii) at least 5, no losses |
|---|---|---|---|---|---|---|
| GRIMDRIP | per market | 2 | 2 | 0 | fail (2 ≠ 5) | fail (< 5) |
| GRIMDRIP | per event | 1 | 1 | 0 | fail | fail |
| GRIMDRIP | per "made money" (market / event) | 2 / 1 | 2 / 1 | 0 | fail | fail |
| endlessFate | per market | 9 | 6 | 3 | fail | fail |
| endlessFate | per event | 7 | 4 | 3 | fail | fail |
| endlessFate | per "made money" (market / event) | 9 / 7 | 6 / 4 | 3 / 3 | fail | fail |
| endlessFate | **naive "closed positions only"** | 6 | 6 | 0 | fail (6 ≠ 5) | **pass (spurious)** |
| mintblade | per market | 5 | 5 | 0 | **pass** | **pass** |
| mintblade | per event | 3 | 3 | 0 | fail | fail |
| mintblade | per "made money" (market) | 5 | 5 | 0 | pass (one leg is a $4.80 ticket that made $0.19) | pass |

"Won" and "made money" coincide at market level here because there were no exits.

### Why a 5-for-5 record is weak evidence

- **Null model:** every decision wins with its entry-implied probability (VWAP), so edge is zero. Matches are independent. Nested legs within a match are handled jointly through a home-margin state distribution backed out of the wallet's own entry prices; all outcomes are enumerated exactly.

| | GRIMDRIP | endlessFate | mintblade |
|---|---|---|---|
| P(all markets won) | 0.288 | 0.009 | 0.113 |
| naive product of VWAPs (ignores nesting) | 0.143 | 0.002 | 0.026 |
| P(all events made money) | 0.498 | 0.013 | 0.172 |
| expected events won (observed) | 0.29 (1) | 3.84 (**4**) | 1.69 (3) |
| P(P&L at least as large as observed) | **0.288** | **0.168** | **0.113** |
| expected P&L under null (= -fees) | -$94,912 | -$160,131 | -$127,398 |
| SD of P&L under null | $6.16M | $6.27M | $7.33M |

- **The naive product of entry prices overstates the evidence.**
  - Example: mintblade's per-market 5-for-5 has naive probability 0.026, but because three legs are the same match the correct joint probability is **0.113**.
  - The probability is also small only because some legs are longshot draws. A draw at 0.24 happens 1 time in 4.
- **Base rate: how many wallets pass by luck.**
  - Analytically, a wallet with five independent bets at price p passes with probability p^5: 3% at p = 0.5, 17% at 0.7, 59% at 0.9.
  - Empirically, from a 2% hash sample of CryptoHouse `user_positions` x `assets` (markets closed 2025-01-05 to 2026-01-05, pre-V2; `ge_base_rate_cryptohouse.parquet`), 1,020 sampled wallets had exactly 5 resolved markets. **380 (37%) won all five** and **103 (10%) made money on all five**.
  - Scaled to the population, that is about 51,000 wallets with exactly five decisions, of which about **19,000 are "5-for-5"** and about **5,000 "made money 5-for-5"**.
  - For at least 5 decisions with no losses (5-12 markets), about 93,000 wallets pass on wins and about 17,000 on made-money.
  - Caveats: `assets` covers only about 22k markets, so per-wallet counts are truncated; "won" means the outcome the wallet bought most of resolved to 1. The figures are PLAUSIBLE order-of-magnitude, not exact.
  - Either way, **thousands of wallets per year pass the user's screen by luck alone**.
- **Selection makes it worse.** These wallets came to attention because their P&L is large. The style-identical LEEEROYJENKINS lost $2.75M on overlapping matches and would never appear on a winners list.

## 9. Comparison with mintblade

| | GRIMDRIP | endlessFate | mintblade |
|---|---|---|---|
| active window | 06-18 15:23-16:00 | 06-12 to 06-18 | 06-03 ($4.80 test), 06-15 to 06-16 |
| distinct matches / markets | 1 / 2 | 7 / 9 | 2 World Cup + 1 MLB / 5 |
| style | pre-match, last 37 min, "Czechia not win" + draw | pre-match (1 at half-time), draw/underdog-not-lose sides, plus Colombia favourite | pre-match, "Iran not win" (last 43 min) and the KSA-URY trio |
| taker order sizes | median $50k; 90% are round $10k multiples (e.g. $250,000.01, $200,000.07) | median $35k; up to $1.14M; 54% round | median $10k; up to $851k; 55% round |
| maker fills | 577, median $10 | 336, median $28 | 561, median $10 |
| realised P&L | +$7.51M | +$7.25M (+$0.07M rebates) | +$9.11M |
| shared events | none | KSA-URY with mintblade (same side; mintblade 6-10 min later) | KSA-URY |

## 10. Is following profitable?

> Pointer (2026-10-17): a print-based follower reconstruction with delays of 5 s to hourly, $500–$10k sizes, fees and a zero-edge null is in `copyability.md`. It supersedes the ex-post copy test here.

- [corrected by reviewer] **Point-in-time selection (VERIFIED, `review_04_pit_screen.py`):** at the time of every one of its entries, none of the three wallets passed either screen under any counting rule. GRIMDRIP had no resolved history at all. endlessFate had 0–8 resolved markets including losses, and was −$1.57M realised before its KSA-URY entries. mintblade had only the $4.81 Mets ticket. mintblade passes (per market) only after its final market resolved (06-16 03:22 UTC), and it never traded again. A follower using the user's screens would have copied **zero** of these trades. The ex-post copy results below assume the wallets were known in advance.
- **Ex post:** an equal-weight follower entering 1, 5 or 15 minutes after each wallet's first or last fill would have earned about the wallets' own returns on these matches (`ge_copy_lag.parquet`):
  - GRIMDRIP: about +170-180% per $ on 2 legs
  - endlessFate: about +64-70% mean per $ over 14 market-episodes
  - Reason: pre-match prices barely moved after the entries.
- **But this replicates luck, not demonstrated skill:**
  1. Win rates match the entry-implied probabilities (4 vs 3.84 expected for endlessFate).
  2. CLV is about zero.
  3. The P&L is dominated by three drawn matches (CZE-RSA, KSA-URY, IRN-NZL) bought at 0.24-0.29.
  4. Over all four style-similar accounts, the combined record is 6 profitable and 3 losing matches. Belgium alone lost -$8.77M.
- **Capacity:** the wallets were 70-100% of the taker flow in their windows. A follower would be buying after them, at or above their VWAP, with little depth left.
- **Data latency:** fills appear in the Data API after settlement on Polygon. The wallets finished most episodes 7-12 minutes before kick-off, so a follower has minutes, not hours.
- **Dormancy:** no wallet has traded since June/July 2026, so there is nothing to follow now (`/v2/value` = 0, no open positions).

## 11. Contradictions with CONTEXT.md and data caveats

- **Fee rate:** sports fee rate in these markets is **0.03** (`sports_fees_v2`), not the 0.05 category default.
- **Mets position:** mintblade's Mets position realised **+$0.19**, not $0.
- **Polygon RPC:** publicnode does **not** serve historical `eth_getLogs` or receipts.
- **Deposits/withdrawals:** they appear in `/v2/activity` only with `exclude_deposits_withdrawals=false` (default true, per the v2 OpenAPI spec).
- **Missing withdrawals:** even then, **5 of endlessFate's 25 on-chain withdrawals and 3 relayer refunds are missing** (VERIFIED on-chain). GRIMDRIP and mintblade reconcile to within $5.
- **`/v2/trades` start/end:** honoured on the `user` shape only; the `condition` shape serves a fixed three-year window (OpenAPI spec). `filter_amount` defaults to 0.01 shares.
- **Tier fields:** `weightedVolume` equals last-trading-day taker wV for all three wallets, so the tier looks stale (semantics UNVERIFIED).
- **Kick-off times:** actual kick-off can differ from `gameStartTime` by a minute or two. Fills within about 20 s of scheduled kick-off are classed pre-event; they total $10k for GRIMDRIP and $2k for mintblade-KSA.
- **Line-up times:** release times were not verified per match.

## Files

- **Scripts** (`analyses/wallets/`):
  - `ge_pull_wallets.py`, `ge_map_markets.py`, `ge_pull_tapes.py`, `ge_build_decisions.py`, `ge_tape_analysis.py`
  - `ge_onchain_flows.py`, `ge_deposit_sources.py`, `ge_scan_pusd_logs.py`, `ge_screens.py`, `ge_base_rate_cryptohouse.py`
  - `ge_capital_sizes.py`, `ge_copy_lag.py`, `ge_pull_leeroy.py`, `ge_plot_paths.py`
- **Derived data** (`data/derived/`):
  - `ge_fills`, `ge_dec_market`, `ge_dec_match`, `ge_dec_episode`, `ge_match_states`
  - `ge_episode_impact`, `ge_price_paths`, `ge_counterparties`, `ge_cotraders`, `ge_cross_candidates`, `ge_overlap_timing`
  - `ge_screens`, `ge_null_pnl`, `ge_base_rate_cryptohouse`, `ge_capital`, `ge_size_patterns`, `ge_copy_lag`
  - `ge_fund_flows`, `ge_fund_sources`, `ge_leeroy_*`, `ge_markets`, `ge_event_markets`, `ge_events`
  - Raw API pulls: `ge_trades_*`, `ge_activity*`, `ge_positions`, `ge_user_stats`, `ge_user_pnl`, `ge_value`, `ge_profiles`
  - Tapes: `ge_tape_*`, `ge_prices_1m`
- **Figure:** `notes/wallets/figs/ge_price_paths.png`.

External sources (match facts):
- beIN Sports "All the Goals! Czechia vs South Africa" and "Belgium vs Egypt" (beinsports.com, 2026-06-18 and 2026-06-15)
- bundesliga.com match reports (CZE-RSA, CAN-BIH, USA-PAR, BEL-EGY)
- Flashscore reports (CAN-BIH, IRN-NZL)
- ESPN gameId 760414 (KOR-CZE)
- Sky Sports (KOR-CZE, KSA-URY)
- The Analyst (KSA-URY, AUS-TUR)
- socceroos.com.au (AUS-TUR kick-off)
- FIFA post-match summary reports PMSR-M24 (UZB-COL, 20:00 local KO) and PMSR-M02 (KOR-CZE), fifatrainingcentre.com
- Al Jazeera live blog (USA-PAR)
- Gulf News (IRN-NZL)
- thestatsapi.com (line-ups about 75 min before KO; vendor claim, not FIFA)
