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

Scripts (read-only) in `analyses/latency/`:

| Script | What it does | Output |
|---|---|---|
| `measure_latency.py` | 10-min live run: Data API polling (cached and cache-busted URLs), CLOB market WS, RTDS `activity` firehose and filtered streams, `/v2/status`, post-run tapes, Polygon RPC block times | `data/derived/latency_<UTC>_*.parquet`, `_summary.json`; raw responses in `data/raw/data-api/live/<date>/latency_<UTC>_responses.json.gz` |
| `analyze_latency.py` | Offline analysis of one run (joins by tx hash, coverage, timestamp semantics) | `data/derived/latency_<UTC>_analysis.json` |
| `endpoint_probe.py` | One call per endpoint: shape, page size, behaviour on resolved markets, v1 status | `data/derived/endpoint_probe_20261017T1545.json` |
| `pagination_caps_probe.py` | Walks boards and holder lists to their real depth | `data/derived/pagination_caps_*.json` |
| `activity_types_probe.py` | Example rows for every `/v2/activity` type among top-volume wallets | `data/derived/activity_types_probe_20261017T1558.json` |
| `gamma_status_sample.py` | Status fields of 2,000 markets closed 2026-10-10..12, plus `/v2/resolutions` | `data/derived/gamma_status_sample_20261017T1557.parquet` |

---

## 0. Summary for strategy design

LATENCY_SUMMARY_PLACEHOLDER

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

REALTIME_PLACEHOLDER

---

## 3. Measured detection latency

LATENCY_PLACEHOLDER

---

## 4. Historical order books and fill datasets

DATASETS_PLACEHOLDER

---

## 5. Data pitfalls

PITFALLS_PLACEHOLDER

---

## 6. Contradictions with CONTEXT.md and earlier notes

CONTRA_PLACEHOLDER

## 7. Open questions

OPEN_PLACEHOLDER
