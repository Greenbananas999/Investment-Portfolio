"""Phase 3 candidate analysis: US growth stocks (8 shortlisted names plus the control group).

    python -m research.candidates.us_growth --all --write      # 8 JSONs, memos, charts, control table
    python -m research.candidates.us_growth --ticker META      # one name, printed only
    python -m research.candidates.us_growth --ticker META --write
    python -m research.candidates.us_growth --control --write  # control table only
    python -m research.candidates.us_growth --pe-history       # audit the P/E inputs of the assumptions file

Binding rules: research/plan/method.md sections 1, 2, 3, 7, 9, 11, 12; output
format research/plan/results_schema.md. One script for all eight names so the
numbers are comparable.

- Prices: data/research/prices.csv (Yahoo adjusted close = total return),
  through research.screen.read_wide_csv (spike filter) and usd_prices (USD = 1).
- Monthly returns: calendar month ends, the partial last month dropped. In-sample
  2010-01 to 2017-12, out-of-sample 2018-01 to the last full month, full =
  2010-01 to the last full month. Risk-free = BIL monthly total return.
  Benchmark IVW (S&P 500 Growth); QQQ shown alongside.
- Deflated Sharpe: N = 46 trials (US names that passed the hard screens).
- Forward models: research.capm, research.dcf, research.grinold_kroner and
  research.montecarlo, unchanged, through the thin adapters `make_stock` and
  `make_dataset`. Extra assumptions: research/candidates/assumptions_us_growth.py.
- No trade is modelled here (buy-and-hold monthly returns), so no cost is charged.
- Nothing is downloaded. Missing files raise with the path.
"""

import argparse
import dataclasses
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .. import capm, config, data as rdata, dcf, grinold_kroner, montecarlo
from ..screen import (benchmark_monthly, edgar_facts, is_oos_rank_test, load_universe, metrics_block,
                      monthly_returns, point_in_time, rolling_ir, rolling_sharpe, split_events,
                      stock_measures, usd_prices)
from ..screen.edgar import edgar_path, read_companyfacts
from ..screen.fundamental import _eps_today_units
from ..screen.prices import dividend_factor, read_dividends, read_wide_csv
from .assumptions_us_growth import ASSUMPTIONS, PE_MEDIAN_10Y, TARGET_PE_CAP

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research"
PLAN = ROOT / "research" / "plan"
LONGLISTS = PLAN / "longlists"
REPORTS = ROOT / "reports" / "candidates"
CHARTS = REPORTS / "charts"
MEMOS = ROOT / "research" / "candidates" / "memos"

MODULE = "research.candidates.us_growth"
ASSUMPTIONS_REF = ("research/config.py::MarketAssumptions, DCFSettings, GKSettings, MonteCarloSettings; "
                   "research/candidates/assumptions_us_growth.py::USGrowthAssumptions")
TICKERS = ["AVGO", "META", "AMZN", "REGN", "NVDA", "ADBE", "MA", "GILD"]
FADED = ["BIIB", "SIRI", "ILMN", "CTSH", "AKAM", "EXPE"]
NEAR_MISSES = ["FANG", "ORLY", "LRCX", "SBUX", "AMAT", "MNST", "ODFL"]   # research/plan/shortlist.md
BENCH, ALT_BENCH, RF = "IVW", "QQQ", "BIL"
SUPPORT = [BENCH, ALT_BENCH, RF, "ACWI", "^GSPC"]
N_TRIALS = 46
IS_START, IS_END, OOS_START = "2010-01-01", "2017-12-31", "2018-01-01"
SHORT_HISTORY = 120
ROLL = 36

# method.md section 11: total return from the close of `start` (a month end) to the close of `end`.
STRESS_WINDOWS = {
    "gfc_2008": ("2007-10-31", "2009-02-28"),
    "taper_2013": ("2013-04-30", "2013-08-31"),
    "covid_2020": ("2020-01-31", "2020-03-31"),
    "inflation_2022": ("2021-12-31", "2022-10-31"),
}
USD_EPISODES = {"usd_2014_15": ("2014-06-30", "2015-03-31"), "usd_2021_22": ("2021-06-30", "2022-09-30")}
USD_RISE = 0.02

COLORS = {"stock": "#2a78d6", "IVW": "#eb6834", "QQQ": "#1baf7a", "ink": "#0b0b0b", "ink2": "#52514e",
          "grid": "#e4e3df", "shade": "#f1f0ec"}


