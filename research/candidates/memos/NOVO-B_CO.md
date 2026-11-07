# Novo Nordisk A/S (NOVO-B.CO) - international growth candidate

Country DK, currency DKK, sector Pharmaceuticals. Benchmark EFG/EEM 50/50 (USD), home index ^STOXX50E_DKK (local). Numbers from `python -m research.candidates.intl_growth --ticker NOVO-B.CO --write`; JSON `reports/candidates/NOVO-B_CO.json`. In-sample 2010-2017, out-of-sample (OOS) 2018-01 to 2026-10.

**Thesis.** The global leader in diabetes and obesity drugs (insulin, semaglutide: Ozempic/Wegovy). It was the top in-sample composite; the 2021-2024 GLP-1 boom and the 2024-2026 collapse (Lilly's tirzepatide winning share, US pricing pressure, guidance cuts) make it the clearest case of a great business whose share price ran ahead of its earnings.

**Return drivers.** Volume growth of GLP-1 drugs, US net pricing, the obesity pipeline (oral and next-generation molecules) versus Eli Lilly; a 4% dividend yield and buybacks.

| USD, monthly | In-sample | OOS | Benchmark OOS |
|---|---|---|---|
| CAGR | 22.1% | 7.0% | 5.8% |
| Sharpe vs BIL | 0.98 | 0.30 | 0.27 |
| Information ratio (t) | 0.75 (2.1) | 0.16 (0.5) | - |
| Alpha (t) | 18.4% (2.5) | 7.0% (0.7) | - |
| Max drawdown | -40% | -74% | -33% |
| Deflated Sharpe (N=31) | 0.74 | 0.13 | - |
| Local: Sharpe / IR vs home index | 1.09 / 0.95 | 0.38 / 0.14 | - |

Method s8 drop rule 2 (OOS Sharpe below benchmark and OOS IR < 0): **not triggered**.

**Fundamentals** (SEC EDGAR point-in-time (CIK0000353278.json); point-in-time: values as filed). Latest fiscal year 2025-12-31: 3-year revenue CAGR 20.4%, net-income CAGR 22.6%, operating margin 41.3%, ROIC 33.6%, FCF yield 4.9%, trailing P/E 11.7 (0.31x its 5-year median). In-sample fundamental score 0.71 (rank 1 of 31 by composite). Margins and ROIC are still those of a top-quartile pharma; the trailing P/E is about a third of its 5-year median, so the price, not the business, did most of the falling.

**Currency.** OOS the stock made 7.9%/yr in DKK, the currency -0.8%/yr, so 7.0%/yr in USD; FX was 8% of the USD return variance. A monthly CIP hedge (cost -0.89%/yr incl. 5 bp per roll) would have returned 8.9%/yr (+1.9% vs unhedged; vol 29% vs 30%). Forward: PPP implies +0.5%/yr for the DKK, UIP +1.3%/yr, the 10-year trend +0.4%/yr. DKK is pegged to the euro, so the USD result is a EUR/USD exposure; the US-Danish rate gap made hedging pay (negative hedge cost) over 2018-2026.

**Expected 7-year return (USD).** CAPM global 7.6%, CAPM local via PPP 5.8%, DCF implied 8.1%, Grinold-Kroner 10.4% (target P/E 16.0). Consensus (median) **7.9%** USD / 7.3% local; with UIP FX 8.7%, with trend FX 7.8%. Monte Carlo (drift set to consensus) 5-95%: -11.0% to 28.2%/yr; historical-drift median 14.3%. 

**Stress (USD, stock / benchmark).** GFC -20% / -58%; taper 2013 -4% / -7%; Covid 1% / -18%; 2022 -1% / -30%; strong-USD months (29) -2.4% / -6.8% per month; 2014-15 USD rally 29% / -3%; 2021-22 30% / -33%.

**Technicals.** No technical signal survived the pre-registered OOS test for this type (research/plan/shortlist.md), so none is used here.

**Risks.** Single-franchise concentration (GLP-1 is most of growth); US drug-price policy (IRA negotiation, most-favoured-nation pricing); semaglutide patent expiry in some markets from 2026; foundation control (Novo Holdings) limits takeover discipline.

**Verdict.** Runner-up at best. OOS Sharpe 0.30 with an IR t-stat of 0.5 is not evidence of skill, and the -74% drawdown since the 2024 peak is far outside the -25% security budget; the cheap valuation (forward about 8% a year in USD) is the only argument for it.

> **How to explain this pick.** Since 2018 Novo Nordisk returned 7.0% a year in dollars with a worst fall of -74%, against 5.8% a year for the international-growth benchmark (risk-adjusted: Sharpe 0.30 vs 0.27). The DKK cost 0.8% a year against the dollar, so the local-currency return was 7.9%; hedging the currency each month would have raised the dollar return by 1.9% a year. Looking forward, the middle of our model estimates is about 8% a year in dollars over 7 years, with a wide 5-95% range of -11% to 28% a year.

Data notes: DKK 3M: DK_3M (yields.csv), previous month; home index is a Yahoo price index (no dividends): local IR/alpha are flattered by about its dividend yield; home index proxy: Euro Stoxx 50 (^STOXX50E) converted to DKK; no OMX Copenhagen series on disk; doubled prices on a few 2005-2006 holidays lie before the 2010 window; ADR cross-check vs NVO: corr 0.988 over 262 months, mean difference -0.08%/yr (local in USD minus ADR); OOS corr 0.989, diff -0.15%/yr; fundamentals: SEC EDGAR point-in-time (CIK0000353278.json); traded value (Yahoo volume x USD adj. close): 280M USD/day last 252 days; 114M at 2017-12-31.
