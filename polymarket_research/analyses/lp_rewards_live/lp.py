"""Liquidity-reward scoring per docs.polymarket.com/programs/liquidity-rewards (read 2026-10-17).

S(v,s) = ((v-s)/v)^2 * b, v = rewardsMaxSpread (cents), s = distance (cents) from the size-cutoff-adjusted midpoint.
Q_one = S-weighted bids on m + asks on m'; Q_two = asks on m + bids on m'. The public YES book is the unified book
(NO orders appear mirrored), so Q_one = S-weighted YES bids and Q_two = S-weighted YES asks.
Q_min = max(min(Q1,Q2), max(Q1,Q2)/c) if 0.10 <= mid <= 0.90 else min(Q1,Q2); c = 3.
The in-game multiplier b multiplies every order in a market-sample alike, so it cancels in the per-sample share.
'Size-cutoff-adjusted midpoint' is not defined precisely in the docs: PRIMARY = mid of the prices at which
cumulative depth from the top first reaches rewardsMinSize; SENSITIVITY = mid of the best levels whose own
aggregate size >= rewardsMinSize; and the plain touch mid.
"""
from __future__ import annotations

import math

C = 3.0


def adj_mid(bids, asks, min_size, mode="cum"):
    """bids/asks best-first [(p, s)]. Returns (adj_bid, adj_ask, mid) or None."""
    def pick(levels):
        if not levels:
            return None
        if mode == "plain":
            return levels[0][0]
        cum = 0.0
        for p, s in levels:
            if mode == "level" and s >= min_size:
                return p
            cum += s
            if mode == "cum" and cum >= min_size:
                return p
        return None
    b, a = pick(bids), pick(asks)
    if b is None or a is None:
        return None
    return b, a, (b + a) / 2


def S(v, s):
    return ((v - s) / v) ** 2 if 0 <= s < v else 0.0


def side_score(levels, mid, v, side, min_size=None, level_filter=False):
    """S-weighted depth within v cents of mid. side='bid' or 'ask'."""
    q = 0.0
    for p, sz in levels:
        dist = (mid - p) * 100 if side == "bid" else (p - mid) * 100
        if dist >= v:
            break
        if dist < 0:      # crossed relative to adjusted mid (can happen with thin tops): treat as at mid
            dist = 0.0
        if level_filter and min_size and sz < min_size:
            continue
        q += S(v, dist) * sz
    return q


def qmin(q1, q2, mid):
    if 0.10 <= mid <= 0.90:
        return max(min(q1, q2), max(q1, q2) / C)
    return min(q1, q2)


def comp_qmin(q1, q2, mid):
    """Bounds on the competitors' summed Q_min (per-maker split unobservable)."""
    inband = 0.10 <= mid <= 0.90
    central = qmin(q1, q2, mid)                       # whole book behaves like one balanced maker
    conservative = (q1 + q2) if inband else min(q1, q2)  # upper bound on sum_n Q_min,n
    optimistic = max(q1, q2) / C if inband else math.nan  # lower bound (in band only)
    return optimistic, central, conservative


def our_quote(bids, asks, tick, capital, variant="join"):
    """Two-sided quote: YES bid at pb and NO bid at 1-pa (== YES ask at pa), N shares each.
    Capital locked = N*pb + N*(1-pa). variant 'join' = at the touch; 'improve' = one tick inside when spread >= 3 ticks."""
    if not bids or not asks:
        return None
    pb, pa = bids[0][0], asks[0][0]
    if variant == "improve" and pa - pb >= 3 * tick - 1e-9:
        pb, pa = round(pb + tick, 6), round(pa - tick, 6)
    per = pb + (1 - pa)
    if per <= 0:
        return None
    return pb, pa, capital / per


def with_order(levels, p, n, is_bid):
    """Insert our order (price p, n shares) into best-first levels."""
    d = dict(levels)
    d[p] = d.get(p, 0.0) + n
    return sorted(d.items(), key=lambda t: t[0], reverse=is_bid)


def reward_estimate(bids, asks, tick, v, min_size, daily_rate, capital, mid_mode="cum", variant="join", level_filter=False):
    oq = our_quote(bids, asks, tick, capital, variant)
    if oq is None or not v:
        return None
    pb, pa, n = oq
    # the scored book includes our own orders, so the adjusted mid is computed with them added
    am = adj_mid(with_order(bids, pb, n, True), with_order(asks, pa, n, False), min_size, mid_mode)
    if am is None:
        return None
    _, _, mid = am
    q1c = side_score(bids, mid, v, "bid", min_size, level_filter)
    q2c = side_score(asks, mid, v, "ask", min_size, level_filter)
    eligible = n >= (min_size or 0)
    q1o = S(v, max(0.0, (mid - pb) * 100)) * n if eligible else 0.0
    q2o = S(v, max(0.0, (pa - mid) * 100)) * n if eligible else 0.0
    qo = qmin(q1o, q2o, mid)
    opt, cen, con = comp_qmin(q1c, q2c, mid)
    out = {"mid": mid, "pb": pb, "pa": pa, "n": n, "eligible": eligible, "q1c": q1c, "q2c": q2c, "q_ours": qo,
           "inband": 0.10 <= mid <= 0.90}
    for k, comp in (("opt", opt), ("cen", cen), ("con", con)):
        sh = qo / (qo + comp) if (qo > 0 and not math.isnan(comp)) else (0.0 if qo == 0 else math.nan)
        out[f"share_{k}"] = sh
        out[f"rew_{k}"] = daily_rate * sh if not math.isnan(sh) else math.nan
    return out
