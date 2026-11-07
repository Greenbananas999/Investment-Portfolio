"""Adversarial review of the derivative overlays (Phase 3, reviewer: opus).

Independent recomputation of the claims in research/candidates/overlays.py,
reports/candidates/<overlay>.json and reports/candidates/overlays/*_monthly.csv.
Nothing the analyst wrote is modified; the analyst module is imported only to
(a) rebuild its series in memory for the reproduction check and (b) run the
perturbation (look-ahead) tests against its own engine. Every other number is
recomputed here from data/research/ with separate code.

    python -m research.reviews.overlays_check            # all checks (~2-3 min)
    python -m research.reviews.overlays_check --quick    # skip calibration re-fit and in-memory rerun
    python -m research.reviews.overlays_check --json out.json
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research"
REP = ROOT / "reports" / "candidates"
OVL = REP / "overlays"
OPTION_IDS = ["cc_spx_30d_1m", "cc_spx_atm_1m", "pput_5pct_3m", "collar_cll_95_110"]
FX_IDS = ["fxfwd_emlocal_50pct_3m", "fxfwd_emlocal_100pct_3m"]
ALL_IDS = OPTION_IDS + FX_IDS
IS_, IE_, OS_ = "2010-01-01", "2017-12-31", "2018-01-01"
OUT = {}


def say(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------------------
# Independent statistics (own code, not research/metrics.py)
# ---------------------------------------------------------------------------
def raw_prices(cols):
    head = pd.read_csv(DATA / "prices.csv", nrows=0).columns
    df = pd.read_csv(DATA / "prices.csv", index_col=0, parse_dates=True,
                     usecols=[head[0]] + [c for c in cols if c in head]).sort_index()
    return df[~df.index.duplicated(keep="last")].apply(pd.to_numeric, errors="coerce")


def monthly(px):
    return px.resample("ME").last().pct_change(fill_method=None)


def stats(r, rf):
    r = r.dropna()
    ex = r - rf.reindex(r.index).fillna(0.0)
    w = (1 + r).cumprod()
    w = pd.concat([pd.Series([1.0]), w.reset_index(drop=True)])
    return {"sharpe": float(ex.mean() / ex.std(ddof=1) * math.sqrt(12)),
            "vol": float(r.std(ddof=1) * math.sqrt(12)),
            "max_dd": float((w / w.cummax() - 1).min()),
            "cagr": float((1 + r).prod() ** (12 / len(r)) - 1), "months": int(len(r))}


def rule85(plain, over, pts=0.02):
    ds, dd = over["sharpe"] - plain["sharpe"], over["max_dd"] - plain["max_dd"]
    return {"d_sharpe": ds, "d_maxdd_pts": dd * 100, "passes_sharpe": bool(ds > 0),
            "passes_dd": bool(dd >= pts), "passes": bool(ds > 0 or dd >= pts)}


# ---------------------------------------------------------------------------
# 1. Statistics from the published CSVs vs the JSON
# ---------------------------------------------------------------------------
def check_csv_stats(rf):
    say("\n== 1. OOS stats recomputed from reports/candidates/overlays/*_monthly.csv ==")
    res = {}
    for oid in ALL_IDS:
        df = pd.read_csv(OVL / f"{oid}_monthly.csv", index_col=0, parse_dates=True)
        js = json.loads((REP / f"{oid}.json").read_text(encoding="utf-8"))
        o = df.loc[OS_:]
        plain, over = stats(o["underlying_return"], rf), stats(o["overlaid_return"], rf)
        h100 = stats(o["underlying_return"] + o["overlay_return_h100"], rf)
        jw, jwo = js["overlay"]["with"]["out_of_sample"], js["overlay"]["without"]["out_of_sample"]
        diffs = {"sharpe_with": over["sharpe"] - jw["sharpe"], "sharpe_without": plain["sharpe"] - jwo["sharpe"],
                 "vol_with": over["vol"] - jw["vol"], "dd_with": over["max_dd"] - jw["max_drawdown"],
                 "dd_without": plain["max_dd"] - jwo["max_drawdown"]}
        row = {"plain": plain, "overlaid_csv_ratio": over, "overlaid_h100": h100,
               "hedge_ratio_csv": float(df["hedge_ratio"].iloc[0]),
               "verdict_csv_ratio": rule85(plain, over), "verdict_h100": rule85(plain, h100),
               "max_abs_diff_vs_json": float(max(abs(v) for v in diffs.values())),
               "cost_annual_oos_csv": float(o["cost"].mean() * 12),
               "cost_annual_oos_json": js["overlay"]["annual_cost"]["out_of_sample"],
               "cost_annual_full_json": js["overlay"]["annual_cost"]["full"]}
        if "at_100pct" in js["overlay"]:
            a = js["overlay"]["at_100pct"]["with"]["out_of_sample"]
            row["h100_vs_json"] = {"sharpe": h100["sharpe"] - a["sharpe"], "dd": h100["max_dd"] - a["max_drawdown"]}
            pr = js["overlay"]["sleeve_proxy_50_IVW_50_EFG_EEM"]
            row["proxy_json"] = {"plain_sharpe": pr["without_oos"]["sharpe"], "with_sharpe": pr["with_oos"]["sharpe"],
                                 "plain_dd": pr["without_oos"]["max_drawdown"], "with_dd": pr["with_oos"]["max_drawdown"]}
        res[oid] = row
        say(f"{oid:26s} h={row['hedge_ratio_csv']:.3f} plain S {plain['sharpe']:.3f} vol {plain['vol']:.3f} "
            f"DD {plain['max_dd']:.3f} | csv-ratio S {over['sharpe']:.3f} vol {over['vol']:.3f} DD {over['max_dd']:.3f} "
            f"pass={row['verdict_csv_ratio']['passes']} | h100 S {h100['sharpe']:.3f} vol {h100['vol']:.3f} "
            f"DD {h100['max_dd']:.3f} pass={row['verdict_h100']['passes']} | max|diff| vs JSON "
            f"{row['max_abs_diff_vs_json']:.1e} | cost OOS {row['cost_annual_oos_csv']:.4f}")
    OUT["csv_stats"] = res
    return res


def check_spy_underlying(rf):
    """The CSV 'underlying' should equal SPY's monthly return from raw prices.csv (no spike filter)."""
    spy = monthly(raw_prices(["SPY"])["SPY"])
    df = pd.read_csv(OVL / "cc_spx_30d_1m_monthly.csv", index_col=0, parse_dates=True)
    d = (df["underlying_return"] - spy.reindex(df.index)).abs()
    last = raw_prices(["SPY"])["SPY"].dropna().index[-1]
    OUT["spy_underlying"] = {"max_abs_diff": float(d.max()), "spy_last_date": str(last.date())}
    say(f"\nSPY underlying vs raw prices.csv monthly: max |diff| {d.max():.2e}; SPY last date {last.date()}")


