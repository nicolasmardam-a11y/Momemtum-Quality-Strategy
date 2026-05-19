"""Last-close price access with explicit staleness control.

No live market-data subscription is used (paper, read-safe). Prices come from
the cached panels produced by the research pipeline:
  - data/prices/wide_close_local.parquet  (local-currency closes)
  - per-ticker data/prices/<ticker>.parquet fallback
  - data/prices/wide_close_usd_em.parquet + FX as last-resort derivation

Every price is returned with its as-of date and source. Anything older than
risk.max_price_staleness_days triggers the stale-price kill switch upstream.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from ibkr_connection import KillSwitch


class MarketData:
    def __init__(self, cfg, logger=None, fx=None):
        self.cfg = cfg
        self.log = logger
        self.fx = fx                       # used to convert USD-panel fallback -> local
        self.max_stale = int(cfg.risk["max_price_staleness_days"])
        self._local = self._read(cfg.path("wide_local"))
        self._usd = self._read(cfg.path("wide_usd"))
        self.root = cfg.root

    @staticmethod
    def _read(p: Path):
        if not Path(p).exists():
            return pd.DataFrame()
        df = pd.read_parquet(p)
        df.index = pd.to_datetime(df.index)
        return df.sort_index()

    def _from_panel(self, df, ticker):
        if df.empty or ticker not in df.columns:
            return None
        s = df[ticker].dropna()
        if s.empty:
            return None
        return float(s.iloc[-1]), pd.Timestamp(s.index[-1])

    def _from_cache(self, ticker):
        p = self.root / "data" / "prices" / f"{ticker.replace('/', '_')}.parquet"
        if not p.exists():
            return None
        try:
            d = pd.read_parquet(p)
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            if "Close" not in d.columns:
                return None
            s = d["Close"]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            s = s.dropna()
            if s.empty:
                return None
            return float(s.iloc[-1]), pd.Timestamp(s.index[-1])
        except Exception:
            return None

    def last_local_price(self, ticker: str, currency: str | None = None):
        """Return dict(price, asof, source, stale_days, is_stale) in the
        instrument's LOCAL currency. If only the USD panel has the name, the
        USD close is converted to `currency` via FX (price_local = usd /
        usd_per(ccy)); without FX/currency that path is refused so a
        mispriced limit can never be generated."""
        hit = self._from_panel(self._local, ticker) or self._from_cache(ticker)
        source = "wide_local/cache"
        if hit is None:
            usd_hit = self._from_panel(self._usd, ticker)
            if usd_hit is not None:
                if currency in (None, "") or self.fx is None:
                    raise KillSwitch(
                        f"{ticker}: only USD price available and no FX/currency "
                        f"to derive a local price (refusing mispriced limit)")
                usd_price, asof = usd_hit
                if str(currency).upper() == "USD":
                    hit = (usd_price, asof)
                else:
                    rate = self.fx.usd_per(currency)        # USD per 1 local unit
                    hit = (usd_price / rate, asof)
                source = "wide_usd->local(fx)"
        if hit is None:
            raise KillSwitch(f"no price available for {ticker} (stale-price rule)")
        price, asof = hit
        stale_days = (pd.Timestamp(datetime.now().date()) - asof.normalize()).days
        return {
            "price": price,
            "asof": asof.strftime("%Y-%m-%d"),
            "source": source,
            "stale_days": int(stale_days),
            "is_stale": bool(stale_days > self.max_stale),
        }

    def last_usd_price(self, ticker: str):
        hit = self._from_panel(self._usd, ticker)
        if hit is None:
            return None
        price, asof = hit
        return {"price": price, "asof": asof.strftime("%Y-%m-%d")}
