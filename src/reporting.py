"""Daily report writers. All outputs are date-stamped under reports/daily/."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


class Reporting:
    def __init__(self, cfg, date: str, logger=None):
        self.cfg = cfg
        self.date = date
        self.log = logger
        self.dir = cfg.path("reports_daily")
        self.dir.mkdir(parents=True, exist_ok=True)

    def _p(self, suffix: str) -> Path:
        return self.dir / f"{self.date}_{suffix}"

    def target_portfolio(self, df: pd.DataFrame):
        df.to_csv(self._p("target_portfolio.csv"), index=False)

    def order_preview(self, df: pd.DataFrame):
        (df if df is not None else pd.DataFrame()).to_csv(
            self._p("order_preview.csv"), index=False)

    def reconciliation(self, df: pd.DataFrame):
        (df if df is not None else pd.DataFrame()).to_csv(
            self._p("reconciliation.csv"), index=False)

    def risk_checks(self, risk: dict):
        self._p("risk_checks.json").write_text(json.dumps(risk, indent=2, default=str))

    def signal_report(self, mode: str, exposure: dict, summary: dict,
                       risk: dict, n_trades, recon_detail: str):
        L = []
        L.append(f"# Global Equity Bot v2.5 — Daily Signal Report")
        L.append("")
        L.append(f"_Date: {self.date} · Mode: **{mode}** · Investor base: "
                 f"{self.cfg.base_ccy} · PAPER ONLY_")
        L.append("")
        L.append("## Overlay exposure")
        L.append("")
        L.append("| Field | Value |")
        L.append("|---|---|")
        for k in ("asof", "exposure", "vol_scalar", "trend_scalar",
                  "urth_above_sma", "eem_above_sma", "prior_exposure",
                  "exposure_change"):
            L.append(f"| {k} | {exposure.get(k)} |")
        L.append("")
        L.append("## Target book")
        L.append("")
        L.append("| Field | Value |")
        L.append("|---|---|")
        for k in ("nav_eur", "exposure", "n_constituents", "invested_eur",
                  "cash_eur", "cash_pct", "projected_cash_deficit"):
            L.append(f"| {k} | {summary.get(k)} |")
        L.append(f"| currencies | {', '.join(summary.get('currencies', []))} |")
        L.append(f"| trades_generated | {n_trades} |")
        L.append("")
        L.append("## Risk checks")
        L.append("")
        L.append(f"**Result: {'PASS' if risk['all_passed'] else 'FAIL'}**"
                 + (f" — hard failures: {risk['hard_failures']}"
                    if not risk["all_passed"] else ""))
        L.append("")
        L.append("| Check | Status | Detail |")
        L.append("|---|---|---|")
        for c in risk["checks"]:
            st = "SKIP" if c["skipped"] else ("PASS" if c["passed"] else "**FAIL**")
            L.append(f"| {c['name']} | {st} | {str(c['detail'])[:80]} |")
        L.append("")
        L.append(f"Reconciliation: {recon_detail}")
        L.append("")
        L.append("## Mode semantics")
        L.append("")
        L.append("- `signal_only` — target book only, no IBKR, no orders.")
        L.append("- `preview` — IBKR reconcile + order preview, **no orders**.")
        L.append("- `paper_trade` — paper orders **after manual approval only**. "
                 "No live trading path exists.")
        self._p("signal_report.md").write_text("\n".join(L), encoding="utf-8")
        if self.log:
            self.log.info("reports written to %s (prefix %s_)", self.dir, self.date)
