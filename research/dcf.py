"""Discounted cash flow: intrinsic value, implied expected return, and Monte Carlo.

Firm-level free-cash-flow model in the company's reporting currency:
  * Year 1 cash flow = forward net income (market cap / forward P/E) times the
    firm's own FCF-to-net-income conversion over the last 4 fiscal years,
    plus after-tax interest (an FCFF approximation). Using forward earnings
    matters in Oct 2026: trailing statements lag the AI and memory boom.
  * Years 2..N grow at the analyst next-year growth rate (capped), then fade
    linearly to the terminal rate by year 10; Gordon growth after that.
    Memory makers instead fall to a mid-cycle level by year 4 (see config).
  * Discount at WACC (CAPM cost of equity; local risk-free + spread for debt).
The **implied return** is the discount rate that makes the DCF value equal
today's enterprise value: the annual return a buyer at today's price earns if
those cash flows arrive. That is the DCF's expected-return estimate.
"""

import numpy as np
from scipy.optimize import brentq

from . import config, fundamentals, fxview


def cash_flows(cf1, g0, gt, s, mid_cycle=None, gn=None):
    """Explicit-period cash flows. `mid_cycle` (fraction of year 1) switches on the cyclical path."""
    flows = [cf1]
    if mid_cycle is not None:
        step = mid_cycle ** (1 / s.cycle_years)
        for t in range(2, s.explicit_years + 1):
            g = step - 1 if t <= 1 + s.cycle_years else gn + (gt - gn) * (t - 1 - s.cycle_years) / (s.explicit_years - 1 - s.cycle_years)
            flows.append(flows[-1] * (1 + g))
        return np.array(flows)
    for t in range(2, s.explicit_years + 1):
        if t <= s.high_growth_years + 1:
            g = g0
        else:
            k = (t - 1 - s.high_growth_years) / (s.explicit_years - 1 - s.high_growth_years)
            g = g0 + (gt - g0) * k
        flows.append(flows[-1] * (1 + g))
    return np.array(flows)


def value(flows, r, gt):
    if r <= gt + 1e-4:
        return np.inf
    t = np.arange(1, len(flows) + 1)
    pv = (flows / (1 + r) ** t).sum()
    tv = flows[-1] * (1 + gt) / (r - gt) / (1 + r) ** len(flows)
    return pv + tv


def implied_return(flows, gt, ev):
    f = lambda r: value(flows, r, gt) - ev
    lo, hi = gt + 0.002, 2.0
    if f(lo) < 0:
        return lo  # even a discount rate near terminal growth cannot justify the price
    return brentq(f, lo, hi) if f(hi) < 0 else hi


