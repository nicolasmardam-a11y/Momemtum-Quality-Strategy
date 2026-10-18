"""Stage 2, step 21: render the markdown tables of pit_wallets_results.md from results/*.parquet and fill the
placeholders (__SUMMARY_TABLE__, __CONFIRM_TABLE__, __BENCH_TABLE__, __INFO_TABLE__, __PORT_TABLE__, __GRID__).
Run from polymarket_research/:  python analyses/pit_wallets/21_note_tables.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from evalib import B1, RES, ROOT, SCREENS  # noqa: E402

NOTE = ROOT / "notes" / "strategies" / "pit_wallets_results.md"


def p(x, d=1):
    return "" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{100 * x:+.{d}f}%"


def ci(lo, hi):
    return f"[{p(lo)}, {p(hi)}]"


def f2(x):
    return "" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.2f}"


def md(df):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        out.append("| " + " | ".join(str(v) for v in r) + " |")
    return "\n".join(out)


def summary_table(c):
    rows = []
    for (t, sc) in [("P", s) for s in SCREENS] + [("F1", "S4_sports"), ("CL", "CL"), ("P", B1)]:
        r = {}
        for sp in ["train", "val", "test"]:
            x = c[(c.stype == t) & (c.screen == sc) & (c.split == sp) & (c.fee == "hist")]
            r[sp] = x.iloc[0] if len(x) else None
        te = r["test"]
        rows.append({"signal": f"{t} {sc}", "train ROI": p(r["train"].roi) if r["train"] is not None else "",
                     "val ROI": p(r["val"].roi) if r["val"] is not None else "",
                     "TEST ROI [95% event CI]": f"{p(te.roi)} {ci(te.ci_lo, te.ci_hi)}",
                     "test ROI ipw / adv": f"{p(te.roi_ipw)} / {p(te.roi_adv)}",
                     "test filled / events": f"{te.n_fill:,} / {te.n_events:,}",
                     "mean follower px": f2(te.mean_px), "hit rate": f2(te.hit)})
    return ("Test-split summary at the pre-registered model (first print >= 2 min after the signal + 0.01, $100, hold, "
            "historical fee 0):\n\n" + md(pd.DataFrame(rows)))


def confirm_table(c, crit):
    rows = []
    te = c[(c.split == "test") & (c.fee == "hist")]
    for r in te.itertuples():
        v = crit[(crit.stype == r.stype) & (crit.screen == r.screen)]
        rows.append({"type": r.stype, "screen": r.screen, "signals": f"{r.n_sig:,}", "fill": f2(r.fill_rate),
                     "events": f"{r.n_events:,}", "net ROI": p(r.roi), "95% CI (event)": ci(r.ci_lo, r.ci_hi),
                     "95% CI (week)": ci(r.ciw_lo, r.ciw_hi), "B1": p(getattr(r, "roi_B1")),
                     "p vs B1": f2(getattr(r, "p_B1")), "B2": p(getattr(r, "roi_B2")), "p vs B2": f2(getattr(r, "p_B2")),
                     "Holm": f2(r.holm), "ipw ROI": p(r.roi_ipw), "adv ROI": p(r.roi_adv),
                     "verdict": v.verdict.iloc[0] if len(v) else "benchmark"})
    order = {s: i for i, s in enumerate(SCREENS + [B1, "CL"])}
    d = pd.DataFrame(rows)
    d["o1"] = d.screen.map(order); d["o2"] = d.type.map({"P": 0, "F1": 1, "F2": 2, "CL": 3})
    d = d.sort_values(["o2", "o1"]).drop(columns=["o1", "o2"])
    return "Test split (2025-07..2025-12 selection dates), all pre-registered hypotheses plus B1:\n\n" + md(d)


def bench_table(b):
    x = b[(b.model == "fp") & (b.split == "test") & (b.stype.isin(["P", "F1", "CL"]))]
    x = x[(x.stype == "P") | (x.screen.isin(["S4_sports", "CL"]))]
    rows = []
    for r in x.itertuples():
        rows.append({"signal": f"{r.stype} {r.screen}", "signal ROI": p(r.roi_hist),
                     "(i) matched random prints": p(r.roi_i_hist),
                     "signal - (i) [95% CI]": f"{p(r.d_i_hist)} {ci(r.d_i_hist_lo, r.d_i_hist_hi)}",
                     "(ii) favourite 0.70-0.95": p(r.roi_fav_hist),
                     "signal - (ii) [95% CI]": f"{p(r.d_fav_hist)} {ci(r.d_fav_hist_lo, r.d_fav_hist_hi)}",
                     "B2 cell": p(r.roi_B2_hist), "(iv) T-bill over holding": p(r.tbill_ret, 2),
                     "median hold (days)": f"{r.hold_days_med:.2f}",
                     "ipw signal - (i)": p(r.dw_i_hist)})
    s5 = "(iii) is the S5 row."
    return md(pd.DataFrame(rows)) + "\n\n" + s5


def info_table(b):
    x = b[(b.model == "fp") & (b.stype.isin(["P", "CL"]))]
    rows = []
    for sc in SCREENS + [B1, "CL"]:
        r = {"screen": sc}
        for sp in ["train", "val", "test"]:
            y = x[(x.screen == sc) & (x.split == sp)]
            if len(y):
                y = y.iloc[0]
                r[f"{sp}: d edge (pts)"] = f"{100 * y.d_edge:+.1f} [{100 * y.d_edge_lo:+.1f}, {100 * y.d_edge_hi:+.1f}]"
                r[f"{sp}: logit b_signal (SE), p"] = (f"{y.lg_b_sig:+.2f} ({y.lg_se_sig:.2f}), {y.lg_p_sig_1s:.2f}"
                                                     if pd.notna(y.get("lg_b_sig", np.nan)) else "")
        rows.append(r)
    return ("P signals at the first-print model. d edge = mean(payoff - follower price) minus the same for matched prints, "
            "in probability points, with a 95% event-clustered CI. Logit: outcome ~ logit(price) + signal indicator; "
            "event-clustered SE; one-sided p for b > 0.\n\n" + md(pd.DataFrame(rows)))


def port_table(P):
    x = P[(P.split == "test") & (P.stype == "P") & (P.fee == "hist")]
    rows = []
    for sc in SCREENS + [B1]:
        r = {"screen": sc}
        for A in [5000, 25000, 100000]:
            y = x[(x.screen == sc) & (x.account == A)].set_index("rule")
            r[f"${A // 1000}k drop / bal / adv: ROI on deployed"] = " / ".join(p(y.roi_deployed.get(k), 0) for k in ["drop", "bal", "adv"])
            if A == 25000:
                r["$25k return on committed: drop / bal"] = " / ".join(p(y.ret_committed.get(k), 0) for k in ["drop", "bal"])
                r["$25k max DD drop / bal"] = " / ".join(f"{100 * y.max_dd.get(k):.0f}%" for k in ["drop", "bal"])
                r["$25k trades taken (drop)"] = f"{int(y.n_taken.get('drop', 0)):,}"
                r["$25k skipped cash / event cap (drop)"] = f"{int(y.skip_cash.get('drop', 0)):,} / {int(y.skip_event.get('drop', 0)):,}"
        rows.append(r)
    cur = x = P[(P.split == "test") & (P.stype == "P") & (P.fee == "cur") & (P.rule == "bal") & (P.account == 25000)]
    extra = "Current fee schedule, bal rule, $25k, ROI on deployed: " + ", ".join(
        f"{r.screen} {p(r.roi_deployed, 1)}" for r in cur.itertuples())
    return md(pd.DataFrame(rows)) + "\n\n" + extra


def grid_text(G, rc):
    te = G[G.split == "test"]
    fam = te[te.screen != B1]
    lines = []
    d = rc["drop"]
    lines.append(f"- **Variants.** {d['n_variants_defined']:,} test-split variants per estimator: 46 signal sets (5 types x 9 "
                 "screens + CL) x 7 delays x 5 entry models x 3 slippages x 2 fee regimes, plus exit-on-sell variants "
                 f"for P and F1b. {d['n_variants_any_fill']:,} have at least one filled signal; "
                 f"{d['n_variants_tested_test']:,} have >= 30 filled events (the multiple-testing family, A12). "
                 "Each variant has an event-clustered Poisson bootstrap (1,000 draws, shared across variants).")
    rows = []
    for en in ["drop", "ipw", "adv"]:
        r = rc[en]
        bt, bv = r["test"]["best_studentized"], r["val"]["best_studentized"]
        vs = r.get("val_selected_on_test") or {}
        rows.append({"estimator": en,
                     "test variants ROI > 0": f"{(fam[fam.est == en].roi > 0).mean():.0%}",
                     "B1 variants ROI > 0": f"{(te[(te.screen == B1) & (te.est == en)].roi > 0).mean():.0%}",
                     "raw p < 0.05": f"{r['n_raw_pnorm_lt_005']:,}", "Holm p < 0.05": f"{r['n_holm_sig_005']:,}",
                     "best test variant (studentized)": f"{bt['stype']} {bt['screen']} d={bt['delay']} {bt['model']} "
                                                        f"slip={bt['slip']} {bt['fee']}{' exit' if bt['exit'] else ''}: "
                                                        f"{p(bt['roi'])} ({int(bt['n_events'])} ev)",
                     "reality-check p (studentized / raw)": f"{r['test']['rc_p_studentized']:.3f} / {r['test']['rc_p_raw']:.3f}",
                     "best on validation -> its test ROI [CI]": f"{bv['stype']} {bv['screen']} d={bv['delay']} {bv['model']}: "
                                                                f"val {p(bv['roi'])} -> test {p(vs.get('roi'))} "
                                                                f"{ci(vs.get('ci_lo'), vs.get('ci_hi'))}"})
    lines.append("\n" + md(pd.DataFrame(rows)))
    # delay decay table (ipw, fp) and size table (ipw)
    base = te[(te.slip == 0) & (te.fee == "hist") & (~te.exit) & (te.stype == "P")]
    dd = base[(base.model == "fp") & (base.est == "ipw")].pivot_table(index="screen", columns="delay", values="roi")
    dd = dd[["5", "30", "120", "600", "900", "3600", "poll"]]
    dd = dd.map(lambda v: p(v))
    dd.insert(0, "screen", dd.index)
    lines.append("\n**Delay decay** (P, first-print model + 0.01, hold, historical fee, ipw, test): ROI by detection delay "
                 "(seconds; poll = next full hour)\n\n" + md(dd.reset_index(drop=True)))
    sz = base[base.delay == "120"].pivot_table(index="screen", columns=["model", "est"], values="roi")
    rows = []
    for sc in sz.index:
        r = {"screen": sc}
        for mo in ["fp", "v100", "v500", "v2500", "v10000"]:
            r[f"{mo} drop / ipw / adv"] = " / ".join(p(sz.loc[sc, (mo, en)], 0) for en in ["drop", "ipw", "adv"])
        rows.append(r)
    lines.append("\n**Size** (P, 2-minute delay, no extra slippage, historical fee, test): ROI drop / ipw / adv\n\n" +
                 md(pd.DataFrame(rows)))
    ex = te[(te.stype == "P") & (te.delay == "120") & (te.slip == 0) & (te.fee == "hist") & (te.model == "fp")
            & (te.est == "ipw")].pivot_table(index="screen", columns="exit", values="roi")
    lines.append("\n**Exit when the followed wallet sells** (P, first print, 2 min, ipw, test), ROI hold -> exit: " +
                 ", ".join(f"{sc} {p(ex.loc[sc, False])} -> {p(ex.loc[sc, True])}" for sc in ex.index))
    sl = te[(te.stype == "P") & (te.delay == "120") & (te.model == "fp") & (~te.exit) & (te.est == "ipw")
            ].pivot_table(index="screen", columns=["fee", "slip"], values="roi")
    lines.append("\n**Slippage / fee** (P, first print, 2 min, ipw, test), ROI at +0 / +0.5 / +1 cent extra; "
                 "historical | current fee: " + "; ".join(
                     f"{sc} {' / '.join(p(sl.loc[sc, ('hist', s)]) for s in [0.0, 0.005, 0.01])} | "
                     f"{' / '.join(p(sl.loc[sc, ('cur', s)]) for s in [0.0, 0.005, 0.01])}" for sc in sl.index))
    ot = G[(G.model == "fp") & (G.delay == "120") & (G.slip == 0) & (G.fee == "hist") & (~G.exit) & (G.est == "ipw")
           & (G.stype.isin(["ADD", "F1b"])) & (G.screen != B1)].pivot_table(index=["stype", "screen"], columns="split",
                                                                            values="roi")
    rows = [{"signal": f"{a} {b_}", "train": p(r_.get("train")), "val": p(r_.get("val")), "test": p(r_.get("test"))}
            for (a, b_), r_ in ot.iterrows()]
    lines.append("\n**Other exploratory signal types** (first print, 2 min, ipw): ROI by split\n\n" + md(pd.DataFrame(rows)))
    return "\n".join(lines)


def main():
    c = pd.read_parquet(RES / "confirmatory.parquet")
    crit = pd.read_parquet(RES / "criteria.parquet")
    b = pd.read_parquet(RES / "bench_compare.parquet")
    P = pd.read_parquet(RES / "portfolio.parquet")
    G = pd.read_parquet(RES / "grid.parquet")
    rc = json.loads((RES / "grid_rc.json").read_text())
    t = NOTE.read_text()
    for k, v in {"__SUMMARY_TABLE__": summary_table(c), "__CONFIRM_TABLE__": confirm_table(c, crit),
                 "__BENCH_TABLE__": bench_table(b), "__INFO_TABLE__": info_table(b), "__PORT_TABLE__": port_table(P),
                 "__GRID__": grid_text(G, rc)}.items():
        if k in t:
            t = t.replace(k, v)
        else:
            print("placeholder missing:", k)
    NOTE.write_text(t)
    print("note tables written")


if __name__ == "__main__":
    main()
