"""Download everything the research models need into data/research/.

    python -m research.fetch                                   # legacy: config.STOCKS set
    python -m research.fetch --universe research/plan/universe.csv [--refresh]
                             [--only prices fx rates cboe fundamentals edgar funds]

Needs open access to Yahoo Finance, OECD, SEC EDGAR, CBOE, Treasury.gov, the
World Bank and (optionally) fred.stlouisfed.org; run it on a home PC and commit
or share the CSVs. Writes under data/research/:
    prices.csv, prices_usd_listing.csv   daily adjusted close, local currency
    fx.csv                               daily USD per 1 unit, one column per currency
    yields.csv                           monthly percent (OECD, FRED, Treasury)
    cpi_annual.csv                       World Bank annual CPI inflation
    cboe/<IDX>.csv                       CBOE option-strategy index histories
    fundamentals/<TICKER>/               yfinance statements and estimates
    edgar/CIK##########.json             SEC companyfacts
    funds.csv                            fund facts from yfinance info
    fetch_log.txt                        what succeeded, what failed, coverage
Existing files are extended, never replaced; existing columns are only
re-downloaded with --refresh. Nothing is interpolated: prices and FX are only
forward-filled across holidays.
"""

import argparse
import datetime as dt
import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

from . import config

DATA = Path(__file__).resolve().parent.parent / "data" / "research"
START = "2005-01-01"
CHUNK = 50
EDGAR_UA = "UMassBoston-622-portfolio-project maloneyj98@gmail.com"
HTTP_UA = "Mozilla/5.0 (research fetcher; UMassBoston-622-portfolio-project)"
STEPS = ("prices", "fx", "rates", "cboe", "fundamentals", "edgar", "funds", "volumes")
STOCK_TYPES = ("us_growth_stock", "intl_growth_stock")
FUND_TYPES = ("em_bond", "other", "benchmark", "rf", "overlay")
CBOE_INDICES = ("BXM", "BXMD", "PUT", "PPUT", "CLL")

# FRED series fetched when not already in yields.csv: column name -> series id.
FRED_NEW = {
    "US_2Y": "DGS2",
    "US_REAL10": "DFII10",
    "US_BE10": "T10YIE",
    "USD_BROAD": "DTWEXBGS",
    "EM_CORP_OAS": "BAMLEMCBPIOAS",
    "EM_HY_OAS": "BAMLEMHBHYCRPIOAS",
    "EM_CORP_TRI": "BAMLEMCBPITRIV",
}

ISO3_TO_ISO2 = {
    "ARG": "AR", "AUS": "AU", "AUT": "AT", "BEL": "BE", "BGR": "BG", "BRA": "BR", "CAN": "CA",
    "CHE": "CH", "CHL": "CL", "CHN": "CN", "COL": "CO", "CRI": "CR", "CZE": "CZ", "DEU": "DE",
    "DNK": "DK", "EA20": "EA", "EA19": "EA", "ESP": "ES", "EST": "EE", "FIN": "FI", "FRA": "FR",
    "GBR": "GB", "GRC": "GR", "HRV": "HR", "HUN": "HU", "IDN": "ID", "IND": "IN", "IRL": "IE",
    "ISL": "IS", "ISR": "IL", "ITA": "IT", "JPN": "JP", "KOR": "KR", "LTU": "LT", "LUX": "LU",
    "LVA": "LV", "MEX": "MX", "NLD": "NL", "NOR": "NO", "NZL": "NZ", "POL": "PL", "PRT": "PT",
    "ROU": "RO", "RUS": "RU", "SAU": "SA", "SVK": "SK", "SVN": "SI", "SWE": "SE", "TUR": "TR",
    "USA": "US", "ZAF": "ZA", "HKG": "HK", "SGP": "SG", "THA": "TH", "MYS": "MY", "PHL": "PH",
    "TWN": "TW", "PER": "PE", "EU27_2020": "EU27",
}
OECD_BASE = "https://sdmx.oecd.org/public/rest/data/"
OECD_Q = {
    "10Y": OECD_BASE + "OECD.SDD.STES,DSD_STES@DF_FINMARK,/.M.IRLT.PA.....?startPeriod=2005-01"
                       "&dimensionAtObservation=AllDimensions&format=csvfile",
    "3M": OECD_BASE + "OECD.SDD.STES,DSD_STES@DF_FINMARK,/.M.IR3TIB.PA.....?startPeriod=2005-01"
                      "&dimensionAtObservation=AllDimensions&format=csvfile",
    "CPIYOY": OECD_BASE + "OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,/.M.N.CPI.PA._T.N.GY?startPeriod=2005-01"
                          "&dimensionAtObservation=AllDimensions&format=csvfile",
}


