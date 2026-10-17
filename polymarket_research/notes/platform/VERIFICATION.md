# Adversarial verification of the platform notes (2026-10-17)

Scope: the claims in `fees_incentives.md`, `mechanics.md`, `data_infrastructure.md` and `geography_legal.md` that most
affect whether a strategy is profitable or feasible. Each claim was attacked against primary sources: docs pages
re-fetched today, contract source, live API responses and on-chain logs. Read-only throughout: no authentication, no
orders, no wallet. The researchers' parquet files were used only to *choose* which markets to query. Every number
below was re-fetched live or re-computed from raw sources.

**Verdicts.**
- **CONFIRMED**: an independent check reproduced the claim.
- **CORRECTED**: the claim was wrong or materially incomplete, and the notes file now says so. Edits are marked
  `[corrected by verifier 2026-10-17]`.
- **REFUTED**: the claim is false.
- **UNVERIFIABLE**: no primary source or test was possible here.

Evidence labels (VERIFIED / PLAUSIBLE) follow CONTEXT.md.

Verifier scripts are in `analyses/verification/` (run from `polymarket_research/` with `PYTHONPATH=.`). Outputs are in
`data/derived/verification_*`, and raw responses are under `data/raw/`. Fresh doc snapshots are in the session
scratchpad (`verify/docs/`).

Result: 41 claims checked. 33 are CONFIRMED, 8 are CORRECTED and none are REFUTED. No claim that changes a headline
conclusion was refuted. The corrections narrow scope or dates, or add a caveat.

---

## 1. Fees, rebates, incentives

