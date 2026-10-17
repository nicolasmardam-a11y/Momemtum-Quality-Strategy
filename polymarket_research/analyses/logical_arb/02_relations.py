"""Generate candidate logical relations between open Polymarket markets (read-only, offline).

Run from polymarket_research/:  python -m analyses.logical_arb.02_relations [YYYY-MM-DD]
Input : data/derived/la_markets_<date>.parquet (from 01_pull_events)
Output: data/derived/la_relations_<date>.parquet

Every relation is a 2-leg bundle (market_a, outcome_a) + (market_b, outcome_b) whose payoff is
>= 1 in every state *according to the question text / structural parsing*. Whether the written
rules really support it is checked by hand later (03 / notes). Families:

  grid_*   sports full-game score predicates (moneyline, draw, spreads, totals, team totals,
           exact score, exact margin, BTTS; soccer also halves) evaluated on a score grid;
           a pair "covers" if payoff_a + payoff_b >= 1 on every grid state (ties pay 0.5 on
           2-way moneylines, the conservative 50-50 assumption).
  acc_*    accumulation ladders: Q1 <= Q2 pointwise and t1 >= t2  =>  (Q1 > t1) implies (Q2 > t2)
           (lines of one quantity, 1H/2H/quarters vs full game, team vs game totals, corners,
           player props: shots/SoT, goals/G+A, anytime scorer, TD props, completions/attempts).
  lad_*    non-sports within-event ladders parsed from groupItemTitle (dates with by/before,
           numeric thresholds with above/reach/+ or below/dip).
  dup      identical normalised question text in different markets.
  xdate    cross-event date ladders: same question template, different 'by <date>'.
"""
from __future__ import annotations

import difflib
import itertools
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
OUT = ROOT / "data" / "derived" / f"la_relations_{DATE}.parquet"

rels: list[tuple] = []  # (family, key, ma, oa, mb, ob, note)


def add(fam, key, ma, oa, mb, ob, note=""):
    if ma == mb:
        return
    if (ma, oa) > (mb, ob):
        ma, oa, mb, ob = mb, ob, ma, oa
    rels.append((fam, key, ma, oa, mb, ob, note))


def norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9à-ÿ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def team_side(name: str, home: str, away: str) -> int | None:
    """0 = home (first in title), 1 = away; None if ambiguous."""
    n, h, a = norm(name), norm(home), norm(away)
    if not n:
        return None
    if n == h and n != a:
        return 0
    if n == a and n != h:
        return 1
    hs = n in h or h in n
    as_ = n in a or a in n
    if hs and not as_:
        return 0
    if as_ and not hs:
        return 1
    return None


# ----------------------------------------------------------------------------- load
m = pd.read_parquet(ROOT / "data" / "derived" / f"la_markets_{DATE}.parquet")
m = m[(m.acceptingOrders == True) & m.clobTokenIds.notna()].copy()  # noqa: E712
m["outs"] = m.outcomes.map(lambda s: json.loads(s) if isinstance(s, str) else [])
m = m[m.outs.map(len) == 2].copy()
m["gst"] = pd.to_datetime(m.gameStartTime, utc=True, errors="coerce", format="ISO8601")
m["end"] = pd.to_datetime(m.endDate, utc=True, errors="coerce", format="ISO8601")
m["start"] = pd.to_datetime(m.startDate, utc=True, errors="coerce", format="ISO8601")
ASOF = pd.to_datetime(m.fetched_at_utc.iloc[0], utc=True)
# any resting order on either side according to Gamma (filter only; books are re-read live)
m["has_book"] = (m.bestBid.fillna(0) > 0) | (m.bestAsk.fillna(1) < 1)
m = m[m.has_book].copy()
m["id"] = m["id"].astype(str)
print("markets with some book", len(m))

SUFFIX = re.compile(r"(\d{4}-\d{2}-\d{2})(-[a-z0-9-]+)?$")


def base_slug(s: str) -> str:
    mm = SUFFIX.search(s or "")
    return s[: mm.end(1)] if mm else s


sp = m[m.sportsMarketType.notna()].copy()
sp["game"] = sp.event_slug.map(base_slug)
sp["title_clean"] = sp.event_title.str.replace(r"\s+-\s+.*$", "", regex=True)

