# Copyability: could a follower have profited after observing mintblade, GRIMDRIP and endlessFate? (as of 2026-10-17)

Script: `analyses/wallets/copyability.py`. Outputs: `data/derived/copyability_*.parquet` and `copyability_summary.json` (file list in §9).
Inputs: the reconstructions in `mintblade.md`, `grimdrip_endlessfate.md` and `linkage.md`, with their fills, markets, tapes and price histories.

**This is an exploratory reconstruction, not a backtest on executable quotes.** Polymarket has no historical order book. CLOB `/book` is a current snapshot only (`notes/platform/data_infrastructure.md` §4). The follower's fill is therefore proxied by later taker prints on the market tape. A print shows that liquidity existed at that price; it does not show that a follower's order would have been filled there.

## 0. Bottom line

> **Reviewer findings (2026-10-17; `review_04_pit_screen.py`, `review_05_mirrored_orders.py`, checks on `copyability_signals/agg/events.parquet`). Marked [corrected by reviewer].**
> - [corrected by reviewer] **Wallet-selection look-ahead.** Every signal below is copied from the wallet's first fill onward. A follower could only have known to follow these wallets after the fact. Applied point-in-time, using only markets resolved before each entry, **none of the three wallets passed either user screen under any counting rule before any of its 21 signals.** GRIMDRIP had no history. endlessFate had 0–8 resolved markets with up to 3 losses (−$1.57M realised before KSA-URY). mintblade had only the $4.81 Mets ticket, and it passes (per market only) after its last market resolved on 06-16 03:22, never trading again. So the user's rule would have produced **0 copyable trades** from these wallets (VERIFIED). "Ex post, yes" in item 1 describes a follower with hindsight about which wallets to follow, not a follower using the screen.
> - [corrected by reviewer] **Weighting.** $2,500 per market-episode puts 43% of deployed capital ($22,907 of $53,298) on one match: KSA-URY, 9 of 21 signals made of nested legs from two linked wallets. Weighting each of the 10 events equally, the 5 s follower earns a mean of **+$332 per $1,000** (median +$397; 7 of 10 events positive; hourly mean +$279), not +$932.
> - [reviewer] **Fill-proxy span.** At the 5 s delay the $2,500 fill uses later prints spanning a median of 51 s and up to 389 s (592 s for the Mets fallback). For the 6 hourly KSA-URY copies at 22:00:00 it spans 378–483 s and crosses the inferred 22:03:36 kick-off. Prices were flat, so the effect is small, but these are not instantaneous fills.
> - [reviewer] **Checked and confirmed.** Taker BUY prints of the same token are the correct (ask) side for a follower's buy. `ex_wallet` and `buy_equiv` change pooled results by at most $3 per $1,000 at 5 s. No t_d falls after `closedTime`. The fee formula and 0.03 rate match the wallets' fills. The only look-ahead found is the wallet selection above, plus the use of goal-inferred kick-off times to label pre- or in-play states (PLAUSIBLE, ±1 min).
> - [reviewer] **Faster than any follower.** On Belgium, endlessFate, LEEEROYJENKINS and FlickRaw signed identical orders within 0.4–2.1 s, before any of them was mined (`WALLETS.md` §4). The cluster's own accounts were the "fastest followers", and a public-data follower is structurally behind them.

1. **Ex post, yes.** A follower who copied each signal within 5 s to 2 min, at $2,500 per signal, would have earned about the wallets' own return per dollar.
   - Pooled over the three wallets: **+$932 per $1,000 deployed** at a 5 s delay, against **+$906** for the wallets at their own VWAP over the same 21 signals (VERIFIED computation).
   - Pre-match prices barely moved. The follower paid on average 0.0c over the wallet's triggering fill. It paid 0.45c less than the wallet's own episode VWAP, because the wallets kept buying and moved the price up after their first fill.
2. **Ex ante, no repeatable edge is demonstrated.**
   - **87% of the pooled follower profit is one match.** Saudi Arabia v Uruguay (9 of the 21 signals) ended in a draw.
   - Excluding that match, the pooled result is +$217 per $1,000 over 9 matches. endlessFate alone is **−$264 per $1,000** over 6 matches.
   - Under a zero-edge null at the follower's own entry prices (nested legs handled jointly), P(P&L ≥ observed) is 0.11 (mintblade), 0.28 (GRIMDRIP), 0.16 (endlessFate) and 0.063 pooled. The expected P&L is −fees.
   - The pooled 0.063 overstates the evidence: the wallets were selected because they won.
3. **Closing-line value (CLV) is small.**
   - Fast copies of the first fill earned **+1.5c** CLV and an implied expected value of **+$17 per $1,000** (5 s, episode level). That came mostly from riding the wallets' own later price impact, not from information.
   - Copying every fill gave CLV +0.1c and EV **−$12 per $1,000**. An hourly monitor gave CLV −0.1c and EV **−$22 per $1,000**: the 0.03 taker fee costs about $15 per $1,000.
