"""Historical effective half-spread paid by takers, from the trade tapes and the fidelity-1 series (last 72h before ref_ts).

For each taker trade in the liquid tape set with a minute-series point at or before it (same token pair, <= 60 s old):
  token-0 mid m = series value at the last minute <= trade ts; the traded token's mid is m (token 0) or 1 - m (token 1).
  effective half-spread = (price - token mid) for a taker BUY, (token mid - price) for a taker SELL.
This measures what takers actually paid relative to the series price in each period (train/validation/test), so it does
not rely on today's books. Caveats: the series point is up to 60 s older than the trade; when the quoted spread exceeds
10c the series shows the last trade instead of the mid; trades are taker-chosen (selection), sizes are the sizes takers
chose. Buckets as in spread_model.parquet (price of the traded token, right-closed TTR = ref_ts - trade time).
Output: data/derived/effective_spread_hist.parquet, analyses/panel/out/07_effective_spread.json
"""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; DER = ROOT / 'data/derived'
PB_EDGES = [0, .02, .05, .15, .35, .65, .85, .95, .98, 1.0001]
PB_LABELS = ['<2c', '2-5c', '5-15c', '15-35c', '35-65c', '65-85c', '85-95c', '95-98c', '>98c']
TTR_EDGES = [0, 1, 6, 24, 72]; TTR_LABELS = ['<=1h', '1-6h', '6-24h', '1-3d']
NB_EDGES = [0, 100, 1000, 10000, np.inf]; NB_LABELS = ['<$100', '$100-1k', '$1k-10k', '>=$10k']


def main():
    s = pd.read_parquet(DER / 'panel_sample.parquet', columns=['condition_id', 'token_id_0', 'ref_ts', 'gameStartTime', 'split',
                                                                'category', 'cluster_id'])
    sel = pd.read_parquet(DER / 'tape_selection.parquet'); liquid = set(sel.condition_id[sel.set == 'liquid'])
    s = s[s.condition_id.isin(liquid)]
    m1 = pd.read_parquet(DER / 'price_series_m1.parquet', filters=[('token_id', 'in', list(s.token_id_0))])
    M = {k: (g.t.values, g.p.values) for k, g in m1.groupby('token_id')}
    out = []
    for f in sorted((DER / 'tapes').glob('tape_*.parquet')):
        T = pd.read_parquet(f, columns=['condition_id', 'token_id', 'side', 'price', 'size', 'timestamp'])
        T = T[T.condition_id.isin(liquid)].merge(s, on='condition_id')
        T['ref_s'] = (T.ref_ts - pd.Timestamp(0, tz='UTC')).dt.total_seconds().astype('int64')
        T = T[(T.timestamp <= T.ref_s) & (T.timestamp > T.ref_s - 72 * 3600)]
        for tok, g in T.groupby('token_id_0'):
            if tok not in M:
                continue
            mt, mp = M[tok]
            i = np.searchsorted(mt, g.timestamp.values, 'right') - 1
            ok = (i >= 0) & (g.timestamp.values - mt[np.clip(i, 0, None)] <= 60)
            g = g[ok].copy(); m = mp[i[ok]]
            is0 = g.token_id.values == tok
            g['tok_mid'] = np.where(is0, m, 1 - m)
            sign = np.where(g.side.values == 'BUY', 1.0, -1.0)
            g['eff_half'] = sign * (g.price.values - g.tok_mid.values)
            out.append(g)
    E = pd.concat(out, ignore_index=True)
    E['notional'] = E.price * E['size']
    E['ttr_h'] = (E.ref_s - E.timestamp) / 3600
    E['ttr_bucket'] = pd.cut(E.ttr_h, TTR_EDGES, labels=TTR_LABELS, right=True, include_lowest=True).astype(object)
    gst = (E.gameStartTime - pd.Timestamp(0, tz='UTC')).dt.total_seconds()
    E.loc[E.gameStartTime.notna() & (E.timestamp >= gst) & E.category.eq('sports'), 'ttr_bucket'] = 'in_play'
    E['pbucket'] = pd.cut(E.tok_mid, PB_EDGES, labels=PB_LABELS, right=False).astype(object)
    E['nbucket'] = pd.cut(E.notional, NB_EDGES, labels=NB_LABELS, right=False).astype(object)

    def agg(g):
        w = g.notional
        return pd.Series({'n_trades': len(g), 'n_markets': g.condition_id.nunique(), 'n_clusters': g.cluster_id.nunique(),
                          'eff_half_med': g.eff_half.median(), 'eff_half_mean': g.eff_half.mean(),
                          'eff_half_wmean': float((g.eff_half * w).sum() / w.sum()) if w.sum() > 0 else np.nan,
                          'eff_half_p75': g.eff_half.quantile(.75), 'share_negative': float((g.eff_half < 0).mean()),
                          'notional_med': w.median()})
    rows = []
    for lvl, keys in [('H0', ['split', 'category', 'pbucket', 'ttr_bucket']), ('H1', ['split', 'pbucket', 'ttr_bucket']),
                      ('H2', ['split', 'category', 'pbucket']), ('H3', ['split', 'pbucket']), ('H4', ['split']),
                      ('HS', ['split', 'pbucket', 'nbucket'])]:
        for k, g in E.groupby(keys):
            rows.append({'level': lvl, **dict(zip(keys, k)), **agg(g).to_dict()})
    R = pd.DataFrame(rows)
    for k in ('category', 'pbucket', 'ttr_bucket', 'nbucket'):
        R[k] = R[k].fillna('ALL')
    R.to_parquet(DER / 'effective_spread_hist.parquet', index=False)
    summ = {'n_trades': int(len(E)), 'n_markets': int(E.condition_id.nunique()),
            'by_split': R[R.level == 'H4'].set_index('split')[['n_trades', 'eff_half_med', 'eff_half_mean', 'eff_half_wmean']].round(4).to_dict('index')}
    json.dump(summ, open(ROOT / 'analyses/panel/out/07_effective_spread.json', 'w'), indent=1, default=str)
    print(json.dumps(summ, default=str))
    pd.set_option('display.width', 250)
    for v in ('eff_half_med', 'eff_half_mean'):
        print(v); print(R[R.level == 'H3'].pivot(index='split', columns='pbucket', values=v).round(4).to_string())
    print(R[(R.level == 'H1') & (R.split == 'test')].pivot(index='ttr_bucket', columns='pbucket', values='eff_half_mean').round(4).to_string())
    print(R[(R.level == 'HS') & (R.split == 'test')].pivot(index='nbucket', columns='pbucket', values='eff_half_mean').round(4).to_string())


if __name__ == '__main__':
    main()
