"""Reviewer: independent screens, distinct-event grouping, zero-edge null and capital, from review_01 outputs only.

Match key = Gamma event slug with '-more-markets' stripped (a spread lives in the '- More Markets' event of the
same match). Null: each match's final state drawn from probabilities implied by the entry VWAPs (ex fee) of the
legs on that match; nested legs are mapped to explicit goal-margin states; matches independent; exact enumeration.
"""
from __future__ import annotations
import itertools, json
import numpy as np, pandas as pd

m = pd.read_parquet("data/derived/review_pnl_markets.parquet")
f = pd.read_parquet("data/derived/review_fills.parquet")
m["match"] = m.events.map(lambda s: json.loads(s)[0].replace("-more-markets", ""))
m["vwap"] = m.notional / m.shares

# ---------------------------------------------------------------- screens
def screen(rows):
    n, k = len(rows), int(rows.sum())
    return n, k, ("PASS" if (n == 5 and k == 5) else "fail"), ("PASS" if (n >= 5 and k == n) else "fail")

out = []
def add(label, df):
    ev = df.groupby("match").agg(won_all=("won", "all"), pnl=("realised", "sum"), cost=("cost", "sum"))
    for rule, ser in [("market: outcome won", df.won), ("market: made money", df.realised > 0),
                      ("event: all legs won", ev.won_all), ("event: made money", ev.pnl > 0)]:
        n, k, s1, s2 = screen(ser)
        out.append(dict(scope=label, rule=rule, n=n, successes=k, exactly5_allwin=s1, ge5_noloss=s2))
    big = df[df.cost >= 100]
    ev2 = big.groupby("match").agg(pnl=("realised", "sum"), won_all=("won", "all"))
    for rule, ser in [("market won, stake>=$100", big.won), ("event made money, stake>=$100", ev2.pnl > 0)]:
        n, k, s1, s2 = screen(ser)
        out.append(dict(scope=label, rule=rule, n=n, successes=k, exactly5_allwin=s1, ge5_noloss=s2))

for w in ["mintblade", "GRIMDRIP", "endlessFate"]:
    add(w, m[m.wallet == w])
# cluster scenarios: same market+outcome in two wallets = one decision (P&L summed)
def merge(ws):
    d = m[m.wallet.isin(ws)].groupby(["condition_id", "outcome_index"]).agg(
        won=("won", "first"), realised=("realised", "sum"), cost=("cost", "sum"), match=("match", "first"),
        shares=("shares", "sum"), notional=("notional", "sum"), question=("question", "first"), payout=("payout", "first")).reset_index()
    return d
for ws, lab in [(["mintblade", "GRIMDRIP"], "mintblade+GRIMDRIP"), (["mintblade", "endlessFate"], "mintblade+endlessFate"),
                (["GRIMDRIP", "endlessFate"], "GRIMDRIP+endlessFate"), (["mintblade", "GRIMDRIP", "endlessFate"], "all three")]:
    add(lab, merge(ws))
scr = pd.DataFrame(out)
scr.to_parquet("data/derived/review_screens.parquet")

# ---------------------------------------------------------------- null (exact enumeration)
def leg_pays(q, outcome, state, home_first=True):
    """state = goal margin bucket for 'X vs Y' matches: one of KSA-type 4 states."""
    raise NotImplementedError

def match_dist(df):
    """Return list of (prob, pnl) for one match given a frame of legs (possibly several wallets)."""
    q = df.question.tolist()
    legs = df.to_dict("records")
    if len(legs) == 1 and not any(x["match"] in ("fifwc-ksa-ury-2026-06-15", "fifwc-cze-rsa-2026-06-18") for x in legs):
        L = legs[0]; p = L["notional"] / L["shares"]
        return [(p, L["shares"] - L["cost"]), (1 - p, -L["cost"])]
    mt = legs[0]["match"]
    if mt == "fifwc-cze-rsa-2026-06-18":
        # states: CZE win, draw, RSA win. legs: Czechia win No (pays draw, RSA), draw Yes (pays draw)
        g = {x["question"]: x for x in legs}
        a = g["Will Czechia win on 2026-06-18?"]; b = g["Will Czechia vs. South Africa end in a draw?"]
        pa, pb = a["notional"] / a["shares"], b["notional"] / b["shares"]
        P = {"draw": pb, "rsa": pa - pb, "cze": 1 - pa}
        pay = {"draw": a["shares"] + b["shares"], "rsa": a["shares"], "cze": 0}
        c = a["cost"] + b["cost"]
        return [(P[s], pay[s] - c) for s in P]
    if mt == "fifwc-ksa-ury-2026-06-15":
        # states: KSA win, draw, URU by 1, URU by 2+. legs: Uruguay win No, draw Yes, Spread URU -1.5 Saudi
        sh = {"uno": 0, "draw": 0, "spr": 0}; nt = dict(sh); c = 0
        for x in legs:
            k = {"Will Uruguay win on 2026-06-15?": "uno", "Will Saudi Arabia vs. Uruguay end in a draw?": "draw", "Spread: Uruguay (-1.5)": "spr"}[x["question"]]
            sh[k] += x["shares"]; nt[k] += x["notional"]; c += x["cost"]
        pu, pd_, ps = (nt[k] / sh[k] for k in ("uno", "draw", "spr"))
        P = {"ksa": pu - pd_, "draw": pd_, "uru1": ps - pu, "uru2": 1 - ps}
        pay = {"ksa": sh["uno"] + sh["spr"], "draw": sh["uno"] + sh["draw"] + sh["spr"], "uru1": sh["spr"], "uru2": 0}
        return [(P[s], pay[s] - c) for s in P]
    raise ValueError(mt)

