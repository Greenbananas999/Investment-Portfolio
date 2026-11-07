# GILD Gilead Sciences, Inc.: candidate memo (US growth stock)

Data to 2026-10-31; benchmark IVW (S&P 500 Growth), risk-free BIL. Every number is from `python -m research.candidates.us_growth --ticker GILD --write`. In-sample = 2010-01 to 2017-12 (96 months), out-of-sample (OOS) = 2018-01 onward (106 months).

**Thesis.** Gilead's HIV franchise funds a 2% dividend; the 2017 screen picked it on hepatitis-C growth that was already fading (revenue was $30.4bn in FY2016, the last year filed by end-2017, and $29.4bn in FY2025).

**What drives returns.** HIV share and pricing, new HIV prevention drugs, oncology, and the dividend.

**Record, in-sample vs out-of-sample (monthly, USD).**

| | IS stock | IS IVW | OOS stock | OOS IVW |
|---|---|---|---|---|
| CAGR | 17.1% | 14.6% | 14.4% | 16.3% |
| Volatility | 26.1% | 12.1% | 24.4% | 18.5% |
| Sharpe | 0.73 | 1.19 | 0.57 | 0.77 |
| Info ratio (t) | 0.19 (0.5) | - | -0.02 (-0.1) | - |
| Alpha (t) | 7.5% (0.8) | - | 11.4% (1.4) | - |
| Max drawdown | -42.8% | -13.0% | -29.4% | -30.5% |
| Deflated Sharpe (N=46) | 0.43 | 0.85 | 0.28 | 0.52 |

Rolling 36-month IR above zero: 46% of windows since 2010, 45% of windows wholly inside OOS. Stress (stock vs IVW): 2008 -3% vs -45%; 2013 taper 19% vs 3%; Covid 19% vs -16%; 2022 12% vs -27%; strong-USD months (29) -2.1% vs -3.5% a month.

**Fundamentals (SEC EDGAR, point-in-time).** Fiscal year known at 2017-12-31 vs the latest filed (FY 2025-12-31). Screen fundamental score (2017): 0.88.

| Measure | 2017 | Latest |
|---|---|---|
| Revenue | $30.4bn | $29.4bn |
| Revenue CAGR 3y | 39.5% | 2.6% |
| Operating margin | 58.0% | 34.0% |
| Free cash flow | $16.7bn | $9.5bn |
| ROIC | 37.6% | 18.3% |
| Net debt / EBITDA | 1.03 | 2.49 |
| Trailing P/E | 7.2 | 24.6 |
| FCF yield | 17.8% | 4.6% |

**Forward 7-year expected return (USD).** CAPM 6.5%, DCF implied 10.5%, Grinold-Kroner 7.8% (of which P/E drift, trailing GAAP P/E from n/a to 18.9 over 10 years: 0.0%); consensus 8.3% (8.3% without the P/E drift); Monte Carlo median 8.2%, 5-95% -7.4% to 26.3% (circular block bootstrap, drift set to the consensus). Both ends of the P/E drift are trailing GAAP multiples; the DCF still starts from forward (analyst) earnings. Assumptions: `research/config.py::MarketAssumptions, DCFSettings, GKSettings, MonteCarloSettings; research/candidates/assumptions_us_growth.py::USGrowthAssumptions`.

**Technicals.** No technical signal was kept: the pre-registered test (method.md section 6) found none with OOS IR > 0 and t > 1 for US growth stocks (shortlist.md), so the technical weight is redistributed and no chart signal is used here.

**Risks.** HIV patent expiries, US drug-price negotiation, oncology write-downs (the source of the negative 2026 EPS consensus that makes the analyst growth figure meaningless; capped at the 7% revenue consensus).

**Verdict (analyst rank 6 of 8; the Phase 4 rubric decides).** Drop under method.md section 8 rule 2: OOS Sharpe 0.57 below IVW and IR -0.02, as its weak in-sample IR (0.19) warned. Like REGN it diversified (beta 0.17; up in the Covid and 2022 windows), but that is not the job of the growth sleeve.

> **How to explain this pick**
>
> 1. GILD is a biopharmaceutical company focused on HIV, liver disease and oncology; a screen using only data to 2017 picked it for the second-highest fundamental score, from a hepatitis-C boom.
> 2. From 2018 to 2026-10, which the screen never saw, it returned 14.4% a year against 16.3% for the S&P 500 Growth fund, with a worst fall of -29% (fund -30%).
> 3. Our models expect about 8% a year over the next seven years (5-95% range -7% to 26%), so it is a dividend and defence story, not a growth one, and we are not using it here.

Charts: `reports/candidates/charts/GILD_growth.png`, `reports/candidates/charts/GILD_rolling.png`. Data notes: full = 2010-01 to the last full month (in-sample + out-of-sample); partial final month dropped; buy-and-hold monthly total returns, no trade modelled, no cost charged; local currency = USD, so the local blocks equal the USD blocks; analyst growth capped at 6.98% (assumptions_us_growth.py).