# ----------------------------------------------------------------------------- grid predicates
SOCCER_H = 8  # goals per team per half on the soccer grid (0..7)


def soccer_states():
    r = np.arange(SOCCER_H)
    h1, a1, h2, a2 = np.meshgrid(r, r, r, r, indexing="ij")
    return {k: v.ravel() for k, v in dict(h1=h1, a1=a1, h2=h2, a2=a2).items()}


SS = soccer_states()
SS["h"], SS["a"] = SS["h1"] + SS["h2"], SS["a1"] + SS["a2"]


def gen_states(maxs):
    r = np.arange(maxs + 1)
    h, a = np.meshgrid(r, r, indexing="ij")
    return {"h": h.ravel(), "a": a.ravel()}


RANGE = re.compile(r"by (\d+)\s*-\s*(\d+)|by (\d+)\+")


def predicate(r, S, home, away, soccer):
    """Payoff vector of outcome-0 token on grid S (values 0, .5, 1), or None if unsupported."""
    t, q, outs = r.sportsMarketType, r.question or "", r.outs
    H, A = S["h"], S["a"]

    def side_of(name):
        return team_side(name, home, away)

    def tm(side, half=None):
        if half is None:
            return (H, A)[side] if side in (0, 1) else None
        return (S["h1"], S["a1"])[side] if half == 1 else (S["h2"], S["a2"])[side]

    if t == "moneyline":
        if outs == ["Yes", "No"]:
            if re.search(r"end in a draw", q, re.I):
                return (H == A).astype(float)
            mm = re.match(r"Will (.+?) win", q)
            if not mm:
                return None
            s = side_of(mm.group(1))
            if s is None:
                return None
            return ((H > A) if s == 0 else (A > H)).astype(float)
        s0 = side_of(outs[0])
        if s0 is None or side_of(outs[1]) != 1 - s0:
            return None
        if soccer:  # 2-way soccer moneyline would need draw rules; skip
            return None
        win = (H > A) if s0 == 0 else (A > H)
        return np.where(H == A, 0.5, win.astype(float))
    if t in ("spreads", "second_half_spreads", "first_half_spreads"):
        if not np.isfinite(r.line) or float(r.line).is_integer():
            return None
        s0 = side_of(outs[0])
        if s0 is None:
            return None
        if t == "spreads":
            mg = (H - A) if s0 == 0 else (A - H)
        elif soccer and t == "second_half_spreads":
            mg = (S["h2"] - S["a2"]) if s0 == 0 else (S["a2"] - S["h2"])
        elif soccer and t == "first_half_spreads":
            mg = (S["h1"] - S["a1"]) if s0 == 0 else (S["a1"] - S["h1"])
        else:
            return None
        return (mg > -float(r.line)).astype(float)
    if t == "totals":
        return (H + A > r.line).astype(float) if np.isfinite(r.line) else None
    if t in ("team_totals", "soccer_team_totals"):
        mm = re.search(r"(?::\s*)?([^:]+?)\s+(?:Team Total: )?O/U", q)
        s = side_of(mm.group(1)) if mm else None
        if s is None or not np.isfinite(r.line):
            return None
        return (tm(s) > r.line).astype(float)
    if t == "both_teams_to_score":
        return ((H > 0) & (A > 0)).astype(float)
    if t == "soccer_exact_score":
        mm = re.match(r"Exact Score: (.+) (\d+) - (\d+) (.+)\?$", q)
        if not mm:
            return None
        s = side_of(mm.group(1))
        if s is None or side_of(mm.group(4)) != 1 - s:
            return None
        x, y = int(mm.group(2)), int(mm.group(3))
        hx, ay = (x, y) if s == 0 else (y, x)
        return ((H == hx) & (A == ay)).astype(float)
    if t == "exact_margin":
        if re.search(r"Tie", q):
            return (H == A).astype(float)
        mm = re.match(r"Exact Margin: (.+?) by (.+)$", q)
        if not mm:
            return None
        s = side_of(mm.group(1))
        if s is None:
            return None
        mg = (H - A) if s == 0 else (A - H)
        rg = mm.group(2).strip()
        m1 = re.match(r"(\d+)\s*-\s*(\d+)$", rg)
        m2 = re.match(r"(\d+)\+$", rg)
        if m1:
            return ((mg >= int(m1.group(1))) & (mg <= int(m1.group(2)))).astype(float)
        if m2:
            return (mg >= int(m2.group(1))).astype(float)
        return None
    if not soccer:
        return None
    # ---- soccer half markets
    if t in ("first_half_totals", "second_half_totals"):
        hf = 1 if t.startswith("first") else 2
        return (tm(0, hf) + tm(1, hf) > r.line).astype(float)
    if t in ("soccer_first_half_team_totals", "soccer_second_half_team_totals"):
        hf = 1 if "first" in t else 2
        mm = re.search(r":\s*(.+?)\s+(?:1st|2nd) Half O/U", q)
        s = side_of(mm.group(1)) if mm else None
        if s is None:
            return None
        return (tm(s, hf) > r.line).astype(float)
    if t == "soccer_halftime_result":
        if re.search(r"Draw at halftime", q):
            return (S["h1"] == S["a1"]).astype(float)
        mm = re.match(r"(.+?) leading at halftime", q)
        s = side_of(mm.group(1)) if mm else None
        if s is None:
            return None
        return ((S["h1"] > S["a1"]) if s == 0 else (S["a1"] > S["h1"])).astype(float)
    if t == "soccer_second_half_result":
        if re.search(r"[Dd]raw", q):
            return (S["h2"] == S["a2"]).astype(float)
        mm = re.match(r"(.+?) to win the second half", q)
        s = side_of(mm.group(1)) if mm else None
        if s is None:
            return None
        return ((S["h2"] > S["a2"]) if s == 0 else (S["a2"] > S["h2"])).astype(float)
    if t == "both_teams_to_score_first_half":
        return ((S["h1"] > 0) & (S["a1"] > 0)).astype(float)
    if t == "both_teams_to_score_second_half":
        return ((S["h2"] > 0) & (S["a2"] > 0)).astype(float)
    if t == "soccer_first_half_exact_score":
        mm = re.match(r"1st Half Exact Score: (.+) (\d+) - (\d+) (.+)\?$", q)
        if not mm:
            return None
        s = side_of(mm.group(1))
        if s is None:
            return None
        x, y = int(mm.group(2)), int(mm.group(3))
        hx, ay = (x, y) if s == 0 else (y, x)
        return ((S["h1"] == hx) & (S["a1"] == ay)).astype(float)
    return None


