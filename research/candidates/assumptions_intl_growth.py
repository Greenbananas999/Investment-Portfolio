"""Assumptions the international growth adapters need that research/config.py does not carry.

`IntlMarketAssumptions` EXTENDS research.config.MarketAssumptions: every value
config.py already has (mature ERP 4.5%, KR/TW/US country risk premia, USD/KRW/TWD
risk-free and inflation, US/KR/TW real GDP) is kept unchanged, and only the
missing countries and currencies (DK, AU, HK, IN, CA, CN; DKK, AUD, HKD, INR,
CAD, CNY) are added. The extended object is passed into the existing
research/capm.py, dcf.py, grinold_kroner.py and fxview.py unchanged.

Sources (web lookups made 2026-11-07, the only web facts in this module):
  [D]  Damodaran, "Country Default Spreads and Risk Premiums", update of
       2026-01-05, https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html
       (mature-market ERP implied by the Aaa rows: 4.23%; config.py keeps 4.5%).
  [O]  OECD 3-month interbank rate, column <ISO2>_3M of data/research/yields.csv
       (on disk; latest observation and its date given per value).
  [IMF-HK] IMF WEO inflation (PCPIPCH) for Hong Kong SAR, 2031 = 2.5%, via
       https://statisticsoftheworld.com/country/HKG/IMF.PCPIPCH (vintage not
       stated by the site; treat as approximate).
  [IMF-CN] IMF CPI forecast for China, 2031 = 1.99% (April 2026 vintage), via
       cbonds.com IMF forecast listing (found by web search 2026-11-07).
  [CB] Central-bank inflation targets: RBI 4% (+/-2%), RBA 2-3% (midpoint
       2.5%), Bank of Canada 2%, Danmarks Nationalbank peg to the euro (ECB 2%).
       Used as the long-run inflation where the IMF 2031 figure was not found.
  [J]  Judgement, rounded, consistent with IMF WEO medium-term real growth
       (not looked up for every country; challenge freely).
"""

from dataclasses import dataclass, field

from research.config import DCFSettings, GKSettings, MarketAssumptions, MonteCarloSettings

# ---------------------------------------------------------------- added values
EXTRA_COUNTRY_RISK_PREMIUM = {
    "DK": 0.0,      # [D] Denmark Aaa, CRP 0.00% (2026-01-05)
    "AU": 0.0,      # [D] Australia Aaa, CRP 0.00% (2026-01-05)
    "HK": 0.0078,   # [D] Hong Kong Aa3, CRP 0.78% (2026-01-05)
    "IN": 0.0285,   # [D] India Baa3, CRP 2.85% (2026-01-05)
    "CA": 0.0,      # [D] Canada Aaa, CRP 0.00% (2026-01-05)
    "CN": 0.0091,   # [D] China A1, CRP 0.91% (2026-01-05)
    # kept from config.py: KR 0.8% (Damodaran Jan 2026 says 0.64%), TW 0.8% (0.78%), US 0.0 (0.23%)
}

EXTRA_RISK_FREE = {
    "DKK": 0.0259,  # [O] DK_3M, 2026-10 = 2.59%
    "AUD": 0.0480,  # [O] AU_3M, 2026-10 = 4.80%
    "HKD": 0.0394,  # no HKD series on disk: US_3M (TB3MS) 2026-09 = 3.94% under the USD peg (CIP)
    "INR": 0.0561,  # [O] IN_3M, 2026-10 = 5.61%
    "CAD": 0.0245,  # [O] CA_3M, 2026-10 = 2.4475%
    "CNY": 0.0151,  # [O] CN_3M, 2026-09 = 1.51%
}

EXTRA_INFLATION = {   # long-run (7-10y) expected CPI inflation
    "DKK": 0.020,   # [CB] DKK pegged to EUR, ECB target 2%; DK_CPIYOY 2025-12 = 1.9% [O]
    "AUD": 0.025,   # [CB] RBA 2-3% target midpoint; AU_CPIYOY 2026-09 = 4.3% is above target
    "HKD": 0.025,   # [IMF-HK] 2031 projection 2.5%
    "INR": 0.040,   # [CB] RBI 4% target; IN_CPIYOY 2018-2026 mean 5.1% [O]
    "CAD": 0.020,   # [CB] Bank of Canada 2% target
    "CNY": 0.020,   # [IMF-CN] 2031 projection 1.99%
}

EXTRA_REAL_GDP = {   # long-run real GDP growth (DCF terminal / G-K years 6-10)
    "DK": 0.015,    # [J]
    "AU": 0.022,    # [J] population growth ~1.3% plus productivity
    "HK": 0.020,    # [J]
    "IN": 0.060,    # [J] IMF medium-term ~6-6.5%
    "CA": 0.018,    # [J]
    "CN": 0.035,    # [J] IMF medium-term ~3.5% and falling
}

