"""Fundamental measures and scores per position type (method.md section 5).

Scores are percentile ranks within the rows passed in (the caller passes one
position type), averaged within each group, then weighted across groups; a
missing group's weight is redistributed pro-rata.
"""

import numpy as np
import pandas as pd

from .edgar import split_factor
from .prices import dividend_factor
from .scoring import percentile_scores

STOCK_GROUPS = {
    "growth": (0.40, {"rev_cagr_3y": True, "ni_cagr_3y": True}),
    "quality": (0.30, {"roic_or_roe": True, "op_margin": True, "op_margin_chg_3y": True,
                       "net_debt_ebitda": False}),
    "valuation": (0.30, {"fcf_yield": True, "pe_rel_5y": False}),
}
BOND_GROUPS = {
    "carry": (0.40, {"carry": True}),
    "credit": (0.30, {"rating_score": False, "country_max_weight": False, "debt_gdp": False,
                      "current_account_gdp": True, "inflation": False, "real_yield": True}),
    "cost_liquidity": (0.15, {"expense_ratio": False, "aum_usd_bn": True, "bid_ask": False,
                              "traded_value_usd_m": True}),
    "diversification": (0.15, {"corr_equity": False}),
}
OTHER_GROUPS = {
    "inflation": (0.40, {"inflation_beta": True, "ret_2022": True}),
    "correlation": (0.30, {"corr_acwx": False, "corr_emb": False}),
    "cost": (0.30, {"expense_ratio": False, "roll_cost": False}),
}
RATINGS = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
           "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D"]
TAX_FALLBACK = 0.25
INFLATION_WINDOW = ("2021-12-31", "2022-10-31")


def group_score(measures, groups):
    """Percentiles per measure, mean within group, weighted across groups (pro-rata if missing)."""
    out = pd.DataFrame(index=measures.index)
    total, wsum = 0.0, 0.0
    for g, (w, cols) in groups.items():
        present = [c for c in cols if c in measures and measures[c].notna().any()]
        if present:
            pct = percentile_scores(measures, present, {c: cols[c] for c in present})
            out[f"{g}_score"] = pct.mean(axis=1, skipna=True)
        else:
            out[f"{g}_score"] = np.nan
        s = out[f"{g}_score"]
        total = total + s.fillna(0) * w
        wsum = wsum + s.notna() * w
    out["fundamental_score"] = (total / wsum).where(wsum > 0)
    return out


def _cagr(a, b, years):
    if pd.isna(a) or pd.isna(b) or a <= 0 or b <= 0:
        return np.nan
    return (b / a) ** (1 / years) - 1


def _row_years_before(table, end, years=3, tol_days=45):
    target = end - pd.DateOffset(years=years)
    d = np.abs((table.index - target).days)
    i = int(np.argmin(d)) if len(d) else None
    return table.iloc[i] if i is not None and d[i] <= tol_days else None


