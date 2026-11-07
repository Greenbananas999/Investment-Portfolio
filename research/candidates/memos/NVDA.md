# NVDA NVIDIA Corporation: candidate memo (US growth stock)

Data to 2026-10-31; benchmark IVW (S&P 500 Growth), risk-free BIL. Every number is from `python -m research.candidates.us_growth --ticker NVDA --write`. In-sample = 2010-01 to 2017-12 (96 months), out-of-sample (OOS) = 2018-01 onward (106 months).

**Thesis.** Nvidia sells the GPUs, networking and software (CUDA) on which most AI models are trained and run; revenue went from $6.9bn in FY2017 to $216bn in FY2026 (EDGAR).

**What drives returns.** AI data-centre spending by cloud companies and governments, product cycles, gross margin, and export rules on China.

**Record, in-sample vs out-of-sample (monthly, USD).**

| | IS stock | IS IVW | OOS stock | OOS IVW |
|---|---|---|---|---|
| CAGR | 35.2% | 14.6% | 53.6% | 16.3% |
| Volatility | 41.7% | 12.1% | 46.7% | 18.5% |
| Sharpe | 0.92 | 1.19 | 1.11 | 0.77 |
| Info ratio (t) | 0.63 (1.8) | - | 1.04 (3.1) | - |
| Alpha (t) | 16.3% (1.2) | - | 26.1% (2.3) | - |
| Max drawdown | -49.9% | -13.0% | -62.8% | -30.5% |
| Deflated Sharpe (N=46) | 0.65 | 0.85 | 0.84 | 0.52 |

Rolling 36-month IR above zero: 85% of windows since 2010, 100% of windows wholly inside OOS. Stress (stock vs IVW): 2008 -77% vs -45%; 2013 taper 8% vs 3%; Covid 12% vs -16%; 2022 -54% vs -27%; strong-USD months (29) -1.6% vs -3.5% a month.

**Fundamentals (SEC EDGAR, point-in-time).** Fiscal year known at 2017-12-31 vs the latest filed (FY 2026-01-25). Screen fundamental score (2017): 0.58.

| Measure | 2017 | Latest |
|---|---|---|
| Revenue | $6.9bn | $215.9bn |
| Revenue CAGR 3y | 18.7% | 100.0% |
| Operating margin | 28.0% | 60.4% |
| Free cash flow | $1.7bn | $102.7bn |
| ROIC | 28.3% | 71.3% |
| Net debt / EBITDA | 0.10 | -0.02 |
| Trailing P/E | 75.3 | 43.1 |
| FCF yield | 1.5% | 2.0% |

**Forward 7-year expected return (USD).** CAPM 12.0%, DCF implied 15.7%, Grinold-Kroner 11.2% (of which P/E drift, trailing GAAP P/E from 26.7 to 22.0 over 10 years: -1.9%); consensus 13.0% (13.6% without the P/E drift); Monte Carlo median 13.5%, 5-95% -17.4% to 54.0% (circular block bootstrap, drift set to the consensus). Both ends of the P/E drift are trailing GAAP multiples; the DCF still starts from forward (analyst) earnings. Assumptions: `research/config.py::MarketAssumptions, DCFSettings, GKSettings, MonteCarloSettings; research/candidates/assumptions_us_growth.py::USGrowthAssumptions`.

**Technicals.** No technical signal was kept: the pre-registered test (method.md section 6) found none with OOS IR > 0 and t > 1 for US growth stocks (shortlist.md), so the technical weight is redistributed and no chart signal is used here.

**Risks.** A pause in AI capex, custom chips (including Broadcom's) taking share, export controls, and the highest volatility of the eight (47% a year OOS; -77% in 2008, -54% in the 2022 window, -63% OOS max drawdown).

**Verdict (analyst rank 1 of 8; the Phase 4 rubric decides).** Keep, ranked first on the judging metrics: OOS Sharpe 1.11, IR 1.04 (t 3.1), deflated Sharpe 0.84 (below the 0.95 bar), and a forward consensus of 13%. The evidence is one regime (the 2023-2026 AI build-out) and the -63% drawdown means it only fits as a small weight inside the security budget.

> **How to explain this pick**
>
> 1. NVDA is the leading maker of AI and graphics processors; a screen using only data to 2017 picked it for it was the momentum-leaning candidate with a 35% in-sample return.
> 2. From 2018 to 2026-10, which the screen never saw, it returned 53.6% a year against 16.3% for the S&P 500 Growth fund, with a worst fall of -63% (fund -30%).
> 3. Our models expect about 13% a year over the next seven years (5-95% range -17% to 54%), so it is one of our two core US picks, held small because it has fallen more than 60% twice.

Charts: `reports/candidates/charts/NVDA_growth.png`, `reports/candidates/charts/NVDA_rolling.png`. Data notes: full = 2010-01 to the last full month (in-sample + out-of-sample); partial final month dropped; buy-and-hold monthly total returns, no trade modelled, no cost charged; local currency = USD, so the local blocks equal the USD blocks.