class Log:
    """Append-only log that flushes every line so a long run can be polled."""

    def __init__(self, path=None, mode="w"):
        self.lines = []
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.fh = open(self.path, mode, encoding="utf-8")
        else:
            self.fh = None

    def append(self, line):
        self.lines.append(line)
        if self.fh:
            self.fh.write(line + "\n")
            self.fh.flush()

    def close(self):
        if self.fh:
            self.fh.close()


# --------------------------------------------------------------------------
# Pure helpers (unit-tested, no network)
# --------------------------------------------------------------------------
def read_universe(path):
    u = pd.read_csv(path, dtype=str, keep_default_na=False)
    for c in ("ticker", "type", "role", "currency", "usd_ticker", "edgar_cik", "category"):
        if c not in u.columns:
            u[c] = ""
    u["ticker"] = u["ticker"].str.strip()
    return u


def fetch_list(uni, step):
    """Items a step fetches from the universe (ordered, de-duplicated)."""
    if step == "prices":
        return list(dict.fromkeys(uni.loc[uni.type != "fx", "ticker"]))
    if step == "prices_usd":
        m = (uni.usd_ticker != "") & (uni.usd_ticker != uni.ticker) & (uni.type != "fx")
        return list(dict.fromkeys(uni.loc[m, "usd_ticker"]))
    if step == "fx":
        return list(dict.fromkeys(uni.loc[uni.type == "fx", "ticker"]))
    if step == "fundamentals":
        return list(dict.fromkeys(uni.loc[uni.type.isin(STOCK_TYPES), "ticker"]))
    if step == "funds":
        return list(dict.fromkeys(uni.loc[uni.type.isin(FUND_TYPES), "ticker"]))
    if step == "edgar":
        ciks = uni.loc[uni.edgar_cik.str.strip() != "", "edgar_cik"].str.strip()
        return list(dict.fromkeys(c.zfill(10) for c in ciks))
    raise ValueError(step)


def merge_columns(existing, new, refresh=False):
    """Add new columns to an existing wide frame; existing columns survive
    untouched unless refresh=True, in which case the same-named new columns replace them."""
    if existing is None or existing.empty:
        return new.sort_index()
    out = existing.copy()
    idx = out.index.union(new.index)
    out = out.reindex(idx)
    for c in new.columns:
        if c in out.columns and not refresh:
            continue
        out[c] = new[c].reindex(idx)
    return out.sort_index()


def fx_to_usd_per_unit(close, fx_rows):
    """close: Yahoo FX closes by Yahoo ticker. fx_rows: universe rows with type=fx.
    fx_direct tickers are already USD per unit; fx_inverse are foreign per USD."""
    out = {}
    for _, r in fx_rows.iterrows():
        t = r["ticker"]
        if t not in close:
            continue
        s = close[t].astype(float)
        s = s.where(s > 0)
        out[r["currency"]] = s if r.get("category") == "fx_direct" else 1.0 / s
    return pd.DataFrame(out, index=close.index)


def parse_oecd_csv(text, suffix):
    """OECD SDMX csvfile -> wide frame, month-start index, columns <ISO2>_<suffix>."""
    df = pd.read_csv(io.StringIO(text), usecols=["REF_AREA", "TIME_PERIOD", "OBS_VALUE"])
    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["OBS_VALUE"])
    df["col"] = df["REF_AREA"].map(lambda a: ISO3_TO_ISO2.get(a, a)) + "_" + suffix
    df["date"] = pd.to_datetime(df["TIME_PERIOD"] + "-01", errors="coerce")
    df = df.dropna(subset=["date"]).drop_duplicates(["col", "date"], keep="last")
    return df.pivot(index="date", columns="col", values="OBS_VALUE").sort_index()


