"""Phase 3 candidate analysis: INTERNATIONAL GROWTH STOCKS (local listings).

One shared script for the eight shortlisted names (research/plan/shortlist.md)
plus a metrics-only control table of every name that passed the hard screens
(faded leaders included). Implements method.md sections 1, 2, 3, 7, 9, 11, 12
and writes reports/candidates/<ID>.json in the research/plan/results_schema.md
format.

    python -m research.candidates.intl_growth --all --write
    python -m research.candidates.intl_growth --ticker 2330.TW [--write]

Conventions
- Monthly total returns: Yahoo adjusted closes (dividends reinvested), last
  close of each calendar month, the partial last month dropped. Daily prices go
  through research.screen.read_wide_csv (one-day spike filter).
- USD return u = local price x USD-per-unit FX (forward-filled onto the price
  dates, never backward). FX return f is defined by (1+u) = (1+l)(1+f), so the
  local / FX / USD split is exact month by month and for compounded windows.
- USD view: vs EFG_EEM_5050 (50% EFG + 50% EEM, monthly rebalanced) and BIL.
  Local view: vs the home index in local currency (Yahoo PRICE index, no
  dividends: local IR and alpha are flattered by roughly the index dividend
  yield) and the local 3-month rate (OECD <ISO2>_3M, the previous month's
  observation, i.e. known at the start of the month).
- Hedged USD return (covered interest parity, monthly roll):
      fp_t = (1 + i_US,t-1 / 12) / (1 + i_loc,t-1 / 12) - 1    (forward premium)
      hedged_t = u_t + fp_t - f_t - c,  c = 5 bp per roll (method.md s10)
  i.e. a forward sold each month on the position's start value; the residual
  unhedged part is l_t x f_t. hedge_cost = 12 x mean(c - fp_t): positive when
  the local rate is above the US rate (hedging INR costs carry, hedging DKK
  earned it in 2018-2026).
- Deflated Sharpe uses n_trials = 31 (international names that passed the
  hard screens), V = 1/(T-1) (method.md change log, section 7).
- Forward 7-year expected returns reuse research/capm.py, dcf.py,
  grinold_kroner.py, montecarlo.py and fxview.py through thin adapters, with
  research/candidates/assumptions_intl_growth.py extending
  research.config.MarketAssumptions.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from research import capm, dcf, fxview, grinold_kroner, montecarlo
from research.config import Stock
from research.data import Dataset, load_fundamentals
from research.metrics import cagr
from research.screen import (benchmark_monthly, deflated_sharpe, is_oos_rank_test, load_universe,
                             metrics_block, monthly_returns, rolling_ir, rolling_sharpe,
                             usd_crosscheck, usd_prices)
from research.screen import edgar as ed
from research.screen.fundamental import stock_measures
from research.screen.prices import read_dividends, read_wide_csv

from . import assumptions_intl_growth as A

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research"
PLAN = ROOT / "research" / "plan"
OUT = ROOT / "reports" / "candidates"
CHARTS = OUT / "charts"
MEMOS = ROOT / "research" / "candidates" / "memos"

TYPE = "intl_growth_stock"
BENCH = "EFG_EEM_5050"
IS_START, IS_END, OOS_START = "2010-01-01", "2017-12-31", "2018-01-01"
N_TRIALS = 31
CAPITAL = 100_000
CANDIDATES = ["NOVO-B.CO", "REA.AX", "2330.TW", "1299.HK", "0700.HK", "BAJFINANCE.NS",
              "000660.KS", "CSU.TO"]
FADED = ["BIDU", "VALE3.SA", "PETR4.SA", "TEVA.TA"]
DK_INDEX = "^STOXX50E_DKK"   # Euro Stoxx 50 converted to DKK (proxy home index for Denmark)

# currency -> yields.csv short-rate column (None = no series on disk)
SHORT_RATE = {"USD": "US_3M", "DKK": "DK_3M", "AUD": "AU_3M", "INR": "IN_3M", "CAD": "CA_3M",
              "KRW": "KR_3M", "CNY": "CN_3M", "EUR": "EA_3M", "JPY": "JP_3M", "GBP": "GB_3M",
              "CHF": "CH_3M", "SEK": "SE_3M", "BRL": None, "MXN": "MX_3M", "IDR": "ID_3M",
              "ZAR": "ZA_3M", "ILS": "IL_3M", "HKD": "US_3M", "TWD": None}

STRESS = {   # method.md section 11 (month-end to month-end)
    "gfc_2008": ("2007-10-31", "2009-02-28"),
    "taper_2013": ("2013-04-30", "2013-08-31"),
    "covid_2020": ("2020-01-31", "2020-03-31"),
    "inflation_2022": ("2021-12-31", "2022-10-31"),
}
USD_EPISODES = {"usd_2014_15": ("2014-05-31", "2015-03-31"), "usd_2021_22": ("2021-05-31", "2022-09-30")}

SECTOR = {"NOVO-B.CO": "Pharmaceuticals", "REA.AX": "Online classifieds (property)",
          "2330.TW": "Semiconductors (foundry)", "1299.HK": "Life insurance",
          "0700.HK": "Internet platforms and games", "BAJFINANCE.NS": "Consumer finance (NBFC)",
          "000660.KS": "Semiconductors (memory)", "CSU.TO": "Vertical-market software"}


SHORT = {"NOVO-B.CO": "Novo Nordisk", "REA.AX": "REA Group", "2330.TW": "TSMC", "1299.HK": "AIA",
         "0700.HK": "Tencent", "BAJFINANCE.NS": "Bajaj Finance", "000660.KS": "SK Hynix",
         "CSU.TO": "Constellation Software"}


def cid(ticker):
    """results_schema.md ID: '.' and '^' replaced by '_'."""
    return ticker.replace(".", "_").replace("^", "_")


def _f(x):
    """JSON-safe float (None for NaN/inf/missing)."""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return x
    return None if not math.isfinite(v) else round(v, 6)


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return _f(o)
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    return o


# ======================================================================== data
class Inputs:
    """Every file the analysis reads, loaded once (no network)."""

    def __init__(self, data_dir=DATA, plan_dir=PLAN):
        self.data_dir, self.plan_dir = Path(data_dir), Path(plan_dir)
        self.universe = load_universe(self.plan_dir / "universe.csv")
        self.scored = pd.read_csv(self.plan_dir / "longlists" / f"{TYPE}_scored.csv")
        self.insample = pd.read_csv(self.plan_dir / "longlists" / f"{TYPE}_insample_table.csv")
        passed = self.scored.loc[self.scored["passed"].astype(bool), "ticker"].tolist()
        self.passed = passed
        rows = self.universe[self.universe["ticker"].isin(set(passed) | set(CANDIDATES))]
        self.rows = rows.set_index("ticker", drop=False)
        idx = {r for r in rows["local_index"] if r} | {A.DK_INDEX_PROXY}
        need = set(passed) | set(CANDIDATES) | idx | {"EFG", "EEM", "ACWX", "ACWI", "BIL"}
        missing = []
        for f in ("prices.csv", "fx.csv", "yields.csv", "prices_usd_listing.csv"):
            if not (self.data_dir / f).exists():
                missing.append(str(self.data_dir / f))
        if missing:
            raise FileNotFoundError("missing data files: " + ", ".join(missing))
        self.prices = read_wide_csv(self.data_dir / "prices.csv", columns=need)
        absent = sorted(need - set(self.prices.columns))
        if any(t in absent for t in CANDIDATES + ["EFG", "EEM", "BIL"]):
            raise FileNotFoundError(f"price columns missing from prices.csv: {absent}")
        self.absent = absent
        self.fx = read_wide_csv(self.data_dir / "fx.csv")
        self.usd_listing = read_wide_csv(self.data_dir / "prices_usd_listing.csv")
        self.yields = pd.read_csv(self.data_dir / "yields.csv", index_col=0, parse_dates=True).sort_index()
        vol_path = self.data_dir / "volumes.csv"
        self.volumes = read_wide_csv(vol_path, spikes=False, columns=need) if vol_path.exists() else None

        # Denmark proxy index in DKK: EUR index x (USD per EUR) / (USD per DKK)
        sx = self.prices[A.DK_INDEX_PROXY].dropna()
        cross = (self.fx["EUR"] / self.fx["DKK"]).reindex(self.fx.index.union(sx.index)).ffill().reindex(sx.index)
        self.prices[DK_INDEX] = (sx * cross).reindex(self.prices.index)

        # universe rows for benchmarks / support tickers (USD) so usd_prices covers them
        bench_rows = pd.DataFrame([{"ticker": t, "currency": "USD", "listing": "NYSE Arca", "usd_ticker": ""}
                                   for t in ("EFG", "EEM", "ACWX", "ACWI", "BIL")])
        self.daily_usd = usd_prices(self.prices, self.fx, pd.concat([rows, bench_rows], ignore_index=True))
        local_cols = [c for c in self.prices.columns]
        self.m_local = monthly_returns(self.prices[local_cols], drop_partial=True)
        self.m_usd = monthly_returns(self.daily_usd, drop_partial=True)
        self.bench = benchmark_monthly(BENCH, self.m_usd)
        self.bil = self.m_usd["BIL"]
        self.acwx = self.m_usd["ACWX"]
        self.last_month = self.m_usd.index[-1]
        self.usd_broad = self._monthly_yield("USD_BROAD", scale=1.0)

    def _monthly_yield(self, col, scale=0.01):
        if col not in self.yields:
            return None
        s = self.yields[col].dropna() * scale
        s.index = s.index + pd.offsets.MonthEnd(0)
        return s.groupby(level=0).last()

    # ---- per-name series --------------------------------------------------
    def row(self, ticker):
        return self.rows.loc[ticker]

    def home_index(self, ticker):
        if ticker == "NOVO-B.CO":
            return DK_INDEX
        ix = self.row(ticker)["local_index"]
        return ix if ix and ix in self.m_local else None

    def series(self, ticker):
        """(local, usd, fx) monthly returns; fx from (1+u) = (1+l)(1+f)."""
        loc = self.m_local[ticker]
        usd = self.m_usd[ticker] if ticker in self.m_usd else loc
        fx = (1 + usd) / (1 + loc) - 1
        return loc, usd, fx

    def short_rate(self, ccy, index):
        """Monthly local risk-free return for months in `index`: previous month's annual
        3M rate / 12; flat assumption where no series (or before it starts). (series, note)"""
        a = A.market_assumptions()
        flat = a.risk_free.get(ccy)
        col = SHORT_RATE.get(ccy)
        s = self._monthly_yield(col) if col else None
        grid = pd.date_range(index.min() - pd.offsets.MonthEnd(1), index.max(), freq="ME")
        if s is None or s.empty:
            if flat is None:
                return None, f"no short rate for {ccy}"
            return pd.Series(flat / 12, index=index), A.NO_SERIES_NOTE.get(ccy, f"{ccy} 3M: flat {flat:.2%}")
        lagged = (s.reindex(grid).ffill(limit=3) / 12).shift(1).reindex(index)
        note = f"{ccy} 3M: {col} (yields.csv), previous month"
        if lagged.isna().any() and flat is not None:
            lagged = lagged.fillna(flat / 12)
            note += f"; flat {flat:.2%} where the series is missing"
        return lagged, A.NO_SERIES_NOTE.get(ccy, note) if ccy in ("HKD", "INR") else note


def windows(r, start=IS_START, end=None):
    end = end or r.index.max()
    return r[(r.index >= pd.Timestamp(start)) & (r.index <= pd.Timestamp(end))]


def split(r, last):
    return {"in_sample": windows(r, IS_START, IS_END), "out_of_sample": windows(r, OOS_START, last),
            "full": windows(r, IS_START, last)}


# ======================================================================== currency
def forward_premium(us_rate_m, loc_rate_m):
    """Monthly CIP forward premium of USD vs local, from monthly (rate/12) returns."""
    return (1 + us_rate_m) / (1 + loc_rate_m) - 1


def hedged_returns(usd, fx, us_rate_m, loc_rate_m, cost=A.FX_FORWARD_COST_PER_ROLL):
    """Monthly USD return with the FX exposure sold forward each month (module docstring)."""
    fp = forward_premium(us_rate_m, loc_rate_m)
    return usd + fp - fx - cost, fp


def currency_block(loc, usd, fx, us_rf, loc_rf, ccy):
    """OOS annualised local / FX / USD split, CIP hedge and FX variance share."""
    df = pd.concat({"l": loc, "u": usd, "f": fx, "us": us_rf, "lr": loc_rf}, axis=1).dropna()
    if len(df) < 12:
        return {k: None for k in ("local_return", "fx_return", "usd_return", "hedged_return",
                                  "hedge_cost", "fx_vol_share")}
    lr, fr, ur = cagr(df["l"]), cagr(df["f"]), cagr(df["u"])
    if ccy == "USD":
        hedged, fp = df["u"], pd.Series(0.0, index=df.index)
        cost = 0.0
    else:
        hedged, fp = hedged_returns(df["u"], df["f"], df["us"], df["lr"])
        cost = A.FX_FORWARD_COST_PER_ROLL
    var_u = df["u"].var()
    share = (df["f"].var() + 2 * df[["l", "f"]].cov().iloc[0, 1]) / var_u if var_u > 0 else np.nan
    return {"local_return": lr, "fx_return": fr, "usd_return": ur,
            "hedged_return": cagr(hedged), "hedge_cost": float(12 * (cost - fp).mean()),
            "fx_vol_share": float(share), "hedged_minus_unhedged": cagr(hedged) - ur,
            "hedged_vol": float(hedged.std() * np.sqrt(12)), "unhedged_vol": float(df["u"].std() * np.sqrt(12)),
            "months": len(df), "start": str(df.index[0].date()), "end": str(df.index[-1].date()),
            "identity_check": (1 + lr) * (1 + fr) - 1 - ur,
            "formula": "usd = (1+local)(1+fx)-1; hedged_t = u_t + fp_t - f_t - 0.0005, "
                       "fp_t = (1+US_3M_{t-1}/12)/(1+loc_3M_{t-1}/12)-1; hedge_cost = 12*mean(0.0005 - fp_t); "
                       "fx_vol_share = (Var(f)+2Cov(l,f))/Var(u), monthly"}


# ======================================================================== stress
def window_return(r, start, end):
    """Compounded return over months after `start` up to `end` (month ends); None if any month is missing."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    n = len(pd.date_range(s, e, freq="ME")) - 1
    w = r[(r.index > s) & (r.index <= e)].dropna()
    if len(w) < n or n <= 0:
        return None
    return float((1 + w).prod() - 1)


