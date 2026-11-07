# Review: international growth stocks (adversarial, opus, 2026-11-07)

Checks: `python -m research.reviews.intl_growth_check` (about 75 s). It recomputes everything from `data/research/*.csv` and does not import the analyst's metrics code. The only exception is the SK Hynix mid-cycle sensitivity, which reruns the analyst's own forward pipeline with the parameter changed in memory. Machine-readable version: `intl_growth_review.json`.

## Reproduction

- I ran `python -m research.candidates.intl_growth --all --write` after copying the outputs. All 8 JSONs, 8 memos, `intl_growth_control.csv` and the summary came out byte-identical (checked with `cmp`).
- The independent recompute covers all 8 names plus the benchmark. It uses local adjusted closes through `read_wide_csv`, multiplies by USD-per-unit FX forward-filled onto the price dates, samples at month-end, and covers 2018-01-31 to 2026-10-31 (106 months).
- Every Sharpe, IR, t, max DD, CAGR, DSR, fx_return, hedge_cost and hedged-minus-unhedged figure matches at the printed precision.
- Turning the spike filter off changes nothing.

| | Sharpe | IR (t) | max DD | DSR | verdict |
|---|---|---|---|---|---|
| Benchmark 50/50 EFG+EEM | 0.273 | - | -33.0% | - | correct; ACWX 0.364 shown |
| 2330.TW TSMC | 0.959 | 1.127 (3.35) | -46.3% | 0.783 | **pass** |
| 000660.KS SK Hynix | 0.735 | 0.757 (2.25) | -53.0% | 0.540 | **downgrade** |
| CSU.TO Constellation | 0.644 | 0.506 (1.50) | -51.9% | 0.429 | pass (runner-up) |
| BAJFINANCE.NS Bajaj | 0.511 | 0.433 (1.29) | -58.5% | 0.285 | pass (runner-up) |
| REA.AX REA | 0.339 | 0.244 (0.73) | -41.1% | 0.139 | pass (not a pick) |
| NOVO-B.CO Novo | 0.305 | 0.158 (0.47) | -73.8% | 0.132 | pass (not a pick) |
| 1299.HK AIA | 0.165 | 0.007 (0.02) | -45.1% | 0.052 | downgrade (do not pick) |
| 0700.HK Tencent | 0.119 | -0.011 (-0.03) | -69.1% | 0.040 | drop, rule 8.2 confirmed |

## Findings by severity

