"""Historical inputs for the crypto lead-lag test (read-only, cached where immutable).

For the last N days, builds the slugs of resolved BTC/ETH 15-minute (Chainlink TWAP) and hourly
(Binance 1h candle) Up-or-Down events. For each it pulls the Gamma event (priceToBeat, outcome, tokens)
and the CLOB /prices-history of the Up token at fidelity=1. That series is a trade/mid series and is NOT
executable. It also pulls Binance 1m klines (data-api.binance.vision) and Coinbase 1m candles.

Run from polymarket_research/:  python -m analyses.lead_lag.02_hist_collect 7
Outputs: data/derived/lead_lag/hist_markets.parquet, hist_pm_1m.parquet, hist_binance_1m.parquet, hist_coinbase_1m.parquet
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

import pandas as pd

from pmr import api
from pmr.http import request_json

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 7
OUT = "data/derived/lead_lag/"
END = datetime(2026, 10, 17, 22, 0, tzinfo=timezone.utc)   # last window must have ended before collection
START = END - timedelta(days=DAYS)
ET = timedelta(hours=-4)   # EDT in October 2026
MON = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


def hourly_slug(asset, t0):
    e = t0 + ET
    h = e.hour % 12 or 12
    ap = "am" if e.hour < 12 else "pm"
    return f"{asset}-up-or-down-{MON[e.month - 1]}-{e.day}-{e.year}-{h}{ap}-et"


def build():
    specs = []
    for a, long in (("btc", "bitcoin"), ("eth", "ethereum")):
        t = START
        while t < END:
            if t.minute % 15 == 0:
                specs.append(dict(asset=a, kind="15m", slug=f"{a}-updown-15m-{int(t.timestamp())}", t0=t, t1=t + timedelta(minutes=15)))
            if t.minute == 0:
                specs.append(dict(asset=a, kind="1h", slug=hourly_slug(long, t), t0=t, t1=t + timedelta(hours=1)))
            t += timedelta(minutes=15)
    return specs


def fetch_event(sp):
    try:
        ev = api.gamma_events(slug=sp["slug"], cache=True)
    except Exception as ex:  # noqa: BLE001
        return {**sp, "err": repr(ex)[:100]}
    if not ev:
        return {**sp, "err": "missing"}
    e = ev[0]
    m = (e.get("markets") or [{}])[0]
    outs, prices, toks = api.jlist(m.get("outcomes")), api.jlist(m.get("outcomePrices")), api.jlist(m.get("clobTokenIds"))
    up = outs.index("Up") if "Up" in outs else 0
    return {**sp, "closed": m.get("closed"), "price_to_beat": (e.get("eventMetadata") or {}).get("priceToBeat"),
            "up_won": float(prices[up]) if prices else None, "up_token": toks[up] if toks else None,
            "down_token": toks[1 - up] if len(toks) > 1 else None, "fee_rate": (m.get("feeSchedule") or {}).get("rate"),
            "volume": float(m.get("volumeNum") or m.get("volume") or 0), "condition": m.get("conditionId"),
            "created": m.get("createdAt"), "err": None}


def fetch_hist(row):
    t0, t1 = row["t0"], row["t1"]
    lead = timedelta(minutes=30) if row["kind"] == "15m" else timedelta(hours=2)
    try:
        h = api.prices_history(row["up_token"], int((t0 - lead).timestamp()), int(t1.timestamp()) + 60, 1, cache=True)
    except Exception:  # noqa: BLE001
        return []
    return [{"slug": row["slug"], "t": int(x["t"]), "p": float(x["p"])} for x in h]


def binance(sym):
    rows, s = [], int((START - timedelta(hours=3)).timestamp() * 1000)
    e = int((END + timedelta(hours=1)).timestamp() * 1000)
    while s < e:
        j = request_json("https://data-api.binance.vision/api/v3/klines",
                         {"symbol": sym, "interval": "1m", "startTime": s, "limit": 1000}, source="binance", cache=True)
        if not j:
            break
        rows += [{"sym": sym, "t": int(k[0]) // 1000, "o": float(k[1]), "h": float(k[2]), "l": float(k[3]), "c": float(k[4]), "v": float(k[5])} for k in j]
        s = int(j[-1][0]) + 60_000
    return rows


def coinbase(pid):
    rows = []
    s = START - timedelta(hours=3)
    while s < END + timedelta(hours=1):
        e = s + timedelta(minutes=300)
        j = request_json(f"https://api.exchange.coinbase.com/products/{pid}/candles",
                         {"granularity": 60, "start": s.isoformat(), "end": e.isoformat()}, source="coinbase", cache=True)
        rows += [{"sym": pid, "t": int(k[0]), "l": float(k[1]), "h": float(k[2]), "o": float(k[3]), "c": float(k[4]), "v": float(k[5])} for k in j]
        s = e
    return rows


if __name__ == "__main__":
    specs = build()
    with ThreadPoolExecutor(4) as ex:
        evs = list(ex.map(fetch_event, specs))
    mk = pd.DataFrame(evs)
    print("events", len(mk), "missing", (mk.err.notna()).sum(), mk.groupby(["asset", "kind"]).size().to_dict())
    mk.to_parquet(OUT + "hist_markets.parquet")
    ok = mk[mk.err.isna() & mk.up_token.notna()]
    with ThreadPoolExecutor(4) as ex:
        hs = list(ex.map(fetch_hist, ok.to_dict("records")))
    pm = pd.DataFrame([r for h in hs for r in h])
    pm.to_parquet(OUT + "hist_pm_1m.parquet")
    print("pm rows", len(pm), "markets with history", pm.slug.nunique() if len(pm) else 0)
    bn = pd.DataFrame(binance("BTCUSDT") + binance("ETHUSDT"))
    bn.to_parquet(OUT + "hist_binance_1m.parquet")
    cb = pd.DataFrame(coinbase("BTC-USD") + coinbase("ETH-USD")).drop_duplicates(["sym", "t"]).sort_values(["sym", "t"])
    cb.to_parquet(OUT + "hist_coinbase_1m.parquet")
    print("binance", len(bn), "coinbase", len(cb))
