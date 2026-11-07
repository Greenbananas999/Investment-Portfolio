"""Command line: `python -m research.screen {hard,score,validate} --type <type> ...`.

Reads the files listed in data_request.md (missing optional files are
skipped and flagged), writes research/plan/longlists/<type>_{hard,scored,signals}.csv.
`hard` and `score` refuse --as-of later than 2017-12-31 unless --allow-oos.
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from . import edgar as ed
from .fundamental import (STOCK_GROUPS, fundamental_score_bonds, fundamental_score_other,
                          fundamental_score_stocks, group_score)
from .hard import hard_screens
from .prices import (DATA, IN_SAMPLE_END, PLAN, ROOT, SCREEN_TYPES, SCREENED_ROLES, benchmark_level,
                     benchmark_monthly, is_local_currency_bond, load_universe, monthly_returns,
                     price_coverage, read_dividends, read_wide_csv, usd_crosscheck, usd_prices)
from .scoring import percentile_scores
from .technical import HIGHER_IS_BETTER, SIGNALS, signals_at, technical_score, technical_signals, \
    validate_signals

BENCH_TICKERS = ["IVW", "EFG", "EEM", "EMB", "EMLC", "GLD", "ACWX", "BIL"]
# Whole-word match on name/category/notes, after stripping the tool name
# "yfinance" (which contains "financ"; planner fix 2026-11-07 after review).
FIN_WORDS = re.compile(r"(bank|banco|financ\w*|insur\w*|brokerage|exchange operator)")


class Inputs:
    """Every data file the screens read, loaded once. Missing optional files are None."""

    def __init__(self, universe_path=None, typ=None, data_dir=DATA, plan_dir=PLAN, inputs_dir=None):
        self.data_dir, self.plan_dir = Path(data_dir), Path(plan_dir)
        inputs_dir = Path(inputs_dir) if inputs_dir else self.plan_dir / "longlists"
        self.notes = []
        self.universe = self._universe(universe_path, typ)
        u = self.universe
        self.needed = set(u["ticker"].dropna()) | set(u["usd_ticker"].dropna()) | set(BENCH_TICKERS)
        self.prices_local = self._prices()
        p = self.data_dir / "prices_usd_listing.csv"
        self.usd_listing = read_wide_csv(p, columns=self.needed) if p.exists() else None
        self.fx = self._fx()
        self.funds = self._csv(self.data_dir / "funds.csv")
        p = self.data_dir / "yields.csv"
        self.yields = pd.read_csv(p, index_col=0, parse_dates=True) if p.exists() else None
        p = self.data_dir / "volume.csv"
        self.volume = read_wide_csv(p, spikes=False, columns=self.needed) if p.exists() else None
        self.extra = self._csv(inputs_dir / f"{typ}_inputs.csv") if typ else None

    def _universe(self, path, typ):
        cands = [Path(path)] if path else [self.plan_dir / "universe.csv"]
        if not path and typ:
            cands.append(self.plan_dir / "longlists" / f"{typ}.csv")
        for c in cands:
            if c.exists():
                self.notes.append(f"universe: {c}")
                return load_universe(c)
        raise FileNotFoundError("no universe file found (tried " + ", ".join(map(str, cands)) + ")")

    def _prices(self):
        frames = []
        for p in (self.data_dir / "prices.csv", self.data_dir / "prices_usd_listing.csv",
                  ROOT / "data" / "prices.csv"):
            if p.exists():
                frames.append(read_wide_csv(p, columns=self.needed))
                self.notes.append(f"prices: {p}")
        if not frames:
            return pd.DataFrame()
        out = frames[0]
        for f in frames[1:]:   # earlier files win; later ones only add missing tickers
            new = [c for c in f.columns if c not in out.columns]
            if new:
                out = out.join(f[new], how="outer")
        return out.sort_index()

    def _fx(self):
        out = None
        for p in (self.data_dir / "fx.csv", ROOT / "data" / "fx.csv"):
            if p.exists():
                f = read_wide_csv(p)
                out = f if out is None else out.join(f[[c for c in f.columns if c not in out]], how="outer")
        out = pd.DataFrame() if out is None else out.sort_index().ffill()
        out["USD"] = 1.0
        return out

    @staticmethod
    def _csv(p):
        if not p.exists():
            return None
        df = pd.read_csv(p)
        return df.set_index("ticker") if "ticker" in df else df


def _rows(inp, typ, roles=SCREENED_ROLES):
    u = inp.universe
    return u[(u["type"] == typ) & (u["role"].isin(roles))] if roles else u[u["type"] == typ]


def _monthly_bench(inp):
    px = inp.prices_local[[t for t in BENCH_TICKERS if t in inp.prices_local]]
    return monthly_returns(px) if len(px.columns) else pd.DataFrame()


def type_benchmark(inp, typ, tickers):
    """Benchmark level for T3 (method.md section 9): Series, or per-ticker frame for EM bonds."""
    mb = _monthly_bench(inp)
    lv = {b: benchmark_monthly(b, mb) for b in ("IVW", "EFG_EEM_5050", "EMB", "EMLC", "GLD")}
    lv = {b: benchmark_level(r) for b, r in lv.items() if r is not None}
    if typ == "em_bond":
        rows = inp.universe.set_index("ticker")
        out = {}
        for t in tickers:
            b = "EMLC" if is_local_currency_bond(rows.loc[t]) else "EMB"
            if b in lv:
                out[t] = lv[b]
        return pd.DataFrame(out) if out else None
    b = {"us_growth_stock": "IVW", "intl_growth_stock": "EFG_EEM_5050", "other": "GLD"}[typ]
    return lv.get(b)


def _fx_at(fx, ccy, date):
    if ccy in (None, "USD") or not isinstance(ccy, str):
        return 1.0
    if ccy not in fx:
        return np.nan
    s = fx[ccy].loc[:pd.Timestamp(date)].dropna()
    return float(s.iloc[-1]) if len(s) else np.nan


def stock_fundamentals(inp, rows, as_of):
    """EDGAR point-in-time tables where a CIK file exists, else current yfinance statements (flagged)."""
    tables, splits, divs, fxr, fin, adr = {}, {}, {}, {}, [], []
    for _, r in rows.iterrows():
        t = r["ticker"]
        path = ed.edgar_path(inp.data_dir / "edgar", r.get("edgar_cik"))
        table = None
        if path is not None:
            cj = ed.read_companyfacts(path)
            if cj is not None:
                table = ed.point_in_time(ed.edgar_facts(cj), as_of)
                splits[t] = ed.split_events(cj)
                if table.empty:
                    table = None
        if table is None:
            table = ed.yfinance_table(inp.data_dir / "fundamentals" / t, r.get("currency"))
        tables[t] = table
        divs[t] = read_dividends(inp.data_dir / "fundamentals" / t / "dividends.csv")
        rep = table.attrs.get("currency") if table is not None else None
        if rep and isinstance(r.get("currency"), str) and rep != r["currency"]:
            date = as_of if table.attrs.get("point_in_time") else inp.fx.index[-1]
            fxr[t] = _fx_at(inp.fx, r["currency"], date) / _fx_at(inp.fx, rep, date)
        text = " ".join(str(r.get(c, "")) for c in ("category", "notes", "name")).lower().replace("yfinance", "")
        if FIN_WORDS.search(text):
            fin.append(t)
        if "ADR" in str(r.get("listing", "")).upper():
            adr.append(t)
    df = fundamental_score_stocks(tables, inp.prices_local, as_of, fin, splits, divs, fxr)
    if df.empty:
        return df
    for t in adr:
        if t in df.index:
            df.loc[t, "fund_flags"] = (df.loc[t, "fund_flags"] + "; ADR price: ADR ratio not applied").strip("; ")
    rep_ccy = {t: (tb.attrs.get("currency") if tb is not None else None) for t, tb in tables.items()}
    df["reporting_currency"] = pd.Series(rep_ccy)
    df["mcap_asof_usd_bn"] = [
        df.loc[t, "market_cap_local"] * _fx_at(inp.fx, rep_ccy.get(t) or "USD", as_of) / 1e9
        if df.loc[t, "fundamentals_pit"] and pd.notna(df.loc[t].get("market_cap_local", np.nan)) else np.nan
        for t in df.index]
    return df


def traded_value(inp, daily_usd, as_of, days=252):
    """Average daily traded value (USD millions) over the last `days` sessions to as_of."""
    if inp.volume is None:
        return None
    out = {}
    for t in daily_usd.columns:
        if t in inp.volume:
            v = (inp.volume[t] * daily_usd[t]).loc[:pd.Timestamp(as_of)].dropna().tail(days)
            out[t] = v.mean() / 1e6 if len(v) >= 120 else np.nan
    return pd.Series(out, dtype=float)


def run_hard(inp, typ, as_of):
    rows = _rows(inp, typ, roles=None)
    daily = usd_prices(inp.prices_local, inp.fx, rows)
    fund = stock_fundamentals(inp, rows, as_of) if typ.endswith("stock") else None
    hard = hard_screens(rows, daily, inp.funds, as_of, fund, traded_value(inp, daily, as_of),
                        fund["mcap_asof_usd_bn"] if fund is not None and len(fund) else None)
    cov = price_coverage(inp.prices_local, inp.fx, rows)
    hard["price_problem"] = hard["ticker"].map(cov)
    return hard, daily, fund


def _fund_table(inp, rows):
    t = rows.set_index("ticker")[["aum_usd_bn", "expense_ratio", "category"]].copy()
    for src in (inp.funds, inp.extra):
        if src is not None:
            src = src[~src.index.duplicated()]
            for c in src.columns:
                if c in t and c in ("aum_usd_bn", "expense_ratio"):
                    t[c] = pd.to_numeric(src[c], errors="coerce").reindex(t.index).combine_first(t[c])
                elif c not in t:
                    t[c] = src[c].reindex(t.index)
    return t


def _dedupe(text):
    """'a; b; a; ' -> 'a; b' (order kept)."""
    parts = [x.strip() for x in str(text).split(";") if x.strip() and x.strip() != "nan"]
    return "; ".join(dict.fromkeys(parts))


def _mean_corr(r, benches, as_of, min_months=36):
    """Mean correlation of r with each benchmark over months to as_of (36 minimum)."""
    cs = []
    for b in benches:
        both = pd.concat([r, b], axis=1).loc[:pd.Timestamp(as_of)].dropna()
        if len(both) >= min_months:
            cs.append(both.corr().iloc[0, 1])
    return float(np.mean(cs)) if cs else np.nan


def run_score(inp, typ, as_of, out_dir, rank_all=False):
    hard, daily, fund = run_hard(inp, typ, as_of)
    hard = hard.set_index("ticker")
    screened = hard.index[hard["role"].isin(SCREENED_ROLES)]
    ranked = list(screened if rank_all else hard.index[hard["passed"]])
    out = hard.copy()
    daily_in = daily.loc[:pd.Timestamp(as_of)]
    if typ.endswith("stock"):
        f = fund.drop(columns=[c for c in ("rev_cagr_3y", "fundamentals_pit", "mcap_asof_usd_bn")
                               if c in fund], errors="ignore")
        gcols = [c for c in f.columns if c.endswith("_score")]
        f = f.drop(columns=gcols)
        if ranked:
            f = f.join(group_score(fund.loc[[t for t in ranked if t in fund.index]], STOCK_GROUPS))
        out = out.join(f)
    else:
        rows = _rows(inp, typ, roles=None)
        mret = monthly_returns(daily_in)
        mb = _monthly_bench(inp)
        if typ == "em_bond":
            ft = _fund_table(inp, rows)
            if "corr_equity" not in ft:
                eq = [b for b in (benchmark_monthly("IVW", mb), benchmark_monthly("EFG_EEM_5050", mb))
                      if b is not None]
                ft["corr_equity"] = pd.Series({t: _mean_corr(mret[t], eq, as_of) if t in mret else np.nan
                                               for t in ft.index})
            if "local_currency" not in ft:
                urows = rows.set_index("ticker")
                ft["local_currency"] = [is_local_currency_bond(urows.loc[t]) for t in ft.index]
            sc = fundamental_score_bonds(ft.loc[[t for t in ranked if t in ft.index]]) if ranked else ft
        else:
            cpi = inp.yields["US_CPI"] if inp.yields is not None and "US_CPI" in inp.yields else None
            ft = _fund_table(inp, rows)
            cols = [t for t in ranked if t in mret]
            full = monthly_returns(daily)   # the function itself only scores months <= as_of
            sc = fundamental_score_other(full[cols], cpi, as_of, mb, ft) if cols else pd.DataFrame()
            if cpi is None:
                out["flags"] = out["flags"] + "; no US_CPI series: inflation beta not computed"
        sc = sc.drop(columns=[c for c in sc.columns if c in out.columns and c not in ("fund_flags",)],
                     errors="ignore")
        out = out.join(sc)
    # technical scores at as_of
    tick = [t for t in ranked if t in daily_in.columns]
    bench = type_benchmark(inp, typ, tick)
    sig_file = out_dir / f"{typ}_signals.csv"
    kept, tech_note = None, "signal validation not run: technical score uses all five signals"
    if sig_file.exists():
        v = pd.read_csv(sig_file, index_col=0)
        kept = [k for k in v.index if bool(v.loc[k, "kept"])]
        tech_note = f"kept signals from {sig_file.name}: {','.join(kept) or 'none'}"
    if tick:
        snap = signals_at(technical_signals(daily_in[tick], bench, as_of), as_of)
        ts, used = technical_score(snap, kept)
        pct = percentile_scores(snap, list(SIGNALS), HIGHER_IS_BETTER).add_suffix("_pct")
        out = out.join(snap).join(pct)
        out["technical_score"] = ts
    out["technical_note"] = tech_note
    if bench is None:
        out["flags"] = out["flags"] + "; type benchmark missing: T3 not computed"
    xc = usd_crosscheck(daily, inp.usd_listing, _rows(inp, typ, roles=None), as_of)
    out = out.join(xc.drop(columns=[c for c in xc.columns if c in out.columns]))
    out["flags"] = out["flags"].fillna("")
    if "fund_flags" in out:
        out["flags"] = out["flags"] + "; " + out["fund_flags"].fillna("")
        out = out.drop(columns="fund_flags")
    if not ranked:
        out["flags"] = out["flags"] + "; no row passed the hard screens: nothing ranked"
    out["flags"] = out["flags"].map(_dedupe)
    out["as_of"] = str(pd.Timestamp(as_of).date())
    sort = [c for c in ("passed", "fundamental_score") if c in out]
    return out.sort_values(sort, ascending=False).reset_index()


def run_validate(inp, typ, cost_bps=10.0, in_sample_end=IN_SAMPLE_END, tickers=None):
    rows = _rows(inp, typ)
    if tickers is not None:
        rows = rows[rows["ticker"].isin(tickers)]
    daily = usd_prices(inp.prices_local, inp.fx, rows)
    bench = type_benchmark(inp, typ, list(daily.columns))
    sig = technical_signals(daily, bench)
    res = validate_signals(sig, monthly_returns(daily), in_sample_end, cost_bps)
    res["long_list_size"] = len(daily.columns)
    res["benchmark_for_T3"] = "missing" if bench is None else ("EMB/EMLC" if typ == "em_bond" else
                                                                {"us_growth_stock": "IVW",
                                                                 "intl_growth_stock": "EFG_EEM_5050",
                                                                 "other": "GLD"}[typ])
    return res.reset_index()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m research.screen", description=__doc__)
    ap.add_argument("command", choices=["hard", "score", "validate"])
    ap.add_argument("--type", required=True, choices=list(SCREEN_TYPES))
    ap.add_argument("--as-of", default=IN_SAMPLE_END)
    ap.add_argument("--allow-oos", action="store_true", help="permit --as-of after 2017-12-31")
    ap.add_argument("--universe", default=None, help="universe CSV (default research/plan/universe.csv)")
    ap.add_argument("--out-dir", default=str(PLAN / "longlists"))
    ap.add_argument("--data-dir", default=str(DATA))
    ap.add_argument("--rank-all", action="store_true", help="score: rank hard-screen failures too")
    ap.add_argument("--passed-only", action="store_true", help="validate: only names passing hard screens")
    ap.add_argument("--cost-bps", type=float, default=10.0)
    a = ap.parse_args(argv)
    if a.command in ("hard", "score") and pd.Timestamp(a.as_of) > pd.Timestamp(IN_SAMPLE_END) \
            and not a.allow_oos:
        print(f"refused: --as-of {a.as_of} is after {IN_SAMPLE_END} (out of sample). "
              "Screens and scores use in-sample data only (method.md section 2); "
              "pass --allow-oos only for the forward thesis.", file=sys.stderr)
        return 2
    try:
        inp = Inputs(a.universe, a.type, data_dir=a.data_dir, inputs_dir=a.out_dir)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if a.command == "hard":
        df, _, _ = run_hard(inp, a.type, a.as_of)
        path = out_dir / f"{a.type}_hard.csv"
        summary = f"{int(df['passed'].sum())} of {len(df)} passed"
    elif a.command == "score":
        df = run_score(inp, a.type, a.as_of, out_dir, a.rank_all)
        path = out_dir / f"{a.type}_scored.csv"
        summary = f"{int(df['passed'].sum())} of {len(df)} passed and ranked"
    else:
        keep = None
        if a.passed_only:
            hp = out_dir / f"{a.type}_hard.csv"
            if not hp.exists():
                print(f"error: --passed-only needs {hp} (run `hard` first)", file=sys.stderr)
                return 2
            h = pd.read_csv(hp)
            keep = set(h.loc[h["passed"], "ticker"])
        df = run_validate(inp, a.type, a.cost_bps, tickers=keep)
        path = out_dir / f"{a.type}_signals.csv"
        summary = "kept: " + (", ".join(df.loc[df["kept"], "signal"]) or "none")
    df.to_csv(path, index=False)
    print(f"wrote {path} ({summary})")
    return 0
