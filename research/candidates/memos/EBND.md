# EBND: State Street SPDR Bloomberg Emerging Markets Local Bond ETF

Candidate memo, EM bond funds (Phase 3). Benchmark EMLC. Fee 0.30%. Reproduce: `python -m research.candidates.em_bonds --ticker EBND --write`.

## What it holds

Passive local-currency EM government bonds, Bloomberg EM Local Currency Government Diversified; 671 holdings; option-adjusted duration 6.07y (SSGA, 2026-11-05); country weights not retrieved.

Top countries (equal-weight 10-currency basket (fund weights not retrieved)): MX BBB, BR BB, ZA BB, IN BBB, ID BBB, PL A-, HU BBB-, CZ AA-, CL A, CO BB.

## What drives returns

local carry (high local yields), local rates, and above all the currency: the FX leg explains most of the USD variance (fx_vol_share below).

| | In-sample 2010-17 | Out of sample 2018-26 |
|---|---|---|
| CAGR | 1.2% | 0.7% |
| Volatility | 10.5% | 9.8% |
| Sharpe (vs BIL) | 0.16 | -0.14 |
| IR vs EMLC (t) | 0.26 (0.7) | -0.12 (-0.4) |
| IR vs EMB / EMLC | -0.76 / 0.26 | -0.29 / -0.12 |
| Alpha (t) | 0.8% (1.0) | -0.4% (-0.6) |
| Max drawdown | -24.6% | -28.0% |
| Deflated Sharpe (N=20) | 0.07 | 0.01 |
| Months | 82 | 106 |

Currency, OOS a year: local 3.0%, FX -2.3%, USD 0.7%, hedged 0.2% (hedge cost 2.8%, BRL left out of the hedge for lack of a 3-month rate); FX share of USD variance 0.74. With LEMB's GBI-EM weights instead: FX -3.4%, hedged 2.0%.

Country cross-check: an equal-weight basket of 10y constant-maturity bonds in MX, ZA, ID, IN, PL, HU, CZ, CL, CO returned 3.4% a year in USD over 2010-08 to 2026-10 against EMLC's 0.9% (correlation 0.91; OOS 3.1% vs 0.9%). The model has no fees and a longer duration.

## Fundamentals (top countries)

| Country | 10y | 3m | CPI | Real 10y | S&P / Moody's |
|---|---|---|---|---|---|
| MX | 9.2% | 6.8% | 3.8% | 5.4% | BBB / Baa3 |
| BR | n/a | n/a | 4.6% | n/a | BB / Ba1 |
| ZA | 8.9% | 7.1% | 3.2% | 5.7% | BB / Ba2 |
| IN | 7.4% | 5.6% | 5.6% | 1.8% | BBB / Baa3 |
| ID | 7.0% | 5.5% | 3.3% | 3.7% | BBB / Baa2 |
| PL | 6.3% | 3.9% | 2.4% | 3.9% | A- / A2 |
| HU | 5.6% | 5.5% | 3.3% | 2.3% | BBB- / Baa2 |
| CZ | 5.2% | 3.9% | 2.1% | 3.1% | AA- / Aa3 |
| CL | 6.0% | 4.6% | 4.2% | 1.8% | A / A2 |
| CO | 13.2% | 10.2% | 6.3% | 7.0% | BB / Baa3 |

Debt/GDP and current account are not in the repo data and were not checked. Gulf and Asian issuers without OECD series show n/a. Full table: `research/candidates/memos/em_bonds_countries.md`.

## Forward view (7 years, USD)

Yield 6.11% (em_bond_inputs.csv ytm; 30-day SEC yield 2026-11-05) minus fee 0.30% minus expected credit loss 0.30% (rating mix: S&P sovereign ratings of the basket countries (em_bonds_countries.csv, retrieved 2026-11-07), basket-weighted; recovery 49%), minus expected FX depreciation 1.48% (PPP 1.09%, UIP 1.82%); duration 6.1y (em_bond_inputs.csv (2026-11-05)).

| Scenario | Exit yield | Net USD a year |
|---|---|---|
| yields unchanged | 6.11% | 4.4% |
| halfway to fair | 5.27% | 4.7% |
| yields up 200bp | 8.11% | 3.7% |
| yields down 200bp | 4.11% | 5.2% |

Yield-based (halfway to fair) 4.7%; Monte Carlo median 4.8%; **consensus 4.8%**, 5-95% range -1.1% to 10.8%. The credit-loss, rating-mix and FX inputs are judgement. The yield is a 30-day SEC yield or a trailing distribution yield, already net of fund expenses, so the expense ratio is not subtracted again (fix after review, 2026-11-07).

## Stress (USD total return; benchmark in brackets)

gfc_2008: n/a (n/a); taper_2013: -12.4% (-14.2%); covid_2020: -10.7% (-14.4%); inflation_2022: -20.3% (-17.5%); strong-USD months average -4.5% (-4.9%).

## Technicals

No technical signal was kept for EM bonds (all five failed the pre-registered out-of-sample test, em_bond_signals.csv), so none is used here.

## Risks

As EMLC; different index (Bloomberg) and slightly longer duration; same currency exposure.

## Verdict

Rank 8 of 8. Drop under section 8 rule 2: OOS Sharpe -0.14 below EMLC's -0.10 and IR vs EMLC -0.12. Same currency problem as EMLC with no offsetting benefit.

> **How to explain this pick**
>
> EBND is a local-currency government emerging-market bond fund; from 2018 to Oct 2026 it returned 0.7% a year with a worst fall of -28%, versus 1.2% a year in 2010-2017.
> Its bonds earned about 3.0% a year in local currency since 2018, but the currencies changed the result by -2.3% a year, and hedging them would have cost about 2.8% a year.
> Our forward estimate for the next 7 years is about 4.8% a year in dollars (5-95% range -1% to 11%), built from today's yield less fees and expected defaults.