GRID_TYPES = {"moneyline", "spreads", "totals", "team_totals", "soccer_team_totals", "both_teams_to_score",
              "soccer_exact_score", "exact_margin", "first_half_totals", "second_half_totals",
              "soccer_first_half_team_totals", "soccer_second_half_team_totals", "soccer_halftime_result",
              "soccer_second_half_result", "both_teams_to_score_first_half", "both_teams_to_score_second_half",
              "soccer_first_half_exact_score", "second_half_spreads", "first_half_spreads"}


def covering_pairs(P):
    """P: (n, S) payoff of outcome-0 tokens. Return list of (i, oi, j, oj) with payoff_i + payoff_j >= 1 everywhere."""
    P2 = np.concatenate([P, 1 - P])  # rows 0..n-1 outcome 0, n..2n-1 outcome 1
    Z = (P2 == 0).astype(np.float32)
    Hh = (P2 == 0.5).astype(np.float32)
    L = (P2 < 1).astype(np.float32)
    fail = Z @ L.T + Hh @ Z.T
    fail = fail + fail.T
    n = P.shape[0]
    out = []
    ii, jj = np.where(fail == 0)
    for a, b in zip(ii, jj):
        if a >= b:
            continue
        i, oi = a % n, a // n
        j, oj = b % n, b // n
        if i == j:
            continue
        out.append((i, oi, j, oj))
    return out


import os  # noqa: E402
REUSE = os.environ.get("LA_REUSE_SPORTS")  # path of an earlier relations file: reuse its grid_/acc_ rows
ng = 0
if REUSE:
    old_r = pd.read_parquet(REUSE, columns=["family", "key", "ma", "oa", "mb", "ob", "note"])
    old_r = old_r[old_r.family.str.startswith(("grid_", "acc"))]
    rels.extend(old_r.itertuples(index=False, name=None))
    del old_r
    print("reused sports relations", len(rels))