def inputs(stock, ds, a, coe, s=None):
    s = s or config.DCFSettings()
    fd = fundamentals.extract(ds.fundamentals.get(stock.ticker, {}))
    if not fd["market_cap"]:
        return None, fd
    fwd_ni = fundamentals.forward_net_income(fd)
    conv_raw = fundamentals.fcf_conversion(fd)
    conv = float(np.clip(conv_raw if conv_raw is not None else 0.7, *s.conversion_range))
    if fwd_ni is not None:
        cf1, base_src = fwd_ni * conv, "forward net income x FCF conversion"
    elif fd["fcf"] is not None and len(fd["fcf"]):
        cf1, base_src = float(fd["fcf"].iloc[-1]), "last fiscal-year FCF"
    else:
        return None, fd
    if fd["interest"] is not None and len(fd["interest"]):
        cf1 += abs(float(fd["interest"].iloc[-1])) * (1 - s.tax_rate)
    # Reporting vs trading currency (market cap is in the trading currency).
    rep, trade = fd["financial_currency"] or stock.currency, fd["currency"] or stock.currency
    conv_fx = 1.0
    if rep != trade and rep in ds.fx and trade in ds.fx:
        conv_fx = float(ds.fx[rep].dropna().iloc[-1] / ds.fx[trade].dropna().iloc[-1])
    debt, cash = fd["debt"] * conv_fx, fd["cash"] * conv_fx
    if base_src.startswith("last"):
        cf1 *= conv_fx

    ag = fd["analyst_growth"]
    if ag is not None:
        g0, g_src = ag[0], f"analyst {ag[1]} growth"
    elif fd["revenue_growth_hist"] is not None:
        g0, g_src = fd["revenue_growth_hist"], "historical revenue CAGR"
    else:
        g0, g_src = a.inflation[stock.currency] + a.long_run_real_gdp[stock.country], "nominal GDP"
    g0 = float(np.clip(g0, s.min_start_growth, s.max_start_growth))
    gn = a.inflation[stock.currency] + a.long_run_real_gdp[stock.country]
    gt = min(s.terminal_growth_cap, a.risk_free[stock.currency], gn)

    mcap = float(fd["market_cap"])
    d_w = min(debt / (debt + mcap), s.target_debt_weight_cap) if debt > 0 else 0.0
    kd = (a.risk_free[stock.currency] + s.cost_of_debt_spread) * (1 - s.tax_rate)
    wacc = (1 - d_w) * coe + d_w * kd
    mid = s.cyclical_mid_cycle.get(stock.key)
    return {"cf1": cf1, "base_source": base_src, "forward_net_income": fwd_ni,
            "fcf_conversion": conv, "fcf_conversion_raw": conv_raw,
            "g0": g0, "g_source": g_src if mid is None else f"cyclical: falls to {mid:.0%} of year 1 by year {1 + s.cycle_years}",
            "g_nominal": gn, "g_terminal": gt, "wacc": wacc, "cost_of_equity": coe,
            "debt": debt, "cash": cash, "market_cap": mcap, "ev": mcap + debt - cash,
            "mid_cycle": mid}, fd


def run(stock, ds, a, coe, mc=None, s=None):
    s = s or config.DCFSettings()
    mc = mc or config.MonteCarloSettings()
    inp, fd = inputs(stock, ds, a, coe, s)
    if inp is None:
        return None
    if inp["cf1"] <= 0:
        return {**inp, "note": "Cash flow base is negative; DCF not meaningful."}
    mid, gn, gt = inp["mid_cycle"], inp["g_nominal"], inp["g_terminal"]
    flows = cash_flows(inp["cf1"], inp["g0"], gt, s, mid, gn)
    ev_fair = value(flows, inp["wacc"], gt)
    equity_fair = ev_fair - inp["debt"] + inp["cash"]
    irr = implied_return(flows, gt, inp["ev"])

    # Monte Carlo over the uncertain inputs.
    rng = np.random.default_rng(mc.seed)
    n = 4000
    g0s = rng.normal(inp["g0"], 0.03 + 0.3 * abs(inp["g0"]), n).clip(-0.2, 0.5)
    gts = rng.normal(gt, 0.005, n).clip(0.0, s.terminal_growth_cap)
    waccs = rng.normal(inp["wacc"], 0.01, n).clip(gt + 0.02, None)
    cf1s = inp["cf1"] * rng.lognormal(0, 0.15, n)
    mids = rng.uniform(0.3, 0.8, n) if mid is not None else [None] * n
    ups, irrs = np.empty(n), np.empty(n)
    for i in range(n):
        fl = cash_flows(cf1s[i], g0s[i], gts[i], s, mids[i], gn)
        ups[i] = (value(fl, waccs[i], gts[i]) - inp["debt"] + inp["cash"]) / inp["market_cap"] - 1
        irrs[i] = implied_return(fl, gts[i], inp["ev"])
    pct = lambda x: {p: float(np.nanpercentile(x, p)) for p in (5, 25, 50, 75, 95)}
    pv_explicit = (flows / (1 + inp["wacc"]) ** np.arange(1, len(flows) + 1)).sum()
    return {
        **inp, "flows": flows.tolist(), "ev_fair": ev_fair, "equity_fair": equity_fair,
        "upside": equity_fair / inp["market_cap"] - 1,
        "expected_local": irr,
        "expected_usd": fxview.to_usd(irr, stock.currency, ds, a),
        "mc_upside": pct(ups), "mc_prob_undervalued": float((ups > 0).mean()),
        "mc_implied_return": pct(irrs),
        "terminal_share_of_value": 1 - pv_explicit / ev_fair,
    }