def stock_measures(table, price_local, as_of, financial=False, splits=None, dividends=None,
                   fx_to_reporting=1.0):
    """Section 5 stock measures from one fundamentals table (`point_in_time` layout).

    price_local: daily adjusted close in the listing currency. It is converted
    to split-adjusted raw prices by undoing Yahoo's dividend adjustment
    (`dividends`, if given); EDGAR share counts and EPS are put in today's
    share units with `splits`. fx_to_reporting converts a listing-currency
    price into the reporting currency (1 when they match).
    Valuation date: as_of for point-in-time tables; for non-PIT (current
    yfinance) tables, the last price date.
    Returns (dict of measures, list of flags).
    """
    flags, m = [], {}
    if table is None or len(table) == 0 or table["revenue"].notna().sum() == 0:
        return m, ["no fundamentals at as_of"]
    pit = table.attrs.get("point_in_time", True)
    t = table[table["revenue"].notna()]
    last = t.iloc[-1]
    end = t.index[-1]
    prev = _row_years_before(t, end)
    m["fy_end"] = end.date().isoformat()
    m["fy_filed"] = last.get("first_filed")
    rev, ni, oi = last["revenue"], last["net_income"], last["operating_income"]
    if prev is None:
        flags.append("no fiscal year 3 years earlier: CAGRs not computed")
        m["rev_cagr_3y"] = m["ni_cagr_3y"] = m["op_margin_chg_3y"] = np.nan
    else:
        m["rev_cagr_3y"] = _cagr(prev["revenue"], rev, 3)
        m["ni_cagr_3y"] = _cagr(prev["net_income"], ni, 3)
        if pd.notna(prev["net_income"]) and prev["net_income"] <= 0:
            flags.append("net income <= 0 three years earlier: NI CAGR not defined")
        pm = prev["operating_income"] / prev["revenue"] if prev["revenue"] else np.nan
        m["op_margin_chg_3y"] = oi / rev - pm if rev else np.nan
    m["op_margin"] = oi / rev if rev else np.nan
    debt = last.get("debt_total", np.nan)
    cash, eq = last["cash"], last["equity"]
    if financial:
        m["roic_or_roe"] = ni / eq if pd.notna(eq) and eq > 0 else np.nan
        m["net_debt_ebitda"] = np.nan
        flags.append("financial: ROE used, net debt/EBITDA skipped")
    else:
        tax, pre = last["income_tax"], last["pretax_income"]
        rate = tax / pre if pd.notna(tax) and pd.notna(pre) and pre > 0 else np.nan
        rate = TAX_FALLBACK if pd.isna(rate) else float(np.clip(rate, 0, 0.5))
        invested = (0 if pd.isna(debt) else debt) + eq - (0 if pd.isna(cash) else cash)
        m["roic_or_roe"] = oi * (1 - rate) / invested if pd.notna(invested) and invested > 0 else np.nan
        ebitda = oi + (0 if pd.isna(last["da"]) else last["da"])
        if pd.isna(last["da"]):
            flags.append("no D&A: EBITDA = operating income")
        m["net_debt_ebitda"] = ((0 if pd.isna(debt) else debt) - (0 if pd.isna(cash) else cash)) / ebitda \
            if pd.notna(ebitda) and ebitda > 0 else np.nan
        if pd.isna(debt):
            flags.append("no debt tag: debt taken as 0")
    # valuation
    p = price_local.dropna() if price_local is not None else pd.Series(dtype=float)
    val_date = pd.Timestamp(as_of) if pit else (p.index[-1] if len(p) else pd.Timestamp(as_of))
    # Yahoo's adjustment runs back from the download date, so undo it on the full series
    raw = (p / dividend_factor(p, dividends) * fx_to_reporting).loc[:val_date]
    if len(raw) == 0:
        m["fcf_yield"] = m["pe_rel_5y"] = m["pe_now"] = m["market_cap_local"] = np.nan
        flags.append("no price at valuation date")
        return m, flags
    if dividends is None:
        flags.append("no dividend file: prices still dividend-adjusted (P/E, FCF yield biased)")
    price = float(raw.iloc[-1])
    shares = last["shares"] * split_factor(splits, last.get("filed_shares"))
    mcap = shares * price if pd.notna(shares) else np.nan
    m["market_cap_local"] = mcap
    m["valuation_date"] = val_date.date().isoformat()
    fcf = last["cfo"] - (0 if pd.isna(last["capex"]) else abs(last["capex"]))
    m["fcf_yield"] = fcf / mcap if pd.notna(mcap) and mcap > 0 else np.nan
    eps_hist = _eps_today_units(t, splits)
    month_px = raw.resample("ME").last()
    month_px = month_px[month_px.index > val_date - pd.DateOffset(years=5)]
    pe = []
    for d, px in month_px.items():
        known = eps_hist[eps_hist["known"] <= d]
        if len(known) and known["eps"].iloc[-1] > 0:
            pe.append(px / known["eps"].iloc[-1])
    eps_now = eps_hist["eps"].iloc[-1] if len(eps_hist) else np.nan
    m["pe_now"] = price / eps_now if pd.notna(eps_now) and eps_now > 0 else np.nan
    if len(pe) >= 24 and pd.notna(m["pe_now"]):
        m["pe_rel_5y"] = m["pe_now"] / float(np.median(pe))
    else:
        m["pe_rel_5y"] = np.nan
        flags.append(f"P/E history {len(pe)} months (<24): P/E vs 5y median not computed")
    return m, flags


def _eps_today_units(t, splits):
    """EPS per fiscal year in today's share units, with the date it became known."""
    eps = t["eps_diluted"].copy()
    fac = pd.Series([split_factor(splits, d) for d in t["filed_eps_diluted"]], index=t.index)
    eps = eps / fac
    alt = t["net_income"] / (t["shares"] * pd.Series([split_factor(splits, d) for d in t["filed_shares"]],
                                                     index=t.index))
    eps = eps.fillna(alt)
    return pd.DataFrame({"eps": eps, "known": t["first_filed"]}).dropna().sort_values("known")


