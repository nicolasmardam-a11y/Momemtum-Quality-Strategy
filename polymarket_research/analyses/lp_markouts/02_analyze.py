"""Family D historical: markout / maker-P&L tables, pre-registered selection on train+validation, one-shot TEST evaluation.

Usage: python analyses/lp_markouts/02_analyze.py
Outputs: analyses/lp_markouts/out/{tables.md, selection.json, cells.parquet}; data/derived/lp_markouts_cells.parquet
All prices are traded-token units (0.01 = 1c/share). Reference prices (M series, R print mid) are NOT executable;
the maker's fill price P is the actual print. Rebates use the CURRENT fee schedule (prospective).
"""
from __future__ import annotations
import glob, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.getcwd())

D = "data/derived"; IN = f"{D}/lp_markouts"; OUT = "analyses/lp_markouts/out"
os.makedirs(OUT, exist_ok=True)
B = 500
RNG = np.random.default_rng(20261018)
FEE_ALL_CATS = pd.Timestamp("2026-03-30", tz="UTC").timestamp()
PB_EDGES = [0, .02, .05, .15, .35, .65, .85, .95, .98, 1.0001]
PB_LAB = ["<2c", "2-5c", "5-15c", "15-35c", "35-65c", "65-85c", "85-95c", "95-98c", ">98c"]


def pbucket(p):
    return pd.Categorical(pd.cut(p, PB_EDGES, labels=PB_LAB, right=False), categories=PB_LAB)


