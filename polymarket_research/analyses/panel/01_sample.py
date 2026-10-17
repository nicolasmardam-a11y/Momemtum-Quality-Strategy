"""Stage-2 sample design: stratified sample of binary markets with Gamma volumeNum >= $10k.

Eligibility (all known before or at listing, except the volume screen and the resolution outcome):
  n_outcomes == 2, enableOrderBook, token_id_0 present, volumeNum >= 10,000 (FULL-LIFE volume: mild look-ahead),
  resolution in {winner, split_50_50}. 50-50 splits are kept and flagged (clean_resolution = False) so the sample
  does not condition on the resolution type; 12 'unresolved_nonterminal' markets have no payout and are dropped.
Allocation: split budgets (train 1,500 / validation 1,500 / test 5,000), then per quarter in proportion to the
number of calendar days of that quarter inside the window, then across categories in proportion to sqrt(N_cell)
with a floor of min(N_cell, 5) and a cap of N_cell. Uniform random draw within a cell (seed 20261017).
sample_weight = N_cell / n_cell re-weights the sample to the eligible population.

Output: data/derived/panel_sample.parquet
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))

SEED = 20261017
BUDGET = {"train": 1500, "validation": 1500, "test": 5000}
FLOOR = 5
COLS = ['id', 'condition_id', 'question_id', 'slug', 'question', 'sportsMarketType', 'startDate', 'createdAt', 'endDate',
        'closedTime', 'gameStartTime', 'eventStartTime', 'outcomes', 'token_id_0', 'token_id_1', 'n_outcomes', 'resolution',
        'winner_idx', 'negRisk', 'negRiskMarketID', 'volumeNum', 'liquidityNum', 'enableOrderBook', 'feesEnabled', 'feeType',
        'fee_rate', 'fee_exponent', 'orderPriceMinTickSize', 'secondsDelay', 'has_disputed', 'multi_proposal', 'event_id',
        'event_slug', 'category', 'category_source', 'end_quarter', 'split', 'structure', 'cluster_id', 'cluster_week',
        'settle_lag_h', 'settle_lag_game_h', 'tags']


def quarter_days(q: str) -> int:
    y, k = int(q[:4]), int(q[-1])
    a = pd.Timestamp(year=y, month=3 * k - 2, day=1)
    b = a + pd.offsets.QuarterBegin(startingMonth=1)
    b = min(b, pd.Timestamp('2026-10-16'))  # universe ends 2026-10-15
    return (b - a).days


def alloc(sizes: pd.Series, budget: int) -> pd.Series:
    """sqrt(N)-proportional allocation with floor min(N, FLOOR) and cap N (largest remainder)."""
    n = np.minimum(sizes, FLOOR).astype(float)
    left = budget - n.sum()
    free = sizes > n
    while left > 0.5 and free.any():
        w = np.sqrt(sizes[free]); add = left * w / w.sum()
        room = sizes[free] - n[free]
        add = np.minimum(add, room)
        n[free] += add; left = budget - n.sum(); free = sizes - n > 1e-9
        if (add < 1e-9).all():
            break
    out = np.floor(n).astype(int)
    rem = budget - out.sum(); frac = (n - out).sort_values(ascending=False)
    for k in frac.index[:max(0, int(rem))]:
        if out[k] < sizes[k]:
            out[k] += 1
    return out


def main():
    m = pd.read_parquet(ROOT / 'data/derived/markets_resolved.parquet', columns=COLS,
                        filters=[('volumeNum', '>=', 1e4)])
    n0 = len(m)
    m = m[(m.n_outcomes == 2) & m.enableOrderBook.fillna(False) & m.token_id_0.notna()
          & m.resolution.isin(['winner', 'split_50_50'])].copy()
    print(f'eligible {len(m):,} of {n0:,} with volumeNum>=10k')
    rng = np.random.default_rng(SEED)
    parts = []
    for sp, g in m.groupby('split'):
        qs = sorted(g.end_quarter.unique())
        days = pd.Series({q: quarter_days(q) for q in qs})
        qb = (BUDGET[sp] * days / days.sum()).round().astype(int)
        for q in qs:
            gq = g[g.end_quarter == q]
            sizes = gq.groupby('category').size()
            na = alloc(sizes, int(qb[q]))
            for cat, k in na.items():
                cell = gq[gq.category == cat]
                idx = rng.choice(len(cell), size=int(k), replace=False)
                s = cell.iloc[np.sort(idx)].copy()
                s['N_cell'] = len(cell); s['n_cell'] = int(k); s['sample_weight'] = len(cell) / k
                parts.append(s)
    s = pd.concat(parts, ignore_index=True)
    s['clean_resolution'] = s.resolution.eq('winner')
    s['y0'] = np.where(s.clean_resolution, (s.winner_idx == 0).astype(float), 0.5)  # payout of token_id_0
    s['ref_ts'] = s[['endDate', 'closedTime']].min(axis=1)  # resolution reference time = min(endDate, closedTime)
    s['early_close'] = s.closedTime < s.endDate - pd.Timedelta('1h')
    s['life_start'] = s[['startDate', 'createdAt']].min(axis=1)
    s.to_parquet(ROOT / 'data/derived/panel_sample.parquet', index=False)
    print(f'sample {len(s):,}'); print(s.groupby('split').size().to_dict())
    print(s.pivot_table(index='end_quarter', columns='category', values='id', aggfunc='count', fill_value=0).to_string())
    print('50-50 in sample', (~s.clean_resolution).sum(), ' neg-risk', s.negRisk.sum(), ' early_close', s.early_close.sum(),
          ' clusters', s.cluster_id.nunique())


if __name__ == '__main__':
    main()
