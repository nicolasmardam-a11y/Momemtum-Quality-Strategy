"""Cross-event crypto price relations (same Binance pair, same candle definitions) - read-only, offline.

Run from polymarket_research/:  python -m analyses.logical_arb.02c_crypto_cross [date-tag]
Input : data/derived/la_markets_<tag>.parquet
Output: data/derived/la_relations_cx_<tag>.parquet (slim schema: family,key,ma,oa,mb,ob,note)

Rules read 2026-10-17 (Gamma descriptions, BTC examples; every pair below is re-checked by regex on BOTH legs'
descriptions: same 'Binance' + same '<ASSET>/USDT' pair, else skipped):
  above(K, t) : YES iff Close of the Binance 1m candle closing at time t (ET) is strictly higher than K.
  bucket[L,U) : 'price on' neg-risk event, same candle at t; a value exactly on a boundary goes to the higher bracket.
  hit-up(K, W): YES iff any 1m candle in window W has High >= K   ('reach'/'hit', groupItemTitle '↑').
  dip(K, W)   : YES iff any 1m candle in W has Low <= K            ('dip', groupItemTitle '↓').
Implications (A => B, bundle NO_A + YES_B unless stated):
  cx_above_hit   above(K,t)   => hit-up(K'<=K, W containing t)      (High >= Close > K >= K')
  cx_above_dip   NOT above(K,t) => dip(K'>=K, W containing t)       bundle YES_above + YES_dip (Low <= Close <= K <= K')
  cx_bkt_above   bucket[L,U)  => above(K<L, t)                      (Close >= L > K)
  cx_bkt_notab   bucket[L,U)  => NOT above(K>=U, t)                 bundle NO_bucket + NO_above
  cx_bkt_hit     bucket[L,U)  => hit-up(K'<=L, W containing t)
  cx_bkt_dip     bucket[L,U)  => dip(K'>=U, W containing t)
  cx_hit_hit     hit-up(K, W1) => hit-up(K'<=K, W2 containing W1);  dip(K, W1) => dip(K'>=K, W2 containing W1)
Window W for yearly 'by December 31' markets starts at the market's creation ('price action before this market's
creation will not be considered'), so W1 must start after the W2 market's createdAt.
"""
from __future__ import annotations

import itertools
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
ET = "America/New_York"
MON = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                    "september", "october", "november", "december"], 1)}
MONRE = "(" + "|".join(MON) + ")"

m = pd.read_parquet(ROOT / "data" / "derived" / f"la_markets_{DATE}.parquet",
                    columns=["id", "question", "description", "event_id", "event_title", "groupItemTitle", "endDate",
                             "createdAt", "acceptingOrders", "outcomes", "bestBid", "bestAsk", "clobTokenIds"])
m = m[(m.acceptingOrders == True) & m.clobTokenIds.notna()].copy()  # noqa: E712
m = m[m.outcomes.map(lambda s: json.loads(s) == ["Yes", "No"] if isinstance(s, str) else False)]
m = m[(m.bestBid.fillna(0) > 0) | (m.bestAsk.fillna(1) < 1)].copy()
m["id"] = m["id"].astype(str)
m["end"] = pd.to_datetime(m.endDate, utc=True, errors="coerce", format="ISO8601")
m["created"] = pd.to_datetime(m.createdAt, utc=True, errors="coerce", format="ISO8601")
for _c in ("groupItemTitle", "description", "question", "event_title"):
    m[_c] = m[_c].fillna("").astype(str)
t = m.event_title.fillna("")
ASSETS = ["Bitcoin", "Ethereum", "Solana", "XRP", "BNB", "Dogecoin", "Hyperliquid", "Cardano"]


def num(s):
    s = (s or "").replace(",", "").replace("$", "").strip()
    mm = re.match(r"^([\d.]+)\s*([kKmM]?)$", s)
    if not mm:
        return None
    return float(mm.group(1)) * {"": 1, "k": 1e3, "K": 1e3, "m": 1e6, "M": 1e6}[mm.group(2)]


