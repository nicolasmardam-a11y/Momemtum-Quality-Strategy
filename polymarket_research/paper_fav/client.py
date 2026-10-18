"""Thin read-only HTTP client for the hourly job.

It does not use pmr.http: that client stores every raw response, which suits one-off research but would
write tens of thousands of files a day here. Provenance is kept instead by storing the order book that
priced each paper fill (signals.book_json). Every failure raises DataError, so a failed run never looks
like 'no signals'."""
from __future__ import annotations

import threading
import time

import requests

from pmr.api import normalize_book

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
_RPS = {"gamma-api.polymarket.com": 5.0, "clob.polymarket.com": 10.0}


class DataError(RuntimeError):
    pass


class Client:
    def __init__(self, timeout: float = 20.0, retries: int = 3):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "paper-fav/0.1 (read-only public data)"
        self.timeout, self.retries = timeout, retries
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def _throttle(self, host: str) -> None:
        with self._lock:
            wait = self._last.get(host, 0.0) + 1.0 / _RPS.get(host, 4.0) - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.monotonic()

    def _req(self, method: str, url: str, **kw):
        host = url.split("/")[2]
        err = None
        for attempt in range(self.retries):
            self._throttle(host)
            try:
                r = self.s.request(method, url, timeout=self.timeout, **kw)
            except requests.RequestException as e:
                err = e
            else:
                if r.status_code < 400:
                    return r.json()
                if r.status_code not in (408, 425, 429, 500, 502, 503, 504):
                    raise DataError(f"HTTP {r.status_code} {url}: {r.text[:200]}")
                err = f"HTTP {r.status_code}"
            time.sleep(2 ** attempt)
        raise DataError(f"{method} {url} failed after {self.retries} attempts: {err}")

    def markets(self, **params):
        """Yield open-market dicts from Gamma /markets/keyset (closed=false unless given)."""
        params = {"limit": 100, "closed": "false", **params}
        while True:
            j = self._req("GET", f"{GAMMA}/markets/keyset", params=params)
            yield from j.get("markets") or []
            cur = j.get("next_cursor")
            if not cur:
                return
            params["after_cursor"] = cur

    def markets_by_condition(self, condition_ids: list[str], closed: bool) -> list[dict]:
        out = []
        for i in range(0, len(condition_ids), 20):
            chunk = condition_ids[i:i + 20]
            out += self._req("GET", f"{GAMMA}/markets",
                             params=[("condition_ids", c) for c in chunk] + [("closed", str(closed).lower()),
                                                                             ("limit", 100)])
        return out

    def books(self, token_ids: list[str]) -> dict[str, dict]:
        """Fresh order books keyed by asset id (POST /books reorders results, so never rely on order)."""
        out: dict[str, dict] = {}
        for i in range(0, len(token_ids), 100):
            chunk = [{"token_id": t} for t in token_ids[i:i + 100]]
            for b in self._req("POST", f"{CLOB}/books", json=chunk) or []:
                nb = normalize_book(b)
                out[str(nb["asset_id"])] = nb | {"raw_timestamp": b.get("timestamp")}
        return out
