"""Smoke tests for the offline dashboard (Phase 6): build into a temp dir and check every page.

The portfolio-dependent pages are tested twice: with no portfolio.json (the "not built yet"
state) and with a small synthetic fixture in the promised layout (marked as a test fixture;
it is never written into reports/).
"""

import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("plotly")

from dashboard import build as dbuild  # noqa: E402

PAGE_FILES = [f"{k}.html" for k, _ in dbuild.PAGES]
ROOT = Path(__file__).resolve().parents[1]


def fake_portfolio():
    """Synthetic portfolio.json in the Phase 5 layout. TEST FIXTURE ONLY: the numbers are random."""
    rng = np.random.default_rng(0)
    picks = ["AVGO", "NVDA", "AMZN", "2330.TW", "BAJFINANCE.NS", "CSU.TO", "PYEMX", "CEMB", "EMB", "HYEM", "IAU", "SLV"]
    sleeve = ["stocks"] * 6 + ["bonds"] * 4 + ["other"] * 2
    w = np.array([0.04, 0.04, 0.04, 0.12, 0.10, 0.10, 0.10, 0.09, 0.09, 0.09, 0.06, 0.13])
    w = w / w.sum()
    dates = [d.strftime("%Y-%m-%d") for d in __import__("pandas").date_range("2010-01-31", "2026-10-31", freq="ME")]
    n = len(dates)

    def mblock(s):
        return {"start": "2010-01-31", "end": "2017-12-31", "months": 96, "cagr": 0.07, "vol": 0.1, "sharpe": s, "max_drawdown": -0.2, "info_ratio": 0.2, "t_stat_ir": 1.0}
    ports = {}
    for k in ["guideline", "guideline_feasible", "optimized", "optimized_overlay", "no_rule", "GUIDE_BENCH", "SIXTY_FORTY", "GLOBAL_6040"]:
        v = 100000 * np.cumprod(1 + rng.normal(0.006, 0.03, n))
        ports[k] = {"weights": dict(zip(picks, map(float, w))), "monthly": {"dates": dates, "value_100k": v.round(0).tolist(), "drawdown": (v / np.maximum.accumulate(v) - 1).round(4).tolist()},
                    "metrics": {"in_sample": mblock(0.8), "out_of_sample": mblock(0.5), "full": mblock(0.6)}, "stress": {}, "rule_checks": {}, "turnover": 0.1, "cost_drag": 0.001}
    fan = {p: (100000 * (1 + 0.06 + z * 0.12 * np.sqrt(np.arange(85) / 12 + 1e-9) / 4) ** (np.arange(85) / 12)).round(0).tolist() for p, z in {"5": -1.64, "25": -0.67, "50": 0, "75": 0.67, "95": 1.64}.items()}
    pts = [{"ret": 0.04 + 0.01 * i, "vol": 0.06 + 0.012 * i, "weights": dict(zip(picks, map(float, w)))} for i in range(8)]
    fr = {k: {"points": pts, "tangency": pts[4], "min_variance": pts[0], "guideline": pts[2], "guideline_feasible": pts[3], "chosen": pts[5]}
          for k in ("ex_ante_rule", "ex_ante_norule", "ex_post_rule", "ex_post_norule")}
    a = rng.normal(size=(12, 12))
    cov = (a @ a.T) / 12 * 0.02 + np.eye(12) * 0.01
    names = picks
    return {"schema_version": 1, "as_of": "2026-11-07", "settings": {"chosen": "optimized"},
            "positions": [{"ticker": t, "name": t, "sleeve": s, "weight": float(x), "dollars": float(x * 100000), "shares": 10.0, "non_us_share": 1.0 if i in (3, 4, 5, 6, 7, 8, 9) else 0.0,
                           "currency": "USD", "exchange": "NYSE"} for i, (t, s, x) in enumerate(zip(picks, sleeve, w))],
            "rule_checks": {"non_us": {"value": 0.72, "threshold": 0.7, "pass": True}, "sleeve_mix": {"pass": False, "value": 0.6}, "bounds_ok": True},
            "portfolios": ports, "variants": [], "adjustments": {}, "attribution": {},
            "monte_carlo": {"median": 150000.0, "p5": 100000.0, "p95": 230000.0, "prob_loss": 0.06, "prob_beat_inflation": 0.8, "fan": fan},
            "targets": {"growth_median": {"value": 150000.0, "threshold": 145000.0, "pass": True}, "max_drawdown": {"value": -0.2, "threshold": -0.25, "pass": True}},
            "frontiers": fr,
            "whatif": {"tickers": picks, "names": names, "mu": rng.uniform(0.04, 0.12, 12).tolist(), "cov": cov.tolist(),
                       "non_us_share": [1.0 if i in (3, 4, 5, 6, 7, 8, 9) else 0.0 for i in range(12)], "sleeve": sleeve,
                       "stress_returns": {"gfc_2008": (-0.3 * np.ones(12)).tolist(), "inflation_2022": (-0.1 * np.ones(12)).tolist(), "strong_usd": (-0.05 * np.ones(12)).tolist(),
                                          "covid_2020": (-0.2 * np.ones(12)).tolist(), "taper_2013": (-0.04 * np.ones(12)).tolist()}, "rf": 0.04},
            "sensitivity": {}, "reproduce": "python -m portfolio.final --write"}


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.bad, self.blob = [], None
        self._in_blob = False
        self.nav_links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and a.get("src", "").startswith(("http://", "https://", "//")):
            self.bad.append(a["src"])
        if tag == "link" and a.get("href", "").startswith(("http://", "https://", "//")):
            self.bad.append(a["href"])
        if tag == "script" and a.get("id") == "page-data":
            self._in_blob = True
            self.blob = ""
        if tag == "a" and self.getpos() and a.get("href", "").endswith(".html"):
            self.nav_links.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_blob = False

    def handle_data(self, data):
        if self._in_blob:
            self.blob += data


