"""Neg-risk converts attributed to user wallets via the NegRiskCtfCollateralAdapter event (read-only Polygon RPC).

Run from polymarket_research/:  python -m analyses.complete_set_arb.onchain_converts2 [n_blocks] [tag]
The legacy NegRiskAdapter event (onchain_converts.py) names the collateral adapter as stakeholder. The adapter
0xadA2005600Dec949baf300f4C6120000bDB6eAab emits its own
PositionsConverted(address indexed stakeholder, bytes32 indexed marketId, uint256 indexed indexSet, uint256, uint256)
(topic 0x1b8b64a5..., signature verified with web3_sha3) whose stakeholder is the user's wallet.
A convert of all n questions (popcount(indexSet) == getQuestionCount(marketId)) returns (n-1)*amount pUSD: the on-chain
footprint of 'buy every NO, convert' (or of inventory clean-up; the event alone cannot tell them apart).
Writes data/derived/complete_set_arb_converts_<tag>.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

ADAPTER = "0xadA2005600Dec949baf300f4C6120000bDB6eAab"
LEGACY = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"


def main(n_blocks: int = 20000, tag: str = "w2"):
    topic = api.rpc("web3_sha3", ["0x" + b"PositionsConverted(address,bytes32,uint256,uint256,uint256)".hex()])
    qsel = api.rpc("web3_sha3", ["0x" + b"getQuestionCount(bytes32)".hex()])[:10]
    bn = int(api.rpc("eth_blockNumber", []), 16)
    logs = []
    for s in range(bn - n_blocks, bn, 2000):
        logs += api.rpc("eth_getLogs", [{"address": ADAPTER, "topics": [topic], "fromBlock": hex(s), "toBlock": hex(min(bn, s + 1999))}])
    qc = {mid: int(api.rpc("eth_call", [{"to": LEGACY, "data": qsel + mid[2:]}, "latest"]), 16)
          for mid in sorted({l["topics"][2] for l in logs})}
    t0 = int(api.rpc("eth_getBlockByNumber", [hex(bn - n_blocks), False])["timestamp"], 16)
    t1 = int(api.rpc("eth_getBlockByNumber", [hex(bn), False])["timestamp"], 16)
    rows = []
    for l in logs:
        d = l["data"][2:]
        rows.append({"block": int(l["blockNumber"], 16), "tx": l["transactionHash"], "wallet": "0x" + l["topics"][1][-40:],
                     "marketId": l["topics"][2], "k": bin(int(l["topics"][3], 16)).count("1"), "n": qc[l["topics"][2]],
                     "amount": int(d[:64], 16) / 1e6, "amount2": int(d[64:128], 16) / 1e6 if len(d) >= 128 else None})
    df = pd.DataFrame(rows)
    df["all_no"] = df.k == df.n
    df["collateral_out"] = (df.k - 1).clip(lower=0) * df.amount
    # block -> approximate time by linear interpolation between the two endpoint timestamps
    df["t"] = t0 + (df.block - (bn - n_blocks)) * (t1 - t0) / n_blocks
    df.to_parquet(ROOT / "data" / "derived" / f"complete_set_arb_converts_{tag}.parquet", index=False)
    h = (t1 - t0) / 3600
    a = df[df.all_no]
    print(f"blocks {bn - n_blocks}..{bn} ({h:.2f} h): converts {len(df)}, wallets {df.wallet.nunique()}, markets {df.marketId.nunique()}")
    print(f"all-NO converts: {len(a)} by {a.wallet.nunique()} wallets in {a.marketId.nunique()} events; sets {a.amount.sum():,.0f}; "
          f"pUSD released {a.collateral_out.sum():,.0f}")
    top = a.groupby("wallet").agg(n=("tx", "size"), events=("marketId", "nunique"), sets=("amount", "sum"),
                                  released=("collateral_out", "sum"), med_n=("n", "median")).sort_values("sets", ascending=False)
    print(top.head(10).round(1).to_string())
    print("all-NO convert size (sets):", a.amount.describe(percentiles=[.5, .9]).round(2).to_dict())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20000, sys.argv[2] if len(sys.argv) > 2 else "w2")
