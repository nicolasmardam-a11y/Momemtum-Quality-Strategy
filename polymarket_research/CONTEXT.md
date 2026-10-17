# Research context (as of 2026-10-17)

Shared ground truth for every research agent. Facts here were verified directly
against live endpoints or docs.polymarket.com on 2026-10-17 unless marked otherwise.
If you find something that contradicts this file, say so explicitly in your notes.

## Ground rules

- Read-only public data only. No wallet connection, private keys, API keys for trading,
  order placement, paid data purchases or paid infrastructure.
- Never fabricate papers, endpoints, wallet links, numbers or backtest results. If data is
  missing, say exactly what is missing and how it changes the conclusion.
- Label every claim: **VERIFIED** (you inspected the primary source or data yourself),
  **PLAUSIBLE** (consistent with evidence but not directly verified), **UNSUPPORTED**.
- Do not infer anyone's real-world identity or allege insider information from wallet data.
- No look-ahead: any backtest selects using only information timestamped before the decision.
- Prices from `/prices-history` or last trades are not executable prices. Say so when you use them.

## Code and data conventions

- Shared client: `pmr/` (`from pmr import api, fees`). Run Python from
  `/home/user/Momemtum-Quality-Strategy/polymarket_research` so `pmr` imports.
  `pmr.http.request_json` throttles per host and stores every raw response with URL, params,
  UTC fetch time and status under `data/raw/` (provenance). Use `cache=True` only for immutable history.
- Put scripts in `analyses/<topic>/`, derived datasets in `data/derived/` (parquet), findings in `notes/<area>/<topic>.md`.
- The repo-root `.gitignore` ignores any path containing `token`, `secret` or `credential`, and `*.jsonl`.
  Do not use those substrings in file names (e.g. use `asset_ids.py`, not `tokens.py`).
- Several agents share one IP. Do not raise `PMR_RATE_SCALE` above 2.
- Installed: pandas 3, numpy, pyarrow, scipy, statsmodels, matplotlib, requests, websockets.

## Platform facts (verified 2026-10-17)

