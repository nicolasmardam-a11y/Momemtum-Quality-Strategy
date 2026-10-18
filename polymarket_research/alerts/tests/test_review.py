"""Adversarial review (2026-10-17): each test tries to make the monitor miss a trade, duplicate
an alert, skip activity silently, call a data failure "no new trades", leak a credential
or misreport a price. Tests marked "probe" document behaviour that was already correct."""
from __future__ import annotations

import copy
import http.server
import io
import json
import logging
import sqlite3
import threading

import pytest
import requests

from alerts import notify
from alerts.dispatch import Dispatcher
from alerts.notify import ConsoleNotifier, Message, NotifyError, TelegramNotifier

from .conftest import SECOND, Harness, base_config, load_fixture, synth_row
from .test_dispatch import Flaky, make_alert

T0 = 1_792_250_000          # 2026-10-17T15:33:20Z
TX = "0x" + "ab" * 32


def row(ts: int, *, wallet: str = SECOND, **kw) -> dict:
    return synth_row(ts, wallet=wallet, **kw)


def poll(h: Harness):
    rep = h.engine.run_cycle()
    h.engine.dispatcher.flush()
    return rep


def dormant(h: Harness, wallet: str = SECOND) -> None:
    """Give the wallet one old row so that it is a real, dormant account (not an unknown address)."""
    h.api.add_activity(wallet, [row(T0 - 40 * 86400, tx="0x" + "0d" * 32, wallet=wallet)])


# --------------------------------------------------------------------------- clock skew

@pytest.mark.parametrize("status_check", [True, False])
def test_local_clock_days_behind_does_not_hide_new_trades(tmp_path, status_check) -> None:
    """A Raspberry Pi without an RTC can boot days behind. ``end`` was derived from the local
    clock, so the window ended before the server's "now" while the watermark (server Date)
    moved past the unseen rows: a silent miss."""
    h = Harness(tmp_path, T0, base_config(poll={"status_check": status_check}), wallets=[SECOND],
                local_offset=-2 * 86400)
    dormant(h)
    poll(h)                                                     # bootstrap
    h.api.add_activity(SECOND, [row(T0 + 100)])
    stored = 0
    for _ in range(3):
        h.clock.advance(30)
        stored += poll(h).polls[0].new_fills
    assert stored == 1 and h.store.count("fills", "ts = ?", (T0 + 100,)) == 1
    assert h.store.open_health_event("local-clock", "clock_skew") is not None


def test_local_clock_hours_ahead_does_not_suppress_fresh_bets_as_too_old(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[SECOND], local_offset=7 * 3600)
    dormant(h)
    poll(h)
    h.api.add_activity(SECOND, [row(T0 + 100)])
    h.clock.t = T0 + 130
    poll(h)
    fresh = {r[0] for r in h.store.q("SELECT bet_id FROM bets WHERE first_ts > ?", (T0,))}
    bets = [a for a in h.alerts("BET") if a["bet_id"] in fresh]
    assert len(bets) == 1 and bets[0]["status"] != "suppressed", bets[0]["suppressed_reason"]
    p = json.loads(bets[0]["payload_json"])
    assert p["detection_lag_s"] < 120                          # measured on the server's clock
    ev = h.store.open_health_event("local-clock", "clock_skew")
    assert ev is not None and "ahead" in ev["detail"]


# --------------------------------------------------------------------------- wrong market / wrong book

def bet_harness(tmp_path, prep=None, cfg_dict=None) -> tuple[Harness, dict]:
    rows = load_fixture("activity_second.json")
    bet = [r for r in rows if r["type"] == "TRADE" and r["side"] == "BUY"][-1]
    h = Harness(tmp_path, bet["timestamp"] - 120, cfg_dict, wallets=[SECOND])
    h.api.gamma[bet["condition_id"]] = load_fixture("gamma_market_open.json")[0]
    h.api.clob_markets[bet["condition_id"]] = load_fixture("clob_market_open.json")
    h.api.books[bet["token_id"]] = load_fixture("book_open.json")
    h.api.taker_rows[SECOND] = load_fixture("trades_taker_second.json")["data"]
    if prep:
        prep(h, bet)
    h.engine.run_cycle()
    h.api.add_activity(SECOND, [bet])
    h.clock.t = bet["timestamp"] + 25
    h.engine.run_cycle()
    return h, bet


