"""Step 5 of the linkage study: trading co-movement between the three wallets, against a baseline of
other large wallets in the same markets.

Data: full market tapes (ge_tape_<cid>.parquet, taker_only=false, all fills incl. maker side; and
ge_tape_taker_<cid>.parquet, taker rows only) for the 13 markets the three wallets traded
(pulled by ge_pull_tapes.py from /v2/trades?condition=, filter_amount=0, cache=True).

Per wallet x market: gross notional, net exposure to outcome index 0 in shares
(BUY outcome0 or SELL outcome1 = +; the reverse = -), first/last fill, taker share.
A wallet is "large" in a match if its gross notional across the match's pulled markets >= $100k.
Baselines:
  B1  KSA-URU: share of large wallets with the same 3-leg direction profile as mintblade/endlessFate.
  B2  All 13 markets: for every pair of large wallets that traded a common market, how often they
      agree in direction on every common market; how often they share a tx hash (traded against each
      other or as co-makers); how close their first entries are.
  B3  Round-number taker orders: share of taker rows with notional within $1 of a multiple of $1,000.
Caveat: the 13 markets were selected because the candidates traded them, so these are conditional baselines.
Outputs: data/derived/linkage_wallet_market.parquet, linkage_pairs.parquet; prints the summary.
"""
from __future__ import annotations

import glob
import itertools

import numpy as np
import pandas as pd

from linkage_common import DERIVED, WALLETS

LARGE = 100_000


