# mintblade (0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb): full reconstruction

> Reviewed adversarially on 2026-10-17 (`analyses/wallets/review_0[1-5]_*.py`). Fills, fees ($127,397.56), redemptions, realised P&L ($9,109,604.79), screens, event grouping, null probabilities and peak capital ($7,982,923) were re-derived independently from raw /v2 data and confirmed. Corrections are marked [corrected by reviewer]. Consolidated view: `WALLETS.md`.

As of 2026-10-17. All data are read-only public pulls; raw payloads are under `data/raw/` (provenance by `pmr.http`).
Labels: **VERIFIED** = checked in primary data, **PLAUSIBLE** = consistent with the evidence but not proven, **UNSUPPORTED** = no support.

## 0. Bottom line

- The wallet made **3 distinct betting decisions** on **3 underlying events**, spread over 5 markets. Two of them matter: a pre-kick-off "Uruguay does not win" bet on Saudi Arabia vs Uruguay ($1.51M at risk) and a pre-kick-off "Iran does not win" bet on IR Iran vs New Zealand ($7.14M at risk). The third is a $4.81 in-play Mets ticket. All three won. Realised P&L is **$9,109,605** from cash flows ($9,110,690 in the Data API), plus $28,790 in rebates. **VERIFIED**
- The P&L is essentially **one ~49% coin flip (Iran No at 0.489) at very large size**. Under the market-implied null, P(total P&L > 0) = 0.489 and P(P&L >= the realised $9.11M) = 0.116. Expected P&L under the null is about **-$155k** (fees plus paying above mid). **VERIFIED** (arithmetic on verified inputs)
- How the screens come out depends on how you count. Counting markets, the wallet passes both "exactly 5, all won" and ">= 5, no losses". Counting distinct events, it fails both (n = 3). Counting markets but dropping the $4.81 Mets test ticket (any minimum stake of $100 or more), it also fails (4 markets, 2 events). Even where it passes, the chance of the same record under the null is 0.11 (correlation-aware) to 0.17 (per event). Nothing here separates skill from luck.
- Timing: both large entries were **pre-event**, made in the last 47 minutes before kick-off. The only in-play entry was the $4.80 Mets ticket, bought after a public 4-run inning. I found no fill after a goal or card. Iran's 7th-minute New Zealand goal came 6.5 minutes after the wallet's last fill. **VERIFIED** (tape, CLOB prices-history, match reports). Performance is not evidence of private information, and none is claimed.
- The wallet was **the price-setter**, not a hidden passenger. In its Iran window it supplied 72.6% of all taker volume and 96.5% of the taker volume on the "No" side. It moved Iran-No from 0.465 to 0.505 (CLOB). A follower would have entered after this impact.
- **endlessFate** (another candidate) took **the same three Saudi–Uruguay positions in the same direction** 6–47 min earlier, about $3.35M notional. It never traded against mintblade (0 shared transactions in 5 markets). **GRIMDRIP** never traded these markets. A shared, sequential operational pattern on 2026-06-18 is noted in Section 9 as a lead for the clustering workstream. It is **not** evidence of common ownership.

## 1. Address to profile (VERIFIED)

| Field | Value | Source |
|---|---|---|
| Gamma `/public-profile` name | `mintblade` (pseudonym `Golden-Reclamation`) | live 2026-10-17 |
| proxyWallet | 0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb | public-profile |
| createdAt | 2026-06-02T14:47:45.193735Z | public-profile |
| Gamma user id | 8422116 | public-profile `users[0].id` |
| takerTier / name | 6 / Obsidian | public-profile |
| weightedVolume | 3,466,942.92 | public-profile (the tier persists although there is no trading after 2026-06-16; the window semantics are not documented here) |
| verifiedBadge | false | public-profile |
| Data API row `name` | `mintblade` on all 830 activity rows and 727 trade rows | /v2/activity, /v2/trades |
| `/v2/user-stats` | trades=5 (= distinct markets), join_date 1780411665 (= createdAt), views 87,363, biggest_win 7,231,848.50 | live |

## 2. Data pulled and API behaviour (VERIFIED unless marked)

Scripts are in `analyses/wallets/mintblade_0[1-8]_*.py`.

