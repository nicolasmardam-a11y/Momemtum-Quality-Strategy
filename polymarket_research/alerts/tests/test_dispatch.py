"""Idempotent alert sending, crash semantics, retries/backoff, rate limits, channels."""
from __future__ import annotations

import io
import json

import pytest
import requests

from alerts.config import parse_config
from alerts.dispatch import Dispatcher
from alerts.notify import (ConsoleNotifier, EmailNotifier, Message, NotifierConfigError, NotifyError,
                           TelegramNotifier, TokenBucket, build_notifiers, redact)

from .conftest import MINTBLADE, Harness, base_config

T0 = 1_792_250_000.0


def make_alert(h: Harness, key: str = "test:1", channels=("console", "file")) -> int:
    return h.store.create_alert(dedupe_key=key, kind="BET", label="NEW BET DETECTED", text=f"alert {key}",
                                payload={"k": key}, now=h.clock(), channels=list(channels))


def test_alert_dedupe_and_single_delivery(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[MINTBLADE])
    a = make_alert(h)
    assert a is not None and make_alert(h) is None            # same dedupe key -> no second alert
    assert h.engine.dispatcher.flush()["sent"] == 2
    assert h.engine.dispatcher.flush()["sent"] == 0           # nothing left to send
    assert h.out.getvalue().count("alert test:1") == 1
    assert len(h.file_path.read_text().splitlines()) == 1
    rec = json.loads(h.file_path.read_text())
    assert rec["dedupe_key"] == "test:1" and rec["possible_duplicate"] is False
    assert h.store.q1("SELECT status FROM alerts WHERE alert_id = ?", (a,))[0] == "sent"


def test_crash_mid_send_at_least_once_resends_with_marker(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[MINTBLADE])
    a = make_alert(h, channels=["console"])
    h.store.conn.execute("UPDATE deliveries SET status = 'sending', attempts = 1 WHERE alert_id = ?", (a,))
    h.restart()                                               # process died after marking 'sending'
    assert h.engine.dispatcher.recover_inflight() == 1
    h.engine.dispatcher.flush()
    out = h.out.getvalue()
    assert "[POSSIBLE DUPLICATE" in out and out.count("alert test:1") == 1
    d = h.store.q1("SELECT * FROM deliveries WHERE alert_id = ?", (a,))
    assert d["status"] == "sent" and d["possible_duplicate"] == 1 and d["attempts"] == 2


def test_crash_mid_send_at_most_once_never_resends_but_reports(tmp_path) -> None:
    d = base_config(notifications={"delivery_semantics": "at_most_once"})
    h = Harness(tmp_path, T0, d, wallets=[MINTBLADE])
    a = make_alert(h, channels=["console"])
    h.store.conn.execute("UPDATE deliveries SET status = 'sending' WHERE alert_id = ?", (a,))
    h.restart()
    h.engine.dispatcher.recover_inflight()
    h.engine.dispatcher.flush()
    assert "alert test:1" not in h.out.getvalue().split("[DATA PROBLEM]")[0]
    assert h.store.q1("SELECT status FROM deliveries WHERE alert_id = ?", (a,))[0] == "unknown"
    ev = h.store.q("SELECT * FROM health_events WHERE kind = 'delivery_unknown'")
    assert len(ev) == 1 and "may not have been delivered" in ev[0]["detail"]


class Flaky:
    name = "telegram"

    def __init__(self, failures: int, retryable: bool = True) -> None:
        self.failures, self.retryable, self.sent = failures, retryable, []

    def send(self, msg: Message) -> None:
        if self.failures > 0:
            self.failures -= 1
            raise NotifyError("synthetic outage", retryable=self.retryable)
        self.sent.append(msg)


def test_retry_with_backoff_then_success(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[MINTBLADE])
    flaky = Flaky(2)
    disp = Dispatcher(h.store, {"telegram": flaky}, h.cfg, clock=h.clock)
    a = make_alert(h, channels=["telegram"])
    assert disp.flush()["retry"] == 1
    d = h.store.q1("SELECT * FROM deliveries WHERE alert_id = ?", (a,))
    assert d["status"] == "pending" and d["next_attempt_at"] == pytest.approx(T0 + 5)   # backoff_base_seconds
    assert disp.flush()["sent"] == 0                          # not due yet: nothing blocks, nothing sent
    h.clock.advance(5)
    disp.flush()
    d = h.store.q1("SELECT * FROM deliveries WHERE alert_id = ?", (a,))
    assert d["next_attempt_at"] == pytest.approx(T0 + 5 + 10)                         # exponential
    h.clock.advance(10)
    assert disp.flush()["sent"] == 1 and len(flaky.sent) == 1