EXTRA_REAL_BOND_YIELD = {"DKK": 0.010, "AUD": 0.015, "HKD": 0.012, "INR": 0.020,
                         "CAD": 0.012, "CNY": 0.005}   # [J] not used by the stock models


@dataclass
class IntlMarketAssumptions(MarketAssumptions):
    """research.config.MarketAssumptions plus the countries/currencies above.

    Existing config keys win (they are never overwritten); new keys are added.
    """
    horizon_years: int = 7   # method.md section 1 (config default is 5)

    def __post_init__(self):
        for attr, extra in (("country_risk_premium", EXTRA_COUNTRY_RISK_PREMIUM),
                            ("risk_free", EXTRA_RISK_FREE), ("inflation", EXTRA_INFLATION),
                            ("long_run_real_gdp", EXTRA_REAL_GDP),
                            ("real_bond_yield", EXTRA_REAL_BOND_YIELD)):
            d = dict(extra)
            d.update(getattr(self, attr))   # config values take precedence
            setattr(self, attr, d)


# ---------------------------------------------------------------- Grinold-Kroner target P/E
# Forward P/E the market drifts to over GKSettings.repricing_years (10 years).
# Keys are candidate IDs. Forward P/E today from data/research/fundamentals/<T>/info.json.
TARGET_PE = {
    # fwd 11.9 after the 2024-26 GLP-1 de-rating (competition, US price cuts).
    # 16 = roughly large-cap pharma's long-run forward multiple; assumes the
    # market stops pricing Novo as ex-growth but not as the 2023 premium (30+).
    "NOVO-B_CO": 16.0,
    # fwd 27. Dominant listings marketplaces have kept 25-35x for a decade; the
    # target assumes a mild fade as growth slows toward nominal GDP.
    "REA_AX": 24.0,
    # fwd 16.0. research/config.py GKSettings.target_pe["TSMC"] = 18, kept for consistency.
    "2330_TW": 18.0,
    # fwd 11.5. Asian life insurers' long-run 12-16x; AIA has carried a premium.
    "1299_HK": 14.0,
    # fwd 11.9. China-internet discount (policy, VIE structure) assumed to narrow
    # partly, not to global-platform levels (20x+).
    "0700_HK": 15.0,
    # fwd 21.6. Indian high-growth lenders 20-30x in 2015-2023; growth now
    # slowing and asset quality cycle; target slightly below today.
    "BAJFINANCE_NS": 20.0,
    # fwd 2.7 on peak memory earnings. research/config.py target 9.0 on
    # MID-CYCLE earnings (with DCFSettings.cyclical_mid_cycle 0.5), kept.
    "000660_KS": 9.0,
    # fwd 19 (trailing 56: acquisition amortisation depresses GAAP EPS).
    # Serial acquirer; 20x assumes reinvestment returns fade slowly.
    "CSU_TO": 20.0,
}

# SK Hynix: same cyclical treatment and mid-cycle fraction as config.py's SKHYNIX.
CYCLICAL_MID_CYCLE = {"000660_KS": 0.5}

# Financials: a free-cash-flow DCF is not meaningful for an insurer or a lender
# (loan growth is the business, "FCF" is negative or arbitrary), so the DCF
# method is reported as null for them and the consensus uses the other methods.
DCF_NOT_APPLICABLE = {"1299_HK": "life insurer", "BAJFINANCE_NS": "lender (NBFC)"}

# Home index for Denmark: no OMX Copenhagen series on disk. Euro Stoxx 50
# (^STOXX50E, EUR) converted to DKK is used as the proxy (DKK is pegged to EUR).
DK_INDEX_PROXY = "^STOXX50E"

# Local risk-free where no OECD 3-month series exists (whole history):
#   TWD: flat research/config.py MarketAssumptions.risk_free["TWD"] = 1.8%
#        (no Taiwan short-rate series on disk). APPROXIMATE: hedge and local
#        Sharpe for 2330.TW rest on this flat value.
#   HKD: US_3M (HKD peg; HIBOR tracks USD rates through CIP). Approximate.
#   INR before 2011-12 (IN_3M starts 2011-11): flat config-extension value 5.61%.
NO_SERIES_NOTE = {
    "TWD": "TWD 3M rate: flat 1.8% (research/config.py; no Taiwan series on disk) - approximate",
    "HKD": "HKD 3M rate: US_3M proxy under the USD peg - approximate",
    "INR": "INR 3M rate: OECD IN_3M from 2011-12; flat 5.61% before - approximate in 2010-2011",
}

FX_FORWARD_COST_PER_ROLL = 0.0005   # method.md section 10: FX forwards 5 bps per roll (monthly roll)


def market_assumptions():
    return IntlMarketAssumptions()


def dcf_settings():
    return DCFSettings(cyclical_mid_cycle=dict(CYCLICAL_MID_CYCLE))


def gk_settings():
    return GKSettings(target_pe=dict(TARGET_PE))


def mc_settings():
    return MonteCarloSettings(horizon_years=7)
