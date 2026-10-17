"""Price path (per-minute tape VWAP of the wallet's own outcome token, taker rows) from
60 min before to 60 min after each entry episode, with the wallet's fills, the
inferred actual kick-off and goal times. Tape prints are not executable prices.
Output: notes/wallets/mintblade_price_paths.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "derived"
OUT = ROOT / "notes" / "wallets" / "mintblade_price_paths.png"
W = "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # reference palette slots 1-3 (validated all-pairs)
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

PANELS = [
    ("IRN-NZL (WC) - Iran win: No", [("0xe70fd51f", "Will IR Iran win on 2026-06-15?", "Iran win: No")],
     "2026-06-16 00:17:22", "2026-06-16 01:04:03",
     [("2026-06-16 01:00:00", "sched. KO"), ("2026-06-16 01:04:03", "actual KO (inferred)"), ("2026-06-16 01:10:33", "NZ 1-0 (7')")]),
    ("KSA-URU (WC) - three legs", [("0xbc54d735", "Will Uruguay win on 2026-06-15?", "Uruguay win: No"),
                                   ("0xa16a7269", "Spread: Uruguay (-1.5)", "Spread U-1.5: Saudi"),
                                   ("0x34432763", "Will Saudi Arabia vs. Uruguay end in a draw?", "Draw: Yes")],
     "2026-06-15 21:54:45", "2026-06-15 22:00:01",
     [("2026-06-15 22:00:00", "sched. KO"), ("2026-06-15 22:03:36", "actual KO (inferred)"), ("2026-06-15 22:44:06", "KSA 1-0 (41')")]),
    ("NYM-SEA (MLB) - Mets moneyline", [("0xa95e5c35", "New York Mets vs. Seattle Mariners", "Mets")],
     "2026-06-03 21:18:42", "2026-06-03 21:18:42",
     [("2026-06-03 19:40:00", "first pitch"), ("2026-06-03 22:17:53", "final 7-1")]),
]


def main():
    f = pd.read_parquet(D / "mintblade_fills.parquet")
    fig, axes = plt.subplots(3, 1, figsize=(10, 11), facecolor=SURF)
    for ax, (title, legs, s, e, marks) in zip(axes, PANELS):
        s, e = pd.Timestamp(s, tz="UTC"), pd.Timestamp(e, tz="UTC")
        lo, hi = s - pd.Timedelta(minutes=60), e + pd.Timedelta(minutes=60)
        ax.set_facecolor(SURF)
        ax.axvspan(s, e if e > s else s + pd.Timedelta(minutes=1), color=INK2, alpha=0.10, lw=0)
        for (cid, q, lab), col in zip(legs, SERIES):
            T = pd.read_parquet(D / f"mintblade_tape_{cid}_taker.parquet")
            T["ts"] = pd.to_datetime(T.timestamp, unit="s", utc=True)
            tok = f.loc[f.question == q, "token_id"].iloc[0]
            T["p"] = np.where(T.token_id == tok, T.price, 1 - T.price)
            T = T[(T.ts >= lo) & (T.ts <= hi)]
            T["m"] = T.ts.dt.floor("min")
            v = T.groupby("m").apply(lambda x: (x.p * x["size"]).sum() / x["size"].sum(), include_groups=False)
            ax.plot(v.index, v.values, color=col, lw=2, label=f"{lab} (tape VWAP/min)")
            mine = f[f.question == q]
            ax.scatter(mine.ts, mine.price, s=np.clip(mine["size"] / mine["size"].max() * 120, 10, 120),
                       color=col, edgecolor=SURF, linewidth=1.5, zorder=3)
            ax.annotate(lab, (v.index[-1], v.values[-1]), xytext=(4, 0), textcoords="offset points",
                        color=INK2, fontsize=8, va="center")
        for i, (t, lab) in enumerate(marks):
            t = pd.Timestamp(t, tz="UTC")
            if lo <= t <= hi:
                ax.axvline(t, color=INK2, lw=1, ls="--")
                ax.text(t, 0.97 - 0.07 * i, " " + lab, transform=ax.get_xaxis_transform(), fontsize=7.5,
                        color=INK2, ha="left", va="top",
                        bbox=dict(facecolor=SURF, edgecolor="none", pad=0.5))
        ax.set_title(title + "  (shaded: wallet entry episode; dots: wallet fills sized by shares)",
                     loc="left", fontsize=10, color=INK, pad=6)
        ax.set_ylabel("price of wallet's outcome", color=INK2, fontsize=9)
        ax.grid(axis="y", color=GRID, lw=0.8)
        for sp in ["top", "right"]:
            ax.spines[sp].set_visible(False)
        for sp in ["left", "bottom"]:
            ax.spines[sp].set_color(GRID)
        ax.tick_params(colors=INK2, labelsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz="UTC"))
        ax.set_xlim(lo, hi)
        if len(legs) > 1:
            ax.legend(frameon=False, fontsize=8, loc="upper left")
    axes[-1].set_xlabel("UTC", color=INK2, fontsize=9)
    fig.suptitle("mintblade: price path +-60 min around each entry episode (Data API tape, not executable prices)",
                 fontsize=11, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT, dpi=130, facecolor=SURF)
    print(OUT)


if __name__ == "__main__":
    main()
