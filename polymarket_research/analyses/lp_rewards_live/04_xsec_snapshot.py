"""Snapshot YES-token books (POST /books) for the reward cross-section. Usage: python -m analyses.lp_rewards_live.04_xsec_snapshot <tag>
-> data/derived/lp_rewards_live/xsec_books_<tag>.parquet (bids/asks best-first, top 80 levels, JSON)."""
import json, sys, time
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
OUT = ROOT / "data/derived/lp_rewards_live"
x = pd.read_parquet(OUT / "xsec_markets.parquet")
toks = x.yes_token.dropna().unique().tolist()
t0 = time.time(); bs = api.books(toks)
rows = [{"snap_utc": t0, "asset_id": b["asset_id"], "market": b["market"], "ts_ms": b["timestamp_ms"], "bids": json.dumps(b["bids"][:80]),
         "asks": json.dumps(b["asks"][:80]), "n_bid_lv": len(b["bids"]), "n_ask_lv": len(b["asks"]), "tick": b["tick_size"],
         "min_order": b["min_order_size"], "neg_risk": b["neg_risk"]} for b in bs]
pd.DataFrame(rows).to_parquet(OUT / f"xsec_books_{sys.argv[1]}.parquet", index=False)
print(sys.argv[1], len(toks), "requested", len(rows), "books", round(time.time() - t0, 1), "s")
