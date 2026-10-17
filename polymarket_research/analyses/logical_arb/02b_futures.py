"""Cross-event nested futures relations (child => parent for the same team/person/film) - read-only, offline.

Run from polymarket_research/:  python -m analyses.logical_arb.02b_futures [date]
Output: data/derived/la_relations_fut_<date>.parquet (same schema as la_relations_<date>.parquet)

Chains were chosen by hand from Gamma event titles (manual review, 2026-10-17). Each listed edge
says "YES in child event implies YES in parent event for the same entity"; all transitive pairs are
emitted. `strength` is the a-priori rule assessment before reading the full rules (TRUE = implied by
competition format; NEAR = implied except for a stated edge case). EXCL pairs are mutually exclusive.
"""
from __future__ import annotations

import difflib
import itertools
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

# child -> parent edges (event ids). Lists on either side mean "whichever event lists the entity".
EDGES = [
    # NFL
    (["202857"], ["203722", "203716"], "TRUE", "NFL champion must win its conference"),
    (["203722"], ["956268"], "TRUE", "AFC champion advanced to AFC Championship Game"),
    (["203716"], ["956269"], "TRUE", "NFC champion advanced to NFC Championship Game"),
    (["956268"], ["956266"], "NEAR", "AFC CG team advanced to Divisional Round (bye wording)"),
    (["956269"], ["956267"], "NEAR", "NFC CG team advanced to Divisional Round (bye wording)"),
    (["956266", "956267"], ["448179"], "TRUE", "Divisional-round team made postseason"),
    (["232598", "232603", "232605", "232614", "232617", "232622", "232642", "232647"], ["448179"], "TRUE",
     "NFL division champion qualifies for playoffs"),
    # NBA
    (["478277"], ["634482", "630022"], "TRUE", "NBA champion won its conference"),
    (["634482"], ["956299"], "TRUE", "East champion advanced to ECF"),
    (["630022"], ["956300"], "TRUE", "West champion advanced to WCF"),
    (["956299", "956300"], ["681898"], "TRUE", "Conference finalist made playoffs"),
    # NHL
    (["588160"], ["652355", "652354"], "TRUE", "NHL champion won its conference"),
    (["652355"], ["956301"], "TRUE", "East champion advanced to ECF"),
    (["652354"], ["956304"], "TRUE", "West champion advanced to WCF"),
    (["956301"], ["956303"], "TRUE", "ECF team advanced to second round"),
    (["956304"], ["956302"], "TRUE", "WCF team advanced to second round"),
    (["956303", "956302"], ["1098839"], "TRUE", "Second-round team made playoffs"),
    (["1183496", "1183499", "1094154"], ["1098839"], "TRUE", "Division winner / Presidents' Trophy makes playoffs"),
    # MLB
    (["179312"], ["215866"], "TRUE", "World Series champion (if AL) won the AL pennant"),
    # College football
    (["357914"], ["801515"], "TRUE", "National champion played in the title game"),
    (["801515"], ["801906"], "TRUE", "Title-game team made semis"),
    (["801906"], ["801879"], "TRUE", "Semifinal team made quarters"),
    (["801879"], ["948140"], "TRUE", "Quarterfinal team made CFP"),
    (["801843"], ["801879"], "NEAR", "Top-4 seed gets bye into quarters (format-dependent)"),
    (["801843"], ["948140"], "TRUE", "Top-4 seed is in the CFP"),
    # UEFA Champions League
    (["659671"], ["1183380"], "TRUE", "UCL champion played the final"),
    (["988995"], ["1183380"], "TRUE", "UCL runner-up played the final"),
    (["1183380"], ["956315"], "TRUE", "Finalist reached semis"),
    (["956315"], ["956314"], "TRUE", "Semifinalist reached quarters"),
    (["956314"], ["956313"], "TRUE", "Quarterfinalist reached R16"),
    (["994204"], ["1024891"], "TRUE", "League-phase winner finished top 8"),
    (["1024891"], ["956313"], "TRUE", "Top-8 league phase goes straight to R16"),
    # Domestic leagues
    (["659518"], ["924594"], "TRUE", "EPL champion finished top 2"),
    (["839398"], ["924594"], "TRUE", "EPL runner-up finished top 2"),
    (["924594"], ["927565"], "TRUE", "Top 2 => top 4"),
    (["927565"], ["924595"], "TRUE", "Top 4 => top 5"),
    (["924595"], ["924596"], "TRUE", "Top 5 => top 6"),
    (["927565"], ["867346"], "NEAR", "EPL top 4 qualifies for UCL (UEFA sanctions / multi-club rules)"),
    (["659548"], ["924599"], "TRUE", "LaLiga champion finished top 2"),
    (["839399"], ["924599"], "TRUE", "LaLiga runner-up finished top 2"),
    (["924599"], ["867558"], "NEAR", "LaLiga top 2 qualifies for UCL (UEFA sanctions)"),
    (["659488"], ["924597"], "TRUE", "Serie A champion finished top 4"),
    (["839408"], ["924597"], "TRUE", "Serie A runner-up finished top 4"),
    (["924597"], ["867604"], "NEAR", "Serie A top 4 qualifies for UCL (UEFA sanctions)"),
    (["681261", "839400"], ["867569"], "NEAR", "Bundesliga top 2 qualifies for UCL (UEFA sanctions)"),
    (["659573"], ["867622"], "NEAR", "Ligue 1 champion qualifies for UCL (UEFA sanctions)"),
    # Awards
    (["48361"], ["1189431"], "TRUE", "Ballon d'Or winner is top 2"),
    (["1189431"], ["811117"], "TRUE", "Top 2 => top 3"),
    (["811117"], ["811116"], "TRUE", "Top 3 => top 5"),
    (["811116"], ["1105185"], "TRUE", "Top 5 => top 10"),
    (["994444"], ["1105210"], "TRUE", "Women's Ballon d'Or winner is top 3"),
    (["1105210"], ["1105212"], "TRUE", "Top 3 => top 5"),
    (["1105212"], ["1105213"], "TRUE", "Top 5 => top 10"),
    # Politics
    (["31552"], ["30829", "31875"], "NEAR", "2028 winner was a major-party nominee (independent / party switch)"),
]
EXCL = [
    (["659671"], ["988995"], "TRUE", "UCL champion vs UCL 2nd place"),
    (["1024891"], ["1024892"], "TRUE", "UCL top 8 vs 9th-24th"),
    (["659518"], ["904907"], "TRUE", "EPL champion vs relegated"),
    (["659548"], ["904908"], "TRUE", "LaLiga champion vs relegated"),
    (["659488"], ["904911"], "TRUE", "Serie A champion vs relegated"),
    (["681261"], ["904909"], "TRUE", "Bundesliga champion vs relegated"),
    (["659573"], ["904910"], "TRUE", "Ligue 1 champion vs relegated"),
    (["927565"], ["904907"], "TRUE", "EPL top 4 vs relegated"),
]