# ---------------------------------------------------------------- narrative (analyst judgement)
# Thesis, drivers and risks are qualitative and written by the analyst; every number in the
# memos is filled in by code. Verdicts were written after the out-of-sample run, which is the
# one use of OOS data the method allows (judging candidates); no rule was changed.
NARRATIVE = {
    "AVGO": dict(
        rank=2,
        business="a semiconductor and infrastructure-software company built by acquisition",
        thesis="Broadcom designs custom AI accelerators and networking chips for the largest cloud "
               "companies and sells enterprise infrastructure software (VMware) on multi-year "
               "contracts. It is a consolidator: it buys franchises, cuts cost and pays out the cash.",
        drivers="hyperscaler AI capital spending (custom chips, Ethernet switching), software "
                "subscription renewals, and the pay-out of free cash flow as dividends.",
        risks="concentration in a few AI customers, a capex downturn, acquisition debt, and a "
              "trailing P/E near 60 that already prices the AI ramp. The 2017 fundamentals are not "
              "point-in-time (Singapore-domiciled until 2018; the current CIK starts then): its 2017 "
              "fundamental score was built from current statements, so the 2017 screen was not "
              "data-to-2017 only for this name.",
        verdict="Keep, ranked second: OOS Sharpe 0.98 and IR 0.72 (t 2.2), every 36-month OOS window "
                "with positive IR. Its -32% worst drawdown is close to the index's -30% but still "
                "breaks the -25% security budget, so it too needs a capped weight. Forward consensus "
                "11% (13% without the assumed de-rating from a trailing P/E of 37.5 to 23); its 2017 "
                "screen data could not be checked point-in-time.",
        reason="the second-best in-sample composite (41% a year, Sharpe 1.4 in 2010-2017; its 2017 "
               "fundamentals came from current statements, not data to 2017)",
        clause="it is one of our two core US picks, with the warning that most of its return came from the AI build-out"),
    "META": dict(
        rank=5,
        business="the owner of Facebook, Instagram and WhatsApp",
        thesis="Meta earns almost all its revenue from advertising on its apps; ad ranking is "
               "AI-driven, and it reinvests heavily in AI data centres and in Reality Labs.",
        drivers="digital advertising growth and pricing, cost discipline, and how much of the cash "
                "flow AI capital spending absorbs.",
        risks="sentiment on capex can turn fast (the 2022 window cost 72% against 27% for IVW); "
              "regulation and privacy rules; dependence on advertising. In-sample history is only "
              "67 months (2012 IPO), flagged short.",
        verdict="Runner-up, ranked fifth: OOS IR 0.17 (t 0.5) is positive but not distinguishable "
                "from zero, the OOS Sharpe (0.51) is below IVW's 0.77, and the -75% drawdown alone "
                "breaks the -25% security budget. Forward consensus 10% is mid-pack.",
        reason="the highest fundamental score of the group (52% revenue growth a year, FY2013-FY2016)",
        clause="it is a runner-up: a strong business, but too volatile for the return it added"),
    "AMZN": dict(
        rank=4,
        business="the largest online retailer and a leading cloud provider (AWS)",
        thesis="Amazon combines retail and advertising with AWS, its most profitable segment; growth "
               "now depends on cloud and AI demand and on retail margins (operating margin rose from "
               "3% in FY2016 (the last year filed by end-2017) to 11% in FY2025 on EDGAR figures).",
        drivers="AWS growth and margin, advertising, retail operating margin, and the level of "
                "data-centre capital spending.",
        risks="heavy capex lowering free cash flow, competition in cloud, antitrust, consumer "
              "spending; no dividend. The DCF implied return (6%) is the lowest of the eight.",
        verdict="Runner-up, ranked fourth: it roughly matched the S&P 500 Growth fund out of sample "
                "(alpha 0%, IR 0.19, t 0.6) with a deeper drawdown (-52% vs -30%). Its forward "
                "consensus (8%) is in the bottom three of the eight.",
        reason="a consistent in-sample record (Sharpe 1.1, drawdown -24%)",
        clause="it is a runner-up: a fine company, but no better than holding the growth index"),
    "REGN": dict(
        rank=7,
        business="a biotechnology company (Eylea, Dupixent with Sanofi, Libtayo)",
        thesis="Regeneron earns most of its profit from two franchises, the eye drug Eylea and the "
               "immunology drug Dupixent, and reinvests in a large antibody pipeline. Its returns "
               "follow approvals and patents, not the tech cycle (OOS beta to IVW 0.08).",
        drivers="Dupixent growth, Eylea against biosimilars, pipeline readouts, and buybacks.",
        risks="the Eylea patent cliff, US drug-price negotiation, clinical failures; revenue growth "
              "fell from 32% a year (3 years to FY2016) to 6% (to FY2025). Its DCF rests on a low "
              "CAPM discount rate (beta 0.4) and 81% of value in the terminal value, so it is fragile.",
        verdict="Drop under method.md section 8 rule 2: OOS Sharpe 0.40 below IVW and IR -0.04. "
                "It was a real diversifier (up 44% in the Covid window and 19% in 2022 while IVW "
                "fell), which Phase 5 may still want from a fund, not from this stock.",
        reason="a different return driver from tech with a 41% in-sample return",
        clause="it did not hold up after 2018 and we are not using it"),
    "NVDA": dict(
        rank=1,
        business="the leading maker of AI and graphics processors",
        thesis="Nvidia sells the GPUs, networking and software (CUDA) on which most AI models are "
               "trained and run; revenue went from $6.9bn in FY2017 to $216bn in FY2026 (EDGAR).",
        drivers="AI data-centre spending by cloud companies and governments, product cycles, gross "
                "margin, and export rules on China.",
        risks="a pause in AI capex, custom chips (including Broadcom's) taking share, export "
              "controls, and the highest volatility of the eight (47% a year OOS; -77% in 2008, "
              "-54% in the 2022 window, -63% OOS max drawdown).",
        verdict="Keep, ranked first on the judging metrics: OOS Sharpe 1.11, IR 1.04 (t 3.1), "
                "deflated Sharpe 0.84 (below the 0.95 bar), and a forward consensus of 13%. The evidence is one regime "
                "(the 2023-2026 AI build-out) and the -63% drawdown means it only fits as a small "
                "weight inside the security budget.",
        reason="it was the momentum-leaning candidate with a 35% in-sample return",
        clause="it is one of our two core US picks, held small because it has fallen more than 60% twice"),
    "ADBE": dict(
        rank=8,
        business="the maker of Photoshop, Acrobat and the Creative Cloud",
        thesis="Adobe sells subscription software for creative and document work with high margins "
               "and buybacks; the open question is whether generative AI tools erode its pricing "
               "power or extend it.",
        drivers="Creative Cloud and Document Cloud subscriptions, AI monetisation, margins, buybacks.",
        risks="AI competition lowering the value of creative software and a de-rating already in the "
              "price (trailing P/E 76 at the end of 2017, 14 now; forward P/E 8.7).",
        verdict="Drop under method.md section 8 rule 2: the weakest OOS record of the eight (Sharpe "
                "0.21, IR -0.26, drawdown -69%). Its forward consensus (15%) is the highest because "
                "G-K assumes the trailing P/E recovers from 13.4 to 23 (+5.6 points a year) and the "
                "DCF starts from forward earnings 1.5x trailing; without the re-rating the consensus "
                "is 13%, and the re-rating cannot be tested.",
        reason="a steady software record (Sharpe 1.0 in-sample)",
        clause="it fell far behind after 2018 and we would not hold it"),
    "MA": dict(
        rank=3,
        business="the second-largest card payment network",
        thesis="Mastercard takes a small fee on a large and growing volume of card and digital "
               "payments; it carries no credit risk and converts most of its profit to cash "
               "(operating margin 58% in FY2025, EDGAR).",
        drivers="payment volume, cross-border travel, value-added services, pricing, and buybacks.",
        risks="regulation of interchange and network fees, real-time payment systems bypassing "
              "cards, litigation; a trailing P/E near 40 gives G-K a negative repricing term.",
        verdict="Keep as the lower-volatility pick, ranked third: OOS Sharpe 0.72 (just below IVW's "
                "0.77), IR 0.14 (t 0.4, weak), the smallest drawdown of the eight (-26%, just over "
                "the budget) and only -8% in the 2022 window against -27% for IVW; but it fell more "
                "than IVW in the Covid window (-24% vs -16%), so it is not defensive in every crisis. "
                "Forward consensus 9%.",
        reason="the lowest in-sample drawdown of the eight (-22%)",
        clause="it is the steady one of our US stocks, chosen for security rather than for extra return"),
    "GILD": dict(
        rank=6,
        business="a biopharmaceutical company focused on HIV, liver disease and oncology",
        thesis="Gilead's HIV franchise funds a 2% dividend; the 2017 screen picked it on hepatitis-C "
               "growth that was already fading (revenue was $30.4bn in FY2016, the last year filed by end-2017, and $29.4bn in FY2025).",
        drivers="HIV share and pricing, new HIV prevention drugs, oncology, and the dividend.",
        risks="HIV patent expiries, US drug-price negotiation, oncology write-downs (the source of "
              "the negative 2026 EPS consensus that makes the analyst growth figure meaningless; "
              "capped at the 7% revenue consensus).",
        verdict="Drop under method.md section 8 rule 2: OOS Sharpe 0.57 below IVW and IR -0.02, as "
                "its weak in-sample IR (0.19) warned. Like REGN it diversified (beta 0.17; up in the "
                "Covid and 2022 windows), but that is not the job of the growth sleeve.",
        reason="the second-highest fundamental score, from a hepatitis-C boom",
        clause="it is a dividend and defence story, not a growth one, and we are not using it here"),
}


