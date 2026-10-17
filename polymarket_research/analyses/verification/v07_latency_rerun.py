"""Verifier re-measurement (read-only, no auth): detection latency of a trade by an arbitrary wallet.

Connections (all public):
  A  RTDS legacy wss://ws-live-data.polymarket.com, topic activity/trades, unfiltered firehose (wallet-attributed)
  B  CLOB market WS wss://ws-subscriptions-clob.polymarket.com/ws/market on the most active assets seen on A in the
     first WARM seconds; last_trade_price carries the match timestamp (ms) and transaction_hash
  C  RTDS activity/trades with filters {"proxyWallet": <most active wallet>} (wallet-filter test)
Afterwards: Polygon block timestamps of a sample of tx hashes (eth_getTransactionReceipt + eth_getBlockByNumber).
Formats from docs /market-data/realtime-data and the RTDS client README (Polymarket/real-time-data-client).
"""
import asyncio
import collections
import json
import statistics
import sys
import time

import websockets

from pmr import api

RUN = int(sys.argv[1]) if len(sys.argv) > 1 else 180
WARM = 20
RTDS = "wss://ws-live-data.polymarket.com"
CLOB = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

rtds_rows = []      # (recv, payload)
clob_ltp = []       # (recv, msg)
filt_rows = []
state = {"assets": None, "wallet": None}


async def pinger(ws, every):
    while True:
        await asyncio.sleep(every)
        try:
            await ws.send("PING")
        except Exception:
            return


async def rtds(sink, filters=None, start_after=0, until=None):
    await asyncio.sleep(start_after)
    sub = {"topic": "activity", "type": "trades"}
    if filters:
        sub["filters"] = json.dumps(filters, separators=(",", ":"))
    async with websockets.connect(RTDS, max_size=2 ** 24) as ws:
        await ws.send(json.dumps({"action": "subscribe", "subscriptions": [sub]}))
        pt = asyncio.create_task(pinger(ws, 5))
        try:
            while time.time() < until:
                try:
                    m = await asyncio.wait_for(ws.recv(), timeout=2)
                except asyncio.TimeoutError:
                    continue
                t = time.time()
                if not m or m in ("PONG", "pong"):
                    continue
                try:
                    j = json.loads(m)
                except json.JSONDecodeError:
                    continue
                p = j.get("payload")
                if isinstance(p, dict) and p.get("transactionHash"):
                    sink.append((t, p))
        finally:
            pt.cancel()


async def clob(until):
    await asyncio.sleep(WARM)
    cnt = collections.Counter(p.get("asset") for _, p in rtds_rows if p.get("asset"))
    assets = [a for a, _ in cnt.most_common(10)]
    state["assets"] = assets
    async with websockets.connect(CLOB, max_size=2 ** 24) as ws:
        await ws.send(json.dumps({"assets_ids": assets, "type": "market"}))
        pt = asyncio.create_task(pinger(ws, 10))
        try:
            while time.time() < until:
                try:
                    m = await asyncio.wait_for(ws.recv(), timeout=2)
                except asyncio.TimeoutError:
                    continue
                t = time.time()
                if not m or m == "PONG":
                    continue
                try:
                    j = json.loads(m)
                except json.JSONDecodeError:
                    continue
                for e in (j if isinstance(j, list) else [j]):
                    if isinstance(e, dict) and e.get("event_type") == "last_trade_price":
                        clob_ltp.append((t, e))
        finally:
            pt.cancel()


async def filt(until):
    await asyncio.sleep(WARM)
    cnt = collections.Counter(p.get("proxyWallet") for _, p in rtds_rows if p.get("proxyWallet"))
    w = cnt.most_common(1)[0][0]
    state["wallet"] = w
    await rtds(filt_rows, filters={"proxyWallet": w}, until=until)


async def main():
    until = time.time() + RUN
    await asyncio.gather(rtds(rtds_rows, until=until), clob(until), filt(until))


asyncio.run(main())
t_end = time.time()

# ---- analysis
first_rtds = {}
for t, p in rtds_rows:
    h = p["transactionHash"].lower()
    first_rtds.setdefault(h, (t, p))
ltp = {}
for t, e in clob_ltp:
    h = (e.get("transaction_hash") or "").lower()
    if h:
        ltp.setdefault(h, (t, e))
joined = [(h, ltp[h], first_rtds[h]) for h in ltp if h in first_rtds]
clob_lat = [t - int(e["timestamp"]) / 1000 for t, e in ltp.values()]
rtds_lat = [r[0] - int(e["timestamp"]) / 1000 for _, (t, e), r in joined]
rtds_vs_payload = [t - int(p["timestamp"]) for t, p in first_rtds.values() if p.get("timestamp")]
# block timestamps for a sample
blk = []
for h, (t, e), r in joined[:40]:
    rc = api.rpc("eth_getTransactionReceipt", [h])
    if not rc:
        continue
    b = api.rpc("eth_getBlockByNumber", [rc["blockNumber"], False])
    bts = int(b["timestamp"], 16)
    blk.append({"match_to_block": bts - int(e["timestamp"]) / 1000, "rtds_recv_minus_block": r[0] - bts,
                "rtds_payload_ts_minus_block": int(r[1]["timestamp"]) - bts, "to": rc.get("to")})
w = state["wallet"]
w_on_firehose = sum(1 for t, p in rtds_rows if p.get("proxyWallet") == w and t > time.time() - RUN + WARM)


def q(x, ps=(0.1, 0.5, 0.9)):
    if not x:
        return None
    s = sorted(x)
    return {f"p{int(p * 100)}": round(s[min(len(s) - 1, int(p * len(s)))], 3) for p in ps} | {"n": len(s), "max": round(s[-1], 3)}


keys = collections.Counter(k for _, p in rtds_rows[:2000] for k in p.keys())
summary = {
    "run_s": RUN, "utc_end": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_end)),
    "rtds_rows": len(rtds_rows), "rtds_rows_per_s": round(len(rtds_rows) / RUN, 1),
    "rtds_payload_keys": sorted(keys), "rtds_rows_with_proxyWallet": sum(1 for _, p in rtds_rows if p.get("proxyWallet")),
    "clob_ltp": len(clob_ltp), "clob_ltp_with_txhash": len(ltp), "joined": len(joined),
    "lat_clob_ws_from_match": q(clob_lat), "lat_rtds_from_match": q(rtds_lat),
    "rtds_recv_minus_payload_ts": q(rtds_vs_payload),
    "match_to_block": q([b["match_to_block"] for b in blk]),
    "rtds_recv_minus_block": q([b["rtds_recv_minus_block"] for b in blk]),
    "rtds_payload_ts_minus_block": q([b["rtds_payload_ts_minus_block"] for b in blk]),
    "settlement_to_addresses": dict(collections.Counter(b["to"] for b in blk)),
    "wallet_filter_test": {"wallet": w, "rows_on_filtered_conn": len(filt_rows), "rows_on_firehose_after_warm": w_on_firehose},
}
print(json.dumps(summary, indent=1))
json.dump(summary, open(f"data/derived/verification_latency_rerun_{time.strftime('%Y%m%dT%H%M', time.gmtime())}.json", "w"), indent=1)
