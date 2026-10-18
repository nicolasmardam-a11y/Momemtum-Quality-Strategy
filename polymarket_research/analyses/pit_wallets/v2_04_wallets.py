"""Stage 3, step 4: wallet trade histories from Data API v2 (/v2/trades?user=..., user shape honours start/end).

Run from polymarket_research/:
  PMR_RATE_SCALE=1.5 python analyses/pit_wallets/v2_04_wallets.py trail [max_seconds]   # subset wallets, pre-D data
  PMR_RATE_SCALE=1.5 python analyses/pit_wallets/v2_04_wallets.py eval  [max_seconds]   # eval wallets, D .. 2026-10-01
Windows (taker_only=false, i.e. maker and taker fills):
  trail: [2025-06-01, 2026-06-01) capped at 20 pages (20,000 fills); plus pre: [full history start=1, 2025-06-01)
         capped at 3 pages (newest 3,000 pre-window fills; used only to tell whether an event was traded before).
  eval:  [2026-06-01, 2026-10-01) capped at 30 pages.
Output: chunked parquet (one file per 40 wallets) under data/derived/pit_wallets/v2/wallets_<mode>/, status TSV.
Wallet lists: wallet_subset.parquet (trail) and eval_wallets.parquet (eval), both fixed before any eval data.
"""
from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from v2common import T_D, T_EVAL1, T_TRAIL0, TRADE_KEEP_USER, V2, to_df, walk  # noqa: E402

LOCK = threading.Lock()
CH = 40


def pull(w: str, mode: str) -> tuple[pd.DataFrame, dict]:
    p = {"user": w, "taker_only": "false"}
    if mode == "trail":
        r1, c1, g1 = walk("/v2/trades", {**p, "start": T_TRAIL0, "end": T_D - 1}, 20, TRADE_KEEP_USER)
        # heavy wallets (trailing cap hit) are excluded from the screens, so their pre-window is not needed
        r0, c0, g0 = ([], False, 0) if c1 else walk("/v2/trades", {**p, "start": 1, "end": T_TRAIL0 - 1}, 3, TRADE_KEEP_USER)
        d1, d0 = to_df(r1, TRADE_KEEP_USER), to_df(r0, TRADE_KEEP_USER)
        d1["win"], d0["win"] = 1, 0
        df = pd.concat([d0, d1], ignore_index=True)
        st = {"wallet": w, "n_trail": len(d1), "capped_trail": int(c1), "n_pre": len(d0), "capped_pre": int(c0),
              "pages": g0 + g1}
    else:
        r2, c2, g2 = walk("/v2/trades", {**p, "start": T_D, "end": T_EVAL1 - 1}, 30, TRADE_KEEP_USER)
        df = to_df(r2, TRADE_KEEP_USER)
        df["win"] = 2
        st = {"wallet": w, "n_eval": len(df), "capped_eval": int(c2), "pages": g2}
    df["wallet"] = w
    return df, st


def run_chunk(ws: list[str], mode: str, d: Path, stp: Path, k: int) -> None:
    dfs, sts = [], []
    for w in ws:
        df, st = pull(w, mode)
        dfs.append(df)
        sts.append(st)
    pd.concat(dfs, ignore_index=True).to_parquet(d / f"chunk_{k:05d}.parquet", index=False, compression="zstd")
    with LOCK:
        new = not stp.exists()
        pd.DataFrame(sts).assign(chunk=k).to_csv(stp, sep="\t", index=False, header=new, mode="a")


def main() -> None:
    mode = sys.argv[1]
    tmax = float(sys.argv[2]) if len(sys.argv) > 2 else 480.0
    src = "wallet_subset.parquet" if mode == "trail" else "eval_wallets.parquet"
    ws = pd.read_parquet(V2 / src, columns=["wallet"])["wallet"].tolist()
    d = V2 / f"wallets_{mode}"
    d.mkdir(exist_ok=True)
    stp = V2 / f"wallets_{mode}_status.tsv"
    prev = pd.read_csv(stp, sep="\t") if stp.exists() else pd.DataFrame(columns=["wallet", "chunk"])
    done_w = set(prev["wallet"])
    ws = [w for w in ws if w not in done_w]  # resumable by wallet, so the wallet list may grow (nested subsets)
    k0 = int(prev["chunk"].max()) + 1 if len(prev) else 0
    chunks = [(k0 + k, ws[i:i + CH]) for k, i in enumerate(range(0, len(ws), CH))]
    print(f"{mode}: {len(ws)} wallets, {len(chunks)} chunks to pull", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(16) as ex:
        futs = []
        for k, c in chunks:
            futs.append(ex.submit(run_chunk, c, mode, d, stp, k))
        nd = 0
        for fu in futs:
            fu.result()
            nd += 1
            if nd % 5 == 0:
                print(f"  {nd}/{len(chunks)} chunks {time.time() - t0:.0f}s", flush=True)
            if time.time() - t0 > tmax:
                for f2 in futs:
                    f2.cancel()
                print("time budget reached; rerun to continue", flush=True)
                break
    st = pd.read_csv(stp, sep="\t")
    print(f"status: wallets {len(st)}, pages {int(st['pages'].sum()):,}, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
