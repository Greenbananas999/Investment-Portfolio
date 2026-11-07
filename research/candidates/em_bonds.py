"""Phase 3 candidate analysis: EM bond funds (8 shortlisted, 20 as a control group).

    python -m research.candidates.em_bonds --all --write     # 8 JSON + memos + charts + control + countries
    python -m research.candidates.em_bonds --ticker EMLC     # one fund, print a summary
    python -m research.candidates.em_bonds --ticker EMLC --write

Method: research/plan/method.md (sections 1, 2, 3, 5, 7, 9, 11, 12); output
format research/plan/results_schema.md. Assumptions (credit loss, FX view,
basket, durations) live in research/candidates/assumptions_em_bonds.py.

Reads only data/research/ and research/plan/longlists/; downloads nothing.
In-sample 2010-01 to 2017-12 and out of sample 2018-01 to the last full month
are always reported side by side. Every number is monthly total return in USD
(fund NAV/adjusted close, already net of fund fees) against BIL.

Key formulas
- Local-currency return of a local fund:  1 + r_local = (1 + r_usd) / (1 + r_fx),
  r_fx = weighted monthly USD return of the currency basket (rebalanced monthly).
- FX-hedged return (covered interest parity, 3-month forward rolled monthly):
  1 + r_hedged = (1 + r_local) x sum_i w_i [(1 + i_US/4) / (1 + i_i/4)]^(1/3),
  with i the 3-month rates (annual, decimals) of the previous month (known when
  the hedge is put on). hedge_cost = annualised mean of (1 - that factor).
- fx_vol_share = cov(r_fx, r_usd) / var(r_usd): the share of USD variance that
  came from the currency leg.
- Expected credit loss per year = sum_bucket w_b x PD_b x (1 - recovery),
  PD_b = 1 - (1 - C7_b)^(1/7), C7 = 7-year cumulative default rate
  interpolated between the 5- and 10-year averages.
- Yield-based 7-year expected return = scenario return of a constant-maturity
  bond with the fund's duration (research.bonds.total_returns on a linear yield
  path) - expense ratio - credit loss, then for local funds
  x (1 - expected depreciation), depreciation = mean of relative PPP and UIP.
"""

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from research import bonds, fxview, montecarlo
from research.config import SPOT_YIELDS, MarketAssumptions, MonteCarloSettings
from research.screen import (deflated_sharpe, expected_fx_loss, is_oos_rank_test, metrics_block,
                             rating_to_score)
from research.screen import stats
from research.screen.prices import monthly_returns, read_wide_csv

from . import assumptions_em_bonds as A

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research"
LL = ROOT / "research" / "plan" / "longlists"
OUT = ROOT / "reports" / "candidates"
CHARTS = OUT / "charts"
MEMOS = ROOT / "research" / "candidates" / "memos"

IS_START, IS_END = "2010-01-01", "2017-12-31"
OOS_START = "2018-01-01"
RF_START = "2007-06-30"           # first BIL monthly return; "full" windows start no earlier
CMD = "python -m research.candidates.em_bonds"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@dataclass
class Ctx:
    M: pd.DataFrame          # monthly USD returns (funds, benchmark parts, BIL)
    rf: pd.Series
    fx: pd.DataFrame         # monthly FX returns, USD per unit
    fxm: pd.DataFrame        # month-end FX levels
    y: pd.DataFrame          # monthly yields, decimals, month-end index
    cpi: pd.DataFrame        # World Bank annual CPI inflation, decimals, index = year
    inputs: pd.DataFrame
    scored: pd.DataFrame
    istable: pd.DataFrame
    countries: pd.DataFrame
    funds: pd.DataFrame
    longlist: pd.DataFrame
    benches: dict


def guide_bench(M, weights=None):
    """GUIDE_BENCH monthly return: fixed weights reset at each calendar quarter start.

    Within a quarter each component drifts with its own return; the portfolio
    return in month t is level_t / level_{t-1} - 1 of sum_i w_i x growth_i.
    """
    w = pd.Series(weights or A.GUIDE_BENCH)
    R = M[list(w.index)].dropna()
    q = R.index.to_period("Q")
    G = (1 + R).groupby(q).cumprod()                 # growth since quarter start
    lvl = (G * w).sum(axis=1)
    prev = lvl.groupby(q).shift(1).fillna(1.0)      # first month of quarter: start level 1
    return (lvl / prev - 1).rename("GUIDE_BENCH")


def load():
    ll = pd.read_csv(LL / "em_bonds.csv")
    scored = pd.read_csv(LL / "em_bond_scored.csv")
    control = scored.loc[scored["passed"].astype(str) == "True", "ticker"].tolist()
    tick = sorted(set(control) | set(A.CANDIDATES) | {"EMB", "EMLC", "BIL"} | set(A.GUIDE_BENCH))
    p = read_wide_csv(DATA / "prices.csv", columns=tick)
    missing = [t for t in tick if t not in p.columns]
    if missing:
        raise SystemExit(f"missing price columns in data/research/prices.csv: {missing}")
    M = monthly_returns(p, drop_partial=True)
    fxd = read_wide_csv(DATA / "fx.csv").ffill()
    fxm = fxd.resample("ME").last()
    fx = fxm.pct_change(fill_method=None).iloc[1:].reindex(M.index)
    y = pd.read_csv(DATA / "yields.csv", index_col=0, parse_dates=True).sort_index() / 100.0
    y.index = y.index + pd.offsets.MonthEnd(0)
    cpi = pd.read_csv(DATA / "cpi_annual.csv", index_col=0) / 100.0
    benches = {"EMB": M["EMB"], "EMLC": M["EMLC"], "GUIDE_BENCH": guide_bench(M)}
    for c in A.EXCLUDED_YIELD_SERIES:
        y[c] = np.nan
    global LAST_MONTH
    LAST_MONTH = M.index[-1]
    return Ctx(M=M, rf=M["BIL"], fx=fx, fxm=fxm, y=y, cpi=cpi,
               inputs=pd.read_csv(LL / "em_bond_inputs.csv").set_index("ticker"),
               scored=scored.set_index("ticker"),
               istable=pd.read_csv(LL / "em_bond_insample_table.csv").set_index("ticker"),
               countries=pd.read_csv(LL / "em_bonds_countries.csv").set_index("country"),
               funds=pd.read_csv(DATA / "funds.csv").set_index("ticker"),
               longlist=ll.set_index("ticker"), benches=benches)


# ---------------------------------------------------------------------------
# Currency basket, local return, CIP hedge
# ---------------------------------------------------------------------------
def basket_weights(ctx, kind="equal"):
    """{currency: weight} summing to 1. 'equal' = A.BASKET_EQUAL; 'gbiem' = LEMB page weights."""
    if kind == "equal":
        return {c: 1 / len(A.BASKET_EQUAL) for c in A.BASKET_EQUAL}
    inv = {v: k for k, v in A.CCY_COUNTRY.items()}
    w = ctx.countries["weight_gbiem_pct"].dropna()
    w = {inv[c]: float(x) for c, x in w.items() if c in inv and inv[c] in ctx.fx.columns}
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def basket_return(R, weights):
    """Monthly return of a basket rebalanced monthly; weights renormalised over the
    columns that have a value that month. NaN when none has."""
    w = pd.Series(weights, dtype=float)
    X = R.reindex(columns=w.index)
    W = X.notna().mul(w, axis=1)
    tot = W.sum(axis=1)
    return (X.fillna(0).mul(w, axis=1).sum(axis=1) / tot).where(tot > 0)


def local_from_usd(r_usd, r_fx):
    """Strip the currency leg: 1 + r_local = (1 + r_usd) / (1 + r_fx)."""
    return (1 + r_usd) / (1 + r_fx) - 1


def cip_hedge_return(i_us, i_loc):
    """One month of a 3-month FX forward hedge by covered interest parity.

    i_us, i_loc: 3-month rates, annual decimals. The hedger sells the currency
    forward at F = S (1 + i_US/4) / (1 + i_loc/4); spread over the 3 months that
    is the monthly factor [(1 + i_US/4) / (1 + i_loc/4)]^(1/3). Returns factor - 1:
    negative (a cost) when the local rate is above the US rate.
    """
    return ((1 + i_us / 4) / (1 + i_loc / 4)) ** (1 / 3) - 1


