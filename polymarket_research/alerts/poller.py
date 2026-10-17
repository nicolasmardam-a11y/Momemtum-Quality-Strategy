"""Poll one wallet: window from stored state, full pagination, store fills, advance state.

State rules
-----------
* ``watermark_ts`` means "every row with block timestamp <= watermark has been
  observed". It is set from the Data API's own clock (HTTP ``Date`` of the first
  page) minus a safety margin (max of ``ingest_safety_seconds`` and the current
  ``/v2/status`` serving lag), so local clock skew cannot move it.
* Each poll starts at ``watermark - overlap_seconds`` (re-reading the overlap is
  harmless: fills are deduplicated by id), or ``now - initial_backfill_hours`` for
  a wallet with no state (the bootstrap baseline).
* The watermark only moves after a complete walk (``next_cursor`` null). Any
  failure, including one on page 37 of 40, leaves it untouched; fills already
  stored from earlier pages stay (they are facts) and the next poll re-reads them.
* A gap larger than ``gap_horizon_hours`` is still backfilled completely by
  pagination; it is flagged as a ``gap`` health event and resolved when the
  backfill completes.
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

    def poll(self, w: WalletConfig, *, status_lag_s: float | None = None,
             forced_backfill_hours: float | None = None) -> PollResult:
        p = self.cfg.poll
        now = self.clock()
        st = self.store.poll_state(w.address)
        start, bootstrap = self.window_start(st, now, forced_backfill_hours)
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
        mode = "bootstrap" if bootstrap else "live"
        try:
            for page in self.sources.iter_activity(w.address, start=start, types=p.activity_types,
                                                   limit=p.page_limit, max_pages=p.max_pages_per_poll):
                if server_time is None:
                    server_time = page.server_time
                fills = to_fills(page.rows, occ, seen_at=self.clock(), poll_mode=mode)
                res.new_fills += len(self.store.insert_fills(fills))
                res.rows += len(page.rows)
                res.pages = page.page_no
                last_cursor = page.next_cursor
                if page.rows:
                    max_ts = max(max_ts or 0, max(int(r["timestamp"]) for r in page.rows))
        except DataError as e:
            return self._failed(w, res, e.kind, str(e), last_cursor, watermark,
                                min_occ=1 if e.kind == "schema" else self.cfg.health.notify_after_consecutive_failures)
        except Exception as e:   # a bug or an unexpected payload: recorded and reported, never swallowed
            log.error("internal error polling %s:\n%s", w.label, traceback.format_exc())
            return self._failed(w, res, "internal", f"{type(e).__name__}: {e}", last_cursor, watermark, min_occ=1)

        ref = server_time if server_time is not None else self.clock()
        margin = max(float(p.ingest_safety_seconds), float(status_lag_s or 0.0))
        new_wm = int(ref - margin)
        self.store.mark_poll_success(w.address, watermark_ts=new_wm, last_seen_row_ts=max_ts, now=self.clock(),
                                     rows=res.rows, new_fills=res.new_fills, bootstrap=bootstrap)
        res.ok = True
        self.health.resolve(w.address, ["poll_failure", "gap"],
                            extra=f"Backfill complete: {res.rows} row(s) read, {res.new_fills} new fill(s) stored.")
        log.info("poll %s: %s (rows=%d pages=%d from %s%s)", w.label, res.outcome, res.rows, res.pages,
                 render.utc(start), ", bootstrap" if bootstrap else "")
        return res

    def _failed(self, w: WalletConfig, res: PollResult, kind: str, detail: str, last_cursor: str | None,
                watermark: int | None, *, min_occ: int) -> PollResult:
        res.error, res.error_class = detail, kind
        n = self.store.mark_poll_failure(w.address, now=self.clock(), error=f"{kind}: {detail}",
                                         last_cursor=last_cursor, new_fills=res.new_fills)
        self.health.problem(w.address, "poll_failure", f"{detail} [consecutive failures: {n}]", error_class=kind,
                            min_occurrences=min_occ, watermark_ts=watermark)
        log.warning("poll %s FAILED (%s, %d consecutive): %s; state not advanced", w.label, kind, n, detail)
        return res
