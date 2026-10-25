"""Securities, data sources and the forward-looking assumptions every model uses.

Everything a reader might want to challenge (risk premia, inflation, growth
fades, target P/E) lives here so the report can cite it in one place.
Market-data inputs (prices, yields, fundamentals) come from data/research/.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stock:
    key: str            # short label used in reports
    name: str
    ticker: str         # Yahoo ticker of the local listing (prices + fundamentals)
    currency: str       # local trading currency
    country: str
    local_index: str    # Yahoo ticker of the home-market index
    usd_ticker: str = ""  # US listing (ADR) if one exists, for a cross-check


STOCKS = [
    Stock("SKHYNIX", "SK Hynix", "000660.KS", "KRW", "KR", "^KS11"),
    Stock("SAMSUNG", "Samsung Electronics", "005930.KS", "KRW", "KR", "^KS11"),
    Stock("TSMC", "Taiwan Semiconductor", "2330.TW", "TWD", "TW", "^TWII", usd_ticker="TSM"),
    Stock("AAPL", "Apple", "AAPL", "USD", "US", "^GSPC"),
    Stock("NVDA", "Nvidia", "NVDA", "USD", "US", "^GSPC"),
    Stock("META", "Meta Platforms", "META", "USD", "US", "^GSPC"),
    Stock("MSFT", "Microsoft", "MSFT", "USD", "US", "^GSPC"),
]


@dataclass(frozen=True)
class Bond:
    key: str
    name: str
    currency: str
    country: str
    yield_series: str     # column in data/research/yields.csv (percent, monthly)
    maturity_years: float
    coupon_freq: int = 1


BONDS = [
    Bond("FR_OAT10", "France OAT 10Y", "EUR", "FR", "FR_10Y", 10.0, coupon_freq=1),
    # FRED/OECD carries no 10Y series for Turkey. The 6M-2Y government yield is
    # the longest free monthly history, so the default Turkish bond is a 2Y note.
    # Drop a monthly CSV at data/research/manual/TR_10Y.csv (date, yield %) and
    # the 10Y line below is used too.
    Bond("TR_GOV2", "Turkey government 2Y", "TRY", "TR", "TR_2Y", 2.0, coupon_freq=2),
    Bond("TR_GOV10", "Turkey government 10Y", "TRY", "TR", "TR_10Y", 10.0, coupon_freq=2),
]

# Benchmarks used for betas and for comparison lines.
GLOBAL_INDEX = "ACWI"        # MSCI ACWI ETF in USD: the market for a USD investor
US_INDEX = "^GSPC"
EXTRA_PRICE_TICKERS = ["ACWI", "SPY", "^GSPC", "^KS11", "^TWII", "^FCHI", "TSM", "^IRX", "^TNX"]

# Yahoo FX tickers: foreign units per 1 USD. Stored as USD per 1 unit.
FX_TICKERS = {"KRW": "KRW=X", "TWD": "TWD=X", "EUR": "EUR=X", "TRY": "TRY=X"}

# FRED series pulled without an API key (fredgraph.csv). Monthly, percent.
FRED_SERIES = {
    "US_3M": "TB3MS",
    "US_10Y": "GS10",
    "FR_10Y": "IRLTLT01FRM156N",
    "FR_3M": "IR3TIB01FRM156N",
    "TR_2Y": "IRLTST01TRM156N",
    "TR_3M": "IR3TIB01TRM156N",
    "KR_3M": "IR3TIB01KRM156N",
    "KR_10Y": "IRLTLT01KRM156N",
    # Annual CPI inflation, for real-return and PPP checks.
    "TR_CPI": "TURCPIALLMINMEI",
    "US_CPI": "CPIAUCSL",
    "FR_CPI": "FRACPIALLMINMEI",
}


@dataclass
class MarketAssumptions:
    """Forward-looking inputs, annual, decimals. Edit to run your own view.

    Sources (as of late 2026, rounded): Damodaran country risk premia
    (Jan 2026 update), IMF WEO inflation projections, central-bank policy
    rates. These are judgement calls, not market data; the report shows them.
    """
    mature_erp: float = 0.045            # equity risk premium, mature market
    country_risk_premium: dict = field(default_factory=lambda: {
        "US": 0.0, "KR": 0.008, "TW": 0.008, "FR": 0.007, "TR": 0.045})
    # Short rates used as the local risk-free rate when no yield series exists.
    risk_free: dict = field(default_factory=lambda: {
        "USD": 0.039, "KRW": 0.025, "TWD": 0.018, "EUR": 0.021, "TRY": 0.38})
    # Long-run inflation expectations (used for FX via relative PPP and for G-K).
    inflation: dict = field(default_factory=lambda: {
        "USD": 0.025, "KRW": 0.020, "TWD": 0.017, "EUR": 0.020, "TRY": 0.22})
    long_run_real_gdp: dict = field(default_factory=lambda: {
        "US": 0.018, "KR": 0.019, "TW": 0.025, "FR": 0.011, "TR": 0.035})
    horizon_years: int = 5


@dataclass
class DCFSettings:
    explicit_years: int = 10       # forecast years before the terminal value
    high_growth_years: int = 5     # growth held at the start rate, then fades linearly
    max_start_growth: float = 0.30  # cap on starting FCF growth
    min_start_growth: float = -0.05
    tax_rate: float = 0.21
    target_debt_weight_cap: float = 0.30
    cost_of_debt_spread: float = 0.012  # over the local risk-free rate
    terminal_growth_cap: float = 0.035
    # Memory makers' free cash flow swings with the DRAM cycle; normalise the
    # starting FCF to the average of the last N years instead of the last year.
    normalise_years: dict = field(default_factory=lambda: {"SKHYNIX": 4, "SAMSUNG": 4})


@dataclass
class GKSettings:
    """Grinold-Kroner: E[R] = D/P + inflation + real EPS growth - net dilution + repricing."""
    repricing_years: int = 10
    # P/E the market is assumed to drift toward over `repricing_years`.
    target_pe: dict = field(default_factory=lambda: {
        "SKHYNIX": 10.0, "SAMSUNG": 13.0, "TSMC": 18.0,
        "AAPL": 24.0, "NVDA": 28.0, "META": 22.0, "MSFT": 28.0})
    # Long-run real earnings growth caps: no company out-grows its economy forever.
    max_real_growth: float = 0.10


@dataclass
class MonteCarloSettings:
    n_paths: int = 20_000
    horizon_years: int = 5
    block_months: int = 6       # block bootstrap length, keeps momentum and vol clusters
    seed: int = 622


STOCK_KEYS = [s.key for s in STOCKS]
STOCKS_BY_KEY = {s.key: s for s in STOCKS}
