# International growth stocks: long list notes (task 2.1)

Built 2026-11-07. File: `intl_growth.csv` (61 rows: 40 candidate, 8 faded_leader, 13 not_testable). No scoring, no price history, nothing written under data/.

## How the list was built
1. Starting pool: names I know to be large non-US growth leaders across the required regions and kinds (semis, software, luxury, healthcare, consumer internet, EM financials, industrial technology). Growth profile is a judgement at this stage, not a computed CAGR.
2. Growth-index cross-check (Nov 5, 2026 holdings, accessed 2026-11-07): iShares MSCI EAFE Growth (EFG) top 25 https://stockanalysis.com/etf/efg/holdings/ ; iShares MSCI EM (EEM) top 25 https://stockanalysis.com/etf/eem/holdings/ ; ACWX top 25 https://stockanalysis.com/etf/acwx/holdings/ . Rows whose source_url is one of the first two appear in that top 25. All other rows cite their Yahoo quote page, which supports size only; their membership in MSCI growth indices was NOT verified (iShares pages did not expose holdings tables to the fetch tool).
3. Each ticker checked with yfinance: `Ticker.info` (marketCap, currency, country, exchange, name) and `Ticker.get_history_metadata()['firstTradeDate']` for the first trade date. Missing marketCap (Moutai, TCS, Reliance, Macquarie) taken from `fast_info`. No price history downloaded.
4. SEC CIKs: https://www.sec.gov/files/company_tickers.json (fetched 2026-11-07, User-Agent set), matched on the ADR/US ticker, zero-padded to 10 digits.

## FX rates used (Yahoo, 2026-11-07, USD per 1 unit)
EUR 1.1143, GBP 1.3356, JPY 0.006312, KRW 0.000733326, TWD 0.030520, HKD 0.12756, CNY 0.15004, INR 0.010648, BRL 0.18195, MXN 0.05377, CAD 0.70781, AUD 0.68681, CHF 1.2195, SEK 0.10110, DKK 0.14908, ZAR 0.060544, IDR 0.0000552, ILS 0.31351. USD-quoted names (MELI, BIDU, SE, NU) need none. Market caps are Yahoo's figure times these rates; they are indicative (share-class and float treatment differ).

## Caveats on the `since` column
Yahoo's first trade date is the first date Yahoo holds data. For many Asian and European names it is a floor (2000-01-03/04, 1996-01-01 for NSE names, 1993-1999 for others) and understates the true listing age. All such rows pass the 2012 rule comfortably, so this only matters for "months of history" counts, which should come from the price download. Rows flagged in notes.

## Hard-rule check
All 40 candidates: non-US domicile, Yahoo first trade date at or before 2012-12-31 (latest: Dollarama 2009-10-09, AIA 2010-10-29), market cap at least $10B (smallest: Naver $19.9B, REA $15.7B). Traded value >= $10M/day is NOT checked here (task 2.4).

## Not testable (role=not_testable, listing after 2012-12-31)
Ferrari RACE.MI 2016-01-04; Adyen 2018-06-13; Recruit 6098.T 2014-10-16; Samsung Biologics 207940.KS 2016-11-11; LG Energy Solution 373220.KS 2022-01-27; Alibaba 9988.HK local 2019-11-26 (NYSE ADS BABA 2014-09-19); Meituan 3690.HK 2018-09-20; Xiaomi 1810.HK 2018-07-09; CATL 300750.SZ 2018-06-11; Nu Holdings 2021-12-09; Shopify SHOP.TO 2015-05-21; WiseTech WTC.AX 2016-04-11; Sea Ltd 2017-10-20.

## Faded leaders (survivorship check, still listed)
Nokia, Ericsson, Petrobras, Vale, China Mobile, Baidu, Teva, Canon. "Growth leader in 2010-2015" is my judgement, not index-verified; confirm against 2010-2015 MSCI/holdings data in task 2.4. Their listing and size were verified in yfinance (all above $10B; smallest Canon $24.4B). Baidu's only listing is the Nasdaq ADS (2005), treated as its local listing. Teva: TASE listing, quote unit agorot (ILA) converted as ILS.

