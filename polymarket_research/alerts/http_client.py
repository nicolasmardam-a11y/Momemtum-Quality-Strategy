"""Thin HTTP layer for the alert system.

Why not ``pmr.http.request_json``: the research client retries up to six times with
sleeps of up to 60 s and writes every response to data/raw/. That is right for
batch research and wrong for a 30-second poll loop (a single outage could block a
cycle for minutes and the raw dump would grow by thousands of files a day). This
layer uses short timeouts, at most ``retries`` quick retries honouring
``Retry-After``, and raises a classified :class:`DataError` for every failure. It
never returns a partial or default value in place of an error.

The transport is injectable so the tests can replay recorded payloads and inject
timeouts, HTTP errors and malformed bodies without touching the network.
"""
from __future__ import annotations

import email.utils
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

import requests

USER_AGENT = "pmr-alerts/0.1 (read-only public data; no trading)"

# Per-host minimum spacing between requests (requests per second). Far below the
# documented Cloudflare limits (Data API /v2/activity 200 per 10 s, CLOB /book 1,500
# per 10 s, Gamma /markets 300 per 10 s; docs /api-reference/rate-limits).
DEFAULT_RPS = {
    "data-api.polymarket.com": 5.0,
    "gamma-api.polymarket.com": 5.0,
    "clob.polymarket.com": 10.0,
}
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504, 520, 522, 524}


class TransportTimeout(Exception):
    """The transport did not get a response within the timeout."""


class TransportError(Exception):
    """Connection-level failure (DNS, reset, TLS, proxy)."""


@dataclass
class RawResponse:
    status: int
    headers: Mapping[str, str]
    text: str


Transport = Callable[[str, str, Mapping[str, Any] | None, Any, float], RawResponse]


@dataclass
class DataError(Exception):
    """A data failure. ``kind`` is one of: timeout, connection, http_error,
    rate_limited, invalid_request, schema, not_found."""

    kind: str
    source: str
    url: str
    detail: str
    status: int | None = None
    retryable: bool = True
    params: Mapping[str, Any] = field(default_factory=dict)
    retry_after_s: float | None = None

    def __str__(self) -> str:
        st = f" HTTP {self.status}" if self.status is not None else ""
        return f"{self.kind}{st} from {self.source} {urlparse(self.url).path}: {self.detail}"


@dataclass
class Response:
    status: int
    body: Any
    headers: Mapping[str, str]
    server_time: float | None   # from the HTTP Date header (server clock), epoch seconds
    elapsed_s: float
    url: str


def requests_transport(session: requests.Session | None = None) -> Transport:
    s = session or requests.Session()
    s.headers["User-Agent"] = USER_AGENT

    def _send(method: str, url: str, params: Mapping[str, Any] | None, json_body: Any, timeout: float) -> RawResponse:
        try:
            r = s.request(method, url, params=params, json=json_body, timeout=(min(5.0, timeout), timeout))
        except requests.Timeout as e:
            raise TransportTimeout(type(e).__name__) from None
        except requests.RequestException as e:
            raise TransportError(f"{type(e).__name__}: {str(e)[:300]}") from None
        return RawResponse(r.status_code, {k.lower(): v for k, v in r.headers.items()}, r.text)

    return _send


def _parse_retry_after(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return max(0.0, float(v))
    except ValueError:
        try:
            dt = email.utils.parsedate_to_datetime(v)
            return max(0.0, dt.timestamp() - time.time())
        except (TypeError, ValueError):
            return None


def _parse_date(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return email.utils.parsedate_to_datetime(v).timestamp()
    except (TypeError, ValueError):
        return None


class HttpClient:
    def __init__(
        self,
        transport: Transport | None = None,
        *,
        timeout: float = 15.0,
        retries: int = 2,
        backoff_s: float = 1.0,
        max_retry_after_s: float = 20.0,
        rps: Mapping[str, float] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.transport = transport or requests_transport()
        self.timeout = timeout
        self.retries = retries
        self.backoff_s = backoff_s
        self.max_retry_after_s = max_retry_after_s
        self.rps = dict(DEFAULT_RPS if rps is None else rps)
        self.sleep = sleep
        self.monotonic = monotonic
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}
        self.calls = 0

    def _throttle(self, host: str) -> None:
        rate = self.rps.get(host)
        if not rate:
            return
        with self._lock:
            wait = self._last.get(host, -1e9) + 1.0 / rate - self.monotonic()
            if wait > 0:
                self.sleep(wait)
            self._last[host] = self.monotonic()

    def get_json(self, url: str, params: Mapping[str, Any] | None = None, *, source: str | None = None,
                 allow_404: bool = False) -> Response:
        return self.request_json("GET", url, params, source=source, allow_404=allow_404)

    def request_json(self, method: str, url: str, params: Mapping[str, Any] | None = None, *,
                     json_body: Any = None, source: str | None = None, allow_404: bool = False) -> Response:
        host = urlparse(url).netloc
        source = source or host
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        last: DataError | None = None
        for attempt in range(self.retries + 1):
            if attempt:
                delay = self.backoff_s * (2 ** (attempt - 1))
                if last is not None and last.retry_after_s is not None:
                    delay = min(self.max_retry_after_s, max(delay, last.retry_after_s))
                self.sleep(delay)
            self._throttle(host)
            t0 = self.monotonic()
            self.calls += 1
            try:
                raw = self.transport(method, url, clean, json_body, self.timeout)
            except TransportTimeout as e:
                last = DataError("timeout", source, url, f"no response within {self.timeout:.0f}s ({e})", params=clean)
                continue
            except TransportError as e:
                last = DataError("connection", source, url, str(e), params=clean)
                continue
            elapsed = self.monotonic() - t0
            if raw.status in RETRY_STATUS:
                kind = "rate_limited" if raw.status == 429 else "http_error"
                last = DataError(kind, source, url, _error_detail(raw.text), status=raw.status, params=clean,
                                 retry_after_s=_parse_retry_after(raw.headers.get("retry-after")))
                continue
            if raw.status == 404 and allow_404:
                return Response(404, _safe_json(raw.text), raw.headers, _parse_date(raw.headers.get("date")), elapsed, url)
            if raw.status >= 400:
                kind = "not_found" if raw.status == 404 else ("invalid_request" if raw.status < 500 else "http_error")
                raise DataError(kind, source, url, _error_detail(raw.text), status=raw.status,
                                retryable=False, params=clean)
            try:
                body = json.loads(raw.text)
            except (json.JSONDecodeError, TypeError) as e:
                raise DataError("schema", source, url, f"response is not JSON ({e}); starts {raw.text[:120]!r}",
                                status=raw.status, retryable=False, params=clean) from None
            return Response(raw.status, body, raw.headers, _parse_date(raw.headers.get("date")), elapsed, url)
        assert last is not None
        last.detail += f" (after {self.retries + 1} attempts)"
        raise last


def _safe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _error_detail(text: str) -> str:
    """Prefer the Data API error envelope ({error, code, retryable, trace_id})."""
    j = _safe_json(text)
    if isinstance(j, dict) and "error" in j:
        parts = [str(j.get("error"))]
        if j.get("code"):
            parts.append(f"code={j['code']}")
        if j.get("trace_id"):
            parts.append(f"trace_id={j['trace_id']}")
        return " ".join(parts)[:400]
    return (text or "")[:200]
