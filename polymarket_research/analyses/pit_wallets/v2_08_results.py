"""Stage 3, step 8: results tables (net ROI, CIs, benchmarks, delay decay, World Cup split, sampling bias).

Run from polymarket_research/:  python analyses/pit_wallets/v2_08_results.py
Reads v2/follower.parquet, v2/bench_prints.parquet. Writes v2/results_*.parquet and v2/results_text.txt.
Estimators (stage-3 note section 1): drop (pre-registered), ipw (fill-selection weighting), adv (adverse bound).
Weighting: "u" = each signal equal; "w" = IPW for the candidate-pool sampling (wallet weight), multiplied in.
Bootstrap: 2,000 resamples of underlying events (ue), seed 20261018.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from v2common import V2  # noqa: E402

B = 2000
RNG = np.random.default_rng(20261018)
SCREENS = ["S1", "S2", "S3", "S5"]
GROUPS = SCREENS + ["B1"]
OWN_BINS = [0.2, 0.5, 0.8, 0.95]
DELAYS = ["5s", "30s", "2m", "15m", "60m", "poll"]


def est_vectors(s: pd.DataFrame, roi_col: str, wcol: str | None) -> dict:
    """Per-row (pnl, cost) for drop / ipw / adv on one signal set at one delay. Stake 1 per signal."""
    feas = (s["status"] == "ok").to_numpy() & (s["dt"].to_numpy() < s["t_res_s"].to_numpy())
    ok = feas & s[roi_col].notna().to_numpy()
    roi = s[roi_col].fillna(0.0).to_numpy()
    p1 = (s["pay"] == 1).to_numpy()
    ob = np.digitize(np.nan_to_num(s["own_px"].to_numpy(), nan=-1.0), OWN_BINS)
    cls = p1.astype(int) * 10 + ob
    key = pd.Series(cls)
    nfe = key[feas].value_counts()
    nok = key[ok].value_counts()
    fr = (nok / nfe).reindex(key).to_numpy()
    wi = np.where(ok, 1.0 / np.where(np.isfinite(fr) & (fr > 0), fr, 1.0), 0.0)
    ww = s[wcol].to_numpy() if wcol else np.ones(len(s))
    lose_unf = feas & ~ok & ~p1
    # ipw2 = stage-2 A12 repair: every feasible loser counts at the mean ROI of filled losers (-1 if none filled);
    # filled winners are reweighted by own-price bucket; winners in buckets with no filled winner are spread over the
    # represented buckets (outcome-level fallback).
    fl = ok & ~p1
    lbar = float(np.average(roi[fl], weights=ww[fl])) if fl.any() else -1.0
    fw, okw = feas & p1, ok & p1
    w2 = np.zeros(len(s))
    if okw.any():
        bk = pd.Series(ob)
        nfe_b = bk[fw].value_counts()
        nok_b = bk[okw].value_counts()
        rep = nok_b.index
        scale = fw.sum() / max(1, nfe_b.reindex(rep).fillna(0).sum())
        wb = (nfe_b.reindex(rep) / nok_b).fillna(0) * scale
        w2 = np.where(okw, bk.map(wb).fillna(0).to_numpy(), 0.0)
    loser_feas = feas & ~p1
    ipw2_pnl = ww * (roi * w2 + lbar * loser_feas)
    ipw2_cost = ww * (w2 + loser_feas)
    return {"drop": (ww * roi * ok, ww * ok), "ipw": (ww * roi * wi, ww * wi), "ipw2": (ipw2_pnl, ipw2_cost),
            "adv": (ww * (roi * ok - lose_unf), ww * (ok | lose_unf)),
            "_fill_win": float(ok[feas & p1].mean()) if (feas & p1).any() else np.nan,
            "_fill_lose": float(ok[feas & ~p1].mean()) if (feas & ~p1).any() else np.nan,
            "_n_feas": int(feas.sum()), "_n_ok": int(ok.sum())}


def boot_counts(n: int) -> np.ndarray:
    return RNG.multinomial(n, np.full(n, 1.0 / n), size=B).astype(np.float64)


def cl(ue: pd.Series, v: np.ndarray, ues: pd.Index) -> np.ndarray:
    return pd.Series(v, index=ue.values).groupby(level=0).sum().reindex(ues, fill_value=0.0).to_numpy()


def ci(ue: pd.Series, pnl: np.ndarray, cost: np.ndarray) -> dict:
    m = cost > 0
    if not m.any():
        return {"roi": np.nan}
    ues = pd.Index(ue[m].unique())
    a, c = cl(ue[m], pnl[m], ues), cl(ue[m], cost[m], ues)
    cnt = boot_counts(len(ues))
    with np.errstate(invalid="ignore", divide="ignore"):
        bs = (cnt @ a) / (cnt @ c)
    lo, hi = np.nanpercentile(bs, [2.5, 97.5])
    return {"roi": a.sum() / c.sum(), "lo": lo, "hi": hi, "p_le0": float(np.nanmean(bs <= 0)), "n_ue": len(ues)}


def p_diff(ue1, p1, c1, ue2, p2, c2) -> float:
    m1, m2 = c1 > 0, c2 > 0
    ues = pd.Index(pd.concat([ue1[m1], ue2[m2]]).unique())
    a1, k1 = cl(ue1[m1], p1[m1], ues), cl(ue1[m1], c1[m1], ues)
    a2, k2 = cl(ue2[m2], p2[m2], ues), cl(ue2[m2], c2[m2], ues)
    cnt = boot_counts(len(ues))
    with np.errstate(invalid="ignore", divide="ignore"):
        diff = (cnt @ a1) / (cnt @ k1) - (cnt @ a2) / (cnt @ k2)
    return float(np.nanmean(diff <= 0))


def holm(ps: dict) -> dict:
    items = sorted(ps.items(), key=lambda kv: kv[1])
    out, run = {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (len(items) - i) * p))
        out[k] = run
    return out


def add_bench(fp: pd.DataFrame, bp: pd.DataFrame) -> pd.DataFrame:
    """R: mean ROI of prints in same cat & week with |cent - follower cent| <= 5, other ue. FAV: 0.70-0.95, other ue."""
    fp = fp.copy()
    fp["week"] = (fp["dt"] + 3 * 86400) // 604800
    fp["cent"] = np.clip(np.round(fp["m1_raw"] * 100), 0, 100)
    cell = bp.groupby(["cat", "week", "cent"]).agg(s=("roi", "sum"), n=("roi", "size")).reset_index()
    cell_ue = bp.groupby(["cat", "week", "cent", "ue"]).agg(s=("roi", "sum"), n=("roi", "size")).reset_index()
    q = fp.loc[fp["m1_raw"].notna(), ["sid", "delay", "category4", "week", "cent", "ue"]].rename(columns={"category4": "cat"})
    rr = []
    for width, nm in [(5, "R"), (1, "R1")]:  # R = pre-specified +-5 cents; R1 = exploratory +-1 cent (extremes)
        qq = pd.concat([q.assign(cent=q["cent"] + o) for o in range(-width, width + 1)], ignore_index=True)
        t1 = qq.merge(cell, on=["cat", "week", "cent"], how="left").groupby(["sid", "delay"])[["s", "n"]].sum()
        t2 = qq.merge(cell_ue, on=["cat", "week", "cent", "ue"], how="left").groupby(["sid", "delay"])[["s", "n"]].sum()
        r = t1 - t2
        r[f"{nm}_roi"] = r["s"] / r["n"].where(r["n"] > 0)
        r[f"{nm}_n"] = r["n"]
        rr.append(r[[f"{nm}_roi", f"{nm}_n"]])
    r = pd.concat(rr, axis=1)
    fav = bp[(bp["cent"] >= 70) & (bp["cent"] <= 95)]
    fc = fav.groupby(["cat", "week"]).agg(s=("roi", "sum"), n=("roi", "size")).reset_index()
    fcu = fav.groupby(["cat", "week", "ue"]).agg(s=("roi", "sum"), n=("roi", "size")).reset_index()
    f1 = q.merge(fc, on=["cat", "week"], how="left").set_index(["sid", "delay"])[["s", "n"]].fillna(0)
    f2 = q.merge(fcu, on=["cat", "week", "ue"], how="left").set_index(["sid", "delay"])[["s", "n"]].fillna(0)
    f = f1 - f2
    f["FAV_roi"] = f["s"] / f["n"].where(f["n"] > 0)
    fp = fp.merge(r, left_on=["sid", "delay"], right_index=True, how="left")
    fp = fp.merge(f[["FAV_roi"]], left_on=["sid", "delay"], right_index=True, how="left")
    fp["d_R"] = fp["m1_roi"] - fp["R_roi"]
    fp["d_R1"] = fp["m1_roi"] - fp["R1_roi"]
    fp["d_FAV"] = fp["m1_roi"] - fp["FAV_roi"]
    return fp


def fragility(ue: pd.Series, pnl: np.ndarray) -> tuple[float, float]:
    tot = pnl.sum()
    if tot <= 0:
        return np.nan, np.nan
    k = max(1, int(np.ceil(0.01 * (pnl != 0).sum())))
    return np.sort(pnl)[::-1][:k].sum() / tot, pd.Series(pnl, index=ue.values).groupby(level=0).sum().max() / tot


def block(fp: pd.DataFrame, g: str, delay: str, roi_col: str, wcol: str | None) -> tuple[pd.DataFrame, dict]:
    s = fp[(fp["delay"] == delay) & fp[g]].reset_index(drop=True)
    return s, est_vectors(s, roi_col, wcol) if len(s) else {}


def main() -> None:
    fp = pd.read_parquet(V2 / "follower.parquet")
    bp = pd.read_parquet(V2 / "bench_prints.parquet")
    fp = add_bench(fp, bp)
    for g in GROUPS + ["wc", "wc_period"]:
        fp[g] = fp[g].fillna(False).astype(bool)
    lines, rows = [], []
    a2 = fp[fp["delay"] == "2m"]
    lines.append(f"benchmark prints {len(bp):,} in {bp['condition_id'].nunique():,} markets; evaluable signals "
                 f"{a2['sid'].nunique():,}; status at 2m {a2['status'].value_counts().to_dict()}")
    pv = {}
    for wcol in [None, "weight"]:
        tag = "w" if wcol else "u"
        sb, eb = block(fp, "B1", "2m", "m1_roi", wcol)
        for g in GROUPS:
            s, e = block(fp, g, "2m", "m1_roi", wcol)
            if not e:
                rows.append({"group": g, "wt": tag, "n_sig": 0})
                continue
            ww = s[wcol].to_numpy() if wcol else np.ones(len(s))
            okm = e["drop"][1] > 0
            res = {"group": g, "wt": tag, "n_sig": len(s), "n_wallet": s["wallet"].nunique(), "n_feas": e["_n_feas"],
                   "n_filled": e["_n_ok"], "fill_win": e["_fill_win"], "fill_lose": e["_fill_lose"]}
            for est in ["drop", "ipw", "ipw2", "adv"]:
                r = ci(s["ue"], *e[est])
                res.update({f"{est}_{k}": v for k, v in r.items()})
            d = s[okm]
            wd = ww[okm]
            res["hit"] = float(np.average(d["pay"], weights=wd))
            res["made_money_share"] = float(np.average(d["m1_roi"] > 0, weights=wd))
            res["avg_px"] = float(np.average(d["m1_px"], weights=wd))
            res["nofee_roi"] = float(np.average(d["m1_roi_nofee"], weights=wd))
            om = d["own_roi"].notna()
            res["own_roi"] = float(np.average(d.loc[om, "own_roi"], weights=wd[om.to_numpy()])) if om.any() else np.nan
            res["cap_share_1k"] = float(np.mean(d["vol30"] >= 1000))
            for bn, col in [("R", "d_R"), ("R1", "d_R1"), ("FAV", "d_FAV")]:
                mm = okm & s[col].notna().to_numpy()
                r = ci(s["ue"], np.where(mm, s[col].fillna(0).to_numpy() * ww, 0.0), np.where(mm, ww, 0.0))
                res.update({f"{bn}_diff": r.get("roi"), f"{bn}_lo": r.get("lo"), f"{bn}_hi": r.get("hi"),
                            f"p_vs_{bn}": r.get("p_le0")})
            if g != "B1":
                res["p_vs_B1"] = p_diff(s["ue"], *e["drop"], sb["ue"], *eb["drop"])
                res["p_vs_B1_ipw"] = p_diff(s["ue"], *e["ipw"], sb["ue"], *eb["ipw"])
                res["p_screen"] = max(res["p_vs_B1"], res["p_vs_R"])
                if tag == "u":
                    pv[g] = res["p_screen"]
            res["top1pct_share"], res["top_event_share"] = fragility(s["ue"], e["drop"][0])
            rows.append(res)
    mt = pd.DataFrame(rows)
    mt["p_holm"] = np.where(mt["wt"] == "u", mt["group"].map(holm(pv)), np.nan)
    mt.to_parquet(V2 / "results_main.parquet", index=False)
    c1 = ["group", "wt", "n_sig", "n_filled", "drop_n_ue", "n_wallet", "fill_win", "fill_lose", "avg_px", "hit",
          "made_money_share", "drop_roi", "drop_lo", "drop_hi", "ipw_roi", "ipw2_roi", "ipw2_lo", "ipw2_hi", "adv_roi", "adv_hi"]
    c2 = ["group", "wt", "nofee_roi", "own_roi", "R_diff", "R_lo", "R_hi", "p_vs_R", "R1_diff", "p_vs_R1", "FAV_diff",
          "p_vs_FAV", "p_vs_B1",
          "p_vs_B1_ipw", "p_holm", "top1pct_share", "top_event_share", "cap_share_1k"]
    lines.append("PRIMARY (M1, 2-min delay, $100, +0.01, current fees) part 1:\n" + mt[[c for c in c1 if c in mt]].round(4).to_string(index=False))
    lines.append("PRIMARY part 2 (benchmarks, inference):\n" + mt[[c for c in c2 if c in mt]].round(4).to_string(index=False))
    # delay decay and size grid
    dr = []
    for g in GROUPS:
        for dn in DELAYS:
            for col in ["m1_roi", "m2_100_roi", "m2s_100_roi", "m2_500_roi", "m2_2500_roi"]:
                for wcol in [None, "weight"]:
                    s, e = block(fp, g, dn, col, wcol)
                    if not e:
                        continue
                    r = {"group": g, "delay": dn, "model": col, "wt": "w" if wcol else "u", "n_ok": e["_n_ok"],
                         "n_feas": e["_n_feas"]}
                    for est in ["drop", "ipw", "ipw2", "adv"]:
                        q = ci(s["ue"], *e[est]) if est == "drop" else {"roi": (e[est][0].sum() / max(1e-9, e[est][1].sum()))}
                        r.update({f"{est}_{k}": v for k, v in q.items()})
                    dr.append(r)
    dt = pd.DataFrame(dr)
    dt.to_parquet(V2 / "results_delay.parquet", index=False)
    for col, est in [("m1_roi", "drop"), ("m1_roi", "ipw2"), ("m1_roi", "adv"), ("m2_2500_roi", "drop"),
                     ("m2_2500_roi", "ipw2"), ("m2_100_roi", "ipw2")]:
        piv = dt[(dt["model"] == col) & (dt["wt"] == "u")].pivot(index="group", columns="delay", values=f"{est}_roi")
        lines.append(f"{col} {est} net ROI by delay (unweighted):\n" + piv[[c for c in DELAYS if c in piv]].round(4).to_string())
    # World Cup / period / category splits at the primary model
    sp = []
    for nm in ["wc", "wc_period", "non_wc_period", "sports", "crypto", "politics", "other"]:
        for g in GROUPS:
            s0 = fp[(fp["delay"] == "2m") & fp[g]]
            if nm == "wc":
                s = s0[s0["wc"]]
            elif nm == "wc_period":
                s = s0[s0["wc_period"]]
            elif nm == "non_wc_period":
                s = s0[~s0["wc_period"]]
            else:
                s = s0[s0["category4"] == nm]
            s = s.reset_index(drop=True)
            if not len(s):
                sp.append({"split": nm, "group": g, "n_sig": 0})
                continue
            e = est_vectors(s, "m1_roi", None)
            r = {"split": nm, "group": g, "n_sig": len(s), "n_ok": e["_n_ok"], "n_wallet": s["wallet"].nunique()}
            for est in ["drop", "ipw", "ipw2", "adv"]:
                q = ci(s["ue"], *e[est])
                r.update({f"{est}_{k}": v for k, v in q.items()})
            okm = e["drop"][1] > 0
            mm = okm & s["d_R"].notna().to_numpy()
            q = ci(s["ue"], np.where(mm, s["d_R"].fillna(0).to_numpy(), 0.0), mm.astype(float))
            r["R_diff"], r["p_vs_R"] = q.get("roi"), q.get("p_le0")
            sp.append(r)
    spt = pd.DataFrame(sp)
    spt.to_parquet(V2 / "results_splits.parquet", index=False)
    lines.append("Splits (M1 2m, unweighted):\n" + spt[[c for c in ["split", "group", "n_sig", "n_ok", "drop_n_ue", "n_wallet",
                 "drop_roi", "drop_lo", "drop_hi", "ipw2_roi", "adv_roi", "R_diff", "p_vs_R"] if c in spt]].round(4).to_string(index=False))
    conc = []
    for g in GROUPS:
        d = a2[a2[g] & a2["m1_raw"].notna()]
        if len(d):
            vc = d["wallet"].value_counts()
            conc.append(f"{g}: top-5 wallets {vc.head(5).sum() / len(d):.1%} of filled signals, median {vc.median():.0f}/wallet")
    lines.append("Concentration: " + "; ".join(conc))
    txt = "\n\n".join(lines)
    (V2 / "results_text.txt").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
