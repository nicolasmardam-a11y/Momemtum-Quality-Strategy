"""Read-only probe of public Polymarket WebSocket channels (no auth, no orders, no wallet).

Answers three questions left open by measure_latency.py:
  1. Does the legacy RTDS `activity` topic accept a server-side WALLET filter? Documented filters are only
     `event_slug` / `market_slug` (github.com/Polymarket/real-time-data-client README). We pick the most active
     wallet from a short firehose sample, then open one connection per candidate filter key
     (proxyWallet, user, wallet, maker, taker) next to an unfiltered firehose and compare.
  2. What does PolyBolt (wss://ws-live-v2.polymarket.com/ws) give an unauthenticated client?
     `price.polymarket` (BestBidAsk per asset_id) and a gated channel (`price.crypto`, expected auth_required).
  3. What does the public sports socket (wss://sports-api.polymarket.com/ws) push?

Usage:  python analyses/latency/ws_channels_probe.py [seconds]
Output: data/derived/ws_channels_probe_<UTC>.json
"""
from __future__ import annotations

import asyncio
import collections
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[2]
RTDS = "wss://ws-live-data.polymarket.com"
POLYBOLT = "wss://ws-live-v2.polymarket.com/ws"
SPORTS = "wss://sports-api.polymarket.com/ws"
RUN_S = int(sys.argv[1]) if len(sys.argv) > 1 else 60
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
OUT = ROOT / "data" / "derived" / f"ws_channels_probe_{STAMP}.json"


def compact(d: dict) -> str:
    return json.dumps(d, separators=(",", ":"))


async def rtds(sub: dict, seconds: float) -> dict:
    rows, stats, first_raw = [], collections.Counter(), []
    async with websockets.connect(RTDS, open_timeout=30, ping_interval=None, max_size=None, proxy=True) as ws:
        await ws.send(json.dumps({"action": "subscribe", "subscriptions": [sub]}))
        t_end, last = time.monotonic() + seconds, time.monotonic()
        while time.monotonic() < t_end:
            if time.monotonic() - last > 5:
                await ws.send("PING")
                last = time.monotonic()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                continue
            if not raw or raw in ("PONG", "pong"):
                stats["empty_or_pong"] += 1
                continue
            try:
                m = json.loads(raw)
            except json.JSONDecodeError:
                stats["nonjson"] += 1
                if len(first_raw) < 2:
                    first_raw.append(raw[:300])
                continue
            stats[f"{m.get('topic')}/{m.get('type')}"] += 1
            p = m.get("payload") or {}
            if isinstance(p, dict) and p.get("proxyWallet"):
                rows.append((p["proxyWallet"].lower(), (p.get("transactionHash") or "").lower()))
            elif len(first_raw) < 2:
                first_raw.append(raw[:300])
    return {"stats": dict(stats), "rows": rows, "non_trade_frames": first_raw}


async def polybolt(subs: list[dict], seconds: float) -> dict:
    frames = []
    async with websockets.connect(POLYBOLT, open_timeout=30, max_size=None, proxy=True) as ws:
        await ws.send(json.dumps({"op": "subscribe", "subscriptions": subs, "rid": "probe"}))
        t_end = time.monotonic() + seconds
        while time.monotonic() < t_end:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                continue
            except websockets.ConnectionClosed as e:
                frames.append({"closed": str(e)})
                break
            frames.append({"recv_ms": int(time.time() * 1000), "raw": raw[:400]})
    kinds = collections.Counter()
    for f in frames:
        try:
            m = json.loads(f.get("raw", "{}"))
            kinds[f"{m.get('op') or m.get('channel')}|{m.get('code', '')}|snapshot={m.get('snapshot', False)}"] += 1
        except json.JSONDecodeError:
            kinds["nonjson"] += 1
    return {"n_frames": len(frames), "kinds": dict(kinds), "examples": frames[:4]}


