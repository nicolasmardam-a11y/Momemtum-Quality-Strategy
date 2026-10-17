"""Repeated CLOB order-book snapshots for every market that appears in a candidate relation.

Run from polymarket_research/:
    PMR_RATE_SCALE=2 python -m analyses.logical_arb.03_snapshot_books <n_snapshots> <interval_s> [date]

Only the outcome-0 token's book is fetched: YES/NO books are exact mirrors
(NO ask = 1 - YES bid, same size; verified on 4 markets 2026-10-17 and re-checked here on a sample).
Tokens are ordered by event/game so the legs of one relation come from the same or an adjacent
POST /books call (seconds apart). Raw responses are kept by pmr.http under data/raw/clob/live/.
Each snapshot is written as data/derived/la_books/snap_<UTC>.parquet with up to 30 levels per side.
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1
INTERVAL = float(sys.argv[2]) if len(sys.argv) > 2 else 300
DATE = sys.argv[3] if len(sys.argv) > 3 else "2026-10-17"
OUTDIR = ROOT / "data" / "derived" / "la_books"
OUTDIR.mkdir(parents=True, exist_ok=True)
LEVELS = 30

# relation files may be slim (family,key,ma,oa,mb,ob,note); token ids come from the market pull of the same tag.
# la_extra_markets_<tag>.parquet (column 'id') adds markets used by multi-leg checks (06_count_sets).
R = pd.concat([pd.read_parquet(f, columns=["ma", "mb"]) for f in
               sorted((ROOT / "data" / "derived").glob(f"la_relations*_{DATE}.parquet"))])
ids = pd.unique(pd.concat([R.ma.astype(str), R.mb.astype(str)]))
xf = ROOT / "data" / "derived" / f"la_extra_markets_{DATE}.parquet"
if xf.exists():
    ids = pd.unique(pd.concat([pd.Series(ids), pd.read_parquet(xf).id.astype(str)]))
MK = pd.read_parquet(ROOT / "data" / "derived" / f"la_markets_{DATE}.parquet", columns=["id", "clobTokenIds", "event_slug"])
MK["id"] = MK["id"].astype(str)
legs = MK[MK.id.isin(set(ids))].drop_duplicates("id").set_axis(["mid", "tok", "slug"], axis=1)
legs["tok0"] = legs.tok.map(lambda s: json.loads(s)[0])
legs = legs.sort_values(["slug", "mid"])
TOKS = legs.tok0.tolist()
MID = dict(zip(legs.tok0, legs.mid))
print("markets to snapshot", len(TOKS), flush=True)


WORKERS = int(os.environ.get("LA_WORKERS", "4"))  # pmr.http still throttles the host globally


def fetch_chunk(i: int):
    chunk = TOKS[i:i + 100]
    tf = time.time()
    try:
        res = request_json(f"{api.CLOB}/books", method="POST", json_body=[{"token_id": t} for t in chunk],
                           source="clob")
    except Exception as e:  # keep going; a missing chunk just means missing books this round
        print("chunk error", i, e, flush=True)
        return tf, []
    return tf, res


def one_snapshot(k: int) -> None:
    t0 = datetime.now(timezone.utc)
    rows = []
    with ThreadPoolExecutor(WORKERS) as ex:
        results = list(ex.map(fetch_chunk, range(0, len(TOKS), 100)))
    for tf, res in results:
        for b in res:
            nb = api.normalize_book(b)
            rows.append({
                "tok0": nb["asset_id"], "mid": MID.get(nb["asset_id"]), "ts_ms": nb["timestamp_ms"],
                "fetch_unix": tf, "tick": nb["tick_size"], "min_size": nb["min_order_size"],
                "bids": json.dumps(nb["bids"][:LEVELS]), "asks": json.dumps(nb["asks"][:LEVELS]),
                "n_bids": len(nb["bids"]), "n_asks": len(nb["asks"]),
            })
    df = pd.DataFrame(rows)
    df["snap_utc"] = t0.isoformat()
    df["snap_k"] = k
    out = OUTDIR / f"snap_{t0:%Y%m%dT%H%M%S}.parquet"
    df.to_parquet(out, index=False)
    print(f"snap {k} {t0:%H:%M:%S} books {len(df)} took {(datetime.now(timezone.utc) - t0).total_seconds():.0f}s -> {out.name}",
          flush=True)


for k in range(N):
    start = time.time()
    one_snapshot(k)
    if k < N - 1:
        time.sleep(max(0, INTERVAL - (time.time() - start)))
print("done", flush=True)
