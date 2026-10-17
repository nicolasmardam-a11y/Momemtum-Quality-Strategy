"""Step 10 of the linkage study: reconcile each wallet's delivered withdrawals to their final on-chain destination.

Inputs: linkage_relay_requests (status=success deliveries of each wallet's withdrawals), linkage_origin_eth (Ethereum
USDC transfers of recipients/hops), linkage_transfers_wdr (Polygon transfers of the same addresses; only the real
USDC / USDC.e contracts are kept -- the many look-alike 'address poisoning' tokens are dropped).
For each wallet: delivered amount per (chain, recipient); for hop recipients whose only inflows are that wallet's
withdrawals, onward transfers per destination. Labels: Etherscan public name tags fetched 2026-10-17
(sink A/B 'Binance Deposit', funded by 'Binance: Deposit Funder 1'; 0xbbfa…4803 untagged, funded by and sweeping to
'Kraken: Hot Wallet 4').
Output: data/derived/linkage_fund_paths.parquet
"""
from __future__ import annotations

import pandas as pd

from linkage_common import DERIVED

NAMES = {"0xb08b85827f803c37b5a3163ec1f03ce6b21e317d": "Binance deposit A 0xb08b…317d",
         "0x33193e1592ff490f21f15bd877736aacf3cbb072": "Binance deposit B 0x3319…b072",
         "0xbbfa4c80f062fdf4a4a7eba84077d0a1ec604803": "Kraken-swept address 0xbbfa…4803",
         "0xa6230f226851a3446a579ca130bbc2b9854fae1c": "hop 0xa623…a1c (mintblade only)",
         "0xac3518db3af76a35ed281a1b25621698fa0d2a89": "hop 0xac35…2a89 (endlessFate only)",
         "0xe065507311074a2e23164f8025c68dd4b9c4a46f": "hop 0xe065…a46f (GRIMDRIP only)",
         "0x4c6d26f63f524d735508d6254aef6ea4184a13bf": "rebate payout 0x4c6d…13bf",
         "0x81160dc6e2c2db1c9b1d5170fe9f487f5c6c14a4": "rebate payout 0x8116…14a4"}
HOP_OF = {"mintblade": "0xa6230f226851a3446a579ca130bbc2b9854fae1c", "endlessFate": "0xac3518db3af76a35ed281a1b25621698fa0d2a89",
          "GRIMDRIP": "0xe065507311074a2e23164f8025c68dd4b9c4a46f"}
REAL_USDC_POLY = {"0x3c499c542cef5e3811e1192ce70d8cc03d5c3359", "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"}


def main() -> None:
    rq = pd.read_parquet(DERIVED / "linkage_relay_requests.parquet")
    w = rq[rq.queried_label.str.endswith(":wallet") & (rq.status == "success")].copy()
    w["wallet"] = w.queried_label.str.split(":").str[0]
    rows = [{"wallet": a, "stage": "1 delivered", "chain": int(c), "to": r, "to_name": NAMES.get(r, r), "amount": x}
            for (a, c, r), x in w.groupby(["wallet", "out_chain", "recipient"]).amt_out.sum().items()]
    eth = pd.read_parquet(DERIVED / "linkage_origin_eth.parquet")
    eth = eth[(eth.token == "USDC") & (eth.dir == "out")]
    pol = pd.read_parquet(DERIVED / "linkage_transfers_wdr.parquet")
    pol = pol[(pol.kind == "erc20") & (pol.dir == "out") & pol.contract.isin(REAL_USDC_POLY)]
    for wal, hop in HOP_OF.items():
        for chain, d in ((1, eth[eth.set_addr == hop]), (137, pol[pol.set_addr == hop])):
            for to, x in d.groupby("to" if "to" in d else "counterparty").amount.sum().items():
                rows.append({"wallet": wal, "stage": "2 onward from hop", "chain": chain, "to": to, "to_name": NAMES.get(to, to), "amount": x})
    df = pd.DataFrame(rows)
    df.to_parquet(DERIVED / "linkage_fund_paths.parquet", index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 44)
    df["amount_m"] = (df.amount / 1e6).round(3)
    print(df.drop(columns=["to", "amount"]).sort_values(["wallet", "stage", "amount_m"], ascending=[True, True, False]).to_string())
    # final destination shares (direct deliveries to non-hop addresses + onward transfers from hops)
    fin = df[~df.to.isin(HOP_OF.values())].copy()
    fin["dest"] = fin.to_name.where(fin.to_name.str.startswith(("Binance", "Kraken", "rebate")), "other")
    t = fin.groupby(["wallet", "dest"]).amount.sum().unstack(fill_value=0) / 1e6
    t["total"] = t.sum(axis=1)
    print("\nfinal destinations ($M):")
    print(t.round(3).to_string())


if __name__ == "__main__":
    main()
