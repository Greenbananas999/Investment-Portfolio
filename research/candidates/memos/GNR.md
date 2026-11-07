# GNR: SPDR S&P Global Natural Resources ETF

*Other sleeve (10%), natural-resource equities. Reproduce: `python -m research.candidates.other_sleeve --ticker GNR --write`; all numbers are in `reports/candidates/GNR.json`. Data to 2026-10-31; in-sample 2010-01 to 2017-12, out-of-sample 2018-01 onward.*

## What it holds and how
1940 Act ETF holding about 90 listed natural-resource producers (energy, metals and mining, agriculture, timber). Expense ratio 0.40%, AUM about $5.4bn (today). **Tax:** Mostly qualified dividends; foreign withholding tax on non-US holdings (partly creditable).

## What drives returns
Equity market beta plus commodity prices through producers' earnings; dividend yield about 2.4%.

## Performance (monthly, USD, net of fees, risk-free BIL)
| | In-sample | Out-of-sample |
|---|---|---|
| Months | 87 | 106 |
| CAGR | 1.9% | 8.6% |
| Volatility | 18.4% | 20.6% |
| Sharpe | 0.19 | 0.38 |
| Max drawdown | -46.8% | -35.5% |
| Deflated Sharpe (33 trials) | 0.06 | 0.17 |
| GLD Sharpe | 0.19 | 0.67 |
| CPI+2% CAGR | 3.7% | 5.7% |

Information ratio vs GLD -0.13 (t -0.39); vs GUIDE_BENCH 0.26; vs CPI+2% 0.24. Share of rolling 36-month windows with IR above zero (vs GLD): 52% full sample, 49% for windows ending out of sample. Charts: `reports/candidates/charts/GNR_growth.png`, `reports/candidates/charts/GNR_rolling.png`.

## Inflation and diversification evidence
- Inflation beta (monthly return on change in YoY US CPI inflation): in-sample 1.36, OOS 1.13. Positive means the fund tended to gain when inflation accelerated; these regressions are noisy, so treat them as weak evidence.
- Partly as advertised: positive (3.4%) but below CPI+2% (7.9%), so it did not keep up with inflation (GLD -11.1%).
- OOS correlation: IVW 0.50, EFG/EEM 0.70, EMB 0.60, GLD 0.31, GUIDE_BENCH 0.77, ACWX 0.80. Beta to the monthly change in the broad dollar index (OOS): -2.48.

| Stress window (total USD return) | GNR | GLD |
|---|---|---|
| gfc_2008 | n/a | 17.8% |
| taper_2013 | -5.1% | -5.7% |
| covid_2020 | -27.0% | -0.9% |
| inflation_2022 | 3.4% | -11.1% |

Strong-dollar months (broad index up 2% or more): average -6.1% vs GLD -2.2% (23 months). Episodes: usd_2014_06_to_2015_03 -15.3% (GLD -5.6%); usd_2021_06_to_2022_09 -5.2% (GLD -13.3%). "n/a" means the fund did not yet exist.

## Forward 7-year view (USD, annual)
| Method | Value | In consensus |
|---|---|---|
| grinold_kroner | 5.6% | yes |
| capm | 8.9% | yes |
| historical | 5.6% | no |
| monte_carlo_median | 7.3% | no |
| monte_carlo_historical_median | 5.6% | no |

Consensus 7.3%; Monte Carlo 5-95 range -4.1% to 19.9%. These are judgement-heavy models; where they disagree by several points the real uncertainty is wider than shown. Formulas, inputs and sources: JSON `expected_return_7y` and `research/candidates/assumptions_other.py`.

## Technicals
Signals T1-T5 were tested on this long list; none was kept (OOS IR not above zero with t above 1), so no technical signal is used for GNR.

## Risks
Behaves largely as cyclical equity (it correlates with ACWX), so the diversification is weaker than bullion; a commodity bust hits it from both sides.

## Non-US share and the 70% rule
Counted at 65% non-US under method.md section 3 (long-list notes, factsheet as of 2026-09-30 where available). Each 1% of the portfolio held here uses 0.35% of the 30% room the rule leaves for US or neutral assets. A 10% position uses 3.5 points of that room.

## Verdict
Section 8 drop rule (OOS Sharpe below GLD and OOS IR below zero): TRIGGERED, runner-up at best. An equity route to commodities; mostly an equity-risk position with a commodity tilt, so it competes with the stock sleeve for risk budget. OOS Sharpe 0.38 (deflated 0.17), OOS max drawdown -35.5%, consensus 7-year return 7.3%.

> **How to explain this pick.** GNR is a natural-resource equities fund (SPDR S&P Global Natural Resources ETF) that counts 65% as non-US under the course rule. Since 2018 it returned 8.6% a year with a Sharpe of 0.38 and a worst drawdown of -36%; in the 2022 inflation and rate shock (Dec 2021 to Oct 2022) it returned 3%. Our models put the next seven years at about 7.3% a year (Monte Carlo range -4% to 20%, judgement-heavy), and its monthly returns correlate 0.80 with world ex-US stocks.
