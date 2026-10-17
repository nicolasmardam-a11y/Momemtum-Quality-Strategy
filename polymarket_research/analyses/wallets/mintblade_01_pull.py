"""Pull the full observable Data API v2 history for mintblade (read-only).

Run from polymarket_research/:  python analyses/wallets/mintblade_01_pull.py
Raw responses land in data/raw/data-api/ (provenance by pmr.http). Live endpoints
(positions, value, pnl, stats) use cache=False; immutable history uses cache=True.
Outputs: data/derived/mintblade_*.parquet and a JSON dump of the small endpoints.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

ADDR = "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb"
OUT = Path(__file__).resolve().parents[2] / "data" / "derived"
OUT.mkdir(parents=True, exist_ok=True)


def save(rows, name):
    df = pd.json_normalize(rows) if rows else pd.DataFrame()
    for c in df.columns:
        if df[c].map(lambda v: isinstance(v, (list, dict))).any():
            df[c] = df[c].map(lambda v: json.dumps(v) if isinstance(v, (list, dict)) else v)
    df.to_parquet(OUT / f"mintblade_{name}.parquet", index=False)
    print(name, len(df))
    return df


def main():
    small = {}
    small["profile"] = api.public_profile(ADDR)
    small["user_stats"] = api.user_stats(ADDR)
    for path in ["/v2/user-pnl", "/v2/value", "/v2/user-volume"]:
        try:
            small[path] = request_json(f"{api.DATA}{path}", {"user": ADDR}, source="data-api")
        except Exception as e:  # record the failure, do not hide it
            small[path] = {"error": str(e)}

    # Full hourly P&L series (source fidelity is daily snapshots)
    pnl = request_json(f"{api.DATA}/v2/user-pnl", {"user": ADDR, "interval": "all"}, source="data-api")
    save(pnl["data"]["points"], "user_pnl_all")

    # Activity: default, and with exclude_deposits_withdrawals both ways
    act = api.activity(ADDR, cache=False)
    save(act, "activity")
    for flag in ["true", "false"]:
        try:
            a2 = api.activity(ADDR, cache=False, exclude_deposits_withdrawals=flag)
            small[f"activity_exclude_dw_{flag}_n"] = len(a2)
            small[f"activity_exclude_dw_{flag}_types"] = pd.Series([r.get("type") for r in a2]).value_counts().to_dict()
            save(a2, f"activity_exdw_{flag}")
        except Exception as e:
            small[f"activity_exclude_dw_{flag}_n"] = f"error {e}"

    # Trades: taker_only=false (all fills) and default (taker-only)
    t_all = api.trades(user=ADDR, taker_only=False, cache=False)
    save(t_all, "trades_all")
    t_def = api.trades(user=ADDR, cache=False)
    save(t_def, "trades_default")
    t_tt = api.trades(user=ADDR, taker_only=True, cache=False)
    save(t_tt, "trades_takeronly_true")

    # Positions for every status (and no status)
    pos = []
    for st in [None, "OPEN", "REDEEMABLE", "REDEEMABLE_LOST", "MERGEABLE", "CLOSED"]:
        try:
            rows = api.positions(ADDR, status=st, cache=False)
        except Exception as e:
            small[f"positions_{st}"] = f"error {e}"
            continue
        for r in rows:
            r["_status_query"] = st or "NONE"
        small[f"positions_{st}_n"] = len(rows)
        pos += rows
    save(pos, "positions")

    with open(OUT / "mintblade_small_endpoints.json", "w") as f:
        json.dump(small, f, indent=1, default=str)
    print(json.dumps({k: v for k, v in small.items() if not isinstance(v, dict)}, indent=1, default=str))


if __name__ == "__main__":
    main()
