"""Evaluate every candidate relation against every book snapshot (executable, depth-aware, after fees).

Run from polymarket_research/:  python -m analyses.logical_arb.04_evaluate [date] [snap_glob] [tag]
Inputs : data/derived/la_relations*_<date>.parquet (slim or full), data/derived/la_books/<snap_glob>,
         data/derived/la_markets_<date>.parquet (leg metadata, fee schedule)
Output : data/derived/la_opps_<date>_<tag>.parquet (one row per relation x snapshot with top-of-book cost < 1)

Bundle = buy leg a (outcome oa of market a) + buy leg b; minimum payoff 1 per pair of shares (by the
relation's logic; rule exceptions are flagged in columns cancel_payoff / rule_class).
Leg ladder: outcome 0 -> asks of the outcome-0 token; outcome 1 -> (1 - bid, size) of the outcome-0
token (mirror books, VERIFIED on samples). Taker fee per share on each fill:
rate * (p(1-p))^exponent with the market's Gamma feeSchedule (fallback pmr.fees category table;
0 if feesEnabled is False). profit_sens re-prices fees at max(feeSchedule rate, documented category
rate), because sports_fees_v2 markets were seen charging 0.05 on-chain while Gamma says 0.03.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import fees  # noqa: E402

DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-17"
SNAP_GLOB = sys.argv[2] if len(sys.argv) > 2 else "snap_*.parquet"
TAG = sys.argv[3] if len(sys.argv) > 3 else "all"
CAT_BY_FEETYPE = {"sports_fees_v3": 0.05, "sports_fees_v2": 0.05, "sports_fees_nfl_cfb_oct26": 0.03,
                  "politics_fees": 0.04, "crypto_fees_v2": 0.07, "culture_fees": 0.05, "weather_fees": 0.05,
                  "finance_prices_fees": 0.04, "tech_fees": 0.04, "economics_fees": 0.05, "mentions_fees": 0.04,
                  "general_fees": 0.05, "zero_fees": 0.0}
SLIM = ["family", "key", "ma", "oa", "mb", "ob", "note"]

R = pd.concat([pd.read_parquet(f, columns=SLIM) for f in
               sorted((ROOT / "data" / "derived").glob(f"la_relations*_{DATE}.parquet"))], ignore_index=True)
for c in ("family", "key", "note"):
    R[c] = R[c].astype(str)
R["oa"] = R.oa.astype("int8")
R["ob"] = R.ob.astype("int8")
M = pd.read_parquet(ROOT / "data" / "derived" / f"la_markets_{DATE}.parquet",
                    columns=["id", "question", "outcomes", "negRisk", "event_slug", "feesEnabled", "feeType",
                             "fee_rate", "fee_exponent", "endDate", "gameStartTime", "sportsMarketType",
                             "orderMinSize", "groupItemTitle"])
M["id"] = M["id"].astype(str)
M = M.drop_duplicates("id").reset_index(drop=True)
POS = pd.Series(np.arange(len(M)), index=M.id)
R = R[R.ma.isin(POS.index) & R.mb.isin(POS.index)].reset_index(drop=True)
ia = POS.loc[R.ma].values
ib = POS.loc[R.mb].values
oa = R.oa.values
ob = R.ob.values

rate = np.where(M.fee_rate.notna(), np.where(M.feesEnabled == False, 0.0, M.fee_rate.fillna(0.0)),  # noqa: E712
                np.where(M.feesEnabled == False, 0.0, fees.TAKER_RATE["other"])).astype(float)  # noqa: E712
expo = M.fee_exponent.fillna(1.0).astype(float).values
rate_sens = np.maximum(rate, M.feeType.map(CAT_BY_FEETYPE).fillna(0.0).values)
print("relations", len(R), "markets", len(M), flush=True)

# ---- rule-exception state: payoff of each leg if the match is cancelled with no make-up game (soccer rules
# read 2026-10-17: win -> "No", draw -> "Yes", exact score -> "0-0", halftime/2nd-half result -> "No",
# totals/spreads/BTTS/team totals/player props -> 50-50; American-football & others -> 50-50 everywhere)


def cancel_payoff(row_m, outcome):
    t, q = row_m.sportsMarketType, (row_m.question or "")
    if not isinstance(t, str):
        return np.nan
    soccer_like = t.startswith("soccer_") or "end in a draw" in q or (t == "moneyline" and q.startswith("Will "))
    yes = None
    if t == "moneyline" and q.startswith("Will "):
        yes = 1.0 if "end in a draw" in q else 0.0
    elif t == "soccer_exact_score" or t == "soccer_first_half_exact_score":
        yes = 1.0 if " 0 - 0 " in q else 0.0
    elif t in ("soccer_halftime_result", "soccer_second_half_result"):
        yes = 0.0
    if yes is None or not soccer_like:
        return 0.5
    return yes if outcome == 0 else 1.0 - yes


def fee_ps(p, r, ex):
    return r * (p * (1 - p)) ** ex


def ladder(book_row, outcome):
    if outcome == 0:
        return json.loads(book_row["asks"])
    return [(round(1 - p, 6), s) for p, s in json.loads(book_row["bids"])]


def walk(la, lb, ra, ea, rb, eb, limit=1.0):
    """Buy equal shares of both legs while marginal cost (prices + fees) < limit."""
    i = j = 0
    qa = la[0][1] if la else 0
    qb = lb[0][1] if lb else 0
    q = cost = 0.0
    while i < len(la) and j < len(lb):
        pa_, pb_ = la[i][0], lb[j][0]
        mc = pa_ + pb_ + fee_ps(pa_, ra, ea) + fee_ps(pb_, rb, eb)
        if mc >= limit:
            break
        take = min(qa, qb)
        q += take
        cost += take * mc
        qa -= take
        qb -= take
        if qa <= 1e-9:
            i += 1
            qa = la[i][1] if i < len(la) else 0
        if qb <= 1e-9:
            j += 1
            qb = lb[j][1] if j < len(lb) else 0
    return q, cost


snaps = sorted(glob.glob(str(ROOT / "data" / "derived" / "la_books" / SNAP_GLOB)))
print("snapshots", len(snaps), flush=True)
out = []
for sp in snaps:
    B = pd.read_parquet(sp).dropna(subset=["mid"]).drop_duplicates("mid").set_index("mid")
    snap_utc = pd.Timestamp(B.snap_utc.iloc[0])
    k = int(B.snap_k.iloc[0])
    bid = np.full(len(M), np.nan)
    ask = np.full(len(M), np.nan)
    have = B.index.intersection(POS.index)
    pb_ = B.loc[have, "bids"].map(lambda s: json.loads(s)[0][0] if s and s != "[]" else np.nan).values
    pa_ = B.loc[have, "asks"].map(lambda s: json.loads(s)[0][0] if s and s != "[]" else np.nan).values
    bid[POS.loc[have].values] = pb_
    ask[POS.loc[have].values] = pa_
    px_a = np.where(oa == 0, ask[ia], 1 - bid[ia])
    px_b = np.where(ob == 0, ask[ib], 1 - bid[ib])
    top = px_a + px_b + fee_ps(px_a, rate[ia], expo[ia]) + fee_ps(px_b, rate[ib], expo[ib])
    cand = np.where(np.isfinite(top) & (top < 1.0))[0]
    print(snap_utc, "relations with top-of-book cost < 1:", len(cand), flush=True)
    for ix in cand:
        r = R.iloc[ix]
        a, b = ia[ix], ib[ix]
        ma_, mb_ = M.iloc[a], M.iloc[b]
        ba_row, bb_row = B.loc[r.ma], B.loc[r.mb]
        la, lb = ladder(ba_row, r.oa), ladder(bb_row, r.ob)
        q, cost = walk(la, lb, rate[a], expo[a], rate[b], expo[b])
        q5, cost5 = walk(la, lb, rate[a], expo[a], rate[b], expo[b], limit=0.995)
        qs, costs = walk(la, lb, rate_sens[a], expo[a], rate_sens[b], expo[b])
        ca, cb = cancel_payoff(ma_, r.oa), cancel_payoff(mb_, r.ob)
        out.append({
            "snap_utc": snap_utc, "snap_k": k, "rel_id": f"{r.ma}:{r.oa}|{r.mb}:{r.ob}", "family": r.family,
            "key": r.key, "note": r.note, "ma": r.ma, "oa": int(r.oa), "mb": r.mb, "ob": int(r.ob),
            "q_a": ma_.question, "q_b": mb_.question, "out_a": json.loads(ma_.outcomes)[r.oa],
            "out_b": json.loads(mb_.outcomes)[r.ob], "px_a": px_a[ix], "px_b": px_b[ix], "top_cost": top[ix],
            "shares": q, "cost": cost, "profit": q - cost, "shares_995": q5, "profit_995": q5 - cost5,
            "shares_sens": qs, "profit_sens": qs - costs,
            "min_size": max(ma_.orderMinSize or 5, mb_.orderMinSize or 5),
            "ts_a": ba_row.ts_ms, "ts_b": bb_row.ts_ms, "fetch_gap_s": abs(ba_row.fetch_unix - bb_row.fetch_unix),
            "end_a": ma_.endDate, "end_b": mb_.endDate, "gst_a": ma_.gameStartTime, "gst_b": mb_.gameStartTime,
            "smt_a": ma_.sportsMarketType, "smt_b": mb_.sportsMarketType,
            "neg_a": ma_.negRisk, "neg_b": mb_.negRisk, "ev_a": ma_.event_slug, "ev_b": mb_.event_slug,
            "rate_a": rate[a], "rate_b": rate[b], "cancel_payoff": ca + cb,
        })
O = pd.DataFrame(out)
O.to_parquet(ROOT / "data" / "derived" / f"la_opps_{DATE}_{TAG}.parquet", index=False)
print("rows", len(O))
