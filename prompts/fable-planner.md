# Planner prompt: find and prove the best assets for the 622 portfolio

How to use: start a Claude Code session in this repo with Fable as the main
model (`claude --model claude-fable-5-1`, or `/model` inside a session) and
paste everything below the line. Fable plans and reviews; it hands the build
work to Sonnet and Opus subagents through the Agent tool. Edit the
**Settings** block first if the rules change.

---

You are the lead planner for a graduate portfolio project (AFMBA622, Global
Portfolio Research, UMass Boston). Your job is to design a research method,
shortlist several promising candidates for each position in the portfolio,
have subagents research and test each one, prove which candidates are best
with backtests and models, and deliver an interactive local web page that
John can use to explore the results and explain each pick to his team. You
plan, delegate, check and decide. You do not write the bulk of the code
yourself: subagents do the building, and you review their output before you
trust it.

## The client brief (John's project proposal, Nov 2026)

These are the rules. They replace any older rules you find in the repo or in
notes (for example the 18-ETF optimizer's 25% cap, or the old four-fund
framing).

- **Purpose:** invest $100,000 over a 7-year horizon. The portfolio should mix
  growth and security.
- **Philosophy:** mostly passive, with periodic adjustments for market
  conditions. A quantitative approach that combines technical and
  fundamental analysis. Diversified across US equities and emerging market
  equities.
- **Risks to address:** short-term and long-term risks, including severe
  market swings and inflation.
- **Constraint 1, non-US:** the portfolio must be 70% non-US. The team's
  reason: the US has had the best returns historically, but recent
  instability argues for a more secure, less US-dependent portfolio.
  John confirmed the rule means at least 70% of total portfolio value is
  non-US (stocks, bonds and other combined), so US assets are at most 30%.
- **Constraint 2, mix:** roughly 55% stocks, 35% bonds, 10% other. This is a
  guideline. You may move away from it if a different allocation is clearly
  better on risk-adjusted terms, but you must show the guideline portfolio
  next to yours and explain the difference.
- **Acceptable investments:** no restrictions on type. Derivatives are
  allowed.
- **Initial structure (a starting point; you may test changes to it):**
  - 3 US growth stocks
  - 3 international growth stocks
  - 4 emerging market bonds (growth and security)
  - Derivatives overlay: covered calls, forwards, futures, options, swaps
  - The 10% "other" sleeve is not specified; propose candidates (gold,
    commodities, global REITs, inflation-linked bonds, cash-like assets).

The stocks and bonds already modeled in `research/` (SK Hynix, Samsung, TSMC,
Apple, Nvidia, Meta, Microsoft, French OAT, Turkish government bonds) were
earlier examples, not a required list. Use or drop them on the evidence.

"Best" means best risk-adjusted return over the 7-year horizon, judged out of
sample: Sharpe ratio and information ratio first (the metrics the course
names), with max drawdown, inflation resilience and FX risk as tie-breakers.

The course brief (`/mnt/project-files/notes/assignment-rules.md` if it exists)
also asks for efficient frontiers, returns in local and base currency, and
bottom-up analysis of top holdings. Cover those inside this work. Ask John at
the first check-in whether the report still needs the separate four-fund
analysis (active and passive global equity and bond funds).

## Settings (change these, nothing else depends on the wording)

```yaml
base_currency: USD
capital_usd: 100000
horizon_years: 7
min_non_us_weight: 0.70          # of total portfolio value
target_mix: { equity: 0.55, bonds: 0.35, other: 0.10 }
mix_tolerance: 0.10              # how far the optimized mix may drift from target before you must justify it in writing
positions: { us_growth_stocks: 3, intl_growth_stocks: 3, em_bonds: 4, other: "1-3" }
shortlist_per_position_type: 8   # candidates screened deeply per type (e.g. 8 US growth stocks for 3 spots)
rebalance: quarterly             # "mostly passive"; also test semi-annual and annual
derivatives: overlay_only        # test with and without; keep only if it improves risk-adjusted results
backtest_start: 2010-01-01
out_of_sample_start: 2018-01-01  # nothing after this date may inform the method or the shortlist
risk_free: BIL                   # or 3M T-bill yield from data/research/yields.csv
models: { planner: fable, builders: sonnet, hard_modeling_and_review: opus }
```

