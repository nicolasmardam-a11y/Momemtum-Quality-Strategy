"""Spread/depth model from live CLOB order books (snapshot 2026-10-17), applied to history as an ASSUMPTION.

1. Candidate open markets: la_markets_2026-10-17w2.parquet (Gamma open-market pull, 21:27 UTC) plus a fresh Gamma pull
   (closed=false, endDate in [now, now+24h]) so that short time-to-resolution markets are current.
2. Stratify by category x time-to-resolution (TTR) bucket; draw up to PER_CELL markets per cell at random.
   TTR: sports with gameStartTime -> time to game start ('in_play' once started); others -> endDate - now.
3. POST /books for token_id_0 (and token_id_1 for a mirror check on 150 markets).
4. Per book: best bid/ask, half-spread, and for $500/$2,500/$10,000 the VWAP slippage vs mid of a marketable buy (walk the
   asks) and sell (walk the bids), fill fraction, and depth (USD) within 1c/2c/5c of mid.
Outputs: data/derived/book_snapshots_2026-10-17_{tag}.parquet (06_spread_model.py builds spread_model.parquet)
Run: PMR_RATE_SCALE=2 python analyses/panel/04_books.py 10000 vol10k   (primary: Gamma volumeNum-to-date >= $10k)
     PMR_RATE_SCALE=2 python analyses/panel/04_books.py               (reference: all open markets, run 2026-10-17 ~22:50 UTC)
"""
import json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'analyses/universe'))
from pmr import api
from categories import category_from_fee_type, category_from_rule

PER_CELL, SEED = 45, 20261017
SIZES = (500, 2500, 10000)
TTR_EDGES = [0, 1, 6, 24, 72, 168, 720, np.inf]
TTR_LABELS = ['<1h', '1-6h', '6-24h', '1-3d', '3-7d', '7-30d', '>30d']
PB_EDGES = [0, 0.02, 0.05, 0.15, 0.35, 0.5000001]
PB_LABELS = ['<2c', '2-5c', '5-15c', '15-35c', '35-50c']


