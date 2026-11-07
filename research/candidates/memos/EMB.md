# EMB: iShares J.P. Morgan USD Emerging Markets Bond ETF

Candidate memo, EM bond funds (Phase 3). Benchmark GUIDE_BENCH (method benchmark EMB; EMB is itself a method benchmark). Fee 0.39%. Reproduce: `python -m research.candidates.em_bonds --ticker EMB --write`.

## What it holds

Passive USD sovereign and quasi-sovereign bonds, JPM EMBI Global Diversified Core; 619 holdings; duration 6.38y; ratings A 17%, BBB 34%, BB 26%, B 19%, CCC 3% (iShares, 2026-11-05).

Top countries (largest EMBI weights shown on the iShares EMB page (2026-11-05, em_bonds_countries.csv); these are EMB's own weights): SA 6.4%, MX 6.25%, TR 4.9%, ID 4.34%, BR 3.89%, PL 3.59%.

## What drives returns

carry (US Treasury yield plus the EM sovereign spread), spread changes (risk appetite, defaults such as the 2020-22 restructurings), and US rates through a 6-7 year duration. No currency leg.

| | In-sample 2010-17 | Out of sample 2018-26 |
|---|---|---|
| CAGR | 6.5% | 2.2% |
| Volatility | 7.1% | 10.6% |
| Sharpe (vs BIL) | 0.92 | 0.02 |
| IR vs GUIDE_BENCH (t) | 0.07 (0.2) | -0.76 (-2.3) |
| IR vs EMB / EMLC | n/a / 0.61 | n/a / 0.21 |
| Alpha (t) | 3.4% (2.1) | -3.1% (-2.0) |
| Max drawdown | -11.3% | -26.7% |
| Deflated Sharpe (N=20) | 0.73 | 0.03 |
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

Yield 6.52% (em_bond_inputs.csv ytm; 30-day SEC yield 2026-11-05) minus fee 0.39% minus expected credit loss 0.74% (rating mix: iShares EMB page, credit quality as of 2026-11-05 (em_bonds.csv notes); recovery 49%); duration 6.4y (em_bond_inputs.csv (2026-11-05)).

| Scenario | Exit yield | Net USD a year |
|---|---|---|
| yields unchanged | 6.52% | 6.0% |
| halfway to fair | 6.04% | 6.2% |
| yields up 200bp | 8.52% | 5.2% |
| yields down 200bp | 4.52% | 6.9% |

Yield-based (halfway to fair) 6.2%; Monte Carlo median 6.3%; **consensus 6.3%**, 5-95% range -0.4% to 12.7%. The credit-loss, rating-mix and FX inputs are judgement. The yield is a 30-day SEC yield or a trailing distribution yield, already net of fund expenses, so the expense ratio is not subtracted again (fix after review, 2026-11-07).

## Stress (USD total return; benchmark in brackets)

gfc_2008: n/a (n/a); taper_2013: -11.2% (-6.5%); covid_2020: -16.0% (-16.9%); inflation_2022: -25.1% (-23.2%); strong-USD months average -4.0% (-5.3%).

## Technicals

No technical signal was kept for EM bonds (all five failed the pre-registered out-of-sample test, em_bond_signals.csv), so none is used here.

## Risks

Sovereign defaults and restructurings (2020-23: Lebanon, Sri Lanka, Ghana, Zambia, Russia, Ukraine); US rate rises (2022: about -18%); concentration in Gulf issuers. Evidence on forward returns is a yield, not a forecast of spreads.

## Verdict

Rank 5 of 8, but the default passive core. OOS Sharpe 0.02; as the benchmark it has no IR vs itself; vs GUIDE_BENCH -0.76 (t -2.3), i.e. EM bonds as a whole lagged the 55/35/10 since 2018. Cheapest (0.39%), most liquid, forward 6.3% (second highest). Keep as the core holding or the fallback if active funds are not wanted.

> **How to explain this pick**
>
> EMB is a US-dollar government emerging-market bond fund; from 2018 to Oct 2026 it returned 2.2% a year with a worst fall of -27%, versus 6.5% a year in 2010-2017.
> It pays dollars, so its risk is credit (countries or companies not paying) and US interest rates, not currencies; its Sharpe ratio since 2018 is 0.02.
> Our forward estimate for the next 7 years is about 6.3% a year in dollars (5-95% range -0% to 13%), built from today's yield less fees and expected defaults.
