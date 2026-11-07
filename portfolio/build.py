"""Phase 5: build the portfolio from the approved picks and test it as a whole.

    python -m portfolio.build --write                    # full run, writes reports/final/
    python -m portfolio.build                            # headline walk-forward only, prints metrics
    python -m portfolio.build --rebalance monthly --lookback-years 5
    python -m portfolio.build --no-rule                  # headline without the 70% non-US floor
    python -m portfolio.build --overlay                  # headline with the protective-put overlay

Binding rules: research/plan/method.md sections 1, 3, 9, 10, 11 and 12.
Picks, runners-up and the overlay decision: research/plan/scorecard.md.

Conventions
- USD base. Daily USD prices = local adjusted close x USD per unit
  (research.screen.prices.usd_prices), then put on US trading days (dates on
  which AGG or BIL trade) with forward-fill of at most 5 days, so Taiwan,
  India and Canada holidays carry the last close (portfolio.data.align_to_calendar).
- Walk-forward: at each rebalance day i the optimizer sees daily returns up
  to day i-1 only; weights then drift with prices until the next rebalance.
  A drift of the non-US share below 0.68 forces a rebalance the next day
  (method.md section 3).
- Monthly series are calendar month ends ('ME'); every metric is computed on
  monthly returns with research.screen.stats.metrics_block, against
  GUIDE_BENCH and BIL.
- Costs (method.md section 10): 5 bp one-way on US-listed stocks and ETFs,
  15 bp on foreign local shares, 0 bp on open-end funds. The put overlay's
  costs are inside its series.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio import backtest, data as pdata, optimize as O
from research import frontier as F
from research import montecarlo as MC
from research.config import MonteCarloSettings
from research.screen import stats
from research.screen.prices import load_universe, read_wide_csv, usd_prices

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "research"
PLAN = ROOT / "research" / "plan"
CAND = ROOT / "reports" / "candidates"
OUT = ROOT / "reports" / "final"
CHARTS = OUT / "charts"
MEMO = ROOT / "research" / "candidates" / "memos" / "portfolio.md"

IN_SAMPLE_END = "2017-12-31"
OOS_START = "2018-01-01"
BACKTEST_END = "2026-10-31"          # last complete month in the data

# ----------------------------------------------------------------------------- the positions
# (ticker, sleeve, non-US share per method.md s3, kind, one-way cost bp)
PICKS = [
    ("AVGO", "us_equity", 0.0, "stock", 5), ("NVDA", "us_equity", 0.0, "stock", 5),
    ("AMZN", "us_equity", 0.0, "stock", 5),
    ("2330.TW", "intl_equity", 1.0, "stock", 15), ("BAJFINANCE.NS", "intl_equity", 1.0, "stock", 15),
    ("CSU.TO", "intl_equity", 1.0, "stock", 15),
    ("PYEMX", "em_bonds", 1.0, "fund", 0), ("CEMB", "em_bonds", 1.0, "fund", 5),
    ("EMB", "em_bonds", 1.0, "fund", 5), ("HYEM", "em_bonds", 1.0, "fund", 5),
    ("IAU", "other", 0.0, "other", 5), ("SLV", "other", 0.0, "other", 5),
]
# GNR and IGF non-US shares: fund factsheets recorded in research/plan/universe.csv notes.
RUNNERS = [
    ("META", "us_equity", 0.0, "stock", 5), ("MA", "us_equity", 0.0, "stock", 5),
    ("REA.AX", "intl_equity", 1.0, "stock", 15), ("NOVO-B.CO", "intl_equity", 1.0, "stock", 15),
    ("TGEIX", "em_bonds", 1.0, "fund", 0), ("EMLC", "em_bonds", 1.0, "fund", 5),
    ("GNR", "other", 0.65, "other", 5), ("IGF", "other", 0.64, "other", 5),
]
SWAPS = {"AMZN": "MA", "CSU.TO": "REA.AX", "HYEM": "TGEIX", "SLV": "GNR"}
FX_STOCKS = {"2330.TW": "TWD", "BAJFINANCE.NS": "INR", "CSU.TO": "CAD"}
BENCH_TICKERS = ["IVW", "EFG", "EEM", "ACWX", "ACWI", "SPY", "AGG", "EMB", "EMLC", "GLD", "BIL"]
FIXED_BENCHES = {
    "GUIDE_BENCH": {"ACWX": 0.55, "EMB": 0.35, "GLD": 0.10},
    "SIXTY_FORTY": {"SPY": 0.60, "AGG": 0.40},
    "GLOBAL_6040": {"ACWI": 0.60, "AGG": 0.40},
}
# Non-US share of the benchmark components (method.md s3). ACWI's ~36% non-US is from
# general knowledge of MSCI ACWI (US about 64%), not a factsheet in the repo: flagged.
BENCH_NON_US = {"ACWX": 1.0, "EMB": 1.0, "GLD": 0.0, "SPY": 0.0, "AGG": 0.0, "ACWI": 0.36}
SLEEVES = ("us_equity", "intl_equity", "em_bonds", "other")
TARGET_MIX = {"equity": 0.55, "bonds": 0.35, "other": 0.10}
BAND = 0.10

STRESS = {"gfc_2008": ("2007-10-31", "2009-02-28"), "taper_2013": ("2013-04-30", "2013-08-31"),
          "covid_2020": ("2020-01-31", "2020-03-31"), "inflation_2022": ("2021-12-31", "2022-10-31")}
USD_EPISODES = {"usd_2014_15": ("2014-05-31", "2015-03-31"), "usd_2021_22": ("2021-05-31", "2022-09-30")}
STRONG_USD_THRESHOLD = 0.02

TARGETS = {"median_ending_value_min": 145_000, "prob_loss_max": 0.10, "prob_beat_cpi_min": 0.75,
           "max_drawdown_min": -0.25, "worst_calendar_year_min": -0.20}

NOTES = [
    "The 12 picks were chosen in 2026 partly on their 2018-2026 (OOS) results and are 2026 survivors, "
    "so the walk-forward backtest overstates what an investor in 2013-2017 could have achieved: "
    "the weights are out of sample, the asset list is not.",
    "Walk-forward weights at rebalance day t use daily returns up to t-1 only.",
    "Daily data are aligned on US trading days (AGG or BIL trades) with forward-fill of at most 5 days, "
    "so Taiwan, India and Canada holidays carry the last close; monthly results use month ends.",
    "NVDA, 2330.TW, SPY, ACWI and META prices in data/research/prices.csv end on 2026-10-23; the last "
    "week of October 2026 is carried flat for them (forward-fill, at most 5 days) and their order-list "
    "price is the 2026-10-23 close.",
    "Every pick is held: stocks 3-10%, funds 1-15%, other 1-10% (the 1% floor for funds and other assets "
    "is this builder's reading of 'every pick held'; method.md fixes only the 3% stock minimum).",
    "The headline walk-forward starts at the first quarter after all 12 picks have 126 common trading "
    "days (HYEM lists 2012-05-14), i.e. 2013-01; the estimation window grows to 3 years by 2015-05. "
    "In-sample metrics therefore cover 2013-01 to 2017-12 (60 months), not 2010-2017.",
    "Benchmarks (GUIDE_BENCH, SIXTY_FORTY, GLOBAL_6040) are fixed mixes reset at each calendar quarter, "
    "gross of trading costs, computed from month-end prices.",
    "EM bond funds and US assets carry zero FX by the method.md section 3 convention (USD-denominated); "
    "a local-currency fund such as EMLC would carry FX risk and is not held.",
    "Synthetic data are used only in tests/test_build.py; nothing in this file comes from synthetic data.",
]


def _pos(rows):
    return [{"ticker": t, "sleeve": s, "non_us": nu, "kind": k, "cost_bp": c} for t, s, nu, k, c in rows]


@dataclass
class Settings:
    rebalance: str = "quarterly"
    lookback_years: int = 3
    rule: bool = True
    overlay: bool = False
    min_non_us: float = 0.70
    drift_floor: float = 0.68
    mean_shrinkage: float = 0.5
    min_common_days: int = 126
    start: str = "2010-01-01"
    capital: float = 100_000.0
    horizon_years: int = 7
    stock_bounds: tuple = (0.03, 0.10)
    fund_bounds: tuple = (0.01, 0.15)
    other_bounds: tuple = (0.01, 0.10)
    mc_paths: int = 20_000
    mc_block: int = 6
    seed: int = 622
    objective: str = "max_sharpe"

    @property
    def lookback_days(self):
        return 252 * self.lookback_years


# ----------------------------------------------------------------------------- data
@dataclass
class Data:
    universe: pd.DataFrame
    prices_local: pd.DataFrame      # raw local closes (spike-filtered), own calendars
    fx: pd.DataFrame
    usd: pd.DataFrame               # USD prices on the US calendar (ffill <= 5 days)
    local: pd.DataFrame             # local prices on the US calendar (for the FX split)
    daily: pd.DataFrame             # daily USD returns, through BACKTEST_END
    daily_local: pd.DataFrame
    rf: pd.Series                   # BIL daily return
    monthly: pd.DataFrame           # month-end USD returns, full history through BACKTEST_END
    yields: pd.DataFrame
    overlay: pd.DataFrame
    cands: dict                     # candidate JSONs by ticker


def _cid(t):
    return t.replace(".", "_").replace("^", "_")


def load_data():
    pos = PICKS + RUNNERS
    tickers = sorted({p[0] for p in pos} | set(BENCH_TICKERS))
    files = {"prices": DATA / "prices.csv", "fx": DATA / "fx.csv", "yields": DATA / "yields.csv",
             "universe": PLAN / "universe.csv",
             "overlay": CAND / "overlays" / "pput_5pct_3m_monthly.csv"}
    missing = [str(p) for p in files.values() if not p.exists()]
    missing += [str(CAND / f"{_cid(t)}.json") for t, *_ in pos if not (CAND / f"{_cid(t)}.json").exists()]
    if missing:
        raise SystemExit("missing inputs (do not download; ask for them):\n  " + "\n  ".join(missing))
    uni = load_universe(files["universe"])
    rows = uni[uni["ticker"].isin(tickers)]
    absent = sorted(set(tickers) - set(rows["ticker"]))
    if absent:
        raise SystemExit(f"universe.csv has no row for {absent}")
    prices = read_wide_csv(files["prices"], columns=tickers)
    absent = sorted(set(tickers) - set(prices.columns))
    if absent:
        raise SystemExit(f"prices.csv has no column for {absent}")
    fx = read_wide_csv(files["fx"])
    usd_raw = usd_prices(prices, fx, rows)[tickers]
    cal = prices[["AGG", "BIL"]].dropna(how="all").index
    usd = pdata.align_to_calendar(usd_raw, cal)
    local = pdata.align_to_calendar(prices[tickers], cal)
    end = pd.Timestamp(BACKTEST_END)
    daily = usd.pct_change(fill_method=None).loc[:end].iloc[1:]
    daily_local = local.pct_change(fill_method=None).loc[:end].iloc[1:]
    rf = daily["BIL"].fillna(0.0)
    m = usd.loc[:end].resample("ME").last().pct_change(fill_method=None).iloc[1:]
    y = pd.read_csv(files["yields"], index_col=0, parse_dates=True).sort_index()
    ov = pd.read_csv(files["overlay"], index_col=0, parse_dates=True)
    cands = {t: json.loads((CAND / f"{_cid(t)}.json").read_text()) for t, *_ in pos}
    return Data(uni, prices, fx, usd, local, daily, daily_local, rf, m, y, ov, cands)


# ----------------------------------------------------------------------------- constraints
def sleeve_bounds(rule_band=True):
    sb = {"us_equity": ("us_equity", None, None), "intl_equity": ("intl_equity", None, None)}
    if rule_band:
        sb.update(equity=(("us_equity", "intl_equity"), TARGET_MIX["equity"] - BAND, TARGET_MIX["equity"] + BAND),
                  bonds=("em_bonds", TARGET_MIX["bonds"] - BAND, TARGET_MIX["bonds"] + BAND),
                  other=("other", max(0.0, TARGET_MIX["other"] - BAND), TARGET_MIX["other"] + BAND))
    return sb


def make_constraints(positions, st, rule=None, available=None, neutral=None, fund_cap=None):
    """The method.md section 10 constraint set for a list of positions."""
    rule = st.rule if rule is None else rule
    names = [p["ticker"] for p in positions]
    bnd = {"stock": st.stock_bounds, "fund": st.fund_bounds, "other": st.other_bounds}
    bounds = []
    for p in positions:
        lo, hi = bnd[p["kind"]]
        if p["kind"] == "fund" and fund_cap is not None:
            hi = fund_cap
        bounds.append((lo, hi))
    return O.build_constraints(names, [p["non_us"] for p in positions], [p["sleeve"] for p in positions],
                               sleeve_bounds(), bounds, st.min_non_us if rule else 0.0,
                               available=available, neutral=neutral)


def rule_constraints(positions, st, neutral=None):
    """The full rule set (always with the 70% floor), used to check any weights."""
    return make_constraints(positions, replace(st, rule=True), rule=True, neutral=neutral)


# ----------------------------------------------------------------------------- walk-forward
def optimizer_weights(R, rf, positions, st, rule=True, neutral=None, objective="max_sharpe",
                      grow_window=True):
    """weight_fn(i) for backtest.walk_forward: estimate on rows < i, optimise under the rules.

    Assets with fewer than st.min_common_days prices in the window are not
    available (pinned to 0); when fewer than four bond funds are available the
    fund cap is raised to max(15%, 45% / funds) so the sleeve band stays
    reachable (only the 2010-start variant needs this)."""
    lb = st.lookback_days
    Rn = R.to_numpy()
    rfn = rf.reindex(R.index).fillna(0.0).to_numpy()
    funds = np.array([p["kind"] == "fund" for p in positions])
    state = {"prev": None}

    def f(i):
        lo = max(0, i - lb)
        win, rwin = Rn[lo:i], rfn[lo:i]
        counts = np.isfinite(win).sum(axis=0)
        avail = counts >= st.min_common_days
        rows = np.isfinite(win[:, avail]).all(axis=1)
        if rows.sum() < st.min_common_days:
            raise O.InfeasibleError(f"only {rows.sum()} common days at {R.index[i].date()}")
        ex = win[rows][:, avail] - rwin[rows][:, None]
        mu_a, cov_a = O.estimate(ex, st.mean_shrinkage)
        n = len(positions)
        mu, cov = np.zeros(n), np.eye(n) * 1e-4
        idx = np.flatnonzero(avail)
        mu[idx] = mu_a
        cov[np.ix_(idx, idx)] = cov_a
        nf = int((funds & avail).sum())
        cap = max(st.fund_bounds[1], 0.45 / nf) if 0 < nf < 4 else None
        c = make_constraints(positions, st, rule=rule, available=avail, neutral=neutral, fund_cap=cap)
        prev = state["prev"]
        if objective == "min_variance":
            w = O.min_variance_constrained(cov, c, prev)
        else:
            w = O.max_sharpe_constrained(mu, cov, c, prev)
        state["prev"] = w
        return w

    return f


@dataclass
class Run:
    name: str
    positions: list
    walk: backtest.WalkResult
    monthly: pd.Series
    note: str = ""
    overlay_monthly: pd.Series = None   # overlay part of the monthly return (if any)


def first_rebalance(R, st, sched):
    """First scheduled day with all assets having st.min_common_days common prices before it."""
    ok = R.notna().all(axis=1).to_numpy()
    cum = np.r_[0, np.cumsum(ok)]          # cum[i] = complete rows before day i
    for i in np.flatnonzero(sched):
        lo = max(0, i - st.lookback_days)
        if cum[i] - cum[lo] >= st.min_common_days:
            return int(i)
    raise O.InfeasibleError("no rebalance day with enough common history")


def run_walk(name, d, positions, st, kind="optimized", fixed=None, rule=True, neutral=None,
             first=None, start=None, trigger=True, buy_hold=False, objective=None):
    tick = [p["ticker"] for p in positions]
    R = d.daily[tick]
    sched = backtest.rebalance_schedule(R.index, start or st.start, st.rebalance)
    if first is None:
        first = first_rebalance(R, st, sched)
    if buy_hold:
        sched = np.zeros(len(R), bool)
    nu = np.array([p["non_us"] for p in positions])
    if kind == "fixed":
        wf = np.array([fixed[t] for t in tick])
        fn = lambda i: wf
    else:
        fn = optimizer_weights(R, d.rf, positions, st, rule=rule, neutral=neutral,
                               objective=objective or st.objective)
    trig = None
    if trigger and rule and kind != "fixed" and not buy_hold:
        trig = lambda w: float(nu @ w) < st.drift_floor
    cost = np.array([p["cost_bp"] for p in positions]) / 1e4
    wr = backtest.walk_forward(R, fn, sched, cost, trig, first)
    return Run(name, positions, wr, backtest.to_monthly(wr.returns))


def guideline_weights(positions, split=None):
    """Exact 55/35/10, equal weight inside each sleeve; `split` = (US, intl) shares of the 55%."""
    eq_us, eq_intl = split or (None, None)
    by = {s: [p["ticker"] for p in positions if p["sleeve"] == s] for s in SLEEVES}
    w = {}
    if split is None:
        eq = by["us_equity"] + by["intl_equity"]
        w.update({t: TARGET_MIX["equity"] / len(eq) for t in eq})
    else:
        w.update({t: eq_us / len(by["us_equity"]) for t in by["us_equity"]})
        w.update({t: eq_intl / len(by["intl_equity"]) for t in by["intl_equity"]})
    w.update({t: TARGET_MIX["bonds"] / len(by["em_bonds"]) for t in by["em_bonds"]})
    w.update({t: TARGET_MIX["other"] / len(by["other"]) for t in by["other"]})
    return w


def with_overlay(run, d, h=1.0, name=None):
    """Add h x equity-sleeve weight (start of month) x overlay_return_h100 to the monthly return."""
    eq = [p["ticker"] for p in run.positions if p["sleeve"] in ("us_equity", "intl_equity")]
    w_eq = run.walk.holdings[eq].sum(axis=1).groupby(run.walk.holdings.index.to_period("M")).first()
    w_eq.index = w_eq.index.to_timestamp(how="end").normalize()
    ov = d.overlay["overlay_return_h100"].copy()
    ov.index = ov.index + pd.offsets.MonthEnd(0)
    part = (h * w_eq.reindex(run.monthly.index) * ov.reindex(run.monthly.index)).fillna(0.0)
    r = run.monthly + part
    return Run(name or run.name + "_overlay", run.positions, run.walk, r,
               note=f"protective put, h = {h:.3f} of the equity sleeve", overlay_monthly=part)


# ----------------------------------------------------------------------------- benchmarks
def fixed_mix_monthly(M, weights, freq="Q"):
    """Fixed weights reset at the start of each calendar quarter; drift within it."""
    w = pd.Series(weights)
    R = M[list(w.index)].dropna()
    q = R.index.to_period(freq)
    G = (1 + R).groupby(q).cumprod()
    lvl = (G * w).sum(axis=1)
    prev = lvl.groupby(q).shift(1).fillna(1.0)
    return (lvl / prev - 1)


# ----------------------------------------------------------------------------- metrics
def window_return(r, start, end):
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    n = len(pd.date_range(s, e, freq="ME")) - 1
    w = r[(r.index > s) & (r.index <= e)].dropna()
    if n <= 0 or len(w) < n:
        return None
    return float((1 + w).prod() - 1)


def strong_usd_months(y):
    s = y["USD_BROAD"].dropna()
    s.index = s.index + pd.offsets.MonthEnd(0)
    chg = s.pct_change(fill_method=None)
    return chg[chg >= STRONG_USD_THRESHOLD].index


def stress_block(r, bench, y):
    out = {k: {"start": s, "end": e, "return": window_return(r, s, e), "guide_bench": window_return(bench, s, e)}
           for k, (s, e) in STRESS.items()}
    months = strong_usd_months(y)
    rr = r.reindex(months).dropna()
    bb = bench.reindex(rr.index)
    out["strong_usd"] = {
        "definition": "months when the FRED broad dollar index (yields.csv USD_BROAD, monthly average) rose "
                      ">= 2% month on month; plus the 2014-06..2015-03 and 2021-06..2022-09 episodes",
        "n_months": int(len(rr)), "months": [str(x.date())[:7] for x in rr.index],
        "avg_return": float(rr.mean()) if len(rr) else None,
        "guide_bench": float(bb.mean()) if len(bb.dropna()) else None,
        **{k: {"start": s, "end": e, "return": window_return(r, s, e), "guide_bench": window_return(bench, s, e)}
           for k, (s, e) in USD_EPISODES.items()}}
    return out


def calendar_years(r):
    g = (1 + r).groupby(r.index.year)
    yrs = g.prod() - 1
    n = g.size()
    return {int(k): {"return": float(v), "months": int(n[k])} for k, v in yrs.items()}


def windows(r):
    return {"in_sample": r.loc[:IN_SAMPLE_END], "out_of_sample": r.loc[OOS_START:], "full": r}


def metric_set(r, bench, rf_m):
    out = {}
    for k, x in windows(r).items():
        x = x.dropna()
        m = stats.metrics_block(x, bench.reindex(x.index), rf_m.reindex(x.index)) if len(x) > 2 else {}
        cy = calendar_years(x) if len(x) else {}
        full = {y: v["return"] for y, v in cy.items() if v["months"] == 12}
        m["worst_calendar_year"] = min(full.values()) if full else None
        m["worst_calendar_year_label"] = min(full, key=full.get) if full else None
        out[k] = m
    return out


def series_block(r, capital):
    v = capital * (1 + r).cumprod()
    dd = v / v.cummax().clip(lower=capital) - 1
    start = r.index[0] - pd.offsets.MonthEnd(1)
    return {"dates": [str(start.date())] + [str(x.date()) for x in r.index],
            "value_100k": [capital] + v.round(2).tolist(),
            "drawdown": [0.0] + dd.round(6).tolist()}


def rule_check_rows(run, cons):
    rows = []
    for dt, w in run.walk.weights.iterrows():
        chk = O.check_weights(w.to_numpy(), cons, tol=1e-6)
        rows.append({"date": str(dt.date()), "non_us_share": chk["non_us_share"],
                     "sleeves": chk["groups"], "non_us_ok": chk["non_us_ok"], "sleeves_ok": chk["groups_ok"],
                     "bounds_ok": chk["bounds_ok"], "bound_violations": chk["bound_violations"],
                     "ok": chk["ok"], "binding": O.binding(w.to_numpy(), cons)})
    return rows


def drift_path(run):
    nu = np.array([p["non_us"] for p in run.positions])
    h = run.walk.holdings
    s = pd.Series(h.to_numpy() @ nu, index=h.index)
    m = s.resample("ME").last()
    return {"dates": [str(x.date()) for x in m.index], "non_us_share": m.round(6).tolist(),
            "min_daily": float(s.min()), "mean_daily": float(s.mean()),
            "days_below_0.70": int((s < 0.70 - 1e-9).sum()), "days_below_0.68": int((s < 0.68 - 1e-9).sum()),
            "drift_triggered_rebalances": [str(x.date()) for x in run.walk.triggered]}


def cost_turnover(run):
    w = run.walk
    years = len(run.monthly) / 12
    t = w.turnover
    init_cost = float(w.costs.iloc[0])
    later = float(w.costs.iloc[1:].sum())
    return ({"rebalances": int(len(t)), "initial_one_way": float(t.iloc[0]) if len(t) else None,
             "avg_one_way_per_rebalance": float(t.iloc[1:].mean()) if len(t) > 1 else 0.0,
             "annual_one_way": float(t.iloc[1:].sum() / years) if len(t) > 1 else 0.0},
            {"initial_purchase": init_cost, "rebalancing_total": later,
             "annual_drag": (init_cost + later) / years, "annual_drag_ex_initial": later / years})


def describe(run, d, bench, rf_m, positions_rule, st, overlay_info=None, extra=None):
    r = run.monthly
    cons = rule_constraints(positions_rule, st)
    rc = rule_check_rows(run, cons)
    turn, cost = cost_turnover(run)
    last = run.walk.weights.iloc[-1]
    out = {
        "weights": {k: float(v) for k, v in last.items()},
        "weights_as_of": str(run.walk.weights.index[-1].date()),
        "monthly": series_block(r, st.capital),
        "metrics": metric_set(r, bench, rf_m),
        "calendar_years": calendar_years(r),
        "stress": stress_block(r, bench, d.yields),
        "rule_checks": {"all_rebalances_ok": all(x["ok"] for x in rc),
                        "non_us_ok_all": all(x["non_us_ok"] for x in rc),
                        "sleeves_ok_all": all(x["sleeves_ok"] for x in rc),
                        "bounds_ok_all": all(x["bounds_ok"] for x in rc),
                        "min_target_non_us_share": min(x["non_us_share"] for x in rc),
                        "rebalances": rc, "realised_non_us": drift_path(run)},
        "turnover": turn, "cost_drag": cost, "note": run.note,
    }
    if overlay_info:
        out["overlay"] = overlay_info
    if extra:
        out.update(extra)
    return out


def describe_bench(name, r_full, comp_index, bench, rf_m, st, d):
    r = r_full.reindex(comp_index)
    w = FIXED_BENCHES[name]
    nu = sum(w[k] * BENCH_NON_US[k] for k in w)
    return {"weights": w, "monthly": series_block(r, st.capital), "metrics": metric_set(r, bench, rf_m),
            "calendar_years": calendar_years(r),
            "stress": stress_block(r_full, bench, d.yields),
            "rule_checks": {"non_us_share": nu, "non_us_ok": nu >= st.min_non_us - 1e-9,
                            "note": "fixed mix, quarterly reset; ACWI non-US share 0.36 is approximate"
                            if "ACWI" in w else "fixed mix, quarterly reset"},
            "turnover": None, "cost_drag": None,
            "note": "gross of trading costs; stress windows use the benchmark's full history"}


# ----------------------------------------------------------------------------- attribution
def attribution(run, d, include_overlay=False):
    h = run.walk.holdings
    tick = list(h.columns)
    R = d.daily[tick].reindex(h.index).fillna(0.0)
    contrib = h * R
    per = contrib.index.to_period("M")
    cm = contrib.groupby(per).sum()
    cm.index = cm.index.to_timestamp(how="end").normalize()
    sleeve_of = {p["ticker"]: p["sleeve"] for p in run.positions}
    by_sleeve = cm.T.groupby(pd.Series(sleeve_of)).sum().T
    costs = run.walk.costs.groupby(per).sum()
    costs.index = costs.index.to_timestamp(how="end").normalize()
    by_sleeve["costs"] = -costs
    if include_overlay and run.overlay_monthly is not None:
        by_sleeve["overlay"] = run.overlay_monthly.reindex(by_sleeve.index).fillna(0.0)
    by_sleeve["residual_compounding"] = run.monthly.reindex(by_sleeve.index) - by_sleeve.sum(axis=1)
    # local vs FX for the three local listings
    fxs = {}
    for t in FX_STOCKS:
        if t not in tick:
            continue
        rl = d.daily_local[t].reindex(h.index).fillna(0.0)
        fx_part = h[t] * (R[t] - rl)
        loc_part = h[t] * rl
        a = pd.DataFrame({"local": loc_part, "fx": fx_part}).groupby(per).sum()
        a.index = a.index.to_timestamp(how="end").normalize()
        fxs[t] = a
    out = {}
    for k, idx in {"in_sample": (None, IN_SAMPLE_END), "out_of_sample": (OOS_START, None),
                   "full": (None, None)}.items():
        sl = by_sleeve.loc[idx[0]:idx[1]]
        n = len(sl)
        blk = {"months": n, "sum_of_monthly_contributions": {c: float(sl[c].sum()) for c in sl.columns},
               "annualised_contribution": {c: float(sl[c].mean() * 12) for c in sl.columns},
               "portfolio_annualised_mean": float(run.monthly.loc[idx[0]:idx[1]].mean() * 12)}
        fxb = {}
        for t, a in fxs.items():
            aa = a.loc[idx[0]:idx[1]]
            fxb[t] = {"currency": FX_STOCKS[t], "local_annualised": float(aa["local"].mean() * 12),
                      "fx_annualised": float(aa["fx"].mean() * 12)}
        tot_l = sum(v["local_annualised"] for v in fxb.values())
        tot_f = sum(v["fx_annualised"] for v in fxb.values())
        blk["local_vs_fx"] = {"positions": fxb, "intl_local_annualised": tot_l, "intl_fx_annualised": tot_f,
                              "other_positions_fx": 0.0}
        out[k] = blk
    out["monthly_by_sleeve"] = {"dates": [str(x.date()) for x in by_sleeve.index],
                                **{c: by_sleeve[c].round(6).tolist() for c in by_sleeve.columns}}
    out["method"] = ("contribution = start-of-day weight x daily USD return, summed by month and sleeve; "
                     "costs and the overlay are separate lines; residual = monthly compounded return minus "
                     "the sum (cross-day compounding). FX part of a local listing = weight x (USD return - "
                     "local return); EM bond funds and US assets are USD-priced and have zero FX by the "
                     "method.md s3 convention (EMLC-type local-currency funds would not).")
    return out


# ----------------------------------------------------------------------------- ex-ante
def consensus(d, tick):
    return np.array([d.cands[t]["expected_return_7y"]["consensus_usd"] for t in tick], float)


def ex_ante_weights(d, positions, st, rule=True, neutral=None):
    """Max Sharpe with mu = consensus_usd (forward), LW covariance from the last lookback of daily data."""
    tick = [p["ticker"] for p in positions]
    win = d.daily[tick].iloc[-st.lookback_days:].dropna()
    rfw = d.rf.reindex(win.index).fillna(0.0)
    _, cov = O.estimate(win.sub(rfw, axis=0).to_numpy(), st.mean_shrinkage)
    rf_fwd = float(d.yields["US_3M"].dropna().iloc[-1]) / 100
    mu = consensus(d, tick) - rf_fwd
    c = make_constraints(positions, st, rule=rule, neutral=neutral)
    w = O.max_sharpe_constrained(mu, cov, c)
    return w, {"rf_forward": rf_fwd, "rf_source": f"yields.csv US_3M {d.yields['US_3M'].dropna().index[-1].date()}",
               "cov_window": [str(win.index[0].date()), str(win.index[-1].date())],
               "expected_return": float(w @ (mu + rf_fwd)), "vol": float(np.sqrt(w @ cov @ w)),
               "sharpe": float((w @ mu) / np.sqrt(w @ cov @ w)), "binding": O.binding(w, c),
               "check": O.check_weights(w, c)}


def last_price(d, t):
    """Last local close on or before the data end, its date, FX and USD price."""
    s = d.prices_local[t].dropna()
    dt, p = s.index[-1], float(s.iloc[-1])
    row = d.universe.set_index("ticker").loc[t]
    ccy = row["currency"] if row["currency"] in d.fx.columns else "USD"
    rate = 1.0 if ccy == "USD" else float(d.fx[ccy].loc[:dt].dropna().iloc[-1])
    return dt, p, ccy, rate, row


def order_list(d, positions, weights, st):
    rows = []
    for p, w in zip(positions, weights):
        t = p["ticker"]
        dt, px, ccy, rate, row = last_price(d, t)
        usd = px * rate
        dollars = w * st.capital
        open_end = row["listing"].strip().lower() == "open-end"
        shares = round(dollars / usd, 3) if open_end else math.floor(dollars / usd)
        rows.append({"ticker": t, "name": row["name"], "sleeve": p["sleeve"], "weight": float(w),
                     "dollars": float(dollars), "shares": shares, "fractional": open_end,
                     "price_local": px, "currency": ccy, "fx_usd_per_unit": rate, "price_usd": usd,
                     "price_date": str(dt.date()), "invested_usd": float(shares * usd),
                     "non_us_share": p["non_us"], "exchange": row["listing"],
                     "expected_return_7y": d.cands[t]["expected_return_7y"]["consensus_usd"],
                     "adr": (row["usd_ticker"] if row["usd_ticker"] and row["usd_ticker"] != t else None)})
    return rows


# ----------------------------------------------------------------------------- frontiers
def frontier_set(d, positions, st, port_points):
    tick = [p["ticker"] for p in positions]
    M = d.monthly[tick].dropna()
    S = F.shrunk_cov(M.to_numpy())
    rf = float(d.monthly["BIL"].reindex(M.index).mean() * 12)
    out = {"sample": [str(M.index[0].date()), str(M.index[-1].date())], "months": len(M),
           "rf_bil_average": rf, "tickers": tick,
           "cov_method": "research.frontier.shrunk_cov (monthly USD, 30% toward the diagonal)"}
    for lab, mu in {"ex_ante": consensus(d, tick), "ex_post": M.mean().to_numpy() * 12}.items():
        blk = {"mu": mu.tolist()}
        for rlab, rule in {"rule_70": True, "no_rule": False}.items():
            c = make_constraints(positions, st, rule=rule)
            blk[rlab] = F.frontier_constrained(mu, S, tick, rf, c, points=25)
        blk["portfolios"] = {k: {"ret": float(w @ mu), "vol": float(np.sqrt(w @ S @ w)),
                                 "sharpe": float((w @ mu - rf) / np.sqrt(w @ S @ w)),
                                 "weights": {t: float(x) for t, x in zip(tick, w)}}
                             for k, w in port_points.items()}
        out[lab] = blk
    out["cov"] = S.tolist()
    return out


# ----------------------------------------------------------------------------- Monte Carlo
def inflation_rate(y):
    c = y["US_CPI"].dropna()
    c = c.loc["2010-01-01":]
    yrs = (len(c) - 1) / 12
    return float((c.iloc[-1] / c.iloc[0]) ** (1 / yrs) - 1), [str(c.index[0].date()), str(c.index[-1].date())]


def monte_carlo(r, drift, st, infl):
    s = MonteCarloSettings(n_paths=st.mc_paths, horizon_years=st.horizon_years,
                           block_months=st.mc_block, seed=st.seed)
    X = pd.DataFrame({"PORT": r.dropna()})
    out = {}
    for lab, tgt in {"forward": {"PORT": drift}, "historical": None}.items():
        res = MC.simulate(X, s, targets=tgt, weights={"PORT": 1.0})
        # same draws again (same seed, same first use of the generator) for the extra statistics
        R = X.copy()
        if tgt:
            R["PORT"] = MC._scale_to(R["PORT"], drift)
        rng = np.random.default_rng(s.seed)
        idx = MC.bootstrap_paths(R.to_numpy(), s.horizon_years * 12, s.n_paths, s.block_months, rng)
        paths = np.cumprod(1 + R.to_numpy()[:, 0][idx], axis=1)
        term = paths[:, -1]
        dd = (paths / np.maximum.accumulate(np.maximum(paths, 1.0), axis=1) - 1).min(axis=1)
        p = res["PORTFOLIO"]
        out[lab] = {
            "drift_annual": drift if tgt else float(np.exp(np.log1p(X["PORT"]).mean() * 12) - 1),
            "median_ending_value": float(np.median(term) * st.capital),
            "p5_ending_value": float(np.percentile(term, 5) * st.capital),
            "p95_ending_value": float(np.percentile(term, 95) * st.capital),
            "prob_nominal_loss": float((term < 1).mean()),
            "prob_beat_inflation": float((term > (1 + infl) ** st.horizon_years).mean()),
            "median_path_max_drawdown": float(np.median(dd)),
            "prob_path_drawdown_worse_than_25pct": float((dd < -0.25).mean()),
            "annualised_percentiles": p["annualised"],
            "fan": {"months": list(range(1, s.horizon_years * 12 + 1)),
                    **{k: (np.array(v) * st.capital).round(0).tolist() for k, v in p["fan"].items()}},
            "check_median_matches_simulate": abs(float(p["terminal_100k"]["50"]) - float(np.median(term) * 100_000)) < 1.0,
        }
    out["settings"] = {"paths": s.n_paths, "block_months": s.block_months, "seed": s.seed,
                       "horizon_years": s.horizon_years, "method": "research.montecarlo.simulate, circular block "
                       "bootstrap of the chosen portfolio's walk-forward monthly returns; forward drift scales "
                       "the series so its geometric mean equals the weighted consensus_usd of the picks"}
    return out


def evaluate_targets(mc_forward, metrics_full, infl):
    t = TARGETS
    chk = {
        "median_ending_value": {"value": mc_forward["median_ending_value"], "target": f">= {t['median_ending_value_min']}",
                                "pass": mc_forward["median_ending_value"] >= t["median_ending_value_min"]},
        "prob_nominal_loss": {"value": mc_forward["prob_nominal_loss"], "target": f"<= {t['prob_loss_max']}",
                              "pass": mc_forward["prob_nominal_loss"] <= t["prob_loss_max"]},
        "prob_beat_inflation": {"value": mc_forward["prob_beat_inflation"], "target": f">= {t['prob_beat_cpi_min']}",
                                "pass": mc_forward["prob_beat_inflation"] >= t["prob_beat_cpi_min"],
                                "inflation_assumed": infl},
        "max_drawdown": {"value": metrics_full.get("max_drawdown"), "target": f">= {t['max_drawdown_min']}",
                         "pass": (metrics_full.get("max_drawdown") or -1) >= t["max_drawdown_min"]},
        "worst_calendar_year": {"value": metrics_full.get("worst_calendar_year"),
                                "target": f">= {t['worst_calendar_year_min']}",
                                "pass": (metrics_full.get("worst_calendar_year") or -1) >= t["worst_calendar_year_min"]},
    }
    chk["all_pass"] = all(v["pass"] for v in chk.values())
    return chk


# ----------------------------------------------------------------------------- helpers
def clean(o):
    """JSON-safe: floats rounded to 6 decimals, NaN/inf -> None, numpy -> python."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if not math.isfinite(f) else round(f, 6)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (pd.Timestamp,)):
        return str(o.date())
    return o


