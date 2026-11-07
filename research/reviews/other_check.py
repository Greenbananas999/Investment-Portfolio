"""Adversarial review of the other-sleeve analysis (research/candidates/other_sleeve.py).

    python -m research.reviews.other_check            # print every check
    python -m research.reviews.other_check --json PATH  # also dump the numbers

Independent of the analyst's helpers wherever possible: returns are rebuilt
from data/research/prices.csv with plain pandas (month-end last price,
pct_change, partial final month dropped), statistics are written out here,
and the analyst's JSON / control CSV are only read to compare against.
Nothing under data/, research/candidates/, research/screen/ or reports/candidates/*.json is written.
"""

import argparse
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

from ..screen.prices import read_wide_csv

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research"
REP = ROOT / "reports" / "candidates"
MEMOS = ROOT / "research" / "candidates" / "memos"
IDS = ["IAU", "SLV", "GSG", "GNR", "VNQI", "IGF", "SCHP", "WIP"]
BENCH = ["GLD", "BIL", "ACWX", "EMB"]
IS_A, IS_B, OOS_A, OOS_B = "2010-01-31", "2017-12-31", "2018-01-31", "2026-10-31"
W22 = ("2021-12-31", "2022-10-31")
TOL = 0.005
OUT = {}


def section(t):
    print("\n" + "=" * 100 + "\n" + t + "\n" + "=" * 100)


# ------------------------------------------------------------------ independent stats
def monthly(daily):
    m = daily.resample("ME").last()
    r = m.pct_change(fill_method=None)
    last = daily.dropna(how="all").index.max()
    if last < last + pd.offsets.BMonthEnd(0):      # partial final month
        r = r.iloc[:-1]
    return r.iloc[1:]


def sharpe(r, rf):
    ex = (r - rf).dropna()
    return float(ex.mean() / ex.std(ddof=1) * math.sqrt(12))


def ir(r, b):
    a = (r - b).dropna()
    return float(a.mean() / a.std(ddof=1) * math.sqrt(12)), float(a.std(ddof=1) * math.sqrt(12)), len(a)


def maxdd(r, include_start=True):
    w = (1 + r.dropna()).cumprod()
    if include_start:
        w = pd.concat([pd.Series([1.0], index=[w.index[0] - pd.offsets.MonthEnd(1)]), w])
    return float((w / w.cummax() - 1).min())


def wret(r, a, b):
    x = r[(r.index > pd.Timestamp(a)) & (r.index <= pd.Timestamp(b))]
    return float((1 + x).prod() - 1), len(x)


def ols(y, x, hac_lags=3):
    """Slope, OLS t, Newey-West t (Bartlett, hac_lags), n."""
    d = pd.concat([y, x], axis=1).dropna()
    yy, xx = d.iloc[:, 0].to_numpy(), d.iloc[:, 1].to_numpy()
    X = np.column_stack([np.ones_like(xx), xx])
    b = np.linalg.lstsq(X, yy, rcond=None)[0]
    e = yy - X @ b
    n = len(yy)
    XtXi = np.linalg.inv(X.T @ X)
    se = math.sqrt((e @ e) / (n - 2) * XtXi[1, 1])
    S = (X * e[:, None]).T @ (X * e[:, None])
    for L in range(1, hac_lags + 1):
        w = 1 - L / (hac_lags + 1)
        G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None])
        S += w * (G + G.T)
    V = XtXi @ S @ XtXi
    return float(b[1]), float(b[1] / se), float(b[1] / math.sqrt(V[1, 1])), n


def dsr(sh_ann, n_trials, T, skew, kurt, v=None):
    sr = sh_ann / math.sqrt(12)
    v = 1 / (T - 1) if v is None else v
    g = 0.5772156649015329
    z = sps.norm.ppf
    sr0 = math.sqrt(v) * ((1 - g) * z(1 - 1 / n_trials) + g * z(1 - 1 / (n_trials * math.e)))
    den = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    return float(sps.norm.cdf((sr - sr0) * math.sqrt(T - 1) / math.sqrt(den))), sr0 * math.sqrt(12)


def flag(ok):
    return "PASS" if ok else "FAIL"