def basket_hedge(ctx, weights, index):
    """Monthly basket hedge return (CIP), rates lagged one month, renormalised over
    currencies that have a 3-month rate; also the list of currencies left out."""
    us = ctx.y["US_3M"].ffill(limit=2).shift(1)
    cols, left_out = {}, []
    for c in weights:
        col = f"{A.CCY_COUNTRY[c]}_3M"
        if col not in ctx.y:
            left_out.append(c)
            continue
        loc = ctx.y[col].ffill(limit=2).shift(1)
        cols[c] = cip_hedge_return(us, loc)
    H = pd.DataFrame(cols).reindex(index)
    left_out += [c for c in H.columns if H[c].isna().all()]
    H = H.drop(columns=[c for c in H.columns if H[c].isna().all()])
    return basket_return(H, {c: weights[c] for c in H.columns}), left_out


def currency_block(ctx, t, r_usd, weights=None):
    """results_schema currency block, OOS, annualised."""
    o = r_usd.loc[OOS_START:].dropna()
    if t not in A.LOCAL_FUNDS:
        c = stats.cagr(o)
        return {"local_return": c, "fx_return": 0.0, "usd_return": c, "hedged_return": c,
                "hedge_cost": 0.0, "fx_vol_share": 0.0,
                "note": "hard-currency (USD) fund: no currency leg modelled; local = usd. "
                        "Active funds may hold some local-currency debt (not measured)."}
    weights = weights or basket_weights(ctx)
    fxr = basket_return(ctx.fx, weights).reindex(o.index)
    loc = local_from_usd(o, fxr)
    h, left = basket_hedge(ctx, weights, o.index)
    hedged = (1 + loc) * (1 + h) - 1
    both = pd.concat([o, fxr], axis=1).dropna()
    share = float(np.cov(both.iloc[:, 1], both.iloc[:, 0])[0, 1] / both.iloc[:, 0].var())
    return {"local_return": stats.cagr(loc), "fx_return": stats.cagr(fxr), "usd_return": stats.cagr(o),
            "hedged_return": stats.cagr(hedged.dropna()), "hedge_cost": float(-h.mean() * 12),
            "fx_vol_share": share,
            "hedged_minus_unhedged": stats.cagr(hedged.dropna()) - stats.cagr(o),
            "basket": {k: round(v, 4) for k, v in weights.items()},
            "hedge_currencies_left_out": left,
            "formula": "1+r_local=(1+r_usd)/(1+r_fx); 1+r_hedged=(1+r_local)*sum_i w_i*((1+i_US/4)/(1+i_i/4))^(1/3), "
                       "OECD/FRED 3-month rates of the previous month; hedge_cost = annualised mean of 1-factor; "
                       "fx_vol_share = cov(r_fx,r_usd)/var(r_usd)",
            "note": "Approximate: the fund's own country weights were not retrieved, so the basket is an "
                    "equal weight of 10 currencies (MXN BRL ZAR INR IDR PLN HUF CZK CLP COP); BRL has no "
                    "3-month rate in the repo and is left out of the hedge (weights renormalised); "
                    "ID 3-month rate ends 2025-12 (forward-filled 2 months, then dropped)."}


# ---------------------------------------------------------------------------
# Credit loss, FX view, scenarios
# ---------------------------------------------------------------------------
def annual_pd(bucket, years=A.HORIZON_YEARS):
    """Annualised default probability from the 5y/10y cumulative averages (percent in A)."""
    c5, c10 = A.CUM_DEFAULT_5Y_10Y[bucket]
    c = (c5 + (c10 - c5) * (years - 5) / 5) / 100
    return 1 - (1 - c) ** (1 / years)


def credit_loss(mix, recovery):
    """Expected annual credit loss: sum w_b x PD_b x (1 - recovery); weights renormalised to 1."""
    tot = sum(mix.values())
    return sum(w / tot * annual_pd(b) for b, w in mix.items()) * (1 - recovery)


def rating_bucket(r):
    """S&P letter (with +/-) -> AAA/AA/A/BBB/BB/B/CCC bucket."""
    s = str(r).strip().upper().rstrip("+-")
    return s if s in A.CUM_DEFAULT_5Y_10Y else ("CCC" if s.startswith("C") else None)


def fund_rating_mix(ctx, t, weights):
    if t in A.RATING_MIX:
        return A.RATING_MIX[t]
    mix = {}
    for c, w in weights.items():
        b = rating_bucket(ctx.countries.loc[A.CCY_COUNTRY[c], "sp_rating"])
        mix[b] = mix.get(b, 0.0) + w
    return (mix, "sovereign", "S&P sovereign ratings of the basket countries (em_bonds_countries.csv, "
                              "retrieved 2026-11-07), basket-weighted")


LAST_MONTH = None   # set by load(): last full month of returns


def latest_any(s):
    """Latest value and date, flagged '(stale)' when older than A.STALE_MONTHS (display only)."""
    s = s.dropna()
    if not len(s):
        return None, None
    v, d = latest(s)
    return (v, d) if v is not None else (float(s.iloc[-1]), f"{s.index[-1].date()} (stale)")


def latest(s):
    """Latest value and date of a series; (None, None) if empty or older than A.STALE_MONTHS."""
    s = s.dropna()
    if not len(s):
        return None, None
    if LAST_MONTH is not None and s.index[-1] < LAST_MONTH - pd.DateOffset(months=A.STALE_MONTHS):
        return None, None
    return float(s.iloc[-1]), str(s.index[-1].date())


def market_assumptions(ctx, ccys):
    """research.config.MarketAssumptions extended with each basket currency's expected
    inflation (latest World Bank year) and short rate (latest OECD 3-month)."""
    a = MarketAssumptions()
    infl, rf = dict(a.inflation), dict(a.risk_free)
    rf["USD"] = latest(ctx.y["US_3M"])[0]
    for c in ccys:
        iso = A.CCY_COUNTRY[c]
        s = ctx.cpi[iso].dropna() if iso in ctx.cpi else pd.Series(dtype=float)
        infl[c] = float(s.iloc[-1]) if len(s) else np.nan
        col = f"{iso}_3M"
        rf[c] = latest(ctx.y[col])[0] if col in ctx.y else None
    a.inflation, a.risk_free = infl, rf
    return a


def fx_view(ctx, weights):
    """Expected annual depreciation of the basket vs USD: mean of PPP and UIP per currency
    (PPP only where no 3-month rate), basket-weighted."""
    a = market_assumptions(ctx, weights)
    rows = {}
    for c, w in weights.items():
        ppp = -fxview.expected_fx(c, None, a, "ppp")
        uip = -fxview.expected_fx(c, None, a, "uip") if a.risk_free.get(c) is not None else None
        loss = expected_fx_loss(a.inflation[c], a.inflation["USD"],
                                a.risk_free.get(c), a.risk_free["USD"] if a.risk_free.get(c) is not None else None)
        rows[c] = {"weight": w, "inflation": a.inflation[c], "rate_3m": a.risk_free.get(c),
                   "ppp_depreciation": ppp, "uip_depreciation": uip, "expected_depreciation": loss}
    df = pd.DataFrame(rows).T
    tot = df["weight"].sum()
    out = {"expected_depreciation": float((df["weight"] * df["expected_depreciation"]).sum() / tot),
           "ppp": float((df["weight"] * df["ppp_depreciation"]).sum() / tot)}
    u = df.dropna(subset=["uip_depreciation"])
    out["uip"] = float((u["weight"] * u["uip_depreciation"]).sum() / u["weight"].sum())
    out["by_currency"] = {c: {k: (None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v))
                              for k, v in r.items()} for c, r in rows.items()}
    out["us_inflation"], out["us_rate_3m"] = a.inflation["USD"], a.risk_free["USD"]
    return out


def maturity_for_duration(duration, y, freq=A.COUPON_FREQ):
    """Maturity (years) of a par bond whose modified duration equals `duration` (bisection)."""
    lo, hi = 0.25, 40.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if bonds.duration_convexity(y, mid, freq)[0] < duration:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def scenario_return(y0, y_end, duration, years=A.HORIZON_YEARS, freq=A.COUPON_FREQ):
    """Annualised return of a constant-maturity bond fund (duration held constant)
    whose yield moves linearly from y0 to y_end over `years`, priced monthly with
    research.bonds.total_returns."""
    m = maturity_for_duration(duration, y0, freq)
    n = int(years * 12)
    path = pd.Series(np.linspace(y0, y_end, n + 1),
                     index=pd.date_range("2000-01-31", periods=n + 1, freq="ME"))
    r = bonds.total_returns(path, m, freq)
    return float((1 + r).prod() ** (1 / years) - 1)


