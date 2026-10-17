"""Cross-check the 'resolution known' time t_res (Gamma closedTime) and the payout against
(1) Data API v2 /v2/resolutions (UMA resolution record per condition: status, price, was_disputed, resolution
    transaction hash, last_update_timestamp) for a random sample of clean traded markets, and
(2) the chain itself for a sub-sample: receipt + block time of the transaction_hash that /v2/resolutions reports
    (public Polygon RPC polygon.drpc.org; polygon-bor-rpc.publicnode.com refuses archive reads without a token,
    tested 2026-10-17). FINDING: that transaction is the market INITIALISATION, not the resolution: its Conditional
    Tokens log is ConditionPreparation (topic0 0xab3760c3..., data = outcomeSlotCount only; the ConditionResolution
    topic0 computed locally is 0xb44d84d3...), and fills continue for days after it. The on-chain resolution time
    itself could not be fetched (eth_getLogs over old blocks is refused by the free RPCs tried).

Run from polymarket_research/:  python analyses/pit_wallets/09_resolution_check.py [n_sample] [n_onchain]
Writes data/derived/pit_wallets/resolution_check.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

OUT = ROOT / "data" / "derived" / "pit_wallets"
CTF = "0x4d97dcd97ec945f40cf65f87097ace5ea0476045"
RPC2 = "https://polygon.drpc.org"
COND_PREP_TOPIC = "0xab3760c3bd2bb38b5bcf54dc79802ed67338b4cf29f3054ded67ed24661e4177"   # ConditionPreparation (observed)
COND_RES_TOPIC = "0xb44d84d3289691f71497564b85d4233648d9dbae8cbdbb4329f301c3a0185894"    # ConditionResolution (keccak)


def rpc2(method, params):
    j = request_json(RPC2, method="POST", json_body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                     source="polygon", cache=True, retries=3)
    if "error" in j:
        raise RuntimeError(str(j["error"])[:200])
    return j["result"]


def to_unix(v):
    """/v2/resolutions returns last_update_timestamp either as unix seconds or as an ISO string."""
    if v in (None, ""):
        return None
    try:
        return int(v)
    except ValueError:
        return int((pd.Timestamp(v) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s"))


def main(n: int, n_chain: int):
    tm = pd.read_parquet(OUT / "token_meta_pit.parquet")
    mk = tm[(tm.p >= 0) & (tm.r > 0) & (tm.t_last < pd.Timestamp("2026-01-05", tz="UTC"))].copy()
    win = mk[mk.p == 1].drop_duplicates("condition_id")[["condition_id", "outcome_index", "question", "category", "r",
                                                         "negRisk", "t_last"]]
    win["year"] = win.t_last.dt.year
    smp = pd.concat([d.sample(min(len(d), n // 3), random_state=11) for _, d in win.groupby("year")])
    rows = []
    for x in smp.itertuples(index=False):
        j = request_json(f"{api.DATA}/v2/resolutions", {"condition": x.condition_id}, source="data-api", cache=True)
        d = (j.get("data") or [{}])
        d = d[-1] if d else {}
        rows.append({"condition_id": x.condition_id, "question": x.question, "category": x.category, "negRisk": x.negRisk,
                     "year": x.year, "t_res": int(x.r), "winner_index": int(x.outcome_index),
                     "t_last_fill": int((x.t_last - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta("1s")),
                     "n_records": len(j.get("data") or []), "res_status": d.get("status"), "res_price": d.get("price"),
                     "was_disputed": d.get("was_disputed"), "res_tx": d.get("transaction_hash"),
                     "res_ts": to_unix(d.get("last_update_timestamp"))})
    df = pd.DataFrame(rows)
    df["tres_minus_resapi_s"] = df.t_res - df.res_ts
    # on-chain sub-sample
    df["chain_ts"] = None; df["chain_has_condprep"] = None; df["chain_has_condres"] = None
    sub = pd.concat([g.head(max(1, n_chain // 8)) for _, g in df[df.res_tx.notna()].groupby(["year", "negRisk"], dropna=False)])
    for i in sub.index:
        try:
            rc = rpc2("eth_getTransactionReceipt", [df.at[i, "res_tx"]])
            blk = rpc2("eth_getBlockByNumber", [rc["blockNumber"], False])
            df.at[i, "chain_ts"] = int(blk["timestamp"], 16)
            ctf = [l for l in rc["logs"] if l["address"].lower() == CTF and len(l["topics"]) > 1
                   and l["topics"][1].lower() == df.at[i, "condition_id"].lower()]
            df.at[i, "chain_has_condprep"] = any(l["topics"][0] == COND_PREP_TOPIC for l in ctf)
            df.at[i, "chain_has_condres"] = any(l["topics"][0] == COND_RES_TOPIC for l in ctf)
        except Exception as e:  # record, do not hide
            df.at[i, "chain_has_condres"] = f"error: {str(e)[:120]}"
    df.to_parquet(OUT / "resolution_check.parquet", index=False)
    pd.set_option("display.width", 220)
    print("sampled", len(df), "with /v2/resolutions record", int(df.res_ts.notna().sum()))
    print("status counts", df.res_status.value_counts(dropna=False).to_dict())
    print("disputed share", float(df.was_disputed.fillna(False).astype(bool).mean()))
    d = df.dropna(subset=["res_ts"])
    print("|t_res - resolutions.last_update| <= 60s:", float((d.tres_minus_resapi_s.abs() <= 60).mean()),
          " <= 1h:", float((d.tres_minus_resapi_s.abs() <= 3600).mean()))
    print("t_res - res_ts quantiles (s):", d.tres_minus_resapi_s.quantile([0, .05, .5, .95, 1]).to_dict())
    print("last fill after t_res:", int((df.t_last_fill > df.t_res).sum()))
    c = df.dropna(subset=["chain_ts"])
    if len(c):
        c = c.assign(tres_minus_tx=c.t_res - c.chain_ts.astype(int), lastfill_minus_tx=c.t_last_fill - c.chain_ts.astype(int))
        print("on-chain checked", len(c), "| tx has ConditionPreparation for the condition:", c.chain_has_condprep.tolist().count(True),
              "| has ConditionResolution:", c.chain_has_condres.tolist().count(True),
              "| fills after that tx:", int((c.lastfill_minus_tx > 0).sum()))
        print("t_res - tx time (days) quantiles:", (c.tres_minus_tx / 86400).quantile([0, .5, 1]).round(2).to_dict())
    print(df.groupby("year").agg(n=("condition_id", "size"), match60=("tres_minus_resapi_s", lambda s: (s.abs() <= 60).mean())))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300, int(sys.argv[2]) if len(sys.argv) > 2 else 20)
