"""Tests for research/candidates/other_sleeve.py (constructed data except the one JSON build)."""

import json

import numpy as np
import pandas as pd
import pytest

from research.candidates import other_sleeve as O
from research.screen import inflation_beta


@pytest.fixture(scope="module")
def built():
    return O.run(O.IDS, write=False, full=False)


def test_json_valid_and_complete(built):
    ctx, results = built
    assert set(results) == set(O.IDS)
    for tk, res in results.items():
        s = json.dumps(res, allow_nan=False)           # no NaN / inf anywhere
        res = json.loads(s)
        assert res["id"] == tk and res["position_type"] == "other" and res["benchmark"] == "GLD"
        for w in ("in_sample", "out_of_sample", "full"):
            assert set(res["metrics"][w]) == {"usd", "local"}
            assert res["metrics"][w]["usd"] == res["metrics"][w]["local"]
        assert res["deflated_sharpe"]["n_trials"] == 33
        assert len(res["rolling"]["dates"]) == len(res["rolling"]["sharpe"]) == len(res["rolling"]["info_ratio"])
        e = res["expected_return_7y"]
        assert len([k for k in e["consensus_methods"]]) >= 2 and "monte_carlo_median" in e["methods"]
        assert e["range_5_95"][0] < e["range_5_95"][1]
        assert set(res["stress"]) >= {"gfc_2008", "taper_2013", "covid_2020", "inflation_2022", "strong_usd"}
        assert len(res["explain"]) == 3 and res["review"]["verdict"] is None
        assert res["data"]["months_in_sample"] >= 60
    iau = results["IAU"]["metrics"]["out_of_sample"]["usd"]
    assert iau["info_ratio"] is None                    # IAU vs GLD undefined
    assert results["IAU"]["alt_benchmarks"]["GUIDE_BENCH"]["out_of_sample"]["info_ratio"] is not None


def _cpi_and_returns(sign, n=120, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2010-01-01", periods=n + 12, freq="MS")
    yoy = 0.02 + np.cumsum(rng.normal(0, 0.002, n + 12))
    level = pd.Series(100.0, index=idx)
    base = 100 * np.cumprod(1 + np.full(n + 12, 0.002))
    # build a level whose YoY inflation equals `yoy` from month 12 on
    lv = list(base[:12])
    for t in range(12, n + 12):
        lv.append(lv[t - 12] * (1 + yoy[t]))
    level = pd.Series(lv, index=idx)
    c = level.copy(); c.index = c.index + pd.offsets.MonthEnd(0)
    dpi = (c / c.shift(12) - 1).diff()
    r = sign * 2.0 * dpi + rng.normal(0, 0.001, len(dpi))
    return level, r.dropna()


def test_inflation_beta_sign_on_constructed_data():
    level, r = _cpi_and_returns(+1)
    b, n = inflation_beta(r, level)
    assert b > 1.5 and n >= 60
    level, r = _cpi_and_returns(-1)
    assert inflation_beta(r, level)[0] < -1.5


def test_gold_real_yield_formula_arithmetic():
    # real = -2.6% + 0.9% = -1.7%; nominal = 0.983 * 1.0223 - 1
    assert O.gold_real_yield_model(0.026, 0.0223, 0.009) == pytest.approx(0.983 * 1.0223 - 1)
    assert O.gold_real_yield_model(0.0, 0.025, 0.0) == pytest.approx(0.025)      # zero real return = inflation
    assert O.gold_real_yield_model(0.02, 0.02, 0.02) == pytest.approx(0.02)      # drift equal to yield cancels


def test_stress_window_dates_and_returns():
    assert O.STRESS_WINDOWS == {"gfc_2008": ("2007-10-31", "2009-02-28"), "taper_2013": ("2013-04-30", "2013-08-31"),
                                "covid_2020": ("2020-01-31", "2020-03-31"), "inflation_2022": ("2021-12-31", "2022-10-31")}
    assert O.STRONG_USD_EPISODES["usd_2014_06_to_2015_03"] == ("2014-05-31", "2015-03-31")
    assert O.STRONG_USD_EPISODES["usd_2021_06_to_2022_09"] == ("2021-05-31", "2022-09-30")
    idx = pd.date_range("2021-01-31", "2022-12-31", freq="ME")
    r = pd.Series(0.01, index=idx)
    assert O.window_return(r, *O.STRESS_WINDOWS["inflation_2022"]) == pytest.approx(1.01 ** 10 - 1)   # 10 months
    assert O.window_return(r, "2007-10-31", "2009-02-28") is None                                       # not covered
    usd = pd.Series([100, 101, 104, 104.5, 107], index=pd.date_range("2020-01-31", periods=5, freq="ME"))
    assert list(O.strong_usd_months(usd)) == [pd.Timestamp("2020-03-31"), pd.Timestamp("2020-05-31")]


def test_guide_bench_constant_returns():
    idx = pd.date_range("2020-01-31", periods=8, freq="ME")
    m = pd.DataFrame({"ACWX": 0.01, "EMB": 0.01, "GLD": 0.01}, index=idx)
    assert O.guide_bench(m).round(10).eq(0.01).all()
