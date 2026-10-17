"""Step 4-5: point-in-time decisions and screens, computed server-side on CryptoHouse per wallet bucket.

Run from polymarket_research/:  python analyses/pit_wallets/04_screens.py [K] [first_bucket] [last_bucket]
Needs data/derived/pit_wallets/meta_ext.tsv (from 03b_build_meta.py), uploaded as external table `m`
(k = last 18 decimal digits of the token id as UInt64, c = condition index, e = event index,
p = clean payout 1/0 or -1, r = resolution-known unix time or 0, cat = 0 sports 1 politics 2 crypto 3 other).

One query per bucket (cityHash64(maker) % K = b). Each returns, per selection date D, the base-rate
counts and a packed array of every wallet passing any screen (S1, S1m, S2, S3, S4[cat]) or in the
bucket-local top 2% (+3) of trailing P&L among wallets with >= 5 resolved decisions (S5 candidates; the
global top-1% cut is applied after all buckets are collected), or in the fixed 1% random sample of eligible
wallets (>= 5 resolved decisions; sipHash64(address) % 100 = 0) used for benchmark B1 (flag 512).
Results are cached per bucket (resumable).
Writes per-bucket parquet files under data/derived/pit_wallets/screen_buckets/ (merged by 05_merge_screens.py).
The same pipeline also emits (as the D = 0 group) every fresh wallet's first decision (wallet's first-ever
fill is a BUY that starts the decision, episode >= $100) with its 6 h episode BUY fills (ts, shares, usd), for the
cluster signal (08_cluster_signals.py); wallets are identified there by cityHash64(address).
first_fill = the wallet's first fill (any token, fills before CUTOFF only).
n_win and med_usd (features, not screens) use only decisions whose 6 h entry episode ended before D, so no fill
at or after D enters any feature; resolved decisions (r < D) are complete before D by construction.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
import ch  # noqa: E402

OUT = ROOT / "data" / "derived" / "pit_wallets"
EXCH = ("0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e", "0xc5d563a36ae78145c45a50134d48a1215220f80a")
META_STRUCT = "k UInt64, c UInt32, e UInt32, p Int8, r UInt32, cat UInt8"


def sel_dates() -> list[tuple[int, int]]:
    out = []
    for y in (2024, 2025):
        for mth in range(1, 13):
            d = datetime(y, mth, 1, tzinfo=timezone.utc)
            d12 = datetime(y - 1, mth, 1, tzinfo=timezone.utc)
            out.append((int(d.timestamp()), int(d12.timestamp())))
    return out


DATES = sel_dates()
CUTOFF = "2026-01-01 00:00:00"   # fills after the last selection date only feed the fresh-wallet (cluster) rows (D = 0)

SQL = """
WITH
  CAST({dates}, 'Array(Tuple(UInt32, UInt32))') AS dates,
  f AS (
    SELECT maker AS w,
           toUInt64OrZero(right(if(maker_asset_id = '0', taker_asset_id, maker_asset_id), 18)) AS k,
           toUInt32(timestamp) AS ts, maker_asset_id = '0' AS buy,
           toFloat64(if(maker_asset_id = '0', taker_amount_filled, maker_amount_filled)) / 1e6 AS sh,
           toFloat64(if(maker_asset_id = '0', maker_amount_filled, taker_amount_filled)) / 1e6 AS usd
    FROM polymarket.orders_filled
    WHERE is_deleted = 0 AND timestamp < '{cutoff}' AND cityHash64(maker) % {K} = {b}
  ),
  wt0 AS (
    SELECT w, k, countIf(buy) AS nb, minIf(ts, buy) AS fb, min(ts) AS ff,
           sumIf(sh, buy) AS bsh, sumIf(usd, buy) AS busd, sumIf(sh, NOT buy) AS ssh, sumIf(usd, NOT buy) AS susd,
           arrayFilter(x -> x.1 <= fb + 21600, groupArrayIf((ts, sh, usd), buy)) AS ep,
           arraySum(x -> x.2, ep) AS ep_sh, arraySum(x -> x.3, ep) AS ep_usd,
           arraySum(x -> if(x.1 <= fb + 21600, x.2, 0), groupArrayIf((ts, sh), NOT buy)) AS ep_ssh,
           arrayMap(x -> (x.1, toFloat32(x.2), toFloat32(x.3)), ep) AS epm
    FROM f GROUP BY w, k
  ),
  wt AS (SELECT *, min(ff) OVER (PARTITION BY w) AS wff FROM wt0),
  wt2 AS (
    SELECT wt.w AS w, wt.k AS k, nb, fb, ff, wff, bsh, busd, ssh, susd, ep_sh, ep_usd, ep_ssh, epm,
           m.c AS c, m.e AS e, m.p AS p, m.r AS r, m.cat AS cat
    FROM wt INNER JOIN m ON wt.k = m.k
  ),
  dec AS (
    SELECT w, e, minIf(fb, nb > 0) AS t0, any(wff) AS wff,
           argMinIf((c, p, r, cat, ep_sh, ep_usd, ep_ssh, k, epm), (fb, -ep_usd), nb > 0) AS d,
           groupArray((c, ff, r, p, bsh - ssh, susd - busd + if(p >= 0, p * (bsh - ssh), 0))) AS tl
    FROM wt2 GROUP BY w, e HAVING countIf(nb > 0) > 0
  ),
  x AS (
    SELECT w, e, t0, wff, d.1 AS c, d.2 AS p, d.3 AS r, d.4 AS cat, d.5 AS ep_sh, d.6 AS ep_usd, d.7 AS ep_ssh, d.8 AS k,
           d.9 AS epm, tl,
           arrayJoin(arrayConcat(arrayMap(z -> z.1, arrayFilter(z -> t0 >= z.2 AND t0 < z.1, dates)),
                                 if(t0 = wff AND ep_usd >= 100, [toUInt32(0)], CAST([], 'Array(UInt32)')))) AS D
    FROM dec
  ),
  y AS (
    SELECT w, D, cat, ep_usd, wff, e, t0, k, epm, p, r,
           ep_usd >= 1 AND (ep_sh - ep_ssh) >= 0.5 * ep_sh AS cnt,
           p >= 0 AND r > 0 AND r < D AS res,
           p = 1 AS won,
           ep_usd / ep_sh AS vw,
           p - vw AS edge,
           vw * (1 - vw) AS var,
           arrayAll(t -> t.2 >= D OR (t.3 > 0 AND t.3 < D AND t.4 >= 0), tl) AS cmp,
           arraySum(t -> if(t.3 > 0 AND t.3 < D AND t.4 >= 0, t.6, 0), tl) AS pnl_ev,
           arrayExists(t -> t.3 > 0 AND t.3 < D AND t.5 < -0.01, tl) AS unrel_ev,
           arraySum(t -> if(t.1 = c, t.6, 0), tl) AS pnl_mk,
           arrayExists(t -> t.1 = c AND t.5 < -0.01, tl) AS unrel_mk,
           cmp AND NOT unrel_ev AND pnl_ev > 0 AS mm
    FROM x
  ),
  agg AS (
    SELECT w, D,
      toUInt16(countIf(cnt AND t0 + 21600 <= D)) AS n_win, toUInt16(countIf(cnt AND res)) AS n_res, toUInt16(countIf(cnt AND res AND won)) AS n_won,
      toUInt16(countIf(cnt AND res AND cmp)) AS n_cmp, toUInt16(countIf(cnt AND res AND cmp AND mm)) AS n_mm,
      toUInt16(countIf(NOT cnt)) AS n_nc, any(wff) AS first_fill,
      anyIf((cityHash64(w), k, e, t0, toFloat32(ep_usd), epm, cat, p, r), D = 0) AS fr,
      toFloat32(sumIf(edge, cnt AND res)) AS se, toFloat32(sumIf(edge * edge, cnt AND res)) AS se2,
      toFloat32(sumIf(var, cnt AND res)) AS sv,
      toFloat32(sumIf(pnl_mk, cnt AND res)) AS pnl, toUInt16(countIf(cnt AND res AND unrel_mk)) AS n_unrel,
      toFloat32(sumIf(ep_usd, cnt AND res)) AS usd_res, toFloat32(quantileExactIf(0.5)(ep_usd, cnt AND t0 + 21600 <= D)) AS med_usd,
      [toUInt16(countIf(cnt AND res AND cat = 0)), toUInt16(countIf(cnt AND res AND cat = 1)),
       toUInt16(countIf(cnt AND res AND cat = 2)), toUInt16(countIf(cnt AND res AND cat = 3))] AS nc,
      [toFloat32(sumIf(edge, cnt AND res AND cat = 0)), toFloat32(sumIf(edge, cnt AND res AND cat = 1)),
       toFloat32(sumIf(edge, cnt AND res AND cat = 2)), toFloat32(sumIf(edge, cnt AND res AND cat = 3))] AS sec,
      [toFloat32(sumIf(var, cnt AND res AND cat = 0)), toFloat32(sumIf(var, cnt AND res AND cat = 1)),
       toFloat32(sumIf(var, cnt AND res AND cat = 2)), toFloat32(sumIf(var, cnt AND res AND cat = 3))] AS svc,
      [toUInt16(countIf(cnt AND res AND won AND cat = 0)), toUInt16(countIf(cnt AND res AND won AND cat = 1)),
       toUInt16(countIf(cnt AND res AND won AND cat = 2)), toUInt16(countIf(cnt AND res AND won AND cat = 3))] AS nwc
    FROM y GROUP BY w, D
  ),
  sc AS (
    SELECT agg.*,
      n_res = 5 AND n_won = 5 AS s1,
      n_cmp = 5 AND n_mm = 5 AS s1m,
      n_res >= 5 AND n_won = n_res AS s2,
      n_res >= 10 AND se > 0 AND se / sqrt(sv + 2.5) >= 2 AS s3,
      arrayMap(i -> nc[i] >= 8 AND sec[i] > 0 AND sec[i] / sqrt(svc[i] + 2.5) >= 2, [1, 2, 3, 4]) AS s4,
      n_res >= 5 AS e5,
      row_number() OVER (PARTITION BY D, e5 ORDER BY pnl DESC) AS rk,
      sum(toUInt32(e5)) OVER (PARTITION BY D) AS ne5
    FROM agg
  ),
  sc2 AS (
    SELECT sc.*,
      toUInt16(s1) + 2 * toUInt16(s1m) + 4 * toUInt16(s2) + 8 * toUInt16(s3) + 16 * toUInt16(s4[1]) + 32 * toUInt16(s4[2])
        + 64 * toUInt16(s4[3]) + 128 * toUInt16(s4[4]) + 256 * toUInt16(e5 AND rk <= ceil(0.02 * ne5) + 3)
        + 512 * toUInt16(e5 AND sipHash64(w) % 100 = 0) AS flags
    FROM sc
  )
