"""Probe the public read endpoints once each and record shape, page size and behaviour (read-only).

Every response is stored by pmr.http under data/raw/ with URL, params and UTC fetch time.
Output: data/derived/endpoint_probe_<UTC>.json (one entry per probe: url, params, status, a short
shape description and the observations printed here).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

DATA, CLOB, GAMMA = api.DATA, api.CLOB, api.GAMMA
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
OUT = ROOT / "data" / "derived" / f"endpoint_probe_{STAMP}.json"

# A resolved market (IR Iran vs New Zealand, 2026-06-15/16, moneyline "IR Iran") and a wallet used elsewhere.
RES_COND = "0xe70fd51f42e61fc309d8e57019a7b76c8dc7bd19b473"  # prefix; full id resolved below
WALLET = "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb"
results = []


def shape(x, depth=0):
    if isinstance(x, dict):
        return {k: shape(v, depth + 1) if depth < 1 else type(v).__name__ for k, v in list(x.items())[:40]}
    if isinstance(x, list):
        return [f"list[{len(x)}]", shape(x[0], depth + 1) if x else None]
    return type(x).__name__


def probe(name, url, params=None, method="GET", body=None, note=""):
    t = time.time()
    try:
        if method == "GET":
            j = request_json(url, params, source="probe")
        else:
            j = request_json(url, params, method=method, json_body=body, source="probe")
        status = 200
    except Exception as ex:  # 4xx are informative here
        j, status = {"error": str(ex)[:400]}, "error"
    rec = {"name": name, "url": url, "params": params, "body": body, "status": status, "t_utc": datetime.fromtimestamp(t, timezone.utc).isoformat(),
           "shape": shape(j), "note": note}
    results.append(rec)
    return j


def main():
    m = api.gamma_markets(slug="fifwc-irn-nzl-2026-06-15-irn", closed="true")[0]
    cond = m["conditionId"]
    tok = api.jlist(m["clobTokenIds"])
    print("resolved market", cond, tok[0][:12])
    # open, liquid market for book probes
    om = list(api.gamma_keyset("markets", {"closed": "false", "limit": 5, "order": "volume24hr", "ascending": "false"}, max_pages=1))
    otok = [t for x in om for t in api.jlist(x.get("clobTokenIds"))]
    ocond = om[0]["conditionId"]

    # ---------------- price history
    j = probe("v2_prices_history_interval_max", f"{DATA}/v2/prices-history", {"token_id": tok[0], "interval": "max"})
    d = j.get("data") or []
    print("v2 interval=max points", len(d), d[:1], d[-2:], j.get("pagination"))
    j = probe("v2_prices_history_interval_max_10800", f"{DATA}/v2/prices-history", {"token_id": tok[0], "interval": "max", "bucket_seconds": 10800})
    print("v2 interval=max 3h points", len(j.get("data") or []))
    j = probe("v2_prices_history_old_window", f"{DATA}/v2/prices-history", {"token_id": tok[0], "start": 1781560000, "end": 1781650000})
    print("v2 old explicit window ->", str(j)[:300])
    j = probe("v2_prices_history_as_of", f"{DATA}/v2/prices-history", {"token_id": tok[0], "as_of": 1781580000})
    print("v2 as_of ->", str(j)[:300])
    j = probe("v2_prices_history_open_1d", f"{DATA}/v2/prices-history", {"token_id": otok[0], "interval": "1d"})
    d = j.get("data") or []
    print("v2 open interval=1d points", len(d), d[:2], d[-1:])
    j = probe("clob_prices_history_max", f"{CLOB}/prices-history", {"market": tok[0], "interval": "max"})
    print("clob interval=max resolved points", len(j.get("history") or []))
    j = probe("clob_prices_history_window_f1", f"{CLOB}/prices-history", {"market": tok[0], "startTs": 1781560000, "endTs": 1781650000, "fidelity": 1})
    h = j.get("history") or []
    print("clob window fidelity=1 points", len(h), h[:2])
    j = probe("clob_prices_history_open_max", f"{CLOB}/prices-history", {"market": otok[0], "interval": "max", "fidelity": 60})
    print("clob open interval=max fidelity=60 points", len(j.get("history") or []))
    j = probe("clob_prices_history_open_1d", f"{CLOB}/prices-history", {"market": otok[0], "interval": "1d", "fidelity": 1})
    h = j.get("history") or []
    print("clob open 1d fidelity=1 points", len(h), h[:2], h[-1:])
    j = probe("clob_batch_prices_history", f"{CLOB}/batch-prices-history", method="POST",
              body={"markets": otok[:2], "interval": "1d", "fidelity": 5})
    print("batch keys", list((j.get("history") or {}).keys())[:3], {k: len(v) for k, v in (j.get("history") or {}).items()})
    j = probe("clob_batch_prices_history_21", f"{CLOB}/batch-prices-history", method="POST",
              body={"markets": (otok * 5)[:21], "interval": "1d", "fidelity": 60})
    print("batch 21 ->", str(j)[:200])

    # ---------------- books
    j = probe("clob_book", f"{CLOB}/book", {"token_id": otok[0]})
    print("book keys", list(j.keys()), "ts", j.get("timestamp"), "levels", len(j.get("bids") or []), len(j.get("asks") or []))
    j = probe("clob_books_get", f"{CLOB}/books", {"token_ids": ",".join(otok[:4])})
    print("books GET n", len(j) if isinstance(j, list) else j)
    j = probe("clob_books_post", f"{CLOB}/books", method="POST", body=[{"token_id": t} for t in otok[:4]])
    print("books POST n", len(j) if isinstance(j, list) else j)
    j = probe("clob_book_resolved", f"{CLOB}/book", {"token_id": tok[0]})
    print("book on resolved ->", str(j)[:200])
    j = probe("clob_last_trades_prices", f"{CLOB}/last-trades-prices", {"token_ids": ",".join(otok[:4])})
    print("last-trades-prices", str(j)[:300])

    # ---------------- Data API v2 misc
    j = probe("v2_holders", f"{DATA}/v2/holders", {"condition": ocond, "limit": 3})
    print("holders", str(j)[:600])
    j = probe("v2_holders_pnl", f"{DATA}/v2/holders", {"condition": ocond, "limit": 2, "include_pnl": "true"})
    print("holders pnl", str(j)[:500])
    j = probe("v2_leaderboard_day", f"{DATA}/v2/leaderboard", {"time_period": "day", "limit": 3})
    print("leaderboard", str(j)[:600])
    j = probe("v2_leaderboard_user", f"{DATA}/v2/leaderboard", {"user": WALLET, "time_period": "all"})
    print("leaderboard user", str(j)[:400])
    j = probe("v2_biggest_winners", f"{DATA}/v2/biggest-winners", {"time_period": "week", "limit": 2})
    print("biggest winners", str(j)[:500])
    j = probe("v2_user_pnl", f"{DATA}/v2/user-pnl", {"user": WALLET, "interval": "max", "fidelity": "1d"})
    dd = j.get("data") or {}
    print("user-pnl", {k: v for k, v in dd.items() if k != "points"}, "points", len(dd.get("points") or []), (dd.get("points") or [None])[-1])
    j = probe("v2_user_stats", f"{DATA}/v2/user-stats", {"user": WALLET})
    print("user-stats", str(j)[:500])
    j = probe("v2_user_volume", f"{DATA}/v2/user-volume", {"user": WALLET})
    print("user-volume", j)
    j = probe("v2_value", f"{DATA}/v2/value", {"user": WALLET})
    print("value", j)
    j = probe("v2_resolutions_cond", f"{DATA}/v2/resolutions", {"condition": cond})
    print("resolutions", str(j)[:900])
    j = probe("v2_tokens_cond", f"{DATA}/v2/tokens", {"condition": cond})
    print("tokens", str(j)[:900])
    j = probe("v2_oi", f"{DATA}/v2/oi", {"condition": ocond})
    print("oi", j)
    j = probe("v2_live_volume", f"{DATA}/v2/live-volume", {"event_id": om[0]["events"][0]["id"] if om[0].get("events") else ""})
    print("live-volume", str(j)[:300])
    j = probe("v2_trades_bare", f"{DATA}/v2/trades", {"limit": 3})
    print("bare trades feed", str(j)[:300])
    j = probe("v2_trades_cond_start_end", f"{DATA}/v2/trades", {"condition": cond, "limit": 3, "start": 1781500000, "end": 1781510000})
    print("cond trades with start/end (expect ignored)", [(r["timestamp"]) for r in j.get("data") or []])
    j = probe("v2_trades_user_start_end", f"{DATA}/v2/trades", {"user": WALLET, "limit": 3, "start": 1781500000, "end": 1781600000})
    print("user trades with start/end", [(r["timestamp"]) for r in j.get("data") or []])
    j = probe("v2_trades_limit_1001", f"{DATA}/v2/trades", {"condition": cond, "limit": 1001})
    print("limit 1001 ->", str(j)[:200])
    j = probe("v2_trades_offset", f"{DATA}/v2/trades", {"condition": cond, "limit": 2, "offset": 10})
    print("offset ->", str(j)[:200])

    # ---------------- rewards / rebates (public CLOB)
    j = probe("clob_rewards_current", f"{CLOB}/rewards/markets/current")
    print("rewards current: limit", j.get("limit"), "count", j.get("count"), "next", j.get("next_cursor"), "row0", str((j.get("data") or [None])[0])[:400])
    j = probe("clob_rewards_multi", f"{CLOB}/rewards/markets/multi", {"page_size": 2, "order_by": "volume_24hr", "position": "DESC"})
    print("rewards multi", str(j)[:700])
    j = probe("clob_rewards_market", f"{CLOB}/rewards/markets/{ocond}")
    print("rewards market", str(j)[:500])
    j = probe("clob_rebates_current", f"{CLOB}/rebates/current", {"date": "2026-10-16", "maker_address": WALLET})
    print("rebates current", str(j)[:300])

    # ---------------- Data API v1 (retires 2026-10-24): still answering today?
    r = requests.get(f"{DATA}/trades", params={"market": cond, "limit": 2}, timeout=30)
    results.append({"name": "v1_trades", "url": f"{DATA}/trades", "status": r.status_code,
                    "headers": {k: v for k, v in r.headers.items() if k.lower() in ("deprecation", "sunset", "link", "warning", "x-trace-id")},
                    "shape": shape(r.json()) if r.ok else r.text[:200]})
    print("v1 /trades", r.status_code, {k: v for k, v in r.headers.items() if k.lower() in ("deprecation", "sunset", "link", "warning")}, r.text[:200])

    OUT.write_text(json.dumps(results, indent=1, default=str))
    print("->", OUT)


if __name__ == "__main__":
    main()
