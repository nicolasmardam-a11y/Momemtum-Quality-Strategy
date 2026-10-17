# Reference check: "The Favorite–Longshot Bias in Prediction Markets: Evidence from Polymarket"

As of 2026-10-17. Author of note: research agent (literature verification).
Labels: **VERIFIED** = I read it in a primary source myself; **PLAUSIBLE** = consistent with the evidence but not
directly checked; **UNSUPPORTED** = no evidence found.

## Verdict

- **The paper exists under this exact title. VERIFIED.** It is arXiv:2609.12878 [econ.GN] by Marcos Cardozo and
  José Ignacio Rivero-Wildemauwe (Universidad Católica del Uruguay), v1 submitted 2026-09-11 14:05:21 UTC.
  - The PDF title page uses an en dash ("Favorite–Longshot"), as in the supplied reference.
  - The arXiv metadata, the PDF metadata and the DataCite DOI record use a hyphen ("Favorite-Longshot").
  - Nothing else differs.
- The supplied reference gave only a title, so there is nothing else in it that could be wrong. Anyone citing the
  paper should know five things:
  1. It is a **single-version arXiv preprint** (v1 only; `/abs/2609.12878v2` returns 404). It has no journal or
     conference status, no SSRN copy that I could find, and no peer review.
  2. **The abstract's headline figure, "purchases below 10 cents lose 19.3 cents per dollar", is not statistically
     significant.** Its 95% CI, clustered by parent event, is [−46.99, +8.30]% (Table 6B), and the null-imposed
     Webb-bootstrap p-value is 0.184 (App. H).
  3. **The longshot result reverses sign under parent-event weighting**, from −6.30% to +4.09%. The paper's own
     conclusion is that the FLB's "magnitude depends on how contracts are grouped".
  4. All returns are **pre-fee, hold-to-resolution, unannualised**. They come from a dataset that ends 2026-03-29,
     the day before fees were extended to all markets.
  5. **It contains no trading strategy, no simulation and no executable-price test.**
- One summary is already wrong: a web-search summary paraphrased the paper as saying heavy longshot buyers
  "don't lose money". The paper says they lose −21.96%, about the same as other wallets' −20.33% (Table 10). Do not use
  that paraphrase.

## Metadata

| Field | Value | Status |
|---|---|---|
| Exact title | The Favorite–Longshot Bias in Prediction Markets: Evidence from Polymarket (arXiv metadata uses a hyphen) | VERIFIED (PDF p.1; arXiv API) |
| Authors | Marcos Cardozo (marcos.cardozo@ucu.edu.uy); José Ignacio Rivero-Wildemauwe (joseignacio.rivero@ucu.edu.uy); both Universidad Católica del Uruguay | VERIFIED (title page) |
| Author check | Rivero-Wildemauwe has other Crossref-indexed economics work (e.g. *Quarterly Review of Economics and Finance* 2021; SSRN 5767918, 5638093; a 2026 dissertation). Per the sibling note, M. Cardozo is credited in the HF dataset v1.3 changelog for finding the `frac_longshot` bug | VERIFIED (Crossref); PLAUSIBLE (changelog, via sibling note) |
| Identifier | arXiv:2609.12878; DOI 10.48550/arXiv.2609.12878 (DataCite, created 2026-09-14, state "findable") | VERIFIED |
| First posted | 2026-09-11 (v1). The title page is dated "September 2026" | VERIFIED |
| Latest version | v1 is the only version as of 2026-10-17 | VERIFIED |
| Status | arXiv preprint, econ.GN. No journal-ref and no comments field. Licence: arXiv non-exclusive distribution. JEL D81, G14, G41. 51 pages | VERIFIED |
| Primary URL | https://arxiv.org/abs/2609.12878 (PDF https://arxiv.org/pdf/2609.12878) | VERIFIED |
| Code/data repo | **None given in the paper.** It uses the public Hugging Face dataset `vgregoire/polymarket-users` v1.3 (2026-07-06, commit 91ddb961…, CC-BY 4.0) | VERIFIED (references) |
| Citations | Cited by arXiv:2610.13593 (Qiu & Qiu, below). arXiv:2609.28965 does not cite it. Semantic Scholar and OpenAlex were rate-limited | VERIFIED (grep of the PDFs) |
| How read | **Full text, all 51 pages**, main text and Appendices A–H, from the arXiv PDF | VERIFIED |

