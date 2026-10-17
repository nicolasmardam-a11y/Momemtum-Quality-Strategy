"""Shared constants and read-only RPC helpers for the mintblade / GRIMDRIP / endlessFate linkage study.

Endpoints (tested 2026-10-17):
- publicnode: latest-state calls only (archive requests need a token).
- polygon.gateway.tenderly.co: free, no key, eth_getLogs over >=200k-block ranges, archive receipts.
  Cross-checked against rpc-mainnet.matic.quiknode.pro and poly.api.pocket.network on a 10k-block
  window (identical 9 logs), see linkage_02_transfers.py --selftest.
- polygon.drpc.org: receipts (no getLogs ranges on the free plan).
All requests go through pmr.http.request_json, so every raw response is stored with provenance.
cache=True is used only for immutable history (blocks far below head, receipts).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analyses" / "mechanics"))
from pmr.http import request_json  # noqa: E402
from keccak import keccak256  # noqa: E402  (pure-Python Keccak-256, verified on a known selector)

DERIVED = ROOT / "data" / "derived"
NOTES = ROOT / "notes" / "wallets"

WALLETS = {
    "mintblade": "0x96cfcb0c30942cfcd1cdf76c7d408794d66b1acb",
    "GRIMDRIP": "0x3f87d51f27ba6e19ec52aaeebb68559a839c742c",
    "endlessFate": "0x5e4c3b5b81171e2ca4ab776ac0d6bba787f9dba2",
}
LABEL = {v: k for k, v in WALLETS.items()}

# docs.polymarket.com /resources/contracts (fetched 2026-10-17) unless noted
KNOWN = {
    "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb": "pUSD (CollateralToken)",
    "0x93070a847efef7f70739046a929d47a521f5b8ee": "Polymarket CollateralOnramp",
    "0x2957922eb93258b93368531d39facca3b4dc5854": "Polymarket CollateralOfframp",
    "0xebc2459ec962869ca4c0bd1e06368272732bcb08": "Polymarket PermissionedRamp",
    "0x00000000000fb5c9adea0298d729a0cb3823cc07": "Polymarket Deposit Wallet Factory",
    "0x7a18edfe055488a3128f01f563e5b479d92ffc3a": "Polymarket Deposit Wallet Beacon",
    "0xaacfeea03eb1561c4e67d661e40682bd20e3541b": "Polymarket Gnosis Safe Factory",
    "0xab45c5a4b0c941a2f231c04c3f49182e1a254052": "Polymarket Proxy Factory",
    "0xe111180000d2663c0091e4f400237545b87b996b": "Polymarket CTF Exchange",
    "0xe2222d279d744050d28e00520010520000310f59": "Polymarket Neg Risk CTF Exchange",
    "0xe3333700ca9d93003f00f0f71f8515005f6c00aa": "Polymarket ExchangeV3",
    "0x4d97dcd97ec945f40cf65f87097ace5ea0476045": "Conditional Tokens (CTF)",
    "0x006f54f7f9a22e0000cc2ab60031000000ae9fef": "Polymarket PositionManager",
    "0x12121212006e4cd160d18e3f00711da5c3372600": "Polymarket Router",
    "0xada100db00ca00073811820692005400218fce1f": "Polymarket CtfCollateralAdapter",
    "0xada2005600dec949baf300f4c6120000bdb6eaab": "Polymarket NegRiskCtfCollateralAdapter",
    "0xa1200000d0002264c9a1698e001292d00e1b00af": "Polymarket AutoRedeemer",
    "0xd91e80cf2e7be2e162c6513ced06f1dd0da35296": "Polymarket Neg Risk Adapter (v1)",
    # tokens (Circle / Polygon PoS bridge; well-known)
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": "USDC.e (PoS-bridged)",
    "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359": "USDC (native, Circle)",
    # docs /trading/bridge/withdraw links this Uniswap v3 pool for the pUSD->USDC withdrawal swap
    "0xd36ec33c8bed5a9f7b6630855f1533455b98a418": "Uniswap v3 USDC/USDC.e pool (docs bridge/withdraw)",
    # identified in this study from event signatures (see linkage_02): RelayErc20Deposit(address,address,uint256,bytes32)
    "0x4cd00e387622c35bddb9b4c962c136462338bc31": "Relay depository (emits RelayErc20Deposit)",
}
TOKENS = {
    "0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb": "pUSD",
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": "USDC.e",
    "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359": "USDC",
}
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TRANSFER_SINGLE = "0xc3d58168c5ae7397731d063d5bbf3d657854427343f4c083240f7aacaa2d0f62"
TRANSFER_BATCH = "0x4a39dc06d4c0dbc64b70af90fd698a233a518aa5d07e595d983b8c0526c8f7fb"

LATEST_RPC = "https://polygon-bor-rpc.publicnode.com"
ARCHIVE_RPC = "https://polygon.gateway.tenderly.co"
RECEIPT_RPC = "https://polygon.drpc.org"


def pad(a: str) -> str:
    return "0x" + "0" * 24 + a.lower()[2:]


def unpad(t: str) -> str:
    return "0x" + t[-40:].lower()


def rpc(method: str, params: list, *, url: str = LATEST_RPC, cache: bool = False, source: str = "polygon"):
    j = request_json(url, method="POST", source=source, cache=cache, timeout=120,
                     json_body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in j:
        raise RuntimeError(f"{method} {url}: {j['error']}")
    return j["result"]


def archive(method: str, params: list, *, cache: bool = True):
    """Historical call (receipts, logs, old blocks); tenderly first, drpc fallback for single-object calls."""
    try:
        return rpc(method, params, url=ARCHIVE_RPC, cache=cache, source="polygon-tenderly")
    except RuntimeError:
        if method == "eth_getLogs":
            raise
        return rpc(method, params, url=RECEIPT_RPC, cache=cache, source="polygon")


def receipt(tx: str) -> dict:
    # identical request shape to ge_onchain_flows.py so its cached receipts are reused
    try:
        r = rpc("eth_getTransactionReceipt", [tx], url=RECEIPT_RPC, cache=True, source="polygon")
        if r:
            return r
    except RuntimeError:
        pass
    return rpc("eth_getTransactionReceipt", [tx], url=ARCHIVE_RPC, cache=True, source="polygon-tenderly")


def label(addr: str) -> str:
    a = addr.lower()
    if a in LABEL:
        return LABEL[a]
    return KNOWN.get(a, "")