# ------------------------------------------------------------------ load
def load():
    ctl = pd.read_csv(REP / "other_control.csv")
    tick = sorted(set(ctl["ticker"]) | set(IDS) | set(BENCH))
    head = pd.read_csv(DATA / "prices.csv", nrows=0).columns
    keep = [head[0]] + [c for c in head[1:] if c in set(tick)]
    raw = pd.read_csv(DATA / "prices.csv", index_col=0, parse_dates=True, usecols=keep).sort_index()
    raw = raw[~raw.index.duplicated(keep="last")].apply(pd.to_numeric, errors="coerce")
    cleaned = read_wide_csv(DATA / "prices.csv", columns=tick)
    y = pd.read_csv(DATA / "yields.csv", index_col=0, parse_dates=True)
    js = {t: json.loads((REP / f"{t}.json").read_text(encoding="utf-8")) for t in IDS}
    return monthly(raw), monthly(cleaned), y, js, ctl


def cpi_month_end(y):
    c = y["US_CPI"].dropna().copy()
    c.index = c.index + pd.offsets.MonthEnd(0)
    return c.groupby(level=0).last()


# ------------------------------------------------------------------ checks
def check_reproduce(mr, mc, js):
    section("1. Independent recompute (raw prices.csv, no spike filter; and read_wide_csv) vs analyst JSON")
    rows = []
    for t in IDS:
        for lab, m in (("raw", mr), ("read_wide_csv", mc)):
            r = m[t].loc[OOS_A:OOS_B].dropna()
            rf = m["BIL"].reindex(r.index)
            s = sharpe(r, rf)
            i, te, n = ir(r, m["GLD"].reindex(r.index))
            dd0, dd1 = maxdd(r, False), maxdd(r, True)
            o = js[t]["metrics"]["out_of_sample"]["usd"]
            rows.append(dict(ticker=t, src=lab, months=len(r), sharpe=s, sharpe_json=o["sharpe"], ir_gld=i, ir_json=o.get("info_ratio"),
                             te_gld=te, maxdd=dd0, maxdd_with_start=dd1, maxdd_json=o["max_drawdown"]))
    df = pd.DataFrame(rows)
    print(df.round(4).to_string(index=False))
    c = df[df.src == "read_wide_csv"]
    ok_s = (c.sharpe - c.sharpe_json).abs().max()
    ok_d = (c.maxdd - c.maxdd_json).abs().max()
    ok_i = (c.ir_gld - c.ir_json.astype(float)).abs().max(skipna=True)
    print(f"max |diff| vs JSON (read_wide_csv): Sharpe {ok_s:.2e}, IR {ok_i:.2e}, maxDD {ok_d:.2e} -> {flag(max(ok_s, ok_d, ok_i) < TOL)}")
    rr = df[df.src == "raw"]
    print(f"raw (no spike filter) max |diff|: Sharpe {(rr.sharpe - rr.sharpe_json).abs().max():.2e}, maxDD {(rr.maxdd - rr.maxdd_json).abs().max():.2e}")
    print(f"maxDD including the starting wealth point differs by up to {(df.maxdd_with_start - df.maxdd).abs().max():.2e}")
    OUT["recompute"] = df.to_dict("records")

    print("\n2022 shock (2021-12-31, 2022-10-31], stress returns:")
    for t in ["IAU", "GSG", "VNQI", "SCHP", "SLV", "GNR", "IGF", "WIP"]:
        v, n = wret(mc[t], *W22)
        j = js[t]["diversification"]["return_2021_12_to_2022_10"]
        print(f"  {t:5s} {v:+.4f} ({n} months) JSON {j:+.4f} {flag(abs(v - j) < TOL)}")
    g, _ = wret(mc["GLD"], *W22)
    print(f"  GLD   {g:+.4f}")
    OUT["ret_2022"] = {t: wret(mc[t], *W22)[0] for t in IDS + ["GLD"]}

    print("\nOOS correlations (months 2018-01..2026-10):")
    OUT["corr"] = {}
    for t in ["GSG", "GNR", "IGF", "IAU"]:
        r = mc[t].loc[OOS_A:OOS_B]
        ca = r.corr(mc["ACWX"].loc[OOS_A:OOS_B]); ce = r.corr(mc["EMB"].loc[OOS_A:OOS_B]); cg = r.corr(mc["GLD"].loc[OOS_A:OOS_B])
        jc = js[t]["diversification"]["oos_correlation"]
        print(f"  {t:5s} ACWX {ca:.3f} (JSON {jc['ACWX']:.3f})  EMB {ce:.3f} (JSON {jc['EMB']:.3f})  GLD {cg:.3f} (JSON {jc['GLD']:.3f})")
        OUT["corr"][t] = dict(ACWX=ca, EMB=ce, GLD=cg)

    # IAU vs GLD: what the nulled IR would have been
    r = mc["IAU"].loc[OOS_A:OOS_B]
    i, te, n = ir(r, mc["GLD"].reindex(r.index))
    print(f"\nIAU vs GLD OOS (nulled in JSON): IR {i:.2f}, tracking error {te:.4%}, active mean {(r - mc['GLD']).loc[OOS_A:OOS_B].mean() * 12:.4%}/yr "
          "-> pure fee difference; nulling it in the JSON is correct, but other_control.csv still carries IAU 0.507 / SGOL 0.471")
    OUT["iau_vs_gld"] = dict(ir=i, te=te)


