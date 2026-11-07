# EM bond long list: build notes (screener, run 2026-11-07)

## How the list was built
1. Candidate tickers came from method.md section 4 plus issuer knowledge (iShares, VanEck, Invesco, SPDR, WisdomTree, Vanguard, First Trust, Global X, JPMorgan, PIMCO, T. Rowe, Fidelity, TCW, DoubleLine, Goldman, MFS, Payden, Eaton Vance, Stone Harbor/Virtus, Ashmore, Franklin, Federated, PGIM, Western Asset, Nuveen, John Hancock). About 120 tickers were probed; tickers that return 404 on Yahoo (e.g. EMBH, EMHB, EMCD, SHLDX-as-EM-debt, GEMDX) were dropped. Names that resolved to equity or unrelated funds were dropped (e.g. MEMKX, ABEMX, FEMKX, LEMIX).
2. Each ticker was checked with yfinance `Ticker(t).info` on 2026-11-07 (inception, totalAssets, netExpenseRatio, yield). No price history was downloaded, FRED was not called.
3. Hard screens (method.md s4): inception on or before 2012-12-31 (60 months by 2017-12-31), net assets at least $200M, net expense at most 1.00%, daily liquidity (all ETFs and open-end funds are daily). Failures are kept with the reason in `notes`.
4. Result: 20 candidates, 11 excluded, 12 not_testable (43 rows).
5. Country file: 24 countries. Ratings from Wikipedia (S&P, Brazil/Argentina Moody's) and countryeconomy.com (Moody's), cross-checked against Trading Economics (S&P). Index weights from the EMB and LEMB iShares pages (top 12 countries only).

## Sources (all accessed 2026-11-07)
- EMB: https://www.ishares.com/us/products/239572/ishares-jp-morgan-usd-emerging-markets-bond-etf (country weights as of 2026-11-05)
- LEMB: https://www.ishares.com/us/products/239528/ishares-jp-morgan-em-local-currency-bond-etf
- CEMB: https://www.ishares.com/us/products/239525/ishares-emerging-markets-corporate-bond-etf
- EMHY: https://www.ishares.com/us/products/239527/ishares-emerging-markets-high-yield-bond-etf
- EBND: https://www.ssga.com/us/en/intermediary/etfs/state-street-spdr-bloomberg-emerging-markets-local-bond-etf-ebnd
- EMLC duration (UCITS fact sheet, 2026-08-31, via search): https://www.vaneck.com/ie/en/library/fact-sheets/emlc-fact-sheet/
- DBLEX inception/ER: https://spciq.doubleline.com/wp-content/uploads/DoubleLine-Emerging-Markets-Fixed-Income-Fund-Fact-Sheet.pdf (Dec 2025 fact sheet)
- FNMIX inception: https://stockanalysis.com/quote/mutf/FNMIX/
- PRELX inception: https://stockanalysis.com/quote/mutf/PRELX , https://www.mutualfunds.com/funds/prelx-t-rowe-price-emerg-mkts-lcl-ccy-bd/
- Yahoo quote pages (source of yfinance data for the other rows): https://finance.yahoo.com/quote/TICKER
- Ratings: https://en.wikipedia.org/wiki/List_of_countries_by_credit_rating ; https://countryeconomy.com/ratings ; https://tradingeconomics.com/country-list/rating

## Share classes chosen
Cheapest class that Yahoo quotes with history among those checked: PEBIX (Instl), PREMX (only no-load class checked), FNMIX, TGEIX (I), DBLEX (I), GSDIX (Instl), JEMDX (I), MEDIX (I), PYEMX, SHMDX (I), EEIIX (I), PRELX. Cheaper R6/Admiral-type classes (e.g. JPMorgan R6, T. Rowe I-class) were not tested; the scoring phase should confirm class and expense. AUM from Yahoo for open-end funds is fund-level (all classes), not class-level.

## Excluded (reason)
PELBX (ER 1.32%, unverified), ELD (AUM $130M), EMCB (AUM $99M), EMBAX (AUM $93M, ER 1.21%), FEMDX (ER 1.02%, AUM $142M), EMDIX (AUM $45M), EMKIX Ashmore (AUM $25M, ER 1.21%), PEMIX (AUM $59M), EMDAX (AUM $40M, ER 1.13%), FEDCX (Fidelity Series, not purchasable), WEMDX (AUM $33M, ER 1.30%).
Not testable: VWOB (2013), VEMBX (2017), FEMB (2014), EMTL (2016), JPMB (2018), EMBD (2020), EMHC (2021), CBON (2014, China only), JEMIX (R6 class date 2015), TRECX (2025), PYELX (2022), NEMDX (2022).
Not found / not checked: Lord Abbett, Wells Fargo, BlackRock, Oppenheimer/Invesco EM debt mutual funds, Capital Group; tickers I tried returned nothing, so they may exist under other tickers.

## Uncertain items
- Yahoo inception dates are unreliable for mutual funds: FNMIX (Yahoo 2018-12-04, true 1993), DBLEX (Yahoo 2026-08-03, true 2010-04-06), PRELX (Yahoo 2021-02-22, true 2011-05-26). PEBIX, MEDIX, TGEIX, JPM, GS dates are Yahoo values (class or fund) and not independently confirmed; all precede 2012, so the screen result is robust, but `since` may be a class date.
- Index names marked "from memory, unverified" in `local_index` (PCY, EMLC, HYEM, all open-end benchmarks, VWOB) were not read from a source page.
- EMLC: VanEck US page failed; the duration comes from a UCITS fact sheet, and country weights there differ between regional documents, so GBI-EM weights in the country file come from LEMB (GBI-EM GD 15% cap/4% floor), not EMLC. EMBI weights come from EMB (Diversified Core), not the full EMBI Global Diversified. Only the top 12 of 31 (EMB) and 22 (LEMB) countries were visible; other weights are blank, not zero.
- AUM differences: EMB $13.84bn (iShares, 2026-11-06) vs $13.57bn (Yahoo); EBND $2.26bn vs $2.24bn; EMHY $546M vs $560M. Yahoo values lag the issuer pages. DBLEX at $286M is close to the floor.
- Ratings: Wikipedia and Trading Economics disagree for Colombia (BB vs BB-), Nigeria (B- vs B), and on outlooks for Mexico and Indonesia. Wikipedia dates in `notes` are the S&P action dates it shows (some, e.g. Thailand 2004, UAE 2007, look stale). Moody's from countryeconomy.com has no dates; Moody's for Nigeria left blank. `rating_date` is the retrieval date.
- FRED IDs are patterns, not verified (FRED not called). Expect 10y to exist for MX, ID, ZA, IN, PL, HU, CZ, CL, CO, TR, KR, BR (BR and ID are less sure). CPI "xxxCPIALLMINMEI" series may end before 2026 (OECD MEI discontinuation).
