"""Tests for research/screen (synthetic data; one integration test on the SEC fixtures)."""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research import screen as s
from research.screen import cli, edgar as ed, fundamental as fu, prices as pr, technical as te

EDGAR = Path(__file__).resolve().parent.parent / "data" / "research" / "edgar"


# ---------------------------------------------------------------- helpers
def _walk(n_days, n_assets, seed=0, start="2005-01-03", vol=0.01, drift=0.0003):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n_days)
    r = rng.normal(drift, vol, (n_days, n_assets))
    return pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index=idx,
                        columns=[f"A{i}" for i in range(n_assets)])


def _universe(rows, path):
    cols = pr.UNIVERSE_COLUMNS
    pd.DataFrame([{c: r.get(c, "") for c in cols} for r in rows]).to_csv(path, index=False)
    return s.load_universe(path)


# ---------------------------------------------------------------- universe and prices
def test_load_universe_keeps_cik_and_flags_problems(tmp_path):
    u = _universe([{"ticker": "AAA", "type": "us_growth_stock", "role": "candidate", "currency": "usd",
                    "edgar_cik": "0000320193", "market_cap_usd_bn": "12.5"},
                   {"ticker": "AAA", "type": "us_growth_stock", "role": "candidate"},
                   {"ticker": "BBB", "type": "weird", "role": "candidate", "currency": "EUR"}],
                  tmp_path / "u.csv")
    assert list(u["ticker"]) == ["AAA", "BBB"]
    assert u.loc[0, "edgar_cik"] == "0000320193" and u.loc[0, "currency"] == "USD"
    assert u.loc[0, "market_cap_usd_bn"] == 12.5
    assert "unknown type" in u.loc[1, "universe_flags"]


def test_usd_prices_multiplies_by_fx_and_handles_local_currency_funds():
    idx = pd.bdate_range("2020-01-01", periods=5)
    px = pd.DataFrame({"X.T": [100.0] * 5, "EMLC": [20.0] * 5, "Z": [1.0] * 5}, index=idx)
    fx = pd.DataFrame({"JPY": [0.01, np.nan, 0.02, 0.02, 0.02]}, index=idx)
    u = pd.DataFrame([{"ticker": "X.T", "currency": "JPY", "listing": "TSE"},
                      {"ticker": "EMLC", "currency": "LOCAL", "listing": "NYSE Arca"},
                      {"ticker": "Z", "currency": "BRL", "listing": "B3"}])
    out = s.usd_prices(px, fx, u)
    assert list(out["X.T"]) == [1.0, 1.0, 2.0, 2.0, 2.0]          # FX forward-filled, never back
    assert (out["EMLC"] == 20.0).all()                             # US-listed fund: price in USD
    assert "Z" not in out                                          # no BRL series: left out
    assert pr.price_coverage(px, fx, u)["Z"].startswith("no FX series")


def test_monthly_returns_use_month_end():
    idx = pd.to_datetime(["2020-01-15", "2020-01-31", "2020-02-14", "2020-02-28", "2020-03-31"])
    m = s.monthly_returns(pd.DataFrame({"a": [1.0, 2.0, 2.5, 3.0, 3.3]}, index=idx))
    assert list(m.index.strftime("%Y-%m-%d")) == ["2020-02-29", "2020-03-31"]
    assert np.allclose(m["a"], [0.5, 0.1])


def test_benchmark_5050_is_monthly_rebalanced_average():
    idx = pd.date_range("2020-01-31", periods=3, freq="ME")
    mb = pd.DataFrame({"EFG": [0.02, -0.01, 0.03], "EEM": [0.04, 0.01, -0.01]}, index=idx)
    b = s.benchmark_monthly("EFG_EEM_5050", mb)
    assert np.allclose(b, [0.03, 0.0, 0.01])
    assert s.benchmark_monthly("IVW", mb) is None
    lvl = s.benchmark_level(b)
    assert lvl.iloc[0] == 1.0 and np.isclose(lvl.iloc[-1], 1.03 * 1.0 * 1.01)


