# PIT wallet-following: stage 1 dataset build (decisions, screens, evaluation export, cluster signal)

As-of 2026-10-17. Stage 1 of 4: this note covers the data build only. No follower return or screen performance
was computed in this stage. Pre-registration: `notes/strategies/pit_wallets_preregistration.md` (written
15:12Z, before any screen or performance number; addenda A0-A7 add implementation detail only).
Labels: **VERIFIED** = I inspected the primary data or source myself; **PLAUSIBLE** = consistent with the
evidence but not checked directly; **UNSUPPORTED** = not established.

__RESULTS__

## 1. Pipeline and files

Run everything from `polymarket_research/`. Every CryptoHouse response is stored with its SQL, the
external-table hashes and the fetch time under `data/raw/cryptohouse/` (helper `analyses/pit_wallets/ch.py`).
Every Gamma, Data API and RPC response is stored by `pmr.http` under `data/raw/`.

| step | script | output (`data/derived/pit_wallets/`) |
|---|---|---|
| fill semantics check | `01_semantics_check.py` | `semantics_check.parquet` |
| traded outcome tokens | `02_traded_assets.py` | `traded_assets.parquet` |
| Gamma metadata of traded tokens | `03_gamma_meta.py` | `gamma_markets_traded.parquet`, `token_meta.parquet`, `gamma_failed_tokens.parquet` |
| CryptoHouse `assets` snapshot (cross-check) | `03a_assets_crosscheck_pull.py` | `ch_assets.parquet` |
| per-token PIT metadata + external table | `03b_build_meta.py` | `token_meta_pit.parquet`, `market_meta.parquet`, `meta_ext.tsv`, `meta_checks.json` |
| decisions + screens (server side, 256 wallet buckets) | `04_screens.py` | `screen_buckets/*` (raw) |
| merge screens, S5 global cut | `05_merge_screens.py` | `screen_base_rates.parquet`, `screen_members.parquet`, `fresh_first_decisions.parquet` |
| evaluation-window export | `06_eval_export.py`, `06b_eval_merge.py` | `eval_chunks/*` (raw), `eval_decisions.parquet`, `eval_buys.parquet`, `eval_coverage.parquet`, `eval_sample_members.parquet`, `eval_wallet_index.parquet` |
| wallet births (cluster base rate) | `07_wallet_births.py` | `wallet_births.parquet` |
| cluster signal | `08_cluster_signals.py` | `cluster_signals.parquet`, `cluster_signal_members.parquet` |
| resolution-time check | `09_resolution_check.py` | `resolution_check.parquet` |
| fee field usage | ad hoc query (section 2) | `fee_field_by_quarter.parquet` |

## 2. Data facts (VERIFIED unless marked)

- **CryptoHouse limits.** These are the `system.settings` values on 2026-10-17. They are stricter than
  CONTEXT.md says: max_result_rows 2,000, **max_result_bytes 1,000,000**, max_execution_time 60 s,
  readonly=1 (no SET, no materialised CTEs), 20 GB memory. A `WITH x AS (subquery)` referenced twice is
  evaluated twice, including the full table scan. Every query here therefore uses one linear pipeline and
  packs its output into arrays to stay under the byte cap.
- **`polymarket.orders_filled`.**
  - 257,649,337 rows from 2022-11-21 19:50 to 2026-01-05 22:05 UTC. Sorted by `id`
    (`<tx hash>_<order hash>`), so time filters do not prune reads; a full scan of the needed columns takes
    3-15 s depending on load.
  - Within a month, `count() = uniqExact(id)` (checked for 2024-11, 2025-06 and 2025-12), so there are no
    duplicate rows. 3,269 rows have `is_deleted=1` and are dropped.
  - `transaction_hash` holds raw bytes. The hex hash is the part of `id` before `_`.
  - Amounts are 6-decimal integers.
  - The `fee` field is 0 for every fill from 2025-04 onwards. Non-zero fees appear only on a few thousand
    fills in 2023-2024 (`fee_field_by_quarter.parquet`).
- **Collateral.** Pre-V2 collateral is USDC.e (`0x2791bca1…84174`), not pUSD. The `getCollateral()` call
  on both legacy exchanges returns it (Polygon RPC).
- **`polymarket.assets` is not a usable universe.** It has 45,535 tokens (22,759 markets). Those cover 0% of
  2023 fill volume and 1-27% of each 2024-2025 quarter's volume (2.3% in 2025-Q4). Market metadata therefore
  comes from Gamma.
- **Coverage of the Gamma lookup.**
  - The lookup used every traded token: 387,473 traded tokens, of which 386,536 have Gamma metadata
    (193,526 markets).
  - That is 99.98% of fill volume and 99.99% of fills. 937 traded tokens have no metadata, and 4 tokens
    returned HTTP 500 on every attempt (`gamma_failed_tokens.parquet`).
  - Gamma `/markets/keyset` accepts repeated `clob_token_ids` (80 per request) and needs `closed=true`
    for resolved markets.

