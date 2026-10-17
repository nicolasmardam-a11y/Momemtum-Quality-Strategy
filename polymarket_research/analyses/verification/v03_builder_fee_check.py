"""Verifier check (read-only): are non-zero OrderFilled.fee values on fee-free markets, and excess fees above
feeSchedule on fee markets, explained by builder fees (builder != 0)? Source: ctf-exchange-v2 ITrading.sol event,
docs /programs/builders/fees ("No platform fee + builder code -> builder fee only")."""
import json, sys, time
from analyses.fees.keccak import keccak256
from pmr import api
from pmr.http import request_json
TOPIC = "0x" + keccak256(b"OrderFilled(bytes32,address,address,uint8,uint256,uint256,uint256,uint256,bytes32,bytes32)").hex()
EXCH = {"0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59", "0xe3333700ca9d93003f00f0f71f8515005f6c00aa"}
CIDS = {"0x3738ad9665480991affe3ba286cd035516e17d1f8b7703e05088ec19c70c21a4": 0.0,   # fee-free (Gamma feesEnabled false)
        "0xe5699e9eeb4d985d52ced2156482d1f49c3c27806e68e8011f4a4d217799e84c": 0.03}  # NFL Saints vs Giants
NTX = int(sys.argv[1]) if len(sys.argv) > 1 else 25
res = []
for cid, rate in CIDS.items():
    cm = request_json(f"{api.CLOB}/clob-markets/{cid}", source="clob")
    toks = {t["t"] for t in cm["t"]}
    tr = request_json(f"{api.DATA}/v2/trades", {"condition": cid, "limit": 200, "_": str(time.time())}, source="data-api")["data"]
    hs = list(dict.fromkeys(t["transaction_hash"] for t in tr))[:NTX]
    for h in hs:
        for lg in api.rpc("eth_getTransactionReceipt", [h])["logs"]:
            if lg["address"].lower() not in EXCH or lg["topics"][0] != TOPIC:
                continue
            w = [int(lg["data"][2 + i:66 + i], 16) for i in range(0, len(lg["data"]) - 2, 64)]
            side, tok, mk, tk, fee, builder = w[0], str(w[1]), w[2], w[3], w[4], w[5]
            if tok not in toks:
                continue
            taker_is_exch = ("0x" + lg["topics"][3][-40:]).lower() in EXCH
            usd, sh = (mk, tk) if side == 0 else (tk, mk)
            usd, sh = usd / 1e6, sh / 1e6
            p = usd / sh if sh else 0
            plat = round(sh * rate * p * (1 - p), 5)
            res.append({"cid": cid[:10], "role": "taker" if taker_is_exch else "maker", "side": "BUY" if side == 0 else "SELL",
                        "shares": sh, "p": round(p, 4), "fee": fee / 1e6, "platform_fee_expected": plat,
                        "excess_bps_of_notional": round((fee / 1e6 - plat) / usd * 1e4, 2) if usd else None,
                        "builder_nonzero": builder != 0})
import collections
for cid in {r["cid"] for r in res}:
    rr = [r for r in res if r["cid"] == cid]
    c = collections.Counter((r["role"], r["builder_nonzero"], r["excess_bps_of_notional"] is not None and abs(r["excess_bps_of_notional"]) > 0.5) for r in rr)
    print(cid, dict(c))
    for r in rr:
        if r["excess_bps_of_notional"] is not None and abs(r["excess_bps_of_notional"]) > 0.5:
            print("   ", r)
json.dump(res, open("data/derived/verification_builder_fee_check.json", "w"), indent=0)
