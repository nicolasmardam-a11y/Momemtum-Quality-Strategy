"""Stage 3, step 7: follower prices from the market taker tapes, payoffs, benchmarks.

Run from polymarket_research/:  python analyses/pit_wallets/v2_07_follower.py
For each evaluable signal (wallet w, t0, decision token = condition + outcome_index) and detection time
dt = t0 + d (d = 5 s, 30 s, 2 min, 15 min, 60 min) or the next full UTC hour after t0 ("poll"), using only
taker BUY prints (taker_only=true tape) of the same token by wallets other than w:
  M1  (pre-registered) price of the first print second at >= dt within 60 min (VWAP of that second) + 0.01, cap 0.999
  M2  VWAP of prints in [dt, dt + 30 min) accumulated to $100 / $500 / $2,500 (+0 and +0.01 slippage)
  vol30  taker-buy $ in [dt, dt + 30 min)
A signal whose tape was capped before dt is marked truncated (excluded, counted).
Fee (current schedule of the market): fee = shares x rate x (p(1-p))^exponent. Payoff at resolution.
Benchmark prints (R random entry, FAV favourite rule): every taker BUY print in the eval and benchmark tapes on clean
markets resolved before 2026-10-15, timestamp in [2026-06-01, 2026-10-01), priced at print + 0.01 with the same fee.
Outputs: v2/follower.parquet (signal x delay x model), v2/bench_prints_cells.parquet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from v2common import T_D, T_EVAL1, T_RESCUT, V2, load_markets  # noqa: E402

DELAYS = {"5s": 5, "30s": 30, "2m": 120, "15m": 900, "60m": 3600, "poll": None}
SIZES = [100, 500, 2500]
WEEK = lambda ts: (ts + 3 * 86400) // 604800  # noqa: E731  Monday-based week index


def fee_per_usd(p, rate, ex):
    return rate * (p * (1 - p)) ** ex / p


def load_tape(kind: str, cid: str) -> pd.DataFrame | None:
    f = V2 / f"tapes_{kind}" / f"{cid[2:20]}.parquet"
    if not f.exists():
        return None
    t = pd.read_parquet(f)
    t = t[t["side"] == 1]
    return t.sort_values("timestamp", kind="stable")


def price_signals(sig: pd.DataFrame, st: pd.DataFrame) -> pd.DataFrame:
    cap_min = st.set_index("condition_id")
    out = []
    for cid, g in sig.groupby("condition_id"):
        t = load_tape("eval", cid)
        capped = bool(cap_min.loc[cid, "capped"]) if cid in cap_min.index else True
        min_ts = int(cap_min.loc[cid, "min_ts"]) if cid in cap_min.index else 0
        for r in g.itertuples(index=False):
            base = {"sid": r.sid}
            if t is None:
                for dn in DELAYS:
                    out.append({**base, "delay": dn, "status": "no_tape"})
                continue
            x = t[(t["outcome_index"] == r.outcome_index) & (t["proxy_wallet"] != r.wallet)]
            ts = x["timestamp"].to_numpy()
            px = x["price"].to_numpy()
            sz = x["size"].to_numpy()
            usd = px * sz
            for dn, d in DELAYS.items():
                dt = int(r.t0 + d) if d is not None else int((r.t0 // 3600 + 1) * 3600)
                row = {**base, "delay": dn, "dt": dt}
                if capped and dt < min_ts:
                    row["status"] = "truncated"
                    out.append(row)
                    continue
                i = np.searchsorted(ts, dt, "left")
                if i < len(ts) and ts[i] < dt + 3600:
                    j = np.searchsorted(ts, ts[i], "right")
                    row["m1_raw"] = usd[i:j].sum() / sz[i:j].sum()
                    row["m1_gap"] = int(ts[i] - dt)
                j30 = np.searchsorted(ts, dt + 1800, "left")
                cu = np.cumsum(usd[i:j30])
                cs = np.cumsum(sz[i:j30])
                row["vol30"] = float(cu[-1]) if len(cu) else 0.0
                for X in SIZES:
                    k = np.searchsorted(cu, X, "left")
                    if k < len(cu):
                        prev_u = cu[k - 1] if k > 0 else 0.0
                        prev_s = cs[k - 1] if k > 0 else 0.0
                        shares = prev_s + (X - prev_u) / px[i + k]
                        row[f"m2_{X}"] = X / shares
                row["status"] = "ok"
                out.append(row)
    return pd.DataFrame(out)


def bench_prints(m: pd.DataFrame) -> pd.DataFrame:
    keep = m[m["clean"] & (m["t_res_s"] > 0) & (m["t_res_s"] < T_RESCUT)].set_index("condition_id")
    rows = []
    seen = set()
    for kind in ["eval", "bench"]:
        st = V2 / f"tapes_{kind}_status.tsv"
        if not st.exists():
            continue
        for cid in pd.read_csv(st, sep="\t")["condition_id"]:
            if cid in seen or cid not in keep.index:
                continue
            seen.add(cid)
            t = load_tape(kind, cid)
            if t is None or not len(t):
                continue
            k = keep.loc[cid]
            t = t[(t["timestamp"] >= T_D) & (t["timestamp"] < T_EVAL1) & (t["timestamp"] < k["t_res_s"])]
            t = t[t["outcome_index"].isin([0, 1])]
            if not len(t):
                continue
            pay = np.where(t["outcome_index"] == 0, k["pay0"], k["pay1"])
            p = np.minimum(0.999, t["price"].to_numpy() + 0.01)
            roi = pay / p - 1 - fee_per_usd(p, k["fee_rate_now"], k["fee_exponent"] if pd.notna(k["fee_exponent"]) else 1.0)
            rows.append(pd.DataFrame({"condition_id": cid, "ue": k["ue"], "cat": k["category4"],
                                      "week": WEEK(t["timestamp"].to_numpy()),
                                      "cent": np.clip(np.round(t["price"].to_numpy() * 100), 0, 100).astype(int),
                                      "roi": roi, "src": kind}))
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    m = load_markets(["condition_id", "event_slug", "category4", "t_res", "clean", "pay0", "pay1", "fee_rate_now",
                      "fee_exponent"])
    sig = pd.read_parquet(V2 / "eval_signals.parquet")
    sig = sig[sig["evaluable"]].reset_index(drop=True)
    sig["sid"] = np.arange(len(sig))
    st = pd.read_csv(V2 / "tapes_eval_status.tsv", sep="\t").drop_duplicates("condition_id", keep="last")
    fp = price_signals(sig, st)
    s = sig[["sid", "wallet", "ue", "t0", "t_res_s", "condition_id", "outcome_index", "category4", "pay", "fee_rate_now",
             "fee_exponent", "wc", "wc_period", "S1", "S2", "S3", "S5", "B1", "weight", "own_px", "fs_usd", "med_usd"]]
    fp = fp.merge(s, on="sid")
    fp["fee_exponent"] = fp["fee_exponent"].fillna(1.0)
    fp["m1_px"] = np.minimum(0.999, fp["m1_raw"] + 0.01)
    fp["m1_roi"] = fp["pay"] / fp["m1_px"] - 1 - fee_per_usd(fp["m1_px"], fp["fee_rate_now"], fp["fee_exponent"])
    for X in SIZES:
        for slip, nm in [(0.0, ""), (0.01, "s")]:
            p = np.minimum(0.999, fp[f"m2_{X}"] + slip)
            fp[f"m2{nm}_{X}_roi"] = fp["pay"] / p - 1 - fee_per_usd(p, fp["fee_rate_now"], fp["fee_exponent"])
    fp["m1_roi_nofee"] = fp["pay"] / fp["m1_px"] - 1
    own = fp["own_px"].clip(upper=0.999)
    fp["own_roi"] = fp["pay"] / own - 1 - fee_per_usd(own, fp["fee_rate_now"], fp["fee_exponent"])
    fp.to_parquet(V2 / "follower.parquet", index=False)
    bp = bench_prints(m)
    bp.to_parquet(V2 / "bench_prints.parquet", index=False)
    print(f"signals {len(sig):,}, rows {len(fp):,}; status at 2m: "
          f"{fp[fp['delay'] == '2m']['status'].value_counts().to_dict()}; m1 filled at 2m "
          f"{fp.loc[fp['delay'] == '2m', 'm1_raw'].notna().mean():.3f}")
    print(f"bench prints {len(bp):,} in {bp['condition_id'].nunique():,} markets ({bp['src'].value_counts().to_dict()})")


if __name__ == "__main__":
    main()
