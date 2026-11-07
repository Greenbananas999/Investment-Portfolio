# EM bond funds: adversarial review (opus, 2026-11-07)

Check script: `python -m research.reviews.em_bonds_check` (add `--json path` to save the numbers). It uses independent code (its own month-end returns, Sharpe/IR/drawdown/DSR, unit-holding GUIDE_BENCH, currency split, CIP hedge and country pricer). It imports the analyst's module only to test its fee and Monte Carlo behaviour.

**Reproduced:** yes. `python -m research.candidates.em_bonds --all --write` regenerates every JSON, memo and control file byte-identical. OOS Sharpe, IR, maxDD and DSR match to 4 decimals for all 8 funds and both benchmarks, and the stress windows match exactly.

## Verdicts

| Fund | Verdict | Decisive evidence |
|---|---|---|
| EMB | pass | A benchmark fund, so there is no edge to test. It would fail 8.2 if GUIDE_BENCH were its type benchmark (Sharpe 0.02 < 0.34, IR -0.76), but method s9 makes EMB itself the type benchmark, so it is not dropped. |
| PCY | fail | Drop confirmed. Six survivors remain (EMB, HYEM, CEMB, TGEIX, PYEMX, EMLC), so the runner-up exception (fewer than 5 survivors) does not apply. |
| HYEM | downgrade | The numbers reproduce. Its rank 1 rests on a Sharpe gap that is not statistically meaningful; do not present it as the clear leader. |
| CEMB | pass | Fee-corrected forward estimate 5.93%. |
| EMLC | downgrade | The analyst already keeps it only as an overlay vehicle and benchmark. State plainly that it fails 8.2 against EMB and is not a pick. |
| EBND | fail | Drop confirmed. The fee double count understates its forward estimate by 0.30pt (SEC yield); with that fixed, EBND (4.65%) is slightly above EMLC (4.63%). |
| TGEIX | downgrade | Survives 8.2. Two memo statements are wrong, and the evidence for selecting it is weaker than stated. |
| PYEMX | pass | The explain text prints the range as '-0% to 13%' (p5 is -0.5%); fix the formatting. |

## Claims by fund

### EMB (pass)

- **pass**: OOS Sharpe 0.02, maxDD -26.7%, DSR 0.03. own month-end returns: Sharpe 0.0188, maxDD -0.2674, DSR 0.0329 (em_bonds_check section 1)
- **pass**: IR vs GUIDE_BENCH -0.76 (t -2.3). -0.7622, t -2.27; my unit-holding quarterly rebuild matches the analyst's guide_bench to 4e-16; monthly rebalancing gives -0.760, so the frequency is immaterial
- **weak evidence**: 'EM bonds as a whole lagged the 55/35/10'. true as arithmetic, but GUIDE_BENCH is 55% equities (OOS Sharpe 0.34); the IR of a bond fund against it measures the asset mix, not the fund
- **pass with correction**: forward 5.9%, second highest. second highest as published; the fee double count understates it by 0.39pt (fee-corrected 6.30%), still second

### PCY (fail)

- **pass**: fails method.md 8.2. OOS Sharpe -0.0120 < EMB 0.0188 and IR vs EMB -0.0947 (t -0.28)
- **pass**: worst OOS drawdown of the eight (-36%). -0.3571
- **unverified**: duration 7.5y. judgement (assumptions_em_bonds.py line 44); +/-1y changes the halfway scenario by only +/-0.07pt

### HYEM (downgrade)

- **pass**: best OOS Sharpe of the eight, 0.13. 0.1332 vs PYEMX 0.0983; in the 20-fund control group EEIIX 0.192, PEBIX 0.138 and EMHY 0.134 are higher
- **pass**: OOS IR vs EMB 0.22, t 0.7. 0.2242, t 0.67
- **pass**: IR positive in 80% of OOS rolling windows. 0.80 of the 106 windows ending 2018 or later; 0.93 of the 71 windows that are fully out of sample. The windows overlap: only about 3 independent 36-month blocks
- **pass**: DSR 0.07. 0.0708
- **weak evidence**: rank 1 of 8. the Sharpe gap to PYEMX is 0.035, with DSR 0.07 vs 0.06 and t(IR) < 1 for both; PYEMX has the higher IR (0.29). The fee-corrected forward estimate, 5.48%, is the lowest of the hard-currency funds (PYEMX 6.79%)
- **pass (arithmetic) / weak evidence (inputs)**: credit loss 1.9%/yr. 0.0191 by hand; the rating mix is judgement, the default table comes from a secondary site (fatfire.com) and the recovery rate from a forum repost
- **weak evidence**: forward yield. 7.08% is a yfinance trailing yield, not a YTM; the 4.6y duration is borrowed from EMHY

### CEMB (pass)

