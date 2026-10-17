"""Pull the market trade tape for each market mintblade traded (read-only).

/v2/trades?condition=... returns newest first; start/end filters are ignored
(re-checked 2026-10-17), so we page backwards until the tape is older than
`first_entry - LOOKBACK`. Both taker_only=false (all fills, maker and taker rows)
and the default (taker rows only) are pulled so roles can be labelled by match.
Closed markets are immutable, so cache=True makes the pull resumable.
Usage: python analyses/wallets/mintblade_03_tapes.py [lookback_hours] [condition_id ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "data" / "derived"
DROP = ["icon", "bio", "profile_image", "profile_image_optimized", "slug", "event_slug", "title"]


def pull(cond: str, stop_ts: int, taker_only: bool | None) -> list[dict]:
    params = {"condition": cond, "limit": 1000}
    if taker_only is not None:
        params["taker_only"] = str(taker_only).lower()
    rows = []
    while True:
        j = request_json(f"{api.DATA}/v2/trades", params, source="data-api", cache=True)
        page = j.get("data") or []
        rows += page
        cur = (j.get("pagination") or {}).get("next_cursor")
        if not page or not cur or min(r["timestamp"] for r in page) < stop_ts:
            return rows
        params["cursor"] = cur


def main():
    lookback_h = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
    fills = pd.read_parquet(OUT / "mintblade_trades_all.parquet")
    first = fills.groupby("condition_id").timestamp.min()
    conds = sys.argv[2:] or list(first.index)
    for c in conds:
        stop = int(first[c] - lookback_h * 3600)
        for mode, tag in [(False, "all"), (None, "taker")]:
            rows = pull(c, stop, mode)
            df = pd.DataFrame(rows).drop(columns=DROP, errors="ignore")
            df.to_parquet(OUT / f"mintblade_tape_{c[:10]}_{tag}.parquet", index=False)
            print(c[:10], tag, len(df), pd.to_datetime(df.timestamp.min(), unit="s"), pd.to_datetime(df.timestamp.max(), unit="s"), flush=True)


if __name__ == "__main__":
    main()
