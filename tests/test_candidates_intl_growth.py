"""Tests for research/candidates/intl_growth.py (international growth stocks, Phase 3)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import capm, config, grinold_kroner
from research.candidates import assumptions_intl_growth as A
from research.candidates import intl_growth as ig

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "research"
HAVE_DATA = (DATA / "prices.csv").exists() and (DATA / "fx.csv").exists()

TOP_KEYS = {"schema_version", "id", "ticker", "usd_ticker", "name", "position_type", "instrument", "country",
            "currency_code", "sector", "non_us", "benchmark", "data", "metrics", "rolling", "currency",
            "expected_return_7y", "stress", "screens", "rubric", "review", "explain", "memo", "charts",
            "reproduce"}
METRIC_KEYS = {"start", "end", "months", "cagr", "vol", "sharpe", "sortino", "max_drawdown", "calmar", "beta",
               "alpha", "tracking_error", "info_ratio", "up_capture", "down_capture", "t_stat_alpha",
               "t_stat_ir", "deflated_sharpe", "best_month", "worst_month", "pct_positive_months"}


def check_schema(res):
    """results_schema.md structure; raises AssertionError with the offending key."""
    assert TOP_KEYS <= set(res), TOP_KEYS - set(res)
    assert res["id"] == res["ticker"].replace(".", "_").replace("^", "_")
    assert res["position_type"] == "intl_growth_stock" and res["benchmark"] == "EFG_EEM_5050"
    assert res["non_us"] is True
    assert isinstance(res["currency_code"], str) and len(res["currency_code"]) == 3
    assert isinstance(res["currency"], dict)   # schema's FX block (the duplicate "currency" key, last wins)
    for k in ("price_start", "price_end", "months_total", "months_in_sample", "months_out_of_sample",
              "sources", "fund_fee", "notes"):
        assert k in res["data"], k
    for w in ("in_sample", "out_of_sample", "full"):
        for ccy in ("usd", "local"):
            assert METRIC_KEYS <= set(res["metrics"][w][ccy]), (w, ccy, METRIC_KEYS - set(res["metrics"][w][ccy]))
    r = res["rolling"]
    assert len(r["dates"]) == len(r["sharpe"]) == len(r["info_ratio"]) and "share_ir_positive_oos" in r
    for k in ("local_return", "fx_return", "usd_return", "hedged_return", "hedge_cost", "fx_vol_share"):
        assert k in res["currency"], k
    e = res["expected_return_7y"]
    for k in ("methods", "consensus_usd", "consensus_local", "range_5_95", "assumptions", "command"):
        assert k in e, k
    assert sum(v is not None for v in e["methods"].values()) >= 3
    assert len(e["range_5_95"]) == 2 and e["range_5_95"][0] <= e["consensus_usd"] <= e["range_5_95"][1] + 0.05
    for k in ("gfc_2008", "taper_2013", "covid_2020", "inflation_2022"):
        assert {"start", "end", "return", "benchmark"} <= set(res["stress"][k])
    assert {"definition", "avg_return", "benchmark"} <= set(res["stress"]["strong_usd"])
    assert {"fundamental_score", "technical_score", "hard_screens_passed", "detail"} <= set(res["screens"])
    assert res["review"] is None or isinstance(res["review"], dict)  # filled in Phase 4
    assert len(res["explain"]) == 3 and all(isinstance(s, str) and s for s in res["explain"])
    json.dumps(res, allow_nan=False)   # no NaN/inf anywhere


# ---------------------------------------------------------------- pure functions
def test_local_usd_fx_identity_on_constructed_data():
    rng = np.random.default_rng(1)
    idx = pd.date_range("2018-01-31", periods=60, freq="ME")
    loc = pd.Series(rng.normal(0.01, 0.06, 60), index=idx)
    fx = pd.Series(rng.normal(-0.002, 0.02, 60), index=idx)
    usd = (1 + loc) * (1 + fx) - 1
    rf = pd.Series(0.002, index=idx)
    c = ig.currency_block(loc, usd, fx, rf, rf, "EUR")
    assert abs((1 + c["local_return"]) * (1 + c["fx_return"]) - 1 - c["usd_return"]) < 1e-12
    assert abs(c["identity_check"]) < 1e-12
    assert 0 < c["fx_vol_share"] < 1
    # equal rates: hedge costs exactly the 5 bp roll
    assert c["hedge_cost"] == pytest.approx(12 * A.FX_FORWARD_COST_PER_ROLL)


def test_series_fx_defined_by_identity():
    class Fake(ig.Inputs):
        def __init__(self):
            idx = pd.date_range("2010-01-31", periods=5, freq="ME")
            self.m_local = pd.DataFrame({"X": [0.1, -0.05, 0.02, 0.0, 0.03]}, index=idx)
            self.m_usd = pd.DataFrame({"X": [0.12, -0.06, 0.02, 0.01, 0.01]}, index=idx)
    loc, usd, fx = Fake().series("X")
    assert np.allclose((1 + loc) * (1 + fx) - 1, usd)


def test_cip_hedge_cost_sign():
    idx = pd.date_range("2018-01-31", periods=36, freq="ME")
    us = pd.Series(0.02 / 12, index=idx)
    high = pd.Series(0.07 / 12, index=idx)     # e.g. INR: local rate above US
    low = pd.Series(0.00 / 12, index=idx)      # e.g. DKK/JPY: local rate below US
    fp_high = ig.forward_premium(us, high)
    fp_low = ig.forward_premium(us, low)
    assert (fp_high < 0).all() and (fp_low > 0).all()
    zero = pd.Series(0.0, index=idx)
    c_high = ig.currency_block(zero, zero, zero, us, high, "INR")
    c_low = ig.currency_block(zero, zero, zero, us, low, "DKK")
    assert c_high["hedge_cost"] > 0 and c_low["hedge_cost"] < 0
    assert c_high["hedge_cost"] == pytest.approx(0.05 + 0.006, abs=0.003)
    # hedged return with FX moving: the FX move is removed (up to the cross term l*f)
    fx = pd.Series(-0.01, index=idx)
    h, _ = ig.hedged_returns((1 + zero) * (1 + fx) - 1, fx, us, us, cost=0.0)
    assert np.allclose(h, 0.0)


def test_stress_windows_match_method():
    assert ig.STRESS == {"gfc_2008": ("2007-10-31", "2009-02-28"), "taper_2013": ("2013-04-30", "2013-08-31"),
                         "covid_2020": ("2020-01-31", "2020-03-31"),
                         "inflation_2022": ("2021-12-31", "2022-10-31")}
    assert ig.USD_EPISODES == {"usd_2014_15": ("2014-05-31", "2015-03-31"),
                               "usd_2021_22": ("2021-05-31", "2022-09-30")}
    idx = pd.date_range("2019-01-31", "2023-12-31", freq="ME")
    r = pd.Series(0.01, index=idx)
    assert ig.window_return(r, "2020-01-31", "2020-03-31") == pytest.approx(1.01 ** 2 - 1)   # Feb, Mar
    assert ig.window_return(r, "2021-12-31", "2022-10-31") == pytest.approx(1.01 ** 10 - 1)
    assert ig.window_return(r, "2007-10-31", "2009-02-28") is None                           # no data
    lvl = pd.Series([100, 103, 103.5, 101, 104], index=pd.date_range("2020-01-31", periods=5, freq="ME"))
    assert list(ig.strong_usd_months(lvl)) == [pd.Timestamp("2020-02-29"), pd.Timestamp("2020-05-31")]


def test_cid():
    assert ig.cid("2330.TW") == "2330_TW" and ig.cid("NOVO-B.CO") == "NOVO-B_CO" and ig.cid("^HSI") == "_HSI"


# ---------------------------------------------------------------- adapters (no network, synthetic data)
def test_assumptions_extend_config_without_overwriting():
    a, base = A.market_assumptions(), config.MarketAssumptions()
    for attr in ("country_risk_premium", "risk_free", "inflation", "long_run_real_gdp"):
        for k, v in getattr(base, attr).items():
            assert getattr(a, attr)[k] == v, (attr, k)
    for c in ("DK", "AU", "HK", "IN", "CA", "CN"):
        assert c in a.country_risk_premium and c in a.long_run_real_gdp
    for c in ("DKK", "AUD", "HKD", "INR", "CAD", "CNY"):
        assert c in a.risk_free and c in a.inflation
    assert a.mature_erp == base.mature_erp and a.horizon_years == 7
    assert set(A.TARGET_PE) == {ig.cid(t) for t in ig.CANDIDATES}


def test_adapter_builds_and_runs_models_without_network():
    rng = np.random.default_rng(3)
    days = pd.bdate_range("2015-01-01", "2020-12-31")
    n = len(days)
    prices = pd.DataFrame({"TEST.AX": 50 * np.cumprod(1 + rng.normal(4e-4, 0.015, n)),
                           "^AXJO": 6000 * np.cumprod(1 + rng.normal(2e-4, 0.01, n)),
                           "ACWI": 60 * np.cumprod(1 + rng.normal(3e-4, 0.01, n))}, index=days)
    fx = pd.DataFrame({"AUD": 0.7 * np.cumprod(1 + rng.normal(0, 0.005, n))}, index=days)
    row = {"ticker": "TEST.AX", "name": "Test Ltd", "currency": "AUD", "country": "AU", "usd_ticker": ""}
    stock = ig.make_stock(row, "^AXJO")
    assert stock.key == "TEST_AX" and stock.local_index == "^AXJO"
    fund = {"TEST.AX": {"info": {"marketCap": 1e10, "forwardPE": 20.0, "currentPrice": 50.0,
                                 "dividendRate": 1.0, "currency": "AUD", "financialCurrency": "AUD"}}}
    ds = ig.CandidateDataset(prices, fx, pd.DataFrame(), fund, [stock])
    local, usd = ds.stock_returns("TEST_AX")
    assert len(local) == len(usd) > 60
    a = A.market_assumptions()
    c = capm.estimate(stock, ds, a)
    assert np.isfinite(c["expected_local"]) and np.isfinite(c["expected_usd_global_capm"])
    g = grinold_kroner.run(stock, ds, a, s=config.GKSettings(target_pe={"TEST_AX": 18.0}))
    assert np.isfinite(g["expected_usd"]) and g["repricing"] < 0


# ---------------------------------------------------------------- integration on the data on disk
@pytest.fixture(scope="module")
def tsmc():
    if not HAVE_DATA:
        pytest.skip("data/research not present")
    inp = ig.Inputs()
    res, _ = ig.analyse(inp, "2330.TW")
    return inp, res


def test_analyse_tsmc_schema_and_identity(tsmc):
    inp, res = tsmc
    check_schema(res)
    c = res["currency"]
    assert abs((1 + c["local_return"]) * (1 + c["fx_return"]) - 1 - c["usd_return"]) < 5e-6   # JSON rounds to 6 decimals
    assert res["metrics"]["in_sample"]["usd"]["end"] == "2017-12-31"
    assert res["metrics"]["out_of_sample"]["usd"]["start"] == "2018-01-31"
    assert res["metrics"]["in_sample"]["usd"]["months"] == 96


def test_written_json_files_are_valid():
    files = [ROOT / "reports" / "candidates" / f"{ig.cid(t)}.json" for t in ig.CANDIDATES]
    present = [f for f in files if f.exists()]
    if not present:
        pytest.skip("run python -m research.candidates.intl_growth --all --write first")
    for f in present:
        check_schema(json.loads(f.read_text(encoding="utf-8")))