# ---------------------------------------------------------------- helpers
def _f(x):
    """Plain float or None (NaN, inf, None -> None)."""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def clean(o, nd=6):
    """JSON-safe copy: NaN/inf -> None, numpy -> python, floats rounded."""
    if isinstance(o, dict):
        return {str(k): clean(v, nd) for k, v in o.items()}
    if isinstance(o, (list, tuple, np.ndarray)):
        return [clean(v, nd) for v in o]
    if isinstance(o, (bool, np.bool_)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        return round(float(o), nd) if math.isfinite(float(o)) else None
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    if o is pd.NA or o is pd.NaT:
        return None
    return o


def _require(path):
    if not Path(path).exists():
        raise FileNotFoundError(f"missing input: {path} (nothing is downloaded; see the report)")
    return path


def _pct(v, d=1):
    return "n/a" if v is None or not np.isfinite(v) else f"{v * 100:.{d}f}%"


def _num(v, d=2):
    return "n/a" if v is None or not np.isfinite(v) else f"{v:.{d}f}"


# ---------------------------------------------------------------- inputs
@dataclasses.dataclass
class Inputs:
    universe: pd.DataFrame
    prices: pd.DataFrame        # daily local (= USD) adjusted close, spike-filtered
    daily_usd: pd.DataFrame
    monthly: pd.DataFrame       # monthly USD returns, partial last month dropped
    yields: pd.DataFrame
    volumes: pd.DataFrame
    scored: pd.DataFrame
    insample: pd.DataFrame

    @property
    def rf(self):
        return self.monthly[RF]

    @property
    def bench(self):
        return benchmark_monthly(BENCH, self.monthly)

    @property
    def alt(self):
        return self.monthly[ALT_BENCH]

    @property
    def last_month(self):
        return self.monthly.index[-1]


def load_inputs(tickers, data_dir=DATA, plan_dir=PLAN):
    """Read only the columns needed. Nothing is fetched."""
    data_dir, plan_dir = Path(data_dir), Path(plan_dir)
    uni = load_universe(_require(plan_dir / "universe.csv"))
    cols = list(dict.fromkeys(list(tickers) + SUPPORT))
    prices = read_wide_csv(_require(data_dir / "prices.csv"), columns=cols)
    missing = [c for c in cols if c not in prices.columns]
    if missing:
        raise FileNotFoundError(f"prices.csv has no column for {missing}")
    fx = read_wide_csv(_require(data_dir / "fx.csv"), columns=["USD"])
    rows = uni[uni["ticker"].isin(cols)]
    daily_usd = usd_prices(prices, fx, rows)
    for c in cols:                      # ^GSPC is not a universe row; it is USD
        if c not in daily_usd:
            daily_usd[c] = prices[c]
    monthly = monthly_returns(daily_usd, drop_partial=True)
    yields = pd.read_csv(_require(data_dir / "yields.csv"), index_col=0, parse_dates=True).sort_index()
    vol_path = data_dir / "volumes.csv"
    volumes = read_wide_csv(vol_path, spikes=False, columns=cols) if vol_path.exists() else pd.DataFrame()
    scored = pd.read_csv(_require(plan_dir / "longlists" / "us_growth_stock_scored.csv")).set_index("ticker")
    insample = pd.read_csv(_require(plan_dir / "longlists" / "us_growth_stock_insample_table.csv")).set_index("ticker")
    return Inputs(uni, prices, daily_usd, monthly, yields, volumes, scored, insample)


# ---------------------------------------------------------------- adapters to research/
def universe_row(universe, ticker):
    r = universe[universe["ticker"] == ticker]
    if r.empty:
        raise KeyError(f"{ticker} not in research/plan/universe.csv")
    return r.iloc[0]


def make_stock(row):
    """research.config.Stock from a universe row: key = ticker, USD, US, home index ^GSPC."""
    t = str(row["ticker"])
    usd = row.get("usd_ticker", "")
    return config.Stock(key=t, name=str(row.get("name", t)), ticker=t, currency="USD", country="US",
                        local_index=ASSUMPTIONS.local_index, usd_ticker=usd if isinstance(usd, str) else "")


class CandidateDataset(rdata.Dataset):
    """research.data.Dataset whose stock registry is the candidate list, not config.STOCKS.

    research.capm calls ds.stock_returns(stock.key), which looks the key up in
    config.STOCKS_BY_KEY; config.py is not edited, so the lookup is redirected here.
    """

    def __init__(self, prices, fx, yields, fundamentals, stocks):
        super().__init__(prices, fx, yields, fundamentals)
        self.stocks = {s.key: s for s in stocks}

    def stock_returns(self, key):
        s = self.stocks[key]
        p = self.monthly_prices()[s.ticker].dropna()
        local = p.pct_change(fill_method=None).dropna()
        fx = self.monthly_fx()[s.currency].reindex(p.index).ffill()
        usd = (p * fx).pct_change(fill_method=None).dropna()
        return local, usd


def make_dataset(stock, prices, yields=None, fundamentals=None, end=None):
    """CandidateDataset for one stock from the wide CSV frames (no network).

    prices: daily frame holding stock.ticker, stock.local_index and config.GLOBAL_INDEX.
    fundamentals: {ticker: dict}; default research.data.load_fundamentals(ticker) (disk only).
    end: last date used (the last full month end), so betas use full months only.
    """
    cols = [c for c in dict.fromkeys([stock.ticker, stock.local_index, config.GLOBAL_INDEX]) if c in prices]
    p = prices[cols]
    if end is not None:
        p = p.loc[:pd.Timestamp(end)]
    fx = pd.DataFrame(index=p.index)
    fund = fundamentals if fundamentals is not None else {stock.ticker: rdata.load_fundamentals(stock.ticker)}
    return CandidateDataset(p, fx, yields if yields is not None else pd.DataFrame(), fund, [stock])


def model_settings(key, mc_paths=None):
    """config.py settings with the per-name values of assumptions_us_growth.py."""
    cap = ASSUMPTIONS.growth_cap.get(key, ASSUMPTIONS.default_growth_cap)
    dcfs = dataclasses.replace(config.DCFSettings(), max_start_growth=cap,
                               cyclical_mid_cycle=dict(ASSUMPTIONS.cyclical_mid_cycle))
    gks = dataclasses.replace(config.GKSettings(), analyst_growth_cap=cap,
                              target_pe={key: ASSUMPTIONS.target_pe.get(key)})
    mcs = dataclasses.replace(config.MonteCarloSettings(), horizon_years=ASSUMPTIONS.horizon_years)
    if mc_paths:
        mcs = dataclasses.replace(mcs, n_paths=mc_paths)
    return dcfs, gks, mcs


def trailing_pe_now(info):
    """Current trailing GAAP P/E: yfinance trailingPE (price / TTM GAAP EPS), else market cap /
    TTM net income to common. None when TTM earnings are not positive."""
    pe = _f(info.get("trailingPE"))
    if pe is not None and pe > 0:
        return pe, "yfinance info.json trailingPE (price / TTM GAAP diluted EPS)"
    mcap, ni = _f(info.get("marketCap")), _f(info.get("netIncomeToCommon"))
    if mcap and ni and ni > 0:
        return mcap / ni, "yfinance info.json marketCap / netIncomeToCommon (TTM GAAP)"
    return None, "TTM GAAP earnings not positive: trailing P/E undefined, repricing set to 0"


def gk_settings_same_basis(gks, key, info):
    """Put both ends of the G-K repricing term on a trailing GAAP basis.

    research/grinold_kroner.py computes repricing = (target / forward_pe) ** (1/years) - 1 from
    yfinance forwardPE (forward, analyst/non-GAAP). The targets in assumptions_us_growth.py are
    trailing GAAP P/Es, so the adapter hands the module the forward-equivalent target
    target_trailing x forward_pe / trailing_pe_now, which makes the module's ratio equal
    target_trailing / trailing_pe_now (module unchanged). Returns (settings, basis dict).
    """
    target = ASSUMPTIONS.target_pe.get(key)
    fwd = _f(info.get("forwardPE"))
    trail, src = trailing_pe_now(info)
    ok = target is not None and fwd and fwd > 0 and trail is not None
    tgt_fwd = target * fwd / trail if ok else None
    basis = {"basis": "trailing GAAP P/E at both ends (current TTM vs trailing target)",
             "trailing_pe_now": trail, "trailing_pe_source": src, "target_pe_trailing": target,
             "forward_pe_now": fwd, "target_pe_forward_equivalent": tgt_fwd,
             "repricing_same_basis": (target / trail) ** (1 / gks.repricing_years) - 1 if ok else 0.0}
    return dataclasses.replace(gks, target_pe={key: tgt_fwd}), basis


def forward_returns(stock, ds, hist_usd, mc_paths=None):
    """expected_return_7y block: CAPM, DCF implied, Grinold-Kroner; Monte Carlo median with
    forward drift = consensus of those three (so the MC median is not in the consensus)."""
    a = config.MarketAssumptions()
    dcfs, gks, mcs = model_settings(stock.key, mc_paths)
    gks, gk_basis = gk_settings_same_basis(gks, stock.key,
                                           ds.fundamentals.get(stock.ticker, {}).get("info", {}))
    c = capm.estimate(stock, ds, a)
    d = dcf.run(stock, ds, a, c["cost_of_equity"], mc=config.MonteCarloSettings(), s=dcfs)
    g = grinold_kroner.run(stock, ds, a, s=gks, dcf_settings=dcfs)
    methods = {"capm": _f(c["expected_usd"]), "dcf": _f(d.get("expected_usd")) if d else None,
               "grinold_kroner": _f(g["expected_usd"]), "yield": None, "monte_carlo_median": None}
    vals = [methods[k] for k in ("capm", "dcf", "grinold_kroner") if methods[k] is not None]
    cons = float(np.mean(vals)) if vals else None
    rng5_95, mc_detail = [None, None], {}
    h = hist_usd.dropna()
    if cons is not None and len(h) >= 60:
        sim = montecarlo.simulate(h.to_frame(stock.key), mcs, {stock.key: cons})[stock.key]
        methods["monte_carlo_median"] = sim["annualised"]["50"]
        rng5_95 = [sim["annualised"]["5"], sim["annualised"]["95"]]
        mc_detail = {"sample": [str(h.index[0].date()), str(h.index[-1].date())], "months": len(h),
                     "n_paths": mcs.n_paths, "block_months": mcs.block_months, "seed": mcs.seed,
                     "horizon_years": mcs.horizon_years, "prob_loss_7y": sim["prob_loss_5y"],
                     "terminal_100k_median": sim["terminal_100k"]["50"],
                     "terminal_100k_5": sim["terminal_100k"]["5"], "terminal_100k_95": sim["terminal_100k"]["95"]}
    # G-K without repricing: how much of the estimate is the assumed P/E drift.
    gk_no_reprice = _f(g["expected_usd"] - g["repricing"]) if g.get("repricing") is not None else None
    detail = {
        "capm": {k: c[k] for k in ("beta_local_raw", "beta_local", "rf_local", "beta_global",
                                   "expected_usd_global_capm")},
        "dcf": None if not d else {k: d.get(k) for k in (
            "base_source", "fcf_conversion", "g0", "g_source", "g_terminal", "wacc", "upside",
            "mc_prob_undervalued", "terminal_share_of_value", "note")},
        "dcf_mc_implied_return": d.get("mc_implied_return") if d else None,
        "grinold_kroner": {**{k: g[k] for k in ("dividend_yield", "inflation", "real_growth", "growth_source",
                                                "net_dilution", "forward_pe", "target_pe", "repricing")},
                           "target_pe_note": "target_pe above is the forward-equivalent handed to "
                                             "research/grinold_kroner.py; see repricing_basis",
                           "repricing_basis": gk_basis, "without_repricing": gk_no_reprice},
        "consensus_without_repricing": _f(np.mean([v for v in (methods["capm"], methods["dcf"], gk_no_reprice)
                                                   if v is not None])),
        "monte_carlo": mc_detail,
        "growth_cap": dcfs.max_start_growth,
    }
    return {"methods": methods, "consensus_usd": cons, "consensus_local": cons,
            "consensus_of": ["capm", "dcf", "grinold_kroner"], "range_5_95": rng5_95,
            "range_source": "forward Monte Carlo (circular block bootstrap, research/montecarlo.py; drift scaled to the consensus), annualised 7-year return",
            "assumptions": ASSUMPTIONS_REF, "command": f"python -m {MODULE} --ticker {stock.key}",
            "detail": clean(detail)}


# ---------------------------------------------------------------- metrics, rolling, stress
def windows(r):
    return {"in_sample": r.loc[IS_START:IS_END], "out_of_sample": r.loc[OOS_START:],
            "full": r.loc[IS_START:]}


def metrics_blocks(r, bench, rf, n_trials=N_TRIALS):
    out = {}
    for w, x in windows(r).items():
        m = metrics_block(x, bench, rf, n_trials=n_trials)
        out[w] = {"usd": m, "local": dict(m)}   # local currency = USD for US stocks
    return out


def rolling_block(r, bench, rf, window=ROLL):
    x = r.loc[IS_START:].dropna()
    rs, ri = rolling_sharpe(x, rf, window), rolling_ir(x, bench, window)
    idx = rs.index.union(ri.index)
    rs, ri = rs.reindex(idx), ri.reindex(idx)
    # windows lying wholly inside the OOS period (first ends 36 months after 2018-01)
    oos_first_end = pd.Timestamp(OOS_START) + pd.offsets.MonthEnd(window)
    ri_oos = ri[ri.index >= oos_first_end].dropna()
    return {"window_months": window, "dates": [str(d.date()) for d in idx],
            "sharpe": [_f(v) for v in rs], "info_ratio": [_f(v) for v in ri],
            "share_ir_positive_oos": _f((ri_oos > 0).mean()) if len(ri_oos) else None,
            "share_ir_positive_full": _f((ri.dropna() > 0).mean()) if ri.notna().any() else None,
            "note": "share_ir_positive_oos counts 36-month windows wholly inside 2018-01..end; "
                    "share_ir_positive_full counts every window from 2010 (the rubric's consistency measure)"}


def window_return(r, start, end):
    """Compounded return over the months after `start` through `end`; None unless every month has data."""
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    x = r[(r.index > s) & (r.index <= e)]
    n_expected = (e.year - s.year) * 12 + (e.month - s.month)
    if len(x) != n_expected or x.isna().any() or n_expected <= 0:
        return None
    return float((1 + x).prod() - 1)


def usd_up_months(yields, threshold=USD_RISE):
    """Month ends in which the FRED broad dollar index (monthly average, DTWEXBGS) rose >= threshold."""
    if "USD_BROAD" not in yields:
        return pd.DatetimeIndex([])
    s = yields["USD_BROAD"].dropna()
    s.index = s.index + pd.offsets.MonthEnd(0)
    s = s.groupby(level=0).last()
    chg = s.pct_change(fill_method=None)
    return chg[chg >= threshold].index


def stress_block(r, bench, alt, yields):
    out = {}
    for k, (s, e) in STRESS_WINDOWS.items():
        out[k] = {"start": s, "end": e, "return": window_return(r, s, e),
                  "benchmark": window_return(bench, s, e), "qqq": window_return(alt, s, e)}
    months = usd_up_months(yields)
    have = [m for m in months if m in r.index and pd.notna(r.get(m))]
    avg = lambda x: _f(x.reindex(have).mean()) if have else None
    out["strong_usd"] = {
        "definition": "average monthly return in months when the FRED broad dollar index "
                      "(USD_BROAD = DTWEXBGS, monthly average) rose by at least 2%",
        "months": len(have), "dates": [str(m.date()) for m in have],
        "avg_return": avg(r), "benchmark": avg(bench), "qqq": avg(alt),
        "episodes": {k: {"start": s, "end": e, "return": window_return(r, s, e),
                         "benchmark": window_return(bench, s, e), "qqq": window_return(alt, s, e)}
                     for k, (s, e) in USD_EPISODES.items()},
    }
    return out


# ---------------------------------------------------------------- fundamentals, screens, liquidity
def _edgar_cik(universe, ticker):
    try:
        return universe_row(universe, ticker).get("edgar_cik")
    except KeyError:
        return None


def fundamentals_compare(ticker, inp, data_dir=DATA):
    """EDGAR point-in-time measures at 2017-12-31 and at the last price date (same library code)."""
    path = edgar_path(Path(data_dir) / "edgar", _edgar_cik(inp.universe, ticker))
    if path is None:
        return {"source": None, "note": "no EDGAR companyfacts file on disk", "2017": None, "latest": None}
    cj = read_companyfacts(path)
    facts, splits = edgar_facts(cj), split_events(cj)
    divs = read_dividends(Path(data_dir) / "fundamentals" / ticker / "dividends.csv")
    px = inp.prices[ticker]
    out = {"source": str(path.relative_to(ROOT)).replace("\\", "/"),
           "note": "point-in-time (EDGAR filing dates); ROIC uses the non-financial formula for every name"}
    for label, as_of in (("2017", IS_END), ("latest", str(px.dropna().index[-1].date()))):
        tab = point_in_time(facts, as_of)
        if tab.empty or tab["revenue"].notna().sum() == 0:
            out[label] = None
            continue
        m, fl = stock_measures(tab, px, as_of, False, splits, divs)
        last = tab[tab["revenue"].notna()].iloc[-1]
        fcf = last["cfo"] - (0 if pd.isna(last["capex"]) else abs(last["capex"]))
        out[label] = clean({
            "as_of": as_of, "fy_end": m.get("fy_end"), "revenue_usd_bn": last["revenue"] / 1e9,
            "net_income_usd_bn": last["net_income"] / 1e9, "fcf_usd_bn": fcf / 1e9,
            "rev_cagr_3y": m.get("rev_cagr_3y"), "ni_cagr_3y": m.get("ni_cagr_3y"),
            "op_margin": m.get("op_margin"), "op_margin_chg_3y": m.get("op_margin_chg_3y"),
            "roic": m.get("roic_or_roe"), "net_debt_ebitda": m.get("net_debt_ebitda"),
            "fcf_yield": m.get("fcf_yield"), "pe_trailing": m.get("pe_now"), "pe_rel_5y": m.get("pe_rel_5y"),
            "market_cap_usd_bn": (m.get("market_cap_local") or np.nan) / 1e9, "flags": "; ".join(fl)})
    if out.get("2017") is None:
        out["note"] += "; no filing known at 2017-12-31 under this CIK"
    return out


def traded_value(ticker, inp, as_of, days=252):
    """Average daily traded value, USD millions (adjusted close x shares; slightly understates old values)."""
    if inp.volumes is None or ticker not in inp.volumes:
        return None
    v = (inp.volumes[ticker] * inp.daily_usd[ticker]).loc[:pd.Timestamp(as_of)].dropna().tail(days)
    return _f(v.mean() / 1e6) if len(v) >= 120 else None


SCREEN_DETAIL = ["rev_cagr_3y", "ni_cagr_3y", "roic_or_roe", "op_margin", "op_margin_chg_3y", "net_debt_ebitda",
                 "fcf_yield", "pe_now", "pe_rel_5y", "growth_score", "quality_score", "valuation_score",
                 "T1", "T2", "T3", "T4", "T5", "mcap_asof_usd_bn", "market_cap_usd_bn", "fundamentals_pit"]


def screens_block(ticker, inp):
    s = inp.scored.loc[ticker]
    det = {c: (s[c] if c in s.index else None) for c in SCREEN_DETAIL}
    det["above_200dma"] = bool(s["T2"] > 0) if pd.notna(s.get("T2")) else None
    if ticker in inp.insample.index:
        t = inp.insample.loc[ticker]
        det.update(composite_is=t["composite"], rank_is=int(t["rank"]), rank_is_of=len(inp.insample))
    det["traded_value_usd_m_2017"] = traded_value(ticker, inp, IS_END)
    det["traded_value_usd_m_latest"] = traded_value(ticker, inp, inp.prices.index[-1])
    det["flags"] = s.get("flags") if isinstance(s.get("flags"), str) else ""
    det["technical_note"] = s.get("technical_note") if isinstance(s.get("technical_note"), str) else ""
    return clean({"fundamental_score": s.get("fundamental_score"), "technical_score": s.get("technical_score"),
                  "hard_screens_passed": bool(s.get("passed")), "as_of": s.get("as_of"),
                  "source": "research/plan/longlists/us_growth_stock_scored.csv, us_growth_stock_insample_table.csv",
                  "detail": det})


# ---------------------------------------------------------------- one candidate
def analyse(ticker, inp, mc_paths=None, data_dir=DATA):
    """Everything in results_schema.md for one ticker, as a dict (nothing written)."""
    row = universe_row(inp.universe, ticker)
    stock = make_stock(row)
    r, bench, rf, alt = inp.monthly[ticker], inp.bench, inp.rf, inp.alt
    daily = inp.prices[ticker].dropna()
    r_all = r.loc[r.first_valid_index():]
    n_is, n_oos = int(r.loc[IS_START:IS_END].notna().sum()), int(r.loc[OOS_START:].notna().sum())
    fund = rdata.load_fundamentals(ticker)
    info = fund.get("info", {})
    ds = make_dataset(stock, inp.prices, inp.yields, {ticker: fund}, end=inp.last_month)
    notes = ["full = 2010-01 to the last full month (in-sample + out-of-sample); partial final month dropped",
             "buy-and-hold monthly total returns, no trade modelled, no cost charged",
             "local currency = USD, so the local blocks equal the USD blocks"]
    if n_is < 96:
        notes.append(f"in-sample has {n_is} months (listed {daily.index[0].date()}): short in-sample history")
    if r_all.notna().sum() < SHORT_HISTORY:
        notes.append("short history (<120 months)")
    flags = str(inp.scored.loc[ticker].get("flags", ""))
    if "not point-in-time" in flags:
        notes.append("2017 screen fundamentals not point-in-time (from current statements), flagged by Phase 2")
    if ticker in ASSUMPTIONS.growth_cap:
        notes.append(f"analyst growth capped at {ASSUMPTIONS.growth_cap[ticker]:.2%} (assumptions_us_growth.py)")

    metrics = metrics_blocks(r, bench, rf)
    alt_blocks = {w: {k: v for k, v in metrics_block(x, alt, rf, N_TRIALS).items()
                      if k in ("start", "end", "months", "beta", "alpha", "t_stat_alpha", "tracking_error",
                               "info_ratio", "t_stat_ir", "up_capture", "down_capture")}
                  for w, x in windows(r).items()}
    oos = metrics["out_of_sample"]["usd"]
    res = {
        "schema_version": 1, "id": ticker.replace(".", "_").replace("^", "_"), "ticker": ticker,
        "usd_ticker": ticker, "name": str(row["name"]), "position_type": "us_growth_stock",
        "instrument": "stock", "country": "US", "currency": "USD",
        "sector": " / ".join(x for x in (info.get("sector"), info.get("industry")) if x) or None,
        "non_us": False, "benchmark": BENCH,
        "data": {"price_start": str(daily.index[0].date()), "price_end": str(daily.index[-1].date()),
                 "months_total": int(r_all.notna().sum()), "months_in_sample": n_is,
                 "months_out_of_sample": n_oos,
                 "sources": ["data/research/prices.csv", "data/research/fx.csv", "data/research/yields.csv",
                             "data/research/volumes.csv", f"data/research/fundamentals/{ticker}/",
                             "data/research/edgar/", "research/plan/longlists/us_growth_stock_scored.csv"],
                 "fund_fee": None, "notes": "; ".join(notes)},
        "metrics": metrics,
        "alt_benchmark": {"id": ALT_BENCH, "vs_alt": alt_blocks},
        "rolling": rolling_block(r, bench, rf),
        "currency": {"local_return": oos.get("cagr"), "fx_return": 0.0, "usd_return": oos.get("cagr"),
                     "hedged_return": None, "hedge_cost": None, "fx_vol_share": 0.0},
        "expected_return_7y": forward_returns(stock, ds, r.loc[IS_START:], mc_paths),
        "stress": stress_block(r, bench, alt, inp.yields),
        "screens": screens_block(ticker, inp),
        "fundamentals": fundamentals_compare(ticker, inp, data_dir),
        "rubric": {"scores": {}, "total": None, "rank_in_type": None},
        "review": {"reviewer": None, "date": None, "verdict": None, "claims": []},
        "explain": [],
        "memo": f"research/candidates/memos/{ticker}.md",
        "charts": {"growth": f"reports/candidates/charts/{ticker}_growth.png",
                   "rolling": f"reports/candidates/charts/{ticker}_rolling.png"},
        "reproduce": f"python -m {MODULE} --ticker {ticker} --write",
    }
    res["explain"] = explain_sentences(ticker, metrics, metrics_blocks(bench, bench, rf), res["expected_return_7y"])
    return clean(res)


def explain_sentences(ticker, metrics, bench_metrics, fwd):
    n = NARRATIVE.get(ticker, {})
    o, b = metrics["out_of_sample"]["usd"], bench_metrics["out_of_sample"]["usd"]
    s1 = f"{ticker} is {n.get('business', 'a US growth company')}; a screen using only data to 2017 picked it for {n.get('reason', 'its record')}."
    s2 = (f"From 2018 to {o.get('end', '')[:7]}, which the screen never saw, it returned {_pct(o.get('cagr'))} a year "
          f"against {_pct(b.get('cagr'))} for the S&P 500 Growth fund, with a worst fall of {_pct(o.get('max_drawdown'), 0)} "
          f"(fund {_pct(b.get('max_drawdown'), 0)}).")
    if fwd and fwd.get("consensus_usd") is not None:
        lo, hi = fwd["range_5_95"]
        s3 = (f"Our models expect about {_pct(fwd['consensus_usd'], 0)} a year over the next seven years "
              f"(5-95% range {_pct(lo, 0)} to {_pct(hi, 0)}), so {n.get('clause', 'it is a candidate')}.")
    else:
        s3 = f"The forward models could not be run, so {n.get('clause', 'it is a candidate')}."
    return [s1, s2, s3]


# ---------------------------------------------------------------- charts
def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(COLORS["ink2"])
    ax.tick_params(colors=COLORS["ink2"], labelsize=8)
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.6)
    ax.set_axisbelow(True)


