"""Re-snapshot the books of the markets selected by 04_books.py and keep the full price levels.

04_books.py stored only derived metrics for token_id_0. This re-fetches POST /books for the same token_id_0 list
(both universes) and stores every level, so 06_spread_model.py can derive both outcome sides (the token_id_1 book is the
mirror of token_id_0's: verified 97-100% on 150 markets per snapshot) and so the stability of spreads between the two
snapshots can be checked. TTR is recomputed at the new snapshot time.
Run: PMR_RATE_SCALE=2 python analyses/panel/04b_resnap_books.py <round_tag>   (e.g. r2)
Output: data/derived/book_levels_2026-10-17_{universe}_{round}.parquet
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from pmr import api


def main(rnd):
    for tag in ('vol10k', 'allopen'):
        s = pd.read_parquet(ROOT / f'data/derived/book_snapshots_2026-10-17_{tag}.parquet',
                            columns=['conditionId', 'token_id_0', 'category', 'endDate', 'gameStartTime', 'ttr_ref', 'negRisk',
                                     'src'] + (['volumeNum'] if tag == 'vol10k' else []))
        now = datetime.now(timezone.utc)
        bk = api.books(s.token_id_0.tolist())
        L = pd.DataFrame([{'token_id_0': b['asset_id'], 'book_ts_ms': b['timestamp_ms'], 'tick_size': b['tick_size'],
                           'min_order_size': b['min_order_size'], 'bids_json': json.dumps(b['bids']),
                           'asks_json': json.dumps(b['asks'])} for b in bk])
        out = s.merge(L, on='token_id_0', how='left')
        end = pd.to_datetime(out.endDate, utc=True, errors='coerce', format='mixed')
        gst = pd.to_datetime(out.gameStartTime, utc=True, errors='coerce', format='mixed')
        out['ttr_h'] = (end - now).dt.total_seconds() / 3600; out['game_h'] = (gst - now).dt.total_seconds() / 3600
        out['snapshot_utc'] = now.isoformat(); out['round'] = rnd; out['book_universe'] = tag
        out.to_parquet(ROOT / f'data/derived/book_levels_2026-10-17_{tag}_{rnd}.parquet', index=False)
        print(tag, rnd, len(out), 'books returned', len(L), now.isoformat())


if __name__ == '__main__':
    main(sys.argv[1])
