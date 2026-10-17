"""Probe the undocumented 'level' (1/2/3) subscription option of the public market websocket (read-only).
Usage: python -m analyses.lp_rewards_live.00_ws_level_probe <asset_id> [seconds]
Records event types and field names per level; raw frames -> data/raw/clob_ws/live/<date>/lp_levelprobe_L<k>.jsonl.gz
"""
import asyncio, gzip, json, sys, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import websockets

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/clob_ws/live" / datetime.now(timezone.utc).strftime("%Y%m%d"); RAW.mkdir(parents=True, exist_ok=True)
URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


async def run(asset, level, secs):
    c, fields = Counter(), {}
    with gzip.open(RAW / f"lp_levelprobe_L{level}.jsonl.gz", "at") as f:
        async with websockets.connect(URL, ping_interval=None, max_size=2**24) as ws:
            await ws.send(json.dumps({"assets_ids": [asset], "type": "market", "level": level, "custom_feature_enabled": True}))
            t0 = time.time()
            while time.time() - t0 < secs:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    await ws.send("PING"); continue
                f.write(json.dumps({"recv": time.time(), "msg": raw}) + "\n")
                if raw in ("PONG",):
                    continue
                try:
                    d = json.loads(raw)
                except Exception:
                    c["nonjson:" + raw[:40]] += 1; continue
                for m in d if isinstance(d, list) else [d]:
                    et = m.get("event_type", "?"); c[et] += 1
                    ks = set(m.keys())
                    if et == "price_change" and m.get("price_changes"):
                        ks |= {"pc." + k for k in m["price_changes"][0].keys()}
                    if et == "book":
                        ks |= {"bid." + k for k in (m.get("bids") or [{}])[0].keys()}
                    fields.setdefault(et, set()).update(ks)
    print("level", level, dict(c)); [print("  ", k, sorted(v)) for k, v in fields.items()]


if __name__ == "__main__":
    a = sys.argv[1]; s = float(sys.argv[2]) if len(sys.argv) > 2 else 20
    for lv in (1, 3):
        asyncio.run(run(a, lv, s))
