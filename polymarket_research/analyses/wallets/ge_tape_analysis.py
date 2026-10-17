"""Market-tape analysis for every (wallet, market, entry episode):
price path +-60 min around the episode, price impact of the wallet's own fills, closing-line value,
counterparties (same transaction hash), cross-candidate overlap and same-direction co-traders.

Inputs: ge_fills, ge_dec_episode, ge_markets, ge_tape_<cid10>, ge_tape_taker_<cid10>, ge_prices_1m
Outputs: ge_price_paths.parquet (1-min bins), ge_episode_impact.parquet, ge_counterparties.parquet,
ge_cotraders.parquet

Tape semantics (verified on the data): /v2/trades?condition=..&taker_only=false returns, per settlement tx,
one taker row plus one row per maker order filled; taker_only=true returns exactly one row per tx (the taker).
All prices below are expressed as the price of the wallet's chosen outcome: a trade in the complementary token
at price q maps to 1-q, and its direction is flipped (BUY of the complement = selling pressure on the outcome).
/prices-history values are a trade/mid series, not executable quotes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "derived"
CANDS = {"0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb": "mintblade",
         "0x3f87d51f27ba6e19ec52aaeebb68559a839c742c": "GRIMDRIP",
         "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2": "endlessFate"}


def load_tape(cid: str) -> pd.DataFrame:
    full = pd.read_parquet(OUT / f"ge_tape_{cid[:10]}.parquet")
    tk = pd.read_parquet(OUT / f"ge_tape_taker_{cid[:10]}.parquet")
    key = set(zip(tk.transaction_hash, tk.proxy_wallet, tk["size"].round(6), tk.price.round(6)))
    full["is_taker"] = [k in key for k in zip(full.transaction_hash, full.proxy_wallet, full["size"].round(6), full.price.round(6))]
    return full


def to_outcome(df: pd.DataFrame, tok: str) -> pd.DataFrame:
    same = df.token_id == tok
    df = df.copy()
    df["p_out"] = np.where(same, df.price, 1 - df.price)
    buy_out = (same & (df.side == "BUY")) | (~same & (df.side == "SELL"))
    df["dir_out"] = np.where(buy_out, 1, -1)  # +1 = pressure toward the wallet's outcome
    df["usd"] = df["size"] * df.price
    return df


def last_price(tk: pd.DataFrame, t: float, exclude: str | None = None) -> float:
    x = tk[(tk.timestamp <= t)]
    if exclude:
        x = x[x.proxy_wallet != exclude]
    return float(x.p_out.iloc[-1]) if len(x) else np.nan


def main() -> None:
    fills = pd.read_parquet(OUT / "ge_fills.parquet")
    mk = pd.read_parquet(OUT / "ge_markets.parquet").set_index("conditionId")
    ph = pd.read_parquet(OUT / "ge_prices_1m.parquet")
    paths, imp, cps, cot, cross = [], [], [], [], []
    for (lab, cid, tok), g in fills.groupby(["label", "condition_id", "token_id"]):
        wallet = g.proxy_wallet.iloc[0]
        tape = to_outcome(load_tape(cid), tok).sort_values("timestamp")
        tk = tape[tape.is_taker]
        ko = mk.loc[cid, "gameStartTime"]
        ko = pd.Timestamp(ko).timestamp()
        # --- cross-candidate presence in this market tape
        for addr, nm in CANDS.items():
            n = (tape.proxy_wallet == addr).sum()
            if n:
                cross.append({"market_of": lab, "condition_id": cid, "question": g.question.iloc[0], "candidate": nm, "rows": int(n),
                              "shares": tape.loc[tape.proxy_wallet == addr, "size"].sum()})
        # --- counterparties: rows in the same tx as each wallet fill
        my_tx = set(g.transaction_hash)
        same_tx = tape[tape.transaction_hash.isin(my_tx)]
        role = dict(zip(g.transaction_hash, g.role))
        for tx, rows in same_tx.groupby("transaction_hash"):
            mine = rows[rows.proxy_wallet == wallet]
            others = rows[rows.proxy_wallet != wallet]
            if role.get(tx) == "maker":
                others = others[others.is_taker]  # a maker's counterparty is the tx taker only
            for r in others.itertuples():
                cps.append({"label": lab, "condition_id": cid, "question": g.question.iloc[0], "tx": tx,
                            "wallet_role": role.get(tx), "counterparty": r.proxy_wallet, "cp_name": r.name,
                            "cp_side": r.side, "cp_outcome": r.outcome, "cp_shares": r.size, "cp_price": r.price,
                            "cp_is_candidate": CANDS.get(r.proxy_wallet), "timestamp": r.timestamp})
        # --- per episode metrics
        for eid, e in g.groupby("episode_id"):
            t0, t1 = e.timestamp.min(), e.timestamp.max()
            w = tk[(tk.timestamp >= t0 - 3600) & (tk.timestamp <= t1 + 3600)].copy()
            w["minute"] = (w.timestamp // 60) * 60
            w["is_wallet"] = w.proxy_wallet == wallet
            b = w.groupby("minute").apply(lambda x: pd.Series({
                "vwap_out": (x.p_out * x["size"]).sum() / x["size"].sum(), "last_out": x.p_out.iloc[-1],
                "taker_usd": x.usd.sum(), "wallet_taker_usd": x.loc[x.is_wallet, "usd"].sum(),
                "net_dir_usd": (x.usd * x.dir_out).sum(), "n": len(x)}), include_groups=False).reset_index()
            b["label"], b["episode_id"], b["condition_id"], b["question"], b["outcome"] = lab, eid, cid, e.question.iloc[0], e.outcome.iloc[0]
            b["min_rel_first_fill"] = (b.minute - t0) / 60
            b["min_rel_ko"] = (b.minute - ko) / 60
            hp = ph[(ph.token_id == tok) & (ph.t >= t0 - 3600) & (ph.t <= t1 + 3600)][["t", "p"]].rename(columns={"t": "minute", "p": "clob_prices_history"})
            hp["minute"] = (hp.minute // 60) * 60
            b = b.merge(hp.drop_duplicates("minute"), on="minute", how="outer").sort_values("minute")
            paths.append(b)
            # impact: market price (others' trades) before the first fill vs after the last fill
            p_pre = last_price(tk, t0 - 1, exclude=None)
            p_pre5 = last_price(tk, t0 - 300)
            p_end = last_price(tk, t1)
            post = {h: last_price(tk, t1 + 60 * h, exclude=wallet) for h in (1, 5, 15, 30, 60)}
            p_ko = last_price(tk, ko - 1, exclude=wallet)
            win = tk[(tk.timestamp >= t0) & (tk.timestamp <= t1)]
            my_tk = e[e.role == "taker"]
            # per taker fill slippage vs the last trade price before it (others' trades)
            slips = []
            for r in my_tk.itertuples():
                pb = last_price(tk[tk.proxy_wallet != wallet], r.timestamp - 1)
                po = r.price
                slips.append((po - pb) * r.size)
            same_dir = win[(win.dir_out == 1) & (win.proxy_wallet != wallet)]
            opp_dir = win[(win.dir_out == -1) & (win.proxy_wallet != wallet)]
            vw = (e.notional.sum() / e["size"].sum())
            imp.append({"label": lab, "episode_id": eid, "condition_id": cid, "question": e.question.iloc[0], "outcome": e.outcome.iloc[0],
                        "first_fill": pd.to_datetime(t0, unit="s", utc=True), "last_fill": pd.to_datetime(t1, unit="s", utc=True),
                        "vwap": vw, "p_last_trade_before_first_fill": p_pre, "p_5min_before": p_pre5, "p_at_last_fill": p_end,
                        **{f"p_plus{h}m_others": v for h, v in post.items()}, "p_close_before_ko_others": p_ko,
                        "move_pre_to_end": p_end - p_pre, "clv_close_minus_vwap": p_ko - vw,
                        "drift_end_to_plus30": post[30] - p_end,
                        "wallet_share_of_taker_usd_in_window": win.loc[win.proxy_wallet == wallet, "usd"].sum() / win.usd.sum() if len(win) else np.nan,
                        "wallet_taker_usd": my_tk.notional.sum(), "window_taker_usd_total": win.usd.sum(),
                        "others_same_dir_taker_usd": same_dir.usd.sum(), "others_opp_dir_taker_usd": opp_dir.usd.sum(),
                        "avg_slippage_vs_prev_trade_per_share": (sum(slips) / my_tk["size"].sum()) if len(my_tk) else np.nan,
                        "impact_per_1m_usd": (p_end - p_pre) / (e.notional.sum() / 1e6)})
            # co-traders: other wallets taking the same direction in [t0-10m, t1+10m]
            cw = tk[(tk.timestamp >= t0 - 600) & (tk.timestamp <= t1 + 600) & (tk.proxy_wallet != wallet) & (tk.dir_out == 1)]
            for addr, x in cw.groupby("proxy_wallet"):
                cot.append({"label": lab, "episode_id": eid, "condition_id": cid, "question": e.question.iloc[0], "wallet": addr,
                            "name": x.name.iloc[0], "same_dir_taker_usd": x.usd.sum(), "first_ts": x.timestamp.min(),
                            "is_candidate": CANDS.get(addr)})
    pd.concat(paths).to_parquet(OUT / "ge_price_paths.parquet", index=False)
    imp = pd.DataFrame(imp); imp.to_parquet(OUT / "ge_episode_impact.parquet", index=False)
    cps = pd.DataFrame(cps); cps.to_parquet(OUT / "ge_counterparties.parquet", index=False)
    cot = pd.DataFrame(cot); cot.to_parquet(OUT / "ge_cotraders.parquet", index=False)
    cross = pd.DataFrame(cross); cross.to_parquet(OUT / "ge_cross_candidates.parquet", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 40)
    print(imp.drop(columns=["condition_id"]).round(4).to_string())
    print(cross.to_string())


if __name__ == "__main__":
    main()