# ---------------------------------------------------------------------------
# 2. Black-Scholes
# ---------------------------------------------------------------------------
def bs(S, K, T, r, s, kind):
    d1 = (math.log(S / K) + (r + 0.5 * s * s) * T) / (s * math.sqrt(T))
    d2 = d1 - s * math.sqrt(T)
    if kind == "call":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def check_bs():
    from research.candidates import overlays as O
    say("\n== 2. Black-Scholes ==")
    c = O.bs_price(100, 100, 1 / 12, 0.0, 0.2, "call")
    p = O.bs_price(100, 100, 1 / 12, 0.0, 0.2, "put")
    textbook = 100 * (2 * norm.cdf(0.5 * 0.2 * math.sqrt(1 / 12)) - 1)   # ATM, r=0: S(2N(s sqrtT/2)-1)
    worst = 0.0
    for S, K, T, r, s in [(100, 95, 0.25, 0.03, 0.25), (7600, 7900, 30 / 365, 0.04, 0.15),
                          (50, 60, 1.0, 0.01, 0.5), (100, 110, 0.1, 0.05, 0.12)]:
            cc, pp = O.bs_price(S, K, T, r, s, "call"), O.bs_price(S, K, T, r, s, "put")
            worst = max(worst, abs(cc - pp - (S - K * math.exp(-r * T))),
                        abs(cc - bs(S, K, T, r, s, "call")), abs(pp - bs(S, K, T, r, s, "put")))
    OUT["bs"] = {"call_100_100_1m_20pct": c, "put": p, "textbook": textbook,
                 "max_parity_or_independent_error": worst}
    say(f"call {c:.6f} put {p:.6f} textbook {textbook:.6f}; max parity/independent error {worst:.2e}")


# ---------------------------------------------------------------------------
# Independent option engine (own roll calendar, smile, strike solver, loop)
# ---------------------------------------------------------------------------
def third_fridays(days, months=None, extend=6):
    out = []
    start, end = days[0].to_period("M"), days[-1].to_period("M") + extend
    for per in pd.period_range(start, end, freq="M"):
        if months and per.month not in months:
            continue
        d1 = per.start_time
        fri = d1 + pd.Timedelta(days=(4 - d1.weekday()) % 7 + 14)
        if fri <= days[-1]:
            prior = days[(days <= fri) & (days.to_period("M") == per)]
            if len(prior):
                out.append(prior[-1])
        else:
            out.append(fri)
    return pd.DatetimeIndex(out)


