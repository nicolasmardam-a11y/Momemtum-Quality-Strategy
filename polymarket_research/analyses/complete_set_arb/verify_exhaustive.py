"""Check Gamma-based exhaustiveness of neg-risk groups against the on-chain question count (read-only eth_call).

Run from polymarket_research/:  python -m analyses.complete_set_arb.verify_exhaustive [n_random]
For every group that ever produced a positive (c) candidate, plus a random sample of n_random groups that the
scanner marked exhaustive, compares NegRiskAdapter.getQuestionCount(negRiskMarketID) with the number of Gamma
markets in the group (open + closed returned by the events keyset). A mismatch means the on-chain complete set
contains questions the scanner did not price, so a buy-all-YES (c) basket would not be a complete set.
Writes data/derived/complete_set_arb_qcount.parquet.
"""
from __future__ import annotations

import glob
import json
import random
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402

D = ROOT / "data" / "derived" / "complete_set_arb"
AD = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"


def main(n_random: int = 120):
    qsel = api.rpc("web3_sha3", ["0x" + b"getQuestionCount(bytes32)".hex()])[:10]
    gl = sorted(glob.glob(str(D / "scan_*_groups.parquet")))
    g = pd.concat([pd.read_parquet(f, columns=["nr_id", "n_members", "n_trad", "n_closed", "n_placeholder", "n_other",
                                                "exhaustive", "aug", "c_edge0", "event_title", "scan_id"]) for f in gl])
    last = g.sort_values("scan_id").drop_duplicates("nr_id", keep="last")
    cand_ids = set(g[(g.c_edge0 > 0)].nr_id)
    exh = last[last.exhaustive & ~last.nr_id.isin(cand_ids)].nr_id.tolist()
    random.seed(17)
    sample = random.sample(exh, min(n_random, len(exh)))
    rows = []
    for gid in sorted(cand_ids) + sample:
        r = last[last.nr_id == gid].iloc[0]
        try:
            qc = int(api.rpc("eth_call", [{"to": AD, "data": qsel + gid[2:]}, "latest"]), 16)
        except Exception as ex:  # noqa: BLE001
            qc = None
            print("eth_call error", gid[:12], repr(ex)[:120])
        rows.append({"nr_id": gid, "event_title": r.event_title, "c_candidate": gid in cand_ids,
                     "scanner_exhaustive": bool(r.exhaustive), "aug": bool(r.aug), "n_members_gamma": int(r.n_members),
                     "n_trad": int(r.n_trad), "n_closed": int(r.n_closed), "q_onchain": qc,
                     "match": qc == int(r.n_members) if qc is not None else None})
    df = pd.DataFrame(rows)
    df.to_parquet(ROOT / "data" / "derived" / "complete_set_arb_qcount.parquet", index=False)
    for lab, x in df.groupby(["c_candidate", "scanner_exhaustive"]):
        print(lab, "groups", len(x), "on-chain count == Gamma members:", int(x.match.fillna(False).sum()),
              "on-chain > Gamma:", int((x.q_onchain > x.n_members_gamma).sum()))
    cc = df[df.c_candidate & df.scanner_exhaustive]
    print(cc[["event_title", "n_members_gamma", "n_trad", "n_closed", "q_onchain", "match"]].to_string()[:3000])


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 120)
