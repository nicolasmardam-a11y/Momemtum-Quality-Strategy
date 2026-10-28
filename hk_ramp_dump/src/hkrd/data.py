"""Data acquisition and the canonical daily panel.

Canonical panel (long format, one row per stock-day, sorted by code, date):

    code (int), date (datetime64), open, high, low, close, volume,
    value (HK$ traded value), traded (bool: volume > 0), quality_mask (bool)

Prices are split/consolidation-adjusted. `value` = close * volume, which is
invariant to share-count adjustments. Every downstream module consumes only
this schema, so swapping the pilot source (yfinance, current listings only)
for a survivorship-free source (Webb-site dump, Capital IQ) means writing one
adapter that emits the same columns.
"""
from __future__ import annotations

import io
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

HKEX_LIST_URL = ("https://www.hkex.com.hk/eng/services/trading/securities/"
                 "securitieslists/ListOfSecurities.xlsx")
DS_PAGE_URL = ("https://www.hkex.com.hk/Services/Trading/Securities/Securities-Lists/"
               "Designated-Securities-Eligible-for-Short-Selling?sc_lang=en")
DS_FILE_BASE = ("https://www.hkex.com.hk/-/media/HKEX-Market/Services/Trading/Securities/"
                "Securities-Lists/Designated-Securities-Eligible-for-Short-Selling/")

PANEL_COLUMNS = ["code", "date", "open", "high", "low", "close", "volume", "value",
                 "traded", "quality_mask"]


def _get(url: str, retries: int = 4) -> bytes:
    import requests

    for k in range(retries):
        try:
            r = requests.get(url, timeout=60)
            if r.status_code == 200:
                return r.content
            if r.status_code == 404:
                raise FileNotFoundError(url)
        except FileNotFoundError:
            raise
        except Exception as e:  # network hiccup: back off and retry
            log.warning("GET %s failed (%s), retry %d", url, e, k + 1)
        time.sleep(2 ** (k + 1))
    raise RuntimeError(f"could not fetch {url}")


# ---------------------------------------------------------------------------
# HKEX reference lists
# ---------------------------------------------------------------------------
def parse_hkex_list(content: bytes, sub_categories: list[str], currency: str = "HKD") -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(content), header=2)
    df = df.rename(columns=lambda c: str(c).split("\n")[0].strip())
    df = df[df["Category"].eq("Equity") & df["Sub-Category"].isin(sub_categories)]
    df = df[df["Trading Currency"].eq(currency)]
    out = pd.DataFrame({
        "code": df["Stock Code"].astype(int),
        "name": df["Name of Securities"].astype(str),
        "board": np.where(df["Sub-Category"].str.contains("GEM"), "GEM", "MAIN"),
        "board_lot": pd.to_numeric(df["Board Lot"].astype(str).str.replace(",", ""), errors="coerce"),
        "shortsell_eligible_now": df["Shortsell Eligible"].eq("Y"),
        "spread_table": df["Spread Table"].astype(str),
    })
    return out.reset_index(drop=True)


def list_ds_files(page_html: str) -> list[str]:
    import re

    return sorted(set(re.findall(r"ds_list\d{8}\.csv", page_html)))


def parse_ds_csv(content: bytes, fname: str) -> pd.DataFrame:
    """One dated HKEX 'Designated Securities Eligible for Short Selling' file."""
    import csv

    text = content.decode("utf-8-sig", errors="replace").splitlines()
    hdr = next(i for i, line in enumerate(text) if line.startswith("No.,"))
    rows = [r[:6] for r in csv.reader(text[hdr + 1:]) if len(r) >= 6 and r[1].strip().isdigit()]
    df = pd.DataFrame(rows, columns=["no", "code", "short_name", "currency", "type", "tick_exempt"])
    df = df[df["type"].str.strip().eq("EQTY") & df["currency"].str.strip().eq("HKD")]
    eff = pd.Timestamp(fname[len("ds_list"):len("ds_list") + 8])
    return pd.DataFrame({"effective_date": eff, "code": df["code"].astype(int).to_numpy(),
                         "tick_exempt": df["tick_exempt"].str.strip().ne("").to_numpy()})


def fetch_ds_history(raw_dir: Path, sleep: float = 0.2) -> pd.DataFrame:
    html = _get(DS_PAGE_URL).decode("utf-8", errors="replace")
    files = list_ds_files(html)
    out_dir = raw_dir / "ds_lists"
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for f in files:
        p = out_dir / f
        if not p.exists():
            try:
                p.write_bytes(_get(DS_FILE_BASE + f))
            except FileNotFoundError:
                log.warning("missing DS file %s", f)
                continue
            time.sleep(sleep)
        frames.append(parse_ds_csv(p.read_bytes(), f))
    return pd.concat(frames, ignore_index=True)


