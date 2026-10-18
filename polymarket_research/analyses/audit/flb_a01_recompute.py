"""AUDIT of flb_near_resolution (auditor, 2026-10-18). Independent re-implementation of the pre-registered rule returns.

Reads only data/derived/flb_entries.parquet + the two cost tables; does NOT use flb_sides.parquet or 04_analyze.py code.
Re-computes, for the 15 rules (TEST, P primary = base cost; W primary = conservative cost):
  weighted net mean, unweighted mean, gross, cluster / week / entry-day / two-way bootstraps,
  and cost sensitivities: MEAN (not median) half-spreads, p75 half-spreads, tick-floor half-spreads.
Output: analyses/audit/out/flb_a01.json (+ short printed summary)
"""
from pathlib import Path
import json, zlib
import numpy as np, pandas as pd
import sys
ROOT = Path(__file__).resolve().parents[2]; DER = ROOT / 'data/derived'; OUT = Path(__file__).parent / 'out'; OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
from pmr import fees

PB = [0, .02, .05, .15, .35, .65, .85, .95, .98, 1.0000001]
PBL = ['<2c', '2-5c', '5-15c', '15-35c', '35-65c', '65-85c', '85-95c', '95-98c', '>98c']
RULES = {'E1': ('A-1d', .80, .95), 'E2': ('A-7d', .95, 1.01)}
for t in (.90, .95, .98, .99):
    for hz, lab in (('A-1d', '24h'), ('A-6h', '6h'), ('A-1h', '1h')):
        RULES[f'H{int(round(t*100))}_{lab}'] = (hz, t, 1.01)


def half_spread_tables(stat):
    """stat in {'med','mean','p75'}: returns function(pb, ttr) -> (base, cons) half-spread, mirroring notes 0.5 levels."""
    sm = pd.read_parquet(DER / 'spread_model.parquet'); eh = pd.read_parquet(DER / 'effective_spread_hist.parquet')
    e = eh[(eh.split == 'test') & (eh.nbucket == 'ALL')]
    ecol = {'med': 'eff_half_med', 'mean': 'eff_half_mean', 'p75': 'eff_half_p75'}[stat]
    bcol = {'med': 'half_spread_med', 'mean': 'half_spread_mean', 'p75': 'half_spread_p75'}[stat]
    H1 = e[e.level == 'H1'].set_index(['pbucket', 'ttr_bucket'])[ecol].to_dict()
    H3 = e[e.level == 'H3'].set_index('pbucket')[ecol].to_dict()
    v = sm[(sm.book_universe == 'vol10k') & (sm.vtier == 'ALL')]
    L2 = v[(v.level == 'L2') & (v.n_markets_two_sided >= 20)].set_index(['pbucket', 'ttr_bucket'])[bcol].to_dict()
    L3 = v[v.level == 'L3'].set_index('pbucket')[bcol].to_dict()
    A3 = sm[(sm.book_universe == 'allopen') & (sm.vtier == 'ALL') & (sm.level == 'L3')].set_index('pbucket')[bcol].to_dict()

    def f(pb, ttr):
        hist = H1.get((pb, ttr), H3.get(pb, np.nan))
        book = L2.get((pb, ttr), L3.get(pb, np.nan))
        hist = max(hist, 0) if not np.isnan(hist) else np.nan  # mean eff spread can be negative (stale mids); floor at 0
        base = np.nanmax([hist, book]); cons = np.nanmax([base, A3.get(pb, np.nan)])
        return base, cons
    return f


def sides(E):
    e = E[(E.clock == 'A') & E.p0.notna()].copy()
    e['p0'] = e.p0.astype(float).round(4)
    a = e.assign(side=0, m=e.p0, pay=e.y0.astype(float))
    b = e.assign(side=1, m=(1 - e.p0).round(4), pay=1 - e.y0.astype(float))
    S = pd.concat([a, b], ignore_index=True)
    S['pb'] = pd.cut(S.m, PB, labels=PBL, right=False).astype(str)
    S['d'] = (pd.to_datetime(S.closedTime, utc=True) - pd.to_datetime(S.h_ts, utc=True)).dt.total_seconds() / 86400
    S['entry_day'] = pd.to_datetime(S.h_ts, utc=True).dt.strftime('%Y-%m-%d')
    S['rate'] = S.category.map(fees.TAKER_RATE).fillna(0.05)
    return S


def add_R(S, stat='med', mult=1.0, tag=''):
    f = half_spread_tables(stat)
    keys = S[['pb', 'ttr_bucket']].drop_duplicates()
    mp = {(r.pb, r.ttr_bucket): f(r.pb, r.ttr_bucket) for r in keys.itertuples()}
    hb = np.array([mp[(a, b)][0] for a, b in zip(S.pb, S.ttr_bucket)])
    hc = np.array([mp[(a, b)][1] for a, b in zip(S.pb, S.ttr_bucket)])
    h = np.where(S['sample'].values == 'P', hb, hc) * mult
    fp = S.m.values + h
    S['f' + tag] = fp
    S['R' + tag] = S.pay.values / (fp + S.rate.values * fp * (1 - fp)) - 1
    return S


