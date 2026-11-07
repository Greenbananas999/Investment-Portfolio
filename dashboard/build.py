"""Build the static dashboard site (dashboard/site/) from the JSON and CSV in reports/.

    python -m dashboard --no-serve        # build only

Every page is a plain HTML file with its data embedded as JSON in one
<script type="application/json" id="page-data"> tag, so the site works when
index.html is opened straight from disk (file://). Plotly.js is copied from the
installed `plotly` package into site/vendor/. Nothing is fetched at run time.
Numbers on the pages come from the JSON/CSV/markdown files, never typed here
(the few rule constants in RULES are copied from method.md and cited).
"""

import csv
import html
import json
import math
import re
import shutil
from pathlib import Path

from . import mdlite
from .series import build_growth

ROOT = Path(__file__).resolve().parents[1]
PKG = Path(__file__).resolve().parent
CAND = ROOT / "reports" / "candidates"
PLAN = ROOT / "research" / "plan"
PORTFOLIO = ROOT / "reports" / "final" / "portfolio.json"
DEFAULT_SITE = PKG / "site"

PAGES = [("index", "Overview"), ("positions", "Positions"), ("compare", "Compare"),
         ("frontier", "Frontier"), ("whatif", "What-if"), ("method", "Method and evidence")]

TYPE_ORDER = ["us_growth_stock", "intl_growth_stock", "em_bond", "other"]
TYPE_LABEL = {"us_growth_stock": "US growth stock", "intl_growth_stock": "International growth stock",
              "em_bond": "EM bond fund", "other": "Other sleeve (gold, silver)", "overlay": "Derivative overlay"}
BENCH_TICKERS = ["IVW", "QQQ", "EFG", "EEM", "EMB", "EMLC", "GLD", "ACWX", "SPY", "AGG", "BIL"]
BLENDS = {"EFG_EEM_5050": {"EFG": 0.5, "EEM": 0.5}, "SIXTY_FORTY": {"SPY": 0.6, "AGG": 0.4},
          "GUIDE_BENCH_proxy": {"ACWX": 0.55, "EMB": 0.35, "GLD": 0.10}}   # method.md section 9

# Rule constants copied from method.md sections 3 and 10 (a portfolio.json `settings` block overrides them).
RULES = {"source": "method.md sections 3 and 10", "non_us_min": 0.70, "sleeve_target": {"stocks": 0.55, "bonds": 0.35, "other": 0.10},
         "sleeve_tolerance": 0.10, "stock_max": 0.10, "stock_min": 0.03, "fund_max": 0.15, "other_max": 0.10,
         "counts": {"us_growth_stock": [3, 3], "intl_growth_stock": [3, 3], "em_bond": [4, 4], "other": [1, 3]}}

COUNTRY = {"US": "United States", "TW": "Taiwan", "IN": "India", "CA": "Canada", "AU": "Australia", "DK": "Denmark",
           "KR": "South Korea", "HK": "Hong Kong", "CN": "China", "NL": "Netherlands", "JP": "Japan"}

METRIC_ROWS = [("cagr", "cagr", "pct"), ("vol", "volatility", "pct"), ("sharpe", "sharpe", "num"),
               ("max_drawdown", "max_drawdown", "pct"), ("info_ratio", "information_ratio", "num"),
               ("t_stat_ir", "t_stat", "num"), ("deflated_sharpe", "deflated_sharpe", "num"),
               ("tracking_error", "tracking_error", "pct"), ("beta", "beta", "num"), ("alpha", "alpha", "pct")]
LABELS = {"rev_cagr_3y": "Revenue growth (3-year CAGR)", "ni_cagr_3y": "Net income growth (3-year CAGR)",
          "op_margin": "Operating margin", "op_margin_chg_3y": "Operating margin change (3 years)",
          "roic": "Return on invested capital", "roic_or_roe": "Return on invested capital (ROE for financials)",
          "net_debt_ebitda": "Net debt / EBITDA", "fcf_yield": "Free cash flow yield", "pe_trailing": "Trailing P/E",
          "pe_now": "Trailing P/E", "pe_rel_5y": "P/E relative to its 5-year median", "ytm": "Yield to maturity",
          "carry": "Carry (yield minus expected FX loss and fee)", "market_cap_usd_bn": "Market cap (USD bn)",
          "revenue_usd_bn": "Revenue (USD bn)", "net_income_usd_bn": "Net income (USD bn)", "fcf_usd_bn": "Free cash flow (USD bn)",
          "market_cap_local": "Market cap (local currency)", "fundamental_score": "Fundamental score (0-1)",
          "growth_score": "Growth score", "quality_score": "Quality score", "valuation_score": "Valuation score",
          "T1": "T1 momentum (12-1 months)", "T2": "T2 above 200-day average (1 = yes)", "T3": "T3 6-month relative strength",
          "T4": "T4 12-month volatility", "T5": "T5 distance below 52-week high", "rank_is": "In-sample rank",
          "rank_is_of": "of", "composite_is": "In-sample composite score", "corr_equity": "Correlation with equities",
          "inflation_beta": "Inflation beta", "ret_2022_info": "Return, Dec 2021 to Oct 2022",
          "corr_acwx": "Correlation with world ex-US stocks (ACWX)", "corr_emb": "Correlation with EM bonds (EMB)",
          "insample_rank": "In-sample rank", "insample_composite": "In-sample composite score",
          "cost_liquidity_score": "Cost and liquidity score", "diversification_score": "Diversification score"}
PCT_KEYS = {"rev_cagr_3y", "ni_cagr_3y", "op_margin", "op_margin_chg_3y", "roic", "roic_or_roe", "fcf_yield", "ytm",
            "carry", "T1", "T3", "T4", "T5", "ret_2022_info"}
SKIP_KEYS = {"as_of", "source", "flags", "fy_end", "fy_filed", "valuation_date", "technical_note", "mcap_asof_usd_bn",
             "fundamentals_pit", "above_200dma", "insample_table_benchmark", "insample_table_ir", "traded_value_usd_m_2017",
             "traded_value_usd_m_latest", "market_cap_usd_bn", "inflation_beta_months", "T2_note"}
STRESS_ORDER = [("gfc_2008", "GFC 2008"), ("taper_2013", "Taper tantrum 2013"), ("covid_2020", "Covid crash 2020"),
                ("inflation_2022", "Inflation and rate shock 2022"), ("strong_usd", "Strong USD (average month)")]


