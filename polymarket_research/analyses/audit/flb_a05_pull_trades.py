"""AUDIT flb (auditor 2026-10-18): pull taker tapes (/v2/trades?condition=, taker-only default) for the E2 and H99_6h trade
markets that are NOT in the panel tape set, so the modelled fill (series mid + bucket half-spread) can be compared with what
takers actually paid for the favourite around the decision time. Resumable (cache=True: tapes of closed markets are immutable).
Scope: E2 (A-7d, side >= 0.95) TEST + validation, H99_6h TEST; samples P and W. max 15 pages (15k rows) per market.
Output: data/derived/audit_flb_trades/part_XXX.parquet (condition_id, outcome_index, side, price, size, timestamp) + pulled.parquet
"""
from pathlib import Path
import sys, importlib, os
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; DER = ROOT / 'data/derived'
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
from pmr import api
A = importlib.import_module('flb_a01_recompute')
ODIR = DER / 'audit_flb_trades'; ODIR.mkdir(exist_ok=True)
MAXP = 15


def targets():
    E = pd.read_parquet(DER / 'flb_entries.parquet')
    S = A.sides(E); S = A.add_R(S, 'med', 1.0, '')
    sel = (((S.horizon == 'A-7d') & (S.m >= 0.95 - 1e-9) & S.split.isin(['test', 'validation'])) |
           ((S.horizon == 'A-6h') & (S.m >= 0.99 - 1e-9) & (S.split == 'test'))) & (S.f <= 0.999)
    T = S[sel]
    tape = set(pd.read_parquet(DER / 'tapes/coverage.parquet').condition_id)
    return sorted(set(T.condition_id) - tape)


def main():
    cids = targets(); print('markets', len(cids), flush=True)
    done = set()
    for f in ODIR.glob('pulled_*.parquet'):
        done |= set(pd.read_parquet(f).condition_id)
    todo = [c for c in cids if c not in done]
    print('todo', len(todo), flush=True)
    k0 = len(list(ODIR.glob('part_*.parquet')))
    for i in range(0, len(todo), 100):
        chunk = todo[i:i + 100]; rows = []; meta = []
        for c in chunk:
            n = 0; err = None
            try:
                it = api.data_v2('/v2/trades', {'condition': c}, cache=True, max_pages=MAXP)
                for r in it:
                    rows.append((c, r.get('outcome_index', r.get('outcomeIndex')), r.get('side'), r.get('price'), r.get('size'), r.get('timestamp')))
                    n += 1
            except Exception as e:  # noqa
                err = str(e)[:200]
            meta.append(dict(condition_id=c, n_rows=n, truncated=n >= MAXP * 1000, error=err))
        D = pd.DataFrame(rows, columns=['condition_id', 'outcome_index', 'side', 'price', 'size', 'timestamp'])
        D = D.astype({'price': float, 'size': float})
        D['timestamp'] = pd.to_numeric(D.timestamp, errors='coerce').astype('Int64')
        k = k0 + i // 100
        D.to_parquet(ODIR / f'part_{k:03d}.parquet', index=False)
        pd.DataFrame(meta).to_parquet(ODIR / f'pulled_{k:03d}.parquet', index=False)
        print(f'chunk {k} rows {len(D)} errors {sum(m["error"] is not None for m in meta)}', flush=True)


if __name__ == '__main__':
    main()
