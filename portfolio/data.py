"""Price and FX download with a local CSV cache.

`load_prices()` returns adjusted daily closes (USD) for the universe, the
risk-free proxy and the benchmark. `load_fx()` returns daily USD-per-foreign
currency rates. Both read from data/*.csv when present so the pipeline can
run offline after one download, and so prices pulled elsewhere (for example
on a home PC) can be dropped in.
"""

from pathlib import Path

import pandas as pd

from . import config

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRICES_CSV = DATA_DIR / "prices.csv"
FX_CSV = DATA_DIR / "fx.csv"


def _download(tickers, start):
    import yfinance as yf

    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False, threads=True)
    if raw.empty:
        raise RuntimeError(
            "No data returned from Yahoo Finance. Check the network, or put "
            f"prices in {PRICES_CSV} (date index, one column per ticker)."
        )
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    if not isinstance(raw.columns, pd.MultiIndex):
        close.columns = tickers
    missing = [t for t in tickers if t not in close.columns or close[t].dropna().empty]
    if missing:
        raise RuntimeError(f"Yahoo Finance returned no data for: {', '.join(missing)}")
    return close.sort_index()


def _read_csv(path):
    return pd.read_csv(path, index_col=0, parse_dates=True).sort_index()


def load_prices(start="2010-01-01", refresh=False):
    tickers = config.TICKERS + [config.RISK_FREE, config.BENCHMARK]
    if PRICES_CSV.exists() and not refresh:
        prices = _read_csv(PRICES_CSV)
        missing = [t for t in tickers if t not in prices.columns]
        if missing:
            raise RuntimeError(f"{PRICES_CSV} is missing {missing}; rerun with --refresh")
        return prices[tickers]
    prices = _download(tickers, start)
    DATA_DIR.mkdir(exist_ok=True)
    prices.to_csv(PRICES_CSV)
    return prices[tickers]


def load_fx(start="2010-01-01", refresh=False):
    """Daily USD value of one unit of each foreign currency."""
    if FX_CSV.exists() and not refresh:
        return _read_csv(FX_CSV)
    direct = config.FX_TICKERS_DIRECT
    inverse = config.FX_TICKERS_INVERSE
    raw = _download(list(direct.values()) + list(inverse.values()), start)
    fx = pd.DataFrame(index=raw.index)
    for ccy, t in direct.items():
        fx[ccy] = raw[t]
    for ccy, t in inverse.items():
        fx[ccy] = 1.0 / raw[t]
    fx = fx.ffill()
    DATA_DIR.mkdir(exist_ok=True)
    fx.to_csv(FX_CSV)
    return fx


def daily_returns(prices):
    """Simple daily returns; leading NaNs are kept for assets that list later."""
    return prices.pct_change(fill_method=None).iloc[1:]


def fx_exposure_returns(fx, index):
    """Daily FX return of each asset's currency basket (USD per foreign unit).

    Returns a DataFrame aligned to `index` with one column per universe asset.
    Assets with no unhedged FX exposure get zeros.
    """
    fx_ret = fx.reindex(index.union(fx.index)).ffill().reindex(index).pct_change(fill_method=None).fillna(0.0)
    out = pd.DataFrame(0.0, index=index, columns=config.TICKERS)
    for a in config.UNIVERSE:
        for ccy, w in a.fx.items():
            if ccy in fx_ret.columns:
                out[a.ticker] += w * fx_ret[ccy]
    return out
