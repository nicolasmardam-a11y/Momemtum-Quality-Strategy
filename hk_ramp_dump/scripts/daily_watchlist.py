"""Daily risk-ranked watchlist (research monitor; places no orders).

    python scripts/daily_watchlist.py [--refresh] [--retrain] [--asof YYYY-MM-DD]

Run after the HKEX close (16:10 HKT, after the closing auction). Writes
outputs/watchlist/<date>.csv and latest.md with: ticker, timestamp,
warning indicators, predicted crash probabilities, and tradeability
(designated-list status, liquidity, lot value, capacity, round-trip cost).

Models are refitted on all label-complete history when --retrain is passed
or the saved models are older than 30 days.
"""
from __future__ import annotations

import argparse
import logging
import pickle
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from hkrd import features as F  # noqa: E402
from hkrd import pipeline as P  # noqa: E402
from hkrd.config import load_config  # noqa: E402
from hkrd.hkex import explicit_cost_rate  # noqa: E402
from hkrd.models import RulesModel, candidate_mask  # noqa: E402

log = logging.getLogger("watchlist")
WARNINGS = {
    "off_high_10pct": lambda x: x["dist_high20"] <= -0.10,
    "upper_wicks": lambda x: x["upper_wick_5"] >= 0.40,
    "selling_on_down_days": lambda x: x["down_value_share_10"] >= 0.55,
    "reversal_on_volume": lambda x: x["reversal_on_volume_5"] >= 1,
    "failed_new_highs": lambda x: x["failed_highs_10"] >= 2,
}


