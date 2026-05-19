"""Validated IBKR contract registry.

The bot may ONLY trade tickers present in config/ibkr_contracts.json.
Any model-selected ticker absent from the registry is refused (hard rule 3).

At load time the registry enforces:
- duplicate conId across model tickers -> KillSwitch (hard rule 6)
- malformed / missing required fields  -> KillSwitch
"""
from __future__ import annotations

import json
from pathlib import Path

from ibkr_connection import KillSwitch

_REQUIRED = ("conId", "symbol", "exchange", "primaryExchange",
             "currency", "localSymbol", "tradingClass")


class ContractRegistry:
    def __init__(self, path: str | Path, logger=None):
        self.path = Path(path)
        self.log = logger
        if not self.path.exists():
            raise KillSwitch(f"contract registry missing: {self.path}")
        self._d: dict[str, dict] = json.loads(self.path.read_text())
        if not self._d:
            raise KillSwitch("contract registry is empty")

        seen: dict[int, str] = {}
        for tk, c in self._d.items():
            for f in _REQUIRED:
                if f not in c or c[f] in (None, ""):
                    raise KillSwitch(f"registry entry {tk} missing field {f}")
            cid = int(c["conId"])
            if cid in seen:
                raise KillSwitch(
                    f"duplicate conId {cid} maps to {seen[cid]} and {tk} "
                    f"(rule 6 — refusing)")
            seen[cid] = tk
        if self.log:
            self.log.info("contract registry loaded: %d names, 0 duplicate conIds",
                           len(self._d))

    # ------------------------------------------------------------------ #
    def has(self, ticker: str) -> bool:
        return ticker in self._d

    def get(self, ticker: str) -> dict:
        if ticker not in self._d:
            raise KillSwitch(f"ticker {ticker} absent from contract registry "
                             f"(rule 3 — refusing to trade)")
        return self._d[ticker]

    def all_tickers(self) -> list[str]:
        return list(self._d)

    def conid_set(self) -> set[int]:
        return {int(c["conId"]) for c in self._d.values()}

    # SMART does NOT route to these venues — orders must go to the native
    # exchange directly or IBKR rejects with Error 200 "No security
    # definition" (confirmed empirically: B3/KRX/NSE/SGX/SFB/JSE fail on
    # SMART, fill on native routing). conId remains the authoritative key.
    NATIVE_ONLY = {"B3", "KRX", "NSE", "SGX", "SFB", "JSE"}

    def ib_contract(self, ticker: str):
        """Build an ib_async Contract pinned by conId. Use SMART routing
        where SMART reaches the venue; route to the native primaryExchange
        for exchanges SMART does not cover (rules 4 & 5 still hold — conId +
        validated currency/primaryExchange)."""
        from ib_async import Stock
        c = self.get(ticker)
        primary = c["primaryExchange"]
        exch = primary if primary in self.NATIVE_ONLY else "SMART"
        ct = Stock(
            symbol=c["symbol"],
            exchange=exch,
            currency=c["currency"],
            primaryExchange=primary,
        )
        ct.conId = int(c["conId"])          # conId is the authoritative key
        return ct