@pytest.fixture(scope="module")
def site_empty(tmp_path_factory):
    out = tmp_path_factory.mktemp("site_empty")
    t0 = time.time()
    dbuild.build(out, quiet=True, portfolio_path=out / "does_not_exist.json")
    return out, time.time() - t0


@pytest.fixture(scope="module")
def site_full(tmp_path_factory):
    out = tmp_path_factory.mktemp("site_full")
    pf = out.parent / "fake_portfolio.json"
    pf.write_text(json.dumps(fake_portfolio()), encoding="utf-8")
    dbuild.build(out, quiet=True, portfolio_path=pf)
    return out


@pytest.mark.parametrize("fixture", ["site_empty", "site_full"])
def test_every_page_has_nav_blob_and_no_external_assets(fixture, request):
    site = request.getfixturevalue(fixture)
    site = site[0] if isinstance(site, tuple) else site
    for name in PAGE_FILES:
        p = site / name
        assert p.exists(), name
        text = p.read_text(encoding="utf-8")
        assert len(text.encode("utf-8")) < 8_000_000, f"{name} is over 8 MB"
        parser = _Scripts()
        parser.feed(text)
        assert not parser.bad, f"{name} loads external assets: {parser.bad}"
        assert "<nav>" in text and all(f'href="{f}"' in text for f in PAGE_FILES), f"{name} lacks the nav bar"
        assert parser.blob is not None, f"{name} has no data blob"
        json.loads(parser.blob)   # must parse
        assert text.count('id="page-data"') == 1
        assert "Data as of" in text and "Rebuild:" in text, f"{name} lacks the footer"
    assert (site / "vendor" / "plotly.min.js").stat().st_size > 1_000_000
    assert (site / "static" / "style.css").exists() and (site / "static" / "app.js").exists()


def test_missing_portfolio_state_and_build_speed(site_empty):
    site, secs = site_empty
    assert secs < 30
    for name in ("index.html", "frontier.html", "whatif.html"):
        text = (site / name).read_text(encoding="utf-8")
        assert 'id="pf-missing"' in text and "Portfolio results not built yet" in text
        data = _blob(text)
        assert data["pf_missing"] is True and data["portfolio"] is None


