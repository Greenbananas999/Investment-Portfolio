# Derivative overlays: summary

Written by `python -m research.candidates.overlays --all --write`. All numbers net of method.md s10 costs; OOS = 2018-01 to 2026-10; option overlays at one XSP contract on a $55,000 equity sleeve (hedge ratio 1.39), FX overlays at the stated ratio on EMLC.

| Overlay | OOS Sharpe plain -> overlaid | OOS vol | OOS max DD | Annual cost | Fit vs CBOE: IS R2 (overlay part) / OOS TE | Passes 8.5 standalone |
|---|---|---|---|---|---|---|
| cc_spx_30d_1m | 0.75 -> 0.60 | 16.2% -> 12.6% | -23.9% -> -23.8% | 0.17% | 0.91 / 2.0% (BXMD) | no |
| cc_spx_atm_1m | 0.75 -> 0.31 | 16.2% -> 10.5% | -23.9% -> -28.5% | 0.35% | 0.92 / 2.4% (BXM) | no |
| pput_5pct_3m | 0.75 -> 0.69 | 16.2% -> 12.0% | -23.9% -> -16.6% | 0.13% | 0.77 / 2.3% (PPUT 1m model) | yes |
| collar_cll_95_110 | 0.75 -> 0.51 | 16.2% -> 10.9% | -23.9% -> -15.6% | 0.18% | 0.90 / 2.6% (CLL) | yes |
| fxfwd_emlocal_50pct_3m | -0.10 -> -0.22 | 10.6% -> 7.3% | -25.5% -> -20.7% | 0.10% | no fitted parameter | yes |
| fxfwd_emlocal_100pct_3m | -0.10 -> -0.47 | 10.6% -> 4.9% | -25.5% -> -16.1% | 0.20% | no fitted parameter | yes |

Calibrated smile (2010-2017, frozen): ATM level -0.0307, call skew 0.2323, put skew 0.2930. Fit by index (gross, 100%):

- BXM: in-sample TE 1.8%, R2 overlay part 0.92; OOS TE 2.4%, R2 overlay part 0.92, mean gap 0.93%/yr.
- BXMD: in-sample TE 1.3%, R2 overlay part 0.91; OOS TE 2.0%, R2 overlay part 0.87, mean gap 0.93%/yr.
- PPUT: in-sample TE 2.1%, R2 overlay part 0.77; OOS TE 2.3%, R2 overlay part 0.88, mean gap 0.03%/yr.

Volatility risk premium (VIX minus next-21-day realised SPY vol): 4.0 pts 2010-2017, 3.7 pts 2018-2026 (chart `reports/candidates/charts/overlays_vrp.png`).
Basis: OOS correlation of EFG_EEM_5050 with SPY 0.83; of the 50/50 sleeve proxy 0.95.

## Honest limits

- No option price history exists in the data; every premium is Black-Scholes on the VIX with a fitted smile. The CBOE indices are the only realised reference, and they are SPX index strategies, not this sleeve.
- PPUT before its 2015 launch (and CLL before 2008) are Cboe back-calculations, not live records; the calibration window 2010-2017 for PPUT is therefore partly back-filled.
- Feasibility: one XSP contract is about $76,237, i.e. 139% of the equity sleeve; whole contracts give 0% or ~139%, nothing in between. Short calls on 139% are partly uncovered and break the overlay-only rule until the sleeve reaches the contract notional. XSP liquidity (spreads wider than the assumed 1% of premium half-spread on far strikes) was not checked.
- Basis risk: S&P 500 options on a sleeve that is about half non-US hedge the international names imperfectly; the sleeve-proxy rows in each JSON quantify it.
- The FX hedge removes carry as well as risk: it gives up the EM-minus-US rate gap every quarter. BRL, THB and MYR are unhedged for lack of a rate series; CIP from interbank rates ignores NDF basis; today's country weights are applied to history (look-ahead flag). It is not implementable in a retail account.
- European exercise, continuous strikes, settlement at the close rather than the opening quotation.
