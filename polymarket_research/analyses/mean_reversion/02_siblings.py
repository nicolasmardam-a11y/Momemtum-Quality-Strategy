"""Family F, step 2: sibling-market co-movement at detection time (pre-registered feature, 0.4).

For each distinct theta=10c shock (primary / noband / lookahead variants) in a multi-market event, pull the CLOB
/prices-history minute series (fidelity=1, token_id_0) of up to 8 sibling markets that were live at t_det
(createdAt <= t_det - 300 s, closedTime >= t_det), over [t_det - 900, t_det]. Only points with t <= t_det are used.
Siblings are ranked by full-life volumeNum (a look-ahead in which siblings are looked at, not in the signal).

Resumable: requests are cached (immutable history) and finished chunks are stored in data/derived/mr_sib_parts/.
Run: PMR_RATE_SCALE=2 python analyses/mean_reversion/02_siblings.py [max_chunks]
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

D = ROOT / "data" / "derived"
PARTS = D / "mr_sib_parts"
CHUNK = 150
MAX_SIB = 8


def build_jobs():
    S = pd.read_parquet(D / "mr_shocks.parquet")
    u = S[(S.theta == 0.10)].drop_duplicates(["condition_id", "t_det"])[["condition_id", "event_id", "t_det", "s", "shock"]]
    mr = pd.read_parquet(D / "markets_resolved.parquet",
                         columns=["condition_id", "event_id", "token_id_0", "volumeNum", "closedTime", "createdAt"])
    mr = mr[mr.event_id.isin(set(u.event_id)) & mr.token_id_0.notna()]
    mr["c_s"] = mr.createdAt.map(lambda x: x.timestamp() if pd.notna(x) else -np.inf)
    mr["x_s"] = mr.closedTime.map(lambda x: x.timestamp() if pd.notna(x) else np.inf)
    by_ev = {k: g.sort_values("volumeNum", ascending=False) for k, g in mr.groupby("event_id")}
    jobs = []
    for r in u.itertuples():
        g = by_ev.get(r.event_id)
        if g is None:
            continue
        g = g[(g.condition_id != r.condition_id) & (g.c_s <= r.t_det - 300) & (g.x_s >= r.t_det)].head(MAX_SIB)
        for sr in g.itertuples():
            jobs.append((r.condition_id, int(r.t_det), sr.condition_id, sr.token_id_0))
    return u, pd.DataFrame(jobs, columns=["condition_id", "t_det", "sib_cid", "sib_token"])


def fetch(job):
    cid, t, scid, tok = job
    try:
        h = api.prices_history(tok, t - 900, t, 1, cache=True)
    except Exception as e:  # noqa: BLE001
        return cid, t, scid, np.nan, np.nan, 0, repr(e)[:200]
    pts = sorted((x["t"], x["p"]) for x in h if x["t"] <= t)
    if not pts:
        return cid, t, scid, np.nan, np.nan, 0, None
    ts = np.array([a for a, _ in pts]); ps = np.array([b for _, b in pts], float)
    p_now = ps[-1]
    k = np.searchsorted(ts, t - 300, side="right") - 1
    p_then = ps[k] if k >= 0 else np.nan
    return cid, t, scid, p_now, p_then, len(pts), None


def main(max_chunks=None):
    u, J = build_jobs()
    PARTS.mkdir(exist_ok=True)
    print(f"shocks {len(u)}, sibling jobs {len(J)}", flush=True)
    keys = J[["condition_id", "t_det"]].drop_duplicates().reset_index(drop=True)
    n_chunks = int(np.ceil(len(keys) / CHUNK))
    done = 0
    for c in range(n_chunks):
        f = PARTS / f"part_{c:03d}.parquet"
        if f.exists():
            continue
        if max_chunks is not None and done >= max_chunks:
            break
        kk = keys.iloc[c * CHUNK:(c + 1) * CHUNK]
        jj = J.merge(kk, on=["condition_id", "t_det"])
        t0 = time.time()
        with ThreadPoolExecutor(8) as ex:
            res = list(ex.map(fetch, jj.itertuples(index=False, name=None)))
        R = pd.DataFrame(res, columns=["condition_id", "t_det", "sib_cid", "p_now", "p_then", "n_pts", "error"])
        R.to_parquet(f, index=False)
        done += 1
        print(f"chunk {c}/{n_chunks}: {len(jj)} req, {R.error.notna().sum()} err, {time.time() - t0:.0f}s", flush=True)
    if all((PARTS / f"part_{c:03d}.parquet").exists() for c in range(n_chunks)):
        R = pd.concat([pd.read_parquet(PARTS / f"part_{c:03d}.parquet") for c in range(n_chunks)], ignore_index=True)
        R["d_sib"] = R.p_now - R.p_then
        R = R.merge(u[["condition_id", "t_det", "s", "shock"]], on=["condition_id", "t_det"], how="left")
        agg = R.groupby(["condition_id", "t_det"]).agg(
            n_sib=("sib_cid", "size"), n_sib_priced=("d_sib", lambda x: x.notna().sum()),
            sib_max_abs=("d_sib", lambda x: x.abs().max()), sib_sum=("d_sib", "sum"),
            sib_n3c=("d_sib", lambda x: (x.abs() >= 0.03).sum()), s=("s", "first"), shock=("shock", "first"),
        ).reset_index()
        agg["sib_sum_signed"] = agg.sib_sum * agg.s  # >0: siblings moved the same way as the shocked token 0
        agg["sib_comove"] = np.where(agg.n_sib_priced > 0, agg.sib_n3c > 0, np.nan)
        agg.drop(columns=["s", "shock"]).to_parquet(D / "mr_siblings.parquet", index=False)
        print("written mr_siblings.parquet", len(agg), "errors", R.error.notna().sum())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
