"""AUDIT flb (auditor 2026-10-18): re-pull CLOB /prices-history at fidelity 1 around the decision time for a seeded sample of
E2 and H99_6h TEST trades (P and W) and check (i) the stored horizon price p0 equals the last fresh point at or before h
(no look-ahead, no stale substitution), (ii) how far the price moved in the next 60 min (would a slower fill matter),
(iii) whether the fidelity-5 / fidelity-60 value could embed post-h information (compare with first point after h).
Output: analyses/audit/out/flb_a07.json
"""
from pathlib import Path
import sys, importlib, json
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
from pmr import api
A = importlib.import_module('flb_a01_recompute')


def main():
    E = pd.read_parquet(A.DER / 'flb_entries.parquet')
    S = A.sides(E); S = A.add_R(S, 'med', 1.0, '')
    rows = []
    for rule in ('E2', 'H99_6h'):
        hz, lo, hi = A.RULES[rule]
        for samp in ('P', 'W'):
            T = S[(S['sample'] == samp) & (S.split == 'test') & (S.horizon == hz) & (S.m >= lo - 1e-9) & (S.f <= 0.999)]
            L = T[T.pay == 0]
            rows.append(pd.concat([L, T[T.pay == 1].sample(min(40, len(T)), random_state=5)]).assign(rule=rule))
    T = pd.concat(rows, ignore_index=True)
    out = []
    for r in T.itertuples():
        h = int(pd.Timestamp(r.h_ts).timestamp())
        try:
            hist = api.prices_history(r.token_id_0, h - 3 * 3600, h + 3600, 1, cache=True)
        except Exception as e:  # noqa
            out.append(dict(rule=r.rule, sample=r.sample, ok=False, err=str(e)[:100])); continue
        if not hist:
            out.append(dict(rule=r.rule, sample=r.sample, ok=False, err='empty')); continue
        t = np.array([x['t'] for x in hist]); p = np.array([float(x['p']) for x in hist])
        side_p = p if r.side == 0 else 1 - p
        pre = np.where(t <= h)[0]; post = np.where(t > h)[0]
        rec = dict(rule=r.rule, sample=r.sample, ok=True, m_stored=r.m, pay=r.pay)
        if len(pre):
            rec['m_fresh'] = round(float(side_p[pre[-1]]), 4); rec['age_s'] = int(h - t[pre[-1]])
        if len(post):
            rec['m_first_after'] = round(float(side_p[post[0]]), 4)
            rec['m_max_dev_60m'] = round(float(np.max(np.abs(side_p[post] - r.m))), 4)
            rec['m_at_60m'] = round(float(side_p[post[-1]]), 4)
        out.append(rec)
    D = pd.DataFrame(out)
    D['match'] = np.isclose(D.m_fresh, D.m_stored, atol=1e-4)
    D['match_first_after'] = np.isclose(D.m_first_after, D.m_stored, atol=1e-4)
    res = {}
    for (rule, samp), d in D[D.ok].groupby(['rule', 'sample']):
        res[f'{rule}|{samp}'] = dict(n=len(d), match_last_before_h=int(d.match.sum()),
                                     mismatch_but_equals_first_after=int((~d.match & d.match_first_after).sum()),
                                     median_abs_diff=round(float((d.m_fresh - d.m_stored).abs().median()), 5),
                                     max_abs_diff=round(float((d.m_fresh - d.m_stored).abs().max()), 4),
                                     mean_move_next_60m=round(float((d.m_at_60m - d.m_stored).mean()), 5),
                                     share_dev_gt_1c_60m=round(float((d.m_max_dev_60m > 0.01).mean()), 3))
    res['n_failed'] = int((~D.ok).sum())
    (A.OUT / 'flb_a07.json').write_text(json.dumps(res, indent=1))
    D.to_parquet(A.OUT / 'flb_a07_detail.parquet', index=False)
    print(json.dumps(res, indent=1))
    print(D[~D.match & D.ok].head(10).to_string())


if __name__ == '__main__':
    main()
