# PCY: Invesco Emerging Markets Sovereign Debt ETF

Candidate memo, EM bond funds (Phase 3). Benchmark EMB. Fee 0.50%. Reproduce: `python -m research.candidates.em_bonds --ticker PCY --write`.

## What it holds

Passive USD sovereign bonds with equal country weights (index stated from memory, unverified: DBIQ EM USD Liquid Balanced); duration, holdings and rating mix not retrieved (Invesco page unreadable).

Top countries (largest EMBI weights shown on the iShares EMB page (2026-11-05, em_bonds_countries.csv); used as a proxy, PCY's own country weights were not retrieved): SA 6.4%, MX 6.25%, TR 4.9%, ID 4.34%, BR 3.89%, PL 3.59%.

## What drives returns

carry (US Treasury yield plus the EM sovereign spread), spread changes (risk appetite, defaults such as the 2020-22 restructurings), and US rates through a 6-7 year duration. No currency leg.

| | In-sample 2010-17 | Out of sample 2018-26 |
|---|---|---|
| CAGR | 7.2% | 1.4% |
| Volatility | 8.1% | 13.8% |
| Sharpe (vs BIL) | 0.89 | -0.01 |
| IR vs EMB (t) | 0.38 (1.1) | -0.09 (-0.3) |
| IR vs EMB / EMLC | 0.38 / 0.68 | -0.09 / 0.11 |
| Alpha (t) | -0.1% (-0.2) | -0.4% (-0.5) |
| Max drawdown | -13.8% | -35.7% |
| Deflated Sharpe (N=20) | 0.70 | 0.03 |
| Months | 96 | 106 |

## Fundamentals (top countries)

| Country | 10y | 3m | CPI | Real 10y | S&P / Moody's |
|---|---|---|---|---|---|
| SA | n/a | n/a | n/a | n/a | A+ / Aa3 |
| MX | 9.2% | 6.8% | 3.8% | 5.4% | BBB / Baa3 |
| TR | 35.8% | n/a | 30.9% | 4.9% | BB- / Ba3 |
| ID | 7.0% | 5.5% | 3.3% | 3.7% | BBB / Baa2 |
| BR | n/a | n/a | 4.6% | n/a | BB / Ba1 |
| PL | 6.3% | 3.9% | 2.4% | 3.9% | A- / A2 |

Debt/GDP and current account are not in the repo data and were not checked. Gulf and Asian issuers without OECD series show n/a. Full table: `research/candidates/memos/em_bonds_countries.md`.

## Forward view (7 years, USD)

Yield 6.24% (em_bond_inputs.csv ytm; yfinance trailing yield (issuer page unreadable)) minus fee 0.50% minus expected credit loss 1.10% (rating mix: judgement: equal country weights give more weight to small high-yield issuers than EMB; recovery 49%); duration 7.5y (judgement: equal-weight sovereign index with longer maturities than EMB (shortlist.md); no duration retrieved).

| Scenario | Exit yield | Net USD a year |
|---|---|---|
| yields unchanged | 6.24% | 5.3% |
| halfway to fair | 5.76% | 5.6% |
| yields up 200bp | 8.24% | 4.2% |
| yields down 200bp | 4.24% | 6.7% |

Yield-based (halfway to fair) 5.6%; Monte Carlo median 5.8%; **consensus 5.7%**, 5-95% range -2.9% to 14.1%. The credit-loss, rating-mix and FX inputs are judgement. The yield is a 30-day SEC yield or a trailing distribution yield, already net of fund expenses, so the expense ratio is not subtracted again (fix after review, 2026-11-07).

## Stress (USD total return; benchmark in brackets)

gfc_2008: -14.2% (n/a); taper_2013: -13.8% (-11.2%); covid_2020: -19.1% (-16.0%); inflation_2022: -32.5% (-25.1%); strong-USD months average -4.4% (-4.0%).

## Technicals

No technical signal was kept for EM bonds (all five failed the pre-registered out-of-sample test, em_bond_signals.csv), so none is used here.

## Risks

Same as EMB plus longer duration and more weight on small, lower-rated countries (equal weighting); worst drawdown of the hard-currency group out of sample.

## Verdict

Rank 6 of 8. Drop under method.md section 8 rule 2: OOS Sharpe (-0.01) below EMB's (0.02) and OOS IR vs EMB below zero (-0.09); worst OOS drawdown of the eight (-36%) from its long duration in 2022.

> **How to explain this pick**
>
> PCY is a US-dollar government emerging-market bond fund; from 2018 to Oct 2026 it returned 1.4% a year with a worst fall of -36%, versus 7.2% a year in 2010-2017.
> It pays dollars, so its risk is credit (countries or companies not paying) and US interest rates, not currencies; its Sharpe ratio since 2018 is -0.01.
> Our forward estimate for the next 7 years is about 5.7% a year in dollars (5-95% range -3% to 14%), built from today's yield less fees and expected defaults.
