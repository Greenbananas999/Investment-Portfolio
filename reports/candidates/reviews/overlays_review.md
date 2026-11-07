# Adversarial review: derivative overlays (reviewer: opus, 2026-11-07)

Check script: `python -m research.reviews.overlays_check` (about 2 minutes; `--quick` skips the
calibration re-fit and the in-memory rerun; `--json PATH` dumps every number).
Machine-readable verdicts: `reports/candidates/reviews/overlays_review.json`.

## Verdicts

| Overlay | Analyst | Review | Decisive evidence |
|---|---|---|---|
| cc_spx_30d_1m | fails 8.5 | **fail** | It cannot be held compliantly: 1 XSP = 139% of the sleeve, and 0 contracts is the only covered size. "Fails 8.5" is weak: the real BXMD index passes the drawdown clause (+2.35 pts OOS), while the model shows +1.35 pts at 100% |
| cc_spx_atm_1m | fails | **fail** | Fails on the model at both ratios and on the real BXM index (+1.70 pts, Sharpe 0.46 vs 0.75) |
| pput_5pct_3m | passes (DD) | **downgrade** | The standalone result reproduces: 100% Sharpe 0.768 (+0.017), DD -17.6% (+6.35 pts). But on an indicative portfolio (GUIDE_BENCH) it fails both clauses: Sharpe 0.342 to 0.264, DD -25.6% to -25.6% |
| collar_cll_95_110 | passes (DD) | **fail** | The short call is uncovered at 1 contract, and 100% is not a whole contract. The portfolio proxy fails at both ratios (Sharpe 0.342 to 0.172, DD +0.27 pts) |
| fxfwd_emlocal_50pct_3m | passes (DD) | **downgrade** | Reproduces (DD +4.80 pts). It cannot be traded at retail, the basket weights have look-ahead, and the portfolio-level gain is noise (Sharpe +0.003) |
| fxfwd_emlocal_100pct_3m | passes (DD) | **downgrade** | Same as the 50% hedge: DD +9.44 pts, carry given up 2.7%/yr, portfolio Sharpe +0.006 |

## What reproduces (pass)

- **Rerun.** `python -m research.candidates.overlays --all --write` rewrote the 6 JSONs, 6 CSVs and
  7 memos byte-identical (cmp against a snapshot taken before the run).
- **CSV vs JSON.** OOS Sharpe, vol and max DD recomputed from the CSVs, with BIL taken from raw
  `prices.csv`, match the JSON to 1e-7. Every number in the brief reproduces:
  - cc30: 0.751 to 0.596, vol 16.2% to 12.6%, DD -23.9% to -23.8%
  - ccATM: Sharpe 0.308, DD -28.5%
  - pput: 0.685, DD -16.6%; at 100%, 0.768 and -17.6%
  - collar: 0.514, DD -15.6%
  - FX 50%: -0.096 to -0.224, vol 7.3%, DD -20.7%
  - FX 100%: -0.469, vol 4.9%, DD -16.1%
- **Independent engine.** I wrote my own third-Friday calendar, smile, brentq delta strike, BS
  pricer, roll loop and costs. It matches the published net series to 5e-9 for cc30, ccATM and
  the collar, and to 6e-5 a month for pput. My own FX hedge loop matches both FX CSVs to 5e-9.
- **Black-Scholes.** S=K=100, r=0, sigma=0.2, T=1/12 gives call = put = 2.302974, equal to the
  textbook value S(2N(sigma sqrt(T)/2) - 1). The put-call parity error and the gap to an
  independent BS are both at most 4.6e-13. Sign conventions are right: the short call credits
  premium and the long put debits it (`cash -= leg.sign * q * prem`, overlays.py line 248).
  Dividends enter through the SPY adjusted close with q = 0.
- **No look-ahead in the option engine.** Multiplying VIX/VIX3M by 2.5 and SPY by 0.6 after
  2020-02-14 changed no month up to 2020-01 (difference 0.0).
- **Calibration.** Distorting all VIX, SPY and CBOE data after 2017 and re-fitting gave identical
  parameters: ATM level -0.03067, call skew 0.23227, put skew 0.29299. The cut-off is in
  `calibrate()`, line 297. The collar is a true hold-out: CLL is never fitted.
- **Tracking.** Fit statistics against the CBOE indices are in this table:

  | Model vs index | In-sample R2 (overlay part) | OOS TE | OOS R2 |
  |---|---|---|---|
  | BXMD | 0.907 | 2.02% | 0.865 |
  | BXM | 0.924 | 2.40% | 0.921 |
  | PPUT (1-month model) | 0.767 | 2.32% | 0.884 |
  | CLL (hold-out) | 0.897 | 2.63% | 0.911 |

