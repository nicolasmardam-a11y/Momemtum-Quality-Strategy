"""Delivery state machine: pending -> sending -> sent | pending (retry) | failed | unknown.

Delivery semantics (documented choice)
--------------------------------------
Each (alert, channel) delivery is committed as ``sending`` *before* the network
call and as ``sent``/``pending``/``failed`` after it. If the process dies between
those two commits the outcome is unknown. On restart:

* ``at_least_once`` (default): the delivery is re-queued with
  ``possible_duplicate=1`` and re-sent with a visible "[POSSIBLE DUPLICATE]"
  marker. A missed bet alert is worse than a visible duplicate.
* ``at_most_once``: the delivery is marked ``unknown``, never re-sent, and a
  health event is recorded so the possible loss is not silent.

Alerts themselves are created exactly once (UNIQUE dedupe_key), so re-polling
or re-evaluating never produces a second alert for the same bet.

Rate limiting and backoff never block polling: a rate-limited or failed delivery
is rescheduled (``next_attempt_at``) and the dispatcher moves on. In loop mode it
runs in its own thread with its own SQLite connection.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable

from .config import Config
from .notify import Message, Notifier, NotifyError, TokenBucket
from .store import Store

log = logging.getLogger("alerts.dispatch")


class Dispatcher:
    def __init__(self, store: Store, notifiers: dict[str, Notifier], cfg: Config, *,
                 clock: Callable[[], float] = time.time, monotonic: Callable[[], float] = time.monotonic,
                 on_problem: Callable[[str, str, str], None] | None = None) -> None:
        self.store = store
        self.notifiers = notifiers
        self.cfg = cfg
        self.clock = clock
        n = cfg.notifications
        self.buckets = {name: TokenBucket(n.channels[name].rate_per_minute, n.channels[name].burst, monotonic)
                        for name in notifiers}
        # on_problem(scope, kind, detail) lets the engine record health events.
        self.on_problem = on_problem or (lambda scope, kind, detail: None)

    def recover_inflight(self) -> int:
        """Handle deliveries left in 'sending' by a crash. Returns how many were found."""
        rows = self.store.q("SELECT alert_id, channel FROM deliveries WHERE status = 'sending'")
        now = self.clock()
        for r in rows:
            if self.cfg.notifications.delivery_semantics == "at_least_once":
                self.store.conn.execute(
                    "UPDATE deliveries SET status = 'pending', possible_duplicate = 1, next_attempt_at = ? "
                    "WHERE alert_id = ? AND channel = ?", (now, r["alert_id"], r["channel"]))
                log.warning("delivery alert=%s channel=%s was interrupted mid-send; re-queued as possible duplicate",
                            r["alert_id"], r["channel"])
            else:
                self.store.conn.execute(
                    "UPDATE deliveries SET status = 'unknown', last_error = 'interrupted mid-send (at_most_once: not resent)' "
                    "WHERE alert_id = ? AND channel = ?", (r["alert_id"], r["channel"]))
                self.on_problem(f"notify:{r['channel']}", "delivery_unknown",
                                f"alert #{r['alert_id']} may not have been delivered on {r['channel']} "
                                "(interrupted mid-send; at_most_once so it was not re-sent)")
            self.store.refresh_alert_status(r["alert_id"])
        return len(rows)

    def _due(self, limit: int) -> list:
        return self.store.q(
            """SELECT d.alert_id, d.channel, d.attempts, d.possible_duplicate, a.dedupe_key, a.kind, a.label,
                      a.text, a.payload_json
                 FROM deliveries d JOIN alerts a ON a.alert_id = d.alert_id
                WHERE d.status = 'pending' AND d.next_attempt_at <= ?
                ORDER BY d.alert_id, d.channel LIMIT ?""", (self.clock(), limit))

    def flush(self, *, max_items: int = 100, deadline_s: float | None = None) -> dict[str, int]:
        """Attempt every due delivery once (bounded). Returns counts by outcome."""
        stats = {"sent": 0, "retry": 0, "failed": 0, "rate_limited": 0, "skipped": 0}
        t_end = None if deadline_s is None else time.monotonic() + deadline_s
        for d in self._due(max_items):
            if t_end is not None and time.monotonic() > t_end:
                break
            ch = d["channel"]
            notifier = self.notifiers.get(ch)
            now = self.clock()
            if notifier is None:
                # Channel disabled since the alert was queued: keep it, retry later, but say so.
                self.store.conn.execute(
                    "UPDATE deliveries SET next_attempt_at = ?, last_error = 'channel not configured in this run' "
                    "WHERE alert_id = ? AND channel = ?", (now + 300, d["alert_id"], ch))
                stats["skipped"] += 1
                continue
            wait = self.buckets[ch].try_take()
            if wait > 0:
                self.store.conn.execute("UPDATE deliveries SET next_attempt_at = ? WHERE alert_id = ? AND channel = ?",
                                        (now + wait, d["alert_id"], ch))
                stats["rate_limited"] += 1
                continue
            # Commit 'sending' before the network call (see module docstring).
            cur = self.store.conn.execute(
                "UPDATE deliveries SET status = 'sending', attempts = attempts + 1, last_attempt_at = ? "
                "WHERE alert_id = ? AND channel = ? AND status = 'pending'", (now, d["alert_id"], ch))
            if cur.rowcount != 1:
                continue   # another dispatcher took it
            msg = Message(d["alert_id"], d["dedupe_key"], d["kind"], d["label"], d["text"],
                          json.loads(d["payload_json"]), bool(d["possible_duplicate"]))
            try:
                notifier.send(msg)
            except NotifyError as e:
                self._failed(d, ch, e, stats)
            except Exception as e:  # a bug in a notifier must not kill the loop, but it is recorded, not hidden
                scrub = getattr(notifier, "scrub", lambda text: text)
                detail = scrub(f"notifier crashed: {type(e).__name__}: {e}")
                log.error("channel %s: %s", ch, detail)      # no traceback: it could carry an unredacted URL
                self._failed(d, ch, NotifyError(detail), stats)
            else:
                self.store.conn.execute(
                    "UPDATE deliveries SET status = 'sent', sent_at = ?, last_error = NULL WHERE alert_id = ? AND channel = ?",
                    (self.clock(), d["alert_id"], ch))
                stats["sent"] += 1
            self.store.refresh_alert_status(d["alert_id"])
        return stats

    def _failed(self, d, ch: str, e: NotifyError, stats: dict[str, int]) -> None:
        n = self.cfg.notifications
        attempts = d["attempts"] + 1
        now = self.clock()
        if e.retryable and attempts < n.max_attempts:
            delay = min(n.backoff_max_seconds, n.backoff_base_seconds * 2 ** (attempts - 1))
            if e.retry_after_s:
                delay = max(delay, e.retry_after_s)
            self.store.conn.execute(
                "UPDATE deliveries SET status = 'pending', next_attempt_at = ?, last_error = ? "
                "WHERE alert_id = ? AND channel = ?", (now + delay, e.detail[:500], d["alert_id"], ch))
            stats["retry"] += 1
            log.warning("delivery alert=%s channel=%s failed (attempt %d), retry in %.0fs: %s",
                        d["alert_id"], ch, attempts, delay, e.detail)
        else:
            self.store.conn.execute(
                "UPDATE deliveries SET status = 'failed', last_error = ? WHERE alert_id = ? AND channel = ?",
                (e.detail[:500], d["alert_id"], ch))
            stats["failed"] += 1
            log.error("delivery alert=%s channel=%s failed permanently: %s", d["alert_id"], ch, e.detail)
            self.on_problem(f"notify:{ch}", "delivery", f"alert #{d['alert_id']} not delivered on {ch} after "
                                                        f"{attempts} attempt(s): {e.detail}")


class DispatcherThread(threading.Thread):
    """Runs a Dispatcher on its own SQLite connection until ``stop`` is set.

    Delivery problems are recorded through a HealthMonitor bound to the same
    thread-local connection (SQLite connections must not cross threads).
    """

    def __init__(self, db_path: str, notifiers: dict[str, Notifier], cfg: Config, stop: threading.Event,
                 poll_s: float = 1.0) -> None:
        super().__init__(name="alert-dispatcher", daemon=True)
        self.db_path, self.notifiers, self.cfg, self.stop, self.poll_s = db_path, notifiers, cfg, stop, poll_s

    def run(self) -> None:
        from .health import HealthMonitor   # local import: health imports nothing from dispatch

        store = Store(self.db_path)
        health = HealthMonitor(store, self.cfg, self.notifiers)

        def on_problem(scope: str, kind: str, detail: str) -> None:
            ch = scope.split(":", 1)[1] if scope.startswith("notify:") else None
            health.problem(scope, kind, detail, error_class="notify", exclude_channels=[ch] if ch else [])

        disp = Dispatcher(store, self.notifiers, self.cfg, on_problem=on_problem)
        disp.recover_inflight()
        while not self.stop.is_set():
            try:
                disp.flush(max_items=50)
            except Exception:
                log.exception("dispatcher cycle failed; will retry")
            self.stop.wait(self.poll_s)
        try:
            disp.flush(max_items=50, deadline_s=10)
        finally:
            store.close()
