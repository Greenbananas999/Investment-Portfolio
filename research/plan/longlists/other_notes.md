# Other sleeve long list: build notes (task 2.1, screener role)

Built 2026-11-07. File: `research/plan/longlists/other.csv` (108 rows: 32 candidate, 42 excluded, 34 not_testable). No price history downloaded; nothing under `data/` touched.

## How it was built

1. Started from the brief's category list plus method.md section 4 "Other" universe and the fixed candidates in data_request.md section 2 (GLD, IAU, SLV, DBC, GSG, PDBC, GUNR, VNQI, RWX, IGF, TIP, SCHP, WIP, BIL, UUP), then added peers in every category.
2. One yfinance `Ticker(t).info` pass on 2026-11-07 (about 125 tickers) read: `fundInceptionDate` (or `firstTradeDateEpochUtc`), `totalAssets` (converted to USD bn), `netExpenseRatio` (percent, stored in the CSV as a decimal), category, exchange. Names in the CSV are yfinance names truncated at 45 characters. Source URL is the Yahoo quote page unless a fund page was actually read (see below).
3. Hard screens (method.md section 4): inception on or before 2012-12-31, net assets at least $200M, expense ratio at most 0.75%. Pass = candidate. Fail on AUM or expense = excluded. Inception after 2012 = not_testable. Sector equity, single-commodity, US REIT, credit-bearing "cash", leveraged and similar classes are excluded by class with the reason in notes; some of these pass the numeric screens and are flagged "planner may override".
4. `non_us_share` (method.md section 3): 0.00 for gold, silver, platinum/palladium, commodities, US TIPS, cash. For equity and ex-US funds it comes from the fund factsheet where retrieved.

## Non-US share evidence (fund pages)

| Fund | Value used | Evidence |
|---|---|---|
| GNR | 0.65 | US 35.20%, SSGA factsheet as of 2026-09-30: https://www.ssga.com/library-content/products/factsheets/etfs/us/factsheet-us-en-gnr.pdf (fetched 2026-11-07) |
| GII | 0.64 | US 36.44%, SSGA factsheet 2026-09-30: https://www.ssga.com/library-content/products/factsheets/etfs/us/factsheet-us-en-gii.pdf |
| RWO | 0.27 | US 72.95%, SSGA factsheet 2026-09-30: https://www.ssga.com/library-content/products/factsheets/etfs/us/factsheet-us-en-rwo.pdf |
| RWX | 1.00 | Dow Jones Global ex-U.S. index; no US in country table (Japan 26.92%, UK 13.95%), factsheet 2026-09-30: .../factsheet-us-en-rwx.pdf |
| WIP | 1.00 | index covers linkers "outside the United States"; no US in country table (UK 18.36%, Brazil 7.99%), factsheet 2026-09-30: .../factsheet-us-en-wip.pdf |
| IGF | 0.64 | US 36.15% as of 2026-11-05, https://www.ishares.com/us/products/239746/ishares-global-infrastructure-etf (fetched 2026-11-07) |
| GUNR | 0.65 (approximate) | US about 35.45% from a third-party page (BestETF, dated 2026-04-04, found via search; site now closed). Official Northern Trust page timed out. Treat as approximate. |
| VNQI | 1.00 (by design) | Vanguard page returned no data; ex-US by index name only. Not verified from holdings. |
| IGE, HAP, WOOD | unverified | country tables not retrieved (etfdb returned 403) |

SSGA web pages (as opposed to factsheet PDFs) show empty country tables; the PDFs work.

## Candidates (32, above the 15-25 target)

The target was exceeded because eight US TIPS funds and four precious-metal-basket funds all pass every hard screen. The scoring step (2.4) can thin them. Counts: gold 3 (GLD, IAU, SGOL); silver 2 (SLV, SIVR); precious_basket 4 (GLTR, PPLT, PALL, DBP); commodities 2 (GSG, DJP); natural_resources 4 (GUNR, GNR, IGE, HAP); reit_exus 2 (VNQI, RWX); reit_global 1 (RWO); infrastructure 2 (IGF, GII); tips_us 8 (TIP, SCHP, VTIP, STIP, LTPZ, SPIP, STPZ, TDTT); linkers_intl 1 (WIP); cash 2 (BIL, SHV); timber_farmland 1 (WOOD). A reasonable trim, if the planner wants about 20, is to keep one fund per near-duplicate group (for example GLD/IAU, TIP/SCHP/STIP, GUNR/GNR); this is a suggestion, not applied.

