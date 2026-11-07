"""Assumptions for the EM bond fund candidate analysis (research/candidates/em_bonds.py).

Everything here is a judgement call or a sourced fact typed in by hand; market
data (prices, FX, yields, CPI) is read from data/research/ at run time. Each
entry says which it is. Edit and rerun to test a different view:

    python -m research.candidates.em_bonds --all --write
"""

# ---------------------------------------------------------------------------
# Candidates (Phase 2 shortlist, research/plan/shortlist.md) and benchmarks
# ---------------------------------------------------------------------------
CANDIDATES = ["EMB", "PCY", "HYEM", "CEMB", "EMLC", "EBND", "TGEIX", "PYEMX"]
LOCAL_FUNDS = {"EMLC", "EBND"}
BENCHMARK = {"EMB": "GUIDE_BENCH", "PCY": "EMB", "HYEM": "EMB", "CEMB": "EMB",
             "EMLC": "GUIDE_BENCH", "EBND": "EMLC", "TGEIX": "EMB", "PYEMX": "EMB"}
# EMB and EMLC are the method's benchmarks: IR against themselves is undefined,
# so their headline IR is against GUIDE_BENCH and the other EM benchmark.
METHOD_BENCHMARK = {t: ("EMLC" if t in LOCAL_FUNDS else "EMB") for t in CANDIDATES}
GUIDE_BENCH = {"ACWX": 0.55, "EMB": 0.35, "GLD": 0.10}   # method.md s9, quarterly rebalance
N_TRIALS = 20                                             # long list size (deflated Sharpe)

# ---------------------------------------------------------------------------
# Currency basket for the local-currency funds
# ---------------------------------------------------------------------------
# Primary: EMLC/EBND country weights were NOT retrieved for either fund (the
# long-list notes say the VanEck page failed; SSGA weights not read), so the
# primary basket is an equal weight of the ten currencies the overlay plan
# names. Sensitivity: the GBI-EM GD 15%-cap weights shown on the LEMB page
# (em_bonds_countries.csv weight_gbiem_pct, 2026-11-05, top 12 only), which
# is a different fund on a sister index.
BASKET_EQUAL = ["MXN", "BRL", "ZAR", "INR", "IDR", "PLN", "HUF", "CZK", "CLP", "COP"]
CCY_COUNTRY = {"MXN": "MX", "BRL": "BR", "ZAR": "ZA", "INR": "IN", "IDR": "ID", "PLN": "PL",
               "HUF": "HU", "CZK": "CZ", "CLP": "CL", "COP": "CO", "CNY": "CN", "TRY": "TR",
               "MYR": "MY", "THB": "TH", "PHP": "PH"}
CROSSCHECK_COUNTRIES = ["MX", "BR", "ZA", "ID", "IN", "PL", "HU", "CZ", "CL", "CO"]

# ---------------------------------------------------------------------------
# Fund yields and durations (current, for the forward view)
# ---------------------------------------------------------------------------
# Yield: em_bond_inputs.csv `ytm` (source and date in that file). Duration:
# em_bond_inputs.csv where present, else the judgement below.
DURATION_JUDGEMENT = {
    "PCY": (7.5, "judgement: equal-weight sovereign index with longer maturities than EMB "
                 "(shortlist.md); no duration retrieved"),
    "HYEM": (4.6, "judgement: set equal to EMHY's 4.66y (iShares 2026-11-05), the closest peer"),
    "TGEIX": (6.4, "judgement: set equal to EMB's 6.38y (benchmark EMBI GD); not retrieved"),
    "PYEMX": (6.4, "judgement: set equal to EMB's 6.38y (benchmark EMBI GD); not retrieved"),
}

# ---------------------------------------------------------------------------
# Expected credit loss  (JUDGEMENT built on published averages)
# ---------------------------------------------------------------------------
# Cumulative default rates (percent) at 5 and 10 years by rating, global
# corporates 1981-2023, S&P Global Ratings "2023 Annual Global Corporate
# Default And Rating Transition Study" (2024-03-28,
# https://www.spglobal.com/ratings/en/research/articles/240328-default-transition-and-recovery-2023-annual-global-corporate-default-and-rating-transition-study-13047827).
# The S&P page returned HTTP 403 on 2026-11-07, so the rounded figures are from
# the secondary summary https://fatfire.com/sp-probability-of-default-table
# (accessed 2026-11-07), which says they are approximate long-run averages.
CUM_DEFAULT_5Y_10Y = {"AAA": (0.17, 0.60), "AA": (0.15, 0.50), "A": (0.38, 1.10),
                      "BBB": (1.20, 3.50), "BB": (7.00, 14.0), "B": (16.0, 26.0),
                      "CCC": (50.0, 60.0)}
# Corporate rates are applied to sovereigns too. Moody's found sovereign
# default rates LOWER than for similarly rated corporates (1983-2005 study,
# reported by FinanceAsia, https://financeasia.com/article/who-defaults-more/36764,
# accessed 2026-11-07), so this is conservative for the sovereign funds.
# Recovery (share of face recovered):
RECOVERY = {
    "sovereign": (0.49, "Moody's average sovereign recovery 1983-2013, 49%, as quoted in a 2015 "
                        "J.P. Morgan note reproduced at https://forums.investireoggi.it/threads/"
                        "venezuela-e-petroleos-de-venezuela-cap-1.78893/page-4550 (secondary, "
                        "accessed 2026-11-07); bimodal, 20-40% or above 60%"),
    "corporate": (0.40, "senior unsecured bond recovery 38-45 cents in normal periods, below 25 in "
                        "2008-09, per https://fatfire.com/sp-probability-of-default-table "
                        "(secondary summary of S&P, accessed 2026-11-07); 40% used"),
}
# Annual loss for a bucket = annualised 7-year default probability x (1 - recovery),
# with the 7-year cumulative rate interpolated linearly between 5y and 10y.
HORIZON_YEARS = 7