| # | Claim (as written by the researcher) | Verdict | Evidence | Source |
|---|---|---|---|---|
| F1 | Taker fee = `C × rate × p × (1−p)`, takers only; makers never pay | **CONFIRMED** (platform fee) | Docs formula re-read. On-chain, 25/25 builder-free NFL taker fills match `0.03·C·p(1−p)` to < 0.5 bp, and 70/70 maker fills paid 0, including 22 maker fills that carried a builder code. Builder caveat: see F12 | [trading/fees](https://docs.polymarket.com/trading/fees.md); [ITrading.sol](https://github.com/Polymarket/ctf-exchange-v2/blob/main/src/exchange/interfaces/ITrading.sol); `v03_builder_fee_check.py` |
| F2 | Category rates Crypto 0.07 / Sports 0.05 / Fin-Pol-Ment-Tech 0.04 / Econ-Cult-Weath-Other 0.05 / Geopolitics 0; maker rebate 20/15/25% | **CONFIRMED** | Both docs pages re-fetched. Live `/clob-markets` `fd.r` equals Gamma `feeSchedule.rate` on every fee-enabled market checked (15/15); the fee-free markets have no `fd` and `feesEnabled=false`. On-chain today: crypto 6/6 at 0.07, politics 5/6 at 0.04 (the 6th, 0.0465, came from the first pass, which did not filter by token or builder) | [trading/fees](https://docs.polymarket.com/trading/fees.md), [maker-rebates](https://docs.polymarket.com/programs/maker-rebates.md); `v02_live_fee_check.py` |
| F3 | NFL/CFB markets (`sports_fees_nfl_cfb_oct26`) charge 0.03 with a 15% rebate; undocumented | **CONFIRMED** | 5/5 markets show Gamma 0.03/0.15 and CLOB `fd.r`=0.03. On-chain 0.03 on 6/6 fills (Saints vs Giants), 6/6 (Notre Dame spread) and 25/25 builder-free fills in a second pass. No changelog entry mentions NFL, CFB or 0.03 | [changelog](https://docs.polymarket.com/changelog/predictions.md); `v02`, `v03` |
| F4 | Legacy `sports_fees_v2` markets: 0.03 with a 25% rebate today | **CONFIRMED** | 5/5 markets show Gamma 0.03/0.25 and `fd.r`=0.03. On-chain 12/12 taker fills at 0.03 on two Ballon d'Or markets today | Gamma `/markets/keyset`; CLOB `/clob-markets`; Polygon RPC |
| F5 | Gamma `feeSchedule` misstates history: crypto was charged 0.072 until early May; `sports_fees_v2` was charged 0.05 after the July 10 change | **CONFIRMED** | Independent dates, builder≠0 excluded. 2026-04-30: crypto 7,635/7,635 at 0.072. 2026-05-12: crypto 7,391/7,391 at 0.070. 2026-07-15: `sports_fees_v2` 690/690 at 0.05 while Gamma shows 0.03 | `v10_historical_fee_dates.py` → `verification_historical_fee_dates_A.json`; archive logs via polygon.drpc.org |
| F6 | `sports_fees_v2` was charged 0.05 "to at least 07-28" and was back at 0.03 "by 09-03" | **CORRECTED** | 08-05: 12/12 at 0.05. 08-15: 243/243 at 0.05. 08-25: 27/27 at 0.03. The reversion is between 08-15 20:00 and 08-25 20:00 UTC | `verification_historical_fee_dates_B.json` |
| F7 | Taker rebate = share of taker fees paid (Gold 18% × $104,008.29 = $18,721.49); "the docs never state the base" | **CORRECTED** (the base is confirmed; the "never stated" part is wrong) | Live `/v2/activity` recomputation: 06-16 fees $104,008.29 × 0.18 = $18,721.49, exact; user-stats `fees_paid` $127,397.56 matches. But the fees page says "Takers can also earn a portion of fees back through the tiered Taker Rebate Program" | [trading/fees](https://docs.polymarket.com/trading/fees.md); `v01_taker_rebate.py` |
| F8 | Tier thresholds $2k…$10M wV, rebates 3–50%, wV = size × (1−p) × weight (Sports 1.0, Pol/Fin/Ment/Tech 1.3, Econ/Cult/Weath/Other 1.7, Crypto 2.3, Geo 0) | **CONFIRMED** | Docs re-read | [taker-rebates](https://docs.polymarket.com/programs/taker-rebates.md) |
| F9 | Taker rebates were batched for this wallet, not paid daily as documented | **CONFIRMED** (one wallet) | Only 2 TAKER_REBATE rows (2026-06-23, 2026-07-08) for fee days 06-15 and 06-16. The docs say "paid every day at midnight UTC" | `v01`; [taker-rebates](https://docs.polymarket.com/programs/taker-rebates.md) |
| F10 | Liquidity rewards total $289,412/day across 14,608 markets; median $3/day; max $8,850 | **CORRECTED** (snapshot-dependent) | A re-sum at 22:05 UTC gave $191,809/day across 14,421 markets, median $3, p90 $25, max $2,000. Game-day props had closed. The docs scoring rule (c = 3.0, two-sided outside [0.10, 0.90], $1 minimum, 1,440 samples per epoch) is CONFIRMED | `GET clob.polymarket.com/rewards/markets/current`; `v09_lp_rewards_sum.py`; [liquidity-rewards](https://docs.polymarket.com/programs/liquidity-rewards.md) |
| F11 | Holding reward rate conflicts: docs 4.00%, help center 3.25% | **CONFIRMED** | Both pages re-fetched: "4.00% annualized" and "3.25% annualized", the latter dated June 1, 2026. The implied ≈1.75% from one holder was not re-tested | [positions-tokens](https://docs.polymarket.com/concepts/positions-tokens.md); [help center](https://help.polymarket.com/en/articles/13364459-holding-rewards) |
| F12 | Fee-free markets show on-chain fee 0 "on all but a few multi-level fills" | **CORRECTED** | The non-zero fees are **builder fees**. On the fee-free "US x Iran ceasefire through Oct 31" market, 3/25 taker fills had fee > 0, all with `builder ≠ 0`, at exactly 25, 50 and 100 bps of notional. The docs say "No platform fee + builder code → builder fee only". So the on-chain `fee` = platform + builder fee | [builders/fees](https://docs.polymarket.com/programs/builders/fees.md); `v03_builder_fee_check.py` |
| F13 | Cost table: sports round trip at 0.30 = 3.10¢ (10.3%), crypto 3.94¢ (13.1%), geopolitics 1.00¢ (3.3%); hold at 0.90 sports 0.45¢ (0.50%) | **CONFIRMED** (arithmetic) | Recomputed: 0.01 + 0.05·(0.305·0.695 + 0.295·0.705) = 3.10¢; crypto 0.01 + 0.07·(…) = 3.94¢; 0.05·0.9·0.1 = 0.45¢ | formula from [trading/fees](https://docs.polymarket.com/trading/fees.md) |

## 2. Mechanics, settlement, resolution

| # | Claim | Verdict | Evidence | Source |
|---|---|---|---|---|
| M1 | YES and NO books are one book (YES bid p = NO ask 1−p, same size), so binary complete-set arbitrage cannot appear on the visible book | **CONFIRMED** | 12/12 live markets were exact mirrors at every level (26–170 levels). Best asks summed to 1.001–1.014 and best bids to 0.986–0.999 | CLOB `GET /book`; `v04_mirror_books.py` |
| M2 | Neg-risk `convertPositions`: k NOs → (k−1)·amount·(1−f) collateral + YES on every other question; `feeBips` = 0 | **CONFIRMED** | Source re-read (NegRiskAdapter.sol `convertPositions`, commit f78b35b). `eth_call getFeeBips` = 0 on 25/25 distinct `negRiskMarketID`s drawn with a new random seed (question counts 3–93) | [NegRiskAdapter.sol](https://github.com/Polymarket/neg-risk-ctf-adapter/blob/main/src/NegRiskAdapter.sol); `v05_negrisk_feebips.py` |
| M3 | No open market is Protocol V2; all are `version: v1` | **CONFIRMED** | Fee census 288,003/288,003 v1 (independent of the mechanics census). Live: the 1,000 most recently created open markets (newest 2026-10-17 21:47 UTC) are all v1. `/clob-markets` `v` = "v1" on every market checked | Gamma `/markets/keyset?order=createdAt`; `/clob-markets` |
| M4 | `secondsDelay`: 1 s on ~237k sports markets, 3 s on ~533–544, none outside sports | **CONFIRMED** with one exception (noted in file) | Gamma and CLOB `sd`=1 on all NFL and EPL markets checked; legacy v2 futures have none. Exception: a stale weather market (Atlanta, May 15) has `sd`=3 | Gamma; CLOB `/clob-markets` |
| M5 | Crypto up/down markets carry a 150 ms taker delay (`itode`) | **CORRECTED** (scope) | `itode:true` on 5-min, 15-min and hourly crypto up/down markets (all ~200 hourly markets checked). Absent on 4-hour and daily up/down markets and on price-level crypto markets. Present on some equity up/down markets (AAPL, SPY, SPCX, MU) but not on index ones. 150 ms since 2026-09-04 per the changelog is confirmed; the order-lifecycle page still says 250 ms | CLOB `/clob-markets`; [changelog](https://docs.polymarket.com/changelog/predictions.md); [order-lifecycle](https://docs.polymarket.com/concepts/order-lifecycle.md) |
| M6 | Live UMA bonds are $250 (sports) / $500 and liveness is 900 s on many markets; the docs say $750 and 2 h | **CONFIRMED** on-chain | Docs re-read ("typically $750", "2-hour challenge period"). Last 3,000 blocks: `QuestionInitialized.proposalBond` 250 ×2,571, 500 ×187, 750 ×0. `ProposePrice` liveness = 900 s on 150/150 sampled. `optimisticOracle()` of `0x6507…` = `0x2c0367a9db231ddebd88a94b4f6461a6e47c58b1` | [resolution](https://docs.polymarket.com/concepts/resolution.md); [IUmaCtfAdapter.sol](https://github.com/Polymarket/uma-ctf-adapter/blob/main/src/interfaces/IUmaCtfAdapter.sol); `v06_uma_onchain_params.py` |
| M7 | UMA markets resolve ~2–3 h after `endDate` ("after the event"); Chainlink crypto ~1 min | **CORRECTED** (interpretation) | For sports, `endDate` = `gameStartTime` on 97.8% of 1,434 freshly closed markets, so the lag is measured from kick-off, not from the end of the game. Fresh sample: start → close median 4.3 h (p10 2.4, p90 8.9). Crypto median 0.01 h, consistent | Gamma `closed=true&order=closedTime`; `verification_recent_closed_markets.parquet` |
| M8 | Disputes are rare: 0.035% of closed markets (sports 0.024%); the docs flow is 1st dispute → re-proposal, 2nd → DVM, 4–6 days | **CONFIRMED** (consistent) | 0 disputes in 1,500 and in 4,000 freshly closed markets (95% sports). Docs flow and timeline re-read | Gamma `umaResolutionStatuses`; [resolution](https://docs.polymarket.com/concepts/resolution.md) |
| M9 | 50-50 payouts hit 1.7% of sports markets | **CORRECTED** (sample-dependent) | The researcher's windows range from 0.93% to 3.17%. A fresh sample of 3,807 sports markets (2026-10-17 21:22–22:02 UTC) had 11 (0.29%); the data-infrastructure sample had 2/2,000. The 50-50s concentrate in tennis totals and handicaps, esports props and child moneylines | Gamma `outcomePrices`; `verification_recent_closed_4000.parquet` |
| M10 | A matched trade reaches the chain a median ~2.27 s after the match | **CONFIRMED** | Re-run: match → block median 2.42 s, p90 2.78 s, max 3.28 s (n=40). 37 of the 40 txs went to `0xE111…` and 3 to `0xe222…` | CLOB WS + Polygon RPC; `v07_latency_rerun.py` |

## 3. Data infrastructure and detection latency

| # | Claim | Verdict | Evidence | Source |
|---|---|---|---|---|
| D1 | The legacy RTDS `activity` topic is a public, unauthenticated, wallet-attributed trade firehose: ~54 rows/s, median ~2.2 s after the match | **CONFIRMED** | Re-run: 54.0 rows/s, 9,722/9,722 rows carry `proxyWallet`; latency from match median 2.21 s, p90 2.96 s, max 3.87 s (n=489). Payload `timestamp` is 1 s before block time. The docs say "Keep using RTDS for the `activity` topic" | [rtds-to-polybolt](https://docs.polymarket.com/migrate/rtds-to-polybolt.md); `v07_latency_rerun.py` |
| D2 | No server-side wallet filter on RTDS; `market_slug` filters work | **CONFIRMED** | `{"proxyWallet"}` (checksummed and lowercase) and `{"user"}` gave 0 rows while the firehose carried 53 and 16 of that wallet's rows. The `market_slug` control gave 734/734, none off-target | `v07`, `v08_rtds_filter_control.py` |
| D3 | `/v2/trades` is CloudFront-cached (`max-age=300`); an identical polling URL can be minutes stale; a nonce busts the cache; busted 2-s polling ≈ 4.6 s after the row timestamp | **CONFIRMED** | Headers: `max-age=300`, a second request was a `Hit` with `age 2`, the nonce request was a `Miss`. `/v2/activity` max-age=15, `/v2/holders` 120, Gamma keyset 300 (`age` 274). Busted poll median 4.29 s (n=12); the cached URL saw no new row within 120 s | live headers; `v11_poll_latency.py` |
| D4 | No official historical order-book endpoint | **CONFIRMED** | CLOB OpenAPI (55 paths): `/book` takes only `token_id`, `/books`; history routes are `/prices-history` and `/batch-prices-history` only. Gamma: none. Data v2: only `/v2/prices-history` | [clob-openapi.yaml](https://docs.polymarket.com/api-spec/clob-openapi.yaml), [data-api v2 openapi](https://data-api.polymarket.com/v2/openapi.json) |
| D5 | CryptoHouse `orders_filled` is stale at 2026-01-05 22:05:45 | **CONFIRMED** | 257,649,337 rows, 2022-11-21 19:50:09 → 2026-01-05 22:05:45, max block 81,265,743 | `crypto-clickhouse.clickhouse.com` |
| D6 | `/v2/trades` ignores `start`/`end` with `condition` but honours them with `user` | **CONFIRMED** | A condition query with a window 7–6 days ago returned today's rows. A user query for 2026-06-15 returned 52 rows inside the window; an empty window returned 0 | Data API v2 live |
| D7 | `/v2/prices-history` serves resolved tokens (CONTEXT said empty); CLOB `/prices-history?interval=max` returns empty for them | **CONFIRMED** | Token `98258…0714`: v2 `interval=max` gave 114 points ending `{price 0.0, resolution_seconds 0}`; CLOB gave 0 points | Data API v2; CLOB |
| D8 | Telonex: $99/month, trades/quotes/books from 2025-10-11. Tardis: from 2026-05-25, first day of each month free | **CONFIRMED** as vendor statements (label stays PLAUSIBLE: data not downloaded) | Vendor pages re-read | [telonex.io/pricing](https://telonex.io/pricing), [telonex.io/data/polymarket](https://telonex.io/data/polymarket), [Tardis docs](https://docs.tardis.dev/historical-data-details/polymarket) |
| D9 | CLOB market WS `last_trade_price` arrives ~13 ms after the match, with tx hash and no wallet | **CONFIRMED** | Re-run median 17 ms, p90 205 ms (n=493); 493/493 carry `transaction_hash` | `v07_latency_rerun.py` |

## 4. Geography and legal

| # | Claim | Verdict | Evidence | Source |
|---|---|---|---|---|
| G1 | Docs geoblock: 7 OFAC block-completely rows; 37 close-only rows on frontend and API (incl. US, GB, FR, DE, IT, AU, SG, PL, TW, TH and 4 Canadian provinces); 5 frontend-only (IE, JP, MT sports, NL, KR) | **CONFIRMED** | Page re-fetched and rows counted | [geoblock](https://docs.polymarket.com/api-reference/geoblock.md) |
| G2 | ToS (effective 2026-08-11) bars persons who "reside in, are located in, are incorporated in…" listed places, and §4.1 adds "a citizen of"; VPNs prohibited | **CONFIRMED** | Google Doc export of the document embedded on polymarket.com/tos, re-read | [polymarket.com/tos](https://polymarket.com/tos) |
| G3 | `GET polymarket.com/api/geoblock` checks only the IP; from this sandbox it returns blocked, US/OH | **CONFIRMED** | Live: `{"blocked": true, "country": "US", "region": "OH"}` | [geoblock](https://docs.polymarket.com/api-reference/geoblock.md) |
| G4 | Gamma `restricted` = true on every open market, so it is useless as a filter | **CONFIRMED** | 1,000/1,000 top open markets by 24h volume, plus every market fetched in F2–F4 | Gamma live |
| G5 | Help center says "39 countries" but lists 40 and omits KR | **CONFIRMED** | 40 two-letter codes parsed; KR absent | [help center](https://help.polymarket.com/en/articles/13364163-geographic-restrictions) |
| G6 | Polymarket US: taker Θ = 0.0695 (Table Tennis 0.10), maker −0.0125, new tiers from 2026-10-19; no public trade tape | **CONFIRMED** | Docs re-read: "Trades are not disseminated via market data APIs" | [docs.polymarket.us/fees](https://docs.polymarket.us/fees.md), [market-data](https://docs.polymarket.us/trader-guide/market-data.md) |
| G7 | Kalshi Developer Agreement v1.1: use counts as acceptance; API use limited to a member's own trading; no storing or aggregating; no benchmarking | **CONFIRMED** (text of the S3 copy, last-modified 2023-11-09). Whether it is the live version is UNVERIFIABLE (kalshi.com returns 429) | PDF re-read; docs.kalshi.com/welcome says use binds to the Developer Agreement | [S3 PDF](https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf), [docs.kalshi.com/welcome](https://docs.kalshi.com/welcome.md) |
| G8 | Perps blocked from the US, all of Canada, CU, IR, KP, SY and occupied Ukraine; read-only data not restricted | **CONFIRMED** | Page re-read | [perps geographic restrictions](https://docs.polymarket.com/api-reference/perps/geographic-restrictions.md) |
| G9 | (geography §2.5) International maker rebates are "20–25%" of taker fees | **CORRECTED** to 15–25% (Sports 15%). The international sports taker rate also has 0.03 exceptions | Docs table | [maker-rebates](https://docs.polymarket.com/programs/maker-rebates.md) |

---

## 5. What changes for strategies

1. **Fee inference from chain data.** `OrderFilled.fee` includes builder fees: 0–100 bps of notional for takers and 0–50
   bps for makers. Any backtest that reads other wallets' fees on-chain must drop `builder ≠ 0` fills when it wants the
   platform rate. Live costs through a third-party front end can exceed the platform schedule by up to 1% per taker fill.
2. **The historical fee regime table needs one more date.** Legacy `sports_fees_v2` markets paid 0.05 from 2026-07-11 to
   at least 08-15, and 0.03 again by 08-25. Gamma shows 0.03 for the whole period.
3. **Latency strategies on crypto.** Only 5m, 15m and 1h up/down markets carry the 150 ms taker delay. 4h and daily
   up/down markets match immediately. That changes which markets favour makers over takers.
4. **Resolution lock-up for sports.** Gamma `endDate` is the scheduled start. A "3 h after `endDate`" lag is about 1 h
   after a 2-hour game ends. UMA liveness on these markets is 15 minutes on-chain.
5. **The 50-50 tail is a market-type risk, not a category rate.** It is 0.3% to 3% depending on mix, concentrated in
   tennis totals, esports props and child moneylines. "Buy the 0.99 favourite" strategies must filter by
   `sportsMarketType`.
6. **LP reward pools move intraday.** The total was $289k at 15:00 and $192k at 22:05 UTC on the same day. Size LP
   capacity estimates per market and time, not from one snapshot.

## 6. Not re-tested (left at the researchers' label)

- AutoRedeemer ~12 s after resolution; convert gas 0.58M–13.7M.
- The open-market census totals (99.6% fee-enabled, 93.1% of 24h volume).
- The holder's implied ≈1.75% holding yield.
- The `/v2/resolutions` `payouts: null` share.
- Third-party dataset row counts.
- All secondary-source regulatory actions (§3 of `geography_legal.md`) and the live Kalshi restricted list (kalshi.com
  returns 429).
- Latency at peak hours or from other regions.

## 7. Recommended changes to CONTEXT.md (not applied: shared ground-truth file)

- "Sports 0.05": add that NFL/CFB (`sports_fees_nfl_cfb_oct26`) and legacy `sports_fees_v2` markets charge 0.03.
- "Makers never pay": true for platform fees only. Builder maker fees of up to 50 bps exist.
- "`/v2/prices-history` returned empty for a resolved token": wrong today (D7).
- "`secondsDelay` … some sports markets": it is 1 s on ~92% of open sports markets. Add `itode` (150 ms) on
  5m/15m/1h crypto up/down markets.
- "Positions span Conditional Tokens and a PositionManager": 0 open markets are v2 (M3).
- `pmr/fees.py`: `MAKER_REBATE_SHARE['sports']` = 0.15 is wrong for `sports_fees_v2` (0.25), and there is no 0.03
  NFL/CFB case. `market_fee_rate()` already prefers the per-market `feeSchedule`, which handles both today.
