"""Family F, step 3: costs, tradable reversal returns, pre-registered tests (notes section 0.3-0.6).

Inputs: mr_shocks.parquet, mr_trades.parquet (01), mr_siblings.parquet (02), effective_spread_hist.parquet,
        spread_model.parquet (panel 5.1-5.3), panel_sample.parquet (feesEnabled).
Outputs: data/derived/mr_returns.parquet (one row per entered trade x exit, all cost variants),
         analyses/mean_reversion/out/03_results.json, out/03_tables.md (compact tables).
Run: python analyses/mean_reversion/03_outcomes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import fees  # noqa: E402

D = ROOT / "data" / "derived"
OUT = Path(__file__).resolve().parent / "out"
B = 2000
RNG = np.random.default_rng(20261017)
PB_EDGES = [0, .02, .05, .15, .35, .65, .85, .95, .98, 1.0001]
PB_LABELS = ['<2c', '2-5c', '5-15c', '15-35c', '35-65c', '65-85c', '85-95c', '95-98c', '>98c']
CURRENT_FEE_TYPES = {"sports_fees_v3", "crypto_fees_v2", "weather_fees", "finance_prices_fees", "sports_fees_nfl_cfb_oct26",
                     "culture_fees", "mentions_fees", "politics_fees", "tech_fees", "economics_fees", "general_fees",
                     "zero_fees"}
EXITS = ["15m", "1h", "6h", "24h", "res"]


def pb(x):
    return pd.cut(pd.Series(x), PB_EDGES, labels=PB_LABELS, right=False).astype(object).to_numpy()


def ttr_b(ttr_h, in_play):
    lab = np.select([ttr_h <= 1, ttr_h <= 6, ttr_h <= 24, ttr_h <= 72], ['<=1h', '1-6h', '6-24h', '1-3d'], 'gt3d')
    return np.where(in_play, 'in_play', lab)


class HalfSpread:
    """hs = max(hist effective H1 -> H3, live-book vol10k L1 (n2s >= 20) -> L3, local tape median split x pbucket)."""

    def __init__(self, local_tab):
        e = pd.read_parquet(D / "effective_spread_hist.parquet")
        e = e[e.n_markets >= 20]
        self.h1 = e[e.level == "H1"].set_index(["split", "pbucket", "ttr_bucket"]).eff_half_med.to_dict()
        self.h3 = e[e.level == "H3"].set_index(["split", "pbucket"]).eff_half_med.to_dict()
        s = pd.read_parquet(D / "spread_model.parquet")
        s = s[s.book_universe == "vol10k"]
        self.l1 = s[(s.level == "L1") & (s.n_markets_two_sided >= 20)].set_index(["category", "pbucket"]).half_spread_med.to_dict()
        self.l3 = s[s.level == "L3"].set_index("pbucket").half_spread_med.to_dict()
        self.loc = local_tab

    def __call__(self, split, cat, price, ttr_h, in_play):
        pbs = pb(price); tb = ttr_b(np.asarray(ttr_h, float), np.asarray(in_play, bool))
        out = np.empty(len(pbs)); src = []
        for k, (sp, c, p_, t_) in enumerate(zip(split, cat, pbs, tb)):
            h = self.h1.get((sp, p_, t_), self.h3.get((sp, p_), np.nan))
            l = self.l1.get((c, p_), self.l3.get(p_, np.nan))
            q = self.loc.get((sp, p_), self.loc.get((sp, "ALL"), np.nan))
            v = np.array([h, l, q], float)
            out[k] = np.nanmax(v) if np.isfinite(v).any() else 0.01
            src.append("hist" if v[0] == out[k] else ("book" if v[1] == out[k] else "local"))
        return out, np.array(src)


def boot_ci(ret, groups, alpha, b=B):
    """Ratio-of-sums cluster bootstrap of the mean per trade. Returns (lo, hi)."""
    g = pd.Series(ret).groupby(np.asarray(groups))
    s, c = g.sum().to_numpy(), g.size().to_numpy()
    k = len(s)
    if k < 3:
        return np.nan, np.nan
    W = RNG.multinomial(k, np.full(k, 1 / k), size=b)
    m = (W @ s) / (W @ c)
    return float(np.quantile(m, alpha / 2)), float(np.quantile(m, 1 - alpha / 2))


def to_md(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        lines.append("| " + " | ".join(f"{v:.4f}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(lines)


def summarize(df, col="ret_net", alpha=0.025, ci=True):
    r = df[col].to_numpy()
    o = dict(n=int(len(df)), n_clusters=int(df.cluster_id.nunique()), n_weeks=int(df.week.nunique()))
    if len(df) == 0:
        return o
    o.update(mean=float(r.mean()), median=float(np.median(r)), hit=float((r > 0).mean()),
             mean_gross=float(df.ret_gross.mean()), mean_cents=float(df.pnl_net.mean()),
             mean_hold_d=float(df.hold_d.mean()), roc=float(df.pnl_net.sum() / df.cost_e.sum()))
    if ci and len(df) >= 10:
        o["ci_cluster"] = boot_ci(r, df.cluster_id, alpha)
        o["ci_week"] = boot_ci(r, df.week, alpha)
        o["lo"] = min(o["ci_cluster"][0], o["ci_week"][0]); o["hi"] = max(o["ci_cluster"][1], o["ci_week"][1])
    return o


def drop_top_clusters(df, k=5, col="ret_net"):
    top = df.groupby("cluster_id")[col].sum().nlargest(k).index
    return float(df.loc[~df.cluster_id.isin(top), col].mean())


def build():
    S = pd.read_parquet(D / "mr_shocks.parquet")
    X = pd.read_parquet(D / "mr_trades.parquet")
    X = X[X.entered.astype(bool)].copy()
    sib = pd.read_parquet(D / "mr_siblings.parquet")[["condition_id", "t_det", "sib_comove", "n_sib_priced", "sib_max_abs"]]
    fe = pd.read_parquet(D / "panel_sample.parquet", columns=["condition_id", "feesEnabled"])
    S = S.merge(sib, on=["condition_id", "t_det"], how="left").merge(fe, on="condition_id", how="left")
    keys = ["condition_id", "theta", "variant", "t_det"]
    X = X.merge(S, on=keys, how="left", validate="many_to_one")
    X = X[X.split_t != "after"]
    # local half-spread table (distinct entry prints, any theta/variant/delay)
    u = X.drop_duplicates(["condition_id", "t_entry"])
    u = u.assign(pbq=pb(u.q_entry.to_numpy()))
    loc = {}
    for sp, g in u.groupby("split_t"):
        loc[(sp, "ALL")] = float(g.loc_hs.median())
        for p_, gg in g.groupby("pbq"):
            if gg.loc_hs.notna().sum() >= 20:
                loc[(sp, p_)] = float(gg.loc_hs.median())
    hs = HalfSpread(loc)
    # fee rates (current schedule); as-traded = market's own Gamma fee fields
    cat = X.category.fillna("other").str.lower()
    tab = cat.map(fees.TAKER_RATE).fillna(0.05)
    X["fee_rate_cur"] = np.where(X.feeType.isin(CURRENT_FEE_TYPES) & X.fee_rate.notna(), X.fee_rate, tab)
    X["fee_rate_hist"] = np.where(X.feesEnabled.fillna(False).astype(bool) & X.fee_rate.notna(), X.fee_rate, 0.0)
    gst = X.gameStartTime.map(lambda x: x.timestamp() if pd.notna(x) else np.nan).to_numpy()
    sports = cat.eq("sports").to_numpy()
    ref = X.ref_ts.map(lambda x: x.timestamp()).to_numpy()
    X["hs_e"], X["hs_src_e"] = hs(X.split_t, cat, X.q_entry.to_numpy(), (ref - X.t_entry) / 3600,
                                  sports & (X.t_entry.to_numpy() >= gst))
    X["q_det"] = np.where(X.s == -1, X.p0_det, 1 - X.p0_det)
    rows = []
    for ex in EXITS:
        Y = X.copy()
        Y["exit"] = ex
        if ex == "res":
            Y["q_x"] = Y.payout; Y["t_x"] = Y.close_s; Y["at_res"] = True
        else:
            Y["q_x"] = Y[f"q_{ex}"]; Y["t_x"] = Y[f"t_{ex}"]; Y["at_res"] = Y[f"res_{ex}"].astype(bool)
        tx = Y.t_x.to_numpy(float)
        hx, _ = hs(Y.split_t, cat.loc[Y.index], Y.q_x.to_numpy(), (ref - tx) / 3600, sports & (tx >= gst))
        Y["hs_x"] = np.where(Y.at_res, 0.0, hx)
        rows.append(Y)
    Y = pd.concat(rows, ignore_index=True)
    qe, qx, res = Y.q_entry.to_numpy(), Y.q_x.to_numpy(), Y.at_res.to_numpy()

    def ret(mult_hs, rate, side_aware=False):
        add_e = mult_hs * Y.hs_e.to_numpy()
        if side_aware:  # entry print ask-type for the reversal token -> fill at print; else pay the full local spread
            add_e = np.where(Y.entry_ask_type.astype(bool), 0.0, 2 * Y.hs_e.to_numpy())
        pe = np.clip(qe + add_e, 0.001, 0.999)
        ce = pe + rate * pe * (1 - pe)
        px = np.clip(qx - mult_hs * Y.hs_x.to_numpy(), 0.0, 1.0)
        pxn = np.where(res, qx, px - rate * px * (1 - px))
        return pxn - ce, ce

    Y["pnl_gross"] = qx - qe; Y["ret_gross"] = Y.pnl_gross / qe
    Y["pnl_net"], Y["cost_e"] = ret(1, Y.fee_rate_cur.to_numpy()); Y["ret_net"] = Y.pnl_net / Y.cost_e
    p, c = ret(0, Y.fee_rate_cur.to_numpy()); Y["ret_feeonly"] = p / c
    p, c = ret(1, 0.0); Y["ret_nofee"] = p / c
    p, c = ret(2, Y.fee_rate_cur.to_numpy()); Y["ret_2hs"] = p / c
    p, c = ret(1, Y.fee_rate_hist.to_numpy()); Y["ret_hist_fee"] = p / c
    p, c = ret(1, Y.fee_rate_cur.to_numpy(), side_aware=True); Y["ret_sideaware"] = p / c
    Y["hold_d"] = (Y.t_x - Y.t_entry) / 86400
    # ex-ante feature subsets
    Y["regime"] = np.where((Y.n_takers_win <= 2) & (Y.top_wallet_share >= 0.7), "liquidity_like",
                           np.where(Y.n_takers_win >= 5, "news_like", "mixed"))
    Y["round_time"] = Y.minute.mod(30) < 5
    Y["tod"] = pd.cut(Y.hour_utc, [0, 8, 16, 24], right=False, labels=["00-08", "08-16", "16-24"]).astype(str)
    Y["plevel"] = pd.cut(Y.p0_det, [0.0, 0.2, 0.8, 1.0001], right=False, labels=["0.05-0.2", "0.2-0.8", "0.8-0.95"]).astype(str)
    Y["catg"] = np.where(Y.category.eq("crypto"), "crypto",
                         np.where(Y.category.eq("sports"), "sports", "other"))
    tr = S[(S.split_t == "train") & (S.variant == "primary") & (S.theta == 0.10)].vol24.dropna()
    q1, q2 = tr.quantile([1 / 3, 2 / 3])
    Y["vol_terc"] = np.select([Y.vol24 <= q1, Y.vol24 <= q2, Y.vol24 > q2], ["low", "mid", "high"], "na")
    Y["single_tx"] = np.where(Y.top_tx_share >= 0.7, "tx>=0.7", "tx<0.7")
    Y["sib"] = np.where(Y.sib_comove == 1, "sib_comove", np.where(Y.sib_comove == 0, "sib_quiet", "no_sib_data"))
    Y["absshock"] = pd.cut(Y.shock.abs(), [0, 0.10, 0.15, 0.25, 1.01], right=False,
                           labels=["5-10c", "10-15c", "15-25c", ">=25c"]).astype(str)
    Y.to_parquet(D / "mr_returns.parquet", index=False)
    return Y, dict(vol_terciles=[float(q1), float(q2)], local_hs={f"{a}|{b}": v for (a, b), v in loc.items()})


def main():
    Y, meta = build()
    R = {"meta": meta}
    cell = lambda th, d, ex, v="primary": Y[(Y.theta == th) & (Y.delay == d) & (Y.exit == ex) & (Y.variant == v)]
    P = cell(0.10, 120, "1h")
    tests = {}
    for name, sub in [("P1_all", P), ("P2_liquidity_like", P[P.regime == "liquidity_like"])]:
        t = {}
        for sp in ["train", "validation", "test"]:
            t[sp] = summarize(sub[sub.split_t == sp])
        te = sub[sub.split_t == "test"]
        la = cell(0.10, 120, "1h", "lookahead_res"); la = la[la.split_t == "test"]
        if name.startswith("P2"):
            la = la[la.regime == "liquidity_like"]
        t["test_2hs_mean"] = float(te.ret_2hs.mean()) if len(te) else np.nan
        t["test_sideaware_mean"] = float(te.ret_sideaware.mean()) if len(te) else np.nan
        t["test_histfee_mean"] = float(te.ret_hist_fee.mean()) if len(te) else np.nan
        t["test_drop_top5_mean"] = drop_top_clusters(te) if len(te) > 10 else np.nan
        t["test_lookahead_mean"] = float(la.ret_net.mean()) if len(la) else np.nan
        cap = te.drop_duplicates(["condition_id", "t_det"]).cap5m_rev_notional
        t["test_cap5_median"] = float(cap.median()) if len(cap) else np.nan
        T, V = t["test"], t["validation"]
        rej = {
            "R1": bool(T.get("n", 0) == 0 or T["mean"] <= 0 or T.get("lo", -1) <= 0),
            "R2": bool(V.get("n", 0) == 0 or V["mean"] <= 0),
            "R3": bool(T.get("mean", -1) <= 0 and t["test_lookahead_mean"] > 0),
            "R4": bool(t["test_2hs_mean"] <= 0),
            "R5": bool(t["test_drop_top5_mean"] <= 0),
            "R6_inconclusive": bool(T.get("n", 0) < 100 or T.get("n_clusters", 0) < 30),
            "R7": bool(t["test_cap5_median"] < 250),
        }
        t["rejections"] = rej
        tests[name] = t
    R["primary_tests"] = tests
    # 45-cell grid (primary variant): TEST and validation means, 99.9% intervals on TEST
    grid = []
    for (th, d, ex), g in Y[Y.variant == "primary"].groupby(["theta", "delay", "exit"]):
        te, va = g[g.split_t == "test"], g[g.split_t == "validation"]
        s = summarize(te, alpha=0.001)
        grid.append(dict(theta=th, delay=d, exit=ex, n_test=s["n"], cl_test=s["n_clusters"], gross_test=s.get("mean_gross"),
                         net_test=s.get("mean"), med_test=s.get("median"), lo999=s.get("lo"), hi999=s.get("hi"),
                         net_2hs=float(te.ret_2hs.mean()), net_val=float(va.ret_net.mean()) if len(va) else np.nan,
                         gross_val=float(va.ret_gross.mean()) if len(va) else np.nan,
                         net_train=float(g[g.split_t == "train"].ret_net.mean()),
                         drop5=drop_top_clusters(te) if len(te) > 10 else np.nan,
                         pass_R1_R5=bool(s.get("mean", -1) > 0 and s.get("lo", -1) > 0 and (va.ret_net.mean() > 0)
                                         and te.ret_2hs.mean() > 0 and drop_top_clusters(te) > 0)))
    G = pd.DataFrame(grid)
    R["grid"] = G.round(5).to_dict("records")
    # feature subsets, primary cell and the res exit, validation + TEST
    feats = ["regime", "single_tx", "sib", "phase", "round_time", "tod", "vol_terc", "plevel", "catg", "absshock"]
    F = []
    for ex in ["1h", "res"]:
        c = cell(0.10, 120, ex)
        for f in feats:
            for lev, g in c.groupby(f):
                for sp in ["validation", "test"]:
                    gg = g[g.split_t == sp]
                    if len(gg) == 0:
                        continue
                    s = summarize(gg, alpha=0.05, ci=len(gg) >= 30)
                    F.append(dict(exit=ex, feature=f, level=str(lev), split=sp, n=s["n"], cl=s["n_clusters"],
                                  gross=s["mean_gross"], net=s["mean"], med=s["median"], hit=s["hit"],
                                  lo95=s.get("lo"), hi95=s.get("hi"),
                                  cap5_med=float(gg.cap5m_rev_notional.median())))
    FF = pd.DataFrame(F)
    R["features"] = FF.round(5).to_dict("records")
    # diagnostics: where does the reversal happen? (in reversal-token cents, primary cell TEST)
    te = P[P.split_t == "test"]
    alld = cell(0.10, 30, "1h"); alld = alld[alld.split_t == "test"]
    R["diag"] = dict(
        rev_before_entry_c_d120=float(((te.q_entry - te.q_det) * 100).mean()),
        rev_before_entry_c_d30=float(((alld.q_entry - alld.q_det) * 100).mean()),
        shock_c=float((te.shock.abs() * 100).mean()),
        hs_e_med=float(te.hs_e.median()), hs_e_mean=float(te.hs_e.mean()),
        hs_src=te.hs_src_e.value_counts(normalize=True).round(3).to_dict(),
        fee_rate_mean=float(te.fee_rate_cur.mean()),
        fee_c_mean=float((te.fee_rate_cur * te.q_entry * (1 - te.q_entry) * 100).mean()),
        gross_c_mean=float((te.pnl_gross * 100).mean()), net_c_mean=float((te.pnl_net * 100).mean()),
        entry_ask_type_share=float(te.entry_ask_type.mean()),
        cap5_quantiles=te.cap5m_rev_notional.quantile([.25, .5, .75, .9]).round(0).to_dict(),
        test_trades_per_week=float(len(te) / te.week.nunique()),
        test_weeks=int(te.week.nunique()),
    )
    (OUT / "03_results.json").write_text(json.dumps(R, indent=1, default=float))
    # compact markdown tables
    md = ["## Primary tests (theta 10c, delay 120 s, exit 1 h)\n"]
    for k, t in tests.items():
        md.append(f"**{k}**")
        md.append("| split | n | clusters | gross | net | median | hit | 97.5% lo | 97.5% hi |\n|---|---|---|---|---|---|---|---|---|")
        for sp in ["train", "validation", "test"]:
            s = t[sp]
            md.append(f"| {sp} | {s['n']} | {s['n_clusters']} | {s.get('mean_gross', np.nan):.4f} | {s.get('mean', np.nan):.4f} | "
                      f"{s.get('median', np.nan):.4f} | {s.get('hit', np.nan):.3f} | {s.get('lo', np.nan):.4f} | {s.get('hi', np.nan):.4f} |")
        md.append(f"TEST: 2xhs {t['test_2hs_mean']:.4f}; side-aware {t['test_sideaware_mean']:.4f}; as-traded fees "
                  f"{t['test_histfee_mean']:.4f}; drop top-5 clusters {t['test_drop_top5_mean']:.4f}; look-ahead variant "
                  f"{t['test_lookahead_mean']:.4f}; cap5 median ${t['test_cap5_median']:.0f}. Rejections: {t['rejections']}\n")
    md.append("## Grid (primary variant, TEST net mean per trade; 99.9% interval)\n")
    md.append(to_md(G[["theta", "delay", "exit", "n_test", "cl_test", "gross_test", "net_test", "lo999", "hi999", "net_val",
                 "net_train", "net_2hs", "pass_R1_R5"]]))
    md.append("\n## Feature subsets (theta 10c, delay 120 s)\n")
    md.append(to_md(FF))
    md.append("\n## Diagnostics\n```\n" + json.dumps(R["diag"], indent=1, default=float) + "\n```")
    (OUT / "03_tables.md").write_text("\n".join(md))
    for k, t in tests.items():
        print(k, {sp: {kk: (round(v, 4) if isinstance(v, float) else v) for kk, v in t[sp].items()
                       if kk in ("n", "n_clusters", "mean", "mean_gross", "lo", "hi")} for sp in ["validation", "test"]})
        print("  ", {k2: (round(v, 4) if isinstance(v, float) else v) for k2, v in t.items() if k2.startswith("test_")},
              t["rejections"])
    print("grid passing R1-R5:", int(G.pass_R1_R5.sum()), "of", len(G))
    print(json.dumps(R["diag"], default=float))


if __name__ == "__main__":
    main()
