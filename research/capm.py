"""CAPM expected returns, local (home-market) and global (USD investor) versions.

Local CAPM:  E[R_local] = rf_local + beta_local * (mature ERP + country risk premium)
Global CAPM: E[R_usd]   = rf_usd + beta_ACWI * mature ERP + country risk premium
Betas use the last 60 months of monthly returns, Blume-adjusted (0.67 b + 0.33)
because raw betas drift toward 1 over time.
"""

from . import config, fxview, metrics


def blume(b):
    return 0.67 * b + 0.33


def estimate(stock, ds, a, months=60):
    local, usd = ds.stock_returns(stock.key)
    m_local = ds.index_returns(stock.local_index, in_usd=False)
    m_global = ds.index_returns(config.GLOBAL_INDEX)
    b_loc_raw = metrics.beta(local.iloc[-months:], m_local)
    b_glob_raw = metrics.beta(usd.iloc[-months:], m_global)
    b_loc, b_glob = blume(b_loc_raw), blume(b_glob_raw)
    crp = a.country_risk_premium[stock.country]
    rf_loc = a.risk_free[stock.currency]
    e_local = rf_loc + b_loc * (a.mature_erp + crp)
    e_global_usd = a.risk_free["USD"] + b_glob * a.mature_erp + crp
    return {
        "beta_local_raw": b_loc_raw, "beta_global_raw": b_glob_raw,
        "beta_local": b_loc, "beta_global": b_glob,
        "rf_local": rf_loc, "crp": crp,
        "expected_local": e_local,
        "expected_usd": fxview.to_usd(e_local, stock.currency, ds, a),
        "expected_usd_global_capm": e_global_usd,
        "cost_of_equity": e_local,
    }
