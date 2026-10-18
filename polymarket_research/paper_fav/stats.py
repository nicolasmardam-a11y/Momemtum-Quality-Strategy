"""Scorecard and kill rule.

Kill rule (proposed by the audit in notes/strategies/flb_near_resolution.md, post hoc): stop if realised
losses exceed `ratio` (0.75) x the price-implied losses, once the implied sum reaches `min_implied` (5).
Price-implied losses = sum(1 - fill price) over resolved positions; realised losses = sum(1 - payout), so a
50-50 resolution counts as half a loss. The loss ratio k = realised / implied; break-even after costs was
about 0.79 in liquid markets, and the backtest estimate was 0.54 [0.36, 0.78].
A second flag (my addition) fires if the median fill pays more than `max_median_slippage_cents` over the
book midpoint, because the backtest assumed fills close to the series price.
"""
from __future__ import annotations

from statistics import median

from scipy.stats import chi2


def poisson_ci(k: float, alpha: float = 0.05) -> tuple[float, float]:
    """Exact (Garwood) interval for a Poisson count; fractional counts are rounded for the bounds."""
    n = round(k)
    lo = 0.0 if n == 0 else chi2.ppf(alpha / 2, 2 * n) / 2
    hi = chi2.ppf(1 - alpha / 2, 2 * n + 2) / 2
    return lo, hi


def summarise(rows: list, cfg: dict, subset: str = "all") -> dict:
    kcfg = cfg["kill"]
    res = [r for r in rows if r["status"] == "resolved"]
    implied = sum(1 - r["vwap"] for r in res)
    losses = sum(1 - r["payout"] for r in res)
    cost = sum(r["shares"] * r["all_in"] for r in res)
    pnl = sum(r["pnl"] for r in res)
    cap_days = sum(r["shares"] * r["all_in"] * max(r["days_held"], 1 / 24) for r in res)
    out = {
        "subset": subset, "signals": len(rows), "open": len(rows) - len(res), "resolved": len(res),
        "losses": losses, "implied_losses": implied, "pnl": pnl, "cost": cost,
        "ret_per_trade": (sum(r["ret"] for r in res) / len(res)) if res else None,
        "ret_on_cost": pnl / cost if cost else None,
        "ret_per_capital_day": pnl / cap_days if cap_days else None,
        "median_slippage_c": median([r["slippage_c"] for r in rows]) if rows else None,
        "mean_days_held": (sum(r["days_held"] for r in res) / len(res)) if res else None,
        "disputed": sum(1 for r in res if r["disputed"]),
    }
    if implied > 0:
        lo, hi = poisson_ci(losses)
        out |= {"k": losses / implied, "k_lo": lo / implied, "k_hi": hi / implied}
    out["kill"] = bool(implied >= kcfg["min_implied_losses"] and losses > kcfg["ratio"] * implied)
    out["slippage_flag"] = bool(out["median_slippage_c"] is not None and len(rows) >= 30
                                and out["median_slippage_c"] > kcfg["max_median_slippage_cents"])
    out["evidence_status"] = ("killed" if out["kill"] else
                              "collecting" if implied < kcfg["min_implied_losses"] else "passing")
    return out


def subsets(rows: list) -> dict[str, list]:
    """'core' (liquid and tight spread) is the version comparable to the backtest's positive liquid sample;
    'all' is the rule exactly as pre-registered. Each subset carries its own kill-rule status."""
    return {"all": rows,
            "core": [r for r in rows if r["liquid"] and r.get("tight")],
            "tight": [r for r in rows if r.get("tight")],
            "liquid": [r for r in rows if r["liquid"]],
            "wide_or_thin": [r for r in rows if not (r["liquid"] and r.get("tight"))],
            "exact_score": [r for r in rows if r["exact_score"]]}


def scorecard(rows: list, cfg: dict) -> str:
    groups = subsets(rows)
    lines = ["PAPER SCORECARD: favourite >= 0.95 at T-7d (read-only; no orders are placed)", ""]
    hdr = f"{'subset':16s}{'signals':>8s}{'open':>6s}{'res':>6s}{'loss':>6s}{'implied':>8s}{'k':>6s}" \
          f"{'k 95% CI':>14s}{'ret/trade':>10s}{'P&L $':>9s}{'status':>11s}"
    lines.append(hdr)
    for name, g in groups.items():
        s = summarise(g, cfg, name)
        k = f"{s['k']:.2f}" if "k" in s else "-"
        ci = f"[{s['k_lo']:.2f},{s['k_hi']:.2f}]" if "k" in s else "-"
        rt = f"{100 * s['ret_per_trade']:+.2f}%" if s["ret_per_trade"] is not None else "-"
        lines.append(f"{name:16s}{s['signals']:8d}{s['open']:6d}{s['resolved']:6d}{s['losses']:6.1f}"
                     f"{s['implied_losses']:8.2f}{k:>6s}{ci:>14s}{rt:>10s}{s['pnl']:9.2f}{s['evidence_status']:>11s}")
    s = summarise(rows, cfg)
    core = summarise(groups["core"], cfg, "core")
    lines += ["", f"Kill rule: stop if losses > {cfg['kill']['ratio']} x implied once implied >= "
                  f"{cfg['kill']['min_implied_losses']}. Status: all {s['evidence_status'].upper()}, "
                  f"core {core['evidence_status'].upper()}. Judge the strategy on 'core'.",
              "Median fill slippage vs book mid: "
              + (f"{s['median_slippage_c']:.2f}c" if s["median_slippage_c"] is not None else "-")
              + (" (FLAG: above threshold)" if s["slippage_flag"] else ""),
              "Reference: backtest k = 0.54 [0.36, 0.78]; break-even after costs ~0.79 (liquid markets)."]
    return "\n".join(lines)
