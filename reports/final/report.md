# Global Portfolio Research: Final Report

AFMBA622 Global Portfolio Research, UMass Boston. Written 2026-11-07 and reviewed line by line against the scorecard the same day. Market data run to 2026-11-06 (`reports/final/portfolio.json`, field `as_of`; a few tickers end on 2026-10-23, see Appendix C).

## How to read the source notes

Every number carries a source in square brackets. The code names the file; the command below reproduces it. Where a table comes from one file, the source line sits under the table instead of in each cell. All commands run from the repository root.

| Code | File | Command that produces it |
|---|---|---|
| PJ | `reports/final/portfolio.json` (portfolio numbers) | `python -m portfolio.build --write` |
| CMP, VAR, ORD | `reports/final/comparison.csv`, `variants.csv`, `order_list.csv` | `python -m portfolio.build --write` |
| PM | `research/candidates/memos/portfolio.md` (Phase 5 memo; its numbers are PJ numbers) | `python -m portfolio.build --write` |
| US, INTL, BND, OTH, OVL | `reports/candidates/<ID>.json` for the US growth, international growth, EM bond, other-sleeve and overlay candidates | `python -m research.candidates.us_growth --all --write`, `... intl_growth --all --write`, `... em_bonds --all --write`, `... other_sleeve --all --write`, `... overlays --all --write` |
| SCC, SCD | `reports/candidates/scorecard.csv`, `research/plan/scorecard.md` | `python research/plan/scorecard.py --write` |
| CTL | control tables and rank tests: `reports/candidates/us_growth_control_summary.json`, `us_growth_control.csv`, `intl_growth_control_summary.json`, `intl_growth_control.csv`, `em_bonds_control_rank.json`, `em_bonds_control.csv`, `other_control_rank.json`, `other_control.csv` | the `--all --write` command of the type (US: `python -m research.candidates.us_growth --control --write`) |
| HARD, SIG, ITB | `research/plan/longlists/<type>_hard.csv`, `<type>_signals.csv`, `<type>_insample_table.csv` | `python -m research.screen hard --type <type> --as-of 2017-12-31`, `python -m research.screen validate --type <type>`, `python research/plan/shortlist_table.py` |
| REV | `reports/candidates/reviews/<type>_review.md` and `.json` | `python -m research.reviews.us_growth_check`, `intl_growth_check`, `em_bonds_check`, `other_check`, `overlays_check` |
| MEM | `research/candidates/memos/<ID>.md` (analyst text; numbers are candidate-JSON numbers) | the candidate command above |
| METH, PLAN, SHORT, DR | `research/plan/method.md`, `PLAN.md`, `shortlist.md`, `data_request.md` | documents, no command |

Where two files disagree I use `portfolio.json` for portfolio numbers and the candidate JSON for candidate numbers. The disagreements I found are listed in Appendix D.

Metric words are defined the first time they appear and again in the glossary in Appendix A. "IS" means in-sample, "OOS" means out-of-sample. A t-statistic below 2 is called weak evidence. A p-value above 0.05 is called not significant.

---

## 1. Purpose and client brief

The client has $100,000 and a 7-year horizon. The goal is growth plus security. The client wants a mostly passive portfolio with periodic adjustments, built with a quantitative method that combines technical and fundamental analysis. At least 70% of total portfolio value must be outside the United States. The target mix is roughly 55% stocks, 35% bonds and 10% other. Derivatives are allowed. The initial structure is three US growth stocks, three international growth stocks, four emerging-market (EM) bonds, a derivatives overlay and an unspecified 10% "other" sleeve [METH header, PLAN settings]. The course also asks for efficient frontiers, returns in local and base currency, and bottom-up analysis of the top holdings.

The portfolio is judged on risk-adjusted return out of sample: the Sharpe ratio (excess return over the risk-free rate, divided by volatility) and the information ratio (IR: active return over a benchmark, divided by tracking error) come first. Maximum drawdown (the worst peak-to-trough loss), inflation resilience and currency risk break ties [METH section 1].

The pre-registered objective in numbers [METH section 1]:

| Item | Rule |
|---|---|
| Base currency and capital | USD, $100,000 |
| Horizon | 7 years (Nov 2026 to Nov 2033) |
| Growth target | median 7-year ending value at least $145,000 in the forward Monte Carlo |
| Security budget | maximum drawdown no worse than -25% in the walk-forward backtest; probability of a nominal loss at most 10%; probability of beating US CPI at least 75%; worst calendar year no worse than -20% |
| Priority | if both cannot be met, the security budget wins and the shortfall is reported |

In short (Section 10): the process is defensible, the picks' out-of-sample record is not proof of skill, and one of the five section-1 targets, the drawdown limit, is missed by 0.47 points.

**Two periods are used and they differ for candidates and for the portfolio.** Candidate assets are scored in-sample on 2010-01 to 2017-12 (96 months) and out-of-sample on 2018-01 to 2026-10 (106 months) [US, INTL, BND, OTH `data.months_in_sample`, `months_out_of_sample`]. The portfolio walk-forward cannot start before all 12 picks have six months of common history. HYEM lists in May 2012, so the portfolio backtest starts in 2013-01 and its in-sample window is 2013-01 to 2017-12 (60 months), not 2010-2017 [PJ `notes`, `settings.walk_forward_start`; PM header]. Out-of-sample is 106 months for both.

---

## 2. Investment philosophy

**Mostly passive.** The brief says "mostly passive with periodic adjustments". In practice this meant three things.

1. No market timing and no discretionary calls. The only trades are rule-based: a quarterly rebalance back to the target weights, plus an extra rebalance if the non-US share drifts below 68% [METH section 10; PJ `settings.drift_floor`].
2. Low turnover and low cost. Over 2013-2026 the portfolio made 67 rebalances: the scheduled quarterly ones plus 11 extra, drift-triggered ones [PJ `adjustments.weight_changes`, field `drift_triggered`]. Annual one-way turnover was 23.0% and the cost drag was 0.039% a year [PJ `portfolios.optimized.turnover`, `cost_drag`].
3. Cheap, simple vehicles where a vehicle could be chosen. By weight, 40% of the portfolio is in passive funds (EMB, CEMB, HYEM, IAU, SLV), 15% is in one active fund (PYEMX) and 45% is in six single stocks [PJ `ex_ante.weights`; the sums are arithmetic on those weights].

Honest reading: the stock half is not passive. Six single stocks are a concentrated, active choice. "Mostly passive" here describes the management style (rules, few trades), not the holdings.

**Quantitative.** Every choice goes through rules fixed before results were seen: hard screens, a 100-point rubric, a pre-registered technical-signal test and an adversarial review [METH status line].

**Fundamental plus technical, and what actually happened.** The brief asked for both. The fundamental side worked as designed (growth, quality and valuation scores for stocks; carry, credit and cost scores for bond funds). The technical side did not survive its own test. Five signals (12-1 month momentum, 200-day trend, 6-month relative strength, low volatility, distance below the 52-week high) were each tested in four position types. None met the pre-registered bar (out-of-sample IR above zero and t above 1.0) in any type [SIG; SHORT "Technical signals: none kept"]. Per the rule fixed in advance, the technical weight in the rubric was redistributed to the other components. **So the final portfolio contains no technical analysis, because the technical analysis we tested did not add value out of sample.** That is a result, not an omission.

**Periodic adjustments.** The adjustments were tested, not assumed. Section 8 shows what they bought (rule compliance and a shallower drawdown) and what they cost (return).

---

## 3. Constraints and how they were implemented

### 3.1 The 70% non-US rule

The rule is applied to total portfolio value. Each asset has a non-US share, fixed before any result was seen [METH section 3]:

| Asset | Non-US share |
|---|---|
| Stock | 1.0 if the company's headquarters or domicile is outside the US (an ADR or US listing of a foreign company counts as non-US; MercadoLibre, Uruguay, counts as non-US), else 0.0 |
| Bond fund | share of holdings whose issuer is non-US (EM sovereign and corporate funds: 1.0, even when USD-denominated) |
| Equity fund | share of holdings domiciled outside the US, from the latest factsheet (source and date recorded) |
| Gold, commodities, USD cash, US TIPS, US REITs | 0.0 (no foreign country; counted conservatively against the 30% US/neutral room) |
| Global ex-US REITs, international inflation-linked bonds | by holdings, as for funds |
| Derivative overlay | the share of its underlying |

The check is on target weights at every rebalance date: the non-US share must be at least 0.70. Between rebalances the share drifts; a reading below 0.68 triggers a rebalance. Gold and silver are classified 0.0 non-US by default. The project owner (John) was asked at check-in 1 and approved the method; the default stood, and both treatments are shown [PLAN answers log]. Section 6.6 shows the treatment barely matters.

In the final portfolio the six international and EM positions count 1.0 and the three US stocks and the two metals count 0.0 [SCD "Final list for Phase 5"; ORD column `non_us_share`].

### 3.2 The 55/35/10 guideline and its tolerance

The target mix is 55% stocks, 35% bonds, 10% other. The pre-registered tolerance is plus or minus 10 percentage points per sleeve, so the allowed bands are stocks 45-65%, bonds 25-45% and other 0-20% [METH section 10; PJ `settings.sleeve_bands`]. Any drift beyond the tolerance must be justified in writing and the exact guideline shown alongside. The guideline portfolio is the exact 55/35/10 split with equal weights inside each sleeve, on the same rebalance schedule [METH section 10].

### 3.3 Position counts and bounds

Three US growth stocks, three international growth stocks, four EM bond funds, one to three "other" assets. A single stock is at most 10% of the portfolio and at least 3% if held. A single fund is at most 15%. A single "other" asset is at most 10%. The backtest builder added a 1% floor for each fund and each "other" asset ("every pick is held"). That floor is the builder's reading, not a number in the method [PJ `settings.stock_bounds`, `fund_bounds`, `other_bounds`, `notes`].

Trading costs charged in the backtest: 5 bp one way on US-listed stocks and ETFs, 15 bp on foreign local shares, 0 bp on the open-end fund PYEMX [PJ `settings.costs_bp_one_way`].

### 3.4 What turned out to be infeasible

The exact 55/35/10 mix, a 10% metals sleeve, a 10% single-stock cap and the 70% non-US rule cannot all hold at once. The arithmetic:

- With the 10% single-stock cap, the three international stocks can hold at most 30%.
- Gold and silver count as 0% non-US. A 10% metals sleeve plus three US stocks must therefore stay within the 30% that the 70% rule leaves for US or neutral assets.
- The exact 55/35/10 guideline puts 27.5% in US stocks and 10% in metals: 37.5% US or neutral, so 62.5% non-US. **It fails the 70% rule.**
- The "guideline-feasible" version (20% US stocks, 35% international stocks, 35% bonds, 10% other) meets 70% only by holding 11.67% in each international stock, **above the 10% cap**.
- Inside the caps, the 70% floor forces the EM bond sleeve to at least 40% (its band tops out at 45%), and the feasible stock range is 45-58%, not 45-65%.

| Rule set | US stocks | Intl stocks | All stocks | Bonds | Other | Non-US share |
|---|---|---|---|---|---|---|
| 70% rule on | 15.0% to 28.0% | 25.0% to 30.0% | 45.0% to 58.0% | 40.0% to 45.0% | 2.0% to 15.0% | 70.0% to 75.0% |
| no 70% rule | 15.0% to 30.0% | 15.0% to 30.0% | 45.0% to 60.0% | 25.0% to 45.0% | 2.0% to 20.0% | 50.0% to 75.0% |
| gold and silver neutral | 15.0% to 29.4% | 18.0% to 30.0% | 45.0% to 59.4% | 26.0% to 45.0% | 2.0% to 20.0% | 56.0% to 75.0% |

Source: `reports/final/portfolio.json` `rule_checks.feasible_region.*.groups` and `.non_us_share`, `python -m portfolio.build --write`. The "other" range starts at 2% because two "other" positions are held at 1% each.

| Weights | US stocks | Intl stocks | Bonds | Other | Non-US | 70% met | Position-bound violations | All met |
|---|---|---|---|---|---|---|---|---|
| Ex-ante weights (order list) | 15.0% | 30.0% | 45.0% | 10.0% | 75.0% | yes | none | yes |
| Guideline 55/35/10 | 27.5% | 27.5% | 35.0% | 10.0% | 62.5% | no | none | no |
| Guideline-feasible (20% US / 35% intl) | 20.0% | 35.0% | 35.0% | 10.0% | 70.0% | yes | 2330.TW, BAJFINANCE.NS, CSU.TO | no |

Source: `reports/final/portfolio.json` `rule_checks.ex_ante.check`, `.guideline`, `.guideline_feasible`, `python -m portfolio.build --write`.

The stock cap (10%) and the 3-10% stock band are the team's rules in the method, not the client's. Relaxing the cap would let the guideline-feasible weights through. That is a decision for the team, not something the data settle (Section 6.5).

---

## 4. Method

The method was written and committed before any candidate was backtested. It could change afterwards only through a logged entry and a full rerun [METH header, section 13].

### 4.1 Samples

In-sample (IS) 2010-01 to 2017-12; out-of-sample (OOS) 2018-01 to 2026-10, monthly, USD, total returns, risk-free rate BIL (a T-bill ETF). All screens, signal tests and the shortlist use only data before 2018. A candidate needs 60 months before 2018 (listed by 2012-12-31) to be scored; under 120 months in total is flagged "short history" [METH section 2]. The walk-forward portfolio re-estimates on a trailing window, so every portfolio return is OOS by construction. **The asset list is not OOS** (Section 5.4).

### 4.2 Universes and hard screens

| Position type | Universe | Hard screens (in-sample data only) |
|---|---|---|
| US growth stocks (3) | Nasdaq-100 members, the 50 largest S&P 500 Growth members, plus a faded-leaders list (survivorship check) | US domicile; listed by 2012-12-31; market cap at least $10B today and $2B at 2017-12-31; traded value at least $20M a day; 3-year revenue CAGR at 2017-12-31 at least 8% (point-in-time, SEC EDGAR) |
| International growth stocks (3) | largest 120 non-US companies with a growth profile, developed and EM, local listing preferred | non-US domicile; listed by 2012-12-31; market cap at least $10B; traded value at least $10M a day; revenue CAGR at least 8%, point-in-time where SEC data exist, else current statements flagged "not point-in-time" |
| EM bond funds (4) | US-listed EM bond ETFs and major open-end funds: hard-currency sovereign, local-currency sovereign, corporate and high yield | 60 months by 2017; assets at least $200M; fee at most 1.00%; daily liquidity |
| Other sleeve (1-3) | gold, silver, commodities, natural resources, ex-US REITs, infrastructure, TIPS, international linkers, managed futures | 60 months by 2017; assets at least $200M; fee at most 0.75% |
| Overlays | covered calls, protective puts, collars, FX forwards | modelled history over the full OOS period |

Source: [METH section 4].

### 4.3 Fundamental screens, technical screens and their validation

Fundamental scores are percentile ranks within the type at 2017-12-31 (in-sample) and on latest data (forward thesis). Stocks: growth 40% (revenue and net income CAGR), quality 30% (ROIC or ROE, margins, leverage), valuation 30% (free-cash-flow yield, P/E relative to own history). Bond funds: carry 40%, credit and country quality 30%, cost and liquidity 15%, diversification 15%. Other sleeve: inflation beta 40%, correlation with ACWX and EMB 30%, carry and expense ratio 30% [METH section 5].

The five technical signals (T1 to T5) are validated by a long-only top-tercile test against the equal-weighted long list, monthly, 10 bp one-way cost. A signal is kept only if its OOS IR is above zero and its OOS t-statistic is above 1.0 [METH section 6]. None was kept (Section 5.2).

Multiple testing: with 20-46 names per type, the best OOS Sharpe is partly luck. Each candidate therefore reports a deflated Sharpe ratio (the probability that the true Sharpe beats the best of N luck-only trials, Bailey and Lopez de Prado 2014) and t-statistics, and each type reports the Spearman rank correlation between the in-sample and OOS scores [METH section 7].

### 4.4 Rubric, benchmarks and drop rules

The 100-point rubric (percentile rank within type times weight) [METH section 7]:

| Component | Weight | Measured as |
|---|---|---|
| OOS Sharpe ratio (USD) | 20 | monthly, vs BIL |
| OOS information ratio vs type benchmark | 15 | monthly |
| OOS maximum drawdown | 10 | less negative is better |
| Consistency | 10 | share of rolling 36-month windows with IR above zero |
| Diversification | 10 | lower OOS correlation with the other sleeves' benchmarks |
| Inflation resilience | 5 | return 2021-12-31 to 2022-10-31 and beta to CPI changes |
| Liquidity and cost | 5 | traded value and expense ratio |
| Forward 7-year expected return | 15 | consensus of at least two methods |
| Fundamental score | 5 | latest data |
| Technical score | 5 | kept signals only (none kept, so the 5 points were redistributed pro rata) |

Benchmarks [METH section 9]: US growth stocks IVW (S&P 500 Growth ETF); international growth stocks a 50/50 mix of EFG and EEM (EAFE Growth and EM); EM bonds EMB (local-currency funds EMLC); other sleeve GLD (gold); the whole portfolio GUIDE_BENCH (55% ACWX, 35% EMB, 10% GLD, reset quarterly). Context benchmarks: SIXTY_FORTY (SPY/AGG) and GLOBAL_6040 (ACWI/AGG).

