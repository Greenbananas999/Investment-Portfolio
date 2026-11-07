# REGN Regeneron Pharmaceuticals, Inc.: candidate memo (US growth stock)

Data to 2026-10-31; benchmark IVW (S&P 500 Growth), risk-free BIL. Every number is from `python -m research.candidates.us_growth --ticker REGN --write`. In-sample = 2010-01 to 2017-12 (96 months), out-of-sample (OOS) = 2018-01 onward (106 months).

**Thesis.** Regeneron earns most of its profit from two franchises, the eye drug Eylea and the immunology drug Dupixent, and reinvests in a large antibody pipeline. Its returns follow approvals and patents, not the tech cycle (OOS beta to IVW 0.08).

**What drives returns.** Dupixent growth, Eylea against biosimilars, pipeline readouts, and buybacks.

**Record, in-sample vs out-of-sample (monthly, USD).**

| | IS stock | IS IVW | OOS stock | OOS IVW |
|---|---|---|---|---|
| CAGR | 40.9% | 14.6% | 10.9% | 16.3% |
| Volatility | 42.8% | 12.1% | 32.8% | 18.5% |
| Sharpe | 1.00 | 1.19 | 0.40 | 0.77 |
| Info ratio (t) | 0.70 (2.0) | - | -0.04 (-0.1) | - |
| Alpha (t) | 26.7% (1.7) | - | 11.9% (1.1) | - |
| Max drawdown | -38.1% | -13.0% | -58.5% | -30.5% |
| Deflated Sharpe (N=46) | 0.74 | 0.85 | 0.14 | 0.52 |

Rolling 36-month IR above zero: 55% of windows since 2010, 45% of windows wholly inside OOS. Stress (stock vs IVW): 2008 -35% vs -45%; 2013 taper 13% vs 3%; Covid 44% vs -16%; 2022 19% vs -27%; strong-USD months (29) 0.1% vs -3.5% a month.

**Fundamentals (SEC EDGAR, point-in-time).** Fiscal year known at 2017-12-31 vs the latest filed (FY 2025-12-31). Screen fundamental score (2017): 0.72.

| Measure | 2017 | Latest |
|---|---|---|
| Revenue | $4.9bn | $14.3bn |
| Revenue CAGR 3y | 32.2% | 5.6% |
| Operating margin | 27.4% | 24.9% |
| Free cash flow | $1.5bn | $5.0bn |
| ROIC | 22.9% | 10.2% |
| Net debt / EBITDA | -0.37 | -0.27 |
| Trailing P/E | 48.8 | 21.8 |
| FCF yield | n/a | n/a |

**Forward 7-year expected return (USD).** CAPM 5.7%, DCF implied 10.3%, Grinold-Kroner 5.6% (of which P/E drift, trailing GAAP P/E from 20.0 to 20.8 over 10 years: 0.4%); consensus 7.2% (7.1% without the P/E drift); Monte Carlo median 7.3%, 5-95% -15.3% to 35.5% (circular block bootstrap, drift set to the consensus). Both ends of the P/E drift are trailing GAAP multiples; the DCF still starts from forward (analyst) earnings. Assumptions: `research/config.py::MarketAssumptions, DCFSettings, GKSettings, MonteCarloSettings; research/candidates/assumptions_us_growth.py::USGrowthAssumptions`.

**Technicals.** No technical signal was kept: the pre-registered test (method.md section 6) found none with OOS IR > 0 and t > 1 for US growth stocks (shortlist.md), so the technical weight is redistributed and no chart signal is used here.

**Risks.** The Eylea patent cliff, US drug-price negotiation, clinical failures; revenue growth fell from 32% a year (3 years to FY2016) to 6% (to FY2025). Its DCF rests on a low CAPM discount rate (beta 0.4) and 81% of value in the terminal value, so it is fragile.

**Verdict (analyst rank 7 of 8; the Phase 4 rubric decides).** Drop under method.md section 8 rule 2: OOS Sharpe 0.40 below IVW and IR -0.04. It was a real diversifier (up 44% in the Covid window and 19% in 2022 while IVW fell), which Phase 5 may still want from a fund, not from this stock.

> **How to explain this pick**
>
> 1. REGN is a biotechnology company (Eylea, Dupixent with Sanofi, Libtayo); a screen using only data to 2017 picked it for a different return driver from tech with a 41% in-sample return.
> 2. From 2018 to 2026-10, which the screen never saw, it returned 10.9% a year against 16.3% for the S&P 500 Growth fund, with a worst fall of -59% (fund -30%).
> 3. Our models expect about 7% a year over the next seven years (5-95% range -15% to 36%), so it did not hold up after 2018 and we are not using it.

Charts: `reports/candidates/charts/REGN_growth.png`, `reports/candidates/charts/REGN_rolling.png`. Data notes: full = 2010-01 to the last full month (in-sample + out-of-sample); partial final month dropped; buy-and-hold monthly total returns, no trade modelled, no cost charged; local currency = USD, so the local blocks equal the USD blocks.