def shortable_on(ds: pd.DataFrame, dates: pd.Series, codes: pd.Series) -> np.ndarray:
    """True if `code` is on the designated list in force on each date.

    Uses the latest list with effective_date <= date. Dates before the first
    archived list (2016-05) return False: shortability is unknown, so it is
    treated as unavailable rather than assumed.
    """
    ds = ds[["effective_date", "code"]].drop_duplicates()
    eff = np.sort(ds["effective_date"].unique())
    members = {e: set(ds.loc[ds["effective_date"].eq(e), "code"]) for e in eff}
    d = pd.to_datetime(dates).to_numpy()
    idx = np.searchsorted(eff, d, side="right") - 1
    c = np.asarray(codes)
    return np.array([i >= 0 and ci in members[eff[i]] for i, ci in zip(idx, c)])


# ---------------------------------------------------------------------------
# Prices: yfinance pilot (current listings only => survivorship-biased)
# ---------------------------------------------------------------------------
def yahoo_symbol(code: int) -> str:
    return f"{code:04d}.HK"


def fetch_yahoo_prices(codes: list[int], start: str, batch: int = 60, sleep: float = 1.5) -> pd.DataFrame:
    import yfinance as yf

    frames = []
    for i in range(0, len(codes), batch):
        chunk = codes[i:i + batch]
        syms = [yahoo_symbol(c) for c in chunk]
        for attempt in range(4):
            try:
                raw = yf.download(syms, start=start, auto_adjust=False, actions=False,
                                  group_by="ticker", progress=False, threads=True)
                break
            except Exception as e:
                log.warning("batch %d failed (%s), retry", i, e)
                time.sleep(2 ** (attempt + 2))
        else:
            continue
        for c, s in zip(chunk, syms):
            if s not in raw.columns.get_level_values(0):
                continue
            d = raw[s].dropna(how="all")
            if d.empty:
                continue
            frames.append(pd.DataFrame({
                "code": c, "date": d.index.tz_localize(None) if d.index.tz else d.index,
                "open": d["Open"].to_numpy(), "high": d["High"].to_numpy(),
                "low": d["Low"].to_numpy(), "close": d["Close"].to_numpy(),
                "adj_close": d["Adj Close"].to_numpy(), "volume": d["Volume"].to_numpy(),
            }))
        log.info("fetched %d/%d", min(i + batch, len(codes)), len(codes))
        time.sleep(sleep)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------
def flag_suspect_adjustments(close: pd.Series, factors: list[float], tol: float,
                             min_abs_ret: float, max_abs_logret: float) -> pd.Series:
    """Flag daily moves that look like vendor corporate-action errors.

    A one-day close ratio within `tol` (log space) of a common consolidation or
    split factor is far more likely to be a missed adjustment than a trade.
    These are exactly the moves a naive ramp detector would mistake for
    ramps or dumps, so they are masked rather than kept.
    """
    lr = np.log(close / close.shift(1))
    big = lr.abs() >= np.log1p(min_abs_ret)
    logs = np.log(np.asarray(factors, dtype=float))
    near = np.zeros(len(lr), dtype=bool)
    a = lr.abs().to_numpy()
    for lf in logs:
        near |= np.abs(a - lf) <= tol
    return pd.Series((big.to_numpy() & near) | (a > max_abs_logret), index=close.index)


def build_panel(prices: pd.DataFrame, dq: dict) -> pd.DataFrame:
    """Raw vendor rows -> canonical panel with quality mask."""
    p = prices.copy()
    p = p[(p["close"] > 0) & p["close"].notna()]
    p = p.sort_values(["code", "date"]).drop_duplicates(["code", "date"], keep="last")
    for c in ["open", "high", "low"]:
        p[c] = p[c].where(p[c] > 0, p["close"])
    p["high"] = p[["high", "open", "close"]].max(axis=1)
    p["low"] = p[["low", "open", "close"]].min(axis=1)
    p["volume"] = p["volume"].fillna(0).clip(lower=0)
    p["value"] = p["close"] * p["volume"]
    p["traded"] = p["volume"] > 0

    def _mask(g: pd.DataFrame) -> pd.Series:
        s = flag_suspect_adjustments(g["close"], dq["suspect_factors"], dq["suspect_tolerance"],
                                     dq["suspect_min_abs_return"], dq["max_abs_daily_logret"])
        k = dq["mask_days_around"]
        return s.rolling(2 * k + 1, center=True, min_periods=1).max().astype(bool)

    p["quality_mask"] = p.groupby("code", group_keys=False)[["close"]].apply(_mask)
    return p[PANEL_COLUMNS].reset_index(drop=True)


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def load_panel(store_dir: Path) -> pd.DataFrame:
    import duckdb

    q = f"SELECT * FROM read_parquet('{(store_dir / 'panel.parquet').as_posix()}') ORDER BY code, date"
    return duckdb.sql(q).df()
