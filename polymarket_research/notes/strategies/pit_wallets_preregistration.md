# Pre-registration: point-in-time wallet-following screens (Polymarket)

- Written: **2026-10-17T15:12Z** (UTC), before any screen performance, follower return, or
  evaluation-window statistic was computed. At this time only data-coverage counts had been
  queried (monthly fill counts, `polymarket.assets` coverage, duplicate counts).
- Author: research agent, stage 1 of 4 (dataset build). Stages 2-4 evaluate.
- Rule for edits: this file may only gain detail (dated addenda at the bottom). Nothing in it is
  changed after validation or test results are seen. Any deviation is logged as a dated addendum
  with the reason, and is reported as a deviation in the final write-up.
- Trader's original idea under test: "follow Polymarket accounts that made five bets in the
  previous 12 months and won all five".

## 1. Data

- Fills: CryptoHouse `polymarket.orders_filled` (on-chain `OrderFilled` events of the pre-V2
  CTF Exchange and NegRisk CTF Exchange), 2022-11-21 .. 2026-01-05. Rows with `is_deleted=1`
  are dropped. Matches: `polymarket.orders_matched` (used for semantics checks only).
- Market metadata: Gamma closed markets (`/markets/keyset?closed=true&include_tag=true`,
  shared universe pull plus a 2022-11..2023-12 pull made for this project) and CryptoHouse
  `polymarket.assets` as a cross-check / fallback.
- Amounts are 6-decimal integers (USDC/pUSD collateral and outcome-token shares).

## 2. Fill rule (to be verified empirically in the build, see pit_wallets_build.md)

Each `OrderFilled` row is the fill of exactly one order, owned by the address in `maker`.
- wallet = `maker` (never the `taker` column, which is either the counterparty wallet, whose own
  fill is a separate row, or the exchange contract).
- role = `taker` if `taker` is an exchange contract (CTF Exchange
  `0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e` or NegRisk CTF Exchange
  `0xc5d563a36ae78145c45a50134d48a1215220f80a`), else `maker`.
- side = BUY if `maker_asset_id = '0'` (the order gave collateral), SELL if `taker_asset_id = '0'`.
- token = the non-zero asset id; shares = token amount / 1e6; collateral = collateral amount / 1e6;
  price = collateral / shares.
If the empirical check against Data API `/v2/trades` contradicts this rule, the verified rule is
used and the discrepancy is logged as an addendum before any performance is computed.

## 3. Market resolution and "resolution known" time

- Clean resolution: final payout vector of the market is exactly {1, 0}. Markets with any other
  payout (e.g. 0.5/0.5, unresolved, cancelled) are excluded from all win/loss records and flagged.
- Resolution-known time `t_res` = Gamma `closedTime`; if missing, `umaEndDate`; if missing,
  CryptoHouse `assets.market_closed_date` (if > 1970); otherwise the market is excluded.
  A sample is cross-checked against `assets.market_closed_date` and `umaResolutionStatus`.
- Category: from Gamma tags (market tags, then parent-event tags) mapped to
  sports / politics / crypto / other with a fixed slug list documented in the build note
  (finalised from tag frequencies only, before any performance is computed).

## 4. Decision definition

- Unit = (wallet, event_id). One decision per wallet per distinct event (economically equivalent
  positions inside one event, e.g. YES on one outcome and NO on another, are one decision).
- `t0` = time of the wallet's first BUY fill of any outcome token of the event.
- Decision token = the token of that first BUY (ties in the same second: the token with the
  largest collateral in that second).
- Entry episode = the wallet's BUY fills of the decision token in [t0, t0 + 6 h].
  Recorded: entry VWAP, shares, notional (collateral), first-fill time, maker share of episode
  notional, number of fills, category, decision-token payout, `t_res`.
- Net-buy condition: episode net shares (episode buys minus sells of the decision token in the
  same 6 h) must be >= 50% of episode buy shares; otherwise the decision is a "scalp", is not
  counted as a bet in any screen, but is kept in the dataset with a flag.
