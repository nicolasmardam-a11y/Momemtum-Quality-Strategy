"""Shared helpers for the stage-3 2026 holdout (Data API v2).

Lean fetcher: uses pmr.http's per-host throttle and session, but stores only slim parsed rows (parquet) plus a
provenance log per request (URL, params, UTC fetch time, HTTP status, row count, sha1 of the raw body), instead
of the full gzipped body. Reason: disk (about 9 GB free, stage budget 1.5 GB); a full 1,000-row /v2/trades page is
about 56 kB gzipped because every row repeats title, icon, slug and profile fields. Logged as a deviation from the
pmr raw-storage convention in the stage-3 note.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import http as H  # noqa: E402

V2 = ROOT / "data" / "derived" / "pit_wallets" / "v2"
V2.mkdir(parents=True, exist_ok=True)
DATA = "https://data-api.polymarket.com"
PROV = V2 / "provenance_log.tsv"
_plock = threading.Lock()

T_TRAIL0 = 1748736000   # 2025-06-01T00:00:00Z
T_D = 1780272000        # 2026-06-01T00:00:00Z
T_EVAL1 = 1790812800    # 2026-10-01T00:00:00Z
T_RESCUT = 1792022400   # 2026-10-15T00:00:00Z


def _prov(url: str, params: dict, status: int, n: int, sha: str, ms: float) -> None:
    line = "\t".join([datetime.now(timezone.utc).isoformat(), url, json.dumps(params, sort_keys=True), str(status),
                      str(n), sha, f"{ms:.0f}"])
    with _plock:
        new = not PROV.exists()
        with open(PROV, "a") as f:
            if new:
                f.write("fetched_at_utc\turl\tparams\tstatus\tn_rows\tsha1_body\telapsed_ms\n")
            f.write(line + "\n")


def get(path: str, params: dict, retries: int = 8) -> dict:
    url = f"{DATA}{path}"
    host = "data-api.polymarket.com"
    err = None
    for attempt in range(retries):
        H._throttle(host)
        t0 = time.monotonic()
        try:
            r = H._session.get(url, params=params, timeout=60)
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(min(60, 2 ** attempt))
            continue
        if r.status_code in H._RETRY_STATUS:
            err = RuntimeError(f"HTTP {r.status_code} {r.text[:200]}")
            ra = r.headers.get("Retry-After")
            time.sleep(float(ra) if ra and ra.replace('.', '', 1).isdigit() else min(60, 2 ** attempt))
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code} {url} {params} {r.text[:300]}")
        body = r.content
        j = json.loads(body)
        rows = j.get("data") or []
        _prov(url, params, r.status_code, len(rows) if isinstance(rows, list) else 1,
              hashlib.sha1(body).hexdigest(), (time.monotonic() - t0) * 1000)
        return j
    raise RuntimeError(f"giving up {url} {params}: {err}")


def walk(path: str, params: dict, cap_pages: int, keep: list[str]) -> tuple[list[dict], bool, int]:
    """Follow the keyset cursor (re-sending all filters). Returns slim rows, capped flag, pages."""
    p = dict(params)
    p.setdefault("limit", 1000)
    out, pages = [], 0
    while True:
        j = get(path, p)
        rows = j.get("data") or []
        out += [{k: r.get(k) for k in keep} for r in rows]
        pages += 1
        cur = (j.get("pagination") or {}).get("next_cursor")
        if not cur:
            return out, False, pages
        if pages >= cap_pages:
            return out, True, pages
        p["cursor"] = cur


TRADE_KEEP_TAPE = ["proxy_wallet", "side", "outcome_index", "size", "price", "timestamp"]
TRADE_KEEP_USER = ["condition_id", "event_slug", "side", "outcome_index", "size", "price", "timestamp"]


def to_df(rows: list[dict], keep: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=keep)
    if len(df):
        df["size"] = df["size"].astype("float64")
        df["price"] = df["price"].astype("float64")
        df["timestamp"] = df["timestamp"].astype("int64")
        df["outcome_index"] = df["outcome_index"].fillna(-1).astype("int16")
        df["side"] = (df["side"] == "BUY").astype("int8")  # 1 = BUY, 0 = SELL
    return df


def u01(key: str) -> float:
    """Deterministic uniform(0,1) from md5 — used for every sampling step (documented, outcome-blind)."""
    return int(hashlib.md5(key.encode()).hexdigest()[:15], 16) / float(16 ** 15)


GAME_RE = r"^(.*?-\d{4}-\d{2}-\d{2})"
MCOLS = ["condition_id", "event_slug", "category4", "t_res", "clean", "pay0", "pay1", "fee_rate_now", "fee_exponent",
         "sportsMarketType", "volumeNum"]


def load_markets(cols: list[str] | None = None) -> pd.DataFrame:
    """Slim market table with the stage-3 underlying-event key `ue` (addendum A6 + slug keys)."""
    m = pd.read_parquet(V2 / "markets_2026.parquet", columns=cols or MCOLS)
    slug = m["event_slug"].fillna("")
    pref = slug.str.extract(GAME_RE)[0]
    sp = (m["category4"] == "sports") & pref.notna()
    m["ue"] = ("s:" + slug).where(~sp, "g:" + pref.fillna(""))
    m["t_res_s"] = ((m["t_res"] - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s")).fillna(0).astype("int64")
    return m


def ue_for_rows(slugs: pd.Series, cids: pd.Series, m: pd.DataFrame) -> pd.Series:
    """ue for trade rows: from the market table when the condition is known; otherwise from the row's event slug,
    using the game prefix only when that prefix is a known sports game key."""
    mm = m.set_index("condition_id")["ue"]
    u = cids.map(mm)
    gset = set(m.loc[m["ue"].str.startswith("g:"), "ue"])
    s = slugs.fillna("")
    pref = "g:" + s.str.extract(GAME_RE)[0].fillna("#")
    fb = pref.where(pref.isin(gset), "s:" + s)
    return u.fillna(fb)
