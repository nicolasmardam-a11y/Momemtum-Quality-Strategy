"""Paper-order submission. PAPER ONLY. No live code path exists.

Submission is refused unless ALL of the following hold:
  - cfg.safety.live_trading_enabled is False
  - cfg.safety.paper_only is True
  - mode == 'paper_trade'
  - IBKR account starts with the paper prefix ('DU')
  - manual approval flag is True (and typed confirmation handled by caller)
  - the risk-check battery passed (all_passed)
  - every order is LMT (market orders refused)

There is no parameter, flag, or branch in this module that can route an order
to a live account or the live port. Orders are LMT + GTC + outsideRth, pinned
by conId, throttled, and every action is written to the JSONL audit log.
"""
from __future__ import annotations

import time

from ibkr_connection import KillSwitch


class LiveTradingForbidden(RuntimeError):
    pass


class PaperExecutor:
    def __init__(self, cfg, conn, registry, audit, logger):
        self.cfg = cfg
        self.conn = conn
        self.reg = registry
        self.audit = audit
        self.log = logger

    def _guards(self, mode: str, approved: bool, risk_passed: bool):
        sf = self.cfg.safety
        if sf.get("live_trading_enabled") is not False:
            raise LiveTradingForbidden("live_trading_enabled is not False")
        if sf.get("paper_only") is not True:
            raise LiveTradingForbidden("paper_only is not True")
        if mode != "paper_trade":
            raise KillSwitch(f"submission requires mode=paper_trade (got {mode})")
        self.conn.assert_paper()
        if not approved:
            raise KillSwitch("manual approval not granted (--approve required)")
        if not risk_passed:
            raise KillSwitch("risk-check battery did not pass — refusing to submit")
        if str(self.cfg.order["type"]).upper() != "LMT":
            raise KillSwitch("order.type is not LMT — refusing")

    def submit(self, mode: str, preview_df, approved: bool, risk_passed: bool) -> dict:
        self._guards(mode, approved, risk_passed)
        from ib_async import LimitOrder

        throttle = float(self.cfg.order["throttle_seconds"])
        max_inflight = int(self.cfg.order["max_in_flight"])
        tif = self.cfg.order["tif"]
        orth = bool(self.cfg.order["outside_rth"])
        acct = self.conn.account

        self.audit.write("submission_start", mode=mode, account=acct,
                         n_orders=int(len(preview_df)), approved=approved)
        submitted, inflight = [], []
        for _, o in preview_df.iterrows():
            tk = o["ticker"]
            contract = self.reg.ib_contract(tk)
            order = LimitOrder(o["side"], int(o["trade_qty"]), float(o["limit_price"]),
                               tif=tif, outsideRth=orth)
            try:
                trade = self.conn.ib.placeOrder(contract, order)
                oid = trade.order.orderId
                rec = self.audit.write(
                    "order_submitted", account=acct, ticker=tk,
                    conId=int(o["conId"]), side=o["side"], qty=int(o["trade_qty"]),
                    limit=float(o["limit_price"]), currency=o["currency"],
                    tif=tif, outsideRth=orth, order_id=oid)
                self.log.info("PAPER order %s: %s %d %s @ %.4f %s",
                              oid, o["side"], int(o["trade_qty"]), tk,
                              float(o["limit_price"]), o["currency"])
                submitted.append({"ticker": tk, "order_id": oid, "trade": trade})
                inflight.append(trade)
            except Exception as e:
                self.audit.write("order_failed", account=acct, ticker=tk, error=str(e))
                self.log.error("order FAILED %s: %s", tk, e)
            time.sleep(throttle)
            # An order leaves "in flight" once IBKR has ACKNOWLEDGED it — not
            # only when filled/cancelled. GTC orders into closed markets rest
            # (Submitted/PreSubmitted) and would otherwise block the pacing
            # gate forever. Pacing only needs to bound un-acknowledged sends.
            def _pending(t):
                st = t.orderStatus.status
                return st in ("", "PendingSubmit", "ApiPending")
            inflight = [t for t in inflight if _pending(t)]
            guard = 0
            while len(inflight) >= max_inflight and guard < 20:
                self.conn.ib.sleep(0.5)
                inflight = [t for t in inflight if _pending(t)]
                guard += 1

        self.conn.ib.sleep(15)
        statuses = []
        for s in submitted:
            t = s["trade"]
            st = {"ticker": s["ticker"], "order_id": s["order_id"],
                  "status": t.orderStatus.status,
                  "filled": float(t.orderStatus.filled),
                  "avg_price": float(t.orderStatus.avgFillPrice or 0.0)}
            statuses.append(st)
            self.audit.write("order_status", **st)
        self.audit.write("submission_end", n_submitted=len(submitted))
        return {"submitted": len(submitted), "statuses": statuses}
