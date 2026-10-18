"""Family D historical: robustness of the TEST survivors (declared post hoc in notes §8) + capacity.

- survivors x fee era (current regime = trades from 2026-03-30)
- survivors x early-close flag (M sample = 72 h before close, so for early-closing markets membership looks ahead)
- capacity: TEST daily back-of-queue fill flow (q_max = 250 shares per taker trade) and implied P&L per day
Usage: python analyses/lp_markouts/04_robust.py
"""
import importlib.util, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.getcwd())
spec = importlib.util.spec_from_file_location("a2", "analyses/lp_markouts/02_analyze.py")
a2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(a2)

SURV = {"sports|7-30d": [("category", "sports"), ("ttr", "7-30d")], ">98c": [("pb", ">98c")],
        "ttr 7-30d": [("ttr", "7-30d")], "ttr <=1h": [("ttr", "<=1h")],
        "ttr <=1h ex-crypto": [("ttr", "<=1h"), ("category", "!crypto")], "crypto (incentive-dep.)": [("category", "crypto")],
        "all": []}


def main():
    x = a2.load()
    meta = pd.read_parquet(f"{a2.IN}/market_meta.parquet")[["condition_id", "endDate_s", "closedTime_s"]]
    x = x[x.split == "test"].copy()
    gap = x.condition_id.astype(str).map(meta.set_index("condition_id").eval("endDate_s - closedTime_s"))
    x["early"] = np.where(gap.to_numpy() > 86400, "early_close", "on_schedule")
    cols = a2.add_sums(x)
    ev, evu = pd.factorize(x.event_id.astype(str)); x["ev"] = ev
    wk, wku = pd.factorize(x.week); x["wk"] = wk
    rng = np.random.default_rng(7)
    W = {"ev": (rng.poisson(1.0, (a2.B, len(evu))).astype(float), "ev"),
         "wk": (rng.poisson(1.0, (a2.B, len(wku))).astype(float), "wk")}
    rows, cap = [], []
    for name, conds in SURV.items():
        m = np.ones(len(x), bool)
        for col, val in conds:
            v = x[col].astype(str).to_numpy()
            m &= (v != val[1:]) if val.startswith("!") else (v == val)
        sub = x[m]
        for by in ["fee_era", "early"]:
            c = a2.cells(sub, [by], cols, W).reset_index().rename(columns={by: "cell"})
            c["surv"] = name; c["by"] = by; rows.append(c)
        # capacity (current fee era only)
        s = sub[sub.fee_era == "test_fee_all"]
        if len(s):
            day = (s.t // 86400)
            ndays = (s.t.max() - s.t.min()) / 86400
            fill = s.wq.astype(float); capu = s.cap.astype(float)
            net = s.netM300.astype(float).fillna(0); rs = s.rsM300.astype(float).fillna(0); res = s.rsres.astype(float).fillna(0)
            cap.append({"surv": name, "days": round(ndays, 1), "n_markets": int(s.condition_id.nunique()),
                        "fill_shares_per_day": float(fill.sum() / ndays),
                        "fill_capital_per_day_usd": float((fill * capu).sum() / ndays),
                        "net5m_pnl_per_day_usd": float((fill * net).sum() / ndays),
                        "trading5m_pnl_per_day_usd": float((fill * rs).sum() / ndays),
                        "res_pnl_per_day_usd": float((fill * res).sum() / ndays),
                        "hold_med_h": float(s.to_close_h.median()),
                        "hold_mean_h_fillw": float((fill * s.to_close_h.astype(float)).sum() / fill.sum()) if fill.sum() else None,
                        "max_fill_day_share_of_total": float(fill.groupby(day).sum().max() / fill.sum()) if fill.sum() else None})
    R = pd.concat(rows, ignore_index=True)
    R.to_parquet("analyses/lp_markouts/out/robust_cells.parquet", index=False)
    json.dump(cap, open("analyses/lp_markouts/out/capacity.json", "w"), indent=1)
    f = lambda v: "" if pd.isna(v) else f"{100*v:.2f}"
    for r in R.itertuples():
        print(f"{r.surv[:22]:22} {str(r.cell):13} n={r.n_trades:>8,} ev={r.n_events:>4} wk={r.n_weeks:>3} "
              f"rsM {f(r.rsM300)} [{f(r.rsM300_lo)},{f(r.rsM300_hi)}] rsR {f(r.rsR300)} [{f(r.rsR300_lo)},{f(r.rsR300_hi)}] "
              f"net {f(r.netM300)} [{f(r.netM300_lo)},{f(r.netM300_hi)}] netQ {f(r.netM300_q)} [{f(r.netM300_q_lo)},{f(r.netM300_q_hi)}] "
              f"res {f(r.rsres)} [{f(r.rsres_lo)},{f(r.rsres_hi)}]")
    for c in cap:
        print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in c.items()})


if __name__ == "__main__":
    main()
