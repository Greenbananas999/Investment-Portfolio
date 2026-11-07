# PLAN: find and prove the best assets for the 622 portfolio

Single source of truth for the project. Updated as work completes.

**Status (2026-11-07):** Phase 0 and Phase 1 written. Waiting on check-in 1
with John before Phase 2 starts. No candidate has been backtested.

Companion files in this folder:

| File | What it holds |
|---|---|
| `method.md` | the pre-registered method: objective in numbers, sample split, non-US rule, universes, screens, rubric, benchmarks, drop rules, stress windows. Committed before any backtest. |
| `results_schema.md` | JSON schema for `reports/candidates/<ID>.json` that every analyst writes and the dashboard reads |
| `data_request.md` | every ticker, FX pair, yield series and fundamentals source the plan needs, and the one command that fetches them |
| `shortlist.md` | (Phase 2) the long lists, hard-screen results, and the reasoning for each shortlisted name and each near miss |
| `scorecard.md` | (Phase 4) rubric scores, reviewer verdicts, picks and runners-up |

## Settings

```yaml
base_currency: USD
capital_usd: 100000
horizon_years: 7
min_non_us_weight: 0.70          # of total portfolio value
target_mix: { equity: 0.55, bonds: 0.35, other: 0.10 }
mix_tolerance: 0.10
positions: { us_growth_stocks: 3, intl_growth_stocks: 3, em_bonds: 4, other: "1-3" }
shortlist_per_position_type: 8
rebalance: quarterly             # also test semi-annual and annual
derivatives: overlay_only        # test with and without
backtest_start: 2010-01-01
out_of_sample_start: 2018-01-01
risk_free: BIL
models: { planner: fable, builders: sonnet, hard_modeling_and_review: opus }
```

## Phase 0 findings (what the repo gives us, and what changed in the plan)

**Reusable code.** `portfolio/` is a working walk-forward optimizer on daily
US-listed ETF prices: Ledoit-Wolf covariance, shrunk means, SLSQP max-Sharpe
and min-variance with a non-US floor and a per-asset cap, 21-day rebalance on
a 756-day lookback, 5 bps costs, FX attribution. `research/` has single-asset
expected-return models on monthly data: historical stats, CAPM with Blume
betas, forward-earnings DCF with Monte Carlo, Grinold-Kroner, constant-maturity
bond total returns from yields, block-bootstrap Monte Carlo, a forecast test
and an ex-ante frontier. 13 tests pass (`pytest`, 35 s). Both pipelines are
built around hard-coded universes (`portfolio/config.UNIVERSE`,
`research/config.STOCKS`); the candidate work needs a universe file instead.

**Gaps to fill.** No asset-class mix constraint, no position-count rule, no
sleeve structure, no benchmark-relative metrics on daily data (IR, tracking
error, alpha t-stats, up/down capture), no rolling windows, no deflated Sharpe,
no option or FX-forward modelling, no point-in-time fundamentals (Yahoo gives
4 fiscal years), no dashboard beyond a single-page HTML report.

**Environment.** This session runs on John's Windows PC, not in the cloud
sandbox. Yahoo Finance and FRED are reachable from here (tested 2026-11-07),
so the plan fetches data directly with one batched script instead of handing
John a request to run. `data_request.md` still lists everything so the fetch is
reviewable and reproducible. Python 3.14 and pandas 3.0.5: subagents must use
`ME`/`MS`/`YE` frequency codes, `pct_change(fill_method=None)`, and not rely
on chained assignment.

**Data coverage confirmed on Yahoo (full history to 2026-11-06):** every EM
bond ETF and open-end fund in the universe (EMB, PCY, EMLC, LEMB, EBND, ELD,
CEMB, EMHY, HYEM, EMCB from 2007-2012; PEBIX, PREMX, FNMIX, TGEIX, PELBX from
before 2010; VWOB 2013 and DBLEX 2010), every "other" sleeve ETF (GLD, IAU,
SLV, DBC, GSG, VNQI, RWX, WIP, TIP, SCHP, IGF, GUNR; PDBC 2014 fails the
history rule), the benchmarks (IVW, QQQ, EFG, EEM, ACWX, AGG, BIL, SPY, ACWI),
and foreign local listings (ASML.AS, NOVO-B.CO, MC.PA, SAP.DE, 6861.T, 8035.T,
0700.HK, RELIANCE.NS, HDFCBANK.NS, CSU.TO, CSL.AX, 2454.TW, ATCO-A.ST, DSY.PA,
MELI, NTES). CBOE PUT index (^PUT) has daily history on Yahoo; ^BXM, ^BXMD and
^PPUT do not (one row), so those come from CBOE's own CSVs (see
`data_request.md`). Shopify (2015), Ferrari (2016), Alibaba (2014), 9988.HK
(2019), SGOV (2020) fail the 60-months-before-2018 rule.

**Earlier examples are not required.** The seven stocks and two bonds already
modelled (SK Hynix, Samsung, TSMC, Apple, Nvidia, Meta, Microsoft, French OAT,
Turkish government) enter the long lists like any other name. The old 25% cap
and four-fund framing are replaced by `method.md`.

