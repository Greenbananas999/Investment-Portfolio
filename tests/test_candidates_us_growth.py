"""Tests for research/candidates/us_growth.py (constructed data; one integration test on the disk data)."""

import json
import math
import socket
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import capm, config
from research.candidates import us_growth as ug

DATA = Path(__file__).resolve().parent.parent / "data" / "research"
HAVE_DATA = (DATA / "prices.csv").exists() and (DATA / "yields.csv").exists()


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network access attempted")
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket.socket, "connect", boom)


def _monthly(values, start="2009-01-31"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="ME"), dtype=float)


# ---------------------------------------------------------------- metrics on a constructed series
def test_metrics_on_constructed_series():
    n = len(pd.date_range("2009-01-31", "2026-10-31", freq="ME"))
    rng = np.random.default_rng(1)
    bench = _monthly(rng.normal(0.008, 0.04, n))
    r = 0.002 + 1.5 * bench                  # beta 1.5, alpha 0.2%/month, no noise
    rf = _monthly(np.full(n, 0.001))
    m = ug.metrics_blocks(r, bench, rf)
    assert set(m) == {"in_sample", "out_of_sample", "full"}
    is_, oos = m["in_sample"]["usd"], m["out_of_sample"]["usd"]
    assert m["in_sample"]["local"] == is_                       # USD stock: local = USD
    assert (is_["start"], is_["end"], is_["months"]) == ("2010-01-31", "2017-12-31", 96)
    assert oos["start"] == "2018-01-31" and oos["months"] == n - 108
    assert is_["beta"] == pytest.approx(1.5, abs=1e-9)
    # alpha on excess returns: r - rf = 0.002 + 1.5 b - rf = a + 1.5 (b - rf) -> a = 0.002 + 0.5 rf
    assert is_["alpha"] == pytest.approx((0.002 + 0.5 * 0.001) * 12, rel=1e-6)
    x = r.loc["2010":"2017"]
    assert is_["cagr"] == pytest.approx((1 + x).prod() ** (12 / 96) - 1)
    assert is_["best_month"] == pytest.approx(x.max()) and is_["worst_month"] == pytest.approx(x.min())
    assert 0 <= is_["deflated_sharpe"] <= 1 and is_["max_drawdown"] <= 0
    assert 0 < is_["pct_positive_months"] < 1


def test_window_return_counts_months_and_needs_full_coverage():
    r = _monthly(np.full(240, 0.01), start="2005-01-31")
    s, e = ug.STRESS_WINDOWS["gfc_2008"]
    assert ug.window_return(r, s, e) == pytest.approx(1.01 ** 16 - 1)       # Nov 2007 .. Feb 2009
    assert ug.window_return(r, *ug.STRESS_WINDOWS["covid_2020"]) == pytest.approx(1.01 ** 2 - 1)
    late = r.loc["2008-06-30":]                                              # listed mid-window
    assert ug.window_return(late, s, e) is None


def test_stress_window_dates_match_method():
    assert ug.STRESS_WINDOWS == {
        "gfc_2008": ("2007-10-31", "2009-02-28"), "taper_2013": ("2013-04-30", "2013-08-31"),
        "covid_2020": ("2020-01-31", "2020-03-31"), "inflation_2022": ("2021-12-31", "2022-10-31")}
    assert ug.USD_EPISODES == {"usd_2014_15": ("2014-06-30", "2015-03-31"),
                               "usd_2021_22": ("2021-06-30", "2022-09-30")}
    y = pd.DataFrame({"USD_BROAD": [100, 102.5, 102.0, 104.1, 104.0]},
                     index=pd.date_range("2014-07-01", periods=5, freq="MS"))
    up = ug.usd_up_months(y)
    assert [str(d.date()) for d in up] == ["2014-08-31", "2014-10-31"]      # +2.5%, +2.06%


# ---------------------------------------------------------------- adapters, no network
def test_adapter_builds_stock_and_dataset_offline(no_network):
    row = pd.Series({"ticker": "ZZZ", "name": "Test Co", "usd_ticker": "ZZZ", "local_index": "^NDX"})
    st = ug.make_stock(row)
    assert isinstance(st, config.Stock)
    assert (st.key, st.ticker, st.currency, st.country, st.local_index) == ("ZZZ", "ZZZ", "USD", "US", "^GSPC")
    days = pd.bdate_range("2015-01-01", "2020-12-31")
    rng = np.random.default_rng(0)
    m = rng.normal(0.0004, 0.01, len(days))
    prices = pd.DataFrame({"ZZZ": 100 * np.cumprod(1 + 1.2 * m + rng.normal(0, 0.005, len(days))),
                           "^GSPC": 100 * np.cumprod(1 + m), "ACWI": 100 * np.cumprod(1 + 0.9 * m)}, index=days)
    ds = ug.make_dataset(st, prices, fundamentals={"ZZZ": {"info": {}}}, end="2020-12-31")
    assert isinstance(ds, ug.CandidateDataset) and not ds.synthetic
    local, usd = ds.stock_returns("ZZZ")
    pd.testing.assert_series_equal(local, usd, check_names=False)
    c = capm.estimate(st, ds, config.MarketAssumptions())     # research.capm unchanged, via the adapter
    assert 0.8 < c["beta_local_raw"] < 1.6 and c["expected_usd"] == pytest.approx(c["expected_local"])


