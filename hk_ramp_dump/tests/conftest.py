import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def make_panel(n_days=400, codes=(1, 2, 3), seed=0, ramp_code=2, ramp_at=250):
    """Synthetic panel: random walks; `ramp_code` gets a 20-day +150% ramp on
    5-10x value followed by a -60% collapse. Used only to test mechanics."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-01", periods=n_days)
    rows = []
    for c in codes:
        r = rng.normal(0, 0.02, n_days)
        vol = rng.lognormal(13, 0.3, n_days)
        if c == ramp_code:
            r[ramp_at - 20:ramp_at] = np.log(2.5) / 20
            vol[ramp_at - 20:ramp_at] *= 8
            r[ramp_at:ramp_at + 10] = np.log(0.4) / 10
            vol[ramp_at:ramp_at + 10] *= 4
        close = 1.0 * np.exp(np.cumsum(r))
        op = close * np.exp(rng.normal(0, 0.005, n_days))
        hi = np.maximum(op, close) * 1.01
        lo = np.minimum(op, close) * 0.99
        rows.append(pd.DataFrame({"code": c, "date": dates, "open": op, "high": hi, "low": lo,
                                  "close": close, "volume": vol}))
    p = pd.concat(rows, ignore_index=True)
    p["value"] = p["close"] * p["volume"]
    p["traded"] = p["volume"] > 0
    p["quality_mask"] = False
    return p


@pytest.fixture
def panel():
    return make_panel()
