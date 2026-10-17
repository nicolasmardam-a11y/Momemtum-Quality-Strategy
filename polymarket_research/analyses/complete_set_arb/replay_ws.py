"""Replay recorded market-channel websocket streams and simulate delayed taker execution of neg-risk episodes.

Run from polymarket_research/:  python -m analyses.complete_set_arb.replay_ws
Input: data/raw/clob_ws/live/<date>/ws_<HHMMSS>_<conn>.jsonl.gz written by ws_monitor.py (one run = one HHMMSS prefix).
For every start of a positive top-of-book episode ((d) sell-all-YES == (e) buy-all-NO + convert, or (c) buy-all-YES on an
exhaustive group), we size q = min top-of-book size over the legs used (>= 5 shares), and send one limit order per leg at the
start-time best price. Each leg is checked at start + latency (+ the market's secondsDelay, for sports takers): it fills only
if the book at that moment still offers that price or better. Outcomes: all legs fill (captured), some legs fill (legged,
directional exposure), none fill. Captured profit = q x net edge at start (fees included). Assumptions are optimistic:
no queue competition, full size at improved prices, and the delayed order is not re-checked against the price path.
Writes data/derived/complete_set_arb_ws_replay.parquet.
"""
from __future__ import annotations

import glob
import gzip
import heapq
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import csa  # noqa: E402

D = ROOT / "data" / "derived" / "complete_set_arb"
RAW = ROOT / "data" / "raw" / "clob_ws" / "live"
SCENARIOS = {"latency_0.25s_no_delay": (0.25, False), "latency_0.25s_plus_delay": (0.25, True),
             "latency_1s_plus_delay": (1.0, True)}


def load_universe():
    uv = max(D.glob("universe_v*.parquet"), key=lambda p: int(re.search(r"universe_v(\d+)", p.name).group(1)))
    u = pd.read_parquet(uv)
    u["tokens"] = u["tokens"].map(json.loads)
    return u[u.negRisk & u.nr_id.notna()]


def run_files():
    """Group connection files into runs: connections of one run open within a few seconds of each other."""
    fs = []
    for f in sorted(glob.glob(str(RAW / "*" / "ws_*.jsonl.gz"))):
        m = re.search(r"(\d{8})/ws_(\d{2})(\d{2})(\d{2})_(\d{2})", f)
        fs.append((m.group(1), int(m.group(2)) * 3600 + int(m.group(3)) * 60 + int(m.group(4)), f))
    runs, last, key = defaultdict(list), None, None
    for day, sec, f in sorted(fs):
        if last is None or (day, sec) > (last[0], last[1] + 30):
            key = f"{day}_{sec // 3600:02d}{sec % 3600 // 60:02d}{sec % 60:02d}"
        runs[key].append(f)
        last = (day, sec)
    return runs


def stream(files):
    """Merge messages of several connection files by receive time."""
    its = []
    for i, f in enumerate(files):
        def gen(f=f):
            try:
                with gzip.open(f, "rt") as fh:
                    for line in fh:
                        try:
                            r = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if "recv" in r:
                            yield r["recv"], r["msg"]
            except (EOFError, OSError):  # file of a run still being written
                return
        its.append(gen())
    yield from heapq.merge(*its, key=lambda t: t[0])


def best(b, side):
    lv = [(p, s) for p, s in b[side].items() if s > 0]
    if not lv:
        return None
    return max(lv) if side == "bids" else min(lv)


