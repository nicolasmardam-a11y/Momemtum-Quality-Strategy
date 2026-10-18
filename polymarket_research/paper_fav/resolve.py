"""Settle open paper positions from Gamma once their markets have resolved."""
from __future__ import annotations

from datetime import datetime

from . import rules
from .ledger import Ledger


def payout_for(market: dict, outcome_index: int) -> float | None:
    """Payout per share of the held outcome, or None while the market is not cleanly resolved.
    50-50 resolutions pay 0.5."""
    if not market.get("closed"):
        return None
    try:
        prices = [float(x) for x in rules.jlist(market.get("outcomePrices"))]
    except (TypeError, ValueError):
        return None
    if len(prices) <= outcome_index or abs(sum(prices) - 1) > 1e-6:
        return None
    p = prices[outcome_index]
    return p if p in (0.0, 0.5, 1.0) else None


def resolve(ledger: Ledger, client, now: datetime) -> int:
    pos = ledger.open_positions(before_iso=now.isoformat(timespec="seconds"))
    if not pos:
        return 0
    by_cid = {p["condition_id"]: p for p in pos}
    done = 0
    for m in client.markets_by_condition(list(by_cid), closed=True):
        p = by_cid.get(m.get("conditionId"))
        if p is None:
            continue
        pay = payout_for(m, p["outcome_index"])
        if pay is None:
            continue
        resolved_at = rules.parse_ts(m.get("closedTime")) or now
        disputed = "disputed" in str(m.get("umaResolutionStatuses") or "").lower()
        ledger.resolve(p["condition_id"], resolved_at=resolved_at.isoformat(timespec="seconds"), payout=pay,
                       disputed=disputed)
        done += 1
    return done