## Considered and excluded from the candidate set
- Trimmed only to hold the list at 40 (still eligible, could be re-added): L'Oreal, EssilorLuxottica, adidas, Airbus, Schneider Electric, Dassault Systemes, Nintendo, Shin-Etsu, Nidec, Daikin, Advantest, Samsung SDI, Anta Sports, ICICI Bank, Titan, Walmart de Mexico, Cochlear, Macquarie, Canadian Pacific KC, Xero.
- Xero (XRO.AX): ASX first trade 2012-11-08, NZ domicile, $12.5B; passes the rule by ~7 weeks (only ~61 months before 2018), so I left it out as marginal; re-add if wanted.
- Roche: Yahoo returned 404 for ROG.SW, not verified, excluded.
- Bayer considered for faded leaders, dropped (growth-leader status weak).
- Not examined: NetEase (local HK listing 2020), PDD (2018), Coupang, Spotify (Lux, 2018 listing), Argenx.

## SEC filings (point-in-time fundamentals)
In SEC tickers file via ADR (13 of 40 candidates): ASML, AstraZeneca, Infineon (IFNNY), Novo Nordisk, SAP, Sony, TSMC, HDFC Bank, Infosys, Itau, MercadoLibre, CNR, CSL (CSLLY). Form type (20-F / 40-F / 10-K) not verified; CNR is expected to be a 40-F filer, MELI a 10-K filer, so the "20-F" assumption in the plan should be checked in task 2.4. Faded leaders with CIK: Baidu, Ericsson, Nokia, Petrobras, Vale, Teva. No SEC filings (blank CIK, "no SEC filings" in notes): LVMH, Hermes, Atlas Copco, Lonza, Keyence, Tokyo Electron, Fast Retailing, Chugai, SK Hynix, Samsung, Naver, MediaTek, Tencent, BYD, Ping An, Moutai, AIA, TCS, Bajaj Finance, Reliance, WEG, Naspers, BCA, Couche-Tard, Constellation, Dollarama, REA. Note some of these have an OTC ADR (usd_ticker given) that does not file with the SEC.

## Uncertain
- Naspers mcap unit (ZAR 566B assumed to be rand, giving $34.3B) not cross-checked; Naspers/Prosus structure makes a "growth" label debatable.
- Samsung, SK Hynix, TSMC market caps look very large; taken as Yahoo reports them, not independently verified.
- Many "growth profile" labels (Moutai, Bajaj, Reliance, Atlas Copco, ATD) rest on judgement.
- AIA categorised china_hk (Hong Kong, treated as developed); Tencent, BYD, Ping An, Moutai treated as EM (China). MercadoLibre country UY, category latam_em.
- Denmark, South Africa, Indonesia, Uruguay have no home index in method.md section 9; local_index left blank.
- Yahoo returns Airbus as Netherlands-domiciled; Xero NZ.

## Update 2026-11-07 (follow-up): breadth restored
Added 20 previously trimmed names as role=candidate (total 60 candidates; 24 EM-domiciled; 16 with CIK): OR.PA, EL.PA, ADS.DE, AIR.PA, SU.PA, DSY.PA, 7974.T, 4063.T, 6594.T, 6367.T, 6857.T, 006400.KS, 2020.HK, ICICIBANK.NS, TITAN.NS, WALMEX.MX, COH.AX, MQG.AX, CP.TO, XRO.AX. All were verified in yfinance (info + get_history_metadata), none unverified.
- CORRECTION: Xero (USD 8.6B) and Cochlear (USD 7.0B) are BELOW the $10B hard rule at current FX; the earlier "Xero $12.5B" was in AUD. They are kept as candidates at the coordinator's request and flagged in notes; the screen should drop them. Nidec (11.7B) is the next-smallest above the line.
- Form type hint (`form_type=` in notes) taken from the `filings.recent.form` list of data.sec.gov submissions JSON for each ADR CIK. This overrides the earlier "20-F assumed" caveat: CNI is 40-F; CP, MercadoLibre and Teva are 10-K (US GAAP); CSL (CSLLY) shows none of the three in its recent filings ("other", no point-in-time 20-F data seen); Shopify shows a mix; the rest are 20-F (IFRS or home GAAP).
