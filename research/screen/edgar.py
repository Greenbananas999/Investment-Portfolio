"""SEC EDGAR companyfacts reader and the point-in-time rule (method.md section 5).

Conventions:
- Annual facts only: fp == "FY" and form in 10-K, 20-F, 40-F, 10-KT and their
  amendments. Flow items need a duration of 350-380 days (10-K files also
  carry the fourth quarter with fp == "FY"); balance-sheet items are instants.
- `fy` in the output is the fiscal year of the value (calendar year of its
  period end); EDGAR's own `fy` (the filing's year) is kept as `fy_filing`.
- Tag aliases (data_request.md section 6) are unioned in priority order; when
  one filing tags the same period twice, the first alias wins.
- Monetary values use the company's dominant reporting currency (the unit
  with most annual facts); USD convenience translations of 20-F filers are
  dropped when another currency dominates.
- Per-share items and share counts are in the share units of their filing
  date; `split_events` / `split_factor` convert them to today's units, which
  is the unit Yahoo's split-adjusted prices use.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

CANON = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "Revenue",
                # older us-gaap tags still used in 2010-2017 filings (planner, 2026-11-07)
                "SalesRevenueGoodsNet", "SalesRevenueServicesNet", "RevenuesNetOfInterestExpense",
                "OilAndGasRevenue", "InterestAndDividendIncomeOperating"],
    "net_income": ["NetIncomeLoss", "ProfitLossAttributableToOwnersOfParent", "ProfitLoss"],
    "operating_income": ["OperatingIncomeLoss", "ProfitLossFromOperatingActivities"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
            "CashFlowsFromUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment",
              "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
              "PurchaseOfPropertyPlantAndEquipment"],
    "da": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
           "DepreciationAmortizationAndAccretionNet", "AdjustmentsForDepreciationAndAmortisationExpense",
           "DepreciationAndAmortisationExpense"],
    "income_tax": ["IncomeTaxExpenseBenefit", "IncomeTaxExpenseContinuingOperations"],
    "pretax_income": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                      "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
                      "ProfitLossBeforeTax"],
    "eps_diluted": ["EarningsPerShareDiluted", "DilutedEarningsLossPerShare"],
    "debt": ["LongTermDebt", "DebtLongtermAndShorttermCombinedAmount", "Borrowings"],
    "debt_noncurrent": ["LongTermDebtNoncurrent", "LongtermBorrowings", "NoncurrentPortionOfNoncurrentBorrowings"],
    "bonds_noncurrent": ["NoncurrentPortionOfNoncurrentBondsIssued"],
    "debt_current": ["LongTermDebtCurrent", "DebtCurrent", "CurrentPortionOfLongtermBorrowings"],
    "debt_short": ["CommercialPaper", "ShortTermBorrowings"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalents"],
    "equity": ["StockholdersEquity", "EquityAttributableToOwnersOfParent", "Equity",
               "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "shares": ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding", "NumberOfSharesOutstanding"],
}
FLOW = {"revenue", "net_income", "operating_income", "cfo", "capex", "da", "income_tax",
        "pretax_income", "eps_diluted"}
SHARE_UNIT = {"shares"}
PER_SHARE = {"eps_diluted"}
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A", "10-KT", "10-KT/A"}
NICE_SPLITS = np.array([1.5, 2, 3, 4, 5, 6, 7, 8, 10, 15, 20, 25, 50, 100])
FACT_COLUMNS = ["tag", "fy", "end", "value", "filed", "form", "unit", "start", "fy_filing",
                "accn", "source_tag", "priority"]


def read_companyfacts(path):
    """Load a companyfacts JSON file; None if missing or unreadable."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def edgar_path(edgar_dir, cik):
    """data/research/edgar/<CIK>.json, accepting CIK0000320193.json, 0000320193.json or 320193.json."""
    if cik is None or (isinstance(cik, float) and np.isnan(cik)) or str(cik).strip() in ("", "<NA>", "nan"):
        return None
    digits = "".join(ch for ch in str(cik) if ch.isdigit())
    if not digits:
        return None
    c10 = digits.zfill(10)
    for name in (f"CIK{c10}.json", f"{c10}.json", f"{int(digits)}.json", f"CIK{int(digits)}.json"):
        p = Path(edgar_dir) / name
        if p.exists():
            return p
    return None


