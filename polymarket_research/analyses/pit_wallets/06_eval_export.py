"""Step 6: evaluation-window export for screened wallets.

Run from polymarket_research/:  python analyses/pit_wallets/06_eval_export.py [first_D_index] [last_D_index]
Followed set at D = members of each screen at D (screen_members.parquet). Screens such as S2 have tens of
thousands of members per date, so the export uses a fixed, deterministic random sample per (D, screen)
(first CAP_DEC members by md5(wallet|screen); all members if fewer). Pre-registration addendum A7.
  * decision export (all sampled wallets): every NEW decision in the window [D, next month), i.e. the token of the
    wallet's first BUY in an event whose event-level first BUY (over the wallet's whole history up to the window
    end) is in the window: t0, first-second shares/collateral/taker collateral, collateral bought in the first
    10 min (F1), 6 h episode shares/collateral/sells, first fill id, the wallet's last fill before D and its
    activity days in [D-61d, window end) (F2).
  * fill export (sub-sample, first CAP_FILL per (D, screen)): every BUY fill in the window (ts, shares, collateral,
    role, tx hash as UInt256), on every token, with or without metadata.
One query per (D, wallet chunk); a chunk whose packed result overflows the 1 MB cap is halved (wallets), and a single
heavy wallet is split into time slices for its fills (decision rows only in the slice that starts at D).
Raw chunks: data/derived/pit_wallets/eval_chunks/; merged by 06b_eval_merge.py.
"""
from __future__ import annotations

import hashlib
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
import ch  # noqa: E402

OUT = ROOT / "data" / "derived" / "pit_wallets"
EXCH = "('0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e', '0xc5d563a36ae78145c45a50134d48a1215220f80a')"
META_STRUCT = "k UInt64, c UInt32, e UInt32, p Int8, r UInt32, cat UInt8"
Q_STRUCT = "w String, wi UInt32, e2 UInt8"
CAP_DEC = 1000      # wallets per (D, screen) in the decision export
CAP_FILL = 150      # wallets per (D, screen) in the fill export
TARGET_BYTES = 650_000

COUNT_SQL = """
SELECT groupArray((wi, n)) FROM (
  SELECT q.wi AS wi, n FROM (
    SELECT maker AS w, toUInt32(count()) AS n, toUInt32(uniqExact(taker_asset_id)) AS nt FROM polymarket.orders_filled
    WHERE is_deleted = 0 AND maker_asset_id = '0' AND timestamp >= {D0} AND timestamp < {D1} AND maker IN (SELECT w FROM q)
    GROUP BY maker) AS c INNER JOIN q ON c.w = q.w)
"""

