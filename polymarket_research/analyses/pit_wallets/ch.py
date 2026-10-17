"""CryptoHouse helper for the PIT wallet study: throttled, cached, provenance-recorded SQL with
optional external tables (multipart upload), so wallet/token lists can be joined server-side.

Limits (system.settings, checked 2026-10-17): max_execution_time 60 s, max_result_rows 2000,
max_result_bytes 1,000,000, readonly=1 (no SET), max_memory_usage 20 GB.
Raw responses are stored like pmr.http does: data/raw/cryptohouse/{cache|live}/...
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr.http import RAW, _throttle, _write  # noqa: E402

URL = "https://crypto-clickhouse.clickhouse.com/"
HOST = "crypto-clickhouse.clickhouse.com"
_s = requests.Session()
_s.headers["User-Agent"] = "pmr-research/0.1 (read-only public data)"


class CHError(RuntimeError):
    pass


def q(sql: str, ext: dict | None = None, *, cache: bool = True, retries: int = 4, fmt: str = "JSONCompact",
      timeout: float = 150) -> dict:
    """Run SQL; ext = {name: (structure, tsv_text)}. Returns parsed JSONCompact dict
    (keys meta, data, rows, statistics). Raises CHError on server errors (not retried if 4xx
    deterministic, e.g. syntax / memory / timeout)."""
    sql = sql.strip().rstrip(";") + f" FORMAT {fmt}"
    ext = ext or {}
    exth = {k: hashlib.sha1(v[1].encode()).hexdigest() for k, v in ext.items()}
    key = hashlib.sha1(json.dumps([sql, sorted(exth.items()), sorted((k, v[0]) for k, v in ext.items())]).encode()).hexdigest()
    cpath = RAW / "cryptohouse" / "cache" / key[:2] / f"{key}.json.gz"
    if cache and cpath.exists():
        with gzip.open(cpath, "rt") as f:
            return json.load(f)["body"]
    params = {"user": "crypto"}
    files = None
    if ext:
        params["query"] = sql
        files = {}
        for name, (structure, text) in ext.items():
            params[f"{name}_structure"] = structure
            params[f"{name}_format"] = "TabSeparated"
            files[name] = (f"{name}.tsv", text.encode())
    err = None
    quota_waits = 0
    attempt = -1
    while attempt < retries - 1:
        attempt += 1
        _throttle(HOST)
        t0 = time.monotonic()
        try:
            if files:
                r = _s.post(URL, params=params, files=files, timeout=timeout)
            else:
                r = _s.post(URL, params=params, data=sql.encode(), timeout=timeout)
        except requests.RequestException as e:
            err = e
            time.sleep(min(30, 3 * 2 ** attempt))
            continue
        el = time.monotonic() - t0
        if r.status_code != 200 and "QUOTA_EXCEEDED" in r.text:
            # hourly query quota (120 queries / 3600 s for user crypto, seen 2026-10-17): wait for the interval end
            import re as _re
            m_ = _re.search(r"Interval will end at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", r.text)
            end = datetime.strptime(m_.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) if m_ else None
            wait = (end - datetime.now(timezone.utc)).total_seconds() + 20 if end else 600
            print(f"  [ch] quota exceeded; sleeping {int(max(wait, 30))} s until {m_.group(1) if m_ else '?'}", flush=True)
            time.sleep(max(wait, 30))
            quota_waits += 1
            if quota_waits > 12:
                raise CHError("quota: giving up after 12 waits")
            attempt -= 1
            continue
        if r.status_code != 200:
            full = r.text
            txt = full[:300] + (" ... " + full[-700:] if len(full) > 1000 else full[300:1000])
            # deterministic server errors: do not hammer the shared service
            if any(s in full for s in ("TIMEOUT_EXCEEDED", "Timeout exceeded", "SYNTAX_ERROR", "Syntax error",
                                      "UNKNOWN_IDENTIFIER", "TOO_MANY_ROWS", "Limit for result", "MEMORY_LIMIT",
                                      "ILLEGAL_TYPE", "TYPE_MISMATCH", "NO_COMMON_TYPE", "UNKNOWN_FUNCTION",
                                      "NUMBER_OF_ARGUMENTS", "BAD_ARGUMENTS", "CANNOT_PARSE", "Code: 4", "Code: 6",
                                      "DB::Exception")):
                raise CHError(f"HTTP {r.status_code}: {txt}")
            err = CHError(f"HTTP {r.status_code}: {txt}")
            time.sleep(min(30, 3 * 2 ** attempt))
            continue
        body = r.json()
        now = datetime.now(timezone.utc)
        meta = {"url": URL, "method": "POST", "sql": sql, "ext": {k: [v[0], exth[k], len(v[1])] for k, v in ext.items()},
                "fetched_at_utc": now.isoformat(), "status": r.status_code, "elapsed_ms": round(el * 1000, 1)}
        if cache:
            _write(cpath, meta, body)
        else:
            _write(RAW / "cryptohouse" / "live" / now.strftime("%Y%m%d") / f"{now.strftime('%H%M%S%f')}_{key[:12]}.json.gz",
                   meta, body)
        return body
    raise CHError(f"giving up: {err}")


def rows(sql: str, ext: dict | None = None, **kw) -> list[dict]:
    b = q(sql, ext, **kw)
    names = [m["name"] for m in b["meta"]]
    return [dict(zip(names, r)) for r in b["data"]]


def tsv(rows_iter) -> str:
    return "".join("\t".join(str(x) for x in r) + "\n" for r in rows_iter)
