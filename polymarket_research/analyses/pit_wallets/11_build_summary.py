"""Print the descriptive counts used in notes/strategies/pit_wallets_build.md (sections 6-8).

Run from polymarket_research/:  python analyses/pit_wallets/11_build_summary.py [section]
section in {screens, eval, cluster, audit, all}. Descriptive only: no follower return or evaluation-window
performance is computed here (stage 1 does not look at outcomes of the evaluation window).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "pit_wallets"
def md(df: pd.DataFrame, index: bool = True) -> str:
    """Minimal markdown table (tabulate is not installed)."""
    df = df.reset_index() if index else df
    df.columns = [" ".join(map(str, c)) if isinstance(c, tuple) else str(c) for c in df.columns]
    rows = [" | ".join(df.columns), " | ".join("---" for _ in df.columns)]
    rows += [" | ".join(str(v) for v in r) for r in df.itertuples(index=False)]
    return "\n".join("| " + r + " |" for r in rows)


SPLIT = lambda d: np.where(d < pd.Timestamp("2025-01-01", tz="UTC"), "train",
                           np.where(d < pd.Timestamp("2025-07-01", tz="UTC"), "validation", "test"))


def screens():
    b = pd.read_parquet(OUT / "screen_base_rates.parquet")
    b["date"] = b.D_date.dt.strftime("%Y-%m")
    cols = ["date", "n_w_counted", "n_res5", "n_res10", "n_s1", "n_s1m", "n_s2", "n_s3", "n_s4_sports", "n_s4_politics",
            "n_s4_crypto", "n_s4_other", "s5_n_top", "s5_pnl_cut"]
    t = b[cols].copy()
    t["s5_pnl_cut"] = t.s5_pnl_cut.round(0).astype(int)
    print(md(t, index=False))
    # consistency: member files vs server counts
    chk = {s: bool((b[f"members_{s}"] == b[c]).all()) for s, c in
           [("S1", "n_s1"), ("S1m", "n_s1m"), ("S2", "n_s2"), ("S3", "n_s3"), ("S4_sports", "n_s4_sports")]}
    print("member rows == server counts:", chk, "S5 cut inside every bucket:", bool(b.s5_cut_inside_all_buckets.all()))
    b["S1_share_of_res5"] = b.n_s1 / b.n_res5
    b["S2_share_of_res5"] = b.n_s2 / b.n_res5
    print("S1/eligible(n_res>=5) range:", b.S1_share_of_res5.min().round(4), b.S1_share_of_res5.max().round(4),
          " S2/eligible range:", b.S2_share_of_res5.min().round(4), b.S2_share_of_res5.max().round(4))
    m = pd.read_parquet(OUT / "screen_members.parquet",
                        columns=["D_date", "screen", "wallet", "n_res", "n_won", "pnl", "med_usd", "usd_res", "n_unrel",
                                 "mean_edge", "shrunk_edge", "z_shrunk", "t_plain", "n_win", "first_fill"])
    m["split"] = SPLIT(m.D_date)
    g = m.groupby(["screen", "split"]).agg(rows=("wallet", "size"), wallets=("wallet", "nunique")).unstack("split")
    print(md(g))
    d = m.groupby("screen").agg(med_n_res=("n_res", "median"), med_mean_edge=("mean_edge", "median"),
                                med_trailing_pnl=("pnl", "median"), med_decision_usd=("med_usd", "median"),
                                share_unrel=("n_unrel", lambda s: float((s > 0).mean())))
    print(md(d.round(3)))
    # persistence of S1 membership across consecutive dates (descriptive, trailing only)
    s1 = m[m.screen == "S1"]
    by = s1.groupby("D_date").wallet.apply(set).sort_index()
    pers = [len(a & b) / len(a) for a, b in zip(by.values[:-1], by.values[1:]) if len(a)]
    print("S1 members still S1 next month: median", round(float(np.median(pers)), 3))
    fr = pd.read_parquet(OUT / "fresh_first_decisions.parquet", columns=["t0", "ep_usd", "p"])
    print("fresh first decisions:", len(fr), "with episode >= $1k:", int((fr.ep_usd >= 1000).sum()))


def evals():
    cov = pd.read_parquet(OUT / "eval_coverage.parquet")
    cov["split"] = SPLIT(cov.D_date)
    print(md(cov.groupby(["screen", "split"])[["members", "sampled_dec", "sampled_fill", "exported_decisions",
                                             "wallets_with_decisions"]].sum().unstack("split").fillna(0).astype(int)))
    d = pd.read_parquet(OUT / "eval_decisions.parquet",
                        columns=["D", "wallet", "underlying_key", "has_meta", "clean_resolution", "F1_large", "F2_returning",
                                 "first_taker_share", "ep_usd", "t0", "D_date"])
    print("eval decisions:", len(d), "wallet-dates:", d.groupby(["D", "wallet"]).ngroups,
          "distinct underlying events:", d.underlying_key.nunique(), "no-meta share:", round(1 - d.has_meta.astype(bool).mean(), 4),
          "clean share:", round(d.clean_resolution.mean(), 4))
    print("F1 large share (defined):", round(float(pd.to_numeric(d.F1_large, errors="coerce").mean()), 4),
          "F2 returning share:", round(float(d.F2_returning.mean()), 4),
          "first second fully taker:", round(float((d.first_taker_share > 0.999).mean()), 4))
    inwin = ((d.t0 >= d.D) & (d.t0 < d.D + 32 * 86400)).mean()
    print("t0 inside window share:", round(float(inwin), 4))
    b = pd.read_parquet(OUT / "eval_buys.parquet", columns=["D", "wallet", "ts", "role", "price", "usd", "token_id"])
    print("eval buys:", len(b), "wallet-dates:", b.groupby(["D", "wallet"]).ngroups, "taker share:",
          round(float((b.role == "taker").mean()), 4), "no-meta share:", round(float(b.token_id.isna().mean()), 4),
          "price in (0,1]:", round(float(((b.price > 0) & (b.price <= 1.0001)).mean()), 5))


def cluster():
    s = pd.read_parquet(OUT / "cluster_signals.parquet")
    print("signals:", len(s), "tokens:", s.k.nunique(), "underlying events:", s.underlying_key.nunique(),
          "clean:", round(float(s.clean_resolution.mean()), 3))
    print(md(s.groupby("split").agg(signals=("k", "size"), events=("underlying_key", "nunique"))))
    print(md(s.groupby("category").agg(signals=("k", "size"), events=("underlying_key", "nunique"))))
    print("wallets counting median/max:", s.n_wallets_counting.median(), s.n_wallets_counting.max(),
          " window notional median:", round(float(s.usd_window.median())),
          " fresh-wallet VWAP quantiles 10/50/90:", s.vwap_window.quantile([.1, .5, .9]).round(3).tolist())
    h = ((s.r - s.signal_ts) / 3600).where(s.r > 0)
    print("hours from signal to t_res, quantiles 10/50/90:", h.quantile([.1, .5, .9]).round(1).tolist(),
          " signals at/after t_res:", int((h <= 0).sum()))


def audit():
    a = pd.read_parquet(OUT / "audit_sample.parquet")
    ok = a.dropna(subset=["a_n_res"]).copy()
    flag = {"S1": "a_S1", "S1m": "a_S1m", "S2": "a_S2", "S3": "a_S3"}
    ok["reproduced"] = [bool(r[flag[r.screen]]) for _, r in ok.iterrows()]
    print("audited:", len(ok), "skipped:", len(a) - len(ok), a.get("skipped", pd.Series(dtype=str)).value_counts().to_dict())
    print("n_res equal:", round(float((ok.a_n_res == ok.n_res).mean()), 3), "n_won equal:",
          round(float((ok.a_n_won == ok.n_won).mean()), 3), "|edge-sum diff| < 0.01:",
          round(float(((ok.a_se - ok.se).abs() < 0.01).mean()), 3), "n_mm equal:", round(float((ok.a_n_mm == ok.n_mm).mean()), 3))
    print(md(ok.groupby("screen").reproduced.agg(["size", "mean"])))
    bad = ok[(ok.a_n_res != ok.n_res) | (ok.a_n_won != ok.n_won) | ~ok.reproduced]
    if len(bad):
        print(md(bad[["screen", "n_trade_rows", "n_res", "a_n_res", "n_won", "a_n_won", "n_mm", "a_n_mm"]], index=False))


if __name__ == "__main__":
    sec = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in [("screens", screens), ("eval", evals), ("cluster", cluster), ("audit", audit)]:
        if sec in (name, "all"):
            print(f"\n===== {name}")
            fn()
