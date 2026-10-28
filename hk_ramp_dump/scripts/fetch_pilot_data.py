"""Fetch the pilot dataset.

    python scripts/fetch_pilot_data.py [--limit N]

1. HKEX List of Securities (current ordinary shares, board lots).
2. Every archived HKEX designated short-selling list (2016-05 onward).
3. Daily OHLCV from Yahoo for every current ordinary share, 2012 onward.

The Yahoo panel contains only securities listed today: delisted names are
missing (survivorship bias) and recycled stock codes can splice two issuers.
See docs/01_feasibility.md for the survivorship-free alternative.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from hkrd import data  # noqa: E402
from hkrd.config import load_config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="first N codes only (smoke test)")
    ap.add_argument("--skip-prices", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = load_config()
    raw, store, ref = cfg.path("raw_dir"), cfg.path("store_dir"), cfg.path("reference_dir")

    content = data._get(data.HKEX_LIST_URL)
    (raw / "ListOfSecurities.xlsx").write_bytes(content)
    uni = data.parse_hkex_list(content, cfg["universe"]["sub_categories"],
                               cfg["universe"]["trading_currency"])
    uni.to_csv(ref / "universe_current.csv", index=False)
    logging.info("universe: %d ordinary shares (%s)", len(uni), uni["board"].value_counts().to_dict())

    ds = data.fetch_ds_history(raw)
    data.save_parquet(ds, store / "ds_lists.parquet")
    logging.info("DS lists: %d files, %s .. %s", ds["effective_date"].nunique(),
                 ds["effective_date"].min().date(), ds["effective_date"].max().date())

    if args.skip_prices:
        return
    codes = uni["code"].tolist()[: args.limit]
    px = data.fetch_yahoo_prices(codes, cfg["sample"]["start"])
    data.save_parquet(px, raw / "yahoo_prices.parquet")
    import yfinance as yf

    b = yf.download(cfg["universe"]["benchmark_tickers"], start=cfg["sample"]["start"],
                    auto_adjust=True, progress=False)["Close"]
    b.index = b.index.tz_localize(None) if b.index.tz else b.index
    b.reset_index().rename(columns={"Date": "date"}).to_parquet(store / "benchmarks.parquet", index=False)

    panel = data.build_panel(px, cfg["data_quality"])
    data.save_parquet(panel, store / "panel.parquet")
    logging.info("panel: %d rows, %d codes, %s..%s, masked rows %d", len(panel),
                 panel["code"].nunique(), panel["date"].min().date(), panel["date"].max().date(),
                 int(panel["quality_mask"].sum()))


if __name__ == "__main__":
    pd.options.mode.copy_on_write = True
    main()
