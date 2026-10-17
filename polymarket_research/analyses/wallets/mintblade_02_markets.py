"""Map mintblade's condition_ids to Gamma markets and events (closed=true).

Also pulls every market of each parent event (so economically related markets of
the same match are visible) and the event tags. Output:
  data/derived/mintblade_markets.parquet   (one row per traded market)
  data/derived/mintblade_event_markets.parquet (all markets of the traded events)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "data" / "derived"
FIELDS = ["id", "question", "conditionId", "slug", "groupItemTitle", "outcomes", "outcomePrices", "clobTokenIds",
          "sportsMarketType", "gameStartTime", "startDate", "endDate", "closedTime", "umaEndDate",
          "umaResolutionStatus", "umaResolutionStatuses", "feesEnabled", "feeType", "feeSchedule",
          "secondsDelay", "negRisk", "negRiskMarketID", "orderPriceMinTickSize", "orderMinSize",
          "volumeNum", "rewardsMinSize", "rewardsMaxSpread", "holdingRewardsEnabled", "automaticallyResolved",
          "resolvedBy", "fallbackResolutionType", "line", "marketMetadata", "makerBaseFee", "takerBaseFee"]
EVF = ["id", "slug", "title", "startTime", "endDate", "closedTime", "score", "period", "finishedTimestamp",
       "negRisk", "volume", "openInterest", "gameId", "eventMetadata"]


def flat(m: dict) -> dict:
    r = {k: m.get(k) for k in FIELDS}
    ev = (m.get("events") or [{}])[0]
    for k in EVF:
        r[f"event_{k}"] = ev.get(k)
    r["series"] = ",".join(s.get("slug", "") for s in ev.get("series") or [])
    for k, v in list(r.items()):
        if isinstance(v, (dict, list)):
            r[k] = json.dumps(v)
    return r


def main():
    pos = pd.read_parquet(OUT / "mintblade_trades_all.parquet")
    cids = sorted(pos.condition_id.unique())
    ms = api.gamma_markets(condition_ids=cids, closed="true", cache=True)
    df = pd.DataFrame([flat(m) for m in ms])
    # Event tags and all sibling markets
    sib = []
    tags = {}
    for eid in sorted(set(df.event_id)):
        ev = request_json(f"{api.GAMMA}/events/{eid}", {"include_chat": "false"}, source="gamma", cache=True)
        tags[eid] = ",".join(t.get("slug", "") for t in ev.get("tags") or [])
        for m in ev.get("markets") or []:
            m = dict(m)
            m["events"] = [ev]
            sib.append(flat(m))
    df["event_tags"] = df.event_id.map(tags)
    df.to_parquet(OUT / "mintblade_markets.parquet", index=False)
    sdf = pd.DataFrame(sib)
    sdf["event_tags"] = sdf.event_id.map(tags)
    sdf.to_parquet(OUT / "mintblade_event_markets.parquet", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 80)
    print(df[["question", "sportsMarketType", "gameStartTime", "endDate", "closedTime", "outcomes", "outcomePrices",
              "umaResolutionStatus", "umaResolutionStatuses", "feeType", "feeSchedule", "secondsDelay", "negRisk",
              "event_slug", "event_title", "event_score", "event_finishedTimestamp", "event_tags"]].T.to_string())
    print(sdf[["event_slug", "question", "sportsMarketType", "outcomes", "outcomePrices", "conditionId"]].to_string())


if __name__ == "__main__":
    main()
