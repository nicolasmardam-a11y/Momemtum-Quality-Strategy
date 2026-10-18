"""SQLite ledger for the paper trader. Idempotent: every market is decided at most once, and every
paper position is unique per condition id, so re-running a scan (or recovering after an outage) never
double-counts. The order book at decision time is stored with each signal as provenance for the fill."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
  condition_id TEXT PRIMARY KEY,
  decided_at TEXT NOT NULL,
  decision_ts TEXT,
  anchor_ts TEXT,
  status TEXT NOT NULL,          -- signal | no_favourite | infeasible | missed | unlisted | no_book | not_tradable
  detail TEXT,
  question TEXT,
  category TEXT
);
CREATE TABLE IF NOT EXISTS signals (
  condition_id TEXT PRIMARY KEY REFERENCES decisions(condition_id),
  decided_at TEXT NOT NULL,
  decision_ts TEXT NOT NULL,
  anchor_ts TEXT NOT NULL,
  question TEXT, event_slug TEXT, market_slug TEXT, outcome TEXT, outcome_index INTEGER, token_id TEXT,
  category TEXT, sports_market_type TEXT, exact_score INTEGER, liquid INTEGER, tight INTEGER,
  liquidity_num REAL, volume_num REAL, fee_rate REAL, fee_exponent REAL,
  mid REAL, best_bid REAL, best_ask REAL, spread REAL, depth_1c_usd REAL,
  stake_usd REAL, shares REAL, vwap REAL, fee REAL, all_in REAL, complete INTEGER,
  slippage_c REAL,               -- (vwap - mid) in cents: what the live fill paid over the series-price proxy
  capacity_json TEXT, book_json TEXT,
  status TEXT NOT NULL DEFAULT 'open',   -- open | resolved
  resolved_at TEXT, payout REAL, pnl REAL, ret REAL, days_held REAL, disputed INTEGER
);
CREATE TABLE IF NOT EXISTS runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
  ok INTEGER, scanned INTEGER, due INTEGER, new_signals INTEGER, resolved INTEGER, errors TEXT
);
CREATE TABLE IF NOT EXISTS notices (
  dedupe_key TEXT PRIMARY KEY, sent_at TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(signals)")}
        if "tight" not in cols:  # ledgers created before the tight-spread tag
            self.db.execute("ALTER TABLE signals ADD COLUMN tight INTEGER")
        self.db.commit()

    # ---------------------------------------------------------------- decisions
    def decided(self, condition_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM decisions WHERE condition_id=?", (condition_id,)).fetchone() is not None

    def record_decision(self, condition_id: str, status: str, *, decision_ts=None, anchor_ts=None, detail=None,
                        question=None, category=None) -> bool:
        """Insert once; returns False if this market was already decided."""
        cur = self.db.execute(
            "INSERT OR IGNORE INTO decisions VALUES (?,?,?,?,?,?,?,?)",
            (condition_id, utcnow(), _iso(decision_ts), _iso(anchor_ts), status, detail, question, category))
        self.db.commit()
        return cur.rowcount == 1

    def record_signal(self, row: dict) -> bool:
        """Insert a paper position and its decision atomically; False if it already exists."""
        with self.db:
            cur = self.db.execute(
                "INSERT OR IGNORE INTO decisions VALUES (?,?,?,?,?,?,?,?)",
                (row["condition_id"], row["decided_at"], row["decision_ts"], row["anchor_ts"], "signal", None,
                 row.get("question"), row.get("category")))
            if cur.rowcount != 1:
                return False
            cols = list(row)
            self.db.execute(f"INSERT INTO signals ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                            [json.dumps(v) if isinstance(v, (dict, list)) else v for v in row.values()])
        return True

    # ---------------------------------------------------------------- positions
    def open_positions(self, before_iso: str | None = None) -> list[sqlite3.Row]:
        q = "SELECT * FROM signals WHERE status='open'"
        args: tuple = ()
        if before_iso:
            q += " AND anchor_ts <= ?"
            args = (before_iso,)
        return list(self.db.execute(q, args))

    def resolve(self, condition_id: str, *, resolved_at: str, payout: float, disputed: bool) -> None:
        r = self.db.execute("SELECT * FROM signals WHERE condition_id=?", (condition_id,)).fetchone()
        cost = r["shares"] * r["all_in"]
        pnl = r["shares"] * payout - cost
        decided = datetime.fromisoformat(r["decided_at"])
        days = max((datetime.fromisoformat(resolved_at) - decided).total_seconds() / 86400, 0.0)
        with self.db:
            self.db.execute(
                "UPDATE signals SET status='resolved', resolved_at=?, payout=?, pnl=?, ret=?, days_held=?, disputed=?"
                " WHERE condition_id=? AND status='open'",
                (resolved_at, payout, pnl, pnl / cost if cost else None, days, int(disputed), condition_id))

    def signals(self) -> list[sqlite3.Row]:
        return list(self.db.execute("SELECT * FROM signals ORDER BY decided_at"))

    # ---------------------------------------------------------------- runs and notices
    def start_run(self, kind: str) -> int:
        cur = self.db.execute("INSERT INTO runs (kind, started_at) VALUES (?,?)", (kind, utcnow()))
        self.db.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, *, ok: bool, scanned=0, due=0, new_signals=0, resolved=0, errors=None):
        self.db.execute("UPDATE runs SET finished_at=?, ok=?, scanned=?, due=?, new_signals=?, resolved=?, errors=?"
                        " WHERE run_id=?", (utcnow(), int(ok), scanned, due, new_signals, resolved,
                                            json.dumps(errors) if errors else None, run_id))
        self.db.commit()

    def last_ok_scan(self) -> str | None:
        r = self.db.execute("SELECT max(finished_at) FROM runs WHERE kind='scan' AND ok=1").fetchone()
        return r[0]

    def claim_notice(self, key: str) -> bool:
        """True the first time a notice key is claimed (so each alert is sent once)."""
        cur = self.db.execute("INSERT OR IGNORE INTO notices VALUES (?,?)", (key, utcnow()))
        self.db.commit()
        return cur.rowcount == 1


def _iso(v):
    return v.isoformat(timespec="seconds") if isinstance(v, datetime) else v
