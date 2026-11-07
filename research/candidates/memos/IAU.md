# IAU: iShares Gold Trust

*Other sleeve (10%), gold. Reproduce: `python -m research.candidates.other_sleeve --ticker IAU --write`; all numbers are in `reports/candidates/IAU.json`. Data to 2026-10-31; in-sample 2010-01 to 2017-12, out-of-sample 2018-01 onward.*

## What it holds and how
Grantor trust holding allocated London bullion; no derivatives, no K-1. Expense ratio 0.25%, AUM about $58.1bn (today). **Tax:** Gains taxed as collectibles (up to 28% long-term federal rate); no income distributions.

## What drives returns
The dollar price of gold: falling real yields and a weaker dollar help, central-bank buying and crisis demand help; it pays no income, so it is pure price.

## Performance (monthly, USD, net of fees, risk-free BIL)
| | In-sample | Out-of-sample |
|---|---|---|
| Months | 96 | 106 |
| CAGR | 1.9% | 12.9% |
| Volatility | 17.2% | 16.0% |
| Sharpe | 0.19 | 0.68 |
| Max drawdown | -42.6% | -26.4% |
| Deflated Sharpe (33 trials) | 0.06 | 0.46 |
| GLD Sharpe | 0.19 | 0.67 |
| CPI+2% CAGR | 3.7% | 5.7% |

Information ratio vs GLD is undefined (IAU is the same bullion); vs GUIDE_BENCH 0.44 (t 1.32), vs CPI+2% 0.53 (t 1.56). Share of rolling 36-month windows with IR above zero (vs GUIDE_BENCH): 56% full sample, 75% for windows ending out of sample. Charts: `reports/candidates/charts/IAU_growth.png`, `reports/candidates/charts/IAU_rolling.png`.

## Inflation and diversification evidence
- Inflation beta (monthly return on change in YoY US CPI inflation): in-sample -1.09, OOS -1.10. Positive means the fund tended to gain when inflation accelerated; these regressions are noisy, so treat them as weak evidence.
- NOT as advertised: it lost 11.0% in the 2021-12 to 2022-10 inflation and rate shock while CPI+2% rose 7.9% (GLD -11.1%).
- OOS correlation: IVW 0.13, EFG/EEM 0.38, EMB 0.35, GLD 1.00, GUIDE_BENCH 0.48, ACWX 0.35. Beta to the monthly change in the broad dollar index (OOS): -1.41.

| Stress window (total USD return) | IAU | GLD |
|---|---|---|
| gfc_2008 | 17.9% | 17.8% |
| taper_2013 | -5.7% | -5.7% |
| covid_2020 | -0.7% | -0.9% |
| inflation_2022 | -11.0% | -11.1% |

Strong-dollar months (broad index up 2% or more): average -2.2% vs GLD -2.2% (29 months). Episodes: usd_2014_06_to_2015_03 -5.6% (GLD -5.6%); usd_2021_06_to_2022_09 -13.0% (GLD -13.3%). "n/a" means the fund did not yet exist.

## Forward 7-year view (USD, annual)
| Method | Value | In consensus |
|---|---|---|
| real_yield_model | 0.6% | yes |
| historical_real_plus_breakeven | 10.0% | yes |
| monte_carlo_median | 5.3% | no |
| monte_carlo_historical_median | 10.4% | no |

Consensus 5.3%; Monte Carlo 5-95 range -5.0% to 16.8%. These are judgement-heavy models; where they disagree by several points the real uncertainty is wider than shown. Formulas, inputs and sources: JSON `expected_return_7y` and `research/candidates/assumptions_other.py`.

## Technicals
Signals T1-T5 were tested on this long list; none was kept (OOS IR not above zero with t above 1), so no technical signal is used for IAU.

## Risks
Long flat or falling spells (in-sample drawdown over 40% from the 2011 peak); no yield, so real-rate rises hurt; a recent run-up can reverse; 28% collectibles tax; IAU and GLD are the same asset (0.25% vs 0.40% fee).

## Non-US share and the 70% rule
Counted at 0% non-US under method.md section 3 (long-list notes, factsheet as of 2026-09-30 where available). Each 1% of the portfolio held here uses 1.00% of the 30% room the rule leaves for US or neutral assets. A 10% position would use 10 points of that room.

## Verdict
Section 8 drop rule (OOS Sharpe below GLD and OOS IR below zero): not triggered. The sleeve's reference holding: the simplest inflation and crisis diversifier at the lowest gold fee. The case rests on diversification and the dollar, not on a high expected return. OOS Sharpe 0.68 (deflated 0.46), OOS max drawdown -26.4%, consensus 7-year return 5.3%.

> **How to explain this pick.** IAU is a gold fund (iShares Gold Trust) that counts 0% as non-US under the course rule. Since 2018 it returned 12.9% a year with a Sharpe of 0.68 and a worst drawdown of -26%; in the 2022 inflation and rate shock (Dec 2021 to Oct 2022) it returned -11%. Our models put the next seven years at about 5.3% a year (Monte Carlo range -5% to 17%, judgement-heavy), and its monthly returns correlate 0.35 with world ex-US stocks.
