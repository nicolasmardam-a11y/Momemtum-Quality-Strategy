"""Sub-second lead-lag between spot (Binance, Chainlink via RTDS) and Polymarket up/down mids, from a live collection.

All times are LOCAL RECEIVE times on this sandbox (US-Ohio IP). Network paths differ by venue, so the measured lags include the
difference in delivery delay to this location; a co-located bot sees a different (smaller) number.
Run: python -m analyses.lead_lag.05_live_lag L2   (needs 03_live_analyze output live_<tag>_grid.parquet)
Outputs: data/derived/lead_lag/live_<tag>_impulse.parquet, live_<tag>_events.parquet, live_<tag>_lag_summary.json
"""
from __future__ import annotations

import glob
import json
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

TAG = sys.argv[1] if len(sys.argv) > 1 else "L2"
D = "data/derived/lead_lag/"
BIN = 0.2
KMAX = 75    # 15 s
KMIN = -10   # -2 s


def load(kind):
    fs = sorted(glob.glob(f"{D}live_{TAG}_[0-9][0-9]_{kind}.parquet"))
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)


def binned(t, v, lo, n):
    b = np.floor((t - lo) / BIN).astype(int)
    ok = (b >= 0) & (b < n)
    s = pd.Series(v[ok], index=b[ok]).groupby(level=0).last()
    return s.reindex(range(n)).ffill().values


def event_study(S, G, md, quotes, lo, WS, KSIG, trades=None):
    ev_rows = []
    for a in S:
        lb = S[a]["binance"]
        W = max(1, int(round(WS / BIN)))
        sigw = float(np.nanmedian(G[G.asset == a].sig)) * np.sqrt(WS)
        r1 = lb[W:] - lb[:-W]
        idx = np.where(np.abs(r1) >= KSIG * sigw)[0] + W
        evs, last = [], -1e9
        for i in idx:
            if i - last >= int(30 / BIN):
                evs.append(i)
                last = i
        for m in md[md.asset == a].itertuples():
            g = G[G.slug == m.slug]
            if g.empty:
                continue
            q = quotes[quotes.asset == m.tok0].sort_values("recv")
            q = q[q.bid.notna() & q.ask.notna()]
            if q.empty:
                continue
            qt, qm = q.recv.values, ((q.bid + q.ask) / 2).values
            qb, qa = q.bid.values, q.ask.values

            def quote(t):
                j = np.searchsorted(qt, t, side="right") - 1
                return (qb[j], qa[j]) if j >= 0 else (np.nan, np.nan)
            for i in evs:
                te = lo + i * BIN
                gg = g[(g.t >= te - 1) & (g.t <= te + 1)]
                if gg.empty or not (0.1 < gg.fair.iloc[0] < 0.9) or gg.tau.iloc[0] < 30:
                    continue
                sgn = np.sign(lb[i] - lb[i - W])
                j0 = np.searchsorted(qt, te - WS)  # Polymarket mid when the 10-s spot move began
                if j0 == 0:
                    continue
                m0 = qm[j0 - 1]
                after = np.where((qt >= te - WS) & (qt <= te + 30) & (sgn * (qm - m0) >= 0.0099))[0]
                rec = {}
                if trades is not None:
                    tt = trades.get(m.slug)
                    if tt is not None:
                        for nm_, w0, w1 in (("tr_pre1", -1.0, 0.0), ("tr_0_05", 0.0, 0.5), ("tr_05_2", 0.5, 2.0), ("tr_2_10", 2.0, 10.0)):
                            rec[nm_] = int(((tt >= te + w0) & (tt < te + w1)).sum()) / (w1 - w0)
                        rec["tr_base"] = len(tt) / max(1.0, (g.t.max() - g.t.min()))
                rec.update({"asset": a, "slug": m.slug, "kind": m.kind, "te": te, "ret_bp": float((lb[i] - lb[i - W]) * 1e4),
                       "lat_s": float(qt[after[0]] - te) if len(after) else None, "fair": float(gg.fair.iloc[0])})
                # taker round trip in the direction of the move: enter at te+L (ask of the side), exit at te+H (bid), both taker fees
                for L in (0.0, 0.2, 0.5, 1.0, 2.0, 5.0):
                    b0, a0 = quote(te + L)
                    for H in (10.0, 30.0):
                        b1, a1 = quote(te + L + H)
                        if sgn > 0:
                            ent, ex = a0, b1
                        else:
                            ent, ex = 1 - b0, 1 - a1
                        if np.isnan(ent) or np.isnan(ex):
                            continue
                        rec[f"rt_L{L}_H{int(H)}"] = float(ex - ent - 0.07 * ent * (1 - ent) - 0.07 * ex * (1 - ex))
                        rec[f"gross_L{L}_H{int(H)}"] = float(ex - ent)
                ev_rows.append(rec)

    return pd.DataFrame(ev_rows)