def load() -> pd.DataFrame:
    meta = pd.read_parquet(f"{IN}/market_meta.parquet")
    parts = [pd.read_parquet(f) for f in sorted(glob.glob(f"{IN}/mk_*.parquet"))]
    x = pd.concat(parts, ignore_index=True)
    x["condition_id"] = x.condition_id.astype(str)
    x = x.merge(meta[["condition_id", "event_id", "split", "category", "set", "rate", "rebr", "rel_mkt",
                      "orderPriceMinTickSize"]], on="condition_id", how="left")
    P = x.P.astype(float); d = x.d.astype(float); q = x.q.astype(float)
    x["notional"] = q * P
    x["cap"] = np.where(d > 0, 1 - P, P)
    x["reb"] = x.rebr * x.rate * P * (1 - P)
    x["fee"] = x.rate * P * (1 - P)
    okM = x.M_pre.notna(); okR = x.R_pre.notna()
    x["effM"] = np.where(okM, d * (P - x.M_pre), np.nan)
    x["effR"] = np.where(okR, d * (P - x.R_pre), np.nan)
    for h in [60, 300, 3600, 86400]:
        x[f"moM{h}"] = np.where(okM, d * (x[f"M_{h}"] - x.M_pre), np.nan)
        x[f"rsM{h}"] = np.where(okM, d * (P - x[f"M_{h}"]), np.nan)
    for h in [10, 300, 3600]:
        x[f"moR{h}"] = np.where(okR, d * (x[f"R_{h}"] - x.R_pre), np.nan)
        x[f"rsR{h}"] = np.where(okR, d * (P - x[f"R_{h}"]), np.nan)
    x["rsres"] = d * (P - x.Y)
    x["netM300"] = x.rsM300 + x.reb
    x["netR300"] = x.rsR300 + x.reb
    x["netres"] = x.rsres + x.reb
    tick = x.orderPriceMinTickSize.fillna(0.01)
    x["netM300_exit"] = x.netM300 - x.fee - 0.5 * tick
    x["pb"] = pbucket(P)   # supplementary (post-hoc, declared): unwind by crossing
    # buckets (all conditioning info strictly before t)
    x["pb"] = pbucket(P)
    tt = x.ttr_h
    x["ttr"] = np.select([tt < 0, tt <= 1, tt <= 6, tt <= 24, tt <= 72, tt <= 168, tt <= 720],
                         ["past_end", "<=1h", "1-6h", "6-24h", "1-3d", "3-7d", "7-30d"], ">30d")
    n = x.notional
    x["size"] = np.select([n < 10, n < 100, n < 1000, n < 10000], ["<$10", "$10-100", "$100-1k", "$1k-10k"], ">=$10k")
    gh = x.game_h
    x["game"] = np.select([gh.isna(), gh < -24, gh < -6, gh < -1, gh < 0, gh < 1, gh < 2, gh < 4],
                          ["none", "pre>24h", "pre6-24h", "pre1-6h", "pre<=1h", "inplay0-1h", "inplay1-2h", "inplay2-4h"],
                          "inplay>4h")
    v = x.vol_1h
    x["vol"] = np.select([v.isna(), v < .005, v < .02, v < .05], ["NA", "<0.5c", "0.5-2c", "2-5c"], ">=5c")
    a = x.oi_align
    x["imb"] = np.select([a.isna(), a > .5, a > 0], ["NA", "with_strong", "with"], "against")
    x["release"] = np.where(x.rel_mkt.fillna(False) & (tt >= 0) & (tt <= 24), "release<=24h", "other")
    x["fee_era"] = np.where(x.split != "test", "pre2026", np.where(x.t < FEE_ALL_CATS, "test_preQ2", "test_fee_all"))
    x["week"] = (x.t // (7 * 86400)).astype(np.int64)
    x["all"] = "all"
    x["wq"] = queue_weight(x).astype(np.float32)
    drop = [c for c in x.columns if c.startswith(("M_", "R_"))] + ["vol_1h", "oi_align", "dt_prev", "ttr_h", "game_h",
                                                                    "rel_mkt", "orderPriceMinTickSize", "fee", "Y"]
    x = x.drop(columns=drop)
    for c in x.columns:
        if x[c].dtype == np.float64 and c not in ("t",):
            x[c] = x[c].astype(np.float32)
    for c in ["pb", "ttr", "size", "game", "vol", "imb", "release", "fee_era", "split", "category", "set", "condition_id", "event_id", "all"]:
        x[c] = x[c].astype("category")
    return x


def queue_weight(x: pd.DataFrame, qmax: float = 250.0) -> np.ndarray:
    """Back-of-queue fill weight: min(qmax, max(0, q - Dtouch)), Dtouch = median best-level shares (today's vol10k books)."""
    rows = []
    for f in [f"{D}/book_levels_2026-10-17_vol10k_r2.parquet", f"{D}/book_levels_2026-10-17_vol10k_r3.parquet"]:
        b = pd.read_parquet(f, columns=["bids_json", "asks_json"])
        for bj, aj in zip(b.bids_json, b.asks_json):
            bl = json.loads(bj) if isinstance(bj, str) else []; al = json.loads(aj) if isinstance(aj, str) else []
            if bl:
                p, s = float(bl[0][0]), float(bl[0][1]); rows += [("bid", p, s), ("ask", 1 - p, s)]
            if al:
                p, s = float(al[0][0]), float(al[0][1]); rows += [("ask", p, s), ("bid", 1 - p, s)]
    t = pd.DataFrame(rows, columns=["side", "p", "s"]); t["pb"] = pbucket(t.p)
    Dm = t.groupby(["side", "pb"], observed=False).s.median()
    Dm.to_frame("touch_shares_med").to_csv(f"{OUT}/touch_depth.csv")
    side = np.where(x.d > 0, "ask", "bid")  # taker buy lifts the ask queue of the traded token
    key = pd.MultiIndex.from_arrays([side, x.pb.astype(str)])
    Dv = Dm.reindex(key).to_numpy()
    return np.minimum(qmax, np.maximum(0.0, x.q.to_numpy(float) - Dv))


METRICS = ["effM", "moM60", "moM300", "moM3600", "moM86400", "rsM60", "rsM300", "rsM3600", "rsM86400",
           "effR", "moR10", "moR300", "moR3600", "rsR10", "rsR300",
           "rsres", "reb", "netM300", "netR300", "netres", "netM300_exit"]
BOOT = ["moR10", "moM60", "moM300", "moM3600", "moM86400", "rsM300", "netM300", "rsR300", "rsres", "netres",
        "netM300_q", "netres_q", "roc_res"]


def add_sums(x: pd.DataFrame) -> list[str]:
    cols = []
    q = x.q.astype(float)
    for m in METRICS:
        v = x[m].astype(float); ok = v.notna()
        x[f"n_{m}"] = np.where(ok, q * v, 0.0).astype(np.float32); x[f"d_{m}"] = np.where(ok, q, 0.0).astype(np.float32)
        cols += [f"n_{m}", f"d_{m}"]
    for m in ["netM300", "netres"]:
        v = x[m].astype(float); ok = v.notna()
        x[f"n_{m}_q"] = np.where(ok, x.wq * v, 0.0); x[f"d_{m}_q"] = np.where(ok, x.wq, 0.0)
        cols += [f"n_{m}_q", f"d_{m}_q"]
    ok = x.rsres.notna()
    x["n_roc_res"] = np.where(ok, q * x.rsres, 0.0); x["d_roc_res"] = np.where(ok, q * x.cap, 0.0)
    cols += ["n_roc_res", "d_roc_res"]
    keep = {"rsM300", "rsres", "moR10", "rsR300", "netM300", "netres"}
    x.drop(columns=[m for m in METRICS if m not in keep], inplace=True)
    return cols


def cells(x: pd.DataFrame, keys: list[str], cols: list[str], W: dict) -> pd.DataFrame:
    g = x.groupby(keys, observed=True)
    pt = g[cols].sum()
    out = pd.DataFrame(index=pt.index)
    for m in METRICS + ["netM300_q", "netres_q", "roc_res"]:
        out[m] = pt[f"n_{m}"] / pt[f"d_{m}"]
    out["n_trades"] = g.size(); out["n_events"] = g.event_id.nunique(); out["n_weeks"] = g.week.nunique()
    out["n_markets"] = g.condition_id.nunique()
    out["shares"] = g.q.sum(); out["notional"] = g.notional.sum()
    out["fill_shares_q"] = g.wq.sum()
    out["med_rsM300"] = g.rsM300.median(); out["med_rsres"] = g.rsres.median(); out["med_moR10"] = g.moR10.median()
    out["hold_med_h"] = g.to_close_h.median()
    out["tw_rsM300"] = g.rsM300.mean()
    # cluster bootstrap (Poisson weights) by event and by week; report wider CI
    for clus, (Wm, codes_col) in W.items():
        gs = x.groupby(keys + [codes_col], observed=True)[cols].sum()
        lo = {m: [] for m in BOOT}; hi = {m: [] for m in BOOT}
        for cell in out.index:
            sub = gs.xs(cell if isinstance(cell, tuple) else (cell,), level=list(range(len(keys))), drop_level=True) \
                if len(keys) > 1 else gs.xs(cell, level=0)
            idx = sub.index.to_numpy(np.int64)
            Wc = Wm[:, idx]
            for m in BOOT:
                num = Wc @ sub[f"n_{m}"].to_numpy(); den = Wc @ sub[f"d_{m}"].to_numpy()
                with np.errstate(invalid="ignore", divide="ignore"):
                    r = num / den
                r = r[np.isfinite(r)]
                lo[m].append(np.percentile(r, 2.5) if len(r) > 50 else np.nan)
                hi[m].append(np.percentile(r, 97.5) if len(r) > 50 else np.nan)
        for m in BOOT:
            out[f"{m}_lo_{clus}"] = lo[m]; out[f"{m}_hi_{clus}"] = hi[m]
    for m in BOOT:
        out[f"{m}_lo"] = out[[f"{m}_lo_ev", f"{m}_lo_wk"]].min(axis=1)
        out[f"{m}_hi"] = out[[f"{m}_hi_ev", f"{m}_hi_wk"]].max(axis=1)
        out = out.drop(columns=[f"{m}_lo_ev", f"{m}_lo_wk", f"{m}_hi_ev", f"{m}_hi_wk"])
    return out


ONE_WAY = ["category", "pb", "ttr", "size", "game", "vol", "imb", "release"]
TWO_WAY = [["category", "pb"], ["category", "ttr"], ["game", "pb"]]


def fmt(df: pd.DataFrame, cols: list[str], scale_c: bool = True) -> str:
    d = df[cols].copy()
    for c in cols:
        if c.startswith(("n_", "shares", "notional", "fill_")) or c in ("hold_med_h",):
            continue
        if d[c].dtype.kind == "f" and scale_c:
            d[c] = (d[c] * 100).round(3)   # cents per share
    d = d.reset_index()
    hdr = "| " + " | ".join(map(str, d.columns)) + " |\n|" + "---|" * len(d.columns) + "\n"
    return hdr + "".join("| " + " | ".join("" if pd.isna(v) else (f"{v:,.0f}" if isinstance(v, (float, np.floating)) and abs(v) >= 1000 else str(v)) for v in r) + " |\n" for r in d.itertuples(index=False))


def main():
    x = load()
    cols = add_sums(x)
    ev_codes, ev_u = pd.factorize(x.event_id.astype(str)); x["ev"] = ev_codes
    wk_codes, wk_u = pd.factorize(x.week); x["wk"] = wk_codes
    W = {"ev": (RNG.poisson(1.0, (B, len(ev_u))).astype(float), "ev"),
         "wk": (RNG.poisson(1.0, (B, len(wk_u))).astype(float), "wk")}
    print("rows", len(x), "events", len(ev_u), "weeks", len(wk_u), flush=True)
    res = {}
    # descriptive: by split, and per dimension within each split
    res["split"] = cells(x, ["split"], cols, W)
    allc = []
    for dim in ONE_WAY + ["fee_era"]:
        c = cells(x, ["split", dim], cols, W); c["dim"] = dim
        c.index = c.index.set_names(["split", "cell"]); allc.append(c)
        print("done", dim, flush=True)
    for dims in TWO_WAY:
        c = cells(x, ["split"] + dims, cols, W); c["dim"] = "x".join(dims)
        c.index = pd.MultiIndex.from_tuples([(i[0], "|".join(map(str, i[1:]))) for i in c.index], names=["split", "cell"])
        allc.append(c); print("done", dims, flush=True)
    C = pd.concat(allc)
    sp = res["split"].copy(); sp["dim"] = "all"; sp.index = pd.MultiIndex.from_tuples([(s, "all") for s in sp.index], names=["split", "cell"])
    C = pd.concat([sp, C])
    C.reset_index().to_parquet(f"{D}/lp_markouts_cells.parquet", index=False)
    # selection on train & validation (pre-registered §0.7)
    cand = C[C.dim != "fee_era"].reset_index()
    cand = cand[cand.dim != "all"]
    key = ["dim", "cell"]
    tr = cand[cand.split == "train"].set_index(key); va = cand[cand.split == "validation"].set_index(key)
    te = cand[cand.split == "test"].set_index(key)
    ok = lambda f: (f.netM300 > 0) & (f.netM300_lo > 0) & (f.n_events >= 30) & (f.n_trades >= 2000)
    n_cand = len(set(tr.index) | set(va.index))
    sel = sorted(set(tr.index[ok(tr)]) & set(va.index[ok(va)]))
    out = {"n_candidate_cells": n_cand, "selected": ["|".join(s) for s in sel]}
    ev = []
    for s in sel:
        if s not in te.index:
            ev.append({"cell": "|".join(s), "in_test": False}); continue
        r = te.loc[s]
        flags = {
            "R1_net_lo>0": bool(r.netM300_lo > 0),
            "R2_trading_lo>0": bool(r.rsM300_lo > 0) if "rsM300_lo" in r else None,
            "R3_signR_agrees": bool(np.sign(r.rsR300) == np.sign(r.rsM300)) if pd.notna(r.rsR300) else False,
            "R4_res_hi>=0": bool(not (r.rsres_hi < 0)),
            "R5_queue_net>0": bool(r.netM300_q > 0),
            "R6_size_thick": bool((r.netM300 >= 0.001) & (r.n_events >= 30) & (r.n_weeks >= 10)),
        }
        ev.append({"cell": "|".join(s), "in_test": True, **{k: (float(r[k]) if pd.notna(r[k]) else None) for k in
                   ["netM300", "netM300_lo", "netM300_hi", "rsM300", "rsM300_lo", "rsR300", "rsres", "rsres_lo", "rsres_hi",
                    "netM300_q", "netM300_q_lo", "reb", "n_events", "n_weeks", "n_trades"]}, **flags})
    out["test_eval"] = ev
    # union of selected cells in TEST
    if sel:
        mask = np.zeros(len(x), bool)
        for dim, cell in sel:
            dims = dim.split("x"); vals = cell.split("|")
            mm = x.split.eq("test").to_numpy().copy()
            for dd, vv in zip(dims, vals):
                mm &= x[dd].astype(str).eq(vv).to_numpy()
            mask |= mm
        x["union"] = np.where(mask, "union", "rest")
        U = cells(x[x.split == "test"], ["union"], cols, W)
        U.reset_index().to_parquet(f"{OUT}/union_test.parquet", index=False)
        out["union_test"] = {k: (float(v) if isinstance(v, (float, np.floating, int, np.integer)) else str(v))
                             for k, v in U.loc["union"].items()} if "union" in U.index else None
    json.dump(out, open(f"{OUT}/selection.json", "w"), indent=1, default=str)
    print("candidates", n_cand, "selected", len(sel), flush=True)


if __name__ == "__main__":
    main()
