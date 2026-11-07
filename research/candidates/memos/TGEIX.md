# TGEIX: TCW Emerging Markets Income Fund I

Candidate memo, EM bond funds (Phase 3). Benchmark EMB. Fee 0.85%. Reproduce: `python -m research.candidates.em_bonds --ticker TGEIX --write`.

## What it holds

Active, mainly USD EM sovereign and corporate bonds (benchmark EMBI GD, from memory, unverified); may hold some local-currency debt; holdings, duration and rating mix not retrieved.

Top countries (largest EMBI weights shown on the iShares EMB page (2026-11-05, em_bonds_countries.csv); used as a proxy, TGEIX's own country weights were not retrieved): SA 6.4%, MX 6.25%, TR 4.9%, ID 4.34%, BR 3.89%, PL 3.59%.

## What drives returns

carry (US Treasury yield plus the EM sovereign spread), spread changes (risk appetite, defaults such as the 2020-22 restructurings), and US rates through a 6-7 year duration. No currency leg.

| | In-sample 2010-17 | Out of sample 2018-26 |
|---|---|---|
| CAGR | 7.6% | 2.6% |
| Volatility | 8.0% | 11.4% |
| Sharpe (vs BIL) | 0.95 | 0.07 |
| IR vs EMB (t) | 0.27 (0.8) | 0.17 (0.5) |
| IR vs EMB / EMLC | 0.27 / 0.81 | 0.17 / 0.29 |
| Alpha (t) | 1.3% (0.8) | 0.6% (0.5) |
| Max drawdown | -11.1% | -27.5% |
| Deflated Sharpe (N=20) | 0.75 | 0.05 |
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

Yield 6.52% (em_bond_inputs.csv ytm; yfinance trailing distribution yield (not YTM)) minus fee 0.85% minus expected credit loss 1.06% (rating mix: judgement: active EMBI GD fund assumed to lean to high yield vs EMB; not retrieved; recovery 49%); duration 6.4y (judgement: set equal to EMB's 6.38y (benchmark EMBI GD); not retrieved).

| Scenario | Exit yield | Net USD a year |
|---|---|---|
| yields unchanged | 6.52% | 5.7% |
| halfway to fair | 6.04% | 5.9% |
| yields up 200bp | 8.52% | 4.9% |
| yields down 200bp | 4.52% | 6.6% |

Yield-based (halfway to fair) 5.9%; Monte Carlo median 5.9%; **consensus 5.9%**, 5-95% range -1.4% to 13.5%. The credit-loss, rating-mix and FX inputs are judgement. The yield is a 30-day SEC yield or a trailing distribution yield, already net of fund expenses, so the expense ratio is not subtracted again (fix after review, 2026-11-07).

## Stress (USD total return; benchmark in brackets)

gfc_2008: -9.6% (n/a); taper_2013: -10.5% (-11.2%); covid_2020: -20.4% (-16.0%); inflation_2022: -22.8% (-25.1%); strong-USD months average -3.9% (-4.0%).

## Technicals

No technical signal was kept for EM bonds (all five failed the pre-registered out-of-sample test, em_bond_signals.csv), so none is used here.

## Risks

Active-manager risk (style drift, key-person); higher fee 0.85%; may hold local-currency bonds, so some FX exposure that this analysis does not measure.

## Verdict

Rank 4 of 8. OOS IR vs EMB 0.17 (t 0.5) but the second-worst Covid fall (-20%) and a 0.85% fee. Note: the Phase 2 table's 0.81 in-sample IR was measured against EMLC (the screen classed it local); vs EMB it was 0.27. Runner-up behind PYEMX.

> **How to explain this pick**
>
> TGEIX is a US-dollar government emerging-market bond fund; from 2018 to Oct 2026 it returned 2.6% a year with a worst fall of -28%, versus 7.6% a year in 2010-2017.
> It pays dollars, so its risk is credit (countries or companies not paying) and US interest rates, not currencies; its Sharpe ratio since 2018 is 0.07.
> Our forward estimate for the next 7 years is about 5.9% a year in dollars (5-95% range -1% to 14%), built from today's yield less fees and expected defaults.
