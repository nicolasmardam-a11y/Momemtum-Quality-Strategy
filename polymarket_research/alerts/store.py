"""SQLite storage (stdlib sqlite3) with idempotent, versioned migrations.

Times: ``*_ts`` columns are on-chain block timestamps (integer epoch seconds, UTC);
``*_at`` columns are local wall-clock times (float epoch seconds, UTC).

Each thread must use its own Store (sqlite connections are not shared across
threads); WAL mode lets the poll loop and the notification dispatcher work
concurrently on the same file.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

MIGRATIONS: list[tuple[int, str]] = [
    (1, """
CREATE TABLE IF NOT EXISTS wallets (
    address            TEXT PRIMARY KEY CHECK (address = lower(address)),
    label              TEXT NOT NULL,
    cluster_id         TEXT,
    cluster_confidence TEXT NOT NULL DEFAULT 'none'
                       CHECK (cluster_confidence IN ('confirmed', 'probable', 'weak', 'none')),
    cluster_note       TEXT,
    thresholds_json    TEXT NOT NULL DEFAULT '{}',
    enabled            INTEGER NOT NULL DEFAULT 1,
    updated_at         REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS fills (
    fill_id        TEXT PRIMARY KEY,      -- sha256(wallet|tx|asset|side|size|price|ts|type|occurrence)
    wallet         TEXT NOT NULL,
    activity_type  TEXT NOT NULL,         -- TRADE, SPLIT, MERGE, REDEEM, CONVERSION, ...
    tx_hash        TEXT NOT NULL,
    condition_id   TEXT NOT NULL,
    token_id       TEXT NOT NULL,
    outcome        TEXT,
    outcome_index  INTEGER,
    side           TEXT NOT NULL,         -- BUY/SELL for trades, '' for other activity
    size           REAL NOT NULL,         -- shares
    price          REAL NOT NULL,
    usdc_size      REAL NOT NULL,         -- cash moved, includes the taker fee on taker fills
    ts             INTEGER NOT NULL,      -- block timestamp
    title          TEXT,
    market_slug    TEXT,
    event_slug     TEXT,
    liquidity_role TEXT NOT NULL DEFAULT 'unknown',  -- taker | maker | unknown
    fee_usdc       REAL,
    bet_id         TEXT,
    first_seen_at  REAL NOT NULL,         -- when this system first stored the row
    poll_mode      TEXT NOT NULL DEFAULT 'live',     -- live | bootstrap
    raw_json       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS fills_wallet_ts ON fills (wallet, ts);
CREATE INDEX IF NOT EXISTS fills_bet ON fills (bet_id);
CREATE INDEX IF NOT EXISTS fills_unassigned ON fills (ts) WHERE bet_id IS NULL;

CREATE TABLE IF NOT EXISTS bets (
    bet_id        TEXT PRIMARY KEY,       -- fill_id of the bet's first fill
    wallet        TEXT NOT NULL,
    condition_id  TEXT NOT NULL,
    token_id      TEXT NOT NULL,
    outcome       TEXT,
    side          TEXT NOT NULL,          -- BUY | SELL | SPLIT | MERGE | REDEEM | CONVERSION
    kind          TEXT NOT NULL,          -- new_position | addition | reduction | split | merge | redeem | conversion
    prior_bet_id  TEXT,
    first_ts      INTEGER NOT NULL,
    last_ts       INTEGER NOT NULL,
    n_fills       INTEGER NOT NULL,
    shares        REAL NOT NULL,
    notional_usdc REAL NOT NULL,          -- sum(size * price), fee-exclusive
    usdc_size     REAL NOT NULL,          -- sum(usdc_size), fee-inclusive for taker buys
    first_seen_at REAL NOT NULL,
    last_seen_at  REAL NOT NULL,
    live_fills    INTEGER NOT NULL DEFAULT 0,
    needs_eval    INTEGER NOT NULL DEFAULT 1,
    alert_state   TEXT NOT NULL DEFAULT 'none',      -- none | below_threshold | suppressed | alerted
    title         TEXT,
    market_slug   TEXT,
    event_slug    TEXT,
    updated_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS bets_key ON bets (wallet, condition_id, token_id, side, last_ts);
CREATE INDEX IF NOT EXISTS bets_eval ON bets (needs_eval) WHERE needs_eval = 1;

CREATE TABLE IF NOT EXISTS alerts (
    alert_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key        TEXT NOT NULL UNIQUE,
    kind              TEXT NOT NULL,      -- BET | DATA_PROBLEM | DATA_RECOVERED | DIGEST
    label             TEXT NOT NULL,      -- NEW BET DETECTED | COPY-CANDIDATE | DATA PROBLEM | ...
    wallet            TEXT,
    bet_id            TEXT,
    created_at        REAL NOT NULL,
    status            TEXT NOT NULL,      -- pending | sent | partial | failed | suppressed
    suppressed_reason TEXT,
    text              TEXT NOT NULL,
    payload_json      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    alert_id           INTEGER NOT NULL REFERENCES alerts (alert_id),
    channel            TEXT NOT NULL,
    status             TEXT NOT NULL,     -- pending | sending | sent | failed | unknown
    attempts           INTEGER NOT NULL DEFAULT 0,
    next_attempt_at    REAL NOT NULL,
    last_attempt_at    REAL,
    sent_at            REAL,
    last_error         TEXT,
    possible_duplicate INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (alert_id, channel)
);
CREATE INDEX IF NOT EXISTS deliveries_due ON deliveries (status, next_attempt_at);

CREATE TABLE IF NOT EXISTS poll_state (
    wallet               TEXT PRIMARY KEY,
    watermark_ts         INTEGER,         -- all rows with block ts <= watermark are believed observed
    last_seen_row_ts     INTEGER,         -- newest block ts ever observed for this wallet
    last_cursor          TEXT,            -- next_cursor of the last page fetched (NULL after a full walk)
    last_attempt_at      REAL,
    last_success_at      REAL,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_error           TEXT,
    bootstrapped_at      REAL,
    polls_ok             INTEGER NOT NULL DEFAULT 0,
    polls_failed         INTEGER NOT NULL DEFAULT 0,
    rows_seen            INTEGER NOT NULL DEFAULT 0,
    fills_new            INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS health_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    scope       TEXT NOT NULL,            -- wallet address, data-api, gamma, clob, notify:<channel>
    kind        TEXT NOT NULL,            -- poll_failure | status_lag | status_unavailable | stale | gap |
                                          -- enrichment | delivery | delivery_unknown
    error_class TEXT,                     -- timeout | connection | http_error | rate_limited | schema | ...
    severity    TEXT NOT NULL,            -- info | warning | error
    detail      TEXT NOT NULL,
    first_at    REAL NOT NULL,
    last_at     REAL NOT NULL,
    occurrences INTEGER NOT NULL DEFAULT 1,
    notified_at REAL,
    notify_count INTEGER NOT NULL DEFAULT 0,
    resolved_at REAL
);
CREATE INDEX IF NOT EXISTS health_open ON health_events (scope, kind) WHERE resolved_at IS NULL;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""),
]

SCHEMA_VERSION = MIGRATIONS[-1][0]


def split_sql(sql: str) -> list[str]:
    """Split a migration into statements (``--`` comments removed first, so a
    semicolon inside a comment cannot break a statement)."""
    lines = [ln.split("--", 1)[0] for ln in sql.splitlines()]
    return [st.strip() for st in "\n".join(lines).split(";") if st.strip()]


class Store:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 30000")
        if self.path != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self.migrate()

    # ------------------------------------------------------------------ plumbing

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """IMMEDIATE transaction: commits on success, rolls back on any exception."""
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")

    def migrate(self) -> int:
        """Apply pending migrations. Safe to call any number of times."""
        with self.tx() as c:
            c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)")
            have = {r[0] for r in c.execute("SELECT version FROM schema_migrations")}
            for version, sql in MIGRATIONS:
                if version in have:
                    continue
                for stmt in split_sql(sql):
                    c.execute(stmt)
                c.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, time.time()))
            c.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        return SCHEMA_VERSION

    def close(self) -> None:
        self.conn.close()

    def q(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def q1(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    # ------------------------------------------------------------------ meta

    def get_meta(self, key: str) -> str | None:
        r = self.q1("SELECT value FROM meta WHERE key = ?", (key,))
        return r["value"] if r else None

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                          "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (key, value))

    # ------------------------------------------------------------------ wallets

    def upsert_wallets(self, wallets: Iterable[Any], now: float) -> None:
        """Mirror the configured wallets; wallets dropped from the config are disabled, not deleted."""
        wallets = list(wallets)
        with self.tx() as c:
            c.execute("UPDATE wallets SET enabled = 0, updated_at = ?", (now,))
            for w in wallets:
                thresholds = {"min_usdc": w.min_usdc, "alert_sides": list(w.alert_sides) if w.alert_sides else None}
                c.execute(
                    """INSERT INTO wallets (address, label, cluster_id, cluster_confidence, cluster_note,
                                            thresholds_json, enabled, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT (address) DO UPDATE SET label = excluded.label, cluster_id = excluded.cluster_id,
                         cluster_confidence = excluded.cluster_confidence, cluster_note = excluded.cluster_note,
                         thresholds_json = excluded.thresholds_json, enabled = excluded.enabled,
                         updated_at = excluded.updated_at""",
                    (w.address, w.label, w.cluster_id, w.cluster_confidence, w.cluster_note,
                     json.dumps(thresholds), int(w.enabled), now))

    # ------------------------------------------------------------------ poll state

    def poll_state(self, wallet: str) -> sqlite3.Row | None:
        return self.q1("SELECT * FROM poll_state WHERE wallet = ?", (wallet,))

    def mark_poll_success(self, wallet: str, *, watermark_ts: int, last_seen_row_ts: int | None, now: float,
                          rows: int, new_fills: int, bootstrap: bool) -> None:
        """Advance the watermark (never backwards) after a complete, successful walk."""
        with self.tx() as c:
            c.execute("INSERT OR IGNORE INTO poll_state (wallet) VALUES (?)", (wallet,))
            c.execute(
                """UPDATE poll_state SET
                     watermark_ts = MAX(COALESCE(watermark_ts, 0), ?),
                     last_seen_row_ts = MAX(COALESCE(last_seen_row_ts, 0), COALESCE(?, 0)),
                     last_cursor = NULL, last_attempt_at = ?, last_success_at = ?,
                     consecutive_failures = 0, last_error = NULL,
                     bootstrapped_at = COALESCE(bootstrapped_at, CASE WHEN ? THEN ? END),
                     polls_ok = polls_ok + 1, rows_seen = rows_seen + ?, fills_new = fills_new + ?
                   WHERE wallet = ?""",
                (int(watermark_ts), last_seen_row_ts, now, now, int(bootstrap), now, rows, new_fills, wallet))

    def mark_poll_failure(self, wallet: str, *, now: float, error: str, last_cursor: str | None,
                          new_fills: int) -> int:
        """Record a failed poll. The watermark is deliberately left untouched."""
        with self.tx() as c:
            c.execute("INSERT OR IGNORE INTO poll_state (wallet) VALUES (?)", (wallet,))
            c.execute(
                """UPDATE poll_state SET last_attempt_at = ?, consecutive_failures = consecutive_failures + 1,
                     last_error = ?, last_cursor = ?, polls_failed = polls_failed + 1, fills_new = fills_new + ?
                   WHERE wallet = ?""", (now, error[:1000], last_cursor, new_fills, wallet))
            r = c.execute("SELECT consecutive_failures FROM poll_state WHERE wallet = ?", (wallet,)).fetchone()
        return int(r[0])

    # ------------------------------------------------------------------ fills

    def insert_fills(self, fills: Iterable[dict]) -> list[str]:
        """INSERT OR IGNORE by deterministic fill_id; returns ids that were new."""
        new: list[str] = []
        cols = ("fill_id", "wallet", "activity_type", "tx_hash", "condition_id", "token_id", "outcome",
                "outcome_index", "side", "size", "price", "usdc_size", "ts", "title", "market_slug", "event_slug",
                "liquidity_role", "fee_usdc", "first_seen_at", "poll_mode", "raw_json")
        sql = f"INSERT OR IGNORE INTO fills ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
        with self.tx() as c:
            for f in fills:
                cur = c.execute(sql, tuple(f[k] for k in cols))
                if cur.rowcount == 1:
                    new.append(f["fill_id"])
        return new

    def count(self, table: str, where: str = "1", params: Iterable[Any] = ()) -> int:
        return int(self.q1(f"SELECT COUNT(*) FROM {table} WHERE {where}", params)[0])

    # ------------------------------------------------------------------ alerts / deliveries

    def create_alert(self, *, dedupe_key: str, kind: str, label: str, text: str, payload: dict, now: float,
                     channels: Iterable[str], wallet: str | None = None, bet_id: str | None = None,
                     status: str = "pending", suppressed_reason: str | None = None) -> int | None:
        """Insert an alert and one pending delivery per channel, atomically.

        Returns the new alert_id, or None if an alert with this dedupe_key already
        exists (the caller must treat that as "already handled", not as an error).
        """
        channels = list(channels) if status == "pending" else []
        if status == "pending" and not channels:
            status, suppressed_reason = "suppressed", suppressed_reason or "no delivery channel available"
        with self.tx() as c:
            cur = c.execute(
                """INSERT OR IGNORE INTO alerts (dedupe_key, kind, label, wallet, bet_id, created_at, status,
                                                 suppressed_reason, text, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (dedupe_key, kind, label, wallet, bet_id, now, status,
                 suppressed_reason, text, json.dumps(payload, default=str, sort_keys=True)))
            if cur.rowcount == 0:
                return None
            alert_id = int(cur.lastrowid)
            for ch in channels:
                c.execute("INSERT INTO deliveries (alert_id, channel, status, next_attempt_at) VALUES (?, ?, 'pending', ?)",
                          (alert_id, ch, now))
        return alert_id

    def refresh_alert_status(self, alert_id: int) -> str:
        rows = self.q("SELECT status FROM deliveries WHERE alert_id = ?", (alert_id,))
        sts = {r["status"] for r in rows}
        if not sts:
            return self.q1("SELECT status FROM alerts WHERE alert_id = ?", (alert_id,))["status"]
        if sts == {"sent"}:
            st = "sent"
        elif sts & {"pending", "sending"}:
            st = "pending"
        elif "sent" in sts:
            st = "partial"
        else:
            st = "failed"
        self.conn.execute("UPDATE alerts SET status = ? WHERE alert_id = ?", (st, alert_id))
        return st

    # ------------------------------------------------------------------ health

    def open_health_event(self, scope: str, kind: str) -> sqlite3.Row | None:
        return self.q1("SELECT * FROM health_events WHERE scope = ? AND kind = ? AND resolved_at IS NULL "
                       "ORDER BY event_id DESC LIMIT 1", (scope, kind))
