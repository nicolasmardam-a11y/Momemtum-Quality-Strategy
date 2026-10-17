"""Pull full observable Data API v2 history for GRIMDRIP, endlessFate (and mintblade for comparison).

Run from polymarket_research/:  python analyses/wallets/ge_pull_wallets.py
Raw responses are stored by pmr.http (data/raw/data-api/...). Wallet history is
pulled with cache=True so the script is resumable; the provenance metadata
records the fetch time (2026-10-17). Live state (positions, value, pnl) is cache=False.
Outputs: data/derived/ge_<kind>.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

WALLETS = {
    "GRIMDRIP": "0x3f87d51f27ba6e19ec52aaeebb68559a839c742c",
    "endlessFate": "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2",
    "mintblade": "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb",
}
OUT = ROOT / "data" / "derived"
STATUSES = ["OPEN", "REDEEMABLE", "REDEEMABLE_LOST", "MERGEABLE", "CLOSED"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    acts, acts_dw, tr_all, tr_taker, pos, stats, pnl, val, prof = [], [], [], [], [], [], [], [], []
    for name, a in WALLETS.items():
        p = api.public_profile(a)
        prof.append({"label": name, **{k: v for k, v in p.items() if k != "users"},
                     "user_id": (p.get("users") or [{}])[0].get("id")})
        # activity: default set (exclude_deposits_withdrawals defaults to true) and explicit false
        for flag, sink in (("true", acts), ("false", acts_dw)):
            rows = api.activity(a, start=1, sort_direction="ASC", exclude_deposits_withdrawals=flag, cache=True)
            sink += [{"label": name, **r} for r in rows]
            print(name, "activity excl_dw", flag, len(rows))
        # opt-in TIP type (user<->user transfers) is never in the default set
        rows = api.activity(a, start=1, sort_direction="ASC", type="TIP", exclude_deposits_withdrawals="false", cache=True)
        print(name, "activity TIP", len(rows))
        acts_dw += [{"label": name, "_tip_query": True, **r} for r in rows]
        for to, sink in ((False, tr_all), (True, tr_taker)):
            rows = api.trades(user=a, taker_only=to, start=1, filter_amount=0, cache=True)
            sink += [{"label": name, **r} for r in rows]
            print(name, "trades taker_only", to, len(rows))
        for st in STATUSES:
            rows = api.positions(a, status=st, cache=False)
            pos += [{"label": name, "query_status": st, **r} for r in rows]
            print(name, "positions", st, len(rows))
        s = api.user_stats(a) or {}
        atp = s.pop("all_time_pnl", None) or {}
        stats.append({"label": name, **s, **{f"atp_{k}": v for k, v in atp.items()}})
        j = request_json(f"{api.DATA}/v2/user-pnl", {"user": a, "interval": "max", "fidelity": "1d"}, source="data-api")
        for pt in (j.get("data") or {}).get("points") or []:
            pnl.append({"label": name, **pt})
        v = request_json(f"{api.DATA}/v2/value", {"user": a}, source="data-api").get("data")
        val.append({"label": name, **(v[0] if isinstance(v, list) else (v or {}))})

    for nm, rows in [("activity", acts), ("activity_incl_dw", acts_dw), ("trades_all", tr_all),
                     ("trades_takeronly", tr_taker), ("positions", pos), ("user_stats", stats),
                     ("user_pnl", pnl), ("value", val), ("profiles", prof)]:
        df = pd.DataFrame(rows)
        for c in df.columns:
            if df[c].dtype == object and df[c].map(lambda x: isinstance(x, (dict, list))).any():
                df[c] = df[c].map(lambda x: None if x is None else str(x))
        df.to_parquet(OUT / f"ge_{nm}.parquet", index=False)
        print("wrote", nm, df.shape)


if __name__ == "__main__":
    main()