- `/v2/activity`: 735 rows by default and 735 with `exclude_deposits_withdrawals=true`. **830 rows with `exclude_deposits_withdrawals=false`**: 58 DEPOSIT and 37 WITHDRAWAL rows appear. So by default deposits and withdrawals are *excluded*. CONTEXT.md's list of activity types omits DEPOSIT and WITHDRAWAL; they exist behind this flag. Types: TRADE 727, DEPOSIT 58, WITHDRAWAL 37, REDEEM 5, TAKER_REBATE 2, MAKER_REBATE 1. There are no SPLIT, MERGE or CONVERSION rows.
- `/v2/trades?user=`: 727 rows with `taker_only=false` and 166 with the default (identical to `taker_only=true`). Every default row matches one `taker_only=false` row exactly (tx hash, token, size, price, timestamp, side).
- **Maker/taker inference.** I label the 166 matching rows as taker fills and the other 561 as maker fills. Check: for all 166 taker rows, the activity `usdc_size - size*price` equals `size × 0.03 × p × (1−p)` to within 1.3e-5. For all 561 maker rows it is exactly 0. Summed taker fees are $127,397.56, which equals `user-stats fees_paid` (-127,397.55907). So the inference is consistent with the fee schedule and the API.
- **Fee regime at trade time.** All 5 markets have `feeType=sports_fees_v2` and `feeSchedule {rate 0.03, exponent 1, takerOnly true, rebateRate 0.25}`. That is *0.03*, not the 0.05 sports rate in CONTEXT.md's category table. Per-market Gamma fields are authoritative, and the June-2026 fills reconcile to 0.03.
- `/v2/positions`: status=OPEN, REDEEMABLE, REDEEMABLE_LOST and MERGEABLE all return 0 rows. CLOSED returns 5. No status at all also returns 0. `/v2/value` = 0.0.
- `/v2/user-pnl`: the default is `interval=1d` (hourly points on a daily-snapshot source). `interval=all` returns 3,256 hourly points from 2026-06-04 to 2026-10-17 (`mintblade_user_pnl_all.parquet`). The only mark-to-market snapshot with an open position was 2026-06-16 00:00Z: unrealised -$124,707 on the Saudi–Uruguay legs, fees $23,389. `user-stats.all_time_pnl.timestamp` = 2026-07-09 00:00Z (source block 89,900,136), the last change.
- Market tapes: `/v2/trades?condition=` with `taker_only=false` and with the default, paged newest-first back to 2–3 h before the wallet's first fill. `start`/`end` were ignored again (re-tested), and duplicate identical rows inside one tx are genuine (several equal maker orders), so I did not dedupe them.
- CLOB `/prices-history`, `fidelity=1`, explicit `startTs`/`endTs`: 280–314 points per token, all outcomes of the traded markets plus the 1X2 siblings.
- Polygon: `polygon-bor-rpc.publicnode.com` now refuses June receipts ("Archive requests require a personal token"). **`https://polygon.drpc.org` (no key) works** and is used in `mintblade_06_onchain.py`.

## 3. Markets and events (Gamma, closed=true; VERIFIED)

| Market (condition) | Event | Type | gameStartTime (UTC) | Resolution | closedTime | negRisk |
|---|---|---|---|---|---|---|
| New York Mets vs. Seattle Mariners (0xa95e…f5a1) | mlb-nym-sea-2026-06-03 (MLB) | moneyline | 06-03 19:40 | Mets [1,0]; score 7-1 | 06-03 22:36:10 | no |
| Will Uruguay win on 2026-06-15? (0xbc54…7317) | fifwc-ksa-ury-2026-06-15 | moneyline | 06-15 22:00 | No [0,1]; score 1-1 | 06-16 02:06:57 | yes |
| Will Saudi Arabia vs. Uruguay end in a draw? (0x3443…04fe) | fifwc-ksa-ury-2026-06-15 | moneyline (3-way draw) | 06-15 22:00 | Yes [1,0] | 06-16 02:06:57 | yes |
| Spread: Uruguay (-1.5) (0xa16a…9be1) | fifwc-ksa-ury-2026-06-15-more-markets | spreads | 06-15 22:00 | Saudi Arabia [0,1] | 06-16 00:35:48 | no |
| Will IR Iran win on 2026-06-15? (0xe70f…d9d4) | fifwc-irn-nzl-2026-06-15 | moneyline | 06-16 01:00 | No [0,1]; score 2-2 | 06-16 03:22:16 | yes |

