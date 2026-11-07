# META Meta Platforms, Inc.: candidate memo (US growth stock)

Data to 2026-10-31; benchmark IVW (S&P 500 Growth), risk-free BIL. Every number is from `python -m research.candidates.us_growth --ticker META --write`. In-sample = 2010-01 to 2017-12 (67 months), out-of-sample (OOS) = 2018-01 onward (106 months).

**Thesis.** Meta earns almost all its revenue from advertising on its apps; ad ranking is AI-driven, and it reinvests heavily in AI data centres and in Reality Labs.

**What drives returns.** Digital advertising growth and pricing, cost discipline, and how much of the cash flow AI capital spending absorbs.

**Record, in-sample vs out-of-sample (monthly, USD).**

| | IS stock | IS IVW | OOS stock | OOS IVW |
|---|---|---|---|---|
| CAGR | 37.7% | 14.6% | 15.9% | 16.3% |
| Volatility | 37.5% | 12.1% | 38.4% | 18.5% |
| Sharpe | 1.04 | 1.19 | 0.51 | 0.77 |
| Info ratio (t) | 0.63 (1.5) | - | 0.17 (0.5) | - |
| Alpha (t) | 24.9% (1.4) | - | 2.2% (0.2) | - |
| Max drawdown | -41.9% | -13.0% | -75.4% | -30.5% |
| Deflated Sharpe (N=46) | 0.58 | 0.85 | 0.24 | 0.52 |

Rolling 36-month IR above zero: 85% of windows since 2010, 77% of windows wholly inside OOS. Stress (stock vs IVW): 2008 n/a vs -45%; 2013 taper 49% vs 3%; Covid -17% vs -16%; 2022 -72% vs -27%; strong-USD months (19) -2.9% vs -2.3% a month.

**Fundamentals (SEC EDGAR, point-in-time).** Fiscal year known at 2017-12-31 vs the latest filed (FY 2025-12-31). Screen fundamental score (2017): 0.89.

| Measure | 2017 | Latest |
|---|---|---|
| Revenue | $27.6bn | $201.0bn |
| Revenue CAGR 3y | 52.0% | 19.9% |
| Operating margin | 45.0% | 41.4% |
| Free cash flow | $11.6bn | $46.1bn |
| ROIC | 20.2% | 24.4% |
| Net debt / EBITDA | -0.60 | 0.22 |
| Trailing P/E | 50.6 | 27.4 |
| FCF yield | n/a | n/a |

**Forward 7-year expected return (USD).** CAPM 9.2%, DCF implied 11.3%, Grinold-Kroner 9.8% (of which P/E drift, trailing GAAP P/E from 21.9 to 20.0 over 10 years: -0.9%); consensus 10.1% (10.4% without the P/E drift); Monte Carlo median 10.1%, 5-95% -14.2% to 39.9% (circular block bootstrap, drift set to the consensus). Both ends of the P/E drift are trailing GAAP multiples; the DCF still starts from forward (analyst) earnings. Assumptions: `research/config.py::MarketAssumptions, DCFSettings, GKSettings, MonteCarloSettings; research/candidates/assumptions_us_growth.py::USGrowthAssumptions`.

**Technicals.** No technical signal was kept: the pre-registered test (method.md section 6) found none with OOS IR > 0 and t > 1 for US growth stocks (shortlist.md), so the technical weight is redistributed and no chart signal is used here.

**Risks.** Sentiment on capex can turn fast (the 2022 window cost 72% against 27% for IVW); regulation and privacy rules; dependence on advertising. In-sample history is only 67 months (2012 IPO), flagged short.

**Verdict (analyst rank 5 of 8; the Phase 4 rubric decides).** Runner-up, ranked fifth: OOS IR 0.17 (t 0.5) is positive but not distinguishable from zero, the OOS Sharpe (0.51) is below IVW's 0.77, and the -75% drawdown alone breaks the -25% security budget. Forward consensus 10% is mid-pack.

> **How to explain this pick**
>
> 1. META is the owner of Facebook, Instagram and WhatsApp; a screen using only data to 2017 picked it for the highest fundamental score of the group (52% revenue growth a year, FY2013-FY2016).
> 2. From 2018 to 2026-10, which the screen never saw, it returned 15.9% a year against 16.3% for the S&P 500 Growth fund, with a worst fall of -75% (fund -30%).
> 3. Our models expect about 10% a year over the next seven years (5-95% range -14% to 40%), so it is a runner-up: a strong business, but too volatile for the return it added.

Charts: `reports/candidates/charts/META_growth.png`, `reports/candidates/charts/META_rolling.png`. Data notes: full = 2010-01 to the last full month (in-sample + out-of-sample); partial final month dropped; buy-and-hold monthly total returns, no trade modelled, no cost charged; local currency = USD, so the local blocks equal the USD blocks; in-sample has 67 months (listed 2012-05-18): short in-sample history.
