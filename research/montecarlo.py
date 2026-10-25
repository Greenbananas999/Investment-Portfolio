"""Monte Carlo simulation of 5-year outcomes by block bootstrap.

Months are resampled in blocks (default 6) from the assets' joint monthly
history, so fat tails, volatility clustering, cross-asset correlation and
the FX moves riding on each asset are all kept. Two drift settings:

  historical  - returns as they were. NVDA's 2015-2026 run gets replayed, so
                treat this as "if the past repeats", not a forecast.
  forward     - each asset's monthly returns are scaled so their geometric
                mean equals the model consensus expected return, keeping the
                historical shape of risk. This is the forecast version.
"""

import numpy as np
import pandas as pd


def _scale_to(r, target_annual):
    """Scale gross returns so their geometric mean hits target_annual."""
    g = np.exp(np.log1p(r).mean())
    k = (1 + target_annual) ** (1 / 12) / g
    return (1 + r) * k - 1


def bootstrap_paths(R, months, n_paths, block, rng):
    """Indices of resampled months, shape (n_paths, months)."""
    T = R.shape[0]
    n_blocks = int(np.ceil(months / block))
    starts = rng.integers(0, T - block + 1, size=(n_paths, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_paths, -1)[:, :months]
    return idx


def simulate(returns, settings, targets=None, weights=None):
    """returns: DataFrame of monthly returns (common sample). Returns summary dict."""
    rng = np.random.default_rng(settings.seed)
    R = returns.copy()
    if targets is not None:
        for c in R.columns:
            if c in targets and np.isfinite(targets[c]):
                R[c] = _scale_to(R[c], targets[c])
    X = R.to_numpy()
    months = settings.horizon_years * 12
    idx = bootstrap_paths(X, months, settings.n_paths, settings.block_months, rng)
    out = {}
    cols = list(R.columns)
    log_paths = np.log1p(X)[idx]                     # (paths, months, assets)
    terminal = np.exp(log_paths.sum(axis=1))         # growth of 1
    one_year = np.exp(log_paths[:, :12, :].sum(axis=1)) - 1
    for j, c in enumerate(cols):
        ann = terminal[:, j] ** (1 / settings.horizon_years) - 1
        out[c] = _summ(ann, terminal[:, j], one_year[:, j])
    if weights is not None:
        w = np.array([weights.get(c, 0.0) for c in cols])
        port_m = (X[idx] * w).sum(axis=2)             # monthly rebalanced
        growth = np.cumprod(1 + port_m, axis=1)
        term = growth[:, -1]
        ann = term ** (1 / settings.horizon_years) - 1
        out["PORTFOLIO"] = _summ(ann, term, growth[:, 11] - 1)
        q = np.percentile(growth, [5, 25, 50, 75, 95], axis=0)
        out["PORTFOLIO"]["fan"] = {str(p): q[i].round(4).tolist() for i, p in enumerate((5, 25, 50, 75, 95))}
    return out


def _summ(ann, terminal, one_year):
    pct = lambda x: {str(p): float(np.percentile(x, p)) for p in (5, 25, 50, 75, 95)}
    return {"annualised": pct(ann), "mean_annualised": float(ann.mean()),
            "prob_loss_5y": float((terminal < 1).mean()),
            "var95_1y": float(-np.percentile(one_year, 5)),
            "cvar95_1y": float(-one_year[one_year <= np.percentile(one_year, 5)].mean()),
            "terminal_100k": {k: v * 100_000 for k, v in pct(terminal).items()},
            "hist": np.histogram(np.clip(ann, -0.5, 1.0), bins=30, range=(-0.5, 1.0))[0].tolist()}
