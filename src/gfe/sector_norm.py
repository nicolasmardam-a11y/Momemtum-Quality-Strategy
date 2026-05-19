"""Normalise sector labels across yfinance .info, index hints, and stockanalysis sources.

Hardcoded ticker overrides handle the case where yfinance .info returns no sector for
non-US large caps (German/French/Dutch/etc.) — common occurrence for EU stocks.


The raw fundamentals data has labels like:
  "Tech", "Technology", "Information Technology"   -> all mean "Technology"
  "Healthcare", "Health Care", "Health care"       -> "Health Care"
  "Financial", "Financial Services", "Financials"  -> "Financials"
  "Industrials", "Industrial"                      -> "Industrials"
  etc.

This module maps to a canonical set close to GICS:
  Energy, Materials, Industrials, Consumer Discretionary, Consumer Staples,
  Health Care, Financials, Information Technology, Communication Services,
  Utilities, Real Estate
"""
from __future__ import annotations

import pandas as pd

# Canonical -> aliases
SECTOR_ALIASES: dict[str, list[str]] = {
    "Information Technology": [
        "tech", "technology", "information technology", "info tech",
        "it services", "software", "semiconductors", "computer hardware",
        "industrial machinery",  # ASML labeled as machinery but really tech
    ],
    "Communication Services": [
        "communication services", "communications", "telecom", "telecommunications",
        "telecommunication services", "media", "entertainment",
    ],
    "Health Care": [
        "health care", "healthcare", "health", "biotech", "biotechnology",
        "pharmaceuticals", "medical devices",
    ],
    "Financials": [
        "financial", "financials", "financial services", "banks", "banking",
        "insurance", "diversified financial services", "capital markets",
    ],
    "Industrials": [
        "industrial", "industrials", "industrial services", "industrial conglomerates",
        "aerospace", "defense", "transportation", "machinery", "construction",
    ],
    "Consumer Discretionary": [
        "consumer", "consumer discretionary", "consumer cyclical", "consumer cyclicals",
        "retail", "specialty retail", "auto", "automobiles", "autos",
        "leisure", "hotels", "restaurants", "apparel",
    ],
    "Consumer Staples": [
        "consumer defensive", "consumer staples", "food", "beverage", "tobacco",
        "household products", "personal care",
    ],
    "Energy": [
        "energy", "oil & gas", "oil and gas", "oil", "gas",
    ],
    "Materials": [
        "materials", "basic materials", "chemicals", "metals", "mining", "metals & mining",
        "construction materials", "paper", "containers",
    ],
    "Utilities": [
        "utility", "utilities", "multiline utilities", "electric utility",
        "water utilities", "gas utilities",
    ],
    "Real Estate": [
        "real estate", "reit", "reits", "real estate investment trusts", "realestate",
    ],
}

# Additional ambiguous labels mapped manually (less-confident, after canonical pass)
EXTRA_HINT_MAP = {
    "services": "Information Technology",  # JP/UK "Services" usually IT services
    "support services": "Industrials",
    "trading": "Financials",
    "shipping": "Industrials",
    "personal goods": "Consumer Discretionary",
    "investment trusts": "Financials",
    "investment trust": "Financials",
    "collective investments": "Financials",
    "soft drinks": "Consumer Staples",
    "edp services": "Information Technology",
    "electronic equipment & parts": "Information Technology",
    "catalog/specialty distribution": "Consumer Discretionary",
}

# Build reverse map
_LOOKUP: dict[str, str] = {}
for canon, aliases in SECTOR_ALIASES.items():
    _LOOKUP[canon.lower()] = canon
    for a in aliases:
        _LOOKUP[a.lower()] = canon