def headline_row(name, entry):
    out = {"portfolio": name}
    for k in ("in_sample", "out_of_sample", "full"):
        m = entry["metrics"][k]
        for f in ("cagr", "vol", "sharpe", "sortino", "info_ratio", "max_drawdown", "calmar", "worst_calendar_year"):
            out[f"{k}_{f}"] = m.get(f)
    rc = entry["rule_checks"]
    out["non_us_share"] = (rc.get("realised_non_us", {}).get("mean_daily") if "realised_non_us" in rc
                           else rc.get("non_us_share"))
    out["rules_ok"] = rc.get("all_rebalances_ok", rc.get("non_us_ok"))
    out["annual_turnover"] = (entry["turnover"] or {}).get("annual_one_way")
    out["annual_cost_drag"] = (entry["cost_drag"] or {}).get("annual_drag")
    return out


def variant_row(label, run, bench, rf_m, st, **kw):
    ms = metric_set(run.monthly, bench, rf_m)
    turn, cost = cost_turnover(run)
    row = {"variant": label, **kw, "start": str(run.monthly.index[0].date())}
    for k in ("in_sample", "out_of_sample", "full"):
        for f in ("cagr", "vol", "sharpe", "info_ratio", "max_drawdown"):
            row[f"{k}_{f}"] = ms[k].get(f)
    row["annual_turnover"] = turn["annual_one_way"]
    row["annual_cost_drag"] = cost["annual_drag"]
    row["rebalances"] = turn["rebalances"]
    return row