SQL = """
WITH
  f AS (
    SELECT maker AS w,
           toUInt64OrZero(right(if(maker_asset_id = '0', taker_asset_id, maker_asset_id), 18)) AS k,
           toUInt32(timestamp) AS ts, maker_asset_id = '0' AS buy,
           toFloat64(if(maker_asset_id = '0', taker_amount_filled, maker_amount_filled)) / 1e6 AS sh,
           toFloat64(if(maker_asset_id = '0', maker_amount_filled, taker_amount_filled)) / 1e6 AS usd,
           taker IN {exch} AS tk, id
    FROM polymarket.orders_filled
    WHERE is_deleted = 0 AND timestamp < {D1} AND maker IN (SELECT w FROM q)
  ),
  wt0 AS (
    SELECT w, k, countIf(buy) AS nb, minIf(ts, buy) AS fb, maxIf(ts, ts < {D0}) AS last_before,
           groupArrayIf((ts, toFloat32(sh), toFloat32(usd), tk,
                         reinterpretAsUInt256(reverse(unhex(substring(id, 3, 64))))), buy AND ts >= {S0} AND ts < {S1}
                         AND w IN (SELECT w FROM q WHERE e2 = 1)) AS wb,
           arrayFilter(x -> x.1 <= fb + 21600, groupArrayIf((ts, sh, usd, tk), buy)) AS ep,
           arraySum(x -> x.2, ep) AS ep_sh, arraySum(x -> x.3, ep) AS ep_usd,
           arraySum(x -> if(x.1 <= fb + 600, x.3, 0), ep) AS usd10m,
           arraySum(x -> if(x.1 = fb, x.2, 0), ep) AS sh_first, arraySum(x -> if(x.1 = fb, x.3, 0), ep) AS usd_first,
           arraySum(x -> if(x.1 = fb AND x.4, x.3, 0), ep) AS usd_first_taker, length(ep) AS ep_n,
           arraySum(x -> if(x.1 <= fb + 21600, x.2, 0), groupArrayIf((ts, sh), NOT buy)) AS ep_ssh,
           argMinIf(id, ts, buy) AS fid,
           groupUniqArrayIf(toUInt8(intDiv(ts, 86400) - {day0}), ts >= {Dm61}) AS days
    FROM f GROUP BY w, k
  ),
  wt2 AS (
    SELECT wt0.*, m.k != 0 AS has_meta, m.c AS c, m.e AS e, m.p AS p, m.r AS r, m.cat AS cat
    FROM wt0 LEFT JOIN m ON wt0.k = m.k
  ),
  wt3 AS (
    SELECT *,
      min(if(nb > 0, fb, 4294967295)) OVER (PARTITION BY w, has_meta, if(has_meta, toUInt64(e), k)) AS t0e,
      argMin(k, (if(nb > 0, fb, 4294967295), -ep_usd)) OVER (PARTITION BY w, has_meta, if(has_meta, toUInt64(e), k)) AS kdec,
      max(last_before) OVER (PARTITION BY w) AS w_last_before,
      groupUniqArrayArray(days) OVER (PARTITION BY w) AS w_days
    FROM wt2
  )
SELECT groupArray((q.wi, k, toUInt8(has_meta), c, e, p, r, cat,
                   {first} AND k = kdec AND t0e >= {D0} AND t0e < {D1} AS is_new,
                   if(is_new, t0e, 0), if(is_new, toFloat32(ep_sh), 0), if(is_new, toFloat32(ep_usd), 0),
                   if(is_new, toFloat32(ep_ssh), 0), if(is_new, toFloat32(usd10m), 0), if(is_new, toFloat32(sh_first), 0),
                   if(is_new, toFloat32(usd_first), 0), if(is_new, toFloat32(usd_first_taker), 0), if(is_new, ep_n, 0),
                   if(is_new, fid, ''), w_last_before, if(is_new, w_days, CAST([], 'Array(UInt8)')), wb)) AS a
FROM wt3 INNER JOIN q ON wt3.w = q.w
WHERE length(wb) > 0 OR ({first} AND k = kdec AND t0e >= {D0} AND t0e < {D1})
"""

COLS = ["wi", "k", "has_meta", "c_idx", "e_idx", "p", "r", "cat", "is_new", "t0", "ep_sh", "ep_usd", "ep_ssh", "usd10m",
        "sh_first", "usd_first", "usd_first_taker", "ep_n", "first_fill_id", "w_last_before", "w_days", "wb"]


def months():
    out = []
    for y in (2024, 2025):
        for mth in range(1, 13):
            a = datetime(y, mth, 1, tzinfo=timezone.utc)
            b = datetime(y + (mth == 12), 1 if mth == 12 else mth + 1, 1, tzinfo=timezone.utc)
            out.append((int(a.timestamp()), int(b.timestamp())))
    return out


def sample_members(mem: pd.DataFrame) -> pd.DataFrame:
    """Deterministic per-(D, screen) sample: rank by md5(wallet|screen)."""
    mem = mem.copy()
    mem["h"] = [hashlib.md5(f"{w}|{sc}".encode()).hexdigest() for w, sc in zip(mem.wallet, mem.screen)]
    mem["rank"] = mem.groupby(["D", "screen"]).h.rank(method="first")
    mem["in_dec"] = mem["rank"] <= CAP_DEC
    mem["in_fill"] = mem["rank"] <= CAP_FILL
    return mem.drop(columns=["h"])


