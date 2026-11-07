# Overlay screener notes (task 2.1, derivatives overlay type)

Written 2026-11-07. Companion to `overlays.csv` (15 variants). No backtesting, no
price histories downloaded, FRED not called. Anything marked **unverified** was not
confirmed in this session and must be checked by the fetch (task 2.2) or the
Phase 3.5 analyst before it goes into `research/config.py`.

## 1. Volatility risk premium (VRP): evidence

| Claim | Number | Source (date read) | Strength |
|---|---|---|---|
| S&P 500 implied minus realized vol, 1990-2018 | average VIX 19.3%, average realized 15.1%, premium 4.2 points | Bondarenko / Cboe white paper, posted 2019-05-29: https://www.cboe.com/insights/posts/white-paper-shows-volatility-risk-premium-facilitated-higher-risk-adjusted-returns-for-put-index (read 2026-11-07) | Good for SPX 30-day options; ends 2018, so the OOS period is not covered |
| PUT index vs S&P 500, same white paper | PUT annualized vol 9.95% vs 14.93%; skew -2.09 vs -0.81; PUT +1,835% from 1986-06-30 to 2018-12-31 (PPUT +708%) | same page | Cboe-authored; index values before launch are back-calculated |
| Put selling returns | Summaries report 39% per month (ATM) and 23% per month Jensen alpha for selling index puts (Bondarenko 2014, Quarterly Journal of Finance); the two figures use different measures | Secondary summaries only: https://www.cxoadvisory.com/equity-options/is-40-per-month-shorting-index-puts-a-fair-return ; paper listing https://ideas.repec.org/a/wsi/qjfxxx/v04y2014i03ns2010139214500153.html | Weak: I did not read the paper; do not put these numbers in the report without checking them |
| Covered call decomposition | Short-volatility exposure had a realized Sharpe ratio near 1.0 and contributed under 10% of risk and about 2% annualized return; equity-reversal exposure was about 25% of the ATM covered call's risk with little reward | Israelov and Nielsen, "Covered Calls Uncovered", Financial Analysts Journal 71(6), 2015: https://www.aqr.com/insights/research/journal-article/covered-calls-uncovered ; summary https://quantpedia.com/covered-calls-uncovered/ (read 2026-11-07) | Moderate; the paper's sample period and implied-minus-realized spread were not retrievable (the PDF fetch returned binary) |
| BXM gross premium | about 1.7% per month since May 2006 (gross premium, not return) | Cboe, post dated 2021-07-20: https://www.cboe.com/insights/posts/benchmark-indices-series-income-generation-and-smoother-returns-with-cboes-bxm-bxmd-put-and-cmbo-indices | Good as a calibration target for premium level |
| Variance risk premium on indices is negative | sign confirmed for S&P 500, S&P 100, DJIA; size not retrieved | Carr and Wu, Review of Financial Studies 22(3), 2009, 1311-1341: https://econpapers.repec.org/RePEc:oup:rfinst:v:22:y:2009:i:3:p:1311-1341 | Sign only |
| Protection stays expensive even at low IV | qualitative | CFA Institute digest of a 2015 study: https://rpc.cfainstitute.org/research/cfa-digest/2015/12/still-not-cheap-portfolio-protection-in-calm-markets-digest-summary | Qualitative |

**Where evidence is weak:** I found no verified VRP number for the Nasdaq-100, for
single stocks, for MSCI EM / EFA ETF options, or for the post-2018 period. For SPX
the model should not assume a VRP at all: `^VIX` (already in the fetch list) is the
implied vol, and the realized vol is computed from the S&P 500 series, so the
premium is measured in-sample (2010-2017) and OOS. For every other underlying,
the VRP in vol points {0, 2, 4, 6} is a free parameter, shown as a sensitivity, and
must not be presented as a finding.

**Calibration rule (binding, method.md sections 2 and 12):** skew offset and any VRP
add-on are fitted to the CBOE index returns using 2010-01 to 2017-12 only, frozen in
`research/config.py`, then run OOS 2018-01 to 2026-10. Fitting on the OOS window
would invalidate every overlay result.

## 2. CBOE index definitions and start dates

Start dates are the first row of the daily CSV, checked 2026-11-07 from this PC
(only first row, last row and line count were read; nothing was saved to `data/`).
Last row of each file is 2026-11-06.

