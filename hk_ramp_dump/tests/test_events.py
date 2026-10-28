import numpy as np
import pandas as pd

from hkrd import events
from hkrd.data import flag_suspect_adjustments


def wide(panel):
    return (events.to_wide(panel, "close"), events.to_wide(panel, "value"),
            events.to_wide(panel, "quality_mask"))


def test_detects_synthetic_ramp_dump(panel):
    c, v, m = wide(panel)
    p = events.EventParams(run_days=20, run_return=0.8, value_multiple=5, post_window=20, drawdown=0.4)
    ev = events.detect_events(c, v, m, None, p)
    hit = ev[ev["code"] == 2]
    assert len(hit) == 1
    row = hit.iloc[0]
    assert row["category"] == "A_ramp_dump"
    assert row["max_drawdown_post"] <= -0.4
    assert row["first_signal_date"] <= row["peak_date"]
    # random-walk names should not produce A events at these thresholds
    assert (ev.loc[ev["code"] != 2, "category"] != "A_ramp_dump").all()


def test_quality_mask_suppresses_detection(panel):
    panel = panel.copy()
    sel = (panel["code"] == 2)
    panel.loc[sel, "quality_mask"] = True
    c, v, m = wide(panel)
    ev = events.detect_events(c, v, m, None, events.EventParams())
    assert (ev["code"] != 2).all() if len(ev) else True


def test_runup_flags_are_causal(panel):
    c, v, m = wide(panel)
    p = events.EventParams()
    f1, _, _ = events.runup_flags(c, v, m, None, p)
    c2 = c.copy()
    c2.iloc[300:] *= 5.0          # change the future only
    f2, _, _ = events.runup_flags(c2, v, m, None, p)
    pd.testing.assert_frame_equal(f1.iloc[:300], f2.iloc[:300])


def test_flag_suspect_consolidation():
    s = pd.Series([1.0, 1.01, 10.1, 10.2, 10.15])   # missed 10-into-1 consolidation
    f = flag_suspect_adjustments(s, [10], 0.03, 0.6, 2.5)
    assert bool(f.iloc[2]) and not f.iloc[[0, 1, 3, 4]].any()


def test_sensitivity_grid_shape(panel):
    c, v, m = wide(panel)
    grid = {"run_days": [10, 20], "run_return": [0.8], "value_multiple": [5.0],
            "post_window": [20, 60], "drawdown": [0.3, 0.4]}
    g = events.sensitivity_grid(c, v, m, None, grid, events.EventParams())
    assert len(g) == 2 * 1 * 1 * 2 * 2
