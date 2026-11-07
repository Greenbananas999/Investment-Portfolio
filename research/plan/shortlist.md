# Phase 2 shortlist (in-sample only, data to 2017-12-31)

Written 2026-11-07 after the hard screens, the in-sample fundamental scores
and the signal validation, before any out-of-sample candidate work. Every
number here comes from `research/plan/longlists/<type>_insample_table.csv`
(built by `python research/plan/shortlist_table.py`) and
`<type>_hard.csv`, `<type>_scored.csv`, `<type>_signals.csv`
(built by `python -m research.screen hard|score|validate --type <type>`).

How the tables were ordered (stated so the choice is auditable):
`composite = 0.50 x pct(fundamental_score) + 0.25 x pct(in-sample Sharpe) +
0.25 x pct(in-sample information ratio)`, percentiles within the type. The
composite only orders the table; the picks below follow it except where a
stated diversity reason says otherwise. The Phase 1 rubric (method.md
section 7) is applied later, on out-of-sample data, in Phase 4.

## Long lists and hard screens

| Type | Long list | Candidates | Passed hard screens | Main failure |
|---|---|---|---|---|
| US growth stocks | 128 rows (87 candidates, 20 faded leaders, 21 too young) | 87 | 46 (40 candidates + 6 faded leaders) | 3-year revenue CAGR to 2017 below 8% (47 names, e.g. Apple 7.8%, Microsoft 1.2%, Costco 4.6%); market cap at 2017 below $2B (Axon) |
| International growth stocks | 81 rows (60 candidates, 8 faded leaders, 13 too young) | 60 | 31 (27 + 4 faded leaders) | revenue CAGR below 8% (33 names, e.g. SAP 7.6%, LVMH 0.7%, Samsung 3.3%); market cap below $10B (Xero, Cochlear) |
| EM bond funds | 43 rows | 20 | 20 | (excluded before screening: 11 on AUM or fees, 12 too young) |
| Other sleeve | 108 rows | 33 | 33 | (excluded before screening: 41 by class or fees, 34 too young) |
| Overlays | 15 strategies | 15 | n/a (modelled in Phase 3) | 5 infeasible at $100,000 or outside the overlay-only rule |

