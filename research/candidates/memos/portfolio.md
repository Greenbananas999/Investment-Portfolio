# Phase 5 memo: the portfolio as a whole

Written 2026-11-07. Every number comes from `reports/final/portfolio.json`,
reproduced by `python -m portfolio.build --write` (about 3 minutes). Monthly
USD returns net of trading costs; risk-free BIL; benchmark GUIDE_BENCH
(55% ACWX / 35% EMB / 10% GLD, quarterly). In-sample = 2013-01 to 2017-12
(60 months: the walk-forward cannot start before all 12 picks have six
months of common history, HYEM lists 2012-05). Out-of-sample (OOS) =
2018-01 to 2026-10 (106 months).

## The portfolio to hold today (ex-ante weights, $100,000)

| Sleeve | Positions | Weight |
|---|---|---|
| US growth stocks (15%) | AVGO 3.0%, NVDA 6.5%, AMZN 5.5% | 15% |
| International growth stocks (30%) | TSMC 2330.TW 10%, Bajaj Finance 10%, Constellation 10% | 30% |
| EM bond funds (45%) | PYEMX 15%, CEMB 15%, EMB 14%, HYEM 1% | 45% |
| Other (10%) | IAU 9%, SLV 1% | 10% |

Non-US share 75% (72.4% after whole-share rounding; $2,715 stays in cash
because Constellation costs about $2,500 a share). Expected return 8.0% a
year (consensus_usd of the picks), volatility 9.9%. Order list:
`reports/final/order_list.csv`.

## Why the weights are what they are, and which constraints bind

The rules leave little room. With the 10% single-stock cap the three
international stocks can hold at most 30%, so the 70% floor forces the EM
bond sleeve to at least 40% (its band is 25-45%) and US stocks plus metals
to at most 30%. The feasible equity range is 45-58%, not 45-65%. The exact
55/35/10 guideline is outside the feasible set under any split: the
"guideline-feasible" version (20% US / 35% international) meets the 70%
floor only by holding 11.7% in each international stock, above the cap.

Inside that box the optimizer goes to corners. At the quarterly rebalances
the binding constraints were: PYEMX at its 15% cap (87% of rebalances),
SLV at its 1% floor (84%), equity at its 45% minimum (82%), Constellation
at 10% (78%), IAU at 10% (70%), CEMB at 15% (67%). The 70% floor itself
bound at only 25% of rebalances. The ex-ante weights hit ten bounds at
once. These are corner solutions: the weights express the rules more than
the estimates.

## The comparison (in-sample / OOS)

| Portfolio | CAGR | Vol | Sharpe | IR vs GUIDE | Max DD | Worst year | Non-US |
|---|---|---|---|---|---|---|---|
| (a) guideline 55/35/10 | 27.2 / 20.8% | 10.0 / 16.3% | 2.48 / 1.10 | 2.77 / 1.40 | -4.8 / -26.9% | +16.1 / -20.9% | 62% (fails) |
| (a2) guideline-feasible | 26.2 / 19.6% | 10.0 / 15.8% | 2.40 / 1.06 | 2.68 / 1.40 | -5.9 / -25.7% | +14.7 / -19.4% | 70% (cap fails) |
| (b) optimized | 22.8 / 16.1% | 9.1 / 14.2% | 2.30 / 0.95 | 2.51 / 1.19 | -6.7 / -25.5% | +10.4 / -18.7% | 72% |
| (c) optimized + put | 20.1 / 14.9% | 8.6 / 12.3% | 2.17 / 0.99 | 2.14 / 0.96 | -7.6 / -25.3% | +7.5 / -18.4% | 72% |
| (e) no 70% rule | 22.9 / 16.5% | 9.1 / 14.3% | 2.31 / 0.97 | 2.54 / 1.23 | -6.7 / -25.7% | +10.4 / -18.5% | 71% (fails at times) |
| GUIDE_BENCH | 4.4 / 6.2% | 8.3 / 12.5% | 0.55 / 0.34 | n/a | -13.0 / -25.7% | -3.8 / -15.4% | 90% |
| SIXTY_FORTY | 10.2 / 9.4% | 5.8 / 10.8% | 1.69 / 0.65 | 0.91 / 0.42 | -4.9 / -20.1% | +1.1 / -15.9% | 0% |
| GLOBAL_6040 | 7.4 / 7.5% | 6.1 / 10.5% | 1.18 / 0.51 | 0.71 / 0.21 | -7.5 / -21.3% | -1.0 / -16.1% | 22% |

**The guideline was better than the optimized portfolio.** Equal weights
inside 55/35/10 beat the optimizer OOS on Sharpe (1.10 vs 0.95), IR and
return, at a deeper drawdown (-26.9% vs -25.5%). The rule-compliant
alternative (a2) also beat it (1.06), but it breaks the stock cap. The
optimizer's shrunk 3-year means kept pushing weight into bonds and gold and
away from the US stocks that drove 2018-2026. Method.md section 12 lists
this as a valid finding. Every pick-based portfolio beats every benchmark
by a wide margin. That edge comes from the picks, which are 2026 survivors,
so it is not evidence of skill (see the limits below).