def check_benchmarks(mc, y, js):
    section("3. Alternative benchmarks rebuilt independently: GUIDE_BENCH (55 ACWX / 35 EMB / 10 GLD, quarterly) and CPI+2%")
    df = mc[["ACWX", "EMB", "GLD"]].dropna()
    w0 = np.array([0.55, 0.35, 0.10]); w = w0.copy(); out = []
    for dt, row in df.iterrows():
        p = float(w @ row.to_numpy()); out.append(p)
        w = w * (1 + row.to_numpy()) / (1 + p)
        if dt.month % 3 == 0:
            w = w0.copy()
    gb = pd.Series(out, index=df.index)
    c = cpi_month_end(y)
    cp2 = (1 + c.pct_change(fill_method=None)) * 1.02 ** (1 / 12) - 1
    OUT["alt_bench"] = {}
    for t in ["IAU", "GSG", "SCHP"]:
        r = mc[t].loc[OOS_A:OOS_B]
        a = ir(r, gb.reindex(r.index))[0]
        b, _, n = ir(r, cp2.reindex(r.index))
        ja = js[t]["alt_benchmarks"]["GUIDE_BENCH"]["out_of_sample"]["info_ratio"]
        jb = js[t]["alt_benchmarks"]["CPI_PLUS_2"]["out_of_sample"]["info_ratio"]
        print(f"   {t:5s} IR vs GUIDE_BENCH {a:+.3f} (JSON {ja:+.3f}) {flag(abs(a - ja) < TOL)} | IR vs CPI+2% {b:+.3f} over {n} months (JSON {jb:+.3f}) {flag(abs(b - jb) < TOL)}")
        OUT["alt_bench"][t] = dict(guide=a, cpi2=b)
    print("   CPI+2% (and every inflation beta) loses October 2026 (CPI not yet published) and any month with a missing CPI print in yields.csv, so the OOS IR uses 104 of 106 months.")


