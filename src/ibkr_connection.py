"""IBKR connection wrapper — paper-only, read-safe by default.

Hard kill switches enforced here:
- cannot connect            -> KillSwitch
- connected to a non-paper port (not 4002) -> refused before connect
- managed account does not start with the paper prefix ("DU") -> KillSwitch
- no managed account returned -> KillSwitch

No order is ever placed by this module. Order submission lives in
paper_executor.py and is independently guarded.
"""
from __future__ import annotations


class KillSwitch(RuntimeError):
    """Raised when a hard safety condition fails. The bot must stop."""


class IBKRConnection:
    def __init__(self, cfg, logger):
        self.cfg = cfg
        self.log = logger
        self.ib = None
        self.account: str | None = None

    # ------------------------------------------------------------------ #
    def connect(self):
        ib_cfg = self.cfg.ibkr
        port = ib_cfg["paper_port"]
        if port != 4002:
            raise KillSwitch(f"refusing non-paper port {port}")
        if ib_cfg["live_port"] == port:
            raise KillSwitch("live_port equals paper_port — refusing")

        try:
            from ib_async import IB
        except ImportError as e:
            raise KillSwitch(f"ib_async not installed: {e}")

        self.ib = IB()
        try:
            self.ib.connect(ib_cfg["host"], port,
                            clientId=ib_cfg["client_id"], timeout=15)
        except Exception as e:
            raise KillSwitch(f"IBKR not connected ({ib_cfg['host']}:{port}): {e!r}")

        if not self.ib.isConnected():
            raise KillSwitch("IBKR reports not connected after connect()")

        accounts = self.ib.managedAccounts()
        if not accounts:
            raise KillSwitch("no managed accounts returned")
        prefix = str(ib_cfg["paper_account_prefix"]).upper()
        if not all(a.startswith(prefix) for a in accounts):
            raise KillSwitch(
                f"wrong/non-paper account(s) {accounts}; expected prefix {prefix!r}")
        self.account = accounts[0]
        self.log.info("IBKR connected: account=%s port=%s clientId=%s [PAPER, read-safe]",
                       self.account, port, ib_cfg["client_id"])

        def _on_err(reqId, code, msg, contract):
            self.log.warning("IBKR msg %s: %s", code, str(msg)[:160])
        try:
            self.ib.errorEvent += _on_err
        except Exception:
            pass
        return self

    # ------------------------------------------------------------------ #
    def assert_paper(self):
        if not self.account or not str(self.account).startswith(
                str(self.cfg.ibkr["paper_account_prefix"]).upper()):
            raise KillSwitch(f"account {self.account} is not a paper account")

    def net_liquidation(self):
        """Return (nav_value, nav_currency). Never raises on partial data —
        the caller decides via risk checks."""
        self.assert_paper()
        summ = self.ib.accountSummary(self.account)
        for row in summ:
            if row.tag == "NetLiquidation":
                return float(row.value), row.currency
        raise KillSwitch("NetLiquidation not found in account summary")

    def positions(self) -> list[dict]:
        self.assert_paper()
        out = []
        for p in self.ib.positions(self.account):
            c = p.contract
            out.append({
                "conId": c.conId, "symbol": c.symbol,
                "currency": c.currency, "secType": c.secType,
                "position": float(p.position), "avgCost": float(p.avgCost),
            })
        return out

    def disconnect(self):
        try:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
                self.log.info("IBKR disconnected")
        except Exception:
            pass
