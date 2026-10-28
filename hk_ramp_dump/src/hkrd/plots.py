"""Diagnostic figures (matplotlib, static PNG)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

INK, MUTED, ACCENT, DOWN, UP = "#1f2328", "#6e7781", "#0b6bcb", "#c4314b", "#1a7f37"


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color="#e6e8eb", lw=0.6)


def event_case(ax_p, ax_v, close: pd.Series, value: pd.Series, ev, pad: int = 60):
    lo = close.index.searchsorted(ev.run_start_date) - pad
    hi = close.index.searchsorted(ev.trough_date) + pad
    c = close.iloc[max(lo, 0):hi].dropna()
    v = value.reindex(c.index).fillna(0)
    ax_p.plot(c.index, c.to_numpy(), color=INK, lw=1.2)
    ax_p.set_yscale("log")
    ax_p.set_ylabel("HK$ (traded)", fontsize=7, color=MUTED)
    for d, col, lab in ((ev.run_start_date, MUTED, "run start"), (ev.first_signal_date, ACCENT, "first signal"),
                        (ev.peak_date, DOWN, "peak"), (ev.trough_date, UP, "trough")):
        ax_p.axvline(d, color=col, lw=0.8, ls="--")
        ax_p.annotate(lab, (d, c.max()), fontsize=6.5, color=col, rotation=90, va="top", ha="right")
    ax_p.set_title(f"{ev.code:05d} {str(getattr(ev, 'name', ''))[:18]}  {ev.category}\n"
                   f"run {ev.run_return:+.0%} in {ev.run_days_to_peak}d, then {ev.max_drawdown_post:+.0%}",
                   fontsize=8, color=INK, loc="left")
    ax_v.bar(v.index, v.to_numpy() / 1e6, color=MUTED, width=1.0)
    ax_v.set_ylabel("HK$m", fontsize=7, color=MUTED)
    _style(ax_p)
    _style(ax_v)
    ax_v.tick_params(axis="x", labelrotation=30)


def event_gallery(events: pd.DataFrame, close: pd.DataFrame, value: pd.DataFrame, path: Path, title: str):
    n = len(events)
    if n == 0:
        return
    cols = 3
    rows = int(np.ceil(n / cols))
    fig = plt.figure(figsize=(12, 4.2 * rows))
    # 4 grid rows per event row: price (2), traded value (1), spacer (1)
    gs = fig.add_gridspec(rows * 4, cols, hspace=0.5, wspace=0.25,
                          height_ratios=[1, 1, 0.8, 0.55] * rows)
    for k, ev in enumerate(events.itertuples()):
        r, c = divmod(k, cols)
        ax_p = fig.add_subplot(gs[r * 4:r * 4 + 2, c])
        ax_v = fig.add_subplot(gs[r * 4 + 2, c], sharex=ax_p)
        event_case(ax_p, ax_v, close[ev.code], value[ev.code], ev)
        plt.setp(ax_p.get_xticklabels(), visible=False)
    fig.suptitle(title, fontsize=11, color=INK, x=0.01, y=1.0 + 0.04 / rows, ha="left")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def events_by_year(ev: pd.DataFrame, path: Path):
    t = ev.assign(year=ev["peak_date"].dt.year).groupby(["year", "category"]).size().unstack(fill_value=0)
    colors = {"A_ramp_dump": DOWN, "B_sustained": UP, "C_volatile": MUTED, "censored": "#d0d7de"}
    fig, ax = plt.subplots(figsize=(9, 3.5))
    bottom = np.zeros(len(t))
    for c in [k for k in colors if k in t]:
        ax.bar(t.index, t[c], bottom=bottom, color=colors[c], label=c, width=0.75)
        bottom += t[c].to_numpy()
    ax.legend(frameon=False, fontsize=8, ncol=4)
    ax.set_title("Detected run-up episodes by peak year (primary definition)", fontsize=10, loc="left")
    _style(ax)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def sensitivity_heatmap(grid: pd.DataFrame, path: Path, post_window: int, drawdown: float):
    g = grid[(grid["post_window"] == post_window) & (grid["drawdown"] == drawdown)]
    fig, axes = plt.subplots(1, g["run_days"].nunique(), figsize=(11, 3.2), sharey=True)
    for ax, (L, gg) in zip(np.atleast_1d(axes), g.groupby("run_days")):
        t = gg.pivot(index="value_multiple", columns="run_return", values="frac_A")
        n = gg.pivot(index="value_multiple", columns="run_return", values="n_episodes")
        ax.imshow(t.to_numpy(), cmap="Reds", vmin=0, vmax=1, aspect="auto")
        for i in range(t.shape[0]):
            for j in range(t.shape[1]):
                ax.text(j, i, f"{t.iat[i, j]:.0%}\nn={int(n.iat[i, j])}", ha="center", va="center", fontsize=7)
        ax.set_xticks(range(t.shape[1]), [f"{x:.0%}" for x in t.columns], fontsize=7)
        ax.set_yticks(range(t.shape[0]), [f"{x:g}x" for x in t.index], fontsize=7)
        ax.set_title(f"run window {L}d", fontsize=8)
        ax.set_xlabel("run-up threshold", fontsize=7)
    np.atleast_1d(axes)[0].set_ylabel("traded-value multiple", fontsize=7)
    fig.suptitle(f"Share of episodes followed by a >= {drawdown:.0%} drawdown within {post_window}d",
                 fontsize=10, x=0.01, ha="left")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def calibration_plot(tables: dict[str, pd.DataFrame], path: Path, title: str):
    fig, ax = plt.subplots(figsize=(4.5, 4.2))
    mx = max(max(t["mean_pred"].max(), t["observed"].max()) for t in tables.values())
    ax.plot([0, mx], [0, mx], color="#d0d7de", lw=1)
    for (name, t), col in zip(tables.items(), [ACCENT, DOWN, UP, MUTED]):
        ax.plot(t["mean_pred"], t["observed"], marker="o", ms=3, lw=1, color=col, label=name)
    ax.set_xlabel("predicted", fontsize=8)
    ax.set_ylabel("observed", fontsize=8)
    ax.legend(frameon=False, fontsize=7)
    ax.set_title(title, fontsize=9, loc="left")
    _style(ax)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def equity_curves(series: dict[str, pd.Series], path: Path, title: str):
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for (name, r), col in zip(series.items(), [INK, ACCENT, DOWN, UP, MUTED]):
        ax.plot((1 + r.fillna(0)).cumprod(), lw=1.1, color=col, label=name)
    ax.set_yscale("log")
    ax.legend(frameon=False, fontsize=8)
    ax.set_title(title, fontsize=10, loc="left")
    _style(ax)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