def check_inflation(mc, y, js):
    section("2. Inflation beta: implementation, timing, alternative definitions, IS and OOS, with t-stats")
    c = cpi_month_end(y)
    yoy = c / c.shift(12) - 1
    mom = c.pct_change(fill_method=None)
    defs = {
        "analyst: d(YoY), same month": yoy.diff(),
        "d(YoY), CPI of t vs return of t+1 (release month)": yoy.diff().shift(1),
        "m/m inflation, same month": mom,
        "m/m surprise = m/m minus its trailing 12m mean": mom - mom.rolling(12).mean().shift(1),
        "m/m surprise, release month (t+1)": (mom - mom.rolling(12).mean().shift(1)).shift(1),
        "YoY level, same month": yoy,
    }
    print("CPI index row dated 2026-09-01 is mapped to 2026-09-30 and paired with the September return; the September CPI is "
          "released mid-October. So the analyst's regression is contemporaneous with the reference month (the economically "
          "right pairing for 'does it move with inflation'), not with the information date. Both are shown.")
    res = {}
    for t in ["IAU", "SLV", "GSG", "SCHP", "WIP", "GNR", "IGF", "VNQI"]:
        res[t] = {}
        for w, (a, b) in (("IS", (IS_A, IS_B)), ("OOS", (OOS_A, OOS_B))):
            r = mc[t].loc[a:b]
            for k, x in defs.items():
                beta, t_ols, t_nw, n = ols(r, x.reindex(r.index))
                res[t][f"{w} | {k}"] = dict(beta=beta, t_ols=t_ols, t_nw=t_nw, n=n)
    for t in ["IAU", "SLV", "GSG", "SCHP"]:
        print(f"\n{t}  (JSON: IS {js[t]['diversification']['inflation_beta_in_sample']:+.3f}, OOS {js[t]['diversification']['inflation_beta_oos']:+.3f})")
        for k, v in res[t].items():
            print(f"   {k:62s} beta {v['beta']:+8.3f}  t {v['t_ols']:+5.2f}  NW t {v['t_nw']:+5.2f}  n {v['n']}")
    OUT["inflation_beta"] = res
    # full-history gold (GLD from 2004-12) for robustness
    r = mc["GLD"].dropna()
    for k in ("analyst: d(YoY), same month", "m/m surprise = m/m minus its trailing 12m mean", "YoY level, same month"):
        beta, t1, t2, n = ols(r, defs[k].reindex(r.index))
        print(f"GLD full history {k:52s} beta {beta:+.3f} t {t1:+.2f} NW t {t2:+.2f} n {n}")
    # annual frequency: calendar-year gold return vs calendar-year CPI inflation
    ann = (1 + mc["GLD"]).groupby(mc["GLD"].index.year).prod() - 1
    cy = c.groupby(c.index.year).last()
    infl = (cy / cy.shift(1) - 1)
    d = pd.concat([ann, infl], axis=1).dropna()
    d = d[(d.index >= 2005) & (d.index <= 2025)]
    rho = d.corr().iloc[0, 1]
    print(f"GLD calendar-year return vs calendar-year CPI inflation 2005-2025: corr {rho:+.2f} (n {len(d)} years)")
    OUT["gld_annual_corr_cpi"] = float(rho)


def check_dropping(mc, js, ctl):
    section("4. Drop rule 8.2 (OOS Sharpe below GLD's AND OOS IR vs GLD below zero)")
    r_g = mc["GLD"].loc[OOS_A:OOS_B]
    sg = sharpe(r_g, mc["BIL"].reindex(r_g.index))
    print(f"GLD OOS Sharpe recomputed {sg:.3f}")
    rows = []
    for t in IDS:
        r = mc[t].loc[OOS_A:OOS_B]
        s = sharpe(r, mc["BIL"].reindex(r.index))
        i = None if t == "IAU" else ir(r, mc["GLD"].reindex(r.index))[0]
        drop = (s < sg) and (i is not None and i < 0)
        rows.append(dict(ticker=t, sharpe=round(s, 3), ir_gld=None if i is None else round(i, 3), drop=drop))
    d = pd.DataFrame(rows)
    print(d.to_string(index=False))
    c = ctl.copy()
    c["surv"] = (c.sharpe_oos >= sg) | (c.ir_vs_gld_oos > 0)
    surv = c.loc[c.surv & (c.ticker != "GLD"), "ticker"].tolist()
    print(f"Survivors of 8.2 across the 33-fund long list (excluding GLD itself): {surv} ({len(surv)})")
    print("Under a long-list reading the type has >= 5 survivors, so the six dropped shortlist funds may NOT remain runners-up; "
          "the memos' 'runner-up at best' uses the lenient shortlist reading (2 survivors of 8). Every survivor is precious metal "
          "or IGE (IR +0.01).")
    OUT["drop_rule"] = dict(gld_sharpe=sg, table=rows, longlist_survivors=surv)