def smile(S, K, tau, r, vix, v3, p):
    tau = max(tau, 1 / 365)
    t1, t2 = 30 / 365, 93 / 365
    s1 = vix / 100
    s2 = (v3 if np.isfinite(v3) else vix) / 100
    if tau <= t1:
        atm = s1
    elif tau >= t2:
        atm = s2
    else:
        atm = math.sqrt((s1 ** 2 * t1 + (s2 ** 2 * t2 - s1 ** 2 * t1) * (tau - t1) / (t2 - t1)) / tau)
    m = math.log(K / (S * math.exp(r * tau))) / math.sqrt(tau)
    k = p["skew_call"] if K >= S else p["skew_put"]
    return max(atm + p["atm_level"] - k * m, 0.03)


def strike(spec, S, tau, r, vix, v3, p, kind):
    how = spec[0]
    if how == "atm":
        return S
    if how == "pct":
        return spec[1] * S
    target = spec[1]

    def f(K):
        s = smile(S, K, tau, r, vix, v3, p)
        return norm.cdf((math.log(S / K) + (r + 0.5 * s * s) * tau) / (s * math.sqrt(tau))) - target
    return brentq(f, S * 0.8, S * 1.5, xtol=1e-10)


def engine(daily, legs, h, p, costs, start="2006-08-01"):
    """legs: list of (kind, sign, strike_spec, months_or_None). Returns monthly overlaid, under, cost."""
    d = daily.loc[start:]
    days = d.index
    S, spx, vix, v3, r = (d[c].to_numpy() for c in ("S", "spx", "vix", "vix3m", "r"))
    sched = {}
    for leg in legs:
        sched[leg[3]] = third_fridays(days, leg[3])
    idx = {t: i for i, t in enumerate(days)}
    me = set(pd.Series(np.arange(len(days)), index=days).groupby(days.to_period("M")).max())
    rolls = {k: {idx[t] for t in v if t in idx} for k, v in sched.items()}
    first = min(min(v) for v in rolls.values())
    ev = sorted(i for i in set().union(*rolls.values(), me) if i >= first)
    units, cash, opn, cum, prev, rec = 1.0 / S[first], 0.0, [], 0.0, first, []

    def mark(i):
        v = 0.0
        for o in opn:
            tau = (o["exp"] - days[i]).days / 365
            if tau <= 0:
                px = max(S[i] - o["K"], 0) if o["kind"] == "call" else max(o["K"] - S[i], 0)
            else:
                px = bs(S[i], o["K"], tau, r[i], smile(S[i], o["K"], tau, r[i], vix[i], v3[i], p), o["kind"])
            v += o["sign"] * o["q"] * px
        return v

    for i in ev:
        cash *= math.exp(r[prev] * (days[i] - days[prev]).days / 365)
        still = []
        for o in opn:
            if days[i] >= o["exp"]:
                cash += o["sign"] * o["q"] * (max(S[i] - o["K"], 0) if o["kind"] == "call" else max(o["K"] - S[i], 0))
            else:
                still.append(o)
        opn = still
        todo = [leg for leg in legs if i in rolls[leg[3]]]
        if todo:
            ov = mark(i)
            V = units * S[i] + cash + ov
            units, cash = (V - ov) / S[i], 0.0
            for kind, sign, spec, mo in todo:
                nxt = sched[mo]
                exp = nxt[nxt > days[i]][0]
                tau = (exp - days[i]).days / 365
                K = strike(spec, S[i], tau, r[i], vix[i], v3[i], p, kind)
                prem = bs(S[i], K, tau, r[i], smile(S[i], K, tau, r[i], vix[i], v3[i], p), kind)
                q = h * V / S[i]
                cash -= sign * q * prem
                if costs:
                    c = 0.01 * q * prem + 0.65 * (h * V / (10 * spx[i]))   # contracts = notional / (SPX x 10)
                    cash -= c
                    cum += c
                opn.append({"kind": kind, "sign": sign, "K": K, "exp": exp, "q": q})
        if i in me:
            rec.append((days[i] + pd.offsets.MonthEnd(0), units * S[i] + cash + mark(i), S[i], cum))
        prev = i
    df = pd.DataFrame(rec, columns=["date", "value", "under", "cum"]).set_index("date")
    return pd.DataFrame({"over": df["value"].pct_change(), "under": df["under"].pct_change(),
                         "cost": df["cum"].diff() / df["value"].shift(1)}).iloc[1:]


LEGS = {"cc_spx_30d_1m": [("call", -1, ("delta", 0.30), None)],
        "cc_spx_atm_1m": [("call", -1, ("atm",), None)],
        "pput_5pct_3m": [("put", +1, ("pct", 0.95), (3, 6, 9, 12))],
        "collar_cll_95_110": [("put", +1, ("pct", 0.95), (3, 6, 9, 12)), ("call", -1, ("pct", 1.10), None)],
        "PPUT_1m": [("put", +1, ("pct", 0.95), None)]}


