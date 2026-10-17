"""Step 8 of the linkage study: which other Polymarket accounts send money to the same Binance deposit addresses?

linkage_07 showed that Binance deposit address A (0xb08b…317d, Etherscan tag 'Binance Deposit', funded by
'Binance: Deposit Funder 1') received Relay withdrawals from mintblade (direct), GRIMDRIP and endlessFate (via one
single-purpose hop each) and from six other Polymarket accounts; deposit address B (0x3319…b072) received from
endlessFate (direct, Polygon/BNB) and mintblade (via its hop).
Here:
  1. Relay requests of LEEEROYJENKINS (the style-identical co-trader in grimdrip_endlessfate.md) -> recipients.
  2. Non-Relay EOA senders into A that were themselves funded by Relay fills: resolve those fills by tx hash.
  3. For every Polymarket account found: Gamma profile (createdAt, user id), /v2/user-stats (distinct markets,
     realised market P&L, fees, rebates), first/last trade and the World Cup events traded (Data API /v2/trades).
Output: data/derived/linkage_extended_cluster.parquet
"""
from __future__ import annotations

import time

import pandas as pd

from linkage_03_bridges import flat, relay_requests
from linkage_07_sinks import RELAY_SOLVER, ZERO, relay_by_hash
from linkage_common import DERIVED, WALLETS, request_json
from pmr import api  # noqa: E402  (linkage_common puts the project root on sys.path)

LEEEROY = "0x99aea8f9a64d0142b6b66a4b9d02a2211d45386f"
SINK_A = "0xb08b85827f803c37b5a3163ec1f03ce6b21e317d"
SINK_B = "0x33193e1592ff490f21f15bd877736aacf3cbb072"


def gamma_profile(a: str) -> dict:
    p = request_json("https://gamma-api.polymarket.com/public-profile", {"address": a}, source="gamma", cache=True, retries=2)
    u = (p.get("users") or [{}])[0]
    return {"name": p.get("name"), "pseudonym": p.get("pseudonym"), "created_at": p.get("createdAt"), "user_id": u.get("id")}


def stats(a: str) -> dict:
    s = api.user_stats(a) or {}
    p = s.get("all_time_pnl") or {}
    return {"markets": s.get("trades"), "realized_market_pnl": p.get("realized_market_pnl"), "unrealized_pnl": p.get("unrealized_pnl"),
            "fees_paid": p.get("fees_paid"), "taker_rebate": p.get("taker_rebate"), "maker_rebate": p.get("maker_rebate"),
            "volume": p.get("volume")}


def trades_summary(a: str) -> dict:
    t = pd.DataFrame(api.trades(user=a, taker_only=False))
    if not len(t):
        return {"n_trade_rows": 0}
    ev = t["event_slug"].fillna("") if "event_slug" in t else pd.Series([""] * len(t))
    wc = ev[ev.str.startswith("fifwc-")]
    return {"n_trade_rows": len(t), "first_trade": pd.to_datetime(t.timestamp.min(), unit="s", utc=True),
            "last_trade": pd.to_datetime(t.timestamp.max(), unit="s", utc=True),
            "events": "|".join(sorted(set(ev)))[:600], "n_events": int(ev.nunique()), "n_wc_events": int(wc.nunique())}


def main() -> None:
    accounts: dict[str, set] = {}
    # 1. LEEEROYJENKINS withdrawals
    lj = pd.DataFrame([flat(r, LEEEROY) for r in relay_requests(LEEEROY)])
    if len(lj):
        lj.to_parquet(DERIVED / "linkage_relay_requests_leeeroy.parquet", index=False)
        print("LEEEROY relay requests:", len(lj))
        print(lj.groupby(["status", "in_chain", "out_chain", "recipient"]).agg(n=("id", "size"), amt=("amt_out", "sum"),
                                                                              t0=("created_at", "min")).to_string())
        for rc in set(lj.recipient) & {SINK_A, SINK_B}:
            accounts.setdefault(LEEEROY, set()).add(f"direct->{rc[:6]}")
    # 2. accounts withdrawing straight into A or B (linkage_07), and Relay-funded senders into A
    s = pd.read_parquet(DERIVED / "linkage_sink_inflows.parquet")
    for u, node in zip(s.relay_user, s.node):
        if isinstance(u, str) and u:
            accounts.setdefault(u, set()).add(node)
    bt = pd.read_parquet(DERIVED / "linkage_sink_backtrace.parquet")
    bt = bt[bt.counterparty.isin([RELAY_SOLVER, ZERO])]
    for tx, hop in zip(bt.tx, bt.set_addr):
        r = relay_by_hash(tx)
        time.sleep(3)
        if r.get("relay_user"):
            accounts.setdefault(r["relay_user"], set()).add(f"via-hop {hop[:10]}->sinkA")
            print("hop", hop[:10], "funded by Relay request of", r["relay_user"], r.get("relay_amt_in"))
    rows = []
    for a, how in accounts.items():
        try:
            prof = gamma_profile(a)
        except RuntimeError:
            prof = {}
        row = {"wallet": a, "candidate": {v: k for k, v in WALLETS.items()}.get(a), "how": "|".join(sorted(how)), **prof}
        try:
            row.update(stats(a))
            row.update(trades_summary(a))
        except RuntimeError as err:
            row["err"] = str(err)[:120]
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_parquet(DERIVED / "linkage_extended_cluster.parquet", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 40)
    print(df.drop(columns=["events"], errors="ignore").sort_values("created_at").to_string())


if __name__ == "__main__":
    main()