## What already exists in this repo (reuse it, do not rebuild it)

- `portfolio/`: walk-forward optimizer. Ledoit-Wolf covariance
  (`optimize.ledoit_wolf`), shrunk expected returns, SLSQP max-Sharpe and
  min-variance with a non-US floor and weight cap, periodic rebalancing on a
  trailing lookback, trading costs, FX contribution. Entry point `run.py`.
  Settings in `portfolio/config.py`. You will need to add asset-class mix
  constraints (55/35/10 with tolerance) and position-count rules.
- `research/`: expected-return models for single stocks and sovereign bonds.
  `historical.py` (CAGR, vol, Sharpe, drawdown, beta, IR, currency effect),
  `capm.py` (Blume betas), `dcf.py` (FCF model plus Monte Carlo on inputs),
  `grinold_kroner.py`, `bonds.py` (yield scenarios, duration, total-return
  backtest), `montecarlo.py` (block bootstrap), `forecast_test.py` (how well
  each method predicted next-year returns), `frontier.py` (ex-ante frontier
  with and without the non-US rule), `metrics.py`. Every assumption lives in
  `research/config.py`. Entry point `research_run.py`. `research/html_report.py`
  and `research/report_template.html` are a starting point for the dashboard.
- Cached data: `data/prices.csv`, `data/fx.csv`, `data/research/` (prices,
  FX, yields, fundamentals for the seven example stocks).
- Tests in `tests/`. Keep them passing; add tests for new modules.

## Data constraints (plan around these)

- The cloud sandbox proxy blocks Yahoo Finance, FRED and Stooq. Real data was
  downloaded on John's Windows PC (`C:\Users\malon\OneDrive\Desktop\Code\porfolio`,
  same repo) and committed. Do not assume a subagent can download prices.
- So: before any backtest, list every ticker, FX pair, yield series and
  fundamentals file the plan needs, and write a single fetch script plus a
  request file (`research/plan/data_request.md`) that John can run on his PC.
  Batch it into one request, not a trickle. Extend `research/fetch.py` rather
  than writing a new fetcher.
- Emerging market bonds: individual EM bond prices are hard to get for free.
  Use EM bond ETFs and funds (hard-currency sovereign, local-currency
  sovereign, EM corporate, frontier) as the tradable positions or as price
  proxies, and government yield series for country-level modeling. Say which
  you used. Turkish yield history is missing from free sources; do not invent
  it.
- Options: free historical option prices are rare. Model covered calls and
  protective puts with Black-Scholes on realized or implied volatility plus a
  stated volatility risk premium, and cross-check against the CBOE BXM
  (buy-write) and PPUT (put-write/protective) index histories if fetched.
  Model FX forwards from interest rate differentials (covered interest
  parity). State every assumption.
- Never present synthetic data (`--synthetic`) as a result. It only checks
  that code runs.

## How you work

### Phase 0: orient (you, no subagents)

Read `README.md`, `portfolio/config.py`, `research/config.py` and skim the
modules above. Then write `research/plan/PLAN.md` with: the phases below
adapted to what you found, the task list with owners (which subagent, which
model), the data request, and the decision rules from Phase 1. Keep PLAN.md
current as work completes; it is the single source of truth.

### Phase 1: fix the method before looking at results

Write `research/plan/method.md` and commit it **before** any candidate is
backtested. It must state:

- The client objective, 7-year horizon, risk tolerance, and how "growth and
  security" translates into numbers (e.g. a max drawdown budget, a minimum
  real return target).
- For each position type, the screening universe: e.g. US growth stocks from
  the S&P 500 / Nasdaq 100; international growth stocks from developed ex-US
  and EM large caps (ADRs or local listings, local listings preferred for the
  currency analysis); EM bonds from EM sovereign and corporate bond ETFs and
  funds; the "other" sleeve from gold, broad commodities, global REITs, TIPS
  and similar.
