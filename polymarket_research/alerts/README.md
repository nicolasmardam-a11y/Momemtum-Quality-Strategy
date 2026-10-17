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
python -m pytest alerts/tests -q                                         # 67 tests, no network
```

Flags: `--once`, `--backfill-hours N` (the first cycle re-reads at least N hours, idempotently),
`--db PATH`, `--interval S`, `--max-cycles N`, `--dry-run` (console and file only, even if
Telegram or email are enabled), `--report`, `--log-level`. Exit codes: 0 means all polls were OK,
2 means a configuration error, 3 means a `--once` run hit at least one data problem (useful under cron).

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
`run.py` (CLI). The shared research client `pmr` is reused for pure functions:
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

`python -m pytest alerts/tests -q`: **67 tests, about 5 s, no network.** Fixtures in
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
* Maker/taker labels for fee-free markets depend on the `/v2/trades` cross-check (one extra call per
  alert). If it fails, those fills stay `unknown`.
* `overlap_seconds` (600 s) is the maximum ingestion delay tolerated. A row ingested later than
  that, while `/v2/status` reports no lag, would be missed. `/v2/status` lag above 120 s widens the margin.
* Exposure comes from `/v2/positions` (custody balances) and may lag the fills by a few seconds.
  It excludes Combos and Perps.
* Gamma metadata is CDN-cached for up to 300 s. Closed and accepting-orders flags come from the CLOB
  instead, but `event.live` and `gameStartTime` come from Gamma.
* Cluster labels in the example config are placeholders. They are based only on profile creation
  times in CONTEXT.md and should be updated from `notes/wallets/`.
* Rate limiting of notifications is per process. Two copies running against one DB would share
  alerts (each dedupe key is unique) but not rate-limit budgets. Run one instance.