def check_engine(daily, p, rf):
    say("\n== 2b. Independent engine vs published CSV (net, at the CSV hedge ratio and at 100%) ==")
    res = {}
    for oid in OPTION_IDS:
        df = pd.read_csv(OVL / f"{oid}_monthly.csv", index_col=0, parse_dates=True)
        h = float(df["hedge_ratio"].iloc[0])
        mine = engine(daily, LEGS[oid], h, p, True).loc[IS_:]
        mine1 = engine(daily, LEGS[oid], 1.0, p, True).loc[IS_:]
        d = (mine["over"] - df["overlaid_return"]).abs()
        d1 = ((mine1["over"] - mine1["under"]) - df["overlay_return_h100"]).abs()
        dc = (mine["cost"] - df["cost"]).abs()
        lin = df["overlay_return"] - h * df["overlay_return_h100"]
        res[oid] = {"max_abs_diff_overlaid": float(d.max()), "max_abs_diff_h100_overlay": float(d1.max()),
                    "max_abs_diff_cost": float(dc.max()), "annual_cost_mine_oos": float(mine["cost"].loc[OS_:].mean() * 12),
                    "annual_cost_mine_oos_h100": float(mine1["cost"].loc[OS_:].mean() * 12),
                    "nonlinearity_overlay_minus_h_times_h100_mean_annual": float(lin.loc[OS_:].mean() * 12),
                    "nonlinearity_te": float(lin.loc[OS_:].std() * math.sqrt(12))}
        say(f"{oid:22s} max|diff| overlaid {d.max():.1e}, h100 overlay {d1.max():.1e}, cost {dc.max():.1e}; "
            f"annual cost OOS {res[oid]['annual_cost_mine_oos']:.4f} (h100 {res[oid]['annual_cost_mine_oos_h100']:.4f}); "
            f"h-scaling gap {res[oid]['nonlinearity_overlay_minus_h_times_h100_mean_annual']:+.4f}/yr")
    OUT["engine"] = res
    return res


# ---------------------------------------------------------------------------
# 2c. Look-ahead: perturb data after a date, the series before it must not move
# ---------------------------------------------------------------------------
def check_lookahead(daily, p):
    from research.candidates import overlays as O
    say("\n== 2c. Look-ahead perturbation on the analyst engine ==")
    P = O.Params(**p)
    cut = pd.Timestamp("2020-02-14")       # day after which VIX and SPY are distorted
    res = {}
    for oid in OPTION_IDS:
        legs = O.OPTION_OVERLAYS[oid]["legs"]
        base = O.to_returns(O.simulate(daily, legs, 1.0, P, "2006-08-01"))
        pert = daily.copy()
        m = pert.index > cut
        pert.loc[m, "vix"] *= 2.5
        pert.loc[m, "vix3m"] *= 2.5
        pert.loc[m, "S"] *= 0.6
        alt = O.to_returns(O.simulate(pert, legs, 1.0, P, "2006-08-01"))
        before = (base.loc[:"2020-01-31"] - alt.loc[:"2020-01-31"]).abs().max().max()
        after = (base.loc["2020-03-31":] - alt.loc["2020-03-31":]).abs().max().max()
        res[oid] = {"max_change_months_before_cut": float(before), "max_change_after": float(after)}
        say(f"{oid:22s} months <= 2020-01: max change {before:.1e} (must be 0); after: {after:.1e}")
    OUT["lookahead"] = res


def check_calibration_frozen(mkt):
    from research.candidates import overlays as O
    say("\n== 3a. Calibration uses 2010-2017 only: distort all data after 2017 and re-fit ==")
    daily = mkt["daily"].copy()
    m = daily.index > "2017-12-31"
    daily.loc[m, ["vix", "vix3m"]] *= 3.0
    daily.loc[m, "S"] *= 0.5
    cboe = {k: v.copy() for k, v in mkt["cboe"].items()}
    for k in cboe:
        cboe[k].loc[cboe[k].index > "2017-12-31"] *= 0.3
    p_alt = O.calibrate(daily, cboe)
    p0 = O.calibrate(mkt["daily"], mkt["cboe"])
    js = json.loads((REP / "cc_spx_30d_1m.json").read_text(encoding="utf-8"))["overlay"]["calibration"]["params"]
    OUT["calibration"] = {"refit": p0.__dict__, "refit_with_post2017_distorted": p_alt.__dict__, "json": js}
    say(f"refit {p0.__dict__}\ndistorted post-2017 {p_alt.__dict__}\nJSON {js}")
    return p0.__dict__


# ---------------------------------------------------------------------------
# 3b. Model vs CBOE indices (gross, 100%), and the verdict on the real indices
# ---------------------------------------------------------------------------
def cboe_m(name, days):
    s = pd.read_csv(DATA / "cboe" / f"{name}.csv", index_col=0, parse_dates=True)["value"].sort_index()
    s = s[~s.index.duplicated(keep="last")]
    lv = s.reindex(s.index.union(days)).ffill().reindex(days)
    lv = lv.groupby(days.to_period("M")).last()
    lv.index = lv.index.to_timestamp("M")
    return lv.pct_change(fill_method=None)


