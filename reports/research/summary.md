# Expected returns: 7 stocks, French and Turkish bonds (data to 2026-10-23)

## Expected annual return, next 5-10 years

| Asset | CAPM | DCF implied | Grinold-Kroner | Yield-based | Consensus local | Consensus USD |
|---|---|---|---|---|---|---|
| SK Hynix (KRW) | 10.6% | 13.1% | 7.9% | | 10.6% | 11.1% |
| Samsung Electronics (KRW) | 8.6% | 9.3% | 10.7% | | 9.5% | 10.1% |
| Taiwan Semiconductor (TWD) | 7.9% | 10.0% | 14.0% | | 10.6% | 11.5% |
| Apple (USD) | 8.6% | 7.0% | 5.0% | | 6.9% | 6.9% |
| Nvidia (USD) | 12.0% | 15.7% | 18.3% | | 15.3% | 15.3% |
| Meta Platforms (USD) | 9.2% | 11.3% | 11.5% | | 10.7% | 10.7% |
| Microsoft (USD) | 8.5% | 10.2% | 14.5% | | 11.1% | 11.1% |
| France OAT 10Y (EUR) | | | | 4.9% | 4.9% | 5.4% |
| Turkey government 2Y (TRY) | | | | 34.5% | 34.5% | 10.3% |
| Turkey government 10Y (TRY) | | | | 35.7% | 35.7% | 11.2% |

USD = local x expected FX move from relative PPP (inflation gap).

## Historical (since 2010, or listing)

| Asset | CAGR local | CAGR USD | FX effect | Vol USD | Sharpe USD | Max DD USD | Beta ACWI |
|---|---|---|---|---|---|---|---|
| SK Hynix | 28.1% | 27.1% | -1.1% | 48.9% | 0.68 | -53.0% | 1.57 |
| Samsung Electronics | 18.9% | 17.9% | -1.0% | 35.5% | 0.59 | -48.4% | 1.37 |
| Taiwan Semiconductor | 27.6% | 27.5% | -0.1% | 26.3% | 1.00 | -46.0% | 1.07 |
| Apple | 26.9% | 26.9% | 0.0% | 26.4% | 0.98 | -39.5% | 0.99 |
| Nvidia | 44.5% | 44.5% | 0.0% | 44.4% | 1.02 | -62.8% | 1.59 |
| Meta Platforms | 23.9% | 23.9% | 0.0% | 38.0% | 0.71 | -75.4% | 1.27 |
| Microsoft | 20.5% | 20.5% | 0.0% | 23.0% | 0.87 | -30.5% | 0.94 |
| France OAT 10Y | 1.2% | -0.2% | -1.4% | 9.9% | -0.12 | -39.0% | 0.33 |

## 70/30 sample portfolio (2012-06-30 to 2026-09-30, USD, monthly rebalanced)

Portfolio: CAGR 27.4%, vol 21.6%, Sharpe 1.16, info ratio vs ACWI 0.97, max DD -40.7%.  ACWI: CAGR 11.9%, Sharpe 0.78.

## Monte Carlo, 5 years, USD (forward drift)

| Asset | 5th pct | Median | 95th pct | P(loss over 5y) | 1y VaR 95% |
|---|---|---|---|---|---|
| SKHYNIX | -20.4% | 10.5% | 62.2% | 31% | 45.1% |
| SAMSUNG | -15.3% | 8.6% | 46.5% | 30% | 36.0% |
| TSMC | -7.1% | 11.9% | 34.6% | 16% | 25.8% |
| AAPL | -12.4% | 6.4% | 27.9% | 29% | 31.4% |
| NVDA | -17.9% | 15.7% | 61.1% | 24% | 49.0% |
| META | -16.0% | 11.9% | 47.7% | 26% | 44.6% |
| MSFT | -5.1% | 10.9% | 27.3% | 13% | 22.8% |
| FR_OAT10 | -2.7% | 5.6% | 13.5% | 13% | 13.2% |
| PORTFOLIO | -4.7% | 13.3% | 33.9% | 12% | 23.0% |

## How well did the methods forecast? (next-year USD return, 2015-2024)

| Method | Mean abs error | Bias | Rank correlation |
|---|---|---|---|
| capm | 54.0% | -38.4% | 0.13 |
| flat8 | 54.0% | -37.4% | n/a |
| hist5 | 46.7% | -16.1% | 0.24 |
| yield | 9.5% | 0.7% | n/a |

## Ex-ante max-Sharpe mix (>=70% non-US, 25% cap)

Expected 10.0%, vol 16.3%, Sharpe 0.37: SKHYNIX 4%, SAMSUNG 16%, TSMC 25%, NVDA 9%, META 2%, MSFT 19%, FR_OAT10 25%
