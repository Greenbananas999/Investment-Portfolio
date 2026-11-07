# Constellation Software Inc. (CSU.TO) - international growth candidate

Country CA, currency CAD, sector Vertical-market software. Benchmark EFG/EEM 50/50 (USD), home index ^GSPTSE (local). Numbers from `python -m research.candidates.intl_growth --ticker CSU.TO --write`; JSON `reports/candidates/CSU_TO.json`. In-sample 2010-2017, out-of-sample (OOS) 2018-01 to 2026-10.

**Thesis.** Serial acquirer of small vertical-market software businesses (thousands of niche, mission-critical systems for municipalities, utilities, healthcare), compounding by reinvesting free cash flow at high returns.

**Return drivers.** Capital deployed in acquisitions and the hurdle rate earned; organic growth low single digits; founder Mark Leonard stepped down as president in 2025.

| USD, monthly | In-sample | OOS | Benchmark OOS |
|---|---|---|---|
| CAGR | 45.7% | 17.6% | 5.8% |
| Sharpe vs BIL | 1.66 | 0.64 | 0.27 |
| Information ratio (t) | 1.48 (4.2) | 0.51 (1.5) | - |
| Alpha (t) | 36.9% (4.6) | 14.5% (1.7) | - |
| Max drawdown | -18% | -52% | -33% |
| Deflated Sharpe (N=31) | 1.00 | 0.43 | - |
| Local: Sharpe / IR vs home index | 1.83 / 1.68 | 0.74 / 0.47 | - |

Method s8 drop rule 2 (OOS Sharpe below benchmark and OOS IR < 0): **not triggered**.

**Fundamentals** (yfinance current statements (fundamentals not point-in-time); **flagged**). Latest fiscal year 2025-12-31: 3-year revenue CAGR 20.6%, net-income CAGR 0.0%, operating margin 18.1%, ROIC 21.0%, FCF yield 5.0%, trailing P/E 103.4 (1.11x its 5-year median). In-sample fundamental score 0.48 (rank 10 of 31 by composite). Books in USD: revenue CAGR 21%. GAAP earnings are depressed by acquisition amortisation, so the trailing P/E on last fiscal-year EPS (about 100) overstates the multiple; forward P/E 19, FCF yield about 5%.

**Currency.** OOS the stock made 19.1%/yr in CAD, the currency -1.2%/yr, so 17.6%/yr in USD; FX was 14% of the USD return variance. A monthly CIP hedge (cost 0.13%/yr incl. 5 bp per roll) would have returned 19.3%/yr (+1.6% vs unhedged; vol 25% vs 27%). Forward: PPP implies +0.5%/yr for the CAD, UIP +1.4%/yr, the 10-year trend -0.5%/yr. CAD cost 1.2%/yr OOS and was 14% of USD variance; the US-Canada rate gap was small, so hedging cost almost nothing in carry.

**Expected 7-year return (USD).** CAPM global 8.2%, CAPM local via PPP 6.6%, DCF implied 11.1%, Grinold-Kroner 9.2% (target P/E 20.0). Consensus (median) **8.7%** USD / 8.1% local; with UIP FX 9.7%, with trend FX 7.6%. Monte Carlo (drift set to consensus) 5-95%: -8.1% to 26.3%/yr; historical-drift median 30.8%. 

**Stress (USD, stock / benchmark).** GFC -28% / -58%; taper 2013 21% / -7%; Covid -14% / -18%; 2022 -21% / -30%; strong-USD months (29) -3.1% / -6.8% per month; 2014-15 USD rally 56% / -3%; 2021-22 -1% / -33%.

**Technicals.** No technical signal survived the pre-registered OOS test for this type (research/plan/shortlist.md), so none is used here.

**Risks.** Capital deployment (larger, lower-return deals), succession after the founder, fear of AI disrupting legacy software (the 2025-2026 sell-off, -52% drawdown); revenue is global, so Canada-specific risk is low.

**Verdict.** Good runner-up. OOS Sharpe 0.64 and IR 0.51 (t 1.5, deflated Sharpe 0.43) with the best 2022 stress result of the eight, but the 2025-2026 drawdown shows the 'software is safe' assumption failing; forward about 9% a year in USD.

> **How to explain this pick.** Since 2018 Constellation Software returned 17.6% a year in dollars with a worst fall of -52%, against 5.8% a year for the international-growth benchmark (risk-adjusted: Sharpe 0.64 vs 0.27). The CAD cost 1.2% a year against the dollar, so the local-currency return was 19.1%; hedging the currency each month would have raised the dollar return by 1.6% a year. Looking forward, the middle of our model estimates is about 9% a year in dollars over 7 years, with a wide 5-95% range of -8% to 26% a year.

Data notes: CAD 3M: CA_3M (yields.csv), previous month; home index is a Yahoo price index (no dividends): local IR/alpha are flattered by about its dividend yield; no ADR/US listing on disk to cross-check the USD series; fundamentals: yfinance current statements (fundamentals not point-in-time); traded value (Yahoo volume x USD adj. close): 153M USD/day last 252 days; 19M at 2017-12-31.
