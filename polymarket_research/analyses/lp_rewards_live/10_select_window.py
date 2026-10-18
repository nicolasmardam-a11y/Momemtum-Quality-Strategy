"""Select the websocket market set for an ADDITIONAL capture window with the SAME rule as 02_select.py (stratum A:
reward market with volume_24hr >= $500, acceptingOrders, mid 0.15-0.85, touch spread <= rewardsMaxSpread, class quotas,
one market per event, not ending within 3 h when possible), from a fresh rewards snapshot.
Usage: python -m analyses.lp_rewards_live.10_select_window <rewards_tag> <label>  -> ws_markets_<label>.parquet
Does not overwrite xsec_markets.parquet / ws_markets.parquet (used to replay w1).
"""
import importlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sel = importlib.import_module("analyses.lp_rewards_live.02_select")
OUT = ROOT / "data" / "derived" / "lp_rewards_live"


def main(tag, label):
    r = pd.read_parquet(OUT / f"rewards_{tag}.parquet")
    r = r[r.total_daily_rate.fillna(0) > 0]
    x = r[r.in_multi == "both"].assign(stratum="A")
    g = sel.gamma_rows(x.condition_id.tolist())
    x = x.merge(g, on="condition_id", how="left")
    x["yes_token"] = x.yes_token.fillna(x.yes_token_g)
    x["no_token"] = x.no_token.fillna(x.no_token_g)
    x["fee_rate"] = pd.to_numeric(x.g_fee_rate, errors="coerce").fillna(x.fee_rate)
    x.loc[x.g_feesEnabled == False, "fee_rate"] = 0.0  # noqa: E712
    x["rebate_rate"] = pd.to_numeric(x.g_rebate_rate, errors="coerce").fillna(x.fee_rebateRate)
    x["fee_type"] = x.g_feeType.fillna(x.feeType)
    x["tick"] = pd.to_numeric(x.g_tick, errors="coerce").fillna(x.orderPriceMinTickSize)
    now = datetime.now(timezone.utc)
    w = x[x.g_acceptingOrders == True].copy()  # noqa: E712
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
        sub = sub.sort_values("volume_24hr", ascending=False).drop_duplicates("event_slug")
        picks.append(sub.head(k))
    ws = pd.concat(picks)
    ws.to_parquet(OUT / f"ws_markets_{label}.parquet", index=False)
    print("stratum A", len(x), "eligible", len(w), "ws markets", len(ws), ws.cls.value_counts().to_dict())
    w1 = pd.read_parquet(OUT / "ws_markets.parquet")
    print("overlap with w1 set:", int(ws.condition_id.isin(w1.condition_id).sum()))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