def charts(ticker, inp, res, out_dir=CHARTS):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    r = inp.monthly[ticker].loc[IS_START:]
    start = r.first_valid_index()
    series = {ticker: r.loc[start:], "IVW": inp.bench.loc[start:], "QQQ": inp.alt.loc[start:]}
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=130)
    ax.axvspan(pd.Timestamp(start), pd.Timestamp(IS_END), color=COLORS["shade"], zorder=0)
    ax.text(pd.Timestamp(start) + pd.Timedelta(days=60), 0.97, "in-sample (screen period)", transform=ax.get_xaxis_transform(),
            fontsize=8, color=COLORS["ink2"], va="top")
    ax.text(pd.Timestamp(OOS_START) + pd.Timedelta(days=60), 0.97, "out-of-sample", transform=ax.get_xaxis_transform(),
            fontsize=8, color=COLORS["ink2"], va="top")
    for k, s in series.items():
        lvl = 10_000 * (1 + s.fillna(0)).cumprod()
        lvl = pd.concat([pd.Series([10_000.0], index=[s.index[0] - pd.offsets.MonthEnd(1)]), lvl])
        c = COLORS["stock"] if k == ticker else COLORS[k]
        ax.plot(lvl.index, lvl.values, color=c, linewidth=2 if k == ticker else 1.5,
                label={ticker: ticker, "IVW": "IVW (S&P 500 Growth)", "QQQ": "QQQ (Nasdaq-100)"}[k])
        ax.annotate(f"${lvl.iloc[-1]:,.0f}", (lvl.index[-1], lvl.iloc[-1]), fontsize=7.5, color=COLORS["ink"],
                    xytext=(4, 0), textcoords="offset points", va="center")
    ax.set_yscale("log")
    ax.set_ylabel("value of $10,000 (log scale)", fontsize=8, color=COLORS["ink2"])
    ax.set_title(f"{ticker}: growth of $10,000, monthly total return in USD", fontsize=10, color=COLORS["ink"], loc="left")
    _style(ax)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()
    g = out_dir / f"{ticker}_growth.png"
    fig.savefig(g)
    plt.close(fig)

    ro = res["rolling"]
    d = pd.to_datetime(ro["dates"])
    fig, axes = plt.subplots(2, 1, figsize=(8, 5), dpi=130, sharex=True)
    for ax, key, lab in ((axes[0], "sharpe", "Sharpe (vs BIL)"), (axes[1], "info_ratio", "information ratio vs IVW")):
        v = np.array([np.nan if x is None else x for x in ro[key]], dtype=float)
        ax.axhline(0, color=COLORS["ink2"], linewidth=0.8)
        ax.axvline(pd.Timestamp(OOS_START), color=COLORS["ink2"], linewidth=0.8, linestyle="--")
        ax.plot(d, v, color=COLORS["stock"], linewidth=2)
        ax.set_ylabel(lab, fontsize=8, color=COLORS["ink2"])
        _style(ax)
    axes[0].set_title(f"{ticker}: rolling 36-month Sharpe and information ratio (window end; dashed = OOS start)",
                      fontsize=10, color=COLORS["ink"], loc="left")
    fig.tight_layout()
    rp = out_dir / f"{ticker}_rolling.png"
    fig.savefig(rp)
    plt.close(fig)
    return g, rp


