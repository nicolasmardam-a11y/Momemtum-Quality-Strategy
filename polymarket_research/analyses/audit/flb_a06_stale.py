"""AUDIT flb: does the E2 / H99_6h edge sit in stale or round-number display prices (wide-spread mid artefacts)?
Splits each rule's TEST trades by decision-time activity (n_chg_24h == 0 vs > 0; last_change_age) and by whether m sits on a
0.5c grid (typical of a mid of two 1c-tick quotes, i.e. a >= 1c spread). Weighted net (primary cost) and unweighted."""
from pathlib import Path
import sys, importlib, json
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent)); A = importlib.import_module('flb_a01_recompute')
E = pd.read_parquet(A.DER / 'flb_entries.parquet')
S = A.sides(E); S = A.add_R(S, 'med', 1.0, '')
# (n_chg_24h, last_change_age_s already carried by sides())
S['grid_half_cent'] = np.isclose((S.m * 1000) % 5, 0) | np.isclose((S.m * 1000) % 5, 5)
S['stale24'] = S.n_chg_24h.fillna(0) == 0
S['m_dec'] = ((S.m * 10000).round() % 10 != 0)  # sub-0.1c price => 0.001 tick book (spread can be <= 0.1c)
out = {}
for rule in ('E2', 'H99_6h', 'H98_6h', 'H95_24h'):
    hz, lo, hi = A.RULES[rule]
    for samp in ('P', 'W'):
        for split in ('test', 'validation'):
            T = S[(S['sample'] == samp) & (S.split == split) & (S.horizon == hz) & (S.m >= lo - 1e-9) & (S.f <= 0.999)]
            for key in ('stale24', 'grid_half_cent'):
                for v, d in T.groupby(key):
                    w = d.weight.values
                    out[f'{rule}|{samp}|{split}|{key}={v}'] = dict(n=len(d), losses=int((d.pay == 0).sum()), m=round(float(np.average(d.m, weights=w)), 4),
                        net=round(float(np.average(d.R, weights=w)), 4), net_unw=round(float(d.R.mean()), 4), share=round(len(d) / len(T), 3))
for k, v in out.items():
    if '|test|' in k or k.startswith('E2|W|validation'):
        print(k, v)
json.dump(out, open(A.OUT / 'flb_a06.json', 'w'), indent=1)
