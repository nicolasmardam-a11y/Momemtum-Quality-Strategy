"""Step 4b: base rate for 'two large accounts were created minutes apart'.

Population: every wallet with >= $100k gross notional in at least one of the candidate matches (full tapes of the
13 markets, linkage_wallet_market.parquet). For each, Gamma /public-profile createdAt and user id (cached).
Counts the share of pairs created within 14 min / 60 min / same UTC day and with user-id gap <= 160, and the number
of such pairs among the large wallets. Caveat: these markets were chosen because the candidates traded them.
Output: data/derived/linkage_profile_baseline.parquet
"""
from __future__ import annotations

import itertools

import pandas as pd

from linkage_common import DERIVED, WALLETS, request_json

INV = {v: k for k, v in WALLETS.items()}


def main() -> None:
    wm = pd.read_parquet(DERIVED / "linkage_wallet_market.parquet")
    mg = wm.groupby(["match_key", "proxy_wallet"]).gross.sum().reset_index()
    large = sorted(mg[mg.gross >= 100_000].proxy_wallet.unique())
    rows = []
    for a in large:
        try:
            p = request_json("https://gamma-api.polymarket.com/public-profile", {"address": a}, source="gamma", cache=True, retries=2)
        except RuntimeError:
            p = {}
        u = (p.get("users") or [{}])[0]
        rows.append({"wallet": a, "name": p.get("name"), "created_at": p.get("createdAt"), "user_id": u.get("id"), "candidate": INV.get(a)})
    df = pd.DataFrame(rows)
    df["ca"] = pd.to_datetime(df.created_at, utc=True, errors="coerce")
    df["user_id"] = pd.to_numeric(df.user_id, errors="coerce")
    df.drop(columns=["ca"]).to_parquet(DERIVED / "linkage_profile_baseline.parquet", index=False)
    d = df.dropna(subset=["ca"])
    pr = []
    for (_, a), (_, b) in itertools.combinations(d.iterrows(), 2):
        gap = abs((a.ca - b.ca).total_seconds()) / 60
        pr.append({"a": a.wallet, "b": b.wallet, "gap_min": gap, "id_gap": abs(a.user_id - b.user_id) if pd.notna(a.user_id) and pd.notna(b.user_id) else None,
                   "same_day": a.ca.date() == b.ca.date(), "cands": tuple(sorted(x for x in (a.candidate, b.candidate) if isinstance(x, str)))})
    p = pd.DataFrame(pr)
    print(f"large wallets: {len(large)}, with profile createdAt: {len(d)}; pairs: {len(p):,}")
    for m in (10, 14, 60, 24 * 60):
        print(f"  pairs created within {m:>5} min: {(p.gap_min <= m).sum():>4} ({(p.gap_min <= m).mean():.2%})")
    print(f"  pairs with user-id gap <= 160: {(p.id_gap <= 160).sum()} ({(p.id_gap <= 160).mean():.2%})")
    print("  wallets created on 2026-06-02:", d[d.ca.dt.date == pd.Timestamp('2026-06-02').date()][["wallet", "name", "created_at", "user_id"]].to_string())
    close = p[p.gap_min <= 14].merge(d[["wallet", "name"]], left_on="a", right_on="wallet").merge(d[["wallet", "name"]], left_on="b", right_on="wallet", suffixes=("_a", "_b"))
    print("  pairs within 14 min:")
    print(close[["name_a", "name_b", "gap_min", "id_gap", "cands"]].to_string())
    print("  creation-month distribution:", d.ca.dt.strftime("%Y-%m").value_counts().sort_index().to_dict())


if __name__ == "__main__":
    main()
