"""When did Gamma's `restricted` flag become standard? Sample closed markets by start-date window."""
from __future__ import annotations
import collections
from pmr import api

windows = [("2020-10-01","2021-01-01"),("2021-06-01","2021-07-01"),("2022-01-01","2022-02-01"),
           ("2022-06-01","2022-07-01"),("2023-01-01","2023-02-01"),("2023-06-01","2023-07-01"),
           ("2024-01-01","2024-02-01"),("2024-06-01","2024-07-01"),("2024-10-01","2024-11-01"),
           ("2025-01-01","2025-02-01"),("2025-06-01","2025-07-01"),("2026-01-01","2026-02-01"),
           ("2026-06-01","2026-07-01")]
for a, b in windows:
    rows = list(api.gamma_keyset("markets", {"closed": "true", "start_date_min": a, "start_date_max": b},
                                             max_pages=3))
    c = collections.Counter(r.get("restricted") for r in rows)
    print(a, b, "n=", len(rows), dict(c))
