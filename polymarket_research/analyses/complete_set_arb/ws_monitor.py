"""Real-time (websocket) monitor of near-miss neg-risk groups for (c)/(d)/(e) episodes (read-only).

Run from polymarket_research/ (background):
  nohup python -m analyses.complete_set_arb.ws_monitor <scan_groups.parquet> <minutes> > data/derived/complete_set_arb/ws.log 2>&1 &

Subscribes to the public CLOB market channel for the YES token of every tradable member of each group whose
REST top-of-book (d) edge, or (c) edge for exhaustive groups, was within 2% of break-even. The NO book is
the exact mirror of the YES book (verified on the REST scans), so YES bids give (d) == (e) and YES asks give (c).
Every raw message is appended to data/raw/clob_ws/live/<date>/ws_<conn>.jsonl.gz with receive time (provenance).
After every update the group's top-of-book net edges are recomputed; when positive, the depth-aware profile is
computed and an episode is opened; it closes when the edge is no longer positive.
Episodes -> data/derived/complete_set_arb/ws_episodes.parquet; per-group minute samples -> ws_samples.parquet.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import math
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import websockets

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import csa  # noqa: E402

OUT = ROOT / "data" / "derived" / "complete_set_arb"
RAW = ROOT / "data" / "raw" / "clob_ws" / "live" / datetime.now(timezone.utc).strftime("%Y%m%d")
RAW.mkdir(parents=True, exist_ok=True)
URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
PER_CONN = 500

books = {}            # asset -> {"bids": {p: s}, "asks": {p: s}, "ts": ms}
asset_group = {}      # asset -> group id
groups = {}           # gid -> dict(rows=[universe rows], exhaustive=bool, title)
episodes = []         # closed episodes
open_ep = {}          # (gid, type) -> episode dict
samples = []
stats = defaultdict(int)


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def as_levels(side, d):
    lv = [(p, s) for p, s in d.items() if s > 0]
    return sorted(lv, key=lambda t: t[0], reverse=(side == "bids"))


def edges(gid):
    g = groups[gid]
    sb, sa, ok_b, ok_a = 0.0, 0.0, True, True
    for r in g["rows"]:
        b = books.get(r["tokens"][0])
        if b is None:
            return None
        bids = [p for p, s in b["bids"].items() if s > 0]
        asks = [p for p, s in b["asks"].items() if s > 0]
        if bids:
            p = max(bids)
            sb += p - csa.fee_ps(p, r["fee_rate"], r["fee_exp"])
        if asks:
            p = min(asks)
            sa += p + csa.fee_ps(p, r["fee_rate"], r["fee_exp"])
        else:
            ok_a = False
    return {"d": sb - 1.0, "c": (1.0 - sa) if (ok_a and g["exhaustive"]) else -math.inf}


def depth_profile(gid, ty):
    g = groups[gid]
    if ty == "d":
        legs = [csa.leg_segments(as_levels("bids", books[r["tokens"][0]]["bids"]), r["fee_rate"], r["fee_exp"], "sell")
                for r in g["rows"]]
        segs, depth = csa.combine(legs, "sell", 1.0, False)
        return csa.profile(segs, depth, allow_beyond=True, beyond_value=-1.0)
    legs = [csa.leg_segments(as_levels("asks", books[r["tokens"][0]]["asks"]), r["fee_rate"], r["fee_exp"], "buy")
            for r in g["rows"]]
    segs, depth = csa.combine(legs, "buy", 1.0, True)
    return csa.profile(segs, depth)


def crossed_any(gid):
    for r in groups[gid]["rows"]:
        b = books.get(r["tokens"][0])
        if b:
            bids = [p for p, s in b["bids"].items() if s > 0]
            asks = [p for p, s in b["asks"].items() if s > 0]
            if bids and asks and max(bids) >= min(asks):
                return True
    return False


def on_update(gid, ts_ms, recv):
    e = edges(gid)
    if e is None:
        return
    for ty in ("d", "c"):
        key = (gid, ty)
        v = e[ty]
        if v > 0:
            prof = depth_profile(gid, ty)
            ep = open_ep.get(key)
            if ep is None:
                ep = open_ep[key] = {"gid": gid, "type": ty, "title": groups[gid]["title"], "start_ms": ts_ms,
                                     "start_recv": recv, "n_updates": 0, "max_edge0": v, "max_pmax": prof["pmax"],
                                     "max_qstar": prof["qstar"], "p100_at_max": prof.get("p100"),
                                     "crossed": crossed_any(gid), "n_legs": len(groups[gid]["rows"])}
                stats[f"open_{ty}"] += 1
            ep["n_updates"] += 1
            if prof["pmax"] > ep["max_pmax"]:
                ep.update(max_pmax=prof["pmax"], max_qstar=prof["qstar"], p100_at_max=prof.get("p100"))
            ep["max_edge0"] = max(ep["max_edge0"], v)
            ep["crossed"] = ep["crossed"] or crossed_any(gid)
        elif key in open_ep:
            ep = open_ep.pop(key)
            ep["end_ms"], ep["end_recv"] = ts_ms, recv
            ep["dur_s"] = (ts_ms - ep["start_ms"]) / 1000
            episodes.append(ep)


def apply(msg, recv):
    et = msg.get("event_type")
    if et == "book":
        a = msg["asset_id"]
        books[a] = {"bids": {float(x["price"]): float(x["size"]) for x in msg.get("bids") or []},
                    "asks": {float(x["price"]): float(x["size"]) for x in msg.get("asks") or []},
                    "ts": int(msg.get("timestamp") or 0)}
        stats["book"] += 1
        return [(asset_group.get(a), int(msg.get("timestamp") or 0))]
    if et == "price_change":
        out = []
        ts = int(msg.get("timestamp") or 0)
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
            out.append((asset_group.get(a), ts))
        stats["price_change"] += 1
        return out
    stats[et or "other"] += 1
    return []


async def conn(i, assets, t_end):
    path = RAW / f"ws_{datetime.now(timezone.utc):%H%M%S}_{i:02d}.jsonl.gz"
    f = gzip.open(path, "at")
    f.write(json.dumps({"meta": {"url": URL, "assets": assets, "opened_utc": datetime.now(timezone.utc).isoformat()}}) + "\n")
    while time.time() < t_end:
        try:
            async with websockets.connect(URL, ping_interval=None, max_size=2 ** 24) as ws:
                await ws.send(json.dumps({"assets_ids": assets, "type": "market"}))

                async def pinger():
                    while True:
                        await asyncio.sleep(10)
                        await ws.send("PING")
                pt = asyncio.create_task(pinger())
                try:
                    while time.time() < t_end:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        recv = time.time()
                        if raw == "PONG":
                            continue
                        f.write(json.dumps({"recv": recv, "msg": raw}) + "\n")
                        data = json.loads(raw)
                        for m in (data if isinstance(data, list) else [data]):
                            for gid, ts in apply(m, recv):
                                if gid:
                                    on_update(gid, ts or int(recv * 1000), recv)
                finally:
                    pt.cancel()
        except Exception as ex:
            log(f"conn {i} error {repr(ex)[:200]}; reconnecting")
            stats["reconnect"] += 1
            await asyncio.sleep(2)
    f.close()


async def reporter(t_end):
    while time.time() < t_end:
        await asyncio.sleep(60)
        now = time.time()
        for gid in groups:
            e = edges(gid)
            if e:
                samples.append({"t": now, "gid": gid, "d_edge0": e["d"], "c_edge0": e["c"]})
        flush()
        log(f"books {len(books)}/{len(asset_group)} stats {dict(stats)} open {len(open_ep)} closed {len(episodes)}")


TAG = sys.argv[3] if len(sys.argv) > 3 else "0"


def flush():
    eps = episodes + [dict(v, end_ms=None, dur_s=None, still_open=True) for v in open_ep.values()]
    if eps:
        pd.DataFrame(eps).assign(run=TAG).to_parquet(OUT / f"ws_episodes_{TAG}.parquet", index=False)
    if samples:
        pd.DataFrame(samples).assign(run=TAG).to_parquet(OUT / f"ws_samples_{TAG}.parquet", index=False)


async def main(groups_file, minutes):
    g = pd.read_parquet(groups_file)
    g = g[(g.n_trad >= 2) & ((g.d_edge0 > -0.02) | (g.exhaustive & (g.c_edge0 > -0.02)))]
    uv = max(OUT.glob("universe_v*.parquet"), key=lambda p: int(re.search(r"universe_v(\d+)", p.name).group(1)))
    u = pd.read_parquet(uv)
    u["tokens"] = u["tokens"].map(json.loads)
    u = u[u.nr_id.isin(set(g.nr_id))]
    for gid, x in u.groupby("nr_id"):
        rows = [r for r in x.to_dict("records") if csa.tradable(r)]
        if len(rows) < 2:
            continue
        ex = bool(g.loc[g.nr_id == gid, "exhaustive"].iloc[0])
        groups[gid] = {"rows": rows, "exhaustive": ex, "title": x.event_title.iloc[0]}
        for r in rows:
            asset_group[r["tokens"][0]] = gid
    assets = sorted(asset_group)
    log(f"monitoring {len(groups)} groups, {len(assets)} YES assets from {groups_file} / {uv.name}")
    t_end = time.time() + minutes * 60
    tasks = [conn(i, assets[j:j + PER_CONN], t_end) for i, j in enumerate(range(0, len(assets), PER_CONN))]
    await asyncio.gather(reporter(t_end), *tasks)
    flush()
    log("done", dict(stats))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], float(sys.argv[2])))
