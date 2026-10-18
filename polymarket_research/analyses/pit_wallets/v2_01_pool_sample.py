"""Stage 3, step 1: stratified sample of markets that resolved 2026-01-15 .. 2026-05-31 (candidate-pool frame).

Run from polymarket_research/:  python analyses/pit_wallets/v2_01_pool_sample.py
Frame: markets_2026.parquet rows with clean {1,0} resolution and t_res in [2026-01-15, 2026-06-01).
Strata: category4 (sports, politics, crypto, other) x volume tier (T1 < $10k, T2 $10k-$1M, T3 >= $1M, Gamma volumeNum).
Within a stratum the n_s markets with the smallest md5('pool|condition_id') are taken (simple random sample without
replacement, outcome-blind). N_s and n_s are saved so wallet inclusion probabilities can be computed later.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from v2common import V2, u01  # noqa: E402

N_PER = {"T1": 60, "T2": 80, "T3": 40}


def tier(v: float) -> str:
    return "T1" if v < 1e4 else ("T2" if v < 1e6 else "T3")


def main() -> None:
    m = pd.read_parquet(V2 / "markets_2026.parquet",
                        columns=["condition_id", "ue", "event_slug", "category4", "t_res", "clean", "volumeNum"])
    f = m[m["clean"] & (m["t_res"] >= "2026-01-15") & (m["t_res"] < "2026-06-01")].copy()
    f["volumeNum"] = f["volumeNum"].fillna(0.0)
    f["tier"] = f["volumeNum"].map(tier)
    f["stratum"] = f["category4"] + "_" + f["tier"]
    f["u"] = f["condition_id"].map(lambda c: u01("pool|" + c))
    f = f.sort_values(["stratum", "u"])
    f["rank"] = f.groupby("stratum").cumcount()
    f["N_s"] = f.groupby("stratum")["condition_id"].transform("size")
    f["n_s"] = f["tier"].map(N_PER).clip(upper=f["N_s"])
    s = f[f["rank"] < f["n_s"]].drop(columns=["rank"])
    # frame table (needed for inclusion probabilities: which frame markets each wallet traded, by stratum)
    f[["condition_id", "ue", "stratum", "N_s", "n_s", "t_res"]].to_parquet(V2 / "pool_frame.parquet", index=False)
    s.to_parquet(V2 / "pool_sample.parquet", index=False)
    st = s.groupby("stratum").agg(n=("condition_id", "size"), N=("N_s", "first"), vol_M=("volumeNum", lambda x: x.sum() / 1e6))
    st["f"] = st["n"] / st["N"]
    print(st.round(4).to_string())
    print("sample markets", len(s), "distinct ue", s["ue"].nunique(), "total volume $M", round(s["volumeNum"].sum() / 1e6, 1))


if __name__ == "__main__":
    main()
