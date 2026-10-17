"""Reviewer: independent re-derivation of fills, fees, redemptions and realised P&L from raw /v2 data.

Does not read any earlier derived parquet. Re-pulls /v2/activity, /v2/trades (cache=True: immutable history of
dormant wallets, identical params to ge_pull_wallets.py so cached raw responses are reused), /v2/positions and
/v2/user-stats (live), and Gamma markets (closed=true, cache=True). Writes data/derived/review_pnl_*.parquet.
"""
from __future__ import annotations
import json, sys
import pandas as pd, numpy as np
from pmr import api
from pmr.http import request_json

W = {"mintblade": "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb",
     "GRIMDRIP": "0x3f87d51f27ba6e19ec52aaeebb68559a839c742c",
     "endlessFate": "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2"}
OUT = "data/derived/"

rows_m, rows_w, fills_all = [], [], []
cids = set()
for name, a in W.items():
    act = pd.DataFrame(api.activity(a, start=1, sort_direction="ASC", exclude_deposits_withdrawals="false", cache=True))
    tall = pd.DataFrame(api.trades(user=a, taker_only=False, start=1, filter_amount=0, cache=True))
    ttak = pd.DataFrame(api.trades(user=a, taker_only=True, start=1, filter_amount=0, cache=True))
    pos = {st: pd.DataFrame(api.positions(a, status=st, cache=False)) for st in ["OPEN", "REDEEMABLE", "REDEEMABLE_LOST", "MERGEABLE", "CLOSED"]}
    us = api.user_stats(a) or {}
    atp = us.get("all_time_pnl") or {}
    for c in ["size", "usdc_size", "price"]:
        act[c] = pd.to_numeric(act[c], errors="coerce")
    for d in (tall, ttak):
        d["size"] = pd.to_numeric(d["size"]); d["price"] = pd.to_numeric(d["price"])
    types = act["type"].value_counts().to_dict()
    tr = act[act.type == "TRADE"].copy()
    # role: a taker row matches (tx, token, size, price) in the taker-only pull
    key = lambda d: d["transaction_hash"].str.lower() + "|" + d["token_id"].astype(str) + "|" + d["size"].round(6).astype(str) + "|" + d["price"].round(6).astype(str)
    tk = set(key(ttak))
    tall["taker"] = key(tall).isin(tk)
    tr["k"] = key(tr)
    tr["taker"] = tr["k"].isin(tk)
    tr["fee_impl"] = tr["usdc_size"] - tr["size"] * tr["price"]
    tr["fee_model"] = np.where(tr["taker"], tr["size"] * 0.03 * tr["price"] * (1 - tr["price"]), 0.0)
    fee_err = (tr["fee_impl"] - tr["fee_model"]).abs().max()
    sides = tr["side"].value_counts().to_dict()
    red = act[act.type == "REDEEM"]
    dep = act[act.type == "DEPOSIT"]["usdc_size"].sum(); wdr = act[act.type == "WITHDRAWAL"]["usdc_size"].sum()
    inc = act[act.type.isin(["TAKER_REBATE", "MAKER_REBATE", "REWARD"])]["usdc_size"].sum()
    other = {t: types[t] for t in types if t not in ("TRADE", "REDEEM", "DEPOSIT", "WITHDRAWAL", "TAKER_REBATE", "MAKER_REBATE", "REWARD")}
    g = tr.groupby(["condition_id", "outcome_index"]).agg(shares=("size", "sum"), cost=("usdc_size", "sum"), notional=("size", lambda s: 0),
                                                         fees=("fee_impl", "sum"), n=("size", "size"), ntak=("taker", "sum"),
                                                         t0=("timestamp", "min"), t1=("timestamp", "max"), title=("title", "first"),
                                                         outcome=("outcome", "first"), event_slug=("event_slug", "first"))
    g["notional"] = tr.assign(nn=tr["size"] * tr["price"]).groupby(["condition_id", "outcome_index"])["nn"].sum()
    g = g.reset_index()
    rd = red.groupby("condition_id").agg(redeemed_usdc=("usdc_size", "sum"), redeemed_shares=("size", "sum"), t_red=("timestamp", "max")).reset_index()
    g = g.merge(rd, on="condition_id", how="left").fillna({"redeemed_usdc": 0, "redeemed_shares": 0})
    g["wallet"] = name
    cids |= set(g.condition_id)
    # trades endpoint cross-check
    rows_w.append(dict(wallet=name, act_rows=len(act), types=json.dumps(types), other_types=json.dumps(other), sides=json.dumps(sides),
                       trades_all=len(tall), trades_taker=len(ttak), taker_subset=bool(set(key(ttak)) <= set(key(tall))),
                       act_trade_rows=len(tr), act_trade_taker=int(tr.taker.sum()), fee_formula_maxerr=float(fee_err),
                       fees_impl=float(tr.fee_impl.sum()), dep=float(dep), wdr=float(wdr), income=float(inc),
                       us_trades=us.get("trades"), us_realized_market_pnl=atp.get("realized_market_pnl"), us_fees_paid=atp.get("fees_paid"),
                       us_taker_rebate=atp.get("taker_rebate"), us_maker_rebate=atp.get("maker_rebate"), us_reward=atp.get("reward_income"),
                       us_unrealized=atp.get("unrealized_pnl"), us_deposits=atp.get("deposits"), us_withdrawals=atp.get("withdrawals"),
                       us_join=us.get("join_date"),
                       pos_counts=json.dumps({k: len(v) for k, v in pos.items()}),
                       pos_closed_realized=float(pd.to_numeric(pos["CLOSED"].get("realized_pnl", pd.Series(dtype=float))).sum()) if len(pos["CLOSED"]) else 0.0,
                       names=json.dumps(act["name"].value_counts().to_dict())))
    rows_m.append(g)
    tall["wallet"] = name
    fills_all.append(tall)
    if len(pos["CLOSED"]):
        pc = pos["CLOSED"].copy(); pc["wallet"] = name
        pc.to_parquet(OUT + f"review_pos_closed_{name}.parquet")

