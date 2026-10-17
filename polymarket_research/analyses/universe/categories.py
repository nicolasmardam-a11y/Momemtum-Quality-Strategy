"""Deterministic market -> category mapping (sports, politics, crypto, finance, economics, culture,
weather, tech, mentions, geopolitics, other).

Two labels are produced:

* ``category_fee``  - from Gamma's per-market ``feeType`` (authoritative for fees where present).
* ``category_rule`` - from tags / sportsMarketType / slug patterns only (never looks at feeType),
  so it is defined identically for every era, including the pre-2026 fee-free markets.

``category`` = ``category_fee`` when feeType maps to a category, else ``category_rule``.

Rule (first match wins, evaluated on the union of market tags and parent-event tags, all lower-cased):
  1. mentions    tag in MENTIONS_TAGS, or slug/question matches MENTIONS_RE
  2. sports      sportsMarketType present, or tag in SPORTS_TAGS, or slug starts with a league prefix
  3. crypto      tag in CRYPTO_TAGS, or slug matches CRYPTO_SLUG_RE
  4. weather     tag in WEATHER_TAGS
  5. culture     tag in CULTURE_FIRST_TAGS (tweet counts, YouTube creators)
  6. other       tag in OTHER_FIRST_TAGS (home prices)
  7. politics    tag in ELECTION_TAGS
  8. economics   tag in ECONOMICS_TAGS (incl. company earnings/EPS markets, which carry economics_fees)
  9. finance     tag in FINANCE_TAGS
 10. tech        tag in TECH_TAGS
 11. geopolitics tag in GEOPOLITICS_TAGS
 12. politics    tag in POLITICS_TAGS
 13. culture     tag in CULTURE_TAGS
 14. other
The tag sets and the precedence were chosen on markets with endDate 2026-01-01..2026-06-30 (feeType as the
reference label) and the agreement is reported out of sample on 2026-07-01..2026-10-15 (see universe.md).
"""
from __future__ import annotations

import re

CATEGORIES = ["sports", "politics", "crypto", "finance", "economics", "culture", "weather", "tech",
              "mentions", "geopolitics", "other"]

# feeType -> category. zero_fees is ambiguous (fee rate 0) so it falls through to the rule.
FEE_TYPE_MAP = {
    "sports": "sports", "crypto": "crypto", "politics": "politics", "finance": "finance",
    "economics": "economics", "culture": "culture", "weather": "weather", "tech": "tech",
    "mentions": "mentions", "geopolitics": "geopolitics", "general": "other",
}


def category_from_fee_type(fee_type) -> str | None:
    if not isinstance(fee_type, str) or not fee_type:
        return None
    head = fee_type.split("_")[0].lower()
    return FEE_TYPE_MAP.get(head)


MENTIONS_TAGS = {"mentions", "mention-markets", "mention", "earnings-calls", "earnings-call", "what-will-they-say",
                 "say", "speech-mentions"}
MENTIONS_RE = re.compile(r"\b(say|says|mention|mentions|said)\b.*\b(during|in|at|on)\b", re.I)
SPORTS_TAGS = {"sports", "soccer", "tennis", "esports", "nba", "nfl", "mlb", "nhl", "ufc", "mma", "cricket", "f1",
               "formula1", "golf", "boxing", "basketball", "baseball", "hockey", "football", "cfb", "cbb", "ncaa",
               "ncaab", "ncaaf", "table-tennis", "chess", "wnba", "epl", "premier-league", "champions-league", "ucl",
               "la-liga", "bundesliga", "serie-a", "ligue-1", "mls", "olympics", "cycling", "racing", "darts",
               "rugby", "volleyball", "handball", "league-of-legends", "dota-2", "counter-strike", "csgo", "cs2",
               "valorant"}
SPORTS_SLUG_RE = re.compile(r"^(nba|nfl|mlb|nhl|wnba|ufc|epl|cfb|cbb|atp|wta|lol|cs2|dota2|val|ipl|mls|ucl|uel|"
                            r"lal|bun|sea|fl1|itsb|ere|por|cricket|tennis|soccer)-", re.I)
CRYPTO_TAGS = {"crypto", "crypto-prices", "bitcoin", "ethereum", "solana", "xrp", "ripple", "dogecoin", "btc",
               "eth", "sol", "memecoins", "airdrops", "stablecoins", "defi", "nft", "nfts", "crypto-policy",
               "microstrategy", "hyperliquid", "bnb", "cardano"}
