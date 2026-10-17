"""Enrichment math (book depth, deterioration, follower fee), market state, exposure,
and an end-to-end alert built from recorded payloads."""
from __future__ import annotations

import json

import pytest

from alerts import DISCLAIMER
from alerts.enrich import book_metrics, deterioration, exposure, fill_stats, follower_fee, links, market_state
from pmr.api import normalize_book
from pmr.fees import market_fee_rate, taker_fee

from .conftest import SECOND, Harness, base_config, load_fixture


def test_book_metrics_on_recorded_book() -> None:
    raw = load_fixture("book_open.json")
    m = book_metrics(normalize_book(raw))
    asks = sorted((float(x["price"]), float(x["size"])) for x in raw["asks"])
    bids = sorted(((float(x["price"]), float(x["size"])) for x in raw["bids"]), reverse=True)
    assert m["best_ask"] == asks[0][0] and m["best_bid"] == bids[0][0]
    assert m["spread_cents"] == pytest.approx((asks[0][0] - bids[0][0]) * 100)
    for c in (1, 5):
        a = [(p, s) for p, s in asks if p <= asks[0][0] + c / 100 + 1e-9]
        b = [(p, s) for p, s in bids if p >= bids[0][0] - c / 100 - 1e-9]
        assert m[f"ask_depth_{c}c_shares"] == pytest.approx(sum(s for _, s in a))
        assert m[f"ask_depth_{c}c_usd"] == pytest.approx(sum(p * s for p, s in a), abs=0.01)
        assert m[f"bid_depth_{c}c_usd"] == pytest.approx(sum(p * s for p, s in b), abs=0.01)
    assert m["ask_depth_5c_usd"] >= m["ask_depth_1c_usd"] > 0


def test_book_metrics_synthetic_and_empty() -> None:
    book = {"bids": [(0.50, 100), (0.495, 50), (0.40, 1000)], "asks": [(0.52, 200), (0.53, 100), (0.58, 10)]}
    m = book_metrics(book)
    assert m["spread_cents"] == pytest.approx(2.0)
    assert m["ask_depth_1c_shares"] == 300 and m["ask_depth_1c_usd"] == pytest.approx(104 + 53)
    assert m["ask_depth_5c_shares"] == 300                  # 0.58 is 6c away
    assert m["bid_depth_1c_shares"] == 150 and m["bid_depth_5c_shares"] == 150
    e = book_metrics({"bids": [], "asks": []})
    assert e["best_ask"] is None and e["spread_cents"] is None and e["ask_depth_1c_usd"] == 0


def test_deterioration_math() -> None:
    assert deterioration(0.50, 0.53) == {"deterioration_cents": pytest.approx(3.0), "deterioration_pct": pytest.approx(6.0)}
    assert deterioration(0.50, 0.49)["deterioration_cents"] == pytest.approx(-1.0)     # follower gets a better price
    assert deterioration(0.60, 0.58, "SELL")["deterioration_cents"] == pytest.approx(2.0)
    assert deterioration(0.50, None)["deterioration_cents"] is None


def test_follower_fee_matches_platform_formula() -> None:
    f = follower_fee(0.53, 0.03, 1.0, 100.0)
    per_share = 0.03 * 0.53 * 0.47                              # fee = shares * rate * p * (1 - p)
    assert f["fee_cents_per_share"] == pytest.approx(per_share * 100)
    assert f["fee_pct_of_notional"] == pytest.approx(per_share / 0.53 * 100)
    assert f["follow_shares"] == pytest.approx(100 / 0.53, abs=1e-4)
    assert f["follow_fee_usd"] == taker_fee(100 / 0.53, 0.53, 0.03) == pytest.approx(1.41, abs=1e-5)
    assert f["all_in_price"] == pytest.approx(0.53 + per_share)
    assert follower_fee(1.0, 0.03, 1.0, 100)["fee_cents_per_share"] is None
    g = load_fixture("gamma_market_open.json")[0]
    assert market_fee_rate(g) == g["feeSchedule"]["rate"] == 0.04     # recorded politics market
    assert market_fee_rate({**g, "feesEnabled": False, "feeSchedule": None}) == 0.0


