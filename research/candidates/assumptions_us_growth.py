"""Assumptions the US growth adapters need that research/config.py does not carry.

Everything else (equity risk premium, risk-free rate, inflation, US real GDP,
DCF fade, terminal growth cap, Monte Carlo block length and seed) is taken
unchanged from research/config.py (MarketAssumptions, DCFSettings, GKSettings,
MonteCarloSettings). Only the values below are new. No value here comes from
the web; each one is either a config.py value or is derived from data on disk
with the command given.

Derived values were computed on 2026-11-07 with
    python -m research.candidates.us_growth --pe-history
(median of month-end trailing P/E, 2016-11 to the last full month, 2026-10; split- and
dividend-unadjusted Yahoo close / latest point-in-time EDGAR diluted EPS
known at that month end). They are frozen here so that the forward models do
not move when the data is refreshed; rerun the command to audit them.
"""

from dataclasses import dataclass, field

# Ten-year median trailing P/E, from the command above (kept for audit; not a target by itself).
PE_MEDIAN_10Y = {
    "AVGO": 47.5, "META": 31.0, "AMZN": 81.9, "REGN": 20.8,
    "NVDA": 64.1, "ADBE": 51.1, "MA": 40.9, "GILD": 18.9,
}

# Cap on the target forward P/E: 23 = median of the four US targets already in
# research/config.py GKSettings.target_pe (AAPL 24, NVDA 22, META 20, MSFT 26).
# A mega-cap's own 2016-2026 multiple was set during a decade of falling rates
# and is not assumed to come back; the cap keeps new names on the same scale
# as the names config.py already covers.
TARGET_PE_CAP = 23.0


@dataclass(frozen=True)
class USGrowthAssumptions:
    # Target TRAILING GAAP P/E reached over GKSettings.repricing_years (10 years).
    # Basis (review 2026-11-07): the current end is also trailing GAAP (yfinance trailingPE,
    # TTM), so the repricing term compares like with like; the adapter in us_growth.py
    # (gk_settings_same_basis) converts the target to the forward-equivalent the module expects.
    # NVDA and META reuse the config.py numbers as trailing anchors (config labels them forward).
    # Rule: research/config.py value where the name is already there (NVDA, META);
    # otherwise min(PE_MEDIAN_10Y, TARGET_PE_CAP).
    target_pe: dict = field(default_factory=lambda: {
        "NVDA": 22.0,   # research/config.py GKSettings.target_pe["NVDA"]
        "META": 20.0,   # research/config.py GKSettings.target_pe["META"]
        "AVGO": 23.0,   # min(47.5, 23): cap binds
        "AMZN": 23.0,   # min(81.9, 23): cap binds
        "REGN": 20.8,   # own 10-year median trailing P/E, below the cap
        "ADBE": 23.0,   # min(51.1, 23): cap binds
        "MA": 23.0,     # min(40.9, 23): cap binds
        "GILD": 18.9,   # own 10-year median trailing P/E, below the cap
    })

    # Per-name cap on the analyst growth rate used for DCF years 2-5 and G-K
    # years 1-5. Default = config.py (DCFSettings.max_start_growth = 0.20,
    # GKSettings.analyst_growth_cap = 0.20). Override only where the analyst EPS
    # growth is a base effect rather than growth.
    growth_cap: dict = field(default_factory=lambda: {
        # GILD: +1y EPS growth in growth_estimates.csv is +1130% because the
        # current-year EPS consensus is negative (-0.98, a one-off charge). The
        # +1y revenue growth consensus is used instead: 6.98%
        # (data/research/fundamentals/GILD/revenue_estimate.csv, row +1y, column growth).
        "GILD": 0.0698,
    })
    default_growth_cap: float = 0.20     # research/config.py DCFSettings.max_start_growth

    # Cyclical (memory-style) mid-cycle fade from DCFSettings.cyclical_mid_cycle.
    # None of the eight is flagged: config.py already treats NVDA as non-cyclical
    # and the same rule is applied to AVGO; the Monte Carlo and the 5-95 range
    # carry the cycle risk instead. Stated so a reviewer can challenge it.
    cyclical_mid_cycle: dict = field(default_factory=dict)

    # Forward Monte Carlo horizon = the client horizon (method.md section 1),
    # replacing MonteCarloSettings.horizon_years = 5.
    horizon_years: int = 7

    # Home index for the local CAPM beta (task brief: local_index "^GSPC").
    local_index: str = "^GSPC"


ASSUMPTIONS = USGrowthAssumptions()
