"""Ex-post 'copy' test on the wallets' own decisions: a follower buys the same outcome with $1 per
market-episode at the last taker trade price by others at (first fill + lag) or (last fill + lag),
pays the taker fee rate*p*(1-p) per share, holds to resolution. Trade prices are not executable quotes,
and depth is ignored (the wallets themselves took 70-100% of taker volume), so this is an upper bound.
In-play entries are only copied if the lagged time is still before the final whistle.
Output: data/derived/ge_copy_lag.parquet"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived"
f = pd.read_parquet(OUT / "ge_fills.parquet")
f = f[f.notional > 100]
rows = []
for (lab, eid, cid, tok), g in f.groupby(["label", "episode_id", "condition_id", "token_id"]):
    tk = pd.read_parquet(OUT / f"ge_tape_taker_{cid[:10]}.parquet")
    tk = tk[tk.proxy_wallet != g.proxy_wallet.iloc[0]].sort_values("timestamp")
    tk["p"] = np.where(tk.token_id == tok, tk.price, 1 - tk.price)
    payout, rate = g.payout.iloc[0], g.fee_rate.iloc[0]
    vw = g.notional.sum() / g["size"].sum()
    for anchor, t in (("first_fill", g.timestamp.min()), ("last_fill", g.timestamp.max())):
        for lag in (0, 60, 300, 900):
            x = tk[tk.timestamp <= t + lag]
            if not len(x):
                continue
            p = float(x.p.iloc[-1])
            if p <= 0 or p >= 1:
                continue
            ret = (payout - p - rate * p * (1 - p)) / (p + rate * p * (1 - p))
            rows.append({"label": lab, "episode_id": eid, "question": g.question.iloc[0], "outcome": g.outcome.iloc[0],
                         "anchor": anchor, "lag_s": lag, "wallet_vwap": vw, "follower_price": p,
                         "payout": payout, "follower_return_per_$": ret,
                         "wallet_return_per_$": (payout - vw - rate * vw * (1 - vw)) / (vw + rate * vw * (1 - vw))})
d = pd.DataFrame(rows)
d.to_parquet(OUT / "ge_copy_lag.parquet", index=False)
s = d.groupby(["label", "anchor", "lag_s"]).agg(n=("follower_return_per_$", "size"), mean_ret=("follower_return_per_$", "mean"),
                                               median_ret=("follower_return_per_$", "median"), wins=("payout", "sum"),
                                               mean_price=("follower_price", "mean"), wallet_mean_ret=("wallet_return_per_$", "mean"))
pd.set_option("display.width", 200)
print(s.round(3).to_string())
