"""FX conversion for a EUR investor base.

data/fx/fx_history.parquet columns are currency codes; the value is USD per
1 unit of that currency (USD column == 1.0), consistent with the research
pipeline (local_to_usd = amount_local * fx[ccy]).

EUR conversion: amount_eur = amount_usd / fx['EUR'].

Missing or NaN rate for any currency in use -> KillSwitch (hard rule:
"missing FX rate").
"""
from __future__ import annotations

import pandas as pd

from ibkr_connection import KillSwitch


class FXRates:
    def __init__(self, cfg, logger=None):
        self.cfg = cfg
        self.log = logger
        df = pd.read_parquet(cfg.path("fx_history"))
        df.index = pd.to_datetime(df.index)
        df = df.sort_index().ffill()
        if df.empty:
            raise KillSwitch("fx_history is empty (missing FX rate)")
        self.asof = df.index[-1].strftime("%Y-%m-%d")
        self._row = df.iloc[-1]
        if "USD" not in self._row.index:
            # USD base is implicitly 1.0 if absent
            self._row = pd.concat([self._row, pd.Series({"USD": 1.0})])
        self.base = cfg.base_ccy
        self._usd_per_base = self._rate(self.base)

    def _rate(self, ccy: str) -> float:
        if ccy == "USD":
            return 1.0
        if ccy not in self._row.index:
            raise KillSwitch(f"missing FX rate for {ccy}")
        v = self._row[ccy]
        if pd.isna(v) or float(v) <= 0:
            raise KillSwitch(f"invalid/NaN FX rate for {ccy}")
        return float(v)

    # ------------------------------------------------------------------ #
    def usd_per(self, ccy: str) -> float:
        return self._rate(ccy)

    def to_usd(self, amount: float, ccy: str) -> float:
        return amount * self._rate(ccy)

    def to_base(self, amount: float, ccy: str) -> float:
        """Convert an amount in `ccy` into the investor base currency (EUR)."""
        return self.to_usd(amount, ccy) / self._usd_per_base

    def convert(self, amount: float, from_ccy: str, to_ccy: str) -> float:
        return self.to_usd(amount, from_ccy) / self._rate(to_ccy)

    def check_currencies(self, currencies) -> list[str]:
        """Return the list of currencies with a usable rate; raises on any
        missing so the caller can surface a single, explicit kill switch."""
        missing = []
        for c in sorted(set(currencies)):
            try:
                self._rate(c)
            except KillSwitch:
                missing.append(c)
        if missing:
            raise KillSwitch(f"missing FX rate(s): {missing}")
        return sorted(set(currencies))
