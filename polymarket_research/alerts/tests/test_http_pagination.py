"""HTTP error classification, retries, and complete cursor pagination."""
from __future__ import annotations

import pytest

from alerts.http_client import DataError, HttpClient
from alerts.sources import Sources

from .conftest import SECOND, Clock, FakeApi, load_fixture

T0 = 1_792_250_000.0
TYPES = ("TRADE", "SPLIT", "MERGE", "REDEEM", "CONVERSION")


def client(api: FakeApi, retries: int = 0, sleeps: list | None = None) -> Sources:
    sl = sleeps if sleeps is not None else []
    return Sources(HttpClient(api, retries=retries, sleep=sl.append, rps={}), clock=api.clock)


def test_follows_recorded_live_cursors_to_the_end() -> None:
    """Replays a genuine 3-page keyset walk (limit=4) recorded from the live API."""
    api = FakeApi(Clock(T0))
    pages = load_fixture("activity_pages_live.json")
    api.live_pages = {p["request"].get("cursor"): p["body"] for p in pages}
    out = list(client(api).iter_activity(SECOND, start=pages[0]["request"]["start"], types=TYPES, limit=4))
    assert [len(p.rows) for p in out] == [len(p["body"]["data"]) for p in pages]
    assert out[-1].next_cursor is None
    # the cursor sent on page n is exactly the next_cursor returned on page n-1
    sent = [params.get("cursor") for url, params in api.calls]
    assert sent == [None] + [p["body"]["pagination"]["next_cursor"] for p in pages[:-1]]
    # filters are re-sent on every page (the cursor carries only the seek anchor)
    assert all(params["type"] == ",".join(TYPES) and params["sort_direction"] == "ASC" for _, params in api.calls)


def test_full_pagination_returns_every_row(second_rows) -> None:
    api = FakeApi(Clock(T0))
    api.add_activity(SECOND, second_rows)
    pages = list(client(api).iter_activity(SECOND, start=1, types=TYPES, limit=7))
    got = [r for p in pages for r in p.rows]
    assert len(got) == len(second_rows) and len(pages) == -(-len(second_rows) // 7)
    ts = [r["timestamp"] for r in got]
    assert ts == sorted(ts)                                # oldest first


def test_cache_bust_end_param_and_inclusive_start(second_rows) -> None:
    api = FakeApi(Clock(T0))
    api.add_activity(SECOND, second_rows)
    t = second_rows[10]["timestamp"]
    rows = [r for p in client(api).iter_activity(SECOND, start=t, types=TYPES) for r in p.rows]
    assert min(r["timestamp"] for r in rows) == t          # start is inclusive
    assert api.calls[0][1]["end"] == int(T0) + 86_400      # unique per second -> CDN miss


def test_repeated_cursor_and_truncation_are_errors(second_rows) -> None:
    api = FakeApi(Clock(T0))
    api.add_activity(SECOND, second_rows)
    with pytest.raises(DataError, match="max_pages"):
        list(client(api).iter_activity(SECOND, start=1, types=TYPES, limit=5, max_pages=3))
    loop = {"data": [], "pagination": {"has_more": True, "limit": 1, "offset": 0, "next_cursor": "same"}}
    api.live_pages = {None: loop, "same": loop}
    with pytest.raises(DataError, match="repeated"):
        list(client(api).iter_activity(SECOND, start=1, types=TYPES))
    api.live_pages = {None: {"data": [], "pagination": {"has_more": True, "limit": 1, "offset": 0, "next_cursor": None}}}
    with pytest.raises(DataError, match="has_more=true without next_cursor"):
        list(client(api).iter_activity(SECOND, start=1, types=TYPES))


def test_schema_surprises_are_detected(second_rows) -> None:
    api = FakeApi(Clock(T0))
    api.fail("/v2/activity", "missing_field")
    with pytest.raises(DataError) as e:
        list(client(api).iter_activity(SECOND, start=1, types=TYPES))
    assert e.value.kind == "schema"
    api.fail("/v2/activity", "bad_json")
    with pytest.raises(DataError, match="not JSON"):
        list(client(api).iter_activity(SECOND, start=1, types=TYPES))
    bad = dict(second_rows[0], proxy_wallet="0x" + "1" * 40)
    api.add_activity(SECOND, [bad])
    with pytest.raises(DataError, match="proxy_wallet"):
        list(client(api).iter_activity(SECOND, start=1, types=TYPES))


def test_retries_honour_retry_after_then_classify() -> None:
    api = FakeApi(Clock(T0))
    sleeps: list[float] = []
    api.fail("/v2/status", 503)
    st = client(api, retries=2, sleeps=sleeps).status()     # one 503, then success
    assert st["lag_seconds"] is not None and sleeps == [1.0]
    api.fail("/v2/status", "timeout", times=3)
    with pytest.raises(DataError) as e:
        client(api, retries=2).status()
    assert e.value.kind == "timeout" and "after 3 attempts" in e.value.detail
    api.fail("/v2/status", 429, times=1)
    with pytest.raises(DataError) as e:
        client(api, retries=0).status()
    assert e.value.kind == "rate_limited" and e.value.retry_after_s == 1.0


def test_4xx_is_not_retried_and_keeps_error_envelope() -> None:
    body = load_fixture("error_invalid_cursor.json")             # live 400 envelope

    class Api(FakeApi):
        def __call__(self, method, url, params, json_body, timeout):
            self.calls.append((url, params))
            return self._json(body, 400)

    api = Api(Clock(T0))
    with pytest.raises(DataError) as e:
        list(client(api, retries=3).iter_activity(SECOND, start=1, types=TYPES))
    assert e.value.kind == "invalid_request" and "invalid cursor" in e.value.detail and "trace_id" in e.value.detail
    assert len(api.calls) == 1


def test_server_date_header_is_parsed() -> None:
    api = FakeApi(Clock(T0))
    r = HttpClient(api, rps={}).get_json("https://data-api.polymarket.com/v2/status")
    assert r.server_time == pytest.approx(T0, abs=1)
