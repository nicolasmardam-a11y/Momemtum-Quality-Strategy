"""Reviewer: point-in-time (PIT) screen status of each wallet at each of its own entry signals.

A follower can only copy a wallet that has already passed the screen, using markets resolved (Gamma closedTime)
before the signal. For each market-episode signal (first fill of a wallet on a market), count the wallet's resolved
decisions before that time, per market and per match, and their outcome-won / made-money status. Output:
data/derived/review_pit_screen.parquet
"""
from __future__ import annotations
import json
import pandas as pd

m = pd.read_parquet("data/derived/review_pnl_markets.parquet")
m["match"] = m.events.map(lambda s: json.loads(s)[0].replace("-more-markets", ""))
m["closed"] = pd.to_datetime(m.closedTime, utc=True)
m["t0"] = pd.to_datetime(m.t0, unit="s", utc=True)
rows = []
for w, g in m.groupby("wallet"):
    for _, s in g.sort_values("t0").iterrows():
        prior = g[g.closed < s.t0]
        ev = prior.groupby("match").agg(won=("won", "all"), pnl=("realised", "sum"))
        def st(n, k):
            return ("PASS" if n == 5 and k == 5 else "fail") + "/" + ("PASS" if n >= 5 and k == n else "fail")
        rows.append(dict(wallet=w, signal=s.question, t0=s.t0, prior_mk=len(prior), prior_mk_won=int(prior.won.sum()),
                         prior_ev=len(ev), prior_ev_money=int((ev.pnl > 0).sum()), prior_realised=prior.realised.sum(),
                         screen_market=st(len(prior), int(prior.won.sum())), screen_event=st(len(ev), int((ev.pnl > 0).sum()))))
    last_close = g.closed.max()
    full = g.groupby("match").realised.sum()
    rows.append(dict(wallet=w, signal="(after last resolution; no later trades)", t0=last_close, prior_mk=len(g), prior_mk_won=int(g.won.sum()),
                     prior_ev=len(full), prior_ev_money=int((full > 0).sum()), prior_realised=g.realised.sum(),
                     screen_market=("PASS" if len(g) == 5 and g.won.all() else "fail") + "/" + ("PASS" if len(g) >= 5 and g.won.all() else "fail"),
                     screen_event=("PASS" if len(full) == 5 and (full > 0).all() else "fail") + "/" + ("PASS" if len(full) >= 5 and (full > 0).all() else "fail")))
d = pd.DataFrame(rows)
d.to_parquet("data/derived/review_pit_screen.parquet")
pd.set_option("display.width", 220)
print(d.assign(signal=d.signal.str[:34], prior_realised=d.prior_realised.round(0)).to_string())
