"""Verifier check (read-only): per-market fee class, delays, UMA params, version, and the rate actually
charged on-chain for recent taker fills, for the highest-volume open market of selected feeTypes.

Sources: Gamma /markets/keyset (live), CLOB /clob-markets/{cid} (live), Data API /v2/trades (recent tx hashes),
Polygon RPC eth_getTransactionReceipt -> OrderFilled logs (ctf-exchange-v2 ITrading.sol event).
The researcher parquet is used ONLY to choose which markets to query.
"""
import json
import sys
import time

import pandas as pd

from analyses.fees.keccak import keccak256
from pmr import api
from pmr.http import request_json

TOPIC = "0x" + keccak256(b"OrderFilled(bytes32,address,address,uint8,uint256,uint256,uint256,uint256,bytes32,bytes32)").hex()
EXCH = {"0xe111180000d2663c0091e4f400237545b87b996b", "0xe2222d279d744050d28e00520010520000310f59",
        "0xe3333700ca9d93003f00f0f71f8515005f6c00aa"}
FEETYPES = sys.argv[1:] or ["sports_fees_nfl_cfb_oct26", "sports_fees_v2", "sports_fees_v3", "crypto_fees_v2",
                            "politics_fees", "culture_fees", "NONE"]
import os
N_PER_TYPE = int(os.environ.get("NPT", "2"))
N_TX = 6

d = pd.read_parquet("data/derived/open_market_fees_2026-10-17.parquet")
d["feeType"] = d["feeType"].fillna("NONE")


def decode(log):
    data = log["data"][2:]
    w = [int(data[i:i + 64], 16) for i in range(0, len(data), 64)]
    side, token, mk, tk, fee = w[0], w[1], w[2], w[3], w[4]
    taker = "0x" + log["topics"][3][-40:]
    if side == 0:  # BUY: maker gives collateral (mk), receives tokens (tk)
        usd, sh = mk / 1e6, tk / 1e6
    else:
        sh, usd = mk / 1e6, tk / 1e6
    p = usd / sh if sh else None
    return {"taker_is_exchange": taker.lower() in EXCH, "side": "BUY" if side == 0 else "SELL", "shares": sh,
            "price": p, "fee": fee / 1e6, "token": str(token)}


out = []
for ft in FEETYPES:
    sub = d[d.feeType == ft].sort_values("volume24hr", ascending=False).head(N_PER_TYPE)
    for _, row in sub.iterrows():
        cid = row.conditionId
        g = request_json(f"{api.GAMMA}/markets/keyset", {"condition_ids": cid, "limit": 5}, source="gamma")
        gm = (g.get("markets") or [None])[0]
        if gm is None:
            g = request_json(f"{api.GAMMA}/markets/keyset", {"condition_ids": cid, "closed": "true", "limit": 5}, source="gamma")
            gm = (g.get("markets") or [{}])[0]
        cm = request_json(f"{api.CLOB}/clob-markets/{cid}", source="clob")
        toks = {str(x) for x in api.jlist(gm.get("clobTokenIds"))} | {str(t.get("t")) for t in (cm.get("t") or []) if isinstance(t, dict)}
        rec = {"feeType_parquet": ft, "question": row.question[:60], "cid": cid,
               "gamma_feeType": gm.get("feeType"), "gamma_feesEnabled": gm.get("feesEnabled"),
               "gamma_feeSchedule": gm.get("feeSchedule"), "gamma_secondsDelay": gm.get("secondsDelay"),
               "gamma_version": gm.get("version"), "gamma_umaBond": gm.get("umaBond"),
               "gamma_customLiveness": gm.get("customLiveness"), "gamma_restricted": gm.get("restricted"),
               "gamma_createdAt": gm.get("createdAt"),
               "clob_fd": cm.get("fd"), "clob_sd": cm.get("sd"), "clob_itode": cm.get("itode")}
        tr = request_json(f"{api.DATA}/v2/trades", {"condition": cid, "limit": 40, "_": str(time.time())},
                          source="data-api").get("data") or []
        hashes = []
        for t in tr:
            h = t.get("transaction_hash")
            if h and h not in hashes and 0.03 < float(t.get("price", 0)) < 0.97:
                hashes.append(h)
        rates = []
        for h in hashes[:N_TX]:
            rc = api.rpc("eth_getTransactionReceipt", [h])
            for lg in rc.get("logs", []):
                if lg["address"].lower() in EXCH and lg["topics"][0] == TOPIC:
                    x = decode(lg)
                    if x["token"] in toks and x["taker_is_exchange"] and x["shares"] >= 1 and x["price"] and 0.02 < x["price"] < 0.98:
                        rates.append(round(x["fee"] / (x["shares"] * x["price"] * (1 - x["price"])), 4))
        rec["onchain_taker_implied_rates"] = rates
        rec["n_tokens_known"] = len(toks)
        rec["latest_trade_ts"] = tr[0].get("timestamp") if tr else None
        out.append(rec)
        print(json.dumps(rec, default=str))
json.dump(out, open(f"data/derived/verification_live_fee_check_{time.strftime('%Y%m%dT%H%M', time.gmtime())}.json", "w"),
          indent=1, default=str)
