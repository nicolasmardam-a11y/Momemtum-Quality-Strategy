"""Build the cross-section (strata A/B/C) of reward-eligible markets and the ~20-market websocket set.

A = every current reward market listed by /rewards/markets/multi with volume_24hr >= $500 (active);
B = seeded random 500 of the remaining reward markets; C = top 60 of the remaining by total_daily_rate.
Fresh Gamma rows (condition_ids, include_tag) give clobTokenIds, feeSchedule, tick, min size, reward params.
Writes data/derived/lp_rewards_live/xsec_markets.parquet and ws_markets.parquet.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

OUT = ROOT / "data" / "derived" / "lp_rewards_live"


def gamma_rows(cids):
    rows = []
    for i in range(0, len(cids), 50):
        j = request_json(f"{api.GAMMA}/markets/keyset", {"condition_ids": cids[i:i + 50], "limit": 100, "include_tag": "true"},
                         source="gamma")
        for m in j.get("markets") or []:
            fs = m.get("feeSchedule") or {}
            tok = api.jlist(m.get("clobTokenIds"))
            outc = api.jlist(m.get("outcomes"))
            rows.append({"condition_id": m.get("conditionId"), "g_question": m.get("question"), "g_slug": m.get("slug"),
                         "yes_token_g": tok[0] if tok else None, "no_token_g": tok[1] if len(tok) > 1 else None,
                         "outcome0": outc[0] if outc else None,
                         "g_feeType": m.get("feeType"), "g_feesEnabled": m.get("feesEnabled"),
                         "g_fee_rate": fs.get("rate") if isinstance(fs, dict) else None,
                         "g_fee_exp": fs.get("exponent") if isinstance(fs, dict) else None,
                         "g_rebate_rate": fs.get("rebateRate") if isinstance(fs, dict) else None,
                         "g_negRisk": m.get("negRisk"), "g_tick": m.get("orderPriceMinTickSize"), "g_min_order": m.get("orderMinSize"),
                         "g_rewardsMinSize": m.get("rewardsMinSize"), "g_rewardsMaxSpread": m.get("rewardsMaxSpread"),
                         "g_endDate": m.get("endDate"), "g_gameStartTime": m.get("gameStartTime"), "g_secondsDelay": m.get("secondsDelay"),
                         "g_volume24hr": m.get("volume24hr"), "g_bestBid": m.get("bestBid"), "g_bestAsk": m.get("bestAsk"),
                         "g_acceptingOrders": m.get("acceptingOrders"),
                         "g_tags": "|".join(t.get("slug", "") for t in (m.get("tags") or []))})
    return pd.DataFrame(rows).drop_duplicates("condition_id")


def main():
    r = pd.read_parquet(OUT / "rewards_t0.parquet")
    r = r[r.total_daily_rate.fillna(0) > 0]
    a = r[r.in_multi == "both"].assign(stratum="A")
    rest = r[r.in_multi != "both"]
    c = rest.nlargest(60, "total_daily_rate").assign(stratum="C")
    b = rest.drop(c.index).sample(500, random_state=20261017).assign(stratum="B")
    x = pd.concat([a, b, c], ignore_index=True)
    g = gamma_rows(x.condition_id.tolist())
    x = x.merge(g, on="condition_id", how="left")
    x["yes_token"] = x.yes_token.fillna(x.yes_token_g)
    x["no_token"] = x.no_token.fillna(x.no_token_g)
    x["fee_rate"] = pd.to_numeric(x.g_fee_rate, errors="coerce").fillna(x.fee_rate)
    x.loc[x.g_feesEnabled == False, "fee_rate"] = 0.0  # noqa: E712
    x["rebate_rate"] = pd.to_numeric(x.g_rebate_rate, errors="coerce").fillna(x.fee_rebateRate)
    x["fee_type"] = x.g_feeType.fillna(x.feeType)
    x["tick"] = pd.to_numeric(x.g_tick, errors="coerce").fillna(x.orderPriceMinTickSize)
    x.to_parquet(OUT / "xsec_markets.parquet", index=False)
    print("xsec", x.stratum.value_counts().to_dict(), "with yes_token", x.yes_token.notna().sum(),
          "gamma rows", len(g), "acceptingOrders", x.g_acceptingOrders.value_counts(dropna=False).to_dict())

    # ----- websocket set: active, mid 0.15-0.85, not ending within 3h, spread across fee classes
    now = datetime.now(timezone.utc)
    w = x[(x.stratum == "A") & (x.g_acceptingOrders == True)].copy()  # noqa: E712
    w["bb"] = pd.to_numeric(w.g_bestBid, errors="coerce"); w["ba"] = pd.to_numeric(w.g_bestAsk, errors="coerce")
    w["mid"] = (w.bb + w.ba) / 2
    w["end"] = pd.to_datetime(w.g_endDate, utc=True, errors="coerce")
    w = w[(w.mid.between(0.15, 0.85)) & (w.ba - w.bb <= w.rewards_max_spread / 100) & w.no_token.notna()]
    w["cls"] = w.fee_type.fillna("unknown").str.replace(r"_fees.*", "", regex=True)
    quota = {"politics": 4, "sports": 4, "weather": 2, "economics": 2, "finance": 2, "tech": 2, "culture": 2, "crypto": 2,
             "zero": 1, "mentions": 1, "unknown": 1}
    picks = []
    for cls, k in quota.items():
        sub = w[w.cls == cls]
        late = sub[sub.end > now + timedelta(hours=3)]
        sub = late if len(late) >= k else sub
        # one market per event within a class, highest 24h volume first
        sub = sub.sort_values("volume_24hr", ascending=False).drop_duplicates("event_slug")
        picks.append(sub.head(k))
    ws = pd.concat(picks)
    ws.to_parquet(OUT / "ws_markets.parquet", index=False)
    print("ws markets", len(ws))
    for _, m in ws.iterrows():
        print(f"  {m.cls:9s} vol24={m.volume_24hr:>9.0f} rate={m.total_daily_rate:>6.0f} v={m.rewards_max_spread} min={m.rewards_min_size} "
              f"mid={m.mid:.3f} end={str(m.end)[:16]} {str(m.question)[:55]}")


if __name__ == "__main__":
    main()
