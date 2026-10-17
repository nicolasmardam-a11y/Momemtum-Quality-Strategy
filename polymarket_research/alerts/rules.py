"""Which bets alert, which are suppressed, and the COPY-CANDIDATE rule set.

Labels
------
* ``NEW BET DETECTED``: pure observation of executed fills. Every bet alert gets
  this label unless the copy-candidate rules are enabled *and* all of them pass.
* ``COPY-CANDIDATE``: only when ``copy_candidate.enabled`` is true and every
  configured rule passes. Missing data fails the rule (fail closed). The default
  config disables the rules, so every alert is informational.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from .config import CONFIDENCE_LEVELS, Config, WalletConfig

LABEL_NEW = "NEW BET DETECTED"
LABEL_COPY = "COPY-CANDIDATE"


@dataclass
class Decision:
    action: str                 # "skip" | "suppress" | "alert"
    reason: str
    qualified_because: list[str] = field(default_factory=list)


def decide(bet: sqlite3.Row, w: WalletConfig, cfg: Config, now: float) -> Decision:
    """Decide what to do with a bet that changed. Pure function of stored state."""
    sides = cfg.alert_sides(w)
    if bet["side"] not in sides:
        return Decision("skip", f"side {bet['side']} is recorded only (alert_sides={list(sides)})")
    min_usdc = cfg.min_usdc(w)
    if bet["usdc_size"] < min_usdc:
        return Decision("skip", f"below threshold: ${bet['usdc_size']:,.2f} < min_usdc ${min_usdc:,.2f}")
    because = [f"{bet['side']} bet of ${bet['usdc_size']:,.2f} >= min_usdc ${min_usdc:,.2f}"]
    if bet["kind"] == "addition":
        because.append("addition to an existing position: a previous BUY run on this outcome ended more than "
                       f"{cfg.grouping.gap_minutes:g} min before this one")
    elif bet["kind"] == "new_position":
        because.append("first BUY run on this outcome seen by this monitor")
    if bet["live_fills"] == 0 and not cfg.alerting.alert_on_bootstrap:
        return Decision("suppress", "bootstrap baseline: fills recorded during this wallet's first poll "
                                    "(alerting.alert_on_bootstrap=false)", because)
    age = now - bet["last_ts"]
    if age > cfg.alerting.max_alert_age_minutes * 60:
        return Decision("suppress", f"too old: last fill executed {age / 3600:.1f} h before detection "
                                    f"(> max_alert_age_minutes={cfg.alerting.max_alert_age_minutes:g})", because)
    return Decision("alert", "qualified", because)


def copy_candidate(enr: dict, w: WalletConfig, cfg: Config, detection_lag_s: float | None) -> tuple[str, list[str], list[str]]:
    """Return (label, passed, failed) for the configured copy-candidate rules."""
    cc = cfg.copy_candidate
    if not cc.enabled:
        return LABEL_NEW, [], ["copy-candidate rules disabled in config (informational only)"]
    passed: list[str] = []
    failed: list[str] = []

    def rule(ok: bool | None, text: str) -> None:
        (passed if ok else failed).append(text + ("" if ok is not None else " [data missing]"))

    book = enr.get("book") or {}
    ms = enr.get("market_state") or {}
    det = (enr.get("deterioration") or {}).get("deterioration_cents")
    fee = (enr.get("follower_fee") or {}).get("fee_pct_of_notional")
    rule(None if detection_lag_s is None else detection_lag_s <= cc.max_detection_lag_seconds,
         f"detection lag <= {cc.max_detection_lag_seconds:g}s")
    rule(None if det is None else det <= cc.max_deterioration_cents,
         f"deterioration <= {cc.max_deterioration_cents:g}c")
    spread = book.get("spread_cents") if book.get("available") else None
    rule(None if spread is None else spread <= cc.max_spread_cents, f"spread <= {cc.max_spread_cents:g}c")
    depth = book.get("ask_depth_1c_usd") if book.get("available") else None
    rule(None if depth is None else depth >= cc.min_ask_depth_usd_within_1c,
         f"ask depth within 1c >= ${cc.min_ask_depth_usd_within_1c:,.0f}")
    rule(None if fee is None else fee <= cc.max_follower_fee_pct, f"follower taker fee <= {cc.max_follower_fee_pct:g}%")
    if cc.require_not_in_play:
        rule(None if ms.get("in_play") is None else not ms["in_play"], "not in-play")
    if cc.require_accepting_orders:
        rule(None if ms.get("accepting_orders") is None else bool(ms["accepting_orders"]) and not ms.get("closed"),
             "market accepting orders")
    rank = {c: i for i, c in enumerate(reversed(CONFIDENCE_LEVELS))}   # none=0 .. confirmed=3
    if rank[cc.min_cluster_confidence] > 0:
        rule(rank[w.cluster_confidence] >= rank[cc.min_cluster_confidence],
             f"cluster confidence >= {cc.min_cluster_confidence}")
    label = LABEL_COPY if not failed else LABEL_NEW
    return label, passed, failed
