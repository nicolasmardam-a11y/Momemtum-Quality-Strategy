"""Decode ERC-20 Transfer logs in the receipts of every DEPOSIT / WITHDRAWAL transaction that
/v2/activity (exclude_deposits_withdrawals=false) reports for the three wallets.

publicnode refuses historical receipts ('archive requests require a personal token'), so this uses
the free public endpoints polygon.drpc.org and rpc-mainnet.matic.quiknode.pro (receipts only;
eth_getLogs ranges are refused on their free tiers). Receipts are immutable -> cache=True.
Output: data/derived/ge_fund_flows.parquet (one row per Transfer log touching a wallet).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr.http import request_json  # noqa: E402

OUT = ROOT / "data" / "derived"
RPCS = ["https://polygon.drpc.org", "https://rpc-mainnet.matic.quiknode.pro"]
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TOKENS = {
    "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb": "pUSD",
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": "USDC.e",
    "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359": "USDC",
}


def receipt(tx: str) -> dict | None:
    for u in RPCS:
        try:
            j = request_json(u, method="POST", source="polygon", cache=True,
                             json_body={"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionReceipt", "params": [tx]})
            if j.get("result"):
                return j["result"]
        except RuntimeError as e:
            print("rpc fail", u, str(e)[:120])
    return None


def main() -> None:
    act = pd.read_parquet(OUT / "ge_activity_incl_dw.parquet")
    dw = act[act.type.isin(["DEPOSIT", "WITHDRAWAL"])]
    wallets = {r.proxy_wallet.lower(): r.label for r in act[["proxy_wallet", "label"]].drop_duplicates().itertuples()}
    rows = []
    for (lab, tx), g in dw.groupby(["label", "transaction_hash"]):
        r = receipt(tx)
        if r is None:
            rows.append({"label": lab, "tx": tx, "status": "no_receipt"})
            continue
        w = g.proxy_wallet.iloc[0].lower()
        for lg in r["logs"]:
            if lg["topics"][0] != TRANSFER or len(lg["topics"]) != 3:
                continue
            frm, to = "0x" + lg["topics"][1][-40:], "0x" + lg["topics"][2][-40:]
            if w not in (frm, to):
                continue
            rows.append({"label": lab, "tx": tx, "block": int(r["blockNumber"], 16), "tx_from": r["from"], "tx_to": r["to"],
                         "token": TOKENS.get(lg["address"].lower(), lg["address"].lower()), "from": frm, "to": to,
                         "amount": int(lg["data"], 16) / 1e6, "direction": "in" if to == w else "out",
                         "api_type": g.type.iloc[0], "api_rows": len(g), "api_usdc": g.usdc_size.sum(),
                         "counterparty": frm if to == w else to,
                         "counterparty_is_candidate": wallets.get(frm if to == w else to)})
    df = pd.DataFrame(rows)
    df.to_parquet(OUT / "ge_fund_flows.parquet", index=False)
    print(df.groupby(["label", "api_type", "token", "direction"]).agg(n=("amount", "size"), amt=("amount", "sum")))


if __name__ == "__main__":
    main()
