"""Configuration loading and validation.

The YAML file is parsed strictly: unknown keys are rejected so that a typo such as
``min_usd`` instead of ``min_usdc`` fails loudly instead of silently using a default.
Notification credentials are never read from the file; they come only from
environment variables (see notify.py).
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
CONFIDENCE_LEVELS = ("confirmed", "probable", "weak", "none")
ACTIVITY_TYPES = ("TRADE", "SPLIT", "MERGE", "REDEEM", "CONVERSION", "REWARD", "YIELD",
                  "TAKER_REBATE", "MAKER_REBATE")
BET_SIDES = ("BUY", "SELL", "SPLIT", "MERGE", "REDEEM", "CONVERSION")


class ConfigError(ValueError):
    """Raised for any invalid or inconsistent configuration."""


@dataclass(frozen=True)
class WalletConfig:
    address: str
    label: str
    cluster_id: str | None = None
    cluster_confidence: str = "none"
    cluster_note: str | None = None
    enabled: bool = True
    # Optional per-wallet overrides; None means "use the global alerting value".
    min_usdc: float | None = None
    alert_sides: tuple[str, ...] | None = None


@dataclass(frozen=True)
class PollConfig:
    interval_seconds: float = 30.0
    jitter_seconds: float = 5.0
    overlap_seconds: int = 600
    ingest_safety_seconds: int = 30
    page_limit: int = 500
    activity_types: tuple[str, ...] = ("TRADE", "SPLIT", "MERGE", "REDEEM", "CONVERSION")
    initial_backfill_hours: float = 24.0
    gap_horizon_hours: float = 6.0
    max_pages_per_poll: int = 5000
    request_timeout_seconds: float = 15.0
    retries: int = 2
    status_check: bool = True
    cache_bust: bool = True


@dataclass(frozen=True)
class GroupingConfig:
    gap_minutes: float = 10.0


@dataclass(frozen=True)
class AlertingConfig:
    alert_sides: tuple[str, ...] = ("BUY",)
    min_usdc: float = 0.0
    max_alert_age_minutes: float = 360.0
    alert_on_bootstrap: bool = False
    follow_usd: float = 100.0
    taker_crosscheck: bool = True
    # Bounds that keep a very active wallet (hundreds of bets an hour) from stalling the loop or flooding channels.
    max_enrichments_per_cycle: int = 10
    max_alerts_per_wallet_per_hour: int = 30


@dataclass(frozen=True)
class CopyCandidateConfig:
    enabled: bool = False
    max_detection_lag_seconds: float = 60.0
    max_deterioration_cents: float = 1.0
    max_spread_cents: float = 2.0
    require_not_in_play: bool = True
    require_accepting_orders: bool = True
    min_ask_depth_usd_within_1c: float = 500.0
    max_follower_fee_pct: float = 2.0
    min_cluster_confidence: str = "none"


@dataclass(frozen=True)
class HealthConfig:
    status_lag_threshold_seconds: float = 120.0
    status_snapshot_max_age_seconds: float = 300.0
    stale_after_intervals: int = 5
    notify_after_consecutive_failures: int = 2
    renotify_minutes: float = 60.0
    digest_interval_hours: float = 24.0


@dataclass(frozen=True)
class ChannelConfig:
    enabled: bool = False
    path: str | None = None            # file channel only
    rate_per_minute: float = 30.0
    burst: int = 5


@dataclass(frozen=True)
class NotificationsConfig:
    delivery_semantics: str = "at_least_once"   # or "at_most_once"
    max_attempts: int = 8
    backoff_base_seconds: float = 5.0
    backoff_max_seconds: float = 600.0
    send_timeout_seconds: float = 10.0
    channels: dict[str, ChannelConfig] = field(default_factory=lambda: {
        "console": ChannelConfig(enabled=True, rate_per_minute=600, burst=50),
        "file": ChannelConfig(enabled=True, path="alerts/out/alerts.ndjson", rate_per_minute=600, burst=50),
        "telegram": ChannelConfig(enabled=False, rate_per_minute=20, burst=3),
        "email": ChannelConfig(enabled=False, rate_per_minute=1, burst=3),
    })


@dataclass(frozen=True)
class StorageConfig:
    db_path: str = "alerts/out/alerts.sqlite"


@dataclass(frozen=True)
class Config:
    wallets: tuple[WalletConfig, ...]
    poll: PollConfig = PollConfig()
    grouping: GroupingConfig = GroupingConfig()
    alerting: AlertingConfig = AlertingConfig()
    copy_candidate: CopyCandidateConfig = CopyCandidateConfig()
    health: HealthConfig = HealthConfig()
    notifications: NotificationsConfig = NotificationsConfig()
    storage: StorageConfig = StorageConfig()

    def wallet(self, address: str) -> WalletConfig:
        for w in self.wallets:
            if w.address == address.lower():
                return w
        raise KeyError(address)

    def min_usdc(self, w: WalletConfig) -> float:
        return self.alerting.min_usdc if w.min_usdc is None else w.min_usdc

    def alert_sides(self, w: WalletConfig) -> tuple[str, ...]:
        return self.alerting.alert_sides if w.alert_sides is None else w.alert_sides


def resolve_path(p: str | Path) -> Path:
    """Relative paths in the config are resolved against the polymarket_research directory."""
    p = Path(p)
    return p if p.is_absolute() else PROJECT_ROOT / p


def _build(cls: type, data: Any, where: str, overrides: dict[str, Any] | None = None):
    """Instantiate a frozen dataclass from a mapping, rejecting unknown keys."""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"{where}: expected a mapping, got {type(data).__name__}")
    names = {f.name: f for f in dataclasses.fields(cls)}
    unknown = sorted(set(data) - set(names))
    if unknown:
        raise ConfigError(f"{where}: unknown key(s) {unknown}; allowed: {sorted(names)}")
    kwargs: dict[str, Any] = {}
    for k, v in data.items():
        f = names[k]
        default = f.default if f.default is not dataclasses.MISSING else None
        if isinstance(default, tuple) or k in ("activity_types", "alert_sides"):
            if v is None:
                kwargs[k] = None
                continue
            if isinstance(v, str):
                v = [x.strip() for x in v.split(",") if x.strip()]
            if not isinstance(v, list):
                raise ConfigError(f"{where}.{k}: expected a list")
            v = tuple(str(x).upper() for x in v)
        elif isinstance(default, bool):
            if not isinstance(v, bool):
                raise ConfigError(f"{where}.{k}: expected true/false, got {v!r}")
        elif isinstance(default, (int, float)) and not isinstance(default, bool):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ConfigError(f"{where}.{k}: expected a number, got {v!r}")
            if v < 0:
                raise ConfigError(f"{where}.{k}: must be >= 0, got {v!r}")
            v = type(default)(v) if isinstance(default, float) else v
        kwargs[k] = v
    kwargs.update(overrides or {})
    return cls(**kwargs)


def _wallet(data: Any, i: int) -> WalletConfig:
    where = f"wallets[{i}]"
    if not isinstance(data, dict):
        raise ConfigError(f"{where}: expected a mapping")
    data = dict(data)
    thresholds = data.pop("thresholds", None) or {}
    if not isinstance(thresholds, dict):
        raise ConfigError(f"{where}.thresholds: expected a mapping")
    bad = sorted(set(thresholds) - {"min_usdc", "alert_sides"})
    if bad:
        raise ConfigError(f"{where}.thresholds: unknown key(s) {bad}")
    allowed = {"address", "label", "cluster_id", "cluster_confidence", "cluster_note", "enabled"}
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(f"{where}: unknown key(s) {unknown}")
    addr = str(data.get("address", ""))
    if not ADDRESS_RE.match(addr):
        # The Data API answers 200 with an empty list for a malformed address, so a
        # typo here would look exactly like "no new trades". Reject it up front.
        raise ConfigError(f"{where}.address: {addr!r} is not a 0x-prefixed 40-hex-digit address")
    conf = str(data.get("cluster_confidence") or "none").lower()
    if conf not in CONFIDENCE_LEVELS:
        raise ConfigError(f"{where}.cluster_confidence: {conf!r} not in {CONFIDENCE_LEVELS}")
    min_usdc = thresholds.get("min_usdc")
    if min_usdc is not None and (isinstance(min_usdc, bool) or not isinstance(min_usdc, (int, float)) or min_usdc < 0):
        raise ConfigError(f"{where}.thresholds.min_usdc: expected a number >= 0")
    sides = thresholds.get("alert_sides")
    if sides is not None:
        sides = tuple(str(s).upper() for s in sides)
        bad_sides = [s for s in sides if s not in BET_SIDES]
        if bad_sides:
            raise ConfigError(f"{where}.thresholds.alert_sides: {bad_sides} not in {BET_SIDES}")
    enabled = data.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError(f"{where}.enabled: expected true/false")
    return WalletConfig(
        address=addr.lower(),
        label=str(data.get("label") or addr[:10]),
        cluster_id=(str(data["cluster_id"]) if data.get("cluster_id") not in (None, "") else None),
        cluster_confidence=conf,
        cluster_note=(str(data["cluster_note"]) if data.get("cluster_note") else None),
        enabled=enabled,
        min_usdc=float(min_usdc) if min_usdc is not None else None,
        alert_sides=sides,
    )


def parse_config(raw: dict[str, Any]) -> Config:
    if not isinstance(raw, dict):
        raise ConfigError("top level: expected a mapping")
    allowed = {"version", "wallets", "poll", "grouping", "alerting", "copy_candidate", "health",
               "notifications", "storage"}
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ConfigError(f"top level: unknown key(s) {unknown}")
    if raw.get("version", 1) != 1:
        raise ConfigError(f"unsupported config version {raw.get('version')!r}")
    wallets_raw = raw.get("wallets") or []
    if not isinstance(wallets_raw, list) or not wallets_raw:
        raise ConfigError("wallets: at least one wallet is required")
    wallets = tuple(_wallet(w, i) for i, w in enumerate(wallets_raw))
    seen: set[str] = set()
    for w in wallets:
        if w.address in seen:
            raise ConfigError(f"wallets: duplicate address {w.address}")
        seen.add(w.address)

    poll = _build(PollConfig, raw.get("poll"), "poll")
    bad_types = [t for t in poll.activity_types if t not in ACTIVITY_TYPES]
    if bad_types:
        raise ConfigError(f"poll.activity_types: unknown {bad_types}; allowed {ACTIVITY_TYPES}")
    if "TRADE" not in poll.activity_types:
        raise ConfigError("poll.activity_types must include TRADE")
    if not 1 <= poll.page_limit <= 1000:
        raise ConfigError("poll.page_limit must be within 1..1000 (Data API v2 cap)")
    if poll.interval_seconds < 1:
        raise ConfigError("poll.interval_seconds must be >= 1")

    alerting = _build(AlertingConfig, raw.get("alerting"), "alerting")
    bad_sides = [s for s in alerting.alert_sides if s not in BET_SIDES]
    if bad_sides:
        raise ConfigError(f"alerting.alert_sides: {bad_sides} not in {BET_SIDES}")

    cc = _build(CopyCandidateConfig, raw.get("copy_candidate"), "copy_candidate")
    if cc.min_cluster_confidence not in CONFIDENCE_LEVELS:
        raise ConfigError(f"copy_candidate.min_cluster_confidence not in {CONFIDENCE_LEVELS}")

    notif_raw = dict(raw.get("notifications") or {})
    channels_raw = notif_raw.pop("channels", None) or {}
    if not isinstance(channels_raw, dict):
        raise ConfigError("notifications.channels: expected a mapping")
    defaults = NotificationsConfig().channels
    unknown_ch = sorted(set(channels_raw) - set(defaults))
    if unknown_ch:
        raise ConfigError(f"notifications.channels: unknown channel(s) {unknown_ch}; allowed {sorted(defaults)}")
    channels: dict[str, ChannelConfig] = {}
    for name, base in defaults.items():
        merged = {**dataclasses.asdict(base), **(channels_raw.get(name) or {})}
        channels[name] = _build(ChannelConfig, merged, f"notifications.channels.{name}")
    if channels["file"].enabled and not channels["file"].path:
        raise ConfigError("notifications.channels.file.path is required when the file channel is enabled")
    if channels["file"].path and channels["file"].path.endswith(".jsonl"):
        raise ConfigError("notifications.channels.file.path: use .ndjson or .log, not .jsonl (ignored by the repo)")
    notifications = _build(NotificationsConfig, notif_raw, "notifications", overrides={"channels": channels})
    if notifications.delivery_semantics not in ("at_least_once", "at_most_once"):
        raise ConfigError("notifications.delivery_semantics must be at_least_once or at_most_once")
    if not any(c.enabled for c in channels.values()):
        raise ConfigError("notifications: enable at least one channel (console is the safe default)")

    return Config(
        wallets=wallets,
        poll=poll,
        grouping=_build(GroupingConfig, raw.get("grouping"), "grouping"),
        alerting=alerting,
        copy_candidate=cc,
        health=_build(HealthConfig, raw.get("health"), "health"),
        notifications=notifications,
        storage=_build(StorageConfig, raw.get("storage"), "storage"),
    )


def load_config(path: str | Path) -> Config:
    p = Path(path)
    if not p.exists():
        p2 = resolve_path(path)
        if not p2.exists():
            raise ConfigError(f"config file not found: {path}")
        p = p2
    with p.open() as f:
        raw = yaml.safe_load(f)
    return parse_config(raw or {})
