# Read-only Polymarket bet alerts

A small, self-contained monitor for a configured list of public wallets. It polls the public
Data API v2, stores every executed fill in SQLite, groups fills into bet events, enriches
qualifying bets with a fresh order-book snapshot and market state, and notifies via console,
file, Telegram or email.

**What it is not.** It holds no private keys, seed phrases or trading API keys. It never
connects a wallet, places orders or copies trades. **Nothing is deployed and no monitoring is
running.** The CLI runs in the foreground only while you run it. By default every alert is
labelled informational: *no copy signal has been validated by this research*.

```
cd polymarket_research
python -m alerts.run --config alerts/config.example.yaml --once          # one cycle, then exit
python -m alerts.run --config alerts/config.example.yaml                 # foreground loop (30 s +/- 5 s), Ctrl-C to stop
python -m alerts.run --config alerts/config.example.yaml --report        # stored state and open problems, no network
python -m alerts.run --config alerts/config.example.yaml --once --backfill-hours 48 --db /tmp/x.sqlite
python -m pytest alerts/tests -q                                         # 108 tests, no network
```

Flags: `--once`, `--backfill-hours N` (the first cycle re-reads at least N hours, idempotently),
`--db PATH`, `--interval S`, `--max-cycles N`, `--dry-run` (console and file only, even if
Telegram or email are enabled), `--report`, `--log-level`. Exit codes: 0 means all polls were OK,
2 means a configuration error, 3 means a `--once` run hit at least one data problem (useful under cron),
4 means another monitor process already holds this database's lock (`<db>.lock`; one process per DB).

---

## 1. Architecture

```
                        public, unauthenticated, read-only HTTPS
   +----------------------------------------------------------------------------------+
   |  data-api.polymarket.com        gamma-api.polymarket.com      clob.polymarket.com |
   |  /v2/activity  (poll source)    /markets?condition_ids=       /book  (fresh book)  |
   |  /v2/trades    (taker check)    (question, event, fees,       /markets/{cid}       |
   |  /v2/positions (exposure)        gameStartTime, event.live)   (closed, accepting,  |
   |  /v2/status    (feed lag)                                      secondsDelay)       |
   +-------------^------------------------------^-----------------------^-------------+
                 |                              |                       |
          http_client.py  (short timeouts, <=2 retries honouring Retry-After, DataError for every failure)
                 |                              |                       |
          sources.py  (envelope + row schema checks, full cursor pagination, CDN cache-bust)
                 |                              |                       |
   +-------------+-----------+          +-------+-----------------------+------+
   | poller.py               |          | enrich.py                            |
   |  window = watermark -   |          |  book depth 1c/5c, spread, price     |
   |  overlap; walk all pages|          |  deterioration, follower fee,        |
   |  -> fills (INSERT OR    |          |  maker/taker, exposure, market state |
   |  IGNORE by fill_id)     |          +-------------------^------------------+
   |  advance watermark only |                              |
   |  after a complete walk  |    grouping.py --> bets --> rules.py (qualify / suppress /
   +-----------+-------------+                               COPY-CANDIDATE rules)
               |                                              |
               v                                              v
   +---------------------------------------------------------------------------+
   |  SQLite (store.py, WAL): wallets, fills, bets, alerts, deliveries,         |
   |  poll_state, health_events, meta                                           |
   +---------------------------------------------------------------------------+
               ^                                              |
               | health.py: DATA PROBLEM / RECOVERED episodes,| pending deliveries
               | stale wallets, /v2/status lag, 24 h digest   v
               |                               dispatch.py (own thread + own DB connection in loop mode)
               +-------------------------------  pending -> sending -> sent | retry(backoff) | failed
                                               notify.py: console | file (.ndjson) | Telegram | SMTP
```

Modules (all in `alerts/`): `config.py` strict YAML loader; `http_client.py`; `sources.py`;
`fills.py` (identity, maker/taker); `poller.py`; `grouping.py`; `enrich.py`; `rules.py`;
`render.py`; `health.py`; `notify.py`; `dispatch.py`; `engine.py` (one cycle, loop);
`clock.py` (server-corrected clock); `logsafe.py` (credential-redacting log handler);
`instance.py` (one process per DB); `run.py` (CLI). The shared research client `pmr` is reused for pure functions:
`pmr.fees.taker_fee` and `market_fee_rate`, and `pmr.api.normalize_book` and `jlist`. The alert
system has its own thin HTTP layer because `pmr.http.request_json` retries up to six times with
sleeps of up to 60 s and writes every response to `data/raw/`. That suits batch research. In a
30-second loop it would block a cycle for minutes during an outage and write thousands of files a day.

## 2. Data flow, one cycle

1. `GET /v2/status`. If the serving lag is above 120 s, or the snapshot is older than 300 s, a
   **DATA PROBLEM** is raised and the watermark safety margin widens to the reported lag.
2. For each wallet, walk `GET /v2/activity?user=…&type=TRADE,SPLIT,MERGE,REDEEM,CONVERSION&start=<watermark-600>&end=<now+1d>&sort_direction=ASC&limit=500`,
   following `pagination.next_cursor` until it is `null`. Each page is schema-checked and its rows
   are inserted as fills (`INSERT OR IGNORE`). Only after the full walk does the watermark advance.
3. Unassigned fills are attached to bets (same wallet, condition, outcome token and side,
   consecutive fills at most 10 min apart).
4. Changed bets are evaluated. A BUY bet at or above `min_usdc` is enriched (fresh book, fees,
   exposure, market state) and an alert is stored with one pending delivery per channel. Sells,
   merges, splits and redeems are stored and summarised in the digest, but do not alert unless
   configured to.
5. Stale-wallet check and, every 24 h, a digest/heartbeat.
6. The dispatcher sends pending deliveries with rate limits and backoff. It runs in its own thread
   in loop mode, and after the cycle in `--once` mode.

## 3. Executed vs unfilled orders

