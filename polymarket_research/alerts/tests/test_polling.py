"""Dedupe on overlapping polls, failure paths, no-new-trades vs failure, restart recovery."""
from __future__ import annotations

from .conftest import MINTBLADE, SECOND, Harness, add_dormant, base_config


def uruguay(mint_rows):
    cid = next(r["condition_id"] for r in mint_rows if r["title"].startswith("Will Uruguay win"))
    return [r for r in mint_rows if r["condition_id"] == cid and r["type"] == "TRADE"]


def poll(h: Harness):
    rep = h.engine.run_cycle()
    h.engine.dispatcher.flush()
    return rep


def test_overlapping_polls_never_duplicate_fills_or_alerts(tmp_path, mint_rows) -> None:
    rows = uruguay(mint_rows)                               # 36 fills, one bet, 316 s
    t_first = rows[0]["timestamp"]
    h = Harness(tmp_path, t_first - 3600, wallets=[MINTBLADE])
    rep = poll(h)                                           # bootstrap: nothing yet
    assert rep.polls[0].ok and rep.polls[0].bootstrap and rep.polls[0].new_fills == 0

    h.clock.t = rows[19]["timestamp"] + 20
    h.api.add_activity(MINTBLADE, rows[:20])
    rep = poll(h)
    assert rep.polls[0].new_fills == 20 and not rep.polls[0].bootstrap
    for _ in range(3):                                      # same data, overlapping windows
        h.clock.advance(30)
        rep = poll(h)
        assert rep.polls[0].ok and rep.polls[0].rows == 20 and rep.polls[0].new_fills == 0
    h.api.add_activity(MINTBLADE, rows[20:])
    h.clock.t = rows[-1]["timestamp"] + 15
    rep = poll(h)
    assert rep.polls[0].new_fills == 16 and rep.polls[0].rows == 36
    assert h.store.count("fills") == 36
    bets = h.store.q("SELECT * FROM bets")
    assert len(bets) == 1 and bets[0]["n_fills"] == 36
    assert len(h.alerts("BET")) == 1                         # one alert despite five polls
    assert h.store.count("deliveries", "status = 'sent' AND alert_id IN (SELECT alert_id FROM alerts "
                                       "WHERE kind = 'BET')") == 2   # console + file, once each
    assert h.out.getvalue().count("NEW BET DETECTED") == 1
    # one BET line (the other lines are the no_history notice for this history-less fake wallet and its recovery)
    assert sum('"kind": "BET"' in ln for ln in h.file_path.read_text().splitlines()) == 1


def test_no_new_trades_is_success_not_a_problem(tmp_path) -> None:
    h = Harness(tmp_path, 1_792_250_000, wallets=[SECOND])
    add_dormant(h.api, SECOND, 1_792_250_000 - 40 * 86400)   # a real, dormant account (review: see no_history)
    for _ in range(4):
        rep = poll(h)
        h.clock.advance(30)
        p = rep.polls[0]
        assert p.ok and p.outcome == "ok, no new trades"
    st = h.store.poll_state(SECOND)
    assert st["consecutive_failures"] == 0 and st["polls_ok"] == 4
    assert st["watermark_ts"] == int(h.clock.t - 30 - 30)      # server Date - ingest_safety_seconds
    assert h.alerts("DATA_PROBLEM") == [] and h.store.count("health_events") == 0


def test_failures_never_advance_state_and_raise_data_problem(tmp_path, second_rows) -> None:
    h = Harness(tmp_path, 1_792_250_000, wallets=[SECOND])
    add_dormant(h.api, SECOND, 1_792_250_000 - 40 * 86400)
    poll(h)
    wm = h.store.poll_state(SECOND)["watermark_ts"]
    h.clock.advance(30)
    h.api.fail("/v2/activity", 500)
    rep = poll(h)
    assert not rep.polls[0].ok and rep.polls[0].error_class == "http_error"
    st = h.store.poll_state(SECOND)
    assert st["watermark_ts"] == wm and st["consecutive_failures"] == 1 and "HTTP 500" in st["last_error"]
    assert h.alerts("DATA_PROBLEM") == []                   # 1 < notify_after_consecutive_failures (2)
    h.clock.advance(30)
    h.api.fail("/v2/activity", "timeout")
    poll(h)
    probs = h.alerts("DATA_PROBLEM")
    assert len(probs) == 1 and "timeout" in probs[0]["text"] and "NOT 'no new trades'" in probs[0]["text"]
    assert h.store.poll_state(SECOND)["watermark_ts"] == wm
    h.clock.advance(30)
    h.api.fail("/v2/activity", "connection")
    poll(h)
    assert len(h.alerts("DATA_PROBLEM")) == 1                # no spam while the episode is open
    h.clock.advance(3700)                                   # renotify_minutes = 60
    h.api.fail("/v2/activity", 502)
    poll(h)
    probs = [a for a in h.alerts("DATA_PROBLEM") if '"kind": "poll_failure"' in a["payload_json"]]
    assert len(probs) == 2 and "still ongoing" in probs[1]["text"]
    stale = [a for a in h.alerts("DATA_PROBLEM") if '"kind": "stale"' in a["payload_json"]]
    assert len(stale) == 1                                   # > 5 intervals without a successful poll
    h.clock.advance(30)
    rep = poll(h)                                            # recovery
    assert rep.polls[0].ok
    assert len(h.alerts("DATA_RECOVERED")) == 2              # poll_failure and stale episodes both close
    st = h.store.poll_state(SECOND)
    assert st["consecutive_failures"] == 0 and st["watermark_ts"] > wm
    assert h.store.count("health_events", "resolved_at IS NULL AND kind = 'poll_failure'") == 0
    assert "[DATA PROBLEM]" in h.out.getvalue() and "[DATA RECOVERED]" in h.out.getvalue()