for game, g in ([] if REUSE else sp[sp.sportsMarketType.isin(GRID_TYPES)].groupby("game")):
    titles = g.title_clean.value_counts().index
    mm = re.match(r"(.+?)\s+vs\.?\s+(.+)$", titles[0]) if len(titles) else None
    if not mm:
        continue
    home, away = mm.group(1).strip(), mm.group(2).strip()
    soccer = g.sportsMarketType.str.startswith("soccer_").any() or g.question.str.contains("end in a draw").any()
    if soccer:
        S = SS
    else:
        lines = pd.concat([g.line.abs(), g.line.abs()]).dropna()
        maxs = int(min(250, max(30, 1.6 * (lines.max() if len(lines) else 30))))
        S = gen_states(maxs)
    preds, idx = [], []
    for k, r in g.iterrows():
        p = predicate(r, S, home, away, soccer)
        if p is None or p.min() == p.max():
            continue
        preds.append(p)
        idx.append(r)
    if len(preds) < 2:
        continue
    P = np.vstack(preds)
    for i, oi, j, oj in covering_pairs(P):
        ri, rj = idx[i], idx[j]
        if ri.event_id == rj.event_id and ri.negRisk and rj.negRisk:
            continue  # inside one neg-risk event: complete-set family, not this study
        fam = "grid_soccer" if soccer else "grid_other"
        add(fam, game, ri.id, oi, rj.id, oj, f"{ri.sportsMarketType}~{rj.sportsMarketType}")
    ng += 1
print("grid games", ng, "relations so far", len(rels))

# ----------------------------------------------------------------------------- accumulation ladders
QTY = {  # sportsMarketType -> (quantity, subject-regex or None, period)
    "totals": ("pts", None), "first_half_totals": ("pts_1h", None), "second_half_totals": ("pts_2h", None),
    "q1_totals": ("pts_q1", None), "q2_totals": ("pts_q2", None), "q3_totals": ("pts_q3", None),
    "q4_totals": ("pts_q4", None),
    "team_totals": ("tpts", "team"), "soccer_team_totals": ("tpts", "team"),
    "first_half_team_totals": ("tpts_1h", "team"), "second_half_team_totals": ("tpts_2h", "team"),
    "soccer_first_half_team_totals": ("tpts_1h", "team"), "soccer_second_half_team_totals": ("tpts_2h", "team"),
    "total_corners": ("cor", None), "soccer_first_half_total_corners": ("cor_1h", None),
    "soccer_second_half_total_corners": ("cor_2h", None), "soccer_team_total_corners": ("tcor", "team"),
    "team_touchdowns": ("ttd", "team"), "football_game_total_touchdowns": ("td", None),
    "soccer_player_goals": ("p_goals", "player"), "soccer_anytime_goalscorer": ("p_goals", "player"),
    "soccer_player_assists": ("p_ast", "player"), "soccer_player_goals_plus_assists": ("p_ga", "player"),
    "soccer_player_shots": ("p_shots", "player"), "soccer_player_shots_on_target": ("p_sot", "player"),
    "soccer_player_goalkeeper_saves": ("p_saves", "player"),
    "anytime_touchdowns": ("p_td", "player"), "two_plus_touchdowns": ("p_td", "player"),
    "passing_yards": ("p_passyds", "player"), "passing_touchdowns": ("p_passtd", "player"),
    "rushing_yards": ("p_rushyds", "player"), "receiving_yards": ("p_recyds", "player"),
    "receptions": ("p_rec", "player"), "passing_attempts": ("p_att", "player"),
    "passing_completions": ("p_cmp", "player"),
}
# Q1 <= Q2 pointwise (same subject unless noted 'game'); (q1, q2, scale) means Q2 >= scale*Q1
LE = [("pts_q1", "pts_1h", 1), ("pts_q2", "pts_1h", 1), ("pts_q3", "pts_2h", 1), ("pts_q4", "pts_2h", 1),
      ("pts_1h", "pts", 1), ("pts_2h", "pts", 1), ("pts_q1", "pts", 1), ("pts_q2", "pts", 1),
      ("pts_q3", "pts", 1), ("pts_q4", "pts", 1),
      ("tpts_1h", "tpts", 1), ("tpts_2h", "tpts", 1), ("tpts", "pts", 1), ("tpts_1h", "pts_1h", 1),
      ("tpts_2h", "pts_2h", 1), ("tpts_1h", "pts", 1), ("tpts_2h", "pts", 1),
      ("cor_1h", "cor", 1), ("cor_2h", "cor", 1), ("tcor", "cor", 1), ("ttd", "td", 1),
      ("p_goals", "p_ga", 1), ("p_ast", "p_ga", 1), ("p_sot", "p_shots", 1), ("p_cmp", "p_att", 1),
      ("ttd", "tpts", 6), ("td", "pts", 6)]
