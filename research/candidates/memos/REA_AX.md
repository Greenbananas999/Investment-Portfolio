# REA Group Limited (REA.AX) - international growth candidate

Country AU, currency AUD, sector Online classifieds (property). Benchmark EFG/EEM 50/50 (USD), home index ^AXJO (local). Numbers from `python -m research.candidates.intl_growth --ticker REA.AX --write`; JSON `reports/candidates/REA_AX.json`. In-sample 2010-2017, out-of-sample (OOS) 2018-01 to 2026-10.

**Thesis.** Australia's dominant online property-listings marketplace (realestate.com.au), majority-owned by News Corp: a network business with pricing power that grows with listing 'depth' fees more than with housing volumes.

**Return drivers.** Annual price rises on premium listings, depth penetration, adjacent mortgage and data products; earnings growth in the low teens; expensive multiple.

| USD, monthly | In-sample | OOS | Benchmark OOS |
|---|---|---|---|
| CAGR | 29.3% | 8.7% | 5.8% |
| Sharpe vs BIL | 0.96 | 0.34 | 0.27 |
| Information ratio (t) | 0.89 (2.5) | 0.24 (0.7) | - |
| Alpha (t) | 24.1% (2.5) | 6.0% (0.7) | - |
| Max drawdown | -33% | -41% | -33% |
| Deflated Sharpe (N=31) | 0.73 | 0.14 | - |
| Local: Sharpe / IR vs home index | 1.03 / 1.18 | 0.40 / 0.37 | - |

Method s8 drop rule 2 (OOS Sharpe below benchmark and OOS IR < 0): **not triggered**.

**Fundamentals** (yfinance current statements (fundamentals not point-in-time); **flagged**). Latest fiscal year 2026-06-30: 3-year revenue CAGR 13.0%, net-income CAGR 15.7%, operating margin 48.6%, ROIC 42.3%, FCF yield n/a, trailing P/E 41.8 (0.62x its 5-year median). In-sample fundamental score 0.68 (rank 2 of 31 by composite). 49% operating margin, ROIC above 40%, net cash; trailing P/E around 40, below its own 5-year median.

**Currency.** OOS the stock made 10.0%/yr in AUD, the currency -1.2%/yr, so 8.7%/yr in USD; FX was 25% of the USD return variance. A monthly CIP hedge (cost 0.31%/yr incl. 5 bp per roll) would have returned 10.5%/yr (+1.9% vs unhedged; vol 28% vs 32%). Forward: PPP implies +0.0%/yr for the AUD, UIP -0.9%/yr, the 10-year trend -0.9%/yr. The AUD is a risk-on, commodity currency: FX was a quarter of USD variance and fell with stocks in 2020 and 2022, which weakens it as a diversifier.

**Expected 7-year return (USD).** CAPM global 9.4%, CAPM local via PPP 10.0%, DCF implied 9.8%, Grinold-Kroner 10.7% (target P/E 24.0). Consensus (median) **9.9%** USD / 9.9% local; with UIP FX 9.0%, with trend FX 9.0%. Monte Carlo (drift set to consensus) 5-95%: -7.3% to 29.6%/yr; historical-drift median 18.2%. 

**Stress (USD, stock / benchmark).** GFC -64% / -58%; taper 2013 1% / -7%; Covid -38% / -18%; 2022 -35% / -30%; strong-USD months (29) -5.6% / -6.8% per month; 2014-15 USD rally -12% / -3%; 2021-22 -40% / -33%.

**Technicals.** No technical signal survived the pre-registered OOS test for this type (research/plan/shortlist.md), so none is used here.

**Risks.** Australian housing cycle and listing volumes; competition from Domain (now owned by CoStar); News Corp control (about 61%); valuation if growth slows; AUD weakness in risk-off episodes.

**Verdict.** Not recommended. OOS Sharpe 0.34 and IR 0.24 (t 0.7) are barely above the benchmark's 0.27, and the Covid drawdown was twice the benchmark's; a high-quality business whose price already reflects it (forward about 10% a year in USD).

> **How to explain this pick.** Since 2018 REA Group returned 8.7% a year in dollars with a worst fall of -41%, against 5.8% a year for the international-growth benchmark (risk-adjusted: Sharpe 0.34 vs 0.27). The AUD cost 1.2% a year against the dollar, so the local-currency return was 10.0%; hedging the currency each month would have raised the dollar return by 1.9% a year. Looking forward, the middle of our model estimates is about 10% a year in dollars over 7 years, with a wide 5-95% range of -7% to 30% a year.

Data notes: AUD 3M: AU_3M (yields.csv), previous month; home index is a Yahoo price index (no dividends): local IR/alpha are flattered by about its dividend yield; no ADR/US listing on disk to cross-check the USD series; fundamentals: yfinance current statements (fundamentals not point-in-time); traded value (Yahoo volume x USD adj. close): 33M USD/day last 252 days; 10M at 2017-12-31.
