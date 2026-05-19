"""Load and HARD-validate the bot configuration.

Safety rules are enforced here so they cannot be bypassed by a YAML typo:
- ibkr.paper_port must be 4002
- ibkr.live_port must differ from paper_port
- ibkr.paper_account_prefix must be "DU"
- safety.paper_only must be True
- safety.live_trading_enabled must be False
- safety.refuse_market_orders must be True
- mode (if provided) must be one of signal_only / preview / paper_trade

Any violation raises ConfigError and the bot refuses to start.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
VALID_MODES = ("signal_only", "preview", "paper_trade")


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class BotConfig:
    raw: dict[str, Any]
    root: Path = ROOT

    # convenience accessors -------------------------------------------------
    @property
    def base_ccy(self) -> str:
        return self.raw["investor_base_currency"]

    @property
    def ibkr(self) -> dict:
        return self.raw["ibkr"]

    @property
    def safety(self) -> dict:
        return self.raw["safety"]

    @property
    def order(self) -> dict:
        return self.raw["order"]

    @property
    def overlay(self) -> dict:
        return self.raw["overlay"]

    @property
    def risk(self) -> dict:
        return self.raw["risk"]

    @property
    def costs(self) -> dict:
        return self.raw["costs"]

    def path(self, key: str) -> Path:
        return self.root / self.raw["paths"][key]


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ConfigError(msg)


def load_config(config_path: str | Path | None = None, mode: str | None = None) -> BotConfig:
    cfg_path = Path(config_path) if config_path else (ROOT / "config" / "bot.yaml")
    if not cfg_path.exists():
        raise ConfigError(f"config not found: {cfg_path}")
    raw = yaml.safe_load(cfg_path.read_text()) or {}

    # ---- structural presence ----
    for key in ("investor_base_currency", "ibkr", "safety", "paths",
                "order", "overlay", "risk", "costs"):
        _require(key in raw, f"missing top-level config key: {key}")

    ib = raw["ibkr"]
    sf = raw["safety"]
    od = raw["order"]

    # ---- HARD safety invariants ----
    _require(ib.get("paper_port") == 4002,
             f"ibkr.paper_port must be 4002 (got {ib.get('paper_port')})")
    _require(ib.get("live_port") != ib.get("paper_port"),
             "ibkr.live_port must differ from paper_port")
    _require(str(ib.get("paper_account_prefix", "")).upper() == "DU",
             "ibkr.paper_account_prefix must be 'DU'")
    _require(sf.get("paper_only") is True, "safety.paper_only must be true")
    _require(sf.get("live_trading_enabled") is False,
             "safety.live_trading_enabled must be false (no live path permitted)")
    _require(sf.get("refuse_market_orders") is True,
             "safety.refuse_market_orders must be true")
    _require(str(od.get("type", "")).upper() == "LMT",
             "order.type must be LMT (market orders are forbidden)")

    if mode is not None:
        _require(mode in VALID_MODES, f"invalid mode {mode!r}; allowed {VALID_MODES}")

    # ---- path existence (inputs must exist; outputs are created on demand) ----
    for k in ("security_master", "current_portfolio", "ibkr_contracts",
              "ibkr_contracts_full", "tradable_universe", "naked_returns",
              "benchmarks_wide", "eem", "fx_history"):
        p = ROOT / raw["paths"][k]
        _require(p.exists(), f"required input missing: {k} -> {p}")

    for k in ("state_dir", "reports_daily", "logs_execution", "logs_system"):
        (ROOT / raw["paths"][k]).mkdir(parents=True, exist_ok=True)

    return BotConfig(raw=raw)
