"""Verifier check (read-only): total configured liquidity rewards per day, CLOB GET /rewards/markets/current (public)."""
import json, statistics, time
from pmr.http import request_json
rows, cur = [], None
for _ in range(100):
    p = {"next_cursor": cur} if cur else {}
    j = request_json("https://clob.polymarket.com/rewards/markets/current", p, source="clob")
    rows += j.get("data") or []
    cur = j.get("next_cursor")
    if not cur or cur == "LTE=":
        break
print("rows", len(rows)); print("example", json.dumps(rows[0])[:600])
per = {}
for r in rows:
    tot = sum(float(c.get("rewards_daily_rate") or c.get("total_daily_rate") or 0) for c in (r.get("rewards_config") or []))
    tot = float(r.get("total_daily_rate") or tot)
    per[r.get("condition_id")] = per.get(r.get("condition_id"), 0) + tot
v = sorted(per.values())
print("markets", len(per), "total $/day", round(sum(v)), "median", v[len(v)//2], "p90", v[int(.9*len(v))], "max", v[-1])
json.dump({"rows": len(rows), "markets": len(per), "total": sum(v), "median": v[len(v)//2], "max": v[-1], "utc": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())},
          open("data/derived/verification_lp_rewards_sum.json", "w"))
