"""Pull /v2/trades?condition=... taker tapes (default taker_only) for a stratified liquid subsample of the panel sample.

Selection (uses full-life Gamma volumeNum, the same mild look-ahead as the sample screen): within each split x category
stratum of panel_sample, take the top-k markets by volumeNum, k = round(1500 * n_stratum / 8000), floor min(n, 5).
Plus an audit set: 100 random null-volumeNum markets (2026Q3, enableOrderBook, binary, resolved) to measure how many
markets the volume screen misses because Gamma volumeNum is blank.

Pagination: keyset cursor, newest first, 1,000 rows per page, capped at MAX_PAGES pages per market (newest part kept;
`truncated` flags it). Raw pages are cached (immutable history) by pmr.http.

Run: PMR_RATE_SCALE=2 python analyses/panel/03_pull_tapes.py select|pull [max_chunks]
Outputs: data/derived/tape_selection.parquet, data/derived/tapes/tape_NNN.parquet, data/derived/tapes/coverage_NNN.parquet
"""
import sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from pmr.http import request_json

DATA = 'https://data-api.polymarket.com'
TAPES = ROOT / 'data/derived/tapes'; TAPES.mkdir(parents=True, exist_ok=True)
SEL = ROOT / 'data/derived/tape_selection.parquet'
MAX_PAGES, CHUNK = 100, 100
KEEP = ['condition_id', 'token_id', 'outcome', 'outcome_index', 'side', 'price', 'size', 'timestamp', 'proxy_wallet',
        'transaction_hash']


def select():
    s = pd.read_parquet(ROOT / 'data/derived/panel_sample.parquet')
    g = s.groupby(['split', 'category'])
    k = (1500 * g.size() / len(s)).round()
    k = np.minimum(np.maximum(k, np.minimum(g.size(), 5)), g.size())
    sel = pd.concat([gg.nlargest(int(k[key]), 'volumeNum') for key, gg in g])
    sel = sel[['condition_id', 'token_id_0', 'split', 'category', 'end_quarter', 'volumeNum', 'ref_ts', 'closedTime']].assign(
        set='liquid')
    m = pd.read_parquet(ROOT / 'data/derived/markets_resolved.parquet',
                        columns=['condition_id', 'token_id_0', 'split', 'category', 'end_quarter', 'volumeNum', 'endDate',
                                 'closedTime', 'enableOrderBook', 'resolution', 'n_outcomes'],
                        filters=[('end_quarter', '=', '2026Q3')])
    a = m[m.volumeNum.isna() & m.enableOrderBook.fillna(False) & m.resolution.eq('winner') & (m.n_outcomes == 2)]
    a = a.sample(100, random_state=20261017).assign(set='nullvol_audit')
    a['ref_ts'] = a[['endDate', 'closedTime']].min(axis=1)
    sel = pd.concat([sel, a[sel.columns]], ignore_index=True)
    sel.to_parquet(SEL, index=False)
    print(sel.groupby(['set', 'split']).size().to_dict(), 'vol $M', round(sel.volumeNum.sum() / 1e6))


def pull_one(cid):
    params = {'condition': cid, 'limit': 1000}
    rows, pages, err, empty_more, seen_cursors = [], 0, None, 0, set()
    while True:
        try:
            j = request_json(f'{DATA}/v2/trades', params, source='data-api', cache=True)
        except Exception as e:  # noqa: BLE001
            err = str(e)[:300]; break
        d = j.get('data') or []
        rows += [{k: x.get(k) for k in KEEP} for x in d]
        pages += 1
        pg = j.get('pagination') or {}
        cur = pg.get('next_cursor')
        if not d and cur:
            empty_more += 1
        if not cur or not pg.get('has_more', True):
            truncated = False; break
        if cur in seen_cursors:
            err = 'cursor_loop'; truncated = True; break
        seen_cursors.add(cur)
        if pages >= MAX_PAGES:
            truncated = True; break
        params['cursor'] = cur
    if err:
        truncated = True
    df = pd.DataFrame(rows, columns=KEEP)
    cov = {'condition_id': cid, 'n_rows': len(df), 'n_pages': pages, 'truncated': truncated, 'error': err,
           'empty_pages_with_more': empty_more}
    if len(df):
        df['price'] = df.price.astype(float); df['size'] = df['size'].astype(float); df['timestamp'] = df.timestamp.astype('int64')
        ts = df.timestamp.values
        cov.update(first_ts=int(ts.min()), last_ts=int(ts.max()), nonmonotone=int((np.diff(ts) > 0).sum()),
                   dup_rows=int(df.duplicated().sum()), notional=float((df.price * df['size']).sum()))
    return df, cov


def pull(max_chunks=None):
    sel = pd.read_parquet(SEL)
    n = int(np.ceil(len(sel) / CHUNK)); done = 0
    for c in range(n):
        fc = TAPES / f'coverage_{c:03d}.parquet'
        if fc.exists():
            continue
        if max_chunks is not None and done >= max_chunks:
            break
        t0 = time.time(); cids = sel.condition_id.iloc[c * CHUNK:(c + 1) * CHUNK].tolist()
        with ThreadPoolExecutor(12) as ex:
            res = list(ex.map(pull_one, cids))
        nonempty = [r[0] for r in res if len(r[0])]
        tape = pd.concat(nonempty, ignore_index=True) if nonempty else pd.DataFrame(columns=KEEP)
        tape.to_parquet(TAPES / f'tape_{c:03d}.parquet', index=False)
        cov = pd.DataFrame([r[1] for r in res]); cov.to_parquet(fc, index=False)
        print(f'chunk {c}/{n}: {len(tape):,} rows, pages {cov.n_pages.sum()}, truncated {cov.truncated.sum()}, '
              f'errors {cov.error.notna().sum()}, {time.time() - t0:.0f}s', flush=True)
        done += 1


if __name__ == '__main__':
    if sys.argv[1] == 'select':
        select()
    else:
        pull(int(sys.argv[2]) if len(sys.argv) > 2 else None)
