"""Other-sleeve candidate analysis (10% inflation / diversification sleeve), one script for 8 funds.

    python -m research.candidates.other_sleeve --all --write
    python -m research.candidates.other_sleeve --ticker IAU [--write]

Writes (with --write): reports/candidates/<ID>.json, research/candidates/memos/<ID>.md,
reports/candidates/charts/<ID>_growth.png, <ID>_rolling.png, other_correlations.png,
reports/candidates/other_control.csv (+ other_control_rank.json).
Method: research/plan/method.md; schema: research/plan/results_schema.md.
Monthly USD total returns (NAV, net of fees), in-sample 2010-01 to 2017-12, OOS 2018-01 to last full month.
Assumptions: research/candidates/assumptions_other.py.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .. import config
from ..montecarlo import simulate
from ..screen import (benchmark_monthly, inflation_beta, is_oos_rank_test, load_universe,
                      monthly_returns, stats, usd_prices)
from ..screen.prices import read_wide_csv
from . import assumptions_other as A

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research"
LL = ROOT / "research" / "plan" / "longlists"
OUT = ROOT / "reports" / "candidates"
CHARTS = OUT / "charts"
MEMOS = ROOT / "research" / "candidates" / "memos"

IDS = ["IAU", "SLV", "GSG", "GNR", "VNQI", "IGF", "SCHP", "WIP"]
IS_START, IS_END, OOS_START = "2010-01-01", "2017-12-31", "2018-01-01"
WINDOWS = {"in_sample": (IS_START, IS_END), "out_of_sample": (OOS_START, None), "full": (None, None)}
BENCH_TICKERS = ["IVW", "EFG", "EEM", "EMB", "GLD", "ACWX", "ACWI", "BIL"]
CORR_BENCHES = ["IVW", "EFG_EEM_5050", "EMB", "GLD", "GUIDE_BENCH"]
REL_KEYS = ["beta", "alpha", "tracking_error", "info_ratio", "t_stat_ir", "t_stat_alpha", "up_capture", "down_capture"]

# method.md section 11: name -> (start, end); return = compounded months in (start, end]
STRESS_WINDOWS = {
    "gfc_2008": ("2007-10-31", "2009-02-28"),
    "taper_2013": ("2013-04-30", "2013-08-31"),
    "covid_2020": ("2020-01-31", "2020-03-31"),
    "inflation_2022": ("2021-12-31", "2022-10-31"),
}
STRONG_USD_EPISODES = {"usd_2014_06_to_2015_03": ("2014-05-31", "2015-03-31"),
                       "usd_2021_06_to_2022_09": ("2021-05-31", "2022-09-30")}
STRONG_USD_THRESHOLD = 0.02

META = {
    "IAU": dict(name="iShares Gold Trust", category="gold", sector="Gold bullion", country="GLOBAL",
                structure="Grantor trust holding allocated London bullion; no derivatives, no K-1.",
                tax="Gains taxed as collectibles (up to 28% long-term federal rate); no income distributions.",
                drivers="The dollar price of gold: falling real yields and a weaker dollar help, central-bank buying and crisis demand help; it pays no income, so it is pure price.",
                risks="Long flat or falling spells (in-sample drawdown over 40% from the 2011 peak); no yield, so real-rate rises hurt; a recent run-up can reverse; 28% collectibles tax; IAU and GLD are the same asset (0.25% vs 0.40% fee)."),
    "SLV": dict(name="iShares Silver Trust", category="silver", sector="Silver bullion", country="GLOBAL",
                structure="Grantor trust holding allocated London silver bars.",
                tax="Collectibles tax (up to 28%); no income.",
                drivers="Silver price: monetary demand like gold plus industrial demand (solar, electronics), so it trades as a high-beta gold with a cyclical component.",
                risks="Roughly twice gold's volatility and a -70% in-sample drawdown; industrial slowdowns hit it while gold may rise; thin 2010-17 return."),
    "GSG": dict(name="iShares S&P GSCI Commodity-Indexed Trust", category="broad commodities", sector="Commodity futures (GSCI)", country="GLOBAL",
                structure="Commodity pool holding S&P GSCI futures plus T-bill collateral; K-1 partnership reporting; energy is the largest part of the index.",
                tax="K-1 reporting; futures gains are taxed under the 60/40 rule; income and roll results are not smooth.",
                drivers="Spot commodity prices (mostly crude oil) plus roll yield (negative in contango, positive in backwardation) plus T-bill collateral interest.",
                risks="Concentrated in energy; contango roll drag; lost money in-sample; K-1 complexity; expense ratio is exactly at the 0.75% hard-screen limit."),
    "GNR": dict(name="SPDR S&P Global Natural Resources ETF", category="natural-resource equities", sector="Energy, metals and agriculture producers", country="GLOBAL",
                structure="1940 Act ETF holding about 90 listed natural-resource producers (energy, metals and mining, agriculture, timber).",
                tax="Mostly qualified dividends; foreign withholding tax on non-US holdings (partly creditable).",
                drivers="Equity market beta plus commodity prices through producers' earnings; dividend yield about 2.4%.",
                risks="Behaves largely as cyclical equity (it correlates with ACWX), so the diversification is weaker than bullion; a commodity bust hits it from both sides."),
    "VNQI": dict(name="Vanguard Global ex-U.S. Real Estate ETF", category="ex-US REITs", sector="Listed real estate ex-US", country="GLOBAL",
                 structure="1940 Act ETF tracking the S&P Global ex-US Property Index (developed and emerging property companies); Vanguard share class.",
                 tax="Mostly non-qualified dividends (ordinary income), foreign withholding tax.",
                 drivers="Property-company equity returns: rents, interest rates (cap rates), local currencies (unhedged) and equity sentiment; yield about 5%.",
                 risks="Equity-like drawdowns in rate shocks (2022); unhedged foreign currency; weak short-run inflation hedge; country mix not verified from holdings."),
    "IGF": dict(name="iShares Global Infrastructure ETF", category="infrastructure", sector="Utilities, transport, energy infrastructure", country="GLOBAL",
                structure="1940 Act ETF tracking the S&P Global Infrastructure Index (listed utilities, pipelines, airports, toll roads).",
                tax="Mostly qualified dividends; foreign withholding tax on non-US holdings.",
                drivers="Regulated and contracted cash flows (often inflation-linked tariffs), interest rates (bond-like), and equity sentiment; yield about 2.9%.",
                risks="Rate-sensitive like utilities; correlated with equities in a crash; about a third US holdings."),
    "SCHP": dict(name="Schwab U.S. TIPS ETF", category="US TIPS", sector="US Treasury inflation-protected securities", country="US",
                 structure="1940 Act ETF tracking the Bloomberg US Treasury Inflation-Linked Bond Index; expense ratio 0.03%.",
                 tax="Interest and inflation accruals are taxable each year (phantom income) though not paid in cash; best held in a tax-deferred account.",
                 drivers="Real yields (duration about 6.5 years, not re-verified) plus realised CPI inflation accrued to principal.",
                 risks="Falls when real yields rise; only protects against US inflation; counts fully against the 70% rule; the deflation floor applies only to Treasury principal."),
    "WIP": dict(name="SPDR FTSE International Government Inflation-Protected Bond ETF", category="international inflation-linked bonds", sector="Non-US government linkers", country="GLOBAL",
                structure="1940 Act ETF tracking the FTSE International Inflation-Linked Securities Select Index; non-US government linkers (UK 18%, Brazil 8% per the 2026-09-30 factsheet); understood to be currency-unhedged (not re-verified).",
                tax="Interest and inflation accruals taxable annually; currency gains are ordinary income.",
                drivers="Local real yields, local inflation accruals and, above all, currencies against the dollar (unhedged).",
                risks="Currency risk is large relative to the bond return; UK linkers fell hard in 2022; Brazil's high carry is volatile; only 26% of the country mix is known."),
}
FX_NOTE = {"VNQI": "not decomposed: country/currency mix of the fund was not retrieved (long-list notes give none)",
           "WIP": "not decomposed: long-list notes give only UK 18.36% and Brazil 7.99% (26% of the fund)"}


# ----------------------------------------------------------------------------------------- data
class Ctx:
    pass


def month_end_series(s):
    s = s.dropna().copy()
    s.index = s.index + pd.offsets.MonthEnd(0)
    return s.groupby(level=0).last()


def guide_bench(m):
    """55% ACWX / 35% EMB / 10% GLD, weights reset at calendar quarter ends (drift in between)."""
    df = m[["ACWX", "EMB", "GLD"]].dropna()
    w0 = np.array([0.55, 0.35, 0.10])
    w, out = w0.copy(), []
    for dt, row in df.iterrows():
        r = row.to_numpy()
        port = float((w * r).sum())
        out.append(port)
        w = w * (1 + r) / (1 + port)
        if dt.month in (3, 6, 9, 12):
            w = w0.copy()
    return pd.Series(out, index=df.index, name="GUIDE_BENCH")


def cpi_plus(cpi_index, spread=0.02):
    """Monthly US CPI inflation plus spread/12 compounded; absent where CPI is not yet published."""
    c = month_end_series(cpi_index)
    return ((1 + c.pct_change(fill_method=None)) * (1 + spread) ** (1 / 12) - 1).dropna().rename("CPI_PLUS_2")


def load():
    ctx = Ctx()
    scored = pd.read_csv(LL / "other_scored.csv", dtype={"flags": str, "reasons": str})
    ctx.scored = scored.set_index("ticker")
    ctx.passed = [t for t in scored.loc[scored["passed"].astype(str) == "True", "ticker"]]
    ctx.table = pd.read_csv(LL / "other_insample_table.csv").set_index("ticker")
    ctx.signals = pd.read_csv(LL / "other_signals.csv", index_col=0)
    ctx.funds = pd.read_csv(DATA / "funds.csv").set_index("ticker")
    uni = load_universe(ROOT / "research" / "plan" / "universe.csv")
    want = sorted(set(ctx.passed) | set(BENCH_TICKERS) | set(IDS))
    uni = uni[uni["ticker"].isin(want)]
    prices = read_wide_csv(DATA / "prices.csv", columns=want)
    fx = read_wide_csv(DATA / "fx.csv", columns=["EUR"])
    ctx.daily = usd_prices(prices, fx, uni)
    ctx.m = monthly_returns(ctx.daily, drop_partial=True)
    ctx.rf = ctx.m["BIL"]
    ctx.y = pd.read_csv(DATA / "yields.csv", index_col=0, parse_dates=True)
    ctx.bench = {"GLD": ctx.m["GLD"], "IVW": ctx.m["IVW"], "EMB": ctx.m["EMB"], "ACWX": ctx.m["ACWX"], "ACWI": ctx.m["ACWI"],
                 "EFG_EEM_5050": benchmark_monthly("EFG_EEM_5050", ctx.m), "GUIDE_BENCH": guide_bench(ctx.m),
                 "CPI_PLUS_2": cpi_plus(ctx.y["US_CPI"])}
    ctx.usd_broad = month_end_series(ctx.y["USD_BROAD"])
    return ctx


# ----------------------------------------------------------------------------------------- stats helpers
def window_return(r, start, end):
    """Compounded return over the months in (start, end]; None unless every month is present."""
    months = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="ME")[1:]
    if len(months) == 0:
        return None
    x = r.reindex(months)
    if x.isna().any():
        return None
    return float((1 + x).prod() - 1)


def strong_usd_months(usd_broad):
    chg = usd_broad.pct_change(fill_method=None)
    return chg[chg >= STRONG_USD_THRESHOLD].index


def stress_block(ctx, r):
    bm = ctx.bench["GLD"]
    out = {}
    for k, (a, b) in STRESS_WINDOWS.items():
        out[k] = {"start": a, "end": b, "return": window_return(r, a, b), "benchmark": window_return(bm, a, b)}
    mo = strong_usd_months(ctx.usd_broad)
    x, xb = r.reindex(mo).dropna(), bm.reindex(mo).dropna()
    out["strong_usd"] = {"definition": f"months when USD_BROAD (FRED broad dollar index, monthly) rose >= {STRONG_USD_THRESHOLD:.0%}",
                         "months_in_sample": int(len(x)), "avg_return": float(x.mean()) if len(x) else None,
                         "benchmark": float(xb.mean()) if len(xb) else None, "episodes": {}}
    for k, (a, b) in STRONG_USD_EPISODES.items():
        out["strong_usd"]["episodes"][k] = {"start": a, "end": b, "return": window_return(r, a, b),
                                           "benchmark": window_return(bm, a, b)}
    return out


def rel_block(r, bench, ctx):
    return {k: v for k, v in stats.metrics_block(r, bench, ctx.rf, A.N_TRIALS).items() if k in REL_KEYS}


def beta_vs(r, mkt, rf):
    df = pd.concat([r - rf, mkt - rf], axis=1, sort=True).dropna()
    if len(df) < 24:
        return np.nan
    return float(np.polyfit(df.iloc[:, 1], df.iloc[:, 0], 1)[0])


def last_val(y, col):
    s = y[col].dropna()
    return float(s.iloc[-1]) / 100, str(s.index[-1].date())


def cpi_cagr_over(ctx, r):
    cm = month_end_series(ctx.y["US_CPI"])
    a = cm.loc[:r.index[0] - pd.offsets.MonthEnd(1)]
    b = cm.loc[:r.index[-1]]
    n = (b.index[-1].year - a.index[-1].year) * 12 + b.index[-1].month - a.index[-1].month
    return float((b.iloc[-1] / a.iloc[-1]) ** (12 / n) - 1)


# ----------------------------------------------------------------------------------------- expected return
def gold_real_yield_model(real10, be10, drift):
    """Nominal expected return: real = -real10 + drift ; (1 + real)(1 + be10) - 1. Inputs are decimals."""
    return (1 + (-real10 + drift)) * (1 + be10) - 1


def expected_returns(ctx, tk, r):
    y = ctx.y
    real10, d_real = last_val(y, "US_REAL10")
    be10, d_be = last_val(y, "US_BE10")
    rf, d_rf = last_val(y, "US_3M")
    fund_yield = float(ctx.funds.loc[tk, "yield"])
    fee = float(ctx.funds.loc[tk, "expense_ratio"])
    inputs = {"US_REAL10": [real10, d_real], "US_BE10": [be10, d_be], "US_3M": [rf, d_rf],
              "fund_yield": fund_yield, "fund_fee": fee}
    methods, notes, consensus_keys = {}, {}, []
    hist_nom = stats.cagr(r)
    cc = cpi_cagr_over(ctx, r)
    hist_real = (1 + hist_nom) / (1 + cc) - 1
    hist_fwd = (1 + hist_real) * (1 + be10) - 1
    hw = f"{r.index[0].date()} to {r.index[-1].date()}"
    inputs["history"] = {"window": hw, "nominal_cagr": hist_nom, "cpi_cagr": cc, "real_cagr": hist_real}
    if tk in ("IAU", "SLV"):
        drift = float(y["US_REAL10"].dropna().mean()) / 100
        inputs["gold_drift"] = drift
        methods["real_yield_model"] = gold_real_yield_model(real10, be10, drift)
        methods["historical_real_plus_breakeven"] = hist_fwd
        consensus_keys = ["real_yield_model", "historical_real_plus_breakeven"]
        notes["real_yield_model"] = (f"E[real] = -{real10:.2%} (10y TIPS real yield, {d_real}) + {drift:.2%} (drift = {A.GOLD_DRIFT_RULE}); "
                                     f"plus breakeven {be10:.2%}. Judgement call. Source: {A.GOLD_SOURCES[0]}")
        notes["historical_real_plus_breakeven"] = (f"history {hw}: nominal {hist_nom:.2%}, real {hist_real:.2%}; assumes the real return "
                                                   "repeats, plus breakeven. One path (a long bull run): optimistic, judgement call")
        if tk == "SLV":
            notes["silver"] = A.SILVER_NOTE
    elif tk == "GSG":
        methods["collateral_roll_spot"] = rf + A.GSG_ROLL_YIELD + be10 + A.GSG_SPOT_REAL - fee
        methods["historical_real_plus_breakeven"] = hist_fwd
        consensus_keys = ["collateral_roll_spot", "historical_real_plus_breakeven"]
        gap = stats.cagr(r) - stats.cagr(ctx.rf.reindex(r.index).dropna())
        notes["collateral_roll_spot"] = (f"US_3M {rf:.2%} + roll {A.GSG_ROLL_YIELD:.1%} (ASSUMED: no spot GSCI series on disk, so roll yield "
                                         f"cannot be backed out of realised return) + spot = inflation {be10:.2%} - fee {fee:.2%}. Judgement call. "
                                         f"Sanity check: GSG CAGR minus BIL CAGR over its history = {gap:.2%}. {A.COMMODITY_SOURCES[0]}")
        notes["historical_real_plus_breakeven"] = f"history {hw}: nominal {hist_nom:.2%}, real {hist_real:.2%}"
    elif tk in ("GNR", "IGF", "VNQI"):
        g = A.REAL_GROWTH[tk]
        methods["grinold_kroner"] = fund_yield + be10 + g
        b = beta_vs(r, ctx.bench["ACWI"], ctx.rf)
        erp = config.MarketAssumptions().mature_erp
        methods["capm"] = rf + b * erp
        methods["historical"] = hist_nom
        consensus_keys = ["grinold_kroner", "capm"]
        inputs["beta_acwi"] = b
        notes["grinold_kroner"] = (f"yield {fund_yield:.2%} (funds.csv) + inflation {be10:.2%} (US_BE10) + real growth {g:.1%} (judgement); "
                                   f"no repricing or dilution. {A.GK_SOURCE}")
        notes["capm"] = f"rf {rf:.2%} (US_3M {d_rf}) + beta to ACWI {b:.2f} x ERP {erp:.1%} (research.config.MarketAssumptions.mature_erp)"
        notes["historical"] = f"information only, not in consensus: nominal CAGR {hist_nom:.2%} over {hw}"
    elif tk == "SCHP":
        methods["real_yield_plus_breakeven"] = real10 + be10 - fee
        methods["fund_yield"] = fund_yield
        methods["historical"] = hist_nom
        consensus_keys = ["real_yield_plus_breakeven", "fund_yield"]
        notes["real_yield_plus_breakeven"] = f"10y real yield {real10:.2%} + 10y breakeven {be10:.2%} - fee {fee:.2%}; SCHP duration is shorter than 10 y: approximation"
        notes["fund_yield"] = "trailing distribution yield from funds.csv (includes realised inflation accruals): a cross-check, not a forecast"
        notes["historical"] = f"information only: nominal CAGR {hist_nom:.2%} over {hw}"
    elif tk == "WIP":
        w = pd.Series(A.WIP_WEIGHTS) / sum(A.WIP_WEIGHTS.values())
        nom = {c: last_val(y, f"{c}_10Y")[0] for c in w.index}
        cpi = {c: last_val(y, f"{c}_CPIYOY")[0] for c in w.index}
        real = {c: nom[c] - cpi[c] for c in w.index}
        fx_ppp = {c: (1 + be10) / (1 + cpi[c]) - 1 for c in w.index}
        methods["country_real_yield_plus_inflation_ppp"] = sum(w[c] * (real[c] + cpi[c] + fx_ppp[c]) for c in w.index) - A.WIP_FEE
        methods["fund_yield"] = fund_yield
        methods["historical"] = hist_nom
        consensus_keys = ["country_real_yield_plus_inflation_ppp", "fund_yield"]
        inputs["wip_countries"] = {c: {"weight_renormalised": float(w[c]), "nominal_10y": nom[c], "cpi_yoy": cpi[c],
                                      "real_proxy": real[c], "ppp_fx": fx_ppp[c]} for c in w.index}
        notes["country_real_yield_plus_inflation_ppp"] = ("UK and Brazil only (26% of the fund; the rest of the mix is unknown): real proxy = nominal 10Y - CPI YoY "
                                                        "(not a true linker real yield; the OECD file has none), plus CPI YoY carried forward, plus relative-PPP FX "
                                                        "(US_BE10 vs country CPI), minus fee 0.50%. Crude")
        notes["fund_yield"] = "trailing distribution yield from funds.csv, before FX: a cross-check"
        notes["historical"] = f"information only: nominal CAGR {hist_nom:.2%} over {hw}"
    cons = float(np.mean([methods[k] for k in consensus_keys]))
    st = config.MonteCarloSettings(n_paths=A.MC_PATHS, horizon_years=A.HORIZON_YEARS, block_months=A.MC_BLOCK_MONTHS, seed=A.MC_SEED)
    df = r.dropna().to_frame(tk)
    fwd = simulate(df, st, targets={tk: cons})[tk]["annualised"]
    his = simulate(df, st)[tk]["annualised"]
    methods["monte_carlo_median"] = fwd["50"]
    notes["monte_carlo_median"] = ("block bootstrap (6-month blocks, 20,000 paths, seed 622) of the fund's own monthly history, scaled so the geometric "
                                   "mean equals the consensus: the median is close to the consensus by construction (circular); it supplies the 5-95 "
                                   "range and is NOT averaged into the consensus")
    methods["monte_carlo_historical_median"] = his["50"]
    notes["monte_carlo_historical_median"] = "same bootstrap with unscaled history ('if the past repeats'); information only"
    return {"methods": methods, "consensus_methods": consensus_keys, "consensus_usd": cons, "consensus_local": cons,
            "range_5_95": [fwd["5"], fwd["95"]], "range_5_95_basis": "annualised 7-year return, forward-drift Monte Carlo",
            "inputs": inputs, "method_notes": notes,
            "assumptions": "research/candidates/assumptions_other.py (constants and sources); yields from data/research/yields.csv",
            "command": f"python -m research.candidates.other_sleeve --ticker {tk}"}


# ----------------------------------------------------------------------------------------- one fund
def diversification(ctx, tk, r):
    oos, ins = r.loc[OOS_START:], r.loc[IS_START:IS_END]
    cor = {}
    for b in ["IVW", "EFG_EEM_5050", "EMB", "GLD", "GUIDE_BENCH", "ACWX"]:
        d = pd.concat([oos, ctx.bench[b]], axis=1, sort=True).dropna()
        cor[b] = float(d.corr().iloc[0, 1]) if len(d) >= 36 else None
    cpi = ctx.y["US_CPI"]
    bi, ni = inflation_beta(ins, cpi)
    bo, no = inflation_beta(oos, cpi)
    usd_chg = ctx.usd_broad.pct_change(fill_method=None)
    d = pd.concat([oos, usd_chg], axis=1, sort=True).dropna()
    usd_beta = float(np.polyfit(d.iloc[:, 1], d.iloc[:, 0], 1)[0]) if len(d) >= 36 else None
    w = STRESS_WINDOWS["inflation_2022"]
    own = [cor[b] for b in ["IVW", "EFG_EEM_5050", "EMB", "GLD"] if cor[b] is not None and not (tk == "IAU" and b == "GLD")]
    return {"oos_correlation": cor, "oos_correlation_months": int(len(oos)),
            "inflation_beta_in_sample": None if pd.isna(bi) else bi, "inflation_beta_in_sample_months": ni,
            "inflation_beta_oos": None if pd.isna(bo) else bo, "inflation_beta_oos_months": no,
            "inflation_beta_definition": "OLS slope of monthly return on the monthly change in year-on-year US CPI inflation (research.screen.inflation_beta)",
            "return_2021_12_to_2022_10": window_return(r, *w), "return_2022_benchmark_gld": window_return(ctx.bench["GLD"], *w),
            "return_2022_cpi_plus_2": window_return(ctx.bench["CPI_PLUS_2"], *w),
            "oos_beta_to_usd_broad_monthly_change": usd_beta,
            "oos_avg_correlation_excl_own": float(np.mean(own))}


def explain(tk, res):
    o = res["metrics"]["out_of_sample"]["usd"]
    d, e, meta = res["diversification"], res["expected_return_7y"], META[tk]
    r22 = d["return_2021_12_to_2022_10"]
    s1 = f"{tk} is a {meta['category']} fund ({meta['name']}) that counts {A.NON_US[tk]:.0%} as non-US under the course rule."
    s2 = f"Since 2018 it returned {o['cagr']:.1%} a year with a Sharpe of {o['sharpe']:.2f} and a worst drawdown of {o['max_drawdown']:.0%}"
    s2 += f"; in the 2022 inflation and rate shock (Dec 2021 to Oct 2022) it returned {r22:.0%}." if r22 is not None else "."
    ac = d["oos_correlation"].get("ACWX")
    s3 = (f"Our models put the next seven years at about {e['consensus_usd']:.1%} a year (Monte Carlo range {e['range_5_95'][0]:.0%} to "
          f"{e['range_5_95'][1]:.0%}, judgement-heavy), and its monthly returns correlate {ac:.2f} with world ex-US stocks.")
    return [s1, s2, s3]


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if (math.isnan(o) or math.isinf(o)) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def build_fund(ctx, tk):
    meta = META[tk]
    r = ctx.m[tk].dropna()
    is_gld = tk == "IAU"
    metrics = {}
    for w, (a, b) in WINDOWS.items():
        blk = stats.metrics_block(r.loc[a:b], ctx.bench["GLD"], ctx.rf, A.N_TRIALS)
        if is_gld:     # IAU vs GLD is the same asset: tracking error is only the fee difference
            for k in REL_KEYS:
                blk[k] = None
        metrics[w] = {"usd": blk, "local": dict(blk)}
    alt = {bn: {w: rel_block(r.loc[a:b], ctx.bench[bn], ctx) for w, (a, b) in WINDOWS.items()}
           for bn in ("GUIDE_BENCH", "CPI_PLUS_2")}
    ref = {}
    for bn in ("GLD", "GUIDE_BENCH", "CPI_PLUS_2"):
        ref[bn] = {}
        for w, (a, b) in WINDOWS.items():
            x = ctx.bench[bn].loc[a:b].dropna()
            ref[bn][w] = {"cagr": stats.cagr(x), "vol": stats.vol(x), "sharpe": stats.sharpe(x, ctx.rf),
                          "max_drawdown": stats.max_drawdown(x), "months": int(len(x))}
    rb_name = "GUIDE_BENCH" if is_gld else "GLD"
    rs, ri = stats.rolling_sharpe(r, ctx.rf), stats.rolling_ir(r, ctx.bench[rb_name])
    idx = rs.index.intersection(ri.index)
    oos_ir = ri.loc[OOS_START:]
    rolling = {"dates": [str(d.date()) for d in idx], "sharpe": rs.loc[idx].tolist(), "info_ratio": ri.loc[idx].tolist(),
               "info_ratio_benchmark": rb_name, "window_months": 36,
               "share_ir_positive_full": stats.share_ir_positive(r, ctx.bench[rb_name]),
               "share_ir_positive_oos": float((oos_ir > 0).mean()) if len(oos_ir) else None}
    oos = r.loc[OOS_START:]
    fxs = FX_NOTE.get(tk)
    currency = {"local_return": stats.cagr(oos), "fx_return": None if fxs else 0.0, "usd_return": stats.cagr(oos),
                "hedged_return": None, "hedge_cost": None, "fx_vol_share": None if fxs else 0.0,
                "note": fxs or "USD-priced fund: local = USD, FX share 0 by construction (dollar sensitivity is in "
                               "diversification.oos_beta_to_usd_broad_monthly_change)"}
    sc = ctx.scored.loc[tk]
    nz = lambda v: None if pd.isna(v) else (float(v) if isinstance(v, (int, float, np.floating)) else v)
    kept = [k for k in ctx.signals.index if bool(ctx.signals.loc[k, "kept"])]
    gnote = ("; IAU IS GLD (same bullion, 0.15 point lower fee), so the GLD information ratio, alpha, beta and tracking error are "
             "undefined (null); use the IR versus GUIDE_BENCH or CPI+2% (alt_benchmarks)") if is_gld else ""
    res = {
        "schema_version": 1, "id": tk, "ticker": tk, "usd_ticker": tk, "name": meta["name"], "position_type": "other",
        "instrument": "etf", "country": meta["country"], "currency": "USD", "sector": meta["sector"],
        "category": meta["category"], "non_us": bool(A.NON_US[tk] >= 0.5), "non_us_share": A.NON_US[tk],
        "benchmark": "GLD",
        "data": {"price_start": str(ctx.daily[tk].dropna().index[0].date()), "price_end": str(ctx.daily[tk].dropna().index[-1].date()),
                 "months_total": int(len(r)), "months_in_sample": int(len(r.loc[IS_START:IS_END])),
                 "months_out_of_sample": int(len(oos)), "last_full_month": str(r.index[-1].date()),
                 "sources": ["data/research/prices.csv", "data/research/yields.csv", "data/research/funds.csv",
                             "research/plan/longlists/other_scored.csv", "research/plan/longlists/other_notes.md"],
                 "fund_fee": float(ctx.funds.loc[tk, "expense_ratio"]),
                 "notes": ("Monthly returns from Yahoo adjusted close (dividends reinvested; NAV net of fee). USD-listed, so local = usd. "
                           "Risk-free BIL. Deflated Sharpe uses n_trials = 33. IR in the main block is versus GLD" + gnote +
                           ". non_us is true when the share is at least 0.5; use non_us_share for the 70% rule. The shortlist table said "
                           "about 0.5 / 0.6 for GNR / IGF; the factsheet-based long-list notes (0.65 / 0.64) are used."
                           + (" VNQI's 1.00 is by index design, not verified from holdings." if tk == "VNQI" else ""))},
        "metrics": metrics, "alt_benchmarks": alt, "benchmark_reference": ref,
        "deflated_sharpe": {"n_trials": A.N_TRIALS, "in_sample": metrics["in_sample"]["usd"].get("deflated_sharpe"),
                            "out_of_sample": metrics["out_of_sample"]["usd"].get("deflated_sharpe"),
                            "full": metrics["full"]["usd"].get("deflated_sharpe"),
                            "note": "probability the true Sharpe beats the best of 33 luck-only trials (Bailey and Lopez de Prado 2014); V = 1/(T-1)"},
        "rolling": rolling, "currency": currency, "diversification": diversification(ctx, tk, r),
        "expected_return_7y": expected_returns(ctx, tk, r), "stress": stress_block(ctx, r),
        "screens": {"fundamental_score": nz(sc["fundamental_score"]), "technical_score": nz(sc["technical_score"]),
                    "hard_screens_passed": bool(sc["passed"]), "technical_signals_kept": kept,
                    "detail": {k: nz(sc[k]) for k in ["inflation_beta", "inflation_beta_months", "ret_2022_info", "corr_acwx", "corr_emb",
                                                      "inflation_score", "correlation_score", "cost_score", "expense_ratio", "aum_usd_bn",
                                                      "T1", "T2", "T3", "T4", "T5"] if k in sc.index},
                    "flags": str(sc["flags"]), "source": "research/plan/longlists/other_scored.csv (as of 2017-12-31)"},
        "rubric": {"scores": {}, "total": None, "rank_in_type": None},
        "review": {"reviewer": None, "date": None, "verdict": None, "claims": []},
        "memo": f"research/candidates/memos/{tk}.md",
        "charts": {"growth": f"reports/candidates/charts/{tk}_growth.png", "rolling": f"reports/candidates/charts/{tk}_rolling.png"},
        "reproduce": f"python -m research.candidates.other_sleeve --ticker {tk} --write",
    }
    res["explain"] = explain(tk, res)
    return clean(res)


# ----------------------------------------------------------------------------------------- control
def control_table(ctx):
    rows = []
    for t in ctx.passed:
        r = ctx.m[t].dropna()
        row = {"ticker": t, "name": ctx.scored.loc[t, "name"], "category": ctx.table["category"].get(t, "")}
        for lab, (a, b) in (("is", (IS_START, IS_END)), ("oos", (OOS_START, None))):
            x = r.loc[a:b]
            blk = stats.metrics_block(x, ctx.bench["GLD"], ctx.rf, A.N_TRIALS) if len(x) > 2 else {}
            ib = inflation_beta(x, ctx.y["US_CPI"])[0] if len(x) >= 36 else np.nan
            row.update({f"months_{lab}": len(x), f"cagr_{lab}": blk.get("cagr"), f"sharpe_{lab}": blk.get("sharpe"),
                        f"ir_vs_gld_{lab}": blk.get("info_ratio"), f"max_dd_{lab}": blk.get("max_drawdown"),
                        f"inflation_beta_{lab}": ib})
        row["deflated_sharpe_oos"] = stats.metrics_block(r.loc[OOS_START:], None, ctx.rf, A.N_TRIALS).get("deflated_sharpe")
        row["fundamental_score_is"] = ctx.scored.loc[t, "fundamental_score"]
        row["composite_is"] = ctx.table["composite"].get(t, np.nan)
        row["in_shortlist"] = t in IDS
        rows.append(row)
    df = pd.DataFrame(rows)
    df.loc[df["ticker"] == "GLD", ["ir_vs_gld_is", "ir_vs_gld_oos"]] = np.nan   # benchmark itself
    df.loc[df["ticker"] == "BIL", ["sharpe_is", "sharpe_oos"]] = np.nan          # the risk-free rate itself
    s = df.set_index("ticker")
    tests = {"composite_vs_oos_sharpe": is_oos_rank_test(s["composite_is"], s["sharpe_oos"]),
             "composite_vs_oos_ir_vs_gld": is_oos_rank_test(s["composite_is"], s["ir_vs_gld_oos"]),
             "fundamental_score_vs_oos_sharpe": is_oos_rank_test(s["fundamental_score_is"], s["sharpe_oos"]),
             "is_sharpe_vs_oos_sharpe": is_oos_rank_test(s["sharpe_is"], s["sharpe_oos"])}
    return df.sort_values("composite_is", ascending=False), tests


# ----------------------------------------------------------------------------------------- charts
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def growth_chart(ctx, tk, r, path):
    plt = _plt()
    start = max(r.index[0], pd.Timestamp("2010-01-31"))
    col = {tk: "#1f5fa8", "GLD": "#c79a00", "CPI + 2%": "#6b6b6b"}
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=110)
    for k, s in ((tk, r), ("GLD", ctx.bench["GLD"]), ("CPI + 2%", ctx.bench["CPI_PLUS_2"])):
        x = s.loc[start:].dropna()
        g = 10000 * (1 + x).cumprod()
        g = pd.concat([pd.Series([10000.0], index=[x.index[0] - pd.offsets.MonthEnd(1)]), g])
        ax.plot(g.index, g.values, label=k, color=col[k], lw=1.9 if k == tk else 1.3, ls="--" if k == "CPI + 2%" else "-")
    ax.axvspan(start - pd.offsets.MonthEnd(1), pd.Timestamp(IS_END), color="#cccccc", alpha=0.35, label="in-sample (to 2017-12)")
    ax.set_yscale("log")
    ax.set_title(f"{tk}: growth of $10,000 (monthly total return, USD, log scale)", fontsize=10)
    ax.set_ylabel("USD"); ax.legend(frameon=False, fontsize=8); ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def rolling_chart(tk, res, path):
    plt = _plt()
    rl = res["rolling"]
    d = pd.to_datetime(rl["dates"])
    fig, ax = plt.subplots(2, 1, figsize=(8, 5), dpi=110, sharex=True)
    ax[0].plot(d, rl["sharpe"], color="#1f5fa8"); ax[0].set_ylabel("rolling 36m Sharpe (vs BIL)")
    ax[1].plot(d, rl["info_ratio"], color="#b5541c"); ax[1].set_ylabel(f"rolling 36m IR vs {rl['info_ratio_benchmark']}")
    for a in ax:
        a.axhline(0, color="k", lw=0.6); a.axvline(pd.Timestamp(OOS_START), color="#888", ls=":", lw=1); a.grid(alpha=0.25)
    ax[0].set_title(f"{tk}: rolling 36-month statistics (dotted line = start of out-of-sample)", fontsize=10)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def heatmap(ctx, path):
    plt = _plt()
    M = np.array([[pd.concat([ctx.m[t].loc[OOS_START:], ctx.bench[b].loc[OOS_START:]], axis=1, sort=True).dropna().corr().iloc[0, 1]
                   for b in CORR_BENCHES] for t in IDS])
    fig, ax = plt.subplots(figsize=(7, 4.6), dpi=110)
    im = ax.imshow(M, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(CORR_BENCHES)), CORR_BENCHES, rotation=25, ha="right", fontsize=8)
    ax.set_yticks(range(len(IDS)), IDS, fontsize=9)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=8, color="white" if abs(M[i, j]) > 0.6 else "black")
    ax.set_title("Out-of-sample (2018-01 onward) monthly return correlation", fontsize=10)
    fig.colorbar(im, ax=ax, shrink=0.8); fig.tight_layout(); fig.savefig(path); plt.close(fig)


# ----------------------------------------------------------------------------------------- memo
def pc(x, d=1):
    return "n/a" if x is None else f"{x * 100:.{d}f}%"


def f2(x):
    return "n/a" if x is None else f"{x:.2f}"


ROLE = {
    "IAU": "The sleeve's reference holding: the simplest inflation and crisis diversifier at the lowest gold fee. The case rests on diversification and the dollar, not on a high expected return.",
    "SLV": "A higher-risk cousin of gold; worth holding only if its OOS record beats gold per unit of risk, which the table lets you test.",
    "GSG": "Tests the claim that commodities hedge inflation; judge it on the in-sample loss, the roll drag and the OOS record above.",
    "GNR": "An equity route to commodities; mostly an equity-risk position with a commodity tilt, so it competes with the stock sleeve for risk budget.",
    "VNQI": "The only candidate that counts fully non-US and diversifies by asset class; it helps the 70% rule rather than consuming US room.",
    "IGF": "Defensive real-asset equity with partly inflation-linked tariffs and the smallest in-sample drawdown of the real-asset funds.",
    "SCHP": "The 'security' candidate: low volatility and cheapest, but US-only and exposed to real-rate rises.",
    "WIP": "Inflation protection that counts fully non-US, but with unhedged currency risk.",
}


def memo_text(tk, res, ctx):
    meta = META[tk]
    mt = res["metrics"]
    i, o = mt["in_sample"]["usd"], mt["out_of_sample"]["usd"]
    d, e, st = res["diversification"], res["expected_return_7y"], res["stress"]
    c, alt, ref = d["oos_correlation"], res["alt_benchmarks"], res["benchmark_reference"]
    share = A.NON_US[tk]
    kept = res["screens"]["technical_signals_kept"]
    r22, g22, c22 = d["return_2021_12_to_2022_10"], d["return_2022_benchmark_gld"], d["return_2022_cpi_plus_2"]
    if r22 is None:
        shock = "The 2022 window cannot be computed (fund too young)."
    elif r22 > (c22 or 0):
        shock = f"The 2022 shock behaved as advertised: it returned {pc(r22)} against CPI+2% of {pc(c22)} over the same ten months (GLD {pc(g22)})."
    elif r22 > 0:
        shock = f"Partly as advertised: positive ({pc(r22)}) but below CPI+2% ({pc(c22)}), so it did not keep up with inflation (GLD {pc(g22)})."
    else:
        shock = f"NOT as advertised: it lost {pc(-r22)} in the 2021-12 to 2022-10 inflation and rate shock while CPI+2% rose {pc(c22)} (GLD {pc(g22)})."
    gu, cp = alt["GUIDE_BENCH"]["out_of_sample"], alt["CPI_PLUS_2"]["out_of_sample"]
    ir_main = o.get("info_ratio")
    if tk == "IAU":
        ir_line = (f"Information ratio vs GLD is undefined (IAU is the same bullion); vs GUIDE_BENCH {f2(gu['info_ratio'])} (t {f2(gu['t_stat_ir'])}), "
                   f"vs CPI+2% {f2(cp['info_ratio'])} (t {f2(cp['t_stat_ir'])}).")
    else:
        ir_line = (f"Information ratio vs GLD {f2(ir_main)} (t {f2(o.get('t_stat_ir'))}); vs GUIDE_BENCH {f2(gu['info_ratio'])}; "
                   f"vs CPI+2% {f2(cp['info_ratio'])}.")
    beats = o["sharpe"] >= ref["GLD"]["out_of_sample"]["sharpe"]
    drop = tk != "IAU" and (not beats) and ir_main is not None and ir_main < 0
    rule = "Section 8 drop rule (OOS Sharpe below GLD and OOS IR below zero): " + ("TRIGGERED, runner-up at best." if drop else "not triggered.")
    ro = res["rolling"]
    rows = "\n".join(f"| {k} | {pc(v['return'])} | {pc(v['benchmark'])} |" for k, v in st.items() if k != "strong_usd")
    su = st["strong_usd"]
    eps = "; ".join(f"{k} {pc(v['return'])} (GLD {pc(v['benchmark'])})" for k, v in su["episodes"].items())
    meth = "\n".join(f"| {k} | {pc(v)} | {'yes' if k in e['consensus_methods'] else 'no'} |" for k, v in e["methods"].items())
    room = ("A 10% position would use 10 points of that room." if share == 0 else
            f"A 10% position uses {10 * (1 - share):.1f} points of that room." if share < 1 else "It uses none of that room.")
    tech = "none was kept (OOS IR not above zero with t above 1)" if not kept else "these were kept: " + ", ".join(kept)
    return f"""# {tk}: {meta['name']}