def test_permanent_failure_is_reported_on_other_channels(tmp_path) -> None:
    d = base_config(notifications={"max_attempts": 2})
    h = Harness(tmp_path, T0, d, wallets=[MINTBLADE])
    flaky = Flaky(10)
    notifiers = {"telegram": flaky, "console": ConsoleNotifier(h.out)}
    disp = Dispatcher(h.store, notifiers, h.cfg, clock=h.clock, on_problem=h.engine._delivery_problem)
    h.engine.health.channels = list(notifiers)
    a = make_alert(h, channels=["telegram", "console"])
    disp.flush()
    h.clock.advance(5)
    disp.flush()
    assert h.store.q1("SELECT status FROM deliveries WHERE alert_id = ? AND channel = 'telegram'", (a,))[0] == "failed"
    assert h.store.q1("SELECT status FROM alerts WHERE alert_id = ?", (a,))[0] == "partial"
    prob = h.alerts("DATA_PROBLEM")
    assert len(prob) == 1
    chans = {r[0] for r in h.store.q("SELECT channel FROM deliveries WHERE alert_id = ?", (prob[0]["alert_id"],))}
    assert chans == {"console"}                               # not sent to the channel that is failing
    non_retry = Flaky(1, retryable=False)
    disp2 = Dispatcher(h.store, {"telegram": non_retry}, h.cfg, clock=h.clock)
    b = make_alert(h, key="test:2", channels=["telegram"])
    assert disp2.flush()["failed"] == 1 and h.store.q1("SELECT attempts FROM deliveries WHERE alert_id = ?", (b,))[0] == 1


def test_rate_limit_defers_without_blocking(tmp_path) -> None:
    d = base_config(notifications={"channels": {"console": {"enabled": True, "rate_per_minute": 6, "burst": 2},
                                                "file": {"enabled": False}}})
    h = Harness(tmp_path, T0, d, wallets=[MINTBLADE])
    mono = [0.0]
    disp = Dispatcher(h.store, {"console": ConsoleNotifier(h.out)}, h.cfg, clock=h.clock, monotonic=lambda: mono[0])
    for i in range(5):
        make_alert(h, key=f"r:{i}", channels=["console"])
    st = disp.flush()
    assert st["sent"] == 2 and st["rate_limited"] == 3
    pend = h.store.q("SELECT next_attempt_at FROM deliveries WHERE status = 'pending'")
    assert len(pend) == 3 and all(p[0] > T0 for p in pend)
    mono[0] = 10.0
    h.clock.advance(10)
    assert disp.flush()["sent"] == 1                          # 6/min -> one token per 10 s


def test_token_bucket() -> None:
    t = [0.0]
    b = TokenBucket(60, 1, clock=lambda: t[0])
    assert b.try_take() == 0 and b.try_take() == pytest.approx(1.0)
    t[0] = 1.0
    assert b.try_take() == 0


class FakeResp:
    def __init__(self, status: int, body: dict) -> None:
        self.status_code, self._body, self.text = status, body, json.dumps(body)

    def json(self) -> dict:
        return self._body


