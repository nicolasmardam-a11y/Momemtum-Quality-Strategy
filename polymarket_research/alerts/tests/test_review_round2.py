"""Adversarial review, round 2 (2026-10-18).

Every test here was written to fail against the code as it stood after round 1
(``test_review.py``) and passes after the fix described in README "Review". Each one
tries to make the monitor duplicate an alert, skip activity silently, block alerts,
misreport an outcome/role, or wedge a wallet.
"""
from __future__ import annotations

import copy
import json
import smtplib
import sqlite3
import threading

import pytest
import requests

from alerts import grouping, render
from alerts.dispatch import Dispatcher
from alerts.notify import EmailNotifier, TelegramNotifier

from .conftest import SECOND, Harness, base_config
from .test_dispatch import make_alert
from .test_review import T0, bet_harness, dormant, payload, poll, row


def _status(h: Harness, alert_id: int) -> tuple[str, int]:
    r = h.store.q1("SELECT status, possible_duplicate FROM deliveries WHERE alert_id = ?", (alert_id,))
    return r[0], r[1]


# --------------------------------------------------------------------------- duplicates: two processes

def test_second_instance_on_the_same_db_refuses_to_start(tmp_path, monkeypatch) -> None:
    """Overlapping cron ``--once`` runs (or a manual ``--once`` beside the loop) each called
    recover_inflight() at startup and re-queued the *other* process's in-flight send as a
    possible duplicate, so the alert was delivered twice."""
    from alerts import run
    from alerts.instance import InstanceLock

    h = Harness(tmp_path, T0, wallets=[SECOND])
    a = make_alert(h, channels=["console"])
    h.store.conn.execute("UPDATE deliveries SET status = 'sending' WHERE alert_id = ?", (a,))   # A is mid-send
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(json.dumps(base_config()))          # JSON is valid YAML

    def no_engine(*_a, **_k):
        raise AssertionError("a second instance must not start polling or sending")

    monkeypatch.setattr(run, "Engine", no_engine)
    argv = ["--config", str(cfg_file), "--db", h.db_path, "--dry-run"]
    with InstanceLock(h.db_path):                           # instance A still running
        assert run.main(argv + ["--once"]) == 4
        assert _status(h, a) == ("sending", 0)              # A's send was not re-queued
        assert run.main(argv + ["--report"]) == 0           # read-only report still works
    lock = InstanceLock(h.db_path)
    lock.acquire()                                          # free again once A has exited
    lock.release()


# --------------------------------------------------------------------------- duplicates: ambiguous sends

class _Ok:
    status_code = 200
    text = '{"ok": true}'

    def json(self) -> dict:
        return {"ok": True}


def _timeout_then_ok() -> tuple:
    texts: list[str] = []

    def post(url, json=None, timeout=None):   # noqa: A002 - mirrors requests.post
        texts.append(json["text"])
        if len(texts) == 1:
            raise requests.ReadTimeout("read timed out (request was sent)")
        return _Ok()
    return post, texts


def test_telegram_read_timeout_is_resent_marked_as_possible_duplicate(tmp_path) -> None:
    """A read timeout means Telegram may already have delivered the message; the retry went out
    unmarked, so the user could not tell a duplicate from a second bet."""
    h = Harness(tmp_path, T0, wallets=[SECOND])
    post, texts = _timeout_then_ok()
    disp = Dispatcher(h.store, {"telegram": TelegramNotifier("123:fake-bot-value", "1", post=post)}, h.cfg,
                      clock=h.clock, monotonic=h.clock)
    a = make_alert(h, channels=["telegram"])
    disp.flush()
    h.clock.advance(120)
    disp.flush()
    assert len(texts) == 2 and not texts[0].startswith("[POSSIBLE DUPLICATE")
    assert texts[1].startswith("[POSSIBLE DUPLICATE")
    assert _status(h, a) == ("sent", 1)


