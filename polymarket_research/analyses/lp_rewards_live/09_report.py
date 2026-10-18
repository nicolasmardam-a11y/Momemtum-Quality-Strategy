"""Aggregate results for notes/strategies/lp_rewards_live.md (prints compact tables; writes summary json).
Usage: python -m analyses.lp_rewards_live.09_report w1 w2
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import lp  # noqa: E402

OUT = ROOT / "data" / "derived" / "lp_rewards_live"
RNG = np.random.default_rng(20261017)
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)


def boot_ci(values_by_block, stat=np.sum, n=4000, q=(0.05, 0.95)):
    v = np.asarray(values_by_block, dtype=float)
    if len(v) == 0:
        return (np.nan, np.nan)
    bs = [stat(v[RNG.integers(0, len(v), len(v))]) for _ in range(n)]
    return tuple(np.quantile(bs, q))


def rewards_section(res):
    d = pd.read_parquet(OUT / "xsec_reward_est.parquet")
    p = d[(d.variant == "primary") & d.scorable]
    print("\n=== Cross-section rewards (primary variant), by snapshot x stratum x capital")
    t = p.groupby(["tag", "stratum", "capital"]).agg(
        n=("rate", "size"), rate_med=("rate", "median"), spread_med_c=("spread", lambda s: s.median() * 100),
        scores=("q_ours", lambda s: (s > 0).mean()), share_cen_med=("share_cen", "median"), share_con_med=("share_con", "median"),
        rew_cen_med=("rew_cen", "median"), rew_cen_p90=("rew_cen", lambda s: s.quantile(.9)),
        y_cen_bp_med=("yield_cen", lambda s: s.median() * 1e4), y_con_bp_med=("yield_con", lambda s: s.median() * 1e4),
        r1_pass=("r1_pass", "mean"))
    print(t.round(3).to_string())
    res["xsec_table"] = t.round(4).reset_index().to_dict("records")
    # by fee class at $2,500, first snapshot
    s0 = p[(p.capital == 2500) & (p.tag == p.tag.min())].copy()
    s0["cls"] = s0.fee_type.fillna("unknown").str.replace(r"_fees.*", "", regex=True)
    t2 = s0.groupby(["cls"]).agg(n=("rate", "size"), rate_sum=("rate", "sum"), share_cen_med=("share_cen", "median"),
                                 rew_cen_med=("rew_cen", "median"), y_cen_bp_med=("yield_cen", lambda s: s.median() * 1e4),
                                 r1_pass=("r1_pass", "mean")).sort_values("rate_sum", ascending=False)
    print("\n=== $2,500 by fee class (snapshot", p.tag.min(), ")")
    print(t2.round(3).to_string())
    res["xsec_by_class"] = t2.round(4).reset_index().to_dict("records")
    # persistence of the estimate per market across snapshots
    if p.tag.nunique() > 1:
        w = p[p.capital == 2500].pivot_table(index="condition_id", columns="tag", values="rew_cen")
        tags = sorted(w.columns)
        a, b = w[tags[0]], w[tags[-1]]
        ok = a.notna() & b.notna()
        both_pass = p[p.capital == 2500].pivot_table(index="condition_id", columns="tag", values="r1_pass", aggfunc="max")
        bp = both_pass.dropna()
        print(f"\npersistence {tags[0]}->{tags[-1]}: spearman rew_cen {a[ok].corr(b[ok], method='spearman'):.3f}; "
              f"R1 pass in all snapshots {bp.all(axis=1).mean():.3f} vs in first {bp[tags[0]].mean():.3f}")
        res["persist_spearman"] = float(a[ok].corr(b[ok], method="spearman"))
        res["r1_all_snapshots"] = float(bp.all(axis=1).mean())
    # sensitivity variants
    v = d[(d.capital == 2500) & d.scorable].groupby(["variant"]).agg(r1=("r1_pass", "mean"), y_cen_bp=("yield_cen", lambda s: s.median() * 1e4),
                                                                      sh_cen=("share_cen", "median"))
    print("\n=== variants ($2,500, all snapshots)")
    print(v.round(3).to_string())
    res["variants"] = v.round(4).reset_index().to_dict("records")
    # official competitiveness score as alternative denominator (interpretation UNSUPPORTED)
    x = pd.read_parquet(OUT / "xsec_markets.parquet")[["condition_id", "competitiveness"]]
    q = s0.merge(x, on="condition_id")
    q = q[q.competitiveness.notna()]
    q["cen_q"] = [lp.comp_qmin(a, b, m)[1] for a, b, m in zip(q.q1c, q.q2c, q.mid)]
    q["ratio"] = q.competitiveness / q.cen_q.replace(0, np.nan)
    print(f"competitiveness / central competitor Q: median {q.ratio.median():.3f}, IQR {q.ratio.quantile(.25):.3f}-{q.ratio.quantile(.75):.3f}, n={q.ratio.notna().sum()}")
    res["competitiveness_ratio_median"] = float(q.ratio.median())


def config_persistence(res):
    r0 = pd.read_parquet(OUT / "rewards_t0.parquet")
    files = sorted(OUT.glob("rewards_t*.parquet"))
    early = pd.read_parquet(ROOT / "data/derived/lp_rewards_current_2026-10-17.parquet")
    early = early[~early.sponsored_query]
    out = {"t0_markets": int((r0.total_daily_rate > 0).sum()), "t0_rate_sum": float(r0.total_daily_rate.sum()),
           "early_markets_1509": int((early.total_daily_rate > 0).sum()), "early_rate_sum_1509": float(early.total_daily_rate.sum())}
    if len(files) > 1:
        r1 = pd.read_parquet(files[-1])
        s0, s1 = set(r0.condition_id), set(r1.condition_id)
        out.update(t1_file=files[-1].name, t1_markets=len(s1), t1_rate_sum=float(r1.total_daily_rate.sum()),
                   dropped=len(s0 - s1), added=len(s1 - s0))
        m = r0.merge(r1[["condition_id", "total_daily_rate", "rewards_max_spread", "rewards_min_size"]], on="condition_id", suffixes=("", "_t1"))
        out["rate_changed_share"] = float((m.total_daily_rate != m.total_daily_rate_t1).mean())
        out["params_changed_share"] = float(((m.rewards_max_spread != m.rewards_max_spread_t1) | (m.rewards_min_size != m.rewards_min_size_t1)).mean())
        ws = pd.concat([pd.read_parquet(f) for f in sorted(OUT.glob("ws_markets*.parquet"))])
        out["ws_markets_dropped"] = int((~ws.condition_id.isin(s1)).sum())
    e0 = set(early.condition_id)
    out["t0_also_in_1509"] = float(r0.condition_id.isin(e0).mean())
    print("\n=== reward-config persistence", json.dumps(out))
    res["config_persistence"] = out


def micro_section(res):
    tr = pd.read_parquet(OUT / "micro_trades.parquet")
    pm = pd.read_parquet(OUT / "micro_markets.parquet")
    dec = pd.read_parquet(OUT / "micro_touch_decreases.parquet")
    print("\n=== microstructure (all prints, YES space)")
    print(f"prints {len(tr)} in {pm.shape[0]} markets; at touch {tr.at_touch.mean():.3f}; beyond touch {tr.through.mean():.3f}; "
          f"touch prints consuming the whole displayed level {tr.consumes_level.sum()}/{tr.at_touch.sum()}")
    print(f"touch-level size decreases: {len(dec)}; volume share explained by prints {dec.by_trade.sum()/dec.delta.sum():.3f}; "
          f"level depletions {dec.depleted.sum()}, with a print at that level within 1.5 s {(dec.depleted & (dec.by_trade>0)).sum()}")
    g = pm.groupby("cls").agg(markets=("n_trades", "size"), trades_per_h_med=("trades_per_h", "median"),
                              touch_prints_per_h_med=("touch_prints_per_h", "median"), notional_per_h_med=("notional_per_h", "median"),
                              consume_level=("share_consume_level", "mean"), dec_trade_share=("touch_dec_trade_share", "median"),
                              spread_c=("med_spread", lambda s: s.median() * 100))
    print(g.round(3).to_string())
    res["micro_by_class"] = g.round(4).reset_index().to_dict("records")
    rows = []
    for h in (5, 30, 60, 300):
        x = tr.dropna(subset=[f"mo{h}"])
        blk = x.groupby("condition_id")
        tot = blk[f"mo{h}"].sum().to_numpy()
        cnt = blk[f"mo{h}"].count().to_numpy()
        ci = boot_ci(np.c_[tot, cnt], stat=lambda a: a[:, 0].sum() / a[:, 1].sum()) if len(tot) else (np.nan, np.nan)
        rows.append({"h": h, "n": len(x), "markets": len(tot), "mo_mean_c": x[f"mo{h}"].mean() * 100, "mo_ci90_c": (ci[0] * 100, ci[1] * 100),
                     "spread_cap_c": x.spread_cap.mean() * 100, "as_mean_c": x[f"as{h}"].mean() * 100,
                     "mo_notional_w_bp": (x[f"mo{h}"] * x["size"]).sum() / (x.price * x["size"]).sum() * 1e4})
    mo = pd.DataFrame(rows)
    print(mo.round(3).to_string())
    res["markouts_all_prints"] = mo.round(4).to_dict("records")
    cl = pm.set_index("condition_id").cls.to_dict()
    tr["cls"] = tr.condition_id.map(cl)
    by = tr.groupby(["label", "cls"]).agg(n=("price", "size"), markets=("condition_id", "nunique"),
                                         spread_cap_c=("spread_cap", lambda s: s.mean() * 100),
                                         mo60_c=("mo60", lambda s: s.mean() * 100), mo300_c=("mo300", lambda s: s.mean() * 100),
                                         as60_c=("as60", lambda s: s.mean() * 100))
    print(by.round(3).to_string())
    res["markouts_by_label_cls"] = by.round(4).reset_index().to_dict("records")


def boot_ci_rows(arr):
    arr = np.asarray(arr)
    bs = [arr[RNG.integers(0, len(arr), len(arr))].sum() for _ in range(4000)]
    return np.quantile(bs, [0.05, 0.95])


def sim_section(res):
    E = pd.read_parquet(OUT / "sim_summary.parquet")
    F = pd.read_parquet(OUT / "sim_fills.parquet")
    print("\n=== simulated passive strategy (60 s requote, join touch); P&L in $ over the capture window")
    rows = []
    for (cap, opt), e in E.groupby(["cap", "rule"]):
        f = F[(F.cap == cap) & (F.rule == opt)] if len(F) else F
        per = e.set_index(["label", "condition_id"])   # FIX 2026-10-18: markets overlap across windows
        fm = f.groupby(["label", "condition_id"]).agg(sc=("spread_cap", "sum"), as60=("as60", lambda s: s.fillna(0).sum()),
                                           reb=("rebate_ub", "sum"), n=("qty", "size"), qty=("qty", "sum")) if len(f) else pd.DataFrame()
        per = per.join(fm, how="left").fillna({"sc": 0, "as60": 0, "reb": 0, "n": 0, "qty": 0})
        per["resid"] = per.mtm_pnl - per.sc - per.as60          # inventory drift beyond 60 s
        per["trade_net"] = per.mtm_pnl - per.liq_cost
        per["net_r3"] = per.mtm_pnl + per.rew_cen                      # pre-registered R3 definition
        per["net_cen"] = per.trade_net + per.rew_cen + per.reb          # stricter: after liquidation, + rebate UB
        per["net_con"] = per.trade_net + per.rew_con
        ci_trade = boot_ci_rows(per.mtm_pnl.to_numpy())
        ci_net = boot_ci_rows(per.net_r3.to_numpy())
        top_mkt = per.net_r3.abs().max() / max(1e-9, per.net_r3.abs().sum())
        hrs = per.hours.median()
        rows.append({"cap": cap, "rule": opt, "markets": len(per), "quoted": int((per.n_posts > 0).sum()), "fills": int(per.n.sum()),
                     "fill_markets": int((per.n > 0).sum()), "filled_notional": float((f.qty * f.price).sum()) if len(f) else 0.0,
                     "spread_capture": per.sc.sum(), "adverse_sel_60s": per.as60.sum(), "inventory_resid": per.resid.sum(),
                     "mtm_pnl": per.mtm_pnl.sum(), "liq_cost": per.liq_cost.sum(), "trade_net": per.trade_net.sum(),
                     "mtm_ci90": tuple(np.round(ci_trade, 2)), "net_r3": per.net_r3.sum(), "net_r3_ci90": tuple(np.round(ci_net, 2)), "rewards_cen": per.rew_cen.sum(), "rewards_con": per.rew_con.sum(),
                     "rebate_ub": per.reb.sum(), "net_cen": per.net_cen.sum(),
                     "net_con": per.net_con.sum(), "top_market_share_absnet": top_mkt, "hours_med": hrs,
                     "capital_quoted": cap * int((per.n_posts > 0).sum())})
        if opt == "conservative":
            per.reset_index().to_parquet(OUT / f"sim_per_market_cap{cap}.parquet", index=False)
    S = pd.DataFrame(rows)
    print(S.drop(columns=["mtm_ci90", "net_r3_ci90"]).round(2).to_string())
    print(S[["cap", "rule", "mtm_ci90", "net_r3_ci90"]].to_string())
    res["sim"] = S.round(4).to_dict("records")
    if len(F):
        f = F[F.rule == "conservative"]
        f = f.copy()
        f["win5"] = (f.t // 300).astype(int)
        res["fills_trade_through_share"] = float(f.trade_through.mean())
        res["fills_per_cap"] = f.groupby("cap").size().to_dict()
        E0 = E[E.rule == "conservative"].set_index(["label", "condition_id", "cap"]).mid_end
        f["mid_end"] = [E0.get((lb, c, k), np.nan) for lb, c, k in zip(f.label, f.condition_id, f.cap)]
        f["contrib"] = np.where(f.side == "bid", 1, -1) * (f.mid_end - f.price) * f.qty
        conc = {}
        for cap in sorted(f.cap.unique()):
            w = f[f.cap == cap].groupby("win5").contrib.sum()
            conc[int(cap)] = float(w.abs().max() / max(1e-9, w.abs().sum()))
        res["top_5min_window_share"] = conc
        print("top 5-min window share of |fill MTM|:", {k: round(v, 2) for k, v in conc.items()})
        # R2: pooled 60 s markout per share of conservative fills (cap 500), qty-weighted, market-block bootstrap
        g = f[(f.cap == 500)].dropna(subset=["as60"])
        g = g.assign(mo60=g.spread_cap + g.as60)
        blk = g.groupby("condition_id").agg(mo=("mo60", "sum"), q=("qty", "sum"))
        arr = blk[["mo", "q"]].to_numpy()
        bs = [arr[i, 0].sum() / arr[i, 1].sum() for i in (RNG.integers(0, len(arr), len(arr)) for _ in range(4000))] if len(arr) else [np.nan]
        r2 = {"fills": len(g), "markets": len(blk), "mo60_per_share_c": float(g.mo60.sum() / g.qty.sum() * 100) if len(g) else np.nan,
              "ci90_c": [float(np.quantile(bs, .05) * 100), float(np.quantile(bs, .95) * 100)],
              "spread_cap_per_share_c": float(g.spread_cap.sum() / g.qty.sum() * 100) if len(g) else np.nan,
              "as60_per_share_c": float(g.as60.sum() / g.qty.sum() * 100) if len(g) else np.nan}
        res["R2_conservative_fills_mo60"] = r2
        print("R2 (conservative fills, 60 s markout per share):", {k: (np.round(v, 3) if not isinstance(v, list) else np.round(v, 3).tolist()) for k, v in r2.items()})
        for cap in sorted(f.cap.unique()):
            g = f[f.cap == cap]
            print(f"cap {cap}: fills {len(g)}; trade-through share {g.trade_through.mean():.2f}; mean AS60/share "
                  f"{(g.as60/g.qty).mean()*100:.2f}c; mean spread capture/share {(g.spread_cap/g.qty).mean()*100:.2f}c")


def book_consistency(labels, res):
    """WS-reconstructed touch vs REST /books touch at each 60 s REST sample (data-quality check)."""
    from importlib import import_module
    Mid = import_module("07_microstructure").Mid
    out = {}
    for lab in labels:
        tb = pd.read_parquet(OUT / f"tob_{lab}.parquet")
        rest = pd.read_parquet(OUT / f"rest_books_{lab}.parquet")
        f = OUT / ("ws_markets.parquet" if lab == "w1" else f"ws_markets_{lab}.parquet")
        ymap = pd.read_parquet(f).set_index("yes_token").condition_id.to_dict()
        rest = rest[rest.asset_id.isin(ymap)]
        mid = Mid(tb)
        agree = n = 0
        for r in rest.itertuples():
            bids, asks = json.loads(r.bids), json.loads(r.asks)
            if not bids or not asks:
                continue
            t_book = r.ts_ms / 1000 if r.ts_ms else r.snap_utc
            bb, ba = mid.at(ymap[r.asset_id], t_book)
            n += 1
            agree += int(abs(bb - bids[0][0]) < 1e-9 and abs(ba - asks[0][0]) < 1e-9)
        out[lab] = {"samples": n, "touch_agree": agree / max(1, n)}
    print("\n=== WS vs REST touch agreement", out)
    res["book_consistency"] = out


def capacity(res):
    """Gross REWARD capacity (no trading P&L): greedy top-k markets by central reward at a fixed per-market size,
    first snapshot, observed markets only (B is a 500-market sample of ~13k, so this understates B's contribution)."""
    d = pd.read_parquet(OUT / "xsec_reward_est.parquet")
    p = d[(d.variant == "primary") & d.scorable & (d.tag == d.tag.min())]
    n_pop = {"A": (p.stratum == "A").sum(), "B": 13238, "C": 60}
    rf = sorted(OUT.glob("rewards_t*.parquet"))
    alive = set(pd.read_parquet(rf[-1], columns=["condition_id"]).condition_id)  # R8: config still present at last pull
    out = []
    for acct in (5000, 25000, 100000):
        for size in (500, 2500, 10000):
            k = acct // size
            if k < 1:
                continue
            q = p[p.capital == size].nlargest(int(k), "rew_cen")
            q = q.assign(inband=q.inband.astype(bool))
            # out-of-sample (added 2026-10-18): same markets re-scored at the LAST snapshot; 0 if unscorable or config gone (R8)
            last = d[(d.variant == "primary") & (d.tag == d.tag.max()) & (d.capital == size)].set_index("condition_id")
            oos = q.condition_id.map(last.rew_cen.where(last.scorable.astype(bool), 0.0)).fillna(0.0)
            oos = oos.where(q.condition_id.isin(alive), 0.0)
            out.append({"account": acct, "per_market": size, "markets": len(q), "rew_cen_day": q.rew_cen.sum(),
                        "rew_con_day": q.rew_con.sum(), "yield_cen_bp_day": q.rew_cen.sum() / acct * 1e4,
                        "oos_rew_cen_day": float(oos.sum()), "oos_yield_cen_bp_day": float(oos.sum()) / acct * 1e4,
                        "oos_tag": str(d.tag.max()),
                        "share_from_C": q[q.stratum == "C"].rew_cen.sum() / max(1e-9, q.rew_cen.sum()),
                        "share_outside_band": q[~q.inband].rew_cen.sum() / max(1e-9, q.rew_cen.sum()),
                        "share_sports": q[q.fee_type.fillna("").str.startswith("sports")].rew_cen.sum() / max(1e-9, q.rew_cen.sum())})
    o = pd.DataFrame(out)
    print("\n=== gross reward capacity (rewards only; before adverse selection, inventory and fees)")
    print(o.round(3).to_string())
    res["capacity_rewards_only"] = o.round(4).to_dict("records")
    # population-weighted R1 pass rate
    q = p[p.capital == 2500]
    w = q.stratum.map(lambda s: n_pop[s] / max(1, (q.stratum == s).sum()))
    res["r1_pass_popweighted_2500"] = float((q.r1_pass * w).sum() / w.sum())
    print("R1 pass at $2,500, population-weighted:", round(res["r1_pass_popweighted_2500"], 3))
    for tg in sorted(d.tag.unique()):
        qq = d[(d.variant == "primary") & d.scorable.astype(bool) & (d.tag == tg) & (d.capital == 2500) & d.condition_id.isin(alive)]
        ww = qq.stratum.map(lambda s: n_pop[s] / max(1, (qq.stratum == s).sum()))
        r = float((qq.r1_pass * ww).sum() / ww.sum())
        res[f"r1_pass_popweighted_2500_R8_{tg}"] = r
        print(f"R1 pass at $2,500 pop-weighted, R8-persistent markets only, snapshot {tg}: {r:.3f} (n={len(qq)})")


def main(labels):
    res = {}
    rewards_section(res)
    capacity(res)
    config_persistence(res)
    micro_section(res)
    sim_section(res)
    book_consistency(labels, res)
    (OUT / "report_summary.json").write_text(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1:])
