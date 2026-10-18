"""R4 check and a NON-EXECUTABLE paper test on the historical primary panel (hist_panel_primary.parquet).
R4: predictable move implied by the lagged (60-120 s) fair-change coefficient vs half the median live spread + taker fee.
Paper test (upper bound, NOT executable: the prices-history value is stale by ~15 s, see response coefficients):
  at each sample t with tau >= 120 s, gap = fair - pm. If |gap| - fee(entry) - half_spread >= 0.02 buy the cheap side at
  pm(+/-)half_spread, hold to resolution. Fit nothing; this is the pre-registered H2 threshold applied to the history.
Run: python -m analyses.lead_lag.04b_hist_r4_paper  -> data/derived/lead_lag/hist_r4_paper.json
"""
import json
import numpy as np
import pandas as pd
D = "data/derived/lead_lag/"
Q = pd.read_parquet(D + "hist_panel_primary.parquet").sort_values(["slug", "t"])
S = json.load(open(D + "hist_summary.json"))["PRIMARY_at_pm_timestamps_binance1s"]
HALF = 0.005   # half of the 1-cent median live spread on 15m/1h up/down books (live_L2 summary)
rng = np.random.default_rng(3)
out = {}
for k, x in Q.groupby("kind"):
    x = x.copy()
    lagc = S[k]["response"]["coef"]["d_60_120"]
    d = (x.f60 - x.f120).abs()
    pred = lagc * d
    hurdle = HALF + 0.07 * x.pm * (1 - x.pm)
    r = {"lag_coef": lagc, "median_abs_dfair_60_120": float(d.median()), "median_pred_move": float(pred.median()),
         "median_hurdle": float(hurdle.median()), "share_pred_gt_hurdle": float((pred > hurdle).mean())}
    x = x[(x.tau >= 120) & x.pm.between(0.02, 0.98)]
    gap = x.f0 - x.pm
    buy_up = gap > 0
    ent = np.where(buy_up, x.pm + HALF, 1 - x.pm + HALF)
    fee = 0.07 * ent * (1 - ent)
    edge = np.abs(gap) - HALF - fee
    sel = edge >= 0.02
    pay = np.where(buy_up, x.y, 1 - x.y)
    pnl = pay - ent - fee
    z = pd.DataFrame({"slug": x.slug.values, "t": x.t.values, "pnl": pnl, "sel": sel.values})
    z = z[z.sel]
    # one trade per market (first signal), to count distinct events and avoid pyramiding
    first = z.groupby("slug").head(1)
    def boot(v, g):
        mk = g.unique(); by = {s: v[g == s] for s in mk}; ms = []
        for _ in range(2000):
            pick = rng.choice(mk, len(mk)); ms.append(np.concatenate([by[s] for s in pick]).mean())
        return [float(np.mean(v)), float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))]
    r["paper_all_signals"] = {"n": int(len(z)), "markets": int(z.slug.nunique()), "mean_ci": boot(z.pnl.values, z.slug.values) if len(z) else None}
    r["paper_first_per_market"] = {"n": int(len(first)), "mean_ci": boot(first.pnl.values, first.slug.values) if len(first) else None,
                                   "hit_rate": float((first.pnl > 0).mean()) if len(first) else None}
    # time split: first 4 days vs last 3 days
    cut = Q.t.min() + 4 * 86400
    for lab, ff in (("first4d", first[first.t < cut]), ("last3d", first[first.t >= cut])):
        r[f"paper_first_{lab}"] = {"n": int(len(ff)), "mean": float(ff.pnl.mean()) if len(ff) else None}
    out[k] = r
json.dump(out, open(D + "hist_r4_paper.json", "w"), indent=1)
print(json.dumps(out, indent=1))