CRYPTO_SLUG_RE = re.compile(r"^(btc|eth|sol|xrp|doge|bnb|hype)-(updown|up-or-down)|"
                            r"^(bitcoin|ethereum|solana|xrp|dogecoin)-(up-or-down|above|price|reach|dip)", re.I)
WEATHER_TAGS = {"weather", "daily-temperature", "highest-temperature", "lowest-temperature", "temperature",
                "climate", "global-temp", "hurricanes", "hurricane", "hurricane-season", "snow", "rain",
                "precipitation", "climate-science", "natural-disasters", "earthquakes"}
ECONOMICS_TAGS = {"earnings", "economy", "economics", "fed", "fed-rates", "fed-rate", "interest-rates", "inflation", "cpi",
                  "gdp", "jobs", "jobs-report", "unemployment", "recession", "economic-policy", "tariffs",
                  "macro", "fomc", "pce", "treasuries", "yields", "taxes", "trade-war", "nfp", "payrolls"}
FINANCE_TAGS = {"finance", "stocks", "equities", "commodities", "finance-updown", "pyth-finance", "ipo", "ipos",
                "s-p-500", "sp500", "nasdaq", "gold", "oil", "forex", "indices", "business",
                "companies", "stock-prices", "silver", "pre-market"}
TECH_TAGS = {"tech", "ai", "ai-rankings", "big-tech", "openai", "science", "space", "spacex", "elon-musk-tech",
             "apple", "google", "nvidia", "tesla", "chatgpt", "llm", "gpt", "anthropic", "gemini", "grok",
             "technology", "app-store"}
GEOPOLITICS_TAGS = {"geopolitics", "world", "ukraine", "russia", "israel", "gaza", "middle-east", "iran", "china",
                    "taiwan", "war", "ceasefire", "military", "nato", "north-korea", "syria", "lebanon", "hamas",
                    "hezbollah", "houthis", "venezuela", "ukraine-russia", "russia-ukraine", "world-affairs",
                    "foreign-policy", "conflicts", "india-pakistan"}
POLITICS_TAGS = {"politics", "elections", "us-presidential-election", "global-elections", "primaries",
                 "primary-elections", "trump", "congress", "senate", "house", "us-politics", "main-election",
                 "trump-presidency", "polls", "polling", "approval", "supreme-court", "courts", "biden",
                 "democrats", "republicans", "governor", "mayor", "uk-politics", "france", "germany", "canada",
                 "elon-musk", "doge", "cabinet", "executive-orders", "legal"}
CULTURE_TAGS = {"pop-culture", "culture", "music", "movies", "awards", "oscars", "grammys", "emmys",
                "entertainment", "celebrities", "tv", "youtube", "tweets-markets", "tweets", "twitter", "x",
                "social-media", "box-office", "spotify", "billboard", "gaming", "video-games", "reality-tv",
                "netflix", "religion", "pope", "mrbeast", "kanye", "taylor-swift", "eurovision", "mr-beast"}

# Overrides found on the design sample (2026-05/06 endDates, feeType as reference):
CULTURE_FIRST_TAGS = {"tweets-markets", "mrbeast", "youtube"}        # tweet-count / creator markets: culture fee
OTHER_FIRST_TAGS = {"parcl", "housing", "real-estate"}             # home-price markets: general (other) fee
ELECTION_TAGS = {"elections", "global-elections", "world-elections", "main-election", "primaries",
                 "primary-elections"}                               # elections tagged 'world' are politics

RULES = [
    ("mentions", MENTIONS_TAGS), ("sports", SPORTS_TAGS), ("crypto", CRYPTO_TAGS), ("weather", WEATHER_TAGS),
    ("culture", CULTURE_FIRST_TAGS), ("other", OTHER_FIRST_TAGS), ("politics", ELECTION_TAGS),
    ("economics", ECONOMICS_TAGS), ("finance", FINANCE_TAGS), ("tech", TECH_TAGS),
    ("geopolitics", GEOPOLITICS_TAGS), ("politics", POLITICS_TAGS), ("culture", CULTURE_TAGS),
]


def category_from_rule(tags: set[str], slug: str = "", question: str = "", sports_market_type=None) -> str:
    tags = {t.lower() for t in tags if t}
    slug = slug or ""
    question = question or ""
    for cat, tagset in RULES:
        if tags & tagset:
            return cat
        if cat == "mentions" and MENTIONS_RE.search(question) and "say" in question.lower():
            return cat
        if cat == "sports" and (isinstance(sports_market_type, str) and sports_market_type or SPORTS_SLUG_RE.search(slug)):
            return cat
        if cat == "crypto" and CRYPTO_SLUG_RE.search(slug):
            return cat
    return "other"
