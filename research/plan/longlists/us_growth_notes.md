# US growth stock long list: build notes

Screener: US growth stocks (3 spots). Built 2026-11-07. File: `us_growth.csv` (115 rows: 87 candidate, 8 faded_leader, 20 not_testable). No revenue growth or score computed; index membership is the growth definition.

## How the list was built
1. Current Nasdaq-100 members taken from Wikipedia (page lists 100 names; infobox says 101). Names were mapped to tickers by hand.
2. S&P 500 Growth top 50: the issuer pages (SSGA, stockanalysis.com) show only the top 10 or 25, and the full file is a download or behind a paywall. I used the ChartRow SPYG holdings page, ranks 1-50 (SPYG tracks the S&P 500 Growth index). ChartRow weights are ESTIMATES rolled forward from the fund's 2026-06-30 SEC filing at 2026-11-06 prices, so ranks near 40-50 (weights 0.25-0.5%) are approximate. Ranks 1-25 broadly agree with the SSGA/stockanalysis lists dated 2026-11-05. Alphabet is one row (GOOGL).
3. Faded leaders: see below.
4. yfinance `Ticker.info` used only for country, currency, exchange, marketCap and first trade date. The field is `firstTradeDateMilliseconds`; `firstTradeDateEpochUtc` named in the brief is absent in yfinance 1.7.0. Market cap is the 2026-11-07 value. No price history downloaded.
5. EDGAR CIKs from the SEC ticker file (User-Agent sent as required), zero-padded to 10 digits. The saved file was a ticker-to-CIK mapping; spot checks AAPL 320193 and NVDA 1045810 are correct. All 115 rows have a CIK.
6. Rules: role=candidate if US domicile (yfinance country), first trade on or before 2012-12-31, market cap at least $10B. role=not_testable if US and large but first trade after 2012-12-31. Faded leaders carry role=faded_leader and skip the market-cap rule (all are above $10B anyway).

Count note: the brief aimed for 30-40 candidates. The union of the two index universes gives 87 that pass the three hard rules. I did not trim arbitrarily; the later method.md section 4 screens (market cap at 2017-12-31, traded value, 3-year revenue CAGR) will cut it. A hard cap can be applied if wanted.

