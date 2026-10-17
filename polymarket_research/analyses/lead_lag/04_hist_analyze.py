"""Historical 1-minute lead-lag test on resolved BTC/ETH 15m (Chainlink TWAP) and 1h (Binance candle) markets.

Polymarket side: CLOB /prices-history fidelity=1 of the Up token, a trade/mid series. It is NOT an executable price, and its
timestamp convention is not documented, so the alignment is estimated from the data (lead/lag profile).
Spot side: Coinbase BTC-USD/ETH-USD 1m (proxy for Chainlink BTC/USD) and Binance BTCUSDT/ETHUSDT 1m (resolution source of the
1h markets). The fair model is pre-registered in notes/strategies/lead_lag.md section 0.1.

Run: python -m analyses.lead_lag.04_hist_analyze
Outputs: data/derived/lead_lag/hist_panel.parquet, hist_summary.json
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

D = "data/derived/lead_lag/"


def spot_tables():
    bn = pd.read_parquet(D + "hist_binance_1m.parquet")
    cb = pd.read_parquet(D + "hist_coinbase_1m.parquet")
    out = {}
    for src, df, m in (("binance", bn, {"BTCUSDT": "btc", "ETHUSDT": "eth"}), ("coinbase", cb, {"BTC-USD": "btc", "ETH-USD": "eth"})):
        for sym, a in m.items():
            x = df[df.sym == sym].drop_duplicates("t").set_index("t").sort_index()
            # price AT minute boundary m = close of the candle that ends at m (starts at m-60)
            px = pd.Series(x.c.values, index=x.index + 60)
            px = px.reindex(range(int(px.index.min()), int(px.index.max()) + 1, 60)).ffill()
            r = np.log(px).diff()
            sig = r.rolling(60, min_periods=30).std().shift(0) / math.sqrt(60)   # trailing 60 x 1m, per sqrt-second
            opn = pd.Series(x.o.values, index=x.index)
            out[(src, a)] = dict(px=px, sig=sig, opn=opn)
    return out


def fair_at(kind, s, K, sg, t, t1):
    if kind == "15m":
        var = (t1 - 60 - t) + 20.0 if t <= t1 - 60 else max(t1 - t, 0) / 3.0
    else:
        var = float(t1 - t)
    if var <= 0 or sg <= 0:
        return float(s >= K)
    return float(norm.cdf(math.log(s / K) / (sg * math.sqrt(var))))


def primary(mk, pm, sp):
    """Panel at the Polymarket sample timestamps; spot = Binance 1s close of the second before t (no look-ahead)."""
    one = pd.read_parquet(D + "hist_binance_1s.parquet")
    px1 = {}
    for sym, a in (("BTCUSDT", "btc"), ("ETHUSDT", "eth")):
        x = one[one.sym == sym].drop_duplicates("t").set_index("t").c.sort_index()
        x.index = x.index + 1                      # price AT second t = close of the 1s kline that started at t-1
        px1[a] = x.reindex(range(int(x.index.min()), int(x.index.max()) + 1)).ffill()
    rows = []
    offs = (0, 5, 15, 30, 60, 120)
    for m in mk.itertuples():
        t0, t1 = int(m.t0.timestamp()), int(m.t1.timestamp())
        h = pm[(pm.slug == m.slug) & (pm.t > t0) & (pm.t < t1)].drop_duplicates("t").sort_values("t")
        if len(h) < 3:
            continue
        P1 = px1[m.asset]
        K = P1.get(t0) if m.kind == "15m" else sp[("binance", m.asset)]["opn"].get(t0)
        if K is None or pd.isna(K):
            continue
        sig = sp[("binance", m.asset)]["sig"]
        for t, p in zip(h.t.values, h.p.values):
            t = int(t)
            sg = sig.get((t // 60) * 60)
            if sg is None or pd.isna(sg):
                continue
            rec = {"slug": m.slug, "asset": m.asset, "kind": m.kind, "t": t, "tau": t1 - t, "pm": float(p), "y": m.up_won}
            for o in offs + (-60,):
                tt = t - o
                s = P1.get(tt)
                if s is None or pd.isna(s) or tt <= t0 - 1 or tt >= t1:
                    rec[f"f{o}"] = np.nan
                else:
                    rec[f"f{o}"] = fair_at(m.kind, float(s), float(K), float(sg), tt, t1)
            rows.append(rec)
    return pd.DataFrame(rows)


def primary_tests(Q):
    clip = lambda p: np.clip(p, 1e-3, 1 - 1e-3)
    ll = lambda y, p: float(-np.mean(y * np.log(clip(p)) + (1 - y) * np.log(1 - clip(p))))
    out = {}
    for k, x in Q.groupby("kind"):
        x = x.sort_values(["slug", "t"]).copy()
        r = {"n": int(len(x)), "markets": int(x.slug.nunique()), "median_sample_gap_s": float(x.groupby("slug").t.diff().median()),
             "logloss_pm": ll(x.y, x.pm), "logloss_fair": ll(x.y, x.f0)}
        X = sm.add_constant(pd.DataFrame({"lpm": np.log(clip(x.pm) / (1 - clip(x.pm))), "lfair": np.log(clip(x.f0) / (1 - clip(x.f0)))}))
        fit = sm.Logit(x.y.values, X).fit(disp=0, cov_type="cluster", cov_kwds={"groups": pd.factorize(x.slug)[0]})
        r["logit_coef"], r["logit_t"] = fit.params.round(3).to_dict(), fit.tvalues.round(2).to_dict()
        # response decomposition: dPM between consecutive samples vs fair changes in sub-intervals before t
        x["pm_prev"] = x.groupby("slug").pm.shift(1)
        x["t_prev"] = x.groupby("slug").t.shift(1)
        z = x[(x.t - x.t_prev).between(50, 70)].copy()
        z["dpm"] = z.pm - z.pm_prev
        z["d_0_5"] = z.f0 - z.f5
        z["d_5_15"] = z.f5 - z.f15
        z["d_15_30"] = z.f15 - z.f30
        z["d_30_60"] = z.f30 - z.f60
        z["d_60_120"] = z.f60 - z.f120
        z["d_lead"] = z["f-60"] - z.f0          # look-ahead check: fair change AFTER t (should be ~0 if no look-ahead in pm)
        cols = ["d_0_5", "d_5_15", "d_15_30", "d_30_60", "d_60_120", "d_lead"]
        z = z.dropna(subset=["dpm"] + cols)
        z = z[z.tau >= 60]
        f = sm.OLS(z.dpm, sm.add_constant(z[cols])).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(z.slug)[0]})
        r["response"] = {"n": int(len(z)), "coef": f.params.round(3).to_dict(), "t": f.tvalues.round(1).to_dict(), "r2": round(f.rsquared, 3)}
        # predictive, no look-ahead: next PM change on the current gap (fair - pm) and the last-minute fair change
        x["gap"] = x.f0 - x.pm
        x["dpm_next"] = x.groupby("slug").pm.shift(-1) - x.pm
        x["dt_next"] = x.groupby("slug").t.shift(-1) - x.t
        z2 = x[x.dt_next.between(50, 70) & (x.tau >= 120)].dropna(subset=["gap", "dpm_next", "f60"])
        z2 = z2.assign(dfair=z2.f0 - z2.f60)
        f2 = sm.OLS(z2.dpm_next, sm.add_constant(z2[["gap", "dfair"]])).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(z2.slug)[0]})
        pred = f2.fittedvalues
        hurdle = 0.07 * z2.pm * (1 - z2.pm)
        r["predictive"] = {"n": int(len(z2)), "coef": f2.params.round(4).to_dict(), "t": f2.tvalues.round(2).to_dict(), "r2": round(f2.rsquared, 4),
                           "abs_pred_median": float(pred.abs().median()), "abs_pred_p90": float(pred.abs().quantile(0.9)),
                           "abs_gap_median": float(z2.gap.abs().median()),
                           "share_pred_gt_fee+0.005": float((pred.abs() > hurdle + 0.005).mean()),
                           "share_pred_gt_fee+0.01": float((pred.abs() > hurdle + 0.01).mean())}
        out[k] = r
    return out


def main():
    mk = pd.read_parquet(D + "hist_markets.parquet")
    mk = mk[mk.err.isna() & mk.up_won.notna()]
    pm = pd.read_parquet(D + "hist_pm_1m.parquet")
    sp = spot_tables()
    rows = []
    for m in mk.itertuples():
        t0, t1 = int(m.t0.timestamp()), int(m.t1.timestamp())
        h = pm[pm.slug == m.slug].drop_duplicates("t").set_index("t").p
        if h.empty:
            continue
        src = "coinbase" if m.kind == "15m" else "binance"
        S = sp[(src, m.asset)]
        if m.kind == "15m":
            if m.price_to_beat is None or pd.isna(m.price_to_beat):
                continue
            s0 = S["px"].get(t0)
            K = s0      # per-market basis: strike mapped onto the proxy = proxy price at the start minute
        else:
            K = S["opn"].get(t0)
        if K is None or pd.isna(K):
            continue
        # minute grid from t0-? : use in-window minutes only (strike known), plus PM at grid
        grid = list(range(t0, t1 + 1, 60))
        pmg = h.reindex(sorted(set(h.index) | set(grid))).ffill().reindex(grid)
        for t in grid:
            s, sg = S["px"].get(t), S["sig"].get(t)
            if s is None or sg is None or pd.isna(s) or pd.isna(sg) or sg <= 0:
                continue
            if m.kind == "15m":
                var = (t1 - 60 - t) + 20.0 if t <= t1 - 60 else max(t1 - t, 0) / 3.0
            else:
                var = float(t1 - t)
            fair = norm.cdf(math.log(s / K) / (sg * math.sqrt(var))) if var > 0 else float(s >= K)
            rows.append((m.slug, m.asset, m.kind, t, t1 - t, pmg.get(t), fair, m.up_won, math.log(s / K), sg))
    P = pd.DataFrame(rows, columns=["slug", "asset", "kind", "t", "tau", "pm", "fair", "y", "lnSK", "sig"])
    P = P.sort_values(["slug", "t"]).reset_index(drop=True)
    P.to_parquet(D + "hist_panel.parquet")
    out = {"n_rows": int(len(P)), "n_markets": int(P.slug.nunique()), "by_kind": P.groupby("kind").slug.nunique().to_dict(),
           "note": "prices-history is a trade/mid series, not executable; 1-min resolution"}
    clip = lambda p: np.clip(p, 1e-3, 1 - 1e-3)
    ll = lambda y, p: float(-np.mean(y * np.log(clip(p)) + (1 - y) * np.log(1 - clip(p))))
    res = {}
    for k, x in P[P.pm.notna() & (P.tau > 0)].groupby("kind"):
        r = {"n": int(len(x)), "markets": int(x.slug.nunique()), "logloss_pm": ll(x.y, x.pm), "logloss_fair": ll(x.y, x.fair),
             "brier_pm": float(((x.pm - x.y) ** 2).mean()), "brier_fair": float(((x.fair - x.y) ** 2).mean())}
        # logistic: does fair add information beyond the Polymarket price? (clustered by market)
        X = pd.DataFrame({"lpm": np.log(clip(x.pm) / (1 - clip(x.pm))), "lfair": np.log(clip(x.fair) / (1 - clip(x.fair)))})
        X = sm.add_constant(X)
        try:
            fit = sm.Logit(x.y.values, X).fit(disp=0, cov_type="cluster", cov_kwds={"groups": pd.factorize(x.slug)[0]})
            r["logit_coef"] = fit.params.round(3).to_dict()
            r["logit_t"] = fit.tvalues.round(2).to_dict()
        except Exception as ex:  # noqa: BLE001
            r["logit_err"] = repr(ex)[:100]
        # tau buckets
        x = x.assign(tb=pd.cut(x.tau, [0, 120, 300, 600, 1200, 2400, 3600], right=True))
        r["by_tau"] = {str(b): {"n": int(len(g)), "ll_pm": ll(g.y, g.pm), "ll_fair": ll(g.y, g.fair)} for b, g in x.groupby("tb", observed=True) if len(g) > 50}
        res[k] = r
    out["calibration"] = res
    # lead-lag profile: dPM(t) on dFair(t+j*60), j=-2..2, within market
    P["dpm"] = P.groupby("slug").pm.diff()
    P["dfair"] = P.groupby("slug").fair.diff()
    for j in (-3, -2, -1, 1, 2):
        P[f"dfair_{j}"] = P.groupby("slug").dfair.shift(-j)   # dfair_{j} = dFair at t + j minutes
    P["gap"] = P.fair - P.pm
    P["dpm_next"] = P.groupby("slug").dpm.shift(-1)
    ll_res = {}
    for k, x in P.groupby("kind"):
        cols = ["dfair_-3", "dfair_-2", "dfair_-1", "dfair", "dfair_1", "dfair_2"]
        z = x.dropna(subset=["dpm"] + cols)
        z = z[z.tau >= 60]
        fit = sm.OLS(z.dpm, sm.add_constant(z[cols])).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(z.slug)[0]})
        r = {"n": int(len(z)), "coef": fit.params.round(4).to_dict(), "t": fit.tvalues.round(2).to_dict(), "r2": round(fit.rsquared, 3)}
        # predictive (no look-ahead): next-minute PM change on current gap and current/lagged fair changes
        z2 = x.dropna(subset=["dpm_next", "gap", "dfair", "dpm"])
        z2 = z2[z2.tau >= 120]
        f2 = sm.OLS(z2.dpm_next, sm.add_constant(z2[["gap", "dfair", "dpm"]])).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(z2.slug)[0]})
        pred = f2.fittedvalues
        r["predictive"] = {"n": int(len(z2)), "coef": f2.params.round(4).to_dict(), "t": f2.tvalues.round(2).to_dict(), "r2": round(f2.rsquared, 4),
                           "abs_pred_move_median": float(pred.abs().median()), "abs_pred_move_p90": float(pred.abs().quantile(0.9)),
                           "abs_gap_median": float(z2.gap.abs().median())}
        # fee + half-spread hurdle at the observed price
        hurdle = 0.07 * z2.pm * (1 - z2.pm)
        r["predictive"]["share_pred_gt_fee_plus_halfspread_0.005"] = float((pred.abs() > hurdle + 0.005).mean())
        r["predictive"]["share_pred_gt_fee_plus_halfspread_0.01"] = float((pred.abs() > hurdle + 0.01).mean())
        ll_res[k] = r
    out["leadlag_1m"] = ll_res
    Q = primary(mk, pm, sp)
    Q.to_parquet(D + "hist_panel_primary.parquet")
    out["PRIMARY_at_pm_timestamps_binance1s"] = primary_tests(Q)
    out["prereg_grid_note"] = ("The keys calibration/leadlag_1m use the pre-registered minute grid (Coinbase 1m proxy for 15m). "
                               "prices-history points fall at irregular seconds (t mod 60 ~ 20-24 s), so on the grid the PM value is "
                               "~35-40 s stale; the PRIMARY block evaluates spot at the PM timestamps instead.")
    json.dump(out, open(D + "hist_summary.json", "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:7000])


if __name__ == "__main__":
    main()
