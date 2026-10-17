"""Random-sample coverage + resolution audit of the Gamma universe against the CLOB /markets listing.

CLOB GET /markets is paginated by an opaque cursor that is base64("id:<market id>"); a crafted cursor
returns the next 1,000 markets after that id (verified 2026-10-17). Offsets are stratified by split:
K/3 offsets per split (train / validation / test), each 300 ids below a randomly drawn universe market
of that split (seed 20261017). For each CLOB page we compare
  * coverage A: CLOB markets with closed=true and end_date_iso in [2024-01-01, 2026-10-16) that are
    missing from markets_resolved.parquet (by condition_id);
  * coverage B: universe markets whose Gamma id lies inside the CLOB page's id span but are absent from CLOB;
  * resolution: CLOB tokens[].winner / is_50_50_outcome vs our parsed winner_idx / split_50_50.
Run from polymarket_research/: python analyses/universe/04_audit_clob_sample.py [K]
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

K = int(sys.argv[1]) if len(sys.argv) > 1 else 45
DER = ROOT / "data" / "derived"
LO, HI = "2024-01-01", "2026-10-16"


def main() -> None:
    u = pd.read_parquet(DER / "markets_resolved.parquet",
                        columns=["id", "condition_id", "endDate", "resolution", "winner_idx", "split", "category"])
    u["idn"] = u["id"].astype(int)
    u["condition_id"] = u["condition_id"].str.lower()
    rng = np.random.default_rng(20261017)
    offs = []
    for sp in ["train", "validation", "test"]:
        ids = u.loc[u["split"] == sp, "idn"].to_numpy()
        offs += [(int(x) - 300, sp) for x in rng.choice(ids, size=K // 3, replace=False)]
    offs.sort()
    cond = set(u["condition_id"])
    rows, ab = [], []
    for o, sp in offs:
        cur = base64.b64encode(f"id:{o}".encode()).decode()
        j = request_json(f"{api.CLOB}/markets", {"next_cursor": cur}, source="clob", cache=True)
        nc = j.get("next_cursor")
        hi_id = None
        if nc and nc != "LTE=":
            try:
                hi_id = int(base64.b64decode(nc).decode().split(":")[1])
            except (ValueError, IndexError):
                hi_id = None
        data = j.get("data") or []
        clob_conds = set()
        for m in data:
            c = (m.get("condition_id") or "").lower()
            clob_conds.add(c)
            end = (m.get("end_date_iso") or "")[:10]
            toks = m.get("tokens") or []
            win = [i for i, t in enumerate(toks) if t.get("winner")]
            rows.append({"offset": o, "offset_split": sp, "condition_id": c, "closed": m.get("closed"),
                         "end_date_iso": m.get("end_date_iso"), "in_window": bool(end) and LO <= end < HI,
                         "in_universe": c in cond, "clob_winner_idx": win[0] if len(win) == 1 else None,
                         "clob_n_winners": len(win), "is_50_50": m.get("is_50_50_outcome"),
                         "enable_order_book": m.get("enable_order_book"), "archived": m.get("archived"),
                         "active": m.get("active"), "question": (m.get("question") or "")[:120]})
        if hi_id:
            span = u[(u["idn"] > o) & (u["idn"] <= hi_id)]
            ab.append({"offset": o, "offset_split": sp, "hi_id": hi_id, "n_universe_in_span": len(span),
                       "n_missing_from_clob": int((~span["condition_id"].isin(clob_conds)).sum())})
    r = pd.DataFrame(rows)
    a = pd.DataFrame(ab)
    m = r.merge(u[["condition_id", "resolution", "winner_idx"]], on="condition_id", how="left")
    tgt = m[(m["closed"] == True) & m["in_window"]]  # noqa: E712
    out = {"K_pages": len(offs), "clob_rows": len(r), "by_split": {}}
    for sp, g in tgt.groupby("offset_split"):
        aa = a[a["offset_split"] == sp]
        out["by_split"][sp] = {"clob_closed_in_window": len(g), "missing_from_universe": int((~g["in_universe"]).sum()),
                               "universe_in_spans": int(aa["n_universe_in_span"].sum()),
                               "universe_in_spans_missing_from_clob": int(aa["n_missing_from_clob"].sum())}
    out["clob_closed_in_window"] = len(tgt)
    out["clob_closed_in_window_missing_from_universe"] = int((~tgt["in_universe"]).sum())
    out["clob_open_in_window"] = int(((m["closed"] != True) & m["in_window"]).sum())  # noqa: E712
    both = tgt[tgt["in_universe"]]
    w = both[both["resolution"] == "winner"]
    out["winner_compared"] = len(w)
    out["winner_agree"] = int((w["winner_idx"].astype("float") == w["clob_winner_idx"].astype("float")).sum())
    s = both[both["resolution"] == "split_50_50"]
    out["split_compared"] = len(s)
    out["split_clob_is_50_50"] = int((s["is_50_50"] == True).sum())  # noqa: E712
    out["split_clob_n_winners_dist"] = {str(k): int(v) for k, v in s["clob_n_winners"].value_counts().items()}
    out["clob_is_50_50_but_universe_winner"] = int(((both["is_50_50"] == True) & (both["resolution"] == "winner")).sum())  # noqa: E712
    miss = tgt[~tgt["in_universe"]]
    out["missing_examples"] = miss[["condition_id", "end_date_iso", "question", "enable_order_book", "archived"]].head(15).to_dict("records")
    out["missing_enable_order_book_dist"] = {str(k): int(v) for k, v in miss["enable_order_book"].value_counts(dropna=False).items()}
    dis = w[w["winner_idx"].astype("float") != w["clob_winner_idx"].astype("float")]
    out["winner_disagree_examples"] = dis[["condition_id", "winner_idx", "clob_winner_idx", "clob_n_winners", "question"]].head(15).to_dict("records")
    r.to_parquet(DER / "universe_audit_clob_sample.parquet", index=False)
    (DER / "universe_audit_clob_sample.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
