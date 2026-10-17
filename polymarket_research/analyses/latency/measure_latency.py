"""Detection latency of public Polymarket trade data, measured read-only.

What it does (no auth, no orders, no wallet):
  1. Samples the public RTDS `activity/trades` firehose for SELECT_S seconds, counts trades per
     market and per wallet, and picks the N most active markets that do not expire during the run
     (5-minute / 15-minute crypto up-down markets are excluded because they roll over) plus the
     N_WALLETS most active wallets.
  2. For RUN_S seconds, in parallel:
       a. polls Data API `GET /v2/trades?condition=<id>&limit=50` (default taker_only=true) for each
          market every POLL_S seconds in two modes:
            - "cached": the identical URL every time (what a naive poller does). The response carries
              `cache-control: public, max-age=300` and is served by CloudFront, so it can be stale.
            - "busted": the same request plus a unique `_=<nonce>` query parameter, which misses the
              edge cache (undocumented; verified 2026-10-17) and shows the origin's freshness.
          and `GET /v2/trades?user=<wallet>&limit=50` (busted) for the chosen wallets;
          recording request-send / response-receive UTC times and the `age` / `x-cache` headers;
       b. listens to the CLOB market WebSocket (`last_trade_price`: match time in ms + tx hash);
       c. listens to the legacy RTDS WebSocket `activity` topic, types `trades` and `orders_matched`,
          unfiltered (firehose, every row kept), plus one `market_slug`-filtered `trades` connection
          per chosen market (filters must be compact JSON; only the first subscription per connection was honoured);
       d. reads `/v2/status` (Data API freshness) every 30 s.
  3. After the run, pulls each chosen market's full tape for the window with taker_only=false
     (maker + taker rows) to check what the RTDS rows correspond to, and looks up a random sample of
     transaction hashes on Polygon (eth_getTransactionReceipt + eth_getBlockByNumber) to compare each
     source's timestamp with the block timestamp.

Clock: local times are time.time(). A clock bound is derived from RTDS envelope timestamps (server ms)
versus receive time and saved in the summary.

Usage:  python analyses/latency/measure_latency.py [run_seconds] [n_markets] [n_wallets]
Output: data/derived/latency_<UTC>_{markets,wallets,dataapi,polls,clobws,rtds,rtds_filtered,tape,rpc,joined,status}.parquet
        data/derived/latency_<UTC>_summary.json
        data/raw/data-api/live/<YYYYMMDD>/latency_<UTC>_responses.json.gz (every poll response with URL, times, headers)
"""
from __future__ import annotations

import asyncio
import collections
import gzip
import json
import random
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import websockets

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

RTDS = "wss://ws-live-data.polymarket.com"
CLOB_WS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DATA = "https://data-api.polymarket.com"
OUT = ROOT / "data" / "derived"

RUN_S = int(sys.argv[1]) if len(sys.argv) > 1 else 600
N_MARKETS = int(sys.argv[2]) if len(sys.argv) > 2 else 5
N_WALLETS = int(sys.argv[3]) if len(sys.argv) > 3 else 2
SELECT_S = 60
POLL_S = 2.0
RPC_SAMPLE = 160
EXCLUDE = r"updown-(?:5m|15m)|-5m-|-15m-"
NOW = datetime.now(timezone.utc)
STAMP = NOW.strftime("%Y%m%dT%H%M")
RAW_OUT = ROOT / "data" / "raw" / "data-api" / "live" / NOW.strftime("%Y%m%d") / f"latency_{STAMP}_responses.json.gz"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "pmr-research/0.1 (read-only public data; latency measurement)"


def now_ms() -> int:
    return int(time.time() * 1000)


def compact(d: dict) -> str:
    return json.dumps(d, separators=(",", ":"))


# ----------------------------------------------------------------------------- RTDS

