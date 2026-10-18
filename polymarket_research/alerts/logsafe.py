"""Log output that cannot contain a notification credential.

The notifiers scrub their own error strings, but that is not enough: ``urllib3``
logs every request line at DEBUG and the Telegram Bot API puts the bot credential
in the URL path (``POST /bot<id>:<key>/sendMessage``), and a traceback of any
exception raised while calling it can carry the same URL. So the handler installed
here redacts the *formatted* record (message, arguments and traceback) against the
credential values read from the environment, in every form they can appear in.
"""
from __future__ import annotations

import logging
import time
from typing import Mapping, TextIO
from urllib.parse import quote

from .notify import redact

# Environment variables whose values must never reach a log (see notify.py).
CREDENTIAL_ENV = ("PM_ALERT_TELEGRAM_BOT", "PM_ALERT_SMTP_PASSWORD")
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_MARK = "_pm_alerts_handler"


def sensitive_values(env: Mapping[str, str]) -> list[str]:
    """Every string form of the configured credentials, longest first.

    Includes URL-quoted forms and, for the bot credential, the key part after the
    ``:`` (the numeric bot id before it is public, the key is not).
    """
    out: set[str] = set()
    for name in CREDENTIAL_ENV:
        v = env.get(name) or ""
        if len(v) < 4:
            continue
        out.update({v, quote(v), quote(v, safe="")})
        if name == "PM_ALERT_TELEGRAM_BOT" and ":" in v:
            out.add(v.split(":", 1)[1])
    return sorted((s for s in out if len(s) >= 4), key=len, reverse=True)


class RedactingFormatter(logging.Formatter):
    def __init__(self, fmt: str, values: list[str]) -> None:
        super().__init__(fmt)
        self.values = values
        self.converter = time.gmtime          # log timestamps in UTC, like every other time shown

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record), self.values)


def install(level: str, *, stream: TextIO, env: Mapping[str, str]) -> logging.Handler:
    """Install (or replace) this package's root handler and set the root level."""
    root = logging.getLogger()
    for h in [h for h in root.handlers if getattr(h, _MARK, False)]:
        root.removeHandler(h)
    handler = logging.StreamHandler(stream)
    setattr(handler, _MARK, True)
    handler.setFormatter(RedactingFormatter(LOG_FORMAT, sensitive_values(env)))
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    return handler