*Other sleeve (10%), {meta['category']}. Reproduce: `python -m research.candidates.other_sleeve --ticker {tk} --write`; all numbers are in `reports/candidates/{tk}.json`. Data to {res['data']['last_full_month']}; in-sample 2010-01 to 2017-12, out-of-sample 2018-01 onward.*

## What it holds and how
{meta['structure']} Expense ratio {pc(res['data']['fund_fee'], 2)}, AUM about ${ctx.funds.loc[tk, 'aum_usd'] / 1e9:.1f}bn (today). **Tax:** {meta['tax']}

## What drives returns
{meta['drivers']}

## Performance (monthly, USD, net of fees, risk-free BIL)
| | In-sample | Out-of-sample |
|---|---|---|
| Months | {i['months']} | {o['months']} |
| CAGR | {pc(i['cagr'])} | {pc(o['cagr'])} |
| Volatility | {pc(i['vol'])} | {pc(o['vol'])} |
| Sharpe | {f2(i['sharpe'])} | {f2(o['sharpe'])} |
| Max drawdown | {pc(i['max_drawdown'])} | {pc(o['max_drawdown'])} |
| Deflated Sharpe (33 trials) | {f2(i.get('deflated_sharpe'))} | {f2(o.get('deflated_sharpe'))} |
| GLD Sharpe | {f2(ref['GLD']['in_sample']['sharpe'])} | {f2(ref['GLD']['out_of_sample']['sharpe'])} |
| CPI+2% CAGR | {pc(ref['CPI_PLUS_2']['in_sample']['cagr'])} | {pc(ref['CPI_PLUS_2']['out_of_sample']['cagr'])} |

