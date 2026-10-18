"""Extension: resolved BTC/ETH 5-minute up/down events (Chainlink TWAP-60s) over the last N days, same method as 02/04 primary.
prices-history (fidelity=1) gives <= ~5 points per market; NOT executable. Spot = Binance 1s (hist_binance_1s.parquet).
Run: python -m analyses.lead_lag.02c_hist_5m 3 -> data/derived/lead_lag/hist5m_markets.parquet, hist5m_pm.parquet, hist5m_summary.json
"""
import importlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pandas as pd

h = importlib.import_module("analyses.lead_lag.02_hist_collect")
a4 = importlib.import_module("analyses.lead_lag.04_hist_analyze")
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
END = h.END
START = END - timedelta(days=DAYS)
specs = []
for a in ("btc", "eth"):
    t = START
    while t < END:
        specs.append(dict(asset=a, kind="15m", slug=f"{a}-updown-5m-{int(t.timestamp())}", t0=t, t1=t + timedelta(minutes=5)))
        t += timedelta(minutes=5)
with ThreadPoolExecutor(4) as ex:
    evs = list(ex.map(h.fetch_event, specs))
mk = pd.DataFrame(evs)
mk.to_parquet("data/derived/lead_lag/hist5m_markets.parquet")
ok = mk[mk.err.isna() & mk.up_token.notna()]
with ThreadPoolExecutor(4) as ex:
    hs = list(ex.map(h.fetch_hist, ok.to_dict("records")))
pm = pd.DataFrame([r for x in hs for r in x])
pm.to_parquet("data/derived/lead_lag/hist5m_pm.parquet")
# kind '15m' is used only to select the TWAP variance branch in fair_at; relabel afterwards
sp = a4.spot_tables()
Q = a4.primary(mk[mk.err.isna() & mk.up_won.notna()], pm, sp)
Q["kind"] = "5m"
Q.to_parquet("data/derived/lead_lag/hist5m_panel.parquet")
res = a4.primary_tests(Q)
res["n_events"] = int(len(mk)); res["missing"] = int(mk.err.notna().sum()); res["median_volume"] = float(mk.volume.median())
json.dump(res, open("data/derived/lead_lag/hist5m_summary.json", "w"), indent=1, default=str)
print(json.dumps(res, indent=1, default=str)[:3000])
