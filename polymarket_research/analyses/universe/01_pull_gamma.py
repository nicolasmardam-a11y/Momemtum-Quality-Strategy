"""Pull every CLOSED Gamma market (and its parent events) with endDate 2024-01-01..2026-10-15.

Run from polymarket_research/ (resumable; finished windows are skipped, pages are cached):
    PMR_RATE_SCALE=2 python -m analyses.universe.01_pull_gamma markets
    PMR_RATE_SCALE=2 python -m analyses.universe.01_pull_gamma events
    PMR_RATE_SCALE=2 python -m analyses.universe.01_pull_gamma events_missing
    PMR_RATE_SCALE=2 python analyses/universe/01_pull_gamma.py month_split markets 2026-08   (weekly windows; used for
        2026-08 after a deterministic Cloudflare 403 on one monthly keyset cursor)

Source: GET https://gamma-api.polymarket.com/markets/keyset?closed=true&include_tag=true
        &end_date_min=<window start>&end_date_max=<window end>&limit=100 (cursor: after_cursor)
        GET /events/keyset?closed=true&include_markets=false&end_date_min/max (same windows, wider range)
        GET /events/keyset?id=..&id=..  for event ids referenced by markets but not found by date window.
Gamma returns only open markets unless closed=true (CONTEXT.md). Every raw page is stored by
pmr.http under data/raw/gamma/cache/ (cache=True: resolved markets are treated as immutable history).
Slim per-window chunks go to data/raw/gamma_universe/{markets,events}/<YYYY-MM>.ndjson.gz (+ .meta.json).
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

OUT = ROOT / "data" / "raw" / "gamma_universe"
DROP = {"description", "image", "icon", "events", "tags", "clobRewards", "series", "markets", "eventMetadata",
        "imageOptimized", "iconOptimized", "featuredImage"}


def month_windows(start: str, end: str) -> list[tuple[str, str, str]]:
    """[(label, min_iso, max_iso)] calendar-month windows; the final window is clipped at `end` (exclusive)."""
    y, m = int(start[:4]), int(start[5:7])
    out = []
    while True:
        lo = f"{y:04d}-{m:02d}-01T00:00:00Z"
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        hi = f"{ny:04d}-{nm:02d}-01T00:00:00Z"
        if lo >= end:
            break
        out.append((f"{y:04d}-{m:02d}", lo, min(hi, end)))
        y, m = ny, nm
    return out


def slim_market(m: dict) -> dict:
    d = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in m.items() if k not in DROP}
    d["tags_json"] = json.dumps([{"id": t.get("id"), "slug": t.get("slug"), "label": t.get("label")}
                                 for t in (m.get("tags") or [])])
    d["clobRewards_json"] = json.dumps(m.get("clobRewards") or [])
    evs = []
    for e in m.get("events") or []:
        ev = {k: v for k, v in e.items() if k not in DROP}
        ev["series_slugs"] = [s.get("slug") for s in (e.get("series") or [])]
        evs.append(ev)
    d["events_json"] = json.dumps(evs)
    d["n_events"] = len(evs)
    return d


def slim_event(e: dict) -> dict:
    d = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in e.items() if k not in DROP}
    d["tags_json"] = json.dumps([{"id": t.get("id"), "slug": t.get("slug"), "label": t.get("label")}
                                 for t in (e.get("tags") or [])])
    d["series_json"] = json.dumps([{"id": s.get("id"), "slug": s.get("slug"), "title": s.get("title"),
                                    "recurrence": s.get("recurrence"), "seriesType": s.get("seriesType")}
                                   for s in (e.get("series") or [])])
    return d


def write_chunk(path: Path, meta: dict, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as f:
        json.dump({"meta": meta, "rows": rows}, f)
    tmp.replace(path)


def pull_window(kind: str, label: str, lo: str, hi: str) -> tuple[str, int, int]:
    """Stream one end-date window to <label>.ndjson.gz (one slim JSON row per line) + <label>.meta.json."""
    path = OUT / kind / f"{label}.ndjson.gz"
    if path.exists():
        return label, -1, -1
    params = {"closed": "true", "limit": 100, "end_date_min": lo, "end_date_max": hi}
    if kind == "markets":
        params["include_tag"] = "true"
    else:
        params["include_markets"] = "false"
    t0 = time.time()
    n, pages = 0, 0
    p = dict(params)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", compresslevel=3) as f:
        while True:
            j = request_json(f"{api.GAMMA}/{kind}/keyset", p, source="gamma", cache=True)
            batch = j.get(kind) or []
            for x in batch:
                f.write(json.dumps(slim_market(x) if kind == "markets" else slim_event(x)) + "\n")
            n += len(batch)
            pages += 1
            cur = j.get("next_cursor")
            del j
            if not cur or not batch:
                break
            p["after_cursor"] = cur
            if pages % 200 == 0:
                print(f"  {kind} {label}: {pages} pages, {n} rows, {time.time() - t0:.0f}s", flush=True)
    meta = {"kind": kind, "window": [lo, hi], "params": params, "pages": pages, "n": n,
            "built_at_utc": datetime.now(timezone.utc).isoformat(), "endpoint": f"{api.GAMMA}/{kind}/keyset"}
    (OUT / kind / f"{label}.meta.json").write_text(json.dumps(meta))
    tmp.replace(path)
    return label, pages, n


def read_rows(path: Path):
    with gzip.open(path, "rt") as f:
        for line in f:
            yield json.loads(line)


def run(kind: str, start: str, end: str, workers: int = int(__import__("os").environ.get("PULL_WORKERS", "6"))) -> None:
    wins = month_windows(start, end)
    # biggest (most recent) windows first so the long tail overlaps with small ones
    wins = sorted(wins, key=lambda w: w[0], reverse=True)
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(pull_window_retry, kind, *w): w for w in wins}
        for f in as_completed(futs):
            try:
                label, pages, n = f.result()
                print(f"{kind} {label}: pages={pages} rows={n}", flush=True)
            except Exception as e:  # keep other windows going; retry as weekly sub-windows
                label, lo, hi = futs[f]
                print(f"FAILED {kind} {label}: {e} -> retrying as weekly sub-windows", flush=True)
                try:
                    pull_split(kind, label, lo, hi)
                except Exception as e2:
                    print(f"FAILED {kind} {label} (weekly split): {e2}", flush=True)


def pull_window_retry(kind: str, label: str, lo: str, hi: str, attempts: int = 5):
    """pmr.http raises at once on 4xx; a transient Cloudflare 403 (HTML) was seen on 2026-10-17 while
    several agents shared the IP. Retry with back-off; cached pages make each retry cheap. HTTP 500 on a
    whole month (a server-side query failure) is not retried here but split into weeks by the caller."""
    for a in range(attempts):
        try:
            return pull_window(kind, label, lo, hi)
        except RuntimeError as e:
            if "HTTP 500" in str(e) or a == attempts - 1:
                raise
            print(f"  retry {kind} {label} after error: {str(e)[:120]}", flush=True)
            time.sleep(30 * 2 ** a)


def pull_split(kind: str, label: str, lo: str, hi: str, days: int = 7) -> None:
    """Gamma /events/keyset returned HTTP 500 for a full-month window (2026-09, reproducible on 2026-10-17)
    while week windows worked, so a failed month is re-pulled as consecutive sub-windows labelled
    <YYYY-MM>w<k>. Overlapping boundary rows are removed later by id de-duplication."""
    a = datetime.fromisoformat(lo.replace("Z", "+00:00"))
    b = datetime.fromisoformat(hi.replace("Z", "+00:00"))
    from datetime import timedelta
    k = 0
    while a < b:
        c = min(a + timedelta(days=days), b)
        sub = f"{label}w{k}"
        r = pull_window_retry(kind, sub, a.strftime("%Y-%m-%dT%H:%M:%SZ"), c.strftime("%Y-%m-%dT%H:%M:%SZ"))
        print(f"{kind} {sub}: pages={r[1]} rows={r[2]}", flush=True)
        a, k = c, k + 1


def events_missing(batch: int = 100, workers: int = 4) -> None:
    """Fetch parent events referenced by markets but absent from the event date-window pull.

    Referenced ids come from the stage-A parts (column event_ids_all = every event embedded in each
    market). GET /events/keyset?id=..&id=.. (repeated id params, <=100 per request) was verified on
    2026-10-17 to return closed events by id; a parent event can still be open while child markets
    closed, so ids not found with closed=true are re-queried with closed=false.
    """
    import pyarrow.parquet as pq
    have = set()
    for p in (OUT / "events").glob("*.ndjson.gz"):
        have |= {str(r["id"]) for r in read_rows(p)}
    want = set()
    for p in sorted((OUT / "parts").glob("*.parquet")):
        for ids in pq.read_table(p, columns=["event_ids_all"])["event_ids_all"].to_pylist():
            want.update(ids or [])
    miss = sorted(want - have, key=int)
    print(f"events referenced={len(want)} have={len(have)} missing={len(miss)}", flush=True)

    def fetch(ids: list[str], closed: str) -> list[dict]:
        j = request_json(f"{api.GAMMA}/events/keyset",
                         {"id": ids, "closed": closed, "include_markets": "false", "limit": 100},
                         source="gamma", cache=True)
        return [slim_event(x) for x in j.get("events") or []]

    rows: list[dict] = []
    for closed in ("true", "false"):
        got = {str(r["id"]) for r in rows}
        todo = [i for i in miss if i not in got]
        chunks = [todo[i:i + batch] for i in range(0, len(todo), batch)]
        with ThreadPoolExecutor(workers) as ex:
            for k, res in enumerate(ex.map(lambda c: fetch(c, closed), chunks)):
                rows += res
                if k % 200 == 0:
                    print(f"  closed={closed} batch {k}/{len(chunks)}: rows={len(rows)}", flush=True)
    meta = {"kind": "events_missing", "n_requested": len(miss), "n": len(rows),
            "endpoint": f"{api.GAMMA}/events/keyset?id=..", "built_at_utc": datetime.now(timezone.utc).isoformat()}
    write_chunk(OUT / "events_missing_by_id.json.gz", meta, rows)
    print(f"missing fetched rows={len(rows)} of {len(miss)}", flush=True)


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "markets":
        run("markets", "2024-01-01", "2026-10-16T00:00:00Z")
    elif what == "events":
        # wider window: a parent event's endDate can differ from its markets' endDates
        run("events", "2023-07-01", "2026-10-18T00:00:00Z")
    elif what == "events_missing":
        events_missing()


def pull_week_or_days(kind: str, sub: str, a, b) -> None:
    from datetime import timedelta
    try:
        r = pull_window_retry(kind, sub, a.strftime("%Y-%m-%dT%H:%M:%SZ"), b.strftime("%Y-%m-%dT%H:%M:%SZ"), attempts=2)
        print(f"{kind} {sub}: pages={r[1]} rows={r[2]}", flush=True)
    except RuntimeError as e:
        print(f"FAILED {kind} {sub}: {str(e)[:150]} -> daily", flush=True)
        (OUT / kind / f"{sub}.ndjson.tmp").unlink(missing_ok=True)
        d, j = a, 0
        while d < b:
            e2 = min(d + timedelta(days=1), b)
            r = pull_window_retry(kind, f"{sub}d{j}", d.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                  e2.strftime("%Y-%m-%dT%H:%M:%SZ"), attempts=2)
            print(f"{kind} {sub}d{j}: pages={r[1]} rows={r[2]}", flush=True)
            d, j = e2, j + 1


def pull_month_split(kind: str, label: str, workers: int = 4) -> None:
    """Pull one month as weekly sub-windows (in parallel), falling back to daily sub-windows for a failing week.

    Used for markets 2026-08: the monthly keyset chain reached a cursor that Cloudflare answers with HTTP 403
    every time (reproduced 2026-10-17 ~21:30 UTC with and without include_tag), i.e. a deterministic block on
    that cursor string, not rate limiting. Sub-windows produce different cursor chains. Weekly windows are
    [d, d+7d) from the 1st; the last one is clipped at the month end."""
    from datetime import timedelta
    lo = datetime.fromisoformat(f"{label}-01T00:00:00+00:00")
    hi = (lo + timedelta(days=32)).replace(day=1)
    wins, a, k = [], lo, 0
    while a < hi:
        b = min(a + timedelta(days=7), hi)
        wins.append((f"{label}w{k}", a, b))
        a, k = b, k + 1
    with ThreadPoolExecutor(workers) as ex:
        for f in [ex.submit(pull_week_or_days, kind, *w) for w in wins]:
            f.result()


if __name__ == "__main__" and sys.argv[1] == "month_split":
    pull_month_split(sys.argv[2], sys.argv[3])
