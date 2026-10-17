"""Spread/depth model from live CLOB order books (2026-10-17), applied to history as an ASSUMPTION.

Inputs: book_levels_2026-10-17_{vol10k,allopen}_{r2,r3}.parquet (04b_resnap_books.py, full levels) and, for the
stability check, the round-1 metrics in book_snapshots_2026-10-17_{universe}.parquet (04_books.py).
Each token_id_0 book gives two outcome sides: tok0 as served, and tok1 as its mirror (tok1 asks = 1 - tok0 bids,
tok1 bids = 1 - tok0 asks, same share sizes; verified 97-100% by 04_books.py). Price buckets use that side's own mid,
so buying a 2c long shot and buying a 98c favourite fall in different cells.
Cost is measured from the book midpoint, which is what the /prices-history series shows when the spread is <= 10c
(panel.md): a buy of $X fills at mid + slip_buy_X, a sell at mid - slip_sell_X (price units, 1.0 = $1/share).
Slippage medians use only books that can fill the whole size; `fillable_*` gives that share. Fees are NOT included.
TTR buckets are right-closed so the panel horizons map cleanly: T-15m,T-1h -> '<=1h'; T-6h -> '1-6h';
T-12h,T-1d -> '6-24h'; T-3d -> '1-3d'; T-7d -> '3-7d'; T-30d -> '7-30d'. Sports use time to gameStartTime
('in_play' after it); other markets use endDate ('past_end' if the end has passed and the market is still open).
Levels: L0 cat x pbucket x ttr, L1 cat x pbucket, L2 pbucket x ttr, L3 pbucket, L4 all; vol10k also V1 vtier x pbucket x ttr,
V2 vtier x pbucket (vtier = Gamma volumeNum to date). Use the finest level with n_markets >= 20.
Outputs: data/derived/book_sides_2026-10-17.parquet (one row per book side and round), data/derived/spread_model.parquet,
analyses/panel/out/06_spread_model.json
"""
import json
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import spearmanr
ROOT = Path(__file__).resolve().parents[2]
SIZES = (500, 2500, 10000)
EDGES = [0, 1, 6, 24, 72, 168, 720, np.inf]
LABELS = ['<=1h', '1-6h', '6-24h', '1-3d', '3-7d', '7-30d', '>30d']
PB_EDGES = [0, .02, .05, .15, .35, .65, .85, .95, .98, 1.0001]
PB_LABELS = ['<2c', '2-5c', '5-15c', '15-35c', '35-65c', '65-85c', '85-95c', '95-98c', '>98c']


def walk(levels, usd):
    got_usd = got_sh = 0.0
    for p, s in levels:
        take = min(s, (usd - got_usd) / p) if p > 0 else s
        got_usd += take * p; got_sh += take
        if got_usd >= usd - 1e-9:
            break
    return (got_usd / got_sh if got_sh > 0 else np.nan), got_usd / usd


def side_metrics(bids, asks):
    d = {'two_sided': bool(bids and asks), 'n_bid_levels': len(bids), 'n_ask_levels': len(asks)}
    if not d['two_sided']:
        return d
    bb, ba = bids[0][0], asks[0][0]; mid = (bb + ba) / 2
    d.update(best_bid=bb, best_ask=ba, mid=mid, half_spread=(ba - bb) / 2)
    for x in SIZES:
        vb, fb = walk(asks, x); vs, fs = walk(bids, x)
        d[f'slip_buy_{x}'] = vb - mid; d[f'fill_buy_{x}'] = fb; d[f'slip_sell_{x}'] = mid - vs; d[f'fill_sell_{x}'] = fs
    for c in (2, 5):
        d[f'depth_bid_{c}c'] = sum(p * s for p, s in bids if p >= mid - c / 100 - 1e-9)
        d[f'depth_ask_{c}c'] = sum(p * s for p, s in asks if p <= mid + c / 100 + 1e-9)
    return d


