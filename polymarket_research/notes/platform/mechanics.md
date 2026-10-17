# Market mechanics and settlement (as of 2026-10-17)

Scope: how outcome tokens are created, merged, converted and redeemed; the exact transaction
sequences and failure points for complete-set and neg-risk arbitrage; order types and matching;
resolution and redemption timing; Combos and Perps. Read-only research: no orders, no wallet.

Labels: **VERIFIED** = I read the primary source (docs page, contract source, on-chain state or a
live API response) myself on 2026-10-17. **PLAUSIBLE** = consistent with evidence but not directly
verified. **UNSUPPORTED** = no primary source found.

Primary sources used throughout (all fetched 2026-10-17):

- Docs (markdown at `https://docs.polymarket.com/<path>.md`): [/concepts/positions-tokens](https://docs.polymarket.com/concepts/positions-tokens.md),
  [/concepts/negative-risk](https://docs.polymarket.com/concepts/negative-risk.md), [/concepts/order-lifecycle](https://docs.polymarket.com/concepts/order-lifecycle.md),
  [/concepts/prices-orderbook](https://docs.polymarket.com/concepts/prices-orderbook.md), [/concepts/resolution](https://docs.polymarket.com/concepts/resolution.md),
  [/concepts/pusd](https://docs.polymarket.com/concepts/pusd.md), [/resources/contracts](https://docs.polymarket.com/resources/contracts.md),
  [/resources/onchain-position-data](https://docs.polymarket.com/resources/onchain-position-data.md), [/trading/positions/manage](https://docs.polymarket.com/trading/positions/manage.md),
  [/trading/positions/how-positions-work](https://docs.polymarket.com/trading/positions/how-positions-work.md), [/trading/place-orders](https://docs.polymarket.com/trading/place-orders.md),
  [/trading/manage-orders](https://docs.polymarket.com/trading/manage-orders.md), [/trading/matching-engine](https://docs.polymarket.com/trading/matching-engine.md),
  [/market-data/market-details](https://docs.polymarket.com/market-data/market-details.md), [/market-data/public-analytics](https://docs.polymarket.com/market-data/public-analytics.md),
  [/resources/error-codes](https://docs.polymarket.com/resources/error-codes.md), [/migrate/polymarket-v2/*](https://docs.polymarket.com/migrate/polymarket-v2/overview.md),
  [/trading/combos/*](https://docs.polymarket.com/trading/combos/overview.md), [/perps/faq](https://docs.polymarket.com/perps/faq.md), [/changelog/predictions](https://docs.polymarket.com/changelog/predictions.md).
- Contract source (public GitHub, shallow clones read locally): [Polymarket/polymarket-v2-external](https://github.com/Polymarket/polymarket-v2-external) (HEAD 741f8bb, 2026-09-24),
  [Polymarket/ctf-exchange-v2](https://github.com/Polymarket/ctf-exchange-v2) (HEAD ccc0596, 2026-04-13), [Polymarket/neg-risk-ctf-adapter](https://github.com/Polymarket/neg-risk-ctf-adapter),
  [Polymarket/uma-ctf-adapter](https://github.com/Polymarket/uma-ctf-adapter) (HEAD 8b76cc9, 2025-09-03).
- On-chain reads: Polygon public RPC `https://polygon-bor-rpc.publicnode.com` (`eth_call`, `eth_getLogs`, receipts).
- Live APIs: Gamma `/markets/keyset`, `/events`; CLOB `/book(s)`, `/clob-markets/{condition_id}`, market WebSocket; Data API `/v2/resolutions`, `/v2/status`.

Scripts (all read-only), in `analyses/mechanics/`:

| Script | What it measures | Output |
|---|---|---|
| `open_market_census.py` | every open Gamma market (287,718 rows): version, neg-risk flags, `secondsDelay`, tick, min size, UMA bond/liveness, fallback type | `data/derived/mechanics_open_markets_20261017.parquet` |
| `resolution_sample.py` | 37,236 markets closed in six pre-chosen 6-hour windows (Aug–Oct 2026) + `/v2/resolutions` for a 2,160-market stratified subsample | `data/derived/mechanics_resolution_sample.parquet` |
| `settlement_latency.py` | match timestamp (WebSocket) vs block timestamp of the settlement tx, 397 trades | `data/derived/mechanics_settlement_latency_20261017T1515.parquet` |
| `onchain_ops.py` | gas of 60 neg-risk converts; AutoRedeemer events vs resolution time | `data/derived/mechanics_onchain_ops_20261017T1520.parquet` |
| `keccak.py` | pure-Python Keccak-256 for selectors/topics (no keccak lib in sandbox) | n/a |

---

## 0. Summary for strategy design

1. **Binary complete-set arbitrage is structurally impossible on the visible CLOB.** The YES and NO books are one
   book viewed from either side (YES bid at p = NO ask at 1−p, same size; checked on 30 live markets), and the exchange
   itself matches BUY YES + BUY NO as a MINT and SELL YES + SELL NO as a MERGE. So askYES+askNO = 1+spread ≥ 1 and
   bidYES+bidNO = 1−spread ≤ 1 at all times. Sequences (a) and (b) below are documented for completeness only. **VERIFIED**.
2. **Multi-outcome (neg-risk) arbitrage is possible in principle**, because the matching engine never matches across the
   markets of an event. The cleanest form in today's CTF (v1) markets is **"buy every NO, then `convertPositions` with all bits
   set"**: it returns (k−1) pUSD per set immediately, with no wait for resolution. "Sell all YES" is the same trade, because selling YES at
   b is buying NO at 1−b. Convert fee (`feeBips`) was 0 on all 60 sampled neg-risk markets. **VERIFIED** (source + on-chain).
3. **"Buy all YES" in a v1 neg-risk event locks capital until resolution.** The legacy adapter has no horizontal merge.
   In augmented events (placeholders + "Other"), the tradable YES legs are **not** a complete set over time. **VERIFIED** (ABI/source + live event).
4. **No multi-leg order exists on the CLOB.** Every leg is a separate order with its own leg risk: partial fills, the 1–3 s sports
   delay during which an order cannot be cancelled, and the 150 ms crypto taker delay (5m/15m/1h up/down markets only **[corrected by verifier 2026-10-17]**). Each leg also pays its own taker fee
   (`rate·p·(1−p)` per share), and the minimum size is 5 shares per leg.
5. **Capital recycles fast once you hold the tokens.** A matched trade lands on-chain about 2.3 s after the match (median, n=397). A
   merge or convert is one more transaction (Polygon blocks ≈1.5 s; gasless through the relayer for smart wallets). Redemption by
   the AutoRedeemer lands about 12 s after resolution (median, n=150 conditions). **The slow part is resolution itself:**
   the median from `endDate` to on-chain resolution is about 2–3 h for UMA markets and about 1 min for Chainlink crypto up/down markets. A dispute adds days.
   **[corrected by verifier 2026-10-17]** For sports, Gamma `endDate` is the scheduled **start**, not the end. It equals
   `gameStartTime` on 97.8% of 1,434 sports markets closed 2026-10-17 21:42–21:57 UTC. So the sports "3 h after
   `endDate`" is about 3 h after kick-off, which is roughly 1 h after a 2-hour game ends. In that fresh sample,
   start-to-close was p10 2.4 h, median 4.3 h and p90 8.9 h (`data/derived/verification_recent_closed_markets.parquet`).
   On-chain, the UMA challenge window on these markets is 900 s (see §4.2).
6. **Resolution tail risks are real but rare.** "disputed" appears in the Gamma status history of 13 of 37,236 sampled closed
   markets (0.035%). Excluding sports and crypto, the rate is 6 of 960 (0.6%). **50-50 payouts hit 1.7% of sampled sports markets**, mostly
   unplayed sub-markets. **[corrected by verifier 2026-10-17]** The rate depends on market-type mix: 0.9–3.2% across the
   six windows, but 0.29% in a fresh soccer-heavy sample of 3,807. See §4.4. Admins can flag and manually resolve at several layers.

---

## 1. Token systems, contracts and operations

### 1.1 Two position ledgers; today all live trading is on CTF (v1)

| Item | Finding | Label | Source |
|---|---|---|---|
| Collateral | pUSD (ERC-20, 6 dp, USDC-backed; wrap USDC.e via CollateralOnramp `wrap`, unwrap via CollateralOfframp `unwrap`; both pausable) | VERIFIED | [/concepts/pusd](https://docs.polymarket.com/concepts/pusd.md) |
| Ledgers | **CTF** (Conditional Tokens `0x4D97…6045`) for `version:"v1"` markets; **PositionManager** (`0x006F…9fEF`) for `version:"v2"` | VERIFIED | [/trading/positions/how-positions-work](https://docs.polymarket.com/trading/positions/how-positions-work.md) |
| Open markets by version | **287,718 open Gamma markets, 100% `version:"v1"`**; 0 native v2 markets open | VERIFIED (census) | Gamma `/markets/keyset?closed=false` |
| V2 ids on v1 markets | 228,722 open v1 markets also carry 2 `positionIds` (V2 ids). For binary markets, `BinaryModule.legacyConditionId(v2Cond)` returns the CTF condition id, so these are **migration mirrors** of the CTF condition | VERIFIED (eth_call on 2 markets) | [/resources/onchain-position-data](https://docs.polymarket.com/resources/onchain-position-data.md) |
| Combos | use PositionManager/CombinatorialModule with V2 position ids as legs; `comboStatus:"enabled"` on 228,029 open markets | VERIFIED | [/trading/positions/how-positions-work](https://docs.polymarket.com/trading/positions/how-positions-work.md), census |

### 1.2 Current contract addresses (Polygon, chain 137) and what actually routes where

From [/resources/contracts](https://docs.polymarket.com/resources/contracts.md) (VERIFIED), annotated with on-chain checks:

| Role | Address | Notes |
|---|---|---|
| CTF Exchange (v1 binary) | `0xE111180000d2663C0091e4f400237545B87B996B` | EIP-712 domain version "2". Received 106 of 397 sampled settlement txs |
| Neg Risk CTF Exchange (v1 neg-risk) | `0xe2222d279d744050d28e00520010520000310F59` | Received 291 of 397 sampled settlement txs |
| ExchangeV3 (V2 markets) | `0xe3333700cA9d93003F00f0F71f8515005F6c00Aa` | domain version "3". 0 of 397 sampled txs (no v2 markets open) |
| CtfCollateralAdapter (v1 split/merge/redeem, binary) | `0xAdA100Db00Ca00073811820692005400218FcE1f` | wraps pUSD↔USDC.e; `onlyUnpaused(USDCE)` on split/merge/redeem |
| NegRiskCtfCollateralAdapter (v1 neg-risk ops incl. **convert**) | `0xadA2005600Dec949baf300f4C6120000bDB6eAab` | calls legacy NegRiskAdapter; `convertPositions` gated `onlyUnpaused(USDCE)` |
| Legacy NegRiskAdapter | `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296` | Docs label it "CLOB v1, deprecated". In fact it is **still the on-chain engine** behind the adapter above (`NEG_RISK_ADAPTER` immutable) and is `nrAdapter()` of both NegRiskOperators. "Deprecated" means only that the Relayer no longer accepts direct calls to it ([changelog 2026-07-14](https://docs.polymarket.com/changelog/predictions.md)) |
| Router (V2 split/merge/redeem/convert/horizontal ops) | `0x12121212006e4CD160D18e3f00711DA5c3372600` | |
| PositionManager / BinaryModule / NegRiskModule / CombinatorialModule | `0x006F…9fEF` / `0x1000…00Ba` / `0x2000…8933` / `0x3000…31A8` | module id in top byte of position id (1/2/3) |
| AutoRedeemer | `0xa1200000d0002264C9a1698e001292D00E1b00af` | operator-only batch redemption (see §4.6) |
| OracleAggregator (V2) + OO/Chainlink/EOA reporter modules | `0x0A0a…4a87`, `0x0000…527f`, `0xc12E…6814`, `0x8Ef9…0419` | V2 resolution path |

**Resolution contracts actually resolving markets differ from the docs list (VERIFIED on-chain).** In the 37,236-market
closed sample, Gamma `resolvedBy` was:

| `resolvedBy` | count | What it is (eth_call) |
|---|---|---|
| `0x65070BE91477460D8A7AeEb94ef92fe056C2f2A7` | 26,189 | UmaCtfAdapter-type contract; `ctf()` = CTF `0x4D97…`; `optimisticOracle()` = `0x2c0367a9…58b1` |
| `0x69c47De9D4D3Dad79590d61b9e05918E03775f24` | 6,256 | UmaCtfAdapter-type; `ctf()` = NegRiskOperator `0x661992ae…2e93` (`DELAY_PERIOD()` = 0, `nrAdapter()` = `0xd91E…`); same OO `0x2c03…` |
| `0x2F5e3684cb1F318ec51b00Edba38d79Ac2c0aA9d` | 7 | UmaCtfAdapter-type; `ctf()` = NegRiskOperator `0x71523d0f…b820` (`DELAY_PERIOD()` = **3600 s**); OO `0xee3afe34…7c24` |
| none | 4,784 | crypto up/down markets (Chainlink TWAP, no UMA) |

`0x2c0367a9…58b1` exposes `defaultProposerWhitelist()`, so it is UMA's **Managed Optimistic Oracle V2 (MOOV2)**.
Its `defaultLiveness()` is 7200 s. The two adapters in the docs' table (v2.0.0 `0x6A9D…`, v3.1.0 `0x157C…`) point to `0xee3a…`
(`defaultLiveness` 7200 s). The docs list `0xCB18…5130` both as "UMA Optimistic Oracle" and as "UmaCtfAdapter v1.0.0", which is a
doc inconsistency; it reverts on `ctf()` and `optimisticOracle()`.

### 1.3 Split / merge / redeem (exact calls)

From [/trading/positions/manage](https://docs.polymarket.com/trading/positions/manage.md) and
[/migrate/polymarket-v2/contract-integrations](https://docs.polymarket.com/migrate/polymarket-v2/contract-integrations.md). All VERIFIED.

| Op | v1 (CTF) call, target = adapter by `negRisk` | V2 call, target = Router | Approval |
|---|---|---|---|
| Split | `splitPosition(pUSD, 0x0, conditionId, [1,2], amount)` → 1 YES + 1 NO per pUSD | `split(bytes31 conditionId, amount)` | pUSD `approve(target)` |
| Merge | `mergePositions(pUSD, 0x0, conditionId, [1,2], amount)` | `merge(conditionId, amount)` | `setApprovalForAll(target)` on the token ledger |
| Redeem | `redeemPositions(pUSD, 0x0, conditionId, [1,2])` (full balances) | `redeem(conditionId, outcomeIndex, amount)` (one call per outcome) | same |

- There is no redemption deadline ([manage](https://docs.polymarket.com/trading/positions/manage.md)). VERIFIED.
- Each op is a single on-chain transaction. Through the Relayer (Deposit, Safe or Proxy wallet) it is **gasless** for the user, and several
  calls can be batched in one wallet batch, which is one transaction. EOAs pay POL gas ([/trading/wallets-auth](https://docs.polymarket.com/trading/wallets-auth.md)).
  Relayer `POST /submit` returns `STATE_NEW`; poll until `STATE_CONFIRMED`. VERIFIED (docs). The relayer's queueing latency was **not measured**.
- Gas (Foundry snapshots in `polymarket-v2-external/.gas-snapshot`, test totals): Router split ≈ 0.28M, merge ≈ 0.39–0.41M, redeem ≈ 0.42–0.53M,
  NegRisk horizontalSplit ≈ 0.32M, horizontalMerge ≈ 0.47M gas. At the observed 290–440 gwei and POL = $0.0932
  ([Coinbase spot](https://api.coinbase.com/v2/prices/POL-USD/spot), 2026-10-17), that is **≈ $0.01 per operation**. VERIFIED inputs; the cost is arithmetic.

### 1.4 Negative risk: what `convert` does exactly

**v1 / CTF (live today).** `NegRiskAdapter.convertPositions(marketId, indexSet, amount)`, reached through
`NegRiskCtfCollateralAdapter.convertPositions` ([source](https://github.com/Polymarket/neg-risk-ctf-adapter/blob/main/src/NegRiskAdapter.sol),
[adapter source](https://github.com/Polymarket/ctf-exchange-v2/blob/main/src/adapters/NegRiskCtfCollateralAdapter.sol)). VERIFIED by reading source:

- Input: `amount` NO tokens for each question whose bit is set in `indexSet` (k questions, k ≥ 1, of n = `getQuestionCount(marketId)`).
- Output: `amount·(1−f)` **YES of every question not in the set** (n−k of them), plus **(k−1)·amount·(1−f) collateral**
  (USDC.e, re-wrapped into pUSD by the adapter). Here f = `feeBips/10,000`. The burned NOs go to a burn address.
- Fee: `getFeeBips(marketId)` returned **0 for 60 of 60 randomly sampled open neg-risk markets** (of 10,106 distinct open `negRiskMarketID`s). VERIFIED (eth_call).
- Special cases: k = n (all NOs) gives n−1 collateral and no YES. k = 1 gives the n−1 other YES and no collateral.
- Atomic and instant: one transaction, no dependence on resolution.
- Gas grows with n, because the adapter splits a position for each YES it mints. Measured on 60 recent convert txs: median gas **0.58M (≤3 questions), 0.85M (4–8),
  2.0M (9–15), 5.6M (16–40), 13.7M (>40)**. At ~390 gwei and POL $0.093 that is ≈ $0.02 to $0.50 per convert. 35 of the 60 were sent through the
  Deposit Wallet Factory `0x00000000000Fb5C9…` (relayer, gasless to the user). VERIFIED (receipts).
- There is **no horizontal merge** (all YES → collateral) in the v1 adapter ABI (`artifacts/NegRiskAdapter.json`: split, merge per question, convert, redeem). VERIFIED.

**V2 (`NegRiskModule`, not yet used by any open market).** [Source](https://github.com/Polymarket/polymarket-v2-external/blob/main/src/modules/NegRiskModule.sol) and
[docs/modules.md](https://github.com/Polymarket/polymarket-v2-external/blob/main/docs/modules.md). VERIFIED:

- Every V2 neg-risk event has `arity` real conditions plus a **synthetic Other** at index `arity`.
- `Router.convert(eventId, conditionIndex, amount)`: burns 1 NO(i) and mints 1 YES(j) for every j ≠ i, **including Other**. There is no collateral output and no fee.
  To release collateral you then `merge` YES(j)+NO(j) pairs you already hold.
- `horizontalSplit(eventId, amount)`: pUSD → 1 YES of every real condition + Other. `horizontalMerge` is the reverse. This is the early exit
  for a full YES set, but **it needs the Other YES too**.
- Results must be fully binary (no 50-50) and at most one YES per event. Once one condition is YES, the siblings derive NO. If all real
  conditions resolve NO, Other derives YES. An all-NO final state is rejected.

### 1.5 Augmented neg-risk, placeholders and `negRiskOther`

Docs ([/concepts/negative-risk](https://docs.polymarket.com/concepts/negative-risk.md), [/market-data/market-details](https://docs.polymarket.com/market-data/market-details.md)),
VERIFIED: augmented events (`enableNegRisk && negRiskAugmented`) have named outcomes, placeholder outcomes that can be named
later, and an explicit Other. "Only trade on named outcomes"; "the Other outcome's definition changes as placeholders are clarified".

Live example, VERIFIED (Gamma `/events?slug=bachelorette-season-22-winner` + eth_call). On-chain `getQuestionCount` = **49** =
22 named contestants (active, tradable) + **26 placeholders "Contestant A…Z"** (`active:false`, no prices, best ask shown as 1)
+ **"Other (Season Cancelled)"** (`negRiskOther:true`, YES priced 0.92). Census: 27,512 open markets sit in augmented events; only 32
open markets carry `negRiskOther:true`.

Implications for treating an event as an exhaustive complete set:

1. **The complete set is the on-chain question set, not the Gamma market list you can trade.** Check
   `getQuestionCount(negRiskMarketID)` on `0xd91E…` against the markets you price.
2. In an augmented event, buying YES on every *tradable* market (named + Other) is **not** a complete set. If a placeholder is
   later named and wins, Other resolves NO and the basket pays 0. The placeholders cannot be bought on the CLOB.
3. Convert-based trades **stay exact**, because convert mints YES on every non-set question, placeholders included. Placeholder YES is a
   free option worth ≥ 0. "Buy NO on all k tradable markets, convert" returns (k−1) pUSD + placeholder YES regardless of later naming.
4. "Other" can be the favourite (Bachelorette: 0.92), so scanners that drop "Other" create false "sum of YES < 1" signals.
5. V2 events always contain a synthetic Other. If no CLOB book exists for it, YES-side completeness fails in the same way.

---

## 2. Exact transaction sequences for complete-set / neg-risk arbitrage

Notation: n markets in a neg-risk event (k tradable). Prices are per share. The taker fee per leg is
`fee = shares·rate·p·(1−p)` with the market's `feeSchedule.rate` ([/trading/fees](https://docs.polymarket.com/trading/fees.md); see CONTEXT.md).
Minimum order size is 5 shares per order (census: `orderMinSize` = 5 on 287,689 of 287,718 open markets).

### (a) Binary: buy YES + buy NO, then merge, when askYES + askNO < 1

| Step | Action | Collateral | Failure points |
|---|---|---|---|
| 1 | BUY YES at askYES (FOK) | askYES·q + fee | leg risk; partial fill (FAK) |
| 2 | BUY NO at askNO (FOK) | askNO·q + fee | **cannot occur in the visible book**: NO ask = 1 − YES bid, so askYES+askNO = 1 + spread. The engine would match those two resting asks against each other as a MERGE |
| 3 | `mergePositions` (relayer batch) after both fills are on-chain | returns q pUSD | wait for settlement (~2–3 s per fill); adapter pause gate |

Verdict: **impossible except as a display or latency artefact.** VERIFIED: 30 live markets showed the YES bid ladder exactly equal to
1 − the NO ask ladder at identical sizes, and the exchange's MINT/MERGE match types are in
[MATCH_ORDERS_LIFECYCLE.md](https://github.com/Polymarket/polymarket-v2-external/blob/main/src/exchange/MATCH_ORDERS_LIFECYCLE.md)
and [/concepts/prices-orderbook](https://docs.polymarket.com/concepts/prices-orderbook.md).

### (b) Binary: split, then sell YES and NO, when bidYES + bidNO > 1

Split q pUSD → q YES + q NO; SELL both at the bids; collateral needed is q up front. **Impossible for the same reason**:
bidYES + bidNO = 1 − spread ≤ 1, and two such bids would already have been matched as a MINT. VERIFIED.

### (c) Multi-outcome: buy all YES when Σ askYES < 1

| Step | Action | Notes |
|---|---|---|
| 1..n | BUY YES on every question of the **complete on-chain set** (FOK each) | n separate orders and n fees; no atomic multi-market order exists |
| n+1 | **v1: hold until resolution.** The legacy adapter has no horizontal merge, so pUSD is locked until the winner resolves | lock-up runs from days to months; this is the main cost |
| n+1' | V2 only: `horizontalMerge(eventId, q)` returns q pUSD immediately, but needs YES on the synthetic Other too | not applicable to any open market today |

Failure points: legs fill at different times (prices move); augmented events cannot be completed on the CLOB (§1.5);
the payout depends on a single correct resolution of the event. Profit = 1 − Σ askYES − Σ fees, realized only at resolution.

### (d) Sell all YES when Σ bidYES > 1 (split per market, sell YES, convert NOs)

| Step | Action | Collateral |
|---|---|---|
| 1 | split q pUSD in each of the n markets (n txs, or 1 relayer batch) | n·q pUSD up front |
| 2 | SELL YES on each market at bidYES_i | + Σ bid_i·q − fees |
| 3 | `convertPositions(marketId, 2^n − 1, q)` on the n NOs | + (n−1)·q |
| Net | Σ bid_i − 1 − fees per set, **instant** | peak capital n·q; most of it returns within the same minute |

**Simpler equivalent:** since selling YES at b_i is buying NO at 1−b_i, do (e) directly and skip the splits. VERIFIED (mirrored books + convert source).

### (e) Buy all NO, then convert (the practical v1 neg-risk arb)

| Step | Action | Collateral | Failure points |
|---|---|---|---|
| 1..k | BUY NO on each tradable question at askNO_i = 1 − bidYES_i (FOK) | Σ askNO_i·q + fees | leg risk; the 1–3 s sports delay (§3.4) during which the order cannot be cancelled; 5-share minimum; tick grid |
| k+1 | wait for every fill to land on-chain | — | ~2.3 s median after match (§3.6); trade status `RETRYING`/`FAILED` possible |
| k+2 | `NegRiskCtfCollateralAdapter.convertPositions(marketId, indexSet(k bits), q)` via relayer | returns (k−1)·q pUSD (+ YES of any non-traded / placeholder questions) | `onlyUnpaused(USDCE)`; approvals; nonzero `feeBips` (0 in sample) |
| Net | (k−1) − Σ askNO_i − fees per set | instant | profit condition ⇔ Σ_{tradable} bidYES_i > 1 + fees/q |

Notes:
- Fees are small on NO legs priced near 1 because p(1−p) is small. Example at rate 0.04 and NO price 0.90: 0.0036 per share per leg, so 10
  legs ≈ 0.036 per set. That can exceed a typical displayed edge of 0.01–0.03. Use each market's `feeSchedule`.
- When to use k < n: only if the excluded questions' YES is worth ≥ 0 to you (always true) **and** you accept holding them.
- Capital recycling: (k−1)/k of the outlay comes back within one block of the convert. Total wall-clock after the last fill is about
  2–3 s (settlement) + one relayer transaction (blocks are 1.5 s; relayer queue not measured).

### Instant vs. waiting, and capital lock-up

| Operation | Instant? | Measured / documented timing |
|---|---|---|
| CLOB match → on-chain fill | async | median **2.27 s**, p10 1.41 s, p90 2.94 s, max 3.50 s (397 trades, 2026-10-17 15:13 UTC; block time has 1 s resolution) VERIFIED |
| split / merge / convert | yes (1 tx) | Polygon block time **1.5 s** (last 5,000 blocks); `finalized` tag 1 block behind. VERIFIED |
| resolution after `endDate` | no | see §4.5 (median ~2–3 h for UMA, ~1 min Chainlink) |
| redemption | yes (1 tx) or automatic | AutoRedeemer median **~12 s** after resolution (§4.6) |

---

## 3. Order types, matching and settlement

### 3.1 Order types (VERIFIED, [/concepts/order-lifecycle](https://docs.polymarket.com/concepts/order-lifecycle.md), [/trading/place-orders](https://docs.polymarket.com/trading/place-orders.md))

| Type | Behaviour | Details |
|---|---|---|
| GTC | rests until filled or cancelled | |
| GTD | rests until expiry | expires **1 min before** the stated `expiration`; expiration must be ≥ 3 min ahead, so the effective minimum lifetime is ~2 min |
| FOK | fill entirely or reject | market order; `expiration` must be "0" |
| FAK | fill what is available, cancel the rest | rejected if nothing matches |
| Post-only | flag on GTC/GTD; rejected if it would cross ("invalid post-only order: order crosses book") | added Jan 2026 |
| "Market order" | a limit order priced to cross. **BUY amount is pre-fee USD notional for FOK/FAK; GTC/GTD BUY targets shares** | [api-integrations](https://docs.polymarket.com/migrate/polymarket-v2/api-integrations.md) |

- Batch: `POST /orders` max **15** orders ([CLOB OpenAPI](https://docs.polymarket.com/api-spec/clob-openapi.yaml)). Each order is evaluated independently, so a batch is **not atomic**.
- Cancels: `DELETE /orders` max 1,000 ids (OpenAPI; [changelog 2026-06-15](https://docs.polymarket.com/changelog/predictions.md)). The manage-orders page still says 3,000, a doc inconsistency.
  Orders cannot be amended; a change is cancel + replace. A partially filled order can only have its remainder cancelled.
- Rate limits: POST /order 120,000 per 10 min sustained ([changelog 2026-06-01](https://docs.polymarket.com/changelog/predictions.md)).
- Available size = balance − Σ(open size − filled) ([order lifecycle](https://docs.polymarket.com/concepts/order-lifecycle.md)).

### 3.2 Tick size and minimum size

- Allowed ticks: 0.1, 0.01, 0.005, 0.0025 (World Cup only), 0.001, 0.0001. The CLOB rejects off-grid prices. A `tick_size_change`
  WebSocket event signals a change ([market-details](https://docs.polymarket.com/market-data/market-details.md),
  [realtime-data](https://docs.polymarket.com/market-data/realtime-data.md)). VERIFIED.
- **Near extremes the tick becomes 0.001.** The current docs do not state the rule. The cross-section is strongly consistent with "0.001 when price < 0.04
  or > 0.96" (census, mid = Gamma (bestBid+bestAsk)/2):

| mid bucket | ≤0.02 | 0.02–0.04 | 0.04–0.06 | 0.06–0.10 | 0.10–0.50 | 0.50–0.90 | 0.90–0.94 | 0.94–0.96 | 0.96–0.98 | >0.98 |
|---|---|---|---|---|---|---|---|---|---|---|
| share with tick 0.001 | 100% | 97.9% | 68.9% | 25.8% | 5.5% | 3.1% | 18.8% | 55.6% | 100% | 100% |
| n | 8,303 | 7,522 | 5,431 | 6,959 | 100,277 | 21,975 | 846 | 496 | 505 | 2,068 |

  The association is VERIFIED. The exact thresholds and any hysteresis are PLAUSIBLE (they match older Polymarket docs, which are no longer online).
  The tick can change while you hold resting orders, so near-resolution strategies must listen for `tick_size_change`.
- Minimum order size is 5 on essentially all markets (census). The docs table calls `min_order_size` a share count, while an SDK comment calls it a "USDC
  notional" (inconsistency; the CLOB book example and the error text "Size (…) lower than the minimum" suggest shares). PLAUSIBLE: shares.

### 3.3 Matching-engine restarts, restricted modes, heartbeats

VERIFIED ([/trading/matching-engine](https://docs.polymarket.com/trading/matching-engine.md), [/trading/manage-orders](https://docs.polymarket.com/trading/manage-orders.md), [error codes](https://docs.polymarket.com/resources/error-codes.md)):
- Restarts are announced (aim ~2 days' notice) on Telegram and Discord. During a restart, order actions return **HTTP 425** (`Retry-After`). Afterwards there is a
  **2-minute post-only mode** (HTTP 503 `post_only_mode`, `retry_after_seconds`); cancels stay available. Cancel-only and fully disabled
  modes also exist (503 "trading is disabled"). Plan for windows in which you cannot take liquidity, which matters for unwinding a broken arb leg.
- **Heartbeats:** once started (`POST /v1/heartbeats`), if no valid heartbeat arrives within **10 s**, all open orders of those API
  credentials are cancelled. The check runs every 5 s, so cancellation can take up to ~15 s. Send every 5 s.
- Closed-only mode: an account-level circuit breaker that allows only position-reducing orders.
- The 2026-04-28 V2 cutover **wiped all open orders**. Expect the same at future protocol migrations ([changelog](https://docs.polymarket.com/changelog/predictions.md)).

### 3.4 Per-market delays (`secondsDelay`, taker delay)

| Delay | Where | Size | Evidence |
|---|---|---|---|
| Sports/game delay (`secondsDelay`, CLOB `sd`) | **sports only**: 1 s on 237,349 open markets (92% of open sports markets); **3 s on 533** (CS2 odd/even kills/rounds, cricket props, a few soccer); none outside sports. **[corrected by verifier 2026-10-17]** One exception: a stale weather market ("highest temperature in Atlanta … May 15", still flagged open) has `sd`=3 live. Legacy `sports_fees_v2` futures (e.g. UCL/EPL winner) have no delay | 1–3 s | census; CLOB `/clob-markets` `sd` matched Gamma in 40 of 40 sampled markets. VERIFIED |
| Crypto taker delay (`itode`) | crypto **up/down** markets (12 of 12 sampled `itode:true`; 0 of 48 in other categories). **[corrected by verifier 2026-10-17]** Not all of them. Live `/clob-markets` shows `itode:true` on **5-min, 15-min and hourly** crypto up/down markets (every one of ~200 hourly markets checked). It is absent on **4-hour** (`*-updown-4h`) and **daily** (`*-up-or-down-on-<date>`) up/down markets and on price-level crypto markets (`*-above-*`, "will the price"). It is also `true` on some **finance** up/down markets: AAPL, SPY, SPCX and MU, but not SPX, DAX, NIK and other indices. This matches the docs' "selected crypto and finance up/down markets" ([order-lifecycle](https://docs.polymarket.com/concepts/order-lifecycle.md)) | **150 ms** since 2026-09-04 (was 250 → 50 → 150) | [changelog](https://docs.polymarket.com/changelog/predictions.md). The order-lifecycle doc and OpenAPI still say 250 ms |

Semantics (VERIFIED, [order lifecycle](https://docs.polymarket.com/concepts/order-lifecycle.md)): a marketable order is held (status
`delayed`). **It cannot be cancelled during the delay.** Balance, market and risk checks rerun when the delay ends, and the order is then
matched, rested (`unmatched`) or rejected. The docs say the sports delay is "enabled on configured sports markets around live game conditions". Whether it applies before kick-off is PLAUSIBLE but not tested,
since testing would require placing orders.

Implications for latency strategies: in-play sports **takers cannot snipe stale quotes**. Makers see the information and can cancel
(cancels are not delayed) before the delayed taker order matches. Live sports therefore protects makers and penalizes takers. For multi-leg arbs, every sports leg is a
1–3 s commitment that cannot be withdrawn. Crypto up/down has a smaller 150 ms speed bump with the same logic.

### 3.5 Self-trade

There are no documented self-trade-prevention rules for the prediction CLOB. **UNSUPPORTED** either way. The Exchange contracts do not check
maker ≠ taker (source search). The Taker Rebate terms reserve the right to strip rebates for "wash trading, self-matching"
([/programs/taker-rebates](https://docs.polymarket.com/programs/taker-rebates.md)). Perps document CancelMaker STP ([/perps/faq](https://docs.polymarket.com/perps/faq.md)); that does not apply to predictions.

### 3.6 How trades settle on-chain, and how fast

- Matching is off-chain. The operator then calls `matchOrders(taker, makers[], …)`, which is `onlyOperator`. Settlement transfers tokens, or **mints
  (BUY+BUY complements) / merges (SELL+SELL complements)** within the same transaction, and is atomic per match ([MATCH_ORDERS_LIFECYCLE.md](https://github.com/Polymarket/polymarket-v2-external/blob/main/src/exchange/MATCH_ORDERS_LIFECYCLE.md)). VERIFIED.
- Trade statuses: MATCHED → MINED → CONFIRMED, or RETRYING → FAILED. Since 2026-07-24 the order response returns `tradeIDs` and no inline tx hashes
  (async commit pipeline). VERIFIED ([changelog](https://docs.polymarket.com/changelog/predictions.md)).
- **Measured match → block latency:** median **2.27 s** (p90 2.94 s, max 3.50 s, n=397 trades on the 60 highest-volume markets,
  150 s window). Gas per settlement tx: median 286k (mean 476k). Effective gas price median 384 gwei, so ≈ $0.01 per tx, paid by the operator. VERIFIED.
  Caveat: one 150-second window on one day, and only fills that appeared in `last_trade_price`.
- Not verified: whether the CLOB lets you re-sell or merge tokens before the fill is MINED. UNSUPPORTED. Assume you must wait for the on-chain balance.

---

## 4. Resolution

### 4.1 UMA flow on v1 markets (what the contracts actually do)

[UmaCtfAdapter source](https://github.com/Polymarket/uma-ctf-adapter/blob/main/src/UmaCtfAdapter.sol) (VERIFIED by reading source), [/concepts/resolution](https://docs.polymarket.com/concepts/resolution.md):

1. The adapter posts a `YES_OR_NO_QUERY` price request (event-based) with `reward`, `proposalBond` and optional custom `liveness`.
2. A proposer posts the outcome plus a bond. Under MOOV2, only **whitelisted proposers** may propose on Polymarket requests. Criteria: ≥5 proposals and
   >95% accuracy over 6 months, updated monthly; disputes stay permissionless ([UMA docs](https://docs.uma.xyz/using-uma/default-proposer-whitelist);
   [The Block, 2025-08-12, UMIP-189 passed 2025-08-06](https://www.theblock.co/post/366507/polymarket-uma-oracle-update)). Most markets in the sample resolve through MOOV2 adapters (§1.2). VERIFIED.
3. Liveness (challenge window): default **7200 s** on both OOs (eth_call). Many markets override it (Gamma `customLiveness`, census below).
4. **First dispute:** the `priceDisputed` callback **resets** the question, i.e. it sends a fresh price request. The first dispute does not go to a vote.
   **Second dispute:** the request escalates to UMA's DVM. A DVM "ignore price" resets again. Price 0.5 maps to **[1,1], a 50-50 payout**. Neg-risk
   (NegRiskOperator) does not accept ties.
5. DVM: **48 h commit-reveal rounds** (24 h + 24 h). A vote that misses quorum (GAT 5M UMA and SPAT 65% at launch) **rolls** to the next round, up to 4 times
   ([UMA DVM 2.0](https://docs.uma.xyz/protocol-overview/dvm-2.0), [UMA governance](https://docs.uma.xyz/community/governance)). Polymarket's page cites a 24–48 h
   debate period plus ~48 h voting, "4–6 days total" for a disputed market. With rolls, it can take longer. VERIFIED (docs).
6. Neg-risk v1: the adapter reports to a **NegRiskOperator**, which can impose a `DELAY_PERIOD` before `resolveQuestion`. The deployed values are 3600 s on
   `0x7152…` and 0 on `0x6619…` (eth_call). The repo HEAD source says 0, so source and deployment differ. VERIFIED.

**Admin powers (tail risk):** UmaCtfAdapter `flag` → after `SAFETY_PERIOD` (1 h in repo HEAD; deployed value not readable), `resolveManually(payouts)`;
`pause` and `reset`. NegRiskOperator `flagQuestion` → `emergencyResolveQuestion(result)`. In V2, OracleAggregator **admin `resolveResult()` can force-finalize at any
time before resolution**, and modules can `pauseResolution(eventId)` ([oracle README](https://github.com/Polymarket/polymarket-v2-external/blob/main/src/oracle/README.md),
[docs/modules.md](https://github.com/Polymarket/polymarket-v2-external/blob/main/docs/modules.md)). VERIFIED (source). Resolution is ultimately not trustless.

### 4.2 Bonds, rewards, liveness: docs vs live fields

The docs say the bond is "typically $750" and the challenge period is "2 hours". Live Gamma fields on **open** markets (census, VERIFIED) disagree:

| Field | Values (count of open markets) |
|---|---|
| `umaBond` (pUSD) | **250**: 240,862 (sports 234,921); **500**: 42,518 (most non-sports); 2,500: 917; 25,000: 96; 50,000: 54 (large politics); 10,000: 11; **750: 26** |
| `umaReward` | 0.8: 233,512; 5: 35,688; 0.6/3.5/1.5/2/20/10: the rest |
| `customLiveness` (s) | **900**: 88,960 (sports 84,741; weather 3,102; finance 1,109); 0 = default 7200: 39,028; 600: 1,362 (crypto); 1,800: 3,120; 7,200: 830; 3,600: 215; null: 154,203 |

**On-chain confirmation (verifier, 2026-10-17).** Over the last 3,000 blocks (~75 min), `QuestionInitialized` events from
adapters `0x6507…` and `0x69c4…` showed `proposalBond` = 250 pUSD on 2,571 questions and 500 on 187, with none at 750.
The first 150 `ProposePrice` events on MOOV2 `0x2c0367a9db231ddebd88a94b4f6461a6e47c58b1` from those adapters all had
`expirationTimestamp − block time` = 900 s (`analyses/verification/v06_uma_onchain_params.py`). So the Gamma fields
match what the contracts enforce.

So a typical sports market's challenge window is **15 minutes, not 2 hours**, with a $250 bond. Low bonds and short liveness make faster but cheaper-to-attack
resolutions. A low bond also caps a disputer's reward.

### 4.3 V2 resolution path (for future v2 markets)

`OracleAggregator`: per-request reporter modules (UMA OOReporter, Chainlink, EOA) vote. A threshold creates a proposal and starts a Polymarket
**liveness** window (max 7 days, editable by the operator). Disputer modules or conflicting reports trigger arbitration, and an arbitrator or admin calls `resolveResult`.
Request types are BINARY, INCREMENTAL_NEGRISK and ATOMIC_NEGRISK. Gamma shows `resolutionStatus` (inactive/active/resolved) for v2, and v1 uses
`umaResolutionStatus`. VERIFIED ([oracle README](https://github.com/Polymarket/polymarket-v2-external/blob/main/src/oracle/README.md), [api-integrations](https://docs.polymarket.com/migrate/polymarket-v2/api-integrations.md)).

### 4.4 Status fields and how often disputes happen

- `umaResolutionStatuses` is a JSON string of status events. Observed in the closed sample: `["proposed","proposed"]` 22,363; `["proposed"]` 10,066; `[]` 4,784
  (Chainlink); histories with `"disputed"` 13 (up to 9 dispute entries, e.g. "Iran charges Hormuz fees by September 30?", $0.5M volume, 8 disputes).
  The doubled "proposed" is undocumented. UNSUPPORTED interpretation: it may log both the adapter request and the proposal.
- `automaticallyResolved`: **true on 100% of 37,236 closed sampled markets**, including UMA-resolved politics, and null on open markets. It is **not** a
  sports auto-resolution flag and carries no information for filtering. The field is undocumented (no description in the [Gamma OpenAPI](https://docs.polymarket.com/api-spec/gamma-openapi.yaml)).
- `fallbackResolutionType`: `none` or `equal_split`. `equal_split` is set on 18,071 open markets (sports 17,800: player props such as goals, assists and shots, tennis set
  handicaps, spreads and totals; crypto 232; weather 39). In the closed sample it was `none` on every row, yet 493 markets paid 50-50 (below), so
  the field appears not to persist after close. PLAUSIBLE meaning: 50-50 if the event is void (player does not play, set not played).
- **Dispute frequency (measured):**

| Measure | Sample | Rate |
|---|---|---|
| Gamma history contains "disputed" | 37,236 closed markets, six fixed 6-h windows Aug–Oct 2026 | **13 (0.035%)**; sports 7/28,921 (0.024%); crypto 0/7,355; other categories **6/960 (0.63%)** |
| `/v2/resolutions` `was_disputed=true` | 2,160 (all 960 non-sports/non-crypto + 600 sports + 600 crypto) | 2 (0.09%). It misses some Gamma-flagged disputes, so it likely reflects the latest request only |
| first proposal ≠ final price | 1,276 rows with a proposal | 1 |

  Secondary reports (not verified): ~230 contracts entered dispute in April 2026, "<1% of contracts"
  ([KuCoin/BlockBeats, 2026-05-26](https://www.kucoin.com/news/flash/polymarket-dispute-resolutions-dominated-by-9-whale-addresses-critics-raise-concerns)). ">1,150 markets
  triggered arbitration in 2026" by mid-May, and a WSJ analysis that ≥60% of active UMA voters are linked to Polymarket accounts
  ([Finance Magnates, 2026-05-19](https://www.financemagnates.com/fintech/polymarkets-arbitration-model-faces-conflict-of-interest-questions/)). These are consistent with the
  measured order of magnitude, since disputes concentrate in subjective non-sports markets.

- **50-50 resolutions (measured):** 493 of 37,236 (1.32%). **Sports 492/28,921 (1.70%)**: tennis totals and set props, LoL/CS game-3+ props, child moneylines
  (sub-markets that were not played). Crypto 1. No other categories. A position bought at 0.99 pays 0.50 in these cases, a material tail for
  "buy near-certain outcome" sports strategies. VERIFIED (Gamma `outcomePrices` on closed markets).
  **[corrected by verifier 2026-10-17]** The 1.70% depends on the sample and should not be used as a general rate.
  - By window, this sample ranges from 0.93% (09-17) to 3.17% (08-20).
  - A fresh sample of 3,807 sports markets closed 2026-10-17 21:22–22:02 UTC, mostly soccer, had 11 (0.29%).
  - The data-infrastructure sample (Oct 10–12) had 2 of 2,000 (0.1%).
  - The 50-50s concentrate in specific market types: tennis match/set totals and set handicaps, esports game-3+ and
    objective props, and child moneylines.
  - Model the tail per `sportsMarketType`, not per category.
- Clarifications: "Additional context" updates are published on-chain via a bulletin board contract and should not change the question's intent
  ([/concepts/resolution](https://docs.polymarket.com/concepts/resolution.md)). `/v2/resolutions.new_version_q` ("rules updated after posing") was true on 1,276 of 2,160 rows, including
  100% of politics, culture and tech. That looks systematic (possibly re-registration), so do not read it as "clarified". UNSUPPORTED interpretation.

### 4.5 Time from `endDate` to resolution (capital lock-up)

Hours from Gamma `endDate` to the `/v2/resolutions` last-update timestamp (which equals Gamma `closedTime` in these rows). Negative
means resolved before `endDate` (early resolution of "by date X" markets, or a placeholder `endDate`):

| category | n | p10 | median | p90 |
|---|---|---|---|---|
| crypto | 600 | 0.01 | **0.02** (~1 min) | 0.21 |
| sports | 575 | −166 | **3.0** | 6.1 |
| politics | 188 | −274 | **2.1** | 8.7 |
| culture | 134 | −575 | 3.1 | 24.2 |
| economics | 39 | −7.1 | 1.9 | 34.7 |
| finance | 47 | −5.9 | 0.8 | 18.3 |
| tech | 287 | −131 | −9.9 | 4.1 |

VERIFIED (sample). The undisputed UMA path is about 2–3 h after the event. **[corrected by verifier 2026-10-17]** For
sports this is measured from the scheduled start: `endDate` = `gameStartTime` on 97.8% of sports markets (§0.5). It
is not measured from the end of the game, so the post-game lock-up is shorter than the table suggests. Disputed markets add days (4–6+). Early resolution is common: the market
closes as soon as a "by date" event happens, so lock-up can end well before `endDate`.

### 4.6 Redemption and auto-redeem

- AutoRedeemer (`0xa120…00af`) `redeem`/`redeemBinary`/`redeemNegRisk` are `onlyOperator`. They redeem the **full balance** of holders who
  granted `setApprovalForAll(AutoRedeemer)` and forward the pUSD in the same transaction. "Approval alone does not schedule redemption"
  ([contract-integrations](https://docs.polymarket.com/migrate/polymarket-v2/contract-integrations.md), [docs/router.md](https://github.com/Polymarket/polymarket-v2-external/blob/main/docs/router.md)). VERIFIED.
- Data API `/v2/status` ingests `auto_redeem_v3_binary_redemption` and other `auto_redeem_*` cursors. VERIFIED (live).
- **Measured activity:** 14,417 BinaryRedemption, 1,772 NegRiskRedemption and 808 V2 Redemption events in the last 3,000 blocks (~75 min). In a 600-block window,
  4,374 events in 447 txs (median 6 and max 20 holders per tx). **First auto-redeem landed a median 0.2 min (~12 s) after Gamma `closedTime`; max 1.2 min**
  (n=150 conditions). VERIFIED. Caveat: a 15-minute window only observes redemptions near resolution, and only for approving wallets. Whether web-app wallets are approved by default is PLAUSIBLE but not verified.
- Manual redemption has no deadline. Losing-side redemptions pay 0 (0.8% of auto events).

### 4.7 Documented controversial resolutions (tail-risk illustrations; secondary sources)

| When | Market | What happened | Source |
|---|---|---|---|
| Jun 2024 | "Was Barron Trump involved in DJT?" (>$1M) | UMA voted "No"; Polymarket publicly said "UMA got this resolution wrong" and promised a fix. Whether refunds followed is not verified | [The Block](https://www.theblock.co/post/302171/polymarket-contradicts-umas-resolution-on-barron-trumps-involvement-with-djt-token) |
| Mar 2025 | "Ukraine agrees to Trump mineral deal before April?" (~$7M) | resolved "Yes" with no agreement signed; alleged UMA-whale vote; Polymarket called it "unprecedented", said it was "not a market failure", **no refunds** | [The Block, 2025-03-26](https://www.theblock.co/post/348171/polymarket-says-governance-attack-by-uma-whale-to-hijack-a-bets-resolution-is-unprecedented) |
| Jun–Jul 2025 | "Zelenskyy photographed wearing a suit…" (>$237M volume) | initial "Yes" proposal disputed and overturned; finalized "No" on Jul 1 for lack of "credible reporting consensus" | [Decrypt, 2025-07-09](https://decrypt.co/329210/polymarket-rules-no-237m-bet-zelenskyy-suit) |
| May–Jun 2026 | "Strategy sells any bitcoin by May 31?" (>$80M) | 32 BTC sold May 26–31 but disclosed Jun 1; two disputes; UMA vote 98.6% "No" (607 voters); Polymarket note: confirmation "outside of the market's time frame does not qualify" | [Cointelegraph, 2026-06-04](https://cointelegraph.com/news/polymarket-dispute-strategys-bitcoin-sale-resolves-no), [The Block](https://theblock.co/post/403600/polymarket-upholds-no-outcome-strategy-bitcoin-sale-market) |
| Dec 2025 | "Polymarket U.S. go live in 2025?" | reported resolved "Yes" while many users lacked access (lead only; source page paywalled, not read) | [Sportico](https://www.sportico.com/business/sports-betting/2025/polymarket-uma-resolution-crypto-1234878760/) (UNSUPPORTED) |

Common thread: the wording of the rules and the **timing of public confirmation** decide outcomes, not the underlying fact. Voting is token-weighted and
concentrated. Model a small probability of the economically "wrong" resolution on subjective markets, and price that probability into anything held to resolution.

---

## 5. Combos and Perps

### 5.1 Combos (multi-leg RFQ) and collateral return

VERIFIED ([/trading/combos/overview](https://docs.polymarket.com/trading/combos/overview.md), [requesters](https://docs.polymarket.com/trading/combos/requesters.md),
[collateral-return](https://docs.polymarket.com/trading/combos/collateral-return.md), [CombinatorialModule source](https://github.com/Polymarket/polymarket-v2-external/blob/main/src/modules/CombinatorialModule.sol)):

- A Combo is a conjunction of 2–50 legs (V2 position ids, binary or neg-risk). YES pays the product of the leg payouts; NO pays the complement. It is one binary-shaped pair
  traded via **RFQ only**: market makers quote within 400 ms, the requester accepts within a 5 s window (the requesters page; the overview diagram says 10 s, a doc
  inconsistency), and optional Last Look gives the MM 1 s. The requester's `side` must currently be "YES". BUY is sized in notional, SELL in shares. Limit: 15 RFQ creates per minute per maker address.
- On-chain the module rejects only legs that share a condition (`ConflictingConditions`). Operations can reject other legs of the same neg-risk event
  (`EventAlreadyPresent`). The gateway requires "mutually compatible" legs.
- Collateral return (Router `combinatorialCollateralReturn`, planned off-chain): decomposes offsetting Combo positions and merges complements back to pUSD
  before resolution. Supports Deposit, Safe and Proxy wallets, not EOAs.

Can Combos express logical arbitrage? **Mostly no, for a retail requester.**
1. A requester cannot post a resting combo order or sell an arbitrary NO combo. Only YES-side RFQs are allowed, and quotes come from MMs who
   price the logical structure and keep last-look optionality, so mispricings are unlikely to be offered.
2. Logical relations between CLOB markets (A ⊂ B, so buy YES(B) + NO(A) when pB + 1 − pA < 1) are executed on the CLOB itself. Combos add nothing to that leg risk.
3. The real edge is on the **quoting side**: an MM who holds offsetting combos can release collateral early via collateral return. That needs MM
   onboarding and capital, which puts it out of scope for this project's read-only stance.
   Combo mispricing versus the product of leg prices could only be **monitored** if RFQ quotes were public. Confirmed-trade broadcasts go to connected MMs. UNSUPPORTED that any public feed exists.

### 5.2 Perps

VERIFIED ([/perps/overview](https://docs.polymarket.com/perps/overview.md), [/perps/faq](https://docs.polymarket.com/perps/faq.md)): perpetual futures on crypto,
indices, commodities and equities, with pUSD collateral, up to **20x** (crypto, SP500, oil, gold, silver) or 10x (other RWAs), funding payments, and CancelMaker STP. **Order placement is not
permitted from the United States, Canada, Cuba, Iran, North Korea, Syria, Crimea, Donetsk, Luhansk.**
Relevance: low. Perps could hedge the delta of crypto or finance up/down positions within one collateral account, but only in eligible jurisdictions.
They play no part in settlement or resolution of prediction markets.

---

## 6. Contradictions and caveats

1. **Docs vs live UMA parameters:** "bond typically $750" and "2-hour challenge period" vs live `umaBond` 250/500 (750 on 26 markets) and `customLiveness` 900 s on ~89k markets.
2. **Taker delay:** order-lifecycle doc and CLOB OpenAPI (`itode`) say 250 ms; the changelog says 150 ms since 2026-09-04.
3. **`DELETE /orders` limit:** manage-orders doc says 3,000 ids; OpenAPI and changelog say 1,000.
4. **Combo acceptance window:** 10 s (overview) vs 5 s (requesters).
5. **"Deprecated" NegRiskAdapter `0xd91E…`** is still the on-chain core of every v1 neg-risk market (only direct Relayer calls are deprecated).
6. **Contracts page omits the resolvers actually in use** (`0x6507…`, `0x69c4…`, `0x2F5e…`, MOOV2 `0x2c03…`, NegRiskOperators `0x6619…`, `0x7152…`) and lists `0xCB18…` twice under different names.
7. **NegRiskOperator `DELAY_PERIOD`:** repo HEAD constant 0 vs deployed 3600 s on `0x7152…`.
8. **`min_order_size` unit:** shares (docs table) vs "USDC notional" (SDK comment).
9. **CONTEXT.md refinements:** "Positions span Conditional Tokens and a PositionManager". In fact, **no open market is v2**; all trading and settlement today is CTF via CTF Exchange V2 contracts, and v1
   markets carry V2 migration ids for Combos. `secondsDelay` is 1 s on ~92% of open sports markets and 3 s on ~533, never outside sports. Crypto up/down instead has the 150 ms `itode` delay.
   **[corrected by verifier 2026-10-17]** `itode` is set only on the 5-min, 15-min and hourly crypto up/down markets, not
   on the 4-hour or daily ones. It is also set on some single-stock/ETF up/down markets (§3.4).
10. **`pmr.api.books()` caveat (affects other agents):** `POST /books` **does not preserve request order** (8 of 30 two-token requests came back
    reversed). Always key results by `asset_id`. VERIFIED.
11. **`automaticallyResolved`** is true on every closed market sampled, so it is not a sports auto-resolution signal.

## 7. Open questions

- Relayer queueing latency from submit to `STATE_CONFIRMED` for merge or convert (not measured; needs authenticated submission).
- Whether the sports `secondsDelay` is active pre-game or only in-play (needs order placement; out of scope).
- Whether the CLOB lets a just-matched (not yet MINED) position be sold or merged.
- Exact deployed `SAFETY_PERIOD` of the live UMA adapters (the public getter reverts on all three).
- Semantics of the doubled `"proposed"` in `umaResolutionStatuses`, and of `new_version_q` being true on 100% of politics rows.
- When native v2 markets (synthetic Other, horizontal merge) will launch, and whether "Other" will have its own CLOB book.
- Dispute rates in longer-dated, high-volume political markets (the sample is endDate-window based and dominated by short-dated markets; 188 politics rows).
