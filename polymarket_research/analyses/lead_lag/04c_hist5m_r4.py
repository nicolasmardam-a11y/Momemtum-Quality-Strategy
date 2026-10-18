"""R4 (pre-registered, section 0.1) applied to the 5-minute extension panel (02c_hist_5m.py), same formula as 04b_hist_r4_paper.py:
predictable move = lag coefficient (60-120 s) x |fair change 60-120 s before| vs hurdle = half the 1-c live spread + 0.07 p(1-p).
Also the same NON-EXECUTABLE paper test (first signal per market, hold to resolution; an upper bound because the series is stale).
Run: python -m analyses.lead_lag.04c_hist5m_r4 -> data/derived/lead_lag/hist5m_r4_paper.json
"""
import json

import numpy as np
import pandas as pd

D = "data/derived/lead_lag/"
Q = pd.read_parquet(D + "hist5m_panel.parquet").sort_values(["slug", "t"])
S = json.load(open(D + "hist5m_summary.json"))["5m"]
HALF = 0.005
rng = np.random.default_rng(3)
lagc = S["response"]["coef"]["d_60_120"]
d = (Q.f60 - Q.f120).abs()
pred = lagc * d
hurdle = HALF + 0.07 * Q.pm * (1 - Q.pm)
r = {"lag_coef": lagc, "n": int(d.notna().sum()), "median_abs_dfair_60_120": float(d.median()), "median_pred_move": float(pred.median()),
     "median_hurdle": float(hurdle.median()), "share_pred_gt_hurdle": float((pred > hurdle).mean())}
x = Q[(Q.tau >= 60) & Q.pm.between(0.02, 0.98)]
gap = x.f0 - x.pm
buy_up = gap > 0
ent = np.where(buy_up, x.pm + HALF, 1 - x.pm + HALF)
fee = 0.07 * ent * (1 - ent)
sel = (np.abs(gap) - HALF - fee) >= 0.02
pnl = np.where(buy_up, x.y, 1 - x.y) - ent - fee
z = pd.DataFrame({"slug": x.slug.values, "t": x.t.values, "pnl": pnl, "sel": sel.values})
first = z[z.sel].groupby("slug").head(1)
mk = first.slug.unique()
by = {s: first.pnl.values[first.slug.values == s] for s in mk}
ms = [np.concatenate([by[s] for s in rng.choice(mk, len(mk))]).mean() for _ in range(2000)]
r["paper_first_per_market"] = {"n": int(len(first)), "mean": float(first.pnl.mean()), "ci": [float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))]}
json.dump(r, open(D + "hist5m_r4_paper.json", "w"), indent=1)
print(json.dumps(r))
