# PIT wallet-following: stage 1 dataset build (decisions, screens, evaluation export, cluster signal)

As-of 2026-10-17. Stage 1 of 4: this note covers the data build only. No follower return or screen performance
was computed in this stage. Pre-registration: `notes/strategies/pit_wallets_preregistration.md` (written
15:12Z, before any screen or performance number; addenda A0-A7 add implementation detail only).
Labels: **VERIFIED** = I inspected the primary data or source myself; **PLAUSIBLE** = consistent with the
evidence but not checked directly; **UNSUPPORTED** = not established.

## 0. Stage-1 result in brief (resumed session, finished 2026-10-17T23:17Z)

- **Built (VERIFIED).** The point-in-time screens were computed at all 24 selection dates
  (2024-01-01 .. 2025-12-01) over all 256 wallet buckets:
  - S1, S1m, S2, S3, S4 (4 categories), S5 and the B1 random-eligible sample;
  - 973,951 (date, screen, wallet) member rows covering 153,604 distinct wallets;
  - base-rate counts per date;
  - per-wallet signal features.
- **Evaluation-window export (VERIFIED).**
  - 963,643 new decisions of sampled screened wallets in the following calendar month (primary signal).
  - 1,650,952 BUY fills of the fill-export sub-sample (secondary signal), capped at 1,000 per (date, wallet)
    under addendum A9.
- **Cluster signal (VERIFIED).** 773 fresh-wallet cluster signals in 389 underlying events.
- **Checks (VERIFIED).**
  - The fill rule matched the Data API on 28/28 fills.
  - The independent Data API audit reproduced 39/39 sampled screen memberships.
  - Member counts equal the server counts.
  - The S5 cut lies inside every bucket's candidate list.
- **No follower return or evaluation-window performance was computed** (stages 2-4).
- **What the trader's screen actually selects** (VERIFIED, trailing in-sample description, not a test):
  - "5 bets in 12 months, all won" (S1) is not a rare-skill filter. It holds 10k-12k wallets a month in
    2025-H2, 1-4% of eligible wallets.
  - 82% of S1 member rows have an average entry price >= 0.90 (70% >= 0.95), so the five wins are mostly
    favourites bought near certainty.
  - The median S1 wallet's trailing P&L on those bets is $0.56, and only 4.4% made more than $100.
  - Membership turns over by about half each month.
  - So S1 mostly picks small favourite buyers. Copying such buys at worse prices after detection leaves little
    room for profit. That is a prior (PLAUSIBLE), not a result; stage 2 tests it.
- **New constraint.** CryptoHouse enforces 120 queries per hour (section 2). Stage 2 must batch its
  follower-price pulls.

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
| decisions + screens (server side, 256 wallet buckets) | `04_screens.py` | `screen_buckets/*` (raw; `screen_buckets_s5shallow/` = 3 superseded buckets, section 6) |
| merge screens, S5 global cut | `05_merge_screens.py` | `screen_base_rates.parquet`, `screen_members.parquet`, `fresh_first_decisions.parquet` |
| evaluation-window export | `06_eval_export.py`, `06b_eval_merge.py` | `eval_chunks/*` (raw; `eval_chunks_superseded/` = partial months redone in format v2), `eval_decisions.parquet`, `eval_buys.parquet`, `eval_fill_wallets.parquet`, `eval_coverage.parquet`, `eval_sample_members.parquet`, `eval_wallet_index.parquet` |
| wallet births (cluster base rate) | `07_wallet_births.py` | `wallet_births.parquet` |
| cluster signal | `08_cluster_signals.py` | `cluster_signals.parquet`, `cluster_signal_members.parquet` |
| resolution-time check | `09_resolution_check.py` | `resolution_check.parquet` |
| fee field usage | ad hoc query (section 2) | `fee_field_by_quarter.parquet` |
| independent audit of screens (Data API) | `10_audit_sample.py` | `audit_sample.parquet` |
| counts quoted in this note | `11_build_summary.py` | (stdout only) |

