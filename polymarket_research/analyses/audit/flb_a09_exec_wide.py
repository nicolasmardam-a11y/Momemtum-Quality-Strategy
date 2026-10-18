"""AUDIT flb (auditor 2026-10-18): executability of E2 / H99_6h fills in ALL trade markets (not only the panel tape set),
using taker tapes pulled by flb_a05_pull_trades.py plus the panel tapes.

For each rule trade (decision time h, favourite side price m from the series, modelled fill f = m + bucket half-spread):
  (a) first taker BUY of the favourite token in (h, h+2h] and (h, h+24h]: price minus m, minus f; net return if filled there;
  (b) effective half-spread at those prints vs the series value at print time (spread at the print, for THIS market);
  (c) share of trades with no favourite buy within 24h (cannot be verified; thin book).
Splits by 'grid' (m on a 0.5c grid, typical of a mid between 1c-tick quotes) and by decision-time staleness (no change in 24h).
Output: analyses/audit/out/flb_a09.json, flb_a09_trades.parquet
"""
from pathlib import Path
import sys, importlib, glob, json
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent)); A = importlib.import_module('flb_a01_recompute')
DER = A.DER


def series_lookup():
    """token-0 series per market: W = 5-min change points; P = m1 then h60. Returns dict cid -> (t, p)."""
    cp = pd.concat([pd.read_parquet(f, columns=['condition_id', 't', 'p']) for f in sorted(glob.glob(str(DER / 'flb_wide_parts/cp_*.parquet')))])
    out = {k: (v.t.values, v.p.values.astype(float)) for k, v in cp.sort_values(['condition_id', 't']).groupby('condition_id')}
    return out


