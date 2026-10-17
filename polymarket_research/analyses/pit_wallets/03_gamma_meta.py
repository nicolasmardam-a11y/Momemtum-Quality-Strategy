"""M2: Gamma metadata for every outcome token traded on CryptoHouse (from 02_traded_assets).

Run from polymarket_research/:  PMR_RATE_SCALE=2 python analyses/pit_wallets/03_gamma_meta.py
GET /markets/keyset?clob_token_ids=<t1>&clob_token_ids=<t2>...&closed=true&include_tag=true (cached:
resolved markets are immutable history); tokens not found as closed are re-queried without closed
(open markets, cache=False). Writes data/derived/pit_wallets/gamma_markets_traded.parquet (one row per
market) and data/derived/pit_wallets/token_meta.parquet (one row per outcome token).
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

OUT = ROOT / "data" / "derived" / "pit_wallets"
B = 80
KEEP = ["id", "conditionId", "questionID", "question", "slug", "groupItemTitle", "outcomes", "outcomePrices", "clobTokenIds",
        "active", "closed", "closedTime", "umaEndDate", "umaResolutionStatus", "umaResolutionStatuses", "endDate", "startDate",
        "createdAt", "negRisk", "negRiskMarketID", "negRiskOther", "category", "feeType", "feesEnabled", "volumeNum",
        "sportsMarketType", "gameId", "gameStartTime", "automaticallyResolved", "resolvedBy", "fpmmLive", "marketMakerAddress"]


def slim(m: dict) -> dict:
    d = {k: (json.dumps(m.get(k)) if isinstance(m.get(k), (list, dict)) else m.get(k)) for k in KEEP}
    tags = m.get("tags") or []
    d["tag_slugs"] = "|".join((t.get("slug") or "") for t in tags)
    d["tag_labels"] = "|".join((t.get("label") or "") for t in tags)
    evs = m.get("events") or []
    d["n_events"] = len(evs)
    e = evs[0] if evs else {}
    d["event_id"] = str(e.get("id")) if e.get("id") is not None else None
    d["event_slug"] = e.get("slug"); d["event_title"] = e.get("title")
    d["event_negRisk"] = e.get("negRisk"); d["event_seriesSlug"] = e.get("seriesSlug")
    d["event_closedTime"] = e.get("closedTime"); d["event_endDate"] = e.get("endDate")
    d["event_ids_all"] = "|".join(str(x.get("id")) for x in evs)
    return d


FAILED: list[str] = []


def fetch(batch: list[str], closed: bool) -> list[dict]:
    """Gamma returns HTTP 500 for some batches (seen 2026-10-17); split the batch until the failing
    token is isolated, and record isolated failures instead of aborting."""
    p = {"clob_token_ids": batch, "include_tag": "true", "limit": 100}
    if closed:
        p["closed"] = "true"
    try:
        out = []
        while True:
            j = request_json(f"{api.GAMMA}/markets/keyset", p, source="gamma", cache=closed, retries=3 if len(batch) > 1 else 4)
            out += [slim(m) for m in j.get("markets") or []]
            cur = j.get("next_cursor")
            if not cur:
                return out
            p = {**p, "after_cursor": cur}
    except RuntimeError as e:
        if len(batch) == 1:
            FAILED.append(batch[0])
            print("failed token", batch[0], str(e)[-120:], flush=True)
            return []
        h = len(batch) // 2
        return fetch(batch[:h], closed) + fetch(batch[h:], closed)


def main():
    toks = pd.read_parquet(OUT / "traded_assets.parquet").token_id.astype(str).tolist()
    toks = sorted(set(toks))
    batches = [toks[i:i + B] for i in range(0, len(toks), B)]
    print("tokens", len(toks), "batches", len(batches), flush=True)
    rows = []
    with ThreadPoolExecutor(4) as ex:
        for i, r in enumerate(ex.map(lambda b: fetch(b, True), batches)):
            rows += r
            if i % 200 == 0:
                print("closed batch", i, len(rows), flush=True)
    mk = pd.DataFrame(rows).drop_duplicates("id")
    have = set()
    for s in mk.clobTokenIds.dropna():
        have |= set(api.jlist(s))
    miss = [t for t in toks if t not in have]
    print("missing after closed pass:", len(miss), flush=True)
    rows2 = []
    mb = [miss[i:i + B] for i in range(0, len(miss), B)]
    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(lambda b: fetch(b, False), mb):
            rows2 += r
    if rows2:
        mk = pd.concat([mk, pd.DataFrame(rows2)]).drop_duplicates("id")
    mk.to_parquet(OUT / "gamma_markets_traded.parquet", index=False)
    # token table
    tr = []
    for m in mk.itertuples(index=False):
        ids = api.jlist(m.clobTokenIds); outs = api.jlist(m.outcomes); prs = api.jlist(m.outcomePrices)
        for j, t in enumerate(ids):
            tr.append({"token_id": str(t), "market_id": m.id, "condition_id": m.conditionId, "outcome_index": j,
                       "outcome": outs[j] if j < len(outs) else None,
                       "payout_raw": prs[j] if j < len(prs) else None, "n_outcomes": len(ids)})
    tt = pd.DataFrame(tr).drop_duplicates("token_id")
    tt.to_parquet(OUT / "token_meta.parquet", index=False)
    still = set(toks) - set(tt.token_id)
    print("markets", len(mk), "tokens with meta", len(tt), "traded tokens without Gamma meta", len(still), flush=True)
    pd.DataFrame({"token_id": sorted(set(FAILED))}).to_parquet(OUT / "gamma_failed_tokens.parquet", index=False)
    print("tokens whose Gamma lookup failed with HTTP 500:", len(set(FAILED)), flush=True)


if __name__ == "__main__":
    main()
