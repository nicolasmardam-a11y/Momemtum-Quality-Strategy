"""Base rate for the cluster signal: new wallets per month (first-ever fill on the pre-V2 exchanges) and how many
of them start with a BUY. Run from polymarket_research/:  python analyses/pit_wallets/07_wallet_births.py

The cluster detection itself runs inside 04_screens.py (fresh first decisions, D = 0 group) and
08_cluster_signals.py: a first attempt to detect clusters in a stand-alone per-month query (join of all fills
with per-wallet first fills) exceeded the 60 s CryptoHouse limit (2026-10-17) and was dropped.
Writes data/derived/pit_wallets/wallet_births.parquet
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
import ch  # noqa: E402

BIRTHS = """SELECT toString(toStartOfMonth(t0)) AS mo, count() AS n_new, countIf(b) AS n_new_first_buy FROM (
  SELECT maker, min(timestamp) AS t0, argMin(maker_asset_id = '0', timestamp) AS b FROM polymarket.orders_filled
  WHERE is_deleted = 0 GROUP BY maker) GROUP BY mo ORDER BY mo"""

if __name__ == "__main__":
    df = pd.DataFrame(ch.rows(BIRTHS))
    df["mo"] = pd.to_datetime(df.mo, utc=True)
    for c in ["n_new", "n_new_first_buy"]:
        df[c] = df[c].astype("int64")
    df.to_parquet(ROOT / "data/derived/pit_wallets/wallet_births.parquet", index=False)
    print(df.to_string())