- Dust: decisions with episode notional < $1 are not counted as bets (kept, flagged).
- outcome_won = decision-token payout is 1. edge = payout - entry VWAP.
- made_money (event level, approximate): over all of the wallet's exchange fills in the event's
  markets, P&L = sell proceeds - buy cost + payout x net remaining shares (per token).
  Splits, merges, conversions, redemptions and transfers are not in `orders_filled`; a token with
  net-negative shares (sold more than bought, i.e. sourced from a split/conversion) makes the
  P&L "unreliable": unreliable counts as NOT made money (conservative).
  For a decision to count toward S1m at date D, every market of the event in which the wallet
  traded before D must have `t_res < D`. Fallback if this is computationally infeasible on
  CryptoHouse: P&L over the decision market only (both outcome tokens), logged as an addendum.

## 5. Selection schedule and trailing record (point in time)

- Selection dates D = 00:00 UTC on the first day of each month, 2024-01-01 .. 2025-12-01 (24 dates).
- Trailing record at D: decisions with `t0` in [D - 12 calendar months, D) AND `t_res < D`.
  Decisions entered in the window but unresolved at D are counted only as `n_open`.
- All features use only fills with timestamp < D.

## 6. Screens (computed per D, per wallet)

- **S1** exactly 5 counted resolved decisions, all outcome_won.
- **S1m** exactly 5 counted decisions that are resolved and event-complete at D, all made_money.
- **S2** >= 5 counted resolved decisions and zero outcome losses.
- **S3 skill** >= 10 counted resolved decisions, shrunken mean edge > 0 and z >= 2, where with
  y_i payout, p_i entry VWAP, k = 10 pseudo-decisions at zero edge and variance 0.25:
  shrunken mean edge = sum(y_i - p_i) / (n + k);
  z = sum(y_i - p_i) / sqrt(sum p_i(1 - p_i) + 0.25 k).
  (Variance under the null that the entry price is the fair probability; prevents near-certain
  0.99 buyers from qualifying on tiny variance.) The plain t-stat mean/(sd/sqrt n) is stored too.
- **S4 category specialist** the S3 rule computed within one category (sports, politics, crypto,
  other) with >= 8 counted resolved decisions in that category. A wallet can pass for several
  categories; in evaluation only its decisions in the passing category are followed.
- **S5 naive profitable** top 1% of trailing realised P&L (sum over counted resolved decisions of
  decision-market P&L) among wallets with >= 5 counted resolved decisions at D.
- Base rates per D: wallets with >= 1 decision in window, >= 1 / >= 5 / >= 10 counted resolved
  decisions, and the number passing each screen.
- Per-wallet features at D: median decision notional over decisions with t0 in the trailing
  window (resolved or not), last fill time before D, first-ever fill time, n_open.

## 7. Evaluation window and follower model (stages 2-4)

- Evaluation window for D = [D, first day of next month). Followed set fixed at D.
- Primary signal: each NEW decision (first BUY in an event not previously traded) of a followed
  wallet during the window; follower enters once per (wallet, event). Secondary: every BUY fill.
- Signal-level filters (applied to the primary signal): F1 "large bet" = the wallet's cumulative
  buy notional of the decision token in the first 10 minutes >= 5 x its median decision notional
  at D; F2 "returning" = the wallet's previous fill (any) was >= 60 days before the signal fill.
- Follower entry: detection delay after the followed wallet's fill: primary 2 minutes,
  sensitivity 30 s, 10 min, 60 min. Entry price = price of the first taker BUY fill of the same
  token by any other wallet at time >= t + delay (proxy for the best ask; no historical book
  exists), plus 1 tick (0.01, capped at 0.999) slippage. If no such fill within 60 minutes the
  signal is unfilled (counted, not dropped silently). Prices paid by the followed wallet are never
  used as follower prices.
- Fees: (a) historical fee field (pre-V2, mostly zero); (b) stress test with the current taker
  fee schedule fee = shares x rate x p x (1 - p) by category (CONTEXT.md).
- Hold to resolution (final payout). Unclean or unresolved markets are excluded and counted.
- Stake: fixed $100 per signal; capacity check = share of signals with >= $1,000 of taker-buy
  volume in the 60 minutes after t + delay.

## 8. Split

