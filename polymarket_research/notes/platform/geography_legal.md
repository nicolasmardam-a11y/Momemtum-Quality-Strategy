# Geographic restrictions, venue access and regulatory status (as of 2026-10-17)

**These are facts and sources, not legal advice.** Each claim has a label:
**VERIFIED** means I read the primary source or ran the live call myself on 2026-10-17.
**PLAUSIBLE** means secondary reporting or a search snippet of a primary page I could not fetch.
**UNSUPPORTED** means a claim I could not source.
News articles are secondary sources. Raw snapshots of the primary documents are in
`data/raw/legal_2026-10-17/`. The scripts are in `analyses/geography/`.

*Second pass, 2026-10-17 (later the same day).* I added the Polymarket help-center restrictions
article (§1.2a), the **Kalshi Developer Agreement**, which corrects an earlier statement in §4.2,
the South Korea block (2026-08-18), the joint declaration by nine European regulators (2026-06-18),
Kalshi's reported India exclusion (2026-06-17), and the Massachusetts suit filed by Polymarket US.
I re-fetched the docs geoblock page and the perps restrictions page; both are byte-identical to the
earlier snapshots.

---

## 0. Bottom line

1. **Polymarket international (polymarket.com).** Trading is barred for people who "reside in, are located in, are incorporated in…" the US, the UK, France, Germany, Italy, Australia, Singapore, and about 40 other jurisdictions. The ToS defines Restricted Jurisdictions to cover anyone "residing in, a **citizen of**, organized in or located in" a listed jurisdiction. VPNs are expressly prohibited. Violators can have their wallets put in close-only mode. (VERIFIED, ToS effective 2026-08-11.)
2. **The geoblock endpoint checks your IP address. It does not decide whether you are eligible.** From this sandbox, `GET https://polymarket.com/api/geoblock` returned `{"blocked":true,"country":"US","region":"OH"}` (VERIFIED). All research in this project is view-only. Nobody here can or may trade on polymarket.com.
3. **Gamma's `restricted` field is not useful as a per-market filter.** The docs say it means "Market is geo-restricted for some jurisdictions". It is `true` on 40,000/40,000 open markets sampled and on essentially every market created since January 2022 (VERIFIED).
4. **Polymarket US is a separate exchange with a separate order book.** It is a CFTC DCM: QCX LLC d/b/a Polymarket US, designated 2025-07-09. Clearing is by QC Clearing LLC d/b/a Polymarket Clearing, a DCO. It uses USD, not pUSD, has its own API and its own fee schedule (taker Θ = 0.0695). It requires KYC, including an SSN. Its public data has **no trade tape** (VERIFIED).
5. **Regulators keep acting.** At least 16 non-US jurisdictions acted against Polymarket in 2025–2026, the latest being **South Korea (KCSC ISP block, 2026-08-18)**. On 2026-06-18 nine European gambling regulators issued a joint statement promising coordinated action against non-compliant prediction-market platforms. Several of the jurisdictions that acted are **not** on Polymarket's own geoblock list: Portugal, Spain, Hungary, Romania, Ukraine, Argentina, Indonesia and Switzerland. **Polymarket's geoblock list is therefore not a complete map of where trading is legal locally.** (PLAUSIBLE, mostly secondary sources.)
6. **Polymarket's own pages disagree with each other.** The help-center article (last updated 2026-08-14) calls 40 listed countries "completely restricted" (its header says 39). It says permissions "are based on physical location rather than residency". The ToS bars people who *reside in*, are *located in* or are *citizens of* a restricted jurisdiction. **The strictest reading (ToS) is the one that binds** (VERIFIED texts; the reading is mine).
7. **Kalshi** is a CFTC DCM. It also restricts a list of countries, including the UK, France, Poland, Singapore, Taiwan, Thailand, Australia, all of Canada and Russia (VERIFIED, member agreement on S3, last-modified 2025-10-10). A 2026-06-17 revision reportedly added **India** (PLAUSIBLE, secondary). Several US states have fought it in court. Two Kalshi documents limit data use:
   - The **Developer Agreement** says that accessing the API is acceptance. It limits API use "to facilitating a members own trading on the Exchange; all other usages are disallowed". It prohibits "collecting, caching, aggregating, or storing data… except for purposes of facilitating your own trading", and any "benchmarking or competitive purposes" (VERIFIED, v1.1 on S3, last-modified 2023-11-09; docs.kalshi.com links the live version, which returned 429 here).
   - The **Data Terms** forbid scraping, systematic retrieval and any AI/ML use of "Kalshi Data" without written consent (VERIFIED, S3 PDF last-modified 2024-09-11).

   **Using Kalshi data for research, as a non-member, is outside what these terms permit** (PLAUSIBLE reading; not legal advice).
8. **Cross-venue strategies:**
   - Polymarket-international ↔ Kalshi needs one non-US person who is eligible on both venues and allowed by local law. That is a small group: the large markets of the UK, France, Poland, Singapore, Taiwan, Thailand, Australia and Canada are excluded by one venue or the other, and Spain and Brazil blocked both.
   - Polymarket-international ↔ Polymarket-US is effectively impossible for any one person (PLAUSIBLE).
   - Kalshi ↔ Polymarket US works only for US persons, outside the states where either venue is barred.
   - A one-venue variant that uses **Kalshi prices as a signal for trading on Polymarket** is not covered by Kalshi's Developer Agreement, which permits API use only for a member's own Kalshi trading (PLAUSIBLE reading).

---

## 1. Polymarket international

### 1.1 Geoblock endpoint (documented)

| Item | Fact | Label | Source |
|---|---|---|---|
| Endpoint | `GET https://polymarket.com/api/geoblock`, served from `polymarket.com`, not from the API hosts | VERIFIED | https://docs.polymarket.com/api-reference/geoblock.md |
| Response | `{blocked: bool, ip, country (ISO 3166-1 alpha-2), region}` | VERIFIED | same |
| What it checks | Geographic eligibility "of the requesting IP address". Orders "submitted from blocked regions will be rejected" | VERIFIED | same |
| Live call from this sandbox | 2026-10-17T15:32:26Z: `blocked: true, country: US, region: OH` (IP redacted in the snapshot) | VERIFIED | live; `data/raw/legal_2026-10-17/pm_geoblock_live_sandbox.json` |
| Frontend behaviour for a US IP | Banner: "Trading is blocked in the United States on polymarket.com. Switch to polymarket.us… Continue in view only mode" | VERIFIED | https://polymarket.com/tos (HTML fetched 2026-10-17) |
| Server location | Primary servers are in `eu-west-2`. The closest non-georestricted region is `eu-west-1`. Direct co-location in eu-west-2 needs a KYC/KYB form. It is offered to market makers and individuals trading their own account, not to Builder apps | VERIFIED | geoblock docs page |

### 1.2 Restricted jurisdictions, as documented on 2026-10-17

Source: https://docs.polymarket.com/api-reference/geoblock.md (VERIFIED; snapshot `pm_docs_geoblock.md`).
**Block completely** means no new orders and no closing of existing positions.
**Close-only** means existing positions can be closed but no new ones opened.