Public data shows **only executed trades**. `/v2/activity` and `/v2/trades` rows are settled fills
with a block timestamp and transaction hash. Resting or unfilled orders are not observable through
any public read-only endpoint. Cancelled orders and failed matches (MATCHED → FAILED) never become
rows. The system handles "executed vs unfilled" by **only ever alerting on executed fills**. An
alert means the wallet's order filled at least partly. It cannot tell you about the remainder of the
order, or about limit orders still resting on the book.

## 4. What was verified (2026-10-17)

Against `https://data-api.polymarket.com/v2/openapi.json` (title "Polymarket Data API v2",
version 0.1.0) and live calls:

| Fact | How verified |
|---|---|
| `/v2/activity` params: `user`, `limit` (default 100, max 1000; 2000 → `400 invalid_request`), `cursor`, `type` (comma list; unknown → 400), `condition`/`event_id`, `side`, `start`/`end`, `sort_by=TIMESTAMP`, `sort_direction` ASC/DESC (default DESC), `exclude_deposits_withdrawals` (default true) | OpenAPI + live |
| `start`/`end` are **inclusive** epoch seconds on the block timestamp, honoured on the `user` shape of `/v2/activity` and `/v2/trades`. Omitted `start` floors to three years back; `start=1` gives full history. The `condition`/`event_id` shapes of `/v2/trades` ignore them | OpenAPI; live: `start=T` returns the row at T, `start=T+1` does not; a `[826, 843]` window returned exactly the 5 rows inside it |
| Ordering is keyset on `(block_timestamp, sequence_id)`. **`sort_direction=ASC` is honoured on `/v2/activity`, ignored on `/v2/trades`** (always DESC) | live |
| Cursor pagination: follow `pagination.next_cursor` until `null`. `has_more` is exact. The trades/activity cursor carries only the seek anchor and page size, so filters must be re-sent on every page. A garbage cursor gives `400 "invalid cursor"` | OpenAPI + live (recorded 3-page walk in `tests/fixtures/activity_pages_live.json`) |
| `/v2/activity?type=TRADE` rows equal `/v2/trades?taker_only=false` rows (mintblade: 727 = 727, identical multiset), so activity covers maker fills too | live |
| A malformed or unknown address returns **200 with an empty list**, so addresses are validated in config | live |
| CDN caching: `/v2/activity` `cache-control: public, max-age=15`, `/v2/trades` and Gamma `max-age=300` (`x-cache: Hit` on repeats). Varying `end` gives `x-cache: Miss` | live headers |
| Taker inference: `usdc_size` includes the fee (BUY pays `size*price + fee`, SELL receives `size*price − fee`). Every fee-embedded row was in the `/v2/trades` taker-only set (mintblade 166/166, second wallet 54/54). Implied rate 0.03 = Gamma `feeSchedule.rate` of that market (`sports_fees_v2`). Rows without a fee difference can be makers or takers in fee-free markets (the second wallet had 42 such taker rows) | live; fixture test `test_fee_embedded_rows_are_takers_on_recorded_data` |
| `/v2/positions?user=&condition=` and `&event_id=` work; default `status=OPEN` is the superset (includes settled-but-unredeemed) | OpenAPI + live |
| Gamma `/markets?condition_ids=` returns `[]` for a resolved market unless `closed=true`, and `[]` for an open market with `closed=true` | live |
| Market link: `https://polymarket.com/event/<event_slug>` returns 200 with `rel=canonical` to itself. `/event/<event_slug>/<market_slug>` returns 200. `/market/<market_slug>` 307-redirects to `/event/<event_slug>/<market_slug>`. **A non-existent slug also returns 200** (generic page), so a 200 alone does not prove the event exists | live (curl) |
| Data API rows sometimes have an empty `event_slug`. Gamma `events[0].slug` is used as the fallback | live global feed |
| CLOB `/book` returns 404 `"No orderbook exists for the requested token id"` for resolved markets. CLOB `/markets/{condition_id}` is not CDN-cached (`cf-cache-status: DYNAMIC`) and gives `closed`, `accepting_orders`, `seconds_delay`, `game_start_time` | live |
| `/v2/status` → `serving.lag_seconds` (1 s at check time), `age_seconds` (13 s), `ingestion` cursors | live |

**Refines CONTEXT.md:** CONTEXT says `start`/`end` "appeared to be ignored on one test". They
**are honoured on the `user` shape** (`/v2/activity?user=`, `/v2/trades?user=`) and ignored on the
`condition`/`event_id` shapes. That is documented in the OpenAPI spec and was confirmed live. This
system only uses the `user` shape.

## 5. Storage schema (SQLite, `store.py`)

Migrations are versioned (`schema_migrations`, `PRAGMA user_version`), and every statement is
`CREATE … IF NOT EXISTS`, so running them any number of times is harmless (tested).

| Table | Key | Purpose |
|---|---|---|
| `wallets` | `address` (lowercase) | Mirror of config: label, `cluster_id`, `cluster_confidence` ∈ {confirmed, probable, weak, none}, `cluster_note`, thresholds, enabled |
| `fills` | `fill_id` = sha256(wallet, tx hash, asset, side, size, price, ts, type, occurrence) | Every activity row, with `raw_json`, `liquidity_role` (taker/maker/unknown), `fee_usdc`, `bet_id`, `first_seen_at` (detection time), `poll_mode` (bootstrap/live) |
| `bets` | `bet_id` = id of the bet's first fill | Grouped fills: side, kind (new_position, addition, reduction, split, merge, redeem, conversion), time span, shares, notional, cash, `alert_state` |
| `alerts` | `alert_id`; **UNIQUE `dedupe_key`** | One per bet (`bet:<id>`), problem (`health:<event>:open`), digest (`digest:<period>`), etc. Stores rendered text, full JSON payload, status (pending/sent/partial/failed/suppressed) and suppression reason |
| `deliveries` | (`alert_id`, `channel`) | Delivery state machine: pending → sending → sent / pending (retry) / failed / unknown, with attempts, `next_attempt_at`, `last_error` (credentials scrubbed), `possible_duplicate` |
| `poll_state` | `wallet` | `watermark_ts` (all rows ≤ it observed), `last_seen_row_ts`, `last_cursor`, `last_attempt_at`, `last_success_at`, `consecutive_failures`, `last_error`, counters |
| `health_events` | `event_id` | Problem *episodes*: scope, kind, error class, first/last seen, occurrences, `notified_at`, `resolved_at` |
| `meta` | `key` | Digest clock and counters |

