"""Stage 2, step 15: 'exit when the followed wallet sells' variant (A10), at the 2-minute detection delay.

Run from polymarket_research/:  python analyses/pit_wallets/15_exit_prices.py sells|prices
Phase 'sells': for every P signal, t_sell = the followed wallet's first SELL fill of the decision token at
  ts > t0 + 120 s (after the follower's earliest entry) and ts < t_res. One query per chunk of signals.
Phase 'prices' (needs 13_follower_prices output): the follower detects the sale at t_sell + 120 s and sells into
  taker SELL prints of the token by other wallets (orders_filled rows with taker = exchange and
  taker_asset_id = '0'; price = collateral / shares): fpx = first print within 60 min (pre-registered style), and
  for its share quantity q_X (entry size X / entry price of the same model) the VWAP over prints in
  [t_sell + 120, + 30 min) accumulated to q_X shares (0 = not reached: the follower then holds to resolution).
Outputs: data/derived/pit_wallets/exit_sells.parquet, exit_prices.parquet (chunks in exit_chunks/).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
import ch  # noqa: E402

OUT = ROOT / "data" / "derived" / "pit_wallets"
CDIR = OUT / "exit_chunks"
EXCH = "('0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e', '0xc5d563a36ae78145c45a50134d48a1215220f80a')"
DELAY = 120
SIZES = [100, 500, 2500, 10000]

SELL_SQL = """
SELECT groupArray(sid), groupArray(tsell), groupArray(nsell) FROM (
  SELECT s.sid AS sid, min(f.ts) AS tsell, toUInt32(count()) AS nsell
  FROM sg AS s INNER JOIN (
    SELECT maker AS w, toUInt64OrZero(right(maker_asset_id, 18)) AS k, toUInt32(timestamp) AS ts
    FROM polymarket.orders_filled
    WHERE is_deleted = 0 AND taker_asset_id = '0' AND timestamp >= {T0} AND timestamp < {T1}
      AND maker IN (SELECT w FROM sg)
  ) AS f ON s.w = f.w AND s.k = f.k
  WHERE f.ts > s.te AND f.ts < s.tr
  GROUP BY sid)
"""
SELL_STRUCT = "sid UInt32, k UInt64, w String, te UInt32, tr UInt32"

VW = ",\n".join(
    f"toUInt16(if(arrayFirstIndex(c -> c >= q{i}, cs) = 0, 0, least(10000, round(10000 * ("
    f"if(arrayFirstIndex(c -> c >= q{i}, cs) > 1, cu[arrayFirstIndex(c -> c >= q{i}, cs) - 1], 0) + (q{i} - "
    f"if(arrayFirstIndex(c -> c >= q{i}, cs) > 1, cs[arrayFirstIndex(c -> c >= q{i}, cs) - 1], 0)) * "
    f"w30[arrayFirstIndex(c -> c >= q{i}, cs)].2) / q{i}))))" for i in range(len(SIZES)))

PX_SQL = """
WITH
  s AS (SELECT sid, k, w, td, q0, q1, q2, q3, arrayJoin(range(intDiv(td, 3600), intDiv(td + 3600, 3600) + 1)) AS hb FROM sg),
  pr AS (
    SELECT toUInt64OrZero(right(maker_asset_id, 18)) AS k, toUInt32(timestamp) AS ts, intDiv(ts, 3600) AS hb, maker AS mw,
           toFloat64(taker_amount_filled) / 1e6 AS usd, toFloat64(maker_amount_filled) / 1e6 AS sh, usd / sh AS px
    FROM polymarket.orders_filled
    WHERE is_deleted = 0 AND taker_asset_id = '0' AND taker IN {exch} AND maker_amount_filled > 0
      AND timestamp >= {T0} AND timestamp < {T1} AND toUInt64OrZero(right(maker_asset_id, 18)) IN (SELECT k FROM sg)
  ),
  j AS (
    SELECT s.sid AS sid, any(s.td) AS td, any(s.q0) AS q0, any(s.q1) AS q1, any(s.q2) AS q2, any(s.q3) AS q3,
           arraySort(x -> x.1, groupArray((pr.ts, pr.px, pr.sh, pr.usd))) AS a
    FROM s INNER JOIN pr ON s.k = pr.k AND s.hb = pr.hb
    WHERE pr.ts >= s.td AND pr.ts < s.td + 3600 AND pr.mw != s.w
    GROUP BY sid
  )
SELECT groupArray(sid), arrayFlatten(groupArray(v)) FROM (
  SELECT sid, arrayFilter(x -> x.1 < td + 1800, a) AS w30,
         arrayCumSum(x -> x.3, w30) AS cs, arrayCumSum(x -> x.4, w30) AS cu,
         [toUInt16(least(10000, round(10000 * a[1].2))), {VW},
          toUInt16(least(65535, round(arraySum(x -> x.4, w30) / 10)))] AS v
  FROM j)
