"""Family D historical: per-taker-event reference prices for markouts (pre-registered in notes/strategies/lp_markouts.md §0).

Usage: python analyses/lp_markouts/01_build_markouts.py [chunk ...]   (resumable: skips chunks already written)
Output: data/derived/lp_markouts/mk_NNN.parquet (one per tape chunk), float32 prices in TRADED-token terms.
References: M = CLOB prices-history fidelity-1 series of token 0 (mid / display price, not executable);
            R = print mid = (last ask-side print + last bid-side print)/2 in token-0 terms, from the taker tape itself.
No look-ahead in conditioning variables: everything used for bucketing is strictly before t.
"""
from __future__ import annotations
import glob, os, sys, re, time
import numpy as np, pandas as pd, pyarrow.dataset as ds
sys.path.insert(0, os.getcwd())
from pmr import fees

D = "data/derived"
OUT = f"{D}/lp_markouts"
os.makedirs(OUT, exist_ok=True)
H_M = [60, 300, 3600, 86400]
H_R = [10, 60, 300, 3600, 86400]
M_PRE_MAX_AGE, M_POST_MAX_AGE = 120, 180
R_PRE_MAX_AGE = 600
REL = re.compile(r"CPI|inflation|\bFed\b|FOMC|interest rate|rate cut|rate hike|jobs|payroll|unemployment|GDP", re.I)


def load_meta() -> pd.DataFrame:
    sel = pd.read_parquet(f"{D}/tape_selection.parquet")
    mk = pd.read_parquet(f"{D}/markets_resolved.parquet", columns=[
        "condition_id", "event_id", "cluster_id", "endDate", "closedTime", "gameStartTime", "winner_idx",
        "fee_rate", "fee_rebate_rate", "question", "orderPriceMinTickSize"])
    mk = mk[mk.condition_id.isin(sel.condition_id)].drop_duplicates("condition_id")
    m = sel[["condition_id", "token_id_0", "split", "category", "set"]].merge(mk, on="condition_id", how="left")
    cat = m.category.str.lower()
    m["rate"] = np.where(m.fee_rate.notna(), m.fee_rate, cat.map(fees.TAKER_RATE).fillna(0.05))
    m["rebr"] = np.where(m.fee_rebate_rate.notna(), m.fee_rebate_rate, cat.map(fees.MAKER_REBATE_SHARE).fillna(0.25))
    m["rel_mkt"] = cat.isin(["economics", "finance"]) & m.question.fillna("").str.contains(REL)
    for c in ["endDate", "closedTime", "gameStartTime"]:
        v = pd.to_datetime(m[c], utc=True)
        m[c + "_s"] = ((v - pd.Timestamp(0, tz="UTC")) / pd.Timedelta(seconds=1)).where(v.notna(), np.nan)
    return m.set_index("condition_id")


def last_idx(times: np.ndarray, q: np.ndarray, strict: bool) -> np.ndarray:
    return np.searchsorted(times, q, side="left" if strict else "right") - 1


def print_mid(at, ap, bt, bp, q, strict, max_age):
    """R(q) in token-0 terms; NaN if a side is missing/stale or the proxies are crossed."""
    out = np.full(len(q), np.nan)
    if len(at) == 0 or len(bt) == 0:
        return out
    ia, ib = last_idx(at, q, strict), last_idx(bt, q, strict)
    ok = (ia >= 0) & (ib >= 0)
    ia2, ib2 = np.where(ok, ia, 0), np.where(ok, ib, 0)
    a, b = ap[ia2], bp[ib2]
    ok &= (q - at[ia2] <= max_age) & (q - bt[ib2] <= max_age) & (b <= a)
    out[ok] = 0.5 * (a[ok] + b[ok])
    return out


def series_at(st, sp, q, strict, max_age, after=None):
    out = np.full(len(q), np.nan)
    if len(st) == 0:
        return out
    ix = last_idx(st, q, strict)
    ok = ix >= 0
    ix2 = np.where(ok, ix, 0)
    ok &= (q - st[ix2] <= max_age)
    if after is not None:
        ok &= st[ix2] > after
    out[ok] = sp[ix2][ok]
    return out