def load():
    mk = pd.read_parquet(DERIVED / "ge_markets.parquet")
    mk["cid8"] = mk.conditionId.str[:10]
    tapes, takers = [], []
    for f in sorted(glob.glob(str(DERIVED / "ge_tape_0x*.parquet"))):
        tapes.append(pd.read_parquet(f))
    for f in sorted(glob.glob(str(DERIVED / "ge_tape_taker_0x*.parquet"))):
        takers.append(pd.read_parquet(f))
    t, tk = pd.concat(tapes, ignore_index=True), pd.concat(takers, ignore_index=True)
    for d in (t, tk):
        d["proxy_wallet"] = d.proxy_wallet.str.lower()
        d["notional"] = d["size"] * d["price"]
    # taker flag: a row of the full tape is a taker row if (tx, wallet, token, size, price, side) appears in the taker tape
    key = ["transaction_hash", "proxy_wallet", "token_id", "size", "price", "side"]
    tk["_tk"] = 1
    t = t.merge(tk[key + ["_tk"]].drop_duplicates(key), on=key, how="left")
    t["is_taker"] = t._tk.fillna(0).astype(bool)
    t = t.merge(mk[["conditionId", "match_key", "gameStartTime", "question"]], left_on="condition_id", right_on="conditionId", how="left")
    t["ko"] = (pd.to_datetime(t.gameStartTime, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()
    t["sgn"] = np.where((t.side == "BUY") == (t.outcome_index == 0), 1.0, -1.0)
    return t, tk, mk


def wallet_market(t: pd.DataFrame) -> pd.DataFrame:
    g = t.groupby(["match_key", "condition_id", "question", "proxy_wallet"])
    wm = g.agg(gross=("notional", "sum"), n=("notional", "size"), first_ts=("timestamp", "min"), last_ts=("timestamp", "max"),
               ko=("ko", "first"), taker_notional=("notional", lambda x: x[t.loc[x.index, "is_taker"]].sum())).reset_index()
    t = t.assign(exp0=t.sgn * t["size"])
    wm = wm.merge(t.groupby(["condition_id", "proxy_wallet"]).exp0.sum().reset_index(), on=["condition_id", "proxy_wallet"])
    tot = t.groupby(["condition_id", "proxy_wallet"])["size"].sum().rename("shares").reset_index()
    wm = wm.merge(tot, on=["condition_id", "proxy_wallet"])
    wm["dir"] = np.where(wm.exp0.abs() >= 0.2 * wm.shares, np.sign(wm.exp0), 0)  # 0 = two-sided / market making
    wm["candidate"] = wm.proxy_wallet.map({v: k for k, v in WALLETS.items()})
    return wm


def main() -> None:
    t, tk, mk = load()
    wm = wallet_market(t)
    wm.to_parquet(DERIVED / "linkage_wallet_market.parquet", index=False)
    match_gross = wm.groupby(["match_key", "proxy_wallet"]).gross.sum().rename("match_gross").reset_index()
    wm = wm.merge(match_gross, on=["match_key", "proxy_wallet"])
    large = wm[wm.match_gross >= LARGE]
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)

    # --- candidates' own footprint
    c = wm[wm.candidate.notna()]
    print(c[["candidate", "match_key", "question", "gross", "dir", "first_ts", "last_ts", "ko"]]
          .assign(first_rel_ko_min=lambda d: (d.first_ts - d.ko) / 60, last_rel_ko_min=lambda d: (d.last_ts - d.ko) / 60)
          .drop(columns=["first_ts", "last_ts", "ko"]).to_string())
    cm = c.groupby("candidate").match_key.agg(set)
    for a, b in itertools.combinations(cm.index, 2):
        print("common matches", a, b, sorted(cm[a] & cm[b]))
    txs = t[t.proxy_wallet.isin(WALLETS.values())].groupby("transaction_hash").proxy_wallet.nunique()
    print("tx hashes shared by >=2 candidates across the 13 full tapes:", int((txs > 1).sum()))

    # --- B1: KSA-URU leg profile
    ksa = large[large.match_key == "fifwc-ksa-ury-2026-06-15"]
    prof = ksa.pivot_table(index="proxy_wallet", columns="question", values="dir", aggfunc="first")
    ref = prof.loc[WALLETS["mintblade"]]
    print("\nKSA-URU reference profile (mintblade):", ref.to_dict(), "endlessFate:", prof.loc[WALLETS["endlessFate"]].to_dict())
    full = prof.dropna()
    same3 = (full == ref).all(axis=1)
    print(f"B1 large wallets (>= ${LARGE:,} in the match): {len(prof)}; traded all 3 legs: {len(full)}; "
          f"same 3-leg profile: {int(same3.sum())} ({same3.mean():.1%} of 3-leg traders)")
    for q in prof.columns:
        col = prof[q].dropna()
        print(f"   leg '{q}': {len(col)} large traders, share in reference direction {(col == ref[q]).mean():.1%}")
    s3 = full[same3].index
    first = ksa.groupby("proxy_wallet").first_ts.min()
    ko = ksa.ko.iloc[0]
    print("   same-profile wallets, first fill rel. KO (min):", {WALLETS_INV.get(w, w[:10]): round((first[w] - ko) / 60, 1) for w in s3})
    print("   all 3-leg large wallets, profile and first fill rel. KO (min):")
    print(full.assign(first_rel_ko=((first[full.index] - ko) / 60).round(1), cand=full.index.map(WALLETS_INV)).to_string())
    p_same3 = same3.mean()
    print(f"   P(two random 3-leg large traders share the profile) ~ {p_same3 ** 2 + (1 - p_same3) ** 2:.2f} (if two profiles) ; "
          f"P(both on the reference profile) ~ {p_same3 ** 2:.3f}")

    # --- B2: pairwise agreement among large wallets on common markets (all 13 markets)
    L = large.set_index(["proxy_wallet", "condition_id"])
    by_w = large.groupby("proxy_wallet")
    wallets = list(by_w.groups)
    cond_sets = {w: set(g.condition_id) for w, g in by_w}
    dirs = large.set_index(["proxy_wallet", "condition_id"]).dir.to_dict()
    firsts = large.set_index(["proxy_wallet", "condition_id"]).first_ts.to_dict()
    tx_w = t[t.proxy_wallet.isin(wallets)].groupby("transaction_hash").proxy_wallet.agg(lambda x: tuple(sorted(set(x))))
    tx_w = tx_w[tx_w.map(len) > 1]
    pair_tx = {}
    for ws in tx_w:
        for a, b in itertools.combinations(ws, 2):
            pair_tx[(a, b)] = pair_tx.get((a, b), 0) + 1
    rows = []
    for a, b in itertools.combinations(sorted(wallets), 2):
        com = cond_sets[a] & cond_sets[b]
        if not com:
            continue
        agree = [dirs[(a, cc)] == dirs[(b, cc)] and dirs[(a, cc)] != 0 for cc in com]
        gaps = [abs(firsts[(a, cc)] - firsts[(b, cc)]) / 60 for cc in com]
        rows.append({"a": a, "b": b, "n_common": len(com), "n_agree": sum(agree), "all_agree": all(agree),
                     "min_entry_gap_min": min(gaps), "shared_tx": pair_tx.get((a, b), 0)})
    pr = pd.DataFrame(rows)
    pr["cand_pair"] = [(WALLETS_INV.get(a), WALLETS_INV.get(b)) for a, b in zip(pr.a, pr.b)]
    pr.to_parquet(DERIVED / "linkage_pairs.parquet", index=False)
    print(f"\nB2 pairs of large wallets sharing >=1 market: {len(pr):,}")
    for k in [1, 2, 3]:
        sub = pr[pr.n_common >= k]
        print(f"   n_common>={k}: pairs {len(sub):,}; all-agree {sub.all_agree.mean():.1%}; "
              f"all-agree & first entries within 60 min on some market {(sub.all_agree & (sub.min_entry_gap_min <= 60)).mean():.1%}; "
              f"share a tx {(sub.shared_tx > 0).mean():.1%}")
    sub = pr[(pr.n_common >= 3)]
    print("   pairs with >=3 common markets that all agree:", int(sub.all_agree.sum()), "of", len(sub))
    print(pr[pr.cand_pair.map(lambda x: any(x))].sort_values("n_common", ascending=False).head(10).to_string())
    mbef = pr[(pr.cand_pair == ("mintblade", "endlessFate")) | (pr.cand_pair == ("endlessFate", "mintblade"))]
    print("mintblade-endlessFate pair:", mbef.to_dict("records"))
    # rank of the candidate pair among all >=3-common pairs by entry gap
    if len(mbef):
        g0 = mbef.min_entry_gap_min.iloc[0]
        s = pr[(pr.n_common >= 3) & pr.all_agree]
        print(f"   among {len(s)} all-agreeing pairs with >=3 common markets, share with min entry gap <= {g0:.1f} min: "
              f"{(s.min_entry_gap_min <= g0).mean():.1%}")

    # --- B3: round-number taker orders
    tk = tk.merge(mk[["conditionId", "match_key"]], left_on="condition_id", right_on="conditionId", how="left")
    tk["round1k"] = (tk.notional >= 1000) & ((tk.notional - (tk.notional / 1000).round() * 1000).abs() <= 1.0)
    tw = tk.groupby("proxy_wallet").agg(n=("notional", "size"), big=("notional", lambda x: (x >= 1000).sum()),
                                        round1k=("round1k", "sum"), gross=("notional", "sum"))
    tw = tw[tw.gross >= LARGE]
    tw["round_share"] = tw.round1k / tw.big.clip(lower=1)
    tw["candidate"] = tw.index.map(WALLETS_INV)
    print(f"\nB3 large takers (>= ${LARGE:,} taker notional in these markets): {len(tw)}; median round-$1k share "
          f"{tw.round_share.median():.1%}; share of takers with round share >= 50%: {(tw.round_share >= 0.5).mean():.1%}; "
          f">= 80%: {(tw.round_share >= 0.8).mean():.1%} ({int((tw.round_share >= 0.8).sum())} wallets)")
    print(tw[tw.candidate.notna()][["candidate", "n", "big", "round1k", "round_share", "gross"]].to_string())


WALLETS_INV = {v: k for k, v in WALLETS.items()}

if __name__ == "__main__":
    main()
