from datetime import date

import numpy as np
import pandas as pd
import pytest

from hkrd import hkex


@pytest.mark.parametrize("price,expected", [(0.05, 0.001), (0.25, 0.005), (0.49, 0.005), (0.5, 0.01),
                                            (9.99, 0.01), (15.0, 0.02), (50, 0.05), (150, 0.1)])
def test_legacy_ticks(price, expected):
    assert hkex.tick_size(price, date(2020, 1, 2)) == expected


def test_tick_reduction_phase1():
    assert hkex.tick_size(15.0, date(2025, 8, 4)) == 0.01
    assert hkex.tick_size(30.0, date(2025, 8, 4)) == 0.02
    assert hkex.tick_size(30.0, date(2025, 8, 1)) == 0.05


def test_tick_array_matches_scalar():
    prices = np.array([0.1, 0.3, 5.0, 15.0, 30.0])
    dates = pd.to_datetime(["2020-01-02"] * 2 + ["2025-09-01"] * 3)
    arr = hkex.tick_size_array(prices, dates)
    assert list(arr) == [hkex.tick_size(p, d.date()) for p, d in zip(prices, dates)]


def test_round_to_tick_against_trader():
    assert hkex.round_to_tick(0.3012, date(2020, 1, 2), "buy") == pytest.approx(0.305)
    assert hkex.round_to_tick(0.3012, date(2020, 1, 2), "sell") == pytest.approx(0.300)


def test_stamp_duty_schedule():
    v = 1_000_000
    assert hkex.transaction_costs(v, date(2020, 1, 2), 0, 0).stamp == 1000
    assert hkex.transaction_costs(v, date(2022, 1, 3), 0, 0).stamp == 1300
    assert hkex.transaction_costs(v, date(2024, 1, 2), 0, 0).stamp == 1000


def test_brokerage_minimum_and_lots():
    c = hkex.transaction_costs(10_000, date(2020, 1, 2), 8, 50)
    assert c.brokerage == 50
    assert hkex.round_down_lots(12_345, 2000) == 12_000
    with pytest.raises(ValueError):
        hkex.round_down_lots(100, 0)
