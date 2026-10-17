"""k-of-n count constraints across separate (non neg-risk) Yes/No markets of one Gamma event - read-only.

Run from polymarket_research/:
    python -m analyses.logical_arb.06_count_sets define <tag>            # writes la_extra_markets_<tag>.parquet
    python -m analyses.logical_arb.06_count_sets eval <tag> <snap_glob>  # writes la_cnt_opps_<tag>.parquet

A set lists every team that can qualify (n markets) and the competition format fixes how many qualify (k).
Bundles (equal q shares per leg, all taker, fees per leg from feeSchedule):
  ALL_NO : buy NO on all n markets. At most k resolve YES, so payoff >= (n-k) per set in every state
           (fewer qualifiers, e.g. a cancelled season, only raise the payoff). Arbitrage iff cost < n-k.
  ALL_YES: buy YES on all n. Pays exactly k only if the stage is completed as scheduled; a cancellation that
           resolves everything NO pays 0, so at best NEAR-dominance. Arbitrage iff cost < k.
Incomplete lists (n_listed < league size) only support ALL_NO with payoff >= n_listed - k.
k values are from the competition formats (2026-27 seasons) and must match the markets' own rules (checked
by reading the descriptions printed by `define`).
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MODE, TAG = sys.argv[1], sys.argv[2]
SETS = {  # event_id: (k, note)
    "448179": (14, "NFL: 14 of 32 make the postseason"),
    "956266": (4, "AFC: 4 teams play in the Divisional Round"), "956267": (4, "NFC: 4 teams in the Divisional Round"),
    "956268": (2, "AFC Championship Game: 2 teams"), "956269": (2, "NFC Championship Game: 2 teams"),
    "681898": (16, "NBA: 16 of 30 make the playoffs (after play-in)"), "681890": (8, "NBA: 8 teams in the play-in"),
    "956297": (4, "NBA East semis: 4"), "956298": (4, "NBA West semis: 4"),
    "956299": (2, "NBA ECF: 2"), "956300": (2, "NBA WCF: 2"),
    "956303": (4, "NHL East 2nd round: 4"), "956302": (4, "NHL West 2nd round: 4"),
    "956301": (2, "NHL ECF: 2"), "956304": (2, "NHL WCF: 2"),
    "1024891": (8, "UCL league phase top 8"), "1024892": (16, "UCL league phase 9th-24th"),
    "956313": (16, "UCL Round of 16"), "956314": (8, "UCL quarter-finals"), "956315": (4, "UCL semis"),
    "1183380": (2, "UCL final"),
    "1024893": (8, "UEL league phase top 8"), "1024920": (16, "UEL league phase 9th-24th"),
    "1024921": (8, "UECL league phase top 8"), "1024922": (16, "UECL league phase 9th-24th"),
    "904907": (3, "EPL: 3 relegated"), "904908": (3, "LaLiga: 3 relegated"), "904911": (3, "Serie A: 3 relegated"),
    "948140": (12, "CFP: 12-team field (list incomplete)"), "801515": (2, "CFP national title game (list incomplete)"),
}
# Oscars 2027 nominations (99th Academy Awards; nominations 2027-01-21): k = nominee slots per category
# (Best Picture 10, others 5). NEAR at best: ties for the last slot, or a co-directing duo listed as two persons,
# can push the number of YES above k. Casting is left out (new category; slot count not verified).
for _eid, _cat, _k in [("531532", "Picture", 10), ("1198837", "Director", 5), ("531533", "Actor", 5),
                       ("1188161", "Actress", 5), ("1188310", "Supp. Actor", 5), ("1188311", "Supp. Actress", 5),
                       ("1188312", "Orig. Screenplay", 5), ("1188313", "Adapt. Screenplay", 5),
                       ("1188314", "Cinematography", 5), ("1188316", "Makeup", 5), ("1188317", "Doc Feature", 5),
                       ("1188319", "Score", 5), ("1188320", "Animated Feature", 5), ("1193376", "International", 5),
                       ("1193378", "VFX", 5), ("1193412", "Sound", 5), ("1193413", "Costume", 5),
                       ("1193414", "Production Design", 5), ("1193415", "Editing", 5), ("1193416", "Doc Short", 5),
                       ("1193417", "Live Short", 5), ("1193418", "Animated Short", 5), ("1198846", "Song", 5)]:
    SETS[_eid] = (_k, f"Oscars 2027 {_cat} nominations: {_k} slots (list may be incomplete; NEAR)")
# Ballon d'Or 2026 top-k finish (ceremony 2026-10-26): ties are broken by France Football's list, then alphabetically,
# so exactly k players resolve YES (postponement past 2026-11-09 or cancellation -> all No). Lists are incomplete.
for _eid, _k in [("1189431", 2), ("811117", 3), ("811116", 5), ("1105185", 10), ("1105210", 3), ("1105212", 5), ("1105213", 10)]:
    SETS[_eid] = (_k, f"Ballon d'Or 2026 top {_k} ({'women' if _eid.startswith('11052') else 'men'}; list incomplete)")
# Best Director lists two co-directing duos as separate persons (Javier Calvo + Javier Ambrossi; Phil Lord +
# Christopher Miller): one slot can make two listed names YES, so at most 5 + 2 = 7 listed names resolve YES.
SETS["1198837"] = (7, "Oscars 2027 Director: 5 slots but 2 listed duos -> at most 7 listed persons YES (NEAR)")
# lists that contain every possible qualifier (all league / conference members); others support ALL_NO only
COMPLETE = {e for e, (k, note) in SETS.items() if not note.startswith(("Oscars", "Ballon")) and e not in ("948140", "801515")}
BOOKS = ROOT / "data" / "derived" / (f"la_books_{sys.argv[4]}" if len(sys.argv) > 4 and sys.argv[4] != "main" else "la_books")
M = pd.read_parquet(ROOT / "data" / "derived" / f"la_markets_{TAG}.parquet",
                    columns=["id", "question", "description", "event_id", "event_title", "negRisk", "outcomes",
                             "acceptingOrders", "fee_rate", "fee_exponent", "feesEnabled", "orderMinSize", "endDate"])
M["event_id"] = M.event_id.astype(str)
M["id"] = M.id.astype(str)
M = M[M.event_id.isin(SETS) & (M.acceptingOrders == True) & (M.outcomes == '["Yes", "No"]')].copy()  # noqa: E712

if MODE == "define":
    M[["id"]].to_parquet(ROOT / "data" / "derived" / f"la_cnt_markets_{TAG}.parquet", index=False)
    for eid, g in M.groupby("event_id"):
        print(eid, SETS[eid][0], len(g), g.event_title.iloc[0], "| negRisk", g.negRisk.unique())
    sys.exit(0)

rate = np.where(M.feesEnabled == False, 0.0, M.fee_rate.fillna(0.05)).astype(float)  # noqa: E712
M["rate"] = rate
M["expo"] = M.fee_exponent.fillna(1.0)


def walk_set(ladders, rates, expos, payoff):
    """Buy q shares of every leg while the marginal set cost (sum of leg prices + fees) < payoff."""
    pos = [0] * len(ladders)
    left = [lad[0][1] if lad else 0.0 for lad in ladders]
    if any(not lad for lad in ladders):
        return 0.0, 0.0, np.nan
    q = cost = 0.0
    top = None
    while True:
        px = [ladders[i][pos[i]][0] for i in range(len(ladders))]
        mc = sum(p + r * (p * (1 - p)) ** e for p, r, e in zip(px, rates, expos))
        top = mc if top is None else top
        if mc >= payoff:
            break
        take = min(left)
        q += take
        cost += take * mc
        done = False
        for i in range(len(ladders)):
            left[i] -= take
            if left[i] <= 1e-9:
                pos[i] += 1
                if pos[i] >= len(ladders[i]):
                    done = True
                    break
                left[i] = ladders[i][pos[i]][1]
        if done:
            break
    return q, cost, top


out = []
for sp in sorted(glob.glob(str(BOOKS / sys.argv[3]))):
    B = pd.read_parquet(sp, columns=["mid", "bids", "asks", "fetch_unix", "snap_utc"], filters=[("mid", "in", list(M.id))])
    B = B.drop_duplicates("mid").set_index("mid")
    if B.empty:
        continue
    snap = B.snap_utc.iloc[0]
    for eid, g in M.groupby("event_id"):
        k, note = SETS[eid]
        n = len(g)  # all listed markets of the event (open, Yes/No); missing books count as unbuyable legs
        g = g[g.id.isin(B.index)]
        if len(g) == 0:
            continue
        bk = B.loc[g.id]
        yes = [json.loads(a) for a in bk.asks]
        no = [[(round(1 - p, 6), s) for p, s in json.loads(b)] for b in bk.bids]
        for side, lads in (("ALL_NO", no), ("ALL_YES", yes)):
            if side == "ALL_YES" and eid not in COMPLETE:
                continue  # an incomplete list gives no lower bound on the YES payoff
            # a leg with an empty ladder cannot be bought: drop it and weaken the payoff bound accordingly
            # (NO on a subset S pays >= |S|-k; YES on S pays >= k-(n-|S|))
            keep = [i for i, lad in enumerate(lads) if lad]
            ns = len(keep)  # legs actually buyable; n - ns legs are missing or have an empty ladder
            pay = ns - k if side == "ALL_NO" else k - (n - ns)
            if pay <= 0:
                continue
            q, cost, top = walk_set([lads[i] for i in keep], g.rate.iloc[keep].tolist(), g.expo.iloc[keep].tolist(), pay)
            out.append({"snap_utc": snap, "event_id": eid, "note": note, "k": k, "n": n, "n_legs": ns, "side": side,
                        "payoff_per_set": pay, "top_set_cost": top, "shares": q, "cost": cost,
                        "profit": q * pay - cost if q else 0.0,
                        "sum_bid": float(sum(json.loads(b)[0][0] if json.loads(b) else 0 for b in bk.bids)),
                        "sum_ask": float(sum(json.loads(a)[0][0] if json.loads(a) else 1 for a in bk.asks)),
                        "max_fetch_gap_s": float(bk.fetch_unix.max() - bk.fetch_unix.min()),
                        "end": g.endDate.max()})
O = pd.DataFrame(out)
OUTTAG = sys.argv[5] if len(sys.argv) > 5 else TAG
O.to_parquet(ROOT / "data" / "derived" / f"la_cnt_opps_{OUTTAG}.parquet", index=False)
O["gap_to_payoff"] = O.top_set_cost - O.payoff_per_set
print(O.groupby(["event_id", "note", "side"]).agg(n=("n", "first"), k=("k", "first"), snaps=("snap_utc", "nunique"),
                                                 min_gap=("gap_to_payoff", "min"), med_gap=("gap_to_payoff", "median"),
                                                 n_pos=("profit", lambda x: int((x > 0).sum())),
                                                 max_profit=("profit", "max")).to_string())
