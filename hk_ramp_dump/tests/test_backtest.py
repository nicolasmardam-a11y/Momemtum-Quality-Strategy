import numpy as np
import pandas as pd

from hkrd.backtest import EventBacktester, ExecParams, Market, ShortParams, TradeRules


def _market(panel, shortable=True, suspend=None):
    p = panel.copy()
    if suspend is not None:
        code, a, b = suspend
        dates = sorted(p["date"].unique())
        sel = (p["code"] == code) & p["date"].between(dates[a], dates[b])
        p.loc[sel, ["volume", "value"]] = 0.0
    dates = sorted(p["date"].unique())
    sh = pd.DataFrame(shortable, index=pd.DatetimeIndex(dates), columns=sorted(p["code"].unique()))
    lots = pd.Series(1000, index=sorted(p["code"].unique()))
    return Market.from_panel(p, sh, lots)


def _signal(panel, code, i):
    d = sorted(panel["date"].unique())[i]
    return pd.DataFrame({"date": [pd.Timestamp(d)], "code": [code], "score": [1.0]})


def test_short_needs_designation(panel):
    m = _market(panel, shortable=False)
    bt = EventBacktester(m, TradeRules(), ExecParams(), ShortParams(locate_fail={"large": 0, "mid": 0, "small": 0}))
    res = bt.run(_signal(panel, 2, 250))
    assert len(res["trades"]) == 0
    assert (res["failures"]["reason"] == "not_designated").all()


def test_short_profits_on_dump_and_lots(panel):
    m = _market(panel)
    sp = ShortParams(locate_fail={"large": 0, "mid": 0, "small": 0}, daily_recall=0.0)
    bt = EventBacktester(m, TradeRules(hold_days=8, nav=1e7), ExecParams(participation=0.05), sp)
    res = bt.run(_signal(panel, 2, 249))
    tr = res["trades"]
    assert len(tr) == 1
    assert tr["entry_shares"].iloc[0] % 1000 == 0
    assert tr["net_pnl"].iloc[0] > 0
    # daily P&L reconciles with trade P&L when no position is left open
    assert np.isclose(res["daily"]["pnl_net"].sum(), tr["net_pnl"].sum(), rtol=1e-6)


def test_suspension_blocks_exit(panel):
    m = _market(panel, suspend=(2, 252, 280))
    sp = ShortParams(locate_fail={"large": 0, "mid": 0, "small": 0}, daily_recall=0.0)
    bt = EventBacktester(m, TradeRules(hold_days=2, nav=1e7), ExecParams(participation=0.05), sp)
    res = bt.run(_signal(panel, 2, 249))
    tr = res["trades"]
    exit_idx = sorted(panel["date"].unique()).index(tr["exit_date"].iloc[0])
    assert exit_idx > 280


def test_portfolio_hold_semantics_and_frozen_suspension():
    from hkrd.backtest import portfolio_backtest

    idx = pd.bdate_range("2020-01-01", periods=6)
    close = pd.DataFrame({1: [1, 1.1, 1.21, 1.21, 1.21, 1.21], 2: [1.0] * 6}, index=idx)
    traded = pd.DataFrame(True, index=idx, columns=[1, 2])
    traded.loc[idx[3]:, 1] = False                      # stock 1 suspended from day 3
    w = pd.DataFrame(np.nan, index=idx, columns=[1, 2])
    w.iloc[0] = [0.5, 0.5]
    w.iloc[3] = [0.0, 1.0]                               # try to exit stock 1 while suspended
    hs = pd.DataFrame(0.0, index=idx, columns=[1, 2])
    res = portfolio_backtest(w, close, traded, hs, brokerage_bps=0)
    # day 1 applies the targets; stock 1 cannot be sold on day 4 (suspended)
    assert res["n_holdings"].iloc[-1] == 2
    assert res["turnover"].iloc[2:].sum() < 0.6
