# Method (pre-registered)

**Status:** committed before any candidate was backtested. Nothing below may be
changed after results are seen except through the change log at the end,
and any logged change forces a rerun of every candidate under the new rule.

Project: AFMBA622 Global Portfolio Research, UMass Boston. Client brief:
$100,000, 7-year horizon, growth plus security, mostly passive with periodic
adjustments, quantitative (fundamental plus technical), at least 70% non-US,
roughly 55% stocks / 35% bonds / 10% other, derivatives allowed.

## 1. Objective in numbers

| Item | Rule |
|---|---|
| Base currency, capital | USD, $100,000 |
| Horizon | 7 years from the report date (Nov 2026 to Nov 2033) |
| "Growth" target | median 7-year ending value at least $145,000 (about 5.5%/yr nominal, 3%/yr real at 2.5% inflation) in the forward Monte Carlo |
| "Security" budget | maximum drawdown no worse than -25% (monthly, USD) in the walk-forward backtest; probability of a nominal loss over 7 years at most 10%; probability of beating US CPI at least 75%; worst calendar year no worse than -20% |
| Implied risk | roughly 9-13% annual volatility: a moderate risk tolerance, between a 60/40 and a 40/60 |
| Judging metric | out-of-sample Sharpe ratio and information ratio first; max drawdown, inflation resilience and FX risk as tie-breakers |

If the optimized portfolio cannot meet both the growth target and the
security budget, the security budget wins and the shortfall is reported.

## 2. Sample split and minimum history

- **In-sample:** 2010-01-01 to 2017-12-31. All screens, signal tests, and the
  shortlist use only data before 2018-01-01.
- **Out-of-sample (OOS):** 2018-01-01 to the last available month (Oct 2026).
  Used once, to judge candidates and signals. The walk-forward portfolio
  backtest re-estimates on a trailing window, so every portfolio return is
  OOS by construction.
- **Minimum history:** a candidate needs at least 60 months of returns before
  2018-01-01 to be scored (listed on or before 2012-12-31). Anything with less
  than 120 months in total is flagged "short history" in every table.
  Instruments listed after 2012 (for example Shopify 2015, Ferrari 2016,
  Alibaba 2014, SGOV 2020, DBMF 2019) are excluded from the shortlist and may
  only appear as "not testable" notes.
- Monthly total returns (dividends and coupons reinvested, Yahoo adjusted
  close) for all metrics; daily prices for the technical signals and for the
  walk-forward optimizer.

## 3. Non-US rule (70% of total portfolio value)

An asset's non-US share:

| Asset | Non-US share |
|---|---|
| Stock | 1.0 if the company's headquarters/domicile is outside the US (an ADR or US listing of a foreign company counts as non-US; MercadoLibre, Uruguay, counts as non-US), else 0.0 |
| Bond fund | share of holdings whose issuer is non-US (EM sovereign and corporate funds: 1.0, even when USD-denominated) |
| Equity fund | share of holdings domiciled outside the US, from the fund's latest factsheet (source and date recorded) |
| Gold, commodities, USD cash, US TIPS, US REITs | 0.0 (no foreign country; counted conservatively against the 30% US/neutral room) |
| Global ex-US REITs, international inflation-linked bonds | by holdings as for funds |
| Derivative overlay | the share of its underlying |

Rule check: non-US share of target weights at least 0.70 at every rebalance
date. Drift between rebalances is reported; a drift below 0.68 triggers a
rebalance. The conservative gold treatment is a default: John is asked at
check-in 1, and if he treats gold/commodities as neutral the rule is applied
to the remaining assets instead and both results are shown.

## 4. Screening universes (long lists are built from these, then hard screens apply)

