"""Fetch the public taker trade tape (Data API /v2/trades, taker_only default) for the three
contracts in Vojtko & Dujava (2026) and measure the effective half-spread of taker trades
relative to the prevailing 10-minute /prices-history value. Wallet fields are dropped."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

D = ROOT / "data" / "derived" / "literature_checks"
meta = pd.read_csv(D / "qp_mr_meta.csv")
for _, m in meta.iterrows():
    rows = api.trades(condition=m["condition_id"], cache=True)
    df = pd.DataFrame(rows)[["side", "token_id", "outcome", "size", "price", "timestamp", "transaction_hash"]]
    df.to_parquet(D / f"qp_mr_{m['name'].lower()}_trades.parquet", index=False)
    print(m["name"], len(df), pd.to_datetime(df.timestamp.min(), unit="s"), pd.to_datetime(df.timestamp.max(), unit="s"))
