# ADBE Adobe Inc.: candidate memo (US growth stock)

Data to 2026-10-31; benchmark IVW (S&P 500 Growth), risk-free BIL. Every number is from `python -m research.candidates.us_growth --ticker ADBE --write`. In-sample = 2010-01 to 2017-12 (96 months), out-of-sample (OOS) = 2018-01 onward (106 months).

**Thesis.** Adobe sells subscription software for creative and document work with high margins and buybacks; the open question is whether generative AI tools erode its pricing power or extend it.

**What drives returns.** Creative Cloud and Document Cloud subscriptions, AI monetisation, margins, buybacks.

**Record, in-sample vs out-of-sample (monthly, USD).**

| | IS stock | IS IVW | OOS stock | OOS IVW |
|---|---|---|---|---|
| CAGR | 21.5% | 14.6% | 4.1% | 16.3% |
| Volatility | 23.0% | 12.1% | 34.1% | 18.5% |
| Sharpe | 0.97 | 1.19 | 0.21 | 0.77 |
| Info ratio (t) | 0.43 (1.2) | - | -0.26 (-0.8) | - |
| Alpha (t) | 4.8% (0.7) | - | -8.7% (-0.9) | - |
| Max drawdown | -31.7% | -13.0% | -69.4% | -30.5% |
| Deflated Sharpe (N=46) | 0.68 | 0.85 | 0.05 | 0.52 |

Rolling 36-month IR above zero: 68% of windows since 2010, 34% of windows wholly inside OOS. Stress (stock vs IVW): 2008 -65% vs -45%; 2013 taper 1% vs 3%; Covid -9% vs -16%; 2022 -44% vs -27%; strong-USD months (29) -6.9% vs -3.5% a month.

**Fundamentals (SEC EDGAR, point-in-time).** Fiscal year known at 2017-12-31 vs the latest filed (FY 2025-11-28). Screen fundamental score (2017): 0.64.

| Measure | 2017 | Latest |
|---|---|---|
| Revenue | $5.9bn | $23.8bn |
| Revenue CAGR 3y | 13.0% | 10.5% |
| Operating margin | 25.5% | 36.6% |
| Free cash flow | $2.0bn | $9.9bn |
| ROIC | 19.0% | 57.3% |
| Net debt / EBITDA | -0.55 | 0.08 |
| Trailing P/E | 75.5 | 14.3 |
| FCF yield | 2.3% | 10.0% |

**Forward 7-year expected return (USD).** CAPM 9.5%, DCF implied 19.4%, Grinold-Kroner 16.0% (of which P/E drift, trailing GAAP P/E from 13.4 to 23.0 over 10 years: 5.6%); consensus 15.0% (13.1% without the P/E drift); Monte Carlo median 15.2%, 5-95% -4.7% to 37.2% (circular block bootstrap, drift set to the consensus). Both ends of the P/E drift are trailing GAAP multiples; the DCF still starts from forward (analyst) earnings. Assumptions: `research/config.py::MarketAssumptions, DCFSettings, GKSettings, MonteCarloSettings; research/candidates/assumptions_us_growth.py::USGrowthAssumptions`.

**Technicals.** No technical signal was kept: the pre-registered test (method.md section 6) found none with OOS IR > 0 and t > 1 for US growth stocks (shortlist.md), so the technical weight is redistributed and no chart signal is used here.

**Risks.** AI competition lowering the value of creative software and a de-rating already in the price (trailing P/E 76 at the end of 2017, 14 now; forward P/E 8.7).

**Verdict (analyst rank 8 of 8; the Phase 4 rubric decides).** Drop under method.md section 8 rule 2: the weakest OOS record of the eight (Sharpe 0.21, IR -0.26, drawdown -69%). Its forward consensus (15%) is the highest because G-K assumes the trailing P/E recovers from 13.4 to 23 (+5.6 points a year) and the DCF starts from forward earnings 1.5x trailing; without the re-rating the consensus is 13%, and the re-rating cannot be tested.

> **How to explain this pick**
>
> 1. ADBE is the maker of Photoshop, Acrobat and the Creative Cloud; a screen using only data to 2017 picked it for a steady software record (Sharpe 1.0 in-sample).
> 2. From 2018 to 2026-10, which the screen never saw, it returned 4.1% a year against 16.3% for the S&P 500 Growth fund, with a worst fall of -69% (fund -30%).
> 3. Our models expect about 15% a year over the next seven years (5-95% range -5% to 37%), so it fell far behind after 2018 and we would not hold it.

Charts: `reports/candidates/charts/ADBE_growth.png`, `reports/candidates/charts/ADBE_rolling.png`. Data notes: full = 2010-01 to the last full month (in-sample + out-of-sample); partial final month dropped; buy-and-hold monthly total returns, no trade modelled, no cost charged; local currency = USD, so the local blocks equal the USD blocks.
