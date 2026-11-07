"""Adversarial review of the Phase 3 EM bond fund analysis (research/candidates/em_bonds.py).

    python -m research.reviews.em_bonds_check            # print every check
    python -m research.reviews.em_bonds_check --json out.json   # also dump the numbers

Recomputes the analyst's headline numbers with independent code (own month-end
returns, own Sharpe/IR/drawdown/deflated Sharpe, own GUIDE_BENCH, own currency
decomposition and CIP hedge, own country real yields) from data/research/ and
compares them with reports/candidates/<ID>.json. Reads only; writes nothing
unless --json is given. Imports the analyst's module only where a check is
about that module's behaviour (fee double count, Monte Carlo anchoring), and
says so.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

from research.screen.prices import read_wide_csv
from research.candidates import assumptions_em_bonds as A

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research"
LL = ROOT / "research" / "plan" / "longlists"
REP = ROOT / "reports" / "candidates"
IS_START, IS_END, OOS_START, OOS_END = "2010-01-01", "2017-12-31", "2018-01-31", "2026-10-31"
FUNDS = A.CANDIDATES
OUT = {}


def say(*a):
    print(*a)


def jload(t):
    return json.loads((REP / f"{t}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Independent statistics
# ---------------------------------------------------------------------------
def month_end_returns(cols):
    p = read_wide_csv(DATA / "prices.csv", columns=cols)
    m = p.resample("ME").last()
    r = m.pct_change(fill_method=None)
    return r.loc[: OOS_END]          # Nov 2026 is partial: stop at the last full month


def sharpe(r, rf):
    ex = (r - rf.reindex(r.index)).dropna()
    return ex.mean() / ex.std(ddof=1) * math.sqrt(12)


def ir(r, b):
    a = (r - b.reindex(r.index)).dropna()
    return a.mean() / a.std(ddof=1) * math.sqrt(12), len(a)


def maxdd(r, include_first=True):
    """Drawdown of the growth path; include_first adds the starting level 1.0 so a
    loss in the first month counts (the analyst's research.metrics.max_drawdown does not)."""
    w = (1 + r.dropna()).cumprod()
    if include_first:
        w = pd.concat([pd.Series([1.0]), w.reset_index(drop=True)])
    return float((w / w.cummax() - 1).min())


def dsr(sr_annual, n_trials, r):
    """Bailey-Lopez de Prado deflated Sharpe, V = 1/(T-1) (method.md change log)."""
    T = len(r)
    sr = sr_annual / math.sqrt(12)
    v = 1 / (T - 1)
    g = 0.5772156649015329
    sr0 = math.sqrt(v) * ((1 - g) * sps.norm.ppf(1 - 1 / n_trials) + g * sps.norm.ppf(1 - 1 / (n_trials * math.e)))
    sk, ku = float(r.skew()), float(r.kurt()) + 3
    return float(sps.norm.cdf((sr - sr0) * math.sqrt(T - 1) / math.sqrt(1 - sk * sr + (ku - 1) / 4 * sr ** 2)))


def guide_bench_holdings(M, w, months_between=3):
    """55/35/10 portfolio held as units, weights reset after every quarter-end month
    (Mar, Jun, Sep, Dec); months_between=1 gives monthly rebalancing."""
    R = M[list(w)].dropna()
    vals = None
    out = []
    for i, (d, row) in enumerate(R.iterrows()):
        if vals is None or (months_between == 3 and d.month in (1, 4, 7, 10)) or months_between == 1:
            tot = 1.0 if vals is None else sum(vals.values())
            vals = {k: tot * w[k] for k in w}
        before = sum(vals.values())
        vals = {k: v * (1 + row[k]) for k, v in vals.items()}
        out.append(sum(vals.values()) / before - 1)
    return pd.Series(out, index=R.index)


def cagr(r):
    r = r.dropna()
    return float((1 + r).prod() ** (12 / len(r)) - 1)


# ---------------------------------------------------------------------------
# 1. Reproduce OOS metrics and stress
# ---------------------------------------------------------------------------
def check_metrics(M):
    rf = M["BIL"]
    gb_q = guide_bench_holdings(M, A.GUIDE_BENCH, 3)
    gb_m = guide_bench_holdings(M, A.GUIDE_BENCH, 1)
    benches = {"EMB": M["EMB"], "EMLC": M["EMLC"], "GUIDE_BENCH": gb_q}
    rows = {}
    for t in FUNDS:
        d = jload(t)
        r = M[t].loc[OOS_START:OOS_END].dropna()
        b = benches[A.BENCHMARK[t]]
        sh = sharpe(r, rf)
        i, n = ir(r, b)
        o = d["metrics"]["out_of_sample"]["usd"]
        rows[t] = {"months": len(r), "sharpe": sh, "sharpe_json": o["sharpe"], "ir": i, "ir_json": o["info_ratio"],
                   "t_ir": i * math.sqrt(n / 12), "maxdd_incl_first": maxdd(r, True), "maxdd_excl_first": maxdd(r, False),
                   "maxdd_json": o["max_drawdown"], "dsr": dsr(sh, 20, r), "dsr_json": o["deflated_sharpe"],
                   "ir_vs_emb": ir(r, M["EMB"])[0], "ir_vs_emlc": ir(r, M["EMLC"])[0]}
    # benchmarks themselves
    for name, s in (("EMB", M["EMB"]), ("EMLC", M["EMLC"]), ("GUIDE_BENCH_q", gb_q), ("GUIDE_BENCH_m", gb_m)):
        r = s.loc[OOS_START:OOS_END].dropna()
        rows[name + "_bench"] = {"months": len(r), "sharpe": sharpe(r, rf), "maxdd_incl_first": maxdd(r, True),
                                 "cagr": cagr(r), "dsr": dsr(sharpe(r, rf), 20, r)}
    # EMB vs GUIDE_BENCH with quarterly vs monthly rebalancing
    r = M["EMB"].loc[OOS_START:OOS_END]
    rows["EMB_vs_GB"] = {"quarterly": ir(r, gb_q)[0], "monthly": ir(r, gb_m)[0],
                         "t_quarterly": ir(r, gb_q)[0] * math.sqrt(106 / 12),
                         "te_quarterly": float((r - gb_q.reindex(r.index)).std() * math.sqrt(12))}
    # analyst's guide_bench vs mine
    from research.candidates.em_bonds import guide_bench
    g_an = guide_bench(M)
    rows["guide_bench_maxabsdiff_vs_analyst"] = float((g_an - gb_q).abs().max())
    say("\n== 1. OOS metrics (own month-end returns; 2018-01..2026-10) ==")
    for t in FUNDS:
        x = rows[t]
        say(f"{t:6s} n={x['months']} Sharpe {x['sharpe']:.4f} (json {x['sharpe_json']:.4f})  IR {x['ir']:.4f} "
            f"(json {x['ir_json']:.4f}, t {x['t_ir']:.2f})  maxDD incl-first {x['maxdd_incl_first']:.4f} "
            f"excl {x['maxdd_excl_first']:.4f} (json {x['maxdd_json']:.4f})  DSR {x['dsr']:.4f} (json {x['dsr_json']:.4f})")
    for k in ("EMB_bench", "EMLC_bench", "GUIDE_BENCH_q_bench", "GUIDE_BENCH_m_bench"):
        x = rows[k]
        say(f"{k:20s} Sharpe {x['sharpe']:.4f} CAGR {x['cagr']:.4f} maxDD {x['maxdd_incl_first']:.4f} DSR {x['dsr']:.4f}")
    say(f"EMB IR vs GUIDE_BENCH: quarterly {rows['EMB_vs_GB']['quarterly']:.4f} (t {rows['EMB_vs_GB']['t_quarterly']:.2f}, "
        f"TE {rows['EMB_vs_GB']['te_quarterly']:.3f}); monthly-rebalanced {rows['EMB_vs_GB']['monthly']:.4f}")
    say(f"analyst guide_bench vs my unit-holding version, max |diff| = {rows['guide_bench_maxabsdiff_vs_analyst']:.2e}")
    # stress
    st = {}
    for t, k in (("HYEM", "covid_2020"), ("PCY", "inflation_2022"), ("TGEIX", "covid_2020"), ("EMLC", "inflation_2022")):
        s, e = A.STRESS[k]
        r = M[t].loc[pd.Timestamp(s) + pd.Timedelta(days=1): e]
        st[f"{t}_{k}"] = {"mine": float((1 + r).prod() - 1), "json": jload(t)["stress"][k]["return"]}
    covid = {t: float((1 + M[t].loc["2020-02-01":"2020-03-31"]).prod() - 1) for t in FUNDS}
    st["covid_rank_worst_first"] = sorted(covid.items(), key=lambda kv: kv[1])
    say("stress:", {k: v for k, v in st.items() if k != "covid_rank_worst_first"})
    say("Covid 2020 worst first:", [(k, round(v, 4)) for k, v in st["covid_rank_worst_first"]])
    rows["stress"] = st
    OUT["metrics"] = rows
    return benches


# ---------------------------------------------------------------------------
# 1b. Rolling consistency: how many OOS rolling windows are fully OOS
# ---------------------------------------------------------------------------
def check_rolling(M):
    res = {}
    for t in FUNDS:
        b = M["EMB"] if A.BENCHMARK[t] == "EMB" else (M["EMLC"] if A.BENCHMARK[t] == "EMLC" else None)
        if b is None:
            continue
        a = (M[t] - b).loc["2007-06-30":]
        ro = a.rolling(36, min_periods=36)
        roll = (ro.mean() / ro.std()).dropna()
        oos_any = roll.loc[OOS_START:]
        oos_full = roll.loc["2020-12-31":]       # window starts 2018-01 or later
        res[t] = {"share_pos_windows_ending_2018plus": float((oos_any > 0).mean()), "n": len(oos_any),
                  "share_pos_fully_oos": float((oos_full > 0).mean()), "n_fully_oos": len(oos_full),
                  "independent_36m_blocks_oos": round(106 / 36, 1)}
    say("\n== 1b. Rolling 36m IR > 0, windows ending >= 2018-01 vs fully OOS windows (start >= 2018-01) ==")
    for t, x in res.items():
        say(f"{t:6s} any {x['share_pos_windows_ending_2018plus']:.2f} (n {x['n']})  fully-OOS {x['share_pos_fully_oos']:.2f} (n {x['n_fully_oos']})")
    OUT["rolling"] = res


# ---------------------------------------------------------------------------
# 2b. In-sample IR of TGEIX / PEBIX vs EMB and EMLC; corrected composite; control Spearman
# ---------------------------------------------------------------------------
def check_insample_and_control(M):
    rf = M["BIL"]
    ist = pd.read_csv(LL / "em_bond_insample_table.csv").set_index("ticker")
    ll = pd.read_csv(LL / "em_bonds.csv").set_index("ticker")
    res = {}
    for t in ("TGEIX", "PEBIX", "DBLEX", "SHMDX"):
        r = M[t].loc[IS_START:IS_END]
        res[t] = {"ir_vs_emb": ir(r, M["EMB"])[0], "ir_vs_emlc": ir(r, M["EMLC"])[0], "table_ir": float(ist.loc[t, "ir_is"]),
                  "table_benchmark": ist.loc[t, "benchmark"], "category": ll.loc[t, "category"],
                  "word_local_in_notes": "local" in str(ll.loc[t, "notes"]).lower()}
    mis = [t for t in ist.index if ist.loc[t, "benchmark"] == "EMLC" and ll.loc[t, "category"] != "local_sov"]
    say("\n== 2b. Phase 2 benchmark assignment ==")
    say("hard-currency/blend funds the Phase 2 table benchmarked to EMLC:", mis)
    for t, x in res.items():
        say(f"{t:6s} IS IR vs EMB {x['ir_vs_emb']:.3f}  vs EMLC {x['ir_vs_emlc']:.3f}  table {x['table_ir']:.3f} "
            f"({x['table_benchmark']}); 'local' in notes: {x['word_local_in_notes']}")
    # rebuild composite exactly as research/plan/shortlist_table.py, then with corrected IRs
    df = ist.copy()                       # all 20 rows, as shortlist_table.py ranks them
    pct = lambda s: s.rank(pct=True)
    fs = pd.to_numeric(df["fundamental_score"], errors="coerce")
    comp0 = 0.5 * pct(fs).fillna(0.5) + 0.25 * pct(df["sharpe_is"]) + 0.25 * pct(df["ir_is"])
    df2 = df.copy()
    for t in mis:
        df2.loc[t, "ir_is"] = ir(M[t].loc[IS_START:IS_END], M["EMB"])[0]
    comp1 = 0.5 * pct(fs).fillna(0.5) + 0.25 * pct(df2["sharpe_is"]) + 0.25 * pct(df2["ir_is"])
    comp0, comp1 = comp0.dropna(), comp1.dropna()
    rk0, rk1 = comp0.rank(ascending=False), comp1.rank(ascending=False)
    say(f"composite rebuilt, max |diff| vs table {float((comp0 - df['composite'].reindex(comp0.index)).abs().max()):.2e}")
    say("corrected composite rank (old -> new): " + ", ".join(f"{t} {int(rk0[t])}->{int(rk1[t])}" for t in
                                                             comp1.sort_values(ascending=False).index[:12]))
    # control Spearman with the corrected composite
    ctl = pd.read_csv(REP / "em_bonds_control.csv").set_index("ticker")
    a = sps.spearmanr(ctl.loc[comp0.index, "insample_composite"], ctl.loc[comp0.index, "sharpe_oos"])
    b = sps.spearmanr(comp1, ctl.loc[comp1.index, "sharpe_oos"])
    # in-sample-only composite: no fundamental score (it uses 2026 yields, AUM, fees)
    comp_ret = (0.5 * pct(df2["sharpe_is"]) + 0.5 * pct(df2["ir_is"])).dropna()
    c = sps.spearmanr(comp_ret, ctl.loc[comp_ret.index, "sharpe_oos"])
    fsr = sps.spearmanr(fs.reindex(comp0.index), ctl.loc[comp0.index, "sharpe_oos"])
    ir_oos = sps.spearmanr(comp1, ctl.loc[comp1.index, "ir_oos"])
    say(f"Spearman composite vs OOS Sharpe: table {a.statistic:.3f} (p {a.pvalue:.2f}); corrected IR {b.statistic:.3f} "
        f"(p {b.pvalue:.2f}); returns-only (no 2026 fundamentals) {c.statistic:.3f} (p {c.pvalue:.2f}); "
        f"fundamental score alone {fsr.statistic:.3f} (p {fsr.pvalue:.2f}); corrected composite vs OOS IR "
        f"{ir_oos.statistic:.3f} (p {ir_oos.pvalue:.2f}); n={len(comp1)}")
    # control-group funds that beat every shortlisted fund OOS
    sl = ctl.loc[ctl["shortlisted"].astype(str) == "True"]
    better = ctl.loc[(ctl["shortlisted"].astype(str) != "True") & (ctl["sharpe_oos"] > sl["sharpe_oos"].max())]
    say("non-shortlisted funds with OOS Sharpe above the best shortlisted:",
        better[["sharpe_oos", "ir_oos", "maxdd_oos"]].round(3).to_dict("index"))
    sc = pd.read_csv(LL / "em_bond_scored.csv").set_index("ticker")
    inp = pd.read_csv(LL / "em_bond_inputs.csv").set_index("ticker")
    same = all(abs(float(sc.loc[t, "ytm"]) - float(inp.loc[t, "ytm"])) < 1e-9 for t in inp.index if t in sc.index)
    say(f"em_bond_scored.csv ytm equals the 2026-11 em_bond_inputs.csv ytm for every fund: {same}")
    OUT["insample"] = {"funds": res, "mis_benchmarked": mis,
                       "rank_old_new": {t: [int(rk0[t]), int(rk1[t])] for t in comp1.index},
                       "spearman": {"table": [a.statistic, a.pvalue], "corrected_ir": [b.statistic, b.pvalue],
                                    "returns_only": [c.statistic, c.pvalue], "fundamental_only": [fsr.statistic, fsr.pvalue],
                                    "corrected_vs_oos_ir": [ir_oos.statistic, ir_oos.pvalue], "n": len(comp1)},
                       "control_better_than_shortlist": better[["sharpe_oos", "ir_oos", "maxdd_oos"]].to_dict("index"),
                       "fundamental_score_uses_2026_ytm": same}


# ---------------------------------------------------------------------------
# 3. Currency decomposition of EMLC
# ---------------------------------------------------------------------------
def load_rates():
    y = pd.read_csv(DATA / "yields.csv", index_col=0, parse_dates=True).sort_index() / 100.0
    y.index = y.index + pd.offsets.MonthEnd(0)
    return y


def fx_returns(index):
    f = read_wide_csv(DATA / "fx.csv").ffill().resample("ME").last()
    return f.pct_change(fill_method=None).reindex(index), f


def basket(R, w):
    w = pd.Series(w, dtype=float)
    X = R.reindex(columns=w.index)
    W = X.notna().mul(w, axis=1)
    return (X.fillna(0).mul(w, axis=1).sum(axis=1) / W.sum(axis=1)).where(W.sum(axis=1) > 0)


def hedge_series(y, ccys, w, proxy=None):
    """Monthly CIP hedge return per currency, previous month's 3-month rates."""
    us = y["US_3M"].ffill(limit=2).shift(1)
    H = {}
    for c in ccys:
        col = f"{A.CCY_COUNTRY[c]}_3M"
        loc = None
        if col in y and y[col].loc[OOS_START:].notna().any():
            loc = y[col].ffill(limit=2).shift(1)
        elif proxy and c in proxy:
            loc = proxy[c]
        if loc is not None:
            H[c] = ((1 + us / 4) / (1 + loc / 4)) ** (1 / 3) - 1
    return pd.DataFrame(H)


def decompose(r_usd, fx, y, w, proxy=None):
    o = r_usd.loc[OOS_START:OOS_END].dropna()
    f = basket(fx, w).reindex(o.index)
    loc = (1 + o) / (1 + f) - 1
    H = hedge_series(y, list(w), w, proxy).reindex(o.index)
    h = basket(H, {c: w[c] for c in H.columns if H[c].notna().any()})
    hedged = (1 + loc) * (1 + h) - 1
    ident = float(((1 + loc) * (1 + f) - (1 + o)).abs().max())
    cov = np.cov(f, o)[0, 1] / o.var()
    # additive-log variance shares
    lf, ll_, lu = np.log1p(f), np.log1p(loc), np.log1p(o)
    return {"local": cagr(loc), "fx": cagr(f), "usd": cagr(o), "hedged": cagr(hedged.dropna()),
            "hedge_cost": float(-h.mean() * 12), "fx_vol_share_cov": float(cov),
            "var_fx_over_var_usd": float(f.var() / o.var()), "r2_usd_on_fx": float(np.corrcoef(f, o)[0, 1] ** 2),
            "log_cov_share_fx": float(np.cov(lf, lu)[0, 1] / lu.var()),
            "log_cov_share_local": float(np.cov(ll_, lu)[0, 1] / lu.var()),
            "identity_max_abs_error": ident, "hedged_ccys": list(H.columns[H.notna().any()]),
            "months_ID_hedged_after_2025_12": int(H.get("IDR", pd.Series(dtype=float)).loc["2026-01-01":].notna().sum())}


def check_currency(M):
    y = load_rates()
    fx, fxm = fx_returns(M.index)
    eq = {c: 0.1 for c in A.BASKET_EQUAL}
    ctry = pd.read_csv(LL / "em_bonds_countries.csv").set_index("country")
    inv = {v: k for k, v in A.CCY_COUNTRY.items()}
    g = {inv[c]: float(x) for c, x in ctry["weight_gbiem_pct"].dropna().items() if c in inv and inv[c] in fx.columns}
    g = {k: v / sum(g.values()) for k, v in g.items()}
    res = {"equal": decompose(M["EMLC"], fx, y, eq), "gbiem": decompose(M["EMLC"], fx, y, g)}
    # BRL left out: proxy its 3-month rate with Mexico's (a LOWER bound for Selic-CDI over 2018-26 is not in the
    # repo; MXN is the nearest high-carry Latin American rate in the data). Labelled proxy, not data.
    mx = y["MX_3M"].ffill(limit=2).shift(1)
    res["equal_brl_proxy_mx"] = decompose(M["EMLC"], fx, y, eq, proxy={"BRL": mx})
    # TRY in the GBI-EM sensitivity: no 3-month rate after 2008; crude proxy = Turkish CPI y/y (lagged)
    tr = y["TR_CPIYOY"].ffill(limit=2).shift(1) if "TR_CPIYOY" in y else None
    if tr is not None:
        res["gbiem_try_proxy_cpi_brl_proxy_mx"] = decompose(M["EMLC"], fx, y, g, proxy={"BRL": mx, "TRY": tr})
    # sign of the CIP hedge
    one = ((1 + 0.04 / 4) / (1 + 0.10 / 4)) ** (1 / 3) - 1
    res["cip_sign_example_us4_loc10"] = {"monthly_factor_minus_1": one, "annualised": one * 12,
                                         "expected_about": -(0.10 - 0.04)}
    j = jload("EMLC")["currency"]
    say("\n== 3. EMLC currency decomposition OOS (CAGR) ==")
    for k, x in res.items():
        if k.startswith("cip"):
            continue
        say(f"{k:34s} local {x['local']:.4f} fx {x['fx']:.4f} usd {x['usd']:.4f} hedged {x['hedged']:.4f} "
            f"cost {x['hedge_cost']:.4f} cov-share {x['fx_vol_share_cov']:.3f} var-ratio {x['var_fx_over_var_usd']:.3f} "
            f"R2 {x['r2_usd_on_fx']:.3f} identity err {x['identity_max_abs_error']:.1e} hedged {x['hedged_ccys']} "
            f"IDR months hedged 2026: {x['months_ID_hedged_after_2025_12']}")
    say(f"json: local {j['local_return']:.4f} fx {j['fx_return']:.4f} usd {j['usd_return']:.4f} hedged "
        f"{j['hedged_return']:.4f} cost {j['hedge_cost']:.4f} share {j['fx_vol_share']:.3f}; gbiem json hedged "
        f"{j['sensitivity_gbiem_weights']['hedged_return']:.4f} fx {j['sensitivity_gbiem_weights']['fx_return']:.4f}")
    say(f"CIP sign example (US 4%, local 10%): monthly {one:.5f}, x12 {one * 12:.4f} (a cost of about 6%/yr): correct sign")
    OUT["currency"] = res


# ---------------------------------------------------------------------------
# 4. Expected returns: fee double count, Monte Carlo anchoring, duration, yield convention
# ---------------------------------------------------------------------------
def check_expected():
    from research.candidates import em_bonds as E    # analyst module: the check is about its behaviour
    from research import montecarlo
    from research.config import MonteCarloSettings
    ctx = E.load()
    res = {}
    for t in FUNDS:
        d = jload(t)
        e = d["expected_return_7y"]
        yi = e["yield_inputs"]
        er, dep = yi["expense_ratio"], (yi["fx_expected_depreciation"] or 0.0)
        net_fee_yield = t != "EMLC"         # SEC 30-day or trailing distribution yield, both net of fees
        y_corr = e["methods"]["yield"] + (er * (1 - dep) if net_fee_yield else 0.0)
        hist = ctx.M[t].loc[E.RF_START:].dropna().to_frame(t)
        st = MonteCarloSettings(n_paths=A.MC_PATHS, horizon_years=A.HORIZON_YEARS, block_months=A.MC_BLOCK, seed=A.MC_SEED)
        mc = montecarlo.simulate(hist, st, targets={t: y_corr})[t]["annualised"]["50"]
        # scenario with duration +/- 1 year (halfway scenario)
        y0, ye = yi["yield"], e["scenarios"]["halfway_to_fair"]["exit_yield"]
        g0 = E.scenario_return(y0, ye, yi["duration"])
        gp, gm = E.scenario_return(y0, ye, yi["duration"] + 1), E.scenario_return(y0, ye, max(0.5, yi["duration"] - 1))
        res[t] = {"expense_ratio": er, "yield_net_of_fees": net_fee_yield, "consensus": e["consensus_usd"],
                  "consensus_fee_corrected": float(np.mean([y_corr, mc])), "understatement": float(np.mean([y_corr, mc])) - e["consensus_usd"],
                  "mc_minus_yield": e["methods"]["monte_carlo_median"] - e["methods"]["yield"],
                  "unchanged_gross_minus_quoted_yield": e["scenarios"]["yields_unchanged"]["gross_local"] - y0,
                  "monthly_comp_of_yield": (1 + y0 / 12) ** 12 - 1 - y0, "semiannual_eff_minus_yield": (1 + y0 / 2) ** 2 - 1 - y0,
                  "halfway_gross_dur_minus1": gm - g0, "halfway_gross_dur_plus1": gp - g0,
                  "credit_loss": yi["credit_loss"], "duration": yi["duration"], "duration_source": yi["duration_source"],
                  "yield_type": str(pd.read_csv(LL / "em_bond_inputs.csv").set_index("ticker").loc[t, "notes"]).split(";")[0]}
    say("\n== 4. Forward estimate: fee double count, MC anchoring, yield convention, duration ==")
    for t, x in res.items():
        say(f"{t:6s} ER {x['expense_ratio']:.4f} consensus {x['consensus']:.4f} -> fee-corrected {x['consensus_fee_corrected']:.4f} "
            f"(+{x['understatement']:.4f}); MC-yield {x['mc_minus_yield']:+.4f}; unchanged gross - yield "
            f"{x['unchanged_gross_minus_quoted_yield']:+.4f} (monthly comp {x['monthly_comp_of_yield']:+.4f}); "
            f"dur-1/+1 {x['halfway_gross_dur_minus1']:+.4f}/{x['halfway_gross_dur_plus1']:+.4f}; loss {x['credit_loss']:.4f}; "
            f"yield = {x['yield_type'][:45]}")
    r0 = sorted(res, key=lambda t: -res[t]["consensus"])
    r1 = sorted(res, key=lambda t: -res[t]["consensus_fee_corrected"])
    say("forward rank as published:", r0)
    say("forward rank fee-corrected:", r1)
    # credit loss arithmetic for HYEM
    c = {b: (A.CUM_DEFAULT_5Y_10Y[b][0] + (A.CUM_DEFAULT_5Y_10Y[b][1] - A.CUM_DEFAULT_5Y_10Y[b][0]) * 0.4) / 100
         for b in A.CUM_DEFAULT_5Y_10Y}
    pd_ = {b: 1 - (1 - v) ** (1 / 7) for b, v in c.items()}
    hy = sum(w * pd_[b] for b, w in A.RATING_MIX["HYEM"][0].items()) * (1 - A.RECOVERY["corporate"][0])
    say(f"HYEM credit loss by hand {hy:.4f} (json {res['HYEM']['credit_loss']:.4f})")
    OUT["expected"] = {"funds": res, "rank_published": r0, "rank_fee_corrected": r1, "hyem_credit_loss_by_hand": hy}


# ---------------------------------------------------------------------------
# 5. Country table
# ---------------------------------------------------------------------------
def price(c, y, m, f=2):
    n, cc, i = m * f, c / f * 100, y / f
    d = (1 + i) ** -n
    return cc * (1 - d) / i + 100 * d


def cm_returns(s, m=10.0):
    return pd.Series([(price(a, b, m - 1 / 12) + a * 100 / 12) / 100 - 1 for a, b in zip(s.iloc[:-1], s.iloc[1:])],
                     index=s.index[1:])


def check_countries():
    y = load_rates()
    cpi = pd.read_csv(DATA / "cpi_annual.csv", index_col=0) / 100
    tab = {}
    for iso in ("CO", "ZA", "MX"):
        s10 = y[f"{iso}_10Y"].dropna()
        sc = y[f"{iso}_CPIYOY"].dropna()
        wb = cpi[iso].dropna()
        # analyst rule: OECD CPI if within 12 months of 2026-10 and not older than the latest WB year
        use_wb = sc.index[-1] < pd.Timestamp("2025-10-31") or sc.index[-1].year < int(wb.index[-1])
        c = float(wb.iloc[-1]) if use_wb else float(sc.iloc[-1])
        tab[iso] = {"y10": float(s10.iloc[-1]), "y10_date": str(s10.index[-1].date()), "cpi": c,
                    "cpi_src": f"WB {wb.index[-1]}" if use_wb else f"OECD {sc.index[-1].date()}",
                    "real": float(s10.iloc[-1]) - c,
                    "real_oecd_cpi_only": float(s10.iloc[-1] - sc.iloc[-1]), "oecd_cpi_date": str(sc.index[-1].date())}
    br = y["BR_10Y"].dropna()
    brs = {"share_months_unchanged": float((br.diff() == 0).mean()),
           "distinct_2010_2017": sorted(set(np.round(br.loc["2010":"2017"] * 100, 2))),
           "range_2010_2017": [float(br.loc["2010":"2017"].min()), float(br.loc["2010":"2017"].max())],
           "latest": float(br.iloc[-1])}
    # constant-maturity model: same as research.bonds.total_returns?
    from research import bonds
    za = y["ZA_10Y"].dropna()
    diff = float((cm_returns(za) - bonds.total_returns(za, 10.0, 2)).abs().max())
    # Mexico has gaps: the analyst's dropna() treats a 2-month gap as one month
    mx = y["MX_10Y"]
    mxs = mx.loc[: "2026-10-31"]
    full = mxs.loc[mxs.first_valid_index():]
    gaps = int(full.isna().sum())
    r_drop = cm_returns(full.dropna()).loc[IS_START:]
    r_fill = cm_returns(full.interpolate(limit_area="inside")).loc[IS_START:]
    fx, fxm = fx_returns(pd.date_range("2005-01-31", "2026-10-31", freq="ME"))
    fxr = fxm["MXN"].pct_change(fill_method=None)
    usd_drop = (1 + r_drop) * (1 + fxr.reindex(r_drop.index)) - 1
    usd_fill = (1 + r_fill) * (1 + fxr.reindex(r_fill.index)) - 1
    mxres = {"missing_months": gaps, "months_since_2010_drop": len(r_drop), "months_since_2010_fill": len(r_fill),
             "local_cagr_as_built": cagr(r_drop), "local_cagr_gaps_interpolated": cagr(r_fill),
             "usd_cagr_as_built": cagr(usd_drop), "usd_cagr_gaps_interpolated": cagr(usd_fill),
             "usd_oos_as_built": cagr(usd_drop.loc[OOS_START:]), "usd_oos_gaps_interpolated": cagr(usd_fill.loc[OOS_START:]),
             "fx_cagr_mxn_since_2010": cagr(fxr.loc["2010-01-31":]),
             "note": "cagr() annualises by the number of observed months; with gaps the as-built series both skips "
                     "months of carry and FX and compresses time"}
    # effect on the EMLC cross-check basket (equal weight of the 9 countries with a 10y series)
    def usd_series(iso, fill):
        s = y[f"{iso}_10Y"].loc[: "2026-10-31"]
        s = s.loc[s.first_valid_index(): s.last_valid_index()]
        s = s.interpolate(limit_area="inside") if fill else s.dropna()
        r = cm_returns(s)
        inv = {v: k for k, v in A.CCY_COUNTRY.items()}
        return (1 + r) * (1 + fxm[inv[iso]].pct_change(fill_method=None).reindex(r.index)) - 1
    isos = [c for c in A.CROSSCHECK_COUNTRIES if c != "BR"]
    emlc = month_end_returns(["EMLC"])["EMLC"]
    for fill in (False, True):
        U = pd.DataFrame({c: usd_series(c, fill) for c in isos})
        b = basket(U, {c: 1.0 for c in isos})
        both = pd.concat([b, emlc], axis=1).dropna()
        mxres[f"crosscheck_model_cagr_{'filled' if fill else 'as_built'}"] = cagr(both.iloc[:, 0])
        mxres[f"crosscheck_model_oos_{'filled' if fill else 'as_built'}"] = cagr(both.iloc[:, 0].loc[OOS_START:])
    # the analyst's cross-check and table: compare with json values
    say("\n== 5. Country table ==")
    for iso, x in tab.items():
        say(f"{iso} 10y {x['y10']:.4f} ({x['y10_date']}) CPI {x['cpi']:.4f} ({x['cpi_src']}) real {x['real']:.4f}; "
            f"with OECD CPI only ({x['oecd_cpi_date']}) {x['real_oecd_cpi_only']:.4f}")
    say(f"BR_10Y: {brs['share_months_unchanged']:.0%} of months unchanged; 2010-2017 distinct levels {brs['distinct_2010_2017']}; latest {brs['latest']:.4f}")
    say(f"constant-maturity: own pricer vs research.bonds.total_returns on ZA, max |diff| {diff:.1e}; yields divided by 100: "
        f"ZA latest {za.iloc[-1]:.4f}")
    say(f"MX_10Y: {gaps} missing months; local CAGR since 2010 as built {mxres['local_cagr_as_built']:.4f} vs gaps "
        f"interpolated {mxres['local_cagr_gaps_interpolated']:.4f}; USD {mxres['usd_cagr_as_built']:.4f} vs "
        f"{mxres['usd_cagr_gaps_interpolated']:.4f}; USD OOS {mxres['usd_oos_as_built']:.4f} vs "
        f"{mxres['usd_oos_gaps_interpolated']:.4f}; MXN vs USD since 2010 {mxres['fx_cagr_mxn_since_2010']:.4f}/yr")
    say(f"EMLC cross-check basket (9 countries, no BR) full {mxres['crosscheck_model_cagr_as_built']:.4f} as built vs "
        f"{mxres['crosscheck_model_cagr_filled']:.4f} gaps filled; OOS {mxres['crosscheck_model_oos_as_built']:.4f} vs "
        f"{mxres['crosscheck_model_oos_filled']:.4f}")
    OUT["countries"] = {"real_yields": tab, "brazil": brs, "cm_model_diff": diff, "mexico_gaps": mxres}


# ---------------------------------------------------------------------------
# 8. Drop rule
# ---------------------------------------------------------------------------
def check_drop(M):
    rf = M["BIL"]
    o = lambda s: s.loc[OOS_START:OOS_END].dropna()
    sh = {t: sharpe(o(M[t]), rf) for t in FUNDS}
    res = {}
    for t in FUNDS:
        for bname in ("EMB", "EMLC"):
            if t == bname:
                continue
            i = ir(o(M[t]), M[bname])[0]
            res[f"{t}_vs_{bname}"] = {"sharpe": sh[t], "bench_sharpe": sh[bname], "ir": i,
                                      "fails_8_2": bool(sh[t] < sh[bname] and i < 0)}
    say("\n== 8. Drop rule 8.2 (OOS Sharpe below benchmark AND IR < 0) ==")
    for k, x in res.items():
        if x["fails_8_2"]:
            say(f"FAILS {k}: Sharpe {x['sharpe']:.3f} < {x['bench_sharpe']:.3f}, IR {x['ir']:.3f}")
    OUT["drop_rule"] = res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    ctl = pd.read_csv(LL / "em_bond_scored.csv")
    cols = sorted(set(ctl["ticker"]) | set(FUNDS) | {"BIL", "ACWX", "GLD", "EMB", "EMLC"})
    M = month_end_returns(cols)
    check_metrics(M)
    check_rolling(M)
    check_insample_and_control(M)
    check_currency(M)
    check_expected()
    check_countries()
    check_drop(M)
    if a.json:
        def conv(x):
            if isinstance(x, dict):
                return {str(k): conv(v) for k, v in x.items()}
            if isinstance(x, (list, tuple)):
                return [conv(v) for v in x]
            if isinstance(x, (np.floating, float)):
                return None if not np.isfinite(x) else float(x)
            if isinstance(x, (np.integer, np.bool_)):
                return x.item()
            return x
        Path(a.json).write_text(json.dumps(conv(OUT), indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
