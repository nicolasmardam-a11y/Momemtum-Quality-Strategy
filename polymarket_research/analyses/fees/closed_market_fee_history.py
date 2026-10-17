"""Fee parameters that Gamma reports today for *closed* markets, by start-date window (read-only).

Gamma keeps feeType/feeSchedule on resolved markets, so sampling closed markets by start date shows
which fee regimes were attached to markets over time. This is what Gamma shows now; it does not by
itself prove the fee charged at trade time (see onchain_fee_sampler.py for that).
Writes data/derived/closed_market_fees_sample.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from analyses.fees.collect_open_market_fees import row  # noqa: E402

WINDOWS = pd.date_range("2025-10-01", "2026-10-16", freq="7D")
PAGES = int(sys.argv[1]) if len(sys.argv) > 1 else 3

rows = []
for a, b in zip(WINDOWS[:-1], WINDOWS[1:]):
    p = {"closed": "true", "include_tag": "true", "start_date_min": a.strftime("%Y-%m-%dT00:00:00Z"),
         "start_date_max": b.strftime("%Y-%m-%dT00:00:00Z")}
    got = []
    try:
        for m in api.gamma_keyset("markets", p, max_pages=PAGES, cache=True):
            got.append(row(m))
    except RuntimeError as e:  # Gamma occasionally answers 500 deep in a cursor walk; keep what we have
        print("window", a.date(), "partial:", str(e)[:80])
    for g in got:
        g["window_start"] = a.strftime("%Y-%m-%d")
    rows += got
    print(a.date(), len(got))
df = pd.DataFrame(rows).drop_duplicates("id")
out = ROOT / "data" / "derived" / "closed_market_fees_sample.parquet"
df.to_parquet(out, index=False)
print(out, len(df))