m = pd.read_parquet(ROOT / "data" / "derived" / f"la_markets_{DATE}.parquet")
m = m[(m.acceptingOrders == True) & m.clobTokenIds.notna()].copy()  # noqa: E712
m["id"] = m["id"].astype(str)
m["outs"] = m.outcomes.map(lambda s: json.loads(s) if isinstance(s, str) else [])
m = m[m.outs.map(lambda o: o == ["Yes", "No"])]
# Oscars: pair each 'Best X Winner' with 'Best X Nominations'
osc = m[m.event_title.str.startswith("Oscars 2027: Best", na=False)].groupby(["event_id", "event_title"]).size().reset_index()
osc["cat"] = osc.event_title.str.replace(r"\s*(Winner|Nominations)\s*$", "", regex=True).str.strip()
osc["kind"] = osc.event_title.str.extract(r"(Winner|Nominations)\s*$")[0]
for cat, g in osc.groupby("cat"):
    w, n = g[g.kind == "Winner"], g[g.kind == "Nominations"]
    if len(w) == 1 and len(n) == 1:
        EDGES.append(([w.event_id.iloc[0]], [n.event_id.iloc[0]], "TRUE", f"{cat}: winner must be a nominee"))


def norm(s):
    s = (s if isinstance(s, str) else "").lower()
    s = re.sub(r"\b(fc|cf|afc|sc|the|de|club)\b", " ", s)
    s = re.sub(r"[^a-z0-9à-ÿ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ent(r):
    return norm(r.groupItemTitle if isinstance(r.groupItemTitle, str) and r.groupItemTitle else r.question)


m["ent"] = [ent(r) for r in m.itertuples()]
by_ev = {eid: g for eid, g in m.groupby("event_id")}


def match(e, cands: pd.DataFrame):
    if cands is None or cands.empty:
        return None
    ex = cands[cands.ent == e]
    if len(ex) == 1:
        return ex.iloc[0]
    sub = cands[[(len(e) >= 5 and (e in c or c in e)) for c in cands.ent]]
    if len(sub) == 1:
        return sub.iloc[0]
    best = difflib.get_close_matches(e, list(cands.ent), n=2, cutoff=0.86)
    if len(best) == 1:
        return cands[cands.ent == best[0]].iloc[0]
    return None


# build entity -> event -> market map along the chains, then emit transitive pairs
parents = {}
for ch, pa, st, why in EDGES:
    for c in ch:
        parents.setdefault(c, []).append((pa, st, why))

rels = []


def walk(child_row, ev, strength, path, seen):
    for pa, st, why in parents.get(ev, []):
        for p in pa:
            if p in seen:
                continue
            pr = match(child_row.ent, by_ev.get(p))
            if pr is None:
                continue
            s2 = "NEAR" if (strength == "NEAR" or st == "NEAR") else "TRUE"
            rels.append(("fut_nest", f"{child_row.event_id}->{p}", child_row.id, 1, pr.id, 0,
                         f"[{s2}] {' / '.join(path + [why])}"))
            walk(pr, p, s2, path + [why], seen | {p})


for ev in parents:
    for r in by_ev.get(ev, pd.DataFrame()).itertuples():
        walk(r, ev, "TRUE", [], {ev})
for ea, eb, st, why in EXCL:
    for a in ea:
        for r in by_ev.get(a, pd.DataFrame()).itertuples():
            for b in eb:
                pr = match(r.ent, by_ev.get(b))
                if pr is not None:
                    rels.append(("fut_excl", f"{a}x{b}", r.id, 1, pr.id, 1, f"[{st}] {why}"))

R = pd.DataFrame(rels, columns=["family", "key", "ma", "oa", "mb", "ob", "note"]).drop_duplicates(["ma", "oa", "mb", "ob"])
info = m.set_index("id")
cols = ["question", "conditionId", "clobTokenIds", "negRisk", "event_id", "event_slug", "fee_rate", "fee_exponent",
        "feeType", "endDate", "gameStartTime", "sportsMarketType", "orderMinSize", "orderPriceMinTickSize", "outs"]
for leg in ("a", "b"):
    sub = info.loc[R["m" + leg], cols].reset_index(drop=True)
    sub.columns = [f"{c}_{leg}" for c in cols]
    R = pd.concat([R.reset_index(drop=True), sub], axis=1)
R["outs_a"] = R.outs_a.map(json.dumps)
R["outs_b"] = R.outs_b.map(json.dumps)
R["rel_id"] = R.ma + ":" + R.oa.astype(str) + "|" + R.mb + ":" + R.ob.astype(str)
out = ROOT / "data" / "derived" / f"la_relations_fut_{DATE}.parquet"
R.to_parquet(out, index=False)
print(out, len(R))
print(R.groupby(["family"]).size())
print(R.note.str.extract(r"^\[(\w+)\]")[0].value_counts())
print(R.sample(min(25, len(R)), random_state=1)[["question_a", "question_b", "note"]].to_string())