NEAR_LE = [("p_goals", "p_sot", 1)]  # a goal is normally a shot on target, but provider definitions vary
GAME_LEVEL = {"pts", "pts_1h", "pts_2h", "pts_q1", "pts_q2", "pts_q3", "pts_q4", "cor", "cor_1h", "cor_2h", "td"}


def subject_of(r, kind):
    q = r.question or ""
    if kind == "player":
        mm = re.match(r"(.+?):", q)
        return norm(mm.group(1)) if mm else None
    # team: text before 'O/U' / 'Team Total' / 'Total Touchdowns' / 'Corners', after 'A vs. B:'
    q2 = re.sub(r"^.+? vs\.? .+?:\s*", "", q)
    mm = re.match(r"(.+?)\s+(?:1st Half |2nd Half |1H |2H )?(?:Team Total:|Total Touchdowns:|O/U|Corners)", q2)
    return norm(mm.group(1)) if mm else None


def threshold(r):
    t = r.sportsMarketType
    if t in ("soccer_anytime_goalscorer", "anytime_touchdowns"):
        return 0.5
    if t == "two_plus_touchdowns":
        return 1.5
    if r.outs not in (["Over", "Under"], ["Yes", "No"]):
        return None
    return float(r.line) if pd.notna(r.line) else None


acc = sp[sp.sportsMarketType.isin(QTY)].copy()
acc["qty"] = acc.sportsMarketType.map(lambda t: QTY[t][0])
acc["subj"] = [subject_of(r, QTY[r.sportsMarketType][1]) if QTY[r.sportsMarketType][1] else "game"
               for r in acc.itertuples()]
acc["thr"] = [threshold(r) for r in acc.itertuples()]
acc = acc[acc.subj.notna() & acc.thr.notna()]
le_map = {}
for q1, q2, sc in LE:
    le_map.setdefault(q1, []).append((q2, sc, "acc"))
for q1, q2, sc in NEAR_LE:
    le_map.setdefault(q1, []).append((q2, sc, "acc_near"))
n0 = len(rels)
for game, g in ([] if REUSE else acc.groupby("game")):
    stm = list(g.itertuples())
    by = {}
    for r in stm:
        by.setdefault((r.qty, r.subj), []).append(r)
    for (q, s), lst in by.items():
        # same quantity ladder
        for r1, r2 in itertools.combinations(lst, 2):
            if r1.thr == r2.thr:
                if r1.id != r2.id:  # equal statements in two markets (duplicates): both crossings
                    add("acc_dup", game, r1.id, 0, r2.id, 1, f"{q} dup")
                    add("acc_dup", game, r1.id, 1, r2.id, 0, f"{q} dup")
                continue
            hi, lo = (r1, r2) if r1.thr > r2.thr else (r2, r1)
            add("acc_ladder", game, hi.id, 1, lo.id, 0, f"{q}>{hi.thr} => >{lo.thr}")
        # cross-quantity dominance
        for q2, sc, fam in le_map.get(q, []):
            s2 = "game" if q2 in GAME_LEVEL else s
            for r1 in lst:
                for r2 in by.get((q2, s2), []):
                    # Q1 > t1 => Q1 >= floor(t1)+1 => Q2 >= sc*(floor(t1)+1) > t2 needed
                    if sc * (np.floor(r1.thr) + 1) > r2.thr:
                        add(fam, game, r1.id, 1, r2.id, 0, f"{q}>{r1.thr} => {q2}>{r2.thr}")