4. **The hourly concept is structurally too slow.**
   - World Cup matches kick off on the hour, so an hourly poll detects most pre-match entries **at the scheduled kick-off**:
     - 7 of 19 pre-match market-episodes were detected at exactly the scheduled kick-off.
     - At fill level, 82% of pre-match fills were first seen at or after kick-off.
     - 10 of the 12 market-episodes it did catch before kick-off were caught only because those two matches kicked off 3.6–4.1 min late.
   - It would be useless for in-play signals, which reprice within seconds.
   - Pre-match copying needs a detection delay of a few minutes at most: the follower's price stayed within 1c of the trigger for a median of about 20 min, and kick-off came a median 32 min after the first fill. A 30 s polling loop or RTDS (~1–2 s) is adequate. In-play reaction needs seconds.
5. **Practical limits.**
   - **Rare signals:** 10 events in 15 days, June 2026.
   - **Dormant wallets:** no trades since 2026-06-18, last activity 2026-07-17 (VERIFIED in the reconstructions), so there is nothing to follow today.
   - **Limited capacity:** the wallets took 70–100% of taker flow, and in some windows other traders printed only $0.8k–$19k before kick-off.
   - **Likely one book:** `linkage.md` rates the three wallets as strong_probabilistic members of one financial counterparty (PLAUSIBLE, not proven). Pooling them is therefore not three independent sources. The wider 11-account book netted +$14.9M, with four accounts losing $15.0M. A follower who had picked a different visible member (FlickRaw, LEEEROYJENKINS) would have lost.

## 1. Method (VERIFIED as implemented; assumptions marked)

**Signals.**
- **Fill level:** every one of the 1,871 BUY fills (mintblade 727, GRIMDRIP 670, endlessFate 474), maker and taker.
- **Market-episode level:** 21 signals, each a wallet's first fill on one outcome token within an entry episode. An episode is the fills of one wallet on one match with gaps of 10 min or less (from `ge_fills.parquet`).
- **Independent events** are matches, 10 in total. Saudi Arabia–Uruguay is one event, even though it spans 3 markets and 2 wallets.

**Detection time.** t_d = the fill's block timestamp plus a delay. The delays map onto the measured latencies in `notes/platform/data_infrastructure.md` §3 (VERIFIED there) and `alerts/README.md` §14:

| delay | what it represents |
|---|---|
| 5 s | best public detection: RTDS `activity` (~0.7–2 s after the block) or a cache-busted Data API poll (median 4.6 s, p90 6.5 s), plus an order round trip (~0.2 s) |
| 30 s | the repo's alert loop with 30 s polling (block to alert: median ~20 s, p90 ~35 s) |
| 2 min | a naive poller hitting CloudFront-cached URLs (median 112 s, max 302 s) |
| 15 min / 60 min | manual or slow-cron following |
| hourly | next top of the hour at or after timestamp + 5 s (busted-poll latency), executed at that instant, with no human delay (optimistic) |

The Data API `timestamp` is block time, which lags the off-chain match by about 2 s. A print stamped t_d therefore matched about 2 s earlier, which is small against the delay grid.

**Fill proxy.**
- Taker BUY prints of the same token with block time in [t_d, t_d + 10 min], from the full `ge_tape_taker_*` tapes. These are one row per transaction and agree with mintblade's independent tape pulls transaction for transaction; all 397 wallet taker fills appear there as BUYs of the same token (VERIFIED).
- Prints are accumulated up to the follower's size ($500, $2,500 or $10,000). Each print's notional counts as the liquidity available at its price.
- If the window holds less than the size, the remainder is priced at the CLOB `/prices-history` point at t_d plus a half-spread. The half-spread is estimated from the tape as (median ask-side print − median bid-side print)/2 within ±15 min, clipped to 0.05–2c, default 0.5c. These cases are flagged `fallback`.
- Sensitivities:
  - `ex_wallet` drops the followed wallet's own prints.
  - `buy_equiv` adds taker SELLs of the complement token, which are economically buys of this token at 1 − p.
  - Both change pooled results by no more than $5 per $1,000 at delays of 15 min or less (`copyability_agg.parquet`).

