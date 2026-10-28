"""Four competing crash-probability models with a common interface:

    m.fit(X: DataFrame, y: Series, codes: Series, dates: Series) -> self
    m.predict_proba(X, codes, dates) -> np.ndarray   # P(target = 1)

A  RulesModel       transparent run-up + distribution checklist, calibrated by
                    empirical frequency per score level in the training data.
B  RegimeModel      Gaussian HMM on (return, relative value). Live/test
                    predictions use *causal forward-filtered* state
                    probabilities only, never smoothed posteriors.
C  GBMModel         LightGBM on all features, all stock-days.
D  TwoStageModel    stage 1: abnormal upward regime filter; stage 2: LightGBM
                    estimating P(collapse | stage 1) on stage-1 rows only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import logsumexp
from sklearn.linear_model import LogisticRegression

from .features import FEATURES


def candidate_mask(X: pd.DataFrame, ret_20_min: float, value_ratio_20_min: float) -> np.ndarray:
    """Stage-1 abnormal upward regime. Features are log-scale."""
    return ((X["ret_20"] >= np.log1p(ret_20_min)) &
            (X["value_ratio_20"] >= np.log1p(value_ratio_20_min))).to_numpy()


# ---------------------------------------------------------------------------
class RulesModel:
    """Score = in_runup x (1 + number of distribution warnings)."""

    name = "A_rules"

    def __init__(self, ret_20_min=0.5, value_ratio_20_min=3.0):
        self.ret_20_min, self.vr_min = ret_20_min, value_ratio_20_min
        self.table: pd.Series | None = None
        self.prior = 0.0

    def score(self, X: pd.DataFrame) -> np.ndarray:
        runup = candidate_mask(X, self.ret_20_min, self.vr_min)
        warns = ((X["dist_high20"] <= -0.10).astype(int) + (X["upper_wick_5"] >= 0.40).astype(int)
                 + (X["down_value_share_10"] >= 0.55).astype(int)
                 + (X["reversal_on_volume_5"] >= 1).astype(int) + (X["failed_highs_10"] >= 2).astype(int))
        return np.where(runup, 1 + warns.to_numpy(), 0)

    def fit(self, X, y, codes=None, dates=None):
        s = self.score(X)
        df = pd.DataFrame({"s": s, "y": np.asarray(y, float)}).dropna()
        self.prior = df["y"].mean()
        g = df.groupby("s")["y"].agg(["sum", "count"])
        k = 20.0  # shrink sparse score levels toward the prior
        self.table = (g["sum"] + k * self.prior) / (g["count"] + k)
        return self

    def predict_proba(self, X, codes=None, dates=None):
        s = self.score(X)
        return pd.Series(s).map(self.table).fillna(self.prior).to_numpy()


# ---------------------------------------------------------------------------
class RegimeModel:
    """Diagonal Gaussian HMM fitted on training-period sequences, then a causal
    forward filter run over each stock's history; a logistic regression maps
    filtered state probabilities (and their 5-day change) to crash risk."""

    name = "B_regime_hmm"
    obs_cols = ["ret_1", "value_ratio_1", "close_loc_1"]

    def __init__(self, n_states=3, n_iter=50, fit_sample_tickers=400, seed=7):
        self.n_states, self.n_iter, self.n_tickers, self.seed = n_states, n_iter, fit_sample_tickers, seed

    def _obs(self, X):
        o = X[self.obs_cols].to_numpy(dtype=float, copy=True)
        o[:, 0] = np.clip(o[:, 0], -0.5, 0.5)
        return o

    def fit(self, X, y, codes, dates):
        from hmmlearn.hmm import GaussianHMM

        rng = np.random.default_rng(self.seed)
        o = self._obs(X)
        ok = ~np.isnan(o).any(axis=1)
        codes = np.asarray(codes)
        uc = np.unique(codes[ok])
        pick = set(rng.choice(uc, min(self.n_tickers, len(uc)), replace=False))
        sel = ok & np.isin(codes, list(pick))
        order = np.lexsort((np.asarray(dates)[sel], codes[sel]))
        oo, cc = o[sel][order], codes[sel][order]
        lengths = np.diff(np.flatnonzero(np.r_[True, cc[1:] != cc[:-1], True]))
        self.hmm = GaussianHMM(self.n_states, covariance_type="diag", n_iter=self.n_iter,
                               random_state=self.seed).fit(oo, lengths)
        P = self.filtered(X, codes, dates)
        self.lr = LogisticRegression(C=1.0, max_iter=500)
        yy = np.asarray(y, float)
        m = ~np.isnan(P).any(axis=1) & ~np.isnan(yy)
        self.lr.fit(P[m], yy[m])
        return self

    def filtered(self, X, codes, dates) -> np.ndarray:
        """Forward-filtered P(state_t | obs_1..t) per stock, plus 5-day changes.

        Runs date by date across all stocks at once. A stock-day without an
        observation propagates the previous belief through the transition
        matrix with no emission update, so the filter never peeks ahead.
        """
        h = self.hmm
        K = self.n_states
        logA = np.log(h.transmat_)
        means = h.means_
        cov = np.asarray(h.covars_)
        var = np.array([np.diag(c) for c in cov]) if cov.ndim == 3 else cov
        const = -0.5 * np.log(2 * np.pi * var).sum(axis=1)
        o = self._obs(X)
        ud, di = np.unique(np.asarray(dates), return_inverse=True)
        uc, ci = np.unique(np.asarray(codes), return_inverse=True)
        O = np.full((len(ud), len(uc), o.shape[1]), np.nan)
        O[di, ci] = o
        la = np.tile(np.log(h.startprob_ + 1e-300), (len(uc), 1))
        W = np.empty((len(ud), len(uc), K))
        for t in range(len(ud)):
            x = O[t]
            has = ~np.isnan(x).any(axis=1)
            ll = const[None, :] - 0.5 * (((np.nan_to_num(x)[:, None, :] - means[None]) ** 2) / var[None]).sum(2)
            la = np.where(has[:, None], la + ll, la)
            la = la - logsumexp(la, axis=1, keepdims=True)
            W[t] = np.exp(la)
            la = logsumexp(la[:, :, None] + logA[None], axis=1)
        d5 = W - np.concatenate([np.full((5, len(uc), K), np.nan), W[:-5]], axis=0)
        return np.hstack([W[di, ci], d5[di, ci]])

    def predict_proba(self, X, codes, dates):
        P = self.filtered(X, codes, dates)
        res = np.full(len(P), np.nan)
        m = ~np.isnan(P).any(axis=1)
        res[m] = self.lr.predict_proba(P[m])[:, 1]
        return res


# ---------------------------------------------------------------------------
class GBMModel:
    name = "C_lightgbm"

    def __init__(self, params: dict, negative_subsample=0.1, features=None, seed=7):
        self.params = dict(params)
        self.neg = negative_subsample
        self.features = features or FEATURES
        self.seed = seed

    def fit(self, X, y, codes=None, dates=None):
        import lightgbm as lgb

        yy = np.asarray(y, float)
        ok = ~np.isnan(yy)
        rng = np.random.default_rng(self.seed)
        keep = ok & ((yy == 1) | (rng.random(len(yy)) < self.neg))
        w = np.where(yy[keep] == 1, 1.0, 1.0 / self.neg)
        self.model = lgb.LGBMClassifier(**{**self.params, "random_state": self.seed, "verbose": -1})
        self.model.fit(X.loc[keep, self.features], yy[keep], sample_weight=w)
        return self

    def predict_proba(self, X, codes=None, dates=None):
        return self.model.predict_proba(X[self.features])[:, 1]

    def importance(self) -> pd.Series:
        imp = self.model.booster_.feature_importance("gain")
        return pd.Series(imp / imp.sum(), index=self.features).sort_values(ascending=False)


class TwoStageModel:
    name = "D_two_stage"

    def __init__(self, params: dict, ret_20_min=0.5, value_ratio_20_min=3.0, features=None, seed=7):
        p = dict(params)
        p["min_child_samples"] = max(20, p.get("min_child_samples", 200) // 4)
        self.stage2 = GBMModel(p, negative_subsample=1.0, features=features, seed=seed)
        self.ret_20_min, self.vr_min = ret_20_min, value_ratio_20_min

    def fit(self, X, y, codes=None, dates=None):
        m = candidate_mask(X, self.ret_20_min, self.vr_min)
        self.stage2.fit(X.loc[m], np.asarray(y, float)[m])
        yy = np.asarray(y, float)
        self.outside_rate = float(np.nanmean(yy[~m]))   # P(crash) outside stage 1
        return self

    def predict_proba(self, X, codes=None, dates=None):
        m = candidate_mask(X, self.ret_20_min, self.vr_min)
        p = np.full(len(X), self.outside_rate)
        if m.any():
            p[m] = self.stage2.predict_proba(X.loc[m])
        return p

    def importance(self):
        return self.stage2.importance()
