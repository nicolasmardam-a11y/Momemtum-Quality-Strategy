"""Build the long-format price panel from the pulled /prices-history series (+ tape-based fields) and run the checks.

Series: merged = fidelity-60 points before the fidelity-1 window, then fidelity-1 points (last 72h before ref_ts).
Horizon price = last merged observation with t <= horizon_ts (never after). Recorded per row:
  obs_ts, staleness_s = horizon_ts - obs_ts, src (m1/h60), last_change_ts/age (time since the series value last changed;
  left-censored at the series start), and for tape markets the last taker trade before the horizon and volume known then.
Reference types:
  res   : ref_ts = min(endDate, closedTime); horizons T-30d,7d,3d,1d,12h,6h,1h,15m (as specified; for early-closing
          markets this reference is only known ex post: look-ahead for any rule that conditions on it)
  sched : endDate (the scheduled end, known ex ante); a horizon after closedTime is null (market already resolved)
  game  : gameStartTime -60m/-15m (sports and any market with gameStartTime); null if after closedTime
Outputs: data/derived/price_series_{h60,m1}.parquet, price_panel.parquet, panel_fetch_log.parquet,
         tapes/coverage.parquet, analyses/panel/out/05_checks.json
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
DER = ROOT / 'data/derived'; PARTS = DER / 'panel_parts'; TAPES = DER / 'tapes'
OUT = ROOT / 'analyses/panel/out'
H_RES = {'T-30d': 30 * 86400, 'T-7d': 7 * 86400, 'T-3d': 3 * 86400, 'T-1d': 86400, 'T-12h': 12 * 3600, 'T-6h': 6 * 3600,
         'T-1h': 3600, 'T-15m': 900}
H_GAME = {'G-60m': 3600, 'G-15m': 900}
VOL_SCREEN = 10_000


def load_parts(kind):
    fs = sorted(PARTS.glob(f'{kind}_*.parquet'))
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)


def change_ts(t, p):
    """For each point, the time at which the series last changed value (first point counts as a change)."""
    chg = np.r_[True, np.abs(np.diff(p)) > 1e-12]
    idx = np.maximum.accumulate(np.where(chg, np.arange(len(p)), 0))
    return t[idx]


def main():
    s = pd.read_parquet(DER / 'panel_sample.parquet')
    h60 = load_parts('h60').sort_values(['token_id', 't']).drop_duplicates(['token_id', 't'])
    m1 = load_parts('m1').sort_values(['token_id', 't']).drop_duplicates(['token_id', 't'])
    log = load_parts('log')
    h60.to_parquet(DER / 'price_series_h60.parquet', index=False); m1.to_parquet(DER / 'price_series_m1.parquet', index=False)
    log.to_parquet(DER / 'panel_fetch_log.parquet', index=False)
    checks = {'fetch': {'requests': int(len(log)), 'errors': int(log.error.notna().sum()),
                        'h60_points': int(len(h60)), 'm1_points': int(len(m1))}}
    G60 = {k: g for k, g in h60.groupby('token_id')}; G1 = {k: g for k, g in m1.groupby('token_id')}

    # ---- tapes (liquid subsample) -------------------------------------------------------------------------------------
    cov = pd.concat([pd.read_parquet(f) for f in sorted(TAPES.glob('coverage_*.parquet'))], ignore_index=True)
    sel = pd.read_parquet(DER / 'tape_selection.parquet')
    cov = sel.merge(cov, on='condition_id', how='left'); cov.to_parquet(TAPES / 'coverage.parquet', index=False)
    tp = pd.concat([pd.read_parquet(f, columns=['condition_id', 'token_id', 'price', 'size', 'timestamp'])
                    for f in sorted(TAPES.glob('tape_*.parquet'))], ignore_index=True)
    tok0 = dict(zip(sel.condition_id, sel.token_id_0))
    tp['p0'] = np.where(tp.token_id.values == tp.condition_id.map(tok0).values, tp.price, 1 - tp.price)
    tp['notional'] = tp.price * tp['size']
    tp = tp.sort_values(['condition_id', 'timestamp'])
    T = {k: (g.timestamp.values, g.p0.values, np.cumsum(g.notional.values)) for k, g in tp.groupby('condition_id')}
    covd = cov.set_index('condition_id')

    # ---- panel --------------------------------------------------------------------------------------------------------
    rows, fid_cmp, align = [], [], []
    rng = np.random.default_rng(1)
    for r in s.itertuples():
        a = G60.get(r.token_id_0); b = G1.get(r.token_id_0)
        m1_start = int(r.ref_ts.timestamp()) - 72 * 3600
        parts = []
        if a is not None:
            parts.append(a[a.t < m1_start].assign(src='h60'))
        if b is not None:
            parts.append(b.assign(src='m1'))
        ser = pd.concat(parts) if parts else pd.DataFrame(columns=['t', 'p', 'src'])
        t = ser.t.values.astype('int64'); p = ser.p.values.astype(float); src = ser.src.values
        ct = change_ts(t, p) if len(t) else t
        # fidelity consistency: h60 points inside the m1 window vs m1 at the same minute / end of that hour
        if a is not None and b is not None and len(b) > 10:
            aa = a[a.t >= m1_start + 60]
            if len(aa):
                bt, bp = b.t.values, b.p.values
                i0 = np.searchsorted(bt, aa.t.values, 'right') - 1; i1 = np.searchsorted(bt, aa.t.values + 3540, 'right') - 1
                ok = i0 >= 0
                fid_cmp.append(pd.DataFrame({'d_same': np.abs(aa.p.values[ok] - bp[i0[ok]]),
                                             'd_end': np.abs(aa.p.values[ok] - bp[i1[ok]])}))
        tape = T.get(r.condition_id)
        if tape is not None and b is not None and len(b) > 30:
            tt, tpx, _ = tape
            pts = b.sample(min(200, len(b)), random_state=int(rng.integers(1e9)))
            d = {'condition_id': r.condition_id}
            for lag in (-600, -300, -120, -60, 0, 60, 120, 300, 600):
                j = np.searchsorted(tt, pts.t.values + lag, 'right') - 1
                okj = j >= 0
                d[lag] = float(np.median(np.abs(pts.p.values[okj] - tpx[j[okj]]))) if okj.any() else np.nan
                d[f'mean_{lag}'] = float(np.mean(np.abs(pts.p.values[okj] - tpx[j[okj]]))) if okj.any() else np.nan
            # post-hoc event test: when the minute series changes at t, are there trades just before t or just after?
            bt, bp = b.t.values, b.p.values
            ch = bt[1:][np.abs(np.diff(bp)) > 1e-12]
            if len(ch):
                nb = np.searchsorted(tt, ch, 'right') - np.searchsorted(tt, ch - 60, 'right')
                na = np.searchsorted(tt, ch + 60, 'right') - np.searchsorted(tt, ch, 'right')
                d.update(ev_n=len(ch), ev_trade_before=float((nb > 0).mean()), ev_trade_after=float((na > 0).mean()))
            align.append(d)
        refs = [('res', r.ref_ts, H_RES), ('sched', r.endDate, H_RES)]
        if pd.notna(r.gameStartTime):
            refs.append(('game', r.gameStartTime, H_GAME))
        ref_s = int(r.ref_ts.timestamp())
        closed = int((r.closedTime if pd.notna(r.closedTime) else r.ref_ts).timestamp())  # closedTime missing -> endDate
        tc = covd.loc[r.condition_id] if r.condition_id in covd.index else None
        for rt, base, hs in refs:
            base_s = int(base.timestamp())
            for lab, off in hs.items():
                h = base_s - off
                row = {'condition_id': r.condition_id, 'ref_type': rt, 'horizon': lab, 'horizon_ts': h}
                if h > closed:
                    row['null_reason'] = 'post_close'; rows.append(row); continue
                if h > ref_s:  # series fetched only up to ref_ts (only game horizons when endDate < gameStartTime)
                    row['null_reason'] = 'after_series_end'; rows.append(row); continue
                i = np.searchsorted(t, h, 'right') - 1
                if i < 0:
                    row['null_reason'] = 'no_obs_before' if len(t) else 'no_series'; rows.append(row); continue
                row.update(price=p[i], obs_ts=int(t[i]), src=src[i], last_change_ts=int(ct[i]),
                           change_censored=bool(ct[i] == t[0]))
                if tape is not None:
                    tt, tpx, cn = tape
                    j = np.searchsorted(tt, h, 'right') - 1
                    tot = cn[-1] if len(cn) else 0.0
                    before = cn[j] if j >= 0 else 0.0
                    row.update(last_trade_ts=int(tt[j]) if j >= 0 else None, last_trade_p0=float(tpx[j]) if j >= 0 else None,
                               tape_notional_before=float(before), tape_notional_total=float(tot))
                    trunc = bool(tc['truncated']) if tc is not None else True
                    if not trunc and tot > 0:
                        row['volnum_at_h_est'] = r.volumeNum * before / tot
                        row['vol_screen_at_h'] = row['volnum_at_h_est'] >= VOL_SCREEN
                    elif trunc and j >= 0 and before > 0:
                        row['volnum_at_h_est'] = np.nan  # the oldest part of the tape is missing
                        row['vol_screen_at_h'] = True if before >= VOL_SCREEN else None  # lower bound only
                rows.append(row)
    P = pd.DataFrame(rows)
    for c in ('horizon_ts', 'obs_ts', 'last_change_ts', 'last_trade_ts'):
        P[c] = pd.to_datetime(P[c], unit='s', utc=True)
    P['staleness_s'] = (P.horizon_ts - P.obs_ts).dt.total_seconds()
    P['last_change_age_s'] = (P.horizon_ts - P.last_change_ts).dt.total_seconds()
    P['last_trade_age_s'] = (P.horizon_ts - P.last_trade_ts).dt.total_seconds()
    meta = s[['condition_id', 'token_id_0', 'event_id', 'cluster_id', 'cluster_week', 'split', 'category', 'end_quarter',
              'structure', 'negRisk', 'y0', 'clean_resolution', 'early_close', 'sample_weight', 'volumeNum']]
    P = P.merge(meta, on='condition_id', how='left')
    P['in_tape_set'] = P.condition_id.isin(set(sel.condition_id[sel.set == 'liquid']))
    P.to_parquet(DER / 'price_panel.parquet', index=False)

    # ---- checks -------------------------------------------------------------------------------------------------------
    has60 = s.token_id_0.isin(G60.keys()); has1 = s.token_id_0.isin(G1.keys())
    res = P[P.ref_type == 'res']
    piv = res.pivot_table(index='condition_id', columns='horizon', values='price', aggfunc='first')
    both = piv[['T-1d', 'T-1h']].notna().all(axis=1).reindex(s.condition_id).fillna(False)
    checks['coverage'] = {'n_sample': int(len(s)), 'h60_nonempty': float(has60.mean()), 'm1_nonempty': float(has1.mean()),
                          'res_T-1d_and_T-1h_priced': float(both.mean()),
                          'by_split_both': both.groupby(s.split.values).mean().round(4).to_dict(),
                          'res_priced_share_by_horizon': res.groupby('horizon').price.apply(lambda x: x.notna().mean()).round(4).to_dict()}
    checks['lookahead'] = {'rows_obs_after_horizon': int((P.obs_ts > P.horizon_ts).sum()),
                           'rows_priced_after_close': int(((P.null_reason == 'post_close') & P.price.notna()).sum())}
    F = pd.concat(fid_cmp) if fid_cmp else pd.DataFrame(columns=['d_same', 'd_end'])
    checks['fidelity'] = {'n': int(len(F)), 'same_minute_within_0.5c': float((F.d_same <= 0.005).mean()),
                          'end_of_hour_within_0.5c': float((F.d_end <= 0.005).mean()),
                          'same_minute_exact': float((F.d_same < 1e-9).mean())}
    A = pd.DataFrame(align)
    lags = (-600, -300, -120, -60, 0, 60, 120, 300, 600)
    checks['alignment'] = {'n_markets': int(len(A)), 'median_abs_gap_by_lag_s': {str(k): float(A[k].median()) for k in lags},
                           'mean_abs_gap_by_lag_s (post hoc)': {str(k): float(A[f'mean_{k}'].mean()) for k in lags},
                           'change_events (post hoc)': {'n_markets': int(A.ev_n.notna().sum()), 'n_events': int(A.ev_n.sum()),
                                                        'share_with_trade_in_prior_60s': float((A.ev_trade_before * A.ev_n).sum() / A.ev_n.sum()),
                                                        'share_with_trade_in_next_60s': float((A.ev_trade_after * A.ev_n).sum() / A.ev_n.sum())}}
    tc_l = cov[cov.set == 'liquid']
    ratio = (tc_l.notional / tc_l.volumeNum)[~tc_l.truncated.astype(bool)]
    aud = cov[cov.set == 'nullvol_audit']
    checks['tapes'] = {'markets': int(len(tc_l)), 'rows': int(tc_l.n_rows.sum()), 'pages': int(tc_l.n_pages.sum()),
                       'errors': int(tc_l.error.notna().sum()), 'truncated': int(tc_l.truncated.sum()),
                       'complete_share': float((~tc_l.truncated.astype(bool) & tc_l.error.isna()).mean()),
                       'empty_pages_with_more': int(tc_l.empty_pages_with_more.sum()),
                       'nonmonotone_steps': int(tc_l.nonmonotone.fillna(0).sum()), 'dup_rows': int(tc_l.dup_rows.fillna(0).sum()),
                       'ratio_tape_notional_to_volumeNum_q': ratio.quantile([.1, .25, .5, .75, .9]).round(3).to_dict(),
                       'nullvol_audit': {'n': int(len(aud)), 'with_trades': int((aud.n_rows > 0).sum()),
                                         'tape_notional_ge_10k': int((aud.notional >= 1e4).sum()),
                                         'tape_notional_ge_10k_x_median_ratio': int((aud.notional >= 1e4 * ratio.median()).sum()),
                                         'notional_q': aud.notional.fillna(0).quantile([.5, .9, .99]).round(0).to_dict()}}
    json.dump(checks, open(OUT / '05_checks.json', 'w'), indent=1, default=str)
    print(json.dumps(checks, indent=1, default=str)[:4000])


if __name__ == '__main__':
    main()
