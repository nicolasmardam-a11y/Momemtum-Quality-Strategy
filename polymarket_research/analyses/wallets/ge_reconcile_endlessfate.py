"""Reconcile endlessFate's cash flows on-chain (2026-06-18 withdrawal window), using cached QuikNode eth_getLogs
chunks (pUSD out of the wallet; USDC.e into the wallet) written by ge_scan_pusd_logs.py / ad-hoc queries.
Finding: /v2/activity omits 5 bridge withdrawals ($3,999,995) and the relayer's 3 immediate refunds ($2,399,997)
of three of them; net omission = $1,599,998 = the cash gap. Output: data/derived/ge_endlessfate_reconciliation.parquet"""
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr.http import request_json  # noqa: E402
U = "https://rpc-mainnet.matic.quiknode.pro"
T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
PUSD, USDCE = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
W = "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2"; PAD = "0x" + "0" * 24 + W[2:]
VAULT = "0xc417fd8e9661c0d2120b64a04bb3278c17e99db1"
OUT = ROOT / "data" / "derived"


def logs(addr, b, topics):
    j = request_json(U, method="POST", source="polygon", cache=True, timeout=90,
                     json_body={"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
                                "params": [{"address": addr, "fromBlock": hex(b), "toBlock": hex(b + 9999), "topics": topics}]})
    return j["result"]


rows = []
for b in (88710000, 88720000):
    for l in logs(USDCE, b, [T, None, PAD]):
        fr = "0x" + l["topics"][1][-40:]
        if fr != VAULT:
            rows.append({"block": int(l["blockNumber"], 16), "tx": l["transactionHash"], "kind": "USDC.e in (relayer)", "counterparty": fr, "amount": int(l["data"], 16) / 1e6})
pad3 = ["0x" + "0" * 24 + a[2:] for a in [W, "0x3f87d51f27ba6e19ec52aaeebb68559a839c742c", "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb"]]
for b in (88720000,):
    for l in logs(PUSD, b, [T, pad3]):
        if "0x" + l["topics"][1][-40:] == W and "0x" + l["topics"][2][-40:] == PUSD.lower():
            rows.append({"block": int(l["blockNumber"], 16), "tx": l["transactionHash"], "kind": "pUSD unwrap (withdrawal)", "counterparty": PUSD.lower(), "amount": int(l["data"], 16) / 1e6})
df = pd.DataFrame(rows).sort_values("block")
act = pd.read_parquet(OUT / "ge_activity_incl_dw.parquet")
act = act[act.label == "endlessFate"]
df["in_api"] = df.tx.isin(set(act.transaction_hash))
df.to_parquet(OUT / "ge_endlessfate_reconciliation.parquet", index=False)
pd.set_option("display.width", 200)
print(df.to_string())
print(df.groupby(["kind", "in_api"]).amount.agg(["size", "sum"]))
