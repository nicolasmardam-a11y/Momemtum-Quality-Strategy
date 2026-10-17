"""Cluster signal candidate (pre-registration section 12 + addendum A2), client-side from fresh_first_decisions.parquet.

Run from polymarket_research/:  python analyses/pit_wallets/08_cluster_signals.py
Input rows: one per fresh wallet (first-ever exchange fill is the BUY that starts its first decision, 6 h
episode >= $100), with the episode BUY fills (ts, shares, usd) of the decision token.
Rule: for each outcome token, at each minute m (UTC minute index), consider fresh-wallet BUY fills of that
token with minute in (m-60, m]. A wallet counts at m if its cumulative episode buys of the token up to its
fill minute are >= $100 (only past fills). Signal = first minute with >= 3 counting wallets AND combined
fresh-wallet buy notional in the window >= $20,000. Signal time = end of that minute. One signal per token.
Writes data/derived/pit_wallets/cluster_signals.parquet (one row per signal) and
cluster_signal_members.parquet (the fresh fills inside each signal window).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "pit_wallets"
MIN_W, MIN_USD_W, MIN_TOT, WIN = 3, 100.0, 20000.0, 60


def main():
    fr = pd.read_parquet(OUT / "fresh_first_decisions.parquet")
    rows = fr[["wallet_hash", "k", "e_idx", "t0", "cat", "p", "r", "ep_ts", "ep_sh", "ep_usd_fills"]].explode(
        ["ep_ts", "ep_sh", "ep_usd_fills"]).rename(columns={"ep_ts": "ts", "ep_sh": "sh", "ep_usd_fills": "usd"})
    rows = rows.dropna(subset=["ts"])
    rows["ts"] = rows.ts.astype("int64"); rows["sh"] = rows.sh.astype(float); rows["usd"] = rows.usd.astype(float)
    rows["minute"] = rows.ts // 60
    rows = rows.sort_values(["k", "wallet_hash", "ts"])
    rows["cum"] = rows.groupby(["k", "wallet_hash"]).usd.cumsum()
    # cheap pre-filter: tokens with >= 3 fresh wallets reaching $100 and >= $20k in total
    g = rows.groupby("k").agg(nw=("wallet_hash", "nunique"), tot=("usd", "sum"))
    keep = g[(g.nw >= MIN_W) & (g.tot >= MIN_TOT)].index
    r = rows[rows.k.isin(keep)].sort_values(["k", "minute", "ts"])
    sigs, mems = [], []
    for k, t in r.groupby("k", sort=False):
        mins = np.unique(t.minute.values)
        for m in mins:
            w = t[(t.minute > m - WIN) & (t.minute <= m)]
            cw = w[w.cum >= MIN_USD_W].wallet_hash.nunique()
            tot = w.usd.sum()
            if cw >= MIN_W and tot >= MIN_TOT:
                sigs.append({"k": k, "e_idx": int(t.e_idx.iloc[0]), "cat": int(t.cat.iloc[0]), "p": int(t.p.iloc[0]),
                             "r": int(t.r.iloc[0]), "signal_minute": int(m), "signal_ts": int((m + 1) * 60),
                             "n_wallets_counting": int(cw), "n_wallets_any": int(w.wallet_hash.nunique()),
                             "usd_window": float(tot), "sh_window": float(w.sh.sum()),
                             "vwap_window": float(tot / w.sh.sum()) if w.sh.sum() > 0 else np.nan,
                             "first_fill_ts_window": int(w.ts.min()), "last_fill_ts_window": int(w.ts.max())})
                mems.append(w.assign(signal_minute=int(m)))
                break
    s = pd.DataFrame(sigs)
    if len(s):
        s["signal_time"] = pd.to_datetime(s.signal_ts, unit="s", utc=True)
        s["k"] = s.k.astype("uint64")
        tok = pd.read_parquet(OUT / "token_meta_pit.parquet",
                              columns=["k", "token_id", "condition_id", "underlying_key", "event_slug", "question", "outcome",
                                       "category", "negRisk"])
        tok["k"] = tok.k.astype("uint64")
        s = s.merge(tok, on="k", how="left")
        s["clean_resolution"] = s.p >= 0
        s["t_res"] = pd.to_datetime(s.r.where(s.r > 0), unit="s", utc=True)
        s["split"] = np.select([s.signal_ts < 1735689600, s.signal_ts < 1751328000, s.signal_ts < 1767225600],
                               ["train_2024", "validation_2025H1", "test_2025H2"], "after_2025")
        s.loc[s.signal_ts < 1704067200, "split"] = "pre_2024"
    s.to_parquet(OUT / "cluster_signals.parquet", index=False)
    (pd.concat(mems) if mems else pd.DataFrame()).to_parquet(OUT / "cluster_signal_members.parquet", index=False)
    print("fresh first decisions", len(fr), "tokens pre-filtered", len(keep), "signals", len(s))
    if len(s):
        print(s.groupby(s.signal_time.dt.year).size().to_string())
        print(s.groupby("split").size().to_string())
        print(s.groupby("category").size().to_string())


if __name__ == "__main__":
    main()