## 3. Fill semantics (step 2)

**Rule (VERIFIED on a sample).** Each `OrderFilled` row is the fill of exactly one order, owned by the address
in `maker`. To count every wallet fill exactly once:

- wallet = `maker`. The `taker` column is never used as a wallet.
- role = taker if `taker` is an exchange contract, else maker.
- side = BUY if `maker_asset_id = '0'` (the order paid collateral), SELL if `taker_asset_id = '0'`. Exactly one
  of the two is '0' on every row: 182,153,532 BUY rows and 75,495,805 SELL rows, none with neither.
- token = the non-zero asset id.
- shares = token amount / 1e6, collateral = collateral amount / 1e6, price = collateral / shares.

**Check against the Data API.**
- I took 4 transactions from 2025-06-10 14:00-14:02 UTC, with 28 fills in total. They cover:
  - a CTF-exchange taker BUY against 10 complement-token maker BUYs plus 2 same-token maker SELLs
    (a MINT-style match);
  - a NegRisk-exchange taker SELL against a maker BUY plus a complement maker SELL (a MERGE-style match);
  - two plain taker SELLs, one on each exchange.
- I compared them with Data API `/v2/trades?condition=…&taker_only=false` rows carrying the same
  `transaction_hash`.
- Result: 28/28 one-to-one matches on (tx, wallet, token, shares, price). Side agreed on every fill. The
  largest price difference was 4e-11.
- In every transaction, the taker's shares equal the makers' same-token shares on the opposite side plus
  the complement-token shares on the same side.

**Exchange contracts.**
- The legacy exchanges in this data are `0x4bfb41d5…8982e` (CTF Exchange, 58.0M taker-order rows) and
  `0xc5d563a3…0f80a` (NegRisk CTF Exchange, 50.2M rows).
- Polygon RPC confirms them: `getCtf()` returns Conditional Tokens `0x4d97dcd9…6045` for the first and the
  NegRisk Adapter `0xd91e80cf…5296` for the second. Both are listed in docs `/resources/contracts`.
- The current docs page lists only the V2 exchanges (`0xE1111800…996B`, `0xe2222d27…0F59`), which do not
  appear in this pre-V2 data.
- NegRisk fills have the same row shape. The only difference is the exchange address on the taker row.

**`orders_matched`.** One row per taker order. Its asset ids and amounts are mirrored relative to the taker's
own `OrderFilled` row (checked 4/4). It is not used for aggregation.

**Data API caveat.** `/v2/trades` rows carry no role field. The role comes only from the on-chain row.

## 4. Market metadata and the resolution-known time (step 3)

**Payout.**
- Gamma `outcomePrices` on closed markets give the payout. A market is clean only if every token pays
  exactly 1 or 0 (1e-3 tolerance) and exactly one token pays 1.
- 191,493 of 193,527 traded markets are clean, carrying 98.6% of fill volume.
- The unclean markets are:
  - 370 with 50-50 payouts;
  - the rest still unresolved or under UMA proposal or dispute (`umaResolutionStatus`: 451 proposed,
    4 disputed);
  - plus tokens without metadata.
- Unclean markets never count as a win or a loss.

**Resolution-known time `t_res` = Gamma `closedTime`.** It is present for every closed market (383,496 tokens);
the 3,040 tokens without it are open markets. Checks:

- Fills after `t_res` are rare. Only 0.0065% of clean tokens have a fill more than 1 h after `t_res`
  (0.0003% more than 1 day). In a sample of 432 markets, 20 had fills 2-182 s after `t_res`.
- Against Data API `/v2/resolutions`: 432 markets were sampled at random, stratified by year. All 432 have
  status `resolved` and 2 were disputed.
  - `t_res - last_update_timestamp` is never negative.
  - The difference is 0 for every non-negRisk market except a few (max 15.9 h).
  - For negRisk markets, `closedTime` is 68-90 min after the UMA record.
  - So `t_res` is never earlier than the API's resolution record. Using it can only delay when a decision
    counts as resolved, never advance it.
- On-chain: for 3 auto-resolved crypto up/down markets, the transaction that `/v2/resolutions` reports
  contains the Conditional Tokens `ConditionResolution` log for the condition, and its block time equals
  `t_res`.
  - For most other markets, that transaction is the market initialisation: its CTF log is
    `ConditionPreparation` and fills continue for days afterwards. The API's `transaction_hash` is therefore
    not reliably the resolution transaction.
  - A broad on-chain check of resolution times was not possible. Free RPCs refuse archive `eth_getLogs`
    (publicnode: token required; drpc: range limit), so the true on-chain resolution time for most markets
    is UNSUPPORTED here. It may be earlier than `t_res` (a conservative bias).