def test_telegram_notifier_and_redaction() -> None:
    bot = "123456:ABCdefSECRETvalue"
    calls = []

    def post(url, json=None, timeout=None):
        calls.append((url, json, timeout))
        return FakeResp(200, {"ok": True, "result": {}})

    t = TelegramNotifier(bot, "42", post=post)
    t.send(Message(1, "k", "BET", "NEW BET DETECTED", "hello", {}))
    url, body, _ = calls[0]
    assert url == f"https://api.telegram.org/bot{bot}/sendMessage"
    assert body["chat_id"] == "42" and "hello" in body["text"] and body["disable_web_page_preview"] is True

    def post_429(url, json=None, timeout=None):
        return FakeResp(429, {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 7}})

    with pytest.raises(NotifyError) as e:
        TelegramNotifier(bot, "42", post=post_429).send(Message(1, "k", "BET", "L", "x", {}))
    assert e.value.retry_after_s == 7 and e.value.retryable

    def post_boom(url, json=None, timeout=None):
        raise requests.ConnectionError(f"HTTPSConnectionPool(host='api.telegram.org'): Max retries with url: {url}")

    with pytest.raises(NotifyError) as e:
        TelegramNotifier(bot, "42", post=post_boom).send(Message(1, "k", "BET", "L", "x", {}))
    assert bot not in e.value.detail and "[REDACTED]" in e.value.detail

    def post_401(url, json=None, timeout=None):
        return FakeResp(401, {"ok": False, "description": f"Unauthorized for bot{bot}"})

    with pytest.raises(NotifyError) as e:
        TelegramNotifier(bot, "42", post=post_401).send(Message(1, "k", "BET", "L", "x", {}))
    assert not e.value.retryable and bot not in e.value.detail


def test_credential_never_reaches_the_database(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[MINTBLADE])
    bot = "999:TOPsecretBOTvalue"

    def post_boom(url, json=None, timeout=None):
        raise requests.ConnectionError(f"failed url: {url}")

    disp = Dispatcher(h.store, {"telegram": TelegramNotifier(bot, "1", post=post_boom)}, h.cfg, clock=h.clock)
    make_alert(h, channels=["telegram"])
    disp.flush()
    dump = "\n".join(h.store.conn.iterdump())
    assert bot not in dump and "[REDACTED]" in dump


def test_email_notifier_uses_starttls_and_login() -> None:
    log = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            log.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            log.append(("quit",))

        def starttls(self, context=None):
            log.append(("starttls",))

        def login(self, user, pw):
            log.append(("login", user))

        def send_message(self, em):
            log.append(("send", em["Subject"], em["To"]))

    e = EmailNotifier("smtp.example.org", 587, "me", "pw", "a@example.org", ["b@example.org"], smtp_factory=FakeSMTP)
    e.send(Message(3, "k", "BET", "NEW BET DETECTED", "[NEW BET DETECTED] new position | x", {}))
    assert [x[0] for x in log] == ["connect", "starttls", "login", "send", "quit"]
    assert log[3][1].startswith("[NEW BET DETECTED]") and log[3][2] == "b@example.org"


def test_build_notifiers_reads_env_only_and_fails_loudly(tmp_path) -> None:
    d = base_config(notifications={"channels": {"telegram": {"enabled": True}, "file": {"enabled": True,
                                                "path": str(tmp_path / "x.ndjson")}}})
    cfg = parse_config(d)
    with pytest.raises(NotifierConfigError) as e:
        build_notifiers(cfg, env={})
    assert "PM_ALERT_TELEGRAM_BOT" in str(e.value)
    secret_env = {"PM_ALERT_TELEGRAM_BOT": "777:zzzSECRETzzz", "PM_ALERT_TELEGRAM_CHAT": "5"}
    n = build_notifiers(cfg, env=secret_env, stream=io.StringIO())
    assert set(n) == {"console", "file", "telegram"}
    assert set(build_notifiers(cfg, env=secret_env, dry_run=True)) == {"console", "file"}
    assert "zzzSECRETzzz" not in json.dumps(cfg.__repr__())


def test_redact() -> None:
    assert redact("x abcdef y", ["abcdef"]) == "x [REDACTED] y"
    assert redact("x ab y", ["ab"]) == "x ab y"               # too short to redact safely


def test_unexpected_notifier_crash_is_recorded_and_scrubbed(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[MINTBLADE])
    bot = "555:CRASHsecretVALUE"

    def post_bug(url, json=None, timeout=None):
        raise KeyError(f"bug while posting to {url}")          # not a requests exception

    disp = Dispatcher(h.store, {"telegram": TelegramNotifier(bot, "1", post=post_bug)}, h.cfg, clock=h.clock)
    a = make_alert(h, channels=["telegram"])
    assert disp.flush()["retry"] == 1
    d = h.store.q1("SELECT * FROM deliveries WHERE alert_id = ?", (a,))
    assert "notifier crashed: KeyError" in d["last_error"] and bot not in d["last_error"]