def main():
    ref, tob = load("ref"), load("tob")
    G = pd.read_parquet(f"{D}live_{TAG}_grid.parquet")
    md = pd.read_parquet(f"{D}live_{TAG}_meta.parquet")
    lo, hi = G.t.min(), G.t.max()
    n = int((hi - lo) / BIN) + 1
    quotes = tob[tob.bid_sz.notna()]
    trd = tob[tob.bid_sz.isna()]   # last_trade_price rows (stored as ask=price, ask_sz=size)
    tok2slug = {t: m.slug for m in md.itertuples() for t in (m.tok0, m.tok1)}
    trd = trd.assign(slug=trd.asset.map(tok2slug))
    trades = {k: np.sort(v.recv.values) for k, v in trd.groupby("slug")}
    S = {}
    for a, bs, cs in (("bitcoin", "BTCUSDT", "btc/usd"), ("ethereum", "ETHUSDT", "eth/usd")):
        b = ref[(ref.src == "binance_bt") & (ref.sym == bs)].sort_values("recv")
        c = ref[(ref.src == "chainlink") & (ref.sym == cs)].sort_values("recv")
        S[a] = {"binance": np.log(binned(b.recv.values, b.price.values, lo, n)),
                "chainlink": np.log(binned(c.recv.values, c.price.values, lo, n))}
    imp_rows, summ = [], {"bin_s": BIN, "window": [float(lo), float(hi)]}
    # sensitivity dP/dlnS from the 1-s grid (Binance-type approximation for all kinds)
    G = G.assign(delta=norm.pdf(norm.ppf(G.fair.clip(1e-4, 1 - 1e-4))) / (G.sig * np.sqrt(G.tau.clip(lower=1))))
    acc = {}
    for m in md.itertuples():
        g = G[G.slug == m.slug].sort_values("t")
        if len(g) < 120:
            continue
        q = quotes[quotes.asset == m.tok0].sort_values("recv")
        q = q[q.bid.notna() & q.ask.notna() & ((q.ask - q.bid) <= 0.05)]
        if len(q) < 50:
            continue
        mid = binned(q.recv.values, ((q.bid + q.ask) / 2).values, lo, n)
        dlt = binned(g.t.values, g.delta.values, lo, n)
        tau = binned(g.t.values, g.tau.values, lo, n)
        fair = binned(g.t.values, g.fair.values, lo, n)
        active = ~np.isnan(dlt) & ~np.isnan(mid) & (tau > 30) & (fair > 0.05) & (fair < 0.95)
        # the market's own window only (binned() forward-fills past the window end)
        b0, b1 = int((g.t.min() - lo) / BIN), int((g.t.max() - lo) / BIN)
        active[:b0] = False
        active[b1 + 1:] = False
        y = np.diff(mid, prepend=np.nan)
        for src in ("binance", "chainlink"):
            x = np.diff(S[m.asset][src], prepend=np.nan) * dlt
            key = (m.asset, m.kind if m.kind in ("5m", "15m") else "1h+", src)
            L = KMAX - KMIN + 1
            a = acc.setdefault(key, {"XtX": np.zeros((L, L)), "Xty": np.zeros(L), "n": 0, "markets": 0})
            xs = np.where(~np.isnan(x), x, 0.0)
            ys = np.where(~np.isnan(y), y, 0.0)
            rows_ = np.where(active)[0]
            rows_ = rows_[(rows_ - KMAX >= 0) & (rows_ - KMIN < n)]
            if len(rows_) < 100:
                continue
            # y_t = sum_k beta_k x_{t-k}, k in [KMIN, KMAX]  (k > 0: spot moved k bins BEFORE the Polymarket change)
            X = np.stack([xs[rows_ - k] for k in range(KMIN, KMAX + 1)], axis=1)
            a["XtX"] += X.T @ X
            a["Xty"] += X.T @ ys[rows_]
            a["n"] += int(len(rows_))
            a["markets"] += 1
    for key, a in acc.items():
        if a["n"] < 500:
            continue
        beta = np.linalg.lstsq(a["XtX"], a["Xty"], rcond=None)[0]
        cum = np.cumsum(beta)
        ks = np.arange(KMIN, KMAX + 1)
        c0 = cum[ks == -1][0]  # cumulative up to just before 0
        tot = cum[-1]
        r = {"asset": key[0], "kind": key[1], "src": key[2], "bins": a["n"], "markets": a["markets"], "total_resp_15s": float(tot)}
        for h in (0, 0.2, 0.6, 1, 2, 3, 5, 10, 15):
            r[f"cum_{h}s"] = float(cum[ks == int(round(h / BIN))][0])
        r["pre_0"] = float(c0)
        rel = (cum - c0) / (tot - c0) if (tot - c0) != 0 else cum * np.nan
        for f in (0.5, 0.9):
            hit = np.where((ks >= 0) & (rel >= f))[0]
            r[f"t_{int(f*100)}pct_s"] = float(ks[hit[0]] * BIN) if len(hit) else None
        imp_rows.append(r)
    imp = pd.DataFrame(imp_rows)
    imp.to_parquet(f"{D}live_{TAG}_impulse.parquet")
    summ["impulse"] = imp.round(3).to_dict("records")

    # Binance -> Chainlink delay (how fast the resolution-source stream reflects Binance)
    cl = {}
    for a in S:
        xb = np.diff(S[a]["binance"], prepend=np.nan)
        yc = np.diff(S[a]["chainlink"], prepend=np.nan)
        ok = ~np.isnan(xb)
        xb0 = np.where(ok, xb, 0.0)
        yc0 = np.where(~np.isnan(yc), yc, 0.0)
        rr = np.arange(max(KMAX, 50), n + min(KMIN, 0))
        X = np.stack([xb0[rr - k] for k in range(KMIN, 51)], axis=1)
        beta = np.linalg.lstsq(X.T @ X, X.T @ yc0[rr], rcond=None)[0]
        cum = np.cumsum(beta)
        ks = np.arange(KMIN, 51)
        cl[a] = {f"cum_{h}s": float(cum[ks == int(round(h / BIN))][0]) for h in (0, 0.6, 1, 2, 3, 4, 6, 10)}
    summ["binance_to_chainlink"] = cl

    # Event studies. A (pre-registered): |10-s Binance log return| >= 3 sigma_10s. B (fast shock, OpenMarket-like): |1-s return| >= 4 sigma_1s.
    for evname, WS, KSIG in (("events", 10.0, 3.0), ("events_fast1s", 1.0, 4.0)):
        ev = event_study(S, G, md, quotes, lo, WS, KSIG, trades)
        ev.to_parquet(f"{D}live_{TAG}_{evname}.parquet")
        if len(ev):
            summ[evname] = {"window_s": WS, "k_sigma": KSIG, "n_spot_events": int(ev.te.nunique()), "n_market_events": int(len(ev)),
                            "share_moved_within_30s": float(ev.lat_s.notna().mean()),
                            "lat_quantiles_s": ev.lat_s.dropna().quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(3).to_dict(),
                            "share_moved_before_threshold": float((ev.lat_s.dropna() < 0).mean()),
                            "by_kind_median_lat": ev.groupby("kind").lat_s.median().round(3).to_dict(),
                            "round_trip_after_fees_mean": {c: float(ev[c].mean()) for c in ev.columns if c.startswith("rt_")},
                            "round_trip_gross_mean": {c: float(ev[c].mean()) for c in ev.columns if c.startswith("gross_")},
                            "share_rt_positive": {c: float((ev[c] > 0).mean()) for c in ev.columns if c.startswith("rt_")},
                            "trade_rate_per_s": {c: float(ev[c].mean()) for c in ev.columns if c.startswith("tr_")}}
    json.dump(summ, open(f"{D}live_{TAG}_lag_summary.json", "w"), indent=1, default=str)
    print(json.dumps(summ, indent=1, default=str)[:5000])


if __name__ == "__main__":
    main()