# ---------------------------------------------------------------- small helpers

def clean(o):
    """Recursively turn NaN/inf into None so json.dumps(allow_nan=False) works."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    return o


def dumps(o):
    return json.dumps(clean(o), allow_nan=False, separators=(",", ":")).replace("<", "\\u003c").replace("\u2028", "\\u2028")


def esc(s):
    return html.escape("" if s is None else str(s))


def num(x, d=2):
    return "n/a" if not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x) else f"{x:.{d}f}"


def pct(x, d=1):
    return "n/a" if not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x) else f"{x * 100:.{d}f}%"


def compact(x):
    a = abs(x)
    for lim, suf in ((1e12, " trn"), (1e9, " bn"), (1e6, " m")):
        if a >= lim:
            return f"{x / lim:,.1f}{suf}"
    return f"{x:,.2f}"


def fmt_pair(key, v):
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        if key in PCT_KEYS:
            return pct(v)
        if abs(v) >= 1e6:
            return compact(v)
        if key.startswith("rank") or key == "rank_is_of":
            return str(int(v))
        return num(v, 2)
    return esc(v)


def read_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def read_text(p):
    return Path(p).read_text(encoding="utf-8")


def verdict_class(v):
    v = (v or "").lower()
    if v.startswith("pass"):
        return "pass"
    if v.startswith("downgrade"):
        return "warn"
    if v.startswith("fail"):
        return "fail"
    return "none"


def verdict_word(v):
    if not v:
        return "no verdict"
    return v.replace(" (drop rule 8.2 triggered)", " (drop rule 8.2)")


class Gloss:
    """First use of a term shows its definition beside it; later uses carry it as a tooltip."""

    def __init__(self, g):
        self.g, self.seen = g, set()

    def term(self, key, label=None, block=True, tip=False):
        e = self.g.get(key)
        if not e:
            return esc(label or key)
        lab = esc(label or e["label"])
        d = esc(e["def"])
        if tip or key in self.seen:
            return f'<abbr title="{d}">{lab}</abbr>'
        self.seen.add(key)
        return f'{lab}<span class="def{" blk" if block else ""}">{d}</span>'


# ---------------------------------------------------------------- inputs

def load_inputs(root=ROOT, portfolio_path=None):
    cand_dir = root / "reports" / "candidates"
    cands = {}
    for f in sorted(cand_dir.glob("*.json")):
        try:
            d = read_json(f)
        except Exception:
            continue
        if isinstance(d, dict) and "id" in d and "position_type" in d:
            cands[d["id"]] = d
    with open(cand_dir / "scorecard.csv", encoding="utf-8", newline="") as f:
        score = list(csv.DictReader(f))
    reviews = {}
    for f in sorted((cand_dir / "reviews").glob("*_review.json")):
        r = read_json(f)
        reviews[f.stem] = r
    portfolio = None
    pf = Path(portfolio_path) if portfolio_path else root / "reports" / "final" / "portfolio.json"
    if pf.exists():
        try:
            portfolio = read_json(pf)
        except Exception as e:   # a half-written file is treated as missing
            print(f"warning: could not read {pf}: {e}")
    return {"cands": cands, "score": score, "reviews": reviews, "portfolio": portfolio,
            "glossary": read_json(PKG / "data" / "glossary.json"), "why": read_json(PKG / "data" / "why_lost.json")}


def fnum(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def as_of_date(inp):
    pf = inp["portfolio"]
    if pf and pf.get("as_of"):
        return str(pf["as_of"])
    ends = [d.get("metrics", {}).get("full", {}).get("usd", {}) or {} for d in inp["cands"].values()]
    ends = [e.get("end") for e in ends if e.get("end")]
    return max(ends) if ends else "unknown"


def meta_for(inp):
    """{yahoo ticker: info} for every candidate (used by Overview and What-if)."""
    uni = {}
    up = PLAN / "universe.csv"
    if up.exists():
        with open(up, encoding="utf-8", newline="") as f:
            uni = {r["ticker"]: r for r in csv.DictReader(f)}
    out = {}
    for d in inp["cands"].values():
        t = d.get("ticker")
        ccy = d.get("currency_code") or (uni.get(t, {}).get("currency")) or (d["currency"] if isinstance(d.get("currency"), str) else None)
        pt = d["position_type"]
        if pt in ("us_growth_stock", "intl_growth_stock"):
            region = COUNTRY.get(d.get("country"), d.get("country") or "n/a")
        elif pt == "em_bond":
            region = "EM bonds (multi-country)"
        else:
            region = "Global (precious metals)"
        out[t] = {"id": d["id"], "name": d.get("name"), "position_type": pt, "country": d.get("country"),
                  "currency": ccy, "region": region, "non_us": d.get("non_us_share", 1.0 if d.get("non_us") else 0.0)}
    return out


# ---------------------------------------------------------------- page shell

def render_page(key, title, body, data, scripts, as_of, sources, plotly=True):
    nav = "".join(f'<a href="{k}.html"{" class=active" if k == key else ""}>{esc(t)}</a>' for k, t in PAGES)
    srcs = "".join(f"<li><code>{esc(s)}</code></li>" for s in sources)
    js = ""
    if plotly:
        js += '<script src="vendor/plotly.min.js"></script>\n'
    js += '<script src="static/app.js"></script>\n' + "".join(f'<script src="static/{s}"></script>\n' for s in scripts)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | AFMBA622 portfolio dashboard</title>
<link rel="stylesheet" href="static/style.css">
</head><body data-page="{key}">
<header class="top"><div class="brand">AFMBA622 global portfolio <span>$100,000 | 7 years | at least 70% non-US</span></div>
<nav>{nav}</nav></header>
<main>
{body}
</main>
<footer><p>Data as of <strong>{esc(as_of)}</strong>. This page is built offline from the JSON in <code>reports/</code>; nothing is loaded from the internet.
Rebuild: <code>python -m dashboard --no-serve</code>.</p>
<details><summary>Source and reproduce commands for this page</summary><ul>{srcs}</ul></details></footer>
<script type="application/json" id="page-data">{dumps(data)}</script>
{js}</body></html>
"""


def glossary_block(g, keys, title="What these terms mean"):
    items = "".join(f"<dt>{esc(g[k]['label'])}</dt><dd>{esc(g[k]['def'])}</dd>" for k in keys if k in g)
    return f'<details class="guide" open><summary>{esc(title)}</summary><dl>{items}</dl></details>'


