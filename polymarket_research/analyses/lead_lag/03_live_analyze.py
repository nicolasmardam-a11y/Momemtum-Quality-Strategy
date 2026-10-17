"""Analyse a live collection (live_collect.py) against the pre-registered rules in notes/strategies/lead_lag.md.

Run from polymarket_research/:  python -m analyses.lead_lag.03_live_analyze L2
Outputs (data/derived/lead_lag/):
  live_<tag>_meta.parquet        market metadata incl. strike and outcome (Gamma, after resolution)
  live_<tag>_grid.parquet        1-s grid per market: fair value, asks/bids, edges
  live_<tag>_episodes.parquet    distinct signal episodes with delayed-entry P&L and markouts
  live_<tag>_impulse.parquet     distributed-lag response of Polymarket mids to spot (100 ms bins)
  live_<tag>_summary.json
"""
from __future__ import annotations

import glob
import json
import math
import re
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

from pmr import api
from pmr.http import request_json

TAG = sys.argv[1] if len(sys.argv) > 1 else "L2"
D = "data/derived/lead_lag/"
EDGE_MIN, DELAY_S, MERGE_GAP = 0.02, 1.0, 2.0
rng = np.random.default_rng(7)


def load(kind):
    fs = sorted(glob.glob(f"{D}live_{TAG}_[0-9][0-9]_{kind}.parquet"))
    return pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True) if fs else pd.DataFrame()


def fee(p, rate=0.07):
    return rate * p * (1 - p)


# ----------------------------------------------------------------------------- metadata, strikes, outcomes
def metadata(meta):
    rows = []
    for m in meta["markets"]:
        s = m["slug"]
        r = dict(slug=s, kind=m["kind"], asset=m["asset"], start=pd.Timestamp(m["start"]).timestamp() if m["start"] else None,
                 end=pd.Timestamp(m["end"]).timestamp(), tok0=m["tokens"][0], tok1=m["tokens"][1], out0=m["outcomes"][0],
                 rate=float((m.get("fee") or {}).get("rate", 0.07)), minsize=float(m.get("minsize") or 5))
        g = api.gamma_markets(slug=s, closed="true") or api.gamma_markets(slug=s)
        gm = g[0] if g else {}
        pr = api.jlist(gm.get("outcomePrices"))
        r["closed"] = gm.get("closed")
        r["win0"] = float(pr[0]) if pr and gm.get("closed") else None
        if m["kind"] in ("5m", "15m", "4h"):
            ev = api.gamma_events(slug=s, closed="true") or api.gamma_events(slug=s)
            r["strike"] = ((ev[0].get("eventMetadata") or {}).get("priceToBeat")) if ev else None
            r["ref"] = "chainlink"
        elif m["kind"] == "1h":
            sym = "BTCUSDT" if m["asset"] == "bitcoin" else "ETHUSDT"
            k = request_json("https://data-api.binance.vision/api/v3/klines",
                             {"symbol": sym, "interval": "1h", "startTime": int(r["start"] * 1000), "limit": 1}, source="binance", cache=True)
            r["strike"] = float(k[0][1]) if k and int(k[0][0]) == int(r["start"] * 1000) else None
            r["ref"] = "binance"
        else:
            mk = re.search(r"above-([\d]+)(k?)-on", s)
            r["strike"] = float(mk.group(1)) * (1000 if mk.group(2) else 1)
            r["ref"] = "binance"
            r["start"] = r["end"] - 3600  # the deciding candle; model is valid before it too, see active window
        rows.append(r)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- volatility from Binance 1s klines
