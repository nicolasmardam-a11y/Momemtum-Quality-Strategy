"""Family F, step 4: secondary universe, shocks on the 1-min display series of all 8,000 panel markets (notes 7.3).

Display prices are NOT executable; costs (hist/book half-spread + current fee) are applied. Descriptive only.
Output: data/derived/mr_m1_returns.parquet, analyses/mean_reversion/out/04_results.json
Run: python analyses/mean_reversion/04_minute_series.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mr03", HERE / "03_outcomes.py")
mr03 = importlib.util.module_from_spec(spec); spec.loader.exec_module(mr03)
D, OUT = mr03.D, mr03.OUT
THETAS = [0.05, 0.10, 0.15]
DELAYS = [60, 120, 900]
HORIZONS = {"15m": 900, "1h": 3600, "6h": 21600, "24h": 86400}
SH = 1 << 31


def main():
    ps = pd.read_parquet(D / "panel_sample.parquet", columns=[
        "condition_id", "token_id_0", "event_id", "cluster_id", "category", "endDate", "closedTime", "ref_ts", "gameStartTime",
        "y0", "feeType", "fee_rate"])
    ps = ps[ps.token_id_0.notna() & ps.y0.notna()].drop_duplicates("token_id_0").reset_index(drop=True)
    tape = set(pd.read_parquet(D / "tapes" / "coverage.parquet").query("set == 'liquid'").condition_id)
    m = pd.read_parquet(D / "price_series_m1.parquet")
    m["code"] = m.token_id.map(pd.Series(np.arange(len(ps)), index=ps.token_id_0)).astype("float")
    m = m[m.code.notna()].drop(columns="token_id")
    m["code"] = m.code.astype(np.int64)
    m = m.sort_values(["code", "t"]).drop_duplicates(["code", "t"], keep="last")
    code, t, p = m.code.to_numpy(), m.t.to_numpy(np.int64), m.p.to_numpy(float)
    del m
    key = code * SH + t
    n = len(key)
    first = np.r_[True, code[1:] != code[:-1]]
    chg = np.r_[0, ((p[1:] != p[:-1]) & ~first[1:]).astype(np.int64)]
    cc = np.cumsum(chg)
    start = t[np.maximum.accumulate(np.where(first, np.arange(n), 0))]
    end_s = ps.endDate.map(lambda x: x.timestamp()).to_numpy()[code]
    close_s = ps.ref_ts.map(lambda x: x.timestamp()).to_numpy()[code]
    j = np.searchsorted(key, key - 300, "right") - 1
    ok = (j >= 0) & (code[np.maximum(j, 0)] == code)
    j = np.maximum(j, 0)
    lo24 = np.searchsorted(key, key - 300 - 86400, "left")
    nchg = cc[j] - cc[lo24]
    dl = p - p[j]
    cand = np.where(ok & (nchg >= 20) & (t >= start + 86400) & (t <= end_s - 3600) & (p >= 0.05) & (p <= 0.95)
                    & (np.abs(dl) >= 0.05 - 1e-9))[0]
    lo35 = np.searchsorted(key, key[cand] - 2100, "left")
    amed = np.array([np.median(p[a:b + 1]) for a, b in zip(lo35, j[cand])])
    dm = p[cand] - amed
    print(f"points {n:,}, candidates {len(cand):,}", flush=True)
    rows = []
    for theta in THETAS:
        sel = (np.sign(dl[cand]) == np.sign(dm)) & (np.abs(dl[cand]) >= theta - 1e-9) & (np.abs(dm) >= theta - 1e-9)
        idx, med = cand[sel], amed[sel]
        last_c, last_t = -1, -1e18
        for i, md in zip(idx, med):
            if code[i] == last_c and t[i] <= last_t + 3600:
                continue
            last_c, last_t = code[i], t[i]
            s = int(np.sign(p[i] - md))
            conv = (lambda x: x) if s == -1 else (lambda x: 1.0 - x)
            y0 = ps.y0.iat[code[i]]
            pay = y0 if s == -1 else 1 - y0
            for delay in DELAYS:
                e = np.searchsorted(key, key[i] + delay, "left")
                if e >= n or code[e] != code[i] or t[e] > t[i] + delay + 1800 or t[e] >= close_s[i]:
                    continue
                r = dict(code=int(code[i]), theta=theta, t_det=int(t[i]), s=s, p_det=p[i], shock=p[i] - md, delay=delay,
                         t_entry=int(t[e]), q_det=conv(p[i]), q_entry=conv(p[e]), payout=pay, close_s=close_s[i])
                for hn, h in HORIZONS.items():
                    x = np.searchsorted(key, key[e] + h, "left")
                    if x < n and code[x] == code[i] and t[x] < close_s[i]:
                        r[f"q_{hn}"], r[f"t_{hn}"], r[f"res_{hn}"] = conv(p[x]), int(t[x]), False
                    else:
                        r[f"q_{hn}"], r[f"t_{hn}"], r[f"res_{hn}"] = pay, int(close_s[i]), True
                r["q_res"], r["t_res"], r["res_res"] = pay, int(close_s[i]), True
                rows.append(r)
    X = pd.DataFrame(rows)
    X = X.join(ps.drop(columns=["token_id_0"]), on="code")
    X["split_t"] = mr03.np.where(X.t_det < mr03.pd.Timestamp("2025-07-01", tz="UTC").timestamp(), "train",
                                 np.where(X.t_det < pd.Timestamp("2026-01-01", tz="UTC").timestamp(), "validation",
                                          np.where(X.t_det < pd.Timestamp("2026-10-16", tz="UTC").timestamp(), "test", "after")))
    X = X[X.split_t != "after"].reset_index(drop=True)
    X["week"] = pd.to_datetime(X.t_det, unit="s", utc=True).dt.strftime("%G-W%V")
    X["tape_market"] = X.condition_id.isin(tape)
    hs = mr03.HalfSpread({})
    cat = X.category.fillna("other").str.lower()
    rate = np.where(X.feeType.isin(mr03.CURRENT_FEE_TYPES) & X.fee_rate.notna(), X.fee_rate,
                    cat.map(mr03.fees.TAKER_RATE).fillna(0.05))
    gst = X.gameStartTime.map(lambda x: x.timestamp() if pd.notna(x) else np.nan).to_numpy()
    sports = cat.eq("sports").to_numpy()
    ref = X.close_s.to_numpy()
    hs_e, _ = hs(X.split_t, cat, X.q_entry.to_numpy(), (ref - X.t_entry) / 3600, sports & (X.t_entry.to_numpy() >= gst))
    out = []
    for ex in ["15m", "1h", "6h", "24h", "res"]:
        qx, tx, res = X[f"q_{ex}"].to_numpy(), X[f"t_{ex}"].to_numpy(float), X[f"res_{ex}"].to_numpy(bool)
        hx, _ = hs(X.split_t, cat, qx, (ref - tx) / 3600, sports & (tx >= gst))
        hx = np.where(res, 0.0, hx)
        pe = np.clip(X.q_entry.to_numpy() + hs_e, 0.001, 0.999); ce = pe + rate * pe * (1 - pe)
        px = np.clip(qx - hx, 0, 1); pxn = np.where(res, qx, px - rate * px * (1 - px))
        Y = X[["code", "condition_id", "cluster_id", "event_id", "week", "split_t", "theta", "delay", "category", "tape_market",
               "q_det", "q_entry", "shock", "t_entry"]].copy()
        Y["exit"] = ex; Y["q_x"] = qx; Y["at_res"] = res; Y["hs_e"] = hs_e
        Y["pnl_gross"] = qx - X.q_entry.to_numpy(); Y["ret_gross"] = Y.pnl_gross / X.q_entry.to_numpy()
        Y["pnl_net"] = pxn - ce; Y["cost_e"] = ce; Y["ret_net"] = Y.pnl_net / ce
        Y["hold_d"] = (tx - X.t_entry.to_numpy()) / 86400
        out.append(Y)
    Y = pd.concat(out, ignore_index=True)
    Y.to_parquet(D / "mr_m1_returns.parquet", index=False)
    res = []
    for (th, d, ex), g in Y.groupby(["theta", "delay", "exit"]):
        for sp in ["train", "validation", "test"]:
            gg = g[g.split_t == sp]
            if len(gg) < 10:
                continue
            s = mr03.summarize(gg, alpha=0.001)
            nt = gg[~gg.tape_market]
            res.append(dict(theta=th, delay=d, exit=ex, split=sp, n=s["n"], cl=s["n_clusters"], gross=s["mean_gross"],
                            net=s["mean"], med=s["median"], lo999=s.get("lo"), hi999=s.get("hi"),
                            gross_c=float(gg.pnl_gross.mean() * 100), net_c=float(gg.pnl_net.mean() * 100),
                            rev_det_c=float(((gg.q_x - gg.q_det) * 100).mean()),
                            net_nontape=float(nt.ret_net.mean()) if len(nt) else np.nan, n_nontape=int(len(nt)),
                            drop5=mr03.drop_top_clusters(gg) if len(gg) > 10 else np.nan))
    Rz = pd.DataFrame(res)
    (OUT / "04_results.json").write_text(json.dumps(Rz.round(5).to_dict("records"), indent=1, default=float))
    print(Rz[Rz.split == "test"].drop(columns=["split"]).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