def main():
    E = pd.read_parquet(DER / 'flb_entries.parquet')
    S = A.sides(E); S = A.add_R(S, 'med', 1.0, ''); S = A.add_R(S, 'mean', 1.0, '_mean')
    rows = []
    for rule, splits in (('E2', ('test', 'validation')), ('H99_6h', ('test',))):
        hz, lo, hi = A.RULES[rule]
        T = S[(S.horizon == hz) & (S.m >= lo - 1e-9) & (S.f <= 0.999) & S.split.isin(splits)].copy(); T['rule'] = rule
        rows.append(T)
    T = pd.concat(rows, ignore_index=True)
    T['grid'] = np.isclose((T.m * 1000) % 5, 0) | np.isclose((T.m * 1000) % 5, 5)
    T['stale24'] = T.n_chg_24h.fillna(0) == 0
    cols = ['condition_id', 'outcome_index', 'side', 'price', 'size', 'timestamp']
    tp = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(DER / 'audit_flb_trades/part_*.parquet')))] +
                   [pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(DER / 'tapes/tape_*.parquet')))])
    tp = tp[tp.condition_id.isin(set(T.condition_id))].dropna(subset=['timestamp'])
    tp = tp.astype({'price': float, 'size': float, 'timestamp': np.int64, 'outcome_index': np.int64})
    tp = tp.drop_duplicates().sort_values(['condition_id', 'timestamp'])
    G = {k: v for k, v in tp.groupby('condition_id')}
    pulled = pd.concat([pd.read_parquet(f) for f in glob.glob(str(DER / 'audit_flb_trades/pulled_*.parquet'))])
    trunc = set(pulled[pulled.truncated].condition_id)
    SER = series_lookup()
    recs = []
    for r in T.itertuples():
        h = int(pd.Timestamp(r.h_ts).timestamp())
        rec = dict(rule=r.rule, sample=r.sample, split=r.split, condition_id=r.condition_id, m=r.m, f=r.f, f_mean=r.f_mean, pay=r.pay,
                   w=r.weight, rate=r.rate, grid=r.grid, stale24=r.stale24, category=r.category, truncated=r.condition_id in trunc)
        x = G.get(r.condition_id)
        if x is not None:
            ts = x.timestamp.values; pr = x.price.values
            fav_buy = (x.outcome_index.values == r.side) & (x.side.values == 'BUY')
            rec['n_prints_total'] = len(x); rec['first_print_ts'] = int(ts.min()); rec['last_print_ts'] = int(ts.max())
            for lab, win in (('2h', 7200), ('24h', 86400)):
                b = np.where(fav_buy & (ts > h) & (ts <= h + win))[0]
                rec[f'n_buy_{lab}'] = len(b)
                if len(b):
                    rec[f'p_buy_{lab}'] = float(pr[b[0]]); rec[f'dt_buy_{lab}'] = int(ts[b[0]] - h)
                    rec[f'p_buymin_{lab}'] = float(pr[b].min())
            # effective half-spread at favourite-buy prints in (h-24h, h+24h], vs the W series value at print time
            if r.sample == 'W' and r.condition_id in SER:
                st, sp = SER[r.condition_id]
                b = np.where(fav_buy & (ts > h - 86400) & (ts <= h + 86400))[0]
                if len(b):
                    j = np.searchsorted(st, ts[b], side='right') - 1
                    ok = j >= 0
                    mid = np.where(r.side == 0, sp[np.maximum(j, 0)], 1 - sp[np.maximum(j, 0)])
                    eh = (pr[b] - mid)[ok]
                    if len(eh):
                        rec['eff_half_med_at_prints'] = float(np.median(eh)); rec['n_eff'] = int(len(eh))
        recs.append(rec)
    D = pd.DataFrame(recs)
    D.to_parquet(A.OUT / 'flb_a09_trades.parquet', index=False)
    res = {}

    def summ(d):
        r = dict(n=len(d), losses=int((d.pay == 0).sum()), with_tape=int(d.n_prints_total.notna().sum()) if 'n_prints_total' in d else 0)
        w = d.w.values
        r['net_model'] = round(float(np.average(d.pay / (d.f + d.rate * d.f * (1 - d.f)) - 1, weights=w)), 5)
        for lab in ('2h', '24h'):
            c = f'p_buy_{lab}'
            k = d[d[c].notna()] if c in d else d.iloc[:0]
            r[f'share_buy_{lab}'] = round(len(k) / max(len(d), 1), 3)
            if len(k):
                pb = k[c].values; wk = k.w.values
                r[f'mean_buy_minus_m_{lab}'] = round(float((pb - k.m).mean()), 5)
                r[f'med_buy_minus_m_{lab}'] = round(float(np.median(pb - k.m)), 5)
                r[f'mean_buy_minus_f_{lab}'] = round(float((pb - k.f).mean()), 5)
                r[f'net_at_buy_{lab}'] = round(float(np.average(k.pay / (pb + k.rate * pb * (1 - pb)) - 1, weights=wk)), 5)
                r[f'net_model_same_{lab}'] = round(float(np.average(k.pay / (k.f + k.rate * k.f * (1 - k.f)) - 1, weights=wk)), 5)
                r[f'net_at_buy_{lab}_unw'] = round(float((k.pay / (pb + k.rate * pb * (1 - pb)) - 1).mean()), 5)
                r[f'losses_with_buy_{lab}'] = int((k.pay == 0).sum())
        if 'eff_half_med_at_prints' in d:
            e = d.eff_half_med_at_prints.dropna()
            if len(e):
                r['eff_half_at_prints_median_over_trades'] = round(float(e.median()), 5)
                r['eff_half_at_prints_mean_over_trades'] = round(float(e.mean()), 5)
                r['model_half_mean_same'] = round(float((d.f - d.m)[d.eff_half_med_at_prints.notna()].mean()), 5)
        return r

    for (rule, samp, split), d in D.groupby(['rule', 'sample', 'split']):
        res[f'{rule}|{samp}|{split}'] = summ(d)
        for key in ('grid', 'stale24'):
            for v, dd in d.groupby(key):
                res[f'{rule}|{samp}|{split}|{key}={v}'] = summ(dd)
    res['n_truncated_tapes'] = int(D.truncated.sum())
    (A.OUT / 'flb_a09.json').write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        if '|test' in k and ('stale' not in k):
            print(k, v)


if __name__ == '__main__':
    main()
