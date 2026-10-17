"""Shared test harness: a fake public-API transport backed by recorded fixtures.

``FakeApi`` implements the Data API v2 semantics verified on 2026-10-17 over the
recorded rows: inclusive ``start``/``end`` on block timestamp, ``type`` filter,
``sort_direction``, keyset cursors (opaque here; the real ones are signed), the
``{data, pagination}`` envelope, and an HTTP ``Date`` header from a fake clock. It
can inject timeouts, HTTP errors and schema surprises, and it records every call.
No test touches the network.
"""
from __future__ import annotations

import base64
import copy
import email.utils
import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alerts.config import parse_config  # noqa: E402
from alerts.engine import Engine  # noqa: E402
from alerts.http_client import HttpClient, RawResponse, TransportError, TransportTimeout  # noqa: E402
from alerts.notify import ConsoleNotifier, FileNotifier  # noqa: E402
from alerts.sources import Sources  # noqa: E402
from alerts.store import Store  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
MINTBLADE = "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb"
SECOND = "0xc8c1f765515347a725afff5faa4f5632dd8d1e41"


def load_fixture(name: str) -> Any:
    return json.loads((FIX / name).read_text())["body"]


class Clock:
    def __init__(self, t: float) -> None:
        self.t = float(t)

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


class FakeApi:
    """Callable transport: (method, url, params, json_body, timeout) -> RawResponse."""

    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.activity: dict[str, list[dict]] = {}     # wallet -> rows (visible now), in ingestion order
        self.calls: list[tuple[str, dict]] = []
        self.faults: list[tuple[str, Any]] = []        # (path substring, fault) consumed in order
        self.status_body = load_fixture("status.json")
        self.gamma: dict[str, dict] = {}
        self.clob_markets: dict[str, dict] = {}
        self.books: dict[str, dict] = {}
        self.positions_by_condition: dict[tuple[str, str], list[dict]] = {}
        self.positions_by_event: dict[tuple[str, str], list[dict]] = {}
        self.taker_rows: dict[str, list[dict]] = {}
        self.live_pages: dict[str | None, dict] | None = None

    # -------------------------------------------------------------- setup helpers
    def add_activity(self, wallet: str, rows: list[dict]) -> None:
        self.activity.setdefault(wallet, []).extend(copy.deepcopy(rows))

    def fail(self, path_sub: str, fault: Any, times: int = 1, after: int = 0) -> None:
        """Inject ``fault`` on the next ``times`` matching calls, after letting ``after`` through."""
        self.faults.extend([(path_sub, ("pass", None))] * after + [(path_sub, fault)] * times)

    def count(self, path_sub: str) -> int:
        return sum(1 for u, _ in self.calls if path_sub in u)

    # -------------------------------------------------------------- transport
    def __call__(self, method: str, url: str, params: dict | None, json_body: Any, timeout: float) -> RawResponse:
        params = dict(params or {})
        self.calls.append((url, params))
        for i, (sub, fault) in enumerate(self.faults):
            if sub in url:
                self.faults.pop(i)
                if fault != ("pass", None):
                    return self._fault(fault)
                break
        path = url.split("polymarket.com", 1)[1]
        if path == "/v2/activity":
            if self.live_pages is not None:
                return self._json(self.live_pages[params.get("cursor")])
            return self._activity(params)
        if path == "/v2/status":
            return self._json(self.status_body)
        if path == "/v2/trades":
            return self._trades(params)
        if path == "/v2/positions":
            key = params.get("condition") or params.get("event_id")
            table = self.positions_by_condition if params.get("condition") else self.positions_by_event
            rows = table.get((params["user"], key), [])
            return self._json({"data": rows, "pagination": {"has_more": False, "limit": 100, "offset": 0, "next_cursor": None}})
        if path == "/markets" and "gamma-api" in url:
            m = self.gamma.get(params["condition_ids"])
            want_closed = params.get("closed") == "true"
            hit = [m] if m is not None and bool(m.get("closed")) == want_closed else []
            return self._json(hit)
        if path.startswith("/markets/"):
            cid = path.split("/markets/", 1)[1]
            return self._json(self.clob_markets[cid]) if cid in self.clob_markets else self._json(
                {"error": "market not found"}, 404)
        if path == "/book":
            b = self.books.get(params["token_id"])
            return self._json(b) if b else self._json({"error": "No orderbook exists for the requested token id"}, 404)
        raise AssertionError(f"unexpected request {url} {params}")

    def _json(self, body: Any, status: int = 200, headers: dict | None = None) -> RawResponse:
        h = {"content-type": "application/json", "date": email.utils.formatdate(self.clock(), usegmt=True)}
        h.update(headers or {})
        return RawResponse(status, h, json.dumps(body))

    def _fault(self, fault: Any) -> RawResponse:
        if fault == "timeout":
            raise TransportTimeout("ReadTimeout")
        if fault == "connection":
            raise TransportError("ConnectionError: reset by peer")
        if fault == "bad_json":
            return RawResponse(200, {"date": email.utils.formatdate(self.clock(), usegmt=True)}, "<html>oops</html>")
        if fault == "missing_field":
            return self._json({"data": [{"proxy_wallet": MINTBLADE, "timestamp": 1}],
                               "pagination": {"has_more": False, "limit": 1, "offset": 0, "next_cursor": None}})
        if isinstance(fault, int):
            body = {"error": "synthetic failure", "code": "internal" if fault >= 500 else "rate_limited",
                    "retryable": True, "trace_id": "test"}
            return self._json(body, fault, {"retry-after": "1"} if fault in (429, 503) else None)
        raise AssertionError(fault)

    def _activity(self, params: dict) -> RawResponse:
        wallet = params["user"].lower()
        rows = self.activity.get(wallet, [])
        types = set(params.get("type", "").split(",")) if params.get("type") else None
        start = int(params.get("start") or 0)
        end = int(params.get("end") or 4_000_000_000)
        indexed = [(r["timestamp"], i, r) for i, r in enumerate(rows)
                   if start <= r["timestamp"] <= end and (types is None or r["type"] in types)]
        asc = (params.get("sort_direction") or "DESC").upper() == "ASC"
        indexed.sort(key=lambda t: (t[0], t[1]), reverse=not asc)
        limit = int(params.get("limit") or 100)
        if params.get("cursor"):
            cur = json.loads(base64.urlsafe_b64decode(params["cursor"]))
            anchor = (cur["ts"], cur["sq"])
            limit = cur["l"]
            indexed = [t for t in indexed if ((t[0], t[1]) > anchor if asc else (t[0], t[1]) < anchor)]
        page = indexed[:limit]
        more = len(indexed) > limit
        nxt = None
        if more:
            nxt = base64.urlsafe_b64encode(json.dumps({"ts": page[-1][0], "sq": page[-1][1], "l": limit}).encode()).decode()
        return self._json({"data": [copy.deepcopy(t[2]) for t in page],
                           "pagination": {"has_more": more, "limit": limit, "offset": 0, "next_cursor": nxt}})

    def _trades(self, params: dict) -> RawResponse:
        rows = [r for r in self.taker_rows.get(params["user"].lower(), [])
                if int(params.get("start") or 0) <= r["timestamp"] <= int(params.get("end") or 4_000_000_000)]
        return self._json({"data": rows, "pagination": {"has_more": False, "limit": 1000, "offset": 0, "next_cursor": None}})


