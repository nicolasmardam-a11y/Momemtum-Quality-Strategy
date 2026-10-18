"""Stage 4 (audit), step a03: independent point-in-time re-derivation of the trader's screen (S1) at TEST dates.

Auditor's own implementation (not the code of 04_screens.py or 10_audit_sample.py), on a fresh hash sample
(salt 'auditor-a03'):
  * 25 S1 members at selection dates 2025-07-01 .. 2025-12-01;
  * negative controls from the random eligible sample B1 at the same dates: 8 wallets with n_res = 5 and n_won = 4,
    6 with n_res = 6 and n_won = 6 (neither may be S1).
For each wallet: full trade history from Data API /v2/trades?user=..&taker_only=false (independent of CryptoHouse),
truncated to timestamp < D. Pre-registered rules (sections 4-6): decision = (wallet, underlying event), t0 = first
BUY, decision token = largest $ bought in the t0 second, 6 h episode (fills < D), counted if episode $ >= 1 and
net shares >= 50%, resolved if the market is clean and Gamma closedTime < D, window t0 in [D - 12 months, D).
Look-ahead checks: (i) every fill used is < D; (ii) for every counted resolved decision, the market's UMA resolution
record (Data API /v2/resolutions last_update_timestamp, an independent source) is also before D; (iii) the trailing
record contains no decision whose market resolved at or after D.
Output: data/derived/pit_wallets/audit/a03_pit_audit.parquet (+ per-decision a03_decisions.parquet).
Run from polymarket_research/:  python analyses/pit_wallets/a03_pit_audit_s1.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

OUT = ROOT / "data" / "derived" / "pit_wallets"
AUD = OUT / "audit"
T_TEST = 1751328000


def h(x: str) -> str:
    return hashlib.md5(("auditor-a03|" + x).encode()).hexdigest()


def minus12(D: int) -> int:
    d = pd.Timestamp(D, unit="s", tz="UTC")
    return int(pd.Timestamp(year=d.year - 1, month=d.month, day=1, tz="UTC").timestamp())


def to_unix(v):
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return int(pd.Timestamp(v).timestamp())


def derive(rows: list[dict], D: int, tm: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    t = pd.DataFrame(rows)
    if t.empty:
        return pd.DataFrame(), {"n_rows": 0}
    t["ts"] = t["timestamp"].astype(int)
    t = t[t.ts < D].copy()
    t["token_id"] = t["asset"].astype(str) if "asset" in t else t["token_id"].astype(str)
    t["size"] = t["size"].astype(float); t["price"] = t["price"].astype(float)
    t["usd"] = t["size"] * t["price"]
    t["buy"] = t["side"].astype(str).str.upper() == "BUY"
    t = t.merge(tm, on="token_id", how="inner")
    info = {"n_rows": len(rows), "n_rows_lt_D": len(t), "max_ts_used": int(t.ts.max()) if len(t) else 0}
    lo = minus12(D)
    b = t[t.buy]
    t0 = b.groupby("underlying_key").ts.min().rename("t0")
    t0 = t0[(t0 >= lo) & (t0 < D)]
    out = []
    for ue, tt in t0.items():
        fb = b[(b.underlying_key == ue) & (b.ts == tt)]
        tok = fb.groupby("token_id").usd.sum().idxmax()
        ep = t[(t.token_id == tok) & (t.ts >= tt) & (t.ts <= tt + 21600)]
        eb, es = ep[ep.buy], ep[~ep.buy]
        sh, usd = eb["size"].sum(), eb.usd.sum()
        meta = tm[tm.token_id == tok].iloc[0]
        counted = (usd >= 1) and (sh - es["size"].sum() >= 0.5 * sh)
        resolved = bool(meta.market_clean) and meta.r > 0 and meta.r < D
        out.append(dict(underlying_key=ue, t0=int(tt), token_id=tok, condition_id=meta.condition_id, usd=usd,
                        vwap=usd / sh if sh else np.nan, counted=counted, resolved=resolved, r=int(meta.r),
                        won=bool(meta.p == 1)))
    return pd.DataFrame(out), info


def main():
    tm = pd.read_parquet(OUT / "token_meta_pit.parquet",
                         columns=["token_id", "condition_id", "underlying_key", "p", "r", "market_clean"])
    tm["token_id"] = tm.token_id.astype(str)
    m = pd.read_parquet(OUT / "screen_members.parquet", columns=["D", "wallet", "flags", "n_res", "n_won", "se"])
    m = m.drop_duplicates(["D", "wallet"])
    m = m[m.D >= T_TEST]
    m["hh"] = [h(f"{w}|{d}") for w, d in zip(m.wallet, m.D)]
    s1 = m[(m["flags"] & 1) > 0].sort_values("hh").head(25).assign(group="S1")
    b1 = m[(m["flags"] & 512) > 0]
    c4 = b1[(b1.n_res == 5) & (b1.n_won == 4)].sort_values("hh").head(8).assign(group="ctrl_5of4")
    c6 = b1[(b1.n_res == 6) & (b1.n_won == 6)].sort_values("hh").head(6).assign(group="ctrl_6of6")
    smp = pd.concat([s1, c4, c6], ignore_index=True)
    res, decs = [], []
    resol_cache = {}
    for x in smp.itertuples(index=False):
        rows = api.trades(user=x.wallet, taker_only=False, cache=True)
        if len(rows) > 20000:
            res.append(dict(D=x.D, wallet=x.wallet, group=x.group, skipped=True)); continue
        d, info = derive(rows, int(x.D), tm)
        r = dict(D=x.D, wallet=x.wallet, group=x.group, skipped=False, n_res_s1=int(x.n_res), n_won_s1=int(x.n_won), **info)
        if len(d):
            cr = d[d.counted & d.resolved]
            r.update(a_n_res=len(cr), a_n_won=int(cr.won.sum()), a_S1=bool(len(cr) == 5 and cr.won.all()),
                     a_n_dec=len(d), a_n_open=int((d.counted & ~d.resolved).sum()),
                     a_resolved_after_D=int((cr.r >= x.D).sum()))
            uma_late = 0
            for c in cr.condition_id:
                if c not in resol_cache:
                    j = request_json(f"{api.DATA}/v2/resolutions", {"condition": c}, source="data-api", cache=True)
                    dd = j.get("data") or []
                    resol_cache[c] = to_unix(dd[-1].get("last_update_timestamp")) if dd else None
                ts = resol_cache[c]
                uma_late += int(ts is not None and ts >= x.D)
            r["uma_missing"] = int(sum(resol_cache[c] is None for c in cr.condition_id))
            r["uma_at_or_after_D"] = uma_late
            decs.append(d.assign(D=x.D, wallet=x.wallet, group=x.group))
        res.append(r)
        print(x.group, x.wallet[:10], pd.Timestamp(int(x.D), unit="s").date(), "server", int(x.n_res), int(x.n_won),
              "audit", r.get("a_n_res"), r.get("a_n_won"), "uma>=D", r.get("uma_at_or_after_D"), flush=True)
    out = pd.DataFrame(res)
    out.to_parquet(AUD / "a03_pit_audit.parquet", index=False)
    if decs:
        pd.concat(decs, ignore_index=True).to_parquet(AUD / "a03_decisions.parquet", index=False)
    ok = out[~out.skipped]
    ok = ok.assign(match=(ok.a_n_res == ok.n_res_s1) & (ok.a_n_won == ok.n_won_s1))
    print(ok.groupby("group").agg(n=("wallet", "size"), match=("match", "sum"), aS1=("a_S1", "sum"),
                                  uma_late=("uma_at_or_after_D", "sum"), uma_missing=("uma_missing", "sum"),
                                  res_after_D=("a_resolved_after_D", "sum")).to_string())
    print("max fill ts used minus D (must be < 0):", int((ok.max_ts_used - ok.D).max()))


if __name__ == "__main__":
    main()
