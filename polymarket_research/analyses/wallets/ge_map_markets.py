"""Map every condition_id traded by GRIMDRIP / endlessFate / mintblade to its Gamma market and event.

Also pulls every market of each parent event (and of the sibling '-more-markets' event of
the same match) so economically overlapping positions can be checked.
Outputs: data/derived/ge_markets.parquet (traded markets), ge_event_markets.parquet (all
markets in the traded matches), ge_events.parquet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

OUT = ROOT / "data" / "derived"

MKT_FIELDS = ["id", "question", "conditionId", "slug", "groupItemTitle", "sportsMarketType", "line", "gameStartTime",
              "endDate", "closedTime", "umaEndDate", "outcomes", "outcomePrices", "clobTokenIds", "umaResolutionStatus",
              "umaResolutionStatuses", "feesEnabled", "feeType", "feeSchedule", "makerBaseFee", "takerBaseFee",
              "secondsDelay", "negRisk", "negRiskMarketID", "negRiskOther", "orderPriceMinTickSize", "orderMinSize",
              "volumeNum", "resolvedBy", "automaticallyResolved", "fallbackResolutionType", "rewardsMinSize",
              "rewardsMaxSpread", "holdingRewardsEnabled", "clearBookOnStart", "acceptingOrdersTimestamp", "restricted"]
EVT_FIELDS = ["id", "slug", "title", "startTime", "endDate", "closedTime", "eventDate", "score", "period", "ended",
              "finishedTimestamp", "gameId", "negRisk", "volume", "seriesSlug", "automaticallyResolved"]


def flat_market(m: dict) -> dict:
    row = {k: m.get(k) for k in MKT_FIELDS}
    for k in ("outcomes", "outcomePrices", "clobTokenIds", "umaResolutionStatuses"):
        row[k] = json.dumps(api.jlist(m.get(k)))
    row["feeSchedule"] = json.dumps(m.get("feeSchedule"))
    row["fee_rate"] = (m.get("feeSchedule") or {}).get("rate")
    md = m.get("marketMetadata") or {}
    row["optic_market"] = md.get("opticOddsMarketName")
    row["optic_selection"] = md.get("opticOddsSelection")
    row["optic_fixture"] = md.get("opticOddsFixtureId")
    ev = (m.get("events") or [{}])[0]
    for k in EVT_FIELDS:
        row[f"event_{k}"] = ev.get(k)
    row["event_tags"] = json.dumps([t.get("label") for t in (ev.get("tags") or [])])
    row["event_sportradar"] = (ev.get("eventMetadata") or {}).get("sportradarGameId")
    return row


def main() -> None:
    t = pd.read_parquet(OUT / "ge_trades_all.parquet")
    cids = sorted(t.condition_id.unique())
    ms = []
    for i in range(0, len(cids), 20):
        ms += api.gamma_markets(condition_ids=cids[i:i + 20], closed="true", cache=True)
    mk = pd.DataFrame([flat_market(m) for m in ms])
    print("traded markets", len(mk), "of", len(cids))
    # event-level detail (tags live on the events endpoint)
    ev_rows, all_mk = [], []
    slugs = set(mk.event_slug)
    # sibling events of the same match: base slug <-> base-more-markets
    slugs |= {s + "-more-markets" for s in slugs if not s.endswith("-more-markets")}
    slugs |= {s.replace("-more-markets", "") for s in slugs}
    for s in sorted(slugs):
        evs = api.gamma_events(slug=s, closed="true", cache=True)
        if not evs:
            evs = api.gamma_events(slug=s, cache=True)
        for e in evs:
            ev_rows.append({**{k: e.get(k) for k in EVT_FIELDS},
                            "tags": json.dumps([x.get("label") for x in (e.get("tags") or [])]),
                            "n_markets": len(e.get("markets") or []),
                            "sportradar": (e.get("eventMetadata") or {}).get("sportradarGameId")})
            for m in e.get("markets") or []:
                m = dict(m)
                m.setdefault("events", [e])
                all_mk.append(flat_market(m))
    evdf = pd.DataFrame(ev_rows).drop_duplicates("id")
    amk = pd.DataFrame(all_mk).drop_duplicates("conditionId")
    tagmap = dict(zip(evdf.slug, evdf.tags))
    mk["event_tags"] = mk.event_slug.map(tagmap)
    amk["event_tags"] = amk.event_slug.map(tagmap)
    # match key: base slug without -more-markets
    for df in (mk, amk):
        df["match_key"] = df.event_slug.str.replace("-more-markets", "", regex=False)
    mk.to_parquet(OUT / "ge_markets.parquet", index=False)
    amk.to_parquet(OUT / "ge_event_markets.parquet", index=False)
    evdf.to_parquet(OUT / "ge_events.parquet", index=False)
    print("events", len(evdf), "event markets", len(amk))


if __name__ == "__main__":
    main()
