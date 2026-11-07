"""Shared screening library (method.md sections 2-7 and 12).

One implementation of the hard screens, fundamental and technical scores and
the signal validation, used by every position type. See
research/plan/screen_usage.md for the commands.
"""

from .edgar import edgar_facts, point_in_time, split_events, split_factor, yfinance_table
from .fundamental import (expected_fx_loss, fundamental_score_bonds, fundamental_score_other,
                          fundamental_score_stocks, inflation_beta, rating_to_score, stock_measures)
from .hard import hard_screens
from .prices import (BENCHMARKS, TYPE_BENCHMARK, benchmark_level, benchmark_monthly, dividend_factor,
                     load_universe, monthly_returns, usd_crosscheck, usd_prices)
from .scoring import (RUBRIC_WEIGHTS, deflated_sharpe, expected_max_sharpe, is_oos_rank_test,
                      percentile_scores, rubric_score)
from .stats import (alpha_t, capture, info_ratio, max_drawdown, metrics_block, rolling_ir,
                    rolling_sharpe, share_ir_positive, sharpe, sortino, tracking_error)
from .technical import (HIGHER_IS_BETTER, signals_at, technical_score, technical_signals,
                        tercile_backtest, validate_signals)
