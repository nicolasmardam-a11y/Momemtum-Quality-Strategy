"""Repeated live scan for complete-set / within-market arbitrage (read-only, no orders).

Run from polymarket_research/ (background):
  PMR_RATE_SCALE=2 nohup python -m analyses.complete_set_arb.collect 80 > data/derived/complete_set_arb/collect.log 2>&1 &

Every CYCLE_S seconds: full neg-risk scan (books of YES and NO of every tradable neg-risk member);
every BINARY_EVERY-th cycle also a full binary scan (both outcome tokens of every tradable binary market).
Between full scans, candidates are re-fetched every RESCAN_S seconds to measure persistence.
The Gamma universe (events keyset, closed=false, active=true) is refreshed every UNIVERSE_S seconds
in a background thread. Raw responses are recorded by pmr.http under data/raw/{gamma,clob}/live/.
Outputs: data/derived/complete_set_arb/scan_<id>_{groups,members,binary}.parquet, cand_<id>.parquet.
"""
from __future__ import annotations

import json
import math
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pmr import api  # noqa: E402
import csa  # noqa: E402

OUT = ROOT / "data" / "derived" / "complete_set_arb"
OUT.mkdir(parents=True, exist_ok=True)
CYCLE_S, BINARY_EVERY, RESCAN_S, UNIVERSE_S = 300, 2, 40, 900
# Collection window offset: window 1 (15:18-16:21 UTC) used scan ids 0..; window 2 uses 100.. so files do not collide.
SCAN_OFFSET = int(__import__("os").environ.get("CSA_SCAN_OFFSET", "0"))
MIN_CAND = 0.0  # any positive net profit at >= 1 share is a raw candidate (filters applied in analysis)

state = {"rows": None, "t": None, "ver": 0}
lock = threading.Lock()


def log(*a):
    print(datetime.now(timezone.utc).strftime("%H:%M:%S"), *a, flush=True)


def universe_loop(stop):
    while not stop.is_set():
        try:
            t0 = time.time()
            rows, t = csa.load_universe()
            with lock:
                state["rows"], state["t"], state["ver"] = rows, t, state["ver"] + 1
            pd.DataFrame([{k: (json.dumps(v) if isinstance(v, list) else v) for k, v in r.items()} for r in rows]) \
                .to_parquet(OUT / f"universe_v{state['ver'] + SCAN_OFFSET}.parquet", index=False)
            log(f"universe v{state['ver']}: {len(rows)} markets in {time.time() - t0:.0f}s")
        except Exception as ex:
            log("universe error", repr(ex)[:300])
        stop.wait(UNIVERSE_S)


def build_index(rows):
    groups = defaultdict(list)
    binaries = []
    for r in rows:
        if r["negRisk"] and r["nr_id"]:
            groups[r["nr_id"]].append(r)
        elif csa.tradable(r):
            binaries.append(r)
    return groups, binaries


def nr_tokens(groups):
    toks = []
    for g, ms in groups.items():
        for r in ms:
            if csa.tradable(r):
                toks += r["tokens"]
    return toks


def scan_binaries(binaries, scan_id, now_iso):
    """Fetch both tokens of every binary market chunk-wise, analyse per chunk, keep only summaries."""
    rows_out, cands = [], []
    chunks = [binaries[i:i + 50] for i in range(0, len(binaries), 50)]

    def one(ch):
        toks = [t for r in ch for t in r["tokens"]]
        try:
            bl = api.books(toks)
        except Exception as ex:
            log("binary books error", repr(ex)[:200])
            return [], []
        bks = {b["asset_id"]: b for b in bl if b.get("asset_id")}
        now_ms = time.time() * 1000
        res, cc = [], []
        for r in ch:
            a = csa.analyze_binary(r, bks)
            if a is None:
                continue
            a["age_max"] = max((csa._age(bks.get(t), now_ms) for t in r["tokens"]), default=math.nan)
            res.append(a)
            if (a["a_pmax"] > MIN_CAND) or (a["b_pmax"] > MIN_CAND):
                cc.append({"kind": "binary", "id": r["market_id"], "type": "a" if a["a_pmax"] > 0 else "b",
                           "pmax": max(a["a_pmax"], a["b_pmax"]), "metrics": json.dumps(a, default=str),
                           "flags": "|".join(csa.flags_for([r], bks, now_ms, now_iso)),
                           "legs": json.dumps(csa.leg_detail([r], bks), default=str),
                           "tokens": json.dumps(r["tokens"]), "title": r["question"], "event_slug": r["event_slug"]})
        return res, cc

    with ThreadPoolExecutor(24) as ex:
        for res, cc in ex.map(one, chunks):
            rows_out += res
            cands += cc
    df = pd.DataFrame(rows_out)
    df["scan_id"] = scan_id
    df["fetched_at"] = now_iso
    df.to_parquet(OUT / f"scan_{scan_id:03d}_binary.parquet", index=False)
    return df, cands


