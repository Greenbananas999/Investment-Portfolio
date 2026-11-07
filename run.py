"""End-to-end pipeline: data -> optimize -> walk-forward backtest -> report.

    python run.py              # use cached data/ CSVs, download if missing
    python run.py --refresh    # force a fresh download from Yahoo Finance
    python run.py --synthetic  # random-walk prices, for testing the code only

Writes reports/summary.md, reports/equity_curve.png, reports/target_weights.csv
and reports/weights_history_<strategy>.csv.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio import backtest, config, data

REPORTS = Path(__file__).resolve().parent / "reports"
LABELS = {"max_sharpe": "Max Sharpe", "min_variance": "Min variance",
          "equal_weight": "Equal weight", "benchmark": f"{config.BENCHMARK} (benchmark)"}


def synthetic_data(seed=0, years=12):
    """Random-walk prices and FX with the real universe's tickers. Testing only."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(end="2026-10-09", periods=years * 252)
    tickers = config.TICKERS + [config.RISK_FREE, config.BENCHMARK]
    n = len(tickers)
    a = rng.normal(size=(n, n)) * 0.006
    cov = a @ a.T + np.eye(n) * 0.00005
    mu = rng.normal(0.0003, 0.0002, n)
    rets = rng.multivariate_normal(mu, cov, len(days))
    rets[:, tickers.index(config.RISK_FREE)] = 0.0001
    prices = pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=days, columns=tickers)
    prices.loc[: days[400], "INDA"] = np.nan  # a late listing, like the real INDA
    ccys = list(config.FX_TICKERS_DIRECT) + list(config.FX_TICKERS_INVERSE)
    fx = pd.DataFrame(np.cumprod(1 + rng.normal(0, 0.005, (len(days), len(ccys))), axis=0),
                      index=days, columns=ccys)
    return prices, fx


def fmt(v, key):
    if key in ("Sharpe", "Sortino", "Calmar"):
        return f"{v:.2f}"
    if key == "Final value ($)":
        return f"${v:,.0f}"
    return f"{v:.1%}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download prices")
    ap.add_argument("--synthetic", action="store_true", help="use fake data (code test only)")
    ap.add_argument("--start", default=None, help="first out-of-sample date")
    ap.add_argument("--max-weight", type=float, default=None)
    ap.add_argument("--min-non-us", type=float, default=None)
    args = ap.parse_args()

    rules = config.Rules()
    settings = config.BacktestSettings()
    if args.max_weight is not None:
        rules.max_weight = args.max_weight
    if args.min_non_us is not None:
        rules.min_non_us = args.min_non_us
    if args.start:
        settings.start = args.start

    if args.synthetic:
        prices, fx = synthetic_data()
        settings.start = str(prices.index[settings.lookback_days].date())
    else:
        prices = data.load_prices(refresh=args.refresh)
        fx = data.load_fx(refresh=args.refresh)

    rets = data.daily_returns(prices)
    asset_ret = rets[config.TICKERS]
    rf = rets[config.RISK_FREE].fillna(0.0)
    fx_exp = data.fx_exposure_returns(fx, rets.index)

    results = {s: backtest.run(s, asset_ret, rf, fx_exp, rules, settings)
               for s in backtest.STRATEGIES}
    oos = results["max_sharpe"].returns.index
    bench = rets[config.BENCHMARK].reindex(oos).fillna(0.0)

    table = {}
    for s, r in results.items():
        table[LABELS[s]] = backtest.metrics(r.returns, rf, r.fx_contribution, r.turnover, rules.capital)
    table[LABELS["benchmark"]] = backtest.metrics(bench, rf, capital=rules.capital)
    table = pd.DataFrame(table)

    # Weights to hold today, from the most recent lookback window.
    window = asset_ret.iloc[-settings.lookback_days:]
    rf_window = rf.iloc[-settings.lookback_days:]
    today = pd.DataFrame({LABELS[s]: backtest.target_weights(s, window, rf_window, rules)
                          for s in backtest.STRATEGIES}, index=config.TICKERS)

    REPORTS.mkdir(exist_ok=True)
    today.to_csv(REPORTS / "target_weights.csv", float_format="%.4f")
    for s, r in results.items():
        r.weights.to_csv(REPORTS / f"weights_history_{s}.csv", float_format="%.4f")
    _plot(results, bench, REPORTS / "equity_curve.png", rules.capital)
    _write_summary(table, today, rules, settings, oos, args.synthetic)

    print(table.apply(lambda col: [fmt(v, k) if pd.notna(v) else "" for k, v in col.items()]).to_string())
    print(f"\nReport written to {REPORTS / 'summary.md'}")


def _plot(results, bench, path, capital):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    series = {LABELS[s]: r.returns for s, r in results.items()}
    series[LABELS["benchmark"]] = bench
    for label, r in series.items():
        wealth = capital * (1 + r).cumprod()
        ax1.plot(wealth.index, wealth, label=label, lw=1.4)
        ax2.plot(wealth.index, wealth / wealth.cummax() - 1, lw=1)
    ax1.set_ylabel("Portfolio value ($)")
    ax1.legend(frameon=False)
    ax1.set_title("Walk-forward backtest (out of sample)")
    ax2.set_ylabel("Drawdown")
    ax2.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _write_summary(table, today, rules, settings, oos, synthetic):
    shown = table.apply(lambda col: [fmt(v, k) if pd.notna(v) else "" for k, v in col.items()])
    weights = today[(today > 0.0005).any(axis=1)].copy()
    dollars = (weights * rules.capital).round(-1)
    w_tbl = weights.map(lambda v: f"{v:.1%}" if v > 0.0005 else "")
    w_tbl["Non-US"] = [("yes" if config.ASSETS[t].non_us else "no") for t in weights.index]
    non_us_share = {c: today.loc[[a.ticker for a in config.UNIVERSE if a.non_us], c].sum()
                    for c in today.columns}

    lines = []
    if synthetic:
        lines += ["> **SYNTHETIC DATA.** These numbers come from random-walk prices and only",
                  "> show that the code runs. They say nothing about real markets.", ""]
    lines += [
        "# Portfolio backtest summary", "",
        f"Out-of-sample period: {oos[0].date()} to {oos[-1].date()} "
        f"({len(oos) / 252:.1f} years). Rebalanced every {settings.rebalance_days} trading days "
        f"on a {settings.lookback_days}-day lookback, {settings.cost_bps:.0f} bps trading cost.",
        f"Rules: long-only, at least {rules.min_non_us:.0%} non-US, max {rules.max_weight:.0%} "
        f"per ETF, ${rules.capital:,.0f} starting capital. Sharpe uses {config.RISK_FREE} as the risk-free rate.",
        "", "## Results", "", shown.to_markdown(), "",
        "FX contribution is the annualized return that came from currency moves on unhedged holdings "
        "(approximate fund currency mixes in `portfolio/config.py`).", "",
        "![equity curve](equity_curve.png)", "",
        "## Target weights today", "",
        w_tbl.to_markdown(), "",
        "Non-US share: " + ", ".join(f"{k} {v:.0%}" for k, v in non_us_share.items()), "",
        "Dollar amounts on $100,000:", "", dollars[dollars.sum(axis=1) > 0].to_markdown(), "",
    ]
    (REPORTS / "summary.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
