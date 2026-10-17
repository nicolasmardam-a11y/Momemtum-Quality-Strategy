"""Descriptive statistics of the resolved-market universe (tables for notes/strategies/universe.md).

Run from polymarket_research/: python analyses/universe/05_stats.py > <out.md>
Reads data/derived/markets_resolved.parquet, events_resolved.parquet, universe_build_stats.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DER = ROOT / "data" / "derived"
CATS = ["sports", "crypto", "politics", "finance", "economics", "culture", "weather", "tech", "mentions",
        "geopolitics", "other"]
COLS = ["endDate", "closedTime", "gameStartTime", "startDate", "category", "category_fee",
        "category_rule", "category_source", "feesEnabled", "feeType", "fee_rate", "fee_exponent", "fee_rebate_rate",
        "structure", "negRisk", "resolution", "has_disputed", "multi_proposal", "dispute_flag", "n_proposed",
        "umaResolutionStatus", "settle_lag_h", "settle_lag_game_h", "volumeNum", "liquidityNum", "end_quarter", "split",
        "parse_ok", "event_id", "n_events", "version", "event_version", "restricted", "automaticallyResolved",
        "sportsMarketType", "n_outcomes", "enableOrderBook", "secondsDelay", "orderPriceMinTickSize", "duration_h",
        "rewardsMinSize", "rewardsMaxSpread", "closed", "archived", "cluster_id", "cluster_source", "cluster_week",
        "n_proposal_rounds", "dup_proposal_record", "traded"]


def md(df: pd.DataFrame, floatfmt: str = "{:,.0f}") -> str:
    d = df.copy()
    out = ["| " + " | ".join([str(d.index.name or "")] + [str(c) for c in d.columns]) + " |",
           "|" + "---|" * (len(d.columns) + 1)]
    for idx, r in d.iterrows():
        cells = []
        for v in r.values:
            if isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join([str(idx)] + cells) + " |")
    return "\n".join(out)


def pct(x) -> str:
    return f"{100 * x:.1f}%"


def main() -> None:
    import pyarrow.parquet as pq
    import pyarrow.compute as pc
    m = pq.read_table(DER / "markets_resolved.parquet", columns=COLS).to_pandas(strings_to_categorical=True)
    for c in m.columns:  # low-cardinality strings back to plain (arrow-backed) str for comparisons
        if isinstance(m[c].dtype, pd.CategoricalDtype) and c not in ("event_id", "cluster_id"):
            m[c] = m[c].astype("str").where(m[c].notna(), None)
    n_no_tags = int(pc.sum(pc.equal(pc.list_value_length(pq.read_table(DER / "markets_resolved.parquet", columns=["tags"])["tags"]), 0)).as_py() or 0)
    m["id"] = np.arange(len(m))  # row counter for size aggregations (Gamma ids are not needed here)
    cid = pq.read_table(DER / "markets_resolved.parquet", columns=["condition_id"])["condition_id"]
    n_cid_null = int(cid.null_count)
    n_cid_dupes = int(len(cid) - n_cid_null - len(pc.unique(cid.drop_null())))
    del cid
    ev = pd.read_parquet(DER / "events_resolved.parquet")
    st = json.loads((DER / "universe_build_stats.json").read_text())
    p = print
    N = len(m)
    p(f"## Totals\n\nmarkets={N:,}  events(referenced)={m['event_id'].nunique():,}  events in events_resolved={len(ev):,}")
    p(f"build stats: { {k: v for k, v in st.items() if k != 'rows_by_window'} }\n")
    p(md(m.groupby("split").agg(markets=("id", "size"), events=("event_id", "nunique"),
                                volume_usd=("volumeNum", "sum")).reindex(["train", "validation", "test"])))

    p("\n## Leakage clusters by split (cluster_id: sports game stem > event_id > negRiskMarketID > condition_id)\n")
    p(md(m.groupby("split").agg(markets=("id", "size"), clusters=("cluster_id", "nunique"), events=("event_id", "nunique"),
                                weeks=("cluster_week", "nunique")).reindex(["train", "validation", "test"])))
    p("\ncluster_source shares:\n")
    p(md(m["cluster_source"].value_counts(normalize=True).to_frame("share"), "{:.4f}"))

    # ---- category x quarter
    ct = pd.crosstab(m["end_quarter"], m["category"]).reindex(columns=CATS, fill_value=0)
    ct["total"] = ct.sum(axis=1)
    ct.loc["total"] = ct.sum()
    ct.index.name = "quarter"
    p("\n## Markets by category x endDate quarter (all markets)\n")
    p(md(ct))
    mv = m.loc[m["volumeNum"].fillna(0) >= 10_000, ["end_quarter", "category"]]
    ct2 = pd.crosstab(mv["end_quarter"], mv["category"]).reindex(columns=CATS, fill_value=0)
    ct2["total"] = ct2.sum(axis=1)
    ct2.loc["total"] = ct2.sum()
    ct2.index.name = "quarter"
    p("\n## Markets with volumeNum >= $10k by category x quarter\n")
    p(md(ct2))
    vq = m.pivot_table(index="end_quarter", columns="category", values="volumeNum", aggfunc="sum").reindex(columns=CATS) / 1e6
    vq["total"] = vq.sum(axis=1)
    vq.index.name = "quarter"
    p("\n## Gamma volumeNum ($M) by category x quarter\n")
    p(md(vq, "{:,.1f}"))

    # ---- category source
    cs = pd.crosstab(m["end_quarter"], m["category_source"], normalize="index")
    p("\n## Category source share by quarter (feeType vs tag rule)\n")
    p(md(cs, "{:.3f}"))

    # ---- fees
    p("\n## Fee-enabled share by quarter (all markets; and volume-weighted)\n")
    fe = m[["end_quarter", "feesEnabled", "volumeNum", "fee_rate"]].assign(fe=m["feesEnabled"].fillna(False).astype(bool), v=m["volumeNum"].fillna(0))
    g = fe.groupby("end_quarter").apply(lambda d: pd.Series({
        "markets": len(d), "share_fee_enabled": d["fe"].mean(),
        "vol_share_fee_enabled": (d["v"] * d["fe"]).sum() / max(d["v"].sum(), 1e-9),
        "share_feeSchedule_present": d["fee_rate"].notna().mean()}), include_groups=False)
    p(md(g, "{:.3f}"))
    t = m.loc[m["split"] == "test", ["id", "category", "feesEnabled", "fee_rate", "feeType", "fee_exponent", "fee_rebate_rate"]]
    p("\n### TEST period (2026-01-01..2026-10-15) fee schedule by category: share fee-enabled, (rate, exponent, rebate) combos\n")
    tt = t.assign(fe=t["feesEnabled"].fillna(False).astype(bool))
    p(md(tt.groupby("category").agg(markets=("id", "size"), share_fee_enabled=("fe", "mean"),
                                    median_rate=("fee_rate", "median")).reindex(CATS), "{:.3f}"))
    combos = t.groupby(["feeType", "fee_rate", "fee_exponent", "fee_rebate_rate"], dropna=False).size().sort_values(ascending=False)
    p("\nfeeType x (rate, exponent, rebateRate) in TEST, top 25:\n")
    p(md(combos.head(25).to_frame("markets").reset_index().set_index("feeType"), "{:.4g}"))
    ftq = pd.crosstab(m["end_quarter"], m["feeType"].astype("string").fillna("None"))
    p("\nfeeType by quarter:\n")
    p(md(ftq))

    # ---- structure
    p("\n## Market structure share by quarter\n")
    p(md(pd.crosstab(m["end_quarter"], m["structure"], normalize="index"), "{:.3f}"))
    p("\nStructure by category (all periods):\n")
    p(md(pd.crosstab(m["category"], m["structure"], normalize="index").reindex(CATS), "{:.3f}"))

    # ---- resolution / disputes
    p("\n## Resolution outcome counts by quarter\n")
    rq = pd.crosstab(m["end_quarter"], m["resolution"])
    rq["split_share"] = rq.get("split_50_50", 0) / rq.sum(axis=1)
    p(md(rq, "{:,.4f}"))
    p("\nResolution by category (share):\n")
    p(md(pd.crosstab(m["category"], m["resolution"], normalize="index").reindex(CATS), "{:.4f}"))
    p("\numaResolutionStatus counts:\n")
    p(md(m["umaResolutionStatus"].astype("string").fillna("None").value_counts().to_frame("markets")))
    p("\n## Dispute incidence by quarter (has_disputed = 'disputed' in umaResolutionStatuses; multi_proposal = >1 'proposed')\n")
    dq = m.groupby("end_quarter").agg(markets=("id", "size"), has_disputed=("has_disputed", "mean"),
                                      multi_proposal=("multi_proposal", "mean"), dispute_flag_broad=("dispute_flag", "mean"))
    p(md(dq, "{:.4f}"))
    p("\nDispute incidence by category:\n")
    dc = m.groupby("category").agg(markets=("id", "size"), has_disputed=("has_disputed", "mean"),
                                   multi_proposal=("multi_proposal", "mean"), split_50_50=("resolution", lambda s: (s == "split_50_50").mean())).reindex(CATS)
    p(md(dc, "{:.4f}"))
    mv2 = m.loc[m["volumeNum"].fillna(0) >= 10_000, ["id", "category", "has_disputed", "multi_proposal", "resolution"]]
    dcv = mv2.groupby("category").agg(markets=("id", "size"), has_disputed=("has_disputed", "mean"),
                                      multi_proposal=("multi_proposal", "mean"), split_50_50=("resolution", lambda s: (s == "split_50_50").mean())).reindex(CATS)
    p("\nDispute / 50-50 incidence by category, markets with volume >= $10k:\n")
    p(md(dcv, "{:.4f}"))
    p("\nmulti_proposal x has_disputed (counts):\n")
    p(md(pd.crosstab(m["multi_proposal"], m["has_disputed"])))
    p("\nn_proposed (raw 'proposed' records) distribution:\n")
    p(md(m["n_proposed"].value_counts().sort_index().to_frame("markets")))
    p("\nn_proposal_rounds (runs of consecutive 'proposed') distribution:\n")
    p(md(m["n_proposal_rounds"].value_counts().sort_index().to_frame("markets")))
    p("\nshare with duplicate consecutive 'proposed' records (recording artefact) by quarter:\n")
    p(md(m.groupby("end_quarter").agg(dup_proposal_record=("dup_proposal_record", "mean")), "{:.4f}"))
    p("\n## Traded proxy (volumeNum > 0 or lastTradePrice present) share, volumeNum null share, enableOrderBook by quarter / category\n")
    p(md(m.groupby("end_quarter").agg(markets=("id", "size"), traded=("traded", "mean"),
                                      volume_null=("volumeNum", lambda s: s.isna().mean()),
                                      orderbook_false=("enableOrderBook", lambda s: (s == False).mean())), "{:.4f}"))  # noqa: E712
    p(md(m.groupby("category").agg(markets=("id", "size"), traded=("traded", "mean")).reindex(CATS), "{:.4f}"))
    p("\nTraded-proxy markets only, by category x quarter:\n")
    mt = m.loc[m["traded"], ["id", "end_quarter", "category", "split", "structure", "has_disputed", "multi_proposal", "resolution", "feesEnabled"]]
    ct3 = pd.crosstab(mt["end_quarter"], mt["category"]).reindex(columns=CATS, fill_value=0)
    ct3["total"] = ct3.sum(axis=1)
    ct3.loc["total"] = ct3.sum()
    ct3.index.name = "quarter"
    p(md(ct3))
    p("\nTraded markets: structure share by split, dispute and 50-50 incidence by split:\n")
    p(md(pd.crosstab(mt["split"], mt["structure"], normalize="index").reindex(["train", "validation", "test"]), "{:.4f}"))
    p(md(mt.groupby("split").agg(markets=("id", "size"), has_disputed=("has_disputed", "mean"),
                                 multi_proposal=("multi_proposal", "mean"),
                                 split_50_50=("resolution", lambda s: (s == "split_50_50").mean()),
                                 fee_enabled=("feesEnabled", lambda s: s.fillna(False).astype(bool).mean())
                                 ).reindex(["train", "validation", "test"]), "{:.4f}"))
    del mt

    # ---- settlement lag
    p("\n## Settlement lag: closedTime - endDate (hours)\n")
    def lagstats(s):
        s = s.dropna()
        return pd.Series({"n": len(s), "p10": s.quantile(.1), "p25": s.quantile(.25), "median": s.median(),
                          "p75": s.quantile(.75), "p90": s.quantile(.9), "share_negative": (s < 0).mean()})
    p(md(pd.concat({"all": lagstats(m["settle_lag_h"])}, axis=1).T, "{:,.2f}"))
    p("\nby category:\n")
    p(md(m.groupby("category")["settle_lag_h"].apply(lagstats).unstack().reindex(CATS), "{:,.2f}"))
    p("\nby quarter:\n")
    p(md(m.groupby("end_quarter")["settle_lag_h"].apply(lagstats).unstack(), "{:,.2f}"))
    p("\nsports: closedTime - gameStartTime (hours), markets with gameStartTime:\n")
    sp = m.loc[m["category"] == "sports", ["settle_lag_game_h", "gameStartTime", "has_disputed", "multi_proposal"]]
    p(md(pd.concat({"sports_vs_gameStart": lagstats(sp["settle_lag_game_h"])}, axis=1).T, "{:,.2f}"))
    p(f"\nnull closedTime: {m['closedTime'].isna().sum():,}; null gameStartTime among sports: {sp['gameStartTime'].isna().mean():.3f}")
    p("\nsettlement lag (closedTime - endDate, h) by dispute group, non-sports only (sports endDate is often a deadline):\n")
    nsp = m.loc[m["category"] != "sports", ["settle_lag_h", "has_disputed", "multi_proposal"]].assign(grp=lambda d: np.select(
        [d["has_disputed"], d["multi_proposal"]], ["disputed", "multi_proposal_no_dispute"], "single_proposal"))
    p(md(nsp.groupby("grp")["settle_lag_h"].apply(lagstats).unstack(), "{:,.2f}"))
    p("\nsports: closedTime - gameStartTime (h) by dispute group:\n")
    spg = sp.assign(grp=lambda d: np.select([d["has_disputed"], d["multi_proposal"]],
                                            ["disputed", "multi_proposal_no_dispute"], "single_proposal"))
    p(md(spg.groupby("grp")["settle_lag_game_h"].apply(lagstats).unstack(), "{:,.2f}"))

    # ---- volume
    p("\n## Volume distribution (Gamma volumeNum, USD, lifetime)\n")
    def vstats(s):
        s = s.fillna(0)
        q = s.quantile([.1, .25, .5, .75, .9, .99])
        top = s.sort_values(ascending=False)
        return pd.Series({"n": len(s), "share_zero": (s <= 0).mean(), "p25": q[.25], "median": q[.5], "p75": q[.75],
                          "p90": q[.9], "p99": q[.99], "total_$M": s.sum() / 1e6,
                          "top1pct_share": top.head(max(1, len(s) // 100)).sum() / max(s.sum(), 1e-9),
                          "share_ge_10k": (s >= 1e4).mean(), "share_ge_100k": (s >= 1e5).mean()})
    p(md(pd.concat({"all": vstats(m["volumeNum"])}, axis=1).T, "{:,.3f}"))
    p("\nby category:\n")
    p(md(m.groupby("category")["volumeNum"].apply(vstats).unstack().reindex(CATS), "{:,.3f}"))
    p("\nby split:\n")
    p(md(m.groupby("split")["volumeNum"].apply(vstats).unstack().reindex(["train", "validation", "test"]), "{:,.3f}"))

    # ---- category mapping holdout
    p("\n## Category rule vs feeType (rule never sees feeType)\n")
    lab = m.loc[m["category_fee"].notna(), ["id", "endDate", "category_fee", "category_rule"]].copy()
    # categories.py: tag sets / precedence were designed on endDate 2026-01-01..2026-06-30 (feeType as reference)
    lab["period"] = np.select([lab["endDate"] < pd.Timestamp("2026-01-01", tz="UTC"),
                               lab["endDate"] < pd.Timestamp("2026-07-01", tz="UTC")],
                              ["pre-2026 (feeType rare)", "2026-01..06 (design)"], "2026-07..10 (holdout)")
    lab["agree"] = lab["category_fee"] == lab["category_rule"]
    p(md(lab.groupby("period").agg(n=("id", "size"), agree=("agree", "mean")), "{:.4f}"))
    ho = lab[lab["period"].str.startswith("2026-07")]
    p("\nholdout agreement by feeType category (recall) and non-sports overall:\n")
    p(md(ho.groupby("category_fee").agg(n=("id", "size"), agree=("agree", "mean")), "{:.4f}"))
    ns = ho[ho["category_fee"] != "sports"]
    p(f"\nholdout non-sports agreement: {ns['agree'].mean():.4f} on n={len(ns):,}")
    conf = pd.crosstab(ho["category_fee"], ho["category_rule"])
    p("\nholdout confusion (rows feeType category, cols rule):\n")
    p(md(conf))
    p("\nzero_fees markets by rule category (all periods):\n")
    p(md(m[m["feeType"] == "zero_fees"]["category_rule"].value_counts().to_frame("markets")))

    # ---- data quality
    p("\n## Data quality\n")
    dq = {
        "parse_ok_share": m["parse_ok"].mean(),
        "n_outcomes_dist": m["n_outcomes"].value_counts().to_dict(),
        "condition_id_null": n_cid_null,
        "condition_id_dupes": n_cid_dupes,
        "markets_no_event": int((m["n_events"] == 0).sum()),
        "markets_multi_event": int((m["n_events"] > 1).sum()),
        "event_found_share": m["event_id"].isin(set(ev["event_id"])).mean(),
        "version_counts": m["version"].value_counts(dropna=False).to_dict(),
        "event_version_counts": m["event_version"].value_counts(dropna=False).to_dict(),
        "restricted_counts": m["restricted"].value_counts(dropna=False).to_dict(),
        "automaticallyResolved_counts": m["automaticallyResolved"].value_counts(dropna=False).to_dict(),
        "enableOrderBook_false": int((m["enableOrderBook"] == False).sum()),  # noqa: E712
        "archived_true": int((m["archived"] == True).sum()),  # noqa: E712
        "closed_flag_not_true": int((m["closed"] != True).sum()),  # noqa: E712
        "endDate_before_startDate": int((m["duration_h"] < 0).sum()),
        "startDate_null": int(m["startDate"].isna().sum()),
        "closedTime_null": int(m["closedTime"].isna().sum()),
        "closed_before_start": int((m["closedTime"] < m["startDate"]).sum()),
        "volume_null": int(m["volumeNum"].isna().sum()),
        "liquidity_null_share": m["liquidityNum"].isna().mean(),
        "feesEnabled_true_but_no_schedule": int(((m["feesEnabled"] == True) & m["fee_rate"].isna()).sum()),  # noqa: E712
        "feesEnabled_false_but_schedule": int(((m["feesEnabled"] == False) & m["fee_rate"].notna()).sum()),  # noqa: E712
        "feeSchedule_rate_vs_pmr_table_mismatch_TEST": None,
        "secondsDelay_gt0": int((m["secondsDelay"].fillna(0) > 0).sum()),
        "tick_size_counts": m["orderPriceMinTickSize"].value_counts(dropna=False).head(6).to_dict(),
        "markets_with_no_tags": n_no_tags,
        "sportsMarketType_present_share_in_sports": m.loc[m["category"] == "sports", "sportsMarketType"].notna().mean(),
    }
    sys.path.insert(0, str(ROOT))
    from pmr import fees
    tt = m.loc[(m["split"] == "test") & m["fee_rate"].notna() & (m["feesEnabled"] == True), ["fee_rate", "category", "feeType"]]  # noqa: E712
    mm = tt["fee_rate"] != tt["category"].map(fees.TAKER_RATE)
    dq["feeSchedule_rate_vs_pmr_table_mismatch_TEST"] = {"n_fee_markets": len(tt), "n_mismatch": int(mm.sum()),
                                                         "by_feeType": tt[mm].groupby(["feeType", "fee_rate"]).size().sort_values(ascending=False).head(10).to_dict()}
    for k, v in dq.items():
        p(f"- {k}: {v}")


if __name__ == "__main__":
    main()
