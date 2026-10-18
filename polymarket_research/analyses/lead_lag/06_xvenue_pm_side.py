"""Polymarket side of the cross-venue comparison (read-only): rules, fee schedule and executable top-of-book for
events that Kalshi also lists (Fed decision, House/Senate control). No Kalshi market data is requested (see notes 0.2).
Run: python -m analyses.lead_lag.06_xvenue_pm_side -> data/derived/lead_lag/xvenue_pm_side.json
"""
import json
from datetime import datetime, timezone
from pmr import api
SLUGS = ["fed-decision-in-october-20260617190323537", "which-party-will-win-the-house-in-2026", "which-party-will-win-the-senate-in-2026"]
out = {"fetched_utc": datetime.now(timezone.utc).isoformat(), "events": []}
for s in SLUGS:
    e = api.gamma_events(slug=s)[0]
    mk = []
    toks = []
    for m in e.get("markets") or []:
        t = api.jlist(m.get("clobTokenIds"))
        mk.append({"question": m.get("question"), "slug": m.get("slug"), "fee": m.get("feeSchedule"), "feeType": m.get("feeType"),
                   "endDate": m.get("endDate"), "tokens": t, "volume": m.get("volumeNum"), "active": m.get("active"), "closed": m.get("closed")})
        toks += t[:1]
    bk = {b["asset_id"]: b for b in api.books([t for t in toks if t])}
    for m in mk:
        b = bk.get(m["tokens"][0]) if m["tokens"] else None
        if b:
            m["yes_bid"], m["yes_ask"] = (b["bids"][0] if b["bids"] else None), (b["asks"][0] if b["asks"] else None)
            m["yes_ask_depth_usd_3c"] = sum(p * q for p, q in b["asks"] if b["asks"] and p <= b["asks"][0][0] + 0.03)
            m["yes_bid_depth_usd_3c"] = sum(p * q for p, q in b["bids"] if b["bids"] and p >= b["bids"][0][0] - 0.03)
        m.pop("tokens")
    out["events"].append({"slug": s, "title": e.get("title"), "description": (e.get("description") or (e.get("markets") or [{}])[0].get("description") or "")[:2500],
                          "resolutionSource": e.get("resolutionSource"), "volume": e.get("volume"), "markets": mk})
json.dump(out, open("data/derived/lead_lag/xvenue_pm_side.json", "w"), indent=1, default=str)
for ev in out["events"]:
    print("==", ev["title"], ev["volume"])
    print(ev["description"][:900].replace("\n", " "))
    for m in ev["markets"]:
        if m.get("active") and not m.get("closed"):
            print("  ", (m["question"] or "")[:70], m.get("feeType"), (m.get("fee") or {}).get("rate"), m.get("yes_bid"), m.get("yes_ask"),
                  round(m.get("yes_ask_depth_usd_3c") or 0), round(m.get("yes_bid_depth_usd_3c") or 0))
