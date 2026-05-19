"""Daily strategy check + full dashboard snapshot. ACCOUNT-DECOUPLED.

Remote/scheduled routine. ZERO IBKR / paper-account connection: uses only a
public yfinance refresh (delegated to scripts/daily_update.py) plus the local
frozen research artifacts. Every run produces:

  1. Refreshed overlay  — URTH/EEM refresh + naked-series extension +
     exposure recompute, via scripts/daily_update.py (idempotent, yfinance
     only, no broker). This also writes reports/daily/<date>_overlay.json,
     which the Streamlit app's load_today_exposure() already reads
     newest-first  ->  the LIVE dashboard stays fresh automatically.
  2. A dated, self-contained dashboard snapshot under
     reports/dashboard/<YYYY-MM-DD>/  (index.html + snapshot.md +
     metrics.json + the underlying CSV/JSON), mirrored to
     reports/dashboard/latest/  ->  full browsable daily history, opens
     with no server.

The stock book is FROZEN (quarterly reconstitution); the daily-varying part
is the risk overlay, so the daily check refreshes the overlay and re-renders
the snapshot, never re-ranks. Never imports ib_async / connects a broker.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
from logger import get_logger

# ---- local artifacts (same files the Streamlit dashboard reads) -----------
OVERLAY_RET = ROOT / "equity/v25_overlay_returns.csv"
NAKED_RET = ROOT / "equity/full_pit_naked_returns.csv"
BENCH = ROOT / "data/prices/benchmarks_wide.parquet"
PORT = ROOT / "reports/production/current_portfolio_clean.csv"
COUNTRY_PNL = ROOT / "reports/production/v25_country_pnl.csv"
SUBPERIOD = ROOT / "reports/production/v25_subperiod.csv"
DAILY_DIR = ROOT / "reports/daily"
DASH_DIR = ROOT / "reports/dashboard"


# ---- metric helpers (mirrors dashboard/app.py, no streamlit dep) ----------
def _metrics(daily: pd.Series) -> dict:
    if daily is None or len(daily) < 2:
        return {}
    daily = daily.dropna()
    years = (daily.index[-1] - daily.index[0]).days / 365.25
    eq = (1 + daily).cumprod()
    cagr = eq.iloc[-1] ** (1 / years) - 1 if eq.iloc[-1] > 0 and years > 0 else np.nan
    vol = daily.std(ddof=0) * np.sqrt(252)
    sharpe = (daily.mean() / daily.std(ddof=0) * np.sqrt(252)
              if daily.std(ddof=0) > 0 else np.nan)
    dd = (eq / eq.cummax()) - 1
    mdd = dd.min()
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan
    down = daily[daily < 0]
    sortino = (daily.mean() / down.std(ddof=0) * np.sqrt(252)
               if len(down) > 1 and down.std(ddof=0) > 0 else np.nan)
    return {"CAGR": cagr, "Vol": vol, "Sharpe": sharpe,
            "Sortino": sortino, "MDD": mdd, "Calmar": calmar,
            "cur_dd": float(dd.iloc[-1])}


def _read_series(path: Path):
    if not path.exists():
        return None
    s = pd.read_csv(path, parse_dates=[0], index_col=0)
    return s.iloc[:, 0]


def _load_overlay_json():
    js = sorted(DAILY_DIR.glob("*_overlay.json"))
    if not js:
        return {}, None
    o = json.loads(js[-1].read_text())
    return o.get("overlay", {}), js[-1].name


def _action(exp: float) -> str:
    if exp < 0.05:
        return "FULLY DEFENSIVE — all cash"
    if exp < 0.30:
        return "DEFENSIVE — small equity exposure"
    if exp < 0.70:
        return "REDUCED — sub-target equity"
    if exp < 0.95:
        return "NORMAL — near target"
    return "FULL — max equity exposure"


def run_daily_update(log) -> dict:
    """Delegate the (broker-free) data + overlay refresh. Tolerant: if the
    network refresh fails the snapshot is still built off existing data."""
    rc, tail = 0, ""
    try:
        p = subprocess.run(
            [sys.executable, str(ROOT / "scripts/daily_update.py")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=600)
        rc = p.returncode
        tail = (p.stdout or "")[-1500:] + (p.stderr or "")[-500:]
        log.info("daily_update.py rc=%d", rc)
    except Exception as e:                              # noqa: BLE001
        rc, tail = -1, repr(e)
        log.error("daily_update.py failed (snapshot continues): %r", e)
    return {"rc": rc, "tail": tail}


# ---- snapshot rendering ---------------------------------------------------
_CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:24px;
color:#1a1a1a;background:#fafafa}h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;border-bottom:2px solid #ddd;padding-bottom:4px;margin-top:28px}
.sub{color:#666;font-size:12px;margin-bottom:16px}
.cards{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.card{background:#fff;border:1px solid #e2e2e2;border-radius:8px;padding:12px 16px;
min-width:150px}.card .k{font-size:11px;color:#888;text-transform:uppercase}
.card .v{font-size:20px;font-weight:600;margin-top:2px}
table{border-collapse:collapse;font-size:12px;background:#fff;margin:8px 0}
th,td{border:1px solid #e2e2e2;padding:5px 9px;text-align:right}
th{background:#f0f0f0}td:first-child,th:first-child{text-align:left}
.banner{background:#fff3cd;border:1px solid #ffe69c;padding:8px 12px;
border-radius:6px;font-size:12px;margin:10px 0}
.foot{color:#888;font-size:11px;margin-top:30px;border-top:1px solid #ddd;
padding-top:10px}
"""


