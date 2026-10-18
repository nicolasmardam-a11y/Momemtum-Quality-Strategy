"""Stage 2, step 13: follower execution proxy from subsequent on-chain TAKER BUY prints (server side).

Run from polymarket_research/:  python analyses/pit_wallets/13_follower_prices.py [max_queries]
For each pricing row (token k, signal time t, followed wallet w) of sig_pricing.parquet and each detection delay
d in DELAYS (5 s, 30 s, 2 min, 10 min, 15 min, 60 min, hourly poll = next full UTC hour after t), using only taker
BUY prints of token k by wallets other than w (orders_filled rows with taker = exchange contract and
maker_asset_id = '0'; price = collateral / shares of the row):
  fpx   price of the first print at >= t + d within 60 min (pre-registered model; 0 = none)
  fgap  seconds from t + d to that print (65535 = none)
  v<X>  VWAP of prints in [t + d, t + d + 30 min) accumulated to $X, X in SIZES (0 = not reached = unfilled)
  vol30 / vol60  taker-buy $ in [t + d, +30 min) / [t + d, +60 min), in $10 units (capped at 65535)
Prices are x 1e4 as UInt16. Taker prints show prices that traded, not the book: this is a proxy.
Resumable: one parquet per chunk in data/derived/pit_wallets/follower_chunks/.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
import ch  # noqa: E402

OUT = ROOT / "data" / "derived" / "pit_wallets"
CDIR = OUT / "follower_chunks"
EXCH = "('0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e', '0xc5d563a36ae78145c45a50134d48a1215220f80a')"
DELAYS = ["5", "30", "120", "600", "900", "3600", "poll"]
SIZES = [100, 500, 2500, 10000]
FIELDS = ["fpx", "fgap"] + [f"v{x}" for x in SIZES] + ["vol30", "vol60"]
NV = len(FIELDS)
CHUNK = 7000
HORIZON = 7205   # 60 min max delay + 60 min first-print window

VW = ",\n".join(
    f"toUInt16(if(arrayFirstIndex(c -> c >= {x}, cu) = 0, 0, least(10000, round(10000 * {x} / ("
    f"if(arrayFirstIndex(c -> c >= {x}, cu) > 1, cs[arrayFirstIndex(c -> c >= {x}, cu) - 1], 0) + ({x} - "
    f"if(arrayFirstIndex(c -> c >= {x}, cu) > 1, cu[arrayFirstIndex(c -> c >= {x}, cu) - 1], 0)) / "
    f"w[arrayFirstIndex(c -> c >= {x}, cu)].2)))))" for x in SIZES)

SQL = """
WITH
  s AS (SELECT sid, k, t, w, arrayJoin(range(intDiv(t, 3600), intDiv(t + {H}, 3600) + 1)) AS hb FROM sg),
  pr AS (
    SELECT toUInt64OrZero(right(taker_asset_id, 18)) AS k, toUInt32(timestamp) AS ts, intDiv(ts, 3600) AS hb,
           maker AS mw, toFloat64(maker_amount_filled) / 1e6 AS usd,
           toFloat64(maker_amount_filled) / toFloat64(taker_amount_filled) AS px
    FROM polymarket.orders_filled
    WHERE is_deleted = 0 AND maker_asset_id = '0' AND taker IN {exch} AND timestamp >= {T0} AND timestamp < {T1}
      AND taker_amount_filled > 0 AND toUInt64OrZero(right(taker_asset_id, 18)) IN (SELECT k FROM sg)
  ),
  j AS (
    SELECT s.sid AS sid, any(s.t) AS t, arraySort(x -> x.1, groupArray((pr.ts, pr.px, pr.usd))) AS a
    FROM s INNER JOIN pr ON s.k = pr.k AND s.hb = pr.hb
    WHERE pr.ts >= s.t + 5 AND pr.ts < s.t + {H} AND pr.mw != s.w
    GROUP BY sid
  )