| Group | Applies to | Jurisdictions (ISO codes) |
|---|---|---|
| OFAC-sanctioned, **block completely** | Frontend and API | Iran IR, Syria SY, Cuba CU, North Korea KP, Ukraine–Crimea UA-43, Ukraine–Donetsk UA-14, Ukraine–Luhansk UA-09 |
| Regulatory, **close-only** | Frontend and API (37 rows) | Australia AU, Belarus BY, Belgium BE, Burundi BI, Brazil BR, Canada–British Columbia CA-BC, Canada–Ontario CA-ON, Canada–Alberta CA-AB, Canada–Quebec CA-QC, Central African Republic CF, DR Congo CD, Ethiopia ET, France FR, Germany DE, Iraq IQ, Italy IT, Lebanon LB, Libya LY, Myanmar MM, New Zealand NZ, Nicaragua NI, North Korea KP (also listed above), Poland PL, Russia RU, Singapore SG, Somalia SO, Slovakia SK, South Sudan SS, Sudan SD, Taiwan TW, Thailand TH, United Kingdom GB, **United States US**, US Minor Outlying Islands UM, Venezuela VE, Yemen YE, Zimbabwe ZW |
| Regulatory, **close-only on frontend only** ("the API itself is not restricted") | Frontend | Ireland IE, Japan JP, Malta MT (sports only), Netherlands NL, South Korea KR |

