"""Percentile ranks, the section 7 rubric, deflated Sharpe and the IS/OOS rank test."""

import math

import numpy as np
import pandas as pd
from scipy import stats as sps

EULER_GAMMA = 0.5772156649015329

# method.md section 7, points out of 100
RUBRIC_WEIGHTS = {
    "oos_sharpe": 20, "oos_ir": 15, "oos_max_drawdown": 10, "consistency": 10,
    "diversification": 10, "inflation": 5, "liquidity_cost": 5, "forward_return": 15,
    "fundamental": 5, "technical": 5,
}


def percentile_scores(df, columns, higher_is_better):
    """Percentile rank within the frame, 0-1, best = 1 (method.md section 7).

    pandas `rank(pct=True, method="average")`: the best of n names scores 1,
    the worst 1/n; ties share the average. NaN stays NaN and is not counted.
    higher_is_better: {column: bool}; a missing key means higher is better.
    """
    out = pd.DataFrame(index=df.index)
    for c in columns:
        x = pd.to_numeric(df[c], errors="coerce")
        out[c] = x.rank(pct=True, method="average", ascending=bool(higher_is_better.get(c, True)))
    return out


def rubric_score(df, weights=None, technical_kept=True):
    """Weighted rubric total (method.md section 7), 0-100.

    df: one column per component holding its percentile score (0-1) within the
    type; names as in RUBRIC_WEIGHTS. If no technical signal was kept
    (`technical_kept=False`, or the technical column is absent or all NaN)
    its weight is dropped and the rest scale up pro-rata (section 6 rule). A
    component missing for one name is handled the same way for that name,
    and `missing_weight` reports how many points were redistributed.
    """
    w = dict(RUBRIC_WEIGHTS if weights is None else weights)
    if not technical_kept or "technical" not in df or df["technical"].isna().all():
        w.pop("technical", None)
    total = pd.Series(0.0, index=df.index)
    avail = pd.Series(0.0, index=df.index)
    for c, wt in w.items():
        if c not in df:
            continue
        x = pd.to_numeric(df[c], errors="coerce")
        total += x.fillna(0) * wt
        avail += x.notna() * wt
    full = float(sum(w.values()))
    out = pd.DataFrame({"rubric_total": (100 * total / avail).where(avail > 0),
                        "weight_used": avail, "missing_weight": full - avail}, index=df.index)
    out.attrs["weights"] = w
    return out


def expected_max_sharpe(n_trials, sr_var):
    """E[max SR] of n independent trials with true SR 0 (Bailey and Lopez de Prado 2014):
    sqrt(V) * ((1 - g) * Z(1 - 1/N) + g * Z(1 - 1/(N e))), g = Euler-Mascheroni constant."""
    if n_trials <= 1:
        return 0.0
    z = sps.norm.ppf
    return math.sqrt(sr_var) * ((1 - EULER_GAMMA) * z(1 - 1 / n_trials)
                                + EULER_GAMMA * z(1 - 1 / (n_trials * math.e)))


def deflated_sharpe(sharpe_annual, n_trials, n_months, skew, kurt, sr_var=None, periods=12):
    """Deflated Sharpe ratio (Bailey and Lopez de Prado 2014), probability in [0, 1].

    Works in per-period (monthly) Sharpe units: sr = sharpe_annual / sqrt(12).
    DSR = Phi((sr - sr0) * sqrt(T - 1) / sqrt(1 - skew * sr + (kurt - 1) / 4 * sr^2)),
    sr0 = expected_max_sharpe(N, V). kurt is raw kurtosis (3 for a normal;
    pandas .kurt() + 3). V = variance of the trials' monthly Sharpe ratios if
    `sr_var` is given (e.g. np.var(trial_sharpes_annual / sqrt(12), ddof=1)),
    else 1 / (T - 1), the estimator variance under the null.
    """
    if any(pd.isna(x) for x in (sharpe_annual, skew, kurt)) or n_months < 3:
        return np.nan
    sr = sharpe_annual / math.sqrt(periods)
    v = 1.0 / (n_months - 1) if sr_var is None else sr_var
    sr0 = expected_max_sharpe(n_trials, v)
    den = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    if den <= 0:
        return np.nan
    return float(sps.norm.cdf((sr - sr0) * math.sqrt(n_months - 1) / math.sqrt(den)))


def is_oos_rank_test(is_scores, oos_scores):
    """Spearman rank correlation between in-sample and OOS scores (method.md section 7).

    Aligns on the index, drops NaN. Returns dict rho, p_value (two-sided), n,
    and `predictive` = rho > 0 (a type with rho <= 0 leans on forward models).
    """
    both = pd.concat([pd.Series(is_scores), pd.Series(oos_scores)], axis=1).dropna()
    if len(both) < 3:
        return {"rho": np.nan, "p_value": np.nan, "n": len(both), "predictive": False}
    rho, p = sps.spearmanr(both.iloc[:, 0], both.iloc[:, 1])
    return {"rho": float(rho), "p_value": float(p), "n": len(both), "predictive": bool(rho > 0)}
