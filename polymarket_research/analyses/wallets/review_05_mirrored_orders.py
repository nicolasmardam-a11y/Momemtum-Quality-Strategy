"""Reviewer: search for near-simultaneous identical orders across the candidates and two cluster accounts.

Accounts: mintblade, GRIMDRIP, endlessFate, LEEEROYJENKINS, FlickRaw (addresses below; profiles in linkage.md).
A 'mirror' = fills by two different accounts on the same token, same side, same size (+-0.01 sh) and same price,
with block times within 5 s. For each mirror, the signed V2 Order struct is decoded from cached tx calldata
(eth_getTransactionByHash via linkage_common.archive, cache=True) to get the order creation timestamp.
Round-dollar orders ($1k multiples) are flagged, since equal-dollar orders at one price give equal sizes by chance.
Output: data/derived/review_mirrored_orders.parquet
"""
from __future__ import annotations
import itertools, sys
sys.path.insert(0, "analyses/wallets")
import pandas as pd
from pmr import api
from linkage_common import archive  # noqa: E402

A = {"mintblade": "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb", "GRIMDRIP": "0x3f87d51f27ba6e19ec52aaeebb68559a839c742c",
     "endlessFate": "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2", "LEEEROYJENKINS": "0x99aea8f9a64d0142b6b66a4b9d02a2211d45386f",
     "FlickRaw": "0xb0128303d06dfdd2bd6a10d15aac737c83e82ac3"}
fr = []
for n, a in A.items():
    t = pd.DataFrame(api.trades(user=a, taker_only=False, start=1, filter_amount=0, cache=True))
    t["acct"] = n
    fr.append(t)
T = pd.concat(fr, ignore_index=True)
T["size"] = pd.to_numeric(T["size"]); T["price"] = pd.to_numeric(T["price"]); T["timestamp"] = T.timestamp.astype(int)
rows = []
for (x, y) in itertools.combinations(A, 2):
    m = T[T.acct == x].merge(T[T.acct == y], on=["token_id", "side"], suffixes=("_x", "_y"))
    m = m[((m.size_x - m.size_y).abs() < 0.01) & ((m.price_x - m.price_y).abs() < 1e-9) & ((m.timestamp_x - m.timestamp_y).abs() <= 5)]
    for _, r in m.iterrows():
        rows.append(dict(acct_x=x, acct_y=y, title=r.title_x, token_id=r.token_id, size=r.size_x, price=r.price_x,
                         usd=r.size_x * r.price_x, ts_x=r.timestamp_x, ts_y=r.timestamp_y, tx_x=r.transaction_hash_x, tx_y=r.transaction_hash_y))
M = pd.DataFrame(rows)

def order_ts(tx, wallet, size):
    t = archive("eth_getTransactionByHash", [tx])
    b = bytes.fromhex(t["input"][10:]); w = [b[i:i + 32] for i in range(0, len(b) - len(b) % 32, 32)]
    tail = wallet[2:].lower(); out = None
    for i in range(1, len(w) - 11):
        if w[i].hex().endswith(tail) and w[i + 1].hex().endswith(tail):
            u = lambda k: int.from_bytes(w[i + k], "big")
            if abs(u(4) / 1e6 - size) < 0.02 or out is None:
                out = (pd.to_datetime(u(7), unit="ms", utc=True), u(3) / 1e6, u(4) / 1e6, int(t["blockNumber"], 16))
    return out

if len(M):
    M["round_dollar"] = (M.usd % 1000 < 1.5) | (M.usd % 1000 > 998.5)
    for side in ("x", "y"):
        res = [order_ts(tx, A[a], s) for tx, a, s in zip(M[f"tx_{side}"], M[f"acct_{side}"], M["size"])]
        M[f"order_ts_{side}"] = [r[0] if r else pd.NaT for r in res]
        M[f"block_{side}"] = [r[3] if r else None for r in res]
    M["sign_gap_s"] = (M.order_ts_y - M.order_ts_x).dt.total_seconds()
M.to_parquet("data/derived/review_mirrored_orders.parquet")
pd.set_option("display.width", 250)
print(len(M), "mirrored fill pairs;", int((~M.round_dollar).sum()) if len(M) else 0, "non-round-dollar")
if len(M):
    print(M[~M.round_dollar][["acct_x", "acct_y", "title", "size", "price", "usd", "order_ts_x", "order_ts_y", "sign_gap_s", "block_x", "block_y"]].to_string())
    print(M[M.round_dollar].groupby(["acct_x", "acct_y"]).size().to_string())
