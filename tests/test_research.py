import numpy as np
import pandas as pd

from research import bonds, config, data, dcf, fundamentals, montecarlo


def test_par_bond_prices_at_100():
    assert np.isclose(bonds.price(0.05, 0.05, 10, 1), 100.0)
    assert np.isclose(bonds.price(0.30, 0.30, 2, 2), 100.0)


def test_bond_total_return_is_carry_when_yields_flat():
    y = pd.Series(0.06, index=pd.date_range("2020-01-31", periods=13, freq="ME"))
    r = bonds.total_returns(y, 10, 1)
    assert np.isclose((1 + r).prod() - 1, 0.06, atol=0.003)


def test_duration_close_to_textbook():
    dur, _ = bonds.duration_convexity(0.04, 10, 1)
    assert 8.0 < dur < 8.3  # modified duration of a 10y 4% annual par bond is ~8.11


def test_dcf_implied_return_inverts_value():
    s = config.DCFSettings()
    flows = dcf.cash_flows(100.0, 0.10, 0.03, s)
    v = dcf.value(flows, 0.09, 0.03)
    assert np.isclose(dcf.implied_return(flows, 0.03, v), 0.09, atol=1e-6)


def test_cyclical_path_reaches_mid_cycle():
    s = config.DCFSettings()
    flows = dcf.cash_flows(100.0, 0.2, 0.025, s, mid_cycle=0.5, gn=0.04)
    assert np.isclose(flows[s.cycle_years], 50.0)


def test_dilution_skips_share_class_jumps():
    sh = pd.Series([100.0, 99.0, 98.0, 110.0], index=pd.date_range("2022", periods=4, freq="YE"))
    assert fundamentals.net_dilution(sh) < 0


def test_forward_monte_carlo_hits_target_median():
    rng = np.random.default_rng(0)
    r = pd.DataFrame({"A": rng.normal(0.02, 0.06, 240), "B": rng.normal(0.0, 0.02, 240)})
    st = config.MonteCarloSettings(n_paths=4000)
    out = montecarlo.simulate(r, st, targets={"A": 0.08, "B": 0.03})
    assert abs(out["A"]["annualised"]["50"] - 0.08) < 0.02
    assert abs(out["B"]["annualised"]["50"] - 0.03) < 0.01


def test_pipeline_runs_on_synthetic_data(tmp_path, monkeypatch):
    import research_run
    monkeypatch.setattr(research_run, "OUT", tmp_path)
    monkeypatch.setattr("sys.argv", ["research_run.py", "--synthetic"])
    research_run.main()
    assert (tmp_path / "results.json").exists()