## Phases, tasks and owners

Owner key: **F** = planner (Fable, this session); **S** = Sonnet subagent;
**O** = Opus subagent. One subagent per row unless stated.

### Phase 0: orient (done)

| # | Task | Owner | Output |
|---|---|---|---|
| 0.1 | Read repo, test data access, run tests | F | this file |
| 0.2 | Results JSON schema | F | `results_schema.md` |

### Phase 1: method before results (done, awaiting check-in 1)

| # | Task | Owner | Output |
|---|---|---|---|
| 1.1 | Pre-registered method | F | `method.md` |
| 1.2 | Data request draft | F | `data_request.md` |
| 1.3 | **Check-in 1 with John** (method, benchmarks, gold rule, mutual funds allowed, four-fund analysis) | F | John's answers logged below |

### Phase 2: wide screen, then shortlist

| # | Task | Owner | Output |
|---|---|---|---|
| 2.1 | Long lists (names, tickers, country, currency, listing date, sources; no prices yet) for US growth, intl growth, EM bonds, other, overlays. Five briefs in parallel. | S x5 | `research/plan/longlists/<type>.csv` |
| 2.2 | Merge long lists into `research/plan/universe.csv`; extend `research/fetch.py` to read it (prices in local currency and USD listing, FX for every currency, FRED yields and CPI, CBOE indices, yfinance fundamentals, EDGAR companyfacts for SEC filers); one run; commit data. Only this agent edits `fetch.py`. | S | `data/research/*`, `data_request.md` finalised, `fetch_log.txt` |
| 2.3 | Shared screening library: hard screens, fundamental and technical scores, signal validation (method.md sections 5-6), deflated Sharpe, point-in-time EDGAR reader. One module, tests. | O | `research/screen.py`, `tests/test_screen.py` |
| 2.4 | Apply screens per type on in-sample data only; ranked tables with scores and source links. Same five agents as 2.1, continued. | S x5 | `research/plan/longlists/<type>_scored.csv`, signal validation tables |
| 2.5 | Pick 8 per type (6-8 for other, 4-5 overlays); reasoning for each pick and near miss; note which make the 70% floor easy or hard | F | `shortlist.md` |
| 2.6 | Commit Phase 2. **Usage pause:** post shortlist, data summary and the Phase 3-7 plan with subagent counts and models; wait for "continue". | F | message to John |

### Phase 3: deep research per type (parallel, one agent per type)

| # | Agent | Model | Candidates | Why this model |
|---|---|---|---|---|
| 3.1 | US growth stock analyst | O | 8 | DCF, Grinold-Kroner, CAPM judgement, covered-call interaction |
| 3.2 | International growth stock analyst | O | 8 | same, plus local vs USD and hedging analysis |
| 3.3 | EM bond analyst | O | 8 | yield scenarios, country credit, local vs hard currency, FX forward hedging |
| 3.4 | Other-sleeve analyst | S | 6-8 | standard backtest and inflation-beta metrics |
| 3.5 | Overlay analyst | O | 4-5 overlays | Black-Scholes with volatility risk premium, CIP forwards, cost modelling |

Each writes `research/candidates/<type>.py` (one shared script per type),
tests, memos in `research/candidates/memos/`, JSON per candidate in
`reports/candidates/` per `results_schema.md`, charts in
`reports/candidates/charts/`. Planner verifies: run the command, spot-check two
numbers, read the tests.

### Phase 4: adversarial review, then picks

| # | Task | Owner |
|---|---|---|
| 4.1 | One reviewer per type that did not build it: rerun from committed code, hunt look-ahead, survivorship, cherry-picked windows, wrong benchmark, missing fees/dividends, currency errors, overfitting; pass/fail per claim | O x5 |
| 4.2 | Apply the rubric, drop or downgrade per reviewer verdicts, pick 3/3/4/1-3 and 1-2 runners-up each; write why each runner-up lost | F |
| 4.3 | **Check-in 3 with John**: picks and runners-up before the portfolio build | F |

### Phase 5: portfolio build and proof

| # | Task | Owner |
|---|---|---|
| 5.1 | Extend `portfolio/optimize.py` and `research/frontier.py` (not rewrite): 70% floor, sleeve mix within tolerance, position counts and per-position bounds, long-only; universe from a candidates file instead of `config.UNIVERSE`. Only this agent edits those modules. | O |
| 5.2 | Compare (a) guideline 55/35/10 equal-weight, (b) optimized within rules, (c) optimized with overlays, (d) GUIDE_BENCH and 60/40, (e) optimized without the 70% rule; walk-forward at quarterly, semi-annual, annual; costs; list of adjustments made and whether they helped | O (same) |
| 5.3 | 7-year forward Monte Carlo (block bootstrap plus forward drift): median, 5th/95th ending value, P(loss), P(beat inflation); ex-post and ex-ante frontiers with and without the rule; Sharpe, IR, attribution by sleeve and by local vs FX; order list (ticker, shares, dollars, weight, non-US flag) | O (same) |
| 5.4 | Verify, commit `reports/final/portfolio.json` | F |