Run logs of the resumed session are in `data/derived/pit_wallets/logs/`.

## 2. Data facts (VERIFIED unless marked)

- **CryptoHouse limits.** These are the `system.settings` values on 2026-10-17. They are stricter than
  CONTEXT.md says: max_result_rows 2,000, **max_result_bytes 1,000,000**, max_execution_time 60 s,
  readonly=1 (no SET, no materialised CTEs), 20 GB memory. A `WITH x AS (subquery)` referenced twice is
  evaluated twice, including the full table scan. Every query here therefore uses one linear pipeline and
  packs its output into arrays to stay under the byte cap.
- **Hourly query quota (new on 2026-10-17, not in CONTEXT.md).** CryptoHouse returned `QUOTA_EXCEEDED`:
  "Quota for user `crypto` for 3600s has been exceeded: queries = 145/120", with intervals ending on the full
  hour.
  - That means at most **120 queries per hour**. It is probably counted per IP, so all agents on this sandbox
    share it (PLAUSIBLE: the quota key was not shown).
  - Failed queries appear to count too.
  - `ch.py` now sleeps until the interval ends instead of retrying.
  - Any stage-2 pull of follower prices from CryptoHouse must fit this budget: at most about 120 tokens or
    time windows per hour unless they are batched into one query.
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
   inside every bucket's list. Three buckets failed that check and were re-run with a top-8% + 12 list (section 6).
7. B1 is a fixed 1% hash sample of eligible wallets.

**The P&L formula.** P&L = sum over tokens of (sell proceeds - buy cost + payout x net shares). This is exact
for a clean binary market even when the wallet also split or merged. Splitting S sets costs S and returns
payout(YES) + payout(NO) = 1 per set at resolution, so the split terms cancel. It is not exact for NegRisk
conversions or transfers between wallets. The pre-registered "net-negative shares = unreliable = not made
money" rule is therefore conservative. It was kept as pre-registered.

## 6. Screens: base rates and members (step 5) — counts only, no performance

**Run.**
- All 256 wallet buckets were computed with the same SQL. Buckets 0-142 and 178-218 ran before the
  interruption and 143-177 and 219-255 after it; the queries are cached under `data/raw/cryptohouse/cache/`.
- Each bucket read 258,035,873 rows. That count is the same for every bucket, so the table did not change
  between the runs.
- No bucket had to be split for the 1 MB cap.

**The S5 candidate depth was too shallow in three buckets.**
- The merge found that buckets 29, 62 and 92 did not reach the global S5 cut at 2024-12, 2025-01 and
  2025-02. Their top 2% + 3 candidate lists ended above the cut.
- Those three buckets were re-run with a list of the top 8% + 12 (`PMR_S5_DEPTH=0.08,12`). The earlier files
  are kept in `screen_buckets_s5shallow/`.
- Every other output of those buckets was identical: the counts, and the S1-S4 and B1 members.
- After the re-run, the global cut lies inside every bucket's list at all 24 dates. The re-run changed the
  2024-12 S5 cut from $11,511 to $11,568.

**Consistency checks (VERIFIED).**
- `screen_members` row counts equal the server-side screen counts at every date for S1, S1m, S2, S3 and S4.
- Independent audit (`10_audit_sample.py`, `audit_sample.parquet`): I took 40 random (date, wallet) members,
  10 each of S1, S1m, S2 and S3, and pulled each wallet's full history from Data API
  `/v2/trades?user=…&taker_only=false`, a source independent of CryptoHouse. I re-implemented the rules in
  pandas with the same token metadata.
  - One wallet was skipped because it had more than 20,000 Data API rows.
  - All 39 audited memberships were reproduced.
  - n_res matched in 39 of 39. n_won and the edge sum matched in 38 of 39; the exception is one S3 wallet with
    218 decisions, 154 wins against 155, and the screen flag is unchanged. n_mm matched in 39 of 39.
  - The one difference is consistent with the A8 tie-break or a single fill that is missing in one of the
    two sources (PLAUSIBLE).

