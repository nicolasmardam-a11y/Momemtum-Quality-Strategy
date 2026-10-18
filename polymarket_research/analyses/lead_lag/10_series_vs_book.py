"""Direct check of the section-2 caveat: is CLOB /prices-history (fidelity=1) a delayed copy of the live book mid?
For the up/down markets in a live window, fetch /prices-history for the Up token and compare each point (t, p) with the live
best-bid/ask mid (live_<tag>_NN_tob.parquet, local receive time) at t - lag for lag = 0..90 s. Report the lag that minimises
the median |p - mid(t - lag)|, overall and by kind. Read-only. Descriptive (not a pre-registered test).
Run: python -m analyses.lead_lag.10_series_vs_book L4 -> data/derived/lead_lag/series_vs_book_<tag>.json
"""
import glob
import json
import sys

import numpy as np
import pandas as pd

from pmr import api

TAG = sys.argv[1] if len(sys.argv) > 1 else "L4"
D = "data/derived/lead_lag/"
LAGS = np.arange(0, 91, 1.0)

md = pd.read_parquet(f"{D}live_{TAG}_meta.parquet")
md = md[md.kind.isin(["5m", "15m", "1h", "4h"])]
tob = pd.concat([pd.read_parquet(f, columns=["recv", "asset", "bid", "ask"]) for f in sorted(glob.glob(f"{D}live_{TAG}_[0-9][0-9]_tob.parquet"))])
tob = tob[tob.bid.notna() & tob.ask.notna() & (tob.ask - tob.bid <= 0.03)].sort_values("recv")
t_lo, t_hi = tob.recv.min(), tob.recv.max()
rows = []
for m in md.itertuples():
    q = tob[tob.asset == m.tok0]
    if len(q) < 50:
        continue
    qt, qm = q.recv.values, ((q.bid + q.ask) / 2).values
    h = api.prices_history(m.tok0, int(max(m.start, t_lo)) - 120, int(min(m.end, t_hi)) + 60, 1, cache=False)
    for pt in h or []:
        t, p = float(pt["t"]), float(pt["p"])
        if t - 90 < t_lo + 5 or t > t_hi:
            continue
        idx = np.searchsorted(qt, t - LAGS, side="right") - 1
        if (idx < 0).any():
            continue
        err = np.abs(p - qm[idx])
        rows.append({"slug": m.slug, "kind": m.kind, "t": t, "p": p, **{f"e{int(L)}": float(e) for L, e in zip(LAGS, err)}})
R = pd.DataFrame(rows)
out = {"tag": TAG, "n_points": int(len(R)), "markets": int(R.slug.nunique()) if len(R) else 0,
       "t_mod_60_median": float((R.t % 60).median()) if len(R) else None}


def best(df):
    med = np.array([df[f"e{int(L)}"].median() for L in LAGS])
    mean = np.array([df[f"e{int(L)}"].mean() for L in LAGS])
    j = int(np.argmin(mean))
    return {"n": int(len(df)), "lag_min_mean_abs_err_s": float(LAGS[j]), "mean_abs_err_at_best": round(float(mean[j]), 4),
            "mean_abs_err_lag0": round(float(mean[0]), 4), "median_abs_err_lag0": round(float(med[0]), 4),
            "share_exact_lag0": round(float((df["e0"] < 0.0051).mean()), 3),
            "share_exact_best": round(float((df[f"e{int(LAGS[j])}"] < 0.0051).mean()), 3),
            "mean_abs_err_by_lag": {int(L): round(float(v), 4) for L, v in zip(LAGS, mean) if L in (0, 5, 10, 15, 20, 30, 45, 60, 90)}}


if len(R):
    out["all"] = best(R)
    out["by_kind"] = {k: best(g) for k, g in R.groupby("kind") if len(g) >= 20}
json.dump(out, open(f"{D}series_vs_book_{TAG}.json", "w"), indent=1)
print(json.dumps(out, indent=1)[:2500])