def pf_missing_note():
    return ('<div id="pf-missing" class="notice" hidden><strong>Portfolio results not built yet.</strong> '
            'This page reads <code>reports/final/portfolio.json</code>, which has not been written. '
            'Run the portfolio builder, then <code>python -m dashboard</code> again.</div>')


# ---------------------------------------------------------------- Positions

def stress_table(d, label_pos):
    st = d.get("stress") or {}
    rows = []
    extra = None
    for k, lab in STRESS_ORDER:
        s = st.get(k)
        if not isinstance(s, dict):
            continue
        if k == "strong_usd":
            a, b = s.get("avg_return"), s.get("benchmark")
            span = f"{s.get('months', '')} months" if s.get("months") else "months the dollar rose 2%+"
            xtra = ""
        else:
            a, b = s.get("return"), s.get("benchmark")
            span = f"{s.get('start', '')} to {s.get('end', '')}"
            xtra = pct(s.get("qqq") if "qqq" in s else s.get("guide_bench")) if ("qqq" in s or "guide_bench" in s) else ""
            extra = "QQQ" if "qqq" in s else ("GUIDE_BENCH" if "guide_bench" in s else extra)
        rows.append((lab, span, pct(a), pct(b), xtra))
    if not rows:
        return "<p class=muted>Stress results not available (key <code>stress</code>).</p>"
    head = f"<th>Window</th><th>Dates</th><th>{esc(label_pos)}</th><th>Benchmark</th>" + (f"<th>{esc(extra)}</th>" if extra else "")
    body = "".join(f"<tr><td>{esc(a)}</td><td class=muted>{esc(b)}</td><td class=num>{c}</td><td class=num>{dd}</td>"
                   + (f"<td class=num>{e}</td>" if extra else "") + "</tr>" for a, b, c, dd, e in rows)
    return f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def kv_table(pairs):
    if not pairs:
        return "<p class=muted>Not available.</p>"
    return '<table class="kv"><tbody>' + "".join(f"<tr><th>{esc(LABELS.get(k, k.replace('_', ' ')))}</th><td class=num>{fmt_pair(k, v)}</td></tr>"
                                                  for k, v in pairs) + "</tbody></table>"


def fundamentals_pairs(d):
    fl = d.get("fundamentals_latest")
    if isinstance(fl, dict) and isinstance(fl.get("measures"), dict):
        src = fl["measures"]
    elif isinstance(d.get("fundamentals"), dict) and isinstance(d["fundamentals"].get("latest"), dict):
        src = d["fundamentals"]["latest"]
    else:
        src = {}
    return [(k, v) for k, v in src.items() if k not in SKIP_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool)]


def screen_pairs(d):
    sc = d.get("screens") or {}
    pairs = []
    if isinstance(sc.get("fundamental_score"), (int, float)):
        pairs.append(("fundamental_score", sc["fundamental_score"]))
    for k, v in (sc.get("detail") or {}).items():
        if k in SKIP_KEYS or isinstance(v, (dict, list, str)) or v is None:
            continue
        if isinstance(v, bool):
            continue
        pairs.append((k, v))
    return pairs


def memo_excerpt(d):
    p = ROOT / (d.get("memo") or "")
    if not d.get("memo") or not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    out = {}
    for key, rx in (("risks", r"\*\*Risks\.\*\*\s*(.+?)(?:\n\s*\n|$)"), ("verdict", r"\*\*Verdict[^*]*\*\*\s*(.+?)(?:\n\s*\n|$)")):
        m = re.search(rx, text, re.S)
        if m:
            out[key] = " ".join(m.group(1).split())
    return out


def claims_table(d, review_notes):
    rv = d.get("review") or {}
    claims = rv.get("claims") or []
    if not claims:
        return "<p class=muted>No reviewer claims recorded (key <code>review.claims</code>).</p>"
    rows = ""
    for c in claims:
        st = str(c.get("status", ""))
        ev = c.get("evidence") or c.get("note") or ""
        rows += (f'<tr><td>{esc(c.get("claim"))}</td><td><span class="badge {verdict_class(st) if st.lower().startswith(("pass", "fail")) else "warn"}">{esc(st)}</span></td>'
                 f"<td class=small>{esc(ev)}</td></tr>")
    note = f'<p class="small"><strong>Reviewer note.</strong> {esc(review_notes)}</p>' if review_notes else ""
    return f'<div class="tablewrap"><table><thead><tr><th>Claim checked</th><th>Result</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table></div>{note}'


