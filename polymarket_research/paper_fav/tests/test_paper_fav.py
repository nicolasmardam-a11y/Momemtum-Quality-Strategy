"""Offline tests for the paper trader (no network)."""
from datetime import datetime, timedelta, timezone

import pytest

from paper_fav import rules
from paper_fav.ledger import Ledger
from paper_fav.resolve import payout_for, resolve
from paper_fav.scan import scan
from paper_fav.stats import summarise

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
CFG = {
    "rule": {"horizon_days": 7, "decision_tolerance_hours": 3, "min_side_mid": 0.95, "max_all_in": 0.999,
             "stake_usd": 20, "capacity_sizes_usd": [100, 500], "liquid_volume_usd": 10000,
             "liquid_liquidity_usd": 5000, "tight_spread_max": 0.02},
    "kill": {"ratio": 0.75, "min_implied_losses": 5, "max_median_slippage_cents": 0.5},
}


def market(cid, anchor, *, game=True, created=None, tokens=("A", "B"), accepting=True, fee=0.05, **kw):
    m = {"conditionId": cid, "question": f"Q {cid}", "slug": f"m-{cid}", "outcomes": '["Yes", "No"]',
         "clobTokenIds": str(list(tokens)).replace("'", '"'), "enableOrderBook": True, "acceptingOrders": accepting,
         "endDate": anchor.isoformat().replace("+00:00", "Z"), "feesEnabled": True,
         "feeSchedule": {"rate": fee, "exponent": 1}, "createdAt": (created or anchor - timedelta(days=30)).isoformat(),
         "events": [{"slug": f"e-{cid}"}], "volumeNum": 20000, "liquidityNum": 100}
    if game:
        m["gameStartTime"] = anchor.strftime("%Y-%m-%d %H:%M:%S+00")
    m.update(kw)
    return m


def book(bids, asks):
    return {"bids": sorted(bids, reverse=True), "asks": sorted(asks), "raw_timestamp": "1"}


class FakeClient:
    def __init__(self, markets, books, closed=None):
        self._m, self._b, self._closed = markets, books, closed or []

    def markets(self, **params):
        yield from self._m

    def books(self, ids):
        return {t: self._b[t] for t in ids if t in self._b}

    def markets_by_condition(self, cids, closed):
        return [m for m in self._closed if m["conditionId"] in cids]


# ------------------------------------------------------------------ rules
def test_parse_gamma_timestamps():
    assert rules.parse_ts("2026-10-24 19:30:00+00") == datetime(2026, 10, 24, 19, 30, tzinfo=timezone.utc)
    assert rules.parse_ts("2026-10-24T19:30:00Z") == datetime(2026, 10, 24, 19, 30, tzinfo=timezone.utc)
    assert rules.parse_ts(None) is None


def test_decision_window_and_listing():
    h, tol = timedelta(days=7), timedelta(hours=3)
    a = NOW + h  # D == NOW
    assert rules.decision_status(market("x", a), NOW, h, tol) == "due"
    assert rules.decision_status(market("x", a + timedelta(hours=1)), NOW, h, tol) == "early"
    assert rules.decision_status(market("x", a - timedelta(hours=4)), NOW, h, tol) == "missed"
    assert rules.decision_status(market("x", a, created=NOW + timedelta(minutes=5)), NOW, h, tol) == "unlisted"


def test_anchor_prefers_game_start():
    m = market("x", NOW, game=True, endDate="2026-11-30T00:00:00Z")
    assert rules.anchor(m) == NOW


def test_walk_asks_fee_and_vwap():
    f = rules.walk_asks([(0.96, 10), (0.97, 1000)], 20, rate=0.05, exponent=1)
    assert f.complete
    shares_l1 = 10
    shares_l2 = (20 - 9.6) / 0.97
    assert f.shares == pytest.approx(shares_l1 + shares_l2)
    fee = 0.05 * (shares_l1 * 0.96 * 0.04 + shares_l2 * 0.97 * 0.03)
    assert f.fee == pytest.approx(round(fee, 5))
    assert f.all_in == pytest.approx((20 + f.fee) / f.shares)