All five have `umaResolutionStatus=resolved`, `umaResolutionStatuses=["proposed"]`, `automaticallyResolved=true`, `secondsDelay=0`, tick 0.001, min size 5, and tags `sports,games,soccer,fifa-world-cup` (`mlb,baseball` for the Mets). Saudi–Uruguay is **one match split across two Gamma events** (the main event plus "-more-markets"). I treat it as one underlying event.

## 4. Decision tables (VERIFIED; `mintblade_decisions_market.parquet`, `_event`, `_episodes`, `_fills`)

All 727 fills are BUYs. There are no sells and no merges, and every position was redeemed in full (redeemed shares = bought shares). Unrealised P&L is 0.

### 4a. Per market

| Market → outcome | Fills (taker/maker) | First–last fill (UTC) | Shares | VWAP (incl. fee) | Notional | Fees | Redeemed | Realised P&L | Return on cost | Edge per share (payoff − VWAP) |
|---|---|---|---|---|---|---|---|---|---|---|
| Mets ML → Mets | 1 (1/0) | 06-03 21:18:42 | 5 | 0.960 (0.9612) | $4.80 | $0.006 | $5.00 on 06-15 21:20 | **+$0.19** | 4.0% | 0.040 |
| Uruguay win → No | 36 (36/0) | 06-15 21:54:45–22:00:01 | 2,152,994 | 0.3652 (0.3722) | $786,362 | $14,973 | $2,152,994 | **+$1,351,659** | 169% | 0.635 |
| Spread URU −1.5 → Saudi | 11 (11/0) | 21:56:04–21:58:49 | 1,053,072 | 0.6267 (0.6338) | $659,999 | $7,390 | $1,053,072 | **+$385,683** | 58% | 0.373 |
| Draw → Yes | 5 (5/0) | 21:57:52–21:59:21 | 187,501 | 0.2400 (0.2455) | $45,000 | $1,026 | $187,501 | **+$141,475** | 307% | 0.760 |
| Iran win → No | 674 (113/561) | 06-16 00:17:22–01:04:03 | 14,366,351 (taker 13,879,618; maker 486,732) | 0.4894 (0.4967) | $7,031,554 (taker $6,788,187; maker $243,366) | $104,008 | $14,366,351 | **+$7,230,789** | 101% | 0.511 |
| **Total** | 727 (166/561) | | | | **$8,522,920** | **$127,398** | **$17,759,922** | **+$9,109,605** | | |

Data API `positions.realized_pnl` sums to $9,110,689.71, which is $1,084.92 (0.012%) above my cash-flow figure: Iran +$1,059.91, Uruguay +$18.91, spread +$5.92, draw +$0.19. The cash-flow figure is the one consistent with the books. Deposits minus withdrawals plus redemptions plus rebates minus trade cash leaves −$1.67, and the on-chain pUSD and USDC.e balances of the wallet are 0. So I treat the API number as slightly overstated. I did not identify the source of the API's cost basis. **VERIFIED** (the reconciliation); the cause is unknown.

Holding period from first fill to redemption is 2.7–4.2 h for the football legs. For the Mets it is 288 h: the game ended 1 h after the fill, but the ticket was only redeemed when the wallet came back on 06-15.

### 4b. Per distinct event (decision)

| Event | Markets | Cost | Realised P&L | Result | Taker share |
|---|---|---|---|---|---|
| NYM–SEA 2026-06-03 | 1 | $4.81 | +$0.19 | won (Mets 7-1) | 100% |
| KSA–URU 2026-06-15 | 3 (one nested decision, see §6) | $1,514,751 | +$1,878,816 | all legs won (1-1 draw) | 100% |
| IRN–NZL 2026-06-15 | 1 | $7,135,562 | +$7,230,789 | won (2-2 draw) | 96.5% |

### 4c. Entry episodes (a gap of more than 10 minutes starts a new episode)

| # | Event | Start–end (UTC) | Fills | Cost | Relative to the inferred actual start | Class |
|---|---|---|---|---|---|---|
| 1 | NYM–SEA | 06-03 21:18:42 | 1 | $4.81 | +98.7 min after first pitch | **in-play-after-public-news** |
| 2 | KSA–URU (3 markets) | 06-15 21:54:45–22:00:01 | 52 | $1.51M | −8.9 to −3.6 min | **pre-event** |
| 3 | IRN–NZL | 06-16 00:17:22–01:04:03 | 674 | $7.14M | −46.7 to ≈0 min | **pre-event**. 93.5% of cost was filled before the scheduled 01:00 KO and 98.6% before 01:03:50. The final 200k-share ($100k) taker fill at 01:04:03 lands on the inferred kick-off ±15 s, so it is at most "in-play, first seconds, no identified news" |