def sides_table():
    rows = []
    for f in sorted(ROOT.glob('data/derived/book_levels_2026-10-17_*_r*.parquet')):
        L = pd.read_parquet(f)
        for r in L.itertuples():
            if not isinstance(r.bids_json, str):
                continue
            bids = [tuple(x) for x in json.loads(r.bids_json)]; asks = [tuple(x) for x in json.loads(r.asks_json)]
            base = {'book_universe': r.book_universe, 'round': r.round, 'snapshot_utc': r.snapshot_utc,
                    'conditionId': r.conditionId, 'category': r.category, 'ttr_ref': r.ttr_ref, 'ttr_h': r.ttr_h,
                    'game_h': r.game_h, 'tick_size': r.tick_size, 'negRisk': r.negRisk,
                    'volumeNum': getattr(r, 'volumeNum', np.nan)}
            rows.append({**base, 'side': 'tok0', **side_metrics(bids, asks)})
            rows.append({**base, 'side': 'tok1', **side_metrics([(1 - p, s) for p, s in asks], [(1 - p, s) for p, s in bids])})
    b = pd.DataFrame(rows)
    use_game = b.ttr_ref.eq('game_start')
    h = np.where(use_game, b.game_h, b.ttr_h)
    lab = pd.cut(pd.Series(h, index=b.index), EDGES, labels=LABELS, right=True, include_lowest=True).astype(object)
    lab[use_game & (b.game_h <= 0)] = 'in_play'; lab[~use_game & (b.ttr_h <= 0)] = 'past_end'
    b['ttr_bucket'] = lab
    b['pbucket'] = pd.cut(b.mid, PB_EDGES, labels=PB_LABELS, right=False).astype(object)
    b['pbucket'] = b.pbucket.fillna('no_mid')
    b['vtier'] = pd.cut(b.volumeNum, [1e4, 1e5, 1e6, np.inf], labels=['10k-100k', '100k-1M', '>=1M'], right=False).astype(object)
    b['wide_gt10c'] = (2 * b.half_spread) > 0.10  # series shows last trade, not mid, when the spread exceeds 10c
    return b


def stats(g):
    t = g[g.two_sided.fillna(False).astype(bool)]
    d = {'n_obs': len(g), 'n_markets': g.conditionId.nunique(), 'n_two_sided': len(t),
         'n_markets_two_sided': t.conditionId.nunique(), 'share_two_sided': len(t) / len(g) if len(g) else np.nan}
    if len(t):
        hs = t.half_spread
        d.update(half_spread_med=hs.median(), half_spread_mean=hs.mean(), half_spread_p75=hs.quantile(.75),
                 half_spread_p90=hs.quantile(.9), share_spread_gt10c=t.wide_gt10c.mean(), tick_med=t.tick_size.median())
        for x in SIZES:
            for sd in ('buy', 'sell'):
                ok = t[f'fill_{sd}_{x}'] >= 0.999
                d[f'fillable_{sd}_{x}'] = ok.mean()
                d[f'slip_{sd}_{x}_med'] = t.loc[ok, f'slip_{sd}_{x}'].median()
                d[f'slip_{sd}_{x}_p75'] = t.loc[ok, f'slip_{sd}_{x}'].quantile(.75)
        for c in (2, 5):
            d[f'depth_bid_{c}c_med'] = t[f'depth_bid_{c}c'].median(); d[f'depth_ask_{c}c_med'] = t[f'depth_ask_{c}c'].median()
    return d


def model(b, levels):
    out = []
    for lvl, keys in levels:
        if keys:
            g = pd.DataFrame([{**dict(zip(keys, k if isinstance(k, tuple) else (k,))), **stats(gg)} for k, gg in b.groupby(keys)])
        else:
            g = pd.DataFrame([stats(b)])
        g['level'] = lvl
        out.append(g)
    return pd.concat(out, ignore_index=True)