def null_stats(df):
    dists = [match_dist(g) for _, g in df.groupby("match")]
    obs = df.realised.sum()
    tot = [(1.0, 0.0)]
    for d in dists:
        tot = [(p1 * p2, x1 + x2) for (p1, x1) in tot for (p2, x2) in d]
    p = np.array([t[0] for t in tot]); x = np.array([t[1] for t in tot])
    mu = (p * x).sum(); sd = np.sqrt((p * (x - mu) ** 2).sum())
    p_all_events = np.prod([sum(pp for pp, xx in d if xx > 0) for d in dists])
    return dict(n_events=len(dists), obs=obs, p_ge_obs=p[x >= obs - 1e-6].sum(), p_pos=p[x > 0].sum(), mean=mu, sd=sd,
                p_all_events_made_money=p_all_events, exp_events_made_money=sum(sum(pp for pp, xx in d if xx > 0) for d in dists))

nl = []
for w in ["mintblade", "GRIMDRIP", "endlessFate"]:
    nl.append(dict(scope=w, **null_stats(m[m.wallet == w])))
for ws, lab in [(["mintblade", "GRIMDRIP"], "mintblade+GRIMDRIP"), (["mintblade", "GRIMDRIP", "endlessFate"], "all three")]:
    nl.append(dict(scope=lab, **null_stats(merge(ws))))
# mintblade without the Mets test ticket
nl.append(dict(scope="mintblade ex Mets", **null_stats(m[(m.wallet == "mintblade") & (m.cost >= 100)])))
nul = pd.DataFrame(nl)
nul.to_parquet("data/derived/review_null.parquet")

# ---------------------------------------------------------------- capital
f["ts"] = pd.to_datetime(f.timestamp, unit="s", utc=True)
f["cost"] = f["size"] * f["price"] + np.where(f.taker, f["size"] * 0.03 * f["price"] * (1 - f["price"]), 0)
mm = m.set_index(["wallet", "condition_id"])
ev = []
for (w, cid), g in f.groupby(["wallet", "condition_id"]):
    r = mm.loc[(w, cid)]
    close = pd.Timestamp(r.closedTime); red = pd.to_datetime(r.t_red, unit="s", utc=True) if r.redeemed_usdc > 0 else pd.NaT
    for _, x in g.iterrows():
        ev.append((w, x.ts, x.cost, "fill"))
    c = g.cost.sum()
    ev.append((w, close, -c, "close"))                      # unresolved-cost view
    ev.append((w, red if pd.notna(red) else close, -c, "redeem"))  # cash-tied-up view (losers: freed at close)
E = pd.DataFrame(ev, columns=["wallet", "ts", "amt", "kind"])
cap = []
for scope, ws in [("mintblade", ["mintblade"]), ("GRIMDRIP", ["GRIMDRIP"]), ("endlessFate", ["endlessFate"]),
                  ("all three", ["mintblade", "GRIMDRIP", "endlessFate"]), ("mintblade+GRIMDRIP", ["mintblade", "GRIMDRIP"])]:
    for view in ["close", "redeem"]:
        e = E[E.wallet.isin(ws) & E.kind.isin(["fill", view])].sort_values(["ts", "amt"], ascending=[True, False])
        s = e.amt.cumsum()
        i = s.idxmax()
        cap.append(dict(scope=scope, view=("unresolved cost (to closedTime)" if view == "close" else "cash tied up (to redemption)"),
                        peak=s.max(), at=e.loc[i, "ts"]))
cap = pd.DataFrame(cap)
cap.to_parquet("data/derived/review_capital.parquet")

pd.set_option("display.width", 220)
print(scr.to_string())
print(nul.round(4).to_string())
print(cap.to_string())
