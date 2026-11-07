"""Assumptions for the derivative-overlay analysis (research/candidates/overlays.py).

Every entry is either a rule copied from research/plan/method.md, a sourced
contract fact, or a modelling choice; each says which. Market data (SPY, ^VIX,
^VIX3M, ^GSPC, CBOE indices, FX, OECD 3-month rates) is read from
data/research/ at run time and is never typed in here. Rerun after editing:

    python -m research.candidates.overlays --all --write
"""

# ---------------------------------------------------------------------------
# Sample split (method.md section 2). Calibration uses data to CALIBRATION_END only.
# ---------------------------------------------------------------------------
IN_SAMPLE_START = "2010-01-01"
IN_SAMPLE_END = "2017-12-31"
CALIBRATION_START = "2010-01-01"
CALIBRATION_END = "2017-12-31"       # skew/level parameters are fitted on 2010-01..2017-12 and frozen
OOS_START = "2018-01-01"
# Modelling choice: the option engine starts in 2006-09 (first full month of
# ^VIX3M, which starts 2006-07-17) so the GFC stress window can be shown. Months
# before 2010 are "pre-sample": never used for calibration, not in the metrics.
ENGINE_START = "2006-08-01"
OUTPUT_START = "2010-01-01"          # first month written to the *_monthly.csv files

# ---------------------------------------------------------------------------
# Option model
# ---------------------------------------------------------------------------
# Underlying: SPY adjusted close (total return, dividends reinvested by Yahoo)
# with dividend yield q = 0 in Black-Scholes, so dividends enter through the
# total-return underlying rather than a smoothed yield. Modelling choice from
# the task brief; it understates call premia slightly versus an SPX price-index
# option (forward is S*e^{rT} instead of S*e^{(r-q)T}, about 0.1% per month).
UNDERLYING = "SPY"
INDEX_LEVEL = "^GSPC"                # used only to count XSP contracts (notional = SPX x 10)
# Implied vol: ^VIX is the 30-day SPX implied volatility (variance-swap style,
# Cboe VIX white paper); ^VIX3M is the 93-day equivalent (history from
# 2006-07-17 in prices.csv, so no term-structure assumption is needed). For
# remaining life between 30 and 93 days total variance is interpolated
# linearly in time; below 30 days ^VIX is used, above 93 days ^VIX3M.
IV_SHORT, IV_SHORT_DAYS = "^VIX", 30
IV_LONG, IV_LONG_DAYS = "^VIX3M", 93
# Smile: sigma(K, tau) = sigma_atm(tau) + ATM_LEVEL - SKEW_SIDE * ln(K/F)/sqrt(tau),
# SKEW_SIDE = SKEW_CALL for K >= F and SKEW_PUT for K < F. ATM_LEVEL is needed
# because VIX is a variance-swap level, which sits above at-the-money IV when
# the smile is skewed. All three are FREE PARAMETERS, fitted on 2010-2017 only:
#   ATM_LEVEL  on CBOE BXM  (ATM monthly buy-write)
#   SKEW_CALL  on CBOE BXMD (30-delta monthly buy-write), ATM_LEVEL frozen
#   SKEW_PUT   on CBOE PPUT (monthly 5% OTM put),          ATM_LEVEL frozen
# CBOE CLL (collar) is never used in fitting: it is a pure hold-out check.
PARAM_BOUNDS = {"atm_level": (-0.06, 0.04), "skew_call": (-0.20, 0.60), "skew_put": (-0.20, 0.80)}
MIN_VOL = 0.03                       # floor on any modelled implied vol (numerical guard)
# Risk-free rate inside Black-Scholes and on premium cash: US_3M (FRED TB3MS,
# monthly average, percent) converted to continuous ln(1 + r). method.md s9
# names TB3MS for the research models. Sharpe ratios use BIL (method.md s9).
RATE_SERIES = "US_3M"
# Roll timing: SPX standard monthly options expire on the third Friday
# (Cboe SPX/XSP product pages). When that day is not a trading day in the SPY
# calendar the previous trading day is used. Expiring options settle at the
# intrinsic value on the SPY close of that day and the new options are struck
# on the same close. (CBOE indices use the special opening quotation; that
# difference is part of the reported tracking error.) Quarterly legs roll in
# Mar, Jun, Sep and Dec, as CLL's put leg does (Cboe CLL description, notes s2).
ROLL_WEEKDAY, ROLL_WEEK = 4, 3        # Friday, third week
QUARTER_MONTHS = (3, 6, 9, 12)
# At each roll all cash (premium received, put cost paid) is swept into the
# underlying, as in a buy-write index, so the sleeve stays fully invested.

# ---------------------------------------------------------------------------
# Costs (method.md section 10)
# ---------------------------------------------------------------------------
OPTION_HALF_SPREAD = 0.01            # half the bid-ask, as a fraction of premium, per opening trade
OPTION_FEE_PER_CONTRACT = 0.65       # USD per contract per trade
# Cash-settled XSP options expire without a closing trade, so no spread or fee
# is charged at expiry (modelling choice; exercise/settlement fees ignored).
FX_ROLL_COST_BPS = 5.0               # per quarterly roll, on the hedged notional

