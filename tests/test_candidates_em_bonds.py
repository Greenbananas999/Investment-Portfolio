"""Tests for research/candidates/em_bonds.py (constructed data; the JSON checks read the
written reports and skip when `python -m research.candidates.em_bonds --all --write` has not run)."""

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.candidates import assumptions_em_bonds as A
from research.candidates import em_bonds as E

ROOT = Path(__file__).resolve().parents[1]


# ---- credit loss ----------------------------------------------------------
def test_annual_pd_interpolates_7y_and_annualises():
    c5, c10 = A.CUM_DEFAULT_5Y_10Y["BBB"]
    c7 = (c5 + (c10 - c5) * 2 / 5) / 100
    assert E.annual_pd("BBB") == pytest.approx(1 - (1 - c7) ** (1 / 7))
    # ordering: worse ratings default more
    pds = [E.annual_pd(b) for b in ("A", "BBB", "BB", "B", "CCC")]
    assert pds == sorted(pds)


def test_credit_loss_arithmetic():
    assert E.credit_loss({"BB": 1.0}, 0.40) == pytest.approx(E.annual_pd("BB") * 0.60)
    mix = {"BBB": 0.5, "B": 0.5}
    want = (0.5 * E.annual_pd("BBB") + 0.5 * E.annual_pd("B")) * (1 - 0.49)
    assert E.credit_loss(mix, 0.49) == pytest.approx(want)
    # weights are renormalised (EMB's published buckets sum to 99.1%)
    assert E.credit_loss({"BBB": 0.25, "B": 0.25}, 0.49) == pytest.approx(want)
    assert E.credit_loss({"A": 1.0}, 1.0) == 0.0


def test_rating_bucket():
    assert E.rating_bucket("BBB-") == "BBB"
    assert E.rating_bucket("A+") == "A"
    assert E.rating_bucket("AA-") == "AA"
    assert E.rating_bucket("CC") == "CCC"


# ---- CIP hedge ------------------------------------------------------------
def test_cip_hedge_sign_and_size():
    # local rate above US rate: selling the currency forward costs carry
    h = E.cip_hedge_return(0.04, 0.10)
    assert h < 0
    assert h == pytest.approx((0.04 - 0.10) / 12, rel=0.05)
    # local rate below US rate: the hedge earns
    assert E.cip_hedge_return(0.05, 0.01) > 0
    assert E.cip_hedge_return(0.03, 0.03) == pytest.approx(0.0)
    # three monthly factors compound to the 3-month forward points
    f = (1 + E.cip_hedge_return(0.04, 0.10)) ** 3
    assert f == pytest.approx((1 + 0.04 / 4) / (1 + 0.10 / 4))


# ---- basket FX decomposition ----------------------------------------------
def test_basket_decomposition_identity():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2018-01-31", periods=48, freq="ME")
    fx = pd.DataFrame(rng.normal(-0.002, 0.03, (48, 3)), index=idx, columns=["AAA", "BBB", "CCC"])
    w = {"AAA": 0.5, "BBB": 0.3, "CCC": 0.2}
    fxb = E.basket_return(fx, w)
    assert fxb.iloc[0] == pytest.approx(sum(fx.iloc[0][c] * x for c, x in w.items()))
    usd = pd.Series(rng.normal(0.003, 0.03, 48), index=idx)
    loc = E.local_from_usd(usd, fxb)
    np.testing.assert_allclose((1 + loc) * (1 + fxb) - 1, usd, atol=1e-12)
    # compounding: local CAGR x FX CAGR = USD CAGR exactly
    g = lambda r: (1 + r).prod()
    assert g(loc) * g(fxb) == pytest.approx(g(usd))


def test_basket_renormalises_missing_currency():
    idx = pd.date_range("2020-01-31", periods=2, freq="ME")
    fx = pd.DataFrame({"X": [0.01, 0.01], "Y": [np.nan, 0.03]}, index=idx)
    b = E.basket_return(fx, {"X": 0.5, "Y": 0.5})
    assert b.iloc[0] == pytest.approx(0.01)
    assert b.iloc[1] == pytest.approx(0.02)


