"""Verifier check: is the TAKER_REBATE a share of taker fees paid (18% Gold reconciliation)?

Read-only. Pulls /v2/activity for one wallet and recomputes daily taker fees from TRADE rows.
"""
import json
from collections import defaultdict
from datetime import datetime, timezone

from pmr import api

W = "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb"
rows = api.activity(W, start=1)
print("rows", len(rows))
types = defaultdict(int)
for r in rows:
    types[r.get("type")] += 1
print(dict(types))
print("sample TRADE row:", json.dumps(next(r for r in rows if r.get("type") == "TRADE"), indent=0)[:1500])
for r in rows:
    if r.get("type") in ("TAKER_REBATE", "MAKER_REBATE"):
        ts = datetime.fromtimestamp(int(r["timestamp"]), timezone.utc)
        print(r["type"], ts.isoformat(), r.get("usdc_size"), r.get("size"))

# Implied fee for TRADE rows: BUY usdc_size = size*price + fee ; SELL usdc_size = size*price - fee
fees_by_day = defaultdict(float)
for r in rows:
    if r.get("type") != "TRADE":
        continue
    sz, px, usd = float(r["size"]), float(r["price"]), float(r["usdc_size"])
    fee = usd - sz * px if r.get("side") == "BUY" else sz * px - usd
    d = datetime.fromtimestamp(int(r["timestamp"]), timezone.utc).date().isoformat()
    fees_by_day[d] += fee
for d in sorted(fees_by_day):
    if abs(fees_by_day[d]) > 1:
        print(d, round(fees_by_day[d], 2), "x0.18 =", round(0.18 * fees_by_day[d], 2))
print("total implied fees", round(sum(fees_by_day.values()), 2))
print("user-stats", json.dumps(api.user_stats(W))[:1500])