`occurrence` in `fill_id` numbers rows that are identical on every other field within one walk.
Such rows share a block timestamp and every walk covers whole seconds, so the numbering is stable
across walks. No identical rows were seen in mintblade's full history (727 trades) or in either
fixture, but the index exists so that a genuine repeat is never collapsed.

## 6. The poll loop (pseudocode)

```text
on start:  migrate DB; mirror wallets; dispatcher.recover_inflight()
every interval (30 s +/- jitter):
    lag = status_check()                         # DATA PROBLEM if lag > 120 s or snapshot age > 300 s
    for wallet in wallets:
        st = poll_state[wallet]
        if st.watermark is None:                 # first ever poll = bootstrap baseline
            start = now - initial_backfill_hours;   mode = bootstrap
        else:
            start = st.watermark - overlap_seconds;  mode = live
            if --backfill-hours: start = min(start, now - N h)
            if now - st.watermark > gap_horizon: health.problem(wallet, "gap")    # flagged, never skipped
        try:
            for page in walk(/v2/activity, start..now+1d, ASC, follow next_cursor until null):
                validate envelope and every row        # else raise DataError(schema)
                insert fills (INSERT OR IGNORE by fill_id)   # facts persist even if a later page fails
            watermark = max(st.watermark, server_Date_of_first_page - max(30 s, lag))
            mark success; health.resolve(wallet, poll_failure, gap)
        except DataError as e:                     # timeout | connection | http_error | rate_limited | schema
            mark failure (watermark untouched); health.problem(wallet, poll_failure, e)
            # DATA PROBLEM after 2 consecutive failures (schema: immediately); renotify hourly
        except Exception as e:                     # bug: recorded as poll_failure/internal, never swallowed
            same as above
    group unassigned fills into bets
    for bet in bets needing evaluation (freshest first, <= 10 enrichments per cycle):
        skip       if side not alerted (sells, merges, redeems are recorded only) or below min_usdc
        suppress   if bootstrap-only, older than max_alert_age, or the wallet hit its hourly alert cap
        otherwise  enrich (fresh book etc.), label NEW BET DETECTED / COPY-CANDIDATE,
                   INSERT alert (UNIQUE dedupe_key "bet:<id>") + pending deliveries
    stale check (no success for 5 intervals -> DATA PROBLEM); digest every 24 h
dispatcher (separate thread): for due deliveries: rate-limit -> mark 'sending' -> send ->
    'sent' | retry with exponential backoff | 'failed' after max_attempts (+ DATA PROBLEM on other channels)
```

## 7. Deduplication, idempotency and delivery semantics

* **Fills:** deterministic `fill_id` plus `INSERT OR IGNORE`. Re-polling overlapping windows (the
  default overlap is 600 s on every poll) never creates duplicates (tested over five overlapping polls).
* **Bets:** each fill is attached once and the assignment is persisted, so bet ids never change.
  A late-ingested fill inside an existing bet's span extends that bet. Existing bets are never merged,
  so alerts already sent stay consistent with the stored data.
* **Alerts:** `UNIQUE dedupe_key` (`bet:<bet_id>`). Re-evaluation, restarts and overlapping polls
  cannot create a second alert for the same bet. Alerting reads state from the DB rather than from
  "rows new in this poll", so fills stored by a poll that failed halfway are still alerted on later (tested).
* **Deliveries: at-least-once by default.** The delivery row is committed as `sending` *before* the
  network call and as `sent`/`pending`/`failed` after it. If the process dies in between, the outcome
  is unknown. On restart, `at_least_once` re-sends it with a visible
  **"[POSSIBLE DUPLICATE: a previous send … outcome is unknown]"** marker. A missed bet alert is worse
  than a labelled duplicate. `delivery_semantics: at_most_once` marks it `unknown`, never re-sends it,
  and records a `delivery_unknown` health event (also raised as a DATA PROBLEM on the other channels),
  so a possible loss is never silent. The file channel writes `alert_id` and `dedupe_key` on every
  line, so consumers can deduplicate.

## 8. Outage recovery

* The watermark advances only after a complete walk. **Any** failure (HTTP error, timeout, schema
  surprise, failure on page 37 of 40, internal bug) leaves it untouched, so the next poll starts
  from the same place.
* The watermark comes from the server's clock (the HTTP `Date` of the first page) minus
  `max(ingest_safety_seconds, /v2/status lag)`, so local clock skew cannot move it forward. Each
  poll re-reads `overlap_seconds` (600 s) before it. That is the maximum ingestion delay tolerated.
  A `/v2/status` lag above the threshold is reported, and widens the margin.
