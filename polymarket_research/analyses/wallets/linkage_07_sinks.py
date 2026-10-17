"""Step 7 of the linkage study: where the three wallets' withdrawals end up on Ethereum.

linkage_06 found that the Relay withdrawal recipients of all three wallets forward USDC, within minutes to hours,
into two EOAs that sweep everything to Binance-labelled hot wallets:
  sink A 0xb08b…317d  (sweeps USDC -> 0xee7a…4055 'Binance: Hot Wallet 34', USDT -> 0x28c6…1d60 'Binance 14')
  sink B 0x3319…b072  (sweeps USDC -> 0xee7a…4055)
(labels: Etherscan public name tags, fetched 2026-10-17). This script attributes every inflow of the sinks and of
the single-hop intermediaries:
  - Relay fills (USDC from the Relay solver 0xf70d…dbef or USDC minted from 0x0 in a Relay fill tx) are looked up on
    the Relay API by tx hash -> origin user (a Polygon address) -> Polymarket profile (Gamma /public-profile);
  - any other EOA sender is traced one hop back on Ethereum (stablecoin inflows, 2026-05-10 .. 2026-06-25).
Outputs: data/derived/linkage_sink_inflows.parquet, linkage_sink_backtrace.parquet
"""
from __future__ import annotations

import time

import pandas as pd

from linkage_06_origin_chains import ETH_RPC, EVM_TOKENS, decode, rpc
from linkage_common import DERIVED, LABEL, TRANSFER, pad, request_json

SINKS = {"0xb08b85827f803c37b5a3163ec1f03ce6b21e317d": "sinkA", "0x33193e1592ff490f21f15bd877736aacf3cbb072": "sinkB"}
HOPS = {"0xa6230f226851a3446a579ca130bbc2b9854fae1c": "mintblade:wdr-hop", "0xac3518db3af76a35ed281a1b25621698fa0d2a89": "endlessFate:wdr-hop",
        "0xe065507311074a2e23164f8025c68dd4b9c4a46f": "GRIMDRIP:wdr-hop", "0xbbfa4c80f062fdf4a4a7eba84077d0a1ec604803": "eF-hop->0xbbfa"}
RELAY_SOLVER = "0xf70da97812cb96acdf810712aa562db8dfa3dbef"
ZERO = "0x" + "0" * 40
BINANCE = {"0xee7ae85f2fe2239e27d9c1e23fffe168d63b4055": "Binance: Hot Wallet 34 (Etherscan tag)",
           "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14 (Etherscan tag)"}


def relay_by_hash(tx: str) -> dict:
    for attempt in range(8):  # the deprecated v2 route throttles in stages; back off (responses are cached once fetched)
        try:
            j = request_json("https://api.relay.link/requests/v2", {"hash": tx}, source="relay", cache=True, retries=1)
            break
        except RuntimeError as err:
            if "429" not in str(err) or attempt == 7:
                raise
            time.sleep(60 * (attempt + 1))
    rq = j.get("requests") or []
    if not rq:
        return {}
    r = rq[0]
    d = r.get("data") or {}
    ins = d.get("inTxs") or []
    return {"relay_id": r.get("id"), "relay_user": (r.get("user") or "").lower(), "relay_recipient": (r.get("recipient") or "").lower(),
            "relay_in_chain": ins[0].get("chainId") if ins else None, "relay_created": r.get("createdAt"),
            "relay_amt_in": float(((d.get("metadata") or {}).get("currencyIn") or {}).get("amountFormatted") or "nan")}


def profile(addr: str) -> dict:
    try:
        p = request_json("https://gamma-api.polymarket.com/public-profile", {"address": addr}, source="gamma", cache=True, retries=2)
    except RuntimeError:
        return {"pm_name": None, "pm_created": None}
    return {"pm_name": p.get("name"), "pm_created": p.get("createdAt")}