def _blob(text):
    p = _Scripts()
    p.feed(text)
    return json.loads(p.blob)


def test_positions_cards(site_empty):
    site, _ = site_empty
    text = (site / "positions.html").read_text(encoding="utf-8")
    assert text.count('<article class="card"') == 12
    assert text.count("How to explain this pick") == 12
    for t in ("NVDA", "2330.TW", "IAU", "EMB"):
        assert t in text
    assert "Runners-up in this type" in text
    assert re.search(r'<img src="img/NVDA_growth\.png"', text)
    assert (site / "img" / "NVDA_growth.png").exists()


def test_compare_has_all_candidates_and_series(site_empty):
    site, _ = site_empty
    d = _blob((site / "compare.html").read_text(encoding="utf-8"))
    cands = [p for p in (ROOT / "reports" / "candidates").glob("*.json") if "id" in json.loads(p.read_text(encoding="utf-8"))]
    assert len(cands) == 38
    labels = {m["label"] for m in d["meta"].values()}
    for p in cands:
        c = json.loads(p.read_text(encoding="utf-8"))
        assert (c["ticker"] if c["position_type"] != "overlay" else c["id"]) in labels
    assert len(d["dates"]) > 190 and d["dates"][0] == "2009-12-31"
    nv = d["usd"]["NVDA"]
    assert len(nv) == len(d["dates"]) and nv[0] == 1.0 and nv[-1] > 20
    assert "NVDA" in d["rolling"] and "IVW" in d["usd"] and "SIXTY_FORTY" in d["usd"]
    assert "2330.TW" in d["local"]


def test_method_page_content(site_empty):
    site, _ = site_empty
    text = (site / "method.html").read_text(encoding="utf-8")
    for needle in ("Change log", "Signal validation", "no technical signal", "Caveats", "Reproduce", "Adversarial review summary"):
        assert needle.lower() in text.lower(), needle
    assert "python -m dashboard" in text


def test_full_portfolio_build_embeds_data(site_full):
    for name in ("index.html", "frontier.html", "whatif.html"):
        text = (site_full / name).read_text(encoding="utf-8")
        d = _blob(text)
        assert d["pf_missing"] is False
        assert len(d["portfolio"]["portfolios"]) == 8
        assert d["meta"]["NVDA"]["position_type"] == "us_growth_stock"
    assert 'Data as of <strong>2026-11-07</strong>' in (site_full / "index.html").read_text(encoding="utf-8")


def test_real_portfolio_json_if_present(tmp_path):
    """When the portfolio builder has written reports/final/portfolio.json, the pages embed it and carry its as_of date."""
    pf = ROOT / "reports" / "final" / "portfolio.json"
    if not pf.exists():
        pytest.skip("reports/final/portfolio.json not built yet")
    dbuild.build(tmp_path, quiet=True)
    real = json.loads(pf.read_text(encoding="utf-8"))
    for name in ("index.html", "frontier.html", "whatif.html"):
        d = _blob((tmp_path / name).read_text(encoding="utf-8"))
        assert d["pf_missing"] is False and d["portfolio"]["as_of"] == real["as_of"]
        assert len(d["portfolio"]["positions"]) == len(real["positions"])
    assert f'Data as of <strong>{real["as_of"]}</strong>' in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_mdlite_basics():
    from dashboard.mdlite import md_to_html
    out = md_to_html("## T\n\n| a | b |\n|---|---|\n| **x** | `y` |\n\n- one\n- two\n\ntext <b>")
    assert "<table" in out and "<strong>x</strong>" in out and "<li>two</li>" in out and "&lt;b&gt;" in out


def test_headless_browser_no_console_errors(site_full):
    sync = pytest.importorskip("playwright.sync_api", reason="Playwright is not installed; take screenshots by hand (reports/final/screenshots/README.md)")
    with sync.sync_playwright() as pw:
        br = pw.chromium.launch()
        for name in PAGE_FILES:
            page = br.new_page()
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto((site_full / name).as_uri())
            page.wait_for_timeout(500)
            assert not errors, f"{name}: {errors}"
        br.close()