- **Fundamental screens** (decided now): e.g. revenue and earnings growth,
  ROIC, margins, leverage, free cash flow yield, valuation vs. history and
  peers, DCF upside from `research/dcf.py`. For bonds: yield, spread,
  duration, credit rating, country debt and inflation metrics, currency
  valuation.
- **Technical screens** (decided now): e.g. 12-1 month momentum, price vs.
  200-day moving average, relative strength vs. benchmark, volatility. The
  proposal calls for technical analysis, so test whether each signal actually
  added value out of sample; drop any that did not and say so.
- The scoring rubric with weights, decided now: out-of-sample Sharpe,
  information ratio vs. the position's benchmark, max drawdown, consistency
  (rolling 3-year IR above zero), correlation with the rest of the
  portfolio, inflation sensitivity, liquidity, and the fundamental and
  technical scores.
- The benchmark for each position type: S&P 500 Growth or Nasdaq 100 for US
  growth stocks, MSCI ACWI ex-US Growth or MSCI EM for international, the
  J.P. Morgan EMBI Global Diversified (or an ETF tracking it) for EM bonds,
  and a 55/35/10 ACWI ex-US / EM bond / gold blend for the whole portfolio
  plus a plain 60/40 for context.
- What counts as proof (see Evidence standards) and what drops a candidate.

Changing the rubric after seeing results is not allowed. If you must change
it, log the change and the reason in method.md and rerun every candidate
under the new rubric.

### Phase 2: wide screen, then shortlist

Delegate one screening subagent per position type (Sonnet): US growth stocks,
international growth stocks, EM bonds, the "other" sleeve, and derivatives
overlays. Each builds a long list (20-40 names), applies the hard screens and
the fundamental and technical scores using **only in-sample data** (before
`out_of_sample_start`), and returns a ranked table with ticker, name, country,
currency, sector, scores and source links. You pick
`shortlist_per_position_type` per type for deep research and write the
reasoning for each pick and each near miss to `research/plan/shortlist.md`.

Include candidates that disagree with each other (e.g. a value-leaning and a
momentum-leaning growth stock, a hard-currency and a local-currency EM bond
fund, Asian vs. Latin American exposure), so the comparison tests something.
Note which candidates make the 70% non-US floor easy or hard to reach.

Derivatives candidates to test as overlays, not standalone bets: covered
calls on the US growth stocks, protective puts or collars on the equity
sleeve, FX forwards to hedge some of the EM local-currency bond exposure,
and index futures for cheap rebalancing.

**Usage pause (required):** after Phase 2 is committed, stop. Post a short
summary of the shortlist, the data request, and a plan for Phases 3-7 with
the number of subagents and which model each uses. Then wait for John to
check his usage and say "continue". Do not start Phase 3 without that.

### Phase 3: deep research on each candidate (parallel subagents)

Spawn one subagent per position type (about five), each analysing all of
its shortlisted candidates with one shared script, rather than one subagent
per candidate. This keeps usage down and makes the candidates comparable. Sonnet for
standard backtest and metrics work; Opus for anything with real modeling
judgement (DCF, expected returns, EM bond scenarios, option overlays,
attribution). Every subagent gets the brief template at the end of this
prompt, filled in. Each returns:

- A one-page memo: thesis, what drives returns, fundamentals, technicals,
  risks, and a verdict. End with a "how to explain this pick" box: three
  plain-English sentences John can say to his team.
- Metrics in USD and in local currency: CAGR, vol, Sharpe, Sortino, max
  drawdown, beta, alpha, tracking error, information ratio, up/down capture,
  all split in-sample vs. out-of-sample, plus rolling 3-year Sharpe and IR.
- Currency split: local return, FX return, and the effect of hedging.
- Expected 7-year return using at least two methods from `research/` (DCF,
  CAPM, Grinold-Kroner, yield-based for bonds, Monte Carlo ranges), with every
  assumption cited from `research/config.py` or added there.
- Stress behaviour: 2008, 2013 taper tantrum, 2020 Covid crash, 2022
  inflation and rate shock, plus a strong-USD scenario.
- Code under `research/candidates/` (or a new module), with tests, and the
  exact command that reproduces every number.
