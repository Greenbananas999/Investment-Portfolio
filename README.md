# 622 Investment Portfolio

Portfolio models for the 622 foreign investment class: $100,000 USD paper
account, at least 70% non-US assets, scored on risk-adjusted return.

## What it does

1. Downloads daily adjusted prices for a set of US-listed international ETFs
   (developed and emerging equity, hedged and unhedged foreign bonds) plus a
   small US sleeve, and daily FX rates. Cached in `data/`.
2. Builds two long-only portfolios with a 25% cap per ETF and the 70% non-US
   floor: **max Sharpe** and **minimum variance** (Ledoit-Wolf covariance,
   shrunk expected returns). Equal weight and ACWI are shown for comparison.
3. Backtests them walk-forward: every 21 trading days it re-optimizes on the
   trailing 3 years only, so every reported return is out of sample. 5 bps
   trading cost on turnover.
4. Reports CAGR, volatility, Sharpe, Sortino, max drawdown, Calmar, final
   value of $100k, FX contribution and turnover, plus the weights to hold today.

## Run it

```bash
pip install -r requirements.txt
python run.py                 # downloads prices on first run, then uses the cache
python run.py --refresh       # re-download
python run.py --max-weight 0.2 --min-non-us 0.8   # try other rules
python run.py --synthetic     # fake data, only to check the code runs
pytest
```

Output lands in `reports/` (`summary.md`, `equity_curve.png`,
`target_weights.csv`, weight history per strategy).

Edit the universe, rules and backtest settings in `portfolio/config.py`.
Prices from another source can be dropped into `data/prices.csv` (date index,
one column per ticker) and `data/fx.csv` (USD per unit of each currency).

## Expected-return research (stocks and sovereign bonds)

A second pipeline in `research/` estimates expected returns for SK Hynix,
Samsung, TSMC, Apple, Nvidia, Meta and Microsoft, plus French OAT and Turkish
government bonds, in local currency and in USD.

| Method | Module | What it gives |
|---|---|---|
| Historical backtest | `historical.py` | CAGR, volatility, Sharpe, drawdown, beta, information ratio, currency effect |
| CAPM (local and global) | `capm.py` | Blume-adjusted betas, cost of equity |
| DCF | `dcf.py` | Forward-earnings FCF model, value vs price, implied return, Monte Carlo on inputs |
| Grinold-Kroner | `grinold_kroner.py` | Dividend yield + inflation + real growth + buybacks + repricing |
| Bonds | `bonds.py` | Yield scenarios, duration, constant-maturity total-return backtest |
| Monte Carlo | `montecarlo.py` | 5-year block-bootstrap outcomes, historical and forward drift |
| Forecast test | `forecast_test.py` | How well each method predicted next-year returns, 2015-2024 |
| Ex-ante frontier | `frontier.py` | Efficient frontier with and without the 70% non-US rule |

```bash
python -m research.fetch        # needs Yahoo Finance + FRED access (run on a home PC)
python research_run.py          # writes reports/research/results.json and summary.md
python -m research.html_report  # writes reports/research/expected_returns.html
python research_run.py --synthetic   # code check only
```

Every judgement call (risk premia, inflation, target P/Es, growth caps, the
memory-cycle fade) is in `research/config.py`. Turkish yield history is not
available from free sources; current Turkish yields are spot quotes in
`config.SPOT_YIELDS`. Drop a monthly `date,yield` CSV at
`data/research/manual/TR_10Y.csv` (or `TR_2Y.csv`) to add them to the backtest.

## Dashboard

An offline web dashboard for exploring the results and explaining each position to the team.

```bash
pip install -r requirements.txt     # plotly is the only dashboard dependency
python -m dashboard                 # builds dashboard/site/ and serves http://localhost:8000
python -m dashboard --no-serve      # build only (then open dashboard/site/index.html directly)
python -m dashboard --port 8080 --open
```

The build reads the JSON in `reports/` (`candidates/*.json`, `candidates/scorecard.csv`, `candidates/reviews/`,
`final/portfolio.json`), the plan documents in `research/plan/`, and `data/research/prices.csv` and `fx.csv`
(for the Compare growth series). It is idempotent: a rebuild replaces `dashboard/site/`.

| Page | What it shows |
|---|---|
| Overview | The final $100k split by position, sleeve, country and currency; rule checks as pass/fail badges; in-sample and out-of-sample Sharpe, information ratio and drawdown for the eight portfolios; growth of $100k with the in-sample period shaded; the Monte Carlo fan and the five targets |
| Positions | One printable card per pick: the three "how to explain this pick" sentences, track record in-sample vs out-of-sample, currency effect, forward estimate, fundamentals, stress table, reviewer verdict and claims, and the runners-up with why they lost |
| Compare | Overlay any of the 38 candidates, faded leaders, controls and benchmarks: growth of $10,000, drawdowns, rolling 36-month Sharpe and information ratio, local vs USD |
| Frontier | The four efficient frontiers (ex-ante/ex-post, with/without the 70% rule) as toggles, with tangency, minimum-variance, guideline and chosen portfolios; hover for weights |
| What-if | Sliders for every position; live expected return, volatility, Sharpe, non-US share, sleeve mix and rule violations; stress-scenario buttons; reset to chosen or guideline |
| Method and evidence | The pre-registered method, change log, signal validation (no technical signal kept), in-sample vs out-of-sample rank tests, review summary, caveats, data sources and reproduce commands |

Offline: Plotly.js is copied from the installed `plotly` package into `dashboard/site/vendor/` at build time, every page
embeds its data as JSON in the HTML, and nothing is fetched from the internet, so the pages also work from `file://`.
Overview, Frontier and What-if show "portfolio results not built yet" until `reports/final/portfolio.json` exists.
Tests: `pytest tests/test_dashboard.py` (a headless-browser check runs only if Playwright is installed).
