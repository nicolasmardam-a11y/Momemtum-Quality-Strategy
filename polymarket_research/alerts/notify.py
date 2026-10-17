"""Notification channels and per-channel rate limiting.

Credentials are read only from environment variables, are never written to the
database, files or logs, and are scrubbed from every error string (``redact``)
because ``requests`` exceptions embed the request URL, and the Telegram Bot API
puts the bot credential in the URL path.

Environment variables
---------------------
Telegram: PM_ALERT_TELEGRAM_BOT (bot credential from @BotFather), PM_ALERT_TELEGRAM_CHAT (chat id)
Email:    PM_ALERT_SMTP_HOST, PM_ALERT_SMTP_PORT (default 587), PM_ALERT_SMTP_USER,
          PM_ALERT_SMTP_PASSWORD, PM_ALERT_SMTP_FROM, PM_ALERT_SMTP_TO (comma-separated),
          PM_ALERT_SMTP_SSL=1 for implicit TLS (port 465); otherwise STARTTLS is required.
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import sys
import threading
import time
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, TextIO

import requests

from .config import Config, resolve_path

TELEGRAM_API = "https://api.telegram.org"


class NotifyError(Exception):
    def __init__(self, detail: str, *, retryable: bool = True, retry_after_s: float | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.retryable = retryable
        self.retry_after_s = retry_after_s


@dataclass
class Message:
    alert_id: int
    dedupe_key: str
    kind: str
    label: str
    text: str
    payload: dict
    possible_duplicate: bool = False

    def subject(self) -> str:
        first = self.text.splitlines()[0] if self.text else self.label
        return ("[POSSIBLE DUPLICATE] " if self.possible_duplicate else "") + first[:150]

    def body(self) -> str:
        pre = ("[POSSIBLE DUPLICATE: a previous send of this alert was interrupted and its outcome is unknown]\n"
               if self.possible_duplicate else "")
        return pre + self.text + f"\n(alert #{self.alert_id}, key {self.dedupe_key})"


class Notifier(Protocol):
    name: str

    def send(self, msg: Message) -> None: ...


def redact(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s and len(s) >= 4:
            text = text.replace(s, "[REDACTED]")
    return text


class TokenBucket:
    """In-process token bucket: ``rate_per_minute`` sustained, ``burst`` capacity."""

    def __init__(self, rate_per_minute: float, burst: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.rate = max(rate_per_minute, 1e-6) / 60.0
        self.capacity = max(1, burst)
        self.tokens = float(self.capacity)
        self.clock = clock
        self.t = clock()
        self.lock = threading.Lock()

    def try_take(self) -> float:
        """Take a token and return 0, or return the seconds until one is available."""
        with self.lock:
            now = self.clock()
            self.tokens = min(self.capacity, self.tokens + (now - self.t) * self.rate)
            self.t = now
            if self.tokens >= 1:
                self.tokens -= 1
                return 0.0
            return (1 - self.tokens) / self.rate


class ConsoleNotifier:
    name = "console"

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream

    def send(self, msg: Message) -> None:
        out = self.stream or sys.stdout
        bar = "=" * 78
        out.write(f"{bar}\n{msg.body()}\n{bar}\n")
        out.flush()


class FileNotifier:
    """Appends one JSON object per line (newline-delimited JSON, ``.ndjson``)."""

    name = "file"

    def __init__(self, path: str | Path) -> None:
        self.path = resolve_path(path)
        if self.path.suffix == ".jsonl":
            raise ValueError("use .ndjson or .log, not .jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, msg: Message) -> None:
        rec = {"alert_id": msg.alert_id, "dedupe_key": msg.dedupe_key, "kind": msg.kind, "label": msg.label,
               "possible_duplicate": msg.possible_duplicate, "written_at": time.time(), "text": msg.text,
               "payload": msg.payload}
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, default=str, sort_keys=True) + "\n")
        except OSError as e:
            raise NotifyError(f"file write failed: {e}") from None


HttpPost = Callable[..., Any]


class TelegramNotifier:
    """Telegram Bot API sendMessage over HTTPS. Plain text (no parse_mode) to avoid markup errors."""

    name = "telegram"

    def __init__(self, bot: str, chat: str, *, timeout: float = 10.0, post: HttpPost | None = None) -> None:
        self._bot = bot
        self.chat = chat
        self.timeout = timeout
        self._post = post or requests.post

    def scrub(self, text: str) -> str:
        return redact(text, [self._bot])

    def send(self, msg: Message) -> None:
        url = f"{TELEGRAM_API}/bot{self._bot}/sendMessage"
        body = {"chat_id": self.chat, "text": msg.body()[:4096], "disable_web_page_preview": True}
        try:
            r = self._post(url, json=body, timeout=self.timeout)
        except requests.RequestException as e:
            raise NotifyError(redact(f"telegram request failed: {type(e).__name__}: {e}", [self._bot])) from None
        try:
            j = r.json()
        except ValueError:
            j = {}
        if r.status_code == 200 and j.get("ok"):
            return
        desc = redact(str(j.get("description") or r.text[:200]), [self._bot])
        if r.status_code == 429:
            ra = (j.get("parameters") or {}).get("retry_after")
            raise NotifyError(f"telegram rate limited: {desc}", retry_after_s=float(ra) if ra else None)
        raise NotifyError(f"telegram HTTP {r.status_code}: {desc}", retryable=r.status_code >= 500)


SmtpFactory = Callable[..., Any]


class EmailNotifier:
    name = "email"

    def __init__(self, host: str, port: int, user: str | None, password: str | None, sender: str,
                 recipients: list[str], *, use_ssl: bool = False, timeout: float = 15.0,
                 smtp_factory: SmtpFactory | None = None) -> None:
        self.host, self.port, self.user, self._password = host, port, user, password
        self.sender, self.recipients, self.use_ssl, self.timeout = sender, recipients, use_ssl, timeout
        self._factory = smtp_factory

    def scrub(self, text: str) -> str:
        return redact(text, [self._password or ""])

    def send(self, msg: Message) -> None:
        em = EmailMessage()
        em["Subject"] = msg.subject()
        em["From"] = self.sender
        em["To"] = ", ".join(self.recipients)
        em.set_content(msg.body())
        ctx = ssl.create_default_context()
        try:
            if self._factory is not None:
                smtp = self._factory(self.host, self.port, timeout=self.timeout)
            elif self.use_ssl:
                smtp = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=ctx)
            else:
                smtp = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            with smtp:
                if not self.use_ssl:
                    smtp.starttls(context=ctx)
                if self.user:
                    smtp.login(self.user, self._password or "")
                smtp.send_message(em)
        except smtplib.SMTPAuthenticationError as e:
            raise NotifyError(redact(f"smtp auth failed: {e.smtp_code}", [self._password or ""]), retryable=False) from None
        except (smtplib.SMTPException, OSError) as e:
            raise NotifyError(redact(f"smtp failed: {type(e).__name__}: {e}", [self._password or ""])) from None


class NotifierConfigError(ValueError):
    pass


def build_notifiers(cfg: Config, env: Mapping[str, str] | None = None, *, dry_run: bool = False,
                    stream: TextIO | None = None) -> dict[str, Notifier]:
    """Instantiate enabled channels. Missing credentials for an enabled network
    channel is a startup error naming the variable (never its value)."""
    env = os.environ if env is None else env
    ch = cfg.notifications.channels
    out: dict[str, Notifier] = {}
    if ch["console"].enabled:
        out["console"] = ConsoleNotifier(stream)
    if ch["file"].enabled:
        out["file"] = FileNotifier(ch["file"].path or "alerts/out/alerts.ndjson")
    if dry_run:
        return out or {"console": ConsoleNotifier(stream)}
    if ch["telegram"].enabled:
        missing = [k for k in ("PM_ALERT_TELEGRAM_BOT", "PM_ALERT_TELEGRAM_CHAT") if not env.get(k)]
        if missing:
            raise NotifierConfigError(f"telegram channel enabled but environment variable(s) {missing} are not set")
        out["telegram"] = TelegramNotifier(env["PM_ALERT_TELEGRAM_BOT"], env["PM_ALERT_TELEGRAM_CHAT"],
                                           timeout=cfg.notifications.send_timeout_seconds)
    if ch["email"].enabled:
        need = ("PM_ALERT_SMTP_HOST", "PM_ALERT_SMTP_FROM", "PM_ALERT_SMTP_TO")
        missing = [k for k in need if not env.get(k)]
        if missing:
            raise NotifierConfigError(f"email channel enabled but environment variable(s) {missing} are not set")
        out["email"] = EmailNotifier(
            env["PM_ALERT_SMTP_HOST"], int(env.get("PM_ALERT_SMTP_PORT") or 587), env.get("PM_ALERT_SMTP_USER"),
            env.get("PM_ALERT_SMTP_PASSWORD"), env["PM_ALERT_SMTP_FROM"],
            [x.strip() for x in env["PM_ALERT_SMTP_TO"].split(",") if x.strip()],
            use_ssl=env.get("PM_ALERT_SMTP_SSL") == "1", timeout=cfg.notifications.send_timeout_seconds)
    return out