## Sources (accessed 2026-11-07)
- Nasdaq-100 members: https://en.wikipedia.org/wiki/Nasdaq-100 (mentions the April 2011 special rebalance; no 2010-2016 change table on the page).
- S&P 500 Growth top 50: https://chartrow.com/quote/spyg/holdings (estimates, see above). Cross-checks: https://stockanalysis.com/etf/spyg/holdings/ and https://stockanalysis.com/etf/ivw/holdings/ (top 25, 2026-11-05); https://www.ssga.com/us/en/intermediary/etfs/spdr-portfolio-s-p-500-growth-etf-spyg (top 10, 2026-11-05).
- 2012 Nasdaq-100 leaders: https://investorplace.com/?p=246930 ("QQQ's Ugly Side Comes Out to Play", 2012-10-19): top eight QQQ holdings Apple, Microsoft, Google, Oracle, Intel, Amazon, Qualcomm, Cisco; Apple nearly 20%; top 10 = 57%.
- 2015 weights: QQQ trust SEC filing https://www.sec.gov/Archives/edgar/data/0001067839/000119312516441831/d106822d485bpos.htm (via search summary: 2015-12-31 Apple 11.11%, Microsoft 8.39%, Amazon 6.00%, Alphabet 4.96%, Facebook 4.50%); https://www.etftrends.com/2015/02/nasdaq-100-evolution-good-for-etfs/amp/ (Amazon and Comcast in the top 10, Feb 2015). Read only through search summaries, not the full documents.
- Nasdaq NDXMEGA research PDF https://indexes.nasdaqomx.com/docs/NDXMEGA_Research.pdf has a 2014-08-30 top-10 table, but I could not extract its text. Worth opening manually to confirm 2014 leaders.
- Delisting facts: Wikipedia pages for Celgene, Express Scripts, Altaba, Walgreens Boots Alliance, Dell, Activision Blizzard (https://en.wikipedia.org/wiki/ plus the page name).

## Faded leaders (still listed): 8 rows, below the 10-15 target
| Ticker | Evidence |
|---|---|
| INTC, CSCO, QCOM | Top-8 QQQ holdings Oct 2012 (InvestorPlace). Cisco was part of a 25.2% Apple+Microsoft+Cisco weight in 2015 (search summary). All three are still Nasdaq-100 members, so they are also in the current universe; stored once as faded_leader. |
| EBAY, CTSH, BIIB, ILMN | Top-20 Nasdaq-100 status in 2010-2015 NOT verified from any source I could read; included from recall of their size then. Uncertain. ILMN may never have been top 20. |
| IBM | Whether IBM was a top-20 S&P 500 Growth name in 2010-2015 is NOT verified (IBM was often classed as value). Now roughly rank 43 in SPYG. Uncertain. |

Oracle (top-4 QQQ holding in 2012, moved to NYSE in 2013) is in the current SPYG top 50 (about rank 47) with market cap 362B, so I kept it as a normal candidate, not a faded leader.

## Delisted former leaders (cannot be priced)
| Company | Exit | Reason | Source |
|---|---|---|---|
| Celgene (CELG) | Acquisition by Bristol-Myers Squibb, completion reported 2019-11-20/21 | Acquired, $74B | Wikipedia Celgene (exact delisting day not on page) |
| Express Scripts (ESRX) | 2018-12-20 | Acquired by Cigna | Wikipedia Express Scripts |
| Yahoo / Altaba (YHOO/AABA) | Operating business sold to Verizon 2017-06-13; Altaba stopped trading 2019-10-02, dissolved 2019-10-04 | Asset sale then liquidation | Wikipedia Altaba |
| Dell Inc. (DELL) | 2013-10-30 | Leveraged buyout (went private). Dell Technologies relisted 2018 as a different security | Wikipedia Dell |
| Walgreens Boots Alliance (WBA) | 2025-08-28 | Taken private by Sycamore Partners | Wikipedia Walgreens Boots Alliance |
| Activision Blizzard (ATVI) | 2023-10-13 | Acquired by Microsoft | Wikipedia Activision Blizzard |

Also probably delisted leaders but NOT source-checked (do not cite): DirecTV, Twenty-First Century Fox, Monsanto, Allergan, Alexion, Kraft Foods Group. Exit dates not verified.

## Excluded or not in the file
- Non-US domicile per yfinance (Nasdaq-100 members): Arm (UK), ASML (NL), Coca-Cola Europacific (UK), Ferrovial (NL), Linde (yfinance UK; Irish plc), MercadoLibre (Uruguay), Nebius (NL), NXP (NL), PDD (Ireland), Seagate (Singapore), Shopify (Canada), Thomson Reuters (Canada).
- Considered as faded leaders but dropped: Under Armour (UA/UAA, market cap 2.2-2.3B), GoPro (GPRO, 0.2B), Chipotle (CMG, 43.6B), because I could not show any was a top-20 Nasdaq-100 or S&P 500 Growth name in 2010-2015. Also NetApp, Gen Digital, Viatris (Mylan), First Solar, Salesforce, Disney, Lululemon (Canada), Garmin (Switzerland): not shown to be top-20, not included.
- SpaceX appears in the Wikipedia Nasdaq-100 list at the access date with no ticker I could confirm in yfinance; omitted. It cannot meet the 2012 rule anyway.
- Baidu: non-US, skipped as instructed.

## Not_testable (US, large, first trade after 2012-12-31)
ABNB, APP, ALAB, CEG, CRWV, CRWD, DDOG, DASH, GEHC, LITE, MRNA, PLTR, PYPL, RKLB, SNDK, ABBV (2013-01-02, misses by two days), GEV, ANET, UBER, HLT. Dates are yfinance first trade dates.

## Uncertain items
- yfinance `since` can reflect predecessor or spin-off history (KDP = Dr Pepper Snapple 2008; MDLZ = Kraft Foods 2001; GE = pre-spin GE; AVGO = Avago, Singapore-domiciled until 2018; HON ticker vs the Wikipedia "Honeywell Aerospace / Honeywell Technologies" split). These pass the date rule only through legacy history and need a check before scoring.
- Market caps are yfinance 2026-11-07 values, not independently verified.
- SPYG top-50 membership at the margin (ranks 45-55 differ by under 0.05% weight) is estimate-based.
- aum_usd_bn and expense_ratio are blank by design for stocks.

## Follow-up (2026-11-07): faded-leader group widened to 20 rows (+ GPRO as not_testable)
Added 12 faded_leader rows: UAA, FSLR, WYNN, FFIV, AKAM, GEN (ex-Symantec), EXPE, SIRI, FOSL, TRIP, GRPN, NTAP. All US domicile, first trade on or before 2012-12-31, verified with yfinance info (ticker, first trade date, market cap). The $10B rule is waived for faded leaders (UAA 2.3B, FOSL 0.5B, TRIP 0.8B, GRPN 0.6B, WYNN 8.6B are below it). Final faded_leader count: 20.
- GPRO (GoPro): first trade 2014-06-26 fails the 2012-12-31 rule, so it is a not_testable row (category faded_leader), not a faded_leader.
- UNSOURCED (growth-leader claim from recall, no source found; source_url left blank): UAA, FSLR, WYNN, FFIV, AKAM, GEN, EXPE, SIRI, FOSL, TRIP, GRPN, NTAP, GPRO. Wikipedia's Nasdaq-100 page has no component-change history, and no archived 2010-2014 QQQ/IVW holdings page was found. Previously flagged as unverified: EBAY, CTSH, BIIB, ILMN, IBM. Sourced: INTC, CSCO, QCOM only.
- Not added: EA (yfinance returned no first trade date, so the date rule cannot be checked), GRMN, STX, CPRI (foreign domicile), WDC, GILD, VRTX, REGN, ADSK, MU (already candidates; rows unchanged).

### Additional delisted former leaders (not priceable)
| Company | Exit | Reason | Source |
|---|---|---|---|
| Zynga (ZNGA) | 2022-05-23 | Acquired by Take-Two Interactive | Wikipedia Zynga |
| Staples (SPLS) | 2017-09-12 | Taken private by Sycamore Partners | Wikipedia Staples Inc. |
| Whole Foods Market (WFM) | 2017-08-28 | Acquired by Amazon, $13.7B | Wikipedia Whole Foods Market |
| Bed Bath & Beyond (BBBY) | 2023 (bankruptcy) | Defunct retailer; exact filing and delisting dates not on the Wikipedia page I read | Wikipedia disambiguation page only; date not verified |
Groupon (GRPN) is still listed (market cap 0.6B), so it is a faded leader, not a delisting.
