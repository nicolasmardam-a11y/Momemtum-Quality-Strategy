"""Build the tidy fills table and the market / match / entry-episode decision tables for
GRIMDRIP and endlessFate (mintblade included for comparison).

Inputs: ge_trades_all, ge_trades_takeronly, ge_activity, ge_markets (from the pull/map scripts).
Outputs (data/derived/): ge_fills.parquet, ge_dec_market.parquet, ge_dec_match.parquet,
ge_dec_episode.parquet, ge_match_states.parquet

Conventions
- role: a fill is 'taker' iff its tx hash appears in the wallet's taker_only=true trade list
  (verified: taker-only rows are an exact subset of taker_only=false rows, one row per tx).
- fee: taker fills only, fee = size * feeSchedule.rate * p * (1-p) (exponent 1). Matches the
  Data API position field entry_fees_usdc to the cent for every market (verified).
- realised P&L (cash basis) = redemptions + sells - buy notional - fees. Resolved losers that were
  never redeemed are realised losses (payout 0) even though /v2/positions reports them as
  'unrealized_pnl'. No market here is unresolved, so unrealised P&L = 0 for all wallets.
- episode: consecutive fills of one wallet on one match separated by <= 10 min.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "derived"
GAP = 600  # episode split, seconds

# Final scores and home/away from Gamma event 'score' (home-away, verified vs match reports)
TEAMS = {  # match_key: (home, away)
    "fifwc-kr-cze-2026-06-11": ("Korea Republic", "Czechia"),
    "fifwc-can-bih-2026-06-12": ("Canada", "Bosnia and Herzegovina"),
    "fifwc-usa-par-2026-06-12": ("United States", "Paraguay"),
    "fifwc-aus-tur-2026-06-14": ("Australia", "Türkiye"),
    "fifwc-bel-egy-2026-06-15": ("Belgium", "Egypt"),
    "fifwc-ksa-ury-2026-06-15": ("Saudi Arabia", "Uruguay"),
    "fifwc-irn-nzl-2026-06-15": ("IR Iran", "New Zealand"),
    "fifwc-uzb-col-2026-06-17": ("Uzbekistan", "Colombia"),
    "fifwc-cze-rsa-2026-06-18": ("Czechia", "South Africa"),
    "mlb-nym-sea-2026-06-03": ("New York Mets", "Seattle Mariners"),
}
STATES = [-2, -1, 0, 1, 2]  # home goal margin bucket: <=-2, -1, 0, +1, >=+2


def ts(x) -> float:
    return pd.Timestamp(x).timestamp() if pd.notna(x) else np.nan


def pays_in_state(q: str, outcome: str, home: str, away: str, line, state: int) -> bool:
    """Does holding `outcome` of market `q` pay $1 when home margin bucket == state?"""
    if q.startswith("Spread:"):
        fav = q.split("Spread: ")[1].split(" (")[0]
        need = abs(float(line))  # favourite must win by more than |line| (e.g. 1.5 -> >= 2)
        fav_margin = state if fav == home else -state
        fav_covers = fav_margin >= 2 if need == 1.5 else None
        return fav_covers if outcome == fav else not fav_covers
    if "end in a draw" in q:
        return (state == 0) if outcome == "Yes" else (state != 0)
    team = q.replace("Will ", "").split(" win on")[0]
    team_wins = (state > 0) if team == home else (state < 0)
    return team_wins if outcome == "Yes" else not team_wins


def main() -> None:
    t = pd.read_parquet(OUT / "ge_trades_all.parquet")
    tk = pd.read_parquet(OUT / "ge_trades_takeronly.parquet")
    act = pd.read_parquet(OUT / "ge_activity.parquet")
    mk = pd.read_parquet(OUT / "ge_markets.parquet")
    evs = pd.read_parquet(OUT / "ge_events.parquet")

    mk["ko_ts"] = mk.gameStartTime.map(ts)
    mk["closed_ts"] = mk.closedTime.map(ts)
    mk["finished_ts"] = mk.event_finishedTimestamp.map(ts)
    mkx = mk.set_index("conditionId")

    # ------------------------------------------------------------------ fills
    f = t.copy()
    f["role"] = np.where(f.transaction_hash.isin(set(tk.transaction_hash)), "taker", "maker")
    f["notional"] = f["size"] * f.price
    f = f.join(mkx[["question", "match_key", "sportsMarketType", "line", "fee_rate", "ko_ts", "closed_ts",
                    "finished_ts", "outcomes", "outcomePrices", "negRisk", "secondsDelay", "event_score"]],
               on="condition_id")
    f["fee"] = np.where(f.role == "taker", f["size"] * f.fee_rate * f.price * (1 - f.price), 0.0)
    f["payout"] = [float(json.loads(op)[int(i)]) for op, i in zip(f.outcomePrices, f.outcome_index)]
    f["won"] = f.payout == 1.0
    f["sec_to_ko"] = f.timestamp - f.ko_ts
    f["time_utc"] = pd.to_datetime(f.timestamp, unit="s", utc=True)
    f = f.sort_values(["label", "timestamp"]).reset_index(drop=True)
    # episodes per wallet x match
    f["episode"] = 0
    for (lab, mkey), g in f.groupby(["label", "match_key"]):
        ep = (g.timestamp.diff().fillna(0) > GAP).cumsum() + 1
        f.loc[g.index, "episode"] = ep.values
    f["episode_id"] = f.label + "|" + f.match_key + "|E" + f.episode.astype(str)
    keep = ["label", "proxy_wallet", "timestamp", "time_utc", "transaction_hash", "condition_id", "token_id", "question",
            "match_key", "event_slug", "sportsMarketType", "outcome", "outcome_index", "side", "size", "price", "notional",
            "role", "fee_rate", "fee", "payout", "won", "ko_ts", "sec_to_ko", "episode", "episode_id", "negRisk", "secondsDelay"]
    f[keep].to_parquet(OUT / "ge_fills.parquet", index=False)

    # ------------------------------------------------------------------ redemptions / merges / sells
    red = act[act.type == "REDEEM"].groupby(["label", "condition_id"]).agg(redeem_usdc=("usdc_size", "sum"),
                                                                            redeem_ts=("timestamp", "max"))
    other = act[act.type.isin(["MERGE", "SPLIT", "CONVERSION"])]
    print("MERGE/SPLIT/CONVERSION rows:", len(other))

    # ------------------------------------------------------------------ market-level decisions
    def agg_block(g: pd.DataFrame) -> pd.Series:
        b = g[g.side == "BUY"]
        s = g[g.side == "SELL"]
        sh = b["size"].sum()
        cost = b.notional.sum()
        fees = g.fee.sum()
        return pd.Series({
            "first_fill_utc": g.time_utc.min(), "last_fill_utc": g.time_utc.max(), "n_fills": len(g),
            "n_taker": (g.role == "taker").sum(), "n_maker": (g.role == "maker").sum(),
            "taker_share_of_shares": g.loc[g.role == "taker", "size"].sum() / g["size"].sum(),
            "shares_bought": sh, "buy_notional": cost, "vwap": cost / sh if sh else np.nan,
            "vwap_incl_fee": (cost + b.fee.sum()) / sh if sh else np.nan,
            "shares_sold": s["size"].sum(), "sell_proceeds": s.notional.sum(), "fees": fees,
            "min_to_ko_first": g.sec_to_ko.min() / 60, "min_to_ko_last": g.sec_to_ko.max() / 60,
            "notional_after_ko": g.loc[g.sec_to_ko > 0, "notional"].sum(),
        })

    gm = f.groupby(["label", "match_key", "condition_id", "question", "outcome"])
    dm = gm.apply(agg_block, include_groups=False).reset_index()
    dm = dm.join(red, on=["label", "condition_id"])
    pmap = dict(zip(f.condition_id + "|" + f.outcome, f.payout))
    dm["payout_per_share"] = (dm.condition_id + "|" + dm.outcome).map(pmap)
    dm["outcome_won"] = dm.payout_per_share == 1.0
    dm["settlement_value"] = (dm.shares_bought - dm.shares_sold) * dm.payout_per_share
    dm["redeem_usdc"] = dm.redeem_usdc.fillna(0.0)
    dm["unredeemed_winning_value"] = dm.settlement_value - dm.redeem_usdc  # >0 would be unrealised-but-certain
    dm["realised_pnl"] = dm.redeem_usdc + dm.sell_proceeds - dm.buy_notional - dm.fees
    dm["realised_pnl_if_settled"] = dm.settlement_value + dm.sell_proceeds - dm.buy_notional - dm.fees
    dm["unrealised_pnl"] = 0.0  # every market resolved; losers at payout 0 are realised losses
    dm["max_capital"] = dm.buy_notional + dm.fees  # no sells, so peak = total outlay
    dm["return_on_max_capital"] = dm.realised_pnl_if_settled / dm.max_capital
    dm["made_money"] = dm.realised_pnl_if_settled > 0
    dm["edge_per_share"] = dm.payout_per_share - dm.vwap
    dm["edge_per_share_incl_fee"] = dm.payout_per_share - dm.vwap_incl_fee
    dm["entry_implied_prob"] = dm.vwap
    closed = mkx.closed_ts
    dm["resolved_utc"] = pd.to_datetime(dm.condition_id.map(closed), unit="s", utc=True)
    dm["holding_hours_to_resolution"] = (dm.resolved_utc - dm.first_fill_utc).dt.total_seconds() / 3600
    dm["holding_hours_to_redeem"] = np.where(dm.redeem_ts.notna(),
                                             (dm.redeem_ts - dm.first_fill_utc.map(lambda x: x.timestamp())) / 3600, np.nan)
    dm.to_parquet(OUT / "ge_dec_market.parquet", index=False)

    # ------------------------------------------------------------------ match-level (distinct event) + state payoffs
    st_rows, dmm = [], []
    for (lab, mkey), g in dm.groupby(["label", "match_key"]):
        home, away = TEAMS[mkey]
        cost = g.max_capital.sum()
        pay = {}
        for s in STATES:
            v = 0.0
            for r in g.itertuples():
                line = mkx.loc[r.condition_id, "line"]
                if pays_in_state(r.question, r.outcome, home, away, line, s):
                    v += r.shares_bought
            pay[s] = v - cost
            st_rows.append({"label": lab, "match_key": mkey, "home_margin_bucket": s, "net_pnl_in_state": v - cost,
                            "gross_payout": v, "cost": cost})
        score = evs.loc[evs.slug == mkey, "score"].dropna()
        h, a = (int(x) for x in score.iloc[0].split("-")) if len(score) else (None, None)
        dmm.append({
            "label": lab, "match_key": mkey, "home": home, "away": away, "final_score": f"{h}-{a}",
            "n_markets": len(g), "markets": " | ".join(f"{q} -> {o}" for q, o in zip(g.question, g.outcome)),
            "first_fill_utc": g.first_fill_utc.min(), "last_fill_utc": g.last_fill_utc.max(),
            "min_to_ko_first": g.min_to_ko_first.min(), "min_to_ko_last": g.min_to_ko_last.max(),
            "buy_notional": g.buy_notional.sum(), "fees": g.fees.sum(), "max_capital": cost,
            "n_fills": g.n_fills.sum(), "taker_share_of_shares": (g.taker_share_of_shares * g.shares_bought).sum() / g.shares_bought.sum(),
            "realised_pnl": g.realised_pnl.sum(), "realised_pnl_if_settled": g.realised_pnl_if_settled.sum(),
            "return_on_max_capital": g.realised_pnl_if_settled.sum() / cost,
            "all_markets_won": bool(g.outcome_won.all()), "any_market_won": bool(g.outcome_won.any()),
            "made_money": g.realised_pnl_if_settled.sum() > 0,
            "pnl_by_home_margin": json.dumps({str(k): round(v) for k, v in pay.items()}),
            "states_with_profit": ",".join(str(k) for k, v in pay.items() if v > 0),
        })
    pd.DataFrame(st_rows).to_parquet(OUT / "ge_match_states.parquet", index=False)
    dmm = pd.DataFrame(dmm)
    dmm.to_parquet(OUT / "ge_dec_match.parquet", index=False)

    # ------------------------------------------------------------------ entry episodes
    ep = []
    for eid, g in f.groupby("episode_id"):
        row = {"episode_id": eid, "label": g.label.iloc[0], "match_key": g.match_key.iloc[0],
               "first_fill_utc": g.time_utc.min(), "last_fill_utc": g.time_utc.max(),
               "duration_min": (g.timestamp.max() - g.timestamp.min()) / 60,
               "min_to_ko_first": g.sec_to_ko.min() / 60, "min_to_ko_last": g.sec_to_ko.max() / 60,
               "n_fills": len(g), "n_markets": g.condition_id.nunique(),
               "notional": g.notional.sum(), "fees": g.fee.sum(),
               "taker_share_notional": g.loc[g.role == "taker", "notional"].sum() / g.notional.sum(),
               "notional_after_ko": g.loc[g.sec_to_ko > 0, "notional"].sum(),
               "legs": "; ".join(f"{q} -> {o}: {sh:,.0f} sh @ {nt / sh:.4f}" for (q, o), (sh, nt) in
                                 g.groupby(["question", "outcome"])[["size", "notional"]].sum().iterrows()),
               "settled_pnl": (g["size"] * g.payout - g.notional - g.fee).sum()}
        ep.append(row)
    ep = pd.DataFrame(ep)
    ep.to_parquet(OUT / "ge_dec_episode.parquet", index=False)

    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 50); pd.set_option("display.max_colwidth", 80)
    print(dm[["label", "question", "outcome", "first_fill_utc", "last_fill_utc", "n_fills", "taker_share_of_shares",
              "shares_bought", "vwap", "buy_notional", "fees", "redeem_usdc", "outcome_won", "realised_pnl_if_settled",
              "return_on_max_capital", "edge_per_share", "min_to_ko_first", "min_to_ko_last", "holding_hours_to_resolution"]].round(4).to_string())
    print(dmm.drop(columns=["markets"]).round(3).to_string())
    print(ep.round(3).to_string())


if __name__ == "__main__":
    main()
