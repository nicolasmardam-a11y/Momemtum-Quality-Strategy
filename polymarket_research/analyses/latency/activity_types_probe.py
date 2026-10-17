"""Find example rows of each /v2/activity type (SPLIT, MERGE, CONVERSION, REDEEM, REWARD, rebates, TIP, deposits)
among top-volume leaderboard wallets, to document how non-trade actions appear (read-only).
Output: data/derived/activity_types_probe_<UTC>.json"""
import json, sys, collections
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
lb = request_json(f"{api.DATA}/v2/leaderboard", {"time_period": "week", "sort_by": "VOLUME", "limit": 25}, source="data-api")["data"]
wallets = [r["user_id"] for r in lb]
examples, counts = {}, collections.Counter()
for w in wallets:
    j = request_json(f"{api.DATA}/v2/activity", {"user": w, "limit": 1000, "exclude_deposits_withdrawals": "false"}, source="data-api")
    rows = j.get("data") or []
    c = collections.Counter(r.get("type") for r in rows)
    counts.update(c)
    for r in rows:
        t = r.get("type")
        if t not in examples:
            examples[t] = {k: v for k, v in r.items() if k not in ("bio", "profile_image", "profile_image_optimized", "icon")}
    for t in ("SPLIT", "MERGE", "CONVERSION", "TIP"):
        if t not in examples:
            jj = request_json(f"{api.DATA}/v2/activity", {"user": w, "limit": 3, "type": t}, source="data-api")
            for r in jj.get("data") or []:
                examples.setdefault(t, {k: v for k, v in r.items() if k not in ("bio", "profile_image", "profile_image_optimized", "icon")})
out = ROOT / "data" / "derived" / f"activity_types_probe_{STAMP}.json"
out.write_text(json.dumps({"wallets": wallets, "type_counts_last1000_rows": counts, "examples": examples}, indent=1, default=str))
print(dict(counts))
for t, e in examples.items():
    print(t, json.dumps(e)[:700])
print("->", out)
