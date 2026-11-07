# US growth stocks: adversarial review (Phase 4)

Reviewer: opus, 2026-11-07. Verification code: `python -m research.reviews.us_growth_check`
(add `--reproduce` to re-run the analyst's `analyse()` in memory and diff every JSON field).
Machine-readable version: `reports/candidates/reviews/us_growth_review.json`.

## Verdicts

| Name | Analyst | Review | Decisive evidence |
|---|---|---|---|
| NVDA | keep, rank 1 | **pass** | Sharpe 1.110, IR 1.043, t 3.10 (Newey-West 2.75); IR positive in both halves (2018-22 0.63, 2023-26 1.64) and in all 71 OOS 36-month windows |
| AVGO | keep, rank 2 | **pass** (fix the wording) | Sharpe 0.978, IR 0.724, t 2.15; 71/71 OOS windows IR>0 (min 0.27). Its #1 in-sample rank used FY2025 fundamentals; it would still rank 5th |
| MA | keep, rank 3 | **downgrade** | Sharpe 0.721 < IVW 0.775, IR 0.137 (t 0.41). 2022 -8.1% vs -27.4%, but Covid -23.5% vs IVW -16.4%; 2023-26 IR -0.26 |
| AMZN | runner-up | pass | alpha -0.2% (t -0.03), DD -52.1% |
| META | runner-up | pass | DD -75.4%, 2022 -72.3%, IR 0.169 (t 0.50) |
| REGN | drop | fail (agree) | Sharpe 0.397, IR -0.036: rule 8.2 |
| GILD | drop | fail (agree) | Sharpe 0.568, IR -0.019: rule 8.2 |
| ADBE | drop | fail (agree) | Sharpe 0.214, IR -0.259, DD -69.4% |

## Recomputed vs analyst (OOS 2018-01-31 to 2026-10-31, 106 months)

My numbers come from my own numpy code. Prices are read with `read_wide_csv`, I take the last close of each calendar month, and I drop the partial month 2026-11. The analyst used the same convention. Every value below matches the JSON to within 1e-6.

| | Sharpe | IR (t) | Alpha (t) | Max DD | DSR | 2022 | Covid |
|---|---|---|---|---|---|---|---|
| NVDA | 1.110 | 1.043 (3.10) | 26.1% (2.30) | -62.8% | 0.840 | -54.1% | +11.6% |
| AVGO | 0.978 | 0.724 (2.15) | 18.6% (1.85) | -31.7% | 0.757 | -27.7% | -21.0% |
| MA | 0.721 | 0.137 (0.41) | 7.5% (1.06) | -26.2% | 0.457 | -8.1% | -23.5% |
| AMZN | 0.576 | 0.193 (0.57) | -0.2% (-0.03) | -52.1% | 0.290 | -38.6% | -2.9% |
| META | 0.513 | 0.169 (0.50) | 2.2% (0.21) | -75.4% | 0.237 | -72.3% | -17.4% |
| GILD | 0.568 | -0.019 (-0.06) | 11.4% (1.36) | -29.4% | 0.277 | +12.1% | +19.4% |
| REGN | 0.397 | -0.036 (-0.11) | 11.9% (1.05) | -58.5% | 0.138 | +18.6% | +44.5% |
| ADBE | 0.214 | -0.259 (-0.77) | -8.7% (-0.92) | -69.4% | 0.054 | -43.8% | -9.4% |
| IVW | 0.775 | - | - | -30.5% | 0.518 | -27.4% | -16.4% |
| QQQ | 0.845 | 0.562 (1.67) | | -32.6% | 0.598 | -29.8% | -12.9% |

Without the spike filter the results are the same, except AVGO's Sharpe moves from 0.978 to 0.986. The filter blanks two genuine AVGO trading days, 2020-03-18 and 2024-07-31. The second is a month end. The difference does not change any conclusion.

## Methodology findings, by severity

1. **The in-sample screen used later information (affects AVGO, but the shortlist would be the same).** AVGO's 2017 fundamental score is half of the composite. It was built from current yfinance statements (FY ending 2025-10-31, `fundamentals_pit` False). BKR and MRVL have the same problem. The universe also uses 2026 index membership and today's market cap. So the memo line "a screen using only data to 2017 picked it" is not true for AVGO. With a neutral fundamental score AVGO ranks 5th instead of 1st, which is still inside the top 8.
2. **The Grinold-Kroner repricing term compares two different P/E measures (forward estimates are inflated).** The target P/E is anchored on trailing GAAP medians, capped at 23. The cap is the median of the config.py targets, which have no external source. The starting point is Yahoo's forward non-GAAP P/E. Forward EPS divided by trailing EPS is 2.49 for AVGO, 2.01 for NVDA, 1.56 for REGN and 1.53 for ADBE. As a result, repricing adds 4.3 to 10.2 points a year for these four names. Consensus without repricing: AVGO 13.0% (headline 14.4%), NVDA 13.6% (15.3%), ADBE 13.1% (16.5%). If G-K starts from the trailing P/E instead: AVGO 11.4%, NVDA 13.0%. The ADBE claim is right, and the DCF adds to the effect: ADBE's DCF gives 19.4% with +207% upside, because it starts from forward EPS that is 1.53x trailing EPS.
3. **Monte Carlo edge effect: the analyst's suspicion is correct.** In `research/montecarlo.py`, `bootstrap_paths` draws block start points from [0, T-block] without wrapping around. The first and last months can therefore only appear in a few blocks. They are drawn 1/6 as often as a middle month (empirical check: 0.17). This alone moves the implied median by -1.4 to +2.2 points. It explains +2.2 of NVDA's +2.6 gap between median and consensus, and +2.2 of META's +2.3. It affects the medians, the 5-95% ranges and Phase 5 if Phase 5 uses this module. It does not affect the consensus, which excludes the Monte Carlo.
4. **The control-group claims are right, but one label is wrong.** 9 of 46 passers (19.6%) beat IVW. Spearman correlation is 0.147 (p 0.33). The faded-leader median Sharpe is 0.136, and Biogen went from 10th in-sample to 45th out of sample. All of these match. But "near misses LRCX, PANW, FTNT, APH placed 3rd-6th OOS" is mislabelled. Only LRCX (in-sample rank 7) is a near miss in shortlist.md. PANW, FTNT and APH ranked 19th, 29th and 32nd in-sample. Of the 10 best out-of-sample names, the in-sample ranks were 9, 1, 32, 19, 29, 7, 21, 8, 23 and 30. The shortlist's median OOS Sharpe (0.572) equals the median of all passers. The names swapped in (NVDA, MA, GILD: median 0.72) did worse than the names swapped out (FANG, LRCX, ORLY: 0.82). The summary file labels the Spearman result `predictive: true`, but a p-value of 0.33 is not significant.
5. **AVGO ROE bug: confirmed, and it does not change the shortlist.** In `research/screen/cli.py` (line 27 `FIN_WORDS`, line 154), the word "financ" matches "yfinance" in the universe.csv notes. That tags AVGO, SIRI, KDP and GEN as financials. For AVGO, ROE was 28.4% where ROIC is 20.0%, and the net debt/EBITDA of 1.40 was skipped. Quality score falls from 0.659 to 0.506, fundamental score from 0.636 to 0.590, and the composite rank from 1 to 2 (META moves to first). SIRI drops from 17th to 25th. The top 8 is unchanged.
6. **Multiple testing.** Only NVDA's t clears a Bonferroni bar for choosing among the 8 names (one-sided z 2.24). AVGO's t of 2.15 and alpha t of 1.85 count as moderate evidence. NVDA's deflated Sharpe of 0.84 is below the conventional 0.95 bar. The deflated Sharpe itself is correctly computed: I checked it with N=46, T=106, and skew and kurtosis included. I also checked NVDA's t by hand: 1.0433/sqrt(12)*sqrt(106) = 3.10.
7. **Minor.** The USD stress episodes start at the end of the first month, so June 2014 and June 2021 are excluded. The snapshot date of info.json is not recorded.

Items checked and passed:
- Stress windows match method.md section 11 exactly.
- The benchmark is IVW total return, with QQQ shown.
- Dividends are included: GILD returns 14.4% a year with dividends vs 10.3% price-only.
- No fees or trading costs apply.
- Everything is in USD, and the local blocks equal the USD blocks.
- The explain sentences 2-3 match the JSON for all 8 names.

## Memo overclaims

- AVGO: "best risk-adjusted name for the security budget". Its -31.7% drawdown breaks the -25% budget.
- MA: "defensive". This holds in the 2022 window only. MA fell more than IVW in Covid.
- All eight names, sentence 1, "using only data to 2017". Not true for AVGO's fundamentals, or for the universe.

## Recommended changes

See `recommended_changes` in the JSON. In short:
- Reword AVGO's and MA's verdicts.
- Correct the near-miss label.
- Report the forward consensus without the repricing term before scoring the forward-return component.
- Relabel the Spearman result as not significant.
- Fix FIN_WORDS in a later run, through the change log.
- Fix the bootstrap edge effect before Phase 5.
