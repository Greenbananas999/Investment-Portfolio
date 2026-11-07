"""Tests for research/candidates/overlays.py (constructed prices are test inputs, never results)."""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.candidates import assumptions_overlays as A
from research.candidates import overlays as O

ROOT = Path(__file__).resolve().parents[1]
HAS_DATA = (ROOT / "data" / "research" / "prices.csv").exists() and \
    (ROOT / "data" / "research" / "cboe" / "BXMD.csv").exists()


def test_put_call_parity():
    S, K, T, r = 100.0, np.array([80.0, 95.0, 100.0, 110.0]), 0.25, 0.03
    for sig in (0.1, 0.25, 0.6):
        c = O.bs_price(S, K, T, r, sig, "call")
        p = O.bs_price(S, K, T, r, sig, "put")
        np.testing.assert_allclose(c - p, S - K * np.exp(-r * T), atol=1e-10)
    # zero time: intrinsic value
    assert O.bs_price(105.0, 100.0, 0.0, 0.03, 0.2, "call") == pytest.approx(5.0)
    assert O.bs_price(95.0, 100.0, 0.0, 0.03, 0.2, "put") == pytest.approx(5.0)


def test_delta_strike_solves_target():
    p = O.Params(atm_level=-0.02, skew_call=0.2, skew_put=0.3)
    leg = O.Leg("call", -1, ("delta", 0.30), "monthly")
    S, tau, r = 100.0, 28 / 365, 0.02
    K = O.strike_for(leg, S, tau, r, 18.0, 19.0, p)
    sig = O.implied_vol(S, K, tau, r, 18.0, 19.0, p)
    assert K > S
    assert O.bs_delta(S, K, tau, r, sig, "call") == pytest.approx(0.30, abs=1e-4)


def _market(path, start="2021-01-04", end="2021-02-19", vix=20.0, r=0.0):
    days = pd.bdate_range(start, end)
    S = pd.Series(np.interp(np.arange(len(days)), [0, len(days) - 1], [path[0], path[1]]), index=days)
    return pd.DataFrame({"S": S, "spx": S * 10, "vix": vix, "vix3m": vix, "r": r}, index=days)


def test_covered_call_payoff_at_expiry():
    # Constructed prices: rolls on 2021-01-15 and 2021-02-19 (third Fridays). Price path is
    # linear from 90 to 120, so S on the first roll is known and S at expiry is 120.
    d = _market((90.0, 120.0))
    p = O.Params()
    leg = O.Leg("call", -1, ("atm",), "monthly")
    sim = O.simulate(d, [leg], 1.0, p, costs=False)
    t0, t1 = pd.Timestamp("2021-01-15"), pd.Timestamp("2021-02-19")
    S0, S1 = d.loc[t0, "S"], d.loc[t1, "S"]
    tau = (t1 - t0).days / 365
    sig = O.implied_vol(S0, S0, tau, 0.0, 20.0, 20.0, p)
    prem = O.bs_price(S0, S0, tau, 0.0, sig, "call")
    expected = (S0 + prem) / S0            # capped at the strike: shares worth S1, call pays S1 - K
    assert S1 > S0
    assert sim.loc["2021-02-28", "value"] == pytest.approx(expected, rel=1e-10)
    # underlying grew by S1/S0; the overlay gave up the upside above the strike
    assert sim.loc["2021-02-28", "under"] / sim.loc["2021-01-31", "under"] > 1
    # costs: half-spread 1% of premium + fee 0.65 h / (10 x SPX), charged at each roll
    simc = O.simulate(d, [leg], 1.0, p, costs=True)
    c0 = A.OPTION_HALF_SPREAD * prem / S0 + A.OPTION_FEE_PER_CONTRACT / (10 * d.loc[t0, "spx"])
    assert simc.loc["2021-01-31", "cum_cost"] == pytest.approx(c0, rel=1e-9)


def test_protective_put_floors_loss():
    d = _market((100.0, 70.0))
    leg = O.Leg("put", +1, ("pct", 0.95), "monthly")
    sim = O.simulate(d, [leg], 1.0, O.Params(), costs=False)
    t0 = pd.Timestamp("2021-01-15")
    S0 = d.loc[t0, "S"]
    tau = (pd.Timestamp("2021-02-19") - t0).days / 365
    prem = O.bs_price(S0, 0.95 * S0, tau, 0.0, O.implied_vol(S0, 0.95 * S0, tau, 0.0, 20, 20, O.Params()), "put")
    # shares S1/S0, put pays (0.95 S0 - S1)/S0, premium paid prem/S0: floored at 0.95 - premium
    assert sim.loc["2021-02-28", "value"] == pytest.approx(0.95 - prem / S0, rel=1e-9)


