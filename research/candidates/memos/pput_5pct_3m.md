# Protective put, 5% OTM, 3-month, quarterly (`pput_5pct_3m`)

Overlay on SPY (S&P 500 total return, index-level equity sleeve): buy a 3-month 95% S&P 500 put each quarterly expiry (Mar/Jun/Sep/Dec). Assumptions: `research/candidates/assumptions_overlays.py`. Monthly series for Phase 5: `reports/candidates/overlays/pput_5pct_3m_monthly.csv`. Reproduce: `python -m research.candidates.overlays --overlay pput_5pct_3m --write`.

## Result (net of costs)

| Window | Sharpe plain / overlaid | Vol plain / overlaid | Max DD plain / overlaid | Sortino plain / overlaid | Worst month plain / overlaid | Up / down capture |
|---|---|---|---|---|---|---|
| In-sample 2010-17 | 1.14 / 0.43 | 11.9% / 8.9% | -16.2% / -17.4% | 2.02 / 0.66 | -7.9% / -5.6% | 0.56 / 0.92 |
| OOS 2018-26 | 0.75 / 0.69 | 16.2% / 12.0% | -23.9% / -16.6% | 1.18 / 1.13 | -12.5% / -6.8% | 0.64 / 0.55 |
| Full | 0.90 / 0.58 | 14.3% / 10.6% | -23.9% / -17.4% | 1.46 / 0.93 | -12.5% / -6.8% | 0.60 / 0.69 |

Average annual cost: 0.13% of the sleeve (in-sample 0.12%, OOS 0.13%). Verdict, method.md 8.5 standalone: **passes** (OOS Sharpe change -0.07, max drawdown change 7.3% points; the portfolio-level test is Phase 5's).

## Stress windows (method.md s11)

| Window | Return plain / overlaid | Max DD plain / overlaid | DD reduction |
|---|---|---|---|
| gfc_2008 | -50.8% / -28.7% | -48.8% / -26.0% | 22.8% |
| taper_2013 | 3.0% / 0.3% | -3.0% / -3.1% | -0.1% |
| covid_2020 | -19.4% / 6.7% | -12.5% / 0.0% | 12.5% |
| inflation_2022 | -17.7% / -13.6% | -20.2% / -11.5% | 8.7% |
| strong USD months (29) avg | -3.94% / -1.58% | | |

## Model and calibration

Black-Scholes on SPY total-return prices; ^VIX/^VIX3M as implied vol; smile fitted on 2010-2017 only and frozen: ATM level -0.0307, call skew 0.2323, put skew 0.2930 (vol change per unit of ln(K/F)/sqrt(T)).

- vs CBOE PPUT, in_sample: tracking error 3.4%/yr, mean difference -3.01%/yr, R2 total return 0.879, R2 of the overlay component 0.35 (96 months).
- vs CBOE PPUT, out_of_sample: tracking error 4.9%/yr, mean difference 0.31%/yr, R2 total return 0.857, R2 of the overlay component 0.47 (106 months).
- PPUT rolls a 1-month put monthly; the 3-month quarterly overlay is a loose comparison.
- Measured volatility risk premium (VIX minus next-21-day realised): 4.0 pts in-sample, 3.7 pts OOS (Cboe/Bondarenko 1990-2018: about 4.2).
- At exactly 100% hedge ratio: OOS Sharpe 0.77, max DD -17.6%, standalone verdict passes.
- Basis: on a 50% IVW / 50% EFG_EEM_5050 sleeve proxy the OOS Sharpe goes 0.57 -> 0.41, max DD -30.4% -> -27.7%; OOS correlation of EFG_EEM_5050 with SPY 0.83. The overlay is primarily on the US stocks; the hedge is imperfect for the international names.

## Feasibility at $100,000

- One XSP contract ($76,237) is 139% of a $55,000 equity sleeve; zero contracts is 0%. The series is modelled at the 1-contract ratio (column hedge_ratio); overlay_return_h100 is the same overlay at exactly 100%. Holding puts on more than 100% of the sleeve is a small net short bet below the strike.
- Long puts need no margin (premium paid in full).
- Today (2026-10-23): buy put ('pct', 0.95), XSP strike 724.2, model premium $1,345 per contract at 21.0% vol.

## Limits

- No option price history: premiums are modelled; the CBOE index is the only realised reference.
- Run on the S&P 500 at one XSP contract (139% of a $55,000 sleeve), the overlay changed the 2018-2026 Sharpe from 0.75 to 0.69, volatility from 16.2% to 12.0% and the worst drawdown from -24% to -17%, after costs. Option prices are modelled from the VIX with a smile fitted to CBOE's PPUT index on 2010-2017 only; out of sample the like-for-like model tracks that index with an error of 2.3% a year. On the standalone test it passes method.md rule 8.5; the S&P 500 options hedge the international half of the sleeve only loosely (correlation 0.83).
