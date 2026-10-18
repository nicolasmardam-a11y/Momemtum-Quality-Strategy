"""POST-HOC diagnostics for families E/H (not pre-registered; declared in notes section 9). Written after seeing 04 results.

1. Look-ahead selection by full-life volume: within W (no screen), rule sets split by final volumeNum (<1k, 1k-10k, >=10k).
2. Decision-time activity: rule sets split by n_chg_24h tercile (price changes in the 24 h before entry; known at entry).
3. Rare-loss fragility: unweighted loss counts, Clopper-Pearson 95% upper bound on the loss rate, break-even loss rate,
   and the number of extra full losses that would take the weighted mean net R to 0.
4. Capacity scenarios for $5k / $25k / $100k accounts (population frequency x lock-up; book fill shares; size-dependent net).
Output: analyses/flb_near_res/out/05_posthoc.md
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import beta
sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib.util
spec = importlib.util.spec_from_file_location('a', Path(__file__).parent / '04_analyze.py'); A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
DER, OUT = A.DER, A.OUT
SETS = {'E1': ('A-1d', 0.80, 0.95), 'E2': ('A-7d', 0.95, 1.01), 'H90_24h': ('A-1d', 0.90, 1.01), 'H95_1h': ('A-1h', 0.95, 1.01),
        'H98_6h': ('A-6h', 0.98, 1.01), 'H99_6h': ('A-6h', 0.99, 1.01), 'H99_1h': ('A-1h', 0.99, 1.01), 'H99_24h': ('A-1d', 0.99, 1.01)}


def main():
    S = pd.read_parquet(DER / 'flb_sides.parquet')
    E = pd.read_parquet(DER / 'flb_entries.parquet', columns=['sample', 'condition_id', 'horizon', 'n_chg_24h', 'volumeNum',
                                                            'question'])
    S = S.merge(E, on=['sample', 'condition_id', 'horizon'], how='left')
    S['f_prim'] = np.where(S['sample'] == 'P', S.f_base, S.f_cons)
    S['R_prim'] = np.where(S['sample'] == 'P', S.R_net_base, S.R_net_cons)
    md = ['# 05 post-hoc diagnostics (NOT pre-registered)', '']

    def stats(g, B=1000):
        w = g.weight.values.astype(float)
        q = A.boot((g.pay - g.m).values, w, g.cluster_id.values, B, qs=(0.025, 0.975)) if g.cluster_id.nunique() >= 10 else [np.nan] * 2
        return dict(n=len(g), diff_pp=100 * A.wm(g.pay - g.m, w), lo_pp=100 * q[0], hi_pp=100 * q[1],
                    net_base_pct=100 * A.wm(g.R_net_base, w), net_cons_pct=100 * A.wm(g.R_net_cons, w))

    rows = []
    for rule, (hz, lo, hi) in SETS.items():
        for sp in ('validation', 'test'):
            x = S[(S['sample'] == 'W') & (S.split == sp) & (S.horizon == hz) & (S.m >= lo - 1e-9) & (S.m <= hi) & (S.f_prim <= 0.999)]
            x = x.assign(vt=np.select([x.volumeNum >= 1e4, x.volumeNum >= 1e3], ['>=10k', '1k-10k'], '<1k'))
            for vt, g in x.groupby('vt'):
                rows.append(dict(rule=rule, split=sp, final_volume=vt, **stats(g)))
    md += ['## 1. W: rule sets by FINAL (full-life) volumeNum -- look-ahead selection diagnostic',
           A.to_md(pd.DataFrame(rows), floatfmt='.2f'), '']

    rows = []
    for smp in ('P', 'W'):
        for rule, (hz, lo, hi) in SETS.items():
            x = S[(S['sample'] == smp) & (S.split == 'test') & (S.horizon == hz) & (S.m >= lo - 1e-9) & (S.m <= hi) & (S.f_prim <= 0.999)
                  & S.n_chg_24h.notna()].copy()
            if len(x) < 30:
                continue
            x['act'] = pd.qcut(x.n_chg_24h.rank(method='first'), 3, labels=['low', 'mid', 'high'])
            for t, g in x.groupby('act', observed=True):
                rows.append(dict(sample=smp, rule=rule, activity=t, chg24_max=g.n_chg_24h.max(), **stats(g)))
    md += ['## 2. TEST rule sets by decision-time activity tercile (n_chg_24h, within sample x rule)',
           A.to_md(pd.DataFrame(rows), floatfmt='.2f'), '']

    rows = []
    for smp in ('P', 'W'):
        for rule, (hz, lo, hi) in SETS.items():
            for sp in ('train', 'validation', 'test', 'all'):
                x = S[(S['sample'] == smp) & (S.horizon == hz) & (S.m >= lo - 1e-9) & (S.m <= hi) & (S.f_prim <= 0.999)]
                if sp != 'all':
                    x = x[x.split == sp]
                if len(x) == 0:
                    continue
                w = x.weight.values.astype(float); k = int((x.pay == 0).sum()); n = len(x)
                rwin = A.wm(x.R_prim[x.pay == 1], w[x.pay.values == 1]); net = A.wm(x.R_prim, w)
                rows.append(dict(sample=smp, rule=rule, split=sp, n=n, losses=k, half=int((x.pay == 0.5).sum()),
                                 loss_rate=k / n, cp95_upper=beta.ppf(0.975, k + 1, n - k) if k < n else 1.0,
                                 breakeven_loss_rate=rwin / (1 + rwin), net_pct=100 * net,
                                 extra_losses_to_zero=n * net / (1 + rwin) if net > 0 else 0.0))
    md += ['## 3. Rare-loss fragility (unweighted counts; primary cost; break-even loss rate = Rwin/(1+Rwin))',
           A.to_md(pd.DataFrame(rows), floatfmt='.4f'), '']

    # 4. capacity scenarios (TEST, P population = vol>=10k universe; W population = the rest of the eligible universe)
    rows = []
    for rule in ('E2', 'H99_6h', 'H98_6h', 'H99_1h'):
        hz, lo, hi = SETS[rule]
        for smp in ('P', 'W'):
            x = S[(S['sample'] == smp) & (S.split == 'test') & (S.horizon == hz) & (S.m >= lo - 1e-9) & (S.m <= hi) & (S.f_prim <= 0.999)]
            lam = x.weight.sum() / 288.0; dbar = A.wm(x.d, x.weight); conc = lam * dbar
            for acct in (5000, 25000, 100000):
                size = acct / conc
                rows.append(dict(rule=rule, population=smp, per_day=lam, d_mean=dbar, concurrent=conc, account=acct,
                                 size_if_all_traded=size))
    md += ['## 4. Capacity: qualifying markets per day (population-weighted), mean lock-up, concurrent positions, and the per-trade'
           ' size at which each account would be fully deployed by trading every qualifying market',
           A.to_md(pd.DataFrame(rows), floatfmt='.1f'), '']
    (OUT / '05_posthoc.md').write_text('\n'.join(md))
    print('written', OUT / '05_posthoc.md')


if __name__ == '__main__':
    main()
