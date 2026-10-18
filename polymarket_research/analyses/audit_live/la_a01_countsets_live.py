"""AUDIT logical_arb (auditor 2026-10-18): independent live re-check of the k-of-n ALL_NO count sets.

Independent of 06_count_sets.py / 03b_snapshot_cnt.py:
  * fresh Gamma /events/{id} pull per snapshot (membership, acceptingOrders, closed, negRisk, feeSchedule,
    orderMinSize, tick, description template diff vs the study's 2026-10-17w2 metadata);
  * BOTH token books per leg (YES and NO) in one POST /books per set, so the NO leg is priced on the NO token's own
    asks (not only via the 1 - YES-bid mirror), with a mirror-consistency check and book-timestamp age;
  * own depth walk: equal q shares on every leg, each leg pays rate*(p(1-p))^exponent per share (feeSchedule),
    stop when the marginal set cost >= payoff (n_buyable - k); per-leg min size and $1 notional enforced.
Run from polymarket_research/:  PMR_RATE_SCALE=1 python -m analyses.audit_live.la_a01_countsets_live <n> <interval_s>
Output: data/derived/audit_la/cnt_live_<UTC>.parquet (one row per set x snapshot) + legs_<UTC>.parquet (top-of-book
per leg) + meta_<UTC>.json (rules-template check).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

SETS = {"531533": (5, "Oscars Best Actor", "2027-01-21"), "801515": (2, "CFP title game", "2027-01-26"),
        "1188161": (5, "Oscars Best Actress", "2027-01-21"), "1188310": (5, "Oscars Supp. Actor", "2027-01-21"),
        "811116": (5, "Ballon d'Or Top 5 (NEAR)", "2026-10-26"), "811117": (3, "Ballon d'Or Top 3 (NEAR)", "2026-10-26"),
        "904908": (3, "LaLiga relegated (NEAR)", "2027-05-31"), "956300": (2, "NBA WCF", "2027-05-20"),
        "1198837": (7, "Oscars Director (k=7, duos)", "2027-01-21")}
OUT = ROOT / "data" / "derived" / "audit_la"
OUT.mkdir(parents=True, exist_ok=True)
N, INTERVAL = int(sys.argv[1]), float(sys.argv[2])
OLD = pd.read_parquet(ROOT / "data/derived/la_markets_2026-10-17w2.parquet", columns=["id", "event_id", "description", "groupItemTitle"])
OLD = OLD[OLD.event_id.astype(str).isin(SETS)]


def template(desc: str, name: str) -> str:
    d = desc or ""
    for part in sorted({name, *name.split()}, key=len, reverse=True):
        if len(part) > 2:
            d = d.replace(part, "<X>")
    return re.sub(r"\s+", " ", d).strip()


def walk(no_ladders, rates, expos, payoff, min_sizes):
    """Equal shares on each leg; returns q, cost, top marginal cost, edge at top."""
    pos = [0] * len(no_ladders)
    left = [lad[0][1] for lad in no_ladders]
    q = cost = 0.0
    top = None
    while True:
        px = [no_ladders[i][pos[i]][0] for i in range(len(no_ladders))]
        mc = sum(p + r * (p * (1 - p)) ** e for p, r, e in zip(px, rates, expos))
        top = mc if top is None else top
        if mc >= payoff:
            break
        take = min(left)
        q += take
        cost += take * mc
        stop = False
        for i in range(len(no_ladders)):
            left[i] -= take
            if left[i] <= 1e-9:
                pos[i] += 1
                if pos[i] >= len(no_ladders[i]):
                    stop = True
                    break
                left[i] = no_ladders[i][pos[i]][1]
        if stop:
            break
    # executable only if q >= max per-leg min size and every leg notional >= $1 at its best price
    ok = q >= max(min_sizes) and all(q * lad[0][0] >= 1.0 for lad in no_ladders)
    return q, cost, top, ok


meta_rows, set_rows, leg_rows = [], [], []
for k_snap in range(N):
    t0 = datetime.now(timezone.utc)
    for eid, (k, name, res_date) in SETS.items():
        ev = request_json(f"{api.GAMMA}/events/{eid}", source="gamma")
        mk = [m for m in ev.get("markets", []) if not m.get("closed")]
        tradable = [m for m in mk if m.get("acceptingOrders") and m.get("enableOrderBook") and api.jlist(m.get("outcomes")) == ["Yes", "No"]]
        toks = []
        for m in tradable:
            ids = api.jlist(m["clobTokenIds"])
            toks += [ids[0], ids[1]]
        tf = time.time()
        bks = {b["asset_id"]: b for b in api.books(toks)}
        tf2 = time.time()
        now_ms = tf2 * 1000
        if k_snap == 0:  # rules check once
            old = OLD[OLD.event_id.astype(str) == eid]
            tmpl = {}
            for m in mk:
                tmpl.setdefault(hashlib.md5(template(m.get("description"), m.get("groupItemTitle") or "").encode()).hexdigest()[:8], []).append(m.get("groupItemTitle"))
            meta_rows.append({"event_id": eid, "name": name, "n_open": len(mk), "n_tradable": len(tradable),
                              "n_old": len(old), "added": sorted(set(str(m["id"]) for m in mk) - set(old.id.astype(str))),
                              "removed": sorted(set(old.id.astype(str)) - set(str(m["id"]) for m in mk)),
                              "negRisk": sorted({bool(m.get("negRisk")) for m in mk}),
                              "fee": sorted({json.dumps(m.get("feeSchedule"), sort_keys=True) for m in mk}),
                              "feesEnabled": sorted({bool(m.get("feesEnabled")) for m in mk}),
                              "minsize": sorted({str(m.get("orderMinSize")) for m in mk}),
                              "ticks": sorted({str(m.get("orderPriceMinTickSize")) for m in mk}),
                              "holdingRewards": sorted({bool(m.get("holdingRewardsEnabled")) for m in mk}),
                              "uma": sorted({str(m.get("umaResolutionStatus")) for m in mk}),
                              "endDates": sorted({str(m.get("endDate")) for m in mk}),
                              "templates": {h: len(v) for h, v in tmpl.items()},
                              "template_minority": {h: v for h, v in tmpl.items() if len(v) < max(len(x) for x in tmpl.values())},
                              "desc_changed_vs_w2": int(sum(1 for m in mk if str(m["id"]) in set(old.id.astype(str)) and
                                                             (m.get("description") or "") != old.set_index(old.id.astype(str)).description.get(str(m["id"]), ""))),
                              "sample_desc": (mk[0].get("description") or "")[:1500]})
        lad_no, lad_mirror, rates, expos, mins = [], [], [], [], []
        sum_bid = 0.0
        mirror_bad = crossed = 0
        ages = []
        for m in tradable:
            yid, nid = api.jlist(m["clobTokenIds"])[:2]
            by, bn = bks.get(yid), bks.get(nid)
            if not by or not bn:
                continue
            fs = m.get("feeSchedule") or {}
            r = float(fs.get("rate", 0.05)) if m.get("feesEnabled", True) else 0.0
            e = float(fs.get("exponent", 1.0))
            yb = by["bids"][0] if by["bids"] else None
            ya = by["asks"][0] if by["asks"] else None
            na = bn["asks"][0] if bn["asks"] else None
            if yb and ya and yb[0] >= ya[0]:
                crossed += 1
            if yb and na and abs((1 - yb[0]) - na[0]) > 1e-9:
                mirror_bad += 1
            ages.append((now_ms - (by["timestamp_ms"] or now_ms)) / 1000)
            leg_rows.append({"snap_utc": t0.isoformat(), "event_id": eid, "market_id": str(m["id"]), "who": m.get("groupItemTitle"),
                             "yes_bid": yb[0] if yb else None, "yes_bid_sz": yb[1] if yb else None,
                             "yes_ask": ya[0] if ya else None, "no_ask": na[0] if na else None, "no_ask_sz": na[1] if na else None,
                             "tick": by["tick_size"], "min_size": by["min_order_size"], "rate": r, "book_age_s": ages[-1]})
            if not bn["asks"]:
                continue  # unbuyable leg: drop it; payoff bound falls by one
            sum_bid += yb[0] if yb else 0.0
            lad_no.append(bn["asks"])
            lad_mirror.append([(round(1 - p, 6), s) for p, s in by["bids"]])
            rates.append(r)
            expos.append(e)
            mins.append(max(float(m.get("orderMinSize") or 5), by["min_order_size"] or 5))
        nb = len(lad_no)
        pay = nb - k
        row = {"snap_utc": t0.isoformat(), "snap_k": k_snap, "event_id": eid, "name": name, "k": k, "n_tradable": len(tradable),
               "n_buyable": nb, "payoff": pay, "sum_best_yes_bid": sum_bid, "mirror_mismatch_legs": mirror_bad,
               "crossed_legs": crossed, "max_book_age_s": max(ages) if ages else None, "fetch_s": tf2 - tf, "res_date": res_date}
        for tag, lads in (("no", lad_no), ("mirror", lad_mirror)):
            if pay > 0 and lads and all(lads):
                q, cost, top, ok = walk(lads, rates, expos, pay, mins)
                days = (pd.Timestamp(res_date, tz="UTC") - pd.Timestamp(t0)).total_seconds() / 86400
                row.update({f"{tag}_top_cost": top, f"{tag}_q": q, f"{tag}_cost": cost, f"{tag}_profit": q * pay - cost,
                            f"{tag}_edge": (q * pay - cost) / cost if cost else 0.0, f"{tag}_exec_ok": ok,
                            f"{tag}_ann": ((q * pay - cost) / cost) * 365 / days if cost else 0.0})
        set_rows.append(row)
    print(f"snap {k_snap} {t0:%H:%M:%S}", " | ".join(f"{r['name'][:14]} top={r.get('no_top_cost', float('nan')):.3f}/{r['payoff']} "
                                                     f"P=${r.get('no_profit', 0):.0f}" for r in set_rows[-len(SETS):]), flush=True)
    stamp = t0.strftime("%Y%m%dT%H%M%S") if k_snap == 0 else stamp
    pd.DataFrame(set_rows).to_parquet(OUT / f"cnt_live_{stamp}.parquet", index=False)
    pd.DataFrame(leg_rows).to_parquet(OUT / f"legs_{stamp}.parquet", index=False)
    if k_snap == 0:
        (OUT / f"meta_{stamp}.json").write_text(json.dumps(meta_rows, indent=1, default=str))
    if k_snap < N - 1:
        time.sleep(max(0, INTERVAL - (datetime.now(timezone.utc) - t0).total_seconds()))
print("done", flush=True)