Flags that apply to every stock table: traded value "not checked" (the
library does not yet read `volumes.csv`, which now exists; Phase 3 checks
liquidity); 2017 market cap "not checked" for 16 US names without
point-in-time share counts (passed on today's cap); for 22 of the 31
international passers the fundamentals are **not point-in-time** (no SEC
filings), so their growth screen and fundamental score use current
statements, as method.md section 4 allows and flags. This is the weakest part
of the in-sample screen and the Phase 4 reviewers are told so.

## Technical signals: none kept

Pre-registered test (method.md section 6): top-tercile long-only on each
signal versus the long list, monthly, 10 bp cost; kept if OOS IR > 0 and
t > 1.0. Result from `<type>_signals.csv`:

| Signal | US growth IR in / out (t out) | Intl growth | EM bonds | Other |
|---|---|---|---|---|
| T1 12-1 momentum | 0.38 / -0.17 (-0.5) | 0.77 / 0.09 (0.3) | 0.17 / -0.36 (-1.1) | 0.37 / 0.23 (0.7) |
| T2 above 200-day MA | -0.21 / -0.18 (-0.6) | -0.46 / -0.09 (-0.3) | -0.09 / -0.98 (-2.9) | -0.46 / -0.44 (-1.3) |
| T3 6m relative strength | 0.50 / 0.18 (0.5) | 0.26 / 0.12 (0.4) | -0.99 / -0.51 (-1.5) | 0.39 / 0.24 (0.7) |
| T4 low volatility | -0.65 / -0.68 (-2.0) | -0.17 / -0.57 (-1.7) | 0.24 / 0.16 (0.5) | -0.12 / -0.52 (-1.5) |
| T5 near 52-week high | -0.34 / -0.41 (-1.2) | -0.33 / -0.56 (-1.7) | -0.31 / -0.82 (-2.5) | -0.04 / -0.35 (-1.0) |

No signal clears the bar in any type. Momentum (T1) and relative strength
(T3) were positive in-sample for stocks and roughly zero out of sample; the
trend filter (T2), low volatility (T4) and the 52-week-high rule (T5) were
negative in both periods for growth stocks. Per the pre-registered rule the
technical weight in the rubric is redistributed, and the report will say that
the proposal's technical analysis did not add value out of sample on these
universes. The validation itself used out-of-sample data once, by design;
no candidate was ranked on it.

## Survivorship check

Faded leaders were screened with the same rules. In-sample they look good:
Biogen ranks 10th of 46 US passers, Sirius 17th, Illumina 18th; Baidu ranks
26th of 31 international passers while Vale, Petrobras and Teva are at the
bottom. A 2017 screen would have shortlisted Biogen. Phase 3 therefore
computes the out-of-sample metrics of the faded-leader group alongside the
candidates as a control, and Phase 4 reports how many 2017 in-sample winners
held up.

## US growth stocks: shortlist of 8

| Pick | Ticker | In-sample CAGR / Sharpe / IR / max DD | Fund. score | Why |
|---|---|---|---|---|
| 1 | AVGO Broadcom | 41% / 1.38 / 0.97 / -24% | 0.64 | top composite; semis consolidator; fundamentals not point-in-time (Singapore 20-F filer until 2018), flagged |
| 2 | META Meta Platforms | 38% / 1.04 / 0.63 / -42% | 0.88 | highest fundamental score, 52% revenue CAGR; 67 months in-sample (2012 IPO), flagged short |
| 3 | AMZN Amazon | 31% / 1.12 / 0.72 / -24% | 0.72 | consumer internet, consistent |
| 4 | REGN Regeneron | 41% / 1.00 / 0.70 / -38% | 0.72 | biotech; different driver from tech |
| 5 | NVDA Nvidia | 35% / 0.92 / 0.63 / -50% | 0.58 | second semi; the momentum-leaning candidate, highest volatility |
| 6 | ADBE Adobe | 22% / 0.97 / 0.43 / -32% | 0.64 | software; steadier |
| 7 | MA Mastercard | 26% / 1.23 / 0.66 / -22% | 0.45 | payments; lowest drawdown of the eight, quality over growth |
| 8 | GILD Gilead | 17% / 0.73 / 0.19 / -43% | 0.88 | the value-leaning candidate: highest fundamental score with the weakest in-sample IR (2017 revenue CAGR 39% from the hepatitis-C cycle that was already fading) |

Near misses: FANG Diamondback (rank 4, 47% CAGR, but 62 months in-sample and
an oil-price business; the energy case is covered by GNR/GSG in the other
sleeve); ORLY (rank 8, 1.21 Sharpe, 9% growth just above the bar); LRCX
(rank 7, third semi); SBUX, AMAT, MNST, ODFL (composite 0.61-0.65, no
distinct thesis versus the eight). Failed the growth screen and are not
candidates: Apple 7.8%, Microsoft 1.2%, Alphabet passed (17.6%) but ranks 28th
on a 0.75 Sharpe and 0.19 IR.

## International growth stocks: shortlist of 8

| Pick | Ticker | Country, currency | In-sample CAGR / Sharpe / IR / max DD | Fund. score | Why |
|---|---|---|---|---|---|
| 1 | NOVO-B.CO Novo Nordisk | DK, DKK | 22% / 0.98 / 0.75 / -40% | 0.72 | top composite; Europe healthcare; point-in-time flag |
| 2 | REA.AX REA Group | AU, AUD | 29% / 0.97 / 0.89 / -33% | 0.68 | online classifieds, smallest of the eight, AUD exposure |
| 3 | 2330.TW TSMC | TW, TWD | 22% / 1.20 / 0.94 / -16% | 0.60 | lowest drawdown and highest Sharpe among EM names; first SEC XBRL filing 2018 so scored on current data, flagged |
| 4 | 1299.HK AIA | HK, HKD | 17% / 0.87 / 0.84 / -23% | 0.70 | insurance, Asia ex-China growth; 86 months |
| 5 | 0700.HK Tencent | CN, HKD | 37% / 1.20 / 1.18 / -35% | 0.57 | China internet; the China-policy-risk candidate |
| 6 | BAJFINANCE.NS Bajaj Finance | IN, INR | 60% / 1.39 / 1.37 / -41% | 0.55 | highest in-sample return of all 31; the high-growth EM financial, INR risk |
| 7 | 000660.KS SK Hynix | KR, KRW | 18% / 0.65 / 0.53 / -52% | 0.83 | highest fundamental score; the cyclical, value-leaning candidate (memory cycle), already modelled in `research/` |
| 8 | CSU.TO Constellation Software | CA, CAD | 46% / 1.66 / 1.48 / -18% | 0.48 | best in-sample Sharpe of the type; serial acquirer, Canada |

These were the top eight by composite in the table as it stood when the
shortlist was frozen on 2026-11-07, and no diversity swap was made. Later
that day the screening library's financial-tag bug was fixed (method.md
section 13) and the in-sample table was regenerated: HDFC Bank moved to 7th
and Constellation to 10th. The shortlist was not changed, because by then
out-of-sample work had started and changing it would not have been a
clean in-sample choice; the regenerated table is the one on disk. Near
misses: DOL.TO Dollarama (rank 9, 1.55 Sharpe, Canada already covered),
RMS.PA Hermes (rank 10), HDFCBANK.NS (rank 11, India covered), 035420.KS
Naver, 6861.T Keyence (rank 17, the best Japanese name, 1.16 Sharpe), MELI
(rank 19). Japan and Latin America are not in the deep-research eight; the
Phase 3 international analyst computes the full return metrics for all 31
passers anyway (one script), so the report can show them.