def base_config(**overrides: Any) -> dict:
    """A config dict for tests: both fixture wallets, console+file notifiers, no thresholds."""
    cfg = {
        "version": 1,
        "wallets": [
            {"address": MINTBLADE, "label": "mintblade", "cluster_id": "c1", "cluster_confidence": "weak",
             "cluster_note": "test note"},
            {"address": SECOND, "label": "second", "cluster_confidence": "none"},
        ],
        "poll": {"interval_seconds": 30, "jitter_seconds": 0, "overlap_seconds": 600, "page_limit": 50,
                 "initial_backfill_hours": 24, "retries": 0},
        "alerting": {"max_alert_age_minutes": 360},
        "health": {"notify_after_consecutive_failures": 2},
        "notifications": {"channels": {"console": {"enabled": True}, "file": {"enabled": False}}},
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v
    return cfg


class Harness:
    def __init__(self, tmp_path: Path, t0: float, cfg_dict: dict | None = None, wallets: list[str] | None = None,
                 db_name: str = "alerts.sqlite", api: FakeApi | None = None) -> None:
        self.tmp_path = tmp_path
        self.clock = Clock(t0) if api is None else api.clock
        self.api = api or FakeApi(self.clock)
        d = cfg_dict or base_config()
        if wallets is not None:
            d = {**d, "wallets": [w for w in d["wallets"] if w["address"] in wallets]}
        self.cfg = parse_config(d)
        self.db_path = str(tmp_path / db_name)
        self.out = io.StringIO()
        self.file_path = tmp_path / "alerts.ndjson"
        self.notifiers = {"console": ConsoleNotifier(self.out), "file": FileNotifier(self.file_path)}
        self.open()

    def open(self) -> None:
        self.store = Store(self.db_path)
        http = HttpClient(self.api, retries=self.cfg.poll.retries, sleep=lambda s: None, rps={})
        self.sources = Sources(http, clock=self.clock)
        self.engine = Engine(self.cfg, self.store, self.sources, self.notifiers, clock=self.clock)

    def restart(self) -> None:
        """Simulate a process restart: new connection, new engine, same DB file."""
        self.store.close()
        self.open()

    def alerts(self, kind: str | None = None) -> list:
        if kind:
            return self.store.q("SELECT * FROM alerts WHERE kind = ? ORDER BY alert_id", (kind,))
        return self.store.q("SELECT * FROM alerts ORDER BY alert_id")


@pytest.fixture
def mint_rows() -> list[dict]:
    return load_fixture("activity_mintblade.json")


@pytest.fixture
def second_rows() -> list[dict]:
    return load_fixture("activity_second.json")
