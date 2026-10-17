"""Decision tables, timing, price impact, counterparties and screens for mintblade.

Inputs (all produced by mintblade_01..04 scripts, raw payloads under data/raw/):
  mintblade_trades_all / _trades_default / _activity_exdw_false / _positions / _markets
  mintblade_tape_<cid10>_{all,taker} / mintblade_prices_history
Outputs (data/derived/):
  mintblade_fills.parquet               tidy fills, maker/taker role, fee, time vs kick-off
  mintblade_decisions_market.parquet    one row per market
  mintblade_decisions_event.parquet     one row per underlying match
  mintblade_episodes.parquet            entry episodes (gap > 10 min starts a new one)
  mintblade_capital_timeline.parquet    capital deployed / at risk through time
  mintblade_counterparties.parquet      who was on the other side of each fill
  mintblade_price_windows.parquet       per-minute tape VWAP of the wallet's token, -60..+60 min
  mintblade_impact.parquet              price before/during/after each episode
Run: python analyses/wallets/mintblade_05_analysis.py
"""
from __future__ import annotations

import json
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).resolve().parents[2] / "data" / "derived"
W = "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb"
OTHERS = {"0x3f87d51f27ba6e19ec52aaeebb68559a839c742c": "GRIMDRIP",
          "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2": "endlessFate"}
MATCH = {"mlb-nym-sea-2026-06-03": "NYM-SEA 2026-06-03 (MLB)",
         "fifwc-ksa-ury-2026-06-15": "KSA-URU 2026-06-15 (WC)",
         "fifwc-ksa-ury-2026-06-15-more-markets": "KSA-URU 2026-06-15 (WC)",
         "fifwc-irn-nzl-2026-06-15": "IRN-NZL 2026-06-15 (WC)"}
# Actual kick-off inferred from goal-driven price jumps in the tape (see notes): first goal
# jump time minus (goal minute - 0.5) min. PLAUSIBLE, +-1 min. MLB first pitch from Gamma.
ACTUAL_START = {"KSA-URU 2026-06-15 (WC)": pd.Timestamp("2026-06-15 22:03:36", tz="UTC"),
                "IRN-NZL 2026-06-15 (WC)": pd.Timestamp("2026-06-16 01:04:03", tz="UTC"),
                "NYM-SEA 2026-06-03 (MLB)": pd.Timestamp("2026-06-03 19:40:00", tz="UTC")}
# Public in-play events (minute, description) from match reports (see notes for sources)
# and the UTC second of the matching price jump in the tape.
NEWS = {
    "KSA-URU 2026-06-15 (WC)": [("41'", "Saudi Arabia goal (Al-Amri) 1-0", "2026-06-15 22:44:06"),
                                ("80'", "Uruguay goal (M. Araujo) 1-1", "2026-06-15 23:45:25")],
    "IRN-NZL 2026-06-15 (WC)": [("7'", "New Zealand goal (Just) 0-1", "2026-06-16 01:10:33"),
                                ("32'", "Iran goal (Rezaeian) 1-1", "2026-06-16 01:35:42"),
                                ("53/54'", "New Zealand goal (Just) 1-2", "2026-06-16 02:21:36"),
                                ("63/64'", "Iran goal (Mohebi) 2-2", "2026-06-16 02:30:40")],
    "NYM-SEA 2026-06-03 (MLB)": [("T4", "Mets score 4 in top 4th (line score); price 0.46->0.73 in 20:40 bin", "2026-06-03 20:40:00")],
}


def load():
    t = pd.read_parquet(D / "mintblade_trades_all.parquet")
    td = pd.read_parquet(D / "mintblade_trades_default.parquet")
    act = pd.read_parquet(D / "mintblade_activity_exdw_false.parquet")
    mk = pd.read_parquet(D / "mintblade_markets.parquet")
    return t, td, act, mk


