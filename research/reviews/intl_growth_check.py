"""Adversarial review checks for the INTERNATIONAL GROWTH STOCK candidates.

Independent recomputation (does not import research.candidates.intl_growth):

    python -m research.reviews.intl_growth_check

Reads only data/research/*.csv, research/plan/universe.csv, the longlist
tables and the analyst's JSON outputs (to compare). Prints every check; writes
nothing. Conventions re-implemented from method.md s2/s9:
  - local adjusted closes via research.screen.read_wide_csv (spike filter on;
    a spikes=False sensitivity is printed too)
  - USD price = local x USD-per-unit FX, FX forward-filled onto price dates
  - calendar month-end last close, OOS 2018-01-31 .. 2026-10-31
  - Sharpe = mean(r - BIL)/std * sqrt(12); IR = mean(r - b)/std * sqrt(12)
  - benchmark = 0.5 EFG + 0.5 EEM monthly returns (monthly rebalanced)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sps

from research.screen.prices import read_wide_csv, read_dividends

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data" / "research"
OUT = ROOT / "reports" / "candidates"
OOS0, OOS1 = pd.Timestamp("2018-01-31"), pd.Timestamp("2026-10-31")
IS0, IS1 = pd.Timestamp("2010-01-31"), pd.Timestamp("2017-12-31")
CANDS = {"NOVO-B.CO": "DKK", "REA.AX": "AUD", "2330.TW": "TWD", "1299.HK": "HKD", "0700.HK": "HKD",
         "BAJFINANCE.NS": "INR", "000660.KS": "KRW", "CSU.TO": "CAD"}
HOME = {"REA.AX": "^AXJO", "2330.TW": "^TWII", "1299.HK": "^HSI", "0700.HK": "^HSI",
        "BAJFINANCE.NS": "^NSEI", "000660.KS": "^KS11", "CSU.TO": "^GSPTSE"}
RATE = {"USD": "US_3M", "DKK": "DK_3M", "AUD": "AU_3M", "INR": "IN_3M", "CAD": "CA_3M", "KRW": "KR_3M"}
# plausible USD-per-unit ranges 2018-2026 (if inverted, values would be e.g. 30 for TWD)
FX_RANGE = {"DKK": (0.12, 0.18), "AUD": (0.55, 0.85), "TWD": (0.028, 0.037), "HKD": (0.126, 0.130),
            "INR": (0.0100, 0.0160), "KRW": (0.00060, 0.00095), "CAD": (0.66, 0.85)}
COST = 0.0005


def cid(t):
    return t.replace(".", "_").replace("^", "_")


def month_end(daily):
    return daily.resample("ME").last()


def mret(daily):
    return month_end(daily).pct_change(fill_method=None)


def oos(s):
    return s[(s.index >= OOS0) & (s.index <= OOS1)]


def ins(s):
    return s[(s.index >= IS0) & (s.index <= IS1)]


def sharpe(r, rf):
    ex = (r - rf.reindex(r.index)).dropna()
    return float(ex.mean() / ex.std() * math.sqrt(12))


def ir(r, b):
    a = (r - b.reindex(r.index)).dropna()
    return float(a.mean() / a.std() * math.sqrt(12)), float(a.mean() / a.std() * math.sqrt(len(a)))


def cagr(r):
    r = r.dropna()
    return float((1 + r).prod() ** (12 / len(r)) - 1)


def maxdd(r, include_start=True):
    w = (1 + r.fillna(0)).cumprod()
    if include_start:
        w = pd.concat([pd.Series([1.0]), w.reset_index(drop=True)])
    return float((w / w.cummax() - 1).min())


def dsr(sh_ann, r, n_trials, sr_var=None):
    """Bailey-Lopez de Prado, monthly units, V = 1/(T-1) unless given."""
    T = len(r.dropna())
    sr = sh_ann / math.sqrt(12)
    v = 1 / (T - 1) if sr_var is None else sr_var
    g = 0.5772156649015329
    z = sps.norm.ppf
    sr0 = math.sqrt(v) * ((1 - g) * z(1 - 1 / n_trials) + g * z(1 - 1 / (n_trials * math.e)))
    sk, ku = float(sps.skew(r.dropna())), float(sps.kurtosis(r.dropna(), fisher=False))
    den = 1 - sk * sr + (ku - 1) / 4 * sr ** 2
    return float(sps.norm.cdf((sr - sr0) * math.sqrt(T - 1) / math.sqrt(den))), sr0 * math.sqrt(12)


def to_usd(p_local, fx_col):
    """local x USD-per-unit, FX forward-filled onto price dates (never backward)."""
    p = p_local.dropna()
    rate = fx_col.dropna().reindex(fx_col.dropna().index.union(p.index)).ffill().reindex(p.index)
    return p * rate


def short_rate_m(yields, col):
    """Monthly rate/12 applied to month m = observation of month m-1 (known at start of m)."""
    s = yields[col].dropna() / 100
    s.index = s.index + pd.offsets.MonthEnd(0)
    s = s.groupby(level=0).last()
    grid = pd.date_range("2009-12-31", OOS1, freq="ME")
    return (s.reindex(grid).ffill(limit=3) / 12).shift(1)


def load(spikes=True):
    universe = pd.read_csv(ROOT / "research/plan/universe.csv", dtype=str)
    table = pd.read_csv(ROOT / "research/plan/longlists/intl_growth_stock_insample_table.csv")
    passed = table["ticker"].tolist()
    need = set(passed) | set(CANDS) | set(HOME.values()) | {"^STOXX50E", "EFG", "EEM", "ACWX", "BIL",
                                                            "EWT", "EWA", "EWC", "INDA"}
    px = read_wide_csv(D / "prices.csv", spikes=spikes, columns=need)
    fx = read_wide_csv(D / "fx.csv", spikes=spikes)
    adr = read_wide_csv(D / "prices_usd_listing.csv", spikes=spikes)
    y = pd.read_csv(D / "yields.csv", index_col=0, parse_dates=True).sort_index()
    return universe, table, passed, px, fx, adr, y


def drawdown_dates(r):
    w = (1 + r.fillna(0)).cumprod()
    dd = w / w.cummax() - 1
    trough = dd.idxmin()
    peak = w.loc[:trough].idxmax()
    return str(peak.date())[:7], str(trough.date())[:7], float(dd.min()), float(dd.iloc[-1])


def mid_cycle_sensitivity():
    """Re-run the analyst's own forward pipeline for SK Hynix with other mid-cycle fractions
    (monkeypatched in memory only; no file is written)."""
    from research.candidates import assumptions_intl_growth as A
    from research.candidates import intl_growth as IG
    inp = IG.Inputs()
    loc, usd, fx = inp.series("000660.KS")
    u_full = IG.windows(usd, IG.IS_START, inp.last_month)
    orig = dict(A.CYCLICAL_MID_CYCLE)
    out = {}
    try:
        for mid in (0.5, 0.35, 0.25):
            A.CYCLICAL_MID_CYCLE["000660_KS"] = mid
            e = IG.expected_returns(inp, "000660.KS", u_full)
            out[mid] = (e["consensus_usd"], e["methods"]["dcf"], e["methods"]["grinold_kroner"])
    finally:
        A.CYCLICAL_MID_CYCLE.clear()
        A.CYCLICAL_MID_CYCLE.update(orig)
    return out


def main():
    universe, table, passed, px, fx, adr, y = load()
    ucur = universe.set_index("ticker")["currency"].to_dict()
    print("last price date", px.index.max().date(), "| last fx date", fx.index.max().date())

    # ---------------------------------------------------------------- 1. FX direction
    print("\n== 1a. FX direction (fx.csv = USD per 1 unit?) ==")
    for c, (lo, hi) in FX_RANGE.items():
        s = oos(fx[c].dropna())
        ok = lo <= s.min() and s.max() <= hi
        print(f"{c}: OOS min {s.min():.6g} max {s.max():.6g} last {fx[c].dropna().iloc[-1]:.6g} "
              f"(1 USD = {1 / fx[c].dropna().iloc[-1]:.4g} {c}) -> {'USD per unit OK' if ok else 'CHECK'}")
    # ADR level parity confirms direction AND that conversion is multiplication
    for t, a, k in (("2330.TW", "TSM", 5), ("NOVO-B.CO", "NVO", 1), ("0700.HK", "TCEHY", 1), ("1299.HK", "AAGIY", 4)):
        u = to_usd(px[t], fx[CANDS[t]])
        ratio = (adr[a] / (k * u)).dropna()
        print(f"{a}/({k} x {t} in USD): 2018-01 {ratio.loc['2018-01'].mean():.3f}, last {ratio.iloc[-1]:.3f} "
              f"(near 1 => direction and multiplication correct)")

    # ---------------------------------------------------------------- 1b. USD metrics
    usd_m = {}
    for t in set(passed) | set(CANDS):
        c = ucur.get(t, "USD")
        p = px[t] if t in px else None
        if p is None or p.dropna().empty:
            continue
        usd_m[t] = mret(p.dropna() if c == "USD" else to_usd(p, fx[c]))
    bil = oos(mret(px["BIL"].dropna()))
    efg, eem = mret(px["EFG"].dropna()), mret(px["EEM"].dropna())
    bench = (0.5 * efg + 0.5 * eem)
    bo = oos(bench)
    print("\n== 1b/5. Benchmark 50/50 EFG+EEM (monthly rebalanced) OOS ==")
    print(f"months {bo.count()}  Sharpe {sharpe(bo, bil):.3f}  CAGR {cagr(bo):.4f}  maxDD {maxdd(bo):.4f} "
          f"(analyst 0.27 / 5.8% / -33%)")
    acwx = oos(mret(px["ACWX"].dropna()))
    print(f"ACWX OOS Sharpe {sharpe(acwx, bil):.3f} CAGR {cagr(acwx):.4f} maxDD {maxdd(acwx):.4f}")

    print("\n== 1c. Candidates, OOS USD (independent) vs analyst JSON ==")
    rows = {}
    for t in CANDS:
        r = oos(usd_m[t])
        sh, (i, ti) = sharpe(r, bil), ir(r, bo)
        dd, dd_nostart = maxdd(r), maxdd(r, False)
        js = json.load(open(OUT / f"{cid(t)}.json"))["metrics"]["out_of_sample"]["usd"]
        d, _ = dsr(sh, r, 31)
        rows[t] = dict(sharpe=sh, ir=i, t_ir=ti, maxdd=dd, cagr=cagr(r), vol=r.std() * math.sqrt(12), dsr=d)
        print(f"{t:14s} n {r.count()} Sharpe {sh:.3f} ({js['sharpe']:.3f})  IR {i:.3f} ({js['info_ratio']:.3f}) "
              f"t {ti:.2f} ({js['t_stat_ir']:.2f})  maxDD {dd:.3f} [no-start {dd_nostart:.3f}] ({js['max_drawdown']:.3f}) "
              f"CAGR {cagr(r):.4f} ({js['cagr']:.4f}) vol {r.std()*math.sqrt(12):.3f}  DSR {d:.3f} ({js['deflated_sharpe']:.3f})")
    print("drawdown peak -> trough (USD, OOS):")
    for t in CANDS:
        pk, tr, d_, now = drawdown_dates(oos(usd_m[t]))
        print(f"  {t:14s} {pk} -> {tr} {d_:.3f}; drawdown at 2026-10 {now:.3f}")
    # spike-filter sensitivity
    _, _, _, px2, fx2, _, _ = load(spikes=False)
    print("spikes=False sensitivity (OOS Sharpe / IR):")
    bo2 = oos(0.5 * mret(px2["EFG"].dropna()) + 0.5 * mret(px2["EEM"].dropna()))
    bil2 = oos(mret(px2["BIL"].dropna()))
    for t in CANDS:
        r2 = oos(mret(to_usd(px2[t], fx2[CANDS[t]])))
        print(f"  {t:14s} {sharpe(r2, bil2):.3f} / {ir(r2, bo2)[0]:.3f}")

    # ---------------------------------------------------------------- TSMC vs ADR
    print("\n== 1d. TSMC local-in-USD vs TSM ADR ==")
    u = to_usd(px["2330.TW"], fx["TWD"])
    a = adr["TSM"]
    ra, rb = oos(mret(u)), oos(mret(a.dropna()))
    both = pd.concat([ra, rb], axis=1).dropna()
    gap_mean = (both.iloc[:, 0] - both.iloc[:, 1]).mean() * 12
    gap_cagr = cagr(both.iloc[:, 0]) - cagr(both.iloc[:, 1])
    prem = (month_end(a) / (5 * month_end(u))).dropna()
    p0, p1 = prem.loc[:"2017-12-31"].iloc[-1], prem.loc[:OOS1].iloc[-1]
    yrs = len(both) / 12
    print(f"OOS corr {both.corr().iloc[0, 1]:.3f}; mean gap {gap_mean:+.4f}/yr; CAGR gap {gap_cagr:+.4f}/yr")
    print(f"ADR premium (TSM / 5 shares in USD) 2017-12 {p0:.3f} -> 2026-10 {p1:.3f}: "
          f"{(p1 / p0) ** (1 / yrs) - 1:+.4f}/yr of the ADR's outperformance is premium expansion")

    # ---------------------------------------------------------------- 6. dividends in 2330.TW adj close
    print("\n== 6. Dividend adjustment of 2330.TW adjusted close ==")
    dv = read_dividends(D / "fundamentals" / "2330.TW" / "dividends.csv")
    p, ix = px["2330.TW"].dropna(), px["^TWII"].dropna()
    ratios = []
    for e, div in dv.items():
        if e < pd.Timestamp("2012-01-01") or e not in p.index:
            continue
        prev = p.index[p.index < e][-1]
        dy = div / p.loc[prev]
        rs = p.loc[e] / p.loc[prev] - 1
        ri = ix.reindex([prev, e])
        if ri.isna().any():
            continue
        ratios.append(((rs - (ri.iloc[1] / ri.iloc[0] - 1)) / dy))
    ratios = np.array(ratios)
    print(f"{len(ratios)} ex-dates since 2012: mean (r_2330 - r_TWII)/(div/P) on ex-date = {ratios.mean():+.2f}, "
          f"median {np.median(ratios):+.2f} (about -0.6 if the adj close ignored dividends, about +0.3..0 if adjusted; "
          f"TWII is a price index ~30-40% TSMC)")
    ttm = dv[dv.index > dv.index[-1] - pd.Timedelta(days=365)].sum() / p.iloc[-1]
    print(f"trailing 12m dividend yield at last price {ttm:.4f}")

    # ---------------------------------------------------------------- 2. currency block
    print("\n== 2. Currency decomposition and CIP hedge ==")
    us = short_rate_m(y, "US_3M")
    for t in CANDS:
        c = CANDS[t]
        loc = oos(mret(px[t].dropna()))
        usd = oos(usd_m[t])
        f = (1 + usd) / (1 + loc) - 1
        fxonly = oos(mret(fx[c].dropna().reindex(px[t].dropna().index, method=None).dropna())) \
            if False else None
        if c == "TWD":
            lr = pd.Series(0.018 / 12, index=us.index)
        elif c == "HKD":
            lr = us
        else:
            lr = short_rate_m(y, RATE[c])
        df = pd.concat({"l": loc, "u": usd, "f": f, "us": us, "lr": lr}, axis=1).dropna()
        fp = (1 + df["us"]) / (1 + df["lr"]) - 1
        h = df["u"] + fp - df["f"] - COST
        ident = ((1 + df["l"]) * (1 + df["f"]) - (1 + df["u"])).abs().max()
        js = json.load(open(OUT / f"{cid(t)}.json"))["currency"]
        hc = 12 * (COST - fp).mean()
        line = (f"{t:14s} n {len(df)} local {cagr(df['l']):+.4f} fx {cagr(df['f']):+.4f} ({js['fx_return']:+.4f}) "
                f"usd {cagr(df['u']):+.4f} | identity max err {ident:.1e} | hedge_cost {hc:+.4f} ({js['hedge_cost']:+.4f}) "
                f"hedged-unhedged {cagr(h) - cagr(df['u']):+.4f} ({js['hedged_minus_unhedged']:+.4f}) "
                f"| arith: -mean(f) {-12*df['f'].mean():+.4f}, carry {-hc:+.4f}, var drag saved "
                f"{0.5*12*(df['u'].var()-h.var()):+.4f}")
        print(line)
        if c == "TWD":
            for alt in (0.005, 0.010):
                fp2 = (1 + df["us"]) / (1 + alt / 12) - 1
                h2 = df["u"] + fp2 - df["f"] - COST
                print(f"   TWD sensitivity: flat {alt:.1%} instead of 1.8% -> hedged-unhedged "
                      f"{cagr(h2) - cagr(df['u']):+.4f}, hedge_cost {12*(COST-fp2).mean():+.4f}")
        if c == "INR":
            # UIP check: the forward priced in a rupee fall of about the rate gap; realized vs priced
            print(f"   INR: forward-implied depreciation {12*fp.mean():+.4f}/yr vs realized fx {cagr(df['f']):+.4f}/yr "
                  f"-> hedge won only because the rupee fell {(-cagr(df['f']) + 12*fp.mean()):.4f}/yr more than priced")
    print("US_3M OOS mean", round(12 * oos(us).mean(), 4), "| short-rate columns for TW/HK in yields.csv:",
          [c for c in y.columns if c.startswith(("TW_", "HK_"))])

    # ---------------------------------------------------------------- 3. local block, price-index caveat
    print("\n== 3. Price-index caveat: home price index in USD vs total-return ETF (OOS, gap ~ div yield + fee) ==")
    for ix_t, c, etf in (("^TWII", "TWD", "EWT"), ("^AXJO", "AUD", "EWA"), ("^GSPTSE", "CAD", "EWC"), ("^NSEI", "INR", "INDA")):
        ri = oos(mret(to_usd(px[ix_t], fx[c])))
        re = oos(mret(px[etf].dropna()))
        bb = pd.concat([ri, re], axis=1).dropna()
        print(f"{ix_t} in USD CAGR {cagr(bb.iloc[:,0]):+.4f} vs {etf} {cagr(bb.iloc[:,1]):+.4f}: gap "
              f"{cagr(bb.iloc[:,1]) - cagr(bb.iloc[:,0]):+.4f}/yr (n {len(bb)})")
    # TSMC local IR with TWII grossed up by the EWT gap
    loc = oos(mret(px["2330.TW"].dropna()))
    hi = oos(mret(px["^TWII"].dropna()))
    ri = oos(mret(to_usd(px["^TWII"], fx["TWD"])))
    gap = cagr(oos(mret(px["EWT"].dropna()))) - cagr(ri)
    print(f"TSMC local IR vs ^TWII {ir(loc, hi)[0]:.3f}; vs ^TWII + {gap:.2%}/12 per month {ir(loc, hi + gap / 12)[0]:.3f}; "
          f"local Sharpe vs flat 1.8% {sharpe(loc, pd.Series(0.018/12, index=loc.index)):.3f}")
    nv = oos(mret(px["NOVO-B.CO"].dropna()))
    sx = px["^STOXX50E"].dropna()
    dkp = oos(mret(sx * (fx["EUR"] / fx["DKK"]).reindex(fx.index.union(sx.index)).ffill().reindex(sx.index)))
    bb = pd.concat([nv, dkp], axis=1).dropna()
    print(f"Novo vs Euro Stoxx 50 in DKK: corr {bb.corr().iloc[0,1]:.3f}, beta "
          f"{np.cov(bb.iloc[:,0], bb.iloc[:,1])[0,1]/bb.iloc[:,1].var():.3f}")

    # ---------------------------------------------------------------- 7. control table, multiple testing
    print("\n== 4/7. Control group: 31 hard-screen passers ==")
    ctl = []
    for t in passed:
        if t not in usd_m:
            continue
        r = oos(usd_m[t])
        if r.count() < 24:
            continue
        ctl.append(dict(ticker=t, sharpe_oos=sharpe(r, bil), ir_oos=ir(r, bo)[0], t_ir=ir(r, bo)[1]))
    ctl = pd.DataFrame(ctl).set_index("ticker").join(table.set_index("ticker")[["rank", "composite", "sharpe_is", "ir_is",
                                                                              "fundamental_score", "fundamentals_pit", "role"]])
    rho, pv = sps.spearmanr(ctl["composite"], ctl["sharpe_oos"])
    rho2, pv2 = sps.spearmanr(ctl["sharpe_is"], ctl["sharpe_oos"])
    print(f"n {len(ctl)}; Spearman(composite, OOS Sharpe) {rho:.3f} (p {pv:.2f}); (IS Sharpe, OOS Sharpe) {rho2:.3f} (p {pv2:.2f})")
    ctl["oos_rank"] = ctl["sharpe_oos"].rank(ascending=False, method="min")
    print(ctl.sort_values("sharpe_oos", ascending=False)[["rank", "oos_rank", "sharpe_oos", "ir_oos", "t_ir", "role",
                                                         "fundamentals_pit"]].round(3).to_string())
    v_meas = float(np.var(ctl["sharpe_oos"] / math.sqrt(12), ddof=1))
    r = oos(usd_m["2330.TW"])
    print(f"cross-sectional var of monthly OOS Sharpes {v_meas:.5f} vs 1/(T-1) {1/(r.count()-1):.5f}")
    for t in ("2330.TW", "000660.KS", "CSU.TO", "BAJFINANCE.NS"):
        rr = oos(usd_m[t])
        d1, sr0 = dsr(rows[t]["sharpe"], rr, 31)
        d2, sr0b = dsr(rows[t]["sharpe"], rr, 31, v_meas)
        print(f"  {t}: DSR (V=1/(T-1)) {d1:.3f} [E max SR {sr0:.2f} ann]; DSR (V measured) {d2:.3f} [E max SR {sr0b:.2f}]")
    # Bonferroni-style: t needed for 31 trials, one-sided 5%
    print(f"t needed at 5% one-sided with 31 trials (Bonferroni): {sps.norm.ppf(1 - 0.05 / 31):.2f}")

    # look-ahead in the in-sample composite (fundamental score from current statements)
    print("\n== 4b. In-sample composite look-ahead: fundamentals_pit False for shortlisted names ==")
    tb = table.copy()
    print("shortlisted top-8 pit flags:", tb.head(8)[["ticker", "fundamentals_pit"]].values.tolist())
    print("pit share: candidates", round(tb[tb.role == "candidate"]["fundamentals_pit"].mean(), 2),
          "faded leaders", round(tb[tb.role == "faded_leader"]["fundamentals_pit"].mean(), 2))
    pct = lambda s: s.rank(pct=True)
    tb["comp_price_only"] = 0.5 * pct(tb["sharpe_is"]) + 0.5 * pct(tb["ir_is"])
    tb["rank_price_only"] = tb["comp_price_only"].rank(ascending=False, method="min")
    print(tb.sort_values("rank_price_only")[["ticker", "rank", "rank_price_only", "sharpe_is", "ir_is",
                                              "fundamental_score"]].head(12).round(3).to_string(index=False))
    print("000660.KS price-only rank:", int(tb.set_index("ticker").loc["000660.KS", "rank_price_only"]))

    # ---------------------------------------------------------------- 9. drop rule 8.2
    print("\n== 9. Drop rule 8.2 (Sharpe < benchmark AND IR < 0) ==")
    bsh = sharpe(bo, bil)
    for t, m in rows.items():
        print(f"{t:14s} Sharpe {m['sharpe']:.3f} vs {bsh:.3f}, IR {m['ir']:+.4f} -> "
              f"{'TRIGGERED' if (m['sharpe'] < bsh and m['ir'] < 0) else 'not triggered'}")

    # ---------------------------------------------------------------- 8. forward-model fragility
    print("\n== 8. Forward models ==")
    for t in CANDS:
        e = json.load(open(OUT / f"{cid(t)}.json"))["expected_return_7y"]
        m = {k: v for k, v in e["methods"].items() if k not in ("monte_carlo_median", "yield") and v is not None}
        print(f"{t:14s} consensus {e['consensus_usd']:.4f} from {len(m)} votes {dict((k, round(v, 4)) for k, v in m.items())}"
              f"; fwd P/E {e['gk_detail']['forward_pe']:.2f} -> target {e['gk_detail']['target_pe']}, "
              f"repricing {e['gk_detail']['repricing']:+.4f}; dcf wacc "
              f"{(e['dcf_detail'] or {}).get('wacc')}")
    g = json.load(open(OUT / "000660_KS.json"))["expected_return_7y"]["gk_detail"]
    base = g["dividend_yield"] + g["inflation"] + g["real_growth"] - g["net_dilution"]
    for pe in (2.73, 4.0, 5.5, 8.0):
        rp = (9.0 / pe) ** 0.1 - 1
        print(f"  SK Hynix G-K if forward P/E were {pe}: {base + rp:+.4f} local (analyst {g['repricing'] + base:+.4f})")
    info = json.load(open(D / "fundamentals" / "000660.KS" / "info.json"))
    print("  000660.KS info.json forwardPE", info.get("forwardPE"), "forwardEps", info.get("forwardEps"),
          "trailingPE", info.get("trailingPE"), "-> implied forward earnings (KRW tn)",
          round(info["marketCap"] / info["forwardPE"] / 1e12, 1))
    est = pd.read_csv(D / "fundamentals" / "000660.KS" / "earnings_estimate.csv").set_index("period")
    inc = pd.read_csv(D / "fundamentals" / "000660.KS" / "income_stmt.csv", index_col=0)
    eps25 = float(inc.loc["Diluted EPS"].iloc[0])
    print(f"  price {info['currentPrice']:,.0f} / +1y EPS {est.loc['+1y','avg']:,.0f} = {info['currentPrice']/est.loc['+1y','avg']:.2f}"
          f" (FY2027 consensus, {int(est.loc['+1y','numberOfAnalysts'])} analysts); FY2025 diluted EPS {eps25:,.0f} -> "
          f"forward EPS = {est.loc['+1y','avg']/eps25:.1f}x FY2025; 50% mid-cycle = {0.5*est.loc['+1y','avg']/eps25:.1f}x FY2025")
    print("  re-running the analyst's pipeline with other mid-cycle fractions (consensus, dcf, gk):")
    for mid, v in mid_cycle_sensitivity().items():
        print(f"    mid_cycle {mid}: consensus {v[0]:.4f}, dcf {v[1]}, gk {v[2]:.4f}")

    # ---------------------------------------------------------------- 10. memos and JSON integrity
    print("\n== 4c/10. No post-hoc substitution; memo 'explain' sentences match JSON ==")
    ids = sorted(p_.stem for p_ in (ROOT / "research/candidates/memos").glob("*.md"))
    print("memo IDs:", ids)
    print("deep-research set == in-sample top 8:", sorted(cid(t) for t in table.head(8)["ticker"]) == sorted(cid(t) for t in CANDS))
    for t in CANDS:
        js = json.load(open(OUT / f"{cid(t)}.json"))
        memo = (ROOT / "research/candidates/memos" / f"{cid(t)}.md").read_text(encoding="utf-8")
        ok = all(x in memo for x in js["explain"])
        print(f"  {t:14s} explain sentences in memo verbatim: {ok}; drop_rule_2 {js['drop_rule_2']['triggered']}; "
              f"rubric total {js['rubric']['total']}")


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    main()