SELECT groupArray(sid) AS sids, arrayFlatten(groupArray(v)) AS vals FROM (
  SELECT sid,
    arrayMap(d -> t + d, [5, 30, 120, 600, 900, 3600, toUInt32((intDiv(t, 3600) + 1) * 3600 - t)]) AS sts,
    arrayMap(st -> arrayFilter(x -> x.1 >= st AND x.1 < st + 1800, a), sts) AS W,
    arrayMap(w -> arrayCumSum(x -> x.3, w), W) AS CU,
    arrayMap(w -> arrayCumSum(x -> x.3 / x.2, w), W) AS CS,
    arrayFlatten(arrayMap((st, w, cu, cs) -> [
        toUInt16(least(10000, round(10000 * arrayFirst(x -> x.1 >= st AND x.1 < st + 3600, a).2))),
        toUInt16(if(arrayFirstIndex(x -> x.1 >= st AND x.1 < st + 3600, a) = 0, 65535,
                    toInt64(arrayFirst(x -> x.1 >= st AND x.1 < st + 3600, a).1) - toInt64(st))),
        {VW},
        toUInt16(least(65535, round(arraySum(x -> x.3, w) / 10))),
        toUInt16(least(65535, round(arraySum(x -> if(x.1 >= st AND x.1 < st + 3600, x.3, 0), a) / 10)))
      ], sts, W, CU, CS)) AS v
  FROM j)
"""
STRUCT = "sid UInt32, k UInt64, t UInt32, w String"


def price_chunk(tag: str, g: pd.DataFrame, depth: int = 0) -> int:
    p = CDIR / f"{tag}.parquet"
    if p.exists():
        return 0
    T0, T1 = int(g.t_sig.min()), int(g.t_sig.max()) + HORIZON + 1
    txt = "".join(f"{a}\t{b}\t{c}\t{d}\n" for a, b, c, d in zip(g.psid, g.k, g.t_sig, g.wallet))
    t = time.time()
    try:
        b = ch.q(SQL.format(H=HORIZON, exch=EXCH, T0=T0, T1=T1, VW=VW), {"sg": (STRUCT, txt)})
    except ch.CHError as e:
        msg = str(e)
        if ("Limit for result" in msg or "TOO_MANY" in msg or "TIMEOUT" in msg or "Timeout" in msg
                or "MEMORY" in msg) and len(g) > 200 and depth < 6:
            h = len(g) // 2
            print(f"  {tag}: {msg[:80]} -> split", flush=True)
            return price_chunk(tag + "a", g.iloc[:h], depth + 1) + price_chunk(tag + "b", g.iloc[h:], depth + 1)
        raise
    sids, vals = b["data"][0]
    sids = np.array(sids, dtype=np.int64)
    v = np.array(vals, dtype=np.int64).reshape(len(sids), len(DELAYS), NV) if len(sids) else np.zeros((0, 7, NV))
    df = pd.DataFrame({"psid": sids})
    for i, dname in enumerate(DELAYS):
        for j, f in enumerate(FIELDS):
            df[f"{f}_{dname}"] = v[:, i, j].astype("int32")
    df.to_parquet(p, index=False)
    st = b.get("statistics", {})
    print(f"  {tag}: n={len(g)} with_prints={len(df)} {time.time() - t:.1f}s server={st.get('elapsed', 0):.1f}s "
          f"rows_read={st.get('rows_read', 0)/1e6:.0f}M", flush=True)
    return 1


def main(max_q: int):
    CDIR.mkdir(exist_ok=True)
    pr = pd.read_parquet(OUT / "sig_pricing.parquet")
    pr["ym"] = pd.to_datetime(pr.t_sig, unit="s", utc=True).dt.strftime("%Y%m")
    done = 0
    for ym, g in pr.groupby("ym"):
        g = g.sort_values("t_sig")
        nch = int(np.ceil(len(g) / CHUNK))
        for j, idx in enumerate(np.array_split(np.arange(len(g)), nch)):
            if done >= max_q:
                return
            done += price_chunk(f"fp_{ym}_{j:02d}", g.iloc[idx])
    print("all chunks done", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10 ** 9)