**What the 70% rule costs.** Little. Without it (e), OOS Sharpe is 0.97
instead of 0.95 and CAGR 16.5% instead of 16.1%, and the drawdown is about
the same. The unconstrained optimizer chose 71% non-US on average but
dipped to 61% at its targets and 57% after drift. The rule costs about
0.4%/yr and 0.02 of Sharpe. The sleeve bands and the stock cap bind far
more often than the rule does. Treating gold and silver as neutral (John's
question) moves OOS Sharpe from 0.95 to 0.97 and drawdown by +0.5 points,
and leaves today's ex-ante weights unchanged. The classification is worth
almost nothing here.

## Did the adjustments help?

Quarterly rebalancing, net of costs (0.04%/yr cost drag, 23%/yr one-way
turnover), against buy-and-hold from the first weights: OOS CAGR -14.1
points/yr, OOS max drawdown 6.3 points shallower, OOS Sharpe -0.13.
Buy-and-hold let NVDA run, so it earned far more. Its non-US share drifted
down to 23%, so it would have broken the 70% rule within two years. The
adjustments bought rule compliance and a smaller drawdown, and they cost
return. Rebalancing frequency and lookback hardly matter: OOS Sharpe ranges
0.94-0.98 across monthly, quarterly, semi-annual and annual and across 3-
and 5-year windows (`variants.csv`). The 5-year windows have shallower
drawdowns (-24.2% to -24.7%). The drift trigger (non-US share below 0.68)
forced 11 extra rebalances, nine of them in 2022-2024.

## Did the overlay help?

The put on the S&P 500, at h = 1 of the equity sleeve, cost 1.3%/yr OOS.
It raised OOS Sharpe a little (0.95 to 0.99, because volatility fell from
14.2% to 12.3%), cut the Covid loss from -15.6% to -6.5%, and barely moved
the OOS max drawdown (-25.5% to -25.3%: the 2022 decline was slow, and
puts pay for crashes). IR vs GUIDE_BENCH fell from 1.19 to 0.96. By the
letter of rule 8.5 it survives on the Sharpe leg, but by a margin well
inside estimation error. Basis: the international sleeve's OOS correlation
with SPY is 0.68 (0.37 in-sample), so about half of its variance is not
hedged by an S&P put. One XSP contract is h = 1.69 of today's equity
sleeve. At that ratio OOS Sharpe is 0.97 and drawdown -25.7%. Verdict: not
worth adding. Optional at most, and only as a stated over-hedge.

## Monte Carlo, 7 years, against the method.md section 1 targets

Forward drift 8.0%/yr, the weighted consensus. Circular block bootstrap
(block 6, 20,000 paths) of the optimized walk-forward series. Inflation
2.66%/yr, the US CPI average for 2010-2026.

| Target | Result | Pass |
|---|---|---|
| Median ending value at least $145,000 | $174,400 (5th-95th: $98,700-$283,400) | yes |
| P(nominal loss) at most 10% | 5.4% | yes |
| P(beat US CPI) at least 75% | 86.5% | yes |
| Max drawdown within -25% (backtest) | -25.5% (Dec 2021 to Oct 2022) | **no, by 0.5 points** |
| Worst calendar year within -20% | -18.7% (2022) | yes |

The historical-drift version gives a median of $332,000. That number
replays NVDA's run and is not a forecast. Per section 1, the security
budget wins: the shortfall is reported, not hidden. The pre-registered
alternatives that do meet -25% are the 5-year lookback (-24.2%, OOS Sharpe
0.97) and minimum variance (-24.6%, 0.93). Choosing one of them now would
be a choice made after seeing the OOS results, so that decision belongs to
John and must be labelled as such.

## For John's team (three sentences)

1. The rules (70% non-US, 3-10% per stock, sleeve bands) leave a narrow
   box: about 15% US stocks, 30% international stocks, 45% EM bonds and 10%
   gold and silver, with a forecast of about 8% a year.
2. A simple equal-weight version of the 55/35/10 guideline did as well as
   or better than the optimizer from 2018 to 2026, and the 70% rule itself
   cost only about 0.4% a year.
3. Expect a fall of about 25% in a bad year like 2022, which is right at
   the security limit; protective puts did not prevent it.

## Honest limits

- **Survivorship and selection.** The 12 picks are 2026 survivors chosen
  partly on their 2018-2026 results. The walk-forward weights are out of
  sample; the asset list is not. Every backtest number here overstates what
  an investor in 2013 or 2017 could have achieved. The in-sample Sharpe
  ratios above 2 show the effect (NVDA and AVGO in 2013-2017).
- One OOS regime of 8.8 years (a strong dollar, the 2022 rate shock, an AI
  rally). No 2008 test is possible: CEMB and HYEM did not exist.
- The weights are optimized on history, and most of them sit on bounds. The
  ex-ante weights rest on one consensus forecast per asset, and the EM bond
  forecasts on one method.
- Data: NVDA, TSMC, SPY, ACWI and META prices end 2026-10-23, so the last
  week of October is carried flat for them. Taiwan, India and Canada closes
  are aligned to US trading days (forward-fill of at most 5 days). Buying
  TSMC and Bajaj local shares needs an international account; the TSM ADR
  is the cross-check, and Bajaj has none.
- Funds and other assets have a 1% floor ("every pick held"). This is the
  builder's reading, not a method.md number. The 2010-start variant needed
  a 22.5% fund cap until CEMB and HYEM listed, and is flagged as breaking
  the 15% cap.
