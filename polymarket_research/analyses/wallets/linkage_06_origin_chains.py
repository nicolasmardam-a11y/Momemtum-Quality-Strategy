"""Step 6 of the linkage study: follow the money off Polygon (Ethereum and BNB Chain).

Each candidate deposits through its own Polymarket bridge deposit address (EIP-7702 EOA; same address on
every EVM chain): mintblade 0xb4c3…3a41, GRIMDRIP 0x6e39…d17d, endlessFate 0x8599…8945. Relay requests
(linkage_03) show these addresses were funded on Ethereum (USDC) and BNB Chain (USDC), and that withdrawals
went to a few recipients on Ethereum / BNB Chain / Polygon. The question here: who sent the funds to the
deposit addresses on the origin chains, and do withdrawal recipients of one candidate ever fund another?

Ethereum: eth_getLogs (Transfer, any token, topic-filtered) on the free tenderly gateway in 50k-block windows,
          2026-05-20 .. 2026-09-15, for every deposit address and withdrawal recipient (in and out).
BNB Chain: no free archive getLogs over large ranges was found (dataseed: 'limit exceeded'; drpc free: refused;
          publicnode: archive token needed). bsc-mainnet.gateway.tatum.io serves getLogs over <=100 blocks, so
          only the 150-250 blocks before each Relay origin tx are scanned (the deposit address is swept seconds after
          it is funded), plus ~600 blocks after each BNB-chain withdrawal delivery (5 requests/minute limit).
Counterparty state (nonce, code) is read at head; Blockscout (eth.blockscout.com, public, no key) is queried for
address metadata (name / public tags) only.
Usage: python linkage_06_origin_chains.py eth | bsc | summary
Outputs: data/derived/linkage_origin_eth.parquet, linkage_origin_bsc.parquet, linkage_origin_counterparties.parquet
"""
from __future__ import annotations

import sys
import time

import pandas as pd

from linkage_common import DERIVED, TRANSFER, pad, request_json, unpad

ETH_RPC = "https://mainnet.gateway.tenderly.co"
ETH_RPC2 = "https://eth.drpc.org"
BSC_RCPT = "https://bsc-dataseed.bnbchain.org"
BSC_LOGS = "https://bsc-mainnet.gateway.tatum.io"
BLOCKSCOUT = "https://eth.blockscout.com/api/v2/addresses/"

DEP = {"0xb4c3bd5ad2b6fe14ac233fc40289b7798cc43a41": "mintblade:dep",
       "0x6e396ef61f2a740d48ca403626e826b15bbfd17d": "GRIMDRIP:dep",
       "0x8599cbdb95eaca8dee899589869283724b678945": "endlessFate:dep"}
EVM_TOKENS = {
    1: {"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": ("USDC", 6), "0xdac17f958d2ee523a2206206994597c13d831ec7": ("USDT", 6)},
    56: {"0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d": ("USDC", 18), "0x55d398326f99059ff775485246999027b3197955": ("USDT", 18)},
}
ETH_FROM, ETH_TO = 25_130_000, 25_990_000  # 2026-05-19 14:55Z (verified) .. ~2026-09-14 (12 s blocks)


