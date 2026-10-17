"""Complete-set / within-market arbitrage scanner primitives (read-only).

Family B of the strategy research. All prices are executable CLOB book levels
(pmr.api.books, normalised best-first); fees use each market's Gamma feeSchedule.

Definitions (Q = number of complete sets; one set is worth 1 pUSD at merge/convert/resolution):
  a  binary: buy Q of both outcome tokens at asks, merge          -> profit = Q - cost
  b  binary: split Q, sell both outcome tokens at bids            -> profit = proceeds - Q
  c  neg-risk: buy Q YES of every tradable member, hold to resolution (needs exhaustive set)
  cp neg-risk: split Q in every member, sell all NO, hold the YES set (same payoff as c)
  d  neg-risk: split Q in one member, convert NO -> YES of all others, sell YES in every member with bids
  e  neg-risk: buy Q NO in each of k tradable members, convert -> (k-1)Q pUSD (+ YES of the rest, valued 0)
"""
from __future__ import annotations

import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api, fees  # noqa: E402

SIZES = (100, 1000, 10000)
TRADABLE_COLS = ("active", "enableOrderBook", "acceptingOrders")


# --------------------------------------------------------------------------- universe

def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def market_row(e: dict, m: dict) -> dict:
    fs = m.get("feeSchedule") or {}
    toks = api.jlist(m.get("clobTokenIds"))
    outs = api.jlist(m.get("outcomes"))
    prices = api.jlist(m.get("outcomePrices"))
    rate = fees.market_fee_rate(m, "other")
    return {
        "event_id": e.get("id"), "event_slug": e.get("slug"), "event_title": e.get("title"),
        "ev_negRisk": bool(e.get("negRisk")), "ev_aug": bool(e.get("negRiskAugmented")),
        "nr_id": m.get("negRiskMarketID") if m.get("negRisk") else None,
        "market_id": m.get("id"), "conditionId": m.get("conditionId"), "question": m.get("question"),
        "groupItemTitle": m.get("groupItemTitle"), "negRisk": bool(m.get("negRisk")),
        "negRiskOther": bool(m.get("negRiskOther")),
        "active": bool(m.get("active")), "closed": bool(m.get("closed")),
        "acceptingOrders": bool(m.get("acceptingOrders")), "enableOrderBook": bool(m.get("enableOrderBook")),
        "outcomes": outs, "tokens": toks,
        "outcomePrices": [_f(p) for p in prices] if prices else None,
        "fee_rate": rate, "fee_exp": float(fs.get("exponent") or 1.0) if isinstance(fs, dict) else 1.0,
        "has_feeSchedule": bool(fs), "feesEnabled": m.get("feesEnabled"), "feeType": m.get("feeType"),
        "orderMinSize": _f(m.get("orderMinSize")), "tick": _f(m.get("orderPriceMinTickSize")),
        "secondsDelay": _f(m.get("secondsDelay")) or 0.0, "gameStartTime": m.get("gameStartTime"),
        "umaResolutionStatus": m.get("umaResolutionStatus"), "endDate": m.get("endDate"),
        "volume24hr": _f(m.get("volume24hr")), "liquidityNum": _f(m.get("liquidityNum")),
        "rfqEnabled": m.get("rfqEnabled"), "version": m.get("version"),
    }


def load_universe(max_pages=None) -> tuple[list[dict], datetime]:
    t = datetime.now(timezone.utc)
    rows, seen = [], set()
    for e in api.gamma_keyset("events", {"closed": "false", "active": "true"}, max_pages=max_pages):
        for m in e.get("markets") or []:
            if m.get("id") in seen:
                continue
            seen.add(m.get("id"))
            rows.append(market_row(e, m))
    return rows, t


def tradable(r: dict) -> bool:
    return (not r["closed"]) and all(r[c] for c in TRADABLE_COLS) and len(r["tokens"]) == 2


# --------------------------------------------------------------------------- books

def fetch_books(token_ids: list[str], workers: int = 24) -> tuple[dict, float, float]:
    """Return ({token: normalised book}, t_start, t_end) using parallel POST /books (100 per call)."""
    chunks = [token_ids[i:i + 100] for i in range(0, len(token_ids), 100)]
    out = {}
    t0 = time.time()

    def one(ch):
        try:
            return api.books(ch)
        except Exception as ex:  # keep scanning; missing books are treated as absent
            print("books error", repr(ex)[:200], flush=True)
            return []

    with ThreadPoolExecutor(workers) as ex:
        for res in ex.map(one, chunks):
            for b in res:
                if b.get("asset_id"):
                    out[b["asset_id"]] = b
    return out, t0, time.time()


# --------------------------------------------------------------------------- book walking

def fee_ps(p: float, rate: float, exp: float) -> float:
    return rate * (p * (1 - p)) ** exp


def leg_segments(levels, rate, exp, side):
    """[(cum_start, cum_end, marginal value per share)]; buy -> cost incl. fee, sell -> proceeds net of fee."""
    segs, cum = [], 0.0
    for p, s in levels:
        if s <= 0:
            continue
        v = p + fee_ps(p, rate, exp) if side == "buy" else p - fee_ps(p, rate, exp)
        segs.append((cum, cum + s, v))
        cum += s
    return segs