- **VRP.** 4.03 points in-sample and 3.71 OOS (VIX minus the next 21 days' realised vol).
  The trailing-window version gives 3.97 and 3.77.
- **Costs.** The code charges 1% of premium plus $0.65 x contracts on each opening trade, and
  5 bp per quarterly FX roll. Annual costs: cc30 0.17%, pput 0.13%, FX 0.10% and 0.20%.
- **Sizing.** ^GSPC was 7623.68 on 2026-10-23, so one XSP contract is $76,237, or 1.386 of a
  $55k sleeve. A SPY option lot is $75,997.
- **FX forwards.**
  - The CIP forward by hand equals the code's: MXN 2019-03 F/S 0.985593, PLN 2023-06 0.995906.
  - The hedge sign is right: corr(overlay, basket) is -0.998. In 2020-11 the basket rose 4.6%
    and the hedge lost 4.8%.
  - Carry given up at 100%: 4.21% in-sample and 2.72% OOS on my calculation, against 4.27% and
    2.73% in the JSON.
  - EMLC's beta to the hedged basket is 1.249 with R2 0.827. The EFG_EEM_5050 correlation with
    SPY is 0.825.

## Methodology findings

**High**

1. **Rule 8.5 is a portfolio rule. Every verdict is standalone on SPY, and the verdicts flip at
   portfolio level.** The analyst says the portfolio test is Phase 5's, but the explain
   sentences say "passes method.md rule 8.5". My indicative test uses GUIDE_BENCH (55% ACWX,
   35% EMB, 10% GLD), adds 0.55 x the overlay P&L, and runs over the OOS months to 2026-10.

   | Overlay | at 100% | at 1 contract |
   |---|---|---|
   | pput | fail (Sharpe 0.342 to 0.264, DD +0.02 pts) | fail |
   | collar | fail | fail |
   | ccATM | **pass** on DD (+3.6 pts) | fail |
   | cc30 | fail (+1.66 pts) | **pass** on DD (+2.3 pts) |
   | FX 50% / 100% | pass on Sharpe (+0.003 / +0.006) | (same series) |

   Why the put fails: the portfolio's drawdown runs from 2021-05/08 to 2022-09/10 and is driven
   by EM bonds and ACWX. Over that stretch the put lost 6.3% in 2021-06 to 12 and 4.5% in
   2022-10, against a gain of 6.7% in 2022-01 to 09.
2. **Compliance.** Short XSP calls on 139% of the sleeve are 39% uncovered, and a broker margins
   XSP calls as uncovered even at 100%. For the covered calls and the collar, the only
   compliant size at $100k is zero contracts. The analyst disclosed this, but the headline
   numbers are still the non-compliant 139% series.

**Medium**

3. **The covered-call "fail" depends on the model.** On the real BXMD index the drawdown clause
   passes (+2.35 pts). The model's +0.93%/yr OOS return gap over BXM and BXMD is unexplained:
   - It is not costs (the comparison is gross) and not XSP vs SPX (the SPY fee runs the other way).
   - It comes mostly from 2021 (+4.8%) and 2022 (+3.3%) for BXMD.
   - In-sample years swing as much (2010 +4.3%, 2013 -2.9%), so t is about 1.4.

   The gap flatters returns but not drawdown: the model's DD is -22.5% gross against the
   index's -21.6%.
4. **The quarterly 3-month put has no direct fit.** The "2.3% a year" in pput's explain
   sentence is the 1-month model's figure. The overlay itself is at 4.94% TE and R2 0.47
   against PPUT. Only the CLL hold-out checks the 3-month put pricing.
5. **The FX basket has more look-ahead than the analyst discloses.**
   - INR is 19.2% of the hedge from 2011-11, but it joined the GBI-EM only in 2024 (from
     memory, not verified).
   - CNY is left out without being listed in `FX_EXCLUDED`. It has a 14.93% weight in
     `em_bonds_countries.csv`, and CN_3M runs to 2026-09.
   - TRY is left out because TR_3M ends in 2008. That is justified, but the code and memos do
     not say so.

**Low**

6. The FX engine uses the month-t OECD average at month-t end (lines 378-385), while the option
   engine uses the previous month's rate.
7. The 110% call is priced at about $0 (8.9% vol), so its modelled cost is about $0, below
   half an XSP tick.
8. October 2026 is a partial month, ending 2026-10-23. The constant 1.386 ratio is applied
   back to 2010, when one XSP was $10,739.
9. The VRP uses forward realised vol. That is the correct ex-post definition, used only as a
   diagnostic.

## Rule 8.5 by series

- **1-contract series:** pput, collar, FX 50% and FX 100% pass; cc30 and ccATM fail.
- **Exact 100% series:**
  - pput passes both clauses.
  - The collar and the FX hedges pass on drawdown.
  - cc30 fails (+1.35 pts) and ccATM fails.

## Phase 5 guidance

- **Series to use:** `overlay_return_h100`, net of costs, as P&L per $1 of equity sleeve.
- **What to add it to:** the actual equity-sleeve return, not SPY, scaled by
  h_t = contracts x XSP notional / sleeve value at each roll. Linear scaling misses the 139%
  series by at most 0.27%/yr (collar) and 0.15%/yr (put).
- **Test:** rule 8.5 at portfolio level, for three cases: h = 0, h = 1, and the
  1-contract h (about 1.17 to 1.69, depending on the equity weight).
- **Excluded:** covered calls and the collar, because zero contracts is the only compliant
  size. Also the FX hedges as positions, because they cannot be traded at retail; use them only
  to size unhedged EMLC.
- **Expectation for the put:** on the GUIDE_BENCH proxy it does not cut the drawdown and lowers
  Sharpe, so expect it to fail at portfolio level.
