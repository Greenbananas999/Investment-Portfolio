"""Ex-ante efficient frontier from the model expected returns.

Covariance: monthly USD returns over the common sample, shrunk 30% toward
its diagonal (a simple Ledoit-Wolf-style shrink). Long-only, single-asset
cap, optional minimum non-US weight. Also returns the max-Sharpe portfolio.
"""

import numpy as np
from scipy.optimize import minimize


def shrunk_cov(R, shrink=0.3):
    S = np.cov(R, rowvar=False) * 12
    return (1 - shrink) * S + shrink * np.diag(np.diag(S))


def _solve(mu, S, cons, bounds, objective):
    n = len(mu)
    res = minimize(objective, np.full(n, 1 / n), method="SLSQP", bounds=bounds,
                   constraints=cons, options={"maxiter": 500, "ftol": 1e-10})
    return res.x if res.success else None


def frontier(mu, S, names, non_us_mask, rf, max_w=0.25, min_non_us=0.70, points=25):
    n = len(mu)
    bounds = [(0, max_w)] * n
    base = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    if min_non_us:
        base.append({"type": "ineq", "fun": lambda w: w[non_us_mask].sum() - min_non_us})
    var = lambda w: w @ S @ w
    w_min = _solve(mu, S, base, bounds, var)
    w_maxret = _solve(mu, S, base, bounds, lambda w: -w @ mu)
    lo, hi = w_min @ mu, w_maxret @ mu
    pts = []
    for target in np.linspace(lo, hi, points):
        cons = base + [{"type": "eq", "fun": lambda w, t=target: w @ mu - t}]
        w = _solve(mu, S, cons, bounds, var)
        if w is not None:
            pts.append({"ret": float(w @ mu), "vol": float(np.sqrt(w @ S @ w))})
    w_tan = _solve(mu, S, base, bounds, lambda w: -(w @ mu - rf) / np.sqrt(w @ S @ w))
    pack = lambda w: {"weights": {k: float(round(x, 4)) for k, x in zip(names, w)},
                      "ret": float(w @ mu), "vol": float(np.sqrt(w @ S @ w)),
                      "sharpe": float((w @ mu - rf) / np.sqrt(w @ S @ w))}
    return {"points": pts, "min_variance": pack(w_min), "max_sharpe": pack(w_tan),
            "assets": [{"key": k, "ret": float(m), "vol": float(np.sqrt(S[i, i]))}
                       for i, (k, m) in enumerate(zip(names, mu))]}