## What the paper does

**Question.**
- Does Polymarket show the favorite–longshot bias (FLB)?
- Does the measured bias depend on how related contracts are grouped?
- Do recurrent longshot or favorite buyers bear the losses or gains?
- Which explanations (misperception, risk-love, fees, collateral, execution) survive?

**Mechanisms considered (Sec. 7).**
- Probability misperception.
  - The sign pattern of the probability errors fits it: negative from 4¢ to 45¢, positive from 50¢ to 99¢.
  - But the errors are largest mid-range: −5.86 pp at 35¢ and +7.28 pp at 60¢.
  - In the tails they are tiny: |error| ≤ 0.53 pp below 10¢. The large longshot *returns* come mostly from dividing a
    tiny error by a ~1¢ price.
- Risk-love or skewness preference. It is not supported, because recurrent longshot buyers do not bear
  disproportionate losses.
- Execution, fees and collateral. Each is tested and none explains the longshot losses.
- Heterogeneous beliefs (Ali 1977; Gandhi & Serrano-Padial 2015) and informed sellers. Both are left open.

**Data (VERIFIED, Sec. 2).**
- Source: the Polymarket Users dataset v1.3 of Akey, Grégoire, Harvie & Martineau. The underlying source is the Goldsky
  subgraph of on-chain `OrderFilled` events; see `title_who-wins-who-loses.md`. The authors did not query the chain or
  the API themselves, except Gamma metadata for the shared-collateral (negRisk) flag.
- Period: 2022-11-11 to 2026-03-29.
- Full dataset: 588,287,492 trades, 2,480,104 wallets, 729,133 child markets in 316,429 parent events (614,883 and
  255,427 of them traded).
- Filters (Table 1):
  - self-trades removed;
  - markets with more than two outcomes removed (39 markets);
  - **buyers with counterparty HHI ≥ 0.5 removed** as possible wash traders. This removes 17.7% of wallets but only 3.9%
    of dollars.
- Analysis sample: 586.1M purchases, $23.67B. Return sample: resolved markets only, 560.9M purchases, $22.49B, 591,187
  child markets.
- Unit: each trade counted once, as a *purchase* by the buyer.
- Volume reconciliation (Table 27): $134.28B both-sided, $67.14B one-sided, $24.62B in buyer purchases after the
  restrictions.

**Coverage by category (Table 2; share of the $23.67B).**

| Category | Share of amount paid |
|---|---|
| Sports | 36.8% |
| Politics | 28.5% |
| Crypto | 25.2% |
| Culture | 4.3% |
| Finance | 3.4% |
| Tech | 1.1% |
| Weather | 0.7% |

- Crypto is 67.2% of purchases by count.
- Child markets per parent event (Table 3): mean 2.41, max 144. Sports mean 5.00, Weather 7.75, Crypto 1.20.

**Tails and return measure (Secs. 2.3–2.4).**
- Longshot: p < 0.10. Favorite: p ≥ 0.90. Sensitivity checks at 5/95, 15/85 and 20/80.
- Return per purchase: r = (y − p)/p, held to resolution, **before fees and before liquidity rewards**, not annualised.
- Probability error: E = Σq(y−p)/Σq.
- Three aggregations:
  - equal weight per child market;
  - pooled (dollar-weighted);
  - equal weight per parent event (secondary).
- Tail composition (Table 4): longshots are 18.0% of purchases but only 1.2% of dollars ($273.6M, average price
  **1.17¢**). Favorites are 10.5% of purchases and 43.0% of dollars ($9.66B).

**Evidence type.**
- **Descriptive, in-sample, ex post.**
- The wallet classifications in Sec. 6 are *prospective*: they use only the prior six months and measure the next month.
  They describe who trades, not a trading rule.
- There is no out-of-sample period, no simulated trading and no actual trading.

## Key quantitative findings (all VERIFIED in the PDF)

**Platform-wide tails (Table 6; CIs clustered by parent event).**

| Aggregation | Longshot return | Favorite return |
|---|---|---|
| Equal child market | **−6.30%** [−8.38, −4.22] | **+0.277%** [0.242, 0.312] |
| Pooled | **−19.35%** [−46.99, +8.30], *not significant* | **+0.83%** [0.60, 1.07] |
| Equal parent event | **+4.09%** [1.29, 6.90] | **+0.392%** [0.345, 0.440] |

