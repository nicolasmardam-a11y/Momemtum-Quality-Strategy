"""Peak capital deployed over time, order-size patterns and cross-wallet timing (seconds) for the
overlapping KSA-URY markets. Outputs: data/derived/ge_capital.parquet, ge_size_patterns.parquet, ge_overlap_timing.parquet"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
OUT = ROOT / "data" / "derived"
f = pd.read_parquet(OUT / "ge_fills.parquet")
dm = pd.read_parquet(OUT / "ge_dec_market.parquet")
act = pd.read_parquet(OUT / "ge_activity.parquet")
mk = pd.read_parquet(OUT / "ge_markets.parquet").set_index("conditionId")
cap = []
for lab, g in f.groupby("label"):
    # cash view: buys+fees out, redemptions/rebates in
    ev = [(r.timestamp, -(r.notional + r.fee)) for r in g.itertuples()]
    a = act[(act.label == lab) & act.type.isin(["REDEEM", "TAKER_REBATE", "MAKER_REBATE", "REWARD"])]
    ev += [(r.timestamp, r.usdc_size) for r in a.itertuples()]
    ev = sorted(ev)
    cum = np.cumsum([x[1] for x in ev])
    # exposure view: cost of positions bought and not yet resolved (closedTime)
    expo = []
    for t, _ in ev:
        d = dm[dm.label == lab]
        open_ = d[(d.first_fill_utc.map(lambda x: x.timestamp()) <= t) & (d.condition_id.map(lambda c: pd.Timestamp(mk.loc[c, "closedTime"]).timestamp()) > t)]
        sub = g[(g.timestamp <= t) & g.condition_id.isin(open_.condition_id)]
        expo.append((sub.notional + sub.fee).sum())
    cap.append({"label": lab, "peak_cumulative_net_outlay": -cum.min(), "peak_open_cost_unresolved": max(expo),
                "final_net_cash": cum[-1]})
cap = pd.DataFrame(cap)
cap.to_parquet(OUT / "ge_capital.parquet", index=False)
print(cap)
# size patterns: taker 'orders' (one row per tx) notional roundness
sp = []
for lab, g in f.groupby("label"):
    t = g[g.role == "taker"]
    usd = t.notional
    rnd = (np.abs(usd - np.round(usd / 10000) * 10000) < 5) & (usd >= 10000)
    sp.append({"label": lab, "n_taker_fills": len(t), "median_taker_usd": usd.median(), "max_taker_usd": usd.max(),
               "share_taker_round_10k": rnd.mean(), "n_maker_fills": (g.role == "maker").sum(),
               "median_maker_usd": g.loc[g.role == "maker", "notional"].median(),
               "maker_usd_total": g.loc[g.role == "maker", "notional"].sum(),
               "examples": ", ".join(f"{x:,.2f}" for x in usd.sort_values(ascending=False).head(6))})
sp = pd.DataFrame(sp); sp.to_parquet(OUT / "ge_size_patterns.parquet", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 120)
print(sp.to_string())
# overlap timing on KSA-URY markets incl. the co-trader LEEEROYJENKINS seen in the tape
L = "0x99aea8f9a64d0142b6b66a4b9d02a2211d45386f"
rows = []
for cid in f[f.match_key == "fifwc-ksa-ury-2026-06-15"].condition_id.unique():
    tp = pd.read_parquet(OUT / f"ge_tape_{cid[:10]}.parquet")
    for nm, addr in [("endlessFate", "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2"), ("LEEEROYJENKINS", L),
                     ("mintblade", "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb")]:
        x = tp[tp.proxy_wallet == addr]
        if len(x):
            rows.append({"market": mk.loc[cid, "question"], "wallet": nm, "outcome": ",".join(sorted(set(x.outcome))),
                         "side": ",".join(sorted(set(x.side))), "first_ts": x.timestamp.min(), "last_ts": x.timestamp.max(),
                         "usd": (x["size"] * x.price).sum(), "vwap": (x["size"] * x.price).sum() / x["size"].sum()})
ov = pd.DataFrame(rows).sort_values(["market", "first_ts"])
ov["first_utc"] = pd.to_datetime(ov.first_ts, unit="s"); ov["last_utc"] = pd.to_datetime(ov.last_ts, unit="s")
ov["gap_s_from_prev_wallet_last_fill"] = ov.groupby("market").first_ts.transform(lambda s: s) - ov.groupby("market").last_ts.shift()
ov.to_parquet(OUT / "ge_overlap_timing.parquet", index=False)
print(ov.drop(columns=["first_ts", "last_ts"]).to_string())
p = api.public_profile(L)
print({k: p.get(k) for k in ["name", "pseudonym", "createdAt", "takerTierName", "weightedVolume"]}, (p.get("users") or [{}])[0].get("id"))
print(api.user_stats(L))
