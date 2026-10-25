"""Historical backtest: what each asset actually returned, in local currency and USD."""

import numpy as np
import pandas as pd

from . import bonds, config, metrics


def asset_returns(ds):
    """{key: (local, usd, currency, label)} for every stock and bond with data."""
    out = {}
    for s in config.STOCKS:
        local, usd = ds.stock_returns(s.key)
        out[s.key] = (local, usd, s.currency, s.name)
    for b in config.BONDS:
        local, usd = bonds.returns(b, ds)
        if local is not None and local.index[-1] >= ds.monthly_prices().index[-1] - pd.Timedelta(days=200):
            out[b.key] = (local, usd, b.currency, b.name)
    return out


def window(r, years):
    if years is None:
        return r
    return r[r.index > r.index[-1] - pd.DateOffset(years=years)]


def run(ds, a):
    assets = asset_returns(ds)
    rf_usd = ds.risk_free_monthly("USD", a)
    acwi = ds.index_returns(config.GLOBAL_INDEX)
    stats = {}
    for key, (local, usd, ccy, label) in assets.items():
        rf_loc = ds.risk_free_monthly(ccy, a)
        stats[key] = {"label": label, "currency": ccy, "periods": {}}
        for name, yrs in (("Since 2010", None), ("10 years", 10), ("5 years", 5)):
            u = window(usd[usd.index >= "2010-01-01"], yrs)
            l = window(local[local.index >= "2010-01-01"], yrs)
            su, sl = metrics.summary(u, rf_usd, acwi), metrics.summary(l, rf_loc)
            stats[key]["periods"][name] = {
                "usd": su, "local": sl,
                "fx_contribution": su["CAGR"] - sl["CAGR"],
            }
        stats[key]["calendar_usd"] = {int(k): float(v) for k, v in metrics.calendar_years(usd[usd.index >= "2010-01-01"]).items()}
        stats[key]["calendar_local"] = {int(k): float(v) for k, v in metrics.calendar_years(local[local.index >= "2010-01-01"]).items()}
    return assets, stats


def growth_series(assets, start="2015-01-01"):
    """Growth of 1 in local currency and USD from a common start, for charts."""
    out = {}
    for key, (local, usd, _, _) in assets.items():
        l, u = local[local.index >= start], usd[usd.index >= start]
        out[key] = {"dates": [d.strftime("%Y-%m") for d in u.index],
                    "usd": (1 + u).cumprod().round(4).tolist(),
                    "local": (1 + l.reindex(u.index).fillna(0)).cumprod().round(4).tolist()}
    return out


def sample_portfolio(assets, ds, a, weights=None):
    """Monthly-rebalanced buy list in USD vs ACWI: the 70% non-US / 30% US split."""
    if weights is None:
        non_us = [k for k in assets if k in ("SKHYNIX", "SAMSUNG", "TSMC") or k.startswith(("FR_", "TR_"))]
        us = [k for k in assets if k not in non_us]
        weights = {**{k: 0.70 / len(non_us) for k in non_us}, **{k: 0.30 / len(us) for k in us}}
    usd = pd.DataFrame({k: assets[k][1] for k in weights}).dropna()
    w = pd.Series(weights)
    port = (usd[w.index] * w).sum(axis=1)
    acwi = ds.index_returns(config.GLOBAL_INDEX).reindex(port.index)
    rf = ds.risk_free_monthly("USD", a)
    return {
        "weights": weights, "start": str(port.index[0].date()), "end": str(port.index[-1].date()),
        "portfolio": metrics.summary(port, rf, acwi),
        "acwi": metrics.summary(acwi.dropna(), rf),
        "growth": {"dates": [d.strftime("%Y-%m") for d in port.index],
                   "portfolio": (1 + port).cumprod().round(4).tolist(),
                   "acwi": (1 + acwi.fillna(0)).cumprod().round(4).tolist()},
    }, port