def strong_usd_months(usd_broad, threshold=0.02):
    chg = usd_broad.pct_change()
    return chg[chg >= threshold].index


def stress_block(usd, bench, usd_broad):
    out = {}
    for k, (s, e) in STRESS.items():
        out[k] = {"start": s, "end": e, "return": window_return(usd, s, e),
                  "benchmark": window_return(bench, s, e)}
    months = strong_usd_months(usd_broad)
    both = pd.concat([usd, bench], axis=1).reindex(months).dropna()
    out["strong_usd"] = {
        "definition": "months when the FRED broad dollar index (USD_BROAD, monthly average) rose >= 2% "
                      "month on month; plus the 2014-06..2015-03 and 2021-06..2022-09 episodes",
        "avg_return": float(both.iloc[:, 0].mean()) if len(both) else None,
        "benchmark": float(both.iloc[:, 1].mean()) if len(both) else None,
        "n_months": int(len(both)), "months": [str(d.date())[:7] for d in both.index],
    }
    for k, (s, e) in USD_EPISODES.items():
        out["strong_usd"][k] = {"start": s, "end": e, "return": window_return(usd, s, e),
                                "benchmark": window_return(bench, s, e)}
    return out


# ======================================================================== adapters to research/
def make_stock(row, home_index):
    """research.config.Stock from a universe row (key = candidate ID)."""
    return Stock(key=cid(row["ticker"]), name=row["name"], ticker=row["ticker"], currency=row["currency"],
                 country=row["country"], local_index=home_index or "", usd_ticker=row.get("usd_ticker") or "")