| Position type | Universe | Hard screens (in-sample data only) |
|---|---|---|
| US growth stocks (3 spots) | Current Nasdaq-100 members, plus the 50 largest S&P 500 Growth index members, plus a **faded-leaders list**: companies that were top-20 Nasdaq-100 or S&P 500 Growth names at some point in 2010-2015 and are still listed (survivorship check). Delisted names are listed with their exit date and reason but cannot be priced. | US domicile; listed by 2012-12-31; market cap at least $10B today and at least $2B at 2017-12-31; average daily traded value at least $20M; 3-year revenue CAGR at 2017-12-31 at least 8% (point-in-time, SEC EDGAR) |
| International growth stocks (3 spots) | Largest 120 non-US companies by market cap with a growth profile (3-year revenue CAGR at least 8%), from developed ex-US and EM markets, local listing preferred (ADR added as a cross-check). Must include names from Europe, Japan, Korea/Taiwan, China/HK, India, LatAm and Canada/Australia, and at least 8 EM-domiciled names. | Non-US domicile; local listing by 2012-12-31; market cap at least $10B today; traded value at least $10M/day; revenue CAGR rule as above where point-in-time data exists (SEC 20-F filers), else current 4-year history with the flag "fundamentals not point-in-time" |
| EM bonds (4 spots) | All US-listed EM bond ETFs and the major open-end EM bond funds: hard-currency sovereign (EMB, PCY, VWOB; PREMX, FNMIX, PEBIX, TGEIX), local-currency sovereign (EMLC, LEMB, EBND, ELD; PELBX), EM corporate and high yield (CEMB, EMCB, EMHY, HYEM), short-duration/blended (DBLEX and peers). Country-level yield series (FRED, where available) support the country analysis but individual bonds are not priced. | At least 60 months by 2017-12-31; AUM at least $200M; expense ratio at most 1.00%; daily liquidity |
| Other (1-3 spots, 10% sleeve) | Gold (GLD, IAU), silver (SLV), broad commodities (DBC, GSG, PDBC), natural resources (GUNR), global ex-US REITs (VNQI, RWX), global infrastructure (IGF), US TIPS (TIP, SCHP), international inflation-linked (WIP), cash (BIL). Bitcoin and managed-futures ETFs are excluded for history shorter than the rule. | At least 60 months by 2017-12-31; AUM at least $200M; expense at most 0.75% |
| Derivatives overlays (tested, kept only if they help) | Covered calls on the US growth sleeve (CBOE BXM/BXMD indices and XYLD/QYLD as realized proxies; Black-Scholes model on realized vol plus a stated volatility risk premium); protective puts and collars on the equity sleeve (CBOE PPUT and CLL); FX forwards on EM local-currency bond exposure (covered interest parity from short-rate differentials); index futures for rebalancing (cost model only). | Overlay must have a modelled history over the full OOS period; every assumption written in `research/config.py` |

## 5. Fundamental screens (decided now)

Scored as percentile ranks within the position type, at 2017-12-31 for the
in-sample ranking and at the latest data for the forward thesis. Point-in-time
rule: a fiscal-year value is usable from its SEC filing date (EDGAR
`companyfacts`), or 90 days after fiscal year end where only statement dates
exist.

**Stocks**

| Group (weight in fundamental score) | Measures |
|---|---|
| Growth (40%) | 3-year revenue CAGR; 3-year net income CAGR |
| Quality (30%) | return on invested capital (or ROE for financials); operating margin and its 3-year change; net debt / EBITDA (lower better; skipped for financials) |
| Valuation (30%) | free-cash-flow yield; trailing P/E relative to the company's own 5-year median; for the forward thesis only, the DCF implied return from `research/dcf.py` and the Grinold-Kroner estimate |

