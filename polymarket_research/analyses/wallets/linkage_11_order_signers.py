"""Step 11 of the linkage study: who signed the wallets' CLOB orders (owner key or a delegated session signer)?

docs /trading/wallets-auth: "A Deposit Wallet owner can give a separate signer scoped, time-limited trading access."
A shared delegated signer across wallets would be a key-level link, so the orders themselves are checked.
On-chain, each fill tx calls the exchange (matchOrders-style, selector varies) with V2 Order structs
  (salt, maker, signer, tokenId, makerAmount, takerAmount, side, signatureType, timestamp, metadata, builder, signature).
For the candidates, maker == signer == the Deposit Wallet and signatureType == 3 (ERC-1271). The signature is the
Solady nested-EIP-712 (ERC-7739) wrapper: sig(65) | APP_DOMAIN_SEPARATOR(32) | contents(32) | contentsDescription | uint16 len.
The wallet validates ecrecover over
  keccak256(0x1901 | APP_DOMAIN_SEPARATOR | keccak256(abi.encode(TYPED_DATA_SIGN_TYPEHASH, contents, keccak(name),
            keccak(version), chainId, wallet, salt)))
with TYPED_DATA_SIGN_TYPEHASH = keccak("TypedDataSign(" contentsName " contents,string name,string version,uint256 chainId,
address verifyingContract,bytes32 salt)" contentsType). We recover that key for a sample of orders per wallet and compare it
with owner(). If the recovered key never equals owner(), the wrapper interpretation is wrong and the result is reported as such.
Output: data/derived/linkage_order_signers.parquet
"""
from __future__ import annotations

import sys

import pandas as pd

from linkage_common import DERIVED, WALLETS, archive  # noqa: I001  (puts analyses/mechanics on sys.path for keccak)
from keccak import keccak256  # noqa: E402
from linkage_01_wallet_type import ecrecover, enc_addr, enc_u  # noqa: E402

SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 12  # pass a large number to check every fill tx


def orders_in(inp: str, wallet: str):
    b = bytes.fromhex(inp[10:])
    words = [b[i:i + 32] for i in range(0, len(b) - len(b) % 32, 32)]
    tail = wallet[2:].lower()
    out = []
    for i in range(1, len(words) - 11):
        if words[i].hex().endswith(tail) and words[i + 1].hex().endswith(tail) and int.from_bytes(words[i + 6], "big") == 3:
            start = (i - 1) * 32  # struct head starts at salt
            sig_off = int.from_bytes(words[i + 10], "big")
            p = start + sig_off
            if p + 32 > len(b):
                continue
            ln = int.from_bytes(b[p:p + 32], "big")
            out.append({"maker": "0x" + words[i].hex()[-40:], "signer": "0x" + words[i + 1].hex()[-40:],
                        "sig_type": 3, "sig": b[p + 32:p + 32 + ln]})
    return out


def recover_nested(sig: bytes, wallet: str) -> tuple[str | None, str]:
    if len(sig) < 65 + 64 + 2:
        return None, f"short sig {len(sig)}"
    n = int.from_bytes(sig[-2:], "big")
    desc = sig[129:129 + n]
    if 129 + n + 2 != len(sig):
        return None, f"layout mismatch len={len(sig)} n={n}"
    app_sep, contents = sig[65:97], sig[97:129]
    d = desc.decode("utf-8", "replace")
    # implicit mode: contentsType || contentsName (name = type's struct name, also at the end); explicit: name || type
    if d.endswith(")"):
        name = d.split("(")[0]
        ctype = d
    else:
        name = d[d.rfind(")") + 1:]
        ctype = d[: len(d) - len(name)]
    th = keccak256(f"TypedDataSign({name} contents,string name,string version,uint256 chainId,address verifyingContract,bytes32 salt){ctype}".encode())
    st = keccak256(th + contents + keccak256(b"DepositWallet") + keccak256(b"1") + enc_u(137) + enc_addr(wallet) + bytes(32))
    dg = keccak256(b"\x19\x01" + app_sep + st)
    v = sig[64]
    return ecrecover(dg, v, int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:64], "big")), name


def main() -> None:
    ctl = pd.read_parquet(DERIVED / "linkage_wallet_controllers.parquet").set_index("label")
    s = pd.read_parquet(DERIVED / "linkage_transfers_scan.parquet")
    rows = []
    for lab, w in WALLETS.items():
        x = s[(s.set_addr == w) & (s.dir == "out") & (s.counterparty_label.fillna("").str.contains("Exchange"))]
        txs = x.drop_duplicates("tx").sort_values("block")
        txs = txs.iloc[:: max(1, len(txs) // SAMPLE)].head(SAMPLE)
        for tx in txs.tx:
            t = archive("eth_getTransactionByHash", [tx])
            for o in orders_in(t["input"], w):
                rec, name = recover_nested(o["sig"], w)
                rows.append({"label": lab, "tx": tx, "selector": t["input"][:10], "maker": o["maker"], "order_signer_field": o["signer"],
                             "sig_len": len(o["sig"]), "contents_name": name, "recovered": rec, "owner": ctl.loc[lab, "owner"],
                             "matches_owner": rec == ctl.loc[lab, "owner"]})
    df = pd.DataFrame(rows)
    df.to_parquet(DERIVED / "linkage_order_signers.parquet", index=False)
    pd.set_option("display.width", 220)
    print(df.groupby("label").agg(orders=("tx", "size"), txs=("tx", "nunique"), match_owner=("matches_owner", "sum"),
                                  distinct_recovered=("recovered", "nunique"), sig_len=("sig_len", "median"),
                                  contents=("contents_name", "first")).to_string())
    rec = df.groupby("recovered").label.nunique()
    print("recovered keys used by >1 wallet:", rec[rec > 1].to_dict())


if __name__ == "__main__":
    main()