A candidate is dropped if it has too little history, fails a reviewer-confirmed load-bearing claim, cannot be reproduced, or (rule 8.2) has an OOS Sharpe below its type benchmark and an OOS IR below zero. A derivative overlay is dropped (rule 8.5) if it neither raises the portfolio's OOS Sharpe nor cuts its maximum drawdown by 2 points after costs [METH section 8].

### 4.5 Adversarial review

For each of the five types, a separate reviewer who did not build it reran the committed code and hunted for look-ahead, survivorship, cherry-picked windows, wrong benchmarks, missing fees and currency errors. All numbers reproduced byte-for-byte or to 1e-6 [SCD "Review summary"; REV]. The findings that changed results were fixed and rerun before the picks were made:

| Finding | Severity | Fix |
|---|---|---|
| Grinold-Kroner repricing mixed a forward non-GAAP P/E with a trailing GAAP target, inflating four US forward estimates | high | both ends trailing GAAP; AVGO 14.4% to 11.4%, NVDA 15.3% to 13.0%, ADBE 16.5% to 15.0% |
| EM bond yields had the fund fee subtracted twice (SEC yields are already net of fees) | high | removed; forward estimates up 0.3-0.9 points |
| Mexico's 10-year yield gaps were spliced, flipping the peso's sign in the country table | high | gaps of at most 3 months forward-filled, longer gaps dropped |
| Screening code tagged Broadcom, Sirius, KDP and Gen Digital as financials | medium | whole-word match; Broadcom's in-sample rank 1 to 2, shortlist unchanged |
| Monte Carlo under-sampled the first and last months | medium | circular block bootstrap; medians move up to about 2 points |
| "Gold has a negative inflation beta" | medium | not supported under any lag; wording is now "no detectable relationship" |

Source: [SCD "Review summary" table]. Caveats the reviewers could not fix and that travel with the results: 22 of 31 international passers, including all eight shortlisted, were screened on current statements, not point-in-time ones; home indices for local-currency comparisons are price indices; the EM bond forward estimates rest on one method; the model covered-call return runs 0.9% a year above the CBOE indices [SCD].

### 4.6 What changed after the method was written, and why

The change log [METH section 13] has eight entries: six clarifications and two bug fixes. None changes a pre-registered threshold or weight. The WTMF, faded-leader and rule 8.2 entries were made in response to what the screener did, before the scorecard was written. The two bug fixes came from reviewers, and every affected number was rerun. The full log is reproduced in Appendix B. Other decisions that are not in that log but matter, all recorded elsewhere:

- The portfolio in-sample window starts in 2013, not 2010, because HYEM lists in 2012 (Section 1) [PJ `notes`]. A 2010-start variant is in `variants.csv` and breaks the 15% fund cap for 12 rebalances.
- Check-in 3: John approved the picks as scored, with SK Hynix left out under the downgrade rule [PLAN answers log].
- The international shortlist was frozen on the in-sample table as it stood on 2026-11-07, in which Constellation Software ranked 8th and HDFC Bank 11th. Later that day the financial-tag bug fix (Appendix B) changed a few fundamental scores and the table was regenerated: HDFC Bank now ranks 7th and Constellation 10th. The shortlist was not changed, because out-of-sample work had already started and re-choosing it then would not have been a clean in-sample choice. No diversity swap was made; `shortlist.md` records this (Appendix D, item 3) [ITB `intl_growth_stock_insample_table.csv`; SHORT].

---

## 5. What the screens found

### 5.1 Long lists and pass counts

| Type | Rows on the long list | Candidates | Passed hard screens | Main failure |
|---|---|---|---|---|
| US growth stocks | 128 (87 candidates, 20 faded leaders, 21 too young) | 87 | 46 (40 candidates + 6 faded leaders) | 3-year revenue CAGR below 8% (for example Apple 7.8%, Microsoft 1.2%) |
| International growth stocks | 81 (60 candidates, 8 faded leaders, 13 too young) | 60 | 31 (27 + 4 faded leaders) | revenue CAGR below 8% (for example SAP 7.6%, LVMH 0.7%, Samsung 3.3%) |
| EM bond funds | 43 (20 candidates, 11 excluded on assets or fees, 12 too young) | 20 | 20 | n/a |
| Other sleeve | 108 (33 candidates, 41 excluded on class or fees, 34 too young) | 33 | 33 | n/a |
| Overlays | 15 strategies | 15 | modelled in Phase 3 | 5 infeasible at $100,000 or outside the overlay-only rule |

Sources: pass counts and role counts from `research/plan/longlists/<type>_hard.csv` (HARD); the named examples and the overlay count from [SHORT "Long lists and hard screens"]. For 22 of 31 international passers the revenue screen and fundamental score use current statements, because those companies do not file with the SEC [SHORT; REV intl]. Two more flags: the traded-value screen was "not checked" in the Phase 2 tables (volumes were fetched later; the candidate memos report traded value), and the 2017 market cap was "not checked" for 16 US names without point-in-time share counts [SHORT].

### 5.2 The technical-signal result

Out-of-sample IR (t-statistic) of each signal's top-tercile portfolio against the long-list equal-weight, with the in-sample IR beside it. A signal is kept only if OOS IR is above zero and OOS t is above 1.0.

| Signal | US growth IS / OOS IR (OOS t) | International growth | EM bonds | Other sleeve |
|---|---|---|---|---|
| T1 12-1 month momentum | 0.38 / -0.17 (-0.5) | 0.77 / 0.09 (0.3) | 0.17 / -0.36 (-1.1) | 0.37 / 0.23 (0.7) |
| T2 above 200-day average | -0.21 / -0.18 (-0.6) | -0.46 / -0.09 (-0.3) | -0.09 / -0.98 (-2.9) | -0.46 / -0.44 (-1.3) |
| T3 6-month relative strength | 0.50 / 0.18 (0.5) | 0.26 / 0.12 (0.3) | -0.99 / -0.51 (-1.5) | 0.39 / 0.24 (0.7) |
| T4 low volatility | -0.65 / -0.68 (-2.0) | -0.17 / -0.57 (-1.7) | 0.24 / 0.16 (0.5) | -0.12 / -0.52 (-1.5) |
| T5 near 52-week high | -0.34 / -0.41 (-1.2) | -0.33 / -0.56 (-1.7) | -0.31 / -0.82 (-2.5) | -0.04 / -0.35 (-1.0) |

Source: `research/plan/longlists/<type>_signals.csv`, `python -m research.screen validate --type <type>`. **No signal was kept in any type.** Momentum (T1) and 6-month relative strength (T3) were positive in-sample for stocks and roughly zero out of sample (t below 1). The trend filter (T2), low volatility (T4) and the 52-week-high rule (T5) were negative in both periods for growth stocks. Two EM-bond results are significant but in the wrong direction: T2 (t -2.9) and T5 (t -2.5). The validation used OOS data once, by design; no candidate was ranked on it [SHORT].

### 5.3 The survivorship check

Faded leaders (companies that were top-ranked in 2010-2015 and are still listed) went through the same screens. In-sample several looked fine. Out of sample they did badly. Delisted companies cannot be priced, so the check understates survivorship bias rather than removing it.

US faded leaders that passed the hard screens [CTL `us_growth_control.csv`]:

| Ticker | In-sample rank (of 46) | OOS Sharpe rank (of 46) | OOS Sharpe | OOS IR | OOS max drawdown |
|---|---|---|---|---|---|
| BIIB | 10 | 45 | -0.003 | -0.41 | -65.7% |
| ILMN | 17 | 43 | 0.17 | -0.20 | -83.9% |
| SIRI | 18 | 46 | -0.05 | -0.54 | -66.7% |
| CTSH | 36 | 44 | 0.10 | -0.37 | -53.5% |
| AKAM | 39 | 42 | 0.19 | -0.29 | -39.5% |
| EXPE | 43 | 32 | 0.40 | 0.08 | -58.5% |

The six US faded leaders had a median OOS Sharpe of 0.136 and only one of six had a positive OOS IR (16.7%), against a median of 0.572 and 65.2% for all 46 passers [CTL `us_growth_control_summary.json`]. A 2017 screen would have shortlisted Biogen (10th of 46). International: Baidu ranked 26th of 31 in-sample and had an OOS Sharpe of -0.11; Petrobras ranked 30th in-sample and had an OOS Sharpe of 0.70, 4th of 31 [REV intl, "Verified correct"] [CTL `intl_growth_control_summary.json`].

### 5.4 Did the 2017 screen predict the 2018-2026 winners? No.

The test is the Spearman rank correlation (rho; +1 means identical ranking, 0 means unrelated) between each name's in-sample composite score and its OOS Sharpe ratio.

| Type | Spearman rho (p), in-sample composite vs OOS Sharpe | n | Reading |
|---|---|---|---|
| US growth | +0.14 (0.36) | 46 | positive, not significant |
| International growth | -0.02 (0.93) | 31 | no predictive value |
| EM bond funds | +0.20 (0.42) | 18 | not significant |
| Other sleeve | +0.13 (0.48) | 31 | not significant |

Sources: [CTL `us_growth_control_summary.json` `rank_tests.composite_vs_oos_sharpe`; `intl_growth_control_summary.json` `rank_test_composite_vs_oos_sharpe`; `em_bonds_control_rank.json` `composite_vs_oos_sharpe`; `other_control_rank.json` `composite_vs_oos_sharpe`]. The JSON files label some of these "predictive: true" because rho is above zero. With p-values of 0.36 to 0.93 they are not significant, and the reviewers asked that they be described as such [REV intl finding 3; SCD].

**State it plainly: the 2017 screen did not predict the 2018-2026 winners in any sleeve.** Further detail:

- **US growth.** Only 9 of 46 passers (19.6%) beat IVW on OOS Sharpe. The shortlist's median OOS Sharpe (0.572) equals the median of all 46 passers. Of the ten best OOS names, the in-sample ranks were 9 (NVDA), 2 (AVGO), 32, 19, 29, 7, 21, 8, 23 and 30. AVGO ranked 2nd both ways. NVDA, ranked 9th in-sample, was chosen into the eight by a diversity decision made before OOS data were looked at [CTL; REV us_growth finding 4; `NVDA.json` `review.notes`].
- **International growth.** ASML (in-sample rank 24, OOS Sharpe 0.84, IR t 2.84) and Petrobras (rank 30, OOS Sharpe 0.70) were the best OOS names and were not shortlisted [CTL `best_not_shortlisted_by_oos_sharpe`]. The reviewer's price-only re-ranking moves SK Hynix from the top eight to 19th, because half the composite is a fundamental score built on 2025 statements [REV intl, "High"].
- **EM bonds.** Three funds outside the shortlist (EEIIX 0.192, PEBIX 0.138, EMHY 0.134) scored above the best pick, HYEM (0.133), on OOS Sharpe. With a corrected IR the rho is 0.17 (p 0.49), and on returns alone 0.16 (p 0.52) [REV em_bonds].
- **Other sleeve.** In-sample Sharpe vs OOS Sharpe has rho -0.59 (p 0.0003, n 32): the in-sample losers (commodities, metals) won OOS. The fundamental score alone had rho +0.50 (p 0.004). The reviewer shows the near-duplicate funds (eight TIPS funds, three gold clones) overstate both p-values; on 13 category means the figures are -0.55 (p 0.052) and +0.65 (p 0.017) [CTL `other_control_rank.json`; REV other finding 4].

This matters because the method says that when the in-sample ranking has no predictive value, the picks must "lean on the forward models and drawdown, not on the OOS ranking" [METH section 7]. The rubric still uses OOS ranks: OOS Sharpe (20 points), OOS IR (15), OOS maximum drawdown (10), diversification (10) and inflation resilience (5) are 60 of the 100 points and are measured on 2018-2026 data [METH section 7]. So the picks are partly selected on 2018-2026 results. That is why the portfolio's backtest overstates what an investor in 2017 could have earned (Sections 8 and 10).

---

## 6. Allocation

### 6.1 Final weights by asset type, region, sector and currency

