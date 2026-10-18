"""AUDIT complete_set_arb (auditor 2026-10-18): independent fresh-book re-check of every neg-risk group the study
ever saw with a gross violation (sum best YES bid > 1) or a net-positive (c exhaustive)/(d)/(e) candidate.

Independent of csa.py: fresh Gamma /events?slug= membership (negRiskMarketID, acceptingOrders, closed, feeSchedule,
secondsDelay, umaResolutionStatus, negRiskOther, placeholders), both token books per member, own fee/depth code.
  (e)  buy NO on the subset S of members with 1 - askN - fee > 0, convert -> |S|-1 pUSD (rest of YES valued 0):
       value/set = sum_S (1 - askN_i - fee_i) - 1, walked with equal shares on S.
  (c)  buy YES on every tradable member: 1 - sum(askY_i + fee_i); only meaningful if the group is exhaustive.
Run: PMR_RATE_SCALE=1 python -m analyses.audit_live.csa_a01_recheck <targets.parquet> <n_rounds> <interval_s>
Output: data/derived/audit_csa/recheck_<UTC>.parquet
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

T = pd.read_parquet(sys.argv[1])
NR, INTERVAL = int(sys.argv[2]), float(sys.argv[3])
OUT = ROOT / "data" / "derived" / "audit_csa"
OUT.mkdir(parents=True, exist_ok=True)


def fee(p, m):
    fs = m.get("feeSchedule") or {}
    if not m.get("feesEnabled", True) or not fs:
        r = 0.0 if m.get("feesEnabled") is False else 0.05
    else:
        r = float(fs.get("rate", 0.05))
    return r * (p * (1 - p)) ** float(fs.get("exponent", 1.0) if fs else 1.0)


def walk_e(ladders, mk):
    """Equal shares on every leg in ladders (NO asks); value per marginal set = sum(1-p-fee) - 1."""
    pos = [0] * len(ladders)
    left = [lad[0][1] for lad in ladders]
    q = prof = 0.0
    while True:
        v = sum(1 - ladders[i][pos[i]][0] - fee(ladders[i][pos[i]][0], mk[i]) for i in range(len(ladders))) - 1
        if v <= 0:
            break
        take = min(left)
        q += take
        prof += take * v
        stop = False
        for i in range(len(ladders)):
            left[i] -= take
            if left[i] <= 1e-9:
                pos[i] += 1
                if pos[i] >= len(ladders[i]):
                    stop = True
                    break
                left[i] = ladders[i][pos[i]][1]
        if stop:
            break
    return q, prof


rows = []
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
for rnd in range(NR):
    t0 = datetime.now(timezone.utc)
    for _, tg in T.iterrows():
        try:
            evs = request_json(f"{api.GAMMA}/events", {"slug": tg.slug}, source="gamma")
        except Exception as ex:  # noqa: BLE001
            rows.append({"round": rnd, "nr_id": tg.nr_id, "slug": tg.slug, "err": str(ex)[:100]})
            continue
        ev = evs[0] if isinstance(evs, list) and evs else {}
        mem = [m for m in ev.get("markets", []) if m.get("negRiskMarketID") == tg.nr_id]
        openm = [m for m in mem if not m.get("closed")]
        trad = [m for m in openm if m.get("acceptingOrders") and m.get("enableOrderBook")]
        toks = [t for m in trad for t in api.jlist(m["clobTokenIds"])[:2]]
        bk = {b["asset_id"]: b for b in api.books(toks)} if toks else {}
        sum_bid = sum_ask = 0.0
        e_lads, e_mk, c_val, crossed, nobid = [], [], 1.0, 0, 0
        for m in trad:
            y, n = api.jlist(m["clobTokenIds"])[:2]
            by, bn = bk.get(y), bk.get(n)
            if not by or not bn:
                continue
            if by["bids"] and by["asks"] and by["bids"][0][0] >= by["asks"][0][0]:
                crossed += 1
            sum_bid += by["bids"][0][0] if by["bids"] else 0.0
            nobid += 0 if by["bids"] else 1
            if by["asks"]:
                sum_ask += by["asks"][0][0]
                c_val -= by["asks"][0][0] + fee(by["asks"][0][0], m)
            else:
                c_val = float("nan")
            if bn["asks"] and 1 - bn["asks"][0][0] - fee(bn["asks"][0][0], m) > 0:
                e_lads.append(bn["asks"])
                e_mk.append(m)
        e_top = sum(1 - l[0][0] - fee(l[0][0], m) for l, m in zip(e_lads, e_mk)) - 1 if e_lads else -1.0
        gross_e = sum(1 - l[0][0] for l in e_lads) - 1 if e_lads else -1.0
        q, prof = walk_e(e_lads, e_mk) if e_top > 0 else (0.0, 0.0)
        rows.append({"round": rnd, "t": t0.isoformat(), "nr_id": tg.nr_id, "slug": tg.slug, "title": ev.get("title"),
                     "aug": bool(ev.get("negRiskAugmented")), "n_mem": len(mem), "n_open": len(openm), "n_trad": len(trad),
                     "n_placeholder_or_untradable": len(openm) - len(trad), "has_other": any(m.get("negRiskOther") for m in mem),
                     "in_play": any(float(m.get("secondsDelay") or 0) > 0 for m in trad),
                     "uma_flag": any(m.get("umaResolutionStatus") in ("proposed", "disputed") for m in mem),
                     "fee_rates": sorted({round(fee(0.5, m) / 0.25, 4) for m in trad}),
                     "sum_bidY": sum_bid, "sum_askY": sum_ask, "e_gross_top": gross_e, "e_net_top": e_top,
                     "e_q": q, "e_profit": prof, "c_net_top": c_val, "crossed": crossed, "no_bid_legs": nobid,
                     "study_exh": bool(tg.exh), "study_max_bid": tg.max_bid, "study_nobs": tg.nobs})
    D = pd.DataFrame(rows)
    D.to_parquet(OUT / f"recheck_{stamp}.parquet", index=False)
    r = D[D["round"] == rnd]
    print(f"round {rnd} {t0:%H:%M:%S} groups {len(r)} gross>1 {(r.sum_bidY > 1).sum()} e_net>0 {(r.e_net_top > 0).sum()} "
          f"e_profit>=1 {(r.e_profit >= 1).sum()} c_net>0 {(r.c_net_top > 0).sum()}", flush=True)
    if rnd < NR - 1:
        time.sleep(max(0, INTERVAL - (datetime.now(timezone.utc) - t0).total_seconds()))
print("done", flush=True)