"""
PX_STRUCT = "sid UInt32, k UInt64, w String, td UInt32, q0 Float64, q1 Float64, q2 Float64, q3 Float64"


def sells():
    CDIR.mkdir(exist_ok=True)
    sm = pd.read_parquet(OUT / "sig_members.parquet", columns=["stype", "psid", "k", "wallet", "t_sig", "r"])
    p = sm[sm.stype == "P"].drop_duplicates("psid").sort_values("t_sig")
    print("P pricing rows", len(p))
    for j, idx in enumerate(np.array_split(np.arange(len(p)), int(np.ceil(len(p) / 60000)))):
        g = p.iloc[idx]
        f = CDIR / f"sells_{j:02d}.parquet"
        if f.exists():
            continue
        txt = "".join(f"{a}\t{b}\t{c}\t{d + DELAY}\t{e}\n" for a, b, c, d, e in zip(g.psid, g.k, g.wallet, g.t_sig, g.r))
        t = time.time()
        b = ch.q(SELL_SQL.format(T0=int(g.t_sig.min()), T1=int(g.r.max()) + 1), {"sg": (SELL_STRUCT, txt)})
        sid, ts, ns = b["data"][0]
        pd.DataFrame({"psid": np.array(sid, dtype=np.int64), "t_sell": np.array(ts, dtype=np.int64),
                      "n_sell": np.array(ns, dtype=np.int64)}).to_parquet(f, index=False)
        print(f"  sells_{j:02d}: n={len(g)} with_sell={len(sid)} {time.time() - t:.1f}s", flush=True)
    pd.concat([pd.read_parquet(x) for x in sorted(CDIR.glob("sells_*.parquet"))]).to_parquet(OUT / "exit_sells.parquet", index=False)


def prices():
    es = pd.read_parquet(OUT / "exit_sells.parquet")
    fp = pd.read_parquet(OUT / "follower_prices.parquet",
                         columns=["psid", "fpx_120"] + [f"v{x}_120" for x in SIZES])
    pm = pd.read_parquet(OUT / "sig_pricing.parquet")
    g = es.merge(fp, on="psid").merge(pm, on="psid")
    # share quantities for the pre-registered $100 first-print model (+1 tick) and each VWAP size
    q = pd.DataFrame({"q0": np.where(g.fpx_120 > 0, 100 / np.minimum(0.999, g.fpx_120 / 1e4 + 0.01), 0)})
    for i, x in enumerate(SIZES[1:], start=1):
        col = f"v{x}_120"
        q[f"q{i}"] = np.where(g[col] > 0, x / (g[col] / 1e4), 0)
    g = pd.concat([g.reset_index(drop=True), q], axis=1)
    g = g[(g.q0 > 0) | (g.q1 > 0)].sort_values("t_sell")
    g["td"] = g.t_sell + DELAY
    print("exit rows to price", len(g))
    for j, idx in enumerate(np.array_split(np.arange(len(g)), max(1, int(np.ceil(len(g) / 50000))))):
        c = g.iloc[idx]
        f = CDIR / f"px_{j:02d}.parquet"
        if f.exists():
            continue
        txt = "".join(f"{a}\t{b}\t{w}\t{d}\t{q0:.4f}\t{q1:.4f}\t{q2:.4f}\t{q3:.4f}\n"
                      for a, b, w, d, q0, q1, q2, q3 in zip(c.psid, c.k, c.wallet, c.td, c.q0, c.q1, c.q2, c.q3))
        t = time.time()
        b = ch.q(PX_SQL.format(exch=EXCH, T0=int(c.td.min()), T1=int(c.td.max()) + 3601, VW=VW),
                 {"sg": (PX_STRUCT, txt)})
        sid, vals = b["data"][0]
        v = np.array(vals, dtype=np.int64).reshape(len(sid), 6)
        df = pd.DataFrame({"psid": np.array(sid, dtype=np.int64), "xfpx": v[:, 0], "x100": v[:, 1], "x500": v[:, 2],
                           "x2500": v[:, 3], "x10000": v[:, 4], "xvol30": v[:, 5]})
        df.to_parquet(f, index=False)
        print(f"  px_{j:02d}: n={len(c)} with_prints={len(df)} {time.time() - t:.1f}s", flush=True)
    ex = pd.concat([pd.read_parquet(x) for x in sorted(CDIR.glob("px_*.parquet"))])
    es.merge(ex, on="psid", how="left").to_parquet(OUT / "exit_prices.parquet", index=False)


if __name__ == "__main__":
    {"sells": sells, "prices": prices}[sys.argv[1]]()