**Base rates** (`screen_base_rates.parquet`, every date).
- n_w_counted = wallets with >= 1 counted decision whose entry episode ended before D. n_res5 / n_res10 =
  wallets with >= 5 / >= 10 counted resolved decisions (the S5 and B1 eligibility base).
- s5_n_top = ceil(1% of n_res5). s5_pnl_cut = the trailing decision-market P&L of the last S5 member, in $.

| D | wallets counted | n_res>=5 | n_res>=10 | S1 | S1m | S2 | S3 | S4 sports | S4 politics | S4 crypto | S4 other | S5 n | S5 cut $ |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024-01 | 7464 | 1335 | 639 | 16 | 10 | 43 | 13 | 0 | 0 | 0 | 8 | 14 | 17165 |
| 2024-02 | 9999 | 1762 | 851 | 21 | 19 | 59 | 11 | 0 | 0 | 0 | 8 | 18 | 20541 |
| 2024-03 | 11435 | 2026 | 997 | 22 | 12 | 68 | 13 | 0 | 0 | 0 | 7 | 21 | 22897 |
| 2024-04 | 11281 | 2196 | 1135 | 26 | 23 | 67 | 15 | 0 | 1 | 5 | 5 | 22 | 22443 |
| 2024-05 | 11900 | 2359 | 1238 | 32 | 27 | 82 | 19 | 0 | 5 | 4 | 2 | 24 | 18913 |
| 2024-06 | 19330 | 2736 | 1384 | 52 | 49 | 113 | 22 | 0 | 6 | 5 | 1 | 28 | 18491 |
| 2024-07 | 34389 | 4157 | 1780 | 146 | 131 | 367 | 16 | 2 | 5 | 5 | 6 | 42 | 18385 |
| 2024-08 | 56147 | 7423 | 2874 | 277 | 237 | 814 | 32 | 2 | 11 | 6 | 5 | 75 | 16447 |
| 2024-09 | 82397 | 13207 | 5393 | 377 | 350 | 1372 | 58 | 7 | 34 | 7 | 4 | 133 | 18276 |
| 2024-10 | 115176 | 18680 | 8008 | 567 | 505 | 1838 | 72 | 13 | 45 | 11 | 5 | 187 | 16388 |
| 2024-11 | 187154 | 29600 | 12404 | 933 | 789 | 3317 | 97 | 26 | 61 | 13 | 6 | 296 | 10747 |
| 2024-12 | 297367 | 61103 | 25544 | 2295 | 1516 | 7066 | 239 | 41 | 178 | 25 | 4 | 612 | 11568 |
| 2025-01 | 405415 | 88179 | 36138 | 3081 | 2172 | 10077 | 313 | 90 | 206 | 35 | 11 | 882 | 8725 |
| 2025-02 | 545391 | 151846 | 65808 | 6666 | 5022 | 26886 | 387 | 119 | 212 | 47 | 16 | 1519 | 5592 |
| 2025-03 | 631439 | 198229 | 91978 | 7144 | 5130 | 36424 | 462 | 178 | 226 | 52 | 24 | 1983 | 4317 |
| 2025-04 | 693776 | 243049 | 121266 | 9309 | 6088 | 43564 | 514 | 209 | 258 | 52 | 21 | 2431 | 3707 |
| 2025-05 | 723385 | 294026 | 154593 | 10381 | 5490 | 54457 | 554 | 232 | 238 | 60 | 27 | 2941 | 3379 |
| 2025-06 | 757314 | 335018 | 188296 | 11595 | 6099 | 61017 | 634 | 261 | 256 | 61 | 38 | 3351 | 3300 |
| 2025-07 | 786104 | 355143 | 210183 | 10627 | 5908 | 63189 | 697 | 293 | 278 | 97 | 47 | 3552 | 3593 |
| 2025-08 | 822213 | 371735 | 227808 | 11723 | 6794 | 67556 | 768 | 325 | 253 | 132 | 52 | 3718 | 3559 |
| 2025-09 | 849435 | 379524 | 237658 | 10671 | 6106 | 68424 | 842 | 369 | 227 | 165 | 53 | 3796 | 3559 |
| 2025-10 | 882313 | 390575 | 247717 | 9971 | 5409 | 71407 | 850 | 404 | 209 | 182 | 57 | 3906 | 3804 |
| 2025-11 | 1015499 | 434070 | 274372 | 11359 | 6867 | 82910 | 987 | 430 | 180 | 297 | 68 | 4341 | 5035 |
| 2025-12 | 1044579 | 482212 | 310280 | 11758 | 7097 | 86995 | 1154 | 493 | 159 | 438 | 86 | 4823 | 5268 |

