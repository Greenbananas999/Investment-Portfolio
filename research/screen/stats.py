"""Monthly performance statistics (results_schema.md METRICS block).

All inputs are monthly simple returns (decimals) indexed by month end;
annualisation uses 12. Thin wrappers over research/metrics.py where it
already has the statistic; its API is unchanged.
"""

import numpy as np
import pandas as pd

from .. import metrics as _m
from .scoring import deflated_sharpe

cagr, vol, max_drawdown, beta = _m.cagr, _m.vol, _m.max_drawdown, _m.beta


def _rf(r, rf):
    if rf is None:
        return pd.Series(0.0, index=r.index)
    if np.isscalar(rf):
        return pd.Series(float(rf), index=r.index)
    return rf


def sharpe(r, rf=None):
    """Annualised Sharpe of monthly excess returns over rf (BIL monthly return, or 0)."""
    return _m.sharpe(r, _rf(r, rf))


def sortino(r, rf=None):
    """Annualised mean excess return / downside deviation (root mean square of negative excess)."""
    ex = (r - _rf(r, rf).reindex(r.index).fillna(0)).dropna()
    dd = np.sqrt((np.minimum(ex, 0) ** 2).mean())
    return float(ex.mean() / dd * np.sqrt(12)) if dd > 0 else np.nan


def info_ratio(r, bench):
    """Annualised mean active return / tracking error."""
    return _m.info_ratio(r, bench)


def tracking_error(r, bench):
    """Annualised std of monthly active returns."""
    act = (r - bench.reindex(r.index)).dropna()
    return float(act.std() * np.sqrt(12)) if len(act) > 1 else np.nan


def alpha_t(r, bench, rf=None):
    """OLS of excess returns on benchmark excess returns: (alpha annualised x12, t-stat, beta)."""
    rf = _rf(r, rf)
    df = pd.concat([r - rf.reindex(r.index).fillna(0),
                    bench.reindex(r.index) - rf.reindex(r.index).fillna(0)], axis=1).dropna()
    if len(df) < 24:
        return np.nan, np.nan, np.nan
    y, x = df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy()
    X = np.column_stack([np.ones_like(x), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    s2 = resid @ resid / (len(y) - 2)
    se = np.sqrt(s2 * np.linalg.inv(X.T @ X)[0, 0])
    return float(coef[0] * 12), float(coef[0] / se) if se > 0 else np.nan, float(coef[1])


def capture(r, bench):
    """(up capture, down capture): mean asset return / mean benchmark return in the
    benchmark's up (> 0) and down (< 0) months."""
    df = pd.concat([r, bench], axis=1).dropna()
    up, dn = df[df.iloc[:, 1] > 0], df[df.iloc[:, 1] < 0]
    u = up.iloc[:, 0].mean() / up.iloc[:, 1].mean() if len(up) else np.nan
    d = dn.iloc[:, 0].mean() / dn.iloc[:, 1].mean() if len(dn) else np.nan
    return float(u), float(d)


def rolling_sharpe(r, rf=None, window=36):
    """Rolling `window`-month annualised Sharpe, labelled at the window's last month."""
    ex = (r - _rf(r, rf).reindex(r.index).fillna(0))
    ro = ex.rolling(window, min_periods=window)
    return (ro.mean() / ro.std() * np.sqrt(12)).dropna()


def rolling_ir(r, bench, window=36):
    """Rolling `window`-month annualised information ratio."""
    act = (r - bench.reindex(r.index))
    ro = act.rolling(window, min_periods=window)
    return (ro.mean() / ro.std() * np.sqrt(12)).dropna()


def share_ir_positive(r, bench, window=36):
    """Consistency (method.md section 7): share of rolling windows with IR > 0."""
    ir = rolling_ir(r, bench, window)
    return float((ir > 0).mean()) if len(ir) else np.nan


def metrics_block(r, bench=None, rf=None, n_trials=1):
    """The results_schema.md METRICS dict for one window of monthly returns."""
    r = r.dropna()
    out = {"start": str(r.index[0].date()) if len(r) else None,
           "end": str(r.index[-1].date()) if len(r) else None, "months": int(len(r))}
    if len(r) < 2:
        return out
    sh = sharpe(r, rf)
    mdd = max_drawdown(r)
    c = cagr(r)
    out.update(cagr=c, vol=vol(r), sharpe=sh, sortino=sortino(r, rf), max_drawdown=mdd,
               calmar=c / abs(mdd) if mdd < 0 else np.nan,
               best_month=float(r.max()), worst_month=float(r.min()),
               pct_positive_months=float((r > 0).mean()),
               deflated_sharpe=deflated_sharpe(sh, n_trials, len(r), float(r.skew()), float(r.kurt()) + 3))
    if bench is not None:
        a, t, b = alpha_t(r, bench, rf)
        ir = info_ratio(r, bench)
        act = (r - bench.reindex(r.index)).dropna()
        up, dn = capture(r, bench)
        out.update(beta=b, alpha=a, t_stat_alpha=t, tracking_error=tracking_error(r, bench),
                   info_ratio=ir, t_stat_ir=ir / np.sqrt(12) * np.sqrt(len(act)) if pd.notna(ir) else np.nan,
                   up_capture=up, down_capture=dn)
    return {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in out.items()}