{ir_line} Share of rolling 36-month windows with IR above zero (vs {ro['info_ratio_benchmark']}): {pc(ro['share_ir_positive_full'], 0)} full sample, {pc(ro['share_ir_positive_oos'], 0)} for windows ending out of sample. Charts: `{res['charts']['growth']}`, `{res['charts']['rolling']}`.

## Inflation and diversification evidence
- Inflation beta (monthly return on change in YoY US CPI inflation): in-sample {f2(d['inflation_beta_in_sample'])}, OOS {f2(d['inflation_beta_oos'])}. Positive means the fund tended to gain when inflation accelerated; these regressions are noisy, so treat them as weak evidence.
- {shock}
- OOS correlation: IVW {f2(c['IVW'])}, EFG/EEM {f2(c['EFG_EEM_5050'])}, EMB {f2(c['EMB'])}, GLD {f2(c['GLD'])}, GUIDE_BENCH {f2(c['GUIDE_BENCH'])}, ACWX {f2(c['ACWX'])}. Beta to the monthly change in the broad dollar index (OOS): {f2(d['oos_beta_to_usd_broad_monthly_change'])}.

| Stress window (total USD return) | {tk} | GLD |
|---|---|---|
{rows}

Strong-dollar months (broad index up 2% or more): average {pc(su['avg_return'])} vs GLD {pc(su['benchmark'])} ({su['months_in_sample']} months). Episodes: {eps}. "n/a" means the fund did not yet exist.