print("accumulation relations", len(rels) - n0)

# ----------------------------------------------------------------------------- non-sports within-event ladders
MONTHS = {mo: i for i, mo in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                         "september", "october", "november", "december"], 1)}
DATE_RE = re.compile(r"^(january|february|march|april|may|june|july|august|september|october|november|december)"
                     r"\s+(\d{1,2})(?:,?\s*(\d{4}))?$", re.I)
NUM_RE = re.compile(r"^(?:above|over|>|≥|at least|more than)?\s*[↑↓]?\s*\$?\s*([\d,]*\.?\d+)\s*([kmbt%]?)\b", re.I)
MULT = {"": 1, "k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12, "%": 1}


def parse_date(s, start):
    """Parse 'October 31' / 'June 30, 2027'. Without a year, take the first such date on or after the
    market's startDate (Gamma endDate is unreliable for this: e.g. a 'December 31' market with endDate Nov 1)."""
    mm = DATE_RE.match((s or "").strip())
    if not mm:
        return None
    mo, d, y = MONTHS[mm.group(1).lower()], int(mm.group(2)), mm.group(3)
    if y is None:
        y = start.year if pd.notna(start) else 2026
        try:
            cand = pd.Timestamp(year=int(y), month=mo, day=d, tz="UTC")
        except ValueError:
            return None
        # an open 'by <date>' market cannot have a deadline long past: roll forward past max(start, as-of - 3d)
        ref = max(start, ASOF - pd.Timedelta(days=3)) if pd.notna(start) else ASOF - pd.Timedelta(days=3)
        while cand < ref - pd.Timedelta(days=1):
            cand = cand.replace(year=cand.year + 1)
        return cand
    try:
        return pd.Timestamp(year=int(y), month=mo, day=d, tz="UTC")
    except ValueError:
        return None


def parse_num(s):
    s = (s or "").strip()
    mm = NUM_RE.match(s)
    if not mm or not mm.group(1).replace(",", "").replace(".", ""):
        return None
    try:
        v = float(mm.group(1).replace(",", ""))
    except ValueError:
        return None
    return v * MULT[mm.group(2).lower()]


MD_Q = (r"(?:january|february|march|april|may|june|july|august|september|october|november|december)"
        r"\s+\d{1,2}(?:,?\s*\d{4})?")
ns = m[m.sportsMarketType.isna() | m.event_title.str.contains(r"Win Total|Season|Regular Season|\+", regex=True)].copy()
n0 = len(rels)
skipped_titles = []
for eid, g in ns[(ns.negRisk == False) & (ns.outs.map(lambda o: o == ["Yes", "No"]))].groupby("event_id"):  # noqa: E712
    if len(g) < 2:
        continue
    title = (g.event_title.iloc[0] or "")
    tl = title.lower()
    gi = g.groupItemTitle.fillna("")
    # --- date ladders: cumulative "by/before" wording only
    def qdate(q, gtitle, st):
        ql = (q or "").lower()
        mm = re.search(r"before (\d{4})\b", ql)
        if mm:
            return pd.Timestamp(year=int(mm.group(1)) - 1, month=12, day=31, tz="UTC")
        mm = re.search(MD_Q, ql)
        if mm and re.search(r"\d{4}", mm.group(0)):
            return parse_date(mm.group(0), st)
        mm = re.search(r"\bin (\d{4})\??$", ql)
        if mm and not DATE_RE.match((gtitle or "").strip()):
            return pd.Timestamp(year=int(mm.group(1)), month=12, day=31, tz="UTC")
        return parse_date(gtitle, st)
    dates = [qdate(q, x, e) for q, x, e in zip(g.question, gi, g.start)]
    if sum(d is not None for d in dates) >= 2:
        if re.search(r"\bby\b|before|\bby\.\.\.|by…|by ___|by __", tl) and not re.search(r"\bon\b|\bin\b (?:january|february|march|april|may|june|july|august|september|october|november|december)", tl):
            rows = [(d, r) for d, r in zip(dates, g.itertuples()) if d is not None]
            for (d1, r1), (d2, r2) in itertools.combinations(rows, 2):
                if d1 == d2:
                    continue
                early, late = (r1, r2) if d1 < d2 else (r2, r1)
                add("lad_date", eid, early.id, 1, late.id, 0, f"{title}: {early.groupItemTitle} => {late.groupItemTitle}")
        else:
            skipped_titles.append(("date", title))
        continue
    # --- numeric threshold ladders
    nums = [parse_num(x) for x in gi]
    if sum(v is not None for v in nums) < 2:
        continue
    up = bool(re.search(r"above|over|\bhit\b|reach|more than|at least|high|\+|exceed|higher|greater|≥|or more", tl)) or gi.str.contains(r"\+|↑|Above|above").any()
    down = bool(re.search(r"below|under|less than|dip|low|fewer|<", tl)) or gi.str.contains(r"↓|Below|below").any()
    if re.search(r"between|range|exactly|how many .* (?:in|on)\b", tl) and not re.search(r"\+", " ".join(gi)):
        skipped_titles.append(("range", title))
        continue
    rows = [(v, r) for v, r in zip(nums, g.itertuples()) if v is not None]
    if gi.str.contains("↑").any() or gi.str.contains("↓").any():
        ups = [(v, r) for v, r in rows if "↑" in (r.groupItemTitle or "")]
        dns = [(v, r) for v, r in rows if "↓" in (r.groupItemTitle or "")]
        for (v1, r1), (v2, r2) in itertools.combinations(ups, 2):
            if v1 != v2:
                hi, lo = (r1, r2) if v1 > v2 else (r2, r1)
                add("lad_hit", eid, hi.id, 1, lo.id, 0, f"{title}: {hi.groupItemTitle} => {lo.groupItemTitle}")
        for (v1, r1), (v2, r2) in itertools.combinations(dns, 2):
            if v1 != v2:
                lo, hi = (r1, r2) if v1 < v2 else (r2, r1)
                add("lad_hit", eid, lo.id, 1, hi.id, 0, f"{title}: {lo.groupItemTitle} => {hi.groupItemTitle}")
        continue
    if up == down:
        skipped_titles.append(("dir?", title))
        continue
    for (v1, r1), (v2, r2) in itertools.combinations(rows, 2):
        if v1 == v2:
            continue
        hi, lo = (r1, r2) if v1 > v2 else (r2, r1)
        if up:  # P decreasing in K: (> hi) implies (> lo)
            add("lad_num", eid, hi.id, 1, lo.id, 0, f"{title}: {hi.groupItemTitle} => {lo.groupItemTitle}")
        else:   # below K: (< lo) implies (< hi)
            add("lad_num", eid, lo.id, 1, hi.id, 0, f"{title}: {lo.groupItemTitle} => {hi.groupItemTitle}")
print("non-sports ladder relations", len(rels) - n0, "skipped events", len(skipped_titles))

# ----------------------------------------------------------------------------- duplicates and cross-event date ladders
n0 = len(rels)
yn = m[m.outs.map(lambda o: o == ["Yes", "No"])].copy()
# keep signs: "-1°C" and "1°C" are different questions
yn["nq"] = yn.question.fillna("").str.lower().str.replace(r"[^a-z0-9à-ÿ+\-−.%$]+", " ", regex=True).str.strip()
MDX = r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}"