# ---------------------------------------------------------------- memo
def _fund_row(label, k, f17, fnow, fmt):
    a = f17.get(k) if f17 else None
    b = fnow.get(k) if fnow else None
    return f"| {label} | {fmt(a) if a is not None else 'n/a'} | {fmt(b) if b is not None else 'n/a'} |"


def memo(res, bench_metrics):
    t = res["ticker"]
    n = NARRATIVE[t]
    m = {w: res["metrics"][w]["usd"] for w in ("in_sample", "out_of_sample")}
    b = {w: bench_metrics[w]["usd"] for w in ("in_sample", "out_of_sample")}
    e = res["expected_return_7y"]
    st = res["stress"]
    f = res["fundamentals"]
    f17, fnow = f.get("2017"), f.get("latest")
    sc = res["screens"]
    bn = lambda x: f"${x:,.1f}bn"
    L = [f"# {t} {res['name']}: candidate memo (US growth stock)", "",
         f"Data to {m['out_of_sample']['end']}; benchmark IVW (S&P 500 Growth), risk-free BIL. "
         f"Every number is from `{res['reproduce']}`. In-sample = 2010-01 to 2017-12 "
         f"({res['data']['months_in_sample']} months), out-of-sample (OOS) = 2018-01 onward "
         f"({res['data']['months_out_of_sample']} months).", "",
         f"**Thesis.** {n['thesis']}", "",
         f"**What drives returns.** {n['drivers'][0].upper()}{n['drivers'][1:]}", "",
         "**Record, in-sample vs out-of-sample (monthly, USD).**", "",
         "| | IS stock | IS IVW | OOS stock | OOS IVW |", "|---|---|---|---|---|"]
    for lab, k, fm in (("CAGR", "cagr", _pct), ("Volatility", "vol", _pct), ("Sharpe", "sharpe", _num),
                       ("Info ratio (t)", "info_ratio", None), ("Alpha (t)", "alpha", None),
                       ("Max drawdown", "max_drawdown", _pct), ("Deflated Sharpe (N=46)", "deflated_sharpe", _num)):
        if k == "info_ratio":
            cell = lambda x: f"{_num(x.get('info_ratio'))} ({_num(x.get('t_stat_ir'), 1)})"
            L.append(f"| {lab} | {cell(m['in_sample'])} | - | {cell(m['out_of_sample'])} | - |")
        elif k == "alpha":
            cell = lambda x: f"{_pct(x.get('alpha'))} ({_num(x.get('t_stat_alpha'), 1)})"
            L.append(f"| {lab} | {cell(m['in_sample'])} | - | {cell(m['out_of_sample'])} | - |")
        else:
            L.append(f"| {lab} | {fm(m['in_sample'].get(k))} | {fm(b['in_sample'].get(k))} | "
                     f"{fm(m['out_of_sample'].get(k))} | {fm(b['out_of_sample'].get(k))} |")
    L += ["", f"Rolling 36-month IR above zero: {_pct(res['rolling']['share_ir_positive_full'], 0)} of windows "
          f"since 2010, {_pct(res['rolling']['share_ir_positive_oos'], 0)} of windows wholly inside OOS. "
          f"Stress (stock vs IVW): 2008 {_pct(st['gfc_2008']['return'], 0)} vs {_pct(st['gfc_2008']['benchmark'], 0)}; "
          f"2013 taper {_pct(st['taper_2013']['return'], 0)} vs {_pct(st['taper_2013']['benchmark'], 0)}; "
          f"Covid {_pct(st['covid_2020']['return'], 0)} vs {_pct(st['covid_2020']['benchmark'], 0)}; "
          f"2022 {_pct(st['inflation_2022']['return'], 0)} vs {_pct(st['inflation_2022']['benchmark'], 0)}; "
          f"strong-USD months ({st['strong_usd']['months']}) {_pct(st['strong_usd']['avg_return'])} vs "
          f"{_pct(st['strong_usd']['benchmark'])} a month.", "",
          f"**Fundamentals (SEC EDGAR, point-in-time).** Fiscal year known at 2017-12-31 vs the latest filed "
          f"(FY {fnow.get('fy_end') if fnow else 'n/a'}). Screen fundamental score (2017): "
          f"{_num(sc['fundamental_score'])}.", "",
          "| Measure | 2017 | Latest |", "|---|---|---|",
          _fund_row("Revenue", "revenue_usd_bn", f17, fnow, bn),
          _fund_row("Revenue CAGR 3y", "rev_cagr_3y", f17, fnow, _pct),
          _fund_row("Operating margin", "op_margin", f17, fnow, _pct),
          _fund_row("Free cash flow", "fcf_usd_bn", f17, fnow, bn),
          _fund_row("ROIC", "roic", f17, fnow, _pct),
          _fund_row("Net debt / EBITDA", "net_debt_ebitda", f17, fnow, _num),
          _fund_row("Trailing P/E", "pe_trailing", f17, fnow, lambda x: f"{x:.1f}"),
          _fund_row("FCF yield", "fcf_yield", f17, fnow, _pct), ""]
    if f17 is None:
        L += ["2017 column: no filing under this CIK was known at 2017-12-31 (see flags); the "
              "Phase 2 screen used current statements for it and flagged it.", ""]
    det = e["detail"]
    gk = det.get("grinold_kroner") or {}
    rb = gk.get("repricing_basis") or {}
    L += [f"**Forward 7-year expected return (USD).** CAPM {_pct(e['methods']['capm'])}, DCF implied "
          f"{_pct(e['methods']['dcf'])}, Grinold-Kroner {_pct(e['methods']['grinold_kroner'])} "
          f"(of which P/E drift, trailing GAAP P/E from {_num(rb.get('trailing_pe_now'), 1)} to "
          f"{_num(rb.get('target_pe_trailing'), 1)} over 10 years: {_pct(gk.get('repricing'))}); consensus "
          f"{_pct(e['consensus_usd'])} ({_pct(det.get('consensus_without_repricing'))} without the P/E drift); "
          f"Monte Carlo median {_pct(e['methods']['monte_carlo_median'])}, 5-95% {_pct(e['range_5_95'][0])} to "
          f"{_pct(e['range_5_95'][1])} (circular block bootstrap, drift set to the consensus). "
          f"Both ends of the P/E drift are trailing GAAP multiples; the DCF still starts from forward "
          f"(analyst) earnings. Assumptions: `{e['assumptions']}`.", "",
          "**Technicals.** No technical signal was kept: the pre-registered test (method.md section 6) "
          "found none with OOS IR > 0 and t > 1 for US growth stocks (shortlist.md), so the technical "
          "weight is redistributed and no chart signal is used here.", "",
          f"**Risks.** {n['risks'][0].upper()}{n['risks'][1:]}", "",
          f"**Verdict (analyst rank {n['rank']} of 8; the Phase 4 rubric decides).** {n['verdict']}", "",
          "> **How to explain this pick**", ">"]
    L += [f"> {i + 1}. {s}" for i, s in enumerate(res["explain"])]
    L += ["", f"Charts: `{res['charts']['growth']}`, `{res['charts']['rolling']}`. "
          f"Data notes: {res['data']['notes']}."]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- control group