def test_dividend_factor_undoes_yahoo_adjustment():
    idx = pd.bdate_range("2020-01-01", periods=300)
    raw = pd.Series(np.linspace(50, 80, 300), index=idx)
    divs = pd.Series([1.0, 1.2], index=[idx[100], idx[200]])
    adj = raw.copy()
    for e, d in divs.items():                     # Yahoo: scale closes before the ex-date
        prev = raw.index[raw.index < e][-1]
        adj[adj.index < e] *= 1 - d / raw[prev]
    assert np.allclose(adj / s.dividend_factor(adj, divs), raw)


# ---------------------------------------------------------------- hard screens
def test_hard_screen_needs_60_months_to_as_of_and_ignores_later_data():
    idx = pd.bdate_range("2012-12-03", "2019-12-31")
    daily = pd.DataFrame({"OK": 100.0, "LATE": 100.0}, index=idx)
    daily.loc[:"2012-12-31", "LATE"] = np.nan      # first price 2013-01-01: 59 returns to 2017-12
    daily.loc["2018-01-01":, "OK"] = np.nan        # data after as_of must not matter
    u = pd.DataFrame([{"ticker": t, "type": "other", "role": "candidate", "currency": "USD",
                       "aum_usd_bn": 1.0, "expense_ratio": 0.004} for t in ("OK", "LATE")]
                     + [{"ticker": "EXP", "type": "other", "role": "candidate", "aum_usd_bn": 0.1,
                         "expense_ratio": 0.009}])
    daily["EXP"] = 100.0
    h = s.hard_screens(u, daily, None, "2017-12-31").set_index("ticker")
    assert h.loc["OK", "months_in_sample"] == 60 and h.loc["OK", "passed"]
    assert h.loc["LATE", "months_in_sample"] == 59 and not h.loc["LATE", "passed"]
    assert "AUM" in h.loc["EXP", "reasons"] and "expense ratio" in h.loc["EXP", "reasons"]
    assert "short history" in h.loc["OK", "flags"]


def test_hard_screen_stock_rules():
    daily = pd.DataFrame(100.0, index=pd.bdate_range("2010-01-01", "2018-06-30"),
                         columns=["US1", "US2", "FOR", "NP"])
    u = pd.DataFrame([
        {"ticker": "US1", "type": "us_growth_stock", "role": "candidate", "country": "US", "market_cap_usd_bn": 50},
        {"ticker": "US2", "type": "us_growth_stock", "role": "faded_leader", "country": "US", "market_cap_usd_bn": 5},
        {"ticker": "FOR", "type": "us_growth_stock", "role": "candidate", "country": "DE", "market_cap_usd_bn": 50},
        {"ticker": "NP", "type": "us_growth_stock", "role": "candidate", "country": "US", "market_cap_usd_bn": 50}])
    fund = pd.DataFrame({"rev_cagr_3y": [0.10, 0.20, 0.10, 0.02], "fundamentals_pit": [True, True, True, False]},
                        index=["US1", "US2", "FOR", "NP"])
    h = s.hard_screens(u, daily, None, "2017-12-31", fund, traded_value=pd.Series({"US1": 25.0}),
                       mcap_asof=pd.Series({"US1": 3.0, "US2": 1.0})).set_index("ticker")
    assert h.loc["US1", "passed"]
    assert "market cap today" in h.loc["US2", "reasons"] and "at as_of" in h.loc["US2", "reasons"]
    assert "not US" in h.loc["FOR", "reasons"]
    assert h.loc["NP", "passed"] and "needs point-in-time" in h.loc["NP", "flags"]  # not checked, not failed
    assert "traded value not checked" in h.loc["US2", "flags"]


# ---------------------------------------------------------------- technical signals
def test_signal_at_t_uses_prices_to_end_of_t_minus_1_only():
    daily = _walk(2000, 6, seed=1)
    bench = daily.mean(axis=1)
    t = pd.Timestamp("2010-06-30")
    base = s.technical_signals(daily, bench)
    cut = pd.Timestamp("2010-05-31")                     # end of month t-1
    shocked = daily.copy()
    shocked.loc[shocked.index > cut] *= 3.0              # change every price after t-1
    b2 = shocked.mean(axis=1)
    alt = s.technical_signals(shocked, b2)
    for k in te.SIGNALS:
        assert base[k].loc[t].notna().all()
        pd.testing.assert_series_equal(base[k].loc[t], alt[k].loc[t])
        assert not base[k].loc[pd.Timestamp("2010-08-31")].equals(alt[k].loc[pd.Timestamp("2010-08-31")]) \
            or k == "T2"


