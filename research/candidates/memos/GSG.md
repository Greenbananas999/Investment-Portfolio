# GSG: iShares S&P GSCI Commodity-Indexed Trust

*Other sleeve (10%), broad commodities. Reproduce: `python -m research.candidates.other_sleeve --ticker GSG --write`; all numbers are in `reports/candidates/GSG.json`. Data to 2026-10-31; in-sample 2010-01 to 2017-12, out-of-sample 2018-01 onward.*

## What it holds and how
Commodity pool holding S&P GSCI futures plus T-bill collateral; K-1 partnership reporting; energy is the largest part of the index. Expense ratio 0.75%, AUM about $1.1bn (today). **Tax:** K-1 reporting; futures gains are taxed under the 60/40 rule; income and roll results are not smooth.

## What drives returns
Spot commodity prices (mostly crude oil) plus roll yield (negative in contango, positive in backwardation) plus T-bill collateral interest.

## Performance (monthly, USD, net of fees, risk-free BIL)
| | In-sample | Out-of-sample |
|---|---|---|
| Months | 96 | 106 |
| CAGR | -8.0% | 9.7% |
| Volatility | 19.0% | 23.2% |
| Sharpe | -0.34 | 0.41 |
| Max drawdown | -66.1% | -53.2% |
| Deflated Sharpe (33 trials) | 0.00 | 0.20 |
| GLD Sharpe | 0.19 | 0.67 |
| CPI+2% CAGR | 3.7% | 5.7% |

Information ratio vs GLD -0.04 (t -0.12); vs GUIDE_BENCH 0.23; vs CPI+2% 0.27. Share of rolling 36-month windows with IR above zero (vs GLD): 24% full sample, 34% for windows ending out of sample. Charts: `reports/candidates/charts/GSG_growth.png`, `reports/candidates/charts/GSG_rolling.png`.

## Inflation and diversification evidence
- Inflation beta (monthly return on change in YoY US CPI inflation): in-sample 4.13, OOS 5.75. Positive means the fund tended to gain when inflation accelerated; these regressions are noisy, so treat them as weak evidence.
- The 2022 shock behaved as advertised: it returned 27.7% against CPI+2% of 7.9% over the same ten months (GLD -11.1%).
- OOS correlation: IVW 0.21, EFG/EEM 0.26, EMB 0.24, GLD -0.04, GUIDE_BENCH 0.30, ACWX 0.35. Beta to the monthly change in the broad dollar index (OOS): -1.17.

| Stress window (total USD return) | GSG | GLD |
|---|---|---|
| gfc_2008 | -51.8% | 17.8% |
| taper_2013 | 7.2% | -5.7% |
| covid_2020 | -35.8% | -0.9% |
| inflation_2022 | 27.7% | -11.1% |

Strong-dollar months (broad index up 2% or more): average -5.4% vs GLD -2.2% (29 months). Episodes: usd_2014_06_to_2015_03 -41.1% (GLD -5.6%); usd_2021_06_to_2022_09 33.1% (GLD -13.3%). "n/a" means the fund did not yet exist.

## Forward 7-year view (USD, annual)
| Method | Value | In consensus |
|---|---|---|
| collateral_roll_spot | 4.4% | yes |
| historical_real_plus_breakeven | -1.8% | yes |
| monte_carlo_median | 2.2% | no |
| monte_carlo_historical_median | -0.6% | no |

Consensus 1.3%; Monte Carlo 5-95 range -16.7% to 20.0%. These are judgement-heavy models; where they disagree by several points the real uncertainty is wider than shown. Formulas, inputs and sources: JSON `expected_return_7y` and `research/candidates/assumptions_other.py`.

## Technicals
Signals T1-T5 were tested on this long list; none was kept (OOS IR not above zero with t above 1), so no technical signal is used for GSG.

## Risks
Concentrated in energy; contango roll drag; lost money in-sample; K-1 complexity; expense ratio is exactly at the 0.75% hard-screen limit.

## Non-US share and the 70% rule
Counted at 0% non-US under method.md section 3 (long-list notes, factsheet as of 2026-09-30 where available). Each 1% of the portfolio held here uses 1.00% of the 30% room the rule leaves for US or neutral assets. A 10% position would use 10 points of that room.

## Verdict
Section 8 drop rule (OOS Sharpe below GLD and OOS IR below zero): TRIGGERED, runner-up at best. Tests the claim that commodities hedge inflation; judge it on the in-sample loss, the roll drag and the OOS record above. OOS Sharpe 0.41 (deflated 0.20), OOS max drawdown -53.2%, consensus 7-year return 1.3%.

> **How to explain this pick.** GSG is a broad commodities fund (iShares S&P GSCI Commodity-Indexed Trust) that counts 0% as non-US under the course rule. Since 2018 it returned 9.7% a year with a Sharpe of 0.41 and a worst drawdown of -53%; in the 2022 inflation and rate shock (Dec 2021 to Oct 2022) it returned 28%. Our models put the next seven years at about 1.3% a year (Monte Carlo range -17% to 20%, judgement-heavy), and its monthly returns correlate 0.35 with world ex-US stocks.
