"""Grouping fills into bet events, additions after the gap, non-buy activity."""
from __future__ import annotations

from collections import Counter

from alerts import grouping
from alerts.fills import OccurrenceCounter, to_fills
from alerts.store import Store

from .conftest import SECOND, Harness, base_config

GAP = 600


def load(tmp_path, rows, mode="live", gap=GAP) -> Store:
    s = Store(tmp_path / "g.sqlite")
    s.insert_fills(to_fills(rows, OccurrenceCounter(), seen_at=2e9, poll_mode=mode))
    grouping.assign_pending(s, gap, 2e9)
    return s


def test_mintblade_fills_group_into_five_bets(tmp_path, mint_rows) -> None:
    s = load(tmp_path, mint_rows)
    buys = s.q("SELECT * FROM bets WHERE side = 'BUY' ORDER BY first_ts")
    assert [b["n_fills"] for b in buys] == [1, 36, 11, 5, 30]      # Mets, Uruguay, Spread, Draw, Iran (trimmed)
    assert all(b["kind"] == "new_position" for b in buys)
    assert [b["outcome"] for b in buys] == ["New York Mets", "No", "Saudi Arabia", "Yes", "No"]
    uru = buys[1]
    assert uru["last_ts"] - uru["first_ts"] == 316
    fills = s.q("SELECT * FROM fills WHERE bet_id = ?", (uru["bet_id"],))
    assert abs(sum(f["usdc_size"] for f in fills) - uru["usdc_size"]) < 1e-6
    assert uru["bet_id"] == min(fills, key=lambda f: (f["ts"], f["fill_id"]))["fill_id"]
    redeems = s.q("SELECT * FROM bets WHERE side = 'REDEEM'")
    assert redeems and all(b["kind"] == "redeem" for b in redeems)
    assert s.count("fills", "bet_id IS NULL") == 0


def test_buy_after_the_gap_is_an_addition(tmp_path, second_rows) -> None:
    s = load(tmp_path, second_rows)
    audi = next(r["condition_id"] for r in second_rows if r["title"].startswith("Will Audi"))
    bets = s.q("SELECT * FROM bets WHERE condition_id = ? ORDER BY first_ts", (audi,))
    assert [(b["side"], b["kind"]) for b in bets] == [
        ("BUY", "new_position"), ("BUY", "addition"), ("BUY", "addition"), ("SELL", "reduction")]
    assert bets[1]["prior_bet_id"] == bets[0]["bet_id"] and bets[2]["prior_bet_id"] == bets[1]["bet_id"]
    kinds = Counter(b["kind"] for b in s.q("SELECT kind FROM bets"))
    assert kinds["addition"] >= 10 and kinds["merge"] == 1 and kinds["split"] == 1 and kinds["redeem"] == 2


def test_gap_is_configurable(tmp_path, second_rows) -> None:
    audi = next(r["condition_id"] for r in second_rows if r["title"].startswith("Will Audi"))
    rows = [r for r in second_rows if r["condition_id"] == audi]
    s = load(tmp_path, rows, gap=3 * 3600)
    assert [(b["side"], b["n_fills"]) for b in s.q("SELECT * FROM bets ORDER BY first_ts")] == [("BUY", 3), ("SELL", 1)]


def test_regrouping_is_stable_and_late_fills_attach(tmp_path, mint_rows) -> None:
    uru = [r for r in mint_rows if r["title"].startswith("Will Uruguay win") and r["type"] == "TRADE"]
    late = uru.pop(10)                                      # ingested late, inside the bet's span
    s = load(tmp_path, uru)
    before = s.q("SELECT bet_id, n_fills FROM bets")
    s.insert_fills(to_fills(uru, OccurrenceCounter(), seen_at=2e9, poll_mode="live"))   # re-poll: no-op
    grouping.assign_pending(s, GAP, 2e9)
    assert [tuple(r) for r in s.q("SELECT bet_id, n_fills FROM bets")] == [tuple(r) for r in before]
    s.insert_fills(to_fills([late], OccurrenceCounter(), seen_at=2e9 + 60, poll_mode="live"))
    touched = grouping.assign_pending(s, GAP, 2e9 + 60)
    after = s.q("SELECT * FROM bets")
    assert len(after) == 1 and after[0]["n_fills"] == 36 and touched == [before[0]["bet_id"]]


def test_sells_and_merges_are_recorded_but_do_not_alert(tmp_path, second_rows) -> None:
    rows = second_rows[-30:]
    h = Harness(tmp_path, rows[0]["timestamp"] - 60, wallets=[SECOND])
    h.engine.run_cycle()                                     # empty bootstrap
    h.api.add_activity(SECOND, rows)
    h.clock.t = rows[-1]["timestamp"] + 30
    h.engine.run_cycle()
    sells = h.store.q("SELECT * FROM bets WHERE side != 'BUY'")
    assert sells, "fixture tail has sells/redeems"
    alerted = {a["bet_id"] for a in h.alerts("BET")}
    assert not alerted & {b["bet_id"] for b in sells}
    assert all(h.store.q1("SELECT side FROM bets WHERE bet_id = ?", (b,))[0] == "BUY" for b in alerted)

    d = base_config()
    d["wallets"][1]["thresholds"] = {"alert_sides": ["BUY", "SELL"]}
    h2 = Harness(tmp_path, rows[0]["timestamp"] - 60, d, wallets=[SECOND], db_name="b.sqlite")
    h2.engine.run_cycle()
    h2.api.add_activity(SECOND, rows)
    h2.clock.t = rows[-1]["timestamp"] + 30
    h2.engine.run_cycle()
    sides = {h2.store.q1("SELECT side FROM bets WHERE bet_id = ?", (a["bet_id"],))[0] for a in h2.alerts("BET")
             if a["status"] != "suppressed"}
    assert "SELL" in sides                                   # configurable


def test_min_usdc_threshold_counts_the_whole_bet(tmp_path, mint_rows) -> None:
    """A tiny first fill does not alert; the bet alerts once its cumulative spend crosses the threshold."""
    from .conftest import MINTBLADE
    uru = [r for r in mint_rows if r["title"].startswith("Will Uruguay win") and r["type"] == "TRADE"]
    d = base_config()
    small = sorted(uru, key=lambda r: r["usdc_size"])[0]
    d["wallets"][0]["thresholds"] = {"min_usdc": small["usdc_size"] + 1}
    h = Harness(tmp_path, uru[0]["timestamp"] - 60, d, wallets=[MINTBLADE])
    h.engine.run_cycle()
    h.api.add_activity(MINTBLADE, [small])
    h.clock.t = small["timestamp"] + 10
    h.engine.run_cycle()
    assert h.alerts("BET") == []
    assert h.store.q1("SELECT alert_state FROM bets")[0] == "below_threshold"
    h.api.add_activity(MINTBLADE, [r for r in uru if r is not small])
    h.clock.t = uru[-1]["timestamp"] + 10
    h.engine.run_cycle()
    assert len(h.alerts("BET")) == 1
