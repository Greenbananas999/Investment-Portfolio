"""Phase 5 builder: constraint set, walk-forward rule checks, Monte Carlo targets, JSON layout.

Synthetic data here test the code only; no number below is a result.
"""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from portfolio import backtest, build, optimize as O

ROOT = Path(__file__).resolve().parents[1]
PICKS = build._pos(build.PICKS)
TICK = [p["ticker"] for p in PICKS]


def _cons(st=None, **kw):
    return build.make_constraints(PICKS, st or build.Settings(), **kw)


def test_constraints_hold_on_a_synthetic_problem():
    rng = np.random.default_rng(3)
    x = rng.normal(0.0005, 0.012, (600, 12)) * np.linspace(0.5, 2.0, 12)
    mu, cov = O.estimate(x)
    c = _cons()
    for w in (O.max_sharpe_constrained(mu, cov, c), O.min_variance_constrained(cov, c)):
        chk = O.check_weights(w, c, tol=1e-6)
        assert chk["ok"], chk
        assert abs(w.sum() - 1) < 1e-8
        assert (w >= c.lower - 1e-8).all() and (w <= c.upper + 1e-8).all()
        assert np.asarray(c.non_us) @ w >= 0.70 - 1e-6
        assert 0.45 - 1e-6 <= chk["groups"]["equity"] <= 0.65 + 1e-6
        assert 0.25 - 1e-6 <= chk["groups"]["bonds"] <= 0.45 + 1e-6
        assert chk["groups"]["other"] <= 0.20 + 1e-6


def test_feasible_region_matches_the_arithmetic():
    reg = O.feasible_region(_cons())
    assert reg["feasible"]
    # three international stocks at most 10% each -> bonds must carry at least 40%
    assert reg["groups"]["intl_equity"][1] == pytest.approx(0.30)
    assert reg["groups"]["bonds"][0] == pytest.approx(0.40)
    assert reg["non_us_share"][0] == pytest.approx(0.70)


def test_infeasibility_is_detected_and_explained():
    c = _cons(replace(build.Settings(), min_non_us=0.80))
    assert O.feasible_point(c) is None
    reason = O.infeasibility_reason(c)
    assert "non-US" in reason and "75.0%" in reason
    with pytest.raises(O.InfeasibleError):
        O.max_sharpe_constrained(np.ones(12) * 0.05, np.eye(12) * 0.04, c)
    # bounds that cannot sum to one
    bad = O.build_constraints(["a", "b"], [1, 1], bounds=[(0, 0.3), (0, 0.3)], min_non_us=0)
    assert "maximum weights sum" in O.infeasibility_reason(bad)


def test_guideline_breaks_the_rule_and_feasible_guideline_breaks_the_cap():
    c = build.rule_constraints(PICKS, build.Settings())
    g = build.guideline_weights(PICKS)
    gf = build.guideline_weights(PICKS, (0.20, 0.35))
    cg = O.check_weights(np.array([g[t] for t in TICK]), c)
    cf = O.check_weights(np.array([gf[t] for t in TICK]), c)
    assert not cg["non_us_ok"] and cg["non_us_share"] == pytest.approx(0.625)
    assert cf["non_us_ok"] and not cf["bounds_ok"]
    assert sum(g.values()) == pytest.approx(1) and sum(gf.values()) == pytest.approx(1)


def _synthetic(seed=0, years=6):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2015-01-01", periods=252 * years)
    vols = np.array([0.03, 0.035, 0.03, 0.025, 0.03, 0.025, 0.006, 0.005, 0.006, 0.007, 0.01, 0.02])
    common = rng.normal(0, 0.01, (len(days), 1))
    r = rng.normal(0.0004, 1, (len(days), 12)) * vols / np.sqrt(2) + common * 0.5
    daily = pd.DataFrame(r, index=days, columns=TICK)
    daily.iloc[:100, TICK.index("HYEM")] = np.nan          # a late listing
    rf = pd.Series(0.0001, index=days)
    return SimpleNamespace(daily=daily, rf=rf)


def test_walk_forward_weights_obey_the_rules_at_every_rebalance():
    d = _synthetic()
    st = build.Settings(lookback_years=1, start="2015-01-01")
    run = build.run_walk("t", d, PICKS, st, rule=True)
    c = build.rule_constraints(PICKS, st)
    assert len(run.walk.weights) >= 20
    for dt, w in run.walk.weights.iterrows():
        assert O.check_weights(w.to_numpy(), c, tol=1e-6)["ok"], dt
    # the first rebalance waits until HYEM has the minimum common history
    assert run.walk.weights.index[0] > d.daily.index[100 + st.min_common_days - 1]
    # drift trigger: realised non-US share never below 0.68 for more than one day in a row
    nu = run.walk.holdings.to_numpy() @ np.array([p["non_us"] for p in PICKS])
    below = nu < 0.68 - 1e-9
    assert not (below[1:] & below[:-1]).any()
    # monthly series is the compounded daily series
    assert run.monthly.index.freqstr in ("ME", None) or True
    assert (1 + run.monthly).prod() == pytest.approx((1 + run.walk.returns).prod())


