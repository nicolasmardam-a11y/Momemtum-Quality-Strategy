"""Pick 2-3 wallets that are trading right now, from the global /v2/trades feed (read-only).

Run from polymarket_research/. Prints per-wallet counts over the last 15 minutes.
"""
from __future__ import annotations

import collections
import time

from pmr.http import request_json

DATA = "https://data-api.polymarket.com"


def main() -> None:
    now = int(time.time())
    rows: list[dict] = []
    cursor = None
    for _ in range(5):  # up to 5,000 newest taker rows
        params = {"limit": 1000, "taker_only": "false", "_": str(time.time_ns())}
        if cursor:
            params["cursor"] = cursor
        j = request_json(f"{DATA}/v2/trades", params, source="data-api", timeout=20)
        rows += j.get("data") or []
        cursor = (j.get("pagination") or {}).get("next_cursor")
        if not cursor or rows and rows[-1]["timestamp"] < now - 900:
            break
    recent = [r for r in rows if r["timestamp"] >= now - 900]
    print(f"rows={len(rows)} last15m={len(recent)} newest_age={now - max(r['timestamp'] for r in rows)}s")
    by = collections.defaultdict(list)
    for r in recent:
        by[r["proxy_wallet"]].append(r)
    stats = []
    for w, rs in by.items():
        mkts = {r["condition_id"] for r in rs}
        buys = sum(r["side"] == "BUY" for r in rs)
        usd = sum(r["size"] * r["price"] for r in rs)
        span = max(r["timestamp"] for r in rs) - min(r["timestamp"] for r in rs)
        stats.append((len(rs), w, rs[0].get("name") or rs[0].get("pseudonym"), len(mkts), buys, round(usd), span,
                      rs[0]["title"][:50]))
    stats.sort(reverse=True)
    for s in stats[:40]:
        print(s)


if __name__ == "__main__":
    main()
