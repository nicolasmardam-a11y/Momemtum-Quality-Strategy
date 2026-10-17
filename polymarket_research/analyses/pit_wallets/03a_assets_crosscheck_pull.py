"""Pull CryptoHouse polymarket.assets (45.5k outcome tokens) compactly, for cross-checking Gamma
resolution payouts and closed times. Run from polymarket_research/.
Writes data/derived/pit_wallets/ch_assets.parquet
"""
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
import ch  # noqa: E402

rows = []
for i in range(6):
    b = ch.q(f"""SELECT groupArray((toUInt256(outcome_token_id), toFloat32(outcome_price), toUInt32(market_closed_date),
        toUInt32(market_end_date), toUInt32OrZero(event_id), toUInt8(market_closed), toUInt32(insert_time)))
        FROM polymarket.assets WHERE toUInt8(substring(outcome_token_id, -2)) % 6 = {i}""")
    rows += b["data"][0][0]
df = pd.DataFrame(rows, columns=["token_id", "ch_outcome_price", "ch_closed_ts", "ch_end_ts", "ch_event_id", "ch_closed", "ch_insert_ts"])
df["token_id"] = df.token_id.astype(str)
for c in ["ch_closed_ts", "ch_end_ts", "ch_event_id", "ch_closed", "ch_insert_ts"]:
    df[c] = df[c].astype("int64")
df.to_parquet(ROOT / "data/derived/pit_wallets/ch_assets.parquet", index=False)
print(len(df), df.token_id.nunique())
