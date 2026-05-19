"""Build the target book from the FROZEN production constituents.

Constituents and equal weights come straight from
reports/production/current_portfolio_clean.csv (the cleaned-sector,
trust-excluded top-50). This module does NOT re-rank or re-select — quarterly
reconstitution is the (unchanged) research recommender's job.

target_weight   = book_weight * overlay_exposure
target_mv_eur   = nav_eur * target_weight
target_mv_local = target_mv_eur converted to the name's local currency
target_qty      = floor(target_mv_local / last_local_price)

Any constituent absent from the contract registry raises KillSwitch
(missing conId — hard rule).
"""
from __future__ import annotations

import math

import pandas as pd

from ibkr_connection import KillSwitch


class PortfolioTarget:
    def __init__(self, cfg, registry, market_data, fx, logger=None):
        self.cfg = cfg
        self.reg = registry
        self.md = market_data
        self.fx = fx
        self.log = logger

    def build(self, nav_eur: float, exposure: float) -> dict:
        cp = pd.read_csv(self.cfg.path("current_portfolio"))
        n = len(cp)
        exp_n = int(self.cfg.risk["expected_n_constituents"])
        if n != exp_n:
            raise KillSwitch(
                f"constituent count {n} != expected {exp_n} "
                f"(portfolio drift / unexpected book)")
        wsum = float(cp["weight"].sum())
        if abs(wsum - 1.0) > 1e-6:
            raise KillSwitch(f"weights do not sum to 1.0 (got {wsum:.6f})")

        rows, currencies, stale, missing = [], set(), [], []
        invested_eur = 0.0
        for _, r in cp.iterrows():
            tk = r["ticker"]
            if not self.reg.has(tk):
                missing.append(tk)
                continue
            c = self.reg.get(tk)
            ccy = c["currency"]
            currencies.add(ccy)
            px = self.md.last_local_price(tk, ccy)
            if px["is_stale"]:
                stale.append((tk, px["asof"], px["stale_days"]))
            tgt_w = float(r["weight"]) * exposure
            tgt_mv_eur = nav_eur * tgt_w
            tgt_mv_local = self.fx.convert(tgt_mv_eur, self.cfg.base_ccy, ccy)
            price = px["price"]
            qty = int(math.floor(tgt_mv_local / price)) if price > 0 else 0
            filled_local = qty * price
            filled_eur = self.fx.to_base(filled_local, ccy)
            invested_eur += filled_eur
            rows.append({
                "ticker": tk,
                "conId": int(c["conId"]),
                "ibkr_symbol": c["symbol"],
                "primaryExchange": c["primaryExchange"],
                "currency": ccy,
                "country": r.get("country", ""),
                "sector_clean": r.get("sector", ""),
                "book_weight": float(r["weight"]),
                "target_weight": tgt_w,
                "target_mv_eur": round(tgt_mv_eur, 2),
                "last_local_price": price,
                "price_asof": px["asof"],
                "price_source": px["source"],
                "price_stale_days": px["stale_days"],
                "target_qty": qty,
                "target_mv_local_filled": round(filled_local, 2),
                "target_mv_eur_filled": round(filled_eur, 2),
            })
        if missing:
            raise KillSwitch(f"constituents missing from registry (missing conId): {missing}")

        df = pd.DataFrame(rows)
        cash_eur = nav_eur - invested_eur
        summary = {
            "nav_eur": round(nav_eur, 2),
            "exposure": exposure,
            "n_constituents": len(df),
            "invested_eur": round(invested_eur, 2),
            "cash_eur": round(cash_eur, 2),
            "cash_pct": round(cash_eur / nav_eur, 4) if nav_eur else None,
            "currencies": sorted(currencies),
            "stale_prices": stale,
            "projected_cash_deficit": bool(cash_eur < 0),
        }
        if self.log:
            self.log.info("target: %d names, invested EUR %.0f, cash EUR %.0f (%.1f%%)",
                           len(df), invested_eur, cash_eur,
                           100 * summary["cash_pct"] if summary["cash_pct"] else 0.0)
        return {"targets": df, "summary": summary}
