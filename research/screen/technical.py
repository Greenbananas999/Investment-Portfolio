"""Technical signals T1-T5 and their pre-registered validation (method.md section 6).

Timing convention: a signal panel row labelled with month-end t holds the
value computed from daily USD prices up to the end of month t-1 only, so it
can be traded at the start of month t and is compared with the month-t
return. The last row is the month after the last data month (the signal
usable "now"). `signals_at(signals, as_of)` returns the cross-section built
from data up to as_of.
"""

import numpy as np
import pandas as pd

from .prices import IN_SAMPLE_END, IN_SAMPLE_START

SIGNALS = ("T1", "T2", "T3", "T4", "T5")
HIGHER_IS_BETTER = {"T1": True, "T2": True, "T3": True, "T4": False, "T5": True}
BINARY = {"T2"}
DESCRIPTION = {
    "T1": "12-1 month momentum: return from end of t-13 to end of t-2",
    "T2": "1 if price > 200-trading-day moving average at end of t-1, else 0",
    "T3": "6-month return to end of t-1 minus the type benchmark's 6-month return",
    "T4": "annualised std of the last 252 daily returns to end of t-1 (lower better)",
    "T5": "price / max of last 252 daily closes - 1 at end of t-1 (closer to 0 better)",
}
MA_DAYS, VOL_DAYS, HIGH_DAYS, MIN_DAYS = 200, 252, 252, 200


def _per_column_monthly(daily, fn):
    """Apply fn to each column's own non-NaN daily series, take month-end values."""
    out = {}
    for c in daily.columns:
        s = daily[c].dropna()
        if len(s) == 0:
            continue
        out[c] = fn(s).resample("ME").last()
    return pd.DataFrame(out)


def _above_ma(s):
    ma = s.rolling(MA_DAYS, min_periods=MA_DAYS).mean()
    return (s > ma).astype(float).where(ma.notna())


def technical_signals(daily_usd, benchmark_usd, as_of=None):
    """Monthly panels T1..T5 exactly as method.md section 6 defines them.

    daily_usd: daily USD total-return prices (columns = tickers).
    benchmark_usd: the type benchmark as a daily or month-end level Series, or a
    DataFrame of levels with one column per ticker (EM bonds: EMB or EMLC).
    as_of: if given, nothing after this date is read.
    Rolling windows run on each ticker's own trading days (200 days for the
    moving average, 252 for volatility and the 52-week high, at least 200
    observations required).
    """
    daily = daily_usd.sort_index()
    if as_of is not None:
        daily = daily.loc[:pd.Timestamp(as_of)]
    me = daily.resample("ME").last()
    # month-end-labelled values from data to the end of that month
    t1 = me.shift(1) / me.shift(12) - 1
    t2 = _per_column_monthly(daily, _above_ma)
    t4 = _per_column_monthly(daily, lambda s: s.pct_change(fill_method=None)
                             .rolling(VOL_DAYS, min_periods=MIN_DAYS).std() * np.sqrt(252))
    t5 = _per_column_monthly(daily, lambda s: s / s.rolling(HIGH_DAYS, min_periods=MIN_DAYS).max() - 1)
    r6 = me / me.shift(6) - 1
    t3 = r6 - _bench_6m(benchmark_usd, me, as_of)
    out = {}
    for k, panel in zip(SIGNALS, (t1, t2, t3, t4, t5)):
        panel = panel.reindex(index=me.index, columns=me.columns)
        panel.index = panel.index + pd.offsets.MonthEnd(1)   # value usable in the next month
        out[k] = panel
    return out


def _bench_6m(bench, me, as_of):
    """6-month benchmark return aligned to `me` (Series broadcast, or per-ticker frame)."""
    if bench is None:
        return pd.DataFrame(np.nan, index=me.index, columns=me.columns)
    if as_of is not None:
        bench = bench.loc[:pd.Timestamp(as_of)]
    b = bench.resample("ME").last().reindex(me.index)
    b6 = b / b.shift(6) - 1
    if isinstance(b6, pd.Series):
        return pd.DataFrame({c: b6 for c in me.columns}, index=me.index)
    return b6.reindex(columns=me.columns)


def signals_at(signals, as_of):
    """Cross-section of each signal built from data up to `as_of` (row as_of month + 1)."""
    label = pd.Timestamp(as_of) + pd.offsets.MonthEnd(0) + pd.offsets.MonthEnd(1)
    return pd.DataFrame({k: (p.loc[label] if label in p.index else pd.Series(np.nan, index=p.columns))
                         for k, p in signals.items()})


