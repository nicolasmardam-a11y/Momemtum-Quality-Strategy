"""Read-only public endpoints used by the alert system, with schema checks.

Verified against https://data-api.polymarket.com/v2/openapi.json and live calls on
2026-10-17 (details in README "What was verified"):

* ``/v2/activity?user=`` is keyset-paginated on ``(block_timestamp, sequence_id)``;
  ``sort_direction=ASC`` is honoured (``/v2/trades`` ignores it and is always DESC).
  ``start``/``end`` are inclusive epoch seconds on the block timestamp; omitted
  ``start`` floors to three years back, ``start=1`` is full history.
* The cursor carries only the seek anchor and page size, so every page must
  re-send identical filters. ``pagination.next_cursor`` is ``null`` on the last page.
* A malformed address returns 200 with an empty list, so addresses are validated
  in config.py before they get here.
* Responses are CDN-cached (``cache-control: public, max-age=15`` on activity,
  ``max-age=300`` on trades and Gamma). Varying ``end`` gives each poll a unique
  URL and a CDN miss (verified ``x-cache: Miss``).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from pmr.api import jlist, normalize_book

from .http_client import DataError, HttpClient, Response

DATA = "https://data-api.polymarket.com"
GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

# Fields of an Activity row that this system relies on, with accepted JSON types.
ACTIVITY_REQUIRED: dict[str, tuple[type, ...]] = {
    "proxy_wallet": (str,),
    "timestamp": (int,),
    "type": (str,),
    "size": (int, float),
    "usdc_size": (int, float),
    "price": (int, float),
    "transaction_hash": (str,),
    "condition_id": (str,),
    "token_id": (str,),
    "side": (str,),
    "outcome": (str,),
    "outcome_index": (int,),
    "title": (str,),
    "slug": (str,),
    "event_slug": (str,),
}


def validate_activity_row(row: Any, wallet: str, allowed_types: tuple[str, ...]) -> list[str]:
    """Return a list of schema problems for one activity row (empty means OK)."""
    if not isinstance(row, dict):
        return [f"row is {type(row).__name__}, not an object"]
    problems = []
    for k, types in ACTIVITY_REQUIRED.items():
        if k not in row:
            problems.append(f"missing field {k!r}")
        elif isinstance(row[k], bool) or not isinstance(row[k], types):
            problems.append(f"field {k!r} has type {type(row[k]).__name__}")
    if problems:
        return problems
    if row["proxy_wallet"].lower() != wallet:
        problems.append(f"proxy_wallet {row['proxy_wallet']} != polled wallet {wallet}")
    if row["type"] not in allowed_types:
        problems.append(f"unexpected activity type {row['type']!r} (requested {','.join(allowed_types)})")
    if row["type"] == "TRADE":
        if row["side"] not in ("BUY", "SELL"):
            problems.append(f"TRADE row with side {row['side']!r}")
        if not row["token_id"] or not row["condition_id"]:
            problems.append("TRADE row without token_id/condition_id")
        if not (0.0 <= float(row["price"]) <= 1.0):
            problems.append(f"TRADE price {row['price']} outside [0, 1]")
        if float(row["size"]) <= 0:
            problems.append(f"TRADE size {row['size']} <= 0")
    if row["timestamp"] < 1_500_000_000 or row["timestamp"] > 4_000_000_000:
        problems.append(f"implausible timestamp {row['timestamp']}")
    return problems


def _check_envelope(resp: Response, path: str) -> tuple[list, dict]:
    body = resp.body
    if not isinstance(body, dict) or "data" not in body:
        raise DataError("schema", "data-api", resp.url, f"{path}: missing 'data' envelope", status=resp.status,
                        retryable=False)
    rows = body["data"]
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise DataError("schema", "data-api", resp.url, f"{path}: 'data' is {type(rows).__name__}, expected list",
                        status=resp.status, retryable=False)
    pag = body.get("pagination")
    if not isinstance(pag, dict) or "has_more" not in pag:
        raise DataError("schema", "data-api", resp.url, f"{path}: missing pagination.has_more", status=resp.status,
                        retryable=False)
    if pag.get("has_more") and not pag.get("next_cursor"):
        raise DataError("schema", "data-api", resp.url, f"{path}: has_more=true without next_cursor",
                        status=resp.status, retryable=False)
    return rows, pag


@dataclass
class ActivityPage:
    rows: list[dict]
    next_cursor: str | None
    server_time: float | None
    page_no: int
    server_now: float | None = None     # Date + Age, for clock-offset estimation
    window_end: int | None = None       # the ``end`` actually requested (rows after it were not asked for)


class Sources:
    """All network reads. Every method raises DataError on any failure."""

    # Market metadata changes slowly (and Gamma is CDN-cached for 300 s anyway); CLOB market
    # state is cached only briefly. Books and positions are never cached.
    GAMMA_TTL_S = 300.0
    CLOB_MARKET_TTL_S = 10.0

    def __init__(self, http: HttpClient, *, cache_bust: bool = True, clock: Callable[[], float] = time.time) -> None:
        self.http = http
        self.cache_bust = cache_bust
        self.clock = clock
        self._cache: dict[tuple[str, str], tuple[float, Any]] = {}

    def _cached(self, kind: str, key: str, ttl: float, fetch: Callable[[], Any]) -> Any:
        hit = self._cache.get((kind, key))
        now = self.clock()
        if hit is not None and now - hit[0] < ttl:
            return hit[1]
        val = fetch()                      # errors propagate and are not cached
        self._cache[(kind, key)] = (now, val)
        if len(self._cache) > 2000:
            self._cache.clear()
        return val

    # ------------------------------------------------------------------ Data API v2

    def iter_activity(self, wallet: str, *, start: int, types: tuple[str, ...], limit: int = 500,
                      max_pages: int = 5000, end: int | None = None) -> Iterator[ActivityPage]:
        """Walk /v2/activity for one wallet oldest-first from ``start`` (inclusive) to ``end``.

        Follows ``next_cursor`` until it is null. Raises DataError on a schema
        problem, a repeated cursor, a walk that goes backwards in time (a page that
        re-serves rows from before its anchor would otherwise be stored as phantom
        repeats) or more than ``max_pages`` pages, so a walk is never silently
        truncated or padded. Each page is checked *before* it is yielded.
        """
        if end is None:   # the API default ("now plus one day"); unique per second -> CDN miss
            end = int(self.clock()) + 86_400
        params: dict[str, Any] = {
            "user": wallet,
            "type": ",".join(types),
            "start": max(1, int(start)),
            "end": end if self.cache_bust else None,
            "sort_direction": "ASC",
            "limit": limit,
        }
        seen_cursors: set[str] = set()
        page_no = 0
        last_ts: int | None = None
        while True:
            resp = self.http.get_json(f"{DATA}/v2/activity", params, source="data-api")
            rows, pag = _check_envelope(resp, "/v2/activity")
            problems = []
            for i, r in enumerate(rows):
                for p in validate_activity_row(r, wallet, types):
                    problems.append(f"row {i}: {p}")
            if not problems:
                for i, r in enumerate(rows):
                    if last_ts is not None and r["timestamp"] < last_ts:
                        problems.append(f"row {i} (page {page_no + 1}): timestamp {r['timestamp']} < previous "
                                        f"{last_ts}; sort_direction=ASC walk went backwards (re-served or "
                                        "unordered rows), refusing to store possible phantom repeats")
                        break
                    last_ts = r["timestamp"]
            if problems:
                raise DataError("schema", "data-api", resp.url,
                                f"/v2/activity schema surprise ({len(problems)} problem(s)): " + "; ".join(problems[:5]),
                                status=resp.status, retryable=False, params=params)
            page_no += 1
            cur = pag.get("next_cursor")
            yield ActivityPage(rows, cur, resp.server_time, page_no, server_now=resp.server_now, window_end=end)
            if not cur:
                return
            if cur in seen_cursors:
                raise DataError("schema", "data-api", resp.url, "pagination loop: next_cursor repeated",
                                retryable=False, params=params)
            if page_no >= max_pages:
                raise DataError("schema", "data-api", resp.url,
                                f"walk exceeded max_pages_per_poll={max_pages}; refusing to truncate silently",
                                retryable=False, params=params)
            seen_cursors.add(cur)
            params = {**params, "cursor": cur}

    def _walk(self, path: str, params: dict[str, Any], max_pages: int = 50) -> list[dict]:
        out: list[dict] = []
        params = dict(params)
        seen: set[str] = set()
        for _ in range(max_pages):
            resp = self.http.get_json(f"{DATA}{path}", params, source="data-api")
            rows, pag = _check_envelope(resp, path)
            out.extend(r for r in rows if isinstance(r, dict))
            cur = pag.get("next_cursor")
            if not cur:
                return out
            if cur in seen:
                raise DataError("schema", "data-api", resp.url, f"{path}: next_cursor repeated", retryable=False)
            seen.add(cur)
            params["cursor"] = cur
        raise DataError("schema", "data-api", f"{DATA}{path}", f"{path}: more than {max_pages} pages", retryable=False)

    def trade_fill_keys(self, wallet: str, start: int, end: int, *, taker_only: bool = True) -> set[tuple]:
        """Identity tuples of this wallet's fills in [start, end] from /v2/trades.

        /v2/trades rows have no maker/taker field; the default taker_only=true
        serves each fill once on its taker side, so for a ``user`` query it returns
        exactly the wallet's taker fills (verified: subset of taker_only=false).
        ``taker_only=False`` returns every fill (verified equal to the activity
        TRADE rows, 727 = 727) and is used to prove the index has caught up before
        absence from the taker set is read as "maker".
        """
        rows = self._walk("/v2/trades", {"user": wallet, "start": int(start), "end": int(end), "limit": 1000,
                                         "taker_only": "true" if taker_only else "false"})
        return {(str(r.get("transaction_hash", "")).lower(), r.get("token_id"), r.get("side"), float(r.get("size", 0)),
                 float(r.get("price", 0)), int(r.get("timestamp", 0))) for r in rows}

    def taker_fill_keys(self, wallet: str, start: int, end: int) -> set[tuple]:
        return self.trade_fill_keys(wallet, start, end, taker_only=True)

    def latest_activity(self, wallet: str, types: tuple[str, ...], *, end: int | None = None) -> dict | None:
        """The wallet's newest activity row of ``types`` over its full history, or None.

        Used once per wallet when the bootstrap window is empty: it distinguishes a
        dormant account (the row becomes a known "canary" that later polls must
        re-read) from an address the Data API has never seen (wrong address type).
        """
        params = {"user": wallet, "type": ",".join(types), "start": 1,
                  "end": end if end is not None else int(self.clock()) + 86_400,
                  "sort_direction": "DESC", "limit": 1}
        resp = self.http.get_json(f"{DATA}/v2/activity", params, source="data-api")
        rows, _ = _check_envelope(resp, "/v2/activity")
        if not rows:
            return None
        problems = validate_activity_row(rows[0], wallet, types)
        if problems:
            raise DataError("schema", "data-api", resp.url, "/v2/activity (latest): " + "; ".join(problems[:5]),
                            status=resp.status, retryable=False, params=params)
        return rows[0]

    def positions(self, wallet: str, *, condition: str | None = None, event_id: str | None = None) -> list[dict]:
        """OPEN positions (the superset incl. settled-but-unredeemed) for a wallet, optionally narrowed."""
        return self._walk("/v2/positions", {"user": wallet, "condition": condition, "event_id": event_id,
                                            "limit": 500})

    def status(self) -> dict:
        """/v2/status: serving lag and snapshot age. 503 before the first refresh."""
        resp = self.http.get_json(f"{DATA}/v2/status", source="data-api")
        body = resp.body
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict) or "serving" not in data or "age_seconds" not in data:
            raise DataError("schema", "data-api", resp.url, "/v2/status: unexpected payload shape", retryable=False)
        serving = data.get("serving") or {}
        return {
            "lag_seconds": serving.get("lag_seconds"),
            "worst": serving.get("worst"),
            "age_seconds": data.get("age_seconds"),
            "computed_at": data.get("computed_at"),
            "server_time": resp.server_time,
            "server_now": resp.server_now,
        }

    # ------------------------------------------------------------------ Gamma

    def gamma_market(self, condition_id: str) -> dict | None:
        """Gamma market by condition id. Gamma returns only open markets unless
        closed=true, so an empty open lookup is retried with closed=true."""
        return self._cached("gamma", condition_id, self.GAMMA_TTL_S, lambda: self._gamma_market(condition_id))

    def _gamma_market(self, condition_id: str) -> dict | None:
        for closed in (None, "true"):
            resp = self.http.get_json(f"{GAMMA}/markets", {"condition_ids": condition_id, "closed": closed},
                                      source="gamma")
            if not isinstance(resp.body, list):
                raise DataError("schema", "gamma", resp.url, "/markets: expected a JSON list", retryable=False)
            if resp.body:
                # Never trust position 0: if the filter were ignored or renamed, Gamma would answer with
                # its default listing and the alert would show another market's question, fees and state.
                want = condition_id.lower()
                hit = [m for m in resp.body if isinstance(m, dict) and str(m.get("conditionId", "")).lower() == want]
                if not hit:
                    got = [str(m.get("conditionId"))[:12] for m in resp.body[:3] if isinstance(m, dict)]
                    raise DataError("schema", "gamma", resp.url,
                                    f"/markets?condition_ids={want[:12]}...: no returned market has this conditionId "
                                    f"(got {got}); filter ignored?", retryable=False)
                return hit[0]
        return None

    # ------------------------------------------------------------------ CLOB (public)

    def clob_market(self, condition_id: str) -> dict | None:
        """CLOB market state (not CDN-cached, unlike Gamma): closed, accepting_orders, seconds_delay."""
        return self._cached("clob_market", condition_id, self.CLOB_MARKET_TTL_S, lambda: self._clob_market(condition_id))

    def _clob_market(self, condition_id: str) -> dict | None:
        resp = self.http.get_json(f"{CLOB}/markets/{condition_id}", source="clob", allow_404=True)
        if resp.status == 404:
            return None
        if not isinstance(resp.body, dict):
            raise DataError("schema", "clob", resp.url, "/markets/{id}: expected an object", retryable=False)
        return resp.body

    def book(self, token_id: str) -> dict | None:
        """Fresh executable book snapshot, normalised best-first. None when no book exists (404)."""
        resp = self.http.get_json(f"{CLOB}/book", {"token_id": token_id}, source="clob", allow_404=True)
        if resp.status == 404:
            return None
        b = resp.body
        if not isinstance(b, dict) or "bids" not in b or "asks" not in b:
            raise DataError("schema", "clob", resp.url, "/book: missing bids/asks", retryable=False)
        if b.get("asset_id") is not None and str(b["asset_id"]) != str(token_id):
            raise DataError("schema", "clob", resp.url, f"/book: asset_id {str(b['asset_id'])[:16]}... is not the "
                            f"requested token {str(token_id)[:16]}... (wrong book)", retryable=False)
        try:
            nb = normalize_book(b)
        except (KeyError, TypeError, ValueError) as e:
            raise DataError("schema", "clob", resp.url, f"/book: unparseable levels ({e})", retryable=False) from None
        nb["fetched_at"] = self.clock()
        return nb


__all__ = ["Sources", "ActivityPage", "validate_activity_row", "jlist", "DATA", "GAMMA", "CLOB"]