class CandidateDataset(Dataset):
    """research.data.Dataset over the wide CSVs for stocks that are not in research.config.STOCKS.

    Only `stock_returns` is overridden (the base looks up config.STOCKS_BY_KEY);
    everything the models read (monthly prices, FX, yields, fundamentals) is the
    base class's own code.
    """

    def __init__(self, prices, fx, yields, fundamentals, stocks):
        super().__init__(prices, fx, yields, fundamentals)
        self.stocks = {s.key: s for s in stocks}

    def stock_returns(self, key):
        s = self.stocks[key]
        p = self.monthly_prices()[s.ticker].dropna()
        local = p.pct_change().dropna()
        fx = self.monthly_fx()[s.currency].reindex(p.index).ffill()
        usd = (p * fx).pct_change().dropna()
        return local, usd


def build_dataset(inp, stocks, with_fundamentals=True):
    """Dataset truncated to the last complete month (betas use complete months only)."""
    cols = sorted({s.ticker for s in stocks} | {s.local_index for s in stocks if s.local_index} | {"ACWI"})
    cols = [c for c in cols if c in inp.prices.columns]
    prices = inp.prices[cols].loc[:inp.last_month]
    fund = {s.ticker: load_fundamentals(s.ticker) for s in stocks} if with_fundamentals else {}
    return CandidateDataset(prices, inp.fx.drop(columns=["USD"], errors="ignore"), inp.yields, fund, stocks)


def expected_returns(inp, ticker, usd_full):
    """Forward 7-year expected returns from the research/ models (USD and local)."""
    a, dcs, gks, mcs = A.market_assumptions(), A.dcf_settings(), A.gk_settings(), A.mc_settings()
    row = inp.row(ticker)
    stock = make_stock(row, inp.home_index(ticker))
    ds = build_dataset(inp, [stock])
    notes = []
    c = capm.estimate(stock, ds, a)
    methods_local, methods_usd = {"capm_local": c["expected_local"]}, {"capm_local": c["expected_usd"]}
    methods_usd["capm_global"] = c["expected_usd_global_capm"]
    methods_local["capm_global"] = (1 + c["expected_usd_global_capm"]) / (1 + fxview.expected_fx(stock.currency, ds, a)) - 1
    d = None
    if stock.key in A.DCF_NOT_APPLICABLE:
        notes.append(f"DCF not applied: {A.DCF_NOT_APPLICABLE[stock.key]} (free cash flow not meaningful)")
    else:
        d = dcf.run(stock, ds, a, c["cost_of_equity"], mc=mcs, s=dcs)
        if d is None or "expected_local" not in d:
            notes.append("DCF: " + (d or {}).get("note", "no usable inputs"))
            d = None
        else:
            methods_local["dcf"], methods_usd["dcf"] = d["expected_local"], d["expected_usd"]
    g = grinold_kroner.run(stock, ds, a, s=gks, dcf_settings=dcs)
    methods_local["grinold_kroner"], methods_usd["grinold_kroner"] = g["expected_local"], g["expected_usd"]
    vals = [v for v in methods_usd.values() if v is not None and np.isfinite(v)]
    cons_usd = float(np.median(vals))
    fx_ppp = fxview.expected_fx(stock.currency, ds, a, "ppp")
    cons_local = (1 + cons_usd) / (1 + fx_ppp) - 1
    views = fxview.all_views(stock.currency, ds, a)
    sens = {v: (1 + cons_local) * (1 + fx) - 1 for v, fx in views.items()}
    hist = usd_full.dropna().to_frame(stock.key)
    fwd = montecarlo.simulate(hist, mcs, targets={stock.key: cons_usd})[stock.key]
    his = montecarlo.simulate(hist, mcs)[stock.key]
    command = f"python -m research.candidates.intl_growth --ticker {ticker}"
    return {
        "methods": {"capm": methods_usd["capm_global"], "capm_local": methods_usd["capm_local"],
                    "dcf": methods_usd.get("dcf"), "grinold_kroner": methods_usd["grinold_kroner"],
                    "yield": None, "monte_carlo_median": fwd["annualised"]["50"]},
        "methods_local": methods_local,
        "consensus_usd": cons_usd, "consensus_local": cons_local,
        "consensus_rule": "median of the USD estimates of CAPM local (via PPP), CAPM global, DCF implied "
                          "return and Grinold-Kroner; the Monte Carlo is then run with its drift scaled to "
                          "this consensus, so its median is not an independent vote",
        "fx_views": views, "consensus_usd_by_fx_view": sens,
        "range_5_95": [fwd["annualised"]["5"], fwd["annualised"]["95"]],
        "monte_carlo": {"forward": {k: fwd[k] for k in ("annualised", "prob_loss_5y", "terminal_100k")},
                        "historical_median": his["annualised"]["50"],
                        "note": "7-year block bootstrap (6-month blocks, 20,000 paths, seed 622) of monthly USD "
                                "returns 2010-01..last month; 'prob_loss_5y' key is the 7-year loss probability "
                                "(montecarlo.py names it for its 5-year default)"},
        "capm": {k: c[k] for k in ("beta_local_raw", "beta_global_raw", "beta_local", "beta_global", "rf_local", "crp")},
        "dcf_detail": None if d is None else {k: d.get(k) for k in (
            "g0", "g_source", "g_terminal", "wacc", "fcf_conversion", "upside", "mc_implied_return",
            "terminal_share_of_value", "base_source")},
        "gk_detail": g,
        "notes": notes,
        "assumptions": "research/candidates/assumptions_intl_growth.py::IntlMarketAssumptions (extends "
                       "research/config.py::MarketAssumptions), TARGET_PE, DCFSettings(cyclical_mid_cycle), "
                       "GKSettings, MonteCarloSettings(horizon_years=7); FX: fxview PPP base case, UIP and "
                       "trend shown as sensitivities",
        "assumption_values": {"mature_erp": a.mature_erp, "crp": a.country_risk_premium.get(stock.country),
                              "risk_free_local": a.risk_free.get(stock.currency), "risk_free_usd": a.risk_free["USD"],
                              "inflation_local": a.inflation.get(stock.currency), "inflation_usd": a.inflation["USD"],
                              "real_gdp": a.long_run_real_gdp.get(stock.country),
                              "target_pe": A.TARGET_PE.get(stock.key)},
        "command": command,
    }


# ======================================================================== fundamentals
FINANCIALS = {"1299.HK", "BAJFINANCE.NS"}


def fundamentals_now(inp, ticker):
    """Section 5 measures at the latest data: EDGAR point-in-time where a filing exists, else
    current yfinance statements (flagged)."""
    row = inp.row(ticker)
    table, splits, src = None, None, "yfinance current statements (fundamentals not point-in-time)"
    path = ed.edgar_path(inp.data_dir / "edgar", row.get("edgar_cik"))
    if path is not None:
        cj = ed.read_companyfacts(path)
        if cj is not None:
            t = ed.point_in_time(ed.edgar_facts(cj), pd.Timestamp.today().normalize())
            if not t.empty and t["revenue"].notna().any():
                table, splits, src = t, ed.split_events(cj), f"SEC EDGAR point-in-time ({path.name})"
    if table is None:
        info = load_fundamentals(ticker).get("info", {})   # yfinance books are in financialCurrency
        table = ed.yfinance_table(inp.data_dir / "fundamentals" / ticker,
                                  info.get("financialCurrency") or row["currency"])
    if table is None:
        return {"source": "none", "measures": {}, "flags": ["no fundamentals on disk"]}
    rep = table.attrs.get("currency") or row["currency"]
    fxr = 1.0
    if rep != row["currency"] and rep in inp.fx and row["currency"] in inp.fx:
        fxr = float(inp.fx[row["currency"]].dropna().iloc[-1] / inp.fx[rep].dropna().iloc[-1])
    divs = read_dividends(inp.data_dir / "fundamentals" / ticker / "dividends.csv")
    m, flags = stock_measures(table, inp.prices[ticker], table.attrs.get("as_of", "2026-11-06")
                              if table.attrs.get("point_in_time") else inp.prices.index[-1],
                              financial=ticker in FINANCIALS, splits=splits, dividends=divs, fx_to_reporting=fxr)
    t = table[table["revenue"].notna()]
    hist = {str(e.date()): {"revenue": _f(r["revenue"]), "net_income": _f(r["net_income"]),
                            "operating_income": _f(r["operating_income"])} for e, r in t.tail(4).iterrows()}
    return {"source": src, "reporting_currency": rep, "measures": m, "flags": flags, "history": hist}


