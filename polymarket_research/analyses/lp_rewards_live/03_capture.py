"""Read-only capture of the public CLOB market websocket + 60 s REST /books snapshots for the LP study.

Usage (background): nohup python -m analyses.lp_rewards_live.03_capture <minutes> <label> > data/derived/lp_rewards_live/capture_<label>.log 2>&1 &
Raw frames (with local receive time) -> data/raw/clob_ws/live/<date>/lp_<label>_<HHMMSS>.jsonl.gz (provenance).
REST snapshots -> data/derived/lp_rewards_live/rest_books_<label>.parquet (raw responses also kept by pmr.http).
"""
from __future__ import annotations

import asyncio
import gzip
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import websockets

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

OUT = ROOT / "data" / "derived" / "lp_rewards_live"
RAW = ROOT / "data" / "raw" / "clob_ws" / "live" / datetime.now(timezone.utc).strftime("%Y%m%d")
RAW.mkdir(parents=True, exist_ok=True)
URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
stats = {"frames": 0, "reconnects": 0}


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


async def ws_loop(assets, t_end, label):
    path = RAW / f"lp_{label}_{datetime.now(timezone.utc):%H%M%S}.jsonl.gz"
    f = gzip.open(path, "at")
    f.write(json.dumps({"meta": {"url": URL, "assets": assets, "opened_utc": datetime.now(timezone.utc).isoformat(),
                                 "sub": {"type": "market", "custom_feature_enabled": True}}}) + "\n")
    while time.time() < t_end:
        try:
            async with websockets.connect(URL, ping_interval=None, max_size=2 ** 24) as ws:
                await ws.send(json.dumps({"assets_ids": assets, "type": "market", "custom_feature_enabled": True}))
                f.write(json.dumps({"event": "subscribed", "recv": time.time()}) + "\n")

                async def pinger():
                    while True:
                        await asyncio.sleep(10)
                        await ws.send("PING")
                pt = asyncio.create_task(pinger())
                try:
                    while time.time() < t_end:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        if raw == "PONG":
                            continue
                        f.write(json.dumps({"recv": time.time(), "msg": raw}) + "\n")
                        stats["frames"] += 1
                finally:
                    pt.cancel()
        except Exception as ex:  # reconnect; the gap is logged so analysis can drop it
            stats["reconnects"] += 1
            f.write(json.dumps({"event": "disconnect", "recv": time.time(), "err": repr(ex)[:200]}) + "\n")
            log("ws error", repr(ex)[:200])
            await asyncio.sleep(2)
    f.close()


async def rest_loop(yes, no, t_end, label):
    rows, last_flush = [], time.time()
    k = 0
    while time.time() < t_end:
        t0 = time.time()
        try:
            toks = yes + (no if k % 10 == 0 else [])   # NO books every 10th round (mirror check)
            bs = await asyncio.to_thread(api.books, toks)
            for b in bs:
                rows.append({"snap_utc": t0, "asset_id": b["asset_id"], "market": b["market"], "ts_ms": b["timestamp_ms"],
                             "bids": json.dumps(b["bids"][:60]), "asks": json.dumps(b["asks"][:60]), "tick": b["tick_size"],
                             "min_order": b["min_order_size"], "ltp": b["last_trade_price"]})
        except Exception as ex:
            log("rest error", repr(ex)[:200])
        k += 1
        if time.time() - last_flush > 300:
            pd.DataFrame(rows).to_parquet(OUT / f"rest_books_{label}.parquet", index=False)
            last_flush = time.time()
            log(f"rest rounds={k} rows={len(rows)} ws_frames={stats['frames']} reconnects={stats['reconnects']}")
        await asyncio.sleep(max(1.0, 60 - (time.time() - t0)))
    pd.DataFrame(rows).to_parquet(OUT / f"rest_books_{label}.parquet", index=False)


async def main(minutes, label, mfile="ws_markets.parquet"):
    ws = pd.read_parquet(OUT / mfile)
    yes, no = ws.yes_token.tolist(), ws.no_token.tolist()
    t_end = time.time() + minutes * 60
    log(f"capture {label}: {len(ws)} markets, {len(yes) + len(no)} assets, {minutes} min")
    await asyncio.gather(ws_loop(yes + no, t_end, label), rest_loop(yes, no, t_end, label))
    log("done", stats)


if __name__ == "__main__":
    asyncio.run(main(float(sys.argv[1]), sys.argv[2], *(sys.argv[3:4])))
