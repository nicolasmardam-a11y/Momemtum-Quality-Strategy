"""Summarise a smoke-test alerts DB: detection lags, alerts, duplicates, health events.

Usage: python analyze_active.py <db> <ndjson> <stdout1,stdout2,...> [run windows as start/end epoch pairs]
Lag = first_seen_at (local, NTP-synced clock) - ts (block timestamp, integer seconds, floored).
Fills executed while the monitor was stopped are reported separately (outage backlog).
"""
from __future__ import annotations

import collections
import json
import sqlite3
import statistics
import sys


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def dist(xs: list[float]) -> str:
    if not xs:
        return "n=0"
    return (f"n={len(xs)} min={min(xs):.1f} p10={pct(xs, .1):.1f} p50={pct(xs, .5):.1f} mean={statistics.mean(xs):.1f} "
            f"p90={pct(xs, .9):.1f} p99={pct(xs, .99):.1f} max={max(xs):.1f}")


def main() -> None:
    db, ndjson, stdouts = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
    runs = [tuple(map(float, w.split("/"))) for w in sys.argv[4:]]
    c = sqlite3.connect(db)
    q = lambda s, *a: c.execute(s, a).fetchall()
    lab = dict(q("select address, label from wallets"))

    def running(t: float) -> bool:
        return any(a <= t <= b for a, b in runs) if runs else True

    live = q("select wallet, activity_type, ts, first_seen_at from fills where poll_mode='live'")
    print(f"fills total={q('select count(*) from fills')[0][0]} live={len(live)} "
          f"bootstrap={q('select count(*) from fills where poll_mode=?', 'bootstrap')[0][0]}")
    print("live fills by wallet/type:", collections.Counter((lab[w], t) for w, t, *_ in live))
    online = [f - ts for w, t, ts, f in live if running(ts)]
    backlog = [f - ts for w, t, ts, f in live if not running(ts)]
    print("DETECTION LAG, fills executed while the monitor ran:", dist(online))
    for w in lab:
        print(f"   {lab[w]}:", dist([f - ts for ww, t, ts, f in live if ww == w and running(ts)]))
    print("DETECTION LAG, fills executed while stopped (outage backlog):", dist(backlog))

    print("\nalerts by kind/label/status:", q("select kind, label, status, count(*) from alerts group by 1,2,3"))
    print("suppressed reasons:", q("select substr(suppressed_reason,1,70), count(*) from alerts where status='suppressed' group by 1"))
    bet_alerts = q("select a.alert_id, a.created_at, b.first_ts, b.last_ts, a.payload_json from alerts a join bets b using(bet_id) "
                   "where a.kind='BET' and a.status!='suppressed'")
    dl = [json.loads(p).get("detection_lag_s") for *_, p in bet_alerts]
    print("ALERT detection_lag_s (newest fill seen - its block ts):", dist([x for x in dl if x is not None]))
    pl = [json.loads(p) for *_, p in bet_alerts]
    print("ALERT built - newest fill block ts (bet as alerted):", dist([p["alert_built_at"] - p["bet"]["last_ts"] for p in pl]))
    print("ALERT built - detection of newest fill (enrichment time):", dist([p["alert_built_at"] - p["detected_at"] for p in pl]))

    # duplicates
    nat = q("select count(*) from (select count(*) n from fills group by wallet, tx_hash, token_id, side, size, price, ts, "
            "activity_type having n > 1)")[0][0]
    multi_bet = q("select count(*) from (select bet_id, count(*) n from alerts where kind='BET' group by bet_id having n > 1)")[0][0]
    multi_fill_bet = q("select count(*) from fills where bet_id is null")[0][0]
    deliv = q("select channel, status, possible_duplicate, count(*) from deliveries group by 1,2,3")
    print(f"\nDUPLICATES: natural-key fill groups with >1 row={nat}; bets with >1 alert={multi_bet}; unassigned fills={multi_fill_bet}")
    print("deliveries:", deliv)
    ids = collections.Counter()
    for line in open(ndjson):
        line = line.strip()
        if line:
            ids[json.loads(line).get("alert_id")] += 1
    print(f"file channel: lines={sum(ids.values())} distinct alert_ids={len(ids)} repeated={sum(1 for v in ids.values() if v > 1)}")
    heads = collections.Counter()
    for path in stdouts:
        for line in open(path):
            if line.startswith("[") and "]" in line[:40]:
                heads[line.split("]")[0] + "]"] += 1
    print("console headers:", dict(heads))
    print("\nhealth events:")
    for r in q("select scope, kind, error_class, severity, occurrences, substr(detail,1,200), resolved_at is not null from health_events"):
        print("  ", r)
    print("poll_state:", [(lab[w], wm, ok, bad) for w, wm, ok, bad in
                          q("select wallet, watermark_ts, polls_ok, polls_failed from poll_state")])


if __name__ == "__main__":
    main()
