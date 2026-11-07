# Phase 4 scorecard: rubric, reviews, picks and runners-up

Written 2026-11-07 after the Phase 3 deep research and the five adversarial
reviews. Numbers come from `reports/candidates/scorecard.csv`, produced by
`python research/plan/scorecard.py --write`, which applies method.md section 7
mechanically to `reports/candidates/<ID>.json` and merges the reviewer
verdicts from `reports/candidates/reviews/<type>_review.json`. The same
command writes the `rubric` and `review` blocks into each candidate file.

Out-of-sample (OOS) is 2018-01-31 to 2026-10-31, monthly, USD, risk-free BIL.
Benchmark OOS Sharpe: IVW 0.78, EFG/EEM 50-50 0.27, EMB 0.02, EMLC -0.10,
GLD 0.67.

## How the ranking was formed

1. Rubric (section 7): percentile within type of OOS Sharpe (20), OOS IR (15),
   OOS max drawdown (10), consistency = share of rolling 36-month windows with
   IR above zero (10), diversification = mean OOS correlation with the other
   sleeves' benchmarks (10), inflation = 2021-12 to 2022-10 return (5),
   liquidity and cost = OOS average daily traded value and expense ratio (5),
   forward 7-year expected return (15), in-sample fundamental score (5).
   The technical weight (5) was redistributed because no signal was kept
   (section 6 result, see shortlist.md).
2. Drop rule 8.2: OOS Sharpe below the type benchmark **and** OOS IR below
   zero. Applied before the reviewer verdicts.
3. Reviewer verdicts: "fail" = dropped; "downgrade" = ranked after every pass
   in its type and only picked if the type has fewer passes than slots.
4. Picks = the top 3 / 3 / 4 / 1-3 by that order; runners-up = the next two
   (rule-8.2 casualties may be runners-up only where the type has fewer than
   five survivors, section 13 clarification).

## Review summary (what survived and what did not)

Every reviewer reproduced every analyst number byte-for-byte or to 1e-6 after
an independent recomputation. The findings that changed results were code
and labelling problems, all fixed and rerun before this scorecard:

| Finding | Severity | Fix |
|---|---|---|
| Grinold-Kroner repricing mixed a forward non-GAAP P/E with a trailing GAAP target, inflating four US forward estimates by 4-10 points | high | both ends now trailing GAAP; AVGO 14.4% to 11.4%, NVDA 15.3% to 13.0%, ADBE 16.5% to 15.0% |
| EM bond yields had the fund fee subtracted twice (SEC yields are net) | high | removed; forward estimates up 0.3-0.9 points |
| Mexico's 10-year yield gaps were spliced, flipping the peso's sign in the country table | high | gaps of at most 3 months forward-filled, longer gaps dropped |
| Screening CLI tagged Broadcom, Sirius, KDP and Gen Digital as financials (substring "financ" matched "yfinance") | medium | whole-word match; Broadcom in-sample rank 1 to 2, shortlist unchanged |
| `research/montecarlo.py` under-sampled the first and last months (non-circular blocks) | medium | circular bootstrap; medians move up to about 2 points; consensus never used the Monte Carlo |
| "Gold has a negative inflation beta" | medium | not supported under any lag (no t above 1.65); memos say "no detectable relationship" |
| US "near misses placed 3rd-6th OOS" | low | only LRCX and ORLY were near misses; corrected |
| Rank-test labels "predictive: true" at p 0.3-0.9 | low | relabelled "positive, not significant" |

Findings that could not be fixed and are carried as caveats: 22 of 31
international passers (including all eight shortlisted) were screened on
current statements, not point-in-time, because they do not file with the SEC
(method.md section 4 allowed this with a flag; the reviewer rates it the most
serious weakness of the international shortlist); home indices for the local
view are price indices, flattering local IRs by 1-4%/yr; the EM bond forward
estimates rest on one method (the Monte Carlo is anchored to the yield
drift); the model covered-call return runs 0.9%/yr above the CBOE indices
OOS, which flatters covered calls but not drawdown.

## In-sample ranking vs out-of-sample results (the honest headline)