### 4d. Capital

- Max capital deployed was **$7,982,923** at 06-16 01:04:03. That is the Iran cost plus the unredeemed Uruguay-No and draw legs, whose game had already ended at 00:05.
- Max **capital at risk** (positions in games not yet finished) was **$7,135,562**, the Iran position only. The Saudi–Uruguay game ended before the Iran entry began, so the two bets were never at risk at the same time. The Saudi–Uruguay peak at risk was $1,514,751.
- Return on max capital deployed is 114%. On max at risk it is 128%. These are single-night returns from two outcomes.

## 5. Why "New York Mets vs. Seattle Mariners" shows $0 realised P&L (VERIFIED)

It is not open, not sold, not merged and not a loss. On 2026-06-03 21:18:42 the wallet bought **5 shares, the market's `orderMinSize`, at 0.96** for $4.80 plus a $0.00576 fee. That was 98.7 minutes after first pitch, after the Mets' public 4-run 4th inning (line score NYM 1-0-0-4-1-0-0-1-0, SEA 1-0-0-0-0-0-0-0-0). The score at the fill was probably 6-1, around the 6th inning (PLAUSIBLE: inferred from elapsed time, not a play-by-play timestamp). The Mets price had already risen from 0.43 pre-game to about 0.93 by 21:00 and 0.96 by 21:10. The Mets won 7-1. The wallet redeemed the 5 shares for $5.00 on 2026-06-15 21:20:21, twenty minutes before its first large deposit. Realised P&L is **+$0.19424**: `/v2/positions` `realized_pnl=0.1942`, percent 4.04%. It displays as $0 because of rounding. It was the wallet's first trade, one day after account creation and following a $15 deposit. It has the size and shape of a functionality test (PLAUSIBLE as to intent). Economically it should not count as a "betting decision".

## 6. Are the three Saudi Arabia vs Uruguay markets one decision? Yes (VERIFIED)

The three legs are **nested** bets on one state variable, the final goal difference:

`Draw ⊂ (Saudi win or Draw) = "Uruguay win: No" ⊂ (not Uruguay by 2+) = "Spread Uruguay −1.5: Saudi"`.

They were bought within one 5-minute window (21:54:45–22:00:01). P&L by state, using the wallet's actual share counts and costs:

| Final state | Market-implied prob. at entry (CLOB 21:54/22:00, normalised) | Legs paying | Payout | P&L |
|---|---|---|---|---|
| Saudi win | 0.121 | Uruguay No + Spread | $3,206,066 | +$1,691,315 |
| **Draw (actual, 1-1)** | 0.236 | all three | $3,393,567 | **+$1,878,816** |
| Uruguay by 1 | 0.261 | Spread only | $1,053,072 | −$461,679 |
| Uruguay by 2+ | 0.382 | none | $0 | −$1,514,751 |

- Indicator correlations for nested events: draw vs Uruguay-No ≈ 0.74; Uruguay-No vs spread ≈ 0.59; draw vs spread ≈ 0.43.
- Under the market-implied probabilities, the combined position made money with probability ≈ 0.36 (Saudi win or draw). All three legs won with probability ≈ 0.24 (draw only). The combined expected P&L was **−$51k**.
- Treating the three legs as independent would understate the probability of "all three win" by a factor of about 4: 0.365 × 0.627 × 0.24 = 0.055 against the true 0.236. Counting them as three wins is double counting.
- The wallet did not trade the sibling "Saudi Arabia win" market or any totals markets.

## 7. The Iran "No" position: 14.37M shares at 0.4894 (0.4967 incl. fee) against timing and depth

