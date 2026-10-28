"""Configuration loading. Paths in the YAML are relative to the project root."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    raw: dict[str, Any]
    root: Path = PROJECT_ROOT

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def path(self, key: str) -> Path:
        p = self.root / self.raw["paths"][key]
        p.mkdir(parents=True, exist_ok=True)
        return p


def load_config(path: str | Path | None = None) -> Config:
    path = Path(path) if path else PROJECT_ROOT / "config" / "research.yaml"
    with open(path) as f:
        return Config(yaml.safe_load(f))
