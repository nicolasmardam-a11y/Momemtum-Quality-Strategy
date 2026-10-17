"""Replay captured public market-websocket frames into YES-space books, trades and top-of-book series.

Usage: python -m analyses.lp_rewards_live.06_ws_replay <label> [<label> ...]
Inputs : data/raw/clob_ws/live/<date>/lp_<label>_*.jsonl.gz (written by 03_capture.py), ws_markets*.parquet
Outputs: data/derived/lp_rewards_live/{trades,tob,lvl}_<label>.parquet

Conventions (checked in the data, see notes):
- The YES book is the unified book (NO orders appear mirrored), so only YES-asset `book`/`price_change` frames
  update the book; NO-asset frames are used for a mirror check only.
- A NO-asset trade is mapped to YES space: taker BUY NO at q == taker SELL YES at 1-q (consumes YES bids), and
  taker SELL NO at q == taker BUY YES at 1-q (consumes YES asks).
- `side` of last_trade_price is the taker's side (AsyncAPI). Checked against the pre-trade touch.
- Times: local receive time (s). Server ms timestamps are kept for reference.
"""
from __future__ import annotations

import bisect
import glob
import gzip
import json
import sys
import zlib
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "lp_rewards_live"
RAWDIR = ROOT / "data" / "raw" / "clob_ws" / "live"


def read_lines(path):
    raw = open(path, "rb").read()
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    txt = d.decompress(raw).decode(errors="ignore")
    for L in txt.split("\n"):
        if not L:
            continue
        try:
            yield json.loads(L)
        except json.JSONDecodeError:
            return  # truncated tail of a file still being written


def market_maps(label):
    f = OUT / ("ws_markets.parquet" if label == "w1" else f"ws_markets_{label}.parquet")
    ws = pd.read_parquet(f)
    yes = {r.yes_token: r.condition_id for r in ws.itertuples()}
    no = {r.no_token: r.condition_id for r in ws.itertuples()}
    return ws, yes, no


def best(bk, side):
    d = bk[side]
    if not d:
        return None
    return max(d) if side == "bids" else min(d)


def replay(label):
    ws, yes, no = market_maps(label)
    files = sorted(glob.glob(str(RAWDIR / "*" / f"lp_{label}_*.jsonl.gz")))
    books = {c: {"bids": {}, "asks": {}, "init": False} for c in ws.condition_id}
    trades, tob, lvl, gaps = [], [], [], []
    last_tob = {}
    mirror_chk = [0, 0]

    def push_tob(c, t):
        bk = books[c]
        bb, ba = best(bk, "bids"), best(bk, "asks")
        key = (bb, ba, bk["bids"].get(bb), bk["asks"].get(ba))
        if last_tob.get(c) != key:
            last_tob[c] = key
            tob.append((c, t, bb, ba, bk["bids"].get(bb, 0.0), bk["asks"].get(ba, 0.0)))

    for fp in files:
        for o in read_lines(fp):
            if "event" in o:
                if o["event"] in ("disconnect", "subscribed"):
                    gaps.append((o["event"], o["recv"]))
                continue
            if "msg" not in o:
                continue
            t = o["recv"]
            try:
                m = json.loads(o["msg"])
            except json.JSONDecodeError:
                continue
            for e in (m if isinstance(m, list) else [m]):
                et = e.get("event_type")
                if et == "book":
                    a = e.get("asset_id")
                    if a in yes:
                        c = yes[a]
                        bk = books[c]
                        bk["bids"] = {float(x["price"]): float(x["size"]) for x in e.get("bids") or [] if float(x["size"]) > 0}
                        bk["asks"] = {float(x["price"]): float(x["size"]) for x in e.get("asks") or [] if float(x["size"]) > 0}
                        bk["init"] = True
                        push_tob(c, t)
                elif et == "price_change":
                    touched = set()
                    for pc in e.get("price_changes") or []:
                        a = pc.get("asset_id")
                        if a not in yes:
                            if a in no:
                                mirror_chk[1] += 1
                            continue
                        c = yes[a]
                        bk = books[c]
                        if not bk["init"]:
                            continue
                        side = "bids" if pc["side"] == "BUY" else "asks"
                        p, s = float(pc["price"]), float(pc["size"])
                        old = bk[side].get(p, 0.0)
                        bt = best(bk, side)
                        at_best = bt is not None and abs(p - bt) < 1e-9
                        if s <= 0:
                            bk[side].pop(p, None)
                        else:
                            bk[side][p] = s
                        if s != old:
                            lvl.append((c, t, side, p, old, s, at_best))
                        mirror_chk[0] += 1
                        touched.add(c)
                    for c in touched:
                        push_tob(c, t)
                elif et == "last_trade_price":
                    a = e.get("asset_id")
                    p, s, sd = float(e["price"]), float(e["size"]), e.get("side")
                    if a in yes:
                        c, yp, ys = yes[a], p, sd
                    elif a in no:
                        c, yp, ys = no[a], round(1 - p, 6), ("SELL" if sd == "BUY" else "BUY")
                    else:
                        continue
                    bk = books[c]
                    bb, ba = best(bk, "bids"), best(bk, "asks")
                    trades.append({"condition_id": c, "t": t, "ts_ms": int(e.get("timestamp") or 0), "asset_is_yes": a in yes,
                                   "price": yp, "size": s, "taker_side": ys, "tx": e.get("transaction_hash"),
                                   "fee_rate_bps": e.get("fee_rate_bps"), "bb": bb, "ba": ba,
                                   "bsz": bk["bids"].get(bb, np.nan) if bb is not None else np.nan,
                                   "asz": bk["asks"].get(ba, np.nan) if ba is not None else np.nan})
    tr = pd.DataFrame(trades)
    tb = pd.DataFrame(tob, columns=["condition_id", "t", "bb", "ba", "bsz", "asz"])
    lv = pd.DataFrame(lvl, columns=["condition_id", "t", "side", "price", "old", "new", "at_best"])
    tr.to_parquet(OUT / f"trades_{label}.parquet", index=False)
    tb.to_parquet(OUT / f"tob_{label}.parquet", index=False)
    lv.to_parquet(OUT / f"lvl_{label}.parquet", index=False)
    g = pd.DataFrame(gaps, columns=["event", "t"])
    g.to_parquet(OUT / f"gaps_{label}.parquet", index=False)
    print(label, "files", len(files), "trades", len(tr), "tob rows", len(tb), "lvl rows", len(lv),
          "subscribed/disconnect", g.event.value_counts().to_dict(), "pc yes/no", mirror_chk)
    return tr, tb, lv


if __name__ == "__main__":
    for lab in sys.argv[1:]:
        replay(lab)
