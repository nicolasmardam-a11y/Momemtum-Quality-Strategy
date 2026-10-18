"""Build decision-time entries (one row per market x horizon) for samples P (stage-2 panel) and W (volume-free).

Clocks (pre-registered, notes 0.3): anchor A = gameStartTime for sports markets with one, else endDate.
Horizons: A-7d, A-1d, A-6h, A-1h (all); A+1h, A+2h (sports with a game anchor; in-play, secondary);
R-1d, R-6h, R-1h on the realised close clock (closedTime; descriptive look-ahead benchmark only).
A horizon is valid only if horizon < closedTime and a series point exists at or before it within 15 min (minute / 5-min
grid) or 2 h (hourly grid), and (W) it is not inside a grid gap. Price = last series point with t <= horizon (no look-ahead).
P series: panel price_series_m1 (ref_ts-72h..ref_ts) preferred, else price_series_h60; series end = ref_ts.
W series: 5-minute change points from 02_pull_wide.py.
Also: last_change_age_s, n_chg_24h (activity known at the horizon), and for P tape markets volnum_at_h_est / vol_screen_at_h
(volumeNum x share of taker notional traded at or before the horizon >= $10k).
Output: data/derived/flb_entries.parquet
"""
from pathlib import Path
import glob
import numpy as np, pandas as pd, pyarrow.parquet as pq, pyarrow.compute as pc
ROOT = Path(__file__).resolve().parents[2]; DER = ROOT / 'data/derived'
H = 3600; D = 86400
HOR = [('A-7d', -7 * D, '3-7d', 'A'), ('A-1d', -D, '6-24h', 'A'), ('A-6h', -6 * H, '1-6h', 'A'), ('A-1h', -H, '<=1h', 'A'),
       ('A+1h', H, 'in_play', 'A'), ('A+2h', 2 * H, 'in_play', 'A'),
       ('R-1d', -D, '6-24h', 'R'), ('R-6h', -6 * H, '1-6h', 'R'), ('R-1h', -H, '<=1h', 'R')]
KEEP = ['condition_id', 'question', 'outcomes', 'token_id_0', 'category', 'split', 'end_quarter', 'event_id', 'cluster_id',
        'cluster_week', 'structure', 'negRisk', 'volumeNum', 'fee_rate', 'fee_exponent', 'feesEnabled', 'feeType',
        'has_disputed', 'multi_proposal', 'settle_lag_h', 'settle_lag_game_h', 'resolution', 'y0', 'endDate', 'closedTime',
        'gameStartTime', 'anchor', 'anchor_type', 'weight', 'orderPriceMinTickSize', 'secondsDelay', 'sportsMarketType']


