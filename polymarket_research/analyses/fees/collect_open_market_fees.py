"""Snapshot fee / reward parameters of every open Gamma market (read-only).

Run from polymarket_research/:  python -m analyses.fees.collect_open_market_fees
Writes data/derived/open_market_fees_<date>.parquet (one row per market).
Raw responses are recorded by pmr.http under data/raw/gamma/live/<date>/.
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

MAX_PAGES = int(sys.argv[1]) if len(sys.argv) > 1 else None


def row(m: dict) -> dict:
    fs = m.get("feeSchedule") or {}
    tags = m.get("tags") or []
    ev = (m.get("events") or [{}])[0]
    prices = api.jlist(m.get("outcomePrices"))
    return {
        "id": m.get("id"),
        "conditionId": m.get("conditionId"),
        "question": m.get("question"),
        "slug": m.get("slug"),
        "event_slug": ev.get("slug"),
        "event_version": ev.get("version"),
        "series_slug": ev.get("seriesSlug"),
        "createdAt": m.get("createdAt"),
        "endDate": m.get("endDate"),
        "active": m.get("active"),
        "acceptingOrders": m.get("acceptingOrders"),
        "enableOrderBook": m.get("enableOrderBook"),
        "negRisk": m.get("negRisk"),
        "version": m.get("version"),
        "feesEnabled": m.get("feesEnabled"),
        "feeType": m.get("feeType"),
        "fee_rate": fs.get("rate"),
        "fee_exponent": fs.get("exponent"),
        "fee_takerOnly": fs.get("takerOnly"),
        "fee_rebateRate": fs.get("rebateRate"),
        "feeSchedule_raw": json.dumps(fs) if fs else None,
        "makerBaseFee": m.get("makerBaseFee"),
        "takerBaseFee": m.get("takerBaseFee"),
        "holdingRewardsEnabled": m.get("holdingRewardsEnabled"),
        "rewardsMinSize": m.get("rewardsMinSize"),
        "rewardsMaxSpread": m.get("rewardsMaxSpread"),
        "clobRewards_daily": sum(float(r.get("rewardsDailyRate") or 0) for r in (m.get("clobRewards") or [])),
        "n_clobRewards": len(m.get("clobRewards") or []),
        "orderMinSize": m.get("orderMinSize"),
        "orderPriceMinTickSize": m.get("orderPriceMinTickSize"),
        "secondsDelay": m.get("secondsDelay"),
        "rfqEnabled": m.get("rfqEnabled"),
        "volume24hr": m.get("volume24hr"),
        "volumeNum": m.get("volumeNum"),
        "liquidityNum": m.get("liquidityNum"),
        "bestBid": m.get("bestBid"),
        "bestAsk": m.get("bestAsk"),
        "spread": m.get("spread"),
        "price_yes": float(prices[0]) if prices else None,
        "tag_slugs": "|".join(t.get("slug") or "" for t in tags),
        "tag_labels": "|".join(t.get("label") or "" for t in tags),
    }


def main() -> None:
    fetched = datetime.now(timezone.utc)
    rows = [row(m) for m in api.gamma_keyset("markets", {"closed": "false", "include_tag": "true"}, max_pages=MAX_PAGES)]
    df = pd.DataFrame(rows).drop_duplicates("id")
    df["fetched_at_utc"] = fetched.isoformat()
    out = ROOT / "data" / "derived" / f"open_market_fees_{fetched:%Y-%m-%d}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(out, len(df))


if __name__ == "__main__":
    main()
