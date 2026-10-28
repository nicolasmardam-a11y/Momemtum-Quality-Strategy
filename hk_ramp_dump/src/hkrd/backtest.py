"""Execution-aware daily backtesting.

`EventBacktester` is an order-level engine for discrete trades (Strategy A
shorts; it also handles longs). Signals are formed on the close of t and
become orders for the opening auction of t+1 + delay. Each day it applies:

* tradability: no fill on a day with zero/missing volume (suspension); orders
  wait, entries expire after `entry_ttl` days, exits wait indefinitely;
* shortability: the HKEX designated list in force on the *fill* date, plus a
  random locate failure by liquidity tier and a daily recall probability;
* participation cap: fill value <= p x min(ADV20 known at t, that day's value);
  short fills on down days are additionally haircut (tick rule);
* board lots (whole lots only) and tick rounding against the trader;
* half-spread = max(half a tick, Abdi-Ranaldo estimate / 2) x stress multiplier,
  plus square-root impact k x sigma20 x sqrt(fill / day value);
* explicit HKEX costs on each side (stamp duty, fees, levies, brokerage) and
  borrow fees accrued on short market value by calendar day;
* stops are evaluated on the close and executed at the next open, so gaps and
  suspensions are paid in full.

`portfolio_backtest` handles weight-based long portfolios (Strategies B/C).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .hkex import explicit_cost_rate, round_down_lots, tick_size, transaction_costs


@dataclass
class ExecParams:
    participation: float = 0.02
    delay_days: int = 0
    spread_mult: float = 1.0
    impact_k: float = 1.0
    short_down_day_haircut: float = 0.5
    brokerage_bps: float = 8.0
    brokerage_min: float = 50.0
    entry_ttl: int = 3


@dataclass
class ShortParams:
    require_designated: bool = True
    fee_annual: dict = field(default_factory=lambda: {"large": 0.01, "mid": 0.05, "small": 0.20})
    fee_mult: float = 1.0
    locate_fail: dict = field(default_factory=lambda: {"large": 0.02, "mid": 0.15, "small": 0.50})
    daily_recall: float = 0.005


@dataclass
class TradeRules:
    side: str = "short"            # "short" or "long"
    hold_days: int = 10
    stop_loss: float = 0.30        # adverse close-to-entry move that triggers an exit order
    take_profit: float | None = None
    nav: float = 50_000_000
    max_position_nav: float = 0.02
    max_gross: float = 0.50
    max_positions: int = 25


def liquidity_tier(adv_value: float) -> str:
    if adv_value >= 200e6:
        return "large"
    if adv_value >= 20e6:
        return "mid"
    return "small"


@dataclass
class Market:
    """Wide (date x code) frames aligned on the same index/columns."""
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    value: pd.DataFrame
    spread: pd.DataFrame           # estimated full effective spread (fraction)
    sigma: pd.DataFrame            # 20d daily return std
    adv: pd.DataFrame              # ADV20 traded value known at close t
    shortable: pd.DataFrame        # designated list in force on each date
    board_lot: pd.Series           # by code (current lots: a pilot limitation)
    raw_factor: pd.DataFrame | None = None   # adjusted x factor = traded price (for ticks)

    @classmethod
    def from_panel(cls, panel: pd.DataFrame, shortable: pd.DataFrame, board_lot: pd.Series,
                   spread: pd.DataFrame | None = None) -> "Market":
        cols = ["open", "high", "low", "close", "value"] + (["raw_factor"] if "raw_factor" in panel else [])
        w = {c: panel.pivot(index="date", columns="code", values=c).sort_index() for c in cols}
        r = np.log(w["close"]).diff()
        sigma = r.rolling(20, min_periods=10).std()
        adv = w["value"].fillna(0).rolling(20, min_periods=10).mean()
        if spread is None:
            spread = pd.DataFrame(0.0, index=w["close"].index, columns=w["close"].columns)
        sh = shortable.reindex(index=w["close"].index, columns=w["close"].columns).fillna(False).astype(bool)
        rf = w["raw_factor"].ffill().fillna(1.0) if "raw_factor" in w else None
        return cls(w["open"], w["high"], w["low"], w["close"], w["value"],
                   spread.reindex_like(w["close"]).fillna(0.0), sigma, adv, sh,
                   board_lot.reindex(w["close"].columns), rf)


class EventBacktester:
    def __init__(self, mkt: Market, rules: TradeRules, ex: ExecParams, sp: ShortParams, seed: int = 0):
        self.m, self.r, self.ex, self.sp = mkt, rules, ex, sp
        self.rng = np.random.default_rng(seed)

    def _px_and_cap(self, i: int, j: int, side_sell: bool, is_short_entry: bool):
        m, ex = self.m, self.ex
        val = m.value.iat[i, j]
        if not (val > 0):
            return None, 0.0
        o, h, l, c = m.open.iat[i, j], m.high.iat[i, j], m.low.iat[i, j], m.close.iat[i, j]
        cap = ex.participation * min(val, m.adv.iat[i - 1, j] if i > 0 else val)
        base = o
        if is_short_entry:
            # Tick rule: a short may not be priced below the best ask, so it is
            # filled passively during the continuous session, not at the auction.
            base = (o + h + l + c) / 4.0
            if c < o:
                cap *= ex.short_down_day_haircut
        return base, cap

    def _exec_price(self, base: float, i: int, j: int, fill_value: float, sell: bool) -> float:
        m, ex = self.m, self.ex
        d = m.close.index[i].date()
        # Engine prices are split-adjusted; ticks apply to the price actually
        # traded, so convert to raw, round there, and convert back.
        f = float(m.raw_factor.iat[i, j]) if m.raw_factor is not None else 1.0
        tk = tick_size(base * f, d) / f
        hs = max(0.5 * tk / base, 0.5 * m.spread.iat[i, j]) * ex.spread_mult
        sig = m.sigma.iat[i, j] if np.isfinite(m.sigma.iat[i, j]) else 0.05
        imp = ex.impact_k * sig * np.sqrt(min(fill_value / max(m.value.iat[i, j], 1.0), 1.0))
        px = base * (1 - hs - imp) if sell else base * (1 + hs + imp)
        steps = np.floor(px / tk + 1e-9) if sell else np.ceil(px / tk - 1e-9)
        return max(steps, 1) * tk

    def run(self, signals: pd.DataFrame) -> dict:
        """signals: columns date (signal close), code, score. Higher score first."""
        m, r, ex, sp = self.m, self.r, self.ex, self.sp
        dates = m.close.index
        col = {c: k for k, c in enumerate(m.close.columns)}
        sig_by_day = {d: g.sort_values("score", ascending=False) for d, g in signals.groupby("date")}
        short = r.side == "short"
        pending_entries: list[dict] = []
        positions: dict[int, dict] = {}
        trades, failures, daily = [], [], []

        for i, d in enumerate(dates):
            day_costs, day_borrow, realized = 0.0, 0.0, 0.0
            # ---- 1. exits queued at previous closes
            for code, pos in list(positions.items()):
                if not pos.get("exit_pending"):
                    continue
                j = col[code]
                base, cap = self._px_and_cap(i, j, side_sell=not short, is_short_entry=False)
                if base is None:
                    continue  # suspended: stuck
                lot = int(m.board_lot.iat[j])
                want = pos["shares"]
                sh = want if want * base <= cap else round_down_lots(cap / base, lot)
                if sh <= 0:
                    continue
                px = self._exec_price(base, i, j, sh * base, sell=not short)
                cost = transaction_costs(sh * px, d.date(), ex.brokerage_bps, ex.brokerage_min).total
                mark = pos.get("prev_mark", pos["entry_px"])
                realized += sh * ((mark - px) if short else (px - mark))
                day_costs += cost
                pos["shares"] -= sh
                pos["exit_value"] += sh * px
                pos["exit_costs"] += cost
                pos["exit_shares"] += sh
                if pos["shares"] == 0:
                    trades.append({**{k: v for k, v in pos.items() if k not in ("exit_pending",)},
                                   "exit_date": d, "exit_px": pos["exit_value"] / pos["exit_shares"]})
                    del positions[code]
            # ---- 2. entries queued at previous closes
            still = []
            for o_ in pending_entries:
                j = col[o_["code"]]
                if i < o_["first_fill_idx"]:
                    still.append(o_)
                    continue
                if i > o_["first_fill_idx"] + ex.entry_ttl or o_["code"] in positions:
                    failures.append({**o_, "reason": o_.get("last_reason", "expired")})
                    continue
                if short and sp.require_designated and not m.shortable.iat[i, j]:
                    failures.append({**o_, "reason": "not_designated"})
                    continue
                base, cap = self._px_and_cap(i, j, side_sell=short, is_short_entry=short)
                if base is None:
                    o_["last_reason"] = "suspended"
                    still.append(o_)
                    continue
                lot = int(m.board_lot.iat[j])
                gross = sum(p["shares"] * m.close.iat[i - 1, col[c]] for c, p in positions.items())
                room = max(r.max_gross * r.nav - gross, 0.0)
                target = min(o_["target_value"], room)
                fill_val = min(target, cap)
                sh = round_down_lots(fill_val / base, lot)
                if sh <= 0 or len(positions) >= r.max_positions:
                    o_["last_reason"] = "no_liquidity" if cap < lot * base else "capacity"
                    still.append(o_)
                    continue
                px = self._exec_price(base, i, j, sh * base, sell=short)
                cost = transaction_costs(sh * px, d.date(), ex.brokerage_bps, ex.brokerage_min).total
                day_costs += cost
                positions[o_["code"]] = {
                    "code": o_["code"], "signal_date": o_["signal_date"], "entry_date": d,
                    "entry_idx": i, "entry_px": px, "shares": sh, "entry_shares": sh,
                    "entry_costs": cost, "fill_ratio": sh * base / o_["target_value"],
                    "score": o_["score"], "tier": o_["tier"], "borrow": 0.0, "exit_value": 0.0,
                    "exit_costs": 0.0, "exit_shares": 0, "exit_reason": None,
                }
            pending_entries = still
            # ---- 3. mark to market, borrow, exit decisions at the close
            close_mv = 0.0
            for code, pos in positions.items():
                j = col[code]
                c = m.close.iat[i, j]
                if not np.isfinite(c):
                    c = pos.get("last_close", pos["entry_px"])
                pos["last_close"] = c
                close_mv += pos["shares"] * c
                if short and i > pos["entry_idx"]:
                    days = (d - dates[i - 1]).days
                    fee = pos["shares"] * c * sp.fee_annual[pos["tier"]] * sp.fee_mult * days / 365.0
                    pos["borrow"] += fee
                    day_borrow += fee
                if pos.get("exit_pending"):
                    continue
                move = c / pos["entry_px"] - 1.0
                adverse = move if short else -move
                held = i - pos["entry_idx"]
                reason = None
                if adverse >= r.stop_loss:
                    reason = "stop"
                elif r.take_profit is not None and -adverse >= r.take_profit:
                    reason = "take_profit"
                elif held >= r.hold_days:
                    reason = "time"
                elif short and self.rng.random() < sp.daily_recall:
                    reason = "recall"
                if reason:
                    pos["exit_pending"], pos["exit_reason"] = True, reason
            # ---- 4. new signals -> orders for t+1+delay
            if d in sig_by_day:
                for s in sig_by_day[d].itertuples():
                    j = col.get(s.code)
                    if j is None or s.code in positions:
                        continue
                    adv = m.adv.iat[i, j]
                    tier = liquidity_tier(adv if np.isfinite(adv) else 0.0)
                    rec = {"code": s.code, "signal_date": d, "score": s.score, "tier": tier,
                           "first_fill_idx": i + 1 + ex.delay_days,
                           "target_value": r.max_position_nav * r.nav}
                    k = min(i + 1 + ex.delay_days, len(dates) - 1)
                    if short and sp.require_designated and not m.shortable.iat[k, j]:
                        failures.append({**rec, "reason": "not_designated"})
                        continue
                    if short and self.rng.random() < sp.locate_fail[tier]:
                        failures.append({**rec, "reason": "locate_failed"})
                        continue
                    pending_entries.append(rec)
            # mark-to-market change of open positions since the previous mark
            unreal = 0.0
            for code, pos in positions.items():
                c, pc = pos["last_close"], pos.get("prev_mark", pos["entry_px"])
                unreal += pos["shares"] * ((pc - c) if short else (c - pc))
                pos["prev_mark"] = c
            daily.append({"date": d, "pnl_gross": unreal + realized, "costs": day_costs,
                          "borrow": day_borrow, "gross_exposure": close_mv, "n_pos": len(positions)})

        tr = pd.DataFrame(trades)
        if len(tr):
            sgn = 1 if short else -1
            tr["gross_pnl"] = sgn * (tr["entry_px"] * tr["entry_shares"] - tr["exit_value"])
            tr["net_pnl"] = tr["gross_pnl"] - tr["entry_costs"] - tr["exit_costs"] - tr["borrow"]
            tr["notional"] = tr["entry_px"] * tr["entry_shares"]
            tr["net_ret"] = tr["net_pnl"] / tr["notional"]
            tr["hold_days"] = [(b - a).days for a, b in zip(tr["entry_date"], tr["exit_date"])]
        dd = pd.DataFrame(daily).set_index("date")
        dd["pnl_net"] = dd["pnl_gross"] - dd["costs"] - dd["borrow"]
        dd["ret"] = dd["pnl_net"] / r.nav     # fixed-capital daily return
        return {"trades": tr, "failures": pd.DataFrame(failures), "daily": dd,
                "open_positions": positions}


# ---------------------------------------------------------------------------
def portfolio_backtest(weights: pd.DataFrame, close: pd.DataFrame, traded: pd.DataFrame,
                       half_spread: pd.DataFrame, brokerage_bps: float = 8.0,
                       spread_mult: float = 1.0) -> pd.DataFrame:
    """Long-only weight-based portfolio.

    `weights` are targets decided at close t; NaN means "hold the drifted
    weight". Targets are applied to returns from close t+1 onward (one extra
    day of lag versus an opening-auction fill: a conservative stand-in for
    trading at t+1 during the day). Positions in stocks that do not trade on a
    day cannot be changed (frozen at drifted weight) — that is how suspensions
    trap a liquidation.
    """
    ret = close.pct_change(fill_method=None).fillna(0.0)
    tgt = weights.reindex_like(close).shift(1)
    can = traded.reindex_like(close).fillna(False).astype(bool).to_numpy()
    R = ret.to_numpy()
    T = tgt.to_numpy()
    hs = (half_spread.reindex_like(close).fillna(0.01).to_numpy()) * spread_mult
    dates = close.index
    w = np.zeros(close.shape[1])
    out = []
    for i in range(len(dates)):
        t = T[i]
        new = np.where(can[i] & ~np.isnan(t), t, w)
        s = new.sum()
        if s > 1.0:
            # cannot exceed fully invested: scale the tradable part down
            frozen = (~can[i]) * w
            free = new - frozen
            room = max(1.0 - frozen.sum(), 0.0)
            new = frozen + (free * room / free.sum() if free.sum() > 0 else 0)
        trade = np.abs(new - w)
        cost = (trade * (explicit_cost_rate(dates[i].date(), brokerage_bps) + hs[i])).sum()
        gross = (new * R[i]).sum()
        out.append({"date": dates[i], "ret_gross": gross, "cost": cost, "ret": gross - cost,
                    "turnover": trade.sum() / 2, "n_holdings": int((new > 0).sum()),
                    "exposure": float(new.sum())})
        w = new * (1 + R[i])
        tot = w.sum() + max(1 - new.sum(), 0)  # cash earns 0
        w = w / tot if tot > 0 else w
    return pd.DataFrame(out).set_index("date")


def perf_stats(r: pd.Series, periods: int = 250) -> dict:
    r = r.dropna()
    if len(r) < 2 or r.std() == 0:
        return {"n_days": int(len(r))}
    eq = (1 + r).cumprod()
    ann = eq.iloc[-1] ** (periods / len(r)) - 1
    vol = r.std() * np.sqrt(periods)
    down = r[r < 0].std() * np.sqrt(periods)
    mdd = (eq / eq.cummax() - 1).min()
    return {"n_days": int(len(r)), "ann_return": float(ann), "ann_vol": float(vol),
            "sharpe": float(r.mean() / r.std() * np.sqrt(periods)),
            "sortino": float(r.mean() * periods / down) if down > 0 else np.nan,
            "max_drawdown": float(mdd), "worst_day": float(r.min()),
            "cvar_5": float(r[r <= r.quantile(0.05)].mean())}


def trade_stats(tr: pd.DataFrame) -> dict:
    if tr is None or len(tr) == 0:
        return {"n_trades": 0}
    win = tr["net_pnl"] > 0
    avg_w = tr.loc[win, "net_ret"].mean()
    avg_l = tr.loc[~win, "net_ret"].mean()
    return {"n_trades": int(len(tr)), "n_stocks": int(tr["code"].nunique()),
            "mean_net_ret": float(tr["net_ret"].mean()), "median_net_ret": float(tr["net_ret"].median()),
            "win_rate": float(win.mean()),
            "payoff_ratio": float(avg_w / abs(avg_l)) if np.isfinite(avg_w) and avg_l < 0 else np.nan,
            "total_net_pnl": float(tr["net_pnl"].sum()), "total_notional": float(tr["notional"].sum()),
            "mean_fill_ratio": float(tr["fill_ratio"].mean()),
            "mean_hold_days": float(tr["hold_days"].mean()),
            "exit_reasons": tr["exit_reason"].value_counts().to_dict()}
