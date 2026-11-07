"""Monthly growth series for the Compare page, built from data/research prices and FX.

Uses research.screen.usd_prices and monthly_returns (method.md section 2): USD
price = local adjusted close x USD per unit of local currency, monthly simple
returns from month-end closes. Each level series starts at 1.0 in the month
before its first return (or 2009-12-31 for names listed earlier), 4 decimals.
"""

import numpy as np
import pandas as pd

from research.screen import load_universe, monthly_returns, usd_prices
from research.screen.prices import read_wide_csv

START = "2010-01-31"


def _grid(end):
    return pd.date_range("2009-12-31", end, freq="ME")


def levels_from_returns(r, end):
    """DataFrame of growth levels (1.0 at the base month) on the month-end grid."""
    grid = _grid(end)
    out = {}
    for t in r.columns:
        s = r[t].loc[START:end]
        first = s.first_valid_index()
        if first is None:
            continue
        lv = (1 + s).cumprod()
        prior = first - pd.offsets.MonthEnd(1)
        lv = lv.reindex(grid)
        if prior in lv.index:
            lv.loc[prior] = 1.0
        out[t] = lv
    return pd.DataFrame(out, index=grid)


def to_lists(df, digits=4):
    """{ticker: [value or None, ...]} aligned to df.index."""
    res = {}
    for t in df.columns:
        vals = df[t].to_numpy(dtype=float)
        res[t] = [None if not np.isfinite(v) else round(float(v), digits) for v in vals]
    return res


def build_growth(root, tickers, end, local_tickers=(), blends=None):
    """Return (dates, usd_levels, local_levels) for the tickers present in prices.csv."""
    # same one-day spike removal the analysts used (fx.csv has a bad TWD quote on 2014-12-31)
    wanted = list(dict.fromkeys(list(tickers) + list(local_tickers)))
    prices = read_wide_csv(root / "data" / "research" / "prices.csv", spikes=True, columns=wanted)
    fx = read_wide_csv(root / "data" / "research" / "fx.csv", spikes=True)
    uni = load_universe(root / "research" / "plan" / "universe.csv")
    want = [t for t in dict.fromkeys(tickers) if t in prices.columns]
    sub = uni[uni["ticker"].isin(want)]
    usd = usd_prices(prices[want], fx, sub)
    # tickers the universe file does not cover are assumed to be USD quotes
    extra = [t for t in want if t not in usd.columns and t not in set(uni["ticker"])]
    if extra:
        usd = pd.concat([usd, prices[extra]], axis=1)
    mr = monthly_returns(usd)
    for name, w in (blends or {}).items():   # monthly-rebalanced fixed-weight references
        if all(t in mr.columns for t in w):
            mr[name] = sum(mr[t] * x for t, x in w.items())
    lv = levels_from_returns(mr, end)
    loc_cols = [t for t in local_tickers if t in prices.columns]
    local = None
    if loc_cols:
        local = levels_from_returns(monthly_returns(prices[loc_cols]), end)
    dates = [d.strftime("%Y-%m-%d") for d in lv.index]
    return dates, to_lists(lv), (to_lists(local) if local is not None else {})
