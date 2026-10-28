"""Reproducible daily-data ramp-and-dump event detection.

Definition (all parameters in config `events`):

1. Run-up day t: close_t / min(close_{t-L..t-1}) - 1 >= run_return, measured in
   excess of the market over the same L days, AND mean traded value over
   t-L+1..t >= value_multiple x the median traded value of the preceding
   `baseline_window` days (t-L-B..t-L-1), floored to avoid divide-by-zero on
   dormant stocks.
2. Qualifying days closer than `episode_gap_days` merge into one episode.
3. Peak = highest close from the first qualifying day to `run_days` after
   the last one (prices often keep rising after turnover stops qualifying
   as abnormal). Trough = lowest close in (peak, peak + post_window].
4. Category:
   A  ramp_dump          trough / peak - 1 <= -drawdown
   B  sustained          max drawdown within `sustained_window` days < sustained_max_drawdown
   C  volatile           neither (large swings without the A-type collapse)
   censored              not enough data after the peak to classify

The peak and trough are hindsight quantities. They define the event
database; they are never used as model inputs. `first_signal_date` (first
qualifying day) is the earliest date a run-up rule could have flagged it.

Category B is a price-path proxy. Separating genuine news-driven repricing
needs announcement data (HKEXnews), which the pilot does not have.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from itertools import product

import numpy as np
import pandas as pd

BASELINE_FLOOR_HKD = 50_000.0


@dataclass(frozen=True)
class EventParams:
    run_days: int = 20
    run_return: float = 0.80
    value_multiple: float = 5.0
    post_window: int = 20
    drawdown: float = 0.40
    excess_vs_market: bool = True
    baseline_window: int = 120
    episode_gap_days: int = 5
    sustained_window: int = 60
    sustained_max_drawdown: float = 0.25


def to_wide(panel: pd.DataFrame, col: str) -> pd.DataFrame:
    return panel.pivot(index="date", columns="code", values=col).sort_index()


def runup_flags(close: pd.DataFrame, value: pd.DataFrame, mask: pd.DataFrame,
                market: pd.Series | None, p: EventParams) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Boolean frame of run-up days plus the run return and value ratio frames.

    Uses only data up to and including t, so it is also a valid causal
    stage-1 filter.
    """
    L, B = p.run_days, p.baseline_window
    trough = close.shift(1).rolling(L, min_periods=L).min()
    run = close / trough - 1.0
    if p.excess_vs_market and market is not None:
        m = market.reindex(close.index).ffill()
        mret = (m / m.shift(L) - 1.0).clip(lower=0.0)
        run = (1.0 + run).div(1.0 + mret, axis=0) - 1.0
    v_run = value.fillna(0).rolling(L, min_periods=L).mean()
    base = value.fillna(0).shift(L).rolling(B, min_periods=B // 2).median()
    ratio = v_run / base.clip(lower=BASELINE_FLOOR_HKD)
    bad = mask.fillna(False).astype(float).rolling(L + 1, min_periods=1).max().astype(bool)
    flags = (run >= p.run_return) & (ratio >= p.value_multiple) & ~bad & close.notna()
    return flags, run, ratio


def _episodes(flag_idx: np.ndarray, gap: int) -> list[tuple[int, int]]:
    if len(flag_idx) == 0:
        return []
    eps, s, prev = [], flag_idx[0], flag_idx[0]
    for i in flag_idx[1:]:
        if i - prev > gap:
            eps.append((s, prev))
            s = i
        prev = i
    eps.append((s, prev))
    return eps


def detect_events(close: pd.DataFrame, value: pd.DataFrame, mask: pd.DataFrame,
                  market: pd.Series | None, p: EventParams,
                  shortable: pd.DataFrame | None = None) -> pd.DataFrame:
    """Event database for one parameter set. One row per episode."""
    flags, run, ratio = runup_flags(close, value, mask, market, p)
    dates = close.index
    rows = []
    for code in close.columns:
        f = flags[code].to_numpy()
        idx = np.flatnonzero(f)
        if len(idx) == 0:
            continue
        c = close[code].to_numpy()
        v = value[code].fillna(0).to_numpy()
        valid = np.flatnonzero(~np.isnan(c))
        last_valid = valid[-1]
        for s, e in _episodes(idx, p.episode_gap_days):
            seg = c[s:min(e + p.run_days, last_valid) + 1]
            pk = s + int(np.nanargmax(seg))
            # run start: trough of the lookback window ending at the first signal
            lo = max(s - p.run_days, 0)
            rs = lo + int(np.nanargmin(c[lo:s])) if s > lo else s
            post_end = pk + p.post_window
            sus_end = pk + p.sustained_window
            censored = post_end > last_valid
            post = c[pk + 1:min(post_end, last_valid) + 1]
            sus = c[pk + 1:min(sus_end, last_valid) + 1]
            if len(post) and not np.all(np.isnan(post)):
                tr = pk + 1 + int(np.nanargmin(post))
                dd = c[tr] / c[pk] - 1.0
            else:
                tr, dd = pk, np.nan
            dd_sus = np.nanmin(sus) / c[pk] - 1.0 if len(sus) and not np.all(np.isnan(sus)) else np.nan
            if not censored and dd <= -p.drawdown:
                cat = "A_ramp_dump"
            elif censored:
                cat = "censored"
            elif sus_end <= last_valid and dd_sus > -p.sustained_max_drawdown:
                cat = "B_sustained"
            else:
                cat = "C_volatile"
            base_med = float(np.median(v[max(rs - p.baseline_window, 0):rs])) if rs > 0 else np.nan
            daily = c[rs + 1:pk + 1] / c[rs:pk] - 1.0
            rows.append({
                "code": int(code),
                "run_start_date": dates[rs], "first_signal_date": dates[s],
                "last_signal_date": dates[e], "peak_date": dates[pk], "trough_date": dates[tr],
                "run_start_close": c[rs], "peak_close": c[pk], "trough_close": c[tr],
                "run_return": c[pk] / c[rs] - 1.0,
                "signal_run_return": float(run[code].iloc[s]),
                "run_days_to_peak": pk - rs,
                "max_drawdown_post": dd, "days_peak_to_trough": tr - pk,
                "drawdown_sustained_window": dd_sus,
                "value_ratio_at_signal": float(ratio[code].iloc[s]),
                "peak_value_ratio": float(np.nanmax(ratio[code].iloc[s:e + 1])),
                "mean_value_run_hkd": float(np.mean(v[rs:pk + 1])),
                "baseline_median_value_hkd": base_med,
                "max_daily_return_run": float(np.nanmax(daily)) if len(daily) else np.nan,
                "decline_remaining_at_signal": _remaining(c, s, pk, tr),
                "category": cat,
                "shortable_at_peak": bool(shortable.at[dates[pk], code])
                if shortable is not None and code in shortable.columns else False,
            })
    ev = pd.DataFrame(rows)
    if len(ev):
        ev.insert(0, "event_id", [f"{r.code:05d}_{r.peak_date:%Y%m%d}" for r in ev.itertuples()])
    return ev


def _remaining(c: np.ndarray, s: int, pk: int, tr: int) -> float:
    """Share of the eventual peak-to-trough decline still ahead at close s.

    1.0 = signal at or above the peak (whole collapse ahead), 0 = signal at the trough.
    """
    if tr <= pk or c[pk] == c[tr]:
        return np.nan
    return float(np.clip((c[s] - c[tr]) / (c[pk] - c[tr]), 0.0, 1.5))


def sensitivity_grid(close, value, mask, market, grid: dict, base: EventParams,
                     shortable=None) -> pd.DataFrame:
    """Event counts and category mix across the definition grid."""
    out = []
    for L, R, V in product(grid["run_days"], grid["run_return"], grid["value_multiple"]):
        p0 = EventParams(**{**asdict(base), "run_days": L, "run_return": R, "value_multiple": V,
                            "post_window": max(grid["post_window"]), "drawdown": 0.0})
        ev = detect_events(close, value, mask, market, p0, shortable)
        for W, D in product(grid["post_window"], grid["drawdown"]):
            n = len(ev)
            if n == 0:
                out.append(dict(run_days=L, run_return=R, value_multiple=V, post_window=W,
                                drawdown=D, n_episodes=0))
                continue
            dd = ev["max_drawdown_post"] if W == max(grid["post_window"]) else \
                _dd_within(close, ev, W)
            done = ev["category"].ne("censored")
            a = (dd <= -D) & done
            out.append(dict(run_days=L, run_return=R, value_multiple=V, post_window=W, drawdown=D,
                            n_episodes=n, n_stocks=ev["code"].nunique(), n_A=int(a.sum()),
                            frac_A=float(a.sum() / max(done.sum(), 1)),
                            n_A_shortable=int((a & ev["shortable_at_peak"]).sum())))
    return pd.DataFrame(out)


def _dd_within(close: pd.DataFrame, ev: pd.DataFrame, w: int) -> pd.Series:
    res = []
    pos = {d: i for i, d in enumerate(close.index)}
    for r in ev.itertuples():
        c = close[r.code].to_numpy()
        i = pos[r.peak_date]
        seg = c[i + 1:i + 1 + w]
        res.append(np.nanmin(seg) / c[i] - 1.0 if len(seg) and not np.all(np.isnan(seg)) else np.nan)
    return pd.Series(res, index=ev.index)


def params_from_config(cfg_events: dict) -> EventParams:
    p = cfg_events["primary"]
    return EventParams(run_days=p["run_days"], run_return=p["run_return"],
                       value_multiple=p["value_multiple"], post_window=p["post_window"],
                       drawdown=p["drawdown"], excess_vs_market=p["excess_vs_market"],
                       baseline_window=cfg_events["baseline_window"],
                       episode_gap_days=cfg_events["episode_gap_days"],
                       sustained_window=cfg_events["sustained_window"],
                       sustained_max_drawdown=cfg_events["sustained_max_drawdown"])
