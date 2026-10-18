"""Pull CLOB /prices-history (token_id_0, fidelity 5) for the W sample. Resumable, chunked (CHUNK markets per part).

Window per market: [min(anchor, closedTime) - 7d - 2h, closedTime + 10 min]; if longer than 14.9 d, request 1 covers the
first 14.9 d and request 2 covers [closedTime - 26 h, closedTime + 10 min]. Raw responses are cached (immutable history)
under data/raw/clob/cache/ with URL, params and fetch time.
Stored per part: change points only (first point + every point whose price differs from the previous one) and grid gaps
> 15 min, so the forward-filled 5-minute grid can be reconstructed exactly. Price at t = last change point <= t, valid
only if t >= first grid point and t is not inside a gap.
Run: PMR_RATE_SCALE=2 python analyses/flb_near_res/02_pull_wide.py [max_parts]
Outputs: data/derived/flb_wide_parts/{cp,gaps,meta}_NNN.parquet
"""
import sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pmr import api
ROOT = Path(__file__).resolve().parents[2]; DER = ROOT / 'data/derived'; OUT = DER / 'flb_wide_parts'
CHUNK = 2000; FID = 5; MAXW = int(14.9 * 86400)


def jobs_for(r):
    close = int(r.closedTime.timestamp()); a = int(min(r.anchor, r.closedTime).timestamp())
    s = a - 7 * 86400 - 7200; e = close + 600
    if e - s <= MAXW:
        return [(r.condition_id, r.token_id_0, 0, s, e)]
    return [(r.condition_id, r.token_id_0, 0, s, s + MAXW), (r.condition_id, r.token_id_0, 1, max(s + MAXW, close - 26 * 3600), e)]


def fetch(job):
    cid, tok, k, s, e = job
    try:
        h = api.prices_history(tok, s, e, FID, cache=True); err = None
    except Exception as ex:
        h, err = [], str(ex)[:300]
    if h:
        t = np.array([x['t'] for x in h], dtype=np.int64); p = np.array([x['p'] for x in h], dtype=np.float64)
        o = np.argsort(t, kind='stable'); t, p = t[o], p[o]
        keep = np.r_[True, p[1:] != p[:-1]]
        d = np.diff(t); gi = np.where(d > 900)[0]
        cp = pd.DataFrame({'condition_id': cid, 'req': k, 't': t[keep], 'p': p[keep].astype(np.float32)})
        gaps = pd.DataFrame({'condition_id': cid, 'req': k, 'gap_start': t[gi], 'gap_end': t[gi + 1]})
        meta = dict(condition_id=cid, req=k, start=s, end=e, n_points=len(t), first_t=int(t[0]), last_t=int(t[-1]),
                    max_gap_s=int(d.max()) if len(d) else 0, n_changes=int(keep.sum()) - 1, err=err)
    else:
        cp = gaps = None
        meta = dict(condition_id=cid, req=k, start=s, end=e, n_points=0, first_t=None, last_t=None, max_gap_s=None,
                    n_changes=0, err=err)
    return cp, gaps, meta


def main(max_parts=None):
    OUT.mkdir(parents=True, exist_ok=True)
    w = pd.read_parquet(DER / 'flb_wide_sample.parquet').sort_values(['split', 'category', 'condition_id']).reset_index(drop=True)
    n_parts = int(np.ceil(len(w) / CHUNK)); done = 0
    for c in range(n_parts):
        if (OUT / f'meta_{c:03d}.parquet').exists():
            continue
        if max_parts is not None and done >= max_parts:
            break
        t0 = time.time(); jobs = [j for _, r in w.iloc[c * CHUNK:(c + 1) * CHUNK].iterrows() for j in jobs_for(r)]
        with ThreadPoolExecutor(8) as ex:
            res = list(ex.map(fetch, jobs))
        cps = [x[0] for x in res if x[0] is not None]; gps = [x[1] for x in res if x[1] is not None and len(x[1])]
        (pd.concat(cps) if cps else pd.DataFrame(columns=['condition_id', 'req', 't', 'p'])).to_parquet(OUT / f'cp_{c:03d}.parquet', index=False)
        (pd.concat(gps) if gps else pd.DataFrame(columns=['condition_id', 'req', 'gap_start', 'gap_end'])).to_parquet(OUT / f'gaps_{c:03d}.parquet', index=False)
        meta = pd.DataFrame([x[2] for x in res]); meta.to_parquet(OUT / f'meta_{c:03d}.parquet', index=False)
        done += 1
        print(f'part {c}/{n_parts}: {len(jobs)} req, {meta.err.notna().sum()} err, {(meta.n_points == 0).sum()} empty, '
              f'{time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