**High: the in-sample composite contains look-ahead, and it hits the candidates and the faded leaders unevenly.**
- `research/plan/longlists/intl_growth_stock_scored.csv` labels the scores `as_of 2017-12-31`. But all 8 shortlisted names carry `fundamentals_pit False`, `fy_end 2025-12-31` and `fy_filed 2026-03-31`.
- All 4 faded leaders are point-in-time on FY2016.
- The fundamental score is 50% of the composite.
- Ranked on price alone (0.5 pct IS Sharpe + 0.5 pct IS IR), SK Hynix falls to 19th, Novo to 9th and AIA to 11th. DOL.TO, Keyence and Naspers move into the top 8.
- SK Hynix's 0.83 fundamental score comes from FY2025 HBM-boom numbers: net-income CAGR 168%, operating margin 49%.
- Its OOS result is therefore not a clean out-of-sample selection.
- This is a Phase 2 issue (planner's screen), not the analyst's code. Since the rank correlation is about zero, the composite carried no information either way.

**Medium**
1. *The hedging claim is true for 2018-26 but comes from the dollar, not from carry.*
   - The CIP formula is correct (`intl_growth.py` `hedged_returns`): u + fp - f - 5 bp, with fp = (1+US_3M/12)/(1+loc_3M/12) - 1, both rates lagged one month.
   - Carry was a cost for AUD (0.31%/yr), KRW (0.20%), CAD (0.13%) and INR (3.42%). It was a gain only for DKK (0.89%) and TWD (0.25%).
   - Bajaj: the forward priced a 2.82%/yr rupee fall, and the realised fall was 4.38%/yr. The +2.2% gain is therefore a UIP failure of 1.56%/yr.
   - The rest of each gain is variance drag avoided, 0.36-1.32%/yr.
2. *SK Hynix's forward consensus of 12.4% rests on peak EPS.*
   - Forward P/E is 2.73 = 1,277,000 / FY2027 consensus EPS of 467,761 (39 analysts). That EPS is 7.7x FY2025.
   - The mid-cycle fade is applied, but 50% of forward is still 3.9x FY2025.
   - Rerunning the pipeline: mid-cycle 0.35 gives a consensus of 11.0%, and 0.25 gives 10.0% (G-K 4.6%, DCF 8.8%).
3. *Multiple testing.*
   - The Bonferroni bar for 31 trials is t > 2.95. Only TSMC clears it (3.35); SK Hynix is at 2.25.
   - No name reaches DSR 0.95 under V = 1/(T-1). With the measured V = 0.00506, TSMC's DSR is 0.915.
   - The rank test reports `predictive: True` at rho 0.008 (p 0.96). Under the letter of the rule that is correct, but in substance the ranking has no predictive value, and the report should say so.
4. *The Denmark proxy is uninformative.* Novo's correlation with the Euro Stoxx 50 in DKK is 0.17 (beta 0.30). That makes the CAPM-local vote (5.8%) and the DCF WACC (5.0%, upside 111%) too low. The effect on the consensus is small: 7.9% becomes 8.1% without the CAPM-local vote.

**Low**
- Price-index caveat, quantified as the OOS gap of a total-return ETF over the home price index, in USD:

  | ETF vs index | Gap (%/yr) |
  |---|---|
  | EWT vs ^TWII | +1.42 |
  | EWA vs ^AXJO | +3.60 |
  | EWC vs ^GSPTSE | +2.62 |
  | INDA vs ^NSEI | -0.15 |

  Grossing up ^TWII cuts TSMC's local IR from 0.897 to 0.810.
- There is no TW_ or HK_ rate on disk. The flat 1.8% TWD rate is conservative: at 1.0% TSMC's hedge gain is +3.6%. The analyst noted that HKD uses US_3M.
- For AIA and Bajaj, the DCF is correctly withheld. That leaves 3 votes, 2 of them CAPM, so AIA's consensus is its CAPM-local vote (9.2%).
- G-K uses the analyst's +1y growth for 5 years, which pushes TSMC to the 10% real cap (G-K 14.9%). This is library behaviour, and the median damps it.

**Verified correct**
- FX: all 7 currencies are USD per unit, and the conversion multiplies. ADR level parity confirms both: TSM 1.05 to 1.14, NVO 1.00, TCEHY 1.00, AAGIY 1.01.
- TSMC vs the TSM ADR: OOS correlation 0.933, CAGR gap -0.93%/yr. The ADR premium widening from 1.044 to 1.110 explains 0.70%/yr of that.
- 2330.TW's adjusted close includes dividends. On 37 ex-dates, the ex-date ratio averages +0.44; about -0.6 would be expected if the close were unadjusted.
- The decomposition identity holds to 2e-16.
- Drawdowns: Novo 2024-06 to 2026-03 (-74%), CSU 2025-06 to 2026-03 (-52%).
- Control table: Spearman 0.008; Baidu last; Petrobras 30th to 4th; ASML 0.84 (t 2.84); Keyence 22nd.
- The best non-shortlisted names include PETR4 in 2nd place; Titan is 6th.
- No post-hoc substitution: the deep-research set equals the in-sample top 8.
- Memo "explain" sentences match the JSON word for word.

## Memo wording
- TSMC: "largely survives the multiple-testing haircut" should become "passes Bonferroni (t 3.35 > 2.95); DSR 0.78".
- SK Hynix: "highest in-sample fundamental score" should become "highest score on FY2025 statements". The memo should add the mid-cycle sensitivity.
- Bajaj: the +2.2% hedge figure needs its 3.42%/yr carry cost and the UIP caveat next to it.
- The geopolitical risk (TSMC), memory-cycle risk (SK Hynix) and rupee risk (Bajaj) are stated as risks, not overclaimed.

## Recommended changes (no pre-registered rule changed)
1. SK Hynix becomes a runner-up or small position, with its look-ahead label and the mid-cycle sensitivity.
2. Phase 4 shows the price-only in-sample rank next to the composite.
3. Hedging is described as a 2018-26 dollar outcome, with the carry cost shown for each currency.
4. The rank test is reported as non-predictive in substance.
5. Novo's CAPM-local vote is dropped or flagged.
6. AIA stays out of the picks (it escapes rule 8.2 by 0.007 of IR). Tencent is dropped under rule 8.2.