- **Timing (VERIFIED).** Scheduled KO was 01:00 UTC (Al Jazeera: "6pm local time (01:00 GMT on Tuesday)"; Gamma `gameStartTime`). I infer the actual KO from the first two goal-driven price jumps in the tape: the New Zealand 1-0 goal in the 7th minute at 01:10:33 gives KO ≈ 01:04:03, and the Iran 1-1 goal in the 32nd minute at 01:35:42 gives KO ≈ 01:04:12. So actual KO was about 01:04 UTC (**PLAUSIBLE**, ±~1 min).
  - The wallet bought from 00:17:22 to 01:04:03.
  - From 00:17 to 00:58 it placed taker fills of round dollar amounts (Iran: $10k ×64, $50k ×24, $100k ×8, $200k ×5, $500k ×2, plus a few odd sizes up to $851k; Saudi–Uruguay showed the same pattern). They stepped the price from 0.47 to 0.48, 0.49 and 0.50. This is consistent with "buy $X" market orders (PLAUSIBLE).
  - From 00:59:24 to 01:03:48 it rested a **No bid at 0.50**, filled 561 times (486,732 shares) by 213 takers.
    - [corrected by reviewer] Order-level decode of the signed V2 Order structs (`review_03_order_times.py`, `review_order_times.parquet`; VERIFIED): this was **five successive 500,000-share No bids at 0.50**, not one bid. They were signed at 00:59:09.7, 00:59:27.5, 00:59:41.7, **01:01:13.2 and 01:01:52.1** UTC and filled 36%, 7%, 1%, 53% and 0.2%; each stopped filling while partly unfilled (cancel-and-replace). Two of them were therefore signed *after* the scheduled 01:00 kick-off. The final 200k-share taker order was signed at **01:04:00.2** (filled 01:04:03). So the wallet was still making new decisions after the scheduled kick-off; whether these were before the actual kick-off depends on the inferred ~01:04 start (PLAUSIBLE). Taker orders across all three wallets were signed a median 2.5 s (IQR 2.1–2.9 s) before their fill block.
  - One last 200k-share taker fill came at 01:04:03.
  - No goal, card or other match event preceded any fill. The first goal (NZ, 01:10:33) came 6.5 minutes after the last fill and moved Iran-No from about 0.48 to 0.70.
  - Public pre-match news (Al Jazeera, 2026-06-15): injury doubts for Eckert, Jahanbakhsh and Torabi; 11 Iranian federation members denied visas; the squad arriving on match day. All of this was public before the entries. Line-ups are typically published about 1 h before KO; I did not verify the exact release time. Nothing in the public timeline I found is specific to 00:17–01:04.
- **Depth and impact (VERIFIED from the tape and CLOB).**
  - The wallet's taker buys of No were matched mostly against **resting Iran-Yes bids (mints)**: 13.27M of 13.88M shares. Only 0.61M were matched against No sellers.
  - The largest single order, 1,702,154 shares ($851k at 0.50) at 00:55:31, cleared at **one price level against 33 makers** in one transaction. Two makers each bid about 500k Yes at 0.50.
  - Across its 113 taker transactions, an order touched at most 2 price levels (median 4 makers per transaction). So the book was deep at the touch and repeatedly refilled. No historical book snapshot exists, so these numbers are a lower bound on depth at the level, not the full book.
  - Maker counterparties were concentrated: top 1 = 27%, top 5 = 62%, top 10 = 77% of 13.88M shares, from 297 wallets. The top maker, 0x2c33…0563, also supplied 300k shares in the Uruguay market and looks like a liquidity provider (PLAUSIBLE).
  - **Share of flow.** In 00:17:22–01:04:03 the wallet was 72.6% of all taker shares (13.88M of 19.13M) and 96.5% of the taker shares on the No side. Its 14.37M shares ($7.03M) equal 27% of the market's lifetime Gamma volume ($26.1M).
  - **Price path.** Iran-No (CLOB) read 0.455 at −60 min, 0.465 at the first fill, 0.505 at the last fill and 0.485 at +5 min. Others' tape VWAP was 0.4515 at −60…−30 min, 0.461 at −10…0 min and 0.483 at 0–5 min after. So the wallet paid about 2.8c above the pre-entry level, and about 1.7c of that reverted before the goal (temporary impact). Relative to the −10…0 min VWAP, the impact cost was about $0.40M.
- **Interpretation.** A $7M pre-match position at roughly even odds on "Iran does not beat New Zealand". The market's own 1X2 prices at 00:17 were Iran 0.535 / draw 0.275 / NZ 0.195, and 0.495 / 0.285 / 0.215 at 01:04 after the wallet's buying. The wallet was betting that the market overpriced Iran. The outcome (2-2) went its way. One outcome cannot tell us whether that view was right ex ante.

