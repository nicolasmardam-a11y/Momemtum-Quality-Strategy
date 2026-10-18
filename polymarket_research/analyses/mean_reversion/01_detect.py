"""Family F, step 1: detect price shocks on the taker tapes and measure tradable reversal outcomes.

Pre-registered in notes/strategies/mean_reversion.md section 0. Everything used to define a shock or its
features is timestamped at or before t_det. Outcomes use prints after t_det + delay only.

Output: data/derived/mr_shocks.parquet (one row per shock x variant, features) and
        data/derived/mr_trades.parquet (one row per shock x variant x delay x exit horizon, raw prices; costs in 03).
Run: python analyses/mean_reversion/01_detect.py
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "derived"
OUT = Path(__file__).resolve().parent / "out"

THETAS = [0.05, 0.10, 0.15]
DELAYS = [30, 120, 900]
HORIZONS = {"15m": 900, "1h": 3600, "6h": 21600, "24h": 86400}
VARIANTS = {  # name: (final-hour clock, price band on post-shock p0)
    "primary": ("sched", True),
    "lookahead_res": ("res", True),
    "noband": ("sched", False),
}
SPLIT_EDGES = (pd.Timestamp("2025-07-01", tz="UTC").timestamp(), pd.Timestamp("2026-01-01", tz="UTC").timestamp(),
               pd.Timestamp("2026-10-16", tz="UTC").timestamp())


def split_of(ts):
    return np.where(ts < SPLIT_EDGES[0], "train", np.where(ts < SPLIT_EDGES[1], "validation",
                    np.where(ts < SPLIT_EDGES[2], "test", "after")))


def load():
    cov = pd.read_parquet(D / "tapes" / "coverage.parquet")
    liquid = set(cov.loc[cov.set == "liquid", "condition_id"])
    parts = []
    for f in sorted(glob.glob(str(D / "tapes" / "tape_*.parquet"))):
        t = pd.read_parquet(f)
        t = t[t.condition_id.isin(liquid)]
        t["api_pos"] = np.arange(len(t))  # API order: newest first, used to break same-second ties
        parts.append(t)
    T = pd.concat(parts, ignore_index=True)
    ps = pd.read_parquet(D / "panel_sample.parquet")
    keep = ["condition_id", "token_id_0", "event_id", "cluster_id", "category", "structure", "negRisk", "endDate",
            "closedTime", "ref_ts", "gameStartTime", "y0", "feeType", "fee_rate", "fee_exponent", "split", "volumeNum",
            "early_close", "question"]
    M = ps.loc[ps.condition_id.isin(liquid), keep].set_index("condition_id")
    return T, M


def detect_market(g: pd.DataFrame, meta: pd.Series):
    g = g.sort_values(["timestamp", "api_pos"], ascending=[True, False])
    ts = g.timestamp.to_numpy(np.int64)
    oi = g.outcome_index.to_numpy()
    price = g.price.to_numpy(float)
    p0 = np.where(oi == 0, price, 1.0 - price)
    buy = (g.side.to_numpy() == "BUY")
    d0 = np.where(buy == (oi == 0), 1, -1)  # +1: pressure up on token 0 (ask-type for token 0)
    shares = g["size"].to_numpy(float)
    notional = shares * price
    wallet = g.proxy_wallet.to_numpy()
    txh = g.transaction_hash.to_numpy()
    n = len(ts)
    if n < 30:
        return []
    cumnot = np.concatenate([[0.0], np.cumsum(notional)])
    end_s = meta.endDate.timestamp()
    close_s = (meta.closedTime if pd.notna(meta.closedTime) else meta.endDate).timestamp()
    ref_s = meta.ref_ts.timestamp()
    gst = meta.gameStartTime.timestamp() if pd.notna(meta.gameStartTime) else np.nan

    # vectorised anchors
    j_last = np.searchsorted(ts, ts - 300, side="right") - 1          # last print <= t-300
    lo35 = np.searchsorted(ts, ts - 2100, side="left")               # first print >= t-2100
    lo24 = np.searchsorted(ts, ts - 300 - 86400, side="left")
    n_ref = j_last + 1 - lo35
    n_24 = j_last + 1 - lo24
    not_before = cumnot[np.maximum(j_last + 1, 0)]
    ok_act = (j_last >= 0) & (n_ref >= 3) & (n_24 >= 20) & (not_before >= 5000)
    a_last = np.where(j_last >= 0, p0[np.maximum(j_last, 0)], np.nan)
    dl = p0 - a_last
    cand = np.where(ok_act & (np.abs(dl) >= min(THETAS) - 1e-9))[0]
    if len(cand) == 0:
        return []
    a_med = np.full(n, np.nan)
    for i in cand:
        a_med[i] = np.median(p0[lo35[i]:j_last[i] + 1])
    dm = p0 - a_med

    out = []
    cache = {}
    for theta in THETAS:
        sh = cand[(np.sign(dl[cand]) == np.sign(dm[cand])) & (np.abs(dl[cand]) >= theta - 1e-9)
                  & (np.abs(dm[cand]) >= theta - 1e-9)]
        for vname, (clock, band) in VARIANTS.items():
            lim = (end_s if clock == "sched" else ref_s) - 3600
            last_acc = -1e18
            for i in sh:
                t = ts[i]
                if t > lim or t <= last_acc + 3600:
                    continue
                if band and not (0.05 <= p0[i] <= 0.95):
                    continue
                last_acc = t
                if i not in cache:
                    cache[i] = make_row(i, theta, vname, ts, p0, d0, notional, shares, wallet, txh, a_last, a_med,
                                        n_24, not_before, meta, end_s, close_s, gst)
                r = dict(cache[i]); r["theta"] = theta; r["variant"] = vname
                r["_trades"] = [{**tr, "theta": theta, "variant": vname} for tr in cache[i]["_trades"]]
                out.append(r)
    return out


def make_row(i, theta, vname, ts, p0, d0, notional, shares, wallet, txh, a_last, a_med, n_24, not_before, meta, end_s,
             close_s, gst):
    t = ts[i]
    s = int(np.sign(p0[i] - a_med[i]))
    w0 = np.searchsorted(ts, t - 300, side="right")  # window (t-300, t]
    w1 = i + 1
    win = slice(w0, w1)
    dwin = d0[win]
    same = dwin == s
    nw = notional[win]
    tot_same = nw[same].sum()
    if tot_same > 0:
        sw = pd.Series(nw[same]).groupby(wallet[win][same]).sum()
        st = pd.Series(nw[same]).groupby(txh[win][same]).sum()
        top_w, top_tx = sw.max() / tot_same, st.max() / tot_same
    else:
        top_w = top_tx = np.nan
    # move attribution: price steps inside the window attributed to the print's wallet
    pw = p0[max(w0 - 1, 0):w1]
    steps = np.diff(pw) * s if w0 > 0 else np.diff(np.concatenate([[p0[w0]], p0[win]])) * s
    wsteps = wallet[win][-len(steps):]
    pos = steps.clip(min=0)
    move_top = (pd.Series(pos).groupby(wsteps).sum().max() / pos.sum()) if pos.sum() > 0 else np.nan
    # prior volatility: 5-min grid of last p0 over (t-300-86400, t-300]
    grid = t - 300 - np.arange(288, -1, -1) * 300
    gi = np.searchsorted(ts, grid, side="right") - 1
    gp = np.where(gi >= 0, p0[np.maximum(gi, 0)], np.nan)
    vol24 = np.nanstd(np.diff(gp)) if np.isfinite(gp).sum() > 10 else np.nan
    if np.isnan(gst):
        phase = "no_game"
    elif t < gst - 3600:
        phase = "pre_game"
    elif t < gst:
        phase = "last_hour_pre"
    elif t < gst + 4 * 3600:
        phase = "in_play"
    else:
        phase = "post_game"
    row = dict(condition_id=meta.name, theta=theta, variant=vname, t_det=int(t), s=s, p0_det=p0[i],
               anchor_last=a_last[i], anchor_med=a_med[i], shock=p0[i] - a_med[i],
               n_trades_win=int(w1 - w0), n_takers_win=int(len(set(wallet[win]))),
               n_takers_same=int(len(set(wallet[win][same]))), notional_win=float(nw.sum()),
               notional_same=float(tot_same), top_wallet_share=top_w, top_tx_share=top_tx, move_top_wallet=move_top,
               n_24h=int(n_24[i]), notional_before=float(not_before[i]), vol24=vol24, phase=phase,
               hrs_to_end=(end_s - t) / 3600, hrs_to_game=((gst - t) / 3600) if not np.isnan(gst) else np.nan,
               hour_utc=int(pd.Timestamp(t, unit="s").hour), minute=int(pd.Timestamp(t, unit="s").minute),
               close_s=close_s)
    # outcomes per delay
    trades = []
    n = len(ts)
    conv = (lambda x: x) if s == -1 else (lambda x: 1.0 - x)  # reversal-token price from p0
    pay = meta.y0 if s == -1 else 1.0 - meta.y0
    for delay in DELAYS:
        e = np.searchsorted(ts, t + delay, side="left")
        base = dict(condition_id=meta.name, theta=theta, variant=vname, t_det=int(t), delay=delay)
        if e >= n or ts[e] > t + delay + 1800 or ts[e] >= close_s:
            trades.append({**base, "entered": False})
            continue
        te = ts[e]
        qe = conv(p0[e])
        # local spread around entry (+-60 s): ask-type prints for the reversal token have d0 == -s
        l0, l1 = np.searchsorted(ts, te - 60, "left"), np.searchsorted(ts, te + 60, "right")
        qa = conv(p0[l0:l1][d0[l0:l1] == -s]); qb = conv(p0[l0:l1][d0[l0:l1] == s])
        loc_hs = (np.median(qa) - np.median(qb)) / 2 if len(qa) and len(qb) else np.nan
        c1 = np.searchsorted(ts, te + 300, "right")
        sl = slice(e, c1)
        qq = conv(p0[sl]); mask = (d0[sl] == -s) & (qq <= qe + 0.01 + 1e-9)
        cap5 = float((shares[sl] * qq)[mask].sum())  # reversal-token notional bought by other takers within 1c
        tr = {**base, "entered": True, "t_entry": int(te), "q_entry": qe, "entry_ask_type": bool(d0[e] == -s),
              "loc_hs": loc_hs, "cap5m_rev_notional": cap5, "payout": pay}
        for hn, h in HORIZONS.items():
            x = np.searchsorted(ts, te + h, side="left")
            if x < n and ts[x] < close_s:
                tr[f"q_{hn}"] = conv(p0[x]); tr[f"t_{hn}"] = int(ts[x]); tr[f"res_{hn}"] = False
            else:
                tr[f"q_{hn}"] = pay; tr[f"t_{hn}"] = int(close_s); tr[f"res_{hn}"] = True
        trades.append(tr)
    row["_trades"] = trades
    return row


def main():
    T, M = load()
    print(f"tape rows {len(T):,} markets {T.condition_id.nunique():,} meta {len(M):,}", flush=True)
    rows = []
    for k, (cid, g) in enumerate(T.groupby("condition_id", sort=False)):
        if cid not in M.index:
            continue
        rows += detect_market(g, M.loc[cid])
        if k % 200 == 0:
            print(k, len(rows), flush=True)
    trades = [tr for r in rows for tr in r.pop("_trades")]
    S = pd.DataFrame(rows)
    S = S.merge(M.reset_index(), on="condition_id", how="left")
    S["split_t"] = split_of(S.t_det.to_numpy())
    S["week"] = pd.to_datetime(S.t_det, unit="s", utc=True).dt.strftime("%G-W%V")
    X = pd.DataFrame(trades)
    S.to_parquet(D / "mr_shocks.parquet", index=False)
    X.to_parquet(D / "mr_trades.parquet", index=False)
    summ = S.groupby(["variant", "theta", "split_t"]).size().unstack().fillna(0).astype(int)
    print(summ.to_string())
    (OUT / "01_counts.json").write_text(json.dumps({str(k): v for k, v in summ.to_dict(orient="index").items()}, indent=1))


if __name__ == "__main__":
    main()
