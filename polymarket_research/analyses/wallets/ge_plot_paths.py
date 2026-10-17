"""Small-multiples figure: price of the wallet's chosen outcome (all taker trades, 1-min last price)
from 60 min before the first fill to 60 min after the last fill, with the wallet's own fills,
the scheduled kick-off and the entry window. Trade prices are not executable quotes.
Output: notes/wallets/figs/ge_price_paths.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived"
FIG = ROOT / "notes" / "wallets" / "figs"
SERIES1, SERIES2 = "#2a78d6", "#eb6834"  # reference palette slots 1-2 (light)
TEXT1, TEXT2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def main() -> None:
    f = pd.read_parquet(OUT / "ge_fills.parquet")
    f = f[f.notional > 100]  # the $4.80 Mets ticket is omitted from the figure
    panels = list(f.groupby(["label", "condition_id"]))
    n = len(panels)
    cols = 3
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(15, 3.1 * rows), facecolor=SURF)
    for ax in axes.flat[n:]:
        ax.axis("off")
    for ax, ((lab, cid), g) in zip(axes.flat, panels):
        tok = g.token_id.iloc[0]
        tk = pd.read_parquet(OUT / f"ge_tape_taker_{cid[:10]}.parquet")
        tk["p"] = np.where(tk.token_id == tok, tk.price, 1 - tk.price)
        ko = g.ko_ts.iloc[0]
        t0, t1 = g.timestamp.min() - 3600, g.timestamp.max() + 3600
        w = tk[(tk.timestamp >= t0) & (tk.timestamp <= t1)].sort_values("timestamp")
        w = w.assign(m=(w.timestamp // 60) * 60).groupby("m").p.last()
        x = (w.index - ko) / 60
        ax.set_facecolor(SURF)
        ax.axvspan((g.timestamp.min() - ko) / 60, (g.timestamp.max() - ko) / 60, color=SERIES1, alpha=0.08, lw=0)
        ax.plot(x, w.values, color=SERIES1, lw=1.6, label="market price of chosen outcome (1-min last taker trade)")
        ax.scatter((g.timestamp - ko) / 60, g.price, s=np.clip(g["size"] / g["size"].max() * 60, 8, 60),
                   color=SERIES2, edgecolor=SURF, linewidth=0.8, zorder=3, label="wallet's own fills (size-scaled)")
        ax.axvline(0, color=TEXT2, lw=1, ls="--")
        ax.text(0, 0.03, " kick-off", transform=ax.get_xaxis_transform(), color=TEXT2, fontsize=7, va="bottom")
        q = g.question.iloc[0].replace("Will ", "").replace(" on 2026-06-", " 06-")
        ax.set_title(f"{lab}: {q} -> {g.outcome.iloc[0]}", fontsize=8.5, color=TEXT1, loc="left")
        ax.grid(True, color=GRID, lw=0.6)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(colors=TEXT2, labelsize=7)
        ax.set_xlabel("minutes from scheduled kick-off", fontsize=7, color=TEXT2)
        ax.set_ylim(max(0, w.min() - 0.08), min(1, w.max() + 0.08))
    h, l = axes.flat[0].get_legend_handles_labels()
    fig.suptitle("Price path +-60 min around each entry (shaded = wallet's entry window; dashed = scheduled kick-off)",
                 y=0.997, fontsize=11, color=TEXT1)
    fig.legend(h, l, loc="upper center", bbox_to_anchor=(0.5, 0.985), ncol=2, frameon=False, fontsize=9, labelcolor=TEXT1)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / "ge_price_paths.png", dpi=110, facecolor=SURF)
    print("saved", FIG / "ge_price_paths.png")


if __name__ == "__main__":
    main()