# ---- GUIDE_BENCH quarterly rebalance ----------------------------------------
def test_guide_bench_quarterly_drift():
    idx = pd.date_range("2019-01-31", periods=6, freq="ME")
    M = pd.DataFrame({"ACWX": [0.10, 0.0, 0.0, 0.10, 0.0, 0.0],
                      "EMB": [0.0] * 6, "GLD": [0.0] * 6}, index=idx)
    g = E.guide_bench(M)
    assert g.iloc[0] == pytest.approx(0.055)
    # February: weights have drifted, ACWX return 0, so portfolio 0
    assert g.iloc[1] == pytest.approx(0.0)
    # April starts a new quarter: back to 55%
    assert g.iloc[3] == pytest.approx(0.055)


# ---- scenario engine --------------------------------------------------------
def test_scenario_unchanged_yield_earns_about_the_yield():
    r = E.scenario_return(0.06, 0.06, 6.0)
    assert r == pytest.approx(0.06, abs=0.003)
    assert E.scenario_return(0.06, 0.08, 6.0) < r < E.scenario_return(0.06, 0.04, 6.0)
    m = E.maturity_for_duration(6.0, 0.06)
    from research import bonds
    assert bonds.duration_convexity(0.06, m, 2)[0] == pytest.approx(6.0, abs=1e-3)


# ---- stress windows ---------------------------------------------------------
def test_stress_windows_match_method():
    text = (ROOT / "research" / "plan" / "method.md").read_text(encoding="utf-8")
    sec = text.split("## 11.")[1].split("## 12.")[0]
    found = re.findall(r"(\d{4}-\d{2}-\d{2}) to (\d{4}-\d{2}-\d{2})", sec)
    assert [tuple(v) for v in A.STRESS.values()] == found
    assert A.STRESS["taper_2013"] == ("2013-04-30", "2013-08-31")


def test_window_return_month_end_to_month_end():
    idx = pd.date_range("2013-01-31", periods=12, freq="ME")
    r = pd.Series(0.01, index=idx)
    # (2013-04-30, 2013-08-31] = May..Aug, four months
    assert E.window_return(r, "2013-04-30", "2013-08-31") == pytest.approx(1.01 ** 4 - 1)
    # series starting after the window start is not covered
    assert E.window_return(r.loc["2013-06-30":], "2013-04-30", "2013-08-31") is None


# ---- written JSON -----------------------------------------------------------
REQUIRED = ["schema_version", "id", "ticker", "name", "position_type", "instrument", "non_us", "benchmark",
            "data", "metrics", "rolling", "currency", "expected_return_7y", "stress", "screens", "rubric",
            "review", "explain", "memo", "charts", "reproduce"]


def _no_nan(s):
    def bad(c):
        raise ValueError(f"non-JSON constant {c}")
    return json.loads(s, parse_constant=bad)


@pytest.mark.parametrize("t", A.CANDIDATES)
def test_written_json_valid(t):
    p = ROOT / "reports" / "candidates" / f"{t}.json"
    if not p.exists():
        pytest.skip("run python -m research.candidates.em_bonds --all --write first")
    d = _no_nan(p.read_text(encoding="utf-8"))
    for k in REQUIRED:
        assert k in d, k
    assert d["id"] == t and d["position_type"] == "em_bond" and d["non_us"] is True
    assert (d["review"] is None or isinstance(d["review"], dict)) and len(d["explain"]) == 3  # review block is filled in Phase 4
    for w in ("in_sample", "out_of_sample", "full"):
        for c in ("usd", "local"):
            m = d["metrics"][w][c]
            assert m["months"] >= 60 or w == "in_sample"
            assert "deflated_sharpe" in m and "sharpe" in m
    o = d["metrics"]["out_of_sample"]["usd"]
    assert o["start"] == "2018-01-31" and d["metrics"]["in_sample"]["usd"]["end"] == "2017-12-31"
    e = d["expected_return_7y"]
    assert sum(v is not None for v in e["methods"].values()) >= 2
    assert e["range_5_95"][0] < e["consensus_usd"] < e["range_5_95"][1]
    for k, (s, en) in A.STRESS.items():
        assert d["stress"][k]["start"] == s and d["stress"][k]["end"] == en
    c = d["currency"]
    assert (1 + c["local_return"]) * (1 + c["fx_return"]) == pytest.approx(1 + c["usd_return"], abs=1e-9)
    assert (ROOT / d["memo"]).exists() and (ROOT / d["charts"]["growth"]).exists()
    if t in A.LOCAL_FUNDS:
        assert c["hedge_cost"] > 0      # EM short rates above US rates on average since 2018
        assert "country_crosscheck" in e
