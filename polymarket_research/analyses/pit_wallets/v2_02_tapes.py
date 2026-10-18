"""Stage 3, step 2: pull market trade tapes from Data API v2 (/v2/trades?condition=...).

Run from polymarket_research/:
  PMR_RATE_SCALE=1.5 python analyses/pit_wallets/v2_02_tapes.py pool    # pool sample, taker_only=false (all fills)
  PMR_RATE_SCALE=1.5 python analyses/pit_wallets/v2_02_tapes.py eval    # eval markets, taker_only=true (taker prints)
  PMR_RATE_SCALE=1.5 python analyses/pit_wallets/v2_02_tapes.py bench   # random benchmark markets, taker_only=true
Resumable: one parquet per market in data/derived/pit_wallets/v2/tapes_<kind>/ (written only when complete or capped);
a status table tapes_<kind>_status.tsv records rows, pages and the cap flag.
start/end are ignored for condition-anchored /v2/trades (VERIFIED in notes/platform/data_infrastructure.md), so
every tape is walked from its newest fill backwards.
"""
from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from v2common import TRADE_KEEP_TAPE, V2, to_df, walk  # noqa: E402

CFG = {
    "pool": dict(src="pool_sample.parquet", taker_only="false", cap=150),
    "eval": dict(src="eval_markets.parquet", taker_only="true", cap=200),
    "bench": dict(src="bench_markets.parquet", taker_only="true", cap=200),
}


LOCK = threading.Lock()


def one(cid: str, kind: str, cfg: dict, d: Path, stp: Path) -> None:
    out = d / f"{cid[2:20]}.parquet"
    rows, capped, pages = walk("/v2/trades", {"condition": cid, "taker_only": cfg["taker_only"]}, cfg["cap"], TRADE_KEEP_TAPE)
    df = to_df(rows, TRADE_KEEP_TAPE)
    df.to_parquet(out, index=False, compression="zstd")
    mn = int(df["timestamp"].min()) if len(df) else -1
    with LOCK:
        new = not stp.exists()
        with open(stp, "a") as f:
            if new:
                f.write("condition_id\trows\tpages\tcapped\tmin_ts\n")
            f.write(f"{cid}\t{len(df)}\t{pages}\t{int(capped)}\t{mn}\n")


def main() -> None:
    kind = sys.argv[1]
    cfg = CFG[kind]
    d = V2 / f"tapes_{kind}"
    d.mkdir(exist_ok=True)
    cids = pd.read_parquet(V2 / cfg["src"], columns=["condition_id"])["condition_id"].drop_duplicates().tolist()
    stp = V2 / f"tapes_{kind}_status.tsv"
    done = set(pd.read_csv(stp, sep="\t")["condition_id"]) if stp.exists() else set()
    todo = [c for c in cids if c not in done]
    print(f"{kind}: {len(cids)} markets, {len(todo)} to pull", flush=True)
    t0, n = time.time(), 0
    tmax = float(sys.argv[2]) if len(sys.argv) > 2 else 480.0
    with ThreadPoolExecutor(16) as ex:
        futs = [ex.submit(one, c, kind, cfg, d, stp) for c in todo]
        for fu in as_completed(futs):
            fu.result()
            n += 1
            if n % 50 == 0:
                print(f"  {n}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
            if time.time() - t0 > tmax:
                for f2 in futs:
                    f2.cancel()
                break
    st = pd.read_csv(stp, sep="\t") if stp.exists() else pd.DataFrame()
    left = len([c for c in cids if c not in set(st.get("condition_id", []))])
    print(f"status rows {len(st)}, left {left}, capped {int(st['capped'].sum()) if len(st) else 0}, "
          f"rows {int(st['rows'].sum()) if len(st) else 0:,}, pages {int(st['pages'].sum()) if len(st) else 0:,}, "
          f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
