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
