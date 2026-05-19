"""Central hard kill-switch battery.

run_all() returns {"checks": [...], "all_passed": bool}. If all_passed is
False the orchestrator MUST NOT submit any order. Every enumerated hard kill
switch from the spec is represented; checks that are not applicable in a given
mode (e.g. reconciliation in signal_only) are reported as 'skipped' and do not
fail the battery.
"""
from __future__ import annotations


def _chk(name, passed, detail, severity="HARD", skipped=False):
    return {"name": name, "passed": bool(passed) if not skipped else True,
            "skipped": skipped, "severity": severity, "detail": str(detail)}


def run_all(cfg, ctx: dict) -> dict:
    mode = ctx["mode"]
    checks = []
    needs_ib = mode in ("preview", "paper_trade")

    # --- config / live-trading safety ---
    checks.append(_chk("no_live_trading",
                        cfg.safety.get("live_trading_enabled") is False
                        and cfg.safety.get("paper_only") is True
                        and mode != "live",
                        f"live_trading_enabled={cfg.safety.get('live_trading_enabled')}, "
                        f"paper_only={cfg.safety.get('paper_only')}, mode={mode}"))
    checks.append(_chk("refuse_market_orders",
                        cfg.safety.get("refuse_market_orders") is True
                        and str(cfg.order.get("type")).upper() == "LMT",
                        f"order.type={cfg.order.get('type')}"))

    # --- IBKR connection / account ---
    checks.append(_chk("ibkr_connected", ctx.get("ib_connected", False),
                        ctx.get("ib_detail", "not connected"),
                        skipped=not needs_ib))
    acct = ctx.get("account")
    prefix = str(cfg.ibkr["paper_account_prefix"]).upper()
    checks.append(_chk("paper_account_only",
                        bool(acct) and str(acct).startswith(prefix),
                        f"account={acct}, required prefix={prefix}",
                        skipped=not needs_ib))
    checks.append(_chk("paper_port_4002", cfg.ibkr["paper_port"] == 4002,
                        f"paper_port={cfg.ibkr['paper_port']}"))

    # --- exposure overlay ---
    ov = ctx.get("exposure_info", {})
    exp = ov.get("exposure")
    lo, hi = cfg.risk["exposure_min"], cfg.risk["exposure_max"]
    checks.append(_chk("exposure_in_range",
                        exp is not None and lo <= exp <= hi,
                        f"exposure={exp}, range=[{lo},{hi}]"))
    chg = ov.get("exposure_change")
    thr = cfg.risk["exposure_change_threshold"]
    checks.append(_chk("exposure_change_within_threshold",
                        chg is None or chg <= thr,
                        f"day-over-day change={chg}, threshold={thr} "
                        f"(None=no prior state)"))

    # --- target portfolio integrity ---
    summ = ctx.get("target_summary", {})
    tdf = ctx.get("targets")
    have_targets = tdf is not None and len(tdf) > 0
    checks.append(_chk("portfolio_drift_calc_ok", have_targets and bool(summ),
                        f"n_targets={0 if tdf is None else len(tdf)}"))
    checks.append(_chk("expected_constituent_count",
                        summ.get("n_constituents") == cfg.risk["expected_n_constituents"],
                        f"n={summ.get('n_constituents')}, "
                        f"expected={cfg.risk['expected_n_constituents']}"))
    checks.append(_chk("no_projected_cash_deficit",
                        not summ.get("projected_cash_deficit", False),
                        f"cash_eur={summ.get('cash_eur')}"))
    checks.append(_chk("no_stale_prices",
                        len(summ.get("stale_prices", [])) == 0,
                        f"stale={summ.get('stale_prices')}"))

    # --- registry: missing / duplicate conId, currency match ---
    reg = ctx.get("registry")
    secm = ctx.get("security_master")  # dict ticker->currency
    miss, dup, ccy_mismatch = [], [], []
    if reg is not None and have_targets:
        seen = {}
        for _, r in tdf.iterrows():
            tk = r["ticker"]
            if not reg.has(tk):
                miss.append(tk)
                continue
            cid = int(reg.get(tk)["conId"])
            if cid in seen:
                dup.append((cid, seen[cid], tk))
            seen[cid] = tk
            if secm and tk in secm and secm[tk] and reg.get(tk)["currency"] != secm[tk]:
                ccy_mismatch.append((tk, reg.get(tk)["currency"], secm[tk]))
    checks.append(_chk("no_missing_conid", not miss, f"missing={miss}"))
    checks.append(_chk("no_duplicate_conid", not dup, f"dups={dup}"))
    checks.append(_chk("no_currency_mismatch", not ccy_mismatch,
                        f"mismatch={ccy_mismatch}"))

    # --- FX coverage ---
    fxmiss = ctx.get("fx_missing", [])
    checks.append(_chk("fx_rates_available", not fxmiss, f"missing={fxmiss}"))

    # --- corporate actions (state-file driven; empty by default) ---
    ca = ctx.get("corp_actions", [])
    checks.append(_chk("no_unresolved_corporate_action", not ca,
                        f"unresolved={ca}"))

    # --- reconciliation ---
    rec = ctx.get("reconciliation", {})
    checks.append(_chk("position_reconciliation",
                        not rec.get("mismatch", False),
                        rec.get("detail", "ok"),
                        skipped=not needs_ib or rec.get("skipped", False)))

    # --- order sizing sanity ---
    tr = ctx.get("trades")
    if tr is not None and mode in ("preview", "paper_trade"):
        checks.append(_chk("orders_above_min_size", len(tr) > 0 or ctx.get("no_trades_ok", False),
                            f"n_trades={0 if tr is None else len(tr)}",
                            severity="SOFT"))

    hard_fail = [c for c in checks
                 if not c["skipped"] and not c["passed"] and c["severity"] == "HARD"]
    return {
        "mode": mode,
        "checks": checks,
        "all_passed": len(hard_fail) == 0,
        "hard_failures": [c["name"] for c in hard_fail],
    }