- Probability errors are small:
  - longshots: +0.24 pp (equal child) and −0.23 pp (pooled);
  - favorites: +0.27 pp and +0.82 pp.

**Why the sign changes (Table 7; App. C.2 identities).**
- Equal child → equal parent: **+10.33 pp**. Events with many child markets have lower longshot returns.
- Equal parent → pooled: **−23.44 pp**. Longshot dollars concentrate in low-return events.
- Within-event weighting: +0.06 pp, which is negligible.
- Pooled longshot return after dropping the largest 1 / 5 / 10 parent events: −15.8% / −14.5% / −10.6% (App. H).
- **The pooled loss is driven by a handful of large events.**

**By category (Table 8).**

| Category | Longshot, equal child | Longshot, pooled | Favorite, equal child | Favorite, pooled |
|---|---|---|---|---|
| Crypto | −14.84% | −12.63% | +0.643% | +0.537% |
| Politics | −16.34% | −46.15% | +1.044% | +1.419% |
| Sports | +2.43% (n.s.) | +18.11% (n.s.) | **−0.230%** [−0.285, −0.174] | +0.137% (n.s.) |
| Finance | −2.62% (n.s.) | −72.40% | +0.085% (n.s.) | +1.826% |
| Weather | −25.15% | **+24.74%** [2.49, 47.00] | +0.502% | +0.031% (n.s.) |
| Culture | −26.49% | −18.78% (n.s.) | +0.735% | +0.829% |
| Tech | −20.68% | −18.91% (n.s.) | +0.816% | +0.846% |

- Only **Crypto and Politics** show the two-sided pattern in all four estimates with every CI excluding zero.
- **Sports, the largest category by market count, has no FLB. Its favorites lose slightly under equal weighting.**

**Robustness (App. A–B).**
- Cutoffs (Table 12). Pooled longshot return: −17.94% (5/95), −19.35% (10/90), −15.24% (15/85), −8.86% (20/80). The
  equal-parent-event longshot return turns negative only at 15/85.
- Endpoints excluded (Table 13; 0.02 < p < 0.10 and 0.90 ≤ p < 0.99):

  | Tail | Equal child | Pooled |
  |---|---|---|
  | Longshots | −4.12% [−5.40, −2.84] | **−23.75% [−34.69, −12.81]**, significant |
  | Favorites | +0.187% [0.109, 0.265] | **+1.729% [1.250, 2.209]** |

  Purchases at or above 99¢ dilute the full favorite tail.
- Scheduled closing dates (Table 14). Longshots in markets scheduled to close ≤1 day after purchase: pooled −10.86%,
  equal child −13.14%, equal parent −0.90%. The equal-weight signs flip across these subsamples. Time variation by
  quarter is in Fig. 6, and the 2026-Q1 estimates are provisional because coverage is incomplete.

**Trading conditions (Table 9; Table 16 has the CIs).**
- *Buyer action* ("posted offer" = buyer was the maker; "accepted" = buyer was the taker):

  | Buyer role | Longshot, equal child | Longshot, pooled | Favorite, equal child | Favorite, pooled |
  |---|---|---|---|---|
  | Maker | −3.50% | −17.56% [−29.44, −5.69] | **+0.641%** [0.607, 0.675] | +0.816% |
  | Taker | **−31.17%** [−32.94, −29.40] | −22.17% [−86.22, 41.88] | **−0.460%** [−0.515, −0.405] | +0.877% |

  Under equal weighting, **takers lose at both tails before fees.**
- *Previous trading*:
  - Longshots are negative in all four quartiles; the most-traded quartile has −28.72% pooled.
  - No CIs are available.
  - The equal-child cells are blank ("not included in the existing output"), which suggests an unfinished draft.
- *Fee flag* (market-level metadata, not fees actually paid):
  - no-fee markets: longshots −5.20% (equal child) and −20.78% (pooled);
  - fee-flag markets: −13.03% and +10.03% (n.s.).