def control_table(inp):
    """Every hard-screen passer: in-sample and OOS Sharpe, IR, max DD, and the IS/OOS rank test."""
    passed = inp.scored[inp.scored["passed"].astype(bool)]
    rows = []
    for t in list(passed.index) + [BENCH, ALT_BENCH]:
        if t not in inp.monthly:
            rows.append({"ticker": t, "note": "no price column"})
            continue
        r = inp.monthly[t]
        w = windows(r)
        mi = metrics_block(w["in_sample"], inp.bench, inp.rf, N_TRIALS)
        mo = metrics_block(w["out_of_sample"], inp.bench, inp.rf, N_TRIALS)
        role = "benchmark" if t in (BENCH, ALT_BENCH) else passed.loc[t, "role"]
        rows.append({
            "ticker": t, "role": role, "shortlisted": t in TICKERS, "faded_leader": t in FADED or role == "faded_leader",
            "composite_is": inp.insample["composite"].get(t, np.nan), "rank_is": inp.insample["rank"].get(t, np.nan),
            "fundamental_score": passed["fundamental_score"].get(t, np.nan),
            "months_is": mi.get("months"), "cagr_is": mi.get("cagr"), "sharpe_is": mi.get("sharpe"),
            "ir_is": mi.get("info_ratio"), "max_dd_is": mi.get("max_drawdown"),
            "months_oos": mo.get("months"), "cagr_oos": mo.get("cagr"), "sharpe_oos": mo.get("sharpe"),
            "ir_oos": mo.get("info_ratio"), "t_ir_oos": mo.get("t_stat_ir"), "max_dd_oos": mo.get("max_drawdown"),
            "deflated_sharpe_oos": mo.get("deflated_sharpe")})
    df = pd.DataFrame(rows).set_index("ticker")
    names = df[df["role"] != "benchmark"]
    df["rank_oos_sharpe"] = names["sharpe_oos"].rank(ascending=False)
    bs = df.loc[BENCH, "sharpe_oos"]
    tests = {
        "composite_vs_oos_sharpe": is_oos_rank_test(names["composite_is"], names["sharpe_oos"]),
        "composite_vs_oos_ir": is_oos_rank_test(names["composite_is"], names["ir_oos"]),
        "is_sharpe_vs_oos_sharpe": is_oos_rank_test(names["sharpe_is"], names["sharpe_oos"]),
        "fundamental_vs_oos_sharpe": is_oos_rank_test(names["fundamental_score"], names["sharpe_oos"]),
    }
    for t in tests.values():   # significance label (two-sided 5%); the library's `predictive` is rho > 0 only
        sig = t["p_value"] is not None and np.isfinite(t["p_value"]) and t["p_value"] < 0.05
        t["rho_positive"] = bool(t["rho"] > 0)
        t["predictive"] = bool(t["rho"] > 0 and sig)
        t["label"] = ("positive and significant" if t["predictive"] else
                      "positive, not significant" if t["rho"] > 0 else "zero or negative")
    best = df.loc[names.index].sort_values("sharpe_oos", ascending=False).head(10)
    best10 = [{"ticker": t, "rank_oos": int(best.loc[t, "rank_oos_sharpe"]), "rank_is": _f(best.loc[t, "rank_is"]),
               "group": "shortlist" if t in TICKERS else "near miss (shortlist.md)" if t in NEAR_MISSES
               else "faded leader" if best.loc[t, "faded_leader"] else "other passer"} for t in best.index]
    top8 = names.sort_values("rank_is").head(8)
    fl = names[names["faded_leader"]]
    summary = {
        "n_names": int(len(names)), "benchmark_oos_sharpe": _f(bs),
        "rank_tests": tests,
        "share_beating_ivw_sharpe_oos": _f((names["sharpe_oos"] > bs).mean()),
        "share_ir_positive_oos": _f((names["ir_oos"] > 0).mean()),
        "top8_by_composite": {"tickers": list(top8.index), "median_sharpe_oos": _f(top8["sharpe_oos"].median()),
                              "share_ir_positive_oos": _f((top8["ir_oos"] > 0).mean())},
        "shortlist": {"median_sharpe_oos": _f(names.loc[names["shortlisted"], "sharpe_oos"].median()),
                      "share_ir_positive_oos": _f((names.loc[names["shortlisted"], "ir_oos"] > 0).mean())},
        "faded_leaders": {"tickers": list(fl.index), "median_sharpe_oos": _f(fl["sharpe_oos"].median()),
                          "median_ir_oos": _f(fl["ir_oos"].median()),
                          "share_ir_positive_oos": _f((fl["ir_oos"] > 0).mean())},
        "all_median_sharpe_oos": _f(names["sharpe_oos"].median()),
        "best10_oos": best10,
        "near_misses": {"tickers": NEAR_MISSES,
                        "median_sharpe_oos": _f(names.reindex(NEAR_MISSES)["sharpe_oos"].median())},
        "n_trials_deflated_sharpe": N_TRIALS,
        "command": f"python -m {MODULE} --control --write",
    }
    return df.sort_values(["role", "rank_is"]), clean(summary)