- CryptoHouse `assets` overlap: 35,950 clean tokens. `market_closed_date` equals `t_res` within 1 h for
  99.4% (median difference 0 s). Payout agrees for 99.5%; the disagreements are markets that the
  2026-05-14 `assets` snapshot still shows open.

**Category.**
- Taken from Gamma market tags; the slug sets are in `03b_build_meta.py` (addendum A1). Match order:
  crypto, sports, politics, else other.
- Shares of fill volume: politics 40.7%, sports 34.8%, crypto 19.1%, other 5.4%.
- Where Gamma `feeType` exists (2025+ markets), the mapping agrees:
  - `sports_fees_v2`: 1,780 of 1,780 sports;
  - `crypto_fees_v2`: 456 of 456 crypto;
  - `politics_fees`: 1,588 of 1,622 politics.

**Events.** The decision unit is the Gamma parent event. Sports games that Gamma splits into several events
(`-more-markets`, `-v2`, `-spreads-totals`, cricket props) are merged by their `<...>-YYYY-MM-DD` slug prefix
(addendum A6). This turns 86,030 traded Gamma events into 84,908 underlying events.

## 5. Decisions and screens (steps 4-5): how they are computed

Everything runs server side in one SQL pipeline per wallet bucket (`cityHash64(maker) % 256`). Each query uploads
`meta_ext.tsv` (18.5 MB: token key, condition, event, payout, `t_res`, category) as an external table. The
token key is the last 18 decimal digits of the token id; it is unique over all 387k traded tokens (asserted).

1. Per (wallet, token): first BUY time, the 6 h entry-episode BUY fills, sells inside the episode, and total
   buys and sells (shares and collateral).
2. Per (wallet, underlying event): `t0` = first BUY in the event. The decision token is the token of that BUY
   (ties: larger episode notional). The decision record keeps the episode VWAP, shares and notional, the
   payout, `t_res`, the category, and a list of all the wallet's tokens in the event. The event-level P&L uses
   that list.
3. Each decision is expanded to the selection dates D with `t0` in [D-12m, D).
   - A decision is resolved at D if its market is clean and `t_res < D`.
   - A decision counts as a bet if its notional is >= $1 and it kept >= 50% of its episode shares.
4. S1m uses event completeness at D (every token the wallet traded before D resolved cleanly before D) and
   event P&L > 0 with no net-short token.
5. S3 and S4 use z = sum(y - p) / sqrt(sum p(1-p) + 0.25 k), k = 10, with shrunken mean edge sum(y - p)/(n + k).
6. S5 is the global top 1% of decision-market P&L among wallets with >= 5 resolved decisions. It is cut in
   `05_merge_screens.py` from bucket-local top-2% candidate lists, and the script checks that the cut lies
   inside every bucket's list.
7. B1 is a fixed 1% hash sample of eligible wallets.

**The P&L formula.** P&L = sum over tokens of (sell proceeds - buy cost + payout x net shares). This is exact
for a clean binary market even when the wallet also split or merged. Splitting S sets costs S and returns
payout(YES) + payout(NO) = 1 per set at resolution, so the split terms cancel. It is not exact for NegRisk
conversions or transfers between wallets. The pre-registered "net-negative shares = unreliable = not made
money" rule is therefore conservative. It was kept as pre-registered.

__SCREENS__

__EVAL__

__CLUSTER__

## 9. Limitations (read before using the data)

- **Pre-V2 only.** Fills end 2026-01-05. Protocol V2 activity (2026) is absent, so mintblade-style 2026
  wallets cannot be in this dataset.
- **Only exchange fills.** Splits, merges, conversions, redemptions, transfers and deposits are not in
  `orders_filled`. P&L is fill-based (see section 5). "Newly funded" wallets cannot be identified.
- **`t_res` is Gamma `closedTime` as of 2026-10-17.** It is never earlier than the UMA resolution record in a
  432-market sample, and fills essentially stop before it. True on-chain resolution may come earlier, which
  delays counting (a conservative bias). Gamma fields are a 2026-10-17 snapshot; a market whose closedTime
  was later edited would carry the edited value (PLAUSIBLE rare).
- **Categories come from tags as they are today.** Gamma tags may have been added after the fact. This only
  matters for S4 grouping and is not information about outcomes.
- **Episode notional and entry VWAP are the followed wallet's own prices.** They are not available to a
  follower. Stage 2 must build follower prices from fills by other wallets at t + delay. No historical order
  book exists.
- **Evaluation export is a sample** (A7), so stage-2 confidence intervals must use the sampled counts.
- **Remaining metadata gap.** 937 traded tokens have no Gamma metadata and 4 Gamma lookups failed; together
  about 0.02% of volume. Fills on them are excluded from decisions. Unclean markets (1.4% of volume) count
  as neither wins nor losses.
- **Bucket outputs.** Each wallet-bucket query had to fit under 1 MB. Buckets were sized (256) so that no
  split was needed; the log records any split.
