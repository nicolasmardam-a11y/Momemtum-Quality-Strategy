"""User screens and luck arithmetic for mintblade (as of 2026-10-17, trailing 12 months).

Null hypothesis: each decision wins with its entry-implied probability (the wallet's own
VWAP, or the market-implied state probabilities at entry for the correlated KSA-URU legs).
Market-implied state probabilities come from CLOB /prices-history at 21:54-22:00 UTC
(KSA win, draw, URU win, URU -1.5), which are trade/mid prints, not executable prices.
Output: data/derived/mintblade_screens.json
"""
from __future__ import annotations

import json
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).resolve().parents[2] / "data" / "derived"
W = "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb"


def main():
    dm = pd.read_parquet(D / "mintblade_decisions_market.parquet")
    de = pd.read_parquet(D / "mintblade_decisions_event.parquet")
    sc = pd.read_parquet(D / "mintblade_ksa_uru_scenarios.parquet").set_index("state")
    asof = pd.Timestamp("2026-10-17", tz="UTC")
    lo = asof - pd.DateOffset(months=12)
    assert ((dm.market_closed >= lo) & (dm.market_closed <= asof)).all()

    v = dm.set_index("question")
    p_mets = v.loc["New York Mets vs. Seattle Mariners", "vwap"]
    p_iran_no = v.loc["Will IR Iran win on 2026-06-15?", "vwap"]
    # market-implied KSA-URU state probabilities at the wallet's entry (avg of 21:54 and 22:00 prints)
    st = {"Saudi win": 0.12, "Draw": 0.235, "Uruguay by 1": 0.26, "Uruguay by 2+": 0.38}
    z = sum(st.values())
    st = {k: x / z for k, x in st.items()}

    out = {}
    naive = float(np.prod(dm.vwap))
    naive_fee = float(np.prod(dm.vwap_incl_fee))
    joint_all_markets_win = p_mets * st["Draw"] * p_iran_no
    p_ksa_money = st["Saudi win"] + st["Draw"]
    per_event_money = p_mets * p_ksa_money * p_iran_no
    out["null_probabilities"] = {
        "per_market_5of5_naive_independent_product_vwap": naive,
        "per_market_5of5_naive_independent_product_vwap_incl_fee": naive_fee,
        "per_market_5of5_correlation_aware": joint_all_markets_win,
        "per_event_3of3_made_money": per_event_money,
        "per_event_2of2_excluding_4.80usd_mets_ticket": p_ksa_money * p_iran_no,
        "ksa_uru_all_three_legs_win(=draw)": st["Draw"],
        "ksa_uru_made_money(=KSA win or draw)": p_ksa_money,
        "iran_no": p_iran_no,
        "mets": p_mets,
        "ksa_state_probs_normalised": st,
    }
    # P&L distribution under the null (two football matches independent; Mets negligible)
    iran = v.loc["Will IR Iran win on 2026-06-15?"]
    iran_win_pnl = iran.shares - iran.cost
    iran_lose_pnl = -iran.cost
    dist = []
    for (ks, pk), (iw, pi) in product(st.items(), [(True, p_iran_no), (False, 1 - p_iran_no)]):
        pnl = sc.loc[ks, "pnl"] + (iran_win_pnl if iw else iran_lose_pnl)
        dist.append({"ksa_state": ks, "iran_no_wins": iw, "prob": pk * pi, "pnl": pnl})
    dist = pd.DataFrame(dist)
    realised = dm.realised_pnl.sum()
    out["null_pnl"] = {
        "expected_pnl": float((dist.prob * dist.pnl).sum()),
        "ksa_uru_expected_pnl": float(sum(st[k] * sc.loc[k, "pnl"] for k in st)),
        "iran_expected_pnl": float(p_iran_no * iran_win_pnl + (1 - p_iran_no) * iran_lose_pnl),
        "p_total_pnl_positive": float(dist.loc[dist.pnl > 0, "prob"].sum()),
        "p_total_pnl_ge_realised": float(dist.loc[dist.pnl >= realised - 1, "prob"].sum()),
        "realised_cashflow_pnl": float(realised),
        "table": dist.to_dict("records"),
    }
    # screens
    m_n, m_win, m_money = len(dm), int(dm.chosen_outcome_won.sum()), int((dm.realised_pnl > 0).sum())
    e_n, e_win, e_money = len(de), int(de.all_legs_won.sum()), int((de.realised_pnl > 0).sum())
    big = dm[dm.cost >= 100]
    out["screens"] = {
        "window": [str(lo.date()), str(asof.date())],
        "per_market": {"n": m_n, "chosen_outcome_won": m_win, "made_money": m_money,
                       "screen_i_exactly5_allwin": m_n == 5 and m_win == 5,
                       "screen_ii_ge5_noloss": m_n >= 5 and m_win == m_n},
        "per_event": {"n": e_n, "all_legs_won": e_win, "made_money": e_money,
                      "screen_i_exactly5_allwin": e_n == 5 and e_win == 5,
                      "screen_ii_ge5_noloss": e_n >= 5 and e_win == e_n},
        "per_made_money_market": {"n": m_n, "pnl_gt0": m_money,
                                  "screen_i": m_n == 5 and m_money == 5, "screen_ii": m_n >= 5 and m_money == m_n},
        "per_made_money_event": {"n": e_n, "pnl_gt0": e_money,
                                 "screen_i": e_n == 5 and e_money == 5, "screen_ii": e_n >= 5 and e_money == e_n},
        "sensitivity_min_cost_100usd": {"n_markets": len(big), "n_events": big.match.nunique()},
    }
    # luck pool: expected number of wallets passing a 5-for-5 screen by luck
    pool = {}
    for pbar in [0.4, 0.5, 0.6, 0.8, 0.95]:
        pool[str(pbar)] = {str(n): n * pbar ** 5 for n in [1_000, 10_000, 100_000]}
    pool["mintblade_specific_corr_aware"] = {str(n): n * joint_all_markets_win for n in [1_000, 10_000, 100_000]}
    out["luck_pool_expected_passers"] = pool
    # illustration from data: distinct wallets whose pre-start taker flow was on the winning side
    ill = {}
    for cid10, q, tok_out, start in [("0xe70fd51f", "Iran win: No", "No", "2026-06-16 01:04:03"),
                                     ("0xbc54d735", "Uruguay win: No", "No", "2026-06-15 22:03:36")]:
        T = pd.read_parquet(D / f"mintblade_tape_{cid10}_taker.parquet")
        T = T[T.timestamp < pd.Timestamp(start).timestamp()]
        win = ((T.outcome == tok_out) & (T.side == "BUY")) | ((T.outcome != tok_out) & (T.side == "SELL"))
        ill[q] = {"tape_window_start_utc": str(pd.to_datetime(T.timestamp.min(), unit="s")),
                  "distinct_takers_pre_start": int(T.proxy_wallet.nunique()),
                  "distinct_takers_buying_winning_side_pre_start": int(T[win].proxy_wallet.nunique())}
    out["illustration_winning_side_takers"] = ill
    with open(D / "mintblade_screens.json", "w") as fh:
        json.dump(out, fh, indent=1, default=float)
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
