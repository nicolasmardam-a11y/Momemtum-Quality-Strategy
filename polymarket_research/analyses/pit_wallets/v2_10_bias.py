"""Stage 3, step 10: candidate-pool sampling diagnostics.

Run from polymarket_research/:  python analyses/pit_wallets/v2_10_bias.py
1. Inclusion probability and IPW weight distribution by class; Kish effective sample size.
2. Screen base rates at D (share of eligible wallets), unweighted vs IPW, against the full-population
   CryptoHouse rates of stage 1 (2025-06-01 .. 2025-12-01, screen_base_rates.parquet).
3. Trailing-record profile of members (median n_res, average entry price, made-money share of S1 decisions).
4. Eval activity: share of members with >= 1 new decision in the eval window.
Writes v2/bias_text.txt.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from v2common import ROOT, V2  # noqa: E402


def kish(w: np.ndarray) -> float:
    return float(w.sum() ** 2 / (w ** 2).sum()) if len(w) else np.nan


def main() -> None:
    w = pd.read_parquet(V2 / "screens_D.parquet")
    lines = []
    lines.append(f"subset {len(w):,}; heavy (trailing cap hit, excluded) {int(w['heavy'].sum())} "
                 f"({w['heavy'].mean():.1%}); eligible {int(w['eligible'].sum()):,}")
    t = w[~w["heavy"]].groupby("cls").agg(n=("wallet", "size"), pi_med=("pi_pool", "median"),
                                          m_frame_med=("m_frame", "median"), w_med=("weight", "median"),
                                          elig=("eligible", "mean"))
    lines.append("by class (non-heavy):\n" + t.round(4).to_string())
    el = w[w["eligible"]]
    lines.append(f"eligible: Kish ESS of IPW weights {kish(el['weight'].to_numpy()):.0f} of {len(el)}; "
                 f"weight p50 {el['weight'].median():.0f}, p99 {el['weight'].quantile(.99):.0f}, max {el['weight'].max():.0f}")
    br = pd.read_parquet(ROOT / "data" / "derived" / "pit_wallets" / "screen_base_rates.parquet")
    br = br[br["D_date"] >= "2025-06-01"]
    pop = {"S1": (br["n_s1"] / br["n_res5"]).mean(), "S2": (br["n_s2"] / br["n_res5"]).mean(),
           "S3": (br["n_s3"] / br["n_res5"]).mean(), "S5": (br["s5_n_top"] / br["n_res5"]).mean()}
    rows = []
    for s in ["S1", "S2", "S3", "S5"]:
        x = el[el[s]]
        rows.append({"screen": s, "n": len(x), "share_unw": len(x) / len(el),
                     "share_ipw": x["weight"].sum() / el["weight"].sum(), "pop_2025H2_mean": pop[s],
                     "med_n_res": x["n_res"].median(), "avg_px": x["avg_px"].mean(),
                     "mm_share": (x["n_mm"] / x["n_res"]).mean(), "med_pnl": x["pnl"].median(),
                     "ess": kish(x["weight"].to_numpy())})
    lines.append("screen base rates (share of eligible) vs stage-1 population 2025-06..12 mean:\n" +
                 pd.DataFrame(rows).round(4).to_string(index=False))
    lines.append(f"eligible wallets: weighted share with n_res >= 10: "
                 f"{el.loc[el['n_res'] >= 10, 'weight'].sum() / el['weight'].sum():.3f}; unweighted {float((el['n_res'] >= 10).mean()):.3f}")
    sigp = V2 / "eval_signals.parquet"
    if sigp.exists():
        sg = pd.read_parquet(sigp, columns=["wallet", "evaluable"])
        act = sg.groupby("wallet").size()
        ev = pd.read_parquet(V2 / "eval_wallets.parquet")
        for s in ["S1", "S2", "S3", "S5", "B1"]:
            mem = w.loc[w[s], "wallet"]
            a = mem.map(act).fillna(0)
            lines.append(f"{s}: members {len(mem)}, with >= 1 new decision Jun-Sep {float((a > 0).mean()):.2f}, "
                         f"median new decisions {a.median():.0f}, p90 {a.quantile(.9):.0f}")
        lines.append(f"eval wallets {len(ev)}")
    txt = "\n\n".join(lines)
    (V2 / "bias_text.txt").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
