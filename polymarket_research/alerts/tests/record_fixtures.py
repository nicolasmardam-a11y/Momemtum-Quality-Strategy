"""Re-record the test fixtures from the live public APIs (read-only).

    cd polymarket_research && python -m alerts.tests.record_fixtures

Every fixture file is ``{"meta": {...provenance...}, "body": <trimmed payload>}``.
Trimming keeps the fields the code reads; profile fields of the second, anonymous
wallet (picked from the public trade feed because it has sells, merges, splits and
additions) are blanked. Nothing here authenticates or writes anywhere but fixtures/.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

FIX = Path(__file__).resolve().parent / "fixtures"
DATA, GAMMA, CLOB = "https://data-api.polymarket.com", "https://gamma-api.polymarket.com", "https://clob.polymarket.com"
MINTBLADE = "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb"
SECOND = "0xc8c1f765515347a725afff5faa4f5632dd8d1e41"
TYPES = "TRADE,SPLIT,MERGE,REDEEM,CONVERSION"
PROFILE = ("name", "pseudonym", "bio", "profile_image", "profile_image_optimized", "icon")

S = requests.Session()
S.headers["User-Agent"] = "pmr-alerts-fixture-recorder/0.1 (read-only)"


def get(url: str, params: dict | None = None) -> tuple[int, dict, object]:
    time.sleep(0.25)
    r = S.get(url, params=params, timeout=30)
    try:
        body = r.json()
    except ValueError:
        body = r.text
    return r.status_code, {k.lower(): v for k, v in r.headers.items()}, body


def save(name: str, url: str, params: dict | None, status: int, body: object, note: str) -> None:
    meta = {"url": url, "params": params, "status": status, "note": note,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (FIX / name).write_text(json.dumps({"meta": meta, "body": body}, indent=1, sort_keys=True) + "\n")
    print(f"wrote {name}")


def walk_activity(user: str) -> list[dict]:
    rows: list[dict] = []
    p = {"user": user, "type": TYPES, "start": 1, "end": int(time.time()) + 86400, "sort_direction": "ASC", "limit": 1000}
    while True:
        st, _, j = get(f"{DATA}/v2/activity", p)
        assert st == 200, (st, j)
        rows += j["data"]
        if not j["pagination"].get("next_cursor"):
            return rows
        p["cursor"] = j["pagination"]["next_cursor"]


def blank(rows: list[dict], fields=PROFILE) -> list[dict]:
    return [{k: ("" if k in fields else v) for k, v in r.items()} for r in rows]


def main() -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    # 1. mintblade: first four bets in full + the first 30 fills of the large IR Iran bet + redeems.
    rows = walk_activity(MINTBLADE)
    iran = "0xe70fd51f42e61fc309d8e57019a7b76c8dc7bd19b473351d56ff1e125ae0d9d4"
    keep, n_iran = [], 0
    for r in rows:
        if r["type"] != "TRADE":
            keep.append(r)
        elif r["condition_id"] != iran:
            keep.append(r)
        elif n_iran < 30:
            keep.append(r)
            n_iran += 1
    save("activity_mintblade.json", f"{DATA}/v2/activity",
         {"user": MINTBLADE, "type": TYPES, "start": 1, "sort_direction": "ASC"}, 200, blank(keep, ("icon",)),
         f"full walk had {len(rows)} rows; kept {len(keep)} (all non-Iran fills, first 30 Iran fills, all non-trades)")

    # 2. Second wallet: sells, merges, splits, redeems, additions after the gap.
    rows2 = walk_activity(SECOND)
    save("activity_second.json", f"{DATA}/v2/activity",
         {"user": SECOND, "type": TYPES, "start": 1, "sort_direction": "ASC"}, 200, blank(rows2),
         "anonymous active wallet from the public trade feed; profile fields blanked")

    # 3. A genuine multi-page cursor walk (limit=4), recorded page by page.
    pages = []
    p = {"user": SECOND, "type": TYPES, "start": rows2[0]["timestamp"], "end": rows2[11]["timestamp"],
         "sort_direction": "ASC", "limit": 4}
    while True:
        st, _, j = get(f"{DATA}/v2/activity", p)
        pages.append({"request": dict(p), "status": st, "body": {"data": blank(j["data"]), "pagination": j["pagination"]}})
        cur = j["pagination"].get("next_cursor")
        if not cur:
            break
        p = {**p, "cursor": cur}
    save("activity_pages_live.json", f"{DATA}/v2/activity", None, 200, pages,
         "live keyset walk with limit=4; each page keyed by the cursor that requested it")

    # 4. Status, error envelopes.
    st, _, j = get(f"{DATA}/v2/status")
    save("status.json", f"{DATA}/v2/status", None, st, j, "live freshness snapshot")
    st, _, j = get(f"{DATA}/v2/activity", {"user": SECOND, "cursor": "garbage"})
    save("error_invalid_cursor.json", f"{DATA}/v2/activity", {"cursor": "garbage"}, st, j, "live 400 error envelope")

    # 5. Market metadata: a resolved market (needs closed=true) and an open one with a live book.
    st, _, j = get(f"{GAMMA}/markets", {"condition_ids": iran, "closed": "true"})
    for m in j:
        m.pop("description", None)
    save("gamma_market_closed.json", f"{GAMMA}/markets", {"condition_ids": iran, "closed": "true"}, st, j,
         "resolved IR Iran market (open lookup without closed=true returns [])")
    iran_no = next(r["token_id"] for r in rows if r["condition_id"] == iran and r["type"] == "TRADE")
    st, _, j = get(f"{CLOB}/book", {"token_id": iran_no})
    save("book_404.json", f"{CLOB}/book", None, st, j, "no orderbook for a resolved market's token")

    recent = [r for r in rows2 if r["type"] == "TRADE" and r["side"] == "BUY"][-1]
    cid, tok = recent["condition_id"], recent["token_id"]
    st, _, gm = get(f"{GAMMA}/markets", {"condition_ids": cid})
    for m in gm:
        m.pop("description", None)
    save("gamma_market_open.json", f"{GAMMA}/markets", {"condition_ids": cid}, st, gm, "open market of the second wallet")
    st, _, cm = get(f"{CLOB}/markets/{cid}")
    if isinstance(cm, dict):
        cm.pop("description", None)
    save("clob_market_open.json", f"{CLOB}/markets/{cid}", None, st, cm, "CLOB market state (not CDN-cached)")
    st, _, bk = get(f"{CLOB}/book", {"token_id": tok})
    bk["bids"] = sorted(bk["bids"], key=lambda x: -float(x["price"]))[:25]
    bk["asks"] = sorted(bk["asks"], key=lambda x: float(x["price"]))[:25]
    save("book_open.json", f"{CLOB}/book", {"token_id": tok}, st, bk, "live book, trimmed to 25 levels per side")
    st, _, pm = get(f"{DATA}/v2/positions", {"user": SECOND, "condition": cid})
    save("positions_market.json", f"{DATA}/v2/positions", {"user": SECOND, "condition": cid}, st,
         {"data": blank(pm["data"], PROFILE), "pagination": pm["pagination"]}, "OPEN positions in the market")
    ev_id = (gm[0].get("events") or [{}])[0].get("id") if gm else None
    st, _, pe = get(f"{DATA}/v2/positions", {"user": SECOND, "event_id": ev_id})
    save("positions_event.json", f"{DATA}/v2/positions", {"user": SECOND, "event_id": ev_id}, st,
         {"data": blank(pe["data"], PROFILE), "pagination": pe["pagination"]}, "OPEN positions in the event")
    t0 = rows2[0]["timestamp"]
    st, _, tt = get(f"{DATA}/v2/trades", {"user": SECOND, "start": t0, "end": int(time.time()), "limit": 1000})
    save("trades_taker_second.json", f"{DATA}/v2/trades", {"user": SECOND, "start": t0}, st,
         {"data": blank(tt["data"]), "pagination": tt["pagination"]}, "taker-only (default) fills of the second wallet")


if __name__ == "__main__":
    main()
