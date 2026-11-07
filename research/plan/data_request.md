# Data request (one batch)

Everything the plan needs, fetched by **one command** run on John's Windows PC
(this session runs there, so the planner runs it in task 2.2 and reports what
succeeded and failed). Nothing in this list may be downloaded piecemeal by a
subagent. Items marked *(after 2.1)* are filled in once the long lists exist;
the universe file drives the fetch so adding a name is one CSV row.

```bash
python -m research.fetch --universe research/plan/universe.csv
```

Writes to `data/research/` (existing files are extended, not replaced):
`prices.csv` (daily adjusted close, local currency, one column per ticker),
`prices_usd_listing.csv` (US listings/ADRs), `fx.csv` (USD per unit),
`yields.csv` (FRED monthly), `cboe/<INDEX>.csv`, `fundamentals/<TICKER>/`
(yfinance), `edgar/<CIK>.json` (SEC companyfacts), `funds.csv` (expense
ratio, AUM, inception, category from yfinance info), `fetch_log.txt`.

Source checks done 2026-11-07 from this PC: Yahoo Finance OK (yfinance
1.7.0); SEC EDGAR `companyfacts` OK with a descriptive User-Agent; CBOE index
CSVs OK; Stooq not reachable. FRED answered the first request, then 30
back-to-back requests got connection resets and every request since has timed
out, so FRED has rate-limited this PC for now. The fetch must space FRED
requests 5 seconds apart with retries, and the EM yield series in section 4
are unconfirmed until the fetch log shows them.

## 1. Universe file: `research/plan/universe.csv`

Columns: `ticker, name, type, role, country, currency, listing, usd_ticker,
local_index, edgar_cik, since, notes, source_url`.
`type` in {us_growth_stock, intl_growth_stock, em_bond, other, overlay,
benchmark, index, fx, rf}. `role` in {candidate, faded_leader, benchmark,
support}. The screeners (task 2.1) fill the candidate rows; the rows below are
fixed now.

## 2. Prices (daily, adjusted close, from 2005-01-01)

**Benchmarks and risk-free (fixed):** IVW, QQQ, EFG, EEM, ACWX, ACWI, VXUS,
SPY, AGG, EMB, EMLC, GLD, BIL, plus the existing `portfolio/config.UNIVERSE`
tickers (EFA, HEFA, VGK, EWJ, DXJ, EWU, EWC, EWA, INDA, EWT, MCHI, BNDX, IGOV,
IEF).

**Home indices for local-currency comparison (fixed):** ^GSPC, ^NDX, ^N225,
^FCHI, ^GDAXI, ^STOXX50E, ^FTSE, ^SSMI, ^KS11, ^TWII, ^HSI, ^NSEI, ^GSPTSE,
^AXJO, ^BVSP, ^MXX, ^OMX, ^AEX, 000001.SS; ^IRX, ^TNX, ^VIX.

**EM bond funds (fixed candidates):** EMB, PCY, VWOB, EMLC, LEMB, EBND, ELD,
CEMB, EMCB, EMHY, HYEM, PEBIX, PREMX, FNMIX, TGEIX, PELBX, DBLEX, plus any
added by the EM bond screener with at least 60 months before 2018.

**Other sleeve (fixed candidates):** GLD, IAU, SLV, DBC, GSG, PDBC, GUNR,
VNQI, RWX, IGF, TIP, SCHP, WIP, BIL, UUP.

**Overlay proxies (fixed):** XYLD, QYLD, PUTW (if listed by 2016), ^PUT.

**US growth stocks** *(after 2.1)*: 30-40 tickers (Nasdaq-100, S&P 500
Growth top 50, faded leaders), local = US listing.

**International growth stocks** *(after 2.1)*: 30-40 local listings plus
their US ADR where one exists (e.g. 2330.TW/TSM, ASML.AS/ASML, NOVO-B.CO/NVO,
MC.PA, SAP.DE/SAP, 6861.T, 8035.T, 0700.HK/TCEHY, 1299.HK, RELIANCE.NS,
HDFCBANK.NS/HDB, CSU.TO, CSL.AX, 2454.TW, ATCO-A.ST, DSY.PA, MELI, NTES,
000660.KS, 005930.KS). Already on disk: 000660.KS, 005930.KS, 2330.TW, TSM.

