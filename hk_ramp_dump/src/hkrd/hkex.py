"""HKEX market-structure reference: spread (tick) tables, transaction costs,
trading sessions and board-lot arithmetic.

All schedules are dated so that a backtest applies the rule in force on the
trade date. Items marked VERIFY were sourced from HKEX notices but should be
re-checked against the official fee schedule before any capital decision.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Spread table, Part A (ordinary shares). Tuples: (lower bound inclusive, tick).
# ---------------------------------------------------------------------------
_PART_A_LEGACY = [
    (0.01, 0.001), (0.25, 0.005), (0.50, 0.010), (10.0, 0.020), (20.0, 0.050),
    (100.0, 0.100), (200.0, 0.200), (500.0, 0.500), (1000.0, 1.000),
    (2000.0, 2.000), (5000.0, 5.000),
]
# Minimum-spread reduction phase 1, effective 2025-08-04: HK$10-20 -> 0.01,
# new HK$20-50 band at 0.02, HK$50-100 stays 0.05.
_PART_A_2025 = [
    (0.01, 0.001), (0.25, 0.005), (0.50, 0.010), (10.0, 0.010), (20.0, 0.020),
    (50.0, 0.050), (100.0, 0.100), (200.0, 0.200), (500.0, 0.500),
    (1000.0, 1.000), (2000.0, 2.000), (5000.0, 5.000),
]
# Phase 2, scheduled 2026-08-03: HK$0.50-10 -> 0.005. VERIFY implementation.
_PART_A_2026 = [
    (0.01, 0.001), (0.25, 0.005), (0.50, 0.005), (10.0, 0.010), (20.0, 0.020),
    (50.0, 0.050), (100.0, 0.100), (200.0, 0.200), (500.0, 0.500),
    (1000.0, 1.000), (2000.0, 2.000), (5000.0, 5.000),
]
SPREAD_TABLES: list[tuple[date, list[tuple[float, float]]]] = [
    (date(1900, 1, 1), _PART_A_LEGACY),
    (date(2025, 8, 4), _PART_A_2025),
    (date(2026, 8, 3), _PART_A_2026),
]


def _table_for(d: date) -> list[tuple[float, float]]:
    table = SPREAD_TABLES[0][1]
    for eff, t in SPREAD_TABLES:
        if d >= eff:
            table = t
    return table


def tick_size(price: float, on: date) -> float:
    """Minimum price increment for an ordinary share at `price` on date `on`."""
    table = _table_for(on)
    bounds = [b for b, _ in table]
    i = max(bisect.bisect_right(bounds, price) - 1, 0)
    return table[i][1]


def tick_size_array(prices: np.ndarray, dates: pd.DatetimeIndex | pd.Series) -> np.ndarray:
    """Vectorised tick size, applying the schedule in force on each date."""
    prices = np.asarray(prices, dtype=float)
    d = pd.to_datetime(pd.Series(dates)).dt.date.to_numpy()
    out = np.full(prices.shape, np.nan)
    eff_dates = [e for e, _ in SPREAD_TABLES] + [date(9999, 1, 1)]
    for k, (eff, table) in enumerate(SPREAD_TABLES):
        m = (d >= eff) & (d < eff_dates[k + 1])
        if not m.any():
            continue
        bounds = np.array([b for b, _ in table])
        ticks = np.array([t for _, t in table])
        idx = np.clip(np.searchsorted(bounds, prices[m], side="right") - 1, 0, len(ticks) - 1)
        out[m] = ticks[idx]
    return out


def round_to_tick(price: float, on: date, side: str) -> float:
    """Round a fill price to a valid tick, against the trader (buy up, sell down)."""
    t = tick_size(price, on)
    steps = price / t
    steps = math.ceil(steps - 1e-9) if side == "buy" else math.floor(steps + 1e-9)
    return round(max(steps, 1) * t, 6)


# ---------------------------------------------------------------------------
# Statutory and exchange charges. (effective_from, rate) — rate on consideration.
# ---------------------------------------------------------------------------
STAMP_DUTY = [            # per side, buyer and seller (short sales included)
    (date(2001, 9, 1), 0.0010),
    (date(2021, 8, 1), 0.0013),
    (date(2023, 11, 17), 0.0010),
]
TRADING_FEE = [           # SEHK trading fee, per side
    (date(2000, 1, 1), 0.00005),
    (date(2023, 1, 1), 0.0000565),
]
SFC_LEVY = [              # per side
    (date(2000, 1, 1), 0.00003),
    (date(2014, 12, 1), 0.000027),
]
AFRC_LEVY = [             # FRC/AFRC transaction levy, per side
    (date(2000, 1, 1), 0.0),
    (date(2022, 1, 1), 0.0000015),
]
# CCASS stock settlement fee, per side: rate, min, max (HK$). VERIFY current schedule.
SETTLEMENT_FEE = (0.00002, 2.0, 100.0)


def _rate(schedule: list[tuple[date, float]], d: date) -> float:
    r = schedule[0][1]
    for eff, v in schedule:
        if d >= eff:
            r = v
    return r


@dataclass(frozen=True)
class CostBreakdown:
    stamp: float
    trading_fee: float
    sfc_levy: float
    afrc_levy: float
    settlement: float
    brokerage: float

    @property
    def total(self) -> float:
        return (self.stamp + self.trading_fee + self.sfc_levy + self.afrc_levy
                + self.settlement + self.brokerage)


def transaction_costs(consideration: float, on: date, brokerage_bps: float = 8.0,
                      brokerage_min: float = 50.0) -> CostBreakdown:
    """Explicit costs in HK$ for one side of a trade with value `consideration`.

    Excludes spread and market impact, which the execution model handles.
    Stamp duty is rounded up to the nearest dollar as the Stamp Office does.
    """
    v = abs(consideration)
    if v == 0:
        return CostBreakdown(0, 0, 0, 0, 0, 0)
    rate, lo, hi = SETTLEMENT_FEE
    return CostBreakdown(
        stamp=math.ceil(v * _rate(STAMP_DUTY, on)),
        trading_fee=v * _rate(TRADING_FEE, on),
        sfc_levy=v * _rate(SFC_LEVY, on),
        afrc_levy=v * _rate(AFRC_LEVY, on),
        settlement=min(max(v * rate, lo), hi),
        brokerage=max(v * brokerage_bps / 1e4, brokerage_min),
    )


def explicit_cost_rate(on: date, brokerage_bps: float = 8.0) -> float:
    """Approximate proportional one-side explicit cost (no minimums)."""
    return (_rate(STAMP_DUTY, on) + _rate(TRADING_FEE, on) + _rate(SFC_LEVY, on)
            + _rate(AFRC_LEVY, on) + SETTLEMENT_FEE[0] + brokerage_bps / 1e4)


# ---------------------------------------------------------------------------
# Trading sessions (local time). The daily engine only uses the opening auction
# (pre-opening session) and the close; the table documents the constraints.
# ---------------------------------------------------------------------------
SESSIONS = [
    # (effective_from, pre-open auction, morning, lunch, afternoon, closing auction)
    (date(2011, 3, 7), "09:00-09:30", "09:30-12:00", "12:00-13:30", "13:30-16:00", None),
    (date(2012, 3, 5), "09:00-09:30", "09:30-12:00", "12:00-13:00", "13:00-16:00", None),
    (date(2016, 7, 25), "09:00-09:30", "09:30-12:00", "12:00-13:00", "13:00-16:00", "16:00-16:10"),
]


def round_down_lots(shares: float, board_lot: int) -> int:
    """Whole board lots only; odd lots trade on a separate, illiquid book."""
    if board_lot <= 0:
        raise ValueError("board lot must be positive")
    return int(shares // board_lot) * board_lot
