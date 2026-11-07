"""Backtest of the forecasting methods themselves.

Every December from 2015 to 2024, forecast each asset's next-12-month USD
return using only data available then, and compare with what happened:
  hist5  - trailing 5-year annualised return
  capm   - US T-bill + trailing 60-month ACWI beta x 4.5% ERP (global CAPM)
  yield  - bonds only: the bond's yield, converted to USD at the T-bill
           differential (interest parity)
  flat8  - a naive constant 8% for stocks
Scores: mean absolute error and the rank correlation between forecasts and
outcomes across assets each year (does the method at least order assets?).
DCF and Grinold-Kroner need point-in-time fundamentals, which Yahoo does not
keep, so they cannot be backtested here.
"""

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from . import config, metrics


def run(assets, ds, a, years=range(2015, 2025)):
    acwi = ds.index_returns(config.GLOBAL_INDEX)
    us3m = ds.monthly_yield("US_3M")
    rows = []
    for y in years:
        t = pd.Timestamp(f"{y}-12-31")
        rf = float(us3m[:t].iloc[-1]) if us3m is not None else a.risk_free["USD"]
        for key, (local, usd, ccy, _) in assets.items():
            past, fut = usd[:t], usd[(usd.index > t) & (usd.index <= t + pd.DateOffset(years=1))]
            if len(fut) < 12 or len(past) < 60:
                continue
            realised = float((1 + fut).prod() - 1)
            f = {"hist5": metrics.cagr(past.iloc[-60:])}
            is_bond = key.startswith(("FR_", "TR_"))
            if is_bond:
                bond = next(b for b in config.BONDS if b.key == key)
                yl = ds.monthly_yield(bond.yield_series)
                yv = float(yl[:t].iloc[-1])
                f["yield"] = yv
            else:
                b = metrics.beta(past.iloc[-60:], acwi[:t])
                f["capm"] = rf + (0.67 * b + 0.33) * a.mature_erp
                f["flat8"] = 0.08
            for m, v in f.items():
                rows.append({"year": y, "asset": key, "method": m, "forecast": v, "realised": realised})
    df = pd.DataFrame(rows)
    summary = {}
    for m, g in df.groupby("method"):
        ics = []
        for _, gy in g.groupby("year"):
            if len(gy) >= 4 and gy["forecast"].nunique() > 1:
                ics.append(spearmanr(gy["forecast"], gy["realised"]).statistic)
        summary[m] = {"mae": float((g["forecast"] - g["realised"]).abs().mean()),
                      "bias": float((g["forecast"] - g["realised"]).mean()),
                      "rank_corr": float(np.nanmean(ics)) if ics else None,
                      "n": int(len(g))}
    return summary, df