def rpc(url, method, params, *, cache=True, source="ethereum"):
    j = request_json(url, method="POST", source=source, cache=cache, timeout=120, retries=4,
                     json_body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in j:
        raise RuntimeError(f"{method} {url}: {str(j['error'])[:200]}")
    return j["result"]


def recipients() -> dict:
    r = pd.read_parquet(DERIVED / "linkage_relay_requests.parquet")
    w = r[r.queried_label.str.endswith(":wallet")]
    out = {}
    for (lab, ch, rc), g in w.groupby(["queried_label", "out_chain", "recipient"]):
        if rc.startswith("0x") and len(rc) == 42:
            out.setdefault(rc, set()).add(f"{lab.split(':')[0]}:wdr")
    return {a: "|".join(sorted(v)) for a, v in out.items()}


def decode(lg, chain, set_addr, set_label, direction):
    tok = EVM_TOKENS[chain].get(lg["address"].lower())
    raw = int(lg["data"][:66], 16) if lg["data"] not in ("0x", "") else None
    return {"chain": chain, "set_addr": set_addr, "set_label": set_label, "dir": direction,
            "block": int(lg["blockNumber"], 16), "tx": lg["transactionHash"], "log_index": int(lg["logIndex"], 16),
            "contract": lg["address"].lower(), "from": unpad(lg["topics"][1]), "to": unpad(lg["topics"][2]),
            "token": tok[0] if tok else None, "amount": raw / 10 ** tok[1] if (tok and raw is not None) else None}


def eth() -> None:
    S = {**DEP, **recipients()}
    rows = []
    for a, lab in S.items():
        for direction, topics in (("in", [TRANSFER, None, pad(a)]), ("out", [TRANSFER, pad(a)])):
            for s in range(ETH_FROM, ETH_TO, 50_000):
                e = min(s + 49_999, ETH_TO)
                logs = rpc(ETH_RPC, "eth_getLogs", [{"fromBlock": hex(s), "toBlock": hex(e), "topics": topics}],
                           source="ethereum-tenderly")
                rows += [decode(lg, 1, a, lab, direction) for lg in logs if len(lg["topics"]) == 3]
        print("eth", lab, a, sum(r["set_addr"] == a for r in rows), flush=True)
    df = pd.DataFrame(rows).drop_duplicates(["tx", "log_index", "set_addr", "dir"])
    df["counterparty"] = df["from"].where(df.dir == "in", df["to"])
    ts = {}
    for b in sorted(df.block.unique()):
        ts[b] = int(rpc(ETH_RPC, "eth_getBlockByNumber", [hex(b), False], source="ethereum-tenderly")["timestamp"], 16)
    df["ts"] = pd.to_datetime(df.block.map(ts), unit="s", utc=True)
    df.to_parquet(DERIVED / "linkage_origin_eth.parquet", index=False)
    print(df.groupby(["set_label", "dir", "token"], dropna=False).agg(n=("tx", "size"), amt=("amount", "sum")).to_string())


def bsc() -> None:
    r = pd.read_parquet(DERIVED / "linkage_relay_requests.parquet")
    dep = r[r.queried_user.isin(DEP) & (r.in_chain == 56) & r.in_hash.notna()].drop_duplicates("in_hash")
    wdr = r[r.queried_label.str.endswith(":wallet") & (r.out_chain == 56) & r.out_hash.notna()].drop_duplicates("out_hash")
    usdc = "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d"
    rows, done = [], set()

    def scan(addr, lab, b0, b1, direction):
        # 100-block windows aligned to multiples of 100, so neighbouring sweeps share (cached) windows.
        # The free tatum gateway allows 5 requests / minute: sleep after every uncached call.
        for s in range(b0 // 100 * 100, b1 + 1, 100):
            if (addr, s, direction) in done:
                continue
            done.add((addr, s, direction))
            topics = [TRANSFER, None, pad(addr)] if direction == "in" else [TRANSFER, pad(addr)]
            t0 = time.time()
            for attempt in range(12):
                try:
                    logs = rpc(BSC_LOGS, "eth_getLogs", [{"address": usdc, "fromBlock": hex(s), "toBlock": hex(s + 99),
                                                          "topics": topics}], source="bsc-tatum")
                    break
                except RuntimeError as err:
                    if "429" not in str(err) or attempt == 11:
                        raise
                    time.sleep(65)
            if time.time() - t0 > 0.05:
                time.sleep(13)
            rows.extend(decode(lg, 56, addr, lab, direction) for lg in logs)

    for _, q in dep.iterrows():
        rc = rpc(BSC_RCPT, "eth_getTransactionReceipt", [q.in_hash], source="bsc")
        b = int(rc["blockNumber"], 16)
        lab = DEP[q.queried_user]
        scan(q.queried_user, lab, b - 150, b, "in")
        print("bsc dep", lab, q.in_hash[:12], b, len(rows), flush=True)
    for _, q in wdr.iterrows():
        rc = rpc(BSC_RCPT, "eth_getTransactionReceipt", [q.out_hash], source="bsc")
        b = int(rc["blockNumber"], 16)
        lab = q.queried_label.split(":")[0] + ":wdr"
        scan(q.recipient, lab, b - 5, b + 600, "in")
        scan(q.recipient, lab, b - 5, b + 600, "out")
        print("bsc wdr", lab, q.recipient[:12], b, len(rows), flush=True)
    df = pd.DataFrame(rows).drop_duplicates(["tx", "log_index", "set_addr", "dir"])
    if len(df):
        df["counterparty"] = df["from"].where(df.dir == "in", df["to"])
    df.to_parquet(DERIVED / "linkage_origin_bsc.parquet", index=False)
    print(df.groupby(["set_label", "dir", "token"], dropna=False).agg(n=("tx", "size"), amt=("amount", "sum")).to_string())


def summary() -> None:
    e = pd.read_parquet(DERIVED / "linkage_origin_eth.parquet")
    b = pd.read_parquet(DERIVED / "linkage_origin_bsc.parquet")
    df = pd.concat([e, b], ignore_index=True)
    stable = df[df.token.notna()]
    g = stable.groupby(["chain", "counterparty"]).agg(labels=("set_label", lambda x: "|".join(sorted(set(x)))),
                                                      n=("tx", "size"), amt=("amount", "sum")).reset_index()
    meta = []
    for _, x in g.iterrows():
        url = ETH_RPC if x.chain == 1 else BSC_RCPT
        src = "ethereum-tenderly" if x.chain == 1 else "bsc"
        try:
            nonce = int(rpc(url, "eth_getTransactionCount", [x.counterparty, "latest"], cache=False, source=src), 16)
            code = rpc(url, "eth_getCode", [x.counterparty, "latest"], cache=False, source=src)
        except RuntimeError:
            nonce, code = None, None
        name, tags = None, None
        if x.chain == 1:
            try:
                j = request_json(BLOCKSCOUT + x.counterparty, source="blockscout-eth", cache=True, retries=3)
                name = j.get("name")
                tags = ",".join(t.get("display_name", "") for t in ((j.get("metadata") or {}).get("tags") or []))
            except RuntimeError:
                pass
        meta.append({"nonce": nonce, "code_len": (len(code) - 2) // 2 if code else None,
                     "delegated_7702": bool(code and code.startswith("0xef0100")), "bs_name": name, "bs_tags": tags})
    g = pd.concat([g, pd.DataFrame(meta)], axis=1)
    g.to_parquet(DERIVED / "linkage_origin_counterparties.parquet", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    print(g.sort_values("amt", ascending=False).head(60).to_string())
    multi = g[g["labels"].str.split("|").map(lambda v: len({s.split(':')[0] for s in v}) > 1)]
    print("\ncounterparties touching more than one candidate's deposit address / withdrawal recipient:")
    print(multi.to_string())


if __name__ == "__main__":
    {"eth": eth, "bsc": bsc, "summary": summary}[sys.argv[1]]()