- Train: selection dates 2024-01-01 .. 2024-12-01 (12 dates).
- Validation: 2025-01-01 .. 2025-06-01 (6 dates).
- Test: 2025-07-01 .. 2025-12-01 (6 dates). Test is evaluated once, after the screen list and all
  parameters above are frozen; no parameter is chosen on test.

## 9. Benchmarks

- B0: zero (no trade).
- B1: random eligible wallets: per D, wallets drawn uniformly from those with >= 5 counted resolved
  decisions, same count as the screen (200 draws, or all eligible wallets pooled), followed with
  the identical follower model.
- B2: price/category-matched market baseline: all taker BUY fills in the same eval month, same
  category and same entry-price decile, held to resolution (controls for favourite-longshot bias).
- B3: the followed wallet's own entry price (not achievable by a follower; measures delay decay).

## 10. Metrics

- Primary: net ROI per dollar staked = sum(payout x shares - cost - fees) / sum(cost), at the
  2-minute delay, with 95% CI from a bootstrap clustered by event_id.
- Secondary: mean edge in probability points (payout - follower price); hit rate (outcome won)
  separately from made money; number of signals, events and wallets; monthly P&L, max drawdown;
  fill rate; capacity share; delay decay curve; share of P&L from the top 1% of signals.

## 11. Rejection criteria

A screen / filter / cluster signal is rejected ("no demonstrated edge") if on the test set any of:
1. net ROI at the 2-minute delay <= 0, or its 95% event-clustered CI includes 0;
2. it does not beat B1 and B2 with one-sided p < 0.05 after Holm correction across all tested
   screens, filters and the cluster signal;
3. fewer than 100 distinct events with filled signals (then "inconclusive", not "edge");
4. more than 50% of P&L comes from the top 1% of signals or from a single event (fragile);
5. it was not positive on validation (it is still reported on test, but cannot be called an edge).

## 12. Cluster signal candidate

- Fresh wallet (C1): the wallet's first-ever exchange fill is its first BUY in this event
  (min fill time of the wallet = t0 of the decision). Secondary (C2, young): first-ever fill within
  7 days before t0. "Newly funded" (collateral transfers) is not observable in `orders_filled`
  and is not used.
- Signal: >= 3 distinct fresh wallets, each with >= $100 of buys of the same token, buying the
  same outcome token of the same event, with BUY fills inside a rolling 60-minute window and
  combined notional >= $20,000. Signal time = end of the first minute at which the condition holds
  using only fills up to that minute. Follower model as in section 7 from the signal time.

## Addenda

All addenda below add implementation detail only. Each was written before any screen membership, follower
return or evaluation-window statistic existed.

- **A0 (2026-10-17T15:48Z) fill rule verified.** The section 2 rule was checked on 4 transactions (28 fills,
  CTF and NegRisk exchanges, MINT- and MERGE-style matches) against Data API `/v2/trades`. All 28 matched on
  wallet, token, side, size and price (details in pit_wallets_build.md). Nothing changed.
- **A1 (2026-10-17T15:48Z) category slug lists.** These were fixed from tag frequencies (market counts and fill
  volume) and from agreement with Gamma `feeType` where it exists. No performance data was used. Match order:
  crypto, then sports, then politics, else other. The exact sets are the constants `CRYPTO`, `SPORTS` and
  `POLITICS` in `analyses/pit_wallets/03b_build_meta.py`. Esports and the Gamma tag `games` count as sports.
  Economy, Fed, finance, tech, culture and weather markets count as other.
- **A2 (2026-10-17T15:48Z) point-in-time features.** The features `n_win` (counted decisions in the window)
  and median decision notional use only decisions whose 6 h entry episode ended before D. Resolved decisions
  (t_res < D) are complete before D by construction. `first_fill` is the wallet's first fill on any token.
- **A3 (2026-10-17T15:48Z) S1m.** Implemented as pre-registered, with event-level P&L and the completeness
  rule. The fallback was not needed.
- **A4 (2026-10-17T15:48Z) cluster implementation.**
  - A fresh wallet's decision token is the token of its first-ever fill, which must be a BUY. Its contribution
    is its BUY fills of that token in [t0, t0 + 6 h].
  - A wallet counts at minute m if it has a fill in (m-60, m] and its cumulative episode buys up to that fill
    are >= $100.
  - "Combined notional" = all fresh-wallet buys of the token in (m-60, m].
  - Only the first signal per token is kept.
  - Fresh wallets whose first decision is on a token without Gamma metadata are not seen (coverage gap,
    quantified in the build note). C2 (young wallets) is not built in stage 1.
