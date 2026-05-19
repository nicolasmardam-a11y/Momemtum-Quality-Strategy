"""5-pillar fundamental scoring engine with sector-relative z-scores.

Pillars (each is a weighted blend of normalized sub-metrics):
- Quality (Q): ROIC, ROE, ROA, gross_margin, operating_margin, fcf_margin, -accruals
- Growth (G): rev_cagr_3y, ebit_cagr_3y, eps_cagr_3y, fcf_cagr_3y, -share_count_3y_chg
- Balance Sheet (B): -net_debt_to_ebitda, interest_coverage, fcf_yield>0 flag, -gross_leverage
- Valuation (V): fcf_yield, earnings_yield, 1/ev_ebit, 1/ev_ebitda, 1/pe, 1/pb
- Capital Allocation (C): buyback_yield, dividend_yield, fcf_to_ni, share_count_3y_chg (neg)

Process:
1. Winsorize each raw metric at [1%, 99%] within sector
2. Convert to sector-relative z-score (per sector x metric)
3. Average within pillar
4. Combine pillars per scheme weights
5. Penalize missing data (reduce pillar weight by missing_share)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .utils import get_logger

log = get_logger("scoring")

# Each pillar maps to a list of (metric_column, direction). Direction +1 means "higher is better"
PILLAR_METRICS: dict[str, list[tuple[str, int]]] = {
    "Q": [
        ("roic", +1),
        ("roe", +1),
        ("roa", +1),
        ("gross_margin", +1),
        ("operating_margin", +1),
        ("fcf_margin", +1),
        ("accruals_to_assets", -1),  # high accruals -> bad
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
        # FCF positive flag handled via fcf_local sign in penalties
    ],
    "V": [
        ("fcf_yield", +1),
        ("earnings_yield", +1),
        ("fcf_yield_mktcap", +1),
        # Use inverse of ratios so higher = cheaper
        ("ev_ebit_inv", +1),
        ("ev_ebitda_inv", +1),
        ("pe_inv", +1),
        ("pb_inv", +1),
    ],
    "C": [
        ("buyback_yield", +1),
        ("dividend_yield", +1),
        ("fcf_to_ni", +1),
        ("share_count_3y_chg", -1),  # negative = buyback = good
    ],
}


def winsorize(s: pd.Series, p_low: float = 0.01, p_high: float = 0.99) -> pd.Series:
    if s.empty:
        return s
    lo, hi = s.quantile(p_low), s.quantile(p_high)
    return s.clip(lower=lo, upper=hi)


def sector_zscore(s: pd.Series, sectors: pd.Series, min_n: int = 5) -> pd.Series:
    """Z-score within sector. If sector has <min_n, fall back to overall."""
    out = pd.Series(index=s.index, dtype=float)
    for sec, idx in sectors.groupby(sectors).groups.items():
        vals = s.loc[idx].dropna()
        if len(vals) >= min_n and vals.std(ddof=0) > 0:
            vals_w = winsorize(vals)
            z = (vals_w - vals_w.mean()) / vals_w.std(ddof=0)
            out.loc[vals.index] = z
    # Overall fallback for any NaN that have a non-NaN raw value
    missing = out.isna() & s.notna()
    if missing.any():
        vals = s[missing].dropna()
        all_vals = s.dropna()
        if len(all_vals) >= min_n and all_vals.std(ddof=0) > 0:
            mu = winsorize(all_vals).mean()
            sd = winsorize(all_vals).std(ddof=0)
            out.loc[vals.index] = (vals - mu) / sd
    return out


def add_inverse_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add inverse-valuation metrics: 1 / ev_ebit etc. (higher = cheaper)."""
    df = df.copy()
    for col, new in [("ev_ebit", "ev_ebit_inv"),
                     ("ev_ebitda", "ev_ebitda_inv"),
                     ("pe", "pe_inv"),
                     ("pb", "pb_inv")]:
        if col in df.columns:
            x = df[col].copy()
            # Keep only positive valuations (negative earnings invalid)
            x = x.where(x > 0)
            df[new] = 1.0 / x
        else:
            df[new] = np.nan
    return df