def real_yield_insample(ctx, iso):
    """Average 10y yield minus CPI YoY, 2010-2017 (in-sample), decimals."""
    a, b = f"{iso}_10Y", f"{iso}_CPIYOY"
    if a not in ctx.y or b not in ctx.y or a in A.EXCLUDED_YIELD_SERIES:
        return None
    s = (ctx.y[a] - ctx.y[b]).loc[IS_START:IS_END].dropna()
    return float(s.mean()) if len(s) >= 24 else None


def expected_block(ctx, t, r_usd, weights):
    """expected_return_7y block: (a) yield-based with scenarios, (b) Monte Carlo median."""
    inp = ctx.inputs.loc[t]
    y0 = float(inp["ytm"])
    er = float(ctx.funds.loc[t, "expense_ratio"])
    if pd.notna(inp.get("duration")):
        dur, dur_src = float(inp["duration"]), f"em_bond_inputs.csv ({inp['as_of_date']})"
    else:
        dur, dur_src = A.DURATION_JUDGEMENT[t]
    mix, kind, mix_src = fund_rating_mix(ctx, t, weights)
    rec, rec_src = A.RECOVERY[kind]
    loss = credit_loss(mix, rec)
    us10, us10_date = latest(ctx.y["US_10Y"])
    a = MarketAssumptions()
    us_fair = (1 + a.real_bond_yield["USD"]) * (1 + a.inflation["USD"]) - 1
    local = t in A.LOCAL_FUNDS
    fxv = fx_view(ctx, weights) if local else None
    if local:
        num = den = cur = 0.0
        for c, w in weights.items():
            iso = A.CCY_COUNTRY[c]
            ry, (y10, _) = real_yield_insample(ctx, iso), latest(ctx.y.get(f"{iso}_10Y", pd.Series(dtype=float)))
            pi = fxv["by_currency"][c]["inflation"]
            if ry is None or y10 is None or pi is None:
                continue
            num += w * ((1 + ry) * (1 + pi) - 1)
            cur += w * y10
            den += w
        fair = y0 + (num - cur) / den
        fair_note = (f"fund yield + (basket fair 10y {num / den:.2%} - basket 10y today {cur / den:.2%}); "
                     "fair = (1 + 2010-2017 average real 10y yield) x (1 + expected inflation) - 1")
    else:
        fair = y0 + (us_fair - us10)
        fair_note = (f"fund yield + (US fair 10y {us_fair:.2%} - US 10y {us10:.2%} on {us10_date}); "
                     "spread held constant (no EM spread history before 2023-11 in the repo)")
    scen_y = {"yields_unchanged": y0, "halfway_to_fair": y0 + 0.5 * (fair - y0),
              "yields_up_200bp": y0 + A.SHOCK, "yields_down_200bp": max(0.0, y0 - A.SHOCK)}
    dep = fxv["expected_depreciation"] if local else 0.0
    # 30-day SEC yields and yfinance trailing distribution yields are already net of fund
    # expenses, so the expense ratio is not subtracted again; a portfolio yield to worst
    # (EMLC's UCITS fact-sheet figure) is gross of fees, so there it is subtracted.
    note = str(inp["notes"]).lower()
    yield_is_net = ("sec yield" in note) or ("trailing" in note)
    fee_deduct = 0.0 if yield_is_net else er
    scen = {}
    for k, ye in scen_y.items():
        gross = scenario_return(y0, ye, dur)
        net_local = gross - fee_deduct - loss
        scen[k] = {"exit_yield": ye, "gross_local": gross, "net_local": net_local,
                   "net_usd": (1 + net_local) * (1 - dep) - 1}
    y_usd, y_loc = scen["halfway_to_fair"]["net_usd"], scen["halfway_to_fair"]["net_local"]
    # (b) Monte Carlo: block bootstrap of the fund's own monthly USD history, drift = yield-based
    st = MonteCarloSettings(n_paths=A.MC_PATHS, horizon_years=A.HORIZON_YEARS,
                            block_months=A.MC_BLOCK, seed=A.MC_SEED)
    hist = r_usd.loc[RF_START:].dropna().to_frame(t)
    mc = montecarlo.simulate(hist, st, targets={t: y_usd})[t]
    mc_med = mc["annualised"]["50"]
    methods = {"capm": None, "dcf": None, "grinold_kroner": None, "yield": y_usd, "monte_carlo_median": mc_med}
    cons = float(np.mean([y_usd, mc_med]))
    out = {
        "methods": methods, "consensus_usd": cons,
        "consensus_local": float(np.mean([y_loc, (1 + mc_med) / (1 - dep) - 1])) if local else cons,
        "range_5_95": [mc["annualised"]["5"], mc["annualised"]["95"]],
        "yield_inputs": {
            "yield": y0, "yield_source": f"em_bond_inputs.csv ytm: {inp['source_url']} ({inp['as_of_date']}); "
                                         f"{str(inp['notes']).split(';')[0]}",
            "funds_csv_yield": float(ctx.funds.loc[t, "yield"]),
            "expense_ratio": er, "duration": dur, "duration_source": dur_src,
            "credit_loss": loss, "rating_mix": mix, "rating_mix_source": mix_src,
            "recovery": rec, "recovery_source": rec_src,
            "fair_yield": fair, "fair_yield_rule": fair_note,
            "fx_expected_depreciation": dep if local else None, "fx_view": fxv,
            "yield_is_net_of_fees": yield_is_net, "fee_deducted": fee_deduct,
            "fee_note": ("the yield is a 30-day SEC yield or a trailing distribution yield, already net of fund "
                         "expenses, so the expense ratio is not subtracted again (fix after review, 2026-11-07)"
                         if yield_is_net else
                         f"the yield is a portfolio yield to worst, gross of fees, so the expense ratio "
                         f"({er:.2%}) is subtracted"),
        },
        "scenarios": scen,
        "monte_carlo": {"median": mc_med, "p5": mc["annualised"]["5"], "p95": mc["annualised"]["95"],
                        "prob_loss_7y": mc["prob_loss_5y"], "paths": A.MC_PATHS, "block_months": A.MC_BLOCK,
                        "history": f"{hist.index[0].date()} to {hist.index[-1].date()}",
                        "independent_method": False,
                        "note": "anchored to the yield drift, not an independent method: "
                                "research.montecarlo.simulate forward mode rescales the history to the "
                                "yield-based return, so the median repeats it and only the range adds "
                                "information; prob_loss key holds the 7-year horizon here (the library names it 5y)"},
        "assumptions": "research/candidates/assumptions_em_bonds.py (credit loss, recovery, rating mixes, "
                       "durations, FX view, fair yield); research/config.py::MarketAssumptions (US fair 10y); "
                       "credit-loss and FX inputs are judgement",
        "command": f"{CMD} --ticker {t}",
    }
    return out


# ---------------------------------------------------------------------------
# Country analysis (constant-maturity 10y from OECD yields)
# ---------------------------------------------------------------------------
MAX_FILL_MONTHS = 3


def gap_safe_total_returns(y, max_fill=MAX_FILL_MONTHS, maturity=10.0, freq=2):
    """Constant-maturity total returns that never splice across a data gap.

    Inside the series' first..last valid month, a gap of at most `max_fill` months is
    forward-filled (yield assumed unchanged); a longer gap is a missing period: the
    series is split there and no return is computed across it (NaN months)."""
    y = y.loc[y.first_valid_index():y.last_valid_index()]
    run = y.isna().groupby(y.notna().cumsum()).transform("sum")   # length of each NaN run
    f = y.where(~(y.isna() & (run > max_fill))).ffill(limit=max_fill)
    f = f.where(~(y.isna() & (run > max_fill)))
    seg = f.isna().cumsum()
    parts = [bonds.total_returns(g, maturity, freq) for _, g in f.dropna().groupby(seg[f.notna()])
             if len(g) > 1]
    return (pd.concat(parts) if parts else pd.Series(dtype=float)).reindex(y.index[1:])


