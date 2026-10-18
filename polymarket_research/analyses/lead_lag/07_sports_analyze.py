"""Sports mini forward test analysis (pre-registered in notes/strategies/lead_lag.md section 0.4).

Inputs: sports_<tag>_{markets.json,espn.parquet,tob.parquet} and raw sportsws frames.
Run: python -m analyses.lead_lag.07_sports_analyze S1 -> data/derived/lead_lag/sports_<tag>_events.parquet, sports_<tag>_summary.json
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from glob import glob

import numpy as np
import pandas as pd

TAG = sys.argv[1] if len(sys.argv) > 1 else "S1"
D = "data/derived/lead_lag/"


def norm(s):
    s = re.sub(r"\(.*?\)", "", (s or "").lower())
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


def main():
    mk = json.load(open(f"{D}sports_{TAG}_markets.json"))
    es = pd.read_parquet(f"{D}sports_{TAG}_espn.parquet").sort_values("recv")
    tob = pd.read_parquet(f"{D}sports_{TAG}_tob.parquet").sort_values("recv")
    tob = tob[tob.bid.notna() & tob.ask.notna()]
    # map (ESPN game id, team displayName) -> Polymarket token of that team's moneyline
    team_tok, fee_of, delay_of = {}, {}, {}
    games = es.drop_duplicates("id")
    for g in games.itertuples():
        for team in (g.team0, g.team1):
            nt = norm(team)
            other = norm(g.team1 if team == g.team0 else g.team0)
            for m in mk:
                outs = [norm(o) for o in m["outcomes"]]
                if len(outs) != 2:
                    continue
                hit = [i for i, o in enumerate(outs) if o and (nt.startswith(o) or o in nt)]
                hit_o = [i for i, o in enumerate(outs) if o and (other.startswith(o) or o in other)]
                if len(hit) == 1 and len(hit_o) == 1 and hit[0] != hit_o[0]:
                    team_tok[(g.id, team)] = m["tokens"][hit[0]]
                    fee_of[m["tokens"][hit[0]]] = float((m.get("fee") or {}).get("rate") or 0.05)
                    delay_of[m["tokens"][hit[0]]] = m.get("secondsDelay")
    # scoring events: first ESPN poll where a team's score rises
    ev = []
    for gid, g in es.groupby("id"):
        g = g.sort_values("recv")
        prev = None
        for r in g.itertuples():
            cur = {r.team0: int(r.score0 or 0), r.team1: int(r.score1 or 0)}
            if prev is not None and r.state == "in":
                for team, sc in cur.items():
                    if sc > prev.get(team, sc):
                        ev.append({"id": gid, "league": r.league, "name": r.name, "team": team, "pts": sc - prev[team], "tE": r.recv,
                                   "detail": r.detail})
            prev = cur
    E = pd.DataFrame(ev)
    rows = []
    for e in E.itertuples():
        tok = team_tok.get((e.id, e.team))
        if tok is None:
            continue
        q = tob[tob.asset == tok]
        if q.empty:
            continue
        qt, qm, qs = q.recv.values, ((q.bid + q.ask) / 2).values, (q.ask - q.bid).values

        def at(t):
            i = np.searchsorted(qt, t, side="right") - 1
            return (qm[i], qs[i]) if i >= 0 else (np.nan, np.nan)
        m60, _ = at(e.tE - 60)
        m1, s1 = at(e.tE - 1)
        m30, _ = at(e.tE + 30)
        tot = m30 - m60
        rows.append({**e._asdict(), "token": tok, "mid_m60": m60, "mid_m1": m1, "mid_p30": m30, "spread_m1": s1,
                     "pre_share": (m1 - m60) / tot if abs(tot) >= 0.005 else np.nan, "post_move": m30 - m1,
                     "hurdle": fee_of[tok] * m1 * (1 - m1) + s1 / 2 if not np.isnan(m1) else np.nan, "secondsDelay": delay_of.get(tok)})
    R = pd.DataFrame(rows)
    R.to_parquet(f"{D}sports_{TAG}_events.parquet")
    summ = {"tag": TAG, "games_espn": int(games.id.nunique()), "games_in_play": int(es[es.state == "in"].id.nunique()),
            "matched_team_tokens": len(team_tok), "scoring_events": int(len(E)), "scoring_events_matched": int(len(R))}
    if len(R):
        summ.update({"median_pre_share": float(R.pre_share.median()), "n_pre_share": int(R.pre_share.notna().sum()),
                     "median_abs_post_move": float(R.post_move.abs().median()), "median_hurdle": float(R.hurdle.median()),
                     "share_post_move_gt_hurdle": float((R.post_move > R.hurdle).mean()),
                     "median_move_m60_to_p30": float((R.mid_p30 - R.mid_m60).median()),
                     "by_league": R.groupby("league").agg(n=("pre_share", "size"), pre=("pre_share", "median"), post=("post_move", "median")).round(3).to_dict("index")})
    # Polymarket sports WS vs ESPN: first frame showing the new score for the same game
    frames = []
    for f in glob(f"data/raw/lead_lag_live/*/sportsws_{TAG}.tsv.gz"):
        with gzip.open(f, "rt") as fh:
            for ln in fh:
                t, raw = ln.split("\t", 1)
                try:
                    d = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                for x in (d if isinstance(d, list) else [d]):
                    if isinstance(x, dict) and x.get("score") is not None:
                        frames.append({"recv": float(t), "home": x.get("homeTeam"), "away": x.get("awayTeam"), "score": str(x.get("score")),
                                       "league": x.get("leagueAbbreviation"), "status": x.get("status")})
    W = pd.DataFrame(frames)
    summ["sportsws_frames_with_score"] = int(len(W))
    if len(W) and len(E):
        W = W.sort_values("recv")
        W["chg"] = W.groupby(["home", "away"]).score.transform(lambda s: s != s.shift())
        Wc = W[W.chg]
        lags = []
        for e in E.itertuples():
            nt = norm(e.team)
            cand = Wc[(Wc.recv > e.tE - 180) & (Wc.recv < e.tE + 180)]
            cand = cand[cand.apply(lambda r: any(norm(z) and (norm(z) in nt or nt.startswith(norm(z))) for z in (r.home, r.away)), axis=1)]
            if len(cand):
                lags.append(float(e.tE - cand.recv.iloc[np.argmin(np.abs(cand.recv.values - e.tE))]))
        summ["espn_minus_pm_sportsws_s"] = {"n": len(lags), "median": float(np.median(lags)) if lags else None,
                                             "q25_q75": [float(np.percentile(lags, 25)), float(np.percentile(lags, 75))] if lags else None}
    json.dump(summ, open(f"{D}sports_{TAG}_summary.json", "w"), indent=1, default=str)
    print(json.dumps(summ, indent=1, default=str))


if __name__ == "__main__":
    main()