| Index | Definition | CSV first row | Lines | Notes |
|---|---|---|---|---|
| BXM | S&P 500 buy-write, sells at-the-money SPX calls monthly | 2002-03-22 | 6,196 | The data request said "2002"; confirmed. Not 1986 |
| BXMD | 30-delta buy-write (less premium than BXM, keeps more upside) | 1986-06-20 | 10,170 | Index value 100.00 on the first rows |
| PUT | Sells SPX puts monthly against T-bills | 1991-03-04 | 5,002 | Sparse in early years (gaps in 1991-1994 rows seen) |
| PPUT | Long S&P 500 plus a monthly 5% OTM SPX put | 1986-06-30 | 10,164 | Indexology blog says PPUT was introduced 2015; earlier values are back-calculated (secondary source) |
| CLL | Long S&P 500, buys a quarterly 95% put, sells a monthly 110% call | 2008-08-26 | 4,539 | Indexology blog says introduced 2008; no data for 2000-2008 |

Definitions: Cboe posts https://www.cboe.com/insights/posts/benchmark-indices-series-hedging-downside-exposure-with-pput-cll-and-cllz-indices (2021-07-15) and https://www.cboe.com/insights/posts/benchmark-indices-series-income-generation-and-smoother-returns-with-cboes-bxm-bxmd-put-and-cmbo-indices (2021-07-20). The Cboe index dashboard pages returned no methodology text; the formal methodology documents were not found, so exact roll rules (settlement prices used, ex-dividend handling) are **unverified**. A Callan report dates BXM calculation to 1988 and the BXM announcement to 2002, which conflicts with the 1986 back-test date quoted elsewhere, so 1986-era BXM values should not be used. The tickers at https://www.cboe.com/us/indices/benchmark_indices/ confirm the names: BXM, BXMD, PUT, PPUT, CLL.

Implication: in-sample 2010-2017 is covered by all five indices; the GFC (2008) is covered
only by BXM, BXMD, PUT, PPUT and, for the tail of 2008, by CLL.

## 3. Realized fund proxies (yfinance info, 2026-11-07)

| Ticker | Fund | Inception (first trade) | Expense ratio | Months before 2018-01 | Use |
|---|---|---|---|---|---|
| XYLD | Global X S&P 500 Covered Call ETF | 2013-06-24 | 0.60% | 54 | Cross-check of BXM-style (under the 60-month rule, so cross-check only) |
| QYLD | Global X NASDAQ 100 Covered Call ETF | 2013-12-12 | 0.60% | 48 | Cross-check of Nasdaq buy-write |
| KNG | FT Cboe Vest S&P 500 Dividend Aristocrats Target Income ETF | 2018-03-27 | 0.74% | 0 | OOS only; a partial overwrite, not a clean proxy |
| JEPI | JPMorgan Equity Premium Income ETF | 2020-05-21 | 0.35% | 0 | OOS only; actively managed with equity-linked notes, not a clean proxy |
| JEPQ | JPMorgan Nasdaq Equity Premium Income ETF | 2022-05-04 | 0.35% | 0 | OOS only |
| PUTW | WisdomTree PutWrite fund | launched 2016 per a press release (date not verified) | 0.44% per one profile page | n/a | **Yahoo returned 404 on 2026-11-07; delisting note on one aggregator (2025-07-24) conflicts with other pages.** Drop from the fixed fetch list or accept a failed fetch. Even if alive it has under 60 pre-2018 months |
| RYLD / QYLG / XYLG | Russell 2000 / growth variants | 2019-04-22 / 2020-09-23 / 2020-10-05 | 0.60% / 0.35% / 0.35% | 0 | Not used |

Tracking indices for XYLD and QYLD (BXM and a Nasdaq-100 buy-write) are from my
recollection of the Global X fund descriptions, not re-verified. Fund returns include the
expense ratio, CBOE indices do not, so compare on a gross-of-fee basis or subtract 0.60%.

## 4. FX 3-month rate availability (for covered interest parity)

