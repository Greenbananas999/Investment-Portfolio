# IGF: iShares Global Infrastructure ETF

*Other sleeve (10%), infrastructure. Reproduce: `python -m research.candidates.other_sleeve --ticker IGF --write`; all numbers are in `reports/candidates/IGF.json`. Data to 2026-10-31; in-sample 2010-01 to 2017-12, out-of-sample 2018-01 onward.*

## What it holds and how
1940 Act ETF tracking the S&P Global Infrastructure Index (listed utilities, pipelines, airports, toll roads). Expense ratio 0.37%, AUM about $10.9bn (today). **Tax:** Mostly qualified dividends; foreign withholding tax on non-US holdings.

## What drives returns
Regulated and contracted cash flows (often inflation-linked tariffs), interest rates (bond-like), and equity sentiment; yield about 2.9%.

## Performance (monthly, USD, net of fees, risk-free BIL)
| | In-sample | Out-of-sample |
|---|---|---|
| Months | 96 | 106 |
| CAGR | 7.3% | 7.4% |
| Volatility | 12.7% | 16.2% |
| Sharpe | 0.61 | 0.37 |
| Max drawdown | -16.4% | -29.6% |
| Deflated Sharpe (33 trials) | 0.35 | 0.17 |
| GLD Sharpe | 0.19 | 0.67 |
| CPI+2% CAGR | 3.7% | 5.7% |

Information ratio vs GLD -0.25 (t -0.74); vs GUIDE_BENCH 0.19; vs CPI+2% 0.15. Share of rolling 36-month windows with IR above zero (vs GLD): 48% full sample, 33% for windows ending out of sample. Charts: `reports/candidates/charts/IGF_growth.png`, `reports/candidates/charts/IGF_rolling.png`.

## Inflation and diversification evidence
- Inflation beta (monthly return on change in YoY US CPI inflation): in-sample 0.63, OOS 0.42. Positive means the fund tended to gain when inflation accelerated; these regressions are noisy, so treat them as weak evidence.
- NOT as advertised: it lost 6.1% in the 2021-12 to 2022-10 inflation and rate shock while CPI+2% rose 7.9% (GLD -11.1%).
- OOS correlation: IVW 0.55, EFG/EEM 0.74, EMB 0.78, GLD 0.29, GUIDE_BENCH 0.83, ACWX 0.82. Beta to the monthly change in the broad dollar index (OOS): -1.99.

| Stress window (total USD return) | IGF | GLD |
|---|---|---|
| gfc_2008 | n/a | 17.8% |
| taper_2013 | -6.7% | -5.7% |
| covid_2020 | -29.6% | -0.9% |
| inflation_2022 | -6.1% | -11.1% |

Strong-dollar months (broad index up 2% or more): average -6.0% vs GLD -2.2% (29 months). Episodes: usd_2014_06_to_2015_03 -0.7% (GLD -5.6%); usd_2021_06_to_2022_09 -7.5% (GLD -13.3%). "n/a" means the fund did not yet exist.

## Forward 7-year view (USD, annual)
| Method | Value | In consensus |
|---|---|---|
| grinold_kroner | 6.7% | yes |
| capm | 7.8% | yes |
| historical | 4.7% | no |
| monte_carlo_median | 7.8% | no |
| monte_carlo_historical_median | 5.2% | no |

Consensus 7.2%; Monte Carlo 5-95 range -4.7% to 18.4%. These are judgement-heavy models; where they disagree by several points the real uncertainty is wider than shown. Formulas, inputs and sources: JSON `expected_return_7y` and `research/candidates/assumptions_other.py`.

## Technicals
Signals T1-T5 were tested on this long list; none was kept (OOS IR not above zero with t above 1), so no technical signal is used for IGF.

## Risks
Rate-sensitive like utilities; correlated with equities in a crash; about a third US holdings.

## Non-US share and the 70% rule
Counted at 64% non-US under method.md section 3 (long-list notes, factsheet as of 2026-09-30 where available). Each 1% of the portfolio held here uses 0.36% of the 30% room the rule leaves for US or neutral assets. A 10% position uses 3.6 points of that room.

## Verdict
Section 8 drop rule (OOS Sharpe below GLD and OOS IR below zero): TRIGGERED, runner-up at best. Defensive real-asset equity with partly inflation-linked tariffs and the smallest in-sample drawdown of the real-asset funds. OOS Sharpe 0.37 (deflated 0.17), OOS max drawdown -29.6%, consensus 7-year return 7.2%.

> **How to explain this pick.** IGF is a infrastructure fund (iShares Global Infrastructure ETF) that counts 64% as non-US under the course rule. Since 2018 it returned 7.4% a year with a Sharpe of 0.37 and a worst drawdown of -30%; in the 2022 inflation and rate shock (Dec 2021 to Oct 2022) it returned -6%. Our models put the next seven years at about 7.2% a year (Monte Carlo range -5% to 18%, judgement-heavy), and its monthly returns correlate 0.82 with world ex-US stocks.
