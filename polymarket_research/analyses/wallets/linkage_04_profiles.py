"""Step 4 of the linkage study: how informative are the profile-creation coincidences?

mintblade (user id 8422116, createdAt 2026-06-02T14:47:45Z) and GRIMDRIP (8422276, 15:01:41Z) were
created 14 minutes apart. To calibrate, count every Deposit Wallet the factory deployed in that window
(factory event emitted in each deployment tx, read from the deployment receipts found in linkage_01)
and look up the Gamma public profile of each, giving the number of accounts created in the same
14 minutes and the user-id increment per account.
Outputs: data/derived/linkage_profile_window.parquet
"""
from __future__ import annotations

import pandas as pd

from linkage_common import DERIVED, WALLETS, archive, receipt, request_json, unpad

FACTORY = "0x00000000000fb5c9adea0298d729a0cb3823cc07"
GAMMA = "https://gamma-api.polymarket.com/public-profile"


def main() -> None:
    sg = pd.read_parquet(DERIVED / "linkage_batch_signers.parquet")
    dep = sg[sg.status != "ok"].set_index("label").tx.to_dict()  # deployment txs (selector 0x77835641)
    rc = {k: receipt(t) for k, t in dep.items()}
    ftopic = [lg["topics"][0] for lg in rc["mintblade"]["logs"] if lg["address"].lower() == FACTORY][0]
    blocks = {k: int(r["blockNumber"], 16) for k, r in rc.items()}
    print("factory deploy topic", ftopic, blocks)
    b0, b1 = blocks["mintblade"] - 3_000, blocks["GRIMDRIP"] + 3_000  # ~75 min either side
    logs = []
    for s in range(b0, b1 + 1, 2_000):
        logs += archive("eth_getLogs", [{"address": FACTORY, "fromBlock": hex(s), "toBlock": hex(min(s + 1_999, b1)), "topics": [ftopic]}])
    rows = [{"block": int(lg["blockNumber"], 16), "wallet": unpad(lg["topics"][1]), "owner": unpad(lg["topics"][2]),
             "tx": lg["transactionHash"]} for lg in logs]
    df = pd.DataFrame(rows).drop_duplicates("wallet")
    # block timestamps by linear interpolation between the two end blocks (Polygon ~1.5 s blocks; error < a few s)
    t0 = int(archive("eth_getBlockByNumber", [hex(b0), False])["timestamp"], 16)
    t1 = int(archive("eth_getBlockByNumber", [hex(b1), False])["timestamp"], 16)
    df["ts"] = pd.to_datetime(t0 + (df.block - b0) * (t1 - t0) / (b1 - b0), unit="s", utc=True).dt.round("s")
    # Gamma lookups: every wallet deployed between the two candidates, plus every 4th one outside
    lo, hi = blocks["mintblade"], blocks["GRIMDRIP"]
    df = df.sort_values("block").reset_index(drop=True)
    look = df[((df.block >= lo) & (df.block <= hi)) | (df.index % 4 == 0)]
    prof = []
    for a in look.wallet:
        try:
            p = request_json(GAMMA, {"address": a}, source="gamma", cache=True)
        except RuntimeError as e:
            p = {"error": str(e)[:80]}
        u = (p.get("users") or [{}])[0] if isinstance(p, dict) else {}
        prof.append({"wallet": a, "created_at": p.get("createdAt") if isinstance(p, dict) else None, "user_id": u.get("id"),
                     "name": p.get("name") if isinstance(p, dict) else None, "pseudonym": p.get("pseudonym") if isinstance(p, dict) else None})
    df = df.merge(pd.DataFrame(prof), on="wallet", how="left")
    df["user_id"] = pd.to_numeric(df.user_id, errors="coerce")
    df["candidate"] = df.wallet.map({v: k for k, v in WALLETS.items()})
    df.to_parquet(DERIVED / "linkage_profile_window.parquet", index=False)

    m, g = df[df.candidate == "mintblade"].iloc[0], df[df.candidate == "GRIMDRIP"].iloc[0]
    inwin = df[(df.block >= m.block) & (df.block <= g.block)]
    print(f"deposit wallets deployed {m.ts} .. {g.ts} (inclusive): {len(inwin)}; "
          f"per minute over the whole pulled window: {len(df) / ((df.ts.max() - df.ts.min()).total_seconds() / 60):.1f}")
    ids = inwin.user_id.dropna()
    print("profiles found for in-window wallets:", ids.notna().sum(), "user_id range", ids.min(), ids.max(),
          "id gap mint->grim", g.user_id - m.user_id)
    d = df.dropna(subset=["user_id"]).sort_values("block")
    sl = (d.user_id.diff() / d.block.diff()).median()
    print("median user_id increment per deployed wallet (consecutive):", (d.user_id.diff()).median(), "per block", sl)
    print("named (non-default) profiles in window:", inwin.name.notna().sum(), "of", len(inwin))
    print(inwin[["ts", "wallet", "user_id", "name", "pseudonym", "candidate"]].head(60).to_string())


if __name__ == "__main__":
    main()