def main():
    b = sides_table()
    b.to_parquet(ROOT / 'data/derived/book_sides_2026-10-17.parquet', index=False)
    base = [('L0', ['category', 'pbucket', 'ttr_bucket']), ('L1', ['category', 'pbucket']),
            ('L2', ['pbucket', 'ttr_bucket']), ('L3', ['pbucket']), ('L4', [])]
    Ms = []
    for tag, g in b.groupby('book_universe'):
        lv = base + ([('V1', ['vtier', 'pbucket', 'ttr_bucket']), ('V2', ['vtier', 'pbucket'])] if tag == 'vol10k' else [])
        M = model(g, lv); M['book_universe'] = tag; Ms.append(M)
    M = pd.concat(Ms, ignore_index=True)
    for k in ('category', 'pbucket', 'ttr_bucket', 'vtier'):
        M[k] = M[k].fillna('ALL')
    M['rounds'] = ','.join(sorted(b['round'].unique()))
    key = ['book_universe', 'level', 'category', 'vtier', 'pbucket', 'ttr_bucket']
    M = M[key + [c for c in M.columns if c not in key]]
    M.to_parquet(ROOT / 'data/derived/spread_model.parquet', index=False)
    # stability: round-1 token_id_0 half-spread (04_books.py) vs round-2 for the same markets
    stab = {}
    for tag in ('vol10k', 'allopen'):
        r1 = pd.read_parquet(ROOT / f'data/derived/book_snapshots_2026-10-17_{tag}.parquet', columns=['conditionId', 'half_spread', 'mid'])
        r2 = b[(b.book_universe == tag) & (b['round'] == 'r2') & (b.side == 'tok0')][['conditionId', 'half_spread', 'mid']]
        j = r1.merge(r2, on='conditionId', suffixes=('_r1', '_r2')).dropna()
        stab[tag] = {'n': int(len(j)), 'spearman_half_spread': float(spearmanr(j.half_spread_r1, j.half_spread_r2)[0]),
                     'median_abs_change_half_spread': float((j.half_spread_r1 - j.half_spread_r2).abs().median()),
                     'share_half_spread_unchanged': float(((j.half_spread_r1 - j.half_spread_r2).abs() < 1e-9).mean()),
                     'median_abs_change_mid': float((j.mid_r1 - j.mid_r2).abs().median())}
    summ = {'n_side_rows': int(len(b)), 'by_universe_round': {f'{k[0]}_{k[1]}': int(v) for k, v in b.groupby(['book_universe', 'round']).conditionId.nunique().items()},
            'two_sided_share': b.groupby('book_universe').two_sided.mean().round(3).to_dict(), 'stability_r1_r2': stab}
    json.dump(summ, open(ROOT / 'analyses/panel/out/06_spread_model.json', 'w'), indent=1, default=str)
    print(json.dumps(summ, default=str))
    pd.set_option('display.width', 250)
    P = M[M.book_universe == 'vol10k']
    show = ['n_markets_two_sided', 'half_spread_med', 'half_spread_p75', 'slip_buy_500_med', 'slip_buy_2500_med',
            'slip_buy_10000_med', 'fillable_buy_2500', 'fillable_buy_10000', 'depth_ask_2c_med', 'share_spread_gt10c']
    print(P[P.level.isin(['L3', 'L4'])].set_index('pbucket')[show].round(4).to_string())
    for v in ('half_spread_med', 'slip_buy_500_med', 'n_markets_two_sided'):
        print(v); print(P[P.level == 'L2'].pivot(index='ttr_bucket', columns='pbucket', values=v).round(4).to_string())
    print(P[P.level == 'V2'].pivot(index='vtier', columns='pbucket', values='slip_buy_2500_med').round(4).to_string())
    for tag in ('vol10k', 'allopen'):
        l0 = M[(M.book_universe == tag) & (M.level == 'L0')]
        print(tag, f"L0 cells {len(l0)}, with n_markets_two_sided>=20: {int((l0.n_markets_two_sided >= 20).sum())}")


if __name__ == '__main__':
    main()