* On restart, polling resumes from the stored watermark. If the gap exceeds `gap_horizon_hours`
  (6 h), the backfill is still **complete** (all pages, no cap other than `max_pages_per_poll`,
  which raises an error rather than truncating). The gap is flagged as a DATA PROBLEM ("backfilling
  completely from …") and closed with "DATA RECOVERED … Backfill complete: N rows read, M new fills".
* Bets found while backfilling that are older than `max_alert_age_minutes` (6 h) are stored as
  `suppressed` alerts with the reason. Newer ones alert with a **DELAYED** line and their true
  detection lag. Tested end to end: a crash, a months-long outage and a restart.

## 9. Bet grouping

Same wallet, condition, outcome token and side; consecutive fills at most `grouping.gap_minutes`
(10) apart. A BUY run that starts more than the gap after an earlier BUY run on the same outcome is
a separate event, labelled **addition to position**. A BUY with no earlier run in the DB is
`new_position`. It is upgraded to `addition` if `/v2/positions` shows holdings beyond the bet
(bought before monitoring began). SELL runs are `reduction`. SPLIT, MERGE, REDEEM and CONVERSION
are recorded, grouped and summarised in the digest, but only `alerting.alert_sides` (default
`[BUY]`, overridable per wallet) alert. Thresholds (`min_usdc`) apply to the whole bet: a $5 test
fill does not alert, but the bet alerts once its cumulative spend crosses the threshold. Each bet
alerts once; later growth shows in the DB and the digest.

## 10. Alert contents and definitions

| Field | Definition |
|---|---|
| Market question / event title / outcome / link | Gamma `question`, `events[0].title`, the bet's outcome. Link: `https://polymarket.com/event/<event_slug>/<market_slug>` (event URL if no market slug) |
| Executed (UTC) | Block timestamps of the bet's first and last fill |
| Detected (UTC), detection lag | `first_seen_at` of the bet's newest fill, and that minus its block timestamp: Data API ingestion plus polling delay. `signal_age_s` (payload) = alert time − first fill |
| Spent / shares / avg price | Σ`usdc_size` (fee-inclusive cash), Σ`size`, Σ(size·price)/Σsize (fee-exclusive). Effective price incl. fees = spent / shares |
| Maker/taker split | Fee embedded ⇒ taker; the remainder is checked against `/v2/trades` (taker-only) for the bet window, where absent ⇒ maker; `unknown` if the check fails |
| Book snapshot | CLOB `/book` fetched at alert time: best bid/ask, spread (cents), depth within 1c and 5c of the touch on both sides (shares and USD) |
| Price deterioration | BUY: `best_ask − avg_fill_price`, in cents and as % of the average (SELL: `avg − best_bid`). Positive = a follower pays more than the wallet did |
| Follower taker fee | `rate × (p(1−p))^exponent` per share at the best ask, from the market's Gamma `feeSchedule` (category table fallback). Shown per share in cents, as % of notional, and in $ for `follow_usd` ($100). Exponent ≠ 1 (one legacy market) is flagged, see `notes/platform/fees_incentives.md` |
| Exposure | `/v2/positions` (OPEN) for this condition (shares on this outcome, value, cost) and for the Gamma event id (value across N markets) |
| Market state | CLOB `closed`/`accepting_orders`/`seconds_delay` (not cached) over Gamma's (cached up to 300 s); `gameStartTime`. **In-play** = `event.live`, or `gameStartTime` has passed and the event has not ended |
| Cluster | `cluster_id`, `cluster_confidence`, `cluster_note` from config |
| Why it qualified | e.g. "BUY bet of $1,221.42 ≥ min_usdc $20.00; addition to an existing position …" |

Enrichment failures do not drop the alert. The failing component is listed, a DATA PROBLEM
episode is recorded for that source, and any copy-candidate rule that needs the missing data
fails closed.

## 11. NEW BET DETECTED vs COPY-CANDIDATE

* **NEW BET DETECTED**: pure observation that executed fills exist. Every alert carries
  *"INFORMATIONAL ONLY: no copy signal has been validated by this research. Not a trading recommendation."*
* **COPY-CANDIDATE**: only if `copy_candidate.enabled: true` **and** every rule passes: detection
  lag ≤ 60 s, deterioration ≤ 1c, spread ≤ 2c, ask depth within 1c ≥ $500, follower fee ≤ 2%,
  not in-play, accepting orders, optional minimum cluster confidence. Missing data fails a rule. The
  label text still says the rules are the user's own, and that no copy signal has been validated.
  **The shipped config has `enabled: false`.**

## 12. Health: DATA PROBLEM vs "no new trades"

* A successful poll that returns nothing is **"ok, no new trades"**: state advances, no notification.
* **DATA PROBLEM** notifications (a separate kind from bet alerts) cover HTTP errors, timeouts,
  connection failures, 429s, schema surprises (missing fields, wrong types, wrong wallet, unexpected
  type, non-JSON, `has_more` without a cursor, repeated cursor, page cap), `/v2/status` lag above
  threshold or a stalled snapshot, a wallet with no successful poll for 5 intervals, monitoring
  gaps, enrichment failures, and permanent delivery failures (sent on the other channels).
  A DATA PROBLEM fires after 2 consecutive failures, or immediately for schema problems and gaps.
  It repeats hourly while the problem continues, and a **DATA RECOVERED** follows when it clears.
  Each message says the state was not advanced, and gives the last confirmed watermark.
* **Digest/heartbeat** every 24 h: wallets, polls ok/failed, fills by type, bets by kind, alerts by
  label, suppressed alerts, delivery failures, problems opened and still open, most stale wallet,
  and a summary of sells/merges/redeems.
* **Flood control:** at most 10 enrichments per cycle, freshest first. The rest wait (not dropped).
  At most 30 alerts per wallet per hour. Beyond that, bets are stored as suppressed and one
  **ALERT CAP** notice is sent. This was added after a live test on two high-frequency wallets
  produced 762 BUY bets in 15 minutes.

## 13. Notifiers

| Channel | Default | Setup |
|---|---|---|
| console | on | stdout |
| file | on | `alerts/out/alerts.ndjson`: one JSON object per line (`alert_id`, `dedupe_key`, `label`, `text`, `payload`). Not `.jsonl`, which the repo ignores |
| Telegram | off | `PM_ALERT_TELEGRAM_BOT` (bot credential from @BotFather), `PM_ALERT_TELEGRAM_CHAT` (chat id). Plain-text `sendMessage` over HTTPS, 20/min |
| email | off | `PM_ALERT_SMTP_HOST`, `PM_ALERT_SMTP_PORT` (587), `PM_ALERT_SMTP_USER`, `PM_ALERT_SMTP_PASSWORD`, `PM_ALERT_SMTP_FROM`, `PM_ALERT_SMTP_TO`; STARTTLS (or `PM_ALERT_SMTP_SSL=1`) |

Credentials are read **only** from environment variables. They are never written to the config,
database, output file or logs, and they are scrubbed from error text (the Telegram API puts the
bot credential in the URL path, and `requests` errors echo URLs; tested). Enabling a channel
without its variables is a startup error that names the variables, never their values. Each channel
has a token-bucket rate limit, exponential backoff (5 s doubling to 600 s, 8 attempts), and honours
Telegram's `retry_after`. Delivery runs on its own thread, so a hung SMTP server cannot delay polling.
No real Telegram or email message was sent while building this; both were tested against fakes.

## 14. Latency expectations

Measured on 2026-10-17 (around 15:10–15:50 UTC, short windows, one day; reproduce with
`python analyses/alerts_latency/measure_latency.py`):

| Stage | Measured | Source |
|---|---|---|
| CLOB match → block timestamp | median 2.27 s, p90 2.94 s (n = 397) | `notes/platform/mechanics.md` §3.6 |
| Block timestamp → visible in Data API (polled every 1–4 s, cache-busted) | two runs: global `/v2/trades` p50 3.4–3.5 s, p90 5.3–5.5 s, max 5.5 s (n = 1,323 / 1,429); `/v2/activity?user=` p50 2.6–2.7 s, p90 4.6–4.7 s, max 5.0 s (n = 227 / 183) | this build (includes ≤ 1 s of sampling delay and integer-second truncation) |
| CDN cache if *not* cache-busted | up to 15 s (activity), 300 s (trades, Gamma) | response headers |
| Poll phase at 30 s ± 5 s | uniform 0–35 s, mean ≈ 15 s | config |
| Enrichment (5–7 requests) | ≈ 3 s in the live run (detected 15:45:19, alert built 15:45:22) | live smoke test |
| Public RTDS websocket (see §16) | arrives ≈ at block time (two runs: p50 0.0 / +0.03 s, range −0.9 to +1.2 s, n = 244 / 221), about 3 s before Data API visibility | this build |

**Expected block → alert with 30 s polling:** median ≈ 20 s, p90 ≈ 35 s, worst ≈ 45 s, plus
≈ 2.3 s from the match. Telegram delivery adds about a second (PLAUSIBLE, not measured). A
5-minute cron gives a median of about 2.5 min before scheduler delay. An hourly cron gives about
30 min. `notes/platform/data_infrastructure.md` did not exist when this was written; if it is
added, prefer its numbers where they differ.

## 15. Running continuously (nothing here is set up)

Prompt alerts need a process running **continuously** (the loop mode), plus the SQLite file on
persistent disk. `--once` gives single runs; the state carries over between runs, so periodic runs
are safe but only as fresh as their schedule.

| Option | Cost | Fit |
|---|---|---|
| Home machine / Raspberry Pi with systemd | hardware you own | Best free option. 30 s polling, restart on failure, the DB on local disk. Downtime only when the machine or network is down, and the gap is backfilled and flagged on return |
| Small VPS (any provider) | paid, roughly a few $/month (**not deployed**) | Same as above, with better uptime. Put credentials in the unit's `EnvironmentFile` (chmod 600), never in the repo |
| GitHub Actions cron | free tier | Best-effort only. Minimum interval 5 min, and scheduled runs are often delayed or dropped under load. The SQLite state must persist between runs (e.g. `actions/cache`), or every run re-bootstraps. Credentials go in repository secrets. Use `--once`; exit code 3 marks data problems |

Example systemd unit (documentation only, not installed):

```ini
# /etc/systemd/system/pm-alerts.service
[Unit]
Description=Read-only Polymarket bet alerts
After=network-online.target
[Service]
WorkingDirectory=/home/pi/Momemtum-Quality-Strategy/polymarket_research
ExecStart=/usr/bin/python3 -m alerts.run --config alerts/config.local.yaml
EnvironmentFile=/etc/pm-alerts.env
Restart=always
RestartSec=30
[Install]
WantedBy=multi-user.target
```

**Why an hourly cron is too slow for in-play signals.** At an hourly schedule the expected detection
delay is about 30 minutes (uniform 0–60). In-play prices reprice within seconds of game events. A
soccer half lasts 45 minutes, and 5-minute crypto up/down markets resolve long before the next run.
Sports markets also impose a 1–3 s `secondsDelay` on taker orders (`notes/platform/mechanics.md`
§3.4). By the time an hourly run sees a bet, the book snapshot no longer says anything about the
price the wallet got, and the opportunity, if there ever was one, is gone. Hourly runs are fine for
the digest and for research logging, not for in-play alerts.

## 16. Optional websocket upgrade path

A public, unauthenticated stream exists. **RTDS** at `wss://ws-live-data.polymarket.com`, with
subscription `{"action":"subscribe","subscriptions":[{"topic":"activity","type":"trades"}]}`,
streams *all* trades (about 55 messages/s) with `proxyWallet` (checksum case), `side`, `size`,
`price`, `fee`, `conditionId`, `asset`, `outcome`, `slug`, `eventSlug`, `transactionHash` and
`timestamp`. Verified 2026-10-17: it worked, it arrived about 3 s before Data API visibility, and
all sampled trades (244 and 221 in two runs) later appeared in the Data API. Its documentation status and SLA were
**not** verified. Messages arrive at about block time and may precede final settlement. Unfilled
orders are still invisible. The CLOB `market` websocket has no wallet identity, and the `user`
channel needs trading credentials, so neither applies.

Suggested design (not implemented): a websocket task filters messages by
`proxyWallet.lower() in monitored`, and on a match triggers an immediate Data API poll of that
wallet. The Data API stays the source of truth for storage, dedupe and alert content. The 30 s
poll stays as the fallback, so a dropped socket degrades latency, not correctness. Reconnect with
backoff, and raise a DATA PROBLEM if the socket stays down. Expected gain: about 3 s of ingestion
plus the whole polling phase, so median block → alert falls from about 20 s to about 5 s.

## 17. Operational runbook

* **First run:** copy `config.example.yaml` to `config.local.yaml` (git-ignored), edit the wallets
  and thresholds, then run `--once`. The first poll of a wallet is a baseline: history in the last
  `initial_backfill_hours` is stored but not alerted (`alert_on_bootstrap: false`).
* **Health check:** `--report` shows each wallet's watermark, last success, consecutive failures,
  delivery counts and open problems, without touching the network.
* **DATA PROBLEM received:** `--report`, then read `poll_state.last_error`. A timeout or 5xx usually
  clears by itself. Watch for DATA RECOVERED. `schema` means the API changed: compare a fresh payload
  with `sources.ACTIVITY_REQUIRED`, update, and re-record fixtures
  (`python -m alerts.tests.record_fixtures`). `status_lag` is a Polymarket-side delay; alerts will
  arrive late but complete. `stale` means a wallet has not polled successfully for 5 intervals.
* **After downtime:** just start it again. The gap is backfilled from the watermark and flagged.
  To re-read further back (idempotent), use `--backfill-hours N`.
* **Changing wallets:** edit the config. Removed wallets are disabled, not deleted. A new wallet
  starts with a baseline poll.
* **Credentials:** export the variables in the service environment only. To rotate the Telegram
  credential, revoke it in @BotFather and update the variable. Nothing in the DB needs changing.
* **Data API v1 retirement (2026-10-24):** not affected; only `/v2/*` is used.
* **Backups and size:** the DB is one file (`alerts/out/alerts.sqlite`, git-ignored, WAL mode).
  Copy it while stopped, or use `sqlite3 … ".backup"`. `fills.raw_json` is about 0.6 KB per fill. A
  wallet with about 100 fills a day grows about 20 MB a year.
* **Clock:** keep NTP on. Detection lag uses the local clock; the watermark uses the server's.
* **Stopping:** Ctrl-C or SIGTERM stops after the current cycle. The dispatcher flushes for up to
  10 s. Anything unsent stays pending for the next start.

## 18. Tests

`python -m pytest alerts/tests -q`: **108 tests, about 7 s, no network** (67 from the build, 39 from the
adversarial review in `test_review.py` and `test_review_round2.py`, 2 from the live smoke test in
`test_smoke_findings.py`, see §20). Fixtures in
`alerts/tests/fixtures/` were recorded from the live API on 2026-10-17 by
`python -m alerts.tests.record_fixtures`. They are mintblade activity (trimmed to 88 rows: four
complete bets, 30 fills of the large IR Iran bet, and all five redeems), a second anonymous active
wallet's full history (102 rows with buys, sells, additions, merge, split and redeems; profile
fields blanked), a genuine 3-page cursor walk, `/v2/status`, a 400 error envelope, Gamma closed
and open markets, CLOB market state, a live book, a 404 book, positions, and the taker-only trades
set. `FakeApi` in `conftest.py` implements the verified Data API semantics over those rows, and
injects timeouts, HTTP errors and schema surprises.