| Type | Spearman rho, in-sample composite vs OOS Sharpe (p) | What it means |
|---|---|---|
| US growth (46 passers) | +0.14 (0.36) | positive, not significant; shortlist median OOS Sharpe equals the median of all passers; faded leaders fell from ranks 10-18 to 43-46 |
| International (31) | -0.02 (0.93) | no predictive value; ASML (0.84, t 2.8) and Petrobras were the best OOS names and were not shortlisted |
| EM bonds (20) | +0.20 (0.42) | none; three non-shortlisted funds beat every pick on OOS Sharpe |
| Other (33) | +0.13 (0.48); in-sample Sharpe vs OOS Sharpe -0.59 | the in-sample losers (commodities) won OOS; the fundamental score alone had +0.50 (p 0.004) |

The 2017 screen did not find the 2018-2026 winners in any sleeve. The picks
below therefore lean on the forward models, drawdown and the reviewer
verdicts as much as on the OOS ranking, as method.md section 7 says they must
when the rank test fails.

## US growth stocks (3 spots; benchmark IVW, OOS Sharpe 0.78)

| Rank | Ticker | OOS Sharpe | OOS IR (t) | OOS max DD | 2022 | 7y E[R] | Rubric | Review | Decision |
|---|---|---|---|---|---|---|---|---|---|
| 1 | AVGO | 0.98 | 0.72 (2.2) | -32% | -28% | 11.4% | 76.2 | pass | **pick** |
| 2 | NVDA | 1.11 | 1.04 (3.1) | -63% | -54% | 13.0% | 74.5 | pass | **pick** |
| 3 | AMZN | 0.58 | 0.19 (0.6) | -52% | -39% | 8.1% | 59.0 | pass | **pick** |
| 4 | META | 0.51 | 0.17 (0.5) | -75% | -72% | 10.1% | 47.5 | pass | runner-up |
| 5 | MA | 0.72 | 0.14 (0.4) | -26% | -8% | 8.8% | 57.7 | downgrade | runner-up |
| 6 | GILD | 0.57 | -0.02 | -29% | +12% | 8.3% | 53.5 | fail (8.2) | dropped |
| 7 | ADBE | 0.21 | -0.26 | -69% | -44% | 15.0% | 41.0 | fail (8.2) | dropped |
| 8 | REGN | 0.40 | -0.04 | -59% | +19% | 7.2% | 40.6 | fail (8.2) | dropped |

Why the runners-up lost: META's -75% drawdown and -72% in 2022 are the worst
of the type; its forward estimate (10.1%) does not compensate. MA has the
smallest drawdown and the best 2022, but the reviewer downgraded the
"defensive" label (it fell -23.5% in the Covid window vs -16% for IVW) and its
IR is 0.14 (t 0.4), so under the pre-registered rule it ranks after the three
passes. It is the natural substitute if John wants a lower-volatility US
sleeve. Only NVDA and AVGO beat IVW on OOS Sharpe, and NVDA's edge is one
regime with a -63% drawdown: the Phase 5 optimizer must keep it small.

## International growth stocks (3 spots; benchmark EFG/EEM 50-50, OOS Sharpe 0.27)

| Rank | Ticker | Country | OOS Sharpe | OOS IR (t) | OOS max DD | FX /yr | 7y E[R] USD | Rubric | Review | Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2330.TW TSMC | TW | 0.96 | 1.13 (3.4) | -46% | -1.0% | 10.9% | 76.5 | pass | **pick** |
| 2 | BAJFINANCE.NS | IN | 0.51 | 0.43 (1.3) | -58% | -4.4% | 11.1% | 63.7 | pass | **pick** |
| 3 | CSU.TO Constellation | CA | 0.64 | 0.51 (1.5) | -52% | -1.2% | 8.7% | 56.7 | pass | **pick** |
| 4 | REA.AX | AU | 0.34 | 0.24 (0.7) | -41% | -1.2% | 9.9% | 55.1 | pass | runner-up |
| 5 | NOVO-B.CO | DK | 0.30 | 0.16 (0.5) | -74% | -0.8% | 7.9% | 42.9 | pass | runner-up |
| 6 | 000660.KS SK Hynix | KR | 0.73 | 0.76 (2.3) | -53% | -2.4% | 12.4% | 76.8 | downgrade | not picked |
| 7 | 1299.HK AIA | HK | 0.17 | 0.01 (0.0) | -45% | 0.0% | 9.2% | 42.6 | downgrade | not picked |
| 8 | 0700.HK Tencent | CN | 0.12 | -0.01 | -69% | 0.0% | 10.6% | 35.7 | 8.2 | dropped |

