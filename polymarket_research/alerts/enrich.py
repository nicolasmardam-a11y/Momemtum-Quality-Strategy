"""Alert enrichment: fresh book, price deterioration, follower fee, exposure, market state.

The pure functions at the top are what the tests check numerically. ``Enricher``
calls the network; each component that fails is recorded in ``errors`` (and
reported to health as a DATA PROBLEM by the engine) instead of aborting the
alert, and a copy-candidate rule that needs missing data fails closed.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from pmr.fees import market_fee_rate, taker_fee

from .fills import trade_key
from .http_client import DataError
from .sources import Sources, jlist

EVENT_URL = "https://polymarket.com/event/{event_slug}"
MARKET_URL = "https://polymarket.com/event/{event_slug}/{market_slug}"
PRICE_EPS = 1e-9


# --------------------------------------------------------------------------- pure math

def book_metrics(book: dict) -> dict:
    """Best bid/ask, spread and depth within 1 and 5 cents of the touch.

    ``book`` is normalised best-first (pmr.api.normalize_book): bids descending,
    asks ascending, levels as (price, size). Depth "within 1c" on the ask side is
    every ask priced <= best_ask + 0.01 (shares and USD notional); likewise for
    bids priced >= best_bid - 0.01.
    """
    bids, asks = book.get("bids") or [], book.get("asks") or []
    best_bid = bids[0][0] if bids else None
    best_ask = asks[0][0] if asks else None
    out: dict[str, Any] = {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread_cents": round((best_ask - best_bid) * 100, 4) if best_bid is not None and best_ask is not None else None,
        "mid": round((best_ask + best_bid) / 2, 6) if best_bid is not None and best_ask is not None else None,
        "book_timestamp_ms": book.get("timestamp_ms"),
        "tick_size": book.get("tick_size"),
        "min_order_size": book.get("min_order_size"),
    }
    for c in (1, 5):
        w = c / 100
        a = [(p, s) for p, s in asks if best_ask is not None and p <= best_ask + w + PRICE_EPS]
        b = [(p, s) for p, s in bids if best_bid is not None and p >= best_bid - w - PRICE_EPS]
        out[f"ask_depth_{c}c_shares"] = round(sum(s for _, s in a), 4)
        out[f"ask_depth_{c}c_usd"] = round(sum(p * s for p, s in a), 2)
        out[f"bid_depth_{c}c_shares"] = round(sum(s for _, s in b), 4)
        out[f"bid_depth_{c}c_usd"] = round(sum(p * s for p, s in b), 2)
    return out


def deterioration(avg_fill_price: float, current_price: float | None, side: str = "BUY") -> dict:
    """How much worse a follower's entry is than the wallet's observed average fill.

    BUY: best_ask - avg (positive = follower pays more). SELL: avg - best_bid.
    Returned in cents (price points x 100) and as % of the wallet's average price.
    """
    if current_price is None or avg_fill_price <= 0:
        return {"deterioration_cents": None, "deterioration_pct": None}
    d = (current_price - avg_fill_price) if side == "BUY" else (avg_fill_price - current_price)
    return {"deterioration_cents": round(d * 100, 4), "deterioration_pct": round(d / avg_fill_price * 100, 4)}


def follower_fee(price: float | None, rate: float, exponent: float, follow_usd: float) -> dict:
    """Taker fee for a hypothetical follower buying ``follow_usd`` at ``price``.

    Polymarket fee = shares x rate x (p(1-p))^exponent, charged to takers only
    (docs /trading/fees; pmr.fees). The per-share figure is in cents.
    """
    if price is None or not 0 < price < 1:
        return {"fee_rate": rate, "fee_exponent": exponent, "fee_cents_per_share": None,
                "fee_pct_of_notional": None, "follow_usd": follow_usd, "follow_shares": None, "follow_fee_usd": None}
    per_share = rate * (price * (1 - price)) ** exponent
    shares = follow_usd / price
    return {
        "fee_rate": rate,
        "fee_exponent": exponent,
        "fee_cents_per_share": round(per_share * 100, 6),
        "fee_pct_of_notional": round(per_share / price * 100, 6),
        "follow_usd": follow_usd,
        "follow_shares": round(shares, 4),
        "follow_fee_usd": taker_fee(shares, price, rate, exponent),
        "all_in_price": round(price + per_share, 6),
    }


def fill_stats(fills: list[sqlite3.Row] | list[dict]) -> dict:
    """Aggregate a bet's fills: shares, spend, average and effective prices, maker/taker split."""
    shares = sum(f["size"] for f in fills)
    notional = sum(f["size"] * f["price"] for f in fills)
    usdc = sum(f["usdc_size"] for f in fills)
    by_role: dict[str, float] = {"taker": 0.0, "maker": 0.0, "unknown": 0.0}
    fees = 0.0
    for f in fills:
        role = f["liquidity_role"] if f["liquidity_role"] in by_role else "unknown"
        by_role[role] += f["size"]
        fees += f["fee_usdc"] or 0.0
    return {
        "n_fills": len(fills),
        "shares": round(shares, 6),
        "notional_usdc": round(notional, 6),
        "usdc_spent": round(usdc, 6),
        "avg_fill_price": round(notional / shares, 6) if shares else None,
        "effective_price_incl_fees": round(usdc / shares, 6) if shares else None,
        "wallet_fees_usdc": round(fees, 6),
        "taker_shares": round(by_role["taker"], 6),
        "maker_shares": round(by_role["maker"], 6),
        "unknown_role_shares": round(by_role["unknown"], 6),
        "taker_share_pct": round(by_role["taker"] / shares * 100, 2) if shares else None,
    }