def test_cip_forward_sign_and_arithmetic():
    f = O.cip_forward_factor(0.04, 0.10, 3)
    assert f == pytest.approx((1.04 / 1.10) ** 0.25)
    assert f < 1                                   # high-yield currency trades at a forward discount
    # spot unchanged: the hedge loses the carry
    assert O.hedge_return(0.04, 0.10, 1.0, 1.0) == pytest.approx(f - 1) and f - 1 < 0
    # spot falls 10%: the short forward gains
    assert O.hedge_return(0.04, 0.10, 1.0, 0.9) == pytest.approx(f - 0.9) and f - 0.9 > 0
    assert O.cip_forward_factor(0.05, 0.02, 3) > 1


def test_fx_hedge_engine_one_quarter():
    months = pd.date_range("2020-01-31", "2020-06-30", freq="ME")
    spot = pd.DataFrame({"MXN": [1.0, 1.0, 1.0, 0.9, 0.9, 0.9]}, index=months)
    rates = pd.DataFrame({"USD": 0.02, "MXN": 0.08}, index=months)
    unhedged = pd.Series(0.0, index=months[3:])     # April-June: fund flat in USD
    w = pd.Series({"MXN": 1.0})
    out = O.fx_hedge(unhedged, spot, rates, w, 1.0, cost_bps=5.0)
    total = (1 + out["overlaid_return"]).prod() - 1
    f = O.cip_forward_factor(0.02, 0.08, 3)
    assert total == pytest.approx(f - 0.9 - 5e-4 - 5e-4 * (1 + f - 0.9 - 5e-4), rel=1e-9)
    assert out["carry"].iloc[0] == pytest.approx(f ** 4 - 1)
    half = O.fx_hedge(unhedged, spot, rates, w, 0.5, cost_bps=0.0)
    assert (1 + half["overlaid_return"]).prod() - 1 == pytest.approx(0.5 * (f - 0.9))


def test_contract_sizing():
    s = O.contract_sizing(7623.68, sleeve=55_000)
    assert s["notional_per_contract"] == pytest.approx(76_236.8)
    assert s["contracts"] == 1 and s["max_fully_covered_contracts"] == 0
    assert s["hedge_ratio"] == pytest.approx(76_236.8 / 55_000)
    assert O.contract_sizing(5000.0, sleeve=110_000)["max_fully_covered_contracts"] == 2


def test_calibration_slice_bounds():
    idx = pd.date_range("2009-01-31", "2020-12-31", freq="ME")
    s = O.calibration_slice(pd.Series(1.0, index=idx))
    assert s.index.min() >= pd.Timestamp(A.CALIBRATION_START)
    assert s.index.max() <= pd.Timestamp(A.CALIBRATION_END)


@pytest.mark.skipif(not HAS_DATA, reason="data/research not present")
def test_calibration_ignores_data_after_2017():
    mkt = O.load_market()
    p1 = O.calibrate(mkt["daily"], mkt["cboe"])
    d2 = mkt["daily"].copy()
    late = d2.index > A.CALIBRATION_END
    d2.loc[late, "vix"] *= 3.0
    d2.loc[late, "S"] *= 0.5
    cboe2 = {k: v.where(v.index <= A.CALIBRATION_END, v * 7.0) for k, v in mkt["cboe"].items()}
    p2 = O.calibrate(d2, cboe2)
    assert p1.__dict__ == pytest.approx(p2.__dict__)


@pytest.mark.parametrize("oid", O.ALL_OVERLAYS)
def test_json_valid(oid):
    path = ROOT / "reports" / "candidates" / f"{oid}.json"
    if not path.exists():
        pytest.skip("run python -m research.candidates.overlays --all --write first")
    js = json.loads(path.read_text(encoding="utf-8"),
                    parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    assert js["position_type"] == "overlay" and js["id"] == oid
    for k in ("in_sample", "out_of_sample", "full"):
        assert js["metrics"][k]["usd"]["months"] > 0
    ov = js["overlay"]
    for k in ("underlying", "strategy", "parameters", "assumptions", "calibration", "with", "without",
              "drawdown_reduction", "annual_cost", "feasibility", "verdict_rule"):
        assert k in ov
    assert isinstance(ov["verdict_rule"]["passes_standalone"], bool)
    assert len(js["explain"]) == 3
    csv = ROOT / ov["monthly_series"]
    df = pd.read_csv(csv)
    assert list(df.columns[:6]) == ["date", "underlying_return", "overlay_return", "overlaid_return", "cost",
                                    "hedge_ratio"]
    np.testing.assert_allclose(df["overlaid_return"] - df["underlying_return"], df["overlay_return"], atol=1e-7)
    assert math.isclose(df["hedge_ratio"].iloc[0], df["hedge_ratio"].iloc[-1])