- **Collateral is pUSD** (Polymarket USD). The platform migrated to **Protocol V2** in 2026
  (docs: /migrate/polymarket-v2/*, /concepts/pusd). Positions span Conditional Tokens and a PositionManager.
- **Taker fees** (docs /trading/fees): `fee = shares × rate × p × (1−p)`, takers only, makers never pay.
  Rates: Crypto 0.07; Sports 0.05; Finance/Politics/Mentions/Tech 0.04; Economics/Culture/Weather/Other 0.05;
  Geopolitics 0. Per-market Gamma fields `feesEnabled`, `feeType` (e.g. `sports_fees_v3`) and
  `feeSchedule` `{rate, exponent, takerOnly, rebateRate}` are authoritative for a market.
- **Maker Rebates**: a share of taker fees (Crypto 20%, Sports 15%, others 25%) redistributed daily
  per market, pro rata to the maker's fee-equivalent of filled liquidity.
- **Taker Rebate Program** (live since 2026-05-28): tier by 30-day weighted volume
  `wV = notional × (1 − entry price) × category weight`; rebate 3% (Bronze, $2k wV) to 50% (Obsidian, $10M wV).
- **Liquidity Rewards** program also exists (docs /programs/liquidity-rewards; CLOB `/rewards/markets/*`).
  Gamma markets carry `rewardsMinSize`, `rewardsMaxSpread`, `holdingRewardsEnabled`.
- Gamma markets also carry `secondsDelay` (order delay on some sports markets), `gameStartTime`,
  `umaResolutionStatus(es)`, `fallbackResolutionType`, `negRisk`, `orderPriceMinTickSize`, `orderMinSize`.
- New products exist: **Combos** (multi-leg RFQ positions with collateral return) and **Perps**.

## Data access facts (verified 2026-10-17)

- **IP rate limits** (docs /api-reference/rate-limits; Cloudflare throttles rather than rejects):
  Data API v2 800 req/10 s overall, `/v2/trades` 300/10 s, `/v2/activity` 200/10 s; Gamma `/markets` 300/10 s;
  CLOB `/book` 1,500/10 s, `/books` 500/10 s, `/prices-history` 1,000/10 s.
- **Data API v1 is retired 2026-10-24.** Use `/v2/*` (cursor pagination via `pagination.next_cursor`,
  `limit` ≤ 1000, snake_case fields). v2 routes: activity, trades, positions (status OPEN/REDEEMABLE/
  REDEEMABLE_LOST/MERGEABLE/CLOSED), user-stats, user-pnl, user-volume, value, holders, leaderboard,
  biggest-winners, prices-history, resolutions, tokens, status, oi, live-volume, approvals.
- `/v2/trades?condition=<id>` returns a market's full trade tape incl. 2025 markets (tested).
  Default is taker-side only; `taker_only=false` adds maker fills. Rows have no explicit maker/taker
  role field. `start`/`end` filters appeared to be ignored on one test, so check before relying on them.
- `/v2/trades?user=` and `/v2/activity?user=` give full wallet histories (activity types seen:
  TRADE, REDEEM, TAKER_REBATE, MAKER_REBATE, REWARD; also SPLIT/MERGE/CONVERSION per docs).
- `/v2/user-stats?user=` returns `trades` = **distinct-market count** and an `all_time_pnl` breakdown
  (realized market pnl, rebates, fees paid, volume).
- `/v2/prices-history` returned empty for a resolved token. **CLOB `/prices-history` works for resolved
  markets only with explicit `startTs`/`endTs`** (`fidelity` in minutes); `interval=max` returns empty.
  It is a trade/mid series, not bid/ask or depth.
- **No official historical order book endpoint.** CLOB `/book` and `/books` are current snapshots only
  (bids/asks, tick size, min size, neg_risk, last trade, ms timestamp).
- **Gamma** `/markets/keyset` and `/events/keyset` (limit ≤ 100, `after_cursor`; `offset` not allowed).
  **Gamma returns only open markets unless `closed=true`.** Outcomes, prices and clobTokenIds are JSON strings.
- **CryptoHouse** (public ClickHouse, user `crypto`, read-only, 60 s/query, max 2,000 result rows):
  `polymarket.orders_filled` has 257.6M on-chain fills from **2022-11-21 to 2026-01-05** (pre-V2 exchange only;
  stale afterwards). Also `orders_matched`, `user_positions`, `user_balances`, `token_id_condition`, `slugs`,
  `market_open_interest`. Aggregate server-side.
  `polymarket.assets` has per-outcome-token metadata: `outcome_price` (resolution payout for closed markets),
  `market_condition_id`, `market_question`, `event_id`, `event_slug`, `event_tags`, market start/end/closed dates.
  `polymarket.user_positions` is a final-state snapshot (amount, avg_price, realized_pnl, total_bought), not point-in-time.
  **External tables work** (multipart upload, e.g.
  `curl -F 'ext=@file.tsv' 'https://crypto-clickhouse.clickhouse.com/?user=crypto&ext_structure=k+String,v+UInt8&query=...'`),
  so you can join your own lists server-side and only export small results.
  OrderFilled semantics: one event per maker order filled plus one for the taker order (whose counterparty is the
  exchange contract). Verify against docs /resources/onchain-position-data before aggregating, to avoid double counting.
- The Goldsky Polymarket orderbook subgraph is **deprecated and stale** since V2; do not use it.
- Polygon public RPC `https://polygon-bor-rpc.publicnode.com` works (eth_getLogs etc.).
  Etherscan/Polygonscan require an API key (not available). Dune, SSRN, ScienceDirect, Wiley and
  ResearchGate return 403 from this sandbox. arXiv, RePEc/IDEAS, Kalshi public API (`api.elections.kalshi.com`),
  Binance public data (`data-api.binance.vision`) and Coinbase are reachable. Use WebSearch/WebFetch for the web.

## Candidate wallet facts (verified 2026-10-17, preliminary)

- `0x96cf…1acb` resolves to profile **mintblade** (pseudonym Golden-Reclamation), created
  2026-06-02T14:47:45Z, Gamma user id 8422116, taker tier 6 Obsidian. `user-stats`: 5 distinct markets,
  realized market PnL ≈ $9.11M, fees paid ≈ $127k, taker rebates ≈ $27.9k, maker rebates ≈ $0.9k.
  727 trade rows (taker_only=false), all between 2026-06-03 and 2026-07-08.
  Closed positions: "Will IR Iran win on 2026-06-15?" No (+$7.23M); "Will Uruguay win on 2026-06-15?" No (+$1.35M);
  "Spread: Uruguay (-1.5)" Saudi Arabia (+$0.39M); "Will Saudi Arabia vs. Uruguay end in a draw?" Yes (+$0.14M);
  "New York Mets vs. Seattle Mariners" Mets ($0 realized). Three of the five markets are on the same match.
- `0x3f87…742c` → **GRIMDRIP** (Dismal-Volunteering-Graph), created 2026-06-02T15:01:41Z (14 min after mintblade),
  Gamma user id 8422276, tier 4 Platinum.
- `0x5e4c…dba2` → **endlessFate** (Mushy-Conspirator), created 2026-04-27, user id 7713278, tier 6 Obsidian.
  Its TAKER_REBATE payouts share timestamps with mintblade's (daily batch payouts, so not evidence of a link).
