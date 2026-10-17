"""Who does all-NO converts, and at what implied edge? (read-only Data API v2 + derived convert events)

Run from polymarket_research/:  python -m analyses.complete_set_arb.converter_wallets [tag] [n_wallets]
Input: data/derived/complete_set_arb_converts_<tag>.parquet (onchain_converts2.py).
For the n_wallets largest all-NO converters: pull /v2/activity and /v2/trades (taker_only=true and false), map each
all-NO convert to the wallet's NO buys in the same event during the 60 min before the convert, and compute the implied
per-set edge = (n - 1) - sum_i VWAP(NO_i) (fees not included: the Data API rows do not carry fees) for converts whose
every leg was bought in that window. Also reports what share of the wallet's fills in those events were taker fills.
Writes data/derived/complete_set_arb_converter_edges_<tag>.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

D = ROOT / "data" / "derived"


def main(tag: str = "d1017", n_wallets: int = 6):
    cv = pd.read_parquet(D / f"complete_set_arb_converts_{tag}.parquet")
    a = cv[cv.all_no]
    top = a.groupby("wallet").amount.sum().sort_values(ascending=False).head(n_wallets).index.tolist()
    # marketId (negRiskMarketID) -> conditionIds, from the latest universe snapshots (open markets) of both windows
    uvs = sorted((D / "complete_set_arb").glob("universe_v*.parquet"))
    cm = pd.concat([pd.read_parquet(f, columns=["nr_id", "conditionId", "fee_rate"]) for f in uvs]).drop_duplicates("conditionId")
    cond2nr = dict(zip(cm.conditionId, cm.nr_id))
    rate = dict(zip(cm.conditionId, cm.fee_rate))
    t_lo = a.t.min() - 3600
    out = []
    for w in top:
        act = pd.DataFrame(list(api.data_v2("/v2/activity", {"user": w}, max_pages=20)))
        act = act[act.timestamp >= t_lo]
        tk = pd.DataFrame(list(api.data_v2("/v2/trades", {"user": w, "taker_only": "true"}, max_pages=20)))
        taker_tx = set(tk.transaction_hash) if len(tk) else set()
        tr = act[act.type == "TRADE"].copy()
        tr["nr_id"] = tr.condition_id.map(cond2nr)
        tr["taker"] = tr.transaction_hash.isin(taker_tx)
        for c in a[a.wallet == w].itertuples():
            x = tr[(tr.nr_id == c.marketId) & (tr.timestamp <= c.t + 30) & (tr.timestamp >= c.t - 3600)]
            nob = x[(x.side == "BUY") & (x.outcome_index == 1)]
            legs = nob.groupby("condition_id").apply(lambda g: pd.Series({"sz": g["size"].sum(),
                                                                           "vwap": (g["size"] * g.price).sum() / g["size"].sum()}),
                                                     include_groups=False)
            complete = len(legs) == c.n
            fee_est = float(sum(r.sz and rate.get(cid, 0.05) * r.vwap * (1 - r.vwap) for cid, r in legs.iterrows())) if complete else np.nan
            out.append({"wallet": w, "tx": c.tx, "t": c.t, "marketId": c.marketId, "n": c.n, "amount": c.amount,
                        "n_trades_window": len(x), "n_no_buys": len(nob), "legs_found": len(legs), "complete": complete,
                        "sum_vwap_no": legs.vwap.sum() if complete else np.nan,
                        "edge_gross": (c.n - 1) - legs.vwap.sum() if complete else np.nan,
                        "fee_if_taker_ps": fee_est,
                        "taker_share": float(x.taker.mean()) if len(x) else np.nan,
                        "no_buy_taker_share": float(nob.taker.mean()) if len(nob) else np.nan,
                        "event": x.event_slug.iloc[0] if len(x) else None})
        print(f"{w[:10]}: activity {len(act)} rows since window start, taker trades {len(tk)}", flush=True)
    df = pd.DataFrame(out)
    df.to_parquet(D / f"complete_set_arb_converter_edges_{tag}.parquet", index=False)
    print(df.groupby("wallet").agg(converts=("tx", "size"), sets=("amount", "sum"), complete=("complete", "sum"),
                                   med_edge=("edge_gross", "median"), mean_edge=("edge_gross", "mean"),
                                   med_fee_if_taker=("fee_if_taker_ps", "median"),
                                   taker_share=("taker_share", "mean"), no_buy_taker=("no_buy_taker_share", "mean")).round(4).to_string())
    c = df[df.complete]
    if len(c):
        print("complete converts:", len(c), "sets", round(c.amount.sum()), "set-weighted gross edge",
              round((c.edge_gross * c.amount).sum() / c.amount.sum(), 4))
        print(c.groupby(c.event.str[:4]).agg(n=("tx", "size"), sets=("amount", "sum"), edge=("edge_gross", "median")).to_string())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "d1017", int(sys.argv[2]) if len(sys.argv) > 2 else 6)