def parse_cboe_csv(text):
    """CBOE <IDX>_History.csv -> Series named 'value' with a date index."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip().upper().startswith("DATE")), None)
    if start is None:
        raise ValueError("no DATE header")
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    d = pd.to_datetime(df.iloc[:, 0], format="mixed", errors="coerce")
    v = pd.to_numeric(df.iloc[:, -1], errors="coerce")  # close/level is the last column
    s = pd.Series(v.values, index=d, name="value").dropna()
    s = s[~s.index.isna()]
    s.index.name = "date"
    return s.sort_index()


def parse_worldbank(payload):
    """World Bank JSON (page list) -> frame year x ISO2."""
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 and payload[1] else []
    recs = [(r["countryiso3code"], r["country"]["id"], int(r["date"]), r["value"]) for r in rows
            if r.get("value") is not None]
    df = pd.DataFrame(recs, columns=["iso3", "iso2", "year", "value"])
    if df.empty:
        return pd.DataFrame()
    return df.pivot(index="year", columns="iso2", values="value").sort_index()


def to_monthly_start(s):
    """Daily or monthly series -> last value per month, labelled at month start."""
    return s.dropna().resample("MS").last().dropna()


def _read_wide(path):
    if not Path(path).exists():
        return None
    return pd.read_csv(path, index_col=0, parse_dates=True).sort_index()


# --------------------------------------------------------------------------
# Network helpers
# --------------------------------------------------------------------------
def http_get(url, timeout=30, headers=None, retries=0, backoff=2.0):
    h = {"User-Agent": HTTP_UA}
    h.update(headers or {})
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
        except Exception as e:
            last = e
        time.sleep(backoff * (attempt + 1))
    raise last


def _download_close(tickers, field="Close"):
    import yfinance as yf

    raw = yf.download(list(tickers), start=START, auto_adjust=True, progress=False, threads=True)
    if raw is None or len(raw) == 0:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw[field]
    else:
        close = raw[[field]].rename(columns={field: list(tickers)[0]})
    close = close.sort_index()
    close.index = pd.to_datetime(close.index).tz_localize(None) if close.index.tz is not None else close.index
    close.index.name = "Date"
    return close


def _close(tickers):  # kept for backwards compatibility
    return _download_close(tickers)


def _download_chunks(tickers, log, label, field="Close"):
    frames = []
    for i in range(0, len(tickers), CHUNK):
        chunk = tickers[i:i + CHUNK]
        try:
            c = _download_close(chunk, field)
        except Exception as e:
            log.append(f"{label} chunk {i // CHUNK + 1}: FAILED {type(e).__name__}: {e}")
            c = pd.DataFrame()
        frames.append(c)
        log.append(f"{label} chunk {i // CHUNK + 1}: {len(chunk)} requested, {c.shape[1]} columns returned")
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, axis=1).sort_index() if frames else pd.DataFrame()


def _log_price_stats(close, tickers, log, label):
    for t in tickers:
        s = close[t].dropna() if t in close else pd.Series(dtype=float)
        if s.empty:
            log.append(f"{label} {t}: NO DATA")
        else:
            flag = "  SHORT (<60 rows)" if len(s) < 60 else ""
            log.append(f"{label} {t}: {len(s)} rows, {s.index[0].date()} to {s.index[-1].date()}{flag}")


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------
def _fetch_price_file(tickers, path, log, label, refresh):
    existing = _read_wide(path)
    have = set(existing.columns) if existing is not None else set()
    todo = [t for t in tickers if refresh or t not in have]
    skipped = [t for t in tickers if t not in todo]
    log.append(f"{label}: {len(tickers)} in universe, {len(skipped)} already on disk, {len(todo)} to fetch")
    new = _download_chunks(todo, log, label) if todo else pd.DataFrame()
    _log_price_stats(new, todo, log, label)
    # note on-disk tickers so the summary can see them
    merged = merge_columns(existing, new, refresh=refresh)
    if not merged.empty:
        merged.index.name = "Date"
        merged.to_csv(path)
    return merged


def fetch_prices(log, uni=None, refresh=False):
    if uni is None:  # legacy: the config.STOCKS set
        tickers = sorted({s.ticker for s in config.STOCKS} | set(config.EXTRA_PRICE_TICKERS))
        return _fetch_price_file(tickers, DATA / "prices.csv", log, "price", True)
    _fetch_price_file(fetch_list(uni, "prices"), DATA / "prices.csv", log, "price", refresh)
    usd = fetch_list(uni, "prices_usd")
    if usd:
        _fetch_price_file(usd, DATA / "prices_usd_listing.csv", log, "price_usd", refresh)


def fetch_volumes(log, uni=None, refresh=False):
    """Daily share volume (separate pass; same tickers and layout as the price files)."""
    if uni is None:
        return
    for names, path, label in ((fetch_list(uni, "prices"), DATA / "volumes.csv", "volume"),
                               (fetch_list(uni, "prices_usd"), DATA / "volumes_usd_listing.csv", "volume_usd")):
        if not names:
            continue
        existing = _read_wide(path)
        have = set(existing.columns) if existing is not None else set()
        todo = [t for t in names if refresh or t not in have]
        log.append(f"{label}: {len(names)} in universe, {len(names) - len(todo)} on disk, {len(todo)} to fetch")
        new = _download_chunks(todo, log, label, field="Volume") if todo else pd.DataFrame()
        _log_price_stats(new, todo, log, label)
        merged = merge_columns(existing, new, refresh=refresh)
        if not merged.empty:
            merged.index.name = "Date"
            merged.to_csv(path)


def fetch_fx(log, uni=None, refresh=False):
    path = DATA / "fx.csv"
    if uni is None:
        rows = pd.DataFrame({"ticker": list(config.FX_TICKERS.values()),
                             "currency": list(config.FX_TICKERS.keys()), "category": "fx_inverse"})
        refresh = True
    else:
        rows = uni[uni.type == "fx"]
    tickers = list(dict.fromkeys(rows["ticker"]))
    close = _download_chunks(tickers, log, "fx") if tickers else pd.DataFrame()
    fx = fx_to_usd_per_unit(close, rows)
    for _, r in rows.iterrows():
        n = fx[r["currency"]].dropna() if r["currency"] in fx else pd.Series(dtype=float)
        if n.empty:
            log.append(f"fx {r['currency']} ({r['ticker']}): NO DATA")
        else:
            log.append(f"fx {r['currency']} ({r['ticker']}, {r.get('category', '')}): "
                       f"{len(n)} rows, {n.index[0].date()} to {n.index[-1].date()}")
    existing = _read_wide(path)
    merged = merge_columns(existing, fx, refresh=refresh)
    if "USD" not in merged.columns:
        merged["USD"] = 1.0
    merged = merged.ffill()  # holidays only; no leading fill, no invented values
    merged.index.name = "Date"
    merged.to_csv(path)


def _fred(series_id, timeout=20):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    raw = http_get(url, timeout=timeout)
    df = pd.read_csv(io.BytesIO(raw), index_col=0, parse_dates=True)
    return pd.to_numeric(df.iloc[:, 0], errors="coerce")


def fetch_fred(log, series, refresh=False, pause=5.0, retries=2, monthly=False):
    """Fetch FRED series (name -> id) not already in yields.csv. Returns True if FRED answered."""
    path = DATA / "yields.csv"
    existing = _read_wide(path)
    todo = {n: s for n, s in series.items()
            if refresh or existing is None or n not in existing.columns}
    if not todo:
        log.append("fred: nothing to fetch (all columns present)")
        return True
    out, fails, answered = {}, 0, False
    for k, (name, sid) in enumerate(todo.items()):
        if k:
            time.sleep(pause)
        got = None
        for attempt in range(retries + 1):
            try:
                got = _fred(sid)
                break
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                if attempt < retries:
                    time.sleep(pause)
        if got is None:
            fails += 1
            log.append(f"fred {name} ({sid}): FAILED {err}")
            if fails >= 2 and not answered:
                log.append("FRED unavailable (first two requests timed out); skipping the rest")
                break
            continue
        answered = True
        got = got.dropna()
        s = to_monthly_start(got) if monthly or (len(got) > 2 and (got.index[1] - got.index[0]).days < 20) else got
        out[name] = s
        log.append(f"fred {name} ({sid}): {len(got)} rows, {got.index[0].date()} to {got.index[-1].date()}"
                   f"{' (month-ended to monthly)' if s is not got else ''}")
    if out:
        merged = merge_columns(existing, pd.DataFrame(out), refresh=refresh)
        merged.index.name = existing.index.name if existing is not None else "observation_date"
        merged.to_csv(path)
    return answered


def fetch_oecd(log, refresh=False):
    path = DATA / "yields.csv"
    frames = []
    for suffix, url in OECD_Q.items():
        try:
            text = http_get(url, timeout=120, headers={"Accept": "text/csv"}, retries=1).decode("utf-8")
            df = parse_oecd_csv(text, suffix)
            frames.append(df)
            ends = df.apply(lambda c: c.dropna().index[-1].strftime("%Y-%m"))
            log.append(f"oecd {suffix}: {df.shape[1]} countries, {df.index[0].date()} to {df.index[-1].date()}")
            for c in df.columns:
                s = df[c].dropna()
                log.append(f"oecd {c}: {len(s)} rows, {s.index[0].date()} to {s.index[-1].date()}")
        except Exception as e:
            log.append(f"oecd {suffix}: FAILED {type(e).__name__}: {e}")
    if frames:
        new = pd.concat(frames, axis=1)
        existing = _read_wide(path)
        merged = merge_columns(existing, new, refresh=refresh)
        merged.index.name = existing.index.name if existing is not None else "observation_date"
        merged.to_csv(path)


def fetch_treasury(log, refresh=False):
    """Fallback for US 2y/10y nominal and 10y TIPS real yields (daily -> monthly)."""
    base = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
            "daily-treasury-rates.csv/{y}/all?type={t}&field_tdr_date_value={y}&page&_format=csv")
    got = {}
    for kind, t in (("real", "daily_treasury_real_yield_curve"), ("nom", "daily_treasury_yield_curve")):
        parts = []
        for y in range(2005, dt.date.today().year + 1):
            try:
                raw = http_get(base.format(y=y, t=t), timeout=30, retries=1)
                parts.append(pd.read_csv(io.BytesIO(raw)))
            except Exception as e:
                log.append(f"treasury {kind} {y}: FAILED {type(e).__name__}: {e}")
        if parts:
            df = pd.concat(parts)
            df["Date"] = pd.to_datetime(df["Date"], format="mixed")
            got[kind] = df.set_index("Date").sort_index()
            log.append(f"treasury {kind}: {len(df)} rows, {df['Date'].min().date()} to {df['Date'].max().date()}")
    out = {}
    if "real" in got:
        col = next((c for c in got["real"].columns if c.replace(" ", "").upper() == "10YR"), None)
        if col:
            out["US_REAL10"] = to_monthly_start(pd.to_numeric(got["real"][col], errors="coerce"))
    if "nom" in got:
        n = got["nom"]
        c2 = next((c for c in n.columns if c.replace(" ", "").upper() == "2YR"), None)
        c10 = next((c for c in n.columns if c.replace(" ", "").upper() == "10YR"), None)
        if c2:
            out["US_2Y"] = to_monthly_start(pd.to_numeric(n[c2], errors="coerce"))
        if c10:
            out["US_10Y_CMT"] = to_monthly_start(pd.to_numeric(n[c10], errors="coerce"))
    if "US_REAL10" in out and "US_10Y_CMT" in out:
        out["US_BE10"] = (out["US_10Y_CMT"] - out["US_REAL10"]).dropna()
        log.append("treasury US_BE10: DERIVED as nominal 10y minus 10y TIPS real yield (not the FRED series)")
    if out:
        path = DATA / "yields.csv"
        existing = _read_wide(path)
        merged = merge_columns(existing, pd.DataFrame(out), refresh=refresh)
        merged.index.name = existing.index.name if existing is not None else "observation_date"
        merged.to_csv(path)
        for k, s in out.items():
            log.append(f"treasury {k}: {len(s)} months, {s.index[0].date()} to {s.index[-1].date()}")


def fetch_worldbank(log):
    countries = ["US"]
    p = Path(__file__).resolve().parent / "plan" / "longlists" / "em_bonds_countries.csv"
    try:
        countries += [c for c in pd.read_csv(p, dtype=str)["country"].dropna().str.strip() if c]
    except Exception as e:
        log.append(f"worldbank: cannot read {p.name}: {e}")
    countries = list(dict.fromkeys(countries))
    url = (f"https://api.worldbank.org/v2/country/{';'.join(countries)}/indicator/FP.CPI.TOTL.ZG"
           "?format=json&date=2005:2026&per_page=5000")
    try:
        df = parse_worldbank(json.loads(http_get(url, timeout=60, retries=1)))
    except Exception as e:
        log.append(f"worldbank CPI: FAILED {type(e).__name__}: {e}")
        return
    df.index.name = "year"
    df.to_csv(DATA / "cpi_annual.csv")
    log.append(f"worldbank CPI: {df.shape[1]} of {len(countries)} countries, years {df.index.min()}-{df.index.max()}")
    missing = [c for c in countries if c not in df.columns]
    if missing:
        log.append(f"worldbank CPI: no data for {missing}")


def fetch_rates(log, uni=None, refresh=False):
    if uni is None:  # legacy: the FRED series listed in config
        fetch_fred(log, config.FRED_SERIES, refresh=True, pause=1.0, retries=0)
        return
    fetch_oecd(log, refresh=refresh)
    ok = fetch_fred(log, FRED_NEW, refresh=refresh)
    if not ok:
        log.append("FRED unavailable: using Treasury.gov for US_REAL10, US_2Y, US_10Y_CMT, derived US_BE10")
        try:
            fetch_treasury(log, refresh=refresh)
        except Exception as e:
            log.append(f"treasury: FAILED {type(e).__name__}: {e}")
    try:
        fetch_worldbank(log)
    except Exception as e:
        log.append(f"worldbank: FAILED {type(e).__name__}: {e}")


def fetch_cboe(log, uni=None, refresh=False):
    d = DATA / "cboe"
    d.mkdir(parents=True, exist_ok=True)
    for idx in CBOE_INDICES:
        f = d / f"{idx}.csv"
        if f.exists() and not refresh:
            log.append(f"cboe {idx}: on disk, skipped")
            continue
        try:
            url = f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{idx}_History.csv"
            s = parse_cboe_csv(http_get(url, timeout=60, retries=1).decode("utf-8-sig"))
            s.to_frame().to_csv(f, date_format="%Y-%m-%d")
            log.append(f"cboe {idx}: {len(s)} rows, {s.index[0].date()} to {s.index[-1].date()}")
        except Exception as e:
            log.append(f"cboe {idx}: FAILED {type(e).__name__}: {e}")


def fetch_fundamentals(log, uni=None, refresh=False, pause=0.5):
    import yfinance as yf

    tickers = [s.ticker for s in config.STOCKS] if uni is None else fetch_list(uni, "fundamentals")
    if uni is None:
        refresh = True
    done = 0
    for tk in tickers:
        d = DATA / "fundamentals" / tk
        if d.exists() and not refresh:
            log.append(f"fundamentals {tk}: folder exists, skipped")
            continue
        d.mkdir(parents=True, exist_ok=True)
        t = yf.Ticker(tk)
        got = 0
        try:
            info = {k: v for k, v in t.info.items() if isinstance(v, (int, float, str, bool))}
            (d / "info.json").write_text(json.dumps(info, indent=1, sort_keys=True))
            log.append(f"info {tk}: {len(info)} fields")
            got += 1 if info else 0
        except Exception as e:
            log.append(f"info {tk}: FAILED {type(e).__name__}: {str(e)[:120]}")
        for name in ("cashflow", "balance_sheet", "income_stmt", "growth_estimates",
                     "earnings_estimate", "revenue_estimate", "dividends"):
            time.sleep(pause)
            try:
                df = getattr(t, name)
                if df is None or len(df) == 0:
                    log.append(f"{name} {tk}: empty")
                    continue
                df.to_csv(d / f"{name}.csv")
                got += 1
                log.append(f"{name} {tk}: ok")
            except Exception as e:
                log.append(f"{name} {tk}: FAILED {type(e).__name__}: {str(e)[:120]}")
        log.append(f"fundamentals {tk}: {got}/8 items")
        done += 1
        time.sleep(pause)
    log.append(f"fundamentals: {done} folders fetched, {len(tickers) - done} skipped")


def fetch_edgar(log, uni=None, refresh=False, pause=0.15):
    if uni is None:
        return
    d = DATA / "edgar"
    d.mkdir(parents=True, exist_ok=True)
    ciks = fetch_list(uni, "edgar")
    ok = fail = skip = 0
    for cik in ciks:
        f = d / f"CIK{cik}.json"
        if f.exists() and not refresh:
            skip += 1
            continue
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        try:
            raw = http_get(url, timeout=60, headers={"User-Agent": EDGAR_UA}, retries=1)
            json.loads(raw)  # validate
            f.write_bytes(raw)
            ok += 1
            log.append(f"edgar CIK{cik}: ok, {len(raw) // 1024} KB")
        except urllib.error.HTTPError as e:
            fail += 1
            log.append(f"edgar CIK{cik}: FAILED HTTP {e.code}")
        except Exception as e:
            fail += 1
            log.append(f"edgar CIK{cik}: FAILED {type(e).__name__}: {str(e)[:100]}")
        time.sleep(pause)
    log.append(f"edgar: {ok} fetched, {skip} already on disk, {fail} failed, of {len(ciks)} CIKs")


def _epoch_date(v, ms=False):
    try:
        v = float(v)
        return dt.datetime.fromtimestamp(v / 1000 if ms else v, dt.timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


def fund_row(ticker, info):
    """Flatten a yfinance info dict into the funds.csv columns."""
    inc = _epoch_date(info.get("fundInceptionDate")) if info.get("fundInceptionDate") else ""
    if not inc and info.get("firstTradeDateMilliseconds"):
        inc = _epoch_date(info["firstTradeDateMilliseconds"], ms=True)
    exp = ""
    if info.get("netExpenseRatio") is not None:        # yfinance reports this in percent
        exp = float(info["netExpenseRatio"]) / 100.0
    elif info.get("annualReportExpenseRatio") is not None:  # already a decimal
        exp = float(info["annualReportExpenseRatio"])
    y = info.get("yield")
    if y is None:
        y = info.get("trailingAnnualDividendYield", "")
    return {
        "ticker": ticker, "name": info.get("longName") or info.get("shortName") or "",
        "inception": inc, "aum_usd": info.get("totalAssets", ""), "expense_ratio": exp,
        "category": info.get("category", ""), "yield": y,
        "currency": info.get("currency", ""), "quoteType": info.get("quoteType", ""),
    }


def fetch_funds(log, uni=None, refresh=False, pause=0.5):
    import yfinance as yf

    if uni is None:
        return
    path = DATA / "funds.csv"
    cols = ["ticker", "name", "inception", "aum_usd", "expense_ratio", "category", "yield",
            "currency", "quoteType"]
    old = pd.read_csv(path, dtype={"ticker": str}) if path.exists() else pd.DataFrame(columns=cols)
    have = set(old["ticker"]) if not refresh else set()
    rows = []
    for tk in fetch_list(uni, "funds"):
        if tk in have:
            continue
        try:
            t = yf.Ticker(tk)
            info = t.info or {}
            row = fund_row(tk, info)
            if not row["inception"]:
                try:
                    row["inception"] = _epoch_date(t.get_history_metadata().get("firstTradeDate"))
                except Exception:
                    pass
            rows.append(row)
            log.append(f"funds {tk}: ok inception={row['inception'] or '?'} aum={row['aum_usd'] or '?'} "
                       f"er={row['expense_ratio'] if row['expense_ratio'] != '' else '?'}")
        except Exception as e:
            log.append(f"funds {tk}: FAILED {type(e).__name__}: {str(e)[:120]}")
        time.sleep(pause)
    if rows:
        new = pd.DataFrame(rows, columns=cols)
        out = pd.concat([old[~old["ticker"].isin(new["ticker"])], new], ignore_index=True)
        out.to_csv(path, index=False)
    log.append(f"funds: {len(rows)} fetched this run")


# --------------------------------------------------------------------------
# Coverage summary
# --------------------------------------------------------------------------
def coverage_summary(uni, log):
    prices = _read_wide(DATA / "prices.csv")
    log.append("")
    log.append("=== COVERAGE SUMMARY (prices.csv) ===")
    if prices is None:
        log.append("no prices.csv")
        return
    first = {c: prices[c].dropna().index[0] for c in prices.columns if prices[c].notna().any()}
    nrows = {c: int(prices[c].notna().sum()) for c in prices.columns}
    nodata = []
    for (typ, role), g in uni[uni.type != "fx"].groupby(["type", "role"]):
        ts = list(g["ticker"])
        have = [t for t in ts if t in first]
        miss = [t for t in ts if t not in first]
        short = [t for t in have if nrows[t] < 60]
        early = min((first[t] for t in have), default=None)
        log.append(f"{typ}/{role}: {len(have)}/{len(ts)} with prices; earliest first date "
                   f"{early.date() if early is not None else 'n/a'}; none: {miss or '-'}; "
                   f"under 60 rows: {short or '-'}")
        nodata += [(typ, role, t) for t in miss]
    log.append(f"TOTAL tickers with no price data: {len(nodata)}: {[t for _, _, t in nodata]}")
    fxrows = uni[uni.type == "fx"]
    fx = _read_wide(DATA / "fx.csv")
    if fx is not None and len(fxrows):
        miss = [c for c in fxrows["currency"] if c not in fx.columns or fx[c].dropna().empty]
        log.append(f"fx: {len(fxrows) - len(miss)}/{len(fxrows)} currencies with data; none: {miss or '-'}")
    usd = _read_wide(DATA / "prices_usd_listing.csv")
    if usd is not None:
        want = fetch_list(uni, "prices_usd")
        miss = [t for t in want if t not in usd.columns or usd[t].dropna().empty]
        log.append(f"prices_usd_listing: {len(want) - len(miss)}/{len(want)} with data; none: {miss or '-'}")
    fdir = DATA / "fundamentals"
    want = fetch_list(uni, "fundamentals")
    have = [t for t in want if (fdir / t / "info.json").exists()]
    log.append(f"fundamentals folders with info.json: {len(have)}/{len(want)}; "
               f"missing: {[t for t in want if t not in have] or '-'}")
    ewant = fetch_list(uni, "edgar")
    ehave = [c for c in ewant if (DATA / "edgar" / f"CIK{c}.json").exists()]
    log.append(f"edgar files: {len(ehave)}/{len(ewant)}; missing: {[c for c in ewant if c not in ehave] or '-'}")
    fpath = DATA / "funds.csv"
    if fpath.exists():
        f = pd.read_csv(fpath, dtype={"ticker": str})
        want = fetch_list(uni, "funds")
        log.append(f"funds.csv: {len(set(want) & set(f['ticker']))}/{len(want)} tickers")


# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--universe", help="path to universe.csv; omit for the legacy config.STOCKS fetch")
    ap.add_argument("--refresh", action="store_true", help="re-download items already on disk")
    ap.add_argument("--only", nargs="+", choices=STEPS, help="run only these steps")
    args = ap.parse_args(argv)

    DATA.mkdir(parents=True, exist_ok=True)
    started = time.time()
    header = (f"Fetch run {dt.datetime.now():%Y-%m-%d %H:%M:%S}  universe="
              f"{args.universe or '(legacy config.STOCKS)'}  refresh={args.refresh}  only={args.only or 'all'}")
    log = Log(DATA / "fetch_log.txt", mode="a" if args.only else "w")
    log.append(header)

    if args.universe is None:
        for fn in (fetch_prices, fetch_fx, fetch_rates, fetch_fundamentals):
            try:
                fn(log)
            except Exception as e:
                log.append(f"{fn.__name__}: FAILED {type(e).__name__}: {e}")
    else:
        uni = read_universe(args.universe)
        log.append(f"universe rows: {len(uni)}; steps: {args.only or list(STEPS)}")
        fns = {"prices": fetch_prices, "fx": fetch_fx, "rates": fetch_rates, "cboe": fetch_cboe,
               "fundamentals": fetch_fundamentals, "edgar": fetch_edgar, "funds": fetch_funds, "volumes": fetch_volumes}
        for step in (args.only or STEPS):
            t0 = time.time()
            log.append(f"--- step {step} start {dt.datetime.now():%H:%M:%S}")
            try:
                fns[step](log, uni, args.refresh)
            except Exception as e:
                log.append(f"step {step}: FAILED {type(e).__name__}: {e}")
            log.append(f"--- step {step} done in {time.time() - t0:.0f}s")
        try:
            coverage_summary(uni, log)
        except Exception as e:
            log.append(f"coverage summary: FAILED {type(e).__name__}: {e}")
    log.append(f"Total wall time {time.time() - started:.0f}s")
    log.close()
    print("\n".join(log.lines[-60:]))


if __name__ == "__main__":
    main()
