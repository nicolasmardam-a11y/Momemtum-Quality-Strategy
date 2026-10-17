"""Live read-only collector: Polymarket crypto up/down + above-K books next to reference prices.

Run from polymarket_research/ (background):
  nohup python -m analyses.lead_lag.live_collect <minutes> <tag> > data/derived/lead_lag/live_<tag>.log 2>&1 &

Sources (all public, unauthenticated):
  * CLOB market WS  wss://ws-subscriptions-clob.polymarket.com/ws/market  (book, price_change, best_bid_ask, last_trade_price)
  * RTDS (legacy)   wss://ws-live-data.polymarket.com  topic crypto_prices_chainlink (Chainlink BTC/USD, ETH/USD spot stream,
                    1 value per second; the 5m/15m/4h markets resolve on the Chainlink *TWAP-60s* stream, which is not public)
  * Binance         wss://data-stream.binance.vision  bookTicker + aggTrade BTCUSDT/ETHUSDT (hourly + above-K markets resolve on Binance)
  * Coinbase        wss://ws-feed.exchange.coinbase.com ticker BTC-USD/ETH-USD
Every raw frame is appended as "<local receive epoch>\t<raw frame>" to data/raw/lead_lag_live/<date>/<src>_<tag>_<part>.tsv.gz.
Compact derived tables (top-of-book changes, reference ticks, 1-second depth snapshots) are flushed to
data/derived/lead_lag/live_<tag>_{tob,ref,snap}_<part>.parquet every 5 minutes.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import websockets

from pmr import api

ROOT = Path(__file__).resolve().parents[2]
DER = ROOT / "data" / "derived" / "lead_lag"
RAW = ROOT / "data" / "raw" / "lead_lag_live" / datetime.now(timezone.utc).strftime("%Y%m%d")
DER.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)
MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 60
TAG = sys.argv[2] if len(sys.argv) > 2 else datetime.now(timezone.utc).strftime("%H%M")
T_END = time.time() + MINUTES * 60

books: dict[str, dict] = {}
tob_rows, ref_rows, snap_rows = [], [], []
last_tob: dict[str, tuple] = {}
ref_last: dict[str, dict] = {}
stats = defaultdict(int)
part = 0
raw_files: dict[str, gzip.GzipFile] = {}


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def raw_write(src, recv, raw):
    f = raw_files.get(src)
    if f is None:
        f = raw_files[src] = gzip.open(RAW / f"{src}_{TAG}_{part:02d}.tsv.gz", "at", compresslevel=1)
    f.write(f"{recv:.6f}\t{raw}\n")


# ----------------------------------------------------------------------------- market discovery
PAT = re.compile(r"^(btc|eth)-updown-(5m|15m|4h)-\d+$|^(bitcoin|ethereum)-up-or-down-[a-z]+-\d+-\d{4}-\d+(am|pm)-et$"
                 r"|^(bitcoin|ethereum)-above-[\dk]+-on-[a-z]+-\d+-\d{4}-\d+(am|pm)-et$")


def discover():
    now = datetime.now(timezone.utc)
    t_end = now + timedelta(minutes=MINUTES)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    ms = api.gamma_markets(closed="false", end_date_min=now.strftime(fmt),
                           end_date_max=(t_end + timedelta(hours=4, minutes=5)).strftime(fmt), max_pages=200)
    spot = {}
    for sym in ("BTCUSDT", "ETHUSDT"):
        j = api.request_json("https://data-api.binance.vision/api/v3/ticker/price", {"symbol": sym}, source="binance")
        spot["bitcoin" if sym.startswith("BTC") else "ethereum"] = float(j["price"])
    out = []
    for m in ms:
        s = m.get("slug", "")
        if not PAT.match(s):
            continue
        start = m.get("eventStartTime") or m.get("startDate")
        end = m.get("endDate")
        st = pd.Timestamp(start) if start else None
        en = pd.Timestamp(end)
        kind = ("above" if "-above-" in s else "1h" if "up-or-down" in s else s.split("-")[2])
        asset = "bitcoin" if s.startswith(("btc", "bitcoin")) else "ethereum"
        if kind in ("5m", "15m", "1h", "4h"):
            # window must overlap the collection window
            if st is None or st.timestamp() > T_END or en.timestamp() < time.time():
                continue
        else:  # hourly above-K (Binance 1h close): expiries inside the window, strikes within +-1.5% of spot
            mk = re.search(r"above-([\d]+)(k?)-on", s)
            k = float(mk.group(1)) * (1000 if mk.group(2) else 1)
            if abs(k / spot[asset] - 1) > 0.015 or en.timestamp() > T_END + 60:
                continue
        toks = api.jlist(m.get("clobTokenIds"))
        outs = api.jlist(m.get("outcomes"))
        out.append(dict(slug=s, kind=kind, asset=asset, condition=m.get("conditionId"), start=start, end=end,
                        tokens=toks, outcomes=outs, fee=m.get("feeSchedule"), feeType=m.get("feeType"),
                        tick=m.get("orderPriceMinTickSize"), minsize=m.get("orderMinSize"),
                        rewardsMaxSpread=m.get("rewardsMaxSpread"), rewardsMinSize=m.get("rewardsMinSize")))
    return out, spot


# ----------------------------------------------------------------------------- CLOB book state
def top(a):
    b = books.get(a)
    if not b:
        return None
    bids = [p for p, s in b["bids"].items() if s > 0]
    asks = [p for p, s in b["asks"].items() if s > 0]
    bb = max(bids) if bids else None
    ba = min(asks) if asks else None
    return bb, (b["bids"][bb] if bb is not None else 0.0), ba, (b["asks"][ba] if ba is not None else 0.0)


def note_tob(a, ts, recv):
    t = top(a)
    if t is None:
        return
    if last_tob.get(a) != t:
        last_tob[a] = t
        tob_rows.append((recv, ts, a, *t))


def apply(msg, recv):
    et = msg.get("event_type")
    ts = int(msg.get("timestamp") or 0)
    if et == "book":
        a = msg["asset_id"]
        books[a] = {"bids": {float(x["price"]): float(x["size"]) for x in msg.get("bids") or []},
                    "asks": {float(x["price"]): float(x["size"]) for x in msg.get("asks") or []}, "ts": ts}
        note_tob(a, ts, recv)
    elif et == "price_change":
        touched = set()
        for pc in msg.get("price_changes") or []:
            a = pc["asset_id"]
            b = books.get(a)
            if b is None:
                continue
            side = "bids" if pc["side"] == "BUY" else "asks"
            p, s = float(pc["price"]), float(pc["size"])
            if s <= 0:
                b[side].pop(p, None)
            else:
                b[side][p] = s
            b["ts"] = ts
            touched.add(a)
        for a in touched:
            note_tob(a, ts, recv)
    elif et == "last_trade_price":
        tob_rows.append((recv, ts, msg.get("asset_id"), None, None, float(msg.get("price") or 0), float(msg.get("size") or 0)))
        stats["trade"] += 1
    stats[et or "other"] += 1


async def clob_conn(assets):
    url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    while time.time() < T_END:
        try:
            async with websockets.connect(url, ping_interval=None, max_size=2 ** 24, max_queue=None, proxy=True, open_timeout=30) as ws:
                await ws.send(json.dumps({"assets_ids": assets, "type": "market", "custom_feature_enabled": False}))

                async def pinger():
                    while True:
                        await asyncio.sleep(10)
                        await ws.send("PING")
                pt = asyncio.create_task(pinger())
                try:
                    while time.time() < T_END:
                        raw = await asyncio.wait_for(ws.recv(), timeout=max(1.0, min(60.0, T_END - time.time())))
                        recv = time.time()
                        if raw == "PONG":
                            continue
                        raw_write("clob", recv, raw)
                        data = json.loads(raw)
                        for m in (data if isinstance(data, list) else [data]):
                            apply(m, recv)
                finally:
                    pt.cancel()
        except Exception as ex:
            log("clob error", repr(ex)[:200])
            stats["clob_reconnect"] += 1
            await asyncio.sleep(2)


# ----------------------------------------------------------------------------- reference feeds
def add_ref(src, sym, recv, price, src_ts, bid=None, ask=None):
    ref_rows.append((recv, src, sym, price, src_ts, bid, ask))
    ref_last[f"{src}:{sym}"] = {"recv": recv, "p": price, "ts": src_ts, "bid": bid, "ask": ask}


async def generic(name, url, sub_msgs, handler, ping=None):
    while time.time() < T_END:
        try:
            async with websockets.connect(url, open_timeout=30, max_size=2 ** 24, max_queue=None, proxy=True,
                                          ping_interval=None if ping else 20) as ws:
                for s in sub_msgs:
                    await ws.send(json.dumps(s))
                last = time.monotonic()
                while time.time() < T_END:
                    if ping and time.monotonic() - last > ping:
                        await ws.send("PING")
                        last = time.monotonic()
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        continue
                    recv = time.time()
                    raw_write(name, recv, raw)
                    try:
                        handler(json.loads(raw), recv)
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                        stats[f"{name}_unparsed"] += 1
        except Exception as ex:
            log(name, "error", repr(ex)[:200])
            stats[f"{name}_reconnect"] += 1
            await asyncio.sleep(2)


def h_rtds(m, recv):
    p = m.get("payload") or {}
    if "data" in p and isinstance(p["data"], list):  # initial history batch for a filtered symbol
        return
    sym = p.get("symbol")
    if sym and p.get("value") is not None:
        add_ref("chainlink", sym, recv, float(p["value"]), int(p.get("timestamp") or 0))
        stats["chainlink"] += 1


def h_binance(m, recv):
    d = m.get("data") or {}
    st = m.get("stream", "")
    if st.endswith("@bookTicker"):
        b, a = float(d["b"]), float(d["a"])
        add_ref("binance_bt", d["s"], recv, (b + a) / 2, 0, b, a)
        stats["binance_bt"] += 1
    elif st.endswith("@aggTrade"):
        add_ref("binance_tr", d["s"], recv, float(d["p"]), int(d["T"]))
        stats["binance_tr"] += 1


def h_coinbase(m, recv):
    if m.get("type") == "ticker":
        ts = int(pd.Timestamp(m["time"]).timestamp() * 1000) if m.get("time") else 0
        add_ref("coinbase", m["product_id"], recv, float(m["price"]), ts,
                float(m.get("best_bid") or 0) or None, float(m.get("best_ask") or 0) or None)
        stats["coinbase"] += 1


# ----------------------------------------------------------------------------- sampler + flush
def depth(a, side, within):
    b = books.get(a)
    if not b:
        return 0.0
    lv = [(p, s) for p, s in b[side].items() if s > 0]
    if not lv:
        return 0.0
    best = max(p for p, _ in lv) if side == "bids" else min(p for p, _ in lv)
    if side == "bids":
        return sum(s for p, s in lv if p >= best - within - 1e-9)
    return sum(s for p, s in lv if p <= best + within + 1e-9)


async def sampler(assets):
    while time.time() < T_END:
        await asyncio.sleep(1.0 - (time.time() % 1.0))
        now = time.time()
        for a in assets:
            t = top(a)
            if t is None:
                continue
            snap_rows.append((now, a, *t, depth(a, "bids", 0.01), depth(a, "asks", 0.01),
                              depth(a, "bids", 0.03), depth(a, "asks", 0.03)))


def flush(final=False):
    global part, tob_rows, ref_rows, snap_rows
    tag = f"{TAG}_{part:02d}"
    if tob_rows:
        pd.DataFrame(tob_rows, columns=["recv", "ts_ms", "asset", "bid", "bid_sz", "ask", "ask_sz"]).to_parquet(DER / f"live_{tag}_tob.parquet")
    if ref_rows:
        pd.DataFrame(ref_rows, columns=["recv", "src", "sym", "price", "src_ts", "bid", "ask"]).to_parquet(DER / f"live_{tag}_ref.parquet")
    if snap_rows:
        pd.DataFrame(snap_rows, columns=["t", "asset", "bid", "bid_sz", "ask", "ask_sz", "bid_d1", "ask_d1", "bid_d3", "ask_d3"]).to_parquet(DER / f"live_{tag}_snap.parquet")
    tob_rows, ref_rows, snap_rows = [], [], []
    for f in raw_files.values():
        f.close()
    raw_files.clear()
    part += 1


async def reporter():
    while time.time() < T_END:
        await asyncio.sleep(max(1.0, min(300.0, T_END - time.time())))
        flush()
        log("flushed part", part - 1, dict(stats), "books", len(books))


async def main():
    mk, spot = discover()
    meta = {"tag": TAG, "opened_utc": datetime.now(timezone.utc).isoformat(), "minutes": MINUTES, "spot": spot, "markets": mk}
    json.dump(meta, open(DER / f"live_{TAG}_markets.json", "w"), indent=1, default=str)
    assets = [t for m in mk for t in m["tokens"]]
    log("markets", len(mk), {k: sum(1 for m in mk if m["kind"] == k) for k in ("5m", "15m", "1h", "4h", "above")}, "assets", len(assets))
    # one connection per market group of 2 tokens kept together; 6 connections
    nconn = 6
    chunks = [[t for i, m in enumerate(mk) if i % nconn == c for t in m["tokens"]] for c in range(nconn)]
    tasks = [clob_conn(ch) for ch in chunks if ch] + [sampler(assets), reporter(),
             generic("rtds", "wss://ws-live-data.polymarket.com",
                     [{"action": "subscribe", "subscriptions": [{"topic": "crypto_prices_chainlink", "type": "*", "filters": ""}]}],
                     h_rtds, ping=5),
             generic("binance", "wss://data-stream.binance.vision/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker/btcusdt@aggTrade/ethusdt@aggTrade",
                     [], h_binance),
             generic("coinbase", "wss://ws-feed.exchange.coinbase.com",
                     [{"type": "subscribe", "product_ids": ["BTC-USD", "ETH-USD"], "channels": ["ticker"]}], h_coinbase)]
    await asyncio.gather(*tasks)
    flush(final=True)
    log("done", dict(stats))


if __name__ == "__main__":
    asyncio.run(main())