def payload(h: Harness) -> dict:
    alerts = h.alerts("BET")
    assert len(alerts) == 1
    return json.loads(alerts[0]["payload_json"])


def test_gamma_answer_for_another_market_is_rejected(tmp_path) -> None:
    """If Gamma ignores ``condition_ids`` it returns some other market; the alert must not show
    that market's question, fee schedule, event or in-play state."""
    def prep(h, bet):
        other = copy.deepcopy(load_fixture("gamma_market_open.json")[0])
        other.update(conditionId="0x" + "ee" * 32, question="Some unrelated market?",
                     feeSchedule={"rate": 0.07, "exponent": 1})
        h.api.gamma_override = [other]
    h, bet = bet_harness(tmp_path, prep)
    en = payload(h)["enrichment"]
    assert en["market"]["question"] != "Some unrelated market?" and en["market"]["question"] == bet["title"]
    assert en["market"]["gamma_found"] is False
    assert en["follower_fee"]["fee_rate"] is None
    assert any("conditionId" in e for e in en["enrichment_errors"])
    assert h.store.open_health_event("gamma", "enrichment") is not None or \
        h.store.count("health_events", "scope = 'gamma'") >= 1


def test_book_for_another_token_is_rejected(tmp_path) -> None:
    def prep(h, bet):
        b = copy.deepcopy(load_fixture("book_open.json"))
        b["asset_id"] = "999"                                   # the complementary / some other token
        h.api.books[bet["token_id"]] = b
    h, bet = bet_harness(tmp_path, prep)
    en = payload(h)["enrichment"]
    assert en["book"]["available"] is False and "asset_id" in en["book"]["reason"]
    assert en["deterioration"]["deterioration_cents"] is None


def test_unexpected_gamma_payload_does_not_poison_the_cycle(tmp_path) -> None:
    """A malformed field (here a non-numeric fee rate) raised ValueError out of enrich(); the bet
    kept needs_eval=1, so every cycle crashed on it and later bets, stale checks and the
    digest never ran."""
    def prep(h, bet):
        g = h.api.gamma[bet["condition_id"]]
        g["feeSchedule"] = {"rate": "four percent", "exponent": 1}
        g["events"] = ["not-an-object"]
    h, bet = bet_harness(tmp_path, prep)
    p = payload(h)
    assert p["enrichment"]["fills"]["shares"] == pytest.approx(bet["size"])
    assert any("unexpected" in e for e in p["enrichment"]["enrichment_errors"])
    assert h.store.count("bets", "needs_eval = 1") == 0
    assert h.store.count("health_events", "kind = 'enrichment'") >= 1


# --------------------------------------------------------------------------- maker / taker

def maker_taker_harness(tmp_path, *, index_caught_up: bool) -> dict:
    """Fee-free market: neither fill embeds a fee, so roles come from the /v2/trades cross-check.
    f1 is in truth the taker fill, f2 a maker fill."""
    f1 = row(T0 + 100, tx="0x" + "01" * 32, size=200.0, price=0.40)
    f2 = row(T0 + 105, tx="0x" + "02" * 32, size=50.0, price=0.41)
    h = Harness(tmp_path, T0, wallets=[SECOND])
    dormant(h)
    poll(h)
    h.api.add_activity(SECOND, [f1, f2])
    if index_caught_up:
        h.api.taker_rows[SECOND] = [f1]
    else:                                                       # /v2/trades has not ingested them yet
        h.api.all_trade_rows = {SECOND: []}
        h.api.taker_rows[SECOND] = []
    h.clock.t = T0 + 110
    poll(h)
    bet = [a for a in h.alerts("BET") if a["status"] != "suppressed"]
    assert len(bet) == 1
    return json.loads(bet[0]["payload_json"])["enrichment"]


def test_maker_label_is_not_inferred_from_a_lagging_trades_index(tmp_path) -> None:
    en = maker_taker_harness(tmp_path, index_caught_up=False)
    assert en["fills"]["maker_shares"] == 0 and en["fills"]["taker_shares"] == 0
    assert en["fills"]["unknown_role_shares"] == pytest.approx(250.0)
    assert "incomplete" in en["maker_taker_basis"]


