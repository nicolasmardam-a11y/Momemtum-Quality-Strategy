"""Post-hoc robustness checks (NOT part of the pre-registered verdict).

    python scripts/robustness.py

Strategy B placebo: does the alert-exit overlay beat random exits of the same
number of holdings on the same days? An exit overlay that parks cash until
the next rebalance lowers exposure, which by itself flatters a losing book.
Strategy C: the top-risk decile's return by calendar year.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from hkrd import pipeline as P  # noqa: E402
from hkrd import strategies as S  # noqa: E402
from hkrd.backtest import perf_stats, portfolio_backtest  # noqa: E402
from hkrd.config import load_config  # noqa: E402
from hkrd.hkex import tick_size_array  # noqa: E402
from hkrd.runners import build_market  # noqa: E402

log = logging.getLogger("robustness")


def placebo_exits(alerts: pd.DataFrame, held: pd.DataFrame, rng, cooldown: int = 20) -> pd.DataFrame:
    """Same number of *new* exit events per day as the real overlay (an alert on
    a holding not alerted in the previous `cooldown` days), drawn at random
    from that day's holdings. Alerts repeat on consecutive days, so matching
    raw alert counts would make the placebo exit far more names."""
    real = (alerts & held)
    recent = real.astype(float).shift(1).rolling(cooldown, min_periods=1).max().fillna(0).astype(bool)
    new_events = real & ~recent
    out = pd.DataFrame(False, index=alerts.index, columns=alerts.columns)
    H = held.to_numpy()
    for i, k in enumerate(new_events.sum(axis=1).to_numpy()):
        if k == 0:
            continue
        pool = np.flatnonzero(H[i])
        if len(pool):
            out.iloc[i, rng.choice(pool, min(int(k), len(pool)), replace=False)] = True
    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cfg = load_config()
    inp = P.load_inputs(cfg)
    df = pd.read_parquet(cfg.path("store_dir") / "dataset.parquet", columns=["date", "code", "spread_ar_20"])
    mkt = build_market(cfg, inp, df)
    rf = mkt.raw_factor
    raw_full = mkt.close * rf
    inv_full = S.investable(raw_full, mkt.adv, 5e6, 0.5)
    store = cfg.path("store_dir")
    runs = {"development_oos_2016_2024H1": (pd.read_parquet(store / "oos_predictions.parquet"),
                                            "2016-01-01", cfg["sample"]["validation"][1]),
            "holdout_2024H2_2026": (pd.read_parquet(store / "holdout_predictions.parquet"),
                                    cfg["sample"]["holdout"][0], cfg["sample"]["holdout"][1])}
    rows, yearly = [], []
    for tag, (preds, lo, hi) in runs.items():
        idx = mkt.close.index[(mkt.close.index >= lo) & (mkt.close.index <= hi)]
        close, raw = mkt.close.loc[idx], raw_full.loc[idx]
        traded = mkt.value.loc[idx].fillna(0) > 0
        tk = pd.DataFrame(tick_size_array(raw.to_numpy().ravel(), np.repeat(idx.to_numpy(), raw.shape[1]))
                          .reshape(raw.shape), index=idx, columns=raw.columns)
        hs = np.maximum((mkt.spread.loc[idx] / 2).clip(lower=0), 0.5 * tk / raw).fillna(0.01)
        rebal = S.month_end_dates(idx)
        mom = S.momentum_members(mkt.close, inv_full, rebal)
        base_T = S.targets_from_members(mom, idx, close.columns)
        base = portfolio_backtest(base_T, close, traded, hs)
        held = base_T.ffill().fillna(0) > 0
        rows.append({"period": tag, "variant": "base", **perf_stats(base["ret"]),
                     "avg_exposure": base["exposure"].mean()})
        for model in ("C_lightgbm", "D_two_stage"):
            al = preds.pivot(index="date", columns="code", values=f"alert__{model}__dd20_40") \
                .reindex(index=idx, columns=close.columns).fillna(False).astype(bool)
            real = portfolio_backtest(S.targets_from_members(mom, idx, close.columns, exits=al), close, traded, hs)
            st = {**perf_stats(real["ret"]), "avg_exposure": real["exposure"].mean()}
            rows.append({"period": tag, "variant": f"exit_on_{model}", **st})
            pl = []
            for seed in range(20):
                pe = placebo_exits(al, held, np.random.default_rng(seed))
                r = portfolio_backtest(S.targets_from_members(mom, idx, close.columns, exits=pe), close, traded, hs)
                pl.append({**perf_stats(r["ret"]), "avg_exposure": r["exposure"].mean()})
            pl = pd.DataFrame(pl)
            rows.append({"period": tag, "variant": f"placebo_for_{model}_mean_of_20", **pl.mean().to_dict()})
            for k in ("ann_return", "sharpe", "max_drawdown"):
                rows[-1][f"share_placebos_beating_real_{k}"] = float((pl[k] >= st[k]).mean())
            log.info("%s %s real=%s placebo=%s", tag, model, st["ann_return"], pl["ann_return"].mean())
        # Strategy C top decile by year
        p = preds.pivot(index="date", columns="code", values="p__C_lightgbm__dd20_40").reindex(index=idx, columns=close.columns)
        full, low, high = S.risk_ranked_members(p, inv_full.loc[idx], rebal)
        for k, m in (("ew_investable", full), ("top_decile_risk", high)):
            r = portfolio_backtest(S.targets_from_members(m, idx, close.columns), close, traded, hs)["ret"]
            for y, g in r.groupby(r.index.year):
                yearly.append({"period": tag, "portfolio": k, "year": y, "return": float((1 + g).prod() - 1)})
    out = cfg.path("outputs_dir") / "robustness"
    out.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "strategy_b_placebo.csv", index=False)
    pd.DataFrame(yearly).pivot_table(index=["period", "year"], columns="portfolio", values="return") \
        .to_csv(out / "strategy_c_top_decile_by_year.csv")
    log.info("done")


if __name__ == "__main__":
    main()
