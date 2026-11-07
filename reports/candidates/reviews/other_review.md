# Adversarial review: other sleeve (10%)

Reviewer: opus, 2026-11-07. Verification: `python -m research.reviews.other_check` (source `research/reviews/other_check.py`). Machine-readable version: `reports/candidates/reviews/other_review.json`.

## Reproduction: pass

- `python -m research.candidates.other_sleeve --all --write` rewrote all 8 JSONs, 8 memos, `other_control.csv` and `other_control_rank.json`. They are byte-identical to a snapshot taken before the run.
- I recomputed the out-of-sample (OOS) numbers independently with plain pandas on `data/research/prices.csv` (month-end last price, `pct_change`, partial November 2026 dropped, OOS 2018-01-31 to 2026-10-31, 106 months). I did this both on the raw prices and through `read_wide_csv`. For all 8 funds, OOS Sharpe, IR vs GLD and max drawdown match to 4 decimals. So do the 2021-12 to 2022-10 returns for all 8, and the OOS correlations with ACWX, EMB and GLD for GSG, GNR, IGF and IAU.
- I rebuilt GUIDE_BENCH (quarterly reset) and CPI+2% myself. The IRs for IAU, GSG and SCHP match the JSON: IAU +0.444 / +0.530, GSG +0.232 / +0.270, SCHP -0.404 / -0.550.

## Per-fund verdicts

| Fund | OOS Sharpe | IR vs GLD | Max DD | 2022 | Rule 8.2 | Verdict |
|---|---|---|---|---|---|---|
| IAU | 0.683 | null (fee only: would be 0.51 on 0.28% tracking error) | -26.4% | -11.0% | passes, but only by fee (GLD 0.673) | pass |
| SLV | 0.440 | +0.151 (t 0.45) | -47.5% | -18.1% | survives through IR alone | pass (weak) |
| GSG | 0.411 | -0.042 | -53.2% | +27.7% | triggered | fail |
| GNR | 0.381 | -0.132 | -35.5% | +3.4% | triggered | fail |
| IGF | 0.368 | -0.250 | -29.6% | -6.1% | triggered | fail |
| VNQI | -0.069 | -0.633 | -32.7% | -30.7% | triggered | fail |
| SCHP | 0.036 | -0.710 | -13.8% | -12.6% | triggered | fail |
| WIP | -0.146 | -0.880 | -23.4% | -19.9% | triggered | fail |

GSG, GNR and IGF also trigger rule 8.2: Sharpe below 0.673 and IR below zero. The memos say so ("TRIGGERED, runner-up at best"). So six of the eight fail, not three.

## Findings by severity

### High

1. **How the 8.2 runner-up clause is counted.** The memos read it on the 8-fund shortlist, where only 2 funds survive, so the six failures can stay as runners-up. Read on the 33-fund long list, there are 5 survivors besides GLD (IAU, SGOL, SIVR, SLV, IGE). Under that reading the six cannot even be runners-up. Either way, everything that survives is precious metal, plus IGE at IR +0.01. The method should state which count applies.

2. **The inflation betas do not support the conclusion "gold is not an inflation hedge".** `inflation_beta` (fundamental.py lines 273-288) regresses the return in month t on the change in year-on-year CPI for the same reference month t. That CPI print is published in month t+1. Results for IAU under different definitions:

   | IAU, definition | In-sample beta (t) | OOS beta (t) |
   |---|---|---|
   | Analyst's: change in YoY, same month | -1.09 (-0.64) | -1.10 (-1.00) |
   | Same, with CPI paired to its release month | **+2.04 (+1.27)** | -1.40 (-1.28) |
   | Month-on-month surprise | +0.09 (+0.04) | -0.89 (-0.54) |
   | YoY level | +0.51 (+0.92) | -0.30 (-1.40) |

   - GLD over its full history (259 months): +0.16 (t 0.25). The correlation of calendar-year gold returns with CPI inflation, 2005-2025, is +0.05.
   - No definition reaches |t| of 1.65. The defensible statement is "no detectable monthly CPI relationship". Gold's -11% in 2022 and its OOS slope on real-yield changes (-8.0, t -4.4) are the real evidence.
   - **"Silver has a negative inflation beta" is wrong.** SLV's own JSON shows +1.04 in-sample and +0.004 OOS.
   - GSG's large positive beta (OOS +5.75, t 3.8) is contemporaneous co-movement with the energy part of CPI. It disappears when CPI is paired with its release month (-0.13).
   - SCHP is mis-measured: TIPS indexation uses CPI with about a 3-month lag, so the contemporaneous beta (and OOS month-on-month -1.12, t -2.2) is a timing artefact.

### Medium

