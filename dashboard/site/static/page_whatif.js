/* What-if: change position weights and recompute return, volatility, Sharpe, rules and stress losses in the browser. */
(function () {
  "use strict";
  if (PD.pf_missing || !PD.portfolio) { A.showMissing(); return; }
  var pf = PD.portfolio, wi = pf.whatif, $ = function (id) { return document.getElementById(id); };
  if (!wi || !wi.tickers || !wi.mu || !wi.cov) { $("wi-out").innerHTML = A.na("whatif (tickers, mu, cov)"); return; }
  var R = Object.assign({}, PD.rules), T = wi.tickers, n = T.length, meta = PD.meta || {};
  var bounds = wi.bounds || { stock: [R.stock_min, R.stock_max], fund: [0.01, R.fund_max], other: [0.01, R.other_max] };
  var bands = wi.sleeve_bands || A.get(pf, "settings.sleeve_bands") || null;
  var minNU = A.isNum(+wi.min_non_us) ? +wi.min_non_us : R.non_us_min;
  var rf = A.isNum(wi.rf) ? wi.rf : 0.04, rfNote = A.isNum(wi.rf) ? "Sharpe subtracts the risk-free rate in portfolio.json (" + A.pct(rf, 2) + ")" : "risk-free rate assumed 4% (not in portfolio.json)";
  var sleeve = T.map(function (t, i) { return A.sleeveOf((wi.sleeve || [])[i]); });
  var rawSleeve = T.map(function (t, i) { return (wi.sleeve || [])[i]; });
  var kind = T.map(function (t, i) {
    if (wi.kind && wi.kind[i]) return wi.kind[i];
    var pt = (meta[t] || {}).position_type;
    if (pt === "us_growth_stock" || pt === "intl_growth_stock") return "stock";
    if (pt === "em_bond") return "fund";
    if (pt === "other") return "other";
    return sleeve[i] === "stocks" ? "stock" : sleeve[i] === "bonds" ? "fund" : "other";
  });
  var isPick = T.map(function (t, i) { return wi.pick ? !!wi.pick[i] : true; });
  var nonUS = T.map(function (t, i) { return +(wi.non_us_share || [])[i] || 0; });
  // "Chosen" = the forward-looking order list (ex-ante weights John holds today), not the last walk-forward weights.
  var chosenW = A.weightsMap(((pf.positions || []).length ? (function () { var o = {}; pf.positions.forEach(function (p) { o[p.ticker] = p.weight; }); return o; })() : null) || A.get(pf, "portfolios." + A.chosenKey() + ".weights"), T);
  var guideW = A.weightsMap(A.get(pf, "portfolios.guideline.weights"), T);
  var w = T.map(function (t) { return chosenW[t] || 0; });
  var scen = wi.stress_returns || {};
  var SCEN_LABEL = { gfc_2008: "GFC 2008", inflation_2022: "Inflation shock 2022", strong_usd: "Strong USD", usd_2014_15: "Strong USD 2014-15", usd_2021_22: "Strong USD 2021-22", covid_2020: "Covid 2020", taper_2013: "Taper tantrum 2013" };
  var sel = Object.keys(scen)[0];
  var SLN = { stocks: "Stocks", bonds: "Bonds", other: "Other" };

  var html = "";
  [true, false].forEach(function (pk) {
    if (!pk && !isPick.some(function (x) { return !x; })) return;
    html += '<h3>' + (pk ? "The 12 picks" : "Runners-up (zero in the chosen portfolio)") + "</h3>";
    ["stocks", "bonds", "other"].forEach(function (s) {
      var rows = "";
      T.forEach(function (t, i) {
        if (sleeve[i] !== s || isPick[i] !== pk) return;
        rows += '<div class="slider" id="row-' + i + '"><label for="s' + i + '" title="' + A.esc((wi.names || [])[i] || t) + '">' + A.esc(t) + '</label><input type="range" id="s' + i + '" min="0" max="40" step="0.1" value="0"><output id="o' + i + '">0.0%</output></div>';
      });
      if (rows) html += '<div class="sleevehead">' + SLN[s] + (pk ? ' <span id="sl-' + s + '" class="muted"></span>' : "") + "</div>" + rows;
    });
  });
  html += '<p class="sleevehead">Total <span id="wi-sum"></span></p><p class="small muted">' + A.esc(rfNote) + ". Position bounds and sleeve bands come from portfolio.json (" + A.esc(R.source) + ").</p>";
  $("wi-sliders").innerHTML = html;
  T.forEach(function (t, i) { $("s" + i).addEventListener("input", function (e) { w[i] = parseFloat(e.target.value) / 100; update(); }); });

  function setW(map) { w = T.map(function (t) { return map[t] || 0; }); update(); }
  $("wi-chosen").addEventListener("click", function () { setW(chosenW); });
  $("wi-guide").addEventListener("click", function () { setW(guideW); });
  $("wi-norm").addEventListener("click", function () { var s = w.reduce(function (a, b) { return a + b; }, 0); if (s > 0) w = w.map(function (x) { return x / s; }); update(); });
  $("wi-stress-btns").innerHTML = Object.keys(scen).map(function (k) { return '<button type="button" data-s="' + k + '">' + A.esc(SCEN_LABEL[k] || k.replace(/_/g, " ")) + "</button>"; }).join("");
  $("wi-stress-btns").addEventListener("click", function (e) { var k = e.target.getAttribute && e.target.getAttribute("data-s"); if (k) { sel = k; update(); } });

  function update() {
    var sum = 0, ret = 0, nu = 0, sl3 = { stocks: 0, bonds: 0, other: 0 }, v = 0, i, j, viol = [];
    for (i = 0; i < n; i++) {
      sum += w[i]; ret += w[i] * wi.mu[i]; nu += w[i] * nonUS[i]; sl3[sleeve[i]] += w[i];
      for (j = 0; j < n; j++) v += w[i] * w[j] * wi.cov[i][j];
    }
    var vol = Math.sqrt(Math.max(v, 0)), sharpe = vol > 0 ? (ret - rf) / vol : null;
    var badSum = Math.abs(sum - 1) > 0.0005;
    if (badSum) viol.push("weights sum to " + A.pct(sum, 1) + ", not 100% (use Normalise)");
    var nuBad = nu < minNU - 1e-9; if (nuBad) viol.push("non-US share " + A.pct(nu, 1) + " is below " + A.pct(minNU, 0));
    var slBad = {}, bandKey = { stocks: "equity", bonds: "bonds", other: "other" };
    Object.keys(sl3).forEach(function (s) {
      var lo, hi, bd = bands && bands[bandKey[s]];
      if (bd) { lo = bd[0]; hi = bd[1]; } else { lo = R.sleeve_target[s] - R.sleeve_tolerance; hi = R.sleeve_target[s] + R.sleeve_tolerance; }
      slBad[s] = sl3[s] < lo - 1e-9 || sl3[s] > hi + 1e-9;
      if (slBad[s]) viol.push(s + " sleeve " + A.pct(sl3[s], 1) + " is outside " + A.pct(lo, 0) + " to " + A.pct(hi, 0));
      var e = $("sl-" + s); if (e) { e.innerHTML = A.pct(sl3[s], 1) + " (band " + A.pct(lo, 0) + "-" + A.pct(hi, 0) + ")"; e.style.color = slBad[s] ? "#b3261e" : ""; }
    });
    for (i = 0; i < n; i++) {
      var b = bounds[kind[i]] || [0, 1], held = w[i] > 0.0005, bad = w[i] > b[1] + 1e-9 || (held && w[i] < b[0] - 1e-9);
      if (bad) viol.push(T[i] + " at " + A.pct(w[i], 1) + " is outside its " + A.pct(b[0], 0) + " to " + A.pct(b[1], 0) + " bound");
      $("row-" + i).classList.toggle("bad", bad);
      $("s" + i).value = (w[i] * 100).toFixed(1); $("o" + i).textContent = (w[i] * 100).toFixed(1) + "%";
    }
    $("wi-sum").innerHTML = '<b style="color:' + (badSum ? "#b3261e" : "#1a7f4b") + '">' + A.pct(sum, 1) + "</b>";
    function big(label, val, bad) { return '<div class="bignum' + (bad ? " bad" : "") + '"><b>' + val + "</b><span>" + label + "</span></div>"; }
    $("wi-out").innerHTML = big("Expected return (w' mu)", A.pct(ret, 2)) + big("Volatility", A.pct(vol, 2)) + big(A.gl("sharpe"), A.num(sharpe)) +
      big(A.gl("non_us_share", "Non-US share"), A.pct(nu, 1), nuBad) + big("Stocks / bonds / other", A.pct(sl3.stocks, 0) + " / " + A.pct(sl3.bonds, 0) + " / " + A.pct(sl3.other, 0), slBad.stocks || slBad.bonds || slBad.other) +
      "<div>" + (viol.length ? '<span class="badge fail">RULES BROKEN</span><ul>' + viol.map(function (x) { return "<li>" + A.esc(x) + "</li>"; }).join("") + "</ul>" : '<span class="badge pass">ALL RULES MET</span>') + "</div>";
    /* stress: loss on the part of the mix that has history in the window */
    function loss(k) {
      var l = 0, miss = 0; for (var a = 0; a < n; a++) { var r = scen[k][a]; if (r == null) miss += w[a]; else l += w[a] * r; }
      return { loss: l, missing: miss };
    }
    var rows = Object.keys(scen).map(function (k) {
      var x = loss(k);
      return { cls: k === sel ? "hl" : "", cells: [A.esc(SCEN_LABEL[k] || k), A.pct(x.loss, 1), x.missing > 0.0005 ? A.pct(x.missing, 1) + " of the mix has no history" : "full coverage"] };
    });
    $("wi-stress").innerHTML = A.table(["Scenario (" + A.gl("stress", "stress") + " return on this mix)", "Estimated portfolio return", "Coverage"], rows);
    document.querySelectorAll("#wi-stress-btns button").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-s") === sel); });
    if (sel && scen[sel]) {
      var idx = T.map(function (t, a) { return a; }).filter(function (a) { return w[a] > 0.0005; });
      var contrib = idx.map(function (a) { return scen[sel][a] == null ? null : w[a] * scen[sel][a]; });
      A.plot("wi-chart", [{ type: "bar", x: idx.map(function (a) { return T[a]; }), y: contrib, marker: { color: contrib.map(function (c) { return c != null && c < 0 ? "#b3261e" : "#1a7f4b"; }) },
        hovertemplate: "%{x}: %{y:.2%}<extra></extra>" }], { title: { text: "Contribution to the " + (SCEN_LABEL[sel] || sel) + " result, by position (gaps = no history)", font: { size: 15 } }, yaxis: { tickformat: ".1%" }, showlegend: false });
    }
  }
  update();
})();