**What the members look like (VERIFIED; trailing in-sample statistics, not evaluation results).**
- **"5 bets, 5 wins" is common, not rare.** S1 holds 1.1-4.4% of the eligible wallets (>= 5 resolved
  decisions) at each date: 16 wallets at 2024-01, and 9,971-11,758 a month during 2025-H2. S2 (>= 5 and no
  losses) holds 3-19%.
- **Most of those records come from buying near-certain outcomes.** The members' average entry price
  (1 - mean edge) is >= 0.90 for 82% of S1, 79% of S1m and 90% of S2 member rows, and >= 0.95 for 70% / 68% / 79%.
  The median trailing mean edge is 0.02 for S1 and 0.015 for S2, against 0.003 for the random eligible
  wallets (B1).
- **They make very little money.** S1's median trailing decision-market P&L is $0.56 (S1m $1.31, S2 $0.78).
  Only 4.4% of S1 member rows made more than $100. The median resolved notional over the five bets is
  $83, and the median decision notional is $12.
- **Membership does not persist.** A median of 49% of a date's S1 members are S1 again a month later.
- **S3 and S4 are rare and look different.**
  - S3 has 13-1,154 wallets per date. Its median member has 55 resolved decisions, mean edge 0.15 and
    trailing P&L about $1,150.
  - S4 has 0-493 wallets per date per category. Sports and politics specialists appear from mid-2024, crypto
    from 2025.
  - The S3 and S4 z rule penalises entries near certainty through its variance term, so those wallets are not
    favourite buyers.
- **S5 (top 1% by trailing P&L) is set by size.** Its median decision notional is $297, against $8.5 for B1.
  Its median mean edge is 0.04.
- **About 8% of S3 and S5 member rows have an "unreliable" market P&L** (a token with net-negative fill shares,
  from a split, conversion or transfer). That flag affects S1m only. In S3 and S5 those wallets stay, using the
  fill-based P&L.

**Member rows by split** (rows = (date, wallet) pairs; wallets = distinct).

| screen | train rows | validation rows | test rows | train wallets | validation wallets | test wallets |
|---|---|---|---|---|---|---|
| S1 | 4,764 | 48,176 | 66,109 | 3,810 | 32,466 | 32,331 |
| S1m | 3,668 | 30,001 | 38,181 | 2,835 | 20,360 | 20,345 |
| S2 | 15,206 | 232,425 | 440,481 | 8,801 | 81,617 | 112,016 |
| S3 | 607 | 2,864 | 5,298 | 331 | 936 | 1,828 |
| S4 sports | 91 | 1,089 | 2,314 | 61 | 389 | 708 |
| S4 politics | 346 | 1,396 | 1,306 | 217 | 349 | 456 |
| S4 crypto | 81 | 307 | 1,311 | 34 | 103 | 573 |
| S4 other | 61 | 137 | 363 | 17 | 55 | 122 |
| S5 | 1,472 | 13,107 | 24,136 | 697 | 3,909 | 7,300 |
| B1 (1% random eligible) | 1,338 | 12,987 | 24,329 | 568 | 3,398 | 5,306 |

**The train period is thin.** The 2024 dates have few wallets: S3 has 11-239 members per date, and S4 has 0-178
per category. The test-period numbers per date are large enough. Stage 2 should therefore read the train
period as a rough check only. Validation and test carry the evidence.

