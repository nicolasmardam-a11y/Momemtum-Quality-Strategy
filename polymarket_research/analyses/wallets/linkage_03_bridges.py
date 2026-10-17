"""Step 3 of the linkage study: where deposits came from and where withdrawals went, off Polygon.

Withdrawals: each WITHDRAWAL batch ends with a RelayErc20Deposit event on 0x4cd0…bc31 (topic
0x49fed1d0… = keccak('RelayErc20Deposit(address,address,uint256,bytes32)'), verified in this study),
so the bridge is Relay. Relay's public API (GET /requests/v2?user=<sender>, deprecated but live until
2026-11-24; /v3 needs a key) returns each request's destination chain, recipient and tx hashes.
Deposits: the per-wallet Polymarket bridge deposit address (docs /trading/bridge/deposit: "Each address
is unique to your wallet") is queried on the public Polymarket bridge GET /status/<address> and on
Relay (the bridge forwards cross-chain deposits through Relay, user = deposit address).
All raw responses are stored by pmr.http. Read-only GETs only; POST /deposit or /withdraw are NOT called.
Outputs: data/derived/linkage_relay_requests.parquet, linkage_bridge_status.parquet
"""
from __future__ import annotations

import sys
import time

import pandas as pd

from linkage_common import DERIVED, WALLETS, request_json

RELAY = "https://api.relay.link/requests/v2"
BRIDGE = "https://bridge.polymarket.com/status/"


def relay_requests(user: str) -> list[dict]:
    out, cont = [], None
    while True:
        p = {"user": user, "limit": 50, "sortBy": "createdAt"}
        if cont:
            p["continuation"] = cont
        for attempt in range(8):  # Relay throttles the deprecated v2 route; back off and retry (cached when done)
            try:
                j = request_json(RELAY, p, source="relay", cache=True, retries=1)
                break
            except RuntimeError as e:
                if "429" not in str(e) or attempt == 7:
                    raise
                time.sleep(60 * (attempt + 1))
        time.sleep(3)
        out += j.get("requests") or []
        cont = j.get("continuation")
        if not cont or not j.get("requests"):
            return out


def flat(r: dict, queried: str) -> dict:
    d = r.get("data") or {}
    md = d.get("metadata") or {}
    ci, co = md.get("currencyIn") or {}, md.get("currencyOut") or {}
    ins, outs = d.get("inTxs") or [], d.get("outTxs") or []
    return {
        "queried_user": queried, "id": r["id"], "status": r["status"], "user": (r.get("user") or "").lower(),
        "recipient": (r.get("recipient") or "").lower(), "sender_md": (md.get("sender") or "").lower(),
        "created_at": r.get("createdAt"), "in_chain": ins[0].get("chainId") if ins else None,
        "in_hash": ins[0].get("hash") if ins else None, "in_ts": ins[0].get("timestamp") if ins else None,
        "in_from": ((ins[0].get("data") or {}).get("from") or "").lower() if ins else None,
        "out_chain": outs[0].get("chainId") if outs else None, "out_hash": outs[0].get("hash") if outs else None,
        "out_ts": outs[0].get("timestamp") if outs else None, "n_out": len(outs),
        "cur_in": (ci.get("currency") or {}).get("symbol"), "chain_in": (ci.get("currency") or {}).get("chainId"),
        "amt_in": float(ci.get("amountFormatted") or "nan"),
        "cur_out": (co.get("currency") or {}).get("symbol"), "chain_out": (co.get("currency") or {}).get("chainId"),
        "amt_out": float(co.get("amountFormatted") or "nan"), "fail_reason": d.get("failReason"),
        "refund_fail_reason": d.get("refundFailReason"),
    }


def bridge_status(addr: str) -> list[dict]:
    out, cur = [], None
    while True:
        p = {"limit": 100}
        if cur:
            p["cursor"] = cur
        j = request_json(BRIDGE + addr, p, source="bridge", cache=False)
        out += j.get("transactions") or []
        cur = j.get("nextCursor")
        if not cur:
            return out


def main(extra: list[str]) -> None:
    from linkage_02_transfers import addr_set
    users = {**{a: f"{k}:wallet" for k, a in WALLETS.items()},
             **{a: lab.replace("hop2:", "") + ":depsrc" for a, lab in addr_set("hop2").items()}}
    for a in extra:
        users[a.lower()] = "extra"
    rows = []
    for u, lab in users.items():
        rq = relay_requests(u)
        rows += [{**flat(r, u), "queried_label": lab} for r in rq]
        print("relay", lab, u, len(rq), flush=True)
    rel = pd.DataFrame(rows).drop_duplicates(["queried_user", "id"])
    rel.to_parquet(DERIVED / "linkage_relay_requests.parquet", index=False)
    brows = []
    for u, lab in users.items():
        if not lab.endswith("depsrc"):
            continue
        try:
            tx = bridge_status(u)
        except RuntimeError as e:
            print("bridge status fail", u, str(e)[:100])
            continue
        brows += [{"deposit_address": u, "queried_label": lab, **t} for t in tx]
        print("bridge", lab, u, len(tx), flush=True)
    br = pd.DataFrame(brows)
    br.to_parquet(DERIVED / "linkage_bridge_status.parquet", index=False)
    pd.set_option("display.width", 250)
    print(rel.groupby(["queried_label", "status", "in_chain", "out_chain", "recipient"]).agg(n=("id", "size"), amt=("amt_in", "sum")).to_string())
    if len(br):
        print(br.groupby(["queried_label", "fromChainId", "fromTokenAddress", "status"]).agg(n=("txHash", "size")).to_string())


if __name__ == "__main__":
    main(sys.argv[1:])