def build_card(d, row, inp, gl, site_img, pf_pos):
    g = Gloss(inp["glossary"])
    tid = d["id"]
    rv = d.get("review") or {}
    verdict = rv.get("verdict") or row.get("review_verdict") or ""
    rk = {r["id"]: r for r in inp["score"]}
    notes = ""
    for rev in inp["reviews"].values():
        c = (rev.get("candidates") or {}).get(d["ticker"]) or (rev.get("candidates") or {}).get(tid)
        if c:
            notes = c.get("notes", "")
    m = d.get("metrics") or {}

    def blk(w, ccy="usd"):
        x = (m.get(w) or {})
        return x.get(ccy) or {}
    is_u, oos_u, is_l, oos_l = blk("in_sample"), blk("out_of_sample"), blk("in_sample", "local"), blk("out_of_sample", "local")
    trs = ""
    for key, gk, f in METRIC_ROWS:
        fn = pct if f == "pct" else num
        trs += (f"<tr><th>{g.term(gk)}</th><td class=num>{fn(is_u.get(key))}</td><td class=num>{fn(oos_u.get(key))}</td></tr>")
    bsh = fnum(row.get("benchmark_oos_sharpe"))
    bench_line = f'<p class="small muted">Benchmark out-of-sample Sharpe for this type ({esc(row.get("benchmark"))}): {num(bsh)}.</p>' if bsh is not None else ""
    metrics_tbl = (f'<table class="metrics"><thead><tr><th>USD, monthly total return</th><th>In-sample<br><span class=muted>{esc(is_u.get("start", "")[:7])} to {esc(is_u.get("end", "")[:7])}</span></th>'
                   f'<th>Out-of-sample<br><span class=muted>{esc(oos_u.get("start", "")[:7])} to {esc(oos_u.get("end", "")[:7])}</span></th></tr></thead><tbody>{trs}</tbody></table>{bench_line}')
    # currency
    cur_o, cur_i = d.get("currency") if isinstance(d.get("currency"), dict) else {}, d.get("currency_in_sample") or {}
    cur_rows = ""
    for key, lab in (("local_return", "Return in local currency"), ("fx_return", "Currency effect (FX)"), ("usd_return", "Return in USD"),
                     ("hedged_return", "USD return if hedged"), ("hedge_cost", "Hedge cost per year"), ("fx_vol_share", "FX share of variance")):
        if cur_o.get(key) is None and cur_i.get(key) is None:
            continue
        lab_h = g.term("fx_vol_share", lab) if key == "fx_vol_share" else (g.term("hedge_cost", lab) if key == "hedge_cost" else (g.term("local_vs_usd", lab) if key == "local_return" else esc(lab)))
        cur_rows += f"<tr><th>{lab_h}</th><td class=num>{pct(cur_i.get(key)) if cur_i else 'n/a'}</td><td class=num>{pct(cur_o.get(key))}</td></tr>"
    cur_tbl = (f'<table class="metrics"><thead><tr><th>Currency</th><th>In-sample</th><th>Out-of-sample</th></tr></thead><tbody>{cur_rows}</tbody></table>'
               if cur_rows else "<p class=muted>Dollar-priced: no currency effect.</p>")
    # forward returns
    er = d.get("expected_return_7y") or {}
    mrows = "".join(f"<tr><th>{esc(k.replace('_', ' '))}</th><td class=num>{pct(v)}</td></tr>"
                    for k, v in (er.get("methods") or {}).items() if v is not None)
    rng = er.get("range_5_95")
    fwd = (f'<table class="kv"><tbody>{mrows}<tr class="strong"><th>{g.term("consensus", "Consensus (USD, per year)")}</th><td class=num>{pct(er.get("consensus_usd"))}</td></tr>'
           + (f'<tr><th>Consensus in local currency</th><td class=num>{pct(er.get("consensus_local"))}</td></tr>' if er.get("consensus_local") not in (None, er.get("consensus_usd")) else "")
           + (f'<tr><th>5th to 95th percentile</th><td class=num>{pct(rng[0])} to {pct(rng[1])}</td></tr>' if isinstance(rng, list) and len(rng) == 2 else "")
           + "</tbody></table>") if er else "<p class=muted>Forward estimate not available (key <code>expected_return_7y</code>).</p>"
    # screens
    sc_note = '<p class="small muted">No technical signal was kept for any type (out-of-sample test, Method page), so there is no technical score.</p>'
    fund_tbl = kv_table(fundamentals_pairs(d)) if fundamentals_pairs(d) else ""
    screens_tbl = kv_table(screen_pairs(d))
    # explain
    expl = "".join(f"<li>{esc(s)}</li>" for s in (d.get("explain") or []))
    expl = f'<ol class="explain">{expl}</ol>' if expl else "<p class=muted>No explanation sentences (key <code>explain</code>).</p>"
    # charts
    imgs = ""
    for ck, cap in (("growth", "Growth of $10,000 against the benchmark"), ("rolling", "Rolling 36-month Sharpe and information ratio")):
        src = (d.get("charts") or {}).get(ck)
        if src and (ROOT / src).exists():
            imgs += f'<figure><img src="img/{Path(src).name}" alt="{esc(cap)} for {esc(tid)}" loading="lazy"><figcaption>{esc(cap)}</figcaption></figure>'
    # runners-up
    typ = d["position_type"]
    sib = [r for r in inp["score"] if r["type"] == typ and r["id"] != tid]
    ru = [r for r in sib if r.get("decision") == "runner-up"]
    others = [r for r in sib if r.get("decision") not in ("pick", "runner-up")]
    why = inp["why"]
    ru_html = ""
    for r in sorted(ru, key=lambda r: int(r.get("rank_in_type") or 99)):
        ru_html += (f'<li><strong>{esc(r["ticker"])}</strong> {esc(r["name"])} (rank {esc(r.get("rank_in_type"))}, rubric {num(fnum(r.get("rubric_total")), 1)}, '
                    f'OOS Sharpe {num(fnum(r.get("oos_sharpe")))}, review: {esc(verdict_word(r.get("review_verdict")))}). {esc(why["tickers"].get(r["ticker"], ""))}</li>')
    typ_txt = why["types"].get(typ, {}).get("text", "")
    oth = ", ".join(f'{esc(r["ticker"])} ({esc(r.get("decision") or "not picked")})' for r in sorted(others, key=lambda r: int(r.get("rank_in_type") or 99)))
    ru_block = (f'<ul class="runners">{ru_html or "<li class=muted>No runners-up recorded.</li>"}</ul><p class="small">{esc(typ_txt)}</p>'
                + (f'<p class="small muted">Also screened but not picked or not runner-up: {oth}.</p>' if oth else ""))
    me = memo_excerpt(d)
    memo_html = ""
    if me.get("verdict") or me.get("risks"):
        memo_html = ('<details><summary>Analyst memo: verdict and risks</summary>'
                     + (f'<p class=small><strong>Verdict.</strong> {esc(me.get("verdict"))}</p>' if me.get("verdict") else "")
                     + (f'<p class=small><strong>Risks.</strong> {esc(me.get("risks"))}</p>' if me.get("risks") else "") + "</details>")
    # header badges
    me_row = rk.get(tid, row)
    w = pf_pos.get(d["ticker"])
    wbadge = f'<span class="badge info">{pct(w["weight"])} of portfolio ({"$" + format(w["dollars"], ",.0f") if isinstance(w.get("dollars"), (int, float)) else "n/a"})</span>' if w else ""
    ccy = d.get("currency_code") or (d["currency"] if isinstance(d.get("currency"), str) else "")
    nonus = '<span class="badge info">non-US</span>' if d.get("non_us") else '<span class="badge neutral">counts as US / neutral</span>'
    return f"""<article class="card" id="card-{esc(tid)}" data-type="{esc(typ)}">
<div class="cardhead"><div><h2>{esc(d["ticker"])} <span class="cname">{esc(d.get("name"))}</span></h2>
<p class="muted">{esc(TYPE_LABEL.get(typ, typ))} | {esc(d.get("country"))} | {esc(ccy)} | {esc(d.get("sector") or d.get("category") or "")}</p></div>
<div class="badges"><span class="badge pass">pick</span><span class="badge {verdict_class(verdict)}">review: {esc(verdict_word(verdict))}</span>
<span class="badge neutral">{g.term("rubric", "rubric", tip=True)} {num(fnum(me_row.get("rubric_total")), 1)}, rank {esc(me_row.get("rank_in_type"))} in type</span>{nonus}{wbadge}
<button class="printbtn" type="button" data-print="card-{esc(tid)}">Print this card</button></div></div>
<section class="explainbox"><h3>How to explain this pick</h3>{expl}</section>
<div class="cols2"><section><h3>Track record: in-sample vs out-of-sample</h3>{metrics_tbl}
<p class="small muted">{g.term("in_sample", "In-sample", False)}: the screen was built on these years. {g.term("out_of_sample", "Out-of-sample", False)}: the judging years.</p></section>
<section><h3>Currency: local vs USD</h3>{cur_tbl}<h3>Expected 7-year return</h3>{fwd}</section></div>
<div class="cols2"><section><h3>Fundamentals (latest filings)</h3>{fund_tbl or '<p class=muted>Not available (key <code>fundamentals</code>).</p>'}</section>
<section><h3>Screen scores at 2017 and technicals</h3>{screens_tbl}{sc_note}</section></div>
<section><h3>Charts</h3><div class="figs">{imgs or "<p class=muted>No chart files.</p>"}</div></section>
<section><h3>{g.term("stress", "Stress test", False)} (USD total return over each window)</h3>{stress_table(d, d["ticker"])}</section>
<section><h3>Reviewer verdict and claims</h3>{claims_table(d, notes)}</section>
<section><h3>Runners-up in this type, and why they lost</h3>{ru_block}</section>
{memo_html}
<p class="small muted">Source: <code>reports/candidates/{esc(tid)}.json</code>. Reproduce: <code>{esc(d.get("reproduce"))}</code></p>
</article>"""


