"""Probe CLOB /prices-history semantics (fidelity, timestamp alignment, gaps) and /v2/trades tape size.

Run: python analyses/panel/00_probe.py   (writes analyses/panel/out/00_probe.json)
"""
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pmr import api

OUT = Path(__file__).resolve().parent / "out"; OUT.mkdir(exist_ok=True)
cols = ['condition_id','token_id_0','volumeNum','split','category','endDate','closedTime','createdAt','startDate','question']
m = pd.read_parquet('data/derived/markets_resolved.parquet', columns=cols, filters=[('volumeNum', '>=', 2e4), ('volumeNum', '<=', 1e5)])
rng = np.random.default_rng(0)
picks = []
for (sp, cat), g in m.groupby(['split', 'category']):
    if cat in ('politics', 'sports', 'crypto') and len(g):
        picks.append(g.iloc[rng.integers(len(g))])
res = []
for r in picks:
    ref = int(min(r.endDate, r.closedTime).timestamp())
    h60 = api.prices_history(r.token_id_0, ref - 14 * 86400, ref, 60)
    h1 = api.prices_history(r.token_id_0, ref - 72 * 3600, ref, 1)
    tr = api.trades(condition=r.condition_id, cache=True, limit=1000)
    t60 = np.array([x['t'] for x in h60]); t1 = np.array([x['t'] for x in h1])
    d = dict(split=r.split, cat=r.category, vol=r.volumeNum, q=r.question[:60], n60=len(h60), n1=len(h1),
             n_tr=len(tr), dt60=np.unique(np.diff(t60)).tolist()[:5] if len(t60) > 1 else None,
             dt1_med=float(np.median(np.diff(t1))) if len(t1) > 1 else None,
             t60_mod3600=np.unique(t60 % 3600).tolist()[:5] if len(t60) else None,
             t1_mod60=np.unique(t1 % 60).tolist()[:5] if len(t1) else None,
             first60=int(t60[0]) - (ref - 14 * 86400) if len(t60) else None,
             last60=ref - int(t60[-1]) if len(t60) else None, last1=ref - int(t1[-1]) if len(t1) else None)
    # alignment: for fid1 points, compare p to last trade (token 0) strictly before t, and to last trade at/before t+60
    if len(h1) and tr:
        T = pd.DataFrame(tr); T = T[T.token_id == r.token_id_0].sort_values('timestamp')
        if len(T) > 5:
            ts = T.timestamp.values; px = T.price.astype(float).values
            P = pd.DataFrame(h1)
            def lastpx(tt):
                i = np.searchsorted(ts, tt, side='right') - 1
                return np.where(i >= 0, px[np.clip(i, 0, None)], np.nan)
            for lag in (-60, 0, 60):
                d[f'mad_lag{lag}'] = float(np.nanmedian(np.abs(P.p.values - lastpx(P.t.values + lag))))
                d[f'eq_lag{lag}'] = float(np.nanmean(np.abs(P.p.values - lastpx(P.t.values + lag)) < 1e-9))
    res.append(d); print(d, flush=True)
json.dump(res, open(OUT / '00_probe.json', 'w'), indent=1, default=str)