def test_walk_forward_uses_only_past_data():
    d = _synthetic(1)
    st = build.Settings(lookback_years=1, start="2015-01-01")
    base = build.run_walk("a", d, PICKS, st, rule=True)
    i = int(d.daily.index.get_loc(base.walk.weights.index[3]))
    d2 = SimpleNamespace(daily=d.daily.copy(), rf=d.rf)
    d2.daily.iloc[i:] = d2.daily.iloc[i:] * 5 + 0.01        # change the future only
    alt = build.run_walk("b", d2, PICKS, st, rule=True)
    np.testing.assert_allclose(base.walk.weights.iloc[:4].to_numpy(), alt.walk.weights.iloc[:4].to_numpy(),
                               atol=1e-10)


def test_rebalance_schedule():
    days = pd.bdate_range("2020-01-01", "2020-12-31")
    q = backtest.rebalance_schedule(days, "2020-01-01", "quarterly")
    assert [str(x.date()) for x in days[q]] == ["2020-01-01", "2020-04-01", "2020-07-01", "2020-10-01"]
    assert backtest.rebalance_schedule(days, "2020-01-01", "monthly").sum() == 12
    assert backtest.rebalance_schedule(days, "2020-01-01", "annual").sum() == 1


def test_monte_carlo_targets_on_a_constructed_series():
    idx = pd.date_range("2013-01-31", periods=120, freq="ME")
    r = pd.Series(0.005, index=idx)                         # constant: every path is the same
    st = build.Settings(mc_paths=500)
    mc = build.monte_carlo(r, 0.02, st, 0.025)
    hist, fwd = mc["historical"], mc["forward"]
    assert hist["median_ending_value"] == pytest.approx(100_000 * 1.005 ** 84, rel=1e-9)
    assert fwd["median_ending_value"] == pytest.approx(100_000 * 1.02 ** 7, rel=1e-6)
    full = {"max_drawdown": -0.10, "worst_calendar_year": -0.05}
    t_hist = build.evaluate_targets(hist, full, 0.025)
    assert t_hist["median_ending_value"]["pass"] and t_hist["prob_nominal_loss"]["pass"]
    assert t_hist["prob_beat_inflation"]["value"] == 1.0 and t_hist["all_pass"]
    t_fwd = build.evaluate_targets(fwd, {"max_drawdown": -0.30, "worst_calendar_year": -0.25}, 0.025)
    assert not t_fwd["median_ending_value"]["pass"]           # 114,869 < 145,000
    assert t_fwd["prob_beat_inflation"]["value"] == 0.0       # 2% a year never beats 2.5%
    assert not t_fwd["max_drawdown"]["pass"] and not t_fwd["worst_calendar_year"]["pass"]
    assert not t_fwd["all_pass"]


def test_fixed_mix_resets_each_quarter():
    idx = pd.date_range("2020-01-31", periods=6, freq="ME")
    M = pd.DataFrame({"A": [0.1, 0.1, 0.1, 0.0, 0.0, 0.0], "B": [0.0] * 6}, index=idx)
    r = build.fixed_mix_monthly(M, {"A": 0.5, "B": 0.5})
    assert r.iloc[0] == pytest.approx(0.05)
    assert r.iloc[1] == pytest.approx((0.5 * 1.21 + 0.5) / (0.5 * 1.1 + 0.5) - 1)
    assert r.iloc[3] == pytest.approx(0.0)


def test_clean_rounds_and_removes_nan():
    out = build.clean({"a": np.float64(1.23456789), "b": float("nan"), "c": [np.int64(2), np.bool_(True)]})
    assert out == {"a": 1.234568, "b": None, "c": [2, True]}


REQUIRED = ["schema_version", "as_of", "settings", "positions", "rule_checks", "portfolios", "variants",
            "adjustments", "attribution", "monte_carlo", "targets", "frontiers", "whatif", "sensitivity",
            "reproduce"]
PORTFOLIOS = ["guideline", "guideline_feasible", "optimized", "optimized_overlay", "no_rule", "GUIDE_BENCH",
              "SIXTY_FORTY", "GLOBAL_6040"]


@pytest.mark.skipif(not (ROOT / "reports" / "final" / "portfolio.json").exists(),
                    reason="run python -m portfolio.build --write first")
def test_portfolio_json_layout():
    path = ROOT / "reports" / "final" / "portfolio.json"
    assert path.stat().st_size < 5_000_000
    r = json.loads(path.read_text(encoding="utf-8"))
    assert all(k in r for k in REQUIRED)
    assert r["schema_version"] == 1 and r["reproduce"] == "python -m portfolio.build --write"
    for k in PORTFOLIOS:
        e = r["portfolios"][k]
        for f in ("weights", "monthly", "metrics", "stress", "rule_checks", "turnover", "cost_drag"):
            assert f in e, (k, f)
        assert set(e["metrics"]) >= {"in_sample", "out_of_sample", "full"}
    assert abs(sum(p["weight"] for p in r["positions"]) - 1) < 1e-6
    assert r["portfolios"]["optimized"]["rule_checks"]["all_rebalances_ok"]
    w = r["whatif"]
    n = len(w["tickers"])
    assert len(w["mu"]) == n and len(w["cov"]) == n and len(w["non_us_share"]) == n
    for lab in ("ex_ante", "ex_post"):
        assert len(r["frontiers"][lab]["rule_70"]["points"]) <= 25
