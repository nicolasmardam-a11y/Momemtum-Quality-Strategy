"""Co-trader found in the tapes: LEEEROYJENKINS 0x99aea8f9a64d0142b6b66a4b9d02a2211d45386f (profile verified via
Gamma /public-profile). Pull its trades (taker_only=false and true), activity and positions for comparison.
Outputs: data/derived/ge_leeroy_trades.parquet, ge_leeroy_positions.parquet, ge_leeroy_activity.parquet"""
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
OUT = ROOT / "data" / "derived"
L = "0x99aea8f9a64d0142b6b66a4b9d02a2211d45386f"
t = pd.DataFrame(api.trades(user=L, taker_only=False, start=1, filter_amount=0, cache=True))
tk = pd.DataFrame(api.trades(user=L, taker_only=True, start=1, filter_amount=0, cache=True))
t["role"] = t.transaction_hash.isin(set(tk.transaction_hash)).map({True: "taker", False: "maker"})
t.to_parquet(OUT / "ge_leeroy_trades.parquet", index=False)
pos = []
for st in ["OPEN", "CLOSED"]:
    pos += [{"query_status": st, **r} for r in api.positions(L, status=st)]
pos = pd.DataFrame(pos); pos.to_parquet(OUT / "ge_leeroy_positions.parquet", index=False)
act = pd.DataFrame(api.activity(L, start=1, sort_direction="ASC", exclude_deposits_withdrawals="false", cache=True))
act.to_parquet(OUT / "ge_leeroy_activity.parquet", index=False)
t["usd"] = t["size"] * t.price
g = t.groupby(["event_slug", "title", "outcome", "side"]).agg(n=("size", "size"), usd=("usd", "sum"), sh=("size", "sum"),
                                                              t0=("timestamp", "min"), t1=("timestamp", "max"))
g["vwap"] = g.usd / g.sh; g["t0"] = pd.to_datetime(g.t0, unit="s"); g["t1"] = pd.to_datetime(g.t1, unit="s")
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
print(g.to_string())
print(pos[["query_status", "status", "title", "outcome", "avg_price", "total_size", "current_size", "realized_pnl", "unrealized_pnl"]].to_string())
print(act.groupby("type").usdc_size.agg(["size", "sum"]))
