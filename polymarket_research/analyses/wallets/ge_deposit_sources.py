"""For every DEPOSIT tx, find the address whose USDC.e (or USDC) was wrapped into pUSD for the wallet
(the 'source' of the deposit), and for every WITHDRAWAL tx the final recipient of the unwrapped USDC.e.
Uses cached receipts written by ge_onchain_flows.py. Output: data/derived/ge_fund_sources.parquet
"""
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr.http import request_json  # noqa: E402
T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
PUSD = "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb"
ONRAMP = "0x93070a847efef7f70739046a929d47a521f5b8ee"
OUT = ROOT / "data" / "derived"
f = pd.read_parquet(OUT / "ge_fund_flows.parquet")
rows = []
for (lab, tx, typ), _ in f.groupby(["label", "tx", "api_type"]):
    r = request_json("https://polygon.drpc.org", method="POST", source="polygon", cache=True,
                     json_body={"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionReceipt", "params": [tx]})["result"]
    for lg in r["logs"]:
        if lg["topics"][0] != T or len(lg["topics"]) != 3:
            continue
        frm, to = "0x" + lg["topics"][1][-40:], "0x" + lg["topics"][2][-40:]
        amt = int(lg["data"], 16) / 1e6
        tok = lg["address"].lower()
        if typ == "DEPOSIT" and tok != PUSD and to in (PUSD, ONRAMP):
            rows.append({"label": lab, "tx": tx, "type": typ, "source_or_dest": frm, "amount": amt, "bundler": r["from"], "token": tok})
        if typ == "DEPOSIT" and tok != PUSD and to == f[f.label == lab].iloc[0].get("to", None):
            pass
    if typ == "DEPOSIT" and not any(x["tx"] == tx for x in rows):
        # direct USDC.e transfer into the wallet (no wrap in this tx)
        for lg in r["logs"]:
            if lg["topics"][0] == T and len(lg["topics"]) == 3 and lg["address"].lower() != PUSD:
                rows.append({"label": lab, "tx": tx, "type": typ + "_direct", "source_or_dest": "0x" + lg["topics"][1][-40:],
                             "amount": int(lg["data"], 16) / 1e6, "bundler": r["from"], "token": lg["address"].lower()})
    if typ == "WITHDRAWAL":
        g = f[(f.tx == tx) & (f.direction == "out") & (f.token == "USDC.e")]
        for x in g.itertuples():
            rows.append({"label": lab, "tx": tx, "type": typ, "source_or_dest": x.to, "amount": x.amount, "bundler": r["from"], "token": "usdc.e"})
df = pd.DataFrame(rows)
df.to_parquet(OUT / "ge_fund_sources.parquet", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(df.groupby(["label", "type", "source_or_dest"]).agg(n=("amount", "size"), amt=("amount", "sum")).round(0))
s = df.groupby("source_or_dest").label.agg(lambda x: sorted(set(x)))
print("shared:", s[s.map(len) > 1].to_dict())
