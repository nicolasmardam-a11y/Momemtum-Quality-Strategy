"""Match-to-chain settlement latency, measured read-only.

Subscribes to the public CLOB market WebSocket for the most active open markets,
records `last_trade_price` events (match timestamp in ms + transaction_hash), then
looks up each transaction's block on Polygon and computes block_time - match_time.
Also records any `tick_size_change` events seen. Block timestamps have 1 s resolution.

Usage: python analyses/mechanics/settlement_latency.py [seconds]
Output: data/derived/mechanics_settlement_latency_<UTC>.parquet
"""
from __future__ import annotations

import asyncio
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

WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


async def listen(asset_ids: list[str], seconds: int) -> list[dict]:
    events = []
    async with websockets.connect(WS, open_timeout=30, ping_interval=None, max_size=None,
                                  proxy=True) as ws:
        await ws.send(json.dumps({"assets_ids": asset_ids, "type": "market"}))
        t_end = time.monotonic() + seconds
        last_ping = time.monotonic()
        while time.monotonic() < t_end:
            if time.monotonic() - last_ping > 9:
                await ws.send("PING")
                last_ping = time.monotonic()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                continue
            recv_ms = int(time.time() * 1000)
            if raw in ("PONG", "pong"):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for e in msg if isinstance(msg, list) else [msg]:
                if e.get("event_type") in ("last_trade_price", "tick_size_change"):
                    e["recv_ms"] = recv_ms
                    events.append(e)
    return events


def main() -> None:
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    ms = list(api.gamma_keyset("markets", {"closed": "false", "limit": 100, "order": "volume24hr", "ascending": "false"}, max_pages=1))
    ids = []
    for m in ms[:60]:
        ids += (m.get("positionIds") if m.get("version") == "v2" else api.jlist(m.get("clobTokenIds"))) or []
    events = asyncio.run(listen(ids, seconds))
    trades = [e for e in events if e.get("event_type") == "last_trade_price"]
    print("events", len(events), "trades", len(trades), "tick changes", len(events) - len(trades))
    blocks: dict[str, int] = {}
    rows = []
    for e in trades:
        h = e.get("transaction_hash") or ""
        row = {"asset_id": e.get("asset_id"), "market": e.get("market"), "price": e.get("price"), "size": e.get("size"),
               "side": e.get("side"), "match_ms": int(e.get("timestamp") or 0), "recv_ms": e["recv_ms"], "tx": h}
        if h.startswith("0x") and len(h) == 66:
            try:
                rc = api.rpc("eth_getTransactionReceipt", [h])
                if rc:
                    bn = rc["blockNumber"]
                    if bn not in blocks:
                        blocks[bn] = int(api.rpc("eth_getBlockByNumber", [bn, False])["timestamp"], 16)
                    row["block"] = int(bn, 16)
                    row["block_ts"] = blocks[bn]
                    row["status"] = rc.get("status")
                    row["to"] = rc.get("to")
                    row["gas_used"] = int(rc.get("gasUsed", "0x0"), 16)
                    row["eff_gas_price_gwei"] = int(rc.get("effectiveGasPrice", "0x0"), 16) / 1e9
            except Exception as ex:  # keep going; record the failure
                row["err"] = str(ex)[:120]
        rows.append(row)
    df = pd.DataFrame(rows)
    if "block_ts" in df:
        df["latency_s"] = df["block_ts"] - df["match_ms"] / 1000
    out = ROOT / "data" / "derived" / f"mechanics_settlement_latency_{datetime.now(timezone.utc):%Y%m%dT%H%M}.parquet"
    df.to_parquet(out)
    print("->", out)
    if "latency_s" in df:
        d = df.dropna(subset=["latency_s"]).drop_duplicates("tx")
        print("unique tx with block:", len(d))
        print(d["latency_s"].describe(percentiles=[.1, .25, .5, .75, .9, .99]).to_string())
        print("gas_used per settlement tx:", d["gas_used"].describe().to_string())
        print("eff gas price gwei:", d["eff_gas_price_gwei"].describe().to_string())
        print("exchange contracts:", d["to"].value_counts().to_string())
    print("tx missing:", int((df["tx"] == "").sum()), "of", len(df))
    for e in events:
        if e.get("event_type") == "tick_size_change":
            print("tick change", e)


if __name__ == "__main__":
    main()