def _all_tags(cj):
    facts = cj.get("facts", {}) if isinstance(cj, dict) else {}
    out = {}
    for tax in facts.values():
        for tag, body in tax.items():
            out.setdefault(tag, body)
    return out


def _currency(tags):
    counts = {}
    for canon, aliases in CANON.items():
        if canon in SHARE_UNIT or canon in PER_SHARE:
            continue
        for a in aliases:
            for unit, vals in tags.get(a, {}).get("units", {}).items():
                if "/" in unit or unit in ("shares", "pure"):
                    continue
                counts[unit] = counts.get(unit, 0) + sum(1 for v in vals if v.get("fp") == "FY")
    return max(counts, key=counts.get) if counts else None


def edgar_facts(cik_json):
    """Tidy annual facts [tag, fy, end, value, filed, form, unit, ...] from companyfacts JSON.

    Implements the data_request.md section 6 tag union for method.md section 5:
    canonical tags revenue, net_income, operating_income, cfo, capex, debt,
    cash, equity, shares (plus da, income_tax, pretax_income, eps_diluted and
    debt components used by the quality measures). `cik_json` may be a dict
    or a path. Returns an empty frame with the same columns if nothing usable.
    """
    cj = read_companyfacts(cik_json) if isinstance(cik_json, (str, Path)) else cik_json
    tags = _all_tags(cj or {})
    ccy = _currency(tags)
    rows = []
    for canon, aliases in CANON.items():
        for prio, a in enumerate(aliases):
            units = tags.get(a, {}).get("units", {})
            for unit, vals in units.items():
                if canon in SHARE_UNIT:
                    if unit != "shares":
                        continue
                elif canon in PER_SHARE:
                    if not unit.endswith("/shares") or (ccy and unit.split("/")[0] != ccy):
                        continue
                elif unit != ccy:
                    continue
                for v in vals:
                    if v.get("fp") != "FY" or v.get("form") not in ANNUAL_FORMS or v.get("end") is None:
                        continue
                    rows.append((canon, v.get("end"), v.get("start"), v.get("val"), v.get("filed"),
                                 v.get("form"), unit, v.get("fy"), v.get("accn"), a, prio))
    if not rows:
        return pd.DataFrame(columns=FACT_COLUMNS)
    df = pd.DataFrame(rows, columns=["tag", "end", "start", "value", "filed", "form", "unit",
                                     "fy_filing", "accn", "source_tag", "priority"])
    for c in ("end", "start", "filed"):
        df[c] = pd.to_datetime(df[c], errors="coerce", format="%Y-%m-%d")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    days = (df["end"] - df["start"]).dt.days
    flow = df["tag"].isin(FLOW)
    ok = df["end"].notna() & df["value"].notna() & np.where(flow, days.between(350, 380), df["start"].isna())
    df = df[ok].copy()
    if df.empty:
        return pd.DataFrame(columns=FACT_COLUMNS)
    df["fy"] = df["end"].dt.year
    df = df.sort_values(["tag", "end", "accn", "priority"]).drop_duplicates(["tag", "end", "accn"])
    return df[FACT_COLUMNS].reset_index(drop=True)


