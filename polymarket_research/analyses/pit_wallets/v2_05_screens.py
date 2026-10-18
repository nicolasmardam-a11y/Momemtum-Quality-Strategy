"""Stage 3, step 5: point-in-time decisions and screens S1, S2, S3, S5 at D = 2026-06-01 for the wallet subset.

Run from polymarket_research/:  python analyses/pit_wallets/v2_05_screens.py
Uses only fills with timestamp < D (pulled with end = D - 1) and resolution times t_res < D.
Outputs:
  v2/decisions_trail.parquet  one row per (wallet, ue) decision with t0 in [2025-06-01, D)
  v2/screens_D.parquet         one row per subset wallet: record, screen flags, inclusion probability and IPW weight
  v2/eval_wallets.parquet      S1/S2/S3/S5 members + B1 sample (<= 600 eligible, smallest md5('b1|wallet'))
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from v2common import T_D, T_TRAIL0, V2, load_markets, u01, ue_for_rows  # noqa: E402

EP = 6 * 3600
K = 10


def wquantile(x: np.ndarray, w: np.ndarray, q: float) -> float:
    o = np.argsort(x)
    cw = np.cumsum(w[o]) / w.sum()
    return float(x[o][np.searchsorted(cw, q)])


def build_decisions(t: pd.DataFrame, lo: int, hi: int) -> pd.DataFrame:
    """Decisions (wallet, ue) whose first BUY (over all pulled fills) lies in [lo, hi)."""
    t = t.copy()
    t["usd"] = t["size"] * t["price"]
    buys = t[t["side"] == 1]
    t0 = buys.groupby(["wallet", "ue"])["timestamp"].min().rename("t0").reset_index()
    t0 = t0[(t0["t0"] >= lo) & (t0["t0"] < hi)]
    fb = buys.merge(t0, on=["wallet", "ue"])
    fb = fb[fb["timestamp"] == fb["t0"]]
    tok = fb.groupby(["wallet", "ue", "condition_id", "outcome_index"], as_index=False)["usd"].sum()
    tok = tok.sort_values(["wallet", "ue", "usd"], ascending=[True, True, False]).drop_duplicates(["wallet", "ue"])
    dec = t0.merge(tok[["wallet", "ue", "condition_id", "outcome_index"]], on=["wallet", "ue"])
    # 6 h entry episode on the decision token
    e = t.merge(dec, on=["wallet", "ue", "condition_id", "outcome_index"])
    e = e[(e["timestamp"] >= e["t0"]) & (e["timestamp"] <= e["t0"] + EP) & (e["timestamp"] < hi)]
    eb = e[e["side"] == 1].groupby(["wallet", "ue"]).agg(ep_sh=("size", "sum"), ep_usd=("usd", "sum"), ep_n=("size", "size"))
    es = e[e["side"] == 0].groupby(["wallet", "ue"]).agg(ep_sell_sh=("size", "sum"))
    dec = dec.merge(eb, on=["wallet", "ue"], how="left").merge(es, on=["wallet", "ue"], how="left")
    dec["ep_sell_sh"] = dec["ep_sell_sh"].fillna(0.0)
    dec["vwap"] = dec["ep_usd"] / dec["ep_sh"]
    dec["counted"] = (dec["ep_usd"] >= 1.0) & ((dec["ep_sh"] - dec["ep_sell_sh"]) >= 0.5 * dec["ep_sh"])
    return dec


def market_pnl(t: pd.DataFrame, dec: pd.DataFrame, m: pd.DataFrame, hi: int) -> pd.Series:
    """Decision-market P&L from fills < hi: sum over outcome tokens of sells - buys + payout x net shares."""
    x = t[(t["timestamp"] < hi)].merge(dec[["wallet", "condition_id"]].drop_duplicates(), on=["wallet", "condition_id"])
    x = x.merge(m[["condition_id", "pay0", "pay1"]], on="condition_id", how="left")
    x["pay"] = np.where(x["outcome_index"] == 0, x["pay0"], x["pay1"])
    x["usd"] = x["size"] * x["price"]
    x["cf"] = np.where(x["side"] == 1, -x["usd"], x["usd"])
    x["sh"] = np.where(x["side"] == 1, x["size"], -x["size"])
    g = x.groupby(["wallet", "condition_id", "outcome_index"]).agg(cf=("cf", "sum"), sh=("sh", "sum"), pay=("pay", "first"))
    g["pnl"] = g["cf"] + g["pay"] * g["sh"]
    g["neg"] = g["sh"] < -1e-6
    h = g.groupby(["wallet", "condition_id"]).agg(pnl=("pnl", "sum"), neg=("neg", "any"))
    return h


def main() -> None:
    m = load_markets(["condition_id", "event_slug", "category4", "t_res", "clean", "pay0", "pay1", "fee_rate_now",
                      "fee_exponent"])
    st = pd.read_csv(V2 / "wallets_trail_status.tsv", sep="\t").drop_duplicates("wallet", keep="last")
    sub = pd.read_parquet(V2 / "wallet_subset.parquet")
    files = sorted(glob.glob(str(V2 / "wallets_trail" / "chunk_*.parquet")))
    t = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    t = t[t["timestamp"] < T_D]
    print(f"trail fills {len(t):,} wallets {t['wallet'].nunique():,} (status {len(st):,}, subset {len(sub):,})")
    t["ue"] = ue_for_rows(t["event_slug"], t["condition_id"], m).values
    mres = m.set_index("condition_id")
    dec = build_decisions(t, T_TRAIL0, T_D)
    dec = dec.merge(m[["condition_id", "category4", "clean", "pay0", "pay1", "t_res_s"]], on="condition_id", how="left")
    dec["clean"] = dec["clean"].fillna(False).astype(bool)
    dec["resolved"] = dec["clean"] & (dec["t_res_s"] > 0) & (dec["t_res_s"] < T_D)
    dec["pay"] = np.where(dec["outcome_index"] == 0, dec["pay0"], dec["pay1"])
    dec["won"] = dec["resolved"] & (dec["pay"] == 1)
    dec["edge"] = dec["pay"] - dec["vwap"]
    pn = market_pnl(t, dec, m, T_D)
    dec = dec.merge(pn, left_on=["wallet", "condition_id"], right_index=True, how="left")
    dec["made_money"] = (dec["pnl"] > 0) & ~dec["neg"].fillna(False).astype(bool)
    dec.drop(columns=["pay0", "pay1"]).to_parquet(V2 / "decisions_trail.parquet", index=False)

    r = dec[dec["counted"] & dec["resolved"]].copy()
    r["pv"] = r["vwap"] * (1 - r["vwap"])
    g = r.groupby("wallet")
    w = pd.DataFrame({"n_res": g.size(), "n_won": g["won"].sum(), "sum_edge": g["edge"].sum(), "sum_pv": g["pv"].sum(),
                      "pnl": g["pnl"].sum(), "n_mm": g["made_money"].sum(), "avg_px": g["vwap"].mean()})
    w["n_open"] = dec[dec["counted"] & ~dec["resolved"]].groupby("wallet").size()
    w["med_usd"] = dec[dec["counted"] & (dec["t0"] + EP < T_D)].groupby("wallet")["ep_usd"].median()
    w = sub[["wallet", "cls", "q_cls", "pool_cids"]].merge(w.reset_index(), on="wallet", how="left")
    w = w.merge(st[["wallet", "n_trail", "capped_trail", "capped_pre"]], on="wallet", how="left")
    w[["n_res", "n_won", "sum_edge", "sum_pv", "pnl", "n_mm", "n_open"]] = \
        w[["n_res", "n_won", "sum_edge", "sum_pv", "pnl", "n_mm", "n_open"]].fillna(0)
    w["heavy"] = w["capped_trail"].fillna(1).astype(int) == 1
    # inclusion probability in the pool: frame markets traded (own history, any window) + pool markets seen in
    fr = pd.read_parquet(V2 / "pool_frame.parquet", columns=["condition_id", "stratum", "N_s", "n_s"])
    seen = t[["wallet", "condition_id"]].drop_duplicates()
    pc = w[["wallet", "pool_cids"]].explode("pool_cids").rename(columns={"pool_cids": "condition_id"}).dropna()
    seen = pd.concat([seen, pc]).drop_duplicates().merge(fr, on="condition_id")
    seen["lq"] = np.log1p(-seen["n_s"] / seen["N_s"])
    lq = seen.groupby("wallet")["lq"].sum()
    w["m_frame"] = w["wallet"].map(seen.groupby("wallet").size()).fillna(0)
    w["pi_pool"] = 1 - np.exp(w["wallet"].map(lq).fillna(0.0))
    w["weight"] = 1.0 / (w["pi_pool"] * w["q_cls"])
    ok = ~w["heavy"]
    w["eligible"] = ok & (w["n_res"] >= 5)
    w["S1"] = ok & (w["n_res"] == 5) & (w["n_won"] == 5)
    w["S2"] = ok & (w["n_res"] >= 5) & (w["n_won"] == w["n_res"])
    w["z"] = w["sum_edge"] / np.sqrt(w["sum_pv"] + 0.25 * K)
    w["shrunk"] = w["sum_edge"] / (w["n_res"] + K)
    w["S3"] = ok & (w["n_res"] >= 10) & (w["shrunk"] > 0) & (w["z"] >= 2)
    el = w[w["eligible"]]
    cut = wquantile(el["pnl"].to_numpy(), el["weight"].to_numpy(), 0.99)
    cut_unw = float(np.quantile(el["pnl"], 0.99))
    w["S5"] = w["eligible"] & (w["pnl"] >= cut)
    w["u_b1"] = w["wallet"].map(lambda x: u01("b1|" + x))
    b1 = w[w["eligible"]].nsmallest(600, "u_b1")["wallet"]
    w["B1"] = w["wallet"].isin(b1)
    w.drop(columns=["pool_cids"]).to_parquet(V2 / "screens_D.parquet", index=False)
    ev = w[w[["S1", "S2", "S3", "S5", "B1"]].any(axis=1)][["wallet"]]
    ev.to_parquet(V2 / "eval_wallets.parquet", index=False)
    print(f"decisions in trailing window {len(dec):,}; counted resolved {len(r):,}")
    print(f"subset {len(w):,}, heavy {int(w['heavy'].sum())}, eligible {int(w['eligible'].sum())}")
    for s in ["S1", "S2", "S3", "S5", "B1"]:
        x = w[w[s]]
        print(f"  {s}: n={len(x)}  weighted share of eligible={x['weight'].sum() / el['weight'].sum():.4f}"
              f"  unweighted share={len(x) / max(1, len(el)):.4f}")
    print(f"S5 cut (IPW 99th pct) ${cut:,.0f}; unweighted 99th pct ${cut_unw:,.0f}")
    print("eval wallets", len(ev))


if __name__ == "__main__":
    main()