def test_signal_values_match_definitions():
    daily = _walk(800, 3, seed=2)
    sig = s.technical_signals(daily, daily["A0"], as_of="2007-12-31")
    me = daily.resample("ME").last()
    t = pd.Timestamp("2007-08-31")
    p = lambda k: me.index[me.index.get_loc(t) - k]       # month-end k months before t
    a = "A1"
    assert np.isclose(sig["T1"].loc[t, a], me.loc[p(2), a] / me.loc[p(13), a] - 1)
    r6 = me.loc[p(1)] / me.loc[p(7)] - 1
    assert np.isclose(sig["T3"].loc[t, a], r6[a] - r6["A0"]) and np.isclose(sig["T3"].loc[t, "A0"], 0)
    d = daily.loc[:p(1), a]
    assert sig["T2"].loc[t, a] == float(d.iloc[-1] > d.tail(200).mean())
    assert np.isclose(sig["T4"].loc[t, a], d.pct_change().tail(252).std() * np.sqrt(252))
    assert np.isclose(sig["T5"].loc[t, a], d.iloc[-1] / d.tail(252).max() - 1)
    snap = s.signals_at(sig, "2007-12-31")                # built from data to as_of
    assert sig["T1"].index[-1] == pd.Timestamp("2008-01-31")
    assert np.isclose(snap.loc[a, "T1"], me.loc["2007-11-30", a] / me.loc["2006-12-31", a] - 1)


def test_tercile_strategy_reproduces_known_ir():
    rng = np.random.default_rng(3)
    idx = pd.date_range("2008-01-31", periods=120, freq="ME")
    a = rng.normal(0.004, 0.01, 120)                      # the active return by construction
    base = rng.normal(0.008, 0.04, 120)
    cols = [f"N{i}" for i in range(9)]
    R = pd.DataFrame({c: base + (a if i < 3 else -a / 2) for i, c in enumerate(cols)}, index=idx)
    S = pd.DataFrame({c: float(9 - i) for i, c in enumerate(cols)}, index=idx)
    bt = s.tercile_backtest(S, R, cost_bps=0)
    assert np.allclose(bt["active"], a)
    v = s.validate_signals({"T1": S}, R, in_sample_end="2012-12-31", cost_bps=0,
                           in_sample_start="2008-01-01").loc["T1"]
    oos = a[60:]
    assert np.isclose(v["ir_oos"], oos.mean() / oos.std(ddof=1) * np.sqrt(12))
    assert np.isclose(v["t_oos"], oos.mean() / (oos.std(ddof=1) / np.sqrt(60)))
    assert v["kept"] == bool(v["ir_oos"] > 0 and v["t_oos"] > 1.0)


def test_tercile_cost_on_turnover_and_binary_signal():
    idx = pd.date_range("2010-01-31", periods=24, freq="ME")
    R = pd.DataFrame(0.0, index=idx, columns=list("abcdef"))
    flip = np.where(np.arange(24)[:, None] % 2 == 0, [6, 5, 4, 3, 2, 1], [1, 2, 3, 4, 5, 6])
    S = pd.DataFrame(flip, index=idx, columns=R.columns, dtype=float)
    bt = s.tercile_backtest(S, R, cost_bps=10)
    assert bt["turnover"].iloc[0] == 0 and np.allclose(bt["turnover"].iloc[1:], 2.0)
    assert np.allclose(bt["active"].iloc[1:], -0.002)        # 10 bps x 2 one-way trades
    B = pd.DataFrame([[1, 0, 1, 0, 0, 0]] * 24, index=idx, columns=R.columns, dtype=float)
    assert (s.tercile_backtest(B, R, binary=True)["k"] == 2).all()


def test_tercile_backtest_is_fast():
    import time
    rng = np.random.default_rng(4)
    idx = pd.date_range("2005-01-31", periods=200, freq="ME")
    R = pd.DataFrame(rng.normal(0.01, 0.05, (200, 40)), index=idx)
    sig = {k: pd.DataFrame(rng.normal(size=(200, 40)), index=idx) for k in te.SIGNALS}
    t0 = time.perf_counter()
    out = s.validate_signals(sig, R)
    assert time.perf_counter() - t0 < 2.0 and list(out.index) == list(te.SIGNALS)


