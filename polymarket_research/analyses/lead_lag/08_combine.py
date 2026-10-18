"""Pool live windows (episodes + grids from 03_live_analyze) and apply the pre-registered rejection criteria R1-R5.
Run: python -m analyses.lead_lag.08_combine L2 L3 -> data/derived/lead_lag/live_pooled_summary.json
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

D = "data/derived/lead_lag/"
TAGS = sys.argv[1:] or ["L2", "L3"]
rng = np.random.default_rng(11)


def boot(df, col, n=4000):
    df = df[df[col].notna()]
    if df.empty:
        return {"mean": None, "lo": None, "hi": None, "n": 0, "markets": 0}
    mk = df.slug.unique()
    by = {s: df.loc[df.slug == s, col].values for s in mk}
    ms = [np.concatenate([by[s] for s in rng.choice(mk, len(mk))]).mean() for _ in range(n)]
    return {"mean": float(df[col].mean()), "lo": float(np.percentile(ms, 2.5)), "hi": float(np.percentile(ms, 97.5)),
            "n": int(len(df)), "markets": int(len(mk))}


E = pd.concat([pd.read_parquet(f"{D}live_{t}_episodes.parquet").assign(tag=t) for t in TAGS], ignore_index=True)
G = pd.concat([pd.read_parquet(f"{D}live_{t}_grid.parquet").assign(tag=t) for t in TAGS], ignore_index=True)
out = {"tags": TAGS, "grid_rows": int(len(G)), "grid_markets": int(G.slug.nunique()),
       "grid_seconds_by_kind": G.groupby("kind").size().to_dict()}
out["episodes"] = {"n": int(len(E)), "by_kind": E.groupby("kind").size().to_dict(), "markets_with_episode": int(E.slug.nunique()),
                   "median_dur_s": float(E.dur.median()), "share_dur_ge2": float((E.dur >= 2).mean()),
                   "share_survive_1s": float(E.del_ok.mean()), "median_edge_t0": float(E.edge_at_t0.median()),
                   "median_depth_best_t0_shares": float(E.depth_t0.median()), "median_depth_1c_t0_shares": float(E.depth1c_t0.median()),
                   "median_ask_t0": float(E.ask_t0.median()), "median_tau_t0_s": float(E.tau_t0.median()),
                   "resolved_share": float(E.payout.notna().mean())}
out["pnl"] = {"hold_now": boot(E, "now_pnl"), "hold_delayed_1s": boot(E, "del_pnl"),
              "hold_delayed_survivors": boot(E[E.del_ok == True], "del_pnl"),  # noqa: E712
              "mk5_mid": boot(E, "del_mk5_mid"), "mk30_mid": boot(E, "del_mk30_mid"), "mk60_mid": boot(E, "del_mk60_mid"),
              "mk30_bid_entryfee": boot(E, "del_mk30_bid"), "mk30_bid_bothfees": boot(E, "del_mk30_bidfee")}
# robustness: block bootstrap by 15-min clock block (BTC and ETH windows that share a block share spot shocks)
Eb = E.assign(slug=(E.t0 // 900).astype(int).astype(str))
out["pnl_block15m"] = {"hold_delayed_1s": boot(Eb, "del_pnl"), "mk30_bid_entryfee": boot(Eb, "del_mk30_bid")}
out["pnl_by_kind_delayed"] = {k: boot(x, "del_pnl", 1000) for k, x in E.groupby("kind")}
out["hit_rate_delayed"] = float((E.del_pnl > 0).mean())
# R3: log-loss at 10-s samples where both sides are quoted with spread <= 10 c
S = G[(G.t.round() % 10 == 0) & G.win0.notna() & G.mid.notna() & (G.spread <= 0.10)]
clip = lambda p: np.clip(p, 1e-3, 1 - 1e-3)
ll = lambda y, p: float(-np.mean(y * np.log(clip(p)) + (1 - y) * np.log(1 - clip(p))))
out["R3"] = {"n": int(len(S)), "markets": int(S.slug.nunique()), "ll_fair": ll(S.win0, S.fair), "ll_mid": ll(S.win0, S.mid),
             "by_kind": {k: {"n": int(len(x)), "markets": int(x.slug.nunique()), "ll_fair": ll(x.win0, x.fair), "ll_mid": ll(x.win0, x.mid)}
                         for k, x in S.groupby("kind")}}
tight = G[(G.spread <= 0.05) & G.fair.between(0.05, 0.95)]
out["fair_minus_mid_tight"] = {k: {"n": int(len(x)), "median_abs": float((x.fair - x.mid).abs().median()), "mean": float((x.fair - x.mid).mean())}
                               for k, x in tight.groupby("kind")}
out["spread_median_by_kind"] = G[G.spread.notna() & G.fair.between(0.05, 0.95)].groupby("kind").spread.median().to_dict()
out["ask_depth_best_median_by_kind"] = G[G.fair.between(0.2, 0.8)].groupby("kind").ask_sz.median().to_dict()
out["ask_depth_1c_median_by_kind"] = G[G.fair.between(0.2, 0.8)].groupby("kind").ask_d1.median().to_dict()
Gm = G[G.fair.between(0.05, 0.95)].assign(medge=lambda x: np.fmax(x.edge0, x.edge1))
out["share_seconds_max_edge_ge"] = {k: {str(th): float((x.medge >= th).mean()) for th in (0.0, 0.01, 0.02, 0.05)} | {"n": int(len(x))}
                                    for k, x in Gm.groupby("kind")}
e = out["episodes"]
p = out["pnl"]["hold_delayed_1s"]
out["verdicts"] = {
    "R1_persistence": "REJECT" if (e["median_dur_s"] < 2 or e["share_survive_1s"] < 0.25) else "pass",
    "R2_pnl_hold": "REJECT (no demonstrated edge)" if (p["mean"] is None or p["mean"] <= 0 or p["lo"] <= 0) else "pass",
    "R2_pnl_mk30": "REJECT (no demonstrated edge)" if (out["pnl"]["mk30_bid_entryfee"]["mean"] is None or out["pnl"]["mk30_bid_entryfee"]["lo"] <= 0) else "pass",
    "R3_model_vs_mid": "REJECT (model error)" if out["R3"]["ll_fair"] >= out["R3"]["ll_mid"] else "pass",
    "R5_sample": "inconclusive (<20 episodes)" if e["n"] < 20 else "ok"}
json.dump(out, open(f"{D}live_pooled_summary.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str))
