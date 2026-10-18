"""AUDIT flb: weight concentration, per-category contributions, Kish effective n, and losses for E2 / H99_6h (TEST)."""
from pathlib import Path
import sys, importlib
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent)); A = importlib.import_module('flb_a01_recompute')
E = pd.read_parquet(A.DER / 'flb_entries.parquet')
S = A.sides(E); S = A.add_R(S, 'med', 1.0, '')
S = S.merge(E[['condition_id', 'horizon', 'question', 'n_chg_24h', 'last_change_age_s']].drop_duplicates(['condition_id', 'horizon']), on=['condition_id', 'horizon'], suffixes=('', '_e'))
for rule in ('E2', 'H99_6h'):
    hz, lo, hi = A.RULES[rule]
    for samp in ('P', 'W'):
        T = S[(S['sample'] == samp) & (S.split == 'test') & (S.horizon == hz) & (S.m >= lo - 1e-9) & (S.f <= 0.999)]
        w = T.weight.values; kish = w.sum() ** 2 / (w ** 2).sum()
        g = T.assign(wR=T.weight * T.R).groupby('category').agg(n=('R', 'size'), w=('weight', 'sum'), losses=('pay', lambda p: int((p == 0).sum())),
                                                                 net=('wR', 'sum'))
        g['w_share'] = (g.w / g.w.sum()).round(3); g['net'] = (g.net / g.w).round(4)
        print(f'== {rule} {samp} TEST n={len(T)} Kish n_eff={kish:.0f}  weighted net={np.sum(w*T.R)/w.sum():.4f}')
        print(g.sort_values('w_share', ascending=False)[['n', 'w_share', 'losses', 'net']].to_string())
        L = T[T.pay < 1][['category', 'm', 'f', 'pay', 'weight', 'question', 'n_chg_24h', 'last_change_age_s']]
        L['question'] = L.question.str[:70]
        print(L.to_string())