Covered: dedupe across overlapping polls; grouping into bets, additions after the gap, a
configurable gap, late fills, thresholds on cumulative spend; sells, merges and redeems recorded
without buy alerts; restart after a long outage with complete paginated backfill and gap flagging;
failures that never advance state, with DATA PROBLEM / renotify / RECOVERED; schema surprises;
failure mid-pagination; "no new trades" vs failure; `/v2/status` lag; stale wallets; idempotent
sending; at-least-once and at-most-once crash recovery; retry/backoff and permanent failure;
rate limits; Telegram and email (fakes) with credential scrubbing; enrichment math (depth,
deterioration, fee vs `pmr.fees`); market state and in-play; exposure; copy-candidate rules;
enrichment failure fails closed; flood control; digest; CLI `--once`, `--report`, loop and exit codes.

## 19. Known limitations

* Polling latency (§14). The websocket upgrade is designed, not built.
* Only executed fills are visible (§3). Partial fills of a larger resting order look like a smaller bet.
* Maker/taker labels depend on the `/v2/trades` cross-check (two extra calls per alert, run for every
  BUY/SELL bet since review round 2). If it fails or the index has not caught up, fee-free fills stay
  `unknown` and fee-embedded fills keep an unconfirmed `taker` label (the basis line says so).
* `overlap_seconds` (600 s) is the maximum ingestion delay tolerated. A row ingested later than
  that, while `/v2/status` reports no lag, would be missed. `/v2/status` lag above 120 s widens the margin.