def check_tracking(daily, p, rf):
    say("\n== 3b. Model (gross, h=1, own engine) vs CBOE index; and rule 8.5 on the CBOE index itself ==")
    days = daily.index
    res = {}
    pairs = [("cc_spx_30d_1m", "BXMD"), ("cc_spx_atm_1m", "BXM"), ("PPUT_1m", "PPUT"), ("pput_5pct_3m", "PPUT"),
             ("collar_cll_95_110", "CLL")]
    spy = None
    for mid, ref in pairs:
        g = engine(daily, LEGS[mid], 1.0, p, False)
        spy = g["under"]
        cb = cboe_m(ref, days)
        out = {}
        for lab, sl in (("in_sample", slice(IS_, IE_)), ("out_of_sample", slice(OS_, None))):
            df = pd.concat([g["over"], cb, g["under"]], axis=1, keys=["m", "ref", "u"], sort=True).loc[sl].dropna()
            e = df["m"] - df["ref"]
            ovm, ovr = df["m"] - df["u"], df["ref"] - df["u"]
            out[lab] = {"te": float(e.std() * math.sqrt(12)), "mean_gap_annual": float(e.mean() * 12),
                        "r2_overlay": float(1 - ((ovm - ovr) ** 2).sum() / ((ovr - ovr.mean()) ** 2).sum()),
                        "overlay_mean_model": float(ovm.mean() * 12), "overlay_mean_index": float(ovr.mean() * 12),
                        "index_minus_spy_mean": float(ovr.mean() * 12)}
        o = pd.concat([cb, g["under"], g["over"]], axis=1, keys=["ref", "u", "m"], sort=True).loc[OS_:].dropna()
        out["oos_rule85_on_index"] = {"spy": stats(o["u"], rf), "index": stats(o["ref"], rf),
                                      "model_gross": stats(o["m"], rf)}
        out["oos_rule85_on_index"]["verdict_index"] = rule85(out["oos_rule85_on_index"]["spy"],
                                                             out["oos_rule85_on_index"]["index"])
        res[f"{mid}_vs_{ref}"] = out
        a, b = out["in_sample"], out["out_of_sample"]
        v = out["oos_rule85_on_index"]
        say(f"{mid:18s} vs {ref:5s} IS TE {a['te']:.4f} gap {a['mean_gap_annual']:+.4f} R2ov {a['r2_overlay']:.3f} | "
            f"OOS TE {b['te']:.4f} gap {b['mean_gap_annual']:+.4f} R2ov {b['r2_overlay']:.3f} | "
            f"overlay part model {b['overlay_mean_model']:+.4f} index {b['overlay_mean_index']:+.4f}/yr")
        say(f"{'':18s} OOS on the real index: SPY S {v['spy']['sharpe']:.3f} DD {v['spy']['max_dd']:.3f}; "
            f"{ref} S {v['index']['sharpe']:.3f} DD {v['index']['max_dd']:.3f} vol {v['index']['vol']:.3f}; "
            f"model gross S {v['model_gross']['sharpe']:.3f} DD {v['model_gross']['max_dd']:.3f}; "
            f"rule 8.5 on index passes={v['verdict_index']['passes']}")
    # SPY vs SPX price + dividends cannot be checked (no SPX TR series); the SPY fee is ~0.09%/yr.
    OUT["tracking"] = res
    return res


# ---------------------------------------------------------------------------
# 4. VRP
# ---------------------------------------------------------------------------
def check_vrp(daily):
    say("\n== 4. Volatility risk premium ==")
    lr = np.log(daily["S"]).diff()
    fwd = lr.rolling(21).std().shift(-21) * math.sqrt(252) * 100
    trl = lr.rolling(21).std() * math.sqrt(252) * 100
    res = {}
    for lab, sl in (("in_sample", slice(IS_, IE_)), ("out_of_sample", slice(OS_, None))):
        a = pd.DataFrame({"v": daily["vix"], "f": fwd, "t": trl}).loc[sl]
        af, at = a.dropna(subset=["v", "f"]), a.dropna(subset=["v", "t"])
        res[lab] = {"vix_minus_fwd21": float((af["v"] - af["f"]).mean()),
                    "vix_minus_trailing21": float((at["v"] - at["t"]).mean()),
                    "avg_vix": float(af["v"].mean()), "avg_fwd_realised": float(af["f"].mean()),
                    "median_vix_minus_fwd": float((af["v"] - af["f"]).median()),
                    "end": str(af.index[-1].date())}
        say(f"{lab}: VIX - next-21d realised {res[lab]['vix_minus_fwd21']:.2f} pts (median "
            f"{res[lab]['median_vix_minus_fwd']:.2f}); VIX - trailing-21d {res[lab]['vix_minus_trailing21']:.2f}; "
            f"avg VIX {res[lab]['avg_vix']:.2f}, realised {res[lab]['avg_fwd_realised']:.2f}")
    OUT["vrp"] = res


