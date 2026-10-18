"""Families E (favourite-longshot bias) and H (near-resolution convergence): calibration, costs, pre-registered rules.

Implements notes/strategies/flb_near_resolution.md section 0 as written (deviations: notes section 9).
Input : data/derived/flb_entries.parquet (03_build_entries.py; P = stage-2 panel, W = volume-free wide sample).
Output: data/derived/flb_sides.parquet (market x horizon x side, with costs/returns),
        analyses/flb_near_res/out/04_results.md, 04_results.json.
Run   : python analyses/flb_near_res/04_analyze.py [entries_path]
"""
import json, sys, zlib
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pmr import fees
ROOT = Path(__file__).resolve().parents[2]; DER = ROOT / 'data/derived'; OUT = Path(__file__).parent / 'out'
TBILL_D = 0.0387 / 365  # US Treasury avg rate on marketable T-bills, 2026-09-30 (pre-registered, notes 0.6)
import os
B_RULE, B_DESC = (4000, 2000) if not os.environ.get('QUICK') else (200, 100)
PB_EDGES = [0, .02, .05, .15, .35, .65, .85, .95, .98, 1.0000001]
PB_LABELS = ['<2c', '2-5c', '5-15c', '15-35c', '35-65c', '65-85c', '85-95c', '95-98c', '>98c']
CAL_EDGES = [0, .02, .05, .10, .20, .30, .40, .50, .60, .70, .80, .90, .95, .98, 1.0000001]
CAL_LABELS = ['00-02', '02-05', '05-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80-90', '90-95',
              '95-98', '98-100']
EH = ['A-7d', 'A-1d', 'A-6h', 'A-1h']
RULES = {'E1': ('A-1d', 0.80, 0.95), 'E2': ('A-7d', 0.95, 1.01)}
for thr in (0.90, 0.95, 0.98, 0.99):
    for hz, lab in (('A-1d', '24h'), ('A-6h', '6h'), ('A-1h', '1h')):
        RULES[f'H{int(round(thr * 100))}_{lab}'] = (hz, thr, 1.01)
EPS = 1e-9


# ----------------------------------------------------------------------------------------------------------- costs
def cost_tables():
    sm = pd.read_parquet(DER / 'spread_model.parquet'); eh = pd.read_parquet(DER / 'effective_spread_hist.parquet')
    e = eh[(eh.split == 'test') & (eh.nbucket == 'ALL')]
    h1 = e[e.level == 'H1'].set_index(['pbucket', 'ttr_bucket']).eff_half_med
    h3 = e[(e.level == 'H3')].set_index('pbucket').eff_half_med
    v = sm[(sm.book_universe == 'vol10k') & (sm.vtier == 'ALL')]
    l2 = v[(v.level == 'L2') & (v.n_markets_two_sided >= 20)].set_index(['pbucket', 'ttr_bucket']).half_spread_med
    l3 = v[v.level == 'L3'].set_index('pbucket')
    a3 = sm[(sm.book_universe == 'allopen') & (sm.vtier == 'ALL') & (sm.level == 'L3')].set_index('pbucket').half_spread_med
    for x in (h1, h3, l2, a3):
        assert x.index.is_unique
    return h1, h3, l2, l3, a3


def fee_cur(f, cat):
    return cat.map(fees.TAKER_RATE).fillna(0.05).values * f * (1 - f)