def epoch_s(x):
    return ((pd.to_datetime(x, utc=True) - pd.Timestamp('1970-01-01', tz='UTC')) // pd.Timedelta('1s')).astype(np.int64).values


def horizons(m):
    rows = []
    for lab, off, ttr, clk in HOR:
        base = m.anchor if clk == 'A' else m.closedTime
        x = m[['condition_id']].copy(); x['horizon'] = lab; x['ttr_bucket'] = ttr; x['clock'] = clk
        x['h_ts'] = (base + pd.to_timedelta(off, unit='s'))
        if off > 0:  # in-play only for sports with a game anchor
            x = x[(m.anchor_type == 'game').values]
        rows.append(x)
    hz = pd.concat(rows, ignore_index=True)
    hz = hz[hz.h_ts.notna()].reset_index(drop=True)
    hz['h'] = epoch_s(hz.h_ts)
    return hz


def lookup(codes_s, t_s, p_s, chg_t_s, q_code, q_h):
    """Last point with t <= h within the same code. Arrays sorted by (code, t). Returns idx (-1 if none)."""
    key = (codes_s.astype(np.int64) << 32) | t_s.astype(np.int64)
    qk = (q_code.astype(np.int64) << 32) | q_h.astype(np.int64)
    idx = np.searchsorted(key, qk, side='right') - 1
    ok = (idx >= 0) & (q_code >= 0)
    ok[ok] &= codes_s[idx[ok]] == q_code[ok]
    idx[~ok] = -1
    return idx


def load_series(path, tok_list):
    t = pq.read_table(path)
    t = t.filter(pc.is_in(t['token_id'], value_set=__import__('pyarrow').array(tok_list)))
    enc = pc.dictionary_encode(t['token_id']).combine_chunks()
    codes = enc.indices.to_numpy().astype(np.int64); dic = enc.dictionary.to_pylist()
    tt = t['t'].to_numpy(); pp = t['p'].to_numpy()
    o = np.lexsort((tt, codes)); codes, tt, pp = codes[o], tt[o], pp[o]
    newc = np.r_[True, codes[1:] != codes[:-1]]; chg = newc | np.r_[True, pp[1:] != pp[:-1]]
    pos = np.where(chg, np.arange(len(tt)), 0); np.maximum.accumulate(pos, out=pos); chg_t = tt[pos]
    # count of changes (excluding series start) cumulative, for activity windows
    cum = np.cumsum(chg & ~newc)
    return dict(codes=codes, t=tt, p=pp, chg_t=chg_t, cum=cum, start_t=None, dic={k: i for i, k in enumerate(dic)})


def series_query(S, toks, h, max_stale):
    qc = np.array([S['dic'].get(k, -1) for k in toks], dtype=np.int64)
    idx = lookup(S['codes'], S['t'], S['p'], S['chg_t'], qc, h)
    ok = idx >= 0
    stale = np.full(len(h), np.nan); stale[ok] = h[ok] - S['t'][idx[ok]]
    ok &= stale <= max_stale
    price = np.full(len(h), np.nan); price[ok] = S['p'][idx[ok]]
    lca = np.full(len(h), np.nan); lca[ok] = h[ok] - S['chg_t'][idx[ok]]
    # changes in (h-24h, h]
    idx24 = lookup(S['codes'], S['t'], S['p'], S['chg_t'], qc, h - D)
    n24 = np.full(len(h), np.nan)
    c_now = S['cum'][idx[ok]]; c_then = np.where(idx24[ok] >= 0, S['cum'][np.maximum(idx24[ok], 0)], 0)
    n24[ok] = c_now - c_then
    return price, stale, lca, n24


def build_P():
    s = pd.read_parquet(DER / 'panel_sample.parquet')
    for c in ['endDate', 'closedTime', 'gameStartTime', 'ref_ts']:
        s[c] = pd.to_datetime(s[c], utc=True)
    s['anchor'] = s.endDate; g = (s.category == 'sports') & s.gameStartTime.notna()
    s.loc[g, 'anchor'] = s.loc[g, 'gameStartTime']; s['anchor_type'] = np.where(g, 'game', 'sched')
    s['weight'] = s.sample_weight
    s['closed_missing'] = s.closedTime.isna(); s['closedTime'] = s.closedTime.fillna(s.ref_ts)
    hz = horizons(s).merge(s[['condition_id', 'token_id_0', 'closedTime', 'ref_ts']], on='condition_id')
    toks = hz.token_id_0.values; h = hz.h.values.astype(np.int64)
    M1 = load_series(DER / 'price_series_m1.parquet', list(s.token_id_0))
    p1, st1, lca1, n1 = series_query(M1, toks, h, 900); del M1
    H60 = load_series(DER / 'price_series_h60.parquet', list(s.token_id_0))
    p6, st6, lca6, n6 = series_query(H60, toks, h, 7200); del H60
    use1 = ~np.isnan(p1)
    hz['p0'] = np.where(use1, p1, p6); hz['staleness_s'] = np.where(use1, st1, st6)
    hz['last_change_age_s'] = np.where(use1, lca1, lca6); hz['n_chg_24h'] = np.where(use1, n1, n6)
    hz['src'] = np.where(use1, 'm1', np.where(np.isnan(p6), None, 'h60'))
    ref = epoch_s(hz.ref_ts); close = epoch_s(hz.closedTime)
    hz['null_reason'] = None
    hz.loc[h >= close, 'null_reason'] = 'post_close'
    hz.loc[(h > ref) & hz.null_reason.isna(), 'null_reason'] = 'after_series_end'
    hz.loc[hz.p0.isna() & hz.null_reason.isna(), 'null_reason'] = 'no_series_point'
    hz.loc[hz.null_reason.notna(), ['p0']] = np.nan
    # decision-time volume screen for tape markets
    tp = pd.concat([pd.read_parquet(f, columns=['condition_id', 'price', 'size', 'timestamp']) for f in sorted(glob.glob(str(DER / 'tapes/tape_*.parquet')))])
    tp['notional'] = tp.price * tp['size']; tp = tp.sort_values(['condition_id', 'timestamp'])
    tp['cum'] = tp.groupby('condition_id').notional.cumsum()
    tot = tp.groupby('condition_id').notional.sum()
    hz['in_tape_set'] = hz.condition_id.isin(tot.index)
    vol = s.set_index('condition_id').volumeNum
    out = np.full(len(hz), np.nan)
    cids = tp.condition_id.values; ts = tp.timestamp.values; cum = tp.cum.values
    starts = pd.Series(np.arange(len(tp))).groupby(cids).min(); ends = pd.Series(np.arange(len(tp))).groupby(cids).max()
    m = hz.in_tape_set.values
    for i in np.where(m)[0]:
        cid = hz.condition_id.iat[i]; a, b = starts[cid], ends[cid] + 1
        j = np.searchsorted(ts[a:b], h[i], side='right') - 1
        out[i] = (cum[a + j] if j >= 0 else 0.0) / tot[cid] * vol[cid]
    hz['volnum_at_h_est'] = out; hz['vol_screen_at_h'] = np.where(m, out >= 10000, None)
    hz = hz.drop(columns=['token_id_0', 'closedTime', 'ref_ts']).merge(s[KEEP], on='condition_id')
    hz['sample'] = 'P'
    return hz


def build_W():
    w = pd.read_parquet(DER / 'flb_wide_sample.parquet')
    parts = sorted(glob.glob(str(DER / 'flb_wide_parts/meta_*.parquet')))
    meta = pd.concat([pd.read_parquet(f) for f in parts]); cp = pd.concat([pd.read_parquet(f.replace('meta_', 'cp_')) for f in parts])
    gaps = pd.concat([pd.read_parquet(f.replace('meta_', 'gaps_')) for f in parts])
    w = w[w.condition_id.isin(meta.condition_id)]
    # add artificial gap between req 0 and req 1
    two = meta[meta.req == 1].merge(meta[meta.req == 0][['condition_id', 'last_t']], on='condition_id', suffixes=('', '_0'))
    two = two[two.first_t.notna()]
    gaps = pd.concat([gaps, pd.DataFrame({'condition_id': two.condition_id, 'req': 1, 'gap_start': two.last_t_0.astype(np.int64),
                                          'gap_end': two.first_t.astype(np.int64)})])
    cp = cp.sort_values(['condition_id', 't']).drop_duplicates(['condition_id', 't'], keep='last')
    codes_map = {k: i for i, k in enumerate(w.condition_id)}
    cc = cp.condition_id.map(codes_map).values.astype(np.int64); tt = cp.t.values.astype(np.int64); pp = cp.p.values.astype(np.float64)
    o = np.lexsort((tt, cc)); cc, tt, pp = cc[o], tt[o], pp[o]
    first = np.r_[True, cc[1:] != cc[:-1]]
    cum = np.cumsum(~first)
    hz = horizons(w).merge(w[['condition_id', 'closedTime']], on='condition_id')
    qc = hz.condition_id.map(codes_map).values.astype(np.int64); h = hz.h.values.astype(np.int64)
    idx = lookup(cc, tt, pp, None, qc, h)
    fst = meta.groupby('condition_id').first_t.min(); lst = meta.groupby('condition_id').last_t.max()
    ok = idx >= 0
    p0 = np.full(len(h), np.nan); p0[ok] = pp[idx[ok]]
    lca = np.full(len(h), np.nan); lca[ok] = h[ok] - tt[idx[ok]]
    cens = np.zeros(len(h), bool); cens[ok] = first[idx[ok]]
    idx24 = lookup(cc, tt, pp, None, qc, h - D); n24 = np.full(len(h), np.nan)
    n24[ok] = cum[idx[ok]] - np.where(idx24[ok] >= 0, cum[np.maximum(idx24[ok], 0)], 0)
    hz['p0'] = p0; hz['last_change_age_s'] = lca; hz['change_censored'] = cens; hz['n_chg_24h'] = n24
    hz['src'] = 'f5'
    close = epoch_s(hz.closedTime)
    ft = hz.condition_id.map(fst).values.astype(float); lt = hz.condition_id.map(lst).values.astype(float)
    hz['null_reason'] = None
    hz.loc[h >= close, 'null_reason'] = 'post_close'
    hz.loc[(np.isnan(ft) | (h < ft)) & hz.null_reason.isna(), 'null_reason'] = 'before_series_start'
    hz.loc[(h > lt + 900) & hz.null_reason.isna(), 'null_reason'] = 'after_series_end'
    g = gaps.merge(hz[['condition_id']].reset_index(), on='condition_id')
    gh = h[g['index'].values]
    ing = g['index'].values[(gh > g.gap_start.values + 900) & (gh < g.gap_end.values)]
    hz.loc[hz.index.isin(ing) & hz.null_reason.isna(), 'null_reason'] = 'in_gap'
    hz.loc[hz.p0.isna() & hz.null_reason.isna(), 'null_reason'] = 'no_series_point'
    hz.loc[hz.null_reason.notna(), 'p0'] = np.nan
    hz['staleness_s'] = np.nan; hz['in_tape_set'] = False; hz['volnum_at_h_est'] = np.nan; hz['vol_screen_at_h'] = None
    hz = hz.drop(columns=['closedTime']).merge(w[KEEP], on='condition_id')
    hz['sample'] = 'W'
    return hz


def main(which='both'):
    if which == 'P':
        P = build_P(); P.to_parquet(DER / 'flb_entries_P_tmp.parquet', index=False)
        print(P.groupby(['horizon', 'split']).p0.apply(lambda x: f'{x.notna().sum()}/{len(x)}').unstack().to_string())
        print(P.groupby('null_reason').size().to_string()); return
    P = build_P(); W = build_W()
    E = pd.concat([P, W], ignore_index=True)
    E['outcome0'] = E.outcomes.map(lambda o: str(o[0]) if o is not None and len(o) else None)
    E = E.drop(columns=['outcomes'])
    E['vol_screen_at_h'] = E.vol_screen_at_h.astype(object)
    E.to_parquet(DER / 'flb_entries.parquet', index=False)
    print(E.groupby(['sample', 'horizon', 'split']).p0.apply(lambda x: f'{x.notna().sum()}/{len(x)}').unstack().to_string())
    print(E.groupby(['sample', 'null_reason']).size().to_string())


if __name__ == '__main__':
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else 'both')
