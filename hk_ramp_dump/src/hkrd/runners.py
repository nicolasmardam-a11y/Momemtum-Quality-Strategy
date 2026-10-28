"""Shared strategy runners used by run_backtests.py and run_holdout.py."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from . import pipeline as P
from . import plots
from . import strategies as S
from .backtest import (EventBacktester, ExecParams, Market, ShortParams, TradeRules, perf_stats,
                       portfolio_backtest, trade_stats)
from .hkex import tick_size_array


def build_market(cfg, inp, df):
    panel = inp["panel"]
    dates = pd.DatetimeIndex(sorted(panel["date"].unique()))
    codes = pd.Index(sorted(panel["code"].unique()))
    sh = P.shortable_wide(inp["ds"], dates, codes)
    lots = inp["universe"].set_index("code")["board_lot"].reindex(codes).fillna(1000).astype(int)
    spread = df.pivot(index="date", columns="code", values="spread_ar_20")
    return Market.from_panel(panel, sh, lots, spread)


def exec_from_cfg(cfg, **kw) -> ExecParams:
    ex = cfg["execution"]
    base = ExecParams(participation=0.02, impact_k=ex["impact_k"],
                      short_down_day_haircut=ex["short_fill_haircut_down_day"],
                      brokerage_bps=ex["brokerage_bps"], brokerage_min=ex["brokerage_min_hkd"])
    return replace(base, **kw)


def short_from_cfg(cfg, fee_mult=1.0) -> ShortParams:
    s = cfg["shorting"]
    return ShortParams(require_designated=s["require_designated_list"], fee_annual=s["borrow_fee_annual"],
                       fee_mult=fee_mult, locate_fail=s["locate_failure_prob"],
                       daily_recall=s["daily_recall_prob"])


def run_a(mkt, sig, lo, hi, cfg, hold, stop, nav=50e6, seed=0, fee_mult=1.0, **exkw):
    s = sig[(sig["date"] >= lo) & (sig["date"] <= hi)]
    bt = EventBacktester(mkt, TradeRules(side="short", hold_days=hold, stop_loss=stop, nav=nav,
                                         max_position_nav=cfg["portfolio"]["max_position_nav"],
                                         max_gross=cfg["portfolio"]["max_gross"],
                                         max_positions=cfg["portfolio"]["max_positions"]),
                         exec_from_cfg(cfg, **exkw), short_from_cfg(cfg, fee_mult), seed=seed)
    res = bt.run(s)
    d = res["daily"].loc[lo:hi]
    st = trade_stats(res["trades"])
    st.update({f"pf_{k}": v for k, v in perf_stats(d["ret"]).items()})
    st["avg_gross_deployed_hkd"] = float(d["gross_exposure"].mean())
    st["n_signals"] = int(len(s))
    f = res["failures"]
    st["failures"] = f["reason"].value_counts().to_dict() if len(f) else {}
    st["failed_execution_rate"] = float(len(f) / max(len(s), 1))
    # alerts repeat on consecutive days; count distinct stock-months as opportunities
    opp = s.assign(m=s["date"].dt.to_period("M"))[["code", "m"]].drop_duplicates()
    st["n_opportunities_stock_months"] = int(len(opp))
    if len(f):
        ff = f.assign(m=pd.to_datetime(f["signal_date"]).dt.to_period("M"))
        st["failures_stock_months"] = ff.groupby("reason")[["code", "m"]].apply(
            lambda g: len(g.drop_duplicates())).to_dict()
    traded_opp = (res["trades"].assign(m=pd.to_datetime(res["trades"]["signal_date"]).dt.to_period("M"))
                  [["code", "m"]].drop_duplicates() if len(res["trades"]) else pd.DataFrame(columns=["code", "m"]))
    st["executed_share_of_opportunities"] = float(len(traded_opp) / max(len(opp), 1))
    return st, res


def paper_short_table(df, mkt, sig, lo, hi, holds=(5, 10, 20)):
    """Frictionless short from the t+1 open: the statistical edge before any
    shortability, borrow, cost or liquidity constraint."""
    s = sig[(sig["date"] >= lo) & (sig["date"] <= hi)].copy()
    o1 = mkt.open.shift(-1)
    rows = {}
    sh_next = mkt.shortable.shift(-1).fillna(False)
    for h in holds:
        r = -(mkt.close.shift(-h) / o1 - 1)
        s[f"paper_short_{h}"] = [r.at[d, c] if c in r.columns else np.nan for d, c in zip(s["date"], s["code"])]
    s["designated_next_day"] = [bool(sh_next.at[d, c]) if c in sh_next.columns else False
                                for d, c in zip(s["date"], s["code"])]
    s = s.merge(df[["date", "code", "adv20"]], on=["date", "code"], how="left")
    for name, g in (("all_alerts", s), ("designated_only", s[s["designated_next_day"]]),
                    ("adv_ge_5m", s[s["adv20"] >= 5e6])):
        rows[name] = {"n": int(len(g)), **{f"mean_{h}": float(g[f"paper_short_{h}"].mean()) for h in holds},
                      **{f"median_{h}": float(g[f"paper_short_{h}"].median()) for h in holds}}
    return pd.DataFrame(rows).T, s


def run_bc(cfg, inp, mkt, preds, lo, hi, figs: Path, tag: str) -> tuple[dict, dict]:
    """Strategies B (momentum book + alert exits) and C (risk-ranked long book)."""
    dates = mkt.close.index
    idx = dates[(dates >= lo) & (dates <= hi)]
    close = mkt.close.loc[idx]
    traded = (mkt.value.loc[idx].fillna(0) > 0)
    raw_full = mkt.close * (mkt.raw_factor if mkt.raw_factor is not None else 1.0)
    inv_full = S.investable(raw_full, mkt.adv, 5e6, 0.5)
    raw, inv = raw_full.loc[idx], inv_full.loc[idx]
    tk = pd.DataFrame(tick_size_array(raw.to_numpy().ravel(), np.repeat(idx.to_numpy(), raw.shape[1]))
                      .reshape(raw.shape), index=idx, columns=raw.columns)
    hs = np.maximum((mkt.spread.loc[idx] / 2).clip(lower=0.0), 0.5 * tk / raw).fillna(0.01)
    rebal = S.month_end_dates(idx)
    pw = {k: preds.pivot(index="date", columns="code", values=k).reindex(index=idx, columns=close.columns)
          for k in ["p__C_lightgbm__dd20_40", "alert__C_lightgbm__dd20_40", "alert__D_two_stage__dd20_40"]}

    res_b, curves_b = {}, {}
    mom = S.momentum_members(mkt.close, inv_full, rebal)   # full history for the lookback
    base_T = S.targets_from_members(mom, idx, close.columns)
    curves_b["momentum_top50"] = portfolio_backtest(base_T, close, traded, hs)
    for lab, col in (("exit_on_C_alert", "alert__C_lightgbm__dd20_40"), ("exit_on_D_alert", "alert__D_two_stage__dd20_40")):
        ex = pw[col].fillna(False).astype(bool)
        T = S.targets_from_members(mom, idx, close.columns, exits=ex, cooldown=20)
        curves_b[lab] = portfolio_backtest(T, close, traded, hs)
        held = base_T.ffill().fillna(0) > 0
        al = S.avoided_loss_table(ex, held, close)
        res_b[f"{lab}_alerts_on_holdings"] = int(len(al))
        res_b[f"{lab}_mean_fwd20_after_alert"] = float(al["fwd_ret"].mean()) if len(al) else np.nan
        res_b[f"{lab}_share_alerts_followed_by_loss"] = float((al["fwd_ret"] < 0).mean()) if len(al) else np.nan
        res_b[f"{lab}_share_followed_by_20pct_drop"] = float((al["fwd_ret"] <= -0.2).mean()) if len(al) else np.nan
    for k, c in curves_b.items():
        res_b[k] = perf_stats(c["ret"])
        res_b[k]["avg_turnover_daily"] = float(c["turnover"].mean())
    for lab in ("exit_on_C_alert", "exit_on_D_alert"):
        res_b[f"{lab}_vs_base_p"] = S.block_bootstrap_p(curves_b[lab]["ret"] - curves_b["momentum_top50"]["ret"])
    plots.equity_curves({k: c["ret"] for k, c in curves_b.items()}, figs / f"strategy_b_equity_{tag}.png",
                        f"Strategy B: HK momentum top-50 with crash-alert exits (net, {tag})")

    full, low, high = S.risk_ranked_members(pw["p__C_lightgbm__dd20_40"], inv, rebal)
    curves_c = {k: portfolio_backtest(S.targets_from_members(m, idx, close.columns), close, traded, hs)
                for k, m in (("ew_investable", full), ("ex_top_decile_risk", low), ("top_decile_risk", high))}
    hedge = inp["bench"]["2800.HK"].reindex(idx).pct_change(fill_method=None).fillna(0)
    res_c = {k: {**perf_stats(c["ret"]), "avg_holdings": float(c["n_holdings"].mean())} for k, c in curves_c.items()}
    res_c["ex_top_minus_ew_p"] = S.block_bootstrap_p(curves_c["ex_top_decile_risk"]["ret"] - curves_c["ew_investable"]["ret"])
    res_c["top_minus_ew_p_underperf"] = S.block_bootstrap_p(curves_c["ew_investable"]["ret"] - curves_c["top_decile_risk"]["ret"])
    res_c["low_risk_minus_2800HK"] = perf_stats(curves_c["ex_top_decile_risk"]["ret"] - hedge)
    # long low-risk / short top-risk names that were designated on the rebalance date
    sh_members = {d: [c for c in m if mkt.shortable.at[d, c]] for d, m in high.items()}
    short_leg = portfolio_backtest(S.targets_from_members(sh_members, idx, close.columns), close, traded, hs)
    borrow = short_leg["n_holdings"].gt(0) * cfg["shorting"]["borrow_fee_annual"]["mid"] / 250
    ls = 0.5 * curves_c["ex_top_decile_risk"]["ret"] - 0.5 * (short_leg["ret_gross"] + short_leg["cost"] + borrow)
    res_c["long_low_short_designated_top"] = {**perf_stats(ls),
                                              "avg_short_names": float(short_leg["n_holdings"].mean())}
    plots.equity_curves({k: c["ret"] for k, c in curves_c.items()}, figs / f"strategy_c_equity_{tag}.png",
                        f"Strategy C: monthly crash-risk ranking, investable HK stocks (net, {tag})")
    return res_b, res_c