## 3. FX (daily, USD per 1 unit, from 2005)

Every currency in the universe. Fixed set: EUR, GBP, CHF, SEK, DKK, NOK, JPY,
HKD, CNY, TWD, KRW, INR, SGD, AUD, NZD, CAD, BRL, MXN, ZAR, TRY, IDR, PLN,
HUF, CZK, THB, MYR, PHP, CLP, COP, ILS. Yahoo tickers `EURUSD=X` style where
quoted direct, `JPY=X` style inverted. Already on disk: KRW, TWD, EUR, TRY and
the 13 currencies in `data/fx.csv`.

## 4. Rates, inflation and credit series (monthly; daily series are month-ended)

**Source order (decided 2026-11-07 after FRED rate-limited this PC):**

1. **OECD SDMX API (primary for all non-US rates).** Tested OK, 1 second per
   query, no key. One query returns every country:
   `https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,/.M.IRLT.PA.....?startPeriod=2005-01&dimensionAtObservation=AllDimensions&format=csvfile`
   (10-year government yield, `MEASURE=IRLT`) and the same with `IR3TIB`
   (3-month interbank). Columns `REF_AREA` (ISO3), `TIME_PERIOD`, `OBS_VALUE`.
   Coverage checked since 2017: BRA, CHL, CHN, COL, CZE, HUN, IDN (10y to
   2024-12), IND, KOR, MEX, POL, ROU, ZAF, ISR plus all developed markets.
   No Turkey. These are the same series FRED republishes as IRLTLT01xx and
   IR3TIB01xx.
2. **FRED fredgraph CSV** for US-only series, 5 seconds apart with retries,
   only once FRED answers again (blocked as of 2026-11-07 after a burst).
   Already on disk in `yields.csv`: TB3MS, GS10, CPIAUCSL, French and Korean
   rates, Turkish and French CPI, to 2026-09.
3. **Fallbacks if FRED stays blocked:** US real yields and nominal curve from
   Treasury.gov daily CSVs (tested OK:
   `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/<year>/all?type=daily_treasury_real_yield_curve&field_tdr_date_value=<year>&page&_format=csv`,
   and `type=daily_treasury_yield_curve` for nominal); broad dollar index via
   UUP (Yahoo) or DX-Y.NYB; country CPI via the World Bank API
   (`https://api.worldbank.org/v2/country/<ISO2;...>/indicator/FP.CPI.TOTL.ZG?format=json&date=2005:2026&per_page=200`, tested OK, annual) or the
   OECD CPI dataflow; EM credit spreads (BAML series) have no free fallback
   and are optional.

FRED series list (kept for when FRED answers; the fetch logs failures and
moves on):

| Group | Series |
|---|---|
| US rates and inflation | TB3MS, DGS2, GS10, DFII10 (10y TIPS real), T10YIE (breakeven), CPIAUCSL, DTWEXBGS (broad dollar) |
| Existing | IRLTLT01FRM156N, IR3TIB01FRM156N, IRLTST01TRM156N, IR3TIB01TRM156N, IR3TIB01KRM156N, IRLTLT01KRM156N, TURCPIALLMINMEI, FRACPIALLMINMEI |
| EM 10-year government yields | IRLTLT01MXM156N (MX), IRLTLT01ZAM156N (ZA), IRLTLT01INM156N (IN), IRLTLT01IDM156N (ID), IRLTLT01BRM156N (BR), IRLTLT01PLM156N (PL), IRLTLT01HUM156N (HU), IRLTLT01CZM156N (CZ), IRLTLT01CLM156N (CL), IRLTLT01COM156N (CO), IRLTLT01CNM156N (CN) |
| Short rates for covered interest parity | IR3TIB01xxM156N for MX, ZA, IN, ID, BR, PL, JP, EZ, GB, HK, TW where the series exists |
| EM credit | BAMLEMCBPIOAS (EM corporate OAS), BAMLEMHBHYCRPIOAS (EM HY OAS), BAMLEMCBPITRIV (EM corporate total return index) |
| Country CPI (annual inflation checks) | OECD CPI series for MX, ZA, IN, ID, BR, PL, KR, CN, TW where on FRED |

