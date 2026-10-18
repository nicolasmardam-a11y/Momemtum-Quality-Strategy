"""AUDIT mean_reversion (auditor 2026-10-18).
1. Re-derive P1 (theta 10c, primary variant, delay 120 s, exit 1 h) entry/exit prints for every trade directly from the raw tapes
   with independent code (not 01_detect.py) and compare q_entry / q_1h / payout with mr_trades.
2. Spot-check 40 random TEST shocks: recompute anchor_last, anchor_med, activity screen and the shock from raw prints.
3. Recompute P1 summaries from mr_returns (gross % / cents, net) with fresh cluster, week and entry-day bootstraps.
4. Zero-cost (gross) significance and an optimistic-cost variant (half the modelled half-spread, no fee) to see whether an
   edge could be hidden by the cost model.
Output: analyses/audit/out/mr_a01.json
"""
from pathlib import Path
import glob, json
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; DER = ROOT / 'data/derived'; OUT = Path(__file__).parent / 'out'


def boot(x, g, B=4000, seed=7, q=(0.0125, 0.025, 0.975, 0.9875)):
    codes, _ = pd.factorize(g); sx = np.bincount(codes, x); sn = np.bincount(codes); n = len(sx)
    rng = np.random.default_rng(seed); est = []
    for b0 in range(0, B, 500):
        idx = rng.integers(0, n, size=(500, n)); est.append(sx[idx].sum(1) / sn[idx].sum(1))
    return np.quantile(np.concatenate(est), q).round(5).tolist()


