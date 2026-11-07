"""Hard screens per position type (method.md sections 2 and 4).

Everything is evaluated with data up to as_of, except the rules method.md
states on today's data (market cap "today") and `months_total`, which only
feeds the "short history" flag and never the pass/fail.
A rule whose input is missing is not failed: it is listed in `flags` as
"not checked", so the screener can see what still needs a source.
"""

import numpy as np
import pandas as pd

from .fundamental import normalise_expense
from .prices import MIN_MONTHS, SCREENED_ROLES, SHORT_HISTORY_MONTHS, monthly_returns

RULES = {
    "us_growth_stock": {"kind": "stock", "us": True, "mcap_today": 10.0, "mcap_asof": 2.0,
                        "traded_value": 20.0, "rev_cagr": 0.08, "pit_required": True},
    "intl_growth_stock": {"kind": "stock", "us": False, "mcap_today": 10.0, "mcap_asof": None,
                          "traded_value": 10.0, "rev_cagr": 0.08, "pit_required": False},
    "em_bond": {"kind": "fund", "aum": 0.2, "expense": 0.0100, "daily_liquidity": True},
    "other": {"kind": "fund", "aum": 0.2, "expense": 0.0075},
}
US_CODES = {"US", "USA", "UNITED STATES", "U.S.", "UNITED STATES OF AMERICA"}