TSMC is the only international name whose edge clears the multiple-testing
bar (t 3.4 against a 2.95 threshold for 31 trials; deflated Sharpe 0.78).
Bajaj and Constellation pass with weak evidence (t 1.3 and 1.5) and carry the
INR and a -52% 2025-26 drawdown respectively. **SK Hynix is the judgement
call for John:** it has the highest rubric total of the type (76.8) and real
OOS numbers (t 2.3), but the reviewer downgraded it because its shortlist slot
came from a fundamental score built on 2025 statements (on price alone it
ranked 19th of 31 in-sample). The pre-registered rule ranks a downgrade after
every pass, which puts REA and Novo ahead of it as runners-up. If John accepts
the look-ahead caveat (it applies to all eight international names, not only
SK Hynix), SK Hynix should replace Novo as a runner-up or Constellation as a
pick. Tencent fails rule 8.2 outright.

## EM bond funds (4 spots; benchmark EMB, OOS Sharpe 0.02; local funds EMLC, -0.10)

| Rank | Ticker | Sub-type | OOS Sharpe | OOS IR (t) | OOS max DD | 7y E[R] | Rubric | Review | Decision |
|---|---|---|---|---|---|---|---|---|---|
| 1 | PYEMX Payden | active hard-ccy | 0.10 | 0.29 (0.9) | -28% | 6.6% | 76.5 | pass | **pick** |
| 2 | CEMB | IG corporate | 0.07 | 0.09 (0.3) | -20% | 6.0% | 69.2 | pass | **pick** |
| 3 | EMB | hard-ccy sovereign, passive | 0.02 | -0.76 vs GUIDE_BENCH (-2.3) | -27% | 6.3% | 52.6 | pass | **pick** |
| 4 | HYEM | EM high yield | 0.13 | 0.22 (0.7) | -26% | 5.6% | 78.0 | downgrade | **pick** (fourth slot) |
| 5 | TGEIX TCW | active hard-ccy | 0.07 | 0.17 (0.5) | -28% | 5.9% | 61.7 | downgrade | runner-up |
| 6 | EMLC | local-ccy sovereign | -0.10 | -0.83 vs GUIDE_BENCH | -26% | 4.7% | 33.7 | downgrade | runner-up |
| 7 | PCY | equal-weight sovereign | -0.01 | -0.09 | -36% | 5.7% | 45.2 | fail (8.2) | dropped |
| 8 | EBND | local-ccy (Bloomberg) | -0.14 | -0.12 | -28% | 4.8% | 33.1 | fail (8.2) | dropped |

No EM bond fund has a convincing OOS record: every Sharpe is between -0.14
and 0.13 and every deflated Sharpe is at most 0.07, because 2018-2026
contained the 2022 rate shock and a strong dollar. The funds cannot be told
apart on returns, so the picks follow cost, drawdown and the forward yield.
HYEM takes the fourth slot only because the type has three passes for four
spots; the reviewer's downgrade (its lead over PYEMX is 0.035 of Sharpe) is
recorded. No local-currency fund is picked: EMLC's local bonds earned 3.3%/yr
OOS but the currencies took -2.3%/yr and hedging would have cost 2.8%/yr.
EMLC stays a runner-up because the FX-hedge overlay was tested on it.

## Other sleeve (1-3 spots; benchmark GLD, OOS Sharpe 0.67)

