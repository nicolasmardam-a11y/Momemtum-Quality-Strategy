"""Step 2 of the linkage study: every token transfer into / out of the three account wallets and their
owner EOAs (and, with `hop2`, of the first-hop funding addresses), 2026-04-20 .. head.

Queries (no token filter, so every ERC-20 / ERC-721 / ERC-1155 contract is covered):
  ERC-20/721  Transfer(from, to, value)                  topic1 in S  and  topic2 in S
  ERC-1155    TransferSingle / TransferBatch(op, from, to) topic2 in S  and  topic3 in S
in 100k-block windows on the tenderly public gateway. Windows that end >= 50k blocks below head are
cached (immutable), so the scan is resumable: rerun the same command after a timeout.

Usage (from analyses/wallets/):
  python linkage_02_transfers.py selftest      # cross-check tenderly vs quiknode/pocket on one window
  python linkage_02_transfers.py scan          # S = 3 wallets + 3 owner EOAs
  python linkage_02_transfers.py hop2          # S = funding counterparties found by `scan`
Outputs: data/derived/linkage_transfers_<set>.parquet
"""
from __future__ import annotations

import sys
import time

import pandas as pd
import requests

from linkage_common import (DERIVED, TRANSFER, TRANSFER_BATCH, TRANSFER_SINGLE, WALLETS, archive, label, pad, rpc,
                            unpad)

START = 85_761_578  # first block at/after 2026-04-20T00:00Z (linkage_01 block_at)
STEP = 100_000


def addr_set(which: str) -> dict[str, str]:
    if which == "scan":
        ctl = pd.read_parquet(DERIVED / "linkage_wallet_controllers.parquet")
        s = {r.wallet: f"{r.label}:wallet" for r in ctl.itertuples()}
        s.update({r.owner: f"{r.label}:owner" for r in ctl.itertuples()})
        return s
    if which == "hop2":
        # first-hop funding addresses from linkage_02b: the EIP-7702 deposit accounts that wrapped stablecoins
        # into pUSD for a wallet, and legacy Polymarket Proxy Wallets (45-byte EIP-1167 clones) that sent pUSD in
        d = pd.read_parquet(DERIVED / "linkage_deposit_sources.parquet").dropna(subset=["source"])
        keep = d[d.source_code.str.startswith("EIP-7702 EOA -> 0xe6cae83b") | (d.source_code == "contract(45B)")]
        return {a: "hop2:" + "|".join(sorted(set(g.label))) for a, g in keep.groupby("source")}
    raise SystemExit(which)


def scan(which: str) -> None:
    S = addr_set(which)
    pads = [pad(a) for a in S]
    head = int(rpc("eth_blockNumber", []), 16)
    rows = []
    t0 = time.time()
    for b0 in range(START, head + 1, STEP):
        b1 = min(b0 + STEP - 1, head)
        cache = b1 < head - 50_000
        qs = [("erc20", "out", [TRANSFER, pads]), ("erc20", "in", [TRANSFER, None, pads]),
              ("erc1155", "out", [[TRANSFER_SINGLE, TRANSFER_BATCH], None, pads]),
              ("erc1155", "in", [[TRANSFER_SINGLE, TRANSFER_BATCH], None, None, pads])]
        for kind, d, topics in qs:
            logs = archive("eth_getLogs", [{"fromBlock": hex(b0), "toBlock": hex(b1), "topics": topics}], cache=cache)
            for lg in logs:
                tp = lg["topics"]
                if kind == "erc20":
                    if len(tp) < 3:
                        continue
                    frm, to = unpad(tp[1]), unpad(tp[2])
                    amt_raw = int(lg["data"], 16) if len(tp) == 3 and lg["data"] not in ("0x", "") else None
                    tok_id = int(tp[3], 16) if len(tp) == 4 else None
                else:
                    frm, to = unpad(tp[2]), unpad(tp[3])
                    dd = lg["data"][2:]
                    if tp[0] == TRANSFER_SINGLE:
                        tok_id, amt_raw = int(dd[:64], 16), int(dd[64:128], 16)
                    else:
                        tok_id, amt_raw = None, None  # batch: ids/values arrays, not decoded here
                me = frm if d == "out" else to
                rows.append({"kind": kind, "dir": d, "set_addr": me, "set_label": S.get(me), "block": int(lg["blockNumber"], 16),
                             "tx": lg["transactionHash"], "log_index": int(lg["logIndex"], 16), "contract": lg["address"].lower(),
                             "from": frm, "to": to, "counterparty": to if d == "out" else frm, "amount_raw": amt_raw,
                             "token_id": tok_id, "is_batch": tp[0] == TRANSFER_BATCH})
        if (b0 - START) // STEP % 10 == 0:
            print(which, b0, len(rows), f"{time.time() - t0:.0f}s", flush=True)
    df = pd.DataFrame(rows).drop_duplicates(["tx", "log_index", "dir"])
    # decimals for erc20 amounts (stablecoins 6; look up others)
    dec = {}
    for c in df[df.kind == "erc20"].contract.unique():
        try:
            r = rpc("eth_call", [{"to": c, "data": "0x313ce567"}, "latest"])
            dec[c] = int(r, 16) if r not in ("0x", "") else None
        except RuntimeError:
            dec[c] = None
    df["decimals"] = df.contract.map(dec)
    df["amount"] = [a / 10 ** d if (a is not None and d is not None and k == "erc20") else (a / 1e6 if a is not None else None)
                    for a, d, k in zip(df.amount_raw, df.decimals, df.kind)]
    df["token_sym"] = df.contract.map(lambda c: label(c).split(" ")[0] if label(c) else c)
    df["counterparty_label"] = df.counterparty.map(label)
    df["amount_raw"] = df.amount_raw.astype("string")  # can exceed int64
    df["token_id"] = df.token_id.astype("string")
    df.to_parquet(DERIVED / f"linkage_transfers_{which}.parquet", index=False)
    print("wrote", which, df.shape, f"{time.time() - t0:.0f}s")


def selftest() -> None:
    """Same query on three providers for one 10k window; they must agree."""
    S = addr_set("scan")
    q = {"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
         "params": [{"fromBlock": hex(88_700_000), "toBlock": hex(88_709_999), "topics": [TRANSFER, None, [pad(a) for a in S]]}]}
    for u in ["https://polygon.gateway.tenderly.co", "https://poly.api.pocket.network", "https://rpc-mainnet.matic.quiknode.pro"]:
        r = requests.post(u, json=q, timeout=90).json().get("result")
        print(u, None if r is None else (len(r), sorted({x["transactionHash"] for x in r})[:3]))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    selftest() if cmd == "selftest" else scan(cmd)