def compute_pillar_scores(df: pd.DataFrame, sector_col: str = "sector",
                          sector_neutral: bool = True) -> pd.DataFrame:
    """For each pillar, compute average sector-relative z-score of its sub-metrics.

    Adds columns: score_Q, score_G, score_B, score_V, score_C, n_filled_Q, n_filled_G, ...
    """
    df = add_inverse_metrics(df)
    sectors = df[sector_col].fillna("Unknown") if sector_col in df.columns else pd.Series("Unknown", index=df.index)

    scores: dict[str, pd.Series] = {}
    coverage: dict[str, pd.Series] = {}

    for pillar, mlist in PILLAR_METRICS.items():
        zs = []
        for col, direction in mlist:
            if col not in df.columns:
                continue
            s = df[col].astype(float)
            if sector_neutral:
                z = sector_zscore(s, sectors)
            else:
                vals = s.dropna()
                if vals.std(ddof=0) > 0:
                    vw = winsorize(vals)
                    mu = vw.mean(); sd = vw.std(ddof=0)
                    z = (s - mu) / sd
                else:
                    z = pd.Series(np.nan, index=s.index)
            zs.append(z * direction)
        if zs:
            df_z = pd.concat(zs, axis=1)
            scores[f"score_{pillar}"] = df_z.mean(axis=1, skipna=True)
            coverage[f"cov_{pillar}"] = df_z.notna().mean(axis=1)
        else:
            scores[f"score_{pillar}"] = pd.Series(np.nan, index=df.index)
            coverage[f"cov_{pillar}"] = pd.Series(0.0, index=df.index)

    res = pd.concat({**scores, **coverage}, axis=1)
    return res


def combine_with_weights(scores: pd.DataFrame, weights: dict[str, float],
                         missing_penalty: bool = True) -> pd.Series:
    """Combine pillar scores into composite using configured weights.

    Penalty: if a pillar has 0 coverage for that ticker, its weight is
    re-allocated proportionally to others (so we don't penalize globally),
    BUT a missing_penalty is applied: composite *= (avg_coverage).
    """
    composite = pd.Series(0.0, index=scores.index)
    total_w_per_ticker = pd.Series(0.0, index=scores.index)

    for pillar, w in weights.items():
        col = f"score_{pillar}"
        cov_col = f"cov_{pillar}"
        if col not in scores.columns:
            continue
        s = scores[col]
        cov = scores[cov_col] if cov_col in scores.columns else pd.Series(1.0, index=s.index)
        has_data = s.notna() & (cov > 0)
        composite[has_data] += s[has_data].fillna(0) * w
        total_w_per_ticker[has_data] += w

    # Normalize for partial coverage; require at least 50% pillar weight covered
    composite = composite.where(total_w_per_ticker >= 0.5)
    composite = composite / total_w_per_ticker.replace(0, np.nan)

    if missing_penalty:
        # Average coverage across pillars (weighted)
        avg_cov = pd.Series(0.0, index=scores.index)
        wsum = 0.0
        for pillar, w in weights.items():
            cov_col = f"cov_{pillar}"
            if cov_col in scores.columns:
                avg_cov += scores[cov_col].fillna(0) * w
                wsum += w
        if wsum > 0:
            avg_cov = avg_cov / wsum
        # Multiply composite by avg_cov^0.5 (gentle penalty for missing fields)
        composite = composite * (avg_cov ** 0.5)

    return composite


def apply_quality_floor(df: pd.DataFrame, scores: pd.DataFrame,
                        composite: pd.Series,
                        min_roic: float | None = 0.04,
                        require_positive_fcf_ttm: bool = True,
                        max_net_debt_ebitda: float | None = 6.0) -> pd.Series:
    """Eliminate value traps: zero out the composite for stocks failing safety floors."""
    result = composite.copy()
    if min_roic is not None and "roic" in df.columns:
        mask = (df["roic"] < min_roic) | df["roic"].isna()
        result[mask] = np.nan
    if require_positive_fcf_ttm and "fcf_local" in df.columns:
        mask = df["fcf_local"] <= 0
        result[mask] = np.nan
    if max_net_debt_ebitda is not None and "net_debt_to_ebitda" in df.columns:
        mask = df["net_debt_to_ebitda"] > max_net_debt_ebitda
        result[mask] = np.nan
    return result
