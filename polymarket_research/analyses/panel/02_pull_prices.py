"""Pull CLOB /prices-history for token_id_0 of every sampled market (resumable, chunked).

fidelity=60 over the life of the market capped to the last 120 days before ref_ts, in 14-day windows
(the endpoint rejects windows longer than about 15 days: 'interval is too long');
fidelity=1 over [ref_ts - 72h, ref_ts]. ref_ts = min(endDate, closedTime). Explicit startTs/endTs (resolved markets).
Responses are cached (immutable history). Output parts: data/derived/panel_parts/{h60,m1,log}_NNN.parquet.

Run: PMR_RATE_SCALE=2 python analyses/panel/02_pull_prices.py [max_chunks]
"""
import sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from pmr import api

PARTS = ROOT / 'data/derived/panel_parts'; PARTS.mkdir(parents=True, exist_ok=True)
CHUNK = 400
D14, CAP = 14 * 86400, 120 * 86400


def jobs_for(r):
    ref = int(r.ref_ts.timestamp())
    start = ref - CAP
    if pd.notna(r.life_start):
        start = max(start, int(r.life_start.timestamp()) - 3600)
    out = []
    a = start
    while a < ref:
        b = min(a + D14, ref)
        out.append((r.token_id_0, 'h60', a, b, 60))
        a = b
    out.append((r.token_id_0, 'm1', ref - 72 * 3600, ref, 1))
    return out


def fetch(job):
    tok, kind, a, b, fid = job
    try:
        h = api.prices_history(tok, a, b, fid, cache=True)
        return job, h, None
    except Exception as e:  # noqa: BLE001 - record and continue
        return job, [], str(e)[:300]


def main(max_chunks=None):
    s = pd.read_parquet(ROOT / 'data/derived/panel_sample.parquet')
    n_chunks = int(np.ceil(len(s) / CHUNK))
    done = 0
    for c in range(n_chunks):
        f_log = PARTS / f'log_{c:03d}.parquet'
        if f_log.exists():
            continue
        if max_chunks is not None and done >= max_chunks:
            break
        t0 = time.time()
        sub = s.iloc[c * CHUNK:(c + 1) * CHUNK]
        jobs = [j for r in sub.itertuples() for j in jobs_for(r)]
        rows = {'h60': [], 'm1': []}; log = []
        with ThreadPoolExecutor(8) as ex:
            for (tok, kind, a, b, fid), h, err in ex.map(fetch, jobs):
                log.append((tok, kind, a, b, len(h), err))
                if h:
                    rows[kind].append(pd.DataFrame({'token_id': tok, 't': [x['t'] for x in h], 'p': [x['p'] for x in h]}))
        for kind in ('h60', 'm1'):
            df = pd.concat(rows[kind], ignore_index=True) if rows[kind] else pd.DataFrame(columns=['token_id', 't', 'p'])
            df['t'] = df.t.astype('int64'); df['p'] = df.p.astype('float64')
            df.drop_duplicates(['token_id', 't']).to_parquet(PARTS / f'{kind}_{c:03d}.parquet', index=False)
        pd.DataFrame(log, columns=['token_id', 'kind', 'start_ts', 'end_ts', 'n', 'error']).to_parquet(f_log, index=False)
        nerr = sum(1 for x in log if x[5])
        print(f'chunk {c}/{n_chunks}: {len(jobs)} requests, {nerr} errors, {time.time() - t0:.0f}s', flush=True)
        done += 1


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
