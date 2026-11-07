# WIP: SPDR FTSE International Government Inflation-Protected Bond ETF

*Other sleeve (10%), international inflation-linked bonds. Reproduce: `python -m research.candidates.other_sleeve --ticker WIP --write`; all numbers are in `reports/candidates/WIP.json`. Data to 2026-10-31; in-sample 2010-01 to 2017-12, out-of-sample 2018-01 onward.*

## What it holds and how
1940 Act ETF tracking the FTSE International Inflation-Linked Securities Select Index; non-US government linkers (UK 18%, Brazil 8% per the 2026-09-30 factsheet); understood to be currency-unhedged (not re-verified). Expense ratio 0.50%, AUM about $0.5bn (today). **Tax:** Interest and inflation accruals taxable annually; currency gains are ordinary income.

## What drives returns
Local real yields, local inflation accruals and, above all, currencies against the dollar (unhedged).

## Performance (monthly, USD, net of fees, risk-free BIL)
| | In-sample | Out-of-sample |
|---|---|---|
| Months | 96 | 106 |
| CAGR | 2.7% | 0.4% |
| Volatility | 9.4% | 10.6% |
| Sharpe | 0.32 | -0.15 |
| Max drawdown | -17.5% | -23.4% |
| Deflated Sharpe (33 trials) | 0.12 | 0.01 |
| GLD Sharpe | 0.19 | 0.67 |
| CPI+2% CAGR | 3.7% | 5.7% |

Information ratio vs GLD -0.88 (t -2.61); vs GUIDE_BENCH -0.96; vs CPI+2% -0.42. Share of rolling 36-month windows with IR above zero (vs GLD): 26% full sample, 10% for windows ending out of sample. Charts: `reports/candidates/charts/WIP_growth.png`, `reports/candidates/charts/WIP_rolling.png`.

## Inflation and diversification evidence
- Inflation beta (monthly return on change in YoY US CPI inflation): in-sample 0.68, OOS -0.21. Positive means the fund tended to gain when inflation accelerated; these regressions are noisy, so treat them as weak evidence.
- NOT as advertised: it lost 19.9% in the 2021-12 to 2022-10 inflation and rate shock while CPI+2% rose 7.9% (GLD -11.1%).
- OOS correlation: IVW 0.57, EFG/EEM 0.81, EMB 0.84, GLD 0.51, GUIDE_BENCH 0.87, ACWX 0.81. Beta to the monthly change in the broad dollar index (OOS): -1.69.

| Stress window (total USD return) | WIP | GLD |
|---|---|---|
| gfc_2008 | n/a | 17.8% |
| taper_2013 | -9.4% | -5.7% |
| covid_2020 | -11.5% | -0.9% |
| inflation_2022 | -19.9% | -11.1% |

Strong-dollar months (broad index up 2% or more): average -4.8% vs GLD -2.2% (29 months). Episodes: usd_2014_06_to_2015_03 -9.8% (GLD -5.6%); usd_2021_06_to_2022_09 -22.7% (GLD -13.3%). "n/a" means the fund did not yet exist.

## Forward 7-year view (USD, annual)
| Method | Value | In consensus |
|---|---|---|
| country_real_yield_plus_inflation_ppp | 4.4% | yes |
| fund_yield | 6.3% | yes |
| historical | 1.0% | no |
| monte_carlo_median | 5.6% | no |
| monte_carlo_historical_median | 1.2% | no |

Consensus 5.4%; Monte Carlo 5-95 range -1.8% to 12.4%. These are judgement-heavy models; where they disagree by several points the real uncertainty is wider than shown. Formulas, inputs and sources: JSON `expected_return_7y` and `research/candidates/assumptions_other.py`.

## Technicals
Signals T1-T5 were tested on this long list; none was kept (OOS IR not above zero with t above 1), so no technical signal is used for WIP.

## Risks
Currency risk is large relative to the bond return; UK linkers fell hard in 2022; Brazil's high carry is volatile; only 26% of the country mix is known.

## Non-US share and the 70% rule
Counted at 100% non-US under method.md section 3 (long-list notes, factsheet as of 2026-09-30 where available). Each 1% of the portfolio held here uses 0.00% of the 30% room the rule leaves for US or neutral assets. It uses none of that room.

## Verdict
Section 8 drop rule (OOS Sharpe below GLD and OOS IR below zero): TRIGGERED, runner-up at best. Inflation protection that counts fully non-US, but with unhedged currency risk. OOS Sharpe -0.15 (deflated 0.01), OOS max drawdown -23.4%, consensus 7-year return 5.4%.

> **How to explain this pick.** WIP is a international inflation-linked bonds fund (SPDR FTSE International Government Inflation-Protected Bond ETF) that counts 100% as non-US under the course rule. Since 2018 it returned 0.4% a year with a Sharpe of -0.15 and a worst drawdown of -23%; in the 2022 inflation and rate shock (Dec 2021 to Oct 2022) it returned -20%. Our models put the next seven years at about 5.4% a year (Monte Carlo range -2% to 12%, judgement-heavy), and its monthly returns correlate 0.81 with world ex-US stocks.
