# Resolved-market universe (Gamma, endDate 2024-01-01 .. 2026-10-15)

Status: data build (family = data, verdict = n/a_data_build). As-of 2026-10-17.

## 0. Pre-registered acceptance checks (written 2026-10-17 before any counts were computed)

This is a data build, not a strategy test, so "rejection criteria" are data-quality acceptance checks.
The universe is accepted for downstream research only if all of the following hold; any failure is
reported in section 7 together with what it means for downstream tests.

1. Uniqueness: `condition_id` is unique after de-duplication by Gamma market `id` (month windows overlap at the boundary).
2. Parseability: >= 99% of markets have parseable `outcomes`, `outcomePrices` and `clobTokenIds` with equal lengths.
3. Resolution: >= 97% of markets classify as a clean winner (one payout = 1, rest = 0) or a 50-50 split;
   the remainder is listed by type.
4. Parent events: >= 99% of markets have a parent event found in `events_resolved.parquet`.
5. External cross-check: monthly counts of closed markets (2024-01 .. 2025-12) agree with an
   independent source (CryptoHouse `polymarket.assets`, distinct `market_condition_id` by end month)
   within +/-5% in at least 20 of 24 months; disagreements are explained or listed.
6. Category mapping: on markets where Gamma's `feeType` names a fee category, the tag/slug rule
   (computed WITHOUT looking at feeType) agrees with feeType on >= 90% of markets.
