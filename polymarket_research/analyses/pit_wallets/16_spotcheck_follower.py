"""Stage 2, step 16: independent spot check of the follower execution proxy against Data API /v2/trades.

Run from polymarket_research/:  python analyses/pit_wallets/16_spotcheck_follower.py
For a hash-chosen sample of P signals in small markets (<= 3,000 fills on the token), re-derive from the
Data API taker tape (/v2/trades?condition=..., default taker side) the first BUY trade of the same token by another
wallet at >= t + 120 s (within 60 min) and compare with fpx_120 from CryptoHouse (13_follower_prices.py).
Output: data/derived/pit_wallets/spotcheck_follower.parquet
"""
from __future__ import annotations
import hashlib, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
OUT = ROOT / "data" / "derived" / "pit_wallets"


def main(n=25):
    sm = pd.read_parquet(OUT / "sig_members.parquet", columns=["stype", "psid", "k", "token_id", "wallet", "t_sig"])
    sm = sm[sm.stype == "P"].drop_duplicates("psid")
    fp = pd.read_parquet(OUT / "follower_prices.parquet", columns=["psid", "fpx_120", "fgap_120"])
    tm = pd.read_parquet(OUT / "token_meta_pit.parquet", columns=["k", "condition_id", "n_fills"])
    g = sm.merge(fp, on="psid", how="left").merge(tm, on="k")
    g = g[g.n_fills <= 3000].copy()
    g["h"] = [hashlib.md5(str(x).encode()).hexdigest() for x in g.psid]
    g = g.sort_values("h").head(n)
    out = []
    for r in g.itertuples():
        tr = api.trades(condition=r.condition_id, cache=True)
        x = [t for t in tr if str(t.get("token_id") or t.get("asset")) == r.token_id and t.get("side") == "BUY"
             and r.t_sig + 120 <= int(t["timestamp"]) < r.t_sig + 120 + 3600
             and str(t.get("proxy_wallet") or t.get("proxyWallet")).lower() != r.wallet.lower()]
        x.sort(key=lambda t: int(t["timestamp"]))
        api_px = float(x[0]["price"]) if x else None
        api_gap = int(x[0]["timestamp"]) - r.t_sig - 120 if x else None
        ch_px = (r.fpx_120 / 1e4) if pd.notna(r.fpx_120) and r.fgap_120 != 65535 else None
        out.append(dict(psid=r.psid, n_tape=len(tr), api_px=api_px, api_gap=api_gap, ch_px=ch_px,
                        ch_gap=None if ch_px is None else int(r.fgap_120)))
        print(out[-1], flush=True)
    d = pd.DataFrame(out)
    d.to_parquet(OUT / "spotcheck_follower.parquet", index=False)
    both = d.dropna(subset=["api_px", "ch_px"])
    print("both filled", len(both), "abs diff <= 0.0051:", int(((both.api_px - both.ch_px).abs() <= 0.0051).sum()),
          "same gap:", int((both.api_gap == both.ch_gap).sum()),
          "fill status agrees:", int((d.api_px.isna() == d.ch_px.isna()).sum()), "of", len(d))


if __name__ == "__main__":
    main()
