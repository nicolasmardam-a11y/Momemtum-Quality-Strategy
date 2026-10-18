"""CLI: python -m paper_fav.run --config paper_fav/config.example.yaml {scan,resolve,report,all} [--dry-run]

Run `all` hourly (cron or systemd timer). Read-only: nothing here can place an order.
Exit codes: 0 ok, 2 data problem (reported separately from 'no new signals').
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from alerts.notify import ConsoleNotifier, EmailNotifier, FileNotifier, Message, NotifyError, TelegramNotifier

from .client import Client, DataError
from .ledger import Ledger
from .resolve import resolve
from .scan import scan
from .stats import scorecard, subsets, summarise

ROOT = Path(__file__).resolve().parents[1]


def build_notifiers(ncfg: dict, dry_run: bool) -> list:
    out = []
    if ncfg.get("console", True) or dry_run:
        out.append(ConsoleNotifier())
    if ncfg.get("file"):
        out.append(FileNotifier(ROOT / ncfg["file"]))
    if dry_run:
        return out
    env = os.environ
    if ncfg.get("telegram"):
        missing = [k for k in ("PM_ALERT_TELEGRAM_BOT", "PM_ALERT_TELEGRAM_CHAT") if not env.get(k)]
        if missing:
            raise SystemExit(f"telegram enabled but {missing} not set")
        out.append(TelegramNotifier(env["PM_ALERT_TELEGRAM_BOT"], env["PM_ALERT_TELEGRAM_CHAT"]))
    if ncfg.get("email"):
        missing = [k for k in ("PM_ALERT_SMTP_HOST", "PM_ALERT_SMTP_FROM", "PM_ALERT_SMTP_TO") if not env.get(k)]
        if missing:
            raise SystemExit(f"email enabled but {missing} not set")
        out.append(EmailNotifier(env["PM_ALERT_SMTP_HOST"], int(env.get("PM_ALERT_SMTP_PORT") or 587),
                                 env.get("PM_ALERT_SMTP_USER"), env.get("PM_ALERT_SMTP_PASSWORD"),
                                 env["PM_ALERT_SMTP_FROM"],
                                 [x.strip() for x in env["PM_ALERT_SMTP_TO"].split(",") if x.strip()],
                                 use_ssl=env.get("PM_ALERT_SMTP_SSL") == "1"))
    return out


def notify(ledger: Ledger, notifiers: list, key: str, kind: str, text: str, payload: dict | None = None) -> None:
    """Send once per dedupe key. A failed channel is logged, never fatal to the run."""
    if not ledger.claim_notice(key):
        return
    msg = Message(alert_id=int(hashlib.sha1(key.encode()).hexdigest()[:8], 16), dedupe_key=key, kind=kind,
                  label=kind.upper(), text=text, payload=payload or {})
    for n in notifiers:
        try:
            n.send(msg)
        except NotifyError as e:
            print(f"notify via {getattr(n, 'name', n)} failed: {e}", file=sys.stderr)


def signal_text(s: dict) -> str:
    link = f"https://polymarket.com/event/{s['event_slug']}" + (f"/{s['market_slug']}" if s.get("market_slug") else "")
    return (f"PAPER SIGNAL (no order placed): buy '{s['outcome']}' in \"{s['question']}\"\n"
            f"ask {s['best_ask']:.3f} | mid {s['mid']:.4f} | all-in {s['all_in']:.4f}/share incl. fee "
            f"(rate {s['fee_rate']}) | paper stake ${s['stake_usd']:.0f} = {s['shares']:.1f} shares\n"
            f"spread {100 * s['spread']:.1f}c | ask depth within 1c ${s['depth_1c_usd']:.0f} | "
            f"{'liquid' if s['liquid'] else 'thin'} | {'tight' if s.get('tight') else 'WIDE spread'} | {s['category']}"
            f"{' | EXACT-SCORE (tracked separately)' if s['exact_score'] else ''}\n"
            f"anchor (scheduled end / kick-off) {s['anchor_ts']} | {link}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["scan", "resolve", "report", "all"])
    ap.add_argument("--config", default=str(ROOT / "paper_fav/config.example.yaml"))
    ap.add_argument("--db", help="override the ledger path")
    ap.add_argument("--dry-run", action="store_true", help="console output only")
    a = ap.parse_args(argv)
    cfg = yaml.safe_load(Path(a.config).read_text())
    ledger = Ledger(a.db or ROOT / cfg["db"])
    ncfg = cfg.get("notifications") or {}
    notifiers = build_notifiers(ncfg, a.dry_run)
    client = Client()
    now = datetime.now(timezone.utc)
    rc = 0

    if a.command in ("scan", "all"):
        rid = ledger.start_run("scan")
        try:
            st = scan(ledger, client, cfg, now)
        except DataError as e:
            ledger.finish_run(rid, ok=False, errors=[str(e)])
            notify(ledger, notifiers, f"problem:scan:{now:%Y%m%d%H}", "data_problem",
                   f"DATA PROBLEM: scan failed ({e}). Nothing was decided in this run; markets still inside their "
                   f"decision window will be retried next run.")
            rc = 2
        else:
            ledger.finish_run(rid, ok=True, scanned=st["scanned"], due=st["due"], new_signals=len(st["new_signals"]))
            print(f"scan {now:%Y-%m-%d %H:%M}Z: {st['scanned']} markets scanned, {st['due']} due, "
                  f"outcomes {st['status']}")
            if ncfg.get("notify_each_signal", True):
                for s in st["new_signals"]:
                    notify(ledger, notifiers, f"signal:{s['condition_id']}", "paper_signal", signal_text(s), s)

    if a.command in ("resolve", "all"):
        rid = ledger.start_run("resolve")
        try:
            n = resolve(ledger, client, now)
        except DataError as e:
            ledger.finish_run(rid, ok=False, errors=[str(e)])
            notify(ledger, notifiers, f"problem:resolve:{now:%Y%m%d%H}", "data_problem",
                   f"DATA PROBLEM: resolution check failed ({e}). Open positions are unchanged; retried next run.")
            rc = 2
        else:
            ledger.finish_run(rid, ok=True, resolved=n)
            print(f"resolve: {n} positions settled")

    rows = [dict(r) for r in ledger.signals()]
    for name, group in subsets(rows).items():
        if name not in ("all", "core"):
            continue
        s = summarise(group, cfg, name)
        if s["kill"]:
            notify(ledger, notifiers, f"kill:{name}", "kill", f"KILL RULE TRIGGERED on '{name}': realised losses "
                   f"exceed {cfg['kill']['ratio']} x the price-implied losses (k = {s['k']:.2f}). Do not trade this "
                   f"version of the rule.\n\n" + scorecard(rows, cfg))
    if a.command == "report":
        print(scorecard(rows, cfg))
    elif now.hour >= int(ncfg.get("daily_scorecard_utc_hour", 8)):
        notify(ledger, notifiers, f"scorecard:{now:%Y-%m-%d}", "scorecard", scorecard(rows, cfg))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
