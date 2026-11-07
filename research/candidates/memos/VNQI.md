# VNQI: Vanguard Global ex-U.S. Real Estate ETF

*Other sleeve (10%), ex-US REITs. Reproduce: `python -m research.candidates.other_sleeve --ticker VNQI --write`; all numbers are in `reports/candidates/VNQI.json`. Data to 2026-10-31; in-sample 2010-01 to 2017-12, out-of-sample 2018-01 onward.*

## What it holds and how
1940 Act ETF tracking the S&P Global ex-US Property Index (developed and emerging property companies); Vanguard share class. Expense ratio 0.12%, AUM about $3.5bn (today). **Tax:** Mostly non-qualified dividends (ordinary income), foreign withholding tax.

## What drives returns
Property-company equity returns: rents, interest rates (cap rates), local currencies (unhedged) and equity sentiment; yield about 5%.

## Performance (monthly, USD, net of fees, risk-free BIL)
| | In-sample | Out-of-sample |
|---|---|---|
| Months | 85 | 106 |
| CAGR | 7.8% | -0.2% |
| Volatility | 15.1% | 17.2% |
| Sharpe | 0.57 | -0.07 |
| Max drawdown | -22.4% | -32.7% |
| Deflated Sharpe (33 trials) | 0.28 | 0.01 |
| GLD Sharpe | 0.19 | 0.67 |
| CPI+2% CAGR | 3.7% | 5.7% |

Information ratio vs GLD -0.63 (t -1.88); vs GUIDE_BENCH -0.67; vs CPI+2% -0.23. Share of rolling 36-month windows with IR above zero (vs GLD): 48% full sample, 24% for windows ending out of sample. Charts: `reports/candidates/charts/VNQI_growth.png`, `reports/candidates/charts/VNQI_rolling.png`.

## Inflation and diversification evidence
- Inflation beta (monthly return on change in YoY US CPI inflation): in-sample -1.76, OOS 0.68. Positive means the fund tended to gain when inflation accelerated; these regressions are noisy, so treat them as weak evidence.
- NOT as advertised: it lost 30.7% in the 2021-12 to 2022-10 inflation and rate shock while CPI+2% rose 7.9% (GLD -11.1%).
- OOS correlation: IVW 0.58, EFG/EEM 0.84, EMB 0.80, GLD 0.36, GUIDE_BENCH 0.90, ACWX 0.89. Beta to the monthly change in the broad dollar index (OOS): -2.49.

| Stress window (total USD return) | VNQI | GLD |
|---|---|---|
| gfc_2008 | n/a | 17.8% |
| taper_2013 | -14.2% | -5.7% |
| covid_2020 | -25.4% | -0.9% |
| inflation_2022 | -30.7% | -11.1% |

Strong-dollar months (broad index up 2% or more): average -6.1% vs GLD -2.2% (22 months). Episodes: usd_2014_06_to_2015_03 1.2% (GLD -5.6%); usd_2021_06_to_2022_09 -30.9% (GLD -13.3%). "n/a" means the fund did not yet exist.

## Forward 7-year view (USD, annual)
| Method | Value | In consensus |
|---|---|---|
| grinold_kroner | 7.8% | yes |
| capm | 8.2% | yes |
| historical | 3.3% | no |
| monte_carlo_median | 8.2% | no |
| monte_carlo_historical_median | 3.5% | no |

Consensus 8.0%; Monte Carlo 5-95 range -1.3% to 17.7%. These are judgement-heavy models; where they disagree by several points the real uncertainty is wider than shown. Formulas, inputs and sources: JSON `expected_return_7y` and `research/candidates/assumptions_other.py`.

## Technicals
Signals T1-T5 were tested on this long list; none was kept (OOS IR not above zero with t above 1), so no technical signal is used for VNQI.

## Risks
Equity-like drawdowns in rate shocks (2022); unhedged foreign currency; weak short-run inflation hedge; country mix not verified from holdings.

## Non-US share and the 70% rule
Counted at 100% non-US under method.md section 3 (long-list notes, factsheet as of 2026-09-30 where available). Each 1% of the portfolio held here uses 0.00% of the 30% room the rule leaves for US or neutral assets. It uses none of that room.

## Verdict
Section 8 drop rule (OOS Sharpe below GLD and OOS IR below zero): TRIGGERED, runner-up at best. The only candidate that counts fully non-US and diversifies by asset class; it helps the 70% rule rather than consuming US room. OOS Sharpe -0.07 (deflated 0.01), OOS max drawdown -32.7%, consensus 7-year return 8.0%.

> **How to explain this pick.** VNQI is a ex-US REITs fund (Vanguard Global ex-U.S. Real Estate ETF) that counts 100% as non-US under the course rule. Since 2018 it returned -0.2% a year with a Sharpe of -0.07 and a worst drawdown of -33%; in the 2022 inflation and rate shock (Dec 2021 to Oct 2022) it returned -31%. Our models put the next seven years at about 8.0% a year (Monte Carlo range -1% to 18%, judgement-heavy), and its monthly returns correlate 0.89 with world ex-US stocks.
