# Data infrastructure and measured latency (as of 2026-10-17)

Scope: every public data source a retail Polymarket strategy needs (wallet histories, trade tapes,
price history, books, metadata, resolutions, holders, boards, rewards, PnL), the real-time streams,
a measurement of how fast a trade by an arbitrary wallet becomes visible, the historical order-book and
fill datasets that exist outside Polymarket, and the data pitfalls that break backtests.
Read-only work: no authentication, no orders, no wallet, nothing bought or signed up for.

Labels: **VERIFIED** = I inspected the primary source (docs page, OpenAPI/AsyncAPI spec, live response
or on-chain data) myself on 2026-10-17. **PLAUSIBLE** = consistent with evidence but not verified
directly (for example a vendor's own description of its product). **UNSUPPORTED** = no primary source found.

Primary sources (all fetched 2026-10-17):

- Data API v2 OpenAPI: [data-api.polymarket.com/v2/openapi.json](https://data-api.polymarket.com/v2/openapi.json) (title "Polymarket Data API v2", version 0.1.0)
- CLOB OpenAPI: [docs.polymarket.com/api-spec/clob-openapi.yaml](https://docs.polymarket.com/api-spec/clob-openapi.yaml); Gamma OpenAPI: [docs.polymarket.com/api-spec/gamma-openapi.yaml](https://docs.polymarket.com/api-spec/gamma-openapi.yaml)
- AsyncAPI: [asyncapi.json](https://docs.polymarket.com/asyncapi.json) (CLOB market channel), [ws-live-v2 asyncapi.json](https://ws-live-v2.polymarket.com/asyncapi.json) (PolyBolt 2.0.0), [asyncapi-sports.json](https://docs.polymarket.com/asyncapi-sports.json), [asyncapi-user.json](https://docs.polymarket.com/api-reference/wss/user.md)
- Docs: [/api-reference/rate-limits](https://docs.polymarket.com/api-reference/rate-limits.md), [/migrate/data-api-v1-to-v2](https://docs.polymarket.com/migrate/data-api-v1-to-v2.md),
  [/market-data/realtime-data](https://docs.polymarket.com/market-data/realtime-data.md), [/migrate/rtds-to-polybolt](https://docs.polymarket.com/migrate/rtds-to-polybolt.md),
  [/market-data/prices-order-books](https://docs.polymarket.com/market-data/prices-order-books.md), [/trading/wallet-activity](https://docs.polymarket.com/trading/wallet-activity.md),
  [/trading/wallets-auth](https://docs.polymarket.com/trading/wallets-auth.md), [/resources/onchain-position-data](https://docs.polymarket.com/resources/onchain-position-data.md),
  [/changelog/predictions](https://docs.polymarket.com/changelog/predictions.md)
- Legacy RTDS client README (deprecated package, still the only schema reference for the `activity` topic): [Polymarket/real-time-data-client](https://github.com/Polymarket/real-time-data-client/blob/main/README.md)

Scripts (read-only) in `analyses/latency/` (run from `polymarket_research/`; `rtds_filter_test.py` is standalone):

| Script | What it does | Output |
|---|---|---|
| `measure_latency.py` | 10-min live run: Data API polling (cached and cache-busted URLs), CLOB market WS, RTDS `activity` firehose and filtered streams, `/v2/status`, post-run tapes, Polygon RPC block times | `data/derived/latency_<UTC>_*.parquet`, `_summary.json`; raw responses in `data/raw/data-api/live/<date>/latency_<UTC>_responses.json.gz` |
| `analyze_latency.py` | Offline analysis of one run (joins by tx hash, coverage, timestamp semantics) | `data/derived/latency_<UTC>_analysis.json` |
| `endpoint_probe.py` | One call per endpoint: shape, page size, behaviour on resolved markets, v1 status | `data/derived/endpoint_probe_20261017T1545.json` |
| `pagination_caps_probe.py` | Walks boards and holder lists to their real depth | `data/derived/pagination_caps_*.json` |
| `activity_types_probe.py` | Example rows for every `/v2/activity` type among top-volume wallets | `data/derived/activity_types_probe_20261017T1558.json` |
| `gamma_status_sample.py` | Status fields of 2,000 markets closed 2026-10-10..12, plus `/v2/resolutions` | `data/derived/gamma_status_sample_20261017T1557.parquet` |
| `ws_channels_probe.py` | RTDS wallet-filter test, unauthenticated PolyBolt (`price.polymarket`, gated `price.crypto`), sports socket | `data/derived/ws_channels_probe_20261017T2129.json` |
| `rtds_filter_test.py` | RTDS filter formatting and several subscriptions per connection | `data/derived/rtds_filter_test_20261017T2140.json` |

---

## 0. Summary for strategy design

1. **The fastest public, wallet-attributed trade feed is the legacy RTDS `activity` WebSocket** (`wss://ws-live-data.polymarket.com`,
   no authentication). In a 10-minute run on 5 active markets it delivered a target's trade a **median 2.2 s after the match** (p90 3.1 s, max 4.5 s;
   n = 589), about 0.8 s after its own `timestamp` and at about the Polygon block time. It carries `proxyWallet`, `transactionHash`, price, size, side, asset,
   condition and slug. **No server-side wallet filter exists** (5 filter keys tested: 0 rows); filter the ~54 rows/s firehose client-side. (VERIFIED, §2–3)
2. **Polling the Data API is slower and, done naively, very stale.** `/v2/trades?condition=…&limit=50` every 2 s found a new trade a median
   **4.6 s after its `timestamp`** (upper bound; p90 6.5 s, max 7.9 s; n = 589), i.e. 6.7 s after the match. That is only true with a cache-busting
   parameter: the identical URL is served by CloudFront with `max-age=300`, and a naive poller saw trades a **median 112 s late (p90 256 s, max 302 s)**. (VERIFIED, §3)
3. **The anonymous print is public about 2 s before any wallet-attributed source.** The CLOB market WebSocket's `last_trade_price` arrives 13 ms
   (median) after the match, with price, size, side and tx hash but no wallet. A copy-trader therefore always acts after the leader's price
   impact has been visible to every book subscriber for about 2 s. (VERIFIED, §3)
4. **`timestamp` on Data API trades is the block timestamp** (160/160 transactions matched exactly via Polygon RPC). Blocks land a median
   2.2 s after the off-chain match (1.0–3.7 s). (VERIFIED, §3)
5. **No official historical order books.** Third-party sources exist: Telonex (paid, trades/quotes/books from 2025-10-11), Tardis.dev (from 2026-05-25,
   first day of each month free), free Hugging Face archives (tick-level 2026-02-22 → 2026-08-10; ~5-minute snapshots since 2026-07-23, still updating;
   rewarded-market L2 since 2026-07-22, still updating). (PLAUSIBLE: vendor/dataset descriptions, not downloaded, §4)
6. **Protocol V2 (2026-04-28 onward) fills are in public datasets**: SII-WANGZJ/Polymarket_data (to 2026-10-04), TimeSeventeen/Polymarket-v2 (daily, to 2026-10-16),
   wzsg (to 2026-08-03), plus Dune and Allium. **CryptoHouse is still stale at 2026-01-05 22:05:45** (re-checked today). (VERIFIED for CryptoHouse; PLAUSIBLE for the others, §4)
7. **Backtest-breaking pitfalls**: `taker_only=true` is the default (one taker row per tx); a (tx, wallet) pair is not a unique fill key and Data API rows
   carry no log index; SPLIT/MERGE/CONVERSION/REDEEM rows are needed for PnL; `active=true` on every closed market; `/v2/resolutions` returned
   `payouts: null` for 44% of resolved markets; 8% of RTDS rows lack condition/slug. (VERIFIED, §5)

---

## 1. REST endpoints per data need

### 1.1 Conventions that apply to every Data API v2 route (VERIFIED, OpenAPI `info.description`)

- Base `https://data-api.polymarket.com/v2/...`, no auth. Response is `{data, pagination}`. A miss is `data: null` or `[]`, never an error.
- **Cursor-only pagination**: follow `pagination.next_cursor` until `null`; `has_more` is exact; sending `offset` is a `400` (live: `offset` → 400, `limit=1001` → 400).
  Feeds (`trades`, `activity`) are keyset walks on `(block_timestamp, sequence_id)`, stable under concurrent writes. Boards, `holders` and most
  combo sorts are offset walks hidden in the cursor, so **a walk across a data refresh can skip or repeat rows**. On `trades`/`activity` the cursor
  carries only the anchor and page size: **re-send the same filters on every page** or the walk silently re-anchors.
- **Default page size is 100 on every route I tried** (trades, activity, positions, leaderboard, holders; live). Max 1,000 (`/v2/prices-history` 10,000; `/v2/builders/volume` 90 buckets).
- **Windows**: on `/v2/trades?user=` and `/v2/activity`, omitted/0 `start` = three years back (`start=1` = full history), omitted/0 `end` = now + 1 day.
  **`/v2/trades` with `condition`/`event_id` ignores `start`/`end` and serves a fixed three-year window; the bare feed serves the current plus previous month.**
  Live check: `condition=…&start=1781500000&end=1781510000` returned rows at 1781580178 (ignored); the same window with `user=` was honoured.
- Units: bare `size`/`volume` are **shares**, `_usdc` fields are USD. `outcome_index: 999` = could not be labelled. A missing/`null` number means unavailable, not zero.
- Errors: JSON `{error, code, retryable, trace_id}`; `429`/`503` carry `Retry-After`. Every response has `x-trace-id`.
- **Edge caching (VERIFIED from headers, undocumented except for `/v2/resolutions`)**: responses are served through CloudFront with
  `cache-control: public, max-age=…`. Identical URLs return the cached body until it expires, whoever requested it first. Measured `max-age`:

  | Route | `cache-control` | Consequence |
  |---|---|---|
  | `/v2/trades` (all shapes), v1 `/trades` | `max-age=300` | an identical polling URL can be **up to 5 min stale** (observed `age` up to 217 s) |
  | `/v2/oi` | `max-age=300` | |
  | `/v2/holders` | `max-age=120` | |
  | `/v2/prices-history`, CLOB `/prices-history` | `max-age=90` | |
  | `/v2/activity` | `max-age=15` | |
  | `/v2/value` | `max-age=6` | |
  | `/v2/positions`, `/v2/resolutions` | `max-age=5` (resolutions: up to 10 min once all rows are resolved, per [changelog 2026-10-07](https://docs.polymarket.com/changelog/predictions.md)) | |
  | `/v2/leaderboard`, `/v2/user-pnl`, `/v2/status` | none seen | |
  | Gamma `/markets/keyset` | `max-age=300` (Cloudflare `HIT`, `age` 140) | market metadata, prices and flags can be 5 min old |
  | CLOB `GET /book`, `POST /books` | none (`cf-cache-status: DYNAMIC`) | books are live |

  Adding any unused query parameter (e.g. `_=<nonce>`) produced `x-cache: Miss from cloudfront` and fresh rows on every request (60/60 and 300/300
  requests in my runs; the API did not reject the extra parameter). This is undocumented behaviour, and it moves load to the origin, so use it sparingly
  and inside the rate limits. Different spellings (`limit=49`, `conditionId=` alias, `taker_only=false`) are also separate cache keys.

### 1.2 Endpoint table

Rate limits are per IP from [/api-reference/rate-limits](https://docs.polymarket.com/api-reference/rate-limits.md) (Cloudflare throttles, i.e. delays, rather than rejects).
"ts" = timestamp semantics.

| Need | Endpoint (current) | Key parameters | Page size / pagination | Rate limit | ts semantics | Coverage / notes | Label |
|---|---|---|---|---|---|---|---|
| Wallet trades | `GET /v2/trades?user=` | `user`, `condition` (≤20), `event_id` (≤20), `side`, `taker_only` (default **true**), `filter_type` CASH/TOKENS + `filter_amount` (default 0.01 tokens), `start`/`end` (user shape only) | default 100, max 1000, keyset cursor | 300/10 s (`/v2` overall 800/10 s) | `timestamp` = **block timestamp**, epoch s (spec; matched 100% of RPC sample, §3) | 3-year floor unless `start=1`. No maker/taker role field. Rows: `proxy_wallet, side, token_id, condition_id, size, price, timestamp, title, slug, event_slug, outcome, outcome_index, name, pseudonym, transaction_hash` | VERIFIED |
| Wallet activity | `GET /v2/activity?user=` | `type` (CSV; `TIP` opt-in), `condition`/`event_id` (exclusive), `side`, `start`/`end` on block ts, `sort_direction` ASC/DESC, `exclude_deposits_withdrawals` (default **true**) | default 100, max 1000, keyset `(block_timestamp, sequence_id)` | 200/10 s | block timestamp, s | Types seen live: TRADE, SPLIT, MERGE, REDEEM, CONVERSION, REWARD, MAKER_REBATE, TAKER_REBATE, YIELD, TIP, DEPOSIT, WITHDRAWAL. SDK union also lists MIGRATION and REFERRAL_REWARD ([wallet-activity](https://docs.polymarket.com/trading/wallet-activity.md)) | VERIFIED |
| Wallet positions | `GET /v2/positions` | `user` and/or `condition`; `status` OPEN (default, superset incl. redeemable winners) / REDEEMABLE / REDEEMABLE_LOST / MERGEABLE / CLOSED; `sort_by` (7 options); `include_archived` (default false); `title`; `start`/`end` on `last_event_at` | default 100, max 1000; cursor binds status/sort | 200/10 s | `first_entry_at`, `last_event_at` epoch s | Market anchor (no `user`) = one condition's holders. Fields: `avg_price`, `entry_cost_usdc` (fee-exclusive), `entry_fees_usdc`, `realized_pnl`, `total_size` (= lifetime bought, not balance), `current_size` | VERIFIED |
| Market trade tape | `GET /v2/trades?condition=` (≤20 ids) or `?event_id=` | `taker_only=false` adds maker rows | default 100, max 1000, keyset | 300/10 s | block ts | fixed 3-year window, `start`/`end` ignored; full tapes of 2025 markets retrievable (CONTEXT.md) | VERIFIED |
| Global trade tape | `GET /v2/trades` (no anchor) | | keyset | 300/10 s | block ts | rolling current + previous month only | VERIFIED (spec) |
| Price history (v2) | `GET /v2/prices-history` | `token_id`; exactly one of `interval` (`max`,`all`,`1m`,`1w`,`1d`,`6h`,`1h`), `start`(+`end`, end exclusive), `as_of`; `bucket_seconds` 60–86400 | default/max 10,000 points, cursor | 200/10 s | point `timestamp` = observation (bucket start), `resolution_seconds` = width (0 = exact tick) | 3 h and 12 h series permanent back to 2022-11-18; 1-min ≥ 7 days, 5-min ≥ 60 days, 30-min ≥ 90 days. Explicit windows ≤ 15 days wide. **Resolved series end with a settlement point** (payout 0/1, `resolution_seconds` 0). Live: resolved token, `interval=max` → 114 points at 12 h ending with `{price: 0.0, resolution_seconds: 0}` | VERIFIED |
| Price history (CLOB) | `GET /prices-history` | `market` (token id), `startTs`/`endTs` or `interval`, `fidelity` (minutes, default 1) | one array `history[{t,p}]` | 1,000/10 s | `t` epoch s | Resolved market: `interval=max` → 0 points; explicit window → 337 points at ~1-min spacing. Docs now route price history to `/v2/prices-history` ([changelog 2026-09-04](https://docs.polymarket.com/changelog/predictions.md)) | VERIFIED |
| Batch price history | `POST /batch-prices-history` | body `{markets: [≤20 token ids], start_ts, end_ts, interval, fidelity}` | map token → points | (CLOB general 9,000/10 s) | s | 21 ids → `400 "'markets' exceeds maximum of 20"`; 20 ids → 20 series | VERIFIED |
| Current book | `GET /book?token_id=` | | one book | 1,500/10 s | `timestamp` ms (snapshot) | bids/asks, `tick_size`, `min_order_size`, `neg_risk`, `last_trade_price`, `hash`. Resolved token → `404 "No orderbook exists"` | VERIFIED |
| Many books | `POST /books` body `[{token_id}]` | **max 500 items** ([prices-order-books](https://docs.polymarket.com/market-data/prices-order-books.md)) | array | 500/10 s | ms | **`GET /books?token_ids=` is in the OpenAPI but returns `400 Invalid payload`** in three encodings; use POST | VERIFIED |
| Top-of-book / last trade | `POST /prices`, `POST /midpoints`, `POST /spreads`, `GET /last-trade-price`, `POST /last-trades-prices` (≤500) | | | 500–1,500/10 s | | `GET /last-trades-prices?token_ids=` also returned 400; POST variant documented | VERIFIED (GET failure); PLAUSIBLE (POST not tested) |
| Market metadata | Gamma `GET /markets/keyset`, `GET /events/keyset` | `limit` ≤100, `after_cursor`, `closed` (default **false**), `condition_ids`, `clob_token_ids`, `slug`, `id`, `tag_id`, date ranges, `order`/`ascending` | 100/page, `next_cursor`; `offset` → 422 | `/markets` 300/10 s, `/events` 500/10 s, listing 900/10 s | ISO strings (mixed formats, §5) | Legacy offset `/markets`, `/events` "will be deprecated" ([changelog 2026-04-10](https://docs.polymarket.com/changelog/predictions.md)). OpenAPI `Market` schema lacks fields returned live (`negRisk`, `fallbackResolutionType`, `comboStatus`) | VERIFIED |
| CLOB market params | `GET /clob-markets/{condition_id}` | | single | | | tokens, tick, fees, rewards, RFQ | VERIFIED (spec) |
| Token ↔ market lookup | `GET /v2/tokens` | `token_id` (≤50) or `condition` (≤10; CTF id, neg-risk market id, V2 ids) | not paginated | /v2 800/10 s | | `module` (`v1_ctf` = CTF), `outcome_index` (on-chain slot), `clob_index` (position in Gamma list), `opposite_token_id`, `final_price`, `neg_risk_market_id`, `question_index`. Settlement fields may lag ≤ 1 min | VERIFIED |
| Resolutions | `GET /v2/resolutions` | exactly one of `question_id`, `condition` (≤20), `event_id` (≤20) | not paginated | /v2 800/10 s | `last_update_timestamp`: epoch-seconds **string** on question rows, RFC3339 on condition rows; `resolved_at` RFC3339 | `status` (initialized/posed/proposed/challenged/reproposed/disputed/resolved; active, arbitration), `was_disputed`, `payouts` (micro-USDC per share), `reporter` (UMA_OO/CHAINLINK/EOA), `resolution_source` (reported/derived), `expected_settlement_time` (estimate, since 2026-09-28) | VERIFIED |
| Holders | `GET /v2/holders?condition=` | ≤20 conditions; `limit` per outcome token (max 1000; 100 with `include_pnl=true`, one condition); `min_balance` | per-token groups; offset cursor | /v2 800/10 s | | Default amounts are **net** across outcomes; `include_pnl=true` switches to per-side gross with `avg_price`, `entry_cost_usdc`, PnL. Merge pages by `token_id` | VERIFIED |
| Leaderboards | `GET /v2/leaderboard` | `time_period` day/week/month/all, `category` (overall, Gamma category, `combos`, `esports`), `sort_by` PNL/VOLUME, `user` | ≤1000/page; cursor pins the board. **≥30,000 ranks deep** (30 pages not exhausted) | /v2 800/10 s | | Finite windows = marked equity change net of flows; `all` = realized-only; `volume` in **shares**; ties share a rank | VERIFIED |
| Biggest winners | `GET /v2/biggest-winners` | `time_period`, `category` | **capped at 500 rows** (live, week) | | `resolved_at` epoch s | one row per winning position | VERIFIED |
| User PnL | `GET /v2/user-pnl?user=` | `interval` max/all/1m/1w/1d/12h/6h; `fidelity` 1d/18h/12h/3h/1h | not paginated | "User PNL API 200/10 s" | point `timestamp` + `source_block` | cumulative atoms (realized market/LP/combo, unrealized, fees, rebates, rewards, yield, deposits/withdrawals). `source_fidelity` "1d": historical observations are daily even on a finer grid. **`user-pnl-api.polymarket.com` is retired** (live error message points to `/v2/user-pnl`) | VERIFIED |
| User stats / volume / value | `GET /v2/user-stats`, `/v2/user-volume`, `/v2/value` | `user` | single object | | | `user-stats.trades` = **distinct markets**; `user-volume` floors bounds to UTC days | VERIFIED |
| OI, live volume | `GET /v2/oi`, `/v2/live-volume?event_id=` | ≤20 ids | not paginated | | | live-volume is taker (one-side) shares | VERIFIED |
| Data freshness | `GET /v2/status` | | | 100/10 s | `computed_at`, `age_seconds` | `serving.lag_seconds` was 1–3 s during my runs | VERIFIED |
| Liquidity rewards | `GET /rewards/markets/current` (500/page, `next_cursor`, "LTE=" = last), `/rewards/markets/multi` (`page_size` ≤500, `q`, `tag_slug`, `order_by`, numeric filters), `/rewards/markets/{condition_id}` (100/page) | `sponsored` | cursor | CLOB general | `start_date`/`end_date` YYYY-MM-DD | public, no auth. Per-user `/rewards/user*` endpoints need L2 auth | VERIFIED |
| Maker rebates | `GET /rebates/current?date=&maker_address=` | both required | array | | date | public; returned `null` for a non-maker wallet | VERIFIED |
| Builder trades | `GET /builder/trades?builder_code=` | `market`, `asset_id`, `before`/`after`, `next_cursor` | | | | attributed trades per builder code | VERIFIED (spec) |
| Own orders/trades | CLOB `/data/trades`, `/data/orders`, user WS | | | | | **authenticated, own account only**, not usable for other wallets | VERIFIED (spec) |

### 1.3 What changes on 2026-10-24 (Data API v1 retirement)

Source: [/migrate/data-api-v1-to-v2](https://docs.polymarket.com/migrate/data-api-v1-to-v2.md) (VERIFIED). v1 still answered today (`GET /trades?market=…` → 200, no
`Deprecation`/`Sunset` headers).

| v1 | v2 | What breaks |
|---|---|---|
| `/positions`, `/closed-positions`, `/v1/market-positions` | `/v2/positions?status=…` | `market` → `condition`; three routes fold into one |
| `/trades`, `/activity` | `/v2/trades`, `/v2/activity` | bare arrays → `{data, pagination}`; `limit/offset` (offset capped; docs say 10,000, [changelog 2025-08-26](https://docs.polymarket.com/changelog/predictions.md) said 1,000) → cursor; camelCase → snake_case |
| `/traded` | `/v2/user-stats` (`data.trades`) | unknown user = `data: null` |
| `/holders`, `/value`, `/oi`, `/live-volume`, `/v1/leaderboard`, builders routes | `/v2/...` | envelope and casing |
| (CLOB) `/prices-history` | `/v2/prices-history` | seconds-based buckets, cursor, three window forms. The CLOB route still works and is not part of the v1 retirement notice |
| `/v1/accounting/snapshot` | stays on v1 | not retired |

Practical effect for this project: `pmr.api` already uses only `/v2/*` (plus CLOB `/prices-history`), so nothing breaks. Any third-party tool or notebook
that still calls `/trades?market=` or `/positions` stops working on 2026-10-24.

---

## 2. Real-time streams

Sources: [/market-data/realtime-data](https://docs.polymarket.com/market-data/realtime-data.md), [asyncapi.json](https://docs.polymarket.com/asyncapi.json),
[ws-live-v2 asyncapi.json](https://ws-live-v2.polymarket.com/asyncapi.json), [asyncapi-sports.json](https://docs.polymarket.com/asyncapi-sports.json),
[/migrate/rtds-to-polybolt](https://docs.polymarket.com/migrate/rtds-to-polybolt.md), [RTDS client README](https://github.com/Polymarket/real-time-data-client/blob/main/README.md),
[changelog](https://docs.polymarket.com/changelog/predictions.md). Live tests: `measure_latency.py` (run `20261017T1559`), `ws_channels_probe.py`
(`data/derived/ws_channels_probe_20261017T2129.json`), `rtds_filter_test.py` (`data/derived/rtds_filter_test_20261017T2140.json`).

### 2.1 Channel inventory

| Socket | Channel / topic | Auth | What it carries | Wallet? | Timestamps | Label |
|---|---|---|---|---|---|---|
| CLOB market `wss://ws-subscriptions-clob.polymarket.com/ws/market` | subscribe `{"assets_ids":[…],"type":"market"}`; text `PING` every 10 s | none | `book` (full snapshot), `price_change`, `last_trade_price`, `tick_size_change`; with `custom_feature_enabled`: `best_bid_ask`, `new_market`, `market_resolved` | **no** | `timestamp` ms. On `last_trade_price` it is the **match time** (§3) | VERIFIED (spec + live: 1,194 book, 75,168 price_change, 592 last_trade_price, 8 tick_size_change in 10 min on 10 assets) |
| CLOB user `wss://ws-subscriptions-clob.polymarket.com/ws/user` | own orders and fills | CLOB API key (L2) | the account's own orders/trades only | own only | ms | VERIFIED (docs: [/api-reference/wss/user](https://docs.polymarket.com/api-reference/wss/user.md)) |
| **RTDS (legacy)** `wss://ws-live-data.polymarket.com` | `activity` / `trades` and `activity` / `orders_matched`; `{"action":"subscribe","subscriptions":[{topic,type,filters}]}`; text `PING` every 5 s | **none** | every fill on the platform (firehose) or one market/event | **yes** (`proxyWallet`, `name`, `pseudonym`) | envelope `timestamp` ms (server send); payload `timestamp` **s** (neither match nor block time, §3) | VERIFIED (live) |
| RTDS (legacy) | `comments`, `crypto_prices*`, `equity_prices` | none / mixed | comments (being retired without replacement), legacy reference prices (moving to PolyBolt) | n/a | | VERIFIED (docs) |
| **PolyBolt** `wss://ws-live-v2.polymarket.com/ws` (AsyncAPI "Polymarket PolyBolt WebSocket" 2.0.0) | `price.polymarket` (filter `{asset_id}`) | **none** | top of book (`best_bid`, `best_ask`, book `hash`) per outcome token; snapshot frame then live frames with dense `seq` and `dropped` counter | no | `ts` producer ms; payload `timestamp` book ms | VERIFIED (live: `subscribed`, 1 snapshot, 8 live frames in 40 s) |
| PolyBolt | `price.crypto`, `price.equity`, `price.crypto.twap`, `price.equity.twap` | CLOB API credentials (`{"op":"auth"}`) | licensed reference prices (Chainlink default for crypto) | no | ms | VERIFIED (live: unauthenticated `price.crypto` → `{"op":"error","code":"auth_required"}`) |
| Sports `wss://sports-api.polymarket.com/ws` | push to every client, no subscribe | none | live scores: `gameId`, `leagueAbbreviation`, `homeTeam`, `awayTeam`, `status`, `score`, `period`, `elapsed`, `live`, `ended`, `turn`, `sportradarGameId` | no | **none in the frames I received** | VERIFIED (live: 30 frames in 40 s). The AsyncAPI `SportResult` schema (required `slug`, `last_update`) does not match the live frames; the SDK types on /market-data/realtime-data do |

PolyBolt has **no trades or activity channel**: the migration guide says "Keep using RTDS for the `activity` topic. It has no PolyBolt channel"
([/migrate/rtds-to-polybolt](https://docs.polymarket.com/migrate/rtds-to-polybolt.md)). PolyBolt limits per connection: 64 subscriptions, 20 subscribe frames/s,
64 KB frames, 8 auth attempts; close codes 4001/4002/4003/4008 ([asyncapi](https://ws-live-v2.polymarket.com/asyncapi.json)). RTDS documents no limits.

Status risk (VERIFIED documentation inconsistency): the [changelog of 2026-01-16](https://docs.polymarket.com/changelog/predictions.md) says RTDS docs were
updated "to reflect RTDS supports **comments** and **crypto prices** only", the RTDS client package is marked deprecated, and the 2026-09-15 entry calls RTDS
legacy. Yet the `activity` topic works and the newer migration guide tells users to keep using it. Treat it as public but semi-documented: it could be
withdrawn with little notice (PLAUSIBLE risk).

### 2.2 Is there a public stream of trades by arbitrary wallets? Yes: the RTDS `activity` firehose

Measured in run `20261017T1559` (16:00:50–16:11:02 UTC, VERIFIED):

| Item | `activity/trades` | `activity/orders_matched` |
|---|---|---|
| Rows / s (whole platform) | 54.2 | 20.0 |
| Distinct wallets in 10 min | 5,363 | 3,654 |
| Distinct markets in 10 min | 1,546 | 1,532 |
| Payload keys | `asset, bio, conditionId, eventSlug, fee (on some rows), icon, name, outcome, outcomeIndex, price, profileImage, proxyWallet, pseudonym, side, size, slug, timestamp, title, transactionHash` | same, never `fee` |
| What the rows are (joined to the Data API tape of the 5 target markets, `taker_only=false`) | **the full maker + taker tape**: 1,326/1,326 tape rows present and every RTDS row in the tape | **taker rows only**: 564/564 taker rows, 0 maker rows |
| Rows per transaction (target markets) | median 2, p90 3, max 19 (one per wallet side) | 1 |
| `fee` key | on 564/564 taker rows and 148/791 maker rows | absent |
| Rows with empty `conditionId`, `slug`, `title` | 2,485 (7.6%) | 1,098 (9.1%) |

- The empty-metadata rows still carry `asset`; 40 of 40 such asset ids I looked up with `/v2/tokens` resolved to ordinary CTF markets (`module: v1_ctf`, 28 neg-risk). Look them up; do not drop them.
- **Maker/taker role**: a row that appears in `orders_matched` is the taker; the other rows of the same `transactionHash` in `trades` are makers.
  This gives a role field that neither the Data API nor RTDS `trades` provides directly.
- No message drops were seen: every taker transaction in the window had a CLOB `last_trade_price` event (565/565) and full RTDS coverage.

### 2.3 Filters (VERIFIED live)

| Test | Result |
|---|---|
| `filters` = compact JSON `{"market_slug":"…"}` (one connection per market, 5 markets) | 1,451 rows, 0 off-target |
| Same filter with a space after the colon (`json.dumps` default) | **0 rows** in 40 s while the compact version got 318 |
| Two `market_slug` subscriptions on one connection (two frames, or two items in one frame) | **only the first is served** (290 and 343 rows of market A, 0 of market B, which got 39 rows on its own connection) |
| Wallet filters `{"proxyWallet":…}`, `{"user":…}`, `{"wallet":…}`, `{"maker":…}`, `{"taker":…}` (60 s each, one wallet active on the firehose) | **0 rows each**, while the unfiltered firehose carried 3 of that wallet's rows. Only `event_slug`/`market_slug` are documented ([README](https://github.com/Polymarket/real-time-data-client/blob/main/README.md)) |

Practical design for a wallet alert: one unfiltered `activity/trades` connection plus one `activity/orders_matched` connection, a client-side set of
watched `proxyWallet` addresses, and `/v2/tokens` for rows without metadata. Polling `/v2/trades?user=` (cache-busted) is the fallback.

---

## 3. Measured detection latency

Script `analyses/latency/measure_latency.py`, analysis `analyses/latency/analyze_latency.py`. Main run **`20261017T1559`**: 610 s, 16:00:50–16:11:02 UTC
(summary `data/derived/latency_20261017T1559_summary.json`, analysis `…_analysis.json`, raw per-source tables `…_{dataapi,polls,clobws,rtds,rtds_filtered,tape,rpc,joined,status}.parquet`,
every HTTP response in `data/raw/data-api/live/20261017/latency_20261017T1559_responses.json.gz`). Two 40-s pilots (`20261017T1552`, `20261017T1556`) gave the same picture. All VERIFIED.

### 3.1 Design

- **Markets**: the 5 most active non-rolling markets in a 60-s RTDS firehose sample (5- and 15-minute crypto up/down markets excluded because they expire mid-run):

  | Market | Category / fee type | neg_risk | `secondsDelay` | Trades seen (Data API, busted) |
  |---|---|---|---|---|
  | Will Liverpool FC win on 2026-10-17? | sports_fees_v3 | yes | 1 | 221 |
  | Brentford FC vs. Liverpool FC: O/U 3.5 | sports_fees_v3 | no | 1 | 182 |
  | Bitcoin Up or Down – October 17, 12PM ET | crypto_fees_v2 | no | – | 94 |
  | Highest temperature in Wuhan on Oct 18: 21 °C | weather_fees | yes | 0 | 49 |
  | Highest temperature in Wuhan on Oct 18: 22 °C | weather_fees | yes | 0 | 43 |

  plus the 2 most active wallets (`a5533`, `Flaznorp`) for `/v2/trades?user=`.
- **Sources run in parallel**: (a) `/v2/trades?condition=<id>&limit=50` every 2 s per market in two modes, *cached* (identical URL) and *busted*
  (plus `_=<nonce>`), and `/v2/trades?user=…&limit=50` busted; (b) CLOB market WS; (c) RTDS `activity/trades` and `activity/orders_matched` firehoses and one
  `market_slug`-filtered connection per market; (d) `/v2/status` every 30 s. Afterwards: full tapes with `taker_only=false`, and 160 random tx hashes looked up on
  `polygon-bor-rpc.publicnode.com` (`eth_getTransactionReceipt` → `eth_getBlockByNumber`).
- **Load**: 3,552 Data API requests in 610 s ≈ 58 per 10 s, against 300/10 s for `/v2/trades` ([rate limits](https://docs.polymarket.com/api-reference/rate-limits.md)). 0 errors, all `200`.
- **Bounds**: for a poll, *upper* = receive time of the first response containing the row, *lower* = send time of the previous poll that did not contain it.
- **Clock**: RTDS receive minus server envelope time was ≥ 35 ms (median 244 ms) and CLOB WS receive minus match time was ≥ 5 ms, so the local clock was not
  behind the servers by more than a few tens of ms. Data API round trip: median 141 ms (p90 184 ms).

### 3.2 Results: detection latency (seconds)

From the **match** (CLOB WS `last_trade_price.timestamp`, joined by tx hash), which is when the leader's trade actually happened:

| Source | Wallet? | n | median | p90 | p99 | max |
|---|---|---|---|---|---|---|
| CLOB market WS `last_trade_price` | no | 592 | **0.013** | 0.053 | 0.198 | 1.311 |
| RTDS `activity/orders_matched` (taker rows) | yes | 590 | **1.84** | 2.59 | 3.16 | 3.58 |
| RTDS `activity/trades` (maker + taker rows) | yes | 589 | **2.23** | 3.05 | 3.57 | 4.53 |
| Data API `/v2/trades?condition`, 2-s poll, busted: lower bound | yes | 587 | 4.51 | 6.64 | 7.59 | 8.33 |
| same, upper bound | yes | 587 | **6.72** | 8.83 | 9.77 | 10.54 |
| Data API, identical URL (CloudFront cached), upper | yes | 220 | **114.5** | 245.6 | 296.2 | 301.7 |

The metric asked for, **first-seen local UTC time minus the row's own `timestamp`** (= block time for the Data API):

| Source | n | median | p90 | p99 | max | note |
|---|---|---|---|---|---|---|
| `/v2/trades?condition` busted, upper | 589 | **4.59** | 6.46 | 7.42 | 7.94 | lower bound 2.37 / 4.23 / 5.23 / 5.74; per market medians 4.33–4.86 |
| `/v2/trades?condition` cached, upper | 222 | **111.96** | 256.36 | 299.29 | 301.53 | 176/222 rows > 60 s late; `age` header median 150 s, max 300 s |
| `/v2/trades?user` busted, upper | 344 | **3.56** | 5.14 | 5.99 | 6.15 | lower bound 1.33 / 2.91 / 3.75 / 3.83 |
| RTDS `trades`, receive − payload `timestamp` (firehose, all markets) | 32,532 | **0.77** | 1.18 | 1.35 | 1.65 | |
| RTDS `orders_matched`, receive − payload `timestamp` | 12,010 | 0.70 | 1.12 | 1.25 | 1.42 | |
| RTDS filtered connections, receive − `timestamp` | 1,451 | 0.72 | 1.18 | 1.36 | 1.43 | filtering adds no delay |

Relative to the **block timestamp** from the RPC (160 txs): RTDS receive − block = median **+0.02 s** (−0.89 to +1.07); CLOB WS receive − block = median **−2.15 s**
(−3.69 to −1.03); Data API busted first-seen − block = median **4.52 s** (p90 6.35, max 7.28). Head-to-head on the same trade: Data API busted first-seen minus RTDS
first-seen = median 4.47 s (p90 6.50); RTDS minus CLOB WS = median 2.20 s (p90 3.04). `/v2/status` reported `serving.lag_seconds` of 1–3 s (n = 20).

Other observations: 3 of 2,072 busted polls returned 50 rows that were all new, so a 50-row page every 2 s can occasionally overflow on a busy market
(use `limit` up to 1,000 or follow the cursor). All 160 sampled transactions went to the two CLOB exchange contracts listed on
[/resources/contracts](https://docs.polymarket.com/resources/contracts.md): `0xE111…B996B` CTF Exchange (74) and `0xe222…0F59` Neg Risk CTF Exchange (86).

### 3.3 Timestamp semantics (VERIFIED, n = 160 transactions)

| Field | Meaning measured |
|---|---|
| Data API `/v2/trades` `timestamp` (s) | **equals the Polygon block timestamp in 160/160 cases** (difference 0 s), as the OpenAPI says |
| CLOB WS `last_trade_price.timestamp` (ms) | off-chain **match time**; the block follows a median 2.17 s later (p10 1.32, p90 2.94, range 1.04–3.70) |
| RTDS payload `timestamp` (s) | **neither**: median 1 s *before* the block timestamp (range −2 to 0) and 2 s after the floored match time (range 0–3). It is probably the time the settlement transaction was submitted or seen (PLAUSIBLE, undocumented) |
| RTDS envelope `timestamp` (ms) | server send time (receive − envelope = 35–766 ms) |

So: **`timestamp` is block time, not match time**, and block time lags match time by about 2 s. A backtest that enters "at the leader's timestamp"
is already about 2 s behind the leader and still ahead of anything a follower can actually see.

### 3.4 What this means for copy-trading (analysis)

- Best public detection is about **2 s after the leader's match** (RTDS), or 5–7 s with correct Data API polling. A follower's order then adds a round trip
  (~0.1–0.2 s here) plus any matching delay: 150 ms taker delay on crypto markets since 2026-09-04 ([changelog](https://docs.polymarket.com/changelog/predictions.md)).
  **[corrected by verifier 2026-10-17]** In practice this is only the markets with `itode:true` on `/clob-markets`: 5m/15m/hourly crypto up/down and some single-stock/ETF up/down markets. It does not apply to 4h or daily crypto up/down markets
  and Gamma `secondsDelay` (1 s on both EPL markets above).
- By then the anonymous print has been on the CLOB WS for about 2 s, so anyone watching the book (or the same RTDS firehose) can already have reacted. Copying
  is only plausible where the leader's edge decays over minutes or longer, not seconds.
- **A poller without cache-busting is up to 5 minutes late** and would make a live copy strategy much worse than its backtest. Cache-busting is undocumented
  behaviour (§1.1); it could stop working.
- Realistic backtest rule: entry no earlier than block time + 1 s (RTDS) or + 5 s (poll), at the then-current ask plus slippage. Without historical books (§4),
  the next trades on the tape after that time are the best available proxy, and they are not executable prices.

Limitations: one 10-minute window on a Saturday afternoon (UTC) from one sandbox IP in an unknown region (CloudFront `x-cache` shows a nearby edge);
5 markets. Latency during peak US evening sports, or from other regions, was not measured.

**Independent re-run (verifier, 2026-10-17 21:58–22:01 UTC; `analyses/verification/v07_latency_rerun.py`, `v11_poll_latency.py`).**
Same sandbox, 180 s, with the top 10 assets picked from the firehose. The re-run reproduces the numbers above:

| Measure | Re-run |
|---|---|
| RTDS firehose rate | 54.0 rows/s, every row with `proxyWallet` |
| CLOB WS `last_trade_price` after match | median 0.017 s (n=493) |
| RTDS `activity/trades` after match | median 2.21 s, p90 2.96 s, max 3.87 s (n=489) |
| Match → block | median 2.42 s (n=40) |
| RTDS payload `timestamp` vs block | 1 s before block (median −1 s) |
| Busted 2-s poll, first seen after row timestamp | median 4.29 s (n=12) |
| Identical cached URL | no new row seen within 120 s |

The wallet filters `{"proxyWallet": …}` (checksummed and lowercase) and `{"user": …}` returned 0 rows, while the
firehose carried 16 and 53 of that wallet's rows. A `market_slug` positive control returned 734/734 matching rows. Not
re-tested: peak hours and other regions.

---

## 4. Historical order books and fill datasets

Nothing was bought, downloaded in bulk or signed up for. Dataset rows are labelled PLAUSIBLE when the only evidence is the provider's own description
(dataset card, vendor page); "live" means I checked the listing or file index today.

### 4.1 Official: no historical order-book endpoint (VERIFIED)

- The CLOB OpenAPI has only current-state book routes: `GET /book`, `POST /books`, `/price(s)`, `/midpoint(s)`, `/spread(s)`, `/last-trade(s)-price(s)`
  ([clob-openapi.yaml](https://docs.polymarket.com/api-spec/clob-openapi.yaml), [/market-data/prices-order-books](https://docs.polymarket.com/market-data/prices-order-books.md)).
  A resolved token's `/book` returns `404 "No orderbook exists"` (live).
- Historical *prices* exist (`/v2/prices-history`, CLOB `/prices-history`, `/batch-prices-history`), but they are trade/mid series without bid, ask or depth (§1.2).
- PolyBolt `price.polymarket` and the CLOB market WS give live top of book and depth; anyone who wants history must record it.

### 4.2 Third-party historical order-book / tick data

| Source | What | Coverage | Granularity | Price / licence | Label |
|---|---|---|---|---|---|
| [Telonex](https://telonex.io/data/polymarket) | trades, quotes (every best bid/ask change), book snapshots at 5 / 25 / full depth, on-chain fills, oracle prices | trades/quotes/books from **2025-10-11**; on-chain fills from Nov 2022; crypto resolution prices from 2026-04-02 | tick-by-tick from the WS, daily Parquet via REST/SDK, published within hours of UTC midnight | Free trial 5 downloads; **$99/month** single exchange, $199/month Pro; "personal use licence", commercial = Enterprise ([pricing](https://telonex.io/pricing)) | PLAUSIBLE (vendor) |
| [Tardis.dev](https://docs.tardis.dev/historical-data-details/polymarket) | `trades`, `book_ticker`, `incremental_book_L2`, `quotes`, `book_snapshot_5`, `book_snapshot_25`; captures `book`, `price_change`, `last_trade_price`, `best_bid_ask`, `tick_size_change`, `new_market`, `market_resolved`, `sport_result` | from **2026-05-25** | WS capture with local timestamps (London, GCP europe-west2); symbols = CLOB token ids | first day of each month free without API key; price not stated on the page (third-party listings disagree) | PLAUSIBLE (vendor docs) |
| PMXT archive (`archive.pmxt.dev`, API [`fetchOrderBook`](https://www.pmxt.dev/docs/api-reference/fetch-order-book.md)) | raw CLOB WS event stream as Parquet (free bulk files); API returns reconstructed full L2 at or before a ms timestamp, ≤1,000 snapshots per range call | v1 archive covered about half of markets until 2026-04-12; v2 full coverage from 2026-04-13; **reported to have stopped publishing on 2026-08-10** (per the Joseph3222 card below) | tick events | bulk files CC BY 4.0 (per Joseph3222 card); API needs a PMXT key; price not stated | PLAUSIBLE. `archive.pmxt.dev` returned 503 / connection reset from this sandbox today |
| [Joseph3222/polymarket-orderbook](https://huggingface.co/datasets/Joseph3222/polymarket-orderbook) (HF) | normalised pmxt stream (`book`, `price_change`, `last_trade_price`, `tick_size_change`) plus **1-minute full-depth L2 snapshots** | **2026-02-22 → 2026-08-10**; 2026-06-12 → 06-17 missing; 2026-08-10 partial; before 2026-04-13 only about half of markets | tick (~1.18 TB) and 1-min (~192 GB), daily Parquet | CC BY 4.0, free | PLAUSIBLE (card); listing last modified 2026-09-02 (live) |
| [Houroux/polymarket-l2-history](https://huggingface.co/datasets/Houroux/polymarket-l2-history) (HF) | append-only CLOB WS messages for **liquidity-rewards-eligible markets**, plus derived `analytics/book_levels` | first files 2026-07-22; **still updating** (last modified 2026-10-17 21:22 UTC, live) | WS messages, gzip JSONL | licence "other" (source-platform terms apply) | PLAUSIBLE (card + live listing) |
| [trentmkelly/polymarket_historical_data](https://huggingface.co/datasets/trentmkelly/polymarket_historical_data) (HF) | `market_snapshots` (best bid/ask + full book JSON), `order_book_depth` (levels), `top_holders` | from **2026-07-23**; **still updating** (files dated 2026-10-17 21:22, live) | about every 5 minutes | CC BY 4.0, free | PLAUSIBLE (card + live listing) |
| [DineshKumar8399/polymarket-orderbook-dataset](https://huggingface.co/datasets/DineshKumar8399/polymarket-orderbook-dataset) (HF) | 484,045,253 quote rows (bid/ask/mid), 314,123 markets, 187,094 settlement labels | **2026-07-10 → 2026-09-13** | snapshots (interval not stated in the card) | CC BY 4.0, free | PLAUSIBLE (card) |
| Crypto up/down specialists on HF, e.g. `marketlens/polymarket-btc-5m-l2-depth`, `polyorderbooks/polymarket-crypto-btc-5min-250ms-l2`, `mileswangs/polymarket-btc-updown-5m-orderbook-tick-data` | L2 books for 5/15-min crypto markets only | various 2026 windows | down to 250 ms | mostly CC BY 4.0 | PLAUSIBLE (HF search listing, [huggingface.co/datasets?search=polymarket](https://huggingface.co/datasets?search=polymarket): 184 datasets) |
| PolyOrderbooks ([pm.wiki entry](https://pm.wiki/projects/polyorderbooks)), Apify actor [dirtycode/polymarket-api](https://apify.com/dirtycode/polymarket-api) | crypto-market books every second (PolyOrderbooks); archived snapshots at $0.002 each (Apify) | plan-dependent | | paid | UNSUPPORTED beyond search snippets (leads only) |
| Open-source collectors | no maintained open-source recorder that writes Parquet was found; client libraries exist (e.g. [polyws](https://pypi.org/project/polyws/)) | | | | PLAUSIBLE (search) |

### 4.3 On-chain fill datasets and whether they cover Protocol V2

Protocol V2 here means the exchange contracts in production since **2026-04-28** (pUSD collateral; Goldsky docs and the wzsg card give the date). Exchange addresses:
CTF Exchange `0xE111180000d2663C0091e4f400237545B87B996B`, Neg Risk CTF Exchange `0xe2222d279d744050d28e00520010520000310F59`; PositionManager markets trade on
ExchangeV3 `0xe3333700cA9d93003F00f0F71f8515005F6c00Aa` ([/resources/contracts](https://docs.polymarket.com/resources/contracts.md), VERIFIED).

| Source | Coverage | V2 fills? | Access | Label |
|---|---|---|---|---|
| **CryptoHouse** `polymarket.orders_filled` | 257,649,337 rows, **ends 2026-01-05 22:05:45** (block 81,265,743), re-queried today | **no** | free SQL, `crypto-clickhouse.clickhouse.com`, user `crypto` | VERIFIED |
| [SII-WANGZJ/Polymarket_data](https://huggingface.co/datasets/SII-WANGZJ/Polymarket_data) | 2022-11-21 → **2026-10-04 23:59:59**; 2.03B `orderfilled` rows, 1.27B processed `trades`, 4.05M markets; 279 GB | **yes**: "two V2 exchange contracts (live since 2026-04-28) are now covered"; earlier snapshots missed V2 sell-side fills and had ~0.16% duplicate user rows | free (MIT badge) | PLAUSIBLE (card; listing modified 2026-10-05, live) |
| [TimeSeventeen/Polymarket-v2](https://huggingface.co/datasets/TimeSeventeen/Polymarket-v2) | `OrderFilled/`, `daily_aligned/`, `daily_aligned_multi/` daily files to **2026-10-16** (593 files) | **yes** | CC BY 4.0 | PLAUSIBLE (card + live listing) |
| [TimeSeventeen/Polymarket-v1](https://huggingface.co/datasets/TimeSeventeen/Polymarket-v1) | 2022-11-21 → 2026-04-28, 1.2B `OrderFilled` rows, cleaned layers with relayer/router rows removed, CTF events | v1 only | CC BY 4.0 | PLAUSIBLE (card) |
| [wzsg/polymarket-orderfilled-v2](https://huggingface.co/datasets/wzsg/polymarket-orderfilled-v2) | 575,630,861 rows, **2026-04-28 11:04:48 → 2026-08-03 23:47:33** (blocks 86,127,122–91,397,218) | yes (both V2 exchanges) | card says "updated daily" but last stats 2026-08-04 | PLAUSIBLE |
| [moose-code/polymarket-onchain-v1](https://huggingface.co/datasets/moose-code/polymarket-onchain-v1) (Envio) | Sep 2020 → Apr 2026: fills, matches, splits, merges, redemptions, neg-risk conversions, positions | v1; separate open-source [polymarket-v2-indexer](https://github.com/enviodev/polymarket-v2-indexer) (link from the card; GitHub returned 403 from the sandbox) | CC BY 4.0 | PLAUSIBLE |
| [vgregoire/polymarket-users](https://huggingface.co/datasets/vgregoire/polymarket-users) | 2022-11-11 → 2026-03-29: reconciled end-user trades, daily PnL per user | no | CC BY 4.0 | PLAUSIBLE |
| **Dune** `polymarket_polygon.market_trades` etc. | v1 + v2 exchanges, combos (v3); refresh ~1 h | **yes** ([market_trades](https://docs.dune.com/data-catalog/curated/prediction-markets/polymarket/market_trades)) | Dune account; dune.com returns 403 from this sandbox | PLAUSIBLE (docs) |
| **Allium** `polygon.predictions.trades` | `exchange_type` CTFExchange, NegRiskCTFExchange, **CTFExchangeV2, NegRiskCTFExchangeV2, ComboExchange**, FPMM ([trades](https://docs.allium.so/historical-data/supported-blockchains/evm/polygon/predictions/trades)) | **yes** | commercial | PLAUSIBLE (docs) |
| **Goldsky** | Turbo Pipelines with "v2 Polymarket datasets" (orders filled/matched, positions, balances, OI), streamed to your own DB; public subgraphs "incomplete or incorrect" since 2026-04-28 ([docs](https://docs.goldsky.com/chains/polymarket.md), [product page](https://goldsky.com/chains/polymarket)) | yes | account; $100 free credit, then usage-based | PLAUSIBLE (vendor) |
| "Goldsky Edge Data API" | no product with that name found on [goldsky.com/chains/polymarket](https://goldsky.com/chains/polymarket) or in [docs.goldsky.com/llms.txt](https://docs.goldsky.com/llms.txt); "Edge" there is **Edge RPC** (JSON-RPC endpoints) | – | – | UNSUPPORTED |
| Polymarket Data API `/v2/trades?condition=` | full tape per market, 3-year window, incl. V2-era markets | yes | free, rate-limited | VERIFIED (§1) |
| Polygon public RPC (`polygon-bor-rpc.publicnode.com`) | raw `OrderFilled`/`OrdersMatched`/`FeeCharged` logs | yes | free, slow for bulk | VERIFIED |

**Answer**: yes, several public datasets cover V2 fills (SII-WANGZJ to 2026-10-04, TimeSeventeen v2 to 2026-10-16, wzsg to 2026-08-03, Dune, Allium, Goldsky pipelines).
None of them was downloaded or validated here; before use, check row counts against the Data API tape for a few markets.
Whether any of them covers ExchangeV3 (PositionManager markets) was not established (all 3,500 markets I sampled in Gamma were `version: v1`, §5).

---

## 5. Data pitfalls

| # | Pitfall | Evidence | What to do | Label |
|---|---|---|---|---|
| 1 | **Account wallet ≠ signer.** `proxy_wallet` / `proxyWallet` in the Data API and RTDS is the trading (smart) wallet. Types: **Deposit Wallet** (default for every account wallet deployed on or after **2026-05-04**; UUPS proxy before the 2026-06-29 upgrade, beacon proxy after), legacy **Proxy Wallet** (Magic/Google), legacy **Safe** (MetaMask, Rabby…), and direct **EOA** trading (`signature_type` 0/1/2/3 = EOA, POLY_PROXY, GNOSIS_SAFE, DEPOSIT_WALLET) | [/trading/wallets-auth](https://docs.polymarket.com/trading/wallets-auth.md) | Key every wallet analysis on the account wallet. One person can run many wallets, and Deposit Wallet **Session Keys** (beta) let a separate signer trade for an account ([/trading/session-keys](https://docs.polymarket.com/trading/session-keys.md)), so signer addresses do not identify people. Wallet age: accounts created after 2026-05-04 are all Deposit Wallets, so wallet type alone says little | VERIFIED (docs) |
| 2 | **Non-trade inventory changes.** `/v2/activity` types seen live for the 25 top weekly-volume wallets (last 1,000 rows each, deposits included): TRADE 22,561, REDEEM 1,427, MERGE 598, DEPOSIT 71, TAKER_REBATE 28, CONVERSION 24, MAKER_REBATE 21, REWARD 15, WITHDRAWAL 11, YIELD 5; TIP is opt-in; DEPOSIT/WITHDRAWAL are hidden unless `exclude_deposits_withdrawals=false` | `data/derived/activity_types_probe_20261017T1558.json` | PnL from TRADE rows alone is wrong for anyone who splits, merges, converts or redeems. A market maker who SPLITs and sells both sides looks like a short seller in the trade tape | VERIFIED |
| 3 | **How the rows look.** SPLIT: `price` 0.5 in the example row, no `token_id`, `outcome_index` 999, `size` = `usdc_size` = sets created. MERGE: `price` 0, `outcome_index` 999, `size` = sets merged. REDEEM: per outcome since 2026-08-10 (`outcome`, `outcome_index` set, `price` 0, `usdc_size` = payout; [changelog](https://docs.polymarket.com/changelog/predictions.md)). CONVERSION: `size` = `usdc_size`, no token or outcome. REWARD / MAKER_REBATE / TAKER_REBATE / YIELD: no `condition_id` (daily batch credits). TIP: `side` `IN` | example rows in the probe file | Model each type explicitly; treat `outcome_index` 999 as "not an outcome" | VERIFIED |
| 4 | **Neg-risk conversions.** A NO share in one market of a neg-risk event converts into one YES share of every other market in the event (plus collateral where applicable) ([/concepts/negative-risk](https://docs.polymarket.com/concepts/negative-risk.md)). The activity row does not say which outcomes were converted | probe rows | For exact inventories use on-chain `PositionsConverted` (CTF) / `PositionConverted` (NegRiskModule) logs ([/resources/onchain-position-data](https://docs.polymarket.com/resources/onchain-position-data.md)) or `/v2/positions` snapshots | VERIFIED (docs + rows) |
| 5 | **Maker vs taker rows.** `/v2/trades` defaults to `taker_only=true`, which returns **exactly one row per transaction** (2,455 rows / 2,455 txs in the run's tapes). `taker_only=false` adds maker rows (4,285 rows). No role field | `latency_20261017T1559_tape.parquet` | Role = in the taker-only set or not; live, RTDS `orders_matched` = taker rows (564/564). Volume from `taker_only=false` counts each fill twice (taker + maker side) | VERIFIED |
| 6 | **No unique fill key; "duplicates".** In the full tape a (tx, wallet) pair had 2–10 rows 162 times (different prices, or both outcome tokens of a complementary match); 14 rows were identical on (tx, wallet, token, side, price, size). Data API trade rows carry no log index or fill id | tape parquet; trade row schema in `endpoint_probe_20261017T1545.json` | Do not deduplicate on those columns. Exact accounting needs on-chain `OrderFilled` with `log_index`. On chain, each maker order gets one `OrderFilled` plus one for the taker order whose counterparty is the exchange, so summing all events double counts ([SII-WANGZJ card](https://huggingface.co/datasets/SII-WANGZJ/Polymarket_data) also reports ~0.16% duplicate rows fixed in its 2026-10-05 release; [TimeSeventeen card](https://huggingface.co/datasets/TimeSeventeen/Polymarket-v1) warns raw `OrderFilled` includes relayer/router rows) | VERIFIED (own data); PLAUSIBLE (cards) |
| 7 | **Timestamp precision and meaning.** Data API / activity: integer seconds = block time. CLOB WS: ms = match time (≈2.2 s earlier). RTDS payload: seconds, about 1 s before the block. `/book`: ms snapshot time. Gamma: ISO strings in mixed formats. `/v2/resolutions` `last_update_timestamp`: epoch-seconds string on question rows, RFC3339 on condition rows. Many fills share one second and rows expose no intra-second sequence | §3.3, §1.2 | Order within a second by on-chain log index when it matters; never compare match-time and block-time series without the ~2 s offset | VERIFIED |
| 8 | **CDN-cached responses.** `/v2/trades` and Gamma `/markets/keyset` are cached for up to 300 s at the edge; `/v2/holders` 120 s; price history 90 s | §1.1, §3.2 | Add a nonce parameter when freshness matters (undocumented); record the `age` header | VERIFIED |
| 9 | **RTDS rows without metadata.** 7.6% of `activity/trades` rows have empty `conditionId`, `slug`, `title`; all 40 looked up were ordinary CTF markets | §2.2 | Resolve `asset` via `/v2/tokens` | VERIFIED |
| 10 | **Gamma status flags.** In 2,000 markets closed with `endDate` 2026-10-10…12: `active` = **true** for all 2,000, `archived` false, `restricted` true, `acceptingOrders` false, `umaResolutionStatus` `resolved`. `umaResolutionStatuses` is a list such as `["proposed","proposed"]` (1,974), not a clean timeline; 1 market had a dispute (Gemini Pro release date). Gamma omits closed markets unless `closed=true` | `gamma_status_sample_20261017T1557.parquet` | Use `closed`, `acceptingOrders`, `closedTime` and resolution fields; never `active` | VERIFIED |
| 11 | **Non-0/1 settlements.** 2 of 2,000 settled 50-50 (`outcomePrices` `["0.5","0.5"]`: `nfl-nyg-was-2026-10-11`, `kbo-lot-kt-2026-08-08`) | same | Backtests must read the actual payout vector, not assume 0/1 | VERIFIED |
| 12 | **`/v2/resolutions` payouts missing.** Of 400 sampled markets, all `status: resolved`, but **`payouts` was `null` for 175 (44%)**; where present it matched Gamma `outcomePrices` (225/225, units: micro-USDC per share, 1,000,000 = 1) | same | Prefer Gamma `outcomePrices` (closed markets), `/v2/tokens` `final_price` or on-chain payout numerators; treat `null` as unknown | VERIFIED |
| 13 | **Archived / removed markets.** `/v2/positions` hides archived markets unless `include_archived=true`; Gamma has an `archived` flag. CryptoHouse `polymarket.assets` covers only ~45k tokens versus 2.67M in `token_id_condition`, so metadata joins there lose rows | §1.2; CryptoHouse `system.tables` (live) | Pass `include_archived=true` for complete wallet histories; join metadata via `/v2/tokens` or Gamma `clob_token_ids` | VERIFIED (positions flag from spec); PLAUSIBLE (impact) |
| 14 | **Two position systems.** Gamma `version` `v1` = Conditional Tokens (`tokenId`), `v2` = PositionManager (`positionId`, ExchangeV3). All 2,000 closed and the top 1,500 open markets by 24 h volume were `v1` today; `/v2/tokens` `module` tells them apart (`v1_ctf` vs V2 modules). Combos use the PositionManager and have their own ids | [/resources/onchain-position-data](https://docs.polymarket.com/resources/onchain-position-data.md); live Gamma count | Branch on `version`/`module`; do not mix ids between systems | VERIFIED |
| 15 | **Pagination caps.** `/v2/*` `limit` ≤ 1,000, cursor only (offset → 400). Leaderboard ≥ 30,000 ranks (30 pages, not exhausted). Biggest winners **capped at 500**. Holders: the top market returned 482 holders in one page and reported no more. Bare `/v2/trades`: current + previous month only. `?condition=` tapes: fixed 3-year window. v1 offset cap 10,000 (docs) or 1,000 (2025-08-26 changelog), gone on 2026-10-24. Gamma keyset ≤ 100 per page | `pagination_caps_20261017T1601.json`, §1 | Walk cursors to `null`; re-send filters on every page; expect board walks to skip or repeat rows across refreshes | VERIFIED |
| 16 | **Fees are not in Data API trade rows.** The row schema has no fee field; RTDS `fee` appears on taker rows and on a minority of maker rows | §2.2 | Compute fees from the market's `feeSchedule` or read on-chain `FeeCharged`. **[corrected by verifier 2026-10-17]** On-chain `OrderFilled.fee` / `FeeCharged` include **builder fees**, which are flat 0–100 bps of notional for takers and 0–50 bps for makers ([builders/fees](https://docs.polymarket.com/programs/builders/fees.md)). Verified on a fee-free market: non-zero fees only on `builder≠0` fills, at exactly 25/50/100 bps. So an on-chain fee is not always the platform fee, and a "maker" row with a fee is plausibly a builder maker fee | VERIFIED |
| 17 | **Order delays.** `secondsDelay` (1 s on the EPL markets measured) and the 150 ms crypto taker delay ([changelog 2026-09-04](https://docs.polymarket.com/changelog/predictions.md)) delay matching, so match time is later than order submission | §3.1 | Include them in any execution-latency model. Read `sd` and `itode` per market from `/clob-markets/{condition_id}` **[corrected by verifier 2026-10-17: `itode` covers 5m/15m/1h crypto up/down and some equity up/down only, not all crypto]** | VERIFIED |

---

## 6. Contradictions with CONTEXT.md and earlier notes

| CONTEXT.md / earlier claim | What I found | Label |
|---|---|---|
| "`/v2/prices-history` returned empty for a resolved token" | For resolved token `98258…0714`, `interval=max` returned **114 points** (3-h buckets), an old 25-h window 2 points, `as_of` 1 point (`endpoint_probe_20261017T1545.json`). The route does serve resolved markets, at coarse resolution once fine tiers expire. The empty result may predate the 2026-10-07 fix ("`as_of` now serves an asset whose history lives only in the finer tiers", [changelog](https://docs.polymarket.com/changelog/predictions.md)) | VERIFIED |
| "`start`/`end` filters appeared to be ignored on one test" | Ignored **by design** when `/v2/trades` is anchored on `condition`/`event_id` (fixed 3-year window); honoured with `user` (OpenAPI + live) | VERIFIED |
| Activity types: TRADE, REDEEM, TAKER_REBATE, MAKER_REBATE, REWARD; SPLIT/MERGE/CONVERSION per docs | Also **YIELD**, **TIP** (opt-in), **DEPOSIT**/**WITHDRAWAL** (hidden by default); SPLIT, MERGE and CONVERSION seen live | VERIFIED |
| "Rows have no explicit maker/taker role field" | Correct, but the role is recoverable: `taker_only=true` returns exactly the taker row of each tx, and RTDS `orders_matched` = taker rows | VERIFIED |
| RTDS docs (changelog 2026-01-16): RTDS supports "comments and crypto prices only" | The `activity` topic is live, public and complete; the newer migration guide says keep using RTDS for `activity` | VERIFIED (inconsistency in Polymarket's own docs) |
| AsyncAPI sports spec: `slug` required, `last_update` timestamp | Live frames have `gameId`, `leagueAbbreviation`, … and **no** `slug` or timestamp | VERIFIED |
| Pilot run `20261017T1556` coverage table said `orders_matched` rows were maker rows | Artefact: its taker-only tape pull returned 0 rows (40-s window), so every row was classed as maker. The 10-min run (`20261017T1559`) shows `orders_matched` = taker rows 564/564 | VERIFIED |

## 7. Open questions

1. **RTDS `activity` lifetime and limits.** It has no PolyBolt replacement, its docs were trimmed in January 2026, and no connection or subscription limits are documented. Will it be retired, and with what notice?
2. **Meaning of the RTDS payload `timestamp`** (1 s before block, 2 s after match): submission time? Undocumented.
3. **Region and load dependence.** One 10-minute Saturday window from one sandbox IP. Repeat from the trader's own location, during peak US evening sports, and for 1–2 h.
4. **Is cache-busting tolerated?** It is undocumented and shifts load to the origin. Polymarket could start ignoring unknown parameters in the cache key.
5. **`/v2/resolutions` `payouts: null`** on 44% of resolved markets: bug or semantics (for example markets resolved through a different path)?
6. **Protocol V2 PositionManager (ExchangeV3) markets**: none appeared in 3,500 Gamma markets sampled. When they appear, do the Data API and the third-party datasets cover them the same way?
7. **Third-party datasets not validated**: row counts versus the Data API tape, V2 coverage of Telonex/Tardis, Tardis pricing, pmxt archive status (unreachable today), licence terms for derived research.
8. **Holders depth**: is 482 the complete holder list of the top market, or a server cap?