m = pd.concat(rows_m, ignore_index=True)
# Gamma resolution
mk = []
for cid in sorted(cids):
    r = api.gamma_markets(condition_ids=cid, closed="true", cache=True)
    mk += r
gm = pd.DataFrame([dict(condition_id=x["conditionId"], question=x["question"], outcomes=api.jlist(x.get("outcomes")),
                        prices=[float(p) for p in api.jlist(x.get("outcomePrices"))], closedTime=x.get("closedTime"),
                        gameStartTime=x.get("gameStartTime"), feeType=x.get("feeType"), feeSchedule=json.dumps(x.get("feeSchedule")),
                        uma=x.get("umaResolutionStatus"), negRisk=x.get("negRisk"), events=json.dumps([e.get("slug") for e in x.get("events") or []]),
                        sportsMarketType=x.get("sportsMarketType")) for x in mk])
m = m.merge(gm, on="condition_id", how="left")
m["payout"] = [p[int(i)] if isinstance(p, list) and len(p) > int(i) else np.nan for p, i in zip(m.prices, m.outcome_index)]
m["won"] = m.payout == 1.0
m["realised"] = m.shares * m.payout - m.cost   # resolved: payout value whether or not redeemed
m["realised_cash"] = m.redeemed_usdc - m.cost
m["unredeemed_winner_value"] = np.where(m.won, m.shares - m.redeemed_shares, 0)
m.drop(columns=["prices"]).assign(outcomes=m.outcomes.astype(str)).to_parquet(OUT + "review_pnl_markets.parquet")
w = pd.DataFrame(rows_w)
s = m.groupby("wallet").agg(n_mk=("condition_id", "nunique"), won=("won", "sum"), cost=("cost", "sum"), fees=("fees", "sum"),
                            redeemed=("redeemed_usdc", "sum"), realised=("realised", "sum"), realised_cash=("realised_cash", "sum"),
                            unred_win=("unredeemed_winner_value", "sum")).reset_index()
w = w.merge(s, on="wallet")
w.to_parquet(OUT + "review_pnl_wallets.parquet")
pd.concat(fills_all).to_parquet(OUT + "review_fills.parquet")
pd.set_option("display.width", 250)
print(w[["wallet", "act_rows", "other_types", "sides", "trades_all", "trades_taker", "taker_subset", "act_trade_taker", "fee_formula_maxerr", "pos_counts", "names"]].to_string())
print(w[["wallet", "n_mk", "won", "us_trades", "cost", "fees", "us_fees_paid", "redeemed", "realised", "realised_cash", "us_realized_market_pnl", "pos_closed_realized", "income", "us_taker_rebate", "us_maker_rebate", "us_reward", "us_unrealized", "dep", "wdr", "unred_win"]].round(2).T.to_string())
print(m[["wallet", "question", "outcome", "n", "ntak", "shares", "cost", "fees", "payout", "redeemed_usdc", "realised", "feeType"]].round(2).to_string())
print(gm[["question", "closedTime", "uma", "events"]].to_string())