**Bond funds** (weights): carry 40% (yield to maturity minus expected FX loss
from relative PPP and UIP for local-currency funds, minus the expense ratio);
credit and country quality 30% (average rating, country concentration, issuer
debt/GDP, current account, inflation, real yield); cost and liquidity 15%;
diversification 15% (correlation with the equity sleeves' benchmarks).

**Other sleeve**: inflation beta (regression of monthly returns on changes in
US CPI inflation, plus performance in 2021-12 to 2022-10) 40%; correlation
with ACWX and EMB 30%; carry/roll cost and expense ratio 30%.

## 6. Technical screens (decided now) and how they are validated

Computed monthly from daily USD total-return prices up to the prior month end.

| Code | Signal | Higher score when |
|---|---|---|
| T1 | 12-1 month momentum (months t-12 to t-2) | higher |
| T2 | Price above its 200-day moving average | true |
| T3 | 6-month return relative to the position type's benchmark | higher |
| T4 | 12-month realized volatility | lower |
| T5 | Distance below the 52-week high | smaller |

**Validation (pre-registered):** within each position type's long list,
each month rank by the signal and hold the top tercile equal-weighted versus
the long-list equal-weight, rebalanced monthly, 10 bps one-way cost. A signal
is **kept** if its OOS information ratio is above zero **and** the t-statistic
of its OOS active return is above 1.0. Signals that fail are dropped from the
technical score and reported as "did not add value out of sample". The
technical score is the mean percentile rank of the kept signals; if none are
kept for a type, the technical weight in the rubric is redistributed to the
other components pro-rata (rule fixed now).

## 7. Scoring rubric (fixed now; percentile rank within type times weight)

| Component | Weight | Measured as |
|---|---|---|
| OOS Sharpe ratio (USD) | 20 | monthly, vs BIL |
| OOS information ratio vs type benchmark | 15 | monthly |
| OOS maximum drawdown | 10 | less negative is better |
| Consistency | 10 | share of rolling 36-month windows (full sample) with IR above zero |
| Diversification | 10 | lower average OOS correlation with the other sleeves' benchmarks (IVW, EFG/EEM, EMB, GLD, excluding own) |
| Inflation resilience | 5 | total return 2021-12-31 to 2022-10-31 and beta to CPI changes |
| Liquidity and cost | 5 | traded value, expense ratio, bid-ask estimate |
| Forward 7-year expected return (USD) | 15 | consensus of at least two methods (CAPM, DCF, Grinold-Kroner, yield-based, Monte Carlo median) |
| Fundamental score | 5 | section 5, latest data |
| Technical score | 5 | section 6, kept signals only |
| **Total** | **100** | |

Tie-breakers in order: smaller OOS max drawdown, smaller FX share of USD
variance, lower cost. Picks are the top 3 (stocks), 4 (EM bonds) and 1-3
(other) per type after review; the next 1-2 are runners-up.

Multiple testing: with 20-40 names screened per type the best OOS Sharpe is
partly luck. Each candidate reports the deflated Sharpe ratio (Bailey and
Lopez de Prado, N = long-list size) and t-statistics on alpha and IR, and each
type reports the Spearman rank correlation between in-sample and OOS scores.
A type whose in-sample ranking has no OOS predictive value (rank correlation
at or below zero) is reported as such and the picks lean on the forward
models and drawdown, not on the OOS ranking.

## 8. What drops a candidate

1. Fewer than 60 months of history before 2018, or fails a hard screen.
2. OOS Sharpe below its type benchmark **and** OOS information ratio below
   zero (may remain a runner-up only if the type has fewer than 5 survivors).
3. A reviewer "fail" on a load-bearing claim (look-ahead, survivorship,
   missing dividends or fees, wrong currency, non-reproducible number) that
   the analyst cannot fix.
4. Any number that cannot be reproduced from committed code and data.
5. A derivative overlay is dropped if it does not raise the portfolio's OOS
   Sharpe **or** reduce its max drawdown by at least 2 percentage points net
   of its costs.

## 9. Benchmarks and risk-free rate

| Scope | Benchmark id | Definition |
|---|---|---|
| US growth stocks | `IVW` | iShares S&P 500 Growth ETF (QQQ also shown) |
| International growth stocks | `EFG_EEM_5050` | 50% EFG (MSCI EAFE Growth) + 50% EEM (MSCI EM), rebalanced monthly; ACWX also shown; the home index in local currency for the local-return view (^N225, ^FCHI, ^GDAXI, ^KS11, ^TWII, ^HSI, ^NSEI, ^GSPTSE, ^AXJO, ^BVSP, ^MXX) |
| EM bonds, hard currency and sleeve total | `EMB` | iShares JPM USD EM Bond ETF (tracks EMBI Global Core, the investable twin of EMBI Global Diversified) |
| EM bonds, local currency | `EMLC` | VanEck JPM EM Local Currency Bond ETF (GBI-EM) |
| Other sleeve | `GLD` | gold, the proposal's archetype for the sleeve; US CPI + 2% also shown |
| Whole portfolio | `GUIDE_BENCH` | 55% ACWX / 35% EMB / 10% GLD, rebalanced quarterly |
| Context | `SIXTY_FORTY` | 60% SPY / 40% AGG (and 60% ACWI / 40% AGG shown) |
| Risk-free | `BIL` | SPDR 1-3 month T-bill ETF total return (monthly); TB3MS (FRED) inside the research models |

## 10. Portfolio construction rules (Phase 5, fixed now)

- Long-only base positions; derivatives only as overlays on positions held.
- Non-US share at least 70% (section 3).
- Sleeve weights within +/-10 percentage points of 55% stocks / 35% bonds /
  10% other; any drift beyond the tolerance must be justified in writing and
  the guideline portfolio shown alongside.
- Position counts 3 US growth stocks, 3 international growth stocks, 4 EM
  bond funds, 1-3 other. Single stock at most 10% of the portfolio and at
  least 3% if held; single fund at most 15%; single "other" asset at most 10%.
- Rebalance quarterly (also tested: semi-annual, annual, monthly). Estimation
  window 3 years of daily data (also tested: 5 years). Ledoit-Wolf covariance
  and shrunk means as in `portfolio/optimize.py`.
- Costs: 5 bps one-way on US-listed ETFs and stocks, 15 bps on foreign local
  shares, 0 bps on open-end funds (their fee is in the NAV); option overlays
  pay half the bid-ask spread, set to 1% of premium, plus $0.65 per contract;
  FX forwards 5 bps per roll.
- Guideline portfolio for comparison: exact 55/35/10, equal weight inside
  each sleeve, same rebalance schedule.

## 11. Stress windows (monthly, USD)

| Name | Window |
|---|---|
| GFC 2008 | 2007-10-31 to 2009-02-28 |
| Taper tantrum 2013 | 2013-04-30 to 2013-08-31 |
| Covid crash 2020 | 2020-01-31 to 2020-03-31 |
| Inflation and rate shock 2022 | 2021-12-31 to 2022-10-31 |
| Strong USD | average monthly return in months when the broad dollar index (FRED DTWEXBGS) rose by at least 2%; plus the 2014-06 to 2015-03 and 2021-06 to 2022-09 episodes |

## 12. Evidence standards (binding on every subagent)

- Out of sample means the number was not used to pick the method, the
  shortlist or the weights. In-sample and OOS are always shown side by side.
- Signals and weights at date t use data to t-1 only; fundamentals are lagged
  to their filing date.
- Total-return series net of fund fees and the trading costs above.
- Survivorship: the faded-leaders list is screened with the same rules, and
  the report shows how it did.
- Deflated Sharpe or t-stats on every ranking table.
- No conclusion from less than 60 months; under 120 months flagged.
- Every number reproducible from committed code and data with a stated
  command; every web fact carries a source link and date.
- Synthetic data is never a result.
- "The guideline portfolio was as good as the optimized one" is a valid
  finding and is reported as such if found.

## 13. Change log

| Date | Section | Change | Reason | Rerun done |
|---|---|---|---|---|
| 2026-11-07 | 6 | Clarification, no rule change: T4 = standard deviation of the last 252 daily USD returns; T5 = price / 252-day high minus 1; the top tercile is the top round(n/3) names; T2 (yes/no) holds every name above its 200-day average; the 10 bp cost is charged on the tercile portfolio's turnover only, the equal-weight long list is gross; a name counts in month t only if it has a return that month; "long list" for validation = all candidates plus faded leaders. | Implementation choices made in `research/screen/` before any scoring ran. | n/a (no results yet) |
| 2026-11-07 | 5 | Clarification: fiscal year = year of period end; point-in-time value = latest filing on or before as_of; ROIC = operating income x (1 - tax) / (debt + equity - cash) with a 25% tax rate when the effective rate is missing; market cap at 2017-12-31 is rebuilt from SEC share counts and unadjusted prices (Yahoo prices are split- and dividend-adjusted, so both are undone). For US stocks with no point-in-time revenue the growth screen is "not checked", never substituted with current data. TSMC's first SEC XBRL filing is 2018, so at 2017-12-31 it is scored on current statements and flagged. | Same. | n/a |
| 2026-11-07 | 7 | Clarification: a rubric component missing for one name has its weight redistributed pro-rata for that name (same rule as the technical weight). Deflated Sharpe uses V = 1/(T-1) for the trials' Sharpe variance unless measured. | Same. | n/a |
| 2026-11-07 | 4 | Clarification: WTMF (managed futures, inception 2011) is a candidate for the other sleeve. The method excluded managed-futures ETFs "for history shorter than the rule", and WTMF meets the rule, so the exclusion does not apply to it. | Screener found it passes every hard screen. | n/a |
| 2026-11-07 | 4 | Clarification: faded leaders are exempt from the market-cap rule (only candidates must be at least $10B); the whole point of the group is that they shrank. | Screener had applied the cap to them. | n/a |
