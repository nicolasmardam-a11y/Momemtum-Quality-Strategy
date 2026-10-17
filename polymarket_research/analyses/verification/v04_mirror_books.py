"""Verifier check (read-only): are YES and NO books exact mirrors (YES bid p,size == NO ask 1-p,size)?
Source: CLOB GET /book (live), one call per token, both sides fetched back-to-back."""
import json, time
import pandas as pd
from pmr import api
d = pd.read_parquet("data/derived/open_market_fees_2026-10-17.parquet")
d["end"] = pd.to_datetime(d.endDate, errors="coerce", utc=True)
now = pd.Timestamp.now(tz="UTC")
cand = d[(d.end > now + pd.Timedelta(days=2)) & (d.volume24hr > 20000)].sort_values("volume24hr", ascending=False)
res = []
for _, r in cand.head(40).iterrows():
    g = api.gamma_markets(condition_ids=r.conditionId)
    if not g:
        continue
    toks = api.jlist(g[0].get("clobTokenIds"))
    if len(toks) != 2:
        continue
    try:
        a, b = api.book(toks[0]), api.book(toks[1])
    except Exception as e:
        continue
    ya = {round(p, 4): s for p, s in a["bids"]}
    nb = {round(1 - p, 4): s for p, s in b["asks"]}
    yb = {round(p, 4): s for p, s in a["asks"]}
    na = {round(1 - p, 4): s for p, s in b["bids"]}
    same = ya == nb and yb == na
    sum_asks = (a["asks"][0][0] + b["asks"][0][0]) if a["asks"] and b["asks"] else None
    sum_bids = (a["bids"][0][0] + b["bids"][0][0]) if a["bids"] and b["bids"] else None
    res.append({"q": r.question[:50], "mirror_exact": same, "levels": len(ya) + len(yb), "sum_best_asks": sum_asks,
                "sum_best_bids": sum_bids, "dt_ms": (b["timestamp_ms"] or 0) - (a["timestamp_ms"] or 0)})
    if len(res) >= 12:
        break
for x in res:
    print(x)
print("exact mirrors:", sum(x["mirror_exact"] for x in res), "/", len(res))
json.dump(res, open("data/derived/verification_mirror_books.json", "w"), indent=0)
