"""Pull the full market trade tape (taker_only=false and default taker-only) for every market
traded by the three wallets, plus CLOB /prices-history (1-min) around each match.

Resumable: tapes of resolved markets are immutable, so cache=True.
Usage: python analyses/wallets/ge_pull_tapes.py [condition_id ...]
Outputs: data/derived/ge_tape_<cid[:10]>.parquet, ge_tape_taker_<cid[:10]>.parquet, ge_prices_1m.parquet
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

OUT = ROOT / "data" / "derived"
TAPE_COLS = ["proxy_wallet", "side", "token_id", "condition_id", "size", "price", "timestamp", "outcome",
             "outcome_index", "name", "pseudonym", "transaction_hash"]


def pull_tape(cid: str) -> None:
    for to, tag in ((False, "ge_tape"), (True, "ge_tape_taker")):
        f = OUT / f"{tag}_{cid[:10]}.parquet"
        if f.exists():
            continue
        rows = api.trades(condition=cid, taker_only=to, filter_amount=0, cache=True)
        df = pd.DataFrame(rows)
        df = df[[c for c in TAPE_COLS if c in df.columns]]
        df.to_parquet(f, index=False)
        print(cid[:10], tag, len(df), flush=True)


def pull_prices(mk: pd.DataFrame) -> None:
    rows = []
    for _, m in mk.iterrows():
        toks = json.loads(m.clobTokenIds)
        outs = json.loads(m.outcomes)
        ks = pd.Timestamp(m.gameStartTime).timestamp()
        # 6 h before kickoff to 3 h after
        a, b = int(ks - 6 * 3600), int(ks + 3 * 3600)
        for tok, o in zip(toks, outs):
            for s in range(a, b, 3 * 3600):  # chunk in 3 h windows
                for pt in api.prices_history(tok, s, min(b, s + 3 * 3600), 1, cache=True):
                    rows.append({"condition_id": m.conditionId, "token_id": tok, "outcome": o, "t": pt["t"], "p": pt["p"]})
    df = pd.DataFrame(rows).drop_duplicates(["token_id", "t"])
    df.to_parquet(OUT / "ge_prices_1m.parquet", index=False)
    print("prices", len(df))


def main() -> None:
    mk = pd.read_parquet(OUT / "ge_markets.parquet")
    cids = sys.argv[1:] or list(mk.conditionId)
    for cid in cids:
        pull_tape(cid)
    if not sys.argv[1:]:
        pull_prices(mk)


if __name__ == "__main__":
    main()