- *Shared collateral* (negRisk):
  - longshot losses are not smaller where collateral is shared: −7.80% and −25.76%, against −5.94% and −9.79% without;
  - favorite gains are larger: +0.644% and +1.286%.
  - The comparison is cross-sectional, not causal.
- *Short-horizon markouts after maker longshot buys* (Fig. 3, Tables 17–18):
  - Valued at later *last-trade* prices, not executable bids: +3.92% / +16.91% / +7.56% at 5 min / 1 h / 1 day.
  - Common sample: +4.85% / +6.96% / +6.62%, then **−36.27% at resolution**.
  - These are trade-price valuations, so they are not sellable profits (the authors say so).
- *Conditional regressions* (Table 20; event-clustered SEs). Longshot return falls with log(1 + child-market count)
  (−11.18 pp) and with log(1 + previous purchase dollars) (−8.73 pp).

**Wallets (Sec. 6; Tables 10–11, 21–26).**
- The top decile of past longshot demand, ranked on the residual after controls, supplies 26.6% of next-month longshot
  dollars.
- Its terminal return is −21.96%, against −20.33% for other wallets. It has 22.6% of gross longshot losses.
- The top decile of past favorite demand supplies 15.1% of favorite dollars and earns +0.25%, against +0.88% for others.
  It gets 4.8% of net favorite gains.
- Persistence (Fig. 4): top-decile retention after one month is 68.5% (longshot group) and 64.5% (favorite group).
  After six months, with non-overlapping histories, it is 30.4% and 15.8%.
- All five experience quintiles lose on longshots: −38.34%, −44.13%, −23.68%, −22.29%, −21.55%.
- Longshot purchases with no later recorded sale by the buyer: $99.7M cost, −$53.1M (−53.30%). Purchases whose buyer
  later sold the same token: +0.12%.
- Data quality (App. H): an independent reconstruction for 9,781 wallets has Spearman 0.9926 with the released PnL.

## Costs and execution

- **Fees:** excluded from returns (Sec. 2.3). Only a market-level fee flag is used, with no rebates. The sample predates
  the all-market fee regime. **VERIFIED.**
- **Spreads:** not modelled explicitly. Returns use actual fill prices, so takers' returns already include the spread
  they paid, and maker fills include adverse selection. **VERIFIED** (construction).
- **Depth, partial fills and latency:** not addressed. The paper says nothing on how much could be bought at a price,
  and maker fills are observed only conditional on being filled. **VERIFIED** (absence).
- **Capital lock-up:** returns are not annualised (fn. 6). The only duration statistic is the median
  purchase-to-resolution time of the March 2026 longshot group: 110.4 days, against 19.3 days for other wallets
  (Table 22). Section D.3 says collateral actually committed cannot be reconstructed. **VERIFIED.**
- **My cost arithmetic (PLAUSIBLE, from the CONTEXT.md fee formula; not in the paper).** A taker buying a favorite at
  price p pays fee/notional = rate × (1 − p).

  | Price | Crypto | Sports and Econ/Culture/Weather | Politics, Finance, Tech |
  |---|---|---|---|
  | 0.90 | 0.70% | 0.50% | 0.40% |
  | 0.95 | 0.35% | 0.25% | 0.20% |
  | 0.99 | 0.07% | 0.05% | 0.04% |

  - The equal-child favorite edge (+0.28%, or +0.19% excluding endpoints) is **smaller than today's taker fee at
    0.90–0.95 in every fee-bearing category**.
  - Taker favorite buys were already −0.46% before fees.
  - Only the pooled figures (+0.83% to +1.73%) and the maker-side favorite figures (+0.64% equal child) leave room after
    fees, and the pooled figures depend on a few large events.

## Correlated observations

- **What the paper does:**
  - CIs in Tables 6A–B, 8, 13, 16, 18, 19 and 26 are **clustered by parent event**.
  - The equal-parent-event estimate uses standard errors across events.
  - Pooled returns get a Webb wild-cluster bootstrap.
  - Regressions use event-clustered SEs.
  - Making the aggregation unit explicit is the paper's main contribution. **VERIFIED.**
