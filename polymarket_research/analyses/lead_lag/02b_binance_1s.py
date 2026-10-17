"""Binance BTCUSDT/ETHUSDT 1-second klines (data-api.binance.vision, public) for the historical window, so spot can be
evaluated at the irregular timestamps of the Polymarket /prices-history points without look-ahead.
Run: python -m analyses.lead_lag.02b_binance_1s 7   -> data/derived/lead_lag/hist_binance_1s.parquet
"""
import sys
from datetime import datetime, timezone, timedelta
import pandas as pd
from pmr.http import request_json
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7
END = datetime(2026, 10, 17, 22, 0, tzinfo=timezone.utc)
START = END - timedelta(days=DAYS, hours=3)
out = []
for sym in ("BTCUSDT", "ETHUSDT"):
    s, e = int(START.timestamp() * 1000), int(END.timestamp() * 1000)
    while s < e:
        j = request_json("https://data-api.binance.vision/api/v3/klines", {"symbol": sym, "interval": "1s", "startTime": s, "limit": 1000},
                         source="binance", cache=True)
        if not j:
            break
        out += [(sym, int(k[0]) // 1000, float(k[1]), float(k[4])) for k in j]
        s = int(j[-1][0]) + 1000
    print(sym, len(out), flush=True)
pd.DataFrame(out, columns=["sym", "t", "o", "c"]).to_parquet("data/derived/lead_lag/hist_binance_1s.parquet")
