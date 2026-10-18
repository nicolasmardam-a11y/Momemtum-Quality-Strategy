"""AUDIT flb: robust summary of flb_a09_trades.parquet. A first favourite-BUY print more than 5c from the series price m is treated as
non-comparable (odd prints / the market moved) and excluded, with the share reported. Output analyses/audit/out/flb_a11.json"""
from pathlib import Path
import json
import numpy as np, pandas as pd
OUT = Path(__file__).parent / 'out'
D = pd.read_parquet(OUT / 'flb_a09_trades.parquet')
res = {}
for lab in ('2h', '24h'):
    for keys in (['rule', 'sample', 'split'], ['rule', 'sample', 'split', 'grid']):
        for k, d in D.groupby(keys):
            c = f'p_buy_{lab}'
            have = d[d[c].notna()]
            ok = have[(have[c] - have.m).abs() <= 0.05]
            r = dict(n=len(d), share_with_buy=round(len(have) / len(d), 3), share_noncomparable=round(1 - len(ok) / max(len(have), 1), 3))
            if len(ok):
                pb = ok[c].values; w = ok.w.values
                Rb = ok.pay / (pb + ok.rate * pb * (1 - pb)) - 1; Rm = ok.pay / (ok.f + ok.rate * ok.f * (1 - ok.f)) - 1
                Rmm = ok.pay / (ok.f_mean + ok.rate * ok.f_mean * (1 - ok.f_mean)) - 1
                r.update(med_buy_minus_m=round(float(np.median(pb - ok.m)), 5), mean_buy_minus_m=round(float((pb - ok.m).mean()), 5),
                         mean_model_half=round(float((ok.f - ok.m).mean()), 5), mean_buy_minus_f=round(float((pb - ok.f).mean()), 5),
                         net_at_buy_w=round(float(np.average(Rb, weights=w)), 5), net_model_w=round(float(np.average(Rm, weights=w)), 5),
                         net_model_meanhs_w=round(float(np.average(Rmm, weights=w)), 5),
                         net_at_buy_unw=round(float(Rb.mean()), 5), net_model_unw=round(float(Rm.mean()), 5), losses=int((ok.pay == 0).sum()))
            res[lab + '|' + '|'.join(map(str, k))] = r
json.dump(res, open(OUT / 'flb_a11.json', 'w'), indent=1)
for k, v in res.items():
    if ('test' in k or 'E2|W|validation' in k) and k.count('|') == 3:
        print(k, v)
