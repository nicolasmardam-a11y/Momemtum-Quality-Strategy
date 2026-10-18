"""Stage 2, step 19: compact summary tables for the results note (reads results/*.parquet, prints markdown-ish text).

Run from polymarket_research/:  python analyses/pit_wallets/19_summary.py [section]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from evalib import B1, RES  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)


def pct(x):
    return "" if pd.isna(x) else f"{100 * x:+.1f}%"


def confirm():
    c = pd.read_parquet(RES / "confirmatory.parquet")
    c = c[c.fee == "hist"]
    out = []
    for r in c.itertuples():
        out.append(dict(type=r.stype, screen=r.screen, split=r.split, n=r.n_sig, fill=f"{r.fill_rate:.2f}",
                        ev=r.n_events, roi=pct(r.roi), ci=f"[{pct(r.ci_lo)}, {pct(r.ci_hi)}]",
                        ciw=f"[{pct(r.ciw_lo)}, {pct(r.ciw_hi)}]", hit=f"{r.hit:.2f}", px=f"{r.mean_px:.2f}",
                        B1=pct(getattr(r, "roi_B1", None)), pB1=f"{getattr(r, 'p_B1', float('nan')):.2f}",
                        B2=pct(getattr(r, "roi_B2", None)), pB2=f"{getattr(r, 'p_B2', float('nan')):.2f}",
                        holm=f"{r.holm:.2f}" if pd.notna(r.holm) else "",
                        ipw=pct(r.roi_ipw), ipw_ci=f"[{pct(r.ci_lo_ipw)}, {pct(r.ci_hi_ipw)}]", adv=pct(r.roi_adv),
                        own_edge=f"{r.edge_own_B3:+.3f}" if pd.notna(r.edge_own_B3) else "", edge=f"{r.edge:+.3f}",
                        top_ev=f"{r.top_event_share:.2f}" if pd.notna(r.top_event_share) else "",
                        top1=f"{r.top1_share:.2f}" if pd.notna(r.top1_share) else "", cap=f"{r.cap1000:.2f}"))
    d = pd.DataFrame(out)
    for sp in ["test", "val", "train"]:
        print(f"\n### {sp}")
        print(d[d.split == sp].drop(columns="split").to_string(index=False))
    cur = pd.read_parquet(RES / "confirmatory.parquet")
    cur = cur[(cur.fee == "cur") & (cur.split == "test")][["stype", "screen", "roi", "ci_hi"]]
    print("\n### current-fee stress, test\n", cur.round(3).to_string(index=False))
    print("\n### criteria\n", pd.read_parquet(RES / "criteria.parquet").to_string(index=False))


def grid():
    G = pd.read_parquet(RES / "grid.parquet")
    te = G[(G.split == "test")]
    base = te[(te.slip == 0) & (te.fee == "hist") & (~te.exit)]
    print("### delay decay, P, first-print model (+0.01), hold, hist fee: ROI drop | ipw (test)")
    x = base[(base.stype == "P") & (base.model == "fp")]
    pv = x.pivot_table(index="screen", columns=["est", "delay"], values="roi")
    print((100 * pv[["drop", "ipw"]]).round(1).to_string())
    print("\n### size, P, 2-minute delay, VWAP models: ROI by estimator (test); fill rate winners/losers")
    x = base[(base.stype == "P") & (base.delay == "120")]
    pv = x.pivot_table(index="screen", columns=["model", "est"], values="roi")
    print((100 * pv).round(1).to_string())
    fr = x[x.est == "drop"].pivot_table(index="screen", columns="model", values=["fill_p1", "fill_p0"])
    print(fr.round(2).to_string())
    print("\n### slippage and fee (P, fp, 2 min, ipw, test)")
    x = te[(te.stype == "P") & (te.model == "fp") & (te.delay == "120") & (~te.exit) & (te.est == "ipw")]
    print((100 * x.pivot_table(index="screen", columns=["fee", "slip"], values="roi")).round(1).to_string())
    print("\n### exit-when-wallet-sells vs hold (P, 2 min, hist fee, slip 0, test), drop | ipw")
    x = te[(te.stype == "P") & (te.delay == "120") & (te.slip == 0) & (te.fee == "hist") & (te.model.isin(["fp", "v500"]))
           & (te.est.isin(["drop", "ipw"]))]
    print((100 * x.pivot_table(index="screen", columns=["model", "est", "exit"], values="roi")).round(1).to_string())
    print("\n### other signal types (fp, 2 min, hist, slip 0, hold), ROI drop | ipw by split")
    x = G[(G.model == "fp") & (G.delay == "120") & (G.slip == 0) & (G.fee == "hist") & (~G.exit)
          & (G.stype.isin(["ADD", "F1b", "F1", "F2", "CL"])) & (G.est.isin(["drop", "ipw"]))]
    print((100 * x.pivot_table(index=["stype", "screen"], columns=["est", "split"], values="roi")).round(1).to_string())
    rc = json.loads((RES / "grid_rc.json").read_text())
    for en, r in rc.items():
        print(f"\n### grid inference, estimator {en}")
        print({k: v for k, v in r.items() if k not in ("test", "val")})
        for sp in ["test", "val"]:
            print(sp, json.dumps(r[sp], default=str))
    # positive-variant share per estimator and number of variants
    fam = te[te.screen != B1]
    print("\nshare of test variants with ROI > 0 by estimator:", fam.groupby("est").roi.apply(lambda s: round((s > 0).mean(), 3)).to_dict())
    print("variants with ROI CI lower bound > 0 by estimator:", fam.groupby("est").ci_lo.apply(lambda s: int((s > 0).sum())).to_dict())
    b1 = te[te.screen == B1]
    print("B1 (random wallets) test variants with ROI > 0 by estimator:", b1.groupby("est").roi.apply(lambda s: round((s > 0).mean(), 3)).to_dict())


def portfolio():
    P = pd.read_parquet(RES / "portfolio.parquet")
    x = P[(P.split == "test") & (P.stype == "P")]
    cols = ["rule", "fee", "account", "screen", "n_sig_all", "sample_rate", "unfilled", "n_taken", "skip_cash",
            "skip_event", "roi_deployed", "ret_committed", "max_dd", "util_window", "util_to_last_res",
            "days_locked_after_window", "top5_event_share_abs", "top5_event_share_pnl", "top_wallet_stake_share",
            "cap_median", "cap_share_gt25"]
    for rule in ["drop", "bal", "adv"]:
        y = x[(x.rule == rule) & (x.fee == "hist")][cols]
        print(f"\n### portfolio test, rule={rule}, hist fee")
        print(y.round(3).to_string(index=False))
    y = x[(x.rule == "bal") & (x.fee == "cur")][["account", "screen", "roi_deployed", "ret_committed", "max_dd"]]
    print("\n### portfolio test, rule=bal, current fee\n", y.round(3).to_string(index=False))
    z = P[(P.stype.isin(["CL", "F1"])) & (P.split == "test") & (P.fee == "hist") & (P.account == 25000)]
    print("\n### CL / F1 portfolios, $25k, test\n", z[["rule", "stype", "screen", "n_taken", "roi_deployed",
                                                         "ret_committed", "max_dd"]].round(3).to_string(index=False))
    print("\n### category mix ($25k, bal, test)\n", x[(x.rule == "bal") & (x.fee == "hist") & (x.account == 25000)][
        ["screen", "cat_stake_share", "cat_pnl"]].to_string(index=False))


if __name__ == "__main__":
    {"confirm": confirm, "grid": grid, "portfolio": portfolio}[sys.argv[1]]()
