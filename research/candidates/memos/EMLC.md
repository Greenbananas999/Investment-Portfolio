# EMLC: VanEck J.P. Morgan EM Local Currency Bond ETF

Candidate memo, EM bond funds (Phase 3). Benchmark GUIDE_BENCH (method benchmark EMLC; EMLC is itself a method benchmark). Fee 0.30%. Reproduce: `python -m research.candidates.em_bonds --ticker EMLC --write`.

## What it holds

Passive local-currency EM government bonds, JPM GBI-EM Global Core (from memory, unverified); effective duration 5.13y, yield to worst 6.42% (VanEck UCITS fact sheet 2026-08-31); country weights not retrieved.

Top countries (equal-weight 10-currency basket (fund weights not retrieved)): MX BBB, BR BB, ZA BB, IN BBB, ID BBB, PL A-, HU BBB-, CZ AA-, CL A, CO BB.

## What drives returns

local carry (high local yields), local rates, and above all the currency: the FX leg explains most of the USD variance (fx_vol_share below).

| | In-sample 2010-17 | Out of sample 2018-26 |
|---|---|---|
| CAGR | 1.0% | 0.9% |
| Volatility | 11.6% | 10.7% |
| Sharpe (vs BIL) | 0.14 | -0.10 |
| IR vs GUIDE_BENCH (t) | -0.82 (-2.2) | -0.83 (-2.5) |
| IR vs EMB / EMLC | -0.61 / n/a | -0.21 / n/a |
| Alpha (t) | -4.6% (-2.2) | -4.2% (-2.3) |
| Max drawdown | -28.8% | -25.5% |
| Deflated Sharpe (N=20) | 0.06 | 0.01 |
| Months | 89 | 106 |

Currency, OOS a year: local 3.3%, FX -2.3%, USD 0.9%, hedged 0.4% (hedge cost 2.8%, BRL left out of the hedge for lack of a 3-month rate); FX share of USD variance 0.73. With LEMB's GBI-EM weights instead: FX -3.4%, hedged 2.2%.

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

Yield 6.42% (em_bond_inputs.csv ytm; yield to worst and effective duration from VanEck UCITS fact sheet 2026-08-31 (via search snippet, not US page)) minus fee 0.30% minus expected credit loss 0.30% (rating mix: S&P sovereign ratings of the basket countries (em_bonds_countries.csv, retrieved 2026-11-07), basket-weighted; recovery 49%), minus expected FX depreciation 1.48% (PPP 1.09%, UIP 1.82%); duration 5.1y (em_bond_inputs.csv (2026-08-31)).

| Scenario | Exit yield | Net USD a year |
|---|---|---|
| yields unchanged | 6.42% | 4.4% |
| halfway to fair | 5.58% | 4.7% |
| yields up 200bp | 8.42% | 4.0% |
| yields down 200bp | 4.42% | 5.0% |

Yield-based (halfway to fair) 4.7%; Monte Carlo median 4.7%; **consensus 4.7%**, 5-95% range -1.5% to 11.0%. The credit-loss, rating-mix and FX inputs are judgement. The yield is a portfolio yield to worst, gross of fees, so the expense ratio (0.30%) is subtracted.

## Stress (USD total return; benchmark in brackets)

gfc_2008: n/a (n/a); taper_2013: -14.2% (-6.5%); covid_2020: -14.4% (-16.9%); inflation_2022: -17.5% (-23.2%); strong-USD months average -4.9% (-5.3%).

## Technicals

No technical signal was kept for EM bonds (all five failed the pre-registered out-of-sample test, em_bond_signals.csv), so none is used here.

## Risks

Currency: the dollar's strength since 2011 took most of the local carry; local rate shocks; China/Asia low-yield weights dilute carry. The local-currency view is approximate (basket, not fund weights).

## Verdict

Rank 7 of 8 unhedged. OOS Sharpe -0.10; the currency basket cost about 2.3%/yr since 2018 and hedging would have cost about 2.8%/yr (CIP), so hedged was no better (0.4% vs 0.9% a year). Not a pick on its own record; kept only as the vehicle for the overlay analyst's FX-hedge test and as the local benchmark.

> **How to explain this pick**
>
> EMLC is a local-currency government emerging-market bond fund; from 2018 to Oct 2026 it returned 0.9% a year with a worst fall of -26%, versus 1.0% a year in 2010-2017.
> Its bonds earned about 3.3% a year in local currency since 2018, but the currencies changed the result by -2.3% a year, and hedging them would have cost about 2.8% a year.
> Our forward estimate for the next 7 years is about 4.7% a year in dollars (5-95% range -2% to 11%), built from today's yield less fees and expected defaults.