def NUMS(d):
    """Multiset of numbers and month-day strings in a rules text (dates, thresholds, deadlines)."""
    d = (d or "").lower()
    return sorted(re.findall(r"[-−+]?\d[\d,.]*", d) + re.findall(MDX, d))


# sports questions are not self-contained ("Player: 2+ goals"), so they only match inside one game
yn["dkey"] = yn.nq + np.where(yn.sportsMarketType.notna(), " @" + yn.event_slug.map(base_slug).fillna(""), "")
for nq, g in yn.groupby("dkey"):
    if len(g) < 2 or len(g) > 6:
        continue
    for r1, r2 in itertools.combinations(list(g.itertuples()), 2):
        if r1.conditionId == r2.conditionId:
            continue
        # same question text is not enough (weekly repeats, EPS thresholds, last season): require
        # end dates within 1 day and near-identical rules text; survivors still get manual review
        if pd.isna(r1.end) or pd.isna(r2.end) or abs(r1.end - r2.end) > pd.Timedelta(days=1):
            continue
        sim = difflib.SequenceMatcher(None, (r1.description or "")[:3000], (r2.description or "")[:3000]).ratio()
        if sim < 0.98 or NUMS(r1.description) != NUMS(r2.description):
            continue  # e.g. 'by October 23' vs 'by November 2' copies of one event are a ladder, not a duplicate
        add("dup", nq[:80], r1.id, 0, r2.id, 1, f"duplicate question, desc_sim={sim:.3f}")
        add("dup", nq[:80], r1.id, 1, r2.id, 0, f"duplicate question, desc_sim={sim:.3f}")
