import numpy as np
import pandas as pd

from hkrd import events, features
from hkrd.models import GBMModel, RegimeModel, RulesModel, TwoStageModel

from conftest import make_panel

LGB = dict(n_estimators=20, learning_rate=0.1, num_leaves=7, min_child_samples=5, verbose=-1)


def _dataset():
    frames = [make_panel(n_days=500, codes=range(10 * k, 10 * k + 10), seed=k, ramp_code=10 * k + 3,
                         ramp_at=200 + 20 * k) for k in range(4)]
    p = pd.concat(frames, ignore_index=True)
    w = {c: events.to_wide(p, c) for c in ["open", "high", "low", "close", "value"]}
    F = features.wide_features(w["open"], w["high"], w["low"], w["close"], w["value"], None)
    L = features.forward_labels(w["close"], w["open"], [1], 20, [0.4])
    df = features.stack({**F, **L}).reset_index().dropna(subset=["ret_60", "dd20_40"])
    return df.sort_values(["code", "date"]).reset_index(drop=True)


def test_all_models_fit_and_predict():
    df = _dataset()
    y = df["dd20_40"]
    assert y.sum() > 0
    for m in (RulesModel(), GBMModel(LGB, 0.5), TwoStageModel(LGB),
              RegimeModel(n_states=2, n_iter=5, fit_sample_tickers=20)):
        m.fit(df, y, df["code"], df["date"])
        p = m.predict_proba(df, df["code"], df["date"])
        assert len(p) == len(df)
        ok = ~np.isnan(p)
        assert ok.mean() > 0.9 and (p[ok] >= 0).all() and (p[ok] <= 1).all()


def test_hmm_filter_is_causal():
    df = _dataset()
    m = RegimeModel(n_states=2, n_iter=5, fit_sample_tickers=20).fit(df, df["dd20_40"], df["code"], df["date"])
    cut = df["date"].sort_values().unique()[300]
    a = m.filtered(df, df["code"], df["date"])
    df2 = df.copy()
    late = df2["date"] > cut
    df2.loc[late, ["ret_1", "value_ratio_1", "close_loc_1"]] *= -3.0
    b = m.filtered(df2, df2["code"], df2["date"])
    early = (df["date"] <= cut).to_numpy()
    assert np.allclose(a[early], b[early], equal_nan=True)
