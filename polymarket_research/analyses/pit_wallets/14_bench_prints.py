"""Stage 2, step 14: hash sample of on-chain taker BUY prints for benchmarks B2, (i) matched random entries and
(ii) the favourite rule.

Run from polymarket_research/:  python analyses/pit_wallets/14_bench_prints.py
Taker BUY print = orders_filled row with taker = exchange contract and maker_asset_id = '0'. Per calendar month the
sampling modulus M_m = max(1, round(n_m / TARGET)) keeps about TARGET prints a month (cityHash64(id) % M_m = 0), so
sparse 2024 months are not starved. Every print carries its month's inverse sampling rate M_m (used as a weight only
when pooling across months; within-week matching uses unweighted prints of one month).
Output: data/derived/pit_wallets/bench_prints.parquet (k, ts, px, usd, M), bench_month_counts.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
import ch  # noqa: E402

OUT = ROOT / "data" / "derived" / "pit_wallets"
EXCH = "('0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e', '0xc5d563a36ae78145c45a50134d48a1215220f80a')"
T0, T1 = 1704067200, 1767657600   # 2024-01-01 .. 2026-01-06
TARGET = 12000
PER_QUERY = 34000   # keeps each result under the 1,000,000-byte max_result_bytes

COUNT = f"""
SELECT toYYYYMM(timestamp) AS ym, count() AS n FROM polymarket.orders_filled
WHERE is_deleted = 0 AND maker_asset_id = '0' AND taker IN {EXCH} AND timestamp >= {T0} AND timestamp < {T1}
GROUP BY ym ORDER BY ym
"""

SQL = """
SELECT groupArray(k), groupArray(ts), groupArray(px), groupArray(usd), groupArray(ym) FROM (
  SELECT toUInt64OrZero(right(taker_asset_id, 18)) AS k, toUInt32(timestamp) AS ts,
         toUInt16(least(10000, round(10000 * toFloat64(maker_amount_filled) / toFloat64(taker_amount_filled)))) AS px,
         toFloat32(toFloat64(maker_amount_filled) / 1e6) AS usd, toUInt32(toYYYYMM(timestamp)) AS ym
  FROM polymarket.orders_filled
  WHERE is_deleted = 0 AND maker_asset_id = '0' AND taker IN {exch} AND taker_amount_filled > 0
    AND timestamp >= {a} AND timestamp < {b}
    AND cityHash64(id) % multiIf({mcase}, 1000000000) = 0)
"""


def main():
    cnt_p = OUT / "bench_month_counts.parquet"
    if cnt_p.exists():
        cnt = pd.read_parquet(cnt_p)
    else:
        cnt = pd.DataFrame(ch.rows(COUNT)).astype({"ym": int, "n": int})
        cnt["M"] = np.maximum(1, np.round(cnt.n / TARGET)).astype(int)
        cnt.to_parquet(cnt_p, index=False)
    # month start in epoch seconds (pandas 3 datetimes may be in us, so do not rely on astype(int64))
    cnt["start"] = [int(pd.Timestamp(f"{str(int(y))[:4]}-{str(int(y))[4:]}-01", tz="UTC").timestamp())
                    for y in cnt.ym]
    cnt["exp"] = cnt.n / cnt.M
    print(cnt.to_string())
    cdir = OUT / "bench_chunks"; cdir.mkdir(exist_ok=True)
    # group consecutive months so each query expects <= PER_QUERY prints
    groups, cur, tot = [], [], 0.0
    for _, r in cnt.iterrows():
        if cur and tot + r.exp > PER_QUERY:
            groups.append(cur); cur, tot = [], 0.0
        cur.append(r); tot += r.exp
    if cur:
        groups.append(cur)
    parts = []
    for g in groups:
        tag = f"bp_{int(g[0].ym)}_{int(g[-1].ym)}"
        p = cdir / f"{tag}.parquet"
        if not p.exists():
            a = int(g[0].start)
            b = int(g[-1].start) + 32 * 86400
            b = int(pd.Timestamp(b, unit="s", tz="UTC").replace(day=1, hour=0, minute=0, second=0).timestamp())
            b = min(b, T1)
            mcase = ", ".join(f"toYYYYMM(timestamp) = {int(r.ym)}, {int(r.M)}" for r in g)
            body = ch.q(SQL.format(exch=EXCH, a=a, b=b, mcase=mcase))
            k, ts, px, usd, ym = body["data"][0]
            df = pd.DataFrame({"k": np.array(k, dtype=np.uint64), "ts": np.array(ts, dtype=np.int64),
                               "px": np.array(px, dtype=np.int32) / 1e4, "usd": np.array(usd, dtype=float),
                               "ym": np.array(ym, dtype=np.int64)})
            df.to_parquet(p, index=False)
            print(tag, len(df), flush=True)
        parts.append(pd.read_parquet(p))
    bp = pd.concat(parts, ignore_index=True).merge(cnt[["ym", "M"]], on="ym")
    bp.to_parquet(OUT / "bench_prints.parquet", index=False)
    print("bench prints", len(bp))


if __name__ == "__main__":
    main()