**Market state at t_d.**
- **closed** (at or after Gamma `closedTime`): not executable.
- **post_match** (at or after the event's `finishedTimestamp`). The Australia–Türkiye spread's event has none, so min(closedTime, kick-off + 2 h) is used; this affects only the order of the drawdown path.
- **in_play** (at or after kick-off): the inferred actual kick-off for Saudi Arabia–Uruguay (22:03:36) and Iran–New Zealand (01:04:03) from `mintblade.md` (PLAUSIBLE), otherwise Gamma's scheduled `gameStartTime`.
- **pre_match** otherwise.
- In-play orders also wait the market's Gamma `secondsDelay`. That is the current value; historical values are not available.

**P&L.**
- Follower net = shares × payout − size − fee, with fee = shares × rate × p × (1 − p) per print.
- **Rate 0.03** is the market's current Gamma `feeSchedule` (`sports_fees_v2`, exponent 1, takerOnly, rebateRate 0.25). It is also the rate actually charged at the time: implied 0.0300 on all 397 wallet taker fills (VERIFIED).
  - The two coincide today. However, legacy `sports_fees_v2` markets were charged 0.05 on-chain between 2026-07-11 and mid/late August 2026 (`notes/platform/fees_incentives.md`, VERIFIED there).
- **Rate 0.05** is `sports_fees_v3`, what a comparable soccer market created today pays.
- Taker rebates are ignored. A $500–$10k follower would reach at most Bronze (3%).
- **ROI** = net / (size + fee) summed over executed signals. "Per $1,000" means per $1,000 deployed.
- The wallet's own reference uses its episode VWAP for the same dollar size, with the 0.03 fee charged on all shares. That is an upper bound on its fee, since its maker fills paid none.
- **CLV** = (last `/prices-history` point at or before kick-off) − follower price, for pre-match executions only. The implied EV = shares × CLV − fee. That assumes the closing price is an unbiased probability (an assumption).

## 2. Results: market-episode signals, $2,500 per signal, fee 0.03 (mechanical rule = always copy)

`copyability_agg.parquet` (mode `primary`, rule `mechanical`). Deterioration = follower price − wallet episode VWAP, in cents; negative means the follower paid less. "vs trigger" = follower price − the wallet's first fill price.

| wallet | delay | signals / events | in-play at t_d | fallback | net P&L | per $1,000 (0.03) | per $1,000 (0.05) | det. vs VWAP | det. vs trigger | worst event | mean CLV (n) | EV per $1,000 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mintblade | own VWAP | 5 / 3 | – | – | +$16,288 | +1,285 | – | 0 | – | +$101 | – | – |
| mintblade | 5 s | 5 / 3 | 1 | 1 | +$16,651 | **+1,314** | +1,292 | −0.71 | −0.1 | +$112 | +1.3c (4) | +12 |
| mintblade | 30 s | 5 / 3 | 1 | 1 | +$16,619 | +1,311 | +1,290 | −0.61 | 0.0 | +$112 | +1.1c (4) | +10 |
| mintblade | 2 min | 5 / 3 | 1 | 1 | +$16,134 | +1,273 | +1,252 | −0.26 | +0.4 | +$111 | +0.7c (4) | −3 |
| mintblade | 15 min | 5 / 3 | 4 | 1 | +$15,314 | +1,209 | +1,189 | +1.04 | +1.7 | +$91 | +2.5c (1) | +36 |
| mintblade | 60 min | 5 / 3 | 4 (+1 post) | 3 | +$6,304 | +501 | +494 | +22.63 | +23.3 | +$2 | – | – |
| mintblade | hourly | 5 / 3 | 1 | 1 | +$15,481 | +1,222 | +1,202 | +1.42 | +2.0 | +$17 | −0.5c (4) | −29 |
| GRIMDRIP | own VWAP | 2 / 1 | – | – | +$8,606 | +1,690 | – | 0 | – | +$8,606 | – | – |
| GRIMDRIP | 5 s, 30 s, 2 min | 2 / 1 | 0 | 0 | +$9,044 | **+1,776** | +1,742 | −1.30 | 0.0 | +$9,044 | +1.5c (2) | +16 |
| GRIMDRIP | 15 min | 2 / 1 | 0 | 0 | +$8,938 | +1,755 | +1,722 | −0.80 | +0.5 | +$8,938 | +1.0c (2) | +6 |
| GRIMDRIP | 60 min | 2 / 1 | 2 | 1 | +$15,223 | +2,978 | +2,920 | −14.13 | −12.8 | +$15,223 | – | – |
| GRIMDRIP | hourly | 2 / 1 | 2 (both at the scheduled KO) | 0 | +$8,302 | +1,631 | +1,601 | +0.92 | +2.2 | +$8,302 | – | – |
| endlessFate | own VWAP | 14 / 7 | – | – | +$23,368 | +658 | – | 0 | – | −$5,104 | – | – |
| endlessFate | 5 s | 14 / 7 | 1 | 0 | +$23,987 | **+675** | +659 | −0.24 | 0.0 | −$5,105 | +1.5c (13) | +19 |
| endlessFate | 30 s | 14 / 7 | 1 | 0 | +$23,939 | +674 | +657 | −0.16 | +0.1 | −$5,104 | +1.4c (13) | +18 |
| endlessFate | 2 min | 14 / 7 | 1 | 0 | +$23,938 | +674 | +657 | −0.15 | +0.1 | −$5,104 | +1.4c (13) | +18 |
| endlessFate | 15 min | 14 / 7 | 4 | 1 | +$22,183 | +625 | +609 | +0.55 | +0.8 | −$5,104 | +1.1c (10) | +5 |
| endlessFate | 60 min | 14 / 7 | 12 | 3 | +$12,446 | +351 | +339 | +5.40 | +5.7 | −$5,115 | – | – |
| endlessFate | hourly | 14 / 7 | 6 | 0 | +$20,693 | +583 | +568 | +1.10 | +1.4 | −$5,104 | +0.1c (8) | −19 |
| **pooled** | own VWAP | 21 / 10 | – | – | +$48,262 | +906 | – | 0 | – | −$5,104 | – | – |
| **pooled** | 5 s | 21 / 10 | 2 | 1 | +$49,681 | **+932** | +913 | −0.45 | 0.0 | −$5,105 | +1.5c (19) | **+17** |
| **pooled** | 30 s | 21 / 10 | 2 | 1 | +$49,601 | +931 | +912 | −0.37 | +0.1 | −$5,104 | +1.4c (19) | +16 |
| **pooled** | 2 min | 21 / 10 | 2 | 1 | +$49,116 | +922 | +903 | −0.29 | +0.2 | −$5,104 | +1.3c (19) | +13 |
| **pooled** | 15 min | 21 / 10 | 8 | 2 | +$46,436 | +872 | +853 | +0.54 | +1.0 | −$5,104 | +1.2c (13) | +8 |
| **pooled** | 60 min | 21 / 10 | 18 (+1 post) | 7 | +$33,972 | +639 | +625 | +7.64 | +8.1 | −$5,115 | – | – |
| **pooled** | hourly | 21 / 10 | 9 (7 at the scheduled KO) | 1 | +$44,475 | **+835** | +817 | +1.16 | +1.6 | −$5,104 | −0.1c (12) | **−22** |

**Other counts and the size effect.**
- Worst cumulative drawdown, in resolution order: −$7,143 (pooled, 5 s; endlessFate alone −$7,255) to −$10,060 (pooled, 60 min). It builds up over endlessFate's first five matches: Korea–Czechia lost, Canada–Bosnia won, USA–Paraguay lost twice, Australia–Türkiye won, Belgium lost. Saudi Arabia–Uruguay then turned it positive.
- Peak concurrent exposure was 10 open signals, i.e. $25,000 at $2,500 per signal. A $25k account sized at 10% per signal would have been fully invested on 06-15.
- **Size barely matters in the print proxy.** Pooled per $1,000 at 5 s is +932 at all three sizes ($500, $2,500, $10,000). At hourly it is +832, +835 and +862; fallbacks rise from 0 to 9 at $10,000. The wallets' own large prints dominate the tape, so the proxy cannot measure depth (see §7).
- **Skip if started.** A rule that skips a pre-match signal once the match has started changes nothing at 5 s–2 min. At hourly it keeps 14 signals (6 events): +$41,921, or +1,180 per $1,000, because the at-KO losers drop out. At 60 min it keeps 4 signals: −$1,732, or −172 per $1,000.

**Excluding Saudi Arabia–Uruguay (5 s / hourly):**

| | events | per $1,000, 5 s | per $1,000, hourly |
|---|---|---|---|
| pooled | 9 | +217 | +171 |
| mintblade | 2 | +573 | +474 |
| GRIMDRIP | 1 | +1,776 | +1,631 |
| endlessFate | 6 | **−264** | −271 |

Following endlessFate outside that one draw lost money at every delay.

**Is the 60-minute GRIMDRIP result a gain? No; it is path luck.** Its +$2,978 per $1,000 comes from buying "Czechia does not win" at 0.29 after Czechia's 6' goal, then an 83' South Africa penalty. The same rule bought Belgium-win at 0.28 in play (lost) and the USA–Paraguay draw at 0.155 in play (lost). At 60 min, 18 of 21 copies are in-play bets on the then-current score, not copies of the wallets' pre-match views.

## 3. Price deterioration and the delay budget (VERIFIED computation; prints are proxies)

- **5 s to 2 min:** the follower's price equalled the trigger fill's price to within 0.2c on average. It was 0.3–1.3c below the wallet's own episode VWAP, because the wallets pushed the price up while they kept buying:
  - Czechia-No from 0.48 to a VWAP of 0.498.
  - Iran-No from 0.47 to 0.489.
  - Saudi Arabia–Uruguay draw from 0.22 to 0.228.

  Fast followers of the first fill front-run the remainder of the wallet's episode.
- **Delay budget** (`copyability_latency_budget.parquet`, $2,500, grid 0 s–2 h, 19 pre-match market-episodes):

| measure | value |
|---|---|
| first fill to kick-off | median 31.8 min (range 3.0–68.7) |
| delay until the price is >1c worse than the trigger | median 20 min (IQR 10–30); never in 2 cases |
| delay until >2c worse | median 45 min; never in 4 cases |
| cases where the 1c threshold was crossed before kick-off | 12 of 19 |
| shortest budgets | mintblade's Saudi Arabia–Uruguay legs (5.7–8.8 min before kick-off; draw >1c after 2 min, spread after 7.5 min); Australia–Türkiye (3.0 min before kick-off) |

- **15 min:** pooled mean +0.54c versus VWAP (+1.0c versus trigger). Four market-episodes had already entered play. Australia–Türkiye moved +4.7c, and mintblade's Saudi Arabia +1.5 leg +4.2c.
- **60 min and hourly:** see §2 and §5. At 60 min the mean is +7.6c (vs VWAP), path-dependent and in-play. At hourly it is +1.2c, from prices at or near kick-off.

### Per-signal prices ($2,500 follower VWAP, primary prints)

"at sched. KO" means t_d equals the scheduled kick-off to the second.

| wallet | match, episode, leg | first fill UTC | min to KO | trigger | wallet VWAP | 5 s | 2 min | 15 min | 60 min | hourly (t_d, state) | won |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mintblade | NYM–SEA, Mets ML | 06-03 21:18:42 | −98.7 (in-play) | 0.960 | 0.9600 | 0.956 FB | 0.956 FB | 0.964 FB | 0.999 post | 0.993 FB (22:00 in-play) | Y |
| endlessFate | KOR–CZE, Korea win No | 06-12 01:53:30 | 6.5 | 0.630 | 0.6300 | 0.630 | 0.630 | 0.620 | 0.680 | 0.630 (02:00 at sched. KO) | N |
| endlessFate | CAN–BIH, Bosnia win No | 06-12 19:58:12 | −58.2 (in-play) | 0.570 | 0.5715 | 0.570 | 0.570 | 0.570 | 0.999 FB | 0.570 (20:00 in-play) | Y |
| endlessFate | USA–PAR E1, draw Yes | 06-12 23:51:16 | 68.7 | 0.300 | 0.3000 | 0.300 | 0.300 | 0.300 | 0.310 | 0.300 (00:00 pre) | N |
| endlessFate | USA–PAR E2, draw Yes | 06-13 00:28:12 | 31.8 | 0.300 | 0.3098 | 0.306 | 0.308 | 0.310 | 0.155 | 0.310 (01:00 at sched. KO) | N |
| endlessFate | AUS–TUR, spread Australia | 06-14 03:56:58 | 3.0 | 0.700 | 0.7000 | 0.700 | 0.700 | 0.747 | 0.950 | 0.693 (04:00 at sched. KO) | Y |
| endlessFate | BEL–EGY, Belgium win Yes | 06-15 18:50:09 | 9.8 | 0.660 | 0.6600 | 0.660 | 0.660 | 0.650 | 0.280 | 0.661 (19:00 at sched. KO) | N |
| endlessFate | KSA–URY E1, spread Saudi +1.5 | 06-15 21:07:58 | 55.6 | 0.590 | 0.5900 | 0.590 | 0.590 | 0.600 | 0.638 | 0.630 (22:00 pre) | Y |
| endlessFate | KSA–URY E1, draw Yes | 06-15 21:09:07 | 54.5 | 0.220 | 0.2276 | 0.220 | 0.220 | 0.240 | 0.250 | 0.250 (22:00 pre) | Y |
| endlessFate | KSA–URY E1, Uruguay win No | 06-15 21:19:51 | 43.8 | 0.340 | 0.3400 | 0.340 | 0.340 | 0.350 | 0.420 | 0.370 (22:00 pre) | Y |
| endlessFate | KSA–URY E2, draw Yes | 06-15 21:34:07 | 29.5 | 0.240 | 0.2400 | 0.240 | 0.240 | 0.240 | 0.330 | 0.250 (22:00 pre) | Y |
| endlessFate | KSA–URY E2, Uruguay win No | 06-15 21:35:31 | 28.1 | 0.350 | 0.3577 | 0.350 | 0.350 | 0.360 | 0.460 | 0.370 (22:00 pre) | Y |
| endlessFate | KSA–URY E2, spread Saudi +1.5 | 06-15 21:37:03 | 26.6 | 0.610 | 0.6182 | 0.610 | 0.610 | 0.620 | 0.773 | 0.630 (22:00 pre) | Y |
| mintblade | KSA–URY, Uruguay win No | 06-15 21:54:45 | 8.8 | 0.360 | 0.3652 | 0.360 | 0.362 | 0.368 | 0.769 FB | 0.370 (22:00 pre) | Y |
| mintblade | KSA–URY, spread Saudi +1.5 | 06-15 21:56:04 | 7.5 | 0.620 | 0.6267 | 0.620 | 0.630 | 0.662 | 0.955 FB | 0.630 (22:00 pre) | Y |
| mintblade | KSA–URY, draw Yes | 06-15 21:57:52 | 5.7 | 0.240 | 0.2400 | 0.240 | 0.250 | 0.260 | 0.350 | 0.250 (22:00 pre) | Y |
| mintblade | IRN–NZL, Iran win No | 06-16 00:17:22 | 46.7 | 0.470 | 0.4894 | 0.470 | 0.470 | 0.480 | 0.740 | 0.510 (01:00 pre) | Y |
| endlessFate | UZB–COL E1, Colombia win Yes | 06-18 00:51:58 | 68.0 | 0.710 | 0.7100 | 0.710 | 0.720 | 0.730 | 0.750 | 0.720 (01:00 pre) | Y |
| endlessFate | UZB–COL E2, Colombia win Yes | 06-18 01:08:49 | 51.2 | 0.730 | 0.7348 | 0.730 | 0.730 | 0.730 | 0.750 | 0.760 (02:00 at sched. KO) | Y |
| GRIMDRIP | CZE–RSA, Czechia win No | 06-18 15:23:20 | 36.7 | 0.480 | 0.4979 | 0.480 | 0.480 | 0.490 | 0.290 | 0.510 (16:00 at sched. KO) | Y |
| GRIMDRIP | CZE–RSA, draw Yes | 06-18 15:26:13 | 33.8 | 0.280 | 0.2882 | 0.280 | 0.280 | 0.280 | 0.213 FB | 0.294 (16:00 at sched. KO) | Y |

FB = fallback (prints under $2,500 within 10 min, remainder at `/prices-history` + half-spread); post = after the match finished. "Min to KO" uses the inferred actual kick-off for KSA–URY and IRN–NZL and the scheduled one elsewhere.

## 4. Fill-level following ($2,500 per fill, equal dollars per fill; `copyability_fill_agg.parquet`)

| wallet | delay | fills | in-play at t_d | mean / median / p90 det. (c) | taker / maker fills, mean det. (c) | per $1,000, fill-weighted | per $1,000, event-weighted | wallet's own per $1,000 | CLV (c) | EV per $1,000 |
|---|---|---|---|---|---|---|---|---|---|---|
| pooled | 5 s | 1,871 | 37 | +0.64 / +0.96 / +1.00 | +0.01 / +0.81 | +811 | +222 | +831 | +0.12 | −12 |
| pooled | 30 s | 1,871 | 117 | +0.55 / +0.96 / +1.00 | +0.06 / +0.68 | +814 | +222 | +831 | +0.18 | −11 |
| pooled | 2 min | 1,871 | 539 | +0.20 / +0.50 / +1.00 | +0.12 / +0.22 | +828 | +225 | +831 | +0.22 | −10 |
| pooled | 15 min | 1,871 | 1,488 | +0.08 / +2.00 / +23.5 | −1.43 / +0.49 | +1,150 | +319 | +831 | +0.10 | −7 |
| pooled | 60 min | 1,871 | 1,855 (+10 post) | −1.03 / +10.0 / +16.0 | +4.52 / −2.53 | +1,182 | +116 | +831 | – | – |
| pooled | hourly | 1,871 | 1,529 (+7 post) | +3.23 / +1.00 / +10.0 | +2.14 / +3.52 | +737 | +140 | +831 | −0.44 | −25 |

Per wallet at 5 s, fill-weighted per $1,000 against the wallet's own:

| wallet | follower | wallet |
|---|---|---|
| mintblade | +1,008 | +1,023 |
| GRIMDRIP | +982 | +1,014 |
| endlessFate | +264 | +277 |

**What drives the fill-level numbers.**
- **Maker fills.** 1,474 of 1,871 fills are maker fills: resting bids that were hit. A follower who sees one has to lift the ask, about 1 tick-cent higher. That is where the +0.8–1.0c on maker fills comes from; copying taker fills costs ~0c at 5 s.
- **Fills near kick-off.** Many fills sit in the last minutes before kick-off:
  - 38% of GRIMDRIP's fills and 35% of mintblade's were within 2 min of kick-off.
  - GRIMDRIP's median fill came 2.6 min before kick-off, mintblade's 3.4 min, endlessFate's 16.8 min.
  - So already at 2 min, 539 copies land in play. At 15 min, mintblade's Iran-No copies land after New Zealand's 7' goal: +19c on average for the Iran fills (+18c over all of mintblade's fills), which costs mintblade followers half their return (+532 per $1,000).
