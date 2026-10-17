"""Read whatever eth_getLogs chunks ge_scan_pusd_logs.py has cached so far (data/raw/polygon/cache) and
summarise pUSD outflows FROM endlessFate by counterparty, to locate the $1.6M not labelled WITHDRAWAL.
Output: data/derived/ge_pusd_out_partial.parquet"""
import gzip, json, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
W = {"0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2": "endlessFate", "0x3f87d51f27ba6e19ec52aaeebb68559a839c742c": "GRIMDRIP",
     "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb": "mintblade"}
rows, chunks = [], []
for fn in (ROOT / "data/raw/polygon/cache").glob("*/*.json.gz"):
    with gzip.open(fn, "rt") as f:
        j = json.load(f)
    b = j["meta"].get("body") or {}
    if not isinstance(b, dict) or b.get("method") != "eth_getLogs":
        continue
    prm = b["params"][0]
    if prm.get("address", "").lower() != "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb" or prm["topics"][1] is None:
        continue
    chunks.append(int(prm["fromBlock"], 16))
    for lg in j["body"].get("result") or []:
        frm, to = "0x" + lg["topics"][1][-40:], "0x" + lg["topics"][2][-40:]
        rows.append({"block": int(lg["blockNumber"], 16), "tx": lg["transactionHash"], "from": frm, "to": to,
                     "amount": int(lg["data"], 16) / 1e6, "wallet": W.get(frm)})
df = pd.DataFrame(rows).drop_duplicates(["tx", "from", "to", "amount", "block"])
print("chunks", len(chunks), "blocks", min(chunks), "-", max(chunks) + 9999, "logs", len(df))
df.to_parquet(ROOT / "data/derived/ge_pusd_out_partial.parquet", index=False)
pd.set_option("display.width", 200)
g = df.groupby(["wallet", "to"]).agg(n=("amount", "size"), amt=("amount", "sum"), b0=("block", "min"), b1=("block", "max")).sort_values("amt", ascending=False)
print(g.head(25).to_string())
