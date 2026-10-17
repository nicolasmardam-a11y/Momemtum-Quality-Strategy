"""Reviewer: decode the V2 Order structs signed by the three wallets from cached fill-tx calldata.

Order layout (linkage_11 docstring, VERIFIED there by signature recovery): salt, maker, signer, tokenId, makerAmount,
takerAmount, side, signatureType, timestamp, metadata, builder, signature. The `timestamp` field is the order's
creation time as signed by the trader's client. This lets us (a) date each decision to the second (independent of
fill time), (b) test whether resting orders survived the scheduled kick-off (markets have clearBookOnStart=true).
Uses only cached eth_getTransactionByHash responses (cache=True). Output: data/derived/review_order_times.parquet
"""
from __future__ import annotations
import sys
sys.path.insert(0, "analyses/wallets")
import pandas as pd
from linkage_common import archive  # noqa: E402

W = {"mintblade": "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb",
     "GRIMDRIP": "0x3f87d51f27ba6e19ec52aaeebb68559a839c742c",
     "endlessFate": "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2"}
sig = pd.read_parquet("data/derived/linkage_order_signers.parquet")
rows = []
for lab, w in W.items():
    tail = w[2:].lower()
    for tx in sig[sig.label == lab].tx.unique():
        t = archive("eth_getTransactionByHash", [tx])
        b = bytes.fromhex(t["input"][10:])
        words = [b[i:i + 32] for i in range(0, len(b) - len(b) % 32, 32)]
        for i in range(1, len(words) - 11):
            if words[i].hex().endswith(tail) and words[i + 1].hex().endswith(tail) and int.from_bytes(words[i + 6], "big") == 3:
                u = lambda k: int.from_bytes(words[i + k], "big")
                rows.append(dict(label=lab, tx=tx.lower(), salt=str(u(-1)), token_id=str(u(2)), maker_amt=u(3) / 1e6, taker_amt=u(4) / 1e6,
                                 side=u(5), ts_field=u(7)))
d = pd.DataFrame(rows)
mx = d.ts_field.max()
unit = "ms" if mx > 1e12 else "s"
d["order_ts"] = pd.to_datetime(d.ts_field, unit=unit, utc=True)
f = pd.read_parquet("data/derived/review_fills.parquet")
f["tx"] = f.transaction_hash.str.lower()
ft = f.groupby(["wallet", "tx"]).agg(fill_ts=("timestamp", "min"), taker=("taker", "max"), cid=("condition_id", "first"), n=("size", "size")).reset_index()
ft["fill_ts"] = pd.to_datetime(ft.fill_ts, unit="s", utc=True)
d = d.merge(ft, left_on=["label", "tx"], right_on=["wallet", "tx"], how="left")
d["rest_s"] = (d.fill_ts - d.order_ts).dt.total_seconds()
d.to_parquet("data/derived/review_order_times.parquet")
print("unit", unit, "orders", len(d), "distinct orders (salt)", d.salt.nunique())
print(d.groupby(["label", "taker"]).agg(n=("tx", "size"), orders=("salt", "nunique"), rest_med=("rest_s", "median"), rest_max=("rest_s", "max"), rest_min=("rest_s", "min")).to_string())