def test_fill_stats_and_split() -> None:
    fills = [
        {"size": 100.0, "price": 0.50, "usdc_size": 50.75, "liquidity_role": "taker", "fee_usdc": 0.75},
        {"size": 300.0, "price": 0.54, "usdc_size": 162.0, "liquidity_role": "maker", "fee_usdc": 0.0},
    ]
    s = fill_stats(fills)
    assert s["shares"] == 400 and s["avg_fill_price"] == pytest.approx((50 + 162) / 400)
    assert s["usdc_spent"] == pytest.approx(212.75) and s["effective_price_incl_fees"] == pytest.approx(212.75 / 400)
    assert s["taker_shares"] == 100 and s["maker_shares"] == 300 and s["taker_share_pct"] == 25.0
    assert s["wallet_fees_usdc"] == pytest.approx(0.75)


def test_market_state_and_in_play() -> None:
    closed = load_fixture("gamma_market_closed.json")[0]
    ms = market_state(closed, None, 1_792_250_000)
    assert ms["closed"] is True and ms["accepting_orders"] is False and ms["in_play"] is False
    assert ms["game_start_time"] == "2026-06-16 01:00:00+00"
    g = {"closed": False, "acceptingOrders": True, "gameStartTime": "2026-10-17 15:00:00+00", "secondsDelay": 3,
         "events": [{"live": None, "ended": None}]}
    t_game = 1_792_249_200                                     # 2026-10-17T15:00:00Z
    assert market_state(g, None, t_game - 60)["in_play"] is False
    after = market_state(g, None, t_game + 60)
    assert after["in_play"] is True and after["seconds_delay"] == 3
    live = market_state({**g, "events": [{"live": True}]}, None, t_game - 3600)
    assert live["in_play"] is True and live["in_play_basis"] == "event.live=true"
    # CLOB (not CDN-cached) wins over Gamma for closed / accepting_orders
    clob = {"closed": True, "accepting_orders": False, "seconds_delay": 0}
    assert market_state(g, clob, t_game - 60)["accepting_orders"] is False


def test_exposure_from_recorded_positions() -> None:
    m = load_fixture("positions_market_holder.json")["data"]
    e = load_fixture("positions_event_holder.json")["data"]
    tok = m[0]["token_id"]
    ex = exposure(m, e, tok)
    assert ex["outcome_current_size"] == pytest.approx(m[0]["current_size"])
    assert ex["market"]["current_value_usdc"] == pytest.approx(m[0]["current_value"], abs=0.01)
    assert ex["event"]["markets"] == len({r["condition_id"] for r in e})
    assert ex["event"]["current_value_usdc"] == pytest.approx(sum(r["current_value"] for r in e), abs=0.01)


def test_links_pattern() -> None:
    l = links("fifwc-irn-nzl-2026-06-15", "fifwc-irn-nzl-2026-06-15-irn")
    assert l["event_url"] == "https://polymarket.com/event/fifwc-irn-nzl-2026-06-15"
    assert l["market_url"] == "https://polymarket.com/event/fifwc-irn-nzl-2026-06-15/fifwc-irn-nzl-2026-06-15-irn"
    assert links("", None) == {"event_url": None, "market_url": None}


def live_bet_harness(tmp_path, cfg_dict=None) -> tuple[Harness, dict]:
    rows = load_fixture("activity_second.json")
    bet = [r for r in rows if r["type"] == "TRADE" and r["side"] == "BUY"][-1]
    h = Harness(tmp_path, bet["timestamp"] - 120, cfg_dict, wallets=[SECOND])
    h.api.gamma[bet["condition_id"]] = load_fixture("gamma_market_open.json")[0]
    h.api.clob_markets[bet["condition_id"]] = load_fixture("clob_market_open.json")
    h.api.books[bet["token_id"]] = load_fixture("book_open.json")
    h.api.taker_rows[SECOND] = load_fixture("trades_taker_second.json")["data"]
    h.engine.run_cycle()                                       # bootstrap (nothing in the window yet)
    h.api.add_activity(SECOND, [bet])
    h.clock.t = bet["timestamp"] + 25
    h.engine.run_cycle()
    return h, bet