Turkish yields: FRED series end 2008-2010; no free history. Spot quotes stay
in `research/config.SPOT_YIELDS`; nothing is invented.

## 5. CBOE option-strategy index histories (daily CSV)

`https://cdn.cboe.com/api/global/us_indices/daily_prices/<IDX>_History.csv`
for BXM (buy-write, 2002), BXMD (30-delta buy-write, 1986), PUT (put-write,
1991 sparse, daily from 2000s), PPUT (5% OTM protective put, 1986), CLL
(collar, 2008). Yahoo's ^BXM/^BXMD/^PPUT have one row; ^PUT is on Yahoo and is
cross-checked against the CBOE file.

## 6. Fundamentals

**yfinance (current, up to 4 fiscal years)** for every stock candidate:
info.json, income_stmt, balance_sheet, cashflow, dividends, earnings_estimate,
revenue_estimate, growth_estimates. Same layout as the seven existing folders.

**SEC EDGAR companyfacts (point-in-time, with `filed` dates)** for every US
filer and every 20-F filer in the universe:
`https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`, User-Agent
"UMassBoston-622-portfolio-project <John's email>". Checked: AAPL (us-gaap),
TSM (ifrs-full, TWD, fiscal years 2017-2024 with comparatives), ASML (us-gaap
tags, EUR), Novo Nordisk (ifrs-full, only 2021 onward). Tags to union:
Revenues / RevenueFromContractWithCustomerExcludingAssessedTax / Revenue;
NetIncomeLoss / ProfitLoss; OperatingIncomeLoss; NetCashProvidedByUsedIn
OperatingActivities; PaymentsToAcquirePropertyPlantAndEquipment; LongTermDebt
+ DebtCurrent (or Borrowings); CashAndCashEquivalentsAtCarryingValue;
StockholdersEquity / Equity; CommonStockSharesOutstanding (dei:
EntityCommonStockSharesOutstanding). CIKs come from
`https://www.sec.gov/files/company_tickers.json` and the 20-F list; the
screener records the CIK in `universe.csv`. Companies with no SEC filings get
`edgar_cik` empty and the flag "fundamentals not point-in-time".

**Fund facts** for every ETF and open-end fund: expense ratio, net assets,
inception date, category, yield (yfinance info), and the latest factsheet URL
and date for the holdings region split and average credit rating (recorded by
the screener in `universe.csv` `source_url`, values in `funds.csv`).

## 7. Not available for free, and what is done instead

| Need | Substitute |
|---|---|
| Individual EM sovereign and corporate bond prices | EM bond ETFs and open-end funds as positions; FRED country yields for the country view |
| Turkish yield history | spot quotes only, flagged |
| Historical option prices | Black-Scholes on realized vol plus a stated volatility risk premium, cross-checked against CBOE BXM/PPUT/CLL |
| FX forward points | covered interest parity from 3-month rate differentials |
| Point-in-time index membership | current members plus a faded-leaders list with sources; the report shows how the faded leaders did |
| Point-in-time fundamentals for non-SEC filers | current 4-year yfinance statements, flagged |

## 8. Status

| Date | Event |
|---|---|
| 2026-11-07 | Draft written; sources tested from this PC. Fetch runs in task 2.2 after the long lists exist. |
| 2026-11-07 | Fetch run (`python -m research.fetch --universe research/plan/universe.csv`, 1431 s, plus `--only volumes` 61 s). Prices 410/412 tickers (no data: EMBAX, WEMDX; one-row: EMTL, ^VXEEM), USD listings 51/53 (no data: CHL, CAJ; one row: TOELY), FX 30/30, OECD 10Y 47 / 3M 46 / CPI y/y 53 areas to 2026-09/10, FRED answered (7 new series; EM OAS only from 2023-11), World Bank CPI 25/25, CBOE 5/5, fundamentals 209/209 folders, EDGAR 152/155 (404: CSL.AX, IFX.DE, ICICIBANK.NS), funds 176/176, volumes.csv and volumes_usd_listing.csv added. pytest green. |
