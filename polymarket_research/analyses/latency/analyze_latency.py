"""Analyse one latency run written by measure_latency.py (read-only, no network).

Usage:  python analyses/latency/analyze_latency.py <STAMP>
Output: data/derived/latency_<STAMP>_analysis.json and a printed report.

Definitions (all in seconds):
  match time  = CLOB market-WebSocket `last_trade_price.timestamp` (ms), joined by transaction hash
  block time  = Polygon block timestamp of the settling transaction (integer seconds)
  Data API ts = `/v2/trades` row `timestamp` (documented as block timestamp)
  RTDS ts     = RTDS activity payload `timestamp` (seconds)
  Data API first-seen upper bound = response receipt time of the first poll that returned the row;
  lower bound = send time of the previous poll that did not return it (poll interval ~2 s).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "derived"
STAMP = sys.argv[1]


def load(name):
    p = D / f"latency_{STAMP}_{name}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def q(s) -> dict:
    s = pd.Series(s).dropna().astype(float)
    if s.empty:
        return {"n": 0}
    return {"n": int(len(s)), "min": round(s.min(), 3), "p10": round(s.quantile(.1), 3), "median": round(s.median(), 3),
            "mean": round(s.mean(), 3), "p90": round(s.quantile(.9), 3), "p99": round(s.quantile(.99), 3), "max": round(s.max(), 3)}


summ = json.loads((D / f"latency_{STAMP}_summary.json").read_text())
mk, da, pl, cw, rt, rf, tp, rpc, st = (load(n) for n in ("markets", "dataapi", "polls", "clobws", "rtds", "rtds_filtered", "tape", "rpc", "status"))
T = set(mk.condition_id)
if "_taker_only" not in tp:
    tp["_taker_only"] = "false"
t0 = pd.Timestamp(summ["t_start_utc"]).timestamp()
t1 = pd.Timestamp(summ["t_end_utc"]).timestamp()
A: dict = {"stamp": STAMP, "markets": mk[["slug", "question", "n_trades_select", "seconds_delay", "fee_type", "neg_risk"]].to_dict("records"),
           "window_utc": [summ["t_start_utc"], summ["t_end_utc"]]}

# ------------------------------------------------------------------ clocks
rt["recv_s"] = rt.recv_ms / 1000
A["clock_rtds_recv_minus_envelope_ms"] = q(rt.recv_ms - rt.env_ts_ms)
A["dataapi_rtt_ms"] = q((pl.t_resp - pl.t_req) * 1000)

# ------------------------------------------------------------------ per-tx reference times
match = cw.groupby("tx").agg(match_s=("match_ms", lambda s: s.min() / 1000), ws_recv_s=("recv_ms", lambda s: s.min() / 1000)).reset_index()
blk = rpc.dropna(subset=["block_ts"])[["tx", "block_ts", "block", "to"]] if "block_ts" in rpc else pd.DataFrame(columns=["tx", "block_ts"])

# ------------------------------------------------------------------ Data API rows
live = da[~da.baseline].copy()
live["upper"] = live.t_resp - live.ts
live["lower"] = live.prev_req - live.ts
for (shape, mode), g in live.groupby(["shape", "mode"]):
    A[f"dataapi_{shape}_{mode}"] = {"rows": int(len(g)), "first_seen_minus_ts_upper": q(g.upper), "first_seen_minus_ts_lower": q(g.lower),
                                    "rows_first_seen_more_than_60s_after_ts": int((g.lower > 60).sum())}
# cached mode: how stale is what a naive poller sees? age header and lag of the newest row vs request time
cp = pl[(pl["mode"] == "cached") & pl.max_ts.notna()]
bp = pl[(pl["mode"] == "busted") & pl.max_ts.notna() & (pl["shape"] == "condition")]
A["cached_poll_age_header_s"] = q(pd.to_numeric(cp.age, errors="coerce"))
A["cached_poll_newest_row_age_s"] = q(cp.t_req - cp.max_ts)
A["busted_poll_newest_row_age_s"] = q(bp.t_req - bp.max_ts)
A["x_cache"] = pl.groupby(["mode", "x_cache"]).size().rename("n").reset_index().to_dict("records")

bust = live[(live["mode"] == "busted") & (live["shape"] == "condition")]
cach = live[(live["mode"] == "cached") & (live["shape"] == "condition")]
user = live[(live["mode"] == "busted") & (live["shape"] == "user")]

# ------------------------------------------------------------------ joins on tx
j = blk.merge(bust.groupby("tx").agg(da_ts=("ts", "min"), da_first=("t_resp", "min"), da_prev=("prev_req", "min")).reset_index(), on="tx", how="left")
j = j.merge(match, on="tx", how="left")
rtt = rt[rt.tag == "trades"].groupby("tx").agg(rt_ts=("ts", "min"), rt_recv=("recv_s", "min")).reset_index()
rom = rt[rt.tag == "orders_matched"].groupby("tx").agg(om_ts=("ts", "min"), om_recv=("recv_s", "min")).reset_index()
j = j.merge(rtt, on="tx", how="left").merge(rom, on="tx", how="left")
A["rpc_sample"] = int(len(blk)); A["rpc_to"] = blk["to"].value_counts().to_dict() if len(blk) else {}
A["timestamp_semantics"] = {
    "dataapi_ts_minus_block_ts": q(j.da_ts - j.block_ts),
    "dataapi_ts_equals_block_ts_share": round(float((j.da_ts == j.block_ts).mean()), 4) if len(j) else None,
    "rtds_trades_ts_minus_block_ts": q(j.rt_ts - j.block_ts),
    "rtds_orders_matched_ts_minus_block_ts": q(j.om_ts - j.block_ts),
    "rtds_ts_minus_floor_match": q(j.rt_ts - np.floor(j.match_s)),
    "block_ts_minus_match_s": q(j.block_ts - j.match_s),
}
# ------------------------------------------------------------------ end-to-end detection latency from the match
# CLOB WS gives every trade of subscribed tokens (no wallet). Use all WS trades in target markets.
A["detect_from_match"] = {
    "clob_ws_last_trade_price (no wallet)": q(cw.recv_ms / 1000 - cw.match_ms / 1000),
}
m2 = match.merge(rtt, on="tx", how="inner")
A["detect_from_match"]["rtds_trades (wallet)"] = q(m2.rt_recv - m2.match_s)
m3 = match.merge(rom, on="tx", how="inner")
A["detect_from_match"]["rtds_orders_matched (taker wallet)"] = q(m3.om_recv - m3.match_s)
m4 = match.merge(bust.groupby("tx").t_resp.min().rename("da_first").reset_index(), on="tx", how="inner")
A["detect_from_match"]["dataapi_condition_busted_2s_poll (upper)"] = q(m4.da_first - m4.match_s)
m4b = match.merge(bust.groupby("tx").prev_req.min().rename("da_prev").reset_index(), on="tx", how="inner")
A["detect_from_match"]["dataapi_condition_busted_2s_poll (lower)"] = q(m4b.da_prev - m4b.match_s)
m5 = match.merge(cach.groupby("tx").t_resp.min().rename("da_first").reset_index(), on="tx", how="inner")
A["detect_from_match"]["dataapi_condition_cached_2s_poll (upper)"] = q(m5.da_first - m5.match_s)
# relative to block time (for rows without a WS match, e.g. user-shape rows in other markets)
A["detect_from_block_ts_field"] = {
    "dataapi_condition_busted (upper)": q(bust.upper), "dataapi_condition_busted (lower)": q(bust.lower),
    "dataapi_condition_cached (upper)": q(cach.upper), "dataapi_user_busted (upper)": q(user.upper), "dataapi_user_busted (lower)": q(user.lower),
}
jj = j.dropna(subset=["rt_recv"])
A["detect_from_block_ts_rpc"] = {"rtds_trades_recv_minus_block_ts": q(jj.rt_recv - jj.block_ts),
                                 "clob_ws_recv_minus_block_ts": q(j.ws_recv_s - j.block_ts),
                                 "dataapi_busted_first_minus_block_ts": q(j.da_first - j.block_ts)}
# same (tx, wallet) seen in both RTDS trades and Data API busted
a = bust.groupby(["tx", "wallet"]).t_resp.min()
b = rt[rt.tag == "trades"].groupby(["tx", "wallet"]).recv_s.min()
c = pd.concat([a, b], axis=1, join="inner")
A["dataapi_busted_first_minus_rtds_first"] = q(c.iloc[:, 0] - c.iloc[:, 1])
au = user.groupby(["tx", "wallet"]).t_resp.min()
cu = pd.concat([au, b], axis=1, join="inner")
A["dataapi_user_busted_first_minus_rtds_first"] = q(cu.iloc[:, 0] - cu.iloc[:, 1])

# ------------------------------------------------------------------ coverage (what the RTDS rows are)
lo, hi = t0 + 15, t1 - 20  # margins so both sources fully cover the interval
tpf = tp[(tp._taker_only == "false") & tp.timestamp.between(lo, hi)].copy()
tpt = tp[(tp._taker_only == "true") & tp.timestamp.between(lo, hi)].copy()
for x in (tpf, tpt):
    x["tx"] = x.transaction_hash.str.lower(); x["wallet"] = x.proxy_wallet.str.lower()
key = lambda df: set(zip(df.tx, df.wallet, df.asset if "asset" in df else df.token_id))
kf, kt = key(tpf), key(tpt)
txs_window = set(tpf.tx)
rtw = rt[rt.condition_id.isin(T) & rt.tx.isin(txs_window)]
kr = key(rtw[rtw.tag == "trades"]); ko = key(rtw[rtw.tag == "orders_matched"])
A["coverage_window"] = [lo, hi]
A["coverage"] = {
    "tape_rows_maker_and_taker": len(kf), "tape_rows_taker_only": len(kt), "tape_txs": len(txs_window),
    "rtds_trades_rows": len(kr), "rtds_trades_in_full_tape": len(kr & kf), "full_tape_in_rtds_trades": len(kf & kr),
    "taker_rows_in_rtds_trades": len(kt & kr), "maker_rows_in_rtds_trades": len((kf - kt) & kr),
    "rtds_orders_matched_rows": len(ko), "orders_matched_that_are_taker_rows": len(ko & kt), "taker_rows_in_orders_matched": len(kt & ko),
    "orders_matched_that_are_maker_rows": len(ko & (kf - kt)),
    "rtds_trades_rows_per_tx": q(rtw[rtw.tag == "trades"].groupby("tx").size()),
    "tape_rows_per_tx_maker_and_taker": q(tpf.groupby("tx").size()),
    "clobws_txs_in_window": int(cw[cw.condition_id.isin(T) & cw.tx.isin(txs_window)].tx.nunique()),
    "tape_txs_with_clobws_event": int(len(txs_window & set(cw.tx))),
}
missing = kf - kr
A["coverage"]["full_tape_rows_missing_from_rtds_examples"] = [list(m) for m in list(missing)[:5]]
# fee key vs taker
x = rtw[rtw.tag == "trades"].copy()
x["is_taker"] = [k in kt for k in zip(x.tx, x.wallet, x.asset)]
x["has_fee"] = x["keys"].str.contains(r"(?:^|,)fee(?:,|$)")
A["rtds_fee_key_vs_taker"] = x.groupby(["is_taker", "has_fee"]).size().rename("n").reset_index().to_dict("records")

# firehose characteristics
for tag in ("trades", "orders_matched"):
    y = rt[rt.tag == tag]
    A[f"firehose_{tag}"] = {"rows": int(len(y)), "rows_per_s": round(len(y) / summ["run_seconds"], 2), "distinct_wallets": int(y.wallet.nunique()),
                             "distinct_markets": int(y.condition_id.nunique()), "rows_without_condition_id": int((y.condition_id.fillna("") == "").sum()),
                             "recv_minus_ts": q(y.recv_s - y.ts)}
if len(rf):
    rf["recv_s"] = rf.recv_ms / 1000
    A["rtds_filtered"] = {"rows": int(len(rf)), "slugs_seen": sorted(set(rf.slug.dropna())), "offtarget_rows": int((~rf.condition_id.isin(T)).sum()),
                          "recv_minus_ts": q(rf.recv_s - rf.ts)}
A["status_serving_lag_s"] = q(st.serving_lag_s) if len(st) else {}
A["stream_stats"] = summ.get("stream_stats")
out = D / f"latency_{STAMP}_analysis.json"
out.write_text(json.dumps(A, indent=1, default=str))
print(json.dumps(A, indent=1, default=str))
