# HYEM: VanEck Emerging Markets High Yield Bond ETF

Candidate memo, EM bond funds (Phase 3). Benchmark EMB. Fee 0.40%. Reproduce: `python -m research.candidates.em_bonds --ticker HYEM --write`.

## What it holds

Passive USD high-yield EM corporate bonds (ICE BofA Diversified HY US EM Corporate Plus, from memory, unverified); duration and rating mix not retrieved (VanEck page failed).

Top countries (largest EMBI weights shown on the iShares EMB page (2026-11-05, em_bonds_countries.csv); used as a proxy, HYEM's own country weights were not retrieved): SA 6.4%, MX 6.25%, TR 4.9%, ID 4.34%, BR 3.89%, PL 3.59%.

## What drives returns

mostly spread: high carry, high sensitivity to defaults and risk appetite; shorter duration so US rates matter less. No currency leg.

| | In-sample 2010-17 | Out of sample 2018-26 |
|---|---|---|
| CAGR | 6.5% | 3.4% |
| Volatility | 6.6% | 9.6% |
| Sharpe (vs BIL) | 0.98 | 0.13 |
| IR vs EMB (t) | 0.16 (0.4) | 0.22 (0.7) |
| IR vs EMB / EMLC | 0.16 / 0.66 | 0.22 / 0.38 |
| Alpha (t) | 2.7% (1.3) | 1.1% (0.8) |
| Max drawdown | -11.1% | -26.0% |
| Deflated Sharpe (N=20) | 0.64 | 0.07 |
| Months | 67 | 106 |

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

Yield 7.08% (em_bond_inputs.csv ytm; yfinance trailing yield (issuer page failed)) minus fee 0.40% minus expected credit loss 1.91% (rating mix: judgement: high-yield-only corporate index; mix not retrieved; recovery 40%); duration 4.6y (judgement: set equal to EMHY's 4.66y (iShares 2026-11-05), the closest peer).

| Scenario | Exit yield | Net USD a year |
|---|---|---|
| yields unchanged | 7.08% | 5.4% |
| halfway to fair | 6.60% | 5.5% |
| yields up 200bp | 9.08% | 5.1% |
| yields down 200bp | 5.08% | 5.8% |

Yield-based (halfway to fair) 5.5%; Monte Carlo median 5.7%; **consensus 5.6%**, 5-95% range -0.3% to 11.1%. The credit-loss, rating-mix and FX inputs are judgement. The yield is a 30-day SEC yield or a trailing distribution yield, already net of fund expenses, so the expense ratio is not subtracted again (fix after review, 2026-11-07).

## Stress (USD total return; benchmark in brackets)

gfc_2008: n/a (n/a); taper_2013: -4.9% (-11.2%); covid_2020: -16.3% (-16.0%); inflation_2022: -23.4% (-25.1%); strong-USD months average -2.8% (-4.0%).

## Technicals

No technical signal was kept for EM bonds (all five failed the pre-registered out-of-sample test, em_bond_signals.csv), so none is used here.

## Risks

Corporate defaults in a downturn (China property 2021-22 hit EM high yield); liquidity of a $0.5bn ETF in stress; only 67 in-sample months (short in-sample history).

## Verdict

Rank 1 of 8. Best OOS Sharpe (0.13) and a positive IR vs EMB (0.22, t 0.7) with IR above zero in 80% of OOS rolling windows; in-sample Sharpe 0.98 held up best in relative terms. The price is credit risk: the largest assumed credit loss (1.9%/yr) leaves a 5.5% forward estimate, below EMB's 6.3%. Keep as the credit-risk pick; evidence is weak (t < 1).

> **How to explain this pick**
>
> HYEM is a US-dollar high-yield corporate emerging-market bond fund; from 2018 to Oct 2026 it returned 3.4% a year with a worst fall of -26%, versus 6.5% a year in 2010-2017.
> It pays dollars, so its risk is credit (countries or companies not paying) and US interest rates, not currencies; its Sharpe ratio since 2018 is 0.13.
> Our forward estimate for the next 7 years is about 5.6% a year in dollars (5-95% range -0% to 11%), built from today's yield less fees and expected defaults.
