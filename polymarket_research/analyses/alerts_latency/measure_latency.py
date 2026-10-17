"""Measure how quickly executed trades become visible on public read-only channels.

    cd polymarket_research && python analyses/alerts_latency/measure_latency.py [--seconds 75]

1. Data API first visibility: poll the global /v2/trades feed every 1 s (and the
   /v2/activity feed of the three most active wallets every ~3-4 s) with a
   cache-busting parameter, and record first_seen(local) - block timestamp.
   This includes up to one polling interval of sampling delay and the
   integer-second truncation of block timestamps.
2. RTDS websocket (wss://ws-live-data.polymarket.com, topic activity/trades):
   receive time vs the Data API block timestamp of the same transaction hash.

Read-only, unauthenticated. Requires a synchronised local clock (NTP).
Results quoted in alerts/README.md were measured on 2026-10-17 around 15:10-15:50 UTC.
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import json
import time

import requests
import websockets

DATA = "https://data-api.polymarket.com"


def q(v: list[float]) -> dict:
    v = sorted(v)
    n = len(v)
    if not n:
        return {"n": 0}
    return {"n": n, "p10": round(v[n // 10], 2), "p50": round(v[n // 2], 2), "p90": round(v[int(n * 0.9)], 2),
            "max": round(v[-1], 2), "min": round(v[0], 2)}


def data_api_visibility(seconds: float) -> dict:
    s = requests.Session()
    g = s.get(f"{DATA}/v2/trades", params={"limit": 500, "_cb": str(time.time())}, timeout=30).json()["data"]
    wallets = [w for w, _ in collections.Counter(x["proxy_wallet"] for x in g).most_common(3)]
    seen: set = set()
    useen: set = set()
    lag_g: list[float] = []
    lag_u: list[float] = []
    first, i, t_end = True, 0, time.time() + seconds
    while time.time() < t_end:
        t0 = time.time()
        for x in s.get(f"{DATA}/v2/trades", params={"limit": 200, "_cb": f"{t0:.3f}"}, timeout=30).json()["data"]:
            k = (x["transaction_hash"], x["proxy_wallet"], x["token_id"], x["size"], x["price"])
            if k not in seen:
                seen.add(k)
                if not first:
                    lag_g.append(time.time() - x["timestamp"])
        if i % 3 == 0:
            for w in wallets:
                r = s.get(f"{DATA}/v2/activity", params={"user": w, "type": "TRADE", "limit": 100,
                                                       "end": int(time.time()) + 86400}, timeout=30).json()["data"]
                for x in r:
                    k = (w, x["transaction_hash"], x["token_id"], x["size"], x["price"], x["side"])
                    if k not in useen:
                        useen.add(k)
                        if not first:
                            lag_u.append(time.time() - x["timestamp"])
        first = False
        i += 1
        time.sleep(max(0.0, 1.0 - (time.time() - t0)))
    return {"global_trades_first_visibility_s": q(lag_g), "user_activity_first_visibility_s": q(lag_u)}


async def _rtds(seconds: float) -> list[tuple[float, dict]]:
    out = []
    async with websockets.connect("wss://ws-live-data.polymarket.com", open_timeout=10) as ws:
        await ws.send(json.dumps({"action": "subscribe", "subscriptions": [{"topic": "activity", "type": "trades"}]}))
        t0 = time.time()
        while time.time() - t0 < seconds:
            try:
                m = await asyncio.wait_for(ws.recv(), timeout=5)
            except asyncio.TimeoutError:
                continue
            try:
                j = json.loads(m)
            except (ValueError, TypeError):
                continue
            if isinstance(j, dict) and isinstance(j.get("payload"), dict):
                out.append((time.time(), j["payload"]))
    return out


def rtds_vs_block(seconds: float) -> dict:
    msgs = asyncio.run(_rtds(seconds))
    time.sleep(20)
    byw: dict[str, list] = collections.defaultdict(list)
    for t, p in msgs:
        byw[p["proxyWallet"].lower()].append((t, p))
    s = requests.Session()
    recv_minus_block, block_minus_payload, missing = [], [], 0
    for w, items in sorted(byw.items(), key=lambda kv: -len(kv[1]))[:8]:
        start = min(p["timestamp"] for _, p in items) - 60
        rows = s.get(f"{DATA}/v2/activity", params={"user": w, "type": "TRADE", "start": start, "limit": 1000,
                                                   "end": int(time.time()) + 86400}, timeout=30).json()["data"]
        block = {x["transaction_hash"].lower(): x["timestamp"] for x in rows}
        for t, p in items:
            b = block.get(p["transactionHash"].lower())
            if b is None:
                missing += 1
            else:
                recv_minus_block.append(t - b)
                block_minus_payload.append(b - p["timestamp"])
    return {"rtds_messages": len(msgs), "matched_in_data_api": len(recv_minus_block), "not_found_after_20s": missing,
            "rtds_receive_minus_block_ts_s": q(recv_minus_block),
            "block_ts_minus_rtds_payload_ts_s": q(block_minus_payload)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=75)
    a = ap.parse_args()
    res = {"measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    res.update(data_api_visibility(a.seconds))
    res.update(rtds_vs_block(min(a.seconds, 25)))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
