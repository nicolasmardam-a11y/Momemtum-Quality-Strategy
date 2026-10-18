"""Turn Data API activity rows into stored fills with a deterministic identity.

Fill identity
-------------
``fill_id = sha256(wallet | tx_hash | token_id | side | size | price | ts | type | n)``
where ``n`` is the occurrence index among rows that are identical on all the other
fields within one walk. Identical rows necessarily share a block timestamp, and a
walk always covers whole seconds (``start`` is inclusive), so every walk that
includes that second numbers them the same way: re-polling an overlapping window
yields the same ids and ``INSERT OR IGNORE`` drops the duplicates. On the two
wallets checked (727 and 101 rows) no two rows were identical, so ``n`` is 0 in
practice; it exists so that a genuine repeat can never be collapsed.

Maker/taker inference
---------------------
Activity rows have no role field, but ``usdc_size`` is fee-inclusive: a taker BUY
pays ``size*price + fee`` and a taker SELL receives ``size*price - fee``; makers
never pay fees. Verified 2026-10-17: every row with ``usdc_size != size*price``
was in the wallet's ``/v2/trades`` taker-only set (166/166 for mintblade, 54/54
for a second wallet). Rows with no fee difference are either maker fills or taker
fills in fee-free markets, so they are ``unknown`` until the optional /v2/trades
cross-check (enrich.py) resolves them.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Iterable

FEE_EPS = 1e-6


def num_key(x: float | int) -> str:
    """Canonical string for a JSON number, stable across fetches of the same payload."""
    return repr(float(x))


def identity(row: dict) -> tuple[str, ...]:
    return (
        row["proxy_wallet"].lower(),
        row["transaction_hash"].lower(),
        row["token_id"],
        row["side"],
        num_key(row["size"]),
        num_key(row["price"]),
        str(int(row["timestamp"])),
        row["type"],
    )


def fill_id_for(ident: tuple[str, ...], occurrence: int) -> str:
    return hashlib.sha256("|".join((*ident, str(occurrence))).encode()).hexdigest()


def fee_role(row: dict) -> tuple[str, float | None]:
    """(liquidity_role, fee_usdc) inferred from the fee embedded in usdc_size."""
    if row["type"] != "TRADE":
        return "n/a", None
    notional = float(row["size"]) * float(row["price"])
    diff = float(row["usdc_size"]) - notional
    tol = max(FEE_EPS, 1e-9 * notional)
    if row["side"] == "BUY" and diff > tol:
        return "taker", diff
    if row["side"] == "SELL" and diff < -tol:
        return "taker", -diff
    return "unknown", 0.0


class OccurrenceCounter:
    """Assigns occurrence indexes across all pages of one walk."""

    def __init__(self) -> None:
        self._c: Counter[tuple[str, ...]] = Counter()

    def next(self, ident: tuple[str, ...]) -> int:
        n = self._c[ident]
        self._c[ident] += 1
        return n


def to_fill(row: dict, occ: OccurrenceCounter, *, seen_at: float, poll_mode: str,
            live_from_ts: float | None = None) -> dict:
    """``live_from_ts``: in a bootstrap poll, rows executed at or after this time (when monitoring
    of the wallet began) are live activity, not the pre-existing baseline."""
    ident = identity(row)
    if live_from_ts is not None and int(row["timestamp"]) >= live_from_ts:
        poll_mode = "live"
    role, fee = fee_role(row)
    return {
        "fill_id": fill_id_for(ident, occ.next(ident)),
        "wallet": ident[0],
        "activity_type": row["type"],
        "tx_hash": ident[1],
        "condition_id": row["condition_id"],
        "token_id": row["token_id"],
        "outcome": row.get("outcome") or None,
        "outcome_index": row.get("outcome_index"),
        "side": row["side"] if row["type"] == "TRADE" else "",
        "size": float(row["size"]),
        "price": float(row["price"]),
        "usdc_size": float(row["usdc_size"]),
        "ts": int(row["timestamp"]),
        "title": row.get("title") or None,
        "market_slug": row.get("slug") or None,
        "event_slug": row.get("event_slug") or None,
        "liquidity_role": role,
        "fee_usdc": fee,
        "first_seen_at": seen_at,
        "poll_mode": poll_mode,
        "raw_json": json.dumps(row, sort_keys=True, separators=(",", ":")),
    }


def to_fills(rows: Iterable[dict], occ: OccurrenceCounter, *, seen_at: float, poll_mode: str,
             live_from_ts: float | None = None) -> list[dict]:
    return [to_fill(r, occ, seen_at=seen_at, poll_mode=poll_mode, live_from_ts=live_from_ts) for r in rows]


def trade_key(fill: dict) -> tuple:
    """Key comparable with Sources.taker_fill_keys()."""
    return (fill["tx_hash"], fill["token_id"], fill["side"], float(fill["size"]), float(fill["price"]), int(fill["ts"]))
