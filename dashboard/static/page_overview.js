/* Overview: the final portfolio, read from portfolio.json (shown as "not built yet" when absent). */
(function () {
  "use strict";
  if (PD.pf_missing || !PD.portfolio) { A.showMissing(); return; }
  var pf = PD.portfolio, meta = PD.meta || {};
  var $ = function (id) { return document.getElementById(id); };
  var chosen = A.chosenKey();
  var ports = pf.portfolios || {};
  var pos = (pf.positions || []).map(function (p) {
    var m = meta[p.ticker] || {};
    return Object.assign({ region: m.region || "n/a" }, p, { currency: p.currency || m.currency || "n/a", name: p.name || m.name });
  });

  /* ---- rule checks -------------------------------------------------- */
  function flatten(o, prefix, out) {
    Object.keys(o || {}).forEach(function (k) {
      var v = o[k], name = prefix ? prefix + " / " + k : k;
      if (typeof v === "boolean") out.push({ name: name, ok: v });
      else if (v && typeof v === "object" && !Array.isArray(v)) {
        var flag = ["pass", "passed", "ok", "satisfied"].filter(function (x) { return typeof v[x] === "boolean"; })[0];
        if (flag) {
          var bits = [];
          ["value", "actual", "threshold", "min", "max", "limit"].forEach(function (x) { if (A.isNum(v[x])) bits.push(x + " " + (Math.abs(v[x]) <= 1.5 ? A.pct(v[x]) : A.num(v[x], 0))); });
          out.push({ name: name, ok: v[flag], detail: bits.join(", ") });
        } else flatten(v, name, out);
      }
    });
    return out;
  }
  var ex = A.get(pf, "rule_checks.ex_ante.check") || A.get(pf, "ex_ante.check") || A.get(pf, "rule_checks.ex_ante");
  var cr = A.get(ports, chosen + ".rule_checks") || {};
  var st = pf.settings || {}, minNU = st.min_non_us || (PD.rules || {}).non_us_min;
  var bands = st.sleeve_bands || {};
  var out = [];
  if (ex) {
    out.push({ name: "non-US share at least " + A.pct(minNU, 0), ok: ex.non_us_ok, detail: "order list " + A.pct(ex.non_us_share, 1) });
    var g = ex.groups || {}, tg0 = (PD.rules || {}).sleeve_target, tol = (PD.rules || {}).sleeve_tolerance;
    [["equity", "stocks"], ["bonds", "bonds"], ["other", "other"]].forEach(function (x) {
      var lo, hi, bd = bands[x[0]];
      if (bd) { lo = bd[0]; hi = bd[1]; } else { lo = tg0[x[1]] - tol; hi = tg0[x[1]] + tol; }
      if (A.isNum(g[x[0]])) out.push({ name: x[1] + " mix vs 55 / 35 / 10", ok: g[x[0]] >= lo - 1e-9 && g[x[0]] <= hi + 1e-9, detail: A.pct(g[x[0]], 0) + " (band " + A.pct(lo, 0) + " to " + A.pct(hi, 0) + ")" });
    });
    out.push({ name: "single-position bounds", ok: ex.bounds_ok, detail: (ex.bound_violations || []).join(", ") });
    out.push({ name: "long-only, sums to 100%", ok: ex.sum_ok && ex.long_only_ok });
  }
  var cnt = {}; pos.forEach(function (p) { var t = (meta[p.ticker] || {}).position_type; cnt[t] = (cnt[t] || 0) + 1; });
  var cntr = PD.rules.counts;
  Object.keys(cntr).forEach(function (t) {
    var c = cnt[t] || 0, lo = cntr[t][0], hi = cntr[t][1];
    out.push({ name: (A.SLEEVE_LABEL[{ us_growth_stock: "us_equity", intl_growth_stock: "intl_equity", em_bond: "em_bonds", other: "other" }[t]] || t) + ": count", ok: c >= lo && c <= hi, detail: c + " held (need " + (lo === hi ? lo : lo + " to " + hi) + ")" });
  });
  if (cr.all_rebalances_ok !== undefined) {
    out.push({ name: "walk-forward: non-US share at every rebalance", ok: cr.non_us_ok_all, detail: "lowest " + A.pct(cr.min_target_non_us_share, 1) });
    out.push({ name: "walk-forward: sleeve bands at every rebalance", ok: cr.sleeves_ok_all });
    out.push({ name: "walk-forward: bounds at every rebalance", ok: cr.bounds_ok_all });
  }
  if (!out.length) out = flatten(pf.rule_checks || {}, "", []);
  $("ov-rules").innerHTML = out.length ? out.map(function (c) { return A.badge(c.ok, c.name, c.detail); }).join("") : A.na("rule_checks");
  var gl = ["guideline", "guideline_feasible"].filter(function (k) { return A.get(pf, "rule_checks." + k); }).map(function (k) {
    var c = pf.rule_checks[k];
    return [A.esc(A.PORT_LABEL[k]), A.pct(c.non_us_share, 1), A.badge(c.non_us_ok, "non-US"), A.badge(c.groups_ok, "mix"), A.badge(c.bounds_ok, "bounds" + ((c.bound_violations || []).length ? ": " + c.bound_violations.join(", ") : ""))];
  });
  if (gl.length) $("ov-rules").insertAdjacentHTML("afterend", A.table(["Reference portfolio", "Non-US share", "70% rule", "Sleeve mix", "Bounds"], gl, "left") +
    (A.get(pf, "rule_checks.summary") ? '<p class="small">' + A.esc(pf.rule_checks.summary) + "</p>" : ""));

  /* ---- allocation charts -------------------------------------------- */
  function agg(keyf) {
    var m = {};
    pos.forEach(function (p) { var k = keyf(p) || "n/a"; m[k] = (m[k] || 0) + (A.isNum(p.dollars) ? p.dollars : (p.weight || 0) * 100000); });
    return m;
  }
  function bar(id, title, m) {
    var ks = Object.keys(m).sort(function (a, b) { return m[b] - m[a]; });
    A.plot(id, [{ type: "bar", x: ks.map(function (k) { return m[k]; }), y: ks, orientation: "h", marker: { color: A.COLORS[0] },
      text: ks.map(function (k) { return A.money(m[k]); }), textposition: "auto", hovertemplate: "%{y}: $%{x:,.0f}<extra></extra>" }],
      { title: { text: title, font: { size: 15 } }, yaxis: { autorange: "reversed" }, xaxis: { tickprefix: "$", tickformat: "," }, margin: { l: 150, r: 20, t: 44, b: 40 }, showlegend: false });
  }
  var sorted = pos.slice().sort(function (a, b) { return (b.dollars || 0) - (a.dollars || 0); });
  A.plot("ov-pie", [{ type: "pie", labels: sorted.map(function (p) { return p.ticker; }), values: sorted.map(function (p) { return A.isNum(p.dollars) ? p.dollars : p.weight; }),
    hole: 0.4, textinfo: "label+percent", sort: false, hovertemplate: "%{label}<br>$%{value:,.0f}<extra></extra>" }],
    { title: { text: "By position", font: { size: 15 } }, showlegend: false, margin: { l: 10, r: 10, t: 44, b: 10 } });
  bar("ov-sleeve", "By sleeve", agg(function (p) { return A.SLEEVE_LABEL[p.sleeve] || p.sleeve; }));
  bar("ov-region", "By country / region", agg(function (p) { return p.region; }));
  bar("ov-ccy", "By currency", agg(function (p) { return p.currency; }));

  $("ov-positions").innerHTML = "<h2>Positions</h2>" + A.table(
    ["Ticker", "Name", "Sleeve", "Weight", "Dollars", "Shares", A.gl("non_us_share", "Non-US share"), "Currency", "Exchange"],
    sorted.map(function (p) {
      return [A.esc(p.ticker), A.esc(p.name), A.esc(A.SLEEVE_LABEL[p.sleeve] || p.sleeve), A.pct(p.weight), A.money(p.dollars), A.isNum(p.shares) ? p.shares.toLocaleString("en-US") : "n/a",
        A.pct(p.non_us_share, 0), A.esc(p.currency), A.esc(p.exchange || "n/a")];
    }), "left");

  /* ---- headline table ------------------------------------------------ */
  var names = A.PORTS.filter(function (k) { return ports[k]; });
  Object.keys(ports).forEach(function (k) { if (names.indexOf(k) < 0) names.push(k); });
  function met(k, w) { return A.blk(A.get(ports[k], "metrics." + w)); }
  var rows = names.map(function (k) {
    var I = met(k, "in_sample"), O = met(k, "out_of_sample"), F = met(k, "full");
    return { cls: k === chosen ? "hl" : "", cells: [
      A.esc(A.PORT_LABEL[k] || k) + (k === chosen ? " <small>(chosen)</small>" : ""),
      A.num(I.sharpe), A.num(O.sharpe), A.num(I.info_ratio), A.num(O.info_ratio),
      A.pct(I.cagr), A.pct(O.cagr), A.pct(I.max_drawdown), A.pct(O.max_drawdown), A.pct(F.max_drawdown)] };
  });
  $("ov-headline").innerHTML = A.table(
    ["Portfolio", A.gl("sharpe") + " IS", "OOS", A.gl("information_ratio", "Info ratio") + " IS", "OOS", "CAGR IS", "OOS", A.gl("max_drawdown") + " IS", "OOS", "Full"], rows);
  var C = met(chosen, "out_of_sample"), G = met("GUIDE_BENCH", "out_of_sample"), S = met("SIXTY_FORTY", "out_of_sample");
  function mcv(o) {
    o = o || {};
    var pick = function (a, b) { return o[a] !== undefined ? o[a] : o[b]; };
    return { median: pick("median_ending_value", "median"), p5: pick("p5_ending_value", "p5"), p95: pick("p95_ending_value", "p95"), prob_loss: pick("prob_nominal_loss", "prob_loss"),
      prob_beat_inflation: o.prob_beat_inflation, fan: o.fan, drift: o.drift_annual, dd: o.median_path_max_drawdown, dd25: o.prob_path_drawdown_worse_than_25pct };
  }
  var mc0 = pf.monte_carlo || {}, mc = mcv(mc0.forward || mc0), mcH = mc0.historical ? mcv(mc0.historical) : null;
  function tile(label, val, ref) { return '<div class="bignum"><b>' + val + "</b><span>" + label + (ref ? "<br>" + ref : "") + "</span></div>"; }
  var med = mc.median;
  $("ov-headline").insertAdjacentHTML("afterbegin",
    tile("Out-of-sample Sharpe (chosen)", A.num(C.sharpe), "GUIDE_BENCH " + A.num(G.sharpe) + " | 60/40 " + A.num(S.sharpe)) +
    tile("Out-of-sample information ratio", A.num(C.info_ratio), "vs GUIDE_BENCH") +
    tile("Out-of-sample max drawdown", A.pct(C.max_drawdown), "GUIDE_BENCH " + A.pct(G.max_drawdown) + " | 60/40 " + A.pct(S.max_drawdown)) +
    tile("Expected 7-year value (Monte Carlo median)", A.isNum(med) ? (med > 1000 ? A.money(med) : A.pct(med)) : "n/a", "5th to 95th: " + (A.isNum(mc.p5) ? (mc.p5 > 1000 ? A.money(mc.p5) : A.pct(mc.p5)) : "n/a") + " to " + (A.isNum(mc.p95) ? (mc.p95 > 1000 ? A.money(mc.p95) : A.pct(mc.p95)) : "n/a")));

  /* ---- growth and drawdown ------------------------------------------- */
  var oosStart = (A.get(pf, "settings.out_of_sample") || [])[0] || A.get(pf, "settings.oos_start") || "2018-01-01";
  var gtr = [], dtr = [], first = null;
  names.forEach(function (k, i) {
    var mo = ports[k].monthly; if (!mo || !mo.dates) return;
    if (!first || mo.dates[0] < first) first = mo.dates[0];
    var w = k === chosen ? 4 : 2;
    var col = A.COLORS[i % A.COLORS.length];
    gtr.push({ type: "scatter", mode: "lines", name: A.PORT_LABEL[k] || k, x: mo.dates, y: mo.value_100k, line: { width: w, color: col, dash: /BENCH|SIXTY|GLOBAL/.test(k) ? "dot" : "solid" }, hovertemplate: "%{x|%b %Y}: $%{y:,.0f}<extra>" + (A.PORT_LABEL[k] || k) + "</extra>" });
    dtr.push({ type: "scatter", mode: "lines", name: A.PORT_LABEL[k] || k, x: mo.dates, y: mo.drawdown, line: { width: w, color: col, dash: /BENCH|SIXTY|GLOBAL/.test(k) ? "dot" : "solid" }, showlegend: false, hovertemplate: "%{x|%b %Y}: %{y:.1%}<extra>" + (A.PORT_LABEL[k] || k) + "</extra>" });
  });
  var shade = first ? [{ type: "rect", xref: "x", yref: "paper", x0: first, x1: oosStart, y0: 0, y1: 1, fillcolor: "rgba(31,95,168,0.10)", line: { width: 0 } }] : [];
  if (!gtr.length) { $("ov-growth").innerHTML = A.na("portfolios.*.monthly"); $("ov-dd").innerHTML = ""; }
  else {
    A.plot("ov-growth", gtr, { shapes: shade, title: { text: "Growth of $100,000 (shaded = in-sample)", font: { size: 15 } }, yaxis: { tickprefix: "$", tickformat: "," }, legend: { orientation: "h", y: -0.12 },
      annotations: first ? [{ x: first, xanchor: "left", yref: "paper", y: 1, text: "in-sample", showarrow: false, font: { color: "#1f5fa8", size: 12 } }] : [] });
    A.plot("ov-dd", dtr, { shapes: shade, title: { text: "Drawdown from the previous peak", font: { size: 15 } }, yaxis: { tickformat: ".0%" } });
  }

  /* ---- Monte Carlo fan and targets ------------------------------------ */
  function drawFan(m, label) {
    var fan = m.fan, ftr = [];
    if (fan && typeof fan === "object") {
      var ks = Object.keys(fan).filter(function (k) { return k !== "months" && Array.isArray(fan[k]); }).sort(function (a, b) { return parseFloat(a.replace(/[^0-9.]/g, "")) - parseFloat(b.replace(/[^0-9.]/g, "")); });
      var n = (fan[ks[0]] || []).length, xs = fan.months ? fan.months.map(function (x) { return x / 12; }) : []; if (!xs.length) for (var i = 0; i < n; i++) xs.push(i / 12);
      var lo = ks[0], hi = ks[ks.length - 1], midk = ks.filter(function (k) { return parseFloat(k.replace(/[^0-9.]/g, "")) === 50; })[0];
      ftr.push({ type: "scatter", mode: "lines", x: xs, y: fan[lo], line: { width: 0 }, showlegend: false, hoverinfo: "skip" });
      ftr.push({ type: "scatter", mode: "lines", x: xs, y: fan[hi], fill: "tonexty", fillcolor: "rgba(31,95,168,0.18)", line: { width: 0 }, name: lo + "th to " + hi + "th percentile", hoverinfo: "skip" });
      ks.forEach(function (k) { if (k !== lo && k !== hi && k !== midk) ftr.push({ type: "scatter", mode: "lines", x: xs, y: fan[k], line: { width: 1, dash: "dot", color: "#1f5fa8" }, name: k + "th percentile", hovertemplate: "year %{x:.1f}: $%{y:,.0f}<extra>" + k + "th</extra>" }); });
      if (midk) ftr.push({ type: "scatter", mode: "lines", x: xs, y: fan[midk], line: { width: 3, color: "#1f5fa8" }, name: "median", hovertemplate: "year %{x:.1f}: $%{y:,.0f}<extra>median</extra>" });
      ftr.push({ type: "scatter", mode: "lines", x: [0, xs[xs.length - 1]], y: [100000, 100000], line: { color: "#b3261e", dash: "dash", width: 1 }, name: "$100,000 start" });
      A.plot("ov-fan", ftr, { title: { text: "Simulated portfolio value over 7 years (" + label + ")", font: { size: 15 } }, xaxis: { title: "Years from today" }, yaxis: { tickprefix: "$", tickformat: "," } });
    } else { $("ov-fan").innerHTML = A.na("monte_carlo.fan"); }
  }
  drawFan(mc, "forward drift");
  if (mcH && mcH.fan) {
    $("ov-fan").insertAdjacentHTML("beforebegin", '<div class="controls" id="ov-fan-btns"><button type="button" data-f="f" class="on">Forward drift (the planning case)</button><button type="button" data-f="h">Historical drift (optimistic)</button></div>');
    $("ov-fan-btns").addEventListener("click", function (e) {
      var f = e.target.getAttribute && e.target.getAttribute("data-f"); if (!f) return;
      this.querySelectorAll("button").forEach(function (b) { b.classList.toggle("on", b === e.target); });
      drawFan(f === "f" ? mc : mcH, f === "f" ? "forward drift" : "historical drift");
    });
  }
  function tgBadges(tg) {
    var th = "";
    Object.keys(tg || {}).forEach(function (k) {
      var t = tg[k];
      if (k === "all_pass") { th += A.badge(t, "all five targets"); return; }
      if (!t || typeof t !== "object" || t.pass === undefined) return;
      var val = Math.abs(t.value) > 1.5 ? A.money(t.value) : A.pct(t.value, 1);
      th += A.badge(t.pass, k.replace(/_/g, " "), "value " + val + ", target " + (t.target !== undefined ? t.target : t.threshold));
    });
    return th;
  }
  var tg = pf.targets, th = tgBadges(tg);
  if (tg && tg.historical_drift) th += '<p class="small muted" style="width:100%">If the historical drift continued instead of the forward estimate:</p>' + tgBadges(tg.historical_drift);
  $("ov-targets").innerHTML = th || A.na("targets");
  if (tg && tg.note) $("ov-targets").insertAdjacentHTML("afterend", '<p class="small">' + A.esc(tg.note) + "</p>");
  function mv(v) { return !A.isNum(v) ? "n/a" : (Math.abs(v) > 1000 ? A.money(v) : A.pct(v)); }
  var mrows = [["median ending value", mv(mc.median), mcH ? mv(mcH.median) : "n/a"], ["5th percentile", mv(mc.p5), mcH ? mv(mcH.p5) : "n/a"], ["95th percentile", mv(mc.p95), mcH ? mv(mcH.p95) : "n/a"],
    ["probability of a loss", mv(mc.prob_loss), mcH ? mv(mcH.prob_loss) : "n/a"], ["probability of beating inflation", mv(mc.prob_beat_inflation), mcH ? mv(mcH.prob_beat_inflation) : "n/a"],
    ["median path's worst drawdown", mv(mc.dd), mcH ? mv(mcH.dd) : "n/a"]];
  $("ov-mc").innerHTML = Object.keys(mc0).length ? A.table(["Monte Carlo", "Forward drift", "Historical drift"], mrows) : A.na("monte_carlo");

  var vt = (pf.variants || []).filter(function (v) { return v && typeof v === "object"; });
  var more = vt.length ? "<h2>Variants tested (rebalance frequency, look-back, rule on/off)</h2>" + A.table(["Variant", "OOS " + A.gl("sharpe"), "OOS CAGR", "OOS max DD", "Full max DD", "Annual turnover", "Cost drag"],
    vt.map(function (v) { return [A.esc(v.variant), A.num(v.out_of_sample_sharpe), A.pct(v.out_of_sample_cagr), A.pct(v.out_of_sample_max_drawdown), A.pct(v.full_max_drawdown), A.pct(v.annual_turnover, 0), A.pct(v.annual_cost_drag, 2)]; })) : "";

    [["adjustments", "Periodic adjustments"], ["attribution", "Attribution"], ["sensitivity", "Sensitivity"]].forEach(function (x) { more += A.jsonBlock(x[1] + " (raw, from portfolio.json)", pf[x[0]]); });
  $("ov-more").innerHTML = more;
})();
