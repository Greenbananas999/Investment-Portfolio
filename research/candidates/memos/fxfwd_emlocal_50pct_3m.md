# EM local-currency FX hedge, 50%, 3-month forwards (`fxfwd_emlocal_50pct_3m`)

Overlay on EMLC: sell 3-month CIP forwards on 50% of the EMLC currency basket, rolled quarterly. Assumptions: `research/candidates/assumptions_overlays.py`. Monthly series for Phase 5: `reports/candidates/overlays/fxfwd_emlocal_50pct_3m_monthly.csv`. Reproduce: `python -m research.candidates.overlays --overlay fxfwd_emlocal_50pct_3m --write`.

## Result (net of costs)

| Window | Sharpe plain / overlaid | Vol plain / overlaid | Max DD plain / overlaid | Sortino plain / overlaid | Worst month plain / overlaid | Up / down capture |
|---|---|---|---|---|---|---|
| In-sample 2010-17 | 0.14 / 0.12 | 11.6% / 8.0% | -28.8% / -21.5% | 0.19 / 0.16 | -11.0% / -6.7% | 0.66 / 0.66 |
| OOS 2018-26 | -0.10 / -0.22 | 10.6% / 7.3% | -25.5% / -20.7% | -0.13 / -0.29 | -11.8% / -7.4% | 0.64 / 0.65 |
| Full | 0.01 / -0.06 | 11.1% / 7.6% | -31.1% / -23.8% | 0.02 / -0.08 | -11.8% / -7.4% | 0.65 / 0.66 |

Average annual cost: 0.10% of the sleeve (in-sample 0.10%, OOS 0.10%). Verdict, method.md 8.5 standalone: **passes** (OOS Sharpe change -0.13, max drawdown change 4.8% points; the portfolio-level test is Phase 5's).

## Stress windows (method.md s11)

| Window | Return plain / overlaid | Max DD plain / overlaid | DD reduction |
|---|---|---|---|
| gfc_2008 | not covered by the model history | | |
| taper_2013 | -14.2% / -10.9% | -8.6% / -6.6% | 2.0% |
| covid_2020 | -14.4% / -9.4% | -11.8% / -7.4% | 4.3% |
| inflation_2022 | -17.5% / -14.3% | -17.8% / -14.1% | 3.7% |
| strong USD months (23) avg | -4.85% / -2.96% | | |

## Model and calibration

3-month forwards by covered interest parity from OECD 3-month interbank rates against TB3MS; 5 bp per roll; basket weights (GBI-EM, averages where missing): MXN 11%, ZAR 9%, INR 19%, IDR 10%, PLN 9%, HUF 11%, CZK 11%, CLP 9%, COP 11%. BRL (no BR_3M series in yields.csv), THB and MYR (no OECD series) are not hedged.

- Carry given up at this ratio: 2.13%/yr in-sample, 1.37%/yr OOS; roll costs 0.10%/yr.
- EMLC monthly return on the hedged basket's spot return: beta 1.25, R2 0.83 OOS (beta 1.21, R2 0.80 in-sample): the share of EMLC risk this basket can remove.
- EBND cross-check OOS Sharpe -0.14 -> -0.29.

## Feasibility at $100,000

- 3-month deliverable/non-deliverable FX forwards on 9 EM currencies (bank OTC)
- Bank forwards and NDFs need a dealer credit line or ISDA; not normally open to a retail brokerage account (not verified for a specific broker). The exchange route is CME FX futures on MXN, ZAR and BRL only, whose standard sizes (500,000 MXN = about $26,623; 500,000 ZAR = about $30,272; 100,000 BRL = about $18,195 at fx.csv's last rates; sizes from memory, NOT verified this session) exceed a ~$8,750 EMLC position.

## Limits

- CIP forwards from interbank rates are not dealer quotes; NDF currencies (INR, IDR, CLP, COP) can deviate from CIP.
- Selling 50% of EMLC's currency exposure forward each quarter changed its 2018-2026 Sharpe from -0.10 to -0.22 and its worst drawdown from -26% to -21%. The hedge gives up the interest-rate gap between EM and US cash, about 1.4% a year out of sample, which is most of what local-currency bonds pay for their risk. It cannot be bought in a $100,000 brokerage account as modelled (bank forwards on nine currencies), so it is a test of whether the currency risk is worth taking, not a trade.
