"""Stage 2, step 18: portfolio accounting for a follower (addendum A10).

Run from polymarket_research/:  python analyses/pit_wallets/18_portfolio.py
Accounts $5k / $25k / $100k. Stake 2% of the initial account per signal ($100 / $500 / $2,000), executed at the
2-minute-delay VWAP of taker BUY prints by other wallets for $100 / $500 / $2,500 (the $2,000 stake uses the $2,500
VWAP, a little conservative). At most 5% of the account in one underlying event, at most 100% deployed. Signals are
taken in time order; a signal without free cash or over the event cap is skipped (counted). Capital is locked until
the resolution-known time t_res, then the payout (1/0 per share) returns to cash. Equity = cash + cost of open
positions (no mark-to-market: no historical book), so drawdowns are realised-at-resolution drawdowns.
Runs on the sampled signal stream of each screen (a random subset of that screen's signals: rate in the output).
No annualisation: the windows are 6-12 months and capital stays locked after the window.
Output: data/derived/pit_wallets/results/portfolio.parquet
"""
from __future__ import annotations

import heapq
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from evalib import B1, RES, SCREENS, SPLITS, balanced_keep, detect_time, fee_frac, load_signals, roi_hold  # noqa: E402

ACCOUNTS = [(5000, 100, "v100"), (25000, 500, "v500"), (100000, 2000, "v2500")]
WIN = {"train": (1704067200, 1735689600), "val": (1735689600, 1751328000), "test": (1751328000, 1767225600)}
SETS = [(t, sc) for sc in SCREENS + [B1] for t in ["P", "F1", "F2"]] + [("CL", "CL")]


def run(g: pd.DataFrame, A: float, stake: float, fee: str, split: str) -> dict:
    g = g.sort_values("t_in")
    cash, open_, ev_exp = A, [], {}
    eq_t, eq_v = [WIN[split][0]], [A]
    deployed_t, deployed_v = [WIN[split][0]], [0.0]
    dep = 0.0
    taken, skip_cash, skip_event = [], 0, 0

    def release(upto):
        nonlocal cash, dep
        while open_ and open_[0][0] <= upto:
            r, i, cost, payout, ev = heapq.heappop(open_)
            cash += payout; dep -= cost; ev_exp[ev] -= cost
            eq_t.append(r); eq_v.append(cash + dep)
            deployed_t.append(r); deployed_v.append(dep)

    for row in g.itertuples():
        release(row.t_in)
        fee_usd = stake * row.ff
        if ev_exp.get(row.underlying_key, 0.0) + stake > 0.05 * A + 1e-9:
            skip_event += 1; continue
        if cash < stake + fee_usd - 1e-9:
            skip_cash += 1; continue
        cash -= stake + fee_usd
        dep += stake
        ev_exp[row.underlying_key] = ev_exp.get(row.underlying_key, 0.0) + stake
        payout = stake / row.e * row.p
        heapq.heappush(open_, (row.r, row.Index, stake, payout, row.underlying_key))
        deployed_t.append(row.t_in); deployed_v.append(dep)
        eq_t.append(row.t_in); eq_v.append(cash + dep)
        taken.append((row.Index, payout - stake - fee_usd, stake))
    release(np.inf)
    out = dict(n_signals=len(g), n_taken=len(taken), skip_cash=skip_cash, skip_event=skip_event)
    if not taken:
        return out
    tk = pd.DataFrame(taken, columns=["i", "pnl", "stake"]).set_index("i").join(
        g[["wallet", "underlying_key", "category", "vol30_120", "r"]])
    pnl, stakes = tk.pnl.sum(), tk.stake.sum()
    eq = np.array(eq_v)
    peak = np.maximum.accumulate(eq)
    dd = float(np.max((peak - eq) / peak))
    # time-weighted deployed share over the signal window and up to the last resolution
    t = np.array(deployed_t, dtype=float); v = np.array(deployed_v)
    o = np.argsort(t, kind="stable"); t, v = t[o], v[o]
    a, b = WIN[split]
    end = max(b, t[-1])

    def tw(lo, hi):
        tt = np.clip(np.append(t, hi), lo, hi)
        return float(np.sum(v * np.diff(tt)) / (hi - lo) / A) if hi > lo else np.nan

    evp = tk.groupby("underlying_key").pnl.sum().sort_values(ascending=False)
    wst = tk.groupby("wallet").stake.sum().sort_values(ascending=False)
    cat = tk.groupby("category").agg(stake=("stake", "sum"), pnl=("pnl", "sum"))
    fil = ~g.loc[tk.index, "imputed"].values
    capshare = (tk.stake / np.maximum(tk.vol30_120 * 10.0, 1e-9))[fil]
    out.update(pnl=pnl, stakes=stakes, roi_deployed=pnl / stakes, ret_committed=pnl / A, max_dd=dd,
               final_equity=float(eq[-1]), util_window=tw(a, b), util_to_last_res=tw(a, end),
               days_locked_after_window=float(max(0.0, (t[-1] - b) / 86400)),
               top5_event_share_pnl=float(evp.head(5).sum() / pnl) if pnl > 0 else np.nan,
               top5_event_share_abs=float(evp.abs().sort_values(ascending=False).head(5).sum() / evp.abs().sum()),
               top_event_pnl=float(evp.iloc[0]), worst_event_pnl=float(evp.iloc[-1]),
               n_events=int(len(evp)), n_wallets=int((wst.index != "").sum()),
               top_wallet_stake_share=float(wst.iloc[0] / stakes) if (wst.index != "").any() else np.nan,
               top5_wallet_stake_share=float(wst.head(5).sum() / stakes) if (wst.index != "").any() else np.nan,
               cat_stake_share=";".join(f"{k}:{v_ / stakes:.2f}" for k, v_ in cat.stake.items()),
               cat_pnl=";".join(f"{k}:{v_:.0f}" for k, v_ in cat.pnl.items()),
               cap_median=float(np.median(capshare)) if len(capshare) else np.nan,
               cap_share_gt25=float((capshare > 0.25).mean()) if len(capshare) else np.nan)
    return out