def point_in_time(facts, as_of):
    """Latest fiscal-year values known on `as_of` (method.md section 5 point-in-time rule).

    For each canonical tag and period end, the value from the latest filing
    with `filed` <= as_of (restatements made by then are used, later ones are
    not). Rows are fiscal-year ends (period ends of annual flow items) up to
    as_of; balance-sheet items are taken at those ends. Shares missing at a
    year end fall back to the cover-page count dated within 150 days after it.
    Adds `debt_total` = debt (or noncurrent + current + bonds) + short-term
    debt, `filed` (latest filing used in the row), `first_filed` (the year's
    original filing, i.e. when the year became known) and `filed_<tag>` for
    eps_diluted and shares (their share units). Index: `end`. Empty if none.
    """
    as_of = pd.Timestamp(as_of)
    cols = list(CANON) + ["debt_total", "fy", "filed", "first_filed", "filed_eps_diluted", "filed_shares"]
    if facts is None or len(facts) == 0:
        return pd.DataFrame(columns=cols).rename_axis("end")
    f = facts[(facts["filed"] <= as_of) & (facts["end"] <= as_of)]
    if f.empty:
        return pd.DataFrame(columns=cols).rename_axis("end")
    first = f.groupby(["tag", "end"])["filed"].min()
    latest = f.sort_values(["filed", "priority"], ascending=[True, False]).groupby(["tag", "end"]).tail(1)
    ends = sorted(latest.loc[latest["tag"].isin(FLOW), "end"].unique())
    if not ends:
        return pd.DataFrame(columns=cols).rename_axis("end")
    wide = latest.pivot(index="end", columns="tag", values="value")
    filed = latest.pivot(index="end", columns="tag", values="filed")
    out = wide.reindex(pd.DatetimeIndex(ends)).reindex(columns=list(CANON))
    out.index.name = "end"
    for t in ("eps_diluted", "shares"):
        out[f"filed_{t}"] = filed[t].reindex(out.index) if t in filed else pd.NaT
    sh = latest[latest["tag"] == "shares"].sort_values("end")
    for e in out.index[out["shares"].isna()]:
        cand = sh[(sh["end"] > e) & (sh["end"] <= e + pd.Timedelta(days=150))]
        if len(cand):
            out.loc[e, "shares"] = cand["value"].iloc[0]
            out.loc[e, "filed_shares"] = cand["filed"].iloc[0]
    comp = out[["debt_noncurrent", "debt_current", "bonds_noncurrent"]].sum(axis=1, min_count=1)
    out["debt_total"] = out["debt"].fillna(comp) + out["debt_short"].fillna(0.0)
    out["fy"] = out.index.year
    fl = filed.reindex(out.index)
    out["filed"] = fl.max(axis=1)
    out["first_filed"] = first.unstack(0).reindex(out.index).min(axis=1)
    out.attrs["currency"] = facts["unit"][~facts["tag"].isin(SHARE_UNIT | PER_SHARE)].mode().iloc[0] \
        if (~facts["tag"].isin(SHARE_UNIT | PER_SHARE)).any() else None
    out.attrs["as_of"] = str(as_of.date())
    out.attrs["point_in_time"] = True
    return out


def split_events(cik_json):
    """Stock splits inferred from reported share counts (all forms, first-reported values).

    A jump in shares outstanding between consecutive reporting dates within 8%
    of a common split ratio (1.5, 2, 3, 4, 5, 7, 10, ...) or its inverse is a
    split, dated at the midpoint of the two dates. Returns Series ratio
    (new shares per old share) indexed by the estimated split date.
    """
    cj = read_companyfacts(cik_json) if isinstance(cik_json, (str, Path)) else cik_json
    tags = _all_tags(cj or {})
    pts = []
    for a in ("EntityCommonStockSharesOutstanding", "CommonStockSharesOutstanding"):
        for v in tags.get(a, {}).get("units", {}).get("shares", []):
            pts.append((v.get("end"), v.get("filed"), v.get("val")))
    if not pts:
        return pd.Series(dtype=float)
    df = pd.DataFrame(pts, columns=["end", "filed", "val"])
    df["end"] = pd.to_datetime(df["end"], errors="coerce")
    df["filed"] = pd.to_datetime(df["filed"], errors="coerce")
    df = df.dropna().sort_values(["end", "filed"]).drop_duplicates("end", keep="first")
    df = df[df["val"] > 0]
    out = {}
    v, e = df["val"].to_numpy(float), df["end"].to_numpy()
    for i in range(1, len(v)):
        r = v[i] / v[i - 1]
        for cand in (r, 1 / r):
            j = np.argmin(np.abs(NICE_SPLITS - cand))
            if cand > 1.4 and abs(cand / NICE_SPLITS[j] - 1) < 0.08:
                ratio = NICE_SPLITS[j] if cand == r else 1 / NICE_SPLITS[j]
                mid = pd.Timestamp(e[i - 1]) + (pd.Timestamp(e[i]) - pd.Timestamp(e[i - 1])) / 2
                out[mid] = float(ratio)
    return pd.Series(out, dtype=float).sort_index()


