"""Combine both observation windows, attach the rule classification, apply the pre-registered criteria R1-R5.

Run from polymarket_research/:  python -m analyses.logical_arb.07_combine
Inputs : data/derived/la_opps_summary_2026-10-17_run1c.parquet (window 1, 15:23-16:15 UTC, 13 snapshots)
         data/derived/la_opps_summary_2026-10-17w2_w2.parquet  (window 2, ~21:36-22:40 UTC, 15 snapshots)
         data/derived/la_opps_2026-10-17*_{run1c,w2}.parquet    (per-snapshot rows)
Output : data/derived/la_final_relations_2026-10-17.parquet + printed tables

Rule class (R3): family default, overridden by the manual rule reads documented in
notes/strategies/logical_arb.md section 3. Expected resolution dates override Gamma endDate where the rules
name an earlier event date (e.g. Ballon d'Or ceremony 2026-10-26), because capital comes back at resolution.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "derived"
pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 60)

FAMILY_CLASS = {  # default R3 class by construction (same rules text / same data source), before manual review
    "lad_num": "TRUE", "lad_hit": "TRUE", "lad_date": "TRUE", "xeps": "TRUE", "dup": "TRUE",
    "cx_above_hit": "TRUE", "cx_above_dip": "TRUE", "cx_bkt_above": "TRUE", "cx_bkt_notab": "TRUE",
    "cx_bkt_hit": "TRUE", "cx_bkt_dip": "TRUE", "cx_hit_hit": "TRUE",
    "grid_soccer": "NEAR", "grid_other": "NEAR", "acc": "NEAR", "acc_ladder": "NEAR", "acc_near": "NEAR",
    "xdate": "NEAR", "fut_excl": "NEAR",
}
# manual overrides keyed by (substring of q_a, substring of q_b) -> (class, reason, expected resolution UTC date)
MANUAL = [
    ("Lionel Messi win the 2026 Ballon", "top 2 of the 2026 Ballon", "NEAR",
     "top-2 market resolves No if ceremony slips past 2026-11-09; winner market waits to 2026-12-31", "2026-10-27"),
    ("top 4 seed in the 2027 College Football", "Quarterfinals", "NEAR",
     "QF market resolves No if QF not played by 2027-01-13; byes for seeds 1-4 written into QF rules", None),
    ("top 4 seed in the 2027 College Football", "Make the 2026-27 CFB Playoffs", "NEAR",
     "seed market: no bracket by 2026-12-20 -> No; playoff market deadline differs", None),
    ("Presidential Election", "presidential nomination", "CORRELATED",
     "winner can come from another party's nomination or run independent", None),
    ("finish in the top 4 of the 2026-27 Serie A", "UEFA Champions League", "NEAR",
     "UEFA exclusion/licensing can deny a top-4 club its UCL place", None),
    ("Stanley Cup Champion", "Conference Champion", "TRUE", "Cup winner must win its conference final", None),
    ("not IPO by December 31", "not IPO by December 31", "TRUE",
     "identical rules text in two bracket events; separate UMA requests (oracle-consistency tail)", None),
]


def load(tag_sum, tag_rows):
    S = pd.read_parquet(D / tag_sum).reset_index()
    O = pd.read_parquet(D / tag_rows)
    return S, O


S1, O1 = load("la_opps_summary_2026-10-17_run1c.parquet", "la_opps_2026-10-17_run1c.parquet")
S2, O2 = load("la_opps_summary_2026-10-17w2_w2.parquet", "la_opps_2026-10-17w2_w2.parquet")
S1["window"], S2["window"] = 1, 2
S = pd.concat([S1, S2], ignore_index=True)


def classify(r):
    for qa, qb, cls, why, res in MANUAL:
        if (qa in (r.q_a or "") and qb in (r.q_b or "")) or (qa in (r.q_b or "") and qb in (r.q_a or "")):
            return cls, why, res
    return FAMILY_CLASS.get(r.family, "NEAR"), "family default", None


cl = S.apply(classify, axis=1, result_type="expand")
S["rule_class"], S["rule_note"], S["exp_resolution"] = cl[0], cl[1], cl[2]
asof = {1: pd.Timestamp("2026-10-17T16:00Z"), 2: pd.Timestamp("2026-10-17T22:00Z")}
S["lock_days_adj"] = [
    max((pd.Timestamp(e, tz="UTC") - asof[w]).total_seconds() / 86400, 0.25) if isinstance(e, str) else ld
    for e, w, ld in zip(S.exp_resolution, S.window, S.lock_days)]
S["ann_ret_pct"] = S.med_edge_pct / S.lock_days_adj * 365
S["R5_ok"] = S.med_edge_pct >= 0.5
S["R4_ann_ok"] = S.ann_ret_pct >= 10
S["dominance"] = S.rule_class.isin(["TRUE", "NEAR"])
both = set(S[S.window == 1].rel_id) & set(S[S.window == 2].rel_id)
S["in_both_windows"] = S.rel_id.isin(both)
S.to_parquet(D / "la_final_relations_2026-10-17.parquet", index=False)

for w in (1, 2):
    x = S[(S.window == w)]
    print(f"\n=== window {w}: distinct relations with cost<1 at >= min size: {len(x)}; persistent: {int(x.persistent.sum())}")
    print(x.groupby(["rule_class", "family"]).agg(
        n=("rel_id", "size"), persistent=("persistent", "sum"), R5_ok=("R5_ok", "sum"),
        R5_and_persist=("R5_ok", lambda s: int((s & x.loc[s.index, "persistent"]).sum())),
        med_edge=("med_edge_pct", "median"), sum_med_profit=("med_profit", "sum")).to_string())
P = S[S.persistent & S.dominance & (S.timing.isin(["pre_game", "no_game"]))]
print("\n=== persistent TRUE/NEAR, pre-game/no-game, passing R5 (edge >= 0.5%)")
cols = ["window", "rule_class", "family", "q_a", "out_a", "q_b", "out_b", "n_snaps", "med_shares", "med_profit",
        "med_edge_pct", "lock_days_adj", "ann_ret_pct", "in_both_windows"]
print(P[P.R5_ok].sort_values("med_profit", ascending=False)[cols].head(40).to_string())
for w in (1, 2):
    x = P[(P.window == w) & P.R5_ok]
    hrs = {1: 52 / 60, 2: None}[w]
    print(f"window {w}: R5-passing persistent TRUE/NEAR relations {len(x)}, TRUE {int((x.rule_class == 'TRUE').sum())}, "
          f"sum median depth-limited profit ${x.med_profit.sum():.2f} (overlapping legs -> upper bound), "
          f"TRUE only ${x[x.rule_class == 'TRUE'].med_profit.sum():.2f}; capital-weighted ann. return "
          f"{(x.ann_ret_pct * x.med_shares).sum() / max(x.med_shares.sum(), 1e-9):.1f}%")

# ----------------------------------------------------------------------------- k-of-n count sets (06_count_sets)
# expected resolution (capital back): Oscars nominations announced 2027-01-21 (market rules); CFP title game
# 2027-01-25 (CFP); NBA/NHL conference finals set ~2027-05-20; LaLiga/EPL/Serie A season end ~2027-05-30;
# NFL divisional/championship 2027-01-17/-24; NFL postseason field 2027-01-04; UCL/UEL/UECL league phase 2027-01-28.
EXP_RES = {"Oscars": "2027-01-21", "Ballon": "2026-10-27", "801515": "2027-01-26", "948140": "2026-12-07", "956300": "2027-05-20",
           "956299": "2027-05-20", "956297": "2027-05-05", "956298": "2027-05-05", "904907": "2027-05-30",
           "904908": "2027-05-30", "904911": "2027-05-30", "448179": "2027-01-05", "956266": "2027-01-12",
           "956267": "2027-01-12", "956268": "2027-01-19", "956269": "2027-01-19", "681898": "2027-04-20",
           "681890": "2027-04-13", "1024891": "2027-01-29", "1024892": "2027-01-29", "1024893": "2027-01-29",
           "1024920": "2027-01-29", "1024921": "2027-01-29", "1024922": "2027-01-29"}
CLS = {"904908": "NEAR (administrative relegation without reprieve could make 4)",
       "811116": "NEAR (no tie-break clause: a tie at 5th could make 6 YES)",
       "811117": "NEAR (no tie-break clause: a tie at 3rd could make 4 YES)",
       "1198837": "NEAR (duos counted, k=7)"}
for f, w, t0 in (("la_cnt_opps_w1.parquet", 1, "2026-10-17T16:00Z"), ("la_cnt_opps_2026-10-17w2.parquet", 2, "2026-10-17T22:00Z"),
                 ("la_cnt_opps_bdo.parquet", 3, "2026-10-17T22:20Z")):
    if not (D / f).exists():
        continue
    C = pd.read_parquet(D / f)
    C["ok"] = (C.profit > 0) & (C.shares >= 5)
    C["si"] = C.snap_utc.map({u: i for i, u in enumerate(sorted(C.snap_utc.unique()))})
    rows = []
    for (eid, side), g in C.groupby(["event_id", "side"]):
        pos = sorted(g[g.ok].si)
        run = best = 0
        prev = None
        for x in pos:
            run = run + 1 if prev is not None and x == prev + 1 else 1
            best, prev = max(best, run), x
        key = "Oscars" if g.note.iloc[0].startswith("Oscars") else ("Ballon" if g.note.iloc[0].startswith("Ballon") else eid)
        res = pd.Timestamp(EXP_RES.get(key, str(g.end.dropna().max())[:10] if g.end.notna().any() else "2027-06-30"), tz="UTC")
        lock = (res - pd.Timestamp(t0)).total_seconds() / 86400
        gp = g[g.ok]
        edge = (gp.profit / gp.cost).median() * 100 if len(gp) else np.nan
        rows.append({"window": w, "event_id": eid, "note": g.note.iloc[0][:60], "side": side, "snaps": g.si.nunique(),
                     "n_pos": len(pos), "max_run": best, "med_profit_pos": gp.profit.median() if len(gp) else 0.0,
                     "max_profit": g.profit.max(), "med_capital_pos": gp.cost.median() if len(gp) else 0.0,
                     "med_edge_pct": edge, "lock_days": lock, "ann_ret_pct": edge / lock * 365 if len(gp) else np.nan,
                     "min_gap": (g.top_set_cost - g.payoff_per_set).min(),
                     "rule_class": CLS.get(eid, "NEAR (cancellation)" if side == "ALL_YES" else "TRUE (at most k YES)")})
    T = pd.DataFrame(rows)
    T.to_parquet(D / f"la_cnt_summary_w{w}.parquet", index=False)
    print(f"\n=== k-of-n sets, window {w}: sets x sides evaluated {len(T)}; with any positive snapshot {int((T.n_pos > 0).sum())}")
    print(T[T.n_pos > 0].sort_values("med_profit_pos", ascending=False).to_string(index=False))
