/* Frontier: four efficient frontiers from portfolio.json with marked portfolios. */
(function () {
  "use strict";
  if (PD.pf_missing || !PD.portfolio) { A.showMissing(); return; }
  var pf = PD.portfolio, fr = pf.frontiers || {};
  var $ = function (id) { return document.getElementById(id); };
  var tickers = fr.tickers || A.get(pf, "whatif.tickers") || [];
  var rf = A.get(pf, "whatif.rf");
  var KEYS = [["ex_ante_rule", "Ex-ante, with 70% non-US rule", "ex_ante", "rule_70"], ["ex_ante_norule", "Ex-ante, no rule", "ex_ante", "no_rule"],
    ["ex_post_rule", "Ex-post, with 70% rule", "ex_post", "rule_70"], ["ex_post_norule", "Ex-post, no rule", "ex_post", "no_rule"]];
  var MARKS = [["tangency", "Tangency (best Sharpe)", "star", "#d9622b"], ["min_variance", "Minimum variance", "diamond", "#2a9d8f"],
    ["guideline", "Guideline 55/35/10", "square", "#8a4fbf"], ["guideline_feasible", "Guideline (feasible)", "square-open", "#8a4fbf"], ["chosen", "Chosen portfolio", "x", "#c4325a"]];
  /* Accept both layouts: frontiers.ex_ante_rule.{points, tangency, ...} and frontiers.ex_ante.rule_70.{points, max_sharpe, ...} + ex_ante.portfolios */
  var avail = [];
  KEYS.forEach(function (k) {
    var F = fr[k[0]], par = fr[k[2]] || {};
    if (!F && par[k[3]]) {
      var P = par.portfolios || {}, R = par[k[3]];
      F = { points: R.points, tangency: R.tangency || R.max_sharpe, min_variance: R.min_variance, guideline: R.guideline || P.guideline,
        guideline_feasible: R.guideline_feasible || P.guideline_feasible, chosen: R.chosen || P.chosen || P.chosen_ex_ante, rf: R.rf };
    }
    if (F && F.points) avail.push([k[0], k[1], F]);
  });
  if (!avail.length) { $("fr-chart").innerHTML = A.na("frontiers"); return; }
  var on = {}; avail.forEach(function (k, i) { on[k[0]] = i < 2; });

  var tg = $("fr-toggles");
  tg.innerHTML = avail.map(function (k, i) {
    return '<label><input type="checkbox" data-k="' + k[0] + '"' + (on[k[0]] ? " checked" : "") + '> <span style="color:' + A.COLORS[i] + '">&#9632;</span> ' + A.esc(k[1]) + "</label>";
  }).join("");
  tg.addEventListener("change", function (e) { on[e.target.getAttribute("data-k")] = e.target.checked; draw(); });

  function pt(p) { return p && typeof p === "object" ? p : null; }
  function draw() {
    var traces = [], rows = [];
    avail.forEach(function (k, i) {
      if (!on[k[0]]) return;
      var F = k[2], pts = (F.points || []).filter(pt), col = A.COLORS[i];
      traces.push({ type: "scatter", mode: "lines+markers", name: k[1], legendgroup: k[0], x: pts.map(function (p) { return p.vol; }), y: pts.map(function (p) { return p.ret; }),
        line: { color: col, width: 2 }, marker: { size: 5, color: col }, text: pts.map(function (p) { return A.weightText(p.weights, tickers); }), customdata: pts.map(function (p) { return A.isNum(p.sharpe) ? "Sharpe " + p.sharpe.toFixed(2) : ""; }),
        hovertemplate: "Volatility %{x:.1%}<br>Return %{y:.1%}<br>%{customdata}<br>%{text}<extra>" + k[1] + "</extra>" });
      MARKS.forEach(function (m) {
        var p = pt(F[m[0]]); if (!p) return;
        traces.push({ type: "scatter", mode: "markers", name: m[1] + " (" + k[1] + ")", legendgroup: k[0], showlegend: false, x: [p.vol], y: [p.ret],
          marker: { symbol: m[2], size: 15, color: m[3], line: { color: col, width: 2 } }, text: [A.weightText(p.weights, tickers)],
          hovertemplate: "<b>" + m[1] + "</b> (" + k[1] + ")<br>Volatility %{x:.1%}<br>Return %{y:.1%}<br>%{text}<extra></extra>" });
        rows.push([A.esc(k[1]), A.esc(m[1]), A.pct(p.ret), A.pct(p.vol), A.isNum(p.sharpe) ? A.num(p.sharpe) : (A.isNum(F.rf || rf) && p.vol ? A.num((p.ret - (F.rf || rf)) / p.vol) : "n/a"), A.weightText(p.weights, tickers).replace(/<br>/g, ", ")]);
      });
    });
    /* legend for the marker shapes */
    MARKS.forEach(function (m) { traces.push({ type: "scatter", mode: "markers", name: m[1], x: [null], y: [null], marker: { symbol: m[2], size: 12, color: m[3] } }); });
    A.plot("fr-chart", traces, { title: { text: "Expected return vs volatility", font: { size: 15 } }, xaxis: { title: "Volatility (annual)", tickformat: ".1%" }, yaxis: { title: "Expected annual return", tickformat: ".1%" }, legend: { orientation: "h", y: -0.2 } });
    $("fr-table").innerHTML = rows.length ? "<h2>Marked portfolios</h2>" + A.table(["Frontier", "Portfolio", "Return", "Volatility", A.gl("sharpe") + (A.isNum(rf) ? "" : " (needs rf)"), "Weights"], rows) : "";
  }
  draw();
})();