def build_market(g: pd.DataFrame, mrow, st, sp) -> pd.DataFrame:
    g = g.sort_values("timestamp", kind="stable")
    t = g.timestamp.to_numpy(np.int64)
    i = g.outcome_index.to_numpy(np.int8)
    d = np.where(g.side.to_numpy() == "BUY", 1, -1).astype(np.int8)
    P = g.price.to_numpy(float)
    q = g["size"].to_numpy(float)
    p0 = np.where(i == 0, P, 1 - P)
    d0 = np.where(i == 0, d, -d)
    a_m, b_m = d0 == 1, d0 == -1
    at, ap, bt, bp = t[a_m], p0[a_m], t[b_m], p0[b_m]
    to_tok = lambda x0: np.where(i == 0, x0, 1 - x0)
    closed = mrow.closedTime_s
    w = mrow.winner_idx
    Y = np.where(np.isnan(w), np.nan, (i == w).astype(float)) if not pd.isna(w) else np.full(len(t), np.nan)
    o = {"t": t, "i": i, "d": d, "P": P.astype(np.float32), "q": q.astype(np.float32), "Y": Y.astype(np.float32)}
    # pre-trade references
    Rpre0 = print_mid(at, ap, bt, bp, t, True, R_PRE_MAX_AGE)
    o["R_pre"] = to_tok(Rpre0).astype(np.float32)
    Mpre0 = series_at(st, sp, t, True, M_PRE_MAX_AGE)
    o["M_pre"] = to_tok(Mpre0).astype(np.float32)
    past = lambda h: (not pd.isna(closed)) & (t + h >= closed) if not pd.isna(closed) else np.zeros(len(t), bool)
    for h in H_R:
        r = to_tok(print_mid(at, ap, bt, bp, t + h, False, max(R_PRE_MAX_AGE, h)))
        pm = past(h)
        r = np.where(pm, Y, r)
        o[f"R_{h}"] = r.astype(np.float32)
    for h in H_M:
        m = to_tok(series_at(st, sp, t + h, False, M_POST_MAX_AGE, after=t))
        pm = past(h)
        m = np.where(pm, Y, m)
        o[f"M_{h}"] = m.astype(np.float32)
    # conditioning (strictly before t)
    Rlag0 = print_mid(at, ap, bt, bp, t - 3600, True, 3600)
    o["vol_1h"] = np.abs(Rpre0 - Rlag0).astype(np.float32)
    cs_s = np.concatenate([[0.0], np.cumsum(d0 * q)])
    cs_q = np.concatenate([[0.0], np.cumsum(q)])
    lo = np.searchsorted(t, t - 3600, "left")
    hi = np.searchsorted(t, t, "left")
    n_prior = hi - lo
    with np.errstate(invalid="ignore", divide="ignore"):
        oi = (cs_s[hi] - cs_s[lo]) / (cs_q[hi] - cs_q[lo])
    oi = np.where(n_prior >= 3, oi, np.nan)
    o["oi_align"] = (d0 * oi).astype(np.float32)
    o["n_prior_1h"] = n_prior.astype(np.int32)
    o["dt_prev"] = np.concatenate([[np.nan], np.diff(t)]).astype(np.float32)
    o["ttr_h"] = ((mrow.endDate_s - t) / 3600).astype(np.float32)
    o["game_h"] = ((t - mrow.gameStartTime_s) / 3600 if not pd.isna(mrow.gameStartTime_s)
                   else np.full(len(t), np.nan)).astype(np.float32)
    o["to_close_h"] = ((closed - t) / 3600 if not pd.isna(closed) else np.full(len(t), np.nan)).astype(np.float32)
    df = pd.DataFrame(o)
    return df


def run_chunk(path: str, meta: pd.DataFrame) -> None:
    n = os.path.basename(path).split("_")[1].split(".")[0]
    out = f"{OUT}/mk_{n}.parquet"
    if os.path.exists(out):
        print("skip", out); return
    t0 = time.time()
    tape = pd.read_parquet(path, columns=["condition_id", "outcome_index", "side", "price", "size", "timestamp"])
    cids = tape.condition_id.unique()
    toks = meta.loc[meta.index.intersection(cids), "token_id_0"].dropna().tolist()
    if toks:
        ser = ds.dataset(f"{D}/price_series_m1.parquet").to_table(
            filter=ds.field("token_id").isin(toks)).to_pandas().sort_values(["token_id", "t"])
    else:
        ser = pd.DataFrame({"token_id": pd.Series([], dtype=str), "t": [], "p": []})
    sg = {k: (v.t.to_numpy(np.int64), v.p.to_numpy(float)) for k, v in ser.groupby("token_id")}
    parts = []
    for cid, g in tape.groupby("condition_id", sort=False):
        if cid not in meta.index:
            continue
        mrow = meta.loc[cid]
        st, sp = sg.get(mrow.token_id_0, (np.array([], np.int64), np.array([])))
        df = build_market(g, mrow, st, sp)
        df.insert(0, "condition_id", cid)
        parts.append(df)
    res = pd.concat(parts, ignore_index=True)
    res["condition_id"] = res.condition_id.astype("category")
    res.to_parquet(out, compression="zstd", index=False)
    print(out, len(res), f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    meta = load_meta()
    meta.drop(columns=["question"]).reset_index().to_parquet(f"{OUT}/market_meta.parquet", index=False)
    chunks = sorted(glob.glob(f"{D}/tapes/tape_*.parquet"))
    if len(sys.argv) > 1:
        chunks = [c for c in chunks if any(c.endswith(f"tape_{int(a):03d}.parquet") for a in sys.argv[1:])]
    for c in chunks:
        run_chunk(c, meta)