def tercile_backtest(signal, returns, higher_is_better=True, cost_bps=10.0, binary=False,
                     min_names=3):
    """Top-tercile equal weight vs long-list equal weight, monthly (method.md section 6).

    Each month t, eligible names have a signal at t (data to t-1) and a month-t
    return. The top round(n/3) names by signal (at least 1; ties broken by
    column order) are held equally weighted; for a binary signal the names with
    signal 1 are held (all eligible names if none). Months with fewer than
    `min_names` eligible names are skipped. Cost: cost_bps x sum|w_t - w_{t-1}
    drifted| charged to the tercile portfolio only; the first month is free.
    The benchmark is the gross equal-weight of the eligible names.
    Returns a DataFrame [strategy, strategy_net, benchmark, active, turnover, n, k].
    """
    idx = signal.index.intersection(returns.index)
    cols = signal.columns.intersection(returns.columns)
    S = signal.loc[idx, cols].to_numpy(dtype=float)
    R = returns.loc[idx, cols].to_numpy(dtype=float)
    valid = ~np.isnan(S) & ~np.isnan(R)
    n = valid.sum(axis=1)
    if binary:
        sel = valid & (S > 0.5)
        none = sel.sum(axis=1) == 0
        sel[none] = valid[none]
    else:
        score = np.where(valid, S if higher_is_better else -S, -np.inf)
        order = np.argsort(-score, axis=1, kind="stable")
        ranks = np.empty_like(order)
        rows = np.arange(len(idx))[:, None]
        ranks[rows, order] = np.arange(S.shape[1])[None, :]
        k = np.maximum(1, np.rint(n / 3)).astype(int)
        sel = valid & (ranks < k[:, None])
    ok = n >= min_names
    sel &= ok[:, None]
    kk = sel.sum(axis=1)
    W = np.where(sel, 1.0, 0.0) / np.maximum(kk, 1)[:, None]
    Wb = np.where(valid & ok[:, None], 1.0, 0.0) / np.maximum(n, 1)[:, None]
    R0 = np.nan_to_num(R)
    gross = (W * R0).sum(axis=1)
    bench = (Wb * R0).sum(axis=1)
    turnover = np.zeros(len(idx))
    if len(idx) > 1:
        drift = W[:-1] * (1 + R0[:-1]) / (1 + gross[:-1])[:, None]
        held_before = kk[:-1] > 0
        turnover[1:] = np.where(held_before, np.abs(W[1:] - drift).sum(axis=1), 0.0)
    net = gross - turnover * cost_bps / 1e4
    df = pd.DataFrame({"strategy": gross, "strategy_net": net, "benchmark": bench,
                       "active": net - bench, "turnover": turnover, "n": n, "k": kk}, index=idx)
    return df[ok]


def _ir_t(active):
    a = active.dropna()
    if len(a) < 12 or a.std() == 0:
        return np.nan, np.nan, len(a), np.nan
    m, s = a.mean(), a.std()
    return float(m / s * np.sqrt(12)), float(m / (s / np.sqrt(len(a)))), len(a), float(m * 12)


def validate_signals(signals, monthly_usd, in_sample_end=IN_SAMPLE_END, cost_bps=10,
                     in_sample_start=IN_SAMPLE_START):
    """Pre-registered validation of each signal (method.md section 6). Uses OOS data by design.

    In-sample = months in [in_sample_start, in_sample_end]; OOS = months after
    in_sample_end. IR = mean/std of monthly active return x sqrt(12);
    t = mean / (std / sqrt(months)). kept = OOS IR > 0 and OOS t > 1.0.
    """
    rows = []
    is_end = pd.Timestamp(in_sample_end)
    for code, panel in signals.items():
        bt = tercile_backtest(panel, monthly_usd, HIGHER_IS_BETTER.get(code, True), cost_bps,
                              binary=code in BINARY)
        ins = bt.loc[pd.Timestamp(in_sample_start):is_end, "active"]
        oos = bt.loc[bt.index > is_end, "active"]
        ir_is, t_is, n_is, a_is = _ir_t(ins)
        ir_oos, t_oos, n_oos, a_oos = _ir_t(oos)
        kept = bool(np.isfinite(ir_oos) and np.isfinite(t_oos) and ir_oos > 0 and t_oos > 1.0)
        rows.append({"signal": code, "description": DESCRIPTION.get(code, ""),
                     "months_is": n_is, "active_ann_is": a_is, "ir_is": ir_is, "t_is": t_is,
                     "months_oos": n_oos, "active_ann_oos": a_oos, "ir_oos": ir_oos, "t_oos": t_oos,
                     "avg_names": float(bt["n"].mean()) if len(bt) else np.nan,
                     "avg_turnover": float(bt["turnover"].mean()) if len(bt) else np.nan,
                     "cost_bps": cost_bps, "kept": kept,
                     "note": "" if kept else "did not add value out of sample"})
    return pd.DataFrame(rows).set_index("signal")


def technical_score(snapshot, kept=None):
    """Mean percentile rank of the kept signals (method.md section 6), 0-1.

    snapshot: tickers x signals (from `signals_at`). kept: iterable of signal
    codes; None means all five (validation not run yet, flagged by the CLI).
    Returns (score Series, list of signals used). An empty kept list gives NaN.
    """
    from .scoring import percentile_scores
    used = [k for k in (SIGNALS if kept is None else kept) if k in snapshot.columns]
    if not used:
        return pd.Series(np.nan, index=snapshot.index), used
    pct = percentile_scores(snapshot, used, {k: HIGHER_IS_BETTER[k] for k in used})
    return pct.mean(axis=1, skipna=True), used
