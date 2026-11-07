"""Derivative overlays (Phase 3): covered calls, protective puts, collar, EM FX forwards.

Option overlays are Black-Scholes on SPY total-return prices with ^VIX/^VIX3M as
implied volatility and a two-sided smile whose three free parameters are fitted
on 2010-2017 only against the CBOE BXM, BXMD and PPUT indices, then frozen and
run out of sample (2018 onward). The FX overlay sells 3-month forwards on a
basket of EMLC currencies priced by covered interest parity. Every assumption
is in research/candidates/assumptions_overlays.py.

    python -m research.candidates.overlays --all --write
    python -m research.candidates.overlays --overlay pput_5pct_3m
"""

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import ndtr, ndtri

from ..screen.prices import monthly_returns, read_wide_csv
from ..screen.stats import capture, max_drawdown, metrics_block
from . import assumptions_overlays as A

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research"
REPORTS = ROOT / "reports" / "candidates"
OVL_DIR = REPORTS / "overlays"
CHARTS = REPORTS / "charts"
MEMOS = ROOT / "research" / "candidates" / "memos"
CBOE_NAMES = ("BXM", "BXMD", "PPUT", "CLL", "PUT")
COLORS = {"plain": "#2a78d6", "overlaid": "#eb6834", "ref": "#1baf7a", "unit": "#eda100"}


