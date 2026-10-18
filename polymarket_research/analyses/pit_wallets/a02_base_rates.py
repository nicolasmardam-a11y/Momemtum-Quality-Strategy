"""Stage 4 (audit), step a02: economic sense of the 5-for-5 screen (S1): base rate and a price-implied 'luck' null.

Uses only stage-1 trailing records (screen_members.parquet; no evaluation-window data):
  * B1 rows (flag 512) are a 1% hash sample of ALL eligible wallets (>= 5 counted resolved decisions) at each date, so
    they give the population distribution of n_res and n_won.
  * For a wallet with n resolved bets at entry prices p_i, the probability of winning all of them if prices were fair is
    prod p_i. Only sums are stored (se = sum(y - p), sv = sum p(1-p)), so bounds are used:
      lower 1 - sum(1 - p_i) (Weierstrass), upper (mean p)^n (AM-GM).
  * Calibration: actual wins vs price-implied wins (sum p_i = n_won - se) for the random eligible sample.
Output: data/derived/pit_wallets/audit/a02_base_rates.parquet; summary on stdout.
Run from polymarket_research/:  python analyses/pit_wallets/a02_base_rates.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "pit_wallets"


def main():
    m = pd.read_parquet(OUT / "screen_members.parquet",
                        columns=["D", "wallet", "flags", "n_res", "n_won", "se", "sv", "pnl", "usd_res", "screen"])
    m = m.drop_duplicates(["D", "wallet"])
    m["split"] = np.where(m.D < 1735689600, "train", np.where(m.D < 1751328000, "val", "test"))
    b1 = m[(m["flags"] & 512) > 0].copy()
    s1 = m[(m["flags"] & 1) > 0].copy()
    br = pd.read_parquet(OUT / "screen_base_rates.parquet", columns=["D", "n_res5", "n_s1", "n_s2"])
    rows = []
    for sp, g in b1.groupby("split"):
        e5 = g[g.n_res == 5]
        sump = e5.n_won - e5.se
        lo = np.clip(1 - (5 - sump), 0, 1); hi = (sump / 5) ** 5
        allw = g.n_won.sum(); imp = (g.n_won - g.se).sum()
        rows.append(dict(split=sp, b1_rows=len(g), share_exactly5=len(e5) / len(g),
                         p55_obs=float((e5.n_won == 5).mean()), p55_null_lo=float(lo.mean()), p55_null_hi=float(hi.mean()),
                         s1_flag_consistency=float(((e5.n_won == 5) == ((e5["flags"] & 1) > 0)).mean()),
                         win_rate=float(g.n_won.sum() / g.n_res.sum()), implied_win_rate=float(imp / g.n_res.sum()),
                         mean_edge_pts=float(100 * g.se.sum() / g.n_res.sum())))
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print("Random eligible wallets (B1, 1% hash sample of all eligible wallets):")
    print(t.round(4).to_string(index=False))
    # S1 members: implied mean entry price and luck probability bounds
    s1["mean_px"] = 1 - s1.se / 5
    s1["null_lo"] = np.clip(1 - s1.se, 0, 1)
    s1["null_hi"] = s1.mean_px ** 5
    q = s1.groupby("split").agg(rows=("wallet", "size"), med_px=("mean_px", "median"),
                                share_px_ge090=("mean_px", lambda x: (x >= 0.90).mean()),
                                med_null_lo=("null_lo", "median"), med_null_hi=("null_hi", "median"),
                                share_null_lo_ge05=("null_lo", lambda x: (x >= 0.5).mean()),
                                med_pnl=("pnl", "median"), share_pnl_le0=("pnl", lambda x: (x <= 0).mean()),
                                med_usd_res=("usd_res", "median"))
    print("\nS1 members (exactly 5 resolved, all won): implied mean entry price and probability of 5/5 under fair prices")
    print(q.round(3).to_string())
    br["s1_share_of_eligible"] = br.n_s1 / br.n_res5
    print("\nS1 share of eligible wallets by date: min %.3f median %.3f max %.3f" %
          (br.s1_share_of_eligible.min(), br.s1_share_of_eligible.median(), br.s1_share_of_eligible.max()))
    t.to_parquet(OUT / "audit" / "a02_base_rates.parquet", index=False)
    q.reset_index().to_parquet(OUT / "audit" / "a02_s1_profile.parquet", index=False)


if __name__ == "__main__":
    main()
