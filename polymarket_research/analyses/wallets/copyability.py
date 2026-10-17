"""Copyability: could a follower have profited AFTER observing mintblade / GRIMDRIP / endlessFate trades?

Exploratory reconstruction. There is no historical order book for Polymarket (CLOB /book is a
current snapshot only), so the follower's fill is proxied by the market's own subsequent taker prints.
Printed prices are not guaranteed executable quotes.

Method
- Signals: (a) every individual BUY fill of each wallet; (b) every market-episode (a wallet's first fill
  on one outcome token within an entry episode; episodes are fills on one match with gaps <= 10 min,
  as defined in ge_fills.parquet).
- Detection time t_d = fill block timestamp + delay, delay in {5 s, 30 s, 2 min, 15 min, 60 min}, plus an
  hourly monitor: t_d = next top of the hour at or after (timestamp + 5 s measured busted-poll latency).
  Measured latencies (notes/platform/data_infrastructure.md section 3): RTDS ~0.7-2 s, cache-busted Data API
  poll median 4.6 s (p90 6.5 s), naive cached poll median 112 s (max 302 s).
- Follower fill proxy: VWAP of taker BUY prints of the same token with block time in [t_d, t_d + 600 s],
  accumulated up to the follower's dollar size ($500 / $2,500 / $10,000). Each print's notional is treated
  as the liquidity available at that price. If the window holds less notional than the size, the remainder is
  priced at the CLOB /prices-history point at t_d plus a half-spread estimated from the tape (flagged).
  Sensitivities: 'ex_wallet' drops the followed wallet's own prints; 'buy_equiv' adds taker SELLs of the
  complement token (economically a buy of this token at 1 - price).
- Market state at t_d: closed (>= Gamma closedTime: not executable), post_match (>= event finishedTimestamp),
  in_play (>= kick-off; inferred actual kick-off where the reconstruction has one, else scheduled),
  pre_match. Also seconds to the next print of any kind in that market (book clear at start, pauses).
- P&L per signal = shares x payout - size - taker fee, fee = shares x rate x p x (1 - p) per print.
  Rate 0.03 = the market's current Gamma feeSchedule (sports_fees_v2) = the rate charged at the time
  (verified from the wallets' own fills); 0.05 = sports_fees_v3, what a comparable market created today pays.
  No taker rebates (a small follower would be at most Bronze tier).

Inputs: data/derived/ge_fills.parquet (all 1,871 fills of the three wallets), ge_markets.parquet,
ge_tape_taker_<cid10>.parquet, ge_prices_1m.parquet, mintblade_fills.parquet (inferred kick-offs).
Outputs (data/derived/): copyability_signals.parquet, copyability_agg.parquet, copyability_events.parquet,
copyability_fill_agg.parquet, copyability_hourly.parquet, copyability_curve.parquet, copyability_summary.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived"
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402  (only used if a price-history point is missing; cache=True)

DELAYS = {"5s": 5, "30s": 30, "2m": 120, "15m": 900, "60m": 3600, "hourly": None}
SIZES = (500.0, 2500.0, 10000.0)
WINDOW = 600            # seconds of prints accumulated after t_d
POLL_LAT = 5            # measured busted-poll latency (s) used for the hourly monitor
RATE_NOW, RATE_V3 = 0.03, 0.05
MODES = ("primary", "ex_wallet", "buy_equiv")


def ts(x) -> float:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    return pd.Timestamp(x).timestamp()


# ----------------------------------------------------------------------------- inputs
F = pd.read_parquet(OUT / "ge_fills.parquet").sort_values("timestamp").reset_index(drop=True)
M = pd.read_parquet(OUT / "ge_markets.parquet")
MB = pd.read_parquet(OUT / "mintblade_fills.parquet")
PH = pd.read_parquet(OUT / "ge_prices_1m.parquet")

# fee check: implied rate on the wallets' taker fills
tk = F[F.role == "taker"]
impl = tk.fee / (tk["size"] * tk.price * (1 - tk.price))
FEE_CHECK = {"n_taker_fills": int(len(tk)), "implied_rate_min": float(impl.min()), "implied_rate_max": float(impl.max())}
M["rate_schedule"] = M.feeSchedule.map(lambda s: json.loads(s)["rate"] if isinstance(s, str) else np.nan)

# kick-off: inferred actual where mintblade's reconstruction has one, else Gamma scheduled
ko_actual = {"fifwc-ksa-ury-2026-06-15": ts(MB.loc[MB.match.str.startswith("KSA"), "actual_start"].iloc[0]),
             "fifwc-irn-nzl-2026-06-15": ts(MB.loc[MB.match.str.startswith("IRN"), "actual_start"].iloc[0])}
mk = {}
for _, r in M.iterrows():
    toks, prices = api.jlist(r.clobTokenIds), [float(x) for x in api.jlist(r.outcomePrices)]
    mk[r.conditionId] = dict(
        question=r.question, match_key=r.match_key, tokens=toks, payout=dict(zip(toks, prices)),
        closed=ts(r.closedTime), finished=ts(r.event_finishedTimestamp), ko_sched=ts(r.gameStartTime),
        sdelay=float(r.secondsDelay or 0), rate=float(r.rate_schedule), clear_on_start=bool(r.clearBookOnStart))
fin_by_match = {}
for v in mk.values():
    if not np.isnan(v["finished"]):
        fin_by_match[v["match_key"]] = v["finished"]
for v in mk.values():
    v["ko"] = ko_actual.get(v["match_key"], v["ko_sched"])
    if np.isnan(v["finished"]):
        v["finished"] = fin_by_match.get(v["match_key"], np.nan)
    if np.isnan(v["finished"]):  # AUS-TUR spread: no finishedTimestamp on its "-more-markets" event (approximation)
        v["finished"] = min(v["closed"], v["ko"] + 7200)

TAPE = {cid: pd.read_parquet(OUT / f"ge_tape_taker_{cid[:10]}.parquet").sort_values("timestamp").reset_index(drop=True)
        for cid in F.condition_id.unique()}
ALL_TS = {cid: t.timestamp.to_numpy() for cid, t in TAPE.items()}


class Prints:
    """Cumulative arrays of the aggressive-buy prints for one token (one mode / exclusion)."""

    def __init__(self, df: pd.DataFrame):
        df = df.sort_values("timestamp")
        self.t = df.timestamp.to_numpy(dtype=np.int64)
        self.p = df.px.to_numpy(dtype=float)
        q = df["size"].to_numpy(dtype=float)
        z = np.zeros(1)
        self.CN = np.concatenate([z, np.cumsum(q * self.p)])
        self.CQ = np.concatenate([z, np.cumsum(q)])
        self.CF = np.concatenate([z, np.cumsum(q * self.p * (1 - self.p))])

    def fill(self, t_d: float, size: float):
        i0 = np.searchsorted(self.t, t_d, "left")
        i1 = np.searchsorted(self.t, t_d + WINDOW, "right")
        avail = self.CN[i1] - self.CN[i0]
        if i1 == i0:
            return dict(shares=0.0, F=0.0, filled=0.0, n_prints=0, first_print=np.nan, last_print=np.nan)
        if avail >= size:
            target = self.CN[i0] + size
            k = int(np.searchsorted(self.CN, target, "left"))  # prints i0..k-1 used, k-1 partial
            take = target - self.CN[k - 1]
            pk = self.p[k - 1]
            sh = self.CQ[k - 1] - self.CQ[i0] + take / pk
            Fv = self.CF[k - 1] - self.CF[i0] + take / pk * pk * (1 - pk)
            return dict(shares=sh, F=Fv, filled=size, n_prints=k - i0, first_print=self.t[i0], last_print=self.t[k - 1])
        return dict(shares=self.CQ[i1] - self.CQ[i0], F=self.CF[i1] - self.CF[i0], filled=avail,
                    n_prints=i1 - i0, first_print=self.t[i0], last_print=self.t[i1 - 1])


_cache: dict = {}


def prints(cid: str, tok: str, mode: str, wallet: str) -> Prints:
    key = (cid, tok, mode, wallet if mode == "ex_wallet" else "")
    if key not in _cache:
        t = TAPE[cid]
        a = t[(t.token_id == tok) & (t.side == "BUY")].assign(px=lambda d: d.price)
        if mode == "ex_wallet":
            a = a[a.proxy_wallet != wallet]
        if mode == "buy_equiv":
            b = t[(t.token_id != tok) & (t.side == "SELL")].assign(px=lambda d: 1 - d.price)
            a = pd.concat([a, b])
        a = a[(a.px > 0) & (a.px < 1)]
        _cache[key] = Prints(a)
    return _cache[key]


def half_spread(cid: str, tok: str, t_d: float) -> float:
    """Tape-based half-spread: (median ask-side print - median bid-side print) / 2 within +-15 min."""
    t = TAPE[cid]
    w = t[(t.timestamp >= t_d - 900) & (t.timestamp <= t_d + 900)]
    same = w.token_id == tok
    ask = pd.concat([w[same & (w.side == "BUY")].price, 1 - w[~same & (w.side == "SELL")].price])
    bid = pd.concat([w[same & (w.side == "SELL")].price, 1 - w[~same & (w.side == "BUY")].price])
    if len(ask) < 3 or len(bid) < 3:
        return 0.005
    return float(np.clip((ask.median() - bid.median()) / 2, 0.0005, 0.02))


PH_BY = {tok: g.sort_values("t") for tok, g in PH.groupby("token_id")}


def ph_price(tok: str, t_d: float) -> float:
    g = PH_BY.get(tok)
    if g is None or not len(g) or t_d < g.t.min() - 600 or t_d > g.t.max() + 600:
        h = api.prices_history(tok, int(t_d - 3600), int(t_d + 600), 1, cache=True)
        g = pd.DataFrame(h)
        if not len(g):
            return np.nan
    x = g[g.t <= t_d]
    return float(x.p.iloc[-1]) if len(x) else float(g.p.iloc[0])


def state(m: dict, t: float) -> str:
    if t >= m["closed"]:
        return "closed"
    if not np.isnan(m["finished"]) and t >= m["finished"]:
        return "post_match"
    if t >= m["ko"]:
        return "in_play"
    return "pre_match"


def td_of(t0: float, dkey: str) -> float:
    if DELAYS[dkey] is not None:
        return t0 + DELAYS[dkey]
    return float(np.ceil((t0 + POLL_LAT) / 3600.0) * 3600.0)


def follow(cid, tok, wallet, t0, t_d, size, mode):
    m = mk[cid]
    st = state(m, t_d)
    nxt_i = np.searchsorted(ALL_TS[cid], t_d, "left")
    gap = float(ALL_TS[cid][nxt_i] - t_d) if nxt_i < len(ALL_TS[cid]) else np.nan
    base = dict(state_td=st, sec_to_next_print=gap)
    if st == "closed":
        return dict(base, executable=False, shares=0.0, fee03=0.0, fee05=0.0, follower_px=np.nan, frac_prints=0.0,
                    fallback=False, n_prints=0, fill_secs=np.nan, ph_px=np.nan, half_spread=np.nan)
    # orders placed in play wait secondsDelay before matching (current Gamma value; historical value unknown)
    t_eff = t_d + (m["sdelay"] if st == "in_play" else 0.0)
    r = prints(cid, tok, mode, wallet).fill(t_eff, size)
    sh, Fv, filled = r["shares"], r["F"], r["filled"]
    fb, php, hs = False, np.nan, np.nan
    if filled < size - 1e-9:
        fb = True
        php = ph_price(tok, t_d)
        hs = half_spread(cid, tok, t_d)
        if np.isnan(php):
            return dict(base, executable=False, shares=0.0, fee03=0.0, fee05=0.0, follower_px=np.nan, frac_prints=filled / size,
                        fallback=True, n_prints=r["n_prints"], fill_secs=np.nan, ph_px=php, half_spread=hs)
        pf = float(np.clip(php + hs, 0.001, 0.999))
        sh += (size - filled) / pf
        Fv += (size - filled) / pf * pf * (1 - pf)
    return dict(base, executable=True, shares=sh, fee03=RATE_NOW * Fv, fee05=RATE_V3 * Fv, follower_px=size / sh,
                frac_prints=filled / size, fallback=fb, n_prints=r["n_prints"],
                fill_secs=(r["last_print"] - t_d) if r["n_prints"] else np.nan, ph_px=php, half_spread=hs)


# ----------------------------------------------------------------------------- signals
F["ts0"] = F.timestamp.astype(float)
F["fill_id"] = np.arange(len(F))
ep = (F.groupby(["label", "proxy_wallet", "episode_id", "match_key", "condition_id", "token_id", "question", "outcome"], as_index=False)
      .agg(t0=("ts0", "min"), t_last=("ts0", "max"), n_fills=("ts0", "size"), shares_w=("size", "sum"), notional_w=("notional", "sum"),
           fees_w=("fee", "sum"), payout=("payout", "first")))
ep["wallet_vwap"] = ep.notional_w / ep.shares_w
_first = F.groupby(["episode_id", "token_id"]).price.first()
ep["trig_px"] = [_first[(e, t)] for e, t in zip(ep.episode_id, ep.token_id)]
ep["signal_id"] = ep.episode_id + "|" + ep.outcome
fl = F.assign(t0=F.ts0, wallet_vwap=F.price, trig_px=F.price, signal_id=F.label + "|fill" + F.fill_id.astype(str))


def close_px(tok: str, cid: str) -> float:
    """Closing line: last CLOB prices-history point at or before kick-off (trade/mid series, not a quote)."""
    return ph_price(tok, mk[cid]["ko"])


CLOSE = {(c, t): close_px(t, c) for c, t in F[["condition_id", "token_id"]].drop_duplicates().itertuples(index=False)}

rows = []
for level, S in (("episode", ep), ("fill", fl)):
    for _, s in S.iterrows():
        m = mk[s.condition_id]
        assert abs(m["payout"][s.token_id] - s.payout) < 1e-9
        sig_state = state(m, s.t0)
        for dkey in DELAYS:
            t_d = td_of(s.t0, dkey)
            for size in SIZES:
                for mode in MODES:
                    if level == "fill" and mode != "primary":
                        continue
                    r = follow(s.condition_id, s.token_id, s.proxy_wallet, s.t0, t_d, size, mode)
                    rows.append(dict(level=level, wallet=s.label, signal_id=s.signal_id, episode_id=s.episode_id,
                                     match_key=s.match_key, question=s.question, outcome=s.outcome,
                                     role=(s.role if level == "fill" else None), t0=s.t0, signal_state=sig_state,
                                     ko=m["ko"], finished=m["finished"], closed=m["closed"], min_t0_to_ko=(m["ko"] - s.t0) / 60,
                                     delay=dkey, delay_s=t_d - s.t0, t_d=t_d, size=size, mode=mode, payout=s.payout,
                                     wallet_vwap=s.wallet_vwap, trig_px=s.trig_px,
                                     close_px=CLOSE[(s.condition_id, s.token_id)], **r))
D = pd.DataFrame(rows)
ex = D.executable
D["gross"] = np.where(ex, D.shares * D.payout - D["size"], 0.0)
D["net03"] = D.gross - D.fee03
D["net05"] = D.gross - D.fee05
D["deployed03"] = np.where(ex, D["size"] + D.fee03, 0.0)
D["deployed05"] = np.where(ex, D["size"] + D.fee05, 0.0)
D["deterioration_c"] = (D.follower_px - D.wallet_vwap) * 100
# the wallet's own outcome at the same dollar size (its VWAP, fee 0.03 x p(1-p) on all shares: upper bound
# for its fee because maker fills paid none)
wsh = D["size"] / D.wallet_vwap
D["wallet_net03"] = wsh * D.payout - D["size"] - RATE_NOW * wsh * D.wallet_vwap * (1 - D.wallet_vwap)
D["wallet_deployed03"] = D["size"] + RATE_NOW * wsh * D.wallet_vwap * (1 - D.wallet_vwap)
D["at_sched_ko"] = (D.t_d >= D.ko) & (D.t_d < D.ko + 300) & ~D.match_key.isin(list(ko_actual))
D["skip_started"] = (D.signal_state == "pre_match") & D.state_td.isin(["in_play", "post_match", "closed"])
D["det_vs_trig_c"] = (D.follower_px - D.trig_px) * 100
# closing-line value: only for pre-match executions (the close is the last pre-kick-off price)
pm = ex & (D.state_td == "pre_match")
D["clv_c"] = np.where(pm, (D.close_px - D.follower_px) * 100, np.nan)
D["ev_net03"] = np.where(pm, D.shares * (D.close_px - D.follower_px) - D.fee03, np.nan)
D["wallet_clv_c"] = np.where(D.signal_state == "pre_match", (D.close_px - D.wallet_vwap) * 100, np.nan)
D.to_parquet(OUT / "copyability_signals.parquet", index=False)


# ----------------------------------------------------------------------------- aggregation
def agg(g: pd.DataFrame, rule: str) -> dict:
    x = g[g.executable & ~g.skip_started] if rule == "pre_match_only" else g[g.executable]
    evt = x.groupby("match_key").agg(net03=("net03", "sum"), net05=("net05", "sum"), dep=("deployed03", "sum"),
                                     t=("finished", "first"))
    evt = evt.sort_values("t")
    cum = evt.net03.cumsum()
    dep = x.deployed03.sum()
    return dict(
        signals=int(g.signal_id.nunique()), executed=int(len(x)), independent_events=int(x.match_key.nunique()),
        not_executable=int((~g.executable).sum()), skipped_started=int(g.skip_started.sum()) if rule == "pre_match_only" else 0,
        fallback=int(x.fallback.sum()), executed_in_play=int((x.state_td == "in_play").sum()),
        executed_post_match=int((x.state_td == "post_match").sum()),
        deployed=dep, gross=x.gross.sum(), fees03=x.fee03.sum(), net03=x.net03.sum(), net05=x.net05.sum(),
        roi03=x.net03.sum() / dep if dep else np.nan, roi05=x.net05.sum() / x.deployed05.sum() if dep else np.nan,
        net_per_1000_03=1000 * x.net03.sum() / dep if dep else np.nan, net_per_1000_05=1000 * x.net05.sum() / x.deployed05.sum() if dep else np.nan,
        events_net_positive=int((evt.net03 > 0).sum()), worst_event_net03=evt.net03.min() if len(evt) else np.nan,
        worst_cum_net03=min(0.0, cum.min()) if len(cum) else np.nan,
        mean_det_c=x.deterioration_c.mean(), median_det_c=x.deterioration_c.median(), max_det_c=x.deterioration_c.max(),
        mean_follower_px=x.follower_px.mean(), mean_wallet_vwap=x.wallet_vwap.mean(),
        wallet_net03=x.wallet_net03.sum(), wallet_roi03=x.wallet_net03.sum() / x.wallet_deployed03.sum() if len(x) else np.nan,
        mean_delay_s=x.delay_s.mean(), mean_det_vs_trig_c=x.det_vs_trig_c.mean(),
        n_clv=int(x.clv_c.notna().sum()), mean_clv_c=x.clv_c.mean(), mean_wallet_clv_c=x.wallet_clv_c.mean(),
        ev_net_per_1000_03=1000 * x.ev_net03.sum() / x[x.ev_net03.notna()].deployed03.sum() if x.ev_net03.notna().any() else np.nan)


E = D[D.level == "episode"]
pool = pd.concat([E, E.assign(wallet="POOLED")])
A = []
for (w, dk, size, mode), g in pool.groupby(["wallet", "delay", "size", "mode"]):
    for rule in ("mechanical", "pre_match_only"):
        A.append(dict(wallet=w, delay=dk, size=size, mode=mode, rule=rule, **agg(g, rule)))
# the wallets' own entries as a 0-delay reference (their VWAP, same dollar size)
for (w, size), g in pool[(pool["mode"] == "primary") & (pool.delay == "5s")].groupby(["wallet", "size"]):
    dep = g.wallet_deployed03.sum()
    evt = g.groupby("match_key").wallet_net03.sum()
    A.append(dict(wallet=w, delay="wallet_own", size=size, mode="wallet_vwap", rule="mechanical", signals=int(len(g)),
                  executed=int(len(g)), independent_events=int(g.match_key.nunique()), deployed=dep, net03=g.wallet_net03.sum(),
                  roi03=g.wallet_net03.sum() / dep, net_per_1000_03=1000 * g.wallet_net03.sum() / dep,
                  events_net_positive=int((evt > 0).sum()), worst_event_net03=evt.min(), mean_det_c=0.0))
A = pd.DataFrame(A)
A.to_parquet(OUT / "copyability_agg.parquet", index=False)

EV = (E.groupby(["wallet", "match_key", "delay", "size", "mode"], as_index=False)
      .agg(legs=("signal_id", "size"), executed=("executable", "sum"), states=("state_td", lambda s: ",".join(sorted(set(s)))),
           deployed=("deployed03", "sum"), net03=("net03", "sum"), net05=("net05", "sum"), wallet_net03=("wallet_net03", "sum"),
           mean_det_c=("deterioration_c", "mean"), payout=("payout", "mean")))
EV.to_parquet(OUT / "copyability_events.parquet", index=False)

# fill level: equal dollars per fill; also event-weighted (each match's ROI averaged)
Fl = D[(D.level == "fill") & (D["mode"] == "primary")]
FA = []
for (w, dk, size, rule), g in pd.concat([Fl.assign(rule=r) for r in ("mechanical", "pre_match_only")] +
                                        [Fl.assign(rule=r, wallet="POOLED") for r in ("mechanical", "pre_match_only")]
                                        ).groupby(["wallet", "delay", "size", "rule"]):
    x = g[g.executable & ~g.skip_started] if rule == "pre_match_only" else g[g.executable]
    if not len(x):
        continue
    ev_roi = x.groupby("match_key").apply(lambda h: h.net03.sum() / h.deployed03.sum(), include_groups=False)
    FA.append(dict(wallet=w, delay=dk, size=size, rule=rule, fills=int(len(g)), executed=int(len(x)), events=int(x.match_key.nunique()),
                   fallback=int(x.fallback.sum()), in_play=int((x.state_td == "in_play").sum()),
                   post_match=int((x.state_td == "post_match").sum()), closed=int((~g.executable).sum()),
                   mean_det_c=x.deterioration_c.mean(), median_det_c=x.deterioration_c.median(),
                   p90_det_c=x.deterioration_c.quantile(0.9), share_det_gt_1c=(x.deterioration_c > 1).mean(),
                   mean_det_c_taker=x[x.role == "taker"].deterioration_c.mean(), mean_det_c_maker=x[x.role == "maker"].deterioration_c.mean(),
                   net_per_1000_03=1000 * x.net03.sum() / x.deployed03.sum(), net_per_1000_05=1000 * x.net05.sum() / x.deployed05.sum(),
                   event_weighted_net_per_1000_03=1000 * ev_roi.mean(),
                   wallet_net_per_1000_03=1000 * x.wallet_net03.sum() / x.wallet_deployed03.sum(),
                   mean_clv_c=x.clv_c.mean(), mean_wallet_clv_c=x.wallet_clv_c.mean(), n_clv=int(x.clv_c.notna().sum()),
                   ev_net_per_1000_03=1000 * x.ev_net03.sum() / x[x.ev_net03.notna()].deployed03.sum() if x.ev_net03.notna().any() else np.nan))
FA = pd.DataFrame(FA)
FA.to_parquet(OUT / "copyability_fill_agg.parquet", index=False)

# hourly monitor distribution
H = D[(D.delay == "hourly") & (D["size"] == 2500) & (D["mode"] == "primary")]
H[["level", "wallet", "signal_id", "match_key", "t0", "t_d", "delay_s", "signal_state", "state_td", "min_t0_to_ko",
   "follower_px", "wallet_vwap", "deterioration_c", "net03", "sec_to_next_print"]].to_parquet(OUT / "copyability_hourly.parquet", index=False)

# fine delay grid for the market-episode signals ($2,500, primary prints)
GRID = [0, 5, 15, 30, 60, 120, 180, 300, 450, 600, 900, 1200, 1800, 2700, 3600, 5400, 7200]
C = []
for _, s in ep.iterrows():
    for d in GRID:
        r = follow(s.condition_id, s.token_id, s.proxy_wallet, s.t0, s.t0 + d, 2500.0, "primary")
        C.append(dict(wallet=s.label, signal_id=s.signal_id, match_key=s.match_key, delay_s=d, wallet_vwap=s.wallet_vwap,
                      min_t0_to_ko=(mk[s.condition_id]["ko"] - s.t0) / 60, payout=s.payout,
                      state_td=r["state_td"], follower_px=r["follower_px"], fallback=r["fallback"],
                      deterioration_c=(r["follower_px"] - s.wallet_vwap) * 100))
C = pd.DataFrame(C)
C.to_parquet(OUT / "copyability_curve.parquet", index=False)

# capacity: taker BUY notional by everyone except the followed wallet between its first fill and kick-off
CAP = []
for _, s in ep.iterrows():
    m = mk[s.condition_id]
    t = TAPE[s.condition_id]
    end = min(m["ko"], s.t0 + 3600) if s.t0 < m["ko"] else s.t0 + 900
    w = t[(t.token_id == s.token_id) & (t.side == "BUY") & (t.timestamp > s.t0) & (t.timestamp < end)]
    oth = w[w.proxy_wallet != s.proxy_wallet]
    CAP.append(dict(wallet=s.label, signal_id=s.signal_id, match_key=s.match_key, window_min=(end - s.t0) / 60,
                    wallet_notional_episode=s.notional_w, others_buy_notional=float((oth["size"] * oth.price).sum()),
                    others_buy_prints=int(len(oth)), wallet_buy_notional_in_window=float(((w["size"] * w.price)[w.proxy_wallet == s.proxy_wallet]).sum())))
CAP = pd.DataFrame(CAP)
CAP.to_parquet(OUT / "copyability_capacity.parquet", index=False)

# trading gaps around kick-off (book is cleared on start: clearBookOnStart=true on all 13 markets)
GAP = []
for cid, m in mk.items():
    a = ALL_TS[cid]
    w = a[(a >= m["ko"] - 300) & (a <= m["ko"] + 900)]
    g = np.diff(w) if len(w) > 1 else np.array([np.nan])
    i = int(np.nanargmax(g)) if len(w) > 1 else 0
    GAP.append(dict(match_key=m["match_key"], question=m["question"], ko=pd.Timestamp(m["ko"], unit="s"), prints_window=int(len(w)),
                    max_gap_s=float(np.nanmax(g)), max_gap_start_rel_ko_s=float(w[i] - m["ko"]) if len(w) > 1 else np.nan,
                    seconds_delay_now=m["sdelay"], clear_on_start=m["clear_on_start"]))
GAP = pd.DataFrame(GAP)
GAP.to_parquet(OUT / "copyability_ko_gaps.parquet", index=False)

# latency budget per market-episode signal: first grid delay at which the follower's price is more than
# 1c / 2c worse than the wallet's triggering fill, or the match has started (pre-match signals)
C = C.merge(ep[["signal_id", "trig_px"]], on="signal_id")
C["det_vs_trig_c"] = (C.follower_px - C.trig_px) * 100
LB = []
for sid, g in C.sort_values("delay_s").groupby("signal_id"):
    def first(mask):
        z = g[mask]
        return float(z.delay_s.iloc[0]) if len(z) else np.nan
    LB.append(dict(wallet=g.wallet.iloc[0], signal_id=sid, match_key=g.match_key.iloc[0], min_t0_to_ko=g.min_t0_to_ko.iloc[0],
                   signal_state=("pre_match" if g.min_t0_to_ko.iloc[0] > 0 else "in_play"),
                   first_delay_gt1c=first(g.det_vs_trig_c > 1), first_delay_gt2c=first(g.det_vs_trig_c > 2),
                   first_delay_started=first(g.state_td != "pre_match"),
                   det_at_5s=float(g[g.delay_s == 5].det_vs_trig_c.iloc[0]), det_at_15m=float(g[g.delay_s == 900].det_vs_trig_c.iloc[0])))
LB = pd.DataFrame(LB)
LB.to_parquet(OUT / "copyability_latency_budget.parquet", index=False)


# zero-edge null for the follower: each match's outcome drawn from probabilities implied by the follower's own
# entry prices (nested legs of one match handled jointly through explicit match states)
def match_states(g: pd.DataFrame):
    """Return (state probabilities, {token_question_outcome: payout vector}) for one match."""
    px = g.groupby(["question", "outcome"]).follower_px.mean()
    q = {k[0]: (k[1], v) for k, v in px.items()}
    mkey = g.match_key.iloc[0]
    if mkey == "fifwc-ksa-ury-2026-06-15":
        p_no = px.get(("Will Uruguay win on 2026-06-15?", "No"), np.nan)
        p_d = px.get(("Will Saudi Arabia vs. Uruguay end in a draw?", "Yes"), np.nan)
        p_s = px.get(("Spread: Uruguay (-1.5)", "Saudi Arabia"), np.nan)
        # states: KSA win, draw, URU by 1, URU by 2+
        pr = np.array([p_no - p_d, p_d, p_s - p_no, 1 - p_s])
        pay = {("Will Uruguay win on 2026-06-15?", "No"): [1, 1, 0, 0],
               ("Will Saudi Arabia vs. Uruguay end in a draw?", "Yes"): [0, 1, 0, 0],
               ("Spread: Uruguay (-1.5)", "Saudi Arabia"): [1, 1, 1, 0]}
    elif mkey == "fifwc-cze-rsa-2026-06-18" and len(px) == 2:
        p_no = px[("Will Czechia win on 2026-06-18?", "No")]
        p_d = px[("Will Czechia vs. South Africa end in a draw?", "Yes")]
        pr = np.array([1 - p_no, p_d, p_no - p_d])          # CZE win, draw, RSA win
        pay = {("Will Czechia win on 2026-06-18?", "No"): [0, 1, 1],
               ("Will Czechia vs. South Africa end in a draw?", "Yes"): [0, 1, 0]}
    else:
        assert len(px) == 1, mkey
        k, p1 = next(iter(px.items()))
        pr, pay = np.array([p1, 1 - p1]), {k: [1, 0]}
    pr = np.where(np.isnan(pr), 0.0, pr)
    pr = np.clip(pr, 0.005, None)
    return pr / pr.sum(), pay


def null_mc(x: pd.DataFrame, price_col="follower_px", n=200_000, seed=7):
    rng = np.random.default_rng(seed)
    x = x[x.executable].copy()
    if price_col != "follower_px":
        x["follower_px"] = x[price_col]
    tot = np.zeros(n)
    obs = 0.0
    for mkey, g in x.groupby("match_key"):
        pr, pay = match_states(g)
        st = rng.choice(len(pr), size=n, p=pr)
        for _, r in g.iterrows():
            sh = r["size"] / r.follower_px
            fee = RATE_NOW * sh * r.follower_px * (1 - r.follower_px)
            pv = np.array(pay[(r.question, r.outcome)], dtype=float)
            tot += sh * pv[st] - r["size"] - fee
            obs += sh * r.payout - r["size"] - fee
    return dict(observed=obs, null_mean=tot.mean(), null_sd=tot.std(), p_ge_observed=float((tot >= obs - 1e-6).mean()),
                p_gt_0=float((tot > 0).mean()))


NULL = []
base = E[(E["mode"] == "primary") & (E["size"] == 2500)]
for w in ("mintblade", "GRIMDRIP", "endlessFate", "POOLED"):
    bw = base if w == "POOLED" else base[base.wallet == w]
    for dk in ("5s", "2m", "15m", "60m", "hourly"):
        NULL.append(dict(wallet=w, delay=dk, basis="follower_price", **null_mc(bw[bw.delay == dk])))
    NULL.append(dict(wallet=w, delay="wallet_own", basis="wallet_vwap", **null_mc(bw[bw.delay == "5s"], price_col="wallet_vwap")))
NULL = pd.DataFrame(NULL)
NULL.to_parquet(OUT / "copyability_null.parquet", index=False)

# ----------------------------------------------------------------------------- summary
summ = {"fee_check": FEE_CHECK, "schedule_rates": sorted(M.rate_schedule.unique().tolist()),
        "n_fills": int(len(F)), "n_episode_signals": int(len(ep)),
        "fallback_share_episode_primary": float(E[(E["mode"] == "primary") & E.executable].fallback.mean()),
        "fallback_share_fill": float(Fl[Fl.executable].fallback.mean()),
        "ko_used": {v["match_key"]: pd.Timestamp(v["ko"], unit="s").isoformat() for v in mk.values()}}
(OUT / "copyability_summary.json").write_text(json.dumps(summ, indent=1, default=str))
pd.set_option("display.width", 250)
k = A[(A["mode"].isin(["primary", "wallet_vwap"])) & (A["size"] == 2500) & (A.rule == "mechanical")]
print(k[["wallet", "delay", "executed", "independent_events", "fallback", "executed_in_play", "net03", "net_per_1000_03",
         "net_per_1000_05", "worst_event_net03", "mean_det_c"]].round(2).to_string(index=False))
print(json.dumps(summ, default=str)[:800])