# earnings EPS ladders across events: <tkr>-quarterly-earnings-<gaap|nongaap>-eps-<mm-dd-yyyy>-<thr with pt>
EPS = re.compile(r"^(.+-quarterly-earnings-(?:non)?gaap-eps-\d{2}-\d{2}-\d{4})-(\d+pt\d+|\d+)(?:-\d+)?$")
eps = yn[yn.event_slug.fillna("").str.match(EPS)].copy()
eps["base"] = eps.event_slug.str.extract(EPS)[0]
eps["thr"] = eps.event_slug.str.extract(EPS)[1].str.replace("pt", ".").astype(float)
for base, g in eps.groupby("base"):
    for r1, r2 in itertools.combinations(list(g.itertuples()), 2):
        if r1.thr == r2.thr:
            continue
        hi, lo = (r1, r2) if r1.thr > r2.thr else (r2, r1)
        add("xeps", base, hi.id, 1, lo.id, 0, f"EPS beat {hi.thr} => beat {lo.thr}")
MD = r"(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:,?\s*\d{4})?"
yn["tmpl"] = yn.question.str.lower().str.replace(MD, "<D>", regex=True)
yn["is_by"] = yn.tmpl.str.contains(r"(?:by|before) <d>")
for tmpl, g in yn[yn.is_by & yn.tmpl.str.contains("<d>")].groupby("tmpl"):
    pass  # same template, same date = duplicate (handled above)
yn["tmpl_nodate"] = yn.tmpl.str.replace("<d>", "<D>")
by_t = yn[yn.is_by].copy()
by_t["d"] = [parse_date(re.search(MD, q.lower()).group(0) if re.search(MD, q.lower()) else "", e) for q, e in zip(by_t.question, by_t.start)]
by_t = by_t[by_t.d.notna()]
for tmpl, g in by_t.groupby("tmpl"):
    if g.event_id.nunique() < 2 or len(g) > 30:
        continue
    for r1, r2 in itertools.combinations(list(g.itertuples()), 2):
        if r1.event_id == r2.event_id or r1.d == r2.d:
            continue
        early, late = (r1, r2) if r1.d < r2.d else (r2, r1)
        add("xdate", tmpl[:80], early.id, 1, late.id, 0, f"{early.question} => {late.question}")
print("dup + xdate relations", len(rels) - n0)

# ----------------------------------------------------------------------------- write
R = pd.DataFrame(rels, columns=["family", "key", "ma", "oa", "mb", "ob", "note"]).drop_duplicates(["ma", "oa", "mb", "ob"])
del rels
R["oa"] = R.oa.astype("int8")
R["ob"] = R.ob.astype("int8")
for c in ("family", "key", "note"):
    R[c] = R[c].astype("category")
R.to_parquet(OUT, index=False)
print(OUT, len(R))
print(R.family.value_counts())
cols = ["id", "question", "conditionId", "clobTokenIds", "negRisk", "event_id", "event_slug", "fee_rate", "fee_exponent",
        "feeType", "feesEnabled", "endDate", "gameStartTime", "sportsMarketType", "orderMinSize",
        "orderPriceMinTickSize", "outcomes", "groupItemTitle"]
used = pd.unique(pd.concat([R.ma, R.mb]))
m[m.id.isin(used)][cols].to_parquet(ROOT / "data" / "derived" / f"la_relmarkets_{DATE}.parquet", index=False)
pd.Series(skipped_titles, dtype=object).to_frame().to_csv(ROOT / "data" / "derived" / f"la_skipped_events_{DATE}.csv", index=False)
