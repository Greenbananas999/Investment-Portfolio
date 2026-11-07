/* Compare: overlay any candidates. Growth series were built at build time from prices.csv and fx.csv. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var dates = PD.dates, meta = PD.meta, usd = PD.usd, local = PD.local, rolling = PD.rolling, metrics = PD.metrics;
  var GROUPS = ["pick", "runner-up", "candidate", "overlay", "faded leader", "control", "benchmark"];
  var GL = { "pick": "Picks", "runner-up": "Runners-up", "candidate": "Rejected candidates", "overlay": "Derivative overlays", "faded leader": "Faded leaders (survivorship control)", "control": "Other screened names", "benchmark": "Benchmarks" };
  var ids = Object.keys(meta).filter(function (k) { return usd[k]; });
  function grp(k) { var g = meta[k].group; return GROUPS.indexOf(g) < 0 ? "candidate" : g; }
  var sel = {}, filt = "all", color = {};
  ["NVDA", "2330.TW", "EMB", "IAU", "IVW"].forEach(function (k) { if (usd[k]) sel[k] = true; });
  ids.forEach(function (k, i) { color[k] = A.COLORS[i % A.COLORS.length]; });

  var gb = $("cmp-groups");
  gb.innerHTML = '<button type="button" data-g="all" class="on">All</button>' + GROUPS.filter(function (g) { return ids.some(function (k) { return grp(k) === g; }); })
    .map(function (g) { return '<button type="button" data-g="' + g + '">' + A.esc(GL[g].split(" (")[0]) + "</button>"; }).join("");
  gb.addEventListener("click", function (e) {
    var g = e.target.getAttribute && e.target.getAttribute("data-g"); if (!g) return;
    filt = g; gb.querySelectorAll("button").forEach(function (b) { b.classList.toggle("on", b === e.target); }); list();
  });
  $("cmp-search").addEventListener("input", list);
  $("cmp-picks").addEventListener("click", function () { sel = {}; ids.forEach(function (k) { if (grp(k) === "pick") sel[k] = true; }); list(); draw(); });
  $("cmp-clear").addEventListener("click", function () { sel = {}; list(); draw(); });
  var st = $("cmp-start");
  st.innerHTML = dates.map(function (d, i) { return i % 12 === 1 || i === 1 ? '<option value="' + i + '">' + d.slice(0, 7) + "</option>" : ""; }).join("") + '<option value="' + (dates.length - 1 - 36) + '">last 3 years</option>';
  st.addEventListener("change", draw);
  document.querySelectorAll("input[name=cmp-ccy]").forEach(function (r) { r.addEventListener("change", draw); });

  function list() {
    var q = $("cmp-search").value.toLowerCase(), h = "", last = null;
    GROUPS.forEach(function (g) {
      if (filt !== "all" && filt !== g) return;
      var items = ids.filter(function (k) { return grp(k) === g && (!q || (k + " " + meta[k].name).toLowerCase().indexOf(q) >= 0); });
      if (!items.length) return;
      h += '<div class="grp">' + A.esc(GL[g]) + "</div>";
      items.forEach(function (k) {
        h += '<label><input type="checkbox" data-k="' + A.esc(k) + '"' + (sel[k] ? " checked" : "") + '> <span style="color:' + color[k] + '">&#9632;</span> <b>' + A.esc(meta[k].label) + "</b> " + A.esc((meta[k].name || "").slice(0, 34)) + "</label>";
      });
    });
    var missing = Object.keys(meta).filter(function (k) { return !usd[k]; });
    if (missing.length && filt === "all") h += '<div class="grp">No price series</div><div class="small muted">' + A.esc(missing.join(", ")) + "</div>";
    $("cmp-list").innerHTML = h;
  }
  $("cmp-list").addEventListener("change", function (e) { var k = e.target.getAttribute("data-k"); if (k) { if (e.target.checked) sel[k] = true; else delete sel[k]; draw(); } });

  function series(k, wantLocal) {
    var src = wantLocal && local[k] ? local[k] : usd[k];
    var s0 = +st.value, i0 = -1;
    for (var i = s0; i < src.length; i++) { if (src[i] != null) { i0 = i; break; } }
    if (i0 < 0) return null;
    var base = src[i0], y = [], dd = [], peak = 0;
    for (var j = 0; j < src.length; j++) {
      if (j < i0 || src[j] == null) { y.push(null); dd.push(null); continue; }
      var v = 10000 * src[j] / base; y.push(v); peak = Math.max(peak, v); dd.push(v / peak - 1);
    }
    return { y: y, dd: dd, from: dates[i0], isLocal: !!(wantLocal && local[k]) };
  }

  function draw() {
    var wantLocal = document.querySelector("input[name=cmp-ccy]:checked").value === "local";
    var keys = Object.keys(sel).filter(function (k) { return usd[k]; }), g = [], d = [], rs = [], ri = [], rows = [];
    keys.forEach(function (k) {
      var s = series(k, wantLocal); if (!s) return;
      var nm = meta[k].label + (s.isLocal ? " (local)" : wantLocal ? " (USD, no local series)" : "");
      var common = { name: nm, legendgroup: k, line: { color: color[k], width: grp(k) === "benchmark" ? 2 : 2.5, dash: grp(k) === "benchmark" ? "dot" : "solid" } };
      g.push(Object.assign({ type: "scatter", mode: "lines", x: dates, y: s.y, hovertemplate: "%{x|%b %Y}: $%{y:,.0f}<extra>" + nm + "</extra>" }, common));
      d.push(Object.assign({ type: "scatter", mode: "lines", x: dates, y: s.dd, showlegend: false, hovertemplate: "%{x|%b %Y}: %{y:.1%}<extra>" + nm + "</extra>" }, common, { name: nm }));
      var r = rolling[k];
      if (r) {
        rs.push(Object.assign({ type: "scatter", mode: "lines", x: r.dates, y: r.sharpe, hovertemplate: "%{x|%b %Y}: %{y:.2f}<extra>" + nm + "</extra>" }, common, { name: nm }));
        ri.push(Object.assign({ type: "scatter", mode: "lines", x: r.dates, y: r.ir, showlegend: false, hovertemplate: "%{x|%b %Y}: %{y:.2f}<extra>" + nm + "</extra>" }, common, { name: nm }));
      }
      var M = metrics[k] || {}, mi = (M.is || {}).usd || {}, mo = (M.oos || {}).usd || {}, ml = (M.oos || {}).local || {};
      rows.push([A.esc(meta[k].label) + ' <span class="muted small">' + A.esc(grp(k)) + (s.from > dates[+st.value] ? ", from " + s.from.slice(0, 7) : "") + "</span>",
        A.num(mi.sharpe), A.num(mo.sharpe), A.pct(mi.cagr), A.pct(mo.cagr), A.pct(mo.max_drawdown), A.num(mi.info_ratio), A.num(mo.info_ratio), A.num(mo.t_stat_ir, 1), A.num(mo.deflated_sharpe),
        ml.cagr != null ? A.pct(ml.cagr) : "n/a", ml.sharpe != null ? A.num(ml.sharpe) : "n/a"]);
    });
    var yl = { gridcolor: "#e8ecf1" };
    A.plot("cmp-growth", g, { title: { text: "Growth of $10,000" + (wantLocal ? " (local currency where available)" : " (USD)"), font: { size: 15 } }, yaxis: Object.assign({ type: "log", tickprefix: "$", tickformat: "," }, yl), legend: { orientation: "h", y: -0.12 } });
    A.plot("cmp-dd", d, { title: { text: "Drawdown from the previous peak", font: { size: 15 } }, yaxis: { tickformat: ".0%" } });
    A.plot("cmp-rs", rs, { yaxis: { zeroline: true }, showlegend: false, margin: { l: 50, r: 10, t: 20, b: 40 } });
    A.plot("cmp-ri", ri, { yaxis: { zeroline: true }, showlegend: false, margin: { l: 50, r: 10, t: 20, b: 40 } });
    $("cmp-table").innerHTML = rows.length ? A.table(["Candidate", A.gl("sharpe") + " IS", "OOS", "CAGR IS", "OOS", A.gl("max_drawdown") + " OOS", A.gl("information_ratio", "Info ratio") + " IS", "OOS", A.gl("t_stat") + " (IR, OOS)", A.gl("deflated_sharpe") + " OOS", "OOS CAGR, local", "OOS Sharpe, local"], rows)
      + '<p class="small muted">Overlay rows show the difference between the overlaid sleeve and the underlying. Control names carry the OOS and IS figures from the control CSVs; blanks mean the file does not report that metric. Rolling charts need a candidate file, so benchmarks and controls have none.</p>' : "<p class=muted>Select at least one candidate.</p>";
  }
  list(); draw();
})();
