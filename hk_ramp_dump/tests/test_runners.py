"""End-to-end smoke test of the strategy runners on synthetic data."""
import numpy as np
import pandas as pd

from hkrd import strategies as S
from hkrd.config import load_config
from hkrd.runners import build_market, paper_short_table, run_a, run_bc

from conftest import make_panel


def _inputs(tmp_path):
    frames = [make_panel(n_days=600, codes=range(10 * k, 10 * k + 10), seed=k, ramp_code=10 * k + 3,
                         ramp_at=300 + 30 * k) for k in range(3)]
    panel = pd.concat(frames, ignore_index=True)
    panel["value"] *= 50          # make some names investable (ADV >= HK$5m)
    panel["raw_factor"] = 1.0
    dates = pd.DatetimeIndex(sorted(panel["date"].unique()))
    codes = sorted(panel["code"].unique())
    bench = pd.DataFrame({"^HSI": np.linspace(100, 120, len(dates)), "2800.HK": np.linspace(20, 24, len(dates))},
                         index=dates)
    ds = pd.DataFrame({"effective_date": dates[0], "code": codes[::2]})
    uni = pd.DataFrame({"code": codes, "board_lot": 1000, "name": "X", "board": "MAIN"})
    rng = np.random.default_rng(0)
    df = panel[["date", "code"]].copy()
    df["candidate"] = rng.random(len(df)) < 0.05
    df["spread_ar_20"] = 0.01
    df["adv20"] = 1e7
    df["ret_20"] = np.log(2.5) * df["candidate"]
    preds = df[["date", "code"]].copy()
    for m in ("C_lightgbm", "D_two_stage", "A_rules"):
        p = rng.random(len(df))
        preds[f"p__{m}__dd20_40"] = p
        preds[f"alert__{m}__dd20_40"] = p > 0.9
    return {"panel": panel, "bench": bench, "ds": ds, "universe": uni}, df, preds


def test_runners_end_to_end(tmp_path):
    cfg = load_config()
    inp, df, preds = _inputs(tmp_path)
    mkt = build_market(cfg, inp, df)
    lo, hi = df["date"].min() + pd.Timedelta(days=200), df["date"].max()
    sig = S.alert_signals(preds, df, "D_two_stage")
    st, res = run_a(mkt, sig, lo, hi, cfg, 10, 0.3)
    assert st["n_signals"] > 0
    assert set(res["failures"]["reason"]) <= {"not_designated", "locate_failed", "expired", "no_liquidity",
                                               "capacity", "suspended"}
    paper, _ = paper_short_table(df, mkt, sig, lo, hi)
    assert "designated_only" in paper.index
    res_b, res_c = run_bc(cfg, inp, mkt, preds, lo, hi, tmp_path, "test")
    assert "momentum_top50" in res_b and "ew_investable" in res_c