def fundamental_score_stocks(pit_table_by_ticker, prices_local, as_of, financials=(), splits=None,
                             dividends=None, fx_to_reporting=None):
    """Section 5 stock measures and the weighted percentile score (growth 40 / quality 30 / valuation 30).

    pit_table_by_ticker: {ticker: table from `point_in_time` (EDGAR, PIT) or
    `yfinance_table` (current, attrs point_in_time=False)}; a None table gives
    a row of NaN with a flag. splits, dividends, fx_to_reporting: optional
    {ticker: ...} dicts (see `stock_measures`). The DCF/Grinold-Kroner
    valuation inputs are forward-thesis only and not part of this score.
    Columns: measures, group scores, fundamental_score (0-1), fundamentals_pit, flags.
    """
    rows = []
    for tk, table in pit_table_by_ticker.items():
        px = prices_local[tk] if tk in prices_local else None
        try:
            m, fl = stock_measures(table, px, as_of, tk in set(financials),
                                   (splits or {}).get(tk), (dividends or {}).get(tk),
                                   (fx_to_reporting or {}).get(tk, 1.0))
        except Exception as e:  # never crash a screening run on one name
            m, fl = {}, [f"fundamentals error: {type(e).__name__}: {e}"]
        pit = bool(table is not None and table.attrs.get("point_in_time", True) and len(table))
        if table is not None and not table.attrs.get("point_in_time", True):
            fl.insert(0, "fundamentals not point-in-time")
        rows.append({"ticker": tk, **m, "fundamentals_pit": pit, "fund_flags": "; ".join(fl)})
    df = pd.DataFrame(rows).set_index("ticker") if rows else pd.DataFrame()
    if df.empty:
        return df
    for c in [c for _, (_, cols) in STOCK_GROUPS.items() for c in cols]:
        if c not in df:
            df[c] = np.nan
    return df.join(group_score(df, STOCK_GROUPS))


def rating_to_score(r):
    """Letter rating (S&P/Fitch style, Moody's Baa1 etc. mapped) -> 1 (AAA) .. 22 (D); numbers pass."""
    if r is None or (isinstance(r, float) and np.isnan(r)):
        return np.nan
    if isinstance(r, (int, float)):
        return float(r)
    s = str(r).strip().upper()
    moody = {"AAA": "AAA", "AA1": "AA+", "AA2": "AA", "AA3": "AA-", "A1": "A+", "A2": "A", "A3": "A-",
             "BAA1": "BBB+", "BAA2": "BBB", "BAA3": "BBB-", "BA1": "BB+", "BA2": "BB", "BA3": "BB-",
             "B1": "B+", "B2": "B", "B3": "B-", "CAA1": "CCC+", "CAA2": "CCC", "CAA3": "CCC-"}
    s = moody.get(s, s)
    return float(RATINGS.index(s) + 1) if s in RATINGS else pd.to_numeric(s, errors="coerce")


def expected_fx_loss(infl_local, infl_us, rate_local=None, rate_us=None):
    """Expected annual depreciation of the local currency vs USD (method.md s5 carry).

    Relative PPP: 1 - (1 + pi_us) / (1 + pi_local); UIP: 1 - (1 + r_us) / (1 + r_local).
    The average of the two when both are given, else PPP alone. Decimals.
    """
    ppp = 1 - (1 + infl_us) / (1 + infl_local)
    if rate_local is None or rate_us is None:
        return ppp
    return (ppp + (1 - (1 + rate_us) / (1 + rate_local))) / 2


def normalise_expense(s):
    """Expense ratios as decimals: a column whose maximum exceeds 0.05 is read as percent."""
    s = pd.to_numeric(s, errors="coerce")
    return s / 100 if s.max(skipna=True) > 0.05 else s


