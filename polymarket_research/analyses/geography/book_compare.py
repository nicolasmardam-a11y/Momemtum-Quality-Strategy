"""Show that Polymarket international and Polymarket US run separate order books.

Compares the same real-world question (Democrats control the House after 2026 midterms)
on the international CLOB (pUSD, on-chain settlement) and the Polymarket US public gateway
(USD, Polymarket Clearing). Read-only, no auth. Prices are quotes, not executable fills.
"""
from __future__ import annotations
import datetime as dt, json
from pmr import api
from pmr.http import request_json

ev = request_json("https://gamma-api.polymarket.com/events/slug/which-party-will-win-the-house-in-2026", None, source="gamma")
m = next(x for x in ev["markets"] if "Democratic" in (x.get("question") or ""))
yes = api.jlist(m["clobTokenIds"])[0]
b = api.book(yes)
print("INTL", m["question"], "tick", m.get("orderPriceMinTickSize"), "restricted", m.get("restricted"))
print("  best bid", b["bids"][0] if b.get("bids") else None, "best ask", b["asks"][0] if b.get("asks") else None)
us = request_json("https://gateway.polymarket.us/v1/markets/paccc-usho-midterms-2026-11-03-dem/book", None, source="pm-us")["marketData"]
print("US  ", us["marketSlug"], "state", us["state"])
print("  best bid", us["bids"][0], "best ask", us["offers"][0])
print("fetched", dt.datetime.now(dt.timezone.utc).isoformat())
