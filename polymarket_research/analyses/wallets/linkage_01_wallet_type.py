"""Step 1 of the linkage study: wallet type and controlling key of each account wallet.

For each proxy wallet:
  1. eth_getCode -> classify (Solady ERC-1967 proxy with immutable args = Polymarket Deposit Wallet,
     EIP-1167 clone = legacy Polymarket Proxy Wallet, Gnosis Safe proxy). Parse immutable args
     (factory, walletId).
  2. eth_call owner(), id(), factory(), nonce(), pendingOwner(), paused(), eip712Domain(); try the
     Gnosis Safe getters getOwners()/getThreshold() (expected to revert on a Deposit Wallet).
  3. Every log the wallet contract itself emitted (deployment, upgrades, ownership changes, session
     signer authorisations, batch executions), 2026-04-20 .. head.
  4. Recompute the CREATE2 address from (factory, walletId, initial implementation) as in
     docs /trading/wallets-auth "Derive a Deposit Wallet Address".
  5. Recover the EIP-712 signer of executed batches (ecrecover over the Batch typed data in the
     docs) and compare it with owner().
  6. State of each owner EOA (nonce, code, POL and stablecoin balances).
Outputs: data/derived/linkage_wallet_controllers.parquet, linkage_wallet_events.parquet,
         linkage_batch_signers.parquet
"""
from __future__ import annotations

import json

import pandas as pd

from linkage_common import (ARCHIVE_RPC, DERIVED, TOKENS, WALLETS, archive, keccak256, label, pad, rpc,
                            unpad)

SOLADY_ERC1967_RUNTIME = ("363d3d373d3d363d7f360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
                          "545af43d6000803e6038573d6000fd5b3d6000f3")
IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
BEACON_SLOT = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"
T_UPGRADED = "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b"  # Upgraded(address)
T_OWNERSHIP = "0x8be0079c531659141344cd1fd0a4f28419497f9722a3daafe3b4186f6b6457e0"  # OwnershipTransferred(address,address)
T_INITIALIZED = "0xc7f505b2f371ae2175ee4913f4499e1f2633a7b5936321eed1cdaeb6115181d2"  # Initialized(uint64)
START_BLOCK = 86_000_000   # ~2026-04-20 (block 85,000,000 = 2026-04-02 08:54Z, ~1.5 s blocks); refined below
STEP = 200_000

# ---------------------------------------------------------------- secp256k1 ecrecover (pure Python)
P = 2 ** 256 - 2 ** 32 - 977
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)


def _add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    if p1[0] == p2[0] and (p1[1] + p2[1]) % P == 0:
        return None
    if p1 == p2:
        lam = 3 * p1[0] * p1[0] * pow(2 * p1[1], -1, P) % P
    else:
        lam = (p2[1] - p1[1]) * pow(p2[0] - p1[0], -1, P) % P
    x = (lam * lam - p1[0] - p2[0]) % P
    return x, (lam * (p1[0] - x) - p1[1]) % P


def _mul(k, pt):
    out = None
    while k:
        if k & 1:
            out = _add(out, pt)
        pt = _add(pt, pt)
        k >>= 1
    return out


