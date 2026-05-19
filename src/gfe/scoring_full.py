"""6-factor composite scoring per user spec.

Factors:
- Q: Quality (ROIC, ROE, ROA, margins, fcf_margin, accruals)
- M: Momentum (mom_12_1, mom_6m, risk_adj_mom, trend_sma200, dist_52w_high)
- V: Value (fcf_yield, earnings_yield, ev_ebit_inv, ev_ebitda_inv, pe_inv, pb_inv, dividend_yield)
- G: Growth/revisions proxy (rev_cagr_3y, ebit_cagr_3y, eps_cagr_3y, fcf_cagr_3y)
- B: Balance sheet (net_debt_to_ebitda neg, debt_to_ebitda neg, interest_coverage, fcf_to_ni)
- LV: Low Vol / Defensive (vol_1y neg, downvol_1y neg, maxdd_1y, idio_vol neg)

Weight schemes:
- baseline (user spec): Q=0.25, M=0.25, V=0.20, G=0.15, B=0.10, LV=0.05
- quality_momentum: Q=0.30, M=0.30, V=0.15, G=0.15, B=0.05, LV=0.05
- value_quality:    Q=0.30, M=0.10, V=0.35, G=0.10, B=0.10, LV=0.05
- defensive_compounder: Q=0.30, M=0.15, V=0.15, G=0.10, B=0.15, LV=0.15
- aggressive_gm:    Q=0.20, M=0.35, V=0.10, G=0.25, B=0.05, LV=0.05
- equal_weight:     Q=1/6 each

Ranking variants:
- raw (global)
- sector_neutral (z-score within sector)
- country_neutral (z within country)
- region_neutral (z within region)
- sector_region_neutral (z within sector x region)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .utils import get_logger
from .scoring import winsorize, sector_zscore

log = get_logger("scoring_full")

PILLAR_METRICS: dict[str, list[tuple[str, int]]] = {
    "Q": [
        ("roic", +1),
        ("roe", +1),
        ("roa", +1),
        ("gross_margin", +1),
        ("operating_margin", +1),
        ("fcf_margin", +1),
        ("accruals_to_assets", -1),
    ],
    "M": [
        ("mom_12_1", +1),
        ("mom_6m", +1),
        ("risk_adj_mom", +1),
        ("trend_sma200", +1),
        ("dist_52w_high", +1),  # closer to high = better
    ],
    "V": [
        ("fcf_yield", +1),
        ("earnings_yield", +1),
        ("ev_ebit_inv", +1),
        ("ev_ebitda_inv", +1),
        ("pe_inv", +1),
        ("pb_inv", +1),
        ("dividend_yield_yf", +1),
    ],
    "G": [
        ("rev_cagr_3y", +1),
        ("ebit_cagr_3y", +1),
        ("eps_cagr_3y", +1),
        ("fcf_cagr_3y", +1),
    ],
    "B": [
        ("net_debt_to_ebitda", -1),
        ("debt_to_ebitda", -1),
        ("interest_coverage", +1),
        ("fcf_to_ni", +1),
    ],
    "LV": [
        ("vol_1y", -1),
        ("downvol_1y", -1),
        ("maxdd_1y", +1),  # less negative = better => sign +
        ("idio_vol", -1),
    ],
}

WEIGHT_SCHEMES: dict[str, dict[str, float]] = {
    "baseline":           {"Q": 0.25, "M": 0.25, "V": 0.20, "G": 0.15, "B": 0.10, "LV": 0.05},
    "quality_momentum":   {"Q": 0.30, "M": 0.30, "V": 0.15, "G": 0.15, "B": 0.05, "LV": 0.05},
    "value_quality":      {"Q": 0.30, "M": 0.10, "V": 0.35, "G": 0.10, "B": 0.10, "LV": 0.05},
    "defensive_compounder":{"Q": 0.30,"M": 0.15, "V": 0.15, "G": 0.10, "B": 0.15, "LV": 0.15},
    "aggressive_gm":      {"Q": 0.20, "M": 0.35, "V": 0.10, "G": 0.25, "B": 0.05, "LV": 0.05},
    "equal_weight":       {"Q": 1/6,  "M": 1/6,  "V": 1/6,  "G": 1/6,  "B": 1/6,  "LV": 1/6},
}


def add_inverse_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col, new in [("ev_ebit", "ev_ebit_inv"), ("ev_ebitda", "ev_ebitda_inv"),
                     ("pe", "pe_inv"), ("pb", "pb_inv")]:
        if col in df.columns:
            x = df[col].where(df[col] > 0)
            df[new] = 1.0 / x
        else:
            df[new] = np.nan
    return df


def group_zscore(s: pd.Series, group: pd.Series, min_n: int = 5) -> pd.Series:
    """Z-score within group; fallback to overall if group too small."""
    out = pd.Series(index=s.index, dtype=float)
    for g_val, idx in group.groupby(group).groups.items():
        vals = s.loc[idx].dropna()
        if len(vals) >= min_n and vals.std(ddof=0) > 0:
            vw = winsorize(vals)
            mu, sd = vw.mean(), vw.std(ddof=0)
            out.loc[vals.index] = (vals - mu) / sd
    missing = out.isna() & s.notna()
    if missing.any():
        all_vals = s.dropna()
        if len(all_vals) >= min_n and all_vals.std(ddof=0) > 0:
            vw = winsorize(all_vals)
            mu, sd = vw.mean(), vw.std(ddof=0)
            out.loc[s[missing].index] = (s[missing] - mu) / sd
    return out


def _resolve_neutrality(df: pd.DataFrame, mode: str) -> pd.Series:
    """Return per-row group label for z-score grouping."""
    if mode == "raw":
        return pd.Series("ALL", index=df.index)
    if mode == "sector_neutral":
        return df["sector"].fillna("Unknown") if "sector" in df.columns else df.get("sector_hint", pd.Series("Unknown", index=df.index)).fillna("Unknown")
    if mode == "country_neutral":
        return df["country"].fillna("XX") if "country" in df.columns else df.get("country_yf", pd.Series("XX", index=df.index)).fillna("XX")
    if mode == "region_neutral":
        return df["region"].fillna("XX")
    if mode == "sector_region_neutral":
        sec = df["sector"].fillna("Unknown") if "sector" in df.columns else df.get("sector_hint", pd.Series("Unknown", index=df.index)).fillna("Unknown")
        reg = df["region"].fillna("XX")
        return sec.astype(str) + "|" + reg.astype(str)
    raise ValueError(f"unknown neutrality mode: {mode}")


def compute_full_pillars(df: pd.DataFrame, neutrality: str = "sector_neutral") -> pd.DataFrame:
    """Compute the 6-pillar score table for a single point-in-time DataFrame.

    Input df: per-ticker row with all factor columns present (NaN allowed).
    Required identity columns: sector, country, region (sector_hint fallback).
    """
    df = add_inverse_metrics(df)
    group = _resolve_neutrality(df, neutrality)

    score_cols: dict[str, pd.Series] = {}
    coverage: dict[str, pd.Series] = {}
    for pillar, metrics in PILLAR_METRICS.items():
        zs = []
        for col, sign in metrics:
            if col not in df.columns:
                continue
            s = df[col].astype(float)
            z = group_zscore(s, group)
            zs.append(z * sign)
        if zs:
            zm = pd.concat(zs, axis=1)
            score_cols[f"score_{pillar}"] = zm.mean(axis=1, skipna=True)
            coverage[f"cov_{pillar}"] = zm.notna().mean(axis=1)
        else:
            score_cols[f"score_{pillar}"] = pd.Series(np.nan, index=df.index)
            coverage[f"cov_{pillar}"] = pd.Series(0.0, index=df.index)
    return pd.concat({**score_cols, **coverage}, axis=1)


def composite_with_weights(scores: pd.DataFrame, weights: dict[str, float],
                           min_total_w: float = 0.50, missing_penalty: bool = True) -> pd.Series:
    """Combine pillars; require >=min_total_w of pillar weights covered.

    Missing-data penalty: composite *= sqrt(avg coverage) to gently downweight
    sparse-data stocks (still allows them to rank, but with discount).
    """
    composite = pd.Series(0.0, index=scores.index)
    total_w = pd.Series(0.0, index=scores.index)
    for pillar, w in weights.items():
        col = f"score_{pillar}"
        cov_col = f"cov_{pillar}"
        if col not in scores.columns:
            continue
        s = scores[col]
        cov = scores[cov_col] if cov_col in scores.columns else pd.Series(1.0, index=s.index)
        has = s.notna() & (cov > 0)
        composite[has] += s[has].fillna(0) * w
        total_w[has] += w

    composite = composite.where(total_w >= min_total_w)
    composite = composite / total_w.replace(0, np.nan)

    if missing_penalty:
        avg_cov = pd.Series(0.0, index=scores.index)
        wsum = 0.0
        for pillar, w in weights.items():
            cov_col = f"cov_{pillar}"
            if cov_col in scores.columns:
                avg_cov += scores[cov_col].fillna(0) * w
                wsum += w
        if wsum > 0:
            avg_cov = avg_cov / wsum
        composite = composite * (avg_cov ** 0.5)
    return composite


def apply_quality_floor(df: pd.DataFrame, composite: pd.Series,
                        min_roic: float | None = 0.04,
                        require_positive_fcf_ttm: bool = True,
                        max_net_debt_ebitda: float | None = 6.0,
                        min_mkt_cap_usd: float | None = 1e9) -> pd.Series:
    """Zero out composite for stocks failing safety floors."""
    res = composite.copy()
    if min_roic is not None and "roic" in df.columns:
        bad = (df["roic"] < min_roic) | df["roic"].isna()
        res[bad] = np.nan
    if require_positive_fcf_ttm and "fcf_local" in df.columns:
        bad = df["fcf_local"] <= 0
        res[bad] = np.nan
    if max_net_debt_ebitda is not None and "net_debt_to_ebitda" in df.columns:
        bad = df["net_debt_to_ebitda"] > max_net_debt_ebitda
        res[bad] = np.nan
    if min_mkt_cap_usd is not None and "market_cap_usd" in df.columns:
        bad = df["market_cap_usd"] < min_mkt_cap_usd
        res[bad] = np.nan
    return res


def rank_universe(scores_df: pd.DataFrame, weights: dict[str, float],
                  neutrality: str = "sector_neutral",
                  apply_floors: bool = True) -> pd.DataFrame:
    """End-to-end: take a tidy per-ticker DataFrame, compute pillars, composite, rank."""
    pillars = compute_full_pillars(scores_df, neutrality=neutrality)
    composite = composite_with_weights(pillars, weights)
    if apply_floors:
        composite = apply_quality_floor(scores_df, composite)
    out = scores_df.join(pillars)
    out["composite"] = composite
    out["composite_rank"] = composite.rank(ascending=False, method="min")
    out["composite_pct"] = composite.rank(pct=True)
    return out
