"""AUDIT lp_markouts (auditor 2026-10-18). Independent recomputation of the headline maker-P&L numbers from the per-trade
reference file (data/derived/lp_markouts/mk_*.parquet) with code written separately from 02_analyze.py, plus checks:
  a) TEST split is by market resolution date: how much TEST share volume was traded BEFORE 2026-01-01 (overlapping validation in
     calendar time)? Re-evaluate key cells on trade-time TEST (t >= 2026-01-01) only.
  b) 50-50 markets drop out of resolution metrics (winner unknown): count them.
  c) headline TEST share-weighted eff, markouts, realised spreads (M and R), resolution P&L, current-era rs and rebate,
     with event and week cluster bootstraps (1,000 reps).
  d) the surviving >98c cell and TTR<=1h cell in the current era, on trade-time TEST.
Output: analyses/audit/out/lp_a01.json
"""
from pathlib import Path
import glob, json, sys
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; DER = ROOT / 'data/derived'; OUT = Path(__file__).parent / 'out'
ERA = pd.Timestamp('2026-03-30', tz='UTC').timestamp(); T26 = pd.Timestamp('2026-01-01', tz='UTC').timestamp()
END = pd.Timestamp('2026-10-16', tz='UTC').timestamp()


def boot_ratio(num, den, g, B=1000, seed=3):
    codes, _ = pd.factorize(g); sn = np.bincount(codes, num); sd = np.bincount(codes, den); n = len(sn)
    rng = np.random.default_rng(seed); est = []
    for b0 in range(0, B, 250):
        idx = rng.integers(0, n, size=(250, n)); est.append(sn[idx].sum(1) / sd[idx].sum(1))
    return np.quantile(np.concatenate(est), [0.025, 0.975]).round(5).tolist()


def sw(x, col, ci=True):
    v = x[col].values.astype(float); q = x.q.values.astype(float); ok = ~np.isnan(v)
    r = dict(mean=round(float((v[ok] * q[ok]).sum() / q[ok].sum()), 5), n=int(ok.sum()), events=int(x.event_id[ok].nunique()))
    if ci and ok.sum() > 100:
        e = boot_ratio(v[ok] * q[ok], q[ok], x.event_id.values[ok]); w = boot_ratio(v[ok] * q[ok], q[ok], x.week.values[ok], seed=4)
        r['ci_wider'] = [min(e[0], w[0]), max(e[1], w[1])]
    return r


def main():
    meta = pd.read_parquet(DER / 'lp_markouts/market_meta.parquet')
    cols = ['condition_id', 't', 'd', 'P', 'q', 'Y', 'M_pre', 'M_300', 'R_pre', 'R_300', 'ttr_h']
    x = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(glob.glob(str(DER / 'lp_markouts/mk_*.parquet')))], ignore_index=True)
    x = x.merge(meta[['condition_id', 'event_id', 'split', 'category', 'rate', 'rebr', 'winner_idx', 'closedTime_s']], on='condition_id', how='left')
    P = x.P.astype(float); d = x.d.astype(float)
    x['effM'] = d * (P - x.M_pre); x['moM300'] = d * (x.M_300 - x.M_pre); x['rsM300'] = d * (P - x.M_300)
    x.loc[x.M_pre.isna(), ['effM', 'moM300', 'rsM300']] = np.nan
    x['rsR300'] = np.where(x.R_pre.notna(), d * (P - x.R_300), np.nan)
    x['rsres'] = d * (P - x.Y)
    x['reb'] = x.rebr * x.rate * P * (1 - P)
    x['netM300'] = x.rsM300 + x.reb; x['netR300'] = x.rsR300 + x.reb; x['netres'] = x.rsres + x.reb
    x['week'] = pd.to_datetime(x.t, unit='s').dt.strftime('%G-%V')
    x['pb98'] = P >= 0.98
    res = {}
    T = x[x.split == 'test']
    q = T.q.astype(float)
    res['test_share_before_2026'] = round(float(q[T.t < T26].sum() / q.sum()), 4)
    res['test_trades_before_2026'] = round(float((T.t < T26).mean()), 4)
    res['test_share_after_2026_10_15'] = round(float(q[T.t >= END].sum() / q.sum()), 4)
    v = x[x.split == 'validation']; res['val_share_before_2025_07'] = round(float(v.q[v.t < pd.Timestamp('2025-07-01', tz='UTC').timestamp()].sum() / v.q.sum()), 4)
    res['markets_winner_unknown'] = int(meta.winner_idx.isna().sum()); res['markets_total'] = int(len(meta))
    # headline, TEST (market split) and TEST (trade time in 2026-01-01..10-15 and market split test)
    TT = T[(T.t >= T26) & (T.t < END)]
    for lab, Z in (('test_mkt', T), ('test_tradetime', TT)):
        for col in ('effM', 'moM300', 'rsM300', 'rsR300', 'rsres'):
            res[f'{lab}|{col}'] = sw(Z, col)
        C = Z[Z.t >= ERA]
        for col in ('rsM300', 'rsR300', 'netM300', 'netR300', 'rsres', 'netres'):
            res[f'{lab}|era|{col}'] = sw(C, col)
        for cell, m in (('>98c', C.pb98), ('ttr<=1h', (C.ttr_h >= 0) & (C.ttr_h <= 1)), ('ttr7-30d', (C.ttr_h > 168) & (C.ttr_h <= 720))):
            Z2 = C[m.values]
            for col in ('rsM300', 'rsR300', 'netR300', 'rsres', 'netres'):
                res[f'{lab}|era|{cell}|{col}'] = sw(Z2, col)
            Z3 = Z2[Z2.M_pre.notna()]
            res[f'{lab}|era|{cell}|M_sample_early_close_share'] = round(float(((Z3.closedTime_s - Z3.t) / 3600 < Z3.ttr_h - 72).mean()), 3) if len(Z3) else None
    (OUT / 'lp_a01.json').write_text(json.dumps(res, indent=1))
    for k, v in res.items():
        print(k, v)


if __name__ == '__main__':
    main()