- **Fill weighting.** Fill-weighted results are dominated by the three matches with hundreds of fills (Iran 674, Czechia 650, Colombia 352). Event-weighted, the pooled 5 s figure is +222 per $1,000.

## 5. Luck versus edge: what the follower actually bought

- **Outcome luck dominates (VERIFIED computation; the null model is an assumption).** Zero-edge null with each match's outcome drawn from the follower's own entry prices, nested legs mapped to explicit match states, 200k draws (`copyability_null.parquet`):

| | 5 s P(≥ observed) | 5 s P(P&L > 0) | 5 s null mean / SD | hourly P(≥ observed) |
|---|---|---|---|---|
| mintblade | 0.109 | 0.36 | −$175 / $8,934 | 0.128 |
| GRIMDRIP | 0.282 | 0.48 | −$68 / $6,042 | 0.296 |
| endlessFate | 0.159 | 0.40 | −$517 / $19,789 | 0.181 |
| pooled | **0.063** | 0.38 | −$859 / $28,370 | 0.074 |

- **Cross-check against the reconstructions.** At the wallets' own VWAPs, the same machinery gives 0.114 / 0.290 / 0.162. The reconstructions had 0.111–0.116 (mintblade), 0.288 (GRIMDRIP) and 0.168 (endlessFate) (VERIFIED consistency).
- **Selection bias.** These wallets were chosen because they made millions, so any p-value computed on the same sample is optimistic (`grimdrip_endlessfate.md` §8: thousands of wallets pass 5-for-5 screens by luck each year, PLAUSIBLE).
- **Concentration.** One draw (Saudi Arabia–Uruguay 1-1) supplies 87% of the 5 s pooled profit ($43,098 of $49,681) and 9 of the 21 signals. Those 9 signals came from endlessFate (6) and mintblade (3) within 53 minutes (21:07:58–22:00:01); GRIMDRIP did not trade the match. `linkage.md` places both accounts in one probable cluster (PLAUSIBLE).
- **CLV.**
  - The only measurable non-luck component is +1.3 to +1.5c of CLV for copies of the first fill within 2 min. That is about +$13 to +$17 per $1,000 after fees.
  - It comes from the wallets' own continued buying, which lifted the price after the copy, partly reverting by kick-off. The wallets themselves paid that impact. Their own CLV at VWAP, per pre-match market-episode, was median +0.5c, mean +1.0c (range −0.5 to +4.5c), which is below the fast follower's +1.5c.
  - Copying every fill or copying hourly has CLV of about +0.2c or less and negative EV after the 1.5% fee drag.
