"""Empirical base rate for the user's '5 resolved decisions, all won' screen, from CryptoHouse
(pre-V2 on-chain data; polymarket.user_positions final-state snapshot x polymarket.assets resolutions).
Window: markets closed 2025-01-05 .. 2026-01-05 (the last 12 months CryptoHouse covers; the user's
2025-10-17..2026-10-17 window is mostly V2 and not in CryptoHouse). 2% hash sample of users.
Decision = (user, market); 'won' = the outcome the user bought most of resolved to 1;
'made money' = realized_pnl + amount*(payout - avg_price) > 0. Also per event (event_id).
Caveat: polymarket.assets covers ~22k markets, not all markets, so per-user counts are truncated.
Output: data/derived/ge_base_rate_cryptohouse.parquet
"""
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pmr import api  # noqa: E402
MOD = int(sys.argv[1]) if len(sys.argv) > 1 else 50
SQL = f"""
WITH a AS (SELECT outcome_token_id tok, market_condition_id cid, outcome_price op, event_id ev
           FROM polymarket.assets WHERE market_closed AND market_closed_date >= '2025-01-05'
           AND market_closed_date < '2026-01-05' AND outcome_price IN (0, 1)),
p AS (SELECT user, splitByChar('.', token_id)[1] tok, toFloat64(total_bought) tb, toFloat64(amount) amt,
             toFloat64(avg_price) ap, toFloat64(realized_pnl) rp
      FROM polymarket.user_positions WHERE is_deleted = 0 AND cityHash64(user) % {MOD} = 0 AND toFloat64(total_bought) > 0),
j AS (SELECT p.user user, a.cid cid, a.ev ev, a.op op, p.tb tb, p.rp + p.amt * (a.op - p.ap) pnl FROM p INNER JOIN a ON p.tok = a.tok),
m AS (SELECT user, cid, any(ev) ev, argMax(op, tb) won, sum(pnl) pnl FROM j GROUP BY user, cid),
u AS (SELECT user, count() nmk, uniqExact(ev) nev, min(won) allwon, min(pnl > 0) allmoney, avg(won) wr FROM m GROUP BY user)
SELECT nmk, count() users, sum(allwon) all_won, sum(allmoney) all_money, avg(wr) mean_win_rate
FROM u WHERE nmk <= 12 GROUP BY nmk ORDER BY nmk
"""
rows = api.cryptohouse(SQL)
df = pd.DataFrame(rows).astype(float)
df["sample_mod"] = MOD
df["frac_all_won"] = df.all_won / df.users
df["frac_all_money"] = df.all_money / df.users
df["est_users_population"] = df.users * MOD
df["est_all_won_population"] = df.all_won * MOD
df.to_parquet(ROOT / "data" / "derived" / "ge_base_rate_cryptohouse.parquet", index=False)
print(df.to_string())