# ---------------------------------------------------------------------------
# 6. Sizing
# ---------------------------------------------------------------------------
def check_sizing():
    say("\n== 6. Sizing ==")
    g = raw_prices(["^GSPC", "SPY"])
    spx, spy = g["^GSPC"].dropna(), g["SPY"].dropna()
    n = spx.iloc[-1] * 100 / 10
    res = {"spx_last": float(spx.iloc[-1]), "date": str(spx.index[-1].date()), "xsp_notional": float(n),
           "ratio_on_55k": float(n / 55000), "spy_option_notional": float(spy.iloc[-1] * 100),
           "equity_sleeve_needed_for_1_covered": float(n), "ratio_on_65k_sleeve": float(n / 65000),
           "ratio_on_45k_sleeve": float(n / 45000), "ratio_on_whole_100k": float(n / 100000),
           "xsp_notional_2010_01": float(spx.loc["2010-01"].iloc[-1] * 10)}
    OUT["sizing"] = res
    say(f"SPX {res['spx_last']:.2f} on {res['date']}: XSP notional ${n:,.0f} = {n / 55000:.3f} of $55k "
        f"({n / 65000:.2f} at $65k, {n / 45000:.2f} at $45k); SPY lot ${res['spy_option_notional']:,.0f}; "
        f"XSP notional Jan 2010 ${res['xsp_notional_2010_01']:,.0f}")


# ---------------------------------------------------------------------------
# 8. FX forwards (independent CIP and hedge loop)
# ---------------------------------------------------------------------------
CCY = {"MXN": "MX", "ZAR": "ZA", "INR": "IN", "IDR": "ID", "PLN": "PL", "HUF": "HU", "CZK": "CZ", "CLP": "CL", "COP": "CO"}


def fx_data():
    fx = pd.read_csv(DATA / "fx.csv", index_col=0, parse_dates=True).sort_index()
    y = pd.read_csv(DATA / "yields.csv", index_col=0, parse_dates=True).sort_index()
    return fx, y


