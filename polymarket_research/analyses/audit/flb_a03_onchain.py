"""AUDIT flb (auditor 2026-10-18): independent check of payout labels (y0) against on-chain CTF payouts on Polygon.

CTF 0x4D97DCd97eC945f40cF65F87097ACe5EA0476045: payoutDenominator(bytes32) 0xdd34de67, payoutNumerators(bytes32,uint256) 0x0504c814.
Index 0 of the CTF payout vector = outcome 0 = token_id_0 (checked on resolved markets: y0=1 <-> [1,0]).
Checked: every LOSS and every 50-50 among trades of E2 and the H98/H99 rules (all samples, all splits), plus a seeded random
sample of 150 TEST winners each from E2 and H99_6h. Output: analyses/audit/out/flb_a03_onchain.parquet + printed summary.
"""
from pathlib import Path
import sys
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; OUT = Path(__file__).parent / 'out'
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
from pmr import api
import importlib
A = importlib.import_module('flb_a01_recompute')
CTF = '0x4D97DCd97eC945f40cF65F87097ACe5EA0476045'


def onchain(cid):
    c = cid[2:].rjust(64, '0')
    den = int(api.rpc('eth_call', [{'to': CTF, 'data': '0xdd34de67' + c}, 'latest']), 16)
    n0 = int(api.rpc('eth_call', [{'to': CTF, 'data': '0x0504c814' + c + '0' * 64}, 'latest']), 16) if den else None
    n1 = int(api.rpc('eth_call', [{'to': CTF, 'data': '0x0504c814' + c + '0' * 63 + '1'}, 'latest']), 16) if den else None
    return den, n0, n1


def main():
    E = pd.read_parquet(A.DER / 'flb_entries.parquet')
    S = A.sides(E); S = A.add_R(S, 'med', 1.0, '')
    pick = []
    for rule in ['E2'] + [k for k in A.RULES if k.startswith('H98') or k.startswith('H99')]:
        hz, lo, hi = A.RULES[rule]
        T = S[(S.horizon == hz) & (S.m >= lo - 1e-9) & (S.f <= 0.999)]
        pick.append(T[T.pay < 1].assign(rule=rule, why='loss_or_half'))
        if rule in ('E2', 'H99_6h'):
            wn = T[(T.pay == 1) & (T.split == 'test')]
            pick.append(wn.sample(min(150, len(wn)), random_state=20261018).assign(rule=rule, why='winner_sample'))
    P = pd.concat(pick, ignore_index=True)
    mk = P.drop_duplicates('condition_id')[['condition_id', 'y0']].reset_index(drop=True)
    print('markets to check', len(mk), flush=True)
    rec = []
    for r in mk.itertuples():
        try:
            den, n0, n1 = onchain(r.condition_id)
        except Exception as e:  # noqa
            den, n0, n1 = -1, None, None
        y_chain = (n0 / den) if den and den > 0 and n0 is not None else np.nan
        rec.append(dict(condition_id=r.condition_id, y0=r.y0, den=den, n0=n0, n1=n1, y0_chain=y_chain))
    R = pd.DataFrame(rec)
    R.to_parquet(OUT / 'flb_a03_onchain.parquet', index=False)
    R['match'] = np.isclose(R.y0.astype(float), R.y0_chain.astype(float))
    print(R.groupby(R.den.clip(upper=2)).size().to_string())
    print('match', int(R.match.sum()), 'of', len(R), '; mismatches:')
    print(R[~R.match].head(20).to_string())
    P = P.merge(R[['condition_id', 'match']], on='condition_id')
    print(P.groupby(['rule', 'why']).match.agg(['size', 'sum']).to_string())


if __name__ == '__main__':
    main()