## Forward 7-year view (USD, annual)
| Method | Value | In consensus |
|---|---|---|
{meth}

Consensus {pc(e['consensus_usd'])}; Monte Carlo 5-95 range {pc(e['range_5_95'][0])} to {pc(e['range_5_95'][1])}. These are judgement-heavy models; where they disagree by several points the real uncertainty is wider than shown. Formulas, inputs and sources: JSON `expected_return_7y` and `research/candidates/assumptions_other.py`.

## Technicals
Signals T1-T5 were tested on this long list; {tech}, so no technical signal is used for {tk}.

## Risks
{meta['risks']}

## Non-US share and the 70% rule
Counted at {share:.0%} non-US under method.md section 3 (long-list notes, factsheet as of 2026-09-30 where available). Each 1% of the portfolio held here uses {(1 - share):.2f}% of the 30% room the rule leaves for US or neutral assets. {room}

## Verdict
{rule} {ROLE[tk]} OOS Sharpe {f2(o['sharpe'])} (deflated {f2(o.get('deflated_sharpe'))}), OOS max drawdown {pc(o['max_drawdown'])}, consensus 7-year return {pc(e['consensus_usd'])}.

> **How to explain this pick.** {' '.join(res['explain'])}
"""


# ----------------------------------------------------------------------------------------- main
def run(tickers, write, full):
    ctx = load()
    if write:
        for p in (OUT, CHARTS, MEMOS):
            p.mkdir(parents=True, exist_ok=True)
    results = {}
    for tk in tickers:
        res = build_fund(ctx, tk)
        results[tk] = res
        if write:
            (OUT / f"{tk}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
            growth_chart(ctx, tk, ctx.m[tk].dropna(), CHARTS / f"{tk}_growth.png")
            rolling_chart(tk, res, CHARTS / f"{tk}_rolling.png")
            (MEMOS / f"{tk}.md").write_text(memo_text(tk, res, ctx), encoding="utf-8")
        o = res["metrics"]["out_of_sample"]["usd"]
        print(f"{tk:5s} OOS Sharpe {o['sharpe']:.2f}  IR {o.get('info_ratio')}  maxDD {o['max_drawdown']:.1%}  "
              f"consensus {res['expected_return_7y']['consensus_usd']:.2%}")
    if full:
        df, tests = control_table(ctx)
        print("rank tests (rho, p, n):", {k: (round(v["rho"], 3), round(v["p_value"], 3), v["n"]) for k, v in tests.items()})
        if write:
            df.to_csv(OUT / "other_control.csv", index=False)
            (OUT / "other_control_rank.json").write_text(json.dumps(clean(tests), indent=1), encoding="utf-8")
            heatmap(ctx, CHARTS / "other_correlations.png")
    return ctx, results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ticker", choices=IDS)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    if not (a.all or a.ticker):
        ap.error("give --all or --ticker")
    run(IDS if a.all else [a.ticker], a.write, a.all)


if __name__ == "__main__":
    main()