# ---------------------------------------------------------------- scoring
def test_percentile_and_rubric_arithmetic():
    df = pd.DataFrame({"x": [1, 2, 3, 4], "y": [4, 3, 2, np.nan]}, index=list("abcd"))
    p = s.percentile_scores(df, ["x", "y"], {"x": True, "y": False})
    assert list(p["x"]) == [0.25, 0.5, 0.75, 1.0]
    assert np.allclose(p["y"].iloc[:3], [1 / 3, 2 / 3, 1.0]) and np.isnan(p["y"].iloc[3])
    comp = pd.DataFrame({k: [1.0, 0.5] for k in s.RUBRIC_WEIGHTS}, index=["a", "b"])
    r = s.rubric_score(comp)
    assert np.allclose(r["rubric_total"], [100.0, 50.0])
    comp["technical"] = np.nan                            # no signal kept: 5 points redistributed
    comp.loc["a", "oos_sharpe"] = 0.0
    r = s.rubric_score(comp)
    assert np.isclose(r.loc["a", "rubric_total"], 100 * (95 - 20) / 95)
    assert "technical" not in r.attrs["weights"] and r.loc["a", "missing_weight"] == 0


def test_deflated_sharpe_matches_hand_computation():
    # N=20, T=96, SR=1.0/yr -> 0.288675/month, skew -0.5, kurt 4, V = 1/95:
    # Z(0.95)=1.644854, Z(1-1/(20e))=2.088110, SR0=sqrt(1/95)*(0.422784*1.644854+0.577216*2.088110)=0.195009
    # z = (0.288675-0.195009)*sqrt(95)/sqrt(1+0.5*0.288675+0.75*0.083333)=0.831041 -> Phi = 0.797025
    assert np.isclose(s.deflated_sharpe(1.0, 20, 96, -0.5, 4.0), 0.7970246363, atol=1e-8)
    assert np.isclose(s.expected_max_sharpe(20, 1 / 95), 0.1950085212, atol=1e-9)
    assert s.expected_max_sharpe(1, 0.01) == 0.0
    assert s.deflated_sharpe(1.0, 1, 96, 0.0, 3.0) > s.deflated_sharpe(1.0, 50, 96, 0.0, 3.0)


def test_is_oos_rank_test():
    out = s.is_oos_rank_test(pd.Series([1, 2, 3, 4, 5.0]), pd.Series([2, 4, 6, 8, 10.0]))
    assert np.isclose(out["rho"], 1.0) and out["predictive"] and out["n"] == 5
    assert s.is_oos_rank_test(pd.Series([1.0, 2]), pd.Series([1.0, 2]))["n"] == 2


# ---------------------------------------------------------------- EDGAR
def _fact(end, val, filed, form="10-K", fy=2017, start=True, fp="FY"):
    d = {"end": end, "val": val, "filed": filed, "form": form, "fy": fy, "fp": fp, "accn": f"a-{filed}-{form}"}
    if start:
        d["start"] = str(pd.Timestamp(end) - pd.Timedelta(days=364))[:10]
    return d


FIXTURE = {"cik": 1, "entityName": "Test", "facts": {
    "us-gaap": {
        "SalesRevenueNet": {"units": {"USD": [
            _fact("2014-12-31", 50.0, "2015-02-20", fy=2014),
            _fact("2016-12-31", 90.0, "2017-02-20", fy=2016),
            {"start": "2017-10-01", "end": "2017-12-31", "val": 30.0, "filed": "2018-02-20",
             "form": "10-K", "fy": 2017, "fp": "FY", "accn": "q4"}]}},     # quarter inside a 10-K
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            _fact("2017-12-31", 100.0, "2017-11-15"),                     # original 10-K
            _fact("2017-12-31", 110.0, "2018-03-01", form="10-K/A"),       # amendment, same year
            _fact("2017-06-30", 70.0, "2017-08-01", form="10-Q", fp="Q2")]}},
        "NetIncomeLoss": {"units": {"USD": [_fact("2017-12-31", 10.0, "2017-11-15")]}},
        "StockholdersEquity": {"units": {"USD": [_fact("2017-12-31", 40.0, "2017-11-15", start=False)]}},
        "LongTermDebt": {"units": {"USD": [_fact("2017-12-31", 20.0, "2017-11-15", start=False)]}},
        "CommercialPaper": {"units": {"USD": [_fact("2017-12-31", 5.0, "2017-11-15", start=False)]}},
    },
    "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        _fact("2018-01-31", 1000.0, "2018-02-15", start=False)]}}}}}


