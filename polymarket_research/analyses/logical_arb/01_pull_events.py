"""Pull every open Gamma event with its nested markets (read-only).

Run from polymarket_research/:  python -m analyses.logical_arb.01_pull_events
Writes data/derived/la_events_<date>.parquet (one row per event) and
data/derived/la_markets_<date>.parquet (one row per open, order-book market).
Raw pages are recorded by pmr.http under data/raw/gamma/live/<date>/.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

MKT_KEYS = ["id", "question", "conditionId", "slug", "endDate", "startDate", "description", "resolutionSource",
            "outcomes", "outcomePrices", "clobTokenIds", "active", "closed", "acceptingOrders", "enableOrderBook",
            "negRisk", "negRiskOther", "groupItemTitle", "groupItemThreshold", "questionID", "umaResolutionStatus",
            "umaResolutionStatuses", "feesEnabled", "feeType", "orderPriceMinTickSize", "orderMinSize", "bestBid",
            "bestAsk", "spread", "lastTradePrice", "volumeNum", "liquidityNum", "volume24hr", "comboStatus",
            "rfqEnabled", "fallbackResolutionType", "gameStartTime", "secondsDelay", "sportsMarketType", "line",
            "customLiveness", "umaEndDate", "endDateIso", "createdAt", "version"]


def main() -> None:
    fetched = datetime.now(timezone.utc)
    ev_rows, mk_rows = [], []
    n = 0
    for e in api.gamma_keyset("events", {"closed": "false"}):
        n += 1
        tags = e.get("tags") or []
        series = e.get("series") or []
        ev = {
            "event_id": e.get("id"), "event_slug": e.get("slug"), "event_title": e.get("title"),
            "event_description": e.get("description"), "event_resolutionSource": e.get("resolutionSource"),
            "event_endDate": e.get("endDate"), "event_negRisk": e.get("negRisk"),
            "enableNegRisk": e.get("enableNegRisk"), "negRiskAugmented": e.get("negRiskAugmented"),
            "seriesSlug": e.get("seriesSlug") or (series[0].get("slug") if series else None),
            "series_title": series[0].get("title") if series else None,
            "tag_slugs": "|".join(t.get("slug") or "" for t in tags),
            "event_volume": e.get("volume"), "event_liquidity": e.get("liquidity"),
            "n_markets_total": len(e.get("markets") or []),
        }
        ev_rows.append(ev)
        for m in e.get("markets") or []:
            if m.get("closed") or not m.get("enableOrderBook"):
                continue
            r = {k: m.get(k) for k in MKT_KEYS}
            fs = m.get("feeSchedule") or {}
            r["fee_rate"] = fs.get("rate")
            r["fee_exponent"] = fs.get("exponent")
            r["feeSchedule_raw"] = json.dumps(fs) if fs else None
            for k in ("outcomes", "outcomePrices", "clobTokenIds", "umaResolutionStatuses"):
                if r.get(k) is not None and not isinstance(r[k], str):
                    r[k] = json.dumps(r[k])
            r.update({k: ev[k] for k in ("event_id", "event_slug", "event_title", "event_negRisk", "seriesSlug",
                                         "tag_slugs", "enableNegRisk", "negRiskAugmented")})
            mk_rows.append(r)
        if n % 1000 == 0:
            print(n, len(mk_rows), flush=True)
    evdf = pd.DataFrame(ev_rows).drop_duplicates("event_id")
    mkdf = pd.DataFrame(mk_rows).drop_duplicates("id")
    for df in (evdf, mkdf):
        df["fetched_at_utc"] = fetched.isoformat()
    out = ROOT / "data" / "derived"
    evdf.to_parquet(out / f"la_events_{fetched:%Y-%m-%d}.parquet", index=False)
    mkdf.to_parquet(out / f"la_markets_{fetched:%Y-%m-%d}.parquet", index=False)
    print("events", len(evdf), "open markets", len(mkdf))


if __name__ == "__main__":
    main()