def check_fx(rf):
    from research.candidates import overlays as O
    say("\n== 8. FX forwards ==")
    mkt = O.load_market()                    # spot FX after the analyst's spike filter (data handling, not the hedge)
    spot, rates = O.fx_inputs(mkt)
    w = O.fx_weights()
    fxraw, y = fx_data()
    res = {"weights": w.round(4).to_dict()}
    # (a) CIP forward by hand for MXN and PLN at 2019-03-31 and 2023-06-30
    hand = {}
    for c in ("MXN", "PLN"):
        for t in ("2019-03-31", "2023-06-30"):
            tt = pd.Timestamp(t)
            us = y["US_3M"].loc[tt.to_period("M").start_time] / 100
            lo = y[f"{CCY[c]}_3M"].loc[tt.to_period("M").start_time] / 100
            f_hand = ((1 + us) / (1 + lo)) ** 0.25
            f_code = O.cip_forward_factor(rates.loc[tt, "USD"], rates.loc[tt, c], 3)
            s0 = fxraw[c].loc[:tt].dropna().iloc[-1]
            s1t = tt + pd.offsets.MonthEnd(3)
            s1 = fxraw[c].loc[:s1t].dropna().iloc[-1]
            hand[f"{c}_{t}"] = {"us_3m": float(us), "local_3m": float(lo), "F_over_S_hand": float(f_hand),
                                "F_over_S_code": float(f_code), "S0": float(s0), "S_3m_later": float(s1),
                                "hedge_return_per_unit": float(f_hand - s1 / s0),
                                "annual_carry_given_up": float(1 - f_hand ** 4)}
            say(f"{c} {t}: US {us:.4f} local {lo:.4f} F/S hand {f_hand:.6f} code {f_code:.6f}; S0 {s0:.6f} "
                f"S(+3m) {s1:.6f}; hedge P&L per unit {f_hand - s1 / s0:+.4f}")
    res["cip_by_hand"] = hand
    # (b) independent hedge loop: notional fixed at roll, rolled at Mar/Jun/Sep/Dec month ends,
    #     marked to market each month end at that day's spot and CIP forward for the remaining months.
    emlc = mkt["monthly"]["EMLC"].dropna()
    months = emlc.index
    sp = spot.reindex(spot.index.union(months)).ffill()
    rt = rates.reindex(rates.index.union(months)).ffill(limit=12)
    for h in (0.5, 1.0):
        V, rec = 1.0, []
        t0 = months[0] - pd.offsets.MonthEnd(1)

        def open_at(t, V):
            ok = [c for c in w.index if np.isfinite(sp.loc[t, c]) and np.isfinite(rt.loc[t, c])]
            ww = w[ok] / w[ok].sum()
            q = 3 - t.month % 3 if t.month % 3 else 3
            F = {c: ((1 + rt.loc[t, "USD"]) / (1 + rt.loc[t, c])) ** (q / 12) for c in ok}
            return {"w": ww, "F": F, "S0": sp.loc[t, ok], "N": h * V, "exp": t + pd.offsets.MonthEnd(q), "m": 0.0}
        pos = open_at(t0, V)
        cost_next = 5e-4 * h * V
        for t in months:
            left = (pos["exp"].to_period("M") - t.to_period("M")).n
            m = sum(pos["w"][c] * (pos["F"][c] - sp.loc[t, c] / pos["S0"][c] *
                                   (((1 + rt.loc[t, "USD"]) / (1 + rt.loc[t, c])) ** (left / 12) if left > 0 else 1.0))
                    for c in pos["w"].index)
            Vp = V
            V = V * (1 + emlc.loc[t]) + pos["N"] * (m - pos["m"]) - cost_next
            pos["m"], cost_next = m, 0.0
            if t >= pos["exp"]:
                pos = open_at(t, V)
                V -= 5e-4 * h * V
            rec.append((t, V / Vp - 1))
        mine = pd.Series(dict(rec))
        oid = "fxfwd_emlocal_50pct_3m" if h == 0.5 else "fxfwd_emlocal_100pct_3m"
        csv = pd.read_csv(OVL / f"{oid}_monthly.csv", index_col=0, parse_dates=True)
        d = (mine.reindex(csv.index) - csv["overlaid_return"]).abs().max()
        res[f"engine_{oid}_max_abs_diff"] = float(d)
        say(f"{oid}: independent loop vs CSV overlaid max|diff| {d:.1e}")
    # (c) sign: the months the basket rose most
    bsr = O.basket_spot_return(spot, w)
    csv = pd.read_csv(OVL / "fxfwd_emlocal_100pct_3m_monthly.csv", index_col=0, parse_dates=True)
    j = pd.concat([bsr.rename("basket"), csv["overlay_return"], csv["underlying_return"]], axis=1, sort=True).dropna()
    top = j.sort_values("basket").tail(3)
    bot = j.sort_values("basket").head(3)
    res["sign_check_top_basket_months"] = {str(k.date()): v for k, v in top.round(4).T.to_dict().items()}
    res["sign_check_bottom_basket_months"] = {str(k.date()): v for k, v in bot.round(4).T.to_dict().items()}
    res["corr_overlay_basket"] = float(j["overlay_return"].corr(j["basket"]))
    say(f"basket up months (basket, overlay, EMLC):\n{top}\nbasket down months:\n{bot}\n"
        f"corr(overlay, basket) {res['corr_overlay_basket']:.3f}")
    # (d) carry given up, independently: annualised CIP gap at each quarter-end roll, weighted
    car = []
    for t in rates.index[(rates.index >= "2010-06-30") & (rates.index.month % 3 == 0)]:
        ok = [c for c in w.index if np.isfinite(rt.loc[t, c]) and np.isfinite(sp.loc[t, c])]
        ww = w[ok] / w[ok].sum()
        car.append((t, float(sum(ww[c] * (1 - (1 + rt.loc[t, "USD"]) / (1 + rt.loc[t, c])) for c in ok))))
    car = pd.Series(dict(car))
    res["carry_given_up_100pct"] = {"in_sample": float(car.loc[IS_:IE_].mean()),
                                    "out_of_sample": float(car.loc[OS_:"2026-10-31"].mean())}
    say(f"carry given up at 100% (own calc, quarterly rolls): IS {car.loc[IS_:IE_].mean():.4f}, "
        f"OOS {car.loc[OS_:'2026-10-31'].mean():.4f}")
    # (e) INR look-ahead: INR is 19% of the hedge basket in every month since its rate starts (2011-11)
    res["inr_weight"] = float(w["INR"])
    res["omitted_with_data"] = {"CNY": {"gbiem_weight_pct": 14.93, "CN_3M_last": str(y["CN_3M"].dropna().index[-1].date())},
                                "TRY": {"gbiem_weight_pct": 4.02, "TR_3M_last": str(y["TR_3M"].dropna().index[-1].date())}}
    # (f) regression and an ex-post OLS hedge ratio for context
    df = pd.concat([emlc.rename("f"), bsr.rename("x")], axis=1, sort=True).dropna()
    for lab, sl in (("in_sample", slice(IS_, IE_)), ("out_of_sample", slice(OS_, None))):
        part = df.loc[sl]
        b = np.polyfit(part["x"], part["f"], 1)[0]
        res[f"beta_{lab}"] = {"beta": float(b), "r2": float(part.corr().iloc[0, 1] ** 2)}
    say(f"EMLC on basket: IS {res['beta_in_sample']}, OOS {res['beta_out_of_sample']}")
    OUT["fx"] = res


