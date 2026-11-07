# EM local-currency FX hedge, 100%, 3-month forwards (`fxfwd_emlocal_100pct_3m`)

Overlay on EMLC: sell 3-month CIP forwards on 100% of the EMLC currency basket, rolled quarterly. Assumptions: `research/candidates/assumptions_overlays.py`. Monthly series for Phase 5: `reports/candidates/overlays/fxfwd_emlocal_100pct_3m_monthly.csv`. Reproduce: `python -m research.candidates.overlays --overlay fxfwd_emlocal_100pct_3m --write`.

## Result (net of costs)

| Window | Sharpe plain / overlaid | Vol plain / overlaid | Max DD plain / overlaid | Sortino plain / overlaid | Worst month plain / overlaid | Up / down capture |
|---|---|---|---|---|---|---|
| In-sample 2010-17 | 0.14 / 0.07 | 11.6% / 5.6% | -28.8% / -13.8% | 0.19 / 0.10 | -11.0% / -4.4% | 0.32 / 0.32 |
| OOS 2018-26 | -0.10 / -0.47 | 10.6% / 4.9% | -25.5% / -16.1% | -0.13 / -0.59 | -11.8% / -5.0% | 0.29 / 0.30 |
| Full | 0.01 / -0.20 | 11.1% / 5.2% | -31.1% / -17.2% | 0.02 / -0.27 | -11.8% / -5.0% | 0.30 / 0.31 |

Average annual cost: 0.20% of the sleeve (in-sample 0.21%, OOS 0.20%). Verdict, method.md 8.5 standalone: **passes** (OOS Sharpe change -0.37, max drawdown change 9.4% points; the portfolio-level test is Phase 5's).

## Stress windows (method.md s11)

| Window | Return plain / overlaid | Max DD plain / overlaid | DD reduction |
|---|---|---|---|
| gfc_2008 | not covered by the model history | | |
| taper_2013 | -14.2% / -7.5% | -8.6% / -4.6% | 4.0% |
| covid_2020 | -14.4% / -4.4% | -11.8% / -3.2% | 8.5% |
| inflation_2022 | -17.5% / -11.2% | -17.8% / -10.5% | 7.3% |
| strong USD months (23) avg | -4.85% / -1.07% | | |

## Model and calibration

3-month forwards by covered interest parity from OECD 3-month interbank rates against TB3MS; 5 bp per roll; basket weights (GBI-EM, averages where missing): MXN 11%, ZAR 9%, INR 19%, IDR 10%, PLN 9%, HUF 11%, CZK 11%, CLP 9%, COP 11%. BRL (no BR_3M series in yields.csv), THB and MYR (no OECD series) are not hedged.

- Carry given up at this ratio: 4.27%/yr in-sample, 2.73%/yr OOS; roll costs 0.20%/yr.
- EMLC monthly return on the hedged basket's spot return: beta 1.25, R2 0.83 OOS (beta 1.21, R2 0.80 in-sample): the share of EMLC risk this basket can remove.
- EBND cross-check OOS Sharpe -0.14 -> -0.51.

## Feasibility at $100,000

- 3-month deliverable/non-deliverable FX forwards on 9 EM currencies (bank OTC)
- Bank forwards and NDFs need a dealer credit line or ISDA; not normally open to a retail brokerage account (not verified for a specific broker). The exchange route is CME FX futures on MXN, ZAR and BRL only, whose standard sizes (500,000 MXN = about $26,623; 500,000 ZAR = about $30,272; 100,000 BRL = about $18,195 at fx.csv's last rates; sizes from memory, NOT verified this session) exceed a ~$8,750 EMLC position.

## Limits

- CIP forwards from interbank rates are not dealer quotes; NDF currencies (INR, IDR, CLP, COP) can deviate from CIP.
- Selling 100% of EMLC's currency exposure forward each quarter changed its 2018-2026 Sharpe from -0.10 to -0.47 and its worst drawdown from -26% to -16%. The hedge gives up the interest-rate gap between EM and US cash, about 2.7% a year out of sample, which is most of what local-currency bonds pay for their risk. It cannot be bought in a $100,000 brokerage account as modelled (bank forwards on nine currencies), so it is a test of whether the currency risk is worth taking, not a trade.
