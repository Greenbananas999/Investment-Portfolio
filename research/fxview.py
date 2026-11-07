"""Expected FX moves, used to turn local-currency expected returns into USD.

Three views of where a currency goes against the dollar:
  ppp  - relative purchasing power parity: expected change = (1+pi_US)/(1+pi_local) - 1
  uip  - uncovered interest parity: (1+r_US)/(1+r_local) - 1 (what forwards price in)
  trend - the currency's own historical drift over the last 10 years
PPP is the base case; the others are shown as sensitivities.
"""

from . import config, metrics


def expected_fx(ccy, ds, a, view="ppp"):
    if ccy == "USD":
        return 0.0
    if view == "ppp":
        return (1 + a.inflation["USD"]) / (1 + a.inflation[ccy]) - 1
    if view == "uip":
        return (1 + a.risk_free["USD"]) / (1 + a.risk_free[ccy]) - 1
    if view == "trend":
        r = ds.fx_returns(ccy)
        return metrics.cagr(r.iloc[-120:])
    raise ValueError(view)


def to_usd(local_return, ccy, ds, a, view="ppp"):
    return (1 + local_return) * (1 + expected_fx(ccy, ds, a, view)) - 1


def all_views(ccy, ds, a):
    return {v: expected_fx(ccy, ds, a, v) for v in ("ppp", "uip", "trend")}
