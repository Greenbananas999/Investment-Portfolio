"""Load the cached research data (see research/fetch.py) and build return series."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

DATA = Path(__file__).resolve().parent.parent / "data" / "research"


def _read(path):
    return pd.read_csv(path, index_col=0, parse_dates=True).sort_index()


def remove_spikes(df, jump=0.08, settle=0.04):
    """Blank one-day bad ticks (a value far from both neighbours that agree)."""
    prev, nxt = df.shift(1), df.shift(-1)
    spike = (((df / prev - 1).abs() > jump) & ((df / nxt - 1).abs() > jump)
             & ((nxt / prev - 1).abs() < settle))
    return df.mask(spike).ffill()


class Dataset:
    """Prices in local currency, FX as USD per unit, monthly yields in percent."""

    def __init__(self, prices, fx, yields, fundamentals=None, synthetic=False):
        self.prices = prices
        self.fx = fx.assign(USD=1.0)
        self.yields = yields
        self.fundamentals = fundamentals or {}
        self.synthetic = synthetic
        self.manual = set()

    @classmethod
    def load(cls):
        if not (DATA / "prices.csv").exists():
            raise FileNotFoundError(
                f"{DATA}/prices.csv not found. Run `python -m research.fetch` on a machine "
                "with access to Yahoo Finance and FRED, or use --synthetic.")
        prices = remove_spikes(_read(DATA / "prices.csv"))
        fx = remove_spikes(_read(DATA / "fx.csv"))
        yields = _read(DATA / "yields.csv") if (DATA / "yields.csv").exists() else pd.DataFrame()
        manual = DATA / "manual"
        if manual.exists():
            for f in manual.glob("*.csv"):
                s = _read(f).iloc[:, 0]
                yields[f.stem] = s.resample("MS").mean()
        fundamentals = {s.ticker: load_fundamentals(s.ticker) for s in config.STOCKS}
        ds = cls(prices, fx, yields, fundamentals)
        ds.manual = {f.stem for f in manual.glob("*.csv")} if manual.exists() else set()
        return ds

    # ---- monthly series -------------------------------------------------
    def month_end(self, df):
        return df.resample("ME").last()

    def monthly_prices(self):
        return self.month_end(self.prices)

    def monthly_fx(self):
        return self.month_end(self.fx.ffill())

    def monthly_yield(self, name):
        """Monthly yield in decimals, indexed at month end."""
        if name not in self.yields:
            return None
        s = self.yields[name].dropna() / 100.0
        s.index = s.index + pd.offsets.MonthEnd(0)
        return s.groupby(level=0).last()

    def stock_returns(self, key):
        """Monthly simple returns of a stock: (local, usd)."""
        s = config.STOCKS_BY_KEY[key]
        p = self.monthly_prices()[s.ticker].dropna()
        local = p.pct_change().dropna()
        fx = self.monthly_fx()[s.currency].reindex(p.index).ffill()
        usd = (p * fx).pct_change().dropna()
        return local, usd

    def index_returns(self, ticker, currency="USD", in_usd=True):
        p = self.monthly_prices()[ticker].dropna()
        if in_usd and currency != "USD":
            p = p * self.monthly_fx()[currency].reindex(p.index).ffill()
        return p.pct_change().dropna()

    def fx_returns(self, ccy):
        return self.monthly_fx()[ccy].pct_change().dropna()

    def risk_free_monthly(self, currency, assumptions):
        """Monthly risk-free return series in a currency.

        Uses the FRED short rate where it is current; Turkey's FRED rates stop
        in 2008-2010, so TRY uses the 2Y yield (manual file) and anything else
        missing or stale falls back to the flat assumption.
        """
        name = {"USD": "US_3M", "EUR": "FR_3M", "TRY": "TR_2Y", "KRW": "KR_3M"}.get(currency)
        idx = self.monthly_prices().index
        s = self.monthly_yield(name) if name else None
        if s is None or s.empty or s.index[-1] < idx[-1] - pd.Timedelta(days=400):
            return pd.Series(assumptions.risk_free[currency] / 12, index=idx)
        return (s / 12).shift(1).reindex(idx).ffill().dropna()

    def latest_yield(self, name):
        """(yield, date, source) from the series if current, else from config.SPOT_YIELDS."""
        s = self.monthly_yield(name)
        last_price = self.prices.dropna(how="all").index[-1]
        if s is not None and not s.empty and s.index[-1] >= last_price - pd.Timedelta(days=200):
            return float(s.iloc[-1]), str(s.index[-1].date()), "FRED monthly" if name not in self.manual else "manual file"
        if name in config.SPOT_YIELDS:
            return config.SPOT_YIELDS[name]
        return None, None, None


def load_fundamentals(ticker):
    d = DATA / "fundamentals" / ticker
    out = {"info": {}}
    if not d.exists():
        return out
    if (d / "info.json").exists():
        out["info"] = json.loads((d / "info.json").read_text())
    for f in d.glob("*.csv"):
        try:
            out[f.stem] = pd.read_csv(f, index_col=0)
        except Exception:
            pass
    return out


def synthetic(seed=0, years=15):
    """Random data with the real tickers, for tests and dry runs only."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(end="2026-10-23", periods=years * 252)
    tickers = sorted({s.ticker for s in config.STOCKS} | set(config.EXTRA_PRICE_TICKERS))
    n = len(tickers)
    a = rng.normal(size=(n, n)) * 0.007
    cov = a @ a.T + np.eye(n) * 0.0001
    mu = rng.normal(0.0004, 0.0002, n)
    rets = rng.multivariate_normal(mu, cov, len(days))
    prices = pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=days, columns=tickers)
    prices.loc[: days[600], "META"] = np.nan
    fx = pd.DataFrame(index=days)
    for ccy, drift in {"KRW": 0.0, "TWD": 0.0, "EUR": 0.0, "TRY": -0.0007}.items():
        fx[ccy] = np.cumprod(1 + rng.normal(drift, 0.006, len(days)))
    months = pd.date_range(days[0], days[-1], freq="MS")
    walk = lambda lvl, sd: np.clip(lvl + np.cumsum(rng.normal(0, sd, len(months))), 0.1, None)
    yields = pd.DataFrame({
        "US_3M": walk(2.0, 0.15), "US_10Y": walk(3.0, 0.15), "FR_10Y": walk(2.0, 0.15),
        "FR_3M": walk(1.0, 0.1), "TR_2Y": walk(15.0, 1.0), "TR_3M": walk(14.0, 1.0),
        "KR_3M": walk(2.0, 0.1),
    }, index=months)
    fundamentals = {}
    for s in config.STOCKS:
        price = float(prices[s.ticker].iloc[-1])
        fcf = rng.uniform(5e9, 5e10)
        years_idx = [f"{y}-12-31" for y in (2025, 2024, 2023, 2022)]
        cf = pd.DataFrame({y: [fcf * (0.9 ** i), fcf * 1.3 * (0.9 ** i), -fcf * 0.3]
                           for i, y in enumerate(years_idx)},
                          index=["Free Cash Flow", "Operating Cash Flow", "Capital Expenditure"])
        bs = pd.DataFrame({y: [fcf * 2, fcf * 3, 1e9 * (1 + 0.01 * i)] for i, y in enumerate(years_idx)},
                          index=["Total Debt", "Cash Cash Equivalents And Short Term Investments",
                                 "Ordinary Shares Number"])
        info = {"currentPrice": price, "marketCap": fcf * rng.uniform(15, 40),
                "forwardPE": rng.uniform(10, 35), "dividendRate": price * 0.01,
                "financialCurrency": s.currency, "currency": s.currency, "beta": 1.1}
        ge = pd.DataFrame({"stockTrend": [0.12, 0.10]}, index=["+1y", "+5y"])
        fundamentals[s.ticker] = {"info": info, "cashflow": cf, "balance_sheet": bs,
                                  "growth_estimates": ge}
    return Dataset(prices, fx, yields, fundamentals, synthetic=True)