**Per-wallet signal features (exported in `screen_members`).**
- `med_usd`: median decision notional over the window decisions whose episode ended before D. It feeds F1,
  "bet >= 5x the wallet's own median".
- `first_fill`: the wallet's first-ever fill.
- `n_win`: counted decisions in the window. `n_res`, `n_won`, `n_cmp`, `n_mm`: resolved, won, event-complete
  and made-money counts. `n_nc`: decisions not counted (scalp or dust). `n_unrel`: decisions whose market P&L is
  unreliable.
- `se`, `se2`, `sv`: sums of the edge, the squared edge and p(1-p). `pnl`, `usd_res`: trailing P&L and resolved
  notional.
- Per-category counts, wins, edge sums and z. `mean_edge`, `shrunk_edge`, `z_shrunk` and `t_plain` (the plain
  t-stat, stored but not used).
- "Last activity before D" for F2 is in the evaluation export (`w_last_before`, `prev_active_day_gap`), not
  here.

## 7. Evaluation-window export (step 6) — data only, no performance

**Followed set and sample (A7).**
- The followed set is fixed at D: the members of each screen at D.
- Per (D, screen), the first 1,000 members ranked by md5(wallet|screen) go into the decision export, and the
  first 150 also go into the fill export. Screens with fewer members are exported in full.
- B1 is the 1% hash sample of eligible wallets, exported under the same caps.
- The sample is set by hash, so it does not depend on outcomes.
- `eval_sample_members.parquet` lists every member with its rank and sample flags.
- `eval_wallet_index.parquet` maps the integer wallet ids used in the chunks to addresses.

**Queries.**
- One CryptoHouse query per (D, wallet chunk). The query reads the chunk wallets' whole fill history up to the
  window end, with an external table of wallets and `meta_ext.tsv`.
- A chunk that overflows the 1 MB cap is halved. A single heavy wallet is split by time slice.
- Format v1 was used for 2024-01..09, 2025-05 and 2025-06, uncapped. Format v2 (A9) was used for every other
  month, with the fill cap and a slimmer decision row.
- `06b_eval_merge.py` puts both formats into one schema and applies the A9 cap to v1 locally.
- Chunks of 2024-10 and 2025-07 written in v1 before the quota stop were superseded (moved to
  `eval_chunks_superseded/`), and those months were re-exported whole in v2.
- Query count: 419 chunk files plus 24 per-month count queries. About 45 more queries were rejected by the
  quota and then re-run.

**`eval_decisions.parquet` (primary signal: new decisions).** One row per (D, wallet, new decision), where the
decision's event-level first BUY falls in [D, first day of next month). Columns:
- the wallet's screens at D and the screens it was sampled for;
- the token, condition, underlying event, question, outcome, category and negRisk;
- `t0`;
- the followed wallet's own fills: first-second shares, $ and price, taker share of the first-second $, $ in
  the first 10 min (F1 input), the 6 h episode's shares, $, VWAP, sells and fill count;
- `first_tx` (transaction hash of the first fill);
- payout `p`, `clean_resolution`, `outcome_won` and `t_res`;
- `w_last_before`, `prev_active_day_gap` and `F2_returning`;
- `med_usd_at_D` and `F1_large`.

The followed wallet's prices are **not** follower prices. Stage 2 must price entries from other wallets' fills
at t + delay.

**`eval_buys.parquet` (secondary signal).** Every BUY fill in the window by the fill-export sub-sample, on
every token, with or without metadata, capped under A9. Columns: D, wallet, token key / token_id / condition /
underlying event / category, ts, shares, $, price, role (maker/taker), tx hash, and whether the token is the
wallet's new decision. `eval_fill_wallets.parquet` gives each sampled (D, wallet)'s total window buys, its
exported buys and whether the cap applied.

**`eval_coverage.parquet`.** Per (D, screen): members, number sampled for decisions and for fills, decisions
exported, and wallets with at least one new decision. Totals by split:

| screen | sampled (D, wallet) train / val / test | new decisions exported train / val / test | (D, wallet) pairs with >= 1 new decision train / val / test | fill-export (D, wallet) train / val / test |
|---|---|---|---|---|
| B1_random_eligible | 1,338 / 5,836 / 6,000 | 6,771 / 14,616 / 22,633 | 665 / 2,779 / 1,931 | 775 / 900 / 900 |
| S1 | 3,469 / 6,000 / 6,000 | 9,527 / 10,409 / 4,801 | 1,833 / 2,987 / 1,528 | 1,065 / 900 / 900 |
| S1m | 3,152 / 6,000 / 6,000 | 9,456 / 11,511 / 5,407 | 1,725 / 3,153 / 1,923 | 1,021 / 900 / 900 |
| S2 | 5,613 / 6,000 / 6,000 | 18,450 / 11,994 / 8,008 | 3,282 / 3,542 / 2,411 | 1,332 / 900 / 900 |
| S3 | 607 / 2,864 / 5,144 | 15,889 / 69,024 / 464,853 | 393 / 1,477 / 2,491 | 518 / 900 / 900 |
| S4_crypto | 81 / 307 / 1,311 | 868 / 6,526 / 342,442 | 55 / 169 / 739 | 81 / 307 / 829 |
| S4_other | 61 / 137 / 363 | 1,975 / 4,293 / 20,383 | 42 / 90 / 250 | 61 / 137 / 363 |
| S4_politics | 346 / 1,396 / 1,306 | 6,590 / 20,771 / 31,187 | 205 / 636 / 713 | 318 / 900 / 900 |
| S4_sports | 91 / 1,089 / 2,314 | 7,778 / 49,087 / 123,322 | 71 / 620 / 1,093 | 91 / 809 / 900 |
| S5 | 1,472 / 5,882 / 6,000 | 35,094 / 89,950 / 203,134 | 941 / 3,046 / 2,865 | 827 / 900 / 900 |

**Structural checks (VERIFIED, no outcomes inspected).**
- Every exported decision has `t0` inside its window: 100%.
- Every first-fill transaction hash is 66 hex characters. It is found among the wallet's own same-second
  window fills in 100% of the decisions that also have fills (v1: 1,931/1,931, v2: 5,811/5,811 in the months
  tested). This confirms the UInt256 hash encoding round-trips correctly.
- All exported prices are in (0, 1]. All buys fall inside their window.
- The only duplicate (D, wallet, underlying event) rows are decisions on tokens without metadata (436 rows),
  which have no event key.
- Decisions on tokens without metadata: 0.07%. Clean resolution: 99.6%.
- F2 "returning" is set for 0.62% of decisions and F1 "large bet" for 10.5% (where defined). These shares are
  similar in v1 and v2 months (F2 1.1% vs 0.9%).
- In 50.4% of decisions the first second is entirely taker fills.
- Counts by split:
  - train: 113,978 decisions, 7,089 underlying events, 6,352 wallets;
  - validation: 217,803 decisions, 15,634 events, 9,533 wallets;
  - test: 631,862 decisions, 54,385 events, 6,515 wallets.
  - Many test decisions come from S3, S4-crypto and S5 bots. S3 alone has 464,853 decisions in test, so stage 2
    must weight by wallet or event, not by decision.
- Fill export:
  - 19,588 sampled (D, wallet) pairs, of which 10,095 had any buy.
  - 11,667,861 window buys in total, of which 1,650,952 were exported after the A9 cap.
  - 944 (D, wallet) pairs were capped. Role split: 25.9% taker, 74.1% maker.
  - 0.04% of the exported buys are on tokens without metadata.

## 8. Cluster signal candidate (pre-registration section 12, A4) — signals exported, no performance

**Input** (`fresh_first_decisions.parquet`, built by the D = 0 group of the bucket queries):
- One row for each wallet whose first-ever exchange fill is the BUY that starts its first decision, with a
  6 h episode of >= $100: 448,680 wallets, of which 123,585 have an episode >= $1k.