async def rtds_listen(subs: list[dict], seconds: float, sink: list, tag: str) -> dict:
    """Legacy RTDS: text PING every 5 s; messages are {topic,type,timestamp(ms),payload}.
    Each subscription is sent in its own subscribe frame (several in one frame were not all honoured)."""
    stats = collections.Counter()
    async with websockets.connect(RTDS, open_timeout=30, ping_interval=None, max_size=None, proxy=True) as ws:
        for s in subs:
            await ws.send(json.dumps({"action": "subscribe", "subscriptions": [s]}))
        t_end, last = time.monotonic() + seconds, time.monotonic()
        while time.monotonic() < t_end:
            if time.monotonic() - last > 5:
                await ws.send("PING")
                last = time.monotonic()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                continue
            recv = now_ms()
            if not raw or raw in ("PONG", "pong"):
                stats["empty_or_pong"] += 1
                continue
            try:
                m = json.loads(raw)
            except json.JSONDecodeError:
                stats["nonjson"] += 1
                continue
            stats[f"{m.get('topic')}/{m.get('type')}"] += 1
            p = m.get("payload") or {}
            if not isinstance(p, dict):
                continue
            sink.append({"tag": tag, "type": m.get("type"), "recv_ms": recv, "env_ts_ms": m.get("timestamp"),
                         "ts": p.get("timestamp"), "condition_id": p.get("conditionId"), "asset": p.get("asset"),
                         "slug": p.get("slug"), "event_slug": p.get("eventSlug"), "wallet": (p.get("proxyWallet") or "").lower(),
                         "side": p.get("side"), "price": p.get("price"), "size": p.get("size"), "fee": p.get("fee"),
                         "outcome_index": p.get("outcomeIndex"), "outcome": p.get("outcome"), "title": p.get("title"),
                         "tx": (p.get("transactionHash") or "").lower(), "name": p.get("name"),
                         "keys": ",".join(sorted(p.keys()))})
    return dict(stats)


# ----------------------------------------------------------------------------- CLOB market WS

async def clob_listen(asset_ids: list[str], seconds: float, sink: list) -> dict:
    stats = collections.Counter()
    async with websockets.connect(CLOB_WS, open_timeout=30, ping_interval=None, max_size=None, proxy=True) as ws:
        await ws.send(json.dumps({"assets_ids": asset_ids, "type": "market"}))
        t_end, last = time.monotonic() + seconds, time.monotonic()
        while time.monotonic() < t_end:
            if time.monotonic() - last > 9:
                await ws.send("PING")
                last = time.monotonic()
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2)
            except asyncio.TimeoutError:
                continue
            recv = now_ms()
            if raw in ("PONG", "pong"):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for e in msg if isinstance(msg, list) else [msg]:
                et = e.get("event_type")
                stats[et] += 1
                if et == "last_trade_price":
                    sink.append({"recv_ms": recv, "match_ms": int(e.get("timestamp") or 0), "asset": e.get("asset_id"),
                                 "condition_id": e.get("market"), "price": e.get("price"), "size": e.get("size"),
                                 "side": e.get("side"), "fee_rate_bps": e.get("fee_rate_bps"),
                                 "tx": (e.get("transaction_hash") or "").lower(), "keys": ",".join(sorted(e.keys()))})
    return dict(stats)


# ----------------------------------------------------------------------------- Data API poller (thread)

def get(path: str, params: dict, raw_log: list) -> tuple[dict | None, dict]:
    t_req = time.time()
    meta = {"url": DATA + path, "params": params, "t_req": t_req}
    try:
        r = SESSION.get(DATA + path, params=params, timeout=20)
        meta.update(t_resp=time.time(), status=r.status_code, age=r.headers.get("age"), x_cache=r.headers.get("x-cache"),
                    cache_control=r.headers.get("cache-control"), trace=r.headers.get("x-trace-id"),
                    fetched_at_utc=datetime.now(timezone.utc).isoformat())
        body = r.json() if r.ok else None
        raw_log.append({"meta": meta, "body": body if body is not None else r.text[:500]})
        return body, meta
    except Exception as ex:
        meta.update(t_resp=time.time(), err=str(ex)[:200])
        raw_log.append({"meta": meta, "body": None})
        return None, meta