SELECT D,
  count() AS n_w_any, countIf(n_win >= 1) AS n_w_counted, countIf(n_res >= 1) AS n_res1, countIf(n_res >= 5) AS n_res5,
  countIf(n_res >= 10) AS n_res10, countIf(n_cmp >= 5) AS n_cmp5,
  countIf(s1) AS n_s1, countIf(s1m) AS n_s1m, countIf(s2) AS n_s2, countIf(s3) AS n_s3,
  countIf(s4[1]) AS n_s4_sports, countIf(s4[2]) AS n_s4_politics, countIf(s4[3]) AS n_s4_crypto, countIf(s4[4]) AS n_s4_other,
  countIf(nc[1] >= 8) AS n_c8_sports, countIf(nc[2] >= 8) AS n_c8_politics, countIf(nc[3] >= 8) AS n_c8_crypto, countIf(nc[4] >= 8) AS n_c8_other,
  sum(n_res) AS sum_n_res, sum(n_win) AS sum_n_win,
  groupArrayIf((w, flags, n_win, n_res, n_won, n_cmp, n_mm, n_nc, n_unrel, se, se2, sv, pnl, usd_res, med_usd, nc, nwc, sec, svc,
                first_fill), flags > 0) AS q,
  groupArrayIf(fr, D = 0) AS fresh
