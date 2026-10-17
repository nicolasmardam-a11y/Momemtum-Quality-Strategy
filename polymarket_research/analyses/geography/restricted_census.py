"""Census of the Gamma `restricted` flag on open markets (read-only, public data).

Counts open markets by `restricted` value and by category/tag-ish fields, and
saves a small sample of restricted vs unrestricted markets for inspection.
"""
from __future__ import annotations

import collections
import json
import sys

from pmr import api

MAX_PAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 200

rows = []
for m in api.gamma_keyset("markets", {"closed": "false"}, max_pages=MAX_PAGES):
    rows.append({
        "id": m.get("id"),
        "slug": m.get("slug"),
        "question": m.get("question"),
        "restricted": m.get("restricted"),
        "category": m.get("category"),
        "feeType": m.get("feeType"),
        "active": m.get("active"),
        "acceptingOrders": m.get("acceptingOrders"),
        "volumeNum": m.get("volumeNum"),
        "startDate": m.get("startDate"),
    })

print("open markets fetched:", len(rows))
c = collections.Counter(r["restricted"] for r in rows)
print("restricted counts:", dict(c))
by_fee = collections.Counter((r["feeType"], r["restricted"]) for r in rows)
for k, v in sorted(by_fee.items(), key=lambda kv: -kv[1])[:30]:
    print("feeType/restricted", k, v)
unres = [r for r in rows if r["restricted"] is False]
res = [r for r in rows if r["restricted"] is True]
print("\nsample UNRESTRICTED:")
for r in sorted(unres, key=lambda r: -(r["volumeNum"] or 0))[:15]:
    print(" ", r["slug"], r["feeType"], r["volumeNum"])
print("\nsample RESTRICTED (top volume):")
for r in sorted(res, key=lambda r: -(r["volumeNum"] or 0))[:10]:
    print(" ", r["slug"], r["feeType"], r["volumeNum"])
json.dump({"n": len(rows), "counts": {str(k): v for k, v in c.items()},
           "unrestricted": unres[:200]},
          open("data/derived/gamma_restricted_census_2026-10-17.json", "w"), indent=1, default=str)
