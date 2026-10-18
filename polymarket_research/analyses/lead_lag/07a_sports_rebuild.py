"""Rebuild sports_<tag>_{tob,espn}.parquet from the raw frames written by sports_collect.py.

Needed because the S1 collector process was killed (session interruption at 2026-10-17 23:38 UTC) before it wrote its
derived tables. Same book logic as sports_collect.py; tob rows are written only when the best bid/ask of an asset changes
(equivalent for the as-of lookups in 07_sports_analyze.py). Truncated gzip tails are tolerated.
Run: python -m analyses.lead_lag.07a_sports_rebuild S1
"""
import gzip
import json
import sys
import zlib
from glob import glob

import pandas as pd

TAG = sys.argv[1] if len(sys.argv) > 1 else "S1"
D = "data/derived/lead_lag/"


def lines(path):
    """Yield complete lines of a possibly truncated gzip file."""
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    buf = b""
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            try:
                buf += d.decompress(chunk)
            except zlib.error:
                break
            *full, buf = buf.split(b"\n")
            for ln in full:
                yield ln.decode("utf-8", "replace")


def espn():
    rows, last = [], {}
    for f in sorted(glob(f"data/raw/lead_lag_live/*/espn_{TAG}.tsv.gz")):
        for ln in lines(f):
            parts = ln.split("\t", 3)
            if len(parts) < 4 or parts[2] != "200":
                continue
            recv, lg = float(parts[0]), parts[1]
            try:
                j = json.loads(parts[3])
            except json.JSONDecodeError:
                continue
            for e in j.get("events", []):
                c = e["competitions"][0]
                sc = tuple((x["team"].get("displayName"), x.get("homeAway"), x.get("score")) for x in c["competitors"])
                st = e["status"]["type"].get("state")
                if last.get(e["id"]) != (sc, st):
                    last[e["id"]] = (sc, st)
                    rows.append({"recv": recv, "league": lg, "id": e["id"], "name": e.get("name"), "state": st,
                                 "detail": e["status"]["type"].get("detail"), "clock": e["status"].get("displayClock"),
                                 "period": e["status"].get("period"), "team0": sc[0][0], "ha0": sc[0][1], "score0": sc[0][2],
                                 "team1": sc[1][0], "ha1": sc[1][1], "score1": sc[1][2]})
    return pd.DataFrame(rows)


def tob():
    books, last, out, n = {}, {}, [], 0
    for f in sorted(glob(f"data/raw/lead_lag_live/*/clobS_{TAG}.tsv.gz")):
        for ln in lines(f):
            t, _, raw = ln.partition("\t")
            if not raw or raw == "PONG":
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            recv = float(t)
            n += 1
            for m in (d if isinstance(d, list) else [d]):
                et = m.get("event_type")
                ts = int(m.get("timestamp") or 0)
                touched = []
                if et == "book":
                    books[m["asset_id"]] = {"bids": {float(x["price"]): float(x["size"]) for x in m.get("bids") or []},
                                            "asks": {float(x["price"]): float(x["size"]) for x in m.get("asks") or []}}
                    touched = [m["asset_id"]]
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
                        touched.append(pc["asset_id"])
                for a in set(touched):
                    b = books[a]
                    bb = max((p for p, q in b["bids"].items() if q > 0), default=None)
                    ba = min((p for p, q in b["asks"].items() if q > 0), default=None)
                    if last.get(a) != (bb, ba):
                        last[a] = (bb, ba)
                        out.append((recv, ts, a, bb, ba))
    print("clob frames", n, "tob rows", len(out), flush=True)
    return pd.DataFrame(out, columns=["recv", "ts_ms", "asset", "bid", "ask"])


if __name__ == "__main__":
    E = espn()
    E.to_parquet(f"{D}sports_{TAG}_espn.parquet")
    print("espn rows", len(E), "games", E.id.nunique() if len(E) else 0,
          "in-play games", E[E.state == "in"].id.nunique() if len(E) else 0, flush=True)
    T = tob()
    T.to_parquet(f"{D}sports_{TAG}_tob.parquet")
    print("tob span", pd.to_datetime(T.recv.min(), unit="s"), pd.to_datetime(T.recv.max(), unit="s"), "assets", T.asset.nunique())