- **pass**: only fund within the -25% drawdown budget (-20.3%). -0.2026; next best EMLC -0.2551. The -25% budget is a portfolio rule (method s1), not a fund rule, so the wording overclaims
- **pass**: narrowest forward range 0.7% to 10.1%. width 9.4pt vs 11.5pt or more for the others
- **pass**: OOS IR vs EMB 0.09. 0.0907, t 0.27
- **unverified**: rating mix. judgement, not retrieved

### EMLC (downgrade)

- **pass**: OOS local +3.3%, FX -2.3%, USD +0.9%. recomputed 0.0326 / -0.0230 / 0.0089; the identity (1+l)(1+f)=1+usd holds to 2e-16
- **pass**: CIP hedge cost 2.8%, hedged 0.4%. 0.0283 / 0.0037; the sign is correct (US 4%, local 10% gives about -5.9%/yr). With BRL (left out) proxied by Mexico's 3m rate: cost 3.09%, hedged 0.11%, so leaving BRL out understates the cost by about 0.26pt
- **weak evidence**: 'hedged was no better'. depends on the basket: the analyst's own GBI-EM sensitivity gives hedged 2.24% > unhedged 0.89%. That version strips the TRY/BRL/MYR/THB FX moves without charging their hedge cost; with TRY proxied by Turkish CPI and BRL by MX, the GBI-EM hedged return is 0.02%. Report the result as basket-dependent
- **weak evidence**: FX explains 73% of USD variance. cov(fx,usd)/var(usd) = 0.725 confirmed (a valid Euler/beta share), but var(fx)/var(usd) = 0.64, R2 = 0.82, and the GBI-EM basket gives 0.52
- **pass**: ID 3m end and BRL exclusion handled as stated. IDR is hedged for 3 months of 2026 (the Dec value is used with the normal 1-month lag, then forward-filled 2 months); BRL is never hedged
- **fail**: method 8.2. EMLC passes only against itself. Against EMB (the sleeve benchmark, method s9): Sharpe -0.102 < 0.019 and IR -0.208; against its own headline benchmark GUIDE_BENCH: IR -0.83

### EBND (fail)

- **pass**: fails 8.2: Sharpe -0.14 < EMLC -0.10, IR vs EMLC -0.12. -0.1424 < -0.1017, IR -0.1225; it also fails against EMB (IR -0.292)
- **weak evidence**: memo currency numbers (local 3.0%, FX -2.3%, hedge 2.8%). the FX and hedge legs use the same equal-weight basket as EMLC's, not EBND's own currencies; the explain text reads as fund-specific

### TGEIX (downgrade)

- **pass**: Phase 2 IR 0.81 was measured against EMLC by mistake; vs EMB it is 0.27. 0.805 vs EMLC, 0.274 vs EMB. Cause: research/screen/prices.py:192-195 (is_local_currency_bond matches 'local' in the notes). PEBIX had the same error (0.603 vs EMLC, -0.031 vs EMB), which the analyst did not mention
- **fail**: shortlist reason 'best in-sample IR of the active funds'. against EMB it trails GSDIX (0.55) and FNMIX (0.35). The corrected composite rank moves 7 -> 8, still inside the top 8 by composite, so the shortlist place survives but the stated reason does not
- **fail**: second-worst Covid fall (-20%). TGEIX's -20.4% is the WORST of the eight (PCY -19.1%)
- **pass**: OOS IR vs EMB 0.17 (t 0.5). 0.1696, t 0.50
- **pass with correction**: forward 5.2%. the fee double count is largest here (0.85pt): fee-corrected 6.01%, moving its forward rank from 5 to 3; the yield is a trailing distribution yield, not a YTM

### PYEMX (pass)

- **pass**: highest OOS IR vs EMB 0.29 (t 0.9). 0.2938, t 0.87
- **pass**: IR positive in 85% of OOS windows. 0.85; 0.89 of the fully-OOS windows
- **pass / weak evidence**: highest forward estimate 6.1%. 6.06% reproduced, 6.79% fee-corrected; it rests on a 7.03% yfinance trailing distribution yield (not a YTM), an assumed rating mix and a borrowed 6.4y duration

## Methodology findings

