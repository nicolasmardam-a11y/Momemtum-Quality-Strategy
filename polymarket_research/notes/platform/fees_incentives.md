# Fees, rebates and incentives on Polymarket (current regime and history)

As of 2026-10-17. Scope: the international Polymarket CLOB (Protocol V2, pUSD collateral) documented at
docs.polymarket.com. Polymarket US (the separate CFTC-regulated app) has its own schedule and is out of scope
(see [ingame.com review](https://www.ingame.com/polymarket-review/), secondary).

Labels: **VERIFIED** = I checked it in official docs and/or live API / on-chain data on 2026-10-17.
**PLAUSIBLE** = consistent with the evidence but not directly checked. **SECONDARY** = news or blog only.
**UNSUPPORTED** = claimed somewhere, no support found.

Machine-readable companion: `notes/platform/fee_schedule_2026-10-17.yaml`.
Scripts: `analyses/fees/` (collect_open_market_fees.py, closed_market_fee_history.py, onchain_fee_sampler.py,
lp_rewards_snapshot.py, cost_table.py, keccak.py). Derived data: `data/derived/open_market_fees_2026-10-17.parquet`,
`closed_market_fees_sample.parquet`, `onchain_fee_samples.parquet`, `lp_rewards_current_2026-10-17.parquet`,
`cost_table_2026-10-17.csv`. Raw responses: `data/raw/{gamma,clob,data-api,polygon-archive,bridge}/`.

---

## 0. Summary for decisions

1. **Formula (VERIFIED on-chain).** Takers pay `fee = shares × rate × p × (1 − p)` in pUSD. Makers pay nothing.
   I decoded 20,740 V2 `OrderFilled` taker fills at 21 dates from 2026-04-29 to 2026-10-16. In every
   (fee type, date) cell the modal implied rate equals a documented or Gamma rate. The docs formula is what the
   exchange charges. ([docs/trading/fees](https://docs.polymarket.com/trading/fees.md))
2. **Who pays today.** 99.6% of the 288,003 open markets have fees, and they carry 93.1% of Gamma 24h volume.
   Fee-free markets (1,169) are almost all geopolitics/world. **Tags do not set the fee class.** Only 29% of
   markets tagged `geopolitics` are fee-free. For example, "Xi Jinping out before 2027?" is `politics_fees` (0.04).
   Always read the per-market `feeSchedule`.
3. **Sports is not one rate.** Sports is 0.05 / 15% maker rebate (`sports_fees_v3`, 215,626 markets) for markets
   created from 2026-07-11. Two exceptions charge 0.03, and neither is documented:
   - `sports_fees_nfl_cfb_oct26`: 0.03 / 15%, 38,967 NFL and college-football markets created from 2026-09-04,
     charged 0.03 on-chain on 2026-10-16.
   - `sports_fees_v2`: 0.03 / 25%, 2,460 legacy markets created before 2026-07-10.
4. **Exponent.** Exactly one open market has `exponent != 1`. It is a stale 5-minute XRP market from
   2026-02-24 with legacy params `crypto_15_min` (rate 0.25, exponent 2).
5. **The regime changed often in 2026.** The changes were: fee-free → crypto-only (Jan–Mar) → all categories
   (2026-03-30) → formula change (~03-31/04-01) → V2/pUSD (04-28) → crypto 0.072→0.070 (between 05-04 and
   05-07, on-chain) → taker rebates (05-28) → sports 0.03→0.05 for **all** sports markets (between 07-10 02:00
   and 07-11 02:00 UTC, on-chain) → legacy `sports_fees_v2` markets back at 0.03 between 08-15 20:00 and 08-25 20:00
   UTC **[corrected by verifier 2026-10-17: was "by 09-03"; on-chain 0.05 on 08-05 and 08-15, 0.03 on 08-25]** →
   NFL/CFB 0.03 (09-04).
   **Gamma's feeSchedule on a closed market is what Gamma shows today, not necessarily what was charged.**
   - Crypto markets traded on 2026-04-29 at 0.072 now show 0.07.
   - `sports_fees_v2` markets were charged 0.05 from 07-11 to at least 08-15 but show 0.03 **[corrected by verifier
     2026-10-17: was "at least 07-28"; 690/690 fills at 0.05 on 07-15 20:00, 243/243 on 08-15 20:00]**.
   - Backtests must use on-chain `OrderFilled.fee`, or the regime table in section 2, not today's Gamma field.
6. **The taker rebate is a share of fees paid (VERIFIED).** One wallet's 2026-07-08 TAKER_REBATE of $18,721.49
   equals 18% (Gold) × its 2026-06-16 taker fees of $104,008.29, to the cent. Tier thresholds use weighted
   volume `notional × (1 − p) × category weight`. That rewards buying cheap outcomes. Buying favorites at 0.9
   earns 0.1 wV per $1 of notional.
7. **Round-trip taker costs are large away from 0.5.** At tier 0 with a 1¢ spread, buying at 0.30 and selling
   later at an unchanged mid costs 3.10¢ in sports (10.3% of capital). The same trade costs 3.94¢ in crypto
   (13.1%) and 1.00¢ in geopolitics (3.3%). Buy-and-hold to resolution costs one fee: at 0.90 in sports, 0.45¢
   (0.50%). Obsidian (50% rebate) halves the fee part, not the spread.
8. **Incentives.**
   - Liquidity rewards: $289,412/day configured across 14,608 markets on 2026-10-17. Median $3/day per market,
     max $8,850/day (EPL props).
   - Maker rebates: 15–25% of the fees in the same market.
   - Holding rewards: 339 markets, paid daily as `YIELD`. The stated rate conflicts: 4.00% in the docs, 3.25% in
     the help center. One holder's payouts imply about 1.75% (unresolved).
   - All programs are discretionary and can change without notice.
   - Two temporary programs have ended: the Crypto TWAP $1M (August 2026) and March Madness $2M+.

---

## 1. Current taker fee schedule and how a market's fee is exposed

### 1.1 Formula and documented category rates (VERIFIED)

`fee = C × feeRate × p × (1 − p)`. C is shares and p is the trade price. The fee is rounded to 5 dp and charged
to takers only. Sources: [docs/trading/fees](https://docs.polymarket.com/trading/fees.md) and
[docs/programs/builders/fees](https://docs.polymarket.com/programs/builders/fees.md) ("platform fees are currently
taker-only").

- **Buys:** the fee is charged on top of the notional. A market BUY's `amount` is pre-fee; use `maxSpend` for an
  all-in cap ([docs/trading/place-orders](https://docs.polymarket.com/trading/place-orders.md)).
- **Sells:** the fee is deducted from proceeds. `FeeExceedsProceeds` in
  [ctf-exchange-v2 Trading.sol](https://github.com/Polymarket/ctf-exchange-v2).
- **Activity rows:** a TRADE row's `usdc_size` includes the fee. For example, 200,000 shares × 0.50 shows as
  $101,500 = $100,000 + $1,500, which is rate 0.03 in a `sports_fees_v2` market. Implied fees from
  `/v2/activity` summed exactly to `/v2/user-stats` `fees_paid` for two wallets: $127,397.56 and $160,131.17.

| Category | Taker rate | Fee per share at p=0.5 | Fee as % of notional at p | Maker rebate share | Taker wV weight |
|---|---|---|---|---|---|
| Crypto | 0.07 | 1.75¢ | 7.0%×(1−p) | 20% | 2.3 |
| Sports | 0.05 (see exceptions) | 1.25¢ | 5.0%×(1−p) | 15% | 1.0 |
| Finance, Politics, Mentions, Tech | 0.04 | 1.00¢ | 4.0%×(1−p) | 25% | 1.3 |
| Economics, Culture, Weather, Other | 0.05 | 1.25¢ | 5.0%×(1−p) | 25% | 1.7 |
| Geopolitics / world events | 0 | 0 | 0 | — | 0 |

Sources: [fees](https://docs.polymarket.com/trading/fees.md), [maker-rebates](https://docs.polymarket.com/programs/maker-rebates.md),
[taker-rebates](https://docs.polymarket.com/programs/taker-rebates.md).

The fee in $ is symmetric in p and 1−p. As a fraction of capital it is `rate × (1 − p)`, so buying a 5¢
outcome in crypto costs 6.65% of capital and buying a 95¢ outcome costs 0.35%.

### 1.2 Where a market's fee parameters live (VERIFIED, live calls 2026-10-17)

| Source | Field(s) | What it means |
|---|---|---|
| Gamma `/markets/*` | `feesEnabled`, `feeType` (e.g. `sports_fees_v3`), `feeSchedule {rate, exponent, takerOnly, rebateRate}` | Authoritative per-market config *now*. `rebateRate` = maker rebate as a fraction of taker fees ([market-details](https://docs.polymarket.com/market-data/market-details.md)). Changelog 2026-03-31: "Fees should now be calculated using the feeSchedule object" ([changelog](https://docs.polymarket.com/changelog/predictions.md)) |
| Gamma | `makerBaseFee`, `takerBaseFee` | **1000 on every fee-enabled market, null on fee-free.** A legacy V1 order-signing parameter (bps), **not** the charged rate. Makers pay 0 |
| CLOB `GET /clob-markets/{condition_id}` | `fd {r, e, to}`, `mbf`, `tbf`, `mos`, `mts`, `itode`, `gst` | `fd.r` / `fd.e` match Gamma `rate` / `exponent` on all 9 markets I tested. `mbf`/`tbf` = 1000 ([spec](https://docs.polymarket.com/api-reference/markets/get-clob-market-info.md)) |
| CLOB `GET /fee-rate?token_id=` | `base_fee` | Returned **1000** for every fee-enabled market tested and **0** for a fee-free one. A flag or cap, not the rate. The doc example shows 30 bps ([spec](https://docs.polymarket.com/api-reference/market-data/get-fee-rate.md)) |
| Exchange contract | `maxFeeRateBps` default 500 (5% of cash value) | On-chain sanity cap only. Fees are computed off-chain by the operator and passed in at match time ([ctf-exchange-v2 Fees.sol](https://github.com/Polymarket/ctf-exchange-v2)) |
| On-chain `OrderFilled` | `fee` (6-dp collateral) | Ground truth for what a fill paid. The taker-order event is the one whose `taker` = exchange contract ([onchain-position-data](https://docs.polymarket.com/resources/onchain-position-data.md)) |

### 1.3 Census of all open markets (VERIFIED, Gamma `markets/keyset?closed=false&include_tag=true`, 2026-10-17T15:00Z)

288,003 open markets. `active=true` on all of them. Note that `/markets/keyset` has no `active` parameter in the
[Gamma spec](https://docs.polymarket.com/api-reference.txt), so I did not pass it. `feesEnabled=true` on 286,834
(99.59%). Gamma 24h volume totalled $54.1M, and 93.1% of it was in fee-enabled markets.

| feeType | rate | exp | rebateRate | open markets | % of markets | % of 24h volume | created (first → last) |
|---|---|---|---|---|---|---|---|
| sports_fees_v3 | 0.05 | 1 | 0.15 | 215,626 | 74.9% | 45.1% | 2026-07-11 → today |
| politics_fees | 0.04 | 1 | 0.25 | 11,481 | 4.0% | 13.3% | 2025-07 → today |
| culture_fees | 0.05 | 1 | 0.25 | 2,808 | 1.0% | 12.8% | 2025-11 → today |
| *(none: feesEnabled=false)* | 0 | – | – | 1,169 | 0.4% | 6.9% | 2025-07 → today |
| sports_fees_nfl_cfb_oct26 | 0.03 | 1 | 0.15 | 38,967 | 13.5% | 5.1% | 2026-09-04 → today |
| crypto_fees_v2 | 0.07 | 1 | 0.20 | 5,891 | 2.0% | 4.7% | 2025-08 → today |
| sports_fees_v2 | 0.03 | 1 | 0.25 | 2,460 | 0.9% | 3.6% | 2025-09 → **2026-07-08** |
| weather_fees | 0.05 | 1 | 0.25 | 3,600 | 1.3% | 3.4% | |
| economics_fees | 0.05 | 1 | 0.25 | 999 | 0.3% | 2.9% | |
| finance_prices_fees | 0.04 | 1 | 0.25 | 2,730 | 0.9% | 1.4% | |
| tech_fees | 0.04 | 1 | 0.25 | 1,936 | 0.7% | 0.6% | |
| general_fees | 0.05 | 1 | 0.25 | 118 | 0.04% | 0.03% | |
| mentions_fees | 0.04 | 1 | 0.25 | 185 | 0.06% | 0.03% | |
| zero_fees | 0.00 | 1 | 0.00 | 32 | 0.01% | 0.01% | album-release, a few politics/CFB |
| crypto_15_min | **0.25** | **2** | 0.20 | 1 | – | 0 | 2026-02-23 (stale XRP 5-min market) |

Every market has `takerOnly=true`.

**Exponent check.** 286,833 markets have exponent 1. One has exponent 2: `xrp-updown-5m-1771916400`, end date
2026-02-24. It is still flagged open and still shows `fd {r:0.25, e:2}` on `/clob-markets`.

**By tag** (a market can carry several tags; columns are feeType counts):

| tag | open markets | % fee-enabled | dominant feeTypes |
|---|---|---|---|
| sports | 257,024 | 100.0% | v3 215,543; nfl_cfb_oct26 38,967; v2 2,393; culture 54 |
| soccer | 192,816 | 100.0% | v3 192,282; v2 516 |
| nfl | 20,308 | 100.0% | nfl_cfb_oct26 14,702; v3 5,390; v2 179 |
| esports | 3,404 | 100.0% | v3 2,596; v2 793 |
| crypto | 6,002 | 100.0% | crypto_fees_v2 5,888; finance 39; mentions 32 |
| politics | 12,626 | 95.1% | politics 11,390; none 618; culture 389 |
| elections | 10,046 | 99.6% | politics 10,001 |
| **geopolitics** | 1,487 | **29.3%** | none 1,052; **politics 394**; culture 16 |
| world | 1,187 | 76.7% | politics 798; none 276 |
| iran | 467 | 18.8% | none 379 |
| finance | 3,203 | 99.1% | finance 2,698; economics 319 |
| economy | 1,053 | 97.8% | economics 785; finance 115; general 71 |
| pop-culture | 2,756 | 99.7% | culture 2,550 |
| weather | 3,638 | 99.4% | weather 3,598 |
| tech / ai | 2,655 / 2,151 | 99.2% / 99.2% | tech 1,883 / 1,784 |

Source data: `data/derived/open_market_fees_2026-10-17.parquet`.

### 1.4 On-chain verification of charged rates (VERIFIED)

Method (`analyses/fees/onchain_fee_sampler.py`):
- Sampled 21 dates. Pull `OrderFilled` logs from the CTF Exchange V2 (`0xE111…996B`), the Neg Risk CTF Exchange V2
  (`0xe222…0F59`) and the Poly-v2 ExchangeV3 (`0xe333…00Aa`). Addresses are from
  [contracts](https://docs.polymarket.com/resources/contracts.md).
- Read 10–40-block windows from the public archive RPC `polygon.drpc.org`. publicnode refuses archive reads.
- Keep taker fills only, and compute `fee / (shares × p × (1 − p))`.
- Map each token to its market with Data API `/v2/tokens`, then Gamma `/markets/slug`.
- Restrict to 0.02 < p < 0.98 and shares ≥ 5, which leaves 13,433 fills.
- Additional dates 07-11 02h, 07-18, 07-28 and 08-08 are summarised in the bullets below.

The table shows the modal implied rate. Fill counts per cell range from 1 to 1,111.

| feeType (Gamma today) | 04-29 | 05-01 | 05-04 | 05-07 | 05-10 | 05-29 | 06-20 | 07-08 | 07-09 22h | 07-10 02h | 07-12 | 08-20 | 09-03 | 09-10 | 09-20 | 10-16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| crypto_fees_v2 (0.07) | **0.072** | **0.072** | **0.072** | 0.070 | 0.070 | 0.070 | 0.070 | 0.070 | 0.070 | 0.070 | 0.070 | 0.070 | 0.070 | 0.070 | 0.070 | 0.070 |
| sports_fees_v2 (0.03) | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | **0.05** | – | 0.03 | 0.03 | 0.03 | 0.03 |
| sports_fees_v3 (0.05) | – | – | – | – | – | – | – | – | – | – | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 |
| sports_fees_nfl_cfb_oct26 (0.03) | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | 0.03 |
| politics_fees (0.04) | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | – | 0.04 | 0.04 | 0.04* | 0.04 | 0.04 | 0.04 |
| finance / tech / mentions (0.04) | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | 0.04 | – | 0.04 | 0.04 | 0.04 |
| weather / econ / culture / general (0.05) | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 | 0.05 |
| zero_fees (0) | – | – | – | – | – | – | – | – | – | – | – | – | – | – | 0 | – |

\*Single fill at 0.045, probably a multi-price fill (I use the average price).

Sports detail around the July change (modal implied rate, fill count):

| feeType | 07-09 22h | 07-10 02h | 07-11 02h | 07-12 | 07-18 | 07-28 | 08-08 | 08-20 | 09-03 | 09-10 | 09-20 | 10-16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sports_fees_v2 | 0.03 (147) | 0.03 (48) | **0.05 (69)** | 0.05 (65) | 0.05 (17) | 0.05 (1) | – | – | 0.03 (5) | 0.03 (1) | 0.03 (1) | 0.03 (3) |
| sports_fees_v3 | – | – | 0.05 (11) | 0.05 (79) | 0.05 (105) | 0.05 (117) | 0.05 (82) | 0.05 (116) | 0.05 (63) | 0.05 (74) | 0.05 (149) | 0.05 (99) |

Fee-free markets showed `fee = 0` on all but a few fills. **[corrected by verifier 2026-10-17]** Those few are
**builder fees**, not multi-level fills. On a fee-free market (US x Iran ceasefire, Oct 31), every non-zero taker
`fee` came on a fill whose `OrderFilled.builder` was non-zero, at exactly 25, 50 or 100 bps of notional (3 of 25
taker fills). The docs say a fee-free market with a builder code charges "Builder fee only"
([builders/fees](https://docs.polymarket.com/programs/builders/fees.md)). So the on-chain `fee` = platform fee +
builder fee. Above-schedule outliers in this section (e.g. the 0.045 politics fill) are most likely builder fills too.
In the verifier's re-sample (`analyses/verification/v10_historical_fee_dates.py`) builder≠0 fills were excluded. In
that sample, 100% of the ≈50k taker fills in every (date, feeType) cell sat at the modal rate. Poly-v2 ExchangeV3 tokens did not resolve
through `/v2/tokens` (33 fills, median 0.03). Readings:

- The current formula with these rates was in force **from the first day after the V2 cutover**.
- **The crypto rate fell from 0.072 to 0.070 between 2026-05-04 16:00 and 2026-05-07 16:00 UTC.** There is no
  changelog entry. Secondary sources date it to July ([startpolymarket](https://startpolymarket.com/learn/polymarket-fees/))
  or to March 30 ([sacra](https://www.sacra.com/c/polymarket/)). Both are wrong per the chain.
- **Sports 0.03 → 0.05.** It had not happened by 2026-07-10 02:00 UTC (48 fills at 0.03). It was in force by
  2026-07-11 02:00 UTC (69 fills at 0.05). The changelog says "at midnight UTC" on the July 10 entry, so the
  switch was most likely 2026-07-11 00:00 UTC. `sports_fees_v3` markets start the same day (first created
  2026-07-11 19:00).
- The switch applied to **older** sports markets too. From 07-11 to 07-28 these were charged 0.05 (152 fills):
  game markets created Jun 28 to Jul 9, World Cup, F1, MLS Cup and NBA futures created in 2025–26. Those markets
  show `sports_fees_v2` 0.03 in Gamma today.
- From 2026-09-03 onwards, the `sports_fees_v2` markets that still traded (Ballon d'Or, UFC futures; 10 fills)
  were charged 0.03. Either the v2 schedule reverted between 07-28 and 09-03, or only some v2 markets had been
  switched. The sample cannot distinguish these (no v2 fills on 08-08 or 08-20).
  **[corrected by verifier 2026-10-17]** A 300-block re-sample at extra dates (builder≠0 fills excluded;
  `data/derived/verification_historical_fee_dates_{A,B}.json`) dates the reversion more tightly:

  | Date (20:00 UTC) | `sports_fees_v2` fills at 0.05 | fills at 0.03 |
  |---|---|---|
  | 07-15 | 690/690 | 0 |
  | 08-05 | 12/12 | 0 |
  | 08-15 | 243/243 | 0 |
  | 08-25 | 0 | 27/27 |

  The reversion happened between 2026-08-15 20:00 and 2026-08-25 20:00 UTC.

---

## 2. Fee history timeline (regimes that historical trades were made under)

| Date (UTC) | Event | Label | Source |
|---|---|---|---|
| ≤ 2025 | CLOB essentially fee-free for takers and makers (V1 orders carried `feeRateBps`, normally 0) | PLAUSIBLE | [The Block 2026-01-06](https://www.theblock.co/post/384461/polymarket-adds-taker-fees-to-15-minute-crypto-markets-to-fund-liquidity-rebates) (secondary): "most markets on the platform remain fee-free" |
| 2026-01-05 | Taker fees on **15-min crypto** up/down, "peak at 1.56% at 50%"; maker rebates (daily USDC) start | VERIFIED | [changelog](https://docs.polymarket.com/changelog/predictions.md) |
| 2026-01-16 | Maker rebate distribution documented: volume-weighted vs fee-curve weighted | VERIFIED | changelog |
| 2026-02-11/18 | Sports fees on **NCAAB and Serie A** from 2026-02-18; rebates computed per market | VERIFIED | changelog |
| 2026-02-12 | **5-min crypto** launched with fees (same curve as 15-min) | VERIFIED | changelog |
| 2026-03-06 | Fees extend to **all crypto** (1H, 4H, daily, weekly), **new markets only** | VERIFIED | changelog (2026-03-01 entry) |
| 2026-03-17 | March Madness: $2M+ liquidity rewards, 3.5 s minimum order age | VERIFIED | changelog |
| 2026-03-30 | **Fee Structure V2**: fees on Crypto, Sports, Finance, Politics, Economics, Culture, Weather, Tech, Mentions, Other; Geopolitics free | VERIFIED | changelog |
| 2026-03-30 | Announced as applying to markets that debut on/after 03-30; crypto 0.072 (1.80% peak), sports 0.03 (0.75%), politics 1.00% peak | SECONDARY | [iGB 2026-03-27](https://igamingbusiness.com/prediction-markets/polymarket-sports-fee-hike-2026/), [Pine Analytics 2026-03-25](https://pineanalytics.substack.com/p/polymarket-fee-rollout) |
| 2026-03-31 | "Fees should now be calculated using the feeSchedule object" | VERIFIED | changelog |
| ~2026-03-31/04-01 | Formula changed from `C×p×rate×(p(1−p))^exp` to `C×rate×p(1−p)`, after a brief anomalous version without the leading p. Peak cost as % of notional roughly doubled for the same rate | SECONDARY | [BlockBeats via cnyes 2026-04-01](https://news.cnyes.com/news/id/6404252) |
| 2026-04-28 ~11:00 | **CLOB V2 + pUSD** cutover (~1 h downtime). New exchange contracts; `feeRateBps`/`nonce`/`taker` removed from orders; fees set at match time; builder codes native; open orders wiped | VERIFIED | changelog 2026-04-17 and 2026-04-28 |
| 2026-04-29 | On-chain: crypto 0.072, sports 0.03, 0.04 / 0.05 groups as today, current formula | VERIFIED | §1.4 |
| 2026-05-04 | Deposit Wallet becomes the default for new accounts (gasless via relayer) | VERIFIED | [wallets-auth](https://docs.polymarket.com/trading/wallets-auth.md) |
| 2026-05-04..07 | **Crypto 0.072 → 0.070** (on-chain only, undocumented) | VERIFIED | §1.4 |
| 2026-05-28 | **Taker Rebate Program** live; new **Referral** terms (10% / 5% of net fees) | VERIFIED | [taker-rebates](https://docs.polymarket.com/programs/taker-rebates.md), [referral](https://docs.polymarket.com/programs/referral-program.md) |
| 2026-07-02 | World Cup markets decimalized to a 0.0025 tick | VERIFIED | changelog |
| 2026-07-10/11 | **Sports 0.03 → 0.05; sports maker rebate 25% → 15%** (`sports_fees_v3` for new markets). On-chain the 0.05 applied to all sports markets between 07-10 02:00 and 07-11 02:00 UTC | VERIFIED | changelog; on-chain §1.4 |
| 08-15..08-25 | Legacy `sports_fees_v2` markets charged 0.03 again (Gamma shows 0.03 for all of them). **[corrected by verifier 2026-10-17: window narrowed from 07-28..09-03; 0.05 still charged on 08-15 20:00 UTC, 0.03 on 08-25 20:00 UTC]** | VERIFIED (sparse) | on-chain §1.4 |
| 2026-08 | Crypto TWAP liquidity rewards $1M for 5m/15m/4h markets "through the month of August"; **ended** | VERIFIED | [liquidity-rewards](https://docs.polymarket.com/programs/liquidity-rewards.md) |
| 2026-08-17 / 09-04 | Crypto taker delay 250 → 50 ms (08-17), then 150 ms (09-04 14:00) | VERIFIED | changelog |
| 2026-09-04 | First `sports_fees_nfl_cfb_oct26` markets (0.03 / 15%); not in the docs | VERIFIED (data) | Gamma census; on-chain 10-16 |

**`fees_v1/v2/v3` naming.** These are Gamma `feeType` labels. They are not documented anywhere.

| Version | Gamma params | Where seen | Period |
|---|---|---|---|
| v1 crypto | `crypto_15_min` / `crypto_fees`: 0.25, exp 2, rebate 0.20 | Closed markets created Jan–Feb / Mar 2026 | Jan–Mar 2026 |
| v1 sports | `sports_fees`: 0.0175, exp 1, rebate 0.25 | Closed markets created Mar 2026 | Feb–Mar 2026 |
| v2 | `crypto_fees_v2` 0.07 (charged 0.072 until ~05-05); `sports_fees_v2` 0.03 / 25% | | From ~Apr 2026 |
| v3 | `sports_fees_v3` 0.05 / 15% | | From 2026-07-11 |

The v1 params plug into the old formula and reproduce the documented 1.56% crypto peak:
0.25 × 0.25² = 1.5625% of notional. They also reproduce iGB's "$0.22 per $50 sports trade at 50%":
100 × 0.5 × 0.0175 × 0.25 = $0.219. **PLAUSIBLE**. I did not decode V1-exchange (pre-04-28) fees on-chain, because
V1 used signed `feeRateBps` plus a fee-refund module (`fees_refunded` in user-stats), which needs more work.

**Share of markets with fees, by creation month** (Gamma closed markets, first 300 by keyset order per start-date
week, 16,000 markets; indicative, not random):

| Created | Oct-25 | Nov-25 | Dec-25 | Jan-26 | Feb-26 | Mar-26 | Apr-26 | May-26 | Jun-26 | Jul–Oct-26 |
|---|---|---|---|---|---|---|---|---|---|---|
| fee-enabled | 0% | 6% | 7% | 18% | 30% | 40% | 99% | 95% | 99% | ≈100% |

**Backtest rules of thumb:**
- Treat any fill **before 2026-01-05 as fee-free**.
- Treat a fill from **2026-01-05 to 2026-03-29** as fee-free unless the market is crypto short-horizon, any crypto
  created ≥ 03-06, or NCAAB/Serie A ≥ 02-18. Use the v1 formula for those.
- From **2026-03-30 onward** use per-fill on-chain fees where possible. Otherwise use the regime table:
  crypto 0.072 to ~05-05 then 0.07; sports 0.03 to 07-10 then 0.05 for all sports (legacy v2 markets back to 0.03
  between 08-15 and 08-25 **[corrected by verifier 2026-10-17: was "by 09-03"]**; 0.03 for NFL/CFB from 09-04).
  On-chain `fee` includes any builder fee, so exclude fills with `builder ≠ 0` when inferring the platform rate
  **[added by verifier 2026-10-17]**.
- The fortnight from **03-30 to 04-28** is the least certain. It had the V1 exchange and a formula flip.

---

## 3. Rebates and incentive programs

### 3.1 Maker Rebates (VERIFIED) — [docs](https://docs.polymarket.com/programs/maker-rebates.md)

- **Pool and payout.** The pool is `rebateRate × taker fees` collected **in that market**. It is paid daily in
  pUSD, with a $1 minimum.
- **Split.** Each maker gets `my_fee_equivalent / total_fee_equivalent`, where
  `fee_equivalent = C × rate × p × (1 − p)` of the maker's filled orders. Makers compete only within the same market.
- **Rebate share by category.** Crypto 20%, Sports 15%, others 25%, Geopolitics none. Legacy `sports_fees_v2`
  markets keep `rebateRate` 0.25. The docs say the share is "at the sole discretion of Polymarket and may change".
- **Size.** If all the market's fee-equivalent comes from fills where the taker paid the same rate, a maker earns
  about `rebateRate × taker fee` per filled share. In sports v3 at p=0.5 that is 0.15 × 1.25¢ = **0.19¢ per share**.
  In politics at p=0.5 it is 0.25 × 1.00¢ = **0.25¢**, and in crypto at 0.5 it is 0.20 × 1.75¢ = **0.35¢**.
  These amounts are small next to a 1¢ tick and adverse selection.
- **Endpoint.** `GET https://clob.polymarket.com/rebates/current?date=&maker_address=` is public and covers
  **maker** rebates only, not taker rebates ([spec](https://docs.polymarket.com/api-reference/rebates/get-current-rebated-fees-for-a-maker.md)).
  A live test returned $912.586967 for one wallet on 2026-06-16, which equals its `MAKER_REBATE` activity row paid
  2026-06-17 00:45 UTC.

### 3.2 Taker Rebate Program (VERIFIED) — [docs](https://docs.polymarket.com/programs/taker-rebates.md)

- Live since **2026-05-28**.
- **Weighted volume.** `wV = trade size ($ notional) × (1 − entry price) × category weight × bonuses`, taker
  trades only. Weights: Sports 1.0; Politics, Finance, Mentions and Tech 1.3; Economics, Culture, Weather and
  Other 1.7; Crypto 2.3; Geopolitics 0.
- **Tier updates.** The tier uses 30-day wV, is updated daily at 00:00 UTC, applies going forward only, and drops
  after a "short grace period".

| Tier | 30-day wV | Rebate | One-time bonus | Notional needed in 30 d for sports at p=0.5 | Crypto at p=0.5 | Sports favorite at p=0.9 |
|---|---|---|---|---|---|---|
| 0 | < $2k | 0% | – | – | – | – |
| Bronze | $2k | 3% | $10 | $4k | $1.7k | $20k |
| Silver | $20k | 8% | $50 | $40k | $17k | $200k |
| Gold | $200k | 18% | $250 | $400k | $174k | $2M |
| Platinum | $1M | 32% | $1,500 | $2M | $870k | $10M |
| Diamond | $4M | 44% | $7,500 | $8M | $3.5M | $40M |
| Obsidian | $10M | 50% | $25,000 | $20M | $8.7M | $100M |

- **Basis = share of fees paid** (VERIFIED, one exact reconciliation). **[corrected by verifier 2026-10-17]** The
  docs do state the base, though only on the fees page: "Takers can also earn a portion of fees back through the
  tiered Taker Rebate Program" ([trading/fees](https://docs.polymarket.com/trading/fees.md)). The taker-rebates page
  itself does not repeat it. The verifier re-ran the reconciliation live (`analyses/verification/v01_taker_rebate.py`):
  0.18 × 104,008.29 = 18,721.49, exact.
  Wallet `0x96cf…1acb` paid $104,008.29 of taker fees on 2026-06-16 (computed from `/v2/activity`) and received a
  `TAKER_REBATE` of $18,721.49 on 2026-07-08. 0.18 × 104,008.29 = 18,721.49, so the payout is Gold × fees.
  - Lifetime ratios are 27,877.90 / 127,397.56 = 21.9% for that wallet and 64,534.48 / 160,131.17 = 40.3% for
    `0x5e4c…dba2`. Both are ≤ 50%, which is consistent.
  - Its other payout ($9,156.41 on 2026-06-23) does not reconcile to a single tier × day. That may be bonuses or
    intraday tier changes. **PLAUSIBLE.**
- **Payout timing.** The docs say rebates are "paid every day at midnight UTC". Observed payouts were **batched**:
  both wallets received TAKER_REBATE only on 2026-06-23 and 2026-07-08, so treat payout timing as uncertain.
- **Exclusions.** Fee-free markets earn no wV. Omnibus-wallet integrations are excluded. Polymarket "can change at
  any time without notice" and can claw back for wash or self-trading.
- **Incentive distortion.** `(1 − p)` in wV means longshot buying climbs tiers 10–20× faster per $ than favorite
  buying. A retail account doing $10–50k a month of sports notional sits at Bronze or Silver (3–8%). Model **tier 0
  or Bronze** for a retail trader.

### 3.3 Liquidity Rewards (VERIFIED) — [docs](https://docs.polymarket.com/programs/liquidity-rewards.md)

- **Order score.** `S(v, s) = ((v − s)/v)² · b`. `v` = the market's max qualifying spread in cents
  (`rewardsMaxSpread`), `s` = the order's distance from the size-cutoff-adjusted midpoint, `b` = in-game multiplier.
  Orders below `rewardsMinSize` (shares) do not count.
- **Two-sided requirement.** Side scores are Q_one (bids on m + asks on m′) and Q_two (asks on m + bids on m′).
  - If 0.10 ≤ mid ≤ 0.90: `Q_min = max(min(Q_one, Q_two), max(Q_one/c, Q_two/c))` with **c = 3.0**, so
    single-sided liquidity scores at one third.
  - Outside that band, **two-sided quoting is required**: `Q_min = min(Q_one, Q_two)`.
- **Sampling.** Once a minute at a random offset, up to 1,440 samples per UTC-day epoch. The score is normalized
  per sample, summed over the epoch, then normalized again. The final share × the market's daily reward is paid at
  midnight UTC, with a **$1 minimum** payout. March Madness quoted a 3.5 s minimum resting time
  ([changelog](https://docs.polymarket.com/changelog/predictions.md)). `/order-scoring` checks whether an order
  "has been live for the required duration" ([spec](https://docs.polymarket.com/api-reference/trade/get-order-scoring-status.md)).
- **Live size on 2026-10-17** (`GET /rewards/markets/current`, 14,630 rows; public). Script:
  `analyses/fees/lp_rewards_snapshot.py`.
  - 14,608 markets with standard rewards.
  - **$289,412/day** in total `total_daily_rate`, of which $289,281 native and $131 sponsored. A separate
    sponsored query returned $3,994/day.
  - **[corrected by verifier 2026-10-17]** The total is a point-in-time snapshot. The same endpoint re-summed at
    22:05 UTC the same day gave **$191,809/day across 14,421 markets**, with median $3, p90 $25 and max $2,000
    (`data/derived/verification_lp_rewards_sum.json`). Game-day props drop out when they close. Quote a range or a
    time-stamped value, not "$289k/day".
  - Per market: median $3/day, p90 $25, p99 $104, max **$8,850/day** (EPL spread/total props on 2026-10-17 game
    day, max spread 2.5¢, min size 1,000 shares).
  - All configurations pay in pUSD and run to 2500-12-31.
  - By fee class, from the Gamma snapshot: sports v3 $151k/day, politics $56k, weather $19k, culture $14k,
    fee-free (geopolitics) $13k, finance $10k, NFL/CFB $9k.
  - Typical parameters: max spread 4.5¢ (median), min size 50 shares (254k markets) or 20 (30k).
- **Temporary programs:** March Madness $2M+ (from 2026-03-17) and Crypto TWAP $1M in August 2026, which the docs
  mark as "ended". The base program has run since at least 2024 (example configs start 2024-03-01). Both its size
  and its parameters are set per market by Polymarket.

### 3.4 Holding rewards (VERIFIED existence; rate UNRESOLVED)

- **Stated rate.**
  - The docs say "**4.00% annualized** … sampled once each hour, distributed daily … variable"
    ([positions-tokens](https://docs.polymarket.com/concepts/positions-tokens.md)).
  - The help center (modified 2026-06-01) says **3.25%**, funded by the Polymarket Treasury, with possible caps.
    Its eligible list covers the 2028 presidential/nominee markets, the 2026 midterms, leader-out markets
    (Erdoğan, Zelenskyy, Netanyahu, Xi, Putin), the Russia–Ukraine ceasefire and the 2026 crypto price-hit markets.
    It also says a new reward and oracle system is expected "later this year"
    ([help center](https://help.polymarket.com/en/articles/13364459-holding-rewards)).
  - Gamma tags such as "Earn 3.25%" match the help center.
- **Scope.** `holdingRewardsEnabled=true` on **339 open markets in 41 events**. That includes events not on the
  help-center list, such as state data-center moratoria, company-bankruptcy and impeachment markets.
- **Payout.** Paid as Data API activity type **`YIELD`** daily around 00:10 UTC. One large holder has received it
  every day since 2025-07.
- **Rate check.** That holder's current eligible value is about $13.3k at current prices, but payouts are about
  $0.62–0.65/day. That implies **≈1.7–1.8% APY**, about half the stated rate. Possible explanations are mid-vs-last
  pricing, eligibility subsets or caps. Not resolved.
- **Use in strategies.** It is a carry offset for long-dated markets (about 3% of capital per year at most). Do not
  rely on it: it is discretionary and treasury-funded.

### 3.5 Referral (VERIFIED) — [docs](https://docs.polymarket.com/programs/referral-program.md)

- **Terms effective 2026-05-28.** The referrer needs at least $10k lifetime volume. Rewards are **10% (direct)**
  and **5% (indirect)** of **net** fees, meaning fees after the referred user's tier rebate. They stop when the
  referral reaches Platinum or 30 days after sign-up. Self-referral is prohibited.
- **Earlier terms (SECONDARY).** Around 2026-03-30 the rates were 30% / 10% of gross fees
  ([Pine](https://pineanalytics.substack.com/p/polymarket-fee-rollout)).
- **Relevance.** None to a trader's own costs.

### 3.6 Builder fees (VERIFIED) — [docs](https://docs.polymarket.com/programs/builders/fees.md)

- Flat `notional × bps / 10,000`, **additive** to platform fees. Taker max 100 bps (1%), maker max 50 bps (0.5%).
  A builder can change its rate at most once per 7 days, with 3 days' notice.
- **Using a third-party front end or bot can add up to 1% of notional per taker fill and 0.5% per maker fill.**
  Builder rates are publicly queryable. The official polymarket.com UI is not documented as charging one.
  **PLAUSIBLE**: it carries no builder code.

### 3.7 Which incentives are temporary?

| Program | Status |
|---|---|
| Taker fees | Permanent design, rates changed 5+ times in 2026 |
| Maker rebate | Discretionary share |
| Taker rebate tiers | "Can change at any time without notice" |
| Referral | Same |
| Holding rewards | Treasury-funded, variable, possibly capped, to be replaced "later this year" |
| Liquidity rewards | Per-market allocations; seasonal top-ups end (March Madness, Crypto TWAP) |
| NFL/CFB 0.03 rate | Undocumented; the feeType name `…_oct26` suggests a dated promotion (PLAUSIBLE) |
| Level-up bonuses | One-time |

---

## 4. Non-trading costs

| Item | Cost | Label | Source |
|---|---|---|---|
| Split / merge | 1 pUSD ↔ 1 YES + 1 NO, no protocol fee | VERIFIED | [positions/manage](https://docs.polymarket.com/trading/positions/manage.md) |
| Redeem | Winning token → 1 pUSD, no fee. AutoRedeemer contract exists for automated redemption | VERIFIED | [positions/manage](https://docs.polymarket.com/trading/positions/manage.md), [contracts](https://docs.polymarket.com/resources/contracts.md) |
| Neg-risk convert (No → Yes on all others) | No fee documented | PLAUSIBLE | [negative-risk](https://docs.polymarket.com/concepts/negative-risk.md) |
| Gas: Deposit Wallet (default since 2026-05-04), Proxy (Magic/Google), Safe (MetaMask etc.) | **Gasless** through the Polymarket Relayer. Relayer API key = unlimited for your own wallet; builder keys 100/day (unverified tier) to unlimited | VERIFIED | [wallets-auth](https://docs.polymarket.com/trading/wallets-auth.md), [builder tiers](https://docs.polymarket.com/programs/builders/tiers.md) |
| Gas: EOA (allowlisted) | User pays **POL gas** for approvals, transfers, split/merge/redeem. Polygon gas is typically well under 1¢ per transaction | VERIFIED (who pays); PLAUSIBLE (amount) | wallets-auth |
| Trading gas | None for the user: orders are signed off-chain and the operator submits settlement | VERIFIED | [order-lifecycle](https://docs.polymarket.com/concepts/order-lifecycle.md) |
| Deposit | No Polymarket fee. Bridge (Fun.xyz) quotes include gas, app fee, swap impact. Live minimums: Polygon/Arbitrum/Base/Solana/Tron $2, Ethereum $3, Bitcoin $3.6. Third-party bridges recommended above $50k | VERIFIED | [deposit](https://docs.polymarket.com/trading/bridge/deposit.md), [quote](https://docs.polymarket.com/trading/bridge/quote.md), live `GET bridge.polymarket.com/supported-assets` |
| Withdraw | "Instant and free". pUSD → USDC.e (Offramp) → Uniswap v3 pool → native USDC; UI caps output difference at < 10 bp; pool can run dry; pUSD can be withdrawn directly | VERIFIED | [withdraw](https://docs.polymarket.com/trading/bridge/withdraw.md) |
| pUSD wrap / unwrap | 1:1 via CollateralOnramp / Offramp (pausable); USDC-backed, enforced on-chain | VERIFIED | [pUSD](https://docs.polymarket.com/concepts/pusd.md) |
| Card / exchange on-ramps | Intermediary fees (Coinbase, MoonPay; "2–3%" for cards, SECONDARY) | VERIFIED (exists) | [fees](https://docs.polymarket.com/trading/fees.md) |
| Min order size | **5 shares** on 287,974 / 288,003 open markets (`orderMinSize`, CLOB `min_order_size`) | VERIFIED | Gamma census; [place-orders](https://docs.polymarket.com/trading/place-orders.md) |
| Tick size | 0.01 on 239,209 markets, 0.001 on 48,793, 0.0025 on 1 (World Cup). Possible values: 0.1 / 0.01 / 0.005 / 0.0025 / 0.001 / 0.0001; changes are announced by a `tick_size_change` event | VERIFIED | census; [market-details](https://docs.polymarket.com/market-data/market-details.md) |
| Matching delays | `secondsDelay` 1 s on 237,644 (sports) and 3 s on 544 markets; crypto taker delay 150 ms. **[corrected by verifier 2026-10-17]** The 150 ms taker delay (`itode`) applies to 5-min, 15-min and hourly crypto up/down markets and to some single-stock/ETF up/down markets. It does not apply to 4-hour or daily crypto up/down markets or to price-level crypto markets | VERIFIED | census; changelog; live `/clob-markets` |

---

## 5. Worked effective-cost tables (taker, 2026-10-17 regime)

**Assumptions** (`analyses/fees/cost_table.py`, `data/derived/cost_table_2026-10-17.csv`):
- Fee per share = `(1 − ρ) × rate × p × (1 − p)`, where ρ = tier rebate: T0 0%, Gold 18%, Obsidian 50%.
  The rebate is received later, not at the fill.
- **(a) Hold to resolution.** Buy at p, one taker fee, redeem free.
- **(b) Round trip.** Buy at the ask p + s/2, sell later at the bid p − s/2 with the mid unchanged. Cost = two
  taker fees + the spread s.
- Spread s = **1¢** for p ≤ 0.95. That is the 0.01 tick, and the median Gamma best-bid/ask spread in every price
  bucket from 0.03 to 0.97 was 1.0¢ across 2,077 markets with ≥ $1k 24h volume (PLAUSIBLE, since Gamma best
  bid/ask is a snapshot and not depth). s = **0.1¢** at p = 0.99, the 0.001 tick near the extremes.
- **% of capital = cost per share / p.**
- Market impact beyond the touch is not included.
- Format: ¢ per share / % of capital.

**Sports, standard (`sports_fees_v3`, rate 0.05)**

| p | spread | (a) hold: T0 | Gold | Obsidian | (b) round trip: T0 | Gold | Obsidian |
|---|---|---|---|---|---|---|---|
| 0.05 | 1.0¢ | 0.238¢ / 4.75% | 0.195¢ / 3.90% | 0.119¢ / 2.38% | 1.475¢ / 29.49% | 1.389¢ / 27.79% | 1.237¢ / 24.75% |
| 0.10 | 1.0¢ | 0.450¢ / 4.50% | 0.369¢ / 3.69% | 0.225¢ / 2.25% | 1.900¢ / 19.00% | 1.738¢ / 17.38% | 1.450¢ / 14.50% |
| 0.30 | 1.0¢ | 1.050¢ / 3.50% | 0.861¢ / 2.87% | 0.525¢ / 1.75% | 3.100¢ / 10.33% | 2.722¢ / 9.07% | 2.050¢ / 6.83% |
| 0.50 | 1.0¢ | 1.250¢ / 2.50% | 1.025¢ / 2.05% | 0.625¢ / 1.25% | 3.500¢ / 7.00% | 3.050¢ / 6.10% | 2.250¢ / 4.50% |
| 0.70 | 1.0¢ | 1.050¢ / 1.50% | 0.861¢ / 1.23% | 0.525¢ / 0.75% | 3.100¢ / 4.43% | 2.722¢ / 3.89% | 2.050¢ / 2.93% |
| 0.90 | 1.0¢ | 0.450¢ / 0.50% | 0.369¢ / 0.41% | 0.225¢ / 0.25% | 1.900¢ / 2.11% | 1.738¢ / 1.93% | 1.450¢ / 1.61% |
| 0.95 | 1.0¢ | 0.238¢ / 0.25% | 0.195¢ / 0.21% | 0.119¢ / 0.13% | 1.475¢ / 1.55% | 1.389¢ / 1.46% | 1.237¢ / 1.30% |
| 0.99 | 0.1¢ | 0.050¢ / 0.05% | 0.041¢ / 0.04% | 0.025¢ / 0.03% | 0.199¢ / 0.20% | 0.181¢ / 0.18% | 0.149¢ / 0.15% |

**Politics (rate 0.04)**

| p | spread | (a) hold: T0 | Gold | Obsidian | (b) round trip: T0 | Gold | Obsidian |
|---|---|---|---|---|---|---|---|
| 0.05 | 1.0¢ | 0.190¢ / 3.80% | 0.156¢ / 3.12% | 0.095¢ / 1.90% | 1.380¢ / 27.60% | 1.311¢ / 26.23% | 1.190¢ / 23.80% |
| 0.10 | 1.0¢ | 0.360¢ / 3.60% | 0.295¢ / 2.95% | 0.180¢ / 1.80% | 1.720¢ / 17.20% | 1.590¢ / 15.90% | 1.360¢ / 13.60% |
| 0.30 | 1.0¢ | 0.840¢ / 2.80% | 0.689¢ / 2.30% | 0.420¢ / 1.40% | 2.680¢ / 8.93% | 2.377¢ / 7.92% | 1.840¢ / 6.13% |
| 0.50 | 1.0¢ | 1.000¢ / 2.00% | 0.820¢ / 1.64% | 0.500¢ / 1.00% | 3.000¢ / 6.00% | 2.640¢ / 5.28% | 2.000¢ / 4.00% |
| 0.70 | 1.0¢ | 0.840¢ / 1.20% | 0.689¢ / 0.98% | 0.420¢ / 0.60% | 2.680¢ / 3.83% | 2.377¢ / 3.40% | 1.840¢ / 2.63% |
| 0.90 | 1.0¢ | 0.360¢ / 0.40% | 0.295¢ / 0.33% | 0.180¢ / 0.20% | 1.720¢ / 1.91% | 1.590¢ / 1.77% | 1.360¢ / 1.51% |
| 0.95 | 1.0¢ | 0.190¢ / 0.20% | 0.156¢ / 0.16% | 0.095¢ / 0.10% | 1.380¢ / 1.45% | 1.311¢ / 1.38% | 1.190¢ / 1.25% |
| 0.99 | 0.1¢ | 0.040¢ / 0.04% | 0.032¢ / 0.03% | 0.020¢ / 0.02% | 0.179¢ / 0.18% | 0.165¢ / 0.17% | 0.140¢ / 0.14% |

**Crypto (rate 0.07)**

| p | spread | (a) hold: T0 | Gold | Obsidian | (b) round trip: T0 | Gold | Obsidian |
|---|---|---|---|---|---|---|---|
| 0.05 | 1.0¢ | 0.333¢ / 6.65% | 0.273¢ / 5.45% | 0.166¢ / 3.33% | 1.665¢ / 33.29% | 1.545¢ / 30.90% | 1.332¢ / 26.65% |
| 0.10 | 1.0¢ | 0.630¢ / 6.30% | 0.517¢ / 5.17% | 0.315¢ / 3.15% | 2.260¢ / 22.60% | 2.033¢ / 20.33% | 1.630¢ / 16.30% |
| 0.30 | 1.0¢ | 1.470¢ / 4.90% | 1.205¢ / 4.02% | 0.735¢ / 2.45% | 3.940¢ / 13.13% | 3.411¢ / 11.37% | 2.470¢ / 8.23% |
| 0.50 | 1.0¢ | 1.750¢ / 3.50% | 1.435¢ / 2.87% | 0.875¢ / 1.75% | 4.500¢ / 9.00% | 3.870¢ / 7.74% | 2.750¢ / 5.50% |
| 0.70 | 1.0¢ | 1.470¢ / 2.10% | 1.205¢ / 1.72% | 0.735¢ / 1.05% | 3.940¢ / 5.63% | 3.411¢ / 4.87% | 2.470¢ / 3.53% |
| 0.90 | 1.0¢ | 0.630¢ / 0.70% | 0.517¢ / 0.57% | 0.315¢ / 0.35% | 2.260¢ / 2.51% | 2.033¢ / 2.26% | 1.630¢ / 1.81% |
| 0.95 | 1.0¢ | 0.333¢ / 0.35% | 0.273¢ / 0.29% | 0.166¢ / 0.18% | 1.665¢ / 1.75% | 1.545¢ / 1.63% | 1.332¢ / 1.40% |
| 0.99 | 0.1¢ | 0.069¢ / 0.07% | 0.057¢ / 0.06% | 0.035¢ / 0.04% | 0.239¢ / 0.24% | 0.214¢ / 0.22% | 0.169¢ / 0.17% |

**Geopolitics (rate 0; spread only, and rebate tiers are irrelevant)**

| p | 0.05 | 0.10 | 0.30 | 0.50 | 0.70 | 0.90 | 0.95 | 0.99 |
|---|---|---|---|---|---|---|---|---|
| (a) hold | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| (b) round trip ¢ / % | 1.0 / 20.0% | 1.0 / 10.0% | 1.0 / 3.33% | 1.0 / 2.00% | 1.0 / 1.43% | 1.0 / 1.11% | 1.0 / 1.05% | 0.1 / 0.10% |

**Sports at 0.03** (legacy `sports_fees_v2` and NFL/CFB `…_oct26`): multiply the fee columns of the standard sports
table by 0.6. For example, hold at 0.50 = 0.75¢ / 1.50% (T0), and the round trip at 0.50 = 2.50¢ / 5.00%. The full
table is in the CSV.

**How to read the tables:**
- A hold-to-resolution bet at p must beat the price by `rate × (1 − p)` in probability terms to break even
  (multiply by (1 − ρ) for your tier). For sports T0 that is 4.75 percentage points of edge relative to price at 5¢,
  but 0.25 points at 95¢. Longshots are heavily taxed and favorites lightly.
- For a two-sided taker round trip, fees are the larger part of cost only near p = 0.5. Near the extremes the 1¢
  spread dominates.
- The cheaper side of a binary is the one with lower `% of capital` for the same $ fee. Buying No at 0.95 costs
  0.25% (sports) versus 4.75% for Yes at 0.05, but the $ fee per share is identical.

---

## 6. Contradictions and inconsistencies

**With CONTEXT.md:**
1. CONTEXT says "Sports 0.05". **Today 41,427 open sports markets (14.4% of all open markets; 8.8% of 24h volume)
   charge 0.03:**
   - `sports_fees_nfl_cfb_oct26`, 38,967 markets, with 0.03 charged on-chain;
   - `sports_fees_v2`, 2,460 markets, with 0.03 on-chain since at least 2026-09-03.
   Neither is in the docs.
2. CONTEXT says "Maker rebates … Sports 15%". The legacy `sports_fees_v2` markets carry `rebateRate` 0.25.
3. CONTEXT's "Geopolitics 0" is right for the *fee class*. Markets tagged geopolitics are mostly fee-free, but 29%
   of them carry fees (394 are `politics_fees`). The fee class must be read per market.
4. CONTEXT says Gamma `feeSchedule` is "authoritative for a market". That holds for **current** trades. For past
   trades it is wrong at least for:
   - crypto from 2026-04-28 to ~05-05, charged 0.072 while Gamma shows 0.07;
   - sports v2 markets from 2026-07-11 to at least 08-15, charged 0.05 while Gamma shows 0.03 **[corrected by
     verifier 2026-10-17: was "at least 07-28"]**.
5. CONTEXT describes the taker rebate as "3% … to 50%" without saying what it is a share of. It is a **share of
   taker fees paid** (verified by reconciliation), not of volume.
6. `pmr/fees.py` has three problems:
   - `taker_fee(…, exponent)` uses `rate × (p(1−p))^exponent`. That is correct for exponent 1, but legacy v1 markets
     (exponent 2) used `p × rate × (p(1−p))^exponent`, so the function overstates their fee by 1/p.
   - The sports maker share of 0.15 is wrong for v2 markets.
   - There is no NFL/CFB exception.
   Suggested fix (not applied, shared code): use `feeSchedule` and the on-chain fee for history.

**Within Polymarket's own docs:**
- The holding-reward rate is 4.00% in the [docs](https://docs.polymarket.com/concepts/positions-tokens.md) but
  3.25% in the [help center](https://help.polymarket.com/en/articles/13364459-holding-rewards).
- `orderMinSize` is described as "minimum order size in USDC" in
  [market-details](https://docs.polymarket.com/market-data/market-details.md), but `min_order_size` is "the
  minimum number of shares" in [place-orders](https://docs.polymarket.com/trading/place-orders.md). Treat the value
  5 as shares.
- `/clob-markets` `itode` says "250 ms taker-delay window". The changelog sets the crypto delay at 150 ms since
  2026-09-04.
- Bridge minimums in the docs table (Ethereum $7, Bitcoin $9, Tron $9) are higher than the live `/supported-assets`
  values (Ethereum $3, Bitcoin $3.6, Tron $2).
- The taker-rebate docs say "paid every day". Observed payouts were batched (06-23, 07-08).
- The `/fee-rate` example shows `base_fee: 30`. Live it returns 1000 or 0, and neither is the charged rate.
- The fees page still says "no Polymarket fees to deposit or withdraw **USDC**", although collateral is pUSD.

**Between secondary sources:**
- The date of the crypto 0.072 → 0.07 change is given as Mar 30 (sacra) and July (startpolymarket). On-chain it was
  between May 4 and May 7.
- Pine lists a Finance maker rebate of 50% in March. That is UNSUPPORTED today: Gamma shows 0.25.

---

## 7. Implications for strategies

- **Taker strategies.**
  - Short-horizon taker mean-reversion and momentum in the 0.2–0.8 range face round trips of 3–4.5¢ per share at
    T0 (6–13% of capital). That kills most edges.
  - Near-resolution favorites at 0.90–0.99 have small fees (0.05–0.45¢), and the 1¢ tick dominates. Where
    0.001 ticks exist the cost is tiny.
- **Geopolitics** is the only fee-free taker venue. Its cost is spread only, but it earns no taker-tier wV and has
  no maker rebates.
- **Maker / LP strategies.**
  - Makers pay 0, and the maker rebate adds about 0.19–0.35¢ per filled share at p = 0.5.
  - LP rewards pay $289k/day overall, but $3/day for the median market. Rewards concentrate on game-day sports
    props ($3k–8.9k/day, 2.5¢ max spread, 1,000-share minimum). Retail-scale LP is plausible only in mid-tier
    markets and must be tested against adverse selection. Sports markets add 1–3 s order delays.
- **Rebate tiers** are not reachable for retail at useful levels unless the account trades millions in notional a
  month. Plan on tier 0 or Bronze. Longshot buying gets wV credit 10× faster than favorite buying, so beware
  incentive-driven flow.
- **Backtests over 2025 to early 2026** can mostly assume zero fees (crypto short-horizon excepted). Results do
  **not** carry over to today. For example, two politics taker fees at p = 0.5 add 2¢ per share, which is 4% of
  capital. A 2025 strategy that netted +1% per round trip would net about −3% today at T0.
- **Undocumented per-market rate changes.** Re-read `feeSchedule` (or `/clob-markets` `fd`) at decision time. Never
  hard-code a category rate.

---

## 8. Open questions

1. When exactly did `sports_fees_v2` markets go back from 0.05 to 0.03, between 2026-07-28 and 2026-09-03? Did it
   apply to all of them? v2 fills are sparse after July. A targeted sample of known v2 futures (Ballon d'Or, UFC,
   F1) in August would settle it. **[corrected by verifier 2026-10-17]** It is now narrowed to between 08-15 20:00 and
   08-25 20:00 UTC (§1.4). Whether every v2 market switched is still open.
2. What was the pre-V2 charged fee (2026-01-05 to 04-27) on the V1 exchange, including `fees_refunded`? I did not
   decode it on-chain.
3. What is the holding-reward rate actually paid (observed ≈1.75% vs 3.25% / 4.00% stated), and what is the full
   eligible list?
4. Is the NFL/CFB 0.03 rate temporary (the `oct26` label suggests so), and does the 0.03 apply to all NFL/CFB
   market types?
5. What drives taker-rebate payout batching, and what made up the $9,156.41 payout?
6. Do the official polymarket.com UI or mobile apps attach a builder code with a non-zero builder fee? Not
   documented. Check `OrderFilled.builder` on a UI trade.
7. Is there any fee on neg-risk `convert` (the V1 NegRiskAdapter had a `feeBips` parameter)? Not documented for V2.