FROM sc2 GROUP BY D ORDER BY D
"""

FCOLS = ["wallet_hash", "k", "e_idx", "t0", "ep_usd", "epm", "cat", "p", "r"]
QCOLS = ["wallet", "flags", "n_win", "n_res", "n_won", "n_cmp", "n_mm", "n_nc", "n_unrel", "se", "se2", "sv", "pnl", "usd_res",
         "med_usd", "nc", "nwc", "sec", "svc", "first_fill"]


def build_sql(K: int, b: int) -> str:
    dates = "[" + ",".join(f"({d},{d12})" for d, d12 in DATES) + "]"
    return SQL.format(dates=dates, K=K, b=b, cutoff=CUTOFF)


def run_one(K: int, b: int, ext: dict, cdir: Path) -> None:
    """Run bucket b of K; if the packed result exceeds the 1 MB cap, split it into (2K, b) and (2K, b+K)."""
    p = cdir / f"K{K}_b{b:03d}.parquet"
    if p.exists():
        return
    t = time.time()
    try:
        body = ch.q(build_sql(K, b), ext)
    except ch.CHError as e:
        if "Limit for result" in str(e) or "TOO_MANY_ROWS_OR_BYTES" in str(e):
            print(f"bucket {b}/{K}: result > 1 MB, splitting into {b}/{2 * K} and {b + K}/{2 * K}", flush=True)
            run_one(2 * K, b, ext, cdir)
            run_one(2 * K, b + K, ext, cdir)
            return
        raise
    names = [m_["name"] for m_ in body["meta"]]
    cnt_rows, cand, fresh = [], [], []
    for r in body["data"]:
        d = dict(zip(names, r))
        q = d.pop("q"); fr = d.pop("fresh")
        if int(d["D"]) == 0:
            for z in fr:
                fresh.append({"bucket": b, "K": K, **dict(zip(FCOLS, z))})
            continue
        cnt_rows.append({**d, "bucket": b, "K": K})
        for z in q:
            cand.append({"D": int(d["D"]), "bucket": b, "K": K, **dict(zip(QCOLS, z))})
    cdf = pd.DataFrame(cnt_rows)
    qdf = pd.DataFrame(cand)
    fdf = pd.DataFrame(fresh)
    if len(fdf):
        fdf["ep_ts"] = fdf.epm.map(lambda a: [int(x[0]) for x in a])
        fdf["ep_sh"] = fdf.epm.map(lambda a: [float(x[1]) for x in a])
        fdf["ep_usd_fills"] = fdf.epm.map(lambda a: [float(x[2]) for x in a])
        fdf = fdf.drop(columns=["epm"])
    cdf.to_parquet(cdir / f"K{K}_b{b:03d}_counts.parquet", index=False)
    fdf.to_parquet(cdir / f"K{K}_b{b:03d}_fresh.parquet", index=False)
    qdf.to_parquet(p, index=False)
    st = body.get("statistics", {})
    print(f"bucket {b}/{K}: {len(qdf)} candidates, {len(fdf)} fresh, {round(time.time() - t, 1)}s "
          f"(server {st.get('elapsed')}s, {st.get('rows_read')} rows)", flush=True)


def run(K: int, b0: int, b1: int):
    meta = (OUT / "meta_ext.tsv").read_text()
    ext = {"m": (META_STRUCT, meta)}
    cdir = OUT / "screen_buckets"; cdir.mkdir(exist_ok=True)
    for b in range(b0, b1 + 1):
        run_one(K, b, ext, cdir)


if __name__ == "__main__":
    K = int(sys.argv[1]) if len(sys.argv) > 1 else 64
    b0 = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    b1 = int(sys.argv[3]) if len(sys.argv) > 3 else K - 1
    run(K, b0, b1)