* Exposure comes from `/v2/positions` (custody balances) and may lag the fills by a few seconds.
  It excludes Combos and Perps.
* Gamma metadata is CDN-cached for up to 300 s. Closed and accepting-orders flags come from the CLOB
  instead, but `event.live` and `gameStartTime` come from Gamma.
* Cluster labels in the example config are placeholders. They are based only on profile creation
  times in CONTEXT.md and should be updated from `notes/wallets/`.
* One process per DB is enforced by an exclusive `flock` on `<db>.lock` (exit code 4); `--report`
  is exempt. The lock is advisory and local: it does not protect a DB on a network filesystem
  shared between machines.

## 20. Review (adversarial, 2026-10-17 and 2026-10-18)

The review tried to make the monitor **miss** a trade, **duplicate** an alert, **silently skip**
activity after an outage, report a data failure as "no new trades", **leak** a credential, or
**misreport** a price, side or role. For every real issue a failing test was written first, then the
code was fixed. Tests named `test_probe_*` document behaviour that was already correct.
Round 1 (`tests/test_review.py`) was interrupted by a usage limit and committed part-way (two of its
tests still failed). Round 2 (`tests/test_review_round2.py`) finished it and continued.
Result: `python -m pytest alerts/tests -q`, **106 passed**, pyflakes clean (108 after the smoke-test fix S1 below).