3. **The two IAU expected-return methods.**
   - The 0.6% figure is the real-yield model: (1 - 2.60% + 1.00%)(1 + 2.23%) - 1. The 10.0% figure is the 2005-2026 real CAGR (7.58%) plus breakeven. The 5.3% consensus is their mean.
   - I back-tested the real-yield model on GLD over 166 overlapping 7-year windows. Its predictions correlate -0.55 with what gold actually returned, and it under-predicts by 3.0 points on average.
   - OOS, the 10-year real yield rose from -1.04% to 2.60% while GLD gained 108%.
   - The midpoint hides that neither method is reliable. Report it as a range.
   - The Monte Carlo is not averaged into the consensus (other_sleeve.py lines 294-302), so nothing is double counted. Its 5-95 band reflects the fund's own history only, not model uncertainty.

4. **Rank-test p-values are overstated by near-duplicate funds.** The 33 funds include 8 TIPS funds, 3 gold clones and 4 precious-metal baskets. Repeating the tests on the 13 category means:

   | Test | All funds | 13 category means |
   |---|---|---|
   | In-sample Sharpe vs OOS Sharpe | -0.59 (p 0.0003) | -0.55 (p 0.052) |
   | Fundamental score vs OOS Sharpe | +0.50 (p 0.004) | +0.65 (p 0.017) |
   | Composite vs OOS Sharpe | +0.13 (p 0.48) | +0.21 (p 0.49) |

   - The fundamental-score result holds up; the in-sample Sharpe result is much weaker than p 0.0003 suggests.
   - The fundamental score's link to OOS Sharpe comes from its correlation component (+0.46) and inflation component (+0.45). The cost component goes the other way (-0.25).
   - `other_control.csv` still contains the fee-only IRs vs GLD for IAU (0.507) and SGOL (0.471); line 461 nulls only GLD. Removing them cuts composite vs OOS IR from +0.25 to +0.12.

5. **Other forward models.**
   - **GSG:** the collateral model gives 4.42% (3.94% + (-1%) + 2.23% - 0.75%). GSG's realised history from 2006-08 implies a roll plus real-spot drag of -5.5% a year: CAGR -1.55% vs BIL 1.40% and CPI 2.55%. The -1% roll assumption is optimistic. With roll at -3% or -5%, the consensus falls to about 0.3% or -0.7%.
   - **WIP:** the "real yield" term (nominal minus CPI) plus CPI equals the nominal yield exactly. So it is a nominal-bond model, and it covers only 26% of the fund, with Brazil weighted 30% instead of 8%.
   - **SCHP:** the second method is the trailing yield, which reflects past CPI accruals rather than a forecast.
   - **GNR, IGF, VNQI:** the Grinold-Kroner and CAPM models reproduce exactly. Their growth assumptions are labelled as judgement.

### Low

6. US_CPI has no 2025-10 value. The code drops missing values before differencing (fundamental.py line 280; other_sleeve.py lines 106 and 129), so the 2025-11 observation is a two-month change counted as one month.
7. The deflated Sharpe uses V = 1/(T-1), which is conservative here. With the measured variance of the 32 OOS Sharpes, IAU's deflated Sharpe is 0.69 instead of 0.46. Neither is close to 0.95. IAU's t-stat on mean excess return is 2.03.
8. Look-ahead and survivorship: the composite uses in-sample columns only. However, the cost score and the AUM hard screen use today's figures (flagged in `other_scored.csv`), and funds that closed after 2017 are missing from the universe.
9. Non-US shares follow method.md section 3 and name their sources:
   - 0 for gold, commodities and SCHP.
   - GNR 0.65 (SSGA factsheet 2026-09-30, US 35.20%).
   - IGF 0.64 (iShares page 2026-11-05, US 36.15%).
   - WIP 1.00 (factsheet; no US in the country table).
   - VNQI 1.00 by index name only, not verified from holdings.
   - shortlist.md had said about 0.5 / 0.6 for GNR / IGF. The JSON notes this.
10. Memos: the "How to explain this pick" sentences match the JSON for all 8, since they are generated from it. The hard-coded ROLE text (other_sleeve.py lines 533-542) overclaims:
    - IAU is called an "inflation ... diversifier", despite a beta of -1.1 and -11% in 2022.
    - WIP is called "inflation protection", despite -19.9% in 2022.
    - IGF's "smallest in-sample drawdown of the real-asset funds" is true on the shortlist, but GII (-15.8% vs -16.4%) is lower on the long list.

## Recommended changes (analyst; no pre-registered rule changed)

See `recommended_changes` in the JSON. In short:
- State which survivor count rule 8.2 uses.
- Rewrite the inflation-hedge wording and show t-stats beside every inflation beta.
- Use lagged CPI for SCHP and WIP.
- Show the IAU expected return as a 0.6% to 10.0% range.
- Null the fee-only IRs of IAU and SGOL in the control table and add category-clustered rank tests.
- Add GSG roll sensitivity.
- Fix the missing-CPI gap.