def analyze_groups(groups, bks, scan_id, now_iso, only=None):
    now_ms = time.time() * 1000
    grows, mrows, cands = [], [], []
    for gid, ms in groups.items():
        if only is not None and gid not in only:
            continue
        out, trad = csa.analyze_group(ms, bks)
        out.update({"nr_id": gid, "event_slug": ms[0]["event_slug"], "event_title": ms[0]["event_title"],
                    "scan_id": scan_id, "fetched_at": now_iso})
        if len(trad) >= 2:
            out["flags"] = "|".join(csa.flags_for(trad, bks, now_ms, now_iso))
            out["age_max"] = max((csa._age(bks.get(t), now_ms) for r in trad for t in r["tokens"]), default=math.nan)
            out["fee_rates"] = "|".join(sorted({str(r["fee_rate"]) for r in trad}))
        grows.append(out)
        if only is None:
            for r in trad:
                ty, tn = csa.top(bks[r["tokens"][0]]), csa.top(bks[r["tokens"][1]])
                mrows.append({"nr_id": gid, "market_id": r["market_id"], "bbY": ty[0], "bsY": ty[1], "baY": ty[2],
                              "asY": ty[3], "bbN": tn[0], "bsN": tn[1], "baN": tn[2], "asN": tn[3],
                              "mirror": csa.mirror_ok(bks[r["tokens"][0]], bks[r["tokens"][1]]),
                              "ageY": csa._age(bks[r["tokens"][0]], now_ms), "fee_rate": r["fee_rate"]})
        for ty in ("c", "d", "e"):
            pm = out.get(f"{ty}_pmax")
            if pm is not None and not (isinstance(pm, float) and math.isnan(pm)) and pm > MIN_CAND:
                cands.append({"kind": "negrisk", "id": gid, "type": ty, "pmax": pm, "exhaustive": out["exhaustive"],
                              "metrics": json.dumps(out, default=str), "flags": out.get("flags", ""),
                              "legs": json.dumps(csa.leg_detail(trad, bks), default=str),
                              "tokens": json.dumps([t for r in trad for t in r["tokens"]]),
                              "title": ms[0]["event_title"], "event_slug": ms[0]["event_slug"]})
    return pd.DataFrame(grows), pd.DataFrame(mrows), cands


def save_cands(cands, scan_id, obs_kind, now_iso, suffix=""):
    if not cands:
        return
    df = pd.DataFrame(cands)
    df["scan_id"], df["obs_kind"], df["fetched_at"] = scan_id, obs_kind, now_iso
    df.to_parquet(OUT / f"cand_{scan_id:03d}{suffix}.parquet", index=False)


