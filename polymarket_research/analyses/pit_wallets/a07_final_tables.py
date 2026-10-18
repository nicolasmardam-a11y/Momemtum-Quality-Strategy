"""Stage 4 (audit), step a07: compact tables for pit_wallets_FINAL.md (reads stage-2/3 results and audit outputs).

Prints markdown tables: (1) confirmatory family on test at the pre-registered model, historical fee and current fee,
drop / ipw / adv, with B1, B2 and matched-random (i) benchmarks; (2) ROI by detection delay under the current fee
(drop and ipw, first print + 0.01); (3) 2026 holdout. Run from polymarket_research/:
python analyses/pit_wallets/a07_final_tables.py > /dev/null  (writes audit/a07_tables.md)
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "pit_wallets"
R = OUT / "results"
A = OUT / "audit"
SETS = [("P", "S1"), ("P", "S1m"), ("P", "S2"), ("P", "S3"), ("P", "S4_sports"), ("P", "S4_politics"), ("P", "S4_crypto"),
        ("P", "S4_other"), ("P", "S5"), ("F1", "S1"), ("F1", "S2"), ("F1", "S3"), ("F1", "S4_sports"),
        ("F1", "S4_politics"), ("F1", "S4_crypto"), ("F1", "S4_other"), ("F1", "S5"), ("F2", "S1"), ("F2", "S2"),
        ("F2", "S3"), ("F2", "S5"), ("CL", "CL"), ("P", "B1_random_eligible"), ("F1", "B1_random_eligible"),
        ("F2", "B1_random_eligible")]


def pct(x, d=1):
    return "" if pd.isna(x) else f"{100 * x:+.{d}f}%"


def main():
    c = pd.read_parquet(R / "confirmatory.parquet")
    a1 = pd.read_parquet(A / "a01_recompute.parquet")
    g = pd.read_parquet(R / "grid.parquet")
    bc = pd.read_parquet(R / "bench_compare.parquet")
    lines = []
    lines.append("| signal | n filled / events | test ROI, fee 0 [95% event CI] | wallet-clustered CI (audit) | current fee | ipw / adv (current fee) | B1 | B2 | matched random (i) | Holm p | val ROI |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for t, s in SETS:
        h = c[(c.stype == t) & (c.screen == s) & (c.split == "test") & (c.fee == "hist")]
        cu = c[(c.stype == t) & (c.screen == s) & (c.split == "test") & (c.fee == "cur")]
        va = c[(c.stype == t) & (c.screen == s) & (c.split == "val") & (c.fee == "hist")]
        au = a1[(a1.stype == t) & (a1.screen == s) & (a1.split == "test")]
        b = bc[(bc.model == "fp") & (bc.delay == "120") & (bc.stype == t) & (bc.screen == s) & (bc.split == "test")]
        if h.empty:
            continue
        h, cu = h.iloc[0], cu.iloc[0]
        au = au.iloc[0] if len(au) else None
        bi = f"{pct(b.roi_i_hist.iloc[0])}" if len(b) else ""
        lines.append(f"| {t} {s} | {int(h.n_fill):,} / {int(h.n_events):,} | {pct(h.roi)} [{pct(h.ci_lo)}, {pct(h.ci_hi)}] | "
                     f"[{pct(au.ci_wal_lo) if au is not None else ''}, {pct(au.ci_wal_hi) if au is not None else ''}] | "
                     f"{pct(cu.roi)} | {pct(cu.get('roi_ipw'))} / {pct(cu.get('roi_adv'))} | {pct(h.get('roi_B1'))} | "
                     f"{pct(h.get('roi_B2'))} | {bi} | {'' if pd.isna(h.holm) else f'{h.holm:.2f}'} | "
                     f"{pct(va.iloc[0].roi) if len(va) else ''} |")
    lines.append("")
    # delays, current fee
    dl = ["5", "30", "120", "600", "900", "3600", "poll"]
    lines.append("| signal (test, current fee) | " + " | ".join(f"{d}{'' if d == 'poll' else ' s'} drop / ipw" for d in dl) + " |")
    lines.append("|---|" + "---|" * len(dl))
    x = g[(g.split == "test") & (g.model == "fp") & (g.slip == 0) & (~g.exit.astype(bool)) & (g.fee == "cur")]
    for t, s in SETS:
        row = []
        for d in dl:
            v = x[(x.stype == t) & (x.screen == s) & (x.delay == d)]
            dr = v[v.est == "drop"].roi; iw = v[v.est == "ipw"].roi
            row.append(f"{pct(dr.iloc[0], 0) if len(dr) else ''} / {pct(iw.iloc[0], 0) if len(iw) else ''}")
        lines.append(f"| {t} {s} | " + " | ".join(row) + " |")
    lines.append("")
    # holdout
    a6 = pd.read_parquet(A / "a06_stage3.parquet")
    lines.append("| 2026 holdout (M1, current fee) | 5 s | 30 s | 2 min [event CI] | 2 min wallet CI | 15 min | 60 min | poll | ipw 2 min |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for grp in ["S1", "S2", "S3", "S5", "B1"]:
        v = a6[(a6.group == grp) & (a6.rule == "print_before_tres") & (a6.conv == "prereg")].set_index("delay")
        m = v.loc["2m"]
        lines.append(f"| {grp} | {pct(v.loc['5s'].roi)} | {pct(v.loc['30s'].roi)} | {pct(m.roi)} [{pct(m.ev_lo)}, {pct(m.ev_hi)}] "
                     f"({int(m.n_fill)} filled, {int(m.n_ev)} events) | [{pct(m.wal_lo)}, {pct(m.wal_hi)}] | {pct(v.loc['15m'].roi)} | "
                     f"{pct(v.loc['60m'].roi)} | {pct(v.loc['poll'].roi)} | {pct(m.roi_ipw)} |")
    txt = "\n".join(lines)
    (A / "a07_tables.md").write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
