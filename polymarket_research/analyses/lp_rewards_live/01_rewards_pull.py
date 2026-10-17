"""Pull current liquidity-reward configs (public CLOB) + market metadata; join to the 2026-10-17 Gamma fee census.

GET /rewards/markets/current (all pages) and GET /rewards/markets/multi (all pages, page_size 500; has tokens,
volume_24hr, spread). Writes data/derived/lp_rewards_live/rewards_<tag>.parquet. Read-only, unauthenticated.
Usage: python -m analyses.lp_rewards_live.01_rewards_pull <tag>
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr.http import request_json  # noqa: E402

OUT = ROOT / "data" / "derived" / "lp_rewards_live"
CLOB = "https://clob.polymarket.com"
MINVOL = 500  # multi lists ~all markets (incl. empty rewards_config); restrict to active ones


def pages(path, base):
    cur = None
    while True:
        p = dict(base)
        if cur:
            p["next_cursor"] = cur
        j = request_json(CLOB + path, p, source="clob")
        yield from j.get("data") or []
        cur = j.get("next_cursor")
        if not cur or cur == "LTE=":
            return


def main(tag):
    now = datetime.now(timezone.utc)
    cur = []
    for m in pages("/rewards/markets/current", {}):
        cfg = m.get("rewards_config") or []
        cur.append({"condition_id": m["condition_id"], "rewards_max_spread": m.get("rewards_max_spread"),
                    "rewards_min_size": m.get("rewards_min_size"), "native_daily_rate": m.get("native_daily_rate"),
                    "sponsored_daily_rate": m.get("sponsored_daily_rate"), "total_daily_rate": m.get("total_daily_rate"),
                    "cfg_rate_per_day": sum(float(c.get("rate_per_day") or 0) for c in cfg),
                    "cfg_start_min": min((c.get("start_date") for c in cfg if c.get("start_date")), default=None)})
    cur = pd.DataFrame(cur).drop_duplicates("condition_id")
    mul = []
    for m in pages("/rewards/markets/multi", {"page_size": 500, "min_volume_24hr": MINVOL}):
        t = m.get("tokens") or []
        mul.append({"condition_id": m["condition_id"], "question": m.get("question"), "market_slug": m.get("market_slug"),
                    "event_slug": m.get("event_slug"), "volume_24hr": m.get("volume_24hr"), "spread_multi": m.get("spread"),
                    "competitiveness": m.get("market_competitiveness"), "end_date": m.get("end_date"),
                    "multi_cfg_rate": sum(float(c.get("rate_per_day") or 0) for c in (m.get("rewards_config") or [])),
                    "yes_token": t[0]["token_id"] if t else None, "no_token": t[1]["token_id"] if len(t) > 1 else None,
                    "yes_outcome": t[0].get("outcome") if t else None, "yes_price": t[0].get("price") if t else None})
    mul = pd.DataFrame(mul).drop_duplicates("condition_id")
    df = cur.merge(mul, on="condition_id", how="left", indicator="in_multi")
    cen = pd.read_parquet(ROOT / "data/derived/open_market_fees_2026-10-17.parquet",
                          columns=["conditionId", "feeType", "fee_rate", "fee_exponent", "fee_rebateRate", "feesEnabled",
                                   "negRisk", "orderPriceMinTickSize", "orderMinSize", "secondsDelay", "tag_slugs",
                                   "rewardsMinSize", "rewardsMaxSpread", "volume24hr", "endDate"])
    df = df.merge(cen.rename(columns={"conditionId": "condition_id"}), on="condition_id", how="left")
    df["fetched_at_utc"] = now.isoformat()
    df["in_multi"] = df["in_multi"].astype(str)
    out = OUT / f"rewards_{tag}.parquet"
    df.to_parquet(out, index=False)
    print(out, len(cur), "current;", len(mul), "multi;", df.feeType.notna().sum(), "with census row")
    print("total_daily_rate sum", round(df.total_daily_rate.sum()), "median", df.total_daily_rate.median(),
          "p90", df.total_daily_rate.quantile(.9), "max", df.total_daily_rate.max())
    print(df.groupby("feeType", dropna=False).total_daily_rate.agg(["size", "sum"]).sort_values("sum", ascending=False).head(12))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%H%M"))
