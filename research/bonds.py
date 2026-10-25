"""Sovereign bonds: total-return backtest from yields, and yield-based expected returns.

A constant-maturity bond is bought at par each month (coupon = that month's
yield), held one month, repriced at the next month's yield with one month
less to maturity, and sold. This is the standard way to build a bond index
when only a yield series is available.
"""

import numpy as np
import pandas as pd

from . import config, fxview, metrics


def price(coupon, y, maturity, freq):
    """Clean price per 100 face of a bullet bond (fractional periods allowed)."""
    n = maturity * freq
    c = coupon / freq * 100
    i = y / freq
    if abs(i) < 1e-12:
        return c * n + 100
    disc = (1 + i) ** -n
    return c * (1 - disc) / i + 100 * disc


def duration_convexity(y, maturity, freq):
    """Modified duration and convexity of a par bond (numerical)."""
    h = 1e-4
    p0, pu, pd_ = price(y, y, maturity, freq), price(y, y + h, maturity, freq), price(y, y - h, maturity, freq)
    dur = (pd_ - pu) / (2 * h * p0)
    conv = (pu + pd_ - 2 * p0) / (h * h * p0)
    return dur, conv


def total_returns(yields, maturity, freq):
    """Monthly local-currency total returns from a monthly yield series (decimals)."""
    y = yields.dropna()
    out = []
    for prev, cur in zip(y.iloc[:-1], y.iloc[1:]):
        p1 = price(prev, cur, maturity - 1 / 12, freq)
        out.append((p1 + prev * 100 / 12) / 100 - 1)
    return pd.Series(out, index=y.index[1:])


def returns(bond, ds):
    """Monthly (local, usd) returns, or (None, None) if the yield series is missing."""
    y = ds.monthly_yield(bond.yield_series)
    if y is None or len(y) < 24:
        return None, None
    local = total_returns(y, bond.maturity_years, bond.coupon_freq)
    fx = ds.monthly_fx()[bond.currency].reindex(local.index.union(y.index)).ffill()
    fxr = fx.pct_change().reindex(local.index)
    usd = ((1 + local) * (1 + fxr) - 1).dropna()
    return local, usd


def expected(bond, ds, a, horizon=None):
    """Yield-based expected annual return over the horizon, local and USD.

    Hold-period return for a bond held H years and sold at yield y_H:
        coupons (approx y0 per year) + price change at sale.
    Scenarios: yields unchanged (carry), yields revert halfway to a
    fair value of (local real rate 1.5% + expected inflation), and +/-200 bp
    (Turkey: +/-800 bp) shocks.
    """
    h = horizon or a.horizon_years
    y0 = ds.latest_yield(bond.yield_series)
    if y0 is None:
        return None
    m = bond.maturity_years
    fair = 0.015 + a.inflation[bond.currency]
    shock = 0.08 if bond.currency == "TRY" else 0.02
    scenarios = {"Yields unchanged": y0, "Halfway to fair value": y0 + 0.5 * (fair - y0),
                 f"+{shock * 1e4:.0f} bp": y0 + shock, f"-{shock * 1e4:.0f} bp": max(0.0, y0 - shock)}
    out = {}
    for name, yh in scenarios.items():
        # coupons reinvested at the average of today's and the exit yield;
        # a bond that matures before the horizon rolls into a new one at yh
        re = (y0 + yh) / 2
        held = min(h, m)
        coupons = sum(y0 * 100 * (1 + re) ** (held - k) for k in range(1, int(held) + 1))
        end = price(y0, yh, m - held, bond.coupon_freq) if m - held > 0 else 100.0
        total = (end + coupons) / 100 * (1 + yh) ** (h - held)
        out[name] = total ** (1 / h) - 1
    dur, conv = duration_convexity(y0, m, bond.coupon_freq)
    base = out["Halfway to fair value"]
    return {
        "yield": y0, "fair_yield": fair, "duration": dur, "convexity": conv,
        "scenarios_local": out,
        "expected_local": base,
        "fx_views": fxview.all_views(bond.currency, ds, a),
        "expected_usd": fxview.to_usd(base, bond.currency, ds, a),
        "expected_usd_carry": fxview.to_usd(out["Yields unchanged"], bond.currency, ds, a),
    }