def build_positions(inp, site):
    picks = [r for r in inp["score"] if r.get("decision") == "pick"]
    picks.sort(key=lambda r: (TYPE_ORDER.index(r["type"]) if r["type"] in TYPE_ORDER else 9, int(r.get("rank_in_type") or 99)))
    pf = inp["portfolio"] or {}
    pf_pos = {p.get("ticker"): p for p in (pf.get("positions") or []) if isinstance(p, dict)}
    img = site / "img"
    img.mkdir(parents=True, exist_ok=True)
    cards, summary, repro = [], [], []
    for r in picks:
        d = inp["cands"].get(r["id"])
        if not d:
            continue
        for src in (d.get("charts") or {}).values():
            if src and (ROOT / src).exists():
                shutil.copy2(ROOT / src, img / Path(src).name)
        cards.append(build_card(d, r, inp, inp["glossary"], img, pf_pos))
        oos = ((d.get("metrics") or {}).get("out_of_sample") or {}).get("usd") or {}
        summary.append({"id": d["id"], "ticker": d["ticker"], "name": d.get("name"), "type": d["position_type"],
                        "verdict": (d.get("review") or {}).get("verdict"), "oos_sharpe": oos.get("sharpe"),
                        "oos_cagr": oos.get("cagr"), "rubric_total": fnum(r.get("rubric_total"))})
        repro.append(d.get("reproduce"))
    nav = "".join(f'<a href="#card-{esc(s["id"])}" data-type="{esc(s["type"])}">{esc(s["ticker"])}</a>' for s in summary)
    filt = '<button type="button" data-filter="all" class="on">All 12</button>' + "".join(
        f'<button type="button" data-filter="{t}">{esc(TYPE_LABEL[t])}</button>' for t in TYPE_ORDER)
    body = f"""<h1>Positions: one card per pick</h1>
<p class="lead">Each card is a one-page brief for presenting the pick to the team: three plain sentences, the track record split into the years
the screen saw (in-sample) and the years it did not (out-of-sample), the stress windows, what the independent reviewer checked,
and the runners-up that lost. Use <em>Print this card</em> to print one pick on its own page.</p>
<div class="filters">{filt}</div><div class="jump">{nav}</div>
{"".join(cards)}"""
    return body, {"picks": summary}, sorted(set(x for x in repro if x))


# ---------------------------------------------------------------- Compare

