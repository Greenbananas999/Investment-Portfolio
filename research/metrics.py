"""Return statistics on monthly series."""

import numpy as np
import pandas as pd


def cagr(r):
    r = r.dropna()
    if len(r) < 2:
        return np.nan
    return float((1 + r).prod() ** (12 / len(r)) - 1)


def vol(r):
    return float(r.std() * np.sqrt(12))


def max_drawdown(r):
    w = (1 + r.fillna(0)).cumprod()
    return float((w / w.cummax() - 1).min())


def sharpe(r, rf):
    ex = (r - rf.reindex(r.index).fillna(0)).dropna()
    return float(ex.mean() / ex.std() * np.sqrt(12)) if ex.std() > 0 else np.nan


def info_ratio(r, bench):
    act = (r - bench.reindex(r.index)).dropna()
    return float(act.mean() / act.std() * np.sqrt(12)) if act.std() > 0 else np.nan


def beta(r, m):
    df = pd.concat([r, m], axis=1).dropna()
    if len(df) < 24:
        return np.nan
    c = np.cov(df.iloc[:, 0], df.iloc[:, 1])
    return float(c[0, 1] / c[1, 1])


def summary(r, rf, bench=None):
    out = {"CAGR": cagr(r), "Volatility": vol(r), "Sharpe": sharpe(r, rf),
           "Max drawdown": max_drawdown(r), "Months": int(r.dropna().shape[0]),
           "Start": str(r.dropna().index[0].date()) if len(r.dropna()) else ""}
    if bench is not None:
        out["Beta"] = beta(r, bench)
        out["Info ratio"] = info_ratio(r, bench)
    return out


def calendar_years(r):
    return (1 + r).groupby(r.index.year).prod() - 1
