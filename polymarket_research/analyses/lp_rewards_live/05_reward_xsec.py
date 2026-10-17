"""Reward economics of a hypothetical two-sided quote ($500/$2,500/$10,000) on the reward cross-section.
Usage: python -m analyses.lp_rewards_live.05_reward_xsec s0 [s1 ...]  -> data/derived/lp_rewards_live/xsec_reward_est.parquet
All amounts are liquidity REWARDS (discretionary incentive), not trading P&L.
"""
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
import lp  # noqa: E402
OUT = ROOT / "data/derived/lp_rewards_live"
CAPS = (500, 2500, 10000)
VARIANTS = {"primary": dict(mid_mode="cum", variant="join", level_filter=False),
            "mid_level": dict(mid_mode="level", variant="join", level_filter=False),
            "mid_plain": dict(mid_mode="plain", variant="join", level_filter=False),
            "improve": dict(mid_mode="cum", variant="improve", level_filter=False),
            "lvl_filter": dict(mid_mode="cum", variant="join", level_filter=True)}


def main(tags):
    x = pd.read_parquet(OUT / "xsec_markets.parquet")
    x = x.drop_duplicates("yes_token").set_index("yes_token")
    rows = []
    for tag in tags:
        bk = pd.read_parquet(OUT / f"xsec_books_{tag}.parquet")
        for _, b in bk.iterrows():
            if b.asset_id not in x.index:
                continue
            m = x.loc[b.asset_id]
            bids, asks = [tuple(t) for t in json.loads(b.bids)], [tuple(t) for t in json.loads(b.asks)]
            v, ms, rate = float(m.rewards_max_spread or 0), float(m.rewards_min_size or 0), float(m.total_daily_rate or 0)
            base = {"tag": tag, "snap_utc": b.snap_utc, "condition_id": m.condition_id, "stratum": m.stratum, "fee_type": m.fee_type,
                    "rate": rate, "v": v, "min_size": ms, "tick": b.tick, "volume_24hr": m.volume_24hr,
                    "best_bid": bids[0][0] if bids else np.nan, "best_ask": asks[0][0] if asks else np.nan,
                    "question": m.question if isinstance(m.question, str) else m.g_question}
            for vn, kw in VARIANTS.items():
                for cap in CAPS:
                    if vn != "primary" and cap != 2500:
                        continue
                    r = lp.reward_estimate(bids, asks, b.tick, v, ms, rate, cap, **kw)
                    if r is None:
                        rows.append({**base, "variant": vn, "capital": cap, "scorable": False}); continue
                    rows.append({**base, "variant": vn, "capital": cap, "scorable": True, **r})
    d = pd.DataFrame(rows)
    d["spread"] = d.best_ask - d.best_bid
    d["yield_cen"] = d.rew_cen / d.capital
    d["yield_con"] = d.rew_con / d.capital
    d["r1_pass"] = (d.rew_cen >= 2) & (d.yield_cen >= 0.0005)
    d.to_parquet(OUT / "xsec_reward_est.parquet", index=False)
    p = d[(d.variant == "primary")]
    print("rows", len(d), "markets", p.condition_id.nunique(), "scorable share", round(p.scorable.mean(), 3))
    for cap in CAPS:
        q = p[(p.capital == cap) & p.scorable]
        print(f"cap {cap}: eligible {q.eligible.mean():.2f}  median rew_cen ${q.rew_cen.median():.3f} p90 ${q.rew_cen.quantile(.9):.2f} "
              f"median yield_cen {q.yield_cen.median()*1e4:.2f}bp/d  R1 pass {q.r1_pass.mean():.3f}  median share_cen {q.share_cen.median():.4f}")


if __name__ == "__main__":
    main(sys.argv[1:])
