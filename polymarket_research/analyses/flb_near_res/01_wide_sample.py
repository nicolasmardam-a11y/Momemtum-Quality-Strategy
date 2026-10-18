"""Volume-free stratified sample W for families E/H (pre-registered in notes/strategies/flb_near_resolution.md 0.2).

Eligible: universe markets with n_outcomes == 2, enableOrderBook, traded proxy, resolution winner/split_50_50, token_id_0,
not in the stage-2 panel sample. Allocation per split: TEST 20,000 / validation 6,000 / train 4,000, proportional to
sqrt(N_category) with floor min(N, 150) and cap N. Uniform draw within cell, seed 20261018. weight = N_cell / n_cell.
Output: data/derived/flb_wide_sample.parquet
"""
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; DER = ROOT / 'data/derived'
BUDGET = {'test': 20000, 'validation': 6000, 'train': 4000}
COLS = ['condition_id', 'question', 'slug', 'outcomes', 'token_id_0', 'token_id_1', 'n_outcomes', 'resolution', 'winner_idx',
        'enableOrderBook', 'traded', 'startDate', 'createdAt', 'endDate', 'closedTime', 'gameStartTime', 'sportsMarketType',
        'category', 'split', 'end_quarter', 'event_id', 'cluster_id', 'cluster_week', 'structure', 'negRisk', 'volumeNum',
        'feesEnabled', 'feeType', 'fee_rate', 'fee_exponent', 'orderPriceMinTickSize', 'secondsDelay', 'has_disputed',
        'multi_proposal', 'settle_lag_h', 'settle_lag_game_h', 'umaResolutionStatus']


def alloc(n_by_cat, budget):
    s = np.sqrt(n_by_cat.astype(float)); a = np.minimum(n_by_cat, np.maximum(np.minimum(n_by_cat, 150), np.floor(budget * s / s.sum())))
    for _ in range(50):  # redistribute leftover budget to uncapped cells
        left = budget - a.sum()
        if left <= 0: break
        room = (n_by_cat - a) > 0
        if not room.any(): break
        add = np.floor(left * s[room] / s[room].sum()).clip(lower=1)
        a[room] = np.minimum(n_by_cat[room], a[room] + add)
    return a.astype(int)


def main():
    import pyarrow.dataset as ds
    d = ds.dataset(DER / 'markets_resolved.parquet')
    filt = ((ds.field('n_outcomes') == 2) & (ds.field('enableOrderBook') == True) & (ds.field('traded') == True)
            & ds.field('resolution').isin(['winner', 'split_50_50']))
    light = ['condition_id', 'category', 'split', 'token_id_0', 'closedTime', 'endDate']
    m = d.to_table(columns=light, filter=filt).to_pandas()
    panel = set(pd.read_parquet(DER / 'panel_sample.parquet', columns=['condition_id']).condition_id)
    e = m[m.token_id_0.notna() & ~m.condition_id.isin(panel) & m.closedTime.notna() & m.endDate.notna()].copy()
    rng = np.random.default_rng(20261018); out = []
    for sp, b in BUDGET.items():
        x = e[e.split == sp]; n = x.groupby('category').size(); a = alloc(n, b)
        for cat, k in a.items():
            cell = x[x.category == cat]; idx = rng.choice(len(cell), size=k, replace=False)
            s = cell.iloc[np.sort(idx)].copy(); s['N_cell'] = len(cell); s['n_cell'] = k; s['weight'] = len(cell) / k
            out.append(s)
    w = pd.concat(out, ignore_index=True)[['condition_id', 'N_cell', 'n_cell', 'weight']]
    full = d.to_table(columns=COLS, filter=filt & ds.field('condition_id').isin(list(w.condition_id))).to_pandas()
    w = w.merge(full, on='condition_id', how='left', validate='1:1')
    for c in ['startDate', 'createdAt', 'endDate', 'closedTime', 'gameStartTime']:
        w[c] = pd.to_datetime(w[c], utc=True, errors='coerce')
    w['anchor'] = w.endDate
    sp_gst = (w.category == 'sports') & w.gameStartTime.notna()
    w.loc[sp_gst, 'anchor'] = w.loc[sp_gst, 'gameStartTime']
    w['anchor_type'] = np.where(sp_gst, 'game', 'sched')
    w['y0'] = np.where(w.resolution == 'split_50_50', 0.5, np.where(w.winner_idx == 0, 1.0, 0.0))
    w.to_parquet(DER / 'flb_wide_sample.parquet', index=False)
    print(w.groupby(['split', 'category']).size().unstack(0).to_string()); print(len(w), w.weight.describe().round(1).to_dict())


if __name__ == '__main__':
    main()
