"""HTTP access with per-host rate limiting, retries and raw-response provenance.

Every response is written to data/raw/<source>/... as gzipped JSON together with
the request URL, params, UTC fetch time, HTTP status and elapsed time, so any
derived number can be traced back to the exact payload it came from.

Cached reads (cache=True) are only appropriate for immutable history (resolved
markets, past trades). Live data (books, open positions) must use cache=False;
it is still recorded under data/raw/<source>/live/<YYYYMMDD>/.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# Requests per second per host, per process. Several research processes share one
# IP, so these sit well below the documented Cloudflare limits
# (docs.polymarket.com/api-reference/rate-limits, checked 2026-10-17).
# Scale all of them with PMR_RATE_SCALE (e.g. 2.0 for a single heavy collector).
_DEFAULT_RPS = {
    "data-api.polymarket.com": 6.0,
    "gamma-api.polymarket.com": 8.0,
    "clob.polymarket.com": 15.0,
    "crypto-clickhouse.clickhouse.com": 1.0,
    "polygon-bor-rpc.publicnode.com": 4.0,
    "api.elections.kalshi.com": 4.0,
    "data-api.binance.vision": 5.0,
}
_RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504, 520, 522, 524}

_session = requests.Session()
_session.headers["User-Agent"] = "pmr-research/0.1 (read-only public data)"
_locks: dict[str, threading.Lock] = {}
_last: dict[str, float] = {}


def _throttle(host: str) -> None:
    rps = _DEFAULT_RPS.get(host, 4.0) * float(os.environ.get("PMR_RATE_SCALE", "1"))
    lock = _locks.setdefault(host, threading.Lock())
    with lock:
        wait = _last.get(host, 0.0) + 1.0 / rps - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.monotonic()


def _key(method: str, url: str, params, body) -> str:
    blob = json.dumps([method, url, params, body], sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()


def _write(path: Path, meta: dict, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as f:
        json.dump({"meta": meta, "body": payload}, f)
    tmp.replace(path)


def request_json(
    url: str,
    params: dict | None = None,
    *,
    method: str = "GET",
    json_body=None,
    data: str | None = None,
    source: str | None = None,
    cache: bool = False,
    timeout: float = 60,
    retries: int = 6,
    parse: str = "json",
):
    """Fetch a URL and return the parsed body, recording the raw response.

    cache=True returns a previously stored response for the identical request
    without touching the network. 4xx responses other than 408/425/429 raise
    immediately; transient failures are retried with exponential backoff.
    """
    host = urlparse(url).netloc
    source = source or host.split(".")[0]
    params = {k: v for k, v in (params or {}).items() if v is not None}
    k = _key(method, url, params, json_body if json_body is not None else data)
    cached = RAW / source / "cache" / k[:2] / f"{k}.json.gz"
    if cache and cached.exists():
        with gzip.open(cached, "rt") as f:
            return json.load(f)["body"]

    err = None
    for attempt in range(retries):
        _throttle(host)
        t0 = time.monotonic()
        try:
            r = _session.request(method, url, params=params, json=json_body, data=data, timeout=timeout)
        except requests.RequestException as e:  # connection reset, timeout
            err = e
            time.sleep(min(60, 2 ** attempt))
            continue
        if r.status_code in _RETRY_STATUS:
            err = RuntimeError(f"HTTP {r.status_code} {url} {r.text[:200]}")
            time.sleep(min(60, 2 ** attempt))
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code} {url} {params} {r.text[:500]}")
        payload = r.json() if parse == "json" else r.text
        now = datetime.now(timezone.utc)
        meta = {
            "url": url,
            "method": method,
            "params": params,
            "body": json_body if json_body is not None else data,
            "fetched_at_utc": now.isoformat(),
            "status": r.status_code,
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }
        if cache:
            _write(cached, meta, payload)
        else:
            live = RAW / source / "live" / now.strftime("%Y%m%d") / f"{now.strftime('%H%M%S%f')}_{k[:12]}.json.gz"
            _write(live, meta, payload)
        return payload
    raise RuntimeError(f"giving up on {url} {params}: {err}")
