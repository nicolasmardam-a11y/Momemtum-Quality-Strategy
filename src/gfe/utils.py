"""Utility helpers shared across the GFE package."""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
CACHE_DIR = ROOT / "cache"
REPORTS_DIR = ROOT / "reports"
EQUITY_DIR = ROOT / "equity"
DIAG_DIR = ROOT / "diagnostics"
LOGS_DIR = ROOT / "logs"

for _d in (CACHE_DIR, REPORTS_DIR, EQUITY_DIR, DIAG_DIR, LOGS_DIR,
           CACHE_DIR / "fundamentals", CACHE_DIR / "scoring",
           CACHE_DIR / "universe", CACHE_DIR / "prices"):
    _d.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(LOGS_DIR / f"{name}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def load_yaml(name: str) -> dict[str, Any]:
    p = CONFIG_DIR / name
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=True)


def load_parquet(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None


def with_retry(fn, retries: int = 3, delay: float = 1.0, label: str = ""):
    last = None
    for i in range(retries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(delay * (i + 1))
    raise RuntimeError(f"Failed after {retries} retries ({label}): {last}")
