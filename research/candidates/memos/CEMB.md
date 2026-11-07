# CEMB: iShares J.P. Morgan EM Corporate Bond ETF

Candidate memo, EM bond funds (Phase 3). Benchmark EMB. Fee 0.50%. Reproduce: `python -m research.candidates.em_bonds --ticker CEMB --write`.

## What it holds

Passive USD EM corporate bonds, JPM CEMBI Broad Diversified Core; 1,185 holdings; effective duration 4.21y (iShares, 2026-11-05); rating mix not retrieved.

Top countries (largest EMBI weights shown on the iShares EMB page (2026-11-05, em_bonds_countries.csv); used as a proxy, CEMB's own country weights were not retrieved): SA 6.4%, MX 6.25%, TR 4.9%, ID 4.34%, BR 3.89%, PL 3.59%.

## What drives returns

corporate spread plus US rates (duration about 4y); investment-grade bias, so lower carry and smaller default losses. No currency leg.

| | In-sample 2010-17 | Out of sample 2018-26 |
|---|---|---|
| CAGR | 4.4% | 2.8% |
| Volatility | 6.7% | 8.0% |
| Sharpe (vs BIL) | 0.66 | 0.07 |
| IR vs EMB (t) | -0.15 (-0.4) | 0.09 (0.3) |
| IR vs EMB / EMLC | -0.15 / 0.64 | 0.09 / 0.25 |
| Alpha (t) | 0.4% (0.2) | 0.4% (0.5) |
| Max drawdown | -11.3% | -20.3% |
| Deflated Sharpe (N=20) | 0.37 | 0.05 |
| Months | 68 | 106 |

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

Yield 6.34% (em_bond_inputs.csv ytm; 30-day SEC yield 2026-11-05) minus fee 0.50% minus expected credit loss 0.68% (rating mix: judgement: CEMBI Broad Diversified Core is mostly investment grade; mix not retrieved; recovery 40%); duration 4.2y (em_bond_inputs.csv (2026-11-05)).

| Scenario | Exit yield | Net USD a year |
|---|---|---|
| yields unchanged | 6.34% | 5.8% |
| halfway to fair | 5.86% | 5.9% |
| yields up 200bp | 8.34% | 5.7% |
| yields down 200bp | 4.34% | 6.1% |

Yield-based (halfway to fair) 5.9%; Monte Carlo median 6.0%; **consensus 6.0%**, 5-95% range 1.2% to 10.5%. The credit-loss, rating-mix and FX inputs are judgement. The yield is a 30-day SEC yield or a trailing distribution yield, already net of fund expenses, so the expense ratio is not subtracted again (fix after review, 2026-11-07).

## Stress (USD total return; benchmark in brackets)

gfc_2008: n/a (n/a); taper_2013: -11.3% (-11.2%); covid_2020: -13.9% (-16.0%); inflation_2022: -19.0% (-25.1%); strong-USD months average -2.2% (-4.0%).

## Technicals

No technical signal was kept for EM bonds (all five failed the pre-registered out-of-sample test, em_bond_signals.csv), so none is used here.

## Risks

Corporate spread and US rates; small ETF ($0.4bn) with thin trading; only 68 in-sample months.

## Verdict

Rank 3 of 8. Smallest OOS drawdown (-20%, the only one inside the -25% security budget) and the narrowest forward range (1.2% to 10.6%); OOS IR vs EMB 0.09. Weak in-sample (IR -0.15). Keep as the 'security' bond; small ETF ($0.4bn) with thin trading.

> **How to explain this pick**
>
> CEMB is a US-dollar corporate emerging-market bond fund; from 2018 to Oct 2026 it returned 2.8% a year with a worst fall of -20%, versus 4.4% a year in 2010-2017.
> It pays dollars, so its risk is credit (countries or companies not paying) and US interest rates, not currencies; its Sharpe ratio since 2018 is 0.07.
> Our forward estimate for the next 7 years is about 6.0% a year in dollars (5-95% range 1% to 11%), built from today's yield less fees and expected defaults.
