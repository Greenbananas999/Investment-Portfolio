# Covered call, at-the-money, 1-month (BXM-style) (`cc_spx_atm_1m`)

Overlay on SPY (S&P 500 total return, index-level equity sleeve): sell a 1-month at-the-money S&P 500 call each monthly expiry. Assumptions: `research/candidates/assumptions_overlays.py`. Monthly series for Phase 5: `reports/candidates/overlays/cc_spx_atm_1m_monthly.csv`. Reproduce: `python -m research.candidates.overlays --overlay cc_spx_atm_1m --write`.

## Result (net of costs)

| Window | Sharpe plain / overlaid | Vol plain / overlaid | Max DD plain / overlaid | Sortino plain / overlaid | Worst month plain / overlaid | Up / down capture |
|---|---|---|---|---|---|---|
| In-sample 2010-17 | 1.14 / 0.66 | 11.9% / 7.3% | -16.2% / -13.4% | 2.02 / 0.97 | -7.9% / -9.6% | 0.32 / 0.28 |
| OOS 2018-26 | 0.75 / 0.31 | 16.2% / 10.5% | -23.9% / -28.5% | 1.18 / 0.37 | -12.5% / -19.9% | 0.38 / 0.38 |
| Full | 0.90 / 0.44 | 14.3% / 9.1% | -23.9% / -28.5% | 1.46 / 0.56 | -12.5% / -19.9% | 0.36 / 0.34 |

Average annual cost: 0.35% of the sleeve (in-sample 0.34%, OOS 0.36%). Verdict, method.md 8.5 standalone: **fails** (OOS Sharpe change -0.44, max drawdown change -4.6% points; the portfolio-level test is Phase 5's).

## Stress windows (method.md s11)

| Window | Return plain / overlaid | Max DD plain / overlaid | DD reduction |
|---|---|---|---|
| gfc_2008 | -50.8% / -20.1% | -48.8% / -25.7% | 23.1% |
| taper_2013 | 3.0% / -4.6% | -3.0% / -2.5% | 0.5% |
| covid_2020 | -19.4% / -24.8% | -12.5% / -19.9% | -7.5% |
| inflation_2022 | -17.7% / -5.5% | -20.2% / -14.6% | 5.6% |
| strong USD months (29) avg | -3.94% / -1.83% | | |

## Model and calibration

Black-Scholes on SPY total-return prices; ^VIX/^VIX3M as implied vol; smile fitted on 2010-2017 only and frozen: ATM level -0.0307, call skew 0.2323, put skew 0.2930 (vol change per unit of ln(K/F)/sqrt(T)).

- vs CBOE BXM, in_sample: tracking error 1.8%/yr, mean difference -0.07%/yr, R2 total return 0.954, R2 of the overlay component 0.92 (96 months).
- vs CBOE BXM, out_of_sample: tracking error 2.4%/yr, mean difference 0.93%/yr, R2 total return 0.952, R2 of the overlay component 0.92 (106 months).
- XYLD cross-check OOS: tracking error 3.5%/yr, mean difference 0.04%/yr (model gross of option costs minus the 0.60% fund fee; XYLD starts 2013-06).
- Measured volatility risk premium (VIX minus next-21-day realised): 4.0 pts in-sample, 3.7 pts OOS (Cboe/Bondarenko 1990-2018: about 4.2).
- At exactly 100% hedge ratio: OOS Sharpe 0.53, max DD -24.2%, standalone verdict fails.
- Basis: on a 50% IVW / 50% EFG_EEM_5050 sleeve proxy the OOS Sharpe goes 0.57 -> 0.04, max DD -30.4% -> -30.8%; OOS correlation of EFG_EEM_5050 with SPY 0.83. The overlay is primarily on the US stocks; the hedge is imperfect for the international names.

## Feasibility at $100,000

- One XSP contract ($76,237) is 139% of a $55,000 equity sleeve; zero contracts is 0%. The series is modelled at the 1-contract ratio (column hedge_ratio); overlay_return_h100 is the same overlay at exactly 100%. Writing calls on 139% of the sleeve leaves part of the call uncovered, which breaks the overlay-only rule; it becomes a covered overlay only once the equity sleeve is at least $76,237.
- The short XSP call is not covered by the sleeve's stocks, so a broker margins it as an uncovered broad-based index call: about $13,008 per contract at today's level (premium + 15% of notional less the OTM amount, minimum premium + 10%; Cboe margin rule recalled, not re-verified). Needs the broker's uncovered-option approval level.
- Today (2026-10-23): sell call ('atm',), XSP strike 762.4, model premium $1,573 per contract at 16.6% vol.

## Limits

- No option price history: premiums are modelled; the CBOE index is the only realised reference.
- Run on the S&P 500 at one XSP contract (139% of a $55,000 sleeve), the overlay changed the 2018-2026 Sharpe from 0.75 to 0.31, volatility from 16.2% to 10.5% and the worst drawdown from -24% to -29%, after costs. Option prices are modelled from the VIX with a smile fitted to CBOE's BXM index on 2010-2017 only; out of sample the like-for-like model tracks that index with an error of 2.4% a year. On the standalone test it fails method.md rule 8.5; the S&P 500 options hedge the international half of the sleeve only loosely (correlation 0.83).