def build_compare(inp, end):
    cands, score = inp["cands"], {r["id"]: r for r in inp["score"]}
    series_meta, rolling, metrics = {}, {}, {}
    tickers, local_t = [], []

    def mini(d):
        out = {}
        for w, k in (("in_sample", "is"), ("out_of_sample", "oos")):
            for ccy in ("usd", "local"):
                b = ((d.get("metrics") or {}).get(w) or {}).get(ccy)
                if isinstance(b, dict):
                    out.setdefault(k, {})[ccy] = {x: (round(b[x], 4) if isinstance(b.get(x), (int, float)) else None)
                                                  for x in ("cagr", "vol", "sharpe", "max_drawdown", "info_ratio", "t_stat_ir", "deflated_sharpe")}
        return out

    for cid, d in cands.items():
        sc = score.get(cid, {})
        grp = "overlay" if d["position_type"] == "overlay" else (sc.get("decision") or "candidate")
        if grp == "":
            grp = "candidate"
        key = d["ticker"] if d["position_type"] != "overlay" else "overlay:" + cid
        series_meta[key] = {"label": d["ticker"] if d["position_type"] != "overlay" else cid, "name": d.get("name"), "group": grp,
                            "type": d["position_type"], "verdict": (d.get("review") or {}).get("verdict")}
        metrics[key] = mini(d)
        if d["position_type"] != "overlay":
            tickers.append(d["ticker"])
            ccy = d.get("currency_code") or (d["currency"] if isinstance(d.get("currency"), str) else "")
            if ccy and ccy not in ("USD", "LOCAL", "MIXED"):
                local_t.append(d["ticker"])
        r = d.get("rolling")
        if isinstance(r, dict) and r.get("dates"):
            rolling[key] = {"dates": r["dates"], "sharpe": [None if v is None else round(v, 3) for v in r.get("sharpe", [])],
                            "ir": [None if v is None else round(v, 3) for v in r.get("info_ratio", [])]}
    # controls (faded leaders, non-shortlisted names) from the control CSVs
    colmap = {"cagr": ("cagr_oos",), "sharpe": ("sharpe_oos",), "max_drawdown": ("max_dd_oos", "maxdd_oos"),
              "info_ratio": ("ir_oos", "ir_vs_gld_oos"), "deflated_sharpe": ("deflated_sharpe_oos", "dsr_oos"), "t_stat_ir": ("t_ir_oos", "t_ir_oos")}
    colmap_is = {"cagr": ("cagr_is",), "sharpe": ("sharpe_is",), "max_drawdown": ("max_dd_is", "maxdd_is"),
                 "info_ratio": ("ir_is", "ir_vs_gld_is")}
    known = set(tickers)
    for f, kind in (("us_growth_control.csv", "us_growth_stock"), ("intl_growth_control.csv", "intl_growth_stock"),
                    ("em_bonds_control.csv", "em_bond"), ("other_control.csv", "other")):
        p = CAND / f
        if not p.exists():
            continue
        with open(p, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                t = r.get("ticker")
                if not t or t in known or t in BENCH_TICKERS or t in series_meta:
                    continue
                faded = str(r.get("faded_leader", "")).lower() == "true" or r.get("role") == "faded_leader"
                role = r.get("role", "")
                grp = "benchmark" if role == "benchmark" else ("faded leader" if faded else "control")
                series_meta[t] = {"label": t, "name": r.get("name") or t, "group": grp, "type": kind, "verdict": None}
                mm = {}
                for k, cols in (("oos", colmap), ("is", colmap_is)):
                    blk = {x: next((fnum(r.get(c)) for c in cs if fnum(r.get(c)) is not None), None) for x, cs in cols.items()}
                    mm[k] = {"usd": blk}
                metrics[t] = mm
                tickers.append(t)
                known.add(t)
    for b in BENCH_TICKERS:
        if b not in series_meta:
            series_meta[b] = {"label": b, "name": b, "group": "benchmark", "type": "benchmark", "verdict": None}
            tickers.append(b)
    dates, usd, local = build_growth(ROOT, tickers, end, local_t, BLENDS)
    for b in BLENDS:
        if b in usd:
            series_meta[b] = {"label": b, "name": b.replace("_", " ") + " (monthly rebalanced)", "group": "benchmark", "type": "benchmark", "verdict": None}
    # overlay series from the monthly CSVs
    for cid, d in cands.items():
        if d["position_type"] != "overlay":
            continue
        p = CAND / "overlays" / f"{cid}_monthly.csv"
        if not p.exists():
            continue
        import pandas as pd
        o = pd.read_csv(p, parse_dates=["date"]).set_index("date")
        lv = (1 + o["overlaid_return"]).cumprod()
        lv = pd.concat([pd.Series([1.0], index=[lv.index[0] - pd.offsets.MonthEnd(1)]), lv])
        grid = pd.to_datetime(dates)
        usd["overlay:" + cid] = [None if pd.isna(v) else round(float(v), 4) for v in lv.reindex(grid)]
        series_meta["overlay:" + cid]["name"] = d.get("name", cid) + " (underlying + overlay, monthly CSV)"
    usd = {k: v for k, v in usd.items() if k in series_meta}
    for k in list(series_meta):
        if k not in usd:
            series_meta[k]["no_prices"] = True
    return {"dates": dates, "usd": usd, "local": {k: v for k, v in local.items() if k in series_meta},
            "meta": series_meta, "rolling": rolling, "metrics": metrics, "glossary": inp["glossary"], "end": end}


# ---------------------------------------------------------------- Method page

def doc_section(text, prefix):
    for t, b in mdlite.sections(text):
        if t.startswith(prefix):
            return t, b
    return prefix, ""


def build_method(inp):
    method = read_text(PLAN / "method.md")
    shortlist = read_text(PLAN / "shortlist.md")
    scorecard = read_text(PLAN / "scorecard.md")
    dreq = read_text(PLAN / "data_request.md")
    g = inp["glossary"]
    parts = []

    def block(title, body_md, open_=False, shift=1):
        return f'<details class="sec"{" open" if open_ else ""}><summary>{esc(title)}</summary>{mdlite.md_to_html(body_md, shift)}</details>'

    intro = method.split("## 1.")[0]
    status = re.search(r"\*\*Status:\*\*(.+?)\n\n", intro, re.S)
    parts.append('<section id="method"><h2>1. The pre-registered method</h2>')
    parts.append(f'<p class="lead">{esc(" ".join(status.group(1).split()))}</p>' if status else "")
    brief = re.search(r"Project: .+?\n\n", intro, re.S)
    if brief:
        parts.append(f'<p>{mdlite.inline(" ".join(brief.group(0).split()))}</p>')
    for pre, open_ in (("1.", True), ("2.", False), ("3.", True), ("4.", False), ("5.", False), ("6.", True), ("7.", True), ("8.", False), ("9.", False)):
        t, b = doc_section(method, pre)
        parts.append(block(t, b, open_))
    for pre in ("10.", "11.", "12."):
        t, b = doc_section(method, pre)
        if b:
            parts.append(block(t, b))
    parts.append("</section>")
    t, b = doc_section(method, "13.")
    parts.append(f'<section id="changelog"><h2>2. Change log (method.md section 13)</h2><p>Every change after the method was committed is logged here; none changes a rule. </p>{mdlite.md_to_html(b)}</section>')
    # signals
    t, b = doc_section(shortlist, "Technical signals")
    parts.append(f'<section id="signals"><h2>3. Signal validation: no technical signal was kept</h2>'
                 f'<p class="notice-ok">Each technical signal was tested out of sample, once, by the rule fixed in advance. None passed in any position type, so the technical score is not used in the rubric.</p>'
                 f'{mdlite.md_to_html(b, 1)}'
                 f'{glossary_block(g, ["information_ratio", "t_stat", "out_of_sample"])}</section>')
    t, b = doc_section(shortlist, "Survivorship")
    parts.append(f'<section id="survivorship"><h2>4. Survivorship check</h2>{mdlite.md_to_html(b, 1)}</section>')
    # in-sample vs OOS
    t, b = doc_section(scorecard, "In-sample ranking vs out-of-sample")
    parts.append(f'<section id="oos"><h2>5. In-sample ranking vs out-of-sample results</h2>{mdlite.md_to_html(b, 1)}</section>')
    t, b = doc_section(scorecard, "How the ranking was formed")
    parts.append(f'<section id="rank"><h2>6. How the ranking was formed</h2>{mdlite.md_to_html(b, 1)}</section>')
    # review summary: scorecard text plus a table built from the review files
    t, b = doc_section(scorecard, "Review summary")
    rows = ""
    for name, rev in sorted(inp["reviews"].items()):
        for cid, c in (rev.get("candidates") or {}).items():
            claims = c.get("claims") or []
            npass = sum(1 for x in claims if str(x.get("status", "")).lower().startswith("pass"))
            v = c.get("verdict")
            rows += (f'<tr><td>{esc(cid)}</td><td>{esc(rev.get("type", name))}</td><td><span class="badge {verdict_class(v)}">{esc(verdict_word(v))}</span></td>'
                     f'<td class=num>{npass} of {len(claims)}</td><td class=small>{esc(c.get("notes", ""))}</td></tr>')
    parts.append(f'<section id="reviews"><h2>7. Adversarial review summary</h2>{mdlite.md_to_html(b, 1)}'
                 f'<h3>Verdict for every reviewed candidate</h3><div class="tablewrap"><table><thead><tr><th>Candidate</th><th>Type</th><th>Verdict</th><th>Claims passed</th><th>Reviewer note</th></tr></thead><tbody>{rows}</tbody></table></div></section>')
    # caveats
    cav = re.search(r"Findings that could not be fixed.+?\n\n(?=##)", scorecard, re.S)
    cav_html = mdlite.md_to_html(cav.group(0).replace("\n", " ").replace("Findings that could not be fixed and are carried as caveats:", "").strip()) if cav else ""
    parts.append(f"""<section id="caveats"><h2>8. Caveats</h2>
<ul class="caveats">
<li><strong>Price indices.</strong> Home-market indices used for the local-currency view ignore dividends, which flatters local information ratios.</li>
<li><strong>Point-in-time.</strong> Most international fundamentals could not be rebuilt as they stood in 2017 because the companies do not file with the SEC. They were screened on current statements and flagged.</li>
<li><strong>One out-of-sample regime.</strong> 2018-2026 contained one long growth rally, the 2020 crash, the 2022 rate shock and a strong dollar. A different regime could rank everything differently.</li>
<li><strong>Picks were chosen partly on out-of-sample results.</strong> The rubric uses 2018-2026 data, so the portfolio-level backtest of these 12 names is not a clean test. The walk-forward optimizer weights are out-of-sample by construction; the choice of names is not.</li>
<li><strong>Multiple testing.</strong> With dozens of names per type the best out-of-sample Sharpe is partly luck, which is why deflated Sharpe and t-statistics are shown.</li>
</ul><h3>Carried from the adversarial reviews (scorecard.md)</h3>{cav_html}</section>""")
    # data sources
    heads = [t for t, _ in mdlite.sections(dreq)]
    st = dict(mdlite.sections(dreq)).get(next((h for h in heads if h.startswith("8.")), ""), "")
    ends = {}
    for d in inp["cands"].values():
        dd = d.get("data") or {}
        for k in ("price_start", "price_end"):
            if dd.get(k):
                ends.setdefault(k, []).append(dd[k])
    from collections import Counter
    oos_ends = [(((d.get("metrics") or {}).get("out_of_sample") or {}).get("usd") or {}).get("end") for d in inp["cands"].values()]
    oos_ends = [e for e in oos_ends if e]
    span = (f"Daily prices start {min(ends['price_start'])}; the monthly analysis ends with the last full month, {Counter(oos_ends).most_common(1)[0][0]}." if ends and oos_ends else "")
    lis = "".join(f"<li>{mdlite.inline(h)}</li>" for h in heads)
    parts.append(f'<section id="data"><h2>9. Data sources</h2><p>{esc(span)} Sections of the data request (<code>research/plan/data_request.md</code>):</p><ul>{lis}</ul>{mdlite.md_to_html(st, 2)}</section>')
    # reproduce
    cmds = sorted({d.get("reproduce") for d in inp["cands"].values() if d.get("reproduce")})
    pf = inp["portfolio"] or {}
    pfr = pf.get("reproduce")
    allc = (["python -m research.fetch"] + cmds + ["python research/plan/scorecard.py --write"]
            + ([pfr] if isinstance(pfr, str) else list(pfr or [])) + ["python -m dashboard"])
    parts.append('<section id="reproduce"><h2>10. Reproduce</h2><p>Every number comes from committed code and data. The commands, in order:</p><pre>'
                 + esc("\n".join(dict.fromkeys(c for c in allc if isinstance(c, str)))) + "</pre></section>")
    toc = "".join(f'<a href="#{i}">{esc(t)}</a>' for i, t in (("method", "Method"), ("changelog", "Change log"), ("signals", "Signals"), ("survivorship", "Survivorship"),
                                                          ("oos", "In-sample vs OOS"), ("rank", "Ranking"), ("reviews", "Reviews"), ("caveats", "Caveats"), ("data", "Data"), ("reproduce", "Reproduce")))
    return f'<h1>Method and evidence</h1><div class="jump">{toc}</div>' + "".join(parts), {"sections": heads}, cmds


# ---------------------------------------------------------------- the build

def build(site=DEFAULT_SITE, quiet=False, portfolio_path=None):
    site = Path(site)
    inp = load_inputs(portfolio_path=portfolio_path)
    g = inp["glossary"]
    pf = inp["portfolio"]
    if site.exists():
        for child in site.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    (site / "static").mkdir(parents=True, exist_ok=True)
    (site / "vendor").mkdir(exist_ok=True)
    for f in (PKG / "static").iterdir():
        shutil.copy2(f, site / "static" / f.name)
    try:
        import plotly
    except ImportError as e:
        raise RuntimeError("plotly is required to copy plotly.min.js for offline use: pip install -r requirements.txt") from e
    shutil.copy2(Path(plotly.__file__).parent / "package_data" / "plotly.min.js", site / "vendor" / "plotly.min.js")

    as_of = as_of_date(inp)
    meta = meta_for(inp)
    pf_state = {"missing": pf is None}
    pf_src = ["reports/final/portfolio.json (written by the portfolio builder)"] + ([pf["reproduce"]] if pf and isinstance(pf.get("reproduce"), str) else [])
    base = {"portfolio": pf, "meta": meta, "rules": RULES, "glossary": g, "pf_missing": pf is None}
    pages = {}

    # 1 Overview
    body = f"""<h1>The final portfolio</h1>
{pf_missing_note()}
<p class="lead">$100,000 in 12 positions for 7 years. Everything below is read from <code>reports/final/portfolio.json</code>.</p>
<div id="ov-rules-wrap"><h2>Rule checks</h2><div id="ov-rules" class="badges big"></div></div>
<h2>Where the money is</h2>
<div class="grid4"><div id="ov-pie" class="chart"></div><div id="ov-sleeve" class="chart"></div><div id="ov-region" class="chart"></div><div id="ov-ccy" class="chart"></div></div>
<div id="ov-positions"></div>
<h2>Headline numbers: in-sample and out-of-sample side by side</h2>
<div id="ov-headline"></div>
{glossary_block(g, ["sharpe", "information_ratio", "max_drawdown", "out_of_sample", "in_sample", "non_us_share", "tracking_error", "t_stat", "deflated_sharpe"])}
<h2>Growth of $100,000, eight portfolios</h2>
<p class="small muted">The shaded band is the in-sample period (the data the method was developed on). Click legend entries to hide lines.</p>
<div id="ov-growth" class="chart tall"></div><div id="ov-dd" class="chart"></div>
<h2>Looking forward: the Monte Carlo fan and the five targets</h2>
<div class="cols2"><div id="ov-fan" class="chart"></div><div><div id="ov-targets" class="badges big"></div><p class="small">{esc(g["monte_carlo"]["def"])}</p><div id="ov-mc"></div></div></div>
<div id="ov-more"></div>"""
    pages["index"] = (body, base, ["page_overview.js"], pf_src, True)

    # 2 Positions
    pbody, pdata, prepro = build_positions(inp, site)
    pages["positions"] = (pbody, {**pdata, "pf_missing": pf is None}, [], ["reports/candidates/<ID>.json"] + prepro, False)

    # 3 Compare
    from collections import Counter
    ends = [(((d.get("metrics") or {}).get("out_of_sample") or {}).get("usd") or {}).get("end") for d in inp["cands"].values()]
    ends = [e for e in ends if e]
    end = Counter(ends).most_common(1)[0][0] if ends else "2026-10-31"   # the last full month most files agree on
    cdata = build_compare(inp, end)
    cbody = f"""<h1>Compare any candidates</h1>
<p class="lead">Pick any of the {len(inp["cands"])} candidates (picked, runners-up, dropped, derivative overlays), the faded leaders and the benchmarks.
Growth is built monthly from the price and FX files at build time.</p>
<div class="cmp"><aside><div class="filters" id="cmp-groups"></div><input id="cmp-search" type="search" placeholder="Search ticker or name" aria-label="Search"><div id="cmp-list" class="picklist"></div>
<p><button type="button" id="cmp-picks">The 12 picks</button> <button type="button" id="cmp-clear">Clear</button></p></aside>
<div class="cmpmain"><div class="small">Start date <select id="cmp-start"></select> <label><input type="radio" name="cmp-ccy" value="usd" checked> USD</label> <label><input type="radio" name="cmp-ccy" value="local"> local currency (where it differs)</label></div>
<h2>Growth of $10,000</h2><div id="cmp-growth" class="chart tall"></div>
<h2>Drawdowns</h2><div id="cmp-dd" class="chart"></div>
<div class="cols2"><div><h2>Rolling 36-month Sharpe</h2><div id="cmp-rs" class="chart"></div></div><div><h2>Rolling 36-month information ratio</h2><div id="cmp-ri" class="chart"></div></div></div>
<h2>Metrics: in-sample and out-of-sample, USD and local</h2><div id="cmp-table"></div></div></div>
{glossary_block(g, ["sharpe", "information_ratio", "max_drawdown", "rolling", "local_vs_usd", "in_sample", "out_of_sample", "deflated_sharpe"])}"""
    pages["compare"] = (cbody, cdata, ["page_compare.js"], ["reports/candidates/*.json", "data/research/prices.csv, fx.csv", "python -m dashboard (growth series)"], True)

    # 4 Frontier
    fbody = f"""<h1>Efficient frontiers</h1>{pf_missing_note()}
<p class="lead">For each level of risk, the best expected return the 12 positions can offer. {esc(g["frontier"]["def"])}</p>
<div class="controls" id="fr-toggles"></div>
<div id="fr-chart" class="chart tall"></div><p class="small muted">Hover any point for its weights. Marked portfolios: tangency (best Sharpe), minimum variance, guideline (55/35/10 equal weight), guideline-feasible, and the chosen portfolio.</p>
<div id="fr-table"></div>
{glossary_block(g, ["frontier", "tangency", "min_variance", "ex_ante", "sharpe", "non_us_share", "sleeve_mix"])}"""
    pages["frontier"] = (fbody, base, ["page_frontier.js"], pf_src, True)

    # 5 What-if
    wbody = f"""<h1>What-if: change the weights</h1>{pf_missing_note()}
<p class="lead">Drag the sliders to change each position. Everything recalculates in your browser from the expected returns and covariance in <code>portfolio.json</code>; red marks a broken rule.</p>
<div class="controls"><button type="button" id="wi-chosen">Reset to chosen</button> <button type="button" id="wi-guide">Reset to guideline</button> <button type="button" id="wi-norm">Normalise to 100%</button></div>
<div class="cols2 wi"><div id="wi-sliders"></div><div><div id="wi-out"></div><h2>Stress scenarios</h2><div id="wi-stress-btns" class="controls"></div><div id="wi-stress"></div><div id="wi-chart" class="chart"></div></div></div>
{glossary_block(g, ["sharpe", "volatility", "non_us_share", "sleeve_mix", "stress", "rf"])}"""
    pages["whatif"] = (wbody, base, ["page_whatif.js"], pf_src, True)

    # 6 Method
    mbody, mdata, mrepro = build_method(inp)
    pages["method"] = (mbody, {**mdata, "pf_missing": pf is None}, [], ["research/plan/method.md", "research/plan/shortlist.md", "research/plan/scorecard.md", "research/plan/data_request.md"] + mrepro[:3], False)

    sizes = {}
    for key, title in PAGES:
        body, data, scripts, srcs, plotly_ = pages[key]
        out = render_page(key, title, body, data, scripts, as_of, srcs, plotly_)
        (site / f"{key}.html").write_text(out, encoding="utf-8")
        sizes[f"{key}.html"] = len(out.encode("utf-8"))
    if not quiet:
        print(f"Built {len(PAGES)} pages into {site}")
        for k, v in sizes.items():
            print(f"  {k:<14}{v / 1e6:6.2f} MB")
        if pf is None:
            print("  note: reports/final/portfolio.json not found; Overview, Frontier and What-if show the 'not built yet' state")
    return sizes
