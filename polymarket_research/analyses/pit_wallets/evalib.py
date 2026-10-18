"""Shared helpers for stage 2 (follower simulation): load signals + follower prices, entry/exit models, fees,
event/week-clustered bootstrap. Used by 17_evaluate.py and 18_portfolio.py.

Conventions (pre-registration section 7 + addendum A10):
  entry models  'fp'    = first taker BUY print by another wallet at >= detection (within 60 min) + 1 tick (0.01)
                'vX'    = VWAP of taker BUY prints by other wallets in [detection, detection + 30 min) accumulated to $X
                extra slippage (0 / 0.005 / 0.01) is added on top of either; prices capped at 0.999.
  detection     t_sig + delay (5 s, 30 s, 2 min, 10 min, 15 min, 60 min) or the next full UTC hour ('poll').
  unfilled      no qualifying print, or detection / first print at or after the resolution-known time r.
  fees          'hist' = on-chain fee field in force (0 on taker fills from 2025-04, ~0 before: fee_field_by_quarter);
                'cur'  = current schedule fee = shares x rate x p(1-p) -> as a fraction of stake rate x (1 - e).
  payoff        hold to resolution (payout 1/0), or exit at the next taker SELL prints after the followed wallet's
                first sale (+ 2 min detection), computed for P signals at the 2-minute delay only.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "pit_wallets"
RES = OUT / "results"
DELAYS = ["5", "30", "120", "600", "900", "3600", "poll"]
MODELS = ["fp", "v100", "v500", "v2500", "v10000"]
SLIPS = [0.0, 0.005, 0.01]
FEES = ["hist", "cur"]
FEE_RATE = {"crypto": 0.07, "sports": 0.05, "politics": 0.04, "other": 0.05}
SCREENS = ["S1", "S1m", "S2", "S3", "S4_sports", "S4_politics", "S4_crypto", "S4_other", "S5"]
B1 = "B1_random_eligible"
SPLITS = ["train", "val", "test"]
WEEK = 604800


def week_of(ts):
    """ISO-week index (weeks start Monday 00:00 UTC)."""
    return (np.asarray(ts, dtype=np.int64) + 3 * 86400) // WEEK


def load_signals() -> tuple[pd.DataFrame, dict]:
    """One row per (signal, screen); F1b rows are copies of P rows with F1b true."""
    info = {}
    s = pd.read_parquet(OUT / "sig_members.parquet")
    info["rows_in"] = len(s)
    bad = s.r <= 0
    info["dropped_no_tres"] = int(bad.sum())
    s = s[~bad].copy()
    f1b = s[(s.stype == "P") & (s.F1b.fillna(False).astype(bool))].copy()
    f1b["stype"] = "F1b"
    s = pd.concat([s, f1b], ignore_index=True)
    fp = pd.read_parquet(OUT / "follower_prices.parquet")
    s = s.merge(fp, on="psid", how="left")
    for d in DELAYS:
        s[f"fgap_{d}"] = s[f"fgap_{d}"].fillna(65535).astype(np.int64)
        for c in ["fpx"] + [m for m in MODELS if m != "fp"] + ["vol30", "vol60"]:
            s[f"{c}_{d}"] = s[f"{c}_{d}"].fillna(0).astype(np.int64)
    ex = pd.read_parquet(OUT / "exit_prices.parquet")
    s = s.merge(ex, on="psid", how="left")
    s["fee_rate"] = s.category.map(FEE_RATE).fillna(0.05).values
    s["week"] = week_of(s.t_sig)
    s["ym"] = pd.to_datetime(s.t_sig, unit="s", utc=True).dt.strftime("%Y%m").astype(int)
    s["p"] = s.p.astype(float)
    return s.reset_index(drop=True), info


def detect_time(s: pd.DataFrame, d: str) -> np.ndarray:
    t = s.t_sig.values.astype(np.int64)
    if d == "poll":
        return (t // 3600 + 1) * 3600
    return t + int(d)


def entry(s: pd.DataFrame, model: str, d: str, slip: float = 0.0):
    """Returns (filled, raw price, entry price incl. slippage, entry time proxy)."""
    det = detect_time(s, d)
    gap = s[f"fgap_{d}"].values
    has_first = gap != 65535
    t_in = det + np.where(has_first, gap, 0)
    if model == "fp":
        raw = s[f"fpx_{d}"].values / 1e4
        ok = has_first & (raw > 0) & (t_in < s.r.values)
        e = np.minimum(0.999, raw + 0.01 + slip)
    else:
        raw = s[f"{model}_{d}"].values / 1e4
        ok = (raw > 0) & (det < s.r.values) & has_first & (t_in < s.r.values)
        e = np.minimum(0.999, raw + slip)
    return ok, raw, e, t_in


def fee_frac(s: pd.DataFrame, e: np.ndarray, fee: str) -> np.ndarray:
    if fee == "hist":
        return np.zeros(len(e))
    return s.fee_rate.values * (1.0 - e)


def roi_hold(s, model, d, slip, fee):
    ok, raw, e, t_in = entry(s, model, d, slip)
    roi = s.p.values / e - 1.0 - fee_frac(s, e, fee)
    return ok, np.where(ok, roi, 0.0), raw, e, t_in


def roi_exit(s, model, slip, fee):
    """Exit-when-the-followed-wallet-sells variant (2-minute delay). Falls back to hold when no sale / no prints."""
    ok, roi_h, raw, e, t_in = roi_hold(s, model, "120", slip, fee)
    col = {"fp": "xfpx", "v100": "x100", "v500": "x500", "v2500": "x2500", "v10000": "x10000"}[model]
    xr = s[col].fillna(0).values / 1e4
    xp = np.maximum(0.0, xr - (0.01 if model == "fp" else 0.0) - slip)
    ts = s.t_sell.fillna(-1).values
    use = ok & (xr > 0) & (ts > t_in) & (ts + 120 < s.r.values)
    fee_out = (s.fee_rate.values * xp * (1 - xp) / e) if fee == "cur" else 0.0
    roi_x = xp / e - 1.0 - fee_frac(s, e, fee) - fee_out
    return ok, np.where(use, roi_x, roi_h), use


# ----------------------------------------------------------------------------------------- bootstrap helpers

def codes_of(keys) -> tuple[np.ndarray, int]:
    c, u = pd.factorize(pd.Series(keys).astype(str))
    return c.astype(np.int64), len(u)


def boot_ratio(codes, num, den, B=2000, seed=0, chunk=100):
    """Cluster bootstrap of sum(num)/sum(den): resample clusters with replacement."""
    nc = int(codes.max()) + 1 if len(codes) else 0
    if nc == 0:
        return np.array([])
    N = np.bincount(codes, weights=num, minlength=nc)
    D = np.bincount(codes, weights=den, minlength=nc)
    rng = np.random.default_rng(seed)
    out = []
    for b0 in range(0, B, chunk):
        idx = rng.integers(0, nc, size=(min(chunk, B - b0), nc))
        dd = D[idx].sum(1)
        out.append(np.where(dd > 0, N[idx].sum(1) / np.where(dd > 0, dd, 1), np.nan))
    return np.concatenate(out)


def boot_diff_joint(codes_a, num_a, den_a, codes_b, num_b, den_b, nc, B=2000, seed=0, chunk=100):
    """Joint cluster bootstrap of ratio_a - ratio_b (clusters shared between groups: union of codes, size nc)."""
    Na = np.bincount(codes_a, weights=num_a, minlength=nc); Da = np.bincount(codes_a, weights=den_a, minlength=nc)
    Nb = np.bincount(codes_b, weights=num_b, minlength=nc); Db = np.bincount(codes_b, weights=den_b, minlength=nc)
    rng = np.random.default_rng(seed)
    out = []
    for b0 in range(0, B, chunk):
        idx = rng.integers(0, nc, size=(min(chunk, B - b0), nc))
        da, db = Da[idx].sum(1), Db[idx].sum(1)
        ra = np.where(da > 0, Na[idx].sum(1) / np.where(da > 0, da, 1), np.nan)
        rb = np.where(db > 0, Nb[idx].sum(1) / np.where(db > 0, db, 1), np.nan)
        out.append(ra - rb)
    return np.concatenate(out)


def p_centred(boot, est):
    """One-sided bootstrap p-value for H1: stat > 0 (null imposed by centring)."""
    b = boot[np.isfinite(boot)]
    if len(b) == 0 or not np.isfinite(est):
        return np.nan
    return float((np.sum(b - est >= est) + 1) / (len(b) + 1))


def ci(boot):
    b = boot[np.isfinite(boot)]
    if len(b) < 10:
        return (np.nan, np.nan)
    return (float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5)))


def holm(p):
    p = np.asarray(p, dtype=float)
    out = np.full(len(p), np.nan)
    ok = np.isfinite(p)
    idx = np.where(ok)[0]
    order = idx[np.argsort(p[idx])]
    m = len(order)
    run = 0.0
    for i, j in enumerate(order):
        run = max(run, min(1.0, (m - i) * p[j]))
        out[j] = run
    return out


# ----------------------------------------------------------------------------------------- fill-selection estimators
# The print-based proxy fills a signal only when other wallets' taker BUY prints follow it. Whether such prints occur
# depends on how the market moves next, so the fill indicator is correlated with the outcome (VERIFIED in stage 2:
# for $2,500 VWAP fills, winners fill up to 2x as often as losers; for first-print fills, losers fill more often in
# several screens). Three estimators are therefore reported (addendum A11):
#   drop  pre-registered: unfilled signals are dropped (ROI over filled signals);
#   ipw   outcome-neutral 'always filled' estimate: filled signals weighted by 1 / fill rate of their class
#         (set, outcome, followed wallet's own first-fill price bucket), i.e. unfilled signals are assumed to have
#         prices like filled signals of the same outcome and own-price bucket;
#   adv   adverse-fill bound: every feasible unfilled LOSER is assumed filled (loses its stake), unfilled winners are
#         not filled (no position). Feasible = detection before the resolution-known time.
ESTS = ["drop", "ipw", "adv"]
OWN_BINS = [0.2, 0.5, 0.8, 0.95]


def own_bucket(s: pd.DataFrame) -> np.ndarray:
    fp = s.first_price.values.astype(float)
    b = np.digitize(np.nan_to_num(fp, nan=-1.0), OWN_BINS)
    b[~np.isfinite(fp) | (fp <= 0)] = -1
    return b


def est_vectors(s: pd.DataFrame, ok: np.ndarray, roi: np.ndarray, d: str, stake: float = 100.0) -> dict:
    """Per-row (pnl, cost) vectors for each estimator; s must be one signal set (one split, type and screen).

    ipw (A12 form): under 'always filled' every feasible LOSER loses its stake whatever its entry price, so all
    feasible losers enter with the mean ROI of filled losers (-1 - fee; -1 if none filled). Filled winners are
    weighted by n_feasible / n_filled of their own-price bucket; winners in buckets without any fill are spread over
    the represented buckets (outcome-level fallback). '_w' holds per-row weights for filled rows (losers weighted at
    outcome level), used to reweight signal-minus-benchmark differences."""
    feas = detect_time(s, d) < s.r.values
    ok = ok & feas
    p1 = s.p.values == 1
    b = own_bucket(s) + 1
    n1b = np.bincount(b[feas & p1], minlength=6).astype(float)
    k1b = np.bincount(b[ok & p1], minlength=6).astype(float)
    rep = k1b > 0
    n1_rep, n1_unrep = n1b[rep].sum(), n1b[~rep].sum()
    scale = (n1_rep + n1_unrep) / n1_rep if n1_rep > 0 else np.nan
    w1 = np.where(ok & p1 & rep[b], n1b[b] / np.maximum(k1b[b], 1) * (scale if np.isfinite(scale) else 0.0), 0.0)
    lose = feas & ~p1
    okl = ok & ~p1
    lose_roi = float(roi[okl].mean()) if okl.any() else -1.0
    n0, k0 = float(lose.sum()), float(okl.sum())
    wl = np.where(okl, n0 / k0 if k0 > 0 else np.nan, 0.0)
    lose_unf = lose & ~ok
    ipw_pnl = stake * roi * w1 + stake * np.where(okl, roi, lose_roi) * lose
    ipw_cost = stake * w1 + stake * lose.astype(float)
    out = {"drop": (stake * roi * ok, stake * ok.astype(float)),
           "ipw": (ipw_pnl, ipw_cost),
           "adv": (stake * roi * ok - stake * lose_unf, stake * (ok | lose_unf).astype(float)),
           "_w": w1 + wl}
    out["_fill_p1"] = float(ok[feas & p1].mean()) if (feas & p1).any() else np.nan
    out["_fill_p0"] = float(ok[lose].mean()) if lose.any() else np.nan
    out["_ipw_cover"] = float(n1_rep / max(1.0, n1_rep + n1_unrep))
    return out


def balanced_keep(s: pd.DataFrame, ok: np.ndarray, d: str, seed: int = 7) -> np.ndarray:
    """'bal' rule for path simulations (A11): within each (split, type, screen, own-price bucket) cell, filled signals of
    the outcome with the higher fill rate are randomly thinned so both outcomes have the same fill rate (the lower
    one). The kept sample has an outcome-independent fill probability and real follower prices."""
    feas = detect_time(s, d) < s.r.values
    ok = ok & feas
    p1 = (s.p.values == 1)
    cell = pd.factorize(pd.Series(s.split.astype(str).values + "|" + s.stype.astype(str).values + "|" +
                                  s.screen.astype(str).values + "|" + own_bucket(s).astype(str)))[0]
    key = cell * 2 + p1
    nf = np.bincount(key, weights=feas.astype(float), minlength=2 * (cell.max() + 1))
    no = np.bincount(key, weights=ok.astype(float), minlength=len(nf))
    fr = np.where(nf > 0, no / np.maximum(nf, 1), np.nan).reshape(-1, 2)
    tgt = np.nanmin(fr, axis=1)
    keep_p = np.where(fr > 0, tgt[:, None] / np.where(fr > 0, fr, 1), 0.0)
    u = np.random.default_rng(seed).random(len(s))
    return ok & (u < keep_p[cell, p1.astype(int)])
