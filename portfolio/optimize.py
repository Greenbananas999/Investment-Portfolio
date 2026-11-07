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


# --------------------------------------------------------------------------
# General linear constraint set (Phase 5, method.md sections 3 and 10).
# Added 2026-11-07; the functions above are unchanged.
# --------------------------------------------------------------------------

from dataclasses import dataclass, field  # noqa: E402


@dataclass
class Constraints:
    """Long-only, fully invested weights with linear side constraints.

    lower/upper   per-asset bounds (upper 0 = asset not available)
    non_us        per-asset non-US share (method.md section 3), 0..1
    min_non_us    floor on sum(w x non_us); 0 switches the rule off
    neutral       per-asset mask of assets excluded from the rule's base
                  (gold "reclassified as neutral"): the floor becomes
                  sum(w x non_us) >= min_non_us x (1 - sum(w x neutral))
    groups        {name: (mask, lo, hi)}: lo <= sum(w[mask]) <= hi
    """
    names: list
    lower: np.ndarray
    upper: np.ndarray
    non_us: np.ndarray
    min_non_us: float = 0.0
    neutral: np.ndarray = None
    groups: dict = field(default_factory=dict)

    @property
    def n(self):
        return len(self.names)

    def non_us_row(self):
        """Coefficient row a with the rule written as a @ w >= min_non_us."""
        a = np.asarray(self.non_us, float).copy()
        if self.neutral is not None:
            a = a + self.min_non_us * np.asarray(self.neutral, float)
        return a

    def linear_inequalities(self):
        """(A, b, labels) with A @ w >= b for the rule and the group bands."""
        rows, rhs, labels = [], [], []
        if self.min_non_us > 0:
            rows.append(self.non_us_row())
            rhs.append(self.min_non_us)
            labels.append("non_us_floor")
        for g, (mask, lo, hi) in self.groups.items():
            m = np.asarray(mask, float)
            plain = bool(((m >= 0) & (m <= 1)).all())   # a 0/1 membership mask
            if lo is not None and (lo > 0 or not plain):
                rows.append(m)
                rhs.append(lo)
                labels.append(f"{g}_min")
            if hi is not None and (hi < 1 or not plain):
                rows.append(-m)
                rhs.append(-hi)
                labels.append(f"{g}_max")
        if not rows:
            return np.zeros((0, self.n)), np.zeros(0), []
        return np.array(rows), np.array(rhs), labels


def build_constraints(names, non_us_share, sleeves=None, sleeve_bounds=None, bounds=None,
                      min_non_us=0.70, available=None, neutral=None):
    """Constraint builder (method.md section 10).

    names          asset ids
    non_us_share   {name: share} or array (method.md section 3)
    sleeves        {name: sleeve} or list
    sleeve_bounds  {group: (sleeve name or tuple of sleeve names, lo, hi)}, e.g.
                   {"equity": (("us_equity", "intl_equity"), 0.45, 0.65)}
    bounds         {name: (lo, hi)} or list of pairs
    available      boolean mask; unavailable assets are pinned to 0
    neutral        names excluded from the rule's base (see Constraints)
    """
    names = list(names)
    n = len(names)
    if isinstance(non_us_share, dict):
        nu = np.array([non_us_share[k] for k in names], float)
    else:
        nu = np.asarray(non_us_share, float)
    if bounds is None:
        lo, hi = np.zeros(n), np.ones(n)
    elif isinstance(bounds, dict):
        lo = np.array([bounds[k][0] for k in names], float)
        hi = np.array([bounds[k][1] for k in names], float)
    else:
        lo = np.array([b[0] for b in bounds], float)
        hi = np.array([b[1] for b in bounds], float)
    if available is not None:
        av = np.asarray(available, bool)
        lo, hi = np.where(av, lo, 0.0), np.where(av, hi, 0.0)
    groups = {}
    if sleeves is not None and sleeve_bounds:
        sl = [sleeves[k] for k in names] if isinstance(sleeves, dict) else list(sleeves)
        for g, (members, glo, ghi) in sleeve_bounds.items():
            members = (members,) if isinstance(members, str) else tuple(members)
            groups[g] = (np.array([s in members for s in sl]), glo, ghi)
    neu = None
    if neutral:
        neutral = set(neutral)
        neu = np.array([k in neutral for k in names], float)
    return Constraints(names, lo, hi, nu, float(min_non_us), neu, groups)