def boot(x, w, g, B=4000, seed=1):
    codes, _ = pd.factorize(g)
    Sx = np.bincount(codes, w * x); Sw = np.bincount(codes, w); n = len(Sx)
    rng = np.random.default_rng(seed); out = []
    ch = max(1, int(3e6 // n))
    for b0 in range(0, B, ch):
        idx = rng.integers(0, n, size=(min(ch, B - b0), n))
        out.append(Sx[idx].sum(1) / Sw[idx].sum(1))
    return np.quantile(np.concatenate(out), [0.0033, 0.025, 0.975]).round(5).tolist()


def boot2(x, w, g1, g2, B=2000, seed=2):
    """Two-way (pigeonhole) bootstrap: resample g1 and g2 levels independently, weight obs by product of counts."""
    c1, _ = pd.factorize(g1); c2, _ = pd.factorize(g2); n1, n2 = c1.max() + 1, c2.max() + 1
    rng = np.random.default_rng(seed); est = []
    for _ in range(B):
        k1 = np.bincount(rng.integers(0, n1, n1), minlength=n1); k2 = np.bincount(rng.integers(0, n2, n2), minlength=n2)
        ww = w * k1[c1] * k2[c2]
        est.append((ww * x).sum() / ww.sum() if ww.sum() > 0 else np.nan)
    return np.nanquantile(est, [0.0033, 0.025, 0.975]).round(5).tolist()


def wm(x, w):
    return float(np.sum(w * x) / np.sum(w))


def main():
    E = pd.read_parquet(DER / 'flb_entries.parquet')
    S = sides(E)
    S = add_R(S, 'med', 1.0, '')
    S = add_R(S, 'med', 2.0, '_2x')
    S = add_R(S, 'mean', 1.0, '_mean')
    S = add_R(S, 'p75', 1.0, '_p75')
    S['R_gross'] = np.where(S.m >= 0.0005, S.pay / S.m.clip(lower=1e-9) - 1, np.nan)
    res = {}
    for rule, (hz, lo, hi) in RULES.items():
        for samp in ('P', 'W'):
            for split in ('test', 'validation', 'train'):
                T = S[(S['sample'] == samp) & (S.split == split) & (S.horizon == hz) & (S.m >= lo - 1e-9) & (S.m <= hi + 1e-9) & (S.f <= 0.999)]
                if len(T) == 0:
                    continue
                w = T.weight.values.astype(float); x = T.R.values
                r = dict(n=len(T), clusters=int(T.cluster_id.nunique()), weeks=int(T.cluster_week.nunique()),
                         days=int(T.entry_day.nunique()), losses=int((T.pay == 0).sum()), halves=int((T.pay == .5).sum()),
                         m_mean=round(wm(T.m.values, w), 5), f_mean=round(wm(T.f.values, w), 5),
                         net=round(wm(x, w), 5), net_unw=round(float(x.mean()), 5), gross=round(wm(T.R_gross.values, w), 5),
                         net2x=round(wm(T.R_2x.values, w), 5), net_meanhs=round(wm(T.R_mean.values, w), 5),
                         net_p75hs=round(wm(T.R_p75.values, w), 5),
                         loss_w=round(wm((T.pay == 0).values.astype(float), w), 5),
                         breakeven_loss=round(float(1 - wm(T.f.values, w)), 5))
                if split == 'test' and rule in ('E2', 'H99_6h', 'H98_6h', 'H99_1h', 'E1') or (split == 'test' and samp == 'P'):
                    seed = zlib.crc32(f'{rule}{samp}{split}'.encode())
                    r['ci_cluster'] = boot(x, w, T.cluster_id.values, seed=seed)
                    r['ci_week'] = boot(x, w, T.cluster_week.values, seed=seed + 1)
                    r['ci_entryday'] = boot(x, w, T.entry_day.values, seed=seed + 2)
                    r['ci_unw_cluster'] = boot(x, np.ones_like(w), T.cluster_id.values, seed=seed + 3)
                    if rule in ('E2', 'H99_6h'):
                        r['ci_twoway_cluster_day'] = boot2(x, w, T.cluster_id.values, T.entry_day.values, seed=seed + 4)
                res[f'{rule}|{samp}|{split}'] = r
    (OUT / 'flb_a01.json').write_text(json.dumps(res, indent=1))
    for k in ('E2|P|test', 'E2|W|test', 'E2|P|validation', 'E2|W|validation', 'H99_6h|P|test', 'H99_6h|W|test', 'H99_6h|W|validation', 'E1|P|test', 'H90_24h|P|test'):
        r = res.get(k, {})
        print(k, {kk: r.get(kk) for kk in ('n', 'losses', 'net', 'net_unw', 'gross', 'net2x', 'net_meanhs', 'net_p75hs', 'ci_cluster', 'ci_week', 'ci_entryday', 'ci_twoway_cluster_day', 'ci_unw_cluster', 'breakeven_loss', 'loss_w')})


if __name__ == '__main__':
    main()
