"""Health episodes, DATA PROBLEM / DATA RECOVERED notifications and the periodic digest.

A health event row is an *episode*: it opens on the first failure of a given
(scope, kind), counts further occurrences, and closes (``resolved_at``) on the
next success. Notification rules:

* open: notify once ``occurrences >= min_occurrences`` (e.g. 2 consecutive poll
  failures by default; schema surprises and gaps notify immediately);
* still open after ``renotify_minutes``: notify again ("still ongoing");
* resolved: send DATA RECOVERED, but only if the episode had been notified.

Every episode is stored whether or not it was notified, and appears in the digest,
so a transient blip that never reached the threshold is still visible.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable, Iterable

from . import render
from .config import Config
from .store import Store

log = logging.getLogger("alerts.health")


class HealthMonitor:
    def __init__(self, store: Store, cfg: Config, channels: Iterable[str], *,
                 clock: Callable[[], float] = time.time) -> None:
        self.store = store
        self.cfg = cfg
        self.channels = list(channels)
        self.clock = clock
        self.labels = {w.address: f"wallet {w.label} ({render.short(w.address)})" for w in cfg.wallets}

    def scope_label(self, scope: str) -> str:
        return self.labels.get(scope, scope)

    def problem(self, scope: str, kind: str, detail: str, *, error_class: str | None = None,
                severity: str = "error", min_occurrences: int = 1, notify: bool = True,
                watermark_ts: int | None = None, exclude_channels: Iterable[str] = ()) -> int:
        now = self.clock()
        ev = self.store.open_health_event(scope, kind)
        with self.store.tx() as c:
            if ev is None:
                cur = c.execute(
                    """INSERT INTO health_events (scope, kind, error_class, severity, detail, first_at, last_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""", (scope, kind, error_class, severity, detail[:2000], now, now))
                event_id = int(cur.lastrowid)
            else:
                event_id = ev["event_id"]
                c.execute("""UPDATE health_events SET occurrences = occurrences + 1, last_at = ?, detail = ?,
                               error_class = COALESCE(?, error_class) WHERE event_id = ?""",
                          (now, detail[:2000], error_class, event_id))
        ev = self.store.q1("SELECT * FROM health_events WHERE event_id = ?", (event_id,))
        log.warning("DATA PROBLEM %s %s/%s (x%d): %s", self.scope_label(scope), kind, error_class or "-",
                    ev["occurrences"], detail)
        if not notify or ev["occurrences"] < min_occurrences:
            return event_id
        renotify = ev["notified_at"] is not None
        if renotify and now - ev["notified_at"] < self.cfg.health.renotify_minutes * 60:
            return event_id
        key = f"health:{event_id}:" + (f"renotify:{ev['notify_count']}" if renotify else "open")
        text = render.data_problem(self.scope_label(scope), kind, ev["error_class"], detail, first_at=ev["first_at"],
                                   occurrences=ev["occurrences"], watermark_ts=watermark_ts, renotify=renotify)
        # A failing channel is excluded from its own failure notice, unless it is the only channel:
        # then the notice is queued on it anyway (it is delivered once the channel recovers)
        # rather than being created with no channel at all, which would make the loss silent.
        channels = [c for c in self.channels if c not in set(exclude_channels)] or list(self.channels)
        self.store.create_alert(dedupe_key=key, kind="DATA_PROBLEM", label="DATA PROBLEM", text=text,
                                payload={"scope": scope, "kind": kind, "error_class": ev["error_class"],
                                         "detail": detail, "event_id": event_id, "occurrences": ev["occurrences"]},
                                now=now, channels=channels, wallet=scope if scope.startswith("0x") else None)
        self.store.conn.execute("UPDATE health_events SET notified_at = ?, notify_count = notify_count + 1 "
                                "WHERE event_id = ?", (now, event_id))
        return event_id

    def resolve(self, scope: str, kinds: Iterable[str] | None = None, extra: str = "") -> list[int]:
        now = self.clock()
        kinds = list(kinds) if kinds is not None else None
        rows = self.store.q("SELECT * FROM health_events WHERE scope = ? AND resolved_at IS NULL", (scope,))
        done = []
        for ev in rows:
            if kinds is not None and ev["kind"] not in kinds:
                continue
            self.store.conn.execute("UPDATE health_events SET resolved_at = ? WHERE event_id = ?", (now, ev["event_id"]))
            done.append(ev["event_id"])
            log.info("resolved %s %s after %d occurrence(s)", self.scope_label(scope), ev["kind"], ev["occurrences"])
            if ev["notified_at"] is not None:
                self.store.create_alert(
                    dedupe_key=f"health:{ev['event_id']}:resolved", kind="DATA_RECOVERED", label="DATA RECOVERED",
                    text=render.data_recovered(self.scope_label(scope), ev["kind"], ev["first_at"], now, extra),
                    payload={"scope": scope, "kind": ev["kind"], "event_id": ev["event_id"]}, now=now,
                    channels=self.channels, wallet=scope if scope.startswith("0x") else None)
        return done

    # ------------------------------------------------------------------ checks

    def check_status(self, status: dict) -> None:
        h = self.cfg.health
        lag, age = status.get("lag_seconds"), status.get("age_seconds")
        if lag is None:
            self.problem("data-api", "status_lag", "/v2/status reports no serving lag (no mechanism reported)",
                         error_class="schema", min_occurrences=2)
        elif lag > h.status_lag_threshold_seconds:
            self.problem("data-api", "status_lag",
                         f"Data API serving lag {lag}s > {h.status_lag_threshold_seconds:g}s (worst: {status.get('worst')}); "
                         "new fills may appear late", error_class="feed_lag")
        else:
            self.resolve("data-api", ["status_lag"])
        if age is not None and age > h.status_snapshot_max_age_seconds:
            self.problem("data-api", "status_snapshot_stale",
                         f"/v2/status snapshot is {age}s old (> {h.status_snapshot_max_age_seconds:g}s); the freshness "
                         "monitor itself is stalled", error_class="feed_lag")
        else:
            self.resolve("data-api", ["status_snapshot_stale"])
        self.resolve("data-api", ["status_unavailable"])

    def check_stale(self, started_at: float) -> None:
        """A wallet is stale when it has had no successful poll for stale_after_intervals x interval."""
        now = self.clock()
        limit = self.cfg.health.stale_after_intervals * self.cfg.poll.interval_seconds
        for w in self.cfg.wallets:
            if not w.enabled:
                continue
            st = self.store.poll_state(w.address)
            ref = (st["last_success_at"] if st and st["last_success_at"] else started_at)
            age = now - ref
            if age > limit:
                self.problem(w.address, "stale",
                             f"no successful poll for {render.dur(age)} (> {self.cfg.health.stale_after_intervals} "
                             f"intervals of {self.cfg.poll.interval_seconds:g}s); last error: "
                             f"{(st['last_error'] if st else None) or 'n/a'}", error_class="stale",
                             watermark_ts=st["watermark_ts"] if st else None)
            else:
                self.resolve(w.address, ["stale"])

    # ------------------------------------------------------------------ digest

    def maybe_digest(self) -> int | None:
        now = self.clock()
        last = self.store.get_meta("digest_last_at")
        if last is None:
            self.store.set_meta("digest_last_at", repr(now))
            self.store.set_meta("digest_counters", json.dumps(self._counters()))
            return None
        last_f = float(last)
        if now - last_f < self.cfg.health.digest_interval_hours * 3600:
            return None
        d = self.digest_data(last_f, now)
        alert_id = self.store.create_alert(dedupe_key=f"digest:{int(last_f)}", kind="DIGEST", label="DIGEST",
                                           text=render.digest(d), payload=d, now=now, channels=self.channels)
        self.store.set_meta("digest_last_at", repr(now))
        self.store.set_meta("digest_counters", json.dumps(self._counters()))
        return alert_id

    def _counters(self) -> dict:
        r = self.store.q1("SELECT COALESCE(SUM(polls_ok), 0) ok, COALESCE(SUM(polls_failed), 0) failed FROM poll_state")
        return {"polls_ok": int(r["ok"]), "polls_failed": int(r["failed"])}

    def digest_data(self, t0: float, t1: float) -> dict:
        s = self.store
        prev = json.loads(s.get_meta("digest_counters") or '{"polls_ok": 0, "polls_failed": 0}')
        cur = self._counters()
        fills = s.q("SELECT CASE WHEN activity_type = 'TRADE' THEN side ELSE activity_type END k, COUNT(*) n "
                    "FROM fills WHERE first_seen_at >= ? AND first_seen_at < ? GROUP BY k", (t0, t1))
        bets = s.q("SELECT kind, COUNT(*) n FROM bets WHERE first_seen_at >= ? AND first_seen_at < ? GROUP BY kind", (t0, t1))
        alerts = s.q("SELECT label, COUNT(*) n FROM alerts WHERE kind = 'BET' AND status != 'suppressed' "
                     "AND created_at >= ? AND created_at < ? GROUP BY label", (t0, t1))
        non_buy = s.q("""SELECT w.label, b.side, COUNT(*) n, SUM(b.usdc_size) usd FROM bets b
                         JOIN wallets w ON w.address = b.wallet
                         WHERE b.side != 'BUY' AND b.first_seen_at >= ? AND b.first_seen_at < ?
                         GROUP BY w.label, b.side""", (t0, t1))
        stale = s.q1("SELECT wallet, MIN(last_success_at) t FROM poll_state")
        most_stale = "n/a"
        if stale and stale["t"]:
            most_stale = f"{self.scope_label(stale['wallet'])}: last success {render.dur(t1 - stale['t'])} ago"
        return {
            "from": t0, "to": t1,
            "wallets": sum(1 for w in self.cfg.wallets if w.enabled),
            "polls_ok": cur["polls_ok"] - prev.get("polls_ok", 0),
            "polls_failed": cur["polls_failed"] - prev.get("polls_failed", 0),
            "fills_total": sum(r["n"] for r in fills),
            "fills_by_type": {r["k"]: r["n"] for r in fills},
            "bets_by_kind": {r["kind"]: r["n"] for r in bets},
            "alerts_by_label": {r["label"]: r["n"] for r in alerts},
            "alerts_suppressed": s.count("alerts", "kind = 'BET' AND status = 'suppressed' AND created_at >= ? "
                                         "AND created_at < ?", (t0, t1)),
            "delivery_failures": s.count("deliveries", "status IN ('failed', 'unknown') AND last_attempt_at >= ? "
                                         "AND last_attempt_at < ?", (t0, t1)),
            "problems_opened": s.count("health_events", "first_at >= ? AND first_at < ?", (t0, t1)),
            "problems_open": s.count("health_events", "resolved_at IS NULL"),
            "most_stale": most_stale,
            "non_buy_summary": [f"{r['label']}: {r['side']} x{r['n']} (${r['usd']:,.0f})" for r in non_buy],
        }
