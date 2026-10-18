"""AUDIT flb: E2 / H99_6h sensitivity to (i) excluding soccer exact-score markets, (ii) excluding sports, (iii) one extra loss at the
highest-weight trade, (iv) equal weights. TEST, primary cost. Output printed + analyses/audit/out/flb_a10.json"""
from pathlib import Path
import sys, importlib, json
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent)); A = importlib.import_module('flb_a01_recompute')
E = pd.read_parquet(A.DER / 'flb_entries.parquet')
S = A.sides(E); S = A.add_R(S, 'med', 1.0, '')
out = {}
for rule in ('E2', 'H99_6h'):
    hz, lo, hi = A.RULES[rule]
    for samp in ('P', 'W'):
        for split in ('test', 'validation', 'train'):
            T = S[(S['sample'] == samp) & (S.split == split) & (S.horizon == hz) & (S.m >= lo - 1e-9) & (S.f <= 0.999)]
            if not len(T):
                continue
            wm = lambda d: round(float(np.average(d.R, weights=d.weight)), 5) if len(d) else None
            es = T.sportsMarketType.fillna('').str.contains('exact_score')
            r = dict(n=len(T), all=wm(T), n_exact=int(es.sum()), ex_exact_score=wm(T[~es]), ex_sports=wm(T[T.category != 'sports']),
                     exact_only=wm(T[es]), unweighted=round(float(T.R.mean()), 5))
            # one extra loss: the highest-weight winner becomes a loss
            T2 = T.copy(); i = T2[T2.pay == 1].weight.idxmax(); T2.loc[i, 'R'] = -1.0
            r['one_extra_loss_at_max_weight'] = wm(T2)
            if split == 'test':
                d = T[~es]
                r['ci_ex_exact_cluster'] = A.boot(d.R.values, d.weight.values.astype(float), d.cluster_id.values)
            out[f'{rule}|{samp}|{split}'] = r
            print(rule, samp, split, r)
json.dump(out, open(A.OUT / 'flb_a10.json', 'w'), indent=1)
