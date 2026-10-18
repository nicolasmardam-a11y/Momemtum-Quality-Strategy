"""Plain-text rendering of notifications (Telegram/email/console share one format)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import DISCLAIMER

MAX_TEXT = 3900   # Telegram sendMessage caps text at 4096 characters


def utc(ts: float | int | None) -> str:
    if ts is None:
        return "n/a"
    return datetime.fromtimestamp(float(ts), timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def short(addr: str) -> str:
    return f"{addr[:6]}…{addr[-4:]}" if addr and len(addr) > 12 else addr


def money(x: Any) -> str:
    return "n/a" if x is None else f"${float(x):,.2f}"


def num(x: Any, nd: int = 4) -> str:
    return "n/a" if x is None else f"{float(x):,.{nd}f}"


def dur(s: float | None) -> str:
    if s is None:
        return "n/a"
    s = max(0.0, float(s))
    if s < 120:
        return f"{s:.0f}s"
    if s < 7200:
        return f"{s / 60:.1f} min"
    return f"{s / 3600:.1f} h"


def bet_alert(p: dict) -> str:
    """Render a bet alert from its stored payload."""
    w, bet, en = p["wallet"], p["bet"], p["enrichment"]
    f, mk, ms = en.get("fills") or {}, en.get("market") or {}, en.get("market_state") or {}
    book, det, fee, ex = en.get("book") or {}, en.get("deterioration") or {}, en.get("follower_fee") or {}, en.get("exposure")
    kind = {"new_position": "new position", "addition": "addition to position"}.get(bet["kind"], bet["kind"])
    lines = [
        f"[{p['label']}] {kind} | {w['label']} ({short(w['address'])})",
        DISCLAIMER if p["label"] != "COPY-CANDIDATE" else
        "COPY-CANDIDATE per YOUR configured rules only; no copy signal has been validated by this research.",
    ]
    if p.get("delayed_note"):
        lines.append(f"DELAYED: {p['delayed_note']}")
    lines += [
        ("Market: [COMBO: multi-leg RFQ position, not a single order-book market] " if en.get("combo") else "Market: ")
        + f"{mk.get('question') or bet.get('title')}",
        # The outcome shown is Gamma's name for the traded token when known (enrich.py cross-checks it
        # against the Data API label and reports any disagreement under "Enrichment errors").
        f"Event: {mk.get('event_title') or 'n/a'} | Outcome: {mk.get('outcome') or bet.get('outcome') or 'n/a'}"
        f" | Side: {bet['side']}",
        f"Filled: {num(f.get('shares'), 2)} sh, avg {num(f.get('avg_fill_price'))}, spent {money(f.get('usdc_spent'))}"
        f" ({f.get('n_fills')} fills; incl. fees eff. {num(f.get('effective_price_incl_fees'))})",
        f"Maker/taker: taker {num(f.get('taker_shares'), 2)} / maker {num(f.get('maker_shares'), 2)} / "
        f"unknown {num(f.get('unknown_role_shares'), 2)} sh; wallet fees {money(f.get('wallet_fees_usdc'))}",
        f"Executed (UTC): {utc(bet['first_ts'])} -> {utc(bet['last_ts'])}",
        f"Detected (UTC): {utc(p['detected_at'])} | detection lag {dur(p['detection_lag_s'])} "
        f"| alert built {utc(p['alert_built_at'])}",
    ]
    if book.get("available"):
        lines.append(
            f"Book now ({utc(book.get('fetched_at'))}): bid {num(book.get('best_bid'), 3)} / ask {num(book.get('best_ask'), 3)}"
            f", spread {num(book.get('spread_cents'), 1)}c; ask depth <=1c {money(book.get('ask_depth_1c_usd'))}"
            f" ({num(book.get('ask_depth_1c_shares'), 0)} sh), <=5c {money(book.get('ask_depth_5c_usd'))};"
            f" bid depth <=1c {money(book.get('bid_depth_1c_usd'))}, <=5c {money(book.get('bid_depth_5c_usd'))}")
    else:
        lines.append(f"Book: unavailable ({book.get('reason', 'not fetched')})")
    lines.append(f"Price deterioration vs wallet avg: {num(det.get('deterioration_cents'), 2)}c "
                 f"({num(det.get('deterioration_pct'), 2)}%)")
    lines.append(f"Follower taker fee at that price: {num(fee.get('fee_cents_per_share'), 3)}c/sh "
                 f"({num(fee.get('fee_pct_of_notional'), 2)}% of notional; {money(fee.get('follow_fee_usd'))} on a "
                 f"{money(fee.get('follow_usd'))} follow; rate {fee.get('fee_rate')} via {fee.get('basis')})")
    if ex:
        evx = ex.get("event") or {}
        lines.append(f"Wallet exposure: this outcome {num(ex.get('outcome_current_size'), 2)} sh; market value "
                     f"{money(ex['market']['current_value_usdc'])} (cost {money(ex['market']['entry_cost_usdc'])}); "
                     f"event value {money(evx.get('current_value_usdc'))} across {evx.get('markets', 'n/a')} market(s)")
    else:
        lines.append("Wallet exposure: unavailable")
    if p.get("prior_holdings_note"):
        lines.append(p["prior_holdings_note"])
    lines.append(
        f"Market state: closed={ms.get('closed')} accepting_orders={ms.get('accepting_orders')} "
        f"in_play={ms.get('in_play')} ({ms.get('in_play_basis')}); gameStartTime={ms.get('game_start_time') or 'n/a'}; "
        f"secondsDelay={ms.get('seconds_delay')}")
    conf = w.get("cluster_confidence", "none")
    lines.append(f"Cluster: {w.get('cluster_id') or 'none'} (confidence: {conf})"
                 + (f" - {w['cluster_note']}" if w.get("cluster_note") else ""))
    lines.append("Why it qualified: " + "; ".join(p.get("qualified_because") or []))
    rules_line = ("Copy rules passed: " + ", ".join(p["rules_passed"])) if p["label"] == "COPY-CANDIDATE" else (
        "Copy rules not met: " + ", ".join(p.get("rules_failed") or []))
    lines.append(rules_line)
    if en.get("enrichment_errors"):
        lines.append("Enrichment errors: " + "; ".join(en["enrichment_errors"])[:500])
    lines.append(f"Link: {mk.get('market_url') or mk.get('event_url') or 'n/a'}")
    return clip("\n".join(lines))


def _s(x: Any, nd: int | None = None) -> str:
    """Defensive formatting for the fallback paths: never raises."""
    try:
        return "n/a" if x is None else (f"{float(x):,.{nd}f}" if nd is not None else str(x))
    except (TypeError, ValueError):
        return str(x)


def _t(ts: Any) -> str:
    try:
        return utc(ts)
    except (TypeError, ValueError, OverflowError, OSError):
        return str(ts)


def fallback_bet_alert(bet: dict, wallet_label: str, address: str, error: str) -> str:
    """Minimal alert from stored bet facts only, used when the full alert could not be built."""
    shares, notional = bet.get("shares"), bet.get("notional_usdc")
    try:
        avg = float(notional) / float(shares) if shares else None
    except (TypeError, ValueError):
        avg = None
    link = f"https://polymarket.com/event/{bet['event_slug']}" if bet.get("event_slug") else "n/a"
    return clip("\n".join([
        "[NEW BET DETECTED] [ALERT RENDERING FAILED: enrichment and book data omitted] | "
        f"{wallet_label} ({short(address)})",
        DISCLAIMER,
        f"Market: {_s(bet.get('title'))} | Outcome: {_s(bet.get('outcome'))} | Side: {_s(bet.get('side'))}",
        f"Filled: {_s(shares, 2)} sh, avg {_s(avg, 4)}, spent ${_s(bet.get('usdc_size'), 2)} "
        f"({_s(bet.get('n_fills'))} fills)",
        f"Executed (UTC): {_t(bet.get('first_ts'))} -> {_t(bet.get('last_ts'))}",
        f"Link: {link}",
        f"Error while building the full alert: {error[:300]}",
    ]))


def backfill_summary(items: list[tuple[dict, str, str]], now: float, max_age_minutes: float) -> str:
    """``items``: (bet, wallet_label, address) of qualifying bets suppressed as too old."""
    lines = [f"[BACKFILL SUMMARY] {len(items)} qualifying bet(s) were detected late (monitoring gap, outage or "
             f"--backfill-hours) and are older than max_alert_age_minutes={max_age_minutes:g}, so they were "
             "recorded but NOT alerted individually:"]
    for bet, label, addr in items[:10]:
        shares = bet.get("shares") or 0
        avg = bet["notional_usdc"] / shares if shares else None
        lines.append(f"- {label} ({short(addr)}): {bet['side']} {bet.get('outcome') or 'n/a'} on "
                     f"{bet.get('title') or bet.get('condition_id')} | {money(bet.get('usdc_size'))} for "
                     f"{num(shares, 2)} sh @ avg {num(avg)} | executed {utc(bet['first_ts'])} -> "
                     f"{utc(bet['last_ts'])} ({dur(now - bet['last_ts'])} before detection)")
    if len(items) > 10:
        lines.append(f"(+{len(items) - 10} more; see `python -m alerts.run --report` and the bets table)")
    lines.append("Prices have likely moved since; these are records, not signals.")
    return clip("\n".join(lines))


def rejected_rows(scope_label: str, rows: list[tuple[dict, list[str]]]) -> str:
    """Activity rows that failed validation and were quarantined instead of processed."""
    lines = [f"[DATA PROBLEM] rejected_rows / schema | {scope_label}",
             f"{len(rows)} activity row(s) of this wallet could not be parsed and were NOT processed (no bet alert "
             "will be sent for them). The wallet's other rows are processed normally; these rows are kept in "
             "the rejected_rows table for inspection:"]
    for r, problems in rows[:5]:
        r = r if isinstance(r, dict) else {"row": r}
        tx = str(r.get("transaction_hash") or "")
        lines.append(f"- {_s(r.get('type'))} {_s(r.get('side'))} {_s(r.get('size'))} sh @ {_s(r.get('price'))} "
                     f"(${_s(r.get('usdc_size'))}) on {_s(r.get('title'))!r} at {_t(r.get('timestamp'))}, "
                     f"tx {tx[:10]}…: {'; '.join(problems)[:200]}")
    if len(rows) > 5:
        lines.append(f"(+{len(rows) - 5} more)")
    return clip("\n".join(lines))


def data_problem(scope_label: str, kind: str, error_class: str | None, detail: str, *, first_at: float,
                 occurrences: int, watermark_ts: int | None, renotify: bool) -> str:
    head = "[DATA PROBLEM]" + (" (still ongoing)" if renotify else "")
    lines = [
        f"{head} {kind}{f' / {error_class}' if error_class else ''} | {scope_label}",
        f"Detail: {detail}",
        f"Since {utc(first_at)}; occurrences: {occurrences}.",
        "This is a data failure, NOT 'no new trades'. The poll state was not advanced.",
    ]
    if watermark_ts:
        lines.append(f"Last confirmed watermark: {utc(watermark_ts)}; the gap will be backfilled on recovery.")
    return clip("\n".join(lines))


def data_recovered(scope_label: str, kind: str, first_at: float, now: float, extra: str = "") -> str:
    return clip(f"[DATA RECOVERED] {kind} | {scope_label}\nProblem lasted {dur(now - first_at)} "
                f"(since {utc(first_at)}).{(' ' + extra) if extra else ''}")


def digest(d: dict) -> str:
    lines = [f"[DIGEST] {utc(d['from'])} -> {utc(d['to'])} | read-only monitor heartbeat",
             f"Wallets: {d['wallets']} | polls ok {d['polls_ok']} / failed {d['polls_failed']}",
             f"Fills stored: {d['fills_total']} ({', '.join(f'{k} {v}' for k, v in d['fills_by_type'].items()) or 'none'})",
             f"Bets: {', '.join(f'{k} {v}' for k, v in d['bets_by_kind'].items()) or 'none'}",
             f"Alerts: {', '.join(f'{k} {v}' for k, v in d['alerts_by_label'].items()) or 'none'}; "
             f"suppressed {d['alerts_suppressed']}; delivery failures {d['delivery_failures']}",
             f"Data problems opened: {d['problems_opened']}; still open: {d['problems_open']}",
             f"Most stale wallet: {d['most_stale']}"]
    if d.get("non_buy_summary"):
        lines.append("Sells/merges/redeems recorded (no buy alerts): " + "; ".join(d["non_buy_summary"])[:800])
    lines.append("No new trades is a normal outcome; data failures are reported separately as DATA PROBLEM.")
    return clip("\n".join(lines))


def clip(text: str) -> str:
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 20] + "\n…[truncated]"