def poller(targets: list[dict], seconds: float, sink: list, polls: list, raw_log: list, stop: threading.Event) -> None:
    """targets: dicts with id, shape (condition|user), key, mode (cached|busted)."""
    seen = {t["id"]: collections.Counter() for t in targets}
    prev_req = {t["id"]: None for t in targets}
    first = {t["id"]: True for t in targets}
    t_end = time.monotonic() + seconds
    gap = POLL_S / max(1, len(targets))
    while time.monotonic() < t_end and not stop.is_set():
        cycle0 = time.monotonic()
        for i, t in enumerate(targets):
            # spread requests evenly over the cycle
            wait = cycle0 + i * gap - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            params = {t["shape"]: t["key"], "limit": 50}
            if t["mode"] == "busted":
                params["_"] = f"{time.time_ns()}"
            j, meta = get("/v2/trades", params, raw_log)
            rec = {"target": t["id"], "shape": t["shape"], "key": t["key"], "mode": t["mode"], **{k: meta.get(k) for k in
                   ("t_req", "t_resp", "status", "age", "x_cache", "cache_control", "err")}}
            if not j:
                polls.append(rec)
                continue
            rows = j.get("data") or []
            cnt, new = collections.Counter(), []
            for r in rows:
                k = (r.get("transaction_hash", "").lower(), (r.get("proxy_wallet") or "").lower(), r.get("token_id"),
                     r.get("side"), r.get("size"), r.get("price"), r.get("timestamp"))
                cnt[k] += 1
                if cnt[k] > seen[t["id"]][k]:
                    new.append(r)
            for k, v in cnt.items():
                seen[t["id"]][k] = max(seen[t["id"]][k], v)
            all_new = len(rows) > 0 and len(new) == len(rows) and not first[t["id"]]
            rec.update(n_rows=len(rows), n_new=len(new), all_new=all_new, baseline=first[t["id"]],
                       max_ts=max((r.get("timestamp") or 0) for r in rows) if rows else None)
            polls.append(rec)
            for r in new:
                sink.append({"target": t["id"], "shape": t["shape"], "mode": t["mode"], "t_req": meta["t_req"], "t_resp": meta["t_resp"],
                             "prev_req": prev_req[t["id"]], "baseline": first[t["id"]], "page_all_new": all_new, "age_hdr": meta.get("age"),
                             "ts": r.get("timestamp"), "tx": (r.get("transaction_hash") or "").lower(),
                             "wallet": (r.get("proxy_wallet") or "").lower(), "condition_id": r.get("condition_id"),
                             "asset": r.get("token_id"), "side": r.get("side"), "size": r.get("size"), "price": r.get("price"),
                             "outcome_index": r.get("outcome_index")})
            prev_req[t["id"]] = meta["t_req"]
            first[t["id"]] = False
        time.sleep(max(0.0, POLL_S - (time.monotonic() - cycle0)))


def status_poller(seconds: float, sink: list, raw_log: list, stop: threading.Event) -> None:
    t_end = time.monotonic() + seconds
    while time.monotonic() < t_end and not stop.is_set():
        j, meta = get("/v2/status", {"_": f"{time.time_ns()}"}, raw_log)
        d = (j or {}).get("data") or {}
        sink.append({"t": meta["t_req"], "age_seconds": d.get("age_seconds"),
                     "serving_lag_s": (d.get("serving") or {}).get("lag_seconds"),
                     "serving_worst": (d.get("serving") or {}).get("worst"),
                     "mechanisms": json.dumps((d.get("serving") or {}).get("mechanisms")),
                     "max_synced_block": (d.get("ingestion") or {}).get("max_synced_block"), "err": meta.get("err")})
        stop.wait(30)


# ----------------------------------------------------------------------------- selection