### Phase 6: interactive dashboard (required)

| # | Task | Owner |
|---|---|---|
| 6.1 | `dashboard/` package: `python -m dashboard` builds a static site from `reports/` JSON into `dashboard/site/` and serves on localhost:8000; Plotly.js bundled locally; works offline and by opening `index.html`; sections Overview, Positions, Compare, Frontier, What-if (browser-side recalculation from exported mu and covariance), Method and evidence; plain-language metric definitions | S |
| 6.2 | Smoke test (build + page loads without console errors, Playwright if installed) and screenshots to `reports/final/screenshots/` | S (same) |
| 6.3 | Planner checks screenshots and the what-if math; README run instructions | F |
| 6.4 | **Check-in 4 with John**: try the dashboard, ask for changes | F |

### Phase 7: report

| # | Task | Owner |
|---|---|---|
| 7.1 | Draft `reports/final/report.md`: purpose, philosophy, constraints, method, allocation by type/region/sector/currency, security analysis per position, performance and attribution, risks and derivatives, conclusion, references; every number linked to file and command | S |
| 7.2 | Line-by-line review against the scorecard; fix overclaims; open the pull request | F |

Subagent count: 5 (2.1/2.4) + 1 (2.2) + 1 (2.3) + 5 (3) + 5 (4.1) + 1 (5) + 1 (6) + 1 (7) = 20 briefs, 13 of them Sonnet, 7 Opus (the 2.1 and 2.4 agents are the same five, continued).

## Data plan

Everything the plan needs is listed in `data_request.md` and fetched by one
command, `python -m research.fetch --universe research/plan/universe.csv`,
run from this PC in task 2.2 and committed. Rules:

- No subagent downloads data on its own. If something is missing it stops and
  lists it; the planner adds it to the universe file and reruns the fetch.
- Prices: daily adjusted close in the local listing currency, plus the US
  listing where one exists. FX: USD per unit for every currency in the
  universe. Yields and CPI: FRED monthly. Option indices: CBOE daily CSVs.
  Fundamentals: yfinance (current, 4 fiscal years) for every stock; SEC EDGAR
  `companyfacts` (point-in-time, with filing dates) for every US filer and
  20-F filer. Fund facts (expense ratio, AUM, holdings split): yfinance info
  plus the fund page, with URL and date recorded.
- EM bonds are priced through ETFs and open-end funds; country yields support
  the thesis. Turkish yield history is not available free and is not invented.
- Synthetic data is only for tests.

## Decision rules

All in `method.md`: sample split (2010-2017 in, 2018-2026 out), 60-month
minimum, non-US classification, hard screens, fundamental and technical
scores with pre-registered validation, the 100-point rubric, drop rules,
benchmarks, portfolio bounds, stress windows. The rubric cannot change after
results are seen without a change-log entry and a full rerun.

## Check-ins with John

| # | When | Questions |
|---|---|---|
| 1 | now (after Phase 1) | Approve the method and benchmarks. Gold/commodities/cash count as US-neutral (not non-US) under the 70% rule: confirm or treat as neutral. Are open-end mutual funds acceptable as EM bond positions, or ETFs only? Is the separate four-fund (active/passive global equity and bond fund) course analysis still needed? Does the course brief file exist to drop into `notes/assignment-rules.md`? |
| 2 | data fetched (task 2.2) | Confirmation only, since the fetch runs here; John is told what was fetched and what failed |
| 3 | after Phase 4 | Picks and runners-up before the build |
| 4 | dashboard first runs | Try it, ask for changes |

Answers log:

| Date | Question | Answer |
|---|---|---|
| | | |

## Known limits and risks to the plan

- Point-in-time fundamentals exist only for SEC filers. International names
  that do not file 20-Fs get current fundamentals for the thesis and a
  "not point-in-time" flag in the in-sample fundamental score.
- Open-end fund NAVs on Yahoo are total-return adjusted but their expense
  ratios differ from ETFs; the rubric's cost component handles this, and
  John decides whether they are allowed at all.
- The OOS period (2018-2026) contains one regime: strong US growth, a
  pandemic, a rate shock. Ranking on OOS Sharpe rewards what worked in that
  regime; the deflated Sharpe, the in-sample-vs-OOS rank test and the forward
  models are the counterweights, and the report says so.
- Option overlays are modelled, not traded history; CBOE BXM/PPUT histories
  are the cross-check.
- Usage: five parallel Opus analysts in Phase 3 are the costliest step; the
  usage pause after Phase 2 is where John decides.

## Progress log

| Date | Event |
|---|---|
| 2026-11-07 | Phase 0: repo read, data access confirmed from this PC, tests pass (13). Schema written. |
| 2026-11-07 | Phase 1: `method.md` and `data_request.md` written; committed before any backtest. Check-in 1 requested. |