def et(y, mo, d, hh=0, mi=0):
    return pd.Timestamp(year=y, month=mo, day=d, hour=hh, minute=mi, tz=ET).tz_convert("UTC")


def pair_of(desc):
    mm = re.search(r"Binance[^.]*?\b([A-Z0-9]{2,10})/(USDT|USD|USDC)\b", desc or "")
    return f"{mm.group(1)}/{mm.group(2)}" if mm else None


def candle_time(title, desc, end):
    """UTC close time of the reference candle for an 'above'/'price on' market."""
    mm = re.search(MONRE + r"\s+(\d{1,2})", title.lower())
    if not mm:
        return None
    y = end.year if pd.notna(end) else 2026
    hh, mi = 12, 0
    tt = re.search(r"closing at (\d{1,2}):(\d{2})", desc or "")
    if tt:
        hh, mi = int(tt.group(1)), int(tt.group(2))
    hp = re.search(r",\s*(\d{1,2})\s*(AM|PM)\s*ET", title)
    if hp:  # hourly variants: 'October 17, 5PM ET'
        hh = int(hp.group(1)) % 12 + (12 if hp.group(2) == "PM" else 0)
        mi = 0
    return et(y, MON[mm.group(1)], int(mm.group(2)), hh, mi)


rows_above, rows_bkt, rows_hit = [], [], []
for r in m.itertuples():
    title = r.event_title or ""
    asset = next((a for a in ASSETS if title.startswith(a) or f" {a} " in f" {title} "), None)
    if not asset:
        continue
    pair = pair_of(r.description)
    gi = (r.groupItemTitle or "").strip()
    if re.match(rf"^{asset} above ___ on ", title):
        k = num(gi)
        tc = candle_time(title, r.description, r.end)
        if k is not None and tc is not None and "higher than" in (r.description or ""):
            rows_above.append((asset, pair, tc, k, r))
    elif re.match(rf"^{asset} price on ", title):
        tc = candle_time(title, r.description, r.end)
        g2 = gi.replace(",", "").replace("$", "")
        lo = hi = None
        if g2.startswith("<"):
            lo, hi = float("-inf"), num(g2[1:])
        elif g2.startswith(">"):
            lo, hi = num(g2[1:]), float("inf")
        elif "-" in g2:
            a_, b_ = g2.split("-", 1)
            lo, hi = num(a_), num(b_)
        if tc is not None and lo is not None and hi is not None and "higher range bracket" in (r.description or ""):
            rows_bkt.append((asset, pair, tc, lo, hi, r))
    elif re.match(rf"^(What price will {asset} hit|When will {asset} hit)", title):
        d = r.description or ""
        up = "↑" in gi or re.search(r"High\"? price[s]? (?:is )?equal to or greater than", d) is not None
        dn = "↓" in gi or re.search(r"Low\"? price[s]? (?:is )?equal to or lower than", d) is not None
        if up == dn:
            continue
        k = num(gi.replace("↑", "").replace("↓", "")) if gi.startswith(("↑", "↓")) else None
        if k is None:
            mm = re.search(r"\$([\d,.]+\s*[kK]?)", r.question or "")
            k = num(mm.group(1)) if mm else None
        if k is None:
            continue
        tl = title.lower()
        y = r.end.year if pd.notna(r.end) else 2026
        w0 = w1 = None
        mm = re.search(MONRE + r"\s+(\d{1,2})\s*-\s*(\d{1,2})\??$", tl)
        if mm:  # weekly 'October 12-18' (ET)
            w0, w1 = et(y, MON[mm.group(1)], int(mm.group(2))), et(y, MON[mm.group(1)], int(mm.group(3)), 23, 59)
        elif re.search(r" on " + MONRE + r"\s+(\d{1,2})\??$", tl):
            mm = re.search(r" on " + MONRE + r"\s+(\d{1,2})\??$", tl)
            w0, w1 = et(y, MON[mm.group(1)], int(mm.group(2))), et(y, MON[mm.group(1)], int(mm.group(2)), 23, 59)
        elif re.search(r" in " + MONRE + r"\??$", tl):
            mo = MON[re.search(r" in " + MONRE + r"\??$", tl).group(1)]
            last = (pd.Timestamp(year=y, month=mo, day=1) + pd.offsets.MonthEnd(0)).day
            w0, w1 = et(y, mo, 1), et(y, mo, last, 23, 59)
        else:  # yearly / 'when will' ladders: creation -> deadline in the question
            mq = re.search(MONRE + r"\s+(\d{1,2}),?\s*(\d{4})", (r.question or "").lower())
            if mq:
                w0, w1 = r.created, et(int(mq.group(3)), MON[mq.group(1)], int(mq.group(2)), 23, 59)
            elif re.search(r" in (\d{4})\??$", tl):
                yy = int(re.search(r" in (\d{4})\??$", tl).group(1))
                w0, w1 = r.created, et(yy, 12, 31, 23, 59)
        if w0 is None or pd.isna(w0):
            continue
        rows_hit.append((asset, pair, "up" if up else "dn", k, w0, w1, r))