- Machine-readable results in `reports/candidates/<ticker>.json` (schema
  defined by you in Phase 0) so the dashboard can read them.

### Phase 4: prove it (adversarial review)

For each position type, spawn one Opus reviewer that did not build the
analysis. Its job is to break the conclusion: rerun the numbers from the
committed code, look for look-ahead bias, survivorship bias (today's winning
growth stocks look great in hindsight; include stocks that were top growth
names in 2010-2015 and later faded), cherry-picked windows, wrong benchmark,
fees and dividends missing, currency mistakes, and overfitting. It returns
pass/fail per claim with reasons. A candidate whose edge disappears under
review is dropped or downgraded, and you say so.

Then pick the positions (3 US growth, 3 international growth, 4 EM bonds, the
"other" sleeve) and 1-2 runners-up for each, scored by the Phase 1 rubric.
Write the scorecard to `research/plan/scorecard.md`, including why each
runner-up lost.

### Phase 5: build the portfolio and prove it as a whole

One Opus subagent extends the existing optimizer (`portfolio/optimize.py`,
`research/frontier.py`) instead of writing a new one:

- Constraints: 70% non-US floor, 55/35/10 mix within `mix_tolerance`,
  position counts, long-only for the base positions.
- Compare: (a) the guideline portfolio (exact 55/35/10, equal weight inside
  each sleeve), (b) the optimized portfolio within the rules, (c) the
  optimized portfolio with derivatives overlays, (d) the benchmark blend and
  60/40, and (e) the same optimization without the 70% non-US rule, to show
  what the rule costs or saves.
- Walk-forward backtest at the chosen rebalance frequency with trading
  costs, on $100,000. Show which periodic adjustments the method would have
  made and whether they helped.
- 7-year forward Monte Carlo (block bootstrap plus forward-looking drift):
  median and 5th/95th percentile ending value, probability of loss, probability
  of beating inflation.
- Ex-post and ex-ante efficient frontiers, with and without the non-US rule,
  marking the tangency, minimum-variance, guideline and chosen portfolios.
- Portfolio Sharpe and information ratio, return attribution by sleeve and
  by local return vs. FX, and the final order list: ticker, shares, dollars,
  weight, non-US flag.

### Phase 6: the interactive dashboard (required)

John needs to explore the results on his own and walk his team through why
each position was picked. Build a locally hosted web page:

- Lives in `dashboard/`. One command builds and serves it:
  `python -m dashboard` reads the JSON results in `reports/`, writes a static
  site to `dashboard/site/`, and serves it at `http://localhost:8000` with
  Python's built-in server. It must work on Windows with no extra installs
  beyond `requirements.txt`, and work offline (bundle the charting library,
  e.g. Plotly.js, into `dashboard/site/` rather than relying on a CDN). Also
  works by opening `dashboard/site/index.html` directly if possible.
- Sections (tabs or pages):
  1. **Overview:** the final portfolio, $100k split by position, sleeve,
     region and currency; rule checks shown as pass/fail (70% non-US, mix vs.
     55/35/10, position counts); headline Sharpe, IR, expected return,
     drawdown vs. benchmarks.
  2. **Positions:** one card per pick with the "how to explain this pick"
     sentences, key fundamentals and technicals, charts, and the runners-up
     with why they lost. This is the page John presents from.
  3. **Compare:** choose any candidates (picked or rejected) and overlay
     growth of $10,000, drawdowns, rolling Sharpe, local vs. USD returns.
  4. **Frontier:** the efficient frontiers, toggles for the non-US rule and
     derivatives, hover shows each portfolio's weights.
  5. **What-if:** sliders for each position's weight; live recalculation of
     expected return, volatility, Sharpe, non-US share and mix, with rule
     violations highlighted. Stress scenario buttons (2008, 2022, strong USD)
     that show the portfolio's estimated loss. Computed in the browser from
     exported expected returns and the covariance matrix.
  6. **Method and evidence:** the pre-registered method, out-of-sample
     results, reviewer verdicts, which technical signals worked, caveats and
     data sources.
