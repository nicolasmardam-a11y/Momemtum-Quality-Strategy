"""Stage 4 (audit), step a06: independent re-computation of the stage-3 (2026 holdout) headline numbers.

From v2/follower.parquet only (auditor's code, not v2_08_results.py): M1 = first other-wallet taker BUY print second
>= t0 + d (within 60 min), + 0.01, cap 0.999, each market's current fee (rate x (p(1-p))^exp / p per $; all evaluated
markets have exp = 1), hold to resolution. Drop estimator. Adds:
  * the stricter rule used in stage 2: a print at or after the resolution-known time does not fill (stage 3 only
    required detection before t_res);
  * wallet-clustered CIs next to event-clustered ones (S1's filled signals come from 25 wallets);
  * the tick-aware (+0.001 above 0.96 / below 0.04) and no-tick conventions;
  * a simple 'always-filled' (ipw) version: every feasible loser loses its stake, feasible winners take the mean ROI of
    filled winners in their own-price bucket.
Output: audit/a06_stage3.parquet
Run from polymarket_research/:  python analyses/pit_wallets/a06_stage3_recompute.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from a01_recompute_stage2 import cboot  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "pit_wallets"


def fee(p, rate, ex):
    return rate * (p * (1 - p)) ** ex / p


def main():
    f = pd.read_parquet(OUT / "v2" / "follower.parquet")
    rng = np.random.default_rng(11)
    rows = []
    for dl in ["5s", "30s", "2m", "15m", "60m", "poll"]:
        g0 = f[f.delay == dl]
        for grp in ["S1", "S2", "S3", "S5", "B1"]:
            g = g0[g0[grp].astype(bool)]
            feas = (g.status == "ok").values & (g.dt.values < g.t_res_s.values)
            has = g.m1_raw.notna().values
            tprint = g.dt.values + g.m1_gap.fillna(0).values
            pay = g.pay.values.astype(float)
            own = g.own_px.values
            ob = np.digitize(np.nan_to_num(own, nan=-1), [0.2, 0.5, 0.8, 0.95])
            for rule in ["stage3", "print_before_tres"]:
                ok = feas & has & ((tprint < g.t_res_s.values) if rule == "print_before_tres" else True)
                for conv in ["prereg", "tick_aware", "none"] if (dl == "2m" and rule == "print_before_tres") else ["prereg"]:
                    raw = g.m1_raw.fillna(0).values
                    sl = {"prereg": 0.01, "none": 0.0}.get(conv, None)
                    sl = np.where((raw > 0.96) | (raw < 0.04), 0.001, 0.01) if sl is None else sl
                    e = np.minimum(0.999, raw + sl)
                    roi = np.where(ok, pay / np.where(ok, e, 1) - 1 - fee(np.where(ok, e, 0.5), g.fee_rate_now.values,
                                                                           g.fee_exponent.values), 0)
                    r = dict(delay=dl, group=grp, rule=rule, conv=conv, n_priced=len(g), n_feas=int(feas.sum()),
                             n_fill=int(ok.sum()), n_ev=int(g.ue[ok].nunique()), n_wal=int(g.wallet[ok].nunique()),
                             roi=float(roi[ok].mean()) if ok.any() else np.nan)
                    # ipw
                    pw = pay == 1
                    lose_roi = roi[ok & ~pw].mean() if (ok & ~pw).any() else -1.0
                    wm = roi[ok & pw].mean() if (ok & pw).any() else 0.0
                    imp = np.zeros(len(g))
                    for b_ in np.unique(ob):
                        mb = ob == b_
                        imp[mb & feas & pw] = roi[mb & ok & pw].mean() if (mb & ok & pw).any() else wm
                    imp[feas & ~pw] = lose_roi
                    r["roi_ipw"] = float(imp[feas].mean()) if feas.any() else np.nan
                    if dl == "2m":
                        cost = np.full(int(ok.sum()), 100.0)
                        r["ev_lo"], r["ev_hi"] = cboot(g.ue.values[ok], 100 * roi[ok], cost, rng, 2000)
                        r["wal_lo"], r["wal_hi"] = cboot(g.wallet.values[ok], 100 * roi[ok], cost, rng, 2000)
                        r["ipw_lo"], r["ipw_hi"] = cboot(g.ue.values[feas], 100 * imp[feas], np.full(int(feas.sum()), 100.0),
                                                         rng, 2000)
                        r["late_prints"] = int((feas & has & (tprint >= g.t_res_s.values)).sum())
                    rows.append(r)
    out = pd.DataFrame(rows)
    out.to_parquet(OUT / "audit" / "a06_stage3.parquet", index=False)
    pd.set_option("display.width", 220)
    x = out[out.delay == "2m"]
    print(x.round(4).to_string(index=False))
    print(out[(out.conv == "prereg")].pivot_table(index=["group", "rule"], columns="delay", values="roi").round(4).to_string())


if __name__ == "__main__":
    main()