print("above", len(rows_above), "buckets", len(rows_bkt), "hit/dip", len(rows_hit))
rels = []


def add(fam, key, a, oa, b, ob, note):
    rels.append((fam, key, a.id, oa, b.id, ob, note))


def same_src(p1, p2):
    return p1 is not None and p1 == p2


for (asA, pA, tA, kA, rA) in rows_above:
    for (asB, pB, dirB, kB, w0, w1, rB) in rows_hit:
        if asA != asB or not same_src(pA, pB) or not (w0 <= tA - pd.Timedelta(minutes=1) and tA <= w1):
            continue
        if dirB == "up" and kB <= kA:
            add("cx_above_hit", asA, rA, 1, rB, 0, f"{rA.question} => {rB.question}")
        if dirB == "dn" and kB >= kA:
            add("cx_above_dip", asA, rA, 0, rB, 0, f"NOT {rA.question} => {rB.question}")
    for (asB, pB, tB, lo, hi, rB) in rows_bkt:
        if asA != asB or not same_src(pA, pB) or tA != tB:
            continue
        if kA < lo:
            add("cx_bkt_above", asA, rB, 1, rA, 0, f"{rB.question} => {rA.question}")
        elif kA >= hi:
            add("cx_bkt_notab", asA, rB, 1, rA, 1, f"{rB.question} => NOT {rA.question}")
for (asA, pA, tA, lo, hi, rA) in rows_bkt:
    for (asB, pB, dirB, kB, w0, w1, rB) in rows_hit:
        if asA != asB or not same_src(pA, pB) or not (w0 <= tA - pd.Timedelta(minutes=1) and tA <= w1):
            continue
        if dirB == "up" and kB <= lo:
            add("cx_bkt_hit", asA, rA, 1, rB, 0, f"{rA.question} => {rB.question}")
        if dirB == "dn" and kB >= hi:
            add("cx_bkt_dip", asA, rA, 1, rB, 0, f"{rA.question} => {rB.question}")
for a1, a2 in itertools.permutations(rows_hit, 2):
    asA, pA, dA, kA, w0A, w1A, rA = a1
    asB, pB, dB, kB, w0B, w1B, rB = a2
    if asA != asB or dA != dB or not same_src(pA, pB) or rA.event_id == rB.event_id:
        continue
    if not (w0B <= w0A and w1A <= w1B) or (w0A == w0B and w1A == w1B):
        continue
    if (dA == "up" and kB <= kA) or (dA == "dn" and kB >= kA):
        add("cx_hit_hit", asA, rA, 1, rB, 0, f"{rA.question} => {rB.question}")

R = pd.DataFrame(rels, columns=["family", "key", "ma", "oa", "mb", "ob", "note"]).drop_duplicates(["ma", "oa", "mb", "ob"])
R["oa"] = R.oa.astype("int8")
R["ob"] = R.ob.astype("int8")
R.to_parquet(ROOT / "data" / "derived" / f"la_relations_cx_{DATE}.parquet", index=False)
print(len(R))
print(R.groupby(["family", "key"]).size().to_string())