def check_expected(y, mc, js):
    section("5. Expected-return models recomputed from yields.csv / funds.csv")
    f = pd.read_csv(DATA / "funds.csv").set_index("ticker")
    lv = lambda col: float(y[col].dropna().iloc[-1]) / 100
    real10, be10, rf = lv("US_REAL10"), lv("US_BE10"), lv("US_3M")
    drift = float(y["US_REAL10"].dropna().mean()) / 100
    gold = (1 + (-real10 + drift)) * (1 + be10) - 1
    j = js["IAU"]["expected_return_7y"]
    print(f"inputs: US_REAL10 {real10:.2%} (row {y['US_REAL10'].dropna().index[-1].date()}), US_BE10 {be10:.2%}, US_3M {rf:.2%}, drift {drift:.3%}")
    print(f"IAU real_yield_model = (1 - {real10:.2%} + {drift:.2%})(1 + {be10:.2%}) - 1 = {gold:.4f} (JSON {j['methods']['real_yield_model']:.4f}) -> the 0.6% one")
    print(f"IAU historical_real_plus_breakeven JSON {j['methods']['historical_real_plus_breakeven']:.4f} (history window {j['inputs']['history']['window']}, "
          f"real CAGR {j['inputs']['history']['real_cagr']:.2%}) -> the 10.0% one; consensus = mean = "
          f"{(j['methods']['real_yield_model'] + j['methods']['historical_real_plus_breakeven']) / 2:.4f} (JSON {j['consensus_usd']:.4f})")
    # back-test of the gold real-yield model: prediction at t (drift from data to t only) vs realised 7y GLD
    ry = y["US_REAL10"].dropna(); ry.index = ry.index + pd.offsets.MonthEnd(0)
    be = y["US_BE10"].dropna(); be.index = be.index + pd.offsets.MonthEnd(0)
    g = mc["GLD"].dropna()
    lvl = (1 + g).cumprod()
    pr, rl, dt = [], [], []
    for t0 in lvl.index:
        t1 = t0 + pd.offsets.MonthEnd(84)
        if t1 not in lvl.index or t0 not in ry.index or t0 < pd.Timestamp("2006-01-31"):
            continue
        d_t = ry.loc[:t0].mean() / 100
        pr.append((1 - ry.loc[t0] / 100 + d_t) * (1 + be.loc[t0] / 100) - 1)
        rl.append((lvl.loc[t1] / lvl.loc[t0]) ** (1 / 7) - 1)
        dt.append(t0)
    bt = pd.DataFrame({"pred": pr, "real": rl}, index=dt)
    rho = bt.corr().iloc[0, 1]
    print(f"Gold real-yield model back-test, start months {bt.index[0].date()}..{bt.index[-1].date()} (n {len(bt)}, heavily overlapping): "
          f"corr(pred, realised 7y GLD CAGR) {rho:+.2f}; mean pred {bt.pred.mean():.2%} vs mean realised {bt.real.mean():.2%}; "
          f"mean error {(bt.real - bt.pred).mean():+.2%}")
    oos = mc["GLD"].loc[OOS_A:OOS_B]
    dry = ry.diff().reindex(oos.index) / 100
    b, t1, t2, n = ols(oos, dry)
    print(f"GLD OOS monthly return on monthly change in US_REAL10: slope {b:+.2f} (t {t1:+.2f}, NW {t2:+.2f}); real10 rose "
          f"{ry.loc['2021-12-31'] :.2f} -> {ry.iloc[-1]:.2f} while GLD compounded {lvl.iloc[-1] / lvl.loc['2021-12-31'] - 1:+.0%}")
    OUT["gold_model"] = dict(value=gold, backtest_corr=float(rho), mean_pred=float(bt.pred.mean()), mean_real=float(bt.real.mean()))

    # GSG
    gs = js["GSG"]["expected_return_7y"]
    col = rf + (-0.01) + be10 + 0.0 - float(f.loc["GSG", "expense_ratio"])
    r = mc["GSG"].dropna()
    bil = mc["BIL"].reindex(r.index)
    cg = (1 + r).prod() ** (12 / len(r)) - 1
    cb = (1 + bil.dropna()).prod() ** (12 / bil.notna().sum()) - 1
    c = cpi_month_end(y)
    ci = c.reindex(r.index).dropna()
    cpi_cagr = (ci.iloc[-1] / c.loc[:r.index[0] - pd.offsets.MonthEnd(1)].iloc[-1]) ** (12 / len(ci)) - 1
    implied_roll = cg - cb - cpi_cagr
    print(f"\nGSG collateral_roll_spot = {rf:.2%} - 1.00% + {be10:.2%} - {f.loc['GSG', 'expense_ratio']:.2%} = {col:.4f} (JSON {gs['methods']['collateral_roll_spot']:.4f})")
    print(f"GSG realised {r.index[0].date()}..{r.index[-1].date()}: CAGR {cg:.2%}, BIL {cb:.2%}, CPI {cpi_cagr:.2%} -> "
          f"implied roll + real spot + fee drag {implied_roll:+.2%}/yr vs the assumed roll -1.0% and real spot 0% (fee is already in the NAV)")
    print(f"GSG consensus {gs['consensus_usd']:.4f} = mean(collateral model {gs['methods']['collateral_roll_spot']:.4f}, history {gs['methods']['historical_real_plus_breakeven']:.4f})")
    OUT["gsg"] = dict(model=col, realised_cagr=cg, bil=cb, cpi=cpi_cagr, implied_drag=implied_roll)

    # GK / CAPM for GNR IGF VNQI
    g = {"GNR": 0.010, "IGF": 0.015, "VNQI": 0.005}
    for t in ["GNR", "IGF", "VNQI"]:
        e = js[t]["expected_return_7y"]
        gk = float(f.loc[t, "yield"]) + be10 + g[t]
        b = e["inputs"]["beta_acwi"]
        capm = rf + b * 0.045
        print(f"{t}: GK {float(f.loc[t, 'yield']):.2%} + {be10:.2%} + {g[t]:.1%} = {gk:.4f} (JSON {e['methods']['grinold_kroner']:.4f}); "
              f"CAPM {rf:.2%} + {b:.2f} x 4.5% = {capm:.4f} (JSON {e['methods']['capm']:.4f}); historical {e['methods']['historical']:.4f} (not in consensus)")
    # TIPS
    e = js["SCHP"]["expected_return_7y"]
    print(f"\nSCHP real10 + be10 - fee = {real10 + be10 - 0.0003:.4f} (JSON {e['methods']['real_yield_plus_breakeven']:.4f}); this equals the nominal "
          f"10y Treasury yield ({lv('US_10Y'):.2%}) minus fee; second method fund trailing yield {float(f.loc['SCHP', 'yield']):.4f} is realised "
          "past CPI accrual, not a forecast, but is averaged into the consensus")
    # WIP
    e = js["WIP"]["expected_return_7y"]
    w = {"GB": 18.36 / 26.35, "BR": 7.99 / 26.35}
    tot = 0
    for k in w:
        nom, cp = lv(f"{k}_10Y"), lv(f"{k}_CPIYOY")
        ppp = (1 + be10) / (1 + cp) - 1
        tot += w[k] * ((nom - cp) + cp + ppp)
        print(f"  WIP {k}: weight {w[k]:.3f}, nominal 10Y {nom:.2%}, CPI {cp:.2%}, PPP FX {ppp:+.2%}; real + CPI = nominal exactly")
    print(f"WIP model = {tot - 0.005:.4f} (JSON {e['methods']['country_real_yield_plus_inflation_ppp']:.4f}): the 'real yield' term cancels, so this is a "
          f"NOMINAL-bond yield plus PPP FX on 26% of the fund, with Brazil at {w['BR']:.0%} instead of 8%")
    OUT["wip"] = tot - 0.005

    # Monte Carlo
    print("\nMonte Carlo: forward MC is scaled to the consensus and is NOT averaged into it (other_sleeve.py lines 294-302): no double "
          "count, but its 5-95 range is a bootstrap of the fund's own history at the consensus drift, so it carries no model uncertainty.")


