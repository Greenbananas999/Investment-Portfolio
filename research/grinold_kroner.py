"""Grinold-Kroner building-block expected return.

E[R] = dividend yield + expected inflation + real earnings growth
       - net share issuance (buybacks add) + repricing (P/E drift)

Earnings growth: analyst long-term growth for the first 5 years, the home
economy's nominal growth after that, averaged over the horizon; real growth
is capped. Repricing: forward P/E moves to the target P/E in config over
`repricing_years`.
"""

import numpy as np

from . import config, fundamentals, fxview


def run(stock, ds, a, s=None, dcf_settings=None):
    s = s or config.GKSettings()
    dcfs = dcf_settings or config.DCFSettings()
    fd = fundamentals.extract(ds.fundamentals.get(stock.ticker, {}))
    infl = a.inflation[stock.currency]
    lr_nominal = infl + a.long_run_real_gdp[stock.country]
    years = s.repricing_years
    mid = dcfs.cyclical_mid_cycle.get(stock.key)
    ag = fd["analyst_growth"]
    if mid is not None:
        # Earnings fall from the forward (peak) year to mid-cycle, then grow with the economy.
        g_nominal = (mid * (1 + lr_nominal) ** (years - dcfs.cycle_years)) ** (1 / years) - 1
        g_src = f"cyclical: earnings to {mid:.0%} of forward, then nominal GDP"
    else:
        g_analyst = min(ag[0], s.analyst_growth_cap) if ag is not None else lr_nominal
        g_nominal = (min(5, years) * g_analyst + max(0, years - 5) * lr_nominal) / years
        g_src = f"analyst {ag[1]} (cap {s.analyst_growth_cap:.0%}) then nominal GDP" if ag else "nominal GDP"
    g_real = float(np.clip(g_nominal - infl, -0.10, s.max_real_growth))
    dilution = fundamentals.net_dilution(fd["shares"])
    pe, target = fd["forward_pe"], s.target_pe.get(stock.key)
    repricing = (target / pe) ** (1 / years) - 1 if pe and target and pe > 0 else 0.0
    dy = fd["dividend_yield"] or 0.0
    total = dy + infl + g_real - dilution + repricing
    return {
        "dividend_yield": dy, "inflation": infl, "real_growth": g_real,
        "growth_source": g_src, "net_dilution": dilution,
        "forward_pe": pe, "target_pe": target,
        "repricing": repricing, "expected_local": total,
        "expected_usd": fxview.to_usd(total, stock.currency, ds, a),
    }
