"""Stage 2, step 17: follower returns, benchmarks, information tests, inference and the pre-registered rejection
criteria (pre-registration sections 7-11, addendum A10).

Run from polymarket_research/:  python analyses/pit_wallets/17_evaluate.py [confirm|bench|grid|all]
Outputs in data/derived/pit_wallets/results/:
  confirmatory.parquet  28-hypothesis family (+ B1 rows) at the pre-registered model, every split
  bench_compare.parquet signal vs (i) matched random prints, B2 cells, (ii) favourite rule, (iv) T-bill, info tests
  grid.parquet          exploratory grid (type x screen x delay x size x slippage x fee x exit), every split
  grid_rc.json          Holm over the test grid, White reality check of the best variant, val-selected variant
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from evalib import (B1, DELAYS, ESTS, FEE_RATE, FEES, MODELS, OUT, RES, SCREENS, SLIPS, SPLITS,  # noqa
                    boot_diff_joint, boot_ratio, ci, codes_of, entry, est_vectors, fee_frac, holm, load_signals,
                    p_centred, roi_exit, roi_hold, week_of)
from scipy.stats import norm

SEED = 20261018
FAMILY = [(t, sc) for sc in SCREENS for t in ["P", "F1", "F2"]] + [("CL", "CL")]


# ----------------------------------------------------------------------------------------- benchmark prints

def load_bench() -> pd.DataFrame:
    bp = pd.read_parquet(OUT / "bench_prints.parquet")
    tm = pd.read_parquet(OUT / "token_meta_pit.parquet",
                         columns=["k", "underlying_key", "category", "p", "market_clean", "has_meta", "r"])
    n0 = len(bp)
    bp = bp.merge(tm, on="k", how="inner")
    bp = bp[bp.has_meta.fillna(False).astype(bool) & bp.market_clean.fillna(False).astype(bool) & (bp.r > 0) & (bp.ts < bp.r)].copy()
    bp["p"] = bp.p.astype(float)
    bp["week"] = week_of(bp.ts)
    bp["pxi"] = np.round(bp.px * 1e4).astype(np.int64)
    bp["dec"] = np.minimum(9, np.floor(bp.px * 10)).astype(int)
    bp["fee_rate"] = bp.category.map(FEE_RATE).fillna(0.05)
    bp["underlying_key"] = bp.underlying_key.astype(str)
    bp = bp.sort_values(["category", "week", "pxi"]).reset_index(drop=True)
    print(f"bench prints {n0} -> clean with metadata, before t_res: {len(bp)}")
    return bp


def bench_roi(bp, slip_total, fee):
    e = np.minimum(0.999, bp.px.values + slip_total)
    ff = 0.0 if fee == "hist" else bp.fee_rate.values * (1 - e)
    return bp.p.values / e - 1 - ff


def matched_sums(sig: pd.DataFrame, bp: pd.DataFrame, vals: np.ndarray, win=500):
    """Sum and count of bench values over prints in the same category and ISO week with |px - raw| <= 0.05 and a
    different underlying event. sig needs category, week, underlying_key, rawi (price x 1e4) and a RangeIndex."""
    k = vals.shape[1]
    S = np.zeros((len(sig), k)); N = np.zeros(len(sig))
    cs = np.vstack([np.zeros((1, k)), np.cumsum(vals, axis=0)])
    grp = bp.groupby(["category", "week"]).indices
    pxi = bp.pxi.values
    for key, idx in sig.groupby(["category", "week"]).indices.items():
        if key not in grp:
            continue
        g = grp[key]; a, b = g[0], g[-1] + 1
        px = pxi[a:b]
        r = sig.rawi.values[idx]
        lo = a + np.searchsorted(px, r - win, "left"); hi = a + np.searchsorted(px, r + win, "right")
        S[idx] = cs[hi] - cs[lo]; N[idx] = hi - lo
    m = sig[["category", "week", "underlying_key", "rawi"]].reset_index().merge(
        bp[["category", "week", "underlying_key", "pxi"]].reset_index().rename(columns={"index": "bi"}),
        on=["category", "week", "underlying_key"])
    m = m[(m.pxi - m.rawi).abs() <= win]
    if len(m):
        ii = m["index"].values; bi = m.bi.values
        np.subtract.at(S, ii, vals[bi]); np.subtract.at(N, ii, 1)
    return S, N


def tbill():
    t = pd.read_csv(OUT.parents[1] / "raw" / "fred" / "DTB3.csv")
    t.columns = ["date", "rate"]
    t["rate"] = pd.to_numeric(t.rate, errors="coerce")
    t = t.dropna()
    t["ts"] = [int(pd.Timestamp(x, tz="UTC").timestamp()) for x in t.date]
    return t.sort_values("ts")


def tbill_ret(tb, t_in, r):
    i = np.searchsorted(tb.ts.values, t_in, "right") - 1
    rate = tb.rate.values[np.clip(i, 0, len(tb) - 1)] / 100
    return rate * np.maximum(0, r - t_in) / (365 * 86400), rate


# ----------------------------------------------------------------------------------------- per-set statistics

def set_stats(g, ok, roi, raw, B=2000, seed=SEED):
    """g: rows of one (stype, screen, split); ok/roi/raw arrays aligned with g."""
    f = ok.astype(bool)
    n, nf = len(g), int(f.sum())
    out = dict(n_sig=n, n_fill=nf, fill_rate=nf / n if n else np.nan,
               n_events=int(g.underlying_key[f].nunique()), n_wallets=int(g.wallet[f].replace("", np.nan).nunique()))
    if nf == 0:
        return out, None
    pnl = 100 * roi[f]; cost = np.full(nf, 100.0)
    ev = g.underlying_key.values[f]; wk = g.week.values[f]
    ce, _ = codes_of(ev); cw, _ = codes_of(wk)
    be = boot_ratio(ce, pnl, cost, B, seed); bw = boot_ratio(cw, pnl, cost, B, seed + 1)
    est = pnl.sum() / cost.sum()
    tot = pnl.sum()
    srt = np.sort(pnl)[::-1]
    top1 = srt[: max(1, int(np.ceil(0.01 * nf)))].sum()
    evp = pd.Series(pnl).groupby(ev).sum()
    out.update(roi=est, ci_lo=ci(be)[0], ci_hi=ci(be)[1], ciw_lo=ci(bw)[0], ciw_hi=ci(bw)[1],
               p0=p_centred(be, est), pnl=tot, hit=float(g.p.values[f].mean()), made_money=float((pnl > 0).mean()),
               edge=float((g.p.values[f] - raw[f]).mean()), mean_px=float(raw[f].mean()),
               top1_share=float(top1 / tot) if tot > 0 else np.nan,
               top_event_share=float(evp.max() / tot) if tot > 0 else np.nan,
               top5_event_share=float(evp.sort_values(ascending=False).head(5).sum() / tot) if tot > 0 else np.nan,
               cap1000=float((g.vol60_120.values[f] >= 100).mean()))
    return out, dict(ce=ev, pnl=pnl, cost=cost)


def confirm(s: pd.DataFrame, bp: pd.DataFrame):
    """Pre-registered model: first print at t + 2 min + 0.01, $100, hold, historical fee (and current-fee stress)."""
    rows = []
    for fee in FEES:
        ok, roi, raw, e, t_in = roi_hold(s, "fp", "120", 0.0, fee)
        s_ok, s_roi, s_raw = ok, roi, raw
        # B2 cell means (month, category, price decile) with the same +0.01 slippage and fee
        bp["rb"] = bench_roi(bp, 0.01, fee)
        cell = bp.groupby(["ym", "category", "dec"]).rb.mean()
        dec = np.minimum(9, np.floor(raw * 10)).astype(int)
        key = pd.MultiIndex.from_arrays([s.ym.values, s.category.values, dec])
        b2 = cell.reindex(key).values
        for split in SPLITS:
            for (t, sc) in FAMILY + [(t, B1) for t in ["P", "F1", "F2"]]:
                m = ((s.stype == t) & (s.screen == sc) & (s.split == split)).values
                if not m.any():
                    continue
                g = s[m]
                st, bt = set_stats(g, s_ok[m], s_roi[m], s_raw[m])
                st.update(stype=t, screen=sc, split=split, fee=fee)
                own = g.first_price.values
                okown = np.isfinite(own) & (own > 0)
                st["roi_own_price_B3"] = float((g.p.values[okown] / own[okown] - 1).mean()) if okown.any() else np.nan
                st["edge_own_B3"] = float((g.p.values[okown] - own[okown]).mean()) if okown.any() else np.nan
                st["med_own_px"] = float(np.median(own[okown])) if okown.any() else np.nan
                evs = est_vectors(g, s_ok[m], s_roi[m], "120")
                cg, _ = codes_of(g.underlying_key.values)
                st.update(fill_p1=evs["_fill_p1"], fill_p0=evs["_fill_p0"], ipw_cover=evs["_ipw_cover"])
                for en in ("ipw", "adv"):
                    pn, co = evs[en]
                    if co.sum() > 0:
                        bb = boot_ratio(cg, pn, co, 2000, SEED + 11)
                        st[f"roi_{en}"] = pn.sum() / co.sum()
                        st[f"ci_lo_{en}"], st[f"ci_hi_{en}"] = ci(bb)
                        st[f"p0_{en}"] = p_centred(bb, st[f"roi_{en}"])
                if sc != B1:
                    bt_ = "P" if t == "CL" else t
                    mball = ((s.stype == bt_) & (s.screen == B1) & (s.split == split)).values
                    if mball.any():
                        gb = s[mball]
                        evb = est_vectors(gb, s_ok[mball], s_roi[mball], "120")
                        allc, nc = codes_of(np.concatenate([g.underlying_key.values, gb.underlying_key.values]))
                        ca, cb = allc[: len(g)], allc[len(g):]
                        for en in ("ipw", "adv"):
                            pa, coa = evs[en]; pb_, cob = evb[en]
                            if coa.sum() > 0 and cob.sum() > 0:
                                dd_ = boot_diff_joint(ca, pa, coa, cb, pb_, cob, nc, 2000, SEED + 13)
                                est_ = pa.sum() / coa.sum() - pb_.sum() / cob.sum()
                                st[f"roi_B1_{en}"] = pb_.sum() / cob.sum()
                                st[f"d_B1_{en}"], st[f"p_B1_{en}"] = est_, p_centred(dd_, est_)
                if bt is not None and sc != B1:
                    bt_ = "P" if t == "CL" else t
                    mb = ((s.stype == bt_) & (s.screen == B1) & (s.split == split)).values & s_ok
                    if mb.any():
                        evb = s.underlying_key.values[mb]
                        allc, nc = codes_of(np.concatenate([bt["ce"], evb]))
                        ca, cb = allc[: len(bt["ce"])], allc[len(bt["ce"]):]
                        pb = 100 * s_roi[mb]
                        d = boot_diff_joint(ca, bt["pnl"], bt["cost"], cb, pb, np.full(len(pb), 100.0), nc,
                                            2000, SEED + 7)
                        est = bt["pnl"].sum() / bt["cost"].sum() - pb.sum() / (100 * len(pb))
                        st.update(roi_B1=pb.sum() / (100 * len(pb)), d_B1=est, p_B1=p_centred(d, est))
                    f = s_ok[m]
                    b2g = b2[m][f]
                    have = np.isfinite(b2g)
                    dd = s_roi[m][f][have] - b2g[have]
                    if have.any():
                        c2, _ = codes_of(g.underlying_key.values[f][have])
                        bd = boot_ratio(c2, dd, np.ones(len(dd)), 2000, SEED + 9)
                        st.update(roi_B2=float(b2g[have].mean()), d_B2=float(dd.mean()), p_B2=p_centred(bd, dd.mean()),
                                  b2_missing=int((~have).sum()))
                rows.append(st)
        print(f"confirm fee={fee} done", flush=True)
    c = pd.DataFrame(rows)
    c["p_iu"] = c[["p_B1", "p_B2"]].max(axis=1)
    c["holm"] = np.nan
    for fee in FEES:
        m = (c.split == "test") & (c.fee == fee) & (c.screen != B1)
        c.loc[m, "holm"] = holm(c.loc[m, "p_iu"].values)
    # rejection criteria on test (historical fee = pre-registered fee (a))
    out = []
    for (t, sc) in FAMILY:
        te = c[(c.stype == t) & (c.screen == sc) & (c.split == "test") & (c.fee == "hist")]
        va = c[(c.stype == t) & (c.screen == sc) & (c.split == "val") & (c.fee == "hist")]
        if te.empty:
            continue
        te = te.iloc[0]
        r1 = not (te.get("roi", np.nan) > 0 and te.get("ci_lo", np.nan) > 0)
        r2 = not (te.get("holm", np.nan) < 0.05)
        r3 = te.get("n_events", 0) < 100
        r4 = bool(te.get("pnl", 0) > 0 and (te.get("top1_share", 0) > 0.5 or te.get("top_event_share", 0) > 0.5))
        r5 = not (len(va) and va.iloc[0].get("roi", np.nan) > 0)
        verdict = ("edge" if not (r1 or r2 or r3 or r4 or r5) else
                   "inconclusive (<100 events)" if r3 and not (r1 or r2) else "rejected")
        out.append(dict(stype=t, screen=sc, c1_roi_ci=r1, c2_holm_vs_B1_B2=r2, c3_lt100_events=r3,
                        c4_fragile=r4, c5_not_pos_val=r5, verdict=verdict))
    crit = pd.DataFrame(out)
    return c, crit


# ----------------------------------------------------------------------------------------- benchmarks + info tests

KEY_MODELS = [("fp", "120", 0.0), ("v500", "120", 0.0), ("v2500", "120", 0.0)]


def bench_compare(s: pd.DataFrame, bp: pd.DataFrame):
    import statsmodels.api as sm
    tb = tbill()
    rng = np.random.default_rng(SEED)
    rows = []
    sets = [(t, sc) for t in ["P", "F1", "F1b", "F2", "ADD"] for sc in SCREENS + [B1]] + [("CL", "CL")]
    for model, d, slip in KEY_MODELS:
        st_tot = (0.01 if model == "fp" else 0.0) + slip
        vals = np.column_stack([bench_roi(bp, st_tot, "hist"), bench_roi(bp, st_tot, "cur"),
                                bp.p.values - bp.px.values])
        fav = (bp.px >= 0.70) & (bp.px <= 0.95)
        favcell = pd.DataFrame(vals[fav.values], columns=["h", "c", "e"]).groupby(
            [bp.category.values[fav.values], bp.week.values[fav.values]]).mean()
        cellB2 = pd.DataFrame(vals, columns=["h", "c", "e"]).groupby([bp.ym.values, bp.category.values,
                                                                      bp.dec.values]).mean()
        ok, roi_h, raw, e, t_in = roi_hold(s, model, d, slip, "hist")
        roi_c = roi_h - np.where(ok, fee_frac(s, e, "cur"), 0)
        tbr, _ = tbill_ret(tb, t_in, s.r.values)
        sig = pd.DataFrame({"category": s.category.values, "week": s.week.values,
                            "underlying_key": s.underlying_key.astype(str).values,
                            "rawi": np.round(raw * 1e4).astype(np.int64)})
        S, N = matched_sums(sig, bp, vals)
        mi = np.where(N[:, None] > 0, S / np.maximum(N, 1)[:, None], np.nan)
        fk = pd.MultiIndex.from_arrays([s.category.values, s.week.values])
        fv = favcell.reindex(fk).values
        dec = np.minimum(9, np.floor(raw * 10)).astype(int)
        b2 = cellB2.reindex(pd.MultiIndex.from_arrays([s.ym.values, s.category.values, dec])).values
        for split in SPLITS:
            for (t, sc) in sets:
                ms = ((s.stype == t) & (s.screen == sc) & (s.split == split)).values
                m = ms & ok
                if m.sum() == 0:
                    continue
                g = s[m]
                wfull = np.zeros(len(s))
                wfull[ms] = est_vectors(s[ms], ok[ms], roi_h[ms], d)["ipw"][1] / 100.0
                wv = wfull[m]
                ev, _ = codes_of(g.underlying_key.values)
                r = dict(model=model, delay=d, slip=slip, stype=t, screen=sc, split=split, n_fill=int(m.sum()),
                         n_events=int(ev.max() + 1))
                for fee, rv, col in [("hist", roi_h, 0), ("cur", roi_c, 1)]:
                    x = rv[m]
                    r[f"roi_{fee}"] = float(x.mean())
                    for nm, bm in [("i", mi[m, col]), ("fav", fv[m, col]), ("B2", b2[m, col])]:
                        h = np.isfinite(bm)
                        if h.sum() == 0:
                            continue
                        dd = x[h] - bm[h]
                        bd = boot_ratio(ev[h], dd, np.ones(h.sum()), 1000, SEED + 3)
                        r[f"roi_{nm}_{fee}"] = float(bm[h].mean())
                        r[f"d_{nm}_{fee}"] = float(dd.mean())
                        lo, hi = ci(bd)
                        r[f"d_{nm}_{fee}_lo"], r[f"d_{nm}_{fee}_hi"] = lo, hi
                        r[f"cov_{nm}"] = float(h.mean())
                        bw = boot_ratio(ev[h], wv[h] * dd, wv[h], 1000, SEED + 4)
                        r[f"dw_{nm}_{fee}"] = float((wv[h] * dd).sum() / wv[h].sum())
                        r[f"dw_{nm}_{fee}_lo"], r[f"dw_{nm}_{fee}_hi"] = ci(bw)
                    r[f"roiw_{fee}"] = float((wv * x).sum() / wv.sum())
                # (iv) T-bill over the same holding periods
                r["tbill_ret"] = float(tbr[m].mean())
                r["hold_days_med"] = float(np.median((g.r.values - t_in[m]) / 86400))
                r["roi_hist_minus_tbill"] = r["roi_hist"] - r["tbill_ret"]
                # information test 1: edge = payoff - follower price vs matched prints' payoff - print price
                edge = g.p.values - raw[m]
                be = mi[m, 2]
                h = np.isfinite(be)
                r["edge_sig"] = float(edge.mean())
                if h.any():
                    dd = edge[h] - be[h]
                    bd = boot_ratio(ev[h], dd, np.ones(h.sum()), 1000, SEED + 5)
                    r["edge_match"] = float(be[h].mean()); r["d_edge"] = float(dd.mean())
                    r["d_edge_lo"], r["d_edge_hi"] = ci(bd)
                    r["p_edge"] = p_centred(bd, dd.mean())
                    bw = boot_ratio(ev[h], wv[h] * dd, wv[h], 1000, SEED + 6)
                    r["dw_edge"] = float((wv[h] * dd).sum() / wv[h].sum())
                    r["dw_edge_lo"], r["dw_edge_hi"] = ci(bw)
                # information test 2 (primary model only): logit(outcome) ~ logit(price) + signal, event clusters
                if model == "fp" and m.sum() >= 30 and t in ("P", "F1", "F1b", "F2", "CL", "ADD"):
                    r.update(logit_test(g, raw[m], sig[m].reset_index(drop=True), bp, rng, sm))
                rows.append(r)
        print(f"bench model={model} done", flush=True)
    return pd.DataFrame(rows)


def logit_test(g, raw, sig, bp, rng, sm, per=3, win=500):
    grp = bp.groupby(["category", "week"]).indices
    pxi = bp.pxi.values
    picks_b, picks_s = [], []
    for key, idx in sig.groupby(["category", "week"]).indices.items():
        if key not in grp:
            continue
        gg = grp[key]; a, b = gg[0], gg[-1] + 1
        r = sig.rawi.values[idx]
        lo = a + np.searchsorted(pxi[a:b], r - win, "left"); hi = a + np.searchsorted(pxi[a:b], r + win, "right")
        for _ in range(per):
            n = hi - lo
            okk = n > 0
            j = lo[okk] + np.floor(rng.random(okk.sum()) * n[okk]).astype(int)
            picks_b.append(j); picks_s.append(idx[okk])
    if not picks_b:
        return {}
    jb = np.concatenate(picks_b); js = np.concatenate(picks_s)
    keep = bp.underlying_key.values[jb] != sig.underlying_key.values[js]
    jb = jb[keep]
    y = np.concatenate([g.p.values, bp.p.values[jb]])
    px = np.clip(np.concatenate([raw, bp.px.values[jb]]), 0.005, 0.995)
    dsig = np.concatenate([np.ones(len(raw)), np.zeros(len(jb))])
    clus, _ = codes_of(np.concatenate([g.underlying_key.astype(str).values, bp.underlying_key.values[jb]]))
    X = sm.add_constant(np.column_stack([np.log(px / (1 - px)), dsig]))
    try:
        fit = sm.GLM(y, X, family=sm.families.Binomial()).fit(cov_type="cluster", cov_kwds={"groups": clus})
        return dict(lg_n=len(y), lg_b_logitp=float(fit.params[1]), lg_b_sig=float(fit.params[2]),
                    lg_se_sig=float(fit.bse[2]), lg_p_sig_1s=float(1 - __import__("scipy").stats.norm.cdf(
                        fit.params[2] / fit.bse[2])))
    except Exception as ex:  # noqa: BLE001
        return dict(lg_err=str(ex)[:80])


# ----------------------------------------------------------------------------------------- exploratory grid

def grid(s: pd.DataFrame, B=1000):
    sets = [(t, sc) for t in ["P", "F1", "F1b", "F2", "ADD"] for sc in SCREENS + [B1]] + [("CL", "CL")]
    variants = [(d, mo, sl, fe, False) for d in DELAYS for mo in MODELS for sl in SLIPS for fe in FEES]
    exits = [("120", mo, sl, fe, True) for mo in MODELS for sl in SLIPS for fe in FEES]
    rows, boots = [], {}
    for split in SPLITS:
        ss = s[s.split == split].reset_index(drop=True)
        ce_all, E = codes_of(ss.underlying_key.values)
        rng = np.random.default_rng(SEED + SPLITS.index(split))
        Wc = [rng.poisson(1.0, size=(100, E)).astype(np.float32) for _ in range(B // 100)]
        for (t, sc) in sets:
            m = ((ss.stype == t) & (ss.screen == sc)).values
            if not m.any():
                continue
            g = ss[m].reset_index(drop=True)
            evc = ce_all[m]
            uev, inv = np.unique(evc, return_inverse=True)
            vs = variants + (exits if t in ("P", "F1b") else [])
            vx = [(v_, en) for v_ in vs for en in ESTS]
            Pm = np.zeros((len(uev), len(vx)), dtype=np.float32); Cm = np.zeros_like(Pm)
            meta = []
            for j0, (d, mo, sl, fe, ex) in enumerate(vs):
                if ex:
                    ok, roi, _used = roi_exit(g, mo, sl, fe)
                else:
                    ok, roi, raw, e, t_in = roi_hold(g, mo, d, sl, fe)
                vec = est_vectors(g, ok, roi, d)
                nf = int(ok.sum())
                for k_, en in enumerate(ESTS):
                    j = j0 * len(ESTS) + k_
                    Pm[:, j] = np.bincount(inv, weights=vec[en][0], minlength=len(uev))
                    Cm[:, j] = np.bincount(inv, weights=vec[en][1], minlength=len(uev))
                    meta.append(dict(split=split, stype=t, screen=sc, delay=d, model=mo, slip=sl, fee=fe, exit=ex,
                                     est=en, n_sig=len(g), n_fill=nf,
                                     n_events=int(len(np.unique(inv[ok]))) if nf else 0,
                                     fill_p1=vec["_fill_p1"], fill_p0=vec["_fill_p0"],
                                     roi=float(Pm[:, j].sum() / Cm[:, j].sum()) if Cm[:, j].sum() > 0 else np.nan))
            bt = []
            for W in Wc:
                w = W[:, uev]
                num, den = w @ Pm, w @ Cm
                bt.append(np.where(den > 0, num / np.where(den > 0, den, 1), np.nan))
            bt = np.vstack(bt)
            for j, mm in enumerate(meta):
                b = bt[:, j]
                mm["se"] = float(np.nanstd(b)) if mm["n_fill"] else np.nan
                mm["ci_lo"], mm["ci_hi"] = ci(b) if mm["n_fill"] else (np.nan, np.nan)
                mm["p0"] = p_centred(b, mm["roi"]) if mm["n_fill"] else np.nan
                mm["p_norm"] = float(1 - norm.cdf(mm["roi"] / mm["se"])) if mm["n_fill"] and mm["se"] > 0 else np.nan
                rows.append(mm)
                if split != "train":
                    boots[(split, t, sc, *vx[j][0], vx[j][1])] = b
        print(f"grid {split} done ({len(rows)} rows)", flush=True)
    G = pd.DataFrame(rows)
    rc = {}
    G["holm_test"] = np.nan
    for en in ESTS:
        fam = (G.split == "test") & (G.screen != B1) & (G.n_fill > 0) & (G.est == en)
        G.loc[fam, "holm_test"] = holm(G.loc[fam, "p_norm"].values)
        r_ = {"n_variants_defined": int(((G.split == "test") & (G.screen != B1) & (G.est == en)).sum()),
              "n_variants_tested_test": int(fam.sum()), "n_holm_sig_005": int((G.loc[fam, "holm_test"] < 0.05).sum()),
              "n_raw_pnorm_lt_005": int((G.loc[fam, "p_norm"] < 0.05).sum()),
              "n_raw_pboot_lt_005": int((G.loc[fam, "p0"] < 0.05).sum())}
        for split in ["test", "val"]:
            el = (G.split == split) & (G.screen != B1) & (G.n_events >= 30) & (G.se > 0) & (G.est == en)
            sub = G[el].reset_index()
            keys = [(split, r.stype, r.screen, r.delay, r.model, r.slip, r.fee, r.exit, en) for r in sub.itertuples()]
            Bm = np.column_stack([boots[k] for k in keys])
            roi = sub.roi.values; se = sub.se.values
            tstat = roi / se
            best = int(np.nanargmax(tstat)); bestraw = int(np.nanargmax(roi))
            Tst = np.nanmax((Bm - roi) / se, axis=1); Traw = np.nanmax(Bm - roi, axis=1)
            cols = ["stype", "screen", "delay", "model", "slip", "fee", "exit", "n_fill", "n_events", "roi", "ci_lo",
                    "ci_hi", "fill_p1", "fill_p0"]
            r_[split] = dict(n_eligible=len(sub), best_studentized=sub.iloc[best][cols].to_dict(),
                             rc_p_studentized=float((np.sum(Tst >= tstat[best]) + 1) / (len(Tst) + 1)),
                             best_raw=sub.iloc[bestraw][cols].to_dict(),
                             rc_p_raw=float((np.sum(Traw >= roi[bestraw]) + 1) / (len(Traw) + 1)),
                             share_positive=float((roi > 0).mean()))
        v = r_["val"]["best_studentized"]
        te = G[(G.split == "test") & (G.stype == v["stype"]) & (G.screen == v["screen"]) & (G.delay == v["delay"])
               & (G.model == v["model"]) & (G.slip == v["slip"]) & (G.fee == v["fee"]) & (G.exit == v["exit"])
               & (G.est == en)]
        r_["val_selected_on_test"] = te[["n_fill", "n_events", "roi", "ci_lo", "ci_hi", "p0", "p_norm"]].iloc[0].to_dict() \
            if len(te) else None
        rc[en] = r_
    return G, rc


def main(what):
    RES.mkdir(exist_ok=True)
    t = time.time()
    s, info = load_signals()
    print("signals", info, len(s), flush=True)
    bp = load_bench() if what in ("confirm", "bench", "all") else None
    if what in ("confirm", "all"):
        c, crit = confirm(s, bp)
        c.to_parquet(RES / "confirmatory.parquet", index=False)
        crit.to_parquet(RES / "criteria.parquet", index=False)
        print(crit.verdict.value_counts().to_dict(), f"{time.time() - t:.0f}s", flush=True)
    if what in ("bench", "all"):
        bc = bench_compare(s, bp)
        bc.to_parquet(RES / "bench_compare.parquet", index=False)
        print("bench rows", len(bc), f"{time.time() - t:.0f}s", flush=True)
    if what in ("grid", "all"):
        G, rc = grid(s)
        G.to_parquet(RES / "grid.parquet", index=False)
        (RES / "grid_rc.json").write_text(json.dumps(rc, indent=1, default=str))
        print(json.dumps(rc, default=str)[:1500], f"{time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
