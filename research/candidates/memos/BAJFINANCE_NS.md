# Bajaj Finance Limited (BAJFINANCE.NS) - international growth candidate

Country IN, currency INR, sector Consumer finance (NBFC). Benchmark EFG/EEM 50/50 (USD), home index ^NSEI (local). Numbers from `python -m research.candidates.intl_growth --ticker BAJFINANCE.NS --write`; JSON `reports/candidates/BAJFINANCE_NS.json`. In-sample 2010-2017, out-of-sample (OOS) 2018-01 to 2026-10.

**Thesis.** India's largest retail non-bank lender (consumer durables, personal, SME and mortgage loans): a direct play on Indian consumer-credit growth.

**Return drivers.** Loan-book growth of 25%+ a year, net interest margin, credit costs and the Indian equity multiple; ROE in the high teens.

| USD, monthly | In-sample | OOS | Benchmark OOS |
|---|---|---|---|
| CAGR | 59.8% | 16.0% | 5.8% |
| Sharpe vs BIL | 1.39 | 0.51 | 0.27 |
| Information ratio (t) | 1.37 (3.9) | 0.43 (1.3) | - |
| Alpha (t) | 47.9% (3.8) | 17.6% (1.3) | - |
| Max drawdown | -41% | -58% | -33% |
| Deflated Sharpe (N=31) | 0.97 | 0.28 | - |
| Local: Sharpe / IR vs home index | 1.45 / 1.67 | 0.55 / 0.55 | - |

Method s8 drop rule 2 (OOS Sharpe below benchmark and OOS IR < 0): **not triggered**.

**Fundamentals** (yfinance current statements (fundamentals not point-in-time); **flagged**). Latest fiscal year 2026-03-31: 3-year revenue CAGR 22.6%, net-income CAGR 18.2%, operating margin n/a, ROE 16.7%, FCF yield -9.9%, trailing P/E 35.7 (1.00x its 5-year median). In-sample fundamental score 0.56 (rank 6 of 31 by composite). Revenue CAGR 23%, ROE about 17%; free cash flow is negative by construction (loan growth), so the DCF is left out.

**Currency.** OOS the stock made 21.3%/yr in INR, the currency -4.4%/yr, so 16.0%/yr in USD; FX was 8% of the USD return variance. A monthly CIP hedge (cost 3.42%/yr incl. 5 bp per roll) would have returned 18.3%/yr (+2.2% vs unhedged; vol 41% vs 42%). Forward: PPP implies -1.4%/yr for the INR, UIP -1.6%/yr, the 10-year trend -3.1%/yr. The largest FX drag of the eight: Indian rates above US rates make the hedge expensive, yet the rupee fell by more than the carry in this window.

**Expected 7-year return (USD).** CAPM global 10.1%, CAPM local via PPP 12.6%, DCF implied n/a, Grinold-Kroner 11.1% (target P/E 20.0). Consensus (median) **11.1%** USD / 12.8% local; with UIP FX 10.9%, with trend FX 9.3%. Monte Carlo (drift set to consensus) 5-95%: -11.9% to 39.7%/yr; historical-drift median 35.2%. DCF not applied: lender (NBFC) (free cash flow not meaningful).

**Stress (USD, stock / benchmark).** GFC -87% / -58%; taper 2013 -32% / -7%; Covid -52% / -18%; 2022 -7% / -30%; strong-USD months (29) -5.2% / -6.8% per month; 2014-15 USD rally 93% / -3%; 2021-22 16% / -33%.

**Technicals.** No technical signal survived the pre-registered OOS test for this type (research/plan/shortlist.md), so none is used here.

**Risks.** INR depreciation; the credit cycle (the 2018 IL&FS shadow-bank crisis and Covid hit NBFCs hardest: -52% in Q1 2020 in USD); RBI regulation (2023 lending curbs); succession; high valuation.

**Verdict.** Possible, not first choice. OOS Sharpe 0.51 and IR 0.43 (t 1.3, deflated Sharpe 0.28) are positive but statistically weak, with a -58% drawdown and the worst Covid and taper stress of the eight; forward about 11% a year in USD.

> **How to explain this pick.** Since 2018 Bajaj Finance returned 16.0% a year in dollars with a worst fall of -58%, against 5.8% a year for the international-growth benchmark (risk-adjusted: Sharpe 0.51 vs 0.27). The INR cost 4.4% a year against the dollar, so the local-currency return was 21.3%; hedging the currency each month would have raised the dollar return by 2.2% a year. Looking forward, the middle of our model estimates is about 11% a year in dollars over 7 years, with a wide 5-95% range of -12% to 40% a year.

Data notes: INR 3M rate: OECD IN_3M from 2011-12; flat 5.61% before - approximate in 2010-2011; home index is a Yahoo price index (no dividends): local IR/alpha are flattered by about its dividend yield; no ADR/US listing on disk to cross-check the USD series; financial: ROE used, net debt/EBITDA skipped; fundamentals: yfinance current statements (fundamentals not point-in-time); traded value (Yahoo volume x USD adj. close): 86M USD/day last 252 days; 23M at 2017-12-31.