def run(i0: int, i1: int):
    mem = sample_members(pd.read_parquet(OUT / "screen_members.parquet", columns=["D", "wallet", "screen", "n_win"]))
    mem.to_parquet(OUT / "eval_sample_members.parquet", index=False)
    wal = sorted(mem.loc[mem.in_dec, "wallet"].unique())
    widx = {w: i for i, w in enumerate(wal)}
    pd.DataFrame({"wi": range(len(wal)), "wallet": wal}).to_parquet(OUT / "eval_wallet_index.parquet", index=False)
    meta = (OUT / "meta_ext.tsv").read_text()
    cdir = OUT / "eval_chunks"; cdir.mkdir(exist_ok=True)
    for i, (D0, D1) in enumerate(months()):
        if i < i0 or i > i1:
            continue
        m = mem[(mem.D == D0) & mem.in_dec]
        if m.empty:
            continue
        g = m.groupby("wallet").agg(e2=("in_fill", "max"), n_win=("n_win", "max"))
        qtxt = "".join(f"{w}\t{widx[w]}\t{int(r.e2)}\n" for w, r in g.iterrows())
        b = ch.q(COUNT_SQL.format(D0=D0, D1=D1), {"q": (Q_STRUCT, qtxt)})
        cnt = {int(a): (int(n), int(nt)) for a, n, nt in b["data"][0][0]}
        # estimated bytes per wallet: decision rows (<= tokens touched in window, ~200 B each) + fills (45 B, e2 only)
        est = {}
        for w, r in g.iterrows():
            n, nt = cnt.get(widx[w], (0, 0))
            est[w] = 200 * nt + (45 * n if r.e2 else 0) + 60
        order = sorted(g.index, key=lambda w: est[w])
        chunks, cur, tot = [], [], 0
        for w in order:
            if cur and tot + est[w] > TARGET_BYTES:
                chunks.append(cur); cur, tot = [], 0
            cur.append(w); tot += est[w]
        if cur:
            chunks.append(cur)
        print(f"D={datetime.fromtimestamp(D0, timezone.utc):%Y-%m} wallets={len(g)} (fill-export {int(g.e2.sum())}) "
              f"buys_all={sum(v[0] for v in cnt.values())} chunks={len(chunks)}", flush=True)
        for j, ws in enumerate(chunks):
            qq = "".join(f"{w}\t{widx[w]}\t{int(g.at[w, 'e2'])}\n" for w in ws)
            export(cdir, D0, D1, f"c{j:04d}", ws, qq, meta, D0, D1)


def export(cdir, D0, D1, tag, ws, qq, meta, S0, S1, depth=0):
    """Export one wallet chunk; on a 1 MB overflow split the chunk (or, for one wallet, its fill time range)."""
    p = cdir / f"D{D0}_{tag}.parquet"
    if p.exists():
        return
    t = time.time()
    first = "1" if S0 == D0 else "0"
    try:
        body = ch.q(SQL.format(exch=EXCH, D0=D0, D1=D1, day0=D0 // 86400 - 61, Dm61=D0 - 61 * 86400, S0=S0, S1=S1,
                               first=first), {"q": (Q_STRUCT, qq), "m": (META_STRUCT, meta)})
    except ch.CHError as e:
        over = "Limit for result" in str(e) or "TOO_MANY_ROWS_OR_BYTES" in str(e)
        if over and len(ws) > 1 and depth < 12:
            h = len(ws) // 2
            lines = qq.splitlines(keepends=True)
            export(cdir, D0, D1, tag + "a", ws[:h], "".join(lines[:h]), meta, S0, S1, depth + 1)
            export(cdir, D0, D1, tag + "b", ws[h:], "".join(lines[h:]), meta, S0, S1, depth + 1)
            return
        if over and S1 - S0 > 600 and depth < 16:
            mid = (S0 + S1) // 2
            export(cdir, D0, D1, tag + "t", ws, qq, meta, S0, mid, depth + 1)
            export(cdir, D0, D1, tag + "u", ws, qq, meta, mid, S1, depth + 1)
            return
        print(f"  {tag} FAILED ({len(ws)} wallets): {str(e)[-200:]}", flush=True)
        return
    df = pd.DataFrame(body["data"][0][0], columns=COLS)
    df["D"] = D0; df["slice_start"] = S0; df["slice_end"] = S1
    df.to_parquet(p, index=False)
    print(f"  {tag}: {len(ws)} wallets, {len(df)} rows, {int(df.is_new.astype(bool).sum())} new decisions, "
          f"{sum(len(x) for x in df.wb)} buys, {round(time.time() - t, 1)}s", flush=True)


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 23
    run(a, b)
