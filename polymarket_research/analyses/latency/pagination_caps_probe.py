"""Walk ranked boards and holder lists to find their real depth caps (read-only).
Output: data/derived/pagination_caps_<UTC>.json"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
res = {}


def walk(path, params, max_pages=30):
    n, pages, cur, last = 0, 0, None, None
    while pages < max_pages:
        p = dict(params)
        if cur:
            p = {"cursor": cur, **({"user": params["user"]} if "user" in params else {}),
                 **({"condition": params["condition"]} if "condition" in params else {})}
        try:
            j = request_json(f"{api.DATA}{path}", p, source="data-api")
        except Exception as ex:
            return {"rows": n, "pages": pages, "error": str(ex)[:200]}
        d = j.get("data") or []
        if path == "/v2/holders":
            n += sum(len(g.get("holders") or []) for g in d)
        else:
            n += len(d)
        last = d[-1] if d else last
        pages += 1
        pg = j.get("pagination") or {}
        cur = pg.get("next_cursor")
        if not cur:
            break
    return {"rows": n, "pages": pages, "exhausted": cur is None, "last_rank": (last or {}).get("rank") if isinstance(last, dict) else None}


for tp in ("day", "all"):
    res[f"leaderboard_pnl_{tp}"] = walk("/v2/leaderboard", {"time_period": tp, "limit": 1000})
res["leaderboard_volume_week"] = walk("/v2/leaderboard", {"time_period": "week", "sort_by": "VOLUME", "limit": 1000})
res["biggest_winners_week"] = walk("/v2/biggest-winners", {"time_period": "week", "limit": 1000})
om = list(api.gamma_keyset("markets", {"closed": "false", "limit": 3, "order": "volume24hr", "ascending": "false"}, max_pages=1))
res["holders_top_market"] = {"condition": om[0]["conditionId"], **walk("/v2/holders", {"condition": om[0]["conditionId"], "limit": 1000}, max_pages=10)}
res["positions_market_anchor"] = {"condition": om[0]["conditionId"], **walk("/v2/positions", {"condition": om[0]["conditionId"], "limit": 1000}, max_pages=10)}
out = ROOT / "data" / "derived" / f"pagination_caps_{STAMP}.json"
out.write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
