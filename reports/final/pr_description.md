Title: AFMBA622 portfolio research: method, screens, candidates, reviews, portfolio, dashboard and report

Open at: https://github.com/Greenbananas999/Investment-Portfolio/compare/main...claude/project-thread-2a6t0k?expand=1

---

## Summary

Seven-phase research run under `prompts/fable-planner.md` for the AFMBA622 portfolio: $100,000, 7-year horizon, at least 70% non-US, roughly 55/35/10 stocks/bonds/other.

- **Method first:** `research/plan/method.md` was committed before any candidate was backtested (sample split 2010-2017 / 2018-2026, screens, rubric, drop rules, benchmarks) with a change log of every later clarification and bug fix.
- **Screens:** 442-ticker universe fetched (`research/fetch.py --universe`), shared screening library (`research/screen/`), long lists and in-sample shortlist (`research/plan/shortlist.md`). No technical signal passed the pre-registered out-of-sample test.
- **Candidates and reviews:** 32 positions and 6 overlays analysed with one script per type (`research/candidates/`), results per `research/plan/results_schema.md` in `reports/candidates/`; five adversarial reviewers reproduced every number (`research/reviews/`, `reports/candidates/reviews/`); four code fixes made and rerun.
- **Scorecard and picks:** `research/plan/scorecard.py` applies the rubric and verdicts mechanically; picks in `research/plan/scorecard.md` (AVGO NVDA AMZN; 2330.TW BAJFINANCE.NS CSU.TO; PYEMX CEMB EMB HYEM; IAU SLV).
- **Portfolio:** `portfolio/build.py` extends the optimizer with the 70% floor, sleeve bands and position bounds; guideline, optimized, overlay, no-rule and benchmark comparisons, walk-forward variants, attribution, 7-year Monte Carlo, frontiers, order list (`reports/final/`).
- **Dashboard:** `python -m dashboard` builds an offline site from `reports/` and serves it on localhost:8000 (Plotly bundled from the installed package).
- **Report:** `reports/final/report.md`, every number tied to a file and command, reviewed line by line.

## Findings a reviewer should know

- The equal-weight 55/35/10 guideline beat the optimizer out of sample (Sharpe 1.10 vs 0.95); the method named this a valid finding in advance.
- The optimized portfolio misses the -25% drawdown budget by 0.47 points; the variants that pass were identified after seeing out-of-sample data and are labelled as such.
- The 2017 in-sample ranking had no predictive value in any sleeve, and the picks are 2026 survivors chosen partly on out-of-sample results, so the backtest is an upper bound.

## Notes

- Tests: 119 passed, 2 skipped (`pytest`).
- Raw SEC EDGAR JSON (489 MB) is git-ignored; `data/research/edgar_facts.csv.gz` is the committed extract and `python -m research.fetch --universe research/plan/universe.csv --only edgar` regenerates the raw files.
- `plotly` added to `requirements.txt` for the dashboard.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