def replay(files, u):
    assets = []
    for f in files:
        with gzip.open(f, "rt") as fh:
            assets += json.loads(fh.readline())["meta"]["assets"]
    aset = set(assets)
    rows_by_asset = {}
    groups = defaultdict(list)
    complete = defaultdict(lambda: True)
    for r in u.to_dict("records"):
        if csa.tradable(r):
            if r["tokens"][0] in aset:
                rows_by_asset[r["tokens"][0]] = r
                groups[r["nr_id"]].append(r)
            else:
                complete[r["nr_id"]] = False  # a tradable member was not subscribed: (c) cannot be evaluated
    exh = {}
    gl = sorted(D.glob("scan_*_groups.parquet"))
    gdf = pd.concat([pd.read_parquet(x)[["nr_id", "exhaustive"]] for x in gl]).drop_duplicates("nr_id", keep="last")
    exh = dict(zip(gdf.nr_id, gdf.exhaustive))
    books = {}
    state = {}   # (gid, ty) -> positive?
    pending = []  # heap of (t_check, seq, dict)
    out = []
    seq = 0

    def edge(gid, ty):
        rows = groups[gid]
        if any(r["tokens"][0] not in books for r in rows):
            return None, None
        tot, legs = 0.0, []
        for r in rows:
            b = books[r["tokens"][0]]
            if ty == "d":
                x = best(b, "bids")
                if x:
                    tot += x[0] - csa.fee_ps(x[0], r["fee_rate"], r["fee_exp"])
                    legs.append((r["tokens"][0], x[0], x[1], r["secondsDelay"]))
            else:
                x = best(b, "asks")
                if not x:
                    return None, None
                tot += x[0] + csa.fee_ps(x[0], r["fee_rate"], r["fee_exp"])
                legs.append((r["tokens"][0], x[0], x[1], r["secondsDelay"]))
        return (tot - 1.0 if ty == "d" else 1.0 - tot), legs

    def check(ev, now):
        fills, unwind = [], 0.0
        for (a, p, s, _d) in ev["legs"]:
            r = rows_by_asset[a]
            x = best(books[a], "bids" if ev["type"] == "d" else "asks")
            if ev["type"] == "d":
                ok = x is not None and (x[0] > p + 1e-12 or (abs(x[0] - p) < 1e-12 and x[1] >= ev["q"]))
            else:
                ok = x is not None and (x[0] < p - 1e-12 or (abs(x[0] - p) < 1e-12 and x[1] >= ev["q"]))
            fills.append(ok)
            if ok:
                # cost of unwinding this filled leg immediately at the opposite best price (taker both ways)
                y = best(books[a], "asks" if ev["type"] == "d" else "bids")
                px = y[0] if y else (1.0 if ev["type"] == "d" else 0.0)
                adverse = (px - p) if ev["type"] == "d" else (p - px)
                unwind += ev["q"] * (adverse + csa.fee_ps(p, r["fee_rate"], r["fee_exp"]) + csa.fee_ps(px, r["fee_rate"], r["fee_exp"]))
        nf = sum(fills)
        res = "captured" if nf == len(fills) else ("none" if nf == 0 else "legged")
        out.append({**{k: v for k, v in ev.items() if k != "legs"}, "n_legs": len(fills), "n_filled": nf, "outcome": res,
                    "captured_profit": ev["q"] * ev["edge0"] if res == "captured" else 0.0,
                    "legging_cost": unwind if res == "legged" else 0.0, "t_check": now})

    for recv, raw in stream(files):
        while pending and pending[0][0] <= recv:
            _, _, ev = heapq.heappop(pending)
            check(ev, recv)
        if raw == "PONG":
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        touched = set()
        for m in (data if isinstance(data, list) else [data]):
            et = m.get("event_type")
            if et == "book":
                a = m["asset_id"]
                books[a] = {"bids": {float(x["price"]): float(x["size"]) for x in m.get("bids") or []},
                            "asks": {float(x["price"]): float(x["size"]) for x in m.get("asks") or []}}
                touched.add(a)
            elif et == "price_change":
                for pc in m.get("price_changes") or []:
                    a = pc["asset_id"]
                    if a not in books:
                        continue
                    side = "bids" if pc["side"] == "BUY" else "asks"
                    p, s = float(pc["price"]), float(pc["size"])
                    if s <= 0:
                        books[a][side].pop(p, None)
                    else:
                        books[a][side][p] = s
                    touched.add(a)
        for gid in {rows_by_asset[a]["nr_id"] for a in touched if a in rows_by_asset}:
            for ty in ("d", "c"):
                if ty == "c" and not (exh.get(gid, False) and complete[gid]):
                    continue
                e, legs = edge(gid, ty)
                pos = e is not None and e > 0
                if pos and not state.get((gid, ty)):
                    q = min(s for (_, _, s, _) in legs)
                    if q >= 5:
                        for name, (lat, use_delay) in SCENARIOS.items():
                            delay = max(d for (_, _, _, d) in legs) if use_delay else 0.0
                            seq += 1
                            heapq.heappush(pending, (recv + lat + delay, seq, {
                                "scenario": name, "gid": gid, "type": ty, "title": groups[gid][0]["event_title"],
                                "t_start": recv, "edge0": e, "q": q, "delay": delay, "legs": legs}))
                state[(gid, ty)] = pos
    return out


def main():
    u = load_universe()
    allr = []
    for run, files in sorted(run_files().items()):
        r = replay(files, u)
        for x in r:
            x["run"] = run
        allr += r
        print(f"run {run}: {len(files)} files, {len(r) // len(SCENARIOS)} sized episode starts")
    df = pd.DataFrame(allr)
    if not len(df):
        print("no sized episodes")
        return
    df.to_parquet(ROOT / "data" / "derived" / "complete_set_arb_ws_replay.parquet", index=False)
    pd.set_option("display.width", 250)
    print(df.groupby(["scenario", "type", "outcome"]).agg(n=("gid", "size"), profit=("captured_profit", "sum"),
                                                         med_edge=("edge0", "median"), med_q=("q", "median")).round(3).to_string())
    df["net"] = df.captured_profit - df.legging_cost
    print(df.groupby(["scenario"]).agg(starts=("gid", "size"), captured=("outcome", lambda s: (s == "captured").mean()),
                                       legged=("outcome", lambda s: (s == "legged").mean()),
                                       profit=("captured_profit", "sum"), legging_cost=("legging_cost", "sum"),
                                       net=("net", "sum")).round(3).to_string())
    sp = df.drop_duplicates(["run", "gid", "type", "t_start"])
    print("sports (secondsDelay>0) starts:", int((df[df.scenario == "latency_0.25s_plus_delay"].delay > 0).sum()),
          "| non-sports starts:", int((df[df.scenario == "latency_0.25s_plus_delay"].delay == 0).sum()))
    print(df[df.scenario == "latency_0.25s_plus_delay"].groupby(df.delay > 0).agg(
        starts=("gid", "size"), captured=("outcome", lambda s: (s == "captured").mean()), profit=("captured_profit", "sum"),
        legging_cost=("legging_cost", "sum"), net=("net", "sum")).round(3).to_string())
    print(df[df.scenario == "latency_0.25s_plus_delay"].groupby("title").agg(
        starts=("gid", "size"), captured=("outcome", lambda s: int((s == "captured").sum())),
        legged=("outcome", lambda s: int((s == "legged").sum())), profit=("captured_profit", "sum"),
        legging_cost=("legging_cost", "sum"), delay=("delay", "max")).sort_values("starts", ascending=False).head(15).round(3).to_string())


if __name__ == "__main__":
    main()