def parse_time(v: Any) -> float | None:
    """Parse Gamma/CLOB time strings ('2026-06-16 01:00:00+00', '2026-06-16T01:00:00Z')."""
    if not v or not isinstance(v, str):
        return None
    s = v.strip().replace("Z", "+00:00")
    if s.endswith("+00") and not s.endswith("+00:00"):
        s += ":00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def market_state(gamma: dict | None, clob: dict | None, now: float) -> dict:
    """Closed / accepting orders / in-play. CLOB values win (not CDN-cached); Gamma
    (cached up to 300 s) supplies gameStartTime and the event's live flag."""
    g = gamma or {}
    ev = (g.get("events") or [{}])[0] if isinstance(g.get("events"), list) and g.get("events") else {}
    closed = clob.get("closed") if clob and clob.get("closed") is not None else g.get("closed")
    accepting = clob.get("accepting_orders") if clob and clob.get("accepting_orders") is not None else g.get("acceptingOrders")
    seconds_delay = clob.get("seconds_delay") if clob and clob.get("seconds_delay") is not None else g.get("secondsDelay")
    gst_raw = g.get("gameStartTime") or (clob or {}).get("game_start_time")
    gst = parse_time(gst_raw)
    live_flag = ev.get("live")
    ended = ev.get("ended")
    if live_flag is True:
        in_play, basis = True, "event.live=true"
    elif ended is True or closed is True:
        in_play, basis = False, "event ended / market closed"
    elif gst is not None and gst <= now:
        in_play, basis = True, "gameStartTime has passed and the event has not ended"
    elif gst is not None:
        in_play, basis = False, "gameStartTime is in the future"
    else:
        in_play, basis = False, "no gameStartTime (not a scheduled game)"
    return {
        "closed": closed,
        "accepting_orders": accepting,
        "active": g.get("active"),
        "game_start_time": gst_raw,
        "game_start_ts": gst,
        "in_play": in_play,
        "in_play_basis": basis,
        "seconds_delay": seconds_delay,
        "event_live": live_flag,
        "event_ended": ended,
        "score": ev.get("score"),
        "period": ev.get("period"),
        "neg_risk": g.get("negRisk"),
        "end_date": g.get("endDate"),
        "uma_resolution_status": g.get("umaResolutionStatus"),
    }


def exposure(market_positions: list[dict], event_positions: list[dict] | None, token_id: str) -> dict:
    """The wallet's current observed exposure (Data API positions, OPEN superset)."""
    def summ(rows: list[dict]) -> dict:
        return {
            "positions": len(rows),
            "current_value_usdc": round(sum(float(r.get("current_value") or 0) for r in rows), 2),
            "entry_cost_usdc": round(sum(float(r.get("entry_cost_usdc") or 0) for r in rows), 2),
            "markets": len({r.get("condition_id") for r in rows}),
        }
    same = [r for r in market_positions if r.get("token_id") == token_id]
    out = {
        "market": summ(market_positions),
        "outcome_current_size": round(sum(float(r.get("current_size") or 0) for r in same), 4),
        "outcome_avg_price": float(same[0]["avg_price"]) if same and same[0].get("avg_price") is not None else None,
        "other_outcomes": [{"outcome": r.get("outcome"), "current_size": r.get("current_size")}
                           for r in market_positions if r.get("token_id") != token_id],
    }
    out["event"] = summ(event_positions) if event_positions is not None else None
    return out


