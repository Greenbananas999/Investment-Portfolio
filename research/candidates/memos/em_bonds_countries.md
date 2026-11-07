# EM local-currency government bonds: country table

Built by `python -m research.candidates.em_bonds --all --write`. Yields: OECD/FRED monthly averages in `data/research/yields.csv` (latest observation, date shown). CPI: latest OECD year-on-year, or the World Bank annual figure (`cpi_annual.csv`) when it is newer. Real yield = 10y minus CPI. Ratings: `research/plan/longlists/em_bonds_countries.csv` (Wikipedia / countryeconomy.com, retrieved 2026-11-07). Realised returns: a constant-maturity 10y bond rebuilt from the yields with `research.bonds.total_returns` (semiannual coupon, bought at par each month, no fees), converted to USD at month-end FX. Gap rule (all countries): a missing yield month inside a series is forward-filled when the gap is at most 3 months; a longer gap is a missing period with no return, and returns are never spliced across it (MX_10Y has 63 missing months; before this fix the splice showed the peso rising). Turkey has no free yield history (spot quote only, research.config.SPOT_YIELDS); no return is shown.

| Country | 10y (date) | 3m | CPI (date) | Real 10y | Real 10y avg 2010-17 | S&P / Moody's | Local CAGR | USD CAGR | FX a year | USD in-sample / OOS | Period |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MX | 9.25% (2026-10-31) | 6.81% | 3.8% (2025 (World Bank)) | 5.44% | 2.34% | BBB / Baa3 | 6.7% | 4.6% | -2.0% | 1.2% / 7.6% | 2010-01 to 2026-10 |
| BR | n/a (nan) | n/a | 4.6% (2026-09-30) | n/a | n/a | BB / Ba1 | n/a | n/a | n/a | n/a / n/a | none |
| ZA | 8.94% (2026-10-31) | 7.10% | 3.2% (2025 (World Bank)) | 5.73% | 3.02% | BB / Ba2 | 9.6% | 4.5% | -4.7% | 1.5% / 7.3% | 2010-01 to 2026-10 |
| ID | 7.01% (2024-12-31 (stale)) | 5.46% | 3.3% (2026-09-30) | 3.73% | 2.14% | BBB / Baa2 | 6.2% | 1.6% | -4.3% | -0.9% / 3.7% | 2012-02 to 2024-12 |
| IN | 7.38% (2026-10-31) | 5.61% | 5.6% (2026-09-30) | 1.81% | 1.17% | BBB / Baa3 | 8.1% | 3.9% | -3.9% | 6.1% / 2.4% | 2012-01 to 2026-10 |
| PL | 6.32% (2026-10-31) | 3.88% | 2.4% (2025-12-31) | 3.92% | 2.69% | A- / A2 | 4.1% | 2.1% | -1.9% | 4.6% / -0.0% | 2010-01 to 2026-10 |
| HU | 5.57% (2026-10-31) | 5.50% | 3.3% (2025-12-31) | 2.27% | 3.04% | BBB- / Baa2 | 6.1% | 2.6% | -3.3% | 6.9% / -1.1% | 2010-01 to 2026-10 |
| CZ | 5.24% (2026-09-30) | 3.86% | 2.1% (2025-12-31) | 3.13% | 0.52% | AA- / Aa3 | 1.9% | 0.9% | -0.9% | 2.7% / -0.7% | 2010-01 to 2026-09 |
| CL | 6.05% (2026-10-31) | 4.64% | 4.2% (2025 (World Bank)) | 1.84% | 2.03% | A / A2 | 5.2% | 1.0% | -4.0% | 4.2% / -1.8% | 2010-01 to 2026-10 |
| CO | 13.25% (2026-10-31) | 10.25% | 6.3% (2026-09-30) | 6.96% | 3.61% | BB / Baa3 | 7.1% | 4.3% | -2.6% | 4.5% / 4.1% | 2010-01 to 2026-10 |
| TR | 35.84% (spot 2026-10-23) | n/a | 30.9% (2025-12-31) | 4.95% | n/a | BB- / Ba3 | n/a | n/a | n/a | n/a / n/a | none |

Cross-check against EMLC: the equal-weight model basket returned 3.4% a year in USD vs EMLC 0.9% (2010-08 to 2026-10, correlation 0.91); in-sample 3.7% vs 1.0%, OOS 3.1% vs 0.9%. Caveats: monthly-average yields smooth the series; a 10y bond has more duration than EMLC (about 5y); no fees, bid-ask or withholding tax; ID ends 2024-12; IN starts 2012.

Brazil: the OECD long-term rate in yields.csv (BR_10Y) follows the TJLP/TLP policy lending rate (6.0% in 2010-11, 5.0% in 2013-14, 7.5% in 2016), not a traded 10y bond yield, so it is excluded (research/candidates/assumptions_em_bonds.py EXCLUDED_YIELD_SERIES) and no Brazilian return is shown. Turkey's 3-month series ends 2008 and is not used.

Not checked: debt/GDP and current account (not in the repo data). Chart: `reports/candidates/charts/em_bonds_countries_realyield.png`.
