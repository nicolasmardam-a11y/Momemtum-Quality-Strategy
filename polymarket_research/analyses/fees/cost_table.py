"""Worked effective-cost table for taker strategies under the 2026-10-17 fee regime.

fee/share = rate * p * (1 - p)   (docs /trading/fees; verified on-chain, see onchain_fee_sampler.py)
Net of Taker Rebate Program tier rebate rho (share of taker fees; docs /programs/taker-rebates):
    net_fee = (1 - rho) * fee
(a) buy at p and hold to resolution: one taker fee, no fee on redeem.
(b) buy at ask p+s/2, sell at bid p-s/2 (mid unchanged): two taker fees + spread s.
% of capital = cost per share / p (entry notional). Spread assumption: 1 cent for 0.05 <= p <= 0.95
(0.01 tick; median observed Gamma spread was 1.0c in those buckets on 2026-10-17), 0.1 cent at p = 0.99
(0.001 tick near the extremes).
Writes data/derived/cost_table_2026-10-17.csv and prints markdown.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RATES = {"Sports (standard, sports_fees_v3)": 0.05, "Politics": 0.04, "Crypto": 0.07, "Geopolitics": 0.0}
EXTRA = {"Sports legacy v2 / NFL-CFB Oct-26 (0.03)": 0.03}
TIERS = {"T0": 0.0, "Gold": 0.18, "Obsidian": 0.50}
PRICES = [0.05, 0.10, 0.30, 0.50, 0.70, 0.90, 0.95, 0.99]


def spread(p: float) -> float:
    return 0.001 if p >= 0.985 or p <= 0.015 else 0.01


def rows(rates: dict) -> pd.DataFrame:
    out = []
    for cat, r in rates.items():
        for p in PRICES:
            s = spread(p)
            a, b = p + s / 2, p - s / 2
            for tier, rho in TIERS.items():
                hold = (1 - rho) * r * p * (1 - p)
                rt_fees = (1 - rho) * r * (a * (1 - a) + b * (1 - b))
                rt = rt_fees + s
                out.append({"category": cat, "rate": r, "price": p, "tier": tier, "rebate": rho, "spread_c": s * 100,
                            "hold_c": hold * 100, "hold_pct": 100 * hold / p,
                            "rt_fees_c": rt_fees * 100, "rt_total_c": rt * 100, "rt_total_pct": 100 * rt / p})
    return pd.DataFrame(out)


def md(df: pd.DataFrame) -> str:
    lines = []
    for cat, g in df.groupby("category", sort=False):
        lines.append(f"\n**{cat}** (rate {g.rate.iloc[0]:.2f})\n")
        lines.append("| p | spread | (a) hold: T0 | Gold | Obsidian | (b) round trip: T0 | Gold | Obsidian |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for p, h in g.groupby("price"):
            h = h.set_index("tier")
            cell = lambda t, c, q: f"{h.loc[t, c]:.3f}¢ / {h.loc[t, q]:.2f}%"
            lines.append(f"| {p:.2f} | {h.loc['T0','spread_c']:.1f}¢ | " + " | ".join(cell(t, "hold_c", "hold_pct") for t in TIERS)
                         + " | " + " | ".join(cell(t, "rt_total_c", "rt_total_pct") for t in TIERS) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    df = pd.concat([rows(RATES), rows(EXTRA)], ignore_index=True)
    out = ROOT / "data" / "derived" / "cost_table_2026-10-17.csv"
    df.round(5).to_csv(out, index=False)
    print(md(df))
    print(out, file=sys.stderr)