def test_schema_surprise_notifies_immediately(tmp_path) -> None:
    h = Harness(tmp_path, 1_792_250_000, wallets=[MINTBLADE])
    add_dormant(h.api, MINTBLADE, 1_792_250_000 - 40 * 86400)
    poll(h)
    h.api.fail("/v2/activity", "missing_field")
    rep = poll(h)
    assert rep.polls[0].error_class == "schema"
    probs = h.alerts("DATA_PROBLEM")
    assert len(probs) == 1 and "schema" in probs[0]["text"]


def test_failure_mid_pagination_keeps_facts_and_checkpoints_only_complete_pages(tmp_path, second_rows) -> None:
    d = base_config(poll={"page_limit": 5})
    recent = [r for r in second_rows if r["type"] == "TRADE"][-12:]
    t_first = recent[0]["timestamp"]
    h = Harness(tmp_path, t_first - 600, d, wallets=[SECOND])
    poll(h)                                                  # empty bootstrap
    wm = h.store.poll_state(SECOND)["watermark_ts"]
    h.api.add_activity(SECOND, recent)
    h.clock.t = recent[-1]["timestamp"] + 10
    h.api.fail("/v2/activity", 503, after=1)                 # page 1 ok, page 2 fails
    rep = poll(h)
    assert not rep.polls[0].ok and rep.polls[0].new_fills == 5
    assert h.store.count("fills") == 5
    # Review: the watermark moves only to a checkpoint the walk proved complete (before the newest row
    # of page 1, whose successor page failed), never to "now"; the unread rows stay in the next window.
    cp = h.store.poll_state(SECOND)["watermark_ts"]
    assert wm <= cp < recent[4]["timestamp"] and cp - h.cfg.poll.overlap_seconds < recent[5]["timestamp"]
    alerts_after_failure = len(h.alerts("BET"))
    h.clock.advance(30)
    rep = poll(h)
    assert rep.polls[0].ok and rep.polls[0].new_fills == 7 and h.store.count("fills") == 12
    assert h.store.poll_state(SECOND)["watermark_ts"] > wm
    # fills stored by the failed poll were still evaluated (alerting does not depend on "new in this poll")
    buy_bets = h.store.count("bets", "side = 'BUY'")
    assert len(h.alerts("BET")) == buy_bets >= alerts_after_failure
    assert len({a["bet_id"] for a in h.alerts("BET")}) == len(h.alerts("BET"))


def test_status_lag_is_a_data_problem_and_widens_margin(tmp_path) -> None:
    h = Harness(tmp_path, 1_792_250_000, wallets=[SECOND])
    add_dormant(h.api, SECOND, 1_792_250_000 - 40 * 86400)
    h.api.status_body = {"data": {**h.api.status_body["data"],
                                  "serving": {"lag_seconds": 900, "worst": "activity_feed", "mechanisms": []}}}
    poll(h)
    probs = h.alerts("DATA_PROBLEM")
    assert len(probs) == 1 and "serving lag 900s" in probs[0]["text"]
    assert h.store.poll_state(SECOND)["watermark_ts"] == int(h.clock.t - 900)


def test_stale_wallet_is_reported(tmp_path) -> None:
    d = base_config(health={"notify_after_consecutive_failures": 100, "stale_after_intervals": 3})
    h = Harness(tmp_path, 1_792_250_000, d, wallets=[SECOND])
    poll(h)
    for _ in range(5):
        h.clock.advance(30)
        h.api.fail("/v2/activity", 500)
        poll(h)
    kinds = [a["payload_json"] for a in h.alerts("DATA_PROBLEM")]
    assert any('"kind": "stale"' in k for k in kinds)
    assert not any('"kind": "poll_failure"' in k for k in kinds)   # below its own threshold