| Rank | Ticker | OOS Sharpe | OOS IR vs GLD (t) | OOS max DD | 2022 | Corr ACWX | 7y E[R] | Rubric | Review | Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | IAU gold | 0.68 | n/a (same asset; 0.44 vs GUIDE_BENCH) | -26% | -11% | 0.35 | 5.3% | 81.6 | pass | **pick** |
| 2 | SLV silver | 0.44 | 0.15 (0.5) | -47% | -18% | 0.45 | 3.1% | 64.6 | pass (weak) | **pick** |
| 3 | GNR natural resources | 0.38 | -0.13 | -36% | +3% | 0.80 | 7.3% | 66.5 | 8.2 | runner-up |
| 4 | IGF infrastructure | 0.37 | -0.25 | -30% | -6% | 0.82 | 7.2% | 59.0 | 8.2 | runner-up |
| 5 | GSG commodities | 0.41 | -0.04 | -53% | +28% | 0.35 | 1.3% | 55.3 | 8.2 | dropped |
| 6 | SCHP US TIPS | 0.04 | -0.71 | -14% | -13% | 0.53 | 4.8% | 49.2 | 8.2 | dropped |
| 7 | VNQI ex-US REITs | -0.07 | -0.63 | -33% | -31% | 0.89 | 8.0% | 45.6 | 8.2 | dropped |
| 8 | WIP intl linkers | -0.15 | -0.88 | -23% | -20% | 0.81 | 5.4% | 33.0 | 8.2 | dropped |

Gold set a high bar in 2018-2026 and six of eight candidates fail rule 8.2
against it. The sleeve that survives is precious metals only. Two facts for
John: gold was **not** an inflation hedge in this sample (it lost 11% in the
2022 window and shows no detectable CPI beta), it was a diversifier
(correlation 0.35 with world ex-US stocks); and the only asset that behaved as
an inflation hedge, broad commodities (GSG, +28% in 2022), lost money over
every other window and is dropped. Under method.md section 3 both picks count
as US-neutral, so a 10% gold-and-silver sleeve leaves about 20% of the
portfolio for the three US stocks.

## Derivative overlays (section 8 item 5, tested at portfolio level in Phase 5)

| Overlay | OOS effect on the SPY sleeve (exact 100% ratio) | Standalone 8.5 | Review | Phase 5 use |
|---|---|---|---|---|
| cc_spx_30d_1m | Sharpe 0.75 to 0.60, DD -23.9% to -23.8% | fails | fail (uncovered at 139%, model 0.9%/yr too kind) | not used |
| cc_spx_atm_1m | Sharpe to 0.31, DD worse | fails | fail | not used |
| pput_5pct_3m | Sharpe 0.75 to 0.77, DD -23.9% to -17.6% | passes on drawdown | downgrade (fails on a 55/35/10 proxy) | **test only**, `overlay_return_h100` scaled to the equity sleeve, with and without |
| collar_cll_95_110 | Sharpe to 0.51, DD -15.6% | passes on drawdown | fail (uncovered short call at 1 contract) | not used |
| fxfwd EMLC 50% / 100% | DD -25.5% to -20.7% / -16.1%, Sharpe worse, carry given up 1.4% / 2.7%/yr | drawdown only | downgrade (not tradeable at retail) | not used (EMLC not picked) |

Calibration was honest: parameters fitted on 2010-2017 and frozen; the
measured volatility risk premium was 4.0 vol points in-sample and 3.7 OOS.
Only the protective put goes into Phase 5, and only as a with/without test;
at $100,000 one XSP contract is 139% of the equity sleeve, so the achievable
hedge ratio is 0% or 139%, which the report must say.

## Final list for Phase 5

Picks: AVGO, NVDA, AMZN; 2330.TW, BAJFINANCE.NS, CSU.TO; PYEMX, CEMB, EMB,
HYEM; IAU, SLV. Runners-up (sensitivity portfolios): META, MA; REA.AX,
NOVO-B.CO (SK Hynix pending John); TGEIX, EMLC; GNR, IGF. Overlay test:
pput_5pct_3m.

Non-US share of the picks under method.md section 3: the six international
and EM positions count 1.0 (nine instruments), the three US stocks and the
two metals count 0. The 70% floor therefore binds exactly on the US stocks
plus the other sleeve at 30%, with equity 55% split roughly 20% US / 35%
international and bonds 35%. If John reclassifies gold as neutral, the
optimizer gets 10 points of room back.
