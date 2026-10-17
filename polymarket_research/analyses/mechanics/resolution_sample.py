"""Sample of recently closed markets: resolver contract, Gamma resolution-status history,
and Data API v2 /v2/resolutions lifecycle (was_disputed, reporter, resolved_at).

Read-only. Purpose: estimate how often resolutions are disputed and how long capital
stays locked between a market's endDate / closedTime and on-chain resolution.

Sampling: all markets whose endDate falls in N fixed 6-hour UTC windows (chosen in
advance, spread over Aug-Oct 2026), then at most CAP markets per fee-type stratum are
sent to /v2/resolutions. Output: data/derived/mechanics_resolution_sample.parquet.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

WINDOWS = [  # fixed before looking at any results
    ("2026-08-05T12:00:00Z", "2026-08-05T18:00:00Z"),
    ("2026-08-20T00:00:00Z", "2026-08-20T06:00:00Z"),
    ("2026-09-03T18:00:00Z", "2026-09-04T00:00:00Z"),
    ("2026-09-17T12:00:00Z", "2026-09-17T18:00:00Z"),
    ("2026-10-01T00:00:00Z", "2026-10-01T06:00:00Z"),
    ("2026-10-08T18:00:00Z", "2026-10-09T00:00:00Z"),
]
CAP = 600
random.seed(20261017)


def category(m: dict) -> str:
    ft = (m.get("feeType") or "").lower()
    q = (m.get("question") or "").lower()
    if "up or down" in q or ft.startswith("crypto"):
        return "crypto"
    if ft.startswith("sports") or m.get("sportsMarketType") or m.get("gameStartTime"):
        return "sports"
    return ft.split("_")[0] if ft else "nofee_or_unknown"


def main() -> None:
    rows = []
    for lo, hi in WINDOWS:
        for m in api.gamma_keyset("markets", {"closed": "true", "limit": 100, "end_date_min": lo, "end_date_max": hi}, cache=True):
            rows.append({
                "window": lo, "conditionId": m.get("conditionId"), "question": m.get("question"),
                "version": m.get("version"), "negRisk": m.get("negRisk"), "feeType": m.get("feeType"),
                "category": category(m), "endDate": m.get("endDate"), "closedTime": m.get("closedTime"),
                "umaResolutionStatuses": m.get("umaResolutionStatuses"), "umaResolutionStatus": m.get("umaResolutionStatus"),
                "automaticallyResolved": m.get("automaticallyResolved"), "fallbackResolutionType": m.get("fallbackResolutionType"),
                "resolvedBy": m.get("resolvedBy"), "umaBond": m.get("umaBond"), "umaReward": m.get("umaReward"),
                "customLiveness": m.get("customLiveness"), "outcomePrices": m.get("outcomePrices"),
                "volumeNum": m.get("volumeNum"), "sportsMarketType": m.get("sportsMarketType"),
            })
    df = pd.DataFrame(rows).drop_duplicates("conditionId")
    print("closed markets in windows:", len(df))
    print(df.groupby(["category"]).size().to_string())

    # stratified subsample for the resolution lifecycle lookup
    pick = []
    for cat, g in df.groupby("category"):
        ids = list(g["conditionId"].dropna())
        random.shuffle(ids)
        pick += ids[:CAP]
    res = {}
    for i in range(0, len(pick), 20):
        chunk = pick[i:i + 20]
        j = request_json("https://data-api.polymarket.com/v2/resolutions", {"condition": ",".join(chunk)},
                         source="data-api", cache=True)
        for r in j.get("data") or []:
            cid = r.get("condition_id")
            if cid and cid not in res:
                res[cid] = r
    rdf = pd.DataFrame([{**{"conditionId": k}, **{f"r_{a}": (json.dumps(b) if isinstance(b, (list, dict)) else b)
                                                    for a, b in v.items()}} for k, v in res.items()])
    df["in_lookup"] = df["conditionId"].isin(set(pick))
    out = df.merge(rdf, on="conditionId", how="left")
    path = ROOT / "data" / "derived" / "mechanics_resolution_sample.parquet"
    out.to_parquet(path)
    print("->", path, "lookups", len(pick), "rows returned", len(res))


if __name__ == "__main__":
    main()