def country_returns(ctx, countries=A.CROSSCHECK_COUNTRIES):
    """Monthly local and USD total returns of a constant-maturity 10y bond per country
    (research.bonds.total_returns, semiannual coupons) from the OECD monthly average yields."""
    inv = {v: k for k, v in A.CCY_COUNTRY.items()}
    loc, usd = {}, {}
    for iso in countries:
        col = f"{iso}_10Y"
        if col not in ctx.y or ctx.y[col].dropna().empty:
            continue
        r = gap_safe_total_returns(ctx.y[col])
        fxr = ctx.fxm[inv[iso]].pct_change(fill_method=None).reindex(r.index)
        loc[iso], usd[iso] = r, (1 + r) * (1 + fxr) - 1
    return pd.DataFrame(loc), pd.DataFrame(usd)


def country_table(ctx, loc, usd):
    rows = []
    for iso in A.CROSSCHECK_COUNTRIES + ["TR"]:
        c = ctx.countries.loc[iso] if iso in ctx.countries.index else {}
        y10, d10 = latest_any(ctx.y[f"{iso}_10Y"]) if f"{iso}_10Y" in ctx.y else (None, None)
        y3, d3 = latest(ctx.y[f"{iso}_3M"]) if f"{iso}_3M" in ctx.y else (None, None)
        if iso == "TR":
            y10, _, src = SPOT_YIELDS["TR_10Y"]
            d10 = f"{SPOT_YIELDS['TR_10Y'][1]} spot ({src})"
        cp, dcp = latest(ctx.y[f"{iso}_CPIYOY"]) if f"{iso}_CPIYOY" in ctx.y else (None, None)
        wb = ctx.cpi[iso].dropna() if iso in ctx.cpi else pd.Series(dtype=float)
        if cp is None or (len(wb) and dcp and int(dcp[:4]) < int(wb.index[-1])):
            cp, dcp = (float(wb.iloc[-1]), f"{wb.index[-1]} (World Bank)") if len(wb) else (None, None)
        rec = {"country": iso, "y10": y10, "y10_date": d10, "y3m": y3, "y3m_date": d3, "cpi": cp,
               "cpi_date": dcp, "real_yield": (y10 - cp) if (y10 is not None and cp is not None) else None,
               "sp": c.get("sp_rating"), "moodys": c.get("moodys_rating"),
               "rating_score": rating_to_score(c.get("sp_rating")),
               "real_yield_is_avg": real_yield_insample(ctx, iso)}
        if iso in loc:
            l, u = loc[iso].loc[IS_START:].dropna(), usd[iso].loc[IS_START:].dropna()
            rec.update(ret_start=str(l.index[0].date()), ret_end=str(l.index[-1].date()),
                       local_cagr=stats.cagr(l), usd_cagr=stats.cagr(u),
                       fx_cagr=(1 + stats.cagr(u)) / (1 + stats.cagr(l)) - 1,
                       local_is=stats.cagr(l.loc[:IS_END]), usd_is=stats.cagr(u.loc[:IS_END]),
                       local_oos=stats.cagr(l.loc[OOS_START:]), usd_oos=stats.cagr(u.loc[OOS_START:]))
        rows.append(rec)
    return pd.DataFrame(rows).set_index("country")


def country_crosscheck(ctx, usd):
    """Equal-weight basket of the country constant-maturity USD returns vs EMLC's realised."""
    bask = basket_return(usd, {c: 1.0 for c in usd.columns})
    e = ctx.M["EMLC"].dropna()
    both = pd.concat([bask.rename("model"), e.rename("EMLC")], axis=1).dropna()
    out = {"countries": list(usd.columns), "start": str(both.index[0].date()), "end": str(both.index[-1].date()),
           "correlation": float(both.corr().iloc[0, 1]),
           "note": "equal weight of available countries each month (ID 10y ends 2024-12, IN starts 2011-12); "
                   "10y constant maturity, semiannual coupon, OECD monthly AVERAGE yields (not month-end), "
                   "no fees or bid-ask; EMLC duration about 5y vs 7-8y for a 10y bond"}
    for name, sl in (("full", slice(None)), ("in_sample", slice(IS_START, IS_END)), ("out_of_sample", slice(OOS_START, None))):
        b = both.loc[sl]
        out[name] = {"model_cagr": stats.cagr(b["model"]), "emlc_cagr": stats.cagr(b["EMLC"]),
                     "model_vol": stats.vol(b["model"]), "emlc_vol": stats.vol(b["EMLC"]), "months": len(b)}
    return out


# ---------------------------------------------------------------------------
# Metrics, stress, rolling
# ---------------------------------------------------------------------------
def windows(r):
    return {"in_sample": r.loc[IS_START:IS_END], "out_of_sample": r.loc[OOS_START:], "full": r.loc[RF_START:]}


def ir_vs(ctx, r):
    out = {}
    for b, s in ctx.benches.items():
        act = (r - s.reindex(r.index)).dropna()
        ir = stats.info_ratio(r, s)
        out[b] = {"info_ratio": None if pd.isna(ir) or act.std() < 1e-10 else ir,
                  "t_stat_ir": None if pd.isna(ir) or act.std() < 1e-10 else ir / math.sqrt(12) * math.sqrt(len(act))}
    return out


def metrics_all(ctx, t, r_usd, r_loc, b_usd, b_loc):
    out = {}
    for w, r in windows(r_usd).items():
        r = r.dropna()
        u = metrics_block(r, b_usd, ctx.rf, n_trials=A.N_TRIALS)
        u["info_ratio_vs"] = ir_vs(ctx, r)
        if t in A.LOCAL_FUNDS:
            rl = windows(r_loc)[w].dropna()
            l = metrics_block(rl, b_loc, ctx.rf, n_trials=A.N_TRIALS)
        else:
            l = u
        out[w] = {"usd": u, "local": l}
    return out


def window_return(r, start, end):
    """Total return over (start, end], month-end to month-end; None if the series does
    not cover the whole window."""
    r = r.dropna()
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    if r.empty or r.index[0] > s + pd.offsets.MonthEnd(1) or r.index[-1] < e:
        return None
    return float((1 + r.loc[s + pd.Timedelta(days=1):e]).prod() - 1)


def strong_usd_months(ctx):
    d = ctx.y["USD_BROAD"].dropna().pct_change()
    return d[d >= A.STRONG_USD_THRESHOLD].index


def stress_block(ctx, r, b, bname):
    out = {}
    g = ctx.benches["GUIDE_BENCH"]
    for k, (s, e) in A.STRESS.items():
        out[k] = {"start": s, "end": e, "return": window_return(r, s, e), "benchmark": window_return(b, s, e),
                  "benchmark_id": bname, "guide_bench": window_return(g, s, e)}
    m = strong_usd_months(ctx)
    rr, bb = r.reindex(m).dropna(), b.reindex(m).dropna()
    out["strong_usd"] = {
        "definition": f"months when the FRED broad dollar index DTWEXBGS (monthly average, yields.csv "
                      f"USD_BROAD) rose >= {A.STRONG_USD_THRESHOLD:.0%}; plus two episodes",
        "months": [str(x.date()) for x in rr.index], "avg_return": float(rr.mean()) if len(rr) else None,
        "benchmark": float(bb.mean()) if len(bb) else None, "benchmark_id": bname,
        "episodes": {k: {"start": s, "end": e, "return": window_return(r, s, e), "benchmark": window_return(b, s, e)}
                     for k, (s, e) in A.STRONG_USD_EPISODES.items()}}
    return out


def rolling_block(ctx, r, b):
    sh = stats.rolling_sharpe(r.loc[RF_START:].dropna(), ctx.rf)
    ir = stats.rolling_ir(r.loc[RF_START:].dropna(), b)
    idx = sh.index.union(ir.index)
    oos = ir.loc[OOS_START:]
    return {"dates": [str(d.date()) for d in idx],
            "sharpe": [None if pd.isna(v) else float(v) for v in sh.reindex(idx)],
            "info_ratio": [None if pd.isna(v) else float(v) for v in ir.reindex(idx)],
            "share_ir_positive_oos": float((oos > 0).mean()) if len(oos) else None,
            "share_ir_positive_full": float((ir > 0).mean()) if len(ir) else None,
            "window_months": 36}


# ---------------------------------------------------------------------------
# One fund
# ---------------------------------------------------------------------------
NAMES_INSTR = {"ETF": "etf", "MUTUALFUND": "mutual_fund"}


