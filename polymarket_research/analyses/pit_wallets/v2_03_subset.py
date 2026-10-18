"""Stage 3, step 3: candidate pool from the pool tapes and the wallet subset (pre-2026-06-01 information only).

Run from polymarket_research/:  python analyses/pit_wallets/v2_03_subset.py [targetA targetB targetC targetD targetE]
Pool = every wallet with any fill (taker_only=false) in a sampled pool market (all fills are before the markets'
t_res < 2026-06-01). Classes A-E (see the stage-3 note, section 1). Subset = Bernoulli by md5('sub|wallet') < q_class,
q_class = min(1, target_class / size_class). Output: v2/pool_wallets.parquet, v2/wallet_subset.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from v2common import T_D, V2, load_markets, u01  # noqa: E402

TARGET = {"A": 1000, "B": 800, "C": 600, "D": 400, "E": 200}


def main() -> None:
    if len(sys.argv) == 6:
        for k, v in zip("ABCDE", sys.argv[1:]):
            TARGET[k] = int(v)
    ps = pd.read_parquet(V2 / "pool_sample.parquet", columns=["condition_id", "stratum"])
    m = load_markets(["condition_id", "event_slug", "category4", "t_res", "clean", "pay0", "pay1"])
    m = m[m["condition_id"].isin(ps["condition_id"])]
    dfs = []
    for cid in ps["condition_id"]:
        f = V2 / "tapes_pool" / f"{cid[2:20]}.parquet"
        d = pd.read_parquet(f)
        d["condition_id"] = cid
        dfs.append(d)
    t = pd.concat(dfs, ignore_index=True)
    assert t["timestamp"].max() < T_D, "pool fill after D"
    t = t.merge(m[["condition_id", "ue", "pay0", "pay1"]], on="condition_id", how="left")
    t["pay"] = np.where(t["outcome_index"] == 0, t["pay0"], np.where(t["outcome_index"] == 1, t["pay1"], np.nan))
    print(f"pool fills {len(t):,}, markets {t['condition_id'].nunique()}, wallets {t['proxy_wallet'].nunique():,}")
    g = t.groupby("proxy_wallet")
    w = pd.DataFrame({"n_fills_pool": g.size(), "n_mkts_pool": g["condition_id"].nunique()})
    b = t[t["side"] == 1].sort_values(["proxy_wallet", "ue", "timestamp"])
    fb = b.groupby(["proxy_wallet", "ue"], as_index=False).first()
    gw = fb.groupby("proxy_wallet")
    w["n_ue_buy"] = gw.size()
    w["n_ue_won"] = gw["pay"].sum()
    w = w.fillna({"n_ue_buy": 0, "n_ue_won": 0})
    w["cls"] = np.select(
        [(w["n_ue_buy"] >= 2) & (w["n_ue_won"] == w["n_ue_buy"]), w["n_ue_buy"] >= 2,
         (w["n_ue_buy"] == 1) & (w["n_ue_won"] == 1), w["n_ue_buy"] == 1], ["A", "B", "C", "D"], "E")
    w = w.reset_index().rename(columns={"proxy_wallet": "wallet"})
    size = w["cls"].value_counts()
    q = {c: min(1.0, TARGET[c] / size.get(c, 1)) for c in "ABCDE"}
    w["q_cls"] = w["cls"].map(q)
    w["u_sub"] = w["wallet"].map(lambda x: u01("sub|" + x))
    w["in_subset"] = w["u_sub"] < w["q_cls"]
    # pool markets each wallet was seen in (needed for inclusion probabilities)
    seen = t.groupby("proxy_wallet")["condition_id"].agg(lambda s: sorted(set(s))).rename("pool_cids")
    w = w.merge(seen, left_on="wallet", right_index=True, how="left")
    w.to_parquet(V2 / "pool_wallets.parquet", index=False)
    sub = w[w["in_subset"]].copy()
    sub.to_parquet(V2 / "wallet_subset.parquet", index=False)
    print("class sizes:", size.to_dict())
    print("q:", {k: round(v, 5) for k, v in q.items()})
    print("subset:", sub["cls"].value_counts().to_dict(), "total", len(sub))
    print("pool n_mkts_pool quantiles:", w["n_mkts_pool"].quantile([.5, .9, .99, .999]).to_dict())


if __name__ == "__main__":
    main()