The portfolio to hold today is the "ex-ante" set of weights: the optimizer run once on the latest data, with expected returns taken from the forward consensus of each pick. All tables in 6.1 are arithmetic sums of those twelve weights [PJ `ex_ante.weights`, `positions`; sector and country labels from each pick's JSON `sector` and `country`; commands in the source key].

| Ticker | Sleeve | Weight | Sector / sub-type (candidate JSON) | Country (candidate JSON) | Listing currency | Non-US share |
|---|---|---|---|---|---|---|
| AVGO | us_equity | 3.00% | Technology / Semiconductors | US | USD | 0 |
| NVDA | us_equity | 6.55% | Technology / Semiconductors | US | USD | 0 |
| AMZN | us_equity | 5.45% | Consumer Cyclical / Internet Retail | US | USD | 0 |
| 2330.TW | intl_equity | 10.00% | Semiconductors (foundry) | TW | TWD | 1 |
| BAJFINANCE.NS | intl_equity | 10.00% | Consumer finance (NBFC) | IN | INR | 1 |
| CSU.TO | intl_equity | 10.00% | Vertical-market software | CA | CAD | 1 |
| PYEMX | em_bonds | 15.00% | hard_sov | EM | USD | 1 |
| CEMB | em_bonds | 15.00% | corporate | EM | USD | 1 |
| EMB | em_bonds | 14.00% | hard_sov | EM | USD | 1 |
| HYEM | em_bonds | 1.00% | high_yield | EM | USD | 1 |
| IAU | other | 9.00% | Gold bullion | GLOBAL | USD | 0 |
| SLV | other | 1.00% | Silver bullion | GLOBAL | USD | 0 |

| Asset type | Weight | Guideline (brief) | Difference (pts) |
|---|---|---|---|
| Stocks (US + international) | 45.0% | 55% | -10.0 |
|    of which US growth stocks | 15.0% |  |  |
|    of which international growth stocks | 30.0% |  |  |
| Bonds (EM bond funds) | 45.0% | 35% | +10.0 |
| Other (gold + silver) | 10.0% | 10% | 0.0 |

Stocks are 45% and bonds are 45%. Both sit exactly on the edge of the pre-registered plus-or-minus 10 point tolerance (stocks 10 points below the guideline, bonds 10 points above). Section 3.4 and 6.4 explain why the rules force this.

| Region of issuer or listing | Weight |
|---|---|
| United States (AVGO, NVDA, AMZN) | 15.00% |
| Taiwan (TSMC) | 10.00% |
| India (Bajaj Finance) | 10.00% |
| Canada (Constellation Software, listed in Toronto) | 10.00% |
| Emerging-market issuers via USD bond funds (PYEMX, CEMB, EMB, HYEM) | 45.00% |
| Global, no country (gold, silver) | 10.00% |

| Sector or sub-type | Weight |
|---|---|
| Semiconductors (AVGO, NVDA, TSMC) | 19.55% |
| Internet retail and cloud (AMZN) | 5.45% |
| Consumer finance (Bajaj Finance) | 10.00% |
| Vertical-market software (Constellation) | 10.00% |
| EM sovereign bonds (PYEMX, EMB) | 29.00% |
| EM corporate bonds (CEMB investment grade, HYEM high yield) | 16.00% |
| Gold (IAU) | 9.00% |
| Silver (SLV) | 1.00% |

| Listing currency | Weight |
|---|---|
| USD (US stocks, four USD bond funds, IAU, SLV) | 70.00% |
| TWD (TSMC, listed in Taipei) | 10.00% |
| INR (Bajaj Finance) | 10.00% |
| CAD (Constellation, listed in Toronto) | 10.00% |

Two things the sector table makes visible. First, three semiconductor-linked stocks (AVGO, NVDA, TSMC) are 19.5% of the portfolio and 43% of the stock sleeve (19.5% / 45%). The analysts' memos tie all three to AI data-centre spending [MEM AVGO, NVDA, 2330_TW]. Second, only 30% of the portfolio is outside USD-listed assets: 70% is USD, so the currency exposure is smaller than "70% non-US" suggests. The bond funds are USD-denominated, so their non-US exposure is credit risk, not currency risk.

### 6.2 The order list

| Ticker | Name | Sleeve | Target weight | Target $ | Shares | Price (local) | Invested $ | Non-US share | Exchange |
|---|---|---|---|---|---|---|---|---|---|
| AVGO | Broadcom Inc. | us_equity | 3.00% | $3,000 | 10 | 293.69 USD | $2,937 | 0 | NASDAQ |
| NVDA | NVIDIA Corporation | us_equity | 6.55% | $6,549 | 31 | 210.96 USD | $6,540 | 0 | NASDAQ |
| AMZN | Amazon.com, Inc. | us_equity | 5.45% | $5,451 | 21 | 259.30 USD | $5,445 | 0 | NASDAQ |
| 2330.TW | Taiwan Semiconductor Manufacturing Company Limited | intl_equity | 10.00% | $10,000 | 136 | 2,385.00 TWD | $9,951 | 1 | TWSE (ADR TSM) |
| BAJFINANCE.NS | Bajaj Finance Limited | intl_equity | 10.00% | $10,000 | 868 | 1,087.75 INR | $9,996 | 1 | NSE India |
| CSU.TO | Constellation Software Inc. | intl_equity | 10.00% | $10,000 | 3 | 3,526.52 CAD | $7,548 | 1 | TSX |
| PYEMX | Payden Emerging Markets Bond Fund | em_bonds | 15.00% | $15,000 | 1,405.811 | 10.67 USD | $15,000 | 1 | open-end |
| CEMB | iShares J.P. Morgan EM Corporate Bond ETF | em_bonds | 15.00% | $15,000 | 340 | 44.04 USD | $14,974 | 1 | Cboe BZX |
| EMB | iShares J.P. Morgan USD Emerging Markets Bond ETF | em_bonds | 14.00% | $14,000 | 152 | 91.96 USD | $13,978 | 1 | Nasdaq |
| HYEM | VanEck Emerging Markets High Yield Bond ETF | em_bonds | 1.00% | $1,000 | 52 | 19.18 USD | $997 | 1 | NYSE Arca |
| IAU | iShares Gold Trust | other | 9.00% | $9,000 | 117 | 76.38 USD | $8,936 | 0 | NYSE Arca |
| SLV | iShares Silver Trust | other | 1.00% | $1,000 | 21 | 46.87 USD | $984 | 0 | NYSE Arca |

Source: `reports/final/order_list.csv`, `python -m portfolio.build --write`. Prices are the latest close in `data/research/prices.csv` (NVDA and TSMC: 2026-10-23, the rest 2026-11-06). Shares are whole numbers except for the open-end fund PYEMX. Constellation trades near $2,516 a share, so its 10% slot buys 3 shares and leaves $2,452 unspent. Invested: $97,285; cash left: $2,715, which counts as US-neutral. After rounding the non-US share is 72.4% [PJ `positions_summary.optimized_ex_ante`]. TSMC is bought as TSM (the ADR) in a US account or as 2330.TW through an international account; Bajaj Finance has no ADR on disk, so it needs an international account [PM "Honest limits"; ORD column `adr`].

Ex-ante, the portfolio has an expected return of 8.03% a year, volatility of 9.94% and a Sharpe of 0.41 against a forward risk-free rate of 3.94% (covariance window 2023-10-26 to 2026-10-30) [PJ `ex_ante`]. The frontier chart uses a different covariance estimator and risk-free rate and shows 11.0% volatility for the same weights (6.7).

### 6.3 Rule checks

| Portfolio | 70% non-US met at every rebalance | Sleeve bands met | Position bounds met | Minimum target non-US share | All rules met |
|---|---|---|---|---|---|
| (a) guideline 55/35/10 equal weight | no | yes | yes | 62.5% | no |
| (a2) guideline-feasible | yes | yes | no | 70.0% | no |
| (b) optimized (chosen) | yes | yes | yes | 70.0% | yes |
| (e) optimized, no 70% rule | no | yes | yes | 61.5% | no |

Source: `reports/final/portfolio.json` `portfolios.<name>.rule_checks`, `python -m portfolio.build --write`. "Met at every rebalance" tests the target weights on every rebalance date. The realised share drifts between rebalances:

| Portfolio | Mean daily non-US share | Minimum daily | Trading days below 70% | Trading days below 68% |
|---|---|---|---|---|
| (b) optimized (chosen) | 71.8% | 68.0% | 684 | 0 |
| min-variance (rule on) | 72.3% | 68.1% | 259 | 0 |
| (e) optimized, no 70% rule | 71.1% | 57.1% | 921 | 365 |
| (a) guideline 55/35/10 equal weight | 61.9% | 56.6% | 3479 | 3479 |
| (a2) guideline-feasible | 69.6% | 65.1% | 2159 | 377 |
| buy-and-hold from first optimized weights | 60.2% | 22.6% | 2267 | 1998 |

Source: `reports/final/portfolio.json` `portfolios.<name>.rule_checks.realised_non_us` and `adjustments.buy_and_hold.realised_non_us`. The chosen portfolio's realised non-US share never fell below 68.0%, by design of the drift trigger, but it was below 70% on 684 trading days. The rule as pre-registered tests targets, not daily drift, so (b) passes; a stricter reading would not.

### 6.4 Why the weights are where they are, and which constraints bind

With the 10% stock cap, the three international stocks hold at most 30%. The 70% floor then forces EM bonds to at least 40% and caps US stocks plus metals at 30%. Inside that box the optimizer moves to corners. At the 67 rebalances the binding constraints were:

| Constraint binding at the quarterly rebalance | Share of 67 rebalances, rule on | Share of rebalances, no 70% rule |
|---|---|---|
| PYEMX at 15% cap | 86.6% | 70.1% |
| SLV at 1% floor | 83.6% | 71.6% |
| Equity sleeve at 45% minimum | 82.1% | 67.2% |
| Constellation at 10% cap | 77.6% | 64.2% |
| IAU at 10% cap | 70.1% | 56.7% |
| CEMB at 15% cap | 67.2% | 53.7% |
| EMB at 1% floor | 64.2% | 49.3% |
| Bajaj at 10% cap | 53.7% | 44.8% |
| TSMC at 10% cap | 50.7% | 44.8% |
| AMZN at 3% floor | 35.8% | 22.4% |
| Bond sleeve at 45% maximum | 28.4% | 26.9% |
| AVGO at 3% floor | 25.4% | 22.4% |
| 70% non-US floor | 25.4% | n/a |
| HYEM at 15% cap | 22.4% | 20.9% |
| AVGO at 10% cap | 16.4% | 10.4% |
| NVDA at 3% floor | 14.9% | 14.9% |
| AMZN at 10% cap | 13.4% | 13.4% |
| NVDA at 10% cap | 7.5% | 4.5% |

Source: `reports/final/portfolio.json` `rule_checks.binding_share_optimized`, `binding_share_no_rule`, `python -m portfolio.build --write`. The 70% non-US floor bound at only 25.4% of the rebalances. The sleeve bands and the position caps bound far more often. At the ex-ante weights ten bounds hold at once (equity minimum, bond maximum, AVGO at 3%, TSMC, Bajaj and Constellation at 10%, PYEMX and CEMB at 15%, HYEM and SLV at 1%) [PJ `ex_ante.binding`]. **These are corner solutions: the weights express the rules more than they express the return estimates.**

Two signs that the bond weights in particular carry little information:

- The last walk-forward weights (2026-10-01) hold EMB at 1% and HYEM at 14%, while the order-list weights hold EMB at 14% and HYEM at 1%. The two runs use different return inputs (shrunk history versus forward consensus) and different covariance windows, and they flip these two funds [PJ `sensitivity.gold_neutral.last_walk_forward_weights` and `ex_ante.weights`].
- The reviewer found the EM bond funds statistically tied on out-of-sample evidence: every |t| of IR against the type benchmark is below 0.9 (except EMB and EMLC measured against GUIDE_BENCH) and the best deflated Sharpe is 0.071 [REV em_bonds, "Methodology findings"].

HYEM at 1% and SLV at 1% are token positions that satisfy "four bond funds" and "every pick held". They are not conviction weights. HYEM's reviewer verdict was "downgrade"; it took the fourth bond slot only because the type had three passes for four slots [SCD].

### 6.5 Guideline, guideline-feasible and no-rule comparisons; what the 70% rule costs

Section 8.1 gives the full out-of-sample comparison. The allocation-relevant facts:

- **The exact guideline (a) fails the 70% rule** (62.5% target non-US; mean realised 61.9%) but meets every other rule [PJ `rule_checks.guideline`; CMP].
- **The guideline-feasible portfolio (a2)** meets the 70% target but needs 11.67% in each international stock, breaking the 10% cap [PJ `rule_checks.guideline_feasible`]. Its mean realised non-US share is 69.6%, with 377 days below 68%.
- **What the rule costs.** Without the rule (e), OOS Sharpe is 0.97 instead of 0.95, CAGR 16.5% instead of 16.1%, and the maximum drawdown is -25.7% instead of -25.5% [CMP]. The rule costs about 0.4 points a year and 0.02 of Sharpe. The unconstrained optimizer still chose 71.1% non-US on average, but it dipped to 57.1% on its worst day and was below 68% on 365 days [PJ `portfolios.no_rule.rule_checks.realised_non_us`]. The rule is cheap here because the picks already lean non-US.
- **What the stock cap costs.** The cap, not the 70% rule, separates (b) from (a2). (a2) had a higher OOS Sharpe (1.06 versus 0.95). Whether to relax a 10% single-stock cap that the team set itself is a decision for the team, not something the data decide.

### 6.6 Gold classification and runner-up sensitivity

Treating gold and silver as US-neutral (the 70% floor then applies to the rest of the portfolio) leaves today's ex-ante weights unchanged and moves the backtest only a little. Swapping single picks for their runners-up changes OOS Sharpe by -0.083 to -0.002:

| Portfolio | Sharpe IS | Sharpe OOS | Max DD OOS | Change in OOS Sharpe | Change in max DD (pts, + = shallower) |
|---|---|---|---|---|---|
| Base (b) |  | 0.952 | -25.5% |  |  |
| AMZN replaced by MA | 2.24 | 0.950 | -25.1% | -0.002 | +0.41 |
| CSU.TO replaced by REA.AX | 2.20 | 0.868 | -27.4% | -0.083 | -1.93 |
| HYEM replaced by TGEIX | 2.28 | 0.938 | -25.6% | -0.014 | -0.12 |
| SLV replaced by GNR | 2.30 | 0.935 | -25.5% | -0.017 | -0.03 |
| Gold and silver treated as neutral (70% on the rest) | 2.30 | 0.968 | -25.0% | +0.016 | +0.46 |

Source: `reports/final/portfolio.json` `sensitivity`, `python -m portfolio.build --write`. With gold neutral the feasible non-US range widens to 56-75% and US stocks can reach 29.4% [PJ `sensitivity.gold_neutral.feasible_region`]. Even so, the gold-neutral portfolio's maximum drawdown is -25.02%, which still misses the -25% target by 0.02 points. The classification question is worth almost nothing in this sample. The one swap that matters is Constellation to REA, which lowers OOS Sharpe by 0.083 and deepens the drawdown by 1.9 points.

### 6.7 Efficient frontiers

The frontier code is `research/frontier.py`, extended for the 70% rule and the sleeve bands. It uses monthly USD returns for the 12 picks and a covariance shrunk 30% toward its diagonal [PJ `frontiers.cov_method`]. The ex-ante frontier uses the forward consensus return of each pick. The ex-post frontier uses sample means for 2012-06 to 2026-10 (173 months). The ex-post frontier is hindsight and is shown for description only.

| Frontier | Rule | Point | Return | Vol | Sharpe | Non-US |
|---|---|---|---|---|---|---|
| Ex-ante (consensus forward returns) | 70% rule | min-variance | 7.7% | 10.5% | 0.58 | 70.0% |
| Ex-ante (consensus forward returns) | 70% rule | max-Sharpe | 8.1% | 10.9% | 0.60 | 71.2% |
| Ex-ante (consensus forward returns) | no rule | min-variance | 7.7% | 10.5% | 0.58 | 69.9% |
| Ex-ante (consensus forward returns) | no rule | max-Sharpe | 8.1% | 10.9% | 0.60 | 71.2% |
| Ex-ante (consensus forward returns) |  | guideline | 8.3% | 12.6% | 0.54 |  |
| Ex-ante (consensus forward returns) |  | guideline-feasible | 8.3% | 12.4% | 0.54 |  |
| Ex-ante (consensus forward returns) |  | chosen (order list weights) | 8.0% | 11.0% | 0.58 |  |
| Ex-post (2012-06 to 2026-10 sample means) | 70% rule | min-variance | 17.4% | 10.5% | 1.50 | 70.0% |
| Ex-post (2012-06 to 2026-10 sample means) | 70% rule | max-Sharpe | 22.0% | 12.2% | 1.67 | 70.0% |
| Ex-post (2012-06 to 2026-10 sample means) | no rule | min-variance | 17.4% | 10.5% | 1.50 | 69.9% |
| Ex-post (2012-06 to 2026-10 sample means) | no rule | max-Sharpe | 23.2% | 12.6% | 1.71 | 61.2% |
| Ex-post (2012-06 to 2026-10 sample means) |  | guideline | 22.1% | 12.6% | 1.63 |  |
| Ex-post (2012-06 to 2026-10 sample means) |  | guideline-feasible | 21.4% | 12.4% | 1.60 |  |
| Ex-post (2012-06 to 2026-10 sample means) |  | chosen (order list weights) | 18.3% | 11.0% | 1.52 |  |

Source: `reports/final/portfolio.json` `frontiers.ex_ante`, `frontiers.ex_post`, `python -m portfolio.build --write`. Reading it:

- Ex-ante, the 70% rule makes no difference to the best portfolio: the max-Sharpe point is 71.2% non-US with or without the rule.
- Ex-post, the rule costs a little: max Sharpe 1.67 with the rule (70.0% non-US) versus 1.71 without (61.2% non-US).
- The chosen portfolio sits inside the frontier: ex-ante Sharpe 0.58 versus 0.60 at the top; ex-post 1.52 versus 1.67. The guideline portfolio is well below the ex-ante frontier (0.54) but near the ex-post one (1.63). It holds 55% in stocks against 45%, and the ex-post sample means favour stocks [PJ `frontiers.ex_post.mu`].

Charts: `charts/frontier_ex_ante.png`, `charts/frontier_ex_post.png`, `charts/weights.png` (relative to `reports/final/`).

---

## 7. Security analysis per position

All figures: USD, monthly, risk-free BIL. Candidate figures come from `reports/candidates/<ID>.json` (commands in the source key). Business descriptions and risks are the analysts' text from the memos [MEM] and the reviewers' judgement [REV]; they are not independently verified facts. Per-pick charts: `../candidates/charts/<ID>_growth.png` and `<ID>_rolling.png` (relative to `reports/final/`; for example `../candidates/charts/NVDA_growth.png`).

### 7.0 The twelve picks side by side

| Pick | Benchmark | CAGR IS / OOS | Sharpe IS / OOS | IR (t) IS / OOS | Deflated Sharpe IS / OOS | Max DD IS / OOS | Months IS / OOS |
|---|---|---|---|---|---|---|---|
| AVGO | IVW | 41.2% / 37.0% | 1.38 / 0.98 | 0.97 (2.74) / 0.72 (2.15) | 0.96 / 0.76 | -23.5% / -31.7% | 96 / 106 |
| NVDA | IVW | 35.2% / 53.6% | 0.92 / 1.11 | 0.63 (1.79) / 1.04 (3.10) | 0.65 / 0.84 | -49.9% / -62.8% | 96 / 106 |
| AMZN | IVW | 31.0% / 17.4% | 1.12 / 0.58 | 0.72 (2.03) / 0.19 (0.57) | 0.83 / 0.29 | -23.7% / -52.1% | 96 / 106 |
| 2330.TW | EFG_EEM_5050 | 22.4% / 32.2% | 1.20 / 0.96 | 0.94 (2.65) / 1.13 (3.35) | 0.90 / 0.78 | -15.9% / -46.3% | 96 / 106 |
| BAJFINANCE.NS | EFG_EEM_5050 | 59.8% / 16.0% | 1.39 / 0.51 | 1.37 (3.87) / 0.43 (1.29) | 0.97 / 0.28 | -41.0% / -58.5% | 96 / 106 |
| CSU.TO | EFG_EEM_5050 | 45.7% / 17.6% | 1.66 / 0.64 | 1.48 (4.18) / 0.51 (1.50) | 1.00 / 0.43 | -18.3% / -51.9% | 96 / 106 |
| PYEMX | EMB | 7.0% / 3.0% | 0.98 / 0.10 | 0.20 (0.57) / 0.29 (0.87) | 0.77 / 0.06 | -12.1% / -27.8% | 96 / 106 |
| CEMB | EMB | 4.4% / 2.8% | 0.66 / 0.07 | -0.15 (-0.36) / 0.09 (0.27) | 0.37 / 0.05 | -11.3% / -20.3% | 68 / 106 |
| EMB | GUIDE_BENCH | 6.5% / 2.2% | 0.92 / 0.02 | 0.07 (0.20) / -0.76 (-2.27) | 0.73 / 0.03 | -11.3% / -26.7% | 96 / 106 |
| HYEM | EMB | 6.5% / 3.4% | 0.98 / 0.13 | 0.16 (0.39) / 0.22 (0.67) | 0.64 / 0.07 | -11.1% / -26.0% | 67 / 106 |
| IAU | GLD | 1.9% / 12.9% | 0.19 / 0.68 | n/a / n/a | 0.06 / 0.46 | -42.6% / -26.4% | 96 / 106 |
| SLV | GLD | -0.4% / 12.3% | 0.15 / 0.44 | 0.07 (0.21) / 0.15 (0.45) | 0.04 / 0.20 | -71.9% / -47.5% | 96 / 106 |

Source: `reports/candidates/<ID>.json` `metrics.in_sample.usd`, `metrics.out_of_sample.usd`; deflated Sharpe uses N = 46 (US), 31 (international), 20 (EM bonds), 33 (other) trials. IR is against the benchmark in column 2; EMB's IR is against GUIDE_BENCH, and IAU has no IR (same asset as its benchmark GLD).

| Position | OOS local CAGR | OOS FX a year | OOS USD CAGR | FX share of USD variance | OOS hedged CAGR (CIP model) | Hedge cost a year | Hedged minus unhedged | Sharpe local IS / OOS | Sharpe USD IS / OOS |
|---|---|---|---|---|---|---|---|---|---|
| 2330.TW | 33.5% | -1.0% | 32.2% | 17.7% | 34.8% | -0.25% | +2.6% | 1.24 / 1.09 | 1.20 / 0.96 |
| BAJFINANCE.NS | 21.3% | -4.4% | 16.0% | 8.3% | 18.3% | 3.42% | +2.2% | 1.45 / 0.55 | 1.39 / 0.51 |
| CSU.TO | 19.1% | -1.2% | 17.6% | 14.4% | 19.3% | 0.13% | +1.6% | 1.83 / 0.74 | 1.66 / 0.64 |

Source: `reports/candidates/{2330_TW,BAJFINANCE_NS,CSU_TO}.json` `currency` and `metrics.*.local`, `python -m research.candidates.intl_growth --all --write`. The hedge columns are a model (monthly covered-interest-parity forward, 5 bp per roll). The reviewer warns that the hedge gains are a 2018-2026 dollar outcome, not carry: carry was a cost for INR (3.42% a year), CAD and AUD [REV intl, "Medium" 1]. US stocks, the four bond funds and the metals are priced in USD, so their local and USD returns are equal.

| Pick | GFC 2008 (benchmark) | Taper 2013 | Covid 2020 | 2022 shock |
|---|---|---|---|---|
| AVGO | n/a | 21.2% (3.2%) | -21.0% (-16.4%) | -27.7% (-27.4%) |
| NVDA | -76.6% (-45.4%) | 8.2% (3.2%) | 11.6% (-16.4%) | -54.1% (-27.4%) |
| AMZN | -27.3% (-45.4%) | 10.7% (3.2%) | -2.9% (-16.4%) | -38.6% (-27.4%) |
| 2330.TW | -31.0% (-57.9%) | -9.8% (-6.7%) | -13.0% (-17.8%) | -44.6% (-29.6%) |
| BAJFINANCE.NS | -86.5% (-57.9%) | -31.9% (-6.7%) | -51.7% (-17.8%) | -7.0% (-29.6%) |
| CSU.TO | -28.5% (-57.9%) | 21.5% (-6.7%) | -14.2% (-17.8%) | -21.2% (-29.6%) |
| PYEMX | -13.2% (n/a) | -12.1% (-11.2%) | -16.4% (-16.0%) | -25.0% (-25.1%) |
| CEMB | n/a | -11.3% (-11.2%) | -13.9% (-16.0%) | -19.0% (-25.1%) |
| EMB | n/a | -11.2% (-6.5%) | -16.0% (-16.9%) | -25.1% (-23.2%) |
| HYEM | n/a | -4.9% (-11.2%) | -16.3% (-16.0%) | -23.4% (-25.1%) |
| IAU | 17.9% (17.8%) | -5.7% (-5.7%) | -0.7% (-0.9%) | -11.0% (-11.1%) |
| SLV | -10.3% (17.8%) | -3.7% (-5.7%) | -22.4% (-0.9%) | -18.1% (-11.1%) |

Source: `reports/candidates/<ID>.json` `stress`, return of the pick (benchmark in brackets). "n/a" means the asset did not exist. The 2008 figure for gold is IAU's, not a portfolio figure.

| Pick | CAPM | DCF implied | Grinold-Kroner | Yield-based | Monte Carlo median | Consensus (USD) | 5th to 95th percentile (annualised) |
|---|---|---|---|---|---|---|---|
| AVGO | 9.9% | 16.1% | 8.2% |  | 11.5% | 11.4% | -5.0% to 30.8% |
| NVDA | 12.0% | 15.7% | 11.2% |  | 13.5% | 13.0% | -17.4% to 54.0% |
| AMZN | 9.9% | 6.1% | 8.3% |  | 8.2% | 8.1% | -8.3% to 27.1% |
| 2330.TW | 11.0% | 10.9% | 14.9% |  | 11.0% | 10.9% | -4.6% to 29.2% |
| BAJFINANCE.NS | 10.1% |  | 11.1% |  | 11.2% | 11.1% | -11.9% to 39.7% |
| CSU.TO | 8.2% | 11.1% | 9.2% |  | 9.1% | 8.7% | -8.1% to 26.3% |
| PYEMX |  |  |  | 6.6% | 6.7% | 6.6% | -0.1% to 13.4% |
| CEMB |  |  |  | 5.9% | 6.0% | 6.0% | 1.2% to 10.5% |
| EMB |  |  |  | 6.2% | 6.3% | 6.3% | -0.4% to 12.7% |
| HYEM |  |  |  | 5.5% | 5.7% | 5.6% | -0.3% to 11.1% |
| IAU |  |  |  |  | 5.3% | 5.3% | -5.0% to 16.8% |
| SLV |  |  |  |  | 2.9% | 3.1% | -15.5% to 26.6% |

Source: `reports/candidates/<ID>.json` `expected_return_7y`, annual, USD. The consensus is the median of the available methods; the Monte Carlo drift is set to the consensus, so it is not an independent check. For the bond funds the consensus is in practice one method (yield) [REV em_bonds, "Medium"]. For IAU and SLV the consensus is the mean of a real-yield model and a historical model; for IAU these are 0.6% and 10.0%, and the reviewer found the real-yield model's predictions correlated -0.55 with what gold (GLD) later returned over 166 overlapping seven-year windows [`IAU.json`; REV other finding 3].

### 7.1 AVGO (Broadcom), 3.0%

**Thesis and drivers.** Custom AI accelerators and networking chips for the largest cloud companies, plus enterprise software (VMware) on multi-year contracts; a consolidator that buys franchises, cuts cost and pays out cash. Returns depend on hyperscaler AI spending, software renewals and free-cash-flow pay-out [MEM AVGO].
**Fundamentals.** Latest fiscal year (ended 2025-11-02): revenue $63.9bn, 3-year revenue CAGR 24.4%, operating margin 39.9%, ROIC 19.3%, net debt / EBITDA 2.00, trailing P/E 61.6, free-cash-flow yield 1.9%. **Not point-in-time:** no filing under this CIK was known at 2017-12-31 (Singapore-domiciled until 2018), so its 2017 fundamental score (0.59) came from current statements [US `AVGO.json` `fundamentals.latest`, `screens`]. With a neutral score the reviewer found it would rank 5th rather than first (before the tag fix moved it to second) [REV us_growth findings 1, 5].
**Currency.** USD; none.
**Risks.** Few AI customers, a capex downturn, acquisition debt, a P/E near 60. OOS drawdown -31.7% breaks the -25% budget [MEM].
**Reviewer.** Pass. OOS IR 0.72 (t 2.15), positive in all 71 fully-OOS 36-month windows; deflated Sharpe 0.76. The memo wording "a screen using only data to 2017 picked it" was wrong for AVGO [REV us_growth].
**In plain English.** (1) Broadcom makes chips and software for big data centres and grew by buying companies. (2) From 2018 to October 2026 it returned 37.0% a year against 16.3% for the S&P 500 Growth fund, with a worst fall of -31.7% (fund -30.5%). (3) Our models expect about 11% a year (range -5% to 31%), and most past return came from the AI build-out.

### 7.2 NVDA (Nvidia), 6.5%

**Thesis and drivers.** The GPUs, networking and software (CUDA) on which most AI models are trained and run; revenue rose from $6.9bn (year ended 2017-01) to $215.9bn (year ended 2026-01). Returns depend on AI data-centre spending, product cycles, margins and China export rules [MEM NVDA; US `NVDA.json` `fundamentals`].
**Fundamentals (point-in-time, SEC).** At 2017-12-31: 3-year revenue CAGR 18.7%, operating margin 28.0%, ROIC 28.3%, trailing P/E 75.3 (score 0.58). Latest: revenue CAGR 100.0%, operating margin 60.4%, ROIC 71.3%, P/E 43.1, free-cash-flow yield 2.0%.
**Currency.** USD; none.
**Risks.** An AI-spending pause, custom chips taking share, export controls, and the highest volatility of the eight (46.7% a year OOS; -62.8% OOS drawdown, -54.1% in the 2022 window) [US `NVDA.json`].
**Reviewer.** Pass. OOS IR 1.04 (t 3.10; Newey-West 2.75), the only US name that clears a Bonferroni bar for choosing among eight; deflated Sharpe 0.84, below the usual 0.95. In-sample rank 9 of 46; it entered the eight over FANG, LRCX and ORLY by a diversity decision made before OOS data were used [REV us_growth findings 4, 6; `NVDA.json` `review.notes`].
**In plain English.** (1) Nvidia makes the processors that run most AI work. (2) From 2018 to October 2026 it returned 53.6% a year against 16.3% for the growth fund, but fell as much as 62.8% along the way. (3) Our models expect about 13% a year (range -17% to 54%); it is held small, and the evidence rests on one regime, the AI build-out.

### 7.3 AMZN (Amazon), 5.5%

**Thesis and drivers.** Retail and advertising plus AWS, its most profitable segment; operating margin rose from 3.1% (FY2016) to 11.2% (FY2025). Returns depend on AWS growth, advertising, retail margin and data-centre capex [MEM AMZN].
**Fundamentals (point-in-time, SEC).** 2017: revenue $136.0bn, 3-year CAGR 22.2%, ROIC 30.2%, trailing P/E 238.7 (score 0.72). Latest: revenue $716.9bn, CAGR 11.7%, ROIC 16.3%, P/E 36.2, free-cash-flow yield 5.0%. Flag: no dividend file, so P/E and FCF yield are slightly biased.
**Currency.** USD; none.
**Risks.** Heavy capex, cloud competition, antitrust; no dividend. Its DCF implied return (6.1%) is the lowest of the eight US candidates [MEM].
**Reviewer.** Pass. The analyst memo ranked it fourth of eight ("runner-up"); the rubric put it third (59.0 points) behind AVGO and NVDA and ahead of META (47.5). MA (57.7) ranked after every pass because of its downgrade [SCD; SCC]. OOS alpha is -0.2% (t -0.03) and IR 0.19 (t 0.57): weak evidence for this pick.
**In plain English.** (1) Amazon is the largest online retailer and a leading cloud provider. (2) From 2018 to October 2026 it returned 17.4% a year against 16.3% for the growth fund, with a worst fall of -52.1% (fund -30.5%). (3) Our models expect about 8% a year (range -8% to 27%): a fine company that has not beaten the growth index.

### 7.4 TSMC (2330.TW), 10.0%

**Thesis and drivers.** The leading contract chipmaker, making nearly all leading-edge logic chips (Apple, Nvidia, AMD, Broadcom). Returns depend on AI accelerator demand, its technology lead, pricing power and dividends [MEM 2330_TW].
**Fundamentals.** Latest 20-F (FY2024): 3-year revenue CAGR 22.2%, operating margin 45.7%, ROIC 34.7%, trailing P/E 53.4 (Yahoo forward P/E 16). **Not point-in-time in the screen:** TSMC's first SEC XBRL filing is 2018, so the 2017 screen used current data (score 0.60, in-sample rank 4 of 31) [INTL `2330_TW.json` `screens`, `fundamentals_latest`; REV intl].
**Currency.** OOS TWD return 33.5% a year, TWD -1.0%, USD return 32.2%; the currency was 17.7% of USD variance. A monthly model hedge would have returned 34.8%, using a flat 1.8% Taiwan rate (no series on disk), so it is approximate. The TSM ADR returned about 0.9 to 1.5 points a year more than the local line OOS (Appendix D, item 6).
**Risks.** Taiwan Strait geopolitics (in no backtest), customer concentration, tariffs and export controls, the chip cycle (-44.6% in the 2022 window).
**Reviewer.** Pass. The only international name that clears the multiple-testing bar: OOS IR 1.13 (t 3.35 against 2.95 for 31 trials), deflated Sharpe 0.78 [REV intl].
**In plain English.** (1) TSMC makes most of the world's most advanced chips for other companies. (2) Since 2018 it returned 32.2% a year in dollars against 5.8% for the international-growth benchmark, with a worst fall of -46.3%. (3) Our models expect about 11% a year (range -5% to 29%), with a tail risk, Taiwan, that no backtest includes.

### 7.5 Bajaj Finance (BAJFINANCE.NS), 10.0%

**Thesis and drivers.** India's largest retail non-bank lender (consumer durables, personal, SME, mortgage). Returns depend on loan growth of 25% or more a year, margins, credit costs and the Indian equity multiple [MEM BAJFINANCE_NS].
**Fundamentals.** FY ending 2026-03-31: 3-year revenue CAGR 22.6%, net-income CAGR 18.2%, ROE 16.7%, free-cash-flow yield -9.9% (loan growth), trailing P/E 35.7. **Not point-in-time:** current Yahoo statements; score 0.56, in-sample rank 6 of 31. A price-only ranking puts it 2nd, so selection does not depend on the flagged score [INTL `BAJFINANCE_NS.json`, `review.notes`].
**Currency.** OOS INR return 21.3%, INR -4.4% a year, USD return 16.0%; the currency was 8.3% of USD variance. The model hedge would have added 2.2 points but carried a 3.42% a year cost: the gain is a rupee fall larger than the forward priced, not free carry.
**Risks.** Rupee depreciation, the credit cycle (-51.7% in the Covid window), RBI regulation, succession, valuation; the largest FX drag of the three international stocks.
**Reviewer.** Pass. OOS IR 0.43 (t 1.29), deflated Sharpe 0.28: weak evidence. Worst Covid and taper stress of the eight (-51.7%, -31.9%).
**In plain English.** (1) Bajaj Finance lends to Indian consumers and small firms. (2) Since 2018 it returned 16.0% a year in dollars against 5.8% for the benchmark, but the rupee cost 4.4% a year and the worst fall was -58.5%. (3) Our models expect about 11% a year (range -12% to 40%), and the evidence that it beats the benchmark is weak.

### 7.6 Constellation Software (CSU.TO), 10.0%

**Thesis and drivers.** A serial acquirer of small vertical-market software businesses, compounding by reinvesting cash at high returns. Returns depend on capital deployed and the return earned; the founder stepped down as president in 2025 [MEM CSU_TO].
**Fundamentals.** FY2025: 3-year revenue CAGR 20.6%, net-income CAGR 0.0%, operating margin 18.1%, ROIC 21.0%, free-cash-flow yield 5.0%, trailing P/E 103.4 (forward 19; GAAP earnings are depressed by amortisation). **Not point-in-time:** current Yahoo statements; score 0.48, in-sample rank 10 of 31 [INTL `CSU_TO.json`].
**Currency.** Books in USD, listed in Toronto. OOS CAD return 19.1%, CAD -1.2% a year, USD return 17.6%; the currency was 14.4% of USD variance. The model hedge would have added 1.6 points at a carry cost of 0.13%. Revenue is global, so Canada-specific risk is low [MEM].
**Risks.** Larger, lower-return deals, succession, and fear that AI disrupts legacy software (the 2025-26 sell-off; OOS drawdown -51.9%).
**Reviewer.** Pass. OOS IR 0.51 (t 1.50), deflated Sharpe 0.43: weak evidence. The memo's DCF (167% upside from a 5.8% discount rate) looks too high; the 8.7% consensus does not depend on it [`CSU_TO.json` `review.notes`].
**In plain English.** (1) Constellation buys small software companies and holds them for the long term. (2) Since 2018 it returned 17.6% a year in dollars against 5.8% for the benchmark, and fell 51.9% in 2025-26. (3) Our models expect about 9% a year (range -8% to 26%), with weak evidence that it beats the benchmark.

### 7.7 PYEMX (Payden Emerging Markets Bond Fund), 15.0%

**What it is.** An active, mainly USD EM sovereign fund; fee 0.73%; modelled at 0 bp trading cost (the fee is in the NAV). Holdings, duration and rating mix were not retrieved: duration (6.4 years) is borrowed from EMB, the rating mix is assumed, and the 7.03% yield is a trailing distribution yield, not a yield to maturity [MEM PYEMX]. Returns depend on the Treasury yield plus the EM spread, spread changes and duration.
**Fundamentals.** Current only. Top EMB country weights (iShares, 2026-11-05) used as a proxy: South Africa 6.4%, Mexico 6.25%, Turkey 4.9%, Indonesia 4.34%, Brazil 3.89%, Poland 3.59%. Debt/GDP and current account were not checked [MEM; `em_bonds_countries.md`].
**Currency.** None (USD); active managers may hold some local debt, not measured.
**Risks.** Active-manager risk, the 0.73% fee, assumed holdings.
**Reviewer.** Pass. OOS IR vs EMB 0.29 (t 0.87), deflated Sharpe 0.057; IR positive in 85% of OOS 36-month windows (overlapping, so about three independent blocks) [REV em_bonds].
**In plain English.** (1) PYEMX is a managed fund of emerging-market government bonds paid in dollars. (2) Since 2018 it returned 3.0% a year (7.0% in 2010-2017), with a worst fall of -27.8% and a Sharpe of 0.10. (3) Our forward estimate is about 6.6% a year (range -0.1% to 13.4%), from today's yield less expected defaults.

### 7.8 CEMB (iShares J.P. Morgan EM Corporate Bond ETF), 15.0%

**What it is.** Passive USD EM corporate bonds (JPM CEMBI Broad Diversified Core), 1,185 holdings, effective duration 4.21 years, fee 0.50%, 30-day SEC yield 6.34%; small ($0.4bn, thin trading); rating mix not retrieved [MEM CEMB]. Returns depend on corporate spreads and US rates; investment-grade bias.
**Fundamentals.** Current only; 68 in-sample months.
**Currency.** None (USD).
**Risks.** Spread widening, US rates, a small ETF.
**Reviewer.** Pass. Smallest OOS drawdown of the eight (-20.3%), the only one inside -25%, though that limit is a portfolio rule, so the memo wording overclaims. OOS IR 0.09 (t 0.27); in-sample IR -0.15. Forward 6.0% (fee-corrected 5.93%) [REV em_bonds].
**In plain English.** (1) CEMB owns dollar bonds issued by companies in emerging markets. (2) Since 2018 it returned 2.8% a year (4.4% in 2010-2017), with a worst fall of -20.3% and a Sharpe of 0.07. (3) Our forward estimate is about 6.0% a year (range 1.2% to 10.5%).

### 7.9 EMB (iShares J.P. Morgan USD Emerging Markets Bond ETF), 14.0%

**What it is.** Passive USD sovereign and quasi-sovereign bonds (JPM EMBI Global Diversified Core), 619 holdings, duration 6.38 years, fee 0.39%, SEC yield 6.52%; ratings A 17%, BBB 34%, BB 26%, B 19%, CCC 3% (iShares, 2026-11-05). The cheapest, most liquid fund and the type benchmark [MEM EMB]. Returns depend on carry, spreads and US rates.
**Fundamentals.** Current only; its own country weights as above.
**Currency.** None (USD).
**Risks.** Sovereign defaults and restructurings (2020-23: Lebanon, Sri Lanka, Ghana, Zambia, Russia, Ukraine), US rate rises (-25.1% in the 2022 window), Gulf-issuer concentration.
**Reviewer.** Pass; a benchmark has no edge to test. Its OOS IR against GUIDE_BENCH is -0.76 (t -2.27), which the reviewer reads as the asset mix (a bond fund against a 55%-equity benchmark), not the fund [REV em_bonds].
**In plain English.** (1) EMB owns dollar bonds issued by emerging-market governments and agencies. (2) Since 2018 it returned 2.2% a year (6.5% in 2010-2017), with a worst fall of -26.7% and a Sharpe of 0.02. (3) Our forward estimate is about 6.3% a year (range -0.4% to 12.7%); it is the passive core of the bond sleeve.

### 7.10 HYEM (VanEck Emerging Markets High Yield Bond ETF), 1.0%

**What it is.** Passive USD high-yield EM corporate bonds; fee 0.40%; $0.5bn ETF. Duration (4.6 years) is borrowed from a peer (EMHY); the 7.08% yield is a trailing Yahoo yield; the issuer page failed [MEM HYEM]. Returns are mostly spread: high carry, high sensitivity to defaults.
**Fundamentals.** Current only; 67 in-sample months (short).
**Currency.** None (USD).
**Risks.** Defaults in a downturn (China property 2021-22), small-ETF liquidity. The 1.91% assumed credit loss rests on a secondary default table and a forum repost [REV em_bonds].
**Reviewer.** **Downgrade.** The numbers reproduce, but its rank 1 rests on a Sharpe lead of 0.035 over PYEMX that is not meaningful (deflated Sharpe 0.071 versus 0.057). OOS IR 0.22 (t 0.67). It holds the fourth slot because the type had three passes for four slots.
**In plain English.** (1) HYEM owns riskier dollar bonds from emerging-market companies. (2) Since 2018 it returned 3.4% a year (6.5% in 2010-2017), with a worst fall of -26.0% and the highest Sharpe of the eight (0.13), though not distinguishable from the others. (3) Our forward estimate is about 5.6% a year (range -0.3% to 11.1%), and the portfolio holds only 1% of it.

### 7.11 IAU (iShares Gold Trust), 9.0%

**What it is.** A grantor trust holding allocated London gold; fee 0.25%; no income; collectibles tax (up to 28%) [MEM IAU]. Returns depend on the dollar price of gold: real yields, the dollar, central-bank and crisis demand.
**Fundamentals.** None in the cash-flow sense. The forward view averages a real-yield model (0.6% a year) and a historical real-return-plus-breakeven model (10.0%) to 5.3%, which hides a wide gap. Fundamental score 0.63 [OTH `IAU.json`; REV other finding 3].
**Currency.** Priced in USD; OOS beta to monthly changes in the broad dollar index -1.41 [MEM].
**Inflation evidence.** Gold lost 11.0% in the 2021-12 to 2022-10 shock while CPI+2% rose 7.9%. Its monthly CPI beta is not distinguishable from zero under any definition tried (|t| below 1.65): "no detectable relationship", not "negative" [MEM; REV other finding 2].
**Reviewer.** Pass, but only by fee: OOS Sharpe 0.683 versus GLD 0.673 (same asset). Deflated Sharpe 0.46 (0.69 with measured trial variance), far from significant.
**In plain English.** (1) IAU is a gold fund that counts as zero non-US under the course rule. (2) Since 2018 it returned 12.9% a year with a Sharpe of 0.68 and a worst fall of -26.4%, but it lost 11% in the 2022 inflation shock: it diversifies, and does not protect against inflation. (3) Our models put the next seven years at about 5.3% a year with a wide range, and its returns correlate 0.35 with world ex-US stocks.

### 7.12 SLV (iShares Silver Trust), 1.0%

**What it is.** A grantor trust holding silver bars; fee 0.50%; collectibles tax [MEM SLV]. Returns depend on the silver price: monetary demand like gold plus industrial demand.
**Fundamentals.** None; forward consensus 3.1% (range -15.5% to 26.6%).
**Currency.** Priced in USD; OOS beta to dollar-index changes -3.09.
**Risks.** Roughly twice gold's volatility (OOS 32.1% against 16.0%), a -71.9% in-sample and -47.5% OOS drawdown; it lost 22.4% in the Covid window and 18.1% in the 2022 window [MEM].
**Reviewer.** Pass (weak). It survives rule 8.2 only through an IR of 0.15 (t 0.45); its OOS Sharpe (0.44) is well below gold's (0.67) and its correlation with GLD is 0.77. "Silver has a negative inflation beta" was wrong: +1.04 in-sample, 0.00 OOS [REV other finding 2].
**In plain English.** (1) SLV is a silver fund that counts as zero non-US under the course rule. (2) Since 2018 it returned 12.3% a year with a Sharpe of 0.44 and a worst fall of -47.5%, and it lost 18.1% in the 2022 shock. (3) Our models put the next seven years at about 3.1% a year, so it is a 1% position that mostly adds risk.

### 7.13 Runners-up and why each lost

Rank tables from the scorecard (OOS Sharpe, OOS IR with t in brackets, deflated Sharpe, rubric points, reviewer verdict, decision). Benchmark OOS Sharpe: IVW 0.78, EFG/EEM 0.27, EMB 0.02, EMLC -0.10, GLD 0.67 [SCD].

**US growth stocks (benchmark IVW).**

| Rank | Ticker | OOS Sharpe | OOS IR (t) | OOS deflated Sharpe | OOS max DD | 2022 window return | 7y expected return | Rubric | Review | Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AVGO | 0.98 | 0.72 (2.15) | 0.757 | -31.7% | -27.7% | 11.4% | 76.2 | pass | pick |
| 2 | NVDA | 1.11 | 1.04 (3.10) | 0.840 | -62.8% | -54.1% | 13.0% | 74.5 | pass | pick |
| 3 | AMZN | 0.58 | 0.19 (0.57) | 0.290 | -52.1% | -38.6% | 8.1% | 59.0 | pass | pick |
| 4 | META | 0.51 | 0.17 (0.50) | 0.237 | -75.4% | -72.3% | 10.1% | 47.5 | pass | runner-up |
| 5 | MA | 0.72 | 0.14 (0.41) | 0.457 | -26.2% | -8.1% | 8.8% | 57.7 | downgrade | runner-up |
| 6 | GILD | 0.57 | -0.02 (-0.06) | 0.277 | -29.4% | 12.1% | 8.3% | 53.5 | fail | dropped (8.2) |
| 7 | ADBE | 0.21 | -0.26 (-0.77) | 0.054 | -69.4% | -43.8% | 15.0% | 41.0 | fail | dropped (8.2) |
| 8 | REGN | 0.40 | -0.04 (-0.11) | 0.138 | -58.5% | 18.6% | 7.2% | 40.6 | fail | dropped (8.2) |

**International growth stocks (benchmark EFG/EEM 50/50).**

| Rank | Ticker | OOS Sharpe | OOS IR (t) | OOS deflated Sharpe | OOS max DD | 2022 window return | 7y expected return | Rubric | Review | Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2330.TW | 0.96 | 1.13 (3.35) | 0.783 | -46.3% | -44.6% | 10.9% | 76.5 | pass | pick |
| 2 | BAJFINANCE.NS | 0.51 | 0.43 (1.29) | 0.285 | -58.5% | -7.0% | 11.1% | 63.7 | pass | pick |
| 3 | CSU.TO | 0.64 | 0.51 (1.50) | 0.429 | -51.9% | -21.2% | 8.7% | 56.7 | pass | pick |
| 4 | REA.AX | 0.34 | 0.24 (0.73) | 0.139 | -41.1% | -35.1% | 9.9% | 55.1 | pass | runner-up |
| 5 | NOVO-B.CO | 0.30 | 0.16 (0.47) | 0.132 | -73.8% | -1.0% | 7.9% | 42.9 | pass | runner-up |
| 6 | 000660.KS | 0.73 | 0.76 (2.25) | 0.540 | -53.0% | -46.9% | 12.4% | 76.8 | downgrade | not picked |
| 7 | 1299.HK | 0.17 | 0.01 (0.02) | 0.052 | -45.1% | -23.4% | 9.2% | 42.6 | downgrade | not picked |
| 8 | 0700.HK | 0.12 | -0.01 (-0.03) | 0.040 | -69.1% | -53.7% | 10.6% | 35.7 | downgrade | dropped (8.2) |

**EM bond funds (benchmark EMB; local funds EMLC).**

| Rank | Ticker | OOS Sharpe | OOS IR (t) | OOS deflated Sharpe | OOS max DD | 2022 window return | 7y expected return | Rubric | Review | Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PYEMX | 0.10 | 0.29 (0.87) | 0.057 | -27.8% | -25.0% | 6.6% | 76.5 | pass | pick |
| 2 | CEMB | 0.07 | 0.09 (0.27) | 0.049 | -20.3% | -19.0% | 6.0% | 69.2 | pass | pick |
| 3 | EMB | 0.02 | -0.76 (-2.27) | 0.033 | -26.7% | -25.1% | 6.3% | 52.6 | pass | pick |
| 4 | HYEM | 0.13 | 0.22 (0.67) | 0.071 | -26.0% | -23.4% | 5.6% | 78.0 | downgrade | pick |
| 5 | TGEIX | 0.07 | 0.17 (0.50) | 0.048 | -27.5% | -22.8% | 5.9% | 61.7 | downgrade | runner-up |
| 6 | EMLC | -0.10 | -0.83 (-2.47) | 0.013 | -25.5% | -17.5% | 4.7% | 33.7 | downgrade | runner-up |
| 7 | PCY | -0.01 | -0.09 (-0.28) | 0.026 | -35.7% | -32.5% | 5.7% | 45.2 | fail | dropped (8.2) |
| 8 | EBND | -0.14 | -0.12 (-0.36) | 0.010 | -28.0% | -20.3% | 4.8% | 33.1 | fail | dropped (8.2) |

**Other sleeve (benchmark GLD).**

| Rank | Ticker | OOS Sharpe | OOS IR (t) | OOS deflated Sharpe | OOS max DD | 2022 window return | 7y expected return | Rubric | Review | Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | IAU | 0.68 | n/a | 0.464 | -26.4% | -11.0% | 5.3% | 81.6 | pass | pick |
| 2 | SLV | 0.44 | 0.15 (0.45) | 0.204 | -47.5% | -18.1% | 3.1% | 64.6 | pass (weak) | pick |
| 3 | GNR | 0.38 | -0.13 (-0.39) | 0.168 | -35.5% | 3.4% | 7.3% | 66.5 | fail (drop rule 8.2 triggered) | runner-up |
| 4 | IGF | 0.37 | -0.25 (-0.74) | 0.170 | -29.6% | -6.1% | 7.2% | 59.0 | fail (drop rule 8.2 triggered) | runner-up |
| 5 | GSG | 0.41 | -0.04 (-0.12) | 0.196 | -53.2% | 27.7% | 1.3% | 55.3 | fail (drop rule 8.2 triggered) | dropped (8.2) |
| 6 | SCHP | 0.04 | -0.71 (-2.11) | 0.023 | -13.8% | -12.6% | 4.8% | 49.2 | fail (drop rule 8.2 triggered) | dropped (8.2) |
| 7 | VNQI | -0.07 | -0.63 (-1.88) | 0.010 | -32.7% | -30.7% | 8.0% | 45.6 | fail (drop rule 8.2 triggered) | dropped (8.2) |
| 8 | WIP | -0.15 | -0.88 (-2.61) | 0.005 | -23.4% | -19.9% | 5.4% | 33.0 | fail (drop rule 8.2 triggered) | dropped (8.2) |

Source for the four tables: `reports/candidates/scorecard.csv`, `python research/plan/scorecard.py --write`. "7y expected return" is `expected_return_7y.consensus_usd`; "2022 window" is the return 2021-12-31 to 2022-10-31. The scorecard's "decision" blank means not picked and not dropped.

**US runners-up.** META (47.5 points): OOS Sharpe 0.51 is below the index's 0.77, and its OOS drawdown (-75.4%) and 2022 loss (-72.3%) are the worst of the type. MA (57.7, downgraded): the smallest drawdown (-26.2%) and a good 2022 (-8.1% against -27.4%), but OOS Sharpe 0.72 is below IVW's 0.775, IR 0.14 (t 0.41), and it fell more than the index in the Covid window (-23.5% against -16.4%). It is the natural substitute for a lower-volatility US sleeve: swapping it for AMZN leaves OOS Sharpe at 0.950 and the drawdown 0.41 points shallower (Section 6.6). GILD, ADBE and REGN fail rule 8.2 [SCD; REV us_growth].

**International runners-up.** REA.AX (55.1): OOS Sharpe 0.34 barely clears the benchmark's 0.27, IR 0.24 (t 0.73), and the Australian dollar fell with stocks in 2020 and 2022 [MEM REA_AX]. NOVO-B.CO (42.9): OOS Sharpe 0.30, IR 0.16 (t 0.47), and a -73.8% drawdown since the 2024 peak. **SK Hynix (000660.KS) is the judgement call.** It had the highest rubric total (76.8), OOS Sharpe 0.74 and IR 0.76 (t 2.25), but the reviewer downgraded it: its shortlist slot rested on a fundamental score built on 2025 memory-boom statements (price-only it ranks 19th of 31), and its 12.4% forward consensus rests on peak earnings (11.0% and 10.0% in the mid-cycle sensitivities). A downgrade ranks after every pass, so REA and Novo are the runners-up; John approved the picks with SK Hynix out [SCD; REV intl; PLAN]. AIA escapes rule 8.2 by 0.007 of IR; Tencent fails it.

**EM bond runners-up.** TGEIX (61.7, downgraded): fee 0.85%, OOS IR 0.17 (t 0.50). Its stated edge, "best in-sample IR of the active funds", came from a screen that measured it against the local-currency benchmark by mistake (0.81 versus EMLC, 0.27 versus EMB), and its Covid fall (-20.4%) was the worst of the eight [REV em_bonds]. EMLC (33.7, downgraded): OOS Sharpe -0.10; Section 9.5 gives its currency result. It fails rule 8.2 against EMB and is kept only as the FX-hedge test vehicle. PCY and EBND are dropped under rule 8.2. Swapping HYEM for TGEIX lowers OOS Sharpe by 0.014.

**Other-sleeve runners-up.** GNR (65% non-US) and IGF (64% non-US) trigger rule 8.2 (IR vs GLD -0.13 and -0.25) and are runners-up only because the shortlist had fewer than five survivors under the clarified rule; on the 33-name long list they could not be [SCD; REV other finding 1]. GSG was the only asset that behaved like an inflation hedge (+27.7% in the 2022 window) but fell 53.2% OOS and has a 1.3% forward estimate. SCHP, VNQI and WIP also fail rule 8.2. Six of eight candidates failed against gold, so the sleeve that survives is precious metals only. Swapping SLV for GNR lowers OOS Sharpe by 0.017.

---

## 8. Performance and attribution

### 8.1 In-sample and out-of-sample, eight portfolios

Portfolios: (a) the exact 55/35/10 guideline, equal weight inside sleeves; (a2) the guideline-feasible version; (b) the optimized portfolio within all rules (the chosen one); (c) (b) plus a protective put; (e) (b) without the 70% rule; and three benchmarks. Monthly USD returns net of trading costs, risk-free BIL, IR against GUIDE_BENCH. In-sample is 2013-01 to 2017-12 (60 months), out-of-sample 2018-01 to 2026-10 (106 months). IR is tracking-error-adjusted active return; max drawdown is the worst peak-to-trough loss.

| Portfolio | CAGR IS / OOS | Vol IS / OOS | Sharpe IS / OOS | IR vs GUIDE_BENCH IS / OOS | Max drawdown IS / OOS | Worst calendar year IS / OOS | Mean daily non-US share |
|---|---|---|---|---|---|---|---|
| (a) guideline 55/35/10 equal weight | 27.2% / 20.8% | 10.0% / 16.3% | 2.48 / 1.10 | 2.77 / 1.40 | -4.8% / -26.9% | 16.1% / -20.9% | 61.9% |
| (a2) guideline-feasible | 26.2% / 19.6% | 10.0% / 15.8% | 2.40 / 1.06 | 2.68 / 1.40 | -5.9% / -25.7% | 14.7% / -19.4% | 69.6% |
| (b) optimized (chosen) | 22.8% / 16.1% | 9.1% / 14.2% | 2.30 / 0.95 | 2.51 / 1.19 | -6.7% / -25.5% | 10.4% / -18.7% | 71.8% |
| (c) optimized + put (h=1) | 20.1% / 14.9% | 8.6% / 12.3% | 2.17 / 0.99 | 2.14 / 0.96 | -7.6% / -25.3% | 7.5% / -18.4% | 71.8% |
| (e) optimized, no 70% rule | 22.9% / 16.5% | 9.1% / 14.3% | 2.31 / 0.97 | 2.54 / 1.23 | -6.7% / -25.7% | 10.4% / -18.5% | 71.1% |
| GUIDE_BENCH 55/35/10 ACWX/EMB/GLD | 4.4% / 6.2% | 8.3% / 12.5% | 0.55 / 0.34 | n/a | -13.0% / -25.7% | -3.8% / -15.4% | 90.0% |
| SIXTY_FORTY SPY/AGG | 10.2% / 9.4% | 5.8% / 10.8% | 1.69 / 0.65 | 0.91 / 0.42 | -4.9% / -20.1% | 1.1% / -15.9% | 0.0% |
| GLOBAL_6040 ACWI/AGG | 7.4% / 7.5% | 6.1% / 10.5% | 1.18 / 0.51 | 0.71 / 0.21 | -7.5% / -21.3% | -1.0% / -16.1% | 21.6% |

Source: `reports/final/comparison.csv`, `python -m portfolio.build --write`. Two further rows from the same file:

| Portfolio | CAGR IS / OOS | Vol IS / OOS | Sharpe IS / OOS | IR IS / OOS | Max drawdown IS / OOS | Non-US |
|---|---|---|---|---|---|---|
| min-variance (rule on) | 21.2% / 15.4% | 8.9% / 13.8% | 2.22 / 0.93 | 2.53 / 1.14 | -6.5% / -24.6% | 72.3% |
| (c2) optimized + put (1 XSP contract) | 18.2% / 13.9% | 8.3% / 11.6% | 2.05 / 0.97 | 1.86 / 0.74 | -8.1% / -25.6% | 71.8% |

Evidence behind the figures. The t-statistic of the IR (t(IR)) is IR times the square root of years; alpha is the return unexplained by beta to GUIDE_BENCH; the deflated Sharpe here uses one trial.

| Portfolio | t(IR) IS / OOS | t(alpha) IS / OOS | Alpha IS / OOS | Beta IS / OOS | Deflated Sharpe IS / OOS (N=1) | Down-capture IS / OOS |
|---|---|---|---|---|---|---|
| (a) guideline 55/35/10 equal weight | 6.19 / 4.16 | 6.40 / 4.07 | 20.8% / 13.3% | 0.84 / 1.05 | 1.000 / 0.998 | -0.01 / 0.47 |
| (a2) guideline-feasible | 5.98 / 4.16 | 6.18 / 4.07 | 20.1% / 12.2% | 0.84 / 1.05 | 1.000 / 0.998 | 0.03 / 0.49 |
| (b) optimized (chosen) | 5.61 / 3.52 | 6.01 / 3.58 | 17.4% / 9.4% | 0.79 / 0.95 | 1.000 / 0.995 | 0.09 / 0.48 |
| (c) optimized + put (h=1) | 4.79 / 2.85 | 5.45 / 3.39 | 15.4% / 8.9% | 0.72 / 0.77 | 1.000 / 0.998 | 0.11 / 0.35 |
| (e) optimized, no 70% rule | 5.67 / 3.66 | 6.06 / 3.69 | 17.4% / 9.7% | 0.80 / 0.96 | 1.000 / 0.995 | 0.09 / 0.48 |
| SIXTY_FORTY SPY/AGG | 2.03 / 1.23 | 4.10 / 1.99 | 7.5% / 3.9% | 0.50 / 0.73 | 1.000 / 0.968 | 0.19 / 0.60 |
| GLOBAL_6040 ACWI/AGG | 1.59 / 0.62 | 3.57 / 1.46 | 4.2% / 2.0% | 0.67 / 0.78 | 0.993 / 0.927 | 0.48 / 0.71 |

Source: `reports/final/portfolio.json` `portfolios.<name>.metrics.in_sample`, `.out_of_sample`, `python -m portfolio.build --write`. **The deflated Sharpe in this table uses N = 1** (the default of `metrics_block` in `research/screen/stats.py`). It is the ordinary probability that the Sharpe is above zero. It is not a haircut for choosing 12 survivors from several hundred names, so it should not be read as strong evidence of skill.

What the tables say:

1. **The guideline was as good as or better than the optimized portfolio out of sample.** Equal weights inside 55/35/10 beat the optimizer on OOS Sharpe (1.10 versus 0.95), IR (1.40 versus 1.19) and return (CAGR 20.8% versus 16.1%), with higher volatility (16.3% versus 14.2%) and a slightly deeper drawdown (-26.9% versus -25.5%). The files contain no test of the difference between the two Sharpe ratios, so I do not call the gap significant; both are well above the benchmarks. The optimizer's shrunk 3-year means kept pushing weight into bonds and gold and away from the US stocks that drove 2018-2026 [PM]. Method.md section 12 lists "the guideline was as good as the optimized one" as a valid finding.
2. **Every pick-based portfolio beat every benchmark on OOS Sharpe** (0.93 to 1.10 against 0.34 to 0.65). That edge comes from the picks, which are 2026 survivors chosen partly on their OOS results. It is not evidence of skill (Section 5.4, Section 10).
3. **Security.** The 60/40 benchmark had a shallower OOS drawdown (-20.1%) and worst year (-15.9%) than any pick-based portfolio, but it is 0% non-US. Among the portfolios that hold the picks, maximum drawdowns run from -24.6% (minimum variance) to -26.9% (guideline).
4. **In-sample numbers are inflated.** In-sample Sharpe above 2 (2.30 for (b)) reflects NVDA and AVGO in 2013-2017 and the selection of survivors, and should not be extrapolated.

Calendar-year returns:

| Year | (b) optimized | (a) guideline | GUIDE_BENCH | SIXTY_FORTY |
|---|---|---|---|---|
| 2013 (IS) | 10.4% | 16.1% | 1.9% | 17.7% |
| 2014 (IS) | 21.5% | 23.6% | -0.9% | 10.4% |
| 2015 (IS) | 20.4% | 27.2% | -3.8% | 1.1% |
| 2016 (IS) | 29.1% | 32.3% | 6.8% | 8.1% |
| 2017 (IS) | 33.8% | 37.7% | 19.6% | 14.2% |
| 2018 (OOS) | 3.7% | 4.5% | -9.7% | -2.2% |
| 2019 (OOS) | 30.2% | 33.9% | 18.9% | 21.8% |
| 2020 (OOS) | 32.2% | 42.6% | 10.6% | 15.3% |
| 2021 (OOS) | 11.7% | 21.3% | 3.1% | 15.9% |
| 2022 (OOS) | -18.7% | -20.9% | -15.4% | -15.9% |
| 2023 (OOS) | 34.4% | 46.2% | 13.6% | 17.7% |
| 2024 (OOS) | 31.9% | 38.2% | 7.4% | 15.1% |
| 2025 (OOS) | 24.7% | 31.5% | 28.7% | 13.6% |
| 2026 (OOS) | 4.3%* | 3.8%* | 4.8%* | 7.3%* |

Source: `reports/final/portfolio.json` `portfolios.<name>.calendar_years`. 2026 is ten months (*). The one down year for the picks was 2022 (-18.7% for (b)), which is within the -20% limit.

Charts: `charts/growth.png`, `charts/drawdown.png` (relative to `reports/final/`).

### 8.2 Stress windows

| Portfolio | GFC 2008 | Taper 2013 | Covid 2020 | 2022 shock | Strong-USD months (avg per month) | USD 2014-15 | USD 2021-22 |
|---|---|---|---|---|---|---|---|
| (a) guideline 55/35/10 equal weight | n/a | -2.0% | -14.9% | -26.9% | -2.3% | 21.7% | -15.4% |
| (a2) guideline-feasible | n/a | -3.3% | -16.6% | -25.7% | -2.5% | 23.0% | -14.9% |
| (b) optimized (chosen) | n/a | -5.3% | -15.6% | -25.5% | -2.4% | 19.4% | -19.1% |
| (c) optimized + put (h=1) | n/a | -6.2% | -6.5% | -24.4% | -1.7% | 17.8% | -18.6% |
| (e) optimized, no 70% rule | n/a | -5.3% | -15.6% | -25.7% | -2.4% | 19.4% | -19.8% |
| GUIDE_BENCH 55/35/10 ACWX/EMB/GLD | n/a | -6.5% | -16.9% | -23.2% | -5.3% | -2.8% | -25.7% |
| SIXTY_FORTY SPY/AGG | -31.7% | 0.2% | -11.1% | -16.6% | -2.7% | 7.0% | -13.1% |
| GLOBAL_6040 ACWI/AGG | n/a | -2.1% | -11.3% | -18.7% | -3.5% | 2.9% | -17.7% |

Source: `reports/final/portfolio.json` `portfolios.<name>.stress`, `python -m portfolio.build --write`. Window definitions are in method.md section 11. The 2008 window is n/a for the picks (CEMB and HYEM did not exist, and the walk-forward starts in 2013). The optimized portfolio lost 25.5% in the 2022 inflation and rate shock (the same window as its maximum drawdown), more than GUIDE_BENCH (-23.2%) and much more than 60/40 (-16.6%). The strong-USD month average is not like-for-like: the portfolios use 19 months since 2013 and the benchmarks 29 months since 2008 [PJ `portfolios.<name>.stress.strong_usd.n_months`]. The two dated episodes (2014-05 to 2015-03 and 2021-05 to 2022-09) use the same dates for every row. Inflation resilience is therefore poor in the one inflation shock in the sample: gold lost 11% and the bond funds lost 19% to 25% in that window (Section 7).

### 8.3 Attribution: by sleeve, and local currency versus FX

Contribution is start-of-day weight times daily USD return, summed by month and sleeve, then annualised as a mean of monthly sums (the "residual" is compounding across days). It is an arithmetic mean, so the portfolio total (16.02% OOS) differs from the CAGR (16.09%).

| Window | US stocks | Intl stocks | EM bond funds | Gold + silver | Costs | Compounding residual | Portfolio mean (annualised) |
|---|---|---|---|---|---|---|---|
| IS 2013-2017 | 9.61% | 10.36% | 1.54% | -0.56% | -0.05% | 0.18% | 21.09% |
| OOS 2018-2026 | 6.49% | 6.35% | 1.28% | 1.49% | -0.03% | 0.44% | 16.02% |

Source: `reports/final/portfolio.json` `attribution.optimized.*.annualised_contribution`, `python -m portfolio.build --write`. Out of sample, 12.8 of the 16.0 points came from the six stocks (45% of the portfolio) and 1.3 from the four bond funds (45%). Gold and silver contributed 1.5 points out of sample and lost 0.6 in-sample.

Local currency versus FX for the three international stocks. The FX part of a local listing is weight times (USD return minus local return); US assets and the USD-denominated bond funds carry zero FX by convention.

| Window | Position | Currency | Local-currency contribution (annualised, weight-scaled) | FX contribution (annualised, weight-scaled) |
|---|---|---|---|---|
| IS | 2330.TW | TWD | 1.65% | 0.05% |
| IS | BAJFINANCE.NS | INR | 5.46% | -0.30% |
| IS | CSU.TO | CAD | 3.99% | -0.49% |
| IS | **Intl sleeve total** |  | **11.10%** | **-0.74%** |
| OOS | 2330.TW | TWD | 2.76% | -0.03% |
| OOS | BAJFINANCE.NS | INR | 2.08% | -0.38% |
| OOS | CSU.TO | CAD | 2.01% | -0.09% |
| OOS | **Intl sleeve total** |  | **6.85%** | **-0.50%** |
| Full | 2330.TW | TWD | 2.36% | 0.00% |
| Full | BAJFINANCE.NS | INR | 3.30% | -0.35% |
| Full | CSU.TO | CAD | 2.73% | -0.23% |
| Full | **Intl sleeve total** |  | **8.39%** | **-0.58%** |

Source: `reports/final/portfolio.json` `attribution.optimized.*.local_vs_fx`, `python -m portfolio.build --write`. Currency cost the portfolio 0.50 points a year out of sample (0.74 in-sample), small beside the 6.85 points the three international stocks earned in local terms. The portfolio's currency risk is modest mainly because 70% is USD-listed. Chart: `charts/attribution.png`.

### 8.4 Rebalancing frequency, lookback and the value of periodic adjustments

| Variant | Sharpe IS / OOS | IR IS / OOS | CAGR IS / OOS | Max DD OOS (= full) | Annual one-way turnover | Annual cost drag | Rebalances |
|---|---|---|---|---|---|---|---|
| optimized monthly 3y | 2.23 / 0.95 | 2.43 / 1.17 | 22.0% / 16.0% | -26.0% | 0.38 | 0.06% | 172 |
| optimized monthly 5y | 2.22 / 0.96 | 2.44 / 1.18 | 21.7% / 15.9% | -24.3% | 0.30 | 0.05% | 167 |
| optimized quarterly 3y | 2.30 / 0.95 | 2.51 / 1.19 | 22.8% / 16.1% | -25.5% | 0.23 | 0.04% | 67 |
| optimized quarterly 5y | 2.31 / 0.97 | 2.56 / 1.18 | 22.5% / 16.0% | -24.2% | 0.19 | 0.03% | 58 |
| optimized semiannual 3y | 2.33 / 0.95 | 2.54 / 1.17 | 23.5% / 16.0% | -25.5% | 0.18 | 0.03% | 38 |
| optimized semiannual 5y | 2.35 / 0.94 | 2.59 / 1.12 | 23.2% / 15.6% | -24.3% | 0.15 | 0.03% | 33 |
| optimized annual 3y | 2.39 / 0.96 | 2.58 / 1.15 | 24.6% / 16.1% | -25.8% | 0.16 | 0.03% | 28 |
| optimized annual 5y | 2.36 / 0.98 | 2.57 / 1.17 | 24.1% / 16.3% | -24.7% | 0.13 | 0.02% | 22 |
| buy-and-hold from the first optimized weights | 2.23 / 1.09 | 2.45 / 1.15 | 30.6% / 30.2% | -31.8% | 0.00 | 0.01% | 1 |
| min variance quarterly 3y | 2.22 / 0.93 | 2.53 / 1.14 | 21.2% / 15.4% | -24.6% | 0.19 | 0.03% | 58 |
| no 70% rule quarterly 3y | 2.31 / 0.97 | 2.54 / 1.23 | 22.9% / 16.5% | -25.7% | 0.23 | 0.04% | 56 |
| optimized quarterly 3y, 2010 start (assets as they list) | 2.05 / 0.95 | 2.33 / 1.19 | 22.7% / 16.1% | -25.5% | 0.23 | 0.04% | 79 |

Source: `reports/final/variants.csv`, `python -m portfolio.build --write`. OOS Sharpe ranges only 0.94 to 0.98 across monthly, quarterly, semi-annual and annual rebalancing and across 3- and 5-year estimation windows, so frequency and lookback hardly matter. Turnover and cost fall as the schedule lengthens (cost drag 0.06% to 0.02% a year). The 5-year windows give shallower drawdowns (-24.2% to -24.7%) than 3-year windows (-25.5% to -26.0%). The 2010-start variant has the same OOS numbers by construction and breaks the 15% fund cap for 12 rebalances.

**Did the periodic adjustments help?** The comparison is quarterly rebalancing (with the drift trigger) against buying the first walk-forward weights in 2013 and never trading:

| Window | CAGR quarterly / buy-and-hold | Sharpe quarterly / buy-and-hold | Vol | Max drawdown | Worst calendar year |
|---|---|---|---|---|---|
| IS | 22.8% / 30.6% | 2.30 / 2.23 | 9.1% / 12.4% | -6.7% / -6.4% | 10.4% / 12.1% |
| OOS | 16.1% / 30.2% | 0.95 / 1.09 | 14.2% / 25.1% | -25.5% / -31.8% | -18.7% / -28.2% |

| Window | CAGR difference (pts) | Max drawdown difference (pts, + = rebalanced shallower) | Sharpe difference |
|---|---|---|---|
| in_sample | -7.87 | -0.32 | +0.066 |
| out_of_sample | -14.06 | +6.29 | -0.135 |
| full | -11.87 | +6.29 | +0.002 |

Source: `reports/final/portfolio.json` `adjustments.buy_and_hold.metrics`, `portfolios.optimized.metrics`, `adjustments.rebalanced_minus_buy_hold`, `python -m portfolio.build --write`. Buy-and-hold earned far more (OOS CAGR 30.2% versus 16.1%) and had a higher OOS Sharpe (1.09 versus 0.95), because it let NVDA run. It also had OOS volatility of 25.1%, a maximum drawdown of -31.8% (past the -25% limit), a worst year of -28.2% (past the -20% limit), and a non-US share that first dropped below 70% at the 2016-11-30 month end and reached a daily low of 22.6% [PJ `adjustments.buy_and_hold.realised_non_us`]. **Adjustments did not raise the Sharpe ratio. They bought rule compliance and a shallower drawdown, and cost return.** The cost of trading itself was small: 23.0% annual one-way turnover and 0.039% a year in cost drag [PJ `portfolios.optimized.turnover`, `cost_drag`]. The drift trigger forced 11 extra rebalances, nine of them in 2022-2024 [PJ `adjustments.weight_changes`]. The buy-and-hold start is simply the first walk-forward weights, but its result depends heavily on one stock's run.

### 8.5 Monte Carlo against the five targets

Seven-year forward Monte Carlo: a circular block bootstrap (blocks of 6 months, 20,000 paths, seed 622) of the optimized portfolio's walk-forward monthly returns, scaled so the geometric mean equals the weighted forward consensus (8.03% a year). Inflation is 2.66% a year, the US CPI average for 2010-01 to 2026-09 [PJ `monte_carlo.settings`, `monte_carlo.inflation`].

| Target (method.md section 1) | Result | Pass |
|---|---|---|
| Median ending value of $100,000 at least $145,000 | $174,412 (5th-95th: $98,687 to $283,386) | pass |
| P(nominal loss over 7 years) at most 10% | 5.4% | pass |
| P(beat US CPI) at least 75% (CPI assumed 2.66%/yr) | 86.5% | pass |
| Max drawdown no worse than -25% (walk-forward backtest, monthly) | -25.47% (Dec 2021 to Oct 2022) | **FAIL by 0.47 points** |
| Worst calendar year no worse than -20% | -18.7% (2022) | pass |

Source: `reports/final/portfolio.json` `targets`, `python -m portfolio.build --write`. **Four of five targets pass. The drawdown target fails.** The walk-forward maximum drawdown is -25.47% (December 2021 to October 2022), 0.47 points past the -25% limit. Per method.md section 1 the security budget wins and the shortfall is reported, not hidden.

|  | Forward drift (8.03%/yr) | Historical drift (18.46%/yr) |
|---|---|---|
| Median ending value | $174,412 | $332,412 |
| 5th to 95th percentile | $98,687 to $283,386 | $188,087 to $540,106 |
| P(nominal loss) | 5.4% | 0.06% |
| P(beat CPI) | 86.5% | 99.7% |
| Median path max drawdown | -19.4% | -15.6% |
| P(path max drawdown worse than -25%) | 28.2% | 8.5% |
| Annualised return, 5th / 50th / 95th percentile | -0.2% / 8.3% / 16.0% | 9.4% / 18.7% / 27.2% |

Source: `reports/final/portfolio.json` `monte_carlo.forward`, `monte_carlo.historical`. Points to note:

- The historical-drift version (median $332,412) replays NVDA's run. It is not a forecast; it is in `portfolio.json` and is shown for completeness.
- In the forward simulation, 28.2% of 7-year paths have a drawdown worse than -25%. That is a broader view of the same security question than the single backtest drawdown.
- **The alternatives that would meet the -25% limit were identified after the OOS results were seen.** Two pre-registered variants clear it: the 5-year lookback (quarterly: -24.2%, OOS Sharpe 0.97) and minimum variance (-24.6%, OOS Sharpe 0.93) [VAR; PM]. The other 5-year schedules (monthly -24.3%, semi-annual -24.3%, annual -24.7%) also clear it, so the 5-year lookback is a family, not one lucky draw. Gold-neutral misses by 0.02 points, and the put overlay does not fix it (-25.3%). Choosing any of these now is a choice made after seeing OOS data, so it must be labelled as such and is John's decision. Chart: `charts/montecarlo_fan.png`.

---

## 9. Risks and the use of derivatives

### 9.1 What was tested

Six overlay series were modelled, each tested on the equity sleeve (or, for FX, on local-currency EM debt) with and without the overlay [OVL; SHORT "Derivative overlays"]:

- covered calls: 30-delta monthly (`cc_spx_30d_1m`) and at-the-money monthly (`cc_spx_atm_1m`);
- a protective put: 5% out of the money, 3-month, rolled quarterly (`pput_5pct_3m`);
- a collar: buy a 95% put, sell a 110% call (`collar_cll_95_110`);
- FX forwards on EM local-currency debt, 50% and 100% hedge ratio, 3-month (`fxfwd_emlocal_50pct_3m`, `_100pct_3m`).

Dropped before modelling [SHORT]: single-stock covered calls (a $5,000 to $10,000 position cannot write a 100-share contract), put-writing (adds exposure, breaks the overlay-only and 70% rules), index futures for rebalancing (one micro contract is about $37,000 notional, and the saving on a $5,000 trade is a few dollars), and interest-rate swaps (over the counter, out of reach).

**Calibration.** No option price history exists in the data. Premiums are Black-Scholes on SPY total-return prices with the VIX and VIX3M as implied volatility and a smile fitted on 2010-2017 only (ATM level -0.0307, call skew 0.2323, put skew 0.2930), then frozen [OVL `pput_5pct_3m.json` `overlay.calibration`]. The reviewer distorted all VIX, SPY and CBOE data after 2017, refitted, and got identical parameters, so there is no look-ahead in the option engine [REV overlays]. The model tracks the CBOE indices: in-sample R-squared of the overlay part 0.91 (BXMD), 0.92 (BXM), 0.77 (PPUT, 1-month model; OOS 0.88); OOS tracking error 2.0%, 2.4% and 2.3%; and the collar, never fitted, 2.6% against CLL [REV overlays; `research/candidates/memos/overlays_summary.md`]. The measured volatility risk premium (VIX minus subsequent realised volatility) was 4.0 points in 2010-2017 and 3.7 points in 2018-2026 [OVL].

**Known model biases.**

- The modelled covered-call return runs 0.93% a year above the CBOE BXM and BXMD indices out of sample. It flatters returns, not drawdown (model -22.5% gross against -21.6% for the index) [REV overlays finding 3].
- The quarterly 3-month put has no direct index to fit: against PPUT's 1-month put the tracking error is 4.94% and R-squared 0.47. Only the collar hold-out checks 3-month pricing [REV overlays finding 4].
- PPUT before its 2015 launch and CLL before 2008 are CBOE back-calculations.
- XSP liquidity (spreads wider than the assumed 1% of premium half-spread on far strikes) was not checked.

**Costs.** Each opening trade pays half the bid-ask spread, set at 1% of premium, plus $0.65 a contract; FX forwards pay 5 bp a roll [METH section 10; REV overlays "Costs"]. Annual OOS cost from these charges: 0.13% for the put, 0.16% and 0.36% for the covered calls, 0.17% for the collar, 0.10% and 0.20% for the FX hedges [OVL]. The premium itself is a separate and larger drag (below).

### 9.2 Standalone results on the S&P 500 sleeve and on EMLC

| Overlay | OOS Sharpe plain -> overlaid (1 contract / stated ratio) | OOS max DD plain -> overlaid | OOS annual cost | At exact 100%: Sharpe / max DD | Reviewer verdict | Passes 8.5 standalone |
|---|---|---|---|---|---|---|
| cc_spx_30d_1m | 0.75 -> 0.60 | -23.9% -> -23.8% | 0.16% | 0.67 / -22.6% | fail | no |
| cc_spx_atm_1m | 0.75 -> 0.31 | -23.9% -> -28.5% | 0.36% | 0.53 / -24.2% | fail | no |
| pput_5pct_3m | 0.75 -> 0.69 | -23.9% -> -16.6% | 0.13% | 0.77 / -17.6% | downgrade | yes |
| collar_cll_95_110 | 0.75 -> 0.51 | -23.9% -> -15.6% | 0.17% | 0.67 / -16.9% | fail | yes |
| fxfwd_emlocal_50pct_3m | -0.10 -> -0.22 | -25.5% -> -20.7% | 0.10% | n/a | downgrade | yes |
| fxfwd_emlocal_100pct_3m | -0.10 -> -0.47 | -25.5% -> -16.1% | 0.20% | n/a | downgrade | yes |

Source: `reports/candidates/<overlay>.json` `overlay.with`, `.without`, `.at_100pct`, `.annual_cost`, `.verdict_rule`; reviewer verdicts from `reports/candidates/reviews/overlays_review.json`; `python -m research.candidates.overlays --all --write`. Column 2 is at one XSP contract on a $55,000 equity sleeve (hedge ratio 1.39) for the option overlays and at the stated ratio on EMLC for FX; column 5 is the same overlay at exactly 100%. "Passes 8.5 standalone" is the analyst's test (OOS Sharpe higher, or OOS maximum drawdown at least 2 points smaller, after costs); rule 8.5 is properly a portfolio test, and the reviewer showed that several verdicts flip at portfolio level [REV overlays finding 1]. Only the put reached the portfolio-level test.

### 9.3 Feasibility at $100,000

One XSP (mini-SPX) contract is $76,237 (SPX 7,623.68 on 2026-10-23, contract page read 2026-11-07). That is 139% of a $55,000 equity sleeve and 169% of the portfolio's actual 45% sleeve ($45,000). Whole contracts give a hedge ratio of 0 or 1.39 (1.69 today); nothing in between [OVL `feasibility`; PJ `overlay_basis.h_one_xsp_contract_today` = 1.694]. Consequences:

- Long puts need no margin, so a put overlay is feasible, but only as an over-hedge.
- Short calls (covered calls, the collar) would be 39% uncovered at one contract and brokers margin XSP calls as uncovered even at 100%. The only compliant size is zero contracts. The overlay-only rule rules them out [REV overlays finding 2].
- FX forwards on nine EM currencies are bank over-the-counter contracts, normally not open to a retail account. CME futures cover only MXN, ZAR and BRL, in sizes of about $18,000 to $30,000 [OVL `fxfwd_*` `feasibility`].

### 9.4 The protective put at portfolio level, and why no overlay is recommended

The put was applied to the whole equity sleeve at a hedge ratio of 1.0 (series `overlay_return_h100`, net of costs), and at one XSP contract (hedge ratio 1.69), and tested against the portfolio with no overlay:

| Portfolio | OOS Sharpe | OOS vol | OOS CAGR | OOS IR vs GUIDE_BENCH (t) | OOS max drawdown | Covid 2020 window | 2022 window | Full-sample max drawdown |
|---|---|---|---|---|---|---|---|---|
| (b) optimized, no overlay | 0.95 | 14.2% | 16.1% | 1.19 (3.52) | -25.5% | -15.6% | -25.5% | -25.5% |
| (c) with put, h = 1.0 | 0.99 | 12.3% | 14.9% | 0.96 (2.85) | -25.3% | -6.5% | -24.4% | -25.3% |
| (c2) with put, 1 XSP contract (h = 1.69) | 0.97 | 11.6% | 13.9% | 0.74 (2.19) | -25.6% | 0.0% | -23.8% | -25.6% |

Source: `reports/final/portfolio.json` `portfolios.optimized`, `.optimized_overlay`, `.optimized_overlay_1contract`, `.metrics` and `.stress`, `python -m portfolio.build --write`. For (c): the overlay cut volatility, so OOS Sharpe rose by 0.04 (0.95 to 0.99), a margin the memo calls well inside estimation error. It cut the Covid loss from -15.6% to -6.5% (to about zero at one contract). It did not cut the maximum drawdown by 2 points (it moved 0.2 points, -25.5% to -25.3%), because the 2022 decline was slow and puts pay for crashes. It dragged returns by 1.32 points a year OOS [PJ `attribution.optimized_overlay.out_of_sample.annualised_contribution.overlay`], and IR against the guideline benchmark fell from 1.19 to 0.96. By the letter of rule 8.5 it survives on the Sharpe leg and fails the drawdown leg. The reviewer's indicative test on GUIDE_BENCH found the put fails both clauses (Sharpe 0.342 to 0.264, no drawdown change) [REV overlays].

**Basis risk.** The put is on the S&P 500 but protects a sleeve that is about half non-US. The international sleeve's OOS correlation with SPY is 0.68 (0.37 in-sample), and the whole equity sleeve's is 0.80, so the put pays when SPY falls, not when TSMC, Bajaj or Constellation fall; the memo estimates about half the international sleeve's variance is unhedged [PJ `overlay_basis`; PM].

**Verdict.** No overlay is recommended. The covered calls and the collar cannot be held compliantly at $100,000. The put adds a small Sharpe gain, "well inside estimation error" in the memo's words, at a cost of 1.3 points a year and does not fix the drawdown target. The FX hedges cannot be traded at retail and, when modelled, cut carry and Sharpe. If the client insists on protection, the put is "optional at most, and only as a stated over-hedge" [PM].

### 9.5 FX hedge on local-currency EM debt

The portfolio holds no local-currency bond fund, so no FX overlay is needed for the bond sleeve. The test was run on EMLC as the local benchmark [BND `EMLC.json` `currency`]:

- OOS: local-currency bonds returned +3.3% a year, the currency basket cost 2.3% a year, the USD return was +0.9%. The currency was 73% of USD variance on the analyst's equal-weight 10-currency basket (52% with GBI-EM weights).
- A model hedge (covered interest parity from OECD 3-month rates) would have cost 2.8% a year in carry and returned 0.4% a year, no better than unhedged on that basket. The result depends on the basket: with GBI-EM weights the hedged return is 2.2%, but that version leaves four currencies unhedged for lack of rate series [REV em_bonds].
- Overlay series: a 50% hedge cut OOS volatility from 10.6% to 7.3% and the maximum drawdown from -25.5% to -20.7%, but moved OOS Sharpe from -0.10 to -0.22 and gave up 1.4% a year of carry; a 100% hedge cut the drawdown to -16.1% but moved Sharpe to -0.47 and gave up 2.7% a year [OVL `fxfwd_*`].
- The basket weights use today's country weights on history (look-ahead), and the hedge removes carry as well as risk [REV overlays finding 5].

For the three foreign stocks the same model says a monthly hedge would have added 2.6 (TSMC), 2.2 (Bajaj) and 1.6 (Constellation) points a year in 2018-2026 (Section 7). The reviewer attributes this to the dollar's strength in that window, not to carry; the INR hedge cost 3.42% a year. These hedges were not tested for tradeability or at portfolio level, and they are not recommended.

### 9.6 Other risks the backtests do not capture

One OOS regime (a strong dollar, the 2022 rate shock, an AI rally) and no 2008 test for the portfolio [PM]. Concentration: three AI-linked semiconductor stocks are 19.5% of the portfolio and six single stocks are 45% (Section 6.1). Taiwan Strait risk for TSMC (10%) is in no backtest [REV intl]. CEMB ($0.4bn) and HYEM ($0.5bn) are small ETFs, and Bajaj Finance needs an international account [MEM; PM]. The 12 picks are 2026 survivors chosen partly on OOS results (Section 10). Gold and silver trusts are taxed as collectibles at up to 28% [MEM IAU, SLV]; no other tax analysis was done.

---

## 10. Conclusion

**The honest answer.** The optimizer did not beat a simple rule. Out of sample, equal weights inside 55/35/10 earned a higher Sharpe ratio (1.10) than the rule-compliant optimized portfolio (0.95), but the exact guideline fails the client's 70% non-US requirement (62.5%), and the version that meets it needs 11.67% in each international stock, above the team's own 10% cap. The portfolio we hold, (b), meets every rule at every rebalance and costs about 0.4 points a year against an unconstrained optimizer. Its weights are mostly set by the rules (ten bounds bind at once), not by the return estimates.

**The picks' out-of-sample record overstates what a 2017 investor could have had.** The twelve picks are 2026 survivors, and the rubric that chose them put 60 of its 100 points on 2018-2026 results. The 2017 screen had no predictive power in any sleeve (rho between -0.02 and +0.20, all p above 0.3). Among the twelve picks only NVDA, AVGO and TSMC have an OOS information ratio with a t-statistic above 2. A 2017 investor following the same method would have had Biogen (in-sample rank 10 of 46) on the shortlist's list of passers and would not have had ASML (rank 24 of 31) or Petrobras (rank 30). The backtest (OOS Sharpe 0.95, CAGR 16.1%) is therefore an upper bound, and the forward estimate of 8.0% a year is the number to plan with.

**What the team can defend.**

1. The process: a method fixed before results, a pre-registered technical-signal test, adversarial reviews that reproduced every number, and a full change log. 119 tests passed on 2026-11-07.
2. The negative results, stated plainly: no technical signal added value; the screen did not predict winners; gold was not an inflation hedge; the EM bond funds cannot be told apart; no overlay is worth adding; the guideline was as good as the optimizer.
3. The portfolio's rule compliance (70% non-US at every rebalance; sleeve bands; position bounds) and its modest cost.
4. Four of the five forward targets: median ending value $174,412, a 5.4% chance of a nominal loss, an 86.5% chance of beating inflation, and a worst calendar year of -18.7%.
5. The conclusion that currency risk is small at the portfolio level (-0.50 points a year OOS) and that the put overlay is optional at best.

**What the team cannot defend.**

1. The drawdown target. The backtest maximum drawdown is -25.47%, 0.47 points past the limit, in the 2022 shock, when the portfolio fell more than the benchmark (-25.5% against -23.2%) and far more than 60/40 (-16.6%). In the forward simulation 28.2% of paths draw down more than 25%. The two alternatives that clear the limit were found after seeing OOS data.
2. Any claim that the picks reflect skill. Only TSMC (against 31 trials) and NVDA (when choosing among eight) clear a Bonferroni bar, and NVDA's deflated Sharpe is 0.84, below the usual 0.95. The EM bond funds, gold and silver have deflated Sharpe ratios of 0.03 to 0.46.
3. Inflation resilience. The portfolio lost 25.5% nominal in the one inflation shock, gold lost 11%, and the 86.5% chance of beating CPI is a forecast built on an 8.0% drift.
4. Precision in the weights. HYEM at 1% and SLV at 1% are token positions, and the EMB/HYEM flip between the walk-forward and the order list shows the bond weights are noise.
5. The international fundamentals. All eight shortlisted international names were screened on current, not point-in-time, statements, and the in-sample table that chose them was later regenerated after a bug fix, moving Constellation from 8th to 10th and HDFC Bank from 11th to 7th; the shortlist was kept as frozen (Section 4.6).
6. The mostly-passive label for the stock sleeve, and the technical half of "technical plus fundamental".

**What we recommend.** Hold the order list in Section 6.2 ($97,285 invested, $2,715 in cash), rebalance quarterly with the 68% drift trigger, and report the drawdown shortfall. Treat any switch to a 5-year lookback or minimum variance to meet the -25% limit as a post-hoc choice, label it as one, and leave the decision to John. Do not add the put.

---

## 11. References and reproducibility

### 11.1 Data sources and dates

| Source | What | Date or coverage | Reference |
|---|---|---|---|
| Yahoo Finance via `yfinance` 1.7.0 | daily adjusted-close prices (total return), FX, fundamentals, fund facts, volumes | fetch run 2026-11-07 (1,431 s); 410 of 412 price tickers, 30 of 30 currencies, 209 of 209 fundamentals folders, 176 of 176 fund-facts rows; history to 2026-11-06, with NVDA, 2330.TW, SPY, ACWI and META ending 2026-10-23 | [DR section 8; PJ `notes`] |
| SEC EDGAR `companyfacts` | point-in-time US and 20-F filer fundamentals | 152 of 155 files; 404 for CSL.AX, IFX.DE, ICICIBANK.NS; tidy extract `data/research/edgar_facts.csv.gz` | [DR section 8; PLAN] |
| OECD SDMX API | non-US 10-year and 3-month rates, CPI | 47 areas (10Y), 46 (3M), 53 (CPI), to 2026-09 or 2026-10 | [DR section 4 and 8] |
| FRED | US rates, CPI, TIPS, breakevens, broad dollar index, EM credit spreads | answered again after a rate limit; EM credit spreads only from 2023-11 | [DR section 4 and 8] |
| World Bank API | annual country CPI | 25 of 25 | [DR section 8] |
| CBOE index CSVs | BXM, BXMD, PUT, PPUT, CLL | 5 of 5 | [DR sections 5 and 8] |
| iShares EMB page | country weights and credit quality for EMB | 2026-11-05 | [MEM EMB; `research/candidates/memos/em_bonds_countries.md`] |
| Fund factsheets | GNR non-US share (SSGA, 2026-09-30), IGF (iShares, 2026-11-05) | as stated | [REV other finding 9] |
| Damodaran country risk premia | equity risk premium and country premia | January 2026 update | [`research/candidates/assumptions_intl_growth.py`] |
| Country credit ratings | S&P and Moody's per country | retrieved 2026-11-07 (Wikipedia, countryeconomy.com) | [`research/candidates/memos/em_bonds_countries.md`] |
| CBOE XSP contract page | contract size | read 2026-11-07 | [OVL `feasibility.source`] |

### 11.2 Methods literature cited in the code

The literature is cited in the assumptions files and module docstrings. Two citations are marked in the code as taken from memory or secondary sources.

- Bailey, D. and Lopez de Prado, M. (2014), the deflated Sharpe ratio (`research/screen/scoring.py`).
- Ledoit, O. and Wolf, M. (2004), shrinkage covariance (`portfolio/optimize.py`).
- Grinold, R. and Kroner, K. (2002), The Equity Risk Premium, Investment Insights 5(3), Barclays Global Investors (`research/candidates/assumptions_other.py`; citation confirmed by secondary source, PDF not retrieved).
- Erb, C. and Harvey, C. (2013), The Golden Dilemma, NBER WP 18706 / Financial Analysts Journal 69(4) (`assumptions_other.py`; the figures seen only in secondary sources are not relied on).
- Gorton, G. and Rouwenhorst, K. (2006), Facts and Fantasies about Commodity Futures, Financial Analysts Journal 62(2) (`assumptions_other.py`; "cited from memory, not re-fetched").
- Damodaran, A., Country Default Spreads and Risk Premiums, January 2026 update (`assumptions_intl_growth.py`).
- Black-Scholes option pricing and Blume-adjusted betas (0.67 beta + 0.33) are named in `research/candidates/overlays.py` and `research/capm.py`; the code gives no full citation.
- S&P default and recovery tables came from secondary summaries and a forum repost (`assumptions_em_bonds.py`); the reviewer rates that input weakly sourced.

### 11.3 Commands, section by section

Run from the repository root. Python 3.14, pandas 3.0.5 on Windows.

| Section | Command | Time or note |
|---|---|---|
| 3, 6, 8, 9.4 (portfolio) | `python -m portfolio.build --write` | about 3 minutes; writes `reports/final/portfolio.json`, `comparison.csv`, `variants.csv`, `order_list.csv`, `order_list_guideline_feasible.csv`, `weights_history_optimized.csv`, charts |
| 4, 5 (data) | `python -m research.fetch --universe research/plan/universe.csv` | about 24 minutes, needs network |
| 5 (screens) | `python -m research.screen hard --type <type> --as-of 2017-12-31`; `... score ...`; `... validate --type <type>` for `us_growth_stock`, `intl_growth_stock`, `em_bond`, `other` | writes `research/plan/longlists/*` |
| 5 (in-sample table) | `python research/plan/shortlist_table.py` | writes `<type>_insample_table.csv` |
| 5, 7 (candidates and control tables) | `python -m research.candidates.us_growth --all --write` (and `--control --write`); `python -m research.candidates.intl_growth --all --write`; `python -m research.candidates.em_bonds --all --write`; `python -m research.candidates.other_sleeve --all --write` | JSON, memos, charts, control tables |
| 7 (scorecard) | `python research/plan/scorecard.py --write` | rubric and picks; writes `reports/candidates/scorecard.csv` |
| 7 (reviews) | `python -m research.reviews.us_growth_check`; `intl_growth_check`; `em_bonds_check`; `other_check`; `overlays_check` (add `--reproduce` for US) | reviewers' independent recomputation |
| 9 (overlays) | `python -m research.candidates.overlays --all --write` | JSON and monthly series in `reports/candidates/overlays/` |
| Dashboard | `python -m dashboard` (build and serve on http://localhost:8000); `python -m dashboard --no-serve` | reads the JSON in `reports/`; offline |

### 11.4 Test suite

`pytest` collects 121 tests (`pytest --collect-only -q`). For this draft, `pytest -q -x -p no:cacheprovider` was run on 2026-11-07: **119 passed, 2 skipped in 82.7 s**. The test files are `tests/test_build.py`, `test_candidates_em_bonds.py`, `test_candidates_intl_growth.py`, `test_candidates_other.py`, `test_candidates_overlays.py`, `test_candidates_us_growth.py`, `test_dashboard.py`, `test_fetch.py`, `test_pipeline.py`, `test_research.py` and `test_screen.py`. Synthetic data appear only in tests; nothing in this report comes from synthetic data [PJ `notes`]. The two skips were not inspected.

---

## Appendix A. Glossary of metrics in plain English

| Term | Plain English |
|---|---|
| CAGR | The steady yearly growth rate that turns the starting value into the ending value. |
| Volatility | How much monthly returns bounce around, scaled to a year. Higher means a rougher ride. |
| Sharpe ratio | Return above the risk-free rate (here BIL, a T-bill fund) per unit of volatility. Higher is better. Below 0.5 is weak; above 1 is strong. |
| Sortino ratio | Like Sharpe, but only downside swings count as risk. |
| Information ratio (IR) | Return above a benchmark per unit of how far the portfolio strays from it (tracking error). Positive means it beat the benchmark steadily. |
| t-statistic (t) | How many "standard errors" an estimate sits from zero. Below 2 is weak evidence; above 3 is strong. |
| p-value | The chance of seeing a result at least this strong if nothing real were going on. Above 0.05 is "not significant". |
| Alpha and beta | Beta is how much the portfolio moves with the benchmark. Alpha is the return left over after that. |
| Maximum drawdown | The worst peak-to-trough loss on monthly data. -25% means the portfolio once fell a quarter from a high. |
| Calmar ratio | CAGR divided by the size of the maximum drawdown. |
| Up and down capture | Share of the benchmark's gains (losses) the portfolio captured. Low down-capture is good. |
| Deflated Sharpe ratio | The probability that the Sharpe ratio is real after allowing for the number of names tried. Close to 1 is convincing; below 0.5 is not. In the portfolio table it uses one trial, so it is only the ordinary probability that the Sharpe is above zero. |
| Spearman rho | How closely two rankings agree. +1 identical, 0 unrelated, -1 reversed. |
| In-sample / out-of-sample | Data used to choose (2010-2017 for candidates) versus data held back to test (2018-2026). |
| Walk-forward | At each rebalance, estimate using only past data, trade, and move on. |
| Monte Carlo (block bootstrap) | Many simulated 7-year paths made by reshuffling blocks of past monthly returns, with the average return reset to the forward forecast. |
| Rule 8.2 | Pre-registered: drop a candidate whose OOS Sharpe is below its type benchmark and whose OOS IR is negative. |
| Rule 8.5 | Pre-registered: drop an overlay that neither raises the portfolio's OOS Sharpe nor cuts its maximum drawdown by 2 points after costs. |
| CAPM, DCF, Grinold-Kroner | Three ways to estimate a stock's expected return: from its market risk, from discounting forecast cash flows, and from yield plus growth plus change in valuation. |
| Covered interest parity (CIP) | The no-arbitrage link that prices an FX forward from two countries' interest rates. |
| Basis risk | The hedge does not match the thing hedged (an S&P put on a half non-US portfolio). |
| Corner solution | An optimizer answer that sits on a limit (a cap or a floor) rather than inside it. |

---

## Appendix B. The method change log

From `research/plan/method.md` section 13 [METH]. No entry changes a pre-registered threshold or weight.

| Date | Section | Change | Reason | Rerun done |
|---|---|---|---|---|
| 2026-11-07 | 6 | Clarification: T4 = standard deviation of the last 252 daily USD returns; T5 = price / 252-day high minus 1; top tercile = top round(n/3) names; T2 holds every name above its 200-day average; 10 bp cost on the tercile portfolio's turnover only; a name counts in month t only if it has a return that month; "long list" for validation = all candidates plus faded leaders | implementation choices made in `research/screen/` before any scoring ran | n/a |
| 2026-11-07 | 5 | Clarification: fiscal year = year of period end; point-in-time value = latest filing on or before as_of; ROIC definition with a 25% default tax rate; market cap at 2017-12-31 rebuilt from SEC share counts and unadjusted prices; US stocks without point-in-time revenue are "not checked", never substituted; TSMC's first SEC XBRL filing is 2018 so it is scored on current statements and flagged | same | n/a |
| 2026-11-07 | 7 | Clarification: a rubric component missing for one name has its weight redistributed pro rata for that name; deflated Sharpe uses V = 1/(T-1) unless measured | same | n/a |
| 2026-11-07 | 4 | Clarification: WTMF (managed futures, inception 2011) is a candidate for the other sleeve; the exclusion was for histories shorter than the rule | screener found it passes every hard screen | n/a |
| 2026-11-07 | 4 | Clarification: faded leaders are exempt from the market-cap rule | the point of the group is that they shrank | n/a |
| 2026-11-07 | 5 | Bug fix: the screening CLI tagged a company a financial when "financ" appeared in its notes, which matched "yfinance" (Broadcom, Sirius, Keurig Dr Pepper, Gen Digital); whole-word match now; Broadcom's in-sample rank moves from 1 to 2; shortlist unchanged | US growth reviewer finding 5 | yes (score and in-sample tables) |
| 2026-11-07 | 3 (Phase 3 Monte Carlo) | Bug fix: `research/montecarlo.py` drew the first and last months about one-sixth as often as the others; now a circular block bootstrap; medians move by up to about 2 points; consensus never included the Monte Carlo | US growth reviewer finding 3 | yes (all candidate scripts rerun) |
| 2026-11-07 | 8 | Clarification: in rule 2, "fewer than 5 survivors" counts the deep-researched shortlist of that type; a reviewer "fail" can never be a runner-up | the other-sleeve reviewer asked which set is meant; decided before the scorecard was written | n/a |

---

## Appendix C. Data caveats

Carried from the plan, the shortlist, the portfolio notes and the reviews.

1. **Point-in-time fundamentals are missing for international names.** 22 of 31 international passers, including all eight shortlisted, were screened on current statements; the fundamental score is half the composite. Faded leaders were point-in-time [SCD; REV intl].
2. **Home indices for local-currency comparisons are price indices** (no dividends), which flatters local IRs: the OOS gap of a total-return ETF over the index is -0.15 to +3.60 points a year in USD for four markets [REV intl, "Low"].
3. **One OOS regime** of 8.8 years, and **picks partly chosen on OOS results** from 2026 survivors; the bond long list holds only funds alive in 2026 (404 tickers dropped) [PM; REV em_bonds].
4. **Model and judgement inputs.** Option prices are modelled, not traded history; the model covered-call return is 0.93% a year too kind [REV overlays]. EM bond credit losses, ratings mix and some durations are judgement or borrowed from peers; the forward consensus is in practice one method [REV em_bonds]. The IAU forward consensus averages two models 9.4 points apart [REV other].
5. **Dates and alignment.** Prices end 2026-10-23 for NVDA, 2330.TW, SPY, ACWI and META, and the last week of October 2026 is carried flat. Taiwan, India and Canada closes are aligned to US trading days with a forward-fill of at most 5 days [PJ `notes`].
6. **Prices and fees.** Prices are Yahoo adjusted closes (dividends reinvested); fund NAV histories are net of fees. Fund assets and expense ratios are today's figures, used in the screens as if known in 2017 [SHORT].
7. **Missing or approximate inputs.** No Taiwan short-rate series (flat 1.8% for the TWD hedge); INR flat 5.61% before 2011-12; Brazil's 10-year series is a policy rate and is excluded; Turkish yields are spot quotes only; Mexico's series had 63 missing months (fixed); debt/GDP and current account were not checked [MEM; REV em_bonds].
8. **Source gaps.** CSL.AX, IFX.DE and ICICIBANK.NS returned 404 from EDGAR; NOVO-B.CO has doubled prices on a few 2005-2006 holiday days (before the 2010 start); EM credit spreads from FRED start in 2023-11 [SHORT; DR].
9. **Portfolio periods and floors.** The portfolio in-sample window is 2013-01 to 2017-12, not 2010-2017 (a 2010-start variant breaks the 15% fund cap), and the 1% floor for funds and other assets is the builder's reading of "every pick held" [PJ `notes`; VAR].

---

## Appendix D. Where files disagreed, and what this report uses

1. **Overlay table in `scorecard.md`.** Its header originally said "exact 100% ratio", but the cc30, collar and FX rows are the 1-contract series and only the put row (Sharpe 0.75 to 0.77, drawdown -23.9% to -17.6%) is at 100%; the header was corrected on 2026-11-07 during the report review. `overlays_summary.md` gives the put at 1 contract: 0.75 to 0.69, -23.9% to -16.6%. This report shows both from the overlay JSONs (Section 9.2).
2. **Other-sleeve exclusions.** `shortlist.md` originally said 42 rows were excluded before screening; `other_hard.csv` has 41 excluded, 34 too young and 33 candidates (108). `shortlist.md` was corrected to 41 during the report review. This report uses the CSV.
3. **International shortlist ranks.** `shortlist.md` said the eight were "the top eight by composite" and listed HDFCBANK.NS as rank 11, which was true of the table when the shortlist was frozen. The table was regenerated later the same day after the financial-tag bug fix and now ranks HDFCBANK.NS 7th and CSU.TO 10th. No swap was made; the shortlist was kept as frozen and `shortlist.md` now explains the timing. The intl reviewer's "deep-research set equals the in-sample top 8" referred to the earlier table (Section 4.6).
4. **Buy-and-hold non-US drift.** The Phase 5 memo originally said the buy-and-hold portfolio "would have broken the 70% rule within two years". `portfolio.json` `adjustments.buy_and_hold.realised_non_us` shows the first month-end below 70% on 2016-11-30 (about four years in), a daily minimum of 22.6%. The memo was corrected to the JSON date during the report review; this report uses the JSON.
5. **Analyst ranks versus scorecard decisions.** Several analyst memos and JSON `explain` fields predate the rubric: the AMZN memo says "runner-up, ranked fourth" and its explain text says "runner-up", while the scorecard makes it a pick (third, 59.0 points). Likewise the analyst ranks of PYEMX, EMB and HYEM (2, 5 and 1 of 8) differ from their scorecard ranks (1, 3 and 4). This report follows the scorecard and the approved picks.
6. **TSMC ADR gap.** The memo gives the TSM ADR as returning about 1.5% a year more than the local line OOS (mean monthly difference -1.51%); the reviewer gives a CAGR gap of -0.93% a year. This report says "0.9 to 1.5 points a year".
7. **EM bond funds beating the picks.** `PLAN.md` says "no EM bond fund has an OOS Sharpe above 0.13"; that holds for the eight, but the control group has EEIIX 0.192, PEBIX 0.138 and EMHY 0.134 [REV em_bonds].
8. **Volatility of the chosen portfolio.** 9.9% in `portfolio.json` `ex_ante` (Ledoit-Wolf, daily, window 2023-10-26 to 2026-10-30, risk-free 3.94%) and 11.0% in `frontiers` (monthly covariance shrunk 30% to the diagonal, average BIL risk-free 1.59%). Both are reported with their sources.
9. **`PLAN.md` key results.** It says only NVDA, AVGO and TSMC beat their benchmarks with t above 2. That holds for the picks; SK Hynix (t 2.25) and ASML (t 2.84) also did, but were not picks [SCC; CTL].
10. **Minor.** International T3 OOS t-statistic: 0.4 in `shortlist.md`, 0.35 in `intl_growth_stock_signals.csv`. The Phase 5 memo calls the put's cost "1.3% a year"; that is the attribution line (premium paid net of payoffs, -1.32 points a year), separate from the 0.13% transaction cost in Section 9.1. `scorecard.md` says faded leaders fell "from ranks 10-18 to 43-46"; that is true for three of the six (Section 5.3 gives all six).