def sigma_series(sym, t0, t1):
    rows, s = [], int((t0 - 1900) * 1000)
    while s < t1 * 1000:
        j = request_json("https://data-api.binance.vision/api/v3/klines",
                         {"symbol": sym, "interval": "1s", "startTime": s, "limit": 1000}, source="binance", cache=True)
        if not j:
            break
        rows += [(int(k[0]) // 1000, float(k[4])) for k in j]
        s = int(j[-1][0]) + 1000
    k = pd.Series(dict(rows)).sort_index()
    k = k.reindex(range(k.index.min(), k.index.max() + 1)).ffill()
    r10 = np.log(k).diff(10)
    r10 = r10[(r10.index % 10) == 0]
    sd = r10.rolling(180, min_periods=60).std() / math.sqrt(10)   # per-sqrt-second, trailing 30 min of 10-s returns
    return sd.reindex(range(int(t0) - 5, int(t1) + 5)).ffill(), k


def asof(times, values, q):
    """Last value at or before each q (times sorted)."""
    idx = np.searchsorted(times, q, side="right") - 1
    out = np.where(idx >= 0, values[np.clip(idx, 0, None)], np.nan)
    return out


def fair_binance(S, K, sig, tau):
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.log(S / K) / (sig * np.sqrt(np.maximum(tau, 1e-9)))
    return norm.cdf(z)


def fair_twap(S, K, sig, t, T, cl_t, cl_v):
    """Chainlink TWAP-60s settlement: final = mean of the stream over [T-60, T]."""
    out = np.empty(len(t))
    for i, (s, sg, ti) in enumerate(zip(S, sig, t)):
        if ti <= T - 60:
            v = sg * math.sqrt((T - 60 - ti) + 20.0)
            out[i] = norm.cdf(math.log(s / K) / v) if v > 0 else float(s >= K)
        else:
            w = min(1.0, (ti - (T - 60)) / 60.0)
            m = (cl_t >= T - 60) & (cl_t <= ti)
            A = cl_v[m].mean() if m.any() else s
            mean = w * A + (1 - w) * s
            v = (1 - w) * sg * math.sqrt(max(T - ti, 0) / 3.0)
            out[i] = norm.cdf(math.log(mean / K) / v) if v > 1e-12 else float(mean >= K)
    return out


def main():
    meta = json.load(open(f"{D}live_{TAG}_markets.json"))
    md = metadata(meta)
    md.to_parquet(f"{D}live_{TAG}_meta.parquet")
    snap, ref, tob = load("snap"), load("ref"), load("tob")
    t_lo, t_hi = snap.t.min(), snap.t.max()
    print("snap", len(snap), "ref", len(ref), "tob", len(tob), "window", pd.to_datetime(t_lo, unit="s"), pd.to_datetime(t_hi, unit="s"))
    sig, k1s = {}, {}
    for a, sym in (("bitcoin", "BTCUSDT"), ("ethereum", "ETHUSDT")):
        sig[a], k1s[a] = sigma_series(sym, t_lo, t_hi)
    ref = ref.sort_values("recv")
    R = {}
    for a, bsym, csym in (("bitcoin", "BTCUSDT", "btc/usd"), ("ethereum", "ETHUSDT", "eth/usd")):
        b = ref[(ref.src == "binance_bt") & (ref.sym == bsym)]
        c = ref[(ref.src == "chainlink") & (ref.sym == csym)]
        R[a] = dict(b_t=b.recv.values, b_v=b.price.values, c_t=c.recv.values, c_v=c.price.values,
                    c_src=c.src_ts.values / 1000.0)
    snap = snap.sort_values("t")
    grids = []
    for m in md.itertuples():
        if m.strike is None or (isinstance(m.strike, float) and math.isnan(m.strike)):
            continue
        lo = max(t_lo, m.start if m.kind != "above" else t_lo)
        hi = min(t_hi, m.end - 0.5)
        if hi <= lo:
            continue
        s0 = snap[(snap.asset == m.tok0) & (snap.t >= lo) & (snap.t <= hi)].set_index("t")
        s1 = snap[(snap.asset == m.tok1) & (snap.t >= lo) & (snap.t <= hi)].set_index("t")
        g = s0[["bid", "bid_sz", "ask", "ask_sz", "ask_d1"]].join(s1[["bid", "ask", "ask_sz", "ask_d1"]], rsuffix="_1", how="inner")
        if g.empty:
            continue
        t = g.index.values
        r = R[m.asset]
        sg = sig[m.asset].reindex(np.floor(t).astype(int)).values
        if m.ref == "binance":
            S = asof(r["b_t"], r["b_v"], t)
            P = fair_binance(S, float(m.strike), sg, m.end - t)
        else:
            S = asof(r["c_t"], r["c_v"], t)
            P = fair_twap(S, float(m.strike), sg, t, m.end, r["c_src"], r["c_v"])
        g = g.assign(slug=m.slug, kind=m.kind, asset=m.asset, S=S, sig=sg, tau=m.end - t, fair=P, win0=m.win0, rate=m.rate,
                     minsize=m.minsize)
        grids.append(g.reset_index())
    G = pd.concat(grids, ignore_index=True)
    G["mid"] = (G.bid + G.ask) / 2
    G["spread"] = G.ask - G.bid
    G["edge0"] = G.fair - G.ask - fee(G.ask, G.rate)
    G["edge1"] = (1 - G.fair) - G.ask_1 - fee(G.ask_1, G.rate)
    G.to_parquet(f"{D}live_{TAG}_grid.parquet")
    print("grid rows", len(G), "markets", G.slug.nunique())

    # --------------------------------------------------------------- episodes
    eps = []
    for (slug, side), _ in [((s, sd), None) for s in G.slug.unique() for sd in (0, 1)]:
        g = G[G.slug == slug].sort_values("t").reset_index(drop=True)
        e = g.edge0 if side == 0 else g.edge1
        asz = g.ask_sz if side == 0 else g.ask_sz_1
        sig_on = (e >= EDGE_MIN) & (asz >= g.minsize)
        if not sig_on.any():
            continue
        on_t = g.t[sig_on].values
        # group into runs, merging gaps < MERGE_GAP
        starts = [0] + [i for i in range(1, len(on_t)) if on_t[i] - on_t[i - 1] > MERGE_GAP]
        ends = starts[1:] + [len(on_t)]
        for a, b in zip(starts, ends):
            t0, t1 = on_t[a], on_t[b - 1]
            row0 = g[g.t == t0].iloc[0]
            later = g[g.t >= t0 + DELAY_S - 1e-6]
            ent = later.iloc[0] if len(later) else None
            ask_c, fair_c = ("ask", "fair") if side == 0 else ("ask_1", None)
            rec = dict(slug=slug, kind=row0.kind, asset=row0.asset, side=side, t0=t0, t1=t1, dur=t1 - t0 + 1.0,
                       edge_at_t0=float(e[g.t == t0].iloc[0]), ask_t0=float(row0[ask_c]), depth_t0=float(row0["ask_sz" if side == 0 else "ask_sz_1"]),
                       depth1c_t0=float(row0["ask_d1" if side == 0 else "ask_d1_1"]), tau_t0=float(row0.tau), fair_t0=float(row0.fair),
                       spread_t0=float(row0.spread))
            win = row0.win0 if side == 0 else (1 - row0.win0 if row0.win0 is not None and not pd.isna(row0.win0) else None)
            rec["payout"] = win
            for nm, rr in (("now", row0), ("del", ent)):
                if rr is None or pd.isna(rr[ask_c]):
                    rec[f"{nm}_ok"] = False
                    continue
                p = float(rr[ask_c])
                fv = float(rr.fair) if side == 0 else 1 - float(rr.fair)
                rec[f"{nm}_ask"] = p
                rec[f"{nm}_edge"] = fv - p - fee(p, rr.rate)
                rec[f"{nm}_ok"] = rec[f"{nm}_edge"] >= 0
                rec[f"{nm}_pnl"] = (win - p - fee(p, rr.rate)) if win is not None and not pd.isna(win) else None
                for h in (5, 30, 60):
                    fut = g[g.t >= rr.t + h - 1e-6]
                    if len(fut):
                        f = fut.iloc[0]
                        bid_h = float(f.bid) if side == 0 else float(f.bid_1) if "bid_1" in f else float("nan")
                        mid_h = float(f.mid) if side == 0 else 1 - float(f.mid)
                        rec[f"{nm}_mk{h}_mid"] = mid_h - p - fee(p, rr.rate)
                        rec[f"{nm}_mk{h}_bid"] = bid_h - p - fee(p, rr.rate)
                        rec[f"{nm}_mk{h}_bidfee"] = bid_h - p - fee(p, rr.rate) - fee(bid_h, rr.rate)
            eps.append(rec)
    E = pd.DataFrame(eps)
    E.to_parquet(f"{D}live_{TAG}_episodes.parquet")

    def boot(df, col, n=2000):
        df = df[df[col].notna()]
        if df.empty:
            return (None, None, None, 0)
        mk = df.slug.unique()
        by = {s: df[df.slug == s][col].values for s in mk}
        ms = []
        for _ in range(n):
            pick = rng.choice(mk, len(mk))
            v = np.concatenate([by[s] for s in pick])
            ms.append(v.mean())
        return (float(df[col].mean()), float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5)), int(len(df)))

    summ = {"tag": TAG, "n_grid": int(len(G)), "n_markets": int(G.slug.nunique()),
            "window_utc": [str(pd.to_datetime(t_lo, unit="s")), str(pd.to_datetime(t_hi, unit="s"))]}
    if not E.empty:
        summ["episodes"] = {
            "n": int(len(E)), "by_kind": E.groupby("kind").size().to_dict(),
            "median_dur_s": float(E.dur.median()), "share_dur_ge2": float((E.dur >= 2).mean()),
            "share_survive_1s": float(E.del_ok.mean()),
            "median_edge_t0": float(E.edge_at_t0.median()), "median_depth_t0": float(E.depth_t0.median()),
            "median_depth1c_t0": float(E.depth1c_t0.median()),
            "pnl_now": boot(E, "now_pnl"), "pnl_del": boot(E, "del_pnl"),
            "pnl_del_survivors": boot(E[E.del_ok == True], "del_pnl"),  # noqa: E712
            "mk30_bid_del": boot(E, "del_mk30_bid"), "mk30_bidfee_del": boot(E, "del_mk30_bidfee"),
            "mk5_mid_del": boot(E, "del_mk5_mid"), "mk60_mid_del": boot(E, "del_mk60_mid")}
        summ["episodes_by_kind"] = {k: {"n": int(len(x)), "med_dur": float(x.dur.median()), "surv": float(x.del_ok.mean()),
                                        "pnl_del": boot(x, "del_pnl", 500)} for k, x in E.groupby("kind")}
    # R3: log-loss of fair vs mid at 10-s samples
    S10 = G[(G.t.round() % 10 == 0) & G.win0.notna() & G.mid.notna() & (G.spread <= 0.10)]
    if len(S10):
        y = S10.win0.values
        ll = lambda p: float(-np.mean(y * np.log(np.clip(p, 1e-3, 1 - 1e-3)) + (1 - y) * np.log(np.clip(1 - p, 1e-3, 1 - 1e-3))))
        summ["R3_logloss"] = {"n": int(len(S10)), "markets": int(S10.slug.nunique()), "fair": ll(S10.fair.values), "mid": ll(S10.mid.values),
                              "by_kind": {k: {"n": int(len(x)), "fair": float(-np.mean(x.win0 * np.log(np.clip(x.fair, 1e-3, 1 - 1e-3)) + (1 - x.win0) * np.log(np.clip(1 - x.fair, 1e-3, 1 - 1e-3)))),
                                              "mid": float(-np.mean(x.win0 * np.log(np.clip(x.mid, 1e-3, 1 - 1e-3)) + (1 - x.win0) * np.log(np.clip(1 - x.mid, 1e-3, 1 - 1e-3))))}
                                          for k, x in S10.groupby("kind")}}
    summ["spread_median_by_kind"] = G[G.spread.notna()].groupby("kind").spread.median().to_dict()
    tight = G[(G.spread <= 0.05) & G.fair.between(0.05, 0.95)]
    summ["fair_minus_mid_tight_by_kind"] = {k: {"n": int(len(x)), "median_abs": float((x.fair - x.mid).abs().median()),
                                                "mean": float((x.fair - x.mid).mean())} for k, x in tight.groupby("kind")}
    # strike / settlement check for Chainlink-TWAP markets: priceToBeat vs RTDS Chainlink spot averages around the start,
    # and outcome vs (next contiguous window's priceToBeat >= this priceToBeat)
    chk = []
    tw = md[md.kind.isin(["5m", "15m"]) & md.strike.notna()]
    for m in tw.itertuples():
        r = R[m.asset]
        st = r["c_src"]
        row = {"slug": m.slug, "kind": m.kind, "strike": float(m.strike), "win0": m.win0}
        for lab, a, b in (("cl_avg60", m.start - 60, m.start), ("cl_avg30", m.start - 30, m.start), ("cl_spot", m.start - 1.5, m.start)):
            mm = (st > a) & (st <= b)
            row[lab] = float(r["c_v"][mm].mean()) if mm.sum() >= (50 if lab == "cl_avg60" else 25 if lab == "cl_avg30" else 1) else None
        nxt = tw[(tw.asset == m.asset) & (tw.kind == m.kind) & (abs(tw.start - m.end) < 1)]
        row["next_strike"] = float(nxt.strike.iloc[0]) if len(nxt) else None
        chk.append(row)
    C = pd.DataFrame(chk)
    if len(C):
        for lab in ("cl_avg60", "cl_avg30", "cl_spot"):
            d = (C[lab] / C.strike - 1) * 1e4
            summ[f"strike_minus_{lab}_bp"] = {"n": int(d.notna().sum()), "median_abs": float(d.abs().median()) if d.notna().any() else None,
                                              "p90_abs": float(d.abs().quantile(0.9)) if d.notna().any() else None}
        z = C[C.next_strike.notna() & C.win0.notna()]
        summ["settlement_consistency"] = {"n": int(len(z)), "share_win_eq_next_ge_strike": float(((z.next_strike >= z.strike) == (z.win0 == 1)).mean()) if len(z) else None}
        C.to_parquet(f"{D}live_{TAG}_strikecheck.parquet")
    json.dump(summ, open(f"{D}live_{TAG}_summary.json", "w"), indent=1, default=str)
    print(json.dumps(summ, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