def train_models(cfg, df: pd.DataFrame) -> dict:
    mk = P.make_models(cfg)
    models = {}
    for name in ("A_rules", "D_two_stage", "C_lightgbm"):
        for tgt in P.model_targets(name):
            y = df[tgt]
            m = y.notna()
            models[(name, tgt)] = mk[name]().fit(df.loc[m], y[m])
            log.info("trained %s %s", name, tgt)
    models["train_end"] = df.loc[df["dd20_40"].notna(), "date"].max()
    return models


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download prices first")
    ap.add_argument("--retrain", action="store_true")
    ap.add_argument("--asof", default=None)
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cfg = load_config()
    if args.refresh:
        subprocess.run([sys.executable, str(cfg.root / "scripts" / "fetch_pilot_data.py")], check=True)

    mdir = cfg.path("outputs_dir") / "models"
    mdir.mkdir(exist_ok=True)
    mfile = mdir / "production_models.pkl"
    stale = not mfile.exists() or (time.time() - mfile.stat().st_mtime) > 30 * 86400
    if args.retrain or stale:
        df = pd.read_parquet(cfg.path("store_dir") / "dataset.parquet")
        models = train_models(cfg, df)
        del df
        pickle.dump(models, open(mfile, "wb"))
    models = pickle.load(open(mfile, "rb"))

    inp = P.load_inputs(cfg, end=args.asof)
    panel = inp["panel"]
    asof = pd.Timestamp(args.asof) if args.asof else panel["date"].max()
    panel = panel[(panel["date"] <= asof) & (panel["date"] >= asof - pd.Timedelta(days=400))]
    w = P.wide_frames(panel)
    feats = F.wide_features(w["open"], w["high"], w["low"], w["close"], w["value"],
                            P.market_series(inp["bench"]), cfg["features"]["baseline_window"],
                            w["raw_close"])
    X = pd.DataFrame({k: v.loc[asof] for k, v in feats.items()})
    X.index.name = "code"
    X["traded_today"] = w["traded"].loc[asof]
    X["adv20"] = w["value"].fillna(0).rolling(20, min_periods=10).mean().loc[asof]
    X["close"] = w["raw_close"].loc[asof]
    X = X[X["close"].notna()]
    cf = cfg["candidate_filter"]
    X["stage1_runup"] = candidate_mask(X, cf["ret_20_min"], cf["value_ratio_20_min"])
    for (name, tgt), m in ((k, v) for k, v in models.items() if isinstance(k, tuple)):
        X[f"p_{name}_{tgt}"] = m.predict_proba(X)
    # Separate models per threshold are not constrained to be ordered; a larger
    # drop can never be likelier than a smaller one, so enforce monotonicity.
    for name in ("D_two_stage", "C_lightgbm"):
        X[f"p_{name}_dd20_30"] = np.maximum(X[f"p_{name}_dd20_30"], X[f"p_{name}_dd20_40"])
        X[f"p_{name}_dd20_20"] = np.maximum(X[f"p_{name}_dd20_20"], X[f"p_{name}_dd20_30"])
    X["rule_score"] = RulesModel(cf["ret_20_min"], cf["value_ratio_20_min"]).score(X)
    X["warnings"] = [", ".join(k for k, f in WARNINGS.items() if f(row)) for _, row in X.iterrows()]

    uni = inp["universe"].set_index("code")
    sh = P.shortable_wide(inp["ds"], pd.DatetimeIndex([asof]), X.index).iloc[0]
    X["name"] = uni["name"].reindex(X.index)
    X["board"] = uni["board"].reindex(X.index)
    X["board_lot"] = uni["board_lot"].reindex(X.index)
    X["lot_value_hkd"] = X["board_lot"] * X["close"]
    X["designated_shortable"] = sh.reindex(X.index).fillna(False).to_numpy()
    X["capacity_2pct_adv_hkd"] = 0.02 * X["adv20"]
    half_spread = np.maximum(0.5 * X["tick_rel"], 0.5 * X["spread_ar_20"].fillna(0))
    X["est_round_trip_cost"] = 2 * (explicit_cost_rate(asof.date()) + half_spread)
    X["tradeability"] = np.select(
        [X["designated_shortable"] & (X["adv20"] >= 5e6), X["adv20"] >= 5e6, X["adv20"] >= 5e5],
        ["SHORTABLE: designated, ADV>=HK$5m (borrow not verified)",
         "NOT SHORTABLE: avoid/exit only", "THIN: avoid/exit only, small size"], "ILLIQUID")
    X["timestamp"] = f"{asof.date()} 16:10 HKT (close)"
    X["model_trained_through"] = str(pd.Timestamp(models["train_end"]).date())
    pcol = "p_D_two_stage_dd20_40"
    wl = X[X["stage1_runup"] & X["traded_today"]].sort_values(pcol, ascending=False).head(args.top)
    cols = ["timestamp", "name", "board", "close", "ret_20", "value_ratio_20", "rule_score", "warnings",
            pcol, "p_D_two_stage_dd20_30", "p_D_two_stage_dd20_20", "p_C_lightgbm_dd20_40",
            "designated_shortable", "adv20", "board_lot", "lot_value_hkd", "capacity_2pct_adv_hkd",
            "est_round_trip_cost", "tradeability", "model_trained_through"]
    wl = wl[cols].copy()
    wl["ret_20"] = np.expm1(wl["ret_20"])
    wl["value_ratio_20"] = np.expm1(wl["value_ratio_20"])
    od = cfg.path("outputs_dir") / "watchlist"
    od.mkdir(exist_ok=True)
    wl.reset_index().to_csv(od / f"{asof.date()}.csv", index=False)
    md = [f"# HKEX ramp-and-dump watchlist, {asof.date()}",
          "", f"{len(wl)} stage-1 run-up names out of {int(X['traded_today'].sum())} traded today. "
          "Probabilities are model estimates of a >= 20/30/40% close-to-close drop within 20 trading days. "
          "Research output only; not a trading instruction.", "",
          wl.reset_index().to_markdown(index=False, floatfmt=".3g")]
    (od / "latest.md").write_text("\n".join(md))
    log.info("watchlist: %d names -> %s", len(wl), od / f"{asof.date()}.csv")


if __name__ == "__main__":
    main()
