"""Pool the spot-move event studies (05_live_lag.py) across live windows: taker round trip in the direction of a Binance
move, entry at t_E + L (ask of the side the move favours), exit at t_E + L + H (bid), both legs charged the crypto taker fee.
Descriptive (latency curve), not a pre-registered test; the pre-registered tests are R1-R5 in 08_combine.py.
Run: python -m analyses.lead_lag.09_latency_pool L2 L3 L4 -> data/derived/lead_lag/live_latency_pool.json
"""
import json
import sys

import numpy as np
import pandas as pd

D = "data/derived/lead_lag/"
TAGS = sys.argv[1:] or ["L2", "L3", "L4"]
rng = np.random.default_rng(5)


def boot(df, col, n=3000):
    df = df[df[col].notna()]
    if df.empty:
        return None
    mk = df.slug.unique()
    by = {s: df.loc[df.slug == s, col].values for s in mk}
    ms = [np.concatenate([by[s] for s in rng.choice(mk, len(mk))]).mean() for _ in range(n)]
    return {"mean": round(float(df[col].mean()), 4), "lo": round(float(np.percentile(ms, 2.5)), 4),
            "hi": round(float(np.percentile(ms, 97.5)), 4), "share_pos": round(float((df[col] > 0).mean()), 3),
            "n": int(len(df)), "markets": int(len(mk))}


out = {"tags": TAGS}
for name in ("events", "events_fast1s"):
    fs = []
    for t in TAGS:
        try:
            x = pd.read_parquet(f"{D}live_{t}_{name}.parquet")
            x["tag"] = t
            fs.append(x)
        except FileNotFoundError:
            pass
    E = pd.concat(fs, ignore_index=True)
    E["spot_event"] = E.tag + "_" + E.asset + "_" + E.te.round(1).astype(str)
    res = {"n_market_events": int(len(E)), "n_spot_events": int(E.spot_event.nunique()), "by_tag": E.groupby("tag").size().to_dict(),
           "lat_s_quantiles": {str(q): round(float(E.lat_s.quantile(q)), 3) for q in (0.1, 0.25, 0.5, 0.75, 0.9)},
           "share_moved_before_tE": round(float((E.lat_s < 0).mean()), 3), "median_abs_ret_bp": round(float(E.ret_bp.abs().median()), 2)}
    for L in (0.0, 0.2, 0.5, 1.0, 2.0, 5.0):
        for H in (10, 30):
            res[f"net_L{L}_H{H}"] = boot(E, f"rt_L{L}_H{H}")
            res[f"gross_L{L}_H{H}"] = boot(E, f"gross_L{L}_H{H}")
    out[name] = res
json.dump(out, open(f"{D}live_latency_pool.json", "w"), indent=1)
for name in ("events", "events_fast1s"):
    r = out[name]
    print(name, {k: r[k] for k in ("n_market_events", "n_spot_events", "by_tag", "lat_s_quantiles", "share_moved_before_tE", "median_abs_ret_bp")})
    for L in (0.0, 0.2, 0.5, 1.0, 2.0, 5.0):
        g, n = r[f"gross_L{L}_H10"], r[f"net_L{L}_H10"]
        print(f"  L={L:>3}s H=10s gross {g['mean']:+.4f} [{g['lo']:+.4f},{g['hi']:+.4f}]  net {n['mean']:+.4f} [{n['lo']:+.4f},{n['hi']:+.4f}] pos {n['share_pos']}")