def traded_value(inp, ticker, as_of, days=252):
    """Average daily traded value, USD millions (Yahoo volume x adjusted USD close)."""
    if inp.volumes is None or ticker not in inp.volumes or ticker not in inp.daily_usd:
        return None
    v = (inp.volumes[ticker] * inp.daily_usd[ticker]).dropna().loc[:as_of].tail(days)
    return float(v.mean() / 1e6) if len(v) > 20 else None


# ======================================================================== one candidate
def analyse(inp, ticker):
    row = inp.row(ticker)
    loc, usd, fx = inp.series(ticker)
    ccy = row["currency"]
    hix = inp.home_index(ticker)
    home = inp.m_local[hix] if hix else None
    last = inp.last_month
    full_idx = windows(usd, IS_START, last).index
    rf_loc, rf_note = inp.short_rate(ccy, full_idx)
    us_rf, _ = inp.short_rate("USD", full_idx)
    S_u, S_l = split(usd, last), split(loc, last)
    metrics = {}
    for w in ("in_sample", "out_of_sample", "full"):
        metrics[w] = {"usd": metrics_block(S_u[w], inp.bench, inp.bil, n_trials=N_TRIALS),
                      "local": metrics_block(S_l[w], home, rf_loc, n_trials=N_TRIALS)}
    u_full = S_u["full"]
    rs, ri = rolling_sharpe(u_full, inp.bil), rolling_ir(u_full, inp.bench)
    both = pd.concat([rs, ri], axis=1, keys=["s", "i"]).dropna()
    oos_ir = both.loc[both.index >= OOS_START, "i"]
    rolling = {"dates": [str(d.date()) for d in both.index], "sharpe": both["s"].tolist(),
               "info_ratio": both["i"].tolist(),
               "share_ir_positive_oos": float((oos_ir > 0).mean()) if len(oos_ir) else None,
               "share_ir_positive_full": float((both["i"] > 0).mean()) if len(both) else None,
               "window_months": 36}
    oos = lambda s: windows(s, OOS_START, last)
    cur = currency_block(oos(loc), oos(usd), oos(fx), oos(us_rf), oos(rf_loc), ccy)
    cur_is = currency_block(windows(loc, IS_START, IS_END), windows(usd, IS_START, IS_END),
                            windows(fx, IS_START, IS_END), windows(us_rf, IS_START, IS_END),
                            windows(rf_loc, IS_START, IS_END), ccy)
    # ADR cross-check (full sample and OOS only)
    rows1 = inp.universe[inp.universe["ticker"] == ticker]
    xc_full = usd_crosscheck(inp.daily_usd, inp.usd_listing, rows1).iloc[0]
    xc_oos = usd_crosscheck(inp.daily_usd.loc[OOS_START:], inp.usd_listing.loc[OOS_START:], rows1).iloc[0]
    adr = None
    if xc_full["adr_months"]:
        adr = {"usd_ticker": xc_full["usd_ticker"], "months": int(xc_full["adr_months"]),
               "corr": xc_full["adr_corr"], "ann_diff_local_minus_adr": xc_full["adr_ann_diff"],
               "oos_months": int(xc_oos["adr_months"]), "oos_corr": xc_oos["adr_corr"],
               "oos_ann_diff": xc_oos["adr_ann_diff"]}
    er = expected_returns(inp, ticker, u_full)
    stress = stress_block(usd, inp.bench, inp.usd_broad)
    srow = inp.scored.set_index("ticker").loc[ticker]
    irow = inp.insample.set_index("ticker").loc[ticker]
    fund = fundamentals_now(inp, ticker)
    tv_now, tv_2017 = traded_value(inp, ticker, last), traded_value(inp, ticker, IS_END)
    bm = {"EFG_EEM_5050": {w: metrics_block(split(inp.bench, last)[w], None, inp.bil, n_trials=1)
                           for w in ("in_sample", "out_of_sample")},
          "ACWX": {w: metrics_block(split(inp.acwx, last)[w], None, inp.bil, n_trials=1)
                   for w in ("in_sample", "out_of_sample")},
          "vs_ACWX_usd_oos": metrics_block(S_u["out_of_sample"], inp.acwx, inp.bil, n_trials=N_TRIALS),
          "home_index_local": {"ticker": hix, **{w: metrics_block(split(home, last)[w], None, rf_loc, 1)
                                                 for w in ("in_sample", "out_of_sample")}} if hix else None}
    p = inp.prices[ticker].dropna()
    all_m = usd.dropna()
    notes = [rf_note,
             "home index is a Yahoo price index (no dividends): local IR/alpha are flattered by about its dividend yield"]
    if ticker == "NOVO-B.CO":
        notes.append("home index proxy: Euro Stoxx 50 (^STOXX50E) converted to DKK; no OMX Copenhagen series on disk; "
                     "doubled prices on a few 2005-2006 holidays lie before the 2010 window")
    if ticker == "1299.HK":
        notes.append("listed 2010-10-29: in-sample has 86 months; GFC stress not available")
    if ticker == "000660.KS":
        notes.append("no US listing; Korean won FX from fx.csv")
    if adr:
        notes.append(f"ADR cross-check vs {adr['usd_ticker']}: corr {adr['corr']:.3f} over {adr['months']} months, "
                     f"mean difference {adr['ann_diff_local_minus_adr']:+.2%}/yr (local in USD minus ADR); "
                     f"OOS corr {adr['oos_corr']:.3f}, diff {adr['oos_ann_diff']:+.2%}/yr")
    else:
        notes.append("no ADR/US listing on disk to cross-check the USD series")
    notes += fund["flags"][:4]
    notes.append(f"fundamentals: {fund['source']}")
    if tv_now is not None:
        notes.append(f"traded value (Yahoo volume x USD adj. close): {tv_now:,.0f}M USD/day last 252 days; "
                     f"{tv_2017:,.0f}M at 2017-12-31" if tv_2017 else f"traded value {tv_now:,.0f}M USD/day")
    rid = cid(ticker)
    res = {
        "schema_version": 1, "id": rid, "ticker": ticker,
        "usd_ticker": row["usd_ticker"] or None, "name": row["name"], "position_type": TYPE,
        # results_schema.md uses "currency" twice (the ISO code, then the FX block); in JSON the last
        # key wins, so "currency" holds the block and the ISO code is kept as "currency_code".
        "instrument": "stock", "country": row["country"], "currency_code": ccy, "sector": SECTOR.get(ticker),
        "non_us": True, "benchmark": BENCH,
        "data": {"price_start": str(p.index[0].date()), "price_end": str(p.index[-1].date()),
                 "months_total": int(len(all_m)), "months_in_sample": metrics["in_sample"]["usd"]["months"],
                 "months_out_of_sample": metrics["out_of_sample"]["usd"]["months"],
                 "sources": ["data/research/prices.csv", "data/research/fx.csv", "data/research/yields.csv",
                             "data/research/prices_usd_listing.csv", "data/research/volumes.csv",
                             f"data/research/fundamentals/{ticker}/"] +
                            ([f"data/research/edgar/{Path(fund['source'].split('(')[-1].rstrip(')')).name}"]
                             if fund["source"].startswith("SEC") else []),
                 "fund_fee": None, "home_index": hix, "adr_crosscheck": adr,
                 "traded_value_usd_m": {"last_252d": tv_now, "at_2017_12_31": tv_2017},
                 "notes": "; ".join(n for n in notes if n)},
        "metrics": metrics,
        "benchmark_metrics": bm,
        "rolling": rolling,
        "currency": cur, "currency_in_sample": cur_is,
        "expected_return_7y": er,
        "stress": stress,
        "screens": {"fundamental_score": srow["fundamental_score"],
                    "technical_score": srow["technical_score"] if pd.notna(srow["technical_score"]) else None,
                    "hard_screens_passed": bool(srow["passed"]),
                    "detail": {k: (srow[k] if not isinstance(srow[k], float) or pd.notna(srow[k]) else None)
                               for k in ("rev_cagr_3y", "ni_cagr_3y", "roic_or_roe", "op_margin",
                                         "op_margin_chg_3y", "net_debt_ebitda", "fcf_yield", "pe_now",
                                         "pe_rel_5y", "fundamentals_pit", "T1", "T2", "T3", "T4", "T5",
                                         "technical_note", "flags", "as_of")},
                    "insample_rank": int(irow["rank"]), "composite": irow["composite"],
                    "source": f"research/plan/longlists/{TYPE}_scored.csv, {TYPE}_insample_table.csv"},
        "fundamentals_latest": fund,
        "rubric": {"scores": {}, "total": None, "rank_in_type": None},
        "review": None,
        "explain": [],
        "memo": f"research/candidates/memos/{rid}.md",
        "charts": {"growth": f"reports/candidates/charts/{rid}_growth.png",
                   "rolling": f"reports/candidates/charts/{rid}_rolling.png"},
        "reproduce": f"python -m research.candidates.intl_growth --ticker {ticker} --write",
    }
    res["drop_rule_2"] = drop_rule(res)
    res["explain"] = explain(res)
    return _clean(res), {"usd": usd, "local": loc, "home": home, "rolling": both}


