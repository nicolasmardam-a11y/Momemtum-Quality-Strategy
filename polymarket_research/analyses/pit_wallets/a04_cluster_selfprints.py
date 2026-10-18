"""Stage 4 (audit), step a04: the cluster signal (CL) priced WITHOUT the followed (fresh) wallets' own prints.

Pre-registration section 7 says prices paid by the followed wallet are never used as follower prices; section 12 says
the cluster signal uses the section-7 follower model. Addendum A10 nevertheless priced CL entries from ALL taker BUY
prints after the signal ("cluster signals: no exclusion"), so later buys by the cluster's own fresh wallets could be the
follower's entry print. This script re-prices every cluster signal from the first taker BUY print at >= signal_ts + d
(d = 5 s, 30 s, 2 min, 10 min, 15 min, 60 min; within 60 min) by wallets that are NOT fresh wallets whose first
decision is on that token (fresh_first_decisions.parquet, matched by cityHash64(address)), and also without the
exclusion (to reproduce stage 2). One CryptoHouse query (external table of 773 signals).
Then evaluates CL (first print + 0.01, cap 0.999, $100, hold; fee 0 and current category fee) by split and delay, with
an event-clustered CI at 2 min, with and without the exclusion.
Output: data/derived/pit_wallets/audit/a04_cluster_prices.parquet, a04_cluster_eval.parquet
Run from polymarket_research/:  python analyses/pit_wallets/a04_cluster_selfprints.py
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
DL = [5, 30, 120, 600, 900, 3600]
SQL = """
WITH
  s AS (SELECT sid, k, t, ex, arrayJoin(range(intDiv(t, 3600), intDiv(t + 7205, 3600) + 1)) AS hb FROM sg),
  pr AS (
    SELECT toUInt64OrZero(right(taker_asset_id, 18)) AS k, toUInt32(timestamp) AS ts, intDiv(ts, 3600) AS hb,
           cityHash64(maker) AS mh, toFloat64(maker_amount_filled) / toFloat64(taker_amount_filled) AS px
    FROM polymarket.orders_filled
    WHERE is_deleted = 0 AND maker_asset_id = '0' AND taker IN {exch} AND taker_amount_filled > 0
      AND timestamp >= {T0} AND timestamp < {T1} AND toUInt64OrZero(right(taker_asset_id, 18)) IN (SELECT k FROM sg)
  ),
  j AS (
    SELECT s.sid AS sid, any(s.t) AS t, arraySort(x -> x.1, groupArray((pr.ts, pr.px, has(s.ex, pr.mh)))) AS a
    FROM s INNER JOIN pr ON s.k = pr.k AND s.hb = pr.hb
    WHERE pr.ts >= s.t + 5 AND pr.ts < s.t + 7205
    GROUP BY sid
  )
SELECT sid,
  arrayMap(d -> (arrayFirst(x -> x.1 >= t + d AND x.1 < t + d + 3600, a).1,
                 arrayFirst(x -> x.1 >= t + d AND x.1 < t + d + 3600, a).2,
                 arrayFirst(x -> x.1 >= t + d AND x.1 < t + d + 3600 AND NOT x.3, a).1,
                 arrayFirst(x -> x.1 >= t + d AND x.1 < t + d + 3600 AND NOT x.3, a).2,
                 arrayCount(x -> x.1 >= t + d AND x.1 < t + d + 3600 AND x.3, a),
                 arrayCount(x -> x.1 >= t + d AND x.1 < t + d + 3600, a)), {dl}) AS v
FROM j
"""


def main():
    fpath = OUT / "audit" / "a04_cluster_prices.parquet"
    if fpath.exists():   # resumable: re-evaluate without re-querying
        evaluate(pd.read_parquet(fpath))
        return
    cl = pd.read_parquet(OUT / "cluster_signals.parquet", columns=["k", "signal_ts"])
    cl = cl.reset_index(drop=True); cl["sid"] = np.arange(len(cl))
    fr = pd.read_parquet(OUT / "fresh_first_decisions.parquet", columns=["wallet_hash", "k"])
    ex = fr[fr.k.isin(cl.k)].groupby("k").wallet_hash.apply(lambda s: "[" + ",".join(map(str, sorted(set(s)))) + "]")
    cl["ex"] = cl.k.map(ex).fillna("[]")
    txt = "".join(f"{a}\t{b}\t{c}\t{d}\n" for a, b, c, d in zip(cl.sid, cl.k, cl.signal_ts, cl.ex))
    T0, T1 = int(cl.signal_ts.min()), int(cl.signal_ts.max()) + 7206
    body = ch.q(SQL.format(exch=EXCH, T0=T0, T1=T1, dl="[" + ",".join(map(str, DL)) + "]"),
                {"sg": ("sid UInt32, k UInt64, t UInt32, ex Array(UInt64)", txt)})
    rows = []
    for sid, v in body["data"]:
        for d, (ta, pa, tx, px, nself, nall) in zip(DL, v):
            rows.append(dict(sid=int(sid), delay=d, ts_all=int(ta), px_all=float(pa), ts_ex=int(tx), px_ex=float(px),
                             n_self=int(nself), n_all=int(nall)))
    out = pd.DataFrame(rows).merge(cl[["sid", "k", "signal_ts"]], on="sid")
    out.to_parquet(OUT / "audit" / "a04_cluster_prices.parquet", index=False)
    st = body.get("statistics", {})
    print(f"signals {len(cl)}, with prints {out.sid.nunique()}, server {st.get('elapsed')} s, rows {st.get('rows_read')}")
    evaluate(out)


def evaluate(a: pd.DataFrame) -> None:
    from a01_recompute_stage2 import RATE, cboot
    s = pd.read_parquet(OUT / "sig_members.parquet")
    s = s[s.stype == "CL"]
    s = s.merge(pd.read_parquet(OUT / "follower_prices.parquet"), on="psid", how="left")
    rng = np.random.default_rng(5)
    rows = []
    for d in DL:
        x = a[a.delay == d][["k", "signal_ts", "ts_all", "px_all", "ts_ex", "px_ex"]]
        g = s.merge(x, left_on=["k", "t_sig"], right_on=["k", "signal_ts"], how="left")
        for which in ["all", "ex"]:
            ts = g[f"ts_{which}"].fillna(0).values; px = g[f"px_{which}"].fillna(0).values
            ok = (ts > 0) & (px > 0) & (ts < g.r.values)
            e = np.minimum(0.999, np.round(px, 4) + 0.01)
            p = g.p.astype(float).values
            for fee in ["hist", "cur"]:
                fr = g.category.map(RATE).fillna(0.05).values * (1 - e) if fee == "cur" else 0.0
                roi = np.where(ok, p / np.where(ok, e, 1) - 1 - fr, 0.0)
                for sp in ["train", "val", "test"]:
                    m = (g.split == sp).values & ok
                    lo, hi = (cboot(g.underlying_key.values[m], 100 * roi[m], np.full(int(m.sum()), 100.0), rng, 1000)
                              if d == 120 else (np.nan, np.nan))
                    rows.append(dict(delay=d, prints=which, fee=fee, split=sp, n_fill=int(m.sum()),
                                     n_ev=int(g.underlying_key[m].nunique()), roi=float(roi[m].mean()), lo=lo, hi=hi,
                                     share_first_print_by_fresh=float(((g.ts_all != g.ts_ex) & (g.ts_all > 0))[g.split == sp].mean())))
    r = pd.DataFrame(rows)
    r.to_parquet(OUT / "audit" / "a04_cluster_eval.parquet", index=False)
    print(r[r.delay == 120].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
