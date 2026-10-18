"""AUDIT flb (auditor 2026-10-18): rare-loss model for E2 and H99_6h.
Losses are modelled as Poisson with mean k * sum(1 - m_i) (k = realised / price-implied loss rate; k = 1 means calibrated, k < 1 means
the favourite is underpriced, i.e. FLB). Jeffreys-type Gamma(0.5) prior; posterior Gamma(0.5 + losses, implied).
Break-even k* solves sum w_i [ (1 - k (1 - m_i)) / c_i - 1 ] = 0 over the TEST trades (c_i = fill + current fee, primary cost).
Reports P(k < k*) = posterior probability that the TEST portfolio has positive expected net return, by data pool.
Unweighted counts (each trade one Bernoulli). Also: same for the median-vs-mean half-spread cost variants.
"""
from pathlib import Path
import sys, importlib, json
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, str(Path(__file__).parent)); A = importlib.import_module('flb_a01_recompute')
E = pd.read_parquet(A.DER / 'flb_entries.parquet')
S = A.sides(E); S = A.add_R(S, 'med', 1.0, ''); S = A.add_R(S, 'mean', 1.0, '_mean')
out = {}
for rule in ('E2', 'H99_6h'):
    hz, lo, hi = A.RULES[rule]
    R = S[(S.horizon == hz) & (S.m >= lo - 1e-9) & (S.f <= 0.999) & (S.pay != 0.5)]
    for samp in ('P', 'W'):
        T = R[(R['sample'] == samp) & (R.split == 'test')]
        w = T.weight.values; m = T.m.values
        for ctag in ('', '_mean'):
            f = T['f' + ctag].values; c = f + T.rate.values * f * (1 - f)
            g = lambda k: np.sum(w * ((1 - k * (1 - m)) / c - 1))
            lo_k, hi_k = 0.0, 5.0
            for _ in range(80):
                mid = (lo_k + hi_k) / 2
                lo_k, hi_k = (mid, hi_k) if g(mid) > 0 else (lo_k, mid)
            kstar = (lo_k + hi_k) / 2
            for pool_name, pool in (('test_same_sample', R[(R['sample'] == samp) & (R.split == 'test')]),
                                    ('all_splits_same_sample', R[R['sample'] == samp]),
                                    ('all_splits_both_samples', R),
                                    ('train_val_both_samples', R[R.split != 'test'])):
                L = int((pool.pay == 0).sum()); I = float((1 - pool.m).sum())
                post = stats.gamma(a=0.5 + L, scale=1 / I)
                out[f'{rule}|{samp}{ctag}|{pool_name}'] = dict(kstar=round(kstar, 3), losses=L, implied=round(I, 2), k_hat=round(L / I, 3),
                    k_ci95=[round(post.ppf(.025), 3), round(post.ppf(.975), 3)], P_edge_pos=round(float(post.cdf(kstar)), 3))
for k, v in out.items():
    print(k, v)
json.dump(out, open(A.OUT / 'flb_a08.json', 'w'), indent=1)

# ---- model-based expected net return of the TEST portfolio at the pooled calibration ratio k (all splits, both samples)
R0 = S[(S.horizon == 'A-7d') & (S.m >= 0.95 - 1e-9) & (S.f <= 0.999) & (S.pay != 0.5)]
L = int((R0.pay == 0).sum()); I = float((1 - R0.m).sum()); post = stats.gamma(a=0.5 + L, scale=1 / I)
ks = {'k_hat': L / I, 'k_lo95': post.ppf(.025), 'k_hi95': post.ppf(.975)}
for samp in ('P', 'W'):
    T = R0[(R0['sample'] == samp) & (R0.split == 'test')]
    for ctag in ('', '_mean'):
        f = T['f' + ctag].values; c = f + T.rate.values * f * (1 - f); w = T.weight.values; m = T.m.values
        er = {kk: round(float(np.sum(w * ((1 - kv * (1 - m)) / c - 1)) / w.sum()), 5) for kk, kv in ks.items()}
        eru = {kk: round(float(np.mean((1 - kv * (1 - m)) / c - 1)), 5) for kk, kv in ks.items()}
        out[f'E2_model_ER|{samp}{ctag}'] = dict(weighted=er, unweighted=eru, k=dict((a, round(b, 3)) for a, b in ks.items()))
        print(f'E2 model E[R] {samp}{ctag}', er, 'unw', eru)
json.dump(out, open(A.OUT / 'flb_a08.json', 'w'), indent=1)
