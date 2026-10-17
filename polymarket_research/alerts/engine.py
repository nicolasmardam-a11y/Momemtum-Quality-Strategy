"""One monitoring cycle and the foreground loop.

cycle = status check -> poll every wallet -> group fills -> evaluate bets
        (enrich + create alerts) -> stale check -> digest
Notifications are delivered by the Dispatcher (a separate thread in loop mode),
so a slow or failing channel never delays polling.
"""
from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from . import DISCLAIMER, grouping, render, rules
from .config import Config, WalletConfig
from .dispatch import Dispatcher
from .enrich import Enricher
from .health import HealthMonitor
from .http_client import DataError
from .notify import Notifier
from .poller import Poller, PollResult
from .sources import Sources
from .store import Store

log = logging.getLogger("alerts.engine")


@dataclass
class CycleReport:
    started_at: float
    polls: list[PollResult] = field(default_factory=list)
    status: dict | None = None
    status_error: str | None = None
    bets_touched: int = 0
    alerts_created: int = 0
    alerts_suppressed: int = 0

    @property
    def all_ok(self) -> bool:
        return all(p.ok for p in self.polls) and self.status_error is None


class Engine:
    def __init__(self, cfg: Config, store: Store, sources: Sources, notifiers: dict[str, Notifier], *,
                 clock: Callable[[], float] = time.time, forced_backfill_hours: float | None = None) -> None:
        self.cfg, self.store, self.sources, self.notifiers, self.clock = cfg, store, sources, notifiers, clock
        self.started_at = clock()
        self.forced_backfill_hours = forced_backfill_hours
        self.health = HealthMonitor(store, cfg, notifiers, clock=clock)
        self.poller = Poller(store, sources, cfg, self.health, clock=clock)
        self.enricher = Enricher(sources, follow_usd=cfg.alerting.follow_usd,
                                 taker_crosscheck=cfg.alerting.taker_crosscheck, clock=clock)
        self.dispatcher = Dispatcher(store, notifiers, cfg, clock=clock, on_problem=self._delivery_problem)
        store.upsert_wallets(cfg.wallets, self.started_at)

    def _delivery_problem(self, scope: str, kind: str, detail: str) -> None:
        ch = scope.split(":", 1)[1] if scope.startswith("notify:") else None
        self.health.problem(scope, kind, detail, error_class="notify", exclude_channels=[ch] if ch else [])

    # ------------------------------------------------------------------ cycle

    def check_status(self, rep: CycleReport) -> float | None:
        if not self.cfg.poll.status_check:
            return None
        try:
            st = self.sources.status()
        except DataError as e:
            rep.status_error = str(e)
            self.health.problem("data-api", "status_unavailable", f"/v2/status failed: {e}", error_class=e.kind,
                                min_occurrences=2)
            return None
        rep.status = st
        self.health.check_status(st)
        return float(st["lag_seconds"]) if st.get("lag_seconds") is not None else None

    def run_cycle(self) -> CycleReport:
        rep = CycleReport(started_at=self.clock())
        lag = self.check_status(rep)
        for w in self.cfg.wallets:
            if w.enabled:
                rep.polls.append(self.poller.poll(w, status_lag_s=lag, forced_backfill_hours=self.forced_backfill_hours))
        self.forced_backfill_hours = None    # --backfill-hours applies to the first cycle only
        rep.bets_touched = len(grouping.assign_pending(self.store, self.cfg.grouping.gap_minutes * 60, self.clock()))
        created, suppressed = self.evaluate_bets()
        rep.alerts_created, rep.alerts_suppressed = created, suppressed
        self.health.check_stale(self.started_at)
        self.health.maybe_digest()
        return rep

    # ------------------------------------------------------------------ bets -> alerts

    def evaluate_bets(self) -> tuple[int, int]:
        """Turn changed bets into alerts. Freshest first; at most max_enrichments_per_cycle
        enrichments per cycle (the rest stay queued with needs_eval=1 for the next cycle)."""
        created = suppressed = 0
        budget = self.cfg.alerting.max_enrichments_per_cycle
        for bet in self.store.q("SELECT * FROM bets WHERE needs_eval = 1 ORDER BY last_ts DESC, bet_id"):
            try:
                w = self.cfg.wallet(bet["wallet"])
            except KeyError:
                self._set_bet(bet["bet_id"], bet["alert_state"])
                continue
            if bet["alert_state"] == "alerted":
                self._set_bet(bet["bet_id"], "alerted")     # one alert per bet; growth shows in the digest
                continue
            now = self.clock()
            d = rules.decide(bet, w, self.cfg, now)
            if d.action == "skip":
                state = "below_threshold" if d.reason.startswith("below threshold") else bet["alert_state"]
                self._set_bet(bet["bet_id"], state)
            elif d.action == "suppress":
                if bet["alert_state"] != "suppressed":
                    payload = {"bet": dict(bet), "reason": d.reason, "qualified_because": d.qualified_because}
                    text = (f"[suppressed] {w.label} {bet['side']} {bet['outcome']} on {bet['title']}: "
                            f"${bet['usdc_size']:,.2f} executed {render.utc(bet['first_ts'])}; {d.reason}")
                    if self.store.create_alert(dedupe_key=f"bet:{bet['bet_id']}:suppressed", kind="BET",
                                               label=rules.LABEL_NEW, text=text, payload=payload, now=now,
                                               channels=[], wallet=w.address, bet_id=bet["bet_id"],
                                               status="suppressed", suppressed_reason=d.reason) is not None:
                        suppressed += 1
                self._set_bet(bet["bet_id"], "suppressed")
            else:
                cap = self.cfg.alerting.max_alerts_per_wallet_per_hour
                recent = self.store.count("alerts", "kind = 'BET' AND wallet = ? AND status != 'suppressed' "
                                                    "AND created_at >= ?", (w.address, now - 3600))
                if recent >= cap:
                    self._cap_notice(w, now, cap)
                    reason = f"wallet alert cap: {recent} alerts for {w.label} in the last hour (max {cap})"
                    if self.store.create_alert(dedupe_key=f"bet:{bet['bet_id']}:suppressed", kind="BET",
                                               label=rules.LABEL_NEW, text=f"[suppressed] {reason}",
                                               payload={"bet": dict(bet), "reason": reason}, now=now, channels=[],
                                               wallet=w.address, bet_id=bet["bet_id"], status="suppressed",
                                               suppressed_reason=reason) is not None:
                        suppressed += 1
                    self._set_bet(bet["bet_id"], "suppressed")
                    continue
                if budget <= 0:
                    continue                                 # deferred: stays needs_eval=1
                budget -= 1
                if self._alert(bet, w, d) is not None:
                    created += 1
                self._set_bet(bet["bet_id"], "alerted")
        return created, suppressed

    def _cap_notice(self, w: WalletConfig, now: float, cap: int) -> None:
        hour = int(now // 3600)
        text = (f"[ALERT CAP] {w.label} ({render.short(w.address)}) produced more than {cap} qualifying bets in the "
                f"last hour. Further bets this hour are recorded in the database but not sent (see the digest). "
                f"Consider raising min_usdc for this wallet.")
        self.store.create_alert(dedupe_key=f"cap:{w.address}:{hour}", kind="NOTICE", label="ALERT CAP", text=text,
                                payload={"wallet": w.address, "cap": cap, "hour": hour}, now=now,
                                channels=list(self.notifiers), wallet=w.address)

    def _set_bet(self, bet_id: str, state: str) -> None:
        self.store.conn.execute("UPDATE bets SET needs_eval = 0, alert_state = ? WHERE bet_id = ?", (state, bet_id))

    def _alert(self, bet, w: WalletConfig, d: rules.Decision) -> int | None:
        key = f"bet:{bet['bet_id']}"
        if self.store.q1("SELECT 1 FROM alerts WHERE dedupe_key = ?", (key,)):
            return None
        fills = self.store.q("SELECT * FROM fills WHERE bet_id = ? ORDER BY ts, fill_id", (bet["bet_id"],))
        en = self.enricher.enrich(bet, fills)
        for e in en.errors:
            self.health.problem(e.source, "enrichment", f"alert enrichment failed: {e}", error_class=e.kind,
                                min_occurrences=self.cfg.health.notify_after_consecutive_failures)
        if not en.errors:
            for src in {"data-api", "gamma", "clob"}:
                self.health.resolve(src, ["enrichment"])
        built = self.clock()
        newest = fills[-1]
        detection_lag = max(0.0, newest["first_seen_at"] - newest["ts"])
        signal_age = max(0.0, built - bet["first_ts"])
        label, passed, failed = rules.copy_candidate(en.data, w, self.cfg, detection_lag)
        prior_note = None
        ex = en.data.get("exposure")
        if bet["kind"] == "new_position" and ex:
            extra = ex["outcome_current_size"] - bet["shares"]
            if extra > max(1.0, 0.01 * bet["shares"]):
                prior_note = (f"Positions API shows {extra:,.2f} sh on this outcome beyond this bet "
                              "(held before monitoring began, or transferred in): treated as an addition.")
                self.store.conn.execute("UPDATE bets SET kind = 'addition' WHERE bet_id = ?", (bet["bet_id"],))
                bet = self.store.q1("SELECT * FROM bets WHERE bet_id = ?", (bet["bet_id"],))
                d.qualified_because = [r for r in d.qualified_because if not r.startswith("first BUY run")] + [
                    "addition to an existing position (holdings that predate this monitor, per the positions API)"]
        delayed = None
        if detection_lag > max(300.0, 10 * self.cfg.poll.interval_seconds):
            delayed = (f"detected {render.dur(detection_lag)} after execution (monitoring gap or backfill); "
                       "the opportunity, if any, is likely gone")
        payload = {
            "label": label,
            "disclaimer": DISCLAIMER,
            "wallet": {"address": w.address, "label": w.label, "cluster_id": w.cluster_id,
                       "cluster_confidence": w.cluster_confidence, "cluster_note": w.cluster_note},
            "bet": dict(bet),
            "enrichment": en.data,
            "qualified_because": d.qualified_because,
            "rules_passed": passed,
            "rules_failed": failed,
            "first_fill_detected_at": bet["first_seen_at"],
            "detected_at": newest["first_seen_at"],
            "detection_lag_s": round(detection_lag, 3),
            "signal_age_s": round(signal_age, 3),
            "alert_built_at": built,
            "delayed_note": delayed,
            "prior_holdings_note": prior_note,
        }
        text = render.bet_alert(payload)
        return self.store.create_alert(dedupe_key=key, kind="BET", label=label, text=text, payload=payload,
                                       now=built, channels=list(self.notifiers), wallet=w.address,
                                       bet_id=bet["bet_id"])

    # ------------------------------------------------------------------ loop

    def run_loop(self, stop: threading.Event, *, max_cycles: int | None = None,
                 sleep_jitter: Callable[[], float] | None = None) -> int:
        """Foreground loop until ``stop`` is set (Ctrl-C/SIGTERM) or max_cycles is reached."""
        p = self.cfg.poll
        jitter = sleep_jitter or (lambda: random.uniform(-p.jitter_seconds, p.jitter_seconds))
        cycles = 0
        while not stop.is_set():
            t0 = time.monotonic()
            try:
                rep = self.run_cycle()
                log.info("cycle %d: %d/%d wallet polls ok, %d new alert(s), %d suppressed", cycles + 1,
                         sum(1 for x in rep.polls if x.ok), len(rep.polls), rep.alerts_created, rep.alerts_suppressed)
            except Exception:
                # Engine bugs are logged with traceback and the loop continues; poll state was not advanced
                # for any wallet whose poll did not complete.
                log.exception("cycle failed")
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            wait = max(1.0, p.interval_seconds + jitter() - (time.monotonic() - t0))
            stop.wait(wait)
        return cycles