def _num(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return np.nan
    return x


def history_counts(daily_usd, as_of):
    """Monthly return counts per ticker: up to as_of, and in total; first price date."""
    m_in = monthly_returns(daily_usd.loc[:pd.Timestamp(as_of)])
    m_all = monthly_returns(daily_usd)
    first = daily_usd.apply(lambda s: s.first_valid_index())
    return pd.DataFrame({"months_in_sample": m_in.notna().sum(), "months_total": m_all.notna().sum(),
                         "first_price": first})


def hard_screens(universe, daily_usd, funds=None, as_of="2017-12-31", fundamentals=None,
                 traded_value=None, mcap_asof=None):
    """Section 4 hard screens for each universe row; returns [ticker, passed, reasons, flags, ...].

    universe: rows from `load_universe` (any types; rules by row type).
    daily_usd: daily USD prices. funds: funds.csv frame (ticker index or
    column) with aum_usd_bn and expense_ratio; universe columns are the
    fallback. fundamentals: frame by ticker with rev_cagr_3y and
    fundamentals_pit (from `fundamental_score_stocks`). traded_value: average
    daily traded value in USD millions to as_of, by ticker. mcap_asof: market
    cap in USD bn at as_of, by ticker.
    Rules: at least 60 monthly returns with month end <= as_of; stocks: US or
    non-US domicile, market cap today >= $10B, at as_of >= $2B (US), traded
    value >= $20M (US) / $10M (intl), 3-year revenue CAGR >= 8% (US: point-in-time
    EDGAR only, else not checked; intl: current statements allowed, flagged); funds: AUM
    >= $200M, expense <= 1.00% (EM bonds) / 0.75% (other). Only roles
    candidate and faded_leader are screened; other roles fail with a reason.
    """
    as_of = pd.Timestamp(as_of)
    hist = history_counts(daily_usd, as_of) if len(daily_usd.columns) else pd.DataFrame()
    if funds is not None and "ticker" in getattr(funds, "columns", []):
        funds = funds.set_index("ticker")
    exp_f = normalise_expense(funds["expense_ratio"]) if funds is not None and "expense_ratio" in funds \
        else pd.Series(dtype=float)
    uix = universe.set_index("ticker")
    exp_u = normalise_expense(uix["expense_ratio"]) if "expense_ratio" in uix else pd.Series(dtype=float)
    rows = []
    for _, row in universe.iterrows():
        t, typ = row["ticker"], row["type"]
        rule = RULES.get(typ)
        reasons, flags = [], []
        rec = {"ticker": t, "name": row.get("name"), "type": typ, "role": row.get("role"),
               "country": row.get("country"), "currency": row.get("currency")}
        if isinstance(row.get("universe_flags"), str) and row["universe_flags"]:
            flags.append(row["universe_flags"])
        if rule is None:
            reasons.append(f"type {typ}: no hard screen defined (overlays are modelled in Phase 3)")
        if row.get("role") not in SCREENED_ROLES:
            reasons.append(f"role={row.get('role')}: not screened")
        # history (method.md section 2)
        if t in hist.index and pd.notna(hist.loc[t, "first_price"]):
            n_in, n_all = int(hist.loc[t, "months_in_sample"]), int(hist.loc[t, "months_total"])
            rec.update(months_in_sample=n_in, months_total=n_all,
                       first_price=hist.loc[t, "first_price"].date().isoformat())
            if n_in < MIN_MONTHS:
                reasons.append(f"{n_in} monthly returns to {as_of.date()} (< {MIN_MONTHS})")
            if n_all < SHORT_HISTORY_MONTHS:
                flags.append(f"short history ({n_all} < {SHORT_HISTORY_MONTHS} months)")
        else:
            rec.update(months_in_sample=0, months_total=0, first_price=None)
            reasons.append("no USD price data")
        if rule and rule["kind"] == "stock":
            _stock_rules(row, rule, rec, reasons, flags, fundamentals, traded_value, mcap_asof)
        elif rule and rule["kind"] == "fund":
            aum = _num(funds.loc[t, "aum_usd_bn"]) if funds is not None and t in funds.index \
                and "aum_usd_bn" in funds else np.nan
            if pd.isna(aum):
                aum = _num(row.get("aum_usd_bn"))
            exp = exp_f.get(t, np.nan) if t in exp_f.index else np.nan
            if pd.isna(exp) and t in exp_u.index:
                exp = exp_u.get(t, np.nan)
            rec.update(aum_usd_bn=aum, expense_ratio=exp)
            if pd.isna(aum):
                flags.append("AUM not checked (no data)")
            else:
                flags.append("AUM is the latest figure, not at as_of")
                if aum < rule["aum"]:
                    reasons.append(f"AUM ${aum:.2f}bn < ${rule['aum']}bn")
            if pd.isna(exp):
                flags.append("expense ratio not checked (no data)")
            elif exp > rule["expense"] + 1e-12:
                reasons.append(f"expense ratio {exp:.2%} > {rule['expense']:.2%}")
            if rule.get("daily_liquidity"):
                flags.append("daily liquidity assumed (ETF or open-end fund with daily dealing)")
        rec["passed"] = not reasons
        rec["reasons"] = "; ".join(reasons)
        rec["flags"] = "; ".join(flags)
        rows.append(rec)
    cols = ["ticker", "name", "type", "role", "country", "currency", "passed", "reasons", "flags",
            "months_in_sample", "months_total", "first_price", "market_cap_usd_bn", "mcap_asof_usd_bn",
            "traded_value_usd_m", "rev_cagr_3y", "fundamentals_pit", "aum_usd_bn", "expense_ratio"]
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df:
            df[c] = np.nan
    return df[cols + [c for c in df.columns if c not in cols]]


def _stock_rules(row, rule, rec, reasons, flags, fundamentals, traded_value, mcap_asof):
    t = row["ticker"]
    country = str(row.get("country") or "").strip().upper()
    is_us = country in US_CODES
    if not country or country == "<NA>":
        flags.append("domicile not checked (no country)")
    elif rule["us"] and not is_us:
        reasons.append(f"domicile {country} is not US")
    elif not rule["us"] and is_us:
        reasons.append("US domicile in the international list")
    mc = _num(row.get("market_cap_usd_bn"))
    rec["market_cap_usd_bn"] = mc
    if pd.isna(mc):
        flags.append("market cap today not checked (no data)")
    elif mc < rule["mcap_today"]:
        reasons.append(f"market cap today ${mc:.1f}bn < ${rule['mcap_today']:.0f}bn")
    if rule["mcap_asof"] is not None:
        ma = _num(mcap_asof.get(t)) if mcap_asof is not None else np.nan
        rec["mcap_asof_usd_bn"] = ma
        if pd.isna(ma):
            flags.append("market cap at as_of not checked (no point-in-time shares)")
        elif ma < rule["mcap_asof"]:
            reasons.append(f"market cap at as_of ${ma:.1f}bn < ${rule['mcap_asof']:.0f}bn")
    tv = _num(traded_value.get(t)) if traded_value is not None else np.nan
    rec["traded_value_usd_m"] = tv
    if pd.isna(tv):
        flags.append("traded value not checked (no volume data)")
    elif tv < rule["traded_value"]:
        reasons.append(f"traded value ${tv:.1f}M/day < ${rule['traded_value']:.0f}M")
    f = fundamentals.loc[t] if fundamentals is not None and t in fundamentals.index else None
    g = _num(f.get("rev_cagr_3y")) if f is not None else np.nan
    pit = bool(f.get("fundamentals_pit")) if f is not None and pd.notna(f.get("fundamentals_pit")) else False
    rec["rev_cagr_3y"], rec["fundamentals_pit"] = g, pit
    if pd.isna(g):
        flags.append("revenue CAGR not checked (no fundamentals)")
    elif not pit and rule["pit_required"]:
        flags.append("revenue CAGR not checked (US rule needs point-in-time EDGAR data)")
    else:
        if not pit:
            flags.append("fundamentals not point-in-time")
        if g < rule["rev_cagr"]:
            reasons.append(f"3y revenue CAGR {g:.1%} < {rule['rev_cagr']:.0%}")
