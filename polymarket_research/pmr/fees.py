"""Current Polymarket taker fees and rebates (docs.polymarket.com/trading/fees, as of 2026-10-17).

fee = shares * rate * p * (1 - p), charged to takers only, in pUSD.
Prefer the per-market Gamma field `feeSchedule` ({rate, exponent, takerOnly,
rebateRate}) when present: it is authoritative for that market, and the
category table below is a fallback. Historical trades were made under older
regimes (largely fee-free before 2026), so never apply this table to past fills
without checking the market's fee fields at the time.
"""
from __future__ import annotations

TAKER_RATE = {
    "crypto": 0.07, "sports": 0.05, "finance": 0.04, "politics": 0.04, "economics": 0.05,
    "culture": 0.05, "weather": 0.05, "other": 0.05, "mentions": 0.04, "tech": 0.04, "geopolitics": 0.0,
}
MAKER_REBATE_SHARE = {
    "crypto": 0.20, "sports": 0.15, "finance": 0.25, "politics": 0.25, "economics": 0.25, "culture": 0.25,
    "weather": 0.25, "other": 0.25, "mentions": 0.25, "tech": 0.25, "geopolitics": 0.0,
}
# Taker Rebate Program (live since 2026-05-28): rebate share of fees by 30-day weighted volume.
TAKER_TIERS = [(0, 0.0), (2_000, 0.03), (20_000, 0.08), (200_000, 0.18), (1_000_000, 0.32),
               (4_000_000, 0.44), (10_000_000, 0.50)]
CATEGORY_WEIGHT = {"sports": 1.0, "politics": 1.3, "finance": 1.3, "mentions": 1.3, "tech": 1.3,
                   "economics": 1.7, "culture": 1.7, "weather": 1.7, "other": 1.7, "crypto": 2.3, "geopolitics": 0.0}


def taker_fee(shares: float, price: float, rate: float, exponent: float = 1.0) -> float:
    """Fee in pUSD for a taker fill, rounded to 5 dp like the exchange."""
    return round(shares * rate * (price * (1 - price)) ** exponent, 5)


def market_fee_rate(market: dict, category: str | None = None) -> float:
    """Taker fee rate for a Gamma market dict: feeSchedule first, then category table."""
    fs = market.get("feeSchedule") or {}
    if isinstance(fs, dict) and fs.get("rate") is not None:
        return float(fs["rate"]) if market.get("feesEnabled", True) else 0.0
    if market.get("feesEnabled") is False:
        return 0.0
    return TAKER_RATE.get((category or "other").lower(), 0.05)


def taker_rebate_share(weighted_volume_30d: float) -> float:
    share = 0.0
    for threshold, s in TAKER_TIERS:
        if weighted_volume_30d >= threshold:
            share = s
    return share
