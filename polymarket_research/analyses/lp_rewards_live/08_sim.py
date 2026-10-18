"""Simulated passive two-sided quoting on the captured websocket data (pre-registered rules, notes section 0.2).

Every 60 s per market: cancel and re-post a YES bid at the best bid and a YES ask (== NO bid) at the best ask,
size N = max(rewardsMinSize, capital / (bb + 1 - ba)) shares, only if 0.10 <= mid <= 0.90 and both quotes are
within rewardsMaxSpread (cents) of the mid. We join the BACK of the queue: queue_ahead = displayed touch size.
PRIMARY (conservative) fill rule: queue_ahead falls only with prints at our price on our side; we fill with the
excess; a print beyond our price fills the remainder; no fill within 1 s of posting.
SENSITIVITY (optimistic): cancels at our price also advance us pro rata (queue_ahead *= 1 - cancel/level size).
Inventory cap 2N: beyond it only the reducing side is quoted. P&L: spread capture vs mid at fill, 60 s adverse
selection, residual inventory MTM to the final mid, liquidation cost (half spread + taker fee), and - separately -
liquidity rewards (from the 60 s REST books, central / conservative competitor bounds) and a maker-rebate upper bound.

Usage: python -m analyses.lp_rewards_live.08_sim w1 w2 -> data/derived/lp_rewards_live/sim_{fills,summary}.parquet
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
REQUOTE = 60.0
LAT = 1.0
CAPS = (500, 2500, 10000)


def load(lab):
    f = OUT / ("ws_markets.parquet" if lab == "w1" else f"ws_markets_{lab}.parquet")
    return (pd.read_parquet(OUT / f"trades_{lab}.parquet"), pd.read_parquet(OUT / f"tob_{lab}.parquet"),
            pd.read_parquet(OUT / f"lvl_{lab}.parquet"), pd.read_parquet(f), pd.read_parquet(OUT / f"rest_books_{lab}.parquet"))


def rest_rewards(rest, m, posts):
    """Reward accrual per REST sample (60 s) while our quote is live: our Q vs competitors' Q from the REST book.
    posts: list of (t_post, t_cancel, pb, pa, n). Returns (central $, conservative $, samples quoting, samples)."""
    rb = rest[rest.asset_id == m.yes_token].sort_values("snap_utc")
    v, ms, rate = float(m.rewards_max_spread or 0), float(m.rewards_min_size or 0), float(m.total_daily_rate or 0)
    cen = con = 0.0
    k = 0
    for r in rb.itertuples():
        live = [p for p in posts if p[0] <= r.snap_utc < p[1]]
        if not live or not v:
            continue
        _, _, pb, pa, n = live[-1]
        bids, asks = [tuple(x) for x in json.loads(r.bids)], [tuple(x) for x in json.loads(r.asks)]
        am = lp.adj_mid(lp.with_order(bids, pb, n, True), lp.with_order(asks, pa, n, False), ms, "cum")
        if am is None or n < ms:
            continue
        mid = am[2]
        q1c, q2c = lp.side_score(bids, mid, v, "bid"), lp.side_score(asks, mid, v, "ask")
        # our order is already part of the REST book only if it existed; it does not (virtual), so add it
        q1o, q2o = lp.S(v, max(0.0, (mid - pb) * 100)) * n, lp.S(v, max(0.0, (pa - mid) * 100)) * n
        qo = lp.qmin(q1o, q2o, mid)
        _, c_cen, c_con = lp.comp_qmin(q1c, q2c, mid)
        if qo > 0:
            cen += rate / 1440 * qo / (qo + c_cen)
            con += rate / 1440 * qo / (qo + c_con)
            k += 1
    return cen, con, k, len(rb)


def sim_market(c, m, tr, tb, lv, cap, rule="conservative"):
    optimistic = rule == "optimistic"
    keep = rule == "keep_queue"   # SENSITIVITY (added after pre-registration): keep queue place if the touch price is unchanged
    reactive = rule == "reactive"  # SENSITIVITY (added after pre-registration): cancel 1 s after our price level empties publicly
    ttcap = rule == "tt_capped"    # SENSITIVITY (added 2026-10-18 after w1-w3 results): a trade-through fills at most the printed size
    prev = {}
    tb = tb.sort_values("t")
    tb = tb[tb.bb.notna() & tb.ba.notna()]
    if len(tb) < 2:
        return [], [], None
    ts, bb, ba, bsz, asz = tb.t.to_numpy(), tb.bb.to_numpy(), tb.ba.to_numpy(), tb.bsz.to_numpy(), tb.asz.to_numpy()
    tr = tr.sort_values("t")
    lv = lv[(lv.new < lv.old)].sort_values("t")
    v = float(m.rewards_max_spread or 0)
    ms = float(m.rewards_min_size or 0)
    fee, reb = float(m.fee_rate or 0), float(m.rebate_rate or 0) if pd.notna(m.rebate_rate) else 0.0
    t0, t1 = ts[0] + 30, ts[-1]

    def tob_at(t):
        i = np.searchsorted(ts, t, side="right") - 1
        return (bb[i], ba[i], bsz[i], asz[i]) if i >= 0 else (np.nan,) * 4

    inv, cash = 0.0, 0.0
    cnt = {"touch_prints": 0, "touch_prints_filled": 0, "touch_vol": 0.0, "tt_prints": 0}  # instrumentation only
    fills, posts = [], []
    tq = t0
    tr_t, tr_p, tr_s, tr_side = tr.t.to_numpy(), tr.price.to_numpy(), tr["size"].to_numpy(), tr.taker_side.to_numpy()
    lv_t, lv_p, lv_side, lv_old, lv_new = lv.t.to_numpy(), lv.price.to_numpy(), lv.side.to_numpy(), lv.old.to_numpy(), lv.new.to_numpy()
    while tq < t1:
        tend = min(tq + REQUOTE, t1)
        b, a, bs, as_ = tob_at(tq)
        mid = (b + a) / 2
        n = max(ms, cap / (b + 1 - a)) if b == b and a == a else 0
        quote = (b == b) and (a == a) and 0.10 <= mid <= 0.90 and v > 0 and (mid - b) * 100 < v and (a - mid) * 100 < v
        orders = []
        if quote:
            if inv < 2 * n:
                o = prev.get("bid")
                orders.append(o if (keep and o and abs(o["p"] - b) < 1e-9 and o["rem"] > 0) else {"side": "bid", "p": b, "rem": n, "qa": bs})
            if inv > -2 * n:
                o = prev.get("ask")
                orders.append(o if (keep and o and abs(o["p"] - a) < 1e-9 and o["rem"] > 0) else {"side": "ask", "p": a, "rem": n, "qa": as_})
            posts.append((tq, tend, b, a, n))
        prev = {o["side"]: o for o in orders}
        if orders:
            i0, i1 = np.searchsorted(tr_t, tq + LAT), np.searchsorted(tr_t, tend)
            j0, j1 = np.searchsorted(lv_t, tq + LAT), np.searchsorted(lv_t, tend)
            ev = [(tr_t[i], 0, i) for i in range(i0, i1)]
            if optimistic or reactive:
                ev += [(lv_t[j], 1, j) for j in range(j0, j1)]
            ev.sort()
            recent = []  # (t, side_consumed, price, size) prints, to net out of level decreases
            for t, kind, i in ev:
                if kind == 0:
                    p, s, sd = tr_p[i], tr_s[i], tr_side[i]
                    recent.append((t, "bids" if sd == "SELL" else "asks", p, s))
                    for o in orders:
                        if o["rem"] <= 0 or (o.get("cancel_at") is not None and t >= o["cancel_at"]):
                            continue
                        hit = (o["side"] == "bid" and sd == "SELL") or (o["side"] == "ask" and sd == "BUY")
                        if not hit:
                            continue
                        better = (o["side"] == "bid" and p < o["p"] - 1e-9) or (o["side"] == "ask" and p > o["p"] + 1e-9)
                        same = abs(p - o["p"]) < 1e-9
                        q = 0.0
                        if better:
                            cnt["tt_prints"] += 1
                            q = min(o["rem"], s) if ttcap else o["rem"]
                        elif same:
                            cnt["touch_prints"] += 1; cnt["touch_vol"] += s
                            cnt["touch_prints_filled"] += int(s - o["qa"] > 0)
                            excess = s - o["qa"]
                            o["qa"] = max(0.0, o["qa"] - s)
                            q = min(o["rem"], max(0.0, excess))
                        if q > 0:
                            o["rem"] -= q
                            sg = 1 if o["side"] == "bid" else -1
                            inv += sg * q
                            cash -= sg * q * o["p"]
                            fb, fa, _, _ = tob_at(t - 1e-6)
                            fills.append({"condition_id": c, "t": t, "side": o["side"], "price": o["p"], "qty": q, "trade_through": better,
                                          "mid_fill": (fb + fa) / 2, "cap": cap, "rule": rule})
                else:  # optimistic: cancels at our price advance the queue pro rata; reactive: pull when level empties
                    side = lv_side[i]
                    if reactive:
                        for o in orders:
                            oside = "bids" if o["side"] == "bid" else "asks"
                            if side == oside and abs(lv_p[i] - o["p"]) < 1e-9 and lv_new[i] <= 1e-9 and o.get("cancel_at") is None:
                                o["cancel_at"] = t + LAT
                        continue
                    for o in orders:
                        oside = "bids" if o["side"] == "bid" else "asks"
                        if side != oside or abs(lv_p[i] - o["p"]) > 1e-9 or o["qa"] <= 0:
                            continue
                        delta = lv_old[i] - lv_new[i]
                        tv = sum(r[3] for r in recent if r[1] == oside and abs(r[2] - o["p"]) < 1e-9 and t - r[0] <= 1.5)
                        canc = max(0.0, delta - tv)
                        if lv_old[i] > 0 and canc > 0:
                            o["qa"] = max(0.0, o["qa"] * (1 - canc / lv_old[i]))
        tq = tend
    b, a, _, _ = tob_at(t1)
    mid_end = (b + a) / 2
    liq = abs(inv) * ((a - b) / 2 + fee * mid_end * (1 - mid_end)) if inv else 0.0
    end = {"condition_id": c, "cap": cap, "rule": rule, "inv_end": inv, "cash": cash, "mid_end": mid_end,
           "mtm_pnl": cash + inv * mid_end, "liq_cost": liq, "fee_rate": fee, "rebate_rate": reb, "n_posts": len(posts),
           "hours": (t1 - t0) / 3600, **cnt}
    return fills, posts, end


def main(labels):
    allf, ends = [], []
    for lab in labels:
        tr, tb, lv, ws, rest = load(lab)
        for m in ws.itertuples():
            c = m.condition_id
            for cap in CAPS:
                for opt in ("conservative", "optimistic", "keep_queue", "reactive", "tt_capped"):
                    f, posts, end = sim_market(c, m, tr[tr.condition_id == c], tb[tb.condition_id == c], lv[lv.condition_id == c], cap, opt)
                    if end is None:
                        continue
                    if opt == "conservative":
                        cen, con, k, nsamp = rest_rewards(rest, m, posts)
                    end.update(label=lab, cls=getattr(m, "cls", None), rate=m.total_daily_rate, rew_cen=cen, rew_con=con,
                               rew_samples=k, rest_samples=nsamp, question=str(m.question)[:60])
                    ends.append(end)
                    allf += [dict(x, label=lab) for x in f]  # FIX 2026-10-18: window label (markets overlap across windows)
    F = pd.DataFrame(allf)
    E = pd.DataFrame(ends)
    if len(F):
        sys.path.insert(0, str(Path(__file__).parent))
        from importlib import import_module
        Mid = import_module("07_microstructure").Mid
        sg = np.where(F.side == "bid", 1.0, -1.0)
        F["spread_cap"] = sg * (F.mid_fill - F.price) * F.qty
        for h in (5, 60, 300):
            F[f"as{h}"] = np.nan
        for lab, idx in F.groupby("label").groups.items():   # FIX 2026-10-18: mids from the fill's own window only
            mid = Mid(pd.read_parquet(OUT / f"tob_{lab}.parquet"))
            G = F.loc[idx]
            g_sg = np.where(G.side == "bid", 1.0, -1.0)
            for h in (5, 60, 300):
                mh = np.array([np.mean(mid.at(c, t + h)) for c, t in zip(G.condition_id, G.t)])
                ok = np.array([t + h <= mid.end(c) for c, t in zip(G.condition_id, G.t)])
                F.loc[idx, f"as{h}"] = np.where(ok, g_sg * (mh - G.mid_fill) * G.qty, np.nan)
        F = F.merge(E[["label", "condition_id", "cap", "rule", "fee_rate", "rebate_rate"]], on=["label", "condition_id", "cap", "rule"],
                    how="left")
        F["rebate_ub"] = F.qty * F.fee_rate * F.price * (1 - F.price) * F.rebate_rate
    F.to_parquet(OUT / "sim_fills.parquet", index=False)
    E.to_parquet(OUT / "sim_summary.parquet", index=False)
    print("fills", len(F), "market-runs", len(E))


if __name__ == "__main__":
    main(sys.argv[1:])