def test_walk_asks_incomplete_when_book_thin():
    assert not rules.walk_asks([(0.96, 5)], 20, 0.05, 1).complete


def test_favourite_uses_book_mid_either_side():
    m = market("x", NOW)
    books = {"A": book([(0.03, 100)], [(0.04, 100)]), "B": book([(0.96, 100)], [(0.97, 100)])}
    idx, _, mid = rules.favourite(m, books, 0.95)
    assert idx == 1 and mid == pytest.approx(0.965)
    assert rules.favourite(m, {"A": book([(0.5, 1)], [(0.52, 1)]), "B": book([(0.48, 1)], [(0.5, 1)])}, 0.95) is None


def test_category_from_fee_type_then_tags():
    assert rules.category({"feeType": "sports_fees_v3"}) == "sports"
    assert rules.category({"tags": [{"slug": "politics"}]}) == "politics"
    assert rules.category({}) == "other"


# ------------------------------------------------------------------ scan
def _setup(tmp_path, markets, books):
    return Ledger(tmp_path / "l.sqlite"), FakeClient(markets, books)


def test_scan_records_signal_once_and_is_idempotent(tmp_path):
    m = market("c1", NOW + timedelta(days=7))
    books = {"A": book([(0.96, 500)], [(0.97, 500)]), "B": book([(0.03, 500)], [(0.04, 500)])}
    led, cl = _setup(tmp_path, [m], books)
    st = scan(led, cl, CFG, NOW)
    assert len(st["new_signals"]) == 1
    s = st["new_signals"][0]
    assert s["outcome"] == "Yes" and s["vwap"] == pytest.approx(0.97)
    assert s["slippage_c"] == pytest.approx(0.5)
    assert s["all_in"] == pytest.approx(0.97 + 0.05 * 0.97 * 0.03, abs=1e-5)
    st2 = scan(led, cl, CFG, NOW + timedelta(minutes=30))
    assert st2["new_signals"] == [] and len(led.signals()) == 1


def test_scan_rejects_infeasible_and_no_favourite(tmp_path):
    m1 = market("c1", NOW + timedelta(days=7), tokens=("A", "B"))
    m2 = market("c2", NOW + timedelta(days=7), tokens=("C", "D"))
    books = {"A": book([(0.998, 50)], [(0.999, 50)]), "B": book([(0.001, 50)], [(0.002, 50)]),
             "C": book([(0.6, 50)], [(0.62, 50)]), "D": book([(0.38, 50)], [(0.4, 50)])}
    led, cl = _setup(tmp_path, [m1, m2], books)
    st = scan(led, cl, CFG, NOW)
    assert st["status"] == {"infeasible": 1, "no_favourite": 1}
    assert led.signals() == []


def test_missing_book_is_retried_not_decided(tmp_path):
    m = market("c1", NOW + timedelta(days=7))
    led, cl = _setup(tmp_path, [m], {})
    st = scan(led, cl, CFG, NOW)
    assert st["status"] == {"book_missing_retry": 1} and not led.decided("c1")


def test_late_sighting_is_missed_never_traded(tmp_path):
    m = market("c1", NOW + timedelta(days=7) - timedelta(hours=5))
    books = {"A": book([(0.96, 500)], [(0.97, 500)]), "B": book([(0.03, 500)], [(0.04, 500)])}
    led, cl = _setup(tmp_path, [m], books)
    st = scan(led, cl, CFG, NOW)
    assert st["status"] == {"missed": 1} and led.signals() == []


def test_not_accepting_orders(tmp_path):
    m = market("c1", NOW + timedelta(days=7), accepting=False)
    led, cl = _setup(tmp_path, [m], {})
    assert scan(led, cl, CFG, NOW)["status"] == {"not_tradable": 1}


