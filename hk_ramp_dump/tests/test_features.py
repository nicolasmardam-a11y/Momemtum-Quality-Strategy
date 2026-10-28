import numpy as np
import pandas as pd

from hkrd import events, features


def _w(panel):
    return {k: events.to_wide(panel, k) for k in ["open", "high", "low", "close", "value"]}


def test_features_do_not_use_future(panel):
    w = _w(panel)
    f1 = features.wide_features(w["open"], w["high"], w["low"], w["close"], w["value"], None)
    cut = 300
    w2 = {k: x.copy() for k, x in w.items()}
    for k in w2:
        w2[k].iloc[cut:] = w2[k].iloc[cut:] * 3.7
    f2 = features.wide_features(w2["open"], w2["high"], w2["low"], w2["close"], w2["value"], None)
    for name in features.FEATURES:
        a, b = f1[name].iloc[:cut], f2[name].iloc[:cut]
        assert np.allclose(a.to_numpy(), b.to_numpy(), equal_nan=True), name


def test_labels_use_only_future(panel):
    w = _w(panel)
    L1 = features.forward_labels(w["close"], w["open"], [1, 5], 20, [0.4])
    w2 = {k: x.copy() for k, x in w.items()}
    w2["close"].iloc[:100] *= 0.1     # change the past only
    L2 = features.forward_labels(w2["close"], w2["open"], [1, 5], 20, [0.4])
    assert np.allclose(L1["dd20_40"].iloc[150:300], L2["dd20_40"].iloc[150:300], equal_nan=True)


def test_crash_label_on_synthetic_dump(panel):
    w = _w(panel)
    L = features.forward_labels(w["close"], w["open"], [1], 20, [0.4])
    # at the synthetic peak (index 249) the next 10 days fall 60%
    assert L["dd20_40"][2].iloc[249] == 1.0
    assert np.isnan(L["dd20_40"][2].iloc[-1])   # incomplete window -> NaN, not 0


def test_feature_list_complete(panel):
    w = _w(panel)
    f = features.wide_features(w["open"], w["high"], w["low"], w["close"], w["value"], None)
    assert set(features.FEATURES) <= set(f)
