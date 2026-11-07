# SCHP: Schwab U.S. TIPS ETF

*Other sleeve (10%), US TIPS. Reproduce: `python -m research.candidates.other_sleeve --ticker SCHP --write`; all numbers are in `reports/candidates/SCHP.json`. Data to 2026-10-31; in-sample 2010-01 to 2017-12, out-of-sample 2018-01 onward.*

## What it holds and how
1940 Act ETF tracking the Bloomberg US Treasury Inflation-Linked Bond Index; expense ratio 0.03%. Expense ratio 0.03%, AUM about $17.5bn (today). **Tax:** Interest and inflation accruals are taxable each year (phantom income) though not paid in cash; best held in a tax-deferred account.

## What drives returns
Real yields (duration about 6.5 years, not re-verified) plus realised CPI inflation accrued to principal.

## Performance (monthly, USD, net of fees, risk-free BIL)
| | In-sample | Out-of-sample |
|---|---|---|
| Months | 88 | 106 |
| CAGR | 2.6% | 2.6% |
| Volatility | 4.7% | 5.3% |
| Sharpe | 0.57 | 0.04 |
| Max drawdown | -9.5% | -13.8% |
| Deflated Sharpe (33 trials) | 0.29 | 0.02 |
| GLD Sharpe | 0.19 | 0.67 |
| CPI+2% CAGR | 3.7% | 5.7% |

Information ratio vs GLD -0.71 (t -2.11); vs GUIDE_BENCH -0.40; vs CPI+2% -0.55. Share of rolling 36-month windows with IR above zero (vs GLD): 30% full sample, 2% for windows ending out of sample. Charts: `reports/candidates/charts/SCHP_growth.png`, `reports/candidates/charts/SCHP_rolling.png`.

## Inflation and diversification evidence
- Inflation beta (monthly return on change in YoY US CPI inflation): in-sample -0.68, OOS -0.31. Positive means the fund tended to gain when inflation accelerated; these regressions are noisy, so treat them as weak evidence.
- NOT as advertised: it lost 12.6% in the 2021-12 to 2022-10 inflation and rate shock while CPI+2% rose 7.9% (GLD -11.1%).
- OOS correlation: IVW 0.51, EFG/EEM 0.55, EMB 0.67, GLD 0.38, GUIDE_BENCH 0.62, ACWX 0.53. Beta to the monthly change in the broad dollar index (OOS): -0.45.

| Stress window (total USD return) | SCHP | GLD |
|---|---|---|
| gfc_2008 | n/a | 17.8% |
| taper_2013 | -8.8% | -5.7% |
| covid_2020 | -0.6% | -0.9% |
| inflation_2022 | -12.6% | -11.1% |

Strong-dollar months (broad index up 2% or more): average -1.2% vs GLD -2.2% (23 months). Episodes: usd_2014_06_to_2015_03 -0.2% (GLD -5.6%); usd_2021_06_to_2022_09 -9.6% (GLD -13.3%). "n/a" means the fund did not yet exist.

## Forward 7-year view (USD, annual)
| Method | Value | In consensus |
|---|---|---|
| real_yield_plus_breakeven | 4.8% | yes |
| fund_yield | 4.9% | yes |
| historical | 2.6% | no |
| monte_carlo_median | 4.9% | no |
| monte_carlo_historical_median | 2.7% | no |

Consensus 4.8%; Monte Carlo 5-95 range 1.6% to 8.0%. These are judgement-heavy models; where they disagree by several points the real uncertainty is wider than shown. Formulas, inputs and sources: JSON `expected_return_7y` and `research/candidates/assumptions_other.py`.

## Technicals
Signals T1-T5 were tested on this long list; none was kept (OOS IR not above zero with t above 1), so no technical signal is used for SCHP.

## Risks
Falls when real yields rise; only protects against US inflation; counts fully against the 70% rule; the deflation floor applies only to Treasury principal.

## Non-US share and the 70% rule
Counted at 0% non-US under method.md section 3 (long-list notes, factsheet as of 2026-09-30 where available). Each 1% of the portfolio held here uses 1.00% of the 30% room the rule leaves for US or neutral assets. A 10% position would use 10 points of that room.

## Verdict
Section 8 drop rule (OOS Sharpe below GLD and OOS IR below zero): TRIGGERED, runner-up at best. The 'security' candidate: low volatility and cheapest, but US-only and exposed to real-rate rises. OOS Sharpe 0.04 (deflated 0.02), OOS max drawdown -13.8%, consensus 7-year return 4.8%.

> **How to explain this pick.** SCHP is a US TIPS fund (Schwab U.S. TIPS ETF) that counts 0% as non-US under the course rule. Since 2018 it returned 2.6% a year with a Sharpe of 0.04 and a worst drawdown of -14%; in the 2022 inflation and rate shock (Dec 2021 to Oct 2022) it returned -13%. Our models put the next seven years at about 4.8% a year (Monte Carlo range 2% to 8%, judgement-heavy), and its monthly returns correlate 0.53 with world ex-US stocks.