# ---------------------------------------------------------------------------
# Black-Scholes
# ---------------------------------------------------------------------------
def bs_price(S, K, T, r, sigma, kind):
    """European option price, no dividends (the underlying is a total-return index)."""
    S, K, T, r, sigma = (np.asarray(x, dtype=float) for x in (S, K, T, r, sigma))
    T = np.maximum(T, 0.0)
    sq = sigma * np.sqrt(T)
    intrinsic = np.maximum(S - K, 0.0) if kind == "call" else np.maximum(K - S, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / sq
        d2 = d1 - sq
        disc = K * np.exp(-r * T)
        val = S * ndtr(d1) - disc * ndtr(d2) if kind == "call" else disc * ndtr(-d2) - S * ndtr(-d1)
    out = np.where(sq > 0, val, intrinsic)
    return float(out) if out.ndim == 0 else out


def bs_delta(S, K, T, r, sigma, kind):
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return float(ndtr(d1)) if kind == "call" else float(ndtr(d1) - 1.0)


@dataclass
class Params:
    """Smile parameters (assumptions_overlays.py: fitted on 2010-2017, then frozen)."""
    atm_level: float = 0.0
    skew_call: float = 0.0
    skew_put: float = 0.0


def atm_vol(vix, vix3m, tau):
    """ATM-equivalent vol for remaining life tau (years): total variance interpolated
    linearly between the 30-day ^VIX and 93-day ^VIX3M points."""
    t1, t2 = A.IV_SHORT_DAYS / 365, A.IV_LONG_DAYS / 365
    s1, s2 = vix / 100, (vix3m if np.isfinite(vix3m) else vix) / 100
    if tau <= t1:
        return s1
    if tau >= t2:
        return s2
    w = s1 ** 2 * t1 + (s2 ** 2 * t2 - s1 ** 2 * t1) * (tau - t1) / (t2 - t1)
    return math.sqrt(w / tau)


def implied_vol(S, K, tau, r, vix, vix3m, p):
    """sigma(K, tau) = ATM(tau) + atm_level - skew_side * ln(K/F) / sqrt(tau)."""
    tau = max(tau, 1 / 365)
    x = math.log(K / (S * math.exp(r * tau))) / math.sqrt(tau)
    side = p.skew_call if K >= S else p.skew_put
    return max(atm_vol(vix, vix3m, tau) + p.atm_level - side * x, A.MIN_VOL)


@dataclass(frozen=True)
class Leg:
    kind: str            # "call" | "put"
    sign: int            # -1 written, +1 bought
    strike: tuple        # ("atm",) | ("pct", 0.95) | ("delta", 0.30)
    schedule: str        # "monthly" | "quarterly" (expires at the next roll of its schedule)


def strike_for(leg, S, tau, r, vix, vix3m, p):
    how = leg.strike[0]
    if how == "atm":
        return S
    if how == "pct":
        return leg.strike[1] * S
    if how == "delta":                       # solve N(d1) = delta with the smile, fixed point
        d1 = float(ndtri(leg.strike[1] if leg.kind == "call" else 1 + leg.strike[1]))
        F, K = S * math.exp(r * tau), S
        for _ in range(12):
            sig = implied_vol(S, K, tau, r, vix, vix3m, p)
            K = F * math.exp(-d1 * sig * math.sqrt(tau) + 0.5 * sig ** 2 * tau)
        return K
    raise ValueError(leg.strike)


# ---------------------------------------------------------------------------
# Market data
# ---------------------------------------------------------------------------
def roll_dates(trading_days, start, end, months=None):
    """Third Friday of each month (previous trading day if a holiday), as Timestamps.
    Months after the last trading day keep the calendar third Friday (open expiries)."""
    out = []
    for per in pd.period_range(start, end, freq="M"):
        if months and per.month not in months:
            continue
        first = per.start_time
        fri = first + pd.Timedelta(days=(A.ROLL_WEEKDAY - first.weekday()) % 7 + 7 * (A.ROLL_WEEK - 1))
        if fri <= trading_days[-1]:
            i = trading_days.searchsorted(fri, side="right") - 1
            d = trading_days[i]
            if d.to_period("M") == per:
                out.append(d)
        else:
            out.append(fri)
    return pd.DatetimeIndex(out)


def load_market():
    """Everything the overlays read, from data/research/ only (no downloads)."""
    pf = DATA / "prices.csv"
    px = read_wide_csv(pf, spikes=True, columns=["SPY", "^GSPC", "IVW", "EFG", "EEM", "EMLC",
                                                 "EBND", "BIL", "XYLD"])
    vols = read_wide_csv(pf, spikes=False, columns=["^VIX", "^VIX3M"])
    yields = pd.read_csv(DATA / "yields.csv", index_col=0, parse_dates=True).sort_index()
    fx = read_wide_csv(DATA / "fx.csv", spikes=True)
    cboe = {}
    for n in CBOE_NAMES:
        f = DATA / "cboe" / f"{n}.csv"
        if f.exists():
            s = pd.read_csv(f, index_col=0, parse_dates=True)["value"].sort_index()
            cboe[n] = s[~s.index.duplicated(keep="last")]
    missing = [c for c in ("SPY", "^GSPC", "EMLC", "BIL") if c not in px or px[c].dropna().empty]
    missing += [c for c in ("^VIX", "^VIX3M") if c not in vols]
    missing += [n for n in ("BXM", "BXMD", "PPUT", "CLL") if n not in cboe]
    if missing:
        raise SystemExit(f"missing data, not downloaded: {missing}")
    spy = px["SPY"].dropna()
    days = spy.index
    us = yields[A.RATE_SERIES].dropna()
    # rate for a day = the previous month's TB3MS average (known on that day)
    us_m = us.copy()
    us_m.index = us_m.index.to_period("M") + 1
    r = np.log1p(us_m.reindex(days.to_period("M")).ffill().to_numpy() / 100)
    daily = pd.DataFrame({"S": spy, "spx": px["^GSPC"].reindex(days).ffill(),
                          "vix": vols["^VIX"].reindex(vols.index.union(days)).ffill().reindex(days),
                          "vix3m": vols["^VIX3M"].reindex(vols.index.union(days)).ffill().reindex(days),
                          "r": r}, index=days)
    mret = monthly_returns(px)
    return {"daily": daily, "px": px, "monthly": mret, "yields": yields, "fx": fx, "cboe": cboe,
            "rf": mret["BIL"]}


def month_end_positions(days):
    s = pd.Series(np.arange(len(days)), index=days)
    return s.groupby(days.to_period("M")).max().to_numpy()


def cboe_monthly(series, days):
    """CBOE index sampled on the SPY month-end trading days, monthly returns, ME labels."""
    lv = series.reindex(series.index.union(days)).ffill().reindex(days)
    lv = lv.iloc[month_end_positions(days)]
    lv.index = lv.index + pd.offsets.MonthEnd(0)
    return lv.pct_change(fill_method=None).iloc[1:]


# ---------------------------------------------------------------------------
# Option overlay engine (event-driven: roll dates and month ends)
# ---------------------------------------------------------------------------
def simulate(daily, legs, h, p, start=None, end=None, costs=True):
    """Overlaid sleeve value at each SPY month end (value 1 at the first roll).

    At each roll date of a leg: expiring options settle at intrinsic value; all cash
    is swept into the underlying; h x sleeve value / S units of the new option are
    traded at the Black-Scholes price; cost = half-spread x premium + $0.65 per
    XSP contract (contracts = h x sleeve / (10 x SPX), so the fee is 0.65 h / (10 SPX)
    of the sleeve). Returns DataFrame (ME labels): value, under, cost, rolls.
    """
    d = daily.loc[start:end]
    days = d.index
    S, spx = d["S"].to_numpy(), d["spx"].to_numpy()
    vix, v3, r = d["vix"].to_numpy(), d["vix3m"].to_numpy(), d["r"].to_numpy()
    ext_end = days[-1] + pd.DateOffset(months=4)
    sched = {"monthly": roll_dates(days, days[0], ext_end),
             "quarterly": roll_dates(days, days[0], ext_end, A.QUARTER_MONTHS)}
    pos_of = {dt: i for i, dt in enumerate(days)}
    roll_pos = {k: {pos_of[x] for x in v if x in pos_of} for k, v in sched.items()}
    me_pos = set(month_end_positions(days).tolist())
    first = min(min(roll_pos[l.schedule]) for l in legs)
    events = sorted(x for x in (set().union(*roll_pos.values()) | me_pos) if x >= first)
    N, cash, cum_cost, n_rolls, last = 1.0 / S[first], 0.0, 0.0, 0, first
    opened = []
    recs = []

    def value_open(i):
        tot = 0.0
        for o in opened:
            tau = (o["exp"] - days[i]).days / 365
            if tau <= 0:
                px = max(S[i] - o["K"], 0) if o["kind"] == "call" else max(o["K"] - S[i], 0)
            else:
                sig = implied_vol(S[i], o["K"], tau, r[i], vix[i], v3[i], p)
                px = bs_price(S[i], o["K"], tau, r[i], sig, o["kind"])
            tot += o["sign"] * o["q"] * px
        return tot

    for i in events:
        cash *= math.exp(r[last] * (days[i] - days[last]).days / 365)
        keep = []
        for o in opened:
            if days[i] >= o["exp"]:
                pay = max(S[i] - o["K"], 0) if o["kind"] == "call" else max(o["K"] - S[i], 0)
                cash += o["sign"] * o["q"] * pay
            else:
                keep.append(o)
        opened = keep
        rolling = [l for l in legs if i in roll_pos[l.schedule]]
        if rolling:
            ov = value_open(i)
            V = N * S[i] + cash + ov
            N, cash = (V - ov) / S[i], 0.0
            for leg in rolling:
                nxt = sched[leg.schedule]
                exp = nxt[nxt.searchsorted(days[i], side="right")]
                tau = (exp - days[i]).days / 365
                K = strike_for(leg, S[i], tau, r[i], vix[i], v3[i], p)
                sig = implied_vol(S[i], K, tau, r[i], vix[i], v3[i], p)
                prem = bs_price(S[i], K, tau, r[i], sig, leg.kind)
                q = h * V / S[i]
                cash -= leg.sign * q * prem
                if costs:
                    c = A.OPTION_HALF_SPREAD * q * prem + \
                        A.OPTION_FEE_PER_CONTRACT * h * V / (A.XSP_MULTIPLIER * A.XSP_INDEX_FRACTION * spx[i])
                    cash -= c
                    cum_cost += c
                opened.append({"kind": leg.kind, "sign": leg.sign, "K": K, "exp": exp, "q": q})
                n_rolls += 1
        if i in me_pos:
            recs.append((days[i], N * S[i] + cash + value_open(i), S[i], cum_cost, n_rolls))
        last = i
    out = pd.DataFrame(recs, columns=["date", "value", "under", "cum_cost", "rolls"]).set_index("date")
    out.index = out.index + pd.offsets.MonthEnd(0)
    return out


def to_returns(sim):
    """Monthly underlying, overlaid and cost (fraction of the prior month's value)."""
    df = pd.DataFrame({"underlying_return": sim["under"].pct_change(),
                       "overlaid_return": sim["value"].pct_change(),
                       "cost": sim["cum_cost"].diff() / sim["value"].shift(1)}).iloc[1:]
    df["overlay_return"] = df["overlaid_return"] - df["underlying_return"]
    return df


# ---------------------------------------------------------------------------
# Calibration (2010-2017 only)
# ---------------------------------------------------------------------------
CALIB_MODELS = {
    "BXM": [Leg("call", -1, ("atm",), "monthly")],
    "BXMD": [Leg("call", -1, ("delta", 0.30), "monthly")],
    "PPUT": [Leg("put", +1, ("pct", 0.95), "monthly")],
}


def calibration_slice(r):
    """Months used for fitting: CALIBRATION_START..CALIBRATION_END, nothing later."""
    return r.loc[A.CALIBRATION_START:A.CALIBRATION_END]


def fit_errors(daily, legs, p, ref, start=A.ENGINE_START, end=None):
    """Monthly (model gross of costs, h = 1) minus CBOE index returns."""
    m = to_returns(simulate(daily, legs, 1.0, p, start, end, costs=False))["overlaid_return"]
    return (m - ref).dropna(), m


def calibrate(daily, cboe):
    """Fit atm_level on BXM, skew_call on BXMD, skew_put on PPUT, each by least squares
    on monthly returns 2010-01..2017-12. Inputs are truncated at CALIBRATION_END first."""
    daily = daily.loc[:A.CALIBRATION_END]
    days = daily.index
    refs = {n: calibration_slice(cboe_monthly(cboe[n].loc[:A.CALIBRATION_END], days)) for n in CALIB_MODELS}
    p = Params()
    for name, attr in (("BXM", "atm_level"), ("BXMD", "skew_call"), ("PPUT", "skew_put")):
        def sse(x, name=name, attr=attr):
            q = Params(**{**p.__dict__, attr: x})
            e, _ = fit_errors(daily, CALIB_MODELS[name], q, refs[name])
            return float((calibration_slice(e) ** 2).sum())
        res = minimize_scalar(sse, bounds=A.PARAM_BOUNDS[attr], method="bounded",
                              options={"xatol": 1e-4})
        setattr(p, attr, float(res.x))
    return p


def tracking(model_r, ref_r, under_r):
    """Fit statistics of a model return series against a CBOE index."""
    df = pd.concat([model_r, ref_r, under_r], axis=1, keys=["m", "ref", "u"], sort=True).dropna()
    if len(df) < 12:
        return None
    err = df["m"] - df["ref"]
    ov_m, ov_ref = df["m"] - df["u"], df["ref"] - df["u"]
    r2 = 1 - (err ** 2).sum() / ((df["ref"] - df["ref"].mean()) ** 2).sum()
    r2_ov = 1 - ((ov_m - ov_ref) ** 2).sum() / ((ov_ref - ov_ref.mean()) ** 2).sum()
    return {"start": str(df.index[0].date()), "end": str(df.index[-1].date()), "months": len(df),
            "r2_total_return": float(r2), "r2_overlay_component": float(r2_ov),
            "corr_overlay_component": float(ov_m.corr(ov_ref)),
            "tracking_error": float(err.std() * np.sqrt(12)), "mean_diff_annual": float(err.mean() * 12)}


# ---------------------------------------------------------------------------
# Overlay definitions
# ---------------------------------------------------------------------------
OPTION_OVERLAYS = {
    "cc_spx_30d_1m": {"name": "Covered call, 30-delta, 1-month (BXMD-style)", "ref": "BXMD",
                      "legs": [Leg("call", -1, ("delta", 0.30), "monthly")],
                      "strategy": "sell a 1-month 30-delta S&P 500 call each monthly expiry"},
    "cc_spx_atm_1m": {"name": "Covered call, at-the-money, 1-month (BXM-style)", "ref": "BXM",
                      "cross": "XYLD", "legs": [Leg("call", -1, ("atm",), "monthly")],
                      "strategy": "sell a 1-month at-the-money S&P 500 call each monthly expiry"},
    "pput_5pct_3m": {"name": "Protective put, 5% OTM, 3-month, quarterly", "ref": "PPUT",
                     "ref_note": "PPUT rolls a 1-month put monthly; the 3-month quarterly overlay is a loose comparison",
                     "legs": [Leg("put", +1, ("pct", 0.95), "quarterly")],
                     "strategy": "buy a 3-month 95% S&P 500 put each quarterly expiry (Mar/Jun/Sep/Dec)"},
    "collar_cll_95_110": {"name": "Collar 95/110 (CBOE CLL definition)", "ref": "CLL",
                          "legs": [Leg("put", +1, ("pct", 0.95), "quarterly"),
                                   Leg("call", -1, ("pct", 1.10), "monthly")],
                          "strategy": "buy a 3-month 95% put quarterly and sell a 1-month 110% call monthly"},
}
FX_OVERLAYS = {"fxfwd_emlocal_50pct_3m": 0.5, "fxfwd_emlocal_100pct_3m": 1.0}
ALL_OVERLAYS = list(OPTION_OVERLAYS) + list(FX_OVERLAYS)


def contract_sizing(spx, sleeve=A.EQUITY_SLEEVE_USD, contracts=A.CONTRACTS):
    """XSP notional, whole contracts and the hedge ratio they give on the sleeve."""
    notional = spx * A.XSP_MULTIPLIER * A.XSP_INDEX_FRACTION
    return {"notional_per_contract": notional, "contracts": contracts,
            "max_fully_covered_contracts": int(sleeve // notional),
            "hedge_ratio": contracts * notional / sleeve, "sleeve_usd": sleeve,
            "sleeve_needed_for_100pct": notional * max(contracts, 1)}


# ---------------------------------------------------------------------------
# FX forwards
# ---------------------------------------------------------------------------
def cip_forward_factor(us_rate, local_rate, months=A.FX_TENOR_MONTHS):
    """F/S by covered interest parity, rates as decimals per year, S in USD per local unit."""
    return ((1 + us_rate) / (1 + local_rate)) ** (months / 12)


def hedge_return(us_rate, local_rate, spot0, spot1, months=A.FX_TENOR_MONTHS):
    """Return per unit hedged of selling local currency forward: F/S0 - S1/S0."""
    return cip_forward_factor(us_rate, local_rate, months) - spot1 / spot0


def fx_weights():
    df = pd.read_csv(ROOT / A.COUNTRY_WEIGHTS_FILE)
    w = df.set_index("currency")["weight_gbiem_pct"].reindex(list(A.FX_CURRENCIES))
    return (w.fillna(w.mean()) / w.fillna(w.mean()).sum()).rename("weight")


def fx_inputs(mkt):
    spot = mkt["fx"][list(A.FX_CURRENCIES)].resample("ME").last()
    y = mkt["yields"]
    cols = {"USD": A.RATE_SERIES, **{c: f"{iso}_3M" for c, iso in A.FX_CURRENCIES.items()}}
    rates = pd.DataFrame({c: y[s] for c, s in cols.items() if s in y}) / 100
    rates.index = rates.index + pd.offsets.MonthEnd(0)
    rates = rates.resample("ME").last().ffill(limit=A.RATE_FFILL_MONTHS)
    return spot, rates


def fx_hedge(unhedged, spot, rates, weights, h, cost_bps=A.FX_ROLL_COST_BPS):
    """Monthly hedged return of a local-currency bond fund with h of its value sold
    forward (3-month CIP forwards on the basket, rolled at quarter-end months, marked to
    market monthly). Returns DataFrame: underlying_return, overlaid_return, overlay_return,
    cost, carry (annualised CIP carry of the basket at the last roll, negative = cost)."""
    r = unhedged.dropna()
    months = r.index
    spot = spot.reindex(spot.index.union(months)).ffill()
    rates = rates.reindex(rates.index.union(months)).ffill(limit=A.RATE_FFILL_MONTHS)
    p0 = months[0] - pd.offsets.MonthEnd(1)
    V, recs, st = 1.0, [], None

    def roll(t, V):
        sp, rt = spot.loc[t], rates.loc[t]
        ok = [c for c in weights.index if np.isfinite(sp.get(c, np.nan)) and np.isfinite(rt.get(c, np.nan))
              and np.isfinite(rt["USD"])]
        w = weights[ok] / weights[ok].sum()
        rem = A.FX_TENOR_MONTHS - (t.month % 3 if t.month % 3 else 0)
        rem = rem if rem > 0 else A.FX_TENOR_MONTHS
        f = pd.Series({c: cip_forward_factor(rt["USD"], rt[c], rem) for c in ok})
        carry = float((w * (f ** (12 / rem) - 1)).sum())
        return {"t0": t, "w": w, "f": f, "s0": sp[ok], "notional": h * V, "rem0": rem,
                "exp": t + pd.offsets.MonthEnd(rem), "prev": 0.0, "carry": carry}

    def mtm(st, t):
        sp, rt = spot.loc[t], rates.loc[t]
        rem = (st["exp"].to_period("M") - t.to_period("M")).n
        g = pd.Series({c: cip_forward_factor(rt["USD"], rt[c], rem) if rem > 0 else 1.0 for c in st["w"].index})
        return float((st["w"] * (st["f"] - sp[st["w"].index] / st["s0"] * g)).sum())

    st = roll(p0, V)
    pending_cost = cost_bps / 1e4 * h * V      # first roll's cost, charged in the first month
    for t in months:
        Vp = V
        val = mtm(st, t)
        V = V * (1 + r.loc[t]) + st["notional"] * (val - st["prev"]) - pending_cost
        st["prev"] = val
        cost = pending_cost
        pending_cost = 0.0
        carry = st["carry"]
        if t >= st["exp"]:
            st = roll(t, V)
            c = cost_bps / 1e4 * h * V
            V -= c
            cost += c
        recs.append((t, r.loc[t], V / Vp - 1, cost / Vp if Vp else 0.0, carry))
    df = pd.DataFrame(recs, columns=["date", "underlying_return", "overlaid_return", "cost",
                                     "carry"]).set_index("date")
    df["overlay_return"] = df["overlaid_return"] - df["underlying_return"]
    return df


def basket_spot_return(spot, weights):
    sr = spot.pct_change(fill_method=None)
    avail = sr.notna()
    w = avail.mul(weights, axis=1)
    return (sr.fillna(0) * w).sum(axis=1) / w.sum(axis=1)


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------
def windows(r):
    return {"in_sample": r.loc[A.IN_SAMPLE_START:A.IN_SAMPLE_END],
            "out_of_sample": r.loc[A.OOS_START:], "full": r.loc[A.IN_SAMPLE_START:]}


def compact(m):
    keys = ("start", "end", "months", "cagr", "vol", "sharpe", "sortino", "max_drawdown",
            "worst_month", "up_capture", "down_capture", "info_ratio", "tracking_error")
    return {k: m.get(k) for k in keys}


def window_stats(r):
    if len(r.dropna()) == 0:
        return {"return": None, "max_drawdown": None}
    return {"return": float((1 + r).prod() - 1), "max_drawdown": float(min(max_drawdown(r), 0.0))}


def stress_block(under, over, yields):
    out = {}
    for k, (a, b) in A.STRESS.items():
        u = under.loc[pd.Timestamp(a) + pd.Timedelta(days=1):b]
        o = over.loc[pd.Timestamp(a) + pd.Timedelta(days=1):b]
        if len(u.dropna()) < len(pd.date_range(a, b, freq="ME")) - 1:
            out[k] = {"start": a, "end": b, "note": "not covered by the model history"}
            continue
        w, wo = window_stats(o), window_stats(u)
        out[k] = {"start": a, "end": b, "with": w, "without": wo,
                  "drawdown_reduction": w["max_drawdown"] - wo["max_drawdown"],
                  "return_difference": w["return"] - wo["return"]}
    usd = yields[A.STRONG_USD_SERIES].dropna()
    usd.index = usd.index + pd.offsets.MonthEnd(0)
    up = usd.pct_change(fill_method=None)
    months = up[up >= A.STRONG_USD_RISE].index.intersection(under.dropna().index)
    out["strong_usd"] = {"definition": "months when FRED DTWEXBGS (monthly) rose >= 2%",
                         "months": len(months),
                         "avg_return_with": float(over.loc[months].mean()) if len(months) else None,
                         "avg_return_without": float(under.loc[months].mean()) if len(months) else None}
    for k, (a, b) in A.STRONG_USD_EPISODES.items():
        u = under.loc[pd.Timestamp(a) + pd.Timedelta(days=1):b]
        o = over.loc[pd.Timestamp(a) + pd.Timedelta(days=1):b]
        out["strong_usd"][k] = {"start": a, "end": b, "with": window_stats(o), "without": window_stats(u)}
    return out


def assess(df, rf, yields):
    """Difference-series metrics plus with/without sleeve metrics and the verdict inputs."""
    rf = rf.reindex(df.index)
    metrics, with_, without = {}, {}, {}
    for k, part in windows(df).items():
        metrics[k] = {"usd": metrics_block(part["overlay_return"]), "local": None}
        with_[k] = compact(metrics_block(part["overlaid_return"], part["underlying_return"], rf))
        wo = compact(metrics_block(part["underlying_return"], None, rf))
        wo["up_capture"], wo["down_capture"] = 1.0, 1.0
        without[k] = wo
    oos_w, oos_wo = with_["out_of_sample"], without["out_of_sample"]
    d_sharpe = oos_w["sharpe"] - oos_wo["sharpe"]
    d_dd = oos_w["max_drawdown"] - oos_wo["max_drawdown"]
    costs = df["cost"].loc[A.IN_SAMPLE_START:]
    annual_cost = {"full": float(costs.mean() * 12),
                   "in_sample": float(costs.loc[:A.IN_SAMPLE_END].mean() * 12),
                   "out_of_sample": float(costs.loc[A.OOS_START:].mean() * 12)}
    verdict = {"rule": "method.md s8 item 5, standalone sleeve: OOS Sharpe higher, or OOS max drawdown "
                       "at least 2 points smaller, net of costs; the portfolio-level test is Phase 5's",
               "oos_sharpe_change": d_sharpe, "oos_max_drawdown_change": d_dd,
               "oos_vol_change": oos_w["vol"] - oos_wo["vol"],
               "passes_standalone": bool(d_sharpe > 0 or d_dd >= A.VERDICT_DD_POINTS)}
    return {"metrics": metrics, "with": with_, "without": without,
            "stress": stress_block(df["underlying_return"], df["overlaid_return"], yields),
            "annual_cost": annual_cost, "verdict": verdict}


def vrp_table(daily):
    """VIX minus subsequent 21-trading-day realised SPY vol (annualised, vol points)."""
    lr = np.log(daily["S"]).diff()
    rv = lr.rolling(21).std().shift(-21) * np.sqrt(252) * 100
    df = pd.DataFrame({"vix": daily["vix"], "realised_fwd": rv}).dropna()
    df["vrp"] = df["vix"] - df["realised_fwd"]
    m = df.resample("ME").mean()

    def summ(x):
        return {"start": str(x.index[0].date()), "end": str(x.index[-1].date()), "days": int(len(x)),
                "avg_vix": float(x["vix"].mean()), "avg_realised": float(x["realised_fwd"].mean()),
                "avg_vrp_points": float(x["vrp"].mean()), "share_days_positive": float((x["vrp"] > 0).mean())}
    return m, {"in_sample": summ(df.loc[A.IN_SAMPLE_START:A.IN_SAMPLE_END]),
               "out_of_sample": summ(df.loc[A.OOS_START:]),
               "definition": "^VIX minus the realised volatility of SPY daily log returns over the next "
                             "21 trading days, annualised, in volatility points"}


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------
@dataclass
class Context:
    mkt: dict
    params: Params
    sizing: dict
    vrp_monthly: pd.DataFrame
    vrp: dict
    basis: dict
    calib: dict = field(default_factory=dict)


def build_context(mkt=None):
    mkt = mkt or load_market()
    daily = mkt["daily"]
    params = calibrate(daily, mkt["cboe"])
    sizing = contract_sizing(float(daily["spx"].dropna().iloc[-1]))
    sizing["spx_level"] = float(daily["spx"].dropna().iloc[-1])
    sizing["spx_date"] = str(daily["spx"].dropna().index[-1].date())
    vm, vrp = vrp_table(daily)
    mr = mkt["monthly"]
    eem50 = 0.5 * mr["EFG"] + 0.5 * mr["EEM"]
    oos = slice(A.OOS_START, None)
    basis = {"corr_EFG_EEM_5050_SPY_oos": float(eem50.loc[oos].corr(mr["SPY"].loc[oos])),
             "corr_EFG_EEM_5050_SPY_in_sample": float(eem50.loc[A.IN_SAMPLE_START:A.IN_SAMPLE_END]
                                                      .corr(mr["SPY"].loc[A.IN_SAMPLE_START:A.IN_SAMPLE_END])),
             "corr_IVW_SPY_oos": float(mr["IVW"].loc[oos].corr(mr["SPY"].loc[oos]))}
    proxy = sum(mr[t] * w for t, w in A.SLEEVE_PROXY.items())
    basis["corr_sleeve_proxy_SPY_oos"] = float(proxy.loc[oos].corr(mr["SPY"].loc[oos]))
    ctx = Context(mkt, params, sizing, vm, vrp, basis)
    days = daily.index
    for name, legs in CALIB_MODELS.items():
        m = to_returns(simulate(daily, legs, 1.0, params, A.ENGINE_START, None, costs=False))
        ref = cboe_monthly(mkt["cboe"][name], days)
        ctx.calib[name] = {"in_sample": tracking(m["overlaid_return"].loc[A.IN_SAMPLE_START:A.IN_SAMPLE_END],
                                                 ref, m["underlying_return"]),
                           "out_of_sample": tracking(m["overlaid_return"].loc[A.OOS_START:], ref,
                                                     m["underlying_return"])}
    return ctx


def run_option(oid, ctx):
    spec = OPTION_OVERLAYS[oid]
    mkt, daily, p = ctx.mkt, ctx.mkt["daily"], ctx.params
    h = ctx.sizing["hedge_ratio"]
    net = to_returns(simulate(daily, spec["legs"], h, p, A.ENGINE_START))
    unit = to_returns(simulate(daily, spec["legs"], 1.0, p, A.ENGINE_START))
    gross1 = to_returns(simulate(daily, spec["legs"], 1.0, p, A.ENGINE_START, costs=False))
    net["hedge_ratio"] = h
    net["overlay_return_h100"] = unit["overlay_return"]
    ref = cboe_monthly(mkt["cboe"][spec["ref"]], daily.index)
    track = {"reference": spec["ref"], "note": spec.get("ref_note", ""),
             "in_sample": tracking(gross1["overlaid_return"].loc[A.IN_SAMPLE_START:A.IN_SAMPLE_END], ref,
                                   gross1["underlying_return"]),
             "out_of_sample": tracking(gross1["overlaid_return"].loc[A.OOS_START:], ref,
                                       gross1["underlying_return"])}
    if spec.get("cross"):
        x = mkt["monthly"][spec["cross"]]
        fee = 0.006 / 12   # XYLD expense ratio 0.60% (yfinance 2026-11-07, overlays_notes.md s3)
        track["cross_check_" + spec["cross"]] = {
            "in_sample_partial": tracking(gross1["overlaid_return"].loc[:A.IN_SAMPLE_END] - fee, x,
                                          gross1["underlying_return"]),
            "out_of_sample": tracking(gross1["overlaid_return"].loc[A.OOS_START:] - fee, x,
                                      gross1["underlying_return"]),
            "note": "model gross of option costs minus the 0.60% fund fee; XYLD starts 2013-06"}
    res = assess(net, mkt["rf"], mkt["yields"])
    res_unit = assess(unit, mkt["rf"], mkt["yields"])
    mr = mkt["monthly"]
    proxy = sum(mr[t] * w for t, w in A.SLEEVE_PROXY.items()).reindex(net.index)
    pdf = pd.DataFrame({"underlying_return": proxy, "overlaid_return": proxy + net["overlay_return"],
                        "cost": net["cost"]}).dropna()
    pdf["overlay_return"] = pdf["overlaid_return"] - pdf["underlying_return"]
    res_proxy = assess(pdf, mkt["rf"], mkt["yields"])
    return {"id": oid, "kind": "option", "spec": spec, "series": net, "unit": unit, "gross1": gross1,
            "ref_series": ref, "tracking": track, "res": res, "res_unit": res_unit, "res_proxy": res_proxy}


def run_fx(oid, ctx):
    mkt = ctx.mkt
    h = FX_OVERLAYS[oid]
    spot, rates = fx_inputs(mkt)
    w = fx_weights()
    under = mkt["monthly"][A.UNHEDGED_FUND]
    net = fx_hedge(under, spot, rates, w, h)
    full = fx_hedge(under, spot, rates, w, 1.0)
    net["hedge_ratio"] = h
    net["overlay_return_h100"] = full["overlay_return"]
    res = assess(net, mkt["rf"], mkt["yields"])
    eb = fx_hedge(mkt["monthly"][A.FX_CROSSCHECK_FUND], spot, rates, w, h)
    res_eb = assess(eb, mkt["rf"], mkt["yields"])
    bsr = basket_spot_return(spot, w)
    df = pd.concat([under, bsr], axis=1, keys=["fund", "fx"], sort=True).dropna()
    reg = {}
    for k, part in windows(df).items():
        b = np.polyfit(part["fx"], part["fund"], 1)
        reg[k] = {"beta_to_basket_fx": float(b[0]), "r2": float(part.corr().iloc[0, 1] ** 2)}
    carry = net["carry"]
    hc = {k: {"carry_given_up_per_year_at_100pct": float(-carry.loc[sl].mean()),
              "carry_given_up_at_ratio": float(-carry.loc[sl].mean() * h),
              "roll_cost_per_year": float(net["cost"].loc[sl].mean() * 12),
              "spot_gain_from_hedge_per_year": float(net["overlay_return"].loc[sl].mean() * 12
                                                     - carry.loc[sl].mean() * h + net["cost"].loc[sl].mean() * 12)}
          for k, sl in (("in_sample", slice(A.IN_SAMPLE_START, A.IN_SAMPLE_END)),
                        ("out_of_sample", slice(A.OOS_START, None)), ("full", slice(A.IN_SAMPLE_START, None)))}
    return {"id": oid, "kind": "fx", "h": h, "series": net, "res": res, "res_ebnd": res_eb,
            "weights": w, "regression": reg, "hedge_cost": hc, "rates_end": {
                c: str(rates[c].dropna().index[-1].date()) for c in rates.columns},
            "rates_start": {c: str(rates[c].dropna().index[0].date()) for c in rates.columns}}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
COLS = ["underlying_return", "overlay_return", "overlaid_return", "cost", "hedge_ratio", "overlay_return_h100"]


def write_monthly(run):
    OVL_DIR.mkdir(parents=True, exist_ok=True)
    df = run["series"].loc[A.OUTPUT_START:, COLS].copy()
    df.index = df.index.strftime("%Y-%m-%d")
    df.index.name = "date"
    path = OVL_DIR / f"{run['id']}_monthly.csv"
    df.to_csv(path, float_format="%.8f")
    return path


def feasibility(run, ctx):
    s = ctx.sizing
    if run["kind"] == "fx":
        fx = ctx.mkt["fx"]
        last = {c: float(fx[c].dropna().iloc[-1]) for c in ("MXN", "ZAR", "BRL")}
        return {"contract": "3-month deliverable/non-deliverable FX forwards on 9 EM currencies (bank OTC)",
                "notional_per_contract": None, "contracts": None, "hedge_ratio": run["h"],
                "position_usd_example": A.CAPITAL * 0.35 / 4,
                "hedged_notional_usd_example": A.CAPITAL * 0.35 / 4 * run["h"],
                "margin": "Bank forwards and NDFs need a dealer credit line or ISDA; not normally open to a "
                          "retail brokerage account (not verified for a specific broker). The exchange route is "
                          "CME FX futures on MXN, ZAR and BRL only, whose standard sizes (500,000 MXN = about "
                          f"${500_000 * last['MXN']:,.0f}; 500,000 ZAR = about ${500_000 * last['ZAR']:,.0f}; "
                          f"100,000 BRL = about ${100_000 * last['BRL']:,.0f} at fx.csv's last rates; sizes from "
                          "memory, NOT verified this session) exceed a ~$8,750 EMLC position.",
                "implementable_at_100k": False}
    legs = run["spec"]["legs"]
    daily = ctx.mkt["daily"]
    last = daily.dropna(subset=["vix"]).iloc[-1]
    prem = []
    for leg in legs:
        tau = 30 / 365 if leg.schedule == "monthly" else 91 / 365
        K = strike_for(leg, last["spx"], tau, last["r"], last["vix"], last["vix3m"], ctx.params)
        sig = implied_vol(last["spx"], K, tau, last["r"], last["vix"], last["vix3m"], ctx.params)
        px = bs_price(last["spx"], K, tau, last["r"], sig, leg.kind) * A.XSP_MULTIPLIER * A.XSP_INDEX_FRACTION
        prem.append({"leg": f"{'sell' if leg.sign < 0 else 'buy'} {leg.kind} {leg.strike}",
                     "strike_xsp": K / 10, "premium_usd_per_contract": px, "implied_vol": sig})
    short_calls = [l for l in legs if l.kind == "call" and l.sign < 0]
    m15, m10 = A.UNCOVERED_INDEX_MARGIN
    notional = s["notional_per_contract"]
    margin = "Long puts need no margin (premium paid in full)."
    if short_calls:
        cp = next(x for x in prem if "call" in x["leg"])
        otm = max(cp["strike_xsp"] * 100 - notional, 0)
        req = cp["premium_usd_per_contract"] + max(m15 * notional - otm, m10 * notional)
        margin = (f"The short XSP call is not covered by the sleeve's stocks, so a broker margins it as an "
                  f"uncovered broad-based index call: about ${req:,.0f} per contract at today's level "
                  f"(premium + 15% of notional less the OTM amount, minimum premium + 10%; Cboe margin rule "
                  f"recalled, not re-verified). Needs the broker's uncovered-option approval level.")
    return {"contract": "XSP (Mini-SPX) option, European, cash-settled, $100 x SPX/10",
            "source": "https://www.cboe.com/tradable_products/sp_500/mini_spx_options/ (read 2026-11-07)",
            "spx_level": s["spx_level"], "spx_date": s["spx_date"],
            "notional_per_contract": notional, "contracts": s["contracts"],
            "max_fully_covered_contracts": s["max_fully_covered_contracts"],
            "sleeve_usd": s["sleeve_usd"], "hedge_ratio": s["hedge_ratio"],
            "hedge_ratio_on_us_half_only": s["hedge_ratio"] * 2,
            "legs_today": prem, "margin": margin,
            "note": (f"One XSP contract (${notional:,.0f}) is {s['hedge_ratio']:.0%} of a ${s['sleeve_usd']:,} "
                     f"equity sleeve; zero contracts is 0%. The series is modelled at the 1-contract ratio "
                     f"(column hedge_ratio); overlay_return_h100 is the same overlay at exactly 100%. "
                     + ("Writing calls on 139% of the sleeve leaves part of the call uncovered, which breaks the "
                        "overlay-only rule; it becomes a covered overlay only once the equity sleeve is at "
                        f"least ${notional:,.0f}." if short_calls else
                        "Holding puts on more than 100% of the sleeve is a small net short bet below the strike."))}


def like_for_like(run, ctx):
    """Model-vs-index fit on the index's own definition: the calibration model where one
    exists (PPUT is a monthly 1-month put; the overlay is quarterly 3-month), else this overlay."""
    return ctx.calib.get(run["spec"]["ref"], run["tracking"])


def explain(run, ctx):
    r = run["res"]
    v = r["verdict"]
    w, wo = r["with"]["out_of_sample"], r["without"]["out_of_sample"]
    if run["kind"] == "fx":
        hc = run["hedge_cost"]["out_of_sample"]
        return [f"Selling {run['h']:.0%} of EMLC's currency exposure forward each quarter changed its "
                f"2018-2026 Sharpe from {wo['sharpe']:.2f} to {w['sharpe']:.2f} and its worst drawdown "
                f"from {wo['max_drawdown']:.0%} to {w['max_drawdown']:.0%}.",
                f"The hedge gives up the interest-rate gap between EM and US cash, about "
                f"{hc['carry_given_up_at_ratio']:.1%} a year out of sample, which is most of what local-currency "
                f"bonds pay for their risk.",
                "It cannot be bought in a $100,000 brokerage account as modelled (bank forwards on nine currencies), "
                "so it is a test of whether the currency risk is worth taking, not a trade."]
    return [f"Run on the S&P 500 at one XSP contract ({ctx.sizing['hedge_ratio']:.0%} of a $55,000 sleeve), "
            f"the overlay changed the 2018-2026 Sharpe from {wo['sharpe']:.2f} to {w['sharpe']:.2f}, volatility "
            f"from {wo['vol']:.1%} to {w['vol']:.1%} and the worst drawdown from {wo['max_drawdown']:.0%} to "
            f"{w['max_drawdown']:.0%}, after costs.",
            f"Option prices are modelled from the VIX with a smile fitted to CBOE's {run['spec']['ref']} index on "
            f"2010-2017 only; out of sample the like-for-like model tracks that index with an error of "
            f"{like_for_like(run, ctx)['out_of_sample']['tracking_error']:.1%} a year.",
            ("On the standalone test it passes" if v["passes_standalone"] else "On the standalone test it fails")
            + " method.md rule 8.5; the S&P 500 options hedge the international half of the sleeve only "
              f"loosely (correlation {ctx.basis['corr_EFG_EEM_5050_SPY_oos']:.2f})."]


def build_json(run, ctx, csv_path, chart):
    r = run["res"]
    oid = run["id"]
    is_fx = run["kind"] == "fx"
    if is_fx:
        params = {"hedge_ratio": run["h"], "tenor_months": A.FX_TENOR_MONTHS, "roll": "quarter-end months",
                  "currencies": run["weights"].round(4).to_dict(), "excluded": A.FX_EXCLUDED,
                  "rate_series": {c: (A.RATE_SERIES if c == "USD" else f"{A.FX_CURRENCIES[c]}_3M")
                                  for c in ["USD", *A.FX_CURRENCIES]},
                  "rate_coverage": {"start": run["rates_start"], "end": run["rates_end"]}}
        calibration = {"fitted": "none (no free parameter; forwards from covered interest parity)",
                       "fx_explains_fund": run["regression"]}
        strategy = f"sell 3-month CIP forwards on {run['h']:.0%} of the EMLC currency basket, rolled quarterly"
        underlying, name = A.UNHEDGED_FUND, f"EM local-currency FX hedge, {run['h']:.0%}, 3-month forwards"
    else:
        spec = run["spec"]
        params = {"legs": [{"kind": l.kind, "side": "sell" if l.sign < 0 else "buy", "strike": list(l.strike),
                            "roll": l.schedule} for l in spec["legs"]],
                  "hedge_ratio": ctx.sizing["hedge_ratio"], "underlying_series": "SPY adjusted close",
                  "implied_vol": "^VIX (30d), ^VIX3M (93d), total-variance interpolation",
                  "rate": "TB3MS (US_3M), previous month"}
        calibration = {"fitted_on": f"{A.CALIBRATION_START}..{A.CALIBRATION_END}, frozen",
                       "params": ctx.params.__dict__, "fit_by_index": ctx.calib,
                       "this_overlay_vs_reference": run["tracking"]}
        strategy, underlying, name = spec["strategy"], "SPY (S&P 500 total return, index-level equity sleeve)", spec["name"]
    extra = {"fx_hedge_cost": run["hedge_cost"], "ebnd_crosscheck": {
        "with_oos": run["res_ebnd"]["with"]["out_of_sample"],
        "without_oos": run["res_ebnd"]["without"]["out_of_sample"]}} if is_fx else {
        "at_100pct": {"with": run["res_unit"]["with"], "verdict": run["res_unit"]["verdict"],
                      "annual_cost": run["res_unit"]["annual_cost"]},
        "sleeve_proxy_50_IVW_50_EFG_EEM": {"with_oos": run["res_proxy"]["with"]["out_of_sample"],
                                           "without_oos": run["res_proxy"]["without"]["out_of_sample"],
                                           "verdict": run["res_proxy"]["verdict"]},
        "basis": ctx.basis}
    s = run["series"].loc[A.OUTPUT_START:]
    stress = r["stress"]
    out = {
        "schema_version": 1, "id": oid, "ticker": None, "usd_ticker": None, "name": name,
        "position_type": "overlay", "instrument": "overlay",
        "country": "MULTI" if is_fx else "US", "currency": "MULTI" if is_fx else "USD",
        "sector": None, "non_us": bool(is_fx), "benchmark": A.UNHEDGED_FUND if is_fx else "SPY",
        "data": {"price_start": str(s.index[0].date()), "price_end": str(s.index[-1].date()),
                 "months_total": int(len(s)),
                 "months_in_sample": int(len(s.loc[:A.IN_SAMPLE_END])),
                 "months_out_of_sample": int(len(s.loc[A.OOS_START:])),
                 "sources": (["data/research/prices.csv", "data/research/fx.csv", "data/research/yields.csv",
                              A.COUNTRY_WEIGHTS_FILE] if is_fx else
                             ["data/research/prices.csv", "data/research/yields.csv",
                              f"data/research/cboe/{run['spec']['ref']}.csv"]),
                 "fund_fee": None,
                 "notes": ("EMLC starts 2010-07, so the series starts 2010-08." if is_fx else
                           "SPY/^GSPC end 2026-10-23 in prices.csv, so October 2026 is a partial month. "
                           "PPUT values before its 2015 launch are back-calculated by Cboe.")},
        "metrics": r["metrics"],
        "stress": stress,
        "overlay": {
            "underlying": underlying, "strategy": strategy, "parameters": params,
            "assumptions": "research/candidates/assumptions_overlays.py",
            "calibration": calibration,
            "vrp_in_sample": None if is_fx else ctx.vrp["in_sample"],
            "vrp_oos": None if is_fx else ctx.vrp["out_of_sample"],
            "with": r["with"], "without": r["without"],
            "drawdown_reduction": {k: v.get("drawdown_reduction") for k, v in stress.items() if k != "strong_usd"},
            "annual_cost": r["annual_cost"],
            "feasibility": feasibility(run, ctx),
            "verdict_rule": r["verdict"],
            "monthly_series": str(csv_path.relative_to(ROOT)).replace("\\", "/"),
            **extra},
        "explain": explain(run, ctx),
        "memo": f"research/candidates/memos/{oid}.md",
        "charts": {"growth": chart},
        "reproduce": f"python -m research.candidates.overlays --overlay {oid} --write",
    }
    return clean(out)


def growth_chart(run, ctx):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    CHARTS.mkdir(parents=True, exist_ok=True)
    s = run["series"].loc[A.OUTPUT_START:]
    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=120)
    base = s.index[0] - pd.offsets.MonthEnd(1)

    def lvl(r):
        return pd.concat([pd.Series([1.0], index=[base]), (1 + r.fillna(0)).cumprod()])
    plain = "EMLC unhedged" if run["kind"] == "fx" else "SPY (plain sleeve)"
    ax.plot(lvl(s["underlying_return"]), color=COLORS["plain"], lw=2, label=plain)
    lab = (f"hedged {run['h']:.0%}, net" if run["kind"] == "fx"
           else f"overlaid at {ctx.sizing['hedge_ratio']:.0%} (1 XSP), net")
    ax.plot(lvl(s["overlaid_return"]), color=COLORS["overlaid"], lw=2, label=lab)
    if run["kind"] == "option":
        ref = run["ref_series"].loc[A.OUTPUT_START:]
        ax.plot(lvl(ref), color=COLORS["ref"], lw=2, label=f"CBOE {run['spec']['ref']} (reference)")
        ax.plot(lvl(run["gross1"]["overlaid_return"].loc[A.OUTPUT_START:]), color=COLORS["unit"], lw=1.5,
                ls="--", label="model at 100%, gross (vs reference)")
    ax.axvspan(pd.Timestamp(A.IN_SAMPLE_START), pd.Timestamp(A.IN_SAMPLE_END), color="#888888", alpha=0.12,
               lw=0, label="in-sample (calibration) 2010-2017")
    ax.set_title(f"{run['id']}: growth of $1 (monthly, USD)", fontsize=11, loc="left")
    ax.grid(axis="y", color="#dddddd", lw=0.6)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    path = CHARTS / f"{run['id']}_growth.png"
    fig.savefig(path)
    plt.close(fig)
    return str(path.relative_to(ROOT)).replace("\\", "/")


def vrp_chart(ctx):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    CHARTS.mkdir(parents=True, exist_ok=True)
    m = ctx.vrp_monthly.loc["2007-01-01":]
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=120)
    ax.plot(m.index, m["vix"], color=COLORS["plain"], lw=1.6, label="^VIX (implied, monthly average)")
    ax.plot(m.index, m["realised_fwd"], color=COLORS["overlaid"], lw=1.6,
            label="SPY realised vol over the next 21 trading days")
    ax.axvspan(pd.Timestamp(A.IN_SAMPLE_START), pd.Timestamp(A.IN_SAMPLE_END), color="#888888", alpha=0.12, lw=0,
               label="in-sample 2010-2017")
    v = ctx.vrp
    ax.set_title(f"Volatility risk premium: VIX minus realised averaged {v['in_sample']['avg_vrp_points']:.1f} pts "
                 f"in 2010-17 and {v['out_of_sample']['avg_vrp_points']:.1f} pts in 2018-26", fontsize=10, loc="left")
    ax.set_ylabel("annualised vol, points")
    ax.grid(axis="y", color="#dddddd", lw=0.6)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    path = CHARTS / "overlays_vrp.png"
    fig.savefig(path)
    plt.close(fig)
    return str(path.relative_to(ROOT)).replace("\\", "/")


