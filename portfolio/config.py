"""Investment universe and assignment rules.

All assets are US-listed ETFs priced in USD (home currency). Each asset is
tagged as US or non-US so the optimizer can enforce the class rule that at
least 70% of the portfolio sits in non-US assets.

`fx` maps each asset to the currencies its holdings are exposed to *unhedged*.
Weights are approximate fund currency mixes; currency-hedged funds and
USD-denominated bonds map to {} (no FX exposure). These are used only to
split returns into a local part and an FX part for reporting.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Asset:
    ticker: str
    name: str
    asset_class: str  # "equity", "bond", "cash"
    non_us: bool
    fx: dict = field(default_factory=dict)


UNIVERSE = [
    # Developed ex-US equity
    Asset("EFA", "MSCI EAFE", "equity", True,
          {"EUR": 0.33, "JPY": 0.23, "GBP": 0.15, "CHF": 0.10, "AUD": 0.07, "SEK": 0.03, "DKK": 0.03}),
    Asset("HEFA", "MSCI EAFE, USD-hedged", "equity", True, {}),
    Asset("VGK", "FTSE Europe", "equity", True,
          {"EUR": 0.52, "GBP": 0.24, "CHF": 0.14, "SEK": 0.05, "DKK": 0.05}),
    Asset("EWJ", "MSCI Japan", "equity", True, {"JPY": 1.0}),
    Asset("DXJ", "Japan, USD-hedged", "equity", True, {}),
    Asset("EWU", "MSCI United Kingdom", "equity", True, {"GBP": 1.0}),
    Asset("EWC", "MSCI Canada", "equity", True, {"CAD": 1.0}),
    Asset("EWA", "MSCI Australia", "equity", True, {"AUD": 1.0}),
    # Emerging equity
    Asset("EEM", "MSCI Emerging Markets", "equity", True,
          {"CNY": 0.27, "TWD": 0.19, "INR": 0.19, "KRW": 0.11, "BRL": 0.05}),
    Asset("INDA", "MSCI India", "equity", True, {"INR": 1.0}),
    Asset("EWT", "MSCI Taiwan", "equity", True, {"TWD": 1.0}),
    Asset("MCHI", "MSCI China", "equity", True, {"CNY": 1.0}),
    # Non-US bonds
    Asset("BNDX", "Intl aggregate bonds, USD-hedged", "bond", True, {}),
    Asset("IGOV", "Intl government bonds, unhedged", "bond", True,
          {"EUR": 0.45, "JPY": 0.20, "GBP": 0.10, "CAD": 0.05, "AUD": 0.05}),
    Asset("EMB", "EM sovereign bonds (USD-denominated)", "bond", True, {}),
    # US sleeve (max 30% under the class rule)
    Asset("SPY", "S&P 500", "equity", False),
    Asset("IEF", "US Treasuries 7-10y", "bond", False),
    Asset("GLD", "Gold", "commodity", False),
]

# Risk-free / cash proxy. Used for Sharpe, not traded by the optimizer.
RISK_FREE = "BIL"
# Benchmark shown next to the strategies.
BENCHMARK = "ACWI"

# Yahoo tickers quoted as USD per 1 unit of foreign currency.
FX_TICKERS_DIRECT = {"EUR": "EURUSD=X", "GBP": "GBPUSD=X", "AUD": "AUDUSD=X"}
# Yahoo tickers quoted as foreign units per 1 USD (inverted after download).
FX_TICKERS_INVERSE = {
    "JPY": "JPY=X", "CHF": "CHF=X", "CAD": "CAD=X", "SEK": "SEK=X", "DKK": "DKK=X",
    "CNY": "CNY=X", "TWD": "TWD=X", "INR": "INR=X", "KRW": "KRW=X", "BRL": "BRL=X",
}


@dataclass
class Rules:
    min_non_us: float = 0.70       # class rule: at least 70% non-US
    max_weight: float = 0.25       # cap on any single ETF
    capital: float = 100_000.0     # paper account, USD
    long_only: bool = True


@dataclass
class BacktestSettings:
    start: str = "2012-01-01"
    lookback_days: int = 756       # ~3 years of daily data per estimate
    rebalance_days: int = 21       # ~monthly
    cost_bps: float = 5.0          # one-way trading cost on turnover


TICKERS = [a.ticker for a in UNIVERSE]
ASSETS = {a.ticker: a for a in UNIVERSE}