- **high**: The fee double count biases the forward component (15 rubric points) against the active funds. em_bonds.py:388 computes net = gross - er - loss although SEC and trailing yields are already net of fees. Understatement = expense ratio: TGEIX 0.85, PYEMX 0.73, PCY 0.50, CEMB 0.50, HYEM 0.40, EMB 0.39, EBND 0.30, EMLC 0 (its yield to worst is gross). Forward rank changes: TGEIX 5->3, EBND above EMLC. The analyst flags the problem but does not correct it. It is partly offset by +0.17-0.23pt from monthly compounding of the yield in research.bonds.total_returns (unchanged-yield gross return minus quoted yield).
- **high**: The Mexico row of the country table is wrong: MX_10Y has 63 missing months, and country_returns (em_bonds.py:443) drops them, so each gap is treated as one month and its FX move is lost. MX USD CAGR since 2010: 7.18% as built vs 4.59% with gaps interpolated; OOS 12.58% vs 7.61%. The table shows MXN at +0.5%/yr, while MXN actually fell 2.1%/yr. The EMLC cross-check basket is barely affected (3.35% vs 3.37%).
- **medium**: The Monte Carlo is not an independent second method. the median minus the yield estimate lies between -0.19 and +0.44pt for all eight funds (montecarlo._scale_to targets the yield estimate), so the 'consensus of at least two methods' (method s7) is in practice one method. The analyst says so; the rubric should say it too.
- **medium**: The control rank test uses a composite that is half 2026 data and contains two mis-benchmarked IRs. em_bond_scored.csv ytm equals the 2026-11 em_bond_inputs.csv ytm for every fund. Spearman vs OOS Sharpe: 0.203 (p 0.42) as published; 0.172 (p 0.49) with corrected IRs; 0.162 (p 0.52) on returns only. Composite vs OOS IR: -0.04 published, -0.08 corrected. By method s7 the in-sample ranking therefore has no predictive value for IR, yet the verdicts lean on OOS IR.
- **medium**: The rankings among the eight are not statistically separable. every |t(IR vs type benchmark)| is below 0.9, except EMB and EMLC against GUIDE_BENCH; DSR at most 0.071. Three non-shortlisted control funds beat every pick on OOS Sharpe (EEIIX 0.19, PEBIX 0.14, EMHY 0.134).
- **low**: The currency decomposition and the hedge result depend on an assumed basket. equal weight vs GBI-EM: FX -2.3% vs -3.4%, FX share 0.73 vs 0.52, hedged 0.4% vs 2.2% (the latter biased upward by unhedged TRY/BRL).
- **low**: Survivorship: the long list holds only funds alive in 2026 (404 tickers dropped, em_bonds_notes.md step 1); there is no dead-fund group for bonds. cannot be quantified from repo data
- **low**: The credit-loss inputs are weakly sourced. the default table comes from fatfire.com (secondary) and the sovereign recovery rate from a forum repost (assumptions_em_bonds.py lines 61-77); the arithmetic reproduces (HYEM 1.91%)

## Checklist

1. Reproduce: pass (byte-identical; the independent recompute matches).
2. Benchmarks: pass. Hard-currency funds are measured against EMB and local funds against EMLC; GUIDE_BENCH is rebalanced quarterly (monthly rebalancing gives -0.760 vs -0.762).
3. Currency: the identity, the CIP formula and sign, and the ID and BRL handling all pass. The 73% FX share and 'hedged no better' are weak evidence because they depend on the basket.
4. Expected returns: fee double count confirmed and quantified; Monte Carlo anchored to the yield estimate; duration immaterial (+/-0.07pt per year of duration); PPP/UIP implemented as the mean of the two, per method s5; inputs weakly sourced.
5. Country table: CO 6.96%, ZA 5.73% and MX 5.44% reproduced. BR_10Y is unchanged in 80% of months and moved through six step levels (5.0-7.5%) in 2010-17, so it is a policy rate and the exclusion is confirmed. The pricer equals research.bonds.total_returns and yields are converted to decimals. Found the MX gap bug.
6. Look-ahead and survivorship: half of the in-sample composite is built on 2026 fundamentals, but the conclusion is unchanged (rho stays above 0); current facts are labelled; the long list holds survivors only.
7. Multiple testing: DSR at most 0.071, and every |t(IR)| is below 0.9 for the candidates, so the ranking is overclaimed.
8. Drop rule: PCY and EBND fail as stated; EMLC also fails against EMB (and GUIDE_BENCH); no other fund fails.
9. Memos: the TGEIX Covid statement is wrong; CEMB's 'security budget' is a portfolio rule; EBND's currency numbers are a proxy; the explain text omits that fees are subtracted twice; PYEMX's range shows '-0%'.

## Recommended changes

- Remove the double expense-ratio subtraction for SEC and trailing yields (keep it for EMLC's gross yield to worst), or apply the method's formula only to gross YTMs; then rerun the forward block and the rubric
- Reindex country yields to a full monthly calendar (or skip the return across a gap) in country_returns, and regenerate the MX row
- Fix the TGEIX memo: its Covid fall was the worst of the eight, not the second worst; replace 'best in-sample IR of the active funds' with the corrected 0.27; mention that PEBIX had the same mis-benchmark
- Change research/screen is_local_currency_bond to use the category only (a job for the owner of research/screen), then rebuild em_bond_insample_table.csv; the shortlist is unchanged (TGEIX 7->8)
- State in the EMLC verdict that it fails 8.2 against EMB and that the hedged-vs-unhedged conclusion depends on the basket
- Present HYEM, PYEMX, CEMB and TGEIX as statistically tied on OOS evidence; do not call HYEM a clear rank 1
- Report the control Spearman both with and without the 2026-based fundamental score
- Label EBND's currency numbers as the EMLC proxy basket, not EBND's own currencies
