"""Independent coverage check of the Gamma universe against on-chain fills (CryptoHouse).

Pre-registered check 5 named CryptoHouse polymarket.assets as the independent count source, but that
table holds only 22,759 markets in total (queried 2026-10-17), far below Gamma's counts, so a
month-by-month count comparison is not meaningful. Substitute (declared after the fact in universe.md):
a hash sample of on-chain conditions from polymarket.token_id_condition (cityHash64(condition) % 1000
in RESIDUES), with first/last OrderFilled timestamps from polymarket.orders_filled (pre-V2 exchange,
2022-11-21..2026-01-05). Every sampled condition with a fill and last fill in [2024-01-08, 2025-12-20)
should be in markets_resolved.parquet unless its Gamma endDate lies outside the window or is null.
Missing ones are looked up on Gamma (closed=true and closed=false) to classify the gap.

Run from polymarket_research/: python analyses/universe/06_crosscheck_onchain_sample.py
Writes data/derived/universe_crosscheck_onchain_sample.parquet (+ .json summary).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

DER = ROOT / "data" / "derived"
RESIDUES = (7, 11, 23, 37, 51, 73)
SQL = """SELECT t.condition AS c, min(f.timestamp) AS t0, max(f.timestamp) AS t1, count() AS n
FROM polymarket.orders_filled f
INNER JOIN (SELECT id, condition FROM polymarket.token_id_condition WHERE cityHash64(condition) % 1000 IN {res}) t
ON t.id = if(f.maker_asset_id = '0', f.taker_asset_id, f.maker_asset_id)
GROUP BY c"""


def main() -> None:
    frames = []
    for i in range(0, len(RESIDUES), 3):
        res = "(" + ",".join(str(x) for x in RESIDUES[i:i + 3]) + ")"
        frames.append(pd.DataFrame(api.cryptohouse(SQL.format(res=res))))
    r = pd.concat(frames, ignore_index=True)
    r["c"] = r["c"].str.lower()
    r["t0"] = pd.to_datetime(r["t0"], utc=True)
    r["t1"] = pd.to_datetime(r["t1"], utc=True)
    r["n"] = r["n"].astype(int)
    u = pq.read_table(DER / "markets_resolved.parquet", columns=["condition_id", "endDate"]).to_pandas()
    u["condition_id"] = u["condition_id"].str.lower()
    r = r.merge(u.rename(columns={"condition_id": "c"}), on="c", how="left")
    r["in_universe"] = r["endDate"].notna()
    r["in_window"] = (r["t1"] >= pd.Timestamp("2024-01-08", tz="UTC")) & (r["t1"] < pd.Timestamp("2025-12-20", tz="UTC"))
    miss = r[r["in_window"] & ~r["in_universe"]]
    look = {}
    ids = list(miss["c"])
    for k in range(0, len(ids), 50):
        for closed in ("true", "false"):
            j = request_json(f"{api.GAMMA}/markets/keyset", {"condition_ids": ids[k:k + 50], "closed": closed, "limit": 100},
                             source="gamma", cache=True)
            for m in j.get("markets") or []:
                look[m["conditionId"].lower()] = {"gamma_closed_param": closed, "gamma_endDate": m.get("endDate"),
                                                  "gamma_closedTime": m.get("closedTime"), "question": (m.get("question") or "")[:100]}
    r["gamma_lookup"] = r["c"].map(lambda c: json.dumps(look.get(c)) if c in look else None)

    def reason(row):
        if row["in_universe"]:
            return "in_universe"
        g = look.get(row["c"])
        if g is None:
            return "not_on_gamma"
        if not g["gamma_endDate"]:
            return "gamma_null_endDate"
        e = g["gamma_endDate"][:10]
        if e < "2024-01-01" or e >= "2026-10-16":
            return "gamma_endDate_outside_window"
        return "gamma_open" if g["gamma_closed_param"] == "false" else "unexplained"
    r["status"] = r.apply(reason, axis=1)
    w = r[r["in_window"]]
    k, n = int(w["in_universe"].sum()), len(w)
    z = 1.96
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    out = {"residues": RESIDUES, "sampled_conditions_with_fills": len(r), "in_window": n, "in_universe": k,
           "coverage": p, "wilson95": [centre - half, centre + half],
           "status_counts_in_window": w["status"].value_counts().to_dict(),
           "coverage_vol_weighted_by_fills": float(w.loc[w["in_universe"], "n"].sum() / w["n"].sum())}
    r.to_parquet(DER / "universe_crosscheck_onchain_sample.parquet", index=False)
    (DER / "universe_crosscheck_onchain_sample.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
