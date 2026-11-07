# MA Mastercard Incorporated: candidate memo (US growth stock)

Data to 2026-10-31; benchmark IVW (S&P 500 Growth), risk-free BIL. Every number is from `python -m research.candidates.us_growth --ticker MA --write`. In-sample = 2010-01 to 2017-12 (96 months), out-of-sample (OOS) = 2018-01 onward (106 months).

**Thesis.** Mastercard takes a small fee on a large and growing volume of card and digital payments; it carries no credit risk and converts most of its profit to cash (operating margin 58% in FY2025, EDGAR).

**What drives returns.** Payment volume, cross-border travel, value-added services, pricing, and buybacks.

**Record, in-sample vs out-of-sample (monthly, USD).**

| | IS stock | IS IVW | OOS stock | OOS IVW |
|---|---|---|---|---|
| CAGR | 25.5% | 14.6% | 18.4% | 16.3% |
| Volatility | 20.3% | 12.1% | 23.9% | 18.5% |
| Sharpe | 1.23 | 1.19 | 0.72 | 0.77 |
| Info ratio (t) | 0.66 (1.9) | - | 0.14 (0.4) | - |
| Alpha (t) | 10.1% (1.7) | - | 7.5% (1.1) | - |
| Max drawdown | -21.8% | -13.0% | -26.2% | -30.5% |
| Deflated Sharpe (N=46) | 0.86 | 0.85 | 0.46 | 0.52 |

Rolling 36-month IR above zero: 80% of windows since 2010, 52% of windows wholly inside OOS. Stress (stock vs IVW): 2008 -16% vs -45%; 2013 taper 10% vs 3%; Covid -24% vs -16%; 2022 -8% vs -27%; strong-USD months (29) -3.8% vs -3.5% a month.

**Fundamentals (SEC EDGAR, point-in-time).** Fiscal year known at 2017-12-31 vs the latest filed (FY 2025-12-31). Screen fundamental score (2017): 0.45.

| Measure | 2017 | Latest |
|---|---|---|
| Revenue | $10.8bn | $32.8bn |
| Revenue CAGR 3y | 8.9% | 13.8% |
| Operating margin | 53.5% | 57.6% |
| Free cash flow | $4.3bn | $17.2bn |
| ROIC | 100.6% | 94.2% |
| Net debt / EBITDA | -0.25 | 0.42 |
| Trailing P/E | 41.0 | 39.5 |
| FCF yield | n/a | n/a |

**Forward 7-year expected return (USD).** CAPM 7.8%, DCF implied 9.8%, Grinold-Kroner 8.8% (of which P/E drift, trailing GAAP P/E from 34.2 to 23.0 over 10 years: -3.9%); consensus 8.8% (10.1% without the P/E drift); Monte Carlo median 8.8%, 5-95% -2.2% to 20.4% (circular block bootstrap, drift set to the consensus). Both ends of the P/E drift are trailing GAAP multiples; the DCF still starts from forward (analyst) earnings. Assumptions: `research/config.py::MarketAssumptions, DCFSettings, GKSettings, MonteCarloSettings; research/candidates/assumptions_us_growth.py::USGrowthAssumptions`.

**Technicals.** No technical signal was kept: the pre-registered test (method.md section 6) found none with OOS IR > 0 and t > 1 for US growth stocks (shortlist.md), so the technical weight is redistributed and no chart signal is used here.

**Risks.** Regulation of interchange and network fees, real-time payment systems bypassing cards, litigation; a trailing P/E near 40 gives G-K a negative repricing term.

**Verdict (analyst rank 3 of 8; the Phase 4 rubric decides).** Keep as the lower-volatility pick, ranked third: OOS Sharpe 0.72 (just below IVW's 0.77), IR 0.14 (t 0.4, weak), the smallest drawdown of the eight (-26%, just over the budget) and only -8% in the 2022 window against -27% for IVW; but it fell more than IVW in the Covid window (-24% vs -16%), so it is not defensive in every crisis. Forward consensus 9%.

> **How to explain this pick**
>
> 1. MA is the second-largest card payment network; a screen using only data to 2017 picked it for the lowest in-sample drawdown of the eight (-22%).
> 2. From 2018 to 2026-10, which the screen never saw, it returned 18.4% a year against 16.3% for the S&P 500 Growth fund, with a worst fall of -26% (fund -30%).
> 3. Our models expect about 9% a year over the next seven years (5-95% range -2% to 20%), so it is the steady one of our US stocks, chosen for security rather than for extra return.

Charts: `reports/candidates/charts/MA_growth.png`, `reports/candidates/charts/MA_rolling.png`. Data notes: full = 2010-01 to the last full month (in-sample + out-of-sample); partial final month dropped; buy-and-hold monthly total returns, no trade modelled, no cost charged; local currency = USD, so the local blocks equal the USD blocks.