- **"Outcome won" is not "trader made money".**
  - 17 of 21 market-episode signals won, but the follower made money on only 7 of 10 events (VERIFIED).
  - endlessFate's Saudi Arabia–Uruguay legs, mintblade's 3 legs and GRIMDRIP's 2 legs are nested bets on single matches. Counted per event, a follower of endlessFate made money on 4 of 7 matches.

## 6. Is hourly monitoring too slow? By signal type

**Detection delay of an hourly poll** (`copyability_hourly.parquet`):

| | median delay | other quantiles | caught after kick-off |
|---|---|---|---|
| market-episodes (21) | 24.5 min | min 1.8, p25 6.5, p75 40.2, max 52.0 min | 7 of 19 pre-match signals, all at exactly the scheduled kick-off (16:00, 19:00, 02:00, 04:00, 01:00) |
| fills (1,871) | 10.0 min | p10 0.6, p90 58.0 min | 1,521 of 1,856 pre-match fills (82%) at or after kick-off |

**Pre-match positioning** (19 of 21 market-episodes; 1,856 fills).
- The entries came 3–69 min before kick-off (median 32 min), often finishing seconds before it. All of these matches were scheduled on the hour, so an hourly poll at :00 lands on the kick-off.
- Of the 12 market-episodes it caught before kick-off:
  - 10 (Saudi Arabia–Uruguay ×9, Iran–New Zealand) were caught only because the actual kick-off was inferred 3.6–4.1 min after the scheduled time (PLAUSIBLE). That left a manual follower about 3–4 minutes.
  - The other 2 (USA–Paraguay E1, Colombia E1) began more than an hour before kick-off.