**Perps have a different, shorter list.** Perps order placement is not permitted from the United States, **all of Canada**, Cuba, Iran, North Korea, Syria, Crimea, Donetsk and Luhansk. The page also says "Read-only market data is not subject to these restrictions." (VERIFIED, https://docs.polymarket.com/api-reference/perps/geographic-restrictions.md and https://docs.polymarket.com/perps/faq.md.)

### 1.2a Help-center article "Geographic Restrictions" (last updated 2026-08-14)

Source: https://help.polymarket.com/en/articles/13364163-geographic-restrictions (VERIFIED, fetched 2026-10-17; `lastUpdatedDate` 2026-08-14T…; text snapshot `pm_help_geographic_restrictions_upd_2026-08-14.txt`).

| Item | What the article says | Compared with the docs page |
|---|---|---|
| Blocked countries | "The following 39 countries are completely restricted": AU, BE, BY, BR, BI, CF, CD, CU, DE, ET, FR, GB, IE, IR, IQ, IT, JP, KP, LB, LY, MM, MT, NI, NL, NZ, PL, RU, SG, SK, SO, SS, SD, SY, TW, TH, UM, US, VE, YE, ZW. That is **40 codes**, not 39 | The same set as the docs except **South Korea (KR)**, which is missing. KR is on the docs page (frontend close-only). The KCSC block came on 2026-08-18, four days after the article was last updated, so the docs were probably updated later (PLAUSIBLE timing) |
| Blocked regions | Canada: AB, BC, ON, QC. Ukraine: Crimea (43), Donetsk (14), Luhansk (09) | Same |
| Close-only | "Countries with close-only status include" SG, PL, TH, TW | The docs class about 37 jurisdictions as close-only, and IE/JP/MT/NL/KR as close-only on the frontend only. The help center calls IE, JP, MT (without "sports only") and NL "completely restricted" |
| Country examples | Ontario: "Users can access market data globally but cannot deposit or trade, including via the iOS app". Italy: "can view markets and data but cannot trade". Germany: "Trading is prohibited. Existing positions must be held until market resolution" | Germany "hold until resolution" is stricter than the docs' close-only |
| **Travel** | "Permissions are based on physical location rather than residency; for instance, users traveling to non-restricted regions, such as Bulgaria, can continue to trade" | **Conflicts with the ToS.** The ToS bars anyone who "reside[s] in", is "a citizen of" or is "located in" a restricted jurisdiction |
| VPN | Prohibited; cites "Terms of Service (Section 2.1.4)" | Consistent with the ToS |

Two related help-center articles (VERIFIED):
- "Website vs App" (updated 2026-06-25, https://help.polymarket.com/en/articles/15458828-website-vs-app-what-s-the-difference):
  - "Polymarket.com is not accessible for US residents. US users cannot deposit funds or place trades on the website."
  - The Polymarket US app is "Entirely separate from Polymarket.com - accounts are not connected", with separate support (support@polymarket.us).
  - Android is "Coming Soon". polymarket.us now links to Google Play, so this article is probably stale on that point.
- "How to Sign Up" (updated 2026-01-12, https://help.polymarket.com/en/articles/13369877-how-to-sign-up):
  - Sign-up for polymarket.com is by Google, by email with a 6-digit code, or by crypto wallet.
  - **No identity-verification step is described.** On the international platform, the IP geoblock is therefore the only technical gate. France's ANJ reportedly cited the "absence de vérification d'identité" (PLAUSIBLE, secondary: https://kulturegeek.fr/news-355685/france-bloque-lacces-polymarket-important-site-paris).

The predictions changelog has no entry about geography changes (VERIFIED, grep of https://docs.polymarket.com/changelog/predictions.md). The old URLs `/polymarket-learn/FAQ/geoblocking` and `/developers/CLOB/geoblock` now redirect to the current page. Third-party sites that quote "33 blocked countries" are probably quoting an older version (PLAUSIBLE; the Wayback Machine was unreachable from this sandbox).

### 1.3 Terms of Use (polymarket.com, "Effective as of August 11, 2026")

Operator: **Adventure One QSS, Inc.** Governing law: Panama. The Platform software was developed by Blockratize Inc.
Source: https://polymarket.com/tos, which embeds https://docs.google.com/document/d/1N4aYlRcqaWCeKMID7vUSWJ1UPMvw_v6SP4cOFN8ZxR4/preview (exported text: `pm_intl_terms_of_use_eff_2026-08-11.txt`). All VERIFIED.

| Clause | What it says (paraphrase; quotes are short) |
|---|---|
| Restricted Persons | Trading "is not permitted by persons or entities who reside in, are located in, are incorporated in, have a registered office in, or have their principal place of business in": the USA, Alberta, Australia, Belgium, British Columbia, France, Germany, **Hungary**, Ireland, Italy, Ontario, Poland, Quebec, Russia, Singapore, Slovakia, **Slovenia**, Taiwan, Thailand, the Netherlands, New Zealand, the UK, "or any other restricted territory". The ban also covers anyone acting on behalf of, or controlled by, a Restricted Person. "THERE ARE NO EXCEPTIONS" |
| VPN | Using a VPN "or any similar tool" to circumvent the restrictions "is strictly prohibited". Violators "may have their wallets placed in close-only mode" |
| Restricted Jurisdictions (§4.1) | No access, use or trading of Contracts if "residing in, **a citizen of**, organized in or located in" any jurisdiction on the docs geoblock list (incorporated by reference, "which we may update from time to time without notice") or any comprehensively US-sanctioned territory |
| Content vs Technology Features | People in a Restricted Jurisdiction may use only the **Content Features** (news and information). They may not use the Technology Features or the Platform |
| Sanctions | Representations covering OFAC SDN and EU/UK/UN sanctions |
| Scraping | Prohibits "data mining tools, robots, crawlers, or similar data gathering and extraction tools to scrape or otherwise remove data from the Site, any other Interface, or Features" |
| **Capital Market Client data clause** | Prohibits accessing or using "any data… directly or through an API, or any other means, including on-chain, whether in raw, derived, aggregated, or anonymized form" by a professional capital-markets entity (broker-dealers, FCMs, RIAs, hedge funds, investment managers, prop firms, CPOs, **fintech companies**, banks, exchanges, "or an affiliate of any such entity") or by a market-data distributor, unless agreed in writing. Reselling the Data to such parties is also prohibited |
| Limits | Transaction and rate limits may change without notice |

### 1.4 Discrepancies inside Polymarket's own sources

| Discrepancy | Detail | Practical reading |
|---|---|---|
| ToS headline list vs docs list | Hungary and Slovenia are in the ToS but not in the docs geoblock tables. Brazil, Belarus, Japan, South Korea, Malta (sports) and the African and Middle-East entries are in the docs but not in the ToS headline. | The ToS incorporates the docs list, so the **union** applies. |
| "API not restricted" (IE, JP, MT-sports, NL, KR) vs ToS | The docs say only the frontend is close-only. The ToS lists Ireland and the Netherlands as Restricted Persons with "no exceptions", and makes every docs-listed jurisdiction a Restricted Jurisdiction. | The API being technically open is **not permission** to trade. |
| North Korea | Listed in both the OFAC "block completely" table and the "close-only" table. | Documentation error. OFAC treatment prevails. |
| Perps vs predictions | Perps block all of Canada but not the UK, France and others. Predictions block 4 Canadian provinces plus about 37 more jurisdictions. | The restrictions are product-specific. Check the list for each product. |
| Help center vs docs | The help center (2026-08-14) calls IE, JP, MT and NL "completely restricted" and omits KR. Its header says 39 countries but it lists 40. It names only SG, PL, TH and TW as close-only. | The help center is older and less precise than the docs page. Use the docs page for the list and the ToS for who is covered. |
| Help center "location rather than residency" vs ToS "reside in / citizen of / located in" | The help center implies that a resident of a restricted country can trade while travelling. The ToS says otherwise. | Under the ToS, a resident or citizen of a restricted jurisdiction is barred wherever they are. |

### 1.5 Gamma `restricted` field

* Docs: "`restricted` | boolean | Market is geo-restricted for some jurisdictions." (VERIFIED, https://docs.polymarket.com/market-data/market-details.md; the field is in the Market and Event schemas of https://docs.polymarket.com/api-spec/gamma-openapi.yaml.) The docs do not say *which* jurisdictions, and there is no per-market jurisdiction list.
* Live census, open markets: the first 40,000 open markets from `/markets/keyset?closed=false` (400 pages, page cap reached) all had `restricted = true`. That is 40,000/40,000 across every `feeType` (VERIFIED; `analyses/geography/restricted_census.py`, `data/derived/gamma_restricted_census_2026-10-17.json`).
* Live sample, closed markets (up to 300 per window, `analyses/geography/restricted_history.py`):

| Market start window | n | restricted=true | restricted=false |
|---|---|---|---|
| 2022-01 | 300 | 271 | 29 (all created on or before 2022-01-03, e.g. NBA/NFL spread markets of 2022-01-01) |
| 2022-06 | 101 | 101 | 0 |
| 2023-06 | 96 | 94 | 2 |
| 2024-01 to 2026-06 (7 windows) | 300 each | 300 | 0 |

* Interpretation (PLAUSIBLE): the flag marks markets that are subject to the platform-wide geoblock. It switched on around the CFTC settlement of 2022-01-03 (https://www.cftc.gov/PressRoom/PressReleases/8478-22). **It carries no information for strategy selection.** Do not use it to infer that a market is tradable from a given country.

---

## 2. Polymarket US

### 2.1 Entities and regulatory record (primary sources)

| Date | Event | Label | Source |
|---|---|---|---|
| 2022-01-03 | CFTC order against Blockratize Inc. d/b/a Polymarket: $1.4M penalty, wind-down of non-compliant markets, cease-and-desist | VERIFIED | https://www.cftc.gov/PressRoom/PressReleases/8478-22 |
| 2025-07-09 | CFTC designates **QCX LLC** as a contract market. The CFTC page now reads "QCX LLC d/b/a Polymarket US", status Designated, "now operating under the assumed name of Polymarket US" | VERIFIED | https://www.cftc.gov/IndustryOversight/IndustryFilings/TradingOrganizations/49571 |
| 2025-07-21 | Polymarket press release: it has "closed an acquisition of the holding company of" QCX, LLC (exchange) and QC Clearing LLC (clearinghouse), "collectively 'QCEX'", for **$112 million**. It "paves the way for U.S. users to access Polymarket in the near future" | VERIFIED (company release) | https://www.prnewswire.com/news-releases/polymarket-acquires-cftc-licensed-exchange-and-clearinghouse-qcex-for-112-million-302509626.html |
| 2025-09-02 | CFTC Staff Letter 25-28: no-action relief on swap data reporting and recordkeeping for "QCEX Contracts" (fully collateralized binary and variable-payout options). Condition 6 barred third-party clearing | VERIFIED (as described in 25-48) | https://www.cftc.gov/csl/25-28/download (cited in 25-48) |
| 2025-11-24 | **Amended Order of Designation** vacates the provision that barred FCM intermediation. The exchange petitioned between 2025-08-14 and 2025-11-24 | VERIFIED | https://www.cftc.gov/media/12806/Polymarket%20US%20Amended%20Order%20of%20Designation/download |
| 2025-11-25 | Polymarket press release on the amended order: an "intermediated trading platform", brokerages and FCMs can onboard; no launch date given | VERIFIED (company release) | https://www.prnewswire.com/news-releases/polymarket-receives-cftc-approval-of-amended-order-of-designation-enabling-intermediated-us-market-access-302625833.html |
| 2025-12-11 | CFTC Staff Letter 25-48 removes condition 6 (third-party clearing). It confirms "Polymarket US is a designated contract market ('DCM') and Polymarket Clearing is a derivatives clearing organization ('DCO')" | VERIFIED | https://www.cftc.gov/csl/25-48/download |
| 2026-09-30 | Polymarket announces self-exclusion and deposit limits (US), and a Trust & Safety Center covering "U.S. and international platforms" | VERIFIED (company release) | https://www.prnewswire.com/news-releases/polymarket-launches-new-user-protections-and-trust--safety-program-302894374.html |
| 2026-09-30 | Polymarket US Rulebook, current version dated September 30, 2026 | VERIFIED | https://polymarketexchange.com/files/legal/latest/rulebook |

The polymarket.com footer says Polymarket "operates globally through separate legal entities. Polymarket US is operated by QCX LLC d/b/a Polymarket US, a CFTC-regulated Designated Contract Market. This international platform is not regulated by the CFTC and operates independently." (VERIFIED, polymarket.com HTML.)

The front-end app is a separate company, **PM US Tech (a/k/a QC Tech LLC)**. It is an "independent software vendor (ISV) front end" and "is not itself a DCM, DCO, FCM" (VERIFIED, US app T&C effective 2025-09-25, https://polymarket.us/tos → embedded Google Doc).

### 2.2 Launch timeline (mostly secondary)

| Date | Event | Label | Source |
|---|---|---|---|
| 2025-12-03 | US iOS app opens to waitlisted users with sports contracts first, as announced on Polymarket's X account | PLAUSIBLE (secondary) | https://www.theblock.co/amp/post/381253/polymarket-begins-opening-us-app-to-users-on-waitlist ; https://cointelegraph.com/news/polymarket-us-relaunch-waitlisted-users |
| 2026-05-12 | Waitlist removed and the public iOS rollout begins; no access code needed | PLAUSIBLE (secondary) | https://www.covers.com/industry/polymarket-removes-waitlist-launches-for-american-ios-users-may-12-2026 |
| 2026-06 (reported 2026-06-26) | CNBC and others report an ongoing CFTC investigation of Polymarket, following a WSJ report on staged-win influencer marketing. Two senators asked the CFTC to investigate, and a consumer group sued. Neither the CFTC nor the company has confirmed scope | PLAUSIBLE (secondary) | https://covers.com/industry/report-cftc-conducting-extensive-investigation-into-polymarket-june-26-2026 ; https://theblock.co/post/406400/bipartisan-senators-call-cftc-investigation-polymarket-fake-bets |
| 2026-06-25 | Help center: Polymarket US is an iOS app for US users, "Entirely separate from Polymarket.com - accounts are not connected"; Android "Coming Soon" | VERIFIED (company page) | https://help.polymarket.com/en/articles/15458828-website-vs-app-what-s-the-difference |
| 2026-10-17 | polymarket.us is live on the web. It links to the App Store and to Google Play (`com.polymarket.android`). Web trading status was not tested (that would need login) | VERIFIED (links present) | https://polymarket.us |
| Earliest US markets visible | Gateway market id 28, "Philadelphia vs. Green Bay" NFL, startDate 2025-11-03 | VERIFIED | `GET https://gateway.polymarket.us/v1/markets?limit=3&active=true` |

### 2.3 Products and markets

* The docs list sports (NFL, NBA, NHL, MLB, MLS, college, tennis, golf and more), politics, crypto, economics, weather, tech and culture. Contracts are fully collateralized: a short seller posts $1.00 per contract. Combos and RFQ also exist (VERIFIED, https://docs.polymarket.us/getting-started/what-is-polymarket-us.md, https://docs.polymarket.us/market-structure/collateral-and-margin.md).
* Live gateway census (`analyses/geography/us_gateway_census.py`, `data/derived/pm_us_open_markets_2026-10-17.parquet`). The first 8,000 open markets came back in default order (startDate 2026-03-19 to 2026-08-19, page cap reached, **not a full census**): sports 5,581, politics 2,067, culture 199, crypto 47, finance 46, technology 36, macro 12, geopolitics 7, science 5 (VERIFIED for the sample).
* Funding is in USD: debit card, ACH, Apple Pay, PayPal, Venmo, USDC ("iPhone, where available") and wire. Card and ACH have a $50k daily limit. Wires have a $5k minimum (VERIFIED, https://docs.polymarket.us/learn/get-started/fund-account.md).
* A single market buy in the app is capped at $1,000,000 (VERIFIED, https://docs.polymarket.us/learn/trading/access-and-limits/trading-limits.md).
* Maintenance is every Thursday 06:00–08:00 ET from 2026-09-24. All open orders are cancelled before the window (VERIFIED, https://docs.polymarket.us/faqs/general-faqs.md).

### 2.4 Separate order book from the international platform

* Structurally: Polymarket US is a fiat DCM with DCO clearing, a separate API host and USD prices. The international platform is a pUSD on-chain CLOB (VERIFIED, docs above).
* Empirically, at 2026-10-17 15:49 UTC, for "Democrats control the House after 2026 midterms" (`analyses/geography/book_compare.py`, VERIFIED):

| Venue | Best bid | Best ask | Tick |
|---|---|---|---|
| International (`which-party-will-win-the-house-in-2026`, YES token) | 0.90 × 1,001,030 | 0.91 × 399,871 | 0.01 |
| US (`paccc-usho-midterms-2026-11-03-dem`) | 0.902 × 55,910 | 0.903 × 558,949 | 0.001 |

The two books have different ticks, prices and sizes, so liquidity is not shared.
I found no Polymarket statement on shared liquidity, and the 2025-11-25 release does not address it (VERIFIED absence in that release).

### 2.5 Fee schedule (Polymarket US) vs international

Source: https://docs.polymarket.us/fees.md (VERIFIED; snapshot `pm_us_docs_fees.md`). The international fees are from `CONTEXT.md` and `notes/platform/fees_incentives.md`.

| Item | Polymarket US | Polymarket international |
|---|---|---|
| Taker fee | `Θ·C·p·(1−p)` with Θ = **0.0695** (Table Tennis 0.10). The page notes "Effective exchange-wide from 10 AM ET, Wednesday October 7, 2026". Rounding is banker's rounding to $0.01 | `shares·rate·p·(1−p)` with the rate by category: Crypto 0.07, Sports 0.05, Politics/Finance/Tech/Mentions 0.04, Geopolitics 0. **[corrected by verifier 2026-10-17]** Read the rate per market: NFL/college-football markets (`sports_fees_nfl_cfb_oct26`) and legacy `sports_fees_v2` markets charge 0.03, confirmed on-chain on 2026-10-17 (see fees_incentives.md) |
| Fee at p = 0.50, 100 contracts | $1.74 | Sports $1.25; Politics $1.00 |
| Maker | Rebate Θ = −0.0125 (about 18% of the taker fee). From **2026-10-19 13:00 ET** it moves to tiers by prior-month maker volume: none below $10M, then −0.0035 / −0.0070 / −0.0104 | Makers pay no platform fee. Maker Rebates are **15–25%** of taker fees, by category: Crypto 20%, Sports 15%, others 25% ([maker-rebates](https://docs.polymarket.com/programs/maker-rebates.md)). **[corrected by verifier 2026-10-17: was "20–25%"]** Builder maker fees of up to 50 bps can apply through third-party front ends |
| Taker rebate | Now 10% / 25% / 50% for prior-month taker volume of $250k / $1M / $10M+. From 2026-10-19: 3% / 5% / 10% / 15% / 30% at $250k / $1M / $10M / $25M / $50M+ | Taker Rebate Program, 3%–50% by 30-day weighted volume |
| Combo taker fee | `C·p·[0.0695(1−p) + 0.06(1−p)^4]`, no maker rebate | Combos exist; see the mechanics note |

### 2.6 API access

| Layer | Access | Notes | Source (VERIFIED) |
|---|---|---|---|
| Public API `https://gateway.polymarket.us` | No key | Markets, events, series, sports, search, **book**, **BBO**, settlement, price history. Tested live on 2026-10-17: `/v1/markets` and `/v1/markets/{slug}/book` and `/bbo` return 200 without auth | https://docs.polymarket.us/api-reference/introduction.md |
| Price history | No key | "book-derived Yes and No display prices… these are not individual trades" | https://docs.polymarket.us/api-reference/price-history/get-price-history.md |
| Retail API `https://api.polymarket.us` | Ed25519 API key from polymarket.us/developer, **after KYC** | Orders, portfolio, balances. The WebSockets `/v1/ws/markets` (book and **trades**) and `/v1/ws/private` both need a key. 25 req/s per IP | https://docs.polymarket.us/api-reference/authentication.md, /api-reference/websocket/overview.md, /api-reference/rate-limits.md |
| Institutional REST/gRPC/FIX | Registration portal plus Entity Participant and Clearing Member Agreement, funded by wire | Aggregated L2 only, under scopes `read:marketdata` and `read:l2marketdata` | https://docs.polymarket.us/trader-guide/onboarding.md |
| **Public trade tape** | **None** | "Trades are not disseminated via market data APIs. You can only see your own trades" | https://docs.polymarket.us/trader-guide/market-data.md |

Data terms (US app T&C §5): market data is "licensed to you for personal, non-commercial use in connection with your trading". "Redistribution, resale, scraping, bulk downloads, and commercialization of derived works are prohibited unless expressly licensed." §7(c): no "bots or automation except through authorized APIs" (VERIFIED, US T&C). The Participant Agreement §I.22 says data "may not be redistributed except as PMUS expressly permits" (VERIFIED, https://polymarketexchange.com/files/legal/latest/participant-agreement).

### 2.7 KYC and eligibility

* Sign-up collects date of birth, phone, legal name, residential address and **Social Security number**. A government ID and selfie may be required. KYC must be completed "before you can deposit funds or trade" (VERIFIED, https://docs.polymarket.us/learn/get-started/signup.md).
* Participant Agreement §II.8 (VERIFIED): no access by anyone domiciled, resident or located in an OFAC-sanctioned territory, a FATF black-list or grey-list jurisdiction, or "any jurisdiction that has imposed a national prohibition or warning on the marketing, distribution, or sale to retail clients of products comparable to the Contracts, including retail binary options". The list is updatable without notice.
* The docs say employees of sell-side and buy-side institutions are "generally permitted… unless their firm's internal policies state otherwise". Insider-type and influence-type restrictions apply under the Market Integrity policy (VERIFIED, https://docs.polymarket.us/learn/trading/access-and-limits/trading-restrictions.md).
* The app is "built for US residents" (VERIFIED, what-is page). Because an SSN is required, non-US persons practically cannot onboard (PLAUSIBLE).
* Clause (c) of §II.8 bars any jurisdiction with a national prohibition or warning on retail binary options. EU product-intervention measures, the UK FCA ban and ASIC's measures are such prohibitions, so most residents of the EU, the UK and Australia would be excluded even if they had an SSN. This is my reading and has not been tested against PMUS policy (PLAUSIBLE).

### 2.8 US state-level restrictions

| State | Action | Label | Source |
|---|---|---|---|
| Nevada | Nevada Gaming Control Board sued on 2026-01-15. A TRO followed (14 days, against Blockratize). Then a **preliminary injunction against QCX LLC**: no "sports-, election- or entertainment-related event contracts within Nevada" while enforcement continues. The written order was "forthcoming" as of 2026-06-03 | VERIFIED (AG release) / PLAUSIBLE (TRO details) | https://ag.nv.gov/News/PR/2026/Attorney_General_Ford_Announces_Preliminary_Injunction_in_Prediction_Market_Case/ ; https://www.yogonet.com/international/news/2026/02/03/117414-polymarket-barred-from-nevada-over-licensing-dispute |
| Connecticut | DCP cease-and-desist letters (about 2026-09-09) to 9 operators including **Polymarket**, plus 29 subpoenas. Underdog sued on 2026-09-16 | PLAUSIBLE (secondary) | https://sbcamericas.com/2026/09/16/ct-prediction-markets-crackdown/ ; https://legalsportsreport.com/277020/ct-sends-predictions-operators-cds-serves-suppliers |
| Massachusetts | **QCX LLC v. Campbell**, D. Mass. No. 1:26-cv-10651, filed 2026-02-09. Polymarket US sued pre-emptively for an injunction against enforcement of state gaming law, arguing CEA preemption, after a state court enjoined Kalshi's sports contracts. Outcome not found | PLAUSIBLE (secondary) | https://sbcamericas.com/2026/02/09/polymarket-sues-massachusetts/ ; https://www.bostonglobe.com/2026/02/10/business/polymarket-kalshi-lawsuit-massachusetts-sports-betting ; https://news.bloomberglaw.com/bloomberg-government-news/polymarket-sues-mssachusetts-to-preempt-state-shutdown |
| Tennessee | The sports wagering regulator reportedly ordered Polymarket, Kalshi and Crypto.com to stop offering sports contracts | PLAUSIBLE (secondary, date not confirmed) | https://finance.yahoo.com/news/polymarket-banned-portugal-hungary-prediction-175111303.html |
| Others (AZ, MD, TN, MI…) | A CBS roundup "as of October 16, 2026" lists Polymarket as unavailable or restricted in Nevada, Connecticut, Maryland and Tennessee, and without sports in Arizona. The article contradicts itself in places | PLAUSIBLE (secondary, low confidence) | https://www.cbssports.com/prediction/news/prediction-market-legal-states/ |

Polymarket US docs publish **no state availability list**. A grep of https://docs.polymarket.us/llms-full.txt for state names found none (VERIFIED absence). **Current state eligibility can only be confirmed in the app.**

---

## 3. Regulatory actions by other jurisdictions, 2025–2026

| Date | Jurisdiction | Authority | Action | Label | Source |
|---|---|---|---|---|---|
| (2024-11, context) | Switzerland | Gespa | Blacklisted as unlicensed gambling, with access restrictions | PLAUSIBLE | https://www.coindesk.com/policy/2026/07/18/france-orders-country-s-internet-service-providers-to-block-polymarket |
| (2024-11, context) | France | ANJ | Ban on transactions from France (Polymarket says it has blocked French trading since 2024-11) | PLAUSIBLE / company statement | CoinDesk above ; https://tools.prnewswire.com/en-us/live/20813/release/20260722EN10028 |
| 2025-01-08 | Poland | Ministry of Finance | Added to the register of prohibited gambling domains | PLAUSIBLE | https://www.tradingview.com/news/cointelegraph:924f2c135094b:0-polymarket-hit-by-fresh-european-crackdowns-as-hungary-portugal-block-access/ ; https://nextpredict.io/legal/eu/ |
| 2025-01 (days after Poland) | Singapore | Gambling Regulatory Authority | Access blocked | PLAUSIBLE | Cointelegraph/TradingView above |
| 2025-01-30 | Belgium | Gaming Commission | Blacklisted, with an ISP block requested | PLAUSIBLE | https://sigma.world/news/belgium-joins-growing-list-of-countries-banning-polymarket/ ; nextpredict |
| 2025-07-02 / 2025-08 | Australia | ACMA | Formal warning on 2025-07-02, then an ISP block request under the Interactive Gambling Act. Polymarket is named in "Latest illegal online gambling websites blocked" | PLAUSIBLE (ACMA pages returned 403 to this sandbox; content from a search snippet of the primary page) | https://www.acma.gov.au/articles/2025-08/latest-illegal-online-gambling-websites-blocked ; https://www.acma.gov.au/publications/2025-11/report/action-interactive-gambling-july-september-2025 |
| 2025-10-22 | Italy | ADM | Blacklisted | PLAUSIBLE | https://nextpredict.io/legal/eu/ |
| 2025-10-29 or 2025-11 | Romania | ONJN | Blacklisted. A Bucharest court reportedly refused suspension on 2026-04-01 | PLAUSIBLE (sources disagree on the date) | nextpredict (Nov 2025); search snippet of https://europeangaming.eu/portal/latest-news/2026/05/21/204906/prediction-markets-regulation-in-europe-legal-tracker-2026/ (403) |
| 2026-01 (≈ Jan 6–13) | Ukraine | (reported block) | Access blocked | PLAUSIBLE | Cointelegraph/TradingView above |
| 2026-01 (≈ Jan 16–20) | Hungary | SZTFH (Supervisory Authority for Regulated Activities) | Temporary block of the domain and subdomains for "forbidden organization of gambling activities" | PLAUSIBLE | Cointelegraph/TradingView above |
| 2026-01 (≈ Jan 19–20) | Portugal | SRIJ | Ordered to wind down activity in Portugal | PLAUSIBLE | Cointelegraph/TradingView above ; nextpredict |
| 2026-02 → 2026-06-23 | Netherlands | Kansspelautoriteit | Order to stop. A €420k penalty was reportedly forfeited. The objection was rejected on 2026-06-23 and an appeal is open | PLAUSIBLE | nextpredict ; search snippet of europeangaming tracker |
| 2026-03 (reported 2026-03-17) | Argentina | Buenos Aires court (Judge Susana Parada), at the city's request | Network-level block and app-store removal | PLAUSIBLE | https://finance.yahoo.com/news/buenos-aires-court-orders-polymarket-102935400.html |
| 2026-04-24 | Brazil | Ministry of Finance, CMN Resolution 5298, Anatel | Prediction markets declared illegal. 28 platforms blocked, Polymarket and Kalshi among them | PLAUSIBLE | https://igamingbusiness.com/legal-compliance/compliance/brazil-prediction-markets-illegal/ ; https://www.bloomberg.com/news/articles/2026-04-24/brazil-moves-to-ban-prediction-markets-on-elections-sports |
| 2026-05-22 | Indonesia | Komdigi | Site blocked as online gambling | PLAUSIBLE | https://digitalpolicyalert.org/change/19524-ministry-of-communication-and-digital-affairs-investigation-into-polymarket-over-alleged-illegal-gambling-activities ; https://cointelegraph.com/news/indonesia-blocks-polymarket-bets-presidents-exit |
| 2026-05-26 | Spain | DGOJ | Precautionary block of **Polymarket and Kalshi**, with sanction proceedings expected to take 3–4 months | PLAUSIBLE | https://igamingbusiness.com/legal-compliance/dgoj-blocks-polymarket-kalshi-unauthorised-operations/ |
| 2026-06-17 | India (Kalshi, not Polymarket) | Kalshi Member Agreement revision | Kalshi reportedly withdraws from India after the Online Gaming Act 2025 takes effect (2026-05-01). Its restricted list is reported at 55 jurisdictions | PLAUSIBLE (secondary) | https://parameter.io/kalshi-expands-restricted-territory-count-to-55-nations-following-indian-ban/ ; https://publicgaming.com/news-categories-m/regulatory-issues/16046-kalshi-retreats-from-india-while-european-regulators-target-prediction-markets |
| 2026-06-18 | **BE, FR, DE, IT, NL, PL, PT, ES, CH** (joint) | Nine gambling regulators (tags: ADM, ANJ, DGOJ, GGL, Ksa, SRIJ, …) | Joint statement before the FIFA World Cup. They promise to act "against prediction markets platforms that fail to comply with our local regulations" and ask sports bodies to check legality before partnerships. No platform is named | PLAUSIBLE (secondary; primary text on anj.fr not reachable: expired TLS certificate from this sandbox) | https://www.gamingintelligence.com/legal/232164-european-gambling-regulators-warn-of-prediction-market-risks/ ; https://europeangaming.eu/portal/latest-news/2026/06/19/207511/why-nine-european-regulators-moved-together-on-prediction-markets/ |
| 2026-07-16/17 | France | ANJ | Orders ISPs to block the whole site, including view-only access. The press cites the ANJ on circumvention of the 2024 geoblock, missing identity checks and a Paris criminal investigation opened on 2026-05-04. On 2026-07-22 Polymarket said it "intends to challenge the decision in French courts", and a court challenge was reported on 2026-08-24 | PLAUSIBLE (news) / VERIFIED (company statement) | CoinDesk above ; https://tools.prnewswire.com/en-us/live/20813/release/20260722EN10028 ; https://kulturegeek.fr/news-357512/polymarket-saisit-justice-contester-blocage-france |
| 2026-08-18 | **South Korea** | Korea (Media and) Communications Standards Commission, telecom review subcommittee | ISPs ordered to block domestic access under the Criminal Act (gambling facilitation) and the National Sports Promotion Act. The KCSC rejected Polymarket's defences: the Korean-language service had been removed, won were not accepted, and the platform is non-custodial | PLAUSIBLE (secondary) | https://koreatimes.co.kr/business/companies/20260819/korea-moves-to-block-polymarket-over-illegal-gambling ; https://cointelegraph.com/news/south-korea-block-polymarket-gambling-concerns ; https://sbcnews.co.uk/sportsbook/2026/08/18/polymarket-blocked-in-south-korea/ |
| 2025-09 (reported) | Germany | GGL (reported) | Korea Times reports Germany "blocked" Polymarket in September 2025 for unauthorized betting, and Australia in August 2025. nextpredict says political, economic and social markets cannot be licensed. Polymarket is close-only per its docs | PLAUSIBLE (secondary; no GGL primary found) | Korea Times above ; https://nextpredict.io/legal/eu/ |
| (no date) | India | n/a | CoinDesk lists India as restricted without detail | UNSUPPORTED | CoinDesk above |

**Several of these are not on Polymarket's docs geoblock list as of 2026-10-17:** Spain, Portugal, Switzerland, Romania, Ukraine (outside the three occupied regions), Argentina and Indonesia. Hungary is listed only in the ToS. South Korea is on the docs list (frontend close-only, "API not restricted") despite a national ISP block. Local illegality and Polymarket's geoblock are two different things.

US federal context (VERIFIED, CFTC):

* 2026-02-04: the CFTC withdrew its 2024 "Event Contracts" proposal and staff letter 25-36 (https://www.cftc.gov/PressRoom/PressReleases/9179-26).
* 2026-03-12: the CFTC published an ANPRM on prediction markets (https://www.cftc.gov/PressRoom/PressReleases/9194-26).
* 2026-10-09: the CFTC approved an NPRM, "Further Definition of 'Swap' – Inclusions" (RIN 3038-AF82). It would define event contracts on sports, politics, culture and weather as swaps. Comments are due 30 days after Federal Register publication (https://www.cftc.gov/media/14731/NRPM_EventContractsSwapInclusions100926/download).

The appeals courts are split on whether federal law preempts state gambling law for Kalshi sports contracts:

* Sixth Circuit, 2026-09-25 (Ohio/Tennessee): sports contracts are not swaps, and the CEA does not preempt state gambling law.
* The Ninth Circuit (Nevada) is reportedly also against Kalshi, and the Third Circuit (New Jersey) reportedly for Kalshi.
* The Fourth Circuit (Maryland) is pending.

These rulings are PLAUSIBLE (secondary): https://natlawreview.com/article/sixth-circuit-deepens-circuit-split-kalshi-sports-event-contracts-are-not-swaps-and.

---

## 4. Kalshi

### 4.1 Who can access

| Fact | Label | Source |
|---|---|---|
| KalshiEX LLC is a CFTC DCM. Members must not be "domiciled in, organized in, or located in" a prohibited jurisdiction | VERIFIED | https://kalshi-public-docs.s3.amazonaws.com/kalshi-member-agreement.pdf (S3 last-modified 2025-10-10) |
| Kalshi's Restricted Jurisdictions: Afghanistan, Algeria, Angola, **Australia**, Belarus, Bolivia, Bulgaria, Burkina Faso, Cameroon, **Canada**, CAR, Côte d'Ivoire, Cuba, DRC, Ethiopia, **France**, Haiti, Iran, Iraq, Kenya, Laos, Lebanon, Libya, Mali, Monaco, Mozambique, Myanmar, Namibia, Nicaragua, Niger, North Korea, **Poland**, **Russia**, **Singapore**, Somalia, South Sudan, Sudan, Syria, **Taiwan**, **Thailand**, Ukraine (Crimea, Donetsk, Luhansk, Zaporizhzhia, Kherson), **United Kingdom**, Venezuela, Yemen, Zimbabwe, plus US-sanctioned territories | VERIFIED (for that S3 version; it may not be the live version) | same |
| Help center: "you can trade on Kalshi from many countries"; eligibility "is subject to the terms of the Kalshi Member Agreement"; sign-up verifies identity and country of residence. International users may fund by debit card, wire (min $1,000) or crypto, but not ACH, PayPal or Venmo. The live agreement link is `https://kalshi.com/docs/kalshi-member-agreement.pdf` (429 from this sandbox) | VERIFIED (article updated 2026-03-20) | https://help.kalshi.com/en/articles/14026044-can-i-trade-on-kalshi-from-outside-the-united-states |
| A Member Agreement revision on 2026-06-17 reportedly added India, for a total of about 55 restricted jurisdictions. **The S3 copy used above (2025-10-10) predates it and is stale** | PLAUSIBLE (secondary) | https://parameter.io/kalshi-expands-restricted-territory-count-to-55-nations-following-indian-ban/ |
| On 2025-10-10 Kalshi said it was open in 140+ countries. Sportico reported 12 days later that users in India, Brazil and Nigeria could not sign up | PLAUSIBLE (secondary) | https://www.yogonet.com/international/news/2025/10/13/115763-kalshi-valued-at-5-billion-as-it-expands-to-140-countries-aims-to-globalise-prediction-markets ; https://www.sportico.com/business/sports-betting/2025/kalshi-international-countries-access-1234874388/ |
| Spain (2026-05-26) and Brazil (2026-04-24) blocked Kalshi as well as Polymarket | PLAUSIBLE | §3 above |
| US states: sports contracts are reportedly blocked or halted in Nevada, Michigan, Washington and Massachusetts, among others. Connecticut AG sued Kalshi in 2026 | PLAUSIBLE (secondary) | https://www.cbssports.com/prediction/news/prediction-market-legal-states/ ; https://portal.ct.gov/ag/press-releases/2026-press-releases/connecticut-sues-kalshi-to-stop-illegal-unlicensed-sports-betting (not fetched) |
| kalshi.com returned HTTP 429 to this sandbox, so the live help-center eligibility pages were not read | VERIFIED (limitation) | live |

### 4.2 Market-data API and data terms

| Fact | Label | Source |
|---|---|---|
| Public REST endpoints work without authentication. The production base is `https://external-api.kalshi.com/trade-api/v2`. The legacy `api.elections.kalshi.com` also answered `/exchange/status` with 200 on 2026-10-17 | VERIFIED | https://docs.kalshi.com/getting_started/quick_start_market_data.md ; live |
| The WebSocket needs authentication even for public channels. Historical trades and markets have `/historical/*` endpoints | VERIFIED | https://docs.kalshi.com/llms.txt |
| Authenticated rate limits use token buckets. The Basic tier starts at sign-up; higher tiers are earned by volume | VERIFIED | https://docs.kalshi.com/getting_started/rate_limits.md |
| **Kalshi Data Terms of Use**: "personal use for non-commercial purposes"; non-commercial excludes "(1) the development of any software program, including… training a machine learning or artificial intelligence system; or (2) providing archived or cached data sets". Collecting, copying, downloading, scraping or "compiling (… systematic retrieval to create collections… databases)" or text-and-data-mining "Kalshi Data" needs prior written consent. Any ML/AI use "is expressly prohibited" | VERIFIED (text) / PLAUSIBLE (that this 2024-09-11 S3 copy is current and covers API data; it is written about "the Website… or otherwise") | https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf |
| **Correction to the first pass.** There *is* an API licence. The docs home page says: "By continuing to use or access Kalshi's API, you are agreeing to be bound to our Developer Agreement" (link https://kalshi.com/developer-agreement, 429 from this sandbox). The agreement is not in llms.txt, which is why the first pass missed it | VERIFIED | https://docs.kalshi.com/welcome.md ; snapshot `kalshi_docs_welcome_excerpt_2026-10-17.md` |
| **Kalshi Developer Agreement v1.1**: "Accessing or using Kalshi's API shall be considered a binding acceptance". §3: "Use of Kalshi APIs is expressly limited to facilitating a members own trading on the Exchange; all other usages are disallowed". §3.1 prohibits "Collecting, caching, aggregating, or storing data or content accessed via the API except for purposes of facilitating your own trading on Kalshi", and sharing with third parties without written authorization. §3.5 prohibits access "for any other benchmarking or competitive purposes". §4.1.1: "You must be a Member of Kalshi's Exchange". New York law | VERIFIED (text of the S3 copy, last-modified 2023-11-09) / PLAUSIBLE (that v1.1 is the live version) | https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf ; snapshot `kalshi_developer_agreement_v1.1_s3_lastmod_2023-11-09.txt` |
| API help article: the API gives access to "public information on the exchange, like market data" | VERIFIED (updated 2026-03-10) | https://help.kalshi.com/en/articles/13823854-kalshi-api |

---

## 5. Who can access which venue (cross-venue feasibility)

This is my reading of the sources above. Each person must still confirm their own position.

| Trader profile | Polymarket intl | Polymarket US | Kalshi | Feasible cross-venue pair |
|---|---|---|---|---|
| US resident in the US | **No** (ToS; geoblock) | Yes (KYC with SSN; not NV; other states contested) | Yes (state caveats) | Kalshi ↔ PM US only |
| US citizen living abroad | **No**: the ToS covers "a citizen of" (VERIFIED text) | Unclear: SSN available, but "located in" restrictions apply abroad | Depends on location and the Kalshi list | Probably none (PLAUSIBLE) |
| UK, France, Poland, Singapore, Taiwan, Thailand, Russia, Australia | No | No | No (on Kalshi's list) | None |
| Germany, Italy, Belgium, Brazil, New Zealand, Slovakia, Ireland, Netherlands, Japan, South Korea | No (close-only, or ToS-restricted; South Korea also ISP-blocked since 2026-08-18) | No | Not on Kalshi's 2025-10 S3 list (the live 2026 list was not readable here), but local law applies (Brazil blocked Kalshi) | None, or Kalshi-only where lawful |
| India | Not on Polymarket's lists | No | Reportedly restricted since 2026-06-17 | None for the Kalshi leg |
| Canada outside BC/ON/AB/QC | Not geoblocked for predictions (perps blocked) | No | No (all of Canada restricted) | None |
| Spain, Portugal, Hungary, Romania, Switzerland, Argentina, Indonesia, Ukraine | Not all on the docs geoblock, but a local regulator has blocked Polymarket | No | Spain blocked Kalshi; others unclear | Doubtful / likely unlawful locally |
| Other non-US countries on neither list, where local law allows | Possibly | No | Possibly, if Kalshi actually onboards there (reported unreliable) | PM intl ↔ Kalshi, for a small population |

Polymarket intl ↔ Polymarket US needs a person who is not a US person, not located in the US and not a US citizen, yet passes SSN-based US KYC. That is effectively impossible (PLAUSIBLE).

---

## 6. Implications for this project

1. **The trader must confirm their own eligibility before any strategy is chosen.** Check residence, physical location, **citizenship** (Polymarket intl), entity and affiliation status (Polymarket's "Capital Market Client" clause), and state of residence (Polymarket US, Kalshi). `geoblock: false` is necessary but not sufficient. Using a VPN to get there is a ToS violation and risks close-only wallets. Do not rely on the help center's "physical location rather than residency" travel example. The ToS also covers residents and citizens, and polymarket.com sign-up has no identity check, so a user who is wrongly eligible will not be stopped at sign-up; they carry that risk themselves.
2. **Research on public read-only data is not trading.** The Polymarket ToS lets people in Restricted Jurisdictions use the Content Features, and the Perps docs say "Read-only market data is not subject to these restrictions". This sandbox is a blocked US IP doing view-only reads, and that is the correct posture. **Data-use terms still apply to research:**
   - Polymarket intl forbids Site scraping and forbids professional or fintech entities, and their affiliates, from using the Data without a written agreement.
   - Polymarket US licenses its market data for personal, non-commercial use only, with no bulk downloads or scraping unless licensed.
   - Kalshi's Data Terms forbid systematic retrieval, compiling datasets and any AI/ML use without written consent.

   - Kalshi's **Developer Agreement** limits *any* API use to a member's own trading. It forbids storing or aggregating API data for anything else, and forbids benchmarking or competitive use.

   This project's use of Kalshi data is research: by a non-member, AI-assisted, cross-venue and comparative. That **appears to fall outside both Kalshi documents** (PLAUSIBLE; not legal advice). Recommended posture:
   - Do not build or store a Kalshi dataset. As of this pass, `data/raw/` and `data/derived/` contain no Kalshi pulls.
   - Limit Kalshi to reading its public documentation.
   - Treat any Kalshi-leg strategy as needing either a Kalshi membership used for the member's own trading, or written consent from Kalshi.
3. **Polymarket US is a different market for backtesting.** Results from international data do not transfer directly to Polymarket US:
   - Fees differ: 0.0695 versus 0.04–0.07 by category, and the maker economics differ.
   - Ticks differ: 0.001 versus 0.01 on the market compared.
   - The book is separate.
   - There is **no public trade tape**: only book, BBO, settlement and book-derived display prices. Taker-flow or wallet-following strategies cannot be researched on Polymarket US from public data.
4. **Some strategies need accounts on two venues.** Cross-venue arbitrage and lead-lag execution on both legs need accounts on both venues. Most people do not qualify: US persons are confined to Kalshi ↔ Polymarket US, and non-US persons to Polymarket intl ↔ Kalshi in a narrow set of countries. These strategies are **infeasible for many users**. A one-venue variant uses the other venue's public prices as a signal only:
   - With **Kalshi as the signal**, the Developer Agreement allows this only for a Kalshi member, and only for that member's own Kalshi trading. Using Kalshi prices to trade on Polymarket is therefore not covered.
   - With **Polymarket as the signal** (for example, a Kalshi member watching Polymarket prices), the Polymarket ToS applies. It permits the Content Features but bans Site scraping, and it bans data use by "fintech" and professional entities.
5. **Regime risk is real and recurrent.** Regulators have switched countries to close-only, ISP-blocked whole sites (France, 2026-07-16) and enjoined venues in states (Nevada). Any strategy that holds positions for long periods should assume access could fall to close-only mid-trade. Backtests should not count on continuous access for a user in a contested jurisdiction.
6. **The `restricted` flag cannot be used for universe selection.** It is effectively always `true`.

---

## 7. Contradictions and discrepancies

* **With CONTEXT.md:**
  - CONTEXT lists the Kalshi public API at `api.elections.kalshi.com`. Kalshi's docs now give `https://external-api.kalshi.com/trade-api/v2` as production. Both answered 200 on 2026-10-17, so this is an update rather than an error.
  - CONTEXT treats the Kalshi public API as a usable data source. It is technically reachable without a key. But Kalshi's Developer Agreement (v1.1) limits API use to members' own trading and bars storing or aggregating data for other purposes, and its Data Terms restrict systematic retrieval and AI/ML use. This is a **terms risk** that CONTEXT does not mention, and it affects any Kalshi-leg lead-lag or cross-venue test.
  - CONTEXT's fee facts apply only to the international platform. Polymarket US has a separate schedule (§2.5).
* **With this note's first pass:** §4.2 said no Kalshi API licence existed. The Developer Agreement linked from docs.kalshi.com contradicts that, and the row has been corrected. The Kalshi restricted list from the S3 copy (2025-10-10) is probably stale, since India was reportedly added on 2026-06-17.
* **Inside Polymarket's sources:**
  - The ToS list differs from the docs list: Hungary and Slovenia appear only in the ToS.
  - The docs say "API not restricted" for IE/JP/MT/NL/KR, while the ToS bars Ireland and the Netherlands outright.
  - North Korea is listed twice.
  - The Perps and Predictions lists differ.
  - The help center (2026-08-14) says "39" countries but lists 40, calls IE/JP/MT/NL "completely restricted", omits KR, and bases permissions on "physical location rather than residency", which contradicts the ToS. Its "Android coming soon" also conflicts with the Google Play link on polymarket.us.
* **Secondary sources disagree on dates:** Romania (2025-10-29 vs Nov 2025) and Belgium (2025-01-30 vs Feb 2025). Polymarket US state availability differs across roundups, and the CBS article contradicts itself.

## 8. Open questions

* Polymarket US: the official, current list of states where trading is available is not in the docs. Android and web trading status was not verified by login.
* Are the Kalshi Developer Agreement v1.1 (S3, 2023-11-09), the Data Terms (S3, 2024-09-11) and the Member Agreement (S3, 2025-10-10) the live versions? kalshi.com, including `/developer-agreement` and `/docs/kalshi-member-agreement.pdf`, returned 429 to this sandbox. A human should read the live pages before any Kalshi data use.
* What is the full live Kalshi restricted-jurisdiction list after the reported 2026-06-17 revision (about 55 entries)?
* What is the primary text of the 2026-06-18 joint statement by nine European regulators? anj.fr presented an expired TLS certificate, and TLS checks were not bypassed.
* Will Polymarket add Spain, Portugal, Romania, Switzerland, Argentina, Indonesia, Hungary and Slovenia to the docs geoblock list?
* How is the ToS "citizen of" language enforced for US citizens abroad?
* Primary regulator texts for the Hungary, Portugal, Ukraine, Romania, Netherlands, Germany, Indonesia and Argentina actions are missing. The ACMA pages were blocked (403).
* What is the outcome of the Nevada written order or appeal, of Connecticut's C&D against Polymarket, and of the CFTC NPRM of 2026-10-09 and its effect on preemption litigation?

## 9. Provenance

* Scripts: `analyses/geography/restricted_census.py`, `restricted_history.py`, `us_gateway_census.py`, `book_compare.py`. Run them from `polymarket_research/` with `PYTHONPATH=.`. Raw API responses are stored by `pmr.http` under `data/raw/`.
* Derived data: `data/derived/gamma_restricted_census_2026-10-17.json` and `data/derived/pm_us_open_markets_2026-10-17.parquet`.
* Document snapshots in `data/raw/legal_2026-10-17/`:
  - Polymarket docs pages (geoblock, perps restrictions).
  - Polymarket intl ToS text; Polymarket US app T&C text; Polymarket US Participant Agreement text; Polymarket US fees, KYC and market-data docs.
  - CFTC amended order and Staff Letter 25-48 texts.
  - Kalshi Data Terms and Member Agreement texts.
  - Second pass:
    - Polymarket help-center articles: geographic restrictions (2026-08-14), website vs app (2026-06-25), sign-up (2026-01-12).
    - Kalshi Developer Agreement v1.1 text.
    - Kalshi docs welcome excerpt (the Developer Agreement clause).
    - Kalshi help article on trading outside the US (2026-03-20).
  - A Polymarket US book sample.
  - The geoblock response from this sandbox, with the IP redacted.
