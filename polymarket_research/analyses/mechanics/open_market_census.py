"""Census of currently open Gamma markets: protocol version, neg-risk flags,
secondsDelay, tick size, min size, fee type, combo/RFQ flags.

Read-only. Output: data/derived/mechanics_open_markets_<date>.parquet and a
printed summary. Run from polymarket_research/:  python -m analyses.mechanics.open_market_census
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pmr import api  # noqa: E402

FIELDS = [
    "id", "conditionId", "questionID", "slug", "question", "version", "negRisk", "negRiskOther",
    "secondsDelay", "orderPriceMinTickSize", "orderMinSize", "feesEnabled", "feeType",
    "comboStatus", "rfqEnabled", "acceptingOrders", "enableOrderBook", "endDate", "startDate",
    "umaResolutionStatus", "umaResolutionStatuses", "fallbackResolutionType", "automaticallyResolved",
    "umaBond", "umaReward", "customLiveness", "resolvedBy", "bestBid", "bestAsk", "liquidityNum",
    "volume24hr", "clearBookOnStart", "gameStartTime", "sportsMarketType",
]


def main() -> None:
    rows = []
    for m in api.gamma_keyset("markets", {"closed": "false", "limit": 100}):
        r = {k: m.get(k) for k in FIELDS}
        ev = (m.get("events") or [{}])[0]
        r["event_id"] = ev.get("id")
        r["event_slug"] = ev.get("slug")
        r["event_negRiskAugmented"] = ev.get("negRiskAugmented")
        r["event_enableNegRisk"] = ev.get("enableNegRisk")
        r["event_negRiskMarketID"] = ev.get("negRiskMarketID")
        r["event_negRiskFeeBips"] = ev.get("negRiskFeeBips")
        tags = ev.get("tags") or []
        r["event_tags"] = json.dumps([t.get("slug") for t in tags]) if tags else None
        r["n_position_ids"] = len(m.get("positionIds") or [])
        for k, v in list(r.items()):
            if isinstance(v, (list, dict)):
                r[k] = json.dumps(v)
        rows.append(r)
    df = pd.DataFrame(rows)
    out = Path(__file__).resolve().parents[2] / "data" / "derived" / f"mechanics_open_markets_{datetime.now(timezone.utc):%Y%m%d}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)
    print("rows", len(df), "->", out)
    for col in ["version", "negRisk", "negRiskOther", "secondsDelay", "orderPriceMinTickSize", "orderMinSize",
                "feeType", "comboStatus", "rfqEnabled", "fallbackResolutionType", "automaticallyResolved",
                "umaBond", "umaReward", "customLiveness", "event_negRiskAugmented", "event_negRiskFeeBips",
                "umaResolutionStatus", "acceptingOrders"]:
        print(f"\n== {col}")
        print(df[col].astype(str).value_counts(dropna=False).head(15).to_string())


if __name__ == "__main__":
    main()
