"""Empirically recover the taker-fee formula actually charged on-chain at given dates (read-only).

For each sample time, pulls OrderFilled logs from the CLOB V2 exchanges via public Polygon RPC
over a short block window, keeps the taker-order fills (taker == exchange contract, see
docs /resources/onchain-position-data), and computes

    implied_rate = fee / (shares * p * (1 - p))      (current docs formula, /trading/fees)

Each fill's token is mapped to its market via Data API /v2/tokens and Gamma /markets/slug
(feeType, feeSchedule as Gamma shows them *today*). Writes data/derived/onchain_fee_samples.parquet.

Event ABI from github.com/Polymarket/ctf-exchange-v2 src/exchange/interfaces/ITrading.sol:
OrderFilled(bytes32 indexed orderHash, address indexed maker, address indexed taker, uint8 side,
            uint256 tokenId, uint256 makerAmountFilled, uint256 takerAmountFilled, uint256 fee,
            bytes32 builder, bytes32 metadata)
Usage: python -m analyses.fees.onchain_fee_sampler 2026-05-05T15:00 2026-07-05T15:00 ...
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402
from analyses.fees.keccak import keccak256  # noqa: E402

TOPIC = "0x" + keccak256(b"OrderFilled(bytes32,address,address,uint8,uint256,uint256,uint256,uint256,bytes32,bytes32)").hex()
EXCHANGES = {
    "0xe111180000d2663c0091e4f400237545b87b996b": "ctf_exchange_v2",
    "0xe2222d279d744050d28e00520010520000310f59": "negrisk_ctf_exchange_v2",
    "0xe3333700ca9d93003f00f0f71f8515005f6c00aa": "polyv2_exchange_v3",
}
WINDOW_BLOCKS = int(__import__("os").environ.get("FEE_WINDOW_BLOCKS", "40"))
# publicnode refuses archive reads ("Archive requests require a personal token", 2026-10-17);
# drpc's public endpoint served historical logs without a key on 2026-10-17.
RPC_URL = __import__("os").environ.get("FEE_RPC", "https://polygon.drpc.org")


def rpc(method: str, params: list):
    j = request_json(RPC_URL, method="POST", json_body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                     source="polygon-archive")
    if "error" in j:
        raise RuntimeError(f"RPC {method} error: {j['error']}")
    return j["result"]


def block_at(ts: int) -> int:
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


def decode(log: dict) -> dict:
    d = log["data"][2:]
    w = [int(d[i:i + 64], 16) for i in range(0, len(d), 64)]
    side, token, mk, tk, fee = w[0], w[1], w[2], w[3], w[4]
    if side == 0:   # BUY: maker gives collateral, receives shares
        usdc, shares = mk / 1e6, tk / 1e6
    else:           # SELL: maker gives shares, receives collateral
        usdc, shares = tk / 1e6, mk / 1e6
    p = usdc / shares if shares else None
    taker = "0x" + log["topics"][3][-40:]
    return {
        "block": int(log["blockNumber"], 16), "tx": log["transactionHash"], "log_index": int(log["logIndex"], 16),
        "exchange": EXCHANGES.get(log["address"].lower(), log["address"]), "side": "BUY" if side == 0 else "SELL",
        "token_id": str(token), "shares": shares, "usdc": usdc, "price": p, "fee_usdc": fee / 1e6,
        "is_taker_fill": taker.lower() == log["address"].lower(),
    }


def market_meta(token_ids: list[str]) -> dict[str, dict]:
    out = {}
    for i in range(0, len(token_ids), 50):
        j = request_json("https://data-api.polymarket.com/v2/tokens", {"token_id": ",".join(token_ids[i:i + 50])},
                         source="data-api", cache=True)
        for r in j.get("data") or []:
            out[r["token_id"]] = r
    slugs = {r.get("market_slug") for r in out.values() if r.get("market_slug")}
    gm = {}
    for s in slugs:
        try:
            m = request_json(f"https://gamma-api.polymarket.com/markets/slug/{s}", {"include_tag": "true"}, source="gamma", cache=True)
        except RuntimeError:
            continue
        fs = m.get("feeSchedule") or {}
        gm[s] = {"feeType": m.get("feeType"), "feesEnabled": m.get("feesEnabled"), "gamma_rate": fs.get("rate"),
                 "gamma_exponent": fs.get("exponent"), "gamma_rebateRate": fs.get("rebateRate"),
                 "createdAt": m.get("createdAt"),
                 "tags": "|".join(t.get("slug") or "" for t in (m.get("tags") or []))}
    res = {}
    for t, r in out.items():
        res[t] = {"market_slug": r.get("market_slug"), "title": r.get("title"), "module": r.get("module"),
                  **gm.get(r.get("market_slug"), {})}
    return res


def sample(when: str) -> pd.DataFrame:
    ts = int(datetime.fromisoformat(when).replace(tzinfo=timezone.utc).timestamp())
    b = block_at(ts)
    logs = rpc("eth_getLogs", [{"fromBlock": hex(b), "toBlock": hex(b + WINDOW_BLOCKS),
                                    "address": list(EXCHANGES), "topics": [TOPIC]}])
    df = pd.DataFrame([decode(l) for l in logs])
    if df.empty:
        return df
    df["sample_time"] = when
    df = df[df.is_taker_fill & (df.shares > 0)].copy()
    df["implied_rate_cur"] = df.fee_usdc / (df.shares * df.price * (1 - df.price))
    meta = market_meta(sorted(df.token_id.unique()))
    m = pd.DataFrame.from_dict(meta, orient="index")
    return df.merge(m, left_on="token_id", right_index=True, how="left")


def main(times: list[str]) -> None:
    out = ROOT / "data" / "derived" / "onchain_fee_samples.parquet"
    frames = [pd.read_parquet(out)] if out.exists() else []
    for t in times:
        d = sample(t)
        print(t, len(d))
        frames.append(d)
    df = pd.concat(frames, ignore_index=True).drop_duplicates(["tx", "log_index"])
    df.to_parquet(out, index=False)
    print(out, len(df))


if __name__ == "__main__":
    main(sys.argv[1:])
