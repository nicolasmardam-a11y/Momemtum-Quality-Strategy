import numpy as np
import pandas as pd
import pytest

from hkrd import validation as V

SAMPLE = {"development": ["2012-01-01", "2022-12-31"], "validation": ["2023-01-01", "2024-06-30"],
          "holdout": ["2024-07-01", "2026-10-27"], "first_test_year": 2016, "embargo_days": 20}
DATES = pd.bdate_range("2012-01-02", "2026-10-27")


def test_folds_purge_label_overlap():
    for f in V.walk_forward_folds(DATES, SAMPLE):
        gap = DATES.searchsorted(f.test_start) - DATES.searchsorted(f.train_end)
        assert gap >= SAMPLE["embargo_days"] + 1
        assert f.test_end < pd.Timestamp(SAMPLE["holdout"][0])


def test_holdout_locked():
    hf = V.holdout_fold(DATES, SAMPLE)
    with pytest.raises(PermissionError):
        V.split_masks(pd.Series(DATES), hf)
    tr, te = V.split_masks(pd.Series(DATES), hf, unlock_holdout=True)
    assert te.sum() > 0 and not (tr & te).any()


def test_event_groups_not_split():
    f = V.walk_forward_folds(DATES, SAMPLE)[0]
    d = pd.Series(pd.bdate_range(f.train_end - pd.Timedelta(days=10), periods=40))
    g = pd.Series(["ev1"] * len(d))
    tr, te = V.split_masks(d, f, groups=g)
    assert not tr.any()


def test_metrics_and_bootstrap():
    rng = np.random.default_rng(0)
    y = (rng.random(5000) < 0.02).astype(float)
    p = y * 0.5 + rng.random(5000) * 0.5
    r = V.classification_report(y, p)
    assert r["pr_auc"] > r["base_rate"] and r["roc_auc"] > 0.5
    b = V.random_alert_baseline(y, 0.01, n_draws=200)
    assert abs(b["mean"] - y.mean()) < 0.01
    bs = V.event_bootstrap(pd.Series(rng.normal(0.01, 0.05, 300)), pd.Series(np.repeat(np.arange(30), 10)), n=300)
    assert bs["ci_05"] < bs["point"] < bs["ci_95"]