# Rating mix by fund, share of the portfolio (decimals). Only EMB is sourced.
RATING_MIX = {
    "EMB": ({"A": 0.173, "BBB": 0.339, "BB": 0.255, "B": 0.190, "CCC": 0.034}, "sovereign",
            "iShares EMB page, credit quality as of 2026-11-05 (em_bonds.csv notes)"),
    "PCY": ({"A": 0.10, "BBB": 0.30, "BB": 0.25, "B": 0.27, "CCC": 0.08}, "sovereign",
            "judgement: equal country weights give more weight to small high-yield issuers than EMB"),
    "HYEM": ({"BB": 0.50, "B": 0.38, "CCC": 0.12}, "corporate",
             "judgement: high-yield-only corporate index; mix not retrieved"),
    "CEMB": ({"A": 0.25, "BBB": 0.40, "BB": 0.20, "B": 0.12, "CCC": 0.03}, "corporate",
             "judgement: CEMBI Broad Diversified Core is mostly investment grade; mix not retrieved"),
    "TGEIX": ({"A": 0.10, "BBB": 0.30, "BB": 0.30, "B": 0.22, "CCC": 0.08}, "sovereign",
              "judgement: active EMBI GD fund assumed to lean to high yield vs EMB; not retrieved"),
    "PYEMX": ({"A": 0.15, "BBB": 0.32, "BB": 0.27, "B": 0.20, "CCC": 0.06}, "sovereign",
              "judgement: active EMBI GD fund assumed close to EMB, slightly lower quality"),
    # Local-currency funds: built at run time from the country S&P ratings in
    # em_bonds_countries.csv weighted by the currency basket.
}

# ---------------------------------------------------------------------------
# FX view (relative PPP and UIP) and rate fair value
# ---------------------------------------------------------------------------
# Expected inflation per country = the latest World Bank annual CPI inflation
# in data/research/cpi_annual.csv (2025, or the latest year available).
# JUDGEMENT: realised inflation stands in for a forecast (IMF WEO projections
# are not in the repo). US expected inflation from research.config.MarketAssumptions (2.5%).
# UIP short rates = the latest OECD 3-month rate in yields.csv (<ISO2>_3M);
# BRL has no 3-month series, so its view is PPP only (research.screen.expected_fx_loss rule).
# Combined expected annual depreciation = mean of PPP and UIP (method.md s5).

# Fair yield for the "halfway to fair value" scenario:
#   hard-currency funds: fund yield + (US fair 10y - US 10y today), i.e. the
#     Treasury part reverts, the spread stays (no spread history before 2023-11
#     exists in the repo). US fair 10y = (1 + 1.5%) x (1 + 2.5%) - 1 from
#     research.config.MarketAssumptions.
#   local-currency funds: fund yield + (basket fair 10y - basket 10y today),
#     basket fair 10y = (1 + in-sample 2010-2017 average real 10y yield)
#     x (1 + expected inflation) - 1 per country, weighted by the basket.
SHOCK = 0.02           # +/-200 bp scenarios, as research.bonds.expected
COUPON_FREQ = 2

# Monte Carlo: research.montecarlo block bootstrap of the fund's own monthly
# USD history, drift scaled to the yield-based expected return.
MC_PATHS = 20_000
MC_BLOCK = 6
MC_SEED = 622

# ---------------------------------------------------------------------------
# Stress windows, method.md section 11 (month-end to month-end, USD)
# ---------------------------------------------------------------------------
STRESS = {
    "gfc_2008": ("2007-10-31", "2009-02-28"),
    "taper_2013": ("2013-04-30", "2013-08-31"),
    "covid_2020": ("2020-01-31", "2020-03-31"),
    "inflation_2022": ("2021-12-31", "2022-10-31"),
}
STRONG_USD_EPISODES = {"usd_2014_15": ("2014-05-31", "2015-03-31"),
                       "usd_2021_22": ("2021-05-31", "2022-09-30")}
STRONG_USD_THRESHOLD = 0.02   # monthly rise in FRED DTWEXBGS (yields.csv USD_BROAD, monthly average)

# ---------------------------------------------------------------------------
# Yield series not used
# ---------------------------------------------------------------------------
# The OECD "long-term interest rate" for Brazil (yields.csv BR_10Y) runs 6.0%
# in 2010-11, 5.0% in 2013-14, 7.5% in 2016 and 9.2% in 2026: these are the
# steps of BNDES's TJLP/TLP policy lending rate, not a traded 10-year bond
# yield (Brazilian 10y NTN-F yields were 10-16% over the same years). It is
# therefore excluded from the constant-maturity returns and the fair-value
# basket; Brazil appears with its rating and CPI only.
EXCLUDED_YIELD_SERIES = {"BR_10Y": "OECD BR long-term rate tracks the TJLP/TLP policy rate, not a market 10y yield"}
STALE_MONTHS = 12   # a yield older than this (vs the last full month) is not used as "latest"
