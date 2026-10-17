"""Thin read-only clients for the public Polymarket APIs and auxiliary sources.

Endpoints and limits verified against docs.polymarket.com and live responses on
2026-10-17. Data API v1 is retired on 2026-10-24, so only /v2 routes are used.
None of these calls require authentication, a wallet or a private key.
"""
from __future__ import annotations

import json
from typing import Iterator

from .http import request_json

DATA = "https://data-api.polymarket.com"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
CRYPTOHOUSE = "https://crypto-clickhouse.clickhouse.com/"
POLYGON_RPC = "https://polygon-bor-rpc.publicnode.com"


# --------------------------------------------------------------------------- Data API v2

def data_v2(path: str, params: dict | None = None, *, cache: bool = False, max_pages: int | None = None) -> Iterator[dict]:
    """Yield rows from a cursor-paginated Data API v2 route (limit <= 1000 per page)."""
    params = dict(params or {})
    params.setdefault("limit", 1000 if path.endswith(("trades", "activity")) else 500)
    pages = 0
    while True:
        j = request_json(f"{DATA}{path}", params, source="data-api", cache=cache)
        rows = j.get("data")
        if isinstance(rows, list):
            yield from rows
        elif rows is not None:
            yield rows
        pages += 1
        cur = (j.get("pagination") or {}).get("next_cursor")
        if not cur or (max_pages and pages >= max_pages):
            return
        params["cursor"] = cur


def trades(*, condition: str | None = None, user: str | None = None, taker_only: bool | None = None,
           cache: bool = False, **kw) -> list[dict]:
    """Executed trades. taker_only=False also returns maker-side fills."""
    p = {"condition": condition, "user": user, **kw}
    if taker_only is not None:
        p["taker_only"] = str(taker_only).lower()
    return list(data_v2("/v2/trades", p, cache=cache))


def activity(user: str, *, cache: bool = False, **kw) -> list[dict]:
    return list(data_v2("/v2/activity", {"user": user, **kw}, cache=cache))


def positions(user: str | None = None, *, status: str | None = None, cache: bool = False, **kw) -> list[dict]:
    """status in OPEN, REDEEMABLE, REDEEMABLE_LOST, MERGEABLE, CLOSED."""
    return list(data_v2("/v2/positions", {"user": user, "status": status, **kw}, cache=cache))


def user_stats(user: str) -> dict | None:
    return request_json(f"{DATA}/v2/user-stats", {"user": user}, source="data-api").get("data")


def data_status() -> dict:
    return request_json(f"{DATA}/v2/status", source="data-api").get("data")


# --------------------------------------------------------------------------- Gamma

def gamma_keyset(kind: str, params: dict | None = None, *, cache: bool = False, max_pages: int | None = None) -> Iterator[dict]:
    """Yield markets or events from /markets/keyset or /events/keyset (limit <= 100).

    Gamma silently filters to open markets unless closed=true is passed, so a
    lookup of a resolved market by condition_ids without closed=true returns [].
    """
    params = dict(params or {})
    params.setdefault("limit", 100)
    pages = 0
    while True:
        j = request_json(f"{GAMMA}/{kind}/keyset", params, source="gamma", cache=cache)
        yield from j.get(kind) or []
        pages += 1
        cur = j.get("next_cursor")
        if not cur or (max_pages and pages >= max_pages):
            return
        params["after_cursor"] = cur


def gamma_markets(**params) -> list[dict]:
    cache = params.pop("cache", False)
    return list(gamma_keyset("markets", params, cache=cache))


def gamma_events(**params) -> list[dict]:
    cache = params.pop("cache", False)
    return list(gamma_keyset("events", params, cache=cache))


def public_profile(address: str) -> dict:
    return request_json(f"{GAMMA}/public-profile", {"address": address}, source="gamma")


def jlist(v):
    """Gamma encodes outcomes, outcomePrices and clobTokenIds as JSON strings."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return [v]
    return v or []


# --------------------------------------------------------------------------- CLOB (public market data)

def _levels(levels, reverse):
    out = [(float(x["price"]), float(x["size"])) for x in levels or []]
    return sorted(out, key=lambda t: t[0], reverse=reverse)


def normalize_book(b: dict) -> dict:
    """Return bids best-first (descending) and asks best-first (ascending)."""
    return {
        "asset_id": b.get("asset_id"),
        "market": b.get("market"),
        "timestamp_ms": int(b["timestamp"]) if b.get("timestamp") else None,
        "bids": _levels(b.get("bids"), True),
        "asks": _levels(b.get("asks"), False),
        "tick_size": float(b["tick_size"]) if b.get("tick_size") else None,
        "min_order_size": float(b["min_order_size"]) if b.get("min_order_size") else None,
        "neg_risk": b.get("neg_risk"),
        "last_trade_price": float(b["last_trade_price"]) if b.get("last_trade_price") else None,
    }


def book(token_id: str) -> dict:
    return normalize_book(request_json(f"{CLOB}/book", {"token_id": token_id}, source="clob"))


def books(token_ids: list[str]) -> list[dict]:
    """Batch order books (POST /books). Keep batches modest (<= 100 tokens)."""
    out = []
    for i in range(0, len(token_ids), 100):
        chunk = [{"token_id": t} for t in token_ids[i:i + 100]]
        out += [normalize_book(b) for b in request_json(f"{CLOB}/books", method="POST", json_body=chunk, source="clob")]
    return out


def prices_history(token_id: str, start_ts: int, end_ts: int, fidelity_min: int = 1, *, cache: bool = True) -> list[dict]:
    """Trade/mid price series [{t, p}] for one token. Not bid/ask, not depth.

    Explicit startTs/endTs are required for resolved markets; interval=max
    returns an empty list for them (verified 2026-10-17).
    """
    j = request_json(f"{CLOB}/prices-history",
                     {"market": token_id, "startTs": int(start_ts), "endTs": int(end_ts), "fidelity": fidelity_min},
                     source="clob", cache=cache)
    return j.get("history") or []


# --------------------------------------------------------------------------- CryptoHouse (ClickHouse SQL over on-chain data)

def cryptohouse(sql: str, *, cache: bool = True) -> list[dict]:
    """Run read-only SQL. Limits: 60 s execution, 2,000 result rows.

    polymarket.orders_filled covers 2022-11-21 .. 2026-01-05 (pre-V2 exchange);
    it does not contain Protocol V2 activity. Aggregate server-side.
    """
    j = request_json(CRYPTOHOUSE, {"user": "crypto"}, method="POST", data=sql.rstrip().rstrip(";") + " FORMAT JSON",
                     source="cryptohouse", cache=cache, timeout=120)
    rows = j.get("data", [])
    if len(rows) >= 2000:
        raise RuntimeError("CryptoHouse result hit the 2,000-row cap; paginate or aggregate further")
    return rows


# --------------------------------------------------------------------------- Polygon JSON-RPC

def rpc(method: str, params: list) -> object:
    j = request_json(POLYGON_RPC, method="POST", json_body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                     source="polygon")
    if "error" in j:
        raise RuntimeError(f"RPC {method} error: {j['error']}")
    return j["result"]
