"""Compare the monitor's stored fills with an independent full pull (read-only).

Usage (from polymarket_research/):
  python compare_independent.py <db> <W0> <W1> <OUT0> <OUT1>
W0..W1: comparison window (epoch s, inclusive); OUT0..OUT1: the outage window.

TRADE rows: /v2/trades?user=&taker_only=false&start&end (all pages, newest first), via pmr.http.
Non-trade rows (REDEEM, MERGE, SPLIT, CONVERSION): /v2/activity?user=&type=... over the same window.
Both are compared as multisets on (tx, token, side, size, price, ts, type), because
identical maker fills inside one transaction are genuine and must not be collapsed.
"""
from __future__ import annotations

import collections
import sqlite3
import sys
import time

from pmr.http import request_json

DATA = "https://data-api.polymarket.com"


def pull(path: str, params: dict) -> list[dict]:
    rows: list[dict] = []
    cursor = None
    for _ in range(200):
        p = dict(params, limit=1000, _=str(time.time_ns()))  # nonce: bypass the CDN (max-age 300 on /v2/trades)
        if cursor:
            p["cursor"] = cursor
        j = request_json(f"{DATA}{path}", p, source="data-api", timeout=30)
        rows += j["data"]
        cursor = j["pagination"].get("next_cursor")
        if not cursor:
            return rows
    raise RuntimeError("page cap hit")


def key(tx, tok, side, size, price, ts, typ):
    return (tx.lower(), str(tok), side or "", round(float(size), 6), round(float(price), 6), int(ts), typ)


def main() -> None:
    db, w0, w1, o0, o1 = sys.argv[1], *map(int, sys.argv[2:6])
    c = sqlite3.connect(db)
    lab = dict(c.execute("select address, label from wallets"))
    total_missing = total_extra = 0
    for w, name in lab.items():
        stored = collections.Counter(
            key(*r) for r in c.execute(
                "select tx_hash, token_id, side, size, price, ts, activity_type from fills "
                "where wallet=? and ts between ? and ?", (w, w0, w1)))
        trades = pull("/v2/trades", {"user": w, "taker_only": "false", "start": w0, "end": w1})
        act = pull("/v2/activity", {"user": w, "type": "SPLIT,MERGE,REDEEM,CONVERSION", "start": w0, "end": w1,
                                    "sort_direction": "ASC"})
        ref = collections.Counter(key(r["transaction_hash"], r["token_id"], r["side"], r["size"], r["price"],
                                      r["timestamp"], "TRADE") for r in trades)
        ref += collections.Counter(key(r["transaction_hash"], r.get("token_id") or "", r.get("side") or "", r["size"],
                                       r.get("price") or 0, r["timestamp"], r["type"]) for r in act)
        missing = ref - stored          # in the independent pull, not stored by the monitor
        extra = stored - ref            # stored by the monitor, not in the independent pull
        total_missing += sum(missing.values())
        total_extra += sum(extra.values())
        in_out = lambda cnt: sum(v for k, v in cnt.items() if o0 <= k[5] <= o1)
        reps = sum(1 for v in ref.values() if v > 1)
        print(f"{name}: independent rows={sum(ref.values())} (trades {len(trades)}, other {len(act)}), "
              f"stored={sum(stored.values())}, missing={sum(missing.values())}, extra={sum(extra.values())}; "
              f"outage window: independent={in_out(ref)} stored={in_out(stored)} missing={in_out(missing)}; "
              f"keys with genuine repeats={reps}")
        for k, v in list(missing.items())[:5]:
            print("   MISSING", v, k)
        for k, v in list(extra.items())[:5]:
            print("   EXTRA", v, k)
    print(f"TOTAL missing={total_missing} extra={total_extra}")


if __name__ == "__main__":
    main()