def check_controls(ctl, mc):
    section("7. Control table rank tests, near-duplicate clustering, deflated Sharpe")
    s = ctl.set_index("ticker").copy()
    s.loc["GLD", "ir_vs_gld_oos"] = np.nan
    s.loc["BIL", ["sharpe_is", "sharpe_oos"]] = np.nan

    def sp(a, b, df):
        d = df[[a, b]].dropna()
        rho, p = sps.spearmanr(d[a], d[b])
        return float(rho), float(p), len(d)

    tests = {"composite_is vs sharpe_oos": ("composite_is", "sharpe_oos"),
             "composite_is vs ir_vs_gld_oos": ("composite_is", "ir_vs_gld_oos"),
             "fundamental_score_is vs sharpe_oos": ("fundamental_score_is", "sharpe_oos"),
             "sharpe_is vs sharpe_oos": ("sharpe_is", "sharpe_oos")}
    out = {}
    for k, (a, b) in tests.items():
        r1 = sp(a, b, s)
        cat = s.groupby("category")[[a, b]].mean()
        r2 = sp(a, b, cat)
        s2 = s.drop(index=["IAU", "SGOL"]) if b == "ir_vs_gld_oos" else s
        r3 = sp(a, b, s2)
        out[k] = dict(all=r1, category_means=r2, excl_gold_clones=r3)
        print(f"{k:40s} all funds rho {r1[0]:+.3f} p {r1[1]:.4f} n {r1[2]} | category means rho {r2[0]:+.3f} p {r2[1]:.3f} n {r2[2]}"
              + (f" | without IAU/SGOL fee-artefact IRs rho {r3[0]:+.3f} p {r3[1]:.3f}" if b == "ir_vs_gld_oos" else ""))
    print("Categories: tips_us 8 funds, natural_resources 4, precious_basket 4 ... near-duplicates inflate n and shrink p.")
    sc = pd.read_csv(ROOT / "research" / "plan" / "longlists" / "other_scored.csv").set_index("ticker")
    s = s.join(sc[["inflation_score", "correlation_score", "cost_score"]], how="left")
    for comp in ["inflation_score", "correlation_score", "cost_score"]:
        r = sp(comp, "sharpe_oos", s)
        print(f"   component {comp:18s} vs OOS Sharpe rho {r[0]:+.3f} p {r[1]:.3f} n {r[2]}")
        out[f"component_{comp}"] = r
    print("   fundamental score's cost component uses TODAY's expense ratio (other_scored.csv flag 'AUM is the latest figure'): mild look-ahead")
    OUT["rank_tests"] = out

    # deflated Sharpe: own formula, and with the measured cross-sectional variance of the trials' OOS Sharpe
    sh = s["sharpe_oos"].dropna()
    v_meas = float(np.var(sh / math.sqrt(12), ddof=1))
    T = 106
    print(f"\nDeflated Sharpe, T={T}, N=33; V=1/(T-1)={1 / (T - 1):.5f} vs measured V across the 32 OOS Sharpes {v_meas:.5f}")
    for t in ["IAU", "SLV", "GSG"]:
        r = mc[t].loc[OOS_A:OOS_B]
        shr = sharpe(r, mc["BIL"].reindex(r.index))
        a, sr0a = dsr(shr, 33, len(r), float(r.skew()), float(r.kurt()) + 3)
        b, sr0b = dsr(shr, 33, len(r), float(r.skew()), float(r.kurt()) + 3, v_meas)
        tt = shr / math.sqrt(12) * math.sqrt(len(r))
        print(f"   {t}: Sharpe {shr:.3f}, t(mean excess) {tt:.2f}; DSR null-V {a:.3f} (SR0 {sr0a:.2f}); DSR measured-V {b:.3f} (SR0 {sr0b:.2f})")
        OUT.setdefault("dsr", {})[t] = dict(sharpe=shr, t=tt, dsr_null=a, dsr_measured=b)