def build_fills(t, td, act, mk):
    k = ["transaction_hash", "token_id", "size", "price", "timestamp", "side"]
    f = t.merge(td[k].assign(taker=True), on=k, how="left")
    f["taker"] = f.taker.fillna(False).astype(bool)
    at = act[act.type == "TRADE"][k + ["usdc_size"]]
    f = f.merge(at, on=k, how="left", validate="one_to_one")
    f["ts"] = pd.to_datetime(f.timestamp, unit="s", utc=True)
    f["notional"] = f["size"] * f.price
    mk = mk.set_index("conditionId")
    fs = mk.feeSchedule.map(json.loads)
    f["fee_rate"] = f.condition_id.map(fs.map(lambda d: d["rate"]))
    f["fee_calc"] = np.where(f.taker, (f["size"] * f.fee_rate * f.price * (1 - f.price)).round(5), 0.0)
    f["fee_api"] = f.usdc_size - f.notional  # activity usdc_size includes the taker fee
    f["fee"] = f.fee_api.clip(lower=0)
    f["cost"] = f.usdc_size
    f["question"] = f.condition_id.map(mk.question)
    f["sportsMarketType"] = f.condition_id.map(mk.sportsMarketType)
    f["match"] = f.event_slug.map(MATCH)
    f["sched_start"] = pd.to_datetime(f.condition_id.map(mk.gameStartTime), utc=True)
    f["actual_start"] = f.match.map(ACTUAL_START)
    f["min_from_sched"] = (f.ts - f.sched_start).dt.total_seconds() / 60
    f["min_from_actual"] = (f.ts - f.actual_start).dt.total_seconds() / 60
    f["role"] = np.where(f.taker, "taker", "maker")
    keep = ["ts", "timestamp", "match", "event_slug", "condition_id", "question", "sportsMarketType", "outcome",
            "outcome_index", "side", "size", "price", "notional", "role", "fee_rate", "fee_calc", "fee_api", "fee",
            "cost", "sched_start", "actual_start", "min_from_sched", "min_from_actual", "transaction_hash", "token_id"]
    return f[keep].sort_values("timestamp").reset_index(drop=True)


def market_decisions(f, act, mk):
    mk = mk.set_index("conditionId")
    red = act[act.type == "REDEEM"].groupby("condition_id").agg(redeem_usdc=("usdc_size", "sum"),
                                                              redeem_shares=("size", "sum"),
                                                              redeem_ts=("timestamp", "max"))
    rows = []
    for c, g in f.groupby("condition_id"):
        m = mk.loc[c]
        outs, prices = json.loads(m.outcomes), [float(x) for x in json.loads(m.outcomePrices)]
        oi = int(g.outcome_index.iloc[0])
        payoff = prices[oi]
        sh = g["size"].sum()
        r = red.loc[c] if c in red.index else None
        cost = g.cost.sum()
        redeem = float(r.redeem_usdc) if r is not None else 0.0
        vwap = g.notional.sum() / sh
        fin = m.event_finishedTimestamp if isinstance(m.event_finishedTimestamp, str) else None
        rows.append({
            "match": g.match.iloc[0], "condition_id": c, "question": m.question, "sportsMarketType": m.sportsMarketType,
            "outcome": g.outcome.iloc[0], "side": "/".join(sorted(g.side.unique())), "n_fills": len(g),
            "n_taker": int((g.role == "taker").sum()), "n_maker": int((g.role == "maker").sum()),
            "first_fill": g.ts.min(), "last_fill": g.ts.max(), "shares": sh,
            "taker_shares": g.loc[g.role == "taker", "size"].sum(), "maker_shares": g.loc[g.role == "maker", "size"].sum(),
            "vwap": vwap, "vwap_incl_fee": cost / sh, "notional": g.notional.sum(), "fees": g.fee.sum(),
            "fees_calc": g.fee_calc.sum(), "cost": cost, "sells": 0.0, "merges": 0.0,
            "redeem_shares": float(r.redeem_shares) if r is not None else 0.0, "redeem_usdc": redeem,
            "redeem_ts": pd.to_datetime(r.redeem_ts, unit="s", utc=True) if r is not None else pd.NaT,
            "payoff_per_share": payoff, "chosen_outcome_won": payoff == 1.0,
            "realised_pnl": redeem - cost, "unrealised_pnl": 0.0, "open_shares": sh - (float(r.redeem_shares) if r is not None else 0.0),
            "return_on_cost": (redeem - cost) / cost, "edge_per_share": payoff - vwap,
            "edge_per_share_incl_fee": payoff - cost / sh,
            "sched_start": pd.Timestamp(m.gameStartTime, tz="UTC") if m.gameStartTime else pd.NaT,
            "game_finished": pd.Timestamp(fin) if fin else pd.NaT, "market_closed": pd.Timestamp(m.closedTime),
            "hold_h_to_redeem": ((pd.to_datetime(r.redeem_ts, unit="s", utc=True) - g.ts.min()).total_seconds() / 3600) if r is not None else np.nan,
            "feeSchedule": m.feeSchedule, "feeType": m.feeType, "secondsDelay": m.secondsDelay, "negRisk": m.negRisk,
            "umaResolutionStatus": m.umaResolutionStatus, "umaResolutionStatuses": m.umaResolutionStatuses,
            "outcomePrices": m.outcomePrices, "event_score": m.event_score,
        })
    df = pd.DataFrame(rows).sort_values("first_fill").reset_index(drop=True)
    # the "-more-markets" Gamma event carries no finishedTimestamp: use the same match's value
    df["game_finished"] = df.groupby("match").game_finished.transform(lambda s: s.fillna(s.dropna().max()))
    return df