def drop_rule(res):
    """method.md section 8 rule 2: OOS Sharpe below the benchmark's AND OOS IR below zero."""
    m = res["metrics"]["out_of_sample"]["usd"]
    b = res["benchmark_metrics"]["EFG_EEM_5050"]["out_of_sample"]
    hit = (m.get("sharpe") is not None and b.get("sharpe") is not None and m["sharpe"] < b["sharpe"]
           and m.get("info_ratio") is not None and m["info_ratio"] < 0)
    return {"triggered": bool(hit), "oos_sharpe": m.get("sharpe"), "benchmark_oos_sharpe": b.get("sharpe"),
            "oos_ir": m.get("info_ratio")}


def explain(res):
    m = res["metrics"]["out_of_sample"]["usd"]
    b = res["benchmark_metrics"]["EFG_EEM_5050"]["out_of_sample"]
    c, e = res["currency"], res["expected_return_7y"]
    name = SHORT.get(res["ticker"], res["name"])
    s1 = (f"Since 2018 {name} returned {m['cagr']:.1%} a year in dollars with a worst fall of "
          f"{m['max_drawdown']:.0%}, against {b['cagr']:.1%} a year for the international-growth benchmark "
          f"(risk-adjusted: Sharpe {m['sharpe']:.2f} vs {b['sharpe']:.2f}).")
    fxw = "cost" if c["fx_return"] < 0 else "added"
    s2 = (f"The {res['currency_code']} {fxw} {abs(c['fx_return']):.1%} a year against the dollar, so the "
          f"local-currency return was {c['local_return']:.1%}; hedging the currency each month would have "
          f"{'raised' if c['hedged_minus_unhedged'] > 0 else 'lowered'} the dollar return by "
          f"{abs(c['hedged_minus_unhedged']):.1%} a year.")
    s3 = (f"Looking forward, the middle of our model estimates is about {e['consensus_usd']:.0%} a year in dollars over 7 years, "
          f"with a wide 5-95% range of {e['range_5_95'][0]:.0%} to {e['range_5_95'][1]:.0%} a year.")
    return [s1, s2, s3]


# ======================================================================== control group
def control_table(inp):
    rows = []
    sl = inp.insample.set_index("ticker")
    last = inp.last_month
    for t in inp.passed:
        if t not in inp.m_local and t not in inp.m_usd:
            rows.append({"ticker": t, "note": "no price data"})
            continue
        loc, usd, fx = inp.series(t)
        S = split(usd, last)
        mi = metrics_block(S["in_sample"], inp.bench, inp.bil, n_trials=N_TRIALS)
        mo = metrics_block(S["out_of_sample"], inp.bench, inp.bil, n_trials=N_TRIALS)
        lo, fo = windows(loc, OOS_START, last), windows(fx, OOS_START, last)
        r = inp.row(t) if t in inp.rows.index else {}
        rows.append({
            "ticker": t, "name": r.get("name", ""), "role": sl.loc[t, "role"], "country": r.get("country", ""),
            "currency": r.get("currency", ""), "shortlisted": t in CANDIDATES,
            "insample_rank": int(sl.loc[t, "rank"]), "composite_is": sl.loc[t, "composite"],
            "fundamental_score": sl.loc[t, "fundamental_score"],
            "sharpe_is": mi.get("sharpe"), "ir_is": mi.get("info_ratio"), "maxdd_is": mi.get("max_drawdown"),
            "cagr_is": mi.get("cagr"), "months_is": mi.get("months"),
            "sharpe_oos": mo.get("sharpe"), "ir_oos": mo.get("info_ratio"), "t_ir_oos": mo.get("t_stat_ir"),
            "t_alpha_oos": mo.get("t_stat_alpha"), "maxdd_oos": mo.get("max_drawdown"), "cagr_oos": mo.get("cagr"),
            "deflated_sharpe_oos": mo.get("deflated_sharpe"), "months_oos": mo.get("months"),
            "local_return_oos": cagr(lo), "fx_return_oos": cagr(fo),
        })
    df = pd.DataFrame(rows).sort_values("insample_rank")
    df["oos_sharpe_rank"] = df["sharpe_oos"].rank(ascending=False, method="min")
    test = is_oos_rank_test(df.set_index("ticker")["composite_is"], df.set_index("ticker")["sharpe_oos"])
    test_sh = is_oos_rank_test(df.set_index("ticker")["sharpe_is"], df.set_index("ticker")["sharpe_oos"])
    test_ir = is_oos_rank_test(df.set_index("ticker")["composite_is"], df.set_index("ticker")["ir_oos"])
    bm = metrics_block(windows(inp.bench, OOS_START, last), None, inp.bil, 1)
    summary = {"rank_test_composite_vs_oos_sharpe": test, "rank_test_is_sharpe_vs_oos_sharpe": test_sh,
               "rank_test_composite_vs_oos_ir": test_ir, "n_trials": N_TRIALS,
               "benchmark_oos": {"id": BENCH, "sharpe": bm.get("sharpe"), "cagr": bm.get("cagr"),
                                 "max_drawdown": bm.get("max_drawdown")},
               "faded_leaders": df[df["role"] == "faded_leader"][["ticker", "insample_rank", "sharpe_is",
                                                                   "sharpe_oos", "ir_oos", "maxdd_oos"]]
               .to_dict("records"),
               "best_not_shortlisted_by_oos_sharpe": df[~df["shortlisted"]].nlargest(5, "sharpe_oos")[
                   ["ticker", "insample_rank", "sharpe_oos", "ir_oos", "t_ir_oos", "deflated_sharpe_oos"]]
               .to_dict("records"),
               "window": {"in_sample": [IS_START, IS_END], "out_of_sample": [OOS_START, str(last.date())]},
               "command": "python -m research.candidates.intl_growth --all --write"}
    return df, _clean(summary)


# ======================================================================== charts
C_STOCK, C_BENCH, C_ALT, C_SHADE, C_INK, C_MUTED = "#2a78d6", "#8a8984", "#eb6834", "#efeee9", "#0b0b0b", "#52514e"


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=10, color=C_INK)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c9c8c2")
    ax.tick_params(colors=C_MUTED, labelsize=8)
    ax.grid(axis="y", color="#e6e5df", linewidth=0.6)
    ax.axvspan(pd.Timestamp(IS_START), pd.Timestamp(IS_END), color=C_SHADE, zorder=0)


def _growth(r, start=IS_START):
    r = windows(r, start).dropna()
    lvl = 10_000 * (1 + r).cumprod()
    first = r.index[0] - pd.offsets.MonthEnd(1)
    return pd.concat([pd.Series([10_000.0], index=[first]), lvl])


