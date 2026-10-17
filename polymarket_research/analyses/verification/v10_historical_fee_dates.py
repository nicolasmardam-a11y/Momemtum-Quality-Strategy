"""Verifier check (read-only): implied taker fee rate actually charged on-chain at a few historical dates, by today's
Gamma feeType. Independent re-implementation (own decoder, own block search, different timestamps from the researcher's).
OrderFilled event: ctf-exchange-v2 src/exchange/interfaces/ITrading.sol. Archive logs: polygon.drpc.org (<=100 blocks).
Token -> condition: Data API /v2/tokens; condition -> feeType: Gamma /markets/keyset (closed=true and false).
"""
import collections
import json
import sys
import time

import requests

from analyses.fees.keccak import keccak256
from pmr import api
from pmr.http import request_json

TOPIC = "0x" + keccak256(b"OrderFilled(bytes32,address,address,uint8,uint256,uint256,uint256,uint256,bytes32,bytes32)").hex()
EXCH = ["0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59"]
RPC = "https://polygon.drpc.org"


def rpc(method, params):
    for i in range(6):
        try:
            r = requests.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=60).json()
            if "result" in r:
                return r["result"]
        except Exception as e:  # noqa
            r = {"error": str(e)}
        time.sleep(2 + i)
    raise RuntimeError(r)


def block_at(ts):
    hi = int(rpc("eth_blockNumber", []), 16)
    lo = hi - 20_000_000
    while lo < hi:
        mid = (lo + hi) // 2
        t = int(rpc("eth_getBlockByNumber", [hex(mid), False])["timestamp"], 16)
        if t < ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def sample(iso, nblocks=300):
    ts = int(time.mktime(time.strptime(iso, "%Y-%m-%dT%H:%M")) - time.timezone)
    b0 = block_at(ts)
    fills = []
    for s in range(b0, b0 + nblocks, 100):
        for lg in rpc("eth_getLogs", [{"fromBlock": hex(s), "toBlock": hex(s + 99), "address": EXCH, "topics": [TOPIC]}]):
            if ("0x" + lg["topics"][3][-40:]).lower() not in EXCH:
                continue  # keep the taker-order event only
            w = [int(lg["data"][2 + i:66 + i], 16) for i in range(0, len(lg["data"]) - 2, 64)]
            side, tok, mk, tk, fee, builder = w[0], str(w[1]), w[2], w[3], w[4], w[5]
            usd, sh = (mk, tk) if side == 0 else (tk, mk)
            usd, sh = usd / 1e6, sh / 1e6
            if sh < 5 or builder != 0:
                continue
            p = usd / sh
            if 0.05 < p < 0.95:
                fills.append((tok, fee / 1e6 / (sh * p * (1 - p))))
    toks = list({t for t, _ in fills})
    cond = {}
    for i in range(0, len(toks), 50):
        for r in request_json(f"{api.DATA}/v2/tokens", {"token_id": ",".join(toks[i:i + 50])}, source="data-api",
                              cache=True).get("data") or []:
            cond[str(r.get("token_id"))] = r.get("condition_id")
    cids = list({c for c in cond.values() if c})
    ft = {}
    for i in range(0, len(cids), 20):
        for closed in ("true", "false"):
            j = request_json(f"{api.GAMMA}/markets/keyset", {"condition_ids": cids[i:i + 20], "closed": closed,
                                                             "limit": 100}, source="gamma", cache=True)
            for m in j.get("markets") or []:
                ft[m["conditionId"]] = m.get("feeType") or ("none" if m.get("feesEnabled") is False else None)
    by = collections.defaultdict(list)
    for t, r in fills:
        by[ft.get(cond.get(t))].append(round(r, 3))
    out = {k: {"n": len(v), "modal": collections.Counter(v).most_common(1)[0][0], "top3": collections.Counter(v).most_common(3)}
           for k, v in by.items() if k}
    return {"iso": iso, "block": b0, "n_fills": len(fills), "by_feeType": out}


res = [sample(x) for x in (sys.argv[1:] or ["2026-04-30T15:00", "2026-05-12T15:00", "2026-07-15T20:00"])]
for r in res:
    print(r["iso"], r["block"], r["n_fills"])
    for k, v in sorted(r["by_feeType"].items(), key=lambda kv: -kv[1]["n"]):
        print("   ", k, v)
json.dump(res, open("data/derived/verification_historical_fee_dates.json", "w"), indent=1, default=str)