- The row holds the decision token, the underlying event, the payout and `t_res`, and the episode's BUY fills
  (ts, shares, $).
- Wallets are identified only by `cityHash64(address)`. The addresses were not exported; they are not needed
  for following.
- Context from `wallet_births.parquet` (first-ever fill per month): 600-2,700 new wallets a month in 2023 to
  early 2024, rising to 112k-215k a month in 2024-10 to 2025-02, and 34k-187k a month in 2025. 1.73M wallets in total, 99.3% of which start with a BUY (91.6% in 2025-12).

**Rule and output** (`08_cluster_signals.py` -> `cluster_signals.parquet`, `cluster_signal_members.parquet`):
- The signal fires at the first minute m at which, in (m-60 min, m]:
  - >= 3 fresh wallets with cumulative episode buys >= $100 (counted from past fills only) bought the same
    outcome token; and
  - the fresh-wallet buys of that token sum to >= $20,000.
- Signal time = the end of minute m. One signal per token.
- Each row carries the token, condition, underlying event, question, outcome, category, negRisk, payout,
  `t_res`, the fresh-wallet VWAP and the split label.

| split (by signal time) | signals | distinct underlying events |
|---|---|---|
| before 2024 (unused) | 3 | 2 |
| train 2024 | 233 | 116 |
| validation 2025-H1 | 164 | 73 |
| test 2025-H2 | 373 | 218 |

**Descriptives (VERIFIED, no outcomes used).**
- 773 signals on 773 tokens in 389 underlying events.
- By category: sports 287, politics 233, crypto 208, other 45.
- 96.6% of the signals are on markets with a clean resolution.
- Median 4 counting wallets (maximum 131). Median window notional $22.6k.
- The fresh wallets' VWAP in the window has median 0.98 (10th / 90th percentiles 0.39 / 0.998). So, as with
  S1, most clusters are fresh wallets buying near-certain outcomes.
- Hours from signal to `t_res`: 10th percentile 5.2, median 264, 90th percentile 2,392. No signal fires at or
  after `t_res`.
- Several signals often fall in one event (several NO tokens of one negRisk event). Stage 2 must cluster
  inference by underlying event (only 116 train events).

**Point-in-time caveats.**
- Freshness (first-ever fill), the $100 threshold and the window sums use only past fills.
- **One deviation is conservative.** Fresh wallets whose whole 6 h episode stayed under $100 are not in the
  input at all. A real-time detector would add their buys to the window sum, so it would fire at the same time
  or earlier, never later. Our signal times are therefore never earlier than an achievable detector's
  (PLAUSIBLE small effect).
- **What C1 cannot see.**
  - "Newly funded" (collateral deposits) is not in `orders_filled`.
  - C2 (young wallets) was not built.
  - Wallets whose first fill was on one of the 937 tokens without metadata are never fresh in this data.
- 3 signals before 2024 are outside every split.

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
  split was needed, and none was. Three buckets were re-run with a deeper S5 candidate list (section 6).
- **The every-fill export is capped (A9).** It keeps the first 1,000 BUY fills per (date, wallet), plus ties.
  This truncates the heaviest bot-like wallets, so secondary-signal results describe the first 1,000 fills of
  those wallets. `eval_fill_wallets.parquet` says which (date, wallet) pairs were capped and their full counts.
- **F1 is not knowable at the first fill.** F1 ("large bet") uses the wallet's buys in the first 10 minutes,
  which a follower knows only at t0 + 10 min. Stage 2 must either enter F1 signals no earlier than t0 + 10 min
  or use `usd_first` (first-second notional, known at t0) as the F1 test.
- **The decision tie-break is a logged deviation (A8).** It matters only for same-second buys of two tokens in
  one event.
- **The train period is thin.** The 2024 dates have far fewer wallets than 2025 (section 6), so most of the
  evidence will sit in validation and test.
- **The CryptoHouse quota (120 queries/hour) limits stage 2.** Follower prices for tens of thousands of
  signals must be pulled in batches: many tokens per query through an external table.
