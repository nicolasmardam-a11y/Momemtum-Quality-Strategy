"""Verifier check (read-only): NegRiskAdapter (0xd91E...) getFeeBips / getQuestionCount for a fresh random sample of
open neg-risk markets (different seed from the researcher's). Source: eth_call on Polygon public RPC."""
import random, json
import pandas as pd
from analyses.fees.keccak import keccak256
from pmr import api
NRA = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
SEL_FEE = "0x" + keccak256(b"getFeeBips(bytes32)").hex()[:8]
SEL_QC = "0x" + keccak256(b"getQuestionCount(bytes32)").hex()[:8]
d = pd.read_parquet("data/derived/open_market_fees_2026-10-17.parquet")
nr = d[d.negRisk == True]
random.seed(20261017)
ids = random.sample(list(nr.conditionId), 60)
seen, out = set(), []
for cid in ids:
    g = api.gamma_markets(condition_ids=cid)
    if not g or not g[0].get("negRiskMarketID"):
        continue
    mid = g[0]["negRiskMarketID"]
    if mid in seen:
        continue
    seen.add(mid)
    arg = mid[2:].rjust(64, "0")
    fee = int(api.rpc("eth_call", [{"to": NRA, "data": SEL_FEE + arg}, "latest"]), 16)
    qc = int(api.rpc("eth_call", [{"to": NRA, "data": SEL_QC + arg}, "latest"]), 16)
    out.append({"negRiskMarketID": mid, "feeBips": fee, "questionCount": qc, "q": g[0]["question"][:50]})
    if len(out) >= 25:
        break
print("selectors", SEL_FEE, SEL_QC)
print("n markets", len(out), "feeBips values", sorted({o["feeBips"] for o in out}), "questionCounts", sorted(o["questionCount"] for o in out))
json.dump(out, open("data/derived/verification_negrisk_feebips.json", "w"), indent=0)
