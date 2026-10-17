# Linkage: mintblade, GRIMDRIP and endlessFate (as of 2026-10-17)

Wallets (Polymarket proxy = V2 Deposit Wallet addresses): mintblade `0x96cf…1acb`, GRIMDRIP `0x3f87…742c`, endlessFate `0x5e4c…dba2`.
Scripts: `analyses/wallets/linkage_01…11*.py` (plus `linkage_04b`). Data: `data/derived/linkage_*.parquet`. All raw RPC / API
responses are stored with provenance under `data/raw/` (sources `polygon*`, `ethereum-tenderly`, `bsc*`, `relay`, `gamma`,
`blockscout-eth`). Address labels below come from **Etherscan public name tags** fetched 2026-10-17 (WebFetch); no label is
inferred from behaviour alone unless marked PLAUSIBLE. Nothing here identifies, or tries to identify, any real person.

## 0. Bottom line

| pair | classification | decisive evidence | what is still not proven |
|---|---|---|---|
| mintblade - GRIMDRIP | **STRONG PROBABILISTIC** | 100% of GRIMDRIP's delivered withdrawals ($17.53M) and $8.0M of mintblade's go to the **same Binance deposit address A** (`0xb08b…317d`; GRIMDRIP via a hop that holds only GRIMDRIP's money). Profiles created 14 min apart; only 3 of 5,886 pairs of large traders in these markets were created that close, and all 3 pairs are in this cluster. | No shared signing key (3 distinct owner EOAs). A deposit address identifies an exchange account, not a person. |
| mintblade - endlessFate | **STRONG PROBABILISTIC** | **Cross-routing into two Binance deposit addresses.** endlessFate's hop pays A, which mintblade also uses directly. mintblade's hop pays B (`0x3319…b072`, a fresh address), which endlessFate also uses directly, 86 minutes earlier. Also the same 3 Saudi Arabia–Uruguay legs in the same direction, 6–47 min apart. | Same as above |
| GRIMDRIP - endlessFate | **STRONG PROBABILISTIC** | Both hops forward into A on 2026-06-18: endlessFate $6.35M, GRIMDRIP $17.53M. | No common markets, so no trading evidence |
| any pair, key-level | **NONE** | Each wallet has its own owner EOA. Every executed batch and every one of the 1,862 CLOB order signatures (721 / 667 / 474, one per fill tx) recovers to that wallet's own owner, so no delegated session signer was seen. No direct transfers among the 3 wallets or their owners. | n/a |

- **What is CONFIRMED, as on-chain fact (VERIFIED):** the withdrawal proceeds of all three wallets were sent, directly or through one single-purpose hop, to two addresses. Etherscan tags both as *Binance Deposit*. Binance's *Deposit Funder 1* paid their gas, and their entire balances were swept to Binance hot wallets.
- **Inference (PLAUSIBLE):** an exchange deposit address credits one exchange account. So the proceeds of all three wallets ended up in at most two Binance accounts, and at least one of them received money from all three. I therefore treat the three as **one economic cluster**. This is not proof that one person made every trading decision.
- **The cluster is larger than three, and it includes big losers (PLAUSIBLE membership, same evidence class).** Deposit address A also received Relay withdrawals from at least 9 other Polymarket wallets, 6 directly and 3 through one-use hops; 7 of them have profiles (Section 4).
  - One of them is **FlickRaw** (−$4.87M realised). It was created 8.6 min after GRIMDRIP. Its first trade was the same $4.80 Mets ticket that mintblade bought, 73 s after mintblade.
  - Others include downtownfee (−$3.39M). A Kraken-swept address received money from both endlessFate and **LEEEROYJENKINS** (−$2.75M).
  - So "five wins" on one account may be the visible tail of a multi-account book.
- **Screens by scenario (Section 8):**
  - (a) Independent wallets: only mintblade passes, and only when counting per market (5/5). It fails per event (3 events).
  - (b) mintblade + GRIMDRIP as one entity: 7 market decisions, all won, over 4 events. It passes "≥5, no losses" per market, fails "exactly 5", and fails both rules per event.
  - (c) All three as one entity: 13 market decisions (10 won) over 10 events (7 made money). It fails every screen.
  - Under (c), the realised P&L is $23.87M on a cluster peak capital of $12.07M.
  - (d) The extended book (11 accounts) nets **+$14.9M**, because four of its accounts lost $15.0M.

## 1. Wallet type and controller (VERIFIED; `linkage_01_wallet_type.py`, `linkage_wallet_controllers.parquet`, `linkage_batch_signers.parquet`)

| | mintblade | GRIMDRIP | endlessFate |
|---|---|---|---|
| bytecode | 125 B Solady ERC-1967 proxy with immutable args | same | same |
| contract type | Polymarket **Deposit Wallet** (EIP-712 name `DepositWallet` v1) | same | same |
| implementation / factory | `0x58ca…b1eb` / Deposit Wallet Factory `0x0000…cc07` | same | same |
| `getOwners()` / `getThreshold()` | revert (not a Gnosis Safe) | revert | revert |
| `owner()` = immutable walletId | `0x8518d7d0…7058542` | `0xbd6eb13f…eb02c7d83` | `0xc1086e14…b51abe1` |
| CREATE2 address recomputed from (factory, walletId, impl) | matches | matches | matches |
| upgrades / ownership changes | none (one OwnershipTransferred 0x0 → owner at deploy) | none | none |
| deployed | 2026-06-02 14:48:25Z (40 s after profile creation) | 2026-06-02 15:02:07Z | 2026-05-31 11:08:52Z (V2 wallet; profile from 2026-04-27) |
| executed batches whose EIP-712 signature recovers to `owner()` | 49 / 49 | 58 / 58 | 40 / 40 |
| owner EOA state at head | nonce 0, no code, 0 POL, 0 stablecoins | same | same |

- **CLOB order signatures** (`linkage_11_order_signers.py`, `linkage_order_signers.parquet`).
  - Docs /trading/wallets-auth: "A Deposit Wallet owner can give a separate signer scoped, time-limited trading access." So the orders themselves were checked.
  - Every order of the candidates has maker = signer = the wallet and signatureType 3 (ERC-1271), with a 317-byte nested-EIP-712 (ERC-7739 `TypedDataSign`, contents `Order`) signature.
  - Recovering the inner ECDSA key gives the wallet's own `owner()` for **all 1,862 orders**: mintblade 721/721, GRIMDRIP 667/667, endlessFate 474/474, one per fill transaction that pays an exchange. No key is shared between wallets.
- **The three wallets have three different controllers.** Each owner EOA has never sent a transaction itself. It only signs typed `Batch` messages, which Polymarket relayers submit.
  - 87 distinct relayer EOAs submitted these batches, and 30 of them relayed for more than one candidate. That is Polymarket's shared relayer pool, **not evidence of a link**.
- How proxies map to signers (docs /trading/wallets-auth, /resources/contracts): a Deposit Wallet is a CREATE2 clone keyed by its owner. One owner gives one wallet, so two wallets cannot share an owner without having the same address.
  - Owner keys are typically app-generated or embedded-wallet keys tied to a login (PLAUSIBLE). Different keys are therefore fully consistent with one operator running several logins.
- **Key-level link: NONE (VERIFIED).** This rules out a shared Safe or a shared signer. It does not rule out common control.

## 2. Funding (VERIFIED unless marked; `linkage_02*`, `linkage_03`, `linkage_06`)

### On Polygon
- Deposits arrive as pUSD minted to the wallet after a `wrap` (docs /concepts/pusd, CollateralOnramp).
- Each wallet's first-hop source is its **own** Polymarket bridge deposit address. These are EIP-7702 EOAs that all delegate to the same implementation `0xe6ca…`, which is common Polymarket bridge tooling:
  - mintblade `0xb4c3…3a41`: $9.35M
  - GRIMDRIP `0x6e39…d17d`: $10.02M
  - endlessFate `0x8599…8945`: $4.99M, plus a legacy-proxy migration
- Docs (/trading/bridge/deposit) say each deposit address is unique to its wallet, so distinct deposit addresses carry **no information either way**.
- The remaining pUSD inflows are not deposits:
  - **Redemptions.** GRIMDRIP's two inflows from `0xf3cf…52b0` ($9,925,592 + $3,678,377) are exactly its two redemptions. mintblade and endlessFate redeem through the AutoRedeemer `0xa120…00af`.
  - **Rebates and rewards.** Their amounts match `/v2/user-stats` to the cent:
    - Taker rebates from `0x520b…` and `0xd152…`: mintblade $9,156.41 + $18,721.49 = $27,877.90; endlessFate $64,534.48.
    - Maker rebates from `0x3a94…`: $912.59, $535.68 and $977.72.
    - Dust from `0x03b6…`.
  - **Bounced or refunded withdrawals** from the Relay solver `0xf70d…dbef` (nonce 4.96M).
- **Direct transfers among the 3 wallets and their 3 owners:** 0 ERC-20 and 0 ERC-1155 transfers from 2026-04-20 to head (`linkage_transfers_scan.parquet`, 4,306 rows).
- **Counterparties shared on Polygon are all infrastructure or market:**
  - pUSD contract, the exchanges, the Relay depository `0x4cd0…bc31`, the Relay solver, the rebate payers above
  - the CTF Exchange fee receiver `0x115f…` (it appears in the exchange's fee event in the same tx; mintblade paid $0.00576 in fees on its Mets fill)
  - large market makers such as `0x709e…`. The trade counterparties overlap only as makers.

### Off Polygon: who funded the deposit addresses (`linkage_06_origin_chains.py`, `linkage_origin_eth/bsc.parquet`)

| deposit address | Ethereum (USDC) | BNB Chain (USDC) |
|---|---|---|
| mintblade `0xb4c3…` | $4.80M from **0xee7a…4055 "Binance: Hot Wallet 34"** (06-15 21:50 → 06-16 00:37); the rest are Relay refunds of its own failed bridges | $4.55M from **0x8894…d4e3 "Binance 51"** and **0xe2fc…3ae1 "Binance: Withdrawals 7"** (+$2.75M Relay refunds) |
| GRIMDRIP `0x6e39…` | $5.48M from **Binance: Hot Wallet 34** (06-18 14:54 → 15:58) | $4.55M from **Binance 51 + Binance: Withdrawals 7** (06-18) |
| endlessFate `0x8599…` | none | $4.99M from **Binance 51 + Binance: Withdrawals 7** (05-31) |

- **Every external deposit of all three wallets is a Binance withdrawal (VERIFIED).** Shared exchange hot wallets fund millions of users, so taken alone this is **NONE/WEAK** evidence.
- Coverage on BNB Chain is limited. The only free getLogs endpoint allows 100 blocks per call at 5 calls per minute, so only the 150-250 blocks before each Relay origin transaction were scanned. On Ethereum the full window 2026-05-20 to 2026-09-15 was scanned.

## 3. Withdrawals: where the money went (VERIFIED; `linkage_07_sinks.py`, `linkage_10_fund_paths.py`, `linkage_fund_paths.parquet`)

Every withdrawal is a Relay bridge request. The wallet burns pUSD, receives USDC.e, and pays it to the Relay depository `0x4cd0…bc31`. The Relay API (`/requests/v2`, by user and by tx hash) gives the destination chain and recipient. Delivered amounts below are `status=success` requests only. Refunded requests came back to the wallet, as in the earlier "$100 test plus DEPOSIT refund" pattern.

| wallet | delivered to | then forwarded to | final destination ($M) |
|---|---|---|---|
| mintblade | **A** directly: Ethereum $6.00M (06-16 15:55–16:22) + Polygon $2.00M | n/a | **A 8.00** |
| mintblade | hop `0xa623…1a1c` (Ethereum $10.46M, 06-18 14:42–15:32) | **B**: $10.46M, 06-18 15:37–15:55 (12 transfers) | **B 10.46** |
| GRIMDRIP | hop `0xe065…a46f` (Ethereum $13.48M + Polygon $4.06M, 06-18 18:35 → 06-20) | **A**: $13.47M on Ethereum (19:17–21:34) + $4.06M on Polygon | **A 17.53** (≈100%) |
| endlessFate | **B** directly (Polygon $0.50M + BNB $0.40M, 06-18 14:11–14:18) | n/a | **B 0.90** |
| endlessFate | hop `0xac35…2a89` (Ethereum $9.35M + Polygon $2.00M, 06-18 13:28–14:32) | **A**: $4.35M Ethereum (14:24–15:01) + $2.00M Polygon. `0xbbfa…4803`: $5.00M (15:05–15:28) | **A 6.35**, `0xbbfa` 5.00 |
| rebates (July) | mintblade `0x4c6d…`, endlessFate `0x8116…` | not traced | 0.03 / 0.07 |

- **The hops (VERIFIED).** `0xa623…`, `0xac35…` and `0xe065…` are ordinary EOAs with nonces 12, 14 and 19.
  - Each one's stablecoin inflows are **only** its own wallet's Relay deliveries, matched by destination tx hash.
  - Each one signs its own forwarding transfers (`tx.from` = the hop).
  - Each one emptied itself into A, B or `0xbbfa` within minutes to hours.
  - Each hop is therefore under the control of whoever controls that wallet's withdrawals.
- **A = `0xb08b85827f803c37b5a3163ec1f03ce6b21e317d`.**
  - Etherscan public tag "Binance Deposit". Gas funded by "Binance: Deposit Funder 1". 70 transactions, active from 2026-05-19 (a $100 test) to 06-18.
  - Every outflow is a sweep: USDC to Binance: Hot Wallet 34 ($42.5M on Ethereum; $16.1M on Polygon to the same address, where the Ethereum label is assumed to carry over: PLAUSIBLE) and USDT to "Binance 14" `0x28c6…1d60` ($12.8M).
- **B = `0x33193e1592ff490f21f15bd877736aacf3cbb072`.**
  - Etherscan tag "Binance Deposit", first funded by Binance: Deposit Funder 1 on 2026-06-18 15:43:11Z, 3 transactions in total.
  - It swept $15.46M to Binance: Hot Wallet 34 at 15:54–16:01, and on Polygon swept $0.50M the same way.
  - B was a fresh address that day. endlessFate's withdrawal to it was created at 14:11. mintblade's hop paid it from 15:37, 86 min later.
- **`0xbbfa4c80…4803`** (no public tag). Kraken: Hot Wallet 4 funded its gas, and it forwards everything to Kraken: Hot Wallet 4 `0x05ff…f381` (nonce 1.98M). PLAUSIBLY a Kraken deposit address.
  - It received LEEEROYJENKINS' 06-16 withdrawal ($2.25M via Relay), endlessFate's hop ($5.0M on 06-18) and $4.5M from Binance: Hot Wallet 34 (06-19).
- **Timeline on 2026-06-18 (UTC):**
  - 13:28–14:32: endlessFate withdraws.
  - 14:42–15:32: mintblade withdraws.
  - 14:47–16:00: GRIMDRIP is funded from Binance withdrawals and trades CZE-RSA (15:23–16:00).
  - 18:35–20:39: GRIMDRIP withdraws, and its hop pays A.
  - In other words, capital rotates through Binance accounts that receive from all three. Exchange balances are fungible, so the specific dollars cannot be traced through Binance.
- **Withdrawal fingerprint shared by all three, and by the other accounts in Section 4:** a $100 test, then chunks of $999,999 / $499,999 / $399,999 (amount minus $1). Its base rate among Polymarket withdrawers was not measured.
- Noise: dozens of zero-value or fake-token "address-poisoning" transfers with look-alike addresses (`0xb08b…317d`, `0xac35…2a89`, `0x3319…b072` look-alikes) hit A and the hops. They are excluded, since only the real USDC/USDT contracts are counted.

## 4. Extended cluster: other Polymarket accounts paying the same Binance deposit address A (`linkage_08_extended_cluster.py`)

How the list was built:
- Every Ethereum inflow to A was attributed. Relay fills were looked up on the Relay API by tx hash to get the origin Polygon wallet. Non-Relay senders were traced one hop back.
- A's full Ethereum history was covered: first activity 2026-05-19 (a $100 test), last on 06-18.
- A's Ethereum inflows total **$55.27M**. Of that, **$40.0M (72%) is traceable to Polymarket withdrawals**:
  - the three candidates: $23.82M
  - 6 other profiled accounts directly: $9.94M
  - 3 more Polymarket wallets through low-nonce hops that their own Relay withdrawals funded: $6.27M
- The other $15.2M breaks down as follows:
  - USDT $12.76M from 9 EOAs. 8 have nonce 2–3 and each sent a $145–750 test, then the main transfer; one has nonce 188.
  - $2.42M from a busy service contract `0xb92f…` (more than 20k inbound transfers per 50k blocks).
  - $0.06M from one EOA.

| account | created (Gamma) | user id | link to A | distinct markets | realised market P&L | volume | trading window |
|---|---|---|---|---|---|---|---|
| lovelystuff | 2026-03-12 20:01:06 | 6,665,349 | direct ($6.40M, 05-31) | 9 | +$1.80M | $27.1M | 05-24 → 05-30 |
| Inaccuratestake | 2026-03-12 20:07:10 (6 min later, +101 ids) | 6,665,450 | direct ($1.00M, 06-08) | 26 | +$3.85M | $27.9M | 05-24 → 07-17 |
| diggingaround2 | 2026-03-13 20:32 | 6,688,191 | direct ($100 test + $99.68 USDT, 05-21) | 60 | +$0.0003M | $3.7k | 04-21 → 09-13 |
| everydaymortgage | 2026-04-07 16:19:50 | 7,258,544 | via hop `0x3592…` ($1.40M) | 33 | **−$4.02M** | $40.9M | 04-30 → 05-22 |
| downtownfee | 2026-04-07 16:38:11 (18 min later) | 7,259,093 | direct ($2.14M, 06-08) | 50 | **−$3.39M** | $44.6M | 04-29 → 06-07 |
| endlessFate | 2026-04-27 19:18:08 | 7,713,278 | via hop ($6.35M) + B + Kraken-swept `0xbbfa` | 9 | +$7.25M | $26.3M | 06-12 → 06-18 |
| LEEEROYJENKINS | 2026-04-27 19:28:01 (10 min after endlessFate) | 7,713,440 | **not A**: Relay withdrawal $2.25M (06-16) to `0xbbfa`, which also received endlessFate's $5.0M | 7 | **−$2.75M** | $14.7M | 06-14 → 06-15 |
| brightshieldd | 2026-04-28 18:58 | 7,733,173 | direct ($0.40M, 06-08) | 9 | +$0.41M | $6.9M | 05-30 → 07-17 |
| mintblade | 2026-06-02 14:47:45 | 8,422,116 | direct + via hop to B | 5 | +$9.11M | $17.8M | 06-03 → 06-16 |
| GRIMDRIP | 2026-06-02 15:01:41 | 8,422,276 | via hop ($17.53M) | 2 | +$7.51M | $13.6M | 06-18 |
| FlickRaw | 2026-06-02 15:10:19 | 8,422,381 | direct ($100 test, 06-10) | 3 | **−$4.87M** | $9.4M | 06-03 → 06-15 |
| 2 legacy V1 Proxy Wallets `0xeaf7…7110`, `0x2923…26fc` (45-byte EIP-1167 clones, no current profile) | n/a | n/a | via hops `0x5243…` ($2.30M), `0xc4a5…` ($2.57M) | not pulled | not pulled | | |

Sources: `/v2/user-stats` and `/v2/trades` (VERIFIED, pulled 2026-10-17) and Gamma `/public-profile`.

- **Totals for the 10 profiled accounts linked to A:**
  - realised market P&L **+$17.64M**: 7 net winners (+$29.92M) and 3 net losers (−$12.28M)
  - fees $1.37M, rebates $0.15M, volume $214.5M, 206 markets
  - with LEEEROYJENKINS (via `0xbbfa`) the total is **+$14.89M**
  - the 7 non-candidate accounts alone: −$6.23M
- **Accounts are created in tight batches** (VERIFIED timestamps): 03-12 (6 min apart), 04-07 (18 min), 04-27 (10 min), 06-02 (three accounts within 23 min). The $100 test plus $X99,999 chunk withdrawal pattern recurs across the batches.
  - FlickRaw's first trade was the $4.80 Mets ticket, 73 s after mintblade's identical ticket.
  - It then bought Netherlands-win Yes ($3.29M, 06-14) and Belgium-win Yes ($1.51M, 06-15). Both lost, for −$4.87M in total. The Belgium buy was on the same side as endlessFate and LEEEROYJENKINS.
- **Membership status.** The members share the same evidence class as the three candidates: a direct or one-hop withdrawal into deposit address A. So membership is **PLAUSIBLE**, not verified. LEEEROYJENKINS's link runs through a different, Kraken-swept address, which is weaker because that address's tag is unverified.
- **Not done:** a cluster-wide decision-level record (about 185 per-account events; the distinct count is lower because of overlaps) and the V1 history of the two legacy proxies. That is the analysis a copy-trader actually needs (Section 8, scenario d).

## 5. Profile metadata (VERIFIED data; `linkage_04_profiles.py`, `linkage_04b_profile_baseline.py`)

- mintblade was created 2026-06-02 14:47:45Z (Gamma user id 8,422,116) and GRIMDRIP at 15:01:41Z (id 8,422,276). The gap is 13.9 min and 160 ids.
- **Platform rate (why this is weak on its own).**
  - The Deposit Wallet factory deployed **226 wallets** between the two deployments. Over the 3.1-hour window pulled, the rate was 17.6 per minute, including V1-to-V2 migrations of old accounts.
  - New Gamma user ids grew by about **9.7–11.5 per minute**, so about 160 other accounts were created in those 14 minutes.
  - "Created minutes apart" therefore describes hundreds of unrelated pairs every hour.
- **Base rate among large traders (why it is not nothing).**
  - Population: the 109 wallets with ≥$100k in one of the candidates' matches that have a profile date, which makes 5,886 pairs.
  - Only **3 pairs (0.05%)** were created within 14 min of each other, and 1.24% on the same day.
  - All three close pairs sit inside the funds-linked cluster: mintblade–GRIMDRIP (13.9 min, 160 ids), GRIMDRIP–**FlickRaw** (8.6 min, 105 ids), and endlessFate–**LEEEROYJENKINS** (9.9 min, 162 ids).
  - The population is conditional on the candidates' own markets, so the 0.05% is a selected baseline.
- **Name style** (mintblade / GRIMDRIP / endlessFate / FlickRaw / LEEEROYJENKINS, all two-word compounds in different capitalisations) carries no usable signal. Pseudonyms are auto-generated.

## 6. Trading co-movement against baselines (VERIFIED; `linkage_05_comovement.py`, `linkage_pairs.parquet`; the 13 full market tapes)

- **Shared events.** Only mintblade and endlessFate share a match, Saudi Arabia v Uruguay, with the same three legs and directions.
  - endlessFate traded 52–12 min before kick-off; mintblade traded 5–0 min before, at worse prices.
  - **GRIMDRIP shares no market with either.**
- **Same transaction hashes, or trading against each other:** **0** across all 13 full tapes. Among large-wallet pairs with 3 or more common markets, 83.6% share at least one tx, mostly market makers.
- **KSA-URY leg profile (B1).**
  - Of 12 large wallets that traded all three legs, 3 (25%) chose mintblade's profile: endlessFate, mintblade and LEEEROYJENKINS.
  - So P(two random 3-leg traders both on this profile) ≈ 0.06.
- **Pairwise agreement (B2).**
  - Of 421 pairs of large wallets with 3 or more common markets, 16 (3.8%) agree on every market.
  - Among those 16, half had first entries within 35 min of each other.
  - mintblade–endlessFate is one of the 16 (35 min). Unusual, but not extreme.
- **Round-number taker orders (B3).** 95% (mintblade), 95% (GRIMDRIP) and 87% (endlessFate) of taker orders of $1k or more are within $1 of a $1,000 multiple. That is true of only 8 of 69 large takers (11.6%). This is consistent with amount-based market orders, which many UI and API users place, so it is weak to moderate.
- **Test tickets.** mintblade and FlickRaw each bought exactly 5 Mets shares at 0.96 ($4.80) on 2026-06-03, 73 s apart. Within ±2 min only 3 wallets placed any 5-share buy in that market (±10 min: 5 wallets bought Mets 5@0.96). Moderately suggestive.
- **Complementary hedges across wallets:** none within the 13 markets. Every cluster member present (incl. FlickRaw and LEEEROYJENKINS) is on the **same** side, e.g. Belgium Yes for endlessFate, FlickRaw and LEEEROY. Hedges in other markets were not tested.

## 7. Link classification and remaining alternatives

| link | class | for | alternatives that remain |
|---|---|---|---|
| same owner/signer EOA (incl. delegated session signers) | NONE | 3 distinct owners; every batch and every checked order signature recovers to its own owner | n/a |
| direct transfers between the wallets/owners | NONE | 0 transfers (Polygon, 2026-04-20 to head) | n/a |
| common funder (Binance hot wallets) | WEAK | all deposits are Binance withdrawals | exchange hot wallets fund millions of users |
| common destination: Binance deposit A (all 3) and B (mintblade, endlessFate) | **STRONG PROBABILISTIC** (fact VERIFIED; account semantics PLAUSIBLE) | each wallet's proceeds go there directly or via a hop that holds only that wallet's money; A and B are swept to Binance and funded by Binance's deposit funder; B was fresh and used by two wallets within 86 min | (i) A/B belong to an intermediary (OTC desk, broker, account manager or fund) that receives from several independent clients; this still implies a shared financial counterparty and coordination, not independence. (ii) Payments between separate people (profit sharing, a signal seller). (iii) A Binance sub-account structure, i.e. several accounts of one owner. (iv) Mislabelled deposit addresses: low, since the sweep behaviour matches the tag. |
| profile creation 14 min apart; FlickRaw 8.6 min later | WEAK alone; supportive in context | 0.05% of large-trader pairs | ~160 accounts created per 14 min platform-wide |
| KSA-URY same 3 legs (mintblade, endlessFate) | WEAK–MODERATE | 25% of 3-leg large traders share it | public information / copy trading (mintblade later and at worse prices) |
| identical $4.80 Mets ticket (mintblade, FlickRaw) | MODERATE | 2 of 3 five-share buyers within ±2 min | minimum-size test trades are common |
| withdrawal chunking ($100 test, $X99,999) | WEAK–MODERATE | same in all 3 and in the extended accounts | a habit that is easy to copy; base rate not measured |
| same tx / trading against each other / hedges | NONE | 0 shared txs; no opposite sides | n/a |

## 8. Scenarios: the user's screens and P&L (`linkage_09_scenarios.py`, `linkage_scenarios.parquet`)

Counting rules at cluster level:
- A market bought by two cluster wallets on the same outcome is **one** decision, and a match is **one** event.
- P&L is each wallet's own trade and redemption cash flow (realised; all positions resolved, so unrealised P&L is 0). Deposits and withdrawals are never P&L, so routing through Binance cannot double count.
- Peak capital is the maximum simultaneous cost of unresolved positions across the cluster.
- Null: zero edge, matches independent, home-margin states taken from the cluster's notional-weighted entry prices.

| scenario | market decisions (won) | events (made money) | "exactly 5, all won" market / event | "≥5, no losses" market / event | realised P&L | cluster peak capital | P&L / peak | null P(P&L ≥ obs) | null P(all events made money) |
|---|---|---|---|---|---|---|---|---|---|
| (a) mintblade | 5 (5) | 3 (3) | **pass** / fail | **pass** / fail | $9.11M | $8.65M | 1.05 | 0.113 | 0.172 |
| (a) GRIMDRIP | 2 (2) | 1 (1) | fail / fail | fail / fail | $7.51M | $6.10M | 1.23 | 0.288 | 0.498 |
| (a) endlessFate | 9 (6) | 7 (4) | fail / fail | fail / fail | $7.25M | $7.52M | 0.96 | 0.168 | 0.013 |
| (b) mintblade + GRIMDRIP | 7 (7) | 4 (4) | fail / fail | **pass** / fail | $16.62M | $8.65M | 1.92 | 0.032 | 0.085 |
| (c) all three | 13 (10), 3 shared | 10 (7) | fail / fail | fail / fail | $23.87M | $12.07M | 1.98 | 0.028 | 0.003 |

- **Sensitivity (drop stakes < $100, i.e. the $4.80 Mets ticket):**
  - (a) mintblade: 4 markets / 2 events, which fails both screens.
  - (b): 6 markets (all won) / 3 events. It still passes "≥5, no losses" per market and fails per event.
  - (c): 12 / 9, which fails.
- **What changes across scenarios:**
  - **Counting distinct decisions shrinks the evidence.** Under (c), mintblade's and endlessFate's Saudi Arabia–Uruguay positions are one decision. The cluster's real decisions are about 9 football events plus a test ticket, not 16 "markets".
  - **Under (b) the screen passes for the wrong reason.** Merging two wallets adds markets, but the four real events are 3 coin-flip-sized bets plus a test ticket.
  - **P&L does not double count, but capital does.** The cluster's peak capital ($12.07M under (c)) is far below the sum of the wallets' peaks ($22.3M), because money was recycled through Binance between accounts (06-18). So per-wallet "ROI" understates the cluster's leverage of capital. Raw P&L is unchanged.
  - **The null probabilities look smaller for the cluster, but selection worsens.** These three accounts were picked because they won, and the same funds evidence ties them to accounts that lost (Section 4).
  - Even taken at face value, P(P&L ≥ observed) of about 0.03 for a selected cluster is not evidence of edge. The three accounts are survivors chosen from a book that also contains FlickRaw, downtownfee, LEEEROYJENKINS and others.
- **Scenario (d), extended cluster (membership PLAUSIBLE, not proven).** These are the 10 profiled accounts paying A, plus LEEEROYJENKINS via `0xbbfa`.
  - Realised market P&L is **+$14.89M** across 11 accounts and about 213 markets. 7 accounts are up and 4 are down; the losers total −$15.0M.
  - The three candidates' +$23.87M is **160%** of the book's net. The other 8 accounts lost $8.98M combined.
  - At account level, a "winners only" list shows 7 of 11 accounts. A copy-trader who followed "the winning wallets" would have followed the winning accounts of this book, not the book itself.
  - The user's screen cannot be evaluated cluster-wide without the decision-level records of all these accounts, which were not built here.

## 9. What would change the classification

- **Upgrade to CONFIRMED** would require any of:
  - one EOA that signs for two wallets. This is impossible by construction for Deposit Wallet owners, but possible for a delegated session signer, and none was found in the order signatures.
  - a direct pUSD/USDC transfer between two cluster wallets or their hops
  - the same hop EOA used by two wallets
  - exchange or KYC data (not available, and not sought)
- **Downgrade** would follow from evidence that A is a pooled intermediary address with many unrelated depositors.
  - A's whole Ethereum life (2026-05-19 to 06-18, 70 transactions) is 72% Polymarket withdrawals from 12 Polymarket wallets. The rest is one-use EOAs (USDT test + main pairs) and one service contract.
  - That looks like one operator's funnel, or one intermediary's client book, not retail flow.
  - The origin of the $12.76M USDT was not traced beyond one hop.

## 10. Uncertainties, data gaps, contradictions

- **Labels.** "Binance Deposit", "Binance: Hot Wallet 34", "Binance 14", "Binance 51", "Binance: Withdrawals 7", "Kraken: Hot Wallet 4" and "Binance: Deposit Funder 1" are Etherscan public tags (BscScan returned 403). That one Binance deposit address equals one account is standard exchange practice but cannot be checked on-chain: PLAUSIBLE.
- **BNB Chain coverage is partial** (narrow windows before each origin tx). B's sweep on BNB Chain was not found within 600 blocks.
- **Ethereum window.** Blocks 25.13M–25.99M (2026-05-19 15:00Z to about 09-14). A was also checked back to block 25.03M: there is nothing before its $100 test on 05-19. The hops' and B's later history is covered to 09-14.
- **Outside Polygon, only the Relay bridge path was followed.** Polymarket's bridge may also use other routes; the 13 market tapes cover only the candidates' markets.
- **CONTEXT.md contradiction (already noted in grimdrip_endlessfate.md):** publicnode serves only recent blocks for eth_getLogs and receipts. Historical scans used `polygon.gateway.tenderly.co`, `mainnet.gateway.tenderly.co`, `polygon.drpc.org`, `bsc-dataseed.bnbchain.org` (receipts) and `bsc-mainnet.gateway.tatum.io` (getLogs ≤100 blocks, 5 requests/min).
- Relay `/requests/v2` is deprecated (retires 2026-11-24) and throttles in stages; responses are cached.
- **This note supersedes** the ownership verdicts in `grimdrip_endlessfate.md` §6 and `mintblade.md` §9 ("common ownership UNSUPPORTED"). Those notes stopped at the Relay depository on Polygon. Following the Relay deliveries off Polygon is what changes the assessment.

## Files
- Scripts: `analyses/wallets/linkage_common.py`, `linkage_01_wallet_type.py`, `linkage_02_transfers.py` (`scan`, `hop2`, `wdr`), `linkage_02b_deposit_sources.py`, `linkage_03_bridges.py`, `linkage_04_profiles.py`, `linkage_04b_profile_baseline.py`, `linkage_05_comovement.py`, `linkage_06_origin_chains.py`, `linkage_07_sinks.py`, `linkage_08_extended_cluster.py`, `linkage_09_scenarios.py`, `linkage_10_fund_paths.py`, `linkage_11_order_signers.py`
- Data: `data/derived/linkage_wallet_controllers`, `_batch_signers`, `_wallet_events`, `_transfers_scan`, `_transfers_hop2`, `_transfers_wdr`, `_deposit_sources`, `_relay_requests`, `_relay_requests_leeeroy`, `_bridge_status`, `_profile_window`, `_profile_baseline`, `_wallet_market`, `_pairs`, `_origin_eth`, `_origin_bsc`, `_sink_inflows`, `_sink_backtrace`, `_extended_cluster`, `_fund_paths`, `_scenarios`, `_order_signers` (.parquet)