- The realised hourly P&L (+$835 per $1,000) stays positive only because these outcomes won and prices at kick-off were close to pre-match. Hourly CLV is −0.1c and EV is −$22 per $1,000, a zero-edge bet minus fees.
- **Needed latency:** keep within 1c of the trigger and enter before kick-off. That needs a detection-to-order delay of at most about 2–5 min for the shortest windows: mintblade's Saudi Arabia–Uruguay legs 5.7–8.8 min before kick-off, Australia–Türkiye 3.0 min, Korea–Czechia 6.5 min. About 15–20 min is enough for the median signal.
- The repo's 30 s polling alert loop (median ~20 s to alert) is sufficient. A 5-min cron is borderline. Hourly is not.

**In-play reaction** (2 market-episodes: Canada–Bosnia at half-time, the Mets ticket; 15 fills).
- In-play prices jump on goals within seconds. A soccer half is 45 min, and Canada's equaliser came about 33 min after endlessFate's last Bosnia fill.
- Hourly detection (20:00 / 22:00) happened to give an unchanged price for Bosnia-No (0.570). For the Mets it gave 0.993, 18 min before Gamma's `finishedTimestamp`. Neither tells us anything about edge.
- Under 60 min, Canada–Bosnia was copied 2 s before Gamma's `finishedTimestamp`, at 0.999, and the Mets after the game ended.
- An in-play copier needs RTDS-level latency (~1–2 s) plus `secondsDelay` (1 s on Korea–Czechia, Canada–Bosnia and USA–Paraguay today). Even then, the 2 s head start of the anonymous CLOB print (`data_infrastructure.md` §3.4) means faster book-watchers react first.
- With only 2 in-play signals, whether these wallets have in-play skill at all is UNSUPPORTED.

