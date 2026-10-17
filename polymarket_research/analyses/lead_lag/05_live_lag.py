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
BIN = 0.1
KMAX = 300   # 30 s
KMIN = -20   # -2 s


def load(kind):
    fs = sorted(glob.glob(f"{D}live_{TAG}_[0-9][0-9]_{kind}.parquet"))
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)


def binned(t, v, lo, n):
    b = np.floor((t - lo) / BIN).astype(int)
    ok = (b >= 0) & (b < n)
    s = pd.Series(v[ok], index=b[ok]).groupby(level=0).last()
    return s.reindex(range(n)).ffill().values


def main():
    ref, tob = load("ref"), load("tob")
    G = pd.read_parquet(f"{D}live_{TAG}_grid.parquet")
    md = pd.read_parquet(f"{D}live_{TAG}_meta.parquet")
    lo, hi = G.t.min(), G.t.max()
    n = int((hi - lo) / BIN) + 1
    quotes = tob[tob.bid_sz.notna()]
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
            a = acc.setdefault(key, {"num": np.zeros(KMAX - KMIN + 1), "den": 0.0, "n": 0, "markets": 0})
            xs = np.where(active & ~np.isnan(x), x, 0.0)
            ys = np.where(~np.isnan(y), y, 0.0)
            a["den"] += float((xs ** 2).sum())
            for i, k in enumerate(range(KMIN, KMAX + 1)):
                if k >= 0:
                    a["num"][i] += float((xs[: n - k] * ys[k:]).sum())
                else:
                    a["num"][i] += float((xs[-k:] * ys[: n + k]).sum())
            a["n"] += int(active.sum())
            a["markets"] += 1
    for key, a in acc.items():
        beta = a["num"] / a["den"] if a["den"] > 0 else a["num"] * np.nan
        cum = np.cumsum(beta)
        ks = np.arange(KMIN, KMAX + 1)
        c0 = cum[ks == -1][0]  # cumulative up to just before 0
        tot = cum[-1]
        r = {"asset": key[0], "kind": key[1], "src": key[2], "bins": a["n"], "markets": a["markets"], "total_resp_30s": float(tot)}
        for h in (0, 0.5, 1, 2, 5, 10, 30):
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
        den = (xb0 ** 2).sum()
        beta = [float((xb0[: n - k] * yc0[k:]).sum() / den) if k >= 0 else float((xb0[-k:] * yc0[: n + k]).sum() / den) for k in range(KMIN, 101)]
        cum = np.cumsum(beta)
        ks = np.arange(KMIN, 101)
        cl[a] = {f"cum_{h}s": float(cum[ks == int(h / BIN)][0]) for h in (0, 0.5, 1, 2, 3, 5, 10)}
    summ["binance_to_chainlink"] = cl

    # Event study: >= 5 bp Binance move within 1 s; time to first >= 1-tick Polymarket mid move in that direction
    ev_rows = []
    for a in S:
        lb = S[a]["binance"]
        r1 = lb[10:] - lb[:-10]
        idx = np.where(np.abs(r1) >= 5e-4)[0] + 10
        evs, last = [], -1e9
        for i in idx:
            if i - last >= 50:
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
            for i in evs:
                te = lo + i * BIN
                gg = g[(g.t >= te - 1) & (g.t <= te + 1)]
                if gg.empty or not (0.1 < gg.fair.iloc[0] < 0.9) or gg.tau.iloc[0] < 30:
                    continue
                sgn = np.sign(lb[i] - lb[i - 10])
                j0 = np.searchsorted(qt, te - 1.0)  # mid 1 s before the threshold crossing
                if j0 == 0:
                    continue
                m0 = qm[j0 - 1]
                after = np.where((qt >= te - 1.0) & (qt <= te + 30) & (sgn * (qm - m0) >= 0.0099))[0]
                ev_rows.append({"asset": a, "slug": m.slug, "kind": m.kind, "te": te, "ret_bp": float((lb[i] - lb[i - 10]) * 1e4),
                                "lat_s": float(qt[after[0]] - te) if len(after) else None, "fair": float(gg.fair.iloc[0])})
    ev = pd.DataFrame(ev_rows)
    ev.to_parquet(f"{D}live_{TAG}_events.parquet")
    if len(ev):
        summ["events"] = {"n_spot_events": int(ev.te.nunique()), "n_market_events": int(len(ev)),
                          "share_moved_within_30s": float(ev.lat_s.notna().mean()),
                          "lat_quantiles_s": ev.lat_s.dropna().quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(3).to_dict(),
                          "share_moved_before_threshold": float((ev.lat_s.dropna() < 0).mean()),
                          "by_kind_median_lat": ev.groupby("kind").lat_s.median().round(3).to_dict()}
    json.dump(summ, open(f"{D}live_{TAG}_lag_summary.json", "w"), indent=1, default=str)
    print(json.dumps(summ, indent=1, default=str)[:5000])


if __name__ == "__main__":
    main()
