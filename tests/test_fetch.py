"""Offline unit tests for research/fetch.py (no network)."""

import os

import numpy as np
import pandas as pd
import pytest

from research import fetch

UNI = pd.DataFrame({
    "ticker": ["AAPL", "2330.TW", "EMB", "GLD", "^GSPC", "EURUSD=X", "JPY=X", "XYLD"],
    "type": ["us_growth_stock", "intl_growth_stock", "em_bond", "other", "index", "fx", "fx", "overlay"],
    "role": ["candidate"] * 8,
    "currency": ["USD", "TWD", "USD", "USD", "USD", "EUR", "JPY", "USD"],
    "usd_ticker": ["AAPL", "TSM", "EMB", "GLD", "", "", "", "XYLD"],
    "edgar_cik": ["320193", "0001046179", "", "", "", "", "", ""],
    "category": ["", "", "", "", "", "fx_direct", "fx_inverse", ""],
})


def test_fetch_list_per_step():
    assert fetch.fetch_list(UNI, "prices") == ["AAPL", "2330.TW", "EMB", "GLD", "^GSPC", "XYLD"]
    assert fetch.fetch_list(UNI, "prices_usd") == ["TSM"]
    assert fetch.fetch_list(UNI, "fx") == ["EURUSD=X", "JPY=X"]
    assert fetch.fetch_list(UNI, "fundamentals") == ["AAPL", "2330.TW"]
    assert fetch.fetch_list(UNI, "funds") == ["EMB", "GLD", "XYLD"]
    assert fetch.fetch_list(UNI, "edgar") == ["0000320193", "0001046179"]


def test_read_universe_keeps_cik_zeros(tmp_path):
    p = tmp_path / "u.csv"
    p.write_text("ticker,type,role,edgar_cik\nAAPL,us_growth_stock,candidate,0000320193\n")
    u = fetch.read_universe(p)
    assert u.loc[0, "edgar_cik"] == "0000320193" and u.loc[0, "usd_ticker"] == ""


def test_fx_direct_vs_inverse():
    idx = pd.date_range("2024-01-01", periods=3)
    close = pd.DataFrame({"EURUSD=X": [1.1, 1.2, 1.25], "JPY=X": [100.0, 125.0, 0.0]}, index=idx)
    fx = fetch.fx_to_usd_per_unit(close, UNI[UNI.type == "fx"])
    assert list(fx.columns) == ["EUR", "JPY"]
    assert fx["EUR"].tolist() == [1.1, 1.2, 1.25]          # direct: unchanged
    assert fx["JPY"].iloc[0] == pytest.approx(0.01)         # inverse: 1/x
    assert fx["JPY"].iloc[1] == pytest.approx(0.008)
    assert np.isnan(fx["JPY"].iloc[2])                      # zero quote is not inverted into inf


def test_parse_oecd_csv():
    text = ("DATAFLOW,REF_AREA,FREQ,MEASURE,UNIT_MEASURE,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n"
            "X,USA,M,IRLT,PA,2005-01,4.22,A\nX,USA,M,IRLT,PA,2005-02,4.17,A\n"
            "X,EA20,M,IRLT,PA,2005-01,3.60,A\nX,BRA,M,IRLT,PA,2005-02,,A\n")
    df = fetch.parse_oecd_csv(text, "10Y")
    assert set(df.columns) == {"US_10Y", "EA_10Y"}
    assert df.index[0] == pd.Timestamp("2005-01-01")
    assert df.loc["2005-02-01", "US_10Y"] == 4.17
    assert np.isnan(df.loc["2005-02-01", "EA_10Y"])


def test_parse_cboe_csv():
    text = "Some preface\nDATE,BXM\n06/30/1986,100.0\n07/01/1986,101.5\n"
    s = fetch.parse_cboe_csv(text)
    assert s.index[0] == pd.Timestamp("1986-06-30") and s.iloc[1] == 101.5 and s.name == "value"
    text2 = "DATE,OPEN,HIGH,LOW,CLOSE\n01/02/2020,1,2,0.5,1.5\n"
    assert fetch.parse_cboe_csv(text2).iloc[0] == 1.5


def test_merge_columns_keeps_existing():
    idx = pd.date_range("2024-01-01", periods=3)
    old = pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=idx)
    nidx = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    new = pd.DataFrame({"A": [9.0] * 4, "B": [5.0, 6.0, 7.0, 8.0]}, index=nidx)
    m = fetch.merge_columns(old, new)
    assert m["A"].dropna().tolist() == [1.0, 2.0, 3.0]       # untouched
    assert m["B"].notna().sum() == 4 and len(m) == 5
    r = fetch.merge_columns(old, new, refresh=True)
    assert r["A"].dropna().tolist() == [9.0] * 4
    assert fetch.merge_columns(None, new).equals(new.sort_index())


def test_fund_row_conversions():
    r = fetch.fund_row("EMB", {"netExpenseRatio": 0.39, "firstTradeDateMilliseconds": 1196726400000,
                               "totalAssets": 1e10, "yield": 0.06, "quoteType": "ETF"})
    assert r["expense_ratio"] == pytest.approx(0.0039) and r["inception"] == "2007-12-04"
    r2 = fetch.fund_row("PEBIX", {"annualReportExpenseRatio": 0.0085})
    assert r2["expense_ratio"] == 0.0085


def test_parse_worldbank():
    payload = [{"page": 1}, [
        {"countryiso3code": "MEX", "country": {"id": "MX"}, "date": "2020", "value": 3.4},
        {"countryiso3code": "MEX", "country": {"id": "MX"}, "date": "2021", "value": None},
        {"countryiso3code": "USA", "country": {"id": "US"}, "date": "2020", "value": 1.2}]]
    df = fetch.parse_worldbank(payload)
    assert df.loc[2020, "MX"] == 3.4 and list(df.index) == [2020]


@pytest.mark.skipif(os.environ.get("FETCH_LIVE") != "1", reason="network test; set FETCH_LIVE=1")
def test_live_cboe():
    s = fetch.parse_cboe_csv(fetch.http_get(
        "https://cdn.cboe.com/api/global/us_indices/daily_prices/BXM_History.csv").decode())
    assert len(s) > 1000