# ---------------------------------------------------------------------------
# Sizing at $100,000 (the achievable hedge ratio)
# ---------------------------------------------------------------------------
CAPITAL = 100_000
EQUITY_SLEEVE_USD = 55_000           # method.md s1: about 55% stocks
# XSP (Mini-SPX): 1/10 of SPX, $100 multiplier, so notional = SPX x 10; cash
# settled, exercise only at expiration. Source: Cboe Mini-SPX product page,
# https://www.cboe.com/tradable_products/sp_500/mini_spx_options/ (read 2026-11-07).
# A SPY option (100 shares) has the same notional to within the SPY/SPX ratio.
XSP_MULTIPLIER = 100
XSP_INDEX_FRACTION = 0.1
CONTRACTS = 1                        # whole contracts per leg the sleeve supports (see feasibility)
# Margin: an XSP call written against a sleeve of individual stocks is NOT a
# covered position at a broker (the cover would have to be the index itself),
# so it is margined as an uncovered broad-based index option. Cboe's margin
# rule for that (from the Cboe Margin Manual, recalled, NOT re-verified this
# session): 100% of the premium plus 15% of the index notional less any
# out-of-the-money amount, minimum premium plus 10% of notional.
UNCOVERED_INDEX_MARGIN = (0.15, 0.10)

# ---------------------------------------------------------------------------
# International basis check (method.md s9 benchmark ids)
# ---------------------------------------------------------------------------
# The equity sleeve is about half US growth stocks and half international. A
# sleeve proxy of 50% IVW + 50% EFG_EEM_5050 (monthly rebalanced) is shown with
# the same S&P 500 overlay P&L added, to quantify basis risk.
SLEEVE_PROXY = {"IVW": 0.5, "EFG": 0.25, "EEM": 0.25}

# ---------------------------------------------------------------------------
# FX forwards on EM local-currency bonds
# ---------------------------------------------------------------------------
UNHEDGED_FUND = "EMLC"               # task brief: EMLC monthly total return is the unhedged series
FX_CROSSCHECK_FUND = "EBND"
# Currencies named in the plan. THB and MYR have no OECD 3-month series in
# yields.csv; BRL has none either (yields.csv has no BR_3M column: the OECD
# IR3TIB01BRM156N series was not delivered by the fetch). All three are left
# unhedged and the basis this creates is reported.
FX_CURRENCIES = {"MXN": "MX", "ZAR": "ZA", "INR": "IN", "IDR": "ID", "PLN": "PL",
                 "HUF": "HU", "CZK": "CZ", "CLP": "CL", "COP": "CO"}
FX_EXCLUDED = {"BRL": "no BR_3M column in data/research/yields.csv",
               "THB": "no OECD 3-month series", "MYR": "no OECD 3-month series"}
# Weights: weight_gbiem_pct from research/plan/longlists/em_bonds_countries.csv
# (GBI-EM figures from the LEMB page, read 2026-11-05/07) where given; HUF, CZK
# and COP have no figure there and get the average of the given weights
# (modelling choice; the task says equal weight where none is given). Weights
# are renormalised each roll over the currencies that have a rate and a spot.
# Applying today's weights to history is a look-ahead flag (notes s6 item 5).
COUNTRY_WEIGHTS_FILE = "research/plan/longlists/em_bonds_countries.csv"
# Rates: OECD IR3TIB01<CC>M156N (3-month interbank, monthly average, percent),
# against TB3MS (3-month T-bill). Interbank rates carry a bank-credit premium
# over T-bills, so the modelled carry is slightly overstated (notes s4).
# A missing month is forward-filled for up to 12 months (Indonesia ends 2025-12).
RATE_FFILL_MONTHS = 12
# Forward by covered interest parity, 3 months: F = S x ((1+r_US)/(1+r_loc))^(1/4),
# S and F in USD per unit of local currency (fx.csv convention). Selling the
# local currency forward returns F/S0 - S_T/S0 per unit hedged. Rolled at
# quarter-end month closes; marked to market at each month end with the then
# spot and rates for the remaining months.
FX_TENOR_MONTHS = 3
FX_HEDGE_RATIOS = (0.5, 1.0)

# ---------------------------------------------------------------------------
# Stress windows (method.md section 11), month-end dates
# ---------------------------------------------------------------------------
STRESS = {
    "gfc_2008": ("2007-10-31", "2009-02-28"),
    "taper_2013": ("2013-04-30", "2013-08-31"),
    "covid_2020": ("2020-01-31", "2020-03-31"),
    "inflation_2022": ("2021-12-31", "2022-10-31"),
}
STRONG_USD_SERIES = "USD_BROAD"      # FRED DTWEXBGS monthly, in yields.csv
STRONG_USD_RISE = 0.02
STRONG_USD_EPISODES = {"usd_2014": ("2014-06-30", "2015-03-31"), "usd_2021": ("2021-06-30", "2022-09-30")}

# Verdict, method.md s8 item 5 (standalone sleeve version; the portfolio test is Phase 5's):
# keep if OOS Sharpe rises, or OOS max drawdown improves by >= 2 percentage points, net of costs.
VERDICT_DD_POINTS = 0.02
