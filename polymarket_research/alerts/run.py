"""Command line entry point.

    cd polymarket_research
    python -m alerts.run --config alerts/config.example.yaml --once
    python -m alerts.run --config alerts/config.example.yaml              # foreground loop, Ctrl-C to stop
    python -m alerts.run --config alerts/config.example.yaml --report     # print stored state, no network

This runs in the foreground only. It does not daemonise, install a service or
schedule itself; see README "Running continuously" for those options.

Exit codes (useful under cron): 0 all polls ok, 2 configuration error,
3 at least one data problem in a --once run.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time

from . import DISCLAIMER, render
from .config import ConfigError, load_config, resolve_path
from .dispatch import DispatcherThread
from .engine import Engine
from .http_client import HttpClient
from .notify import NotifierConfigError, build_notifiers
from .sources import Sources
from .store import Store

log = logging.getLogger("alerts")


def report(store: Store) -> str:
    out = ["poll_state:"]
    for r in store.q("SELECT p.*, w.label FROM poll_state p LEFT JOIN wallets w ON w.address = p.wallet ORDER BY w.label"):
        out.append(f"  {r['label'] or r['wallet']}: watermark {render.utc(r['watermark_ts'])}, last success "
                   f"{render.utc(r['last_success_at'])}, consecutive failures {r['consecutive_failures']}, "
                   f"polls ok/failed {r['polls_ok']}/{r['polls_failed']}, last error {r['last_error'] or '-'}")
    out.append(f"fills: {store.count('fills')}  bets: {store.count('bets')}  alerts: {store.count('alerts')}")
    for r in store.q("SELECT status, COUNT(*) n FROM deliveries GROUP BY status"):
        out.append(f"  deliveries {r['status']}: {r['n']}")
    open_ev = store.q("SELECT * FROM health_events WHERE resolved_at IS NULL ORDER BY first_at")
    out.append(f"open data problems: {len(open_ev)}")
    for e in open_ev:
        out.append(f"  {e['scope']} {e['kind']}/{e['error_class']} x{e['occurrences']} since {render.utc(e['first_at'])}: "
                   f"{e['detail'][:200]}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m alerts.run", description="Read-only Polymarket wallet bet alerts")
    ap.add_argument("--config", required=True, help="YAML config (see alerts/config.example.yaml)")
    ap.add_argument("--once", action="store_true", help="run one cycle, deliver notifications, exit")
    ap.add_argument("--backfill-hours", type=float, default=None,
                    help="first cycle re-reads at least this many hours (idempotent; old bets are suppressed)")
    ap.add_argument("--db", default=None, help="SQLite path (default: storage.db_path from the config)")
    ap.add_argument("--interval", type=float, default=None, help="override poll.interval_seconds")
    ap.add_argument("--max-cycles", type=int, default=None, help="stop the loop after N cycles")
    ap.add_argument("--dry-run", action="store_true", help="console/file notifiers only, even if others are enabled")
    ap.add_argument("--report", action="store_true", help="print stored poll/health state and exit (no network)")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.Formatter.converter = time.gmtime
    try:
        cfg = load_config(args.config)
        if args.interval is not None:
            import dataclasses
            cfg = dataclasses.replace(cfg, poll=dataclasses.replace(cfg.poll, interval_seconds=args.interval))
        db_path = str(resolve_path(args.db or cfg.storage.db_path))
        store = Store(db_path)
        if args.report:
            print(report(store))
            return 0
        notifiers = build_notifiers(cfg, dry_run=args.dry_run)
    except (ConfigError, NotifierConfigError) as e:
        print(f"configuration error: {e}", file=sys.stderr)
        return 2

    http = HttpClient(timeout=cfg.poll.request_timeout_seconds, retries=cfg.poll.retries)
    sources = Sources(http, cache_bust=cfg.poll.cache_bust)
    engine = Engine(cfg, store, sources, notifiers, forced_backfill_hours=args.backfill_hours)
    log.info("read-only monitor: %d wallet(s), channels %s, db %s. No orders are placed. %s",
             sum(1 for w in cfg.wallets if w.enabled), sorted(notifiers), db_path, DISCLAIMER)

    if args.once:
        engine.dispatcher.recover_inflight()
        rep = engine.run_cycle()
        stats = engine.dispatcher.flush(max_items=500, deadline_s=60)
        for p in rep.polls:
            log.info("  %s: %s", cfg.wallet(p.wallet).label, p.outcome)
        log.info("cycle done: %d alert(s) created, %d suppressed; deliveries %s", rep.alerts_created,
                 rep.alerts_suppressed, stats)
        pending = store.count("deliveries", "status = 'pending'")
        if pending:
            log.warning("%d delivery(ies) still pending (rate limit/backoff); they are kept and sent next run", pending)
        return 0 if rep.all_ok else 3

    stop = threading.Event()

    def _stop(signum, _frame):
        log.info("signal %s: stopping after the current cycle", signum)
        stop.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    disp = DispatcherThread(db_path, notifiers, cfg, stop)
    disp.start()
    log.info("foreground loop: every %.0fs +/- %.0fs jitter; Ctrl-C to stop", cfg.poll.interval_seconds,
             cfg.poll.jitter_seconds)
    try:
        engine.run_loop(stop, max_cycles=args.max_cycles)
    finally:
        stop.set()
        disp.join(timeout=30)
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
