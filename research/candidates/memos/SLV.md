# SLV: iShares Silver Trust

*Other sleeve (10%), silver. Reproduce: `python -m research.candidates.other_sleeve --ticker SLV --write`; all numbers are in `reports/candidates/SLV.json`. Data to 2026-10-31; in-sample 2010-01 to 2017-12, out-of-sample 2018-01 onward.*

## What it holds and how
Grantor trust holding allocated London silver bars. Expense ratio 0.50%, AUM about $25.2bn (today). **Tax:** Collectibles tax (up to 28%); no income.

## What drives returns
Silver price: monetary demand like gold plus industrial demand (solar, electronics), so it trades as a high-beta gold with a cyclical component.

## Performance (monthly, USD, net of fees, risk-free BIL)
| | In-sample | Out-of-sample |
|---|---|---|
| Months | 96 | 106 |
| CAGR | -0.4% | 12.3% |
| Volatility | 32.4% | 32.1% |
| Sharpe | 0.15 | 0.44 |
| Max drawdown | -71.9% | -47.5% |
| Deflated Sharpe (33 trials) | 0.04 | 0.20 |
| GLD Sharpe | 0.19 | 0.67 |
| CPI+2% CAGR | 3.7% | 5.7% |

Information ratio vs GLD 0.15 (t 0.45); vs GUIDE_BENCH 0.36; vs CPI+2% 0.41. Share of rolling 36-month windows with IR above zero (vs GLD): 47% full sample, 55% for windows ending out of sample. Charts: `reports/candidates/charts/SLV_growth.png`, `reports/candidates/charts/SLV_rolling.png`.

## Inflation and diversification evidence
- Inflation beta (monthly return on change in YoY US CPI inflation): in-sample 1.04, OOS 0.00. Positive means the fund tended to gain when inflation accelerated; these regressions are noisy, so treat them as weak evidence.
- NOT as advertised: it lost 18.1% in the 2021-12 to 2022-10 inflation and rate shock while CPI+2% rose 7.9% (GLD -11.1%).
- OOS correlation: IVW 0.29, EFG/EEM 0.47, EMB 0.44, GLD 0.77, GUIDE_BENCH 0.54, ACWX 0.45. Beta to the monthly change in the broad dollar index (OOS): -3.09.

| Stress window (total USD return) | SLV | GLD |
|---|---|---|
| gfc_2008 | -10.3% | 17.8% |
| taper_2013 | -3.7% | -5.7% |
| covid_2020 | -22.4% | -0.9% |
| inflation_2022 | -18.1% | -11.1% |

Strong-dollar months (broad index up 2% or more): average -5.2% vs GLD -2.2% (29 months). Episodes: usd_2014_06_to_2015_03 -11.9% (GLD -5.6%); usd_2021_06_to_2022_09 -32.4% (GLD -13.3%). "n/a" means the fund did not yet exist.

## Forward 7-year view (USD, annual)
| Method | Value | In consensus |
|---|---|---|
| real_yield_model | 0.6% | yes |
| historical_real_plus_breakeven | 5.5% | yes |
| monte_carlo_median | 2.9% | no |
| monte_carlo_historical_median | 5.7% | no |

Consensus 3.1%; Monte Carlo 5-95 range -15.5% to 26.6%. These are judgement-heavy models; where they disagree by several points the real uncertainty is wider than shown. Formulas, inputs and sources: JSON `expected_return_7y` and `research/candidates/assumptions_other.py`.

## Technicals
Signals T1-T5 were tested on this long list; none was kept (OOS IR not above zero with t above 1), so no technical signal is used for SLV.

## Risks
Roughly twice gold's volatility and a -70% in-sample drawdown; industrial slowdowns hit it while gold may rise; thin 2010-17 return.

## Non-US share and the 70% rule
Counted at 0% non-US under method.md section 3 (long-list notes, factsheet as of 2026-09-30 where available). Each 1% of the portfolio held here uses 1.00% of the 30% room the rule leaves for US or neutral assets. A 10% position would use 10 points of that room.

## Verdict
Section 8 drop rule (OOS Sharpe below GLD and OOS IR below zero): not triggered. A higher-risk cousin of gold; worth holding only if its OOS record beats gold per unit of risk, which the table lets you test. OOS Sharpe 0.44 (deflated 0.20), OOS max drawdown -47.5%, consensus 7-year return 3.1%.

> **How to explain this pick.** SLV is a silver fund (iShares Silver Trust) that counts 0% as non-US under the course rule. Since 2018 it returned 12.3% a year with a Sharpe of 0.44 and a worst drawdown of -48%; in the 2022 inflation and rate shock (Dec 2021 to Oct 2022) it returned -18%. Our models put the next seven years at about 3.1% a year (Monte Carlo range -16% to 27%, judgement-heavy), and its monthly returns correlate 0.45 with world ex-US stocks.
