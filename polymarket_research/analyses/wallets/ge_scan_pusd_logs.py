"""Scan pUSD Transfer logs FROM (and TO) the three wallets over 2026-05-31..2026-07-20 via the free
QuikNode public Polygon endpoint (10,000-block cap per eth_getLogs). Chunks are cached (immutable
history), so the scan is resumable. Purpose: locate pUSD outflows that /v2/activity does not label
as WITHDRAWAL (endlessFate cash reconciliation gap). Output: data/derived/ge_pusd_logs.parquet
Usage: python analyses/wallets/ge_scan_pusd_logs.py [from|to]
"""
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr.http import request_json  # noqa: E402
U = "https://rpc-mainnet.matic.quiknode.pro"
PUSD = "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB"
T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
W = {"0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2": "endlessFate", "0x3f87d51f27ba6e19ec52aaeebb68559a839c742c": "GRIMDRIP",
     "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb": "mintblade"}
PADS = ["0x" + "0" * 24 + a[2:] for a in W]
START, END, STEP = 87_650_000, 90_540_000, 10_000
direction = sys.argv[1] if len(sys.argv) > 1 else "from"
rows = []
for b in range(START, END, STEP):
    topics = [T, PADS] if direction == "from" else [T, None, PADS]
    j = request_json(U, method="POST", source="polygon", cache=True, timeout=90,
                     json_body={"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
                                "params": [{"address": PUSD, "fromBlock": hex(b), "toBlock": hex(b + STEP - 1), "topics": topics}]})
    if "error" in j:
        raise RuntimeError(j["error"])
    for lg in j["result"]:
        frm, to = "0x" + lg["topics"][1][-40:], "0x" + lg["topics"][2][-40:]
        rows.append({"block": int(lg["blockNumber"], 16), "tx": lg["transactionHash"], "from": frm, "to": to,
                     "amount": int(lg["data"], 16) / 1e6, "wallet": W.get(frm if direction == "from" else to)})
    if (b - START) // STEP % 20 == 0:
        print(b, len(rows), flush=True)
pd.DataFrame(rows).to_parquet(ROOT / "data" / "derived" / f"ge_pusd_logs_{direction}.parquet", index=False)
print("done", len(rows))
