"""Microstructure stats from the replayed websocket capture: arrival rates at the touch, level depletion,
trade- vs cancel-driven queue depletion, and maker-side markouts of ALL prints (unconditional).

Usage: python -m analyses.lp_rewards_live.07_microstructure w1 w2 -> data/derived/lp_rewards_live/micro_*.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "lp_rewards_live"
H = (5, 30, 60, 300)
WIN = 1.5  # s, window to match a level decrease with a print at that price


class Mid:
    def __init__(self, tob):
        self.d = {}
        for c, g in tob.groupby("condition_id"):
            g = g.sort_values("t")
            ok = g.bb.notna() & g.ba.notna()
            g = g[ok]
            self.d[c] = (g.t.to_numpy(), g.bb.to_numpy(), g.ba.to_numpy())

    def at(self, c, t):
        if c not in self.d:
            return np.nan, np.nan
        ts, bb, ba = self.d[c]
        i = np.searchsorted(ts, t, side="right") - 1
        if i < 0:
            return np.nan, np.nan
        return bb[i], ba[i]

    def end(self, c):
        ts = self.d.get(c, (np.array([]),))[0]
        return ts[-1] if len(ts) else np.nan


def load(labels):
    tr, tb, lv, ws = [], [], [], []
    for lab in labels:
        tr.append(pd.read_parquet(OUT / f"trades_{lab}.parquet").assign(label=lab))
        tb.append(pd.read_parquet(OUT / f"tob_{lab}.parquet").assign(label=lab))
        lv.append(pd.read_parquet(OUT / f"lvl_{lab}.parquet").assign(label=lab))
        f = OUT / ("ws_markets.parquet" if lab == "w1" else f"ws_markets_{lab}.parquet")
        ws.append(pd.read_parquet(f).assign(label=lab))
    out = [pd.concat(x, ignore_index=True) for x in (tr, tb, lv, ws)]
    for d in out:  # FIX 2026-10-18: window-scoped key, a market can appear in several capture windows (w4 overlaps w1-w3)
        d["cid"] = d.condition_id
        d["condition_id"] = d.label + "|" + d.cid
    return out[0], out[1], out[2], out[3].drop_duplicates("condition_id")


def main(labels):
    tr, tb, lv, ws = load(labels)
    mid = Mid(tb)
    t_start = tb.groupby("label").t.min().to_dict()
    t_end = tb.groupby("label").t.max().to_dict()
    hours = {k: (t_end[k] - t_start[k]) / 3600 for k in t_start}
    meta = ws.set_index("condition_id")

    # ---------------- prints vs touch
    buy = tr.taker_side == "BUY"
    tr["at_touch"] = np.where(buy, np.isclose(tr.price, tr.ba), np.isclose(tr.price, tr.bb))
    tr["through"] = np.where(buy, tr.price > tr.ba + 1e-9, tr.price < tr.bb - 1e-9)
    tr["touch_sz"] = np.where(buy, tr.asz, tr.bsz)
    tr["consumes_level"] = tr.at_touch & (tr["size"] >= tr.touch_sz - 1e-9)
    tr["notional"] = tr.price * tr["size"]
    # ---------------- maker-side markouts (maker sold on taker BUY, bought on taker SELL)
    sgn = np.where(buy, -1.0, 1.0)            # maker position sign in YES
    m0 = np.array([np.mean(mid.at(c, t - 1e-6)) for c, t in zip(tr.condition_id, tr.t)])
    tr["mid0"] = m0
    tr["half_spread"] = (tr.ba - tr.bb) / 2
    tr["spread_cap"] = sgn * (m0 - tr.price)          # >0 when the maker traded on the good side of mid
    for h in H:
        mh = np.array([np.mean(mid.at(c, t + h)) for c, t in zip(tr.condition_id, tr.t)])
        valid = np.array([t + h <= mid.end(c) for c, t in zip(tr.condition_id, tr.t)])
        tr[f"mo{h}"] = np.where(valid, sgn * (mh - tr.price), np.nan)     # maker P&L per share at horizon h
        tr[f"as{h}"] = np.where(valid, sgn * (mh - m0), np.nan)           # adverse selection (<0 = against maker)
    tr.assign(mkey=tr.condition_id, condition_id=tr.cid).to_parquet(OUT / "micro_trades.parquet", index=False)

    # ---------------- level decreases at the touch: trade-driven vs cancel-driven
    lv = lv.sort_values("t")
    dec = lv[(lv.new < lv.old - 1e-9) & lv.at_best].copy()
    dec["delta"] = dec.old - dec.new
    # YES-space side consumed: taker SELL consumes bids, taker BUY consumes asks
    tr["cons_side"] = np.where(buy, "asks", "bids")
    tv = tr.groupby(["condition_id", "cons_side", "price"])
    traded = []
    for r in dec.itertuples():
        key = (r.condition_id, r.side, r.price)
        if key in tv.groups:
            g = tr.loc[tv.groups[key]]
            vol = g[(g.t >= r.t - WIN) & (g.t <= r.t + WIN)]["size"].sum()
        else:
            vol = 0.0
        traded.append(min(r.delta, vol))
    dec["by_trade"] = traded
    dec["by_cancel"] = dec.delta - dec.by_trade
    dec["depleted"] = dec.new <= 1e-9
    dec.assign(mkey=dec.condition_id, condition_id=dec.cid).to_parquet(OUT / "micro_touch_decreases.parquet", index=False)

    # ---------------- per-market table
    rows = []
    tbg = {c: g.sort_values("t") for c, g in tb.groupby("condition_id")}
    for c, g in tr.groupby("condition_id"):
        lab = meta.loc[c, "label"]
        d = dec[dec.condition_id == c]
        tq = tbg.get(c)
        if tq is not None and len(tq) > 1:
            dt = np.diff(np.r_[tq.t.to_numpy(), t_end[lab]])
            bsz_tw = np.nansum(tq.bsz.to_numpy() * dt) / dt.sum()
            asz_tw = np.nansum(tq.asz.to_numpy() * dt) / dt.sum()
        else:
            bsz_tw = asz_tw = np.nan
        vb = g[g.at_touch & (g.taker_side == "SELL")]["size"].sum() / hours[lab]
        va = g[g.at_touch & (g.taker_side == "BUY")]["size"].sum() / hours[lab]
        rows.append({"condition_id": c, "label": lab, "cls": meta.loc[c, "cls"], "question": str(meta.loc[c, "question"])[:60],
                     "hours": hours[lab], "n_trades": len(g), "trades_per_h": len(g) / hours[lab],
                     "touch_prints_per_h": g.at_touch.sum() / hours[lab], "notional_per_h": g.notional.sum() / hours[lab],
                     "share_at_touch": g.at_touch.mean(), "share_through": g.through.mean(),
                     "share_consume_level": g.consumes_level.sum() / max(1, g.at_touch.sum()),
                     "touch_dec_vol": d.delta.sum(), "touch_dec_trade_share": d.by_trade.sum() / d.delta.sum() if len(d) else np.nan,
                     "touch_depletions": d.depleted.sum(),
                     "depletions_by_trade": (d.depleted & (d.by_trade > 0)).sum(),
                     "bsz_tw": bsz_tw, "asz_tw": asz_tw, "touch_vol_bid_per_h": vb, "touch_vol_ask_per_h": va,
                     "wait_h_bid": bsz_tw / vb if vb > 0 else np.inf, "wait_h_ask": asz_tw / va if va > 0 else np.inf,
                     "med_spread": np.nanmedian(g.ba - g.bb), "mo60_mean_c": g.mo60.mean() * 100, "as60_mean_c": g.as60.mean() * 100})
    pm = pd.DataFrame(rows)
    seen = set(pm.condition_id) if len(pm) else set()
    zero = [{"condition_id": c, "label": r.label, "cls": r.cls, "question": str(r.question)[:60], "hours": hours[r.label],
             "n_trades": 0, "trades_per_h": 0.0, "touch_prints_per_h": 0.0, "notional_per_h": 0.0,
             "wait_h_bid": np.inf, "wait_h_ask": np.inf} for c, r in meta.iterrows() if c not in seen and r.label in hours]
    pm = pd.concat([pm, pd.DataFrame(zero)], ignore_index=True)
    pm["mkey"] = pm.condition_id; pm["condition_id"] = pm.mkey.str.split("|").str[1]
    pm.to_parquet(OUT / "micro_markets.parquet", index=False)
    print("hours", {k: round(v, 3) for k, v in hours.items()}, "markets with prints", int((pm.n_trades > 0).sum()), "of", len(ws))
    print("prints", len(tr), "at touch %.3f through %.3f consume-level (of touch prints) %.3f" %
          (tr.at_touch.mean(), tr.through.mean(), tr.consumes_level.sum() / max(1, tr.at_touch.sum())))
    print("touch decreases: n=%d vol=%.0f trade-share %.3f; depletions %d of which with a print %d" %
          (len(dec), dec.delta.sum(), dec.by_trade.sum() / max(1e-9, dec.delta.sum()), dec.depleted.sum(),
           (dec.depleted & (dec.by_trade > 0)).sum()))
    for h in H:
        x = tr[f"mo{h}"].dropna()
        print(f"maker markout h={h}s n={len(x)} mean {x.mean()*100:.3f}c  median {x.median()*100:.3f}c  "
              f"AS mean {tr[f'as{h}'].mean()*100:.3f}c  spread_cap mean {tr.spread_cap.mean()*100:.3f}c")


if __name__ == "__main__":
    main(sys.argv[1:])
