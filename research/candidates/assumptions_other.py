"""Forward-looking assumptions for the other-sleeve expected-return models.

Every number a reader might challenge is here, with its source or the label
"judgement". Market inputs (yields, breakevens) are read from
data/research/yields.csv at run time; only the constants below are fixed.
All annual, decimals, USD nominal unless noted. These are JUDGEMENT CALLS for
gold, silver and commodities: the models disagree with each other by several
points and the report says so.
"""

N_TRIALS = 33          # passed names in research/plan/longlists/other_scored.csv (deflated Sharpe)
HORIZON_YEARS = 7
MC_PATHS = 20_000
MC_BLOCK_MONTHS = 6
MC_SEED = 622

# --- Gold and silver: real-yield model -------------------------------------
# E[real return] = -REAL10_now + drift ; E[nominal] = (1 + E[real]) * (1 + BE10) - 1.
# drift = average 10-year TIPS real yield over the data (2003-2026), so that
# when the real yield sits at its own average gold's expected real return is
# zero (Erb and Harvey find no long-run real return in gold beyond mean
# reversion of its real price). The level-of-yield-to-return link is a
# simplification of a changes relationship: judgement, weak evidence.
GOLD_DRIFT_RULE = "mean of US_REAL10 over the full yields.csv history (2003-2026)"
GOLD_SOURCES = [
    "Erb, C. and Harvey, C. (2013) The Golden Dilemma, NBER WP 18706 / Financial Analysts Journal 69(4): "
    "https://www.nber.org/papers/w18706 (found by search 2026-11-07; the real-yield correlation figures "
    "(about -0.7 to -0.8, 1997-2012) were seen only in secondary sources and are not relied on)",
    "FRED DFII10 (10-year TIPS yield) and T10YIE (breakeven), via data/research/yields.csv columns US_REAL10, US_BE10",
]
SILVER_NOTE = ("Silver uses the same formula as gold (judgement): it has no better anchor, and its "
               "industrial demand adds a cyclical component the model ignores.")

# --- Commodities (GSG, S&P GSCI) -------------------------------------------
# E[TR] = collateral yield (US_3M) + roll yield + spot return (= expected inflation) - fee.
# Spot GSCI is not on disk, so roll yield cannot be backed out of GSG's realised return:
# it is an ASSUMPTION. The GSCI is energy-heavy and was in contango for most of 2006-2020.
GSG_ROLL_YIELD = -0.010   # judgement; sensitivity +/- 3 points
GSG_SPOT_REAL = 0.0       # spot return = inflation (Gorton and Rouwenhorst 2006)
GSG_FEE = 0.0075          # funds.csv expense ratio (the NAV history is already net of it)
COMMODITY_SOURCES = [
    "Gorton, G. and Rouwenhorst, K.G. (2006) Facts and Fantasies about Commodity Futures, "
    "Financial Analysts Journal 62(2) (NBER WP 10595; cited from memory, not re-fetched)",
]

# --- Equity-like real assets: Grinold-Kroner building block ----------------
# E[R] = fund distribution yield (funds.csv) + expected inflation (US_BE10) + real growth.
# No repricing and no dilution term. The fund yield is already net of expenses.
# Real growth of distributions: judgement, kept low because dividends of
# resource producers and REITs have grown about with inflation, not above it.
REAL_GROWTH = {"GNR": 0.010, "IGF": 0.015, "VNQI": 0.005}
GK_SOURCE = ("Grinold, R. and Kroner, K. (2002) The Equity Risk Premium, Investment Insights 5(3), "
             "Barclays Global Investors (citation confirmed 2026-11-07 via "
             "https://en.wikipedia.org/wiki/Grinold_and_Kroner_Model; PDF not retrieved)")
# CAPM: rf (US_3M latest) + beta to ACWI x ERP; ERP is research.config.MarketAssumptions.mature_erp (4.5%).

# --- Inflation-linked bonds -------------------------------------------------
# SCHP: 10-year real yield + 10-year breakeven - fee. Duration of SCHP is shorter than
# 10 years, so this is an approximation; 'yield' method = funds.csv trailing yield.
SCHP_FEE = 0.0003
# WIP: weights of the two countries the long-list notes give (SSGA factsheet 2026-09-30):
# UK 18.36%, Brazil 7.99%; renormalised to 100% of those two (26% of the fund; the rest is unknown).
WIP_WEIGHTS = {"GB": 18.36, "BR": 7.99}
WIP_FEE = 0.0050
# Method 1: sum of w * nominal 10Y (real-yield proxy = nominal 10Y - CPI YoY, plus CPI YoY carried
# forward) + relative-PPP FX (US_BE10 vs country CPI YoY) - fee. Method 2: funds.csv trailing yield.

# --- Non-US share (method.md section 3), from other_notes.md ---------------
NON_US = {"IAU": 0.00, "SLV": 0.00, "GSG": 0.00, "GNR": 0.65, "VNQI": 1.00, "IGF": 0.64,
          "SCHP": 0.00, "WIP": 1.00}