def test_end_to_end_alert_payload(tmp_path) -> None:
    h, bet = live_bet_harness(tmp_path)
    alerts = h.alerts("BET")
    assert len(alerts) == 1
    a = alerts[0]
    p = json.loads(a["payload_json"])
    en = p["enrichment"]
    assert a["label"] == "NEW BET DETECTED" and p["label"] == "NEW BET DETECTED"
    assert DISCLAIMER in a["text"] and "no copy signal has been validated" in a["text"]
    assert en["market"]["question"].startswith("Will Dwayne")
    assert en["market"]["event_title"] == "Presidential Election Winner 2028"
    assert en["market"]["market_url"] == ("https://polymarket.com/event/presidential-election-winner-2028/"
                                          "will-dwayne-the-rock-johnson-win-the-2028-us-presidential-election")
    assert en["fills"]["shares"] == pytest.approx(bet["size"])
    assert en["fills"]["usdc_spent"] == pytest.approx(bet["usdc_size"])
    assert en["fills"]["taker_shares"] == pytest.approx(bet["size"])      # fee embedded -> taker
    book = normalize_book(load_fixture("book_open.json"))
    assert en["book"]["best_ask"] == book["asks"][0][0]
    assert en["deterioration"]["deterioration_cents"] == pytest.approx((book["asks"][0][0] - bet["price"]) * 100, abs=1e-4)
    assert en["follower_fee"]["fee_rate"] == 0.04 and en["follower_fee"]["basis"] == "feeSchedule"
    assert en["follower_fee"]["fee_cents_per_share"] == pytest.approx(
        0.04 * book["asks"][0][0] * (1 - book["asks"][0][0]) * 100)
    assert en["market_state"]["accepting_orders"] is True and en["market_state"]["in_play"] is False
    assert p["detection_lag_s"] == pytest.approx(25, abs=0.01)
    assert p["wallet"]["cluster_confidence"] == "none"
    assert "copy-candidate rules disabled" in a["text"]
    assert "Why it qualified:" in a["text"] and "Execut" in a["text"] and "Detected (UTC)" in a["text"]
    assert en.get("enrichment_errors") is None


def test_copy_candidate_rules(tmp_path) -> None:
    on = base_config(copy_candidate={"enabled": True, "max_detection_lag_seconds": 60,
                                     "max_deterioration_cents": 1.0, "max_spread_cents": 2.0,
                                     "min_ask_depth_usd_within_1c": 500})
    h, _ = live_bet_harness(tmp_path, on)
    a = h.alerts("BET")[0]
    assert a["label"] == "COPY-CANDIDATE"
    assert "YOUR configured rules only" in a["text"] and "no copy signal has been validated" in a["text"]
    strict = base_config(copy_candidate={"enabled": True, "max_spread_cents": 0.01, "max_detection_lag_seconds": 5})
    h2, _ = live_bet_harness(tmp_path / "b", strict)
    a2 = h2.alerts("BET")[0]
    assert a2["label"] == "NEW BET DETECTED"
    failed = json.loads(a2["payload_json"])["rules_failed"]
    assert any("spread" in f for f in failed) and any("detection lag" in f for f in failed)


def test_enrichment_failure_still_alerts_and_reports_problem(tmp_path) -> None:
    on = base_config(copy_candidate={"enabled": True})
    rows = load_fixture("activity_second.json")
    bet = [r for r in rows if r["type"] == "TRADE" and r["side"] == "BUY"][-1]
    h = Harness(tmp_path, bet["timestamp"] - 120, on, wallets=[SECOND])
    h.engine.run_cycle()
    h.api.add_activity(SECOND, [bet])
    h.clock.t = bet["timestamp"] + 25
    h.api.fail("clob.polymarket.com/book", 500, times=1)
    h.engine.run_cycle()
    a = h.alerts("BET")[0]
    p = json.loads(a["payload_json"])
    assert a["label"] == "NEW BET DETECTED"                     # missing data fails the rules closed
    assert p["enrichment"]["book"]["available"] is False and "book fetch failed" in p["enrichment"]["book"]["reason"]
    assert any("[data missing]" in f for f in p["rules_failed"])
    assert h.store.count("health_events", "kind = 'enrichment' AND scope = 'clob'") == 1


def test_prior_holdings_from_positions_api_mark_an_addition(tmp_path) -> None:
    rows = load_fixture("activity_second.json")
    bet = [r for r in rows if r["type"] == "TRADE" and r["side"] == "BUY"][-1]
    holder = load_fixture("positions_market_holder.json")["data"][0]
    pos = dict(holder, token_id=bet["token_id"], condition_id=bet["condition_id"],
               current_size=bet["size"] + 500.0, outcome=bet["outcome"])
    h = Harness(tmp_path, bet["timestamp"] - 120, wallets=[SECOND])
    h.api.positions_by_condition[(SECOND, bet["condition_id"])] = [pos]
    h.engine.run_cycle()
    h.api.add_activity(SECOND, [bet])
    h.clock.t = bet["timestamp"] + 20
    h.engine.run_cycle()
    a = h.alerts("BET")[0]
    assert "addition to position" in a["text"] and "500.00 sh on this outcome beyond this bet" in a["text"]
    assert "first BUY run" not in a["text"]
    assert h.store.q1("SELECT kind FROM bets")[0] == "addition"
