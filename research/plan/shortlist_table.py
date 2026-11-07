"""In-sample tables the planner uses to pick the Phase 2 shortlist.

    python research/plan/shortlist_table.py [--type us_growth_stock]

For every name that passed the hard screens (research/plan/longlists/<type>_scored.csv)
this joins the in-sample fundamental score with in-sample (2010-01 to 2017-12)
monthly USD return statistics against the method.md section 9 benchmark, and a
transparent composite used only to order the table:

    composite = 0.50 x pct(fundamental_score) + 0.25 x pct(IS Sharpe) + 0.25 x pct(IS IR)

Percentiles are within the position type. Nothing after 2017-12-31 is read.
Writes research/plan/longlists/<type>_insample_table.csv. Faded leaders are
included so the survivorship check is visible in the same table.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from research import screen
from research.screen import stats
from research.screen.prices import read_wide_csv, type_benchmark_ids

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "research"
LL = ROOT / "research" / "plan" / "longlists"
IS_START, IS_END = "2010-01-31", "2017-12-31"
TYPES = ["us_growth_stock", "intl_growth_stock", "em_bond", "other"]


def pct(s):
    return s.rank(pct=True)


def build(t, universe, monthly, rf):
    scored = pd.read_csv(LL / f"{t}_scored.csv", dtype={"flags": str, "reasons": str})
    scored = scored[scored["passed"].astype(str) == "True"].copy()
    bench_ids = type_benchmark_ids(universe)
    rows = []
    for _, s in scored.iterrows():
        tk = s["ticker"]
        if tk not in monthly.columns:
            continue
        r = monthly[tk].loc[IS_START:IS_END].dropna()
        b_id = bench_ids.get(tk)
        b = screen.benchmark_monthly(b_id, monthly)
        b = b.loc[IS_START:IS_END] if b is not None else None
        rows.append({
            "ticker": tk, "name": s["name"], "role": s["role"], "country": s["country"],
            "currency": s["currency"], "months_is": len(r),
            "cagr_is": stats.cagr(r), "vol_is": stats.vol(r),
            "sharpe_is": stats.sharpe(r, rf), "ir_is": stats.info_ratio(r, b) if b is not None else np.nan,
            "beta_is": stats.beta(r, b) if b is not None else np.nan,
            "maxdd_is": stats.max_drawdown(r), "benchmark": b_id,
            "fundamental_score": s.get("fundamental_score"), "rev_cagr_3y": s.get("rev_cagr_3y"),
            "fundamentals_pit": s.get("fundamentals_pit"), "category": universe.set_index("ticker").get("category", {}).get(tk, ""),
            "flags": s.get("flags", ""),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    fs = pd.to_numeric(df["fundamental_score"], errors="coerce")
    df["composite"] = (0.5 * pct(fs).fillna(0.5) + 0.25 * pct(df["sharpe_is"]) + 0.25 * pct(df["ir_is"]))
    df = df.sort_values("composite", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", np.arange(1, len(df) + 1))
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", choices=TYPES)
    args = ap.parse_args()
    universe = screen.load_universe(ROOT / "research" / "plan" / "universe.csv")
    prices = read_wide_csv(DATA / "prices.csv")
    fx = read_wide_csv(DATA / "fx.csv")
    usd = screen.usd_prices(prices, fx, universe)
    monthly = screen.monthly_returns(usd)
    rf = monthly["BIL"] if "BIL" in monthly else None
    pd.set_option("display.width", 250)
    for t in ([args.type] if args.type else TYPES):
        df = build(t, universe, monthly, rf)
        out = LL / f"{t}_insample_table.csv"
        df.to_csv(out, index=False)
        show = ["rank", "ticker", "name", "role", "country", "months_is", "cagr_is", "vol_is", "sharpe_is",
                "ir_is", "maxdd_is", "fundamental_score", "rev_cagr_3y", "fundamentals_pit", "composite"]
        print(f"\n===== {t}: {len(df)} names passed; benchmark {df['benchmark'].iloc[0] if len(df) else ''}; wrote {out.name}")
        with pd.option_context("display.max_rows", 100):
            print(df[show].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