def main(duration_min: float):
    stop = threading.Event()
    th = threading.Thread(target=universe_loop, args=(stop,), daemon=True)
    th.start()
    while state["rows"] is None:
        time.sleep(2)
    t_end = time.time() + duration_min * 60
    scan_id = SCAN_OFFSET
    while time.time() < t_end:
        c0 = time.time()
        with lock:
            rows, uver = state["rows"], state["ver"]
        groups, binaries = build_index(rows)
        now_iso = datetime.now(timezone.utc).isoformat()
        toks = nr_tokens(groups)
        bks, ta, tb = csa.fetch_books(toks)
        log(f"scan {scan_id} (u{uver}): neg-risk {len(groups)} groups, {len(toks)} tokens, {len(bks)} books in {tb - ta:.0f}s")
        gdf, mdf, cands = analyze_groups(groups, bks, scan_id, now_iso)
        gdf.to_parquet(OUT / f"scan_{scan_id:03d}_groups.parquet", index=False)
        mdf.to_parquet(OUT / f"scan_{scan_id:03d}_members.parquet", index=False)
        del bks
        if scan_id % BINARY_EVERY == 0:
            t1 = time.time()
            bdf, bc = scan_binaries(binaries, scan_id, now_iso)
            cands += bc
            log(f"scan {scan_id}: binary {len(bdf)} markets in {time.time() - t1:.0f}s; binary cands {len(bc)}")
        save_cands(cands, scan_id, "full", now_iso)
        live = {(c["kind"], c["id"]): c for c in cands if c["pmax"] > 0.01 and (c["type"] != "c" or c.get("exhaustive"))}
        log(f"scan {scan_id}: raw cands {len(cands)}, rescan set {len(live)}, elapsed {time.time() - c0:.0f}s")
        # ---------------- fast rescans of candidates until the next full scan
        k = 0
        while live and time.time() + RESCAN_S < c0 + CYCLE_S and time.time() < t_end:
            time.sleep(max(0, RESCAN_S - ((time.time() - c0) % RESCAN_S)))
            k += 1
            toks = sorted({t for c in live.values() for t in json.loads(c["tokens"])})[:4000]
            bks, _, _ = csa.fetch_books(toks, workers=8)
            now_iso = datetime.now(timezone.utc).isoformat()
            now_ms = time.time() * 1000
            rc = []
            gids = {cid for (kind, cid) in live if kind == "negrisk"}
            if gids:
                # record every re-observation, including zero/negative ones, so persistence can be measured
                for gid in gids:
                    out, trad = csa.analyze_group(groups[gid], bks)
                    for ty in ("c", "d", "e"):
                        rc.append({"kind": "negrisk", "id": gid, "type": ty, "pmax": out.get(f"{ty}_pmax"),
                                   "edge0": out.get(f"{ty}_edge0"), "exhaustive": out.get("exhaustive"),
                                   "flags": "|".join(csa.flags_for(trad, bks, now_ms, now_iso)) if trad else "",
                                   "metrics": json.dumps(out, default=str), "legs": json.dumps(csa.leg_detail(trad, bks), default=str),
                                   "tokens": json.dumps([t for r in trad for t in r["tokens"]]), "title": groups[gid][0]["event_title"],
                                   "event_slug": groups[gid][0]["event_slug"]})
            bmap = {r["market_id"]: r for r in binaries}
            for (kind, cid) in list(live):
                if kind != "binary" or cid not in bmap:
                    continue
                r = bmap[cid]
                a = csa.analyze_binary(r, bks)
                if a is None:
                    continue
                rc.append({"kind": "binary", "id": cid, "type": "a" if a["a_pmax"] >= a["b_pmax"] else "b",
                           "pmax": max(a["a_pmax"], a["b_pmax"]), "metrics": json.dumps(a, default=str),
                           "flags": "|".join(csa.flags_for([r], bks, now_ms, now_iso)),
                           "legs": json.dumps(csa.leg_detail([r], bks), default=str), "tokens": json.dumps(r["tokens"]),
                           "title": r["question"], "event_slug": r["event_slug"]})
            save_cands(rc, scan_id, "rescan", now_iso, suffix=f"_r{k:02d}")
            alive = {(c["kind"], c["id"]) for c in rc if (c["pmax"] or 0) > 0.01 and (c["type"] != "c" or c.get("exhaustive"))}
            log(f"  rescan {scan_id}.{k}: {len(toks)} tokens, still positive {len(alive)}/{len(live)}")
        scan_id += 1
        rest = c0 + CYCLE_S - time.time()
        if rest > 0 and time.time() + rest < t_end:
            time.sleep(rest)
    stop.set()
    log("done")


if __name__ == "__main__":
    main(float(sys.argv[1]) if len(sys.argv) > 1 else 80)
