"""Historical recurrence proxy for k-of-n count sets (nomination-style events).

For past non-neg-risk events made of separate "Will X be nominated?" markets, sum the
hourly CLOB /prices-history YES prices across the event's markets and compare with k,
the number of slots. Prices are trade/mid series, NOT executable: an all-NO basket profits
roughly when sum_yes - k exceeds the per-leg half-spreads plus fees. The live 2026-10-17
Best Actor snapshot (19 legs) had mid-sum 5.92 vs best-bid-sum 5.68 and fees ~0.125/set,
so we use an approximate break-even of 0.02 per leg (0.38 for 19 legs). Caps (k) are the
official nominee counts as known to the author; they are ASSUMED unless noted and are
sanity-checked against the realised number of Yes resolutions (yes <= k).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pmr import api  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CAPS = {  # event_id: (k, cap source)
    50248: (10, "Oscars Best Picture: 10 nominees (Rule Five, verified on oscars.org 2026-10-18 for the 99th rules)"),
    50281: (5, "Oscars acting categories: 5 (Rule Five §6, verified)"),
    50297: (5, "Oscars acting: 5 (verified)"),
    50289: (5, "Oscars acting: 5 (verified)"),
    50302: (5, "Oscars acting: 5 (verified)"),
    50385: (5, "Oscars Director: 5 (verified)"),
    50398: (5, "Oscars Documentary Feature: 5 (Rule Five §6, verified)"),
    50408: (5, "Oscars Casting: 5 (assumed)"),
    160498: (5, "Oscars International Feature: 5 (verified)"),
    50407: (5, "Oscars Animated Feature: 5 (verified)"),
    15290: (10, "Oscars Best Picture (2025 ceremony): 10 (assumed)"),
    56670: (8, "Grammys general field: 8 (assumed)"),
    56673: (8, "Grammys general field: 8 (assumed)"),
    56674: (8, "Grammys general field: 8 (assumed)"),
    56677: (8, "Grammys general field: 8 (assumed)"),
    57142: (6, "Golden Globes: 6 nominees per category (assumed)"),
    5828: (1, "Party nominee: 1"),
    5853: (1, "Party nominee: 1"),
}
ACTOR_AWARDS = [112242, 112259, 112213, 112243, 112264, 112160, 112253, 112258, 112170, 112093, 102609, 112180,
                102612, 112155]  # Actor Awards (SAG): 5 nominees per category (assumed)
for e in ACTOR_AWARDS:
    CAPS[e] = (5, "Actor Awards: 5 nominees per category (assumed)")

cols = ["condition_id", "question", "event_id", "event_title", "endDate", "closedTime", "negRisk", "winner_idx",
        "token_id_0", "outcomes", "volumeNum"]
m = pd.read_parquet(ROOT / "data/derived/markets_resolved.parquet", columns=cols,
                    filters=[("event_id", "in", [str(e) for e in CAPS])])
m["event_id"] = m["event_id"].astype(int)
m = m[m["event_id"].isin(CAPS)]
m = m[~m["negRisk"].fillna(False).astype(bool)]
rows = []
for eid, g in m.groupby("event_id"):
    k, src = CAPS[eid]
    first = g["outcomes"].map(lambda o: (api.jlist(o) if isinstance(o, str) else list(o))[0] if o is not None and len(o) else None)
    g = g[first == "Yes"]
    n = len(g)
    if n == 0:
        print(f"event {eid}: no Yes/No markets, skipped", file=sys.stderr)
        continue
    yes = int((g["winner_idx"] == 0).sum())
    t_res = pd.to_datetime(g["closedTime"], utc=True, format="mixed").min()
    if pd.isna(t_res):
        t_res = pd.to_datetime(g["endDate"], utc=True, format="mixed").min()
    print(f"event {eid} n={n} k={k} t_res={t_res}", file=sys.stderr, flush=True)
    end_ts = int(t_res.timestamp())
    start_ts = end_ts - 60 * 86400
    series = {}
    for _, r in g.iterrows():
        h = []
        for a in range(start_ts, end_ts, 14 * 86400):  # the endpoint rejects long intervals
            h += api.prices_history(r["token_id_0"], a, min(a + 14 * 86400, end_ts), fidelity_min=60)
        if h:
            s = pd.Series({pd.Timestamp(x["t"], unit="s", tz="UTC").floor("h"): float(x["p"]) for x in h})
            series[r["condition_id"]] = s[~s.index.duplicated(keep="last")]
    if len(series) < n:
        print(f"event {eid}: {n - len(series)} of {n} markets have no history", file=sys.stderr)
    df = pd.DataFrame(series).sort_index().ffill()
    df = df.dropna()  # hours where every listed market has a price
    if df.empty:
        continue
    df = df[df.index < t_res - pd.Timedelta(hours=1)]  # drop the final hour (announcement leaks)
    s = df.sum(axis=1)
    excess = s - k
    be = 0.02 * len(series)
    proxy_profit = excess - be  # per set, rough
    hours = len(s)
    rows.append({
        "event_id": eid, "event": g["event_title"].iloc[0], "n_listed": n, "n_priced": len(series), "k": k,
        "yes_realised": yes, "hours_all_listed": hours, "first_all_listed": s.index.min(), "resolved": t_res,
        "median_sum_yes": round(float(s.median()), 3), "max_sum_yes": round(float(s.max()), 3),
        "share_hours_sum_gt_k": round(float((excess > 0).mean()), 3),
        "share_hours_proxy_profitable": round(float((proxy_profit > 0).mean()), 3),
        "median_proxy_profit_per_set": round(float(proxy_profit.median()), 3),
        "median_proxy_return": round(float((proxy_profit / (len(series) - s)).median()), 4),
        "volume_usd": round(float(g["volumeNum"].fillna(0).sum())), "cap_source": src,
    })
out = pd.DataFrame(rows).sort_values("resolved")
out.to_csv(ROOT / "analyses/logical_arb/out_10_count_set_history.csv", index=False)
pd.set_option("display.width", 250)
print(out.drop(columns=["cap_source"]).to_string(index=False))
