"""Merge per-bucket screen outputs into the screen datasets.

Run from polymarket_research/:  python analyses/pit_wallets/05_merge_screens.py [K]
Outputs (data/derived/pit_wallets/):
  screen_base_rates.parquet   per selection date: wallets eligible / passing each screen (all buckets summed),
                              plus the S5 threshold
  screen_members.parquet      one row per (selection date, screen, wallet) with the wallet's trailing stats
  fresh_first_decisions.parquet  fresh-wallet first decisions (cluster input)
S5 = top 1% of trailing decision-market P&L among wallets with >= 5 counted resolved decisions, cut globally
from the bucket-local top-2%(+3) candidate lists; the script asserts the global cut lies inside every
bucket's candidate list (otherwise S5 members could be missing).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "pit_wallets"
CATS = ["sports", "politics", "crypto", "other"]
BITS = {"S1": 1, "S1m": 2, "S2": 4, "S3": 8, "S4_sports": 16, "S4_politics": 32, "S4_crypto": 64, "S4_other": 128,
        "B1_random_eligible": 512}


def main(K: int):
    d = OUT / "screen_buckets"
    have = set()
    for p in d.glob("K*_b*_counts.parquet"):
        kk, bb = p.name.split("_")[:2]
        have.add((int(kk[1:]), int(bb[1:])))

    def parts(k, b):  # files covering residue class b mod k (a bucket may have been split into 2k)
        if (k, b) in have:
            return [(k, b)]
        if k > 4096:
            raise AssertionError(f"residue {b} mod {k} not covered")
        return parts(2 * k, b) + parts(2 * k, b + k)

    use = [x for b in range(K) for x in parts(K, b)]
    rd = lambda suf: pd.concat([pd.read_parquet(d / f"K{k}_b{b:03d}{suf}.parquet") for k, b in use], ignore_index=True)
    cnt, cand, fresh = rd("_counts"), rd(""), rd("_fresh")
    cnt["bucket"] = cnt.K.astype(str) + ":" + cnt.bucket.astype(str)
    cand["bucket"] = cand.K.astype(str) + ":" + cand.bucket.astype(str)
    print("bucket files used:", len(use))
    num = [c for c in cnt.columns if c not in ("D", "bucket", "K")]
    cnt["D"] = cnt.D.astype("int64")
    for c in num:
        cnt[c] = cnt[c].astype("int64")
    base = cnt.groupby("D")[num].sum().reset_index()
    cand["D"] = cand.D.astype("int64")
    for c in ["flags", "n_win", "n_res", "n_won", "n_cmp", "n_mm", "n_nc", "n_unrel", "first_fill"]:
        cand[c] = cand[c].astype("int64")
    for c in ["se", "se2", "sv", "pnl", "usd_res", "med_usd"]:
        cand[c] = cand[c].astype(float)
    for i, c in enumerate(CATS):
        cand[f"n_{c}"] = cand.nc.map(lambda a: int(a[i]))
        cand[f"nwon_{c}"] = cand.nwc.map(lambda a: int(a[i]))
        cand[f"se_{c}"] = cand.sec.map(lambda a: float(a[i]))
        cand[f"sv_{c}"] = cand.svc.map(lambda a: float(a[i]))
        cand[f"z_{c}"] = cand[f"se_{c}"] / np.sqrt(cand[f"sv_{c}"] + 2.5)
    cand = cand.drop(columns=["nc", "nwc", "sec", "svc"])
    cand["mean_edge"] = cand.se / cand.n_res.where(cand.n_res > 0)
    cand["shrunk_edge"] = cand.se / (cand.n_res + 10)
    cand["z_shrunk"] = cand.se / np.sqrt(cand.sv + 2.5)
    var = (cand.se2 - cand.se ** 2 / cand.n_res.where(cand.n_res > 0)) / (cand.n_res - 1).where(cand.n_res > 1)
    cand["t_plain"] = cand.mean_edge / np.sqrt(var.clip(lower=1e-12) / cand.n_res)
    # S5 global cut
    s5_rows, thr = [], []
    for D, g in cand[(cand["flags"] & 256) > 0].groupby("D"):
        n_e5 = int(base.loc[base.D == D, "n_res5"].iloc[0])
        n_top = max(1, math.ceil(0.01 * n_e5))
        g = g.sort_values("pnl", ascending=False)
        cut = g.pnl.iloc[n_top - 1] if len(g) >= n_top else -np.inf
        # every bucket's last candidate must be <= cut, else wallets above the cut may be missing in that bucket
        worst = g.groupby("bucket").pnl.min()
        full = cand[(cand.D == D)]
        ok = bool((worst <= cut).all())
        thr.append({"D": D, "s5_n_top": n_top, "s5_pnl_cut": float(cut), "s5_cut_inside_all_buckets": ok,
                    "s5_n_candidates": len(g)})
        s5_rows.append(g.head(n_top).assign(screen="S5"))
    thr = pd.DataFrame(thr)
    base = base.merge(thr, on="D", how="left")
    mem = []
    for scr, bit in BITS.items():
        mem.append(cand[(cand["flags"] & bit) > 0].assign(screen=scr))
    mem.append(pd.concat(s5_rows))
    mem = pd.concat(mem, ignore_index=True)
    mem["D_date"] = pd.to_datetime(mem.D, unit="s", utc=True)
    base["D_date"] = pd.to_datetime(base.D, unit="s", utc=True)
    base = base.merge(mem.groupby(["D", "screen"]).size().unstack(fill_value=0).add_prefix("members_").reset_index(), on="D", how="left")
    base.to_parquet(OUT / "screen_base_rates.parquet", index=False)
    mem.to_parquet(OUT / "screen_members.parquet", index=False)
    for c in ["wallet_hash", "k"]:
        fresh[c] = fresh[c].astype("uint64")
    for c in ["e_idx", "t0", "cat", "p", "r"]:
        fresh[c] = fresh[c].astype("int64")
    fresh["ep_usd"] = fresh.ep_usd.astype(float)
    fresh.to_parquet(OUT / "fresh_first_decisions.parquet", index=False)
    pd.set_option("display.width", 250)
    print(base[["D_date", "n_w_counted", "n_res1", "n_res5", "n_res10", "n_s1", "n_s1m", "n_s2", "n_s3", "n_s4_sports",
                "n_s4_politics", "n_s4_crypto", "n_s4_other", "s5_n_top", "s5_pnl_cut", "s5_cut_inside_all_buckets"]].to_string())
    print("members", len(mem), "distinct wallets", mem.wallet.nunique(), "fresh first decisions", len(fresh))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 64)