## EM bond funds: shortlist of 8

| Pick | Ticker | Sub-type | In-sample CAGR / Sharpe / IR vs EMB or EMLC / max DD | Fee | Why |
|---|---|---|---|---|---|
| 1 | EMB iShares USD EM Bond | hard-currency sovereign, passive | 6.5% / 0.92 / benchmark / -11% | 0.39% | the index itself; the "mostly passive" core; 13.8bn AUM |
| 2 | PCY Invesco EM Sovereign Debt | hard-currency sovereign, equal-weight | 7.2% / 0.89 / 0.39 / -14% | 0.50% | disagrees with EMB on construction (equal country weights, longer duration) |
| 3 | HYEM VanEck EM High Yield | EM high-yield corporate | 6.5% / 0.98 / 0.16 / -11% | 0.40% | top composite; the credit-risk candidate; 67 months in-sample |
| 4 | CEMB iShares EM Corporate | EM investment-grade corporate | 4.4% / 0.66 / -0.15 / -11% | 0.50% | the corporate-spread candidate; lower return in-sample, included for the sub-type |
| 5 | EMLC VanEck EM Local Currency | local-currency sovereign, passive | 1.0% / 0.14 / benchmark / -29% | 0.30% | local-currency core; the FX-risk candidate and the one the forward hedge is tested on |
| 6 | EBND SPDR Bloomberg EM Local | local-currency sovereign (Bloomberg index) | 1.2% / 0.16 / 0.26 / -25% | 0.30% | disagrees with EMLC on index construction; better in-sample IR |
| 7 | TGEIX TCW EM Income | active hard-currency | 7.6% / 0.95 / 0.81 / -11% | 0.85% | best in-sample IR of the active funds |
| 8 | PYEMX Payden EM Bond | active hard-currency | 7.0% / 0.98 / 0.20 / -12% | 0.73% | second-highest composite; cheaper active alternative |

Near misses: EMHY (rank 3, overlaps HYEM), GSDIX (1.10 Sharpe, 0.83% fee),
JEMDX, PEBIX, FNMIX, LEMB (overlaps EMLC), DBLEX (blend, 0.91% fee). The bond
fundamental score rests on **current** yields and only partial duration and
rating inputs (`em_bond_inputs.csv`), so it is the least informative column
of this table; the in-sample ranking leans on returns. All EM bond funds
count fully as non-US under method.md section 3.

## Other sleeve: shortlist of 8

