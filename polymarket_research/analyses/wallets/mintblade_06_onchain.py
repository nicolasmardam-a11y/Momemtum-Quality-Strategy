"""On-chain checks for mintblade deposits/withdrawals (read-only Polygon JSON-RPC).

publicnode refuses receipts older than its pruning window ("archive requests require a
personal token", 2026-10-17), so this uses the public dRPC endpoint (no key), still through
pmr.http.request_json for provenance. Decodes ERC-20 Transfer logs in each DEPOSIT/WITHDRAWAL
transaction to see which token moved, from where and to where, and reads the wallet's
current balance of that token. A shared funder/bridge is NOT evidence of common ownership.
Output: data/derived/mintblade_cashflow_transfers.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pmr.http import request_json  # noqa: E402

RPC = "https://polygon.drpc.org"
D = Path(__file__).resolve().parents[2] / "data" / "derived"
W = "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def rpc(method, params, cache=False):
    j = request_json(RPC, method="POST", json_body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                     source="polygon-drpc", cache=cache)
    if "error" in j:
        raise RuntimeError(j["error"])
    return j["result"]


def main():
    a = pd.read_parquet(D / "mintblade_activity_exdw_false.parquet")
    cf = a[a.type.isin(["DEPOSIT", "WITHDRAWAL"])]
    rows = []
    for tx in sorted(set(cf.transaction_hash)):
        r = rpc("eth_getTransactionReceipt", [tx], cache=True)
        for lg in r["logs"]:
            if lg["topics"][0] == TRANSFER and len(lg["topics"]) == 3:
                frm, to = "0x" + lg["topics"][1][-40:], "0x" + lg["topics"][2][-40:]
                if W[2:] in (frm[2:], to[2:]):
                    rows.append({"tx": tx, "block": int(r["blockNumber"], 16), "tx_from": r["from"], "tx_to": r["to"],
                                 "token": lg["address"], "from": frm, "to": to, "amount_raw": int(lg["data"], 16)})
    df = pd.DataFrame(rows)
    df.to_parquet(D / "mintblade_cashflow_transfers.parquet", index=False)
    pd.set_option("display.width", 250)
    print(df.groupby(["token"]).size())
    df["dir"] = df.apply(lambda r: "in" if r["to"] == W else "out", axis=1)
    print(df.groupby(["token", "dir", "from", "to"]).agg(n=("tx", "size"), amt=("amount_raw", "sum")).to_string())
    print(df.groupby(["dir", "tx_from"]).size().to_string())
    # current balances of every token seen
    for tok in df.token.unique():
        data = "0x70a08231" + W[2:].rjust(64, "0")
        bal = rpc("eth_call", [{"to": tok, "data": data}, "latest"])
        dec = rpc("eth_call", [{"to": tok, "data": "0x313ce567"}, "latest"])
        print("balance", tok, int(bal, 16), "decimals", int(dec, 16) if dec != "0x" else None)


def deposit_sources():
    """First-hop USDC.e source wrapped into pUSD inside each DEPOSIT tx (cached receipts)."""
    a = pd.read_parquet(D / "mintblade_activity_exdw_false.parquet")
    pusd, usdce = "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb", "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"
    rows = []
    for tx in sorted(set(a[a.type == "DEPOSIT"].transaction_hash)):
        r = rpc("eth_getTransactionReceipt", [tx], cache=True)
        for lg in r["logs"]:
            if lg["topics"][0] == TRANSFER and len(lg["topics"]) == 3 and lg["address"] == usdce:
                frm, to = "0x" + lg["topics"][1][-40:], "0x" + lg["topics"][2][-40:]
                if to in (pusd, W):
                    rows.append({"tx": tx, "src": frm, "to": to, "amount": int(lg["data"], 16) / 1e6})
    df = pd.DataFrame(rows)
    print(df.groupby(["src", "to"]).amount.agg(["size", "sum"]).to_string())
    for src in df.groupby("src").amount.sum().sort_values().index[-2:]:
        print(src, "code:", rpc("eth_getCode", [src, "latest"]))  # 0xef0100<addr> = EIP-7702 delegated EOA


if __name__ == "__main__":
    main()
    deposit_sources()
