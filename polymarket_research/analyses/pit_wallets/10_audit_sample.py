"""Independent audit of the server-side decision/screen pipeline on a random sample of screened wallets.

Run from polymarket_research/:  python analyses/pit_wallets/10_audit_sample.py [n_per_screen]
For sampled (D, wallet) members of S1, S1m, S2 and S3, the wallet's full trade history is pulled from the Data API
(/v2/trades?user=..&taker_only=false; an independent source of the same fills) and the pre-registered decision
rules are re-implemented in pandas with token_meta_pit.parquet (events, payouts, t_res). The audit compares
n_res, n_won, the edge sum and the screen flags with the CryptoHouse result. Data API rows carry no maker/taker
role and may be capped for very active wallets, so wallets with more than 20,000 trade rows are skipped.
Writes data/derived/pit_wallets/audit_sample.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

OUT = ROOT / "data" / "derived" / "pit_wallets"
CUTOFF = 1764547200  # 2025-12-01


def decisions(tr: pd.DataFrame, tm: pd.DataFrame) -> pd.DataFrame:
    t = tr.merge(tm, on="token_id", how="inner")
    t = t.sort_values("ts")
    rows = []
    for (e,), g in t.groupby(["e_idx"]):
        b = g[g.side == "BUY"]
        if b.empty:
            continue
        t0 = b.ts.min()
        first = b[b.ts == t0].groupby("token_id").usd.sum().sort_values(ascending=False)
        k = first.index[0]
        gk = g[g.token_id == k]
        ep = gk[(gk.side == "BUY") & (gk.ts <= t0 + 21600)]
        ep_ssh = gk[(gk.side == "SELL") & (gk.ts <= t0 + 21600)].shares.sum()
        meta = g[g.token_id == k].iloc[0]
        tl = g.groupby("token_id").agg(
            bsh=("shares", lambda s: s[g.loc[s.index, "side"] == "BUY"].sum()),
            ssh=("shares", lambda s: s[g.loc[s.index, "side"] == "SELL"].sum()),
            busd=("usd", lambda s: s[g.loc[s.index, "side"] == "BUY"].sum()),
            susd=("usd", lambda s: s[g.loc[s.index, "side"] == "SELL"].sum()),
            ff=("ts", "min"), p=("p", "first"), r=("r", "first"), c=("c_idx", "first"))
        rows.append({"e_idx": e, "t0": t0, "token_id": k, "c": meta.c_idx, "p": meta.p, "r": meta.r, "cat": meta.cat_idx,
                     "ep_sh": ep.shares.sum(), "ep_usd": ep.usd.sum(), "ep_ssh": ep_ssh, "tl": tl})
    return pd.DataFrame(rows)


def record(dec: pd.DataFrame, D: int) -> dict:
    D12 = int(pd.Timestamp(D, unit="s", tz="UTC").replace(year=pd.Timestamp(D, unit="s", tz="UTC").year - 1).timestamp())
    x = dec[(dec.t0 >= D12) & (dec.t0 < D)].copy()
    x["cnt"] = (x.ep_usd >= 1) & ((x.ep_sh - x.ep_ssh) >= 0.5 * x.ep_sh)
    x["res"] = (x.p >= 0) & (x.r > 0) & (x.r < D)
    x["vw"] = x.ep_usd / x.ep_sh
    y = x[x.cnt & x.res]
    se = float((y.p - y.vw).sum()); sv = float((y.vw * (1 - y.vw)).sum())
    n = len(y); nw = int((y.p == 1).sum())
    cmp_mm = []
    for r in y.itertuples():
        tl = r.tl
        cmp = bool(((tl.ff >= D) | ((tl.r > 0) & (tl.r < D) & (tl.p >= 0))).all())
        res_t = tl[(tl.r > 0) & (tl.r < D) & (tl.p >= 0)]
        pnl = float((res_t.susd - res_t.busd + res_t.p * (res_t.bsh - res_t.ssh)).sum())
        unrel = bool(((res_t.bsh - res_t.ssh) < -0.01).any())
        cmp_mm.append((cmp, cmp and not unrel and pnl > 0))
    n_cmp = sum(c for c, _ in cmp_mm); n_mm = sum(m for _, m in cmp_mm)
    return {"a_n_res": n, "a_n_won": nw, "a_se": se, "a_sv": sv, "a_n_cmp": n_cmp, "a_n_mm": n_mm,
            "a_S1": n == 5 and nw == 5, "a_S1m": n_cmp == 5 and n_mm == 5, "a_S2": n >= 5 and nw == n,
            "a_S3": n >= 10 and se > 0 and se / np.sqrt(sv + 2.5) >= 2}


def main(n_per: int):
    mem = pd.read_parquet(OUT / "screen_members.parquet")
    tm = pd.read_parquet(OUT / "token_meta_pit.parquet", columns=["token_id", "c_idx", "e_idx", "p", "r", "cat_idx", "has_meta"])
    tm = tm[tm.has_meta]
    smp = pd.concat([mem[mem.screen == s].sample(min(n_per, (mem.screen == s).sum()), random_state=5)
                     for s in ["S1", "S1m", "S2", "S3"]])
    out = []
    for m in smp.itertuples(index=False):
        rows = list(api.data_v2("/v2/trades", {"user": m.wallet, "taker_only": "false"}, cache=True, max_pages=20))
        if len(rows) >= 20000:
            out.append({"D": m.D, "wallet": m.wallet, "screen": m.screen, "skipped": "too many rows"}); continue
        tr = pd.DataFrame(rows)
        if tr.empty:
            out.append({"D": m.D, "wallet": m.wallet, "screen": m.screen, "skipped": "no data api rows"}); continue
        tr = tr.rename(columns={"timestamp": "ts", "size": "shares"})
        tr["token_id"] = tr.token_id.astype(str); tr["shares"] = tr.shares.astype(float)
        tr["usd"] = tr.shares * tr.price.astype(float)
        tr = tr[tr.ts < CUTOFF]
        dec = decisions(tr, tm)
        a = record(dec, int(m.D))
        out.append({"D": m.D, "wallet": m.wallet, "screen": m.screen, "n_trade_rows": len(tr), "n_res": m.n_res,
                    "n_won": m.n_won, "se": m.se, "n_cmp": m.n_cmp, "n_mm": m.n_mm, **a})
        print(out[-1], flush=True)
    df = pd.DataFrame(out)
    df.to_parquet(OUT / "audit_sample.parquet", index=False)
    ok = df.dropna(subset=["a_n_res"])
    flag = {"S1": "a_S1", "S1m": "a_S1m", "S2": "a_S2", "S3": "a_S3"}
    ok = ok.assign(screen_reproduced=[bool(r[flag[r.screen]]) for _, r in ok.iterrows()])
    print("audited", len(ok), "skipped", len(df) - len(ok))
    print("n_res equal:", float((ok.a_n_res == ok.n_res).mean()), " n_won equal:", float((ok.a_n_won == ok.n_won).mean()),
          " |se diff| < 0.01:", float(((ok.a_se - ok.se).abs() < 0.01).mean()))
    print(ok.groupby("screen").screen_reproduced.mean())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
