"""Apply the user's screens (trailing 12 months to 2026-10-17) under three counting rules and compute
how likely each observed record / P&L is under the null that every decision wins with its
entry-implied probability (market price = true probability, i.e. zero edge).

Null model: matches are independent. Within a match, the joint distribution over home-margin buckets
{<=-2,-1,0,+1,>=+2} is backed out of the wallet's own entry VWAPs (moneyline win/draw prices and the
1.5-goal spread), so nested legs (draw => team-X-not-win) are handled. Where a bucket split is not
identified by the wallet's own prices, it does not matter for that wallet's payoff.
Outputs: data/derived/ge_screens.parquet, ge_null_pnl.parquet
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "derived"
WIN_START, WIN_END = pd.Timestamp("2025-10-17", tz="UTC"), pd.Timestamp("2026-10-17", tz="UTC")


def match_state_probs(g: pd.DataFrame) -> dict[int, float]:
    """Bucket probabilities implied by the wallet's VWAPs on one match (see module doc)."""
    q = dict(zip(g.question + "|" + g.outcome, g.vwap))
    k = g.match_key.iloc[0]
    if k == "fifwc-ksa-ury-2026-06-15":  # home KSA, away URY
        p_draw = q["Will Saudi Arabia vs. Uruguay end in a draw?|Yes"]
        p_not_ury = q["Will Uruguay win on 2026-06-15?|No"]
        p_ury2 = 1 - q["Spread: Uruguay (-1.5)|Saudi Arabia"]
        p_ksa = p_not_ury - p_draw
        return {2: p_ksa / 2, 1: p_ksa / 2, 0: p_draw, -1: 1 - p_not_ury - p_ury2, -2: p_ury2}
    if k == "fifwc-cze-rsa-2026-06-18":  # home CZE
        p_draw = q["Will Czechia vs. South Africa end in a draw?|Yes"]
        p_not_cze = q["Will Czechia win on 2026-06-18?|No"]
        return {2: (1 - p_not_cze) / 2, 1: (1 - p_not_cze) / 2, 0: p_draw, -1: (p_not_cze - p_draw) / 2, -2: (p_not_cze - p_draw) / 2}
    return {}


def main() -> None:
    dm = pd.read_parquet(OUT / "ge_dec_market.parquet")
    dmm = pd.read_parquet(OUT / "ge_dec_match.parquet")
    st = pd.read_parquet(OUT / "ge_match_states.parquet")
    dm = dm[(dm.first_fill_utc >= WIN_START) & (dm.first_fill_utc < WIN_END)]
    rows, nulls = [], []
    for lab in ["GRIMDRIP", "endlessFate", "mintblade"]:
        m = dm[dm.label == lab]
        e = dmm[dmm.label == lab]
        # ---- per-match outcome distributions under the null: list of (prob, pnl, legs_won_vector)
        per_match = []
        for mk_, g in m.groupby("match_key"):
            sp = match_state_probs(g)
            if sp:
                s = st[(st.label == lab) & (st.match_key == mk_)].set_index("home_margin_bucket").net_pnl_in_state
                # legs won per state
                from ge_build_decisions import TEAMS, pays_in_state  # noqa
                home, away = TEAMS[mk_]
                mkt = pd.read_parquet(OUT / "ge_markets.parquet").set_index("conditionId")
                outs = []
                for b, p in sp.items():
                    won = [pays_in_state(r.question, r.outcome, home, away, mkt.loc[r.condition_id, "line"], b) for r in g.itertuples()]
                    outs.append((p, float(s.loc[b]), won))
                per_match.append((mk_, list(g.question), outs))
            else:  # single-leg (or independent) match: win w.p. VWAP
                r = g.iloc[0]
                win_pnl = r.shares_bought - r.max_capital
                per_match.append((mk_, [r.question], [(r.vwap, win_pnl, [True]), (1 - r.vwap, -r.max_capital, [False])]))
        # enumerate joint null distribution
        dist = []
        for combo in itertools.product(*[x[2] for x in per_match]):
            p = float(np.prod([c[0] for c in combo]))
            pnl = sum(c[1] for c in combo)
            legs = [w for c in combo for w in c[2]]
            ev_allwon = [all(c[2]) for c in combo]
            ev_money = [c[1] > 0 for c in combo]
            dist.append((p, pnl, sum(legs), len(legs), sum(ev_allwon), sum(ev_money)))
        d = pd.DataFrame(dist, columns=["p", "pnl", "legs_won", "n_legs", "events_allwon", "events_money"])
        obs_pnl = m.realised_pnl_if_settled.sum()
        obs_legs = int(m.outcome_won.sum())
        obs_ev = int(e.all_markets_won.sum())
        obs_money_mk = int(m.made_money.sum())
        obs_money_ev = int(e.made_money.sum())
        n_mk, n_ev = len(m), len(e)
        nulls.append({"label": lab, "expected_pnl_null": (d.p * d.pnl).sum(), "sd_pnl_null": np.sqrt((d.p * d.pnl ** 2).sum() - (d.p * d.pnl).sum() ** 2),
                      "observed_pnl": obs_pnl, "p_pnl_ge_observed": d.loc[d.pnl >= obs_pnl - 1, "p"].sum(),
                      "p_all_markets_won": d.loc[d.legs_won == d.n_legs, "p"].sum(),
                      "naive_product_of_vwaps": float(np.prod(m.vwap)),
                      "p_markets_won_ge_observed": d.loc[d.legs_won >= obs_legs, "p"].sum(),
                      "p_all_events_won": d.loc[d.events_allwon == n_ev, "p"].sum(),
                      "p_events_won_ge_observed": d.loc[d.events_allwon >= obs_ev, "p"].sum(),
                      "p_all_events_made_money": d.loc[d.events_money == n_ev, "p"].sum(),
                      "expected_markets_won_null": (d.p * d.legs_won).sum(), "expected_events_won_null": (d.p * d.events_allwon).sum(),
                      "n_outcomes_enumerated": len(d), "prob_mass_check": d.p.sum()})
        for rule, n, wins, losses in [
            ("per_market_outcome", n_mk, obs_legs, n_mk - obs_legs),
            ("per_event_all_legs_won", n_ev, obs_ev, n_ev - obs_ev),
            ("per_market_made_money", n_mk, obs_money_mk, n_mk - obs_money_mk),
            ("per_event_made_money", n_ev, obs_money_ev, n_ev - obs_money_ev),
        ]:
            rows.append({"label": lab, "rule": rule, "n_resolved_decisions": n, "successes": wins, "losses": losses,
                         "screen_exact5_allwin": (n == 5) and (losses == 0), "screen_ge5_noloss": (n >= 5) and (losses == 0)})
        # naive 'closed positions only' view (what a leaderboard of redeemed positions shows)
        cl = m[m.redeem_usdc > 0]
        rows.append({"label": lab, "rule": "naive_closed_positions_only", "n_resolved_decisions": len(cl), "successes": len(cl), "losses": 0,
                     "screen_exact5_allwin": len(cl) == 5, "screen_ge5_noloss": len(cl) >= 5,
                     "note": f"{len(m) - len(cl)} resolved losing markets are unredeemed and absent from status=CLOSED"})
    sc = pd.DataFrame(rows)
    nu = pd.DataFrame(nulls)
    sc.to_parquet(OUT / "ge_screens.parquet", index=False)
    nu.to_parquet(OUT / "ge_null_pnl.parquet", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(sc.to_string())
    print(nu.T.to_string())


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