def pct(x, d=1):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x * 100:.{d}f}%"


def num(x, d=2):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{d}f}"


def memo(run, ctx, js):
    o = js["overlay"]
    w, wo = o["with"], o["without"]
    lines = [f"# {js['name']} (`{run['id']}`)", "",
             f"Overlay on {o['underlying']}: {o['strategy']}. Assumptions: `{o['assumptions']}`. "
             f"Monthly series for Phase 5: `{o['monthly_series']}`. Reproduce: `{js['reproduce']}`.", "",
             "## Result (net of costs)", "",
             "| Window | Sharpe plain / overlaid | Vol plain / overlaid | Max DD plain / overlaid | Sortino plain / overlaid | Worst month plain / overlaid | Up / down capture |",
             "|---|---|---|---|---|---|---|"]
    for k, lab in (("in_sample", "In-sample 2010-17"), ("out_of_sample", "OOS 2018-26"), ("full", "Full")):
        a, b = wo[k], w[k]
        lines.append(f"| {lab} | {num(a['sharpe'])} / {num(b['sharpe'])} | {pct(a['vol'])} / {pct(b['vol'])} | "
                     f"{pct(a['max_drawdown'])} / {pct(b['max_drawdown'])} | {num(a['sortino'])} / {num(b['sortino'])} | "
                     f"{pct(a['worst_month'])} / {pct(b['worst_month'])} | {num(b['up_capture'])} / {num(b['down_capture'])} |")
    v = o["verdict_rule"]
    ac = o["annual_cost"]
    lines += ["", f"Average annual cost: {pct(ac['full'], 2)} of the sleeve (in-sample {pct(ac['in_sample'], 2)}, "
                  f"OOS {pct(ac['out_of_sample'], 2)}). Verdict, method.md 8.5 standalone: "
                  f"**{'passes' if v['passes_standalone'] else 'fails'}** (OOS Sharpe change {num(v['oos_sharpe_change'])}, "
                  f"max drawdown change {pct(v['oos_max_drawdown_change'])} points; the portfolio-level test is Phase 5's).", "",
              "## Stress windows (method.md s11)", "", "| Window | Return plain / overlaid | Max DD plain / overlaid | DD reduction |",
              "|---|---|---|---|"]
    for k, sv in js["stress"].items():
        if k == "strong_usd":
            continue
        if "with" not in sv:
            lines.append(f"| {k} | {sv.get('note')} | | |")
            continue
        lines.append(f"| {k} | {pct(sv['without']['return'])} / {pct(sv['with']['return'])} | "
                     f"{pct(sv['without']['max_drawdown'])} / {pct(sv['with']['max_drawdown'])} | {pct(sv['drawdown_reduction'])} |")
    su = js["stress"]["strong_usd"]
    lines.append(f"| strong USD months ({su['months']}) avg | {pct(su['avg_return_without'], 2)} / {pct(su['avg_return_with'], 2)} | | |")
    lines += ["", "## Model and calibration", ""]
    if run["kind"] == "option":
        t = run["tracking"]
        pr = ctx.params
        lines += [f"Black-Scholes on SPY total-return prices; ^VIX/^VIX3M as implied vol; smile fitted on 2010-2017 only "
                  f"and frozen: ATM level {pr.atm_level:+.4f}, call skew {pr.skew_call:.4f}, put skew {pr.skew_put:.4f} "
                  "(vol change per unit of ln(K/F)/sqrt(T)).", ""]
        for k in ("in_sample", "out_of_sample"):
            x = t[k]
            if x:
                lines.append(f"- vs CBOE {t['reference']}, {k}: tracking error {pct(x['tracking_error'])}/yr, mean difference "
                             f"{pct(x['mean_diff_annual'], 2)}/yr, R2 total return {num(x['r2_total_return'], 3)}, "
                             f"R2 of the overlay component {num(x['r2_overlay_component'], 2)} ({x['months']} months).")
        if t.get("note"):
            lines.append(f"- {t['note']}.")
        for k, x in t.items():
            if k.startswith("cross_check") and x["out_of_sample"]:
                lines.append(f"- XYLD cross-check OOS: tracking error {pct(x['out_of_sample']['tracking_error'])}/yr, mean "
                             f"difference {pct(x['out_of_sample']['mean_diff_annual'], 2)}/yr ({x['note']}).")
        vi, vo = ctx.vrp["in_sample"], ctx.vrp["out_of_sample"]
        lines += [f"- Measured volatility risk premium (VIX minus next-21-day realised): {vi['avg_vrp_points']:.1f} pts "
                  f"in-sample, {vo['avg_vrp_points']:.1f} pts OOS (Cboe/Bondarenko 1990-2018: about 4.2).",
                  f"- At exactly 100% hedge ratio: OOS Sharpe {num(o['at_100pct']['with']['out_of_sample']['sharpe'])}, "
                  f"max DD {pct(o['at_100pct']['with']['out_of_sample']['max_drawdown'])}, standalone verdict "
                  f"{'passes' if o['at_100pct']['verdict']['passes_standalone'] else 'fails'}.",
                  f"- Basis: on a 50% IVW / 50% EFG_EEM_5050 sleeve proxy the OOS Sharpe goes "
                  f"{num(o['sleeve_proxy_50_IVW_50_EFG_EEM']['without_oos']['sharpe'])} -> "
                  f"{num(o['sleeve_proxy_50_IVW_50_EFG_EEM']['with_oos']['sharpe'])}, max DD "
                  f"{pct(o['sleeve_proxy_50_IVW_50_EFG_EEM']['without_oos']['max_drawdown'])} -> "
                  f"{pct(o['sleeve_proxy_50_IVW_50_EFG_EEM']['with_oos']['max_drawdown'])}; OOS correlation of EFG_EEM_5050 "
                  f"with SPY {ctx.basis['corr_EFG_EEM_5050_SPY_oos']:.2f}. The overlay is primarily on the US stocks; the "
                  "hedge is imperfect for the international names."]
    else:
        hc = run["hedge_cost"]
        reg = run["regression"]
        lines += ["3-month forwards by covered interest parity from OECD 3-month interbank rates against TB3MS; 5 bp per "
                  "roll; basket weights (GBI-EM, averages where missing): "
                  + ", ".join(f"{c} {x:.0%}" for c, x in run["weights"].items()) + ". "
                  "BRL (no BR_3M series in yields.csv), THB and MYR (no OECD series) are not hedged.", "",
                  f"- Carry given up at this ratio: {pct(hc['in_sample']['carry_given_up_at_ratio'], 2)}/yr in-sample, "
                  f"{pct(hc['out_of_sample']['carry_given_up_at_ratio'], 2)}/yr OOS; roll costs "
                  f"{pct(hc['out_of_sample']['roll_cost_per_year'], 2)}/yr.",
                  f"- EMLC monthly return on the hedged basket's spot return: beta {num(reg['out_of_sample']['beta_to_basket_fx'])}, "
                  f"R2 {num(reg['out_of_sample']['r2'])} OOS (beta {num(reg['in_sample']['beta_to_basket_fx'])}, R2 "
                  f"{num(reg['in_sample']['r2'])} in-sample): the share of EMLC risk this basket can remove.",
                  f"- EBND cross-check OOS Sharpe {num(run['res_ebnd']['without']['out_of_sample']['sharpe'])} -> "
                  f"{num(run['res_ebnd']['with']['out_of_sample']['sharpe'])}."]
    f = o["feasibility"]
    lines += ["", "## Feasibility at $100,000", "", f"- {f.get('note', f.get('contract'))}", f"- {f['margin']}"]
    if run["kind"] == "option":
        for leg in f["legs_today"]:
            lines.append(f"- Today ({f['spx_date']}): {leg['leg']}, XSP strike {leg['strike_xsp']:.1f}, model premium "
                         f"${leg['premium_usd_per_contract']:,.0f} per contract at {leg['implied_vol']:.1%} vol.")
    lines += ["", "## Limits", "",
              "- No option price history: premiums are modelled; the CBOE index is the only realised reference."
              if run["kind"] == "option" else
              "- CIP forwards from interbank rates are not dealer quotes; NDF currencies (INR, IDR, CLP, COP) can deviate from CIP.",
              "- " + " ".join(js["explain"]), ""]
    MEMOS.mkdir(parents=True, exist_ok=True)
    (MEMOS / f"{run['id']}.md").write_text("\n".join(lines), encoding="utf-8")