def normalize_sector(raw: str | None) -> str:
    """Map a raw sector label to a canonical one. Unknown -> 'Other'."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "Other"
    key = str(raw).strip().lower()
    if not key:
        return "Other"
    if key in _LOOKUP:
        return _LOOKUP[key]
    # Substring match (for "Health Care" but also "Tech & Media")
    for alias, canon in _LOOKUP.items():
        if alias in key:
            return canon
    # Final fallback: extra hint map (only-after-canonical-pass)
    if key in EXTRA_HINT_MAP:
        return EXTRA_HINT_MAP[key]
    return "Other"


def normalize_sectors_in_df(df: pd.DataFrame,
                              sector_col: str = "sector",
                              hint_col: str = "sector_hint",
                              new_col: str = "sector_canonical") -> pd.DataFrame:
    """Add a `sector_canonical` column. Tries TICKER_SECTOR_OVERRIDES, then sector_col,
    then hint_col, then 'Other'."""
    df = df.copy()
    raw_primary = df[sector_col] if sector_col in df.columns else pd.Series(dtype=object, index=df.index)
    raw_hint = df[hint_col] if hint_col in df.columns else pd.Series(dtype=object, index=df.index)
    canon = []
    for i in df.index:
        # 1. Hardcoded override by ticker
        if i in TICKER_SECTOR_OVERRIDES:
            canon.append(TICKER_SECTOR_OVERRIDES[i])
            continue
        # 2. Normalize the raw sector
        c = normalize_sector(raw_primary.get(i))
        if c == "Other":
            c = normalize_sector(raw_hint.get(i))
        canon.append(c)
    df[new_col] = canon
    return df


# Hardcoded sector for stocks where yfinance .info returns no sector
# (mostly non-US large caps). Manually curated from public GICS classifications.
TICKER_SECTOR_OVERRIDES: dict[str, str] = {
    # France (Paris)
    "TTE.PA": "Energy",                     # TotalEnergies
    "OR.PA":  "Consumer Staples",           # L'Oréal
    "RMS.PA": "Consumer Discretionary",     # Hermès
    "MC.PA":  "Consumer Discretionary",     # LVMH
    "AI.PA":  "Materials",                  # Air Liquide
    "SU.PA":  "Industrials",                # Schneider Electric
    "LR.PA":  "Industrials",                # Legrand
    "EN.PA":  "Industrials",                # Bouygues
    "BVI.PA": "Industrials",                # Bureau Veritas
    "VIE.PA": "Utilities",                  # Veolia
    "ENGI.PA": "Utilities",                 # Engie
    "EL.PA":  "Consumer Discretionary",     # EssilorLuxottica
    "CS.PA":  "Financials",                 # Axa
    "BNP.PA": "Financials",                 # BNP Paribas
    "ACA.PA": "Financials",                 # Crédit Agricole
    "GLE.PA": "Financials",                 # Société Générale
    "SAN.PA": "Health Care",                # Sanofi
    "DG.PA":  "Industrials",                # Vinci
    "SAF.PA": "Industrials",                # Safran
    "AIR.PA": "Industrials",                # Airbus
    "STM.PA": "Information Technology",     # STMicroelectronics
    "CAP.PA": "Information Technology",     # Capgemini
    "PUB.PA": "Communication Services",     # Publicis
    "HO.PA":  "Industrials",                # Thales
    "ML.PA":  "Consumer Discretionary",     # Michelin
    "KER.PA": "Consumer Discretionary",     # Kering
    "DSY.PA": "Information Technology",     # Dassault Systemes
    "TEP.PA": "Consumer Discretionary",     # Teleperformance
    "CA.PA":  "Consumer Staples",           # Carrefour
    "ERF.PA": "Health Care",                # Eurofins Scientific
    "URW.AS": "Real Estate",                # Unibail
    # Germany (Xetra)
    "SIE.DE": "Industrials",                # Siemens
    "ENR.DE": "Industrials",                # Siemens Energy
    "IFX.DE": "Information Technology",     # Infineon
    "ALV.DE": "Financials",                 # Allianz
    "MUV2.DE": "Financials",                # Munich Re
    "DBK.DE": "Financials",                 # Deutsche Bank
    "DTE.DE": "Communication Services",     # Deutsche Telekom
    "DHL.DE": "Industrials",                # Deutsche Post DHL
    "MRK.DE": "Health Care",                # Merck KGaA
    "BNR.DE": "Materials",                  # Brenntag
    "G1A.DE": "Industrials",                # GEA Group
    "SAP.DE": "Information Technology",     # SAP
    "ADS.DE": "Consumer Discretionary",     # Adidas
    "BAS.DE": "Materials",                  # BASF
    "BAYN.DE": "Health Care",               # Bayer
    "BMW.DE": "Consumer Discretionary",     # BMW
    "CON.DE": "Consumer Discretionary",     # Continental
    "DAI.DE": "Consumer Discretionary",     # Mercedes-Benz Group
    "MBG.DE": "Consumer Discretionary",     # Mercedes-Benz Group (new)
    "DPW.DE": "Industrials",                # DHL (alt)
    "EOAN.DE": "Utilities",                 # E.ON
    "FRE.DE": "Health Care",                # Fresenius
    "HEN3.DE": "Consumer Staples",          # Henkel
    "HEI.DE": "Materials",                  # HeidelbergCement
    "LIN.DE": "Materials",                  # Linde
    "MTX.DE": "Industrials",                # MTU Aero Engines
    "RWE.DE": "Utilities",                  # RWE
    "VNA.DE": "Real Estate",                # Vonovia
    "VOW3.DE": "Consumer Discretionary",    # Volkswagen
    "ZAL.DE": "Consumer Discretionary",     # Zalando
    "DTG.DE": "Industrials",                # Daimler Truck
    "SY1.DE": "Materials",                  # Symrise
    "SHL.DE": "Health Care",                # Siemens Healthineers
    # UK (LSE)
    "HLMA.L": "Information Technology",     # Halma
    "ITRK.L": "Industrials",                # Intertek
    "DPLM.L": "Industrials",                # Diploma
    "RR.L":   "Industrials",                # Rolls-Royce
    "BA.L":   "Industrials",                # BAE Systems
    "HSBA.L": "Financials",                 # HSBC
    "LLOY.L": "Financials",                 # Lloyds
    "BARC.L": "Financials",                 # Barclays
    "STAN.L": "Financials",                 # Standard Chartered
    "NWG.L":  "Financials",                 # NatWest
    "AZN.L":  "Health Care",                # AstraZeneca
    "GSK.L":  "Health Care",                # GSK
    "SHEL.L": "Energy",                     # Shell
    "BP.L":   "Energy",                     # BP
    "ULVR.L": "Consumer Staples",           # Unilever
    "DGE.L":  "Consumer Staples",           # Diageo
    "RKT.L":  "Consumer Staples",           # Reckitt
    "BATS.L": "Consumer Staples",           # BAT
    "IMB.L":  "Consumer Staples",           # Imperial Brands
    "CNA.L":  "Utilities",                  # Centrica
    "NG.L":   "Utilities",                  # National Grid
    "SSE.L":  "Utilities",                  # SSE
    "LSEG.L": "Financials",                 # LSE Group
    "PRU.L":  "Financials",                 # Prudential
    "AV.L":   "Financials",                 # Aviva
    "LGEN.L": "Financials",                 # Legal & General
    "INF.L":  "Communication Services",     # Informa
    "REL.L":  "Communication Services",     # Relx
    "WPP.L":  "Communication Services",     # WPP
    "BT-A.L": "Communication Services",     # BT
    # Netherlands
    "ASML.AS": "Information Technology",    # ASML
    "PRX.AS":  "Consumer Discretionary",    # Prosus
    "INGA.AS": "Financials",                # ING
    "AD.AS":   "Consumer Staples",          # Ahold Delhaize
    "ABN.AS":  "Financials",                # ABN AMRO
    "RAND.AS": "Industrials",               # Randstad
    "NN.AS":   "Financials",                # NN Group
    "HEIA.AS": "Consumer Staples",          # Heineken
    "WKL.AS":  "Industrials",               # Wolters Kluwer
    "URW.AS":  "Real Estate",
    # Italy
    "ENI.MI":   "Energy",                   # Eni
    "ENEL.MI":  "Utilities",                # Enel
    "ISP.MI":   "Financials",               # Intesa
    "UCG.MI":   "Financials",               # Unicredit
    "G.MI":     "Financials",               # Generali
    "STLAM.MI": "Consumer Discretionary",   # Stellantis
    "TRN.MI":   "Utilities",                # Terna
    "MONC.MI":  "Consumer Discretionary",   # Moncler
    "PRY.MI":   "Industrials",              # Prysmian
    "RACE.MI":  "Consumer Discretionary",   # Ferrari
    # Spain
    "ITX.MC":  "Consumer Discretionary",    # Inditex
    "SAN.MC":  "Financials",                # Santander
    "BBVA.MC": "Financials",                # BBVA
    "IBE.MC":  "Utilities",                 # Iberdrola
    "TEF.MC":  "Communication Services",    # Telefonica
    "REP.MC":  "Energy",                    # Repsol
    "ANA.MC":  "Industrials",               # Acciona
    "FER.MC":  "Industrials",               # Ferrovial
    # Switzerland
    "NESN.SW": "Consumer Staples",          # Nestle
    "ROG.SW":  "Health Care",               # Roche
    "NOVN.SW": "Health Care",               # Novartis
    "ZURN.SW": "Financials",                # Zurich Insurance
    "UBSG.SW": "Financials",                # UBS
    "CFR.SW":  "Consumer Discretionary",    # Richemont
    "ABBN.SW": "Industrials",               # ABB
    "GIVN.SW": "Materials",                 # Givaudan
    "LONN.SW": "Health Care",               # Lonza
    "PARG.SW": "Information Technology",    # Partners Group
    "SLHN.SW": "Financials",                # Swiss Life
    "SREN.SW": "Financials",                # Swiss Re
    "GEBN.SW": "Industrials",               # Geberit
    "HOLN.SW": "Materials",                 # Holcim
    "LHN.SW":  "Materials",                 # LafargeHolcim (alt)
    "ALC.SW":  "Health Care",               # Alcon
    "SOON.SW": "Health Care",               # Sonova
    "SIKA.SW": "Materials",                 # Sika
    # Nordics + Belgium + Finland
    "UCB.BR":  "Health Care",               # UCB
    "WRT1V.HE": "Industrials",              # Wartsila
    "NDA-FI.HE": "Financials",              # Nordea
    "KNEBV.HE": "Industrials",              # KONE
    "FORTUM.HE": "Utilities",               # Fortum
    "NESTE.HE": "Energy",                   # Neste
    "SAMPO.HE": "Financials",               # Sampo
    "UPM.HE":   "Materials",                # UPM-Kymmene
    # Japan (.T suffix)
    "7203.T": "Consumer Discretionary",     # Toyota
    "6758.T": "Information Technology",     # Sony
    "9984.T": "Communication Services",     # SoftBank
    "8306.T": "Financials",                 # MUFG
    "9432.T": "Communication Services",     # NTT
    "6920.T": "Information Technology",     # Lasertec
    "6857.T": "Information Technology",     # Advantest
    "9983.T": "Consumer Discretionary",     # Fast Retailing
    "7974.T": "Communication Services",     # Nintendo
    "8316.T": "Financials",                 # SMFG
    "4519.T": "Health Care",                # Chugai
    "7741.T": "Health Care",                # HOYA
    "4502.T": "Health Care",                # Takeda
    "4063.T": "Materials",                  # Shin-Etsu Chemical
    "4568.T": "Health Care",                # Daiichi Sankyo
    "8035.T": "Information Technology",     # Tokyo Electron
    "6098.T": "Communication Services",     # Recruit Holdings
    "6273.T": "Industrials",                # SMC Corporation
    "6594.T": "Industrials",                # Nidec
    "6981.T": "Information Technology",     # Murata
    "7267.T": "Consumer Discretionary",     # Honda
    "8001.T": "Industrials",                # Itochu
    "8031.T": "Industrials",                # Mitsui
    "8058.T": "Industrials",                # Mitsubishi Corp
    "8316.T": "Financials",
    "5108.T": "Consumer Discretionary",     # Bridgestone
    "4901.T": "Information Technology",     # Fujifilm
    "1605.T": "Energy",                     # INPEX
    "6501.T": "Industrials",                # Hitachi
    # Canada (.TO suffix) — extras
    "RY.TO":  "Financials",                 # Royal Bank
    "TD.TO":  "Financials",                 # TD Bank
    "SHOP.TO": "Information Technology",    # Shopify
    "ENB.TO": "Energy",                     # Enbridge
    "CNQ.TO": "Energy",                     # Canadian Natural Resources
    "K.TO":   "Materials",                  # Kinross Gold
    "LUN.TO": "Materials",                  # Lundin Mining
    "WPM.TO": "Materials",                  # Wheaton Precious Metals
    "PAAS.TO": "Materials",                 # Pan American Silver
    "DOL.TO": "Consumer Discretionary",     # Dollarama
    "BMO.TO": "Financials",                 # BMO
    "BNS.TO": "Financials",                 # Scotiabank
    "CM.TO":  "Financials",                 # CIBC
    "MFC.TO": "Financials",                 # Manulife
    "SU.TO":  "Energy",                     # Suncor
    "CP.TO":  "Industrials",                # Canadian Pacific
    "CNR.TO": "Industrials",                # Canadian National
    "GWO.TO": "Financials",                 # Great-West Lifeco
}