def select() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sample: list = []
    stats = asyncio.run(rtds_listen([{"topic": "activity", "type": "trades"}], SELECT_S, sample, "select"))
    df = pd.DataFrame(sample)
    print("selection firehose:", stats, "rows", len(df), "rows without conditionId", int((df.condition_id.fillna("") == "").sum()))
    ok = df[df.condition_id.fillna("").str.startswith("0x")]
    counts = (ok[~ok.slug.fillna("").str.contains(EXCLUDE) & ~ok.event_slug.fillna("").str.contains(EXCLUDE)]
              .groupby(["condition_id", "slug"]).size().sort_values(ascending=False))
    picked = []
    soon = pd.Timestamp.now(tz="UTC") + pd.Timedelta(seconds=RUN_S + 600)
    for (cid, slug), n in counts.head(40).items():
        ms = list(api.gamma_keyset("markets", {"condition_ids": cid, "limit": 5}, max_pages=1))
        if not ms:
            continue
        m = ms[0]
        end = pd.to_datetime(m.get("endDate"), utc=True, errors="coerce")
        if pd.notna(end) and end < soon and not m.get("gameStartTime"):
            continue  # expires during the run (sports markets keep trading past endDate until closed)
        picked.append({"condition_id": cid, "slug": slug, "question": m.get("question"), "n_trades_select": int(n),
                       "end_date": m.get("endDate"), "game_start": m.get("gameStartTime"), "seconds_delay": m.get("secondsDelay"),
                       "fee_type": m.get("feeType"), "neg_risk": m.get("negRisk"), "version": m.get("version"),
                       "asset_ids": json.dumps(api.jlist(m.get("clobTokenIds"))), "volume24hr": m.get("volume24hr")})
        if len(picked) >= N_MARKETS:
            break
    wal = (ok[ok.wallet.str.len() == 42].groupby("wallet").agg(n=("tx", "size"), markets=("condition_id", "nunique"),
                                                                 name=("name", "first")).sort_values("n", ascending=False))
    wal = wal.head(N_WALLETS).reset_index()
    return pd.DataFrame(picked), wal, df


# ----------------------------------------------------------------------------- main run

async def run_streams(mk: pd.DataFrame, clob_sink, rtds_sink, rtds_f_sink, stream_stats):
    assets = [a for s in mk.asset_ids for a in json.loads(s)]
    tasks: dict = {
        "clob": clob_listen(assets, RUN_S, clob_sink),
        "rtds_trades": rtds_listen([{"topic": "activity", "type": "trades"}], RUN_S, rtds_sink, "trades"),
        "rtds_matched": rtds_listen([{"topic": "activity", "type": "orders_matched"}], RUN_S, rtds_sink, "orders_matched"),
    }
    # one connection per filter: a second subscribe frame on the same connection was not honoured (tested 2026-10-17)
    for i, s in enumerate(mk.slug):
        tasks[f"rtds_filtered_{i}"] = rtds_listen([{"topic": "activity", "type": "trades", "filters": compact({"market_slug": s})}],
                                                 RUN_S, rtds_f_sink, f"filtered:{s}")
    res = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for k, r in zip(tasks, res):
        stream_stats[k] = r if isinstance(r, dict) else f"ERROR {r!r}"


def full_tape(cond: str, since: float, raw_log: list, taker_only: str = "false") -> list[dict]:
    rows, cursor = [], None
    for _ in range(40):
        p = {"condition": cond, "limit": 1000, "taker_only": taker_only, "_": f"{time.time_ns()}"}
        if cursor:
            p["cursor"] = cursor
        j, _m = get("/v2/trades", p, raw_log)
        time.sleep(0.3)
        if not j:
            break
        d = j.get("data") or []
        rows += d
        cursor = (j.get("pagination") or {}).get("next_cursor")
        if not cursor or not d or min(r["timestamp"] for r in d) < since:
            break
    return rows


def rpc_lookup(txs: list[str]) -> pd.DataFrame:
    blocks: dict[str, int] = {}
    rows = []
    for h in txs:
        row = {"tx": h}
        try:
            rc = api.rpc("eth_getTransactionReceipt", [h])
            if rc:
                bn = rc["blockNumber"]
                if bn not in blocks:
                    blocks[bn] = int(api.rpc("eth_getBlockByNumber", [bn, False])["timestamp"], 16)
                row.update(block=int(bn, 16), block_ts=blocks[bn], status=rc.get("status"), to=(rc.get("to") or "").lower(),
                           n_logs=len(rc.get("logs") or []))
        except Exception as ex:
            row["err"] = str(ex)[:160]
        rows.append(row)
    return pd.DataFrame(rows)


def q(s) -> dict:
    s = pd.Series(s).dropna().astype(float)
    if s.empty:
        return {"n": 0}
    return {"n": int(len(s)), "min": round(s.min(), 3), "p10": round(s.quantile(.1), 3), "median": round(s.median(), 3),
            "mean": round(s.mean(), 3), "p90": round(s.quantile(.9), 3), "p99": round(s.quantile(.99), 3), "max": round(s.max(), 3)}