def test_restart_after_long_outage_backfills_everything(tmp_path, second_rows) -> None:
    """Crash, 30-day outage, restart: every row after the stored watermark is fetched via
    pagination (no silent skipping), the gap is flagged, old bets are recorded but suppressed."""
    d = base_config(poll={"page_limit": 7})
    rows = [r for r in second_rows]
    split = 30
    t_a = rows[split - 1]["timestamp"] + 60
    h = Harness(tmp_path, t_a, d, wallets=[SECOND])
    h.api.add_activity(SECOND, rows[:split])
    poll(h)
    baseline = h.store.count("fills")
    wm = h.store.poll_state(SECOND)["watermark_ts"]
    assert baseline == sum(1 for r in rows[:split] if r["timestamp"] >= t_a - 24 * 3600)

    # outage: the process is gone while the wallet keeps trading
    h.store.close()
    h.api.add_activity(SECOND, rows[split:])
    h.clock.t = rows[-1]["timestamp"] + 120                  # months later, last fill 2 min ago
    calls_before = h.api.count("/v2/activity")
    h.open()                                                 # restart from the stored state
    rep = poll(h)
    assert rep.polls[0].ok
    expected = {i for i, r in enumerate(rows) if r["timestamp"] >= wm - 600 or
                (i < split and r["timestamp"] >= t_a - 24 * 3600)}
    assert h.store.count("fills") == len(expected) == len(rows) - sum(
        1 for r in rows[:split] if r["timestamp"] < t_a - 24 * 3600)
    assert h.api.count("/v2/activity") - calls_before >= (len(rows) - split) // 7   # paginated
    gap = h.store.q("SELECT * FROM health_events WHERE kind = 'gap'")
    assert len(gap) == 1 and gap[0]["resolved_at"] is not None
    texts = [a["text"] for a in h.alerts("DATA_PROBLEM")] + [a["text"] for a in h.alerts("DATA_RECOVERED")]
    assert any("backfilling completely" in t for t in texts) and any("Backfill complete" in t for t in texts)
    sup = h.store.q("SELECT * FROM alerts WHERE status = 'suppressed' AND suppressed_reason LIKE 'too old%'")
    assert sup, "bets from the outage that are older than max_alert_age are recorded as suppressed"
    live = [a for a in h.alerts("BET") if a["status"] != "suppressed"]
    assert all(h.clock.t - h.store.q1("SELECT last_ts FROM bets WHERE bet_id = ?", (a["bet_id"],))[0] <= 6 * 3600
               for a in live)
    # a second restart re-reads the overlap and creates nothing new
    n_alerts, n_fills = h.store.count("alerts"), h.store.count("fills")
    h.restart()
    h.clock.advance(30)
    poll(h)
    assert h.store.count("fills") == n_fills
    assert h.store.count("alerts", "kind = 'BET'") == len(h.alerts("BET"))
    assert h.store.count("alerts") == n_alerts


def test_enrichment_budget_defers_and_wallet_cap_limits_floods(tmp_path, second_rows) -> None:
    """A very active wallet must not stall the loop: at most N enrichments per cycle (the rest
    wait, freshest first), and at most M alerts per wallet per hour (the rest are recorded)."""
    base = 1_792_250_000
    buys = [r for r in second_rows if r["type"] == "TRADE" and r["side"] == "BUY"][:12]
    rows = [dict(r, timestamp=base + 900 * i) for i, r in enumerate(buys)]   # 12 separate bets, 15 min apart
    d = base_config(alerting={"max_enrichments_per_cycle": 4, "max_alerts_per_wallet_per_hour": 6},
                    poll={"gap_horizon_hours": 48})
    h = Harness(tmp_path, base - 60, d, wallets=[SECOND])
    poll(h)                                                   # empty bootstrap
    h.api.add_activity(SECOND, rows)
    h.clock.t = rows[-1]["timestamp"] + 30
    rep = poll(h)
    assert rep.alerts_created == 4
    assert h.store.count("bets", "needs_eval = 1") == 8       # deferred, not dropped
    newest = h.store.q1("SELECT bet_id FROM bets ORDER BY last_ts DESC LIMIT 1")[0]
    assert newest in {a["bet_id"] for a in h.alerts("BET")}    # freshest first
    h.clock.advance(30)
    rep = poll(h)
    assert rep.alerts_created == 2                            # cap of 6 per hour reached
    h.clock.advance(30)
    poll(h)
    sent = [a for a in h.alerts("BET") if a["status"] != "suppressed"]
    capped = h.store.q("SELECT * FROM alerts WHERE suppressed_reason LIKE 'wallet alert cap%'")
    assert len(sent) == 6 and len(capped) == 6 and h.store.count("bets", "needs_eval = 1") == 0
    notices = h.alerts("NOTICE")
    assert len(notices) == 1 and "[ALERT CAP]" in notices[0]["text"]
