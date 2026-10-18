"""Hourly scan: decide every market whose decision time (anchor - 7 days) has just passed.

Each market is decided exactly once, inside [D, D + tolerance]. Markets first seen after the window are
recorded as 'missed' and never traded, so an outage cannot create look-ahead. A market whose books cannot
be fetched in this run is left undecided and retried next run while still inside the window."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import rules
from .ledger import Ledger

# Sports markets are anchored on gameStartTime, but endDate (the only Gamma date filter) can be later than
# the game, so the endDate query window extends this far past the anchor window.
SPORTS_END_SLACK = timedelta(days=8)


def scan(ledger: Ledger, client, cfg: dict, now: datetime) -> dict:
    r = cfg["rule"]
    horizon = timedelta(days=r["horizon_days"])
    tol = timedelta(hours=r["decision_tolerance_hours"])
    lo = now + horizon - tol - timedelta(hours=1)
    hi = now + horizon + SPORTS_END_SLACK
    stats = {"scanned": 0, "due": 0, "new_signals": [], "status": {}}
    due: list[dict] = []
    for m in client.markets(active="true", end_date_min=lo.isoformat(), end_date_max=hi.isoformat(),
                            include_tag="true"):
        stats["scanned"] += 1
        cid = m.get("conditionId")
        if not cid or len(rules.jlist(m.get("clobTokenIds"))) != 2 or not m.get("enableOrderBook", True):
            continue
        if ledger.decided(cid):
            continue
        st = rules.decision_status(m, now, horizon, tol)
        if st == "early":
            continue
        if st != "due":
            a = rules.anchor(m)
            ledger.record_decision(cid, st, anchor_ts=a, decision_ts=a - horizon if a else None,
                                   question=m.get("question"), category=rules.category(m))
            _count(stats, st)
            continue
        due.append(m)
    stats["due"] = len(due)
    tokens = [str(t) for m in due for t in rules.jlist(m["clobTokenIds"])]
    books = client.books(tokens) if tokens else {}
    for m in due:
        _decide(ledger, cfg, m, books, now, horizon, stats)
    return stats


def _decide(ledger: Ledger, cfg: dict, m: dict, books: dict, now: datetime, horizon: timedelta, stats: dict):
    r = cfg["rule"]
    cid = m["conditionId"]
    a = rules.anchor(m)
    d = a - horizon
    cat = rules.category(m)
    base = dict(anchor_ts=a, decision_ts=d, question=m.get("question"), category=cat)
    if not m.get("acceptingOrders", True) or m.get("closed"):
        ledger.record_decision(cid, "not_tradable", **base)
        return _count(stats, "not_tradable")
    ids = [str(t) for t in rules.jlist(m["clobTokenIds"])]
    if not all(t in books for t in ids):
        return _count(stats, "book_missing_retry")  # undecided: retried next run while inside the window
    fav = rules.favourite(m, books, r["min_side_mid"])
    if fav is None:
        mids = [rules.mid(books[t]) for t in ids]
        ledger.record_decision(cid, "no_favourite", detail=f"mids={mids}", **base)
        return _count(stats, "no_favourite")
    idx, book, mid = fav
    rate, expo = rules.fee_params(m)
    fill = rules.walk_asks(book["asks"], r["stake_usd"], rate, expo)
    if not fill.complete or fill.all_in > r["max_all_in"]:
        ledger.record_decision(cid, "infeasible",
                               detail=f"mid={mid:.4f} all_in={fill.all_in:.4f} complete={fill.complete}", **base)
        return _count(stats, "infeasible")
    capacity = {}
    for usd in r.get("capacity_sizes_usd", []):
        f = rules.walk_asks(book["asks"], usd, rate, expo)
        capacity[str(usd)] = {"all_in": round(f.all_in, 5), "complete": f.complete}
    best_bid, best_ask = book["bids"][0][0], book["asks"][0][0]
    depth = sum(p * s for p, s in book["asks"] if p <= best_ask + 0.01 + 1e-9)
    vol, liq = m.get("volumeNum"), m.get("liquidityNum")
    liquid = (vol or 0) >= r["liquid_volume_usd"] or (liq or 0) >= r["liquid_liquidity_usd"]
    outcomes = rules.jlist(m.get("outcomes"))
    ev = (m.get("events") or [{}])[0]
    row = {
        "condition_id": cid, "decided_at": now.isoformat(timespec="seconds"),
        "decision_ts": d.isoformat(timespec="seconds"), "anchor_ts": a.isoformat(timespec="seconds"),
        "question": m.get("question"), "event_slug": ev.get("slug"), "market_slug": m.get("slug"),
        "outcome": outcomes[idx] if idx < len(outcomes) else str(idx), "outcome_index": idx, "token_id": ids[idx],
        "category": cat, "sports_market_type": m.get("sportsMarketType"), "exact_score": int(rules.is_exact_score(m)),
        "liquid": int(liquid), "tight": int(best_ask - best_bid <= r.get("tight_spread_max", 0.02) + 1e-9),
        "liquidity_num": liq, "volume_num": vol, "fee_rate": rate, "fee_exponent": expo,
        "mid": mid, "best_bid": best_bid, "best_ask": best_ask, "spread": best_ask - best_bid, "depth_1c_usd": depth,
        "stake_usd": r["stake_usd"], "shares": fill.shares, "vwap": fill.vwap, "fee": fill.fee,
        "all_in": fill.all_in, "complete": int(fill.complete), "slippage_c": (fill.vwap - mid) * 100,
        "capacity_json": capacity,
        "book_json": {"asks": book["asks"][:20], "bids": book["bids"][:20], "timestamp": book.get("raw_timestamp")},
    }
    if ledger.record_signal(row):
        stats["new_signals"].append(row)
        _count(stats, "signal")


def _count(stats: dict, key: str):
    stats["status"][key] = stats["status"].get(key, 0) + 1
