"""Stage 4 (adversarial audit), step a01: independent re-computation of the stage-2 confirmatory results.

Written by the auditor without importing evalib.py / 17_evaluate.py. Inputs: sig_members.parquet (signals),
follower_prices.parquet (server-side print summaries), token_meta_pit.parquet (payout and t_res re-joined by token key,
to check the copies carried in sig_members). Checks:
  * invariants: eval-window timing (t0 in [D, next month)), F1 signal time = t0 + 600 s, payout / t_res consistency,
    first print at or after detection, print before t_res;
  * pre-registered model (first other-wallet taker BUY print >= detection, + 0.01, cap 0.999, $100, hold, fee 0):
    ROI, event-clustered CI, plus wallet-clustered and week-clustered CIs (auditor addition);
  * sensitivity: current taker fee (rate x (1 - e) per $), no-tick entry, every delay, ipw-free 'all-or-nothing'
    bounds (adv: unfilled feasible losers lose the stake).
Output: data/derived/pit_wallets/audit/a01_recompute.parquet, a01_delays.parquet; summary on stdout.
Run from polymarket_research/:  python analyses/pit_wallets/a01_recompute_stage2.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "pit_wallets"
AUD = OUT / "audit"
RATE = {"crypto": 0.07, "sports": 0.05, "politics": 0.04, "other": 0.05}
DELAYS = {"5": 5, "30": 30, "120": 120, "600": 600, "900": 900, "3600": 3600, "poll": None}
B = 2000


def month_end(D):
    d = pd.to_datetime(pd.Series(D), unit="s", utc=True) + pd.offsets.MonthBegin(1)
    return np.array([int(x.timestamp()) for x in d])


def cboot(keys, pnl, cost, rng, B=B):
    """Cluster bootstrap percentile CI of sum(pnl)/sum(cost), clusters resampled with replacement."""
    c, u = pd.factorize(pd.Series(keys).astype(str))
    n = len(u)
    if n < 2:
        return np.nan, np.nan
    P = np.bincount(c, pnl, n); C = np.bincount(c, cost, n)
    out = np.empty(B)
    for b in range(0, B, 200):
        idx = rng.integers(0, n, (min(200, B - b), n))
        out[b:b + len(idx)] = P[idx].sum(1) / C[idx].sum(1)
    return np.percentile(out, 2.5), np.percentile(out, 97.5)


def main():
    s = pd.read_parquet(OUT / "sig_members.parquet")
    s = s[s.stype.isin(["P", "F1", "F2", "CL"])].copy()
    tm = pd.read_parquet(OUT / "token_meta_pit.parquet", columns=["k", "p", "r", "market_clean", "endDate"])
    tm = tm.rename(columns={"p": "p_tm", "r": "r_tm"})
    s = s.merge(tm, on="k", how="left")
    fp = pd.read_parquet(OUT / "follower_prices.parquet")
    s = s.merge(fp, on="psid", how="left")
    print("signals", len(s), "by type", s.stype.value_counts().to_dict())
    # ---------------- invariants
    inv = {}
    inv["p_mismatch"] = int((s.p.astype(float) != s.p_tm.astype(float)).sum())
    inv["r_mismatch"] = int((s.r.astype(float) != s.r_tm.astype(float)).sum())
    inv["unclean_in_signals"] = int((~s.market_clean.fillna(False).astype(bool)).sum())
    dec = s[s.src == "decision"]
    me = month_end(dec.D.values)
    inv["t0_outside_window"] = int(((dec.t0.values < dec.D.values) | (dec.t0.values >= me)).sum())
    inv["P_tsig_ne_t0"] = int(((dec.stype == "P") & (dec.t_sig != dec.t0)).sum())
    inv["F2_tsig_ne_t0"] = int(((dec.stype == "F2") & (dec.t_sig != dec.t0)).sum())
    inv["F1_tsig_ne_t0p600"] = int(((dec.stype == "F1") & (dec.t_sig != dec.t0 + 600)).sum())
    inv["t0_at_or_after_tres"] = int((s.t0 >= s.r).sum())
    inv["r_le_0"] = int((s.r <= 0).sum())
    s = s[s.r > 0].copy()
    for d in DELAYS:
        g = s[f"fgap_{d}"].fillna(65535)
        inv[f"neg_gap_{d}"] = int((g < 0).sum())
    print("invariants:", inv)
    # ---------------- pricing
    t = s.t_sig.values.astype(np.int64)
    s["week"] = (t + 3 * 86400) // 604800
    s["fee_rate"] = s.category.map(RATE).fillna(0.05)
    p = s.p.values.astype(float)
    rows, drows = [], []
    rng = np.random.default_rng(20261018)
    for d, dd in DELAYS.items():
        det = (t // 3600 + 1) * 3600 if dd is None else t + dd
        gap = s[f"fgap_{d}"].fillna(65535).values.astype(np.int64)
        raw = s[f"fpx_{d}"].fillna(0).values / 1e4
        has = (gap != 65535) & (raw > 0)
        tin = det + np.where(has, gap, 0)
        feas = det < s.r.values
        ok = has & (tin < s.r.values)
        e = np.minimum(0.999, raw + 0.01)
        roi0 = np.where(ok, p / np.where(ok, e, 1) - 1, 0.0)
        roic = roi0 - np.where(ok, s.fee_rate.values * (1 - e), 0.0)
        inv_late = int((has & feas & (tin >= s.r.values)).sum())
        for key, g in s.groupby(["stype", "screen", "split"]).indices.items():
            o = ok[g]
            nf = int(o.sum())
            if nf == 0:
                continue
            lose_unf = feas[g] & ~o & (p[g] == 0)
            r = dict(stype=key[0], screen=key[1], split=key[2], delay=d, n_sig=len(g), n_fill=nf,
                     n_events=s.underlying_key.values[g][o].astype(str).size and
                     pd.Series(s.underlying_key.values[g][o]).nunique(),
                     roi_hist=float(roi0[g][o].mean()), roi_cur=float(roic[g][o].mean()),
                     roi_adv_cur=float((roic[g][o].sum() - lose_unf.sum()) / (nf + lose_unf.sum())),
                     mean_px=float(raw[g][o].mean()), hit=float(p[g][o].mean()))
            if d == "120":
                gg = g[o]
                pnl0, pnlc = 100 * roi0[gg], 100 * roic[gg]
                cost = np.full(len(gg), 100.0)
                ev = s.underlying_key.values[gg]
                wl = np.where(s.wallet.values[gg] == "", ev.astype(str), s.wallet.values[gg])
                r["ci_ev_lo"], r["ci_ev_hi"] = cboot(ev, pnl0, cost, rng)
                r["ci_wal_lo"], r["ci_wal_hi"] = cboot(wl, pnl0, cost, rng)
                r["ci_wk_lo"], r["ci_wk_hi"] = cboot(s.week.values[gg], pnl0, cost, rng)
                r["ci_cur_ev_lo"], r["ci_cur_ev_hi"] = cboot(ev, pnlc, cost, rng)
                r["n_wallets"] = int(pd.Series(wl).nunique())
                # no tick: entry at the raw print price (lower bound on cost for a 0.001-tick market)
                e0 = np.minimum(0.999, raw[gg])
                r["roi_notick"] = float((p[gg] / e0 - 1).mean())
                # the tick convention matters most near 0.99: share of filled signals with raw >= 0.96
                r["share_raw_ge096"] = float((raw[gg] >= 0.96).mean())
                r["median_gap_s"] = float(np.median(gap[gg]))
                r["late_print_unfilled"] = inv_late
                rows.append(r)
            drows.append(r)
    res = pd.DataFrame(rows)
    dl = pd.DataFrame(drows)
    # ---------------- slippage-convention x estimator sensitivity at the 2-minute delay (auditor, exploratory)
    det = t + 120
    gap = s["fgap_120"].fillna(65535).values.astype(np.int64)
    raw = s["fpx_120"].fillna(0).values / 1e4
    has = (gap != 65535) & (raw > 0)
    feas = det < s.r.values
    ok = has & (det + np.where(has, gap, 0) < s.r.values)
    own = s.first_price.values.astype(float)
    ob = np.digitize(np.nan_to_num(own, nan=-1), [0.2, 0.5, 0.8, 0.95])
    conv = {"prereg_+0.01": np.full(len(s), 0.01),
            "tick_aware": np.where((raw > 0.96) | (raw < 0.04), 0.001, 0.01),
            "none": np.zeros(len(s))}
    srows = []
    for cname, sl in conv.items():
        e = np.minimum(0.999, raw + sl)
        for fee in ("hist", "cur"):
            roi = np.where(ok, p / np.where(ok, e, 1) - 1 - (s.fee_rate.values * (1 - e) if fee == "cur" else 0), 0)
            for key, g in s.groupby(["stype", "screen", "split"]).indices.items():
                if key[2] != "test":
                    continue
                o, fz, pw = ok[g], feas[g], p[g] == 1
                if o.sum() == 0:
                    continue
                ev = s.underlying_key.values[g].astype(str)
                # ipw ('always filled'): every feasible loser loses its stake (minus the mean fee of filled losers);
                # feasible winners take the mean ROI of filled winners in their own-price bucket (outcome-level
                # fallback for buckets without a filled winner)
                lose_roi = roi[g][o & ~pw].mean() if (o & ~pw).any() else -1.0
                wmean = roi[g][o & pw].mean() if (o & pw).any() else 0.0
                imp = np.zeros(len(g))
                for b_ in np.unique(ob[g]):
                    mb = ob[g] == b_
                    fw = mb & o & pw
                    imp[mb & fz & pw] = roi[g][fw].mean() if fw.any() else wmean
                imp[fz & ~pw] = lose_roi
                pn_d, co_d = 100 * roi[g] * o, 100.0 * o
                pn_i, co_i = 100 * imp * fz, 100.0 * fz
                lo_d, hi_d = cboot(ev, pn_d, co_d, rng, 1000)
                lo_i, hi_i = cboot(ev, pn_i, co_i, rng, 1000)
                srows.append(dict(stype=key[0], screen=key[1], conv=cname, fee=fee,
                                  roi_drop=pn_d.sum() / co_d.sum(), lo_drop=lo_d, hi_drop=hi_d,
                                  roi_ipw=pn_i.sum() / max(co_i.sum(), 1), lo_ipw=lo_i, hi_ipw=hi_i,
                                  fill_win=float(o[fz & pw].mean()) if (fz & pw).any() else np.nan,
                                  fill_lose=float(o[fz & ~pw].mean()) if (fz & ~pw).any() else np.nan))
    sens = pd.DataFrame(srows)
    sens.to_parquet(AUD / "a01_slippage_sens.parquet", index=False)
    pv = sens[(sens.stype == "P") | (sens.screen.isin(["CL"])) | ((sens.stype == "F1") & (sens.screen == "S4_sports"))]
    print(pv[pv.fee == "hist"].pivot_table(index=["stype", "screen"], columns="conv",
          values=["roi_drop", "hi_drop", "roi_ipw", "hi_ipw"]).round(3).to_string())
    print(pv[(pv.fee == "cur") & (pv.conv == "none")][["stype", "screen", "roi_drop", "hi_drop", "roi_ipw", "hi_ipw",
          "fill_win", "fill_lose"]].round(3).to_string(index=False))
    res.to_parquet(AUD / "a01_recompute.parquet", index=False)
    dl.to_parquet(AUD / "a01_delays.parquet", index=False)
    # ---------------- compare with stage-2 confirmatory.parquet
    c = pd.read_parquet(OUT / "results" / "confirmatory.parquet")
    c = c[c.fee == "hist"][["stype", "screen", "split", "n_fill", "n_events", "roi", "ci_lo", "ci_hi"]]
    m = res.merge(c, on=["stype", "screen", "split"], how="left", suffixes=("", "_s2"))
    m["d_roi"] = m.roi_hist - m.roi
    print("max |ROI diff| vs stage 2:", float(m.d_roi.abs().max()), " n_fill diffs:", int((m.n_fill != m.n_fill_s2).sum()),
          " n_events diffs:", int((m.n_events != m.n_events_s2).sum()))
    te = m[m.split == "test"].sort_values(["stype", "screen"])
    pd.set_option("display.width", 250)
    cols = ["stype", "screen", "n_fill", "n_events", "n_wallets", "roi_hist", "ci_ev_lo", "ci_ev_hi", "ci_wal_lo",
            "ci_wal_hi", "ci_wk_lo", "ci_wk_hi", "roi_cur", "ci_cur_ev_hi", "roi_notick", "share_raw_ge096", "median_gap_s"]
    print(te[cols].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
