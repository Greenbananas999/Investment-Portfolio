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


# --------------------------------------------------------------------------
# Generic walk-forward engine (Phase 5). Added 2026-11-07; `run` above is unchanged.
# --------------------------------------------------------------------------

@dataclass
class WalkResult:
    returns: pd.Series           # daily portfolio return, net of trading costs
    costs: pd.Series             # daily trading cost (fraction of portfolio value)
    holdings: pd.DataFrame       # start-of-day weights after any trade (drift between rebalances)
    weights: pd.DataFrame        # target weights at each rebalance
    turnover: pd.Series          # one-way turnover at each rebalance (0.5 x sum |dw|)
    triggered: list              # rebalance dates forced by the drift trigger, not the schedule


def rebalance_schedule(dates, start, freq):
    """Boolean mask: first trading day of each new period on or after `start`.

    freq: "monthly", "quarterly", "semiannual", "annual" (calendar periods)."""
    dates = pd.DatetimeIndex(dates)
    months = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}[freq]
    key = dates.year * 12 + (dates.month - 1) // months
    first = np.r_[True, key[1:] != key[:-1]]
    return first & (dates >= pd.Timestamp(start))


def walk_forward(asset_ret, weight_fn, schedule, cost_one_way, drift_trigger=None, first=None):
    """Daily walk-forward with drifting weights between rebalances.

    asset_ret      daily simple returns (DataFrame, NaN treated as 0 for held assets)
    weight_fn(i)   target weights for day i using data up to day i-1 only
                   (the caller slices asset_ret.iloc[:i]); trades at day i's open
    schedule       boolean mask over asset_ret.index: scheduled rebalance days
    cost_one_way   per-asset one-way cost (decimal) charged on |dw|
    drift_trigger  f(weights) -> True forces a rebalance the next day
    first          first day index (default: first scheduled day)
    """
    dates = asset_ret.index
    sched = np.asarray(schedule, bool)
    if first is None:
        first = int(np.flatnonzero(sched)[0])
    cost = np.asarray(cost_one_way, float)
    R = asset_ret.fillna(0.0).to_numpy()
    n = R.shape[1]
    w = np.zeros(n)
    port, costs, hold = [], [], []
    targets, turn, trig = {}, {}, []
    force = False
    for i in range(first, len(dates)):
        c = 0.0
        if sched[i] or force or i == first:
            new_w = np.asarray(weight_fn(i), float)
            dw = np.abs(new_w - w)
            c = float(cost @ dw)
            if force and not sched[i]:
                trig.append(dates[i])
            targets[dates[i]] = new_w
            turn[dates[i]] = float(dw.sum() / 2)
            w = new_w
            force = False
        hold.append(w.copy())
        r = R[i]
        rp = float(w @ r)
        port.append(rp - c)
        costs.append(c)
        w = w * (1 + r) / (1 + rp) if 1 + rp != 0 else w
        if drift_trigger is not None and drift_trigger(w):
            force = True
    idx = dates[first:]
    cols = list(asset_ret.columns)
    return WalkResult(pd.Series(port, index=idx), pd.Series(costs, index=idx),
                      pd.DataFrame(hold, index=idx, columns=cols),
                      pd.DataFrame.from_dict(targets, orient="index", columns=cols),
                      pd.Series(turn), trig)


def to_monthly(daily):
    """Compound daily returns into calendar-month ('ME') returns."""
    return (1 + daily).resample("ME").prod() - 1