def test_edgar_parsing_picks_filing_known_at_as_of():
    f = s.edgar_facts(FIXTURE)
    assert set(f.columns) >= {"tag", "fy", "end", "value", "filed", "form", "unit"}
    rev = f[f["tag"] == "revenue"]
    assert 30.0 not in set(rev["value"]) and 70.0 not in set(rev["value"])   # quarter and 10-Q dropped
    p17 = s.point_in_time(f, "2017-12-31")
    assert p17.loc["2017-12-31", "revenue"] == 100.0          # amendment filed later is not known yet
    assert p17.loc["2016-12-31", "revenue"] == 90.0           # alias SalesRevenueNet unioned
    assert p17.loc["2017-12-31", "debt_total"] == 25.0        # long-term debt + commercial paper
    assert np.isnan(p17.loc["2017-12-31", "shares"])          # cover page filed 2018-02-15
    p18 = s.point_in_time(f, "2018-12-31")
    assert p18.loc["2017-12-31", "shares"] == 1000.0          # cover-page count after year end
    assert p18.loc["2017-12-31", "revenue"] == 110.0
    assert p18.loc["2017-12-31", "first_filed"] == pd.Timestamp("2017-11-15")
    assert s.point_in_time(f, "2015-01-31").empty


def test_split_detection_and_factor():
    sh = [{"end": "2013-12-31", "val": 1000, "filed": "2014-01-20"},
          {"end": "2014-03-31", "val": 990, "filed": "2014-04-20"},
          {"end": "2014-09-30", "val": 6930, "filed": "2014-10-20"},
          {"end": "2014-12-31", "val": 6900, "filed": "2015-01-20"}]
    cj = {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": sh}}}}}
    sp = s.split_events(cj)
    assert list(sp) == [7.0] and pd.Timestamp("2014-03-31") < sp.index[0] < pd.Timestamp("2014-09-30")
    assert s.split_factor(sp, "2014-01-01") == 7.0 and s.split_factor(sp, "2015-01-01") == 1.0


# ---------------------------------------------------------------- fundamental scores
def _table(rev0, rev3, ni0, ni3, pit=True):
    ends = pd.to_datetime(["2014-12-31", "2015-12-31", "2016-12-31", "2017-12-31"])
    t = pd.DataFrame({"revenue": np.linspace(rev0, rev3, 4), "net_income": np.linspace(ni0, ni3, 4),
                      "operating_income": np.linspace(rev0, rev3, 4) * 0.2, "cfo": 30.0, "capex": 10.0,
                      "da": 5.0, "income_tax": 5.0, "pretax_income": 20.0, "eps_diluted": np.linspace(ni0, ni3, 4) / 10,
                      "debt_total": 50.0, "cash": 20.0, "equity": 100.0, "shares": 10.0}, index=ends)
    t["first_filed"] = t.index + pd.Timedelta(days=40)
    t["filed_shares"] = t["filed_eps_diluted"] = t["first_filed"]
    t.attrs["point_in_time"] = pit
    return t


def test_fundamental_score_stocks_measures_and_weights():
    px = pd.DataFrame(200.0, index=pd.bdate_range("2012-01-01", "2018-03-31"), columns=["A", "B", "C"])
    tables = {"A": _table(100, 200, 10, 30), "B": _table(100, 120, 10, 12), "C": None}
    df = s.fundamental_score_stocks(tables, px, "2017-12-31")
    assert np.isclose(df.loc["A", "rev_cagr_3y"], 2 ** (1 / 3) - 1)
    assert np.isclose(df.loc["A", "fcf_yield"], 20 / (10 * 200))
    assert np.isclose(df.loc["A", "roic_or_roe"], 40 * (1 - 0.25) / (50 + 100 - 20))
    assert np.isclose(df.loc["A", "net_debt_ebitda"], 30 / 45)
    assert np.isclose(df.loc["A", "pe_now"], 200 / 3.0)
    assert df.loc["A", "growth_score"] == 1.0 and df.loc["B", "growth_score"] == 0.5
    g, q, v = (df.loc["B", f"{k}_score"] for k in ("growth", "quality", "valuation"))
    assert np.isclose(df.loc["B", "fundamental_score"], 0.4 * g + 0.3 * q + 0.3 * v)
    assert np.isnan(df.loc["C", "fundamental_score"]) and "no fundamentals" in df.loc["C", "fund_flags"]
    assert df.loc["A", "fundamentals_pit"]
    fin = s.fundamental_score_stocks({"A": _table(100, 200, 10, 30)}, px, "2017-12-31", financials=["A"])
    assert np.isclose(fin.loc["A", "roic_or_roe"], 0.30) and np.isnan(fin.loc["A", "net_debt_ebitda"])


def test_fundamental_score_bonds_carry():
    t = pd.DataFrame({"ytm": [0.06, 0.07, 0.065], "expected_fx_loss": [np.nan, 0.02, np.nan],
                      "local_currency": [False, True, True], "expense_ratio": [0.39, 0.30, 0.50],
                      "avg_rating": ["BBB", "Baa3", 12], "aum_usd_bn": [10, 3, 1]}, index=["H", "L", "X"])
    out = s.fundamental_score_bonds(t)
    assert np.allclose(out.loc[["H", "L"], "carry"], [0.06 - 0.0039, 0.07 - 0.02 - 0.003])
    assert np.isnan(out.loc["X", "carry"]) and "without expected FX loss" in out.loc["X", "fund_flags"]
    assert list(out["rating_score"]) == [9.0, 10.0, 12.0]
    assert np.isclose(s.expected_fx_loss(0.08, 0.02), 1 - 1.02 / 1.08)
    assert out["fundamental_score"].notna().all()


def test_fundamental_score_other_inflation_beta():
    idx = pd.date_range("2005-01-31", "2023-06-30", freq="ME")
    rng = np.random.default_rng(5)
    infl = 0.02 + np.cumsum(rng.normal(0, 0.001, len(idx)))
    cpi = pd.Series(100 * np.cumprod(np.r_[1.0, (1 + infl[1:]) ** (1 / 12)]), index=idx - pd.offsets.MonthBegin(1))
    c = cpi.copy(); c.index = idx
    dpi = (c / c.shift(12) - 1).diff()
    r = pd.DataFrame({"G": 0.005 + 3.0 * dpi.fillna(0) + rng.normal(0, 1e-5, len(idx)),
                      "B": rng.normal(0.003, 0.01, len(idx))}, index=idx)
    out = s.fundamental_score_other(r, cpi, "2017-12-31")
    assert abs(out.loc["G", "inflation_beta"] - 3.0) < 0.05
    assert np.isnan(out.loc["G", "ret_2022"]) and not np.isnan(out.loc["G", "ret_2022_info"])
    assert "2022 window after as_of" in out.loc["G", "fund_flags"]
    assert out.loc["G", "inflation_score"] == 1.0


# ---------------------------------------------------------------- stats
def test_stats_helpers():
    rng = np.random.default_rng(6)
    idx = pd.date_range("2010-01-31", periods=120, freq="ME")
    b = pd.Series(rng.normal(0.008, 0.04, 120), index=idx)
    r = 0.002 + 1.2 * b + pd.Series(rng.normal(0, 0.01, 120), index=idx)
    alpha, t, beta = s.alpha_t(r, b)
    assert abs(beta - 1.2) < 0.05 and abs(alpha - 0.024) < 0.03 and t > 0
    act = r - b
    assert np.isclose(s.info_ratio(r, b), act.mean() / act.std() * np.sqrt(12))
    assert np.isclose(s.tracking_error(r, b), act.std() * np.sqrt(12))
    assert np.isclose(s.sharpe(r), r.mean() / r.std() * np.sqrt(12))
    assert s.sortino(r) > s.sharpe(r) * 0.5
    up, dn = s.capture(r, b)
    assert up > 1 and dn > 1
    assert len(s.rolling_ir(r, b)) == 85 and 0 <= s.share_ir_positive(r, b) <= 1
    assert np.isclose(s.max_drawdown(pd.Series([0.1, -0.5, 0.2])), -0.5)
    m = s.metrics_block(r, b, None, n_trials=20)
    assert m["months"] == 120 and 0 <= m["deflated_sharpe"] <= 1 and m["t_stat_alpha"] == pytest.approx(t)


# ---------------------------------------------------------------- CLI
def test_cli_refuses_out_of_sample_as_of(capsys):
    assert cli.main(["score", "--type", "other", "--as-of", "2019-01-31"]) == 2
    assert "refused" in capsys.readouterr().err


def test_cli_end_to_end_on_synthetic_files(tmp_path):
    data, out = tmp_path / "data", tmp_path / "out"
    data.mkdir()
    names = ["G1", "G2", "G3", "G4", "NEW"]
    px = _walk(3500, len(names) + len(cli.BENCH_TICKERS), seed=7)
    px.columns = names + cli.BENCH_TICKERS
    px.loc[:"2015-01-01", "NEW"] = np.nan
    px.to_csv(data / "prices.csv")
    pd.DataFrame({"EUR": 1.1}, index=px.index).to_csv(data / "fx.csv")
    u = tmp_path / "u.csv"
    _universe([{"ticker": t, "type": "other", "role": "candidate", "currency": "USD", "listing": "NYSE Arca",
                "aum_usd_bn": 1.0, "expense_ratio": 0.4} for t in names], u)
    args = ["--type", "other", "--universe", str(u), "--out-dir", str(out), "--data-dir", str(data)]
    assert cli.main(["hard"] + args) == 0
    h = pd.read_csv(out / "other_hard.csv").set_index("ticker")
    assert h["passed"].sum() == 4 and not h.loc["NEW", "passed"]
    assert cli.main(["validate"] + args) == 0
    v = pd.read_csv(out / "other_signals.csv")
    assert list(v["signal"]) == list(te.SIGNALS) and v["months_oos"].min() > 0
    assert cli.main(["score"] + args) == 0
    sc = pd.read_csv(out / "other_scored.csv").set_index("ticker")
    assert sc.loc[["G1", "G2", "G3", "G4"], "T1"].notna().all()
    assert "kept signals from other_signals.csv" in sc["technical_note"].iloc[0]
    assert (sc["as_of"] == "2017-12-31").all()


# ---------------------------------------------------------------- SEC fixtures
@pytest.mark.skipif(not (EDGAR / "CIK0000320193.json").exists() or not (EDGAR / "CIK0001046179.json").exists(),
                    reason="SEC companyfacts fixtures not downloaded")
def test_edgar_integration_apple_and_tsmc():
    aapl = ed.read_companyfacts(EDGAR / "CIK0000320193.json")
    p = s.point_in_time(s.edgar_facts(aapl), "2017-12-31")
    assert p.attrs["currency"] == "USD"
    assert p.loc["2017-09-30", "revenue"] == 229_234e6 and p.loc["2014-09-27", "revenue"] == 182_795e6
    assert p.index.max() == pd.Timestamp("2017-09-30")              # FY2018 10-K filed Nov 2018
    sp = s.split_events(aapl)
    assert list(sp) == [7.0, 4.0]
    m, _ = fu.stock_measures(p, pd.Series(169.23 / 4, index=pd.bdate_range("2012-01-02", "2017-12-29")),
                             "2017-12-31", splits=sp)
    assert 0.8e12 < m["market_cap_local"] < 0.95e12                  # about $870bn at end-2017
    tsmc = ed.read_companyfacts(EDGAR / "CIK0001046179.json")
    f = s.edgar_facts(tsmc)
    assert s.point_in_time(f, "2017-12-31").empty                    # first XBRL 20-F filed 2018
    q = s.point_in_time(f, "2025-12-31")
    assert q.attrs["currency"] == "TWD" and q.loc["2024-12-31", "revenue"] == 2_894_307_700_000
