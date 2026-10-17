"""Config validation, idempotent migrations, deterministic fill ids, maker/taker inference."""
from __future__ import annotations

import copy

import pytest

from alerts.config import ConfigError, load_config, parse_config
from alerts.fills import OccurrenceCounter, fee_role, to_fill, trade_key
from alerts.store import SCHEMA_VERSION, Store

from .conftest import MINTBLADE, SECOND, base_config, load_fixture


def test_example_config_loads_and_is_informational() -> None:
    cfg = load_config("alerts/config.example.yaml")
    assert len(cfg.wallets) == 3
    assert all(w.address == w.address.lower() for w in cfg.wallets)
    assert cfg.copy_candidate.enabled is False            # informational by default
    assert cfg.notifications.channels["telegram"].enabled is False
    assert cfg.notifications.channels["email"].enabled is False
    assert cfg.notifications.channels["file"].path.endswith(".ndjson")
    assert cfg.min_usdc(cfg.wallets[0]) == 1000


@pytest.mark.parametrize("mutate, msg", [
    (lambda d: d["wallets"][0].update(address="0x123"), "not a 0x-prefixed"),
    (lambda d: d["wallets"][0].update(cluster_confidence="sure"), "cluster_confidence"),
    (lambda d: d["wallets"].append(dict(d["wallets"][0])), "duplicate address"),
    (lambda d: d["poll"].update(min_usd=5), "unknown key"),
    (lambda d: d["poll"].update(page_limit=5000), "page_limit"),
    (lambda d: d.update(notifications={"channels": {"file": {"enabled": True, "path": "x.jsonl"}}}), ".jsonl"),
    (lambda d: d.update(notifications={"channels": {"console": {"enabled": False}, "file": {"enabled": False}}}),
     "enable at least one"),
    (lambda d: d["wallets"][0].update(thresholds={"min_usd": 1}), "unknown key"),
    (lambda d: d.update(alerting={"alert_sides": ["HOLD"]}), "alert_sides"),
])
def test_config_rejects_mistakes(mutate, msg) -> None:
    d = copy.deepcopy(base_config())
    mutate(d)
    with pytest.raises(ConfigError, match=msg):
        parse_config(d)


def test_per_wallet_thresholds_override_globals() -> None:
    d = base_config(alerting={"min_usdc": 50, "alert_sides": ["BUY"]})
    d["wallets"][1]["thresholds"] = {"min_usdc": 5000, "alert_sides": ["BUY", "SELL"]}
    cfg = parse_config(d)
    assert cfg.min_usdc(cfg.wallet(MINTBLADE)) == 50
    assert cfg.min_usdc(cfg.wallet(SECOND)) == 5000
    assert cfg.alert_sides(cfg.wallet(SECOND)) == ("BUY", "SELL")


def test_migrations_are_idempotent(tmp_path) -> None:
    p = tmp_path / "a.sqlite"
    s = Store(p)
    s.conn.execute("INSERT INTO meta (key, value) VALUES ('x', '1')")
    assert s.migrate() == SCHEMA_VERSION
    assert s.migrate() == SCHEMA_VERSION
    s.close()
    s2 = Store(p)                                         # reopen runs migrate() again
    assert s2.get_meta("x") == "1"
    assert s2.q1("PRAGMA user_version")[0] == SCHEMA_VERSION
    assert s2.count("schema_migrations") == 1
    tables = {r[0] for r in s2.q("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"wallets", "fills", "bets", "alerts", "deliveries", "poll_state", "health_events"} <= tables


def test_fill_id_is_deterministic_and_keeps_true_repeats(mint_rows) -> None:
    row = next(r for r in mint_rows if r["type"] == "TRADE")
    a = to_fill(row, OccurrenceCounter(), seen_at=1.0, poll_mode="live")
    b = to_fill(copy.deepcopy(row), OccurrenceCounter(), seen_at=2.0, poll_mode="live")
    assert a["fill_id"] == b["fill_id"]                   # same row, different fetch -> same id
    occ = OccurrenceCounter()
    twins = [to_fill(row, occ, seen_at=1.0, poll_mode="live") for _ in range(2)]
    assert twins[0]["fill_id"] == a["fill_id"] and twins[1]["fill_id"] != a["fill_id"]
    other = dict(row, size=row["size"] + 1)
    assert to_fill(other, OccurrenceCounter(), seen_at=1, poll_mode="live")["fill_id"] != a["fill_id"]
    # every recorded row maps to a distinct id
    occ = OccurrenceCounter()
    ids = [to_fill(r, occ, seen_at=1, poll_mode="live")["fill_id"] for r in mint_rows]
    assert len(ids) == len(set(ids)) == len(mint_rows)


def test_fee_embedded_rows_are_takers_on_recorded_data(second_rows) -> None:
    """Recorded evidence for the inference rule: every fill whose usdc_size differs from
    size*price is in the wallet's /v2/trades taker-only set."""
    taker = {(r["transaction_hash"].lower(), r["token_id"], r["side"], float(r["size"]), float(r["price"]),
              int(r["timestamp"])) for r in load_fixture("trades_taker_second.json")["data"]}
    occ = OccurrenceCounter()
    fills = [to_fill(r, occ, seen_at=1, poll_mode="live") for r in second_rows if r["type"] == "TRADE"]
    fee_rows = [f for f in fills if f["liquidity_role"] == "taker"]
    assert fee_rows, "fixture should contain fee-paying fills"
    assert all(trade_key(f) in taker for f in fee_rows)
    # BUY takers pay more than notional, SELL takers receive less
    assert any(f["side"] == "SELL" for f in fee_rows) and any(f["side"] == "BUY" for f in fee_rows)
    for f in fee_rows:
        assert f["fee_usdc"] > 0


def test_fee_role_basic() -> None:
    base = {"type": "TRADE", "size": 100.0, "price": 0.5}
    assert fee_role({**base, "side": "BUY", "usdc_size": 50.75}) == ("taker", pytest.approx(0.75))
    assert fee_role({**base, "side": "SELL", "usdc_size": 49.25}) == ("taker", pytest.approx(0.75))
    assert fee_role({**base, "side": "BUY", "usdc_size": 50.0}) == ("unknown", 0.0)
    assert fee_role({"type": "MERGE", "size": 1, "price": 0, "side": "", "usdc_size": 1})[0] == "n/a"
