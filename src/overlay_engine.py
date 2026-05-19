"""Daily exposure overlay — FROZEN, reuses the research overlay verbatim.

exposure = vol_target(10% ann, 60d) x multi_asset_trend(URTH, EEM, 200d SMA,
OFF only when BOTH below SMA). This is the exact production overlay from
config/strategy.yaml; nothing here is tuned.

Persists the prior exposure so the day-over-day jump can be range-checked
(exposure_change_threshold kill switch).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ibkr_connection import KillSwitch


class OverlayEngine:
    def __init__(self, cfg, logger=None):
        self.cfg = cfg
        self.log = logger
        self.state_path = cfg.path("state_dir") / "exposure_state.json"

    def _load_series(self):
        ov = self.cfg.overlay
        from gfe.overlays import vol_target_overlay, multi_asset_trend

        hist = pd.read_csv(self.cfg.path("naked_returns"),
                           parse_dates=[0], index_col=0).iloc[:, 0]
        bench = pd.read_parquet(self.cfg.path("benchmarks_wide"))
        if isinstance(bench.columns, pd.MultiIndex):
            bench.columns = bench.columns.get_level_values(0)
        urth = bench["URTH"].dropna()
        eem_df = pd.read_parquet(self.cfg.path("eem"))
        if isinstance(eem_df.columns, pd.MultiIndex):
            eem_df.columns = eem_df.columns.get_level_values(0)
        eem = eem_df["Close"]
        if isinstance(eem, pd.DataFrame):
            eem = eem.iloc[:, 0]

        vt = vol_target_overlay(hist,
                                target_vol_annual=ov["target_vol_annual"],
                                lookback_days=ov["vol_lookback_days"])
        mt = multi_asset_trend({"URTH": urth, "EEM": eem},
                               sma_days=ov["trend_sma_days"],
                               n_required=ov["trend_n_required_off"])
        mt = mt.reindex(hist.index).ffill().fillna(1.0)
        combined = (vt.reindex(hist.index).ffill() * mt).clip(upper=1.0)
        return hist, urth, eem, vt, mt, combined

    def compute(self) -> dict:
        ov = self.cfg.overlay
        hist, urth, eem, vt, mt, combined = self._load_series()
        if combined.empty:
            raise KillSwitch("overlay produced no exposure series "
                             "(portfolio drift / overlay calculation failure)")
        exposure = float(combined.iloc[-1])
        vol_s = float(vt.iloc[-1])
        trend_s = float(mt.iloc[-1])
        asof = pd.Timestamp(combined.index[-1]).strftime("%Y-%m-%d")

        sma = ov["trend_sma_days"]
        urth_now, urth_sma = float(urth.iloc[-1]), float(urth.rolling(sma).mean().iloc[-1])
        eem_now, eem_sma = float(eem.iloc[-1]), float(eem.rolling(sma).mean().iloc[-1])

        prior = None
        if self.state_path.exists():
            try:
                prior = float(json.loads(self.state_path.read_text()).get("exposure"))
            except Exception:
                prior = None
        change = None if prior is None else abs(exposure - prior)

        result = {
            "asof": asof,
            "exposure": exposure,
            "vol_scalar": vol_s,
            "trend_scalar": trend_s,
            "urth_price": urth_now, "urth_sma200": urth_sma,
            "urth_above_sma": urth_now > urth_sma,
            "eem_price": eem_now, "eem_sma200": eem_sma,
            "eem_above_sma": eem_now > eem_sma,
            "prior_exposure": prior,
            "exposure_change": change,
        }
        if self.log:
            self.log.info("overlay: exposure=%.3f (vol=%.2f trend=%.0f) "
                          "URTH %s SMA, EEM %s SMA, prior=%s",
                          exposure, vol_s, trend_s,
                          ">" if result["urth_above_sma"] else "<",
                          ">" if result["eem_above_sma"] else "<", prior)
        return result

    def persist(self, exposure: float, asof: str):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(
            {"exposure": exposure, "asof": asof}, indent=2))
