"""Verifier check (read-only): RTDS activity filters with a positive control (market_slug) and wallet keys
(lowercase proxyWallet, user). One connection per subscription; 45 s."""
import asyncio, json, time, collections, websockets
RTDS = "wss://ws-live-data.polymarket.com"
async def conn(filters, sink, until):
    sub = {"topic": "activity", "type": "trades"}
    if filters is not None:
        sub["filters"] = json.dumps(filters, separators=(",", ":"))
    async with websockets.connect(RTDS, max_size=2**24) as ws:
        await ws.send(json.dumps({"action": "subscribe", "subscriptions": [sub]}))
        last = time.time()
        while time.time() < until:
            if time.time() - last > 5:
                await ws.send("PING"); last = time.time()
            try:
                m = await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                continue
            try:
                p = json.loads(m).get("payload")
            except Exception:
                continue
            if isinstance(p, dict) and p.get("transactionHash"):
                sink.append(p)
async def main():
    warm = []
    await conn(None, warm, time.time() + 15)
    w = collections.Counter(p["proxyWallet"] for p in warm).most_common(1)[0][0]
    slug = collections.Counter(p.get("slug") for p in warm if p.get("slug")).most_common(1)[0][0]
    until = time.time() + 45
    sinks = {k: [] for k in ["firehose", "market_slug", "proxyWallet_lower", "user_lower"]}
    await asyncio.gather(conn(None, sinks["firehose"], until), conn({"market_slug": slug}, sinks["market_slug"], until),
                         conn({"proxyWallet": w.lower()}, sinks["proxyWallet_lower"], until),
                         conn({"user": w.lower()}, sinks["user_lower"], until))
    fh = sinks["firehose"]
    print(json.dumps({"wallet": w, "slug": slug,
                      "firehose_rows": len(fh), "firehose_rows_wallet": sum(p["proxyWallet"].lower() == w.lower() for p in fh),
                      "firehose_rows_slug": sum(p.get("slug") == slug for p in fh),
                      "market_slug_conn_rows": len(sinks["market_slug"]),
                      "market_slug_conn_offtarget": sum(p.get("slug") != slug for p in sinks["market_slug"]),
                      "proxyWallet_lower_rows": len(sinks["proxyWallet_lower"]), "user_lower_rows": len(sinks["user_lower"])}, indent=1))
asyncio.run(main())
