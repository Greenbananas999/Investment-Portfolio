# AMZN Amazon.com, Inc.: candidate memo (US growth stock)

Data to 2026-10-31; benchmark IVW (S&P 500 Growth), risk-free BIL. Every number is from `python -m research.candidates.us_growth --ticker AMZN --write`. In-sample = 2010-01 to 2017-12 (96 months), out-of-sample (OOS) = 2018-01 onward (106 months).

**Thesis.** Amazon combines retail and advertising with AWS, its most profitable segment; growth now depends on cloud and AI demand and on retail margins (operating margin rose from 3% in FY2016 (the last year filed by end-2017) to 11% in FY2025 on EDGAR figures).

**What drives returns.** AWS growth and margin, advertising, retail operating margin, and the level of data-centre capital spending.

**Record, in-sample vs out-of-sample (monthly, USD).**

| | IS stock | IS IVW | OOS stock | OOS IVW |
|---|---|---|---|---|
| CAGR | 31.0% | 14.6% | 17.4% | 16.3% |
| Volatility | 27.6% | 12.1% | 32.4% | 18.5% |
| Sharpe | 1.12 | 1.19 | 0.58 | 0.77 |
| Info ratio (t) | 0.72 (2.0) | - | 0.19 (0.6) | - |
| Alpha (t) | 12.3% (1.4) | - | -0.2% (-0.0) | - |
| Max drawdown | -23.7% | -13.0% | -52.1% | -30.5% |
| Deflated Sharpe (N=46) | 0.83 | 0.85 | 0.29 | 0.52 |

Rolling 36-month IR above zero: 80% of windows since 2010, 58% of windows wholly inside OOS. Stress (stock vs IVW): 2008 -27% vs -45%; 2013 taper 11% vs 3%; Covid -3% vs -16%; 2022 -39% vs -27%; strong-USD months (29) -1.6% vs -3.5% a month.

**Fundamentals (SEC EDGAR, point-in-time).** Fiscal year known at 2017-12-31 vs the latest filed (FY 2025-12-31). Screen fundamental score (2017): 0.72.

| Measure | 2017 | Latest |
|---|---|---|
| Revenue | $136.0bn | $716.9bn |
| Revenue CAGR 3y | 22.2% | 11.7% |
| Operating margin | 3.1% | 11.2% |
| Free cash flow | $9.7bn | $139.5bn |
| ROIC | 30.2% | 16.3% |
| Net debt / EBITDA | -1.00 | -0.12 |
| Trailing P/E | 238.7 | 36.2 |
| FCF yield | 1.7% | 5.0% |

**Forward 7-year expected return (USD).** CAPM 9.9%, DCF implied 6.1%, Grinold-Kroner 8.3% (of which P/E drift, trailing GAAP P/E from 21.0 to 23.0 over 10 years: 0.9%); consensus 8.1% (7.8% without the P/E drift); Monte Carlo median 8.2%, 5-95% -8.3% to 27.1% (circular block bootstrap, drift set to the consensus). Both ends of the P/E drift are trailing GAAP multiples; the DCF still starts from forward (analyst) earnings. Assumptions: `research/config.py::MarketAssumptions, DCFSettings, GKSettings, MonteCarloSettings; research/candidates/assumptions_us_growth.py::USGrowthAssumptions`.

**Technicals.** No technical signal was kept: the pre-registered test (method.md section 6) found none with OOS IR > 0 and t > 1 for US growth stocks (shortlist.md), so the technical weight is redistributed and no chart signal is used here.

**Risks.** Heavy capex lowering free cash flow, competition in cloud, antitrust, consumer spending; no dividend. The DCF implied return (6%) is the lowest of the eight.

**Verdict (analyst rank 4 of 8; the Phase 4 rubric decides).** Runner-up, ranked fourth: it roughly matched the S&P 500 Growth fund out of sample (alpha 0%, IR 0.19, t 0.6) with a deeper drawdown (-52% vs -30%). Its forward consensus (8%) is in the bottom three of the eight.

> **How to explain this pick**
>
> 1. AMZN is the largest online retailer and a leading cloud provider (AWS); a screen using only data to 2017 picked it for a consistent in-sample record (Sharpe 1.1, drawdown -24%).
> 2. From 2018 to 2026-10, which the screen never saw, it returned 17.4% a year against 16.3% for the S&P 500 Growth fund, with a worst fall of -52% (fund -30%).
> 3. Our models expect about 8% a year over the next seven years (5-95% range -8% to 27%), so it is a runner-up: a fine company, but no better than holding the growth index.

Charts: `reports/candidates/charts/AMZN_growth.png`, `reports/candidates/charts/AMZN_rolling.png`. Data notes: full = 2010-01 to the last full month (in-sample + out-of-sample); partial final month dropped; buy-and-hold monthly total returns, no trade modelled, no cost charged; local currency = USD, so the local blocks equal the USD blocks.