## 7. Capacity, market state and execution caveats

**Capacity** (`copyability_capacity.parquet`).
- Taker BUY notional by everyone except the followed wallet, from its first fill to kick-off (capped at 60 min):

| signal | other traders' buy notional | window |
|---|---|---|
| Australia–Türkiye | $800 | 3 min |
| mintblade's three Saudi Arabia–Uruguay legs | $5.7k–$18.8k | 6–9 min |
| Iran–New Zealand | $230k | 47 min (mintblade itself bought $6.64M) |
| Czechia No / draw | $383k / $63k | 37 / 34 min |
| endlessFate's Saudi Arabia +1.5 and Uruguay-No legs, and Belgium | $1.0M–$1.8M | |
| endlessFate's Saudi Arabia–Uruguay draw legs | $138k–$179k | |

- Without the wallet's own flow, $10,000 per signal is plausible in most windows but not all. Matching the wallets' size is impossible: they were 70–100% of taker flow and moved prices 0–4c.
- The print proxy has a hard limit: it cannot show the depth a follower's order would have met, and it treats each print's notional as fully available.

**Market state (VERIFIED from Gamma fields and the tape).**
- No t_d fell at or after `closedTime` at any delay, so every copy was executable.
- `clearBookOnStart=true` on all 13 markets: resting orders are cancelled at kick-off, so a follower using limit orders placed before kick-off loses them at the start.
- The largest gap between consecutive prints within [kick-off − 5 min, kick-off + 15 min] was 5–42 s in the 12 football markets and 102 s in the MLB market. No extended suspension is visible around kick-off.
- In-play pauses on goals cannot be observed from prints alone. `secondsDelay` is the current Gamma value; values in June 2026 are not available.
- At 60 min, 10 fills and 1 market-episode landed after the match had finished, at about 0.999.