def links(event_slug: str | None, market_slug: str | None) -> dict:
    """polymarket.com/event/<event_slug> is canonical (verified 2026-10-17: 200 with a
    matching rel=canonical); /event/<event_slug>/<market_slug> deep-links one market."""
    if not event_slug:
        return {"event_url": None, "market_url": None}
    return {"event_url": EVENT_URL.format(event_slug=event_slug),
            "market_url": MARKET_URL.format(event_slug=event_slug, market_slug=market_slug) if market_slug else None}


# --------------------------------------------------------------------------- network enrichment

@dataclass
class Enrichment:
    data: dict = field(default_factory=dict)
    errors: list[DataError] = field(default_factory=list)


class Enricher:
    def __init__(self, sources: Sources, *, follow_usd: float, taker_crosscheck: bool,
                 clock: Callable[[], float]) -> None:
        self.sources = sources
        self.follow_usd = follow_usd
        self.taker_crosscheck = taker_crosscheck
        self.clock = clock

    PAYLOAD_ERRORS = (KeyError, TypeError, ValueError, AttributeError, IndexError)

    def _try(self, en: Enrichment, label: str, fn: Callable[[], Any], source: str = "enrich") -> Any:
        """Run one enrichment component. Network failures (DataError) and payload-shape surprises
        (a field of the wrong type) are both recorded as errors of that component only."""
        try:
            return fn()
        except DataError as e:
            err = e
        except self.PAYLOAD_ERRORS as e:
            err = DataError("schema", source, "", f"{label}: unexpected payload ({type(e).__name__}: {e})",
                            retryable=False)
        en.errors.append(err)
        en.data.setdefault("enrichment_errors", []).append(f"{label}: {err}")
        return None

    def _roles(self, en: Enrichment, bet: sqlite3.Row, fills: list[dict]) -> str:
        """Resolve 'unknown' liquidity roles via /v2/trades; returns the cross-check outcome.

        "maker" is inferred from *absence* from the taker-only feed, which is only valid
        once /v2/trades has ingested these fills. So the full feed (taker_only=false,
        verified equal to the activity TRADE rows) must contain every fill of the bet
        first; otherwise roles stay unknown ("incomplete").
        """
        if not (self.taker_crosscheck and bet["side"] in ("BUY", "SELL")
                and any(f["liquidity_role"] == "unknown" for f in fills)):
            return "not run"
        span = (bet["wallet"], bet["first_ts"], bet["last_ts"])
        everything = self._try(en, "trades index check", lambda: self.sources.trade_fill_keys(*span, taker_only=False),
                               "data-api")
        if everything is None:
            return "failed"
        missing = [f for f in fills if trade_key(f) not in everything]
        if missing:
            return f"incomplete: /v2/trades has not yet ingested {len(missing)} of {len(fills)} fill(s)"
        takers = self._try(en, "taker cross-check", lambda: self.sources.trade_fill_keys(*span, taker_only=True),
                           "data-api")
        if takers is None:
            return "failed"
        for f in fills:
            if f["liquidity_role"] == "unknown":
                f["liquidity_role"] = "taker" if trade_key(f) in takers else "maker"
            elif f["liquidity_role"] == "taker" and trade_key(f) not in takers:
                f["liquidity_role"] = "unknown"     # fee seen but not a taker fill (builder fee?): do not guess
        return "ok"

    def enrich(self, bet: sqlite3.Row, fills: list[sqlite3.Row]) -> Enrichment:
        en = Enrichment()
        d = en.data
        fills = [dict(f) for f in fills]
        # 1. Maker/taker: fee-embedded rows are takers; the rest are checked against /v2/trades.
        crosscheck = self._roles(en, bet, fills)
        d["maker_taker_basis"] = (
            "fee embedded in usdc_size => taker; " +
            ("remaining fills checked against /v2/trades taker-only feed" if crosscheck == "ok"
             else "remaining fills unknown (cross-check " + crosscheck + ")"))
        d["fills"] = fill_stats(fills)

        # 2. Market metadata (Gamma) and fresh state (CLOB).
        gamma = self._try(en, "gamma market", lambda: self.sources.gamma_market(bet["condition_id"]), "gamma")
        clob = self._try(en, "clob market", lambda: self.sources.clob_market(bet["condition_id"]), "clob")
        g = gamma if isinstance(gamma, dict) else {}

        def market_section() -> tuple[dict, dict]:
            evs = g.get("events")
            ev = evs[0] if isinstance(evs, list) and evs else {}
            if not isinstance(ev, dict):
                raise TypeError(f"events[0] is {type(ev).__name__}, not an object")
            return ev, {
                "question": g.get("question") or bet["title"],
                "event_title": ev.get("title"),
                "event_id": str(ev["id"]) if ev.get("id") is not None else None,
                "outcomes": jlist(g.get("outcomes")),
            }
        sect = self._try(en, "gamma market fields", market_section, "gamma")
        ev, mfields = sect if sect is not None else ({}, {"question": bet["title"], "event_title": None,
                                                           "event_id": None, "outcomes": []})
        event_slug = bet["event_slug"] or ev.get("slug")
        market_slug = bet["market_slug"] or g.get("slug")
        d["market"] = {
            **mfields,
            "outcome": bet["outcome"],
            "condition_id": bet["condition_id"],
            "token_id": bet["token_id"],
            "gamma_found": gamma is not None,
            **links(event_slug, market_slug),
        }
        d["market_state"] = self._try(en, "market state", lambda: market_state(
            g if sect is not None else {k: v for k, v in g.items() if k != "events"}, clob, self.clock()), "gamma") or {}

        # 3. Fresh executable book for the traded outcome (Sources.book checks asset_id == token).
        n_err = len(en.errors)
        book = self._try(en, "clob book", lambda: self.sources.book(bet["token_id"]), "clob") if bet["token_id"] else None
        if not bet["token_id"]:
            d["book"] = {"available": False, "reason": "no single outcome token (split/merge/conversion)"}
        elif len(en.errors) > n_err:
            d["book"] = {"available": False, "reason": f"book fetch failed: {en.errors[-1]}"}
        elif book is None:
            d["book"] = {"available": False, "reason": "no order book (CLOB 404): market closed or not tradable"}
        else:
            bm = book_metrics(book)
            bm["available"] = True
            bm["fetched_at"] = book.get("fetched_at")
            d["book"] = bm
        best = None
        if d["book"] and d["book"].get("available"):
            best = d["book"]["best_ask"] if bet["side"] == "BUY" else d["book"]["best_bid"]
        avg = d["fills"]["avg_fill_price"] or 0.0
        d["deterioration"] = deterioration(avg, best, bet["side"])

        # 4. Follower fee at the current ask from the market's feeSchedule.
        def fee_section() -> dict:
            if gamma is None:
                rate, exponent, basis = None, 1.0, "unknown (Gamma lookup failed)"
            else:
                fs = g.get("feeSchedule") if isinstance(g.get("feeSchedule"), dict) else {}
                rate = market_fee_rate(g, g.get("category"))
                exponent = float(fs.get("exponent") or 1.0) if fs else 1.0
                basis = "feeSchedule" if fs.get("rate") is not None else "category fallback (pmr.fees)"
            out = (follower_fee(best, rate, exponent, self.follow_usd)
                   if rate is not None else {"fee_rate": None, "fee_cents_per_share": None,
                                             "follow_fee_usd": None, "follow_usd": self.follow_usd})
            if exponent != 1.0:
                # notes/platform/fees_incentives.md: legacy (v1) exponent-2 markets used a different formula.
                basis += f"; exponent {exponent:g} != 1: legacy fee formula, figure may be wrong"
            out["basis"] = basis
            out["fee_type"] = g.get("feeType")
            return out
        d["follower_fee"] = self._try(en, "follower fee", fee_section, "gamma") or {
            "fee_rate": None, "fee_cents_per_share": None, "follow_fee_usd": None, "follow_usd": self.follow_usd,
            "basis": "unknown (fee fields unparseable)"}

        # 5. Exposure: this market, and the whole event when the event id is known.
        mpos = self._try(en, "positions (market)",
                         lambda: self.sources.positions(bet["wallet"], condition=bet["condition_id"]), "data-api")
        eid = d["market"]["event_id"]
        epos = self._try(en, "positions (event)", lambda: self.sources.positions(bet["wallet"], event_id=eid),
                         "data-api") if eid else None
        d["exposure"] = (self._try(en, "exposure", lambda: exposure(mpos, epos, bet["token_id"]), "data-api")
                         if mpos is not None else None)
        d["enriched_at"] = self.clock()
        return en
