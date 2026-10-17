"""Scan pUSD mints (Transfer from 0x0) INTO the three wallets over a block range via the free QuikNode public
endpoint (10,000-block cap). Every Polymarket deposit wraps collateral into pUSD, so mints = deposits.
Chunks are cached (immutable), so runs are resumable and can be split across processes.
Usage: python analyses/wallets/ge_scan_pusd_mints.py START END TAG
Output: data/derived/ge_pusd_mints_<TAG>.parquet"""
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr.http import request_json  # noqa: E402
U = "https://rpc-mainnet.matic.quiknode.pro"
PUSD = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"
T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO = "0x" + "0" * 64
W = {"0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2": "endlessFate", "0x3f87d51f27ba6e19ec52aaeebb68559a839c742c": "GRIMDRIP",
     "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb": "mintblade"}
PADS = ["0x" + "0" * 24 + a[2:] for a in W]
start, end, tag = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
rows = []
for b in range(start, end, 10_000):
    j = request_json(U, method="POST", source="polygon", cache=True, timeout=90,
                     json_body={"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
                                "params": [{"address": PUSD, "fromBlock": hex(b), "toBlock": hex(min(end, b + 10_000) - 1), "topics": [T, ZERO, PADS]}]})
    if "error" in j:
        raise RuntimeError(j["error"])
    for lg in j["result"]:
        to = "0x" + lg["topics"][2][-40:]
        rows.append({"block": int(lg["blockNumber"], 16), "tx": lg["transactionHash"], "to": to, "wallet": W.get(to),
                     "amount": int(lg["data"], 16) / 1e6})
pd.DataFrame(rows, columns=["block", "tx", "to", "wallet", "amount"]).to_parquet(ROOT / "data" / "derived" / f"ge_pusd_mints_{tag}.parquet", index=False)
print("done", tag, len(rows))
