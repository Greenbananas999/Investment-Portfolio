"""Download everything the research models need into data/research/.

    python -m research.fetch

Needs open access to Yahoo Finance and fred.stlouisfed.org (the cloud
sandbox blocks both, so this is run on a home PC and the CSVs are committed).
Writes:
    prices.csv       daily adjusted closes, local currency, one column per ticker
    fx.csv           daily USD per 1 unit of KRW, TWD, EUR, TRY
    yields.csv       monthly yields/CPI from FRED, percent
    fundamentals/<TICKER>/{info.json,cashflow.csv,balance_sheet.csv,income_stmt.csv,growth_estimates.csv}
    fetch_log.txt    what succeeded, what failed
"""

import io
import json
import urllib.request
from pathlib import Path

import pandas as pd

from . import config

DATA = Path(__file__).resolve().parent.parent / "data" / "research"
START = "2005-01-01"


def _close(tickers):
    import yfinance as yf

    raw = yf.download(tickers, start=START, auto_adjust=True, progress=False, threads=True)
    close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    return close.sort_index()


def fetch_prices(log):
    tickers = [s.ticker for s in config.STOCKS] + config.EXTRA_PRICE_TICKERS
    close = _close(sorted(set(tickers)))
    for t in tickers:
        n = close[t].dropna().shape[0] if t in close else 0
        log.append(f"price {t}: {n} rows")
    close.to_csv(DATA / "prices.csv")


def fetch_fx(log):
    close = _close(list(config.FX_TICKERS.values()))
    fx = pd.DataFrame(index=close.index)
    for ccy, t in config.FX_TICKERS.items():
        fx[ccy] = 1.0 / close[t]
        log.append(f"fx {ccy}: {close[t].dropna().shape[0]} rows")
    fx.ffill().to_csv(DATA / "fx.csv")


def _fred(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    with urllib.request.urlopen(url, timeout=30) as r:
        df = pd.read_csv(io.StringIO(r.read().decode()), index_col=0, parse_dates=True)
    return pd.to_numeric(df.iloc[:, 0], errors="coerce")


def fetch_yields(log):
    out = {}
    for name, sid in config.FRED_SERIES.items():
        try:
            s = _fred(sid).dropna()
            out[name] = s
            log.append(f"fred {name} ({sid}): {len(s)} rows, {s.index[0].date()} to {s.index[-1].date()}")
        except Exception as e:  # keep going; the models skip what is missing
            log.append(f"fred {name} ({sid}): FAILED {e}")
    pd.DataFrame(out).to_csv(DATA / "yields.csv")


def fetch_fundamentals(log):
    import yfinance as yf

    for s in config.STOCKS:
        d = DATA / "fundamentals" / s.ticker
        d.mkdir(parents=True, exist_ok=True)
        t = yf.Ticker(s.ticker)
        try:
            info = {k: v for k, v in t.info.items() if isinstance(v, (int, float, str, bool))}
            (d / "info.json").write_text(json.dumps(info, indent=1, sort_keys=True))
            log.append(f"info {s.ticker}: {len(info)} fields")
        except Exception as e:
            log.append(f"info {s.ticker}: FAILED {e}")
        for name in ("cashflow", "balance_sheet", "income_stmt", "growth_estimates",
                     "earnings_estimate", "revenue_estimate", "dividends"):
            try:
                df = getattr(t, name)
                if df is None or len(df) == 0:
                    log.append(f"{name} {s.ticker}: empty")
                    continue
                df.to_csv(d / f"{name}.csv")
                log.append(f"{name} {s.ticker}: ok")
            except Exception as e:
                log.append(f"{name} {s.ticker}: FAILED {e}")


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    log = []
    for step in (fetch_prices, fetch_fx, fetch_yields, fetch_fundamentals):
        try:
            step(log)
        except Exception as e:
            log.append(f"{step.__name__}: FAILED {e}")
    (DATA / "fetch_log.txt").write_text("\n".join(log) + "\n")
    print("\n".join(log))


if __name__ == "__main__":
    main()
