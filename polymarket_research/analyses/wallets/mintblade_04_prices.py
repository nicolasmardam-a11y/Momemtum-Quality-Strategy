"""CLOB /prices-history (fidelity=1 min) for every outcome of the markets mintblade traded,
from 2 h before the wallet's first fill in that event to 30 min after the game finished.

These series are trade/mid prints, not executable bid/ask and not depth.
Output: data/derived/mintblade_prices_history.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pmr import api  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "data" / "derived"


def main():
    mk = pd.read_parquet(OUT / "mintblade_markets.parquet")
    sib = pd.read_parquet(OUT / "mintblade_event_markets.parquet")
    fills = pd.read_parquet(OUT / "mintblade_trades_all.parquet")
    first = fills.groupby("condition_id").timestamp.min()
    # include the sibling 1X2 markets of the two football matches (same parent event)
    want = set(mk.conditionId)
    want |= set(sib[sib.event_slug.isin(["fifwc-irn-nzl-2026-06-15", "fifwc-ksa-ury-2026-06-15"])].conditionId)
    rows = []
    allm = pd.concat([mk, sib]).drop_duplicates("conditionId").set_index("conditionId")
    for c in sorted(want):
        m = allm.loc[c]
        # window anchor: the wallet's first fill in any market of the same match
        match = m.event_slug.replace("-more-markets", "")
        cids = allm[allm.event_slug.str.replace("-more-markets", "") == match].index
        t0 = int(first[first.index.isin(cids)].min()) - 2 * 3600
        fin = m.event_finishedTimestamp or m.closedTime
        t1 = int(pd.Timestamp(fin).timestamp()) + 1800 if isinstance(fin, str) else t0 + 8 * 3600
        for tok, outc in zip(api.jlist(m.clobTokenIds), api.jlist(m.outcomes)):
            h = api.prices_history(tok, t0, t1, 1, cache=True)
            for p in h:
                rows.append({"condition_id": c, "question": m.question, "token_id": tok, "outcome": outc,
                             "t": p["t"], "p": p["p"]})
            print(m.question[:50], outc, len(h), flush=True)
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df.t, unit="s", utc=True)
    df.to_parquet(OUT / "mintblade_prices_history.parquet", index=False)


if __name__ == "__main__":
    main()
