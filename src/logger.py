"""Structured logging + immutable order audit trail.

- System log:  logs/system/YYYY-MM-DD_bot.log   (human-readable, rotating per day)
- Order audit: logs/execution/YYYY-MM-DD_orders.jsonl  (append-only JSONL)

The audit log is append-only and flushed after every write so a crash never
loses a submitted-order record.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _day(date: str | None) -> str:
    return date or datetime.now().strftime("%Y-%m-%d")


def get_logger(date: str | None = None, name: str = "v25bot") -> logging.Logger:
    d = _day(date)
    log_dir = ROOT / "logs" / "system"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{d}_bot.log"

    logger = logging.getLogger(f"{name}.{d}")
    logger.setLevel(logging.INFO)
    if logger.handlers:                      # idempotent across imports
        return logger
    logger.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    logger.info("=== logger initialised (system log: %s) ===", path)
    return logger


class OrderAuditLog:
    """Append-only JSONL audit of every order preview and submission."""

    def __init__(self, date: str | None = None):
        d = _day(date)
        log_dir = ROOT / "logs" / "execution"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.path = log_dir / f"{d}_orders.jsonl"

    def write(self, event: str, **fields) -> dict:
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": event,
            **fields,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
            f.flush()
        return rec
