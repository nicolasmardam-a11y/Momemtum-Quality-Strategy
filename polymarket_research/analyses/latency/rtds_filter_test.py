import asyncio, json, time, collections, websockets
URL = "wss://ws-live-data.polymarket.com"
async def listen(frames, secs):
    c = collections.Counter()
    async with websockets.connect(URL, open_timeout=30, ping_interval=None, max_size=None, proxy=True) as ws:
        for f in frames:
            await ws.send(json.dumps(f))
        t_end = time.monotonic() + secs; last = time.monotonic()
        while time.monotonic() < t_end:
            if time.monotonic() - last > 5:
                await ws.send("PING"); last = time.monotonic()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                continue
            try:
                m = json.loads(raw)
            except Exception:
                continue
            c[(m.get("payload") or {}).get("slug")] += 1
    return dict(c)
def sub(slug, compact=True):
    f = json.dumps({"market_slug": slug}, separators=(",", ":")) if compact else json.dumps({"market_slug": slug})
    return {"topic": "activity", "type": "trades", "filters": f}
async def main():
    fh = await listen([{"action": "subscribe", "subscriptions": [{"topic": "activity", "type": "trades"}]}], 15)
    top = [s for s, _ in sorted(fh.items(), key=lambda x: -x[1]) if s][:2]
    a, b = top
    res = await asyncio.gather(
        listen([{"action": "subscribe", "subscriptions": [sub(a)]}, {"action": "subscribe", "subscriptions": [sub(b)]}], 40),
        listen([{"action": "subscribe", "subscriptions": [sub(a), sub(b)]}], 40),
        listen([{"action": "subscribe", "subscriptions": [sub(a)]}], 40),
        listen([{"action": "subscribe", "subscriptions": [sub(b)]}], 40),
        listen([{"action": "subscribe", "subscriptions": [sub(a, compact=False)]}], 40),
    )
    out = {"a": a, "b": b, "two_frames_one_conn": res[0], "one_frame_two_subs": res[1], "only_a": res[2], "only_b": res[3], "a_with_spaces": res[4]}
    print(json.dumps(out))
asyncio.run(main())