def charts(res, ser, inp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, NullFormatter

    CHARTS.mkdir(parents=True, exist_ok=True)
    rid, name = res["id"], res["name"]
    start = max(pd.Timestamp(IS_START), ser["usd"].dropna().index[0])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=False)
    money = FuncFormatter(lambda v, _: f"${v/1000:,.0f}k")
    ax = axes[0]
    _style(ax, "USD: growth of $10,000 (log scale)")
    for s, lab, col, lw in ((ser["usd"], res["ticker"], C_STOCK, 2.0),
                            (inp.bench, "EFG/EEM 50/50", C_BENCH, 1.6), (inp.acwx, "ACWX", C_ALT, 1.2)):
        g = _growth(s, start)
        ax.plot(g.index, g.values, color=col, lw=lw, label=f"{lab}: ${g.iloc[-1]/1000:,.0f}k")
    ax.set_yscale("log"); ax.yaxis.set_major_formatter(money); ax.yaxis.set_minor_formatter(NullFormatter())
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax = axes[1]
    _style(ax, f"Local currency ({res['currency_code']}) vs home index (price index)")
    g = _growth(ser["local"], start)
    ax.plot(g.index, g.values, color=C_STOCK, lw=2.0,
            label=f"{res['ticker']} ({res['currency_code']}): {g.iloc[-1]/1000:,.0f}k")
    if ser["home"] is not None:
        h = _growth(ser["home"], start)
        ax.plot(h.index, h.values, color=C_BENCH, lw=1.6, label=f"{res['data']['home_index']}: {h.iloc[-1]/1000:,.0f}k")
    ax.set_yscale("log"); ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v/1000:,.0f}k"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle(f"{name}: shaded = in-sample 2010-2017, unshaded = out-of-sample (local index is a price index)", x=0.01, ha="left",
                 fontsize=11, color=C_INK)
    fig.tight_layout()
    fig.savefig(ROOT / res["charts"]["growth"], dpi=130)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    roll = ser["rolling"]
    bsh = rolling_sharpe(windows(inp.bench, IS_START), inp.bil)
    ax = axes[0]
    _style(ax, "Rolling 36-month Sharpe (USD, vs BIL)")
    ax.plot(roll.index, roll["s"], color=C_STOCK, lw=2.0, label=res["ticker"])
    ax.plot(bsh.index, bsh.values, color=C_BENCH, lw=1.6, label="EFG/EEM 50/50")
    ax.axhline(0, color="#9b9a95", lw=0.8)
    ax.legend(frameon=False, fontsize=8)
    ax = axes[1]
    _style(ax, "Rolling 36-month information ratio vs EFG/EEM 50/50")
    ax.plot(roll.index, roll["i"], color=C_STOCK, lw=2.0)
    ax.axhline(0, color="#9b9a95", lw=0.8)
    fig.tight_layout()
    fig.savefig(ROOT / res["charts"]["rolling"], dpi=130)
    plt.close(fig)


# ======================================================================== memo
def _pct(x, d=1):
    return "n/a" if x is None else f"{x:.{d}%}"


def _num(x, d=2):
    return "n/a" if x is None else f"{x:.{d}f}"


def memo(res):
    t = TEXT.get(res["ticker"], TEXT_DEFAULT)
    mi, mo = res["metrics"]["in_sample"]["usd"], res["metrics"]["out_of_sample"]["usd"]
    li, lo = res["metrics"]["in_sample"]["local"], res["metrics"]["out_of_sample"]["local"]
    b = res["benchmark_metrics"]["EFG_EEM_5050"]
    c, e, st = res["currency"], res["expected_return_7y"], res["stress"]
    f = res["fundamentals_latest"]
    fm = f.get("measures", {})
    pit = "point-in-time: values as filed" if f["source"].startswith("SEC") else "**flagged**"
    meth = e["methods"]
    sens = e["consensus_usd_by_fx_view"]
    dr = res["drop_rule_2"]
    lines = [
        f"# {res['name']} ({res['ticker']}) - international growth candidate",
        "",
        f"Country {res['country']}, currency {res['currency_code']}, sector {res['sector']}. Benchmark EFG/EEM 50/50 "
        f"(USD), home index {res['data']['home_index']} (local). Numbers from `{res['reproduce']}`; "
        f"JSON `reports/candidates/{res['id']}.json`. In-sample 2010-2017, out-of-sample (OOS) 2018-01 to "
        f"{mo['end'][:7]}.",
        "",
        f"**Thesis.** {t['thesis']}",
        "",
        f"**Return drivers.** {t['drivers']}",
        "",
        "| USD, monthly | In-sample | OOS | Benchmark OOS |",
        "|---|---|---|---|",
        f"| CAGR | {_pct(mi.get('cagr'))} | {_pct(mo.get('cagr'))} | {_pct(b['out_of_sample'].get('cagr'))} |",
        f"| Sharpe vs BIL | {_num(mi.get('sharpe'))} | {_num(mo.get('sharpe'))} | {_num(b['out_of_sample'].get('sharpe'))} |",
        f"| Information ratio (t) | {_num(mi.get('info_ratio'))} ({_num(mi.get('t_stat_ir'), 1)}) | "
        f"{_num(mo.get('info_ratio'))} ({_num(mo.get('t_stat_ir'), 1)}) | - |",
        f"| Alpha (t) | {_pct(mi.get('alpha'))} ({_num(mi.get('t_stat_alpha'), 1)}) | {_pct(mo.get('alpha'))} "
        f"({_num(mo.get('t_stat_alpha'), 1)}) | - |",
        f"| Max drawdown | {_pct(mi.get('max_drawdown'), 0)} | {_pct(mo.get('max_drawdown'), 0)} | "
        f"{_pct(b['out_of_sample'].get('max_drawdown'), 0)} |",
        f"| Deflated Sharpe (N=31) | {_num(mi.get('deflated_sharpe'))} | {_num(mo.get('deflated_sharpe'))} | - |",
        f"| Local: Sharpe / IR vs home index | {_num(li.get('sharpe'))} / {_num(li.get('info_ratio'))} | "
        f"{_num(lo.get('sharpe'))} / {_num(lo.get('info_ratio'))} | - |",
        "",
        f"Method s8 drop rule 2 (OOS Sharpe below benchmark and OOS IR < 0): "
        f"**{'triggered' if dr['triggered'] else 'not triggered'}**.",
        "",
        f"**Fundamentals** ({f['source']}; {pit}). Latest fiscal year {fm.get('fy_end', 'n/a')}: "
        f"3-year revenue CAGR {_pct(fm.get('rev_cagr_3y'))}, net-income CAGR {_pct(fm.get('ni_cagr_3y'))}, "
        f"operating margin {_pct(fm.get('op_margin'))}, {'ROE' if res['ticker'] in FINANCIALS else 'ROIC'} "
        f"{_pct(fm.get('roic_or_roe'))}, FCF yield {_pct(fm.get('fcf_yield'))}, trailing P/E "
        f"{_num(fm.get('pe_now'), 1)} ({_num(fm.get('pe_rel_5y'))}x its 5-year median). "
        f"In-sample fundamental score {res['screens']['fundamental_score']:.2f} (rank {res['screens']['insample_rank']} of 31 "
        f"by composite). {t.get('fundamentals', '')}",
        "",
        f"**Currency.** OOS the stock made {_pct(c['local_return'])}/yr in {res['currency_code']}, the currency "
        f"{_pct(c['fx_return'])}/yr, so {_pct(c['usd_return'])}/yr in USD; FX was {_pct(c['fx_vol_share'], 0)} "
        f"of the USD return variance. A monthly CIP hedge (cost {_pct(c['hedge_cost'], 2)}/yr incl. 5 bp per roll) "
        f"would have returned {_pct(c['hedged_return'])}/yr ({c['hedged_minus_unhedged']:+.1%} vs unhedged; "
        f"vol {_pct(c['hedged_vol'], 0)} vs {_pct(c['unhedged_vol'], 0)}). Forward: PPP implies "
        f"{e['fx_views']['ppp']:+.1%}/yr for the {res['currency_code']}, UIP {e['fx_views']['uip']:+.1%}/yr, the "
        f"10-year trend {e['fx_views']['trend']:+.1%}/yr. {t.get('currency', '')}",
        "",
        f"**Expected 7-year return (USD).** CAPM global {_pct(meth['capm'])}, CAPM local via PPP "
        f"{_pct(meth['capm_local'])}, DCF implied {_pct(meth['dcf'])}, Grinold-Kroner {_pct(meth['grinold_kroner'])} "
        f"(target P/E {e['assumption_values']['target_pe']}). Consensus (median) **{_pct(e['consensus_usd'])}** "
        f"USD / {_pct(e['consensus_local'])} local; with UIP FX {_pct(sens['uip'])}, with trend FX "
        f"{_pct(sens['trend'])}. Monte Carlo (drift set to consensus) 5-95%: {_pct(e['range_5_95'][0])} to "
        f"{_pct(e['range_5_95'][1])}/yr; historical-drift median {_pct(e['monte_carlo']['historical_median'])}. "
        + (" ".join(e["notes"]) + "." if e["notes"] else ""),
        "",
        f"**Stress (USD, stock / benchmark).** GFC {_pct(st['gfc_2008']['return'], 0)} / "
        f"{_pct(st['gfc_2008']['benchmark'], 0)}; taper 2013 {_pct(st['taper_2013']['return'], 0)} / "
        f"{_pct(st['taper_2013']['benchmark'], 0)}; Covid {_pct(st['covid_2020']['return'], 0)} / "
        f"{_pct(st['covid_2020']['benchmark'], 0)}; 2022 {_pct(st['inflation_2022']['return'], 0)} / "
        f"{_pct(st['inflation_2022']['benchmark'], 0)}; strong-USD months ({st['strong_usd']['n_months']}) "
        f"{_pct(st['strong_usd']['avg_return'])} / {_pct(st['strong_usd']['benchmark'])} per month; "
        f"2014-15 USD rally {_pct(st['strong_usd']['usd_2014_15']['return'], 0)} / "
        f"{_pct(st['strong_usd']['usd_2014_15']['benchmark'], 0)}; 2021-22 {_pct(st['strong_usd']['usd_2021_22']['return'], 0)} / "
        f"{_pct(st['strong_usd']['usd_2021_22']['benchmark'], 0)}.",
        "",
        "**Technicals.** No technical signal survived the pre-registered OOS test for this type "
        "(research/plan/shortlist.md), so none is used here.",
        "",
        f"**Risks.** {t['risks']}",
        "",
        f"**Verdict.** {t['verdict']}",
        "",
        "> **How to explain this pick.** " + " ".join(res["explain"]),
        "",
        f"Data notes: {res['data']['notes']}.",
        "",
    ]
    MEMOS.mkdir(parents=True, exist_ok=True)
    (ROOT / res["memo"]).write_text("\n".join(lines), encoding="utf-8")


