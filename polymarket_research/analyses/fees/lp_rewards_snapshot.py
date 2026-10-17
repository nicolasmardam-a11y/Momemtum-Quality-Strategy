"""Snapshot of current CLOB liquidity-reward configurations (public, read-only).

GET https://clob.polymarket.com/rewards/markets/current (500/page, next_cursor 'LTE=' = last page),
standard and sponsored=true. Writes data/derived/lp_rewards_current_<date>.parquet.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr.http import request_json  # noqa: E402


def pull(sponsored: bool) -> list[dict]:
    rows, cur = [], None
    while True:
        p = {"sponsored": "true"} if sponsored else {}
        if cur:
            p["next_cursor"] = cur
        j = request_json("https://clob.polymarket.com/rewards/markets/current", p, source="clob")
        for m in j.get("data") or []:
            cfg = m.get("rewards_config") or []
            rows.append({
                "condition_id": m.get("condition_id"), "sponsored_query": sponsored,
                "rewards_max_spread": m.get("rewards_max_spread"), "rewards_min_size": m.get("rewards_min_size"),
                "native_daily_rate": m.get("native_daily_rate"), "sponsored_daily_rate": m.get("sponsored_daily_rate"),
                "total_daily_rate": m.get("total_daily_rate"), "sponsors_count": m.get("sponsors_count"),
                "cfg_rate_per_day": sum(float(c.get("rate_per_day") or 0) for c in cfg),
                "cfg_assets": "|".join(sorted({c.get("asset_address") or "" for c in cfg})),
                "cfg_start_min": min((c.get("start_date") for c in cfg if c.get("start_date")), default=None),
                "cfg_end_max": max((c.get("end_date") for c in cfg if c.get("end_date")), default=None),
            })
        cur = j.get("next_cursor")
        if not cur or cur == "LTE=":
            return rows


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    df = pd.DataFrame(pull(False) + pull(True))
    df["fetched_at_utc"] = now.isoformat()
    out = ROOT / "data" / "derived" / f"lp_rewards_current_{now:%Y-%m-%d}.parquet"
    df.to_parquet(out, index=False)
    print(out, len(df))
    print(df.groupby("sponsored_query")[["native_daily_rate", "sponsored_daily_rate", "total_daily_rate", "cfg_rate_per_day"]].sum())
