"""Pure decision logic: anchors, decision windows, favourite selection, paper fills, fees.

Mirrors the pre-registered rule E2 (`notes/strategies/flb_near_resolution.md` section 0):
- anchor A = gameStartTime for markets that have one, else endDate (the scheduled clock);
- decision time D = A - horizon (7 days);
- the favourite side is the outcome token whose price is >= 0.95 at D;
- a trade is feasible only if its all-in cost per share (ask VWAP + taker fee) is <= 0.999.
The backtest priced the favourite from the /prices-history series; live, the book midpoint plays that role
and the paper fill walks the real asks, so slippage against the midpoint is measured, not assumed.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from pmr.fees import TAKER_RATE


def parse_ts(value) -> datetime | None:
    """Parse Gamma timestamps such as '2026-10-24T19:30:00Z' or '2026-10-24 19:30:00+00'."""
    if not value:
        return None
    s = str(value).strip().replace(" ", "T", 1)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    elif len(s) >= 3 and (s[-3] in "+-") and s[-3:].lstrip("+-").isdigit():
        s += ":00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def jlist(value) -> list:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return []
    return list(value or [])


def anchor(market: dict) -> datetime | None:
    return parse_ts(market.get("gameStartTime")) or parse_ts(market.get("endDate"))


def decision_status(market: dict, now: datetime, horizon: timedelta, tolerance: timedelta) -> str:
    """'due' if now is inside [D, D + tolerance]; 'early' before D; 'missed' after the window;
    'unlisted' if the market did not exist at D (the backtest could not have priced it either)."""
    a = anchor(market)
    if a is None:
        return "no_anchor"
    d = a - horizon
    created = parse_ts(market.get("createdAt")) or parse_ts(market.get("startDate"))
    if created is not None and created > d:
        return "unlisted"
    if now < d:
        return "early"
    if now <= d + tolerance:
        return "due"
    return "missed"


def category(market: dict) -> str:
    """Fee category from feeType (authoritative for fees), else from tags."""
    ft = str(market.get("feeType") or "").lower()
    for c in TAKER_RATE:
        if ft.startswith(c):
            return c
    tags = {str(t.get("slug", "")).lower() for t in market.get("tags") or [] if isinstance(t, dict)}
    for c in ("sports", "crypto", "politics", "geopolitics", "finance", "economics", "culture", "weather",
              "tech", "mentions"):
        if c in tags:
            return c
    return "other"


def fee_params(market: dict) -> tuple[float, float]:
    """(rate, exponent) charged to a taker in this market, from its feeSchedule."""
    if market.get("feesEnabled") is False:
        return 0.0, 1.0
    fs = market.get("feeSchedule") or {}
    if isinstance(fs, dict) and fs.get("rate") is not None:
        return float(fs["rate"]), float(fs.get("exponent") or 1.0)
    return TAKER_RATE.get(category(market), 0.05), 1.0


def is_exact_score(market: dict) -> bool:
    smt = str(market.get("sportsMarketType") or "").lower()
    return "exact" in smt or "exact score" in str(market.get("question") or "").lower()


def mid(book: dict) -> float | None:
    if not book.get("bids") or not book.get("asks"):
        return None
    return (book["bids"][0][0] + book["asks"][0][0]) / 2


@dataclass
class Fill:
    usd: float           # target stake
    shares: float
    vwap: float          # ask VWAP, before fees
    fee: float           # total taker fee, pUSD
    all_in: float        # (shares * vwap + fee) / shares
    complete: bool       # the visible asks could absorb the whole stake


def walk_asks(asks: list[tuple[float, float]], usd: float, rate: float, exponent: float) -> Fill:
    """Buy up to `usd` of notional (before fees) along best-first asks, charging the fee per level."""
    remaining, shares, cost, fee = usd, 0.0, 0.0, 0.0
    for price, size in asks:
        if remaining <= 1e-9:
            break
        take = min(size, remaining / price)
        shares += take
        cost += take * price
        fee += take * rate * (price * (1 - price)) ** exponent
        remaining -= take * price
    if shares <= 0:
        return Fill(usd, 0.0, float("nan"), 0.0, float("nan"), False)
    fee = round(fee, 5)
    return Fill(usd, shares, cost / shares, fee, (cost + fee) / shares, remaining <= 1e-6)


def favourite(market: dict, books: dict[str, dict], min_mid: float) -> tuple[int, dict, float] | None:
    """Return (outcome index, book, mid) of the side whose book midpoint is >= min_mid, if any."""
    ids = jlist(market.get("clobTokenIds"))
    for i, tok in enumerate(ids):
        b = books.get(str(tok))
        m = mid(b) if b else None
        if m is not None and m >= min_mid:
            return i, b, m
    return None


def prefilter(market: dict, min_mid: float, margin: float = 0.02) -> bool:
    """Cheap screen on Gamma's (CDN-cached) best prices before fetching books."""
    bid, ask = market.get("bestBid"), market.get("bestAsk")
    if bid is None or ask is None:
        p = market.get("lastTradePrice")
        if p is None:
            return True  # unknown: let the book decide
        p0 = float(p)
    else:
        p0 = (float(bid) + float(ask)) / 2
    return p0 >= min_mid - margin or p0 <= 1 - min_mid + margin