### 20.1 Issues found and fixed

| # | Failure mode | What went wrong | Fix |
|---|---|---|---|
| R1.1 | miss | A local clock days behind (Pi without RTC) put the window's `end` (local now + 1 d) before the newest rows while the watermark (server `Date`) moved past them | `clock.py` `ServerClock`: every block-time decision uses the server's clock; skew above `max_clock_skew_seconds` is a health event |
| R1.2 | silent skip | A local clock hours *ahead* suppressed fresh bets as "too old" and inflated detection lag | same `ServerClock` |
| R1.3 | misreport | Gamma ignoring `condition_ids` would put another market's question, fees and in-play state on the alert | the response must contain the requested `conditionId`, otherwise it is a schema error |
| R1.4 | misreport | A `/book` for another token would be shown as the traded outcome's book | `asset_id` must equal the traded token |
| R1.5 | blocked alerts | A malformed Gamma field raised out of `enrich()`; the bet stayed queued and crashed every cycle | each enrichment component is isolated and fails closed |
| R1.6 | misreport (maker/taker) | Absence from the taker-only feed was read as "maker" even when `/v2/trades` had not yet ingested the fills | "maker" only once `taker_only=false` contains every fill of the bet; otherwise `unknown` |
| R1.7 | leak | `--log-level DEBUG` printed the Telegram bot credential (urllib3 logs `POST /bot<credential>/sendMessage`) | `logsafe.py` redacting formatter (plain, URL-quoted and key-part forms) on the root handler, installed by `run.configure_logging` (round 2 wrote this; round 1 left only the test) |
| R1.8 | silent loss | A delivery left in `sending` after a failed outcome write stayed stuck until restart | in-process lease (`max(60 s, 3 x send timeout)`), then re-sent as POSSIBLE DUPLICATE |
| R1.9 | silent loss | 8 attempts with 5..600 s backoff gave up after ~14 min, so a 30-min internet outage dropped queued alerts | retry until **both** `max_attempts` and `give_up_after_minutes` (360) are exhausted. Round 2: the test itself was broken (its token bucket ran on real `time.monotonic` inside a simulated hour); fixed |
| R1.10 | silent loss | A delivery-failure notice for the only channel had no channel at all | it is queued on that channel |
| R1.11 | "no new trades" | A degraded backend answering 200 `data: []` looked like a quiet wallet and the watermark advanced | **canary**: every window reaches back to stored rows and must return at least one; otherwise `incomplete_data` DATA PROBLEM |
| R1.12 | "no new trades" | A signer/EOA or a typo'd valid-looking address returns 200 `[]` forever | full-history probe at bootstrap; `no_history` warning |
| R1.13 | misreport | Trades made while the first (bootstrap) polls were failing were treated as baseline | `first_attempt_at`: fills after the first *attempt* are live |
| R1.14 | miss | A `/v2/status` outage dropped the safety margin to 30 s | the last known lag is kept |
| R1.15 | miss/stall | A walk that cannot finish in one poll (page cap, expired cursor, late-page error) restarted from the same watermark forever | checkpoint to one second before the newest row of the last page that had a successor |
| R1.16 | duplicate | A cursor page re-serving rows from before its anchor became phantom "repeat" fills | the ASC walk must be non-decreasing in block time, else schema error |
| R2.1 | duplicate | Overlapping cron `--once` runs, or a manual `--once` beside the loop: each startup `recover_inflight()` re-queued the *other* process's in-flight send | `instance.py`: exclusive non-blocking `flock` on `<db>.lock`, exit code 4; `--report` exempt. Verified live: the second process exits 4 |
| R2.2 | duplicate | A Telegram read timeout (request sent, reply lost) was retried **without** the POSSIBLE DUPLICATE marker. Under `at_most_once` it was re-sent anyway | `NotifyError.outcome_unknown`: re-sent marked (at_least_once), or marked `unknown` plus a `delivery_unknown` health event (at_most_once) |
| R2.3 | duplicate | SMTP: the server accepted the message but `QUIT` failed (421) and the email was re-sent every retry | an error after `send_message` returned counts as delivered (logged). A disconnect or timeout during DATA is `outcome_unknown` |
| R2.4 | blocked/silent | Any exception while building *one* alert (render, rules, store) escaped `evaluate_bets`: the cycle aborted before every older bet, the stale check and the digest, on every cycle, and was only logged | per-bet isolation: a plain **fallback alert** from stored facts (`[ALERT RENDERING FAILED]`) plus an `engine/evaluation` problem. `run_cycle` isolates each stage; internal errors become `engine/cycle_failure` (DATA PROBLEM after 2 cycles, then RECOVERED) and make `--once` exit 3 |
| R2.5 | misreport (side) | The outcome came only from the Data API row label. A mislabel would show "Yes" for a NO purchase, and unlabelled rows (`outcome_index: 999`) showed "Outcome: None" | Gamma's parallel `clobTokenIds`/`outcomes` lists map the traded token to its outcome. Gamma's name is shown; a disagreement or a token that is not one of the market's is reported in the alert (`outcome_data_api` and `outcome_gamma` kept in the payload) |
| R2.6 | misreport (maker/taker) | "Fee embedded ⇒ taker" was confirmed only when the bet also had a fee-free fill. Builder fees can be charged to makers (data_infrastructure.md pitfall 16) | the `/v2/trades` cross-check runs for every BUY/SELL bet. A fee-embedded fill missing from a complete taker feed becomes `unknown`. Verified live: two real bets confirmed as taker |
| R2.7 | silent skip | After an outage, qualifying bets older than `max_alert_age_minutes` were stored as suppressed **with no channel**: the user saw DATA RECOVERED and nothing about the bets | one **BACKFILL SUMMARY** notice per cycle listing them (wallet, side, outcome, market, spend, size, avg, times; at most 10 lines). Idempotent |
| R2.8 | miss (loud) | One row failing validation (for example a TRADE with no outcome token, as a new product could produce) failed every poll of that wallet until the code changed, so all its later trades were missed | invalid rows are **quarantined** (`rejected_rows`, migration 3) and each new one is reported with its facts. A walk in which *no* row is valid is still a hard schema failure (probe test) |
| R2.9 | miss (loud) | The bootstrap probe still raised on a malformed newest row, so such a dormant wallet failed bootstrap forever | that row is quarantined and the wallet polls on without a canary |

