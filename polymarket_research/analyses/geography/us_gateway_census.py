"""Category census of open Polymarket US markets via the public gateway (no auth).

Source: https://docs.polymarket.us/api-reference/markets/get-markets (GET https://gateway.polymarket.us/v1/markets).
"""
from __future__ import annotations
import collections, json, sys
from pmr.http import request_json

BASE = "https://gateway.polymarket.us/v1/markets"
rows, offset, limit = [], 0, 100
max_pages = int(sys.argv[1]) if len(sys.argv) > 1 else 60
for _ in range(max_pages):
    j = request_json(BASE, {"limit": limit, "offset": offset, "active": "true", "closed": "false"}, source="pm-us")
    ms = j.get("markets") or []
    rows += ms
    if len(ms) < limit:
        break
    offset += limit
print("open US markets fetched:", len(rows), "(page cap hit)" if len(rows) >= limit * max_pages else "")
print("by category:", collections.Counter(m.get("category") for m in rows).most_common())
print("by marketType:", collections.Counter(m.get("marketType") for m in rows).most_common(12))
print("by status:", collections.Counter(m.get("status") for m in rows).most_common())
print("slug prefixes:", collections.Counter((m.get("slug") or "").split("-")[0] for m in rows).most_common(15))
non_sport = [m for m in rows if m.get("category") != "sports"]
for m in non_sport[:25]:
    print("  ", m.get("category"), m.get("slug"), "|", (m.get("question") or "")[:80])
import pandas as pd
pd.DataFrame([{k: m.get(k) for k in ("id", "slug", "question", "category", "marketType", "status", "startDate", "endDate")} for m in rows]
             ).to_parquet("data/derived/pm_us_open_markets_2026-10-17.parquet", index=False)
# NOTE: default ordering returned the first 8,000 open markets (startDate 2026-03-19..2026-08-19); not a full census.
