"""Side collector: repeated CLOB book snapshots for the k-of-n count-set markets (06_count_sets) - read-only.

Run from polymarket_research/:
    PMR_RATE_SCALE=2 python -m analyses.logical_arb.03b_snapshot_cnt <n_snapshots> <interval_s> <tag>
Input : data/derived/la_cnt_markets_<tag>.parquet (from `06_count_sets define <tag>`), la_markets_<tag>.parquet
Output: data/derived/la_books_cnt/snap_<UTC>.parquet (same schema as 03_snapshot_books). All legs of one set are
fetched within one or two POST /books calls (< ~1 s apart), so the set is priced on a near-simultaneous book.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

N, INTERVAL, TAG = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
LIST = sys.argv[4] if len(sys.argv) > 4 else "cnt"  # list la_<LIST>_markets_<tag>.parquet -> la_books_<LIST>/
OUT = ROOT / "data" / "derived" / f"la_books_{LIST}"
OUT.mkdir(parents=True, exist_ok=True)
ids = set(pd.read_parquet(ROOT / "data" / "derived" / f"la_{LIST}_markets_{TAG}.parquet").id.astype(str))
MK = pd.read_parquet(ROOT / "data" / "derived" / f"la_markets_{TAG}.parquet", columns=["id", "clobTokenIds", "event_id"])
MK["id"] = MK.id.astype(str)
MK = MK[MK.id.isin(ids)].sort_values(["event_id", "id"])
MK["tok0"] = MK.clobTokenIds.map(lambda s: json.loads(s)[0])
TOKS, MID = MK.tok0.tolist(), dict(zip(MK.tok0, MK.id))
print("markets", len(TOKS), flush=True)
for k in range(N):
    t0 = datetime.now(timezone.utc)
    rows = []
    for i in range(0, len(TOKS), 100):
        tf = time.time()
        try:
            res = request_json(f"{api.CLOB}/books", method="POST", json_body=[{"token_id": t} for t in TOKS[i:i + 100]],
                               source="clob")
        except Exception as e:  # missing chunk -> those sets are skipped this round
            print("chunk error", i, e, flush=True)
            continue
        for b in res:
            nb = api.normalize_book(b)
            rows.append({"tok0": nb["asset_id"], "mid": MID.get(nb["asset_id"]), "ts_ms": nb["timestamp_ms"],
                         "fetch_unix": tf, "tick": nb["tick_size"], "min_size": nb["min_order_size"],
                         "bids": json.dumps(nb["bids"][:30]), "asks": json.dumps(nb["asks"][:30]),
                         "n_bids": len(nb["bids"]), "n_asks": len(nb["asks"])})
    df = pd.DataFrame(rows)
    df["snap_utc"], df["snap_k"] = t0.isoformat(), k
    df.to_parquet(OUT / f"snap_{t0:%Y%m%dT%H%M%S}.parquet", index=False)
    print(f"snap {k} {t0:%H:%M:%S} books {len(df)}", flush=True)
    if k < N - 1:
        time.sleep(max(0, INTERVAL - (datetime.now(timezone.utc) - t0).total_seconds()))
print("done", flush=True)
