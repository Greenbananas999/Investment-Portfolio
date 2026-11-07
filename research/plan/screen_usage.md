# Screening library: how to run it (task 2.4)

Code: `research/screen/` (package; `python -m research.screen`). Implements
method.md sections 2-7. Reads `research/plan/universe.csv` and the files in
`data/research/`; writes to `research/plan/longlists/`.

**Rule: scoring runs only with `--as-of 2017-12-31`** (the default). `hard`
and `score` refuse a later date unless `--allow-oos` is passed, which is for
the planner's forward thesis only. `validate` uses out-of-sample data by
design and is run once, by the planner.

```bash
python -m research.screen hard     --type us_growth_stock --as-of 2017-12-31
python -m research.screen score    --type us_growth_stock --as-of 2017-12-31
python -m research.screen validate --type us_growth_stock          # planner only
```

`--type` is one of `us_growth_stock`, `intl_growth_stock`, `em_bond`, `other`
(overlays are modelled in Phase 3). Options: `--rank-all` (also rank names
that failed a hard screen), `--passed-only` (validate on hard-screen passers),
`--universe <csv>`, `--out-dir <dir>`, `--cost-bps 10`.

**Extra inputs** (optional): put `research/plan/longlists/<type>_inputs.csv`
with a `ticker` column plus any of: EM bonds `ytm, expected_fx_loss,
local_currency, avg_rating, country_max_weight, debt_gdp,
current_account_gdp, inflation, real_yield, bid_ask, traded_value_usd_m`;
other sleeve `roll_cost`. Decimals (0.06 = 6%). Expense ratios may be
decimals or percent per column (a column whose max exceeds 0.05 is read as percent).

## Output files

- `<type>_hard.csv`: `ticker, name, type, role, country, currency, passed,
  reasons, flags, months_in_sample, months_total, first_price,
  market_cap_usd_bn, mcap_asof_usd_bn, traded_value_usd_m, rev_cagr_3y,
  fundamentals_pit, aum_usd_bn, expense_ratio, price_problem`.
- `<type>_scored.csv`: the hard columns, then the section 5 measures (stocks:
  `rev_cagr_3y, ni_cagr_3y, roic_or_roe, op_margin, op_margin_chg_3y,
  net_debt_ebitda, fcf_yield, pe_now, pe_rel_5y`, `fy_end`, `valuation_date`;
  bonds: `carry, rating_score, corr_equity, ...`; other: `inflation_beta,
  ret_2022, ret_2022_info, corr_acwx, corr_emb`), the group scores
  (`growth_score`, ...), `fundamental_score` (0-1), raw signals `T1..T5`, their
  percentiles `T1_pct..T5_pct`, `technical_score` (0-1), `technical_note`, the
  ADR cross-check `usd_ticker, adr_months, adr_corr, adr_ann_diff`, `as_of`.
  Scores are percentile ranks among the names that passed the hard screens.
- `<type>_signals.csv`: per signal `months_is, ir_is, t_is, months_oos,
  ir_oos, t_oos, active_ann_*, avg_names, avg_turnover, kept, note`. Once it
  exists, `score` uses only the kept signals for `technical_score`.

## Reading the flags

- `reasons` (non-empty means `passed = False`): a rule that was checked and failed.
- `flags`: never fails a name. "... not checked" means the input is missing
  (find a source or note it); "fundamentals not point-in-time" means current
  yfinance statements were used (allowed for international stocks only;
  US revenue CAGR then counts as not checked); "short history" means fewer
  than 120 months in total; "AUM is the latest figure" and "2022 window
  after as_of: reported, not scored" are reminders, not problems.
- T1-T5 at as_of 2017-12-31 use prices to 2017-12-31 only; T4 is
  volatility (lower is better), T5 is price / 52-week high - 1 (closer to 0
  is better).

Synthetic data is never a result. Do not edit the scored files by hand;
rerun the command.
