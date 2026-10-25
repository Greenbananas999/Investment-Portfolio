"""Expected-return research: 7 stocks + French and Turkish government bonds.

    python research_run.py              # uses data/research/ (see research/fetch.py)
    python research_run.py --synthetic  # random data, to check the code runs

Methods (each in research/):
  historical       backtest of realised returns, local currency and USD
  capm             local and global CAPM
  dcf              forward-earnings DCF, implied return, Monte Carlo on inputs
  grinold_kroner   building-block expected return
  bonds            yield-based scenarios and a constant-maturity backtest
  montecarlo       5-year block-bootstrap simulation (historical and forward)
  forecast_test    how well each method forecast the next year, 2015-2024
  frontier         ex-ante efficient frontier from the model expected returns

Writes reports/research/results.json and reports/research/summary.md.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research import (bonds, capm, config, data, dcf, forecast_test, frontier, fxview,
                      grinold_kroner, historical, montecarlo)

OUT = Path(__file__).resolve().parent / "reports" / "research"


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else round(float(o), 6)
    if isinstance(o, np.integer):
        return int(o)
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    args = ap.parse_args()
    ds = data.synthetic() if args.synthetic else data.Dataset.load()
    a = config.MarketAssumptions()
    mcs = config.MonteCarloSettings()

    assets, hist = historical.run(ds, a)

    stocks = {}
    for s in config.STOCKS:
        c = capm.estimate(s, ds, a)
        d = dcf.run(s, ds, a, c["cost_of_equity"])
        g = grinold_kroner.run(s, ds, a)
        methods_local = {"CAPM": c["expected_local"], "DCF implied": d and d.get("expected_local"),
                         "Grinold-Kroner": g["expected_local"]}
        vals = [v for v in methods_local.values() if v is not None and np.isfinite(v)]
        cons_local = float(np.mean(vals))
        stocks[s.key] = {
            "name": s.name, "ticker": s.ticker, "currency": s.currency, "country": s.country,
            "capm": c, "dcf": d, "gk": g, "methods_local": methods_local,
            "methods_usd": {k: (fxview.to_usd(v, s.currency, ds, a) if v is not None else None)
                            for k, v in methods_local.items()},
            "consensus_local": cons_local,
            "consensus_usd": fxview.to_usd(cons_local, s.currency, ds, a),
            "fx_views": fxview.all_views(s.currency, ds, a),
            "price": float(ds.prices[s.ticker].dropna().iloc[-1]),
        }

    bond_out = {}
    for b in config.BONDS:
        e = bonds.expected(b, ds, a)
        if e is None:
            continue
        bond_out[b.key] = {"name": b.name, "currency": b.currency, "maturity": b.maturity_years,
                           "has_history": b.key in assets, **e, "consensus_local": e["expected_local"], "consensus_usd": e["expected_usd"]}

    # Monte Carlo on the joint USD (and local) history.
    keys = [k for k in assets]
    usd = pd.DataFrame({k: assets[k][1] for k in keys}).dropna()
    local = pd.DataFrame({k: assets[k][0] for k in keys}).dropna()
    targets_usd = {k: (stocks.get(k) or bond_out.get(k))["consensus_usd"] for k in keys}
    targets_loc = {k: (stocks.get(k) or bond_out.get(k))["consensus_local"] for k in keys}
    port_info, _ = historical.sample_portfolio(assets, ds, a)
    w = port_info["weights"]
    mc = {"sample": {"start": str(usd.index[0].date()), "end": str(usd.index[-1].date()), "months": len(usd)},
          "usd_historical": montecarlo.simulate(usd, mcs, None, w),
          "usd_forward": montecarlo.simulate(usd, mcs, targets_usd, w),
          "local_forward": montecarlo.simulate(local, mcs, targets_loc)}

    fc_summary, fc_rows = forecast_test.run(assets, ds, a)

    non_us = np.array([k in ("SKHYNIX", "SAMSUNG", "TSMC") or k.startswith(("FR_", "TR_")) for k in keys])
    S = frontier.shrunk_cov(usd[keys].to_numpy())
    mu = np.array([targets_usd[k] for k in keys])
    fr = {"rule_70": frontier.frontier(mu, S, keys, non_us, a.risk_free["USD"], 0.25, 0.70),
          "unconstrained": frontier.frontier(mu, S, keys, non_us, a.risk_free["USD"], 0.25, 0.0)}

    results = {
        "as_of": str(ds.prices.dropna(how="all").index[-1].date()),
        "synthetic": ds.synthetic,
        "assumptions": a.__dict__, "dcf_settings": config.DCFSettings().__dict__,
        "gk_settings": config.GKSettings().__dict__,
        "historical": hist, "growth": historical.growth_series(assets),
        "sample_portfolio": port_info,
        "stocks": stocks, "bonds": bond_out, "monte_carlo": mc,
        "forecast_test": fc_summary, "frontier": fr,
        "fx_history": {c: {"cagr_10y": float(((1 + ds.fx_returns(c).iloc[-120:]).prod()) ** 0.1 - 1)}
                       for c in ("KRW", "TWD", "EUR", "TRY")},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(clean(results), indent=1))
    fc_rows.to_csv(OUT / "forecast_test_rows.csv", index=False)
    write_summary(results)
    print((OUT / "summary.md").read_text())


def pct(v, d=1):
    return "n/a" if v is None or not np.isfinite(v) else f"{v * 100:.{d}f}%"


def write_summary(r):
    L = [f"# Expected returns: 7 stocks, French and Turkish bonds (data to {r['as_of']})", ""]
    if r["synthetic"]:
        L += ["**SYNTHETIC DATA: code check only, not results.**", ""]
    L += ["## Expected annual return, next 5-10 years", "",
          "| Asset | CAPM | DCF implied | Grinold-Kroner | Yield-based | Consensus local | Consensus USD |",
          "|---|---|---|---|---|---|---|"]
    for k, s in r["stocks"].items():
        m = s["methods_local"]
        L.append(f"| {s['name']} ({s['currency']}) | {pct(m['CAPM'])} | {pct(m['DCF implied'])} | "
                 f"{pct(m['Grinold-Kroner'])} | | {pct(s['consensus_local'])} | {pct(s['consensus_usd'])} |")
    for k, b in r["bonds"].items():
        L.append(f"| {b['name']} ({b['currency']}) | | | | {pct(b['expected_local'])} | "
                 f"{pct(b['consensus_local'])} | {pct(b['consensus_usd'])} |")
    L += ["", "USD = local x expected FX move from relative PPP (inflation gap).", "",
          "## Historical (since 2010, or listing)", "",
          "| Asset | CAGR local | CAGR USD | FX effect | Vol USD | Sharpe USD | Max DD USD | Beta ACWI |",
          "|---|---|---|---|---|---|---|---|"]
    for k, h in r["historical"].items():
        p = h["periods"]["Since 2010"]
        L.append(f"| {h['label']} | {pct(p['local']['CAGR'])} | {pct(p['usd']['CAGR'])} | "
                 f"{pct(p['fx_contribution'])} | {pct(p['usd']['Volatility'])} | {p['usd']['Sharpe']:.2f} | "
                 f"{pct(p['usd']['Max drawdown'])} | {p['usd'].get('Beta', float('nan')):.2f} |")
    sp = r["sample_portfolio"]
    L += ["", f"## 70/30 sample portfolio ({sp['start']} to {sp['end']}, USD, monthly rebalanced)", "",
          f"Portfolio: CAGR {pct(sp['portfolio']['CAGR'])}, vol {pct(sp['portfolio']['Volatility'])}, "
          f"Sharpe {sp['portfolio']['Sharpe']:.2f}, info ratio vs ACWI {sp['portfolio']['Info ratio']:.2f}, "
          f"max DD {pct(sp['portfolio']['Max drawdown'])}.  ACWI: CAGR {pct(sp['acwi']['CAGR'])}, Sharpe {sp['acwi']['Sharpe']:.2f}.", "",
          "## Monte Carlo, 5 years, USD (forward drift)", "",
          "| Asset | 5th pct | Median | 95th pct | P(loss over 5y) | 1y VaR 95% |", "|---|---|---|---|---|---|"]
    for k, m in r["monte_carlo"]["usd_forward"].items():
        L.append(f"| {k} | {pct(m['annualised']['5'])} | {pct(m['annualised']['50'])} | {pct(m['annualised']['95'])} | "
                 f"{pct(m['prob_loss_5y'], 0)} | {pct(m['var95_1y'])} |")
    L += ["", "## How well did the methods forecast? (next-year USD return, 2015-2024)", "",
          "| Method | Mean abs error | Bias | Rank correlation |", "|---|---|---|---|"]
    for k, f in r["forecast_test"].items():
        rc = "n/a" if f["rank_corr"] is None else f"{f['rank_corr']:.2f}"
        L.append(f"| {k} | {pct(f['mae'])} | {pct(f['bias'])} | {rc} |")
    ms = r["frontier"]["rule_70"]["max_sharpe"]
    L += ["", "## Ex-ante max-Sharpe mix (>=70% non-US, 25% cap)", "",
          f"Expected {pct(ms['ret'])}, vol {pct(ms['vol'])}, Sharpe {ms['sharpe']:.2f}: " +
          ", ".join(f"{k} {v:.0%}" for k, v in ms["weights"].items() if v > 0.005)]
    (OUT / "summary.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