def test_model_settings_use_assumptions_file():
    dcfs, gks, mcs = ug.model_settings("GILD")
    assert dcfs.max_start_growth == pytest.approx(0.0698) and gks.analyst_growth_cap == pytest.approx(0.0698)
    assert gks.target_pe == {"GILD": 18.9} and mcs.horizon_years == 7
    dcfs, gks, _ = ug.model_settings("NVDA")
    assert dcfs.max_start_growth == config.DCFSettings().max_start_growth
    assert gks.target_pe["NVDA"] == config.GKSettings().target_pe["NVDA"]


def test_clean_turns_nan_into_null():
    out = ug.clean({"a": float("nan"), "b": np.float64(0.1234567891), "c": [np.inf, 1], "d": np.bool_(True)})
    assert out == {"a": None, "b": 0.123457, "c": [None, 1], "d": True}


# ---------------------------------------------------------------- schema of a produced JSON
REQUIRED = ["schema_version", "id", "ticker", "usd_ticker", "name", "position_type", "instrument", "country",
            "currency", "sector", "non_us", "benchmark", "data", "metrics", "rolling", "currency",
            "expected_return_7y", "stress", "screens", "rubric", "review", "explain", "memo", "charts", "reproduce"]
METRIC_KEYS = ["start", "end", "months", "cagr", "vol", "sharpe", "sortino", "max_drawdown", "calmar", "beta",
               "alpha", "tracking_error", "info_ratio", "up_capture", "down_capture", "t_stat_alpha",
               "t_stat_ir", "deflated_sharpe", "best_month", "worst_month", "pct_positive_months"]


def _walk_numbers(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk_numbers(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk_numbers(v, f"{path}[{i}]")
    elif isinstance(o, float):
        yield path, o


@pytest.mark.skipif(not HAVE_DATA, reason="data/research not on disk")
def test_produced_json_matches_schema(tmp_path, no_network):
    inp = ug.load_inputs(["META"])
    res = ug.write_candidate("META", inp, ug.analyse("META", inp, mc_paths=500), out_dir=tmp_path,
                             memo_dir=tmp_path, with_charts=False)
    j = json.loads((tmp_path / "META.json").read_text(encoding="utf-8"))
    assert j == res
    assert all(k in j for k in REQUIRED), [k for k in REQUIRED if k not in j]
    assert j["position_type"] == "us_growth_stock" and j["non_us"] is False and j["benchmark"] == "IVW"
    for w in ("in_sample", "out_of_sample", "full"):
        for c in ("usd", "local"):
            blk = j["metrics"][w][c]
            assert all(k in blk for k in METRIC_KEYS), (w, c)
        assert j["metrics"][w]["usd"] == j["metrics"][w]["local"]
    oos = j["metrics"]["out_of_sample"]["usd"]
    assert oos["start"] == "2018-01-31" and j["metrics"]["in_sample"]["usd"]["end"] == "2017-12-31"
    # decimals, not percents
    assert -1 < oos["max_drawdown"] <= 0 and 0 < oos["vol"] < 2 and -1 < oos["cagr"] < 3
    assert 0 <= oos["pct_positive_months"] <= 1 and 0 <= oos["deflated_sharpe"] <= 1
    e = j["expected_return_7y"]
    present = [k for k in ("capm", "dcf", "grinold_kroner", "monte_carlo_median") if e["methods"][k] is not None]
    assert len(present) >= 3 and all(-0.5 < e["methods"][k] < 0.6 for k in present)
    assert e["range_5_95"][0] < e["consensus_usd"] < e["range_5_95"][1]
    assert "assumptions_us_growth.py" in e["assumptions"] and e["command"].startswith("python -m")
    # nulls, not zeros, for missing values; no NaN anywhere
    assert j["stress"]["gfc_2008"]["return"] is None            # META listed 2012
    assert j["stress"]["gfc_2008"]["benchmark"] is not None
    assert j["currency"]["hedged_return"] is None and j["currency"]["fx_return"] == 0.0
    assert j["review"]["verdict"] is None and j["rubric"]["total"] is None
    assert all(math.isfinite(v) for _, v in _walk_numbers(j))
    assert len(j["rolling"]["dates"]) == len(j["rolling"]["sharpe"]) == len(j["rolling"]["info_ratio"])
    assert 0 <= j["rolling"]["share_ir_positive_oos"] <= 1
    assert len(j["explain"]) == 3 and all(isinstance(s, str) and s.endswith(".") for s in j["explain"])
    assert set(j["stress"]) == {"gfc_2008", "taper_2013", "covid_2020", "inflation_2022", "strong_usd"}
    assert j["stress"]["strong_usd"]["months"] > 0
    assert (tmp_path / "META.md").read_text(encoding="utf-8").startswith("# META")
