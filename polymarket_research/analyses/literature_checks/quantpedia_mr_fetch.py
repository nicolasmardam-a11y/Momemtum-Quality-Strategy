"""Fetch the price series used (approximately) by Vojtko & Dujava (2026), "Exploiting
Mean-Reversion in Decentralized Prediction Markets: Evidence from Polymarket Binary Contracts"
(Quantpedia blog 2026-04-17; SSRN 10.2139/ssrn.6726362).

Read-only. Pulls Gamma metadata and CLOB /prices-history (10-minute fidelity) for the
"No" token of the three contracts the authors studied, and a public trade tape summary,
then writes one parquet per contract to data/derived/literature_checks/.

CLOB /prices-history is a trade/mid series, NOT executable bid/ask prices.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

OUT = ROOT / "data" / "derived" / "literature_checks"
OUT.mkdir(parents=True, exist_ok=True)

SLUGS = {
    "Jesus": "will-jesus-christ-return-in-2025",
    "China": "will-china-invade-taiwan-in-2025",
    "Alien": "will-the-us-confirm-that-aliens-exist-in-2025",
}


def ts(s: str) -> int:
    return int(pd.Timestamp(s).tz_convert("UTC").timestamp()) if pd.Timestamp(s).tzinfo else int(pd.Timestamp(s, tz="UTC").timestamp())


def fetch_history(asset: str, start: int, end: int, fidelity: int = 10, chunk_days: int = 14) -> pd.DataFrame:
    rows = []
    t = start
    while t < end:
        t2 = min(end, t + chunk_days * 86400)
        rows += api.prices_history(asset, t, t2, fidelity)
        t = t2
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.drop_duplicates("t").sort_values("t")
    df["time"] = pd.to_datetime(df["t"], unit="s", utc=True)
    return df[["time", "t", "p"]].reset_index(drop=True)


def main() -> None:
    meta = []
    for name, slug in SLUGS.items():
        ev = api.gamma_events(slug=slug, closed="true", max_pages=1)[0]
        m = ev["markets"][0]
        outcomes = api.jlist(m["outcomes"])
        asset_ids = api.jlist(m["clobTokenIds"])
        no_asset = asset_ids[outcomes.index("No")]
        start = ts(m["startDate"])
        end = ts(m["umaEndDate"]) + 3600
        h = fetch_history(no_asset, start, end)
        h.to_parquet(OUT / f"qp_mr_{name.lower()}_no_10min.parquet", index=False)
        meta.append({
            "name": name, "slug": slug, "condition_id": m["conditionId"], "no_asset_id": no_asset,
            "start": m["startDate"], "end": m["endDate"], "closed": m.get("closedTime"),
            "outcome_prices": m["outcomePrices"], "volume": m.get("volumeNum"),
            "tick_now": m.get("orderPriceMinTickSize"), "fees_enabled": m.get("feesEnabled"),
            "holding_rewards": m.get("holdingRewardsEnabled"),
            "n_points": len(h), "first": h["time"].min() if len(h) else None, "last": h["time"].max() if len(h) else None,
        })
        print(name, len(h), h["time"].min() if len(h) else None, h["time"].max() if len(h) else None)
    pd.DataFrame(meta).to_csv(OUT / "qp_mr_meta.csv", index=False)
    print("fetched", datetime.now(timezone.utc).isoformat())


if __name__ == "__main__":
    main()