def ecrecover(digest: bytes, v: int, r: int, s: int) -> str:
    if v >= 27:
        v -= 27
    x = r
    y = pow((x * x * x + 7) % P, (P + 1) // 4, P)
    if y % 2 != v:
        y = P - y
    z = int.from_bytes(digest, "big")
    rinv = pow(r, -1, N)
    q = _add(_mul(s * rinv % N, (x, y)), _mul((-z * rinv) % N, G))
    pub = q[0].to_bytes(32, "big") + q[1].to_bytes(32, "big")
    return "0x" + keccak256(pub)[-20:].hex()


# ---------------------------------------------------------------- ABI helpers
def w(b: bytes, off: int) -> int:
    return int.from_bytes(b[off:off + 32], "big")


def enc_addr(a: str) -> bytes:
    return bytes.fromhex(a[2:].rjust(64, "0"))


def enc_u(x: int) -> bytes:
    return x.to_bytes(32, "big")


def decode_execute(inp: str):
    """execute(Batch[] batches, bytes[] signatures) as observed on the Deposit Wallet Factory (0x0a3c4405)."""
    b = bytes.fromhex(inp[2:])
    sel, d = b[:4].hex(), b[4:]
    ob, os_ = w(d, 0), w(d, 32)
    out = []
    nb = w(d, ob)
    sigs = []
    ns = w(d, os_)
    for i in range(ns):
        so = os_ + 32 + w(d, os_ + 32 + 32 * i)
        ln = w(d, so)
        sigs.append(d[so + 32:so + 32 + ln])
    for i in range(nb):
        base = ob + 32 + w(d, ob + 32 + 32 * i)
        wallet = "0x" + d[base + 12:base + 32].hex()
        nonce, deadline, co = w(d, base + 32), w(d, base + 64), w(d, base + 96)
        cb = base + co
        calls = []
        for j in range(w(d, cb)):
            cbase = cb + 32 + w(d, cb + 32 + 32 * j)
            target = "0x" + d[cbase + 12:cbase + 32].hex()
            value = w(d, cbase + 32)
            do = cbase + w(d, cbase + 64)
            data = d[do + 32:do + 32 + w(d, do)]
            calls.append((target, value, data))
        out.append({"wallet": wallet, "nonce": nonce, "deadline": deadline, "calls": calls,
                    "signature": sigs[i] if i < len(sigs) else None})
    return sel, out


def batch_digest(name: str, version: str, wallet: str, nonce: int, deadline: int, calls) -> bytes:
    th_dom = keccak256(b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
    dom = keccak256(th_dom + keccak256(name.encode()) + keccak256(version.encode()) + enc_u(137) + enc_addr(wallet))
    th_call = keccak256(b"Call(address target,uint256 value,bytes data)")
    th_batch = keccak256(b"Batch(address wallet,uint256 nonce,uint256 deadline,Call[] calls)"
                         b"Call(address target,uint256 value,bytes data)")
    ch = b"".join(keccak256(th_call + enc_addr(t) + enc_u(v) + keccak256(dt)) for t, v, dt in calls)
    st = keccak256(th_batch + enc_addr(wallet) + enc_u(nonce) + enc_u(deadline) + keccak256(ch))
    return keccak256(b"\x19\x01" + dom + st)


def decode_string_tuple(res: str):
    """eip712Domain() -> (bytes1 fields, string name, string version, uint256 chainId, address vc, bytes32 salt, uint256[] ext)."""
    b = bytes.fromhex(res[2:])
    def s(off):
        o = w(b, off)
        return b[o + 32:o + 32 + w(b, o)].decode()
    return {"fields": b[0], "name": s(32), "version": s(64), "chainId": w(b, 96), "verifyingContract": "0x" + b[140:160].hex()}


def call(to, data, block="latest"):
    try:
        return rpc("eth_call", [{"to": to, "data": data}, block])
    except RuntimeError as e:
        return f"REVERT {str(e)[:90]}"


def classify(code: str):
    h = code[2:]
    if h.startswith(SOLADY_ERC1967_RUNTIME):
        args = h[len(SOLADY_ERC1967_RUNTIME):]
        return "Solady ERC-1967 proxy with immutable args (Polymarket Deposit Wallet)", args
    if h.startswith("363d3d373d3d3d363d73"):
        return "EIP-1167 minimal proxy (legacy Polymarket Proxy Wallet pattern)", h[20:60]
    if "a619486e" in h:  # masterCopy() selector in GnosisSafeProxy
        return "Gnosis Safe proxy", ""
    return ("EOA" if h == "" else "other contract"), ""


def initcode_erc1967(impl: str, args: bytes) -> bytes:
    """Solady LibClone.initCodeERC1967(implementation, args): 0x61<runSize> 3d8160233d39 73<impl> 6009 5155f3 <runtime><args>."""
    run = bytes.fromhex(SOLADY_ERC1967_RUNTIME) + args
    return (bytes.fromhex("61") + len(run).to_bytes(2, "big") + bytes.fromhex("3d8160233d3973") + bytes.fromhex(impl[2:])
            + bytes.fromhex("60095155f3") + run)


def create2(factory: str, salt: bytes, init_hash: bytes) -> str:
    return "0x" + keccak256(b"\xff" + bytes.fromhex(factory[2:]) + salt + init_hash)[-20:].hex()


def block_at(ts: int) -> int:
    lo, hi = 80_000_000, int(rpc("eth_blockNumber", []), 16)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        t = int(archive("eth_getBlockByNumber", [hex(mid), False])["timestamp"], 16)
        lo, hi = (mid, hi) if t <= ts else (lo, mid)
    return lo


def main():
    head = int(rpc("eth_blockNumber", []), 16)
    start = block_at(int(pd.Timestamp("2026-04-20", tz="UTC").timestamp()))
    print("start block (2026-04-20T00:00Z):", start, "head:", head)
    end_cached = head - 50_000  # only cache ranges well below head

    rows, events = [], []
    # all logs emitted by the three wallet contracts themselves
    for b0 in range(start, head + 1, STEP):
        b1 = min(b0 + STEP - 1, head)
        logs = archive("eth_getLogs", [{"address": list(WALLETS.values()), "fromBlock": hex(b0), "toBlock": hex(b1)}],
                       cache=b1 < end_cached)
        for lg in logs:
            events.append({"wallet": lg["address"].lower(), "label": label(lg["address"]), "block": int(lg["blockNumber"], 16),
                           "tx": lg["transactionHash"], "topic0": lg["topics"][0],
                           "topics": json.dumps(lg["topics"][1:]), "data": lg["data"]})
    ev = pd.DataFrame(events)
    print("wallet-emitted logs:", len(ev))
    print(ev.groupby(["label", "topic0"]).agg(n=("tx", "size"), first=("block", "min"), last=("block", "max")).to_string())

    for lab, a in WALLETS.items():
        code = rpc("eth_getCode", [a, "latest"])
        kind, args = classify(code)
        r = {"label": lab, "wallet": a, "code_bytes": len(code) // 2 - 1, "kind": kind}
        if args:
            r["arg_factory"], r["arg_wallet_id"] = "0x" + args[24:64], "0x" + args[64 + 24:128]
        r["impl_slot"] = unpad(rpc("eth_getStorageAt", [a, IMPL_SLOT, "latest"]))
        r["beacon_slot"] = unpad(rpc("eth_getStorageAt", [a, BEACON_SLOT, "latest"]))
        for nm, sel in [("owner", "0x8da5cb5b"), ("id", "0xaf640d0f"), ("factory", "0xc45a0155"),
                        ("pendingOwner", "0xe30c3978"), ("nonce", "0xaffed0e0"), ("paused", "0x5c975abb"),
                        ("safe_getOwners", "0xa0e67e2b"), ("safe_getThreshold", "0xe75235b8")]:
            res = call(a, sel)
            r[nm] = (unpad(res) if nm in ("owner", "id", "factory", "pendingOwner") and not res.startswith("REVERT")
                     else (int(res, 16) if res.startswith("0x") else res))
        dom = decode_string_tuple(call(a, "0x84b0196e"))
        r["eip712_name"], r["eip712_version"] = dom["name"], dom["version"]
        # deployment and upgrades from the wallet's own logs
        e = ev[ev.wallet == a].sort_values("block")
        r["first_log_block"] = int(e.block.min()) if len(e) else None
        up = e[e.topic0 == T_UPGRADED]
        r["upgrades"] = json.dumps([(int(x.block), unpad(json.loads(x.topics)[0])) for x in up.itertuples()])
        own = e[e.topic0 == T_OWNERSHIP]
        r["ownership_events"] = json.dumps([(int(x.block), [unpad(t) for t in json.loads(x.topics)]) for x in own.itertuples()])
        r["n_wallet_logs"] = len(e)
        r["wallet_log_topic0s"] = json.dumps(e.topic0.value_counts().to_dict())
        # CREATE2 re-derivation (UUPS variant: initial implementation from the first Upgraded event)
        if args:
            fac, wid = r["arg_factory"], bytes.fromhex(args[64:128])
            salt = keccak256(enc_addr(fac) + wid)
            impl0 = json.loads(r["upgrades"])[0][1] if json.loads(r["upgrades"]) else r["impl_slot"]
            ic = initcode_erc1967(impl0, bytes.fromhex(args))
            r["create2_initial_impl"] = impl0
            r["create2_derived"] = create2(fac, salt, keccak256(ic))
            r["create2_matches"] = r["create2_derived"] == a
        if r["first_log_block"]:
            blk = archive("eth_getBlockByNumber", [hex(r["first_log_block"]), False])
            r["first_log_time"] = pd.to_datetime(int(blk["timestamp"], 16), unit="s", utc=True).isoformat()
        rows.append(r)

    ctl = pd.DataFrame(rows)
    # owner EOA state
    for i, r in ctl.iterrows():
        o = r["owner"]
        ctl.loc[i, "owner_nonce"] = int(rpc("eth_getTransactionCount", [o, "latest"]), 16)
        ctl.loc[i, "owner_code"] = rpc("eth_getCode", [o, "latest"])
        ctl.loc[i, "owner_pol"] = int(rpc("eth_getBalance", [o, "latest"]), 16) / 1e18
        for t, nm in TOKENS.items():
            ctl.loc[i, f"owner_{nm}"] = int(call(t, "0x70a08231" + o[2:].rjust(64, "0")), 16) / 1e6
            ctl.loc[i, f"wallet_{nm}"] = int(call(t, "0x70a08231" + r["wallet"][2:].rjust(64, "0")), 16) / 1e6

    # EIP-712 signer recovery on executed batches: every distinct tx in which the wallet emitted logs
    sig_rows = []
    for lab, a in WALLETS.items():
        dom = ctl.set_index("label").loc[lab]
        txs = ev[ev.wallet == a].drop_duplicates("tx").sort_values("block").tx.tolist()
        for tx in txs:
            t = archive("eth_getTransactionByHash", [tx])
            if t["to"] is None or t["input"][:10] != "0x0a3c4405":
                sig_rows.append({"label": lab, "tx": tx, "to": t["to"], "selector": t["input"][:10], "status": "not execute()"})
                continue
            _, batches = decode_execute(t["input"])
            for bt in batches:
                sg = bt["signature"]
                rec = None
                if sg is not None and len(sg) == 65:
                    dg = batch_digest(dom["eip712_name"], dom["eip712_version"], bt["wallet"], bt["nonce"], bt["deadline"], bt["calls"])
                    rec = ecrecover(dg, sg[64], int.from_bytes(sg[:32], "big"), int.from_bytes(sg[32:64], "big"))
                sig_rows.append({"label": lab, "tx": tx, "block": int(t["blockNumber"], 16), "relayer": t["from"],
                                 "batch_wallet": bt["wallet"], "batch_nonce": bt["nonce"], "n_calls": len(bt["calls"]),
                                 "call_targets": ",".join(c[0] for c in bt["calls"]),
                                 "call_selectors": ",".join(c[2][:4].hex() for c in bt["calls"]),
                                 "sig_len": None if sg is None else len(sg), "recovered_signer": rec,
                                 "owner": dom["owner"], "matches_owner": rec == dom["owner"], "status": "ok"})
    sg = pd.DataFrame(sig_rows)

    ctl.to_parquet(DERIVED / "linkage_wallet_controllers.parquet", index=False)
    ev.to_parquet(DERIVED / "linkage_wallet_events.parquet", index=False)
    sg.to_parquet(DERIVED / "linkage_batch_signers.parquet", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 80)
    print(ctl.T.to_string())
    print(sg.groupby(["label", "status", "matches_owner"], dropna=False).size())
    print(sg.groupby(["label"]).recovered_signer.unique())
    print("relayers per wallet:", sg.groupby("label").relayer.nunique().to_dict(),
          "relayers shared across wallets:", sorted(set.intersection(*[set(g.relayer.dropna()) for _, g in sg.groupby("label")])))
    print("selectors seen in batches:", sg.call_selectors.str.split(",").explode().value_counts().to_dict())


if __name__ == "__main__":
    main()
