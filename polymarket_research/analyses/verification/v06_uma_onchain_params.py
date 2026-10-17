"""Verifier check (read-only): live UMA parameters on-chain for markets resolving through the main Polymarket UMA adapters.
- proposalBond from UmaCtfAdapter QuestionInitialized events (uma-ctf-adapter IUmaCtfAdapter.sol)
- liveness = expirationTimestamp - proposal block time from OptimisticOracleV2-style ProposePrice events
Source: Polygon public RPC eth_getLogs / eth_call."""
import collections, json, sys, requests, time
from analyses.fees.keccak import keccak256
from pmr import api
ADAPTERS = ["0x65070BE91477460D8A7AeEb94ef92fe056C2f2A7", "0x69c47De9D4D3Dad79590d61b9e05918E03775f24"]
t_qi = "0x" + keccak256(b"QuestionInitialized(bytes32,uint256,address,bytes,address,uint256,uint256)").hex()
t_pp = "0x" + keccak256(b"ProposePrice(address,address,bytes32,uint256,bytes,int256,uint256,address)").hex()
oo = "0x" + api.rpc("eth_call", [{"to": ADAPTERS[0], "data": "0x" + keccak256(b"optimisticOracle()").hex()[:8]}, "latest"])[-40:]
print("optimisticOracle() of adapter 0x6507:", oo)
head = int(api.rpc("eth_blockNumber", []), 16)
NB = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
bonds = collections.Counter(); rewards = collections.Counter()
lv = collections.Counter()
STEP = 100
def logs(flt):
    for i in range(5):
        r = requests.post("https://polygon.drpc.org", json={"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [flt]}, timeout=60).json()
        if "result" in r:
            return r["result"]
        time.sleep(2)
    raise RuntimeError(r)
blk_ts = {}
def bts(bn):
    if bn not in blk_ts:
        blk_ts[bn] = int(api.rpc("eth_getBlockByNumber", [hex(bn), False])["timestamp"], 16)
    return blk_ts[bn]
n_pp = 0
for start in range(head - NB, head, STEP):
    end = min(start + STEP - 1, head)
    for lg in logs({"fromBlock": hex(start), "toBlock": hex(end), "address": ADAPTERS, "topics": [t_qi]}):
        w = lg["data"][2:]
        words = [w[i:i + 64] for i in range(0, len(w), 64)]
        reward, bond = int(words[2], 16) / 1e6, int(words[3], 16) / 1e6
        bonds[bond] += 1; rewards[reward] += 1
    for lg in logs({"fromBlock": hex(start), "toBlock": hex(end), "address": oo, "topics": [t_pp]}):
        if ("0x" + lg["topics"][1][-40:]).lower() not in {a.lower() for a in ADAPTERS}:
            continue
        w = lg["data"][2:]
        words = [w[i:i + 64] for i in range(0, len(w), 64)]
        exp = int(words[4], 16)
        n_pp += 1
        if n_pp <= 150:
            lv[exp - bts(int(lg["blockNumber"], 16))] += 1
print("blocks scanned", NB, "QuestionInitialized proposalBond counts:", dict(bonds.most_common()))
print("reward counts:", dict(rewards.most_common(8)))
print("ProposePrice from adapters:", n_pp, "liveness (s) counts (first 150):", dict(lv.most_common()))
json.dump({"oo": oo, "bonds": bonds, "rewards": rewards, "liveness": lv, "blocks": NB, "head": head},
          open("data/derived/verification_uma_onchain_params.json", "w"), default=str)