def add_costs(S):
    h1, h3, l2, l3, a3 = cost_tables()
    mi = pd.MultiIndex.from_arrays([S.pb.values, S.ttr_bucket.values])
    hist = h1.reindex(mi).values; hist = np.where(np.isnan(hist), h3.reindex(S.pb.values).values, hist)
    book = l2.reindex(mi).values; book = np.where(np.isnan(book), l3.half_spread_med.reindex(S.pb.values).values, book)
    S['h_base'] = np.fmax(hist, book); S['h_cons'] = np.fmax(S.h_base.values, a3.reindex(S.pb.values).values)
    S['h_src_hist'] = hist; S['h_src_book'] = book
    m, pay, cat = S.m.values, S.pay.values, S.category
    S['R_gross'] = np.where(m >= 0.0005, pay / np.maximum(m, 1e-9) - 1, np.nan)
    for k in ('base', 'cons'):
        f = m + S[f'h_{k}'].values; S[f'f_{k}'] = f
        S[f'R_spread_{k}'] = pay / f - 1
        S[f'R_net_{k}'] = pay / (f + fee_cur(f, cat)) - 1
        f2 = m + 2 * S[f'h_{k}'].values
        S[f'R_net2x_{k}'] = pay / (f2 + fee_cur(f2, cat)) - 1
    fb = S.f_base.values
    asf = np.where(S.feesEnabled.fillna(False).values.astype(bool) & S.fee_rate.notna().values,
                   S.fee_rate.fillna(0).values * (fb * (1 - fb)) ** S.fee_exponent.fillna(1).values, 0.0)
    S['R_asT_base'] = pay / (fb + asf) - 1
    prim = np.where(S['sample'].values == 'P', 'base', 'cons')
    S['f_prim'] = np.where(prim == 'base', S.f_base, S.f_cons)
    S['R_prim'] = np.where(prim == 'base', S.R_net_base, S.R_net_cons)
    S['R_prim2x'] = np.where(prim == 'base', S.R_net2x_base, S.R_net2x_cons)
    S['R_spread_prim'] = np.where(prim == 'base', S.R_spread_base, S.R_spread_cons)
    # capacity: vol10k L3 buy slippage from mid at $500/$2.5k/$10k (+ current fee)
    for s in (500, 2500, 10000):
        sl = l3[f'slip_buy_{s}_med'].reindex(S.pb.values).values; f = m + sl
        S[f'R_net_size{s}'] = pay / (f + fee_cur(f, cat)) - 1
        S[f'fillable_{s}'] = l3[f'fillable_buy_{s}'].reindex(S.pb.values).values
    return S


# ----------------------------------------------------------------------------------------------------------- sides
def make_sides(E):
    e = E[E.p0.notna()].copy()
    e['p0'] = e.p0.astype(float).round(4)
    s0 = e.assign(side=0, m=e.p0, pay=e.y0.astype(float))
    s1 = e.assign(side=1, m=(1 - e.p0).round(4), pay=1 - e.y0.astype(float))
    S = pd.concat([s0, s1], ignore_index=True)
    S['pb'] = pd.cut(S.m, PB_EDGES, labels=PB_LABELS, right=False).astype(object)
    S['cal'] = pd.cut(S.m, CAL_EDGES, labels=CAL_LABELS, right=False).astype(object)
    S['d'] = (pd.to_datetime(S.closedTime, utc=True) - pd.to_datetime(S.h_ts, utc=True)).dt.total_seconds() / 86400
    S['entry_day'] = pd.to_datetime(S.h_ts, utc=True).dt.floor('D').astype(str)
    S['is_yes_side'] = ((S.side == 0) & (S.outcome0 == 'Yes')) | ((S.side == 1) & (S.outcome0 == 'No'))
    S['yesno'] = S.outcome0.isin(['Yes', 'No'])
    # volume tercile within sample x split (full-life volumeNum: look-ahead, descriptive only)
    mk = S.drop_duplicates(['sample', 'split', 'condition_id'])[['sample', 'split', 'condition_id', 'volumeNum']]
    mk['vterc'] = mk.groupby(['sample', 'split']).volumeNum.transform(
        lambda v: pd.qcut(v.rank(method='first'), 3, labels=['low', 'mid', 'high']).astype(str))
    S = S.merge(mk[['sample', 'split', 'condition_id', 'vterc']], on=['sample', 'split', 'condition_id'], how='left')
    return add_costs(S)