def main() -> None:
    mk, wal, sel = select()
    print(mk[["slug", "n_trades_select", "end_date", "seconds_delay", "fee_type"]].to_string())
    print(wal.to_string())
    if mk.empty:
        raise SystemExit("no markets selected")
    mk.to_parquet(OUT / f"latency_{STAMP}_markets.parquet", index=False)
    wal.to_parquet(OUT / f"latency_{STAMP}_wallets.parquet", index=False)
    sel.to_parquet(OUT / f"latency_{STAMP}_selection_firehose.parquet", index=False)

    targets = []
    for c in mk.condition_id:
        for mode in ("cached", "busted"):
            targets.append({"id": f"cond:{c[:10]}:{mode}", "shape": "condition", "key": c, "mode": mode})
    for w in wal.wallet:
        targets.append({"id": f"user:{w[:10]}:busted", "shape": "user", "key": w, "mode": "busted"})

    da_sink, polls, status, raw_log = [], [], [], []
    clob_sink, rtds_sink, rtds_f_sink, stream_stats = [], [], [], {}
    stop = threading.Event()
    th = threading.Thread(target=poller, args=(targets, RUN_S, da_sink, polls, raw_log, stop), daemon=True)
    ts = threading.Thread(target=status_poller, args=(RUN_S, status, raw_log, stop), daemon=True)
    t0 = time.time()
    th.start(); ts.start()
    asyncio.run(run_streams(mk, clob_sink, rtds_sink, rtds_f_sink, stream_stats))
    stop.set(); th.join(timeout=60); ts.join(timeout=5)
    t1 = time.time()
    print("streams:", stream_stats)

    tape = []
    for c in mk.condition_id:
        for flag in ("false", "true"):
            for r in full_tape(c, t0 - 5, raw_log, flag):
                r["_cond"] = c
                r["_taker_only"] = flag
                tape.append(r)

    da = pd.DataFrame(da_sink); pl = pd.DataFrame(polls); cw = pd.DataFrame(clob_sink)
    rt = pd.DataFrame(rtds_sink); rf = pd.DataFrame(rtds_f_sink); st = pd.DataFrame(status); tp = pd.DataFrame(tape)
    targets_c = set(mk.condition_id)

    live = da[~da.baseline].copy() if len(da) else da
    bust = live[(live["mode"] == "busted") & (live["shape"] == "condition")] if len(live) else live
    txs = sorted(set(bust.tx)) if len(bust) else []
    random.seed(17)
    rpc = rpc_lookup(random.sample(txs, min(RPC_SAMPLE, len(txs))))

    RAW_OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(RAW_OUT, "wt") as f:
        json.dump(raw_log, f)
    for name, df in (("dataapi", da), ("polls", pl), ("clobws", cw), ("rtds", rt), ("rtds_filtered", rf), ("rpc", rpc),
                     ("status", st), ("tape", tp)):
        df.to_parquet(OUT / f"latency_{STAMP}_{name}.parquet", index=False)

    # ------------------------------------------------------------------ metrics
    S: dict = {"stamp": STAMP, "run_seconds": RUN_S, "poll_interval_s": POLL_S, "markets": mk.slug.tolist(),
               "wallets": wal.to_dict("records"), "t_start_utc": datetime.fromtimestamp(t0, timezone.utc).isoformat(),
               "t_end_utc": datetime.fromtimestamp(t1, timezone.utc).isoformat(), "stream_stats": stream_stats,
               "selection_rows": int(len(sel)), "selection_rows_without_condition": int((sel.condition_id.fillna("") == "").sum())}
    if len(rt):
        S["clock_check_rtds_recv_minus_envelope_ms"] = q(rt.recv_ms - rt.env_ts_ms)
    if len(pl):
        pl["rtt_ms"] = (pl.t_resp - pl.t_req) * 1000
        S["dataapi_request_rtt_ms"] = q(pl.rtt_ms)
        S["dataapi_polls_by_mode"] = pl.groupby("mode").size().to_dict()
        S["dataapi_xcache_by_mode"] = pl.groupby(["mode", "x_cache"]).size().rename("n").reset_index().to_dict("records")
        S["dataapi_age_header_cached_mode_s"] = q(pd.to_numeric(pl[pl["mode"] == "cached"].age, errors="coerce"))
        S["dataapi_pages_all_new"] = int(pl.all_new.fillna(False).sum())
        S["dataapi_errors"] = int(pl.err.notna().sum()) if "err" in pl else 0
        S["dataapi_status_codes"] = pl.status.value_counts(dropna=False).to_dict()
        S["dataapi_cache_control_values"] = pl.cache_control.value_counts(dropna=False).to_dict()
    if len(live):
        live["lat_upper_s"] = live.t_resp - live.ts
        live["lat_lower_s"] = live.prev_req - live.ts
        for (shape, mode), g in live.groupby(["shape", "mode"]):
            S[f"dataapi_{shape}_{mode}_latency_vs_ts_upper_s"] = q(g.lat_upper_s)
            S[f"dataapi_{shape}_{mode}_latency_vs_ts_lower_s"] = q(g.lat_lower_s)
            S[f"dataapi_{shape}_{mode}_late_rows_gt60s"] = int((g.lat_lower_s > 60).sum())
    if len(cw):
        S["clobws_latency_vs_match_s"] = q((cw.recv_ms - cw.match_ms) / 1000)
        S["clobws_trades"] = int(len(cw)); S["clobws_tx_present"] = int((cw.tx.str.len() == 66).sum())
        S["clobws_keys"] = cw["keys"].value_counts().to_dict()
    for tag in ("trades", "orders_matched"):
        x = rt[rt.tag == tag] if len(rt) else rt
        if len(x):
            lat = x.recv_ms / 1000 - x.ts
            S[f"rtds_{tag}_rows"] = int(len(x)); S[f"rtds_{tag}_rows_per_s"] = round(len(x) / RUN_S, 2)
            S[f"rtds_{tag}_rows_without_condition"] = int((x.condition_id.fillna("") == "").sum())
            S[f"rtds_{tag}_latency_vs_ts_s_all"] = q(lat)
            S[f"rtds_{tag}_latency_vs_ts_s_targets"] = q(lat[x.condition_id.isin(targets_c)])
            S[f"rtds_{tag}_distinct_wallets"] = int(x.wallet.nunique())
            S[f"rtds_{tag}_key_sets"] = x["keys"].value_counts().head(5).to_dict()
    if len(rf):
        S["rtds_filtered_rows"] = int(len(rf)); S["rtds_filtered_slugs"] = sorted(set(rf.slug.dropna()))
        S["rtds_filtered_offtarget_rows"] = int((~rf.condition_id.isin(targets_c)).sum())

    # ---- coverage: Data API tape (maker+taker) vs RTDS rows for the target markets during the window
    if len(tp) and len(rt):
        tpw = tp[(tp._taker_only == "false") & (tp.timestamp >= t0 + 5) & (tp.timestamp <= t1 - 10)].copy()
        tpw["tx"] = tpw.transaction_hash.str.lower(); tpw["wallet"] = tpw.proxy_wallet.str.lower()
        taker = bust[(bust.ts >= t0 + 5) & (bust.ts <= t1 - 10)] if len(bust) else bust
        for tag in ("trades", "orders_matched"):
            x = rt[(rt.tag == tag) & rt.condition_id.isin(targets_c) & (rt.ts >= t0 + 5) & (rt.ts <= t1 - 10)]
            kx = set(zip(x.tx, x.wallet)); kt = set(zip(tpw.tx, tpw.wallet)); kk = set(zip(taker.tx, taker.wallet))
            S[f"coverage_{tag}"] = {"rtds_rows": int(len(x)), "rtds_tx_wallet_pairs": len(kx),
                                    "tape_rows_taker_only_false": int(len(tpw)), "tape_tx_wallet_pairs": len(kt),
                                    "busted_poll_taker_pairs": len(kk),
                                    "rtds_pairs_in_tape": len(kx & kt), "tape_pairs_in_rtds": len(kt & kx),
                                    "taker_pairs_in_rtds": len(kk & kx), "rtds_pairs_that_are_taker_rows": len(kx & kk)}
        # which RTDS `trades` rows are taker rows (Data API taker_only=true) and does the `fee` key mark them?
        x = rt[(rt.tag == "trades") & rt.condition_id.isin(targets_c) & (rt.ts >= t0 + 5) & (rt.ts <= t1 - 10)].copy()
        kk = set(zip(taker.tx, taker.wallet))
        x["is_taker_row"] = [(a, b) in kk for a, b in zip(x.tx, x.wallet)]
        x["has_fee_key"] = x["keys"].str.contains(r"(?:^|,)fee(?:,|$)")
        S["rtds_trades_taker_vs_fee_key"] = x.groupby(["is_taker_row", "has_fee_key"]).size().rename("n").reset_index().to_dict("records")
        S["rtds_trades_rows_per_tx_targets"] = q(x.groupby("tx").size())
        # first-seen differences for the same (tx, wallet)
        a = bust.groupby(["tx", "wallet"]).t_resp.min()
        b = rt[rt.tag == "trades"].groupby(["tx", "wallet"]).recv_ms.min() / 1000
        c = pd.concat([a, b], axis=1, join="inner")
        S["dataapi_busted_first_minus_rtds_first_s"] = q(c.iloc[:, 0] - c.iloc[:, 1])
        if len(cw):
            w = cw.groupby("tx").recv_ms.min() / 1000
            bt = rt[rt.tag == "trades"].groupby("tx").recv_ms.min() / 1000
            c2 = pd.concat([bt, w], axis=1, join="inner")
            S["rtds_first_minus_clobws_first_s"] = q(c2.iloc[:, 0] - c2.iloc[:, 1])

    # ---- block timestamps vs source timestamps (tx-level)
    if len(rpc) and "block_ts" in rpc:
        r = rpc.dropna(subset=["block_ts"])[["tx", "block_ts", "block", "to"]]
        d1 = bust.groupby("tx").agg(da_ts=("ts", "min"), da_first=("t_resp", "min")).reset_index()
        j = r.merge(d1, on="tx", how="left")
        if len(cw):
            j = j.merge(cw.groupby("tx").agg(ws_match_ms=("match_ms", "min"), ws_recv_ms=("recv_ms", "min")).reset_index(), on="tx", how="left")
        if len(rt):
            j = j.merge(rt[rt.tag == "trades"].groupby("tx").agg(rt_ts=("ts", "min"), rt_recv_ms=("recv_ms", "min"),
                                                                rt_env_ms=("env_ts_ms", "min")).reset_index(), on="tx", how="left")
        j["da_ts_minus_block"] = j.da_ts - j.block_ts
        S["rpc_sample"] = int(len(r)); S["rpc_exchange_to"] = r["to"].value_counts().to_dict()
        S["dataapi_ts_equals_block_ts_frac"] = round(float((j.da_ts_minus_block == 0).mean()), 4)
        S["dataapi_ts_minus_block_ts"] = q(j.da_ts_minus_block)
        S["dataapi_busted_first_seen_minus_block_s"] = q(j.da_first - j.block_ts)
        if "ws_match_ms" in j:
            S["block_minus_ws_match_s"] = q(j.block_ts - j.ws_match_ms / 1000)
            S["dataapi_busted_first_seen_minus_ws_match_s"] = q(j.da_first - j.ws_match_ms / 1000)
            S["ws_recv_minus_block_s"] = q(j.ws_recv_ms / 1000 - j.block_ts)
        if "rt_ts" in j:
            S["rtds_ts_minus_block_ts"] = q(j.rt_ts - j.block_ts)
            S["rtds_recv_minus_block_s"] = q(j.rt_recv_ms / 1000 - j.block_ts)
            if "ws_match_ms" in j:
                S["rtds_ts_minus_floor_ws_match_s"] = q(j.rt_ts - np.floor(j.ws_match_ms / 1000))
                S["rtds_recv_minus_ws_match_s"] = q(j.rt_recv_ms / 1000 - j.ws_match_ms / 1000)
        j.to_parquet(OUT / f"latency_{STAMP}_joined.parquet", index=False)
    if len(st):
        S["status_serving_lag_s"] = q(st.serving_lag_s)
    (OUT / f"latency_{STAMP}_summary.json").write_text(json.dumps(S, indent=1, default=str))
    print(json.dumps(S, indent=1, default=str))


if __name__ == "__main__":
    main()
