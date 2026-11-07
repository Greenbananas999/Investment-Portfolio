# PYEMX: Payden Emerging Markets Bond Fund

Candidate memo, EM bond funds (Phase 3). Benchmark EMB. Fee 0.73%. Reproduce: `python -m research.candidates.em_bonds --ticker PYEMX --write`.

## What it holds

Active, mainly USD EM sovereign bonds (benchmark EMBI GD, from memory, unverified); holdings, duration and rating mix not retrieved.

Top countries (largest EMBI weights shown on the iShares EMB page (2026-11-05, em_bonds_countries.csv); used as a proxy, PYEMX's own country weights were not retrieved): SA 6.4%, MX 6.25%, TR 4.9%, ID 4.34%, BR 3.89%, PL 3.59%.

## What drives returns

carry (US Treasury yield plus the EM sovereign spread), spread changes (risk appetite, defaults such as the 2020-22 restructurings), and US rates through a 6-7 year duration. No currency leg.

| | In-sample 2010-17 | Out of sample 2018-26 |
|---|---|---|
| CAGR | 7.0% | 3.0% |
| Volatility | 7.1% | 10.6% |
| Sharpe (vs BIL) | 0.98 | 0.10 |
| IR vs EMB (t) | 0.20 (0.6) | 0.29 (0.9) |
| IR vs EMB / EMLC | 0.20 / 0.70 | 0.29 / 0.37 |
| Alpha (t) | 0.7% (0.9) | 0.8% (0.9) |
| Max drawdown | -12.1% | -27.8% |
| Deflated Sharpe (N=20) | 0.77 | 0.06 |
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

Yield 7.03% (em_bond_inputs.csv ytm; yfinance trailing distribution yield (not YTM)) minus fee 0.73% minus expected credit loss 0.90% (rating mix: judgement: active EMBI GD fund assumed close to EMB, slightly lower quality; recovery 49%); duration 6.4y (judgement: set equal to EMB's 6.38y (benchmark EMBI GD); not retrieved).

| Scenario | Exit yield | Net USD a year |
|---|---|---|
| yields unchanged | 7.03% | 6.4% |
| halfway to fair | 6.55% | 6.6% |
| yields up 200bp | 9.03% | 5.6% |
| yields down 200bp | 5.03% | 7.3% |

Yield-based (halfway to fair) 6.6%; Monte Carlo median 6.7%; **consensus 6.6%**, 5-95% range -0.1% to 13.4%. The credit-loss, rating-mix and FX inputs are judgement. The yield is a 30-day SEC yield or a trailing distribution yield, already net of fund expenses, so the expense ratio is not subtracted again (fix after review, 2026-11-07).

## Stress (USD total return; benchmark in brackets)

gfc_2008: -13.2% (n/a); taper_2013: -12.1% (-11.2%); covid_2020: -16.4% (-16.0%); inflation_2022: -25.0% (-25.1%); strong-USD months average -3.5% (-4.0%).

## Technicals

No technical signal was kept for EM bonds (all five failed the pre-registered out-of-sample test, em_bond_signals.csv), so none is used here.

## Risks

Active-manager risk; fee 0.73%; holdings not retrieved, so the rating mix is assumed.

## Verdict

Rank 2 of 8. Highest OOS IR vs EMB (0.29, t 0.9), IR positive in 85% of OOS windows, and the highest forward estimate (6.8%) on a 7.0% distribution yield. Active fee 0.73%. Keep as the active hard-currency pick; its rating mix is assumed, not retrieved.

> **How to explain this pick**
>
> PYEMX is a US-dollar government emerging-market bond fund; from 2018 to Oct 2026 it returned 3.0% a year with a worst fall of -28%, versus 7.0% a year in 2010-2017.
> It pays dollars, so its risk is credit (countries or companies not paying) and US interest rates, not currencies; its Sharpe ratio since 2018 is 0.10.
> Our forward estimate for the next 7 years is about 6.6% a year in dollars (5-95% range -0% to 13%), built from today's yield less fees and expected defaults.
