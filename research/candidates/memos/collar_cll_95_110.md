# Collar 95/110 (CBOE CLL definition) (`collar_cll_95_110`)

Overlay on SPY (S&P 500 total return, index-level equity sleeve): buy a 3-month 95% put quarterly and sell a 1-month 110% call monthly. Assumptions: `research/candidates/assumptions_overlays.py`. Monthly series for Phase 5: `reports/candidates/overlays/collar_cll_95_110_monthly.csv`. Reproduce: `python -m research.candidates.overlays --overlay collar_cll_95_110 --write`.

## Result (net of costs)

| Window | Sharpe plain / overlaid | Vol plain / overlaid | Max DD plain / overlaid | Sortino plain / overlaid | Worst month plain / overlaid | Up / down capture |
|---|---|---|---|---|---|---|
| In-sample 2010-17 | 1.14 / 0.46 | 11.9% / 8.5% | -16.2% / -15.7% | 2.02 / 0.70 | -7.9% / -6.2% | 0.54 / 0.88 |
| OOS 2018-26 | 0.75 / 0.51 | 16.2% / 10.9% | -23.9% / -15.6% | 1.18 / 0.79 | -12.5% / -6.5% | 0.55 / 0.55 |
| Full | 0.90 / 0.49 | 14.3% / 9.9% | -23.9% / -15.7% | 1.46 / 0.75 | -12.5% / -6.5% | 0.55 / 0.67 |

Average annual cost: 0.18% of the sleeve (in-sample 0.19%, OOS 0.17%). Verdict, method.md 8.5 standalone: **passes** (OOS Sharpe change -0.24, max drawdown change 8.3% points; the portfolio-level test is Phase 5's).

## Stress windows (method.md s11)

| Window | Return plain / overlaid | Max DD plain / overlaid | DD reduction |
|---|---|---|---|
| gfc_2008 | -50.8% / -18.4% | -48.8% / -20.1% | 28.7% |
| taper_2013 | 3.0% / 0.3% | -3.0% / -3.0% | -0.0% |
| covid_2020 | -19.4% / 1.3% | -12.5% / 0.0% | 12.5% |
| inflation_2022 | -17.7% / -12.7% | -20.2% / -11.2% | 9.1% |
| strong USD months (29) avg | -3.94% / -1.38% | | |

## Model and calibration

Black-Scholes on SPY total-return prices; ^VIX/^VIX3M as implied vol; smile fitted on 2010-2017 only and frozen: ATM level -0.0307, call skew 0.2323, put skew 0.2930 (vol change per unit of ln(K/F)/sqrt(T)).

- vs CBOE CLL, in_sample: tracking error 1.4%/yr, mean difference 0.48%/yr, R2 total return 0.978, R2 of the overlay component 0.90 (96 months).
- vs CBOE CLL, out_of_sample: tracking error 2.6%/yr, mean difference -0.93%/yr, R2 total return 0.953, R2 of the overlay component 0.91 (106 months).
- Measured volatility risk premium (VIX minus next-21-day realised): 4.0 pts in-sample, 3.7 pts OOS (Cboe/Bondarenko 1990-2018: about 4.2).
- At exactly 100% hedge ratio: OOS Sharpe 0.67, max DD -16.9%, standalone verdict passes.
- Basis: on a 50% IVW / 50% EFG_EEM_5050 sleeve proxy the OOS Sharpe goes 0.57 -> 0.23, max DD -30.4% -> -27.0%; OOS correlation of EFG_EEM_5050 with SPY 0.83. The overlay is primarily on the US stocks; the hedge is imperfect for the international names.

## Feasibility at $100,000

- One XSP contract ($76,237) is 139% of a $55,000 equity sleeve; zero contracts is 0%. The series is modelled at the 1-contract ratio (column hedge_ratio); overlay_return_h100 is the same overlay at exactly 100%. Writing calls on 139% of the sleeve leaves part of the call uncovered, which breaks the overlay-only rule; it becomes a covered overlay only once the equity sleeve is at least $76,237.
- The short XSP call is not covered by the sleeve's stocks, so a broker margins it as an uncovered broad-based index call: about $7,624 per contract at today's level (premium + 15% of notional less the OTM amount, minimum premium + 10%; Cboe margin rule recalled, not re-verified). Needs the broker's uncovered-option approval level.
- Today (2026-10-23): buy put ('pct', 0.95), XSP strike 724.2, model premium $1,345 per contract at 21.0% vol.
- Today (2026-10-23): sell call ('pct', 1.1), XSP strike 838.6, model premium $0 per contract at 8.9% vol.

## Limits

- No option price history: premiums are modelled; the CBOE index is the only realised reference.
- Run on the S&P 500 at one XSP contract (139% of a $55,000 sleeve), the overlay changed the 2018-2026 Sharpe from 0.75 to 0.51, volatility from 16.2% to 10.9% and the worst drawdown from -24% to -16%, after costs. Option prices are modelled from the VIX with a smile fitted to CBOE's CLL index on 2010-2017 only; out of sample the like-for-like model tracks that index with an error of 2.6% a year. On the standalone test it passes method.md rule 8.5; the S&P 500 options hedge the international half of the sleeve only loosely (correlation 0.83).
