"""Group stored fills into bet events.

A bet event is a run of fills by the same wallet on the same condition, outcome
token and side, where consecutive fills are at most ``gap`` seconds apart (default
10 min). A BUY run that starts more than ``gap`` after an earlier BUY run on the
same outcome is a separate event of kind ``addition`` (addition to position).

Assignment is incremental and persisted: each fill is attached exactly once
(``fills.bet_id``), in ``(ts, fill_id)`` order, to the existing bet whose time span
it falls within ``gap`` of, otherwise it starts a new bet whose id is that fill's
id. Re-polling never re-groups already-assigned fills, so bet ids (and therefore
alert dedupe keys) are stable. A late-ingested fill that lands inside an existing
bet's span extends it; existing bets are never merged, which keeps alerts that
were already sent consistent with what is stored.
"""
from __future__ import annotations

import sqlite3

from .store import Store

_KIND_BY_SIDE = {"SELL": "reduction", "SPLIT": "split", "MERGE": "merge", "REDEEM": "redeem",
                 "CONVERSION": "conversion"}


def bet_side(fill: sqlite3.Row) -> str:
    return fill["side"] if fill["activity_type"] == "TRADE" else fill["activity_type"]


def assign_pending(store: Store, gap_s: float, now: float) -> list[str]:
    """Attach every unassigned fill to a bet. Returns the ids of bets that changed."""
    touched: list[str] = []
    with store.tx() as c:
        pending = c.execute(
            "SELECT * FROM fills WHERE bet_id IS NULL AND activity_type NOT IN "
            "('REWARD','YIELD','TAKER_REBATE','MAKER_REBATE') ORDER BY ts, fill_id").fetchall()
        for f in pending:
            side = bet_side(f)
            key = (f["wallet"], f["condition_id"], f["token_id"], side)
            bet = c.execute(
                """SELECT * FROM bets WHERE wallet = ? AND condition_id = ? AND token_id = ? AND side = ?
                     AND first_ts - ? <= ? AND last_ts + ? >= ?
                   ORDER BY ABS(last_ts - ?) LIMIT 1""",
                (*key, gap_s, f["ts"], gap_s, f["ts"], f["ts"])).fetchone()
            live = 1 if f["poll_mode"] == "live" else 0
            if bet is not None:
                c.execute(
                    """UPDATE bets SET first_ts = MIN(first_ts, ?), last_ts = MAX(last_ts, ?), n_fills = n_fills + 1,
                         shares = shares + ?, notional_usdc = notional_usdc + ?, usdc_size = usdc_size + ?,
                         first_seen_at = MIN(first_seen_at, ?), last_seen_at = MAX(last_seen_at, ?),
                         live_fills = live_fills + ?, needs_eval = 1, updated_at = ?
                       WHERE bet_id = ?""",
                    (f["ts"], f["ts"], f["size"], f["size"] * f["price"], f["usdc_size"], f["first_seen_at"],
                     f["first_seen_at"], live, now, bet["bet_id"]))
                bet_id = bet["bet_id"]
            else:
                bet_id = f["fill_id"]
                prior = c.execute(
                    """SELECT bet_id FROM bets WHERE wallet = ? AND condition_id = ? AND token_id = ? AND side = ?
                         AND last_ts < ? ORDER BY last_ts DESC LIMIT 1""", (*key, f["ts"])).fetchone()
                if side == "BUY":
                    kind = "addition" if prior else "new_position"
                else:
                    kind = _KIND_BY_SIDE.get(side, side.lower())
                c.execute(
                    """INSERT INTO bets (bet_id, wallet, condition_id, token_id, outcome, side, kind, prior_bet_id,
                         first_ts, last_ts, n_fills, shares, notional_usdc, usdc_size, first_seen_at, last_seen_at,
                         live_fills, needs_eval, alert_state, title, market_slug, event_slug, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, 1, 'none', ?, ?, ?, ?)""",
                    (bet_id, *key[:3], f["outcome"], side, kind, prior["bet_id"] if prior else None,
                     f["ts"], f["ts"], f["size"], f["size"] * f["price"], f["usdc_size"], f["first_seen_at"],
                     f["first_seen_at"], live, f["title"], f["market_slug"], f["event_slug"], now))
            c.execute("UPDATE fills SET bet_id = ? WHERE fill_id = ?", (bet_id, f["fill_id"]))
            if bet_id not in touched:
                touched.append(bet_id)
    return touched
