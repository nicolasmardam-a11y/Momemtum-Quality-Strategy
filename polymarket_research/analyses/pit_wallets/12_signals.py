"""Stage 2, step 12: build the follower signal table and the pricing sample (no prices, no outcomes used).

Run from polymarket_research/:  python analyses/pit_wallets/12_signals.py
Signal types (pre-registration section 7 + stage-2 addendum A10):
  P   primary: each new decision of a sampled screened wallet, signal time t0 (first fill).
  F1  pre-registered 'large bet' (10-min buys >= 5x own median): signal time t0 + 600 s (knowable only then).
  F1b exploratory 'large bet' known at t0 (first-second $ >= 5x own median): evaluated inside the P sample.
  F2  'returning' (no active day in the 60 days before): signal time t0; all F2 decisions are priced.
  ADD every add-on BUY fill-second of the fill-export sub-sample (excluding the first-fill second of a new decision).
  CL  fresh-wallet cluster signals (signal_ts).
S4_<cat> follows only decisions in that category. Unclean / no-metadata markets are excluded (counted).
Sample (A10): Bernoulli hash sample per (split, screen, type): include if u < min(1, cap / n), u = md5(wallet|k|t0).
Outputs (data/derived/pit_wallets/): sig_members.parquet (one row per (signal, screen)), sig_pricing.parquet
(unique (k, t_sig, wallet) rows to price, psid), sig_sample_counts.parquet.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "pit_wallets"
CAP = {"P": 8000, "F1": 2000, "ADD": 2000}
CATS = {"S4_crypto": "crypto", "S4_sports": "sports", "S4_politics": "politics", "S4_other": "other"}
T_VAL, T_TEST = 1735689600, 1751328000   # 2025-01-01, 2025-07-01


def split_of(D):
    return np.where(D < T_VAL, "train", np.where(D < T_TEST, "val", "test"))


def u_hash(*cols):
    return np.array([int(hashlib.md5("|".join(map(str, x)).encode()).hexdigest()[:13], 16) / 16 ** 13
                     for x in zip(*cols)])


def explode_screens(df, col):
    x = df.assign(screen=df[col].str.split("|")).explode("screen")
    keep = ~x.screen.isin(list(CATS)) | (x.screen.map(CATS) == x.category)
    return x[keep]


def main():
    tm = pd.read_parquet(OUT / "token_meta_pit.parquet",
                         columns=["k", "token_id", "underlying_key", "category", "p", "market_clean", "r", "has_meta"])
    d = pd.read_parquet(OUT / "eval_decisions.parquet",
                        columns=["D", "wallet", "sampled_for", "k", "token_id", "t0", "underlying_key", "category",
                                 "has_meta", "clean_resolution", "p", "r", "usd_first", "usd10m", "med_usd_at_D",
                                 "F1_large", "F2_returning", "first_price", "entry_vwap", "ep_usd", "first_taker_share"])
    d["split"] = split_of(d.D.values)
    n0 = len(d)
    d["ok"] = d.has_meta & d.clean_resolution.fillna(False).astype(bool)
    print(f"decisions {n0}, excluded unclean/no-meta {int((~d.ok).sum())}")
    d = d[d.ok].copy()
    d["u"] = u_hash(d.wallet, d.k, d.t0)
    d["F1b"] = d.usd_first >= 5 * d.med_usd_at_D
    d["F1"] = d.F1_large.astype(bool)
    x = explode_screens(d, "sampled_for")
    rows = []
    # P (and F1b, F2 inside it): rate per (split, screen)
    n = x.groupby(["split", "screen"]).size().rename("n").reset_index()
    n["rate"] = np.minimum(1.0, CAP["P"] / n.n)
    x = x.merge(n[["split", "screen", "rate"]], on=["split", "screen"])
    p = x[x.u < x.rate].assign(stype="P", t_sig=lambda z: z.t0)
    rows.append(p)
    # F2: all
    rows.append(x[x.F2_returning.astype(bool)].assign(stype="F2", t_sig=lambda z: z.t0, rate=1.0))
    # F1 (pre-registered, signal time t0 + 600 s)
    f1 = x[x.F1].drop(columns="rate")
    nf = f1.groupby(["split", "screen"]).size().rename("n").reset_index()
    nf["rate"] = np.minimum(1.0, CAP["F1"] / nf.n)
    f1 = f1.merge(nf[["split", "screen", "rate"]], on=["split", "screen"])
    rows.append(f1[f1.u < f1.rate].assign(stype="F1", t_sig=lambda z: z.t0 + 600))
    sig = pd.concat(rows, ignore_index=True)
    sig["src"] = "decision"
    # ADD: add-on buy fill-seconds of the fill-export sub-sample
    b = pd.read_parquet(OUT / "eval_buys.parquet", columns=["D", "wallet", "k", "ts", "usd", "token_is_new_decision"])
    b = b.groupby(["D", "wallet", "k", "ts"], as_index=False).agg(usd=("usd", "sum"), newtok=("token_is_new_decision", "max"))
    first = d[["D", "wallet", "k", "t0"]].rename(columns={"t0": "ts"}).assign(isfirst=1)
    # also exclude first seconds of new decisions that were unclean (not in d): use the raw decision file
    draw = pd.read_parquet(OUT / "eval_decisions.parquet", columns=["D", "wallet", "k", "t0"]).rename(columns={"t0": "ts"})
    draw["isfirst"] = 1
    b = b.merge(draw.drop_duplicates(), on=["D", "wallet", "k", "ts"], how="left")
    b = b[b.isfirst.isna()].drop(columns="isfirst")
    b = b.merge(tm, on="k", how="left")
    nb0 = len(b)
    b = b[b.has_meta.fillna(False).astype(bool) & b.market_clean.fillna(False).astype(bool)].copy()
    print(f"add-on buy-seconds {nb0}, excluded unclean/no-meta {nb0 - len(b)}")
    sm = pd.read_parquet(OUT / "eval_sample_members.parquet")
    sm = sm[sm.in_fill].groupby(["D", "wallet"]).screen.apply(lambda s: "|".join(sorted(s))).rename("fill_for").reset_index()
    b = b.merge(sm, on=["D", "wallet"], how="inner")
    b["split"] = split_of(b.D.values)
    b["u"] = u_hash(b.wallet, b.k, b.ts)
    bx = explode_screens(b, "fill_for")
    nb = bx.groupby(["split", "screen"]).size().rename("n").reset_index()
    nb["rate"] = np.minimum(1.0, CAP["ADD"] / nb.n)
    bx = bx.merge(nb[["split", "screen", "rate"]], on=["split", "screen"])
    add = bx[bx.u < bx.rate].assign(stype="ADD", t_sig=lambda z: z.ts, t0=lambda z: z.ts, src="fill")
    add = add.rename(columns={"usd": "usd_first"})
    # CL: cluster signals
    cl = pd.read_parquet(OUT / "cluster_signals.parquet")
    cl = cl[cl.split.isin(["train_2024", "validation_2025H1", "test_2025H2"])].copy()
    ncl0 = len(cl)
    cl = cl[cl.clean_resolution.astype(bool)]
    cl = cl.assign(stype="CL", screen="CL", t_sig=cl.signal_ts, t0=cl.signal_ts, wallet="", D=0, rate=1.0, u=0.0,
                   split=cl.split.map({"train_2024": "train", "validation_2025H1": "val", "test_2025H2": "test"}), src="cluster")
    print(f"cluster signals {ncl0}, excluded unclean {ncl0 - len(cl)}")
    keep = ["stype", "screen", "split", "D", "wallet", "k", "token_id", "t0", "t_sig", "underlying_key", "category",
            "p", "r", "rate", "u", "src", "usd_first", "usd10m", "med_usd_at_D", "first_price", "entry_vwap", "ep_usd",
            "F1b", "F2_returning", "first_taker_share"]
    allsig = pd.concat([sig.reindex(columns=keep), add.reindex(columns=keep), cl.reindex(columns=keep)], ignore_index=True)
    allsig["wallet"] = allsig.wallet.fillna("")
    allsig["k"] = allsig.k.astype("uint64")
    allsig["t_sig"] = allsig.t_sig.astype("int64")
    pr = allsig[["k", "t_sig", "wallet"]].drop_duplicates().sort_values(["t_sig", "k"]).reset_index(drop=True)
    pr["psid"] = np.arange(len(pr), dtype="uint32")
    allsig = allsig.merge(pr, on=["k", "t_sig", "wallet"])
    allsig.to_parquet(OUT / "sig_members.parquet", index=False)
    pr.to_parquet(OUT / "sig_pricing.parquet", index=False)
    cnt = allsig.groupby(["stype", "screen", "split"]).agg(n=("psid", "size"), events=("underlying_key", "nunique"),
                                                           rate=("rate", "first")).reset_index()
    cnt.to_parquet(OUT / "sig_sample_counts.parquet", index=False)
    print(cnt.pivot_table(index=["stype", "screen"], columns="split", values="n", aggfunc="sum").fillna(0).astype(int).to_string())
    print("pricing rows", len(pr), "member rows", len(allsig))


if __name__ == "__main__":
    main()
