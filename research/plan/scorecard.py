"""Phase 4 scorecard: apply the pre-registered rubric (method.md section 7) to
the Phase 3 candidate results, merge the reviewer verdicts, apply the drop
rules (section 8) and write the ranking per position type.

    python research/plan/scorecard.py [--write]

Reads reports/candidates/<ID>.json (analysts), reports/candidates/reviews/
<type>_review.json (reviewers, optional until they exist), data/research/
prices.csv, volumes.csv, fx.csv, funds.csv and research/plan/universe.csv.
Writes reports/candidates/scorecard.csv and, with --write, the `rubric` and
`review` blocks of each candidate JSON (planner-owned fields only).

Rubric components (percentile within type, best = 1, times the weight):
  oos_sharpe (20)        metrics.out_of_sample.usd.sharpe
  oos_ir (15)            metrics.out_of_sample.usd.info_ratio (for a fund that is
                         itself the type benchmark the analyst stored the IR vs
                         GUIDE_BENCH; flagged in the table)
  oos_max_drawdown (10)  metrics.out_of_sample.usd.max_drawdown, less negative better
  consistency (10)       rolling.share_ir_positive_full
  diversification (10)   mean OOS correlation of the candidate's monthly USD return
                         with the other sleeves' benchmarks (IVW, EFG_EEM_5050, EMB,
                         GLD, excluding the candidate's own type benchmark), lower better
  inflation (5)          stress.inflation_2022.return (2021-12-31 to 2022-10-31), higher better
  liquidity_cost (5)     mean of pct(OOS average daily traded value, USD) and
                         pct(-expense ratio); open-end funds get the median traded value
  forward_return (15)    expected_return_7y.consensus_usd
  fundamental (5)        screens.fundamental_score (in-sample, 2017-12-31)
  technical (5)          dropped: no signal was kept (section 6), weight redistributed
Tie-breakers: smaller OOS max drawdown, smaller fx_vol_share, lower fee.

Drop rule 8.2: OOS Sharpe below the type benchmark's AND OOS IR below zero.
Reviewer verdicts: fail = dropped; downgrade = ranked after every pass in its
type and cannot be a top pick unless the type has fewer passes than slots.
"""

import argparse
import glob
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from research import screen  # noqa: E402
from research.screen.prices import SLEEVE_BENCHMARKS, TYPE_BENCHMARK, read_wide_csv  # noqa: E402
from research.screen.scoring import RUBRIC_WEIGHTS, percentile_scores, rubric_score  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CAND = ROOT / "reports" / "candidates"
DATA = ROOT / "data" / "research"
OOS = ("2018-01-31", "2026-10-31")
SLOTS = {"us_growth_stock": 3, "intl_growth_stock": 3, "em_bond": 4, "other": 3}
HIGHER = {"oos_sharpe": True, "oos_ir": True, "oos_max_drawdown": True, "consistency": True,
          "diversification": False, "inflation": True, "liquidity_cost": True,
          "forward_return": True, "fundamental": True}


