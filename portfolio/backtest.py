"""Walk-forward (out-of-sample) backtest.

At each rebalance date the optimizer sees only the trailing `lookback_days`
of returns, then holds the resulting weights (drifting with prices) until the
next rebalance. Trading costs are charged on turnover.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config, optimize


@dataclass
class Result:
    name: str
    returns: pd.Series          # daily portfolio return, net of costs
    fx_contribution: pd.Series  # daily FX part of that return
    weights: pd.DataFrame       # target weights at each rebalance
    turnover: pd.Series         # one-way turnover at each rebalance


STRATEGIES = ("max_sharpe", "min_variance", "equal_weight")


def target_weights(strategy, window, rf_window, rules, mean_shrinkage=0.5):
    """Weights for one strategy from a lookback window of asset returns."""
    tickers = list(window.columns)
    available = window.notna().all().to_numpy()
    non_us = np.array([config.ASSETS[t].non_us for t in tickers])
    if strategy == "equal_weight":
        return optimize.equal_weight(available, non_us, rules.min_non_us)
    excess = window.loc[:, available].sub(rf_window, axis=0).to_numpy()
    mu_a, cov_a = optimize.estimate(excess, mean_shrinkage)
    n = len(tickers)
    mu = np.zeros(n)
    cov = np.eye(n) * 1e-4
    idx = np.flatnonzero(available)
    mu[idx] = mu_a
    cov[np.ix_(idx, idx)] = cov_a
    if strategy == "min_variance":
        return optimize.min_variance(cov, available, non_us, rules.max_weight, rules.min_non_us)
    if strategy == "max_sharpe":
        return optimize.max_sharpe(mu, cov, available, non_us, rules.max_weight, rules.min_non_us)
    raise ValueError(strategy)


def run(strategy, asset_ret, rf_ret, fx_exp, rules, settings):
    tickers = list(asset_ret.columns)
    dates = asset_ret.index
    first = max(settings.lookback_days, int(dates.searchsorted(pd.Timestamp(settings.start))))
    if first >= len(dates):
        raise ValueError("not enough history for the chosen start date and lookback")

    cost = settings.cost_bps / 1e4
    w = np.zeros(len(tickers))
    port, fx_part = [], []
    weight_rows, turnover = {}, {}
    filled = asset_ret.fillna(0.0).to_numpy()
    fx_np = fx_exp[tickers].to_numpy()

    for i in range(first, len(dates)):
        trade_cost = 0.0
        if (i - first) % settings.rebalance_days == 0:
            window = asset_ret.iloc[i - settings.lookback_days:i].copy()
            # Only hold assets that also have a price on the rebalance day.
            window.loc[:, asset_ret.iloc[i].isna().to_numpy()] = np.nan
            new_w = target_weights(strategy, window, rf_ret.iloc[i - settings.lookback_days:i], rules)
            traded = np.abs(new_w - w).sum()
            trade_cost = cost * traded
            w = new_w
            weight_rows[dates[i]] = w
            turnover[dates[i]] = traded / 2
        r = filled[i]
        rp = w @ r
        port.append(rp - trade_cost)
        fx_part.append(w @ fx_np[i])
        w = w * (1 + r) / (1 + rp)

    idx = dates[first:]
    return Result(
        name=strategy,
        returns=pd.Series(port, index=idx),
        fx_contribution=pd.Series(fx_part, index=idx),
        weights=pd.DataFrame.from_dict(weight_rows, orient="index", columns=tickers),
        turnover=pd.Series(turnover),
    )


def metrics(returns, rf, fx_contribution=None, turnover=None, capital=100_000.0):
    rf = rf.reindex(returns.index).fillna(0.0)
    excess = returns - rf
    years = len(returns) / optimize.TRADING_DAYS
    wealth = (1 + returns).cumprod()
    dd = wealth / wealth.cummax() - 1
    vol = returns.std() * np.sqrt(optimize.TRADING_DAYS)
    downside = excess[excess < 0].std() * np.sqrt(optimize.TRADING_DAYS)
    cagr = wealth.iloc[-1] ** (1 / years) - 1
    out = {
        "CAGR": cagr,
        "Volatility": vol,
        "Sharpe": excess.mean() * optimize.TRADING_DAYS / vol if vol > 0 else np.nan,
        "Sortino": excess.mean() * optimize.TRADING_DAYS / downside if downside > 0 else np.nan,
        "Max drawdown": dd.min(),
        "Calmar": cagr / -dd.min() if dd.min() < 0 else np.nan,
        "Final value ($)": capital * wealth.iloc[-1],
    }
    if fx_contribution is not None:
        out["FX contribution (ann.)"] = fx_contribution.mean() * optimize.TRADING_DAYS
    if turnover is not None and len(turnover):
        out["Avg turnover / rebalance"] = turnover.iloc[1:].mean() if len(turnover) > 1 else np.nan
    return out