# ------------------------------------------------------------------------------------------------------- inference
def boot(x, w, g, B, seed=0, qs=(0.0033, 0.025, 0.975, 0.9967)):
    codes, _ = pd.factorize(g)
    Sx = np.bincount(codes, w * x); Sw = np.bincount(codes, w); n = len(Sx)
    if n < 2:
        return [np.nan] * len(qs)
    rng = np.random.default_rng(seed); est = []
    ch = max(1, min(B, int(4e6 // n)))
    for b0 in range(0, B, ch):
        idx = rng.integers(0, n, size=(min(ch, B - b0), n))
        est.append(Sx[idx].sum(1) / Sw[idx].sum(1))
    return list(np.quantile(np.concatenate(est), qs))


def icc(x, g):
    d = pd.DataFrame({'x': x, 'g': g}); N = len(d); gs = d.groupby('g').x; k = gs.ngroups
    if k < 2 or N <= k:
        return np.nan, np.nan
    ni = gs.size().values; mi = gs.mean().values; gm = d.x.mean()
    msb = (ni * (mi - gm) ** 2).sum() / (k - 1); msw = ((d.x - gs.transform('mean')) ** 2).sum() / (N - k)
    n0 = (N - (ni ** 2).sum() / N) / (k - 1)
    r = (msb - msw) / (msb + (n0 - 1) * msw) if (msb + (n0 - 1) * msw) > 0 else np.nan
    deff = 1 + ((ni ** 2).sum() / N - 1) * r
    return r, deff


def wm(x, w):
    x = np.asarray(x, float); w = np.asarray(w, float); ok = ~np.isnan(x)
    return float((w[ok] * x[ok]).sum() / w[ok].sum()) if ok.any() else np.nan


def summarize(T, full=True, seed=0):
    if len(T) == 0:
        return dict(n=0)
    w = T.weight.values.astype(float)
    r = dict(n=len(T), n_clusters=T.cluster_id.nunique(), n_weeks=T.cluster_week.nunique(), pop_trades=float(w.sum()),
             m_mean=wm(T.m, w), f_mean=wm(T.f_prim, w), win=wm(T.pay == 1, w), loss=wm(T.pay == 0, w),
             half=wm(T.pay == 0.5, w), gross=wm(T.R_gross, w), spread=wm(T.R_spread_prim, w), net=wm(T.R_prim, w),
             net2x=wm(T.R_prim2x, w), net_base=wm(T.R_net_base, w), net_cons=wm(T.R_net_cons, w),
             asT=wm(T.R_asT_base, w), d_mean=wm(T.d, w), d_med=float(T.d.median()),
             unweighted_net=float(T.R_prim.mean()))
    r['ret_per_day'] = float((w * T.R_prim).sum() / (w * T.d).sum())
    r['excess_vs_tbill'] = wm(T.R_prim - TBILL_D * T.d, w)
    if not full:
        return r
    for col, tag in (('R_prim', ''), ('R_net_base', '_base')):
        for gname in ('cluster_id', 'cluster_week'):
            q = boot(T[col].values, w, T[gname].values, B_RULE, seed)
            r[f'ci{tag}_{gname}'] = q  # [bonf_lo, lo95, hi95, bonf_hi]
    cs = T.assign(c=w * T.R_prim).groupby('cluster_id').agg(c=('c', 'sum'), w=('weight', 'sum'))
    top = cs.sort_values('c', ascending=False).head(5)
    r['net_drop_top5'] = float((cs.c.sum() - top.c.sum()) / (cs.w.sum() - top.w.sum())) if len(cs) > 5 else np.nan
    r['icc_cluster'], r['deff_cluster'] = icc(T.R_prim.values, T.cluster_id.values)
    r['icc_day'], r['deff_day'] = icc(T.R_prim.values, T.entry_day.values)
    pc = T.groupby('cluster_id').agg(pnl=('R_prim', 'sum'), k=('R_prim', 'size'), q=('question', 'first'))
    wc = pc.sort_values('pnl').iloc[0]
    r['worst_cluster_pnl_per_$1_each'] = float(wc.pnl); r['worst_cluster_k'] = int(wc.k)
    r['worst_cluster_q'] = str(wc.q)[:90]; r['max_trades_per_cluster'] = int(pc.k.max())
    r['worst_trade_R'] = float(T.R_prim.min())
    for s in (500, 2500, 10000):
        r[f'net_size{s}'] = wm(T[f'R_net_size{s}'], w); r[f'fillable_{s}'] = wm(T[f'fillable_{s}'], w)
    return r


def rule_trades(S, rule, extra=None):
    hz, lo, hi = RULES[rule] if rule in RULES else rule
    T = S[(S.horizon == hz) & (S.m >= lo - EPS) & (S.m <= hi + EPS) & (S.f_prim <= 0.999)]
    if extra is not None:
        T = T[extra(T)]
    return T


# ---------------------------------------------------------------------------------------------------- calibration
def calib(S, keys, B=B_DESC, ci=True):
    rows = []
    for k, g in S.groupby(keys, dropna=False):
        w = g.weight.values.astype(float)
        r = dict(zip(keys, k if isinstance(k, tuple) else (k,)))
        r.update(n=len(g), n_cl=g.cluster_id.nunique(), price=wm(g.m, w), realised=wm(g.pay, w))
        r['diff'] = r['realised'] - r['price']
        r['R_gross'] = wm(g.R_gross, w); r['R_net'] = wm(g.R_prim, w)
        if ci and g.cluster_id.nunique() >= 10:
            q = boot((g.pay - g.m).values, w, g.cluster_id.values, B, qs=(0.025, 0.975)); r['lo'], r['hi'] = q
            q = boot(g.R_prim.values, w, g.cluster_id.values, B, qs=(0.025, 0.975)); r['Rlo'], r['Rhi'] = q
        rows.append(r)
    return pd.DataFrame(rows)


def to_md(df, index=False, floatfmt='.4f'):
    df = df.reset_index() if index else df
    def f(v):
        if isinstance(v, (float, np.floating)):
            return '' if np.isnan(v) else format(v, floatfmt)
        return str(v)
    head = '| ' + ' | '.join(map(str, df.columns)) + ' |'
    sep = '|' + '|'.join('---' for _ in df.columns) + '|'
    return '\n'.join([head, sep] + ['| ' + ' | '.join(f(v) for v in row) + ' |' for row in df.itertuples(index=False)])


def fmt(df, cols=None, nd=4):
    df = df if cols is None else df[[c for c in cols if c in df]]
    return to_md(df, floatfmt=f'.{nd}f') if len(df) else '(empty)'


def ci_s(r, key):
    q = r.get(key)
    return '' if q is None or any(pd.isna(q)) else f'[{q[1]:+.4f}, {q[2]:+.4f}] (bonf lo {q[0]:+.4f})'


# ------------------------------------------------------------------------------------------------------------ main
def main(path=None):
    path = Path(path) if path else DER / 'flb_entries.parquet'
    E = pd.read_parquet(path)
    if 'outcome0' not in E:
        E['outcome0'] = E.outcomes.map(lambda o: str(o[0]) if o is not None and len(o) else None)
    S = make_sides(E)
    keep = ['sample', 'split', 'condition_id', 'event_id', 'cluster_id', 'cluster_week', 'category', 'horizon', 'clock',
            'ttr_bucket', 'h_ts', 'side', 'm', 'pay', 'pb', 'cal', 'weight', 'd', 'h_base', 'h_cons', 'f_base', 'f_cons',
            'R_gross', 'R_spread_base', 'R_net_base', 'R_net_cons', 'R_net2x_base', 'R_net2x_cons', 'R_asT_base', 'R_prim',
            'vterc', 'is_yes_side', 'yesno', 'vol_screen_at_h', 'resolution', 'has_disputed', 'settle_lag_h']
    X = S[keep].copy(); X['vol_screen_at_h'] = X.vol_screen_at_h.astype(object).map(lambda v: None if v is None else bool(v))
    X.to_parquet(DER / 'flb_sides.parquet', index=False); del X
    md = [f'# 04 results (generated by 04_analyze.py from {path.name})', '']
    js = {}
    samples = sorted(S['sample'].unique())

    # ---- coverage
    cov = S[S.side == 0].groupby(['sample', 'split', 'horizon']).size().unstack('horizon')
    md += ['## Coverage (markets priced per sample x split x horizon)', to_md(cov, index=True, floatfmt='.0f'), '']

    # ---- E: calibration by bucket x horizon (TEST), both samples
    md += ['## E1 calibration: TEST, bucket x horizon (A clock). diff = realised - price; [lo,hi] cluster 95% CI.'
           ' R_gross = buy at series price; R_net = primary cost (P base, W cons) + current fee', '']
    cal_all = []
    for smp in samples:
        for hz in EH:
            sub = S[(S['sample'] == smp) & (S.split == 'test') & (S.horizon == hz)]
            if len(sub) == 0:
                continue
            c = calib(sub, ['cal']); c.insert(0, 'horizon', hz); c.insert(0, 'sample', smp); cal_all.append(c)
    cal_all = pd.concat(cal_all, ignore_index=True)
    cal_all.to_parquet(DER / 'flb_calibration_test.parquet', index=False)
    for smp in samples:
        md += [f'### sample {smp}', fmt(cal_all[cal_all['sample'] == smp],
                                         ['horizon', 'cal', 'n', 'n_cl', 'price', 'realised', 'diff', 'lo', 'hi', 'R_gross',
                                          'R_net', 'Rlo', 'Rhi']), '']
    # FLB presence test: pooled <=10c sides (TEST)
    flb = []
    for smp in samples:
        for hz in EH:
            for tail, cond in (('<=10c', lambda s: s.m < 0.10), ('>=90c', lambda s: s.m >= 0.90)):
                sub = S[(S['sample'] == smp) & (S.split == 'test') & (S.horizon == hz)]; sub = sub[cond(sub)]
                if len(sub) < 10:
                    continue
                c = calib(sub.assign(t=tail), ['t']).iloc[0].to_dict(); c.update(sample=smp, horizon=hz)
                c['flb_present'] = bool((tail == '<=10c') and c.get('hi', np.nan) < 0); flb.append(c)
    flb = pd.DataFrame(flb); js['flb_presence'] = flb.to_dict('records')
    md += ['## E1b FLB presence (pre-registered descriptive test): pooled tails, TEST',
           fmt(flb, ['sample', 'horizon', 't', 'n', 'n_cl', 'price', 'realised', 'diff', 'lo', 'hi', 'R_gross', 'R_net', 'Rlo',
                     'Rhi', 'flb_present']), '']

    # ---- tails by category, volume tercile, period
    def tails(df, keys):
        df = df.assign(tl=np.select([df.m < 0.10, df.m >= 0.90], ['<=10c', '>=90c'], 'mid'))
        df = df[df.tl != 'mid']
        return calib(df, keys + ['tl'])
    for nm, keys, filt in (('category (TEST, A-1d)', ['sample', 'category'], lambda s: (s.split == 'test') & (s.horizon == 'A-1d')),
                           ('category (TEST, A-1h)', ['sample', 'category'], lambda s: (s.split == 'test') & (s.horizon == 'A-1h')),
                           ('volume tercile (full-life volumeNum, look-ahead; TEST)', ['sample', 'horizon', 'vterc'],
                            lambda s: (s.split == 'test') & s.horizon.isin(['A-1d', 'A-1h'])),
                           ('period (split)', ['sample', 'horizon', 'split'], lambda s: s.horizon.isin(EH))):
        t = tails(S[filt(S)], keys)
        md += [f'## E2 tails by {nm}', fmt(t, keys + ['tl', 'n', 'n_cl', 'price', 'realised', 'diff', 'lo', 'hi', 'R_gross',
                                                     'R_net', 'Rlo', 'Rhi']), '']
        js[f'tails_{nm}'] = t.to_dict('records')

    # ---- E1X category selection on train+validation (P, base cost = primary for P)
    tv = rule_trades(S[(S['sample'] == 'P') & S.split.isin(['train', 'validation'])], 'E1')
    sel = tv.groupby('category').apply(lambda g: pd.Series(dict(n=len(g), net=wm(g.R_net_base, g.weight))),
                                       include_groups=False).reset_index()
    X = sorted(sel[(sel.n >= 30) & (sel.net > 0)].category)
    js['E1X_selection'] = sel.to_dict('records'); js['E1X_X'] = X
    md += ['## E1X category selection (P, train+validation pooled, E1, base cost + current fee)', fmt(sel), f'X = {X}', '']

    # ---- rules
    rule_list = list(RULES) + (['E1X'] if X else [])
    res = {}
    for rule in rule_list:
        for smp in samples:
            for sp in ('train', 'validation', 'test'):
                sub = S[(S['sample'] == smp) & (S.split == sp)]
                T = rule_trades(sub, 'E1', lambda t: t.category.isin(X)) if rule == 'E1X' else rule_trades(sub, rule)
                res[(rule, smp, sp)] = summarize(T, full=(sp == 'test') or (sp == 'validation' and smp == 'P'),
                                                 seed=zlib.crc32(rule.encode()) % 1000)
        # literal E2 variant + vol-screen subset (P TEST)
        if rule in ('E1', 'E1X') or rule.startswith('H') or rule == 'E2':
            sub = S[(S['sample'] == 'P') & (S.split == 'test')]
            T = rule_trades(sub, 'E1', lambda t: t.category.isin(X)) if rule == 'E1X' else rule_trades(sub, rule)
            V = T[T.vol_screen_at_h.astype(object).map(lambda v: v is True or v == True)]
            res[(rule, 'P_volscreen', 'test')] = summarize(V, full=False) if len(V) else dict(n=0)
    for smp in samples:
        for sp in ('validation', 'test'):
            sub = S[(S['sample'] == smp) & (S.split == sp)]
            T = rule_trades(sub, 'E2', lambda t: t.yesno & ~t.is_yes_side)  # longshot = the Yes token -> buy No
            res[('E2_literal', smp, sp)] = summarize(T, full=(sp == 'test'))

    # ---- verdicts
    verdicts = {}
    for rule in rule_list:
        pt, pv, wt = res[(rule, 'P', 'test')], res[(rule, 'P', 'validation')], res.get((rule, 'W', 'test'), dict(n=0))
        vs = res[(rule, 'P_volscreen', 'test')]
        if pt.get('n', 0) == 0:
            verdicts[rule] = dict(verdict='no_demonstrated_edge', note='no trades'); continue
        c = {}
        c['1_bonf_lo_gt0_both'] = bool(pt['ci_cluster_id'][0] > 0 and pt['ci_cluster_week'][0] > 0)
        c['2_val_net_gt0'] = bool(pv.get('net', np.nan) > 0)
        c['3_ret_per_day_gt_tbill'] = bool(pt['ret_per_day'] > TBILL_D)
        c['4_net2x_gt0'] = bool(pt['net2x'] > 0)
        c['5_drop_top5_gt0'] = bool(pt['net_drop_top5'] > 0)
        c['6_n200_cl100_wk20'] = bool(pt['n'] >= 200 and pt['n_clusters'] >= 100 and pt['n_weeks'] >= 20)
        c['7_W_test_base_gt0'] = bool(wt.get('n', 0) > 0 and wt['net_base'] > 0)
        c['8_volscreen_gt0'] = (bool(vs['net'] > 0) if vs.get('n', 0) >= 100 else 'n/a (n<100)')
        prom = all(v is True or v == 'n/a (n<100)' for v in c.values())
        rej = pt['ci_cluster_id'][2] < 0
        mar_a = pt['net'] > 0 and all(c[k] for k in ['3_ret_per_day_gt_tbill', '4_net2x_gt0', '5_drop_top5_gt0',
                                                     '6_n200_cl100_wk20', '7_W_test_base_gt0'])
        mar_b = wt.get('n', 0) > 0 and wt['ci_base_cluster_id'][1] > 0 and wt['ci_base_cluster_week'][1] > 0
        v = ('promising_test_further' if prom else 'rejected' if rej else 'marginal' if (mar_a or mar_b)
             else 'no_demonstrated_edge')
        verdicts[rule] = dict(verdict=v, criteria=c, rejected_flag=bool(rej), marginal_a=bool(mar_a), marginal_b=bool(mar_b))

    # ---- rule tables
    cols = ['n', 'n_clusters', 'n_weeks', 'pop_trades', 'm_mean', 'f_mean', 'win', 'loss', 'half', 'gross', 'spread', 'net',
            'net2x', 'asT', 'net_base', 'net_cons', 'd_mean', 'd_med', 'ret_per_day', 'excess_vs_tbill']
    rows = []
    for (rule, smp, sp), r in res.items():
        rows.append(dict(rule=rule, sample=smp, split=sp, **{k: r.get(k, np.nan) for k in cols}))
    RT = pd.DataFrame(rows)
    md += [f'## Rules: all samples/splits. net = primary cost (P base, W conservative) + current fee; T-bill/day = {TBILL_D:.6f}',
           fmt(RT, ['rule', 'sample', 'split'] + cols), '']
    md += ['## Rules: TEST inference (net primary; 95% CI wider-of-two reported in notes) and verdicts', '']
    vrows = []
    for rule in rule_list:
        pt = res[(rule, 'P', 'test')]; wt = res.get((rule, 'W', 'test'), {})
        if pt.get('n', 0) == 0:
            continue
        vrows.append(dict(rule=rule, n=pt['n'], net=pt['net'], ci_cluster=ci_s(pt, 'ci_cluster_id'),
                          ci_week=ci_s(pt, 'ci_cluster_week'), drop5=pt['net_drop_top5'], net2x=pt['net2x'],
                          val_net=res[(rule, 'P', 'validation')].get('net'), W_n=wt.get('n'), W_net_cons=wt.get('net'),
                          W_net_base=wt.get('net_base'), W_ci_base_cl=ci_s(wt, 'ci_base_cluster_id') if wt else '',
                          volscr_n=res[(rule, 'P_volscreen', 'test')].get('n'),
                          volscr_net=res[(rule, 'P_volscreen', 'test')].get('net'), verdict=verdicts[rule]['verdict']))
    md += [to_md(pd.DataFrame(vrows)), '']
    md += ['## Correlation / tail-loss (TEST, primary net)', '']
    crow = []
    for (rule, smp, sp), r in res.items():
        if sp == 'test' and smp in ('P', 'W') and r.get('n', 0) and 'icc_cluster' in r:
            crow.append(dict(rule=rule, sample=smp, n=r['n'], loss=r['loss'], worst_trade=r['worst_trade_R'],
                             icc_cluster=r['icc_cluster'], deff_cluster=r['deff_cluster'], icc_day=r['icc_day'],
                             deff_day=r['deff_day'], max_k_cluster=r['max_trades_per_cluster'],
                             worst_cluster_pnl=r['worst_cluster_pnl_per_$1_each'], worst_cluster_k=r['worst_cluster_k'],
                             worst_cluster_q=r['worst_cluster_q']))
    md += [to_md(pd.DataFrame(crow)), '']
    md += ['## Capacity inputs (P TEST): net mean R with vol10k L3 buy slippage at size + current fee; share of books fillable', '']
    caprow = []
    for rule in rule_list:
        r = res[(rule, 'P', 'test')]
        if r.get('n', 0):
            caprow.append(dict(rule=rule, pop_trades_test=r['pop_trades'], per_week=r['pop_trades'] / (288 / 7),
                               d_mean=r['d_mean'], cap_needed_at_500=500 * r['pop_trades'] / 288 * r['d_mean'],
                               **{f'net_{s}': r[f'net_size{s}'] for s in (500, 2500, 10000)},
                               **{f'fill_{s}': r[f'fillable_{s}'] for s in (500, 2500, 10000)}))
    md += [to_md(pd.DataFrame(caprow)), '']

    # ---- H descriptive: disjoint bands, category, R clock, in-play
    bands = [(0.90, 0.95), (0.95, 0.98), (0.98, 0.99), (0.99, 1.0)]
    hd = []
    for smp in samples:
        for hz in ['A-1d', 'A-6h', 'A-1h', 'R-1d', 'R-6h', 'R-1h', 'A+1h', 'A+2h']:
            for lo, hi in bands:
                sub = S[(S['sample'] == smp) & (S.split == 'test')]
                T = rule_trades(sub, (hz, lo, hi - 1e-6 if hi < 1 else 1.01))
                if len(T):
                    r = summarize(T, full=False); hd.append(dict(sample=smp, horizon=hz, band=f'[{lo:.2f},{hi:.2f})',
                                                                **{k: r[k] for k in ['n', 'n_clusters', 'm_mean', 'win', 'loss',
                                                                                     'gross', 'net', 'net_base', 'd_mean',
                                                                                     'ret_per_day']}))
    md += ['## H descriptive: disjoint bands, TEST (R-* = realised-close clock, LOOK-AHEAD; A+* = in-play, sports)',
           to_md(pd.DataFrame(hd)), '']
    hc = []
    for smp in samples:
        for rule in ['H90_24h', 'H95_6h', 'H95_1h', 'H99_1h']:
            T = rule_trades(S[(S['sample'] == smp) & (S.split == 'test')], rule)
            for cat, g in T.groupby('category'):
                r = summarize(g, full=False)
                hc.append(dict(sample=smp, rule=rule, category=cat, **{k: r[k] for k in ['n', 'n_clusters', 'win', 'gross',
                                                                                        'net', 'ret_per_day']}))
    md += ['## H by category (TEST, descriptive)', to_md(pd.DataFrame(hc)), '']

    # ---- worst cases, disputes, settlement delay (H trades, TEST, union of the 12 H rules = the >=0.90 set)
    Hset = pd.concat([rule_trades(S[S.split == 'test'], r).assign(rule=r) for r in RULES if r.startswith('H')])
    Hu = Hset.sort_values('m', ascending=False).drop_duplicates(['sample', 'condition_id', 'horizon'])
    worst = Hu[Hu.pay < 1].sort_values(['m'], ascending=False).drop_duplicates(['sample', 'condition_id']).head(25)
    worst = worst.assign(question=worst.question.str.slice(0, 80))
    md += ['## H worst cases: TEST losses (payout 0 or 0.5) with the highest entry price',
           fmt(worst, ['sample', 'horizon', 'category', 'm', 'f_prim', 'pay', 'R_prim', 'has_disputed', 'settle_lag_h',
                       'question']), '']
    dz = []
    for smp in samples:
        for hz in ['A-1d', 'A-6h', 'A-1h']:
            g = Hu[(Hu['sample'] == smp) & (Hu.horizon == hz)].drop_duplicates('condition_id')
            if len(g) == 0:
                continue
            w = g.weight.values.astype(float); lag = g.settle_lag_h
            dz.append(dict(sample=smp, horizon=hz, n=len(g), disputed=wm(g.has_disputed.fillna(False), w),
                           multi_proposal=wm(g.multi_proposal.fillna(False), w), fifty=wm(g.pay == 0.5, w),
                           lag_med_h=float(lag.median()), lag_p90_h=float(lag.quantile(.9)), lag_p99_h=float(lag.quantile(.99)),
                           sh_lag_gt24h=wm(lag > 24, w), sh_lag_gt72h=wm(lag > 72, w), sh_lag_gt7d=wm(lag > 168, w),
                           d_held_mean=wm(g.d, w), d_held_p90=float(g.d.quantile(.9)),
                           tbill_cost_mean=wm(TBILL_D * g.d, w)))
    md += ['## H disputes / 50-50 / settlement delay (closedTime - endDate) for TEST >=0.90 entries',
           to_md(pd.DataFrame(dz)), '']
    js['disputes'] = dz; js['worst_cases'] = worst[['sample', 'horizon', 'category', 'm', 'pay', 'question']].to_dict('records')
    js['rules'] = {f'{a}|{b}|{c}': v for (a, b, c), v in res.items()}; js['verdicts'] = verdicts
    js['tbill_per_day'] = TBILL_D
    (OUT / '04_results.md').write_text('\n'.join(md))
    (OUT / '04_results.json').write_text(json.dumps(js, indent=1, default=lambda o: o.item() if hasattr(o, 'item') else str(o)))
    print('verdicts:', {k: v['verdict'] for k, v in verdicts.items()})


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