def _df_html(df: pd.DataFrame) -> str:
    return df.to_html(index=False, border=0, justify="right",
                      float_format=lambda x: f"{x:,.3f}")


def build_snapshot(log, upd: dict) -> dict:
    date = datetime.now().strftime("%Y-%m-%d")
    ov, ov_src = _load_overlay_json()
    exp = float(ov.get("exposure", float("nan")))
    vs = float(ov.get("vol_scalar", exp))
    trend_on = ov.get("trend_scalar", 1.0) and float(ov.get("trend_scalar", 1.0)) > 0.5

    overlay = _read_series(OVERLAY_RET)
    naked = _read_series(NAKED_RET)

    # benchmark daily returns aligned to the overlay window
    bench_rets = {}
    if BENCH.exists() and overlay is not None:
        b = pd.read_parquet(BENCH)
        if isinstance(b.columns, pd.MultiIndex):
            b.columns = b.columns.get_level_values(0)
        b.index = pd.to_datetime(b.index)
        for tk in ["URTH", "SPY", "QQQ", "MTUM", "QUAL", "ACWI"]:
            if tk in b.columns:
                r = b[tk].dropna().pct_change().dropna()
                r = r.loc[overlay.index[0]:overlay.index[-1]]
                if len(r) > 0:
                    bench_rets[tk] = r

    # metrics table
    rows = []
    if overlay is not None:
        rows.append({"Series": "v2.5 overlay (production)", **_metrics(overlay)})
    if naked is not None:
        rows.append({"Series": "v2.5 naked (no overlay)", **_metrics(naked)})
    for tk, r in bench_rets.items():
        rows.append({"Series": tk, **_metrics(r)})
    mdf = pd.DataFrame(rows)
    if not mdf.empty:
        for c in ("CAGR", "Vol", "MDD", "cur_dd"):
            if c in mdf:
                mdf[c] = (mdf[c] * 100).round(2)
        for c in ("Sharpe", "Sortino", "Calmar"):
            if c in mdf:
                mdf[c] = mdf[c].round(2)
        mdf = mdf.rename(columns={"CAGR": "CAGR %", "Vol": "Vol %",
                                  "MDD": "MaxDD %", "cur_dd": "CurDD %"})

    # annual returns (overlay + benchmarks)
    ann = None
    if overlay is not None:
        ann = pd.DataFrame({"v2.5 overlay":
                            overlay.groupby(overlay.index.year)
                            .apply(lambda x: (1 + x).prod() - 1)})
        for tk, r in bench_rets.items():
            ann[tk] = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)
        ann = (ann * 100).round(1)
        ann.index.name = "Year"
        ann = ann.reset_index()

    # rolling Sharpe latest
    roll = {}
    if overlay is not None and len(overlay) > 252:
        def _rs(x):
            return x.mean() / x.std(ddof=0) * np.sqrt(252) if x.std(ddof=0) > 0 else np.nan
        r1 = overlay.rolling(252).apply(_rs).dropna()
        r3 = overlay.rolling(252 * 3).apply(_rs).dropna()
        roll = {"sharpe_1y_latest": round(float(r1.iloc[-1]), 2) if len(r1) else None,
                "sharpe_3y_latest": round(float(r3.iloc[-1]), 2) if len(r3) else None}

    # the frozen 50-name book
    book = pd.read_csv(PORT) if PORT.exists() else None
    geo = {}
    book_html = "<p>current_portfolio_clean.csv not found</p>"
    if book is not None:
        b2 = book.copy()
        b2["mkt_cap_$B"] = (b2["market_cap_usd"] / 1e9).round(1)
        b2 = b2.sort_values("composite_score", ascending=False).reset_index(drop=True)
        b2.insert(0, "rk", range(1, len(b2) + 1))
        cols = [c for c in ["rk", "ticker", "long_name", "country", "sector",
                            "mkt_cap_$B", "composite_score", "score_Q",
                            "score_M", "roic", "mom_12_1", "vol_1y"]
                if c in b2.columns]
        book_html = _df_html(b2[cols].round(3))
        for key in ("country", "region", "sector", "currency"):
            if key in book.columns:
                geo[key] = book[key].value_counts().to_dict()

    cpnl = _read_series(COUNTRY_PNL)
    cpnl_html = ""
    if cpnl is not None:
        cp = cpnl.sort_values(ascending=False)
        top = cp.head(8).round(3).to_dict()
        bot = cp.tail(5).round(3).to_dict()
        cpnl_html = ("<b>Top:</b> " + ", ".join(f"{k} {v}" for k, v in top.items())
                     + "<br><b>Bottom:</b> "
                     + ", ".join(f"{k} {v}" for k, v in bot.items()))

    sub_html = ""
    if SUBPERIOD.exists():
        sp = pd.read_csv(SUBPERIOD)
        for c in ("cagr", "vol", "max_dd"):
            if c in sp.columns:
                sp[c] = (sp[c] * 100).round(1)
        sub_html = _df_html(sp.round(2))

    naked_last = naked.index[-1].date() if naked is not None else "n/a"
    ov_last = ov.get("asof", "n/a")

    # ---------- HTML ----------
    cards = [
        ("Exposure", f"{exp*100:.1f}%" if exp == exp else "n/a"),
        ("Vol scalar", f"{vs*100:.0f}%" if vs == vs else "n/a"),
        ("Trend filter", "ON" if trend_on else "OFF"),
        ("URTH / EEM",
         f"{'>' if ov.get('urth_above_sma') else '<'}SMA / "
         f"{'>' if ov.get('eem_above_sma') else '<'}SMA"),
        ("Book", f"{len(book) if book is not None else 0} names"),
        ("Overlay asof", str(ov_last)),
    ]
    cards_html = "".join(
        f'<div class="card"><div class="k">{k}</div>'
        f'<div class="v">{v}</div></div>' for k, v in cards)
    geo_html = ""
    for key, d in geo.items():
        items = ", ".join(f"{k}:{v}" for k, v in
                          sorted(d.items(), key=lambda kv: -kv[1]))
        geo_html += f"<p><b>{key.title()}</b> &mdash; {items}</p>"

    upd_banner = ""
    if upd.get("rc", 0) != 0:
        upd_banner = (f'<div class="banner">⚠️ daily_update refresh '
                      f'rc={upd.get("rc")} — snapshot built from existing '
                      f'data (overlay asof {ov_last}, naked last {naked_last}). '
                      f'Check connectivity.</div>')

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>GFE v2.5 — Daily Strategy Snapshot {date}</title><style>{_CSS}</style>
</head><body>
<h1>📈 Global Equity Bot v2.5 — Daily Strategy Snapshot</h1>
<div class="sub">{date} · account-decoupled (no broker) · overlay source
{ov_src or 'n/a'} · <b>Action: {_action(exp) if exp==exp else 'n/a'}</b></div>
{upd_banner}
<div class="cards">{cards_html}</div>

