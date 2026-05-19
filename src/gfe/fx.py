"""FX helpers to convert local-currency notional to USD."""
from __future__ import annotations

import pandas as pd
import yfinance as yf

from .utils import CACHE_DIR, get_logger

log = get_logger("fx")

# Yahoo FX symbols (X = "EURUSD=X" returns EUR/USD)
YF_FX_MAP = {
    "USD": None,
    "EUR": "EURUSD=X",
    "GBP": "GBPUSD=X",
    "CHF": "CHFUSD=X",
    "JPY": "JPYUSD=X",
    "CAD": "CADUSD=X",
    "AUD": "AUDUSD=X",
    "SGD": "SGDUSD=X",
    "HKD": "HKDUSD=X",
    "INR": "INRUSD=X",
    "KRW": "KRWUSD=X",
    "TWD": "TWDUSD=X",
    "SEK": "SEKUSD=X",
    "NOK": "NOKUSD=X",
    "DKK": "DKKUSD=X",
    "BRL": "BRLUSD=X",
    "MXN": "MXNUSD=X",
    "ZAR": "ZARUSD=X",
    "PLN": "PLNUSD=X",
}

# Map exchange suffix -> local currency
SUFFIX_TO_CCY = {
    "": "USD",      # US (no suffix)
    ".L": "GBP",
    ".TO": "CAD",
    ".V": "CAD",
    ".SW": "CHF",
    ".T": "JPY",
    ".AX": "AUD",
    ".HK": "HKD",
    ".SI": "SGD",
    ".NS": "INR",
    ".BO": "INR",
    ".KS": "KRW",
    ".KQ": "KRW",
    ".TW": "TWD",
    ".ST": "SEK",
    ".OL": "NOK",
    ".CO": "DKK",
    ".HE": "EUR",
    ".DE": "EUR",
    ".F": "EUR",
    ".PA": "EUR",
    ".MI": "EUR",
    ".MC": "EUR",
    ".AS": "EUR",
    ".BR": "EUR",
    ".IR": "EUR",
    ".LS": "EUR",
    ".VI": "EUR",
    ".SA": "BRL",
    ".MX": "MXN",
    ".JO": "ZAR",
    ".WA": "PLN",
}


def get_ticker_currency(ticker: str) -> str:
    for suffix in sorted(SUFFIX_TO_CCY.keys(), key=lambda s: -len(s)):
        if suffix and ticker.endswith(suffix):
            return SUFFIX_TO_CCY[suffix]
    return "USD"


def fetch_fx_history(start: str = "2010-01-01") -> pd.DataFrame:
    """Fetch FX/USD daily history for all currencies we use. Returns DataFrame
    with columns = currency, values = price in USD per unit of currency.
    USD column is always 1.0."""
    cache = CACHE_DIR / "fx_history.parquet"
    if cache.exists():
        try:
            return pd.read_parquet(cache)
        except Exception:
            pass

    syms = [s for s in YF_FX_MAP.values() if s]
    log.info("Fetching FX history for %d currencies", len(syms))
    df = yf.download(syms, start=start, progress=False, auto_adjust=False, threads=True)
    if "Close" in df.columns.get_level_values(0):
        close = df["Close"]
    else:
        close = df  # type: ignore[assignment]
    out = pd.DataFrame(index=close.index)
    for ccy, yfsym in YF_FX_MAP.items():
        if yfsym is None:
            out[ccy] = 1.0
        elif yfsym in close.columns:
            out[ccy] = close[yfsym]
        else:
            log.warning("FX miss: %s (%s)", ccy, yfsym)
            out[ccy] = float("nan")
    out = out.ffill().bfill()
    out.to_parquet(cache)
    return out


def latest_fx_rates() -> dict[str, float]:
    df = fetch_fx_history()
    return df.iloc[-1].to_dict()