# ---------------------------------------------------------------- P/E audit for the assumptions file
def pe_history(ticker, inp, start="2016-11-01", data_dir=DATA):
    """Median month-end trailing P/E since `start`: unadjusted close / latest known EDGAR diluted EPS."""
    path = edgar_path(Path(data_dir) / "edgar", _edgar_cik(inp.universe, ticker))
    if path is None:
        return None
    cj = read_companyfacts(path)
    tab = point_in_time(edgar_facts(cj), inp.prices.index[-1])
    eps = _eps_today_units(tab[tab["revenue"].notna()], split_events(cj))
    p = inp.prices[ticker].dropna()
    raw = (p / dividend_factor(p, read_dividends(Path(data_dir) / "fundamentals" / ticker / "dividends.csv")))
    m = raw.resample("ME").last().loc[start:inp.last_month]
    pe = []
    for d, v in m.items():
        k = eps[eps["known"] <= d]
        if len(k) and k["eps"].iloc[-1] > 0:
            pe.append(v / k["eps"].iloc[-1])
    return {"months": len(pe), "median": float(np.median(pe)) if pe else None}


# ---------------------------------------------------------------- write
def write_candidate(ticker, inp, res=None, out_dir=REPORTS, memo_dir=MEMOS, chart_dir=CHARTS, with_charts=True):
    res = res or analyse(ticker, inp)
    out_dir, memo_dir = Path(out_dir), Path(memo_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    memo_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{res['id']}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    bm = clean(metrics_blocks(inp.bench, inp.bench, inp.rf))
    (memo_dir / f"{ticker}.md").write_text(memo(res, bm), encoding="utf-8")
    if with_charts:
        charts(ticker, inp, res, chart_dir)
    return res


def print_summary(results, summary=None):
    print("| Ticker | IS Sharpe | OOS Sharpe | OOS IR (t) | OOS max DD | Deflated Sharpe OOS | 7y consensus | MC 5-95 |")
    print("|---|---|---|---|---|---|---|---|")
    for r in results:
        i, o, e = r["metrics"]["in_sample"]["usd"], r["metrics"]["out_of_sample"]["usd"], r["expected_return_7y"]
        print(f"| {r['ticker']} | {_num(i.get('sharpe'))} | {_num(o.get('sharpe'))} | {_num(o.get('info_ratio'))} "
              f"({_num(o.get('t_stat_ir'), 1)}) | {_pct(o.get('max_drawdown'))} | {_num(o.get('deflated_sharpe'))} | "
              f"{_pct(e['consensus_usd'])} | {_pct(e['range_5_95'][0])} to {_pct(e['range_5_95'][1])} |")
    if summary:
        print(json.dumps(summary, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(prog=f"python -m {MODULE}", description=__doc__.split("\n")[0])
    ap.add_argument("--ticker", action="append", help="one of the 8 shortlisted tickers (repeatable)")
    ap.add_argument("--all", action="store_true", help="all 8 candidates and the control table")
    ap.add_argument("--control", action="store_true", help="control table only")
    ap.add_argument("--pe-history", action="store_true", help="print the P/E audit for the assumptions file")
    ap.add_argument("--write", action="store_true", help="write JSON, memo, charts (and control CSV)")
    args = ap.parse_args(argv)
    tickers = TICKERS if args.all else (args.ticker or [])
    bad = [t for t in tickers if t not in NARRATIVE]
    if bad:
        ap.error(f"not a shortlisted US growth candidate: {bad}")
    if not (tickers or args.control or args.pe_history):
        ap.error("give --ticker, --all, --control or --pe-history")
    need = list(tickers)
    if args.all or args.control:
        sc = pd.read_csv(_require(LONGLISTS / "us_growth_stock_scored.csv"))
        need += list(sc.loc[sc["passed"].astype(bool), "ticker"])
    if args.pe_history:
        need += TICKERS
    inp = load_inputs(list(dict.fromkeys(need)))
    if args.pe_history:
        print(f"target P/E cap {TARGET_PE_CAP}")
        for t in TICKERS:
            h = pe_history(t, inp)
            print(t, h, "frozen:", PE_MEDIAN_10Y.get(t), "target:", ASSUMPTIONS.target_pe.get(t))
    results = []
    for t in tickers:
        res = write_candidate(t, inp) if args.write else analyse(t, inp)
        results.append(res)
    summary = None
    if args.all or args.control:
        df, summary = control_table(inp)
        if args.write:
            REPORTS.mkdir(parents=True, exist_ok=True)
            df.round(6).to_csv(REPORTS / "us_growth_control.csv")
            (REPORTS / "us_growth_control_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
        cols = ["role", "rank_is", "composite_is", "sharpe_is", "ir_is", "max_dd_is", "sharpe_oos", "ir_oos",
                "t_ir_oos", "max_dd_oos", "deflated_sharpe_oos", "rank_oos_sharpe"]
        with pd.option_context("display.width", 200, "display.max_rows", 100):
            print(df[cols].round(2).to_string())
    if results or summary:
        print_summary(results, summary)


if __name__ == "__main__":
    main()
