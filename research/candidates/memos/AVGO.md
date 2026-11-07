# AVGO Broadcom Inc.: candidate memo (US growth stock)

Data to 2026-10-31; benchmark IVW (S&P 500 Growth), risk-free BIL. Every number is from `python -m research.candidates.us_growth --ticker AVGO --write`. In-sample = 2010-01 to 2017-12 (96 months), out-of-sample (OOS) = 2018-01 onward (106 months).

**Thesis.** Broadcom designs custom AI accelerators and networking chips for the largest cloud companies and sells enterprise infrastructure software (VMware) on multi-year contracts. It is a consolidator: it buys franchises, cuts cost and pays out the cash.

**What drives returns.** Hyperscaler AI capital spending (custom chips, Ethernet switching), software subscription renewals, and the pay-out of free cash flow as dividends.

**Record, in-sample vs out-of-sample (monthly, USD).**

| | IS stock | IS IVW | OOS stock | OOS IVW |
|---|---|---|---|---|
| CAGR | 41.2% | 14.6% | 37.0% | 16.3% |
| Volatility | 27.9% | 12.1% | 36.4% | 18.5% |
| Sharpe | 1.38 | 1.19 | 0.98 | 0.77 |
| Info ratio (t) | 0.97 (2.7) | - | 0.72 (2.2) | - |
| Alpha (t) | 23.8% (2.5) | - | 18.6% (1.9) | - |
| Max drawdown | -23.5% | -13.0% | -31.7% | -30.5% |
| Deflated Sharpe (N=46) | 0.96 | 0.85 | 0.76 | 0.52 |

Rolling 36-month IR above zero: 98% of windows since 2010, 100% of windows wholly inside OOS. Stress (stock vs IVW): 2008 n/a vs -45%; 2013 taper 21% vs 3%; Covid -21% vs -16%; 2022 -28% vs -27%; strong-USD months (24) 0.4% vs -2.6% a month.

**Fundamentals (SEC EDGAR, point-in-time).** Fiscal year known at 2017-12-31 vs the latest filed (FY 2025-11-02). Screen fundamental score (2017): 0.59.

| Measure | 2017 | Latest |
|---|---|---|
| Revenue | n/a | $63.9bn |
| Revenue CAGR 3y | n/a | 24.4% |
| Operating margin | n/a | 39.9% |
| Free cash flow | n/a | $26.9bn |
| ROIC | n/a | 19.3% |
| Net debt / EBITDA | n/a | 2.00 |
| Trailing P/E | n/a | 61.6 |
| FCF yield | n/a | 1.9% |

2017 column: no filing under this CIK was known at 2017-12-31 (see flags); the Phase 2 screen used current statements for it and flagged it.

**Forward 7-year expected return (USD).** CAPM 9.9%, DCF implied 16.1%, Grinold-Kroner 8.2% (of which P/E drift, trailing GAAP P/E from 37.5 to 23.0 over 10 years: -4.8%); consensus 11.4% (13.0% without the P/E drift); Monte Carlo median 11.5%, 5-95% -5.0% to 30.8% (circular block bootstrap, drift set to the consensus). Both ends of the P/E drift are trailing GAAP multiples; the DCF still starts from forward (analyst) earnings. Assumptions: `research/config.py::MarketAssumptions, DCFSettings, GKSettings, MonteCarloSettings; research/candidates/assumptions_us_growth.py::USGrowthAssumptions`.

**Technicals.** No technical signal was kept: the pre-registered test (method.md section 6) found none with OOS IR > 0 and t > 1 for US growth stocks (shortlist.md), so the technical weight is redistributed and no chart signal is used here.

**Risks.** Concentration in a few AI customers, a capex downturn, acquisition debt, and a trailing P/E near 60 that already prices the AI ramp. The 2017 fundamentals are not point-in-time (Singapore-domiciled until 2018; the current CIK starts then): its 2017 fundamental score was built from current statements, so the 2017 screen was not data-to-2017 only for this name.

**Verdict (analyst rank 2 of 8; the Phase 4 rubric decides).** Keep, ranked second: OOS Sharpe 0.98 and IR 0.72 (t 2.2), every 36-month OOS window with positive IR. Its -32% worst drawdown is close to the index's -30% but still breaks the -25% security budget, so it too needs a capped weight. Forward consensus 11% (13% without the assumed de-rating from a trailing P/E of 37.5 to 23); its 2017 screen data could not be checked point-in-time.

> **How to explain this pick**
>
> 1. AVGO is a semiconductor and infrastructure-software company built by acquisition; a screen using only data to 2017 picked it for the second-best in-sample composite (41% a year, Sharpe 1.4 in 2010-2017; its 2017 fundamentals came from current statements, not data to 2017).
> 2. From 2018 to 2026-10, which the screen never saw, it returned 37.0% a year against 16.3% for the S&P 500 Growth fund, with a worst fall of -32% (fund -30%).
> 3. Our models expect about 11% a year over the next seven years (5-95% range -5% to 31%), so it is one of our two core US picks, with the warning that most of its return came from the AI build-out.

Charts: `reports/candidates/charts/AVGO_growth.png`, `reports/candidates/charts/AVGO_rolling.png`. Data notes: full = 2010-01 to the last full month (in-sample + out-of-sample); partial final month dropped; buy-and-hold monthly total returns, no trade modelled, no cost charged; local currency = USD, so the local blocks equal the USD blocks; 2017 screen fundamentals not point-in-time (from current statements), flagged by Phase 2.