def combine(legs, side, payoff, required=True):
    """Combine leg marginal curves into per-set value segments.

    buy : value(q) = payoff - sum_i cost_i(q)      (all legs required)
    sell: value(q) = sum_i proceeds_i(q) - payoff  (required=False: an exhausted leg contributes 0)
    Returns (segments [(q0, q1, value)], depth) where depth is where a required leg runs out.
    """
    if not legs:
        return [], 0.0
    bps = sorted({x for segs in legs for (a, b, _) in segs for x in (a, b)} | {0.0})
    depth = min(segs[-1][1] if segs else 0.0 for segs in legs) if required else max(
        (segs[-1][1] if segs else 0.0) for segs in legs)
    idx = [0] * len(legs)
    out = []
    for q0, q1 in zip(bps[:-1], bps[1:]):
        if q0 >= depth:
            break
        tot = 0.0
        for i, segs in enumerate(legs):
            while idx[i] < len(segs) and segs[idx[i]][1] <= q0:
                idx[i] += 1
            if idx[i] < len(segs):
                tot += segs[idx[i]][2]
        val = payoff - tot if side == "buy" else tot - payoff
        out.append((q0, min(q1, depth), val))
    return out, depth


def profile(segs, depth, sizes=SIZES, allow_beyond=False, beyond_value=None):
    """Profit at fixed sizes (NaN if beyond depth unless allow_beyond), Q* and max profit, top-of-book edge."""
    res = {"edge0": segs[0][2] if segs else math.nan, "depth": depth}
    cum, qstar, pmax = 0.0, 0.0, 0.0
    for q0, q1, v in segs:
        if v <= 0:
            break
        cum += (q1 - q0) * v
        qstar, pmax = q1, cum
    res["qstar"], res["pmax"] = qstar, pmax
    for Q in sizes:
        if Q > depth + 1e-9 and not allow_beyond:
            res[f"p{Q}"] = math.nan
            continue
        tot = 0.0
        for q0, q1, v in segs:
            if q0 >= Q:
                break
            tot += (min(q1, Q) - q0) * v
        if Q > depth and allow_beyond:
            tot += (Q - depth) * beyond_value
        res[f"p{Q}"] = tot
    return res


def top(b):
    if not b:
        return (math.nan, 0.0, math.nan, 0.0)
    bb = b["bids"][0] if b["bids"] else (math.nan, 0.0)
    ba = b["asks"][0] if b["asks"] else (math.nan, 0.0)
    return (bb[0], bb[1], ba[0], ba[1])


def mirror_ok(b0, b1, tol=1e-9):
    """True if token1's asks are exactly token0's bids mirrored at 1-p (and vice versa)."""
    if not b0 or not b1:
        return None
    m1 = [(round(1 - p, 6), round(s, 4)) for p, s in b0["bids"]]
    a1 = [(round(p, 6), round(s, 4)) for p, s in b1["asks"]]
    m2 = [(round(1 - p, 6), round(s, 4)) for p, s in b0["asks"]]
    b1b = [(round(p, 6), round(s, 4)) for p, s in b1["bids"]]
    return m1 == a1 and m2 == b1b


def crossed(b):
    return bool(b and b["bids"] and b["asks"] and b["bids"][0][0] >= b["asks"][0][0])


# --------------------------------------------------------------------------- analysis

def _age(b, now_ms):
    return (now_ms - b["timestamp_ms"]) / 1000 if b and b.get("timestamp_ms") else math.nan


def flags_for(rows, bks, now_ms, now_iso):
    fl = set()
    for r in rows:
        if not tradable(r):
            fl.add("not_tradable")
        if r["secondsDelay"] and r["secondsDelay"] > 0:
            fl.add("seconds_delay")
        g = r.get("gameStartTime")
        if g:
            try:
                gs = datetime.fromisoformat(str(g).replace("Z", "+00:00").replace(" ", "T"))
                if gs.tzinfo is None:
                    gs = gs.replace(tzinfo=timezone.utc)
                if gs.timestamp() * 1000 < now_ms:
                    fl.add("game_started")
            except ValueError:
                pass
        if (r.get("umaResolutionStatus") or "") in ("proposed", "disputed", "challenged"):
            fl.add("resolution_pending")
        for t in r["tokens"]:
            b = bks.get(t)
            if b is None:
                fl.add("missing_book")
                continue
            if crossed(b):
                fl.add("crossed_book")
            if _age(b, now_ms) > 300:
                fl.add("stale_gt5min")
    return sorted(fl)


