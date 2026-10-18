"""Stage 3, step 6: evaluation signals (new decisions 2026-06-01 .. 2026-09-30) and the market lists to price them.

Run from polymarket_research/:  python analyses/pit_wallets/v2_06_eval.py
Signal = a new decision of an eval wallet: the first BUY in an underlying event never traded before in the
wallet's pulled history (pre-window newest 3,000 fills + trailing window + eval window), with t0 in [D, 2026-10-01).
Evaluable = decision market resolved cleanly with t_res < 2026-10-15. Others are counted and excluded.
Outputs: v2/eval_signals.parquet (all new decisions, with an evaluable flag), v2/eval_markets.parquet,
         v2/bench_markets.parquet (benchmark market sample: Poisson PPS by Gamma volume, 75 expected per category4,
         clean markets with t_res in [2026-06-01, 2026-10-15); md5('bench|condition_id') < p_i).
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from v2_05_screens import build_decisions  # noqa: E402
from v2common import T_D, T_EVAL1, T_RESCUT, V2, load_markets, u01, ue_for_rows  # noqa: E402

WC_POS = r"^fifwc-|fifa|world-cup"
WC_NEG = r"t20|cricket|icc|rugby|hockey|baseball|esports|lol-|cs2|valorant|dota|club-world-cup|womens"


def is_wc(slug: pd.Series) -> pd.Series:
    s = slug.fillna("")
    return s.str.contains(WC_POS) & ~s.str.contains(WC_NEG)


def main() -> None:
    m = load_markets(["condition_id", "event_slug", "category4", "t_res", "clean", "pay0", "pay1", "fee_rate_now",
                      "fee_exponent", "sportsMarketType", "volumeNum"])
    scr = pd.read_parquet(V2 / "screens_D.parquet")
    ev = pd.read_parquet(V2 / "eval_wallets.parquet")
    tr = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(V2 / "wallets_trail" / "chunk_*.parquet")))],
                   ignore_index=True)
    tr = tr[tr["wallet"].isin(ev["wallet"])]
    te = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(V2 / "wallets_eval" / "chunk_*.parquet")))],
                   ignore_index=True)
    te = te[(te["timestamp"] >= T_D) & (te["timestamp"] < T_EVAL1)]
    t = pd.concat([tr[tr["timestamp"] < T_D], te], ignore_index=True)
    t["ue"] = ue_for_rows(t["event_slug"], t["condition_id"], m).values
    dec = build_decisions(t, T_D, T_EVAL1)
    # first-second notional and the wallet's own first-second VWAP (benchmark B3, not achievable by a follower)
    t["usd"] = t["size"] * t["price"]
    fs = t[t["side"] == 1].merge(dec[["wallet", "ue", "t0", "condition_id", "outcome_index"]],
                                 on=["wallet", "ue", "condition_id", "outcome_index"])
    fs = fs[fs["timestamp"] == fs["t0"]].groupby(["wallet", "ue"]).agg(fs_usd=("usd", "sum"), fs_sh=("size", "sum"))
    dec = dec.merge(fs, on=["wallet", "ue"], how="left")
    dec["own_px"] = dec["fs_usd"] / dec["fs_sh"]
    dec = dec.merge(m[["condition_id", "event_slug", "category4", "clean", "pay0", "pay1", "t_res_s", "fee_rate_now",
                       "fee_exponent", "sportsMarketType"]], on="condition_id", how="left")
    dec["pay"] = np.where(dec["outcome_index"] == 0, dec["pay0"], dec["pay1"])
    dec["clean"] = dec["clean"].fillna(False).astype(bool)
    dec["evaluable"] = dec["clean"] & (dec["t_res_s"] > 0) & (dec["t_res_s"] < T_RESCUT) & (dec["t_res_s"] > dec["t0"])
    dec["wc"] = is_wc(dec["event_slug"]) & (dec["category4"] == "sports")
    dec["wc_period"] = (dec["t0"] >= 1781136000) & (dec["t0"] < 1784505600)  # 2026-06-11 .. 2026-07-20
    dec = dec.merge(scr[["wallet", "S1", "S2", "S3", "S5", "B1", "weight", "med_usd"]], on="wallet", how="left")
    dec = dec.drop(columns=["pay0", "pay1"])
    dec.to_parquet(V2 / "eval_signals.parquet", index=False)
    em = dec.loc[dec["evaluable"], ["condition_id"]].drop_duplicates()
    em.to_parquet(V2 / "eval_markets.parquet", index=False)
    print(f"eval fills {len(te):,} wallets with eval fills {te['wallet'].nunique()}/{len(ev)}")
    print(f"new decisions {len(dec):,}, evaluable {int(dec['evaluable'].sum()):,}, markets to price {len(em):,}")
    for s in ["S1", "S2", "S3", "S5", "B1"]:
        x = dec[dec[s].fillna(False)]
        print(f"  {s}: signals {len(x):,} evaluable {int(x['evaluable'].sum()):,} wallets {x['wallet'].nunique()} "
              f"ue {x.loc[x['evaluable'], 'ue'].nunique()} wc {int((x['wc'] & x['evaluable']).sum())}")
    # benchmark market sample
    b = m[m["clean"] & (m["t_res_s"] >= T_D) & (m["t_res_s"] < T_RESCUT)].copy()
    b["volumeNum"] = b["volumeNum"].fillna(0.0).clip(lower=0)
    b["p_inc"] = (75 * b["volumeNum"] / b.groupby("category4")["volumeNum"].transform("sum")).clip(upper=1.0)
    b["u"] = b["condition_id"].map(lambda c: u01("bench|" + c))
    bs = b[b["u"] < b["p_inc"]][["condition_id", "category4", "p_inc", "volumeNum"]]
    bs.to_parquet(V2 / "bench_markets.parquet", index=False)
    print("bench markets", bs["category4"].value_counts().to_dict(), "new vs eval", int((~bs["condition_id"].isin(em["condition_id"])).sum()))


if __name__ == "__main__":
    main()
