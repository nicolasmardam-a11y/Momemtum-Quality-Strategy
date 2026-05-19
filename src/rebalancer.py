"""Compute the trade list = target book - current reconciled positions.

Pure arithmetic / execution plumbing (no model logic). Trades are dropped if:
  - notional < order.min_order_value_eur (below practical size), or
  - the lot-rounded quantity is 0 because the exchange enforces a minimum
    lot the strategy's per-name target is smaller than (Tokyo TSEJ / SGX = 100
    shares — confirmed empirically via IBKR Error 388).
Quantities are floored to the exchange lot so the bot can never submit an
order IBKR will reject for size. This only moves holdings to the frozen target.
"""
from __future__ import annotations

import pandas as pd

# Exchanges that reject sub-lot orders. Everything else trades odd lots (1).
EXCHANGE_MIN_LOT = {"TSEJ": 100, "SGX": 100}


class Rebalancer:
    def __init__(self, cfg, fx, logger=None):
        self.cfg = cfg
        self.fx = fx
        self.log = logger
        self.min_eur = float(cfg.order["min_order_value_eur"])

    def build_trades(self, targets: pd.DataFrame,
                     current_by_conid: dict[int, float]) -> pd.DataFrame:
        rows = []
        for _, t in targets.iterrows():
            cid = int(t["conId"])
            cur = float(current_by_conid.get(cid, 0.0))
            tgt = int(t["target_qty"])
            delta = tgt - int(cur)
            if delta == 0:
                continue
            side = "BUY" if delta > 0 else "SELL"
            px = float(t["last_local_price"])
            lot = EXCHANGE_MIN_LOT.get(str(t["primaryExchange"]), 1)
            # floor the trade to a whole number of exchange lots
            lot_qty = (abs(delta) // lot) * lot if lot > 1 else abs(delta)
            below_lot = lot_qty <= 0
            eff_qty = abs(delta) if lot == 1 else lot_qty
            notional_local = eff_qty * px
            notional_eur = self.fx.to_base(notional_local, t["currency"])
            below_min = (not below_lot) and notional_eur < self.min_eur
            rows.append({
                "ticker": t["ticker"],
                "conId": cid,
                "ibkr_symbol": t["ibkr_symbol"],
                "primaryExchange": t["primaryExchange"],
                "currency": t["currency"],
                "country": t.get("country", ""),
                "side": side,
                "current_qty": int(cur),
                "target_qty": tgt,
                "trade_qty": int(eff_qty),
                "exchange_lot": lot,
                "last_local_price": px,
                "notional_local": round(notional_local, 2),
                "notional_eur": round(notional_eur, 2),
                "below_min_size": bool(below_min),
                "below_min_lot": bool(below_lot),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            drop = df["below_min_size"] | df["below_min_lot"]
            kept = df[~drop].copy()
            n_eur = int(df["below_min_size"].sum())
            n_lot = int(df["below_min_lot"].sum())
        else:
            kept, n_eur, n_lot = df, 0, 0
        if self.log:
            self.log.info("rebalancer: %d trades (%d skipped < EUR %.0f, "
                           "%d skipped < exchange min-lot)",
                           len(kept), n_eur, self.min_eur, n_lot)
        return kept.reset_index(drop=True)
