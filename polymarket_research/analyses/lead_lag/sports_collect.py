"""Read-only sports mini forward test collector: ESPN public scoreboard (polled), Polymarket sports WS, CLOB books.
Run: nohup python -m analyses.lead_lag.sports_collect <minutes> S1 > data/derived/lead_lag/sports_S1.log 2>&1 &
Raw: data/raw/lead_lag_live/<date>/{espn,sportsws,clobS}_<tag>.tsv.gz ("<recv>\\t<frame>"); derived: sports_<tag>_{tob,espn}.parquet
"""
import asyncio, gzip, json, sys, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
import requests
import websockets
from pmr import api
MIN = float(sys.argv[1]); TAG = sys.argv[2]
T_END = time.time() + MIN * 60
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/lead_lag_live" / datetime.now(timezone.utc).strftime("%Y%m%d"); RAW.mkdir(parents=True, exist_ok=True)
DER = ROOT / "data/derived/lead_lag"
F = {k: gzip.open(RAW / f"{k}_{TAG}.tsv.gz", "at", compresslevel=1) for k in ("espn", "sportsws", "clobS")}
books, tob, espn_rows = {}, [], []
URLS = {"cfb": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
        "nhl": "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"}


def discover():
    now = datetime.now(timezone.utc)
    ms = api.gamma_markets(closed="false", end_date_min=(now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           end_date_max=(now + timedelta(hours=14)).strftime("%Y-%m-%dT%H:%M:%SZ"), max_pages=60)
    out = []
    for m in ms:
        s = m.get("slug", "")
        if not s.startswith(("cfb-", "nhl-")) or m.get("sportsMarketType") != "moneyline":
            continue
        gs = pd.Timestamp(m.get("gameStartTime")) if m.get("gameStartTime") else None
        if gs is None or gs.timestamp() > T_END or gs.timestamp() < time.time() - 3 * 3600:
            continue
        out.append({"slug": s, "question": m.get("question"), "outcomes": api.jlist(m.get("outcomes")), "tokens": api.jlist(m.get("clobTokenIds")),
                    "gameStartTime": m.get("gameStartTime"), "secondsDelay": m.get("secondsDelay"), "fee": m.get("feeSchedule"),
                    "feeType": m.get("feeType"), "events": [(e.get("slug"), e.get("title")) for e in (m.get("events") or [])][:1]})
    return out


async def espn_poll():
    s = requests.Session()
    last = {}
    while time.time() < T_END:
        for lg, u in URLS.items():
            try:
                r = await asyncio.to_thread(s.get, u, timeout=10)
                recv = time.time()
                F["espn"].write(f"{recv:.3f}\t{lg}\t{r.status_code}\t{r.text}\n")
                for e in r.json().get("events", []):
                    c = e["competitions"][0]
                    sc = tuple((x["team"].get("displayName"), x.get("homeAway"), x.get("score")) for x in c["competitors"])
                    key = e["id"]
                    if last.get(key) != (sc, e["status"]["type"].get("state")):
                        last[key] = (sc, e["status"]["type"].get("state"))
                        espn_rows.append({"recv": recv, "league": lg, "id": key, "name": e.get("name"), "state": e["status"]["type"].get("state"),
                                          "detail": e["status"]["type"].get("detail"), "clock": e["status"].get("displayClock"), "period": e["status"].get("period"),
                                          "team0": sc[0][0], "ha0": sc[0][1], "score0": sc[0][2], "team1": sc[1][0], "ha1": sc[1][1], "score1": sc[1][2]})
            except Exception as ex:  # noqa: BLE001
                print("espn err", repr(ex)[:120], flush=True)
        await asyncio.sleep(4)


async def sports_ws():
    while time.time() < T_END:
        try:
            async with websockets.connect("wss://sports-api.polymarket.com/ws", proxy=True, open_timeout=30, max_queue=None) as ws:
                while time.time() < T_END:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        continue
                    if isinstance(raw, str):
                        F["sportsws"].write(f"{time.time():.3f}\t{raw}\n")
        except Exception as ex:  # noqa: BLE001
            print("sportsws err", repr(ex)[:120], flush=True); await asyncio.sleep(2)


def note(a, recv, ts):
    b = books.get(a)
    if not b:
        return
    bids = [p for p, q in b["bids"].items() if q > 0]; asks = [p for p, q in b["asks"].items() if q > 0]
    tob.append((recv, ts, a, max(bids) if bids else None, min(asks) if asks else None))


async def clob(assets):
    while time.time() < T_END:
        try:
            async with websockets.connect("wss://ws-subscriptions-clob.polymarket.com/ws/market", proxy=True, ping_interval=None, max_queue=None, max_size=2 ** 24) as ws:
                await ws.send(json.dumps({"assets_ids": assets, "type": "market"}))
                last = time.monotonic()
                while time.time() < T_END:
                    if time.monotonic() - last > 10:
                        await ws.send("PING"); last = time.monotonic()
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    except asyncio.TimeoutError:
                        continue
                    recv = time.time()
                    if raw == "PONG":
                        continue
                    F["clobS"].write(f"{recv:.6f}\t{raw}\n")
                    d = json.loads(raw)
                    for m in (d if isinstance(d, list) else [d]):
                        et = m.get("event_type"); ts = int(m.get("timestamp") or 0)
                        if et == "book":
                            books[m["asset_id"]] = {"bids": {float(x["price"]): float(x["size"]) for x in m.get("bids") or []},
                                                    "asks": {float(x["price"]): float(x["size"]) for x in m.get("asks") or []}}
                            note(m["asset_id"], recv, ts)
                        elif et == "price_change":
                            for pc in m.get("price_changes") or []:
                                b = books.get(pc["asset_id"])
                                if b is None:
                                    continue
                                side = "bids" if pc["side"] == "BUY" else "asks"
                                p, q = float(pc["price"]), float(pc["size"])
                                if q <= 0:
                                    b[side].pop(p, None)
                                else:
                                    b[side][p] = q
                                note(pc["asset_id"], recv, ts)
        except Exception as ex:  # noqa: BLE001
            print("clob err", repr(ex)[:120], flush=True); await asyncio.sleep(2)


async def main():
    mk = discover()
    json.dump(mk, open(DER / f"sports_{TAG}_markets.json", "w"), indent=1, default=str)
    assets = [t for m in mk for t in m["tokens"]]
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), "markets", len(mk), "assets", len(assets), flush=True)
    await asyncio.gather(espn_poll(), sports_ws(), clob(assets))
    for f in F.values():
        f.close()
    pd.DataFrame(tob, columns=["recv", "ts_ms", "asset", "bid", "ask"]).to_parquet(DER / f"sports_{TAG}_tob.parquet")
    pd.DataFrame(espn_rows).to_parquet(DER / f"sports_{TAG}_espn.parquet")
    print("done", len(tob), len(espn_rows), flush=True)


asyncio.run(main())
