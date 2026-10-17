"""Pull every CLOSED Gamma market (and its parent events) with endDate 2024-01-01..2026-10-15.

Run from polymarket_research/ (resumable; finished windows are skipped, pages are cached):
    PMR_RATE_SCALE=2 python -m analyses.universe.01_pull_gamma markets
    PMR_RATE_SCALE=2 python -m analyses.universe.01_pull_gamma events
    PMR_RATE_SCALE=2 python -m analyses.universe.01_pull_gamma events_missing

Source: GET https://gamma-api.polymarket.com/markets/keyset?closed=true&include_tag=true
        &end_date_min=<window start>&end_date_max=<window end>&limit=100 (cursor: after_cursor)
        GET /events/keyset?closed=true&include_markets=false&end_date_min/max (same windows, wider range)
        GET /events/keyset?id=..&id=..  for event ids referenced by markets but not found by date window.
Gamma returns only open markets unless closed=true (CONTEXT.md). Every raw page is stored by
pmr.http under data/raw/gamma/cache/ (cache=True: resolved markets are treated as immutable history).
Slim per-window chunks go to data/raw/gamma_universe/{markets,events}/<YYYY-MM>.json.gz.
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
    path = OUT / kind / f"{label}.json.gz"
    if path.exists():
        return label, -1, -1
    params = {"closed": "true", "limit": 100, "end_date_min": lo, "end_date_max": hi}
    if kind == "markets":
        params["include_tag"] = "true"
    else:
        params["include_markets"] = "false"
    t0 = time.time()
    rows, pages = [], 0
    p = dict(params)
    while True:
        j = request_json(f"{api.GAMMA}/{kind}/keyset", p, source="gamma", cache=True)
        batch = j.get(kind) or []
        rows += [slim_market(x) if kind == "markets" else slim_event(x) for x in batch]
        pages += 1
        cur = j.get("next_cursor")
        if not cur or not batch:
            break
        p["after_cursor"] = cur
        if pages % 100 == 0:
            print(f"  {kind} {label}: {pages} pages, {len(rows)} rows, {time.time() - t0:.0f}s", flush=True)
    meta = {"kind": kind, "window": [lo, hi], "params": params, "pages": pages, "n": len(rows),
            "built_at_utc": datetime.now(timezone.utc).isoformat(), "endpoint": f"{api.GAMMA}/{kind}/keyset"}
    write_chunk(path, meta, rows)
    return label, pages, len(rows)


def run(kind: str, start: str, end: str, workers: int = 6) -> None:
    wins = month_windows(start, end)
    # biggest (most recent) windows first so the long tail overlaps with small ones
    wins = sorted(wins, key=lambda w: w[0], reverse=True)
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(pull_window, kind, *w): w for w in wins}
        for f in as_completed(futs):
            try:
                label, pages, n = f.result()
                print(f"{kind} {label}: pages={pages} rows={n}", flush=True)
            except Exception as e:  # keep other windows going; rerun picks up the failed one
                print(f"FAILED {kind} {futs[f][0]}: {e}", flush=True)


def events_missing() -> None:
    """Fetch parent events referenced by markets but absent from the event date-window pull."""
    have = set()
    for p in (OUT / "events").glob("*.json.gz"):
        with gzip.open(p, "rt") as f:
            have |= {str(r["id"]) for r in json.load(f)["rows"]}
    want = set()
    for p in (OUT / "markets").glob("*.json.gz"):
        with gzip.open(p, "rt") as f:
            for r in json.load(f)["rows"]:
                for e in json.loads(r.get("events_json") or "[]"):
                    want.add(str(e["id"]))
    miss = sorted(want - have, key=int)
    print(f"events referenced={len(want)} have={len(have)} missing={len(miss)}", flush=True)
    rows = []
    for i in range(0, len(miss), 50):
        ids = miss[i:i + 50]
        for closed in ("true", "false"):  # a parent event can still be open while some child markets closed
            j = request_json(f"{api.GAMMA}/events/keyset",
                             {"id": ids, "closed": closed, "include_markets": "false", "limit": 100},
                             source="gamma", cache=True)
            rows += [slim_event(x) for x in j.get("events") or []]
        if (i // 50) % 20 == 0:
            print(f"  missing batch {i // 50}: rows={len(rows)}", flush=True)
    meta = {"kind": "events_missing", "n_requested": len(miss), "n": len(rows),
            "built_at_utc": datetime.now(timezone.utc).isoformat()}
    write_chunk(OUT / "events" / "_missing_by_id.json.gz", meta, rows)
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
