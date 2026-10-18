"""Stage 3 (2026 holdout), step 0: slim market table for 2025-05 .. 2026-10 from the shared Gamma universe.

Run from polymarket_research/:  python analyses/pit_wallets/v2_00_markets.py
Source: data/derived/markets_resolved.parquet (every Gamma market with closed=true and endDate in
[2024-01-01, 2026-10-16), fetched 2026-10-17, see notes/*/universe.md). No new API calls.
Output: data/derived/pit_wallets/v2/markets_2026.parquet, one row per market with
  condition_id (trade rows carry condition_id + outcome_index, so token ids are not stored), event keys (underlying-event key per pre-registration addendum A6), category4,
  t_res (closedTime, else umaEndDate), clean flag, payout per token, current fee schedule fields.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "derived" / "markets_resolved.parquet"
OUT = ROOT / "data" / "derived" / "pit_wallets" / "v2"
OUT.mkdir(parents=True, exist_ok=True)

COLS = ["condition_id", "question", "slug", "event_id", "event_slug", "category", "closedTime", "umaEndDate",
        "endDate", "startDate", "createdAt", "gameStartTime", "resolution", "winner_idx", "token_id_0", "token_id_1",
        "n_outcomes", "feesEnabled", "feeType", "fee_rate", "fee_exponent", "fee_taker_only", "volumeNum",
        "negRisk", "sportsMarketType", "umaResolutionStatus", "has_disputed", "secondsDelay", "orderPriceMinTickSize"]

CAT4 = {"sports": "sports", "crypto": "crypto", "politics": "politics", "geopolitics": "politics"}
GAME = re.compile(r"^(.*?-\d{4}-\d{2}-\d{2})")


def main() -> None:
    t = pq.read_table(SRC, columns=COLS)
    ct = t["closedTime"]
    keep = pc.or_kleene(pc.greater_equal(ct, pd.Timestamp("2025-04-01", tz="UTC")), pc.is_null(ct))
    df = t.filter(keep).to_pandas()
    df["t_res"] = df["closedTime"].fillna(df["umaEndDate"])
    df = df[df["t_res"].notna() & (df["t_res"] >= pd.Timestamp("2025-04-01", tz="UTC"))].copy()
    df["category4"] = df["category"].map(CAT4).fillna("other")
    # underlying event key (addendum A6): sports games split across several Gamma events share the slug prefix
    pref = df["event_slug"].fillna("").str.extract(GAME)[0]
    df["ue"] = np.where((df["category4"] == "sports") & pref.notna(), "g:" + pref.fillna(""), "e:" + df["event_id"].astype(str))
    df["clean"] = (df["resolution"] == "winner") & (df["n_outcomes"] == 2) & df["winner_idx"].isin([0, 1])
    df["pay0"] = np.where(df["clean"], (df["winner_idx"] == 0).astype(float), np.nan)
    df["pay1"] = np.where(df["clean"], (df["winner_idx"] == 1).astype(float), np.nan)
    df["fee_rate_now"] = np.where(df["feesEnabled"].fillna(False), df["fee_rate"].fillna(0.0), 0.0)
    slim = ["condition_id", "event_id", "event_slug", "ue", "category", "category4", "t_res", "endDate", "gameStartTime",
            "clean", "pay0", "pay1", "fee_rate_now", "fee_exponent", "feeType", "volumeNum", "negRisk",
            "sportsMarketType", "secondsDelay"]
    df = df[slim]
    df.to_parquet(OUT / "markets_2026.parquet", index=False, compression="zstd")
    print(f"markets {len(df):,}  clean {df['clean'].mean():.3f}  t_res range {df['t_res'].min()} .. {df['t_res'].max()}")
    w = df[(df["t_res"] >= "2026-01-15") & (df["t_res"] < "2026-06-01")]
    print("frame Jan15-May31 by category4:", w["category4"].value_counts().to_dict())
    print("fee_rate_now>0 share in frame:", round(float((w["fee_rate_now"] > 0).mean()), 3))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
