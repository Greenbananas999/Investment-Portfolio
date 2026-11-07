"""Universe file, USD prices, monthly returns, type benchmarks and price de-adjustment.

Conventions (method.md sections 2 and 9):
- Prices are Yahoo adjusted closes in the listing's local currency.
- USD price = local price x USD per 1 unit of the currency (fx.csv), with FX
  forward-filled onto the price dates. A US listing/ADR is never used as the
  price; it is only compared in `usd_crosscheck`.
- Monthly returns use calendar month ends ('ME'), last available close in the
  month, `pct_change(fill_method=None)`.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ..data import remove_spikes

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research"
PLAN = ROOT / "research" / "plan"

IN_SAMPLE_START = "2010-01-01"
IN_SAMPLE_END = "2017-12-31"
MIN_MONTHS = 60
SHORT_HISTORY_MONTHS = 120

TYPES = {"us_growth_stock", "intl_growth_stock", "em_bond", "other", "overlay",
         "benchmark", "index", "fx", "rf"}
ROLES = {"candidate", "faded_leader", "not_testable", "excluded", "benchmark", "support"}
SCREENED_ROLES = ("candidate", "faded_leader")
SCREEN_TYPES = ("us_growth_stock", "intl_growth_stock", "em_bond", "other")
UNIVERSE_COLUMNS = ["ticker", "name", "type", "role", "country", "currency", "listing",
                    "usd_ticker", "local_index", "edgar_cik", "since", "market_cap_usd_bn",
                    "aum_usd_bn", "expense_ratio", "category", "notes", "source_url"]
NUMERIC = ["market_cap_usd_bn", "aum_usd_bn", "expense_ratio"]

# method.md section 9: benchmark id -> {ticker: weight}, rebalanced monthly.
BENCHMARKS = {
    "IVW": {"IVW": 1.0},
    "EFG_EEM_5050": {"EFG": 0.5, "EEM": 0.5},
    "EMB": {"EMB": 1.0},
    "EMLC": {"EMLC": 1.0},
    "GLD": {"GLD": 1.0},
}
TYPE_BENCHMARK = {"us_growth_stock": "IVW", "intl_growth_stock": "EFG_EEM_5050",
                  "em_bond": "EMB", "other": "GLD"}
SLEEVE_BENCHMARKS = ["IVW", "EFG_EEM_5050", "EMB", "GLD"]


def load_universe(path):
    """Read universe.csv (data_request.md section 1) into a clean DataFrame.

    Missing columns are added empty; `type`/`role` are lower-cased; `edgar_cik`
    is kept as a string (leading zeros); numeric columns are coerced. Problems
    (unknown type or role, duplicate ticker) go to a `universe_flags` column
    instead of raising.
    """
    df = pd.read_csv(path, dtype={"edgar_cik": str, "since": str}, keep_default_na=True)
    df.columns = [c.strip() for c in df.columns]
    for c in UNIVERSE_COLUMNS:
        if c not in df.columns:
            df[c] = np.nan
    for c in ("ticker", "type", "role", "country", "currency", "usd_ticker", "edgar_cik"):
        df[c] = df[c].astype("string").str.strip()
    df["type"] = df["type"].str.lower()
    df["role"] = df["role"].str.lower()
    df["currency"] = df["currency"].str.upper()
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    flags = pd.Series("", index=df.index, dtype=object)
    flags[~df["type"].isin(TYPES)] += "unknown type; "
    flags[~df["role"].isin(ROLES)] += "unknown role; "
    flags[df["ticker"].duplicated(keep="first")] += "duplicate ticker (first row used); "
    flags[df["currency"].isna()] += "no currency (USD assumed); "
    df["universe_flags"] = flags.str.rstrip("; ")
    df = df[df["ticker"].notna()].drop_duplicates("ticker", keep="first")
    for c in df.columns:   # text columns: plain str, "" for missing (pd.NA is not truthy-safe)
        if c not in NUMERIC:
            df[c] = [("" if pd.isna(x) else str(x)) for x in df[c]]
    return df.reset_index(drop=True)


US_VENUES = {"nyse", "nyse arca", "nyse american", "nasdaq", "nasdaq gm", "nasdaq gs", "nasdaq cm",
             "cboe bzx", "nyse arca/nasdaq", "open-end", "otc", "adr"}


def price_currency(row, fx_columns=None):
    """Currency the row's Yahoo price is quoted in.

    The `currency` column is used when it is an FX column (or USD). When it is
    not (EM bond funds write LOCAL or MIXED for their exposure) and the
    listing is a US venue or a US open-end fund, the price is in USD.
    Returns None when neither applies.
    """
    ccy = row.get("currency")
    ccy = ccy if isinstance(ccy, str) and ccy else None
    if ccy == "USD" or (ccy and fx_columns is not None and ccy in fx_columns):
        return ccy
    if str(row.get("listing", "")).strip().lower() in US_VENUES:
        return "USD"
    return None if ccy else "USD"


def usd_prices(prices_local, fx, universe):
    """Daily USD prices for every universe ticker found in `prices_local` (method.md s2).

    USD price = local adjusted close x USD per unit of the row's price
    currency (`price_currency`; USD = 1). FX is forward-filled onto the price
    dates (never backward). Tickers with no price column, or whose currency
    has no FX column, are left out; `price_coverage` reports why.
    """
    fx = fx.copy()
    fx["USD"] = 1.0
    out = {}
    for _, row in universe.iterrows():
        t = row["ticker"]
        if t not in prices_local.columns:
            continue
        ccy = price_currency(row, fx.columns)
        if ccy is None or ccy not in fx.columns:
            continue
        p = prices_local[t].dropna()
        if p.empty:
            continue
        rate = fx[ccy].reindex(fx.index.union(p.index)).ffill().reindex(p.index)
        out[t] = p * rate
    return pd.DataFrame(out).sort_index()


def price_coverage(prices_local, fx, universe):
    """Why each universe ticker does or does not have a USD price (for flags)."""
    rows = []
    fxc = set(fx.columns) | {"USD"}
    for _, row in universe.iterrows():
        t, ccy = row["ticker"], price_currency(row, fxc)
        if t not in prices_local.columns or prices_local[t].dropna().empty:
            why = "no price data"
        elif ccy is None or ccy not in fxc:
            why = f"no FX series for {row.get('currency')}"
        else:
            why = ""
        rows.append({"ticker": t, "price_problem": why})
    return pd.DataFrame(rows).set_index("ticker")["price_problem"]


def monthly_prices(daily):
    """Last available close in each calendar month ('ME')."""
    return daily.resample("ME").last()


def monthly_returns(daily, drop_partial=False):
    """Monthly simple returns from daily prices, month-end ('ME') resampling (method.md s2).

    A month with no observation for a ticker is NaN, and so is the return
    after it (no filling across gaps). `drop_partial` drops the final month
    when the last date is before that month's last business day.
    """
    m = monthly_prices(daily)
    r = m.pct_change(fill_method=None)
    if drop_partial and len(daily.index):
        last = daily.index.max()
        if last < last + pd.offsets.BMonthEnd(0):
            r = r.iloc[:-1]
    return r.iloc[1:]


def benchmark_monthly(benchmark_id, monthly_usd):
    """Monthly return of a method.md section 9 benchmark, rebalanced monthly.

    `monthly_usd` must hold the component tickers' monthly USD returns.
    Returns None if a component is missing; months where any component is
    missing are NaN.
    """
    w = BENCHMARKS[benchmark_id]
    if not all(t in monthly_usd.columns for t in w):
        return None
    r = sum(monthly_usd[t] * x for t, x in w.items())
    return r.rename(benchmark_id)


def benchmark_level(returns):
    """Month-end index level (start 1) from monthly returns, NaN before the first return."""
    r = returns.dropna()
    if r.empty:
        return r
    lvl = (1 + r).cumprod()
    first = r.index[0] - pd.offsets.MonthEnd(1)
    return pd.concat([pd.Series([1.0], index=[first]), lvl]).rename(returns.name)


def is_local_currency_bond(row):
    """EM bond fund is local-currency (benchmark EMLC) if category/name/notes say so."""
    text = " ".join(str(row.get(c, "")) for c in ("category", "name", "notes")).lower()
    return "local" in text


def type_benchmark_ids(universe):
    """{ticker: benchmark id} for screened rows; EM local-currency funds get EMLC."""
    out = {}
    for _, row in universe.iterrows():
        b = TYPE_BENCHMARK.get(row["type"])
        if row["type"] == "em_bond" and is_local_currency_bond(row):
            b = "EMLC"
        out[row["ticker"]] = b
    return out


def usd_crosscheck(daily_usd, usd_listing, universe, as_of=None):
    """Compare each local-listing USD series with its US listing/ADR (cross-check only).

    Returns per ticker: usd_ticker, months of overlap, correlation of monthly
    returns, and the annualised mean monthly return difference (local in USD
    minus ADR). Data after `as_of` is not used.
    """
    rows = []
    for _, row in universe.iterrows():
        t, u = row["ticker"], row["usd_ticker"]
        rec = {"ticker": t, "usd_ticker": u if isinstance(u, str) else None,
               "adr_months": 0, "adr_corr": np.nan, "adr_ann_diff": np.nan}
        if isinstance(u, str) and u and u != t and t in daily_usd and usd_listing is not None \
                and u in usd_listing:
            a = daily_usd[t].loc[:as_of] if as_of else daily_usd[t]
            b = usd_listing[u].loc[:as_of] if as_of else usd_listing[u]
            ra = monthly_returns(a.to_frame()).iloc[:, 0]
            rb = monthly_returns(b.to_frame()).iloc[:, 0]
            both = pd.concat([ra, rb], axis=1).dropna()
            if len(both) >= 12:
                rec.update(adr_months=len(both), adr_corr=float(both.corr().iloc[0, 1]),
                           adr_ann_diff=float((both.iloc[:, 0] - both.iloc[:, 1]).mean() * 12))
        rows.append(rec)
    return pd.DataFrame(rows).set_index("ticker")


def dividend_factor(adj_close, dividends):
    """Yahoo's cumulative dividend adjustment factor D(d), so raw(d) = adj(d) / D(d).

    Yahoo multiplies closes before each ex-date e by (1 - div_e / close_{e-1}),
    with close the split-adjusted, not dividend-adjusted, price. Working back
    from the last ex-date: close_{e-1} = adj_{e-1} / D_after + div_e. Returns a
    Series on `adj_close`'s index (1.0 when there are no dividends).
    """
    p = adj_close.dropna()
    fac = pd.Series(1.0, index=p.index)
    if dividends is None or len(dividends) == 0 or p.empty:
        return fac
    d = dividends[(dividends > 0) & (dividends.index <= p.index[-1])].sort_index()
    after = 1.0
    for e, div in d.iloc[::-1].items():
        before = p.index[p.index < e]
        if len(before) == 0:
            continue
        prev = before[-1]
        close = p.loc[prev] / after + div
        f = 1.0 - div / close
        if not 0.5 < f <= 1.0:
            continue
        after *= f
        fac.loc[fac.index < e] *= f
    return fac


def read_dividends(path):
    """yfinance dividends.csv (tz-aware dates) -> Series indexed by naive date."""
    try:
        df = pd.read_csv(path)
    except (OSError, ValueError):
        return None
    if df.shape[1] < 2 or df.empty:
        return None
    idx = pd.to_datetime(df.iloc[:, 0].astype(str).str.slice(0, 10), errors="coerce")
    s = pd.Series(pd.to_numeric(df.iloc[:, 1], errors="coerce").to_numpy(), index=idx)
    return s[s.index.notna()].dropna().sort_index()


def clean_spikes(df):
    """`research.data.remove_spikes` applied to each column on its own trading dates.

    Running it per column keeps genuine gaps (holidays on other calendars,
    delistings) as NaN instead of forward-filling them.
    """
    out = {}
    for c in df.columns:
        s = df[c].dropna()
        out[c] = remove_spikes(s.to_frame()).iloc[:, 0] if len(s) > 2 else s
    return pd.DataFrame(out, index=df.index) if out else df


def read_wide_csv(path, spikes=True, columns=None):
    """Date-indexed CSV (prices, fx, volume) with optional one-day spike removal.
    `columns` limits the read to those columns (others are skipped)."""
    if columns is not None:
        head = pd.read_csv(path, nrows=0).columns
        keep = [head[0]] + [c for c in head[1:] if c in set(columns)]
        df = pd.read_csv(path, index_col=0, parse_dates=True, usecols=keep).sort_index()
    else:
        df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df = df.apply(pd.to_numeric, errors="coerce")
    return clean_spikes(df) if spikes else df