# ======================================================================== narrative
# Qualitative text for the memos, written by the analyst after reading the
# 2026-11-07 run. The memo tables and sentences built in memo() are filled from
# the JSON; the few numbers quoted in a verdict below were copied from that run
# and must be re-read if the data are refreshed.
TEXT_DEFAULT = {"thesis": "", "drivers": "", "risks": "", "verdict": "", "fundamentals": "", "currency": ""}
TEXT = {
    "NOVO-B.CO": {
        "thesis": "The global leader in diabetes and obesity drugs (insulin, semaglutide: Ozempic/Wegovy). "
                  "It was the top in-sample composite; the 2021-2024 GLP-1 boom and the 2024-2026 collapse "
                  "(Lilly's tirzepatide winning share, US pricing pressure, guidance cuts) make it the clearest "
                  "case of a great business whose share price ran ahead of its earnings.",
        "drivers": "Volume growth of GLP-1 drugs, US net pricing, the obesity pipeline (oral and next-generation "
                   "molecules) versus Eli Lilly; a 4% dividend yield and buybacks.",
        "fundamentals": "Margins and ROIC are still those of a top-quartile pharma; the trailing P/E is about a "
                        "third of its 5-year median, so the price, not the business, did most of the falling.",
        "currency": "DKK is pegged to the euro, so the USD result is a EUR/USD exposure; the US-Danish rate gap "
                    "made hedging pay (negative hedge cost) over 2018-2026.",
        "risks": "Single-franchise concentration (GLP-1 is most of growth); US drug-price policy (IRA "
                 "negotiation, most-favoured-nation pricing); semaglutide patent expiry in some markets from "
                 "2026; foundation control (Novo Holdings) limits takeover discipline.",
        "verdict": "Runner-up at best. OOS Sharpe 0.30 with an IR t-stat of 0.5 is not evidence of skill, and "
                   "the -74% drawdown since the 2024 peak is far outside the -25% security budget; the cheap "
                   "valuation (forward about 8% a year in USD) is the only argument for it.",
    },
    "REA.AX": {
        "thesis": "Australia's dominant online property-listings marketplace (realestate.com.au), majority-owned "
                  "by News Corp: a network business with pricing power that grows with listing 'depth' fees "
                  "more than with housing volumes.",
        "drivers": "Annual price rises on premium listings, depth penetration, adjacent mortgage and data "
                   "products; earnings growth in the low teens; expensive multiple.",
        "fundamentals": "49% operating margin, ROIC above 40%, net cash; trailing P/E around 40, below its own "
                        "5-year median.",
        "currency": "The AUD is a risk-on, commodity currency: FX was a quarter of USD variance and fell with "
                    "stocks in 2020 and 2022, which weakens it as a diversifier.",
        "risks": "Australian housing cycle and listing volumes; competition from Domain (now owned by CoStar); "
                 "News Corp control (about 61%); valuation if growth slows; AUD weakness in risk-off episodes.",
        "verdict": "Not recommended. OOS Sharpe 0.34 and IR 0.24 (t 0.7) are barely above the benchmark's 0.27, "
                   "and the Covid drawdown was twice the benchmark's; a high-quality business whose price "
                   "already reflects it (forward about 10% a year in USD).",
    },
    "2330.TW": {
        "thesis": "The world's leading contract chipmaker, making nearly all leading-edge logic chips (Apple, "
                  "Nvidia, AMD, Broadcom); the AI build-out runs through its 3nm/2nm nodes and advanced "
                  "packaging (CoWoS).",
        "drivers": "AI accelerator demand, the technology lead over Samsung and Intel Foundry, pricing power at "
                   "the leading node, capex discipline, rising dividends.",
        "fundamentals": "The latest 20-F on disk is FY2024: 46% operating margin, ROIC about 35%, net cash. The "
                        "trailing P/E on FY2024 EPS overstates today's multiple; Yahoo's forward P/E is 16.",
        "currency": "TWD moved little against the USD (about -1%/yr OOS) but was 18% of USD variance because it "
                    "co-moves with the stock. The hedge result rests on a flat 1.8% TWD rate (no Taiwan short-"
                    "rate series on disk): approximate. The TSM ADR returned about 1.5%/yr more than the local "
                    "line OOS (the ADR premium widened).",
        "risks": "Taiwan Strait geopolitics (the dominant tail risk, absent from every backtest); customer "
                 "concentration (Apple, Nvidia); US tariffs and export controls; the semiconductor cycle "
                 "(2022: -45% in USD).",
        "verdict": "Strongest candidate. OOS Sharpe 0.96 and IR 1.13 with t = 3.4 and deflated Sharpe 0.78 make it "
                   "the only one of the eight whose OOS edge largely survives the multiple-testing haircut; "
                   "forward about 11% a year in USD, and the geopolitical tail argues for sizing, not exclusion.",
    },
    "1299.HK": {
        "thesis": "Pan-Asian life insurer (ex-AIG) selling protection and savings products to the growing "
                  "middle class in Hong Kong, mainland China, Thailand, Singapore and Malaysia.",
        "drivers": "Value-of-new-business growth, mainland visitor sales in Hong Kong, capital return (buybacks: "
                   "share count falling about 3%/yr) and operating ROE.",
        "fundamentals": "Books in USD: ROE about 14%, trailing P/E about 17. A free-cash-flow DCF is not "
                        "meaningful for an insurer, so that method is left out.",
        "currency": "HKD is pegged to the USD: FX was about 1% of USD variance and hedging only adds cost (the "
                    "HKD rate is proxied by US 3M).",
        "risks": "China growth and property exposure in the investment book; mainland visitor flows; rate "
                 "sensitivity of insurance liabilities; Hong Kong political risk; only 86 in-sample months.",
        "verdict": "Do not pick. OOS Sharpe 0.17 is below the benchmark's 0.27 and the IR is zero (t 0.0), "
                   "missing drop rule 2 only because the IR is +0.01; the 16% Grinold-Kroner figure rests on "
                   "buybacks and a re-rating the OOS period did not deliver.",
    },
    "0700.HK": {
        "thesis": "China's largest internet platform: WeChat/Weixin, online games, fintech (WeChat Pay), cloud "
                  "and advertising, plus a large investment portfolio.",
        "drivers": "Games (domestic and overseas), advertising on Video Accounts, payment volumes, cost control "
                   "and buybacks; AI as an option.",
        "fundamentals": "Books in CNY: 33% operating margin, ROIC about 20%, net cash; trailing P/E about 15, below "
                        "its 5-year median.",
        "currency": "Listed in HKD (USD peg): FX was about 1% of USD variance, so for Tencent the currency "
                    "question is really a China-risk question.",
        "risks": "China policy dominates: the 2021 regulatory crackdown (game licences, fintech, data), US "
                 "investment restrictions (Pentagon 1260H list, January 2025), the VIE structure, US-China "
                 "tensions; -69% drawdown in 2021-2022.",
        "verdict": "Drop under the pre-registered rule: OOS Sharpe 0.12 is below the benchmark's 0.27 and the IR "
                   "is -0.01 (method.md section 8, rule 2). The in-sample IR of 1.18 did not carry over; the "
                   "forward models (about 11% a year in USD) say it is cheap, which is a thesis, not evidence.",
    },
    "BAJFINANCE.NS": {
        "thesis": "India's largest retail non-bank lender (consumer durables, personal, SME and mortgage loans): "
                  "a direct play on Indian consumer-credit growth.",
        "drivers": "Loan-book growth of 25%+ a year, net interest margin, credit costs and the Indian equity "
                   "multiple; ROE in the high teens.",
        "fundamentals": "Revenue CAGR 23%, ROE about 17%; free cash flow is negative by construction (loan "
                        "growth), so the DCF is left out.",
        "currency": "The largest FX drag of the eight: Indian rates above US rates make the hedge expensive, "
                    "yet the rupee fell by more than the carry in this window.",
        "risks": "INR depreciation; the credit cycle (the 2018 IL&FS shadow-bank crisis and Covid hit NBFCs "
                 "hardest: -52% in Q1 2020 in USD); RBI regulation (2023 lending curbs); succession; high "
                 "valuation.",
        "verdict": "Possible, not first choice. OOS Sharpe 0.51 and IR 0.43 (t 1.3, deflated Sharpe 0.28) are "
                   "positive but statistically weak, with a -58% drawdown and the worst Covid and taper stress "
                   "of the eight; forward about 11% a year in USD.",
    },
    "000660.KS": {
        "thesis": "The world's number-two memory maker and the leader in high-bandwidth memory (HBM) for Nvidia "
                  "accelerators; the cyclical, value-leaning candidate with the highest in-sample fundamental "
                  "score.",
        "drivers": "DRAM and NAND prices (boom-bust), HBM share, capex discipline across Samsung, SK Hynix and "
                   "Micron. 2026 earnings are at a cyclical peak (forward P/E 2.7).",
        "fundamentals": "49% operating margin and 31% ROIC at the peak. DCF and Grinold-Kroner assume earnings "
                        "fall to 50% of the forward year by year 4 (research/config.py mid-cycle rule), which is "
                        "why G-K gives only about 8.5%.",
        "currency": "The won cost 2.4%/yr OOS; FX was only 5% of USD variance because the stock's own 59% "
                    "volatility swamps it.",
        "risks": "The memory cycle (2008: -77%, 2022: -47% in USD); HBM dependence on one customer (Nvidia); US "
                 "export controls (its Wuxi fabs in China); Korea discount and chaebol governance (SK Group).",
        "verdict": "Strong OOS record (Sharpe 0.73, IR 0.76, t 2.3, deflated Sharpe 0.54) but bought at peak "
                   "earnings, with the widest forward range of the eight and 59% volatility; a small position or "
                   "runner-up, not a core holding for a growth-plus-security client.",
    },
    "CSU.TO": {
        "thesis": "Serial acquirer of small vertical-market software businesses (thousands of niche, mission-"
                  "critical systems for municipalities, utilities, healthcare), compounding by reinvesting free "
                  "cash flow at high returns.",
        "drivers": "Capital deployed in acquisitions and the hurdle rate earned; organic growth low single "
                   "digits; founder Mark Leonard stepped down as president in 2025.",
        "fundamentals": "Books in USD: revenue CAGR 21%. GAAP earnings are depressed by acquisition "
                        "amortisation, so the trailing P/E on last fiscal-year EPS (about 100) overstates the "
                        "multiple; forward P/E 19, FCF yield about 5%.",
        "currency": "CAD cost 1.2%/yr OOS and was 14% of USD variance; the US-Canada rate gap was small, so "
                    "hedging cost almost nothing in carry.",
        "risks": "Capital deployment (larger, lower-return deals), succession after the founder, fear of AI "
                 "disrupting legacy software (the 2025-2026 sell-off, -52% drawdown); revenue is global, so "
                 "Canada-specific risk is low.",
        "verdict": "Good runner-up. OOS Sharpe 0.64 and IR 0.51 (t 1.5, deflated Sharpe 0.43) with the best 2022 "
                   "stress result of the eight, but the 2025-2026 drawdown shows the 'software is safe' "
                   "assumption failing; forward about 9% a year in USD.",
    },
}