def analyze_binary(r, bks):
    b0, b1 = bks.get(r["tokens"][0]), bks.get(r["tokens"][1])
    if b0 is None or b1 is None:
        return None
    rate, exp = r["fee_rate"], r["fee_exp"]
    t0, t1 = top(b0), top(b1)
    out = {"market_id": r["market_id"], "bb0": t0[0], "bs0": t0[1], "ba0": t0[2], "as0": t0[3],
           "bb1": t1[0], "bs1": t1[1], "ba1": t1[2], "as1": t1[3],
           "mirror": mirror_ok(b0, b1), "crossed0": crossed(b0), "crossed1": crossed(b1),
           "age0": None, "age1": None}
    sa, da = combine([leg_segments(b0["asks"], rate, exp, "buy"), leg_segments(b1["asks"], rate, exp, "buy")], "buy", 1.0)
    sb, db = combine([leg_segments(b0["bids"], rate, exp, "sell"), leg_segments(b1["bids"], rate, exp, "sell")], "sell", 1.0)
    for k, (s, d) in {"a": (sa, da), "b": (sb, db)}.items():
        pr = profile(s, d)
        for kk, v in pr.items():
            out[f"{k}_{kk}"] = v
    return out


def analyze_group(members, bks):
    """members: all universe rows sharing a negRiskMarketID (incl. closed, placeholders)."""
    trad = [r for r in members if tradable(r) and r["tokens"][0] in bks and r["tokens"][1] in bks]
    open_untradable = [r for r in members if not r["closed"] and r not in trad]
    placeholders = [r for r in members if not r["closed"] and not r["active"]]
    other = [r for r in members if r["negRiskOther"]]
    closed = [r for r in members if r["closed"]]
    closed_yes = [r for r in closed if r["outcomePrices"] and (r["outcomePrices"][0] or 0) > 0.5]
    exhaustive = (len(open_untradable) == 0 and len(placeholders) == 0 and len(closed_yes) == 0
                  and (not other or all(o in trad for o in other)) and len(trad) >= 2)
    out = {"n_members": len(members), "n_trad": len(trad), "n_open_untradable": len(open_untradable),
           "n_placeholder": len(placeholders), "n_other": len(other), "n_closed": len(closed),
           "n_closed_yes": len(closed_yes), "exhaustive": exhaustive,
           "aug": any(r["ev_aug"] for r in members)}
    if len(trad) < 2:
        return out, trad
    yb = [bks[r["tokens"][0]] for r in trad]
    nb = [bks[r["tokens"][1]] for r in trad]
    out["sum_askY"] = sum(top(b)[2] if not math.isnan(top(b)[2]) else math.inf for b in yb)
    out["sum_bidY"] = sum(top(b)[0] for b in yb if not math.isnan(top(b)[0]))
    out["sum_askN"] = sum(top(b)[2] if not math.isnan(top(b)[2]) else math.inf for b in nb)
    out["sum_bidN"] = sum(top(b)[0] for b in nb if not math.isnan(top(b)[0]))
    out["n_mirror_bad"] = sum(1 for r, a, b in zip(trad, yb, nb) if mirror_ok(a, b) is False)
    k = len(trad)
    specs = {
        "c": ([leg_segments(b["asks"], r["fee_rate"], r["fee_exp"], "buy") for r, b in zip(trad, yb)], "buy", 1.0, True),
        "cp": ([leg_segments(b["bids"], r["fee_rate"], r["fee_exp"], "sell") for r, b in zip(trad, nb)], "sell", None, True),
        "d": ([leg_segments(b["bids"], r["fee_rate"], r["fee_exp"], "sell") for r, b in zip(trad, yb)], "sell", 1.0, False),
        # e: per set, member i joins the converted NO basket S only while 1 - askN_i - fee > 0 and depth remains;
        # value per set = sum_{i in S} (1 - askN_i - fee_i) - 1  (convert returns |S|-1 pUSD; YES of the rest valued 0)
        "e": ([[(a, b_, max(0.0, 1.0 - v)) for (a, b_, v) in leg_segments(b["asks"], r["fee_rate"], r["fee_exp"], "buy")]
               for r, b in zip(trad, nb)], "sell", 1.0, False),
    }
    for key, (legs, side, payoff, req) in specs.items():
        if key == "cp":
            # split k markets (cost k per set), sell k NO, keep the YES set worth 1 at resolution: value = proceeds - (k-1)
            segs, depth = combine(legs, "sell", float(k - 1), True)
        else:
            segs, depth = combine(legs, side, payoff, req)
        pr = profile(segs, depth, allow_beyond=(key in ("d", "e")), beyond_value=-1.0)
        for kk, v in pr.items():
            out[f"{key}_{kk}"] = v
    return out, trad


def leg_detail(rows, bks, nlev=3):
    out = []
    for r in rows:
        d = {"market_id": r["market_id"], "title": r["groupItemTitle"] or r["question"], "fee_rate": r["fee_rate"],
             "min_size": r["orderMinSize"], "tick": r["tick"], "acceptingOrders": r["acceptingOrders"],
             "secondsDelay": r["secondsDelay"]}
        for side_i, t in enumerate(r["tokens"]):
            b = bks.get(t) or {}
            d[f"t{side_i}_bids"] = (b.get("bids") or [])[:nlev]
            d[f"t{side_i}_asks"] = (b.get("asks") or [])[:nlev]
            d[f"t{side_i}_ts"] = b.get("timestamp_ms")
        out.append(d)
    return out
