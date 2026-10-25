"""Pull the handful of numbers the valuation models need out of Yahoo statements.

Yahoo row names change between versions, so each item tries several labels.
Values are in the company's reporting currency; `fx_to_price` converts to the
currency the shares trade in when the two differ (e.g. TSM ADR vs TWD books).
"""

import numpy as np
import pandas as pd


def _row(df, *names):
    if df is None:
        return None
    for n in names:
        if n in df.index:
            s = pd.to_numeric(df.loc[n], errors="coerce")
            s.index = pd.to_datetime(s.index, errors="coerce")
            return s.dropna().sort_index()
    return None


def extract(f):
    info = f.get("info", {})
    cf, bs, inc = f.get("cashflow"), f.get("balance_sheet"), f.get("income_stmt")
    fcf = _row(cf, "Free Cash Flow")
    if fcf is None:
        ocf = _row(cf, "Operating Cash Flow", "Total Cash From Operating Activities")
        capex = _row(cf, "Capital Expenditure", "Capital Expenditures")
        fcf = (ocf + capex) if ocf is not None and capex is not None else None
    interest = _row(inc, "Interest Expense", "Interest Expense Non Operating")
    debt = _row(bs, "Total Debt")
    cash = _row(bs, "Cash Cash Equivalents And Short Term Investments",
                "Cash And Cash Equivalents")
    shares = _row(bs, "Ordinary Shares Number", "Share Issued")
    revenue = _row(inc, "Total Revenue")
    net_income = _row(inc, "Net Income", "Net Income Common Stockholders")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    mcap = info.get("marketCap")
    div_rate = info.get("dividendRate") or info.get("trailingAnnualDividendRate") or 0.0
    return {
        "fcf": fcf, "interest": interest, "revenue": revenue, "net_income": net_income,
        "ttm_net_income": info.get("netIncomeToCommon"),
        "debt": float(debt.iloc[-1]) if debt is not None and len(debt) else 0.0,
        "cash": float(cash.iloc[-1]) if cash is not None and len(cash) else 0.0,
        "shares": shares,
        "price": price, "market_cap": mcap,
        "dividend_yield": (div_rate / price) if price else 0.0,
        "forward_pe": info.get("forwardPE"), "trailing_pe": info.get("trailingPE"),
        "financial_currency": info.get("financialCurrency"),
        "currency": info.get("currency"),
        "analyst_growth": analyst_growth(f),
        "revenue_growth_hist": _cagr(revenue),
    }


def _cagr(s):
    if s is None or len(s) < 2 or s.iloc[0] <= 0 or s.iloc[-1] <= 0:
        return None
    years = (s.index[-1] - s.index[0]).days / 365.25
    return float((s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1) if years > 0 else None


def forward_net_income(fd):
    """Next-12-month net income implied by market cap / forward P/E."""
    pe, mcap = fd["forward_pe"], fd["market_cap"]
    return mcap / pe if pe and mcap and pe > 0 else None


def fcf_conversion(fd, years=4):
    """Sum of free cash flow / sum of net income over the last few fiscal years."""
    f, n = fd["fcf"], fd["net_income"]
    if f is None or n is None:
        return None
    df = pd.concat([f, n], axis=1, join="inner").dropna().iloc[-years:]
    return float(df.iloc[:, 0].sum() / df.iloc[:, 1].sum()) if df.iloc[:, 1].sum() > 0 else None


def analyst_growth(f):
    """Analyst long-term (+5y) growth, else next-year growth. None if neither."""
    for name in ("growth_estimates", "earnings_estimate"):
        df = f.get(name)
        if df is None or len(df) == 0:
            continue
        num = df.apply(pd.to_numeric, errors="coerce")
        col = next((c for c in ("stockTrend", "stock", "growth") if c in num.columns), num.columns[0])
        for row in ("+5y", "LTG", "+1y", "0y"):
            if row in num.index and np.isfinite(num.loc[row, col]):
                return float(num.loc[row, col]), row
    return None


def net_dilution(shares, max_step=0.05):
    """Average annual change in share count (negative = buybacks).

    Year-on-year moves over 5% are skipped as share-class reclassifications
    (Yahoo's 2025 Samsung count jumps when preferred shares are folded in).
    """
    if shares is None or len(shares) < 2:
        return 0.0
    chg = shares.pct_change().dropna()
    chg = chg[chg.abs() <= max_step]
    return float(chg.mean()) if len(chg) else 0.0
