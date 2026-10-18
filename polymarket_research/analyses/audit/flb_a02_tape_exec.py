"""AUDIT flb (auditor 2026-10-18): are the modelled fill prices executable? Check against the actual taker tapes.

For every P rule trade (all splits) whose market is in the /v2/trades tape set, find taker prints that reveal the favourite's ask
after the decision time h:
  - taker BUY of the favourite token at price p  (ask <= p at that moment)
  - taker SELL of the complement token at price q (favourite ask via mirrored book ~ 1 - q; reported separately)
Measures: first favourite-BUY print in (h, h+30m] and (h, h+2h]; its price minus the series price m and minus the modelled fill f;
return if filled at that print (current fee), vs modelled return on the same trades. Also "outcome-known" flags.
Output: analyses/audit/out/flb_a02.json
"""
from pathlib import Path
import glob, json, sys
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; DER = ROOT / 'data/derived'; OUT = Path(__file__).parent / 'out'
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
from pmr import fees
import importlib
A = importlib.import_module('flb_a01_recompute')


def main():
    E = pd.read_parquet(DER / 'flb_entries.parquet')
    E = E[(E['sample'] == 'P') & E.in_tape_set.astype(bool)]
    S = A.sides(E); S = A.add_R(S, 'med', 1.0, '')
    rows = []
    for rule, (hz, lo, hi) in A.RULES.items():
        T = S[(S.horizon == hz) & (S.m >= lo - 1e-9) & (S.m <= hi + 1e-9) & (S.f <= 0.999)].copy()
        T['rule'] = rule; rows.append(T)
    T = pd.concat(rows, ignore_index=True)
    cids = set(T.condition_id)
    tp = pd.concat([pd.read_parquet(f, columns=['condition_id', 'outcome_index', 'side', 'price', 'size', 'timestamp'])
                    for f in sorted(glob.glob(str(DER / 'tapes/tape_*.parquet')))])
    tp = tp[tp.condition_id.isin(cids)].astype({'price': float, 'size': float, 'timestamp': np.int64, 'outcome_index': np.int64})
    tp = tp.sort_values(['condition_id', 'timestamp']).reset_index(drop=True)
    g = {k: v for k, v in tp.groupby('condition_id')}
    cov = pd.read_parquet(DER / 'tapes/coverage.parquet').set_index('condition_id')
    out = []
    for r in T.itertuples():
        x = g.get(r.condition_id)
        h = int(pd.Timestamp(r.h_ts).timestamp())
        rec = dict(rule=r.rule, split=r.split, condition_id=r.condition_id, m=r.m, f=r.f, pay=r.pay, w=r.weight, rate=r.rate,
                   category=r.category, truncated=bool(cov.truncated.get(r.condition_id, False)))
        if x is None:
            out.append(rec); continue
        ts = x.timestamp.values
        fav_buy = (x.outcome_index.values == r.side) & (x.side.values == 'BUY')
        cmp_sell = (x.outcome_index.values != r.side) & (x.side.values == 'SELL')
        for lab, win in (('30m', 1800), ('2h', 7200)):
            sel = (ts > h) & (ts <= h + win)
            b = np.where(sel & fav_buy)[0]; s_ = np.where(sel & cmp_sell)[0]
            rec[f'n_buy_{lab}'] = len(b)
            if len(b):
                rec[f'p_first_buy_{lab}'] = float(x.price.values[b[0]])
                pv = x.price.values[b]; sz = x['size'].values[b]
                rec[f'p_vwap_buy_{lab}'] = float((pv * sz).sum() / sz.sum())
                rec[f'p_min_buy_{lab}'] = float(pv.min())
            if len(s_):
                rec[f'p_first_cmpsell_{lab}'] = float(1 - x.price.values[s_[0]])
        # any print of any kind in the 2h BEFORE h (activity at decision time)
        rec['n_prints_prev2h'] = int(((ts > h - 7200) & (ts <= h)).sum())
        # last favourite BUY print before h
        bb = np.where((ts <= h) & fav_buy)[0]
        if len(bb):
            rec['p_last_buy_before'] = float(x.price.values[bb[-1]]); rec['age_last_buy_before_s'] = int(h - ts[bb[-1]])
        out.append(rec)
    D = pd.DataFrame(out)
    D.to_parquet(OUT / 'flb_a02_tape_trades.parquet', index=False)
    res = {}
    for (rule, split), d in D.groupby(['rule', 'split']):
        r = dict(n=len(d), n_truncated=int(d.truncated.sum()))
        for lab in ('30m', '2h'):
            c = f'p_first_buy_{lab}'
            if c not in d:
                continue
            k = d[d[c].notna()]
            r[f'share_with_buy_{lab}'] = round(len(k) / len(d), 3)
            if len(k):
                r[f'med_first_buy_minus_m_{lab}'] = round(float((k[c] - k.m).median()), 5)
                r[f'mean_first_buy_minus_m_{lab}'] = round(float((k[c] - k.m).mean()), 5)
                r[f'mean_first_buy_minus_f_{lab}'] = round(float((k[c] - k.f).mean()), 5)
                r[f'share_first_buy_above_f_{lab}'] = round(float((k[c] > k.f + 1e-9).mean()), 3)
                fb = k[c].values; R_t = k.pay.values / (fb + k.rate.values * fb * (1 - fb)) - 1
                R_m = k.pay.values / (k.f.values + k.rate.values * k.f.values * (1 - k.f.values)) - 1
                w = k.w.values
                r[f'net_at_first_buy_{lab}_w'] = round(float((w * R_t).sum() / w.sum()), 5)
                r[f'net_model_same_trades_{lab}_w'] = round(float((w * R_m).sum() / w.sum()), 5)
                r[f'net_at_first_buy_{lab}_unw'] = round(float(R_t.mean()), 5)
                r[f'net_model_same_trades_{lab}_unw'] = round(float(R_m.mean()), 5)
                r[f'losses_with_buy_{lab}'] = int((k.pay == 0).sum())
        r['losses_all'] = int((d.pay == 0).sum())
        r['share_no_print_prev2h'] = round(float((d.n_prints_prev2h == 0).mean()), 3) if 'n_prints_prev2h' in d else None
        res[f'{rule}|{split}'] = r
    (OUT / 'flb_a02.json').write_text(json.dumps(res, indent=1))
    for k in ('E2|test', 'E2|validation', 'H99_6h|test', 'H99_1h|test', 'H98_6h|test', 'H95_6h|test', 'H90_24h|test', 'E1|test'):
        print(k, res.get(k))


if __name__ == '__main__':
    main()
