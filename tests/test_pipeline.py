import numpy as np
import pandas as pd

from portfolio import backtest, config, data, optimize
from run import synthetic_data


def _inputs():
    prices, fx = synthetic_data(seed=1, years=5)
    rets = data.daily_returns(prices)
    return rets[config.TICKERS], rets[config.RISK_FREE].fillna(0.0), data.fx_exposure_returns(fx, rets.index)


def test_weights_respect_rules():
    asset_ret, rf, fx_exp = _inputs()
    rules = config.Rules()
    settings = config.BacktestSettings(start="2000-01-01", lookback_days=504)
    non_us = np.array([config.ASSETS[t].non_us for t in config.TICKERS])
    for s in ("max_sharpe", "min_variance"):
        w = backtest.run(s, asset_ret, rf, fx_exp, rules, settings).weights.to_numpy()
        assert np.allclose(w.sum(axis=1), 1.0, atol=1e-6)
        assert (w >= -1e-9).all()
        assert (w <= rules.max_weight + 1e-6).all()
        assert (w[:, non_us].sum(axis=1) >= rules.min_non_us - 1e-6).all()


def test_unlisted_asset_gets_zero_weight():
    asset_ret, rf, _ = _inputs()
    window = asset_ret.iloc[:300]  # INDA has no prices yet in this window
    w = backtest.target_weights("min_variance", window, rf.iloc[:300], config.Rules())
    assert w[config.TICKERS.index("INDA")] == 0.0


def test_min_variance_beats_equal_weight_in_sample():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 0.01, (1000, 6)) * np.array([1, 2, 3, 1, 2, 3])
    _, cov = optimize.estimate(x)
    ok = np.ones(6, bool)
    w = optimize.min_variance(cov, ok, ok, 0.5, 0.0)
    eq = np.full(6, 1 / 6)
    assert w @ cov @ w < eq @ cov @ eq


def test_metrics_drawdown():
    r = pd.Series([0.1, -0.5, 0.2], index=pd.bdate_range("2024-01-01", periods=3))
    m = backtest.metrics(r, pd.Series(0.0, index=r.index))
    assert np.isclose(m["Max drawdown"], -0.5)
