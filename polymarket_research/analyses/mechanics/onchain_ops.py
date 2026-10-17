"""On-chain measurements of position operations (read-only, public Polygon RPC).

1. Neg-risk convert (legacy NegRiskAdapter PositionsConverted): gas used per tx vs the
   number of questions in the neg-risk market.
2. AutoRedeemer (BinaryRedemption / NegRiskRedemption / Redemption): how long after a
   market's resolution the automated redemption lands. Resolution time proxy: Gamma
   `closedTime` (shown elsewhere in these notes to coincide with the /v2/resolutions
   last-update timestamp to within the minute); on-chain resolution events are not
   fetched here.

Output: data/derived/mechanics_onchain_ops_<UTC>.parquet (+ printed summary).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from keccak import selector, topic  # noqa: E402
from pmr import api  # noqa: E402

NRA = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
AR = "0xa1200000d0002264C9a1698e001292D00E1b00af"
T_CONV = topic("PositionsConverted(address,bytes32,uint256,uint256)")
T_BIN = topic("BinaryRedemption(address,bytes32,uint256)")
T_NR = topic("NegRiskRedemption(address,bytes32,uint256)")


def logs(addr: str, t: str, lo: int, hi: int) -> list[dict]:
    out = []
    for a in range(lo, hi + 1, 1000):
        out += api.rpc("eth_getLogs", [{"address": addr, "topics": [t], "fromBlock": hex(a), "toBlock": hex(min(a + 999, hi))}])
    return out


_bts: dict[int, int] = {}


def block_ts(bn: int) -> int:
    if bn not in _bts:
        _bts[bn] = int(api.rpc("eth_getBlockByNumber", [hex(bn), False])["timestamp"], 16)
    return _bts[bn]


def main() -> None:
    head = int(api.rpc("eth_blockNumber", []), 16)
    # 1) converts: last 1,500 blocks, up to 60 distinct transactions
    conv = logs(NRA, T_CONV, head - 1500, head)
    rows = []
    seen = set()
    for lg in conv:
        h = lg["transactionHash"]
        if h in seen or len(seen) >= 60:
            continue
        seen.add(h)
        market_id = lg["topics"][2]
        index_set = int(lg["topics"][3], 16)  # indexSet is indexed (INegRiskAdapter.sol)
        amount = int(lg["data"][2:66], 16) / 1e6
        qn = int(api.rpc("eth_call", [{"to": NRA, "data": selector("getQuestionCount(bytes32)") + market_id[2:]}, "latest"]), 16)
        rc = api.rpc("eth_getTransactionReceipt", [h])
        rows.append({"kind": "convert", "tx": h, "market_id": market_id, "questions": qn,
                     "n_no_converted": bin(index_set).count("1"), "amount": amount,
                     "gas_used": int(rc["gasUsed"], 16), "gas_price_gwei": int(rc["effectiveGasPrice"], 16) / 1e9,
                     "tx_to": rc["to"], "n_logs_in_tx": len(rc["logs"])})
    cdf = pd.DataFrame(rows)

    # 2) auto-redeem lag: last 600 blocks of binary + neg-risk redemptions
    ar = [("binary", lg) for lg in logs(AR, T_BIN, head - 600, head)] + [("negrisk", lg) for lg in logs(AR, T_NR, head - 600, head)]
    arows = []
    for kind, lg in ar:
        arows.append({"kind": "auto_" + kind, "tx": lg["transactionHash"], "block": int(lg["blockNumber"], 16),
                      "holder": "0x" + lg["topics"][1][-40:], "conditionId": lg["topics"][2],
                      "payout": int(lg["data"][2:66], 16) / 1e6})
    adf = pd.DataFrame(arows)
    print("auto-redeem events (last 600 blocks):", len(adf), "distinct tx:", adf["tx"].nunique() if len(adf) else 0)
    lag = pd.DataFrame()
    if len(adf):
        # one Gamma lookup per condition (sampled), using closed=true
        conds = adf["conditionId"].drop_duplicates().sample(min(150, adf["conditionId"].nunique()), random_state=7).tolist()
        closed = {}
        for i in range(0, len(conds), 20):
            for m in api.gamma_keyset("markets", {"closed": "true", "limit": 100, "condition_ids": conds[i:i + 20]}):
                closed[m["conditionId"].lower()] = m.get("closedTime")
        sub = adf[adf["conditionId"].isin(conds)].copy()
        sub["closedTime"] = sub["conditionId"].str.lower().map(closed)
        sub = sub.dropna(subset=["closedTime"])
        sub["block_ts"] = sub["block"].map(block_ts)
        sub["closed_ts"] = pd.to_datetime(sub["closedTime"], utc=True, format="mixed").map(lambda x: int(x.timestamp()))  # unit-safe under pandas 3
        sub["lag_min"] = (sub["block_ts"] - sub["closed_ts"]) / 60
        lag = sub
        per_cond = sub.groupby("conditionId")["lag_min"].min()
        print("conditions matched in Gamma:", len(per_cond))
        print("minutes from Gamma closedTime to FIRST auto-redeem seen in window (per condition):")
        print(per_cond.describe(percentiles=[.1, .25, .5, .75, .9]).round(1).to_string())
        print("payout per event (pUSD):", adf["payout"].describe(percentiles=[.5, .9, .99]).round(2).to_string())
        print("zero-payout (losing side) share:", round((adf["payout"] == 0).mean(), 3))
        txs = adf.groupby("tx").size()
        print("events per auto-redeem tx:", txs.describe().round(1).to_string())
        rc = api.rpc("eth_getTransactionReceipt", [adf["tx"].iloc[0]])
        print("example auto-redeem tx from:", rc["from"], "to:", rc["to"], "gasUsed:", int(rc["gasUsed"], 16))
    if len(cdf):
        print("\nconvert txs:", len(cdf))
        print(cdf.groupby(pd.cut(cdf["questions"], [0, 3, 8, 15, 40, 400]))[["gas_used", "gas_price_gwei", "n_no_converted"]]
              .median().to_string())
        print("tx_to:", cdf["tx_to"].value_counts().to_string())
        print("amount converted:", cdf["amount"].describe(percentiles=[.5, .9]).round(2).to_string())
    out = ROOT / "data" / "derived" / f"mechanics_onchain_ops_{datetime.now(timezone.utc):%Y%m%dT%H%M}.parquet"
    pd.concat([cdf, lag], ignore_index=True).astype(str).to_parquet(out)
    print("->", out)


if __name__ == "__main__":
    main()
