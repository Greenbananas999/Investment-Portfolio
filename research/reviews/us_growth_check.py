"""Phase 4 adversarial review, US growth stocks: independent recomputation.

    python -m research.reviews.us_growth_check              # all checks, printed (~20 s)
    python -m research.reviews.us_growth_check --reproduce  # also re-runs the analyst's analyse() in memory
                                                            # and diffs every numeric field of the 8 JSONs (~70 s)
    python -m research.reviews.us_growth_check --json out.json   # also dump the numbers

Independent of research.candidates.us_growth: prices are read with
research.screen.read_wide_csv (the same spike filter, as the brief asks), and a
raw read without the filter is shown as a sensitivity. Monthly convention:
last close of each calendar month ('ME'), simple return, months after
2026-10-31 dropped (the last price is 2026-11-06, a partial month).
In-sample 2010-01-31..2017-12-31, OOS 2018-01-31..2026-10-31.
Every statistic below is coded here with numpy (not with research.screen.stats),
except where a check is explicitly about a library function (montecarlo,
fundamental scoring), which is then called on purpose.
Nothing is written except --json; no analyst file is touched.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

from research.screen.prices import read_wide_csv

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research"
LL = ROOT / "research" / "plan" / "longlists"
REP = ROOT / "reports" / "candidates"

TICKERS = ["AVGO", "META", "AMZN", "REGN", "NVDA", "ADBE", "MA", "GILD"]
FADED = ["BIIB", "SIRI", "ILMN", "CTSH", "AKAM", "EXPE"]
IS = ("2010-01-31", "2017-12-31")
OOS = ("2018-01-31", "2026-10-31")
LAST_FULL = "2026-10-31"
N_TRIALS = 46
STRESS = {"gfc_2008": ("2007-10-31", "2009-02-28"), "taper_2013": ("2013-04-30", "2013-08-31"),
          "covid_2020": ("2020-01-31", "2020-03-31"), "inflation_2022": ("2021-12-31", "2022-10-31")}
# method.md section 11, copied by hand for the comparison
METHOD_S11 = {"gfc_2008": ("2007-10-31", "2009-02-28"), "taper_2013": ("2013-04-30", "2013-08-31"),
              "covid_2020": ("2020-01-31", "2020-03-31"), "inflation_2022": ("2021-12-31", "2022-10-31")}


# ------------------------------------------------------------------ data
def monthly_from_daily(px):
    m = px.resample("ME").last()
    r = m.pct_change(fill_method=None).iloc[1:]
    return r.loc[:LAST_FULL]


def load(cols, spikes=True):
    if spikes:
        px = read_wide_csv(DATA / "prices.csv", columns=cols)
    else:
        head = pd.read_csv(DATA / "prices.csv", nrows=0).columns
        px = pd.read_csv(DATA / "prices.csv", index_col=0, parse_dates=True,
                         usecols=[head[0]] + [c for c in head[1:] if c in set(cols)]).sort_index()
        px = px[~px.index.duplicated(keep="last")].apply(pd.to_numeric, errors="coerce")
    return px, monthly_from_daily(px)


# ------------------------------------------------------------------ statistics (own code)
def sharpe(r, rf):
    ex = (r - rf.reindex(r.index).fillna(0)).dropna()
    return ex.mean() / ex.std(ddof=1) * math.sqrt(12)


def ir(r, b):
    a = (r - b.reindex(r.index)).dropna()
    sd = a.std(ddof=1)
    return (a.mean() / sd * math.sqrt(12) if sd > 0 else float("nan")), len(a)


def mdd(r, start_at_one=True):
    w = (1 + r.dropna()).cumprod()
    if start_at_one:
        w = pd.concat([pd.Series([1.0]), w.reset_index(drop=True)])
    return float((w / w.cummax() - 1).min())


def cagr(r):
    r = r.dropna()
    return float((1 + r).prod() ** (12 / len(r)) - 1)


def ols_alpha(r, b, rf):
    rf = rf.reindex(r.index).fillna(0)
    df = pd.concat([r - rf, b.reindex(r.index) - rf], axis=1).dropna()
    y, x = df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy()
    X = np.column_stack([np.ones_like(x), x])
    beta, res, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    s2 = e @ e / (len(y) - 2)
    se = math.sqrt(s2 * np.linalg.inv(X.T @ X)[0, 0])
    return beta[0] * 12, beta[0] / se, beta[1]


def nw_t(x, lags=3):
    """Newey-West t-statistic of the mean of x (Bartlett kernel)."""
    x = np.asarray(x.dropna(), float)
    n, u = len(x), x - x.mean()
    s = u @ u / n
    for k in range(1, lags + 1):
        s += 2 * (1 - k / (lags + 1)) * (u[k:] @ u[:-k]) / n
    return x.mean() / math.sqrt(s / n) if s > 0 else float("nan")


def dsr(sh_annual, n_trials, T, skew, kurt_raw):
    """Bailey & Lopez de Prado deflated Sharpe, V = 1/(T-1) (method.md change log, s7)."""
    sr = sh_annual / math.sqrt(12)
    v = 1 / (T - 1)
    g = 0.5772156649015329
    z = sps.norm.ppf
    sr0 = math.sqrt(v) * ((1 - g) * z(1 - 1 / n_trials) + g * z(1 - 1 / (n_trials * math.e)))
    den = 1 - skew * sr + (kurt_raw - 1) / 4 * sr ** 2
    return float(sps.norm.cdf((sr - sr0) * math.sqrt(T - 1) / math.sqrt(den))), sr0 * math.sqrt(12)


def wret(r, s, e):
    x = r[(r.index > pd.Timestamp(s)) & (r.index <= pd.Timestamp(e))]
    return float((1 + x).prod() - 1) if x.notna().all() and len(x) else None


def block(r, b, rf, s, e):
    x = r.loc[s:e].dropna()
    a, ta, be = ols_alpha(x, b, rf)
    i, n = ir(x, b)
    sh = sharpe(x, rf)
    return {"months": len(x), "start": str(x.index[0].date()), "end": str(x.index[-1].date()),
            "cagr": cagr(x), "vol": float(x.std() * math.sqrt(12)), "sharpe": sh, "info_ratio": i,
            "t_ir": i / math.sqrt(12) * math.sqrt(n), "t_ir_nw3": nw_t(x - b.reindex(x.index)),
            "alpha": a, "t_alpha": ta, "beta": be, "max_dd": mdd(x), "max_dd_lib_convention": mdd(x, False),
            "deflated_sharpe": dsr(sh, N_TRIALS, len(x), float(x.skew()), float(x.kurt()) + 3)[0]}


# ------------------------------------------------------------------ checks
def candidate_checks(mo, mo_raw):
    rf, b, q = mo["BIL"], mo["IVW"], mo["QQQ"]
    out = {}
    for t in TICKERS + ["IVW", "QQQ"]:
        r = mo[t]
        o = block(r, b, rf, *OOS)
        o["sharpe_raw_prices"] = sharpe(mo_raw[t].loc[OOS[0]:OOS[1]].dropna(), mo_raw["BIL"])
        o["ir_vs_qqq"] = ir(r.loc[OOS[0]:OOS[1]].dropna(), q)[0]
        o["stress"] = {k: {"ret": wret(r, s, e), "ivw": wret(b, s, e)} for k, (s, e) in STRESS.items()}
        x = r.loc[OOS[0]:OOS[1]]
        o["sub_2018_2022"] = {k: v for k, v in block(r, b, rf, "2018-01-31", "2022-12-31").items()
                              if k in ("sharpe", "info_ratio", "t_ir", "cagr")}
        o["sub_2023_2026"] = {k: v for k, v in block(r, b, rf, "2023-01-31", OOS[1]).items()
                              if k in ("sharpe", "info_ratio", "t_ir", "cagr")}
        act = (x - b.reindex(x.index)).dropna()
        ro = act.rolling(36).mean() / act.rolling(36).std() * math.sqrt(12)
        ro = ro.dropna()
        o["rolling36_oos"] = ({"n": len(ro), "share_pos": float((ro > 0).mean()), "min": float(ro.min()),
                               "first_end": str(ro.index[0].date())} if len(ro) else None)
        out[t] = o
    return out


def compare_json(c):
    """Analyst JSON vs recomputed (OOS usd block and stress)."""
    rows = []
    for t in TICKERS:
        d = json.loads((REP / f"{t}.json").read_text(encoding="utf-8"))
        m = d["metrics"]["out_of_sample"]["usd"]
        mine = c[t]
        pairs = [("sharpe", m["sharpe"], mine["sharpe"]), ("info_ratio", m["info_ratio"], mine["info_ratio"]),
                 ("t_stat_ir", m["t_stat_ir"], mine["t_ir"]), ("alpha", m["alpha"], mine["alpha"]),
                 ("t_stat_alpha", m["t_stat_alpha"], mine["t_alpha"]), ("beta", m["beta"], mine["beta"]),
                 ("max_drawdown", m["max_drawdown"], mine["max_dd"]), ("cagr", m["cagr"], mine["cagr"]),
                 ("deflated_sharpe", m["deflated_sharpe"], mine["deflated_sharpe"]),
                 ("months", m["months"], mine["months"]), ("start", m["start"], mine["start"]),
                 ("end", m["end"], mine["end"]),
                 ("share_ir_positive_oos", d["rolling"]["share_ir_positive_oos"], mine["rolling36_oos"]["share_pos"])]
        for k in STRESS:
            pairs.append((f"stress.{k}", d["stress"][k]["return"], mine["stress"][k]["ret"]))
            pairs.append((f"stress.{k}.ivw", d["stress"][k]["benchmark"], mine["stress"][k]["ivw"]))
        for k, a, me in pairs:
            if isinstance(a, str) or isinstance(me, str):
                diff = 0.0 if a == me else None
            else:
                diff = None if a is None or me is None else float(me - a)
            rows.append({"ticker": t, "field": k, "analyst": a, "review": me, "diff": diff})
    return pd.DataFrame(rows)


def control_checks(mo):
    sc = pd.read_csv(LL / "us_growth_stock_scored.csv", dtype={"flags": str})
    passed = sc[sc["passed"].astype(str) == "True"]["ticker"].tolist()
    ins = pd.read_csv(LL / "us_growth_stock_insample_table.csv").set_index("ticker")
    rf, b = mo["BIL"], mo["IVW"]
    rows = {}
    for t in passed:
        x = mo[t].loc[OOS[0]:OOS[1]].dropna()
        rows[t] = {"sharpe_oos": sharpe(x, rf), "ir_oos": ir(x, b)[0], "composite_is": ins.loc[t, "composite"],
                   "rank_is": int(ins.loc[t, "rank"]), "role": ins.loc[t, "role"]}
    df = pd.DataFrame(rows).T
    for c in ("sharpe_oos", "ir_oos", "composite_is"):
        df[c] = df[c].astype(float)
    df["rank_oos"] = df["sharpe_oos"].rank(ascending=False).astype(int)
    ivw = sharpe(b.loc[OOS[0]:OOS[1]].dropna(), rf)
    rho, p = sps.spearmanr(df["composite_is"], df["sharpe_oos"])
    rho_ir, p_ir = sps.spearmanr(df["composite_is"], df["ir_oos"])
    beat = df[df["sharpe_oos"] > ivw]
    fl = df.loc[[t for t in FADED if t in df.index]]
    top10 = df.sort_values("rank_oos").head(10)
    sl = df.loc[TICKERS]
    # names chosen in place of composite ranks 4, 7, 8 (FANG, LRCX, ORLY): NVDA (9), MA (11), GILD (14)
    swap_in, swap_out = ["NVDA", "MA", "GILD"], ["FANG", "LRCX", "ORLY"]
    # in-sample sanity: composite uses only <= 2017 returns: recompute IS Sharpe of the shortlist
    is_sh = {t: sharpe(mo[t].loc[IS[0]:IS[1]].dropna(), rf) for t in TICKERS}
    is_diff = max(abs(is_sh[t] - ins.loc[t, "sharpe_is"]) for t in TICKERS)
    return {
        "n": len(df), "ivw_sharpe_oos": ivw, "n_beat_ivw": len(beat), "share_beat_ivw": len(beat) / len(df),
        "beat_ivw": {t: (round(v, 3), int(df.loc[t, "rank_is"])) for t, v in beat["sharpe_oos"].items()},
        "spearman_composite_oos_sharpe": (rho, p), "spearman_composite_oos_ir": (rho_ir, p_ir),
        "spearman_ex_faded": sps.spearmanr(df.drop(fl.index)["composite_is"], df.drop(fl.index)["sharpe_oos"]),
        "faded": {t: (round(fl.loc[t, "sharpe_oos"], 3), int(fl.loc[t, "rank_is"]), int(fl.loc[t, "rank_oos"]))
                  for t in fl.index},
        "faded_median_sharpe": float(fl["sharpe_oos"].median()),
        "shortlist_median_sharpe": float(sl["sharpe_oos"].median()),
        "shortlist_beat_ivw": int((sl["sharpe_oos"] > ivw).sum()),
        "all_median_sharpe": float(df["sharpe_oos"].median()),
        "top10_oos": {t: (int(r["rank_oos"]), int(r["rank_is"]), round(r["sharpe_oos"], 3)) for t, r in top10.iterrows()},
        "near_miss_ranks": {t: (int(df.loc[t, "rank_is"]), int(df.loc[t, "rank_oos"])) for t in
                            ["FANG", "ORLY", "LRCX", "SBUX", "AMAT", "MNST", "ODFL", "PANW", "FTNT", "APH"]},
        "swap_in_median_sharpe": float(df.loc[swap_in, "sharpe_oos"].median()),
        "swap_out_median_sharpe": float(df.loc[swap_out, "sharpe_oos"].median()),
        "top8_composite_median_sharpe": float(df.sort_values("rank_is").head(8)["sharpe_oos"].median()),
        "is_sharpe_max_abs_diff_vs_insample_table": is_diff,
    }


def mc_edge_check():
    """Is research/montecarlo.py's block bootstrap under-sampling the ends, and how much does it move the median?"""
    from research import config, montecarlo
    out = {}
    px, mo = load(TICKERS)
    B = config.MonteCarloSettings().block_months
    for t in TICKERS:
        d = json.loads((REP / f"{t}.json").read_text(encoding="utf-8"))
        e = d["expected_return_7y"]
        h = mo[t].loc["2010-01-31":].dropna()
        cons = e["consensus_usd"]
        x = montecarlo._scale_to(h.to_numpy(), cons)
        T = len(x)
        tt = np.arange(T)
        cnt = np.minimum(tt, T - B) - np.maximum(0, tt - B + 1) + 1        # starts covering month t
        w = cnt / cnt.sum()
        lw = np.log1p(x)
        implied_edge = math.exp(12 * (w @ lw)) - 1
        implied_uniform = math.exp(12 * lw.mean()) - 1                      # = consensus by construction
        # empirical: sample the bootstrap indices with the module's own function and seed
        rng = np.random.default_rng(622)
        idx = montecarlo.bootstrap_paths(x[:, None], 84, 20000, B, rng)
        freq = np.bincount(idx.ravel(), minlength=T) / idx.size
        out[t] = {"T": T, "consensus": cons, "mc_median_json": e["methods"]["monte_carlo_median"],
                  "implied_by_edge_weights": implied_edge, "implied_uniform": implied_uniform,
                  "weight_first_last_vs_middle": (float(w[0] / w[T // 2]), float(w[-1] / w[T // 2])),
                  "empirical_freq_first_last_vs_middle": (float(freq[0] / freq[T // 2]), float(freq[-1] / freq[T // 2])),
                  "edge_months_logret_first5_last5": (float(lw[:5].mean() * 12), float(lw[-5:].mean() * 12)),
                  "gap_median_minus_consensus": e["methods"]["monte_carlo_median"] - cons,
                  "gap_explained_by_edge": implied_edge - cons}
    return out


def gk_check():
    out = {}
    for t in TICKERS:
        d = json.loads((REP / f"{t}.json").read_text(encoding="utf-8"))
        e = d["expected_return_7y"]
        g = e["detail"]["grinold_kroner"]
        m = e["methods"]
        rep = (g["target_pe"] / g["forward_pe"]) ** (1 / 10) - 1
        info = json.loads((DATA / "fundamentals" / t / "info.json").read_text(encoding="utf-8"))
        info = info.get("info", info)
        tr = info.get("trailingPE")
        rep_trailing = (g["target_pe"] / tr) ** (1 / 10) - 1 if tr else None
        gk_tr = g["without_repricing"] + rep_trailing if rep_trailing is not None else None
        cons_noreprice = np.mean([m["capm"], m["dcf"], g["without_repricing"]])
        cons_tr = np.mean([m["capm"], m["dcf"], gk_tr]) if gk_tr is not None else None
        out[t] = {"forward_pe": g["forward_pe"], "trailing_pe_yahoo": tr,
                  "trailing_pe_edgar": d["fundamentals"]["latest"]["pe_trailing"] if d["fundamentals"]["latest"] else None,
                  "target_pe": g["target_pe"], "repricing_recomputed": rep, "repricing_json": g["repricing"],
                  "gk": m["grinold_kroner"], "gk_without_repricing": g["without_repricing"],
                  "repricing_if_start_trailing": rep_trailing, "consensus": e["consensus_usd"],
                  "consensus_without_repricing": float(cons_noreprice),
                  "consensus_if_gk_starts_trailing": None if cons_tr is None else float(cons_tr),
                  "capm": m["capm"], "dcf": m["dcf"], "dcf_upside": e["detail"]["dcf"]["upside"],
                  "dcf_terminal_share": e["detail"]["dcf"]["terminal_share_of_value"],
                  "fwd_eps_over_trailing_eps": (info.get("forwardEps") / info.get("trailingEps"))
                  if info.get("trailingEps") and info.get("trailingEps") > 0 else None}
    return out


def avgo_roe_check():
    """AVGO scored as a financial: the FIN_WORDS match is 'financ' inside 'yfinance' in universe.csv notes."""
    from research.screen import edgar as ed
    from research.screen.fundamental import STOCK_GROUPS, group_score, stock_measures
    from research.screen.prices import read_dividends
    uni = pd.read_csv(ROOT / "research" / "plan" / "universe.csv")
    fin_words = ("bank", "financ", "insur", "brokerage", "exchange operator")
    hits = {}
    for _, r in uni[uni["type"] == "us_growth_stock"].iterrows():
        text = " ".join(str(r.get(c, "")) for c in ("category", "notes", "name")).lower()
        w = [x for x in fin_words if x in text]
        if w:
            hits[r["ticker"]] = {"words": w, "only_via_yfinance": "yfinance" in text
                                 and "financ" not in text.replace("yfinance", "")}
    sc = pd.read_csv(LL / "us_growth_stock_scored.csv", dtype={"flags": str}).set_index("ticker")
    passed = sc[sc["passed"].astype(str) == "True"].copy()
    cols = [c for _, (_, cc) in STOCK_GROUPS.items() for c in cc]
    base = group_score(passed[cols], STOCK_GROUPS)
    sanity = float((base["fundamental_score"] - passed["fundamental_score"]).abs().max())
    px = read_wide_csv(DATA / "prices.csv", columns=["AVGO", "SIRI"])
    fixed = passed[cols].copy()
    meas = {}
    for t in ("AVGO", "SIRI"):
        if t not in passed.index:
            continue
        row = uni.set_index("ticker").loc[t]
        path = ed.edgar_path(DATA / "edgar", str(row["edgar_cik"]).zfill(10) if pd.notna(row["edgar_cik"]) else None)
        table = None
        if path is not None:
            cj = ed.read_companyfacts(path)
            table = ed.point_in_time(ed.edgar_facts(cj), IS[1]) if cj is not None else None
            splits = ed.split_events(cj) if cj is not None else None
            if table is not None and table.empty:
                table = None
        else:
            splits = None
        if table is None:
            table, splits = ed.yfinance_table(DATA / "fundamentals" / t, "USD"), None
        m, fl = stock_measures(table, px[t], IS[1], False, splits,
                               read_dividends(DATA / "fundamentals" / t / "dividends.csv"))
        meas[t] = {"roe_as_scored": float(passed.loc[t, "roic_or_roe"]), "roic_nonfinancial": m.get("roic_or_roe"),
                   "net_debt_ebitda_nonfinancial": m.get("net_debt_ebitda"), "fy_end_used": m.get("fy_end"),
                   "pit": bool(table.attrs.get("point_in_time", True))}
        fixed.loc[t, "roic_or_roe"] = m.get("roic_or_roe")
        fixed.loc[t, "net_debt_ebitda"] = m.get("net_debt_ebitda")
    new = group_score(fixed, STOCK_GROUPS)
    ins = pd.read_csv(LL / "us_growth_stock_insample_table.csv").set_index("ticker")

    def composite(fs):
        df = ins[["sharpe_is", "ir_is"]].copy()
        df["fs"] = fs.reindex(df.index)
        c = 0.5 * df["fs"].rank(pct=True).fillna(0.5) + 0.25 * df["sharpe_is"].rank(pct=True) \
            + 0.25 * df["ir_is"].rank(pct=True)
        return c, c.rank(ascending=False, method="first").astype(int)

    c0, r0 = composite(passed["fundamental_score"])
    c1, r1 = composite(new["fundamental_score"])
    fs_neutral = passed["fundamental_score"].copy()
    fs_neutral.loc["AVGO"] = np.nan                     # no point-in-time data -> neutral 0.5 percentile
    c2, r2 = composite(fs_neutral)
    return {"fin_word_hits": hits, "group_score_sanity_max_abs_diff": sanity, "measures": meas,
            "avgo": {"quality_as_scored": float(passed.loc["AVGO", "quality_score"]),
                     "quality_fixed": float(new.loc["AVGO", "quality_score"]),
                     "fund_as_scored": float(passed.loc["AVGO", "fundamental_score"]),
                     "fund_fixed": float(new.loc["AVGO", "fundamental_score"]),
                     "composite_as_scored": float(c0["AVGO"]), "rank_as_scored": int(r0["AVGO"]),
                     "composite_fixed": float(c1["AVGO"]), "rank_fixed": int(r1["AVGO"]),
                     "composite_fund_neutral": float(c2["AVGO"]), "rank_fund_neutral": int(r2["AVGO"]),
                     "fy_end_of_scored_data": str(passed.loc["AVGO", "fy_end"]),
                     "fundamentals_pit": str(passed.loc["AVGO", "fundamentals_pit"])},
            "siri": {"fund_as_scored": float(passed.loc["SIRI", "fundamental_score"]),
                     "fund_fixed": float(new.loc["SIRI", "fundamental_score"]),
                     "rank_as_scored": int(r0["SIRI"]), "rank_fixed": int(r1["SIRI"])} if "SIRI" in passed.index else None,
            "top8_fixed": list(r1.sort_values().index[:8]), "top8_as_scored": list(r0.sort_values().index[:8])}


def explain_check(c):
    out = {}
    for t in TICKERS:
        d = json.loads((REP / f"{t}.json").read_text(encoding="utf-8"))
        s2 = d["explain"][1]
        o, b = c[t], c["IVW"]
        want = [f"{o['cagr'] * 100:.1f}% a year", f"{b['cagr'] * 100:.1f}% for the S&P 500 Growth",
                f"worst fall of {o['max_dd'] * 100:.0f}%", f"(fund {b['max_dd'] * 100:.0f}%)"]
        e = d["expected_return_7y"]
        lo, hi = e["range_5_95"]
        want3 = [f"about {e['consensus_usd'] * 100:.0f}% a year", f"{lo * 100:.0f}% to {hi * 100:.0f}%"]
        out[t] = {"s2_ok": all(w in s2 for w in want), "s3_ok": all(w in d["explain"][2] for w in want3),
                  "missing": [w for w in want if w not in s2] + [w for w in want3 if w not in d["explain"][2]]}
    return out


def reproduce():
    """Re-run the analyst's analyse() in memory and diff every numeric leaf against the JSON on disk."""
    from research.candidates import us_growth as ug
    sc = pd.read_csv(LL / "us_growth_stock_scored.csv")
    inp = ug.load_inputs(list(dict.fromkeys(TICKERS + list(sc.loc[sc["passed"].astype(bool), "ticker"]))))
    worst = {}

    def walk(a, b, path=""):
        if isinstance(a, dict):
            for k in set(a) | set(b):
                walk(a.get(k), b.get(k), f"{path}.{k}")
        elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, f"{path}[{i}]")
        elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
            worst[path] = abs(a - b)
        elif a != b:
            worst[path] = float("inf")

    for t in TICKERS:
        res = json.loads(json.dumps(ug.analyse(t, inp)))
        disk = json.loads((REP / f"{t}.json").read_text(encoding="utf-8"))
        walk(res, disk, t)
    bad = {k: v for k, v in worst.items() if v > 1e-9}
    return {"leaves_compared": len(worst), "leaves_different": len(bad), "examples": dict(list(bad.items())[:10])}


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m research.reviews.us_growth_check")
    ap.add_argument("--reproduce", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    sc = pd.read_csv(LL / "us_growth_stock_scored.csv")
    cols = list(dict.fromkeys(TICKERS + list(sc.loc[sc["passed"].astype(bool), "ticker"]) + ["IVW", "QQQ", "BIL"]))
    px, mo = load(cols)
    _, mo_raw = load(TICKERS + ["IVW", "QQQ", "BIL"], spikes=False)
    print(f"monthly: {mo.index[0].date()}..{mo.index[-1].date()} (last daily price {px.index[-1].date()}, partial month dropped)")
    res = {"stress_windows_match_method_s11": STRESS == METHOD_S11}
    c = candidate_checks(mo, mo_raw)
    res["candidates"] = c
    pd.set_option("display.width", 250)
    tab = pd.DataFrame({t: {k: c[t][k] for k in ("sharpe", "sharpe_raw_prices", "info_ratio", "t_ir", "t_ir_nw3",
                                                 "alpha", "t_alpha", "beta", "max_dd", "max_dd_lib_convention",
                                                 "deflated_sharpe", "ir_vs_qqq", "cagr", "vol")}
                        for t in c}).T
    print("\nOOS 2018-01..2026-10, recomputed:\n", tab.round(3).to_string())
    print("\nstress (stock / IVW):")
    for t in c:
        print(t, {k: (None if v["ret"] is None else round(v["ret"], 3), round(v["ivw"], 3)) for k, v in c[t]["stress"].items()})
    print("\nsub-periods and rolling OOS IR:")
    for t in c:
        print(t, "2018-22", {k: round(v, 2) for k, v in c[t]["sub_2018_2022"].items()},
              "| 2023-26", {k: round(v, 2) for k, v in c[t]["sub_2023_2026"].items()}, "| roll36", c[t]["rolling36_oos"])
    cmp_ = compare_json(c)
    num = cmp_[cmp_["diff"].notna()]
    print("\nanalyst JSON vs review: max |diff| per field")
    print(num.assign(ad=num["diff"].abs()).groupby("field")["ad"].max().round(6).to_string())
    print("non-numeric mismatches:", cmp_[cmp_["diff"].isna()][["ticker", "field", "analyst", "review"]].to_dict("records"))
    res["json_compare_max_abs_diff"] = num.assign(ad=num["diff"].abs()).groupby("field")["ad"].max().to_dict()
    ctl = control_checks(mo)
    res["control"] = ctl
    print("\ncontrol:", json.dumps(ctl, indent=1, default=float))
    mc = mc_edge_check()
    res["montecarlo"] = mc
    print("\nmonte carlo edge check:")
    print(pd.DataFrame(mc).T[["T", "consensus", "mc_median_json", "implied_by_edge_weights",
                              "gap_median_minus_consensus", "gap_explained_by_edge",
                              "weight_first_last_vs_middle", "empirical_freq_first_last_vs_middle",
                              "edge_months_logret_first5_last5"]].to_string())
    gk = gk_check()
    res["grinold_kroner"] = gk
    print("\nG-K repricing:")
    print(pd.DataFrame(gk).T.round(4).to_string())
    av = avgo_roe_check()
    res["avgo_roe"] = av
    print("\nAVGO ROE-as-financial check:", json.dumps(av, indent=1, default=str))
    ex = explain_check(c)
    res["explain"] = ex
    print("\nexplain sentences vs recomputed numbers:", ex)
    if a.reproduce:
        rp = reproduce()
        res["reproduce"] = rp
        print("\nreproduce (analyse() in memory vs JSON on disk):", rp)
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=1, default=lambda o: float(o) if np.isscalar(o) else str(o)),
                                encoding="utf-8")


if __name__ == "__main__":
    main()
