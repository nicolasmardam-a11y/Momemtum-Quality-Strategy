"""Read-only Polymarket wallet bet-alert system.

Polls public Data API v2 activity for a configured list of wallets, stores every
executed fill in SQLite, groups fills into bet events, enriches qualifying bets
with a fresh order-book snapshot and market state, and sends notifications.

It never connects a wallet, holds keys, places orders or copies trades. See
alerts/README.md for architecture, delivery semantics and the operational runbook.
"""
from __future__ import annotations

__version__ = "0.1.0"

DISCLAIMER = (
    "INFORMATIONAL ONLY: no copy signal has been validated by this research. "
    "Not a trading recommendation."
)