# ----------------------------------------------------------------------------- charts
def charts(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    path.mkdir(parents=True, exist_ok=True)
    P = res["portfolios"]
    show = ["optimized", "optimized_overlay", "guideline", "guideline_feasible", "no_rule",
            "GUIDE_BENCH", "SIXTY_FORTY", "GLOBAL_6040"]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for k in show:
        m = P[k]["monthly"]
        ax.plot(pd.to_datetime(m["dates"]), m["value_100k"], lw=2.2 if k == "optimized" else 1.2, label=k)
    ax.axvline(pd.Timestamp(OOS_START), color="grey", ls="--", lw=1)
    ax.set_ylabel("Value of $100,000 (USD)")
    ax.set_title("Walk-forward growth, net of costs (dashed line: out-of-sample start)")
    ax.legend(frameon=False, fontsize=8, ncol=2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path / "growth.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    for k in ["optimized", "optimized_overlay", "guideline_feasible", "GUIDE_BENCH", "SIXTY_FORTY"]:
        m = P[k]["monthly"]
        ax.plot(pd.to_datetime(m["dates"]), np.array(m["drawdown"]) * 100, lw=1.3, label=k)
    ax.axhline(-25, color="red", ls=":", lw=1, label="-25% budget")
    ax.set_ylabel("Drawdown (%)")
    ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path / "drawdown.png", dpi=120)
    plt.close(fig)

    for lab in ("ex_ante", "ex_post"):
        fr = res["frontiers"][lab]
        fig, ax = plt.subplots(figsize=(8, 5.5))
        for rlab, col in (("rule_70", "C0"), ("no_rule", "C1")):
            f = fr[rlab]
            if f is None:
                continue
            ax.plot([p["vol"] for p in f["points"]], [p["ret"] for p in f["points"]], "-o", ms=3, color=col,
                    label=f"frontier {rlab}")
            ax.scatter(f["max_sharpe"]["vol"], f["max_sharpe"]["ret"], marker="*", s=160, color=col,
                       label=f"tangency {rlab}")
            ax.scatter(f["min_variance"]["vol"], f["min_variance"]["ret"], marker="s", s=50, color=col)
        for a in fr["rule_70"]["assets"]:
            ax.scatter(a["vol"], a["ret"], s=12, color="grey")
            ax.annotate(a["key"], (a["vol"], a["ret"]), fontsize=7, color="grey")
        for k, v in fr["portfolios"].items():
            ax.scatter(v["vol"], v["ret"], marker="D", s=40)
            ax.annotate(k, (v["vol"], v["ret"]), fontsize=8)
        ax.set_xlabel("Volatility (annual)")
        ax.set_ylabel("Expected return (annual)" if lab == "ex_ante" else "Realised mean return (annual)")
        ax.set_title(f"Efficient frontier, {lab.replace('_', '-')} (squares: minimum variance)")
        ax.legend(frameon=False, fontsize=8)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(path / f"frontier_{lab}.png", dpi=120)
        plt.close(fig)

    mc = res["monte_carlo"]["forward"]["fan"]
    fig, ax = plt.subplots(figsize=(9, 5))
    x = mc["months"]
    ax.fill_between(x, mc["5"], mc["95"], alpha=0.2, label="5-95%")
    ax.fill_between(x, mc["25"], mc["75"], alpha=0.35, label="25-75%")
    ax.plot(x, mc["50"], lw=2, label="median")
    ax.axhline(145_000, color="green", ls=":", label="$145,000 target")
    ax.axhline(100_000, color="grey", ls="--", lw=1)
    ax.set_xlabel("Months from today")
    ax.set_ylabel("USD")
    ax.set_title("Monte Carlo, 7 years, forward drift (block bootstrap)")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path / "montecarlo_fan.png", dpi=120)
    plt.close(fig)

    wh = pd.read_csv(OUT / "weights_history_optimized.csv", index_col=0, parse_dates=True)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.stackplot(wh.index, wh.T.to_numpy(), labels=wh.columns, step="post",
                 colors=plt.get_cmap("tab20").colors[:wh.shape[1]])
    ax.set_ylim(0, 1)
    ax.set_title("Optimized portfolio: target weights at each rebalance")
    ax.legend(frameon=False, fontsize=7, ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(path / "weights.png", dpi=120)
    plt.close(fig)

    at = res["attribution"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for ax, key in zip(axes, ("optimized", "optimized_overlay")):
        a = at[key]
        cats = [c for c in a["full"]["annualised_contribution"] if c != "residual_compounding"]
        xs = np.arange(len(cats))
        for j, win in enumerate(("in_sample", "out_of_sample")):
            ax.bar(xs + (j - 0.5) * 0.38, [a[win]["annualised_contribution"][c] * 100 for c in cats], 0.38,
                   label=win)
        ax.set_xticks(xs, cats, rotation=30, fontsize=8)
        ax.set_title(key)
        ax.axhline(0, color="black", lw=0.8)
        ax.grid(alpha=0.3, axis="y")
    axes[0].set_ylabel("Annualised contribution (% per year)")
    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path / "attribution.png", dpi=120)
    plt.close(fig)


# ----------------------------------------------------------------------------- pipeline
def headline(d, st, positions=None):
    positions = positions or _pos(PICKS)
    run = run_walk("optimized", d, positions, st, rule=st.rule)
    if st.overlay:
        run = with_overlay(run, d, 1.0, "optimized_overlay")
    return run


def full_run(st, write=True, verbose=True):
    t0 = time.time()
    log = (lambda *a: print(*a, flush=True)) if verbose else (lambda *a: None)
    d = load_data()
    picks = _pos(PICKS)
    tick = [p["ticker"] for p in picks]
    M = d.monthly
    rf_m = M["BIL"]
    guide_full = fixed_mix_monthly(M, FIXED_BENCHES["GUIDE_BENCH"])
    st_rule = replace(st, rule=True)

    # --- feasibility
    feas = {}
    for lab, kw in {"rule_70": dict(rule=True), "no_rule": dict(rule=False),
                    "gold_neutral": dict(rule=True, neutral=["IAU", "SLV"])}.items():
        feas[lab] = O.feasible_region(make_constraints(picks, st, **kw))
    log("feasible region (rule 70%):", json.dumps(clean(feas["rule_70"]["groups"])),
        "non-US", clean(feas["rule_70"]["non_us_share"]))

    # --- headline walk-forward portfolios
    runs = {}
    runs["optimized"] = run_walk("optimized", d, picks, st_rule, rule=True)
    first_day = runs["optimized"].walk.returns.index[0]
    first_i = int(d.daily.index.get_loc(first_day))
    log(f"walk-forward from {first_day.date()} ({time.time() - t0:.0f}s)")
    runs["no_rule"] = run_walk("no_rule", d, picks, st, rule=False, first=first_i)
    runs["min_variance"] = run_walk("min_variance", d, picks, st_rule, rule=True, first=first_i,
                                    objective="min_variance")
    g = guideline_weights(picks)
    gf = guideline_weights(picks, (0.20, 0.35))
    runs["guideline"] = run_walk("guideline", d, picks, st, kind="fixed", fixed=g, first=first_i)
    runs["guideline_feasible"] = run_walk("guideline_feasible", d, picks, st, kind="fixed", fixed=gf, first=first_i)
    runs["optimized_overlay"] = with_overlay(runs["optimized"], d, 1.0, "optimized_overlay")
    comp_index = runs["optimized"].monthly.index
    bench = guide_full.reindex(comp_index)

    # ex-ante weights (order list) and the implementable put hedge ratio at 1 XSP contract
    w_ex, ex_info = ex_ante_weights(d, picks, st_rule)
    eq_mask = np.array([p["sleeve"] in ("us_equity", "intl_equity") for p in picks])
    h_contract = float(d.overlay["hedge_ratio"].iloc[-1] * 55_000 / (w_ex[eq_mask].sum() * st.capital))
    runs["optimized_overlay_1contract"] = with_overlay(runs["optimized"], d, h_contract, "optimized_overlay_1contract")

    # basis of the S&P put against the international sleeve
    hold = runs["optimized"].walk.holdings
    intl = [p["ticker"] for p in picks if p["sleeve"] == "intl_equity"]
    eq_all = [p["ticker"] for p in picks if p["sleeve"] in ("us_equity", "intl_equity")]
    def sleeve_ret(names):
        c = (hold[names] * d.daily[names].reindex(hold.index).fillna(0)).sum(axis=1) / hold[names].sum(axis=1)
        return backtest.to_monthly(c)
    intl_m, eq_m = sleeve_ret(intl), sleeve_ret(eq_all)
    spy_m = M["SPY"].reindex(comp_index)
    oos = slice(OOS_START, None)
    overlay_basis = {
        "corr_oos_intl_sleeve_vs_spy": float(intl_m.loc[oos].corr(spy_m.loc[oos])),
        "corr_oos_equity_sleeve_vs_spy": float(eq_m.loc[oos].corr(spy_m.loc[oos])),
        "corr_in_sample_intl_sleeve_vs_spy": float(intl_m.loc[:IN_SAMPLE_END].corr(spy_m.loc[:IN_SAMPLE_END])),
        "h_economic": 1.0, "h_one_xsp_contract_today": h_contract,
        "note": "The put is on the S&P 500 and is applied to the whole equity sleeve (US and international), "
                "so the hedge carries basis risk: it pays when SPY falls, not when TSMC, Bajaj or Constellation "
                "fall. At $100,000 one XSP contract over-hedges the equity sleeve (h above 1); fractions of a "
                "contract are not possible. Series: overlay_return_h100 (net of costs), scaled to the drifting "
                "equity-sleeve weight at the start of each month."}

    P = {}
    for k in ("guideline", "guideline_feasible", "optimized", "optimized_overlay", "no_rule", "min_variance",
              "optimized_overlay_1contract"):
        extra = None
        if k.startswith("optimized_overlay"):
            extra = {"overlay": {**overlay_basis, "h_used": 1.0 if k == "optimized_overlay" else h_contract}}
        P[k] = describe(runs[k], d, bench, rf_m, picks, st)
        if extra:
            P[k].update(extra)
    P["guideline"]["note"] = ("exact 55/35/10, equal weight inside each sleeve, quarterly; breaks the 70% rule "
                              "(27.5% US stocks + 10% metals = 37.5% US/neutral) and is shown anyway")
    P["guideline_feasible"]["note"] = ("55/35/10 with equity 20% US (equal) / 35% international (equal); meets the "
                                       "70% floor exactly but breaks the 10% single-stock cap (11.67% each)")
    for name, w in FIXED_BENCHES.items():
        r_full = fixed_mix_monthly(M, w)
        P[name] = describe_bench(name, r_full, comp_index, bench, rf_m, st, d)

    # --- variants: rebalance x lookback, plus the 2010-start variant and buy-and-hold
    variants = []
    for freq in ("monthly", "quarterly", "semiannual", "annual"):
        for lb in (3, 5):
            stv = replace(st_rule, rebalance=freq, lookback_years=lb)
            rv = runs["optimized"] if (freq, lb) == (st.rebalance, st.lookback_years) else \
                run_walk(f"opt_{freq}_{lb}y", d, picks, stv, rule=True, first=first_i)
            variants.append(variant_row(f"optimized {freq} {lb}y", rv, bench, rf_m, stv,
                                        rebalance=freq, lookback_years=lb, rule=True))
            log(f"variant {freq} {lb}y done ({time.time() - t0:.0f}s)")
    bh = run_walk("buy_hold", d, picks, st_rule, kind="optimized", rule=True, first=first_i, buy_hold=True)
    variants.append(variant_row("buy-and-hold from the first optimized weights", bh, bench, rf_m, st_rule,
                                rebalance="none", lookback_years=st.lookback_years, rule=True))
    variants.append(variant_row("min variance quarterly 3y", runs["min_variance"], bench, rf_m, st_rule,
                                rebalance=st.rebalance, lookback_years=st.lookback_years, rule=True))
    variants.append(variant_row("no 70% rule quarterly 3y", runs["no_rule"], bench, rf_m, st,
                                rebalance=st.rebalance, lookback_years=st.lookback_years, rule=False))
    # 2010-start variant: sleeves that exist; before CEMB/HYEM list, the fund cap rises to 22.5%
    st10 = replace(st_rule, min_common_days=126)
    r10 = run_walk("opt_2010", d, picks, st10, rule=True, start="2010-01-01",
                   first=int(np.flatnonzero(backtest.rebalance_schedule(d.daily.index, "2010-01-01", st.rebalance))[0]))
    v10 = variant_row("optimized quarterly 3y, 2010 start (assets as they list)", r10,
                      guide_full.reindex(r10.monthly.index), rf_m, st10, rebalance=st.rebalance,
                      lookback_years=st.lookback_years, rule=True)
    rc10 = rule_check_rows(r10, rule_constraints(picks, st))
    v10["rebalances_breaking_fund_cap"] = sum(1 for x in rc10 if not x["bounds_ok"])
    v10["note"] = ("AVGO joins once it has 126 days in the window; CEMB and HYEM join from 2012-11; until then "
                   "PYEMX and EMB carry the bond sleeve with a 22.5% fund cap (a deviation from the 15% cap, "
                   "flagged as bounds failures in the rule check)")
    variants.append(v10)
    log(f"variants done ({time.time() - t0:.0f}s)")

    # --- adjustments: rebalancing vs buy-and-hold
    def diff(a, b, k):
        ma, mb = metric_set(a.monthly, bench, rf_m), metric_set(b.monthly, bench, rf_m)
        return {w: {"cagr_diff": (ma[w].get("cagr") or 0) - (mb[w].get("cagr") or 0),
                    "max_drawdown_diff": (ma[w].get("max_drawdown") or 0) - (mb[w].get("max_drawdown") or 0),
                    "sharpe_diff": (ma[w].get("sharpe") or 0) - (mb[w].get("sharpe") or 0)}
                for w in ("in_sample", "out_of_sample", "full")}
    bh_desc = describe(bh, d, bench, rf_m, picks, st)
    adj = {"rebalanced_minus_buy_hold": diff(runs["optimized"], bh, "x"),
           "buy_and_hold": {"metrics": bh_desc["metrics"], "monthly": bh_desc["monthly"],
                            "realised_non_us": bh_desc["rule_checks"]["realised_non_us"],
                            "first_weights": {t: float(x) for t, x in zip(tick, bh.walk.weights.iloc[0])}},
           "weight_changes": [], "weights_history_csv": "reports/final/weights_history_optimized.csv"}
    wh = runs["optimized"].walk.weights
    prev = None
    for dt, w in wh.iterrows():
        chg = None if prev is None else {t: float(w[t] - prev[t]) for t in tick}
        adj["weight_changes"].append({"date": str(dt.date()), "weights": {t: float(w[t]) for t in tick},
                                      "change": chg, "turnover_one_way": float(runs["optimized"].walk.turnover[dt]),
                                      "drift_triggered": dt in runs["optimized"].walk.triggered})
        prev = w
    dd_ = adj["rebalanced_minus_buy_hold"]
    adj["verdict"] = (
        "Rebalancing (net of costs) vs buy-and-hold: OOS CAGR {:+.2%}, OOS max drawdown {:+.2%} "
        "(positive = rebalanced shallower), OOS Sharpe {:+.2f}; full CAGR {:+.2%}. The buy-and-hold "
        "portfolio's non-US share drifted to a minimum of {:.1%}, so it would have broken the 70% rule."
    ).format(dd_["out_of_sample"]["cagr_diff"], dd_["out_of_sample"]["max_drawdown_diff"],
             dd_["out_of_sample"]["sharpe_diff"], dd_["full"]["cagr_diff"],
             bh_desc["rule_checks"]["realised_non_us"]["min_daily"])

    # --- attribution
    att = {"optimized": attribution(runs["optimized"], d),
           "optimized_overlay": attribution(runs["optimized_overlay"], d, include_overlay=True)}

    # --- sensitivity
    base_m = metric_set(runs["optimized"].monthly, bench, rf_m)
    pool = {p["ticker"]: p for p in _pos(PICKS + RUNNERS)}
    sens = {"swaps": [], "base_oos_sharpe": base_m["out_of_sample"].get("sharpe"),
            "base_oos_max_drawdown": base_m["out_of_sample"].get("max_drawdown")}
    for out_t, in_t in SWAPS.items():
        pos2 = [pool[in_t] if p["ticker"] == out_t else p for p in picks]
        try:
            rs = run_walk(f"swap_{out_t}", d, pos2, st_rule, rule=True, first=first_i)
            ms = metric_set(rs.monthly, bench, rf_m)
            sens["swaps"].append({"out": out_t, "in": in_t, "oos_sharpe": ms["out_of_sample"].get("sharpe"),
                                  "oos_max_drawdown": ms["out_of_sample"].get("max_drawdown"),
                                  "oos_cagr": ms["out_of_sample"].get("cagr"),
                                  "oos_sharpe_change": ms["out_of_sample"]["sharpe"] - sens["base_oos_sharpe"],
                                  "oos_max_drawdown_change": ms["out_of_sample"]["max_drawdown"] - sens["base_oos_max_drawdown"],
                                  "in_sample_sharpe": ms["in_sample"].get("sharpe")})
        except O.InfeasibleError as e:
            sens["swaps"].append({"out": out_t, "in": in_t, "error": str(e)})
    rg = run_walk("gold_neutral", d, picks, st_rule, rule=True, neutral=["IAU", "SLV"], first=first_i)
    mg = metric_set(rg.monthly, bench, rf_m)
    w_exg, exg = ex_ante_weights(d, picks, st_rule, neutral=["IAU", "SLV"])
    sens["gold_neutral"] = {
        "definition": "IAU and SLV treated as neutral: the 70% floor applies to the rest of the portfolio "
                      "(sum(w x non_us) >= 0.70 x (1 - w_IAU - w_SLV))",
        "oos_sharpe": mg["out_of_sample"].get("sharpe"), "oos_max_drawdown": mg["out_of_sample"].get("max_drawdown"),
        "oos_cagr": mg["out_of_sample"].get("cagr"), "in_sample_sharpe": mg["in_sample"].get("sharpe"),
        "oos_sharpe_change": mg["out_of_sample"]["sharpe"] - sens["base_oos_sharpe"],
        "oos_max_drawdown_change": mg["out_of_sample"]["max_drawdown"] - sens["base_oos_max_drawdown"],
        "feasible_region": feas["gold_neutral"],
        "ex_ante_weights": {t: float(x) for t, x in zip(tick, w_exg)}, "ex_ante": exg,
        "last_walk_forward_weights": {t: float(x) for t, x in zip(tick, rg.walk.weights.iloc[-1])}}
    log(f"sensitivity done ({time.time() - t0:.0f}s)")

    # --- order lists
    positions = order_list(d, picks, w_ex, st)
    gf_vec = np.array([gf[t] for t in tick])
    positions_gf = order_list(d, picks, gf_vec, st)

    def cash_summary(rows):
        inv = sum(r["invested_usd"] for r in rows)
        nu = sum(r["invested_usd"] * r["non_us_share"] for r in rows) / st.capital   # cash counts as US
        return {"invested_usd": inv, "cash_left_usd": st.capital - inv, "non_us_share_after_rounding": nu,
                "note": "whole shares for exchange-listed positions (fractional for the open-end fund PYEMX); "
                        "CSU.TO trades near USD 2,500 a share, so its 10% slot buys 3 shares; leftover cash "
                        "sits in BIL or the brokerage sweep and counts as US/neutral"}
    positions_summary = {"optimized_ex_ante": cash_summary(positions),
                         "guideline_feasible": cash_summary(positions_gf)}

    # --- Monte Carlo on the chosen portfolio
    chosen = {"optimized": "optimized", "overlay": "optimized_overlay", "no_rule": "no_rule"}[
        "overlay" if st.overlay else ("no_rule" if not st.rule else "optimized")]
    infl, infl_win = inflation_rate(d.yields)
    drift = float(w_ex @ consensus(d, tick))
    mc = monte_carlo(runs[chosen].monthly, drift, st, infl)
    mc["chosen_portfolio"] = chosen
    mc["inflation"] = {"rate": infl, "source": f"yields.csv US_CPI, average annual change {infl_win[0]} to {infl_win[1]}"}
    mc["forward_drift_source"] = "weighted consensus_usd of the picks at the ex-ante (order list) weights"
    targets = evaluate_targets(mc["forward"], P[chosen]["metrics"]["full"], infl)
    targets["historical_drift"] = evaluate_targets(mc["historical"], P[chosen]["metrics"]["full"], infl)
    targets["note"] = ("median, P(loss) and P(beat CPI) from the forward Monte Carlo; max drawdown and worst "
                       "calendar year from the walk-forward backtest (full window, monthly USD)")
    log(f"monte carlo done ({time.time() - t0:.0f}s)")

    # --- frontiers
    pts = {"guideline": np.array([g[t] for t in tick]), "guideline_feasible": gf_vec,
           "chosen_ex_ante": w_ex, "optimized_latest": runs["optimized"].walk.weights.iloc[-1].to_numpy()}
    fronts = frontier_set(d, picks, st, pts)
    log(f"frontiers done ({time.time() - t0:.0f}s)")

    # --- what-if block (picks and runners-up)
    allpos = _pos(PICKS + RUNNERS)
    at = [p["ticker"] for p in allpos]
    Mw = M[at].dropna()
    Sw = F.shrunk_cov(Mw.to_numpy())
    whatif = {"tickers": at, "names": [d.universe.set_index("ticker").loc[t, "name"] for t in at],
              "mu": consensus(d, at).tolist(), "cov": Sw.tolist(),
              "non_us_share": [p["non_us"] for p in allpos], "sleeve": [p["sleeve"] for p in allpos],
              "kind": [p["kind"] for p in allpos], "pick": [t in tick for t in at],
              "cov_sample": [str(Mw.index[0].date()), str(Mw.index[-1].date())],
              "stress_returns": {k: [window_return(M[t], s, e) for t in at] for k, (s, e) in {**STRESS, **USD_EPISODES}.items()},
              "bounds": {"stock": st.stock_bounds, "fund": st.fund_bounds, "other": st.other_bounds},
              "sleeve_bands": {k: [v - BAND, v + BAND] for k, v in TARGET_MIX.items()},
              "min_non_us": st.min_non_us, "rf": fronts["rf_bil_average"]}

    # --- binding summary for the optimized walk-forward
    bind_counts = {}
    for row in P["optimized"]["rule_checks"]["rebalances"]:
        for b in row["binding"]:
            bind_counts[b] = bind_counts.get(b, 0) + 1
    nreb = len(P["optimized"]["rule_checks"]["rebalances"])
    bind_nr = {}
    for row in rule_check_rows(runs["no_rule"], make_constraints(picks, st, rule=False)):
        for b in row["binding"]:
            bind_nr[b] = bind_nr.get(b, 0) + 1
    rule_checks = {
        "feasible_region": feas,
        "binding_share_optimized": {k: v / nreb for k, v in sorted(bind_counts.items(), key=lambda x: -x[1])},
        "binding_share_no_rule": {k: v / nreb for k, v in sorted(bind_nr.items(), key=lambda x: -x[1])},
        "ex_ante": {"check": ex_info["check"], "binding": ex_info["binding"]},
        "guideline": O.check_weights(np.array([g[t] for t in tick]), rule_constraints(picks, st)),
        "guideline_feasible": O.check_weights(gf_vec, rule_constraints(picks, st)),
        "summary": ("With the 10% single-stock cap the three international stocks hold at most 30%, so the "
                    "70% floor forces the EM bond sleeve to at least 40% (band 25-45%) and US stocks plus "
                    "metals to at most 30%; the feasible equity range is 45-58%. The exact 55/35/10 guideline "
                    "is outside the feasible set under any split."),
    }

    settings = {**{k: v for k, v in asdict(st).items()}, "base_currency": "USD",
                "backtest_start_requested": st.start, "walk_forward_start": str(first_day.date()),
                "backtest_end": BACKTEST_END, "in_sample": ["walk-forward start", IN_SAMPLE_END],
                "out_of_sample": [OOS_START, BACKTEST_END], "risk_free": "BIL",
                "benchmark": "GUIDE_BENCH (55% ACWX / 35% EMB / 10% GLD, quarterly)",
                "costs_bp_one_way": {p["ticker"]: p["cost_bp"] for p in _pos(PICKS + RUNNERS)},
                "sleeve_bands": {k: [v - BAND, v + BAND] for k, v in TARGET_MIX.items()},
                "calendar": "US trading days (AGG or BIL), forward-fill at most 5 days",
                "chosen_portfolio": chosen}
    res = {"schema_version": 1, "as_of": str(d.prices_local.index.max().date()), "settings": settings,
           "notes": NOTES, "positions": positions, "positions_guideline_feasible": positions_gf,
           "positions_summary": positions_summary,
           "ex_ante": {**ex_info, "weights": {t: float(x) for t, x in zip(tick, w_ex)}},
           "rule_checks": rule_checks, "portfolios": P, "variants": variants, "adjustments": adj,
           "attribution": att, "monte_carlo": mc, "targets": targets, "frontiers": fronts, "whatif": whatif,
           "sensitivity": sens, "overlay_basis": overlay_basis,
           "reproduce": "python -m portfolio.build --write"}
    res = clean(res)
    if write:
        write_outputs(res, runs, tick)
        log(f"written to {OUT} ({time.time() - t0:.0f}s)")
    return res


def write_outputs(res, runs, tick):
    OUT.mkdir(parents=True, exist_ok=True)
    runs["optimized"].walk.weights.rename_axis("date").to_csv(OUT / "weights_history_optimized.csv",
                                                               float_format="%.6f")
    pd.DataFrame(res["positions"]).to_csv(OUT / "order_list.csv", index=False)
    pd.DataFrame(res["positions_guideline_feasible"]).to_csv(OUT / "order_list_guideline_feasible.csv", index=False)
    order = ["guideline", "guideline_feasible", "optimized", "optimized_overlay", "no_rule", "GUIDE_BENCH",
             "SIXTY_FORTY", "GLOBAL_6040", "min_variance", "optimized_overlay_1contract"]
    pd.DataFrame([headline_row(k, res["portfolios"][k]) for k in order]).to_csv(OUT / "comparison.csv",
                                                                               index=False, float_format="%.6f")
    pd.DataFrame(res["variants"]).to_csv(OUT / "variants.csv", index=False, float_format="%.6f")
    txt = json.dumps(res, separators=(",", ":"), allow_nan=False)
    (OUT / "portfolio.json").write_text(txt, encoding="utf-8")
    charts(res, CHARTS)


def print_table(res):
    order = ["guideline", "guideline_feasible", "optimized", "optimized_overlay", "no_rule", "GUIDE_BENCH",
             "SIXTY_FORTY", "GLOBAL_6040"]
    hdr = f"{'portfolio':20s} {'win':4s} {'CAGR':>7s} {'vol':>6s} {'Sharpe':>6s} {'IR':>6s} {'maxDD':>7s} {'worstY':>7s} {'nonUS':>6s}"
    print(hdr)
    for k in order:
        e = res["portfolios"][k]
        rc = e["rule_checks"]
        nu = rc["realised_non_us"]["mean_daily"] if "realised_non_us" in rc else rc["non_us_share"]
        for w, lab in (("in_sample", "IS"), ("out_of_sample", "OOS")):
            m = e["metrics"][w]
            f = lambda x, p=True: "   n/a" if x is None else (f"{x:7.1%}" if p else f"{x:6.2f}")
            print(f"{k:20s} {lab:4s} {f(m.get('cagr'))} {f(m.get('vol'))[1:]} {f(m.get('sharpe'), False)} "
                  f"{f(m.get('info_ratio'), False)} {f(m.get('max_drawdown'))} {f(m.get('worst_calendar_year'))} {nu:6.1%}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="full run; write reports/final/")
    ap.add_argument("--rebalance", choices=["monthly", "quarterly", "semiannual", "annual"], default="quarterly")
    ap.add_argument("--lookback-years", type=int, choices=[3, 5], default=3)
    ap.add_argument("--no-rule", action="store_true", help="headline without the 70%% non-US floor")
    ap.add_argument("--overlay", action="store_true", help="headline with the protective-put overlay")
    a = ap.parse_args(argv)
    st = Settings(rebalance=a.rebalance, lookback_years=a.lookback_years, rule=not a.no_rule, overlay=a.overlay)
    if a.write:
        res = full_run(st, write=True)
        print_table(res)
        return
    d = load_data()
    run = headline(d, st)
    bench = fixed_mix_monthly(d.monthly, FIXED_BENCHES["GUIDE_BENCH"]).reindex(run.monthly.index)
    ms = metric_set(run.monthly, bench, d.monthly["BIL"])
    for k, m in ms.items():
        print(k, {f: (round(m[f], 4) if isinstance(m.get(f), float) else m.get(f))
                  for f in ("start", "end", "cagr", "vol", "sharpe", "info_ratio", "max_drawdown", "worst_calendar_year")})
    print("last weights:", {k: round(v, 4) for k, v in run.walk.weights.iloc[-1].items()})


if __name__ == "__main__":
    main()