def fundamental_score_bonds(funds_table):
    """EM bond fund score (method.md s5): carry 40 / credit and country 30 / cost and liquidity 15 /
    diversification 15.

    Input columns (decimals; any may be missing, the measure is then skipped):
    ytm, expected_fx_loss (local-currency funds; 0 assumed for hard currency,
    see `expected_fx_loss`), local_currency (bool), expense_ratio, avg_rating
    (letter or 1-22), country_max_weight, debt_gdp, current_account_gdp,
    inflation, real_yield, aum_usd_bn, bid_ask, traded_value_usd_m,
    corr_equity (in-sample correlation with IVW and EFG/EEM, mean).
    carry = ytm - expected_fx_loss - expense_ratio.
    """
    df = funds_table.copy()
    flags = pd.Series("", index=df.index, dtype=object)
    if "expense_ratio" in df:
        df["expense_ratio"] = normalise_expense(df["expense_ratio"])
    if "ytm" in df:
        loss = df["expected_fx_loss"] if "expected_fx_loss" in df else pd.Series(np.nan, index=df.index)
        local = df["local_currency"].fillna(False).astype(bool) if "local_currency" in df \
            else pd.Series(False, index=df.index)
        missing = local & loss.isna()
        flags[missing] += "local-currency fund without expected FX loss (carry not computed); "
        loss = loss.where(local, loss.fillna(0.0))
        exp = df["expense_ratio"].fillna(0.0) if "expense_ratio" in df else 0.0
        df["carry"] = df["ytm"] - loss - exp
    else:
        flags += "no ytm column: carry not computed; "
    if "avg_rating" in df:
        df["rating_score"] = df["avg_rating"].map(rating_to_score)
    used = [c for _, (_, cols) in BOND_GROUPS.items() for c in cols if c in df and df[c].notna().any()]
    flags += "inputs used: " + ",".join(used)
    out = df.join(group_score(df, BOND_GROUPS))
    out["fund_flags"] = flags.str.rstrip("; ")
    return out


def inflation_beta(r, cpi_monthly, min_months=36):
    """OLS slope of monthly returns on the monthly change in year-on-year CPI inflation.

    cpi_monthly: CPI index level (any monthly dates; moved to month end).
    Returns (beta, months). A beta of 2 means +1pp of inflation surprise went
    with +2% return that month.
    """
    c = cpi_monthly.dropna().copy()
    c.index = c.index + pd.offsets.MonthEnd(0)
    c = c.groupby(level=0).last()
    dpi = (c / c.shift(12) - 1).diff()
    both = pd.concat([r, dpi], axis=1).dropna()
    if len(both) < min_months or both.iloc[:, 1].std() == 0:
        return np.nan, len(both)
    x, y = both.iloc[:, 1].to_numpy(), both.iloc[:, 0].to_numpy()
    return float(np.polyfit(x, y, 1)[0]), len(both)


def fundamental_score_other(monthly_usd, cpi_monthly, as_of="2017-12-31", bench_monthly=None, costs=None):
    """Other-sleeve score (method.md s5): inflation 40 / correlation with ACWX and EMB 30 / cost 30.

    Inflation: `inflation_beta` on months up to as_of, plus the 2021-12-31 to
    2022-10-31 return, which is used only when that window ends on or before
    as_of (otherwise it is reported in `ret_2022` but excluded from the score
    and flagged). Correlations over months up to as_of (36 minimum) with
    bench_monthly columns ACWX and EMB. costs: optional frame by ticker with
    expense_ratio and roll_cost (annual carry/roll cost, positive = cost).
    """
    as_of = pd.Timestamp(as_of)
    rows = []
    a, b = (pd.Timestamp(x) for x in INFLATION_WINDOW)
    for tk in monthly_usd.columns:
        r = monthly_usd[tk].dropna()
        ins = r.loc[:as_of]
        beta, n = inflation_beta(ins, cpi_monthly) if cpi_monthly is not None else (np.nan, 0)
        win = r[(r.index > a) & (r.index <= b)]
        ret22 = float((1 + win).prod() - 1) if len(win) == 10 else np.nan
        rec = {"ticker": tk, "inflation_beta": beta, "inflation_beta_months": n,
               "ret_2022_info": ret22, "ret_2022": ret22 if b <= as_of else np.nan}
        fl = [] if b <= as_of else ["2022 window after as_of: reported, not scored"]
        for col in ("ACWX", "EMB"):
            key = f"corr_{col.lower()}"
            if bench_monthly is not None and col in bench_monthly and col != tk:
                both = pd.concat([ins, bench_monthly[col].loc[:as_of]], axis=1).dropna()
                rec[key] = float(both.corr().iloc[0, 1]) if len(both) >= 36 else np.nan
            else:
                rec[key] = np.nan
                fl.append(f"no {col} correlation")
        rec["fund_flags"] = "; ".join(fl)
        rows.append(rec)
    df = pd.DataFrame(rows).set_index("ticker")
    if costs is not None:
        c = costs.copy()
        if "expense_ratio" in c:
            c["expense_ratio"] = normalise_expense(c["expense_ratio"])
        df = df.join(c[[x for x in ("expense_ratio", "roll_cost") if x in c]], how="left")
    return df.join(group_score(df, OTHER_GROUPS))