## 8. Timing against public information, all events (VERIFIED unless marked)

| Event | Wallet fills | Public timeline | Classification |
|---|---|---|---|
| NYM–SEA 06-03 | 21:18:42 (1 fill) | First pitch 19:40; Mets 4-run 4th (price 0.46 to 0.73 in the 20:40 bin, about 0.93 by 21:00); Mets 6-1 after 5 (line score); final 7-1, game finished 22:17:53 | in-play-after-public-news (bought at 0.96 after the move) |
| KSA–URU 06-15 | 21:54:45–22:00:01 | Scheduled KO 22:00. Actual KO about 22:03:36, inferred from the Saudi 41' goal jump at 22:44:06 (PLAUSIBLE). Uruguay equaliser 80' at 23:45:25. Final 1-1, finished 00:05:03 | pre-event. No specific news identified, but strong same-direction buying in the hour before (incl. endlessFate) had already moved Uruguay-No from 0.325 to 0.355 (CLOB) |
| IRN–NZL 06-15/16 | 00:17:22–01:04:03 | KO about 01:04; goals 7' (01:10:33), 32' (01:35:42), 53/54' (02:21:36), 63/64' (02:30:40); final 2-2, finished 03:03:24 | pre-event (last fill at KO ±15 s) |

Match sources: Gulf News (Iran 2-2 New Zealand; goals 7', 32', 53'/54', 63'/64'), Flashscore (the same), Al Jazeera (KO time, team news), and AP via Borneo Post / Ahram (Saudi Arabia 1-1 Uruguay; 41' Al-Amri, 80' M. Araújo). Mets line score from mrbaseball.com game 823130. The goal minute-to-UTC mapping uses the tape's price jumps, not an official clock.

Figure: `notes/wallets/mintblade_price_paths.png` shows the per-minute tape VWAP of the wallet's own outcome token from 60 min before to 60 min after each episode, with the wallet's fills, KO and goal markers. Tape prints are not executable prices.