<h2>Validated metrics — overlay vs naked vs benchmarks</h2>
{_df_html(mdf) if not mdf.empty else '<p>no return series</p>'}

<h2>Annual returns (%)</h2>
{_df_html(ann) if ann is not None else '<p>n/a</p>'}

<h2>Rolling Sharpe (latest)</h2>
<p>1-year: <b>{roll.get('sharpe_1y_latest','n/a')}</b> &nbsp;·&nbsp;
3-year: <b>{roll.get('sharpe_3y_latest','n/a')}</b></p>

<h2>Geography &amp; sectors (frozen book)</h2>
{geo_html or '<p>n/a</p>'}

<h2>Historical country PnL contribution</h2>
<p>{cpnl_html or 'n/a'}</p>

<h2>Crisis subperiods (overlay applied)</h2>
{sub_html or '<p>n/a</p>'}

<h2>The 50 picks (frozen — quarterly reconstitution)</h2>
{book_html}

<div class="foot">Simulated / paper research. Not investment advice. No live
trading. Stock book frozen (quarterly); overlay refreshed daily from public
data only. Data freshness — overlay asof {ov_last}, naked series last
{naked_last}. Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}.
</div></body></html>"""

    # ---------- Markdown (git-diffable history) ----------
    md = [f"# GFE v2.5 — Daily Strategy Snapshot {date}",
          "",
          f"_Account-decoupled (no broker). Overlay source: {ov_src or 'n/a'}._",
          "",
          f"**Action:** {_action(exp) if exp==exp else 'n/a'}",
          "",
          "| Field | Value |", "|---|---|",
          f"| Exposure | {exp*100:.1f}% |" if exp == exp else "| Exposure | n/a |",
          f"| Vol scalar | {vs*100:.0f}% |" if vs == vs else "| Vol scalar | n/a |",
          f"| Trend filter | {'ON' if trend_on else 'OFF'} |",
          f"| URTH/EEM vs SMA | {'>' if ov.get('urth_above_sma') else '<'} / "
          f"{'>' if ov.get('eem_above_sma') else '<'} |",
          f"| Overlay asof | {ov_last} |",
          f"| Naked series last | {naked_last} |",
          f"| Book | {len(book) if book is not None else 0} names (frozen) |",
          f"| Rolling Sharpe 1y/3y | {roll.get('sharpe_1y_latest','n/a')} / "
          f"{roll.get('sharpe_3y_latest','n/a')} |",
          ""]
    if not mdf.empty:
        md.append("## Validated metrics")
        md.append(mdf.to_markdown(index=False))
        md.append("")
    md.append("_Simulated/paper. Not investment advice. No live trading._")

    # ---------- write dated + latest ----------
    outdir = DASH_DIR / date
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "index.html").write_text(html, encoding="utf-8")
    (outdir / "snapshot.md").write_text("\n".join(md), encoding="utf-8")
    metrics_json = {
        "date": date,
        "run_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "overlay": ov, "overlay_source": ov_src,
        "rolling": roll,
        "metrics": (mdf.to_dict(orient="records") if not mdf.empty else []),
        "geo": geo,
        "naked_last": str(naked_last),
        "daily_update_rc": upd.get("rc"),
    }
    (outdir / "metrics.json").write_text(json.dumps(metrics_json, indent=2,
                                                    default=str))
    if PORT.exists():
        shutil.copy2(PORT, outdir / "current_portfolio_clean.csv")
    js = sorted(DAILY_DIR.glob("*_overlay.json"))
    if js:
        shutil.copy2(js[-1], outdir / "overlay.json")

    latest = DASH_DIR / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    for f in outdir.iterdir():
        shutil.copy2(f, latest / f.name)

    log.info("snapshot written -> %s (and latest/)", outdir)
    return {"date": date, "dir": str(outdir), "exposure": exp,
            "naked_last": str(naked_last), "overlay_asof": str(ov_last),
            "sharpe_1y": roll.get("sharpe_1y_latest"),
            "daily_update_rc": upd.get("rc")}


def main() -> int:
    date = datetime.now().strftime("%Y-%m-%d")
    log = get_logger(date)
    log.info("=== DAILY STRATEGY CHECK start (%s) — account-decoupled ===", date)
    upd = run_daily_update(log)
    res = build_snapshot(log, upd)
    log.info("=== DAILY STRATEGY CHECK done -> %s ===", res["dir"])
    print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
