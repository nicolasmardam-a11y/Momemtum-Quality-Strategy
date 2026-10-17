"""Recent neg-risk conversions on the legacy NegRiskAdapter (read-only Polygon RPC).

Run from polymarket_research/:  python -m analyses.complete_set_arb.onchain_converts [n_blocks]
For each PositionsConverted(stakeholder, marketId, indexSet, amount) event in the last n_blocks, compares the
number of converted NO questions (popcount of indexSet) with getQuestionCount(marketId). A convert of all n
questions returns (n-1)·amount pUSD and is the signature of a 'buy every NO, convert' complete-set trade
(or of position clean-up; the two cannot be told apart from the event alone).
Writes data/derived/complete_set_arb_onchain_converts.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

AD = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"


def main(n_blocks: int = 20000):
    topic = api.rpc("web3_sha3", ["0x" + b"PositionsConverted(address,bytes32,uint256,uint256)".hex()])
    qsel = api.rpc("web3_sha3", ["0x" + b"getQuestionCount(bytes32)".hex()])[:10]
    bn = int(api.rpc("eth_blockNumber", []), 16)
    logs = []
    for s in range(bn - n_blocks, bn, 2000):
        logs += api.rpc("eth_getLogs", [{"address": AD, "topics": [topic], "fromBlock": hex(s), "toBlock": hex(min(bn, s + 1999))}])
    qc = {}
    for mid in sorted({l["topics"][2] for l in logs}):
        qc[mid] = int(api.rpc("eth_call", [{"to": AD, "data": qsel + mid[2:]}, "latest"]), 16)
    t0 = int(api.rpc("eth_getBlockByNumber", [hex(bn - n_blocks), False])["timestamp"], 16)
    t1 = int(api.rpc("eth_getBlockByNumber", [hex(bn), False])["timestamp"], 16)
    rows = [{"block": int(l["blockNumber"], 16), "tx": l["transactionHash"], "stakeholder": "0x" + l["topics"][1][-40:],
             "marketId": l["topics"][2], "k": bin(int(l["topics"][3], 16)).count("1"), "n": qc[l["topics"][2]],
             "amount": int(l["data"], 16) / 1e6} for l in logs]
    df = pd.DataFrame(rows)
    df["all_no"] = df.k == df.n
    df["collateral_out"] = (df.k - 1).clip(lower=0) * df.amount
    df.attrs["span_hours"] = (t1 - t0) / 3600
    df.to_parquet(ROOT / "data" / "derived" / "complete_set_arb_onchain_converts.parquet", index=False)
    h = (t1 - t0) / 3600
    print(f"blocks {bn - n_blocks}..{bn}, {h:.2f} h, converts {len(df)} ({len(df) / h:.0f}/h), markets {df.marketId.nunique()}")
    print(f"all-NO converts (k == n): {int(df.all_no.sum())} ({df.all_no.mean():.1%}); pUSD released by all-NO converts "
          f"{df[df.all_no].collateral_out.sum():,.0f}; total collateral released {df.collateral_out.sum():,.0f}")
    print(f"k == n-1: {int((df.k == df.n - 1).sum())}; k == 1: {int((df.k == 1).sum())}")
    print(df.groupby(df.n.clip(upper=10)).agg(converts=("tx", "size"), all_no=("all_no", "sum"), amt_med=("amount", "median")).to_string())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20000)
