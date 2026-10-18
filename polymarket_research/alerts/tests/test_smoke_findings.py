"""Findings of the live smoke test (2026-10-18, notes/alerts_smoke_test.md).

Combo (multi-leg RFQ) fills reached the alert path with lookups that cannot succeed:
/v2/positions answered 400 "invalid condition id" (raised as a DATA PROBLEM), CLOB /book
404 was rendered as "market closed or not tradable", and the fee-free fill was labelled
"maker" because combo fills never appear in the taker-only /v2/trades feed.
"""
from __future__ import annotations

import json

from alerts.enrich import is_combo

from .conftest import SECOND, Harness, load_fixture

# Shape observed live: 34 hex digits, then zeros; title joins two markets with " AND ".
COMBO_CID = "0x037a734069bd6aa8e2d3876752879da2cd" + "0" * 30


def _combo_row() -> dict:
    rows = load_fixture("activity_second.json")
    base = [r for r in rows if r["type"] == "TRADE" and r["side"] == "BUY"][-1]
    size, price = 51.5, 0.963
    return dict(base, condition_id=COMBO_CID, is_combo=True, size=size, price=price,
                usdc_size=round(size * price, 6), transaction_hash="0x" + "c0" * 32,
                title="Match A: X vs Y AND Match B: Z vs W", slug="", event_slug="")  # live: empty strings


def test_is_combo_reads_the_raw_row_flag() -> None:
    assert is_combo([{"raw_json": json.dumps({"is_combo": True})}])
    assert not is_combo([{"raw_json": json.dumps({"is_combo": False})}, {"raw_json": "{}"}])
    assert not is_combo([{"raw_json": "not json"}, {}])


def test_combo_bet_alerts_without_failing_lookups_or_guessing_maker(tmp_path) -> None:
    row = _combo_row()
    h = Harness(tmp_path, row["timestamp"] - 120, wallets=[SECOND])
    h.engine.run_cycle()
    h.api.add_activity(SECOND, [row])
    h.clock.t = row["timestamp"] + 25
    calls = {p: h.api.count(p) for p in ("/book", "/v2/positions", "/markets", "/v2/trades")}
    h.engine.run_cycle()

    a = h.alerts("BET")[0]
    p = json.loads(a["payload_json"])
    en = p["enrichment"]
    assert en["combo"] is True
    assert "[COMBO: multi-leg RFQ position" in a["text"] and row["title"] in a["text"]
    assert "market closed" not in a["text"] and "combo (multi-leg RFQ position)" in a["text"]
    assert en["fills"]["maker_shares"] == 0 and en["fills"]["unknown_role_shares"] == 51.5
    assert "enrichment_errors" not in en
    # No lookup that is structurally bound to fail was made for this bet.
    assert {p_: h.api.count(p_) for p_ in calls} == calls
    assert h.store.count("health_events", "kind = 'enrichment'") == 0