Price impact per leg (others' taker VWAP, `mintblade_impact.parquet`):

| Leg | −60…−30 min | −10…0 min | Wallet VWAP | 0…+5 min | Wallet share of taker shares in its window |
|---|---|---|---|---|---|
| Uruguay No | 0.329 | 0.360 | 0.365 | 0.360 | 93.7% |
| Spread Saudi | 0.589 | 0.620 | 0.627 | 0.624 | 94.9% |
| Draw Yes | 0.227 | 0.240 | 0.240 | 0.241 | 94.4% |
| Iran No | 0.452 | 0.461 | 0.489 | 0.483 | 72.6% (96.5% of No-side flow) |

## 9. Counterparties and the other candidate wallets (VERIFIED)

- Counterparties are in `mintblade_counterparties.parquet`.
  - Taker fills: the other rows in the same transaction are the makers.
  - Maker fills: the counterparty is the taker row from the taker-only tape. Other makers in the same transaction are on the same side and are labelled "co-maker".
- Distinct counterparties: Iran 297 makers plus 213 takers; Uruguay-No 89; spread 41; draw 14; Mets 1.
- Largest named counterparties: 0x2c33…0563 (3.79M Iran, 0.30M Uruguay), "Countryside" (2.01M Iran), "surfandturf" (1.20M Iran), "wr0ngw4yb3tt0r" (0.62M Uruguay plus 0.29M spread), "eth10001" (131k draw).
- **GRIMDRIP (0x3f87…742c)** has no trades in any of the 5 markets (`/v2/trades?user=&condition=` and the tapes) and no shared transaction hash. Its only markets are Czechia vs South Africa on 2026-06-18: Czechia-win No (9.93M shares) and draw Yes (3.68M), traded 15:23–16:00.
- **endlessFate (0x5e4c…dba2)** has no shared transaction with mintblade, so it **never traded against it**. It **took the same three Saudi–Uruguay legs in the same direction earlier**:
  - Uruguay No: 4.63M shares at 0.357, 21:19–21:48
  - Spread Saudi: 1.43M shares at 0.608, 21:08–21:48
  - Draw Yes: 3.53M shares at 0.235, 21:09–21:47
  - That is $3.35M notional. mintblade entered 6–47 min later at slightly worse prices (0.365 / 0.627 / 0.240). endlessFate did not trade the Iran market.
- **Operational similarity on 2026-06-18 (a lead for clustering only, not evidence of common ownership).**
  - endlessFate withdrew $11.35M gross ($10.65M net of one refunded $0.70M) from 13:28 to 14:32. mintblade withdrew $11.63M gross ($10.46M net of two refunds) from 14:42 to 15:32. GRIMDRIP deposited $9.52M from 14:48 to 16:00 ($12.40M by 20:27) and traded 15:23–16:00.
  - All three use the same withdrawal fingerprint: a $100 test, then $999,999 / $499,999 / $399,999 chunks, and an identical-amount "DEPOSIT" refund straight after some withdrawals.
  - All three withdraw through the same platform path: pUSD burned, USDC.e from 0xc417…9db1, then out to contract 0x4cd00e38…bc31. That is shared infrastructure.
  - First-hop deposit sources differ: mintblade 0xb4c3…3a41, GRIMDRIP 0x6e39…d17d. Both are EIP-7702-delegated EOAs pointing to the same delegate implementation, which is common tooling.
  - Amounts do not match one-to-one. A shared bridge, relayer or style is **not** proof of common ownership. **UNSUPPORTED** as an ownership claim.
  - [corrected by reviewer] See `WALLETS.md` §4: the reviewer found synchronized identical Belgium orders in endlessFate, LEEEROYJENKINS and FlickRaw (signed 0.4–2.1 s apart, before any of them was mined). mintblade and GRIMDRIP have no such mirrored orders with any of these accounts (`review_05_mirrored_orders.py`).
  - **Update 2026-10-17 (see `linkage.md`):** this verdict was reached before the Relay withdrawals were followed off Polygon. All three wallets' withdrawals end, directly or through one single-purpose hop, in two Etherscan-tagged *Binance Deposit* addresses: `0xb08b…317d` received from all three and `0x3319…b072` from mintblade and endlessFate. The link is now classed **STRONG PROBABILISTIC** (common destination account, not a shared key).
- **Funding (VERIFIED).**
  - 55 pUSD mints to the wallet total $9,352,937, of which $9,352,922 came via 0xb4c3…3a41.
  - Three USDC.e inflows of $1,663,369 from EOA 0xf70d…dbef each match an amount the wallet had just withdrawn. They look like refunded or bounced withdrawals (PLAUSIBLE).
  - Withdrawals total $20,154,702.
  - Net withdrawals minus deposits = $9,138,397 = cash-flow P&L $9,109,605 + rebates $28,790 (−$1.67 residual). Deposits and withdrawals are not profit and are not counted as such anywhere above.
  - Deposits arrived just in time, in about $250k chunks: 21:40–22:32 for Saudi–Uruguay and 00:34–01:05 for Iran.
  - Last activity: rebate withdrawals on 2026-07-17. No trades after 2026-06-16.

## 10. Screens (trailing 12 months, 2025-10-17 to 2026-10-17; all 5 markets resolved 2026-06-03…06-16)

| Counting rule | n | Successes | (i) exactly 5, all successful | (ii) ≥5, no observed losses |
|---|---|---|---|---|
| Per market (chosen outcome won) | 5 | 5 | **PASS** | **PASS** |
| Per distinct event (all legs won) | 3 | 3 | FAIL (n=3) | FAIL (n<5) |
| Per "made money", market level (realised > 0) | 5 | 5 (Mets +$0.19) | **PASS** | **PASS** |
| Per "made money", event level | 3 | 3 | FAIL | FAIL |
| Sensitivity: drop stakes under $100 | 4 markets / 2 events | all | FAIL | FAIL |

**Why 5-for-5 is weak evidence here:**

1. **Probability of the record under the null** (each decision wins with its entry-implied probability):

   | How the record is counted | Probability |
   |---|---|
   | Naive product of the 5 market VWAPs | 0.026 (0.028 incl. fee) |
   | Correlation-aware 5/5 per market: P(Mets) × P(draw) × P(Iran No) = 0.96 × 0.236 × 0.489 | **0.111** |
   | Per event, made money: 0.96 × 0.357 × 0.489 | **0.168** |
   | Without the test ticket | 0.175 |

   The naive product overstates the significance by about 4× because the three Saudi–Uruguay legs are one bet.

2. **Size ≠ skill.** The $9.1M depends almost entirely on Iran. P(P&L > 0) = 0.489 and P(P&L ≥ $9.11M) = 0.116 under the null, with an expected P&L of −$155k. [corrected by reviewer] Strictly, P&L ≥ the realised $9,109,605 also needs the $4.81 Mets leg (without it the total is $9,109,600), so P = 0.96 × 0.236 × 0.489 = **0.111** with these CLOB probabilities, or **0.113** with entry VWAPs as probabilities (`review_02_screens_null_capital.py`). The −$155k expected P&L uses CLOB mids; with entry VWAPs as probabilities the null mean is −$127,398, i.e. minus the fees.

3. **Selection.** A wallet is surfaced *because* it won big (leaderboard or biggest-winner lists), so the posterior has to account for the many similar wallets that lost and are not shown. In these two matches alone, 490 distinct wallets took Iran-No and 542 took Uruguay-No as takers before kick-off in the pulled tape windows. Every one of them "won".

4. **Luck pool.** If N wallets each place 5 independent bets at average entry price p̄, the expected number of perfect records is N·p̄⁵:

   | p̄ | N = 10,000 | N = 100,000 |
   |---|---|---|
   | 0.5 | 312 | 3,125 |
   | 0.6 | 778 | 7,776 |
   | 0.8 | 3,277 | 32,768 |
   | 0.95 (favourite-buyers) | 7,738 | 77,378 |

   With mintblade's own odds, 1 in 9 wallets that made the same bets would match the record. **The N values are illustrative assumptions, not a measured count of Polymarket wallets with exactly 5 decisions.** That count was not computed: CryptoHouse stops at 2026-01-05, and there is no Data API endpoint for it.

5. **Two real decisions** cannot support an estimate of edge. A binomial 2/2 is consistent with any win rate from about 0.16 to 1 (95% Clopper–Pearson lower bound ≈ 0.16).

## 11. Copy-trading implications (PLAUSIBLE; no backtest run here)

> Pointer (2026-10-17): a print-based follower reconstruction with delays of 5 s to hourly, $500–$10k sizes, fees and a zero-edge null is in `copyability.md`. It supersedes the ex-post copy test here.

- The edge, if any, sits in a few minutes before kick-off, and the wallet itself moves the price by 1–3c.
- A follower polling `/v2/activity` would see the first fill only after it printed. They would pay at least the post-impact price (Iran 0.48–0.50, Uruguay-No 0.36–0.37) plus a 0.03·p(1−p) taker fee, and would carry the same coin-flip variance.
- With 3 decisions in 4.5 months and no activity since June, the signal is also too rare to follow systematically.

## 12. Uncertainties and gaps

- Actual kick-off times are inferred from tape price jumps (±~1 min), not taken from official match clocks. Line-up release times were not verified.
- The cause of the $1,085 gap between the Data API realised P&L and the cash-flow reconstruction was not identified.
- No historical order book exists. Depth is inferred from fills (a lower bound).
- The tape pulls cover 2–3 h before the first fill (the Mets tape is complete). Earlier same-market activity by the other wallets outside these windows was checked through `/v2/trades?user=&condition=`.
- Ownership links between the three wallets are not established. The 06-18 sequence is a lead only. No inference is made about anyone's real-world identity.
- Luck-pool sizes (N) are illustrative.

## 13. Files

Scripts are in `analyses/wallets/`:
- `mintblade_01_pull.py`: Data API pulls
- `mintblade_02_markets.py`: Gamma mapping
- `mintblade_03_tapes.py`: market tapes
- `mintblade_04_prices.py`: CLOB prices-history
- `mintblade_05_analysis.py`: decision tables, episodes, capital, counterparties, impact
- `mintblade_06_onchain.py`: deposit/withdrawal on-chain checks via dRPC
- `mintblade_07_plot.py`: figure
- `mintblade_08_screens.py`: screens and null probabilities

Derived data are in `data/derived/mintblade_*.parquet`:
- fills, decisions_market, decisions_event, episodes, capital_timeline, counterparties, impact, price_windows
- prices_history, clob_prices_offsets, ksa_uru_scenarios
- tape_<cid>_{all,taker}, markets, event_markets, positions, activity*, trades*, user_pnl_all
- cashflow_transfers, ref_{GRIMDRIP,endlessFate}_{trades,activity}

Also `mintblade_small_endpoints.json` and `mintblade_screens.json`.
