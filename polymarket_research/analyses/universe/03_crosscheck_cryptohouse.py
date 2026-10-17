"""Independent count cross-check: CryptoHouse polymarket.assets distinct markets by end month.

Run from polymarket_research/: python analyses/universe/03_crosscheck_cryptohouse.py
Writes data/derived/universe_crosscheck_cryptohouse.parquet
"""
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

SQL = """
SELECT toStartOfMonth(market_end_date) AS m,
       uniqExact(market_condition_id) AS n_all,
       uniqExactIf(market_condition_id, market_closed) AS n_closed,
       max(insert_time) AS max_insert
FROM polymarket.assets
WHERE market_end_date >= '2024-01-01' AND market_end_date < '2026-10-16'
GROUP BY m ORDER BY m
"""
rows = api.cryptohouse(SQL)
df = pd.DataFrame(rows)
print(df.to_string())
df.to_parquet(ROOT / "data" / "derived" / "universe_crosscheck_cryptohouse.parquet", index=False)
