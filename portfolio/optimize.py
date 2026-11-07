"""Long-only portfolio optimizers with weight caps and the non-US floor.

Estimates use daily excess returns (asset minus risk-free). The covariance is
Ledoit-Wolf shrunk toward a scaled identity, and expected returns are shrunk
toward their cross-sectional average, because raw historical means make
max-Sharpe weights jump around.
"""

import numpy as np
from scipy.optimize import minimize

TRADING_DAYS = 252


def ledoit_wolf(x):
    """Ledoit-Wolf (2004) shrinkage covariance toward mu * I. x is T x N."""
    t, n = x.shape
    xc = x - x.mean(axis=0)
    s = xc.T @ xc / t
    mu = np.trace(s) / n
    target = mu * np.eye(n)
    d2 = np.sum((s - target) ** 2)
    b2 = sum(np.sum((np.outer(r, r) - s) ** 2) for r in xc) / t**2
    b2 = min(b2, d2)
    shrink = b2 / d2 if d2 > 0 else 1.0
    return shrink * target + (1 - shrink) * s


def estimate(excess, mean_shrinkage=0.5):
    """Annualized expected excess returns and covariance from a T x N array."""
    mu = excess.mean(axis=0)
    mu = mean_shrinkage * mu.mean() + (1 - mean_shrinkage) * mu
    cov = ledoit_wolf(excess)
    return mu * TRADING_DAYS, cov * TRADING_DAYS


def _constraints(non_us_mask, min_non_us):
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
    if min_non_us > 0:
        mask = non_us_mask.astype(float)
        cons.append({"type": "ineq", "fun": lambda w: mask @ w - min_non_us})
    return cons


def _solve(objective, n, available, non_us_mask, max_weight, min_non_us):
    bounds = [(0.0, max_weight if ok else 0.0) for ok in available]
    k = available.sum()
    if k * max_weight < 1.0 - 1e-9:
        raise ValueError(f"{k} assets x {max_weight:.0%} cap cannot sum to 100%")
    w0 = np.where(available, 1.0 / k, 0.0)
    res = minimize(objective, w0, method="SLSQP", bounds=bounds,
                   constraints=_constraints(non_us_mask, min_non_us),
                   options={"maxiter": 500, "ftol": 1e-12})
    w = np.clip(res.x, 0.0, None)
    if not res.success and (abs(w.sum() - 1) > 1e-4 or non_us_mask @ w < min_non_us - 1e-4):
        raise RuntimeError(f"optimizer failed: {res.message}")
    return w / w.sum()


def min_variance(cov, available, non_us_mask, max_weight, min_non_us):
    n = len(cov)
    return _solve(lambda w: w @ cov @ w, n, available, non_us_mask, max_weight, min_non_us)


def max_sharpe(mu, cov, available, non_us_mask, max_weight, min_non_us):
    n = len(cov)

    def neg_sharpe(w):
        vol = np.sqrt(max(w @ cov @ w, 1e-16))
        return -(w @ mu) / vol

    return _solve(neg_sharpe, n, available, non_us_mask, max_weight, min_non_us)


def equal_weight(available, non_us_mask, min_non_us):
    """Equal weight across available assets, scaled to respect the non-US floor."""
    w = np.where(available, 1.0, 0.0)
    w /= w.sum()
    non_us = (non_us_mask & available)
    share = w[non_us].sum()
    if share < min_non_us:
        w[non_us] *= min_non_us / share
        us = available & ~non_us_mask
        w[us] *= (1 - min_non_us) / w[us].sum()
    return w