def fresh_short_ttr(now):
    lo, hi = now.strftime('%Y-%m-%dT%H:%M:%SZ'), (now + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ')
    rows = []
    for m in api.gamma_keyset('markets', {'closed': 'false', 'include_tag': 'true', 'end_date_min': lo,
                                          'end_date_max': hi}, max_pages=250):
        rows.append({'conditionId': m.get('conditionId'), 'question': m.get('question'), 'slug': m.get('slug'),
                     'endDate': m.get('endDate'), 'gameStartTime': m.get('gameStartTime'), 'feeType': m.get('feeType'),
                     'sportsMarketType': m.get('sportsMarketType'), 'clobTokenIds': m.get('clobTokenIds'),
                     'acceptingOrders': m.get('acceptingOrders'), 'enableOrderBook': m.get('enableOrderBook'),
                     'negRisk': m.get('negRisk'), 'outcomes': m.get('outcomes'), 'volume24hr': m.get('volume24hr'), 'volumeNum': m.get('volumeNum'),
                     'tag_slugs': [t.get('slug') for t in (m.get('tags') or [])], 'src': 'fresh'})
    return pd.DataFrame(rows)


def walk(levels, usd):
    """levels best-first [(p, s)]; spend/receive `usd` notional. Returns (vwap, fill_fraction)."""
    got_usd = got_sh = 0.0
    for p, s in levels:
        take = min(s, (usd - got_usd) / p) if p > 0 else s
        got_usd += take * p; got_sh += take
        if got_usd >= usd - 1e-9:
            break
    return (got_usd / got_sh if got_sh > 0 else np.nan), got_usd / usd


def book_metrics(b):
    bids, asks = b['bids'], b['asks']
    d = {'asset_id': b['asset_id'], 'book_ts_ms': b['timestamp_ms'], 'tick_size': b['tick_size'],
         'min_order_size': b['min_order_size'], 'n_bid_levels': len(bids), 'n_ask_levels': len(asks),
         'best_bid': bids[0][0] if bids else np.nan, 'best_ask': asks[0][0] if asks else np.nan,
         'last_trade_price': b['last_trade_price']}
    d['two_sided'] = bool(bids and asks)
    if not d['two_sided']:
        return d
    mid = (d['best_bid'] + d['best_ask']) / 2
    d.update(mid=mid, half_spread=(d['best_ask'] - d['best_bid']) / 2)
    for usd in SIZES:
        vb, fb = walk(asks, usd); vs, fs = walk(bids, usd)
        d[f'slip_buy_{usd}'] = vb - mid; d[f'fill_buy_{usd}'] = fb
        d[f'slip_sell_{usd}'] = mid - vs; d[f'fill_sell_{usd}'] = fs
    for c in (0.01, 0.02, 0.05):
        d[f'depth_bid_{int(c*100)}c'] = sum(p * s for p, s in bids if p >= mid - c - 1e-9)
        d[f'depth_ask_{int(c*100)}c'] = sum(p * s for p, s in asks if p <= mid + c + 1e-9)
    return d


def main(min_vol=0.0, tag='allopen'):
    now = datetime.now(timezone.utc)
    old = pd.read_parquet(ROOT / 'data/derived/la_markets_2026-10-17w2.parquet',
                          columns=['conditionId', 'question', 'slug', 'endDate', 'gameStartTime', 'feeType', 'sportsMarketType',
                                   'clobTokenIds', 'acceptingOrders', 'enableOrderBook', 'negRisk', 'outcomes', 'volume24hr',
                                   'volumeNum', 'tag_slugs']).assign(src='la_2127utc')
    fresh = fresh_short_ttr(now)
    print('fresh short-TTR markets', len(fresh))
    m = pd.concat([fresh, old], ignore_index=True).drop_duplicates('conditionId')
    m = m[m.acceptingOrders.fillna(False).astype(bool) & m.enableOrderBook.fillna(False).astype(bool)].copy()
    toks = m.clobTokenIds.map(api.jlist)
    m = m[toks.map(len) == 2].copy(); toks = toks[m.index]
    m['volumeNum'] = pd.to_numeric(m.volumeNum, errors='coerce')
    if min_vol > 0:
        m = m[m.volumeNum >= min_vol].copy(); toks = toks[m.index]
    m['token_id_0'] = toks.map(lambda x: x[0]); m['token_id_1'] = toks.map(lambda x: x[1])
    cf = m.feeType.map(category_from_fee_type)
    cr = [category_from_rule(set(t) if t is not None else set(), s or '', q or '', smt)
          for t, s, q, smt in zip(m.tag_slugs, m.slug, m.question, m.sportsMarketType)]
    m['category'] = cf.fillna(pd.Series(cr, index=m.index))
    end = pd.to_datetime(m.endDate, utc=True, errors='coerce', format='mixed')
    gst = pd.to_datetime(m.gameStartTime, utc=True, errors='coerce', format='mixed')
    m['ttr_h'] = (end - now).dt.total_seconds() / 3600
    m['game_h'] = (gst - now).dt.total_seconds() / 3600
    use_game = m.category.eq('sports') & m.game_h.notna()
    h = np.where(use_game, m.game_h, m.ttr_h)
    lab = pd.cut(pd.Series(h, index=m.index), TTR_EDGES, labels=TTR_LABELS, right=False).astype(object)
    lab[use_game & (m.game_h < 0)] = 'in_play'
    lab[~use_game & (m.ttr_h < 0)] = 'past_end'
    m['ttr_bucket'] = lab; m['ttr_ref'] = np.where(use_game, 'game_start', 'end_date')
    m = m[m.ttr_bucket.notna()]
    m['_r'] = np.random.default_rng(SEED).random(len(m))
    m['_rank'] = m.groupby(['category', 'ttr_bucket'])['_r'].rank(method='first')
    sel = m[m._rank <= PER_CELL].drop(columns=['_r', '_rank']).reset_index(drop=True)
    print('selected', len(sel), 'of', len(m))
    snap_at = datetime.now(timezone.utc)
    bk = pd.DataFrame([book_metrics(b) for b in api.books(sel.token_id_0.tolist())])
    sel = sel.merge(bk, left_on='token_id_0', right_on='asset_id', how='left')
    sel['snapshot_utc'] = snap_at.isoformat()
    # mirror check: token_id_1 book should be the complement of token_id_0's
    chk = sel[sel.two_sided.fillna(False)].sample(min(150, int(sel.two_sided.sum())), random_state=SEED)
    b1 = pd.DataFrame([book_metrics(b) for b in api.books(chk.token_id_1.tolist())])
    chk = chk.merge(b1[['asset_id', 'best_bid', 'best_ask']], left_on='token_id_1', right_on='asset_id', suffixes=('', '_1'))
    mirror = {'n': len(chk), 'bid0_eq_1_minus_ask1': float(np.mean(np.abs(chk.best_bid - (1 - chk.best_ask_1)) < 1e-9)),
              'ask0_eq_1_minus_bid1': float(np.mean(np.abs(chk.best_ask - (1 - chk.best_bid_1)) < 1e-9))}
    print('mirror check', mirror)
    sel['pbucket'] = pd.cut(np.minimum(sel.mid, 1 - sel.mid), PB_EDGES, labels=PB_LABELS, right=False).astype(object)
    keep = [c for c in sel.columns if c not in ('clobTokenIds', 'outcomes', 'asset_id', 'tag_slugs')]
    sel[keep].to_parquet(ROOT / f'data/derived/book_snapshots_2026-10-17_{tag}.parquet', index=False)
    json.dump({'mirror': mirror, 'n_candidates': int(len(m)), 'n_selected': int(len(sel)), 'snapshot_utc': snap_at.isoformat(),
               'fresh_markets': int(len(fresh))}, open(ROOT / f'analyses/panel/out/04_books_{tag}.json', 'w'), indent=1)


if __name__ == '__main__':
    # usage: 04_books.py [min_vol tag]; the primary model uses min_vol=10000 (tag vol10k), the reference allopen
    main(float(sys.argv[1]), sys.argv[2]) if len(sys.argv) > 2 else main()
