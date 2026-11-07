# Candidate results schema (`reports/candidates/<ID>.json`)

One JSON file per candidate, written by the Phase 3 analyst subagents and read
by the dashboard (Phase 6), the scorecard (Phase 4) and the portfolio builder
(Phase 5). `<ID>` is the Yahoo ticker with `.` and `^` replaced by `_`
(`2330_TW.json`, `NOVO-B_CO.json`, `EMB.json`).

Every number is a decimal (0.12 = 12%), annualised unless the key says
otherwise, computed from **monthly total returns** unless the key says
`daily`. Missing values are `null`, never 0. Dates are `YYYY-MM-DD`.

```jsonc
{
  "schema_version": 1,
  "id": "2330_TW",
  "ticker": "2330.TW",                 // Yahoo ticker used for prices
  "usd_ticker": "TSM",                 // US listing if one exists, else null
  "name": "Taiwan Semiconductor",
  "position_type": "intl_growth_stock",// us_growth_stock | intl_growth_stock | em_bond | other | overlay
  "instrument": "stock",               // stock | etf | mutual_fund | index | overlay
  "country": "TW", "currency": "TWD", "sector": "Semiconductors",
  "non_us": true,                      // per the non-US rule in method.md
  "benchmark": "EFG_EEM_5050",         // benchmark id from method.md
  "data": {
    "price_start": "2005-01-03", "price_end": "2026-11-06",
    "months_total": 262, "months_in_sample": 96, "months_out_of_sample": 106,
    "sources": ["data/research/prices.csv", "data/research/fx.csv"],
    "fund_fee": null,                  // expense ratio for funds, else null
    "notes": "any data caveat"
  },
  "metrics": {                         // same block repeated per window and currency
    "in_sample":     { "usd": { ...METRICS }, "local": { ...METRICS } },
    "out_of_sample": { "usd": { ...METRICS }, "local": { ...METRICS } },
    "full":          { "usd": { ...METRICS }, "local": { ...METRICS } }
  },
  "rolling": {                         // 36-month windows, month-end dates, USD
    "dates": ["2012-12-31", "..."],
    "sharpe": [0.8, "..."], "info_ratio": [0.1, "..."],
    "share_ir_positive_oos": 0.71      // consistency metric from the rubric
  },
  "currency": {                        // out-of-sample, annualised
    "local_return": 0.14, "fx_return": -0.01, "usd_return": 0.13,
    "hedged_return": 0.135, "hedge_cost": 0.005,   // from covered interest parity
    "fx_vol_share": 0.12               // share of USD variance that came from FX
  },
  "expected_return_7y": {              // forward-looking, USD unless noted
    "methods": { "capm": 0.09, "dcf": 0.11, "grinold_kroner": 0.10, "yield": null, "monte_carlo_median": 0.10 },
    "consensus_usd": 0.10, "consensus_local": 0.095,
    "range_5_95": [-0.02, 0.22],
    "assumptions": "research/config.py::MarketAssumptions, DCFSettings",
    "command": "python -m research.candidates.intl_growth --ticker 2330.TW"
  },
  "stress": {                          // total USD return over each window
    "gfc_2008":      { "start": "2007-10-31", "end": "2009-02-28", "return": -0.55, "benchmark": -0.50 },
    "taper_2013":    { "start": "2013-05-31", "end": "2013-08-31", "return": -0.08, "benchmark": -0.10 },
    "covid_2020":    { "start": "2020-01-31", "end": "2020-03-31", "return": -0.20, "benchmark": -0.22 },
    "inflation_2022":{ "start": "2021-12-31", "end": "2022-10-31", "return": -0.35, "benchmark": -0.30 },
    "strong_usd":    { "definition": "months when DXY rose >= 2%", "avg_return": -0.03, "benchmark": -0.02 }
  },
  "screens": {                         // from Phase 2, in-sample only
    "fundamental_score": 0.72, "technical_score": 0.61, "hard_screens_passed": true,
    "detail": { "rev_growth_3y": 0.15, "roic": 0.25, "momentum_12_1": 0.30, "above_200dma": true }
  },
  "rubric": {                          // filled by the planner in Phase 4, weights from method.md
    "scores": { "oos_sharpe": 0.8, "oos_ir": 0.6, "...": 0.0 }, "total": 0.0, "rank_in_type": null
  },
  "review": {                          // Phase 4 reviewer verdicts
    "reviewer": "opus", "date": null, "verdict": null,   // pass | downgrade | fail
    "claims": [ { "claim": "OOS Sharpe 0.9", "status": "pass", "note": "" } ]
  },
  "explain": [                         // three plain-English sentences for John's team
    "sentence 1", "sentence 2", "sentence 3"
  ],
  "memo": "research/candidates/memos/2330_TW.md",
  "charts": { "growth": "reports/candidates/charts/2330_TW_growth.png" },
  "reproduce": "python -m research.candidates.intl_growth --ticker 2330.TW --write"
}
```

`METRICS` block:

```jsonc
{ "start": "2018-01-31", "end": "2026-10-31", "months": 106,
  "cagr": 0.0, "vol": 0.0, "sharpe": 0.0, "sortino": 0.0, "max_drawdown": 0.0,
  "calmar": 0.0, "beta": 0.0, "alpha": 0.0, "tracking_error": 0.0, "info_ratio": 0.0,
  "up_capture": 0.0, "down_capture": 0.0,
  "t_stat_alpha": 0.0, "t_stat_ir": 0.0, "deflated_sharpe": null,
  "best_month": 0.0, "worst_month": 0.0, "pct_positive_months": 0.0 }
```

Benchmarks and the risk-free rate are the ones in `research/plan/method.md`.
Overlays (`position_type: overlay`) use the same file with `metrics` holding
the **difference** overlay-minus-underlying and an extra `overlay` block
(`underlying`, `strategy`, `assumptions`, `with`, `without`).

Portfolio-level results (Phase 5) go in `reports/final/portfolio.json`;
schema to be added there when Phase 5 starts.