def main():
    s, _ = load_signals()
    rows = []
    for A, stake, model in ACCOUNTS:
        for fee in ["hist", "cur"]:
            ok, roi, raw, e, t_in = roi_hold(s, model, "120", 0.0, fee)
            det = detect_time(s, "120")
            lose_unf = ~ok & (det < s.r.values) & (s.p.values == 0)
            xa = s.assign(ok=ok, e=e, t_in=t_in, ff=fee_frac(s, e, fee), imputed=False)
            xb = s.assign(ok=lose_unf, e=1.0, t_in=det, ff=0.0, imputed=True)  # adverse bound: unfilled losers lose
            xd = xa[xa.ok]
            xv = pd.concat([xd, xb[xb.ok]])
            xk = xa[balanced_keep(s, ok, "120")]
            for split, (t, sc), (rule, x) in [(sp, ts, rx) for sp in SPLITS for ts in SETS
                                               for rx in [("drop", xd), ("bal", xk), ("adv", xv)]]:
                    g = x[(x.stype == t) & (x.screen == sc) & (x.split == split)]
                    n_all = int(((s.stype == t) & (s.screen == sc) & (s.split == split)).sum())
                    if n_all == 0:
                        continue
                    r = run(g, A, stake, fee, split)
                    r.update(account=A, stake=stake, model=model, fee=fee, split=split, stype=t, screen=sc, rule=rule,
                             n_sig_all=n_all, unfilled=n_all - len(g),
                             sample_rate=float(s[(s.stype == t) & (s.screen == sc) & (s.split == split)].rate.iloc[0]))
                    rows.append(r)
        print("account", A, "done", flush=True)
    P = pd.DataFrame(rows)
    P.to_parquet(RES / "portfolio.parquet", index=False)
    v = P[(P.split == "test") & (P.fee == "hist") & (P.stype == "P") & (P.account == 25000)]
    print(v[["rule", "screen", "n_sig_all", "n_taken", "skip_cash", "skip_event", "roi_deployed", "ret_committed",
             "max_dd", "util_window", "top5_wallet_stake_share", "cap_median"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