def check_memos(js):
    section("8. Memo 'How to explain this pick' sentences vs JSON")
    for t in IDS:
        txt = (MEMOS / f"{t}.md").read_text(encoding="utf-8")
        exp = txt.split("**How to explain this pick.**")[1]
        o = js[t]["metrics"]["out_of_sample"]["usd"]
        sh = float(re.search(r"Sharpe of (-?[\d.]+)", exp).group(1))
        dd = float(re.search(r"worst drawdown of (-?\d+)%", exp).group(1)) / 100
        ac = float(re.search(r"correlate (-?[\d.]+) with", exp).group(1))
        ok = abs(sh - o["sharpe"]) < 0.006 and abs(dd - o["max_drawdown"]) < 0.006 and abs(ac - js[t]["diversification"]["oos_correlation"]["ACWX"]) < 0.006
        infl = "inflation" in exp.lower()
        print(f"   {t:5s} Sharpe {sh} / DD {dd:.2f} / ACWX {ac} match JSON: {flag(ok)}")
    print("   ROLE strings (other_sleeve.py lines 533-542) are hard-coded text, not data: IAU 'simplest inflation ... diversifier' "
          "vs its own inflation beta -1.1 and 2022 return -11%; WIP 'inflation protection' vs 2022 -19.9%; IGF 'partly inflation-linked tariffs' vs 2022 -6.1%.")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    mr, mc, y, js, ctl = load()
    check_reproduce(mr, mc, js)
    check_benchmarks(mc, y, js)
    check_inflation(mc, y, js)
    check_dropping(mc, js, ctl)
    check_expected(y, mc, js)
    check_controls(ctl, mc)
    check_memos(js)
    if a.json:
        Path(a.json).write_text(json.dumps(OUT, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