def summary_memo(runs, ctx):
    lines = ["# Derivative overlays: summary", "",
             "Written by `python -m research.candidates.overlays --all --write`. All numbers net of method.md s10 costs; "
             "OOS = 2018-01 to 2026-10; option overlays at one XSP contract on a $55,000 equity sleeve "
             f"(hedge ratio {ctx.sizing['hedge_ratio']:.2f}), FX overlays at the stated ratio on EMLC.", "",
             "| Overlay | OOS Sharpe plain -> overlaid | OOS vol | OOS max DD | Annual cost | Fit vs CBOE: IS R2 (overlay part) / OOS TE | Passes 8.5 standalone |",
             "|---|---|---|---|---|---|---|"]
    for run in runs:
        r = run["res"]
        w, wo = r["with"]["out_of_sample"], r["without"]["out_of_sample"]
        if run["kind"] == "option":
            t = like_for_like(run, ctx)
            ref = run["spec"]["ref"] + (" 1m model" if run["spec"]["ref"] in ctx.calib and run["id"] == "pput_5pct_3m" else "")
            fit = f"{num(t['in_sample']['r2_overlay_component'])} / {pct(t['out_of_sample']['tracking_error'])} ({ref})"
        else:
            fit = "no fitted parameter"
        lines.append(f"| {run['id']} | {num(wo['sharpe'])} -> {num(w['sharpe'])} | {pct(wo['vol'])} -> {pct(w['vol'])} | "
                     f"{pct(wo['max_drawdown'])} -> {pct(w['max_drawdown'])} | {pct(r['annual_cost']['full'], 2)} | {fit} | "
                     f"{'yes' if r['verdict']['passes_standalone'] else 'no'} |")
    p, vi, vo = ctx.params, ctx.vrp["in_sample"], ctx.vrp["out_of_sample"]
    lines += ["", f"Calibrated smile (2010-2017, frozen): ATM level {p.atm_level:+.4f}, call skew {p.skew_call:.4f}, "
                  f"put skew {p.skew_put:.4f}. Fit by index (gross, 100%):", ""]
    for n, c in ctx.calib.items():
        lines.append(f"- {n}: in-sample TE {pct(c['in_sample']['tracking_error'])}, R2 overlay part "
                     f"{num(c['in_sample']['r2_overlay_component'])}; OOS TE {pct(c['out_of_sample']['tracking_error'])}, "
                     f"R2 overlay part {num(c['out_of_sample']['r2_overlay_component'])}, mean gap "
                     f"{pct(c['out_of_sample']['mean_diff_annual'], 2)}/yr.")
    lines += ["", f"Volatility risk premium (VIX minus next-21-day realised SPY vol): {vi['avg_vrp_points']:.1f} pts "
                  f"2010-2017, {vo['avg_vrp_points']:.1f} pts 2018-2026 (chart `reports/candidates/charts/overlays_vrp.png`).",
              f"Basis: OOS correlation of EFG_EEM_5050 with SPY {ctx.basis['corr_EFG_EEM_5050_SPY_oos']:.2f}; of the "
              f"50/50 sleeve proxy {ctx.basis['corr_sleeve_proxy_SPY_oos']:.2f}.", "",
              "## Honest limits", "",
              "- No option price history exists in the data; every premium is Black-Scholes on the VIX with a fitted smile. "
              "The CBOE indices are the only realised reference, and they are SPX index strategies, not this sleeve.",
              "- PPUT before its 2015 launch (and CLL before 2008) are Cboe back-calculations, not live records; the "
              "calibration window 2010-2017 for PPUT is therefore partly back-filled.",
              "- Feasibility: one XSP contract is about "
              f"${ctx.sizing['notional_per_contract']:,.0f}, i.e. {ctx.sizing['hedge_ratio']:.0%} of the equity sleeve; "
              "whole contracts give 0% or ~139%, nothing in between. Short calls on 139% are partly uncovered and break the "
              "overlay-only rule until the sleeve reaches the contract notional. XSP liquidity (spreads wider than the "
              "assumed 1% of premium half-spread on far strikes) was not checked.",
              "- Basis risk: S&P 500 options on a sleeve that is about half non-US hedge the international names "
              "imperfectly; the sleeve-proxy rows in each JSON quantify it.",
              "- The FX hedge removes carry as well as risk: it gives up the EM-minus-US rate gap every quarter. BRL, THB "
              "and MYR are unhedged for lack of a rate series; CIP from interbank rates ignores NDF basis; today's "
              "country weights are applied to history (look-ahead flag). It is not implementable in a retail account.",
              "- European exercise, continuous strikes, settlement at the close rather than the opening quotation.", ""]
    (MEMOS / "overlays_summary.md").write_text("\n".join(lines), encoding="utf-8")