def load_candidates():
    rows = {}
    for f in sorted(glob.glob(str(CAND / "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        if d.get("position_type") in SLOTS and "metrics" in d:
            rows[d["id"]] = d
    return rows


def load_reviews():
    out = {}
    for f in glob.glob(str(CAND / "reviews" / "*_review.json")):
        d = json.load(open(f, encoding="utf-8"))
        for cid, r in d.get("candidates", {}).items():
            out[cid] = {"verdict": r.get("verdict"), "claims": r.get("claims", []),
                        "notes": r.get("notes", ""), "reviewer": d.get("reviewer", "opus"),
                        "date": d.get("date", str(date.today())), "source": Path(f).name}
    return out


def market_inputs(cands):
    universe = screen.load_universe(ROOT / "research" / "plan" / "universe.csv")
    tickers = sorted({d["ticker"] for d in cands.values()} | {"IVW", "EFG", "EEM", "EMB", "GLD", "BIL", "ACWX"})
    prices = read_wide_csv(DATA / "prices.csv", columns=tickers)
    fx = read_wide_csv(DATA / "fx.csv")
    usd = screen.usd_prices(prices, fx, universe[universe.ticker.isin(tickers)])
    monthly = screen.monthly_returns(usd).loc[OOS[0]:OOS[1]]
    bench = {b: screen.benchmark_monthly(b, monthly) for b in SLEEVE_BENCHMARKS}
    vol = read_wide_csv(DATA / "volumes.csv", spikes=False, columns=tickers)
    funds = pd.read_csv(DATA / "funds.csv")
    funds = funds.set_index("ticker") if "ticker" in funds else funds
    return monthly, bench, usd, vol, funds


def traded_value(ticker, usd, vol):
    if ticker not in usd or ticker not in vol:
        return np.nan
    tv = (usd[ticker] * vol[ticker]).loc[OOS[0]:OOS[1]].dropna()
    tv = tv[tv > 0]
    return float(tv.mean() / 1e6) if len(tv) else np.nan


def build(cands, reviews, write=False):
    monthly, bench, usd, vol, funds = market_inputs(cands)
    bench_sharpe = {}
    for b, r in bench.items():
        ex = (r - monthly["BIL"]).dropna()
        bench_sharpe[b] = float(ex.mean() / ex.std() * np.sqrt(12))
    bench_sharpe["EMLC"] = None
    if "EMLC" in monthly:
        ex = (monthly["EMLC"] - monthly["BIL"]).dropna()
        bench_sharpe["EMLC"] = float(ex.mean() / ex.std() * np.sqrt(12))
    rows = []
    for cid, d in cands.items():
        t = d["position_type"]
        o = d["metrics"]["out_of_sample"]["usd"]
        own = TYPE_BENCHMARK[t]
        if t == "em_bond" and str(d.get("sector", "")).startswith("local"):
            own = "EMLC"
        tk = d["ticker"]
        corr = [monthly[tk].corr(bench[b]) for b in SLEEVE_BENCHMARKS if b != own and tk in monthly]
        fee = d.get("data", {}).get("fund_fee")
        if fee is None and tk in funds.index and "expense_ratio" in funds:
            fee = funds.loc[tk, "expense_ratio"]
        fee = 0.0 if fee is None or (isinstance(fee, float) and np.isnan(fee)) else float(fee)
        b_sh = bench_sharpe.get(own)
        drop2 = bool(b_sh is not None and o["sharpe"] < b_sh and o["info_ratio"] is not None and o["info_ratio"] < 0)
        rv = reviews.get(cid, {})
        rows.append({
            "id": cid, "ticker": tk, "name": d["name"], "type": t, "benchmark": own,
            "oos_sharpe": o["sharpe"], "oos_ir": o["info_ratio"], "oos_ir_vs": o.get("info_ratio_vs", d.get("benchmark")),
            "oos_max_drawdown": o["max_drawdown"], "t_stat_ir": o.get("t_stat_ir"),
            "deflated_sharpe": o.get("deflated_sharpe"),
            "consistency": d.get("rolling", {}).get("share_ir_positive_full"),
            "diversification": float(np.nanmean(corr)) if corr else np.nan,
            "inflation": (d.get("stress", {}).get("inflation_2022") or {}).get("return"),
            "traded_value_usd_m": traded_value(tk, usd, vol), "fee": fee,
            "forward_return": d.get("expected_return_7y", {}).get("consensus_usd"),
            "fundamental": (d.get("screens") or {}).get("fundamental_score"),
            "fx_vol_share": (d.get("currency") or {}).get("fx_vol_share") if isinstance(d.get("currency"), dict) else None,
            "benchmark_oos_sharpe": b_sh, "drop_rule_2": drop2,
            "review_verdict": rv.get("verdict"), "review_source": rv.get("source"),
        })
    df = pd.DataFrame(rows).set_index("id")
    # open-end funds (no exchange volume): median traded value of the type
    for t, g in df.groupby("type"):
        med = g["traded_value_usd_m"].median()
        df.loc[(df.type == t) & df.traded_value_usd_m.isna(), "traded_value_usd_m"] = med
    out = []
    for t, g in df.groupby("type"):
        pct = percentile_scores(g, ["oos_sharpe", "oos_ir", "oos_max_drawdown", "consistency", "diversification",
                                    "inflation", "forward_return", "fundamental", "traded_value_usd_m", "fee"],
                                {**HIGHER, "traded_value_usd_m": True, "fee": False})
        pct["liquidity_cost"] = pct[["traded_value_usd_m", "fee"]].mean(axis=1)
        comp = pct[list(RUBRIC_WEIGHTS)[:-1]]  # all but technical
        rs = rubric_score(comp, technical_kept=False)
        g = g.copy()
        for c in comp.columns:
            g[f"pct_{c}"] = comp[c]
        g["rubric_total"] = rs["rubric_total"]
        g["missing_weight"] = rs["missing_weight"]
        # eligibility and ordering: fail or drop-rule -> out; downgrade after passes
        g["status"] = np.where(g.review_verdict.eq("fail"), "dropped: reviewer fail",
                      np.where(g.drop_rule_2, "dropped: rule 8.2",
                      np.where(g.review_verdict.eq("downgrade"), "downgraded", "eligible")))
        order = g.status.map({"eligible": 0, "downgraded": 1, "dropped: rule 8.2": 2, "dropped: reviewer fail": 3})
        g = g.assign(_o=order).sort_values(["_o", "rubric_total", "oos_max_drawdown", "fx_vol_share", "fee"],
                                           ascending=[True, False, False, True, True]).drop(columns="_o")
        g["rank_in_type"] = np.arange(1, len(g) + 1)
        n = SLOTS[t]
        elig = g.index[g.status.isin(["eligible"])].tolist()
        if len(elig) < n:
            elig += g.index[g.status.eq("downgraded")].tolist()[: n - len(elig)]
        picks = elig[:n]
        survivors = g.index[~g.status.str.startswith("dropped")].tolist()
        # section 8 rule 2: a rule-8.2 casualty may stay a runner-up only when
        # the type has fewer than 5 survivors; a reviewer "fail" never can.
        pool = [i for i in g.index if i not in picks and not g.loc[i, "status"].startswith("dropped")]
        if len(survivors) < 5:
            pool += [i for i in g.index if g.loc[i, "status"] == "dropped: rule 8.2"]
        runners = pool[:2]
        g["decision"] = ["pick" if i in picks else "runner-up" if i in runners else "" for i in g.index]
        out.append(g)
    sc = pd.concat(out)
    sc.to_csv(CAND / "scorecard.csv")
    if write:
        for cid, d in cands.items():
            r = sc.loc[cid]
            d["rubric"] = {"scores": {c: (None if pd.isna(r[f"pct_{c}"]) else round(float(r[f"pct_{c}"]), 4)) for c in list(RUBRIC_WEIGHTS)[:-1]},
                           "weights": {k: v for k, v in RUBRIC_WEIGHTS.items() if k != "technical"},
                           "total": None if pd.isna(r["rubric_total"]) else round(float(r["rubric_total"]), 2),
                           "rank_in_type": int(r["rank_in_type"]), "status": r["status"], "decision": r["decision"],
                           "drop_rule_2": bool(r["drop_rule_2"]), "benchmark_oos_sharpe": r["benchmark_oos_sharpe"],
                           "note": "technical weight redistributed (no signal kept); liquidity uses OOS average daily traded value and the expense ratio"}
            rv = reviews.get(cid)
            if rv:
                d["review"] = {"reviewer": rv["reviewer"], "date": rv["date"], "verdict": rv["verdict"],
                               "claims": rv["claims"], "notes": rv["notes"], "source": rv["source"]}
            json.dump(d, open(CAND / f"{cid}.json", "w", encoding="utf-8"), indent=1, default=float)
    return sc, bench_sharpe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write rubric/review blocks into the candidate JSONs")
    args = ap.parse_args()
    cands = load_candidates()
    reviews = load_reviews()
    sc, bs = build(cands, reviews, write=args.write)
    pd.set_option("display.width", 250)
    print("benchmark OOS Sharpe:", {k: (round(v, 3) if v is not None else None) for k, v in bs.items()})
    print("reviews loaded for:", sorted(reviews) if reviews else "none yet")
    cols = ["rank_in_type", "ticker", "oos_sharpe", "oos_ir", "t_stat_ir", "oos_max_drawdown", "consistency",
            "diversification", "inflation", "traded_value_usd_m", "fee", "forward_return", "fundamental",
            "rubric_total", "drop_rule_2", "review_verdict", "status", "decision"]
    for t, g in sc.groupby("type", sort=False):
        print(f"\n===== {t}")
        print(g[cols].round(3).to_string())
    print(f"\nwrote {CAND / 'scorecard.csv'}" + (" and the rubric/review blocks" if args.write else ""))


if __name__ == "__main__":
    main()
