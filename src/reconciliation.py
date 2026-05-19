"""Reconcile live IBKR positions against the target book.

Produces a per-name table (current vs target qty and EUR MV) and a single
`mismatch` boolean used by the reconciliation kill switch. Also flags
ORPHAN positions: anything held in the account whose conId is not in the
validated registry (must be investigated before trading).

In signal_only mode there is no IBKR connection, so reconciliation is
reported as skipped (does not fail the risk battery).
"""
from __future__ import annotations

import pandas as pd


class Reconciliation:
    # Instruments that belong to OTHER strategies on a shared paper account
    # (e.g. micro_futures_bot's MNQ). The Global Equity bot fully excludes
    # these from reconciliation — never reported, never blocked.
    IGNORE_CONIDS = {770561201}   # MNQ Micro-Nasdaq future

    def __init__(self, cfg, fx, registry, logger=None, full_conids=None):
        self.cfg = cfg
        self.fx = fx
        self.reg = registry
        self.log = logger
        self.tol_qty = int(cfg.risk["reconcile_tol_qty"])
        self.tol_eur = float(cfg.risk["reconcile_tol_value_eur"])
        # The reconcile scope for "is this an explainable instrument" is the
        # FULL validated registry, not just the top-50 trade gate. A held name
        # in the full registry is a known, currency-correct, validated
        # instrument (e.g. a prior-book holding pending exit) — not a hard
        # orphan. Only instruments in NEITHER set are unexplained (hard kill).
        self.known_conids = set(full_conids) if full_conids else registry.conid_set()

    def skipped(self) -> dict:
        return {"skipped": True, "mismatch": False, "detail": "skipped (no IBKR in signal_only)",
                "df": pd.DataFrame(), "current_by_conid": {}}

    def run(self, ib_positions: list[dict], targets: pd.DataFrame) -> dict:
        """Reconcile the bot's own asset class (equities) against the broker.

        A 'mismatch' is broker state the bot cannot EXPLAIN — i.e. an equity
        (STK) position whose conId is not in the validated registry. Needing
        to trade toward the target (current != target) is NOT a mismatch: that
        is precisely the job of the rebalancer. Non-equity instruments
        (futures/options owned by other strategies on a shared paper account)
        are reported as external and are out of this equity bot's scope.
        """
        cur = {int(p["conId"]): p for p in ib_positions}
        cur_by_conid = {cid: float(p["position"]) for cid, p in cur.items()}
        reg_conids = self.reg.conid_set()

        rows, needs = [], 0
        for _, t in targets.iterrows():
            cid = int(t["conId"])
            cq = float(cur_by_conid.get(cid, 0.0))
            tq = int(t["target_qty"])
            dq = tq - cq
            px = float(t["last_local_price"])
            mv_cur_eur = self.fx.to_base(cq * px, t["currency"])
            mv_tgt_eur = self.fx.to_base(tq * px, t["currency"])
            need = abs(dq) > self.tol_qty
            if need:
                needs += 1
            rows.append({
                "ticker": t["ticker"], "conId": cid, "currency": t["currency"],
                "current_qty": int(cq), "target_qty": tq, "qty_delta": int(dq),
                "current_mv_eur": round(mv_cur_eur, 2),
                "target_mv_eur": round(mv_tgt_eur, 2),
                "needs_trade": bool(need),
            })

        tgt_conids = {int(t["conId"]) for _, t in targets.iterrows()}
        equity_orphans, external_non_equity, pending_exit = [], [], []
        for cid, p in cur.items():
            if abs(p["position"]) <= 0:
                continue
            if cid in self.IGNORE_CONIDS:      # not this strategy's scope
                continue
            sectype = str(p.get("secType", "STK")).upper()
            entry = {"conId": cid, "symbol": p["symbol"],
                     "position": p["position"], "currency": p["currency"]}
            if sectype != "STK":
                entry["secType"] = sectype
                external_non_equity.append(entry)
            elif cid not in self.known_conids:
                equity_orphans.append(entry)           # truly unknown -> HARD
            elif cid not in tgt_conids:
                pending_exit.append(entry)             # validated, not in book

        df = pd.DataFrame(rows)
        mismatch = len(equity_orphans) > 0       # HARD: only UNVALIDATED equities
        detail = (f"{needs} name(s) need trades (normal); "
                  f"{len(equity_orphans)} unvalidated equity orphan(s) [HARD]; "
                  f"{len(pending_exit)} validated pending-exit (info); "
                  f"{len(external_non_equity)} external non-equity (ignored)")
        if self.log:
            self.log.info("reconciliation: %s", detail)
            if pending_exit:
                self.log.info("  pending-exit (validated, not in target): %s",
                              [o["symbol"] for o in pending_exit])
            if external_non_equity:
                self.log.info("  external non-equity (other strategy): %s",
                              [o["symbol"] for o in external_non_equity])
            if equity_orphans:
                self.log.warning("  UNVALIDATED ORPHANS (HARD block): %s",
                                 [o["symbol"] for o in equity_orphans])
        return {"skipped": False, "mismatch": mismatch, "detail": detail,
                "df": df, "orphans": equity_orphans,
                "pending_exit": pending_exit,
                "external_non_equity": external_non_equity,
                "current_by_conid": cur_by_conid}
