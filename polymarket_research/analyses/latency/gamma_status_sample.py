"""Tally the status fields Gamma returns for recently closed markets (read-only).

Pulls closed markets whose endDate falls in a fixed window, then counts `archived`, `active`,
`umaResolutionStatus`, `umaResolutionStatuses` history (proposed/disputed), payout shape of
`outcomePrices` (0/1, 50-50, other), `automaticallyResolved`, `fallbackResolutionType`, and whether
`/v2/resolutions` agrees. Output: data/derived/gamma_status_sample_<UTC>.parquet and a printed summary.

Usage: python analyses/latency/gamma_status_sample.py [end_date_min] [end_date_max] [max_pages]
"""
from __future__ import annotations

import collections
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

lo = sys.argv[1] if len(sys.argv) > 1 else "2026-10-10T00:00:00Z"
hi = sys.argv[2] if len(sys.argv) > 2 else "2026-10-12T00:00:00Z"
pages = int(sys.argv[3]) if len(sys.argv) > 3 else 20
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")

rows = list(api.gamma_keyset("markets", {"closed": "true", "end_date_min": lo, "end_date_max": hi, "limit": 100}, cache=True, max_pages=pages))
keep = ["conditionId", "slug", "question", "endDate", "closedTime", "active", "closed", "archived", "restricted", "acceptingOrders",
        "umaResolutionStatus", "umaResolutionStatuses", "automaticallyResolved", "fallbackResolutionType", "resolvedBy",
        "outcomePrices", "negRisk", "version", "feeType", "volumeNum"]
df = pd.DataFrame([{k: r.get(k) for k in keep} for r in rows])


def payout(s):
    p = [float(x) for x in api.jlist(s)] if s else []
    if not p:
        return "missing"
    if sorted(p) == [0.0, 1.0]:
        return "0/1"
    if all(abs(x - 0.5) < 1e-9 for x in p):
        return "50-50"
    return "other:" + ",".join(f"{x:g}" for x in p)


df["payout_shape"] = df.outcomePrices.map(payout)
df["ever_disputed"] = df.umaResolutionStatuses.fillna("").str.contains("disputed")
# /v2/resolutions for a subsample (20 conditions per call)
sub = df.conditionId.dropna().head(400).tolist()
res = {}
for i in range(0, len(sub), 20):
    j = request_json(f"{api.DATA}/v2/resolutions", {"condition": ",".join(sub[i:i + 20])}, source="data-api", cache=True)
    for r in j.get("data") or []:
        res[r.get("condition_id")] = r
df["r_status"] = df.conditionId.map(lambda c: (res.get(c) or {}).get("status"))
df["r_was_disputed"] = df.conditionId.map(lambda c: (res.get(c) or {}).get("was_disputed"))
df["r_payouts"] = df.conditionId.map(lambda c: json.dumps((res.get(c) or {}).get("payouts")))
out = ROOT / "data" / "derived" / f"gamma_status_sample_{STAMP}.parquet"
df.to_parquet(out, index=False)
print("markets", len(df), "window", lo, hi)
for c in ["active", "closed", "archived", "restricted", "acceptingOrders", "umaResolutionStatus", "automaticallyResolved",
          "fallbackResolutionType", "payout_shape", "ever_disputed", "version", "r_status", "r_was_disputed"]:
    print(c, df[c].astype(str).value_counts(dropna=False).head(8).to_dict())
print("umaResolutionStatuses histories", collections.Counter(df.umaResolutionStatuses.fillna("None")).most_common(8))
print("->", out)