| S1 | misreport / noise | Live smoke test 2026-10-18 (`notes/alerts_smoke_test.md`): **Combo** fills (`is_combo: true`, synthetic condition id, title "A AND B") went through normal enrichment. `/v2/positions` answered 400 "invalid condition id" (a DATA PROBLEM health event per combo bet), CLOB `/book` 404 was shown as "market closed or not tradable", and the fee-free fill was labelled **maker** because combo fills never appear in the taker-only `/v2/trades` feed (0 of 6 live) | `enrich.is_combo` + `Enricher._enrich_combo`: no lookups, roles stay unknown (fee-embedded = taker, unconfirmed), the alert says `[COMBO: multi-leg RFQ position …]` and why book/fee/exposure are unavailable. Test `test_smoke_findings.py` (fails without the fix) |

### 20.2 Probed and found correct (no change)

* **`start` inclusive vs exclusive.** Windows reach back to `canary - 1` and overlap 600 s, so an exclusive `start` would lose nothing.
* **Same-second fills, many fills in one tx, true identical repeats across a page boundary.** The occurrence index is per walk and walks cover whole seconds, so ids are stable.
* **Cursor pages re-send every filter.** An expired or invalid cursor (400) fails only that walk; cursors are never reused across polls, and the checkpoint keeps progress.
* **`has_more` without `next_cursor`, a repeated cursor, page-cap overflow.** All are schema errors. A walk is never silently truncated.
* **Gamma for closed markets.** An empty open lookup is retried with `closed=true`. CLOB `closed`/`accepting_orders` (not CDN-cached) take precedence.
* **Neg-risk markets.** The book fetched is the traded token's (for example the NO token of a neg-risk outcome) and `neg_risk` is shown.
* **Data API v1 retirement (2026-10-24).** Every Data API call is `/v2/*`, both in `alerts/` and in `analyses/alerts_latency/` (test `test_probe_only_v2...`). Nothing changes on that date.
* **SPLIT/MERGE/REDEEM/CONVERSION rows.** They carry empty strings, not nulls, in `token_id`/`side`/`outcome` (checked against `data/derived/activity_types_probe_20261017T1558.json`), so they pass validation.
* **Negative `overlap_seconds` / `ingest_safety_seconds`.** Already rejected by the config's generic non-negative check.

### 20.3 Remaining limitations (not fixed)

* **Phantom duplicates are detected, not prevented.** If the API re-served a row at the *same* second across a page boundary, the walk cannot tell it from a true repeat (rows carry no sequence id). The next overlapping re-read reports it as a `vanished_rows` warning, but the size may already be in an alert.
* **Ambiguous sends are inherent.** A ConnectionError after the request left the machine is still treated as "not sent". Telegram 5xx is retried without the duplicate marker.
* **The builder-fee premise is PLAUSIBLE, not VERIFIED for the Data API.** The docs say makers can pay builder fees. Whether `usdc_size` on the Data API includes them was not verified, so R2.6 is a safeguard. The cross-check costs two `/v2/trades` calls per alert, and while the index lags the label stays an unconfirmed `taker`.
* **The outcome cross-check depends on Gamma.** If Gamma is down or does not list the market, the Data API label is shown unverified, and the alert's enrichment-errors line says Gamma failed.
* **Quarantined rows are reported, not interpreted.** A trade in a format this code cannot parse produces a DATA PROBLEM with its raw facts, never a bet alert. If many rows break at once (and some rows still parse), there is one such message per poll.
* **One process per DB on one machine.** The lock is a local `flock`; it does not protect a DB on a network filesystem shared by two hosts.
* **A dead database cannot report itself.** If SQLite itself fails (disk full, I/O error), health events cannot be written, so the failure is only in the log (with traceback), and `--once` exits 3.
* **Health-episode race (theoretical).** `HealthMonitor.problem` reads the open episode before taking the write lock. Two connections raising the same (scope, kind) at the same moment could open two episodes, which means two notices. In practice the engine and the dispatcher thread use disjoint scopes, and the instance lock rules out a second process.
* All limitations in §19 still apply (polling latency, executed fills only, 600 s maximum ingestion delay, CDN-cached Gamma metadata, placeholder cluster labels).

### 20.4 Verification

* `python -m pytest alerts/tests -q`: 106 passed, about 7 s, no network (108 after S1). `pyflakes alerts analyses/alerts_latency`: clean.
* Live, read-only smoke on 2026-10-18 (`--dry-run`; DBs, logs and alert file under `data/derived/alerts_smoke/`, which is git-ignored):
  * The example config with `--backfill-hours 2000`: the three dormant wallets bootstrap via the history probe; the second cycle re-reads each canary row ("ok, no new trades", exit 0).
  * While a lock was held, a second `--once` process exited 4 and `--report` still worked.
  * Two active public wallets with `alert_on_bootstrap`: 2 bet alerts, 1 ALERT CAP notice, 6 deliveries, 0 enrichment errors. The Data API and Gamma outcome labels agreed ("Under"), and the cross-check confirmed both bets as taker.
* No Telegram or email message was sent; those channels were exercised only against fakes. Nothing was deployed, and no monitoring is running.
* A fuller live smoke test (history reconstruction of the three candidate wallets, 17 min on three busy wallets, a 5-minute outage checked against an independent `/v2/trades` pull) is in `notes/alerts_smoke_test.md`.