def ksa_uru_scenarios(dm):
    """Payoff of the three KSA-URU legs across mutually exclusive final-score states."""
    legs = dm[dm.match == "KSA-URU 2026-06-15 (WC)"].set_index("question")
    pays = {  # state -> which legs pay 1
        "Saudi win": ["Will Uruguay win on 2026-06-15?", "Spread: Uruguay (-1.5)"],
        "Draw": ["Will Uruguay win on 2026-06-15?", "Spread: Uruguay (-1.5)", "Will Saudi Arabia vs. Uruguay end in a draw?"],
        "Uruguay by 1": ["Spread: Uruguay (-1.5)"],
        "Uruguay by 2+": [],
    }
    cost = legs.cost.sum()
    out = []
    for s, ls in pays.items():
        payout = sum(legs.loc[q, "shares"] for q in ls)
        out.append({"state": s, "payout": payout, "cost": cost, "pnl": payout - cost})
    return pd.DataFrame(out)




def episodes(f, gap_min=10):
    f = f.sort_values("timestamp").copy()
    new = (f.groupby("match").timestamp.diff().fillna(1e9) > gap_min * 60)
    f["episode"] = new.cumsum()
    rows = []
    for e, g in f.groupby("episode"):
        rows.append({"episode": int(e), "match": g.match.iloc[0], "markets": "; ".join(sorted(g.question.unique())),
                     "start": g.ts.min(), "end": g.ts.max(), "n_fills": len(g), "shares": g["size"].sum(),
                     "notional": g.notional.sum(), "cost": g.cost.sum(), "fees": g.fee.sum(),
                     "taker_notional": g.loc[g.role == "taker", "notional"].sum(),
                     "maker_notional": g.loc[g.role == "maker", "notional"].sum(),
                     "min_from_sched_first": g.min_from_sched.min(), "min_from_sched_last": g.min_from_sched.max(),
                     "min_from_actual_first": g.min_from_actual.min(), "min_from_actual_last": g.min_from_actual.max()})
    ep = pd.DataFrame(rows)
    return f, ep


def classify(ep):
    out = []
    for _, r in ep.iterrows():
        news = [pd.Timestamp(t, tz="UTC") for _, _, t in NEWS.get(r.match, [])]
        before = [t for t in news if t < r.end]
        if r.min_from_actual_last <= 0.5:  # last fill no later than ~30 s after inferred actual kick-off
            c = "pre-event"
        elif before:
            c = "in-play-after-public-news"
        else:
            c = "in-play-no-identified-news"
        out.append(c)
    ep["timing_class"] = out
    return ep


def capital_timeline(f, dm):
    ev = []
    for _, g in f.iterrows():
        ev.append((g.ts, g.cost, g.condition_id, "fill"))
    for _, r in dm.iterrows():
        ev.append((r.redeem_ts, -r.cost, r.condition_id, "redeem"))
    ev = pd.DataFrame(ev, columns=["ts", "d_cost", "condition_id", "kind"]).sort_values(["ts", "kind"])
    ev["capital_deployed"] = ev.d_cost.cumsum()
    # at risk: cost of positions whose game had not finished yet
    fin = dm.set_index("condition_id").game_finished
    risk = []
    for ts in ev.ts:
        held = f[(f.ts <= ts)]
        held = held[held.condition_id.map(fin) > ts]
        risk.append(held.cost.sum())
    ev["capital_at_risk"] = risk
    return ev.reset_index(drop=True)


def load_tape(cid10, kind):
    A = pd.read_parquet(D / f"mintblade_tape_{cid10}_{kind}.parquet")
    A["ts"] = pd.to_datetime(A.timestamp, unit="s", utc=True)
    return A


