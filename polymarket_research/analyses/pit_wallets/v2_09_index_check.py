"""Stage 3 check: does Data API v2 trade `outcome_index` equal the Gamma outcome position (clobTokenIds order)?

Run from polymarket_research/:  python analyses/pit_wallets/v2_09_index_check.py
For 150 pool-sample markets (smallest md5) one 50-row page of /v2/trades is compared with token_id_0/1 of the
shared Gamma universe. Output: v2/index_check.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent))
from v2common import ROOT, V2, get, u01  # noqa: E402


def main() -> None:
    ps = pd.read_parquet(V2 / "pool_sample.parquet", columns=["condition_id", "stratum"])
    ps["u"] = ps["condition_id"].map(lambda c: u01("idx|" + c))
    ps = ps.nsmallest(150, "u")
    g = pq.read_table(ROOT / "data" / "derived" / "markets_resolved.parquet",
                      columns=["condition_id", "token_id_0", "token_id_1"],
                      filters=[("condition_id", "in", ps["condition_id"].tolist())]).to_pandas()
    rows = []
    for cid in ps["condition_id"]:
        j = get("/v2/trades", {"condition": cid, "taker_only": "false", "limit": 50})
        for r in j.get("data") or []:
            rows.append({"condition_id": cid, "token_id": r["token_id"], "outcome_index": r["outcome_index"]})
    d = pd.DataFrame(rows).merge(g, on="condition_id")
    d["gamma_idx"] = (d["token_id"] == d["token_id_1"]).astype(int).where(
        (d["token_id"] == d["token_id_0"]) | (d["token_id"] == d["token_id_1"]), -1)
    d["match"] = d["gamma_idx"] == d["outcome_index"]
    d.to_parquet(V2 / "index_check.parquet", index=False)
    print(f"rows {len(d)}, markets {d['condition_id'].nunique()}, token found {float((d['gamma_idx'] >= 0).mean()):.4f}, "
          f"outcome_index == Gamma position {float(d['match'].mean()):.4f}, mismatching markets "
          f"{d.loc[~d['match'], 'condition_id'].nunique()}")


if __name__ == "__main__":
    main()
