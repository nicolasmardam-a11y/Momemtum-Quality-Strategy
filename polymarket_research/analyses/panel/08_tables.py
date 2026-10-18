"""Print the markdown tables used in notes/strategies/panel.md section 5 (spread model and historical effective spread)."""
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
PB = ['<2c', '2-5c', '5-15c', '15-35c', '35-65c', '65-85c', '85-95c', '95-98c', '>98c']
TTR = ['<=1h', '1-6h', '6-24h', '1-3d', '3-7d', '7-30d', '>30d', 'in_play', 'past_end']


def md(df, fmt='{:.4f}'):
    cols = list(df.columns)
    out = ['| ' + ' | '.join([str(df.index.name or '')] + [str(c) for c in cols]) + ' |', '|' + '---|' * (len(cols) + 1)]
    for i, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append('' if pd.isna(v) else (fmt.format(v) if isinstance(v, float) else str(v)))
        out.append('| ' + ' | '.join([str(i)] + cells) + ' |')
    return '\n'.join(out)


M = pd.read_parquet(ROOT / 'data/derived/spread_model.parquet')
V = M[M.book_universe == 'vol10k']
l3 = V[V.level.isin(['L3', 'L4'])].set_index('pbucket').reindex(PB + ['ALL'])
cols = {'n_markets_two_sided': 'markets', 'half_spread_med': 'half-spread med', 'half_spread_p75': 'p75',
        'slip_buy_500_med': 'buy $500', 'slip_buy_2500_med': 'buy $2.5k', 'slip_buy_10000_med': 'buy $10k',
        'slip_sell_500_med': 'sell $500', 'slip_sell_2500_med': 'sell $2.5k', 'fillable_buy_2500': 'fillable buy $2.5k',
        'fillable_buy_10000': 'fillable buy $10k', 'depth_ask_2c_med': 'ask depth 2c $', 'share_spread_gt10c': 'spread>10c'}
t = l3[list(cols)].rename(columns=cols); t.index.name = 'token price'
t['markets'] = t['markets'].astype('Int64').astype(str); t['ask depth 2c $'] = t['ask depth 2c $'].round(0)
print(md(t)); print()
for v, lab in (('half_spread_med', 'half-spread median'), ('slip_buy_2500_med', 'buy $2.5k slippage median'), ('n_markets_two_sided', 'markets')):
    p = V[V.level == 'L2'].pivot(index='ttr_bucket', columns='pbucket', values=v).reindex(index=TTR, columns=PB)
    p.index.name = lab
    print(md(p, '{:.0f}' if v.startswith('n_') else '{:.4f}')); print()
p = V[V.level == 'V2'].pivot(index='vtier', columns='pbucket', values='slip_buy_2500_med').reindex(columns=PB)
p.index.name = 'buy $2.5k by volume tier'; print(md(p)); print()
A = M[(M.book_universe == 'allopen') & M.level.isin(['L3', 'L4'])].set_index('pbucket').reindex(PB + ['ALL'])
a = A[['n_markets_two_sided', 'half_spread_med', 'slip_buy_2500_med', 'fillable_buy_2500', 'share_spread_gt10c']]
a.index.name = 'all-open token price'; print(md(a)); print()
E = pd.read_parquet(ROOT / 'data/derived/effective_spread_hist.parquet')
for v in ('eff_half_med', 'eff_half_mean'):
    p = E[E.level == 'H3'].pivot(index='split', columns='pbucket', values=v).reindex(index=['train', 'validation', 'test'], columns=PB)
    p.index.name = v; print(md(p)); print()
p = E[(E.level == 'H1') & (E.split == 'test')].pivot(index='ttr_bucket', columns='pbucket', values='eff_half_med').reindex(
    index=['<=1h', '1-6h', '6-24h', '1-3d', 'in_play'], columns=PB)
p.index.name = 'TEST eff_half_med by TTR'; print(md(p)); print()
p = E[(E.level == 'H2') & (E.split == 'test')].pivot(index='category', columns='pbucket', values='eff_half_med').reindex(columns=PB)
p.index.name = 'TEST eff_half_med by category'; print(md(p))