def test_at_most_once_never_resends_after_an_ambiguous_timeout(tmp_path) -> None:
    h = Harness(tmp_path, T0, base_config(notifications={"delivery_semantics": "at_most_once"}), wallets=[SECOND])
    post, texts = _timeout_then_ok()
    disp = Dispatcher(h.store, {"telegram": TelegramNotifier("123:fake-bot-value", "1", post=post)}, h.cfg,
                      clock=h.clock, monotonic=h.clock, on_problem=h.engine._delivery_problem)
    a = make_alert(h, channels=["telegram"])
    for _ in range(5):
        disp.flush()
        h.clock.advance(600)
    assert len(texts) == 1
    assert _status(h, a)[0] == "unknown"
    assert h.store.open_health_event("notify:telegram", "delivery_unknown") is not None


class _SmtpQuitFails:
    """The server accepted the message (send_message returned) but QUIT got a 421."""

    def __init__(self) -> None:
        self.sent: list = []

    def __call__(self, host, port, timeout=None):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        raise smtplib.SMTPResponseException(421, b"4.4.2 closing transmission channel")

    def starttls(self, context=None) -> None:
        pass

    def login(self, user, password) -> None:
        pass

    def send_message(self, em) -> None:
        self.sent.append(em)


def test_email_accepted_by_the_server_is_not_resent_when_quit_fails(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[SECOND])
    smtp = _SmtpQuitFails()
    em = EmailNotifier("smtp.example.invalid", 587, "u", "fake-pass-1234", "a@example.invalid",
                       ["b@example.invalid"], smtp_factory=smtp)
    disp = Dispatcher(h.store, {"email": em}, h.cfg, clock=h.clock, monotonic=h.clock)
    a = make_alert(h, channels=["email"])
    for _ in range(3):
        disp.flush()
        h.clock.advance(600)
    assert len(smtp.sent) == 1
    assert _status(h, a)[0] == "sent"


# --------------------------------------------------------------------------- one bad bet must not block the rest

def test_one_unrenderable_bet_does_not_block_other_alerts(tmp_path, monkeypatch) -> None:
    """An exception while building one alert escaped evaluate_bets(): the cycle aborted before every
    older bet, the stale check and the digest, on every cycle, and was only logged."""
    h = Harness(tmp_path, T0, wallets=[SECOND])
    dormant(h)
    poll(h)
    h.api.add_activity(SECOND, [row(T0 + 100, tx="0x" + "a1" * 32, cid="0x" + "c1" * 32, token="111"),
                                row(T0 + 110, tx="0x" + "a2" * 32, cid="0x" + "c2" * 32, token="222")])
    h.clock.t = T0 + 130
    real = render.bet_alert

    def fragile(p: dict) -> str:
        if p["bet"]["condition_id"] == "0x" + "c2" * 32:          # the newest bet is evaluated first
            raise TypeError("unsupported format string passed to NoneType.__format__")
        return real(p)

    monkeypatch.setattr(render, "bet_alert", fragile)
    poll(h)
    sent = [a for a in h.alerts("BET") if a["status"] != "suppressed"]
    assert len(sent) == 2, [a["text"][:60] for a in sent]
    fallback = [a for a in sent if "ALERT RENDERING FAILED" in a["text"]]
    assert len(fallback) == 1 and "BUY" in fallback[0]["text"] and "Synthetic market?" in fallback[0]["text"]
    assert h.store.open_health_event("engine", "evaluation") is not None


