/* Shared helpers. Every page embeds its data in <script type="application/json" id="page-data">,
   so nothing is fetched and the site works from file://. */
(function () {
  "use strict";
  var el = document.getElementById("page-data");
  var PD = el ? JSON.parse(el.textContent) : {};
  window.PD = PD;
  var A = (window.A = {});

  A.COLORS = ["#1f5fa8", "#d9622b", "#2a9d8f", "#8a4fbf", "#c2a100", "#c4325a", "#4d7c0f", "#5b6770", "#0e7490", "#a16207", "#be185d", "#3f6212"];
  A.esc = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  };
  A.isNum = function (x) { return typeof x === "number" && isFinite(x); };
  A.num = function (x, d) { return A.isNum(x) ? x.toFixed(d == null ? 2 : d) : "n/a"; };
  A.pct = function (x, d) { return A.isNum(x) ? (x * 100).toFixed(d == null ? 1 : d) + "%" : "n/a"; };
  A.money = function (x) { return A.isNum(x) ? "$" + Math.round(x).toLocaleString("en-US") : "n/a"; };
  A.get = function (o, path) {
    var cur = o, parts = path.split(".");
    for (var i = 0; i < parts.length; i++) { if (cur == null) return undefined; cur = cur[parts[i]]; }
    return cur;
  };
  A.na = function (key) { return '<span class="muted">not available (' + A.esc(key) + ")</span>"; };
  A.badge = function (ok, text, extra) {
    var cls = ok === true ? "pass" : ok === false ? "fail" : "none";
    return '<span class="badge ' + cls + '">' + (ok === true ? "PASS " : ok === false ? "FAIL " : "") + A.esc(text) + (extra ? " <small>" + A.esc(extra) + "</small>" : "") + "</span>";
  };
  A.gl = function (key, label) {
    var g = (PD.glossary || {})[key];
    if (!g) return A.esc(label || key);
    return '<abbr title="' + A.esc(g.def) + '">' + A.esc(label || g.label) + "</abbr>";
  };
  A.table = function (head, rows, cls) {
    var h = "<tr>" + head.map(function (x) { return "<th>" + x + "</th>"; }).join("") + "</tr>";
    var b = rows.map(function (r) {
      var rc = r.cls ? ' class="' + r.cls + '"' : "";
      return "<tr" + rc + ">" + (r.cells || r).map(function (c, i) { return "<td" + (i > 0 && !/left/.test(cls || "") ? ' class="num"' : "") + ">" + c + "</td>"; }).join("") + "</tr>";
    }).join("");
    return '<div class="tablewrap"><table class="' + (cls || "") + '"><thead>' + h + "</thead><tbody>" + b + "</tbody></table></div>";
  };
  A.showMissing = function () {
    var n = document.getElementById("pf-missing");
    if (n) n.hidden = false;
    document.querySelectorAll(".chart, #ov-rules-wrap").forEach(function (c) { c.style.display = "none"; });
    ["fr-toggles", "wi-sliders", "wi-out", "wi-stress-btns"].forEach(function (id) { var e = document.getElementById(id); if (e) e.style.display = "none"; });
  };
  A.plot = function (id, traces, layout, config) {
    var node = document.getElementById(id);
    if (!node || typeof Plotly === "undefined") return;
    var lay = Object.assign({
      font: { family: "Segoe UI, system-ui, Arial, sans-serif", size: 14, color: "#1c2530" },
      paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff", margin: { l: 64, r: 24, t: 44, b: 52 },
      legend: { orientation: "h", y: -0.18 }, colorway: A.COLORS, hovermode: "closest"
    }, layout || {});
    Plotly.newPlot(node, traces, lay, Object.assign({ responsive: true, displaylogo: false }, config || {}));
  };
  /* Weights may arrive as {ticker: w} or as an array aligned to a ticker list. */
  A.weightsMap = function (w, tickers) {
    var out = {};
    if (Array.isArray(w)) { (tickers || []).forEach(function (t, i) { out[t] = +w[i] || 0; }); }
    else if (w && typeof w === "object") { Object.keys(w).forEach(function (t) { out[t] = +w[t] || 0; }); }
    return out;
  };
  A.weightText = function (w, tickers) {
    var m = A.weightsMap(w, tickers);
    return Object.keys(m).filter(function (t) { return m[t] > 0.0005; }).sort(function (a, b) { return m[b] - m[a]; })
      .map(function (t) { return t + " " + (m[t] * 100).toFixed(1) + "%"; }).join("<br>");
  };
  A.blk = function (m) { return m && m.usd ? m.usd : m || {}; };
  A.sleeveOf = function (s) {
    s = String(s || "").toLowerCase();
    if (/stock|equit|growth/.test(s)) return "stocks";
    if (/bond|fixed|credit/.test(s)) return "bonds";
    return "other";
  };
  A.chosenKey = function () {
    var pf = PD.portfolio || {};
    return (pf.settings && (pf.settings.chosen || pf.settings.chosen_portfolio)) || pf.chosen || (pf.monte_carlo && pf.monte_carlo.chosen_portfolio) || "optimized";
  };
  A.PORTS = ["guideline", "guideline_feasible", "optimized", "optimized_overlay", "no_rule", "GUIDE_BENCH", "SIXTY_FORTY", "GLOBAL_6040"];
  A.SLEEVE_LABEL = { us_equity: "US growth stocks", intl_equity: "International growth stocks", em_bonds: "EM bonds", other: "Other (gold, silver)" };
  A.PORT_LABEL = { guideline: "Guideline 55/35/10", guideline_feasible: "Guideline (feasible)", optimized: "Optimized", optimized_overlay: "Optimized + put overlay",
    no_rule: "Optimized, no 70% rule", GUIDE_BENCH: "GUIDE_BENCH (55 ACWX / 35 EMB / 10 GLD)", SIXTY_FORTY: "60/40 (SPY/AGG)", GLOBAL_6040: "Global 60/40 (ACWI/AGG)",
    min_variance: "Minimum variance", optimized_overlay_1contract: "Optimized + 1 put contract" };
  A.jsonBlock = function (title, obj) {
    if (obj == null) return "";
    return "<details><summary>" + A.esc(title) + "</summary><pre>" + A.esc(JSON.stringify(obj, null, 1)).slice(0, 60000) + "</pre></details>";
  };

  document.addEventListener("DOMContentLoaded", function () {
    /* Positions page: filter by type and print one card. */
    document.querySelectorAll("[data-filter]").forEach(function (b) {
      b.addEventListener("click", function () {
        var f = b.getAttribute("data-filter");
        document.querySelectorAll("[data-filter]").forEach(function (x) { x.classList.toggle("on", x === b); });
        document.querySelectorAll(".card, .jump a").forEach(function (c) {
          var t = c.getAttribute("data-type");
          c.style.display = f === "all" || t === f ? "" : "none";
        });
      });
    });
    document.querySelectorAll("[data-print]").forEach(function (b) {
      b.addEventListener("click", function () {
        var card = document.getElementById(b.getAttribute("data-print"));
        document.querySelectorAll(".print-target").forEach(function (c) { c.classList.remove("print-target"); });
        card.classList.add("print-target");
        document.body.setAttribute("data-print-only", "1");
        window.print();
      });
    });
    window.addEventListener("afterprint", function () {
      document.body.removeAttribute("data-print-only");
      document.querySelectorAll(".print-target").forEach(function (c) { c.classList.remove("print-target"); });
    });
  });
})();
