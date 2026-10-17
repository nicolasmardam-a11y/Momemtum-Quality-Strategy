"""Sensitivity of the neg-risk (d)/(e) top-of-book edge to the taker-fee level (no network access).

Run from polymarket_research/:  python -m analyses.complete_set_arb.fee_sensitivity [w1|w2|all]
Uses scan_*_members.parquet (top of book per tradable member, YES side) and scan_*_groups.parquet (flags).
edge_d(f) = sum_i [bbY_i - f * rate_i * bbY_i * (1 - bbY_i)] - 1 over members with a YES bid, which equals the
(e) buy-all-NO + convert edge because the NO book mirrors the YES book. f = 1 is the pre-registered (full fee) case;
f = 0.97 / 0.82 / 0.50 are Taker Rebate Program rebate shares 3% (Bronze) / 18% / 50% (top tier), applied as fee x (1 - rebate);
f = 0 is the gross (maker / fee-free) case. Rebates are paid daily in arrears, so this is a profitability band, not
an execution price. Top of book only (size ignored), so counts are upper bounds on what is executable.
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "derived" / "complete_set_arb"
W = sys.argv[1] if len(sys.argv) > 1 else "all"
FS = {"full fee (pre-reg)": 1.0, "rebate 3% (Bronze)": 0.97, "rebate 18%": 0.82, "rebate 50% (Obsidian)": 0.50, "no fee (gross)": 0.0}
INPLAY = ("game_started", "seconds_delay")


def keep(f):
    s = int(re.search(r"scan_(\d+)", f).group(1))
    return W == "all" or (W == "w1" and s < 100) or (W == "w2" and s >= 100)


def main():
    mf = [f for f in sorted(glob.glob(str(D / "scan_*_members.parquet"))) if keep(f)]
    gf = [f for f in sorted(glob.glob(str(D / "scan_*_groups.parquet"))) if keep(f)]
    m = pd.concat([pd.read_parquet(f, columns=["nr_id", "bbY", "bsY", "fee_rate"]).assign(scan=int(re.search(r"scan_(\d+)", f).group(1))) for f in mf])
    g = pd.concat([pd.read_parquet(f, columns=["nr_id", "flags", "n_trad"]).assign(scan=int(re.search(r"scan_(\d+)", f).group(1))) for f in gf])
    g["inplay"] = g["flags"].fillna("").map(lambda s: any(k in s for k in INPLAY))
    g["other_flag"] = g["flags"].fillna("").map(lambda s: any(k in s for k in ("not_tradable", "crossed_book", "resolution_pending", "missing_book")))
    m = m[m.bbY.notna()]
    m["fee_unit"] = m.fee_rate * m.bbY * (1 - m.bbY)
    agg = m.groupby(["scan", "nr_id"]).agg(sbid=("bbY", "sum"), sfee=("fee_unit", "sum"), minsz=("bsY", "min")).reset_index()
    agg = agg.merge(g, on=["scan", "nr_id"], how="left")
    print(f"window {W}: scans {agg.scan.nunique()}, group-scans {len(agg)}, distinct groups {agg.nr_id.nunique()}")
    rows = []
    for lab, f in FS.items():
        e = agg.sbid - f * agg.sfee - 1
        pos = agg[e > 0]
        clean = pos[~pos.inplay.fillna(False) & ~pos.other_flag.fillna(False)]
        rows.append({"fee_level": lab, "group_scans_pos": len(pos), "distinct_groups_pos": pos.nr_id.nunique(),
                     "distinct_pos_not_inplay_noflag": clean.nr_id.nunique(),
                     "per_scan_mean_pos": round(len(pos) / agg.scan.nunique(), 2),
                     "median_edge_pos": round(float((pos.sbid - f * pos.sfee - 1).median()), 4) if len(pos) else None,
                     "median_min_top_size_pos": float(pos.minsz.median()) if len(pos) else None})
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    out.to_parquet(ROOT / "data" / "derived" / f"complete_set_arb_fee_sensitivity_{W}.parquet", index=False)


if __name__ == "__main__":
    main()