def _lp_kwargs(c, A, b):
    return dict(A_ub=-A if len(A) else None, b_ub=-b if len(A) else None,
                A_eq=np.ones((1, c.n)), b_eq=[1.0], bounds=list(zip(c.lower, c.upper)),
                method="highs")


def feasible_point(c):
    """A feasible weight vector found by linear programming, or None if the set is empty."""
    from scipy.optimize import linprog
    A, b, _ = c.linear_inequalities()
    res = linprog(np.zeros(c.n), **_lp_kwargs(c, A, b))
    if res.status != 0:
        return None
    # Move to the analytic centre-ish point: average of the LP vertices that
    # maximise each weight, so SLSQP does not start on a corner.
    pts = []
    for i in range(c.n):
        e = np.zeros(c.n)
        e[i] = -1.0
        r = linprog(e, **_lp_kwargs(c, A, b))
        if r.status == 0:
            pts.append(r.x)
    return np.mean(pts, axis=0) if pts else res.x


def feasible_region(c):
    """Min and max achievable value of each weight, each group and the non-US share.

    Returns {"feasible", "assets": {name: [min, max]}, "groups": {...},
    "non_us_share": [min, max], "reason"}.
    """
    from scipy.optimize import linprog
    A, b, _ = c.linear_inequalities()
    kw = _lp_kwargs(c, A, b)

    def rng(vec):
        lo, hi = linprog(vec, **kw), linprog(-vec, **kw)
        if lo.status != 0 or hi.status != 0:
            return None
        return [float(lo.fun), float(-hi.fun)]

    if linprog(np.zeros(c.n), **kw).status != 0:
        return {"feasible": False, "assets": {}, "groups": {}, "non_us_share": None,
                "reason": infeasibility_reason(c)}
    return {"feasible": True, "reason": "",
            "assets": {k: rng(np.eye(c.n)[i]) for i, k in enumerate(c.names)},
            "groups": {g: rng(np.asarray(m, float)) for g, (m, _, _) in c.groups.items()},
            "non_us_share": rng(np.asarray(c.non_us, float))}


def infeasibility_reason(c):
    """Plain-English reason the set is empty (which simple bound combination conflicts)."""
    from scipy.optimize import linprog
    msgs = []
    if c.lower.sum() > 1 + 1e-9:
        msgs.append(f"minimum weights sum to {c.lower.sum():.1%} > 100%")
    if c.upper.sum() < 1 - 1e-9:
        msgs.append(f"maximum weights sum to {c.upper.sum():.1%} < 100%")
    for g, (m, lo, hi) in c.groups.items():
        m = np.asarray(m, bool)
        if lo is not None and c.upper[m].sum() < lo - 1e-9:
            msgs.append(f"{g}: asset caps allow at most {c.upper[m].sum():.1%} < band minimum {lo:.1%}")
        if hi is not None and c.lower[m].sum() > hi + 1e-9:
            msgs.append(f"{g}: asset minimums need {c.lower[m].sum():.1%} > band maximum {hi:.1%}")
    if c.min_non_us > 0:
        free = Constraints(c.names, c.lower, c.upper, c.non_us, 0.0, None, c.groups)
        A, b, _ = free.linear_inequalities()
        res = linprog(-c.non_us_row(), **_lp_kwargs(free, A, b))
        if res.status == 0 and -res.fun < c.min_non_us - 1e-9:
            msgs.append(f"the highest reachable non-US share is {-res.fun:.1%} "
                        f"< floor {c.min_non_us:.0%}")
    return "; ".join(msgs) or "infeasible (no single bound combination explains it)"


class InfeasibleError(ValueError):
    """The constraint set is empty; the message says why."""