def test_repeated_cycle_crash_is_reported_not_only_logged(tmp_path, monkeypatch) -> None:
    h = Harness(tmp_path, T0, wallets=[SECOND])
    dormant(h)
    poll(h)

    def broken(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(grouping, "assign_pending", broken)
    h.engine.run_loop(threading.Event(), max_cycles=2, sleep_jitter=lambda: -1e6)
    h.engine.dispatcher.flush()
    ev = h.store.open_health_event("engine", "cycle_failure")
    assert ev is not None and ev["occurrences"] == 2
    assert any("cycle_failure" in a["text"] for a in h.alerts("DATA_PROBLEM"))
    monkeypatch.undo()
    poll(h)
    assert h.store.open_health_event("engine", "cycle_failure") is None
    assert len(h.alerts("DATA_RECOVERED")) >= 1


# --------------------------------------------------------------------------- outcome side (YES vs NO)

def test_outcome_label_follows_gammas_token_mapping_when_the_data_api_mislabels(tmp_path) -> None:
    """The traded token is Gamma's "No" token; the row says "Yes". The alert used the row's label."""
    def prep(h, bet):
        bet["outcome"] = "Yes"
    h, _ = bet_harness(tmp_path, prep)
    p = payload(h)
    mk = p["enrichment"]["market"]
    assert mk["outcome"] == "No" and mk["outcome_data_api"] == "Yes"
    assert any("outcome label" in e for e in p["enrichment"]["enrichment_errors"])
    text = h.alerts("BET")[0]["text"]
    assert "Outcome: No | Side: BUY" in text and "Outcome: Yes" not in text


def test_unlabelled_trade_row_gets_its_outcome_from_gamma(tmp_path) -> None:
    """``outcome_index: 999`` means the Data API could not label the row; the alert said 'Outcome: None'."""
    def prep(h, bet):
        bet["outcome"], bet["outcome_index"] = "", 999
    h, _ = bet_harness(tmp_path, prep)
    assert "Outcome: No | Side: BUY" in h.alerts("BET")[0]["text"]       # not "Outcome: None"
    assert not payload(h)["enrichment"].get("enrichment_errors")


def test_token_that_is_not_one_of_the_markets_tokens_is_flagged(tmp_path) -> None:
    def prep(h, bet):
        g = copy.deepcopy(h.api.gamma[bet["condition_id"]])
        g["clobTokenIds"] = json.dumps(["1", "2"])
        h.api.gamma[bet["condition_id"]] = g
    h, _ = bet_harness(tmp_path, prep)
    errs = payload(h)["enrichment"]["enrichment_errors"]
    assert any("not one of this market's clobTokenIds" in e for e in errs)


# --------------------------------------------------------------------------- maker vs taker

def test_fee_embedded_fill_absent_from_the_taker_feed_is_not_labelled_taker(tmp_path) -> None:
    """Builder fees can be charged to makers too (notes/platform/data_infrastructure.md pitfall 16), so
    "fee embedded => taker" must be confirmed by the taker-only feed. It was only checked when the
    bet also had a fee-free fill."""
    def prep(h, bet):
        h.api.taker_rows[SECOND] = [r for r in h.api.taker_rows[SECOND]
                                    if r["transaction_hash"].lower() != bet["transaction_hash"].lower()]
    h, bet = bet_harness(tmp_path, prep)
    f = payload(h)["enrichment"]["fills"]
    assert f["taker_shares"] == 0 and f["unknown_role_shares"] == pytest.approx(bet["size"])


def test_probe_fee_embedded_fill_in_the_taker_feed_stays_taker(tmp_path) -> None:
    h, bet = bet_harness(tmp_path)
    f = payload(h)["enrichment"]["fills"]
    assert f["taker_shares"] == pytest.approx(bet["size"]) and f["unknown_role_shares"] == 0


# --------------------------------------------------------------------------- activity during an outage

def test_bets_executed_during_an_outage_are_summarised_not_silently_suppressed(tmp_path) -> None:
    """After a gap, qualifying bets older than max_alert_age_minutes were stored as 'suppressed'
    with no channel at all: the user heard DATA RECOVERED and nothing about the bets."""
    h = Harness(tmp_path, T0, wallets=[SECOND])
    dormant(h)
    poll(h)
    h.api.add_activity(SECOND, [row(T0 + 3600, size=1000.0, price=0.4)])   # executed while the machine was off
    h.clock.t = T0 + 8 * 3600
    poll(h)
    notes = [a for a in h.alerts("NOTICE") if a["label"] == "BACKFILL SUMMARY"]
    assert len(notes) == 1 and notes[0]["status"] == "sent"
    assert "Synthetic market?" in notes[0]["text"] and "$400.00" in notes[0]["text"]
    assert "BUY" in notes[0]["text"] and "NOT alerted individually" in notes[0]["text"]
    poll(h)
    assert len([a for a in h.alerts("NOTICE") if a["label"] == "BACKFILL SUMMARY"]) == 1


# --------------------------------------------------------------------------- one malformed row must not wedge a wallet

def test_one_unparseable_row_does_not_wedge_the_wallet(tmp_path) -> None:
    """A single row failing validation (e.g. a TRADE with no outcome token, as a new product such as
    Combos might produce) failed every poll of that wallet until the code changed, so every later
    trade of the wallet was missed. It is now quarantined and reported with its facts."""
    h = Harness(tmp_path, T0, wallets=[SECOND])
    dormant(h)
    poll(h)
    bad = row(T0 + 110, tx="0x" + "bb" * 32)
    bad["token_id"] = ""
    h.api.add_activity(SECOND, [row(T0 + 100, tx="0x" + "a1" * 32), bad,
                                row(T0 + 120, tx="0x" + "a3" * 32, cid="0x" + "c3" * 32, token="333")])
    h.clock.t = T0 + 150
    rep = poll(h)
    assert rep.polls[0].ok and rep.polls[0].new_fills == 2
    assert h.store.poll_state(SECOND)["consecutive_failures"] == 0
    probs = [a for a in h.alerts("DATA_PROBLEM") if "could not be parsed" in a["text"]]
    assert len(probs) == 1 and probs[0]["status"] == "sent"
    assert "0xbbbbbb" in probs[0]["text"] and "NOT processed" in probs[0]["text"]
    assert h.store.count("rejected_rows") == 1
    h.clock.t = T0 + 200
    poll(h)                                                       # the overlap re-reads the bad row
    assert len([a for a in h.alerts("DATA_PROBLEM") if "could not be parsed" in a["text"]]) == 1


def test_probe_every_row_invalid_is_still_a_hard_schema_failure(tmp_path) -> None:
    """Quarantine must not turn a real schema change (all rows bad) into 'ok, no new trades'."""
    h = Harness(tmp_path, T0, wallets=[SECOND])
    dormant(h)
    poll(h)
    wm = h.store.poll_state(SECOND)["watermark_ts"]
    for r in h.api.activity[SECOND]:
        r["token_id"] = ""
    h.clock.t = T0 + 60
    rep = poll(h)
    assert not rep.polls[0].ok and rep.polls[0].error_class == "schema"
    assert h.store.poll_state(SECOND)["watermark_ts"] == wm


def test_dormant_wallet_whose_newest_row_is_malformed_still_bootstraps(tmp_path) -> None:
    """The bootstrap probe (latest_activity) still raised on an invalid row, so a dormant wallet whose
    newest-ever row is malformed failed its bootstrap poll forever."""
    h = Harness(tmp_path, T0, wallets=[SECOND])
    old = row(T0 - 40 * 86400, tx="0x" + "0e" * 32)
    old["token_id"] = ""
    h.api.add_activity(SECOND, [old])
    rep = poll(h)
    assert rep.polls[0].ok
    assert h.store.count("rejected_rows") == 1
    assert h.store.open_health_event(SECOND, "no_history") is None


@pytest.mark.parametrize("field", ["overlap_seconds", "ingest_safety_seconds"])
def test_probe_negative_overlap_or_margin_is_a_config_error(field) -> None:
    """Probe (already correct: config._build rejects every negative number). ``start = watermark -
    overlap``: a negative overlap would start each poll after the watermark and skip rows."""
    from alerts.config import ConfigError, parse_config
    with pytest.raises(ConfigError, match=field):
        parse_config(base_config(poll={field: -60}))
