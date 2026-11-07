# Covered call, 30-delta, 1-month (BXMD-style) (`cc_spx_30d_1m`)

Overlay on SPY (S&P 500 total return, index-level equity sleeve): sell a 1-month 30-delta S&P 500 call each monthly expiry. Assumptions: `research/candidates/assumptions_overlays.py`. Monthly series for Phase 5: `reports/candidates/overlays/cc_spx_30d_1m_monthly.csv`. Reproduce: `python -m research.candidates.overlays --overlay cc_spx_30d_1m --write`.

## Result (net of costs)

| Window | Sharpe plain / overlaid | Vol plain / overlaid | Max DD plain / overlaid | Sortino plain / overlaid | Worst month plain / overlaid | Up / down capture |
|---|---|---|---|---|---|---|
| In-sample 2010-17 | 1.14 / 1.01 | 11.9% / 9.0% | -16.2% / -13.1% | 2.02 / 1.71 | -7.9% / -8.1% | 0.62 / 0.58 |
| OOS 2018-26 | 0.75 / 0.60 | 16.2% / 12.6% | -23.9% / -23.8% | 1.18 / 0.82 | -12.5% / -16.7% | 0.70 / 0.71 |
| Full | 0.90 / 0.75 | 14.3% / 11.0% | -23.9% / -23.8% | 1.46 / 1.09 | -12.5% / -16.7% | 0.67 / 0.66 |

Average annual cost: 0.17% of the sleeve (in-sample 0.18%, OOS 0.16%). Verdict, method.md 8.5 standalone: **fails** (OOS Sharpe change -0.16, max drawdown change 0.1% points; the portfolio-level test is Phase 5's).

## Stress windows (method.md s11)

| Window | Return plain / overlaid | Max DD plain / overlaid | DD reduction |
|---|---|---|---|
| gfc_2008 | -50.8% / -33.7% | -48.8% / -33.6% | 15.2% |
| taper_2013 | 3.0% / -5.0% | -3.0% / -2.7% | 0.3% |
| covid_2020 | -19.4% / -22.5% | -12.5% / -16.7% | -4.2% |
| inflation_2022 | -17.7% / -13.1% | -20.2% / -19.6% | 0.6% |
| strong USD months (29) avg | -3.94% / -2.88% | | |

## Model and calibration

Black-Scholes on SPY total-return prices; ^VIX/^VIX3M as implied vol; smile fitted on 2010-2017 only and frozen: ATM level -0.0307, call skew 0.2323, put skew 0.2930 (vol change per unit of ln(K/F)/sqrt(T)).

- vs CBOE BXMD, in_sample: tracking error 1.3%/yr, mean difference 0.25%/yr, R2 total return 0.981, R2 of the overlay component 0.91 (96 months).
- vs CBOE BXMD, out_of_sample: tracking error 2.0%/yr, mean difference 0.93%/yr, R2 total return 0.976, R2 of the overlay component 0.87 (106 months).
- Measured volatility risk premium (VIX minus next-21-day realised): 4.0 pts in-sample, 3.7 pts OOS (Cboe/Bondarenko 1990-2018: about 4.2).
- At exactly 100% hedge ratio: OOS Sharpe 0.67, max DD -22.6%, standalone verdict fails.
- Basis: on a 50% IVW / 50% EFG_EEM_5050 sleeve proxy the OOS Sharpe goes 0.57 -> 0.37, max DD -30.4% -> -25.9%; OOS correlation of EFG_EEM_5050 with SPY 0.83. The overlay is primarily on the US stocks; the hedge is imperfect for the international names.

## Feasibility at $100,000

- One XSP contract ($76,237) is 139% of a $55,000 equity sleeve; zero contracts is 0%. The series is modelled at the 1-contract ratio (column hedge_ratio); overlay_return_h100 is the same overlay at exactly 100%. Writing calls on 139% of the sleeve leaves part of the call uncovered, which breaks the overlay-only rule; it becomes a covered overlay only once the equity sleeve is at least $76,237.
- The short XSP call is not covered by the sleeve's stocks, so a broker margins it as an uncovered broad-based index call: about $10,027 per contract at today's level (premium + 15% of notional less the OTM amount, minimum premium + 10%; Cboe margin rule recalled, not re-verified). Needs the broker's uncovered-option approval level.
- Today (2026-10-23): sell call ('delta', 0.3), XSP strike 782.4, model premium $592 per contract at 14.5% vol.

## Limits

- No option price history: premiums are modelled; the CBOE index is the only realised reference.
- Run on the S&P 500 at one XSP contract (139% of a $55,000 sleeve), the overlay changed the 2018-2026 Sharpe from 0.75 to 0.60, volatility from 16.2% to 12.6% and the worst drawdown from -24% to -24%, after costs. Option prices are modelled from the VIX with a smile fitted to CBOE's BXMD index on 2010-2017 only; out of sample the like-for-like model tracks that index with an error of 2.0% a year. On the standalone test it fails method.md rule 8.5; the S&P 500 options hedge the international half of the sleeve only loosely (correlation 0.83).