def check_weights(w, c, tol=1e-6):
    """Rule checks for one weight vector: sum, long-only, bounds, groups, non-US floor."""
    w = np.asarray(w, float)
    nu = float(np.asarray(c.non_us, float) @ w)
    out = {"sum": float(w.sum()), "sum_ok": bool(abs(w.sum() - 1) <= max(tol, 1e-6)),
           "long_only_ok": bool((w >= -tol).all()),
           "bounds_ok": bool(((w >= c.lower - tol) & (w <= c.upper + tol)).all()),
           "bound_violations": [k for k, x, lo, hi in zip(c.names, w, c.lower, c.upper)
                                if x < lo - tol or x > hi + tol],
           "non_us_share": nu, "groups": {}, "groups_ok": True}
    if c.neutral is not None:
        base = 1 - float(np.asarray(c.neutral, float) @ w)
        out["non_us_share_ex_neutral"] = nu / base if base > 0 else None
    out["non_us_ok"] = bool(c.non_us_row() @ w >= c.min_non_us - tol) if c.min_non_us > 0 else True
    for g, (m, lo, hi) in c.groups.items():
        s = float(np.asarray(m, float) @ w)
        ok = (lo is None or s >= lo - tol) and (hi is None or s <= hi + tol)
        out["groups"][g] = s
        out["groups_ok"] = bool(out["groups_ok"] and ok)
    out["ok"] = bool(out["sum_ok"] and out["long_only_ok"] and out["bounds_ok"]
                     and out["groups_ok"] and out["non_us_ok"])
    return out


def binding(w, c, tol=1e-4):
    """Names of the constraints active at `w` (within tol)."""
    w = np.asarray(w, float)
    act = []
    if c.min_non_us > 0 and c.non_us_row() @ w - c.min_non_us <= tol:
        act.append("non_us_floor")
    for g, (m, lo, hi) in c.groups.items():
        s = np.asarray(m, float) @ w
        if lo is not None and s - lo <= tol:
            act.append(f"{g}_min")
        if hi is not None and hi - s <= tol:
            act.append(f"{g}_max")
    for k, x, lo, hi in zip(c.names, w, c.lower, c.upper):
        if hi > lo and x - lo <= tol:
            act.append(f"{k}_min")
        if hi > lo and hi - x <= tol:
            act.append(f"{k}_max")
    return act


def solve_constrained(objective, c, w0=None):
    """Minimise `objective(w)` over the constraint set with SLSQP.

    Starts from `w0` when it is feasible, else from an LP-feasible interior
    point; raises InfeasibleError with the reason when the set is empty."""
    start = feasible_point(c)
    if start is None:
        raise InfeasibleError(infeasibility_reason(c))
    if w0 is not None and check_weights(w0, c, 1e-9)["ok"]:
        start = np.asarray(w0, float)
    A, b, _ = c.linear_inequalities()
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0, "jac": lambda w: np.ones_like(w)}]
    if len(A):
        cons.append({"type": "ineq", "fun": lambda w: A @ w - b, "jac": lambda w: A})
    res = minimize(objective, start, method="SLSQP", bounds=list(zip(c.lower, c.upper)),
                   constraints=cons, options={"maxiter": 500, "ftol": 1e-12})
    w = np.clip(res.x, c.lower, c.upper)
    w = w / w.sum()
    if not check_weights(w, c, tol=1e-6)["ok"] or objective(w) > objective(start):
        # SLSQP ended outside the set or worse than its start: keep the feasible start.
        return start if check_weights(start, c, 1e-6)["ok"] else w
    return w


def max_sharpe_constrained(mu, cov, c, w0=None):
    """Max (w @ mu) / sqrt(w' cov w) over the constraint set; mu is excess of the risk-free rate."""
    def neg_sharpe(w):
        return -(w @ mu) / np.sqrt(max(w @ cov @ w, 1e-16))
    return solve_constrained(neg_sharpe, c, w0)


def min_variance_constrained(cov, c, w0=None):
    return solve_constrained(lambda w: w @ cov @ w, c, w0)