def main() -> None:
    e = pd.read_parquet(DERIVED / "linkage_origin_eth.parquet")
    e = e[e.token.notna() & (e.amount > 1)]
    inflow = e[e.set_addr.isin({**SINKS, **HOPS}) & (e.dir == "in")].copy()
    # Relay requests already pulled in linkage_03 (candidate wallets' own withdrawals), keyed by destination tx hash
    rq = pd.read_parquet(DERIVED / "linkage_relay_requests.parquet")
    rq = rq[rq.out_hash.notna()].drop_duplicates("out_hash")
    known = {h.lower(): {"relay_id": i, "relay_user": u, "relay_recipient": rc, "relay_in_chain": ic, "relay_created": c, "relay_amt_in": a}
             for h, i, u, rc, ic, c, a in zip(rq.out_hash, rq.id, rq.user, rq.recipient, rq.in_chain, rq.created_at, rq.amt_in)}
    rows = []
    for _, x in inflow.iterrows():
        r = {"node": {**SINKS, **HOPS}[x.set_addr], "node_addr": x.set_addr, "tx": x.tx, "ts": x.ts, "token": x.token,
             "amount": x.amount, "sender": x.counterparty}
        if x.counterparty in (RELAY_SOLVER, ZERO):
            r.update(known.get(x.tx.lower()) or relay_by_hash(x.tx))
            time.sleep(0 if x.tx.lower() in known else 3)
        rows.append(r)
    df = pd.DataFrame(rows)
    users = df.relay_user.dropna().unique() if "relay_user" in df else []
    prof = {u: profile(u) for u in users if u}
    df["origin_label"] = df.relay_user.map(lambda u: LABEL.get(u) if isinstance(u, str) else None)
    df["pm_name"] = df.relay_user.map(lambda u: prof.get(u, {}).get("pm_name") if isinstance(u, str) else None)
    df["pm_created"] = df.relay_user.map(lambda u: prof.get(u, {}).get("pm_created") if isinstance(u, str) else None)
    df.to_parquet(DERIVED / "linkage_sink_inflows.parquet", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 44)
    pd.set_option("display.max_rows", 200)
    df["src"] = df.origin_label.fillna(df.pm_name).fillna(df.relay_user).fillna(df.sender.map(lambda a: {**HOPS, **SINKS}.get(a, a)))
    print(df.groupby(["node", "src", "token"], dropna=False).agg(n=("tx", "size"), amt=("amount", "sum"), t0=("ts", "min"),
                                                                 t1=("ts", "max")).reset_index().to_string())
    # one hop back for non-Relay EOA senders of the sinks
    others = sorted(set(df[(~df.sender.isin([RELAY_SOLVER, ZERO])) & (~df.sender.isin({**HOPS, **SINKS}))].sender))
    bt, busy = [], []
    for a in others:
        try:
            for s in range(25_080_000, 25_400_000, 50_000):
                logs = rpc(ETH_RPC, "eth_getLogs", [{"fromBlock": hex(s), "toBlock": hex(s + 49_999), "topics": [TRANSFER, None, pad(a)]}],
                           source="ethereum-tenderly")
                bt += [decode(lg, 1, a, "sink-sender", "in") for lg in logs if len(lg["topics"]) == 3]
        except RuntimeError as err:
            if "more than 20000 results" not in str(err):
                raise
            busy.append(a)  # >20k incoming transfers in one 50k-block window: a service / hot wallet, not traced further
    print("senders with >20k inbound transfers per 50k blocks (service wallets, not traced):", busy)
    b = pd.DataFrame(bt)
    if len(b):
        b = b[b.token.notna() & (b.amount > 1)]
        b["counterparty"] = b["from"]
        b["cp_label"] = b.counterparty.map(lambda a: BINANCE.get(a, LABEL.get(a, "")))
        b.to_parquet(DERIVED / "linkage_sink_backtrace.parquet", index=False)
        g = b.groupby(["set_addr", "counterparty", "cp_label", "token"]).agg(n=("tx", "size"), amt=("amount", "sum")).reset_index()
        print("\none hop back from non-Relay senders of the sinks:")
        print(g.sort_values("amt", ascending=False).to_string())
        cps = b.groupby("counterparty").set_addr.nunique()
        print("senders' funders shared by >1 sender:", cps[cps > 1].to_dict())


if __name__ == "__main__":
    main()