- Plain language throughout, with a short definition beside each metric
  (what a Sharpe ratio or information ratio means).
- Add a smoke test: the build runs on the committed results and the page
  loads without console errors (Playwright if available). Take screenshots of
  each section into `reports/final/screenshots/` and check them yourself.
- Document how to run it in `README.md`.

### Phase 7: the report

One subagent drafts `reports/final/report.md`: purpose, philosophy,
constraints, method, allocation (asset type, region, sector, currency),
security analysis per position, performance and attribution, risks and
derivatives use, conclusion, references. Every number links to the file and
command that produced it. You review it line by line against the scorecard
and fix anything that overclaims.

## Evidence standards (apply to every claim)

- Out-of-sample means the number was not used to choose the method, the
  shortlist or the weights. Always show in-sample and out-of-sample side by
  side. Walk-forward for anything optimized.
- Survivorship bias: screening growth stocks with today's index members
  flatters the results. Use point-in-time membership where possible, or at
  least show how former leaders did.
- Look-ahead: weights and signals at date t use data up to t-1 only.
  Fundamentals are lagged to their actual release date.
- Total-return series (dividends and coupons reinvested), net of fund fees
  and trading costs. Option overlays include bid-ask costs.
- Multiple testing: screening dozens of names finds winners by luck. Report
  the deflated Sharpe ratio or at least t-stats on alpha and IR, and whether
  the in-sample ranking held out of sample.
- Minimum history: no conclusion from less than 5 years of monthly data;
  flag anything under 10.
- Every number must be reproducible from committed code and data with a
  stated command. Facts from the web (ratings, fund fees, holdings) get a
  source link and date.
- Say plainly when evidence is weak. "The guideline portfolio was as good as
  the optimized one" is a valid and useful finding.

## Delegation rules

- Subagents start with no context. The brief must contain everything: the
  goal, the rules, the files to read, the data available, the evidence
  standards, the exact deliverables and file paths, and how to report back.
- Run independent subagents in parallel. Do not start Phase 3 work on a
  candidate until its data exists in `data/`.
- Give each subagent its own output folder. Only one subagent at a time edits
  a shared module (`portfolio/optimize.py`, `research/config.py`,
  `research/fetch.py`); serialize those edits.
- When a subagent returns, check its work: run its command, spot-check two
  numbers, read its tests. Do not pass unverified claims into the report or
  the dashboard.
- If a subagent is blocked on data, it stops and says what it needs. It does
  not fake, interpolate or swap in a different asset without saying so.

## Check-ins with John

Stop and ask John, with a short summary and a recommendation, at these points
only:

1. After Phase 1: the method, the benchmarks, and whether the four-fund course analysis is still needed.
2. When the data request is ready (he runs the fetch script on his PC).
3. After Phase 4: the picks and runners-up, before the portfolio build.
4. When the dashboard first runs, so he can try it and ask for changes.

Otherwise keep going. Commit after each phase with a clear message, on a
feature branch, and open a pull request at the end.

## Subagent brief template

```
Role: <screener | candidate analyst | reviewer | portfolio builder | dashboard builder | report writer>
Model: <sonnet | opus>
Project: AFMBA622 portfolio. $100,000, 7-year horizon, growth plus security,
at least 70% non-US, roughly 55% stocks / 35% bonds / 10% other, derivatives
allowed. Goal: best risk-adjusted return, judged out of sample by Sharpe and
information ratio.
Your task: <one paragraph>
Candidate(s): <ticker, name, position type, benchmark>
Read first: README.md, research/plan/method.md, <relevant modules>
Data available: <files in data/ and their date ranges>. You cannot download
market data from this sandbox. If something is missing, stop and list it.
Settings: <paste the Settings block>
In-sample: <backtest_start> to <out_of_sample_start>. Out-of-sample: after that.
Evidence standards: <paste the Evidence standards section>
Deliverables: <memo path>, <results JSON path>, <charts>, <code + tests>, and
the exact command that reproduces every number.
Report back: verdict in two sentences, the metrics table, what you could not
check, and anything that surprised you.
```

Start with Phase 0 now.
