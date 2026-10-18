"""CLI entry point (--once, --report, loop) and the periodic digest/heartbeat."""
from __future__ import annotations

import json

import yaml

from alerts import run as run_mod
from alerts.http_client import HttpClient

from .conftest import MINTBLADE, SECOND, Clock, FakeApi, Harness, add_dormant, base_config, load_fixture


def write_cfg(tmp_path, **over) -> str:
    d = base_config(**over)
    d["notifications"] = {"channels": {"console": {"enabled": True},
                                       "file": {"enabled": True, "path": str(tmp_path / "out.ndjson")}}}
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(d))
    return str(p)


def patch_http(monkeypatch, api: FakeApi) -> None:
    monkeypatch.setattr(run_mod, "HttpClient", lambda **kw: HttpClient(api, retries=0, sleep=lambda s: None, rps={}))


def test_cli_once_report_and_exit_codes(tmp_path, monkeypatch, capsys) -> None:
    import time
    api = FakeApi(Clock(time.time()))          # the CLI uses the real clock; the fake API's Date header follows it
    api.clock = time.time
    rows = load_fixture("activity_second.json")
    api.add_activity(SECOND, rows)
    add_dormant(api, MINTBLADE, int(time.time()) - 40 * 86400)    # a dormant account, not an unknown address
    patch_http(monkeypatch, api)
    cfg = write_cfg(tmp_path)
    db = str(tmp_path / "cli.sqlite")
    assert run_mod.main(["--config", cfg, "--once", "--db", db, "--backfill-hours", "100000"]) == 0
    assert run_mod.main(["--config", cfg, "--report", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "poll_state:" in out and "second" in out and "open data problems: 0" in out
    api.fail("/v2/activity", 500, times=5)
    assert run_mod.main(["--config", cfg, "--once", "--db", db]) == 3          # data problem -> non-zero
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 1\nwallets: [{address: '0xnope', label: x}]\n")
    assert run_mod.main(["--config", str(bad), "--once", "--db", db]) == 2


def test_cli_loop_runs_bounded_cycles_with_dispatcher_thread(tmp_path, monkeypatch) -> None:
    import time
    api = FakeApi(Clock(time.time()))
    api.clock = time.time
    patch_http(monkeypatch, api)
    cfg = write_cfg(tmp_path)
    db = str(tmp_path / "loop.sqlite")
    t0 = time.monotonic()
    assert run_mod.main(["--config", cfg, "--db", db, "--interval", "1", "--max-cycles", "2"]) == 0
    assert time.monotonic() - t0 < 20
    # 2 wallets x 2 cycles, plus one full-history probe per wallet at bootstrap (empty window; review fix)
    assert api.count("/v2/activity") == 6


def test_digest_every_interval_once(tmp_path, second_rows) -> None:
    base = 1_792_250_000
    picked = [r for r in second_rows if r["type"] != "TRADE" or r["side"] == "SELL"][-6:]
    rows = [dict(r, timestamp=base + 60 * i) for i, r in enumerate(picked)]    # rebased onto one hour
    d = base_config(health={"digest_interval_hours": 24}, poll={"gap_horizon_hours": 48})
    h = Harness(tmp_path, base - 60, d, wallets=[SECOND])
    h.engine.run_cycle()                                      # first cycle only initialises the digest clock
    assert h.alerts("DIGEST") == []
    h.api.add_activity(SECOND, rows)
    h.clock.t = rows[-1]["timestamp"] + 30
    h.engine.run_cycle()
    assert h.alerts("DIGEST") == []
    h.clock.t = base - 60 + 24 * 3600 + 1
    h.engine.run_cycle()
    dig = h.alerts("DIGEST")
    assert len(dig) == 1
    p = json.loads(dig[0]["payload_json"])
    assert p["polls_ok"] == 2 and p["polls_failed"] == 0 and p["wallets"] == 1
    assert p["fills_total"] == len(rows)
    assert p["non_buy_summary"], "sells/merges/redeems are summarised in the digest"
    assert "[DIGEST]" in dig[0]["text"] and "No new trades is a normal outcome" in dig[0]["text"]
    h.clock.advance(30)
    h.engine.run_cycle()
    assert len(h.alerts("DIGEST")) == 1                       # not repeated within the interval


def test_wallet_removed_from_config_is_disabled(tmp_path) -> None:
    h = Harness(tmp_path, 1_792_250_000)
    assert h.store.count("wallets", "enabled = 1") == 2
    h.store.upsert_wallets([w for w in h.cfg.wallets if w.address == MINTBLADE], 1_792_250_100)
    assert h.store.count("wallets", "enabled = 1") == 1 and h.store.count("wallets") == 2