FRED was **not called** (rate-limited; instruction). IDs below are the OECD naming
pattern `IR3TIB01<CC>M156N` from the data request; existence and end dates are
**unverified** unless noted. The only direct evidence this session: a search shows
the Indonesia pages `IR3TIB01IDM156N` (monthly) and `IR3TIB01IDA156N` (annual, last updated
2025-11-17, one 2024 value of about 5.43%) exist (https://fred.stlouisfed.org/series/IR3TIB01IDM156N).
US leg: `TB3MS` (monthly) is fixed in the data request.

| Currency | Series to try | Confidence | Fallback if absent |
|---|---|---|---|
| MXN | IR3TIB01MXM156N | probable | Banxico TIIE 28-day / Cetes via banxico.org.mx (manual) |
| BRL | IR3TIB01BRM156N | uncertain | Central Bank of Brazil CDI / Selic via bcb.gov.br (manual); onshore CDI vs offshore NDF differ |
| ZAR | IR3TIB01ZAM156N | probable | SARB / JIBAR 3m (manual) |
| INR | IR3TIB01INM156N | uncertain | RBI 91-day T-bill (manual); NDF market, CIP poor |
| IDR | IR3TIB01IDM156N | page exists (above); end date unknown | Bank Indonesia JIBOR (manual) |
| PLN | IR3TIB01PLM156N | probable | NBP WIBOR 3M (manual) |
| HUF | IR3TIB01HUM156N | probable | BUBOR 3M (manual) |
| CZK | IR3TIB01CZM156N | probable | PRIBOR 3M (manual) |
| CLP | IR3TIB01CLM156N | uncertain | Banco Central de Chile (manual) |
| COP | IR3TIB01COM156N | uncertain | Banco de la Republica IBR (manual) |
| THB | none expected on FRED | no free FRED series | Bank of Thailand policy / THBFIX (manual); otherwise leave unhedged and say so |
| MYR | none expected on FRED | no free FRED series | Bank Negara Malaysia OPR (policy rate proxy, manual); otherwise leave unhedged |
| TRY | IR3TIB01TRM156N | uncertain, data request notes FRED Turkish yield series end 2008-2010 | none free; spot quotes only, flagged |

Fallback source for policy-rate proxies, **unverified**: BIS central-bank policy-rate
dataset. A policy rate is not a 3-month forward-implied rate; label such rows
"policy-rate proxy" and do not mix them silently with market rates.

Known limits of the CIP model: (a) CIP deviations exist, especially in non-deliverable
markets (BRL, INR, IDR, CLP, COP, TWD, KRW), where offshore NDF-implied yields differ from onshore money-market rates, and
no free basis data exist; (b) 3-month interbank rates include a credit/liquidity component;
(c) the model gives the expected forward points, not a bank's actual quote with its own spread
(5 bps per roll is the charge in method.md section 10).

## 5. Practical feasibility for a $100,000 account

Contract sizes (SPY and QQQ prices are previous closes from yfinance info, 2026-11-07;
treat as approximate):

| Instrument | Notional | Source |
|---|---|---|
| 1 SPY option (100 shares) | ~$73,300 at SPY 733 (the brief's $65,000 is outdated) | yfinance 2026-11-07 |
| 1 QQQ option | ~$64,700 at QQQ 647 | yfinance 2026-11-07 |
| 1 MES (Micro E-mini S&P 500) | $5 x index = ~$36,700 if the index is ~7,330 (derived from SPY x 10, approximate) | MES $5/pt: https://tradezero.com/en-us/support/questions/what-are-the-contract-specifications-for-the-micro-e-mini-s-and-p-500-mes-tradezero-america |
| MES margin | conflicting: $690 initial (CME FAQ, undated) vs $2,862.88 (TradeZero, as of 2026-09-16) | https://www.cmegroup.com/education/frequently-asked-questions-micro-e-mini-equity-index-futures.html ; TradeZero link above |
| CME Micro Nikkei USD | 0.5 x Nikkei 225; tick 5 points | https://www.benzinga.com/markets/equities/24/10/41116668/cme-group-expands-nikkei-futures-offerings-boosts-japanese-equity-derivatives (Oct 2024) |
| ICE MSCI EM futures (MME) | $50 x index; tick 0.10 = $5 | https://www.ice.com/api/productguide/spec/31196851/pdf |
| MNQ, Euro Stoxx 50, MSCI EAFE, EM currency futures sizes | not confirmed this session | to verify |

What this means for the actual account (sleeves from the brief: ~$55k stocks of which
3 US growth stocks perhaps $15k-$30k, ~$35k EM bonds, ~$10k other):

- **Covered calls on the 3 US stocks: impossible.** 100 shares of a $5k-$10k position is
  only possible if the stock is under $50-$100, and option contracts do not divide.
- **Covered calls on index ETFs:** the SPY lot ($73,300) exceeds the US sleeve. The
  honest route is to model the overlay as a fractional overwrite of the sleeve
  (modelling convenience), then mark it "implementable only with a mini-index option or
  a larger account" (XSP existence and size **unverified**).
- **Protective puts and collars:** one SPY put hedges ~133% of a $55k equity sleeve, so a
  50% hedge is not possible with whole contracts. The put would also be an S&P hedge
  on an equity sleeve that is mostly non-US (basis risk). Puts on EFA/EEM would match better but their
  contract sizes were not checked.
- **Option approval:** collars and covered calls need only basic option approval; cash-secured
  puts need the full cash, so put-writing consumes ~$73,300 per SPY-sized put.
- **FX forwards:** hedged notional is at most ~$17,500 x 50-100% (the local-currency part of the
  bond sleeve). Bank forwards and NDFs are not normally open to a retail brokerage account (not verified for a
  specific broker); a 10+ currency hedge cannot be built from futures. The only
  practical version is hedging MXN/BRL/ZAR with CME FX futures, with basis risk.
- **Futures for rebalancing:** a $5k trade is one-seventh of an MES. At 5 bps one-way
  on ETFs the cost saved is about $2.50 per trade. Not worth it.
- **Interest-rate swaps:** OTC; need an ISDA agreement. Not available to this account (not verified for a
  specific broker). Treasury futures proxy only.

## 6. What cannot be tested honestly, and why

1. **Real option prices.** No free history. Every option overlay is Black-Scholes with ^VIX or
   realized vol plus assumed skew, checked against CBOE indices (which exist only for SPX).
   For Nasdaq-100, single stocks and EFA/EEM options the model is unchecked.
2. **Skew and term structure.** No free history (a `^SKEW` and `^VIX3M` pull through Yahoo is
   untested). Skew offsets are fitted parameters, not observations.
3. **Single-stock covered calls.** No proxy, no VRP source, and unimplementable at this size.
4. **Early-exercise, dividends, discrete strikes.** Not modelled: European exercise, continuous
   strike, dividend yield smoothed.
5. **EM FX forwards.** CIP rates for THB, MYR (and probably TRY) have no free series; NDF currencies break CIP;
   the fund's currency weights are as of the factsheet, so applying them to history is a look-ahead flag.
6. **Swaps.** No free swap curve history was retrieved; only a Treasury-beta proxy is possible.
7. **Futures.** Commission, slippage and basis are assumptions with no sourced figure.
8. **Short OOS stress.** CBOE index back-history (PPUT, CLL) is back-calculated before launch.
   The only real live record of the strategies in the OOS window (2018-2026) is the indices themselves
   plus XYLD/QYLD; JEPI, JEPQ and KNG are different strategies.
9. **VRP in the OOS window.** The 4.2-point figure ends in 2018; whether it persisted in 2018-2026 must be measured, not assumed.

## 7. Assumptions to write into `research/config.py` (names suggested)

`OVERLAY_OPTION_HALF_SPREAD = 0.01` (of premium), `OVERLAY_OPTION_FEE_PER_CONTRACT = 0.65`,
`OVERLAY_FX_ROLL_COST_BPS = 5`, `OVERLAY_RF_SERIES = "TB3MS"`, `OVERLAY_IV_SOURCE = {"spx": "^VIX",
"nasdaq": "^VXN or realized + VRP", "other": "realized 63d + VRP"}`, `OVERLAY_VRP_POINTS_GRID =
(0, 2, 4, 6)`, `OVERLAY_SKEW_PARAMS` (fitted 2010-2017, frozen), `OVERLAY_CALIBRATION_END = "2017-12-31"`,
`OVERLAY_TENORS`, `OVERLAY_DELTAS`, `OVERLAY_HEDGE_RATIOS`, `OVERLAY_OVERWRITE_RATIOS`,
`OVERLAY_FX_RATE_SERIES` (country to series id plus "policy-rate proxy" flag), `OVERLAY_FUT_COST`
(1 tick plus commission, unsourced), `OVERLAY_CONTRACT_NOTIONAL_NOTE` (SPY ~$73,300 at 733 on 2026-11-06).

## 8. Suggested data-request edits (for task 2.2)

- Remove PUTW from the fixed overlay proxies (Yahoo 404) or accept the failed fetch.
- Add `^VXN`, `^VIX3M`, `^SKEW`, `^VXEEM` to the Yahoo index list (existence **unverified**, failures non-fatal).
- Add CBOE files (BXM, BXMD, PUT, PPUT, CLL) as already specified; no changes.