def counterparties(f):
    rows = []
    for c, g in f.groupby("condition_id"):
        A, T = load_tape(c[:10], "all"), load_tape(c[:10], "taker")
        taker_key = set(zip(T.transaction_hash, T.proxy_wallet))
        for tx, gg in g.groupby("transaction_hash"):
            x = A[(A.transaction_hash == tx) & (A.proxy_wallet != W)]
            role = gg.role.iloc[0]
            for _, r in x.iterrows():
                is_taker = (tx, r.proxy_wallet) in taker_key
                if role == "taker":
                    cp = "maker (counterparty)"
                else:
                    cp = "taker (counterparty)" if is_taker else "co-maker (same side)"
                rows.append({"condition_id": c, "question": gg.question.iloc[0], "tx": tx, "wallet_role": role,
                             "cp_role": cp, "cp_wallet": r.proxy_wallet, "cp_name": r["name"], "cp_side": r.side,
                             "cp_outcome": r.outcome, "cp_size": r["size"], "cp_price": r.price,
                             "candidate_wallet": OTHERS.get(r.proxy_wallet, "")})
    return pd.DataFrame(rows)


def price_windows_and_impact(f, ep):
    pw, imp = [], []
    for _, e in ep.iterrows():
        for c, g in f[(f.ts >= e.start) & (f.ts <= e.end)].groupby("condition_id"):
            T = load_tape(c[:10], "taker")
            tok = g.token_id.iloc[0]
            T["p_tok"] = np.where(T.token_id == tok, T.price, 1 - T.price)
            T["mine"] = T.proxy_wallet == W
            T["toward"] = np.where(((T.token_id == tok) & (T.side == "BUY")) | ((T.token_id != tok) & (T.side == "SELL")), 1, -1)
            lo, hi = e.start - pd.Timedelta(minutes=60), e.end + pd.Timedelta(minutes=60)
            w = T[(T.ts >= lo) & (T.ts <= hi)].copy()
            w["min_rel_start"] = ((w.ts - e.start).dt.total_seconds() // 60).astype(int)
            gm = w.groupby("min_rel_start").apply(lambda x: pd.Series({
                "vwap": (x.p_tok * x["size"]).sum() / x["size"].sum(), "shares": x["size"].sum(),
                "wallet_shares": x.loc[x.mine, "size"].sum()}), include_groups=False).reset_index()
            gm["condition_id"], gm["question"], gm["episode"] = c, g.question.iloc[0], e.episode
            pw.append(gm)

            def vw(a, b, others_only=True):
                x = T[(T.ts > a) & (T.ts <= b)]
                if others_only:
                    x = x[~x.mine]
                return (x.p_tok * x["size"]).sum() / x["size"].sum() if len(x) else np.nan

            def last_before(ts):
                x = T[(T.ts < ts) & (~T.mine)].sort_values("timestamp")
                return x.p_tok.iloc[-1] if len(x) else np.nan

            s, en = g.ts.min(), g.ts.max()
            win = T[(T.ts >= s) & (T.ts <= en)]
            imp.append({
                "episode": e.episode, "condition_id": c, "question": g.question.iloc[0], "outcome": g.outcome.iloc[0],
                "first_fill": s, "last_fill": en,
                "vwap_others_-60_-30m": vw(s - pd.Timedelta(minutes=60), s - pd.Timedelta(minutes=30)),
                "vwap_others_-10_0m": vw(s - pd.Timedelta(minutes=10), s),
                "last_trade_before": last_before(s),
                "wallet_first_price": g.sort_values("timestamp").price.iloc[0],
                "wallet_last_price": g.sort_values("timestamp").price.iloc[-1],
                "wallet_vwap": g.notional.sum() / g["size"].sum(),
                "vwap_others_0_+5m_after": vw(en, en + pd.Timedelta(minutes=5)),
                "vwap_others_+5_+10m_after": vw(en + pd.Timedelta(minutes=5), en + pd.Timedelta(minutes=10)),
                "vwap_others_+25_+35m_after": vw(en + pd.Timedelta(minutes=25), en + pd.Timedelta(minutes=35)),
                "vwap_others_+55_+65m_after": vw(en + pd.Timedelta(minutes=55), en + pd.Timedelta(minutes=65)),
                "mkt_taker_shares_in_window": win["size"].sum(),
                "wallet_taker_shares_in_window": win.loc[win.mine, "size"].sum(),
                "mkt_taker_shares_toward_in_window": win.loc[win.toward > 0, "size"].sum(),
                "wallet_total_shares": g["size"].sum(),
                "max_fill_shares": g["size"].max(),
                "max_fill_notional": g.notional.max(),
            })
    return pd.concat(pw, ignore_index=True), pd.DataFrame(imp)


def screens(dm, de):
    asof = pd.Timestamp("2026-10-17", tz="UTC")
    lo = asof - pd.DateOffset(months=12)
    m = dm[(dm.market_closed >= lo) & (dm.market_closed <= asof)]
    e = de[(de.last_resolved >= lo) & (de.last_resolved <= asof)]
    res = {}
    for name, n, wins, money in [("per_market", len(m), int(m.chosen_outcome_won.sum()), int((m.realised_pnl > 0).sum())),
                                 ("per_event", len(e), int(e.all_legs_won.sum()), int((e.realised_pnl > 0).sum()))]:
        res[name] = {"n": n, "wins_outcome": wins, "made_money": money}
    return res


def main():
    t, td, act, mk = load()
    f = build_fills(t, td, act, mk)
    assert abs(f.fee.sum() - 127397.55907) < 0.01, f.fee.sum()
    assert (f[f.role == "maker"].fee_api.abs() < 1e-6).all()
    dm = market_decisions(f, act, mk)
    f, ep = episodes(f)
    ep = classify(ep)
    # event level
    de = []
    for mt, g in dm.groupby("match"):
        ff = f[f.match == mt]
        de.append({"match": mt, "n_markets": len(g), "markets": "; ".join(g.question + " -> " + g.outcome),
                   "first_fill": g.first_fill.min(), "last_fill": g.last_fill.max(), "cost": g.cost.sum(),
                   "notional": g.notional.sum(), "fees": g.fees.sum(), "redeem_usdc": g.redeem_usdc.sum(),
                   "realised_pnl": g.realised_pnl.sum(), "unrealised_pnl": 0.0,
                   "all_legs_won": bool(g.chosen_outcome_won.all()), "any_leg_lost": bool((~g.chosen_outcome_won).any()),
                   "taker_share_notional": ff.loc[ff.role == "taker", "notional"].sum() / ff.notional.sum(),
                   "last_resolved": g.market_closed.max(), "score": g.event_score.dropna().iloc[0] if g.event_score.notna().any() else None,
                   "return_on_cost": g.realised_pnl.sum() / g.cost.sum()})
    de = pd.DataFrame(de).sort_values("first_fill").reset_index(drop=True)
    cap = capital_timeline(f, dm)
    cp = counterparties(f)
    pw, imp = price_windows_and_impact(f, ep)
    sc = ksa_uru_scenarios(dm)

    f.to_parquet(D / "mintblade_fills.parquet", index=False)
    dm.to_parquet(D / "mintblade_decisions_market.parquet", index=False)
    de.to_parquet(D / "mintblade_decisions_event.parquet", index=False)
    ep.to_parquet(D / "mintblade_episodes.parquet", index=False)
    cap.to_parquet(D / "mintblade_capital_timeline.parquet", index=False)
    cp.to_parquet(D / "mintblade_counterparties.parquet", index=False)
    pw.to_parquet(D / "mintblade_price_windows.parquet", index=False)
    imp.to_parquet(D / "mintblade_impact.parquet", index=False)
    sc.to_parquet(D / "mintblade_ksa_uru_scenarios.parquet", index=False)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 60)
    pd.set_option("display.max_colwidth", 60)
    pd.set_option("display.max_rows", 200)
    print("== market decisions ==")
    print(dm.drop(columns=["feeSchedule", "condition_id"]).T.to_string())
    print("== event decisions ==")
    print(de.T.to_string())
    print("== episodes ==")
    print(ep.T.to_string())
    print("== KSA-URU scenario P&L ==")
    print(sc.to_string())
    print("== capital ==")
    print("max deployed", cap.capital_deployed.max(), "at", cap.loc[cap.capital_deployed.idxmax(), "ts"])
    print("max at risk", cap.capital_at_risk.max(), "at", cap.loc[cap.capital_at_risk.idxmax(), "ts"])
    print("== impact ==")
    print(imp.T.to_string())
    print("== counterparties ==")
    print(cp.groupby(["question", "wallet_role", "cp_role"]).agg(n=("cp_size", "size"), sh=("cp_size", "sum"),
                                                                 wallets=("cp_wallet", "nunique")).to_string())
    top = (cp[cp.cp_role != "co-maker (same side)"].groupby(["question", "cp_wallet", "cp_name"]).cp_size.sum()
           .reset_index().sort_values("cp_size", ascending=False).groupby("question").head(5))
    print(top.to_string())
    print("candidate wallets among counterparties:", cp[cp.candidate_wallet != ""].shape[0])
    print("== screens ==", screens(dm, de))


if __name__ == "__main__":
    main()