| Pick | Ticker | Category | In-sample CAGR / Sharpe / IR vs GLD / max DD | Non-US share | Why |
|---|---|---|---|---|---|
| 1 | IAU iShares Gold | gold | 1.9% / 0.19 / 0.52 / -43% | 0 | the proposal's archetype at a lower fee than GLD (0.25% vs 0.40%) |
| 2 | SLV iShares Silver | silver | -0.4% / 0.15 / 0.07 / -72% | 0 | precious metal with industrial demand; the high-volatility case |
| 3 | GSG iShares GSCI Commodity | broad commodities | -8.0% / -0.34 / -0.45 / -66% | 0 | the inflation-hedge case that lost money in-sample; included so the comparison tests the claim rather than assumes it |
| 4 | GNR SPDR Global Natural Resources | natural-resource equities | 1.9% / 0.19 / 0.13 / -47% | about 0.5 (by holdings, Phase 3 verifies) | equity route to commodities; partly non-US |
| 5 | VNQI Vanguard Global ex-US Real Estate | ex-US REITs | 7.8% / 0.57 / 0.44 / -22% | 1.0 | the only candidate that counts fully non-US and still diversifies; helps the 70% floor |
| 6 | IGF iShares Global Infrastructure | infrastructure | 7.3% / 0.61 / 0.24 / -16% | about 0.6 | lowest drawdown of the real-asset funds |
| 7 | SCHP Schwab US TIPS | US inflation-linked | 2.6% / 0.57 / 0.06 / -10% | 0 | cheapest TIPS fund (0.03%); the "security" candidate |
| 8 | WIP SPDR International Inflation-Linked | non-US inflation-linked | 2.7% / 0.32 / -0.01 / -18% | 1.0 | inflation protection that counts as non-US |

Near misses: WOOD (rank 1 by composite, but $0.2bn AUM at the screen floor and
an equity fund in all but name), RWO (73% US, no diversification), SPIP/TIP
(duplicates of SCHP), SGOL (duplicate of IAU), DJP (ETN credit risk), WTMF
(managed futures, negative in-sample Sharpe; stays in the data for the
report). BIL is the risk-free rate and is not a position.

Effect on the 70% rule: of the eight only VNQI and WIP count fully non-US, so
a 10% "other" sleeve built from gold, commodities and TIPS consumes a third
of the 30% US/neutral room before any US stock is bought. With three US
growth stocks the room left is about 20% for the US sleeve. This is the main
tension the Phase 5 optimizer has to resolve, and the reason the gold
treatment is listed as a question for John.

## Derivative overlays: 5 to model

From `longlists/overlays.csv` and `overlays_notes.md`:

| Overlay | Applied to | Proxy / model | Why |
|---|---|---|---|
| cc_spx_30d_1m | equity sleeve (index level) | CBOE BXMD (1986), Black-Scholes on realized vol + measured VIX-realized premium | the standard covered-call test |
| cc_spx_atm_1m | equity sleeve | CBOE BXM (2002), XYLD cross-check (2013) | at-the-money variant, more income less upside |
| pput_5pct_3m | equity sleeve | CBOE PPUT (1986), quarterly 5% OTM puts | the drawdown-control test |
| collar_cll_95_110 | equity sleeve | CBOE CLL (2008) | put financed by a call |
| fxfwd_emlocal_50pct_3m (and 100%) | EMLC/EBND exposure | covered interest parity from OECD 3-month rates (MXN, BRL, ZAR, INR, IDR, PLN, HUF, CZK, CLP, COP) | the FX-hedge test on the local-currency bonds |

Dropped before modelling, with the screener's reasons: single-stock covered
calls (a $5,000-$10,000 position cannot write a 100-share contract);
put-writing (adds exposure, breaks the overlay-only and 70% rules); index
futures for rebalancing (one micro contract is about $37,000 notional and
the cost saved on a $5,000 trade is a few dollars); interest-rate swaps
(OTC, out of reach). Practical note for Phase 3: at $100,000 the equity
overlays are only feasible with mini index options (XSP, one-tenth of SPX) or
on an ETF, and the analyst must size them that way.

## Data caveats carried into Phase 3

- NOVO-B.CO has doubled prices on a few 2005-2006 holiday days that the spike
  filter does not remove; they are before the 2010 backtest start.
- EM credit spread series from FRED start 2023-11, too short for anything but
  context.
- CSL.AX, IFX.DE and ICICIBANK.NS returned HTTP 404 from EDGAR (wrong or
  retired CIKs); no point-in-time fundamentals for them.
- Fund AUM and expense ratios are today's figures.
- Turkish yields: spot quotes only, as before.