# ---------------------------------------------------------------------------
# 7b. Indicative portfolio-level test (rule 8.5 is a portfolio rule)
# ---------------------------------------------------------------------------
def check_portfolio(rf):
    say("\n== 7b. Indicative portfolio-level rule 8.5 on GUIDE_BENCH (55% ACWX / 35% EMB / 10% GLD, monthly rebal) ==")
    m = monthly(raw_prices(["ACWX", "EMB", "GLD", "IVW", "EFG", "EEM", "EMLC", "SPY"]))
    res = {}
    o = m.loc[OS_:]
    e50 = 0.5 * o["EFG"] + 0.5 * o["EEM"]
    res["basis"] = {"corr_EFG_EEM_5050_SPY_oos": float(e50.corr(o["SPY"])),
                    "corr_50IVW_50EFGEEM_SPY_oos": float((0.5 * o["IVW"] + 0.5 * e50).corr(o["SPY"])),
                    "corr_ACWX_SPY_oos": float(o["ACWX"].corr(o["SPY"]))}
    say(f"basis: {res['basis']}")
    m = m.loc[:"2026-10-31"]                 # same last month as the overlay CSVs (prices.csv runs into Nov)
    gb = 0.55 * m["ACWX"] + 0.35 * m["EMB"] + 0.10 * m["GLD"]
    base = stats(gb.loc[OS_:], rf)
    res["GUIDE_BENCH"] = base
    for oid in OPTION_IDS:
        df = pd.read_csv(OVL / f"{oid}_monthly.csv", index_col=0, parse_dates=True)
        for lab, col, k in (("h100", "overlay_return_h100", 1.0), ("csv_ratio", "overlay_return", 1.0)):
            p = gb + 0.55 * k * df[col].reindex(gb.index)
            s = stats(p.loc[OS_:], rf)
            res[f"{oid}_{lab}"] = {**s, **rule85(base, s)}
            say(f"{oid:20s} {lab:9s} Sharpe {base['sharpe']:.3f} -> {s['sharpe']:.3f}, DD {base['max_dd']:.3f} -> "
                f"{s['max_dd']:.3f}  pass={res[f'{oid}_{lab}']['passes']}")
    for oid in FX_IDS:
        df = pd.read_csv(OVL / f"{oid}_monthly.csv", index_col=0, parse_dates=True)
        # EMLC as 1/4 of the 35% bond sleeve (8.75% of the portfolio), replacing a quarter of EMB
        g2 = 0.55 * m["ACWX"] + 0.2625 * m["EMB"] + 0.0875 * m["EMLC"] + 0.10 * m["GLD"]
        b2 = stats(g2.loc[OS_:], rf)
        p = g2 + 0.0875 * df["overlay_return"].reindex(g2.index)
        s = stats(p.loc[OS_:], rf)
        res[oid] = {"base": b2, **s, **rule85(b2, s)}
        say(f"{oid:20s} (EMLC 8.75%) Sharpe {b2['sharpe']:.3f} -> {s['sharpe']:.3f}, DD {b2['max_dd']:.3f} -> "
            f"{s['max_dd']:.3f}  pass={res[oid]['passes']}")
    OUT["portfolio_indicative"] = res


# ---------------------------------------------------------------------------
# 1b. Reproduction in memory (analyst code) vs the published files
# ---------------------------------------------------------------------------
def check_rerun(ctx):
    from research.candidates import overlays as O
    say("\n== 1b. In-memory rerun of the analyst code vs published CSVs ==")
    res = {}
    for oid in ALL_IDS:
        run = O.run_option(oid, ctx) if oid in O.OPTION_OVERLAYS else O.run_fx(oid, ctx)
        s = run["series"].loc["2010-01-01":, O.COLS]
        csv = pd.read_csv(OVL / f"{oid}_monthly.csv", index_col=0, parse_dates=True)
        s.index = pd.to_datetime(s.index.strftime("%Y-%m-%d"))
        d = float((s - csv).abs().max().max())
        res[oid] = d
        say(f"{oid:26s} max|diff| {d:.1e} (CSV is written at 8 decimals)")
    OUT["rerun"] = res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    from research.candidates import overlays as O
    bil = monthly(raw_prices(["BIL"])["BIL"])
    check_csv_stats(bil)
    check_spy_underlying(bil)
    check_bs()
    mkt = O.load_market()
    daily = mkt["daily"]
    if a.quick:
        p = json.loads((REP / "cc_spx_30d_1m.json").read_text(encoding="utf-8"))["overlay"]["calibration"]["params"]
    else:
        p = check_calibration_frozen(mkt)
    check_engine(daily, p, bil)
    check_lookahead(daily, p)
    check_tracking(daily, p, bil)
    check_vrp(daily)
    check_sizing()
    check_fx(bil)
    check_portfolio(bil)
    if not a.quick:
        check_rerun(O.build_context(mkt))
    if a.json:
        Path(a.json).write_text(json.dumps(OUT, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