def run_all(ids, write):
    ctx = build_context()
    runs = []
    for oid in ids:
        run = run_option(oid, ctx) if oid in OPTION_OVERLAYS else run_fx(oid, ctx)
        runs.append(run)
        r = run["res"]
        w, wo = r["with"]["out_of_sample"], r["without"]["out_of_sample"]
        print(f"{oid:26s} OOS Sharpe {wo['sharpe']:.3f} -> {w['sharpe']:.3f}  vol {wo['vol']:.3f} -> {w['vol']:.3f}  "
              f"maxDD {wo['max_drawdown']:.3f} -> {w['max_drawdown']:.3f}  cost/yr {r['annual_cost']['full']:.4f}  "
              f"pass={r['verdict']['passes_standalone']}")
        if write:
            csv = write_monthly(run)
            chart = growth_chart(run, ctx)
            js = build_json(run, ctx, csv, chart)
            REPORTS.mkdir(parents=True, exist_ok=True)
            (REPORTS / f"{oid}.json").write_text(json.dumps(js, indent=2, allow_nan=False), encoding="utf-8")
            memo(run, ctx, js)
    print(f"params {ctx.params}; VRP in {ctx.vrp['in_sample']['avg_vrp_points']:.2f} oos "
          f"{ctx.vrp['out_of_sample']['avg_vrp_points']:.2f}; sizing h={ctx.sizing['hedge_ratio']:.3f}")
    for n, c in ctx.calib.items():
        print(f"  fit {n}: IS TE {c['in_sample']['tracking_error']:.4f} R2ov {c['in_sample']['r2_overlay_component']:.3f} | "
              f"OOS TE {c['out_of_sample']['tracking_error']:.4f} R2ov {c['out_of_sample']['r2_overlay_component']:.3f}")
    if write:
        vrp_chart(ctx)
        if len(ids) == len(ALL_OVERLAYS):
            summary_memo(runs, ctx)
    return ctx, runs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--overlay", action="append", choices=ALL_OVERLAYS)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    ids = ALL_OVERLAYS if a.all or not a.overlay else a.overlay
    run_all(ids, a.write)


if __name__ == "__main__":
    main()