def split_factor(splits, date):
    """Product of split ratios after `date`: multiply a share count of that date
    (divide a per-share value) to express it in today's share units."""
    if splits is None or len(splits) == 0 or pd.isna(date):
        return 1.0
    return float(np.prod(splits[splits.index > pd.Timestamp(date)].to_numpy())) or 1.0


YF_ROWS = {
    "revenue": ("income_stmt", ["Total Revenue", "Operating Revenue"]),
    "net_income": ("income_stmt", ["Net Income", "Net Income Common Stockholders"]),
    "operating_income": ("income_stmt", ["Operating Income", "Total Operating Income As Reported"]),
    "da": ("income_stmt", ["Reconciled Depreciation"]),
    "income_tax": ("income_stmt", ["Tax Provision"]),
    "pretax_income": ("income_stmt", ["Pretax Income"]),
    "eps_diluted": ("income_stmt", ["Diluted EPS"]),
    "cfo": ("cashflow", ["Operating Cash Flow"]),
    "capex": ("cashflow", ["Capital Expenditure"]),
    "debt_total": ("balance_sheet", ["Total Debt"]),
    "cash": ("balance_sheet", ["Cash And Cash Equivalents"]),
    "equity": ("balance_sheet", ["Stockholders Equity", "Common Stock Equity"]),
    "shares": ("balance_sheet", ["Ordinary Shares Number", "Share Issued"]),
}


def yfinance_table(fund_dir, currency=None):
    """Current yfinance statements (up to 4 years) in the `point_in_time` layout, flagged
    not point-in-time (data_request.md section 7). `filed` = fiscal year end + 90 days
    (method.md section 5); per-share values are already in today's share units
    (yfinance restates for splits), so `filed_<tag>` is set to today."""
    d = Path(fund_dir)
    frames = {}
    for name in ("income_stmt", "cashflow", "balance_sheet"):
        p = d / f"{name}.csv"
        if p.exists():
            try:
                frames[name] = pd.read_csv(p, index_col=0)
            except (OSError, ValueError):
                pass
    if not frames:
        return None
    data = {}
    for canon, (src, names) in YF_ROWS.items():
        df = frames.get(src)
        if df is None:
            continue
        for nm in names:
            if nm in df.index:
                s = pd.to_numeric(df.loc[nm], errors="coerce")
                s.index = pd.to_datetime(s.index, errors="coerce")
                data[canon] = s[s.index.notna()]
                break
    if "revenue" not in data:
        return None
    out = pd.DataFrame(data).sort_index()
    out = out[out["revenue"].notna()]
    if "capex" in out:
        out["capex"] = out["capex"].abs()
    for c in list(CANON) + ["debt_total"]:
        if c not in out:
            out[c] = np.nan
    out.index.name = "end"
    out["fy"] = out.index.year
    out["filed"] = out.index + pd.Timedelta(days=90)
    out["first_filed"] = out["filed"]
    today = pd.Timestamp.today().normalize()
    out["filed_eps_diluted"] = today
    out["filed_shares"] = today
    out.attrs.update(currency=currency, point_in_time=False, as_of="current")
    return out
