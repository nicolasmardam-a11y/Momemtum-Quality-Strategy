"""Verifier check (read-only): first-seen minus row timestamp for /v2/trades?condition= polled every 2 s with a
cache-busting nonce (busted) vs identical URL (cached). Market = most active conditionId on the RTDS firehose."""
import asyncio, json, time, collections, statistics, websockets
from pmr.http import request_json
async def warm():
    rows = []
    async with websockets.connect("wss://ws-live-data.polymarket.com", max_size=2**24) as ws:
        await ws.send(json.dumps({"action": "subscribe", "subscriptions": [{"topic": "activity", "type": "trades"}]}))
        end = time.time() + 12
        while time.time() < end:
            try:
                p = json.loads(await asyncio.wait_for(ws.recv(), 1)).get("payload")
            except Exception:
                continue
            if isinstance(p, dict) and p.get("conditionId") and "updown-5m" not in (p.get("slug") or "") and "updown-15m" not in (p.get("slug") or ""):
                rows.append(p["conditionId"])
    return collections.Counter(rows).most_common(1)[0][0]
cid = asyncio.run(warm())
seen_b, seen_c = {}, {}
end = time.time() + 120
url = "https://data-api.polymarket.com/v2/trades"
while time.time() < end:
    for mode, seen in (("b", seen_b), ("c", seen_c)):
        p = {"condition": cid, "limit": 50}
        if mode == "b":
            p["_"] = str(time.time_ns())
        rows = request_json(url, p, source="data-api").get("data") or []
        t = time.time()
        for r in rows:
            k = (r["transaction_hash"], r["proxy_wallet"], r["token_id"], r["size"], r["price"])
            if k not in seen:
                seen[k] = (t, int(r["timestamp"]))
    time.sleep(max(0, 2 - 0.3))
t0 = min(v[1] for v in seen_b.values()) if seen_b else 0
start = end - 120
new_b = [t - ts for t, ts in seen_b.values() if ts > start + 5]
new_c = [t - ts for t, ts in seen_c.values() if ts > start + 5]
q = lambda x: {"n": len(x), "p50": round(statistics.median(x), 2), "p90": round(sorted(x)[int(.9 * len(x))], 2), "max": round(max(x), 2)} if x else None
out = {"condition": cid, "busted": q(new_b), "cached_identical_url": q(new_c)}
print(json.dumps(out))
json.dump(out, open("data/derived/verification_poll_latency.json", "w"))