async def sports(seconds: float) -> dict:
    c, ex, n = collections.Counter(), [], 0
    async with websockets.connect(SPORTS, open_timeout=30, ping_interval=None, max_size=None, proxy=True) as ws:
        t_end = time.monotonic() + seconds
        while time.monotonic() < t_end:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                continue
            if raw in ("ping", "PING"):
                await ws.send("pong")
                c["ping"] += 1
                continue
            n += 1
            try:
                m = json.loads(raw)
                c[",".join(sorted(m.keys()))] += 1
                if len(ex) < 2:
                    ex.append(m)
            except json.JSONDecodeError:
                c["nonjson"] += 1
    return {"messages": n, "key_sets": dict(c), "examples": ex}


async def main() -> dict:
    t0 = datetime.now(timezone.utc).isoformat()
    sample = await rtds({"topic": "activity", "type": "trades"}, 20)
    cnt = collections.Counter(w for w, _ in sample["rows"])
    wallet, wn = cnt.most_common(1)[0]
    # an asset id for PolyBolt: take one from the Gamma top-volume open market
    import requests
    mk = requests.get("https://gamma-api.polymarket.com/markets",
                      params={"limit": 1, "closed": "false", "order": "volume24hr", "ascending": "false"}, timeout=30).json()[0]
    asset = json.loads(mk["clobTokenIds"])[0]
    cands = ["proxyWallet", "user", "wallet", "maker", "taker"]
    tasks = {"firehose": rtds({"topic": "activity", "type": "trades"}, RUN_S)}
    for k in cands:
        tasks[f"filter_{k}"] = rtds({"topic": "activity", "type": "trades", "filters": compact({k: wallet})}, RUN_S)
    tasks["polybolt_public"] = polybolt([{"channel": "price.polymarket", "filter": {"asset_id": asset}}], min(RUN_S, 40))
    tasks["polybolt_gated"] = polybolt([{"channel": "price.crypto", "filter": {"symbol": "btcusd"}}], 10)
    tasks["sports"] = sports(min(RUN_S, 40))
    res = dict(zip(tasks, await asyncio.gather(*tasks.values(), return_exceptions=True)))
    out = {"stamp": STAMP, "t_start_utc": t0, "run_s": RUN_S, "probe_wallet": wallet, "probe_wallet_rows_in_sample": wn,
           "polybolt_asset": asset, "polybolt_market": mk.get("slug")}
    fh = res["firehose"]
    fh_w = [r for r in fh["rows"] if r[0] == wallet] if isinstance(fh, dict) else []
    out["firehose"] = {"rows": len(fh["rows"]), "distinct_wallets": len({w for w, _ in fh["rows"]}), "probe_wallet_rows": len(fh_w),
                       "stats": fh["stats"]} if isinstance(fh, dict) else repr(fh)
    for k in cands:
        r = res[f"filter_{k}"]
        if not isinstance(r, dict):
            out[f"filter_{k}"] = repr(r)
            continue
        own = sum(1 for w, _ in r["rows"] if w == wallet)
        out[f"filter_{k}"] = {"rows": len(r["rows"]), "rows_of_probe_wallet": own, "rows_of_other_wallets": len(r["rows"]) - own,
                              "stats": r["stats"], "non_trade_frames": r["non_trade_frames"]}
    for k in ("polybolt_public", "polybolt_gated", "sports"):
        out[k] = res[k] if isinstance(res[k], dict) else repr(res[k])
    out["t_end_utc"] = datetime.now(timezone.utc).isoformat()
    return out


if __name__ == "__main__":
    o = asyncio.run(main())
    OUT.write_text(json.dumps(o, indent=1, default=str))
    print(json.dumps({k: (v if k not in ("sports", "polybolt_public") else {kk: vv for kk, vv in v.items() if kk != "examples"} if isinstance(v, dict) else v)
                      for k, v in o.items()}, default=str)[:4000])
