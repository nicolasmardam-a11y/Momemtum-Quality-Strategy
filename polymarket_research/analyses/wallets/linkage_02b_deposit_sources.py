"""Step 2b: who actually funded each deposit.

A deposit does not transfer stablecoins to the account wallet: the source sends USDC.e / USDC to the
pUSD contract (CollateralOnramp path) and pUSD is minted to the wallet (Transfer from 0x0). So the
first-hop source is read from the receipt of each mint tx: the stablecoin Transfer whose recipient is
the pUSD contract / Onramp / PermissionedRamp. Direct pUSD transfers in (e.g. endlessFate's legacy
Proxy Wallet migration) are kept as their own rows.
Output: data/derived/linkage_deposit_sources.parquet
"""
from __future__ import annotations

import pandas as pd

from linkage_common import DERIVED, KNOWN, TOKENS, TRANSFER, archive, label, receipt, rpc, unpad

PUSD = "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb"
RAMPS = {PUSD, "0x93070a847efef7f70739046a929d47a521f5b8ee", "0xebc2459ec962869ca4c0bd1e06368272732bcb08"}
ZERO = "0x" + "0" * 40


def code_kind(a: str) -> str:
    c = rpc("eth_getCode", [a, "latest"])
    if c in ("0x", ""):
        return "EOA"
    if c.startswith("0xef0100"):
        return "EIP-7702 EOA -> " + "0x" + c[8:48]
    return f"contract({len(c) // 2 - 1}B)"


def main() -> None:
    t = pd.read_parquet(DERIVED / "linkage_transfers_scan.parquet")
    inn = t[(t.kind == "erc20") & (t.dir == "in") & (t.token_sym == "pUSD")]
    rows = []
    for x in inn[inn.counterparty != ZERO].itertuples():
        rows.append({"label": x.set_label.split(":")[0], "tx": x.tx, "block": x.block, "kind": "direct pUSD in",
                     "source": x.counterparty, "amount": x.amount, "token": "pUSD", "tx_from": None})
    mints = inn[inn.counterparty == ZERO].groupby(["set_label", "tx"]).agg(block=("block", "first"), minted=("amount", "sum"))
    for (set_label, txh), x in mints.iterrows():  # one pass per mint tx (a tx can hold several mints)
        x = x.to_dict()
        x.update({"tx": txh, "set_label": set_label, "amount": x["minted"]})
        x = pd.Series(x)
        r = receipt(x.tx)
        tx = archive("eth_getTransactionByHash", [x.tx])
        w_addr = t[t.set_label == set_label].set_addr.iloc[0]
        # Deposits are often bundled (ERC-4337 handleOps carrying several users' deposits in one tx), so pair
        # each pUSD mint to this wallet with the nearest preceding stablecoin -> ramp transfer of the same amount.
        wraps = []  # (logIndex, from, amount, token)
        for lg in r["logs"]:
            li = int(lg["logIndex"], 16)
            if lg["topics"][0] != TRANSFER or len(lg["topics"]) != 3:
                continue
            frm, to, amt = unpad(lg["topics"][1]), unpad(lg["topics"][2]), int(lg["data"], 16)
            a = lg["address"].lower()
            if a in TOKENS and a != PUSD and to in RAMPS:
                wraps.append((li, frm, amt, TOKENS[a]))
            if a == PUSD and frm == ZERO and to == w_addr:
                cand = [wr for wr in wraps if wr[0] < li and wr[2] == amt]
                src = cand[-1] if cand else (None, None, None, None)
                rows.append({"label": set_label.split(":")[0], "tx": x.tx, "block": x.block, "kind": "mint (wrap)",
                             "source": src[1], "amount": amt / 1e6, "minted": amt / 1e6, "token": src[3],
                             "tx_from": tx["from"], "tx_to": tx["to"], "bundled_wraps_in_tx": len(wraps)})
    df = pd.DataFrame(rows)
    kinds = {a: code_kind(a) for a in df.source.dropna().unique()}
    df["source_code"] = df.source.map(kinds)
    df["source_label"] = df.source.map(lambda a: label(a) if isinstance(a, str) else "")
    df.to_parquet(DERIVED / "linkage_deposit_sources.parquet", index=False)
    pd.set_option("display.width", 250)
    print(df.groupby(["label", "kind", "source", "source_code", "token"], dropna=False)
          .agg(n=("tx", "size"), amt=("amount", "sum"), first=("block", "min"), last=("block", "max")).round(2).to_string())
    s = df.dropna(subset=["source"]).groupby("source").label.agg(lambda v: sorted(set(v)))
    print("sources shared by >1 wallet:", s[s.map(len) > 1].to_dict())


if __name__ == "__main__":
    main()