**Other execution caveats.**
- `/prices-history` points (used for fallbacks and CLV) are a trade/mid series, not quotes.
- Kick-offs for Saudi Arabia–Uruguay and Iran–New Zealand are inferred from tape jumps (±~1 min). Others are scheduled times; actual kick-offs may have been 1–4 min later. That makes the 7 "at scheduled KO" hourly copies borderline pre-match rather than clearly in-play.
- Follower orders on the same token at the same time (e.g. the 9 pooled Saudi Arabia–Uruguay copies at 22:00) are priced independently; their combined impact is ignored.

## 8. Uncertainties and gaps

- **No historical order book.** All follower prices are print-based proxies. Real fills could be better (resting depth beyond the print) or worse (queue competition, the follower's own impact). The `ex_wallet` and `buy_equiv` sensitivities move results by ≤ 1%, which does not remove this limitation.
- **Tiny sample.** 21 market-episodes on 10 matches in 15 days; the exact numbers are reported without significance claims. The pooled sample counts one probable cluster (`linkage.md`, PLAUSIBLE) as three sources.
- **Fees.** The 0.03 versus 0.05 comparison is mechanical. The "current" rate for these legacy markets is 0.03 again, but the platform changed sports fees three times in 2026, so the rate a future follower pays is uncertain. Rebates were ignored.
- **Latency.** The delays come from one day's measurements (2026-10-17) on other markets (`data_infrastructure.md` §3); peak World Cup traffic in June was not measured.
- **CLV assumption.** CLV-implied EV assumes the closing `/prices-history` point is an unbiased probability. The zero-edge null assumes independent matches and uses the follower's own prices as probabilities; within-match state probabilities are backed out of leg prices and clipped at 0.5%.
- **Dormancy.** The wallets have not traded since 2026-06-18, so no out-of-sample test was possible. Any statement about future copyability is UNSUPPORTED.
- **No identity inference.** No identity inference is made. Performance is not treated as evidence of private information; timing is described only relative to kick-off and public goals.

## 9. Files

**Script.** `analyses/wallets/copyability.py`. It runs in about 30 s from cached derived data; it calls `/prices-history` with `cache=True` only if a point is missing.

**Outputs** (`data/derived/`):

| file | contents |
|---|---|
| `copyability_signals.parquet` | one row per signal × delay × size × print mode: t_d, state, follower price, fallback, fees at 0.03 and 0.05, net, wallet reference, CLV, EV |
| `copyability_agg.parquet` | per wallet and pooled × delay × size × mode × rule (mechanical / pre_match_only) |
| `copyability_events.parquet` | per match P&L |
| `copyability_fill_agg.parquet` | fill-level aggregates |
| `copyability_hourly.parquet` | hourly-monitor detection times and states |
| `copyability_curve.parquet` | fine delay grid, 0 s–2 h |
| `copyability_latency_budget.parquet` | per-signal delay budgets |
| `copyability_null.parquet` | zero-edge null results |
| `copyability_capacity.parquet` | other traders' buy notional per signal window |
| `copyability_ko_gaps.parquet` | print gaps around kick-off |
| `copyability_summary.json` | fee check, kick-offs used, fallback shares |

**Superseded.** `ge_copy_lag.parquet` (a last-trade-price copy test in `grimdrip_endlessfate.md` §10) is superseded by this analysis; its conclusion, that a lag of 1–15 min matched the wallets' returns ex post, still holds.
