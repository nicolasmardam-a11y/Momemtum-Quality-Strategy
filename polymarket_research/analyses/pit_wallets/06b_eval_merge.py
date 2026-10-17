"""Merge evaluation-window chunks (06_eval_export.py) into analysis-ready tables.

Run from polymarket_research/:  python analyses/pit_wallets/06b_eval_merge.py
Outputs (data/derived/pit_wallets/):
  eval_decisions.parquet     one row per (D, wallet, new decision in [D, next month)), with token/market/event metadata,
                             entry details of the FOLLOWED wallet (not follower prices), F1 (large bet) and F2 (returning)
                             flags and the wallet's screens at D
  eval_buys.parquet          one row per BUY fill in the window of the fill-export sub-sample, capped at the first 1,000
                             fills per (D, wallet) plus ties in the 1,000th fill's second (addendum A9)
                             (D, wallet, token, ts, shares, collateral, price, role, tx hash)
  eval_fill_wallets.parquet  per (D, wallet) of the fill-export sub-sample: total window buys and whether the cap applied
  eval_coverage.parquet      per (D, screen): members, sampled for decisions, sampled for fills, exported decisions
Chunk formats: v1 (months finished before A9) carry c/e/p/r/cat, the first fill id and the per-day activity array, and
are uncapped; v2 carry prev_day and first_tx and are capped server side. Both are normalised here to one schema and
the cap is applied to v1 locally with the same rule.
F1: collateral bought in the first 10 min of the decision >= 5 x the wallet's median decision notional at D
    (screen feature med_usd; NaN median -> F1 undefined).
F2: the wallet had earlier activity and none in the 60 days before the decision's UTC day (day resolution, A5).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "pit_wallets"
CATS = ["sports", "politics", "crypto", "other"]
FILL_CAP = 1000


def load_chunks() -> pd.DataFrame:
    parts = []
    for p in sorted((OUT / "eval_chunks").glob("D*_c*.parquet")):
        x = pd.read_parquet(p)
        if "fmt" not in x.columns:  # format v1
            x["fmt"] = 1
            day0 = x.D // 86400 - 61
            dd = x.t0 // 86400 - day0
            x["prev_day"] = [max([int(d) for d in days if d < o], default=-1) if new else -1
                             for o, days, new in zip(dd, x.w_days, x.is_new.astype(bool))]
            x["first_tx"] = x.first_fill_id.fillna("").str.split("_").str[0]
            x = x.drop(columns=["c_idx", "e_idx", "p", "r", "cat", "w_days", "first_fill_id"])
        parts.append(x)
    raw = pd.concat(parts, ignore_index=True)
    raw["k"] = raw.k.astype("uint64")
    raw["wi"] = raw.wi.astype("int64")
    return raw


def main():
    raw = load_chunks()
    wi = pd.read_parquet(OUT / "eval_wallet_index.parquet")
    tok = pd.read_parquet(OUT / "token_meta_pit.parquet",
                          columns=["k", "token_id", "condition_id", "c_idx", "e_idx", "event_key", "underlying_key", "event_slug",
                                   "question", "outcome", "category", "cat_idx", "negRisk", "p", "r", "market_clean"])
    tok["k"] = tok.k.astype("uint64")
    raw = raw.merge(wi, on="wi", how="left")
    assert raw.wallet.notna().all()
    mem = pd.read_parquet(OUT / "screen_members.parquet", columns=["D", "wallet", "screen", "med_usd", "n_res", "pnl"])
    smp = pd.read_parquet(OUT / "eval_sample_members.parquet")
    # ---------------- decisions
    d = raw[raw.is_new.astype(bool)].copy()
    d = d.drop_duplicates(["D", "wallet", "k"])
    for c in ["t0", "w_last_before", "ep_n", "prev_day"]:
        d[c] = d[c].astype("int64")
    for c in ["ep_sh", "ep_usd", "ep_ssh", "usd10m", "sh_first", "usd_first", "usd_first_taker"]:
        d[c] = d[c].astype(float)
    d["entry_vwap"] = d.ep_usd / d.ep_sh
    d["first_price"] = d.usd_first / d.sh_first
    d["first_taker_share"] = d.usd_first_taker / d.usd_first
    day0 = d.D // 86400 - 61
    dd = d.t0 // 86400 - day0
    last_off = np.where(d.w_last_before > 0, d.w_last_before // 86400 - day0, np.nan)
    d["prev_active_day_gap"] = np.where(d.prev_day >= 0, dd - d.prev_day, dd - last_off)  # NaN = no earlier activity
    d["F2_returning"] = d.prev_active_day_gap > 60
    med = mem.groupby(["D", "wallet"]).med_usd.max().rename("med_usd_at_D")
    scr = mem.groupby(["D", "wallet"]).screen.apply(lambda s: "|".join(sorted(set(s)))).rename("screens_at_D")
    sdec = smp[smp.in_dec].groupby(["D", "wallet"]).screen.apply(lambda s: "|".join(sorted(set(s)))).rename("sampled_for")
    d = d.join(med, on=["D", "wallet"]).join(scr, on=["D", "wallet"]).join(sdec, on=["D", "wallet"])
    d["F1_large"] = np.where(d.med_usd_at_D > 0, d.usd10m >= 5 * d.med_usd_at_D, np.nan)
    d = d.merge(tok, on="k", how="left")
    d["has_meta"] = d.has_meta.astype(bool)
    d["clean_resolution"] = d.has_meta & (d.p >= 0)
    d["outcome_won"] = np.where(d.clean_resolution, d.p == 1, np.nan)
    d["t0_time"] = pd.to_datetime(d.t0, unit="s", utc=True)
    d["D_date"] = pd.to_datetime(d.D, unit="s", utc=True)
    d["t_res"] = pd.to_datetime(d.r.where(d.r > 0), unit="s", utc=True)
    keep = ["D", "D_date", "wallet", "screens_at_D", "sampled_for", "token_id", "k", "condition_id", "event_key",
            "underlying_key", "event_slug", "question", "outcome", "category", "negRisk", "has_meta", "t0", "t0_time",
            "first_price", "sh_first", "usd_first", "first_taker_share", "usd10m", "ep_n", "ep_sh", "ep_usd", "ep_ssh",
            "entry_vwap", "first_tx", "p", "clean_resolution", "outcome_won", "r", "t_res",
            "w_last_before", "prev_active_day_gap", "F2_returning", "med_usd_at_D", "F1_large", "fmt"]
    d = d[keep]
    d.to_parquet(OUT / "eval_decisions.parquet", index=False)
    # ---------------- buys (fill-export sub-sample)
    b = raw[raw.wb_ts.map(len) > 0][["D", "wallet", "k", "wb_ts", "wb_sh", "wb_usd", "wb_taker", "wb_tx", "is_new", "fmt"]].explode(
        ["wb_ts", "wb_sh", "wb_usd", "wb_taker", "wb_tx"])
    b["ts"] = b.wb_ts.astype("int64")
    b["shares"] = b.wb_sh.astype(float)
    b["usd"] = b.wb_usd.astype(float)
    b["role"] = np.where(b.wb_taker.astype(bool), "taker", "maker")
    b["tx_hash"] = b.wb_tx.astype(str)
    b = b.drop(columns=["wb_ts", "wb_sh", "wb_usd", "wb_taker", "wb_tx"]).rename(columns={"is_new": "token_is_new_decision"})
    b = b.drop_duplicates(["D", "wallet", "k", "ts", "shares", "usd", "tx_hash"])
    # per (D, wallet) totals and the A9 cap (v2: server counts; v1: complete local fills)
    cnts = []
    for p in sorted((OUT / "eval_chunks").glob("counts_D*.parquet")):
        cnts.append(pd.read_parquet(p))
    fw = pd.DataFrame(columns=["D", "wallet", "n_buys_window", "fill_cap_ts"])
    if cnts:
        cn = pd.concat(cnts).merge(wi, on="wi", how="left")
        fw = cn[["D", "wallet", "n_buys_window", "fill_cap_ts"]]
    v1 = b[b.fmt == 1]
    if len(v1):
        g = v1.groupby(["D", "wallet"]).ts
        c1 = pd.DataFrame({"n_buys_window": g.size(),
                           "fill_cap_ts": g.apply(lambda s: int(np.sort(s.values)[FILL_CAP - 1]) if len(s) > FILL_CAP else 0)}).reset_index()
        fw = pd.concat([fw[~fw.set_index(["D", "wallet"]).index.isin(c1.set_index(["D", "wallet"]).index)], c1],
                       ignore_index=True)
    fw["D"] = fw.D.astype("int64"); fw["n_buys_window"] = fw.n_buys_window.astype("int64")
    fw["fill_cap_ts"] = fw.fill_cap_ts.astype("int64")
    b = b.merge(fw[["D", "wallet", "fill_cap_ts"]], on=["D", "wallet"], how="left")
    b = b[(b.fill_cap_ts.fillna(0) == 0) | (b.ts <= b.fill_cap_ts)].drop(columns=["fill_cap_ts"])
    sub = smp[smp.in_fill][["D", "wallet"]].drop_duplicates()
    fw = sub.merge(fw, on=["D", "wallet"], how="left")
    fw["n_buys_window"] = fw.n_buys_window.fillna(0).astype("int64")
    fw["fill_capped"] = fw.fill_cap_ts.fillna(0) > 0
    fw = fw.merge(b.groupby(["D", "wallet"]).size().rename("n_buys_exported").reset_index(), on=["D", "wallet"], how="left")
    fw["n_buys_exported"] = fw.n_buys_exported.fillna(0).astype("int64")
    fw.to_parquet(OUT / "eval_fill_wallets.parquet", index=False)
    b["price"] = b.usd / b.shares
    b = b.merge(tok[["k", "token_id", "condition_id", "underlying_key", "category"]], on="k", how="left")
    b["time"] = pd.to_datetime(b.ts, unit="s", utc=True)
    b.to_parquet(OUT / "eval_buys.parquet", index=False)
    # ---------------- coverage
    cov = smp.groupby(["D", "screen"]).agg(members=("wallet", "size"), sampled_dec=("in_dec", "sum"),
                                           sampled_fill=("in_fill", "sum")).reset_index()
    ex = d.assign(screen=d.sampled_for.str.split("|")).explode("screen").groupby(["D", "screen"]).agg(
        exported_decisions=("t0", "size"), wallets_with_decisions=("wallet", "nunique")).reset_index()
    cov = cov.merge(ex, on=["D", "screen"], how="left")
    exported_months = sorted(raw.D.unique())
    cov["month_exported"] = cov.D.isin(exported_months)
    cov["D_date"] = pd.to_datetime(cov.D, unit="s", utc=True)
    cov.to_parquet(OUT / "eval_coverage.parquet", index=False)
    print("decisions", len(d), "wallets", d.wallet.nunique(), "buys", len(b), "months", len(exported_months),
          "capped fill wallets", int(fw.fill_capped.sum()), "of", len(fw))
    print(cov.groupby("screen")[["members", "sampled_dec", "sampled_fill", "exported_decisions"]].sum().to_string())


if __name__ == "__main__":
    main()