- **What it does not do (PLAUSIBLE, my assessment):**
  - **Calendar time.** There is no clustering by calendar time or by common underlying. Crypto has 172,313 parent events
    with a mean of 1.2 markets each. Many are short-horizon up/down markets on the same BTC/ETH path, so their outcomes
    move together across events. Clustering by event treats them as independent and probably understates the error
    bands for Crypto.
  - **Political events.** Separate parent events on one election (state, national, popular vote) are correlated the
    same way.
  - **Overlapping windows.** The wallet persistence tests reuse overlapping six-month windows (the authors flag this),
    and they treat wallet-months as observations.

## Was the effect identifiable ex ante at executable prices?

**My assessment: not established.**

- The tail definition (price < 10¢ or ≥ 90¢) is known ex ante, and returns are computed at actual fill prices. To that
  extent the classification is not look-ahead.
- **Aggregation dependence.** The sign of the longshot effect depends on aggregation. A diversified rule ("fade every
  longshot") earns roughly the equal-child or equal-parent figure: −6.3% versus +4.1% for the longshot buyer. The large
  pooled figure comes from a few big events that cannot be identified in advance.
- **Fees.** The robust side, favorites, earns +0.2% to +0.8% per dollar before fees and before time value. That is the
  same size as current taker fees, and taker favorite buys were negative even before fees.
- **Maker fills.** Maker favorite buys look better, but the data show only *filled* maker orders. There is no queue,
  depth or fill-probability model, and no execution test.
- **Regime.** The sample ends 2026-03-29, before all-market fees, the taker-rebate programme (2026-05-28) and the V2/pUSD
  migration (CONTEXT.md). There is no out-of-sample period.
- **Category instability.** Sports (36.8% of dollars) shows no FLB, and Weather's sign depends on weighting.
- **Tail risk.** At ≥ 0.90 a single loss wipes out 9 to 99 wins. With event-correlated outcomes, the per-dollar
  favorite premium is small next to that variance. The paper gives no Sharpe ratio or drawdown.

## What to replicate before risking money

1. Load HF `vgregoire/polymarket-users` **v1.3**. Reproduce Tables 1, 4, 6 and 8 with the same filters: two-outcome
   markets, buyer counterparty HHI < 0.5, resolved by 2026-03-29. Confirm the aggregation sign flip and the 1/5/10
   largest-event sensitivity.
2. Check how complementary-mint matches (YES buy against NO buy) are represented as "purchases". This decides whether
   the favorite and longshot tails double-count one economic trade (PLAUSIBLE concern; the paper does not discuss it).
3. Split favorites by maker and taker within category. Subtract the **current per-market `feeSchedule`** taker fee and
   add maker rebates, liquidity rewards and the taker-rebate tier. Report results per day of capital locked
   (purchase-to-resolution), not per trade.
4. Re-run inference clustered by **calendar day** and by underlying (crypto asset, election), not only by parent event.
   Report the distribution of event-level PnL, including worst-case losses at ≥ 0.90.
5. Run an **out-of-sample** test on post-2026-03-30 trades:
   - the Data API `/v2/trades?condition=…&taker_only=false`, or Polygon RPC `eth_getLogs`;
   - not the Goldsky subgraph (deprecated) or CryptoHouse (stale after 2026-01-05).
6. Run an **executable-price** test. Record live `/book` snapshots for candidate markets (0.90–0.98 asks in
   Crypto/Politics). Measure available depth, spread and fill rates for resting bids. There is no historical book
   endpoint, so this has to start prospectively.
7. Exclude Sports, or test it separately. Treat Weather separately, given the Qiu & Qiu horizon result below.
8. Check resolution and dispute risk (UMA disputes, `umaResolutionStatus`) for high-price markets. A wrongly resolved
   0.95 favorite is the tail event that a +0.3% edge cannot absorb.

## Related papers (not the supplied reference; reported so they are not confused with it)

1. **Qiu, Shouchen & Qiu, Huaijun (2026), "Time-Varying Favorite-Longshot Bias in Polymarket Weather Markets",
   arXiv:2610.13593 [cs.DB], v1 2026-10-09.** Full text read (5 pp.). VERIFIED.
   - **Authors:** Shouchen Qiu is a high-school student (Northeast Yucai School). Huaijun Qiu is at Shenyang Aerospace
     University.
   - **Venue:** the arXiv comment says "Accepted at the IEEE ICDM 2026 Teen Research Symposium (Teen Track)". I have not
     checked this with IEEE (PLAUSIBLE).
   - **Data:**
     - Polymarket API taker trades on daily max-temperature markets in 10 cities, 2025-12-05 to 2026-07-31.
     - 2,189 events, 21,697 bucket contracts, 8,544,732 taker trades.
     - Chronological split: train to 2026-05-31, validate on June, test on July.
     - The price at horizon h is the mean taker price in a ±0.5 h window, which is not executable.
   - **Findings:**
     - Longshot (0 < p ≤ 0.10) overpricing appears mostly 30–48 h before the temperature peak, about −0.009.
     - Favorite (0.75 ≤ p ≤ 0.95) overpricing is about −0.10 at 6 h. It is strongest 1–12 h out and about an order of
       magnitude larger (Fig. 2). It reaches −11.2 pp in the 70–90% bin (Fig. 3).
     - B-spline recalibration gives no significant gain (Table II).
   - **Buy-NO test (July, $10 notional per trade, fee 0.05·r(1−r) per share, no depth, spread or slippage; Table III):**
     - Favorite window: 184 trades, post-fee ROI +50.71%, CI [1.76, 102.98]¢ per $.
     - Longshot window: 11,924 trades, post-fee ROI −0.23%, CI includes 0.
   - **Code:** the paper links github.com/ShouchenQiu/PolyWeatherData, but **that GitHub user shows 0 public
     repositories as of 2026-10-17** (VERIFIED via WebFetch; the repo URL returns 404).
   - **It points the other way from Cardozo & Rivero-Wildemauwe for Weather favorites.** C&RW find Weather favorites at
     ≥ 0.90 earn +0.50% (equal child), meaning they are *under*priced. The two papers use different price bands,
     horizons and periods.
   - Evidence type: in-sample calibration plus a one-month out-of-sample diagnostic on mean taker prices. Not
     executable.
2. **Bürgi, Constantin; Deng, Wanying; Whelan, Karl, "Makers and Takers: The Economics of the Kalshi Prediction
   Market", CESifo WP 12122.** Original version Sept 2025, this version Jan 2026 (https://www.ifo.de/DocDL/cesifo1_wp12122.pdf).
   I read the abstract, Sec. 1, Sec. 6 and Sec. 7, not the full text. VERIFIED for those parts.
   - **Kalshi**, not Polymarket. 46,282 contracts, 12,403 events, daily prices up to 10 days before close.
   - Contracts below 10¢ lose over 60%. Contracts above 50¢ earn a small positive return. The average return is −20%
     before fees and −22% after.
   - The FLB is stronger for takers. Makers on contracts priced 50¢ and above earn 1.9% after commission, with a 33% SD.
   - Cited by C&RW as the Kalshi FLB benchmark. It is the most likely source if someone confused "FLB in prediction
     markets" evidence across platforms.
3. **Qin, Boka & Yang, Rui (2026), "Polymarket-v1 Database", arXiv:2606.04217v2** (SSRN DOI 10.2139/ssrn.6870538). I
   read only the stylised-facts section. VERIFIED.
   - Table 3: mean (payout − price) per trade by price decile ranges from −0.0023 (0–0.10, average price 0.052,
     34.9M trades) to +0.0098 (0.80–0.90) and +0.0056 (0.90–1.00, 27.2M trades).
   - This is an independent on-chain archive (2022-11-21 to 2026-04-28) with the same sign pattern. It is trade-weighted
     and not clustered.
4. **Reichenbach, Felix & Walther, Martin, "Exploring Decentralized Prediction Markets: Accuracy, Skill, and Bias on
   Polymarket", SSRN 5910522** (DOI 10.2139/ssrn.5910522, Crossref created 2025-12-13, redeposited 2026-05-24).
   - Existence VERIFIED (Crossref).
   - Full text and abstract **not accessible** (SSRN 403; no abstract in Crossref).
   - Cited by C&RW for calibration over the market lifecycle. I have checked none of its content.
5. **Le, Nam Anh (2026), "Decomposing Crowd Wisdom: Domain-Specific Calibration Dynamics in Prediction Markets",
   arXiv:2602.19520** (v1 2026-02-23, updated 2026-08-04). Abstract only.
   - 353M trades on Kalshi and Polymarket.
   - Persistent underconfidence in politics, meaning prices compressed toward 50%, which is FLB-like. It replicates on
     Polymarket.
6. Other FLB papers found in the Crossref search that are **not about Polymarket** (abstracts only):
   - Zubchenko & Chernov, "Favourite-longshot Bias in Forecasting Platforms", SSRN 7589461, 2026-10-10 (Manifold and
     Metaculus).
   - Krause, SSRN 7087538 and SSRN 7093759 (Kalshi CPI markets), and SSRN 7110758 (unemployment markets).
   - Cao, "Retail-Adjusted Expected Value in Prediction Markets", SSRN 7049119 (calibration slopes; Kalshi cross-check).

## Discrepancies with CONTEXT.md or within the sources

- During the sample the collateral was USDC (paper fn. 2); CONTEXT.md says it is now pUSD. These are consistent because
  the sample ends 2026-03-29.
- The paper's "fee flag" comes from market metadata during a mostly fee-free period. It cannot be mapped to today's
  `feeSchedule`.
- Internal drafting issues suggest an early version:
  - Table 9 has blank cells "not included in the existing output", and App. D mentions "outstanding checks".
  - There are typos ("hey appear").
  - Sec. 5.2 first says there are no early price declines, then that the estimates "do not rule out purchases at
    outdated prices".
- The headline −19.3¢ appears in the abstract without its insignificance being mentioned; Sec. 1 and Sec. 3.1 do mention
  it.

## Search log

1. Read CONTEXT.md and the sibling note `title_who-wins-who-loses.md`. That note named arXiv 2609.12878 as a lead; I
   treated it as unverified.
2. arXiv API `id_list=2609.12878` returned the exact title, authors, econ.GN and published 2026-09-11. The abs page shows
   v1 only, the DataCite DOI and no comments. `/abs/2609.12878v2` returned 404.
3. Downloaded the arXiv PDF (51 pp.) and read it in full through `pdftotext`. No code repository is listed.
4. arXiv searches: `ti:"favorite-longshot"`, `ti:"favourite-longshot"`, `ti:longshot`,
   `abs:polymarket AND abs:longshot`, `all:"favorite longshot" AND all:"prediction market"`, `ti:polymarket` (latest
   60). Only 2609.12878 and 2610.13593 have FLB-on-Polymarket titles.
5. WebSearch:
   - the exact title in quotes: arXiv PDF plus glossary and blog pages;
   - "favorite-longshot bias Polymarket paper SSRN": no SSRN version;
   - author names: no other version and no critiques;
   - "2609.12878" and "Cardozo and Rivero-Wildemauwe": nothing;
   - the topic plus the affiliation: only arXiv and Polymarket-v1.
6. OpenAlex: HTTP 429/budget exhausted for this IP. I did not create an API key, because that would have required
   sending the user's email address.
7. Crossref:
   - `query.bibliographic` for FLB plus Polymarket, and `query.title` for longshot plus Polymarket, found related SSRN
     items (Reichenbach & Walther; Krause ×3; Cao; Zubchenko & Chernov; Skovgaard et al. on Trump-contract bias).
   - Author query (Cardozo / Rivero-Wildemauwe): no SSRN or journal version of this paper; other papers by
     Rivero-Wildemauwe confirm a real economist.
8. DataCite: the 10.48550/arXiv.2609.12878 and 10.48550/arXiv.2610.13593 records were checked.
9. Semantic Scholar: 429 (rate-limited), so there is no citation count from it.
10. arXiv:2610.13593 (Qiu & Qiu): metadata and full PDF read. Its GitHub link: `gh` and curl were blocked by the sandbox
    (403). WebFetch returned 404 for the repo, and the user page lists 0 public repositories.
11. Bürgi, Deng & Whelan: the CESifo PDF was downloaded from ifo.de; I read the abstract, introduction, discussion and
    conclusion.
12. Polymarket-v1 (2606.04217): grepped for longshot and read Sec. 3 and Table 3. arXiv:2609.28965 (Sultan & Morstatter)
    was grepped and does not cite C&RW.
13. Reichenbach & Walther: SSRN through WebFetch returned 403. Two WebSearches found no accessible full text, and the
    investmentofficer.com news link was a login page.
14. Dead ends: SSRN (403), OpenAlex (budget), Semantic Scholar (429), GitHub through the proxy (403), and the Qiu repo
    (404 / not public).