def main():
    R = pd.read_parquet(DER / 'mr_returns.parquet')
    P1 = R[(R.theta == 0.10) & (R.variant == 'primary') & (R.delay == 120) & (R.exit == '1h') & R.entered.astype(bool)].copy()
    res = {}
    # ---- 3. summaries
    P1['day'] = pd.to_datetime(P1.t_entry, unit='s').dt.strftime('%Y-%m-%d')
    for sp, d in P1.groupby('split_t'):
        r = dict(n=len(d), clusters=int(d.cluster_id.nunique()), gross_pct=round(d.ret_gross.mean(), 5), net_pct=round(d.ret_net.mean(), 5),
                 gross_c=round(100 * d.pnl_gross.mean(), 4), net_c=round(100 * d.pnl_net.mean(), 4),
                 median_net=round(d.ret_net.median(), 4))
        if sp in ('test', 'validation'):
            for col in ('ret_net', 'ret_gross', 'pnl_gross'):
                r[f'ci_{col}_cluster'] = boot(d[col].values, d.cluster_id.values)
                r[f'ci_{col}_week'] = boot(d[col].values, d.week.values)
                r[f'ci_{col}_day'] = boot(d[col].values, d.day.values)
            # optimistic cost: half the modelled half-spread both ways, zero fee
            qe, qx = d.q_entry.values, d.q_x.values
            pe = np.clip(qe + 0.5 * d.hs_e.values, 0.001, 0.999); px = np.where(d.at_res.values, qx, np.clip(qx - 0.5 * d.hs_x.values, 0, 1))
            ro = (px - pe) / pe
            r['net_optimistic_halfhs_nofee'] = round(float(ro.mean()), 5)
            r['ci_optimistic_cluster'] = boot(ro, d.cluster_id.values)
            # winsorised gross % (1% tails) - checks the lottery effect of cheap reversal tokens
            lo_, hi_ = np.quantile(d.ret_gross, [0.01, 0.99])
            r['gross_pct_winsor1'] = round(float(d.ret_gross.clip(lo_, hi_).mean()), 5)
            r['share_q_entry_lt_0p10'] = round(float((d.q_entry < 0.10).mean()), 3)
        res[f'P1|{sp}'] = r
    # ---- 1. independent re-derivation of entry/exit prints from raw tapes
    tp = pd.concat([pd.read_parquet(f, columns=['condition_id', 'outcome_index', 'price', 'timestamp']) for f in sorted(glob.glob(str(DER / 'tapes/tape_*.parquet')))])
    tp = tp[tp.condition_id.isin(set(P1.condition_id))]
    tp['p0'] = np.where(tp.outcome_index == 0, tp.price.astype(float), 1 - tp.price.astype(float))
    tp = tp.sort_values(['condition_id', 'timestamp'], kind='stable')
    G = {k: (v.timestamp.values.astype(np.int64), v.p0.values) for k, v in tp.groupby('condition_id')}
    meta = pd.read_parquet(DER / 'mr_shocks.parquet', columns=['condition_id', 'theta', 'variant', 't_det', 'close_s', 'endDate'])
    meta = meta[(meta.theta == 0.10) & (meta.variant == 'primary')]
    X = P1.merge(meta[['condition_id', 't_det', 'close_s']], on=['condition_id', 't_det'], suffixes=('', '_m'))
    agree_e = agree_x = agree_t = 0; diffs = []
    for r in X.itertuples():
        ts, p0 = G[r.condition_id]
        e = np.searchsorted(ts, r.t_det + 120, 'left')
        te = ts[e]
        # within one second several prints can exist: accept a match on any print of that second (ordering within a second)
        same = p0[(ts == te)]
        conv = (lambda v: v) if r.s == -1 else (lambda v: 1 - v)
        agree_t += int(te == r.t_entry)
        agree_e += int(np.any(np.isclose(conv(same), r.q_entry, atol=1e-9)))
        x = np.searchsorted(ts, te + 3600, 'left')
        if x < len(ts) and ts[x] < r.close_s_m:
            sx = conv(p0[ts == ts[x]]); ok = np.any(np.isclose(sx, r.q_1h, atol=1e-9)) and not r.res_1h
        else:
            ok = bool(r.res_1h) and np.isclose(r.q_1h, r.payout)
        agree_x += int(ok)
        if not ok:
            diffs.append(r.condition_id)
    res['rederive'] = dict(n=len(X), entry_time_match=agree_t, entry_price_match=agree_e, exit_1h_match=agree_x)
    # ---- 2. spot check shocks
    S = pd.read_parquet(DER / 'mr_shocks.parquet')
    S = S[(S.theta == 0.10) & (S.variant == 'primary') & (S.split_t == 'test')].sample(40, random_state=11)
    tp2 = pd.concat([pd.read_parquet(f, columns=['condition_id', 'outcome_index', 'price', 'size', 'timestamp']) for f in sorted(glob.glob(str(DER / 'tapes/tape_*.parquet')))])
    tp2 = tp2[tp2.condition_id.isin(set(S.condition_id))]
    tp2['p0'] = np.where(tp2.outcome_index == 0, tp2.price.astype(float), 1 - tp2.price.astype(float))
    tp2['notional'] = tp2.price.astype(float) * tp2['size'].astype(float)
    ok = 0; bad = []
    for r in S.itertuples():
        g = tp2[tp2.condition_id == r.condition_id].sort_values('timestamp', kind='stable')
        ts = g.timestamp.values; p0 = g.p0.values
        t = r.t_det
        prev = ts <= t - 300
        a_last = p0[prev][-1]
        ref = (ts >= t - 2100) & (ts <= t - 300)
        a_med = np.median(p0[ref])
        n24 = int(((ts >= t - 300 - 86400) & prev).sum()); notb = float(g.notional.values[prev].sum())
        at_t = p0[ts == t]
        cond = any((abs(v - a_last) >= 0.1 - 1e-9) and (abs(v - a_med) >= 0.1 - 1e-9) and np.sign(v - a_last) == np.sign(v - a_med) for v in at_t)
        good = cond and np.isclose(a_last, r.anchor_last) and np.isclose(a_med, r.anchor_med) and ref.sum() >= 3 and n24 >= 20 and notb >= 5000 \
            and t <= pd.Timestamp(r.endDate).timestamp() - 3600
        ok += int(good)
        if not good:
            bad.append(dict(cid=r.condition_id[:12], a_last=a_last, a_last_s=r.anchor_last, a_med=a_med, a_med_s=r.anchor_med, n24=n24, notb=notb))
    res['shock_spotcheck'] = dict(n=len(S), reproduced=ok, failures=bad[:5])
    (OUT / 'mr_a01.json').write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float)[:4000])


if __name__ == '__main__':
    main()
