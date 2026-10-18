"""Poll one wallet: window from stored state, full pagination, store fills, advance state.

State rules
-----------
* ``watermark_ts`` means "every row with block timestamp <= watermark has been
  observed". It is set from the Data API's own clock (HTTP ``Date`` of the first
  page) minus a safety margin (max of ``ingest_safety_seconds`` and the current
  ``/v2/status`` serving lag), and never beyond the ``end`` the walk requested.
  All "now" values come from the engine's server-corrected clock (clock.py), so a
  local clock that is hours or days off cannot move the window or the watermark.
* Each poll starts at ``watermark - overlap_seconds`` (re-reading the overlap is
  harmless: fills are deduplicated by id), or ``now - initial_backfill_hours`` for
  a wallet with no state (the bootstrap baseline).
* Canary: the window also always reaches back to the wallet's second-newest stored
  second of activity, and a complete walk must return at least one row this system
  has already stored. A 200 answer with none of them is a DATA PROBLEM
  (``incomplete_data``), never "no new trades", and the watermark does not move.
* The watermark moves to "now - margin" only after a complete walk (``next_cursor``
  null). A walk that fails part-way (error, expired cursor, ``max_pages_per_poll``)
  moves it only to a checkpoint the walk proved complete: one second before the
  newest row of the last page that had a successor (``sort_direction=ASC`` keyset
  on block timestamp; the walk is checked to be non-decreasing), so a long backfill
  progresses across polls instead of restarting forever. Fills from completed pages
  stay (they are facts).
* A gap larger than ``gap_horizon_hours`` is still backfilled completely by
  pagination; it is flagged as a ``gap`` health event and resolved when the
  backfill completes.
* Bootstrap baseline: fills executed before the wallet's *first poll attempt*
  (``first_attempt_at``) are baseline; anything executed after it is live, even if
  the first successful poll comes much later.
"""
from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass
from typing import Callable

from . import render
from .config import Config, WalletConfig
from .fills import OccurrenceCounter, to_fills
from .health import HealthMonitor
from .http_client import DataError
from .sources import Sources
from .store import Store

log = logging.getLogger("alerts.poller")

NO_HISTORY_DETAIL = (
    "the Data API has no activity of the monitored types for this address at all (full history checked). "
    "Every poll would report 'no new trades' forever. Check that it is the account (proxy) wallet shown on the "
    "Polymarket profile, not a signer/EOA or a mistyped address.")


@dataclass
class PollResult:
    wallet: str
    ok: bool
    rows: int = 0
    new_fills: int = 0
    pages: int = 0
    start_ts: int = 0
    bootstrap: bool = False
    error: str | None = None
    error_class: str | None = None

    @property
    def outcome(self) -> str:
        if not self.ok:
            return f"FAILED ({self.error_class})"
        return "ok, no new trades" if self.new_fills == 0 else f"ok, {self.new_fills} new fill(s)"