# ======================================================================== CLI
def summary_line(res):
    m = res["metrics"]["out_of_sample"]["usd"]
    c, e = res["currency"], res["expected_return_7y"]
    return (f"{res['ticker']:<14} OOS Sharpe {_num(m.get('sharpe'))}  IR {_num(m.get('info_ratio'))} "
            f"(t {_num(m.get('t_stat_ir'), 1)})  maxDD {_pct(m.get('max_drawdown'), 0)}  fx {_pct(c['fx_return'])}  "
            f"hedged-unhedged {c['hedged_minus_unhedged']:+.1%}  E[R]7y USD {_pct(e['consensus_usd'])}  "
            f"DSR {_num(m.get('deflated_sharpe'))}")


def run(tickers, write, control=False):
    inp = Inputs()
    out = []
    for t in tickers:
        res, ser = analyse(inp, t)
        print(summary_line(res))
        if write:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / f"{res['id']}.json").write_text(json.dumps(res, indent=1, allow_nan=False), encoding="utf-8")
            charts(res, ser, inp)
            memo(res)
        out.append(res)
    if control:
        df, summ = control_table(inp)
        t = summ["rank_test_composite_vs_oos_sharpe"]
        print(f"control: Spearman(composite IS, Sharpe OOS) = {t['rho']:.2f} (p {t['p_value']:.2f}, n {t['n']})")
        if write:
            df.to_csv(OUT / "intl_growth_control.csv", index=False, float_format="%.6g")
            (OUT / "intl_growth_control_summary.json").write_text(json.dumps(summ, indent=1, allow_nan=False),
                                                                   encoding="utf-8")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true", help="all eight candidates plus the control table")
    ap.add_argument("--ticker", help="one candidate, e.g. 2330.TW")
    ap.add_argument("--write", action="store_true", help="write JSON, memo, charts (and the control CSV)")
    a = ap.parse_args(argv)
    if a.all:
        run(CANDIDATES, a.write, control=True)
    elif a.ticker:
        if a.ticker not in CANDIDATES:
            ap.error(f"{a.ticker} is not one of the eight: {', '.join(CANDIDATES)}")
        run([a.ticker], a.write)
    else:
        ap.error("pass --all or --ticker")


if __name__ == "__main__":
    main()