## Excluded (42) and not_testable (34)

- Fail screens: DBC (expense 0.85%), USCI (1.05%), DBA (0.85%), USO (0.86%), UNG (1.17%), CPER (0.88%), UGL (leveraged, 1.19%), CUT (AUM and 0.76%), DBE (AUM 152M), FTRI, FTAG, VEGI, IFGL, TIPZ (AUM), MNA (0.78%), QAI (0.81%).
- Excluded by class: single-sector commodity funds DBB and DBO (pass numerics), sector equity and miners (MXI, XLB, XME, COPX, REMX, PICK, MOO, GDX, GDXJ; GDX/GDXJ are note-only per brief), US REITs (VNQ, SCHH, IYR, RWR, PSR), nominal international bonds BWX, SHY, credit-bearing "cash" MINT and FLRN, fund-of-ETFs RLY, UUP (currency), Sprott closed-end trusts PHYS/PSLV/CEF (no inception or AUM from yfinance; screens unverified).
- not_testable (listed after 2012-12-31): gold GLDM, BAR, AAAU, OUNZ, IAUM; commodities PDBC, COMT, GCC, BCI, CMDY, BCD, FTGC; NANR, REET, TOLZ, NFRA, IFRA; TIPX, PBTP, GTIP; cash SGOV, GBIL, USFR, TFLO, ICSH, NEAR, JPST; bitcoin BITO, IBIT, GBTC; managed futures DBMF, KMLM, CTA, FMF. Bitcoin and managed-futures rows carry category excluded_class with role not_testable.

## Tax and structure caveats

- Gold, silver, platinum, palladium physical trusts (GLD, IAU, SGOL, SLV, SIVR, GLTR, PPLT, PALL) are grantor trusts: gains taxed as collectibles (up to 28% long-term federal rate). No K-1.
- DBP and GSG are commodity pools: K-1 reporting, futures roll yield/contango drag, and (DBP) a futures-based exposure rather than bullion. DBC, USCI, CPER, USO, UNG, DBB and others are likewise K-1 (excluded anyway). PDBC and COMT avoid K-1 via a Cayman subsidiary, but are not testable.
- DJP is an exchange-traded note: unsecured issuer credit risk, no tracking via holdings, and note maturity/redemption risk; the issuer and call terms were not checked in this pass.
- Equity-based real-asset funds (GUNR, GNR, IGE, HAP, WOOD, IGF, GII) carry equity beta and will correlate with the equity sleeves; foreign dividends may carry withholding tax. The scoring step will measure correlation with ACWX.
- RWO is about 73% US, so it is not a non-US diversifier; it is listed as a candidate because it passes the screens.
- TIPS funds: phantom income on inflation accruals; deflation floors apply only to the Treasury principal.

## Uncertainties

- Expense ratios are yfinance `netExpenseRatio` (may reflect waivers); SSGA pages show gross ratios. They agree for the funds compared (GNR 0.40, GII 0.40, WIP 0.50, RWX 0.59, RWO 0.50, IGF 0.37).
- Local index names were written from general knowledge of each fund, not re-read from every fund page; those not fetched should be treated as unverified descriptions. Indexes marked "(index name not verified)" are explicit guesses.
- AUM is yfinance `totalAssets` as of 2026-11-07, not fund-page figures, except RWX (SSGA page: $239.09M, 2026-11-05, versus yfinance $231M), RWO, GII, WIP, IGF (all consistent).
- The fixed data-request item UUP is excluded by class here because it is a currency fund; it stays in the data request as a reference series.
- VTIP's inception (2012-10-12) gives about 62 months before 2018-01, a thin margin over the 60-month rule.
- WTMF (managed futures) and RLY (multi-asset) pass every numeric screen but are excluded on scope; both flagged for planner decision.
