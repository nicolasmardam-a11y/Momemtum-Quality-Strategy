"""Merge evaluation-window chunks (06_eval_export.py) into analysis-ready tables.

Run from polymarket_research/:  python analyses/pit_wallets/06b_eval_merge.py
Outputs (data/derived/pit_wallets/):
  eval_decisions.parquet  one row per (D, wallet, new decision in [D, next month)), with token/market/event metadata,
                          entry details, F1 (large bet) and F2 (returning) flags and the wallet's screens at D
  eval_buys.parquet       one row per BUY fill in the window of the fill-export sub-sample
                          (D, wallet, token, ts, shares, collateral, price, role, tx hash)
  eval_coverage.parquet   per (D, screen): members, sampled for decisions, sampled for fills, exported decisions
F1: collateral bought in the first 10 min of the decision >= 5 x the wallet's median decision notional at D
    (screen feature med_usd; NaN median -> F1 undefined).
F2: no active UTC day of the wallet in the 60 days before the decision's day (day resolution, addendum A5).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "pit_wallets"
CATS = ["sports", "politics", "crypto", "other"]


def main():
    parts = [pd.read_parquet(p) for p in sorted((OUT / "eval_chunks").glob("D*_c*.parquet"))]
    raw = pd.concat(parts, ignore_index=True)
    wi = pd.read_parquet(OUT / "eval_wallet_index.parquet")
    tok = pd.read_parquet(OUT / "token_meta_pit.parquet",
                          columns=["k", "token_id", "condition_id", "event_key", "underlying_key", "event_slug", "question",
                                   "outcome", "category", "negRisk"])
    tok["k"] = tok.k.astype("uint64")
    raw["k"] = raw.k.astype("uint64")
    raw["wi"] = raw.wi.astype("int64")
    raw = raw.merge(wi, on="wi", how="left")
    mem = pd.read_parquet(OUT / "screen_members.parquet", columns=["D", "wallet", "screen", "med_usd", "n_res", "pnl"])
    smp = pd.read_parquet(OUT / "eval_sample_members.parquet")
    # ---------------- decisions
    d = raw[raw.is_new.astype(bool)].copy()
    d = d.drop_duplicates(["D", "wallet", "k"])
    for c in ["t0", "w_last_before", "ep_n", "p", "r", "cat", "c_idx", "e_idx"]:
        d[c] = d[c].astype("int64")
    for c in ["ep_sh", "ep_usd", "ep_ssh", "usd10m", "sh_first", "usd_first", "usd_first_taker"]:
        d[c] = d[c].astype(float)
    d["entry_vwap"] = d.ep_usd / d.ep_sh
    d["first_price"] = d.usd_first / d.sh_first
    d["first_taker_share"] = d.usd_first_taker / d.usd_first
    d["first_tx"] = d.first_fill_id.str.split("_").str[0]
    d["first_order_hash"] = d.first_fill_id.str.split("_").str[1]
    day0 = d.D // 86400 - 61
    off = d.t0 // 86400 - day0
    d["prev_active_day_gap"] = [
        (int(o) - max([x for x in days if x < o], default=-10**6)) for o, days in zip(off, d.w_days)]
    has_prior = (d.w_last_before > 0) | (d.prev_active_day_gap < 10**5)
    d["F2_returning"] = has_prior & (d.prev_active_day_gap > 60)
    med = mem.groupby(["D", "wallet"]).med_usd.max().rename("med_usd_at_D")
    scr = mem.groupby(["D", "wallet"]).screen.apply(lambda s: "|".join(sorted(set(s)))).rename("screens_at_D")
    sdec = smp[smp.in_dec].groupby(["D", "wallet"]).screen.apply(lambda s: "|".join(sorted(set(s)))).rename("sampled_for")
    d = d.join(med, on=["D", "wallet"]).join(scr, on=["D", "wallet"]).join(sdec, on=["D", "wallet"])
    d["F1_large"] = np.where(d.med_usd_at_D > 0, d.usd10m >= 5 * d.med_usd_at_D, np.nan)
    d = d.merge(tok, on="k", how="left")
    d["category"] = d.category.fillna(pd.Series(CATS, dtype=object).reindex(d.cat).values)
    d["clean_resolution"] = d.p >= 0
    d["outcome_won"] = np.where(d.p >= 0, d.p == 1, np.nan)
    d["t0_time"] = pd.to_datetime(d.t0, unit="s", utc=True)
    d["D_date"] = pd.to_datetime(d.D, unit="s", utc=True)
    d["t_res"] = pd.to_datetime(d.r.where(d.r > 0), unit="s", utc=True)
    keep = ["D", "D_date", "wallet", "screens_at_D", "sampled_for", "token_id", "k", "condition_id", "event_key",
            "underlying_key", "event_slug", "question", "outcome", "category", "negRisk", "has_meta", "t0", "t0_time",
            "first_price", "sh_first", "usd_first", "first_taker_share", "usd10m", "ep_n", "ep_sh", "ep_usd", "ep_ssh",
            "entry_vwap", "first_tx", "first_order_hash", "p", "clean_resolution", "outcome_won", "r", "t_res",
            "w_last_before", "prev_active_day_gap", "F2_returning", "med_usd_at_D", "F1_large"]
    d = d[keep]
    d.to_parquet(OUT / "eval_decisions.parquet", index=False)
    # ---------------- buys
    b = raw[raw.wb.map(len) > 0][["D", "wallet", "k", "wb", "is_new"]].explode("wb")
    b["ts"] = b.wb.map(lambda x: int(x[0]))
    b["shares"] = b.wb.map(lambda x: float(x[1]))
    b["usd"] = b.wb.map(lambda x: float(x[2]))
    b["role"] = b.wb.map(lambda x: "taker" if bool(x[3]) else "maker")
    b["tx_hash"] = b.wb.map(lambda x: "0x" + format(int(x[4]), "064x"))
    b = b.drop(columns=["wb"]).rename(columns={"is_new": "token_is_new_decision"})
    b["price"] = b.usd / b.shares
    b = b.merge(tok[["k", "token_id", "condition_id", "category"]], on="k", how="left")
    b["time"] = pd.to_datetime(b.ts, unit="s", utc=True)
    b = b.drop_duplicates(["D", "wallet", "k", "ts", "shares", "usd", "tx_hash"])
    b.to_parquet(OUT / "eval_buys.parquet", index=False)
    # ---------------- coverage
    cov = smp.groupby(["D", "screen"]).agg(members=("wallet", "size"), sampled_dec=("in_dec", "sum"),
                                           sampled_fill=("in_fill", "sum")).reset_index()
    ex = d.assign(screen=d.sampled_for.str.split("|")).explode("screen").groupby(["D", "screen"]).agg(
        exported_decisions=("t0", "size"), wallets_with_decisions=("wallet", "nunique")).reset_index()
    cov = cov.merge(ex, on=["D", "screen"], how="left")
    cov["D_date"] = pd.to_datetime(cov.D, unit="s", utc=True)
    cov.to_parquet(OUT / "eval_coverage.parquet", index=False)
    print("decisions", len(d), "wallets", d.wallet.nunique(), "buys", len(b))
    print(cov.groupby("screen")[["members", "sampled_dec", "sampled_fill", "exported_decisions"]].sum().to_string())


if __name__ == "__main__":
    main()
