"""Step 9 of the linkage study: the user's screens and P&L under three ownership scenarios.

(a) independent: each wallet on its own (as in mintblade.md / grimdrip_endlessfate.md)
(b) mintblade + GRIMDRIP are one entity
(c) mintblade + GRIMDRIP + endlessFate are one entity
At cluster level a decision is counted once: the same market + outcome bought by two cluster wallets is ONE market
decision (KSA-URY: mintblade and endlessFate bought the same three legs), and a match is ONE event decision.
P&L is summed from each wallet's own trade/redemption cash flows (ge_dec_market.realised_pnl), never from
deposits / withdrawals, so funds routed between cluster accounts through exchange accounts cannot be double counted.
Capital: peak simultaneous cost of unresolved positions across the cluster (first fill -> resolution).
Null (zero edge): each match independent; within a match, home-margin bucket probabilities are backed out of the
cluster's notional-weighted entry VWAPs (ge_screens.match_state_probs); bucket P&L = sum of the wallets' bucket P&L
(ge_match_states.parquet). Sensitivity: drop decisions with stake < $100 (the $4.80 Mets test ticket).
Output: data/derived/linkage_scenarios.parquet
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from ge_screens import match_state_probs
from linkage_common import DERIVED

SCEN = {"a_mintblade": ["mintblade"], "a_GRIMDRIP": ["GRIMDRIP"], "a_endlessFate": ["endlessFate"],
        "b_mintblade+GRIMDRIP": ["mintblade", "GRIMDRIP"],
        "c_all_three": ["mintblade", "GRIMDRIP", "endlessFate"],
        "c'_mintblade+endlessFate": ["mintblade", "endlessFate"]}


def cluster_eval(labels: list[str], dm: pd.DataFrame, st: pd.DataFrame, min_stake: float = 0.0) -> dict:
    m = dm[dm.label.isin(labels) & (dm.max_capital >= min_stake)].copy()
    # market decisions: one per (condition, outcome) across the cluster
    md = m.groupby(["match_key", "condition_id", "question", "outcome"]).agg(
        shares=("shares_bought", "sum"), notional=("buy_notional", "sum"), cost=("max_capital", "sum"),
        pnl=("realised_pnl", "sum"), won=("outcome_won", "first"), n_wallets=("label", "nunique")).reset_index()
    md["vwap"] = md.notional / md.shares
    ev = md.groupby("match_key").agg(pnl=("pnl", "sum"), all_won=("won", "all"), n_mk=("won", "size")).reset_index()
    ev["made_money"] = ev.pnl > 0
    # null distribution
    per_match = []
    for mk_, g in md.groupby("match_key"):
        sp = match_state_probs(g) if len(g) > 1 else {}
        if sp:
            s = st[st.label.isin(m[m.match_key == mk_].label.unique()) & (st.match_key == mk_)]
            s = s.groupby("home_margin_bucket").net_pnl_in_state.sum()
            from ge_build_decisions import TEAMS, pays_in_state
            home, away = TEAMS[mk_]
            mkt = pd.read_parquet(DERIVED / "ge_markets.parquet").set_index("conditionId")
            outs = [(p, float(s.loc[b]), [pays_in_state(r.question, r.outcome, home, away, mkt.loc[r.condition_id, "line"], b)
                                          for r in g.itertuples()]) for b, p in sp.items()]
        else:
            if len(g) > 1:
                raise RuntimeError(f"no joint state model for multi-leg match {mk_}")
            r = g.iloc[0]
            outs = [(r.vwap, r.shares - r.cost, [True]), (1 - r.vwap, -r.cost, [False])]
        per_match.append(outs)
    dist = []
    for combo in itertools.product(*per_match):
        dist.append((float(np.prod([c[0] for c in combo])), sum(c[1] for c in combo),
                     sum(sum(c[2]) for c in combo), sum(all(c[2]) for c in combo), sum(c[1] > 0 for c in combo)))
    d = pd.DataFrame(dist, columns=["p", "pnl", "legs_won", "events_allwon", "events_money"])
    obs = md.pnl.sum()
    # peak simultaneous capital across the cluster
    iv = m[["first_fill_utc", "resolved_utc", "max_capital"]].dropna()
    ts = sorted(set(iv.first_fill_utc) | set(iv.resolved_utc))
    peak = max(iv[(iv.first_fill_utc <= t) & (iv.resolved_utc > t)].max_capital.sum() for t in ts) if len(iv) else np.nan
    n_mk, n_ev = len(md), len(ev)
    w_mk, w_ev, mm_ev = int(md.won.sum()), int(ev.all_won.sum()), int(ev.made_money.sum())
    return {"wallets": "+".join(labels), "min_stake": min_stake, "wallet_market_rows": len(m), "distinct_market_decisions": n_mk,
            "shared_market_decisions": int((md.n_wallets > 1).sum()), "distinct_events": n_ev,
            "markets_won": w_mk, "events_all_legs_won": w_ev, "events_made_money": mm_ev,
            "screen_exact5_allwin_market": n_mk == 5 and w_mk == n_mk, "screen_ge5_noloss_market": n_mk >= 5 and w_mk == n_mk,
            "screen_exact5_allwin_event": n_ev == 5 and w_ev == n_ev, "screen_ge5_noloss_event": n_ev >= 5 and w_ev == n_ev,
            "realised_pnl": obs, "fees": m.fees.sum(), "sum_wallet_peak_capital": m.groupby("label").max_capital.sum().max() if False else np.nan,
            "cluster_peak_capital": peak, "pnl_over_peak_capital": obs / peak if peak else np.nan,
            "null_expected_pnl": (d.p * d.pnl).sum(), "null_sd_pnl": np.sqrt((d.p * d.pnl ** 2).sum() - (d.p * d.pnl).sum() ** 2),
            "null_p_pnl_ge_obs": d.loc[d.pnl >= obs - 1, "p"].sum(), "null_p_all_markets_won": d.loc[d.legs_won == n_mk, "p"].sum(),
            "null_p_all_events_made_money": d.loc[d.events_money == n_ev, "p"].sum(),
            "null_expected_events_made_money": (d.p * d.events_money).sum(), "prob_mass": d.p.sum()}


def main() -> None:
    dm = pd.read_parquet(DERIVED / "ge_dec_market.parquet")
    st = pd.read_parquet(DERIVED / "ge_match_states.parquet")
    rows = [{"scenario": k, **cluster_eval(v, dm, st, ms)} for k, v in SCEN.items() for ms in (0.0, 100.0)]
    df = pd.DataFrame(rows).drop(columns=["sum_wallet_peak_capital"])
    df.to_parquet(DERIVED / "linkage_scenarios.parquet", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(df[df.min_stake == 0].set_index("scenario").T.to_string())
    print(df[df.min_stake == 100].set_index("scenario")[["distinct_market_decisions", "distinct_events", "markets_won", "events_made_money",
                                                        "screen_ge5_noloss_market", "screen_exact5_allwin_market"]].to_string())


if __name__ == "__main__":
    main()