# ------------------------------------------------------------------ resolution and stats
def test_payout_parsing():
    assert payout_for({"closed": True, "outcomePrices": '["1", "0"]'}, 0) == 1.0
    assert payout_for({"closed": True, "outcomePrices": '["0.5", "0.5"]'}, 1) == 0.5
    assert payout_for({"closed": False, "outcomePrices": '["1", "0"]'}, 0) is None
    assert payout_for({"closed": True, "outcomePrices": '["0.97", "0.03"]'}, 0) is None


def test_resolve_and_pnl(tmp_path):
    m = market("c1", NOW + timedelta(days=7))
    books = {"A": book([(0.96, 500)], [(0.97, 500)]), "B": book([(0.03, 500)], [(0.04, 500)])}
    led = Ledger(tmp_path / "l.sqlite")
    scan(led, FakeClient([m], books), CFG, NOW)
    closed = [{"conditionId": "c1", "closed": True, "outcomePrices": '["1", "0"]',
               "closedTime": (NOW + timedelta(days=7, hours=4)).isoformat(), "umaResolutionStatuses": "[]"}]
    assert resolve(led, FakeClient([], {}, closed), NOW + timedelta(days=8)) == 1
    r = dict(led.signals()[0])
    assert r["status"] == "resolved" and r["pnl"] == pytest.approx(r["shares"] - r["shares"] * r["all_in"])
    assert r["days_held"] == pytest.approx(7 + 4 / 24, rel=1e-3)
    assert resolve(led, FakeClient([], {}, closed), NOW + timedelta(days=9)) == 0  # already settled


def _row(vwap, payout, status="resolved"):
    return {"status": status, "vwap": vwap, "payout": payout, "shares": 10.0, "all_in": vwap + 0.001,
            "pnl": 10 * (payout - vwap - 0.001), "ret": (payout - vwap - 0.001) / (vwap + 0.001), "days_held": 8.0,
            "slippage_c": 0.3, "disputed": 0, "liquid": 1, "tight": 1, "exact_score": 0}


def test_kill_rule_needs_enough_implied_losses():
    rows = [_row(0.97, 0.0)] * 3 + [_row(0.97, 1.0)] * 30  # implied 0.99: too early to judge
    s = summarise(rows, CFG)
    assert not s["kill"] and s["evidence_status"] == "collecting"


def test_kill_rule_triggers_and_passes():
    bad = [_row(0.97, 0.0)] * 6 + [_row(0.97, 1.0)] * 194   # implied 6.0, losses 6 > 4.5
    assert summarise(bad, CFG)["kill"]
    good = [_row(0.97, 0.0)] * 3 + [_row(0.97, 1.0)] * 197  # losses 3 < 4.5
    s = summarise(good, CFG)
    assert not s["kill"] and s["evidence_status"] == "passing" and s["k"] == pytest.approx(0.5)


def test_fifty_fifty_counts_half_a_loss():
    s = summarise([_row(0.96, 0.5), _row(0.96, 1.0)], CFG)
    assert s["losses"] == pytest.approx(0.5)


def test_tight_flag_and_core_subset(tmp_path):
    from paper_fav.stats import subsets
    m1 = market("c1", NOW + timedelta(days=7), tokens=("A", "B"))
    m2 = market("c2", NOW + timedelta(days=7), tokens=("C", "D"))
    books = {"A": book([(0.96, 500)], [(0.97, 500)]), "B": book([(0.03, 500)], [(0.04, 500)]),
             "C": book([(0.92, 500)], [(0.98, 500)]), "D": book([(0.02, 500)], [(0.08, 500)])}
    led = Ledger(tmp_path / "l.sqlite")
    scan(led, FakeClient([m1, m2], books), CFG, NOW)
    rows = [dict(r) for r in led.signals()]
    tight = {r["condition_id"]: r["tight"] for r in rows}
    assert tight == {"c1": 1, "c2": 0}
    assert [r["condition_id"] for r in subsets(rows)["core"]] == ["c1"]