def clean(x):
    """JSON-safe: NaN/inf -> None, numpy -> python."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def analyse(ctx, t):
    r_usd = ctx.M[t].dropna()
    bname = A.BENCHMARK[t]
    b_usd = ctx.benches[bname]
    weights = basket_weights(ctx) if t in A.LOCAL_FUNDS else {}
    if t in A.LOCAL_FUNDS:
        fxr = basket_return(ctx.fx, weights).reindex(r_usd.index)
        r_loc = local_from_usd(r_usd, fxr)
        e_loc = local_from_usd(ctx.M["EMLC"], basket_return(ctx.fx, weights).reindex(ctx.M.index))
        b_loc = e_loc if t != "EMLC" else None
    else:
        r_loc, b_loc = r_usd, b_usd
    sc = ctx.scored.loc[t]
    ist = ctx.istable.loc[t]
    fund = ctx.funds.loc[t]
    ll = ctx.longlist.loc[t]
    doc = {
        "schema_version": 1, "id": t, "ticker": t, "usd_ticker": t, "name": str(ll["name"]),
        "position_type": "em_bond", "instrument": NAMES_INSTR.get(str(fund["quoteType"]), "etf"),
        "country": "EM", "currency": "LOCAL" if t in A.LOCAL_FUNDS else "USD", "sector": str(ll["category"]),
        "non_us": True, "benchmark": bname,
        "data": {"price_start": str(ctx.M[t].first_valid_index().date()), "price_end": str(r_usd.index[-1].date()),
                 "months_total": int(len(r_usd)), "months_in_sample": int(len(r_usd.loc[IS_START:IS_END])),
                 "months_out_of_sample": int(len(r_usd.loc[OOS_START:])),
                 "sources": ["data/research/prices.csv", "data/research/fx.csv", "data/research/yields.csv",
                             "data/research/cpi_annual.csv", "data/research/funds.csv",
                             "research/plan/longlists/em_bond_inputs.csv", "research/plan/longlists/em_bonds_countries.csv"],
                 "fund_fee": float(fund["expense_ratio"]),
                 "notes": data_notes(t, r_usd)},
        "metrics": metrics_all(ctx, t, r_usd, r_loc, b_usd, b_loc),
        "rolling": rolling_block(ctx, r_usd, b_usd),
        "currency": currency_block(ctx, t, r_usd, weights or None),
        "expected_return_7y": expected_block(ctx, t, r_usd, weights or basket_weights(ctx)),
        "stress": stress_block(ctx, r_usd, b_usd, bname),
        "screens": {"fundamental_score": float(sc["fundamental_score"]), "technical_score": None,
                    "hard_screens_passed": str(sc["passed"]) == "True",
                    "detail": {"ytm": sc["ytm"], "carry": sc["carry"], "rating_score": sc["rating_score"],
                               "corr_equity": sc["corr_equity"], "carry_score": sc["carry_score"],
                               "credit_score": sc["credit_score"], "cost_liquidity_score": sc["cost_liquidity_score"],
                               "diversification_score": sc["diversification_score"],
                               "insample_rank": int(ist["rank"]), "insample_composite": ist["composite"],
                               "insample_table_benchmark": ist["benchmark"], "insample_table_ir": ist["ir_is"],
                               "technical_note": "no technical signal kept for em_bond (em_bond_signals.csv)",
                               "as_of": "2017-12-31"}},
        "rubric": {"scores": {}, "total": None, "rank_in_type": None},
        "review": None,
        "memo": f"research/candidates/memos/{t}.md",
        "charts": {"growth": f"reports/candidates/charts/{t}_growth.png",
                   "rolling": f"reports/candidates/charts/{t}_rolling.png"},
        "reproduce": f"{CMD} --ticker {t} --write",
    }
    if t in A.LOCAL_FUNDS:
        doc["currency"]["sensitivity_gbiem_weights"] = {
            k: v for k, v in currency_block(ctx, t, r_usd, basket_weights(ctx, "gbiem")).items()
            if k in ("local_return", "fx_return", "usd_return", "hedged_return", "hedge_cost", "fx_vol_share",
                     "basket", "hedge_currencies_left_out")}
        _, usd = country_returns(ctx)
        doc["expected_return_7y"]["country_crosscheck"] = country_crosscheck(ctx, usd)
    if t in ("EMB", "EMLC"):
        doc["data"]["notes"] += (f" {t} is itself a method benchmark: its IR is reported against GUIDE_BENCH "
                                 "(55% ACWX/35% EMB/10% GLD, quarterly) as the headline and against "
                                 "the other EM benchmark in metrics.*.usd.info_ratio_vs.")
    doc["explain"] = explain(doc)
    return clean(doc)


def data_notes(t, r):
    n = []
    if len(r.loc[:IS_END].loc[IS_START:]) < 96:
        n.append(f"{len(r.loc[IS_START:IS_END])} in-sample months (inception after 2010-01)")
    if len(r) < 120:
        n.append("short history")
    n.append("monthly returns from Yahoo adjusted close (distributions reinvested, net of fund fees); "
             "November 2026 is partial and dropped; 'full' window starts at the first BIL month (2007-06) "
             "or inception")
    if t in A.LOCAL_FUNDS:
        n.append("local-currency return is an approximation: USD return with an equal-weight 10-currency "
                 "basket's FX return stripped out (fund weights not retrieved)")
    return "; ".join(n) + "."


CATEGORY_WORDS = {"hard_sov": "a US-dollar government", "local_sov": "a local-currency government",
                  "high_yield": "a US-dollar high-yield corporate", "corporate": "a US-dollar corporate"}


def explain(doc):
    t = doc["id"]
    o = doc["metrics"]["out_of_sample"]["usd"]
    i = doc["metrics"]["in_sample"]["usd"]
    e = doc["expected_return_7y"]
    s1 = (f"{t} is {CATEGORY_WORDS.get(doc['sector'], 'an')} emerging-market bond fund; from 2018 to Oct 2026 it returned "
          f"{o['cagr']:.1%} a year with a worst fall of {o['max_drawdown']:.0%}, versus {i['cagr']:.1%} a year in 2010-2017.")
    if t in A.LOCAL_FUNDS:
        c = doc["currency"]
        s2 = (f"Its bonds earned about {c['local_return']:.1%} a year in local currency since 2018, but the "
              f"currencies changed the result by {c['fx_return']:+.1%} a year, and hedging them would have cost "
              f"about {c['hedge_cost']:.1%} a year.")
    else:
        s2 = (f"It pays dollars, so its risk is credit (countries or companies not paying) and US interest rates, "
              f"not currencies; its Sharpe ratio since 2018 is {o['sharpe']:.2f}.")
    s3 = (f"Our forward estimate for the next 7 years is about {e['consensus_usd']:.1%} a year in dollars "
          f"(5-95% range {e['range_5_95'][0]:.0%} to {e['range_5_95'][1]:.0%}), built from today's yield less fees "
          f"and expected defaults.")
    return [s1, s2, s3]


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def chart_growth(ctx, t, path):
    plt = _plt()
    r = ctx.M[t].loc[RF_START:].dropna()
    fig, ax = plt.subplots(figsize=(8, 4.2))
    names = [t] + [b for b in dict.fromkeys([A.BENCHMARK[t], A.METHOD_BENCHMARK[t]]) if b != t]
    for n in names:
        s = (r if n == t else ctx.benches[n].reindex(r.index)).dropna()
        lvl = 10_000 * (1 + s).cumprod()
        ax.plot(lvl.index, lvl, lw=2.2 if n == t else 1.3, label=n, color=None if n == t else None,
                alpha=1 if n == t else 0.8)
    ax.axvspan(pd.Timestamp(IS_START), pd.Timestamp(IS_END), color="0.9", zorder=0, label="in-sample 2010-2017")
    ax.set_title(f"{t}: growth of $10,000 (USD, monthly total return)")
    ax.set_ylabel("USD")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def chart_rolling(doc, path):
    plt = _plt()
    ro = doc["rolling"]
    d = pd.to_datetime(ro["dates"])
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.plot(d, [np.nan if v is None else v for v in ro["sharpe"]], label="36m Sharpe (vs BIL)")
    ax.plot(d, [np.nan if v is None else v for v in ro["info_ratio"]], label=f"36m IR vs {doc['benchmark']}")
    ax.axhline(0, color="0.4", lw=0.8)
    ax.axvline(pd.Timestamp(OOS_START), color="0.5", ls="--", lw=0.8)
    ax.text(pd.Timestamp(OOS_START), ax.get_ylim()[1] * 0.9, " out of sample", fontsize=8, color="0.4")
    ax.set_title(f"{doc['id']}: rolling 36-month Sharpe and information ratio")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def chart_countries(tab, path):
    plt = _plt()
    d = tab.dropna(subset=["real_yield", "rating_score"])
    d = d[d.index != "TR"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.scatter(d["rating_score"], d["real_yield"] * 100, s=40)
    for iso, row in d.iterrows():
        ax.annotate(f"{iso} ({row['sp']})", (row["rating_score"], row["real_yield"] * 100),
                    textcoords="offset points", xytext=(4, 3), fontsize=8)
    ax.set_xlabel("S&P rating (1 = AAA ... 10 = BBB- ... 13 = BB-)")
    ax.set_ylabel("real 10y yield, % (10y minus latest CPI)")
    ax.set_title("EM local bonds: real yield vs credit rating (latest data)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Memos
# ---------------------------------------------------------------------------
HOLDS = {
    "EMB": "Passive USD sovereign and quasi-sovereign bonds, JPM EMBI Global Diversified Core; 619 holdings; "
           "duration 6.38y; ratings A 17%, BBB 34%, BB 26%, B 19%, CCC 3% (iShares, 2026-11-05).",
    "PCY": "Passive USD sovereign bonds with equal country weights (index stated from memory, unverified: DBIQ EM "
           "USD Liquid Balanced); duration, holdings and rating mix not retrieved (Invesco page unreadable).",
    "HYEM": "Passive USD high-yield EM corporate bonds (ICE BofA Diversified HY US EM Corporate Plus, from memory, "
            "unverified); duration and rating mix not retrieved (VanEck page failed).",
    "CEMB": "Passive USD EM corporate bonds, JPM CEMBI Broad Diversified Core; 1,185 holdings; effective duration "
            "4.21y (iShares, 2026-11-05); rating mix not retrieved.",
    "EMLC": "Passive local-currency EM government bonds, JPM GBI-EM Global Core (from memory, unverified); effective "
            "duration 5.13y, yield to worst 6.42% (VanEck UCITS fact sheet 2026-08-31); country weights not retrieved.",
    "EBND": "Passive local-currency EM government bonds, Bloomberg EM Local Currency Government Diversified; 671 "
            "holdings; option-adjusted duration 6.07y (SSGA, 2026-11-05); country weights not retrieved.",
    "TGEIX": "Active, mainly USD EM sovereign and corporate bonds (benchmark EMBI GD, from memory, unverified); may "
             "hold some local-currency debt; holdings, duration and rating mix not retrieved.",
    "PYEMX": "Active, mainly USD EM sovereign bonds (benchmark EMBI GD, from memory, unverified); holdings, duration "
             "and rating mix not retrieved.",
}
DRIVERS = {
    "hard_sov": "carry (US Treasury yield plus the EM sovereign spread), spread changes (risk appetite, defaults "
                "such as the 2020-22 restructurings), and US rates through a 6-7 year duration. No currency leg.",
    "high_yield": "mostly spread: high carry, high sensitivity to defaults and risk appetite; shorter duration so US "
                  "rates matter less. No currency leg.",
    "corporate": "corporate spread plus US rates (duration about 4y); investment-grade bias, so lower carry and "
                 "smaller default losses. No currency leg.",
    "local_sov": "local carry (high local yields), local rates, and above all the currency: the FX leg explains most "
                 "of the USD variance (fx_vol_share below).",
}
VERDICT = {}   # filled after the first full run, see VERDICTS_TEXT below


def _missing(x):
    return x is None or (isinstance(x, float) and not np.isfinite(x))


def pct(x, d=1):
    return "n/a" if _missing(x) else f"{x * 100:.{d}f}%"


def num(x, d=2):
    return "n/a" if _missing(x) else f"{x:.{d}f}"


def memo(ctx, doc, tab):
    t = doc["id"]
    m = doc["metrics"]
    i, o = m["in_sample"]["usd"], m["out_of_sample"]["usd"]
    e = doc["expected_return_7y"]
    yi = e["yield_inputs"]
    c = doc["currency"]
    cat = doc["sector"]
    local = t in A.LOCAL_FUNDS
    if local:
        top = ["MX", "BR", "ZA", "IN", "ID", "PL", "HU", "CZ", "CL", "CO"]
        top_src = "equal-weight 10-currency basket (fund weights not retrieved)"
    else:
        w = ctx.countries["weight_embi_pct"].dropna().sort_values(ascending=False)
        top = list(w.index[:6])
        top_src = ("largest EMBI weights shown on the iShares EMB page (2026-11-05, em_bonds_countries.csv); "
                   + ("these are EMB's own weights" if t == "EMB" else
                      f"used as a proxy, {t}'s own country weights were not retrieved"))
    lines = [f"# {t}: {doc['name']}", "",
             f"Candidate memo, EM bond funds (Phase 3). Benchmark {doc['benchmark']}"
             + (f" (method benchmark {A.METHOD_BENCHMARK[t]}; {t} is itself a method benchmark)" if t in ("EMB", "EMLC") else "")
             + f". Fee {pct(doc['data']['fund_fee'], 2)}. Reproduce: `{doc['reproduce']}`.", "",
             "## What it holds", "", HOLDS[t], "",
             f"Top countries ({top_src}): " + ", ".join(
                 f"{x} {ctx.countries.loc[x, 'weight_embi_pct' if not local else 'sp_rating']}" + ("%" if not local else "")
                 for x in top) + ".", "",
             "## What drives returns", "", DRIVERS.get(cat, DRIVERS["hard_sov"]), "",
             "| | In-sample 2010-17 | Out of sample 2018-26 |", "|---|---|---|",
             f"| CAGR | {pct(i['cagr'])} | {pct(o['cagr'])} |",
             f"| Volatility | {pct(i['vol'])} | {pct(o['vol'])} |",
             f"| Sharpe (vs BIL) | {num(i['sharpe'])} | {num(o['sharpe'])} |",
             f"| IR vs {doc['benchmark']} (t) | {num(i.get('info_ratio'))} ({num(i.get('t_stat_ir'), 1)}) | "
             f"{num(o.get('info_ratio'))} ({num(o.get('t_stat_ir'), 1)}) |",
             f"| IR vs EMB / EMLC | {num(i['info_ratio_vs']['EMB']['info_ratio'])} / {num(i['info_ratio_vs']['EMLC']['info_ratio'])} | "
             f"{num(o['info_ratio_vs']['EMB']['info_ratio'])} / {num(o['info_ratio_vs']['EMLC']['info_ratio'])} |",
             f"| Alpha (t) | {pct(i.get('alpha'))} ({num(i.get('t_stat_alpha'), 1)}) | {pct(o.get('alpha'))} ({num(o.get('t_stat_alpha'), 1)}) |",
             f"| Max drawdown | {pct(i['max_drawdown'])} | {pct(o['max_drawdown'])} |",
             f"| Deflated Sharpe (N=20) | {num(i['deflated_sharpe'])} | {num(o['deflated_sharpe'])} |",
             f"| Months | {i['months']} | {o['months']} |", ""]
    if local:
        lines += [f"Currency, OOS a year: local {pct(c['local_return'])}, FX {pct(c['fx_return'])}, USD "
                  f"{pct(c['usd_return'])}, hedged {pct(c['hedged_return'])} (hedge cost {pct(c['hedge_cost'])}, "
                  f"BRL left out of the hedge for lack of a 3-month rate); FX share of USD variance "
                  f"{num(c['fx_vol_share'])}. With LEMB's GBI-EM weights instead: FX "
                  f"{pct(c['sensitivity_gbiem_weights']['fx_return'])}, hedged "
                  f"{pct(c['sensitivity_gbiem_weights']['hedged_return'])}.", ""]
        cc = e["country_crosscheck"]
        lines += [f"Country cross-check: an equal-weight basket of 10y constant-maturity bonds in "
                  f"{', '.join(cc['countries'])} returned {pct(cc['full']['model_cagr'])} a year in USD over "
                  f"{cc['start'][:7]} to {cc['end'][:7]} against EMLC's {pct(cc['full']['emlc_cagr'])} "
                  f"(correlation {num(cc['correlation'])}; OOS {pct(cc['out_of_sample']['model_cagr'])} vs "
                  f"{pct(cc['out_of_sample']['emlc_cagr'])}). The model has no fees and a longer duration.", ""]
    lines += ["## Fundamentals (top countries)", "",
              "| Country | 10y | 3m | CPI | Real 10y | S&P / Moody's |", "|---|---|---|---|---|---|"]
    for x in top:
        if x not in tab.index:
            lines.append(f"| {x} | n/a | n/a | n/a | n/a | {ctx.countries.loc[x, 'sp_rating']} / "
                         f"{ctx.countries.loc[x, 'moodys_rating']} |")
            continue
        r = tab.loc[x]
        lines.append(f"| {x} | {pct(r['y10'])} | {pct(r['y3m'])} | {pct(r['cpi'])} | {pct(r['real_yield'])} | "
                     f"{r['sp']} / {r['moodys']} |")
    lines += ["", "Debt/GDP and current account are not in the repo data and were not checked. Gulf and Asian "
              "issuers without OECD series show n/a. Full table: `research/candidates/memos/em_bonds_countries.md`.", "",
              "## Forward view (7 years, USD)", "",
              f"Yield {pct(yi['yield'], 2)} ({yi['yield_source'].split(':')[0]}; {yi['yield_source'].split(';')[-1].strip()}) "
              f"minus fee {pct(yi['expense_ratio'], 2)} minus expected credit loss {pct(yi['credit_loss'], 2)} "
              f"(rating mix: {yi['rating_mix_source']}; recovery {yi['recovery']:.0%})"
              + (f", minus expected FX depreciation {pct(yi['fx_expected_depreciation'], 2)} (PPP {pct(yi['fx_view']['ppp'], 2)}, "
                 f"UIP {pct(yi['fx_view']['uip'], 2)})" if local else "")
              + f"; duration {num(yi['duration'], 1)}y ({yi['duration_source']}).",
              "", "| Scenario | Exit yield | Net USD a year |", "|---|---|---|"]
    for k, s in e["scenarios"].items():
        lines.append(f"| {k.replace('_', ' ')} | {pct(s['exit_yield'], 2)} | {pct(s['net_usd'])} |")
    lines += ["", f"Yield-based (halfway to fair) {pct(e['methods']['yield'])}; Monte Carlo median "
              f"{pct(e['methods']['monte_carlo_median'])}; **consensus {pct(e['consensus_usd'])}**, 5-95% range "
              f"{pct(e['range_5_95'][0])} to {pct(e['range_5_95'][1])}. The credit-loss, rating-mix and FX inputs "
              f"are judgement. {yi['fee_note'][0].upper() + yi['fee_note'][1:]}.", "",
              "## Stress (USD total return; benchmark in brackets)", ""]
    st = doc["stress"]
    lines.append("; ".join(f"{k}: {pct(v['return'])} ({pct(v['benchmark'])})" for k, v in st.items() if k != "strong_usd")
                 + f"; strong-USD months average {pct(st['strong_usd']['avg_return'])} ({pct(st['strong_usd']['benchmark'])}).")
    lines += ["", "## Technicals", "", "No technical signal was kept for EM bonds (all five failed the "
              "pre-registered out-of-sample test, em_bond_signals.csv), so none is used here.", "",
              "## Risks", "", RISKS.get(t, ""), "", "## Verdict", "", VERDICTS_TEXT.get(t, "(see report)"), "",
              "> **How to explain this pick**", ">"]
    lines += [f"> {s}" for s in doc["explain"]]
    return "\n".join(lines) + "\n"


RISKS = {
    "EMB": "Sovereign defaults and restructurings (2020-23: Lebanon, Sri Lanka, Ghana, Zambia, Russia, Ukraine); "
           "US rate rises (2022: about -18%); concentration in Gulf issuers. Evidence on forward returns is "
           "a yield, not a forecast of spreads.",
    "PCY": "Same as EMB plus longer duration and more weight on small, lower-rated countries (equal weighting); "
           "worst drawdown of the hard-currency group out of sample.",
    "HYEM": "Corporate defaults in a downturn (China property 2021-22 hit EM high yield); liquidity of a "
            "$0.5bn ETF in stress; only 67 in-sample months (short in-sample history).",
    "CEMB": "Corporate spread and US rates; small ETF ($0.4bn) with thin trading; only 68 in-sample months.",
    "EMLC": "Currency: the dollar's strength since 2011 took most of the local carry; local rate shocks; "
            "China/Asia low-yield weights dilute carry. The local-currency view is approximate (basket, not fund weights).",
    "EBND": "As EMLC; different index (Bloomberg) and slightly longer duration; same currency exposure.",
    "TGEIX": "Active-manager risk (style drift, key-person); higher fee 0.85%; may hold local-currency bonds, "
             "so some FX exposure that this analysis does not measure.",
    "PYEMX": "Active-manager risk; fee 0.73%; holdings not retrieved, so the rating mix is assumed.",
}
# Written after the first full run (2026-11-07) from the numbers in reports/candidates/<ID>.json.
# None of the eight has an OOS Sharpe that survives deflation (DSR <= 0.07 with N = 20), so the
# ranking leans on OOS IR, drawdown and the forward yield, as method.md section 7 allows.
VERDICTS_TEXT = {
    "HYEM": "Rank 1 of 8. Best OOS Sharpe (0.13) and a positive IR vs EMB (0.22, t 0.7) with IR above zero in "
            "80% of OOS rolling windows; in-sample Sharpe 0.98 held up best in relative terms. The price is credit "
            "risk: the largest assumed credit loss (1.9%/yr) leaves a 5.5% forward estimate, below EMB's 6.3%. "
            "Keep as the credit-risk pick; evidence is weak (t < 1).",
    "PYEMX": "Rank 2 of 8. Highest OOS IR vs EMB (0.29, t 0.9), IR positive in 85% of OOS windows, and the "
             "highest forward estimate (6.8%) on a 7.0% distribution yield. Active fee 0.73%. Keep as the active "
             "hard-currency pick; its rating mix is assumed, not retrieved.",
    "CEMB": "Rank 3 of 8. Smallest OOS drawdown (-20%, the only one inside the -25% security budget) and the "
            "narrowest forward range (1.2% to 10.6%); OOS IR vs EMB 0.09. Weak in-sample (IR -0.15). Keep as the "
            "'security' bond; small ETF ($0.4bn) with thin trading.",
    "TGEIX": "Rank 4 of 8. OOS IR vs EMB 0.17 (t 0.5) but the second-worst Covid fall (-20%) and a 0.85% fee. Note: "
             "the Phase 2 table's 0.81 in-sample IR was measured against EMLC (the screen classed it local); vs EMB "
             "it was 0.27. Runner-up behind PYEMX.",
    "EMB": "Rank 5 of 8, but the default passive core. OOS Sharpe 0.02; as the benchmark it has no IR vs itself; vs "
           "GUIDE_BENCH -0.76 (t -2.3), i.e. EM bonds as a whole lagged the 55/35/10 since 2018. Cheapest (0.39%), most "
           "liquid, forward 6.3% (second highest). Keep as the core holding or the fallback if active funds are not wanted.",
    "PCY": "Rank 6 of 8. Drop under method.md section 8 rule 2: OOS Sharpe (-0.01) below EMB's (0.02) and OOS IR "
           "vs EMB below zero (-0.09); worst OOS drawdown of the eight (-36%) from its long duration in 2022.",
    "EMLC": "Rank 7 of 8 unhedged. OOS Sharpe -0.10; the currency basket cost about 2.3%/yr since 2018 and hedging "
            "would have cost about 2.8%/yr (CIP), so hedged was no better (0.4% vs 0.9% a year). Not a pick on its "
            "own record; kept only as the vehicle for the overlay analyst's FX-hedge test and as the local benchmark.",
    "EBND": "Rank 8 of 8. Drop under section 8 rule 2: OOS Sharpe -0.14 below EMLC's -0.10 and IR vs EMLC -0.12. "
            "Same currency problem as EMLC with no offsetting benefit.",
}


# ---------------------------------------------------------------------------
# Control group and country files
# ---------------------------------------------------------------------------
CONTROL_NOTES = {
    "TGEIX": "Phase 2 in-sample IR (0.81) was measured vs EMLC because the screen classed the fund local-currency; "
             "vs EMB (its correct benchmark) it is in ir_is",
    "PEBIX": "Phase 2 in-sample IR (0.60) was measured vs EMLC because the screen classed the fund local-currency; "
             "vs EMB (its correct benchmark) it is in ir_is (-0.03)",
}


def control(ctx):
    rows = []
    for t, s in ctx.scored.iterrows():
        if str(s["passed"]) != "True":
            continue
        cat = str(s["category"])
        b = "GUIDE_BENCH" if t in ("EMB", "EMLC") else ("EMLC" if cat == "local_sov" else "EMB")
        r = ctx.M[t].dropna()
        bs = ctx.benches[b]
        rec = {"ticker": t, "name": s["name"], "category": cat, "benchmark": b}
        for w, rr in (("is", r.loc[IS_START:IS_END]), ("oos", r.loc[OOS_START:])):
            mb = metrics_block(rr, bs, ctx.rf, n_trials=A.N_TRIALS)
            rec.update({f"months_{w}": mb["months"], f"cagr_{w}": mb.get("cagr"), f"sharpe_{w}": mb.get("sharpe"),
                        f"ir_{w}": mb.get("info_ratio"), f"t_ir_{w}": mb.get("t_stat_ir"),
                        f"maxdd_{w}": mb.get("max_drawdown"), f"dsr_{w}": mb.get("deflated_sharpe")})
        it = ctx.istable.loc[t]
        rec["notes"] = CONTROL_NOTES.get(t, "")
        rec.update(insample_rank=it["rank"], insample_composite=it["composite"],
                   insample_table_benchmark=it["benchmark"], insample_table_ir=it["ir_is"],
                   shortlisted=t in A.CANDIDATES)
        rows.append(rec)
    df = pd.DataFrame(rows).set_index("ticker")
    df["oos_sharpe_rank"] = df["sharpe_oos"].rank(ascending=False)
    rank = {"composite_vs_oos_sharpe": is_oos_rank_test(df["insample_composite"], df["sharpe_oos"]),
            "is_sharpe_vs_oos_sharpe": is_oos_rank_test(df["sharpe_is"], df["sharpe_oos"]),
            "composite_vs_oos_ir": is_oos_rank_test(df["insample_composite"], df["ir_oos"])}
    return df, rank


def countries_memo(tab, cc):
    L = ["# EM local-currency government bonds: country table", "",
         "Built by `python -m research.candidates.em_bonds --all --write`. Yields: OECD/FRED monthly averages in "
         "`data/research/yields.csv` (latest observation, date shown). CPI: latest OECD year-on-year, or the World "
         "Bank annual figure (`cpi_annual.csv`) when it is newer. Real yield = 10y minus CPI. Ratings: "
         "`research/plan/longlists/em_bonds_countries.csv` (Wikipedia / countryeconomy.com, retrieved 2026-11-07). "
         "Realised returns: a constant-maturity 10y bond rebuilt from the yields with `research.bonds.total_returns` "
         "(semiannual coupon, bought at par each month, no fees), converted to USD at month-end FX. "
         "Gap rule (all countries): a missing yield month inside a series is forward-filled when the gap is at "
         "most 3 months; a longer gap is a missing period with no return, and returns are never spliced across "
         "it (MX_10Y has 63 missing months; before this fix the splice showed the peso rising). "
         "Turkey has no free yield history (spot quote only, research.config.SPOT_YIELDS); no return is shown.", "",
         "| Country | 10y (date) | 3m | CPI (date) | Real 10y | Real 10y avg 2010-17 | S&P / Moody's | Local CAGR | USD CAGR | FX a year | USD in-sample / OOS | Period |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for iso, r in tab.iterrows():
        L.append(f"| {iso} | {pct(r['y10'], 2)} ({str(r['y10_date']) if iso != 'TR' else 'spot 2026-10-23'}) | "
                 f"{pct(r['y3m'], 2)} | {pct(r['cpi'], 1)} ({r['cpi_date']}) | {pct(r['real_yield'], 2)} | "
                 f"{pct(r.get('real_yield_is_avg'), 2)} | {r['sp']} / {r['moodys']} | {pct(r.get('local_cagr'))} | "
                 f"{pct(r.get('usd_cagr'))} | {pct(r.get('fx_cagr'))} | {pct(r.get('usd_is'))} / {pct(r.get('usd_oos'))} | "
                 + (f"{str(r.get('ret_start'))[:7]} to {str(r.get('ret_end'))[:7]} |" if isinstance(r.get('ret_start'), str) else "none |"))
    L += ["", f"Cross-check against EMLC: the equal-weight model basket returned {pct(cc['full']['model_cagr'])} a "
          f"year in USD vs EMLC {pct(cc['full']['emlc_cagr'])} ({cc['start'][:7]} to {cc['end'][:7]}, correlation "
          f"{num(cc['correlation'])}); in-sample {pct(cc['in_sample']['model_cagr'])} vs {pct(cc['in_sample']['emlc_cagr'])}, "
          f"OOS {pct(cc['out_of_sample']['model_cagr'])} vs {pct(cc['out_of_sample']['emlc_cagr'])}. "
          "Caveats: monthly-average yields smooth the series; a 10y bond has more duration than EMLC (about 5y); "
          "no fees, bid-ask or withholding tax; ID ends 2024-12; IN starts 2012.", "",
          "Brazil: the OECD long-term rate in yields.csv (BR_10Y) follows the TJLP/TLP policy lending rate "
          "(6.0% in 2010-11, 5.0% in 2013-14, 7.5% in 2016), not a traded 10y bond yield, so it is excluded "
          "(research/candidates/assumptions_em_bonds.py EXCLUDED_YIELD_SERIES) and no Brazilian return is shown. "
          "Turkey's 3-month series ends 2008 and is not used.", "",
          "Not checked: debt/GDP and current account (not in the repo data). Chart: "
          "`reports/candidates/charts/em_bonds_countries_realyield.png`.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def write_fund(ctx, doc, tab):
    OUT.mkdir(parents=True, exist_ok=True)
    CHARTS.mkdir(parents=True, exist_ok=True)
    MEMOS.mkdir(parents=True, exist_ok=True)
    t = doc["id"]
    (OUT / f"{t}.json").write_text(json.dumps(doc, indent=1, allow_nan=False), encoding="utf-8")
    chart_growth(ctx, t, ROOT / doc["charts"]["growth"])
    chart_rolling(doc, ROOT / doc["charts"]["rolling"])
    (ROOT / doc["memo"]).write_text(memo(ctx, doc, tab), encoding="utf-8")


def summary_line(doc):
    o = doc["metrics"]["out_of_sample"]["usd"]
    c, e = doc["currency"], doc["expected_return_7y"]
    return (f"{doc['id']:6s} OOS Sharpe {num(o['sharpe'])}  IR {num(o.get('info_ratio'))}  maxDD {pct(o['max_drawdown'])}  "
            f"DSR {num(o['deflated_sharpe'])}  fx {pct(c['fx_return'])}  hedged-unhedged "
            f"{pct(c.get('hedged_minus_unhedged', 0.0))}  E7y {pct(e['consensus_usd'])} "
            f"[{pct(e['range_5_95'][0])}, {pct(e['range_5_95'][1])}]")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ticker")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    if not args.all and not args.ticker:
        ap.error("give --all or --ticker")
    ctx = load()
    loc, usd = country_returns(ctx)
    tab = country_table(ctx, loc, usd)
    tickers = A.CANDIDATES if args.all else [args.ticker.upper()]
    for t in tickers:
        if t not in A.CANDIDATES:
            raise SystemExit(f"{t} is not one of the 8 shortlisted EM bond funds: {A.CANDIDATES}")
        doc = analyse(ctx, t)
        print(summary_line(doc))
        if args.write:
            write_fund(ctx, doc, tab)
    if args.all:
        df, rank = control(ctx)
        cc = country_crosscheck(ctx, usd)
        print(df[["sharpe_is", "sharpe_oos", "ir_is", "ir_oos", "maxdd_oos", "insample_composite"]].round(2).to_string())
        print(json.dumps(clean(rank), indent=1))
        print(tab[["y10", "y3m", "cpi", "real_yield", "sp", "local_cagr", "usd_cagr"]].round(4).to_string())
        if args.write:
            df.to_csv(OUT / "em_bonds_control.csv", float_format="%.6g")
            (OUT / "em_bonds_control_rank.json").write_text(json.dumps(clean(
                {**rank, "note": "Spearman rank correlation (research.screen.is_oos_rank_test) of the in-sample "
                                 "composite (em_bond_insample_table.csv; EMB and EMLC have none, n=18) and of the "
                                 "in-sample Sharpe (n=20) with OOS Sharpe/IR",
                 "command": f"{CMD} --all --write"}), indent=1), encoding="utf-8")
            (MEMOS / "em_bonds_countries.md").write_text(countries_memo(tab, cc), encoding="utf-8")
            chart_countries(tab, CHARTS / "em_bonds_countries_realyield.png")


if __name__ == "__main__":
    main()
