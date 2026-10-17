"""M1: distinct outcome tokens traded on the pre-V2 exchanges (CryptoHouse orders_filled), with
fill count, collateral volume (wallet-fill legs, i.e. both sides of a match), first/last fill time.

Run from polymarket_research/: python analyses/pit_wallets/02_traded_assets.py
Partitioned by the last two digits of the decimal token id (48 partitions) so every result stays
under the 1 MB result cap; each partition is cached (resumable).
Writes data/derived/pit_wallets/traded_assets.parquet
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
import ch  # noqa: E402

NP = 48
SQL = """
SELECT groupArray((toUInt256(tok), n, vol, t0, t1)) a FROM (
  SELECT if(maker_asset_id = '0', taker_asset_id, maker_asset_id) tok,
         toUInt32(count()) n,
         toFloat32(sum(toFloat64(if(maker_asset_id = '0', maker_amount_filled, taker_amount_filled))) / 1e6) vol,
         toUInt32(min(timestamp)) t0, toUInt32(max(timestamp)) t1
  FROM polymarket.orders_filled
  WHERE is_deleted = 0 AND toUInt8(substring(if(maker_asset_id = '0', taker_asset_id, maker_asset_id), -2)) % {np} = {i}
  GROUP BY tok)
"""


def main():
    out = []
    for i in range(NP):
        t = time.time()
        b = ch.q(SQL.format(np=NP, i=i))
        arr = b["data"][0][0]
        out += arr
        print(i, len(arr), round(time.time() - t, 1), b.get("statistics", {}).get("elapsed"), flush=True)
    df = pd.DataFrame(out, columns=["token_id", "n_fills", "vol_legs", "t_first", "t_last"])
    df["n_fills"] = df.n_fills.astype("int64"); df["vol_legs"] = df.vol_legs.astype(float)
    df["t_first"] = pd.to_datetime(df.t_first.astype("int64"), unit="s", utc=True)
    df["t_last"] = pd.to_datetime(df.t_last.astype("int64"), unit="s", utc=True)
    df.to_parquet(ROOT / "data/derived/pit_wallets/traded_assets.parquet", index=False)
    print(len(df), df.vol_legs.sum())


if __name__ == "__main__":
    main()
