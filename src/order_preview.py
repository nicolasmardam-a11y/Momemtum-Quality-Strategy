"""Order preview: limit prices (tick-rounded) + full cost estimate.

LMT only. BUY limit = last_local * (1 + buffer); SELL = last_local *
(1 - buffer); rounded to a valid tick using the price-tiered tables in
config/execution.yaml (gbp / jpy / krw / default by currency).

Cost estimate (all expressed in EUR):
  commission  = base_one_way_bps  on notional
  slippage    = slippage_bps      on notional
  stamp/FTT   = country_buy_taxes_bps on BUY notional only
  fx cost     = fx_conversion_bps  on notional for non-base currency
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _tick_tables():
    ex = yaml.safe_load((ROOT / "config" / "execution.yaml").read_text())
    return ex.get("tick_rounding", {})


def _ccy_key(ccy: str) -> str:
    return {"GBP": "gbp", "JPY": "jpy", "KRW": "krw"}.get(ccy, "default")


def _round_tick(price: float, ccy: str, side: str, tables: dict) -> tuple[float, float]:
    tiers = (tables.get(_ccy_key(ccy)) or tables.get("default", {})).get("tiers", [])
    tick = 0.01
    for t in sorted(tiers, key=lambda x: -x["price_min"]):
        if price >= t["price_min"]:
            tick = float(t["tick"])
            break
    if tick <= 0:
        return round(price, 6), 0.0
    n = price / tick
    rounded = (math.ceil(n) if side == "BUY" else math.floor(n)) * tick
    return round(rounded, 8), tick


class OrderPreview:
    def __init__(self, cfg, fx, logger=None):
        self.cfg = cfg
        self.fx = fx
        self.log = logger
        self.tables = _tick_tables()
        c = cfg.costs
        self.base_bps = float(c["base_one_way_bps"])
        self.slip_bps = float(c.get("slippage_bps", 0.0))
        self.fx_bps = float(c["fx_conversion_bps"])
        self.tax = {k: float(v) for k, v in c.get("country_buy_taxes_bps", {}).items()}
        self.buf = float(cfg.order["limit_buffer_pct"])

    def build(self, trades: pd.DataFrame) -> pd.DataFrame:
        if trades is None or trades.empty:
            return pd.DataFrame()
        rows = []
        for _, t in trades.iterrows():
            ccy = t["currency"]
            side = t["side"]
            last = float(t["last_local_price"])
            raw_lmt = last * (1 + self.buf) if side == "BUY" else last * (1 - self.buf)
            lmt, tick = _round_tick(raw_lmt, ccy, side, self.tables)
            qty = int(t["trade_qty"])
            notional_local = qty * lmt
            notional_eur = self.fx.to_base(notional_local, ccy)
            commission = notional_eur * self.base_bps / 1e4
            slippage = notional_eur * self.slip_bps / 1e4
            fxcost = 0.0 if ccy == self.cfg.base_ccy else notional_eur * self.fx_bps / 1e4
            stamp = 0.0
            if side == "BUY":
                stamp = notional_eur * self.tax.get(str(t.get("country", "")), 0.0) / 1e4
            total_cost = commission + slippage + fxcost + stamp
            rows.append({
                "ticker": t["ticker"], "conId": int(t["conId"]),
                "ibkr_symbol": t["ibkr_symbol"], "primaryExchange": t["primaryExchange"],
                "side": side, "trade_qty": qty, "currency": ccy,
                "last_local_price": round(last, 6),
                "limit_price": lmt, "tick": tick, "order_type": "LMT",
                "tif": self.cfg.order["tif"], "outside_rth": self.cfg.order["outside_rth"],
                "notional_local": round(notional_local, 2),
                "notional_eur": round(notional_eur, 2),
                "est_commission_eur": round(commission, 2),
                "est_slippage_eur": round(slippage, 2),
                "est_fx_cost_eur": round(fxcost, 2),
                "est_stamp_tax_eur": round(stamp, 2),
                "est_total_cost_eur": round(total_cost, 2),
            })
        df = pd.DataFrame(rows)
        if self.log and not df.empty:
            self.log.info("order preview: %d orders, gross EUR %.0f, est cost EUR %.0f",
                           len(df), df["notional_eur"].abs().sum(),
                           df["est_total_cost_eur"].sum())
        return df