def test_probe_maker_taker_cross_check_when_index_is_complete(tmp_path) -> None:
    en = maker_taker_harness(tmp_path, index_caught_up=True)
    assert en["fills"]["taker_shares"] == pytest.approx(200.0) and en["fills"]["maker_shares"] == pytest.approx(50.0)


# --------------------------------------------------------------------------- credentials in logs

class _OkHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:   # noqa: N802
        self.rfile.read(int(self.headers.get("content-length", 0)))
        body = b'{"ok": true}'
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


def test_debug_logging_never_prints_the_telegram_bot_credential(monkeypatch) -> None:
    """urllib3 logs every request line at DEBUG, and the Bot API puts the credential in the URL
    path, so ``--log-level DEBUG`` wrote it to stderr (and to any log file or journal)."""
    from alerts.run import configure_logging

    bot = "7654321:AAF-review-fake-bot-value_0123456789"
    srv = http.server.HTTPServer(("127.0.0.1", 0), _OkHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(notify, "TELEGRAM_API", f"http://127.0.0.1:{srv.server_port}")
    buf = io.StringIO()
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    try:
        configure_logging("DEBUG", stream=buf, env={"PM_ALERT_TELEGRAM_BOT": bot, "PM_ALERT_TELEGRAM_CHAT": "1"})
        s = requests.Session()
        s.trust_env = False                                     # local server: no proxy
        TelegramNotifier(bot, "1", post=s.post).send(Message(1, "k", "BET", "L", "hello", {}))
        try:
            raise RuntimeError(f"boom while calling {notify.TELEGRAM_API}/bot{bot}/sendMessage")
        except RuntimeError:
            logging.getLogger("alerts.test").exception("traceback with the URL")
    finally:
        srv.shutdown()
        root.handlers[:], _ = saved[0], root.setLevel(saved[1])
    out = buf.getvalue()
    assert "sendMessage" in out                                 # the request line was logged...
    assert bot not in out and bot.split(":")[1] not in out      # ...but never the credential
    assert "[REDACTED]" in out


# --------------------------------------------------------------------------- delivery

class _LockedAfterSend:
    """Connection proxy whose first 'sent' UPDATE fails as if another writer held the lock."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c, self.armed = conn, True

    def execute(self, sql: str, params=()):
        if self.armed and "status = 'sent'" in sql:
            self.armed = False
            raise sqlite3.OperationalError("database is locked")
        return self._c.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._c, name)


def test_delivery_stuck_in_sending_is_recovered_without_a_restart(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[SECOND])
    out = io.StringIO()
    disp = Dispatcher(h.store, {"console": ConsoleNotifier(out)}, h.cfg, clock=h.clock)
    a = make_alert(h, channels=["console"])
    real = h.store.conn
    h.store.conn = _LockedAfterSend(real)
    with pytest.raises(sqlite3.OperationalError):
        disp.flush()
    h.store.conn = real
    assert h.store.q1("SELECT status FROM deliveries WHERE alert_id = ?", (a,))[0] == "sending"
    h.clock.advance(5)
    disp.flush()                                                # within the lease: left alone
    assert out.getvalue().count(f"alert test:1") == 1
    h.clock.advance(600)
    disp.flush()                                                # same process, lease expired
    assert h.store.q1("SELECT status FROM deliveries WHERE alert_id = ?", (a,))[0] == "sent"
    assert out.getvalue().count("[POSSIBLE DUPLICATE") == 1


class _DownUntil:
    name = "telegram"

    def __init__(self, clock, until: float) -> None:
        self.clock, self.until, self.sent = clock, until, []

    def send(self, msg: Message) -> None:
        if self.clock() < self.until:
            raise NotifyError("telegram request failed: ConnectionError: network unreachable")
        self.sent.append(msg)


def test_channel_outage_longer_than_the_attempt_budget_still_delivers(tmp_path) -> None:
    """Default max_attempts=8 with 5..600 s backoff gave up after ~14 min: a 30-minute home
    internet outage lost every queued alert for good."""
    h = Harness(tmp_path, T0, wallets=[SECOND])
    tg = _DownUntil(h.clock, T0 + 1800)
    disp = Dispatcher(h.store, {"telegram": tg}, h.cfg, clock=h.clock)
    a = make_alert(h, channels=["telegram"])
    for _ in range(60):
        disp.flush()
        h.clock.advance(60)
    assert len(tg.sent) == 1 and h.store.q1("SELECT status FROM alerts WHERE alert_id = ?", (a,))[0] == "sent"


def test_delivery_failure_notice_is_not_dropped_when_it_is_the_only_channel(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[SECOND])
    tg = Flaky(1, retryable=False)
    h.engine.health.channels = ["telegram"]
    disp = Dispatcher(h.store, {"telegram": tg}, h.cfg, clock=h.clock, on_problem=h.engine._delivery_problem)
    make_alert(h, channels=["telegram"])
    disp.flush()
    prob = h.alerts("DATA_PROBLEM")
    assert len(prob) == 1 and prob[0]["status"] != "suppressed"
    chans = {r[0] for r in h.store.q("SELECT channel FROM deliveries WHERE alert_id = ?", (prob[0]["alert_id"],))}
    assert chans == {"telegram"}


# --------------------------------------------------------------------------- data failure vs "no new trades"

def test_empty_200_responses_are_a_data_problem_not_no_new_trades(tmp_path) -> None:
    """A degraded backend that answers 200 with ``data: []`` looked exactly like a quiet wallet;
    the watermark kept advancing, and trades made during the episode were never read."""
    h = Harness(tmp_path, T0, wallets=[SECOND])
    dormant(h)
    poll(h)
    h.api.add_activity(SECOND, [row(T0 + 100, tx="0x" + "11" * 32)])
    h.clock.t = T0 + 130
    assert poll(h).polls[0].new_fills == 1
    h.api.fail("/v2/activity", "empty", times=10_000)
    h.api.add_activity(SECOND, [row(T0 + 400, tx="0x" + "22" * 32)])
    outcomes = []
    for _ in range(50):                                         # 25 minutes of empty answers
        h.clock.advance(30)
        outcomes.append(poll(h).polls[0])
    assert not any(p.ok for p in outcomes[2:])
    assert h.store.count("alerts", "kind = 'DATA_PROBLEM'") >= 1
    h.api.faults.clear()
    h.clock.advance(30)
    rep = poll(h)
    assert rep.polls[0].ok and h.store.count("fills", "ts = ?", (T0 + 400,)) == 1


def test_address_with_no_activity_ever_is_flagged(tmp_path) -> None:
    """A signer/EOA or a typo'd but well-formed address returns 200 [] forever."""
    h = Harness(tmp_path, T0, wallets=[SECOND])
    rep = poll(h)
    assert rep.polls[0].ok
    ev = h.store.open_health_event(SECOND, "no_history")
    assert ev is not None and "proxy" in ev["detail"]
    assert h.store.count("alerts", "kind = 'DATA_PROBLEM'") == 1
    h.clock.advance(30)
    poll(h)
    assert h.store.count("alerts", "kind = 'DATA_PROBLEM'") == 1   # once, not every cycle


def test_probe_dormant_wallet_is_quiet_and_its_last_row_is_a_canary(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[SECOND])
    dormant(h)
    assert poll(h).polls[0].ok
    assert h.store.count("health_events") == 0 and h.store.count("fills") == 1
    assert h.store.count("alerts", "kind = 'BET' AND status != 'suppressed'") == 0
    h.clock.advance(30)
    poll(h)
    starts = [int(p["start"]) for u, p in h.api.calls if u.endswith("/v2/activity") and "cursor" not in p]
    assert starts[-1] <= T0 - 40 * 86400                       # the re-read includes the known row


def test_trades_during_a_failing_bootstrap_are_live_not_baseline(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[SECOND])
    h.api.fail("/v2/activity", 503, times=3)
    for _ in range(3):
        assert not poll(h).polls[0].ok
        h.clock.advance(30)
    h.api.add_activity(SECOND, [row(T0 + 40)])               # executed after monitoring began
    h.clock.t = T0 + 100
    assert poll(h).polls[0].ok
    a = h.alerts("BET")
    assert len(a) == 1 and a[0]["status"] != "suppressed", a[0]["suppressed_reason"]


def test_status_outage_keeps_the_last_known_lag_margin(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[SECOND])
    dormant(h)
    body = copy.deepcopy(h.api.status_body)
    body["data"]["serving"]["lag_seconds"] = 900
    h.api.status_body = body
    poll(h)
    assert h.store.poll_state(SECOND)["watermark_ts"] == int(h.clock.t - 900)
    h.clock.advance(30)
    h.api.fail("/v2/status", 503)
    poll(h)
    assert h.store.poll_state(SECOND)["watermark_ts"] <= int(h.clock.t - 900)


# --------------------------------------------------------------------------- pagination

def test_long_backfill_makes_progress_across_failed_polls(tmp_path) -> None:
    """A walk that cannot finish in one poll (max_pages_per_poll, an expired cursor or any error
    on a late page) restarted from the same watermark every time and never caught up."""
    h = Harness(tmp_path, T0, base_config(poll={"page_limit": 5, "max_pages_per_poll": 3}), wallets=[SECOND])
    dormant(h)
    poll(h)
    rows = [row(T0 + 60 + 120 * i, tx=f"0x{i:064x}") for i in range(40)]
    h.api.add_activity(SECOND, rows)
    h.clock.t = T0 + 60 + 120 * 40 + 60
    oks = []
    for i in range(6):
        if i == 1:
            h.api.fail("/v2/activity", 400, after=1)           # an "invalid cursor" on page 2
        oks.append(poll(h).polls[0].ok)
        h.clock.advance(30)
    assert h.store.count("fills", "ts > ?", (T0,)) == 40 and oks[-1]


def test_reanchored_page_does_not_store_phantom_duplicate_fills(tmp_path) -> None:
    """If a cursor page re-serves rows from before its anchor, the walk-wide occurrence counter
    numbered them as new repeats (occurrence 1) and stored phantom fills."""
    h = Harness(tmp_path, T0, base_config(poll={"page_limit": 5}), wallets=[SECOND])
    dormant(h)
    poll(h)
    rows = [row(T0 + 60 + 10 * i, tx=f"0x{i + 100:064x}") for i in range(12)]
    h.api.add_activity(SECOND, rows)
    h.clock.t = T0 + 300
    h.api.prepend_prev_rows = 2
    poll(h)
    assert h.store.count("fills", "ts > ?", (T0,)) <= 12
    h.clock.advance(30)
    assert poll(h).polls[0].ok and h.store.count("fills", "ts > ?", (T0,)) == 12


def test_probe_same_second_fills_in_one_tx_with_true_repeats_across_page_boundaries(tmp_path) -> None:
    h = Harness(tmp_path, T0, base_config(poll={"page_limit": 7}), wallets=[SECOND])
    dormant(h)
    poll(h)
    rows = [row(T0 + 100, size=10.0 + (i % 10), price=0.5 + 0.01 * (i % 10)) for i in range(30)]   # 10 x 3 repeats
    h.api.add_activity(SECOND, rows)
    h.clock.t = T0 + 130
    assert poll(h).polls[0].new_fills == 30
    for _ in range(3):
        h.clock.advance(30)
        assert poll(h).polls[0].new_fills == 0
    assert h.store.count("fills", "ts = ?", (T0 + 100,)) == 30
    live = [a for a in h.alerts("BET") if a["status"] != "suppressed"]
    assert len(live) == 1 and h.store.q1("SELECT n_fills FROM bets WHERE bet_id = ?", (live[0]["bet_id"],))[0] == 30


def test_probe_exclusive_start_would_not_lose_rows(tmp_path) -> None:
    h = Harness(tmp_path, T0, wallets=[SECOND])
    h.api.start_exclusive = True
    dormant(h)
    poll(h)
    for i in range(5):
        h.api.add_activity(SECOND, [row(T0 + 30 * (i + 1), tx=f"0x{i + 500:064x}")])
        h.clock.t = T0 + 30 * (i + 1) + 2
        poll(h)
    assert h.store.count("fills", "ts > ?", (T0,)) == 5


# --------------------------------------------------------------------------- v1 retirement, neg-risk

def test_probe_only_v2_data_api_routes_and_neg_risk_book_is_the_traded_token(tmp_path) -> None:
    h, bet = bet_harness(tmp_path)
    data_paths = {u.split("polymarket.com", 1)[1] for u, _ in h.api.calls if "data-api" in u}
    assert data_paths and all(p.startswith("/v2/") for p in data_paths), data_paths
    en = payload(h)["enrichment"]
    assert en["market_state"]["neg_risk"] is True
    books = [p["token_id"] for u, p in h.api.calls if u.endswith("/book")]
    assert books == [bet["token_id"]]
    assert en["market"]["outcome"] == bet["outcome"]