- **A5 (2026-10-17T15:48Z) evaluation export.**
  - Primary signals = new decisions in the window. A decision is new when its event-level first BUY falls in
    the window, judged from the wallet's whole history up to the window end.
  - Every BUY fill in the window is also exported.
  - The F2 "returning" test uses day resolution: a decision counts as returning if the wallet had no active
    UTC day in the 60 days before the decision's day.
- **A6 (2026-10-17, about 15:50Z) one game, one underlying event.** Gamma splits some sports games across several
  events (`<game>-more-markets`, `-v2`, `-spreads-totals`, cricket prop events). A sports event whose slug starts
  with `<...>-YYYY-MM-DD` is keyed by that prefix, so each game counts as one underlying event. All other markets
  keep the Gamma event id. This merges 86,030 traded Gamma events into 84,908 underlying events.
- **A7 (2026-10-17T16:01Z) evaluation sample and benchmark B1 sample.**
  - Some screens are very large. In one of 256 wallet buckets alone, S2 had 342 members at 2025-12-01.
    Evaluation therefore uses a fixed random sample of wallets per (D, screen): the first 1,000 members ranked by
    md5(wallet|screen) are exported at decision level, and the first 150 also have all their BUY fills exported.
    Screens with fewer members are exported in full.
  - The sample is set by a hash, not by outcomes. It changes the precision of a screen's average, not what it
    estimates.
  - B1 uses a fixed 1% random sample of eligible wallets (>= 5 counted resolved decisions at D;
    sipHash64(address) % 100 = 0), exported under the same caps.
  - Written before any evaluation-window data was pulled.

- **A8 (2026-10-17T21:28Z, resumed session) logged implementation deviation: decision-token tie-break.** Section 4
  says that ties in the first-BUY second go to the token with the largest collateral *in that second*. The
  server-side pipeline (`04_screens.py`, `argMinIf(..., (fb, -ep_usd), ...)`) breaks such ties by the larger
  *6 h entry-episode* notional of each token. The difference only matters when a wallet buys two tokens of the
  same event in the same second, which is rare. Only buckets 0-142 and 178-218 had been computed when the
  session was interrupted. No screen membership had been merged and no evaluation-window statistic existed.
  The rule was left as implemented, so all 256 buckets use one rule. The audit (`10_audit_sample.py`) uses the
  first-second rule, so any disagreement it finds includes this effect.
- **A9 (2026-10-17T22:00Z, resumed session) cap on the every-BUY-fill export (secondary signal) because of a
  CryptoHouse query quota.**
  - Partway through the evaluation export, CryptoHouse rejected queries with `QUOTA_EXCEEDED`: "queries =
    145/120 per 3600 s for user crypto". This is a quota of 120 queries per hour, shared by every agent on this
    IP. It is not in CONTEXT.md.
  - The every-fill export is very concentrated. In 2025-06, 10 of the 539 fill-export wallets with any buy hold
    64% of the window's BUY fills; in 2024-07, 10 of 221 hold 91%. These are bot-like wallets with thousands of
    buys a month, and their fills alone would need several hundred more queries.
  - The secondary (every-fill) export is therefore capped. Per (selection date, wallet), it keeps the wallet's
    first 1,000 BUY fills in the window by timestamp, plus every fill in the same second as the 1,000th. Those
    wallets are flagged, and their total number of window buys is recorded.
  - The same rule is applied locally to the months already exported without the cap, so every month uses one
    rule.
  - The primary signal (new decisions) is not capped.
  - The decision export also drops fields that can be re-joined locally from `token_meta_pit` (condition,
    event, payout, `t_res`, category). The first fill's order hash is dropped and its transaction hash is kept.
    The per-day activity array is replaced by the server-side gap to the previous active day, which is the
    F2 input.
  - Months exported only in part (2024-10 and 2025-07) are re-exported whole in the new format.
  - Decided only from export volume and the quota. No evaluation-window price, outcome or follower return had
    been looked at.