class Poller:
    def __init__(self, store: Store, sources: Sources, cfg: Config, health: HealthMonitor, *,
                 clock: Callable[[], float] = time.time) -> None:
        self.store, self.sources, self.cfg, self.health, self.clock = store, sources, cfg, health, clock

    def window_start(self, st, now: float, forced_backfill_hours: float | None) -> tuple[int, bool]:
        p = self.cfg.poll
        if st is None or st["watermark_ts"] is None:
            hours = forced_backfill_hours if forced_backfill_hours is not None else p.initial_backfill_hours
            return int(now - hours * 3600), True
        start = int(st["watermark_ts"] - p.overlap_seconds)
        if forced_backfill_hours is not None:
            start = min(start, int(now - forced_backfill_hours * 3600))
        return start, False

    def _observe(self, server_now: float | None) -> None:
        observe = getattr(self.clock, "observe", None)
        if observe is not None:
            observe(server_now)

    def poll(self, w: WalletConfig, *, status_lag_s: float | None = None,
             forced_backfill_hours: float | None = None) -> PollResult:
        p = self.cfg.poll
        now = self.clock()
        st = self.store.poll_state(w.address)
        start, bootstrap = self.window_start(st, now, forced_backfill_hours)
        if not bootstrap:
            canary = self.store.canary_ts(w.address, p.activity_types)
            if canary is not None:
                start = min(start, canary - 1)       # -1: robust even if `start` were exclusive
        end = int(now) + 86_400                       # the API default (now + 1 day); also a CDN-cache miss
        expected = (self.store.known_fill_ids(w.address, p.activity_types, start + 1, end)
                    if not bootstrap else set())
        first_attempt = st["first_attempt_at"] if st is not None and st["first_attempt_at"] is not None else now
        res = PollResult(w.address, ok=False, start_ts=start, bootstrap=bootstrap)
        watermark = st["watermark_ts"] if st else None
        if watermark is not None and now - watermark > p.gap_horizon_hours * 3600:
            self.health.problem(
                w.address, "gap",
                f"no confirmed data for {render.dur(now - watermark)} (watermark {render.utc(watermark)}); "
                f"backfilling completely from {render.utc(start)} with full pagination. Alerts for fills older "
                f"than {self.cfg.alerting.max_alert_age_minutes:g} min are recorded but suppressed.",
                error_class="gap", severity="warning", watermark_ts=watermark)
        occ = OccurrenceCounter()
        server_time: float | None = None
        last_cursor: str | None = None
        max_ts: int | None = None
        complete_before: int | None = None    # every row with ts < this has been returned
        seen: set[str] = set()
        mode = "bootstrap" if bootstrap else "live"
        try:
            for page in self.sources.iter_activity(w.address, start=start, types=p.activity_types,
                                                   limit=p.page_limit, max_pages=p.max_pages_per_poll, end=end):
                if server_time is None:
                    server_time = page.server_time
                    self._observe(page.server_now)
                fills = to_fills(page.rows, occ, seen_at=self.clock(), poll_mode=mode,
                                 live_from_ts=first_attempt if bootstrap else None)
                seen.update(f["fill_id"] for f in fills)
                res.new_fills += len(self.store.insert_fills(fills))
                res.rows += len(page.rows)
                res.pages = page.page_no
                last_cursor = page.next_cursor
                if page.rows:
                    page_max = max(int(r["timestamp"]) for r in page.rows)
                    max_ts = max(max_ts or 0, page_max)
                    if page.next_cursor:
                        complete_before = page_max
            if bootstrap and res.rows == 0:
                self._probe_history(w, now, end)
        except DataError as e:
            self._checkpoint(w, complete_before, server_time, status_lag_s, max_ts)
            return self._failed(w, res, e.kind, str(e), last_cursor, watermark,
                                min_occ=1 if e.kind == "schema" else self.cfg.health.notify_after_consecutive_failures)
        except Exception as e:   # a bug or an unexpected payload: recorded and reported, never swallowed
            log.error("internal error polling %s:\n%s", w.label, traceback.format_exc())
            return self._failed(w, res, "internal", f"{type(e).__name__}: {e}", last_cursor, watermark, min_occ=1)

        if expected and not (expected & seen):
            return self._failed(
                w, res, "incomplete_data",
                f"the Data API answered 200 but returned none of the {len(expected)} row(s) of this wallet already "
                f"stored with block time >= {render.utc(start + 1)}; it is not serving this wallet's history "
                "(degraded backend or changed filter), so this cannot be read as 'no new trades'",
                last_cursor, watermark, min_occ=1)
        missing = expected - seen
        if missing:
            self.health.problem(
                w.address, "vanished_rows",
                f"{len(missing)} of {len(expected)} previously stored row(s) were not returned by this re-read "
                "(re-index or chain reorg?). Polling continues; inspect the fills table if this persists.",
                error_class="incomplete_data", severity="warning")
        else:
            self.health.resolve(w.address, ["vanished_rows"])
        if res.rows:
            self.health.resolve(w.address, ["no_history"])

        ref = server_time if server_time is not None else self.clock()
        margin = max(float(p.ingest_safety_seconds), float(status_lag_s or 0.0))
        new_wm = min(int(ref - margin), end)          # never past the end of the window actually requested
        self.store.mark_poll_success(w.address, watermark_ts=new_wm, last_seen_row_ts=max_ts, now=now,
                                     rows=res.rows, new_fills=res.new_fills, bootstrap=bootstrap)
        res.ok = True
        self.health.resolve(w.address, ["poll_failure", "gap"],
                            extra=f"Backfill complete: {res.rows} row(s) read, {res.new_fills} new fill(s) stored.")
        log.info("poll %s: %s (rows=%d pages=%d from %s%s)", w.label, res.outcome, res.rows, res.pages,
                 render.utc(start), ", bootstrap" if bootstrap else "")
        return res

    def _probe_history(self, w: WalletConfig, now: float, end: int) -> None:
        """Empty bootstrap window: is this a dormant account or an address with no history at all?"""
        latest = self.sources.latest_activity(w.address, self.cfg.poll.activity_types, end=end)
        if latest is None:
            self.health.problem(w.address, "no_history", NO_HISTORY_DETAIL, error_class="no_history",
                                severity="warning")
            return
        # Store the newest row as baseline: it becomes the canary every later poll must re-read.
        self.store.insert_fills(to_fills([latest], OccurrenceCounter(), seen_at=self.clock(), poll_mode="bootstrap"))

    def _checkpoint(self, w: WalletConfig, complete_before: int | None, server_time: float | None,
                    status_lag_s: float | None, max_ts: int | None) -> None:
        if complete_before is None or server_time is None:
            return
        p = self.cfg.poll
        margin = max(float(p.ingest_safety_seconds), float(status_lag_s or 0.0))
        cp = min(complete_before - 1, int(server_time - margin))
        if self.store.advance_checkpoint(w.address, cp, last_seen_row_ts=max_ts):
            log.info("poll %s: partial walk checkpointed, watermark -> %s", w.label, render.utc(cp))

    def _failed(self, w: WalletConfig, res: PollResult, kind: str, detail: str, last_cursor: str | None,
                watermark: int | None, *, min_occ: int) -> PollResult:
        res.error, res.error_class = detail, kind
        n = self.store.mark_poll_failure(w.address, now=self.clock(), error=f"{kind}: {detail}",
                                         last_cursor=last_cursor, new_fills=res.new_fills)
        self.health.problem(w.address, "poll_failure", f"{detail} [consecutive failures: {n}]", error_class=kind,
                            min_occurrences=min_occ, watermark_ts=watermark)
        log.warning("poll %s FAILED (%s, %d consecutive): %s; watermark not advanced past the last complete page",
                    w.label, kind, n, detail)
        return res
