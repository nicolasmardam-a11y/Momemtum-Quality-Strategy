"""Step 2: verify OrderFilled semantics against Data API v2 /v2/trades for the same transactions.

Run from polymarket_research/:  python analyses/pit_wallets/01_semantics_check.py
Sample: 4 transactions from 2025-06-10 14:00-14:02 UTC chosen to cover CTF Exchange vs NegRisk
exchange, taker BUY vs SELL, and a MINT-style match (makers buying the complement token).
Writes data/derived/pit_wallets/semantics_check.parquet (one row per CryptoHouse fill, joined to
the matching Data API row when one exists).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
import ch  # noqa: E402
from pmr import api  # noqa: E402
from pmr.http import request_json  # noqa: E402

EXCH = {"0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e": "CTFExchange",
        "0xc5d563a36ae78145c45a50134d48a1215220f80a": "NegRiskCtfExchange"}
TXS = ['0xc4ae4112cac012b94da40cbca9b17a6f34a92614443a4156e314be46d3ad8ef1',
       '0x0c954c8110ef659fdb2095758c59153d2228b68989eb946942e5ea562ae2eb76',
       '0x901d3c9c076b44616467a5859c87193e78603e5c8efa563100bb26630e204eaf',
       '0x5b074aef0bc61fd011bcae6652c45160016d8abf3baa33e9b69b38620cdf603a']
W0, W1 = '2025-06-10 14:00:00', '2025-06-10 14:02:00'
T0, T1 = 1749564000, 1749564120
OUT = ROOT / "data" / "derived" / "pit_wallets"


def main():
    inl = ",".join(f"'{t}'" for t in TXS)
    f = pd.DataFrame(ch.rows(f"""SELECT splitByChar('_', id)[1] tx, id, toUnixTimestamp(timestamp) ts, maker, taker,
        maker_asset_id, taker_asset_id, toString(maker_amount_filled) ma, toString(taker_amount_filled) ta, toString(fee) fee,
        block_number, is_deleted FROM polymarket.orders_filled
        WHERE timestamp >= '{W0}' AND timestamp < '{W1}' AND splitByChar('_', id)[1] IN ({inl}) ORDER BY tx, id"""))
    m = pd.DataFrame(ch.rows(f"""SELECT id tx, toUnixTimestamp(timestamp) ts, maker_asset_id, taker_asset_id,
        toString(maker_amount_filled) ma, toString(taker_amount_filled) ta FROM polymarket.orders_matched
        WHERE timestamp >= '{W0}' AND timestamp < '{W1}' AND id IN ({inl})"""))
    toks = sorted((set(f.maker_asset_id) | set(f.taker_asset_id)) - {"0"})
    tc = pd.DataFrame(ch.rows(f"SELECT id, toString(condition) cond, complement, toString(outcome_index) oi "
                              f"FROM polymarket.token_id_condition WHERE id IN ({','.join(repr(t) for t in toks)})"))
    # --- the rule under test
    f["wallet"] = f.maker
    f["role"] = f.taker.map(lambda t: "taker" if t in EXCH else "maker")
    f["exchange_if_taker_row"] = f.taker.map(EXCH)
    f["side"] = (f.maker_asset_id == "0").map({True: "BUY", False: "SELL"})
    f["token"] = f.maker_asset_id.where(f.maker_asset_id != "0", f.taker_asset_id)
    f["shares"] = (f.ta.astype(float).where(f.side == "BUY", f.ma.astype(float))) / 1e6
    f["usdc"] = (f.ma.astype(float).where(f.side == "BUY", f.ta.astype(float))) / 1e6
    f["price"] = f.usdc / f.shares
    f = f.merge(tc.rename(columns={"id": "token"}), on="token", how="left")
    # --- Data API rows for the same tx
    da = []
    for cond in sorted(f.cond.dropna().unique()):
        p = {"condition": cond, "taker_only": "false", "limit": 1000}
        for page in range(60):
            j = request_json(f"{api.DATA}/v2/trades", p, source="data-api", cache=True)
            d = j.get("data") or []
            da += [x for x in d if x.get("transaction_hash") in TXS]
            cur = (j.get("pagination") or {}).get("next_cursor")
            if not d or not cur or min(x["timestamp"] for x in d) < T0 - 60:
                break
            p["cursor"] = cur
    da = pd.DataFrame(da)
    keep = ["proxy_wallet", "side", "token_id", "condition_id", "size", "price", "timestamp", "outcome", "transaction_hash", "title"]
    da = da[keep] if len(da) else da
    print("CryptoHouse fills:", len(f), " Data API rows for same tx:", len(da))
    # match on (tx, wallet, token, side, size)
    f["size_r"] = f.shares.round(4); f["px_r"] = f.price.round(4)
    da["size_r"] = da["size"].astype(float).round(4); da["px_r"] = da["price"].astype(float).round(4)
    j = f.merge(da.rename(columns={"transaction_hash": "tx", "proxy_wallet": "wallet", "token_id": "token", "side": "da_side",
                                   "price": "da_price", "timestamp": "da_ts"}),
                on=["tx", "wallet", "token", "size_r", "px_r"], how="outer", indicator=True)
    cols = ["tx", "wallet", "role", "exchange_if_taker_row", "side", "da_side", "token", "outcome", "shares", "price", "da_price", "usdc", "_merge"]
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    v = j[cols].copy(); v["tx"] = v.tx.str[:10]; v["wallet"] = v.wallet.str[:10]; v["token"] = v.token.str[:8]
    print(v.to_string())
    print("\nmerge status:", j._merge.value_counts().to_dict())
    both = j[j._merge == "both"]
    print("side agreement:", (both.side == both.da_side).mean(), " max |price diff|:",
          (both.price - both.da_price.astype(float)).abs().max())
    print("\norders_matched rows (one per taker order):")
    print(m.assign(tx=m.tx.str[:10], maker_asset_id=m.maker_asset_id.str[:8], taker_asset_id=m.taker_asset_id.str[:8]).to_string())
    tk = f[f.role == "taker"][["tx", "maker_asset_id", "taker_asset_id", "ma", "ta"]]
    chk = m.merge(tk, on="tx", suffixes=("_m", "_f"))
    chk["mirrored"] = (chk.maker_asset_id_m == chk.taker_asset_id_f) & (chk.ma_m == chk.ta_f) & (chk.ta_m == chk.ma_f)
    print("orders_matched mirrors the taker OrderFilled row (assets/amounts swapped):", chk.mirrored.tolist())
    # conservation per tx: taker shares = sum of maker shares on same token + complement buys (mint) / sells (merge)
    for tx, g in f.groupby("tx"):
        t = g[g.role == "taker"].iloc[0]
        mk = g[g.role == "maker"]
        same = mk[mk.token == t.token]; comp = mk[mk.token != t.token]
        print(tx[:10], "taker", t.side, round(t.shares, 6), "| makers same-token opposite side", round(same.shares.sum(), 6),
              "| makers complement token same side", round(comp.shares.sum(), 6), "| exchange", t.exchange_if_taker_row)
    out = j.drop(columns=["size_r", "px_r"]).copy()
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].astype(str)
    out.to_parquet(OUT / "semantics_check.parquet", index=False)
    print("wrote", OUT / "semantics_check.parquet")


if __name__ == "__main__":
    main()
